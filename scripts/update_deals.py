
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def parse_discount(value):
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        value = value.replace("%", "").strip()
        try:
            return float(value)
        except:
            return 0
    return 0

def parse_price(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        value = value.replace("€", "").replace(",", ".").strip()
        try:
            return float(value)
        except:
            return None
    return None

def calculate_score(p):
    score = 0

    if p.get("discount"):
        score += min(p["discount"], 70) * 2

    if p.get("price"):
        if p["price"] < 20:
            score += 20
        elif p["price"] < 50:
            score += 10

    if p.get("image"):
        score += 10
    else:
        score -= 30

    if not p.get("old_price"):
        score -= 10

    if p.get("sales"):
        score += min(p["sales"] / 10, 20)

    return score

def clean_products(products):
    clean = []
    for p in products:
        price = parse_price(p.get("price"))
        if not price:
            continue
        p["price"] = price

        discount = parse_discount(p.get("discount"))
        if discount <= 0:
            continue
        p["discount"] = discount

        if not p.get("image"):
            p["image"] = "/assets/placeholder-product.svg"

        p["score"] = calculate_score(p)
        clean.append(p)
    return clean

def main():
    ali = load_json(BASE / "data" / "aliexpress_products.json")
    deca = load_json(BASE / "data" / "decathlon_products.json")
    amazon = load_json(BASE / "data" / "amazon_products.json")

    ali = clean_products(ali)
    deca = clean_products(deca)
    amazon = clean_products(amazon)

    all_products = ali + deca + amazon
    all_products.sort(key=lambda x: x.get("score", 0), reverse=True)

    with open(BASE / "data" / "generated_deals.json", "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
