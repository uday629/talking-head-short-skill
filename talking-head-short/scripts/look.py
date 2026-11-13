"""LOOK = the per-video design system (motion style family, background, palette, fonts, caption treatment,
text animation, transitions, 3D moves, element kit). Every video gets a NEW look, chosen from:
  • the genre row of the user's sheet (motion style, elements, mechanics, palette, fonts)
  • the raw footage (its own colors, brightness, framing)
  • a per-video random seed + a history of recent looks (so two videos never look the same)

python look.py RAW "<niche or no>" WORKDIR [--tone calm|balanced|energetic] [--seed N]
      → prints 3 distinct LOOK OPTIONS (A/B/C) and writes WORKDIR/look_options.json
python look.py --pick A|B|C WORKDIR [--palette sheet|footage|blend] [--family doodle] [--accent "#hex"]
      → writes WORKDIR/look.json (the engine reads it), downloads fonts, records history
"""
import sys, os, json, re, time, hashlib, colorsys, random
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", "references", "genre_matrix.json")
ASSETS = os.environ.get("THS_ASSETS", os.path.expanduser("~/.ths_assets"))
HIST = os.path.join(ASSETS, "look_history.json")

# ─────────────────────────────── style families (one per row of the MOTION STYLE GUIDE + 2 from the matrix)
# bg: card canvas · frames: how cards sit over the footage · cap: caption treatment · fx: card text animation
# tr: transitions · d3: 3D moves · cards: card types that suit the family (most typical first)
F = {
 "vector":   dict(name="Clean 2D vector / infographic", kw=["vector", "infographic", "clinical", "minimal 2d", "chart"],
                  bg=["light", "mesh", "solid", "paper"], frames=["full", "panel", "split"], cap=["plain", "bar", "glass"],
                  fx=["slide", "mask"], tr=["push", "iris", "dissolve", "whip"], d3=["tilt", "flip"],
                  cards=["flow", "bars", "counter", "steps", "checklist", "compare", "scale", "list"],
                  el=dict(boil=0, stepped=0, shake=0, glow=0.15, shadow=1, grain=0.006, stroke=4, radius=22, halftone=0, tilt=0),
                  fonts=dict(lead=[("Inter", 500), ("Manrope", 500), ("DM Sans", 500), ("Rubik", 500), ("Poppins", 500)],
                             key=[("Manrope", 800), ("Poppins", 700), ("Outfit", 700), ("Rubik", 700), ("Unbounded", 600)],
                             acc=[("Instrument Serif", 400, 1), ("Lora", 500, 1), ("Fraunces", 400, 1)])),
 "ui":       dict(name="UI / glass / screen-style", kw=["ui", "saas", "screen", "glass", "card ui", "modular", "software", "dashboard"],
                  bg=["mesh", "frosted", "light"], frames=["panel", "full", "split"], cap=["glass", "plain"],
                  fx=["slide", "type"], tr=["iris", "push", "tilt3d", "dissolve"], d3=["tilt", "flip"],
                  cards=["flow", "search", "checklist", "steps", "bars", "counter", "compare"],
                  el=dict(boil=0, stepped=0, shake=0, glow=0.25, shadow=1, grain=0.004, stroke=4, radius=38, halftone=0, tilt=0, cursor=1),
                  fonts=dict(lead=[("Inter", 500), ("DM Sans", 500), ("Manrope", 600)],
                             key=[("Inter", 700), ("Space Grotesk", 700), ("Outfit", 700), ("Bricolage Grotesque", 700)],
                             acc=[("Instrument Serif", 400, 1), ("DM Sans", 400, 1)])),
 "hud":      dict(name="Tech HUD / node pipeline", kw=["hud", "tech", "node", "futuristic", "biomechanical", "data-ui", "wireframe"],
                  bg=["grid", "frosted", "solid"], frames=["full", "panel"], cap=["bar", "plain"],
                  fx=["scramble"], tr=["glitch", "zoom", "whip"], d3=["orbit", "tilt"],
                  cards=["flow", "counter", "scale", "timeline", "cycle", "bars"],
                  el=dict(boil=0, stepped=0, shake=0, glow=1.0, shadow=0, grain=0.008, stroke=3, radius=6, halftone=0, tilt=0),
                  fonts=dict(lead=[("Space Mono", 400), ("IBM Plex Mono", 400), ("IBM Plex Sans", 500)],
                             key=[("Space Grotesk", 700), ("Oswald", 600), ("Bebas Neue", 400), ("Unbounded", 600)],
                             acc=[("IBM Plex Sans", 400, 1), ("Instrument Serif", 400, 1)])),
 "doodle":   dict(name="Hand-drawn / doodle sketch", kw=["hand-drawn", "doodle", "sketch", "whiteboard", "warm editorial"],
                  bg=["paper"], frames=["full", "split", "panel"], cap=["marker", "plain"],
                  fx=["handwrite", "rise"], tr=["dissolve", "peel", "whip"], d3=["tilt"],
                  cards=["list", "cycle", "compare", "scale", "statement", "steps", "quote"],
                  el=dict(boil=1, stepped=12, shake=0, glow=0.0, shadow=0, grain=0.010, stroke=6, radius=14, halftone=0, tilt=2),
                  fonts=dict(lead=[("DM Sans", 500), ("Nunito Sans", 600), ("Patrick Hand", 400)],
                             key=[("Caveat", 700), ("Permanent Marker", 400), ("Lora", 700), ("Fraunces", 700)],
                             acc=[("Caveat", 500, 0), ("Shadows Into Light", 400, 0), ("Lora", 400, 1)])),
 "papercraft": dict(name="Papercraft / mixed-media collage", kw=["papercraft", "collage", "scrapbook", "sticker", "cutout", "postcard", "archival", "tactile", "meme"],
                  bg=["paper", "film"], frames=["full", "split"], cap=["box", "stamp"],
                  fx=["stamp"], tr=["peel", "whip", "push"], d3=["tilt", "parallax"],
                  cards=["checklist", "list", "timeline", "statement", "quote"],
                  el=dict(boil=0, stepped=10, shake=0, glow=0.0, shadow=1, grain=0.012, stroke=5, radius=4, halftone=1, tilt=3),
                  fonts=dict(lead=[("Special Elite", 400), ("Archivo Narrow", 600), ("DM Sans", 600)],
                             key=[("Archivo Black", 400), ("DM Serif Display", 400), ("Bebas Neue", 400), ("Anton", 400)],
                             acc=[("Caveat", 600, 0), ("Instrument Serif", 400, 1)])),
 "kinetic":  dict(name="Bold kinetic typography", kw=["kinetic", "bold", "impact", "high-contrast", "expressive"],
                  bg=["block", "solid", "film"], frames=["full"], cap=["outline", "box"],
                  fx=["slam"], tr=["zoom", "whip", "glitch"], d3=["extrude", "flip"],
                  cards=["counter", "statement", "bars", "scale", "checklist"],
                  el=dict(boil=0, stepped=0, shake=1, glow=0.1, shadow=1, grain=0.014, stroke=6, radius=0, halftone=0, tilt=0),
                  fonts=dict(lead=[("Inter", 700), ("Montserrat", 700), ("Barlow Condensed", 600)],
                             key=[("Anton", 400), ("Bebas Neue", 400), ("Archivo Black", 400), ("Oswald", 700)],
                             acc=[("Instrument Serif", 400, 1), ("Playfair Display", 500, 1)])),
 "editorial": dict(name="Documentary / editorial map & board", kw=["documentary", "editorial", "map", "board", "evidence", "broadcast", "lower-third", "noir", "document", "official"],
                  bg=["film", "paper", "solid"], frames=["full", "panel"], cap=["bar", "marker", "plain"],
                  fx=["type", "mask"], tr=["dissolve", "push", "whip"], d3=["parallax", "tilt"],
                  cards=["timeline", "quote", "compare", "counter"],
                  el=dict(boil=0, stepped=0, shake=0, glow=0.0, shadow=1, grain=0.016, stroke=3, radius=2, halftone=0, tilt=0),
                  fonts=dict(lead=[("IBM Plex Sans", 500), ("Libre Franklin", 500), ("Source Sans 3", 500)],
                             key=[("Playfair Display", 700), ("Merriweather", 700), ("DM Serif Display", 400), ("Oswald", 600)],
                             acc=[("Playfair Display", 400, 1), ("Lora", 400, 1), ("Special Elite", 400, 0)])),
 "luxe":     dict(name="Editorial magazine / luxe", kw=["magazine", "luxury", "fashion", "beauty", "split-screen"],
                  bg=["light", "frosted", "paper"], frames=["full", "split"], cap=["plain"],
                  fx=["mask", "blur"], tr=["dissolve", "blur", "iris"], d3=["tilt"],
                  cards=["statement", "quote", "list", "compare", "scale"],
                  el=dict(boil=0, stepped=0, shake=0, glow=0.0, shadow=1, grain=0.008, stroke=2, radius=0, halftone=0, tilt=0),
                  fonts=dict(lead=[("Manrope", 500), ("Montserrat", 500), ("Raleway", 500)],
                             key=[("Cormorant Garamond", 600), ("Bodoni Moda", 600), ("Playfair Display", 600), ("Instrument Serif", 400)],
                             acc=[("Cormorant Garamond", 500, 1), ("Great Vibes", 400, 0), ("Instrument Serif", 400, 1)])),
 "blueprint": dict(name="Architectural blueprint / 3D callout", kw=["blueprint", "architect", "isometric", "3d/2d", "framework diagram", "process"],
                  bg=["blueprint", "grid", "light"], frames=["full", "panel"], cap=["bar", "plain"],
                  fx=["slide", "type"], tr=["push", "iris", "tilt3d"], d3=["orbit", "tilt"],
                  cards=["flow", "steps", "scale", "bars", "timeline", "counter"],
                  el=dict(boil=0, stepped=0, shake=0, glow=0.35, shadow=0, grain=0.006, stroke=3, radius=4, halftone=0, tilt=0),
                  fonts=dict(lead=[("Lato", 500), ("IBM Plex Sans", 500), ("Archivo Narrow", 600)],
                             key=[("Manrope", 800), ("Oswald", 600), ("Space Grotesk", 700)],
                             acc=[("Lora", 400, 1), ("IBM Plex Sans", 400, 1)])),
 "showreel": dict(name="Cinematic product 3D showreel", kw=["showreel", "3d product", "product reveal", "gadget", "e-commerce", "ecommerce",
                  "luxury branding", "360", "metallic", "orbital"],
                  bg=["light", "mesh", "frosted"], frames=["full", "panel"], cap=["plain", "glass"],
                  fx=["blur", "slide"], tr=["tilt3d", "dissolve", "iris"], d3=["orbit", "parallax"],
                  cards=["orbit", "compare", "statement", "list"],
                  el=dict(boil=0, stepped=0, shake=0, glow=0.45, shadow=1, grain=0.005, stroke=3, radius=20, halftone=0, tilt=0),
                  fonts=dict(lead=[("Manrope", 500), ("Outfit", 500), ("Inter", 500)],
                             key=[("Unbounded", 600), ("Space Grotesk", 700), ("Outfit", 700)],
                             acc=[("Instrument Serif", 400, 1), ("Cormorant Garamond", 500, 1)])),
}
TONE_ALT = {"calm": ["luxe", "editorial", "doodle", "vector"], "balanced": ["vector", "papercraft", "ui", "editorial"],
            "energetic": ["kinetic", "papercraft", "hud", "ui"]}

# ─────────────────────────────── color helpers
def hex2rgb(h): h = h.lstrip("#"); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float) / 255
def rgb2hex(c): c = np.clip(np.round(np.asarray(c, float) * 255), 0, 255).astype(int); return "#%02X%02X%02X" % tuple(c)
def lin(c): c = np.asarray(c, float); return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def lum(c): l = lin(c); return float(0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2])
def contrast(a, b): la, lb = lum(a), lum(b); return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)
def hls(c): return colorsys.rgb_to_hls(*np.clip(c, 0, 1))
def mk(h, l, s): return np.array(colorsys.hls_to_rgb(h % 1, min(1, max(0, l)), min(1, max(0, s))))
def push_contrast(c, bg, need):
    """move lightness away from bg until contrast ≥ need (keeps hue)."""
    h, l, s = hls(c); up = lum(bg) < 0.35
    for _ in range(60):
        if contrast(c, bg) >= need: break
        l = min(0.98, l + 0.015) if up else max(0.03, l - 0.015); c = mk(h, l, s)
    return c

# ─────────────────────────────── footage reading
def footage(raw):
    from ff import FFMPEG, probe
    import subprocess, cv2
    P = probe(raw); n = 14
    b = subprocess.run([FFMPEG, "-v", "error", "-i", raw, "-vf", f"fps={n / max(1, P['dur']):.4f},scale=96:170", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    f = np.frombuffer(b, np.uint8)[: (len(b) // (96 * 170 * 3)) * 96 * 170 * 3].reshape(-1, 170, 96, 3).astype(np.float32) / 255
    px = f.reshape(-1, 3)
    hsv = cv2.cvtColor((px[None] * 255).astype(np.uint8), cv2.COLOR_RGB2HSV)[0].astype(float)
    skin = (hsv[:, 0] < 25) & (hsv[:, 1] > 50) & (hsv[:, 2] > 90)
    sample = px[~skin] if (~skin).sum() > 500 else px
    K = 7; _, lab, cen = cv2.kmeans(sample.astype(np.float32), K, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3), 3, cv2.KMEANS_PP_CENTERS)
    cnt = np.bincount(lab.ravel(), minlength=K); order = np.argsort(-cnt)
    cols = [(cen[i].astype(float), cnt[i] / cnt.sum()) for i in order]
    cap = f[:, int(170 * .52):int(170 * .78), 10:86].reshape(-1, 3)
    return dict(colors=cols, bright=lum(px.mean(0)), cap=cap.mean(0), cap_lum=lum(cap.mean(0)),
                sat=float(np.mean([hls(c)[2] * min(1, 4 * hls(c)[1] * (1 - hls(c)[1])) for c, _ in cols])), w=P["w"], h=P["h"])

# ─────────────────────────────── palettes
def sheet_palette(g):
    P = {k: hex2rgb(v["hex"]) for k, v in g["palette"].items()}
    cs = list(P.values())
    neutral = max(cs, key=lambda c: hls(c)[1] - 0.6 * hls(c)[2])               # light, low-sat
    dark = min(cs, key=lambda c: hls(c)[1])
    acc = P.get("4th", cs[-1])
    if hls(acc)[2] < 0.25 or contrast(acc, neutral) < 1.6: acc = max(cs, key=lambda c: hls(c)[2] * (0.3 < hls(c)[1] < 0.75))
    sec = P.get("secondary", cs[1])
    if np.allclose(sec, neutral) or np.allclose(sec, acc): sec = P.get("3rd", cs[2])
    return dict(dark=dark, neutral=neutral, acc=acc, sec=sec, mid=P.get("primary", dark))

def footage_palette(M, rng):
    cols = M["colors"]
    by_l = sorted(cols, key=lambda x: hls(x[0])[1])
    dark = by_l[0][0]; h, l, s = hls(dark); dark = mk(h, min(l, 0.16), min(0.45, s * 1.2 + 0.05))
    light = by_l[-1][0]; h, l, s = hls(light); neutral = mk(h, max(0.90, l), min(0.22, s))
    sat = sorted(cols, key=lambda x: -(hls(x[0])[2] * (0.15 < hls(x[0])[1] < 0.85)) * (0.4 + x[1]))
    a = sat[0][0]; h, l, s = hls(a)
    if s < 0.22:                                           # footage is neutral (white wall, black clothes) → complement of the dominant tint
        dh = hls(cols[0][0])[0]; h = (dh + 0.5 + rng.uniform(-0.06, 0.06)) % 1; s = 0.55
    acc = mk(h, rng.uniform(0.55, 0.64), max(0.5, min(0.8, s * 1.4)))
    m = cols[1][0] if len(cols) > 1 else cols[0][0]; h2, l2, s2 = hls(m)
    sec = mk(h2, 0.5, max(0.25, min(0.55, s2 * 1.3)))
    return dict(dark=dark, neutral=neutral, acc=acc, sec=sec, mid=mk(hls(dark)[0], 0.28, hls(dark)[2]))

def blend_palette(S, Fp):
    out = {}
    for k in S:
        a, b = hls(S[k]), hls(Fp[k])
        dh = ((b[0] - a[0] + 0.5) % 1) - 0.5
        out[k] = mk(a[0] + 0.45 * dh, a[1], a[2] * 0.7 + b[2] * 0.3)
    out["acc"] = Fp["acc"] if hls(Fp["acc"])[2] > 0.4 else S["acc"]
    return out

def colors_for(bg_kind, base, M, rng):
    """card colors per background kind → dict of hex roles the engine reads."""
    dark, neu, acc, sec, mid = base["dark"], base["neutral"], base["acc"], base["sec"], base["mid"]
    if bg_kind in ("light", "paper"):
        bg = neu if bg_kind == "light" else mk(hls(neu)[0], min(0.93, hls(neu)[1]), max(0.18, hls(neu)[2]))
        ink = dark
    elif bg_kind == "block":
        bg = rng.choice([acc, sec]) if hls(acc)[1] < 0.62 else sec; h, l, s = hls(bg); bg = mk(h, min(l, 0.5), max(s, 0.5))
        ink = neu if contrast(neu, bg) > contrast(dark, bg) else dark
        acc = dark if ink is neu else neu
    elif bg_kind == "blueprint":
        h = hls(sec)[0] if 0.5 < hls(sec)[0] < 0.7 else 0.59; bg = mk(h, 0.26, 0.55); ink = mk(h, 0.95, 0.3)
    elif bg_kind == "film":
        bg = mk(hls(dark)[0], 0.11, min(0.25, hls(dark)[2])); ink = neu
    elif bg_kind == "frosted":
        bg = mk(hls(dark)[0], 0.14, hls(dark)[2]); ink = mk(hls(neu)[0], 0.97, 0.1)
    elif bg_kind == "grid":
        bg = mk(hls(dark)[0], 0.09, min(0.5, hls(dark)[2] + 0.1)); ink = mk(hls(neu)[0], 0.94, 0.15)
    else:   # solid / mesh
        bg = mid if hls(mid)[1] < 0.4 else dark; ink = neu
    acc = push_contrast(acc, bg, 3.0); sec2 = push_contrast(sec, bg, 2.2); ink = push_contrast(ink, bg, 7.0)
    cap_text = push_contrast(neu, M["cap"], 4.5) if M["cap_lum"] < 0.45 else push_contrast(mk(hls(neu)[0], 0.97, 0.1), M["cap"] * 0.6, 4.5)
    cap_acc = base["acc"] if bg_kind != "block" else acc
    cap_acc = push_contrast(cap_acc, M["cap"] * (0.6 if M["cap_lum"] > 0.45 else 1), 3.0)
    return {k: rgb2hex(v) for k, v in dict(bg=bg, ink=ink, acc=acc, sec=sec2, neutral=neu, dark=dark,
                                            cap_text=cap_text, cap_acc=cap_acc, mid=mid).items()}

# ─────────────────────────────── picking
def families_for(g, tone):
    ms = (g.get("motion_style", "") + " " + g.get("elements", "")).lower(); niche = g["niche"].lower()
    J = json.load(open(REF)); score = {k: 0.0 for k in F}
    for k, v in F.items():
        score[k] += sum(3 for w in v["kw"] if w in ms)
    for row in J.get("motion_guide", []):
        fam = next((k for k, v in F.items() if any(w in row["category"].lower() for w in v["kw"])), None)
        if fam and any(w.strip(" .&").lower() and w.strip(" .&").lower().split()[0] in niche for w in re.split(r",|&", row.get("niches", ""))): score[fam] += 1.5
    for i, k in enumerate(TONE_ALT.get(tone, [])): score[k] += 1.0 - 0.2 * i
    return sorted(score, key=lambda k: -score[k]), score

def history():
    try: return json.load(open(HIST))[-30:]
    except Exception: return []

def signature(L): return [L["family"], L["bg"], L["caption"], L["fonts"]["key"][0], L["palette_mode"], round(L["accent_hue"] / 30)]

def novelty(L, hist):
    s = signature(L); pen = 0.0
    for age, h in enumerate(reversed(hist)):
        w = 1.0 / (1 + age * 0.35)
        pen += w * sum(a == b for a, b in zip(s, h)) / len(s)
    return -pen

def build(fam, g, M, rng, tone, palette_mode=None, sheet_first=False):
    D = F[fam]
    bg = rng.choice(D["bg"])
    if bg == "light" and M["bright"] < 0.12 and len(D["bg"]) > 1 and rng.random() < 0.5: bg = rng.choice([b for b in D["bg"] if b != "light"])
    pm = palette_mode or rng.choice(["sheet", "footage", "blend"])
    S = sheet_palette(g); Fp = footage_palette(M, rng)
    base = S if pm == "sheet" else (Fp if pm == "footage" else blend_palette(S, Fp))
    col = colors_for(bg, base, M, rng)
    sf = g.get("fonts", {})
    sheet_lead = next((v["family"] for k, v in sf.items() if "body" in k or "caption" in k), None)
    sheet_key = next((v["family"] for k, v in sf.items() if "head" in k), None)
    def pick(lst): return lst[rng.integers(len(lst))]
    lead, key, acc = pick(D["fonts"]["lead"]), pick(D["fonts"]["key"]), pick(D["fonts"]["acc"])
    if sheet_first and sheet_key: key = (sheet_key, 700 if sheet_key not in ("Anton", "Archivo Black", "Bebas Neue") else 400)
    if sheet_first and sheet_lead: lead = (sheet_lead, 500)
    if key[0] == lead[0]: lead = next((x for x in D["fonts"]["lead"] if x[0] != key[0]), ("Inter", 500))
    cap = rng.choice(D["cap"]); fx = rng.choice(D["fx"])
    tr = list(rng.permutation(D["tr"])); d3 = list(D["d3"])
    frames = list(D["frames"]); rng.shuffle(frames)
    el = dict(D["el"])
    if tone == "calm": el["shake"] = 0; tr = [t for t in tr if t not in ("glitch",)] or ["dissolve"]
    if tone == "energetic" and fam not in ("doodle",): el["stepped"] = 0 if fam != "papercraft" else el["stepped"]
    align = rng.choice(["center", "left"] if fam not in ("kinetic", "luxe") else ["center"])
    case = "upper" if fam in ("kinetic",) or (fam in ("hud", "blueprint") and rng.random() < 0.5) else "none"
    cards = list(D["cards"]); head, tail = cards[:4], cards[4:]; rng.shuffle(head); cards = head + tail
    L = dict(family=fam, family_name=D["name"], bg=bg, palette_mode=pm, colors=col,
             fonts=dict(lead=[lead[0], lead[1]], key=[key[0], key[1]], acc=[acc[0], acc[1]], acc_italic=bool(acc[2] if len(acc) > 2 else 0), key_italic=False),
             caption=cap, case=case, text_fx=fx, transitions=tr, depth3d=d3, frames=frames, elements=el, align=align,
             cards=cards, seed=int(rng.integers(1 << 30)), accent_hue=hls(hex2rgb(col["acc"]))[0] * 360)
    return L

def describe(L):
    c = L["colors"]
    return (f"{L['family_name']} · bg {L['bg']} {c['bg']} · ink {c['ink']} · accent {c['acc']} · palette from {L['palette_mode']}"
            f" · fonts {L['fonts']['lead'][0]} / {L['fonts']['key'][0]} / {L['fonts']['acc'][0]}{' italic' if L['fonts']['acc_italic'] else ''}"
            f" · captions {L['caption']}{' UPPER' if L['case']=='upper' else ''} · text {L['text_fx']} · frames {'/'.join(L['frames'])}"
            f" · transitions {'/'.join(L['transitions'][:3])} · 3D {'/'.join(L['depth3d'])} · cards {', '.join(L['cards'][:6])}")

def options(raw, key, wd, tone="balanced", seed=None):
    J = json.load(open(REF))
    g = next((x for x in J["genres"] if x["no"] == str(key) or str(key).lower() in x["niche"].lower()), None)
    if g is None: sys.exit("genre not found: " + key)
    if seed is None:
        h = hashlib.sha1(f"{os.path.abspath(raw)}{os.path.getsize(raw)}{time.time_ns()}".encode()).hexdigest()
        seed = int(h[:8], 16)
    rng = np.random.default_rng(seed); M = footage(raw); hist = history()
    fams, score = families_for(g, tone)
    pool = []
    for fam in fams[:4]:
        for pm in ("sheet", "footage", "blend"):
            for _ in range(3): pool.append(build(fam, g, M, rng, tone, pm, sheet_first=(pm == "sheet" and rng.random() < 0.5)))
    def total(L, chosen):
        s = score[L["family"]] * 0.6 + novelty(L, hist) * 3
        for c in chosen: s -= 2.5 * sum(a == b for a, b in zip(signature(L), signature(c))) / 6
        return s + rng.uniform(0, 0.3)
    chosen = []
    for _ in range(3):
        best = max((L for L in pool if L not in chosen), key=lambda L: total(L, chosen)); chosen.append(best)
    if all(c["family"] == chosen[0]["family"] for c in chosen):   # always offer one different family
        alt = max((L for L in pool if L["family"] != chosen[0]["family"]), key=lambda L: total(L, chosen[:2])); chosen[2] = alt
    os.makedirs(wd, exist_ok=True)
    json.dump(dict(genre=g["niche"], tone=tone, seed=seed, options=chosen,
                   sheet=dict(motion_style=g.get("motion_style"), elements=g.get("elements"), mechanics=g.get("mechanics"))),
              open(os.path.join(wd, "look_options.json"), "w"), indent=1)
    print(f"GENRE {g['niche']} · sheet motion style: {g.get('motion_style','')}")
    print(f"SHEET ELEMENTS: {g.get('elements','')[:220]}")
    print(f"SHEET MECHANICS: {g.get('mechanics','')[:220]}")
    print(f"FOOTAGE: brightness {M['bright']:.2f} · caption zone {rgb2hex(M['cap'])} · colors " + " ".join(rgb2hex(c) for c, _ in M['colors'][:5]))
    for k, L in zip("ABC", chosen): print(f"LOOK {k}: {describe(L)}")
    print("pick → look.py --pick A WORKDIR   (override: --palette sheet|footage|blend  --family NAME  --accent '#hex'  --bg KIND)")

def pick(wd, k, pal=None, fam=None, accent=None, bgk=None):
    O = json.load(open(os.path.join(wd, "look_options.json")))
    L = O["options"]["ABC".index(k.upper())]
    if pal or fam or bgk:
        J = json.load(open(REF)); g = next(x for x in J["genres"] if x["niche"] == O["genre"])
        raw = json.load(open(os.path.join(wd, "probe.json"))).get("raw") if os.path.exists(os.path.join(wd, "probe.json")) else None
        rng = np.random.default_rng(L["seed"])
        M = footage(raw or sys.exit("probe.json lacks raw path; run analyze.py first"))
        L2 = build(fam or L["family"], g, M, rng, O["tone"], pal or L["palette_mode"])
        if bgk: L2["bg"] = bgk; L2["colors"] = colors_for(bgk, dict(sheet_palette(g)), M, rng) if (pal or L["palette_mode"]) == "sheet" else L2["colors"]
        if not fam: L2["fonts"] = L["fonts"]; L2["caption"] = L["caption"]; L2["text_fx"] = L["text_fx"]
        L = L2
    if accent: L["colors"]["acc"] = accent; L["colors"]["cap_acc"] = accent
    json.dump(L, open(os.path.join(wd, "look.json"), "w"), indent=1)
    h = history(); h.append(signature(L)); os.makedirs(ASSETS, exist_ok=True); json.dump(h[-30:], open(HIST, "w"))
    try:
        import assets; assets.font([L["fonts"][r][0] for r in ("lead", "key", "acc")])
    except Exception as e: print("font download:", str(e)[:80])
    print("look.json ←", describe(L))

if __name__ == "__main__":
    a = sys.argv[1:]
    def opt(n, d=None): return a[a.index(n) + 1] if n in a else d
    if a and a[0] == "--pick": pick(a[2], a[1], opt("--palette"), opt("--family"), opt("--accent"), opt("--bg"))
    else: options(a[0], a[1], a[2], opt("--tone", "balanced"), int(opt("--seed")) if opt("--seed") else None)
