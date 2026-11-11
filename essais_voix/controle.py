"""Essai : 2 vraies voix produites comme par le bot (voix.lire : nettoyage des bords + contrôle),
puis mesure de la fin de chaque voix : plus aucun bruit après la dernière syllabe."""
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bot import voix  # noqa: E402

TEXTES = {
    "bioshock": "Le PDG de Take-Two donne enfin des nouvelles du prochain BioShock. Le développement a été compliqué, "
                "mais le jeu avance toujours. Tu l'attends, toi, ce nouveau BioShock ?",
    "niro": "Niro décroche le 5ème disque de platine de sa carrière. Une belle récompense pour l'un des rappeurs les "
            "plus réguliers du game. Tu écoutes encore Niro, toi ?",
}
out = Path(sys.argv[1] if len(sys.argv) > 1 else "sortie")
out.mkdir(parents=True, exist_ok=True)
for nom, texte in TEXTES.items():
    diag = []
    f = voix.lire(texte, out / f"tmp-{nom}", diag)
    print(f"{nom} : " + " | ".join(d.strip() for d in diag))
    if not f:
        continue
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(f), "-f", "s16le", "-ac", "1", "-ar", "24000", "-"],
                       capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768
    w = 240
    pk = [int(20 * np.log10(np.max(np.abs(x[i:i + w])) + 1e-9)) for i in range(len(x) - 40 * w, len(x) - w + 1, w)]
    print(f"   crête des 400 dernières ms (par 10 ms) : {pk}")
    f.rename(out / f"voix-{nom}.mp3")
