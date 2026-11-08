"""Publication des carrousels via l'API officielle Instagram (connexion Facebook)."""
import os
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


def _attendre(container_id, limite_s=240):
    debut = time.time()
    while time.time() - debut < limite_s:
        statut = _req("GET", container_id, fields="status_code").get("status_code")
        if statut == "FINISHED":
            return
        if statut in ("ERROR", "EXPIRED"):
            raise ErreurInstagram(f"Instagram a refusé le média ({statut})")
        time.sleep(5)
    raise ErreurInstagram("Instagram met trop de temps à traiter les images")


def publier_carrousel(urls, legende):
    ig = os.environ.get("IG_USER_ID")
    if not ig:
        raise ErreurInstagram("IG_USER_ID manquant")
    enfants = [_req("POST", f"{ig}/media", image_url=u, is_carousel_item="true")["id"] for u in urls]
    for c in enfants:
        _attendre(c)
    cont = _req("POST", f"{ig}/media", media_type="CAROUSEL", children=",".join(enfants), caption=legende)["id"]
    _attendre(cont)
    media_id = _req("POST", f"{ig}/media_publish", creation_id=cont)["id"]
    try:
        return _req("GET", media_id, fields="permalink").get("permalink", media_id)
    except ErreurInstagram:
        return media_id


def publier_reel(video_url, legende, dans_le_feed=False):
    ig = os.environ.get("IG_USER_ID")
    if not ig:
        raise ErreurInstagram("IG_USER_ID manquant")
    cont = _req("POST", f"{ig}/media", media_type="REELS", video_url=video_url, caption=legende,
                share_to_feed="true" if dans_le_feed else "false")["id"]
    _attendre(cont, limite_s=420)      # la vidéo prend plus de temps à être traitée
    media_id = _req("POST", f"{ig}/media_publish", creation_id=cont)["id"]
    try:
        return _req("GET", media_id, fields="permalink").get("permalink", media_id)
    except ErreurInstagram:
        return media_id


def diagnostic(diag):
    """Vérifie le token et le compte. Aide à trouver IG_USER_ID s'il manque."""
    try:
        moi = _req("GET", "me", fields="id,name")
        diag.append(f"Meta · token valide (utilisateur : {moi.get('name', moi.get('id'))})")
    except ErreurInstagram as ex:
        diag.append(f"Meta · token refusé : {ex}")
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
