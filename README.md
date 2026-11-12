# talking-head-short — Claude skill

A master editing skill for **vertical talking-head short videos** (Instagram Reels, TikTok, YouTube Shorts).
Give Claude a raw clip and type `/talking-head-short`. Claude then:

1. **Analyzes** the clip: transcribes it with word timestamps, removes fillers, stutters, restarts and dead air, and lets you judge the remaining bad takes.
2. **Understands it:** topic, core message, emotion arc, and the niche from a 24-genre editing matrix (finance, self-help, business, health, tech…).
3. **Asks before editing:** style, font pair, color palette, visual density, music choice, and B-roll on or off.
4. **Builds the edit** from a small `spec.json`:
   - kinetic captions on a golden ratio (lead / KEY / accent) that are never cut off,
   - 12 motion-graphic templates (compare, list, steps, counter, scale, cycle, timeline, quote, checklist, search, bars, statement),
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
- `ffmpeg` (mac: `brew install ffmpeg` · linux: `apt-get install -y ffmpeg`)
- Python 3.9+. The skill's `setup.sh` creates a venv with numpy, scipy, pillow, opencv-python-headless (<5) and faster-whisper.
- Internet access for the first transcription model download and for assets.

### Notes for the claude.ai sandbox / free plan
The sandbox may block downloads or limit run time. The skill degrades gracefully:
- If transcription can't install, paste or upload a transcript or `.srt` and it aligns the words (`align_text.py`).
- If asset downloads are blocked, it gives you the Mixkit / Google Fonts links to download and upload yourself, or continues without them.
- If renders hit a time limit, it renders in parts (`--part i/N`, then `--concat N`).

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
