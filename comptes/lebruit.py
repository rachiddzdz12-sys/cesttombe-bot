"""Réglages du compte LE BRUIT (@le.bruit.rap) : média rap. Appliqués par-dessus config.py quand COMPTE=lebruit.
Tout ce qui n'est pas écrit ici reste comme pour C'EST TOMBÉ (voix, contrôle des voix, technique…)."""

REGLAGES = {
    "NOM_PAGE": "LE BRUIT",
    "HANDLE": "@le.bruit.rap",
    "IG_USER_ID": "17841439323487258",       # identifiant Instagram du compte (pas un secret)
    "DA": "bruit",                           # carrousels et Reels dans la DA LE BRUIT (noir, violet, logo B)
    # interrupteur propre à ce compte : False tant que les rendus n'ont pas été validés
    "PUBLICATION_AUTO": True,
    # ligne éditoriale : 100 % rap
    "CATEGORIES": ["RAP FR"],
    "THEME": "",
    "SOURCES_WEB": [],
    "COMPTES_IG": [],
    "COMPTES_RAP": ["rap.minute", "rapfractusofficiel", "booska_p"],
    "COMPTES_X": [
        {"compte": "RapFrActus", "categorie": "RAP FR", "lang": "fr"},
        {"compte": "FrenchRapUS", "categorie": "RAP FR", "lang": "fr"},
        {"compte": "Rapunchline", "categorie": "RAP FR", "lang": "fr"},
        {"compte": "SpotifyFrance", "categorie": "RAP FR", "lang": "fr"},   # tops de la semaine (classements)
    ],
    "X_PLAFOND_MOIS": 9000,                  # avec les 9000 de C'EST TOMBÉ : reste dans les 5 $ offerts par Apify
    # rythme
    "POSTS_PAR_JOUR": 4,                     # démarrage en douceur (et voix Gemini : 16 C'EST TOMBÉ + 4 ≈ quota)
    "HEURE_DEBUT": 11,                       # ~11h, 14h30, 18h, 21h30 : l'après-midi et le soir, quand le rap tourne
    "HEURE_FIN": 23,
    "ECART_MIN_MINUTES": 210,
    "LANCEMENT_JUSQUA": None,
    "RATTRAPAGE_JUSQUA": None,
    "SCORE_MIN": 6,
    "HASHTAGS": {"RAP FR": ["#rapfr", "#rapfrancais", "#actusrap", "#hiphopfrancais", "#rap"]},
    "PROMESSE": "toute l'actu rap",
    "ENVOIE_A": "écoute du rap FR",
    # rubriques de la DA (petit titre en haut de chaque carte)
    "CONSIGNES_TRI": """
PAGE 100 % RAP : seules comptent les infos sur le rap et le hip-hop (artistes, sons, albums, clips, concerts,
classements, chiffres de streaming, clashs, interviews, business du rap). Tout le reste (sport, MMA, foot,
jeux vidéo, économie, faits divers sans rappeur, K-pop, variété, pop) = score 0, info « pas une news ».
Une vidéo ou un tweet vague sans fait précis (« il est vraiment fort », « regardez ça ») = score 3 maximum.
""",
    "CONSIGNES_REDAC": ("\nPAGE LE BRUIT (média rap, « Plus qu'une actu, une culture ») : pour \"rubrique\", choisis "
                        "EXACTEMENT une de ces rubriques : Breaking news, Sorties, Classements, Artiste, Culture, "
                        "Industrie, Interview, Clash. Pour \"visuels\", un rappeur ou un groupe est de type "
                        "\"artiste\" (jamais \"personne\").\n"),
}
