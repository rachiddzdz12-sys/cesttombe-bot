"""Tests hors ligne : tout ce qui peut être vérifié sans clés ni accès aux sites.

Lancer depuis la racine du projet : python tests/test_local.py
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from PIL import Image  # noqa: E402

import config  # noqa: E402
import main  # noqa: E402
from bot import hebergement, ia, images, instagram, rendu, sources  # noqa: E402

OK = []


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    OK.append(msg)


# ------------------------------------------------------------------ 1. flux RSS
now = datetime.now(timezone.utc)
rfc = lambda d: d.strftime("%a, %d %b %Y %H:%M:%S +0000")
FLUX = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>ActuGaming</title><link>https://www.actugaming.net</link><description>x</description>
<item><title>NieR Automata : Une erreur fait passer le poids du jeu à 366 Go sur Steam</title>
<link>https://www.actugaming.net/nier-366-go/</link><guid isPermaLink="false">https://www.actugaming.net/?p=1</guid>
<pubDate>{rfc(now - timedelta(hours=3))}</pubDate><category><![CDATA[Actualités]]></category>
<description><![CDATA[<p>Le jeu demande désormais 366 Go.</p>]]></description>
<content:encoded><![CDATA[<p>Une mise à jour Steam a fait grimper l'espace requis.</p><img src="https://img.example/inline.jpg"/>]]></content:encoded>
<media:content url="https://img.example/nier.jpg" medium="image"><media:credit>Square Enix</media:credit></media:content>
</item>
<item><title>Niveau du monde 5 Seven Deadly Sins Origin : comment le débloquer ?</title>
<link>https://www.actugaming.net/soluce/</link><guid>https://www.actugaming.net/?p=2</guid>
<pubDate>{rfc(now - timedelta(hours=4))}</pubDate><category><![CDATA[Soluces]]></category>
<description>x</description></item>
<item><title>Durée de vie Zelda Ocarina of Time Switch 2 : combien de temps pour finir le jeu ?</title>
<link>https://www.actugaming.net/duree/</link><guid>https://www.actugaming.net/?p=3</guid>
<pubDate>{rfc(now - timedelta(hours=5))}</pubDate><category><![CDATA[Actualités]]></category>
<description>x</description></item>
<item><title>Test de Machin : notre avis</title>
<link>https://www.actugaming.net/test/</link><guid>https://www.actugaming.net/?p=4</guid>
<pubDate>{rfc(now - timedelta(hours=6))}</pubDate><category><![CDATA[Tests]]></category>
<description>x</description></item>
</channel></rss>"""

items = sources.entrees_depuis_flux(FLUX.encode(), filtrer_rubrique=True)
check(len(items) == 1, "flux : soluce, test et article « durée de vie » écartés")
it = items[0]
check(it["images"][0] == "https://img.example/nier.jpg", "flux : image media:content récupérée en premier")
check("https://img.example/inline.jpg" in it["images"], "flux : images du texte gardées en secours")
check(it["credit"] == "Square Enix", "flux : crédit photo récupéré")
check(2.5 < sources.age_heures(it, now) < 3.5, "flux : âge de l'info calculé")

GNEWS = f"""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>GTA 6 - Google Actualités</title>
<item><title>GTA 6 : Rockstar dévoile l'heure de sortie exacte - Gamekult</title>
<link>https://news.google.com/rss/articles/CBMiXYZ?oc=5</link><guid>CBMiXYZ</guid>
<pubDate>{rfc(now - timedelta(hours=1))}</pubDate><description>&lt;a href="x"&gt;GTA 6&lt;/a&gt;</description>
<source url="https://www.gamekult.com">Gamekult</source></item>
<item><title>Le nouveau Zelda bat un record - Jeuxvideo.com</title><link>https://news.google.com/rss/articles/CBMiABC</link>
<guid>CBMiABC</guid><pubDate>{rfc(now - timedelta(hours=2))}</pubDate><source url="https://www.jeuxvideo.com">Jeuxvideo.com</source></item>
</channel></rss>"""
g = sources.entrees_web(GNEWS.encode(), {"nom": "GOOGLE ACTU", "url": "x", "google": True})
check(len(g) == 2 and g[0]["titre"] == "GTA 6 : Rockstar dévoile l'heure de sortie exacte",
      "Google Actualités : « - Média » retiré du titre")
check(g[0]["source_legende"] == "Gamekult" and g[0]["google"] and g[0]["a_lire"],
      "Google Actualités : le vrai média est affiché, article lu seulement s'il est choisi")
BING = f"""<?xml version="1.0" encoding="utf-8"?><rss version="2.0" xmlns:News="https://www.bing.com:443/news/search?q=x&amp;format=rss"><channel><title>Bing</title>
<item><title>GTA 6 : les congés posés pour la sortie explosent</title>
<link>http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;aid=&amp;tid=1&amp;url=https%3a%2f%2fwww.presse-citron.net%2fgta-6-conges%2f&amp;c=1</link>
<description>Les demandes de congés bondissent de 35 %.</description><pubDate>{rfc(now - timedelta(hours=2))}</pubDate>
<News:Source>Presse-citron.net</News:Source></item></channel></rss>"""
b = sources.entrees_web(BING.encode(), {"nom": "BING ACTU", "url": "x", "bing": True})
check(b and b[0]["lien"] == "https://www.presse-citron.net/gta-6-conges/" and b[0]["source_legende"] == "Presse-citron.net",
      "Bing Actualités : lien direct vers l'article et vrai média")
filtre = sources.entrees_web(GNEWS.encode(), {"nom": "JV", "url": "x", "filtre": True})
check(len(filtre) == 1 and sources.est_gta(filtre[0]), "source filtrée : seules les infos GTA sont gardées")
check(sources.est_gta({"titre": "Grand Theft Auto VI : la carte de Leonida"}) and
      not sources.est_gta({"titre": "Gratuit cette semaine sur l'Epic Games Store"}), "filtre GTA : reconnaît GTA 6 / Leonida")
check(sources.texte_article("<html><article><p>" + "GTA 6 sort le 19 novembre sur PS5 et Xbox Series. " * 3
                            + "</p><p>court</p></article></html>").startswith("GTA 6 sort"),
      "article : texte principal extrait")

# ------------------------------------------------------------------ 2. validation de la réponse IA
rep = {"titre": "NieR Automata pèse soudain 366 Go sur Steam.", "mot_cle": "366 go",
       "sections": [{"titre": "Ce qui se passe", "texte": "Texte."}, {"titre": "Vide", "texte": "  "}],
       "accroche": "Ton disque dur va pleurer 😳", "hashtags": ["NieR Automata", "#steam"], "faisable": True}
v = ia.valider(rep, it)
check(v["titre"] == "NieR Automata pèse soudain 366 Go sur Steam", "IA : point final retiré du titre")
check(v["mot_cle"] == "366 Go", "IA : mot clé recalé sur la casse du titre")
check(len(v["sections"]) == 1, "IA : section vide ignorée")
check("#nierautomata" in v["legende"] and "Source : ActuGaming" in v["legende"], "IA : légende assemblée")
try:
    ia.valider({"faisable": False}, it)
    check(False, "IA : source pauvre refusée")
except ia.ErreurIA:
    OK.append("IA : source pauvre refusée")
v2 = ia.valider({"titre": "GTA 6 arrive", "mot_cle": "inexistant", "sections": [{"titre": "a", "texte": "b"}]}, it)
check(v2["mot_cle"] == "", "IA : mot clé absent du titre → ignoré")
check(ia._extraire_json('```json\n{"a": 1}\n```') == {"a": 1}, "IA : JSON entouré de ``` accepté")
check(ia.valider([rep], it)["mot_cle"] == "366 Go", "IA : réponse de rédaction en liste acceptée")
check(ia.manque_accents({"titre": "Maes est libere de prison apres 22 mois",
                         "sections": [{"titre": "x", "texte": " ".join(["il retrouve sa liberte apres"] * 6)}]}),
      "IA : texte sans accents détecté")
check(not ia.manque_accents(v), "IA : texte normal accepté")
_appel_orig = ia.appel
ia.appel = lambda parts: [{"id": 1, "info": True, "score": 7, "doublon": False}]
check(ia.trier([it], [])[it["id"]]["score"] == 7, "IA : tri renvoyé en liste nue accepté")
ia.appel = lambda parts: {"items": [{"id": "1", "info": True, "score": 5}]}
check(ia.trier([it], [])[it["id"]]["score"] == 5, "IA : tri sous une autre clé accepté")
ia.appel = _appel_orig

# ------------------------------------------------------------------ 3. rendu (DA v3)
import subprocess  # noqa: E402
from bot import da3, placement, reel3, video as vid  # noqa: E402
out = Path(tempfile.mkdtemp())
photo = Image.new("RGB", (1600, 900), "#3B4A6B")
long_txt = " ".join(["Une phrase de test pour remplir la slide et vérifier la mise en page."] * 3)
rep3 = {"titre": "NieR Automata pèse soudain 366 Go sur Steam", "titre_haut": "NieR Automata",
        "titre_bas": "pèse 366 Go", "mot_cle": "366 Go", "rubrique": "Gaming",
        "mots_cles": ["Steam", "NieR", "Bug", "366 Go"], "accroche_couv": "Le jeu le plus lourd de Steam",
        "chiffre": "366 Go", "chiffre_texte": "c'est le poids affiché sur Steam",
        "slides": [{"rubrique": "Le bug", "gros": "366 Go", "sous_titre": "au lieu de 50", "texte": long_txt},
                   {"rubrique": "Le studio", "gros_haut": "Le studio", "gros_bas": "enquête",
                    "texte": "Le studio enquête."}],
        "question_haut": "Tu l'aurais", "question_bas": "téléchargé ?", "accroche": "Ton disque dur va pleurer",
        "hashtags": ["#nier", "#steam"], "voix_off": "NieR Automata pèse 366 Go sur Steam. Tu l'aurais téléchargé ?",
        "faisable": True}
post = {"categorie": "GAMING", "source": "ACTUGAMING", "credit": "Square Enix", "source_affichee": "ActuGaming",
        **ia.valider(rep3, it)}
check(post["titre_haut"] and post["titre_bas"] and len(post["slides"]) == 2, "IA v3 : titre en 2 lignes et slides")
une = lambda img, nom="photo1": {"img": img, "analyse": placement.analyser(img), "nom": nom}  # noqa: E731
medias = {"images": [une(photo)], "video": None}
diag_t = []
f1 = da3.carrousel(post, medias, out, "avec-photo", diag_t)
check(all(Image.open(f).size == (1080, 1350) for f in f1), "rendu v3 : toutes les slides en 1080x1350")
check(all(Image.open(f).format == "JPEG" for f in f1), "rendu v3 : JPEG (exigé par Instagram)")
check(len(f1) == 4, f"rendu v3 : couverture + 2 slides + question ({len(f1)} slides)")
ancien = ia.valider({"titre": "Fianso annonce son dernier concert à l'Accor Arena", "mot_cle": "dernier concert",
                     "sections": [{"titre": "Ce qui se passe", "texte": "Une date unique à l'Accor Arena."}],
                     "accroche": "x", "hashtags": [], "faisable": True}, dict(it, categorie="RAP FR"))
post_rap = {"categorie": "RAP FR", "source": "@RAP.MINUTE", "credit": "@rap.minute", "source_affichee": "@rap.minute",
            **ancien}
f2 = da3.carrousel(post_rap, {"images": [], "video": None}, out, "sans-photo", diag_t)
check(len(f2) == 3 and post_rap["titre_haut"], "rendu v3 : ancien format accepté, sans photo → fond neutre")
enorme = dict(post, slides=[dict(post["slides"][0], rubrique=f"Partie {i}") for i in range(12)])
check(len(da3.carrousel(enorme, medias, out, "enorme", diag_t)) == config.MAX_SLIDES, "rendu v3 : plafonné à 10 slides")

# placement : le texte ne se pose jamais sur un texte incrusté, et le sujet reste visible
faux = {"textes": [(0, 1000, 1600, 1350)], "visages": []}     # bandeau de texte en bas de l'image
img_haute = Image.new("RGB", (1080, 1350), "#202020")
c = placement.choisir(img_haute, faux, 1080, 1350, 300)
check(c["zone"] != "bas" or c["zoom"] > 1, "placement : évite le bandeau de texte incrusté")
check(placement.choisir(img_haute, {"textes": [], "visages": []}, 1080, 1350, 300)["propre"], "placement : image vide = propre")
large = Image.new("RGB", (1920, 1080), "#202020")
sujet = {"textes": [], "visages": [], "sujet": (1500, 300, 1800, 800), "sujet_poids": 1500}
c = placement.choisir(large, sujet, 1080, 1920, 300)
check(c.get("sujet_visible", 0) >= 0.8, f"placement : le sujet au bord de l'image reste dans le cadre ({c.get('sujet_visible')})")

# anti-doublon vérifié sur Instagram : mêmes hashtags de sujet = même info
from bot import instagram as _ig  # noqa: E402
check(_ig._meme_sujet(_ig._tags("#sardou #orelsan #rapfr"), _ig._tags("#orelsan #michelsardou #rapfr")),
      "anti-doublon : Sardou/Orelsan reconnu malgré des hashtags différents")
check(not _ig._meme_sujet(_ig._tags("#leto #ayanakamura"), _ig._tags("#leto #tiakola #lovestory")),
      "anti-doublon : deux infos différentes sur le même artiste restent possibles")

# ------------------------------------------------------------------ 3b. vidéo + Reel v3
src = out / "source.mp4"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x334455:size=720x1280:rate=25:duration=6",
                "-f", "lavfi", "-i", "sine=frequency=500:duration=6", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(src)], check=True)
v = vid.preparer(src, out / "an", diag_t)
check(v and v["son"] and len(v["analyses"]) >= 5, "vidéo : analysée image par image")
fv = da3.carrousel(post_rap, {"images": [une(photo)], "video": v}, out, "avec-video", diag_t)
check(all(f.suffix == ".jpg" for f in fv), "rendu v3 : carrousel en images seulement (la vidéo va dans le Reel)")
_lire = reel3.voix.lire
voix_test = out / "voix.mp3"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=4", str(voix_test)],
               check=True)
reel3.voix.lire = lambda texte, dossier, diag: voix_test


def taille(f):
    return subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                           "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout.strip()


rv, cv = reel3.fabriquer(post_rap, {"images": [une(photo)], "video": v}, "un deux trois quatre cinq six", out,
                         "reel-video", diag_t)
check(taille(rv) == "1080,1920" and vid.a_du_son(rv), "Reel v3 : vidéo 1080x1920 avec son")
check(abs(vid.duree(rv) - (0.3 + 4 + 0.3 + reel3.FIN)) < 1.0, f"Reel v3 : durée = voix + carte de fin ({vid.duree(rv):.1f} s)")
check(Image.open(cv).size == (1080, 1920), "Reel v3 : couverture 1080x1920")
rp, _ = reel3.fabriquer(post, medias, "un deux trois", out, "reel-photo", diag_t)
check(rp.exists() and rp.stat().st_size > 30_000, "Reel v3 : une seule photo → photo animée")
reel3.voix.lire = _lire
from bot import voix as _voix  # noqa: E402
check(_voix.normaliser("Son 5ème disque, GTA 6 en 2027 !") == _voix.normaliser("son cinquième disque. GTA six en deux mille vingt-sept"),
      "contrôle voix : chiffres et ordinaux reconnus écrits en lettres")
trou = out / "trou.wav"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=2",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=1.6", "-f", "lavfi", "-i", "sine=frequency=300:duration=2",
                "-filter_complex", "[0][1][2]concat=n=3:v=0:a=1", str(trou)], check=True)
check(_voix.blancs(trou) and not _voix.blancs(voix_test), "contrôle voix : un long blanc au milieu est repéré")
import numpy as _np  # noqa: E402
_sr = 24000
_t = _np.arange(int(1.5 * _sr)) / _sr
_parole = 0.3 * sum(_np.sin(2 * _np.pi * 180 * k * _t) / k for k in range(1, 6)) * (0.6 + 0.4 * _np.sin(2 * _np.pi * 4 * _t))
_bruit = _np.random.default_rng(1).uniform(-0.9, 0.9, int(0.09 * _sr))
_avec_bruit = _np.concatenate([_parole, _np.zeros(int(0.3 * _sr)), _bruit])
_propre = _voix.nettoyer_bords(_avec_bruit, _sr)
check(len(_propre) < len(_parole) + 0.25 * _sr and abs(_propre[-int(0.02 * _sr):]).max() < 0.01,
      "voix : le bruit électrique de fin est coupé, la voix finit en fondu")
_clic = _np.concatenate([_bruit[:int(0.01 * _sr)], _np.zeros(int(0.25 * _sr)), _parole])
check(len(_voix.nettoyer_bords(_clic, _sr)) < len(_parole) + 0.1 * _sr, "voix : le clic du début est coupé")
_mot = _np.concatenate([_parole, _np.zeros(int(0.3 * _sr)), _parole[:int(0.3 * _sr)]])
check(len(_voix.nettoyer_bords(_mot, _sr)) > len(_parole) + 0.55 * _sr, "voix : un vrai dernier mot après une pause est gardé")
check(sources._videos_tweet({"extended_entities": {"media": [{"video_info": {"variants": [
    {"content_type": "video/mp4", "bitrate": 832000, "url": "https://video.twimg.com/a_low.mp4"},
    {"content_type": "video/mp4", "bitrate": 2176000, "url": "https://video.twimg.com/a_high.mp4"},
    {"content_type": "application/x-mpegURL", "url": "https://video.twimg.com/a.m3u8"}]}}]}})[0]
      == "https://video.twimg.com/a_high.mp4", "X : meilleure qualité vidéo choisie")

# ------------------------------------------------------------------ 4. --verif (horaires, quota, écart)
paris = main.PARIS
midi = datetime.now(paris).replace(hour=12, minute=0, second=0, microsecond=0)
_rattrapage = config.RATTRAPAGE_JUSQUA
config.RATTRAPAGE_JUSQUA = None              # règles normales pour ces vérifications
_lancement = config.LANCEMENT_JUSQUA
config.LANCEMENT_JUSQUA = None
vide = {"vus": {}, "publies": []}
check(main.raison_de_ne_pas_poster(vide, midi) is None, "verif : midi, aucun post → on poste")
check("hors horaires" in main.raison_de_ne_pas_poster(vide, midi.replace(hour=4)), "verif : 4h du matin → non")
recent = {"vus": {}, "publies": [{"ts": (midi - timedelta(minutes=30)).isoformat(), "categorie": "GAMING", "titre": "x"}]}
check("dernier post" in main.raison_de_ne_pas_poster(recent, midi), "verif : post il y a 30 min → on attend")
plein = {"vus": {}, "publies": [{"ts": (midi - timedelta(minutes=200 + i)).isoformat(), "categorie": "GAMING",
                                 "titre": "x"} for i in range(config.POSTS_PAR_JOUR)]}
if (midi - timedelta(minutes=200 + config.POSTS_PAR_JOUR)).date() == midi.date():
    check("quota" in main.raison_de_ne_pas_poster(plein, midi), "verif : quota du jour atteint → non")
config.RATTRAPAGE_JUSQUA = (midi + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
il_y_a_55 = {"vus": {}, "publies": [{"ts": (midi - timedelta(minutes=55)).isoformat(), "categorie": "GAMING",
                                     "titre": "x"}]}
check(main.raison_de_ne_pas_poster(il_y_a_55, midi) is None, "rattrapage : un post toutes les 50 min autorisé")
config.RATTRAPAGE_JUSQUA = (midi - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
check(main.raison_de_ne_pas_poster(il_y_a_55, midi) is not None, "rattrapage terminé : retour aux règles normales")
config.RATTRAPAGE_JUSQUA = None

# ------------------------------------------------------------------ 5. passage complet simulé (réseau remplacé)
tmp_etat = Path(tempfile.mkdtemp()) / "etat.json"
main.ETAT, main.SORTIE = tmp_etat, Path(tempfile.mkdtemp())
rap_item = {"id": "ig:42", "categorie": "RAP FR", "source": "@RAP.MINUTE", "source_legende": "@rap.minute",
            "titre": "🚨 Fianso dernier concert", "resume": "Fianso Accor Arena 12/11", "texte": "Fianso Accor Arena 12/11",
            "lien": "https://instagram.com/p/x", "date": (now - timedelta(hours=1)).isoformat(),
            "images": ["https://img.example/rap.jpg"], "credit": "@rap.minute"}
sources.lire_gaming = lambda diag: [it]
sources.lire_rap = lambda diag: [rap_item]
sources.lire_x = lambda diag, etat=None: []
sources.lire_web = lambda diag: []
sources.lire_instagram = lambda diag, comptes=None: []
sources.completer_article = lambda c, diag: c
config.CATEGORIES, config.THEME, config.LANCEMENT_JUSQUA = ["GAMING", "RAP FR"], "", None
images.trouver_images = lambda c, diag, n=4: ([photo], c.get("credit", ""))
appels_ia = []


def faux_appel(parts, modeles=None):
    txt = parts[0]["text"]
    appels_ia.append(("image" if len(parts) > 1 else "texte", txt[:30]))
    if "rédacteur en chef" in txt:
        ids = [l.split("id=")[1].split(" |")[0] for l in txt.splitlines() if "id=" in l]
        return {"resultats": [{"id": i, "info": True, "score": 8, "doublon": False} for i in ids]}
    return {"titre": "Info test du jour", "mot_cle": "test", "sections": [{"titre": "Ce qui se passe", "texte": "Texte."}],
            "accroche": "Accroche", "hashtags": ["#x"], "faisable": True}


ia.appel = faux_appel
publications = []
hebergement.heberger = lambda fichiers: [f"https://raw.example/{Path(f).name}" for f in fichiers]
instagram.publier_carrousel = lambda urls, legende: publications.append((urls, legende)) or "https://instagram.com/p/OK"
instagram.diagnostic = lambda diag: None
instagram.publier_reel = lambda url, legende, feed=False, couverture_url=None: "https://instagram.com/reel/OK"

os.environ["MODE"] = "test"
check(main.executer() == 0, "simulation test : se termine sans erreur")
check(not publications, "simulation test : rien n'est publié")
check(len(list(main.SORTIE.glob("*-legende.txt"))) == 2, "simulation test : 1 carrousel gaming + 1 rap générés")
check(not tmp_etat.exists(), "simulation test : l'état n'est pas modifié")
reels = list(main.SORTIE.glob("*-reel.mp4"))
check(len(reels) == 2 and all(r.stat().st_size > 50_000 for r in reels), "simulation test : 2 Reels vidéo générés")
check(any(k == "image" for k, _ in appels_ia), "simulation : l'image du post rap est envoyée à l'IA")

os.environ["MODE"] = "auto"
check(main.executer() == 0, "simulation auto : se termine sans erreur")
check(len(publications) == 1, "simulation auto : un seul post par passage")
etat = json.loads(tmp_etat.read_text())
check(len(etat["publies"]) == 1 and etat["publies"][0]["lien"] == "https://instagram.com/p/OK", "simulation auto : post enregistré")
premier = etat["publies"][0]["categorie"]
main.executer()
etat = json.loads(tmp_etat.read_text())
check(len(etat["publies"]) == 2 and etat["publies"][1]["categorie"] != premier, "simulation auto : alterne gaming / rap")
main.executer()
check(len(json.loads(tmp_etat.read_text())["publies"]) == 2, "simulation auto : une info déjà publiée n'est jamais republiée")

# page GTA : GTA en priorité, hors GTA seulement si énorme, rap coupé
config.CATEGORIES, config.THEME = ["GAMING"], "GTA"
tmp_etat.unlink()
publications.clear()
gta_item = dict(g[0], id="web:google actu:gta-heure", date=(now - timedelta(minutes=30)).isoformat(),
                texte="Rockstar a confirmé l'heure de sortie de GTA 6 : minuit, heure locale, le 19 novembre. " * 5)
titre_seul = dict(g[0], id="web:google actu:titre-seul", texte="", titre="GTA 6 : un titre sans article")
sources.lire_web = lambda diag: [gta_item, titre_seul]
os.environ["MODE"] = "auto"
check(main.executer() == 0, "page GTA : se termine sans erreur")
etat = json.loads(tmp_etat.read_text())
check(len(etat["publies"]) == 1 and "gta" in etat["publies"][0]["source_id"], "page GTA : l'info GTA passe en premier")
main.executer()
etat = json.loads(tmp_etat.read_text())
check(len(etat["publies"]) == 1, "page GTA : info gaming hors GTA notée 8 refusée (mini 9), rap coupé")
check(all("#gta6" in l for _, l in publications), "page GTA : hashtags GTA dans la légende")
check(json.loads(tmp_etat.read_text())["vus"].get("web:google actu:titre-seul"),
      "page GTA : une info sans article lisible est écartée (jamais de post écrit sur un titre)")

# mode lancement : plus de posts, plus tôt et plus tard
config.LANCEMENT_JUSQUA = (datetime.now(main.PARIS) + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
r = main.reglages(datetime.now(main.PARIS))
check(r["posts_par_jour"] == 16 and r["ecart_min"] == 40 and r["heure_debut"] == 7 and r["heure_fin"] == 24,
      "lancement GTA 6 : 16 posts/jour, 40 min d'écart, de 7h à minuit")
config.LANCEMENT_JUSQUA = (datetime.now(main.PARIS) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
check(main.reglages(datetime.now(main.PARIS))["posts_par_jour"] == config.POSTS_PAR_JOUR,
      "lancement GTA 6 : fini après la date, retour au rythme normal")

# ------------------------------------------------------------------ 6. compte LE BRUIT (2e compte, DA LE BRUIT)
import subprocess as _sp  # noqa: E402
r = _sp.run([sys.executable, "-c", "import main, config; print(main.ETAT.name, main.JOURNAL.name, config.NOM_PAGE, "
             "config.DA, config.CATEGORIES, config.PUBLICATION_AUTO, __import__('os').environ['IG_USER_ID'])"],
            capture_output=True, text=True, cwd=str(RACINE), env=dict(os.environ, COMPTE="lebruit", IG_USER_ID="999"))
check("etat-lebruit.json dernier-journal-lebruit.txt LE BRUIT bruit ['RAP FR'] True 17841439323487258"
      in r.stdout, f"LE BRUIT : profil appliqué, état et journal séparés ({r.stdout.strip() or r.stderr[-200:]})")
r = _sp.run([sys.executable, "-c", "import main, config; print(main.ETAT.name, config.NOM_PAGE, config.DA)"],
            capture_output=True, text=True, cwd=str(RACINE), env={k: v for k, v in os.environ.items() if k != "COMPTE"})
check("etat.json C'EST TOMBÉ v3" in r.stdout, "C'EST TOMBÉ : inchangé sans COMPTE")
from bot import da_bruit, reel_bruit  # noqa: E402
_nom = config.NOM_PAGE
config.NOM_PAGE = "LE BRUIT"
post_lb = dict(post_rap, rubrique="Classements", chiffre="1", chiffre_texte="du Top 50 Spotify France",
               slides=[{"rubrique": "Le classement", "gros": "1", "sous_titre": "Première place", "texte": "Texte."},
                       {"rubrique": "Artiste", "gros": "Ninho", "sous_titre": "Le retour", "texte": "Texte."},
                       {"rubrique": "Culture", "gros_haut": "Un duo", "gros_bas": "qui frappe fort", "texte": "Texte."}],
               question_haut="Tu valides", question_bas="le morceau ?")
flb = da_bruit.carrousel(post_lb, medias, out, "lebruit", diag_t)
check(len(flb) == 5 and all(Image.open(f).size == (1080, 1350) for f in flb),
      f"LE BRUIT : carrousel (couverture, N°1, artiste, récit, fin), chiffre en double écarté ({len(flb)} slides)")
check(reel_bruit.aligner("SDM et Ninho ont frappé fort ?", [{"mot": w, "debut": i, "fin": i + 0.5} for i, w in
      enumerate(["SDM", "et", "Nignon", "frappaient", "fort", "?"])])[2]["mot"] == "Ninho",
      "LE BRUIT : sous-titres = texte exact même si la reconnaissance vocale entend mal un nom")
from bot import bruit_base as _bb
_long = "Booba réagit publiquement au style artistique et au parcours musical de Dayarga, selon lui trop complexe."
_lt = _bb.tenir(_long, _bb.police(500, 38), 500, 2)
check(_bb.unites("Tu valides le morceau ?")[-1] == "morceau ?"
      and not _lt[-1].split()[-1].lower().strip(".…") in _bb.MOTS_VIDES and _lt[-1][-1] in ".…",
      f"LE BRUIT : jamais de « ? » seul en bout de ligne ni de texte coupé sur « de » ({_lt[-1]!r})")
_pc = _bb.casse_normale({"titre_haut": "NINHO SIGNE LE", "titre_bas": "MEILLEUR DÉMARRAGE", "legende": "Ninho et SDM",
                         "slides": [{"gros_haut": "SDM", "gros_bas": "BANTU MENTALITÉ", "texte": "Bantu Mentalité"}]})
check((_pc["titre_haut"], _pc["titre_bas"], _pc["slides"][0]["gros_haut"], _pc["slides"][0]["gros_bas"])
      == ("Ninho signe le", "meilleur démarrage", "SDM", "Bantu Mentalité"),
      "LE BRUIT : titres recopiés TOUT EN CAPITALES remis en casse normale (noms propres gardés)")
_lire2 = reel_bruit.voix.lire
reel_bruit.voix.lire = lambda texte, dossier, diag: voix_test
rlb, clb = reel_bruit.fabriquer(post_lb, medias, "SDM et Ninho frappent fort. Le duo prend la tête. Tu valides ?",
                                out, "lebruit", diag_t)
check(taille(rlb) == "1080,1920" and Image.open(clb).size == (1080, 1920), "LE BRUIT : Reel 1080x1920 et couverture")
reel_bruit.voix.lire = _lire2
config.NOM_PAGE = _nom

print(f"\n{len(OK)} vérifications OK :")
print("\n".join(f"  ✓ {m}" for m in OK))
print(f"\nSlides de test dans {out}")
