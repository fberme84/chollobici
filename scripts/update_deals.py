import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"data/decathlon_products.json"
o=ROOT/"data/generated_deals.json"
data=json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
o.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
print("Deals:",len(data))
