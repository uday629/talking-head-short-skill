# Craft rules (distilled from 16 pro reference reels, a word-by-word study, research, and a client's frame-by-frame corrections)
Read once per job. Each rule exists because breaking it was visibly called out as amateur.

## 1. Read the script before choosing anything
- Label each clause: HOOK · IDENTITY · STORY/DESCRIPTION · LIST · PROBLEM · TURN · ANSWER · REACTION/JUDGMENT · MORAL · CTA.
- Decide the feeling: explain (informational) or make them feel (emotional/reflective). Same footage gets opposite treatments depending on this.
- Style comes from topic + emotion, not from what looks cool. A HUD on a self-help talk, or neon on a calm speaker, is wrong.

## 2. Face vs cut-away
| clause | treatment |
|---|---|
| hook / thesis / identity | face + strong caption |
| reaction, judgment, feeling, moral, "you…" to camera | face, less decoration (sincerity = restraint) |
| description, facts, backstory, numbers, abstract argument | card or B-roll |
| N parallel clauses ("I'm aware of my habits / thoughts / people") | N beats in ONE visual system (list/steps/cycle), each landing on its words |
| list of single words | one overlay; items accumulate on the spoken word |
| payoff line | designed graphic (statement/compare), not a crowded caption |
- Cut-away share: opinion/reflective 25–45%; description-heavy 45–65%.
- Change scene only at clause boundaries. Never start a new scene before the current word or animation has finished. If you can't show it fully, don't show it.

## 3. Motion graphics translate meaning
- Write line → meaning → emotion → visual. Prefer typographic or diagrammatic metaphors (compare levels, scale, cycle, counter). Never use stick figures or clip art.
- One visual system per video: same card background, line weight and accent color.
- Linked elements (a dot on a line, a number on a ring) are driven by the same progress value.
- Less is more for calm speakers: 3–5 cards per minute. Energetic sales: more, faster.

## 4. Typography
- Two clearly different families: a sans for the lead, a serif or display face for the key, and an italic or script accent. Weights that differ but look alike (bold sans + semibold serif) read as one heavy blob.
- Golden ratio by x-height: lead = key ÷ 1.618, accent ≈ key ÷ 1.618. Tight proximity: the lead sits just above the key's cap line.
- The lead is 1–3 words and never wider than the key. Never caption a lone filler (is, a, I, the). Skip words: "relaxed / & calm" beats a full subtitle.
- Layouts rotate for rhythm (left, right, center, offset, inline). Animations vary too (rise, blur, write-on, type, pop for energetic only).
- A caption must never be cut off: the animation completes, plus ≥0.3 s of read time. Engine `--plan` flags violations; fix them by shortening or merging beats.
- Fonts come from the genre row (references/genre_matrix.json), downloaded with `assets.py font`. Feminine/lifestyle → script accent OK; male, reflective or business → italic serif accent.

## 5. Color
- Correction, not a look: neutral white balance from true neutrals, black ≈0.02–0.03, whites ≤0.9, skin on the vectorscope skin line (~123°), saturation 0.95–1.05. Never darken below the raw, never burn the highlights. The engine does this; only tweak `grade` if needed.
- The palette comes from the genre row, adapted to the footage by `style.py` (text contrast ≥4.5:1, accent ≥3:1, accent hue away from the dominant background hue, card bg tinted toward the footage). Roles: primary ~50–60% · secondary ~20–30% · neutral ~10–20% · accent ~5–10%.

## 6. Camera and cuts
- Wide raw: zooms like [1.0, 1.10–1.15] alternate per take, plus push 0.03–0.04. Tight raw: [1.0, 1.05], push ≤0.02. Eye level stays locked; the zoom eases across the cut (no jump).
- No flash frames, no half-finished scenes, no repeated mechanical slide transitions. Mix zoom-through, light-leak, blur and dissolve, matched to the tone (calm → dissolve/blur/light; energetic → zoom).

## 7. Clean cut
- Remove fillers, stutters, restarts, false starts, dead air >0.3 s. Keep natural breaths.
- Rhetorical repetition ("are you in hoping or are you in knowing", "is different. … is different.") is content. Keep it.
- After cutting, the re-transcribed text must read cleanly.

## 8. Sound
- Music is licensed (Mixkit), with mood from the genre row and the emotion arc. Reflective: 55–80 BPM piano/ambient. Energetic: 100–130 BPM. It sits 16–20 dB under the voice and ducks under speech. `music_offset:"auto"` lands a musical phrase on the payoff.
- SFX are real recordings, used sparingly: soft whoosh on card in (-26), pops on list items (-31), one chime on the payoff (-27). If you consciously notice an SFX, it's too loud. Calm videos use air and chimes, never impacts.
- Final mix: -14 LUFS, -1.2 dBTP.

## 9. Genre row = default, footage = judge
Use the row's B-roll, MG style, palette, fonts, music, SFX, delivery and notes. Deviate only when the footage demands it, and say why in one line. The notes column is a hard constraint (no guaranteed returns, label illustrative numbers, no shaming…).
