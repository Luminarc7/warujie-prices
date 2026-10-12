#!/usr/bin/env python3
"""One-off: which Scryfall Tagger tags exist, how many cards each has, and a
few example cards (to choose the roles for the site's role search)."""
import json, os, time, urllib.parse, urllib.request, urllib.error
H = {"User-Agent": "WarujiePriceHistory/1.1 (+https://github.com/Luminarc7/warujie-prices)", "Accept": "application/json"}
CANDIDATES = """buff-temporary buff-power buff-strength buff-toughness combat-trick gives-hexproof gives-indestructible exchange-control control-changing-effects
fixing hand-disruption discard-hand counterspell-creature counterspell-noncreature hard-counter combat-ping death-trigger-self deathtrigger
token-generator tokens-matter token-creation repeatable-token-generator creates-token-of-a-card makes-creature-tokens
cheat-into-play theft threaten gives-evasion gives-haste hatebear fetchland bounce-land copy-spell clone wheel impulse-draw loot rummage""".split()
out = {}
for slug in CANDIDATES:
    q = f"otag:{slug}"
    url = "https://api.scryfall.com/cards/search?" + urllib.parse.urlencode({"q": q, "unique": "cards", "order": "edhrec"})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60) as r:
            d = json.load(r)
            out[slug] = {"n": d.get("total_cards"), "ex": [c.get("name") for c in d.get("data", [])[:8]], "warn": d.get("warnings")}
    except urllib.error.HTTPError as err:
        try:
            body = json.load(err)
        except Exception:
            body = {}
        out[slug] = {"n": 0, "status": err.code, "details": body.get("details"), "warn": body.get("warnings")}
    time.sleep(0.7)
os.makedirs("tools/probe", exist_ok=True)
json.dump(out, open("tools/probe/tags.json", "w"), indent=1)
