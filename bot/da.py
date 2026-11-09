"""DA v2 : photo ou vidéo plein cadre, texte posé directement dessus avec une ombre douce, juste le pseudo.

Le texte ne se pose jamais sur un texte déjà incrusté ni sur un visage (voir placement.py).
Carrousel : couverture (titre) puis une slide par partie du texte, chacune sur une autre image.
"""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import config
from bot import placement, rendu

W, H = 1080, 1350          # carrousel
RW, RH = 1080, 1920        # Reel
M = 72                     # marge
BLANC = rendu.BLANC
HAUTEUR_TEXTE_MAX = 660    # un paragraphe ne couvre jamais plus de la moitié de l'image
REEL = dict(bord_haut=290, bord_bas=520, marge_droite=170)   # zones sûres du Reel (interface Instagram)

FIXES_COUV = {"pseudo": (M, 50, 420, 112), "glisse": (760, 1215, W - M + 10, 1290)}
FIXES_TEXTE = {"pseudo": (M, 50, 420, 112), "pied": (600, 1215, W - M + 10, 1290)}
FIXES_FIN = {**FIXES_TEXTE, "source": (M - 10, 1215, 620, 1290)}


def accent(post):
    return rendu.ACCENTS.get(post["categorie"], rendu.ACCENTS["GAMING"])


# ------------------------------------------------------------------ texte + ombre
def calque(taille, dessin, halo=0.45):
    """Calque transparent : ce que dessin(draw) écrit, plus une ombre douce qui le détache de l'image.
    halo : voile sombre très diffus autour du texte (pas un cadre : il se fond dans l'image), pour rester
    lisible même sur un fond clair."""
    texte = Image.new("RGBA", taille, (0, 0, 0, 0))
    dessin(ImageDraw.Draw(texte))
    alpha = texte.split()[3]
    out = Image.new("RGBA", taille, (0, 0, 0, 0))
    if halo:
        petit_a = alpha.resize((taille[0] // 4, taille[1] // 4), Image.BILINEAR)
        voile = petit_a.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(14))
        voile = voile.resize(taille, Image.BILINEAR).point(lambda a: int(min(255, a * 1.4) * halo))
        couche = Image.new("RGBA", taille, (0, 0, 0, 0))
        couche.putalpha(voile)
        out.alpha_composite(couche)
    large = Image.new("RGBA", taille, (0, 0, 0, 0))
    large.putalpha(alpha.filter(ImageFilter.GaussianBlur(22)).point(lambda a: min(255, int(a * 1.6))))
    serree = Image.new("RGBA", taille, (0, 0, 0, 0))
    serree.putalpha(alpha.filter(ImageFilter.GaussianBlur(4)).point(lambda a: int(a * 0.9)))
    out.alpha_composite(large)
    out.alpha_composite(serree, (0, 3))
    out.alpha_composite(texte)
    return out


def poser(fond, couche):
    im = fond.convert("RGBA")
    im.alpha_composite(couche)
    return im.convert("RGB")


_D = ImageDraw.Draw(Image.new("RGB", (8, 8)))


def bloc_titre(post, largeur, taille_max=124, taille_min=84, lignes_max=4):
    mots = rendu.colored_words(post["titre"], post.get("mot_cle", ""), accent(post))
    taille = taille_max
    while True:
        f = rendu.anton(taille)
        lignes = rendu.wrap(_D, mots, f, largeur)
        if len(lignes) <= lignes_max or taille <= taille_min:
            break
        taille -= 6
    il = int(taille * 1.04)
    return {"lignes": lignes, "f": f, "il": il, "h": len(lignes) * il}


def dessiner_titre(d, bloc, x, y):
    sp = d.textlength(" ", font=bloc["f"])
    for ligne in bloc["lignes"]:
        xx = x
        for w, c in ligne:
            d.text((xx, y + bloc["il"] * 0.86), w, font=bloc["f"], fill=c, anchor="ls")
            xx += d.textlength(w, font=bloc["f"]) + sp
        y += bloc["il"]


def bloc_paragraphe(etiquette, texte, largeur, taille):
    f = rendu.grotesk(taille, 500)
    lignes = [" ".join(t for t, _ in l)
              for l in rendu.wrap(_D, [(w, None) for w in rendu.typo(texte).split()], f, largeur)]
    lh = int(taille * 1.32)
    return {"etiquette": rendu.typo(etiquette).upper(), "lignes": lignes, "f": f, "lh": lh,
            "h": 60 + len(lignes) * lh}


def dessiner_paragraphe(d, bloc, x, y, couleur):
    d.text((x, y + 28), bloc["etiquette"], font=rendu.grotesk(28, 700), fill=couleur, anchor="ls")
    y += 60
    for l in bloc["lignes"]:
        d.text((x, y + bloc["lh"] * 0.78), l, font=bloc["f"], fill=BLANC, anchor="ls")
        y += bloc["lh"]


def petit(d, texte, x, y, anchor="la", taille=26, poids=600, couleur=BLANC):
    d.text((x, y), texte, font=rendu.grotesk(taille, poids), fill=couleur, anchor=anchor)


def pages_de_texte(sections, largeur=W - 2 * M):
    """Découpe les sections en pages qui tiennent sur une image (46 px, sinon 42 px, sinon coupe en deux)."""
    pages = []
    for s in sections:
        for taille in (46, 42):
            b = bloc_paragraphe(s["titre"], s["texte"], largeur, taille)
            if b["h"] <= HAUTEUR_TEXTE_MAX:
                pages.append(b)
                break
        else:
            phrases = re.split(r"(?<=[.!?…])\s+", s["texte"].strip())
            moitie, cumul, total = 0, 0, len(s["texte"])
            for i, p in enumerate(phrases):
                cumul += len(p) + 1
                if cumul >= total / 2:
                    moitie = i + 1
                    break
            moitie = min(max(1, moitie), max(1, len(phrases) - 1))
            a, b = " ".join(phrases[:moitie]), " ".join(phrases[moitie:])
            pages.append(bloc_paragraphe(s["titre"], a, largeur, 42))
            if b:
                pages.append(bloc_paragraphe(s["titre"] + " (suite)", b, largeur, 42))
    return pages


# ------------------------------------------------------------------ choix des images
def fond_neutre(taille=(W, H)):
    """Pas d'image du tout : un fond sombre légèrement dégradé."""
    im = Image.new("RGB", taille, (11, 11, 12))
    d = ImageDraw.Draw(im)
    for y in range(taille[1]):
        g = int(11 + 14 * (1 - y / taille[1]))
        d.line([(0, y), (taille[0], y)], fill=(g, g, g + 1))
    return im


def meilleur_cadrage(pool, hauteur, utilises, **opts):
    """pool = [{"img", "analyse", "nom"}]. Choisit l'image + le cadrage où le bloc tombe le mieux,
    en préférant une image pas encore utilisée et sans répéter un cadrage déjà montré."""
    meilleur = None
    for strict in (True, False):          # si tout a déjà été montré, on accepte de répéter un cadrage
        for rang, m in enumerate(pool):
            deja = utilises.get(m["nom"], [])
            c = placement.choisir(m["img"], m["analyse"], hauteur_bloc=hauteur, eviter=deja if strict else (),
                                  **opts)
            if c is None:
                continue
            note = (c["propre"], -(c["cout"] + 40 * len(deja) + 3 * rang))
            if meilleur is None or note > meilleur[0]:
                meilleur = (note, m, c)
        if meilleur:
            break
    if meilleur is None:
        return None, None
    _, m, c = meilleur
    utilises.setdefault(m["nom"], []).append(c)
    return m, c


# ------------------------------------------------------------------ slides
def couverture(post, media, choix, bloc):
    fond = placement.recadrer(media["img"], choix, W, H)
    return poser(fond, calque_couverture(post, choix, bloc))


def calque_couverture(post, choix, bloc, taille=(W, H)):
    def dessin(d):
        petit(d, config.HANDLE, M, M)
        dessiner_titre(d, bloc, M, choix["y0"])
        petit(d, "GLISSE →", taille[0] - M, taille[1] - 92, anchor="rs", taille=26, poids=700)
    return calque(taille, dessin)


def slide_texte(post, media, choix, bloc, num, total, fin):
    fond = placement.recadrer(media["img"], choix, W, H)

    def dessin(d):
        petit(d, config.HANDLE, M, M)
        dessiner_paragraphe(d, bloc, M, choix["y0"], accent(post))
        if fin:
            src = f"SOURCE · {post['source']}"
            if post.get("credit") and post["credit"].lower() not in post["source"].lower():
                src += f" · PHOTO : {post['credit']}"
            petit(d, src[:48], M, H - 92, anchor="ls", taille=22, poids=500)
        petit(d, f"{num} / {total}", W - M, H - 92, anchor="rs", taille=26, poids=600)
    return poser(fond, calque((W, H), dessin))


def carrousel(post, medias, dossier, prefixe, diag):
    """medias = {"images": [{"img", "analyse", "nom"}], "video": {...} ou None} (voir video.preparer).

    Renvoie la liste des fichiers dans l'ordre du carrousel (.jpg et éventuellement .mp4)."""
    from bot import video as vid
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    images = list(medias.get("images") or [])
    if not images and not medias.get("video"):
        images = [{"img": fond_neutre(), "analyse": {"textes": [], "visages": []}, "nom": "neutre"}]
    bt = bloc_titre(post, W - 2 * M)
    utilises = {}
    fichiers = []

    # 1. couverture : la vidéo si le titre peut s'y poser proprement, sinon une image
    vcouv = None
    v = medias.get("video")
    if v:
        vcouv = vid.couverture(post, v, bt, dossier / f"{prefixe}-1-video.mp4", diag)
    if vcouv:
        fichiers.append(vcouv)
        pool_texte = images + v["images"]
    else:
        pool = images or v["images"]
        m, c = meilleur_cadrage(pool[:3], bt["h"], utilises, W=W, H=H, fixes=FIXES_COUV)
        f = dossier / f"{prefixe}-1.jpg"
        couverture(post, m, c, bt).save(f, "JPEG", quality=92, optimize=True)
        fichiers.append(f)
        diag.append(f"  couverture · {m['nom']} · zone {c['zone']} · zoom {c['zoom']} · "
                    f"{'propre' if c['propre'] else 'PAS PROPRE'}")
        if v:   # vidéo pleine de texte : elle passe brute en slide 2, sans rien dessus
            fichiers.append(vid.brute(v, dossier / f"{prefixe}-2-video.mp4", W, H))
            diag.append("  vidéo · trop de texte incrusté pour y poser le titre : slide 2 brute")
        pool_texte = images + (v["images"] if v else [])
        if not pool_texte:
            pool_texte = pool

    # 2. le texte, page par page, chacune sur une autre image
    pages = pages_de_texte(post["sections"])
    pages = pages[: config.MAX_SLIDES - len(fichiers)]
    total = len(fichiers) + len(pages)
    for i, bloc in enumerate(pages):
        num = len(fichiers) + 1
        fin = i == len(pages) - 1
        m, c = meilleur_cadrage(pool_texte, bloc["h"], utilises, W=W, H=H,
                                fixes=FIXES_FIN if fin else FIXES_TEXTE)
        f = dossier / f"{prefixe}-{num}.jpg"
        slide_texte(post, m, c, bloc, num, total, fin).save(f, "JPEG", quality=92, optimize=True)
        fichiers.append(f)
        if not c["propre"]:
            diag.append(f"  slide {num} · {m['nom']} : pas de zone parfaitement propre")
    return fichiers
