"""XTTS v2 ile bir take'in satırlarını referans sesle okut; satır aralarına sessizlik koy.
Her satır Whisper ile denetlenir; metinle uyuşmazsa (uydurma ek, atlanan kelime) başka tohumla yeniden üretilir.
Kullanım: python3 xtts_say.py <ref.wav> <girdi.txt> <cikti.wav>  (satırlar boş satırla ayrılır)"""
import difflib
import os
import re
import sys

os.environ.setdefault("COQUI_TOS_AGREED", "1")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
import numpy as np
import soundfile as sf
import torch
from faster_whisper import WhisperModel
from TTS.api import TTS

ref, src, out = sys.argv[1:4]
lines = [l.strip() for l in open(src, encoding="utf-8").read().split("\n\n") if l.strip()]
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
asr = WhisperModel("small", device="cpu", compute_type="int8")
SR = 24000


def norm(s):
    s = s.replace("İ", "i").replace("I", "ı").lower()
    return re.sub(r"[^a-zçğıöşü ]", "", s).split()


def check(wav, text):
    a16 = np.interp(np.arange(0, len(wav), SR / 16000), np.arange(len(wav)), wav).astype(np.float32)
    segs, _ = asr.transcribe(a16, language="tr", word_timestamps=True)
    words = [w for s in segs for w in (s.words or [])]
    heard = " ".join(w.word for w in words)
    score = difflib.SequenceMatcher(None, norm(text), norm(heard)).ratio()
    return score, heard, (words[-1].end if words else len(wav) / SR)


gap = np.zeros(int(0.8 * SR), dtype=np.float32)
parts = []
for i, line in enumerate(lines):
    best = None
    for seed in (7, 11, 23, 42, 99):
        torch.manual_seed(seed)
        wav = np.asarray(tts.tts(text=line, speaker_wav=ref, language="tr", split_sentences=False,
                                 temperature=0.6, repetition_penalty=5.0), dtype=np.float32)
        score, heard, end = check(wav, line)
        print(f"  satır {i + 1} tohum {seed}: {score:.2f}  «{heard.strip()}»", file=sys.stderr)
        if best is None or score > best[0]:
            best = (score, wav, end)
        if score >= 0.97:
            break
    score, wav, end = best
    wav = wav[: min(len(wav), int((end + 0.25) * SR))]          # son kelimeden sonraki uydurma kuyruğu kes
    parts += ([gap] if i else []) + [wav]
sf.write(out, np.concatenate(parts), SR)
print("ok", out)
