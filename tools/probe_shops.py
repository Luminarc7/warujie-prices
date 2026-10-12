#!/usr/bin/env python3
"""One-off look at the shops' public price lists (Card Kingdom, Mana Pool):
what the records look like and how complete they are. Saves a small summary
in tools/probe/ - nothing is published."""
import collections, gzip, json, os, time, urllib.request

HEADERS = {"User-Agent": "WarujiePriceHistory/1.1 (+https://github.com/Luminarc7/warujie-prices)", "Accept": "application/json"}
WANT = ("Yawgmoth, Thran Physician", "Lightning Bolt", "Ragavan, Nimble Pilferer")


def get(url):
    t = time.time()
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=300) as r:
        raw = r.read()
        info = {"status": r.status, "bytes": len(raw), "type": r.headers.get("Content-Type"), "secs": round(time.time() - t, 1)}
    text = raw.decode("utf-8")
    if text.startswith("<html>"):
        text = text.removeprefix("<html><head></head><body>").removesuffix("</body></html>")
    return json.loads(text), info


out = {}
try:
    data, info = get("https://api.cardkingdom.com/api/v2/pricelist")
    recs = data.get("data") or []
    cond = collections.Counter()
    for r in recs:
        cv = r.get("condition_values") or {}
        cond[tuple(sorted(k for k, v in cv.items() if v not in (None, 0, "0", "0.00")))] += 1
    out["ck_v2"] = {"info": info, "meta": data.get("meta"), "n": len(recs), "keys": sorted({k for r in recs[:500] for k in r}),
                    "first": recs[:3], "wanted": [r for r in recs if r.get("name") in WANT][:40],
                    "condition_keys": [[list(k), n] for k, n in cond.most_common(12)],
                    "with_scryfall": sum(1 for r in recs if r.get("scryfall_id")),
                    "in_stock": sum(1 for r in recs if (r.get("qty_retail") or 0) > 0),
                    "variations": collections.Counter((r.get("variation") or "")[:30] for r in recs).most_common(30)}
except Exception as err:
    out["ck_v2"] = {"error": repr(err)}

for name in ("variants", "singles"):
    try:
        data, info = get(f"https://manapool.com/api/v1/prices/{name}")
        recs = data.get("data") or []
        o = {"info": info, "meta": data.get("meta"), "n": len(recs), "keys": sorted({k for r in recs[:500] for k in r}),
             "first": recs[:3], "wanted": [r for r in recs if r.get("name") in WANT][:60]}
        if name == "variants":
            for f in ("language_id", "condition_id", "finish_id", "product_type"):
                o[f] = collections.Counter(str(r.get(f)) for r in recs).most_common(20)
            o["qty"] = collections.Counter(min(r.get("available_quantity") or 0, 10) for r in recs).most_common()
        out["manapool_" + name] = o
    except Exception as err:
        out["manapool_" + name] = {"error": repr(err)}

os.makedirs("tools/probe", exist_ok=True)
with gzip.open("tools/probe/shops.json.gz", "wt", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print({k: (v.get("n"), v.get("info"), v.get("error")) for k, v in out.items()})
