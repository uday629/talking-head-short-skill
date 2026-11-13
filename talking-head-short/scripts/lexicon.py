"""Meaning → visual suggestions, word-synced. Reads WORKDIR/words.json and prints, for every moment of the
transcript, WHAT the voice is talking about and WHICH graphic the reference reels used for that meaning.
python lexicon.py WORKDIR            → compact list:  t  "phrase"  → category → spec snippet idea

The mapping (references/visual_lexicon.md) was learned from 16 professional before/after reels: editors show
the MEANING of the exact words being said at that instant (money → money, growth → growth, a problem → a red
problem marker), mostly as overlays beside the face, and keep the face clean on personal/moral lines."""
import sys, os, re, json

def norm(w): return re.sub(r"[^a-z0-9$%']", "", w.lower())

# category: (keywords (whole words / stems), suggestion)
LEX = [
 ("money",     r"\$|money|dollars?|bucks|rupees?|taka|price|prices|pay|paid|paying|salary|income|revenue|profit|cost|costs|budget|cash|earn\w*|spend\w*|invest\w*|rich|wealth\w*|afford\w*|sales",
               'overlay "badge" (glass value card beside the head, value counts up) — or "rain" (+amount) for big/escalating sums'),
 ("growth",    r"grow\w*|growth|scale|scaling|increase\w*|boost\w*|rise|rising|double\w*|triple\w*|results?|progress|improv\w*|level|higher",
               'overlay "trend" dir:up (line draws upward behind the speaker; add "icons":["people"] if clients/owners are named)'),
 ("decline",   r"drop\w*|declin\w*|los(e|ing|t)|slow\w*|fall\w*|crash\w*|down|decreas\w*|shrink\w*",
               'overlay "trend" dir:down (red) — or caption "strike" on the failing word'),
 ("reach",     r"viral|views?|followers?|reach|audience|million|millions|seen|impressions",
               'overlay "tally" icon:eye (rolling number) — e.g. views counting up on "go viral"'),
 ("problem",   r"problems?|struggl\w*|stress\w*|pain\w*|painful|hurt\w*|mistakes?|fail\w*|wrong|weak\w*|sensitive|risk\w*|issues?|stuck|frustrat\w*|hard|difficult|unsure|worr\w*|anxi\w*|damage\w*|broke\w*|sick",
               'overlay "warn" (red warning pills, one per spoken problem) or "ring" tone:problem with a tag; caption "strike" on negation words'),
 ("solution",  r"solution|solve\w*|fix\w*|heal\w*|protect\w*|restor\w*|strength\w*|fight|support\w*|cure\w*|answer|better|safe",
               'overlay "ring" tone:solution (calm ring + tag) or a "statement" card whose words grow; switch accent from red to the brand color'),
 ("people",    r"people|clients?|customers?|community|team\w*|groups?|followers|audience|owners?|buyers?|sellers?|homeowners?|everyone|someone|creators?|family|friends",
               'overlay "pop" icon:people — or a "cycle"/"flow" card with person icons when it is the topic of the sentence'),
 ("best",      r"best|top|premium|number one|#1|leading|elite|king|greatest|ultimate",
               'overlay "pop" icon:crown on the word; key color = accent (the value word)'),
 ("feeling",   r"love\w*|like them|care\w*|heart|feel\w*|happy|enjoy\w*",
               'overlay "pop" icon:heart (only when it is said warmly; NOT on filler "like")'),
 ("idea",      r"idea\w*|learn\w*|realiz\w*|insight\w*|aware\w*|awareness|understand\w*|think about|lesson\w*|master\w*",
               'overlay "pop" icon:bulb — reflective lines: keep the face, small caption'),
 ("system",    r"system\w*|process\w*|tool\w*|automat\w*|workflow\w*|structure\w*|framework\w*|operations?|machine\w*",
               'overlay "pop" icon:gear — or a "flow" card when the steps are spoken'),
 ("time",      r"week\w*|month\w*|years?|days?|daily|monday|tuesday|wednesday|thursday|friday|saturday|sunday|schedule\w*|calendar|hours?|minutes?|2024|2025|2026|morning|night",
               'card "calendar" (a month that builds, highlighted day, year faint behind) — or "pop" icon:clock'),
 ("search",    r"search\w*|google\w*|look(ing)? for|ask\w*|chatgpt|gpt|ai|type",
               'card "search" (bar types the exact words being said; cursor click for UI looks)'),
 ("social",    r"social|instagram|tiktok|youtube|facebook|online|app|apps|phone|reels?",
               'overlay "pop" icon:phone — or a full "flow"/"list" card of platforms when listed'),
 ("camera",    r"camera|record\w*|film\w*|shoot\w*|video\w*",
               'overlay "viewfinder" — ONLY when the topic literally is filming/recording'),
 ("product",   r"product\w*|toothpaste|device\w*|gadget\w*|bottle|brand|ingredient\w*|formula|cream|serum|machine",
               'card "orbit" (rotating object with spec callouts, one callout per spoken feature) — or keep a real product shot'),
 ("contrast",  r"versus|vs|instead|rather than|not \w+ but|but",
               'card "compare" (two sides, levels driven by the words) when two states are named'),
 ("goal",      r"goal\w*|target\w*|focus\w*|aim\w*|niche|strategy|plan\w*",
               'overlay "pop" icon:target'),
]
NUM = re.compile(r"^\$?\d[\d,.]*(k|m)?$|^(hundred|hundreds|thousand|thousands|million|millions|billion)$")
FILLER = {"like", "so", "um", "uh", "you", "know"}

def suggest(words):
    toks = [norm(w["w"]) for w in words]; out = []
    text = " ".join(toks)
    for i, w in enumerate(words):
        n = toks[i]
        if not n: continue
        win = " ".join(toks[i:i + 3])
        for cat, pat, sug in LEX:
            if re.fullmatch(pat, n) or (" " in pat and re.match(r"(" + pat + r")\b", win)):
                if cat == "feeling" and n == "like": continue
                if cat == "time" and any(NUM.match(x) or x.startswith("$") for x in toks[max(0, i - 3):i]): continue   # "$500 a month" is a rate, not a date
                out.append((w["s"], cat, i, sug)); break
        if NUM.match(n) or (n.startswith("$")):
            out.append((w["s"], "number", i, 'money → overlay "badge" count:true; other stat → card "counter" or overlay "tally"'))
        if w["w"].strip().endswith("?"):
            out.append((w["s"], "question", i, 'caption the question on the face (big key word); answer gets the graphic'))
    # spoken lists: ≥2 commas or "and" joining short parallel chunks within 10 words
    i = 0
    while i < len(words):           # "A, B and C" / "A, B, C, D": short chunks (≤3 words) separated by commas, closed by and/or
        j, items, start = i, 0, i
        while j < len(words):
            k = j
            while k < len(words) and k - j < 3 and not words[k]["w"].endswith(","): k += 1
            if k < len(words) and words[k]["w"].endswith(",") and k - j < 3: items += 1; j = k + 1
            else: break
        tail = [toks[m] for m in range(j, min(len(words), j + 4))]
        if items >= 2 or (items >= 1 and ("and" in tail or "or" in tail) and j - start <= 6):
            if items >= 2 or "and" in tail:
                out.append((words[start]["s"], "list", start, 'spoken list → overlay "icons" (tiles on the chest, one per item, accumulating) if they speak to camera; "cycle"/"flow"/"list" card if it explains'))
            i = j + 1
        else: i += 1
    out.sort()
    # merge same category hits within 1.2 s
    merged = []
    for s, cat, i, sug in out:
        if any(m[1] == cat and s - m[0] < 2.5 for m in merged[-4:]): continue
        merged.append((s, cat, i, sug))
    return merged

def main():
    wd = sys.argv[1]; words = json.load(open(os.path.join(wd, "words.json")))
    for s, cat, i, sug in suggest(words):
        ph = " ".join(w["w"] for w in words[max(0, i - 2):i + 4])
        print(f"{s:6.2f}  {cat:9s} \"{ph}\"  → {sug}")
    print("RULES: graphic lands ON the word (use its phrase as \"at\"); problem=red, solution=brand accent; personal/moral/feeling lines stay on the face with a small caption; one category per beat; never stack two overlays at once.")

if __name__ == "__main__":
    main()
