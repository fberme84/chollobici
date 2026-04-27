
import json, os
from datetime import datetime

HISTORY_FILE = "data/decathlon_price_history.json"
PRODUCTS_FILE = "data/decathlon_products.json"

today = datetime.utcnow().strftime("%Y-%m-%d")

with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
    products = json.load(f)

if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
else:
    history = {}

for p in products:
    pid = str(p.get("id") or p.get("url"))
    price = p.get("price")
    if not price:
        continue
    try:
        price = float(str(price).replace("€","").replace(",","."))
    except:
        continue

    if pid not in history:
        history[pid] = {"history":[]}

    h = history[pid]["history"]
    if h and h[-1]["date"] == today:
        continue

    h.append({"date":today,"price":price})
    history[pid]["history"] = h[-60:]

with open(HISTORY_FILE,"w",encoding="utf-8") as f:
    json.dump(history,f,indent=2)
