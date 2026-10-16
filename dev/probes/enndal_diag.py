"""One-off check: why the test night read no Modern Horizons 3 products.
Reads ONE list page (MH3, in stock, page 1) and writes only counts, product
codes and the page's tag outline (no text, no prices) to probe_out/enndal_diag.txt."""
import os, re, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import shop_enndal as en

page = en.fetch(en.list_url(2333, 1))
out = [f"length {len(page)}", f"total {en.parse_total(page)}",
       f"list_area blocks {len(en.PRODUCT_RE.findall(page))}",
       f"parsed {len(en.parse_list(page))}",
       f"'list_area' occurrences {page.count('list_area')}",
       f"'product_name' occurrences {page.count('product_name')}",
       f"'/product/' occurrences {page.count('/product/')}"]
codes = re.findall(r'/product/([^/"]+)/', page)
out.append("codes (first 20): " + " ".join(urllib.parse.unquote(c) for c in codes[:20]))
out.append("codes failing CODE_RE: " + " ".join(urllib.parse.unquote(c) for c in codes
           if not en.CODE_RE.match(urllib.parse.unquote(c)))[:3000])
i = page.find("product_name")
if i < 0:
    i = page.find("<title>")
seg = page[max(0, i - 3000): i + 3000]
outline = re.sub(r">[^<]+<", ">T<", seg)
outline = re.sub(r'(href|src|alt|title|value)="[^"]*"', r'\1=""', outline)
out.append("tag outline around the first product:\n" + outline)
open("probe_out/enndal_diag.txt", "w").write("\n".join(out) + "\n")
print("\n".join(out[:9]))
