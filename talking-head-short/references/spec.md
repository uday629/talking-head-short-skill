# spec.json — the only thing you write per video
Keep it short. Times come from the transcript automatically: you write **words**, not timestamps.

**`look.json` (from `scripts/look.py`) overrides `palette` and `fonts` automatically** — if `$WD/look.json` exists, the engine replaces whatever `palette`/`fonts` you write below with the chosen look's own values. So once you've run `look.py --pick`, don't hand-write `palette`/`fonts` in spec.json at all; only pick card **types** from that look's `cards` list and rotate card `in`/`out` through its `transitions` list. `palette`/`fonts` below only matter if you're running without look.json (legacy `style.py` path).

```json
{
 "raw": "raw.mp4", "out": "final.mp4",
 "tone": "calm | balanced | energetic",          // default caption animation: blur | rise | pop
 "caption_y": 0.62,                               // lockup center (0.58–0.64). Keep 0.12–0.80 safe zone
 "palette": {"primary","secondary","3rd","4th","card_bg"},   // copy from style.py output
 "fonts": {"lead": ["DM Sans", 500], "key": ["Lora", 600], "acc": ["Lora", 400], "acc_italic": true, "key_italic": false},
 "grade": {"sat": 1.0, "contrast": 0.12, "wb": 0.6},          // correction only; sat 0.95–1.05
 "camera": {"zooms": [1.0, 1.08], "push": 0.03, "ease": 8, "eye": [x, y], "eye_y": 0.33},
 "segments": null,                                // optional override; default = segments.json from analyze
 "captions": [ CAPTION, ... ],                    // in spoken order
 "cards":    [ CARD, ... ],                       // full-screen motion graphics (in spoken order)
 "overlays": [ OVERLAY, ... ],                    // meaning-graphics ON the face plate (see OVERLAY below)
 "broll":    [ {"file": "video_123.mp4", "at": ["phrase start", "phrase end"], "offset": 0, "speed": 1.0, "in": "dissolve"} ],
 "audio": {"music": "music_22.mp3", "music_offset": "auto", "music_db": -18, "payoff": "phrase", "voice": "clean|podcast",
           "sfx": {"in": "sfx_a.mp3", "out": "sfx_b.mp3", "item": "sfx_c.mp3", "payoff": "sfx_d.mp3"},
           "sfx_extra": [{"file": "...", "at": "phrase", "db": -26}]}
}
```

## CAPTION
`{"lead": "the way you", "key": "show up", "acc": "when you know", "layout": "L|R|C|O|I", "anim": "rise|blur|pop|write|type", "kc": "text|accent|secondary|dim", "ac": "accent|text", "acc_spoken": true, "over": false, "t": [src_s, src_e]}`
- Only `key` is required. The words must be spoken (they are matched to the transcript in order). `acc_spoken:false` means the accent is your own word.
- lead = 1–3 words before the key; key = 1–2 meaning words; acc = short tail (optional).
- Leave `layout` empty for automatic rhythm (L, R, C, O; I for 1-word leads), or set it to compose deliberately.
- `kc:"accent"` only on value/payoff words (≈1 in 4 captions).

## CARD (full screen; captions are hidden while a card shows)
`{"type": T, "at": ["first words", "last words"], "hold": 0.45, "in": "zoom|dissolve|light|blur", "out": "dissolve|zoom", "data": {...}}`
Items may carry `"at": "phrase"` to land exactly on the spoken word. Without it, items spread evenly and all land ≥0.6 s before the card ends.

| type | data | use when the voice… |
|---|---|---|
| statement | lead, key, acc, kc | lands a thesis/payoff ("that knowing vs hoping") |
| compare | left{lead,title,level 0–1,level_label,items[],at}, right{…,tone}, footer, footer_at | contrasts two states/options |
| list | title, items[{text,at}] | lists parallel things (also as an overlay) |
| checklist | title, items | lists requirements / do-this |
| steps | title, items | gives a process / framework |
| counter | lead, to, from, prefix, suffix, decimals, label, at | says a number / price / stat |
| bars | title, items[{label,value,hi}], unit, prefix | compares amounts |
| scale | title, left, right, value 0–1, at, acc | names a spectrum / where you sit |
| cycle | center, items | describes a loop / habit / cycle |
| timeline | title, items[{label,sub}] | tells a sequence over time |
| quote | text, by | quotes someone / a key line |
| search | title, query | "people google…", asks a question |
| flow | title, items[{text,at,icon?}] (2–4) | describes a pipeline/funnel/flow ("income→expense", stages) — connected icon nodes with a traveling pulse |
| orbit | title, items[{text,at}] (2–4) | a product/gadget/space being shown off — a rotating 3D wireframe with spec callouts landing on it |
| calendar | year, month, highlight[days], start_dow 0–6, days, title | talks about weeks/months/a year/a date |

`list`/`cycle` items pick an icon automatically from the item text (money/time/people/growth/… → a matching line icon); pass `"icon": "dollar"` etc. yourself only to override. Icon names: dollar, clock, check, chart, bulb, heart, bell, flag, person, leaf, shield, mail, star.

B-roll: a licensed clip (assets.py video) whose literal content matches the line. It is graded to match, pushes slowly, and keeps captions on top.

## Engine guarantees (don't re-implement)
- Golden-ratio lockup by x-height. The lead is never wider than the key, sits tight above it, and the accent tucks under it.
- A caption stays until its animation finishes plus 0.3 s; the plan reports anything that needs more time.
- Cards snap off raw cut points; back-to-back cards chain. A card ends where the next beat starts.
- Eye-locked camera with an eased zoom across cuts; the zoom never drops below the frame-fill minimum.
- Text auto-fits the frame width; the scrim adapts to background brightness.

## OVERLAY (drawn on the speaker's shot; captions stay; one at a time — `--plan` flags overlaps)
`{"type": T, "at": ["first words", "last words"], "hold": 0.3, "data": {...}}` — every item carries `"at": "phrase"` so it lands on its word.
| type | data | when the voice says… (see references/visual_lexicon.md) |
|---|---|---|
| badge | items[{value, label, count, chart, side l/r, tone, at}] | a money amount / price / stat — glass card beside the head, value counts up if `count` |
| rain | to, from, prefix, suffix, n | big or escalating money — bills fall, amount rolls on the chest |
| trend | dir up/down, icons[...], dur | growth / scale / results (up) or decline (down, red) — line draws behind the speaker |
| tally | icon, to, from, prefix, suffix, label, at | views / followers / reach — icon + rolling number on the chest |
| icons | items[{text, icon, tone, at}], y | a spoken list addressed to camera — tiles accumulate on the chest |
| warn | items[{text, at}], y | problems / pain points — red warning pills stack |
| ring | tone problem/solution, tag, r | stress / pressure on the person (red) or protection / support (accent) — ring draws around the head |
| pop | items[{icon, text, tone, at}] | a meaning word: best→crown, love→heart, idea→bulb, system→gear, people→people, social→phone, goal→target |
| viewfinder | — | only when the topic literally is filming/recording |

Caption marks: `"strike": true` (red line through the key after it lands — failing/negation), `"circle": true` (hand-drawn loop around the key — one emphasis word).
Icon names: dollar, coin, clock, calendar, check, chart, arrow_up, bulb, heart, bell, flag, person, people, leaf, shield, mail, star, crown, gear, eye, warn, phone, target.
