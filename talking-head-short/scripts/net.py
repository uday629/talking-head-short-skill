"""Downloads with fallbacks. Many sandboxes (claude.ai code execution) block most sites but allow GitHub,
so every asset has a GitHub-hosted mirror on this repo's 'assets-v1' release.
THS_BLOCK="host1,host2" simulates blocked hosts (for testing)."""
import os, urllib.request, zipfile, io
REPO = os.environ.get("THS_REPO", "uday629/talking-head-short-skill")
MIRROR = f"https://github.com/{REPO}/releases/download/assets-v1/"
ASSETS = os.environ.get("THS_ASSETS", os.path.expanduser("~/.ths_assets"))
UA = {"User-Agent": "Mozilla/5.0 (talking-head-short skill)"}
BLOCK = [h for h in os.environ.get("THS_BLOCK", "").split(",") if h]

def get(url, timeout=120):
    if any(h in url for h in BLOCK): raise OSError("blocked (simulated): " + url)
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()

def first(urls, timeout=120):
    """try each url in order → (bytes, url). Raises OSError listing every failure."""
    errs = []
    for u in urls:
        try: return get(u, timeout), u
        except Exception as e: errs.append(f"{u.split('/')[2]}: {str(e)[:60]}")
    raise OSError("all sources failed → " + " | ".join(errs))

def mirror_zip(name, dest):
    """download MIRROR/name (a .zip) once and extract into dest; returns dest."""
    flag = os.path.join(dest, ".ok_" + name)
    if os.path.exists(flag): return dest
    os.makedirs(dest, exist_ok=True)
    data, _ = first([MIRROR + name], timeout=600)
    zipfile.ZipFile(io.BytesIO(data)).extractall(dest)
    open(flag, "w").write("ok"); return dest
