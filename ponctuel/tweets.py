"""Publication demandée à la main : les N derniers tweets d'un compte X, un post (carrousel + Reel) chacun.

Usage (workflow rafale-tweets) : COMPTE=FrenchRapUS NOMBRE=10 python ponctuel/tweets.py
Chaque info suit le même chemin qu'un post du bot : rédaction par l'IA, photos en plus, DA v2, voix Aoede.
"""
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
os.environ.setdefault("CATEGORIE", "rap")          # recul de 72 h sur les tweets (pas seulement 24 h)

import config  # noqa: E402
import main  # noqa: E402
from bot import da, hebergement, ia, images, instagram, reel, sources, visuels  # noqa: E402

COMPTE = os.environ.get("COMPTE", "FrenchRapUS")
NOMBRE = int(os.environ.get("NOMBRE", "10"))
config.COMPTES_X = [COMPTE]
SORTIE = main.SORTIE
SORTIE.mkdir(exist_ok=True)

etat = main.charger_etat()
diag = main.Journal([f"Rafale : les {NOMBRE} derniers tweets de @{COMPTE}"])
cands = [c for c in sources.lire_x(diag, etat) if c["id"] not in etat["vus"]][:NOMBRE]
main.sauver_etat(etat)                              # compteur Apify à jour tout de suite
diag.append(f"{len(cands)} tweet(s) à publier")
publies = 0
for n, c in enumerate(cands, 1):
    cat = c["categorie"]
    diag.append(f"\n[{n}/{len(cands)}] {cat} · {c['titre'][:110]}")
    try:
        photos, credit = images.trouver_images(c, diag)
        jpeg = images.en_jpeg(photos[0]) if (photos and cat == "RAP FR") else None
        red = ia.rediger(c, jpeg)
        n_source = len(photos)
        photos, credits = images.completer(photos, visuels.chercher(red.get("visuels"), diag))
        if credits:
            red["legende"] = red["legende"].replace("\n\n#", f"\nPhotos : {' · '.join(credits)}\n\n#", 1)
        post = {"categorie": cat, "source": c["source"], "credit": credit, **red}
        prefixe = f"{datetime.now(main.PARIS):%Y%m%d-%H%M}-x{n:02d}"
        medias = main.preparer_medias(c, photos, prefixe, diag, n_source)
        fichiers = da.carrousel(post, medias, SORTIE, prefixe, diag)
        video = None
        try:
            video = reel.fabriquer(post, medias, red.get("voix_off"), SORTIE, prefixe, diag)
        except Exception as ex:
            diag.append(f"  ⚠️ Reel impossible : {str(ex)[:150]}")
        urls = hebergement.heberger(fichiers + ([video] if video else []))
        try:
            lien = instagram.publier_carrousel(urls[:len(fichiers)], red["legende"])
        except instagram.ErreurInstagram as ex:
            if not any(str(f).endswith(".mp4") for f in fichiers):
                raise
            diag.append(f"  ⚠️ vidéo refusée ({str(ex)[:120]}) : carrousel sans vidéo")
            sans = {"images": medias["images"] or (medias["video"] or {}).get("images", []), "video": None}
            fichiers = da.carrousel(post, sans, SORTIE, prefixe + "b", diag)
            urls = hebergement.heberger(fichiers + ([video] if video else []))
            lien = instagram.publier_carrousel(urls[:len(fichiers)], red["legende"])
        now = datetime.now(timezone.utc).isoformat()
        etat["vus"][c["id"]] = now
        etat["publies"].append({"ts": now, "categorie": cat, "titre": red["titre"], "source_id": c["id"],
                                "lien": lien})
        diag.append(f"  ✅ PUBLIÉ : « {red['titre']} » {lien}")
        if video:
            try:
                etat["publies"][-1]["reel"] = instagram.publier_reel(urls[-1], red["legende"],
                                                                     config.REEL_DANS_LE_FEED)
                diag.append(f"  ✅ REEL : {etat['publies'][-1]['reel']}")
            except Exception as ex:
                diag.append(f"  ⚠️ Reel non publié : {str(ex)[:200]}")
        publies += 1
    except Exception as ex:
        diag.append(f"  ❌ {type(ex).__name__} : {str(ex)[:200]}")
        traceback.print_exc()
    main.sauver_etat(etat)                          # l'état est enregistré après chaque post
    for f in SORTIE.glob(f"*-x{n:02d}-*"):          # place disque : on ne garde que les images
        if f.is_dir():
            import shutil
            shutil.rmtree(f, ignore_errors=True)
    time.sleep(20)
diag.append(f"\nTerminé : {publies} post(s) publié(s) sur {len(cands)}")
if ia.JOURNAL:
    diag.append("Gemini : " + " · ".join(ia.JOURNAL))
