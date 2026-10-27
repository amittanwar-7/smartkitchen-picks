"""Fetch live product data (title, image, price) from the Flipkart Affiliate Search API into products.json.

Runs in GitHub Actions with FK_AFFILIATE_ID / FK_AFFILIATE_TOKEN from repository secrets.
Never fails the build: if credentials are missing or the API errors, the previous products.json is kept.
"""
import datetime, json, os, time, urllib.parse, urllib.request
from pathlib import Path

from content import GUIDES
from clusters import CLUSTERS

ROOT = Path(__file__).parent
OUT = ROOT / "products.json"
API = "https://affiliate-api.flipkart.net/affiliate/1.0/search.json"
PER_QUERY = 3


def load_env():
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def queries():
    qs = [x["query"] for g in GUIDES for x in g["picks"]] + [c["cta"][1] for c in CLUSTERS]
    return list(dict.fromkeys(qs))


def https(u):
    return "https://" + u[len("http://"):] if u and u.startswith("http://") else u


def with_affid(u, affid):
    parts = urllib.parse.urlsplit(https(u))
    q = dict(urllib.parse.parse_qsl(parts.query))
    q["affid"] = affid
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(q)))


def amount(d, *keys):
    for k in keys:
        v = (d.get(k) or {}).get("amount")
        if v:
            return int(v)
    return None


def parse(data, affid):
    items = data.get("products") or data.get("productInfoList") or []
    out = []
    for it in items:
        b = it.get("productBaseInfoV1") or (it.get("productBaseInfo") or {}).get("productAttributes") or {}
        url = b.get("productUrl") or ""
        host = urllib.parse.urlsplit(url).hostname or ""
        if not url or not (host == "flipkart.com" or host.endswith(".flipkart.com")):
            continue
        if b.get("inStock") is False:
            continue
        imgs = b.get("imageUrls") or {}
        img = imgs.get("400x400") or imgs.get("200x200") or imgs.get("275x275") or next(iter(imgs.values()), "")
        price = amount(b, "flipkartSpecialPrice", "flipkartSellingPrice", "sellingPrice")
        if not (b.get("title") and img and price):
            continue
        t = b["title"].strip()
        if len(t) > 90:
            t = t[:90].rsplit(" ", 1)[0].rstrip(",(-") + "…"
        out.append({
            "title": t,
            "brand": b.get("productBrand") or "",
            "image": https(img),
            "price": price,
            "mrp": amount(b, "maximumRetailPrice"),
            "url": with_affid(url, affid),
        })
        if len(out) >= PER_QUERY:
            break
    return out


def main():
    load_env()
    affid = os.environ.get("FK_AFFILIATE_ID") or json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["affiliate_id"]
    token = os.environ.get("FK_AFFILIATE_TOKEN")
    if not token:
        print("FK_AFFILIATE_TOKEN not set; keeping existing products.json")
        return
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"items": {}}
    items, ok, fail = dict(old.get("items", {})), 0, 0
    for q in queries():
        url = API + "?" + urllib.parse.urlencode({"query": q, "resultCount": 10})
        req = urllib.request.Request(url, headers={"Fk-Affiliate-Id": affid, "Fk-Affiliate-Token": token, "User-Agent": "smartkitchen-picks"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                prods = parse(json.loads(r.read().decode("utf-8")), affid)
            if prods:
                items[q] = prods
            ok += 1
        except Exception as ex:
            fail += 1
            print(f"  failed: {q!r}: {type(ex).__name__} {getattr(ex, 'code', '')}")
        time.sleep(0.3)  # well under the 20 calls/second API limit
    OUT.write_text(json.dumps({"fetched": datetime.date.today().isoformat(), "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Queries ok={ok} failed={fail}; queries with products={len(items)}")


if __name__ == "__main__":
    main()
