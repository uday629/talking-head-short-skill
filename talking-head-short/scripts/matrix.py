"""Rebuild references/genre_matrix.json from the user's Excel sheet (run whenever the sheet changes).
python matrix.py talking_head_genre_editing_matrix.xlsx [--out ../references/genre_matrix.json]
Reads: GENRE EDITING MATRIX (one row per niche), MOTION STYLE GUIDE, COLOR PALETTE GUIDE, GOOGLE FONTS LIBRARY.
Needs openpyxl (pip install openpyxl)."""
import sys, os, re, json
try:
    import openpyxl
except ImportError:
    sys.exit("pip install openpyxl  (only needed to convert the sheet)")

HERE = os.path.dirname(os.path.abspath(__file__))
COLS = {"no.": "no", "niche": "niche", "b-roll": "broll", "primary motion": "motion_style", "key visual": "elements",
        "movement": "mechanics", "color palette": "palette_text", "font pair": "fonts_text", "music": "music", "sfx": "sfx",
        "presenter": "delivery", "hook": "hook", "rhythm": "rhythm", "on-screen": "notes", "motion design": "motion_style"}

def rows(ws):
    out = [[("" if c is None else str(c).strip()) for c in r] for r in ws.iter_rows(values_only=True)]
    hi = next(i for i, r in enumerate(out) if sum(bool(c) for c in r) >= 4)        # first real header row
    return out[hi], [r for r in out[hi + 1:] if any(r)]

def palette(txt):
    P = {}
    for role, hx, name in re.findall(r"(Primary|Secondary|3rd|4th)\s*(#[0-9A-Fa-f]{6})\s*(?:\(([^)]*)\))?", txt):
        P[role.lower() if role[0].isalpha() else role] = {"hex": hx.upper(), "name": name}
    return P

def fonts(txt):
    F = {}
    for part in txt.split("|"):
        m = re.match(r"\s*([A-Z /&-]+):\s*(.+)", part)
        if not m: continue
        role = m[1].strip().lower().replace(" / ", "_").replace(" ", "_")
        fam = re.split(r"\(| for | Google Fonts", m[2])[0].strip().rstrip(".")
        w = re.search(r"\(([^)]*)\)", m[2])
        F[role] = {"family": fam, "weights": w[1] if w else "400"}
    return F

def main():
    src = sys.argv[1]; out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(HERE, "..", "references", "genre_matrix.json")
    wb = openpyxl.load_workbook(src, data_only=True)
    ws = next(w for w in wb.worksheets if "MATRIX" in w.title.upper())
    hdr, data = rows(ws)
    keys = []
    for h in hdr:
        hl = h.lower(); keys.append(next((v for k, v in COLS.items() if k in hl), None))
    genres = []
    for r in data:
        g = {k: r[i] for i, k in enumerate(keys) if k and i < len(r)}
        if not g.get("no") or not g.get("niche"): continue
        g["no"] = str(g["no"]).split(".")[0]
        g["palette"] = palette(g.get("palette_text", "")); g["fonts"] = fonts(g.get("fonts_text", ""))
        g.setdefault("motion", " · ".join(x for x in (g.get("motion_style", ""), g.get("elements", "")) if x))
        genres.append(g)
    J = {"source": os.path.basename(src), "genres": genres}
    for w in wb.worksheets:
        t = w.title.upper()
        if "MOTION STYLE" in t:
            h, d = rows(w); J["motion_guide"] = [dict(zip(["category", "visual", "text", "elements", "fps_easing", "signature", "niches"], r)) for r in d if r[0]]
        elif "PALETTE" in t:
            h, d = rows(w); J["palette_roles"] = [dict(zip(["role", "purpose", "coverage", "example", "accessibility", "important"], r)) for r in d if r[0]]
        elif "FONT" in t:
            h, d = rows(w); J["font_library"] = [dict(zip(["family", "best_use", "weights", "role", "url"], r)) for r in d if r[0]]
    json.dump(J, open(out, "w"), indent=1, ensure_ascii=False)
    print(f"{len(genres)} genres · {len(J.get('motion_guide', []))} motion styles · {len(J.get('font_library', []))} fonts → {out}")

if __name__ == "__main__":
    main()
