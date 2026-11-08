"""Reel maison 1080x1920 : photo qui zoome + gros titre, puis les slides de l'info, avec la voix off."""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from bot import rendu, voix

W, H, FPS = 1080, 1920, 30
PH_TOP, PH_H = 300, 760
FONDU = 0.4


def _fond_couverture(post, accent):
    img = Image.new("RGB", (W, H), rendu.NOIR)
    d = ImageDraw.Draw(img)
    rendu.logo(d, rendu.PAD, 180, accent)
    rendu.tag(d, W - rendu.PAD, 180, post["categorie"], accent)
    d.rectangle([0, PH_TOP + PH_H, W, PH_TOP + PH_H + 12], fill=accent)
    words = rendu.colored_words(post["titre"], post.get("mot_cle"), accent)
    rendu.titre_bloc(d, words, PH_TOP + PH_H + 60, 1560, 104)
    return img


def _plein(chemin):
    slide = Image.open(chemin).convert("RGB")
    img = Image.new("RGB", (W, H), rendu.NOIR)
    img.paste(slide, (0, (H - slide.height) // 2))
    return img


def fabriquer(post, photo, slides, texte_voix, dossier, prefixe, diag):
    """slides = fichiers JPEG du carrousel (le 1er est la couverture, ignorée ici). Renvoie le .mp4."""
    accent = rendu.ACCENTS.get(post["categorie"], rendu.ACCENTS["GAMING"])
    dossier = Path(dossier)
    audio = voix.lire(texte_voix, dossier / f"{prefixe}-audio", diag) if texte_voix else None
    duree_audio = voix.duree(audio) if audio else 0

    fond = _fond_couverture(post, accent)
    grand = None
    if photo is not None:
        cy = 0.12 if post["categorie"] == "RAP FR" else 0.4
        grand = ImageOps.fit(photo, (int(W * 1.1), int(PH_H * 1.1)), method=Image.LANCZOS, centering=(0.5, cy))
    pages = [_plein(s) for s in slides[1:]]

    # durées : la voix commande ; sinon 11 s par défaut
    total = max(duree_audio + 0.8, 9.0) if duree_audio else 11.0
    d_cov = max(3.5, total * 0.3)
    if len(pages) == 1:          # une seule slide de texte : elle prend tout le reste
        scenes = [("cov", d_cov), (pages[0], max(2.5, total - d_cov))]
    else:
        d_fin = 2.5
        d_mid = max(2.5, (total - d_cov - d_fin) / (len(pages) - 1))
        scenes = [("cov", d_cov)] + [(p, d_mid) for p in pages[:-1]] + [(pages[-1], d_fin)]

    def image(scene, t):
        nom, duree = scene
        if nom != "cov":
            return nom
        img = fond.copy()
        if grand is not None:
            z = 1.0 + 0.1 * min(1, t / duree)          # zoom lent de 100 % à 110 %
            w, h = int(W * z), int(PH_H * z)
            fr = grand.resize((w, h), Image.BILINEAR) if (w, h) != grand.size else grand
            x0 = (fr.width - W) // 2
            img.paste(fr.crop((x0, 0, x0 + W, PH_H)), (0, PH_TOP))
        return img

    sortie = dossier / f"{prefixe}-reel.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    cmd += ["-i", str(audio), "-af", "apad"] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest", "-movflags", "+faststart", str(sortie)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i, sc in enumerate(scenes):
            n = int(sc[1] * FPS)
            for k in range(n):
                t = k / FPS
                im = image(sc, t)
                if i + 1 < len(scenes) and t > sc[1] - FONDU:
                    im = Image.blend(im, image(scenes[i + 1], 0), (t - (sc[1] - FONDU)) / FONDU)
                ff.stdin.write(im.tobytes())
        ff.stdin.close()
    except BrokenPipeError:
        pass
    if ff.wait() != 0 or not sortie.exists():
        raise RuntimeError("ffmpeg n'a pas pu créer le Reel")
    diag.append(f"  reel · {voix.duree(sortie):.1f} s {'avec voix' if audio else 'muet'}")
    return sortie
