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
        return None

    for attempt in range(3):
        try:
            log(f"[INFO] Intento {attempt+1} de descarga Decathlon...")
            resp = requests.get(FEED_URL, timeout=(20, 120))

            log(f"[INFO] Status code Decathlon: {resp.status_code}")
            log(f"[INFO] Content-Type Decathlon: {resp.headers.get('Content-Type')}")
            log(f"[INFO] Bytes recibidos Decathlon: {len(resp.text)}")

            sample = resp.text[:500].replace("\n", " ").replace("\r", " ")
            log(f"[INFO] Muestra respuesta Decathlon: {sample}")

            # guardar debug siempre
            DEBUG_RAW_PATH.write_text(resp.text, encoding="utf-8")

            if resp.status_code == 200 and len(resp.text) > 1000:
                return resp.text
            else:
                log("[WARN] Respuesta sospechosa, reintentando...")

        except Exception as e:
            log(f"[ERROR] Error descargando Decathlon: {e}")

        time.sleep(10 * (attempt + 1))

    return None


def parse_feed(raw_text):
    log("[INFO] Inicio parseo feed Decathlon")

    if not raw_text:
        log("[WARN] Texto vacío, no se puede parsear")
        return []

    # aquí deberías tener tu parser real
    # de momento simulamos detección básica
    records = raw_text.split("http")
    log(f"[INFO] Registros candidatos Decathlon detectados: {len(records)}")

    products = []

    for r in records:
        if "bici" in r.lower() or "ciclismo" in r.lower():
            products.append({
                "title": r[:80],
                "source": "decathlon"
            })

    log(f"[INFO] Registros Decathlon ciclismo tras filtrar: {len(products)}")

    return products


def save_products(products):
    tmp_path = OUTPUT_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(OUTPUT_PATH)


def main():
    raw = fetch_feed()

    if not raw:
        log("[WARN] No se ha podido obtener feed Decathlon. Se mantiene catálogo anterior si existe.")
        return

    products = parse_feed(raw)

    if not products:
        log("[WARN] Decathlon ha devuelto 0 productos tras parseo")

    save_products(products)

    # FIX aplicado aquí 👇
    excluded_count = len([p for p in products if p.get("catalog_excluded")])
    log(f"Productos Decathlon excluidos por redirección/listing: {excluded_count}")

    log(f"Productos Decathlon ciclismo guardados: {len(products)}")


if __name__ == "__main__":
    main()