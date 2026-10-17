"""Card-scan probe: finds the card's four edges near the on-screen guide.

The visitor holds the card roughly inside a card-shaped guide, so each edge is
searched only in a band around the guide's matching side. Along the band the
strongest edge points are collected, straight lines are fitted through them
(RANSAC), and of the few candidate lines per side the four that make the most
card-shaped outline win. Written with plain arrays so it ports to JavaScript.
"""
import numpy as np
import cv2

CARD_RATIO = 63 / 88
WORK_W = 540            # the photo is searched at this width
STRONG = 0.45           # a line along at least this share of a side is a real edge
BAND_OUT, BAND_IN = 0.10, 0.15   # how far outside / inside each guide side an edge is looked for


def edge_points(mag, axis, lo, hi, positions, outward, peaks=3, rel=0.15, floor=12.0):
    """For each position along a side, the `peaks` outermost strong edge
    locations across the band [lo, hi). axis=0: horizontal side (scan down
    columns). outward: +1 when the outside of the card is at higher
    coordinates (bottom, right), -1 when lower (top, left). Taking the
    outermost edges, not the strongest, matters: rules text and frame lines
    inside the card are often stronger than the card's own edge."""
    pts = []
    for p in positions:
        prof = mag[lo:hi, p] if axis == 0 else mag[p, lo:hi]
        if prof.size < 3:
            continue
        thr = max(floor, rel * prof.max(), 3.0 * float(np.median(prof)))
        cand = np.where((prof[1:-1] >= prof[:-2]) & (prof[1:-1] > prof[2:]) & (prof[1:-1] >= thr))[0] + 1
        if cand.size == 0:
            continue
        cand = cand[::-1] if outward > 0 else cand
        for b in cand[:peaks]:
            pts.append((p, lo + b, prof[b]))
    return np.array(pts, dtype=np.float64).reshape(-1, 3)


def fit_lines(pts, max_slope, tol, rng, want=4, iters=150, min_frac=0.25, n_pos=1):
    """Lines v = a*u + b through (u, v, weight) points; returns up to `want`
    (a, b, support) found one after another, removing each line's points."""
    lines = []
    pts = pts.copy()
    for _ in range(want):
        if len(pts) < 8:
            break
        best, best_in = None, None
        for _ in range(iters):
            i, j = rng.choice(len(pts), 2, replace=False)
            (u1, v1, _), (u2, v2, _) = pts[i], pts[j]
            if abs(u2 - u1) < 10:
                continue
            a = (v2 - v1) / (u2 - u1)
            if abs(a) > max_slope:
                continue
            b = v1 - a * u1
            inl = np.abs(pts[:, 1] - (a * pts[:, 0] + b)) < tol
            score = pts[inl, 2].sum()
            if best is None or score > best:
                best, best_in = score, inl
        if best_in is None:
            break
        u, v = pts[best_in, 0], pts[best_in, 1]
        support = len(np.unique(u)) / n_pos
        if support < min_frac:
            break
        a, b = np.polyfit(u, v, 1)
        lines.append((a, b, support))
        pts = pts[~best_in]
    return lines


def intersect(h, v):
    """h: y = a*x + b (horizontal side); v: x = c*y + d (vertical side)."""
    a, b = h[0], h[1]
    c, d = v[0], v[1]
    y = (a * d + b) / (1 - a * c)
    x = c * y + d
    return np.array([x, y])


def detect_card(photo, guide, rng=None):
    """photo: RGB uint8; guide: (x0, y0, x1, y1) in the photo. Returns 4x2
    corners (tl, tr, br, bl) in the photo, or None when nothing card-shaped."""
    rng = rng or np.random.default_rng(0)
    h0, w0 = photo.shape[:2]
    f = WORK_W / w0
    small = cv2.resize(photo, (WORK_W, int(round(h0 * f))), interpolation=cv2.INTER_AREA)
    g = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY).astype(np.float32), (0, 0), 1.2)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    ax, ay = np.abs(gx), np.abs(gy)
    H, W = g.shape
    x0, y0, x1, y1 = [v * f for v in guide]
    gw, gh = x1 - x0, y1 - y0
    cols = np.arange(int(x0 + 0.18 * gw), int(x1 - 0.18 * gw), 3)
    rows = np.arange(int(y0 + 0.18 * gh), int(y1 - 0.18 * gh), 3)
    clamp = lambda v, hi: int(max(0, min(hi, v)))  # noqa: E731
    slope = np.tan(np.deg2rad(14))
    sides = {}
    # top and bottom: y as a function of x
    # each side's band reaches further into the card than out of it: the
    # visitor fits the card inside the guide, and lines well outside it are
    # other cards or the table
    for name, centre in (("top", y0), ("bottom", y1)):
        o = 1 if name == "bottom" else -1
        lo, hi = sorted((centre + o * BAND_OUT * gh, centre - o * BAND_IN * gh))
        pts = edge_points(ay, 0, clamp(lo, H), clamp(hi, H), cols, o)
        sides[name] = fit_lines(pts, slope, 2.0, rng, n_pos=len(cols))
    for name, centre in (("left", x0), ("right", x1)):
        o = 1 if name == "right" else -1
        lo, hi = sorted((centre + o * BAND_OUT * gw, centre - o * BAND_IN * gw))
        pts = edge_points(ax, 1, clamp(lo, W), clamp(hi, W), rows, o)
        # (u, v) = (y, x): x as a function of y
        sides[name] = fit_lines(pts, slope, 2.0, rng, n_pos=len(rows))
    if any(not sides[k] for k in sides):
        return None
    # number each side's lines from the outside in: the card's own edge is the
    # outermost long straight line, the black border's inner edge and the text
    # box come after it
    mid_u = {"top": (x0 + x1) / 2, "bottom": (x0 + x1) / 2, "left": (y0 + y1) / 2, "right": (y0 + y1) / 2}
    outward = {"top": -1, "bottom": 1, "left": -1, "right": 1}
    for k in sides:
        lines = sorted(sides[k], key=lambda ln: -outward[k] * (ln[0] * mid_u[k] + ln[1]))
        # how many well-supported lines lie outside each one: passing over the
        # card's real edge to an inner line costs more than any support gained
        sides[k] = [(a, b, sup, sum(1 for o in lines[:i] if o[2] >= STRONG))
                    for i, (a, b, sup) in enumerate(lines)]

    best, best_score = None, None
    for t in sides["top"]:
        for b in sides["bottom"]:
            for l in sides["left"]:
                for r in sides["right"]:
                    c = np.array([intersect(t, l), intersect(t, r), intersect(b, r), intersect(b, l)])
                    wid = (np.linalg.norm(c[1] - c[0]) + np.linalg.norm(c[2] - c[3])) / 2
                    hei = (np.linalg.norm(c[3] - c[0]) + np.linalg.norm(c[2] - c[1])) / 2
                    if hei <= 0 or wid <= 0:
                        continue
                    ratio_err = abs(np.log((wid / hei) / CARD_RATIO))
                    size = wid * hei / (gw * gh)
                    if ratio_err > 0.12 or not (0.5 < size < 1.45):
                        continue
                    if cv2.contourArea(c.astype(np.float32)) <= 0 or not cv2.isContourConvex(c.astype(np.float32)):
                        continue
                    support = t[2] + b[2] + l[2] + r[2]
                    skipped = t[3] + b[3] + l[3] + r[3]
                    # card-shaped, the outermost strong edges, well supported
                    score = support - 1.0 * skipped - 6 * ratio_err - 1.0 * abs(np.log(size))
                    if best_score is None or score > best_score:
                        best, best_score = c, score
    if best is None:
        return None
    return (best / f).astype(np.float32)
