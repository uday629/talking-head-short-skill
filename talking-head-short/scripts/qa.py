"""QA on the finished file. python qa.py WORKDIR
Prints: duration, loudness, flash frames, and writes qa_endframes.jpg = the LAST frame of every caption beat and card
(where cut-off text / unfinished animations show up). Look at that one image before delivering."""
import os, sys, json, subprocess
import numpy as np, cv2
WD = sys.argv[1]; log = json.load(open(os.path.join(WD, "render_log.json")))
spec = json.load(open(os.path.join(WD, "spec.json"))); f = os.path.join(WD, spec.get("out", "final.mp4"))
if not os.path.exists(f): f = os.path.join(WD, "video.mp4")
r = subprocess.run(["ffmpeg", "-v", "info", "-i", f, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
I = [l.split()[1] for l in r.splitlines() if l.strip().startswith("I:")]; Pk = [l.split()[1] for l in r.splitlines() if l.strip().startswith("Peak:")]
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-vf", "scale=108:192", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, 192, 108).astype(np.float32)
flash = []
for i in range(1, len(fr) - 1):
    a = np.abs(fr[i] - fr[i - 1]).mean(); b = np.abs(fr[i] - fr[i + 1]).mean(); c = np.abs(fr[i - 1] - fr[i + 1]).mean()
    if a > 5 and b > 5 and c < 0.6 * min(a, b): flash.append(round(i / 30, 2))
ts = [(c["end"] - 0.2, c["key"]) for c in log["captions"]] + [(c["b"] - 0.2, c["type"]) for c in log["cards"]]   # just before the fade-out
ts = sorted(t for t in ts if t[0] > 0)
ims = []
for t, lab in ts:
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", f, "-frames:v", "1", "-vf", "scale=216:384", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    if len(b) == 216 * 384 * 3:
        im = np.frombuffer(b, np.uint8).reshape(384, 216, 3).copy(); cv2.putText(im, f"{t:.1f} {lab[:14]}", (4, 16), 0, 0.42, (0, 255, 255), 1); ims.append(im)
if ims:
    rows = [np.hstack(ims[i:i + 8] + [np.zeros_like(ims[0])] * (8 - len(ims[i:i + 8]))) for i in range(0, len(ims), 8)]
    cv2.imwrite(os.path.join(WD, "qa_endframes.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 82])
print(f"QA {os.path.basename(f)} | dur {len(fr) / 30:.1f}s | loud {I[-1] if I else '?'} LUFS peak {Pk[-1] if Pk else '?'} | flash {flash or 'none'} | issues {len(log['issues'])}")
print("check: qa_endframes.jpg (every beat/card end — nothing cut off, every animation finished)")
