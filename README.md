# talking-head-short — Claude skill

A master editing skill for **vertical talking-head short videos** (Instagram Reels, TikTok, YouTube Shorts).
Give Claude a raw clip and type `/talking-head-short`. Claude then:

1. **Analyzes** the clip: transcribes it with word timestamps, removes fillers, stutters, restarts and dead air, and lets you judge the remaining bad takes.
2. **Understands it:** topic, core message, emotion arc, and the niche from a 24-genre editing matrix (finance, self-help, business, health, tech…).
3. **Asks before editing:** style, font pair, color palette, visual density, music choice, and B-roll on or off.
4. **Builds the edit** from a small `spec.json`:
   - kinetic captions on a golden ratio (lead / KEY / accent) that are never cut off,
   - 14 motion-graphic templates (compare, list, steps, counter, scale, cycle, timeline, quote, checklist, search, bars, statement, flow, orbit) with auto-picked icons, plus a per-video look.py design system,
   - licensed B-roll, an eye-locked eased camera, smooth transitions, and color *correction* (not a filter).
5. **Mixes the audio:** cleans the voice, adds licensed music ducked under speech (a musical phrase can land on your payoff line) and subtle SFX, and masters to -14 LUFS.
6. **Runs QA:** a contact sheet of every caption/card end frame, a flash-frame scan, and a loudness check.

All music, SFX, B-roll and fonts are downloaded at run time from **copyright-free sources**: Mixkit (free license, no attribution) and Google Fonts (SIL OFL). Each job keeps a `LICENSES.txt`.

---

## Install

### Claude Code (recommended, full quality)
```bash
git clone https://github.com/uday629/talking-head-short-skill.git
mkdir -p ~/.claude/skills
cp -r talking-head-short-skill/talking-head-short ~/.claude/skills/
```
Restart Claude Code. Then: `/talking-head-short` plus the path to your raw video.

### Claude desktop / claude.ai
Download `talking-head-short.zip` from the **Releases** page (or zip the `talking-head-short/` folder yourself).
Then go to **Settings → Capabilities → Skills → Upload skill**. Code execution must be enabled.

## Requirements
- `ffmpeg` (optional: if missing, setup installs a static build from PyPI)
- Python 3.9+. The skill's `setup.sh` creates a venv with numpy, scipy, pillow, opencv-python-headless (<5) and faster-whisper.
- Internet access to PyPI and GitHub (HuggingFace/Mixkit/Google Fonts are optional; see below).

### claude.ai: turn on network access first
The sandbox needs internet to install Python libraries and download the model and assets.
**Settings → Capabilities → Code execution → Network access → "All domains"**, or allow at least:
`pypi.org, files.pythonhosted.org, github.com, objects.githubusercontent.com, release-assets.githubusercontent.com, api.github.com, raw.githubusercontent.com, cdn.jsdelivr.net` (plus optionally `huggingface.co, mixkit.co, assets.mixkit.co`).
With network access off ("None"), the skill cannot run: the speech model and libraries are hundreds of MB, too large to ship inside a skill.

### Works in Claude's sandbox (free plan included)
Sandboxes often block HuggingFace, Mixkit and the Google Fonts API, but allow GitHub and PyPI. The skill falls back automatically to this repo's **[assets-v1 release](https://github.com/uday629/talking-head-short-skill/releases/tag/assets-v1)**:

| need | first source | fallback |
|---|---|---|
| ffmpeg | system | static build from PyPI (`imageio-ffmpeg`) |
| speech-to-text | HuggingFace Whisper | `whisper-base.zip` / `whisper-tiny.zip` (MIT) |
| music + SFX | Mixkit (free license) | `ths-pack.zip`: 8 tracks + 13 SFX, CC0 public domain (OpenGameArt) |
| fonts | Google Fonts (GitHub API → jsDelivr) | `ths-fonts.zip`: 42 OFL families (covers every style family in look.py) |
| B-roll | Mixkit stock video | motion-graphic cards instead (or upload your own clips) |

Long renders are split into parts (`--part i/N`, then `--concat N`) to fit sandbox time limits. Rendering is CPU-heavy, so a laptop with Claude Code is much faster.
If your fork lives elsewhere, set `THS_REPO=owner/repo` so the mirrors point at your releases.

## How it works
```
talking-head-short/
├── SKILL.md                 workflow Claude follows (analyze → brief → ask → assets → spec → plan → styleframes → render → mix → QA)
├── references/
│   ├── craft.md             editing rules: face vs cut-away, typography, color, camera, cuts, sound
│   ├── spec.md              the spec.json format + motion-graphic template catalog
│   └── genre_matrix.json    24 niches × B-roll / MG / palette / fonts / music / SFX / delivery / hook / rhythm / notes
└── scripts/
    ├── setup.sh             one-time environment
    ├── analyze.py           transcribe, clean cut, eye point, report
    ├── net.py / ff.py       download fallbacks (GitHub mirror) + ffmpeg resolver
    ├── align_text.py        fallback word timing from a pasted transcript
    ├── style.py             picks the genre row and adapts the palette to the real footage (contrast/hue), with reasons
    ├── assets.py            search/download Mixkit music/SFX/video + Google Fonts
    ├── engine.py            renderer (captions, cards, B-roll, camera, color, transitions) + plan checks + styleframes
    ├── render.sh            parallel render
    ├── mix.py               voice clean-up, music, SFX, -14 LUFS, mux
    ├── qa.py                end-frame contact sheet, flash frames, loudness
    └── cc.py                measured color correction
```

Typical render speed: about 5 minutes per minute of 1080×1920 video on a laptop (parallel).

## Editing principles baked in
- Style follows **topic + emotion**, never "what looks cool".
- Captions: two contrasting font styles, lead = key ÷ 1.618 (x-height), tight proximity, rotating composed layouts. Every caption finishes animating and stays on screen ≥0.3 s.
- Motion graphics translate meaning (no clip art), finish before the scene changes, and stay in one visual system.
- Smooth: no flash frames, transitions snapped off raw cuts, eye-level locked zoom.
- The genre matrix is the default; the footage is the judge (palette auto-adapted for contrast).

## License
MIT for the code and docs (see `LICENSE`). Downloaded assets keep their own licenses (Mixkit Free License, SIL OFL).
