"""One-off sample of ENNDAL GAMES pages, to design the price reader.

ENNDAL GAMES agreed (2026-10-15) to low-frequency automated access. This fetches
about five pages once, one at a time and 5 seconds apart, honours robots.txt,
and saves the raw pages under probe_out/enndal/ for offline parsing.
"""
import os, re, time, urllib.error, urllib.request, urllib.robotparser

BASE = "https://www.enndalgames.com"
CONTACT = "warujie.mtg" + "@" + "gmail.com"
UA = f"WarujieShopPrices/0.1 (+https://warujie.jp; {CONTACT})"
OUT = "probe_out/enndal"
GAP = 5.0
os.makedirs(OUT, exist_ok=True)

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, dict(r.headers), r.read()

def save(name, url, status, headers, body):
    with open(f"{OUT}/{name}", "wb") as f:
        f.write(body)
    with open(f"{OUT}/index.txt", "a") as f:
        f.write(f"{name}\t{status}\t{len(body)}\t{headers.get('Content-Type','')}\t{url}\n")

try:
    status, headers, robots = get(BASE + "/robots.txt")
except urllib.error.HTTPError as e:   # no robots.txt (404) means no restrictions
    status, headers, robots = e.code, dict(e.headers), b""
save("robots.txt", BASE + "/robots.txt", status, headers, robots)
rp = urllib.robotparser.RobotFileParser()
rp.parse(robots.decode("utf-8", "replace").splitlines())

pages = [
    ("list_blb_p1.html", BASE + "/products/list.php?category_id=2363&disp_number=100"),
    ("list_blb_p2.html", BASE + "/products/list.php?category_id=2363&disp_number=100&pageno=2"),
    ("search_bolt.html", BASE + "/products/list.php?mode=search&name=%E7%A8%B2%E5%A6%BB"),
]
details = []
for name, url in pages:
    time.sleep(GAP)
    if not rp.can_fetch(UA, url):
        save(name + ".skipped", url, 0, {}, b"disallowed by robots.txt")
        continue
    status, headers, body = get(url)
    save(name, url, status, headers, body)
    if name == "list_blb_p1.html":
        ids = re.findall(rb"detail\.php\?product_id=(\d+)", body)
        details = list(dict.fromkeys(ids))[:2]

for pid in details:
    time.sleep(GAP)
    url = f"{BASE}/products/detail.php?product_id={pid.decode()}"
    if not rp.can_fetch(UA, url):
        continue
    status, headers, body = get(url)
    save(f"detail_{pid.decode()}.html", url, status, headers, body)
