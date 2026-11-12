"""Measured primary color correction (order: levels/exposure → white balance → contrast → saturation → skin).
Targets from research: neutral blacks ~0.02–0.04 (not crushed, not milky), speculars ≤0.92, skin Y ~0.55–0.60,
skin hue on the skin-tone line (~123° on a Rec.709 vectorscope), saturation +5–10% with skin protected."""
import numpy as np, cv2, math

def measure(img):  # img float RGB 0..1 (source framing 540x960)
    Y = 0.2126 * img[..., 0] + 0.7152 * img[..., 1] + 0.0722 * img[..., 2]
    tee = img[600:700, 150:300].reshape(-1, 3).mean(0)
    skin = img[300:345, 255:320].reshape(-1, 3).mean(0)
    return dict(black=float(np.percentile(Y, 1)), white=float(np.percentile(Y, 99.7)), tee=tee, skin=skin)

def build(ref):
    """Derive correction parameters from a reference raw frame."""
    tee = ref["tee"]; g = tee.mean() / np.maximum(tee, 1e-4)        # neutralise the black t-shirt (true neutral)
    g = 1 + (g - 1) * 0.8
    b_in = ref["black"] - 0.012; w_in = ref["white"] + 0.02
    return dict(gain=g.astype(np.float32), b_in=b_in, w_in=w_in)

def ycc(rgb):
    Y = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    return Y, (rgb[..., 2] - Y) / 1.8556, (rgb[..., 0] - Y) / 1.5748
def rgb_from(Y, cb, cr):
    R = Y + 1.5748 * cr; B = Y + 1.8556 * cb; G = (Y - 0.2126 * R - 0.0722 * B) / 0.7152
    return np.stack([R, G, B], -1)

def correct(img, P, skin_target=123.0, sat=1.08, contrast=0.16, out_black=0.028, out_white=0.90):
    x = img * P["gain"]                                              # 1. white balance (from neutral reference)
    x = (x - P["b_in"]) / (P["w_in"] - P["b_in"])                    # 2. levels: set black & white points
    x = out_black + np.clip(x, 0, 1.05) * (out_white - out_black)
    Y, cb, cr = ycc(np.clip(x, 0, 1))
    Ys = Y + contrast * (Y - 0.42) * (1 - np.abs(2 * Y - 0.84))      # 3. gentle S contrast around mids (luma only)
    Ys = np.clip(Ys, 0, 1)
    ang = np.degrees(np.arctan2(cr, cb)) % 360; mag = np.hypot(cb, cr)
    w = np.clip(1 - np.abs(((ang - 118 + 180) % 360) - 180) / 30, 0, 1) * np.clip((Ys - 0.25) / 0.2, 0, 1)
    rot = np.radians((skin_target - 116.0) * w)                       # 4. skin hue → skin-tone line
    ca, sa = np.cos(rot), np.sin(rot)
    cb2 = cb * ca - cr * sa; cr2 = cb * sa + cr * ca
    s = sat * (1 - 0.06 * w)                                          # 5. saturation, skin protected
    out = rgb_from(Ys, cb2 * s, cr2 * s)
    return np.clip(out, 0, 1).astype(np.float32)
