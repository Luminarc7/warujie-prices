#!/usr/bin/env python3
"""One-off check of the published offers: CardTrader rows and a few cards' files."""
import collections, gzip, json, os, urllib.request
BASE = "https://luminarc7.github.io/warujie-prices/"
H = {"User-Agent": "WarujiePriceHistory/1.1 (+https://github.com/Luminarc7/warujie-prices)"}
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=120).read()
index = json.loads(get(BASE + "index.json"))
os.makedirs("tools/sample", exist_ok=True)
stats = collections.Counter(); countries = collections.Counter(); langs = collections.Counter()
for key in index["shards"]:
    raw = get(BASE + f"q/{key}.json.gz?d={index['quotes_date']}-ct")
    d = json.loads(gzip.decompress(raw))
    stats["bytes"] += len(raw)
    for sid, rows in d.get("l", {}).items():
        ct = [r for r in rows if r[0] == "ct"]
        if ct:
            stats["printings_ct"] += 1
            stats["rows_ct"] += len(ct)
            for r in ct:
                countries[r[6]] += 1; langs[r[5]] += 1
    if key in ("b5", "86", "08", "a9"):
        open(f"tools/sample/q_{key}.json.gz", "wb").write(raw)
json.dump({"stats": stats, "countries": countries.most_common(), "langs": langs.most_common(), "offers": index.get("offers")}, open("tools/sample/summary.json", "w"), indent=1)
