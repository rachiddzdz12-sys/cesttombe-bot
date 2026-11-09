"""Post ponctuel (actu politique, demandé à la main) : Teddy Riner annonce sa candidature à la présidentielle 2027.

Texte écrit à la main à partir de sources vérifiées (franceinfo, Brut, RTS, le tweet de Teddy Riner du 9/11/2026).
La vidéo est celle du tweet de Teddy Riner, récupérée via Apify.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import config  # noqa: E402
import main  # noqa: E402
from bot import da, hebergement, images, instagram, reel, rendu, sources, visuels  # noqa: E402

rendu.ACCENTS["ACTU"] = "#2EE6FF"          # catégorie actu générale : cyan (ni lime gaming, ni orange rap)
SORTIE = main.SORTIE
SORTIE.mkdir(exist_ok=True)
diag = main.Journal(["Post ponctuel : Teddy Riner candidat à la présidentielle 2027"])
PUBLIER = os.environ.get("PUBLIER") == "oui"

post = {
    "categorie": "ACTU", "source": "@TEDDYRINER (X) · FRANCEINFO", "credit": "",
    "titre": "Teddy Riner candidat à la présidentielle 2027", "mot_cle": "présidentielle 2027",
    "sections": [
        {"titre": "Ce qui se passe",
         "texte": "Teddy Riner a annoncé ce lundi 9 novembre sa candidature à l’élection présidentielle de 2027, "
                  "dans une vidéo publiée sur ses réseaux sociaux. « Je suis candidat à l’élection présidentielle "
                  "de 2027 », a écrit le quintuple champion olympique de judo."},
        {"titre": "Pourquoi il se lance",
         "texte": "Il explique que sa décision remonte à l’après JO de Paris 2024 : il dit avoir vu le pays se "
                  "rassembler, puis se diviser quelques semaines plus tard. Il se présente comme ni de droite "
                  "ni de gauche."},
    ],
}
voix_off = ("Teddy Riner se lance dans la course à l’Élysée. Le quintuple champion olympique a annoncé ce lundi "
            "sa candidature à la présidentielle 2027, dans une vidéo sur ses réseaux. Abonne-toi à C’est tombé.")
legende = ("Teddy Riner se lance pour 2027 : retour sur son annonce en images 🗳️\n\n"
           "Glisse pour tout savoir 👉\n\n"
           "Sources : @teddyriner (X), franceinfo\n\n"
           "#teddyriner #presidentielle2027 #election #actualite #cesttombe")

# ------------------------------------------------------------------ 1. le tweet et sa vidéo (Apify)
tweet, lus = None, 0
for requete in ("from:teddyriner candidat", "from:teddyriner"):
    r = requests.post(f"https://api.apify.com/v2/acts/{config.APIFY_ACTEUR}/run-sync-get-dataset-items",
                      params={"token": os.environ["APIFY_TOKEN"], "timeout": 150, "maxItems": 10},
                      json={"twitterContent": requete, "maxItems": 10, "queryType": "Latest"}, timeout=200)
    items = [t for t in r.json() if isinstance(t, dict)] if r.status_code < 400 else []
    lus += len(items)
    for t in items:
        texte = t.get("text") or t.get("full_text") or t.get("fullText") or ""
        if "candidat" in texte.lower() and sources._videos_tweet(t) and not texte.startswith("From KaitoEasyAPI"):
            tweet = t
            break
    diag.append(f"Apify « {requete} » → {len(items)} tweets, vidéo trouvée : {'oui' if tweet else 'non'}")
    if tweet:
        break
if not tweet:
    sys.exit("Vidéo du tweet introuvable : il faudra l'envoyer à la main.")
cand = {"categorie": "ACTU", "images": [], "videos": sources._videos_tweet(tweet), "credit": ""}
img = sources._premier(tweet, ["media_url_https", "mediaUrl", "media_url", "thumbnail_url"])
if isinstance(img, str):
    cand["images"] = [img]
diag.append(f"Tweet : {(tweet.get('text') or tweet.get('fullText') or '')[:140]}")

# ------------------------------------------------------------------ 2. rendu DA v2
prefixe = f"{datetime.now(main.PARIS):%Y%m%d-%H%M}-actu"
photos, _ = images.trouver_images(cand, diag)
n_source = len(photos)
photos, credits = images.completer(photos, visuels.chercher([{"type": "personne", "nom": "Teddy Riner"}], diag))
if credits:
    legende = legende.replace("\n\n#", f"\nPhotos : {' · '.join(credits)}\n\n#", 1)
medias = main.preparer_medias(cand, photos, prefixe, diag, n_source)
fichiers = da.carrousel(post, medias, SORTIE, prefixe, diag)
diag.append(f"carrousel prêt ({len(fichiers)} slides) : {[f.name for f in fichiers]}")
video = reel.fabriquer(post, medias, voix_off, SORTIE, prefixe, diag)
(SORTIE / f"{prefixe}-legende.txt").write_text(legende, encoding="utf-8")
if not PUBLIER:
    sys.exit(0)

# ------------------------------------------------------------------ 3. publication
urls = hebergement.heberger(fichiers + [video])
try:
    lien = instagram.publier_carrousel(urls[:len(fichiers)], legende)
except instagram.ErreurInstagram as ex:
    diag.append(f"⚠️ carrousel refusé ({str(ex)[:150]}) : nouvel essai sans vidéo")
    sans = {"images": medias["images"] or (medias["video"] or {}).get("images", []), "video": None}
    fichiers = da.carrousel(post, sans, SORTIE, prefixe + "b", diag)
    urls = hebergement.heberger(fichiers + [video])
    lien = instagram.publier_carrousel(urls[:len(fichiers)], legende)
diag.append(f"✅ CARROUSEL PUBLIÉ : {lien}")
pub = {"ts": datetime.now(timezone.utc).isoformat(), "categorie": "ACTU", "titre": post["titre"] + " (en images)",
       "source_id": "x:" + str(tweet.get("id") or tweet.get("id_str") or ""), "lien": lien}
try:
    pub["reel"] = instagram.publier_reel(urls[-1], legende, config.REEL_DANS_LE_FEED)
    diag.append(f"✅ REEL PUBLIÉ : {pub['reel']}")
except Exception as ex:
    diag.append(f"⚠️ Reel non publié : {str(ex)[:200]}")
(SORTIE / "publication.json").write_text(json.dumps({"pub": pub, "tweets_lus": lus}, ensure_ascii=False))
