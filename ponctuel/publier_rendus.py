"""Publication demandée à la main : des rendus déjà fabriqués et validés (carrousel + Reel), publiés tels quels.

Usage : COMPTE=lebruit python ponctuel/publier_rendus.py <dossier des rendus> <plan.json>

plan.json : liste dans l'ordre de publication de
  {"prefixe": "20261115-2228-rap-lebruit-1", "titre": "…", "sources": ["bout du titre de l'info d'origine", …]}
Pour chaque post : <prefixe>-1.jpg, -2.jpg… (slides), <prefixe>-legende.txt, <prefixe>-reel.mp4 et
<prefixe>-reel-couverture.jpg. Les posts sont notés dans l'état du compte (titres publiés, infos d'origine vues)
pour que le bot ne les refasse jamais. Pas de filet anti-doublon ici : c'est une demande explicite.
"""
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import config  # noqa: E402
import main  # noqa: E402  (applique le profil COMPTE)
from bot import hebergement, instagram, sources  # noqa: E402

PAUSE_S = int(os.environ.get("PAUSE_S", "90"))      # entre deux posts, pour ne pas tout lâcher d'un coup


def fichiers_du_post(dossier, prefixe):
    slides = sorted(dossier.glob(f"{prefixe}-[0-9].jpg"), key=lambda f: int(f.stem.rsplit("-", 1)[1]))
    legende = (dossier / f"{prefixe}-legende.txt").read_text(encoding="utf-8").strip()
    video, couv = dossier / f"{prefixe}-reel.mp4", dossier / f"{prefixe}-reel-couverture.jpg"
    if not slides:
        raise FileNotFoundError(f"aucune slide pour {prefixe}")
    return slides, legende, (video if video.exists() else None), (couv if couv.exists() else None)


def marquer_vus(plan, etat, diag):
    """Les infos d'origine (tweet, post Instagram) sont marquées vues : le bot ne les reprendra pas."""
    cands = sources.lire_rap(diag) + sources.lire_x(diag, etat)
    maintenant = datetime.now(timezone.utc).isoformat()
    for p in plan:
        for c in cands:
            if any(m.lower() in (c["titre"] + " " + c.get("resume", "")).lower() for m in p.get("sources", [])):
                etat["vus"][c["id"]] = maintenant
                diag.append(f"  info d'origine marquée vue : « {c['titre'][:70]} »")


def publier(dossier, plan):
    diag = main.Journal([f"Publication à la main sur {getattr(config, 'HANDLE', config.NOM_PAGE)}"])
    instagram.diagnostic(diag)
    etat = main.charger_etat()
    code = 0
    for i, p in enumerate(plan):
        if i:
            time.sleep(PAUSE_S)
        try:
            slides, legende, video, couv = fichiers_du_post(dossier, p["prefixe"])
            entree = {"ts": datetime.now(timezone.utc).isoformat(), "categorie": config.CATEGORIES[0],
                      "titre": p["titre"], "source_id": None, "lien": None, "manuel": True}
            etat["publies"].append(entree)
            main.sauver_etat(etat)            # noté AVANT de publier : jamais republié, même si la suite plante
            en_ligne = slides + ([video, couv] if video and couv else [video] if video else [])
            urls = hebergement.heberger(en_ligne)
            entree["lien"] = instagram.publier_carrousel(urls[:len(slides)], legende)
            main.sauver_etat(etat)
            diag.append(f"✅ PUBLIÉ : « {p['titre']} » → {entree['lien']}")
            if video:
                try:
                    entree["reel"] = instagram.publier_reel(urls[len(slides)], legende, config.REEL_DANS_LE_FEED,
                                                            couverture_url=urls[-1] if couv else None)
                    main.sauver_etat(etat)
                    diag.append(f"✅ REEL PUBLIÉ : {entree['reel']}")
                except Exception as ex:
                    diag.append(f"⚠️ Reel non publié : {str(ex)[:200]}")
                    code = 1
        except Exception as ex:
            diag.append(f"❌ « {p['titre']} » : {type(ex).__name__} : {str(ex)[:200]}")
            traceback.print_exc()
            code = 1
    try:
        marquer_vus(plan, etat, diag)
    except Exception as ex:
        diag.append(f"⚠️ infos d'origine non marquées : {str(ex)[:150]}")
    main.sauver_etat(etat)
    main.resume_github(diag)
    return code


if __name__ == "__main__":
    sys.exit(publier(Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))))
