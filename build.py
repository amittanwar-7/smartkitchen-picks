"""Static site generator. Edit config.json and content.py, then run: python build.py  (output goes to ./docs)"""
import json, html, shutil, datetime
from pathlib import Path
from urllib.parse import quote_plus

from content import GUIDES
from clusters import CLUSTERS

ROOT = Path(__file__).parent
cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
OUT = ROOT / "docs"
BASE = cfg["site_url"].rstrip("/")
TODAY = datetime.date.today().isoformat()
e = html.escape

LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
<rect width="64" height="64" rx="14" fill="#0b5fff"/>
<path d="M18 26h28l-3 20a4 4 0 0 1-4 3H25a4 4 0 0 1-4-3z" fill="#fff"/>
<path d="M16 26h32" stroke="#f7b500" stroke-width="5" stroke-linecap="round"/>
<path d="M26 20c0-5 4-6 6-10M34 20c0-5 4-6 6-10" stroke="#f7b500" stroke-width="3" fill="none" stroke-linecap="round"/>
</svg>"""


def make_og_image(path, name):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1200, 630), "#0b5fff")
    d = ImageDraw.Draw(img)

    def font(size):
        for f in ("arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                pass
        return ImageFont.load_default()

    d.rounded_rectangle((90, 215, 290, 415), 40, fill="#ffffff")
    d.rectangle((75, 240, 305, 270), fill="#f7b500")
    d.text((340, 230), name, font=font(64), fill="#ffffff")
    d.text((340, 330), "Budget kitchen buying guides for India", font=font(36), fill="#dbe7ff")
    img.save(path)


def link(query):
    return f"https://www.flipkart.com/search?q={quote_plus(query)}&affid={cfg['affiliate_id']}"


_pf = ROOT / "products.json"
PRODUCTS = json.loads(_pf.read_text(encoding="utf-8")) if _pf.exists() else {"items": {}}


def products_html(query):
    items = PRODUCTS.get("items", {}).get(query) or []
    if not items:
        return ""
    cards = ""
    for p in items:
        mrp = f' <s>₹{p["mrp"]:,}</s>' if p.get("mrp") and p["mrp"] > p["price"] else ""
        cards += (f'<a class="prod" rel="sponsored nofollow noopener" target="_blank" href="{e(p["url"])}">'
                  f'<img src="{e(p["image"])}" alt="{e(p["title"])}" width="160" height="160" loading="lazy" referrerpolicy="no-referrer">'
                  f'<span class="pt">{e(p["title"])}</span><span class="pp">₹{p["price"]:,}{mrp}</span></a>')
    return (f'<div class="prods">{cards}</div>'
            f'<p class="meta">Examples from Flipkart. Price as of {e(PRODUCTS.get("fetched", ""))}; prices and stock change often, so check Flipkart before you buy.</p>')


def slugify(s):
    return "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")


CSS = """
:root{--b:#0b5fff;--bg:#fafafa;--t:#1f2933}*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:var(--bg);color:var(--t);line-height:1.7}
header,footer{background:#fff;border-bottom:1px solid #e5e7eb;padding:14px 20px}footer{border-top:1px solid #e5e7eb;border-bottom:0;margin-top:40px;font-size:.9rem}
header a{margin-right:16px;text-decoration:none;color:var(--b);font-weight:600}
header .brand{display:inline-flex;align-items:center;gap:10px;color:var(--t);margin-right:24px}
main{max-width:820px;margin:0 auto;padding:20px}h1{line-height:1.25}h2{margin-top:2rem}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:16px;margin:14px 0}
.btn{display:inline-block;background:#f7b500;color:#111;padding:8px 14px;border-radius:6px;text-decoration:none;font-weight:700}
.note{background:#fff8e1;border-left:4px solid #f7b500;padding:10px 14px;font-size:.92rem}
.crumbs,.meta{font-size:.88rem;color:#52606d}.crumbs a{color:var(--b)}
table{border-collapse:collapse;width:100%;font-size:.92rem;background:#fff}th,td{border:1px solid #e5e7eb;padding:8px 10px;text-align:left;vertical-align:top}th{background:#f1f5f9}
.label{font-weight:700;margin:.6rem 0 .2rem}
.prods{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin:12px 0 4px}
.prod{display:flex;flex-direction:column;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px;text-decoration:none;color:var(--t);font-size:.88rem}
.prod img{width:100%;height:160px;object-fit:contain}.prod .pt{margin:6px 0;line-height:1.35}.prod .pp{font-weight:700;margin-top:auto}.prod s{color:#7b8794;font-weight:400}
"""

NAV = '<a href="{b}/">Home</a><a href="{b}/about.html">About</a><a href="{b}/disclosure.html">Affiliate Disclosure</a>'


def jsonld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False) + "</script>"


def page(path, title, desc, body, extra_ld=(), og_type="website", noindex=False):
    url = f"{BASE}/" if path == "index.html" else f"{BASE}/{path}"
    img = f"{BASE}/og-image.png"
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": cfg["site_name"], "url": f"{BASE}/", "inLanguage": "en-IN"}]
    ld += list(extra_ld)
    robots = "noindex,follow" if noindex else "index,follow,max-image-preview:large"
    doc = f"""<!doctype html><html lang="en-IN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<meta name="robots" content="{robots}"><meta name="theme-color" content="#0b5fff">
<link rel="canonical" href="{url}">
<link rel="icon" type="image/svg+xml" href="{BASE}/favicon.svg"><link rel="apple-touch-icon" href="{BASE}/og-image.png">
<meta property="og:type" content="{og_type}"><meta property="og:site_name" content="{e(cfg['site_name'])}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}"><meta property="og:image" content="{img}"><meta property="og:locale" content="en_IN">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}"><meta name="twitter:image" content="{img}">
<style>{CSS}</style>{''.join(jsonld(x) for x in ld)}
{cfg.get('analytics_snippet', '')}</head><body>
<header><a class="brand" href="{BASE}/"><img src="{BASE}/logo.svg" alt="{e(cfg['site_name'])} logo" width="36" height="36"><strong>{e(cfg['site_name'])}</strong></a> {NAV.format(b=BASE)}</header>
<main>{body}</main>
<footer>© {e(cfg['site_name'])}. As a Flipkart affiliate we may earn a commission from qualifying purchases, at no extra cost to you.
Prices and availability change, so please check Flipkart for the latest details.
<br><a href="{BASE}/privacy.html">Privacy</a></footer></body></html>"""
    (OUT / path).write_text(doc, encoding="utf-8")


def ul(items):
    return "<ul>" + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul>"


def render_guide(g):
    p = f"{g['slug']}.html"
    gurl = f"{BASE}/{p}"
    intro = "".join(f"<p>{e(x)}</p>" for x in g["intro"])
    table = ("<table><thead><tr><th>Pick</th><th>Best for</th></tr></thead><tbody>"
             + "".join(f'<tr><td><a href="#{slugify(x["name"])}">{e(x["name"])}</a></td><td>{e(x["best_for"])}</td></tr>' for x in g["picks"])
             + "</tbody></table>")
    sections = ""
    for s in g["sections"]:
        sections += f"<h2>{e(s['h'])}</h2>"
        sections += "".join(f"<p>{e(x)}</p>" for x in s.get("p", []))
        if s.get("ul"):
            sections += ul(s["ul"])
    picks = ""
    for i, x in enumerate(g["picks"]):
        picks += (f'<div class="card" id="{slugify(x["name"])}"><h3>{i+1}. {e(x["name"])}</h3><p>{e(x["why"])}</p>'
                  f'<p class="label">Best for</p><p>{e(x["best_for"])}</p>'
                  f'<p class="label">What to look for</p>{ul(x["look"])}'
                  f'<p class="label">What to avoid</p>{ul(x["avoid"])}{products_html(x["query"])}'
                  f'<a class="btn" rel="sponsored nofollow noopener" target="_blank" href="{e(link(x["query"]))}">See {e(x["name"].lower())} options on Flipkart</a></div>')
    faq = "".join(f"<h3>{e(q)}</h3><p>{e(a)}</p>" for q, a in g["faq"])
    related = "".join(f'<li><a href="{BASE}/{o["slug"]}.html">{e(o["title"])}</a></li>' for o in GUIDES if o is not g)
    arts = [c for c in CLUSTERS if c["pillar"] == g["slug"]]
    articles = ""
    if arts:
        articles = ("<h2>Related articles</h2><ul>"
                    + "".join(f'<li><a href="{BASE}/{c["slug"]}.html">{e(c["title"])}</a></li>' for c in arts) + "</ul>")
    body = (f'<p class="crumbs"><a href="{BASE}/">Home</a> › {e(g["title"])}</p><h1>{e(g["title"])}</h1>'
            f'<p class="meta">By {e(cfg["site_name"])} · Last updated {TODAY}</p>'
            f'{intro}<h2>Quick overview</h2>{table}{sections}<h2>Our picks and what to check</h2>{picks}'
            f'<h2>Common mistakes to avoid</h2>{ul(g["mistakes"])}<h2>Frequently asked questions</h2>{faq}'
            f'{articles}<h2>More buying guides</h2><ul>{related}</ul>'
            '<div class="note">Disclosure: links on this page are affiliate links. We may earn a commission if you buy, at no extra cost to you. '
            'We do not test products ourselves; these guides explain what to check before you buy.</div>')
    ld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{BASE}/"},
            {"@type": "ListItem", "position": 2, "name": g["title"], "item": gurl}]},
        {"@context": "https://schema.org", "@type": "Article", "headline": g["title"], "description": g["desc"],
         "image": f"{BASE}/og-image.png", "datePublished": TODAY, "dateModified": TODAY, "inLanguage": "en-IN",
         "mainEntityOfPage": gurl, "author": {"@type": "Organization", "name": cfg["site_name"], "url": f"{BASE}/"},
         "publisher": {"@type": "Organization", "name": cfg["site_name"], "logo": {"@type": "ImageObject", "url": f"{BASE}/og-image.png"}}},
    ]
    page(p, g["title"], g["desc"], body, extra_ld=ld, og_type="article")


def render_cluster(c):
    p = f"{c['slug']}.html"
    curl = f"{BASE}/{p}"
    pillar = next(g for g in GUIDES if g["slug"] == c["pillar"])
    intro = "".join(f"<p>{e(x)}</p>" for x in c["intro"])
    secs = ""
    for s in c["sections"]:
        secs += f"<h2>{e(s['h'])}</h2>" + "".join(f"<p>{e(x)}</p>" for x in s.get("p", []))
        if s.get("ul"):
            secs += ul(s["ul"])
    faq = "".join(f"<h3>{e(q)}</h3><p>{e(a)}</p>" for q, a in c["faq"])
    sibs = [o for o in CLUSTERS if o["pillar"] == c["pillar"] and o is not c]
    more = "".join(f'<li><a href="{BASE}/{o["slug"]}.html">{e(o["title"])}</a></li>' for o in sibs)
    body = (f'<p class="crumbs"><a href="{BASE}/">Home</a> › <a href="{BASE}/{pillar["slug"]}.html">{e(pillar["title"])}</a> › {e(c["title"])}</p>'
            f'<h1>{e(c["title"])}</h1><p class="meta">By {e(cfg["site_name"])} · Last updated {TODAY}</p>'
            f'{intro}{secs}{products_html(c["cta"][1])}<p><a class="btn" rel="sponsored nofollow noopener" target="_blank" href="{e(link(c["cta"][1]))}">{e(c["cta"][0])}</a></p>'
            f'<h2>Frequently asked questions</h2>{faq}'
            f'<h2>Read the full guide</h2><ul><li><a href="{BASE}/{pillar["slug"]}.html">{e(pillar["title"])}</a></li></ul>'
            + (f"<h2>Related articles</h2><ul>{more}</ul>" if more else "")
            + '<div class="note">Disclosure: Flipkart links on this page are affiliate links. We may earn a commission if you buy, at no extra cost to you.</div>')
    ld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{BASE}/"},
            {"@type": "ListItem", "position": 2, "name": pillar["title"], "item": f"{BASE}/{pillar['slug']}.html"},
            {"@type": "ListItem", "position": 3, "name": c["title"], "item": curl}]},
        {"@context": "https://schema.org", "@type": "Article", "headline": c["title"], "description": c["desc"],
         "image": f"{BASE}/og-image.png", "datePublished": TODAY, "dateModified": TODAY, "inLanguage": "en-IN",
         "mainEntityOfPage": curl, "author": {"@type": "Organization", "name": cfg["site_name"], "url": f"{BASE}/"},
         "publisher": {"@type": "Organization", "name": cfg["site_name"], "logo": {"@type": "ImageObject", "url": f"{BASE}/og-image.png"}}},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in c["faq"]]},
    ]
    page(p, c["title"], c["desc"], body, extra_ld=ld, og_type="article")


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    urls = ["index.html"]
    cards = ""
    for g in GUIDES:
        urls.append(f"{g['slug']}.html")
        cards += f'<div class="card"><h2><a href="{BASE}/{g["slug"]}.html">{e(g["title"])}</a></h2><p>{e(g["desc"])}</p></div>'
        render_guide(g)
    latest = ""
    for c in CLUSTERS:
        urls.append(f"{c['slug']}.html")
        latest += f'<li><a href="{BASE}/{c["slug"]}.html">{e(c["title"])}</a></li>'
        render_cluster(c)
    page("index.html", f"{cfg['site_name']} – Budget Kitchen Gadgets Buying Guides",
         "Honest buying guides for budget kitchen gadgets in India: what to check before you buy gadgets under ₹500 and ₹1000.",
         f"<h1>{e(cfg['site_name'])}</h1><p>Practical buying guides for budget kitchen gadgets in India. "
         "Each guide explains the materials, specs and safety checks that matter, so you can pick the right product yourself.</p>"
         f"{cards}<h2>How-to articles and buying tips</h2><ul>{latest}</ul>")
    urls += ["about.html", "disclosure.html", "privacy.html"]
    page("about.html", "About Us", "About SmartKitchen Picks India, how we write our guides and how the site earns money.",
         f"<h1>About {e(cfg['site_name'])}</h1>"
         "<p>This site publishes buying guides for budget kitchen products in India. Our goal is to explain what to check before you buy, "
         "such as materials, safety, size and warranty, so that you spend your money on the right thing.</p>"
         "<h2>How we write our guides</h2>"
         "<p>We research each product category, explain how the products work, and list what to look for and what to avoid. "
         "We do not test products ourselves, so we never claim hands-on testing and we do not rank products by performance. "
         "Where a statement depends on a product's specification, we tell you to check the listing.</p>"
         "<h2>How the site earns money</h2>"
         "<p>We are part of the Flipkart Affiliate Program. If you buy through a link, we may earn a commission at no extra cost to you. "
         "This does not change what we recommend you check. See our <a href=\"" + BASE + "/disclosure.html\">affiliate disclosure</a>.</p>"
         "<h2>Corrections</h2><p>Product details and prices change. If you find an error, please contact us through the GitHub repository for this site and we will correct it.</p>")
    page("disclosure.html", "Affiliate Disclosure", "How this site earns money through the Flipkart Affiliate Program.",
         "<h1>Affiliate Disclosure</h1><p>This site participates in the Flipkart Affiliate Program. "
         "When you click a link and make a purchase, we may earn a commission at no extra cost to you. "
         "Product prices and availability are set by Flipkart and its sellers and may change at any time.</p>")
    page("privacy.html", "Privacy Policy", "How this site handles visitor data and cookies.",
         "<h1>Privacy Policy</h1><p>We do not collect personal information directly. If analytics is enabled, "
         "it may use cookies to count visits. Flipkart may set its own cookies when you follow a link.</p>")
    page("404.html", "Page not found", "This page could not be found.",
         f'<h1>Page not found</h1><p>Try the <a href="{BASE}/">home page</a> for all our guides.</p>', noindex=True)
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{BASE}/{'' if u == 'index.html' else u}</loc><lastmod>{TODAY}</lastmod></url>" for u in urls)
        + "</urlset>", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    (OUT / "logo.svg").write_text(LOGO_SVG, encoding="utf-8")
    (OUT / "favicon.svg").write_text(LOGO_SVG, encoding="utf-8")
    make_og_image(OUT / "og-image.png", cfg["site_name"])
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Built {len(urls) + 1} pages into {OUT}")


build()
