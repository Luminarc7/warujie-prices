#!/usr/bin/env python3
"""One-off check of the published shop data: the size of every q/ file, and a
few cards' files and Scryfall records saved in tools/sample/ for a look."""
import gzip, json, os, time, urllib.request

BASE = "https://luminarc7.github.io/warujie-prices/"
HEADERS = {"User-Agent": "WarujiePriceHistory/1.1 (+https://github.com/Luminarc7/warujie-prices)", "Accept": "application/json"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120) as r:
        return r.read()


os.makedirs("tools/sample", exist_ok=True)
index = json.loads(get(BASE + "index.json"))
sizes = {}
for key in index.get("shards") or []:
    raw = get(BASE + f"q/{key}.json.gz?d={index.get('quotes_date', '')}")
    data = json.loads(gzip.decompress(raw))
    sizes[key] = [len(raw), len(data.get("p", {})), len(data.get("l", {})), len(data.get("lk", {}))]
cards = {}
for path in ("dmr/110", "dmr/110/ja", "mh1/116", "mh1/116/ja", "tsr/336", "mh2/138", "mh2/138/ja", "2xm/129", "m10/146"):
    try:
        c = json.loads(get("https://api.scryfall.com/cards/" + path))
        cards[path] = c
        time.sleep(0.15)
    except Exception as err:
        cards[path] = {"error": repr(err)}
keys = sorted({c["id"][:2] for c in cards.values() if c.get("id")})
for key in keys:
    with open(f"tools/sample/q_{key}.json.gz", "wb") as fh:
        fh.write(get(BASE + f"q/{key}.json.gz?d={index.get('quotes_date', '')}"))
json.dump({"index": index, "sizes": sizes, "total_bytes": sum(v[0] for v in sizes.values())}, open("tools/sample/summary.json", "w"), indent=1)
json.dump(cards, open("tools/sample/cards.json", "w"), ensure_ascii=False)
print("total", sum(v[0] for v in sizes.values()), "bytes in", len(sizes), "files")
