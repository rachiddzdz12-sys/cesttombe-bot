"""Réglages de C'EST TOMBÉ. C'est le seul fichier à modifier pour changer le comportement du bot."""
import os

# ------------------------------------------------------------------ interrupteur
PUBLICATION_AUTO = True       # True = le bot publie tout seul toutes les 30 min

# ------------------------------------------------------------------ Reels
REELS = True                  # publie aussi un Reel avec voix off pour chaque info
REEL_DANS_LE_FEED = False     # False = le Reel va dans l'onglet Reels, le carrousel reste seul dans la grille
VOIX = "fr-FR-DeniseNeural"     # autres voix : fr-FR-RemyMultilingualNeural, fr-FR-DeniseNeural, fr-FR-VivienneMultilingualNeural
VOIX_VITESSE = "+8%"
MUSIQUE = "musique/fond.mp3"  # instru de fond de chaque Reel (laisser vide "" pour aucune)
MUSIQUE_VOLUME = 0.14         # 0.14 ≈ -17 dB : la musique accompagne, la voix reste devant
MUSIQUE_DEBUT = 0             # secondes à sauter au début de l'instru (intro trop calme, par ex.)
VOIX_A_TESTER = ["fr-FR-VivienneMultilingualNeural", "fr-FR-DeniseNeural", "fr-FR-EloiseNeural",
                 "fr-FR-RemyMultilingualNeural"]

# ------------------------------------------------------------------ rythme
POSTS_PAR_JOUR = 6            # total gaming + rap
HEURE_DEBUT = 9               # heure de Paris, premier post possible
HEURE_FIN = 23                # heure de Paris, plus aucun post après
ECART_MIN_MINUTES = 120       # temps minimum entre deux posts
SCORE_MIN = 6                 # note mini (sur 10) donnée par l'IA pour qu'une info soit publiée
AGE_MAX_HEURES = {"GAMING": 48, "RAP FR": 24}   # on ignore les infos plus vieilles

# ------------------------------------------------------------------ sources
GAMING = {
    "nom": "ACTUGAMING",          # affiché sur les slides
    "nom_legende": "ActuGaming",  # affiché dans la légende
    # essayés dans l'ordre : flux de la rubrique, puis flux général filtré
    "flux": [
        "https://www.actugaming.net/actualites/feed/",
        "https://www.actugaming.net/feed/",
    ],
    "page_secours": "https://www.actugaming.net/actualites/",
    "categories_ok": ["actualités", "actualites", "news"],
    "categories_exclues": ["soluces", "soluce", "astuces", "guides", "guide d'achat",
                           "guides d'achat", "bons plans", "bon plan", "tests", "test"],
    # titres écartés d'office (articles pratiques, pas de l'actu)
    "titres_exclus": ["où l'acheter", "où l’acheter", "meilleur prix", "durée de vie",
                      "comment débloquer", "soluce", "astuce", "code promo", "bon plan",
                      "guide d'achat", "guide d’achat"],
}

COMPTES_RAP = ["rap.minute", "rapfractusofficiel"]

# Comptes X (Twitter) rap, lus via Apify (crédit gratuit de 5 $/mois, sans carte) — secret APIFY_TOKEN
COMPTES_X = ["RapFrActus"]
APIFY_ACTEUR = "kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest"
X_MAX_TWEETS = 20  # pseudos Instagram (comptes Pro), sans le @

# ------------------------------------------------------------------ identité
HANDLE = "@cesttombe.actu"
HASHTAGS = {
    "GAMING": ["#jeuxvideo", "#gaming", "#actujv", "#gamer", "#cesttombe"],
    "RAP FR": ["#rapfr", "#rapfrancais", "#actusrap", "#hiphopfrancais", "#cesttombe"],
}

# ------------------------------------------------------------------ clé Gemini
# Utilisée seulement si le secret GitHub GEMINI_API_KEY n'existe pas.
# Ne rends jamais ce dépôt public tant que la clé est écrite ici.
GEMINI_API_KEY_DANS_LE_CODE = ""  # vide : la clé est dans le secret GitHub GEMINI_API_KEY

# ------------------------------------------------------------------ technique
GRAPH = "https://graph.facebook.com/v25.0"
# flash-lite d'abord : rapide et rarement saturé ; flash en secours
GEMINI_MODELES = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-flash-lite-latest",
                              "gemini-flash-latest"] if m]
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
MAX_SLIDES = 10
