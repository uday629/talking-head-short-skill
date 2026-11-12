---
name: talking-head-short
description: Master editor for vertical talking-head short videos (Reels, TikTok, Shorts). From one raw clip it transcribes, removes bad takes and silences, detects the niche (24-genre matrix), asks the user to choose style options, then renders a smooth, professional edit with golden-ratio kinetic captions, meaning-driven motion graphics, licensed B-roll, music, SFX and fonts, color correction, and QA. Use it whenever the user gives a raw talking-head, podcast-clip, coach, founder, UGC or explainer video and wants it edited or "made viral", types /talking-head-short, or asks for captions, motion graphics, B-roll or a reel edit, even if they don't name the skill.
---

# Talking-Head Short — master editor

Write terse replies. Don't echo transcripts or long logs. Fix things by editing `spec.json` with the Edit tool, never by rewriting it. Every script prints a compact report; read it, act, move on.

`S=<this skill dir>/scripts`, `WD=<work dir next to the raw file>/ths_<name>`.

## 0. Setup (once per machine)
`bash $S/setup.sh` → use the printed `PY=`. Needs ffmpeg.
- If whisper can't install or download, ask the user to paste a transcript (or upload an .srt), then run `$PY $S/align_text.py $WD transcript.txt`.
- Assets go to `~/.ths_assets` (override with `THS_ASSETS`).

## 1. Analyze
`$PY $S/analyze.py RAW $WD`
It prints the resolution, eye point, the clean length, auto-removed fillers/stutters/restarts, CHECK (soft fillers, low-confidence words, long pauses), and TEXT with timestamps every 8 words.
- **Judge bad takes yourself.** Remove false starts, unfinished sentences, "you know like yeah", "kind of". Keep rhetorical repetition. Re-run with `--remove '[[s,e],...]'` (source seconds). Transcription is cached.
- Look at `$WD/frames.jpg` only if the eye point or framing is in doubt.

## 2. Brief (in your head, then 4 lines to the user)
Write: topic · core message · emotion arc (hook → … → payoff) · niche row (from NICHES) · tone (calm/balanced/energetic) · raw framing (wide or tight).
Then run `$PY $S/style.py RAW "<niche>" --out $WD/style.json`. It gives the adapted palette with reasons, fonts, MG/B-roll/music/SFX direction and hard notes.
Read `references/craft.md` once (the rules) and `references/spec.md` (the spec format).

## 3. Ask before building (never render first)
Use AskUserQuestion if available; otherwise one compact numbered message. Recommend option 1 each time.
1. **Style:** detected niche + tone (e.g. "Self-help · calm-reflective") vs 1–2 alternatives.
2. **Fonts:** the row's pair vs 2 alternatives with a clear style contrast (sans lead + serif/italic key, or bold sans key + italic serif accent).
3. **Palette:** footage-adapted row palette vs footage-derived vs a brand color the user gives.
4. **Visual density:** Minimal (captions + 2–3 cards) · Balanced (captions + 4–6 cards / B-roll) · Rich (more MG + B-roll).
5. **Music:** 3 licensed candidates from `$PY $S/assets.py music "<mood>"` (id · title · tags), or none.
6. **B-roll:** yes (licensed stock matching literal lines) / no.
Skip any question the user already answered. Wait for the answers.

## 4. Gather assets
- Fonts: `$PY $S/assets.py font "Family" ...`
- Music, SFX, video: run `assets.py music|sfx|video "<query>"` to list, then `assets.py get <kind> <id> $WD`.
  - SFX by tone: calm → "air woosh", "chime"; balanced → "whoosh", "pop"; energetic → "swoosh", "impact" (used once).
- If the output says NETWORK_BLOCKED, give the user the URL to download and upload the file, or continue without it.

## 5. Write spec.json, plan, styleframes
1. Write `$WD/spec.json` (see references/spec.md): captions in spoken order, cards on the right clauses, audio.
2. `$PY $S/engine.py $WD --plan` → fix every ISSUE by editing the spec (shorten or merge beats, move or drop captions under cards), then re-plan until it reports none or only acceptable ones.
3. `$PY $S/engine.py $WD --frames t1,...` with 10–15 times: every card mid-point and end−0.3 s, and every caption at its end−0.1 s. Look at `$WD/styleframes.jpg` and fix anything cut off, crowded, mis-aligned or off-palette.
4. Show the user the styleframes with one line ("ok to render?"). Iterate only on what they flag.

## 6. Render, mix, QA
- `bash $S/render.sh $PY $WD` renders parts in parallel and concatenates them (≈5 min per minute of video on a laptop). In a sandbox with a time limit per command, run `$PY $S/engine.py $WD --render --part i/N` once per part, then `--concat N`.
- `$PY $S/mix.py $WD` → `final.mp4` (voice clean-up, ducked music with payoff alignment, SFX, -14 LUFS).
- `$PY $S/qa.py $WD` → look at `qa_endframes.jpg`. Every beat and card end must show finished text and animation. Flash frames must be none.
- Deliver the file path, plus 3 lines on what you chose and why. Mention any assets you couldn't download.

## Non-negotiables (why: each one was called out as amateur)
- Captions never cut off. Lead is ≤ key width and sits close. Two contrasting font styles at a golden ratio. Never caption lone filler words.
- Motion graphics show the meaning, finish before the scene changes, and stay in one visual system. No stick figures or clip art.
- Smooth: an eased, eye-locked zoom across cuts; no flash frames; varied transitions.
- Color correction only. Licensed assets only (Mixkit / Google Fonts OFL), with LICENSES.txt kept in $WD.
