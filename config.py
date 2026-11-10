"""Réglages de C'EST TOMBÉ. C'est le seul fichier à modifier pour changer le comportement du bot."""
import os

# ------------------------------------------------------------------ interrupteur
PUBLICATION_AUTO = True       # True = le bot publie tout seul toutes les 30 min
PAUSE = False                 # True = arrêt d'urgence : plus aucune publication automatique, quoi qu'il arrive

# ------------------------------------------------------------------ vidéos des sources
VIDEOS = True                 # si la source a une vidéo, elle devient la slide 2 du carrousel

# ------------------------------------------------------------------ Reels
REELS = True                  # publie aussi un Reel avec voix off pour chaque info
REEL_DANS_LE_FEED = False     # False = le Reel va dans l'onglet Reels, le carrousel reste seul dans la grille
VOIX = "gemini:Aoede"           # voix Gemini (très naturelle) ; si elle ne répond pas : VOIX_SECOURS (edge-tts)
VOIX_VITESSE = "+8%"
VOIX_SECOURS = "fr-FR-DeniseNeural"   # voix edge-tts utilisée si la voix Gemini ne répond pas
# Voix Gemini (VOIX = "gemini:<nom>") : ton demandé à la voix, avant le texte
VOIX_CONSIGNE = (
    "Synthesize speech for the transcript below. Everything before #### TRANSCRIPT is direction only: do NOT "
    "speak it, do NOT add, remove or change any word. Read the transcript exactly as written, in French.\n\n"
    "### DIRECTION\nVoice of a 26-year-old French woman who runs a popular news page on Instagram and TikTok, "
    "recording on her phone close to the microphone. Natural and conversational, like telling a friend some news, "
    "with a slight smile in the voice. Lively but relaxed, real breaths between sentences, quick rhythm with small "
    "pauses before the key facts. Native Parisian French. Never robotic, never over-acted.\n\n#### TRANSCRIPT\n")
VOIX_GEMINI_TEMPO = 1.0
# chaque modèle a son propre quota gratuit par jour : si le premier est épuisé, on passe au suivant
GEMINI_TTS_MODELES = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"]
# traitement « studio » de la voix : coupe le bas, un peu de chaleur, de la présence, de-esser, compression
VOIX_TRAITEMENT = ("highpass=f=80,equalizer=f=220:t=q:w=1:g=1.5,equalizer=f=3800:t=q:w=1.2:g=3,deesser=i=0.35,"
                   "acompressor=threshold=-20dB:ratio=3:attack=5:release=90:makeup=3")
MUSIQUE = "musique/fond.mp3"  # instru de fond de chaque Reel (laisser vide "" pour aucune)
MUSIQUE_VOLUME = 0.14         # 0.14 ≈ -17 dB : la musique accompagne, la voix reste devant
MUSIQUE_DEBUT = 0             # secondes à sauter au début de l'instru (intro trop calme, par ex.)
VOIX_A_TESTER = ["gemini:Aoede", "gemini:Leda", "gemini:Despina", "gemini:Callirrhoe", "gemini:Sulafat",
                 "gemini:Kore", "fr-FR-DeniseNeural"]

# ------------------------------------------------------------------ rythme
POSTS_PAR_JOUR = 6
# Rattrapage après une coupure : jusqu'à cette date (heure de Paris), le bot poste plus souvent et accepte
# des infos plus anciennes, pour couvrir ce qu'il a raté. Mettre None pour le désactiver.
RATTRAPAGE_JUSQUA = "2026-11-11T12:00"
RATTRAPAGE = {"posts_par_jour": 10, "ecart_min": 50, "facteur_age": 3, "score_min": 5}
X_FACTEUR_RECUL = 1          # réglé par le bot pendant un rattrapage            # total gaming + rap
HEURE_DEBUT = 9               # heure de Paris, premier post possible
HEURE_FIN = 23                # heure de Paris, plus aucun post après
ECART_MIN_MINUTES = 120       # temps minimum entre deux posts
SCORE_MIN = int(os.environ.get("SCORE_MIN") or 6)                 # note mini (sur 10) donnée par l'IA pour qu'une info soit publiée
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
COMPTES_X = ["RapFrActus", "FrenchRapUS"]
APIFY_ACTEUR = "kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest"
X_MAX_TWEETS = 15           # par compte et par lecture (Apify facture au tweet)
# un tweet qui parle de jeu vidéo part dans la catégorie GAMING (ex : @FrenchRapUS poste aussi sur GTA 6)
MOTS_GAMING = (r"\b(gta|ps5|ps4|playstation|xbox|nintendo|switch 2|steam|rockstar|jeu vid[ée]o|jeux vid[ée]o|"
               r"gaming|fortnite|call of duty|warzone|minecraft|ea sports|fc 2[0-9]|ubisoft|bethesda|"
               r"trailer du jeu|manette|console)\b")
X_PLAFOND_MOIS = 10000        # au-delà, plus aucune lecture X ce mois-ci (≈ 2,50 $ sur les 5 $ offerts)  # pseudos Instagram (comptes Pro), sans le @

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
