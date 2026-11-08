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

# ------------------------------------------------------------------ 2. validation de la réponse IA
rep = {"titre": "NieR Automata pèse soudain 366 Go sur Steam.", "mot_cle": "366 go",
       "sections": [{"titre": "Ce qui se passe", "texte": "Texte."}, {"titre": "", "texte": "vide"}],
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

# ------------------------------------------------------------------ 3. rendu
out = Path(tempfile.mkdtemp())
photo = Image.new("RGB", (1600, 900), "#3B4A6B")
long_txt = " ".join(["Une phrase de test pour remplir la slide et vérifier la pagination automatique."] * 6)
post = {"categorie": "GAMING", "titre": "NieR Automata pèse soudain 366 Go sur Steam", "mot_cle": "366 Go",
        "source": "ACTUGAMING", "credit": "Square Enix",
        "sections": [{"titre": "Ce qui se passe", "texte": long_txt},
                     {"titre": "Ce qu'en dit le studio", "texte": "Le studio enquête."},
                     {"titre": "En attendant", "texte": long_txt}]}
f1 = rendu.carrousel(post, photo, out, "avec-photo")
check(all(Image.open(f).size == (1080, 1350) for f in f1), "rendu : toutes les slides en 1080x1350")
check(all(Image.open(f).format == "JPEG" for f in f1), "rendu : JPEG (exigé par Instagram)")
check(2 < len(f1) <= config.MAX_SLIDES, f"rendu : texte long paginé ({len(f1)} slides)")
post_rap = dict(post, categorie="RAP FR", titre="Fianso annonce son dernier concert à l'Accor Arena",
                mot_cle="dernier concert", source="@RAP.MINUTE", credit="@rap.minute",
                sections=[{"titre": "Ce qui se passe", "texte": "Une date unique à l'Accor Arena."}])
f2 = rendu.carrousel(post_rap, None, out, "sans-photo")
check(len(f2) == 2, "rendu : info courte → 2 slides, couverture sans photo")
enorme = dict(post, sections=[{"titre": f"Partie {i}", "texte": long_txt} for i in range(12)])
check(len(rendu.carrousel(enorme, photo, out, "enorme")) == config.MAX_SLIDES, "rendu : plafonné à 10 slides")

# ------------------------------------------------------------------ 4. --verif (horaires, quota, écart)
paris = main.PARIS
midi = datetime.now(paris).replace(hour=12, minute=0, second=0, microsecond=0)
vide = {"vus": {}, "publies": []}
check(main.raison_de_ne_pas_poster(vide, midi) is None, "verif : midi, aucun post → on poste")
check("hors horaires" in main.raison_de_ne_pas_poster(vide, midi.replace(hour=4)), "verif : 4h du matin → non")
recent = {"vus": {}, "publies": [{"ts": (midi - timedelta(minutes=30)).isoformat(), "categorie": "GAMING", "titre": "x"}]}
check("dernier post" in main.raison_de_ne_pas_poster(recent, midi), "verif : post il y a 30 min → on attend")
plein = {"vus": {}, "publies": [{"ts": (midi - timedelta(minutes=200 + i)).isoformat(), "categorie": "GAMING",
                                 "titre": "x"} for i in range(config.POSTS_PAR_JOUR)]}
if (midi - timedelta(minutes=200 + config.POSTS_PAR_JOUR)).date() == midi.date():
    check("quota" in main.raison_de_ne_pas_poster(plein, midi), "verif : quota du jour atteint → non")

# ------------------------------------------------------------------ 5. passage complet simulé (réseau remplacé)
tmp_etat = Path(tempfile.mkdtemp()) / "etat.json"
main.ETAT, main.SORTIE = tmp_etat, Path(tempfile.mkdtemp())
rap_item = {"id": "ig:42", "categorie": "RAP FR", "source": "@RAP.MINUTE", "source_legende": "@rap.minute",
            "titre": "🚨 Fianso dernier concert", "resume": "Fianso Accor Arena 12/11", "texte": "Fianso Accor Arena 12/11",
            "lien": "https://instagram.com/p/x", "date": (now - timedelta(hours=1)).isoformat(),
            "images": ["https://img.example/rap.jpg"], "credit": "@rap.minute"}
sources.lire_gaming = lambda diag: [it]
sources.lire_rap = lambda diag: [rap_item]
sources.lire_x = lambda diag: []
images.trouver_photo = lambda c, diag: (photo, c.get("credit", ""))
appels_ia = []


def faux_appel(parts):
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
instagram.publier_reel = lambda url, legende, feed=False: "https://instagram.com/reel/OK"

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

print(f"\n{len(OK)} vérifications OK :")
print("\n".join(f"  ✓ {m}" for m in OK))
print(f"\nSlides de test dans {out}")
