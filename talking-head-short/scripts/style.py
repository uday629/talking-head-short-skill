"""Genre matrix → per-video adapted style.
Usage:  python style.py <raw.mp4> <genre no or keyword> [--out style.json]
1. Loads the user's genre matrix (genre_matrix.json).
2. Measures the raw footage: background/caption-zone luminance + dominant hues, skin hue.
3. Adapts the 4-color palette to the footage:
   - text-on-footage colors must reach WCAG contrast (≥4.5:1 small, ≥3:1 large) against the caption zone;
     if not → lighten/darken in OKLab-ish lightness, keeping hue.
   - accent must separate from the footage's dominant hue (≥30° hue distance) and from skin; if it clashes →
     rotate toward the footage complement while staying near the matrix hue family.
   - card backgrounds keep matrix hue but are blended toward the footage's own dominant color (≤35%) so cards feel
     like part of the same world.
4. Prints the matrix fonts; download them with: assets.py font "Family" ...
Every change is written with a reason, so the matrix stays the default and deviations are explicit.
"""
import sys, json, math, subprocess, colorsys, os
import numpy as np, cv2
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "genre_matrix.json")

def hex2rgb(h): h = h.lstrip("#"); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float) / 255
def rgb2hex(c): c = np.clip(np.round(np.asarray(c) * 255), 0, 255).astype(int); return "#%02X%02X%02X" % tuple(c)
def lin(c): c = np.asarray(c, float); return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def lum(c): l = lin(c); return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]
def contrast(a, b):
    la, lb = lum(a), lum(b); hi, lo = max(la, lb), min(la, lb); return (hi + 0.05) / (lo + 0.05)
def hue(c): return colorsys.rgb_to_hls(*np.clip(c, 0, 1))[0] * 360
def hdist(a, b): d = abs(a - b) % 360; return min(d, 360 - d)
def set_l(c, L):
    h, l, s = colorsys.rgb_to_hls(*np.clip(c, 0, 1)); return np.array(colorsys.hls_to_rgb(h, L, s))
def set_h(c, H):
    h, l, s = colorsys.rgb_to_hls(*np.clip(c, 0, 1)); return np.array(colorsys.hls_to_rgb((H % 360) / 360, l, s))

def measure(path, n=24):
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True).stdout)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={n / dur:.4f},scale=216:384", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, 384, 216, 3).astype(float) / 255
    cap = f[:, int(384 * 0.52):int(384 * 0.78), int(216 * 0.1):int(216 * 0.9)].reshape(-1, 3)   # caption zone
    allp = f.reshape(-1, 3)
    hsv = cv2.cvtColor((allp.reshape(1, -1, 3) * 255).astype(np.uint8), cv2.COLOR_RGB2HSV)[0].astype(float)
    sat = hsv[:, 1] > 60; skin = (hsv[:, 0] < 25) & (hsv[:, 1] > 50) & (hsv[:, 2] > 90)
    hist = np.bincount((hsv[sat & ~skin, 0] * 2 // 15).astype(int), minlength=24)
    dom_h = (np.argmax(hist) * 15 + 7.5) if hist.sum() else None
    dom_col = allp[sat & ~skin].mean(0) if (sat & ~skin).sum() else allp.mean(0)
    return dict(cap_mean=cap.mean(0), cap_p90=np.percentile(cap, 90, axis=0), cap_p10=np.percentile(cap, 10, axis=0),
                cap_lum=float(lum(cap.mean(0))), dom_hue=dom_h, dom_color=dom_col,
                skin_hue=float(np.median(hsv[skin, 0]) * 2) if skin.sum() else 20.0, bright=float(lum(allp.mean(0))))

def adapt(genre, M):
    P = {k: hex2rgb(v["hex"]) for k, v in genre["palette"].items()}
    changes = []; out = {}
    bg = M["cap_mean"]; bg_hi = M["cap_p90"]; dark_footage = M["cap_lum"] < 0.18
    # text on footage: neutral (3rd) for captions, accent (4th) for keywords
    for role, need in (("3rd", 4.5), ("4th", 3.0), ("secondary", 3.0)):
        c = P[role].copy(); orig = c.copy()
        target_bg = bg_hi if dark_footage else M["cap_p10"]
        tries = 0
        while contrast(c, target_bg) < need and tries < 40:
            h, l, s = colorsys.rgb_to_hls(*c)
            l = min(0.97, l + 0.02) if dark_footage else max(0.05, l - 0.02)
            if role == "4th": s = min(1.0, max(s, colorsys.rgb_to_hls(*orig)[2]) + 0.01)   # keep accent vivid while lightening
            c = np.array(colorsys.hls_to_rgb(h, l, s)); tries += 1
        if tries:
            changes.append(f"{role}: {rgb2hex(orig)} → {rgb2hex(c)} — contrast on footage caption zone was {contrast(orig, target_bg):.2f}:1, needs {need}:1")
        P[role] = c
    # accent separation from footage dominant hue & skin
    if M["dom_hue"] is not None:
        a = P["4th"]; ah = hue(a)
        # captions sit on clothes/background, not on skin → separate only from the footage's dominant hue
        for ref, name in ((M["dom_hue"], "footage dominant hue"),):
            if hdist(ah, ref) < 30:
                comp = (ref + 180) % 360
                newh = ah + max(-35, min(35, ((comp - ah + 540) % 360) - 180))
                P["4th"] = set_h(a, newh)
                changes.append(f"4th: {rgb2hex(a)} → {rgb2hex(P['4th'])} — hue {ah:.0f}° was within 30° of {name} ({ref:.0f}°); rotated toward complement")
                break
    # card background: matrix primary tinted toward the footage world
    prim = P["primary"]; tint = 0.30 if M["dom_hue"] is not None else 0.0
    card = prim * (1 - tint) + M["dom_color"] * tint * (lum(prim) / max(1e-3, lum(M["dom_color"]))) ** 0.5
    card = set_l(card, colorsys.rgb_to_hls(*np.clip(prim, 0, 1))[1])
    if tint: changes.append(f"card background: primary {rgb2hex(prim)} tinted 30% toward footage color {rgb2hex(M['dom_color'])} → {rgb2hex(card)} so cards belong to the same world")
    out = {k: rgb2hex(v) for k, v in P.items()}; out["card_bg"] = rgb2hex(card)
    # text on cards contrast
    if contrast(hex2rgb(out["3rd"]), card) < 4.5: changes.append("WARNING: 3rd on card < 4.5:1 — use 3rd as card bg and primary as text instead")
    return out, changes

def main():
    path, key = sys.argv[1], sys.argv[2]
    data = json.load(open(REF))
    g = next((x for x in data["genres"] if x["no"] == key or key.lower() in x["niche"].lower()), None)
    if g is None: sys.exit("genre not found: " + key)
    M = measure(path); pal, ch = adapt(g, M)
    style = dict(genre=g["niche"], matrix_palette={k: v["hex"] for k, v in g["palette"].items()}, adapted_palette=pal, palette_changes=ch,
                 fonts=g["fonts"], music=g["music"], sfx=g["sfx"], motion=g["motion"], broll=g["broll"], delivery=g["delivery"], hook=g["hook"],
                 rhythm=g["rhythm"], notes=g["notes"],
                 footage=dict(caption_zone=rgb2hex(M["cap_mean"]), caption_lum=round(M["cap_lum"], 3), dominant_hue=M["dom_hue"],
                              dominant_color=rgb2hex(M["dom_color"]), skin_hue=round(M["skin_hue"]), brightness=round(M["bright"], 3)))
    if "--out" in sys.argv: json.dump(style, open(sys.argv[sys.argv.index("--out") + 1], "w"), indent=1)
    print("GENRE:", style["genre"]); print("PALETTE:", style["adapted_palette"])
    for c in ch: print("  adapt:", c)
    print("FONTS:", "; ".join(f"{k}={v['family']} {v['weights']}" for k, v in style["fonts"].items()))
    print("FOOTAGE:", style["footage"])
    for k in ("motion", "broll", "music", "sfx", "rhythm", "notes"): print(k.upper() + ":", style[k])

if __name__ == "__main__":
    main()
