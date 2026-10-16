"""ENNDAL GAMES (enndalgames.com): yen prices and stock for warujie.jp's JP tab.

ENNDAL GAMES agreed on 2026-10-15 to low-frequency automated access, and we told
them how we read their shop: once a night (2-6am Japan time), one page at a
time, PAGE_GAP seconds apart, with a User-Agent naming warujie.jp and our
contact address. Keep it that way: never read pages in parallel, and stop at
once if they ask.

Their shop is EC-CUBE 2. Every set is a category; its list pages show 100
products each, and every product carries a code in its URL,
    <SET>-<rarity><colour>-<number>-<lang>-<condition>-<finish>
(e.g. BLB-MW-0002-JP-NM-normal), its name "(BLB-MW)English/日本語", and a
table with one row per language and condition: price in yen and copies left.

    parse_categories(html) -> [(category_id, name, items)]
    parse_list(html)       -> [{"set", "number", "finish", "name_en", "name_ja",
                                "url", "offers": [(lang, cond, yen, copies)]}]
    read_shop(...)         -> the in-stock offers of the categories asked for
"""
import html as htmllib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://www.enndalgames.com"
CONTACT = "warujie.mtg" + "@" + "gmail.com"
USER_AGENT = f"WarujieShopPrices/1.0 (+https://warujie.jp; {CONTACT})"
PAGE_GAP = 4.0          # seconds between pages (we promised 3-5)
PER_PAGE = 100          # the largest page size the shop offers
LANGS = {"日本語": "JA", "英語": "EN"}

CATEGORY_RE = re.compile(
    r'category_id=(\d+)&(?:amp;)?disp_number=\d+"[^>]*>([^<]+)<span>\((\d+)\)</span>')
PRODUCT_RE = re.compile(r'<div class="list_area[^"]*">(.*?)<div class="listcomment">', re.S)
NAME_RE = re.compile(r'<a href="([^"]+/product/([^/"]+)/)"\s+class="product_name"[^>]*>([^<]+)</a>')
# some sets' codes end in "_" (MH3-MC-0006-JP-NM-normal_)
CODE_RE = re.compile(r'^([A-Z0-9]+)-([A-Z])([A-Z])-([0-9A-Za-z]+)-([A-Z]+)-([A-Z]+)-([a-z]+)_*$')
ROW_RE = re.compile(r'<tr><th>\s*(\S+)\s+(\S+)\s*</th><td><span class="price">([\d,]+)円</span>'
                    r'<span class="quantity">\s*残り\s*(\d+)</span>')
TOTAL_RE = re.compile(r'<span class="attention">(\d+)件</span>')


def parse_categories(page):
    """The set categories in the shop's menu, with their item counts
    (out-of-stock items included)."""
    seen, out = set(), []
    for cid, name, n in CATEGORY_RE.findall(page):
        if cid not in seen:
            seen.add(cid)
            out.append((int(cid), htmllib.unescape(name).strip(), int(n)))
    return out


def parse_total(page):
    m = TOTAL_RE.search(page)
    return int(m.group(1)) if m else 0


def split_name(title):
    """'【拡張アート】(LCI-RA)Threefold Thunderhulk/三重の稲妻巨人【No.0390】'
    -> ('Threefold Thunderhulk', '三重の稲妻巨人')."""
    t = re.sub(r"【[^】]*】", "", htmllib.unescape(title))
    t = re.sub(r"^\([^)]*\)", "", t).strip()
    en, _, ja = t.partition("/")
    return en.strip(), ja.strip()


def parse_list(page):
    """The products on one list page, with an offer per language and
    condition that has copies left."""
    out = []
    for block in PRODUCT_RE.findall(page):
        m = NAME_RE.search(block)
        if not m:
            continue
        url, code, title = m.groups()
        c = CODE_RE.match(urllib.parse.unquote(code))
        if not c:
            continue
        set_code, _rarity, _colour, number, _lang, _cond, finish = c.groups()
        offers = []
        for lang, cond, yen, copies in ROW_RE.findall(block):
            copies = int(copies)
            if copies <= 0 or lang not in LANGS:
                continue
            offers.append((LANGS[lang], cond, int(yen.replace(",", "")), copies))
        en, ja = split_name(title)
        out.append({"set": set_code.lower(), "number": number.lstrip("0") or "0",
                    "finish": finish, "name_en": en, "name_ja": ja,
                    "url": htmllib.unescape(url), "offers": offers})
    return out


def fetch(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ja"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            if err.code in (403, 429, 503):   # the shop is pushing back: stop for tonight
                raise
            if attempt == tries - 1:
                raise
        except OSError:
            if attempt == tries - 1:
                raise
        time.sleep(PAGE_GAP * 5)


def list_url(category_id, page_no):
    # oos=0 leaves out products with no copies left, so fewer pages are read
    return f"{BASE}/products/list.php?category_id={category_id}&disp_number={PER_PAGE}&pageno={page_no}&oos=0"


def read_shop(categories, minutes, get=fetch, sleep=time.sleep, log=print):
    """Read the given categories' in-stock products, one page at a time,
    PAGE_GAP seconds apart, for at most `minutes`. Returns (products,
    finished category ids)."""
    deadline = time.monotonic() + minutes * 60
    products, done, first = [], [], True
    for cid in categories:
        page_no = 1
        while True:
            if time.monotonic() > deadline:
                log(f"  ENNDAL: time is up after {len(done)} categories")
                return products, done
            if not first:
                sleep(PAGE_GAP)
            first = False
            page = get(list_url(cid, page_no))
            got = parse_list(page)
            if not got and PRODUCT_RE.search(page):
                log(f"  ENNDAL: category {cid} page {page_no} has products we could not read")
            products.extend(got)
            total = parse_total(page)
            if not got or page_no * PER_PAGE >= total:
                break
            page_no += 1
        done.append(cid)
    return products, done
