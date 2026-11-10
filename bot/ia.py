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


def appel(parts, modeles=None):
    cle = os.environ.get("GEMINI_API_KEY") or config.GEMINI_API_KEY_DANS_LE_CODE
    if not cle:
        raise ErreurIA("clé Gemini manquante")
    derniere = None
    for modele in [m for m in (modeles or config.GEMINI_MODELES) if m not in _MODELES_HS]:
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
- "info" : true si c'est une VRAIE actualité (annonce, sortie, date, chiffre, polémique, clash, record, déclaration, rumeur sérieuse). Les récaps de sorties (« les sorties de la semaine », « ce qui sort ce soir à minuit », liste des albums/sons du vendredi) comptent comme de l'info utile : note-les au moins 7.
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

Produis (format « carrousel + Reel » épuré : textes très courts, percutants) :
- "titre" : 6 à 10 mots, le titre complet de l'info, style breaking news, sans emoji.
- "titre_haut" et "titre_bas" : le même titre coupé en 2 lignes courtes (chacune 22 caractères maximum, espaces compris). La 2e ligne est la plus forte (elle sera en couleur). Ex : « Teddy Riner, » / « candidat en 2027. »
- "mot_cle" : 1 à 3 mots copiés EXACTEMENT du titre, le cœur de l'info.
- "rubrique" : 1 ou 2 mots pour la rubrique (ex : « Rap FR », « Gaming », « Clash », « Sortie », « Politique »).
- "mots_cles" : 4 mots-clés très courts (12 caractères maximum chacun) : noms, lieu, chiffre, thème.
- "accroche_couv" : 2 à 4 mots au-dessus du titre (ex : « L'annonce du jour », « Le clash de la semaine »).
- "chiffre" : LE chiffre fort de l'info s'il est dans la source (ex : « ×5 », « 366 GO », « 1 M », « 2027 »), 8 caractères maximum ; "" s'il n'y en a pas.
- "chiffre_texte" : 4 à 10 mots qui expliquent ce chiffre (ou, sans chiffre, qui résument l'info).
- "slides" : 2 à 4 slides pour la suite du carrousel, dans l'ordre logique. Chaque slide : "rubrique" (2 à 4 mots, ex : « Le déclic », « Les chiffres », « Ce qu'il a dit », « Et maintenant »), soit "gros" (un chiffre ou une date de la source, 6 caractères maximum, ex : « 2024 », « 23 », « 8 500 »), soit "gros_haut" + "gros_bas" (2 lignes courtes de 14 caractères maximum chacune quand il n'y a pas de chiffre), "sous_titre" (2 à 5 mots qui expliquent le gros texte) et "texte" (15 à 30 mots, les faits). Pour un récap de sorties, une slide par sortie (artiste en "gros_haut", titre en "gros_bas").
- "question_haut" et "question_bas" : une question au lecteur coupée en 2 lignes courtes (ex : « Tu t'y » / « attendais ? », « Et toi, tu danserais » / « en plein marathon ? »). Neutre, jamais d'opinion politique.
- "accroche_reel_haut" et "accroche_reel_bas" : l'accroche du Reel en 2 lignes de 18 caractères maximum, la plus intrigante possible (ex : « 7 heures de course » / « et c'est lui la star »).
- "accroche" : 1 phrase pour la légende Instagram, avec 1 emoji maximum.
- "hashtags" : 2 ou 3 hashtags précis sur le sujet (nom du jeu, de l'artiste…), sans espace, en minuscules.
- "voix_off" : le texte lu par la voix du Reel, écrit pour l'oral comme une créatrice de contenu qui raconte l'info à ses abonnés : 35 à 55 mots, phrases courtes, du « tu ». Commence par une accroche forte (une question ou un fait surprenant), raconte l'essentiel avec les vrais faits, et termine par la même question au spectateur que "question_haut" + "question_bas".
- "visuels" : 1 ou 2 sujets à montrer en photo, du plus important au moins important. Chaque sujet : "type" = "personne", "artiste" (musicien), "jeu" (jeu vidéo) ou "autre", et "nom" = le nom exact et complet (ex : « Teddy Riner », « Ninho », « God of War Ragnarök »).
- "faisable" : false si la source ne contient pas assez d'info pour faire un post fiable, sinon true.

Réponds UNIQUEMENT en JSON : {{"titre": "", "titre_haut": "", "titre_bas": "", "mot_cle": "", "rubrique": "", "mots_cles": [], "accroche_couv": "", "chiffre": "", "chiffre_texte": "", "slides": [{{"rubrique": "", "gros": "", "gros_haut": "", "gros_bas": "", "sous_titre": "", "texte": ""}}], "question_haut": "", "question_bas": "", "accroche_reel_haut": "", "accroche_reel_bas": "", "accroche": "", "hashtags": [], "voix_off": "", "visuels": [{{"type": "", "nom": ""}}], "faisable": true}}"""


def rediger(cand, image_jpeg=None):
    theme = "jeux vidéo" if cand["categorie"] == "GAMING" else "rap français"
    parts = [{"text": PROMPT_REDAC.format(
        theme=theme, source=cand["source"], titre=cand["titre"], texte=cand["texte"][:5000],
        image=" et dans l'image jointe (lis le texte écrit dessus)" if image_jpeg else "")}]
    if image_jpeg:
        parts.append({"inline_data": {"mime_type": "image/jpeg",
                                      "data": base64.b64encode(image_jpeg).decode()}})
    res = valider(appel(parts), cand)
    if manque_accents(res):           # Gemini recopie parfois une source écrite sans accents ni apostrophes
        JOURNAL.append("texte sans accents ou sans apostrophes : réécriture demandée")
        parts[0] = {"text": parts[0]["text"] + "\n\nATTENTION : la source est mal orthographiée. Écris en "
                    "français impeccable : tous les accents (é, è, à, ç…) et toutes les apostrophes "
                    "(l’artiste, n’a, s’est, d’humour), y compris dans le titre et les noms (Cédric)."}
        plus_fort = [m for m in config.GEMINI_MODELES if "lite" not in m] + config.GEMINI_MODELES
        try:
            res2 = valider(appel(parts, list(dict.fromkeys(plus_fort))), cand)
            if not manque_accents(res2) or _defauts(res2) < _defauts(res):
                res = res2
        except ErreurIA:
            pass
    return accents_manquants(apostrophes(res), cand)


_ELISION = re.compile(r"\b(qu|[ldnsjmtcLDNSJMTC]|Qu|QU) (?=[aeiouyhéèêàâîôûAEIOUYHÉÈÊÀÂÎÔÛ])")


CHAMPS_TEXTE = ("titre", "titre_haut", "titre_bas", "mot_cle", "accroche_couv", "chiffre_texte", "question_haut",
                "question_bas", "accroche_reel_haut", "accroche_reel_bas", "voix_off")
CHAMPS_SLIDE = ("rubrique", "gros_haut", "gros_bas", "sous_titre", "texte")


def _champs(res):
    return [res.get(k, "") for k in ("titre", "voix_off")] + [s["texte"] for s in res["sections"]]


def _corriger_tout(res, fix):
    """Applique une correction de texte à tous les textes affichés ou lus du post."""
    for k in CHAMPS_TEXTE:
        if isinstance(res.get(k), str):
            res[k] = fix(res[k])
    res["mots_cles"] = [fix(m) for m in res.get("mots_cles", [])]
    for sl in res.get("slides", []):
        for k in CHAMPS_SLIDE:
            if isinstance(sl.get(k), str):
                sl[k] = fix(sl[k])
    for sec in res.get("sections", []):
        sec["texte"], sec["titre"] = fix(sec["texte"]), fix(sec["titre"])
    return res


def _defauts(res):
    texte = " ".join(_champs(res))
    lettres = sum(c.isalpha() for c in texte) or 1
    accents = sum(c in ACCENTS for c in texte)
    return len(_ELISION.findall(texte)) + (5 if accents / lettres < 0.008 else 0)


def _sans_accent(mot):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", mot) if unicodedata.category(c) != "Mn")


_AMBIGUS = {"cote", "marche", "peche", "tache", "sale", "mais", "jeune", "eleve", "pecher", "retraite", "ferme"}


def accents_manquants(res, cand=None):
    """Remet les accents oubliés sur un mot (souvent un nom ou le titre) quand le même mot apparaît
    ailleurs correctement accentué (« pitie » → « pitié », « Cedric » → « Cédric »)."""
    corpus = " ".join(_champs(res) + [s["titre"] for s in res["sections"]]
                      + [res.get(k, "") for k in CHAMPS_TEXTE if isinstance(res.get(k), str)])
    connus = {}
    for m in re.findall(r"[\wÀ-ÿ’'-]+", corpus):
        if any(c in ACCENTS for c in m) and len(m) >= 4:
            connus.setdefault(_sans_accent(m).lower(), m.lower())

    def fix(texte):
        def remplace(mt):
            m = mt.group(0)
            cle = m.lower()
            if len(m) < 4 or cle in _AMBIGUS or any(c in ACCENTS for c in m) or cle not in connus:
                return m
            bon = connus[cle]
            if m.isupper():
                return bon.upper()
            return bon[0].upper() + bon[1:] if m[0].isupper() else bon
        return re.sub(r"[\wÀ-ÿ]+", remplace, texte)

    return _corriger_tout(res, fix)


def apostrophes(res):
    """Dernier filet : « n a » → « n’a », « L artiste » → « L’artiste »."""
    return _corriger_tout(res, lambda t: _ELISION.sub(lambda m: m.group(1) + "’", t))


ACCENTS = set("éèêëàâäîïôöùûüçÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ")


def manque_accents(res):
    """Vrai si le texte est visiblement mal orthographié : presque pas d'accents (moins de 0,8 % des lettres,
    alors qu'un texte français en a 2 à 4 %) ou des apostrophes manquantes (« n a », « s est »)."""
    texte = " ".join(_champs(res))
    return len(texte.split()) >= 25 and _defauts(res) > 0


FIN_VOIX = "Abonne-toi à C’est tombé."
VOIX_MOTS_MAX = 60


def raccourcir_voix(texte, question=""):
    """La voix off reste courte : au-delà de VOIX_MOTS_MAX mots, on garde les premières phrases.
    Elle finit par la question au spectateur si on l'a, sinon par l'appel à s'abonner."""
    texte = re.sub(r"\s*Abonne-toi à C[’']est tombé[^.!?]*[.!?]?\s*$", "", texte.strip())
    phrases = re.split(r"(?<=[.!?…])\s+", texte)
    finit_par_question = phrases and phrases[-1].endswith("?")
    fin = phrases.pop() if finit_par_question and len(phrases) > 1 else (question or FIN_VOIX)
    garde, n = [], 0
    for p in phrases:
        if garde and n + len(p.split()) > VOIX_MOTS_MAX - len(fin.split()):
            break
        garde.append(p)
        n += len(p.split())
    return (" ".join(garde).strip() + " " + fin).strip()


def valider(rep, cand):
    """Contrôle et nettoie la réponse de l'IA. Lève ErreurIA si inutilisable."""
    if isinstance(rep, list):   # parfois Gemini renvoie [ {...} ]
        rep = next((r for r in rep if isinstance(r, dict)), {})
    if not isinstance(rep, dict):
        raise ErreurIA("réponse IA dans un format inattendu")
    if not rep.get("faisable", True):
        raise ErreurIA("source trop pauvre selon l'IA")
    titre = (rep.get("titre") or "").strip().rstrip(".")
    slides = [_slide(x) for x in rep.get("slides", []) if isinstance(x, dict) and (x.get("texte") or "").strip()]
    if not slides:   # ancien format (sections)
        slides = [_slide({"rubrique": x.get("titre"), "gros_haut": x.get("titre"), "texte": x.get("texte")})
                  for x in rep.get("sections", []) if isinstance(x, dict) and (x.get("texte") or "").strip()]
    sections = [{"titre": sl["rubrique"] or "Les détails", "texte": sl["texte"]} for sl in slides]
    if not titre or not sections:
        raise ErreurIA("réponse incomplète (titre ou slides manquants)")
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
    voix_off = (rep.get("voix_off") or "").strip()
    if len(voix_off.split()) < 12:      # secours : on lit le titre et la première phrase
        premiere = re.split(r"(?<=[.!?])\s+", sections[0]["texte"].strip())[0]
        voix_off = f"{titre}. {premiere} {FIN_VOIX}"
    q1, q2 = _court(rep.get("question_haut"), 26) or "Et toi,", _court(rep.get("question_bas"), 26) or "t'en penses quoi ?"
    voix_off = raccourcir_voix(voix_off, f"{q1} {q2}".strip())
    visuels = [{"type": str(v.get("type") or "autre"), "nom": str(v["nom"]).strip()}
               for v in (rep.get("visuels") or []) if isinstance(v, dict) and v.get("nom")][:2]
    haut, bas = _court(rep.get("titre_haut"), 26), _court(rep.get("titre_bas"), 26)
    if not haut or not bas:
        haut, bas = couper_titre(titre)
    defaut_rubrique = {"GAMING": "Gaming", "RAP FR": "Rap FR"}.get(cand["categorie"], "Actu")
    mots_cles = [_court(m, 16) for m in (rep.get("mots_cles") or []) if _court(m, 16)][:4]
    chiffre = _court(rep.get("chiffre"), 9)
    return {"titre": titre, "mot_cle": mot_cle, "voix_off": voix_off[:700], "visuels": visuels,
            "sections": sections[:4], "slides": slides[:4], "legende": legende[:2200],
            "titre_haut": haut, "titre_bas": bas, "rubrique": _court(rep.get("rubrique"), 18) or defaut_rubrique,
            "mots_cles": mots_cles, "accroche_couv": _court(rep.get("accroche_couv"), 30),
            "chiffre": chiffre, "chiffre_texte": _court(rep.get("chiffre_texte"), 80),
            "question_haut": q1, "question_bas": q2,
            "accroche_reel_haut": _court(rep.get("accroche_reel_haut"), 24) or haut,
            "accroche_reel_bas": _court(rep.get("accroche_reel_bas"), 24) or bas}


MOTS_VIDES = {"et", "ou", "de", "du", "des", "la", "le", "les", "un", "une", "dans", "sur", "à", "au", "aux", "pour",
              "avec", "en", "qui", "que", "son", "sa", "ses", "leur", "leurs", "par", "mais", "car", "ce", "cette",
              "ces", "il", "elle", "ils", "elles", "on", "se", "ne", "pas", "plus", "très", "après", "avant", "chez",
              "vers", "sans", "sous", "entre", "dont", "où", "lors", "son", "notre", "votre", "mon", "ma", "mes"}


def _court(texte, n):
    """Texte nettoyé ; trop long → coupé au dernier mot entier."""
    t = re.sub(r"\s+", " ", str(texte or "")).strip()
    if len(t) <= n:
        return t
    coupe = t[:n]
    # d'abord à une fin de phrase ou de proposition, si elle garde au moins la moitié du texte
    fin = max(coupe.rfind(x) for x in (". ", " — ", " : ", ", ", " ; ", "! ", "? ", " et ", " mais ", " qui ",
                                         " alors ", " avant ", " après ", " pour "))
    if fin >= n // 2:
        return coupe[:fin].rstrip(" ,;:—")
    coupe = coupe.rsplit(" ", 1)[0] if " " in coupe else coupe
    mots = coupe.split()
    while len(mots) > 2 and (mots[-1].lower().strip(",;:") in MOTS_VIDES or mots[-1].endswith("'")):
        mots.pop()                    # jamais « … dans un documentaire et »
    return " ".join(mots).rstrip(",;:")


def couper_titre(titre):
    """Coupe un titre en 2 lignes équilibrées (au « : » ou à la virgule s'il y en a)."""
    for sep in (" : ", ": ", ", "):
        if sep in titre:
            a, b = titre.split(sep, 1)
            if 3 <= len(a) <= 26 and 3 <= len(b) <= 26:
                return a.strip() + ("," if sep == ", " else ""), b.strip()
    mots = titre.split()
    meilleur = (99, titre, "")
    for i in range(1, len(mots)):
        a, b = " ".join(mots[:i]), " ".join(mots[i:])
        ecart = max(len(a), len(b))
        if ecart < meilleur[0]:
            meilleur = (ecart, a, b)
    return meilleur[1], meilleur[2]


def _slide(x):
    gros = _court(x.get("gros"), 8)
    gh, gb = _court(x.get("gros_haut"), 18), _court(x.get("gros_bas"), 18)
    if gros and not re.search(r"\d", gros) and not gb:   # « gros » sans chiffre : il passe en titre 2 lignes
        gh, gros = gros, ""
    if not gros and gh and not gb:
        gh, gb = couper_titre(gh) if len(gh) > 10 else (gh, "")
    return {"rubrique": _court(x.get("rubrique"), 30), "gros": gros, "gros_haut": gh, "gros_bas": gb,
            "sous_titre": _court(x.get("sous_titre"), 34), "texte": _court(x.get("texte"), 260)}
