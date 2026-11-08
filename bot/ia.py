"""Gemini : trie les infos, puis rédige le titre, les slides et la légende."""
import base64
import json
import os
import re
import time

import requests

import config

URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"


class ErreurIA(Exception):
    pass


def _extraire_json(txt):
    txt = txt.strip()
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt)
    return json.loads(txt)


JOURNAL = []          # ce qui s'est passé avec Gemini pendant ce passage (affiché dans le résumé)
_MODELES_HS = set()   # modèles en échec pendant ce passage : on ne les réessaie pas


def _delai_conseille(r):
    """Délai de réessai indiqué par Google (« retryDelay »: "33s"), sinon None."""
    m = re.search(r'"retryDelay"\s*:\s*"(\d+)(?:\.\d+)?s"', r.text)
    return int(m.group(1)) if m else None


def appel(parts):
    cle = os.environ.get("GEMINI_API_KEY") or config.GEMINI_API_KEY_DANS_LE_CODE
    if not cle:
        raise ErreurIA("clé Gemini manquante")
    derniere = None
    for modele in [m for m in config.GEMINI_MODELES if m not in _MODELES_HS]:
        for essai in range(2):
            debut = time.time()
            try:
                r = requests.post(URL.format(modele),
                                  headers={"x-goog-api-key": cle, "Content-Type": "application/json"},
                                  json={"contents": [{"role": "user", "parts": parts}],
                                        "generationConfig": {"responseMimeType": "application/json",
                                                             "temperature": 0.4}},
                                  timeout=60)
            except requests.RequestException as ex:
                derniere = f"{modele} : {type(ex).__name__}"
                JOURNAL.append(f"{derniere} après {time.time() - debut:.0f} s")
                continue
            duree = time.time() - debut
            if r.status_code == 429:
                delai = _delai_conseille(r)
                derniere = f"{modele} : quota atteint (HTTP 429)"
                JOURNAL.append(derniere + (f", réessai conseillé dans {delai} s" if delai else ""))
                if essai == 0 and delai is not None and delai <= 30:
                    time.sleep(delai + 1)       # limite par minute : courte attente puis réessai
                    continue
                break                           # quota du jour ou attente trop longue : modèle suivant
            if r.status_code in (500, 503):
                derniere = f"{modele} : surchargé (HTTP {r.status_code})"
                JOURNAL.append(derniere)
                time.sleep(8)
                continue
            if r.status_code in (400, 403, 404):
                derniere = f"{modele} : refusé (HTTP {r.status_code}) {r.text[:160]}"
                JOURNAL.append(derniere)
                break
            if r.status_code != 200:
                raise ErreurIA(f"{modele} HTTP {r.status_code} : {r.text[:300]}")
            try:
                cand = r.json()["candidates"][0]["content"]["parts"]
                rep = _extraire_json("".join(p.get("text", "") for p in cand if not p.get("thought")))
                JOURNAL.append(f"{modele} : réponse en {duree:.0f} s")
                return rep
            except (KeyError, IndexError, json.JSONDecodeError) as ex:
                derniere = f"{modele} : réponse illisible ({type(ex).__name__})"
                JOURNAL.append(derniere)
        _MODELES_HS.add(modele)
    raise ErreurIA(f"Gemini n'a pas répondu correctement : {derniere}")


PROMPT_TRI = """Tu es le rédacteur en chef de « C'EST TOMBÉ », une page Instagram d'actu {theme} pour un public français de 16-30 ans.

Voici des infos candidates. Pour chacune, décide :
- "info" : true si c'est une VRAIE actualité (annonce, sortie, date, chiffre, polémique, clash, record, déclaration, rumeur sérieuse).
  false si c'est un guide, une soluce, un bon plan, une promo, une liste de prix, un test, un contenu sponsorisé, ou un post sans info (juste une ambiance, un mème, une pub).
- "score" : de 0 à 10, à quel point ça va faire réagir notre public (10 = tout le monde va en parler).
- "doublon" : true UNIQUEMENT si c'est exactement le même événement qu'un des sujets déjà publiés listés plus bas (même fait, même annonce). Un sujet voisin ou une suite (ex : une réaction, un procès, une nouvelle étape) n'est PAS un doublon.

Sujets déjà publiés récemment :
{deja}

Infos candidates :
{liste}

Réponds UNIQUEMENT en JSON : {{"resultats": [{{"id": "...", "info": true, "score": 7, "doublon": false}}]}}"""


def trier(candidats, titres_publies):
    """Renvoie {id réel du candidat: {"info", "score", "doublon"}}.

    Gemini reçoit des numéros courts (1, 2, 3…) plutôt que les vrais identifiants (longues URL),
    qu'il recopie parfois de travers.
    """
    theme = "jeux vidéo" if candidats[0]["categorie"] == "GAMING" else "rap français"
    liste = "\n".join(f'- id={i} | {c["titre"]} | {c["resume"][:280]}' for i, c in enumerate(candidats, start=1))
    deja = "\n".join(f"- {t}" for t in titres_publies[-20:]) or "(aucun)"
    rep = appel([{"text": PROMPT_TRI.format(theme=theme, deja=deja, liste=liste)}])
    if isinstance(rep, dict):
        rep = rep.get("resultats") or next((v for v in rep.values() if isinstance(v, list)), [])
    notes = {}
    for r in rep if isinstance(rep, list) else []:
        if not isinstance(r, dict):
            continue
        try:
            i = int(str(r.get("id", "")).strip().lstrip("#")) - 1
        except ValueError:
            continue
        if 0 <= i < len(candidats):
            notes[candidats[i]["id"]] = r
    return notes


PROMPT_REDAC = """Tu écris un post carrousel Instagram pour « C'EST TOMBÉ », page d'actu {theme}.
Ton : direct, clair, phrases courtes, français correct, pas de vulgarité, pas de « wesh ». Tu tutoies le lecteur seulement dans l'accroche. Écris toujours les nombres, dates et durées en chiffres (22 mois, 6 novembre, 366 Go). Écris en français correct AVEC TOUS LES ACCENTS (é, è, ê, à, ù, ç…), y compris dans le titre.

PAS DE REMPLISSAGE : pas de phrases creuses (« cela fait parler », « les fans attendent avec impatience », « cette nouvelle attire l'attention »). Si la source est courte, fais seulement 2 sections courtes avec les vrais faits.

RÈGLE ABSOLUE : utilise UNIQUEMENT les faits présents dans la source ci-dessous{image}. N'invente rien : aucune date, aucun chiffre, aucun nom, aucune citation qui n'y figure pas. Si un détail n'est pas dans la source, ne l'écris pas. Reformule avec tes propres mots, ne recopie pas de phrases entières.

SOURCE ({source}) :
Titre : {titre}
Texte : {texte}

Produis :
- "titre" : 6 à 10 mots, percutant, style breaking news, sans point final, sans emoji. Si le titre contient deux idées, sépare-les par « : » (ex : « Maes libéré : son avocat prend la parole »).
- "mot_cle" : 1 à 3 mots copiés EXACTEMENT du titre, le cœur de l'info (un nom, un chiffre, un mot fort).
- "sections" : 2 à 4 sections dans l'ordre logique. Chaque section : "titre" court (ex : "Ce qui se passe", "Les détails", "C'est quand", "Ce qu'en dit le studio", "Pourquoi ça compte") et "texte" de 25 à 70 mots. Total maximum 230 mots.
- "accroche" : 1 phrase pour la légende Instagram, avec 1 emoji maximum.
- "hashtags" : 2 ou 3 hashtags précis sur le sujet (nom du jeu, de l'artiste…), sans espace, en minuscules.
- "faisable" : false si la source ne contient pas assez d'info pour faire un post fiable, sinon true.

Réponds UNIQUEMENT en JSON : {{"titre": "", "mot_cle": "", "sections": [{{"titre": "", "texte": ""}}], "accroche": "", "hashtags": [], "faisable": true}}"""


def rediger(cand, image_jpeg=None):
    theme = "jeux vidéo" if cand["categorie"] == "GAMING" else "rap français"
    parts = [{"text": PROMPT_REDAC.format(
        theme=theme, source=cand["source"], titre=cand["titre"], texte=cand["texte"][:5000],
        image=" et dans l'image jointe (lis le texte écrit dessus)" if image_jpeg else "")}]
    if image_jpeg:
        parts.append({"inline_data": {"mime_type": "image/jpeg",
                                      "data": base64.b64encode(image_jpeg).decode()}})
    res = valider(appel(parts), cand)
    if manque_accents(res):           # Gemini oublie parfois tous les accents : on fait réécrire une fois
        JOURNAL.append("texte sans accents : réécriture demandée")
        parts[0] = {"text": parts[0]["text"] + "\n\nATTENTION : mets bien tous les accents français."}
        res2 = valider(appel(parts), cand)
        if not manque_accents(res2):
            res = res2
    return res


ACCENTS = set("éèêëàâäîïôöùûüçÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ")


def manque_accents(res):
    """Vrai si un texte français assez long ne contient aucun accent (presque impossible en vrai)."""
    texte = res["titre"] + " " + " ".join(s["texte"] for s in res["sections"])
    return len(texte.split()) >= 25 and not any(c in ACCENTS for c in texte)


def valider(rep, cand):
    """Contrôle et nettoie la réponse de l'IA. Lève ErreurIA si inutilisable."""
    if isinstance(rep, list):   # parfois Gemini renvoie [ {...} ]
        rep = next((r for r in rep if isinstance(r, dict)), {})
    if not isinstance(rep, dict):
        raise ErreurIA("réponse IA dans un format inattendu")
    if not rep.get("faisable", True):
        raise ErreurIA("source trop pauvre selon l'IA")
    titre = (rep.get("titre") or "").strip().rstrip(".")
    sections = [s for s in rep.get("sections", [])
                if isinstance(s, dict) and s.get("titre") and s.get("texte")]
    if not titre or not sections:
        raise ErreurIA("réponse incomplète (titre ou sections manquants)")
    if len(titre.split()) > 14:
        titre = " ".join(titre.split()[:14])
    mot_cle = (rep.get("mot_cle") or "").strip()
    if len(mot_cle.split()) > 3:      # un mot clé trop long colorerait la moitié du titre
        mot_cle = ""
    if mot_cle and mot_cle.lower() not in titre.lower():
        mot_cle = ""
    elif mot_cle:  # reprend la casse exacte du titre
        i = titre.lower().index(mot_cle.lower())
        mot_cle = titre[i:i + len(mot_cle)]
    tags = [("#" + t.lstrip("#")).lower().replace(" ", "") for t in rep.get("hashtags", [])[:3]]
    tags += config.HASHTAGS[cand["categorie"]]
    tags = list(dict.fromkeys(tags))
    legende = (f"{(rep.get('accroche') or titre).strip()}\n\n"
               f"Glisse pour tout savoir 👉\n\n"
               f"Source : {cand.get('source_legende', cand['source'])}\n\n"
               + " ".join(tags))
    return {"titre": titre, "mot_cle": mot_cle,
            "sections": [{"titre": s["titre"].strip(), "texte": s["texte"].strip()} for s in sections[:4]],
            "legende": legende[:2200]}
