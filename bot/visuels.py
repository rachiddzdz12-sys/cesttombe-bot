"""Photos supplémentaires du sujet, pour varier les images d'un post (slides et Reel).

Sources gratuites, sans clé :
- jeu      → captures d'écran officielles de la page Steam du jeu
- artiste  → photo de l'artiste et pochettes (Deezer), puis photos libres de Wikimedia Commons
- personne / autre → photos libres de Wikimedia Commons (crédit obligatoire, ajouté à la légende)
Ne lève jamais d'exception : au pire, aucune image en plus.
"""
import io
import re
import unicodedata

import requests
from PIL import Image

UA = "CestTombeBot/1.0 (+https://github.com/rachiddzdz12-sys/cesttombe-bot)"
LICENCES_OK = ("cc by", "cc-by", "cc0", "public domain", "domaine public", "pd")


def _get(url, **kw):
    return requests.get(url, headers={"User-Agent": UA}, timeout=25, **kw)


def _norme(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def _mots(t):
    return [m for m in _norme(t).split() if len(m) >= 3 or m.isdigit()]


def _correspond(nom, candidat, part=1.0):
    """Vrai si les mots du nom cherché se retrouvent dans le candidat (au moins `part` d'entre eux)."""
    mots = _mots(nom)
    if not mots:
        return False
    cible = " " + _norme(candidat) + " "
    return sum(f" {m} " in cible for m in mots) >= max(1, round(len(mots) * part))


def _image(url):
    r = _get(url)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content))
    img.load()
    if img.width < 600 or img.height < 400:
        raise ValueError(f"trop petite ({img.width}x{img.height})")
    return img.convert("RGB")


# ------------------------------------------------------------------ Steam (jeux)
def steam(nom, n=4):
    r = _get("https://store.steampowered.com/api/storesearch/", params={"term": nom, "l": "french", "cc": "FR"})
    items = r.json().get("items", [])
    jeu = next((i for i in items if _correspond(nom, i.get("name", ""), 0.75)), None)
    if not jeu:
        return []
    d = _get("https://store.steampowered.com/api/appdetails", params={"appids": jeu["id"], "l": "french"}).json()
    data = (d.get(str(jeu["id"])) or {}).get("data") or {}
    return [(s["path_full"], "") for s in data.get("screenshots", [])[:n] if s.get("path_full")]


# ------------------------------------------------------------------ Deezer (artistes)
FANS_MIN = 5000      # en dessous, risque d'homonyme inconnu : pas de pochettes Deezer


def deezer(nom, n=3):
    r = _get("https://api.deezer.com/search/artist", params={"q": nom, "limit": 10})
    n += 2                                # des pochettes en double (éditions deluxe) seront écartées
    # homonymes (un DJ « Ninho » à côté du rappeur) : on garde le plus suivi, et seulement s'il a un vrai public
    memes = [a for a in r.json().get("data", []) if _correspond(nom, a.get("name", ""), 1.0)]
    artiste = max(memes, key=lambda a: a.get("nb_fan", 0), default=None)
    if not artiste or artiste.get("nb_fan", 0) < FANS_MIN:
        return []
    urls = [(artiste["picture_xl"], "")] if artiste.get("picture_xl") else []
    albums = _get(f"https://api.deezer.com/artist/{artiste['id']}/albums", params={"limit": 6}).json().get("data", [])
    urls += [(a["cover_xl"], "") for a in albums if a.get("cover_xl")][: n - len(urls)]
    return urls


# ------------------------------------------------------------------ Wikimedia Commons (photos libres)
def _sans_html(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t or "")).strip()


def commons(nom, n=4):
    r = _get("https://commons.wikimedia.org/w/api.php", params={
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 20,
        "gsrsearch": f'"{nom}" filetype:bitmap', "prop": "imageinfo", "iiprop": "url|size|extmetadata",
        "iiurlwidth": 1600})
    pages = sorted((r.json().get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    sortie = []
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        titre = p.get("title", "")
        licence = _sans_html((meta.get("LicenseShortName") or {}).get("value", ""))
        if not _correspond(nom, titre + " " + _sans_html((meta.get("ImageDescription") or {}).get("value", ""))):
            continue
        if info.get("width", 0) < 800 or not any(l in licence.lower() for l in LICENCES_OK):
            continue
        if re.search(r"logo|signature|map|carte|coat of arms|blason", titre, re.I):
            continue
        auteur = _sans_html((meta.get("Artist") or {}).get("value", ""))[:40] or "Wikimedia Commons"
        sortie.append((info.get("thumburl") or info.get("url"), f"{auteur} / Wikimedia Commons ({licence})"))
        if len(sortie) >= n:
            break
    return sortie


def commons_personne(nom, n=4):
    """Photos libres d'une personne : seulement si le nom complet (prénom + nom) est dans le nom du fichier,
    pour ne jamais prendre un homonyme (ex : « Leto » le rappeur ≠ Jared Leto)."""
    if len(_mots(nom)) < 2:
        return []
    return [(u, c) for u, c in commons(nom, n * 2) if _correspond(nom, u.rsplit("/", 1)[-1], 1.0)][:n]


# artistes : Deezer seulement (un nom de scène a trop d'homonymes) ; « autre » : pas de recherche d'images
SOURCES = {"jeu": (steam,), "artiste": (deezer,), "personne": (commons_personne,), "autre": ()}


def chercher(sujets, diag, n=4):
    """sujets = [{"type": "jeu" | "artiste" | "personne" | "autre", "nom": "…"}] (donnés par l'IA).
    Renvoie [(image PIL, crédit)] — crédit non vide quand la licence l'exige."""
    from bot.images import _empreinte
    trouvees, empreintes = [], []
    for s in (sujets or [])[:2]:
        nom, typ = (s.get("nom") or "").strip(), (s.get("type") or "autre").strip().lower()
        if not nom:
            continue
        for fn in SOURCES.get(typ, ()):
            if len(trouvees) >= n:
                break
            try:
                urls = fn(nom, n - len(trouvees))
            except Exception as ex:
                diag.append(f"  visuels · {fn.__name__} « {nom} » : {str(ex)[:100]}")
                continue
            ok = 0
            for url, credit in urls:
                try:
                    img = _image(url)
                except Exception:
                    continue
                e = _empreinte(img)
                if any(sum(a != b for a, b in zip(e, f)) < 10 for f in empreintes):
                    continue                    # même image (ex : pochette de l'édition deluxe)
                empreintes.append(e)
                trouvees.append((img, credit))
                ok += 1
            diag.append(f"  visuels · {fn.__name__} « {nom} » → {ok} image(s)")
    return trouvees[:n]
