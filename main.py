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


class Journal(list):
    """Liste de lignes de diagnostic, affichées au fur et à mesure (avec l'heure dans les logs GitHub)."""

    def append(self, ligne):
        print(ligne, flush=True)
        super().append(ligne)


def publication_auto():
    """La variable GitHub PUBLICATION (on/off) a priorité sur config.PUBLICATION_AUTO."""
    v = os.environ.get("PUBLICATION", "").strip().lower()
    if v in ("on", "off"):
        return v == "on"
    return config.PUBLICATION_AUTO


# ------------------------------------------------------------------ --verif
def verif():
    mode = os.environ.get("MODE", "auto")
    maintenant = datetime.now(PARIS)
    if mode in ("test", "reel", "voix"):
        lancer, raison = True, f"lancement manuel ({mode})"
    elif not publication_auto():
        lancer, raison = False, "publication automatique désactivée (PUBLICATION_AUTO = False dans config.py)"
    else:
        r = raison_de_ne_pas_poster(charger_etat(), maintenant)
        lancer, raison = r is None, (r or "c'est le moment de poster")
    print(f"[verif] {raison}")
    sortie_github("lancer", "true" if lancer else "false")
    if not lancer:
        resume_github([f"Pas de post : {raison}"])


# ------------------------------------------------------------------ travail principal
def executer():
    from bot import hebergement, ia, images, instagram, reel, rendu, sources

    mode = os.environ.get("MODE", "auto")
    test = mode == "test"
    diag = Journal([f"Mode : {mode}"])
    print(diag[0], flush=True)
    etat = charger_etat()
    now_utc = datetime.now(timezone.utc)
    now_paris = now_utc.astimezone(PARIS)
    code = 0

    try:
        if os.environ.get("IG_ACCESS_TOKEN"):
            instagram.diagnostic(diag)

        cands = sources.lire_gaming(diag) + sources.lire_rap(diag) + sources.lire_x(diag, etat)
        cat_forcee = os.environ.get("CATEGORIE", "").strip().lower() in ("gaming", "rap")
        # en test, ou en lancement manuel ciblé, on accepte des infos plus anciennes (jusqu'à 3x)
        facteur_age = 3 if (test or (mode == "reel" and cat_forcee)) else 1
        frais = [c for c in cands if c["id"] not in etat["vus"]
                 and sources.age_heures(c, now_utc) <= config.AGE_MAX_HEURES[c["categorie"]] * facteur_age]
        diag.append(f"{len(frais)} infos fraîches et jamais traitées (sur {len(cands)} lues)")

        du_jour = posts_du_jour(etat, now_paris)
        ordre = sorted(["GAMING", "RAP FR"], key=lambda cat: sum(p["categorie"] == cat for p in du_jour))
        forcee = {"gaming": "GAMING", "rap": "RAP FR"}.get(os.environ.get("CATEGORIE", "").strip().lower())
        if forcee:   # lancement manuel ciblé sur une catégorie
            ordre = [forcee] + [c for c in ordre if c != forcee]
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
                video = None
                if config.REELS:
                    try:
                        video = reel.fabriquer(post, photo, fichiers, red.get("voix_off"), SORTIE, prefixe, diag)
                    except Exception as ex:   # sans Reel, le carrousel part quand même
                        diag.append(f"  ⚠️ Reel impossible : {str(ex)[:150]}")
                en_ligne = fichiers + ([video] if video else [])
                if test:   # on vérifie aussi l'hébergement, sans publier
                    try:
                        urls = hebergement.heberger(en_ligne)
                        diag.append(f"  fichiers en ligne ({len(urls)}) : {urls[0]}")
                        if video:
                            diag.append(f"  reel en ligne : {urls[-1]}")
                    except hebergement.ErreurHebergement as ex:
                        diag.append(f"  ⚠️ hébergement impossible : {ex}")
                    fait = True
                    break
                urls = hebergement.heberger(en_ligne)
                lien = instagram.publier_carrousel(urls[:len(fichiers)], red["legende"])
                vu(c)
                etat["publies"].append({"ts": now_utc.isoformat(), "categorie": cat, "titre": red["titre"],
                                        "source_id": c["id"], "lien": lien})
                diag.append(f"  ✅ PUBLIÉ : {lien}")
                if video:
                    try:
                        lien_reel = instagram.publier_reel(urls[-1], red["legende"], config.REEL_DANS_LE_FEED)
                        etat["publies"][-1]["reel"] = lien_reel
                        diag.append(f"  ✅ REEL PUBLIÉ : {lien_reel}")
                    except Exception as ex:
                        diag.append(f"  ⚠️ Reel non publié : {str(ex)[:200]}")
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
        elif "x_mois" in etat:   # même en test, les tweets lus sont facturés : on garde le compteur
            reel_etat = charger_etat()
            reel_etat["x_mois"] = etat["x_mois"]
            sauver_etat(reel_etat)
        if ia.JOURNAL:
            diag.append("Gemini : " + " · ".join(ia.JOURNAL))
        resume_github(diag)
    return code


def echantillons_voix():
    """Mode « voix » : fait lire la même phrase par plusieurs voix et les met en ligne pour comparer."""
    from bot import hebergement, voix
    texte = ("Maes est officiellement sorti de prison après 22 mois de détention. "
             "Son avocat parle d'un tournant majeur dans le dossier. "
             "Abonne-toi à C'est tombé pour pas rater la suite.")
    diag, fichiers = Journal(["Mode : voix"]), []
    for v in config.VOIX_A_TESTER:
        config.VOIX = v
        f = voix.lire(texte, SORTIE / v, diag)
        if f:
            dest = SORTIE / f"voix-{v}.mp3"
            f.rename(dest)
            fichiers.append(dest)
    if fichiers:
        for u in hebergement.heberger(fichiers):
            diag.append(f"  écoute : {u}")
    resume_github(diag)
    return 0


if __name__ == "__main__":
    if "--verif" in sys.argv:
        verif()
    elif os.environ.get("MODE") == "voix":
        sys.exit(echantillons_voix())
    else:
        sys.exit(executer())
