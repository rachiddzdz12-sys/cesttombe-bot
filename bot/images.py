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


def en_jpeg(img, cote_max=1600):
    img = img.copy()
    img.thumbnail((cote_max, cote_max))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()
