"""Publication des carrousels via l'API officielle Instagram (connexion Facebook)."""
import os
from datetime import datetime, timedelta, timezone
import re
import time

import requests

import config


class ErreurInstagram(Exception):
    pass


def _token():
    t = os.environ.get("IG_ACCESS_TOKEN")
    if not t:
        raise ErreurInstagram("IG_ACCESS_TOKEN manquant")
    return t


def _req(methode, chemin, **params):
    params["access_token"] = _token()
    url = f"{config.GRAPH}/{chemin}"
    r = requests.post(url, data=params, timeout=60) if methode == "POST" else requests.get(url, params=params, timeout=60)
    j = r.json()
    if "error" in j:
        raise ErreurInstagram(j["error"].get("message", str(j["error"])))
    return j


class MediaRefuse(ErreurInstagram):
    """Instagram refuse un média AVANT publication (format, vidéo…) : on peut réessayer autrement."""


class PublicationIncertaine(ErreurInstagram):
    """Erreur au moment de publier, sans pouvoir vérifier si le post est parti : ne JAMAIS republier."""


def _attendre(container_id, limite_s=240):
    debut = time.time()
    while time.time() - debut < limite_s:
        statut = _req("GET", container_id, fields="status_code").get("status_code")
        if statut == "FINISHED":
            return
        if statut in ("ERROR", "EXPIRED"):
            raise MediaRefuse(f"Instagram a refusé le média ({statut})")
        time.sleep(5)
    raise ErreurInstagram("Instagram met trop de temps à traiter les images")


def publier_carrousel(urls, legende):
    ig = os.environ.get("IG_USER_ID")
    if not ig:
        raise ErreurInstagram("IG_USER_ID manquant")
    enfants = []
    try:
        for u in urls:
            if u.lower().endswith(".mp4"):
                enfants.append(_req("POST", f"{ig}/media", media_type="VIDEO", video_url=u,
                                    is_carousel_item="true")["id"])
            else:
                enfants.append(_req("POST", f"{ig}/media", image_url=u, is_carousel_item="true")["id"])
        for c, u in zip(enfants, urls):
            _attendre(c, limite_s=420 if u.lower().endswith(".mp4") else 240)
        cont = _req("POST", f"{ig}/media", media_type="CAROUSEL", children=",".join(enfants), caption=legende)["id"]
        _attendre(cont)
    except MediaRefuse:
        raise
    except ErreurInstagram as ex:      # rien n'est publié à ce stade : on peut réessayer autrement
        raise MediaRefuse(str(ex))
    return _publier(ig, cont, legende, "FEED")


def _publier(ig, cont, legende, produit):
    """media_publish. Instagram renvoie parfois une erreur (ou ne répond pas) alors que le post est bien parti :
    dans ce cas on vérifie sur le compte avant de conclure, et on ne republie jamais à l'aveugle."""
    try:
        media_id = _req("POST", f"{ig}/media_publish", creation_id=cont)["id"]
    except Exception as ex:
        time.sleep(15)
        media_id = _retrouver(ig, legende, produit)
        if not media_id:
            raise PublicationIncertaine(f"publication incertaine : {str(ex)[:150]}")
    try:
        return _req("GET", media_id, fields="permalink").get("permalink", media_id)
    except Exception:
        return media_id


def _retrouver(ig, legende, produit, n=6):
    """Cherche parmi les derniers posts du compte un post (FEED ou REELS) avec exactement cette légende."""
    try:
        for m in _req("GET", f"{ig}/media", fields="id,caption,media_product_type", limit=n).get("data", []):
            if m.get("media_product_type") == produit and \
                    (m.get("caption") or "").strip()[:120] == legende.strip()[:120]:
                return m["id"]
    except Exception:
        return None
    return None


GENERIQUES = {"#rapfr", "#rapfrancais", "#actusrap", "#hiphopfrancais", "#cesttombe", "#jeuxvideo", "#gaming",
              "#actujv", "#gamer", "#actualite", "#actu", "#news", "#rap", "#hiphop"}


def _tags(texte):
    return {h[1:].lower() for h in re.findall(r"#\w+", texte or "")} - {g[1:] for g in GENERIQUES}


def _meme_sujet(a, b):
    """Hashtags de sujet en commun (« sardou » et « michelsardou » comptent comme le même)."""
    communs = sum(1 for x in a if any(x == y or (len(x) >= 4 and len(y) >= 4 and (x in y or y in x)) for y in b))
    return communs >= 2 or (communs == 1 and len(a) == 1 and len(b) == 1)


def deja_publie(legende, heures=24):
    """Filet de sécurité anti-doublon, vérifié sur Instagram lui-même : un post récent du compte qui parle du
    même sujet (mêmes hashtags de noms, de titres…). Renvoie son lien, ou None."""
    ig = os.environ.get("IG_USER_ID")
    sujets = _tags(legende)
    if not ig or not sujets:
        return None
    limite = datetime.now(timezone.utc) - timedelta(hours=heures)
    try:
        recents = _req("GET", f"{ig}/media", fields="caption,timestamp,permalink,media_product_type",
                       limit=25).get("data", [])
    except Exception:
        return None
    for m in recents:
        if m.get("media_product_type") == "REELS":
            continue
        if datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")) < limite:
            break
        if _meme_sujet(sujets, _tags(m.get("caption"))):
            return m.get("permalink") or m.get("id")
    return None


def publier_reel(video_url, legende, dans_le_feed=False):
    ig = os.environ.get("IG_USER_ID")
    if not ig:
        raise ErreurInstagram("IG_USER_ID manquant")
    cont = _req("POST", f"{ig}/media", media_type="REELS", video_url=video_url, caption=legende,
                share_to_feed="true" if dans_le_feed else "false")["id"]
    _attendre(cont, limite_s=420)      # la vidéo prend plus de temps à être traitée
    return _publier(ig, cont, legende, "REELS")


class AccesBloque(ErreurInstagram):
    """Meta a bloqué l'accès de l'application à l'API (erreur 200 « API access blocked »)."""


def diagnostic(diag):
    """Vérifie le token et le compte. Aide à trouver IG_USER_ID s'il manque.
    Lève AccesBloque si Meta bloque l'application : inutile alors de préparer un post."""
    try:
        moi = _req("GET", "me", fields="id,name")
        diag.append(f"Meta · token valide (utilisateur : {moi.get('name', moi.get('id'))})")
    except ErreurInstagram as ex:
        diag.append(f"Meta · token refusé : {ex}")
        if "access blocked" in str(ex).lower():
            raise AccesBloque(str(ex))
        return
    try:
        info = _req("GET", "debug_token", input_token=_token()).get("data", {})
        diag.append("Meta · autorisations du token : " + ", ".join(sorted(info.get("scopes", []))))
    except ErreurInstagram as ex:
        diag.append(f"Meta · impossible de lire les autorisations du token : {ex}")
    ig = os.environ.get("IG_USER_ID")
    if not ig:
        try:
            pages = _req("GET", "me/accounts", fields="name,instagram_business_account{id,username}")
            for p in pages.get("data", []):
                iba = p.get("instagram_business_account")
                if iba:
                    diag.append(f"Meta · page « {p['name']} » → compte @{iba.get('username')} : IG_USER_ID = {iba['id']}")
            if not pages.get("data"):
                diag.append("Meta · aucune page Facebook accessible avec ce token")
        except ErreurInstagram as ex:
            diag.append(f"Meta · impossible de lister les pages : {ex}")
        return
    try:
        compte = _req("GET", ig, fields="username,followers_count,media_count")
        diag.append(f"Instagram · @{compte.get('username')} ({compte.get('followers_count', '?')} abonnés)")
        q = _req("GET", f"{ig}/content_publishing_limit", fields="quota_usage,config")
        data = (q.get("data") or [{}])[0]
        diag.append(f"Instagram · posts publiés par l'API sur 24 h : {data.get('quota_usage', '?')}"
                    f" / {data.get('config', {}).get('quota_total', '?')}")
    except ErreurInstagram as ex:
        diag.append(f"Instagram · erreur sur le compte {ig} : {ex}")
