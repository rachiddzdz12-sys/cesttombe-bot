"""Essai : échantillons de voix (Gemini TTS vs voix actuelle) + photos supplémentaires du sujet + démo complète."""
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import config  # noqa: E402
from bot import da, placement, reel, visuels, voix  # noqa: E402

S = RACINE / "sortie"
S.mkdir(exist_ok=True)
diag = []
log = lambda m: (print(m, flush=True), diag.append(m))  # noqa: E731
texte = ("Teddy Riner se lance dans la course à l’Élysée. Le quintuple champion olympique a annoncé ce lundi "
         "sa candidature à la présidentielle 2027, dans une vidéo sur ses réseaux. Abonne-toi à C’est tombé.")

# 1. voix
for v in ["Aoede", "Leda", "Despina", "Callirrhoe", "Sulafat", "Kore"]:
    try:
        f = voix._gemini(texte, S / f"voix-gemini-{v}.mp3", v)
        log(f"voix Gemini {v} : {voix.duree(f):.1f} s")
    except Exception as ex:
        log(f"voix Gemini {v} : ÉCHEC {str(ex)[:200]}")
    time.sleep(22)
try:
    f = voix._edge(texte, S / "voix-actuelle-Denise.mp3", "fr-FR-DeniseNeural")
    log(f"voix Denise : {voix.duree(f):.1f} s")
except Exception as ex:
    log(f"voix Denise : ÉCHEC {ex}")

# 2. photos du sujet
for typ, nom in [("personne", "Teddy Riner"), ("artiste", "Ninho"), ("artiste", "Heuss L'Enfoiré"),
                 ("jeu", "Mass Effect Legendary Edition"), ("personne", "Jensen Huang")]:
    res = visuels.chercher([{"type": typ, "nom": nom}], diag, n=4)
    slug = visuels._norme(nom).replace(" ", "-")
    for i, (img, credit) in enumerate(res):
        img.thumbnail((900, 900))
        img.save(S / f"visuel-{slug}-{i + 1}.jpg", quality=85)
        log(f"  {nom} {i + 1} : {img.width}x{img.height} · {credit or '—'}")
    log(f"{nom} : {len(res)} image(s)")
print("\n".join(diag))

# 3. démo complète Teddy Riner : plusieurs photos + voix courte
res = visuels.chercher([{"type": "personne", "nom": "Teddy Riner"}], [], n=5)
if res:
    for v in ("Aoede", "Leda", "Kore"):          # première voix Gemini qui répond
        config.VOIX = f"gemini:{v}"
        try:
            voix._gemini("Test.", S / "_t.mp3", v)
            break
        except Exception:
            time.sleep(20)
    post = {"categorie": "ACTU", "source": "@TEDDYRINER (X) · FRANCEINFO", "credit": "",
            "titre": "Teddy Riner candidat à la présidentielle 2027", "mot_cle": "présidentielle 2027",
            "sections": [{"titre": "Ce qui se passe", "texte": "Teddy Riner a annoncé ce lundi 9 novembre sa "
                          "candidature à l’élection présidentielle de 2027, dans une vidéo publiée sur ses réseaux."},
                         {"titre": "Pourquoi il se lance", "texte": "Il explique que sa décision remonte à l’après "
                          "JO de Paris 2024. Il se présente comme ni de droite ni de gauche."}]}
    medias = {"images": [{"img": im, "analyse": placement.analyser(im), "nom": f"photo{i + 1}"}
                         for i, (im, _) in enumerate(res)], "video": None}
    d2 = []
    f = da.carrousel(post, medias, S, "demo", d2)
    r = reel.fabriquer(post, medias, texte, S, "demo", d2)
    print("\n".join(d2))
    (S / "demo-credits.txt").write_text("\n".join(c for _, c in res if c), encoding="utf-8")
(S / "journal.txt").write_text("\n".join(diag), encoding="utf-8")
