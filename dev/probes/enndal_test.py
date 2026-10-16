"""One-off test night: read two ENNDAL GAMES sets (in stock only) with
shop_enndal.read_shop and match every product to a Scryfall printing.

Writes probe_out/enndal_match.txt: counts, the match rate per set, and the
products that matched nothing (set, number, English name). No prices are
written, so nothing of the shop's is republished.
"""
import collections, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import build_prices as bp
import shop_enndal as en

# Bloomburrow (2363) was read on 2026-10-17 and all 670 matched; MH3 read
# nothing because its codes end in "_", so it is read again after the fix.
CATEGORIES = [2333]                # Modern Horizons 3
OUT = "probe_out/enndal_match.txt"
os.makedirs("probe_out", exist_ok=True)

def key_number(n):
    return n.lower().lstrip("0") or "0"

print("Reading Scryfall's default_cards...")
by_num, by_name = {}, {}
for c in bp.iter_cards(bp.bulk_url()):
    s = c.get("set", "")
    by_num[(s, key_number(c.get("collector_number", "")))] = c
    by_name.setdefault((s, c.get("name", "").split(" // ")[0].lower()), []).append(c)
print(f"  {len(by_num)} printings")

t0 = time.monotonic()
products, done = en.read_shop(CATEGORIES, minutes=30)
pages_secs = time.monotonic() - t0

stats = collections.Counter()
per_set = collections.defaultdict(collections.Counter)
misses = []
for p in products:
    stats["products"] += 1
    stats["offers"] += len(p["offers"])
    stats["finish:" + p["finish"]] += 1
    card = by_num.get((p["set"], key_number(p["number"])))
    how = "number"
    if card and card.get("name", "").split(" // ")[0].lower() != p["name_en"].lower():
        how = "number, name differs"
    if not card:
        cands = by_name.get((p["set"], p["name_en"].lower())) or []
        card = cands[0] if len(cands) == 1 else None
        how = "name"
    if card:
        stats["matched by " + how] += 1
        per_set[p["set"]]["ok"] += 1
    else:
        per_set[p["set"]]["miss"] += 1
        misses.append((p["set"], p["number"], p["finish"], p["name_en"]))

with open(OUT, "w") as f:
    f.write(f"categories read: {done} of {CATEGORIES}; {pages_secs/60:.1f} minutes\n")
    for k, v in sorted(stats.items()):
        f.write(f"{k}: {v}\n")
    for s, c in sorted(per_set.items()):
        f.write(f"set {s}: {c['ok']} matched, {c['miss']} not\n")
    f.write("\nnot matched:\n")
    for m in misses:
        f.write("  %s %s %s %s\n" % m)
print(open(OUT).read())
