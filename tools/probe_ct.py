#!/usr/bin/env python3
"""One-off check of the CardTrader API with the repository's token: what the
answers look like (sellers' names left out). Saves tools/probe/ct.json."""
import collections, json, os, time, urllib.request, urllib.error

TOKEN = os.environ.get("CARDTRADER_TOKEN", "").strip()
BASE = "https://api.cardtrader.com/api/v2/"
out = {"token_set": bool(TOKEN)}


def get(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + TOKEN, "Accept": "application/json",
                                                        "User-Agent": "WarujiePriceHistory/1.1 (+https://github.com/Luminarc7/warujie-prices)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", "replace")[:500]


s, info = get("info"); out["info"] = [s, {k: v for k, v in (info.items() if isinstance(info, dict) else []) if k not in ("email",)} if isinstance(info, dict) else info]
s, exps = get("expansions"); out["expansions_status"] = s
mtg = [e for e in exps if isinstance(e, dict) and e.get("game_id") == 1] if isinstance(exps, list) else []
out["expansions"] = {"all": len(exps) if isinstance(exps, list) else exps, "magic": len(mtg), "sample": mtg[:3],
                     "mh2": [e for e in mtg if e.get("code") in ("mh2", "dmr", "mh1")]}
for e in out["expansions"]["mh2"][:2]:
    s, bps = get(f"blueprints/export?expansion_id={e['id']}")
    out.setdefault("blueprints", {})[e["code"]] = [s, len(bps) if isinstance(bps, list) else bps,
                                                   [{k: b.get(k) for k in ("id", "name", "scryfall_id", "category_id", "version")} for b in (bps[:3] if isinstance(bps, list) else [])],
                                                   sum(1 for b in bps if isinstance(b, dict) and b.get("scryfall_id")) if isinstance(bps, list) else None]
    time.sleep(1.1)
    s, prods = get(f"marketplace/products?expansion_id={e['id']}&foil=false")
    if isinstance(prods, dict):
        allp = [p for v in prods.values() for p in v]
        out.setdefault("products", {})[e["code"]] = {
            "status": s, "blueprints": len(prods), "products": len(allp),
            "currencies": collections.Counter(str((p.get("price") or {}).get("currency")) for p in allp).most_common(),
            "countries": collections.Counter(str((p.get("user") or {}).get("country_code")) for p in allp).most_common(15),
            "conditions": collections.Counter(str((p.get("properties_hash") or {}).get("condition")) for p in allp).most_common(),
            "languages": collections.Counter(str((p.get("properties_hash") or {}).get("mtg_language")) for p in allp).most_common(),
            "keys": sorted({k for p in allp[:50] for k in p}), "prop_keys": sorted({k for p in allp[:50] for k in (p.get("properties_hash") or {})}),
            "sample": [{k: v for k, v in p.items() if k != "user"} | {"user_country": (p.get("user") or {}).get("country_code")} for p in allp[:3]]}
    else:
        out.setdefault("products", {})[e["code"]] = [s, prods]
    time.sleep(1.1)
os.makedirs("tools/probe", exist_ok=True)
json.dump(out, open("tools/probe/ct.json", "w"), ensure_ascii=False, indent=1)
print("saved")
