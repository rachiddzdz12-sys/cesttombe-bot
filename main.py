"""C'EST TOMBÉ — point d'entrée.

  python main.py --verif   → (sans dépendance) dit s'il faut lancer un post maintenant
  python main.py           → fait le travail, selon la variable MODE :
                              auto : passage planifié, publie si une bonne info est dispo
                              test : génère les carrousels (1 gaming + 1 rap) SANS publier
                              reel : publie un post tout de suite (ignore horaires et écart)
"""
import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import config

PARIS = ZoneInfo("Europe/Paris")
RACINE = Path(__file__).resolve().parent
ETAT = RACINE / "etat.json"
SORTIE = RACINE / "sortie"


# ------------------------------------------------------------------ état (posts publiés, infos déjà vues)
def charger_etat():
    try:
        e = json.loads(ETAT.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        e = {}
    e.setdefault("vus", {})
    e.setdefault("publies", [])
    return e


def sauver_etat(e):
    limite = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    e["vus"] = {k: v for k, v in e["vus"].items() if v >= limite}
    e["publies"] = e["publies"][-300:]
    ETAT.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")


def posts_du_jour(etat, maintenant_paris):
    return [p for p in etat["publies"]
            if datetime.fromisoformat(p["ts"]).astimezone(PARIS).date() == maintenant_paris.date()]


def raison_de_ne_pas_poster(etat, maintenant_paris):
    if not (config.HEURE_DEBUT <= maintenant_paris.hour < config.HEURE_FIN):
        return f"hors horaires ({maintenant_paris:%H:%M} à Paris)"
    du_jour = posts_du_jour(etat, maintenant_paris)
    if len(du_jour) >= config.POSTS_PAR_JOUR:
        return f"quota du jour atteint ({len(du_jour)} posts)"
    if etat["publies"]:
        dernier = datetime.fromisoformat(etat["publies"][-1]["ts"])
        ecart = (maintenant_paris - dernier).total_seconds() / 60
        if ecart < config.ECART_MIN_MINUTES:
            return f"dernier post il y a {int(ecart)} min (minimum {config.ECART_MIN_MINUTES})"
    return None


def sortie_github(cle, valeur):
    f = os.environ.get("GITHUB_OUTPUT")
    if f:
        with open(f, "a") as fh:
            fh.write(f"{cle}={valeur}\n")


def resume_github(lignes):
    f = os.environ.get("GITHUB_STEP_SUMMARY")
    if f:
        with open(f, "a", encoding="utf-8") as fh:
            fh.write("### C'EST TOMBÉ\n\n" + "\n".join(f"- {l}" for l in lignes) + "\n")


# ------------------------------------------------------------------ --verif
def verif():
    mode = os.environ.get("MODE", "auto")
    maintenant = datetime.now(PARIS)
    if mode in ("test", "reel"):
        lancer, raison = True, f"lancement manuel ({mode})"
    elif os.environ.get("PUBLICATION", "").strip().lower() != "on":
        lancer, raison = False, "publication automatique désactivée (variable PUBLICATION ≠ on)"
    else:
        r = raison_de_ne_pas_poster(charger_etat(), maintenant)
        lancer, raison = r is None, (r or "c'est le moment de poster")
    print(f"[verif] {raison}")
    sortie_github("lancer", "true" if lancer else "false")
    if not lancer:
        resume_github([f"Pas de post : {raison}"])


# ------------------------------------------------------------------ travail principal
def executer():
    from bot import hebergement, ia, images, instagram, rendu, sources

    mode = os.environ.get("MODE", "auto")
    test = mode == "test"
    diag = [f"Mode : {mode}"]
    etat = charger_etat()
    now_utc = datetime.now(timezone.utc)
    now_paris = now_utc.astimezone(PARIS)
    code = 0

    try:
        if os.environ.get("IG_ACCESS_TOKEN"):
            instagram.diagnostic(diag)

        cands = sources.lire_gaming(diag) + sources.lire_rap(diag)
        facteur_age = 3 if test else 1   # en test, on accepte des infos plus anciennes pour voir un rendu
        frais = [c for c in cands if c["id"] not in etat["vus"]
                 and sources.age_heures(c, now_utc) <= config.AGE_MAX_HEURES[c["categorie"]] * facteur_age]
        diag.append(f"{len(frais)} infos fraîches et jamais traitées (sur {len(cands)} lues)")

        du_jour = posts_du_jour(etat, now_paris)
        ordre = sorted(["GAMING", "RAP FR"], key=lambda cat: sum(p["categorie"] == cat for p in du_jour))
        titres_publies = [p["titre"] for p in etat["publies"]]
        vu = lambda c: etat["vus"].__setitem__(c["id"], now_utc.isoformat())

        for cat in ordre:
            pool = [c for c in frais if c["categorie"] == cat][:15]
            if not pool:
                diag.append(f"{cat} · aucune info fraîche")
                continue
            try:
                notes = ia.trier(pool, titres_publies)
            except ia.ErreurIA as ex:
                diag.append(f"{cat} · tri IA impossible : {ex}")
                continue

            retenues, infos_faibles = [], []
            for c in pool:
                n = notes.get(c["id"])
                if not n:
                    diag.append(f"  ?    « {c['titre'][:70]} » : pas notée par l'IA")
                    continue
                score = int(n.get("score", 0) or 0)
                if not n.get("info"):
                    verdict = "✗ pas une news"
                elif n.get("doublon"):
                    verdict = "✗ déjà publiée"
                elif score < config.SCORE_MIN:
                    verdict = f"✗ trop faible (mini {config.SCORE_MIN})"
                    infos_faibles.append((score, c))
                else:
                    verdict = "✓"
                    retenues.append((score, c))
                diag.append(f"  {score:>2}/10 {verdict} « {c['titre'][:70]} »")
                if verdict != "✓" and not test:
                    vu(c)   # écartée pour de bon, on ne la reproposera pas
            if test and not retenues and infos_faibles:
                retenues = [max(infos_faibles, key=lambda x: x[0])]   # en test, on montre quand même un rendu
                diag.append("  (test : aucune info au-dessus du seuil, on rend quand même la meilleure)")
            retenues.sort(key=lambda x: -x[0])
            diag.append(f"{cat} · {len(retenues)} infos retenues"
                        + (f", meilleure : « {retenues[0][1]['titre'][:80]} » ({retenues[0][0]}/10)" if retenues else ""))

            fait = False
            for score, c in retenues[:3]:
                photo, credit = images.trouver_photo(c, diag)
                jpeg = images.en_jpeg(photo) if (photo is not None and cat == "RAP FR") else None
                try:
                    red = ia.rediger(c, jpeg)
                except ia.ErreurIA as ex:
                    diag.append(f"  rédaction impossible pour « {c['titre'][:60]} » : {ex}")
                    if not test:
                        vu(c)
                    continue
                post = {"categorie": cat, "source": c["source"], "credit": credit, **red}
                prefixe = f"{now_paris:%Y%m%d-%H%M}-{'jv' if cat == 'GAMING' else 'rap'}"
                fichiers = rendu.carrousel(post, photo, SORTIE, prefixe)
                (SORTIE / f"{prefixe}-legende.txt").write_text(red["legende"], encoding="utf-8")
                diag.append(f"  carrousel prêt : « {red['titre']} » ({len(fichiers)} slides)")
                if test:
                    fait = True
                    break
                urls = hebergement.heberger(fichiers)
                lien = instagram.publier_carrousel(urls, red["legende"])
                vu(c)
                etat["publies"].append({"ts": now_utc.isoformat(), "categorie": cat, "titre": red["titre"],
                                        "source_id": c["id"], "lien": lien})
                diag.append(f"  ✅ PUBLIÉ : {lien}")
                fait = True
                break
            if fait and not test:
                break   # un seul post par passage
    except Exception as ex:
        diag.append(f"❌ Erreur : {type(ex).__name__} : {ex}")
        traceback.print_exc()
        code = 1
    finally:
        if not test:
            sauver_etat(etat)
        print("\n".join(diag))
        resume_github(diag)
    return code


if __name__ == "__main__":
    if "--verif" in sys.argv:
        verif()
    else:
        sys.exit(executer())
