import glob
import subprocess

import numpy as np
from faster_whisper import WhisperModel

m = WhisperModel("small", device="cpu", compute_type="int8")
out = []
for f in sorted(glob.glob("/tmp/r/voix-*.mp3")) + sorted(glob.glob("/tmp/da/*.mp4")):
    if "traitee" in f:
        continue
    brut = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", f, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                          capture_output=True).stdout
    audio = np.frombuffer(brut, np.int16).astype(np.float32) / 32768
    segs, info = m.transcribe(audio, language="fr")
    texte = " ".join(f"[{s.start:.1f}-{s.end:.1f}] {s.text.strip()}" for s in segs)
    out.append(f"{f.split('/')[-1]} : {texte}")
    print(out[-1], flush=True)
open("/tmp/r/transcriptions.txt", "w").write("\n\n".join(out))
