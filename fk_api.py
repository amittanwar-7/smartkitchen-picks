"""Tiny client for the Flipkart Affiliate Product Feed API. Credentials come from .env (never committed)."""
import json, os, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
API = "https://affiliate-api.flipkart.net/affiliate"


def creds():
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    aid = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["flipkart_affid"]
    return aid, env.get("FK_AFFILIATE_TOKEN") or os.environ["FK_AFFILIATE_TOKEN"]


def get(url):
    aid, tok = creds()
    req = urllib.request.Request(url, headers={"Fk-Affiliate-Id": aid, "Fk-Affiliate-Token": tok})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def categories():
    aid, _ = creds()
    return get(f"{API}/api/{aid}.json")


if __name__ == "__main__":
    d = categories()
    for k, v in d.get("apiGroups", {}).get("affiliate", {}).get("apiListings", {}).items():
        print(k)
