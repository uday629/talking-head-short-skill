"""Licensed free assets with automatic fallbacks (no attribution needed anywhere).
  music/sfx:  Mixkit (free license)  → GitHub mirror CC0 pack (OpenGameArt public-domain music + SFX)
  fonts:      Google Fonts repo (OFL) → GitHub mirror OFL font pack (32 families) → system font
  video:      Mixkit stock video      → none (use motion-graphic cards instead)
python assets.py music "calm piano" [--n 6]   → candidates:  id | title | tags      (pack ids look like pack:lofi_chill)
python assets.py sfx   "whoosh"     [--n 8]
python assets.py video "coffee shop" [--n 6]
python assets.py get music|sfx|video ID WORKDIR  → downloads into WORKDIR + LICENSES.txt line
python assets.py font "DM Sans" "Lora" ...       → ensures fonts in $THS_ASSETS/fonts
python assets.py pack                            → lists the whole CC0 pack (works fully offline after first download)"""
import sys, os, re, json, html, shutil, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import net
ASSETS = net.ASSETS
def slug(q): return urllib.parse.quote(q.strip().lower().replace(" ", "-"))

# ───────── CC0 pack (GitHub mirror)
def pack():
    d = net.mirror_zip("ths-pack.zip", os.path.join(ASSETS, "pack"))
    return os.path.join(d, "ths-pack"), json.load(open(os.path.join(d, "ths-pack", "manifest.json")))
def pack_search(kind, q, n):
    try: root, man = pack()
    except Exception as e: print("PACK_UNAVAILABLE", str(e)[:120]); return
    words = [w for w in re.split(r"\W+", q.lower()) if w]
    items = [m for m in man if m["kind"] == kind]
    items.sort(key=lambda m: -sum(w in (m["mood"] + " " + m["file"]).lower() for w in words))
    for m in items[:n]:
        pid = "pack:" + os.path.splitext(os.path.basename(m["file"]))[0]
        print(f"{pid} | {m['mood']}" + (f" | {m.get('bpm')} BPM {m.get('mode','')} {m.get('dur','')}s" if kind == "music" else ""))

# ───────── Mixkit
def mixkit_search(kind, q, n):
    path = {"music": "free-stock-music", "sfx": "free-sound-effects", "video": "free-stock-video"}[kind]
    h = net.get(f"https://mixkit.co/{path}/discover/{slug(q)}/", 30).decode("utf8", "ignore")
    out = []
    if kind == "music":
        for m in re.finditer(r'data-audio-player-item-id-value="(\d+)"\s+data-audio-player-item-type-value="music"', h):
            seg = h[m.start():m.start() + 4000]
            t = re.search(r'item-grid-card__title">\s*([^<]+?)\s*<', seg)
            tags = re.findall(r'meta-links__link" data-global--meta-links-target="link" href="[^"]+">([^<]+)<', seg)[:5]
            out.append(f"{m.group(1)} | {html.unescape(t.group(1)) if t else '?'} | {', '.join(tags)}")
    elif kind == "sfx":
        for m in re.finditer(r'sfx/(\d+)/\1-preview\.mp3', h):
            seg = h[max(0, m.start() - 3000):m.start()]
            t = re.findall(r'item-grid-card__title[^>]*>\s*([^<]+?)\s*<', seg)
            out.append(f"{m.group(1)} | {html.unescape(t[-1]) if t else '?'}")
    else:
        for m in re.finditer(r'data-algolia-analytics-object-id="video-(\d+)"', h):
            t = re.search(r'overlay-video-title">\s*([^<]+?)\s*<', h[m.start():m.start() + 6000])
            out.append(f"{m.group(1)} | {html.unescape(t.group(1)) if t else '?'}")
    seen = []
    for x in out:
        if x not in seen: seen.append(x)
    return seen[:n]

def search(kind, q, n):
    try:
        r = mixkit_search(kind, q, n)
        if r: print("\n".join(r)); return
    except Exception as e:
        print("mixkit unreachable →", "CC0 pack" if kind != "video" else "no stock video", f"({str(e)[:50]})")
    if kind == "video": print("NO_BROLL_SOURCE → use motion-graphic cards instead (or ask the user to upload clips)"); return
    pack_search(kind, q, n)

def get(kind, iid, outdir):
    os.makedirs(outdir, exist_ok=True)
    if iid.startswith("pack:"):
        root, man = pack(); name = iid[5:]
        m = next(x for x in man if os.path.splitext(os.path.basename(x["file"]))[0] == name)
        fn = os.path.join(outdir, f"{kind}_{name}.mp3"); shutil.copy(os.path.join(root, m["file"]), fn)
        lic = f"CC0 public domain (OpenGameArt, via GitHub mirror)  {m['source']}"
    else:
        url = {"music": f"https://assets.mixkit.co/music/{iid}/{iid}.mp3",
               "sfx": f"https://assets.mixkit.co/active_storage/sfx/{iid}/{iid}-preview.mp3",
               "video": f"https://assets.mixkit.co/videos/{iid}/{iid}-720.mp4"}[kind]
        fn = os.path.join(outdir, f"{kind}_{iid}." + ("mp4" if kind == "video" else "mp3"))
        try: open(fn, "wb").write(net.get(url, 180))
        except Exception as e: print("DOWNLOAD_FAILED", url, str(e)[:60], "→ pick a pack: id instead"); return
        lic = f"Mixkit Free License (no attribution)  {url}"
    with open(os.path.join(outdir, "LICENSES.txt"), "a") as f: f.write(f"{os.path.basename(fn)}  {lic}\n")
    print(fn)

# ───────── fonts
def font(fams):
    fdir = os.path.join(ASSETS, "fonts")
    for fam in fams:
        base = re.sub(r"\s+(Italic|Bold)$", "", fam).strip(); s = base.lower().replace(" ", "")
        d = os.path.join(fdir, s)
        if os.path.isdir(d) and any(f.endswith(".ttf") for f in os.listdir(d)): print(fam, "→ ok"); continue
        ok = False
        for lic in ("ofl", "apache", "ufl"):                         # 1) Google Fonts repo on GitHub
            try: items = json.loads(net.get(f"https://api.github.com/repos/google/fonts/contents/{lic}/{s}", 30))
            except Exception: continue
            os.makedirs(d, exist_ok=True)
            for it in items:
                if it["name"].endswith(".ttf") or it["name"] in ("OFL.txt", "LICENSE.txt"):
                    open(os.path.join(d, it["name"]), "wb").write(net.first([it["download_url"],
                        f"https://cdn.jsdelivr.net/gh/google/fonts@main/{lic}/{s}/{urllib.parse.quote(it['name'])}"])[0])
            ok = True; break
        if not ok:                                                    # 2) GitHub mirror font pack (OFL)
            try:
                p = net.mirror_zip("ths-fonts.zip", os.path.join(ASSETS, "fontpack"))
                src = os.path.join(p, "ths-fonts", s)
                if os.path.isdir(src): shutil.copytree(src, d, dirs_exist_ok=True); ok = True
            except Exception as e: print("font pack unavailable:", str(e)[:80])
        print(fam, "→ ok" if ok else "→ NOT_AVAILABLE (engine uses a system fallback; pick another family from the pack list)")

if __name__ == "__main__":
    a = sys.argv[1:]
    n = int(a[a.index("--n") + 1]) if "--n" in a else 6
    if a[0] in ("music", "sfx", "video"): search(a[0], a[1], n)
    elif a[0] == "get": get(a[1], a[2], a[3])
    elif a[0] == "font": font(a[1:])
    elif a[0] == "pack": pack_search("music", "", 50); pack_search("sfx", "", 50)
