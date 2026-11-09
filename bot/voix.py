"""Voix off : lit le texte du post en français.

1. Gemini TTS (voix très naturelles de Google, gratuites avec la clé Gemini) si config.VOIX = "gemini:<Voix>"
2. edge-tts (voix neuronales Microsoft, gratuites)
3. Piper (voix libre, tourne sur la machine) si rien d'autre ne répond
Renvoie le chemin d'un fichier audio, ou None si aucune voix n'a marché (le Reel sera muet).
"""
import asyncio
import base64
import os
import re
import subprocess
import urllib.request
from pathlib import Path

import config

CACHE = Path.home() / ".cache" / "cesttombe-voix"
PIPER_MODELE = "fr_FR-siwis-medium"
PIPER_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/"


TTS_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"


def _gemini(texte, sortie, voix=None):
    import requests
    voix = voix or config.VOIX.split(":", 1)[1]
    cle = os.environ.get("GEMINI_API_KEY") or config.GEMINI_API_KEY_DANS_LE_CODE
    if not cle:
        raise RuntimeError("clé Gemini manquante")
    derniere = None
    for modele in config.GEMINI_TTS_MODELES:
        r = requests.post(TTS_URL.format(modele), headers={"x-goog-api-key": cle}, timeout=120, json={
            "contents": [{"parts": [{"text": f"{config.VOIX_CONSIGNE}\n\n{texte}"}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voix}}}}})
        if r.status_code != 200:
            derniere = f"{modele} HTTP {r.status_code} : {r.text[:120]}"
            continue
        try:
            part = next(p for p in r.json()["candidates"][0]["content"]["parts"] if p.get("inlineData"))
        except (KeyError, IndexError, StopIteration):
            derniere = f"{modele} : pas d'audio dans la réponse"
            continue
        taux = re.search(r"rate=(\d+)", part["inlineData"].get("mimeType", ""))
        pcm = base64.b64decode(part["inlineData"]["data"])
        # PCM brut → fichier audio, silences du début et de la fin retirés, léger coup d'accélérateur
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", taux.group(1) if taux else "24000",
               "-ac", "1", "-i", "-", "-af",
               "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
               "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
               f"atempo={config.VOIX_GEMINI_TEMPO}", "-ar", "44100", "-b:a", "192k", str(sortie)]
        p = subprocess.run(cmd, input=pcm, capture_output=True)
        if p.returncode != 0 or not sortie.exists() or sortie.stat().st_size < 2000:
            derniere = f"{modele} : conversion impossible"
            continue
        return sortie
    raise RuntimeError(derniere or "aucun modèle TTS")


def _edge(texte, sortie, voix=None):
    import edge_tts
    voix = voix or (config.VOIX if not config.VOIX.startswith("gemini:") else config.VOIX_SECOURS)

    async def run():
        com = edge_tts.Communicate(texte, voix, rate=config.VOIX_VITESSE)
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
    moteurs = [("edge-tts", _edge, dossier / "voix.mp3"), ("piper", _piper, dossier / "voix.mp3")]
    if config.VOIX.startswith("gemini:"):
        moteurs.insert(0, (f"Gemini ({config.VOIX[7:]})", _gemini, dossier / "voix.mp3"))
    for nom, fn, sortie in moteurs:
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
