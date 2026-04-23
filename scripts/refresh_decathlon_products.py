
from __future__ import annotations
import json, os, re, html, urllib.parse, requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_PATH = DATA_DIR / "decathlon_products.json"

FEED_URL = os.getenv("DECATHLON_FEED_URL","").strip()
MAX_PRODUCTS = 200

def normalize(x):
    return urllib.parse.unquote(html.unescape(str(x or ""))).strip()

def is_cycling(text):
    text = text.lower()
    return any(k in text for k in ["bici","cicl","mtb","maillot","casco","rodillo"])

def parse_feed(raw):
    products=[]
    seen=set()

    matches = re.finditer(r"https://afiliacion\.decathlon\.es[^\s]+", raw)

    for m in matches:
        aff = normalize(m.group(0))

        parsed = urllib.parse.urlparse(aff)
        qs = urllib.parse.parse_qs(parsed.query)

        url = normalize(qs.get("url",[""])[0])
        pca = normalize(qs.get("pca",[""])[0])

        title = ""
        if "|" in pca:
            parts = pca.split("|")
            if len(parts)>1:
                title = parts[1]

        if not title:
            title = url.split("/")[-1].replace("-"," ").title()

        if not is_cycling(title):
            continue

        if url in seen:
            continue
        seen.add(url)

        products.append({
            "id": url,
            "title": title[:120],
            "url": url,
            "affiliate_url": aff,
            "image": "",
            "price": None,
            "source": "decathlon"
        })

    return products[:MAX_PRODUCTS]

def main():
    DATA_DIR.mkdir(exist_ok=True)
    r = requests.get(FEED_URL)
    raw = r.text

    products = parse_feed(raw)

    OUTPUT_PATH.write_text(json.dumps(products, indent=2, ensure_ascii=False))
    print("DECATHLON FINAL:", len(products))

if __name__=="__main__":
    main()
