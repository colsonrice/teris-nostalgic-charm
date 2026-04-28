"""Generate the index.html for Teri's Nostalgic Charm from product data.

Pipeline:
    1. _scrape_etsy.py  ← scrapes Etsy shop → _source_products.json
    2. this script      ← _source_products.json → index.html + products.json

Re-run this any time the source data changes. Update CONTACT_EMAIL below
to route inquiries to Teri's real inbox before going live.
"""
import json
import re
from pathlib import Path
from urllib.parse import quote

HERE    = Path(__file__).parent
OUT_DIR = HERE
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---- Config ----------------------------------------------------------
# UPDATE THIS to Teri's real inbox before going live.
CONTACT_EMAIL = "hello@terisnostalgiccharm.com"
SITE_TITLE = "Teri's Nostalgic Charm"
SITE_TAG = "A Catalog of Wearable Mementos"
# ---------------------------------------------------------------------

with open(HERE / "_source_products.json") as f:
    products = json.load(f)


def clean_title(t: str) -> str:
    """Clean up eBay-style titles for display."""
    t = t.strip()
    t = t.replace("\\\"", '"').replace('\\\\', '\\').replace("\\/", "/")
    # Remove dangling escape artifacts (e.g. 3/4\" truncated at the quote)
    t = re.sub(r'\\.', '', t)
    # Strip trailing/leading backslashes and whitespace
    t = t.strip(" \\")
    # Drop a dangling fraction like "3/4" or "18" with no unit
    # (the sizes that got cropped — keep the rest of the descriptor)
    t = re.sub(r"\s+\d+/\d+$", "", t)
    t = re.sub(r"\s+\d+$", "", t)
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t)
    return t


def short_title(t: str, words: int = 5) -> str:
    """Get a short editorial title — first few significant words."""
    t = clean_title(t)
    parts = t.split()
    return " ".join(parts[:words])


def categorize(title: str) -> str:
    t = title.lower()
    if any(k in t for k in [
        "christmas", "gingerbread", "snowflake", "holiday", "valentine",
        "easter", "shamrock", "heart", "angel", "cherub", "cupid",
        "st patrick", "paddy", "clover", "winter",
    ]):
        return "Holiday"
    if any(k in t for k in [
        "teddy", "bear", "bulldog", "dog", "dachshund", "airedale", "bee",
        "rooster", "chicken", "hare", "rabbit", "bunny", "turtle",
        "tortoise", "terrier",
    ]):
        return "Menagerie"
    if any(k in t for k in [
        "hockey", "runner", "skater", "swimmer", "soccer", "figure",
        "cross-country", "diver", "ball", "athlete",
    ]):
        return "Sport"
    if any(k in t for k in [
        "attorney", "lawyer", "nurse", "phlebotomist", "syringe", "stylist",
        "cosmetologist", "optometrist", "navy", "usn", "barbie", "clarinet",
        "musician", "doctor",
    ]):
        return "Vocation"
    if any(k in t for k in [
        "celestial", "moon", "star", "palm", "alice", "wonderland", "clock",
        "wonder", "tropical", "oasis",
    ]):
        return "Whimsy"
    return "Curio"


def material(title: str) -> str:
    t = title.lower()
    if "24 karat gold" in t or "24 kt gold" in t or "24 karat plate" in t:
        return "24K Gold Plate"
    if "sterling silver" in t:
        return "Sterling Silver Plate"
    if "matte silver" in t or "oxidized matte silver" in t:
        return "Oxidized Matte Silver"
    if "antiqued brass" in t or "brass" in t:
        return "Antiqued Brass"
    if "pewter" in t:
        return "Pewter"
    if "copper" in t:
        return "Copper"
    if "silver plate" in t:
        return "Silver Plate"
    return "Mixed Metals"


def form(title: str) -> str:
    t = title.lower()
    if "earrings" in t or "earings" in t:
        return "Earrings"
    if "necklace" in t:
        return "Necklace"
    if "brooch" in t or " pin " in t or t.endswith(" pin") or "pin brooch" in t:
        return "Pin · Brooch"
    if "bracelet" in t:
        return "Bracelet"
    if "anklet" in t:
        return "Anklet"
    return "Charm"


def inquiry_link(item):
    """Build a mailto URL pre-filled with the piece details."""
    subject = f"Inquiring about № {item['no']} — {short_title(item['title'], 6)}"
    body = (
        f"Hi Teri,\n\n"
        f"I'd like to reserve this piece:\n\n"
        f"  № {item['no']}\n"
        f"  {item['title']}\n"
        f"  {item['form']} · {item['material']}\n"
        f"  {item['price']}\n\n"
        f"Could you let me know if it's still available and how to complete the purchase?\n\n"
        f"Thank you!\n— "
    )
    return f"mailto:{CONTACT_EMAIL}?subject={quote(subject)}&body={quote(body)}"


# Annotate
catalog = []
for i, p in enumerate(products, 1):
    t = clean_title(p["title"])
    item = {
        "no": f"{i:03d}",
        "title": t,
        "short": short_title(t, 5),
        "image": p["image"],
        "url": p["url"],   # kept in data layer, not surfaced on the site
        "price": p["price"] or "—",
        "category": categorize(t),
        "material": material(t),
        "form": form(t),
    }
    item["inquire"] = inquiry_link(item)
    catalog.append(item)

# Save annotated catalog
with open(OUT_DIR / "products.json", "w") as f:
    json.dump(catalog, f, indent=2)


# ---------- HTML rendering ----------

def render_product(item, klass="card"):
    return f"""<a class="{klass}" href="{item['inquire']}">
  <figure class="card__media">
    <img src="{item['image']}" alt="{item['title']}" loading="lazy" decoding="async" />
    <span class="card__cat">{item['category']}</span>
  </figure>
  <div class="card__body">
    <span class="card__no">№ {item['no']}</span>
    <h3 class="card__title">{item['short']}</h3>
    <p class="card__meta">{item['form']} · {item['material']}</p>
    <p class="card__price">{item['price']}</p>
    <span class="card__cta">Inquire →</span>
  </div>
</a>"""


# Featured pick — prefer Holiday/Whimsy with image, fall back to first item
def _pick_featured(cat):
    preferred_cats = ["Holiday", "Whimsy", "Menagerie"]
    for c in preferred_cats:
        candidates = [p for p in cat if p["category"] == c and p["image"]]
        if candidates:
            return candidates[0]
    return cat[0]

featured = _pick_featured(catalog)

def pick(category, n=4):
    return [p for p in catalog if p["category"] == category][:n]

raw_grid = (
    pick("Holiday", 3) + pick("Menagerie", 2) + pick("Vocation", 2)
    + pick("Sport", 2) + pick("Whimsy", 1)
)
seen: set[str] = set()
catalog_grid = [p for p in raw_grid if not (p["no"] in seen or seen.add(p["no"]))]
# If we don't have enough categorized items, pad with uncategorized ("Curio")
if len(catalog_grid) < 6:
    curios = [p for p in catalog if p["no"] not in seen]
    catalog_grid += curios[:max(0, 6 - len(catalog_grid))]

themes = [
    {"name": "Holiday", "blurb": "Snowflakes, gingerbread, hearts, hares, four-leaf clovers — an ornament for every calendar page.",
     "n": len([p for p in catalog if p['category'] == 'Holiday'])},
    {"name": "Menagerie", "blurb": "Teddy bears, bulldogs, bumble bees, jackrabbits — small creatures, great affection.",
     "n": len([p for p in catalog if p['category'] == 'Menagerie'])},
    {"name": "Sport", "blurb": "For the hockey goalie, the figure skater, the cross-country runner — a token for the sport that defines them.",
     "n": len([p for p in catalog if p['category'] == 'Sport'])},
    {"name": "Vocation", "blurb": "For the attorney, the nurse, the hairdresser, the petty officer — the work, made wearable.",
     "n": len([p for p in catalog if p['category'] == 'Vocation'])},
    {"name": "Whimsy", "blurb": "Celestial suns, smiling moons, Alice's clocks, palm-tree islands — little magic for everyday wear.",
     "n": len([p for p in catalog if p['category'] == 'Whimsy'])},
]

def _pick_spread(cat, exclude_no=None):
    """Pick a statement piece — necklace or brooch with image, different from featured."""
    form_pref = ["Necklace", "Pin · Brooch", "Bracelet", "Earrings", "Charm"]
    for f in form_pref:
        candidates = [
            p for p in cat
            if p["form"] == f and p["image"] and p["no"] != exclude_no
        ]
        if candidates:
            return candidates[0]
    return next(p for p in cat if p["no"] != exclude_no)

spread_pick = _pick_spread(catalog, exclude_no=featured["no"])

strip_items = [p for p in catalog if p not in catalog_grid][:8]


HTML = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{SITE_TITLE} — {SITE_TAG}</title>
  <meta name="description" content="Hand-curated charm jewelry for the people, professions, and passions you love. Earrings, brooches, necklaces, and bracelets in 24K gold plate, sterling silver, antiqued brass, and pewter." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght,SOFT,WONK@0,9..144,300..900,0..100,0..1;1,9..144,300..900,0..100,0..1&family=Manrope:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <a class="skip" href="#catalog">Skip to catalog</a>

  <!-- Top strip -->
  <div class="strip">
    <span class="strip__lock">★</span>
    <span>Hand-curated charm jewelry · {len(catalog)} pieces in the current catalog · Shipped from the United States</span>
    <span class="strip__lock">★</span>
  </div>

  <!-- Header -->
  <header class="masthead">
    <a href="#" class="mark" aria-label="{SITE_TITLE} — home">
      <span class="mark__pre">Established in Sentiment</span>
      <span class="mark__name"><em>Teri's</em><span>Nostalgic Charm</span></span>
      <span class="mark__post">{SITE_TAG}</span>
    </a>
    <nav class="nav" aria-label="Primary">
      <a href="#catalog">The Catalog</a>
      <a href="#themes">By Theme</a>
      <a href="#letter">A Note</a>
      <a href="#contact" class="nav__cta">Inquire ↓</a>
    </nav>
  </header>

  <!-- Hero -->
  <section class="hero">
    <div class="hero__grid">
      <div class="hero__copy">
        <p class="kicker">The Welcome Page</p>
        <h1 class="hero__title">
          A little<br/>
          <em>charm</em><br/>
          for every<br/>
          life.
        </h1>
        <p class="hero__lede">
          Wearable mementos for the people, professions, and passions you
          love. Each piece is hand-selected and shipped from a small
          collection that has been growing, quietly, for years.
        </p>
        <div class="hero__cta">
          <a class="btn btn--primary" href="#catalog">Browse the Catalog</a>
          <a class="btn btn--ghost" href="#letter">Read the Note ↓</a>
        </div>
        <ul class="hero__facets" aria-label="Featured materials">
          <li>24K Gold Plate</li>
          <li>·</li>
          <li>Sterling Silver</li>
          <li>·</li>
          <li>Antiqued Brass</li>
          <li>·</li>
          <li>Pewter</li>
        </ul>
      </div>
      <figure class="hero__featured">
        <div class="hero__plate">
          <span class="hero__no">№ {featured['no']}</span>
          <img src="{featured['image']}" alt="{featured['title']}" />
          <figcaption class="hero__cap">
            <span>The featured piece —</span>
            <strong>{featured['short']}</strong>
            <em>{featured['form']} · {featured['material']} · {featured['price']}</em>
            <a href="{featured['inquire']}">Inquire about this piece →</a>
          </figcaption>
        </div>
        <div class="hero__shadow" aria-hidden="true"></div>
      </figure>
    </div>
    <div class="ornament" aria-hidden="true">
      <span>✦</span><span>·</span><span>❋</span><span>·</span><span>✦</span>
    </div>
  </section>

  <!-- The Catalog -->
  <section id="catalog" class="catalog">
    <header class="section__head">
      <p class="kicker">The Catalog</p>
      <h2 class="section__title">A selection from <em>the current</em> collection.</h2>
      <p class="section__lede">
        Each piece is one of a kind in a quiet, gift-catalog way — designed
        to be unwrapped, kept, and remembered. Reach out to reserve any
        piece below.
      </p>
    </header>

    <div class="grid">
      {''.join(render_product(p) for p in catalog_grid)}
    </div>
  </section>

  <!-- By Theme -->
  <section id="themes" class="themes">
    <header class="section__head section__head--light">
      <p class="kicker kicker--light">By Theme</p>
      <h2 class="section__title section__title--light">Gift, by feeling.</h2>
      <p class="section__lede section__lede--light">
        Browse the catalog by the moment you're shopping for — the holiday,
        the hobby, the profession that defines someone you love.
      </p>
    </header>
    <ul class="themes__grid">
      {''.join(f'''
      <li class="theme">
        <a href="#catalog">
          <span class="theme__no">{["I","II","III","IV","V"][i]}</span>
          <h3 class="theme__name">{t["name"]}</h3>
          <p class="theme__blurb">{t["blurb"]}</p>
          <span class="theme__count">{t["n"]} pieces →</span>
        </a>
      </li>''' for i, t in enumerate(themes))}
    </ul>
  </section>

  <!-- A Note from Teri -->
  <section id="letter" class="letter">
    <div class="letter__inner">
      <p class="kicker">A Note</p>
      <h2 class="letter__title"><em>Dear friend,</em></h2>
      <div class="letter__body">
        <p>
          What you're looking at is, in a way, a record of small attentions —
          the little teddy bear someone wears because their grandmother had
          one just like it; the lawyer's brooch worn the day she was sworn
          in; the figure skater's earrings tucked into a Christmas card.
        </p>
        <p>
          I've spent years quietly gathering these pieces — vintage and
          vintage-inspired charm jewelry in gold plate, sterling silver,
          antiqued brass, and pewter. This page is a small front porch I
          built so they could be met properly. Reach out about anything
          that catches your eye.
        </p>
        <p class="letter__sign">
          <em>Thank you for stopping in.</em><br/>
          <span>— Teri</span>
        </p>
      </div>
    </div>
  </section>

  <!-- Editorial spread -->
  <section class="spread">
    <article class="spread__inner">
      <p class="kicker kicker--light">The Spread</p>
      <div class="spread__layout">
        <figure class="spread__figure">
          <span class="spread__no">№ {spread_pick['no']}</span>
          <img src="{spread_pick['image']}" alt="{spread_pick['title']}" />
        </figure>
        <div class="spread__copy">
          <h2 class="spread__quote">
            &ldquo;A piece of jewelry has the
            <em>strange power</em> to mean two things at once —
            something to <em>look at</em>, and something to
            <em>remember by</em>.&rdquo;
          </h2>
          <div class="spread__meta">
            <p><strong>{spread_pick['short']}</strong></p>
            <p>{spread_pick['form']} · {spread_pick['material']}</p>
            <p class="spread__price">{spread_pick['price']}</p>
            <a class="btn btn--primary btn--sm" href="{spread_pick['inquire']}">Inquire about this piece →</a>
          </div>
        </div>
      </div>
    </article>
  </section>

  <!-- More from the catalog -->
  <section class="strip-shop">
    <header class="section__head">
      <p class="kicker">More from the case</p>
      <h2 class="section__title">A few more pieces, <em>quickly</em>.</h2>
    </header>
    <div class="rail">
      {''.join(render_product(p, klass="rail-card") for p in strip_items)}
    </div>
  </section>

  <!-- Inquiry / Contact -->
  <section id="contact" class="shop">
    <div class="shop__inner">
      <p class="kicker">Reach out</p>
      <h2 class="shop__title">
        See something <em>you love</em>?<br/>
        Send a note.
      </h2>
      <p class="shop__lede">
        Every piece on this page can be reserved by message. Tell me which
        № you have in mind and I'll confirm it's still available, share any
        extra detail, and walk you through how to complete the purchase.
        Custom requests, gift wrapping, and rush shipping all welcome.
      </p>
      <div class="shop__cta">
        <a class="btn btn--primary btn--lg" href="mailto:{CONTACT_EMAIL}?subject=Hello%20from%20your%20catalog">Send a message ↗</a>
      </div>
      <p class="shop__addr"><em>{CONTACT_EMAIL}</em></p>
    </div>
  </section>

  <!-- Footer -->
  <footer class="foot">
    <div class="foot__inner">
      <div class="foot__col foot__col--mark">
        <span class="foot__name"><em>Teri's</em> Nostalgic Charm</span>
        <span class="foot__tag">{SITE_TAG}</span>
      </div>
      <div class="foot__col">
        <h4>Find a piece</h4>
        <ul>
          <li><a href="#catalog">The Catalog</a></li>
          <li><a href="#themes">By Theme</a></li>
          <li><a href="#letter">A Note from Teri</a></li>
          <li><a href="#contact">Reach out</a></li>
        </ul>
      </div>
      <div class="foot__col">
        <h4>Reserve a piece</h4>
        <ul>
          <li><a href="mailto:{CONTACT_EMAIL}?subject=Hello%20from%20your%20catalog">{CONTACT_EMAIL}</a></li>
          <li><a href="#contact">Inquire about a piece</a></li>
        </ul>
      </div>
      <div class="foot__col foot__col--colophon">
        <h4>Colophon</h4>
        <p>
          Set in <em>Fraunces</em> &amp; Manrope. Listings, photographs,
          and pieces by Teri. Printed on the modern web with care.
        </p>
        <p class="foot__copy">© {SITE_TITLE} · All rights reserved</p>
      </div>
    </div>
    <div class="foot__bar" aria-hidden="true">
      <span>✦</span> Hand-curated <span>·</span> Hand-packed <span>·</span> Hand-shipped <span>✦</span>
    </div>
  </footer>

  <script src="script.js" defer></script>
</body>
</html>
"""


(OUT_DIR / "index.html").write_text(HTML, encoding="utf-8")
print(f"Wrote {OUT_DIR/'index.html'} — {len(HTML):,} bytes")
print(f"Catalog: {len(catalog)} items, contact: {CONTACT_EMAIL}")
print(f"Featured: {featured['title'][:60]}")
print(f"Spread: {spread_pick['title'][:60]}")
