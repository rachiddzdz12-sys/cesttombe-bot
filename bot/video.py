"""Vidéo de la source (tweet, post Insta) : téléchargement puis mise en forme en slide 1080x1350 dans la DA."""
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from bot import rendu
from bot.sources import http_get

W, H = 1080, 1350
ZONE_HAUT, ZONE_H = 190, 980      # zone où la vidéo est posée, entre l'en-tête et le pied
MAX_OCTETS = 80 * 1024 * 1024
MAX_SECONDES = 58                 # Instagram : 60 s max par vidéo de carrousel


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


def _cadre(post, chemin):
    """Calque transparent : logo + tag en haut, source et pseudo en bas."""
    accent = rendu.ACCENTS.get(post["categorie"], rendu.ACCENTS["GAMING"])
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, ZONE_HAUT], fill=rendu.NOIR)
    d.rectangle([0, ZONE_HAUT + ZONE_H, W, H], fill=rendu.NOIR)
    rendu.logo(d, rendu.PAD, rendu.PAD, accent)
    rendu.tag(d, W - rendu.PAD, rendu.PAD, post["categorie"], accent)
    d.rectangle([0, ZONE_HAUT - 8, W, ZONE_HAUT], fill=accent)
    pied = ZONE_HAUT + ZONE_H + 70
    rendu.spaced(d, rendu.PAD, pied, f"VIDÉO · {post['source']}", rendu.grotesk(24, 500), rendu.GRIS, 3)
    d.text((W - rendu.PAD, pied), rendu.config.HANDLE, font=rendu.grotesk(26, 700), fill=rendu.BLANC, anchor="rm")
    img.save(chemin)


def slide(post, source, dossier, prefixe):
    """Fabrique la slide vidéo 1080x1350 (H.264 + AAC, 30 i/s, ≤ 58 s). Renvoie le .mp4."""
    dossier = Path(dossier)
    cadre = dossier / f"{prefixe}-cadre.png"
    _cadre(post, cadre)
    sortie = dossier / f"{prefixe}-2-video.mp4"
    t = min(MAX_SECONDES, duree(source))
    filtre = (f"[0:v]scale={W}:{ZONE_H}:force_original_aspect_ratio=decrease,setsar=1,"
              f"pad={W}:{H}:(ow-iw)/2:{ZONE_HAUT}+({ZONE_H}-ih)/2:color=0x0B0B0C,fps=30[v];"
              f"[v][1:v]overlay=0:0[out]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(source), "-i", str(cadre)]
    if a_du_son(source):
        cmd += ["-filter_complex", filtre, "-map", "[out]", "-map", "0:a:0"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex", filtre,
                "-map", "[out]", "-map", "2:a"]
    cmd += ["-t", f"{t:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-movflags", "+faststart", str(sortie)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not sortie.exists():
        raise RuntimeError(f"mise en forme de la vidéo impossible : {r.stderr[-200:]}")
    return sortie
