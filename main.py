"""C'EST TOMBÉ — point d'entrée.

  python main.py --verif   → (sans dépendance) dit s'il faut lancer un post maintenant
  python main.py           → fait le travail, selon la variable MODE :
                              auto : passage planifié, publie si une bonne info est dispo
                              test : génère les carrousels (1 gaming + 1 rap) SANS publier
                              reel : publie un post tout de suite (ignore horaires et écart)
"""
import json
import os
import re
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import config

PARIS = ZoneInfo("Europe/Paris")
RACINE = Path(__file__).resolve().parent

# Plusieurs comptes, un seul bot : COMPTE=lebruit applique comptes/lebruit.py par-dessus config.py.
# Sans COMPTE, c'est C'EST TOMBÉ, exactement comme avant.
COMPTE = os.environ.get("COMPTE", "").strip().lower()
if COMPTE:
    import importlib
    for _cle, _valeur in importlib.import_module(f"comptes.{COMPTE}").REGLAGES.items():
        setattr(config, _cle, _valeur)
    if getattr(config, "IG_USER_ID", None):
        os.environ["IG_USER_ID"] = config.IG_USER_ID
if os.environ.get("VOIX_GENRE", "").strip().lower() == "homme":     # essai d'une voix d'homme
    config.VOIX, config.VOIX_SECOURS, config.VOIX_CONSIGNE = (config.VOIX_HOMME, config.VOIX_SECOURS_HOMME,
                                                              config.VOIX_CONSIGNE_HOMME)
ETAT = RACINE / (f"etat-{COMPTE}.json" if COMPTE else "etat.json")
JOURNAL = RACINE / (f"dernier-journal-{COMPTE}.txt" if COMPTE else "dernier-journal.txt")
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


def rattrapage(maintenant_paris):
    """Réglages de rattrapage (après une coupure) s'ils sont encore valables, sinon None."""
    fin = getattr(config, "RATTRAPAGE_JUSQUA", None)
    if not fin:
        return None
    try:
        limite = datetime.fromisoformat(fin).replace(tzinfo=PARIS)
    except ValueError:
        return None
    return config.RATTRAPAGE if maintenant_paris < limite else None


def lancement(maintenant_paris):
    """Réglages du mode « sortie de GTA 6 » s'ils sont encore valables, sinon None."""
    fin = getattr(config, "LANCEMENT_JUSQUA", None)
    if not fin:
        return None
    try:
        limite = datetime.fromisoformat(fin).replace(tzinfo=PARIS)
    except ValueError:
        return None
    return config.LANCEMENT if maintenant_paris < limite else None


def reglages(maintenant_paris):
    """Rythme du moment : normal, rattrapage (après une coupure) ou lancement (sortie de GTA 6)."""
    r = {"posts_par_jour": config.POSTS_PAR_JOUR, "ecart_min": config.ECART_MIN_MINUTES,
         "heure_debut": config.HEURE_DEBUT, "heure_fin": config.HEURE_FIN, "score_min": config.SCORE_MIN,
         "facteur_age": 1}
    for special in (lancement(maintenant_paris), rattrapage(maintenant_paris)):
        if special:
            r["posts_par_jour"] = max(r["posts_par_jour"], special.get("posts_par_jour", 0))
            r["ecart_min"] = min(r["ecart_min"], special.get("ecart_min", 10 ** 6))
            r["heure_debut"] = min(r["heure_debut"], special.get("heure_debut", 24))
            r["heure_fin"] = max(r["heure_fin"], special.get("heure_fin", 0))
            r["score_min"] = min(r["score_min"], special.get("score_min", 10))
            r["facteur_age"] = max(r["facteur_age"], special.get("facteur_age", 1))
    return r


def raison_de_ne_pas_poster(etat, maintenant_paris):
    r = reglages(maintenant_paris)
    quota = r["posts_par_jour"]
    ecart_min = r["ecart_min"]
    if not (r["heure_debut"] <= maintenant_paris.hour < r["heure_fin"]):
        return f"hors horaires ({maintenant_paris:%H:%M} à Paris)"
    du_jour = posts_du_jour(etat, maintenant_paris)
    if len(du_jour) >= quota:
        return f"quota du jour atteint ({len(du_jour)} posts)"
    if etat["publies"]:
        dernier = datetime.fromisoformat(etat["publies"][-1]["ts"])
        ecart = (maintenant_paris - dernier).total_seconds() / 60
        if ecart < ecart_min:
            return f"dernier post il y a {int(ecart)} min (minimum {ecart_min})"
    return None


def sortie_github(cle, valeur):
    f = os.environ.get("GITHUB_OUTPUT")
    if f:
        with open(f, "a") as fh:
            fh.write(f"{cle}={valeur}\n")


def resume_github(lignes):
    try:
        JOURNAL.write_text("\n".join(str(l) for l in lignes) + "\n", encoding="utf-8")
    except Exception:
        pass
    f = os.environ.get("GITHUB_STEP_SUMMARY")
    if f:
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(f"### {config.NOM_PAGE}\n\n" + "\n".join(f"- {l}" for l in lignes) + "\n")


class Journal(list):
    """Liste de lignes de diagnostic, affichées au fur et à mesure (avec l'heure dans les logs GitHub)."""

    def append(self, ligne):
        print(ligne, flush=True)
        super().append(ligne)


def publication_auto():
    """La variable GitHub PUBLICATION (on/off) a priorité sur config.PUBLICATION_AUTO.
    config.PAUSE (arrêt d'urgence) a priorité sur tout."""
    if getattr(config, "PAUSE", False):
        return False
    v = os.environ.get("PUBLICATION", "").strip().lower()
    if v in ("on", "off"):
        return v == "on"
    return config.PUBLICATION_AUTO


# ------------------------------------------------------------------ --verif
def verif():
    mode = os.environ.get("MODE", "auto")
    maintenant = datetime.now(PARIS)
    if mode in ("test", "reel", "voix", "photos"):
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
def publier_story(url_video, url_image, diag):
    """Le Reel repris en story (vidéo, sinon sa couverture en image). Ne bloque jamais le post ; sautée si le
    quota d'Instagram (posts publiés par l'API sur 24 h) est presque atteint, pour garder la place aux Reels."""
    from bot import instagram
    try:
        utilise, total = instagram.quota()
        if utilise >= total - getattr(config, "STORIES_MARGE", 12):
            diag.append(f"  · story sautée : quota de l'API presque atteint ({utilise}/{total})")
            return None
    except Exception:
        pass
    for nom, media in (("vidéo", {"video_url": url_video}), ("image", {"image_url": url_image})):
        if not next(iter(media.values())):
            continue
        try:
            sid = instagram.publier_story(**media)
            diag.append(f"  ✅ STORY PUBLIÉE ({nom})")
            return sid
        except instagram.MediaRefuse as ex:
            diag.append(f"  ⚠️ story en {nom} refusée : {str(ex)[:160]}")
        except Exception as ex:
            diag.append(f"  ⚠️ story non publiée : {str(ex)[:160]}")
            return None
    return None


def executer():
    from bot import contexte, hebergement, ia, images, instagram, sources, visuels
    if getattr(config, "DA", "v3") == "bruit":        # DA LE BRUIT : mêmes fonctions, autre rendu
        from bot import da_bruit as da3, reel_bruit as reel3
    else:
        from bot import da3, reel3

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
            try:
                instagram.diagnostic(diag)
            except instagram.AccesBloque:
                if not test:
                    # Meta bloque l'appli : on ne dépense ni Apify ni Gemini pour un post impossible.
                    # Le bot reprend tout seul dès que l'accès revient.
                    diag.append("⛔ Accès à l'API Instagram bloqué par Meta : rien n'est préparé cette fois")
                    return 0

        if not test and rattrapage(now_paris):
            config.X_FACTEUR_RECUL = config.RATTRAPAGE["facteur_age"]
        cat_forcee = os.environ.get("CATEGORIE", "").strip().lower() in ("gaming", "rap")
        cands = (sources.lire_gaming(diag) + sources.lire_web(diag) + sources.lire_instagram(diag)
                 + sources.lire_rap(diag) + sources.lire_x(diag, etat))
        cands = [c for c in cands if c["categorie"] in config.CATEGORIES]
        filtre_source = os.environ.get("SOURCE", "").strip().lower()
        if filtre_source in ("x", "instagram", "web"):   # lancement manuel limité à un type de source
            prefixe_id = {"x": ("x:",), "instagram": ("ig:",), "web": ("ag:", "web:")}[filtre_source]
            cands = [c for c in cands if c["id"].startswith(prefixe_id)]
            diag.append(f"Source limitée à : {filtre_source}")
        # en test, ou en lancement manuel ciblé, on accepte des infos plus anciennes (jusqu'à 3x)
        facteur_age = 3 if (test or (mode == "reel" and cat_forcee)) else 1
        r = rattrapage(now_paris) if not test else None
        if r:   # après une coupure : infos plus anciennes acceptées, note mini un peu plus basse
            facteur_age = max(facteur_age, r["facteur_age"])
            config.SCORE_MIN = min(config.SCORE_MIN, r["score_min"])
            diag.append(f"Rattrapage jusqu'au {config.RATTRAPAGE_JUSQUA} : infos jusqu'à {facteur_age}× plus "
                        f"anciennes, note mini {config.SCORE_MIN}")
        lc = lancement(now_paris)
        if lc:  # sortie de GTA 6 : plus de posts, note mini plus basse pour tout couvrir
            config.SCORE_MIN = min(config.SCORE_MIN, lc["score_min"])
            diag.append(f"Lancement GTA 6 jusqu'au {config.LANCEMENT_JUSQUA} : {lc['posts_par_jour']} posts/jour "
                        f"maxi, note mini {config.SCORE_MIN}")
        page_gta = getattr(config, "THEME", "") == "GTA"
        # essai ciblé (MODE=test) : refaire le rendu d'une info précise, même déjà traitée ou publiée
        filtre_test = os.environ.get("TEST_FILTRE", "").strip() if test else ""
        if filtre_test:
            cands = [c for c in cands if re.search(filtre_test, c['titre'], re.I)]
            diag.append(f"Essai ciblé « {filtre_test} » : {len(cands)} info(s)")
        frais = [c for c in cands if (filtre_test or c["id"] not in etat["vus"])
                 and sources.age_heures(c, now_utc) <= config.AGE_MAX_HEURES[c["categorie"]] * facteur_age]
        diag.append(f"{len(frais)} infos fraîches et jamais traitées (sur {len(cands)} lues)")

        du_jour = posts_du_jour(etat, now_paris)
        ordre = sorted(config.CATEGORIES, key=lambda cat: sum(p["categorie"] == cat for p in du_jour))
        forcee = {"gaming": "GAMING", "rap": "RAP FR"}.get(os.environ.get("CATEGORIE", "").strip().lower())
        if forcee:   # lancement manuel ciblé sur une catégorie
            ordre = [forcee] + [c for c in ordre if c != forcee and c in config.CATEGORIES]
        titres_publies = [] if filtre_test else [p["titre"] for p in etat["publies"]]
        vu = lambda c: etat["vus"].__setitem__(c["id"], now_utc.isoformat())

        for cat in ordre:
            recentes = sorted([c for c in frais if c["categorie"] == cat],
                              key=lambda c: sources.age_heures(c, now_utc))
            if page_gta and cat == "GAMING":   # GTA d'abord ; quelques grosses infos gaming à côté
                gta = [c for c in recentes if sources.est_gta(c)]
                pool = gta[: config.POOL_TRI - 5] + [c for c in recentes if not sources.est_gta(c)][:5]
            else:
                pool = recentes[: config.POOL_TRI]
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
                mini = config.SCORE_MIN
                if page_gta and cat == "GAMING" and not sources.est_gta(c):
                    mini = max(mini, config.SCORE_MIN_HORS_GTA)    # hors GTA : seulement l'énorme
                if not n.get("info"):
                    verdict = "✗ pas une news"
                elif n.get("doublon"):
                    verdict = "✗ déjà publiée"
                elif score < mini:
                    verdict = f"✗ trop faible (mini {mini})"
                    infos_faibles.append((score, c))
                else:
                    verdict = "✓"
                    retenues.append((score, c))
                diag.append(f"  {score:>2}/10 {verdict} « {c['titre'][:70]} »")
                if verdict not in ("✓", "✗ déjà publiée") and not test:
                    vu(c)   # écartée pour de bon, on ne la reproposera pas
                # « déjà publiée » reste en réserve : si la meilleure version d'un événement échoue
                # (article illisible…), une autre version du même événement peut encore passer
            if test and not retenues and infos_faibles:
                retenues = [max(infos_faibles, key=lambda x: x[0])]   # en test, on montre quand même un rendu
                diag.append("  (test : aucune info au-dessus du seuil, on rend quand même la meilleure)")
            # GTA en priorité à note proche ; les annonces officielles de Rockstar passent devant
            retenues.sort(key=lambda x: -(x[0] + (1 if page_gta and sources.est_gta(x[1]) else 0)
                                          + (1 if "ROCKSTAR" in x[1]["source"].upper() else 0)))
            diag.append(f"{cat} · {len(retenues)} infos retenues"
                        + (f", meilleure : « {retenues[0][1]['titre'][:80]} » ({retenues[0][0]}/10)" if retenues else ""))

            fait = False
            n_test = int(os.environ.get("TEST_N") or 1) if test else 1   # en test : rendre plusieurs infos
            rendus = 0
            for score, c in retenues[: max(3, n_test)]:
                c = sources.completer_article(c, diag)      # article d'origine : texte complet, vrai lien
                if c.get("a_lire") and len(c.get("texte", "")) < 250:
                    # jamais un post écrit à partir d'un simple titre : trop maigre, risque d'inventer
                    diag.append(f"  ⏭️ article illisible, info écartée : « {c['titre'][:60]} »")
                    if not test:
                        vu(c)
                    continue
                photos, credit = images.trouver_images(c, diag)
                jpeg = images.en_jpeg(photos[0]) if (photos and cat == "RAP FR") else None
                try:
                    plus = contexte.contexte_en_plus(c, cands, diag)
                except Exception as ex:
                    plus = ""
                    diag.append(f"  contexte · impossible : {str(ex)[:100]}")
                try:
                    red = ia.rediger(c, jpeg, plus)
                except ia.ErreurIA as ex:
                    diag.append(f"  rédaction impossible pour « {c['titre'][:60]} » : {ex}")
                    if not test:
                        vu(c)
                    continue
                n_source = len(photos)        # les photos de la source passent toujours en premier (couverture)
                photos, credits = images.completer(photos, visuels.chercher(red.get("visuels"), diag))
                if credits:   # photos sous licence libre : le crédit est obligatoire
                    for cle in ("legende", "legende_reel"):
                        if red.get(cle):
                            red[cle] = red[cle].replace("\n\n#", f"\nPhotos : {' · '.join(credits)}\n\n#", 1)
                post = {"categorie": cat, "source": c["source"], "credit": credit,
                        "source_affichee": c.get("source_legende", c["source"]), **red}
                prefixe = f"{now_paris:%Y%m%d-%H%M}-{'jv' if cat == 'GAMING' else 'rap'}" + (f"-{COMPTE}" if COMPTE else "")
                if test and n_test > 1:
                    prefixe += f"-{rendus + 1}"        # plusieurs rendus d'essai : un nom chacun
                medias = preparer_medias(c, photos, prefixe, diag, n_source, red)
                fichiers = da3.carrousel(post, medias, SORTIE, prefixe, diag)
                (SORTIE / f"{prefixe}-legende.txt").write_text(red["legende"], encoding="utf-8")
                if red.get("legende_reel"):
                    (SORTIE / f"{prefixe}-legende-reel.txt").write_text(red["legende_reel"], encoding="utf-8")
                if test:   # le post complet, pour pouvoir refaire un rendu à l'identique
                    (SORTIE / f"{prefixe}-post.json").write_text(
                        json.dumps(post, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
                diag.append(f"  carrousel prêt : « {red['titre']} » ({len(fichiers)} slides)")
                video = couv_reel = None
                if config.REELS:
                    try:
                        video, couv_reel = reel3.fabriquer(post, medias, red.get("voix_off"), SORTIE, prefixe, diag)
                    except Exception as ex:   # sans Reel, le carrousel part quand même
                        diag.append(f"  ⚠️ Reel impossible : {str(ex)[:150]}")
                        traceback.print_exc()
                en_ligne = fichiers + ([video, couv_reel] if video else [])
                if test:   # on vérifie aussi l'hébergement, sans publier
                    if os.environ.get("HEBERGEMENT", "").lower() == "non":
                        diag.append("  (hébergement non testé)")
                        rendus += 1
                        fait = True
                        if rendus >= n_test:
                            break
                        continue
                    try:
                        urls = hebergement.heberger(en_ligne)
                        diag.append(f"  fichiers en ligne ({len(urls)}) : {urls[0]}")
                        if video:
                            diag.append(f"  reel en ligne : {urls[-2]}")
                    except hebergement.ErreurHebergement as ex:
                        diag.append(f"  ⚠️ hébergement impossible : {ex}")
                    fait = True
                    break
                doublon = instagram.deja_publie(red["legende"])
                if doublon:      # filet de sécurité : le même sujet est déjà sur le compte
                    diag.append(f"  ⏭️ déjà publié sur le compte ({doublon}) : on passe")
                    vu(c)
                    continue
                # l'info est notée AVANT de publier : même si la suite plante, elle ne sera jamais republiée
                vu(c)
                etat["publies"].append({"ts": now_utc.isoformat(), "categorie": cat, "titre": red["titre"],
                                        "source_id": c["id"], "lien": None})
                sauver_etat(etat)
                urls = hebergement.heberger(en_ligne)
                try:
                    lien = instagram.publier_carrousel(urls[:len(fichiers)], red["legende"])
                except instagram.MediaRefuse as ex:
                    if not any(str(f).endswith(".mp4") for f in fichiers):
                        raise
                    # Instagram a refusé la vidéo AVANT publication : on refait le carrousel sans elle
                    diag.append(f"  ⚠️ vidéo refusée par Instagram ({str(ex)[:120]}) : carrousel sans vidéo")
                    sans = {"images": medias["images"] or (medias["video"] or {}).get("images", []), "video": None}
                    fichiers = da3.carrousel(post, sans, SORTIE, prefixe + "b", diag)
                    en_ligne = fichiers + ([video, couv_reel] if video else [])
                    urls = hebergement.heberger(en_ligne)
                    lien = instagram.publier_carrousel(urls[:len(fichiers)], red["legende"])
                etat["publies"][-1]["lien"] = lien
                sauver_etat(etat)
                diag.append(f"  ✅ PUBLIÉ : {lien}")
                if video:
                    try:
                        lien_reel = instagram.publier_reel(urls[-2], red.get("legende_reel") or red["legende"],
                                                           config.REEL_DANS_LE_FEED,
                                                           couverture_url=urls[-1])
                        etat["publies"][-1]["reel"] = lien_reel
                        diag.append(f"  ✅ REEL PUBLIÉ : {lien_reel}")
                    except Exception as ex:
                        diag.append(f"  ⚠️ Reel non publié : {str(ex)[:200]}")
                else:
                    diag.append("  ⚠️ pas de Reel pour ce post")
                if getattr(config, "STORIES", False):          # chaque publication a sa story
                    sid = publier_story(urls[-2] if video else None, urls[-1] if video else urls[0], diag)
                    if sid:
                        etat["publies"][-1]["story"] = sid
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


def preparer_medias(cand, photos, prefixe, diag, n_source=None, red=None):
    """Images (analysées : textes incrustés, visages) + vidéo de la source (analysée image par image).
    Les n_source premières photos viennent de la source de l'info ; les suivantes ont été cherchées ailleurs."""
    n_source = len(photos) if n_source is None else n_source
    from bot import placement, sources, video as vid
    images = []
    for i, img in enumerate(photos):
        try:
            images.append({"img": img, "analyse": placement.analyser(img), "nom": f"photo{i + 1}",
                           "origine": "source" if i < n_source else "autre"})
        except Exception as ex:
            diag.append(f"  ⚠️ analyse de l'image {i + 1} impossible : {str(ex)[:100]}")
    v = None
    mots = re.findall(r"[\wÀ-ÿ']+", f"{(red or {}).get('titre', '')} {' '.join((red or {}).get('mots_cles') or [])} "
                                    f"{(red or {}).get('recherche_video', '')}")
    if config.VIDEOS and not cand.get("videos") and getattr(config, "VIDEOS_RECHERCHE_X", False) \
            and red and red.get("recherche_video"):
        # pas de vidéo dans la source : une vidéo qui montre le sujet (la mission, le clip, la scène virale)
        vids = sources.videos_x(red["recherche_video"], mots, diag, likes_min=getattr(config, "VIDEOS_LIKES_MIN", 200))
        court = " ".join(red["recherche_video"].split()[:2])
        if not vids and court != red["recherche_video"]:      # recherche plus large : le nom seul
            vids = sources.videos_x(court, mots, diag, likes_min=getattr(config, "VIDEOS_LIKES_MIN", 200) // 2)
        if vids:
            cand = {**cand, "videos": vids}
    if config.VIDEOS and not cand.get("videos") and getattr(config, "VIDEOS_OFFICIELLES", False) \
            and red and red.get("instagram"):
        # sinon : extrait officiel posté par l'artiste (clip, teaser) s'il y en a un récent
        vids = sources.videos_officielles(red["instagram"], mots, diag)
        if vids:
            cand = {**cand, "videos": vids}
    if config.VIDEOS and cand.get("videos"):
        source = vid.telecharger(cand, SORTIE / f"{prefixe}-src", diag)
        if source:
            try:
                v = vid.preparer(source, SORTIE / f"{prefixe}-src", diag)
            except Exception as ex:
                diag.append(f"  ⚠️ vidéo inutilisable : {str(ex)[:150]}")
    return {"images": images, "video": v}


def photos_brutes():
    """Mode « photos » : télécharge les images brutes des meilleures infos du moment (pour faire des maquettes)."""
    from bot import hebergement, images, sources
    diag = Journal(["Mode : photos"])
    etat = charger_etat()
    cands = (sources.lire_gaming(diag) + sources.lire_web(diag) + sources.lire_instagram(diag)
             + sources.lire_rap(diag) + sources.lire_x(diag, etat))
    fichiers = []
    for n, c in enumerate([c for c in cands if c.get("images")][:12]):
        for k, url in enumerate(c["images"][:4]):
            try:
                img = images._telecharger(url)
                f = SORTIE / f"brut-{n:02d}-{k}.jpg"
                f.parent.mkdir(parents=True, exist_ok=True)
                img.save(f, "JPEG", quality=90)
                fichiers.append(f)
                diag.append(f"  {f.name} · {img.width}x{img.height} · {c['titre'][:60]}")
            except Exception as ex:
                diag.append(f"  échec {url[:60]} : {str(ex)[:80]}")
        for k, url in enumerate(c.get("videos", [])[:1]):
            try:
                r = sources.http_get(url)
                f = SORTIE / f"brut-{n:02d}-video.mp4"
                f.write_bytes(r.content)
                fichiers.append(f)
                diag.append(f"  {f.name} · vidéo · {c['titre'][:60]}")
            except Exception as ex:
                diag.append(f"  échec vidéo : {str(ex)[:80]}")
    if fichiers:
        hebergement.heberger(fichiers)
        diag.append(f"{len(fichiers)} fichiers en ligne")
    if "x_mois" in etat:
        e = charger_etat()
        e["x_mois"] = etat["x_mois"]
        sauver_etat(e)
    resume_github(diag)
    return 0


def echantillons_voix():
    """Mode « voix » : fait lire la même phrase par plusieurs voix et les met en ligne pour comparer."""
    from bot import hebergement, voix
    texte = ("Teddy Riner se lance dans la course à l’Élysée. Le quintuple champion olympique a annoncé ce lundi "
             "sa candidature à la présidentielle 2027, dans une vidéo sur ses réseaux. Abonne-toi à C’est tombé.")
    diag, fichiers = Journal(["Mode : voix"]), []
    for v in config.VOIX_A_TESTER:
        config.VOIX = v
        f = voix.lire(texte, SORTIE / v, diag)
        if f:
            dest = SORTIE / f"voix-{v.replace(':', '-')}.mp3"
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
    elif os.environ.get("MODE") == "photos":
        sys.exit(photos_brutes())
    else:
        sys.exit(executer())
