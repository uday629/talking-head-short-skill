"""Step 1: analyze a raw talking-head clip.
python analyze.py RAW.mp4 WORKDIR [--model small.en|base|small] [--no-tx]
Writes WORKDIR/: words.json (src word times), segments.json (proposed clean cut), probe.json, frames.jpg (eye/framing grid).
Prints a compact report (keep it short: this output goes into the model context)."""
import sys, os, json, subprocess, re, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ff import FFMPEG, probe as ffprobe_info

def sh(cmd): return subprocess.run(cmd, capture_output=True, text=True)

def probe(p): return ffprobe_info(p)

def load_model(model):
    """HuggingFace first; if blocked (403/offline sandbox) → GitHub mirror of the same open Whisper weights (MIT)."""
    from faster_whisper import WhisperModel
    import net
    if any(h in "huggingface.co" for h in net.BLOCK): os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        return WhisperModel(model, device="cpu", compute_type="int8"), model
    except Exception as e:
        print("HF model unavailable (" + str(e)[:60] + ") → GitHub mirror")
    for name in (("whisper-base",) if model != "tiny" else ()) + ("whisper-tiny",):
        try:
            d = net.mirror_zip(name + ".zip", os.path.join(net.ASSETS, "models"))
            return WhisperModel(os.path.join(d, name), device="cpu", compute_type="int8"), name
        except Exception as e:
            print(name, "mirror failed:", str(e)[:100])
    raise RuntimeError("no transcription model reachable")

def transcribe(wav, model):
    m, used = load_model(model)
    segs, info = m.transcribe(wav, word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    words = [dict(w=w.word.strip(), s=round(w.start, 2), e=round(w.end, 2), p=round(w.probability, 2)) for s in segs for w in s.words]
    return words, info.language

FILLERS = {"um", "uh", "erm", "uhm", "hmm", "ah", "mm"}
SOFT_FILLERS = {"like", "so", "basically", "actually", "literally"}
def norm(w): return re.sub(r"[^a-z0-9$%']", "", w.lower())

def bad_spans(words):
    """auto-remove only safe cases: hard fillers, immediate stutters, immediate restarts.
    Everything ambiguous is returned as SUGGESTIONS for the model to judge (rhetorical repetition is NOT a retake)."""
    spans, why, sugg = [], [], []
    for w in words:
        if norm(w["w"]) in FILLERS: spans.append([w["s"] - 0.03, w["e"] + 0.03]); why.append(f"filler '{w['w']}'@{w['s']}")
    toks = [norm(w["w"]) for w in words]
    for i in range(len(words) - 1):
        a, b = words[i], words[i + 1]
        if toks[i] and toks[i] == toks[i + 1] and b["s"] - a["e"] < 0.6:
            spans.append([a["s"] - 0.03, b["s"] - 0.03]); why.append(f"stutter '{a['w']}'@{a['s']}")
    for i in range(len(words) - 3):          # restart: 2-4 words, pause/low-conf, then the same words again right away
        for L in (4, 3, 2):
            if i + 2 * L > len(words): continue
            if toks[i:i + L] == toks[i + L:i + 2 * L] and all(toks[i:i + L]):
                spans.append([words[i]["s"] - 0.03, words[i + L]["s"] - 0.03]); why.append(f"restart '{' '.join(toks[i:i+L])}'@{words[i]['s']}"); break
    for i, w in enumerate(words):
        if norm(w["w"]) in SOFT_FILLERS or w.get("p", 1) < 0.35:
            sugg.append(f"{w['w']}@{w['s']}-{w['e']}")
        if i and words[i]["s"] - words[i - 1]["e"] > 0.8: sugg.append(f"[pause {words[i-1]['e']}-{words[i]['s']}]")
    return spans, why, sugg

def speech_segments(wav, remove, maxgap=0.32, pad_in=0.06, pad_out=0.10):
    w = wave.open(wav); a = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768; hop = 160
    n = len(a) // hop
    db = 20 * np.log10(np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, 1)) + 1e-9)
    thr = max(np.percentile(db, 10) + 14, -42); sp = db > thr
    runs, s = [], None
    for i, v in enumerate(sp):
        if v and s is None: s = i
        if not v and s is not None: runs.append([s, i]); s = None
    if s is not None: runs.append([s, n])
    M = []
    for s0, e0 in runs:
        if M and s0 - M[-1][1] < 12: M[-1][1] = e0
        else: M.append([s0, e0])
    segs = [[max(0, s0 / 100 - pad_in), e0 / 100 + pad_out] for s0, e0 in M if e0 - s0 >= 6]
    for r0, r1 in sorted(remove):
        out = []
        for s0, e0 in segs:
            if e0 <= r0 or s0 >= r1: out.append([s0, e0]); continue
            if s0 < r0: out.append([s0, r0])
            if e0 > r1: out.append([r1, e0])
        segs = out
    segs = [x for x in segs if x[1] - x[0] > 0.08]
    hard = {round(r1, 3) for _, r1 in remove}
    merged = []
    for s0, e0 in segs:
        if merged and s0 - merged[-1][1] < maxgap and round(s0, 3) not in hard: merged[-1][1] = e0
        else: merged.append([s0, e0])
    return [[round(s0, 3), round(e0, 3)] for s0, e0 in merged]

def face_eye(raw, P):
    import cv2
    casc = getattr(cv2, "CascadeClassifier", None)
    f = np.frombuffer(subprocess.run([FFMPEG, "-v", "error", "-i", raw, "-vf", f"fps=12/{P['dur']}", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout, np.uint8)
    f = f[:len(f) // (P['w'] * P['h']) * P['w'] * P['h']].reshape(-1, P['h'], P['w'])
    pts = []
    if casc is not None:
        c = casc(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        for g in f:
            fs = c.detectMultiScale(g, 1.1, 5, minSize=(P['w'] // 8, P['w'] // 8))
            if len(fs):
                x, y, w, h = max(fs, key=lambda r: r[2] * r[3]); pts.append((x + w / 2, y + 0.40 * h, w))
    if pts:
        a = np.median(np.array(pts), 0); return dict(eye=[int(a[0]), int(a[1])], face_w=int(a[2]), detected=len(pts))
    return dict(eye=[P['w'] // 2, int(P['h'] * 0.30)], face_w=0, detected=0)

def grid(raw, P, out):
    t = [P['dur'] * k / 5 for k in (0.5, 1.5, 2.5, 3.5, 4.5)]
    fl = ";".join(f"[0:v]trim=start={x:.2f},setpts=PTS-STARTPTS,select=eq(n\\,0),scale=270:-2,drawbox=x=0:y=ih*0.30-1:w=iw:h=2:color=yellow@0.6[f{i}]" for i, x in enumerate(t))
    r = sh([FFMPEG, "-v", "error", "-y", "-i", raw, "-filter_complex", fl + ";" + "".join(f"[f{i}]" for i in range(5)) + "hstack=inputs=5[o]", "-map", "[o]", "-frames:v", "1", out])
    if r.returncode:  # no drawbox filter → plain tile
        sh([FFMPEG, "-v", "error", "-y", "-i", raw, "-vf", f"fps=5/{P['dur']},scale=270:-2,tile=5x1", "-frames:v", "1", out])

def main():
    raw, wd = sys.argv[1], sys.argv[2]; os.makedirs(wd, exist_ok=True)
    model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "small"
    P = probe(raw); wav = os.path.join(wd, "a16.wav")
    sh([FFMPEG, "-v", "error", "-y", "-i", raw, "-ac", "1", "-ar", "16000", wav])
    if "--no-tx" not in sys.argv and not os.path.exists(os.path.join(wd, "words.json")):
        try:
            words, lang = transcribe(wav, model); P["lang"] = lang
            json.dump(words, open(os.path.join(wd, "words.json"), "w"))
        except Exception as e:
            print("TRANSCRIBE_FAILED:", str(e)[:120], "→ ask user for transcript, then: align_text.py"); words = []
    else:
        words = json.load(open(os.path.join(wd, "words.json"))) if os.path.exists(os.path.join(wd, "words.json")) else []
    spans, why, sugg = bad_spans(words)
    if "--remove" in sys.argv: spans += json.loads(sys.argv[sys.argv.index("--remove") + 1]); why.append("+manual")
    segs = speech_segments(wav, spans)
    P.update(face_eye(raw, P)); json.dump(P, open(os.path.join(wd, "probe.json"), "w"))
    json.dump(segs, open(os.path.join(wd, "segments.json"), "w"))
    grid(raw, P, os.path.join(wd, "frames.jpg"))
    kept = sum(e - s for s, e in segs)
    print(f"RAW {P['w']}x{P['h']} {P['fps']}fps {P['dur']}s | eye={P['eye']} faces={P['detected']} | clean {P['dur']}s→{kept:.1f}s in {len(segs)} segs")
    print("REMOVED:", "; ".join(why) if why else "silences only")
    print("CHECK (soft fillers / low-confidence / long pauses; remove bad takes with --remove '[[s,e],..]'):", " ".join(sugg)[:900] or "-")
    if "--remove" not in sys.argv: print("TEXT:", " ".join(f"{w['w']}" + (f"@{w['s']}" if i % 8 == 0 else "") for i, w in enumerate(words)))
    G = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "genre_matrix.json")))
    print("NICHES:", " | ".join(f"{g['no']}.{g['niche'].split(' /')[0]}" for g in G["genres"]))

if __name__ == "__main__":
    main()
