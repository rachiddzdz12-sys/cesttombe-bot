"""Contexte en plus pour expliquer une info au lieu de juste l'annoncer.

Avant la rédaction, on rassemble les détails qui manquent souvent à une source courte (« Ninho sort un
nouveau son 🔥 », sans le titre) :
  1. les autres sources qui parlent du même sujet (recoupement, gratuit) ;
  2. pour une sortie rap : la dernière sortie de l'artiste sur Deezer (titre exact, date, nombre de titres,
     featurings) — données officielles ;
  3. si Gemini peut chercher sur Google (quota disponible) : les faits précis trouvés en ligne.
Chaque bloc est étiqueté avec son origine ; la rédaction n'utilise que ce qui y est écrit.
"""
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

import config

UA = "CestTombeBot/1.0 (+https://github.com/rachiddzdz12-sys/cesttombe-bot)"
FANS_MIN = 50_000                       # artiste reconnu : pas d'homonyme obscur
JOURS_SORTIE = 21                       # une « nouvelle » sortie Deezer date de moins de 3 semaines
_RECHERCHE_HS = []                      # recherche Google indisponible pendant ce passage (quota)

VIDES = {"les", "des", "une", "un", "le", "la", "de", "du", "et", "en", "au", "aux", "pour", "par", "sur", "avec",
         "dans", "qui", "que", "est", "son", "sa", "ses", "il", "elle", "ils", "ce", "cette", "plus", "pas", "the",
         "breaking", "news", "officiel", "officielle", "nouveau", "nouvelle", "rap", "fr", "info", "infos", "video",
         "vidéo", "alerte", "exclu", "via", "après", "avant", "tout", "tous", "fait", "faire", "a", "à", "on"}
THEME = {"gta", "vi", "6", "grand", "theft", "auto", "rockstar", "games", "jeu", "jeux"}
MOTS_SORTIE = re.compile(r"\b(nouveau|nouvel|nouvelle|sort|sortie|sorti|dévoile|dévoilé|annonce|single|son|sons|"
                         r"morceau|titre|album|clip|projet|ep|mixtape|tape|feat|featuring|freestyle|tracklist|"
                         r"extrait|snippet|réédition|deluxe)\b", re.I)


def _get(url, **kw):
    return requests.get(url, headers={"User-Agent": UA}, timeout=20, **kw)


def _norme(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def mots_forts(c):
    """Noms propres, titres et chiffres de l'info (ce qui permet de reconnaître le même sujet ailleurs)."""
    txt = f"{c.get('titre', '')} {(c.get('resume') or '')[:300]}"
    mots = set()
    for m in re.findall(r"[A-ZÀ-Ý0-9][\wÀ-ÿ'’-]{1,}", txt):
        n = _norme(m)
        if n and n not in VIDES and n not in THEME and (len(n) >= 3 or n.isdigit()):
            mots.add(n)
    return mots


def recoupements(cand, cands, n=3):
    """Les autres sources du moment sur le même sujet (au moins 2 noms propres ou chiffres en commun)."""
    forts = mots_forts(cand)
    if len(forts) < 2:
        return []
    proches = []
    for c in cands or []:
        if c.get("id") == cand.get("id") or not c.get("texte"):
            continue
        commun = forts & mots_forts(c)
        if len(commun) >= 2:
            proches.append((len(commun), c))
    proches.sort(key=lambda x: -x[0])
    vus, lignes = set(), []
    for _, c in proches:
        cle = _norme(c["titre"])[:60]
        if cle in vus:
            continue
        vus.add(cle)
        texte = re.sub(r"\s+", " ", c["texte"])[:700]
        lignes.append(f"- {c['source']} : {c['titre']}. {texte}")
        if len(lignes) >= n:
            break
    return lignes


def _artistes(cand):
    """Noms d'artistes possibles : groupes de mots en majuscule du titre et du début du texte."""
    txt = f"{cand.get('titre', '')} . {(cand.get('resume') or '')[:200]}"
    txt = re.sub(r"[🚨🔥📈🎤💿🎶❗️⚡️]+", " . ", txt)
    noms = re.findall(r"\b([A-ZÀ-Ý][\w'’.-]*(?:\s+[A-ZÀ-Ý][\w'’.-]*){0,2})", txt)
    vus, res = set(), []
    for nom in noms:
        n = _norme(nom)
        if not n or n in VIDES or len(n) < 2 or n in vus:
            continue
        vus.add(n)
        res.append(nom.strip())
    return res[:4]


def _artiste_deezer(nom):
    r = _get("https://api.deezer.com/search/artist", params={"q": nom, "limit": 8}).json().get("data", [])
    cible = _norme(nom)
    memes = [a for a in r if _norme(a.get("name", "")) == cible]
    a = max(memes, key=lambda x: x.get("nb_fan", 0), default=None)
    return a if a and a.get("nb_fan", 0) >= FANS_MIN else None


def sorties_deezer(cand, diag=None):
    """Pour une sortie rap : la dernière sortie officielle de l'artiste (titre, type, date, titres, featurings)."""
    if cand.get("categorie") != "RAP FR":
        return []
    if not MOTS_SORTIE.search(f"{cand.get('titre', '')} {(cand.get('resume') or '')[:300]}"):
        return []
    lignes, limite = [], (datetime.now(timezone.utc) - timedelta(days=JOURS_SORTIE)).date().isoformat()
    for nom in _artistes(cand):
        try:
            a = _artiste_deezer(nom)
            if not a:
                continue
            albums = _get(f"https://api.deezer.com/artist/{a['id']}/albums", params={"limit": 10}).json().get("data", [])
            recents = sorted([x for x in albums if (x.get("release_date") or "") >= limite],
                             key=lambda x: x.get("release_date", ""), reverse=True)[:2]
            for alb in recents:
                d = _get(f"https://api.deezer.com/album/{alb['id']}").json()
                titres = [t.get("title", "") for t in (d.get("tracks") or {}).get("data", [])][:12]
                genre = {"single": "single", "album": "album", "ep": "EP"}.get(d.get("record_type", ""), d.get("record_type", ""))
                lignes.append(f"- Deezer (officiel) : {a['name']} — « {d.get('title', alb.get('title'))} », {genre}, "
                              f"sorti le {d.get('release_date', '?')}, {d.get('nb_tracks', len(titres))} titre(s)"
                              + (f" : {', '.join(titres)}" if titres and d.get('nb_tracks', 0) > 1 else ""))
            if lignes:
                break                     # l'artiste principal suffit
        except Exception as ex:
            if diag is not None:
                diag.append(f"  contexte · Deezer « {nom} » : {str(ex)[:80]}")
    return lignes


def recherche_google(cand, diag=None):
    """Faits précis trouvés sur Google par Gemini (titre exact, ce qui a été dit, où et quand). Facultatif :
    silencieux si la recherche n'est pas disponible (quota)."""
    cle = os.environ.get("GEMINI_API_KEY")
    if not cle or not getattr(config, "RECHERCHE_GOOGLE", True) or _RECHERCHE_HS:
        return []
    q = ("Tu prépares un post d'actualité. Info : « " + cand.get("titre", "") + " » (source : " + cand.get("source", "")
         + "). Texte de la source : " + re.sub(r"\s+", " ", cand.get("texte", ""))[:1200] + "\n\nCherche sur Google "
         "les faits précis qui manquent pour EXPLIQUER cette info : le titre exact (morceau, album, clip, jeu, "
         "émission), ce qui a été dit concrètement, la date, le lieu, les personnes, les chiffres. Réponds en 5 "
         "lignes maximum, uniquement des faits vérifiés dans tes résultats, sans phrase d'introduction. Si tu ne "
         "trouves rien de fiable sur CETTE info précise, réponds exactement : RIEN")
    for modele in getattr(config, "RECHERCHE_MODELES", ["gemini-flash-latest", "gemini-3.5-flash"]):
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent",
                              headers={"x-goog-api-key": cle},
                              json={"contents": [{"role": "user", "parts": [{"text": q}]}],
                                    "tools": [{"google_search": {}}], "generationConfig": {"temperature": 0.2}},
                              timeout=60)
            if r.status_code != 200:
                continue
            c = r.json()["candidates"][0]
            txt = "".join(p.get("text", "") for p in c.get("content", {}).get("parts", [])).strip()
            if not (c.get("groundingMetadata") or {}).get("groundingChunks") or not txt or txt.upper().startswith("RIEN"):
                return []
            return ["- Recherche Google : " + re.sub(r"\s*\n\s*", " / ", txt)[:900]]
        except Exception:
            continue
    _RECHERCHE_HS.append(True)
    if diag is not None:
        diag.append("  contexte · recherche Google indisponible pour ce passage")
    return []


def contexte_en_plus(cand, cands, diag=None):
    """Texte « CONTEXTE EN PLUS » pour la rédaction ('' s'il n'y a rien)."""
    blocs = recoupements(cand, cands) + sorties_deezer(cand, diag)
    if len(blocs) < 2:                    # source encore maigre : on cherche les faits précis en ligne
        blocs += recherche_google(cand, diag)
    if diag is not None and blocs:
        diag.append(f"  contexte · {len(blocs)} complément(s) : "
                    + ", ".join(sorted({b.split(':')[0].strip('- ') for b in blocs})))
    return "\n".join(blocs)
