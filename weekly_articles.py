"""Weekly job: pick new topics from Google autosuggest, write articles with GitHub Models,
append them to generated.json. Runs in GitHub Actions with GITHUB_TOKEN (models: read)."""
import json, os, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

from clusters import CLUSTERS
from content import GUIDES

ROOT = Path(__file__).parent
GEN = ROOT / "generated.json"
COUNT = int(os.environ.get("ARTICLE_COUNT", "3"))
MODEL = os.environ.get("MODEL", "openai/gpt-4.1")
TOKEN = os.environ["GITHUB_TOKEN"]
SEEDS = ["best lunch box for", "how to clean", "steel bottle", "air fryer", "kitchen storage",
         "vegetable chopper", "kitchen gadgets under", "pressure cooker", "tawa", "masala box",
         "water bottle for", "kitchen organiser", "mixer grinder", "idli", "chapati"]


def http(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", "ignore")


def suggest(q):
    try:
        u = "https://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=in&q=" + urllib.parse.quote(q)
        return json.loads(http(u))[1]
    except Exception:
        return []


def chat(messages, max_tokens=4000):
    body = json.dumps({"model": MODEL, "messages": messages, "temperature": 0.7, "max_tokens": max_tokens}).encode()
    hdr = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json",
           "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    for i in range(3):
        try:
            return json.loads(http("https://models.github.ai/inference/chat/completions", body, hdr))["choices"][0]["message"]["content"]
        except Exception as ex:
            print("model call failed:", ex, file=sys.stderr)
            time.sleep(10 * (i + 1))
    return ""


def load_gen():
    return json.loads(GEN.read_text(encoding="utf-8")) if GEN.exists() else []


def existing_text():
    return " ".join(c["title"].lower() + " " + c["slug"] for c in CLUSTERS + load_gen())


def pick_topics(n):
    cands = []
    for s in SEEDS:
        cands += suggest(s)
        time.sleep(0.3)
    have = existing_text()
    cands = [c for c in dict.fromkeys(cands) if len(c.split()) >= 3 and c.lower() not in have]
    pillars = ", ".join(g["slug"] for g in GUIDES)
    out = chat([{"role": "user", "content":
        f"From these Google India autosuggest queries about kitchen products, choose {n} specific, helpful, "
        f"non-overlapping topics for buying-guide or how-to articles for Indian home cooks. Skip anything unsafe, "
        f"branded, or already covered by these existing titles: {existing_text()[:1500]}\n\nQueries:\n" + "\n".join(cands[:150]) +
        f"\n\nReturn ONLY a JSON array of {n} objects: {{\"topic\": str, \"pillar\": one of [{pillars}]}}."}], 800)
    m = re.search(r"\[.*\]", out, re.S)
    return json.loads(m.group(0))[:n] if m else []


PROMPT = """Write a helpful, original article for an Indian affiliate site about budget kitchen products.
Topic: {topic}
Rules: 700-1000 words, plain simple English, India-relevant. Cover how to choose or do it, what to check, mistakes, safety/care.
Do NOT invent prices, product specs, ratings, brand claims, or claim personal testing. No product names.
Return ONLY JSON with keys:
slug (lowercase-hyphens, ends with -india or similar, max 60 chars), title (max 70 chars), desc (max 155 chars),
intro (list of 2 paragraphs), sections (list of 3-4 objects {{"h": str, "p": [paragraphs]}} and/or {{"h": str, "ul": [bullets]}}),
faq (list of 3-4 [question, answer] pairs), cta ([button label, short Flipkart search query])."""


def valid(a):
    try:
        return (re.fullmatch(r"[a-z0-9-]{5,70}", a["slug"]) and a["title"] and a["desc"] and len(a["intro"]) >= 1
                and len(a["sections"]) >= 3 and len(a["faq"]) >= 3 and len(a["cta"]) == 2
                and all(len(f) == 2 for f in a["faq"])
                and sum(len(" ".join(s.get("p", []) + s.get("ul", [])).split()) for s in a["sections"]) >= 450)
    except Exception:
        return False


def main():
    gen = load_gen()
    slugs = {c["slug"] for c in CLUSTERS + gen} | {g["slug"] for g in GUIDES}
    added = 0
    for t in pick_topics(COUNT):
        out = chat([{"role": "user", "content": PROMPT.format(topic=t["topic"])}])
        m = re.search(r"\{.*\}", out, re.S)
        try:
            a = json.loads(m.group(0))
        except Exception:
            print("bad JSON for", t["topic"]); continue
        if not valid(a) or a["slug"] in slugs:
            print("rejected:", t["topic"]); continue
        a["pillar"] = t["pillar"] if t["pillar"] in {g["slug"] for g in GUIDES} else GUIDES[0]["slug"]
        a["cta"] = [str(a["cta"][0]), str(a["cta"][1])]
        gen.append(a); slugs.add(a["slug"]); added += 1
        print("added:", a["title"])
    GEN.write_text(json.dumps(gen, indent=1, ensure_ascii=False), encoding="utf-8")
    print("articles added:", added)


if __name__ == "__main__":
    main()
