#!/usr/bin/env python3
"""One-off: which Scryfall Tagger tags exist, how many cards each has, and a
few example cards (to choose the roles for the site's role search)."""
import json, os, time, urllib.parse, urllib.request, urllib.error
H = {"User-Agent": "WarujiePriceHistory/1.1 (+https://github.com/Luminarc7/warujie-prices)", "Accept": "application/json"}
CANDIDATES = """creates-token creates-tokens create-tokens token-creator token-generation token-producer makes-tokens synergy-token token-maker-creature
buff-power buff-strength buff-temporary pump-spell combat-trick power-pump
control-steal steal-permanent control-change gain-control-of mind-control control-magic theft
stone-rain mass-land-destruction land-destruction-mass
etb etb-effect enters-trigger etb-trigger-self ltb ltb-trigger leaves-trigger
discard-opponent targeted-discard hand-attack discard-target opponent-discard
mill-opponent mill-target mill-player
lifegain-matters gain-life-matters
counter-creature counterspell-creature counterspell-noncreature
mana-sink cost-reduction treasure synergy-treasure food clue
wrath-creature boardwipe-creature boardwipe-nonland
banish banish-creature exile-removal doomblade
pinger ping
mana-fixing fixing land-fetch
alternate-win-condition win-condition wincon
graveyard-recursion recursion-artifact recursion-land
reanimate-creature reanimate-self
protection-creature hexproof-granter gives-hexproof gives-indestructible
flash-enabler gives-flash
copy-permanent token-copy
removal-exile removal-destroy removal-bounce removal-damage removal-sacrifice removal-minus""".split()
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
    time.sleep(0.12)
os.makedirs("tools/probe", exist_ok=True)
json.dump(out, open("tools/probe/tags.json", "w"), indent=1)
