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
    "with a slight smile in the voice. Lively but relaxed, steady quick rhythm, natural short pauses at punctuation only. "
    "No sound effects, no laughing, no singing, no long silences. Native Parisian French. Never robotic, never over-acted.\n\n#### TRANSCRIPT\n")
# Essai d'une voix d'homme (VOIX_GENRE=homme, en MODE=test) : même direction, version masculine
VOIX_HOMME = "gemini:Charon"
VOIX_SECOURS_HOMME = "fr-FR-HenriNeural"
VOIX_CONSIGNE_HOMME = (VOIX_CONSIGNE.replace("26-year-old French woman", "27-year-old French man")
                       .replace("her phone", "his phone").replace("with a slight smile in the voice",
                                                                    "relaxed and confident, with a slight smile in the voice"))
VOIX_GEMINI_TEMPO = 1.0
# contrôle de chaque voix Gemini : réécoutée par une reconnaissance vocale et comparée au texte prévu
VOIX_ESSAIS = 3                 # voix refaite jusqu'à 3 fois ; ensuite, voix de secours (edge-tts)
VOIX_CONTROLE_MIN = 0.82        # ressemblance minimale entre ce qui est dit et le texte prévu
VOIX_BLANC_MAX = 1.1            # un blanc plus long au milieu de la voix = voix ratée
VOIX_CONTROLE_MODELE = "small"  # modèle faster-whisper (téléchargé une fois, gardé en cache)
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

# ------------------------------------------------------------------ ligne éditoriale
# C'EST TOMBÉ = page GTA : GTA 6 / GTA VI, GTA Online, Rockstar en priorité, plus les très grosses infos gaming.
# Le rap est coupé ici : il ira sur le futur compte rap.
CATEGORIES = ["GAMING"]          # catégories publiées par ce compte ("RAP FR" : coupé)
THEME = "GTA"                    # "GTA" = page GTA ; "" = page jeux vidéo classique
FILTRE_GTA = (r"\bgta\b|gta ?(6|vi|online|5|v)\b|grand theft auto|rockstar|vice city|leonida|"
              r"lucia caminos|jason duval|port gellhorn|grassrivers")
SCORE_MIN_HORS_GTA = 9           # une info gaming qui ne parle pas de GTA doit être énorme pour passer

# ------------------------------------------------------------------ rythme
POSTS_PAR_JOUR = 6
# Rattrapage après une coupure : jusqu'à cette date (heure de Paris), le bot poste plus souvent et accepte
# des infos plus anciennes, pour couvrir ce qu'il a raté. Mettre None pour le désactiver.
RATTRAPAGE_JUSQUA = "2026-11-11T12:00"
RATTRAPAGE = {"posts_par_jour": 10, "ecart_min": 50, "facteur_age": 3, "score_min": 5}
# Sortie de GTA 6 (19/11/2026) : jusqu'à cette date, beaucoup plus de posts pour couvrir toute l'actu.
LANCEMENT_JUSQUA = "2026-11-30T23:59"
LANCEMENT = {"posts_par_jour": 16, "ecart_min": 40, "score_min": 5, "heure_debut": 7, "heure_fin": 24}
X_FACTEUR_RECUL = 1          # réglé par le bot pendant un rattrapage            # total gaming + rap
HEURE_DEBUT = 9               # heure de Paris, premier post possible
HEURE_FIN = 23                # heure de Paris, plus aucun post après
ECART_MIN_MINUTES = 120       # temps minimum entre deux posts
SCORE_MIN = int(os.environ.get("SCORE_MIN") or 6)                 # note mini (sur 10) donnée par l'IA pour qu'une info soit publiée
AGE_MAX_HEURES = {"GAMING": 36, "RAP FR": 24}   # on ignore les infos plus vieilles
POOL_TRI = 25                    # infos les plus récentes données à l'IA à chaque passage

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

# Sources web GTA, toutes lues à chaque passage. "filtre": True = on ne garde que ce qui parle de GTA.
# "google": True = Google Actualités (lien à décoder pour lire l'article d'origine).
SOURCES_WEB = [
    {"nom": "GOOGLE ACTU", "url": "https://news.google.com/rss/search?q=%22GTA+6%22+OR+%22GTA+VI%22+OR+"
     "%22Grand+Theft+Auto+VI%22&hl=fr&gl=FR&ceid=FR:fr", "google": True},
    {"nom": "GOOGLE NEWS", "url": "https://news.google.com/rss/search?q=%22GTA+6%22+OR+%22GTA+VI%22+OR+"
     "%22Grand+Theft+Auto+VI%22&hl=en-US&gl=US&ceid=US:en", "google": True},
    {"nom": "BING ACTU", "url": "https://www.bing.com/news/search?q=%22GTA+6%22&format=rss&mkt=fr-FR&setlang=fr",
     "bing": True},
    {"nom": "BING ACTU VI", "url": "https://www.bing.com/news/search?q=%22GTA+VI%22&format=rss&mkt=fr-FR&setlang=fr",
     "bing": True},
    {"nom": "ROCKSTAR INTEL", "nom_legende": "Rockstar Intel", "url": "https://www.rockstarintel.com/feed"},
    {"nom": "DEXERTO", "nom_legende": "Dexerto", "url": "https://www.dexerto.com/gta/feed/"},
    {"nom": "GTA BOOM", "nom_legende": "GTA BOOM", "url": "https://www.gtaboom.com/feed"},
    {"nom": "GAMESRADAR", "nom_legende": "GamesRadar", "url": "https://www.gamesradar.com/feeds/tag/grand-theft-auto/"},
    {"nom": "GTABASE", "nom_legende": "GTABase", "url": "https://www.gtabase.com/news?format=feed"},
    {"nom": "GAMEKULT", "nom_legende": "Gamekult", "url": "https://www.gamekult.com/feed.xml", "filtre": True},
    {"nom": "IGN FRANCE", "nom_legende": "IGN France", "url": "https://fr.ign.com/feed.xml", "filtre": True},
    {"nom": "JEUXVIDEO.COM", "nom_legende": "Jeuxvideo.com", "url": "https://www.jeuxvideo.com/rss/rss.xml",
     "filtre": True},
    {"nom": "INSIDER GAMING", "nom_legende": "Insider Gaming", "url": "https://www.insider-gaming.com/feed/",
     "filtre": True},
]

# Comptes Instagram lus (API officielle, gratuit) et leur catégorie. "filtre": True = seulement GTA.
COMPTES_IG = [
    {"compte": "rockstargames", "categorie": "GAMING"},
    {"compte": "playstationfr", "categorie": "GAMING", "filtre": True},
]
COMPTES_RAP = ["rap.minute", "rapfractusofficiel", "booska_p"]   # pour le futur compte rap

# Comptes X (Twitter) lus via Apify (crédit gratuit de 5 $/mois, sans carte) — secret APIFY_TOKEN
# "lang": langue des tweets cherchés (None = toutes) ; "categorie" : forcée (sinon devinée)
COMPTES_X = [
    {"compte": "RockstarGames", "categorie": "GAMING", "lang": None},
    {"compte": "RockstarIntel", "categorie": "GAMING", "lang": None, "filtre": True},
]
COMPTES_X_RAP = ["RapFrActus", "FrenchRapUS"]                    # pour le futur compte rap
APIFY_ACTEUR = "kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest"
X_MAX_TWEETS = 10           # par compte et par lecture (Apify facture au tweet)
# un tweet qui parle de jeu vidéo part dans la catégorie GAMING (ex : @FrenchRapUS poste aussi sur GTA 6)
MOTS_GAMING = (r"\b(gta|ps5|ps4|playstation|xbox|nintendo|switch 2|steam|rockstar|jeu vid[ée]o|jeux vid[ée]o|"
               r"gaming|fortnite|call of duty|warzone|minecraft|ea sports|fc 2[0-9]|ubisoft|bethesda|"
               r"trailer du jeu|manette|console)\b")
X_PLAFOND_MOIS = 10000        # au-delà, plus aucune lecture X ce mois-ci (≈ 2,50 $ sur les 5 $ offerts)  # pseudos Instagram (comptes Pro), sans le @

# ------------------------------------------------------------------ identité
NOM_PAGE = "C'EST TOMBÉ"
DA = "v3"                     # "v3" = DA C'EST TOMBÉ (style 7run, lime) ; "bruit" = DA LE BRUIT
CONSIGNES_REDAC = ""          # consignes de rédaction propres au compte (ajoutées au prompt)
HANDLE = "@cesttombe.actu"
# 5 hashtags au plus (limite d'Instagram) : les 3 premiers de la liste + 2 précis sur le sujet (choisis par l'IA)
HASHTAGS = {
    "GAMING": ["#gta6", "#gtavi", "#rockstargames", "#grandtheftauto", "#gtaonline"],
    "GAMING_HORS_GTA": ["#jeuxvideo", "#gaming", "#actujv", "#gamer", "#jeuvideo"],
    "RAP FR": ["#rapfr", "#rapfrancais", "#actusrap", "#hiphopfrancais", "#rap"],
}
PROMESSE = "ne rien rater de GTA 6"     # « Abonne-toi à @… pour … » dans la légende
ENVOIE_A = "attend GTA 6"                # « Envoie ça à ton pote qui … » si l'IA n'a rien proposé

# ------------------------------------------------------------------ clé Gemini
# Utilisée seulement si le secret GitHub GEMINI_API_KEY n'existe pas.
# Ne rends jamais ce dépôt public tant que la clé est écrite ici.
GEMINI_API_KEY_DANS_LE_CODE = ""  # vide : la clé est dans le secret GitHub GEMINI_API_KEY

# ------------------------------------------------------------------ technique
GRAPH = "https://graph.facebook.com/v25.0"
# flash-lite d'abord : rapide et rarement saturé ; flash en secours ; puis des modèles nommés, car les alias
# « -latest » peuvent rester saturés des heures (16/11 : 503 de 15h à 18h, plus aucun post sur les 2 pages)
GEMINI_MODELES = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-flash-lite-latest", "gemini-flash-latest",
                              "gemini-3.5-flash-lite", "gemini-3-flash-preview", "gemini-3.1-flash-lite",
                              "gemini-3.5-flash"] if m]
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
MAX_SLIDES = 10
