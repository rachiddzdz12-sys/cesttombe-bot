"""Trouve et télécharge la photo qui illustre l'info, avec plusieurs solutions de secours."""
import io

from bs4 import BeautifulSoup
from PIL import Image

from bot.sources import http_get

TAILLE_MIN = (500, 300)


def _telecharger(url):
    r = http_get(url)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content))
    img.load()
    if img.width < TAILLE_MIN[0] or img.height < TAILLE_MIN[1]:
        raise ValueError(f"image trop petite ({img.width}x{img.height})")
    return img.convert("RGB")


def _images_de_la_page(lien):
    p = BeautifulSoup(http_get(lien).text, "html.parser")
    urls = []
    for prop in ("og:image", "twitter:image"):
        m = p.find("meta", property=prop) or p.find("meta", attrs={"name": prop})
        if m and m.get("content"):
            urls.append(m["content"])
    corps = p.find("article") or p
    for img in corps.find_all("img"):
        src = img.get("data-src") or img.get("src")
        if src and src.startswith("http"):
            urls.append(src)
    return urls


def trouver_photo(cand, diag):
    """Renvoie (image PIL ou None, crédit). Ne lève jamais d'exception."""
    essais = list(cand.get("images", []))
    for etape in ("flux", "page"):
        if etape == "page":
            if not cand.get("lien") or cand["categorie"] != "GAMING":
                break
            try:
                essais = _images_de_la_page(cand["lien"])
            except Exception as ex:
                diag.append(f"  photo · page de l'article illisible : {ex}")
                break
        for url in essais[:6]:
            try:
                img = _telecharger(url)
                diag.append(f"  photo · trouvée ({etape}) {img.width}x{img.height}")
                return img, cand.get("credit", "")
            except Exception as ex:
                diag.append(f"  photo · échec ({etape}) : {str(ex)[:120]}")
    diag.append("  photo · aucune : couverture sans photo")
    return None, ""


def _empreinte(img):
    """Petite empreinte (8x8 en niveaux de gris) pour repérer deux fois la même image."""
    g = img.convert("L").resize((9, 8), Image.BILINEAR)
    px = list(g.getdata())
    return tuple(px[r * 9 + c] > px[r * 9 + c + 1] for r in range(8) for c in range(8))


def trouver_images(cand, diag, n=4):
    """Renvoie ([images PIL], crédit) : la photo principale d'abord, puis d'autres images de l'info
    (autres photos du post, images de l'article) pour poser le texte des slides suivantes.
    Ne lève jamais d'exception."""
    urls = list(cand.get("images", []))
    if cand.get("lien") and cand["categorie"] == "GAMING":
        try:
            urls += _images_de_la_page(cand["lien"])
        except Exception as ex:
            diag.append(f"  photo · page de l'article illisible : {str(ex)[:100]}")
    vues, empreintes, trouvees = set(), [], []
    for url in urls:
        if len(trouvees) >= n or len(vues) >= 10:
            break
        if url in vues:
            continue
        vues.add(url)
        try:
            img = _telecharger(url)
        except Exception as ex:
            diag.append(f"  photo · échec : {str(ex)[:100]}")
            continue
        e = _empreinte(img)
        if any(sum(a != b for a, b in zip(e, f)) < 10 for f in empreintes):
            continue      # même image (autre taille ou autre format)
        empreintes.append(e)
        trouvees.append(img)
    diag.append(f"  photo · {len(trouvees)} image(s) : " + ", ".join(f"{i.width}x{i.height}" for i in trouvees)
                if trouvees else "  photo · aucune image")
    return trouvees, (cand.get("credit", "") if trouvees else "")


def completer(photos, extras, n_max=6):
    """Ajoute les photos trouvées ailleurs (visuels.py) sans doublon. Renvoie (photos, crédits à afficher)."""
    empreintes = [_empreinte(p) for p in photos]
    credits = []
    for img, credit in extras:
        if len(photos) >= n_max:
            break
        e = _empreinte(img)
        if any(sum(a != b for a, b in zip(e, f)) < 10 for f in empreintes):
            continue
        photos.append(img)
        empreintes.append(e)
        if credit and credit not in credits:
            credits.append(credit)
    return photos, credits


def en_jpeg(img, cote_max=1600):
    img = img.copy()
    img.thumbnail((cote_max, cote_max))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()
