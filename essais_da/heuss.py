"""Essai DA v2 sur une info connue (Heuss / Cédric Grolet) avec la vraie voix off : carrousel + Reel."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from bot import da, reel, video as vid  # noqa: E402

SORTIE = RACINE / "sortie"
SORTIE.mkdir(exist_ok=True)
diag = []
post = {"categorie": "RAP FR", "source": "@RAP.MINUTE", "credit": "@rap.minute",
        "titre": "Heuss n’a eu aucune pitié pour Cédric Grolet", "mot_cle": "aucune pitié",
        "sections": [
            {"titre": "Ce qui se passe", "texte": "En live, Heuss a regardé les vidéos du chef pâtissier Cédric "
                                                 "Grolet et a enchaîné les vannes sur ses créations."},
            {"titre": "Les détails", "texte": "Pendant que le chef découpe ses fraises en trompe-l’œil, Heuss "
                                             "commente chaque geste sous les rires de ses invités."}]}
voix_off = ("En live, Heuss a regardé les vidéos du chef pâtissier Cédric Grolet. Et il n’a eu aucune pitié : "
            "les vannes se sont enchaînées sur chaque création, sous les rires de ses invités. "
            "Abonne-toi à C’est tombé pour pas rater la suite.")
v = vid.preparer(RACINE / "essais_da" / "heuss.mp4", SORTIE / "heuss-src", diag)
medias = {"images": [], "video": v}
fichiers = da.carrousel(post, medias, SORTIE, "heuss", diag)
r = reel.fabriquer(post, medias, voix_off, SORTIE, "heuss", diag)
print("\n".join(diag))
print([f.name for f in fichiers], r.name)
