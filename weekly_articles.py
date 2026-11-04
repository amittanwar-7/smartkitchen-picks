"""Weekly job: take the next unpublished topics from content_plan.py, write them with Groq,
check quality, and append them to generated.json. Runs in GitHub Actions with the GROQ_API_KEY secret."""
import datetime, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

from clusters import CLUSTERS
from content import GUIDES
from content_plan import PLAN

ROOT = Path(__file__).parent
GEN = ROOT / "generated.json"
COUNT = int(os.environ.get("ARTICLE_COUNT", "3"))
MODELS = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "llama-3.1-8b-instant"]
KEY = os.environ.get("GROQ_API_KEY", "")


def http(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", "ignore")



def pick_models():
    hdr = {"Authorization": "Bearer " + KEY, "User-Agent": "smartkitchen-bot/1.0"}
    try:
        ids = [m["id"] for m in json.loads(http("https://api.groq.com/openai/v1/models", None, hdr))["data"]]
    except Exception as ex:
        print("::warning::could not list models:", str(ex)[:150], flush=True)
        return MODELS
    ids = [i for i in ids if not re.search(r"whisper|guard|tts|orpheus|embed|safeguard|compound", i, re.I)]
    print("available models:", ids, flush=True)
    pref = [i for k in ("gpt-oss-120b", "70b", "120b", "llama", "qwen", "gpt-oss") for i in ids if k in i.lower()]
    return list(dict.fromkeys(pref + ids)) or MODELS


def chat(messages, max_tokens=6000):
    global MODELS
    if not getattr(chat, "ready", False):
        MODELS, chat.ready = pick_models(), True
    hdr = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json", "User-Agent": "smartkitchen-bot/1.0"}
    for i in range(6):
        body = json.dumps({"model": MODELS[i % len(MODELS)], "messages": messages,
                           "temperature": 0.7, "max_tokens": max_tokens}).encode()
        raw = ""
        try:
            raw = http("https://api.groq.com/openai/v1/chat/completions", body, hdr)
            return json.loads(raw)["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as ex:
            print("::error::model call failed:", ex.code, ex.read().decode("utf-8", "ignore")[:300].replace("\n", " "), flush=True)
        except Exception as ex:
            print("::error::model call failed:", str(ex)[:200], "| body:", raw[:200].replace("\n", " "), flush=True)
        time.sleep(20 * (i + 1))
    return ""


def load_gen():
    return json.loads(GEN.read_text(encoding="utf-8")) if GEN.exists() else []


def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:60].strip("-")


def next_topics(n, published):
    return [p for p in PLAN if slugify(p[1]) not in published][:n]


# Writing rules follow Google's "helpful, reliable, people-first content" guidance and its
# spam policies (scaled content abuse, thin affiliate pages): every page must answer the
# reader's question better than a product list, with no invented facts or fake experience.
PROMPT = """You are an experienced Indian sports-equipment coach writing for "Bat & Racket", a site that helps
Indian beginners, parents and club players choose cricket and badminton gear.

Write ONE article.
Title: {title}
Primary search phrase: "{keyword}"
Article type: {kind} ({kind_help})
Product types we will show (in this order): {products}
Related pages already on the site (do NOT repeat their content; the article will link to them): {related}

Quality rules (very important):
- Write for a real person in India with this exact question. Answer it directly in the first paragraph.
- 900-1300 words of genuinely useful, specific guidance: decision criteria, who should choose what, sizes/weights/
  levels where widely accepted, step-by-step instructions for how-tos, common mistakes, safety and care.
- Use the primary search phrase naturally in the first paragraph and in one heading. Never keyword-stuff.
- Plain, friendly Indian English. Short paragraphs. No fluff, no filler intros, no "In conclusion".
- Do NOT claim personal testing or experiences ("we tested", "I used"). Do NOT invent prices, specs, ratings,
  statistics, studies or quotes. Do NOT name brands or specific product models. Budget amounts in the title are fine.
- Add one comparison table where it genuinely helps (e.g. by level, age, size, material).
- Stay strictly on this topic; do not drift into the related pages' topics.

Return ONLY valid JSON with keys:
desc: meta description, 140-155 chars, includes the primary phrase
intro: list of 2 short paragraphs
sections: list of 4-6 objects, each {{"h": heading, "p": [paragraphs]}} and optionally "ul": [bullets]
   and/or "table": [[header cells], [row cells], ...] (max one table in the whole article)
picks: list with exactly {n} objects in the same order as the product types, each
   {{"who": one sentence on who this option suits, "check": [3 short things to check before buying]}}
faq: list of 4 [question, answer] pairs that real buyers ask (answers 2-4 sentences)"""

KIND_HELP = {"buying": "help the reader choose the right product", "howto": "practical step-by-step guide",
             "explain": "explain and compare clearly, then recommend who should pick what"}
BANNED = re.compile(r"\bwe (have )?tested\b|\bi (have )?(tested|used)\b|our test|hands-on|as an ai|in conclusion|"
                    r"\bstudies show\b|\baccording to (a )?(recent )?(study|survey)", re.I)


def words(a):
    txt = " ".join(a["intro"])
    for s in a["sections"]:
        txt += " " + " ".join(s.get("p", []) + s.get("ul", []))
        txt += " " + " ".join(" ".join(map(str, r)) for r in s.get("table", []))
    txt += " " + " ".join(q + " " + x for q, x in a["faq"])
    return txt


def valid(a, n):
    try:
        txt = words(a)
        ok = (a["desc"] and 4 <= len(a["sections"]) <= 7 and len(a["faq"]) >= 3 and all(len(f) == 2 for f in a["faq"])
              and len(a["picks"]) == n and all(p.get("who") and len(p.get("check", [])) >= 2 for p in a["picks"])
              and len(txt.split()) >= 750)
        if not ok:
            print("  failed structure/length check; words =", len(txt.split()))
            return False
        if BANNED.search(txt + json.dumps(a["picks"])):
            print("  failed: banned phrase:", BANNED.search(txt + json.dumps(a["picks"])).group(0))
            return False
        return True
    except Exception as ex:
        print("  failed validation:", ex)
        return False


def clean_table(t):
    rows = [[str(c) for c in r] for r in t if isinstance(r, list) and r]
    return rows if len(rows) >= 2 else None


def write(topic, related):
    title, keyword, pillar, kind, products = topic
    msg = PROMPT.format(title=title, keyword=keyword, kind=kind, kind_help=KIND_HELP[kind], n=len(products),
                        products="; ".join(lbl for lbl, _ in products), related="; ".join(related))
    for attempt in range(2):
        out = chat([{"role": "user", "content": msg}], 7000)
        m = re.search(r"\{.*\}", out, re.S)
        try:
            a = json.loads(m.group(0))
        except Exception:
            print("  bad JSON (attempt", attempt + 1, ")"); continue
        if valid(a, len(products)):
            secs = []
            for s in a["sections"]:
                sec = {"h": str(s["h"]), "p": [str(x) for x in s.get("p", [])]}
                if s.get("ul"):
                    sec["ul"] = [str(x) for x in s["ul"]]
                if s.get("table") and clean_table(s["table"]):
                    sec["table"] = clean_table(s["table"])
                secs.append(sec)
            return {
                "slug": slugify(keyword), "title": title, "desc": str(a["desc"])[:160], "keyword": keyword,
                "pillar": pillar, "date": datetime.date.today().isoformat(),
                "intro": [str(x) for x in a["intro"]][:3], "sections": secs,
                "picks": [{"name": lbl, "query": q, "who": str(p["who"]), "check": [str(x) for x in p["check"]][:4]}
                          for (lbl, q), p in zip(products, a["picks"])],
                "faq": [[str(q), str(x)] for q, x in a["faq"]][:5],
                "cta": [f"See {products[0][0].lower()} on Flipkart", products[0][1]],
            }
    return None


def main():
    gen = load_gen()
    published = {c["slug"] for c in CLUSTERS + gen} | {g["slug"] for g in GUIDES}
    guide_titles = {g["slug"]: g["title"] for g in GUIDES}
    todo = next_topics(COUNT + 2, published)  # a couple of spares in case one fails the quality check
    if not todo:
        print("::warning::content_plan.py is finished - add new topics to keep publishing"); return
    added = 0
    for t in todo:
        if added >= COUNT:
            break
        print("writing:", t[0], flush=True)
        related = [guide_titles[t[2]]] + [c["title"] for c in CLUSTERS + gen if c["pillar"] == t[2]][-8:]
        a = write(t, related)
        if not a:
            print("  skipped (will retry next week)"); continue
        gen.append(a); published.add(a["slug"]); added += 1
        print("  added:", a["slug"], flush=True)
        time.sleep(45)  # stay under Groq's free tokens-per-minute limit
    left = len(next_topics(10**6, published))
    print(f"articles added: {added}; plan topics remaining: {left}", flush=True)
    if added:
        GEN.write_text(json.dumps(gen, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
