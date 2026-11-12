"""Audio: cleaned voice + licensed music bed + SFX → -14 LUFS, then mux with WORKDIR/video.mp4 → final.mp4.
python mix.py WORKDIR
spec.audio = {"music": "music_123.mp3", "music_offset": "auto"|sec, "music_db": -18, "payoff": "phrase",
              "voice": "clean"|"podcast", "sfx": {"in": "sfx_1.mp3", "out": "sfx_2.mp3", "item": "sfx_3.mp3", "payoff": "sfx_4.mp3"},
              "sfx_extra": [{"file": "...", "at": "phrase", "db": -26}]}
Levels (relative to voice): music -16..-20 dB, transition whoosh -26, item pops -31, payoff chime -27 (barely noticed)."""
import os, sys, json, subprocess, wave
import numpy as np
from scipy.signal import butter, sosfilt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ff import FFMPEG, probe as ffprobe_info
sys.argv += ["--plan"] if "--plan" not in sys.argv else []
WD = sys.argv[1]
import importlib.util
spec_ = importlib.util.spec_from_file_location("engine", os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine.py"))
E = importlib.util.module_from_spec(spec_); sys.argv = [sys.argv[0], WD, "--plan"]; spec_.loader.exec_module(E)
E.plan_captions(); E.plan_layers()
A = E.SPEC.get("audio", {}); SR = 48000; tl = E.tl; N = int(tl.dur * SR) + 1
def P(f): return f if os.path.isabs(f) else os.path.join(WD, f)
def load(f, ss=0.0, dur=None):
    cmd = [FFMPEG, "-v", "error", "-ss", str(ss)] + (["-t", str(dur)] if dur else []) + ["-i", P(f), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).astype(np.float64).reshape(-1, 2)
def rms_gain(x, target):
    m = x.mean(1); m = m[np.abs(m) > 1e-4]; return 10 ** ((target - 20 * np.log10(np.sqrt(np.mean(m ** 2)) + 1e-12)) / 20) if len(m) else 1.0
def fade(x, fi, fo):
    x = x.copy(); a, b = int(fi * SR), int(fo * SR)
    if a and len(x) > a: x[:a] *= np.linspace(0, 1, a)[:, None]
    if b and len(x) > b: x[-b:] *= np.linspace(1, 0, b)[:, None]
    return x
def place(buf, x, t, db):
    i = int(max(0, t) * SR); n = min(len(x), len(buf) - i)
    if n > 0: buf[i:i + n] += x[:n] * rms_gain(x, -20) * 10 ** (db / 20)

# voice: concat kept segments with micro-fades, light cleanup chain
parts = [f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,afade=t=in:d=0.012,afade=t=out:st={b - a - 0.015:.3f}:d=0.015[a{i}]" for i, (a, b) in enumerate(tl.segs)]
chain = {"clean": "highpass=f=80,afftdn=nr=8:nf=-42,equalizer=f=250:t=q:w=1.2:g=-1.5,equalizer=f=3500:t=q:w=1.5:g=2,acompressor=threshold=-22dB:ratio=2.5:attack=8:release=120:makeup=2dB,deesser=i=0.3",
         "podcast": "highpass=f=70,afftdn=nr=6:nf=-45,equalizer=f=180:t=q:w=1:g=1.5,equalizer=f=3000:t=q:w=1.5:g=2.5,acompressor=threshold=-20dB:ratio=3:attack=5:release=100:makeup=3dB,deesser=i=0.35"}[A.get("voice", "clean")]
fc = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1,{chain}[v]"
raw = subprocess.run([FFMPEG, "-v", "error", "-i", E.RAW, "-filter_complex", fc, "-map", "[v]", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
if raw.returncode:  # afftdn/deesser missing in some ffmpeg builds → simpler chain
    fc = fc.replace(chain, "highpass=f=80,acompressor=threshold=-22dB:ratio=2.5:attack=8:release=120:makeup=2dB")
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", E.RAW, "-filter_complex", fc, "-map", "[v]", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True)
v = np.frombuffer(raw.stdout, np.float32).astype(np.float64); voice = np.zeros((N, 2)); voice[:min(N, len(v)), 0] = v[:N]; voice[:, 1] = voice[:, 0]
mix = voice.copy()

if A.get("music"):
    off = A.get("music_offset", "auto")
    if off == "auto":   # choose offset so a musical phrase onset lands on the payoff (or at the start)
        tp = E.phrase_time(A["payoff"], hint=0) if A.get("payoff") else 0.0
        full = load(A["music"]).mean(1); hop = int(SR * 0.05); n = len(full) // hop
        db = 20 * np.log10(np.sqrt(np.mean(full[:n * hop].reshape(n, hop) ** 2, 1)) + 1e-9); on = np.maximum(0, np.diff(db, prepend=db[0]))
        best, off = -1e9, 0.0
        for s in np.arange(0.0 if len(full) / SR < tl.dur + 3 else 2.0, max(0.1, len(full) / SR - tl.dur - 1), 0.05):
            ip = int((s + tp) / 0.05); i0 = int(s / 0.05)
            if ip + 20 >= n: break
            sc = on[ip - 1:ip + 2].max() + 0.6 * (db[ip:ip + 20].mean() - db[max(i0, ip - 30):ip].mean()) - 0.15 * db[i0:i0 + 20].std()
            if sc > best: best, off = sc, s
    m = load(A["music"], off, tl.dur + 0.5)[:N]
    if len(m) < N:   # short track (loops in the CC0 pack) → loop it with a 1.5 s crossfade instead of going silent
        full = load(A["music"]); xf = int(1.5 * SR); out = m.copy()
        while len(out) < N:
            seg = full.copy(); k = min(xf, len(out), len(seg))
            out[-k:] = out[-k:] * np.linspace(1, 0, k)[:, None] + seg[:k] * np.linspace(0, 1, k)[:, None]
            out = np.vstack([out, seg[k:]])
        m = out[:N]
    m = fade(m, 0.6, 0.9)
    lp = sosfilt(butter(2, 5, "lp", fs=SR, output="sos"), voice[:, 0] ** 2); duck = 1 - 0.30 * np.clip(np.sqrt(np.maximum(lp, 0)) / 0.04, 0, 1)
    mix += m * duck[:, None] * rms_gain(m, -20) * 10 ** (A.get("music_db", -18) / 20)
    print(f"music offset {off:.2f}s")

S = A.get("sfx", {})
def sfx(kind, t, db, trim=None):
    if kind in S and S[kind]:
        x = load(S[kind]); x = x[:int((trim or 0.9) * SR)]; place(mix, fade(x, 0.004, 0.12), t, db)
for L in E.CARDS: sfx("in", L["a"] - 0.22, -26); sfx("out", L["b"] - 0.1, -30)
for B in E.BROLL: sfx("in", B["a"] - 0.22, -28)
for L in E.CARDS + E.OVERS:
    d = L.get("data", {})
    if L["type"] in ("list", "checklist", "steps", "cycle", "timeline") and d.get("items"):
        for tt in E.item_times(L, d["items"], L["a"], L["b"]): sfx("item", tt - 0.02, -31, 0.4)
if A.get("payoff"): sfx("payoff", E.phrase_time(A["payoff"], hint=0), -27, 2.0)
for x in A.get("sfx_extra", []): place(mix, fade(load(x["file"])[:int(x.get("len", 2) * SR)], 0.004, 0.12), E.phrase_time(x["at"], hint=0), x.get("db", -26))

mix[-int(0.1 * SR):] *= np.linspace(1, 0, int(0.1 * SR))[:, None]; mix /= max(1.0, np.abs(mix).max() / 0.95)
pre = os.path.join(WD, "mix_pre.wav")
with wave.open(pre, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
r = subprocess.run([FFMPEG, "-v", "info", "-i", pre, "-af", "loudnorm=I=-14:TP=-1.2:LRA=7:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
js = json.loads(r[r.rfind("{"):r.rfind("}") + 1])
af = f"loudnorm=I=-14:TP=-1.2:LRA=7:measured_I={js['input_i']}:measured_TP={js['input_tp']}:measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true"
subprocess.run([FFMPEG, "-v", "error", "-y", "-i", pre, "-af", af, "-ar", "48000", os.path.join(WD, "mix.wav")], check=True)
out = os.path.join(WD, E.SPEC.get("out", "final.mp4"))
subprocess.run([FFMPEG, "-v", "error", "-y", "-i", os.path.join(WD, "video.mp4"), "-i", os.path.join(WD, "mix.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out], check=True)
print(out)
