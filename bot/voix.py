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


# ------------------------------------------------------------------ contrôle de la voix
# La voix Gemini improvise parfois : mots ajoutés ou sautés, phrase en anglais, bruits, longs blancs.
# Chaque voix est donc réécoutée par une reconnaissance vocale (faster-whisper) et comparée au texte prévu.
class VoixBizarre(RuntimeError):
    pass


_ASR = {}


def _asr():
    if "modele" not in _ASR:
        try:
            from faster_whisper import WhisperModel
            _ASR["modele"] = WhisperModel(config.VOIX_CONTROLE_MODELE, device="cpu", compute_type="int8")
        except Exception as ex:          # pas de reconnaissance vocale : on garde les contrôles simples
            _ASR["modele"], _ASR["erreur"] = None, str(ex)[:120]
    return _ASR["modele"]


def _pcm16k(fichier):
    import numpy as np
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(fichier), "-f", "s16le", "-ac", "1", "-ar", "16000",
                        "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def normaliser(texte):
    """Texte réduit à ses lettres, chiffres écrits en toutes lettres : « 5ème » = « cinquième »."""
    import unicodedata
    try:
        from num2words import num2words
    except ImportError:
        num2words = None
    t = (texte or "").lower().replace("’", "'")
    if num2words:
        t = re.sub(r"(\d+)\s*(?:ème|eme|è|e|ère|ere|er)\b",
                   lambda m: num2words(int(m.group(1)), to="ordinal", lang="fr"), t)
        t = re.sub(r"\d+", lambda m: num2words(int(m.group(0)), lang="fr"), t)
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z]+", "", t)


def blancs(fichier, seuil=None):
    """Silences au milieu de la voix (pas au début ni à la fin), en secondes."""
    seuil = seuil or config.VOIX_BLANC_MAX
    r = subprocess.run(["ffmpeg", "-i", str(fichier), "-af", f"silencedetect=noise=-38dB:d={seuil}", "-f", "null",
                        "-"], capture_output=True, text=True)
    d = duree(fichier)
    debuts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    fins = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return [round(b - a, 2) for a, b in zip(debuts, fins) if a > 0.3 and b < d - 0.3]


def verifier(fichier, texte):
    """Renvoie (ok, note de 0 à 1, ce qui a été entendu ou la raison). Une voix « bizarre » n'est pas ok."""
    from difflib import SequenceMatcher
    trous = blancs(fichier)
    if trous:
        return False, 0.0, f"blanc de {max(trous):.1f} s au milieu"
    modele = _asr()
    if modele is None:
        return True, 1.0, f"contrôle mot à mot indisponible ({_ASR.get('erreur', '')})"
    segments, info = modele.transcribe(_pcm16k(fichier), language="fr", beam_size=1, vad_filter=False,
                                       condition_on_previous_text=False)
    segments = list(segments)
    entendu = " ".join(sg.text.strip() for sg in segments).strip()
    a, b = normaliser(texte), normaliser(entendu)
    if not b:
        return False, 0.0, "rien d'intelligible"
    note = SequenceMatcher(None, a, b, autojunk=False).ratio()
    longueur = len(b) / max(1, len(a))
    pire = min((sg.avg_logprob for sg in segments), default=0)
    if note < config.VOIX_CONTROLE_MIN:
        return False, note, f"texte différent ({note:.0%}) : « {entendu[:160]} »"
    if not 0.8 <= longueur <= 1.2:
        return False, note, f"{'mots en trop' if longueur > 1 else 'mots sautés'} ({longueur:.0%}) : « {entendu[:160]} »"
    if pire < -1.2:              # passage que la reconnaissance comprend à peine : bruit, charabia, accent bizarre
        return False, note, f"passage incompréhensible ({pire:.2f}) : « {entendu[:160]} »"
    return True, note, entendu


def _gemini(texte, sortie, voix=None):
    import requests
    voix = voix or config.VOIX.split(":", 1)[1]
    cle = os.environ.get("GEMINI_API_KEY") or config.GEMINI_API_KEY_DANS_LE_CODE
    if not cle:
        raise RuntimeError("clé Gemini manquante")
    derniere = None
    for modele in config.GEMINI_TTS_MODELES:
        r = requests.post(TTS_URL.format(modele), headers={"x-goog-api-key": cle}, timeout=120, json={
            "contents": [{"parts": [{"text": f"{config.VOIX_CONSIGNE}{texte}"}]}],
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
               f"atempo={config.VOIX_GEMINI_TEMPO},{config.VOIX_TRAITEMENT}", "-ar", "44100", "-b:a", "192k",
               str(sortie)]
        p = subprocess.run(cmd, input=pcm, capture_output=True)
        if p.returncode != 0 or not sortie.exists() or sortie.stat().st_size < 2000:
            derniere = f"{modele} : conversion impossible"
            continue
        # garde-fou : une voix qui lit aussi la consigne, ou qui invente des phrases, dure bien trop longtemps
        attendu = len(texte.split()) / 3.0
        if not (attendu * 0.5 <= duree(sortie) <= attendu * 1.6 + 1.5):
            derniere = f"{modele} : durée anormale ({duree(sortie):.1f} s au lieu de ~{attendu:.0f} s), écartée"
            sortie.unlink()
            continue
        return sortie, modele
    raise RuntimeError(derniere or "aucun modèle TTS")


def _gemini_controle(texte, sortie, diag=None):
    """Voix Gemini réécoutée : refaite si elle s'écarte du texte (au plus VOIX_ESSAIS fois en tout)."""
    raisons = []
    for essai in range(config.VOIX_ESSAIS):
        f, modele = _gemini(texte, sortie)
        ok, note, quoi = verifier(f, texte)
        if ok:
            if diag is not None:
                diag.append(f"  voix · contrôle OK ({note:.0%}, essai {essai + 1}, {modele})")
            return f
        raisons.append(f"essai {essai + 1} : {quoi}")
        if diag is not None:
            diag.append(f"  voix · ⚠️ refaite, {quoi[:200]}")
        f.unlink(missing_ok=True)
    raise VoixBizarre(" · ".join(raisons)[:300])


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


SIGLES = {"GTA", "PDG", "PS5", "PS4", "PSG", "OM", "NBA", "UFC", "DLC", "PC", "JO", "RER", "SNCF", "TF1", "M6",
          "USA", "UK", "EA", "IA", "BD", "CD", "DVD", "EP", "MMA", "F1", "DJ", "MC", "PNL", "SCH", "RK", "JUL"}


def preparer(texte):
    """Texte vraiment lisible à voix haute : sans emojis, hashtags ni @, sans MAJUSCULES criées, « x » entre
    deux artistes lu « et » (une voix de synthèse fait des choses bizarres sur tout ça)."""
    t = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]", "", texte or "")
    t = re.sub(r"#(\w+)", r"\1", t)
    t = re.sub(r"@(\w+)", r"\1", t)
    t = re.sub(r"(?<=\w) [x×] (?=\w)", " et ", t)
    t = re.sub(r"[×x](\d+)\b", r"\1 fois", t)

    def casse(m):
        mot = m.group(0)
        return mot if mot in SIGLES or len(mot) <= 2 else mot.title()

    t = re.sub(r"\b[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ'-]{2,}\b", casse, t)
    t = re.sub(r"\s+([,.])", r"\1", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def lire(texte, dossier, diag):
    texte = preparer(texte)
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    moteurs = [("edge-tts", _edge, dossier / "voix.mp3"), ("piper", _piper, dossier / "voix.mp3")]
    if config.VOIX.startswith("gemini:"):
        moteurs.insert(0, (f"Gemini ({config.VOIX[7:]})",
                           lambda t, f: _gemini_controle(t, f, diag), dossier / "voix.mp3"))
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
