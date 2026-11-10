import glob
from faster_whisper import WhisperModel
m = WhisperModel("small", device="cpu", compute_type="int8")
out = []
for f in sorted(glob.glob("/tmp/r/voix-*.mp3")) + sorted(glob.glob("/tmp/da/*.mp4")):
    if "traitee" in f:
        continue
    segs, info = m.transcribe(f, language="fr", word_timestamps=False)
    texte = " ".join(s.text.strip() for s in segs)
    out.append(f"{f.split('/')[-1]} : {texte}")
    print(out[-1], flush=True)
open("/tmp/r/transcriptions.txt", "w").write("\n\n".join(out))
