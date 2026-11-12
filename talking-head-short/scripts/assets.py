"""Licensed free assets (no attribution needed): Mixkit music / SFX / stock video, Google Fonts (OFL).
python assets.py music  "calm piano"   [--n 6]      → lists candidates (id | title | genre | dur | bpm?)
python assets.py sfx    "whoosh"       [--n 8]
python assets.py video  "coffee shop"  [--n 6]
python assets.py get music|sfx|video ID OUTDIR       → downloads, appends license line to OUTDIR/LICENSES.txt
python assets.py font "DM Sans" ["Lora" ...]         → downloads Google Font families into ASSETS/fonts
If network is blocked, print the page URL so the user can download and upload the file themselves."""
import sys, os, re, json, html, urllib.request, urllib.parse
UA = {"User-Agent": "Mozilla/5.0"}
ASSETS = os.environ.get("THS_ASSETS", os.path.expanduser("~/.ths_assets"))
def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf8", "ignore")
def slug(q): return urllib.parse.quote(q.strip().lower().replace(" ", "-"))

def search(kind, q, n):
    path = {"music": "free-stock-music", "sfx": "free-sound-effects", "video": "free-stock-video"}[kind]
    url = f"https://mixkit.co/{path}/discover/{slug(q)}/"
    try: h = fetch(url)
    except Exception as e: print("NETWORK_BLOCKED", url); return
    out = []
    if kind == "music":
        for m in re.finditer(r'data-audio-player-item-id-value="(\d+)"\s+data-audio-player-item-type-value="music"', h):
            seg = h[m.start():m.start() + 4000]
            t = re.search(r'item-grid-card__title">\s*([^<]+?)\s*<', seg)
            tags = re.findall(r'meta-links__link" data-global--meta-links-target="link" href="[^"]+">([^<]+)<', seg)[:5]
            out.append(f"{m.group(1)} | {html.unescape(t.group(1)) if t else '?'} | {', '.join(tags)}")
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
            try: d = json.loads(m.group(1))
            except Exception: continue
            for g in d.get("@graph", []):
                for it in (g.get("itemListElement", []) if isinstance(g, dict) else []):
                    if it.get("@type") == "MusicRecording":
                        mid = re.search(r"/music/(\d+)/", it["url"]).group(1)
                        out.append(f"{mid} | {it['name']} | {it.get('genre','')} | {it.get('duration','').replace('PT','')}")
    elif kind == "sfx":
        for m in re.finditer(r'sfx/(\d+)/\1-preview\.mp3', h):
            seg = h[max(0, m.start() - 3000):m.start()]
            t = re.findall(r'item-grid-card__title[^>]*>\s*([^<]+?)\s*<', seg)
            out.append(f"{m.group(1)} | {html.unescape(t[-1]) if t else '?'}")
    else:
        for m in re.finditer(r'data-algolia-analytics-object-id="video-(\d+)"', h):
            seg = h[m.start():m.start() + 6000]
            t = re.search(r'overlay-video-title">\s*([^<]+?)\s*<', seg)
            out.append(f"{m.group(1)} | {html.unescape(t.group(1)) if t else '?'}")
    seen = []
    for x in out:
        if x not in seen: seen.append(x)
    print("\n".join(seen[:n]) or "none")

def get(kind, iid, outdir):
    os.makedirs(outdir, exist_ok=True)
    url = {"music": f"https://assets.mixkit.co/music/{iid}/{iid}.mp3",
           "sfx": f"https://assets.mixkit.co/active_storage/sfx/{iid}/{iid}-preview.mp3",
           "video": f"https://assets.mixkit.co/videos/{iid}/{iid}-720.mp4"}[kind]
    fn = os.path.join(outdir, f"{kind}_{iid}." + ("mp4" if kind == "video" else "mp3"))
    try:
        urllib.request.urlretrieve(url if False else url, fn) if False else open(fn, "wb").write(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read())
    except Exception:
        print("NETWORK_BLOCKED", url); return
    with open(os.path.join(outdir, "LICENSES.txt"), "a") as f:
        f.write(f"{os.path.basename(fn)}  Mixkit Free License (no attribution)  {url}\n")
    print(fn)

def font(fams):
    for fam in fams:
        base = re.sub(r"\s+(Italic|Bold)$", "", fam).strip(); s = base.lower().replace(" ", "")
        d = os.path.join(ASSETS, "fonts", s)
        if os.path.isdir(d) and any(f.endswith(".ttf") for f in os.listdir(d)): print(fam, "→", d); continue
        ok = False
        for lic in ("ofl", "apache", "ufl"):
            try: items = json.loads(fetch(f"https://api.github.com/repos/google/fonts/contents/{lic}/{s}"))
            except Exception: continue
            os.makedirs(d, exist_ok=True)
            for it in items:
                if it["name"].endswith(".ttf") or it["name"] in ("OFL.txt", "LICENSE.txt"):
                    open(os.path.join(d, it["name"]), "wb").write(urllib.request.urlopen(urllib.request.Request(it["download_url"], headers=UA), timeout=60).read())
            ok = True; break
        print(fam, "→", d if ok else "NOT_AVAILABLE (fallback font will be used)")

if __name__ == "__main__":
    a = sys.argv[1:]
    n = int(a[a.index("--n") + 1]) if "--n" in a else 6
    if a[0] in ("music", "sfx", "video"): search(a[0], a[1], n)
    elif a[0] == "get": get(a[1], a[2], a[3])
    elif a[0] == "font": font(a[1:])
