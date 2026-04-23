import json
from pathlib import Path

DATA_DIR = Path("data")
DECATHLON_PATH = DATA_DIR / "decathlon_products.json"
ALIEXPRESS_PATH = DATA_DIR / "aliexpress_products.json"
OUTPUT_PATH = DATA_DIR / "generated_deals.json"


def safe_float(x):
    try:
        return float(x)
    except:
        return 0


def compute_discount_pct(p):
    price = safe_float(p.get("price"))
    old = safe_float(p.get("old_price"))

    if old > 0 and price > 0 and price <= old:
        return round((old - price) / old * 100)
    return 0


# 🔥 FILTRO DECATHLON CORREGIDO
def passes_decathlon_filter(product: dict) -> bool:
    title = (product.get("title") or "").lower()
    text = f" {title} "

    price = safe_float(product.get("price"))
    if not price:
        return False

    # ❌ evitar gama alta absurda
    premium_terms = ["carbon", "cf", "sl", "pro", "racing", "team", "ultra", "factory"]
    if any(term in text for term in premium_terms):
        return False

    is_bike = any(term in text for term in [
        "bici", "bicicleta", "mtb", "gravel", "carretera",
        "rockrider", "triban", "van rysel"
    ])

    # 🚴 bicis
    if is_bike:
        return price <= 1500

    # 🎒 resto
    return price <= 300


def load_json(path):
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except:
        return []


def main():
    decathlon = load_json(DECATHLON_PATH)
    aliexpress = load_json(ALIEXPRESS_PATH)

    print(f"Decathlon leídos: {len(decathlon)}")
    print(f"AliExpress leídos: {len(aliexpress)}")

    # 🔧 aplicar filtro Decathlon
    decathlon_filtered = [
        p for p in decathlon if passes_decathlon_filter(p)
    ]

    print(f"Decathlon tras filtro: {len(decathlon_filtered)}")

    # combinar
    deals = decathlon_filtered + aliexpress

    # ordenar por "recomendación"
    deals.sort(
        key=lambda x: (
            compute_discount_pct(x),
            safe_float(x.get("price"))
        ),
        reverse=True
    )

    # limitar tamaño
    deals = deals[:40]

    print(f"TOTAL DEALS FINAL: {len(deals)}")

    OUTPUT_PATH.write_text(
        json.dumps(deals, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


if __name__ == "__main__":
    main()