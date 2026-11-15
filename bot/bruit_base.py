"""DA « LE BRUIT » : éléments communs au carrousel et au Reel (couleurs, polices Inter, logo B, arcs violets,
texte, photos). Noir profond, photos en couleur un peu éteintes, accent violet, petits titres de rubrique."""
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

RACINE = Path(__file__).resolve().parent.parent
VIOLET = (128, 40, 238)          # violet de la DA (traits, barres, arcs)
VIOLET_TXT = (146, 66, 255)      # même violet, un peu plus lumineux pour le texte sur fond sombre
BLANC = (255, 255, 255)
GRIS = (196, 196, 204)
FOND = (7, 7, 10)


@lru_cache(maxsize=64)
def police(poids, taille):
    return ImageFont.truetype(str(RACINE / "fonts" / f"Inter-{poids}.ttf"), taille)


def largeur(txt, f, track=0):
    return f.getlength(txt) + track * max(0, len(txt) - 1)


def ecrire(d, x, y, txt, f, fill, track=0, anchor="ls"):
    """Texte avec interlettrage (le crénage est gardé : chaque lettre est placée selon la longueur du préfixe)."""
    if not track:
        d.text((x, y), txt, font=f, fill=fill, anchor=anchor)
        return x + f.getlength(txt)
    for i, ch in enumerate(txt):
        d.text((x + f.getlength(txt[:i]) + track * i, y), ch, font=f, fill=fill, anchor=anchor)
    return x + largeur(txt, f, track)


def couper(txt, f, lmax, track=0):
    lignes, cur = [], ""
    for mot in (txt or "").split():
        essai = (cur + " " + mot).strip()
        if largeur(essai, f, track) <= lmax or not cur:
            cur = essai
        else:
            lignes.append(cur)
            cur = mot
    if cur:
        lignes.append(cur)
    return lignes


def ajuster(txt, poids, taille, lmax, n_max, mini=40, track_ratio=-0.02):
    """Police la plus grande (jusqu'à « mini ») qui fait tenir le texte en n_max lignes."""
    for t in range(taille, mini - 1, -4):
        f = police(poids, t)
        lignes = couper(txt, f, lmax, track=int(t * track_ratio))
        if len(lignes) <= n_max:
            return f, lignes
    f = police(poids, mini)
    return f, couper(txt, f, lmax, track=int(mini * track_ratio))[:n_max]


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


# ------------------------------------------------------------------ logo B (masque tiré de la planche DA)
@lru_cache(maxsize=8)
def _masque():
    return Image.open(RACINE / "assets" / "le-bruit-logo.png").convert("L")


@lru_cache(maxsize=32)
def _logo(hauteur, eclat_q):
    m0 = _masque()
    w = round(m0.width * hauteur / m0.height)
    m = m0.resize((w, hauteur), Image.LANCZOS)
    yy, xx = np.mgrid[0:hauteur, 0:w]
    t = xx / w * 0.65 + yy / hauteur * 0.35
    metal = 238 - 95 * t + 14 * np.sin(t * 8)
    if eclat_q is not None:
        metal += 70 * np.exp(-((t - eclat_q / 100) ** 2) / 0.004)
    metal = metal.clip(70, 255)
    img = Image.fromarray(np.dstack([metal * 0.99, metal * 0.99, metal]).clip(0, 255).astype(np.uint8)).convert("RGBA")
    img.putalpha(m)
    return img


def logo(hauteur, eclat=None):
    """Logo B argenté (RGBA). eclat = position 0..1 d'un reflet qui le balaie."""
    return _logo(int(hauteur), None if eclat is None else int(eclat * 100)).copy()


# ------------------------------------------------------------------ arcs violets lumineux
@lru_cache(maxsize=16)
def arcs(w, h, coins=("bas-droite",), force=1.0):
    calque = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    for coin in coins:
        if coin == "bas-droite":
            d.ellipse((w - 300, h - int(h * 0.38), w + 760, h + int(h * 0.3)), outline=VIOLET + (int(255 * force),), width=6)
        elif coin == "haut-droite":
            d.ellipse((w - 300, -720, w + 720, 300), outline=VIOLET + (int(230 * force),), width=6)
        else:
            d.ellipse((-760, -640, 260, 330), outline=VIOLET + (int(210 * force),), width=5)
    halo = calque.filter(ImageFilter.GaussianBlur(24))
    return Image.alpha_composite(Image.alpha_composite(halo, halo), calque.filter(ImageFilter.GaussianBlur(1.3)))


def ombre(img, dessiner, rayon=14, force=170):
    """Ombre douce sous un bloc de texte : le texte est dessiné en noir sur un calque flouté."""
    c = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dessiner(ImageDraw.Draw(c), (0, 0, 0, force))
    img.alpha_composite(c.filter(ImageFilter.GaussianBlur(rayon)))


# ------------------------------------------------------------------ photos
def look(img):
    """Couleurs gardées mais un peu éteintes, léger contraste : le rendu des photos de la DA."""
    return ImageEnhance.Contrast(ImageEnhance.Color(img.convert("RGB")).enhance(0.85)).enhance(1.06)


def partie_propre(media):
    """Fraction de la photo (depuis le haut) à garder pour ne pas montrer le texte incrusté en bas
    (légende, « swipe pour découvrir »…). 1.0 = photo entière."""
    img, an = media["img"], media.get("analyse") or {}
    h = img.height
    bas = [b for b in an.get("textes", []) if b[1] > 0.3 * h and (b[3] - b[1]) > 0.015 * h]
    if not bas:
        return 1.0
    return max(0.35, min(b[1] for b in bas) / h - 0.02)


def centre_sujet(media):
    """Centre du sujet (visages principaux, buste, zone saillante), en fraction de l'image."""
    img, an = media["img"], media.get("analyse") or {}
    boite = an.get("sujet")
    if not boite and an.get("principaux"):
        v = an["principaux"]
        boite = (min(b[0] for b in v), min(b[1] for b in v), max(b[2] for b in v), max(b[3] for b in v))
    if not boite:
        return 0.5, 0.4
    return (boite[0] + boite[2]) / 2 / img.width, (boite[1] + boite[3]) / 2 / img.height


def a_du_texte(media):
    img, an = media["img"], media.get("analyse") or {}
    surf = sum((b[2] - b[0]) * (b[3] - b[1]) for b in an.get("textes", []))
    return surf / (img.width * img.height) > 0.015


def mode_photo(media, w, h):
    """« plein » (photo plein cadre) ou « haut » (photo en haut, fondue dans le noir, texte sur le noir)."""
    img = media["img"]
    if partie_propre(media) < 0.92:
        return "haut"
    if img.width / img.height > w / h * 1.35:       # trop large pour le cadre : on ne garderait qu'une bande
        return "haut"
    return "plein"


def fond_plein(media, w, h, assombrir=0.78, gauche=True, zoom=1.0, decale=(0.0, 0.0)):
    """Photo plein cadre centrée sur le sujet, assombrie à gauche et en bas pour le texte."""
    img = look(media["img"])
    cx, cy = centre_sujet(media)
    s = max(w / img.width, h / img.height) * zoom
    p = img.resize((round(img.width * s) + 1, round(img.height * s) + 1), Image.LANCZOS)
    x0 = int(min(max(0, (cx + decale[0]) * p.width - w / 2), p.width - w))
    y0 = int(min(max(0, (cy + decale[1]) * p.height - h * 0.42), p.height - h))
    a = np.asarray(p.crop((x0, y0, x0 + w, y0 + h))).astype(np.float32) * assombrir
    a *= _ombre_plein(w, h, gauche)[..., None]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert("RGBA")


@lru_cache(maxsize=8)
def _ombre_plein(w, h, gauche):
    yy, xx = np.mgrid[0:h, 0:w]
    bas = ((yy - h * 0.38) / (h * 0.62)).clip(0, 1) ** 1.3 * 0.9
    haut = (1 - yy / 260).clip(0, 1) * 0.55
    lat = ((1 - xx / (w * 0.75)).clip(0, 1) ** 1.6 * 0.5) if gauche else 0
    vign = (1 - 0.7 * (((xx - w / 2) / w) ** 2 + ((yy - h / 2) / h) ** 2)).clip(0.5, 1)
    return ((1 - np.maximum(np.maximum(bas, haut), lat)) * vign).astype(np.float32)


def fond_haut(media, w, h, hauteur, y=110, assombrir=0.86, zoom=1.0):
    """Photo dans le haut de l'écran (sans son texte incrusté), fondue dans le noir vers le bas."""
    img = look(media["img"])
    garder = partie_propre(media)
    img = img.crop((0, 0, img.width, int(img.height * garder)))
    cx, _ = centre_sujet(media)
    s = max(w / img.width, hauteur / img.height) * zoom
    p = img.resize((round(img.width * s) + 1, round(img.height * s) + 1), Image.LANCZOS)
    x0 = int(min(max(0, cx * p.width - w / 2), p.width - w))
    y0 = int(min(max(0, (p.height - hauteur) * 0.3), p.height - hauteur))
    zone = np.asarray(p.crop((x0, y0, x0 + w, y0 + hauteur))).astype(np.float32) * assombrir
    fond = np.empty((h, w, 3), np.float32)
    fond[:] = FOND
    m = _masque_haut(w, hauteur)[..., None]
    fond[y:y + hauteur] = zone * m + fond[y:y + hauteur] * (1 - m)
    return Image.fromarray(fond.clip(0, 255).astype(np.uint8)).convert("RGBA")


@lru_cache(maxsize=8)
def _masque_haut(w, hauteur):
    yy = np.arange(hauteur)[:, None]
    fondu = 1 - ((yy - hauteur * 0.5) / (hauteur * 0.5)).clip(0, 1) ** 1.25
    haut = (yy / 160).clip(0, 1) ** 0.8
    xx = np.arange(w)[None, :]
    cotes = 1 - 0.25 * ((xx - w / 2) / (w / 2)) ** 2
    return (fondu * haut * cotes).astype(np.float32)


def fond_noir(w, h, halo=True):
    img = Image.new("RGBA", (w, h), FOND + (255,))
    if halo:
        f = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(f).ellipse((-200, int(h * 0.15), w + 200, int(h * 0.9)), fill=(40, 18, 80, 80))
        img.alpha_composite(f.filter(ImageFilter.GaussianBlur(170)))
    return img


def grain(img, force=4, graine=1):
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    a += np.random.default_rng(graine).normal(0, force, a.shape[:2] + (1,)).astype(np.float32)
    return Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert("RGBA")


def decouper_chiffre(ch):
    """« 1 » → (« N° », « 1 ») pour un classement ; « 366 Go » → (« 366 », « Go ») ; « ×5 » → (« ×5 », «  »)."""
    import re
    ch = (ch or "").strip()
    if re.fullmatch(r"(n°|#|numéro)?\s*1", ch, re.I):
        return "N°", "1"
    m = re.match(r"^([×x+\-]?[\d\s,.]+)\s*(.*)$", ch)
    return (m.group(1).strip(), m.group(2).strip()) if m else (ch, "")
