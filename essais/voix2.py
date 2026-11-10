"""Échantillons de voix plus humaines : nouveaux modèles Gemini TTS + direction de jeu + traitement studio."""
import base64
import json
import os
import re
import subprocess
import time
from pathlib import Path

import requests

S = Path("sortie"); S.mkdir(exist_ok=True)
CLE = os.environ["GEMINI_API_KEY"]
URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
DIRECTION = """Synthesize speech for the performance defined below. The profile, scene and performance notes are direction only. Do NOT speak them. Speak ONLY the lines under #### TRANSCRIPT, in French.

### PROFILE
A 26-year-old Parisian woman who runs a popular French news page on Instagram and TikTok. She sounds like a real person talking to her followers, not like a radio announcer or an assistant.

### SCENE
She records the voice-over of a vertical video on her phone, close to the microphone, in a quiet room.

### PERFORMANCE NOTES
Natural, conversational and warm, with a slight smile in the voice. Energetic but relaxed, like telling a friend some big news. Native French pronunciation with natural liaisons and real breathing between sentences. Fast, punchy rhythm with tiny pauses before the key facts. Never robotic, never over-acted.

#### TRANSCRIPT
"""
TEXTE = ("[excited] Teddy Riner se lance dans la course à l’Élysée. [short pause] Le quintuple champion olympique a "
         "annoncé ce lundi sa candidature à la présidentielle 2027, dans une vidéo sur ses réseaux. Abonne-toi à C’est tombé.")
ANCIENNE = ("Lis le texte suivant en français, comme une jeune présentatrice d'actu sur Instagram qui raconte une info à "
            "ses abonnés : ton naturel, vivant et complice, débit plutôt rapide, sans exagérer. Lis uniquement le texte, "
            "pas cette consigne.\n\n")
TRAITEMENT = ("highpass=f=80,equalizer=f=220:t=q:w=1:g=1.5,equalizer=f=3800:t=q:w=1.2:g=3,deesser=i=0.35,"
              "acompressor=threshold=-20dB:ratio=3:attack=5:release=90:makeup=3,loudnorm=I=-16:TP=-1.5:LRA=7")
journal = []


def voix(modele, nom_voix, prompt, sortie):
    r = requests.post(URL.format(modele), headers={"x-goog-api-key": CLE}, timeout=180, json={
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["AUDIO"],
                             "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": nom_voix}}}}})
    if r.status_code != 200:
        return f"HTTP {r.status_code} : {r.text[:220]}"
    part = next(p for p in r.json()["candidates"][0]["content"]["parts"] if p.get("inlineData"))
    taux = re.search(r"rate=(\d+)", part["inlineData"].get("mimeType", ""))
    pcm = base64.b64decode(part["inlineData"]["data"])
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", taux.group(1) if taux else "24000",
                    "-ac", "1", "-i", "-", "-af",
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse",
                    "-ar", "44100", "-b:a", "192k", str(sortie)], input=pcm, check=True)
    return "ok"


essais = [("gemini-3.8-flash-tts", "Aoede", DIRECTION + TEXTE, "1-gemini38-Aoede"),
          ("gemini-3.8-flash-tts", "Leda", DIRECTION + TEXTE, "2-gemini38-Leda"),
          ("gemini-3.8-flash-tts", "Achernar", DIRECTION + TEXTE, "3-gemini38-Achernar"),
          ("gemini-3.8-flash-lite-tts", "Aoede", DIRECTION + TEXTE, "4-gemini38lite-Aoede"),
          ("gemini-3.1-flash-tts-preview", "Aoede", DIRECTION + TEXTE, "5-gemini31-Aoede-nouvelle-direction")]
for modele, v, prompt, nom in essais:
    f = S / f"voix-{nom}.mp3"
    try:
        res = voix(modele, v, prompt, f)
    except Exception as ex:
        res = f"échec : {ex}"
    if res == "ok":
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(f), "-af", TRAITEMENT, "-ar", "44100",
                        "-b:a", "192k", str(S / f"voix-{nom}-traitee.mp3")], check=True)
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                           capture_output=True, text=True).stdout.strip()
        res = f"ok ({float(d):.1f} s)"
    journal.append(f"{nom} [{modele}] : {res}")
    print(journal[-1], flush=True)
    time.sleep(15)
(S / "journal.txt").write_text("\n".join(journal), encoding="utf-8")
