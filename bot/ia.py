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


def appel(parts):
    cle = os.environ.get("GEMINI_API_KEY") or config.GEMINI_API_KEY_DANS_LE_CODE
    if not cle:
        raise ErreurIA("clé Gemini manquante")
    derniere = None
    for modele in config.GEMINI_MODELES:
        for essai in range(3):
            try:
                r = requests.post(URL.format(modele),
                                  headers={"x-goog-api-key": cle, "Content-Type": "application/json"},
                                  json={"contents": [{"role": "user", "parts": parts}],
                                        "generationConfig": {"responseMimeType": "application/json",
                                                             "temperature": 0.4}},
                                  timeout=120)
            except requests.RequestException as ex:
                derniere = str(ex)
                time.sleep(10)
                continue
            if r.status_code in (429, 500, 503):        # quota ou surcharge : on patiente
                derniere = f"{modele} HTTP {r.status_code}"
                time.sleep(20 * (essai + 1))
                continue
            if r.status_code in (400, 404) and "model" in r.text.lower():
                derniere = f"{modele} indisponible"
                break                                   # modèle inconnu : on passe au suivant
            if r.status_code != 200:
                raise ErreurIA(f"{modele} HTTP {r.status_code} : {r.text[:300]}")
            try:
                cand = r.json()["candidates"][0]["content"]["parts"]
                return _extraire_json("".join(p.get("text", "") for p in cand))
            except (KeyError, IndexError, json.JSONDecodeError) as ex:
                derniere = f"réponse illisible ({ex})"
                time.sleep(5)
    raise ErreurIA(f"Gemini n'a pas répondu correctement : {derniere}")


PROMPT_TRI = """Tu es le rédacteur en chef de « C'EST TOMBÉ », une page Instagram d'actu {theme} pour un public français de 16-30 ans.

Voici des infos candidates. Pour chacune, décide :
- "info" : true si c'est une VRAIE actualité (annonce, sortie, date, chiffre, polémique, clash, record, déclaration, rumeur sérieuse).
  false si c'est un guide, une soluce, un bon plan, une promo, une liste de prix, un test, un contenu sponsorisé, ou un post sans info (juste une ambiance, un mème, une pub).
- "score" : de 0 à 10, à quel point ça va faire réagir notre public (10 = tout le monde va en parler).
- "doublon" : true si c'est la même histoire qu'un des sujets déjà publiés listés plus bas.

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
    notes = {}
    for r in rep.get("resultats", []):
        try:
            i = int(str(r.get("id", "")).strip().lstrip("#")) - 1
        except ValueError:
            continue
        if 0 <= i < len(candidats):
            notes[candidats[i]["id"]] = r
    return notes


PROMPT_REDAC = """Tu écris un post carrousel Instagram pour « C'EST TOMBÉ », page d'actu {theme}.
Ton : direct, clair, phrases courtes, français correct, pas de vulgarité, pas de « wesh ». Tu tutoies le lecteur seulement dans l'accroche.

RÈGLE ABSOLUE : utilise UNIQUEMENT les faits présents dans la source ci-dessous{image}. N'invente rien : aucune date, aucun chiffre, aucun nom, aucune citation qui n'y figure pas. Si un détail n'est pas dans la source, ne l'écris pas. Reformule avec tes propres mots, ne recopie pas de phrases entières.

SOURCE ({source}) :
Titre : {titre}
Texte : {texte}

Produis :
- "titre" : 6 à 10 mots, percutant, style breaking news, sans point final, sans emoji.
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
    return valider(appel(parts), cand)


def valider(rep, cand):
    """Contrôle et nettoie la réponse de l'IA. Lève ErreurIA si inutilisable."""
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
