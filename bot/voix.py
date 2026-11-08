"""Voix off : lit le texte du post en français.

1. edge-tts (voix neuronales Microsoft, gratuites, meilleure qualité)
2. Piper (voix libre, tourne sur la machine) si edge-tts ne répond pas
Renvoie le chemin d'un fichier audio, ou None si aucune voix n'a marché (le Reel sera muet).
"""
import asyncio
import subprocess
import urllib.request
from pathlib import Path

import config

CACHE = Path.home() / ".cache" / "cesttombe-voix"
PIPER_MODELE = "fr_FR-siwis-medium"
PIPER_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/"


def _edge(texte, sortie):
    import edge_tts

    async def run():
        com = edge_tts.Communicate(texte, config.VOIX, rate=config.VOIX_VITESSE)
        await com.save(str(sortie))

    asyncio.run(asyncio.wait_for(run(), timeout=60))
    if not sortie.exists() or sortie.stat().st_size < 2000:
        raise RuntimeError("fichier audio vide")
    return sortie


def _piper(texte, sortie):
    CACHE.mkdir(parents=True, exist_ok=True)
    for ext in (".onnx", ".onnx.json"):
        f = CACHE / (PIPER_MODELE + ext)
        if not f.exists():
            urllib.request.urlretrieve(PIPER_URL + PIPER_MODELE + ext, f)
    wav = sortie.with_suffix(".wav")
    r = subprocess.run(["python", "-m", "piper", "-m", str(CACHE / (PIPER_MODELE + ".onnx")), "-f", str(wav)],
                       input=texte, text=True, capture_output=True, timeout=120)
    if r.returncode != 0 or not wav.exists():
        raise RuntimeError(r.stderr[-200:])
    return wav


def lire(texte, dossier, diag):
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    for nom, fn, sortie in (("edge-tts", _edge, dossier / "voix.mp3"), ("piper", _piper, dossier / "voix.mp3")):
        try:
            f = fn(texte, sortie)
            diag.append(f"  voix · {nom} ({duree(f):.1f} s)")
            return f
        except Exception as ex:
            diag.append(f"  voix · {nom} indisponible : {str(ex)[:120]}")
    return None


def duree(fichier):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(fichier)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)
