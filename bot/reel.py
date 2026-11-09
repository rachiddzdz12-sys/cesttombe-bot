"""Reel 1080x1920 (DA v2) : image ou vidéo plein écran, titre posé dessus, voix off + musique.

- Info avec vidéo : d'abord l'explication en voix off (sur la vidéo, coupée), puis la vidéo avec son son d'origine.
  Si le titre ne peut pas se poser proprement sur la vidéo : voix off sur la photo animée, puis la vidéo brute.
- Info sans vidéo : la photo (et les autres images) en zoom lent, titre dessus, voix off + musique.
"""
import subprocess
from pathlib import Path

from PIL import Image

import config
from bot import da, placement, voix
from bot import video as vid

W, H, FPS = da.RW, da.RH, 30
FONDU = 0.4
CLIP_MAX = 30          # secondes de vidéo d'origine, avec son, après la voix off
AMPLITUDE = 0.08       # zoom lent : de 100 % à 108 %


# ------------------------------------------------------------------ calques
def bloc_titre(post):
    return da.bloc_titre(post, W - 2 * da.M - 100, taille_max=112, taille_min=80)


def _y_pseudo(zone, y0, y1):
    return y1 + 22 if zone == "haut" else y0 - 58


def fixes_titre(hb):
    """Le pseudo suit le titre : juste au-dessus (ou juste en dessous s'il est en haut)."""
    def boites(zone):
        y0, y1 = placement.zone_y(zone, H, hb, da.REEL["bord_haut"], da.REEL["bord_bas"])
        yp = _y_pseudo(zone, y0, y1)
        return {"pseudo": (da.M - 10, yp - 8, 480, yp + 44)}
    return boites


def calque_titre(post, choix, bloc):
    def dessin(d):
        da.petit(d, config.HANDLE, da.M, _y_pseudo(choix["zone"], choix["y0"], choix["y1"]), taille=30)
        da.dessiner_titre(d, bloc, da.M, choix["y0"])
    return da.calque((W, H), dessin)


def calque_pseudo(choix):
    return da.calque((W, H), lambda d: da.petit(d, config.HANDLE, da.M, choix["y0"] + 8, taille=30))


# ------------------------------------------------------------------ photo animée
class Plan:
    """Une image plein écran qui zoome lentement, avec son calque de texte."""

    def __init__(self, img, fenetre, couche, duree, ampli=AMPLITUDE):
        x0, y0, cw, ch = fenetre
        self.base = img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize(
            (int(W * (1 + ampli)), int(H * (1 + ampli))), Image.LANCZOS)
        self.couche, self.duree, self.ampli = couche, duree, ampli

    def image(self, t):
        z = 1 + self.ampli * min(1.0, max(0.0, t) / self.duree)
        bw, bh = self.base.size
        vw, vh = bw / z, bh / z
        x, y = (bw - vw) / 2, (bh - vh) / 2
        im = self.base.resize((W, H), Image.BILINEAR, box=(x, y, x + vw, y + vh))
        if self.couche is not None:
            im = im.convert("RGBA")
            im.alpha_composite(self.couche)
            im = im.convert("RGB")
        return im


def _ampli_sure(media, choix, zone):
    """Réduit le zoom lent si, en fin de zoom, un texte ou un visage arrivait sous notre texte."""
    x0, y0, cw, ch = choix["fenetre"]
    for a in (AMPLITUDE, 0.04, 0.0):
        f = (x0 + cw * a / (2 * (1 + a)), y0 + ch * a / (2 * (1 + a)), cw / (1 + a), ch / (1 + a))
        _, t, v = placement.controle(media["analyse"], media["img"].width, media["img"].height, f, W, H, zone)
        if t == 0 and v == 0:
            return a
    return 0.0


def plans_photo(post, images, bloc, total, diag):
    """Première image : titre dessus ; les suivantes : juste le pseudo."""
    hb = bloc["h"]
    utilises = {}
    m0, c0 = da.meilleur_cadrage(images[:3], hb, utilises, W=W, H=H, fixes=fixes_titre(hb), **da.REEL)
    zone = (da.M, c0["y0"], W - da.REEL["marge_droite"], c0["y1"])
    plans = [[m0, c0, calque_titre(post, c0, bloc), _ampli_sure(m0, c0, zone)]]
    autres = [m for m in images if m["nom"] != m0["nom"]][:3]
    n = min(len(autres), max(0, int((total - 4) // 3)))
    for m in autres[:n]:
        c = placement.choisir(m["img"], m["analyse"], W, H, 50, zones=("haut",), bord_haut=da.REEL["bord_haut"],
                              fixes={})
        plans.append([m, c, calque_pseudo(c), AMPLITUDE])
    if len(plans) == 1:
        durees = [total]
    else:
        d0 = max(4.0, total * 0.45)
        durees = [d0] + [(total - d0) / (len(plans) - 1)] * (len(plans) - 1)
    diag.append(f"  reel · {len(plans)} image(s) animée(s), titre zone {c0['zone']}"
                f"{'' if c0['propre'] else ' (PAS PROPRE)'}")
    return [Plan(m["img"], c["fenetre"], couche, d, a) for (m, c, couche, a), d in zip(plans, durees)]


def video_des_plans(plans, sortie):
    total = sum(p.duree for p in plans)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-t", f"{total:.2f}", str(sortie)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i, p in enumerate(plans):
            for k in range(int(round(p.duree * FPS))):
                t = k / FPS
                im = p.image(t)
                if i + 1 < len(plans) and t > p.duree - FONDU:
                    im = Image.blend(im, plans[i + 1].image(0), (t - (p.duree - FONDU)) / FONDU)
                ff.stdin.write(im.tobytes())
        ff.stdin.close()
    except BrokenPipeError:
        pass
    if ff.wait() != 0 or not Path(sortie).exists():
        raise RuntimeError("ffmpeg n'a pas pu créer les images animées du Reel")
    return Path(sortie)


# ------------------------------------------------------------------ assemblage
def _avec_son(video_muette, piste, longueur, sortie):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video_muette)]
    cmd += ["-i", str(piste)] if piste else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
            "-t", f"{longueur:.2f}", "-movflags", "+faststart", str(sortie)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"assemblage son impossible : {r.stderr[-200:]}")
    return Path(sortie)


def _enchainer(partie1, partie2, sortie):
    """Voix off puis vidéo d'origine : le son d'origine est remis au niveau des réseaux sociaux."""
    filtre = ("[1:a]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100,aformat=channel_layouts=stereo,"
              "afade=t=in:d=0.25[a1];[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];"
              "[0:v]setsar=1[v0];[1:v]setsar=1[v1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(partie1), "-i", str(partie2), "-filter_complex", filtre,
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", str(sortie)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"enchaînement voix off → vidéo impossible : {r.stderr[-200:]}")
    return Path(sortie)


def fabriquer(post, medias, texte_voix, dossier, prefixe, diag):
    """medias = {"images": [...], "video": {...} ou None} (comme pour da.carrousel). Renvoie le .mp4."""
    dossier = Path(dossier)
    tmp = dossier / f"{prefixe}-reel-tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    audio = voix.lire(texte_voix, dossier / f"{prefixe}-audio", diag) if texte_voix else None
    duree_voix = voix.duree(audio) if audio else 0.0
    l1 = duree_voix + 0.8 if audio else 0.0
    v = medias.get("video")
    images = list(medias.get("images") or [])
    bloc = bloc_titre(post)
    sortie = dossier / f"{prefixe}-reel.mp4"

    if v:
        l2 = min(CLIP_MAX, v["duree"]) if v["son"] else 0.0
        if not l1 and not l2:
            l1 = min(CLIP_MAX, v["duree"])          # ni voix ni son : la vidéo sur la musique
        c = vid.placer(v, W, H, bloc["h"], (max(l1, l2), l2 or l1, 20, 15, 10), fixes=fixes_titre(bloc["h"]), **da.REEL)
        partie1 = partie2 = None
        if c:
            png = tmp / "titre.png"
            calque_titre(post, c, bloc).save(png)
            seg = c["fin"] - c["debut"]
            diag.append(f"  reel · titre sur la vidéo, passage {c['debut']:.0f}-{c['fin']:.0f} s, zone {c['zone']}")
            if l1:
                muet = vid.rendre(v, c, tmp / "p1.mp4", W, H, c["debut"], min(seg, l1), couche=png, son=False,
                                  boucle_jusqua=l1 if seg < l1 else None)
                partie1 = _avec_son(muet, mixer_audio(audio, l1, tmp / "mix.wav", diag), l1, tmp / "p1s.mp4")
            if l2:
                partie2 = vid.rendre(v, c, tmp / "p2.mp4", W, H, c["debut"], min(seg, l2), couche=png, son=True)
        else:
            diag.append("  reel · trop de texte incrusté sur la vidéo : voix off sur la photo, puis vidéo brute")
            if l1:
                pool = images or v["images"]
                muet = video_des_plans(plans_photo(post, pool, bloc, l1, diag), tmp / "p1.mp4")
                partie1 = _avec_son(muet, mixer_audio(audio, l1, tmp / "mix.wav", diag), l1, tmp / "p1s.mp4")
            if l2:
                partie2 = vid.rendre(v, vid.cadrage_centre(v, W, H), tmp / "p2.mp4", W, H, 0, l2, son=True)
        if partie1 and partie2:
            _enchainer(partie1, partie2, sortie)
        else:
            (partie1 or partie2).replace(sortie)
    else:
        total = l1 if l1 else 11.0
        pool = images or [{"img": da.fond_neutre((W, H)), "analyse": {"textes": [], "visages": []}, "nom": "neutre"}]
        muet = video_des_plans(plans_photo(post, pool, bloc, total, diag), tmp / "p1.mp4")
        _avec_son(muet, mixer_audio(audio, total, tmp / "mix.wav", diag), total, sortie)

    diag.append(f"  reel · {voix.duree(sortie):.1f} s {'avec voix' if audio else 'sans voix'}"
                f"{' + musique' if musique() else ''}{' + son de la vidéo' if v and v['son'] else ''}")
    return sortie


def musique():
    f = Path(__file__).resolve().parent.parent / config.MUSIQUE
    return f if config.MUSIQUE and f.exists() else None


def mixer_audio(voix_off, duree, sortie, diag):
    """Voix devant, musique loin derrière : la musique baisse encore quand la voix parle (ducking)."""
    fond = musique()
    t = f"{duree:.2f}"
    niveau = "loudnorm=I=-14:TP=-1.5:LRA=11"   # niveau standard des réseaux sociaux
    if not fond:
        if not voix_off:
            return None
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(voix_off), "-af",
               f"aresample=44100,aformat=channel_layouts=stereo,adelay=300|300,apad,atrim=0:{t},{niveau}",
               "-ar", "44100", "-t", t, str(sortie)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        return sortie if r.returncode == 0 else voix_off
    fin = max(0.0, duree - 1.5)
    vol = config.MUSIQUE_VOLUME if voix_off else config.MUSIQUE_VOLUME * 2.5
    entree_musique = ["-stream_loop", "-1", "-ss", str(config.MUSIQUE_DEBUT), "-i", str(fond)]
    musique_f = (f"aresample=44100,aformat=channel_layouts=stereo,atrim=0:{t},asetpts=N/SR/TB,"
                 f"volume={vol},afade=t=in:d=0.6,afade=t=out:st={fin:.2f}:d=1.5")
    if voix_off:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(voix_off), *entree_musique, "-filter_complex",
               f"[0:a]aresample=44100,aformat=channel_layouts=stereo,adelay=300|300,apad,atrim=0:{t},"
               f"asplit=2[v][cle];[1:a]{musique_f}[m];"
               f"[m][cle]sidechaincompress=threshold=0.02:ratio=5:attack=15:release=450[md];"
               f"[v][md]amix=inputs=2:normalize=0:duration=first,{niveau},alimiter=limit=0.89[out]",
               "-map", "[out]", "-ar", "44100", "-t", t, str(sortie)]
    else:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", *entree_musique, "-filter_complex",
               f"[0:a]{musique_f},{niveau}[out]", "-map", "[out]", "-ar", "44100", "-t", t, str(sortie)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        diag.append(f"  ⚠️ mixage musique impossible, voix seule : {r.stderr[-150:]}")
        return voix_off
    return sortie
