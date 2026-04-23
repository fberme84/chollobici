
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

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
        if not p.get("price"):
            continue
        if p.get("discount", 0) <= 0:
            continue

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

    out_path = BASE / "data" / "generated_deals.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)

    summary = {
        "total": len(all_products),
        "ali": len(ali),
        "decathlon": len(deca),
        "amazon": len(amazon)
    }

    with open(BASE / "data" / "merge_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

if __name__ == "__main__":
    main()
