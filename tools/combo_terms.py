#!/usr/bin/env python3
"""One-off helper: lists the words and sentences used in Commander
Spellbook's combos (results, required card kinds, prerequisites and steps,
with card names replaced by {0}, {1}, ...) so they can be translated into
Japanese for the site. Writes tools/combo_terms.json.gz."""
import collections, gzip, json, os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build_combos as bc

def main():
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "variants.json.gz")
    bc.download(bc.BULK_URL, src)
    features, templates = collections.Counter(), collections.Counter()
    lines, examples = collections.Counter(), {}
    seen = 0
    with bc.open_text(src) as stream:
        for v in bc.iter_array(stream, "variants"):
            if not isinstance(v, dict) or bc.pick(v, "status", default="OK") not in ("OK", "E"):
                continue
            seen += 1
            pop = 1
            names = []
            for u in bc.pick(v, "uses", default=[]) or []:
                n = bc.pick(bc.pick(u, "card", default={}) or {}, "name", default="")
                if n:
                    names.append(n)
            tnames = []
            for r in bc.pick(v, "requires", default=[]) or []:
                n = bc.pick(bc.pick(r, "template", default={}) or {}, "name")
                if n:
                    templates[n] += pop
                    tnames.append(n)
            for p in bc.pick(v, "produces", default=[]) or []:
                f = bc.pick(bc.pick(p, "feature", default={}) or {}, "name")
                if f:
                    features[f] += pop
            subs = []
            for i, n in enumerate(names):
                subs.append((n, "{%d}" % i))
                if " // " in n:
                    for part in n.split(" // "):
                        subs.append((part, "{%d}" % i))
            for i, n in enumerate(tnames):
                subs.append((n, "{T%d}" % i))
            subs.sort(key=lambda s: -len(s[0]))
            text = "\n".join(t for t in (bc.pick(v, "notablePrerequisites", default=""), bc.pick(v, "easyPrerequisites", default=""),
                                         bc.pick(v, "description", default="")) if t)
            for line in text.replace("\r\n", "\n").split("\n"):
                line = line.strip()
                if not line:
                    continue
                norm = line
                for n, ph in subs:
                    norm = norm.replace(n, ph)
                lines[norm] += pop
                if norm not in examples:
                    examples[norm] = line
    out = {"variants": seen,
           "features": features.most_common(),
           "templates": templates.most_common(),
           "lines_total": sum(lines.values()), "lines_distinct": len(lines),
           "lines": [[l, c, examples[l]] for l, c in lines.most_common(40000)]}
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "combo_terms.json.gz")
    with gzip.open(dest, "wt", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(seen, "combos;", len(features), "results;", len(templates), "card kinds;", len(lines), "distinct lines;", os.path.getsize(dest) // 1024, "KB")

if __name__ == "__main__":
    main()
