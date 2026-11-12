"""ffmpeg/ffprobe resolver. Works with a system ffmpeg, or with the pip-installed static build (imageio-ffmpeg)
when the sandbox has none. ffprobe is optional: probe() falls back to parsing `ffmpeg -i`."""
import os, re, shutil, subprocess, json

def _find():
    f = shutil.which("ffmpeg")
    if f: return f
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise SystemExit("ffmpeg not found → run setup.sh (installs a static ffmpeg via pip)")
FFMPEG = _find()
FFPROBE = shutil.which("ffprobe")

def probe(path):
    """→ dict(w, h, fps, dur, audio)"""
    if FFPROBE:
        j = json.loads(subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
                                       "-of", "json", path], capture_output=True, text=True).stdout)
        v = next(s for s in j["streams"] if s["codec_type"] == "video"); n, d = v["r_frame_rate"].split("/")
        return dict(w=v["width"], h=v["height"], fps=round(int(n) / int(d), 3), dur=round(float(j["format"]["duration"]), 2),
                    audio=any(s["codec_type"] == "audio" for s in j["streams"]))
    e = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", e); dur = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0
    v = re.search(r"Video: .*?(\d{2,5})x(\d{2,5})", e); fps = re.search(r"([\d.]+) fps", e)
    rot = re.search(r"rotate\s*:\s*(-?\d+)|rotation of (-?[\d.]+)", e)
    w, h = (int(v[1]), int(v[2])) if v else (0, 0)
    if rot and abs(int(float(rot[1] or rot[2]))) % 180 == 90: w, h = h, w
    return dict(w=w, h=h, fps=float(fps[1]) if fps else 30.0, dur=round(dur, 2), audio="Audio:" in e)
