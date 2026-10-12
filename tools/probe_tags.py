#!/usr/bin/env python3
"""One-off: which Scryfall Tagger tags exist, how many cards each has, and a
few example cards (to choose the roles for the site's role search)."""
import json, os, time, urllib.parse, urllib.request, urllib.error
H = {"User-Agent": "WarujiePriceHistory/1.1 (+https://github.com/Luminarc7/warujie-prices)", "Accept": "application/json"}
CANDIDATES = """removal creature-removal artifact-removal enchantment-removal planeswalker-removal land-removal removal-creature removal-artifact
removal-enchantment removal-planeswalker removal-land removal-any removal-permanent spot-removal hard-removal soft-removal
boardwipe sweeper wrath board-wipe mass-removal creature-sweeper counterspell soft-counter hard-counter
draw card-draw draw-card card-advantage cantrip wheel impulse impulse-draw loot looter rummage rummager
ramp mana-ramp land-ramp mana-dork mana-rock mana-producer mana-ramp-land adds-multiple-mana cost-reducer mana-doubler
tutor tutor-land tutor-creature tutor-artifact tutor-enchantment tutor-instant tutor-sorcery tutor-any land-tutor
graveyard-hate reanimate reanimation reanimator creature-reanimation recursion regrowth recursion-creature
blink flicker flicker-creature sacrifice-outlet sac-outlet free-sac-outlet free-sacrifice-outlet
discard hand-disruption discard-outlet burn burn-any burn-creature burn-player lifegain gain-life life-gain
token-generator tokens create-token creature-token-generator token-maker treasure-maker makes-treasure
pump anthem lord evasion gives-evasion clone copy copy-spell edict forced-sacrifice mill self-mill
drain drain-life land-destruction bounce tapper untapper extra-turn extra-combat-phase threaten steal gain-control
protection gives-protection fog hatebear stax haste-enabler gives-haste scry surveil proliferate
counter-placement plus-one-counters synergy-sacrifice aristocrats death-trigger etb-trigger cast-trigger
cheat-into-play put-onto-battlefield cast-from-graveyard flashback-granter bounce-land fetchland
land-tutor damage-prevention lifelink gives-lifelink deathtouch-granter""".split()
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
