"""Réglages de C'EST TOMBÉ. C'est le seul fichier à modifier pour changer le comportement du bot."""
import os

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

COMPTES_RAP = ["rap.minute"]  # pseudos Instagram (comptes Pro), sans le @

# ------------------------------------------------------------------ identité
HANDLE = "@cesttombe"
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
GEMINI_MODELES = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-flash-latest",
                              "gemini-flash-lite-latest"] if m]
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
MAX_SLIDES = 10
