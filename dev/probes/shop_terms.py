"""One-off: read the terms, contact page and robots.txt of Japanese shops we
might ask for price permission (normal page reads, a few per shop, 3 s apart).
Writes probe_out/shop_terms.txt: each shop's useful links, robots.txt, and the
terms sentences about automated access, copying or reuse."""
import html, re, time, urllib.parse, urllib.request
UA = "Mozilla/5.0 (compatible; WarujieTermsCheck/1.0; +https://warujie.jp)"
SHOPS = {
    "bigweb": "https://mtg.bigweb.co.jp/",
    "PRICE BASE": "https://shop.price-base.com/",
    "Toretoku": "https://www.toretoku.jp/",
}
FIND = ["ジョニーのお店 MTG", "カードショップ抜忍 MTG 通販", "竜のしっぽ MTG 通販", "イエローサブマリン MTG シングル 通販",
        "ホビーステーション MTG シングル 通販", "マスターズスクウェア MTG 通販"]
LINK_WORDS = re.compile(r"規約|特定商取引|特商法|会社概要|運営会社|問い合わせ|問合せ|ガイド|プライバシー|terms|contact|company|law|tokushoho|guide", re.I)
KEY = re.compile(r"スクレイピング|クローラ|クローリング|ロボット|自動|プログラム|転載|複製|無断|二次利用|商用|引用|robot|scrap|crawl", re.I)
out = []

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = r.read()
        cs = r.headers.get_content_charset() or ("shift_jis" if b"shift_jis" in raw[:3000].lower() or b"sjis" in raw[:3000].lower() else
                                                  "euc-jp" if b"euc-jp" in raw[:3000].lower() else "utf-8")
        return raw.decode(cs, "replace"), r.geturl()

def text(page):
    page = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?s)<[^>]+>", "\n", page)
    return re.sub(r"\n\s*\n+", "\n", html.unescape(page))

def links(page, base):
    seen, res = set(), []
    for href, label in re.findall(r'(?is)<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', page):
        label = re.sub(r"(?s)<[^>]+>", "", html.unescape(label)).strip()
        u = urllib.parse.urljoin(base, html.unescape(href))
        if (LINK_WORDS.search(label) or LINK_WORDS.search(href)) and u not in seen and u.startswith("http"):
            seen.add(u); res.append((label[:40], u))
    return res

def check(name, home):
    out.append(f"\n==================== {name}  {home}")
    try:
        page, final = get(home)
    except Exception as e:
        out.append(f"  home: {e}"); return
    out.append(f"  home ok ({final}); title: {re.search(r'(?is)<title>(.*?)</title>', page).group(1).strip()[:80] if re.search(r'(?is)<title>(.*?)</title>', page) else ''}")
    out.append("  mentions MTG singles: " + str(bool(re.search(r"シングル", page)) and bool(re.search(r"MTG|マジック", page))))
    root = "{0.scheme}://{0.netloc}/".format(urllib.parse.urlparse(final))
    time.sleep(3)
    try:
        rb, _ = get(root + "robots.txt"); out.append("  robots.txt:\n    " + "\n    ".join(rb.strip().splitlines()[:25]))
    except Exception as e:
        out.append(f"  robots.txt: {e}")
    ls = links(page, final)
    out.append("  links: " + "; ".join(f"{l} <{u}>" for l, u in ls[:20]))
    emails = set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text(page)))
    for label, u in [x for x in ls if re.search(r"規約|guide|ガイド|terms|特定商取引|特商法|law|tokushoho|会社概要|company|問い合わせ|問合せ|contact", x[0] + x[1], re.I)][:6]:
        time.sleep(3)
        try:
            p, _ = get(u)
        except Exception as e:
            out.append(f"  -- {label} <{u}>: {e}"); continue
        t = text(p)
        emails |= set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", t))
        hits = [ln.strip() for ln in t.splitlines() if KEY.search(ln) and 4 < len(ln.strip()) < 400]
        forms = "form" if re.search(r"(?i)<form", p) else ""
        out.append(f"  -- {label} <{u}> {forms}\n     " + "\n     ".join(hits[:15]))
    out.append("  emails: " + ", ".join(sorted(e for e in emails if not e.endswith((".png", ".jpg", ".gif")))))

for name, home in SHOPS.items():
    check(name, home)
out.append("\n==================== search for the other shops' addresses")
for q in FIND:
    time.sleep(3)
    try:
        page, _ = get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q))
        hits = re.findall(r'class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', page)
        res = []
        for h, l in hits[:6]:
            m = re.search(r"uddg=([^&]+)", h)
            res.append(f"{re.sub(r'<[^>]+>', '', html.unescape(l))[:50]} <{urllib.parse.unquote(m.group(1)) if m else h}>")
        out.append(f"  {q}:\n    " + "\n    ".join(res or ["(no results)"]))
    except Exception as e:
        out.append(f"  {q}: {e}")
open("probe_out/shop_terms.txt", "w").write("\n".join(out) + "\n")
print("\n".join(out))
