"""Lecture des sources : ActuGaming (flux RSS) et comptes Instagram rap (API officielle)."""
import calendar
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup

import config


def http_get(url, **kw):
    return requests.get(url, headers={"User-Agent": config.USER_AGENT,
                                      "Accept-Language": "fr-FR,fr;q=0.9"},
                        timeout=25, **kw)


def texte_propre(html_txt):
    if not html_txt:
        return ""
    return re.sub(r"\s+", " ", BeautifulSoup(html_txt, "html.parser").get_text(" ")).strip()


def _credit(entree):
    c = entree.get("media_credit")
    if isinstance(c, list) and c:
        c = c[0]
    if isinstance(c, dict):
        c = c.get("content", "")
    return (c or "").strip()


def _images(entree):
    urls = []
    for m in entree.get("media_content", []) or []:
        u = m.get("url", "")
        typ = (m.get("type") or m.get("medium") or "image").lower()
        if u and "video" not in typ and not u.lower().split("?")[0].endswith((".mp4", ".webm", ".m3u8")):
            urls.append(u)
    for c in entree.get("content", []) or []:
        for img in BeautifulSoup(c.get("value", ""), "html.parser").find_all("img"):
            src = img.get("data-src") or img.get("src")
            if src and src.startswith("http"):
                urls.append(src)
    vus, propres = set(), []
    for u in urls:
        if u not in vus:
            vus.add(u)
            propres.append(u)
    return propres


def _titre_exclu(titre):
    t = titre.lower()
    return any(m in t for m in config.GAMING["titres_exclus"])


def entrees_depuis_flux(contenu, filtrer_rubrique):
    """Transforme un flux RSS (texte) en candidats. Testable sans réseau."""
    flux = feedparser.parse(contenu)
    res = []
    for e in flux.entries:
        cats = [t.get("term", "").lower().strip() for t in e.get("tags", []) or []]
        if any(c in config.GAMING["categories_exclues"] for c in cats):
            continue
        if filtrer_rubrique and not any(c in config.GAMING["categories_ok"] for c in cats):
            continue
        titre = texte_propre(e.get("title", ""))
        if not titre or _titre_exclu(titre):
            continue
        date = None
        if e.get("published_parsed"):
            date = datetime.fromtimestamp(calendar.timegm(e.published_parsed), tz=timezone.utc)
        contenu_html = (e.get("content") or [{}])[0].get("value", "") if e.get("content") else ""
        res.append({
            "id": "ag:" + (e.get("id") or e.get("link") or titre),
            "categorie": "GAMING",
            "source": config.GAMING["nom"],
            "source_legende": config.GAMING["nom_legende"],
            "titre": titre,
            "resume": texte_propre(e.get("summary", ""))[:600],
            "texte": texte_propre(contenu_html or e.get("summary", ""))[:6000],
            "lien": e.get("link", ""),
            "date": date.isoformat() if date else None,
            "images": _images(e),
            "credit": _credit(e),
        })
    return res


def _page_secours(diag):
    """Dernier recours : lit la page 1 de la rubrique et chaque article (titre, texte, image)."""
    r = http_get(config.GAMING["page_secours"])
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    liens = []
    for a in soup.select("article a[href], h2 a[href], h3 a[href]"):
        href = a["href"]
        if "actugaming.net" in href and href not in liens and href.rstrip("/").count("/") >= 3:
            liens.append(href)
    res = []
    for lien in liens[:10]:
        try:
            p = BeautifulSoup(http_get(lien).text, "html.parser")
            meta = lambda prop: (p.find("meta", property=prop) or {}).get("content", "")
            titre = meta("og:title") or (p.title.string if p.title else "")
            if not titre or _titre_exclu(titre):
                continue
            corps = p.find("article") or p
            res.append({
                "id": "ag:" + lien, "categorie": "GAMING", "source": config.GAMING["nom"],
                "source_legende": config.GAMING["nom_legende"],
                "titre": texte_propre(titre), "resume": meta("og:description"),
                "texte": texte_propre(str(corps))[:6000], "lien": lien,
                "date": meta("article:published_time") or None,
                "images": [meta("og:image")] if meta("og:image") else [], "credit": "",
            })
        except Exception as ex:  # un article illisible ne bloque pas les autres
            diag.append(f"  page article illisible ({lien}) : {ex}")
    return res


def lire_gaming(diag):
    for i, url in enumerate(config.GAMING["flux"]):
        try:
            r = http_get(url)
            diag.append(f"Gaming · {url} → HTTP {r.status_code}")
            if r.status_code != 200:
                continue
            items = entrees_depuis_flux(r.content, filtrer_rubrique=(i > 0))
            if items:
                diag.append(f"  {len(items)} infos retenues après filtre")
                return items
        except Exception as ex:
            diag.append(f"Gaming · {url} → erreur : {ex}")
    try:
        items = _page_secours(diag)
        diag.append(f"Gaming · page de secours → {len(items)} infos")
        return items
    except Exception as ex:
        diag.append(f"Gaming · page de secours → erreur : {ex}")
        return []


def lire_rap(diag):
    token, ig = os.environ.get("IG_ACCESS_TOKEN"), os.environ.get("IG_USER_ID")
    if not token or not ig:
        diag.append("Rap · IG_ACCESS_TOKEN ou IG_USER_ID manquant : source rap ignorée")
        return []
    res = []
    for compte in config.COMPTES_RAP:
        champs = (f"business_discovery.username({compte})"
                  "{username,media.limit(12){id,caption,media_type,media_url,thumbnail_url,timestamp,permalink}}")
        try:
            r = requests.get(f"{config.GRAPH}/{ig}", params={"fields": champs, "access_token": token}, timeout=30)
            j = r.json()
            if "error" in j:
                diag.append(f"Rap · @{compte} → refus de Meta : {j['error'].get('message')}")
                continue
            medias = j.get("business_discovery", {}).get("media", {}).get("data", [])
            diag.append(f"Rap · @{compte} → {len(medias)} posts lus")
            for m in medias:
                legende = (m.get("caption") or "").strip()
                img = m.get("media_url") if m.get("media_type") in ("IMAGE", "CAROUSEL_ALBUM") else m.get("thumbnail_url")
                res.append({
                    "id": "ig:" + m["id"], "categorie": "RAP FR", "source": "@" + compte.upper(),
                    "source_legende": "@" + compte,
                    "titre": legende.split("\n")[0][:140] or "(info dans l'image)",
                    "resume": legende[:600], "texte": legende[:4000], "lien": m.get("permalink", ""),
                    "date": m.get("timestamp"), "images": [img] if img else [], "credit": "@" + compte,
                })
        except Exception as ex:
            diag.append(f"Rap · @{compte} → erreur : {ex}")
    return res


def _premier(obj, cles):
    """Cherche récursivement la première valeur d'une des clés (les scrapers X n'ont pas tous le même format)."""
    if isinstance(obj, dict):
        for k in cles:
            if obj.get(k):
                return obj[k]
        for v in obj.values():
            r = _premier(v, cles)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _premier(v, cles)
            if r:
                return r
    return None


def lire_x(diag):
    """Comptes X (Twitter) via un scraper Apify payé au résultat, couvert par le crédit gratuit mensuel."""
    token = os.environ.get("APIFY_TOKEN")
    if not config.COMPTES_X:
        return []
    if not token:
        diag.append("X · APIFY_TOKEN manquant : comptes X ignorés")
        return []
    depuis = (datetime.now(timezone.utc) - timedelta(hours=config.AGE_MAX_HEURES["RAP FR"]))
    res = []
    for compte in config.COMPTES_X:
        entree = {"searchTerms": [f"from:{compte} since:{depuis:%Y-%m-%d_%H:%M:%S}_UTC -filter:replies"],
                  "from": compte, "maxItems": config.X_MAX_TWEETS, "queryType": "Latest"}
        try:
            r = requests.post(f"https://api.apify.com/v2/acts/{config.APIFY_ACTEUR}/run-sync-get-dataset-items",
                              params={"token": token, "timeout": 150, "maxItems": config.X_MAX_TWEETS},
                              json=entree, timeout=200)
            if r.status_code >= 400:
                diag.append(f"X · @{compte} → refus Apify HTTP {r.status_code} : {r.text[:150]}")
                continue
            items = [t for t in r.json() if isinstance(t, dict)][: config.X_MAX_TWEETS]
            gardes = 0
            for t in items:
                texte = (t.get("text") or t.get("full_text") or t.get("fullText") or "").strip()
                tid = str(t.get("id") or t.get("id_str") or t.get("tweetId") or "")
                if not texte or not tid or texte.startswith("RT @") or t.get("isReply") or t.get("isRetweet"):
                    continue
                img = _premier(t, ["media_url_https", "mediaUrl", "media_url", "thumbnail_url"])
                date = t.get("createdAt") or t.get("created_at")
                try:
                    date = parsedate_to_datetime(date).isoformat() if date and "," in date else date
                except (TypeError, ValueError):
                    pass
                res.append({
                    "id": "x:" + tid, "categorie": "RAP FR", "source": "@" + compte.upper(),
                    "source_legende": "@" + compte + " (X)",
                    "titre": texte.split("\n")[0][:140], "resume": texte[:600], "texte": texte[:4000],
                    "lien": t.get("url") or t.get("twitterUrl") or f"https://x.com/{compte}/status/{tid}",
                    "date": date, "images": [img] if isinstance(img, str) else [], "credit": "@" + compte,
                })
                gardes += 1
            diag.append(f"X · @{compte} → {len(items)} tweets lus, {gardes} gardés")
        except Exception as ex:
            diag.append(f"X · @{compte} → erreur : {str(ex)[:150]}")
    return res


def age_heures(cand, maintenant):
    if not cand.get("date"):
        return 0
    try:
        d = datetime.fromisoformat(cand["date"].replace("Z", "+00:00").replace("+0000", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return (maintenant - d).total_seconds() / 3600
    except ValueError:
        return 0
