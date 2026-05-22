import json
import sys
from pathlib import Path


def safe_text(value) -> str:
    return str(value or "").strip()


def identity_key(deal: dict) -> str:
    for field in ("product_detail_path", "id", "product_id", "affiliate_url", "url"):
        value = safe_text(deal.get(field))
        if value:
            return f"{field}:{value.lower()}"

    title = safe_text(deal.get("title")).lower()
    source = safe_text(deal.get("source") or deal.get("source_label")).lower()
    return f"fallback:{title}:{source}"


def quality_value(deal: dict) -> float:
    raw = deal.get("quality_score")
    try:
        return float(raw)
    except Exception:
        return -1.0


def main() -> int:
    path = Path("data/generated_deals.json")
    if not path.exists():
        print("ERROR: data/generated_deals.json no existe")
        return 1

    try:
        deals = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: no se pudo leer generated_deals.json: {exc}")
        return 1

    if not isinstance(deals, list):
        print("ERROR: generated_deals.json no contiene una lista")
        return 1

    errors = []
    seen = {}

    for idx, deal in enumerate(deals):
        if not isinstance(deal, dict):
            errors.append(f"Entrada no valida en indice {idx}")
            continue

        key = identity_key(deal)
        if key in seen:
            errors.append(f"Duplicado por identidad: indice {seen[key]} y {idx} ({key})")
        else:
            seen[key] = idx

        q = quality_value(deal)
        if q < 0 or q > 100:
            errors.append(f"quality_score invalido en indice {idx}: {deal.get('quality_score')}")

        reasons = deal.get("quality_reasons")
        if not isinstance(reasons, list):
            errors.append(f"quality_reasons no es lista en indice {idx}")

    sorted_deals = sorted(
        deals,
        key=lambda d: (
            quality_value(d),
            float(d.get("chollometer_score") or 0),
            float(d.get("discount_pct") or 0),
        ),
        reverse=True,
    )

    top = sorted_deals[:3]
    top_keys = {identity_key(d) for d in top}
    rest = sorted_deals[3:63]
    overlap = [identity_key(d) for d in rest if identity_key(d) in top_keys]
    if overlap:
        errors.append("Solapamiento detectado entre Top y listado principal")

    if errors:
        print("ERROR: validacion de generated_deals fallida")
        for err in errors:
            print(f"- {err}")
        return 1

    premium = sum(1 for d in deals if bool(d.get("is_premium_quality")))
    avg_quality = round(sum(quality_value(d) for d in deals) / len(deals), 2) if deals else 0
    print("OK: validacion de generated_deals")
    print(f"- total: {len(deals)}")
    print(f"- premium: {premium}")
    print(f"- avg quality: {avg_quality}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
