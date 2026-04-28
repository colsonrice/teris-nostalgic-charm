"""Scrape Teri's Etsy shop listings.

PRIMARY:  Etsy Open API v3 — gets ALL active listings (100/page).
          Requires the env var ETSY_API_KEY (your Etsy app keystring).
          → Get one free at https://www.etsy.com/developers/register

FALLBACK: RSS feed — always works, but limited to 10 most-recent items.
          Existing items from prior runs are preserved in the merged output.

Outputs _source_products.json in the same directory as this script.

Usage:
    python3 _scrape_etsy.py                        # RSS fallback (no key)
    ETSY_API_KEY=abc123 python3 _scrape_etsy.py    # full catalog via API
"""
import html as htmlmod
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

SHOP_NAME  = "NostalgicCharm"
SHOP_RSS   = f"https://www.etsy.com/shop/{SHOP_NAME}/rss"
API_BASE   = "https://openapi.etsy.com/v3/application"
OUT        = Path(__file__).parent / "_source_products.json"
MIN_ITEMS  = 5    # refuse to overwrite if we found fewer than this
API_KEY    = os.environ.get("ETSY_API_KEY", "")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _norm_price(raw) -> str:
    """Return '$XX.XX' from whatever Etsy gives us, or ''."""
    if not raw:
        return ""
    if isinstance(raw, (int, float)):
        return f"${raw:.2f}"
    s = str(raw).strip()
    m = re.search(r"\$([0-9]+(?:\.[0-9]{1,2})?)", s)
    if m:
        v = m.group(1)
        return f"${v}" if "." in v else f"${v}.00"
    m = re.match(r"([0-9]+(?:\.[0-9]{1,2})?)", s.replace(",", ""))
    return f"${m.group(1)}" if m else ""


def _unescape(t: str) -> str:
    """Unescape HTML entities; Etsy RSS double-encodes some (& → &amp; → &amp;amp;)."""
    prev = None
    while prev != t:
        prev = t
        t = htmlmod.unescape(t)
    return t


def _scrub_title(t: str) -> str:
    t = _unescape(t)
    return re.sub(r"\s+by\s+NostalgicCharm\s*$", "", t, flags=re.I).strip()


def _api_get(path: str, params: dict | None = None) -> dict | None:
    """Make an authenticated Etsy API v3 request. Returns parsed JSON or None."""
    if not API_KEY:
        return None
    qs = ""
    if params:
        qs = "?" + "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{API_BASE}{path}{qs}"
    req = urllib.request.Request(
        url,
        headers={
            "x-api-key": API_KEY,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        print(f"[etsy] API error {e.code} for {url}: {body}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"[etsy] API request failed: {exc}", file=sys.stderr)
        return None


# ── Strategy 1: Etsy API v3 ───────────────────────────────────────────────────

def _scrape_api() -> list[dict]:
    """Fetch all active listings via Etsy Open API v3 (requires ETSY_API_KEY)."""
    if not API_KEY:
        print("[etsy] ETSY_API_KEY not set — skipping API strategy", file=sys.stderr)
        return []

    print(f"[etsy] using Etsy API v3 key: {API_KEY[:6]}…", file=sys.stderr)

    # 1. Resolve shop_id from shop name
    shop_data = _api_get("/shops", {"shop_name": SHOP_NAME})
    if not shop_data or not shop_data.get("results"):
        print(f"[etsy] could not resolve shop '{SHOP_NAME}' — trying by name directly",
              file=sys.stderr)
        shop_id = SHOP_NAME
    else:
        shop_id = shop_data["results"][0].get("shop_id") or SHOP_NAME
        print(f"[etsy] shop_id = {shop_id}", file=sys.stderr)

    # 2. Paginate through listings
    items: list[dict] = []
    limit  = 100
    offset = 0

    while True:
        data = _api_get(
            f"/shops/{shop_id}/listings/active",
            {
                "limit":    limit,
                "offset":   offset,
                "includes": "Images",   # embed image data in response
            },
        )
        if not data:
            break
        results = data.get("results", [])
        if not results:
            break

        for r in results:
            lid   = str(r.get("listing_id", ""))
            title = r.get("title", "").strip()
            url   = r.get("url", f"https://www.etsy.com/listing/{lid}/")

            # Price: v3 uses { amount: int, divisor: int, currency_code: str }
            price = ""
            p = r.get("price") or {}
            if isinstance(p, dict) and p.get("amount") and p.get("divisor"):
                dollars = p["amount"] / p["divisor"]
                price = f"${dollars:.2f}"
            elif isinstance(p, dict):
                price = _norm_price(p.get("currency_formatted_value") or
                                    p.get("display_price") or "")
            else:
                price = _norm_price(str(p))

            # Image: included via ?includes=Images
            image = ""
            images = r.get("Images") or r.get("images") or []
            if images:
                img = images[0]
                image = (
                    img.get("url_570xN")
                    or img.get("url_570xN")
                    or img.get("url_75x75")
                    or img.get("url", "")
                )

            if lid and title:
                items.append({
                    "id":    lid,
                    "title": title,
                    "url":   url,
                    "image": image,
                    "price": price,
                })

        count = data.get("count", 0)
        print(f"[etsy] API page offset={offset}: {len(results)} listings "
              f"(total so far: {len(items)}, shop has {count})",
              file=sys.stderr)

        if len(results) < limit or (count and len(items) >= count):
            break
        offset += limit
        time.sleep(0.3)   # be polite to the API

    print(f"[etsy] API total: {len(items)} listings", file=sys.stderr)
    return items


# ── Strategy 2: RSS feed (always available, ≤10 items) ───────────────────────

def _scrape_rss() -> list[dict]:
    """Fetch the Etsy shop RSS feed. Returns ≤10 most-recently-listed items."""
    print("[etsy] fetching RSS feed …", file=sys.stderr)
    result = subprocess.run(
        [
            "curl", "-sL",
            "-A", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            SHOP_RSS,
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    raw    = result.stdout
    chunks = re.findall(r"<item>(.*?)</item>", raw, re.DOTALL)
    items  = []
    for chunk in chunks:
        t = re.search(r"<title>(.*?)</title>",           chunk, re.DOTALL)
        l = re.search(r"<link>(.*?)</link>",             chunk, re.DOTALL)
        d = re.search(r"<description>(.*?)</description>", chunk, re.DOTALL)
        if not (t and l and d):
            continue
        title  = _scrub_title(htmlmod.unescape(t.group(1)).strip())
        url    = l.group(1).strip()
        desc   = htmlmod.unescape(d.group(1))
        pm     = re.search(r'class="price"[^>]*>([^<]+)', desc)
        im     = re.search(r'<img\s+src="([^"]+)"',       desc)
        lm     = re.search(r"/listing/(\d+)/",            url)
        items.append({
            "id":    lm.group(1) if lm else "",
            "title": title,
            "url":   url,
            "image": im.group(1) if im else "",
            "price": _norm_price(pm.group(1) if pm else ""),
        })
    print(f"[etsy] RSS: {len(items)} items", file=sys.stderr)
    return items


# ── Merge with previous run ────────────────────────────────────────────────────

def _merge(fresh: list[dict]) -> list[dict]:
    """
    Keep items from the previous run that aren't in the fresh batch.
    This preserves the full catalog when we only fetched RSS (10 items).
    """
    if not OUT.exists():
        return fresh
    try:
        existing = json.loads(OUT.read_text())
    except Exception:
        return fresh

    fresh_ids = {p["id"] for p in fresh if p.get("id")}
    kept = [p for p in existing if p.get("id") and p["id"] not in fresh_ids]
    if kept:
        print(f"[etsy] retaining {len(kept)} items from previous run not found today",
              file=sys.stderr)
    return fresh + kept


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"[etsy] starting scrape for {SHOP_NAME} …")

    # Primary: Etsy API v3 (full catalog)
    items = _scrape_api()

    # Fallback: RSS (10 most recent)
    if len(items) < MIN_ITEMS:
        if API_KEY:
            print("[etsy] API returned too few items — falling back to RSS", file=sys.stderr)
        items = _scrape_rss()
        items = _merge(items)   # pad with previous run's items

    if len(items) < MIN_ITEMS:
        print(f"[etsy] ERROR: only {len(items)} items found — aborting to protect existing data",
              file=sys.stderr)
        sys.exit(1)

    # Deduplicate by id
    seen: set[str] = set()
    clean: list[dict] = []
    for p in items:
        pid = p.get("id", "")
        if pid and pid not in seen:
            seen.add(pid)
            clean.append(p)

    OUT.write_text(json.dumps(clean, indent=2, ensure_ascii=False))
    print(f"[etsy] saved {len(clean)} items → {OUT}")
