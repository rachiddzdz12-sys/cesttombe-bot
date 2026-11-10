"""DA v3 (forme reprise de @7run.club) : épurée, commerciale.

Carrousel 1080x1350 : logo texte + rubrique en haut, photo plein cadre assombrie vers le bas, accroche lime,
titre sur 2 lignes (blanc / lime), gros chiffre lime, paragraphe court, source, « 02 — 05 » et barre de
progression lime. Dernière slide : une question au lecteur + le pseudo.
Couverture de Reel 1080x1920 dans la même forme.
Le cadrage garde toujours le sujet (visage, personne, objet) entier et hors du texte (voir placement.py).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config
from bot import placement

RACINE = Path(__file__).resolve().parent.parent
POLICES = {"titre": "Oswald-Bold.ttf", "titre2": "Oswald-SemiBold.ttf", "texte": "SourceSans3-SemiBold.ttf",
           "texte_b": "SourceSans3-Bold.ttf", "label": "SpaceGrotesk.ttf"}
LIME = (200, 245, 70)
BLANC = (248, 247, 242)
NOIR = (12, 12, 13)
W, H, M = 1080, 1350, 58
RW, RH = 1080, 1920
_cache = {}


def police(nom, taille):
    cle = (nom, int(taille))
    if cle not in _cache:
        f = ImageFont.truetype(str(RACINE / "fonts" / POLICES[nom]), int(taille))
        if nom == "label":
            try:
                f.set_variation_by_axes([700])
            except Exception:
                pass
        _cache[cle] = f
    return _cache[cle]


_D = ImageDraw.Draw(Image.new("RGB", (8, 8)))


def largeur(texte, f, track=0.0):
    return sum(_D.textlength(c, font=f) for c in texte) + track * f.size * max(0, len(texte) - 1)


def espace(d, xy, texte, f, fill, track=0.0, anchor="ls"):
    """Texte aux lettres écartées (track × taille de police)."""
    x, y = xy
    w = largeur(texte, f, track)
    if anchor[0] == "r":
        x -= w
    elif anchor[0] == "m":
        x -= w / 2
    for c in texte:
        d.text((x, y), c, font=f, fill=fill, anchor="l" + anchor[1])
        x += d.textlength(c, font=f) + track * f.size
    return w


def ajuste(texte, nom, taille, largeur_max, mini=40, track=0.0):
    """Plus grande police (jusqu'à `taille`) pour que le texte tienne sur une ligne."""
    t = taille
    while t > mini and largeur(texte, police(nom, t), track) > largeur_max:
        t -= 4
    return police(nom, t)


def lignes(texte, f, largeur_max, n_max=None):
    out = []
    for mot in (texte or "").split():
        if out and largeur(out[-1] + " " + mot, f) <= largeur_max:
            out[-1] += " " + mot
        else:
            out.append(mot)
    if n_max and len(out) > n_max:
        out = out[:n_max]
        out[-1] = out[-1].rstrip(",;:") + "…"
    return out


def bloc(texte, nom, taille, largeur_max, n_max, mini=22):
    """Police la plus grande (jusqu'à `mini`) qui fait tenir le texte en n_max lignes, sans le couper."""
    for t in range(taille, mini - 1, -1):
        f = police(nom, t)
        out = lignes(texte, f, largeur_max)
        if len(out) <= n_max:
            return f, out
    return f, lignes(texte, f, largeur_max, n_max)


def degrade(taille, haut=0.45, debut=0.28, bas=0.9):
    """Voile sombre : léger en haut (logo), fort en bas (textes)."""
    w, h = taille
    a = Image.new("L", (1, h))
    for y in range(h):
        t = y / h
        v = haut * (1 - t / 0.2) ** 1.5 if t < 0.2 else 0.0
        if t > debut:
            v = max(v, bas * ((t - debut) / (1 - debut)) ** 1.25)
        a.putpixel((0, y), int(255 * min(1.0, v)))
    voile = Image.new("RGBA", (w, h), NOIR + (0,))
    voile.putalpha(a.resize((w, h)))
    return voile


def avec_ombre(couche, rayon=10, force=0.8):
    alpha = couche.split()[3]
    o = Image.new("RGBA", couche.size, (0, 0, 0, 0))
    o.putalpha(alpha.filter(ImageFilter.GaussianBlur(rayon)).point(lambda a: int(a * force)))
    out = Image.new("RGBA", couche.size, (0, 0, 0, 0))
    out.alpha_composite(o, (0, 3))
    out.alpha_composite(couche)
    return out


def logo(d, x, y, taille=44, centre=False):
    """Logo texte « C'EST TOMBÉ » ; (x, y) = haut des capitales (les accents débordent au-dessus)."""
    f = police("titre", taille)
    haut = f.getbbox("CEST", anchor="ls")[1]
    espace(d, (x, y - haut), "C'EST TOMBÉ", f, BLANC, track=0.06, anchor="ms" if centre else "ls")


def fleche(d, x, y, couleur=BLANC):
    d.line([x - 36, y, x, y], fill=couleur, width=3)
    d.line([x - 12, y - 9, x, y], fill=couleur, width=3)
    d.line([x - 12, y + 9, x, y], fill=couleur, width=3)


# ------------------------------------------------------------------ cadrage
FIXES_HAUT = {"logo": (M, 50, 430, 110), "rubrique": (W - 360, 60, W - M, 110)}


def cadre(media, W_, H_, hauteur_bloc, bas, fixes=None, eviter=(), zones=("bas",)):
    """Cadrage qui garde le sujet entier et hors du bloc de texte posé en bas (à `bas` px du bord)."""
    return placement.choisir(media["img"], media["analyse"], W_, H_, hauteur_bloc, zones=zones, bord_bas=bas,
                             fixes=fixes if fixes is not None else FIXES_HAUT, eviter=eviter)


def nettete(m):
    """Netteté de l'image (variance du laplacien sur une version réduite), gardée dans le média."""
    if "nettete" not in m:
        import cv2
        import numpy as np
        g = m["img"].convert("L")
        g = g.resize((512, max(1, int(512 * g.height / g.width))))
        m["nettete"] = float(cv2.Laplacian(np.asarray(g), cv2.CV_64F).var())
    return m["nettete"]


def flou(m, pool):
    """Pénalité d'une image floue (bougé d'une vidéo, photo de mauvaise qualité) par rapport aux autres."""
    ref = max(nettete(x) for x in pool)
    return 260 if ref > 0 and nettete(m) < 0.35 * ref else 0


def choisir_image(pool, hauteur_bloc, bas, utilises, penalite=None, fixes=None, W_=W, H_=H, zones=("bas",)):
    """Meilleure image + cadrage du pool (propre d'abord), en variant les images d'une slide à l'autre
    et en écartant les images floues."""
    meilleur = None
    for strict in (True, False):
        for rang, m in enumerate(pool):
            deja = utilises.get(m["nom"], [])
            c = cadre(m, W_, H_, hauteur_bloc, bas, fixes, deja if strict else (), zones)
            if c is None:
                continue
            note = (c["propre"], -(c["cout"] + 120 * len(deja) + 3 * rang + flou(m, pool)
                                   + (penalite(m) if penalite else 0)))
            if meilleur is None or note > meilleur[0]:
                meilleur = (note, m, c)
        if meilleur:
            break
    _, m, c = meilleur
    utilises.setdefault(m["nom"], []).append(c)
    return m, c


def fond(media, choix, W_=W, H_=H, debut=0.28):
    base = placement.recadrer(media["img"], choix, W_, H_).convert("RGBA")
    base.alpha_composite(degrade((W_, H_), debut=debut))
    return base


# ------------------------------------------------------------------ éléments communs
def entete(d, rubrique):
    logo(d, M, 62)
    if rubrique:
        f = police("label", 23)
        espace(d, (W - M, 95), rubrique.upper()[:22], f, BLANC, track=0.16, anchor="rs")


def barre(base, num, total):
    d = ImageDraw.Draw(base)
    d.rectangle([0, H - 10, W, H], fill=(60, 60, 62))
    d.rectangle([0, H - 10, int(W * num / total), H], fill=LIME)


def kicker(d, x, y, texte, couleur=LIME):
    d.rectangle([x, y - 13, x + 54, y - 9], fill=couleur)
    f = ajuste(texte.upper(), "label", 26, W - 2 * M - 72, mini=18, track=0.14)
    espace(d, (x + 72, y), texte.upper(), f, couleur, track=0.14)


def pied(d, num, total, source=None):
    if source:
        d.text((M, 1300), f"Source : {source}"[:70], font=police("texte", 20), fill=(215, 215, 210), anchor="ls")
    espace(d, (W - M, 1303), f"{num:02d} — {total:02d}", police("titre2", 30), BLANC, track=0.04, anchor="rs")


def titre_2_lignes(haut, bas, taille=118, largeur_max=W - 2 * M):
    """Police commune aux deux lignes du titre, la plus grande qui tient."""
    t = taille
    while t > 70 and max(largeur(haut.upper(), police("titre", t)), largeur(bas.upper(), police("titre", t))) > largeur_max:
        t -= 4
    return police("titre", t)


# ------------------------------------------------------------------ slides
def mesure_couverture(post):
    ft = titre_2_lignes(post["titre_haut"], post["titre_bas"])
    il = int(ft.size * 1.08)
    hauteur = 125 + 2 * il + (110 if post.get("chiffre") or post.get("chiffre_texte") else 0)
    return ft, il, hauteur


def couverture(post, media, choix, total):
    base = fond(media, choix)
    d0 = ImageDraw.Draw(base)
    tags = [t for t in post.get("mots_cles", []) if t][:4]
    if tags:   # bande de mots-clés lime
        d0.rectangle([0, 150, W, 212], fill=LIME)
        for i, t in enumerate(tags):
            f = ajuste(t.upper(), "label", 22, W / len(tags) - 24, mini=14, track=0.18)
            espace(d0, (W * (i + 0.5) / len(tags), 190), t.upper(), f, NOIR, track=0.18, anchor="ms")
    couche = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(couche)
    entete(d, post.get("rubrique"))
    ft, il, _ = mesure_couverture(post)
    a_stat = bool(post.get("chiffre"))
    y_bas = 1225 if (a_stat or post.get("chiffre_texte")) else 1240
    y2 = y_bas - 125 if (a_stat or post.get("chiffre_texte")) else y_bas
    y1 = y2 - il
    kicker(d, M, y1 - ft.size - 18, post.get("accroche_couv") or post.get("rubrique") or "C'est tombé")
    d.text((M, y1), post["titre_haut"].upper(), font=ft, fill=BLANC, anchor="ls")
    d.text((M, y2), post["titre_bas"].upper(), font=ft, fill=LIME, anchor="ls")
    fd = police("texte", 30)
    if a_stat:
        fs = ajuste(post["chiffre"].upper(), "titre", 92, 420, mini=50)
        lw = d.textlength(post["chiffre"].upper(), font=fs)
        d.text((M, y_bas), post["chiffre"].upper(), font=fs, fill=LIME, anchor="ls")
        xs = M + lw + 34
        d.rectangle([xs, y_bas - 82, xs + 2, y_bas + 4], fill=(230, 230, 225))
        fd, ls = bloc(post.get("chiffre_texte", ""), "texte", 30, W - M - xs - 40 - 150, 2)
        for k, l in enumerate(ls):
            d.text((xs + 32, y_bas - 48 + k * int(fd.size * 1.33)), l, font=fd, fill=BLANC, anchor="ls")
    elif post.get("chiffre_texte"):
        fd, ls = bloc(post["chiffre_texte"], "texte", 30, W - 2 * M - 180, 2)
        for k, l in enumerate(ls):
            d.text((M, y_bas - 40 + k * int(fd.size * 1.33)), l, font=fd, fill=BLANC, anchor="ls")
    espace(d, (W - M - 50, 1303), "GLISSE", police("titre2", 30), BLANC, track=0.06, anchor="rs")
    fleche(d, W - M, 1292)
    base.alpha_composite(avec_ombre(couche))
    barre(base, 1, total)
    return base.convert("RGB")


def mesure_slide(s):
    fp = police("texte", 33)
    lp = lignes(s.get("texte", ""), fp, W - 2 * M, 6)
    h = len(lp) * 46 + 62 + 40 + 80
    if s.get("gros") and not s.get("gros_bas"):
        h += 250
    else:
        h += 2 * 128 + 20
    return h + 60, lp


def interieure(post, s, media, choix, num, total, fin):
    base = fond(media, choix, debut=0.22)
    couche = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(couche)
    entete(d, post.get("rubrique"))
    _, lp = mesure_slide(s)
    fp = police("texte", 33)
    y_par = 1232 - (len(lp) - 1) * 46
    for k, l in enumerate(lp):
        d.text((M, y_par + k * 46), l, font=fp, fill=BLANC, anchor="ls")
    y_rule = y_par - 62
    d.rectangle([M, y_rule, M + 118, y_rule + 4], fill=BLANC)
    y_sous = y_rule - 40
    if s.get("sous_titre"):
        fs = ajuste(s["sous_titre"].upper(), "titre", 66, W - 2 * M, mini=40)
        d.text((M, y_sous), s["sous_titre"].upper(), font=fs, fill=BLANC, anchor="ls")
    else:
        y_sous += 70
    if s.get("gros") and not s.get("gros_bas"):
        fg = ajuste(s["gros"].upper(), "titre", 250, W - 2 * M, mini=110)
        y_g = y_sous - 82
        d.text((M - 6, y_g), s["gros"].upper(), font=fg, fill=LIME, anchor="ls")
        y_kick = y_g - fg.size
    else:
        haut, bas = s.get("gros_haut") or s.get("gros") or "", s.get("gros_bas") or ""
        ft = titre_2_lignes(haut, bas)
        y_g2 = y_sous - 92
        d.text((M, y_g2), bas.upper(), font=ft, fill=LIME, anchor="ls")
        d.text((M, y_g2 - int(ft.size * 1.08)), haut.upper(), font=ft, fill=BLANC, anchor="ls")
        y_kick = y_g2 - int(ft.size * 1.08) - ft.size - 22
    kicker(d, M, y_kick, s.get("rubrique") or "")
    pied(d, num, total, post.get("source_affichee") if fin else None)
    base.alpha_composite(avec_ombre(couche))
    barre(base, num, total)
    return base.convert("RGB")


def finale(post, media, choix, total):
    base = placement.recadrer(media["img"], choix, W, H).convert("RGBA")
    base = base.filter(ImageFilter.GaussianBlur(3)).convert("RGBA")
    base.alpha_composite(Image.new("RGBA", (W, H), NOIR + (180,)))
    couche = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(couche)
    logo(d, W / 2, 410, 64, centre=True)
    q1, q2 = post.get("question_haut") or "Et toi,", post.get("question_bas") or "t'en penses quoi ?"
    ft = titre_2_lignes(q1, q2, taille=104, largeur_max=W - 2 * M)
    d.text((W / 2, 640), q1.upper(), font=ft, fill=BLANC, anchor="ms")
    d.text((W / 2, 640 + int(ft.size * 1.15)), q2.upper(), font=ft, fill=LIME, anchor="ms")
    y = 640 + int(ft.size * 1.15) + 80
    fl = police("texte_b", 34)
    pw = d.textlength(config.HANDLE, font=fl) + 80
    d.rounded_rectangle([W / 2 - pw / 2, y, W / 2 + pw / 2, y + 70], radius=35, outline=BLANC, width=3)
    d.text((W / 2, y + 47), config.HANDLE, font=fl, fill=BLANC, anchor="ms")
    d.text((W / 2, y + 137), "Abonne-toi pour ne rien rater", font=police("texte", 26), fill=(225, 225, 220),
           anchor="ms")
    espace(d, (W - M, 1303), f"{total:02d} — {total:02d}", police("titre2", 30), BLANC, track=0.04, anchor="rs")
    base.alpha_composite(avec_ombre(couche))
    barre(base, total, total)
    return base.convert("RGB")


def fond_neutre(taille=(W, H)):
    im = Image.new("RGB", taille, (16, 16, 18))
    d = ImageDraw.Draw(im)
    for y in range(taille[1]):
        g = int(16 + 18 * (1 - y / taille[1]))
        d.line([(0, y), (taille[0], y)], fill=(g, g, g + 2))
    return im


def de_la_source(images, video=None):
    src = [m for m in images if m.get("origine", "source") == "source"] + (video["images"] if video else [])
    return src or list(images)


def carrousel(post, medias, dossier, prefixe, diag):
    """Carrousel DA v3 (images seulement). Renvoie la liste des .jpg dans l'ordre."""
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    v = medias.get("video")
    images = list(medias.get("images") or [])
    pool = images + (v["images"] if v else [])
    if not pool:
        pool = [{"img": fond_neutre(), "analyse": {"textes": [], "visages": [], "sujet": None}, "nom": "neutre"}]
    slides = post["slides"][: config.MAX_SLIDES - 2]
    total = len(slides) + 2
    utilises = {}
    fichiers = []
    # 1. couverture : toujours une image de la source (photo ou image de la vidéo)
    _, _, h_couv = mesure_couverture(post)
    m, c = choisir_image(de_la_source(images, v) or pool, h_couv, 1350 - 1240,
                         utilises, fixes={**FIXES_HAUT, "bande": (0, 150, W, 212)})
    f = dossier / f"{prefixe}-1.jpg"
    couverture(post, m, c, total).save(f, "JPEG", quality=92, optimize=True)
    fichiers.append(f)
    diag.append(f"  couverture · {m['nom']} · zoom {c['zoom']} · {'propre' if c['propre'] else 'PAS PROPRE'}")
    couv = m
    # 2. une slide par partie, chacune sur une autre image (d'abord les photos venues d'ailleurs)
    autres = any(x.get("origine") == "autre" for x in pool)

    def varier(x):
        return 80 if autres and x.get("origine", "source") == "source" else 0

    for i, s in enumerate(slides):
        h, _ = mesure_slide(s)
        m, c = choisir_image(pool, h, 1350 - 1250, utilises, penalite=varier)
        f = dossier / f"{prefixe}-{i + 2}.jpg"
        interieure(post, s, m, c, i + 2, total, fin=(i == len(slides) - 1)).save(f, "JPEG", quality=92,
                                                                                optimize=True)
        fichiers.append(f)
        if not c["propre"]:
            diag.append(f"  slide {i + 2} · {m['nom']} : pas de zone parfaitement propre")
    # 3. question au lecteur
    c = cadre(couv, W, H, 600, 300, fixes={}, zones=("milieu",))
    f = dossier / f"{prefixe}-{total}.jpg"
    finale(post, couv, c, total).save(f, "JPEG", quality=92, optimize=True)
    fichiers.append(f)
    return fichiers


# ------------------------------------------------------------------ couverture de Reel
def puce(d, x, y, cat, sujet):
    f = police("label", 22)
    w = largeur(cat.upper(), f, 0.12)
    d.rectangle([x, y, x + w + 24, y + 40], fill=LIME)
    espace(d, (x + 12, y + 29), cat.upper(), f, NOIR, track=0.12)
    if sujet:
        fs = ajuste(sujet.upper(), "label", 22, RW - x - w - 110, mini=14, track=0.12)
        espace(d, (x + w + 40, y + 29), sujet.upper(), fs, BLANC, track=0.12)


def couverture_reel(post, medias):
    v = medias.get("video")
    pool = de_la_source(list(medias.get("images") or []), v) or \
        [{"img": fond_neutre((RW, RH)), "analyse": {"textes": [], "visages": [], "sujet": None}, "nom": "neutre"}]
    m, c = choisir_image(pool, 520, 1920 - 1660, {}, fixes={"logo": (60, 55, 470, 125)}, W_=RW, H_=RH)
    base = fond(m, c, RW, RH, debut=0.4)
    couche = Image.new("RGBA", (RW, RH), (0, 0, 0, 0))
    d = ImageDraw.Draw(couche)
    logo(d, 62, 70, 52)
    ft = titre_2_lignes(post["titre_haut"], post["titre_bas"], taille=112, largeur_max=RW - 124)
    puce(d, 62, 1450 - ft.size * 2 - 60, post.get("rubrique") or "Actu", post.get("accroche_couv") or "")
    d.text((62, 1450), post["titre_haut"].upper(), font=ft, fill=BLANC, anchor="ls")
    d.text((62, 1450 + int(ft.size * 1.1)), post["titre_bas"].upper(), font=ft, fill=LIME, anchor="ls")
    sous = post.get("chiffre_texte") or ""
    if sous:
        fs, ls = bloc(sous, "texte", 36, RW - 124, 2, mini=28)
        for k, l in enumerate(ls):
            d.text((62, 1450 + int(ft.size * 1.1) + 68 + int(fs.size * 1.28) * k), l, font=fs, fill=BLANC,
                   anchor="ls")
    base.alpha_composite(avec_ombre(couche))
    return base.convert("RGB")
