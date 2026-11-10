"""Choisit où poser notre texte sur une image : jamais sur un texte déjà incrusté, jamais sur un visage,
de préférence sur une zone calme et sombre.

analyser(img)  → textes et visages détectés dans l'image source
choisir(...)   → meilleur cadrage + meilleure zone pour un bloc de texte donné
"""
from functools import lru_cache

import numpy as np
from PIL import Image

_MARGE = 24          # on garde de l'air autour des textes et visages détectés
TEXTE_GENANT = 0.02  # hauteur (part de l'image finale) à partir de laquelle un texte incrusté gêne partout


@lru_cache(maxsize=1)
def _ocr():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


@lru_cache(maxsize=1)
def _visages():
    import cv2
    return cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


@lru_cache(maxsize=1)
def _profils():
    import cv2
    return cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")


def analyser(img):
    """Renvoie {"textes": [(x0,y0,x1,y1)], "visages": [...]} en pixels de l'image source."""
    import cv2
    rgb = np.array(img.convert("RGB"))
    textes = []
    try:
        res, _ = _ocr()(rgb)
        for boite, texte, conf in res or []:
            if float(conf) < 0.5 or len(str(texte).strip()) < 2:
                continue
            xs, ys = [p[0] for p in boite], [p[1] for p in boite]
            textes.append((min(xs), min(ys), max(xs), max(ys)))
    except Exception:
        pass
    gris = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    mini = max(24, min(gris.shape) // 25)        # visages assez petits aussi (photo de plain-pied)
    visages = [(x, y, x + w, y + h) for x, y, w, h in
               _visages().detectMultiScale(gris, scaleFactor=1.1, minNeighbors=6, minSize=(mini, mini))]
    # visages de profil, tournés d'un côté ou de l'autre
    larg = gris.shape[1]
    for miroir in (False, True):
        g = cv2.flip(gris, 1) if miroir else gris
        for x, y, w, h in _profils().detectMultiScale(g, scaleFactor=1.1, minNeighbors=6, minSize=(mini, mini)):
            x0 = larg - x - w if miroir else x
            visages.append((x0, y, x0 + w, y + h))
    return {"textes": textes, "visages": visages, **_sujet(gris, visages)}


@lru_cache(maxsize=1)
def _corps():
    import cv2
    return cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_upperbody.xml")


def _saillance(gris):
    """Zone la plus « parlante » de l'image (résidu spectral, Hou & Zhang 2007) quand il n'y a ni visage ni
    buste : c'est en général l'objet ou le personnage principal. Renvoie (x0, y0, x1, y1)."""
    import cv2
    h, w = gris.shape
    petit = cv2.resize(gris, (64, 64)).astype(np.float32)
    f = np.fft.fft2(petit)
    amp, phase = np.log(np.abs(f) + 1e-6), np.angle(f)
    sal = np.abs(np.fft.ifft2(np.exp((amp - cv2.blur(amp, (3, 3))) + 1j * phase))) ** 2
    sal = cv2.GaussianBlur(sal.astype(np.float32), (9, 9), 2.5)
    yy, xx = np.mgrid[0:64, 0:64]
    sal *= np.exp(-(((xx - 31.5) / 40) ** 2 + ((yy - 31.5) / 40) ** 2))   # léger avantage au centre
    sal = np.where(sal >= np.percentile(sal, 80), sal, 0)                 # on garde les zones les plus fortes
    tot = sal.sum() or 1
    px, py = sal.sum(0).cumsum() / tot, sal.sum(1).cumsum() / tot
    x0, x1 = np.searchsorted(px, 0.12), np.searchsorted(px, 0.88)
    y0, y1 = np.searchsorted(py, 0.12), np.searchsorted(py, 0.88)
    return (x0 * w / 64, y0 * h / 64, (x1 + 1) * w / 64, (y1 + 1) * h / 64)


def _sujet(gris, visages):
    """Le sujet de la photo, à garder entier dans le cadre : visages (+ tête et épaules), sinon bustes,
    sinon la zone la plus saillante. {"sujet": boîte ou None, "sujet_poids": importance}."""
    h, w = gris.shape
    if visages:
        bx = [(a - (c - a) * 0.25, b - (d - b) * 0.3, c + (c - a) * 0.25, d + (d - b) * 0.5) for a, b, c, d in visages]
        poids = 1500
    else:
        mini = max(40, min(gris.shape) // 8)
        bx = [(x, y, x + bw, y + bh) for x, y, bw, bh in
              _corps().detectMultiScale(gris, scaleFactor=1.08, minNeighbors=5, minSize=(mini, mini))]
        poids = 900
        if not bx:
            bx, poids = [_saillance(gris)], 450
    x0, y0 = max(0, min(b[0] for b in bx)), max(0, min(b[1] for b in bx))
    x1, y1 = min(w, max(b[2] for b in bx)), min(h, max(b[3] for b in bx))
    if (x1 - x0) * (y1 - y0) > 0.8 * w * h:       # « sujet » = toute l'image : aucune contrainte utile
        return {"sujet": None, "sujet_poids": 0}
    return {"sujet": (x0, y0, x1, y1), "sujet_poids": poids}


def _fenetre(src_w, src_h, W, H, centrage, zoom):
    """Fenêtre (x0, y0, largeur, hauteur) de l'image source affichée, et l'échelle source → cible."""
    echelle = max(W / src_w, H / src_h) * zoom
    cw, ch = W / echelle, H / echelle
    x0 = (src_w - cw) * centrage[0]
    y0 = (src_h - ch) * centrage[1]
    return echelle, x0, y0, cw, ch


def recadrer(img, choix, W, H):
    """Applique le cadrage choisi (zoom compris) et renvoie l'image W x H."""
    x0, y0, cw, ch = choix["fenetre"]
    return img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.LANCZOS)


def _vers_cible(boites, echelle, x0, y0):
    # boîtes de l'image source → coordonnées de l'image finale (avec une marge de sécurité)
    return [((a - x0) * echelle - _MARGE, (b - y0) * echelle - _MARGE,
             (c - x0) * echelle + _MARGE, (d - y0) * echelle + _MARGE) for a, b, c, d in boites]


def _recouvrement(zone, boites):
    zx0, zy0, zx1, zy1 = zone
    aire = 0.0
    for a, b, c, d in boites:
        w, h = min(zx1, c) - max(zx0, a), min(zy1, d) - max(zy0, b)
        if w > 0 and h > 0:
            aire += w * h
    return aire / max(1.0, (zx1 - zx0) * (zy1 - zy0))


def _agitation_et_clarte(img_cible, zone):
    import cv2
    x0, y0, x1, y1 = [int(max(0, v)) for v in zone]
    morceau = np.array(img_cible.crop((x0, y0, x1, y1)).convert("L"))
    if morceau.size == 0:
        return 1.0, 1.0
    bords = cv2.Canny(morceau, 80, 160)
    return float((bords > 0).mean()), float(morceau.mean() / 255.0)


ELEMENTS_FIXES = {          # petits éléments toujours présents (pseudo, « GLISSE », numéro de slide)
    "pseudo": (72, 50, 420, 112),
    "pied": (600, 1215, 1008, 1290),
}

CENTRAGES = tuple((x, y) for x in (0.5, 0.0, 0.2, 0.8, 1.0) for y in (0.5, 0.0, 0.15, 0.85, 1.0))
ZOOMS = (1.0, 1.12, 1.25, 1.4, 1.6, 1.8, 2.0)


def zone_y(nom, H, hauteur_bloc, bord_haut=150, bord_bas=150):
    if nom == "bas":
        return H - bord_bas - hauteur_bloc, H - bord_bas
    if nom == "haut":
        return bord_haut, bord_haut + hauteur_bloc
    y0 = (H - hauteur_bloc) / 2
    return y0, y0 + hauteur_bloc


def choisir(img, analyse, W, H, hauteur_bloc, zones=("bas", "haut", "milieu"), centrages=CENTRAGES,
            zooms=ZOOMS, marge_x=72, marge_droite=None, bord_haut=150, bord_bas=150,
            agrandissement_max=2.4, fixes=None, eviter=(), genant=TEXTE_GENANT, echelle_source=1.0):
    """Teste chaque cadrage × zoom × zone. Renvoie le meilleur :
    {"fenetre", "zone", "y0", "y1", "propre": bool, "cout", "texte_visible", "zoom", "centrage"}.
    « propre » = aucun texte étranger visible à l'écran, aucun visage sous notre texte.
    bord_haut / bord_bas : bandes réservées (interface Instagram, pseudo…), notre titre n'y va jamais.
    fixes : boîtes des petits éléments (pseudo…) ; dict, ou fonction(zone) → dict si leur place dépend du titre.
    agrandissement_max : au-delà, l'image source serait trop agrandie (floue) ; le zoom 1 reste toujours permis.
    eviter : choix déjà faits sur la même image ; on refuse les cadrages presque identiques, pour varier.
    """
    marge_droite = marge_x if marge_droite is None else marge_droite
    fixes = ELEMENTS_FIXES if fixes is None else fixes
    base = max(W / img.width, H / img.height) / echelle_source   # agrandissement réel de la source
    meilleur = None
    for zoom in zooms:
        if zoom > 1 and base * zoom > max(agrandissement_max, base) + 1e-6:
            continue
        for centrage in centrages:
            echelle, x0, y0, cw, ch = _fenetre(img.width, img.height, W, H, centrage, zoom)
            if any(_proches((x0, y0, cw, ch), e) for e in eviter):
                continue
            textes = _vers_cible(analyse["textes"], echelle, x0, y0)
            visages = _vers_cible(analyse["visages"], echelle, x0, y0)
            # texte incrusté bien visible (sous-titre, logo de média…) ; un petit texte dans le décor
            # (t-shirt, emballage) est toléré ailleurs à l'écran, mais jamais sous notre texte
            grands = _vers_cible([b for b in analyse.get("genants", analyse["textes"])
                                  if (b[3] - b[1]) * echelle >= genant * H],
                                 echelle, x0, y0)
            visible = _recouvrement((0, 0, W, H), grands)        # part de l'écran couverte de texte étranger
            netete = min(1.0, 1.5 / echelle)                     # < 1 dès que la source est agrandie > 1,5×
            # le sujet doit rester à l'image : part des visages détectés entièrement visibles dans le cadrage
            vus = [v for v in analyse["visages"]
                   if v[0] >= x0 and v[1] >= y0 and v[2] <= x0 + cw and v[3] <= y0 + ch]
            sujet = len(vus) / len(analyse["visages"]) if analyse["visages"] else 1.0
            boite, poids = analyse.get("sujet"), analyse.get("sujet_poids", 0)
            if boite:
                bw, bh = boite[2] - boite[0], boite[3] - boite[1]
                iw = min(boite[2], x0 + cw) - max(boite[0], x0)
                ih = min(boite[3], y0 + ch) - max(boite[1], y0)
                dedans = max(0, iw) * max(0, ih) / max(1, bw * bh)        # part du sujet visible
                cible_sujet = ((boite[0] - x0) * echelle, (boite[1] - y0) * echelle,
                               (boite[2] - x0) * echelle, (boite[3] - y0) * echelle)
                aire_sujet = max(1, (cible_sujet[2] - cible_sujet[0]) * (cible_sujet[3] - cible_sujet[1]))
            cible = None
            for nom in zones:
                zy0, zy1 = zone_y(nom, H, hauteur_bloc, bord_haut, bord_bas)
                zone = (marge_x, zy0, W - marge_droite, zy1)
                t = _recouvrement(zone, textes)
                v = _recouvrement(zone, visages)
                boites = fixes(nom) if callable(fixes) else fixes
                f = sum(_recouvrement(b, textes) for b in boites.values())
                sale = visible > 0 or t > 0 or v > 0 or f > 0   # un rendu « pas propre » perd toujours
                fixe = (1000 * sale + 2000 * t + 1500 * min(1.0, visible * 8) + 500 * v + 300 * f
                        + 40 * (1 - netete) + 30 * (zoom - 1) + 600 * (1 - sujet)
                        + {"bas": 0, "haut": 4, "milieu": 8}[nom])
                if boite:   # sujet coupé par le cadre, ou caché sous notre texte
                    cache = (_recouvrement(zone, [cible_sujet]) * (zone[2] - zone[0]) * (zone[3] - zone[1])
                             / aire_sujet)
                    fixe += poids * (1 - dedans) + 0.6 * poids * min(1.0, cache)
                if meilleur is not None and fixe >= meilleur["cout"]:
                    continue                                     # perdu d'avance : on évite le calcul d'image
                if cible is None:
                    cible = recadrer(img, {"fenetre": (x0, y0, cw, ch)}, W // 4, H // 4).resize((W, H))
                agite, clair = _agitation_et_clarte(cible, zone)
                cout = fixe + 60 * agite + 110 * clair
                if meilleur is None or cout < meilleur["cout"]:
                    meilleur = {"fenetre": (x0, y0, cw, ch), "zone": nom, "y0": zy0, "y1": zy1,
                                "propre": not sale, "texte_visible": visible,
                                "cout": cout, "zoom": zoom, "centrage": centrage,
                                "sujet_visible": dedans if boite else 1.0, "visages_visibles": sujet}
    return meilleur


def _proches(fen, autre, seuil=0.55):
    """Vrai si deux cadrages montrent presque la même chose (pour ne pas répéter une image à l'identique)."""
    a = fen
    b = autre["fenetre"]
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return False
    return (w * h) / min(a[2] * a[3], b[2] * b[3]) > seuil


def controle(analyse, src_w, src_h, fenetre, W, H, zone):
    """Pour un cadrage donné (ex : fin d'un zoom lent) : (texte étranger visible, texte sous la zone, visage sous la zone)."""
    x0, y0, cw, ch = fenetre
    echelle = W / cw
    grands = [b for b in analyse["textes"] if (b[3] - b[1]) * echelle >= TEXTE_GENANT * H]
    textes = _vers_cible(analyse["textes"], echelle, x0, y0)
    visible = _recouvrement((0, 0, W, H), _vers_cible(grands, echelle, x0, y0))
    visages = _vers_cible(analyse["visages"], echelle, x0, y0)
    return visible, _recouvrement(zone, textes), _recouvrement(zone, visages)


def _iou(a, b):
    w, h = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def _persistants(images):
    """Textes retrouvés au même endroit sur une image voisine : un vrai texte incrusté (sous-titre, logo).
    Une détection isolée est souvent une erreur de lecture : elle reste interdite sous notre texte,
    mais ne rend pas tout le cadre « sale »."""
    out = []
    for i, (_, _, a) in enumerate(images):
        voisins = [b for j in (i - 1, i + 1) if 0 <= j < len(images) for b in images[j][2]["textes"]]
        out.append([b for b in a["textes"] if any(_iou(b, c) > 0.3 for c in voisins)])
    return out


def _union(images, genants):
    sujets = [a["sujet"] for _, _, a in images if a.get("sujet")]
    # sujet « typique » du passage : boîte médiane (l'union des boîtes grossirait à chaque mouvement)
    sujet = tuple(float(np.median([b[k] for b in sujets])) for k in range(4)) if sujets else None
    return {"textes": [b for _, _, a in images for b in a["textes"]],
            "genants": [b for g in genants for b in g],
            "visages": [b for _, _, a in images for b in a["visages"]],
            "sujet": sujet, "sujet_poids": max([a.get("sujet_poids", 0) for _, _, a in images] or [0])}


def choisir_video(images, W, H, hauteur_bloc, duree_voulue, **options):
    """images : [(t, image, analyse)] prises à intervalle régulier sur la vidéo.
    Cherche le passage de `duree_voulue` secondes (toute la vidéo si elle est plus courte) et le cadrage
    pour lesquels notre texte ne croise jamais de texte incrusté ni de visage, du début à la fin du passage.
    Renvoie le choix de `choisir` + {"debut", "fin"} en secondes.
    """
    images = sorted(images, key=lambda e: e[0])
    pas = images[1][0] - images[0][0] if len(images) > 1 else 1.0
    fin_video = images[-1][0] + pas / 2
    duree = min(duree_voulue, fin_video)
    persist = _persistants(images) if len(images) > 2 else [a["textes"] for _, _, a in images]
    meilleur = None
    debut = 0.0
    while debut + duree <= fin_video + 1e-6:
        idx = [i for i, e in enumerate(images) if debut - pas / 2 <= e[0] <= debut + duree + pas / 2]
        dedans = [images[i] for i in idx]
        ref = dedans[len(dedans) // 2][1]
        c = choisir(ref, _union(dedans, [persist[i] for i in idx]), W, H, hauteur_bloc, **options)
        c["cout"] += 0.2 * debut              # à égalité, on garde le passage le plus tôt
        c["debut"], c["fin"] = debut, debut + duree
        if meilleur is None or (c["propre"], -c["cout"]) > (meilleur["propre"], -meilleur["cout"]):
            meilleur = c
        if fin_video - duree < 1e-6:
            break
        debut += max(1.0, pas)
    return meilleur
