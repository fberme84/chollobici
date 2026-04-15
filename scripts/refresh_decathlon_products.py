import os
import time
import json
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "decathlon_products.json"
DEBUG_RAW_PATH = ROOT / "data" / "debug_decathlon_raw.txt"

FEED_URL = os.getenv("DECATHLON_FEED_URL", "")


def log(msg):
    print(msg, flush=True)


def fetch_feed():
    log(f"[INFO] DECATHLON_FEED_URL configurado: {'sí' if FEED_URL else 'no'}")

    if not FEED_URL:
        log("[WARN] No hay URL de Decathlon")
        return None

    for attempt in range(3):
        try:
            log(f"[INFO] Intento {attempt+1} descarga Decathlon")

            resp = requests.get(FEED_URL, timeout=(20, 120))

            log(f"[INFO] Status code: {resp.status_code}")
            log(f"[INFO] Content-Type: {resp.headers.get('Content-Type')}")
            log(f"[INFO] Bytes recibidos: {len(resp.text)}")

            # 🔥 ASEGURAR CARPETA DATA
            DEBUG_RAW_PATH.parent.mkdir(parents=True, exist_ok=True)

            # 🔥 GUARDAR SIEMPRE RESPUESTA (aunque sea mala)
            DEBUG_RAW_PATH.write_text(resp.text, encoding="utf-8")

            sample = resp.text[:500].replace("\n", " ").replace("\r", " ")
            log(f"[INFO] Muestra: {sample}")

            if resp.status_code == 200 and len(resp.text) > 1000:
                log("[INFO] Feed válido recibido")
                return resp.text
            else:
                log("[WARN] Respuesta sospechosa, reintentando...")

        except Exception as e:
            log(f"[ERROR] Error descargando Decathlon: {e}")

        time.sleep(10 * (attempt + 1))

    log("[ERROR] No se pudo obtener feed válido de Decathlon")
    return None


def parse_feed(raw_text):
    log("[INFO] Inicio parseo feed Decathlon")

    if not raw_text:
        log("[WARN] Texto vacío, no se puede parsear")
        return []

    records = raw_text.split("\n")
    log(f"[INFO] Registros candidatos: {len(records)}")

    products = []

    for r in records:
        if "ciclismo" in r.lower() or "bici" in r.lower():
            products.append({
                "title": r[:100],
                "source": "decathlon"
            })

    log(f"[INFO] Registros ciclismo: {len(products)}")

    return products


def save_products(products):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = OUTPUT_PATH.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(products, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    tmp_path.replace(OUTPUT_PATH)


def main():
    raw = fetch_feed()

    if not raw:
        log("[WARN] No se ha podido obtener feed Decathlon")
        return

    products = parse_feed(raw)

    excluded_count = len([p for p in products if p.get("catalog_excluded")])
    log(f"Productos Decathlon excluidos por redirección/listing: {excluded_count}")

    save_products(products)

    log(f"Productos Decathlon ciclismo guardados: {len(products)}")


if __name__ == "__main__":
    main()