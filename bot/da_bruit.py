"""Carrousel 1080x1350 dans la DA « LE BRUIT » (même interface que da3.carrousel).
Cartes : Breaking news (couverture), Décryptage (gros chiffre), Artiste, Récit, Fin (question + logo)."""
from pathlib import Path

from PIL import ImageDraw

import config
from bot import bruit_base as bb
from bot.bruit_base import BLANC, GRIS, VIOLET, VIOLET_TXT, couper, ecrire, largeur, police

W, H, M = 1080, 1350, 78
F_KICK = police(600, 27)
F_PIED = police(700, 22)


def nom_court():
    return getattr(config, "NOM_PAGE", "LE BRUIT")


def cadre_carte(img):
    ImageDraw.Draw(img).rectangle((0, 0, W - 1, H - 1), outline=(70, 70, 78), width=2)


def entete(img, kicker):
    d = ImageDraw.Draw(img)
    x = ecrire(d, M, 104, (kicker or "Breaking news").upper(), F_KICK, BLANC, track=2)
    d.line((x + 24, 94, x + 124, 94), fill=VIOLET, width=3)
    lg = bb.logo(50)
    img.alpha_composite(lg, (W - M - lg.width, 66))


def pied(img, n, total):
    d = ImageDraw.Draw(img)
    ecrire(d, M, H - 62, nom_court(), F_PIED, BLANC, track=3)
    txt = f"{n} / {total}"
    ecrire(d, W - M - largeur(txt, F_PIED, 2), H - 62, txt, F_PIED, BLANC, track=2)


def fond(media, assombrir=0.78, gauche=True):
    if media is None:
        return bb.fond_noir(W, H)
    if bb.mode_photo(media, W, H) == "haut":
        return bb.fond_haut(media, W, H, hauteur=int(H * 0.72), y=0, assombrir=assombrir + 0.06)
    return bb.fond_plein(media, W, H, assombrir=assombrir, gauche=gauche)


def finir(img, n, total):
    pied(img, n, total)
    cadre_carte(img)
    return bb.grain(img, 4, n).convert("RGB")


# ------------------------------------------------------------------ cartes
def couverture(post, media, n, total):
    img = fond(media)
    img.alpha_composite(bb.arcs(W, H, ("bas-droite",), 0.9))
    entete(img, post.get("rubrique") or "Breaking news")
    lmax = W - 2 * M - 40
    f, lh = bb.ajuster(post.get("titre_haut") or "", 800, 100, lmax, 2, mini=64)
    lb = bb.tenir(post.get("titre_bas") or "", f, lmax, 2)
    if lb and not lb[-1].endswith((".", "?", "!")):
        lb[-1] += "."
    lignes = lh + lb
    pas, y_bas = int(f.size * 0.98), H - 210
    fs, sous = bb.ajuster(post.get("chiffre_texte") or "", 500, 38, W - 2 * M - 160, 3, mini=32)
    ps = int(fs.size * 1.26)
    h = pas * len(lignes) + (24 + ps * len(sous) if sous else 0)
    y0 = y_bas - h

    def dessiner(d, force=None):
        for i, l in enumerate(lignes):
            ecrire(d, M, y0 + pas * (i + 1), l, f, force or (VIOLET_TXT if i >= len(lh) else BLANC), track=-2)
        for k, s in enumerate(sous):
            ecrire(d, M, y0 + pas * len(lignes) + 24 + ps * (k + 1) - 8, s, fs, force or GRIS)

    bb.ombre(img, dessiner)
    d = ImageDraw.Draw(img)
    dessiner(d)
    d.rectangle((M - 32, y0 + 16, M - 28, y_bas + 6), fill=VIOLET)
    return finir(img, n, total)


def chiffre(media, kicker, valeur, texte, detail, n, total):
    """Carte « Décryptage » : gros chiffre (unité en violet) + explication, petite courbe violette."""
    img = fond(media, assombrir=0.55)
    img.alpha_composite(bb.arcs(W, H, ("haut-droite",), 0.7))
    entete(img, kicker)
    nombre, unite = bb.decouper_chiffre(valeur)
    f = police(900, 250 if len(nombre) <= 4 else 190)
    ft, lt = bb.ajuster(texte or "", 500, 46, 640, 3, mini=36)

    def dessiner(dd, force=None):
        if nombre == "N°":
            x = ecrire(dd, M - 4, 640, "N°", police(900, int(f.size * 0.55)), force or VIOLET_TXT)
            ecrire(dd, x + 8, 640, unite, f, force or BLANC, track=-8)
        else:
            x = ecrire(dd, M - 6, 640, nombre, f, force or BLANC, track=-8)
            if unite:
                ecrire(dd, x + 10, 640, unite, police(900, int(f.size * 0.6)), force or VIOLET_TXT)
        for k, l in enumerate(lt):
            ecrire(dd, M, 730 + int(ft.size * 1.26) * k, l, ft, force or BLANC)

    bb.ombre(img, dessiner, rayon=18)
    d = ImageDraw.Draw(img)
    dessiner(d)
    pts = [(560, 1090), (640, 1070), (700, 1040), (760, 1046), (820, 1000), (880, 990), (940, 930), (1000, 860)]
    d.line(pts, fill=VIOLET, width=4)
    for p in pts[1:-1]:
        d.ellipse((p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6), fill=VIOLET)
    texte_bas(img, detail, H - 140)
    return finir(img, n, total)


def artiste(media, kicker, nom, sous, texte, n, total):
    img = fond(media, assombrir=0.62)
    entete(img, kicker or "Artiste")
    f, lignes = bb.ajuster(nom, 800, 130, W - 2 * M, 2, mini=80, track_ratio=-0.025)
    fs, ls = bb.ajuster(sous or "", 500, 46, 600, 2, mini=36)
    y = 560 + int(f.size * 0.98) * (2 - len(lignes)) // 2

    def dessiner(dd, force=None):
        for i, l in enumerate(lignes):
            ecrire(dd, M, y + int(f.size * 0.98) * i, l, f, force or BLANC, track=-3)
        for k, l in enumerate(ls):
            ecrire(dd, M, y + int(f.size * 0.98) * (len(lignes) - 1) + 70 + 56 * k, l, fs, force or BLANC)

    bb.ombre(img, dessiner)
    d = ImageDraw.Draw(img)
    dessiner(d)
    yb = y + int(f.size * 0.98) * (len(lignes) - 1) + 70 + 56 * len(ls) - 30
    d.rectangle((M, yb, M + 90, yb + 5), fill=VIOLET)
    texte_bas(img, texte, H - 120)
    return finir(img, n, total)


def texte_bas(img, texte, y_bas, source=None):
    if not texte and not source:
        return
    fs, lignes = bb.ajuster(texte or "", 500, 36, W - 2 * M - 60, 4, mini=30)
    pt = int(fs.size * 1.33)
    y0 = y_bas - pt * len(lignes)

    def dessiner(dd, force=None):
        for k, l in enumerate(lignes):
            ecrire(dd, M, y0 + pt * (k + 1), l, fs, force or GRIS)

    bb.ombre(img, dessiner, rayon=10)
    d = ImageDraw.Draw(img)
    dessiner(d)
    if source:
        ecrire(d, M, y_bas + 38, f"Source : {source}", police(500, 22), (150, 150, 158))


def recit(media, slide, n, total, source=None):
    img = fond(media, assombrir=0.6)
    img.alpha_composite(bb.arcs(W, H, ("haut-gauche",), 0.6))
    entete(img, slide.get("rubrique") or "Culture")
    haut = slide.get("gros_haut") or slide.get("gros") or ""
    bas = slide.get("gros_bas") or ""
    f = police(800, 96)
    lh, lb = bb.tenir(haut, f, W - 2 * M, 2), bb.tenir(bas, f, W - 2 * M, 2)
    lignes = lh + lb
    y_bas, pas = 820, 94
    y0 = y_bas - pas * len(lignes)
    sous = slide.get("sous_titre") or ""
    fsous, _ls = bb.ajuster(sous, 500, 42, W - 2 * M, 1, mini=30)
    sous = _ls[0] if _ls else ""

    def dessiner(dd, force=None):
        for i, l in enumerate(lignes):
            ecrire(dd, M, y0 + pas * (i + 1), l, f, force or (VIOLET_TXT if i >= len(lh) else BLANC), track=-2)
        if sous:
            ecrire(dd, M, y_bas + 62, sous, fsous, force or BLANC)

    bb.ombre(img, dessiner)
    d = ImageDraw.Draw(img)
    dessiner(d)
    d.rectangle((M - 32, y0 + 16, M - 28, y_bas + (70 if sous else 8)), fill=VIOLET)
    if sous:
        d.rectangle((M, y_bas + 92, M + 70, y_bas + 96), fill=VIOLET)
    texte_bas(img, slide.get("texte") or "", H - 150 if source else H - 120, source=source)
    return finir(img, n, total)


def finale(post, n, total):
    img = bb.fond_noir(W, H)
    img.alpha_composite(bb.arcs(W, H, ("bas-droite", "haut-gauche"), 0.9))
    d = ImageDraw.Draw(img)
    f = police(800, 84)
    q1 = couper(post.get("question_haut") or "Et toi,", f, W - 2 * M)
    q2 = couper(post.get("question_bas") or "t'en penses quoi ?", f, W - 2 * M)
    for i, l in enumerate(q1 + q2):
        ecrire(d, (W - largeur(l, f, -2)) / 2, 300 + 92 * i, l, f, VIOLET_TXT if i >= len(q1) else BLANC, track=-2)
    lg = bb.logo(190)
    img.alpha_composite(lg, ((W - lg.width) // 2, 640))
    fn = police(500, 46)
    nom = nom_court()
    ecrire(d, (W - largeur(nom, fn, 26)) / 2, 950, nom, fn, BLANC, track=26)
    tag = "RAP  ·  CULTURE  ·  ACTUALITÉ"
    ecrire(d, (W - largeur(tag, police(500, 22), 7)) / 2, 1010, tag, police(500, 22), GRIS, track=7)
    s = "ABONNE-TOI POUR NE RIEN RATER"
    f2 = police(600, 24)
    ecrire(d, (W - largeur(s, f2, 4)) / 2, 1160, s, f2, BLANC, track=4)
    d.line(((W - 90) / 2, 1190, (W + 90) / 2, 1190), fill=VIOLET, width=3)
    return finir(img, n, total)


# ------------------------------------------------------------------ choix des images
class Choix:
    """Distribue les images entre les slides : la couverture vient de la source, ensuite on varie
    (d'abord les photos d'artistes trouvées ailleurs), en évitant les images couvertes de texte."""

    def __init__(self, pool):
        self.pool = pool
        self.n = {id(m): 0 for m in pool}

    def prendre(self, source_dabord=False):
        if not self.pool:
            return None

        def cle(m):
            return (self.n[id(m)], (0 if m.get("origine", "source") == "source" else 1) if source_dabord
                    else (1 if m.get("origine", "source") == "source" else 0), bb.a_du_texte(m))

        m = min(self.pool, key=cle)
        self.n[id(m)] += 1
        return m


def doublon_chiffre(gros, chiffre_post):
    """Une partie dont le gros chiffre est celui de la carte « Décryptage » ferait doublon."""
    if not gros or not any(c.isdigit() for c in gros):
        return False
    return bb.decouper_chiffre(gros) == bb.decouper_chiffre(chiffre_post)


def carrousel(post, medias, dossier, prefixe, diag):
    """Renvoie la liste des .jpg dans l'ordre (couverture, chiffre, parties, question)."""
    bb.casse_normale(post)
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    v = medias.get("video")
    pool = list(medias.get("images") or []) + (list(v["images"])[:3] if v else [])
    choix = Choix(pool)
    a_chiffre = bool((post.get("chiffre") or "").strip())
    slides = [s for s in (post.get("slides") or [])
              if not (a_chiffre and doublon_chiffre(s.get("gros"), post["chiffre"]))][: config.MAX_SLIDES - 3]
    total = 2 + len(slides) + (1 if a_chiffre else 0)
    images, n = [], 1
    m = choix.prendre(source_dabord=True)
    images.append(couverture(post, m, n, total))
    diag.append(f"  couverture LE BRUIT · {m['nom'] if m else 'fond noir'} · {bb.mode_photo(m, W, H) if m else ''}")
    n += 1
    if a_chiffre:
        kicker = "Classements" if (post.get("rubrique") or "").lower() == "classements" else "Décryptage"
        images.append(chiffre(choix.prendre(), kicker, post["chiffre"], post.get("chiffre_texte") or "", "", n, total))
        n += 1
    for i, s in enumerate(slides):
        derniere = i == len(slides) - 1
        source = post.get("source_affichee") if derniere else None
        gros = (s.get("gros") or "").strip()
        m = choix.prendre()
        if gros and any(c.isdigit() for c in gros):
            texte = " ".join(x for x in (s.get("sous_titre"), ) if x)
            images.append(chiffre(m, s.get("rubrique") or "Décryptage", gros, texte, s.get("texte") or "", n, total))
        elif gros and not s.get("gros_haut") and len(gros) <= 16:
            images.append(artiste(m, s.get("rubrique") or "Artiste", gros, s.get("sous_titre") or "",
                                  s.get("texte") or "", n, total))
        else:
            images.append(recit(m, s, n, total, source=source))
        n += 1
    images.append(finale(post, n, total))
    fichiers = []
    for i, im in enumerate(images, start=1):
        f = dossier / f"{prefixe}-{i}.jpg"
        im.save(f, "JPEG", quality=92, optimize=True)
        fichiers.append(f)
    return fichiers


def couverture_reel(post, medias):
    """Couverture 1080x1920 du Reel (même carte que l'accroche du Reel)."""
    from bot import reel_bruit
    return reel_bruit.couverture(post, medias)
