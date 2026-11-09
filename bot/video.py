"""Vidéo de la source (tweet, post Insta) : téléchargement, analyse image par image, puis mise en forme
plein cadre (DA v2) : titre posé sur la vidéo seulement si aucun texte incrusté ni visage ne le croise,
du début à la fin du passage gardé.
"""
import json
import subprocess
from pathlib import Path

from PIL import Image

from bot import placement
from bot.sources import http_get

MAX_OCTETS = 80 * 1024 * 1024
MAX_SECONDES = 58                 # Instagram : 60 s max par vidéo de carrousel
MAX_IMAGES = 40                   # images analysées par vidéo (texte incrusté + visages)
COTE_ANALYSE = 1280               # les images analysées sont réduites à ce côté maximum


def telecharger(cand, dossier, diag):
    """Renvoie le chemin du .mp4 source, ou None. Ne lève jamais d'exception."""
    for url in cand.get("videos", [])[:3]:
        try:
            r = http_get(url, stream=True)
            r.raise_for_status()
            dest = Path(dossier) / "source-video.mp4"
            dest.parent.mkdir(parents=True, exist_ok=True)
            taille = 0
            with open(dest, "wb") as f:
                for bloc in r.iter_content(1 << 16):
                    taille += len(bloc)
                    if taille > MAX_OCTETS:
                        raise ValueError("vidéo trop lourde")
                    f.write(bloc)
            if duree(dest) < 2:
                raise ValueError("vidéo illisible ou trop courte")
            diag.append(f"  vidéo · téléchargée ({duree(dest):.0f} s, {taille // 1_000_000} Mo)")
            return dest
        except Exception as ex:
            diag.append(f"  vidéo · échec : {str(ex)[:120]}")
    return None


def duree(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                        "default=nw=1:nk=1", str(f)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def a_du_son(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                        "-of", "json", str(f)], capture_output=True, text=True)
    try:
        return bool(json.loads(r.stdout or "{}").get("streams"))
    except json.JSONDecodeError:
        return False


def preparer(chemin, dossier, diag):
    """Analyse la vidéo (environ 1 image par seconde). Renvoie un dict utilisé par le carrousel et le Reel,
    ou None si la vidéo est illisible."""
    d = duree(chemin)
    if d < 2:
        return None
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    for vieux in dossier.glob("a-*.jpg"):
        vieux.unlink()
    pas = max(1.0, d / MAX_IMAGES)
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(chemin), "-vf",
                        f"fps=1/{pas:.3f},scale='min({COTE_ANALYSE},iw)':'min({COTE_ANALYSE},ih)'"
                        ":force_original_aspect_ratio=decrease", "-q:v", "3", str(dossier / "a-%04d.jpg")],
                       capture_output=True, text=True)
    fichiers = sorted(dossier.glob("a-*.jpg"))
    if r.returncode != 0 or not fichiers:
        diag.append(f"  vidéo · analyse impossible : {r.stderr[-120:]}")
        return None
    analyses = []
    for i, f in enumerate(fichiers):
        img = Image.open(f).convert("RGB")
        analyses.append(((i + 0.5) * pas, img, placement.analyser(img)))
    w, _ = taille(chemin)
    facteur = w / analyses[0][1].width if w else 1.0
    n = len(analyses)
    choisies = [analyses[min(n - 1, int(n * k / 6))] for k in range(6)] if n > 6 else analyses
    avec_texte = sum(1 for _, _, a in analyses if a["textes"])
    diag.append(f"  vidéo · {n} images analysées, texte incrusté sur {avec_texte}")
    return {"chemin": Path(chemin), "duree": d, "son": a_du_son(chemin), "analyses": analyses, "pas": pas,
            "facteur": facteur, "images": [{"img": img, "analyse": a, "nom": f"video@{t:.0f}s"}
                                           for t, img, a in choisies]}


def taille(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    try:
        w, h = r.stdout.strip().split("\n")[0].split(",")[:2]
        return int(w), int(h)
    except ValueError:
        return 0, 0


def placer(v, W, H, hauteur, durees, **opts):
    """Cherche un passage (le plus long possible parmi `durees`) où le bloc tombe proprement."""
    dernier = None
    for d in durees:
        d = min(d, v["duree"])
        if dernier and d >= dernier["fin"] - dernier["debut"] - 0.5:
            continue
        c = placement.choisir_video(v["analyses"], W, H, hauteur, d, **opts)
        if c and c["propre"]:
            return c
        dernier = c
    return None


def rendre(v, choix, sortie, W, H, debut, longueur, couche=None, son=True, boucle_jusqua=None):
    """Recadre la vidéo source (cadrage `choix`), pose le calque `couche` (PNG transparent) et encode.
    boucle_jusqua : durée finale si le passage doit tourner en boucle (sans son)."""
    f = v["facteur"]
    sw, sh = taille(v["chemin"])
    x0, y0, cw, ch = choix["fenetre"]
    cw, ch = min(sw, int(round(cw * f))), min(sh, int(round(ch * f)))
    x0, y0 = max(0, min(sw - cw, int(round(x0 * f)))), max(0, min(sh - ch, int(round(y0 * f))))
    entree = ["-ss", f"{debut:.2f}", "-t", f"{longueur:.2f}", "-i", str(v["chemin"])]
    if boucle_jusqua:
        tmp = Path(sortie).with_name(Path(sortie).stem + "-boucle.mp4")
        rendre(v, choix, tmp, W, H, debut, longueur, couche, son=False)
        entree = ["-stream_loop", "-1", "-i", str(tmp)]
        filtre = "[0:v]null[o]"
        couche = None
    else:
        filtre = f"[0:v]crop={cw}:{ch}:{x0}:{y0},scale={W}:{H}:flags=lanczos,setsar=1,fps=30[v0];"
        filtre += "[v0][1:v]overlay=0:0[o]" if couche else "[v0]null[o]"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *entree]
    if couche:
        cmd += ["-i", str(couche)]
    if son and v["son"] and not boucle_jusqua:
        cmd += ["-filter_complex", filtre + ";[0:a:0]aresample=44100,aformat=channel_layouts=stereo[a]",
                "-map", "[o]", "-map", "[a]"]
    else:
        n = 2 if couche else 1
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex", filtre,
                "-map", "[o]", "-map", f"{n}:a"]
    cmd += ["-t", f"{(boucle_jusqua or longueur):.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", str(sortie)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not Path(sortie).exists():
        raise RuntimeError(f"mise en forme de la vidéo impossible : {r.stderr[-200:]}")
    return Path(sortie)


def couverture(post, v, bloc, sortie, diag):
    """Slide 1 vidéo avec le titre posé dessus. None si aucun passage n'est assez propre."""
    from bot import da
    c = placer(v, da.W, da.H, bloc["h"], (MAX_SECONDES, 30, 20, 15, 10), fixes=da.FIXES_COUV)
    if not c:
        return None
    png = Path(sortie).with_suffix(".png")
    da.calque_couverture(post, c, bloc).save(png)
    try:
        rendre(v, c, sortie, da.W, da.H, c["debut"], c["fin"] - c["debut"], couche=png)
    except RuntimeError as ex:
        diag.append(f"  ⚠️ {str(ex)[:150]}")
        return None
    diag.append(f"  couverture vidéo · passage {c['debut']:.0f}-{c['fin']:.0f} s · zone {c['zone']} · "
                f"zoom {c['zoom']}")
    return Path(sortie)


def cadrage_centre(v, W, H):
    img = v["analyses"][0][1]
    _, x0, y0, cw, ch = placement._fenetre(img.width, img.height, W, H, (0.5, 0.5), 1.0)
    return {"fenetre": (x0, y0, cw, ch)}


def brute(v, sortie, W, H, longueur=MAX_SECONDES):
    """La vidéo telle quelle, recadrée plein cadre, sans rien dessus (avec son)."""
    return rendre(v, cadrage_centre(v, W, H), sortie, W, H, 0, min(longueur, v["duree"]))
