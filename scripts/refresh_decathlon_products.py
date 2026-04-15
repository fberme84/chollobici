import os,time,json,requests
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"data/decathlon_products.json"
DEBUG=ROOT/"data/debug_decathlon_raw.txt"
URL=os.getenv("DECATHLON_FEED_URL","")

def log(x):print(x,flush=True)

def fetch():
    log(f"[INFO] URL configurada: {'sí' if URL else 'no'}")
    if not URL:return None
    for i in range(3):
        try:
            r=requests.get(URL,timeout=(20,120))
            log(f"[INFO] Status {r.status_code}")
            log(f"[INFO] Bytes {len(r.text)}")
            DEBUG.write_text(r.text,encoding="utf-8")
            if r.status_code==200 and len(r.text)>1000:return r.text
        except Exception as e:log(e)
        time.sleep(10*(i+1))
    return None

def parse(t):
    if not t:return []
    rows=t.split("\n")
    prods=[{"title":r[:100],"source":"decathlon"} for r in rows if "bici" in r.lower() or "ciclismo" in r.lower()]
    return prods

def main():
    raw=fetch()
    if not raw:return
    p=parse(raw)
    tmp=OUTPUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(OUTPUT)
    log(f"Productos Decathlon: {len(p)}")

if __name__=="__main__":main()
