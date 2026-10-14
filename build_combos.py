#!/usr/bin/env python3
"""
build_combos.py - Commander combo data for the 悪知恵 (warujie) card pages.

WHERE THE COMBOS COME FROM
--------------------------
Commander Spellbook (https://commanderspellbook.com/), the community combo
database. It publishes every combo as one bulk file and asks other sites to
download that file on a schedule of their own instead of calling its API from
each visitor's browser - which is what this script does, about once a week.
The site credits Commander Spellbook and links every combo back to its page.

WHAT IS WRITTEN
---------------
A folder (normally site/c/) with
    index.json      when the data was built, from which file, and the shards
    xx.json.gz      the combos of the cards whose oracle id starts with "xx"
Each card keeps its most played combos (up to --per-card); the total number
is kept too, so the site can link to the rest on Commander Spellbook.

Between rebuilds the published files are copied over from --previous, so the
big download happens only when the data is older than --max-age days.

USAGE
-----
    python3 build_combos.py --out site/c --previous https://<user>.github.io/warujie-prices/
Options: --source FILE (a variants.json(.gz) already downloaded), --force.
"""

import argparse
import datetime
import gzip
import io
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request

BULK_URL = os.environ.get("WARUJIE_COMBOS_URL", "https://json.commanderspellbook.com/variants.json.gz")
HEADERS = {"User-Agent": "WarujieComboBuilder/2.0 (+https://github.com/warujie/warujie-prices)", "Accept": "application/json"}
FORMAT_BITS = ["standard", "pioneer", "modern", "legacy", "vintage", "premodern", "commander", "pauper"]
FIELDS = ["id", "identity", "cards", "templates", "results", "mana", "popularity", "legal", "prerequisites", "steps"]
MAX_TEXT = 1500       # longest prerequisites / steps text kept per combo
PER_CARD = 40         # combos kept per card (most played first)
MAX_AGE_DAYS = 7      # rebuild from the bulk file when the published data is older than this


def log(msg=""):
    print(msg, flush=True)


def pick(obj, *names, default=None):
    """First present key - the bulk file uses camelCase, older exports snake_case."""
    for name in names:
        if isinstance(obj, dict) and name in obj and obj[name] is not None:
            return obj[name]
    return default


def http_get(url, tries=4):
    last = None
    for attempt in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120)
        except urllib.error.HTTPError as err:
            if err.code == 404:
                raise
            last = err
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            last = err
        time.sleep(5 * (attempt + 1))
    raise last


def load_published(base, rel):
    """A published file (URL or folder) as bytes; None if it isn't there."""
    if not base:
        return None
    if base.startswith(("http://", "https://")):
        try:
            with http_get(base.rstrip("/") + "/" + rel) as resp:
                return resp.read()
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return None
            raise
    path = os.path.join(base, rel)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return fh.read()


def download(url, dest):
    log("Downloading Commander Spellbook's combo file...")
    with http_get(url) as resp, open(dest, "wb") as out:
        done, last = 0, time.time()
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if time.time() - last > 10:
                last = time.time()
                log(f"  ...{done / 1e6:,.0f} MB")
    log(f"  {os.path.getsize(dest) / 1e6:,.1f} MB")


def open_text(path):
    f = open(path, "rb")
    magic = f.read(2)
    f.seek(0)
    if magic == b"\x1f\x8b":
        return io.TextIOWrapper(gzip.GzipFile(fileobj=f), encoding="utf-8")
    return io.TextIOWrapper(f, encoding="utf-8")


def iter_array(stream, key, chunk_size=1 << 20):
    """The objects of the array under `key` in a big JSON document, one at a
    time, without loading the whole document."""
    decoder = json.JSONDecoder()
    needle = '"%s"' % key
    buf = ""
    while True:
        i = buf.find(needle)
        if i >= 0:
            j = buf.find("[", i + len(needle))
            if j >= 0:
                buf = buf[j + 1:]
                break
            more = stream.read(chunk_size)
            if not more:
                return
            buf += more
            continue
        more = stream.read(chunk_size)
        if not more:
            return
        buf = buf[-len(needle):] + more
    pos = 0
    while True:
        while True:
            while pos < len(buf) and buf[pos] in " \t\r\n,":
                pos += 1
            if pos < len(buf):
                break
            more = stream.read(chunk_size)
            if not more:
                return
            buf, pos = more, 0
        if buf[pos] == "]":
            return
        try:
            obj, end = decoder.raw_decode(buf, pos)
        except ValueError:
            more = stream.read(chunk_size)
            if not more:
                raise ValueError("the combo file ends in the middle of a record (download cut short?)")
            buf, pos = buf[pos:] + more, 0
            continue
        yield obj
        pos = end
        if pos > (1 << 22):
            buf, pos = buf[pos:], 0


def read_timestamp(path, limit=4096):
    with open_text(path) as f:
        head = f.read(limit)
    i = head.find('"timestamp"')
    if i < 0:
        return ""
    try:
        value, _ = json.JSONDecoder().raw_decode(head[i + len('"timestamp"'):].lstrip(" :"))
        return str(value)
    except ValueError:
        return ""


def clean_text(text):
    text = (text or "").replace("\r\n", "\n").strip()
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT].rsplit("\n", 1)[0] + "\n…"
    return text


def read_combos(path):
    """All usable combos: (rows, card table [name, oracle], result names)."""
    cards, card_index = [], {}
    results, result_index = [], {}
    rows = []
    seen = 0

    def card_ref(card):
        name = pick(card, "name", default="")
        oracle = pick(card, "oracleId", "oracle_id", default="") or ""
        key = oracle or name
        if key not in card_index:
            card_index[key] = len(cards)
            cards.append([name, oracle])
        return card_index[key]

    def result_ref(name):
        if name not in result_index:
            result_index[name] = len(results)
            results.append(name)
        return result_index[name]

    with open_text(path) as stream:
        for variant in iter_array(stream, "variants"):
            seen += 1
            if seen % 20000 == 0:
                log(f"  ...read {seen:,} combos")
            if not isinstance(variant, dict) or pick(variant, "status", default="OK") not in ("OK", "E"):
                continue
            used = []
            for u in pick(variant, "uses", default=[]) or []:
                card = pick(u, "card", default={}) or {}
                if not pick(card, "name"):
                    continue
                zones = "".join(pick(u, "zoneLocations", "zone_locations", default=[]) or [])
                used.append([card_ref(card), int(pick(u, "quantity", default=1) or 1), zones])
            if not used:
                continue
            templates = []
            for r in pick(variant, "requires", default=[]) or []:
                name = pick(pick(r, "template", default={}) or {}, "name")
                if name:
                    qty = int(pick(r, "quantity", default=1) or 1)
                    templates.append(f"{qty}x {name}" if qty > 1 else name)
            produced = []
            for p in pick(variant, "produces", default=[]) or []:
                feature = pick(p, "feature", default={}) or {}
                name = pick(feature, "name")
                if not name or name.lower() == "lock" or pick(feature, "status") in ("HU", "PU"):
                    continue
                qty = int(pick(p, "quantity", default=1) or 1)
                produced.append(result_ref(f"{qty} {name}" if qty > 1 else name))
            legal = pick(variant, "legalities", default={}) or {}
            prerequisites = "\n".join(t for t in (
                clean_text(pick(variant, "notablePrerequisites", "notable_prerequisites", default="")),
                clean_text(pick(variant, "easyPrerequisites", "easy_prerequisites", default="")),
            ) if t)
            rows.append([
                str(pick(variant, "id", default="")),
                str(pick(variant, "identity", default="C") or "C").upper(),
                used, templates, produced,
                pick(variant, "manaNeeded", "mana_needed", default="") or "",
                int(pick(variant, "popularity", default=0) or 0),
                sum(1 << i for i, fmt in enumerate(FORMAT_BITS) if legal.get(fmt)),
                prerequisites,
                clean_text(pick(variant, "description", default="")),
            ])
    if not seen:
        raise ValueError("no combos in the file - its layout may have changed")
    return rows, cards, results, seen


def shard_data(rows, cards, results, per_card):
    """{shard key: payload}: each card's most played combos, grouped by the
    first two characters of the card's oracle id."""
    by_card = {}
    for idx, row in enumerate(rows):
        for ref, _, _ in row[2]:
            oracle = cards[ref][1]
            if oracle:
                lst = by_card.setdefault(oracle, [])
                if not lst or lst[-1] != idx:
                    lst.append(idx)
    shards = {}
    for oracle, idxs in by_card.items():
        idxs.sort(key=lambda i: (-rows[i][6], rows[i][0]))
        shards.setdefault(oracle[:2].lower(), {})[oracle] = (idxs[:per_card], len(idxs))
    out = {}
    for key, members in shards.items():
        local_rows, row_pos = [], {}
        local_cards, card_pos = [], {}
        local_results, result_pos = [], {}
        by, total = {}, {}
        for oracle, (idxs, n) in sorted(members.items()):
            mine = []
            for i in idxs:
                if i not in row_pos:
                    r = list(rows[i])
                    used = []
                    for ref, qty, zones in r[2]:
                        if ref not in card_pos:
                            card_pos[ref] = len(local_cards)
                            local_cards.append(cards[ref])
                        used.append([card_pos[ref], qty, zones])
                    r[2] = used
                    res = []
                    for ref in r[4]:
                        if ref not in result_pos:
                            result_pos[ref] = len(local_results)
                            local_results.append(results[ref])
                        res.append(result_pos[ref])
                    r[4] = res
                    row_pos[i] = len(local_rows)
                    local_rows.append(r)
                mine.append(row_pos[i])
            by[oracle] = mine
            total[oracle] = n
        out[key] = {"fields": FIELDS, "formats": FORMAT_BITS, "cards": local_cards, "results": local_results,
                    "combos": local_rows, "by": by, "total": total}
    return out, len(by_card)


def write_gz(path, obj):
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, compresslevel=9) as gz:
            gz.write(payload)
    return os.path.getsize(path)


def copy_previous(previous, out, index):
    """Writes the published shards again; False if any is missing."""
    shards = index.get("shards") or []
    if not shards:
        return False
    files = {}
    for key in shards:
        raw = load_published(previous, f"c/{key}.json.gz")
        if raw is None:
            return False
        files[key] = raw
    os.makedirs(out, exist_ok=True)
    for key, raw in files.items():
        with open(os.path.join(out, f"{key}.json.gz"), "wb") as fh:
            fh.write(raw)
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, separators=(",", ":"))
    return True


def main():
    ap = argparse.ArgumentParser(description="Commander combo data for the warujie card pages.")
    ap.add_argument("--out", required=True, help="folder to write (e.g. site/c)")
    ap.add_argument("--previous", default="", help="URL or folder of the published site (its c/ folder is reused)")
    ap.add_argument("--source", default="", help="a variants.json(.gz) already downloaded")
    ap.add_argument("--force", action="store_true", help="rebuild even if the published data is recent")
    ap.add_argument("--max-age", type=int, default=MAX_AGE_DAYS)
    ap.add_argument("--per-card", type=int, default=PER_CARD)
    ap.add_argument("--today", default="", help=argparse.SUPPRESS)
    args = ap.parse_args()
    today = datetime.date.fromisoformat(args.today) if args.today else datetime.datetime.now(datetime.timezone.utc).date()

    previous_index = None
    try:
        raw = load_published(args.previous, "c/index.json")
        previous_index = json.loads(raw) if raw else None
    except Exception as err:
        log(f"  note: the published combo data could not be read ({err})")
    if previous_index and not args.force and not args.source:
        built = (previous_index.get("generated") or "")[:10]
        try:
            age = (today - datetime.date.fromisoformat(built)).days
        except ValueError:
            age = None
        if age is not None and 0 <= age < args.max_age:
            if copy_previous(args.previous, args.out, previous_index):
                log(f"Combo data from {built} is recent - published again unchanged.")
                return 0
            log("  note: the published combo files are incomplete - rebuilding.")

    try:
        source = args.source
        tmp = None
        if not source:
            tmp = tempfile.mkdtemp(prefix="combos_")
            source = os.path.join(tmp, "variants.json.gz")
            download(BULK_URL, source)
        log("Reading combos...")
        rows, cards, results, seen = read_combos(source)
        shards, n_cards = shard_data(rows, cards, results, args.per_card)
        if not shards:
            raise ValueError("no combos could be used")
        os.makedirs(args.out, exist_ok=True)
        size = sum(write_gz(os.path.join(args.out, f"{key}.json.gz"), data) for key, data in shards.items())
        index = {
            "version": 2,
            "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if not args.today else f"{today.isoformat()}T00:00:00Z",
            "source": {"name": "Commander Spellbook", "url": "https://commanderspellbook.com/", "timestamp": read_timestamp(source)},
            "combos": len(rows), "cards": n_cards, "per_card": args.per_card,
            "shards": sorted(shards),
        }
        with open(os.path.join(args.out, "index.json"), "w", encoding="utf-8") as fh:
            json.dump(index, fh, ensure_ascii=False, separators=(",", ":"))
        log(f"Read {seen:,} combos; kept {len(rows):,} for {n_cards:,} cards in {len(shards)} files ({size / 1e6:.1f} MB).")
        return 0
    except Exception as err:   # the price update must not fail because of the combos
        log(f"  note: combos could not be rebuilt ({err}).")
        if previous_index and copy_previous(args.previous, args.out, previous_index):
            log("  the previously published combo data is kept.")
        else:
            log("  no combo data this time.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
