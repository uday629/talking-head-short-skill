"""Fallback when transcription is unavailable: approximate word times from a pasted transcript.
python align_text.py WORKDIR transcript.txt
Distributes words across detected speech runs proportionally to character length → WORKDIR/words.json."""
import sys, os, json, wave, numpy as np
wd, txt = sys.argv[1], open(sys.argv[2]).read().split()
w = wave.open(os.path.join(wd, "a16.wav")); a = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768; hop = 160
n = len(a) // hop; db = 20 * np.log10(np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, 1)) + 1e-9)
sp = db > max(np.percentile(db, 10) + 14, -42)
runs, s = [], None
for i, v in enumerate(sp):
    if v and s is None: s = i
    if not v and s is not None:
        if i - s > 8: runs.append([s / 100, i / 100])
        s = None
tot = sum(e - s for s, e in runs); chars = [len(x) + 1 for x in txt]; C = sum(chars)
out, acc, ri, off = [], 0.0, 0, 0.0
for x, c in zip(txt, chars):
    d = c / C * tot
    while ri < len(runs) and off + d > runs[ri][1] - runs[ri][0] + 1e-6 and off > 0: ri += 1; off = 0.0
    ri = min(ri, len(runs) - 1); s0 = runs[ri][0] + off
    out.append(dict(w=x, s=round(s0, 2), e=round(s0 + d, 2), p=0.5)); off += d
json.dump(out, open(os.path.join(wd, "words.json"), "w")); print(len(out), "words aligned (approx)")
