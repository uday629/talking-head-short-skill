"""Render engine for talking-head shorts. Driven by WORKDIR/spec.json (see references/spec.md).
python engine.py WORKDIR --plan                 → timing/fit/safe-zone checks only (fast, run first)
python engine.py WORKDIR --frames 1.2,5.0,9.4   → styleframes → WORKDIR/styleframes.jpg (one contact image)
python engine.py WORKDIR --render [--part i/N]  → WORKDIR/video.mp4 (or video.partI.mp4; then --concat N)
Design rules baked in (from the user's corrections): golden-ratio lockups, tight proximity, composed layouts,
captions never cut off, eased eye-locked camera, cards snap off raw cuts, every animation completes."""
import os, sys, json, math, re, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ff import FFMPEG, probe as ffprobe_info

W, H, FPS = 1080, 1920, 30
PHI = 1.618
ASSETS = os.environ.get("THS_ASSETS", os.path.expanduser("~/.ths_assets"))

# ───────────────────────── easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def smooth(x): x = clamp(x); return x * x * (3 - 2 * x)
def eout(x): x = clamp(x); return 1 - (1 - x) ** 3
def eio(x): x = clamp(x); return 0.5 - 0.5 * math.cos(math.pi * x)
def bout(x, s=1.4): x = clamp(x) - 1; return x * x * ((s + 1) * x + s) + 1
def prog(t, t0, d): return clamp((t - t0) / max(1e-6, d))
def hexc(h): h = h.lstrip("#"); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255
def norm(w): return re.sub(r"[^a-z0-9$%']", "", w.lower())

# ───────────────────────── spec / timeline
WD = sys.argv[1]
SPEC = json.load(open(os.path.join(WD, "spec.json")))
PROBE = json.load(open(os.path.join(WD, "probe.json")))
WORDS = json.load(open(os.path.join(WD, "words.json")))
SEGS = SPEC.get("segments") or json.load(open(os.path.join(WD, "segments.json")))
RAW = SPEC.get("raw") or SPEC["src"]

# look.json (from look.py) is this video's own design system: palette, fonts, card background texture,
# transition set and caption case. When present it overrides spec.palette/spec.fonts so every video that
# runs look.py gets a different, footage/genre-matched system instead of one fixed default.
LOOK = json.load(open(os.path.join(WD, "look.json"))) if os.path.exists(os.path.join(WD, "look.json")) else None
if LOOK:
    c = LOOK["colors"]
    SPEC["palette"] = dict(primary=c["mid"], secondary=c["sec"], **{"3rd": c["cap_text"], "4th": c["cap_acc"]}, card_bg=c["bg"])
    f = LOOK["fonts"]
    SPEC["fonts"] = dict(lead=f["lead"], key=f["key"], acc=f["acc"], acc_italic=f.get("acc_italic", False), key_italic=f.get("key_italic", False))
BGKIND = LOOK["bg"] if LOOK else "paper"
UPCASE = {"key"} if (LOOK and LOOK.get("case") == "upper") else set()
TRANS_ALIAS = {"push": "zoom", "whip": "zoom", "tilt3d": "zoom", "iris": "zoom", "peel": "blur", "glitch": "blur", "stamp": "pop",
               "parallax": "zoom", "orbit": "zoom", "mask": "blur"}

class TL:
    def __init__(s, segs):
        s.segs = segs; s.out = []; o = 0.0
        for a, b in segs: s.out.append((o, a, b)); o += b - a
        s.dur = o; s.n = int(round(o * FPS)); s.starts = [x[0] for x in s.out]
    def src(s, t):
        for o, a, b in s.out:
            if t < o + (b - a) - 1e-9: return a + t - o
        o, a, b = s.out[-1]; return min(b, a + t - o)
    def o(s, ts):
        for o, a, b in s.out:
            if a - 0.08 <= ts <= b + 0.02: return max(o, o + ts - a)
        for o, a, b in s.out:
            if ts < a: return o
        return s.dur
    def seg_at(s, t): return max(k for k, x in enumerate(s.starts) if x <= t + 1e-6)
tl = TL(SEGS)
OW = [dict(w=w["w"], n=norm(w["w"]), t=tl.o(w["s"]), e=tl.o(w["e"]), s=w["s"]) for w in WORDS]
OW = [w for w in OW if any(a - 0.05 <= w["s"] <= b for a, b in SEGS)]  # words that survived the clean cut

_ptr = [0]
def _score(j, toks):
    k, hit, first = j, 0, None
    for tk in toks:
        m = next((m for m in range(k, min(len(OW), k + 4)) if OW[m]["n"] == tk), None)
        if m is not None: hit += 1; k = m + 1; first = m if first is None else first
    return hit
def locate(text, start_hint=None):
    """map caption words → output times by matching the transcript (best in-order match from the pointer)."""
    toks = [norm(x) for x in text.split() if norm(x)]
    if not toks: return []
    i0 = _ptr[0] if start_hint is None else next((k for k, w in enumerate(OW) if w["t"] >= start_hint - 0.05), 0)
    need = max(1, int(math.ceil(0.6 * len(toks))))
    best = next((j for j in range(i0, len(OW)) if OW[j]["n"] in toks[:2] and _score(j, toks) >= need), None)
    if best is None: best = next((j for j in range(0, len(OW)) if OW[j]["n"] in toks[:2] and _score(j, toks) >= need), None)
    if best is None: return [None] * len(toks)
    out, k = [], best
    for tk in toks:
        hit = next((m for m in range(k, min(len(OW), k + 4)) if OW[m]["n"] == tk), None)
        if hit is not None: out.append(OW[hit]["t"]); k = hit + 1
        else: out.append(None)
    known = [(i, v) for i, v in enumerate(out) if v is not None]
    for i in range(len(out)):
        if out[i] is None:
            prev = max((p for p in known if p[0] < i), default=None, key=lambda p: p[0]); nxt = min((p for p in known if p[0] > i), default=None, key=lambda p: p[0])
            out[i] = prev[1] + 0.18 * (i - prev[0]) if prev else nxt[1] - 0.18 * (nxt[0] - i)
    if start_hint is None: _ptr[0] = k
    return out

def phrase_time(ph, end=False, hint=None):
    ts = locate(ph, hint)
    if not ts or ts[0] is None: raise SystemExit(f"phrase not found in transcript: '{ph}'")
    if end:
        last = norm(ph.split()[-1]); cand = [w for w in OW if w["n"] == last and abs(w["t"] - ts[-1]) < 0.05]
        return (cand[0]["e"] if cand else ts[-1] + 0.3)
    return ts[0]
def _unused():
    return ts[0]

# ───────────────────────── palette / fonts
PAL = {k: hexc(v) for k, v in SPEC["palette"].items()}
TEXT, ACC, SEC = PAL["3rd"], PAL["4th"], PAL["secondary"]
CARD = PAL.get("card_bg", PAL["primary"])
DIM = TEXT * 0.55 + CARD * 0.45
COL = {"text": TEXT, "accent": ACC, "secondary": SEC, "dim": DIM, "primary": PAL["primary"]}
FALLBACK = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Helvetica.ttc"]

def font_file(family, italic):
    d = os.path.join(ASSETS, "fonts", family.lower().replace(" ", ""))
    if os.path.isdir(d):
        fs = sorted(f for f in os.listdir(d) if f.endswith(".ttf"))
        it = [f for f in fs if "Italic" in f]; up = [f for f in fs if "Italic" not in f]
        pick = (it or up) if italic else (up or it)
        var = [f for f in pick if "[" in f]
        return os.path.join(d, (var or pick)[0])
    for f in FALLBACK:
        if os.path.exists(f): return f
    raise SystemExit("no font for " + family)

_fc = {}
def font(role, size):
    spec = SPEC["fonts"][role]; fam, wght = spec[0], spec[1] if len(spec) > 1 else 400
    italic = SPEC["fonts"].get(role + "_italic", False)
    k = (role, int(size))
    if k in _fc: return _fc[k]
    f = ImageFont.truetype(font_file(fam, italic), int(size))
    try:
        axes = f.get_variation_axes(); vals = []
        for ax in axes:
            nm = ax["name"] if isinstance(ax["name"], str) else ax["name"].decode()
            v = wght if nm.lower().startswith("weight") or nm == "wght" else (min(ax["maximum"], max(ax["minimum"], size * 0.75)) if "optical" in nm.lower() or nm == "opsz" else ax["default"])
            vals.append(max(ax["minimum"], min(ax["maximum"], v)))
        f.set_variation_by_axes(vals)
    except Exception: pass
    _fc[k] = f; return f
def xh(role, size): return -font(role, size).getbbox("x", anchor="ls")[1]
def caph(role, size): return -font(role, size).getbbox("H", anchor="ls")[1]
def size_for_xh(role, target): return max(18, int(round(target * 100 / max(1, xh(role, 100)))))

_sc = {}
def sprite(txt, role, size, track=0.0):
    if role in UPCASE: txt = txt.upper()          # display-only (word matching already used the lowercase form)
    k = (txt, role, int(size), track)
    if k in _sc: return _sc[k]
    f = font(role, size); pad = int(size * 0.35) + 8; asc, desc = f.getmetrics()
    ws = [f.getlength(c) for c in txt]
    kern = [f.getlength(txt[i:i + 2]) - ws[i] - ws[i + 1] for i in range(len(txt) - 1)] + [0]
    tw = int(sum(ws) + sum(kern) + track * size * (len(txt) - 1)) + 4
    m = Image.new("L", (tw + 2 * pad, asc + desc + 2 * pad), 0); d = ImageDraw.Draw(m); x = pad
    for i, c in enumerate(txt):
        d.text((x, pad + asc), c, font=f, fill=255, anchor="ls"); x += ws[i] + kern[i] + track * size
    a = np.asarray(m, np.float32) / 255
    sh = np.roll(cv2.GaussianBlur(a, (0, 0), max(2.5, size * 0.035)), int(max(2, size * 0.02)), axis=0)
    r = dict(a=a, sh=sh, tw=tw, pad=pad, asc=asc); _sc[k] = r; return r

def blit(fr, a, x0, y0, col, alpha, sh=None, sh_amt=0.45):
    h, w = a.shape; fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if fx0 >= fx1 or fy0 >= fy1 or alpha <= 0.003: return
    A = a[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0][..., None] * alpha
    reg = fr[fy0:fy1, fx0:fx1]
    if sh is not None: reg *= 1 - sh[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0][..., None] * alpha * sh_amt
    reg *= 1 - A; reg += A * col

def width(words, role, size, gap):
    return sum(sprite(w, role, size)["tw"] for w in words) + gap * size * (len(words) - 1)

ANIM_DUR = {"rise": 0.34, "blur": 0.42, "pop": 0.30, "type": 0.0, "write": 0.0}
def draw_words(fr, words, times, x, base, t, role, size, col, anim="rise", fade=1.0, gap=0.24):
    for w, ta in zip(words, times):
        sp = sprite(w, role, size)
        if anim == "type":
            n = len(w); k = clamp((t - ta) / max(0.02, 0.035 * n)); vis = int(math.ceil(k * n))
            if vis <= 0: x += sp["tw"] + gap * size; continue
            sub = sprite(w[:vis], role, size); blit(fr, sub["a"], int(x - sub["pad"]), int(base - sub["asc"] - sub["pad"]), col, fade, sub["sh"])
            x += sp["tw"] + gap * size; continue
        p = prog(t, ta - 0.03, ANIM_DUR.get(anim, 0.34))
        if p > 0:
            a, sh = sp["a"], sp["sh"]; dy = 0
            if anim == "rise": dy = 0.10 * size * (1 - eout(p)); bl = 4 * (1 - eout(p))
            elif anim == "blur": bl = 9 * (1 - eout(p))
            elif anim == "pop":
                s = 0.82 + 0.18 * bout(p, 1.6); a = cv2.resize(a, None, fx=s, fy=s); sh = cv2.resize(sh, None, fx=s, fy=s); bl = 0
            else: bl = 0
            if bl > 0.6: a = cv2.GaussianBlur(a, (0, 0), bl)
            h_, w_ = a.shape; cx = x + sp["tw"] / 2; cy = base - sp["asc"] - sp["pad"] + sp["a"].shape[0] / 2
            blit(fr, a, int(cx - w_ / 2), int(cy - h_ / 2 + dy), col, smooth(p) * fade, sh)
        x += sp["tw"] + gap * size

def write_on(fr, text, x, base, t, t0, dur, role, size, col, fade=1.0):
    sp = sprite(text, role, size); p = prog(t, t0, dur)
    if p <= 0: return
    a = sp["a"]; w = a.shape[1]; edge = sp["pad"] + eio(p) * (sp["tw"] + 12)
    ramp = np.clip((edge - np.arange(w)) / 22.0, 0, 1)[None, :]
    blit(fr, a * ramp, int(x - sp["pad"]), int(base - sp["asc"] - sp["pad"]), col, fade, sp["sh"] * ramp)

# ───────────────────────── lockup (lead / KEY / accent)
def lockup_geom(lead, key, acc, layout, key_w, maxsize):
    """returns sizes/positions; enforces golden ratio, proximity, width rules."""
    ks = 200; kw = width(key, "key", ks, 0.22); KS = int(min(maxsize, ks * key_w / kw))
    kx = xh("key", KS); kc = caph("key", KS); kw = width(key, "key", KS, 0.22)
    LS = size_for_xh("lead", kx / PHI) if lead else 0
    if lead:
        while width(lead, "lead", LS, 0.28) > kw * 1.0 and LS > size_for_xh("lead", kx / PHI ** 2): LS -= 2
    AS = size_for_xh("acc", kx / PHI * 1.08) if acc else 0
    if acc:
        while width(acc, "acc", AS, 0.22) > kw * 1.05 and AS > 30: AS -= 2
    if layout == "I" and lead and width(lead, "lead", LS, 0.28) + 0.18 * KS + kw > 0.88 * W:
        layout = "L"
    return dict(KS=KS, kw=kw, kx=kx, kc=kc, LS=LS, AS=AS, layout=layout)

def lockup(fr, t, cap, cy, fade=1.0, key_w=None):
    g = cap["_g"]; KS, kw, kx, kc, LS, AS, lay = g["KS"], g["kw"], g["kx"], g["kc"], g["LS"], g["AS"], g["layout"]
    base = cy + kc / 2
    lw = width(cap["lead"], "lead", LS, 0.28) if cap["lead"] else 0
    if lay == "I":
        x0 = W / 2 - (lw + 0.18 * KS + kw) / 2
        draw_words(fr, cap["lead"], cap["lt"], x0, base, t, "lead", LS, cap["lcol"], cap["la"], fade, 0.28)
        kx0 = x0 + lw + 0.18 * KS
    else:
        kx0 = W / 2 - kw / 2
        if cap["lead"]:
            lx = {"L": kx0 + 0.03 * kw, "R": kx0 + kw - lw - 0.03 * kw, "C": W / 2 - lw / 2, "O": kx0 + 0.28 * kw}[lay]
            lx = min(max(lx, kx0), kx0 + kw - lw) if lw <= kw else W / 2 - lw / 2
            draw_words(fr, cap["lead"], cap["lt"], lx, base - kc - 0.20 * kx, t, "lead", LS, cap["lcol"], cap["la"], fade, 0.28)
    if cap["ka"] == "write":
        write_on(fr, " ".join(cap["key"]), kx0, base, t, cap["kt"][0], cap["wdur"], "key", KS, cap["kcol"], fade)
    else:
        draw_words(fr, cap["key"], cap["kt"], kx0, base, t, "key", KS, cap["kcol"], cap["ka"], fade, 0.22)
    if cap["acc"]:
        aw = width(cap["acc"], "acc", AS, 0.22)
        ax = {"L": kx0 + kw - aw, "R": kx0, "C": W / 2 - aw / 2, "O": kx0 + kw - aw, "I": kx0 + kw - aw}[lay]
        ab = base + 0.42 * kx + (-font("acc", AS).getbbox("x", anchor="ls")[1]) * 1.6   # clears key descenders
        if cap["aa"] == "write": write_on(fr, " ".join(cap["acc"]), ax, ab, t, cap["at"][0], cap["adur"], "acc", AS, cap["acol"], fade)
        else: draw_words(fr, cap["acc"], cap["at"], ax, ab, t, "acc", AS, cap["acol"], "rise", fade, 0.22)
    return kx0, base - kc - (LS * 1.2 if cap["lead"] else 0), kw, kc + (LS * 1.4 if cap["lead"] else 0) + (AS * 1.6 if cap["acc"] else 0)

# ───────────────────────── caption planning
TI, TO = 0.42, 0.38
TONE = SPEC.get("tone", "balanced")
CAPY = SPEC.get("caption_y", 0.62)
ISSUES = []
CAPS = []
def plan_captions():
    cyc = ["L", "R", "C", "O"]
    for i, c in enumerate(SPEC.get("captions", [])):
        lead = c.get("lead", "").split() if c.get("lead") else []
        key = c["key"].split(); acc = c.get("acc", "").split() if c.get("acc") else []
        hint = tl.o(c["t"][0]) if "t" in c else None
        ts = locate(" ".join(lead + key + (acc if c.get("acc_spoken", True) else [])), hint)
        nl, nk = len(lead), len(key)
        lt, kt = ts[:nl], ts[nl:nl + nk]
        at = ts[nl + nk:] if c.get("acc_spoken", True) and acc else [kt[-1] + 0.25] * len(acc)
        if None in lt + kt: ISSUES.append(f"caption {i} '{c['key']}' not found in transcript"); continue
        layout = c.get("layout") or ("I" if len(" ".join(lead)) <= 4 and lead else cyc[i % 4])
        g = lockup_geom(lead, key, acc, layout, c.get("key_w", 0.64) * W, c.get("max", 210))
        ka = c.get("anim") or {"calm": "blur", "balanced": "rise", "energetic": "pop"}[TONE]
        if ka == "write" and len(" ".join(key)) > 16: ka = "rise"
        cap = dict(i=i, lead=lead, key=key, acc=acc, lt=lt, kt=kt, at=at, _g=g, ka=ka, la="rise", aa=c.get("acc_anim", "write" if acc else "rise"),
                   kcol=COL[c.get("kc", "text")], lcol=TEXT * 0.92 + 0.08, acol=COL[c.get("ac", "accent")], y=c.get("y", CAPY),
                   wdur=min(0.9, 0.045 * len(" ".join(key)) + 0.2), adur=min(1.0, 0.04 * len(" ".join(acc)) + 0.25), raw=c)
        cap["start"] = min(lt + kt) - 0.06
        last = max(lt + kt + (at if acc else []))
        done = last + max(ANIM_DUR.get(ka, 0.34), cap["wdur"] if ka == "write" else 0, cap["adur"] if acc else 0)
        cap["need"] = done + 0.30          # animation finished + read time (user rule: ≥0.3s)
        cap["end_nat"] = last + 1.2
        CAPS.append(cap)
    CAPS.sort(key=lambda c: c["start"])
    for a, b in zip(CAPS, CAPS[1:]):
        a["end"] = max(a["need"], min(a["end_nat"], b["start"])) if b["start"] >= a["need"] else a["need"]
        if b["start"] < a["need"]:
            shift = a["need"] - b["start"]
            if shift > 0.45: ISSUES.append(f"caption '{' '.join(a['key'])}' needs {shift:.2f}s more → shorten text or merge beats")
            b["start"] = a["need"]
    if CAPS: CAPS[-1]["end"] = min(tl.dur, max(CAPS[-1]["need"], CAPS[-1]["end_nat"]))
    for c in CAPS:
        c["end"] = min(c["end"], tl.dur)
        if c["end"] < c["need"] - 0.02: ISSUES.append(f"caption '{' '.join(c['key'])}' cut by video end (need {c['need']:.2f}, end {c['end']:.2f})")

# ───────────────────────── cards / overlays / broll windows
_wh = [0.0]
def window(item):
    if "t" in item: a, b = tl.o(item["t"][0]), tl.o(item["t"][1])
    else:
        a = phrase_time(item["at"][0], hint=_wh[0]); b = phrase_time(item["at"][1], end=True, hint=a) + item.get("hold", 0.45)
    _wh[0] = a + 0.1
    return a, min(b, tl.dur)
def snap(a, b, tr=0.42):
    for s in tl.starts[1:]:
        if a < s < a + tr: a = s + 0.01
        if b < s < b + tr: b = s
    return a, b
CARDS, OVERS, BROLL = [], [], []
def plan_layers():
    for kind, lst, sn in (("cards", CARDS, True), ("overlays", OVERS, False), ("broll", BROLL, True)):
        _wh[0] = 0.0
        for c in SPEC.get(kind, []):   # list items in spoken order: each search starts after the previous one
            a, b = window(c); a, b = snap(a, b) if sn else (a, b); lst.append(dict(c, a=a, b=b))
    CARDS.sort(key=lambda x: x["a"])
    for p_, n_ in zip(CARDS, CARDS[1:]):          # back-to-back cards → chain (card→card dissolve, no face flash)
        if n_["a"] - p_["b"] < TO + 0.15:
            p_["b"] = n_["a"]; n_["chain"] = p_; p_["chained"] = True
    for L in CARDS:   # small edge overlaps resolve themselves: card ends where the next beat starts; captions fade under the in-transition
        for c in CAPS:
            if L["b"] - 0.7 < c["start"] < L["b"] and c["start"] > L["a"] + 1.6 and not L.get("chained"): L["b"] = c["start"]
    for L in CARDS:
        for c in CAPS:
            if c["start"] < L["b"] - 0.05 and c["end"] > L["a"] + TI and not L.get("show_captions"):
                ISSUES.append(f"caption '{' '.join(c['key'])}' overlaps card {L['type']} → it will be hidden; move it into the card or drop it")
        if L["b"] - L["a"] < 1.6: ISSUES.append(f"card {L['type']} only {L['b']-L['a']:.1f}s → too short to read")
    seen = set()
    for x in CARDS + BROLL:
        for y in CARDS + BROLL:
            if x is not y and x["a"] < y["b"] - 0.01 and y["a"] < x["b"] - 0.01 and (id(y), id(x)) not in seen:
                seen.add((id(x), id(y))); ISSUES.append(f"layers overlap: {x.get('type','broll')} & {y.get('type','broll')}")

# ───────────────────────── frame sources
class Reader:
    def __init__(s, path):
        s.path = path; j = ffprobe_info(path)
        s.w, s.h, s.fps = j["w"], j["h"], j["fps"]; s.p = None; s.cur = -1; s.last = None
    def _open(s, i):
        if s.p: s.p.kill()
        s.p = subprocess.Popen([FFMPEG, "-v", "error", "-ss", f"{i / s.fps:.4f}", "-i", s.path, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10 ** 8)
        s.cur = i - 1
    def get(s, t):
        i = max(0, int(round(t * s.fps)))
        if s.p is None or i < s.cur or i > s.cur + 90: s._open(i)
        while s.cur < i:
            b = s.p.stdout.read(s.w * s.h * 3)
            if len(b) < s.w * s.h * 3: return s.last
            s.last = np.frombuffer(b, np.uint8).reshape(s.h, s.w, 3); s.cur += 1
        return s.last

RD = Reader(RAW)
def auto_params():
    fr = []
    for k in range(5):
        r = subprocess.run([FFMPEG, "-v", "error", "-ss", f"{PROBE['dur'] * (k + 0.5) / 5:.2f}", "-i", RAW, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        if len(r) == RD.w * RD.h * 3: fr.append(np.frombuffer(r, np.uint8).reshape(RD.h, RD.w, 3))
    sel = np.stack(fr).astype(np.float32) / 255
    Y = 0.2126 * sel[..., 0] + 0.7152 * sel[..., 1] + 0.0722 * sel[..., 2]
    mx, mn = sel.max(-1), sel.min(-1); sat = (mx - mn) / np.maximum(mx, 1e-4)
    neutral = (sat < 0.10) & (Y > 0.12) & (Y < 0.85)
    ref = sel[neutral].mean(0) if neutral.sum() > 500 else sel.reshape(-1, 3).mean(0)
    g = ref.mean() / np.maximum(ref, 1e-4); g = 1 + (g - 1) * SPEC.get("grade", {}).get("wb", 0.6)
    return dict(gain=g.astype(np.float32), b_in=float(np.percentile(Y, 0.8)) - 0.012, w_in=float(np.percentile(Y, 99.7)) + 0.02)
GP = auto_params(); GR = SPEC.get("grade", {})
def grade(u8): return cc.correct(u8.astype(np.float32) / 255, GP, sat=GR.get("sat", 1.0), contrast=GR.get("contrast", 0.12), out_black=GR.get("black", 0.025))

# camera: eye-locked, eased zoom across cuts, gentle push inside takes
CAM = SPEC.get("camera", {})
EX, EY = CAM.get("eye", PROBE["eye"])
SB = max(W / RD.w, H / RD.h)
EYE_Y = CAM.get("eye_y", clamp(EY * SB / H, 0.28, 0.40))
ZMIN = max(W / 2 / (EX * SB), W / 2 / ((RD.w - EX) * SB), H * EYE_Y / (EY * SB), H * (1 - EYE_Y) / ((RD.h - EY) * SB)) + 0.002
ZOOMS = [max(ZMIN, z) for z in CAM.get("zooms", [1.0, 1.1])]
PUSH, EASE = CAM.get("push", 0.03), CAM.get("ease", 8) / FPS
def zoom_at(t):
    k = tl.seg_at(t); a = tl.starts[k]; b = tl.starts[k + 1] if k + 1 < len(tl.starts) else tl.dur
    zk = lambda j, u: ZOOMS[j % len(ZOOMS)] * (1 + PUSH * eio(u))
    z = zk(k, (t - a) / max(0.01, b - a))
    if k + 1 < len(tl.starts) and t > b - EASE / 2:   # approaching next cut: blend toward next take's zoom
        u = eio((t - (b - EASE / 2)) / EASE); z = z * (1 - u) + zk(k + 1, 0) * u
    if k > 0 and t < a + EASE / 2:
        u = eio((t - (a - EASE / 2)) / EASE); pa = tl.starts[k - 1]
        z = zk(k - 1, 1.0) * (1 - u) + zk(k, (t - a) / max(0.01, b - a)) * u
    return max(ZMIN, z)
VIG = np.clip(1 - 0.13 * (((np.mgrid[0:H, 0:W][1] - W / 2) / 760.0) ** 2 + ((np.mgrid[0:H, 0:W][0] - H * 0.43) / 1150.0) ** 2) ** 1.2, 0.5, 1)[..., None].astype(np.float32)
def plate(t):
    img = grade(RD.get(tl.src(t)))
    img = img + 0.35 * (img - cv2.GaussianBlur(img, (0, 0), 1.0))          # sharpen at source res (cheap)
    S = SB * zoom_at(t)
    M = np.array([[S, 0, W / 2 - S * EX], [0, S, H * EYE_Y - S * EY]], np.float32)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT) * VIG

_br = {}
def broll_frame(B, t):
    r = _br.setdefault(B["file"], Reader(os.path.join(WD, B["file"]) if not os.path.isabs(B["file"]) else B["file"]))
    u = prog(t, B["a"], B["b"] - B["a"]); ts = B.get("offset", 0) + (t - B["a"]) * B.get("speed", 1.0)
    img = r.get(ts).astype(np.float32) / 255
    l = img.mean(-1, keepdims=True); img = np.clip(l + (img - l) * GR.get("broll_sat", 0.92), 0, 1)
    S = max(W / r.w, H / r.h) * (1.02 + 0.05 * eio(u))
    M = np.array([[S, 0, W / 2 - S * r.w / 2], [0, S, H / 2 - S * r.h / 2]], np.float32)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT) * VIG

# ───────────────────────── card drawing kit
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
_rng = np.random.default_rng(7)
_noise = cv2.resize(cv2.GaussianBlur(_rng.normal(0, 1, (H // 3, W // 3)).astype(np.float32), (0, 0), 0.8), (W, H))[..., None]
_rr = np.clip(np.sqrt(((_xx - W / 2) / 820) ** 2 + ((_yy - H * 0.45) / 1150) ** 2), 0, 1)[..., None]
LIGHT_CARD = float(0.2126 * CARD[0] + 0.7152 * CARD[1] + 0.0722 * CARD[2]) > 0.5
INK = hexc(LOOK["colors"]["ink"]) if LOOK else (PAL["primary"] if LIGHT_CARD else TEXT)   # text color on cards

def _card_bg():
    """card canvas texture, varied by LOOK['bg'] so each design family reads differently, not just re-tinted."""
    if BGKIND == "block":                           # flat, no grain/vignette — bold kinetic / UI blocks
        return np.tile(CARD, (H, W, 1)).astype(np.float32)
    if BGKIND == "grid":                             # tech HUD / blueprint — faint rule grid on a dark/blue field
        g = (CARD * (1.08 - 0.22 * _rr)).astype(np.float32)
        step = 72; ln = ((_xx.astype(int) % step < 2) | (_yy.astype(int) % step < 2)).astype(np.float32)[..., None]
        return g + ln * ACC * 0.05 + _noise * 0.006
    if BGKIND == "film":                             # documentary / noir — darker vignette, heavier grain
        return (CARD * (1.0 - 0.42 * _rr) + _noise * 0.018).astype(np.float32)
    if BGKIND == "mesh":                             # soft two-tone diagonal gradient — UI/glass
        u = np.clip((_xx + _yy * 0.6) / (W + H * 0.6), 0, 1)[..., None]
        return CARD * (1 - 0.22 * u) + SEC * 0.18 * u + _noise * 0.006
    return (CARD * (1.12 - 0.30 * _rr) + _noise * 0.008).astype(np.float32)   # paper/frosted/solid/light default
CARD_BG = _card_bg()
def C(c): return tuple(float(v) for v in c)
def poly(img, pts, col, th, closed=False):
    if len(pts) < 2: return
    p = np.round(np.asarray(pts, np.float64) * 16).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(img, [p], closed, C(col), int(th), cv2.LINE_AA, shift=4)
def circle(img, c, r, col, th=-1): cv2.circle(img, (int(c[0] * 16), int(c[1] * 16)), int(r * 16), C(col), int(th), cv2.LINE_AA, shift=4)
def part(pts, k): n = int(round(len(pts) * clamp(k))); return pts[:max(0, n)]
def glow(fr, lay, amt=0.8, s=10):
    sm = cv2.GaussianBlur(cv2.resize(lay, (W // 2, H // 2), interpolation=cv2.INTER_AREA), (0, 0), s / 2)
    fr += cv2.resize(sm, (W, H)) * amt
def rrect(img, x0, y0, x1, y1, r, col, alpha=1.0):
    m = np.zeros((int(y1 - y0) + 2, int(x1 - x0) + 2), np.uint8); r = int(r)
    cv2.rectangle(m, (r, 0), (m.shape[1] - r, m.shape[0]), 255, -1); cv2.rectangle(m, (0, r), (m.shape[1], m.shape[0] - r), 255, -1)
    for cx, cy in ((r, r), (m.shape[1] - r, r), (r, m.shape[0] - r), (m.shape[1] - r, m.shape[0] - r)): cv2.circle(m, (cx, cy), r, 255, -1, cv2.LINE_AA)
    blit(img, m.astype(np.float32) / 255, int(x0), int(y0), col, alpha)
def text(fr, s, role, size, x, base, t, t0, col, align="l", anim="rise", fade=1.0, gap=0.24):
    ws = s.split(); w = width(ws, role, size, gap)
    lim = (W - 80 - x) if align == "l" else ((x - 80) if align == "r" else 2 * min(x - 60, W - 60 - x))
    while w > lim and size > 22: size -= 2; w = width(ws, role, size, gap)   # never run off-frame
    x0 = x if align == "l" else (x - w / 2 if align == "c" else x - w)
    draw_words(fr, ws, [t0 + 0.06 * i for i in range(len(ws))], x0, base, t, role, size, col, anim, fade, gap); return w
def item_times(card, items, a, b):
    """'at' phrase → time; else evenly spaced; all items land ≥0.6s before card end."""
    lo, hi = a + 0.35, b - 0.7
    out = []
    for i, it in enumerate(items):
        at = it.get("at") if isinstance(it, dict) else None
        tt = phrase_time(at, hint=a - 0.5) if at else lo + (hi - lo) * (i / max(1, len(items) - 1) if len(items) > 1 else 0)
        out.append(clamp(tt, lo, hi))
    return out
def label(it): return it["text"] if isinstance(it, dict) else str(it)

# ───────────────────────── templates (all share palette + fonts; content area y≈300..1600)
def T_statement(fr, t, c, d, a, b):
    cap = dict(lead=d.get("lead", "").split(), key=d["key"].split(), acc=d.get("acc", "").split(), la="rise", ka=c.get("anim", "rise"), aa="write",
               kcol=COL[d.get("kc", "accent")], lcol=INK, acol=COL[d.get("ac", "text")] if not LIGHT_CARD else PAL["secondary"])
    cap["_g"] = lockup_geom(cap["lead"], cap["key"], cap["acc"], d.get("layout", "C"), 0.74 * W, 260)
    n = len(cap["lead"]) + len(cap["key"])
    sc = clamp((b - a - 0.6) / 1.6, 0.45, 1.0)          # compress timing on short cards so everything lands before the end
    cap["lt"] = [a + (0.25 + 0.08 * i) * sc for i in range(len(cap["lead"]))]; cap["kt"] = [a + (0.5 + 0.1 * i) * sc for i in range(len(cap["key"]))]
    cap["at"] = [a + 0.95 * sc] * len(cap["acc"]); cap["wdur"] = 0.7 * sc; cap["adur"] = 0.75 * sc
    lockup(fr, t, cap, H * 0.47)
    k = eio(prog(t, a + 0.9, 0.7)); y = H * 0.47 + cap["_g"]["kc"] + 150
    poly(fr, [(W / 2 - 160 * k, y), (W / 2 + 160 * k, y)], ACC, 3)

def T_list(fr, t, c, d, a, b, overlay=False):
    items = d["items"]; ts = item_times(c, items, a, b)
    size = d.get("size", 58 if overlay else 64); dy = size * 1.75
    x0 = 120 if overlay else 170; y0 = (H * 0.56 if overlay else H * 0.5) - dy * (len(items) - 1) / 2
    fade = 1 - prog(t, b - 0.25, 0.25)
    if overlay:
        m = np.exp(-(((_xx[:1, :] - 380) / 470) ** 2))[0][None, :, None] * np.exp(-(((_yy[:, :1] - (y0 + dy * (len(items) - 1) / 2)) / (dy * len(items) * 0.9)) ** 2))[..., None]
        fr *= 1 - m * 0.45 * smooth(prog(t, a, 0.3)) * fade
    if d.get("title"):
        AS = size_for_xh("acc", xh("lead", size) * 1.35)
        write_on(fr, d["title"], x0 - 6, y0 - dy * 1.05, t, a + 0.1, 0.6, "acc", AS, ACC, fade)
    k = eio(prog(t, a + 0.1, max(0.4, ts[-1] - a)))
    poly(fr, [(x0 - 40, y0 - size * 0.9), (x0 - 40, y0 - size * 0.9 + (dy * (len(items) - 1) + size * 1.1) * k)], ACC * 0.75, 3)
    col = INK if not overlay else TEXT
    for i, (it, ti) in enumerate(zip(items, ts)):
        p = prog(t, ti - 0.05, 0.35)
        if p <= 0: continue
        cur = i == len(items) - 1 or t < ts[i + 1] - 0.05
        circle(fr, (x0 - 40, y0 + i * dy - size * 0.32), 9 * bout(p, 1.6), ACC if cur else ACC * 0.65)
        text(fr, label(it), "lead", size, x0, y0 + i * dy, t, ti - 0.05, col if cur else col * 0.7 + (CARD if not overlay else 0) * 0.3, "l", "rise", fade)

def T_compare(fr, t, c, d, a, b):
    L, R = d["left"], d["right"]; lay = np.zeros_like(fr)
    kd = eio(prog(t, a + 0.2, 0.7)); poly(fr, [(W / 2, 470), (W / 2, 470 + 1000 * kd)], DIM, 2)
    for side, S, cx, col in (("l", L, W * 0.27, ACC), ("r", R, W * 0.73, COL[R.get("tone", "dim")])):
        t0 = phrase_time(S["at"], hint=a - 0.3) if S.get("at") else (a + 0.3 if side == "l" else a + (b - a) * 0.35)
        t0 = clamp(t0, a + 0.25, b - 1.0)
        KS = size_for_xh("key", 62); LS = size_for_xh("lead", 62 / PHI)
        if S.get("lead"): text(fr, S["lead"], "lead", LS, cx, 560, t, t0, INK * 0.85, "c")
        text(fr, S["title"], "key", KS, cx, 660, t, t0 + 0.1, col, "c", "blur")
        lv = S.get("level")
        if lv is not None:   # level bar: one progress value drives bar + dot (linked)
            p = eout(prog(t, t0 + 0.4, 0.9)) * lv; y0, y1 = 1330, 820
            poly(lay, [(cx, y0), (cx, y1)], DIM * 0.6, 10); yy = y0 + (y1 - y0) * p
            poly(lay, [(cx, y0), (cx, yy)], col, 10); circle(lay, (cx, yy), 16 if p > 0 else 0, col)
            if S.get("level_label") and p > 0.05: text(fr, S["level_label"], "lead", 34, cx, 1400, t, t0 + 0.6, INK * 0.7, "c")
        for i, it in enumerate(S.get("items", [])):
            ti = clamp(t0 + 0.45 + 0.35 * i, a, b - 0.7)
            text(fr, label(it), "lead", 40, cx, (1480 if lv is not None else 860) + i * 74, t, ti, INK * 0.85, "c")
    glow(fr, lay, 0.7); fr += lay * 0.9
    if d.get("footer"):
        ft = phrase_time(d["footer_at"], hint=a) if d.get("footer_at") else b - 1.2
        ft = clamp(ft, a + 0.8, b - 0.8)
        text(fr, d["footer"], "key", size_for_xh("key", 46), W / 2, 1690, t, ft, INK, "c", "blur")

def T_counter(fr, t, c, d, a, b):
    t0 = phrase_time(d["at"], hint=a - 0.3) if d.get("at") else a + 0.4; t0 = clamp(t0, a + 0.3, b - 1.2)
    p = eout(prog(t, t0, d.get("dur", 0.9))); v = d.get("from", 0) + (d["to"] - d.get("from", 0)) * p
    s = f"{d.get('prefix','')}{v:,.{d.get('decimals',0)}f}{d.get('suffix','')}"
    KS = size_for_xh("key", 150); w = sprite(s, "key", KS)["tw"]
    if p > 0: blit_text(fr, s, "key", KS, W / 2 - w / 2, H * 0.52, ACC)
    k = p; R = 330; arc = [(W / 2 + R * math.cos(math.radians(-90 + 360 * u)), H * 0.47 + R * math.sin(math.radians(-90 + 360 * u))) for u in np.linspace(0, 1, 140)]
    lay = np.zeros_like(fr); poly(lay, arc, DIM * 0.5, 4); poly(lay, part(arc, k), ACC, 6)
    if 0 < k < 1 or k >= 1: hp = part(arc, k)[-1] if part(arc, k) else arc[0]; circle(lay, hp, 11, ACC)
    glow(fr, lay, 0.8); fr += lay
    if d.get("label"): text(fr, d["label"], "lead", fit(d["label"], "lead", 44, 0.84 * W), W / 2, H * 0.47 + R + 110, t, t0 + 0.3, INK * 0.85, "c")
    if d.get("lead"): text(fr, d["lead"], "lead", 46, W / 2, 470, t, a + 0.2, INK, "c")
def fit(s, role, size, maxw):
    while size > 20 and sprite(s, role, size)["tw"] > maxw: size -= 2
    return size
def blit_text(fr, s, role, size, x, base, col, alpha=1.0):
    sp = sprite(s, role, size); blit(fr, sp["a"], int(x - sp["pad"]), int(base - sp["asc"] - sp["pad"]), col, alpha, sp["sh"])

def T_steps(fr, t, c, d, a, b):
    items = d["items"]; ts = item_times(c, items, a, b); n = len(items); dy = min(220, 1050 / max(1, n)); y0 = H * 0.5 - dy * (n - 1) / 2; x = 230
    lay = np.zeros_like(fr)
    for i, (it, ti) in enumerate(zip(items, ts)):
        p = prog(t, ti - 0.05, 0.4); y = y0 + i * dy
        if i > 0:
            k = eio(prog(t, ts[i - 1], max(0.2, ti - ts[i - 1]))); poly(lay, [(x, y - dy + 48), (x, y - dy + 48 + (dy - 96) * k)], ACC * 0.7, 4)
        if p <= 0: continue
        circle(lay, (x, y), 44 * bout(p, 1.4), ACC, 4)
        s = str(i + 1); sp = sprite(s, "key", 50); blit(fr, sp["a"], int(x - sp["tw"] / 2 - sp["pad"]), int(y + 18 - sp["asc"] - sp["pad"]), INK, smooth(p))
        text(fr, label(it), "lead", 54, x + 90, y + 18, t, ti, INK, "l")
    glow(fr, lay, 0.6); fr += lay
    if d.get("title"): text(fr, d["title"], "key", size_for_xh("key", 60), W / 2, 380, t, a + 0.15, ACC, "c", "blur")

def T_scale(fr, t, c, d, a, b):
    y = H * 0.55; x0, x1 = 150, W - 150; k = eio(prog(t, a + 0.2, 0.8)); lay = np.zeros_like(fr)
    n = 60
    for i in range(int(n * k)):
        u0, u1 = i / n, (i + 1) / n; poly(lay, [(x0 + (x1 - x0) * u0, y), (x0 + (x1 - x0) * u1, y)], SEC * (1 - u0) + ACC * u0, 8)
    for j in range(11):
        if j / 10 <= k: poly(lay, [(x0 + (x1 - x0) * j / 10, y + 26), (x0 + (x1 - x0) * j / 10, y + (44 if j % 5 == 0 else 36))], INK * 0.6, 3)
    t0 = phrase_time(d["at"], hint=a - 0.3) if d.get("at") else a + 0.9; t0 = clamp(t0, a + 0.8, b - 1.2)
    p = eio(prog(t, t0, 1.2)); v = d.get("from", 0.1) + (d["value"] - d.get("from", 0.1)) * p; mx = x0 + (x1 - x0) * v
    if k > 0.95: circle(lay, (mx, y), 24, ACC); circle(lay, (mx, y), 34, ACC * 0.5, 3)
    glow(fr, lay, 0.8); fr += lay
    text(fr, d["left"], "lead", 40, x0, y + 110, t, a + 0.5, SEC if not LIGHT_CARD else INK, "l")
    text(fr, d["right"], "lead", 40, x1, y + 110, t, a + 0.5, ACC, "r")
    if d.get("title"): text(fr, d["title"], "key", size_for_xh("key", 64), W / 2, y - 260, t, a + 0.2, INK, "c", "blur")
    if d.get("acc"):
        AS = fit(d["acc"], "acc", size_for_xh("acc", 40), 0.84 * W)
        write_on(fr, d["acc"], W / 2 - sprite(d["acc"], "acc", AS)["tw"] / 2, y + 260, t, min(t0 + 0.4, b - 1.2), 0.9, "acc", AS, ACC)

def T_bars(fr, t, c, d, a, b):
    items = d["items"]; ts = item_times(c, items, a, b); mx = max(it["value"] for it in items); n = len(items); dy = 170; y0 = H * 0.5 - dy * (n - 1) / 2
    for i, (it, ti) in enumerate(zip(items, ts)):
        p = eout(prog(t, ti, 0.8)); y = y0 + i * dy; L = (W - 360) * it["value"] / mx * p
        rrect(fr, 170, y - 34, 170 + max(8, L), y + 34, 16, ACC if it.get("hi") else SEC, smooth(p * 3))
        text(fr, it["label"], "lead", 40, 170, y - 52, t, ti, INK * 0.85, "l")
        if p > 0.05: blit_text(fr, f"{d.get('prefix','')}{it['value'] * p:,.0f}{d.get('unit','')}", "lead", 40, 190 + L, y + 14, INK)
    if d.get("title"): text(fr, d["title"], "key", size_for_xh("key", 60), W / 2, 380, t, a + 0.15, INK, "c", "blur")

def T_quote(fr, t, c, d, a, b):
    KS = size_for_xh("key", 64); words = d["text"].split(); lines, cur = [], []
    for w in words:
        if width(cur + [w], "key", KS, 0.22) > W * 0.74 and cur: lines.append(cur); cur = []
        cur.append(w)
    lines.append(cur); lh = KS * 1.25; y0 = H * 0.5 - lh * (len(lines) - 1) / 2; ti = a + 0.4
    qs = sprite("“", "key", KS * 2.4); p = prog(t, a + 0.15, 0.4)
    blit(fr, qs["a"], int(W * 0.13 - qs["pad"]), int(y0 - lh * 1.2 - qs["asc"] - qs["pad"]), ACC, smooth(p))
    per = max(0.06, min(0.18, (b - a - 1.6) / max(1, len(words))))
    for i, ln in enumerate(lines):
        x = W / 2 - width(ln, "key", KS, 0.22) / 2
        draw_words(fr, ln, [ti + per * k for k in range(len(ln))], x, y0 + i * lh, t, "key", KS, INK, "blur", 1.0, 0.22); ti += per * len(ln)
    if d.get("by"): text(fr, "— " + d["by"], "lead", 40, W / 2, y0 + lh * len(lines) + 60, t, ti, ACC, "c")

def T_checklist(fr, t, c, d, a, b):
    items = d["items"]; ts = item_times(c, items, a, b); n = len(items); dy = 150; y0 = H * 0.5 - dy * (n - 1) / 2; x = 200
    for i, (it, ti) in enumerate(zip(items, ts)):
        y = y0 + i * dy; p = prog(t, ti - 0.1, 0.3)
        if p <= 0: continue
        cv2.rectangle(fr, (x - 34, int(y - 52)), (x + 34, int(y + 16)), C(INK * 0.8), 3, cv2.LINE_AA)
        k = eio(prog(t, ti + 0.1, 0.35)); ck = [(x - 20, y - 20), (x - 4, y - 2), (x + 26, y - 42)]
        pts = [ck[0], ck[1]] if k < 0.4 else [ck[0], ck[1], (ck[1][0] + (ck[2][0] - ck[1][0]) * (k - 0.4) / 0.6, ck[1][1] + (ck[2][1] - ck[1][1]) * (k - 0.4) / 0.6)]
        if k > 0: poly(fr, pts if k >= 0.4 else [ck[0], (ck[0][0] + (ck[1][0] - ck[0][0]) * k / 0.4, ck[0][1] + (ck[1][1] - ck[0][1]) * k / 0.4)], ACC, 7)
        text(fr, label(it), "lead", 56, x + 70, y, t, ti, INK, "l")
    if d.get("title"): text(fr, d["title"], "key", size_for_xh("key", 60), W / 2, 380, t, a + 0.15, ACC, "c", "blur")

def T_search(fr, t, c, d, a, b):
    q = d["query"]; t0 = a + 0.5; y = H * 0.48; x0, x1 = 110, W - 110
    k = eout(prog(t, a + 0.1, 0.5)); rrect(fr, W / 2 - (W / 2 - x0) * k, y - 70, W / 2 + (W / 2 - x0) * k, y + 70, 70, TEXT if not LIGHT_CARD else np.array([1, 1, 1], np.float32), 0.95 * k)
    ink = PAL["primary"]
    if k > 0.9:
        circle(fr, (x0 + 70, y - 8), 20, ink, 4); poly(fr, [(x0 + 84, y + 6), (x0 + 100, y + 22)], ink, 5)
        n = int(len(q) * clamp((t - t0) / max(0.3, min(1.8, b - t0 - 1.0)))); s = q[:n]
        if s: blit_text(fr, s, "lead", 44, x0 + 130, y + 16, ink)
        if int(t * 2.4) % 2 == 0: cw = sprite(s, "lead", 44)["tw"] if s else 0; cv2.rectangle(fr, (int(x0 + 136 + cw), int(y - 26)), (int(x0 + 140 + cw), int(y + 26)), C(ACC), -1)
    if d.get("title"): text(fr, d["title"], "key", size_for_xh("key", 60), W / 2, y - 260, t, a + 0.15, INK, "c", "blur")

def T_cycle(fr, t, c, d, a, b):
    items = d["items"]; ts = item_times(c, items, a, b); n = len(items); cx, cy, R = W / 2, H * 0.52, 300; lay = np.zeros_like(fr)
    ang = [math.radians(-90 + 360 * i / n) for i in range(n)]
    for i, (it, ti) in enumerate(zip(items, ts)):
        p = prog(t, ti - 0.05, 0.35); px, py = cx + R * math.cos(ang[i]), cy + R * math.sin(ang[i])
        nxt = ts[i + 1] if i + 1 < n else b - 0.4
        k = eio(prog(t, ti, max(0.2, nxt - ti)))
        arc = [(cx + R * math.cos(ang[i] + (2 * math.pi / n) * u), cy + R * math.sin(ang[i] + (2 * math.pi / n) * u)) for u in np.linspace(0.1, 0.9, 40)]
        seg = part(arc, k); poly(lay, seg, ACC * 0.8, 4)
        if p > 0:
            circle(lay, (px, py), 16 * bout(p, 1.5), ACC)
            ox = 1 if math.cos(ang[i]) > 0.3 else (-1 if math.cos(ang[i]) < -0.3 else 0)
            text(fr, label(it), "lead", 44, px + ox * 40, py + (12 if ox else (-40 if math.sin(ang[i]) < 0 else 80)), t, ti, INK, "l" if ox > 0 else ("r" if ox < 0 else "c"))
    glow(fr, lay, 0.8); fr += lay
    if d.get("center"): text(fr, d["center"], "key", size_for_xh("key", 52), cx, cy + 20, t, a + 0.2, INK, "c", "blur")

def T_timeline(fr, t, c, d, a, b):
    items = d["items"]; ts = item_times(c, items, a, b); n = len(items); y = H * 0.5; x0, x1 = 140, W - 140
    k = eio(prog(t, a + 0.1, max(0.5, ts[-1] - a))); poly(fr, [(x0, y), (x0 + (x1 - x0) * k, y)], ACC * 0.8, 4)
    for i, (it, ti) in enumerate(zip(items, ts)):
        x = x0 + (x1 - x0) * (i / max(1, n - 1)); p = prog(t, ti, 0.35)
        if p <= 0: continue
        circle(fr, (x, y), 14 * bout(p, 1.5), ACC)
        top = i % 2 == 0
        text(fr, it["label"] if isinstance(it, dict) else str(it), "key", size_for_xh("key", 34), x, y - 60 if top else y + 100, t, ti, INK, "c", "blur")
        if isinstance(it, dict) and it.get("sub"): text(fr, it["sub"], "lead", 32, x, (y - 60 if top else y + 100) + 50, t, ti + 0.1, INK * 0.7, "c")
    if d.get("title"): text(fr, d["title"], "key", size_for_xh("key", 60), W / 2, 420, t, a + 0.15, INK, "c", "blur")

TEMPL = dict(statement=T_statement, list=T_list, compare=T_compare, counter=T_counter, steps=T_steps, scale=T_scale, bars=T_bars,
             quote=T_quote, checklist=T_checklist, search=T_search, cycle=T_cycle, timeline=T_timeline)

def card_frame(L, t):
    fr = CARD_BG.copy(); TEMPL[L["type"]](fr, t, L, L.get("data", {}), L["a"], L["b"])
    k = eio(prog(t, L["a"], L["b"] - L["a"])); z = 1.0 + 0.03 * k
    M = np.array([[z, 0, W / 2 * (1 - z)], [0, z, H / 2 * (1 - z)]], np.float32)
    return cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

# ───────────────────────── caption layer on plates
def scrim(fr, cy, alpha):
    if alpha <= 0.01: return
    band = fr[int(max(0, cy - 160)):int(min(H, cy + 160)), 80:W - 80]
    lum = float((band * np.array([0.2126, 0.7152, 0.0722], np.float32)).sum(-1).mean())
    a = clamp(0.18 + (lum - 0.10) * 1.4, 0.12, 0.55) * alpha
    m = np.exp(-((_yy[:, :1] - cy) / 260) ** 2)[..., None]; fr *= 1 - m * a
def captions(fr, t, covered):
    for c in CAPS:
        if c["start"] <= t < c["end"]:
            if covered and not c["raw"].get("over"): continue
            fade = 1 - prog(t, c["end"] - 0.14, 0.14)
            cy = c["y"] * H; scrim(fr, cy, smooth(prog(t, c["start"], 0.25)) * fade)
            lockup(fr, t, c, cy, fade)

# ───────────────────────── transitions
def tr_in(A, B, p, style):
    style = TRANS_ALIAS.get(style, style)
    k = eio(p)
    if style == "zoom":
        zf, zb = 1 + 0.10 * k, 1.05 - 0.05 * k
        A2 = cv2.GaussianBlur(cv2.warpAffine(A, np.array([[zf, 0, W / 2 * (1 - zf)], [0, zf, H / 2 * (1 - zf)]], np.float32), (W, H)), (0, 0), 1 + 9 * k)
        B2 = cv2.warpAffine(B, np.array([[zb, 0, W / 2 * (1 - zb)], [0, zb, H / 2 * (1 - zb)]], np.float32), (W, H))
        return A2 * (1 - k) + B2 * k
    if style == "light":
        o = A * (1 - k) + B * k; leak = np.exp(-(((_xx - (150 + 800 * k)) / 380) ** 2 + ((_yy - 700) / 900) ** 2))[..., None]
        return o + leak * ACC * 0.32 * math.sin(math.pi * k)
    if style == "blur":
        s = 1 + 12 * math.sin(math.pi * k); return cv2.GaussianBlur(A, (0, 0), s) * (1 - k) + cv2.GaussianBlur(B, (0, 0), s) * k
    return A * (1 - k) + B * k

def base_frame(t):
    for B in BROLL:
        if B["a"] <= t < B["b"]:
            fr = broll_frame(B, t); captions(fr, t, False); return fr
    fr = plate(t)
    covered = False
    for O in OVERS:
        if O["a"] <= t < O["b"]: TEMPL[O["type"]](fr, t, O, O.get("data", {}), O["a"], O["b"], overlay=True) if O["type"] == "list" else TEMPL[O["type"]](fr, t, O, O.get("data", {}), O["a"], O["b"]); covered = True
    captions(fr, t, False if not covered else False)
    return fr

def frame(t):
    for L in CARDS:
        if L["a"] <= t < L["a"] + TI:
            src = card_frame(L["chain"], L["a"] - 1 / FPS) if L.get("chain") else base_frame(t)
            return tr_in(src, card_frame(L, t), prog(t, L["a"], TI), "dissolve" if L.get("chain") else L.get("in", "zoom"))
        if L["a"] + TI <= t < L["b"]: return card_frame(L, t)
        if L["b"] <= t < L["b"] + TO and not L.get("chained"): return tr_in(card_frame(L, L["b"] - 1 / FPS), base_frame(t), prog(t, L["b"], TO), L.get("out", "dissolve"))
    for B in BROLL:
        if abs(t - B["a"]) < 0.2: return tr_in(plate(t), base_frame(t), prog(t, B["a"] - 0.2, 0.4), B.get("in", "dissolve")) if t < B["a"] else base_frame(t)
    return base_frame(t)

_rg = np.random.default_rng(3); GRAIN = [_rg.normal(0, 0.009, (H, W, 1)).astype(np.float32) for _ in range(4)]
def out_frame(t, n=0): return np.clip(frame(t) + GRAIN[n % 4], 0, 1)

# ───────────────────────── safe zone + report
def safe_check():
    for c in CAPS:
        g = c["_g"]; top = c["y"] * H - g["kc"] - g["LS"] * 1.4; bot = c["y"] * H + g["kc"] / 2 + g["AS"] * 1.8
        if top < 0.12 * H or bot > 0.80 * H: ISSUES.append(f"caption '{' '.join(c['key'])}' outside vertical safe zone")
        if g["kw"] > 0.80 * W: ISSUES.append(f"caption '{' '.join(c['key'])}' too wide")

def main():
    plan_captions(); plan_layers(); safe_check()
    log = dict(duration=round(tl.dur, 2), captions=[dict(key=" ".join(c["key"]), start=round(c["start"], 2), end=round(c["end"], 2), need=round(c["need"], 2), layout=c["_g"]["layout"]) for c in CAPS],
               cards=[dict(type=L["type"], a=round(L["a"], 2), b=round(L["b"], 2)) for L in CARDS], broll=[dict(file=B["file"], a=round(B["a"], 2), b=round(B["b"], 2)) for B in BROLL], issues=ISSUES)
    json.dump(log, open(os.path.join(WD, "render_log.json"), "w"), indent=1)
    a = sys.argv[2:]
    if "--plan" in a:
        print(f"DUR {tl.dur:.1f}s | {len(CAPS)} captions | {len(CARDS)} cards | {len(OVERS)} overlays | {len(BROLL)} broll | zooms {[round(z, 3) for z in ZOOMS]} eye_y {EYE_Y:.2f}")
        print("ISSUES:", "none" if not ISSUES else "\n  " + "\n  ".join(ISSUES)); return
    if "--frames" in a:
        ts = [float(x) for x in a[a.index("--frames") + 1].split(",")]
        ims = [cv2.resize((out_frame(t)[..., ::-1] * 255).astype(np.uint8), (360, 640), interpolation=cv2.INTER_AREA) for t in ts]
        for im, t in zip(ims, ts): cv2.putText(im, f"{t:.1f}", (8, 24), 0, 0.7, (0, 255, 255), 2)
        rows = [np.hstack(ims[i:i + 5] + [np.zeros_like(ims[0])] * (5 - len(ims[i:i + 5]))) for i in range(0, len(ims), 5)]
        cv2.imwrite(os.path.join(WD, "styleframes.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
        if "--full" in a:
            for t in ts: cv2.imwrite(os.path.join(WD, f"sf_{t:05.2f}.jpg"), (out_frame(t)[..., ::-1] * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 90])
        print("styleframes.jpg", "| ISSUES:", len(ISSUES)); return
    if "--concat" in a:
        N = int(a[a.index("--concat") + 1]); lst = os.path.join(WD, "parts.txt")
        open(lst, "w").write("".join(f"file 'video.part{i}.mp4'\n" for i in range(N)))
        subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", os.path.join(WD, "video.mp4")], check=True); print("video.mp4"); return
    i, N = (map(int, a[a.index("--part") + 1].split("/")) if "--part" in a else (0, 1))
    n0, n1 = tl.n * i // N, tl.n * (i + 1) // N
    out = os.path.join(WD, "video.mp4" if N == 1 else f"video.part{i}.mp4")
    preset = os.environ.get("THS_PRESET", "medium"); crf = os.environ.get("THS_CRF", "17")   # THS_PRESET=veryfast in a sandbox with a tight per-command time limit
    p = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    for n in range(n0, n1):
        p.stdin.write((out_frame(n / FPS, n) * 255 + 0.5).astype(np.uint8).tobytes())
        if (n - n0) % 150 == 0: print(f"{n}/{tl.n}", flush=True)
    p.stdin.close(); p.wait(); print(out)

if __name__ == "__main__":
    main()
