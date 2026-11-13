# Visual lexicon: what the voice says → what the screen shows
Learned from 16 professional before/after reels (each studied frame-by-frame at 0.5 s with the word being spoken at that frame).
The single rule every editor followed: **the graphic shows the meaning of the exact words being said at that moment, and it lands on the word.**
`scripts/lexicon.py WORKDIR` scans the transcript and prints these suggestions with timestamps. Treat them as candidates; you choose.

## The lexicon
| the voice says… (meaning) | the reels showed | engine | where | evidence |
|---|---|---|---|---|
| a money amount ("$500", "$2,000 a month") | glass card with the amount + tiny bar chart, floating beside the head, number counts up | overlay `badge` (`count:true`) | beside the face (below the chin on tight shots) | agency hiring: $500 → card right of head, $2000 → second card left |
| big / escalating money ("hundreds of thousands of dollars") | bills falling through the frame + a rolling dollar figure on the chest | overlay `rain` (+`to`) | full frame over the face | marketer: "pay hundreds of thousands of dollars" |
| growth, scale, increase, results | a line that draws upward behind the speaker with an arrowhead (+ people icons when "clients/owners" are named) | overlay `trend` `dir:up` | behind/around the speaker | agency: "helps business owners **scale**" |
| decline, slowing, losing | the same line falling, red; or a red strike through the word | overlay `trend` `dir:down`; caption `strike` | — | consultant: "business **slows down**" |
| reach, views, going viral, followers | eye icon + a view counter rolling up | overlay `tally` `icon:eye` | chest | marketer: "potential to **go viral**" → eye + 3,855 → 7,469 |
| a problem / harm / pain ("weaken", "sensitive", "stresses you out", "unsure") | red: warning pills that stack per problem, a red ring around the head with a tag, red glow on the affected thing | overlay `warn` / `ring tone:problem` | chest / around the head | dentist: "more sensitive", "prone to cavities" pills; content agency: ring + "stress" tag, "what to say?" / "how it turns to revenue?" pills |
| failure / negation of a word ("your content is **failing**", "not intuitive") | red strike drawn across that word | caption `"strike": true` | on the caption | content agency: strike on "Content" |
| the solution / protection ("helps our teeth **fight back**", "restores, strengthens") | the colour flips from red to the brand colour: a calm protective ring; a clean card whose words grow bigger | overlay `ring tone:solution`; card `statement` | around the head / full card | dentist: blue ring around the tooth, "RESTORES / STRENGTHENS / ENAMEL" growing |
| a spoken list of things/qualities/services ("task, experience, skills", "plan, shoot, script, edit, post") | icon tiles appear one per word on the chest and stay (accumulate) | overlay `icons` (items with `at`) | chest, face stays | agency, content agency, CEO hiring |
| a list that *is* the explanation (backstory, ingredients, 3 rules) | one card system, items land one by one | card `list` / `cycle` / `flow` / `steps` | full card | sales coach backstory, AI-founder tools list |
| nouns named in a row ("acid, sugar, coffee") | one object icon pops per noun around the face | overlay `pop` (one item per noun, icon per item) | around the head | dentist |
| best / top / premium / #1 | crown on "best"; the value word gets the accent colour | overlay `pop icon:crown`; caption `kc:"accent"` | beside the word | agency: "best of the **best**" |
| love / care / feelings said warmly | hearts | overlay `pop icon:heart` | around the head | dentist: "we **love** them" |
| an idea / lesson / insight / awareness | light bulb pill | overlay `pop icon:bulb` | beside the head | sales coach: "if you master the fundamental" |
| system / process / tool | gears | overlay `pop icon:gear` or card `flow` | beside / card | consultant "that's not a **system**"; marketer "business **tool**" |
| people / clients / community / team | people icons, an orbit of avatars around a person | overlay `pop icon:people`; card `cycle` with person items | around / card | wedding photographer orbit; community explainer |
| time: weeks, months, a year, days | a calendar that builds, the year big and faint behind | card `calendar` (or `pop icon:clock`) | full card | AI founder: "every new **week** in **2025**" |
| searching / asking Google or AI / "looking for" | a search bar that types the exact sentence | card `search` | full card | agency "looking for full-time editors", wellness "how to heal your body" |
| social media / apps / phone | hand + phone + app icons | overlay `pop icon:phone` or a card of platforms | — | marketer "social media" |
| a product being explained | the real product in hand + floating callouts per feature | keep the product shot; card `orbit` for callouts | — | dentist toothpaste |
| filming / recording (only when the topic IS cameras) | REC viewfinder corners | overlay `viewfinder` | frame | content agency "even if you **record**" |
| one word to emphasize ("from **scratch**") | a hand-drawn loop around that word | caption `"circle": true` | on the caption | AI founder |
| two states contrasted ("not X, it's Y", "hoping vs knowing") | two-sided compare | card `compare` | full card | — |
| a number that is not money ("300 lives", "10 years") | big counter | card `counter` / overlay `tally` | — | brand story, community explainer |
| personal reaction, moral, feeling, wisdom ("I paused", "no human ever did it alone") | NOTHING: face only, small plain caption | — | face | brand story, thought leader: restraint = sincerity |
| a story / metaphor (journey, loneliness, a scene acted out) | B-roll that acts it out, or a cinematic metaphor | `broll` (licensed / user clips) | full frame | menopause comedy, community (cinematic version) |

## Placement and timing rules (from the reels)
1. **On the word.** Every item's `at` is the phrase that carries the meaning. A graphic that appears a second early or late reads as random.
2. **Overlay first, card second.** When the speaker talks *to the viewer*, the graphic sits beside/on them (face stays). Full-screen cards are for explanation, backstory, or a list that *is* the content.
3. **One meaning at a time.** Never two overlays at once; `--plan` flags overlaps. Let the previous graphic finish before the next.
4. **Colour carries meaning.** Problem = red (`tone:"problem"`), solution and value = the look's accent. Use the switch red→accent at the problem→solution turn.
5. **Lists accumulate.** Items of one spoken list stay on screen and add up; they are one graphic, not N separate ones.
6. **Restraint on sincere lines.** Personal, moral, emotional lines get no graphic at all.
7. **Literal only for literal topics.** Viewfinder/REC only when the topic is filming; money rain only for money; hearts only when "love" is said warmly (not the filler "like").
