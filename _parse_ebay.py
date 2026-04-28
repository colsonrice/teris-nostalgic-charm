"""Stricter eBay parser — match complete item card structures."""
import re, json
from pathlib import Path

with open("/tmp/teri_ebay.html") as f:
    html = f.read()

# eBay store cards seem to use the structure:
#   <a href=https://www.ebay.com/itm/<id>?... aria-label="<title>" ... class=str-item-card__link>
#     ...
#     <picture> with image src https://i.ebayimg.com/images/g/<imghash>/s-l300.webp
#     ...
#     "$<price>" text appears near "Buy It Now" or as plain dollar amount
# Each card is bounded; let's split by str-item-card__link occurrences.

# Find all anchor links to items
link_pattern = re.compile(
    r'<a\s+href=(?P<url>https://www\.ebay\.com/itm/(?P<iid>\d+)\?[^\s>]+)'
    r'\s+_sp=[^\s>]*\s+target=_blank\s+aria-label="(?P<title>[^"]+)"',
    re.I
)

items = []
matches = list(link_pattern.finditer(html))
print(f"Found {len(matches)} item cards")

# Each item card extends from this anchor until the NEXT anchor (or end of section)
for i, m in enumerate(matches):
    end = matches[i + 1].start() if i + 1 < len(matches) else min(len(html), m.end() + 4000)
    block = html[m.start():end]

    # Extract image hash from the picture element
    img_match = re.search(r'i\.ebayimg\.com/images/g/([A-Za-z0-9~\-]+)/s-l\d+\.(?:webp|jpg)', block)
    img_hash = img_match.group(1) if img_match else None

    # Extract price — look for the str-item-card__price class block, or fall back to first $X.XX
    price_match = re.search(r'class=str-item-card__price[^>]*>\$([0-9]+(?:\.[0-9]{1,2})?)', block)
    if not price_match:
        price_match = re.search(r'>\s*\$([0-9]+(?:\.[0-9]{1,2})?)\s*<', block)
    if not price_match:
        price_match = re.search(r'\$([0-9]+\.[0-9]{2})', block)

    price = f"${price_match.group(1)}" if price_match else None
    # Normalize
    if price and "." not in price[1:]:
        price = price + ".00"

    items.append({
        "id": m.group("iid"),
        "url": m.group("url").replace("&amp;", "&"),
        "title": m.group("title"),
        "image": f"https://i.ebayimg.com/images/g/{img_hash}/s-l500.jpg" if img_hash else None,
        "price": price,
    })

# Dedupe
seen = set()
clean = []
for it in items:
    if it["id"] in seen or not it["image"]:
        continue
    seen.add(it["id"])
    clean.append(it)

print(f"After dedup: {len(clean)} items with images")
print()
print("Sample (first 15):")
for it in clean[:15]:
    print(f"  {it['price'] or 'N/A':>8}  {it['title'][:70]}")

with open("/tmp/teri_products.json", "w") as f:
    json.dump(clean, f, indent=2)
print(f"\nSaved {len(clean)} items.")
