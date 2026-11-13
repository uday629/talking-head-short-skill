---
name: talking-head-short
description: Master editor for vertical talking-head short videos (Reels, TikTok, Shorts). From one raw clip it transcribes, removes bad takes and silences, detects the niche (24-genre matrix), asks the user to choose style options, then renders a smooth, professional edit with golden-ratio kinetic captions, meaning-driven motion graphics, licensed B-roll, music, SFX and fonts, color correction, and QA. Use it whenever the user gives a raw talking-head, podcast-clip, coach, founder, UGC or explainer video and wants it edited or "made viral", types /talking-head-short, or asks for captions, motion graphics, B-roll or a reel edit, even if they don't name the skill.
---

# Talking-Head Short — master editor

Write terse replies. Don't echo transcripts or long logs. Fix things by editing `spec.json` with the Edit tool, never by rewriting it. Every script prints a compact report; read it, act, move on.

`S=<this skill dir>/scripts`, `WD=<work dir next to the raw file>/ths_<name>`.

## 0. Setup (once per machine/sandbox)
`bash $S/setup.sh` → use the printed `PY=`. It installs everything from PyPI, including a static ffmpeg if none exists.
Every download has an automatic fallback. Sandboxes (claude.ai code execution, free or paid) usually block HuggingFace, Mixkit and the Google Fonts API, but allow GitHub:
- transcription model: HuggingFace → GitHub mirror (whisper-base, then whisper-tiny)
- music/SFX: Mixkit → GitHub mirror CC0 pack (ids look like `pack:lofi_chill`)
- fonts: Google Fonts repo → jsDelivr → GitHub mirror OFL pack (37 families, covers every style family in look.py) → system font
- B-roll: Mixkit → none (use cards, or ask the user to upload clips)
If setup prints "no network" / pip fails: the sandbox has network egress OFF. Tell the user exactly (one message):
"claude.ai → Settings → Capabilities → Code execution → Network access: **All domains** (or add: pypi.org, files.pythonhosted.org, github.com, objects.githubusercontent.com, release-assets.githubusercontent.com, api.github.com, raw.githubusercontent.com, cdn.jsdelivr.net, huggingface.co, mixkit.co, assets.mixkit.co), then start a new chat and run /talking-head-short again." Don't attempt the edit without numpy/ffmpeg.
Only if every source fails: ask for a pasted transcript → `$PY $S/align_text.py $WD transcript.txt`. Assets cache in `~/.ths_assets`.

## 1. Analyze
`$PY $S/analyze.py RAW $WD`
It prints the resolution, eye point, the clean length, auto-removed fillers/stutters/restarts, CHECK (soft fillers, low-confidence words, long pauses), and TEXT with timestamps every 8 words.
- **Judge bad takes yourself.** Remove false starts, unfinished sentences, "you know like yeah", "kind of". Keep rhetorical repetition. Re-run with `--remove '[[s,e],...]'` (source seconds). Transcription is cached.
- Look at `$WD/frames.jpg` only if the eye point or framing is in doubt.

## 2. Brief (in your head, then 4 lines to the user)
Write: topic · core message · emotion arc (hook → … → payoff) · niche row (from NICHES) · tone (calm/balanced/energetic) · raw framing (wide or tight).
Then run `$PY $S/look.py RAW "<niche>" $WD --tone <tone>`. This is the per-video DESIGN SYSTEM step — it is why two videos never come out looking the same.
It measures the actual footage (its own colors, brightness, caption-zone contrast), reads the niche row's motion-style/elements/mechanics from the sheet, and combines them with a random seed and a rolling history of your last ~30 looks (so a repeat family/palette/font/card-set combo is actively avoided) to print **3 distinct LOOK options (A/B/C)** — each a full system: style family (2D vector / UI-glass / tech-HUD / hand-drawn / papercraft / kinetic-type / documentary-editorial / luxe-editorial / blueprint), background texture, a footage-contrast-checked palette, a font trio, caption treatment, card-transition set, and which card types suit that family.
Read `references/craft.md` once (the rules), `references/spec.md` (the spec format), and `references/motion_style_8.md` (which family actually does what, and which engine mechanic realizes it — glow/stroke/grain/tilt/boil/stepped-time/shake/icons/cursor/orbit-3D). A card type is not the motion system: `list`/`counter`/`search` are plain content shapes any family can use, but the *family* (from `look.json`) is what must differ video to video — if two videos in a row come out both flat-text-on-a-card with no glow, no icons, no boil/shake/orbit, something upstream picked the same family or ignored `look.json`'s `elements`/`cards`/`transitions`. Pick card types from `look.json`'s own `cards` list (it already excludes types that don't fit the family), favor `flow`/`cycle`/`list` with real icons (the engine auto-picks one per item — `it.get("icon")` overrides when you want a specific one) over a plain bulleted list, and use `orbit` for any product/gadget/real-estate/luxury beat.

## 3. Ask before building (never render first)
Use AskUserQuestion if available; otherwise one compact numbered message. Recommend option 1 each time.
1. **Look:** the 3 printed LOOK options (A/B/C) — show the one-line description of each, recommend the top-scored one. Don't re-ask about fonts/palette separately; they're inside the look. If the user wants a tweak, use the override flags (`--palette sheet|footage|blend`, `--family NAME`, `--accent "#hex"`, `--bg KIND`) rather than hand-editing colors.
2. **Visual density:** Minimal (captions + 2–3 cards) · Balanced (captions + 4–6 cards / B-roll) · Rich (more MG + B-roll).
3. **Music:** 3 licensed candidates from `$PY $S/assets.py music "<mood>"` (id · title · tags), or none.
4. **B-roll:** yes (licensed stock matching literal lines) / no.
Skip any question the user already answered. Wait for the answers, then `$PY $S/look.py --pick A $WD` (or B/C, with overrides) → writes `$WD/look.json` and downloads its fonts. The engine reads `look.json` automatically and it overrides spec.json's `palette`/`fonts` fields — don't write those by hand when a look.json exists.

## 4. Gather assets
- Fonts: `$PY $S/assets.py font "Family" ...`
- Music, SFX, video: run `assets.py music|sfx|video "<query>"` to list, then `assets.py get <kind> <id> $WD`.
  - SFX by tone: calm → "air woosh", "chime"; balanced → "whoosh", "pop"; energetic → "swoosh", "impact" (used once).
- Blocked sources fall back automatically (pack ids). `assets.py pack` lists the whole offline CC0 pack.

## 5. Write spec.json, plan, styleframes
1. Write `$WD/spec.json` (see references/spec.md): captions in spoken order, cards on the right clauses, audio. Pick card **types** only from `look.json`'s `cards` list (that family's set), and rotate card `in`/`out` through `look.json`'s `transitions` list instead of defaulting to one transition for every card — that repetition is exactly what made every past video look the same.
2. `$PY $S/engine.py $WD --plan` → fix every ISSUE by editing the spec (shorten or merge beats, move or drop captions under cards), then re-plan until it reports none or only acceptable ones.
3. `$PY $S/engine.py $WD --frames t1,...` with 10–15 times: every card mid-point and end−0.3 s, and every caption at its end−0.1 s. Look at `$WD/styleframes.jpg` and fix anything cut off, crowded, mis-aligned or off-palette.
4. Show the user the styleframes with one line ("ok to render?"). Iterate only on what they flag.

## 6. Render, mix, QA
- `bash $S/render.sh $PY $WD` renders parts in parallel and concatenates them (≈5 min per minute of video on a laptop). In a sandbox with a time limit per command, run `$PY $S/engine.py $WD --render --part i/N` once per part, then `--concat N` — one part is well inside a single command's time limit; a combined render of the whole clip is not. If a part still times out, re-run with `THS_PRESET=veryfast $PY $S/engine.py $WD --render --part i/N` (faster x264 preset, same quality target via crf).
- `$PY $S/mix.py $WD` → `final.mp4` (voice clean-up, ducked music with payoff alignment, SFX, -14 LUFS).
- `$PY $S/qa.py $WD` → look at `qa_endframes.jpg`. Every beat and card end must show finished text and animation. Flash frames must be none.
- Deliver the file path, plus 3 lines on what you chose and why. Mention any assets you couldn't download.

## Non-negotiables (why: each one was called out as amateur)
- Captions never cut off. Lead is ≤ key width and sits close. Two contrasting font styles at a golden ratio. Never caption lone filler words.
- Motion graphics show the meaning, finish before the scene changes, and stay in one visual system *per video* — but that system must be chosen fresh each time by `look.py`, never hand-picked out of habit or reused from the last job. No stick figures or clip art.
- Smooth: an eased, eye-locked zoom across cuts; no flash frames; varied transitions (rotate through `look.json`'s `transitions`, don't default to one).
- Color correction only. Licensed assets only (Mixkit / Google Fonts OFL), with LICENSES.txt kept in $WD.

## Maintaining the genre sheet
The user's editing matrix lives as an Excel sheet; `references/genre_matrix.json` is a generated copy `look.py`/`style.py` actually read. Whenever the user hands you an updated `.xlsx` (new rows, new B-roll/palette/font notes), rebuild it — don't hand-edit the JSON:
`$PY $S/matrix.py path/to/the-sheet.xlsx` (needs `pip install openpyxl`; it's not in setup.sh because the sheet changes rarely). It also pulls in the MOTION STYLE GUIDE, COLOR PALETTE GUIDE and GOOGLE FONTS LIBRARY tabs, which `look.py` uses to score style families per niche.
