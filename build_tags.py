#!/usr/bin/env python3
"""
build_tags.py - what each card does, for 悪知恵's role search

Players search by role: 除去 (removal), ドロー (card draw), サーチ (tutors),
マナ加速 (ramp)... Scryfall's Tagger (https://tagger.scryfall.com) is a
community-made list of exactly that, and its "oracle tags" can be searched
with Scryfall's API (otag:removal, otag:counterspell, ...). This reads the
cards of every tag the site uses and writes

    t/tags.json.gz   {"version": 1, "generated": "YYYY-MM-DD", "source": ...,
                      "tags": ["anthem", "boardwipe", ...],
                      "cards": [[oracle id (first 12 characters),
                                 EDHREC rank or null, tag number, ...], ...]}

The EDHREC rank (how many decks play the card) puts the cards people use
first in the site's role results.

Scryfall asks for a pause between requests and answers too many with 429
("try again after 60 seconds"), so requests are 0.7 s apart and a 429 waits
a minute. The tags change slowly: the file is rebuilt once a week; on the
other days the published file is copied over. If Scryfall can't be read, the
published file is kept (and a tag that fails, comes back empty or isn't
reached within the time budget keeps its published cards). It never stops
the price update: on any problem it writes nothing and exits normally.

Usage (normally run by GitHub Actions - see update-prices.yml):
    python3 build_tags.py --out site/t --previous https://warujie.github.io/warujie-prices/
    python3 build_tags.py --out site/t --previous site --force      # rebuild now
    python3 build_tags.py --out site/t --api tests/fixture-folder   # saved answers, for testing
"""
import argparse
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

API = "https://api.scryfall.com"
HEADERS = {"User-Agent": "WarujiePriceHistory/1.1 (+https://github.com/warujie/warujie-prices)", "Accept": "application/json"}
SOURCE = "Scryfall Tagger (oracle tags, via Scryfall's search API)"
FORMAT_VERSION = 1
REBUILD_DAYS = 7
PAUSE = 0.7          # seconds between requests
RATE_LIMIT_WAIT = 65  # after a 429
MINUTES = 15         # time budget; tags not read in time keep their published cards
ID_CHARS = 12        # oracle ids are shortened to this many characters (no two cards share them)

# The tags the site's roles are made of (see ROLES in the site's page).
TAGS = sorted("""
anthem artifact-removal boardwipe bounce bounce-land burn cantrip cheat-into-play clone combat-trick
cost-reducer counterspell creature-removal deathtrigger draw drain-life edict enchantment-removal
extra-combat-phase extra-turn fetchland flicker fog gives-evasion gives-haste gives-hexproof
gives-indestructible graveyard-hate hand-disruption hatebear impulse-draw land-removal lifegain loot
mana-dork mana-doubler mana-rock mill protection ramp reanimate regrowth removal
repeatable-token-generator rummage sacrifice-outlet self-mill tapper theft tutor tutor-any tutor-land
untapper wheel copy-spell
""".split())


def load_published(source, rel):
    """A published file (URL or folder), or None when there is none."""
    if not source:
        return None
    try:
        if source.startswith(("http://", "https://")):
            req = urllib.request.Request(source.rstrip("/") + "/" + rel, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
        else:
            with open(os.path.join(source, rel), "rb") as fh:
                raw = fh.read()
    except (urllib.error.HTTPError, FileNotFoundError):
        return None
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


class Scryfall:
    """Pages of a search, politely: one request every PAUSE seconds, a minute's
    wait after a 429. `api` may be a folder of saved answers (for testing):
    the first page of otag:X is X.json, the next pages are named by the
    answers' own "next_page"."""

    def __init__(self, api):
        self.api = api
        self.remote = api.startswith(("http://", "https://"))
        self.last = 0.0
        self.requests = 0

    def get(self, url):
        if not self.remote:
            with open(os.path.join(self.api, url), encoding="utf-8") as fh:
                return json.load(fh)
        for attempt in range(4):
            wait = self.last + PAUSE - time.time()
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            self.requests += 1
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as err:
                if err.code == 404:
                    return {"data": [], "has_more": False}   # no card has the tag (any more)
                if err.code == 429 and attempt < 3:
                    print(f"  Scryfall asked to slow down; waiting {RATE_LIMIT_WAIT} s")
                    time.sleep(RATE_LIMIT_WAIT)
                    continue
                raise
        raise RuntimeError("Scryfall kept refusing")

    def tag_cards(self, tag):
        """[(oracle id, EDHREC rank or None)] of every card with the tag."""
        if self.remote:
            url = f"{self.api}/cards/search?" + urllib.parse.urlencode({"q": f"otag:{tag}", "unique": "cards", "order": "edhrec"})
        else:
            url = f"{tag}.json"
        out = []
        while url:
            page = self.get(url)
            for card in page.get("data") or []:
                oid = card.get("oracle_id") or ((card.get("card_faces") or [{}])[0].get("oracle_id"))
                if oid:
                    rank = card.get("edhrec_rank")
                    out.append((oid, rank if isinstance(rank, int) else None))
            url = page.get("next_page") if page.get("has_more") else None
        return out


def build(args):
    today = args.date or datetime.now(timezone.utc).date().isoformat()
    previous = None
    try:
        previous = load_published(args.previous, "t/tags.json.gz")
    except Exception as err:
        print(f"  note: the published tags could not be read ({err})")
    fresh = False
    if previous and not args.force:
        try:
            age = (date.fromisoformat(today) - date.fromisoformat(previous.get("generated", ""))).days
        except ValueError:
            age = REBUILD_DAYS
        if 0 <= age < REBUILD_DAYS and set(previous.get("tags") or []) >= set(TAGS):
            print(f"Tags of {previous['generated']} are {age} day(s) old - kept.")
            return previous
    # what the published file says, by tag, for tags that fail this time
    old_by_tag = {}
    if previous:
        names = previous.get("tags") or []
        for row in previous.get("cards") or []:
            for i in row[2:]:
                if 0 <= i < len(names):
                    old_by_tag.setdefault(names[i], []).append((row[0], row[1]))
    print("Reading Scryfall's oracle tags...")
    sf = Scryfall(args.api or API)
    deadline = time.time() + 60 * (MINUTES if args.minutes is None else args.minutes)
    cards = {}        # short oracle id -> [rank, set of tags]
    failed, kept = [], []
    for tag in TAGS:
        got = None
        if time.time() > deadline:
            print(f"  note: out of time before otag:{tag}")
            failed.append(tag)
        else:
            try:
                got = sf.tag_cards(tag)
            except Exception as err:
                print(f"  note: otag:{tag} could not be read ({err})")
                failed.append(tag)
            if got == [] and old_by_tag.get(tag):
                # a tag that had cards and now has none was most likely renamed: keep its cards
                print(f"  note: otag:{tag} has no cards any more")
                failed.append(tag)
                got = None
        if got is None:
            if tag in old_by_tag:
                kept.append(tag)
                got = old_by_tag[tag]
            else:
                continue
        for oid, rank in got:
            key = oid[:ID_CHARS]
            entry = cards.setdefault(key, [None, set()])
            if isinstance(rank, int) and (entry[0] is None or rank < entry[0]):
                entry[0] = rank
            entry[1].add(tag)
        print(f"  {tag}: {len(got)} cards")
    if not cards or len(failed) > len(TAGS) // 2:
        if previous:
            print("  Too many tags could not be read - keeping the published file.")
            return previous
        print("  note: no tags could be read from Scryfall - nothing written.")
        return None
    index = {t: i for i, t in enumerate(TAGS)}
    out = {"version": FORMAT_VERSION, "generated": today, "source": SOURCE, "tags": TAGS,
           "cards": [[key, rank] + sorted(index[t] for t in tags) for key, (rank, tags) in sorted(cards.items())]}
    if failed:
        out["kept_from_before"] = kept
        out["failed"] = failed
    print(f"{len(out['cards'])} cards with {len(TAGS)} tags ({sf.requests} requests)")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="folder to write tags.json.gz into (normally site/t)")
    ap.add_argument("--previous", default="", help="URL or folder of the currently published data")
    ap.add_argument("--api", default="", help="Scryfall's API, or a folder of saved answers for testing")
    ap.add_argument("--date", default="", help="today's date (YYYY-MM-DD, default today UTC)")
    ap.add_argument("--force", action="store_true", help="rebuild even if the published tags are recent")
    ap.add_argument("--minutes", type=float, default=None, help=f"time budget in minutes (default {MINUTES})")
    args = ap.parse_args()
    try:
        data = build(args)
    except Exception as err:   # never stops the price update
        print(f"note: tags could not be built ({err})")
        return 0
    if data is None:
        return 0
    os.makedirs(args.out, exist_ok=True)
    payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
    with open(os.path.join(args.out, "tags.json.gz"), "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(payload)
    print(f"Wrote {os.path.join(args.out, 'tags.json.gz')} ({os.path.getsize(os.path.join(args.out, 'tags.json.gz')) / 1e3:.0f} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
