# SPDX-License-Identifier: AGPL-3.0-or-later
"""_layers.py - the code-drawn parallax layers behind `pix_parallax draw` (numpy only). Every layer is seamless by construction: shapes are stamped at x % W,
profiles are built from integer harmonics or periodic control points, and nothing depends on x outside the layer. Colours come from one palette per time of day
(sky, haze, light and shadow tints) and one 5-tone ramp per depth: far = pulled toward the haze (lighter, less saturated, flatter), near = full colour.
Craft rules used (from the pixel-art references in pixart/KNOWLEDGE.md and a look at CC0 parallax packs): flat colour planes, dither only as one checker row at a tone border,
a 1 px dark contour on land masses, one light from the upper left, hue-shifted ramps (shadows cool, lights warm), clustered not uniform placement, detail falls with distance.
Not meant to compete with hand-made art: these are good starting layers and placeholders."""
import math
import numpy as np

# ------------------------------------------------------------------ colour
HOURS = {                                   # one palette per time of day; everything else is derived
    "dawn": dict(top="#3a4a86", mid="#a47cb0", bottom="#f4b79a", glow="#ffd7a8", haze="#dcbccb", light="#fff0d0", shadow="#3b3a6e", cloud="#f6d3d0", stars=0.2, disc="sun", disc_y=0.80),
    "noon": dict(top="#4a90d9", mid="#8cc4ea", bottom="#c4e8f4", glow=None, haze="#d3e6ee", light="#fffbe0", shadow="#2c4a7a", cloud="#ffffff", stars=0.0, disc="sun", disc_y=0.18),
    "dusk": dict(top="#2a2b66", mid="#a04a86", bottom="#f2a67e", glow="#ffcf8a", haze="#c9a3b4", light="#ffd9a0", shadow="#262a5e", cloud="#f2c1c4", stars=0.6, disc="sun", disc_y=0.74),
    "night": dict(top="#090b22", mid="#1c1850", bottom="#3a3070", glow=None, haze="#5a5090", light="#b8c4ff", shadow="#0a0a2a", cloud="#4a3f7c", stars=1.0, disc="moon", disc_y=0.22),
}


def hexc(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    a = hexc(a) if isinstance(a, str) else a; b = hexc(b) if isinstance(b, str) else b
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def ramp(base, t, P):
    """5 tones, dark to light: line, shade, body, light, highlight. t = depth haze (0 near .. 0.7 far): the body is pulled toward the haze colour, shadows go cool, lights warm."""
    c = mix(base, P["haze"], t)
    return [mix(c, P["shadow"], 0.62), mix(c, P["shadow"], 0.30), c, mix(c, P["light"], 0.22), mix(c, P["light"], 0.45)]


# ------------------------------------------------------------------ small helpers
def blank(W, H):
    return np.zeros((H, W, 4), np.uint8)


def put(im, m, c):
    im[m] = (*c, 255)


def grid(W, H):
    return np.mgrid[0:H, 0:W]


def wrapdx(xx, cx, W):
    """signed distance from column cx with wrap, so shapes near the edge continue on the other side"""
    return (xx - cx + W // 2) % W - W // 2


def checker(xx, yy, ph=0):
    return ((xx + yy + ph) % 2) == 0


# ------------------------------------------------------------------ sky, sun / moon, stars
def sky(W, H, P, n=6):
    """flat colour bands, borders bunched toward the horizon, one checker row above each border and a thin glow at the horizon"""
    md = P.get("mid") or mix(P["top"], P["bottom"], .5)
    cols = [mix(P["top"], md, i / ((n - 1) / 2)) if i <= (n - 1) / 2 else mix(md, P["bottom"], (i - (n - 1) / 2) / ((n - 1) / 2)) for i in range(n)]; im = blank(W, H); yy, xx = grid(W, H)
    edges = [int(H * (i / n) ** 0.8) for i in range(1, n)]; band = np.zeros(H, int)
    for e in edges:
        band[e:] += 1
    for i, c in enumerate(cols):
        put(im, band[yy] == i, c)
    for e in edges:
        put(im, (yy == e - 1) & checker(xx, yy), cols[band[e]])
    if P["glow"]:
        put(im, (yy >= H - 14) & (yy < H - 6) & checker(xx, yy), hexc(P["glow"])); put(im, yy >= H - 6, hexc(P["glow"]))
    return im


def disc(W, H, P, rng, top0=0, vh=None, cx=None):
    """sun (three tones and a glow ring of checker pixels) or moon (pale disc, crescent shadow, two craters); one per layer, drawn in the first viewport"""
    im = blank(W, H); yy, xx = grid(W, H); cx = int(rng.integers(70, 250)) if cx is None else cx; cy = int(top0 + P["disc_y"] * ((vh or H) - 24)) + 10; r = 9 if P["disc"] == "sun" else 8
    d2 = (xx - cx) ** 2 + (yy - cy) ** 2
    if P["disc"] == "sun":
        glow = mix(P["light"], P["bottom"], 0.5)
        put(im, (d2 <= (r + 6) ** 2) & (d2 > (r + 1) ** 2) & checker(xx, yy), glow); put(im, d2 <= (r + 1) ** 2, mix(glow, "#ffffff", 0.3))
        put(im, d2 <= r * r, mix(P["light"], "#ffffff", 0.5)); put(im, d2 <= (r - 3) ** 2, mix(P["light"], "#ffffff", 0.85))
    else:
        base = mix(P["light"], "#ffffff", 0.5); put(im, d2 <= r * r, base)
        put(im, (d2 <= r * r) & ((xx - cx - 3) ** 2 + (yy - cy + 1) ** 2 > (r - 1) ** 2), mix(base, P["shadow"], 0.35))
        for dx, dy in ((-3, -2), (1, 3)):
            put(im, (xx - cx - dx) ** 2 + (yy - cy - dy) ** 2 <= 2, mix(base, P["shadow"], 0.5))
        put(im, (d2 <= (r + 4) ** 2) & (d2 > (r + 1) ** 2) & checker(xx, yy), mix(P["top"], P["light"], 0.3))
    return im


def stars(W, H, P, rng, y_min, y_max, frames=1):
    """a list of `frames` layers; the frames differ only in star brightness (a 4-step twinkle with a phase per star), so they loop by construction"""
    n = int(10 + 90 * P["stars"]); pts = [(int(rng.integers(0, W)), int(rng.integers(y_min, y_max)), int(rng.integers(0, 4)), bool(rng.random() < 0.12)) for _ in range(n)]
    c = [mix(P["top"], P["light"], .35), mix(P["top"], P["light"], .7), mix("#ffffff", P["light"], .25)]; out = []
    for f in range(frames):
        im = blank(W, H)
        for x, y, ph, big in pts:
            lv = (0, 1, 2, 1)[(ph + f) % 4]; im[y, x] = (*c[lv], 255)
            if big and lv == 2:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    im[(y + dy) % H, (x + dx) % W] = (*c[0], 255)
        out.append(im)
    return out


# ------------------------------------------------------------------ clouds
def clouds(W, H, P, rng, y0, y1, n=5, tone=None):
    """lumpy clouds: bumps along a flat base, biggest in the middle, lit upper left per bump, a shaded 2-row underside, size mix with spacing, wrapped"""
    cl = ramp(tone or P["cloud"], 0.0, P); im = blank(W, H); yy, xx = grid(W, H)
    sizes = sorted([int(s) for s in rng.choice([10, 14, 18, 26, 34], size=n, p=[.2, .3, .25, .15, .1])], reverse=True)
    sizes[0] = max(sizes[0], 26)
    placed = []
    for s in sizes:
        for _ in range(40):
            cx = int(rng.integers(0, W))
            if all(min(abs(cx - px), W - abs(cx - px)) >= 0.85 * (s + ps) for px, ps in placed):
                placed.append((cx, s)); break
    for cx, s in placed:
        cy = int(rng.integers(y0, y1)) + int(1.5 * s); m = np.zeros((H, W), bool); nb = int(3 + s // 7); bumps = []      # y0..y1 bound the cloud TOP, so a big cloud is never cut by the top edge
        for j in range(nb):
            u = (j + 0.5) / nb; r = int(s * (0.28 + 0.5 * (1 - abs(2 * u - 1)) ** 0.7)) + int(rng.integers(0, 3))
            bx = cx + int((u - 0.5) * s * 1.5); by = cy - r + 1; dx = wrapdx(xx, bx, W)
            m |= (dx ** 2 + (yy - by) ** 2 <= r * r) & (yy <= cy); bumps.append((bx, by, r))
        put(im, m, cl[2]); lit = np.zeros((H, W), bool)
        for bx, by, r in bumps:
            dx = wrapdx(xx, bx, W); lit |= m & (dx ** 2 + (yy - by) ** 2 <= (r - 1) ** 2) & (dx + (yy - by) < -r * 0.45)
        put(im, lit, cl[3]); put(im, m & (yy >= cy - 1), cl[1]); put(im, m & (yy == cy - 2) & checker(xx, yy), cl[1])
    return im


# ------------------------------------------------------------------ land: mountains, hills, dunes
def _closed_walk(W, rng, amp=2):
    j = np.cumsum(rng.integers(-1, 2, W)).astype(float); j -= np.linspace(j[0], j[-1] + (j[-1] - j[0]) / (W - 1), W)       # a random walk closed into a loop
    return np.clip(j * 0.6, -amp, amp)


def peaks_profile(W, rng, base_y, amp, n_peaks):
    """periodic piecewise-linear profile: n_peaks peaks on an even spacing (jittered), varied heights, valleys between them; slopes stay near 45 degrees, not needles"""
    step = W / n_peaks; pts = []
    for i in range(n_peaks):
        px = i * step + rng.uniform(-0.18, 0.18) * step; vx = px + step / 2 + rng.uniform(-0.15, 0.15) * step
        py = base_y - amp * rng.uniform(0.62, 1.0); vy = base_y - amp * rng.uniform(0.0, 0.32)
        pts.append((px, py, True)); pts.append((vx, vy, False))
        for u in (0.35, 0.7):                                                  # extra vertices on each slope make shoulders and kinks instead of straight lines
            pts.append((px + (vx - px) * u + rng.uniform(-2, 2), py + (vy - py) * u + rng.uniform(-0.10, 0.10) * amp, False))
        pts.append((vx + (px + step - vx) * 0.5 + rng.uniform(-3, 3), (vy + (base_y - amp * rng.uniform(0.62, 1.0))) / 2 + rng.uniform(-0.08, 0.08) * amp, False))
    pts.sort(key=lambda q: q[0]); xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
    xs2 = [x - W for x in xs] + xs + [x + W for x in xs]; ys2 = ys * 3                           # three copies make the interpolation periodic
    prof = np.interp(np.arange(W), xs2, ys2); prof = np.round(prof + _closed_walk(W, rng)).astype(int)
    return prof, [(int(round(q[0])) % W, int(round(q[1]))) for q in pts if q[2]]


def mountains(W, H, P, rng, base, t, base_y, amp, n_peaks=4, snow=False, fog=False):
    """faceted mountains: a lit and a shadow face split at each summit, a dark 1 px contour, a scalloped snow line, and (far plane only) a flat haze band at the foot"""
    r_ = ramp(base, t, P); prof, peaks = peaks_profile(W, rng, base_y, amp, n_peaks); im = blank(W, H); yy, xx = grid(W, H); body = yy >= prof[xx]
    pxs = np.array([q[0] for q in peaks]); pys = np.array([q[1] for q in peaks]); order0 = np.argsort(pxs); pxs, pys = pxs[order0], pys[order0]
    vx = []                                                              # the lowest contour point between neighbouring peaks: the face boundary starts there, so it never cuts a slope
    for k in range(len(pxs)):
        a_, b_ = int(pxs[k]), int(pxs[(k + 1) % len(pxs)]); b_ = b_ + W if b_ <= a_ else b_
        seg = np.arange(a_, b_ + 1); vx.append(int(seg[int(np.argmax(prof[seg % W]))]) % W)
    lp = np.zeros(W, int)
    for k in range(len(pxs)):
        lo, hi = vx[k - 1], vx[k]; hi = hi + W if hi <= lo else hi
        lp[np.arange(lo, hi) % W] = k
    dx = wrapdx(xx, pxs[lp][xx], W); dark = body & (dx > (yy - pys[lp][xx]) * 0.25 + 1)
    ext = np.concatenate([prof[-48:], prof, prof[:48]]); lev_raw = np.array([ext[i:i + 97].max() for i in range(W)])      # the lowest contour point within 48 px: the valley floor next to this column
    lev = np.round(np.convolve(np.concatenate([lev_raw[-15:], lev_raw, lev_raw[:15]]), np.ones(31) / 31, "valid")).astype(int)   # smoothed, so the neutral foot has no stair steps
    below = body & (yy > lev[xx] + 4)                                   # faces exist above the valley floor; under it one neutral tone (no vertical line where the nearest peak changes)
    lit_c = mix(r_[2], P["light"], 0.26); dark_c = mix(r_[2], P["shadow"], 0.52)                                                      # two clearly different faces
    put(im, body, lit_c); put(im, dark, dark_c); put(im, below, mix(lit_c, dark_c, 0.55)); put(im, body & (yy == lev[xx] + 4) & checker(xx, yy), mix(lit_c, dark_c, 0.55)); put(im, body & ~dark & (dx > (yy - pys[lp][xx]) * 0.25 - 2) & checker(xx, yy), dark_c)       # a 2 px checker softens the face edge
    if snow:
        sl = np.array([int(base_y - amp * 0.58 + ((x // 3) % 3 == 1) + ((x // 7) % 2)) for x in range(W)]); sn = body & (yy < sl[xx])
        put(im, sn, mix(r_[4], "#ffffff", .6)); put(im, sn & dark, mix(r_[3], P["shadow"], .30))
    put(im, body & ~np.roll(body, 1, 0), r_[0])
    if fog:
        hz = int(base_y - 0.05 * amp) + np.round(3.5 * np.sin(2 * math.pi * 2 * np.arange(W) / W + rng.uniform(0, 6)) + 1.5 * np.sin(2 * math.pi * 5 * np.arange(W) / W + rng.uniform(0, 6))).astype(int); mid = mix(r_[1], P["haze"], .5); hc = mix(r_[2], P["haze"], .7)
        put(im, body & (yy > hz[xx]) & (yy <= hz[xx] + 6), mid); put(im, body & (yy > hz[xx] + 6), hc)
        put(im, body & (yy == hz[xx]) & checker(xx, yy), mid); put(im, body & (yy == hz[xx] + 6) & checker(xx, yy, 1), hc)
    return im


def hills(W, H, P, rng, base, t, base_y, amp, detail=0.0, outline=False, harmonics=(1, 2, 3, 5)):
    """rolling land: integer harmonics (so it wraps), a lit contour, a flat shade band lower down with one checker row at its border, tufts when detail is high"""
    r_ = ramp(base, t, P); x = np.arange(W); p = np.zeros(W)
    for k in harmonics:
        p += rng.uniform(.4, 1.0) / k ** .5 * np.sin(2 * math.pi * k * x / W + rng.uniform(0, 2 * math.pi))
    p = (p - p.min()) / (p.max() - p.min()); prof = np.round(base_y - amp * p).astype(int); im = blank(W, H); yy, xx = grid(W, H); body = yy >= prof[xx]; dep = yy - prof[xx]
    put(im, body, r_[2]); put(im, body & (dep > 22), r_[1]); put(im, body & (dep == 21) & checker(xx, yy), r_[1])
    put(im, body & ~np.roll(body, 1, 0), r_[0] if outline else r_[3])
    if detail > 0.5:
        tuft = body & (dep == 1) & (rng.random((H, W)) < 0.18); put(im, np.roll(tuft, -1, 0), r_[3])
    return im


def dunes(W, H, P, rng, base, t, base_y, amp):
    """smooth dune ridges: the face turned away from the light is one flat shade tone, ripple lines on the lit face, a light crest"""
    r_ = ramp(base, t, P); x = np.arange(W); p = sum(rng.uniform(.5, 1.0) / k * np.sin(2 * math.pi * k * x / W + rng.uniform(0, 6.28)) for k in (1, 2, 3))
    p = (p - p.min()) / (p.max() - p.min()); prof = np.round(base_y - amp * p).astype(int); im = blank(W, H); yy, xx = grid(W, H); body = yy >= prof[xx]
    k6 = np.ones(13) / 13; sm = np.convolve(np.concatenate([prof[-6:], prof, prof[:6]]).astype(float), k6, "valid")        # smoothed contour, wrapped
    slope = np.roll(sm, -4) - np.roll(sm, 4); away = (slope[xx] > 0.6)                             # contour sinks to the right (y grows): that face turns away from the upper-left light
    dep = yy - prof[xx]; put(im, body, r_[2]); put(im, body & away & (dep > 1) & (dep < 5), r_[1]); put(im, body & (dep > 20), r_[1]); put(im, body & (dep == 19) & checker(xx, yy), r_[1]); put(im, body & ~away & (dep > 6) & (dep % 7 == 0) & checker(xx, yy), r_[3])
    put(im, body & ~np.roll(body, 1, 0), r_[4]); return im


def waves(W, H, P, rng, base, t, top_y, frames=1):
    """sea: a flat water body below the horizon, rows of light dashes that widen toward the viewer; the frames shift the dashes 4 px, so any cycle of 4 frames loops"""
    r_ = ramp(base, t, P); out = []
    for f in range(frames):
        im = blank(W, H); yy, xx = grid(W, H); put(im, yy >= top_y, r_[2]); put(im, yy == top_y, r_[3]); put(im, yy > top_y + 20, r_[1])
        rows = [top_y + 5 + int(k ** 1.35 * 3) for k in range(1, 12)]
        for k, y in enumerate(rows):
            if y >= H - 1:
                break
            ln = 3 + k; sp = 16 + 4 * k; ph = (k * 7 + 4 * f * (1 + k % 2)) % sp
            m = np.zeros(W, bool)
            for s in range(0, W, sp):
                m[(s + ph + np.arange(ln)) % W] = True
            im[y, m] = (*r_[4 if k % 3 == 0 else 3], 255)
        out.append(im)
    return out


# ------------------------------------------------------------------ trees, buildings, ground
def _pine(im, x0, gy, h, r_, trunk):
    W = im.shape[1]; th = max(2, h // 6); tw = 1 if h < 22 else 2
    for dy in range(th):
        for dx in range(tw):
            im[gy - dy, (x0 + dx - tw // 2) % W] = (*trunk, 255)
    top = gy - h; bh = h - th
    for t in range(bh):
        y = top + t; u = (t + 1) / bh; half = int(1 + (h // 5) * u); s = (t * 3) // bh
        half = max(1, half - (2 if s == 1 else 1 if s == 2 else 0))
        if 0 <= y < im.shape[0]:
            for dx in range(-half, half + 1):
                col = r_[1]
                if dx >= half - (1 if half > 2 else 0):
                    col = r_[0]
                elif -half + 1 <= dx <= -half + 2 and half > 2:
                    col = r_[3]
                im[y, (x0 + dx) % W] = (*col, 255)


def _round_tree(im, x0, gy, h, r_, trunk):
    W, H = im.shape[1], im.shape[0]; th = max(3, h // 3); yy, xx = np.mgrid[0:H, 0:W]
    for dy in range(th):
        im[gy - dy, (x0) % W] = (*trunk, 255); im[gy - dy, (x0 + 1) % W] = (*trunk, 255)
    rad = max(4, (h - th) // 2); cy = gy - th - rad + 2; dx = wrapdx(xx, x0, W); m = dx ** 2 + (yy - cy) ** 2 <= rad * rad
    put(im, m, r_[1]); put(im, m & (dx ** 2 + (yy - cy + 1) ** 2 <= (rad - 1) ** 2) & (dx + (yy - cy) < rad * 0.35), r_[2])
    put(im, m & (dx + (yy - cy) < -rad * 0.5) & (dx ** 2 + (yy - cy) ** 2 <= (rad - 2) ** 2), r_[3]); put(im, m & ~(np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)) & (dx + (yy - cy) > rad * .3), r_[0])


def trees(W, H, P, rng, base, t, ground_y, hmin=16, hmax=30, n_clusters=4, per=6, loners=4, broadleaf=0.0, ground_t=None):
    """trees in clusters and loners (not a uniform scatter), drawn far to near so overlaps are right, on a ground band with tufts"""
    r_ = ramp(base, t, P); g = ramp(base, ground_t if ground_t is not None else t, P); im = blank(W, H); yy, xx = grid(W, H)
    prof = ground_y + np.round(1.5 * np.sin(2 * math.pi * 2 * np.arange(W) / W + rng.uniform(0, 6))).astype(int); items = []
    for c in rng.uniform(0, W, n_clusters):
        for _ in range(per):
            items.append((rng.uniform(0, 3), int(c + rng.normal(0, 14)) % W, int(rng.integers(hmin, hmax + 1)), bool(rng.random() < broadleaf)))
    for _ in range(loners):
        items.append((rng.uniform(0, 3), int(rng.integers(0, W)), int(rng.integers(hmin, hmax + 1)), bool(rng.random() < broadleaf)))
    items.sort(key=lambda q: q[0]); trunk = mix(g[0], "#4a3426", .35)
    put(im, yy >= prof[xx], g[1])
    for d, x, h, rnd in items:
        (_round_tree if rnd else _pine)(im, x, int(prof[x] + d), h, r_, trunk)
    put(im, np.roll((yy == prof[xx]) & (rng.random((H, W)) < 0.3), -1, 0) & (yy >= prof[xx] - 1), g[1])
    return im


def skyline(W, H, P, rng, base, t, base_y, hmin, hmax, detail=1.0, lit=0.18, ruins=False):
    """buildings of four shapes (slab, setback, tower with antenna, roof tank); a far skyline is a pure silhouette (detail 0); near ones get sparse window clusters in two sizes. ruins=True: crenellated towers and broken walls"""
    r_ = ramp(base, t, P); im = blank(W, H); yy, xx = grid(W, H); x = 0; win = mix(P["light"], "#ffe9a8", .5)
    first_h = None
    while x < W:
        w = int(rng.integers(14, 30)); last = W - x < 36; w = W - x if last else w; h = int(rng.integers(hmin, hmax)); h = first_h if (last and first_h) else h; first_h = first_h or h
        top = base_y - h; shape = int(rng.integers(0, 4))
        if ruins:
            shape = int(rng.choice([0, 4, 4, 5]))
        im[top:, x:x + w] = (*r_[2], 255); im[top, x:x + w] = (*r_[3], 255); im[top:, x + w - 1] = (*r_[1], 255)
        if shape == 1 and w > 12:                                      # setback: a narrower upper block
            sw = w - 8; im[max(top - 10, 0):top, x + 4:x + 4 + sw] = (*r_[2], 255); im[max(top - 10, 0), x + 4:x + 4 + sw] = (*r_[3], 255); im[max(top - 10, 0):top, x + 3 + sw] = (*r_[1], 255)
        elif shape == 2:                                               # antenna
            im[max(top - int(rng.integers(5, 12)), 0):top, x + w // 2] = (*r_[3], 255)
        elif shape == 3 and w > 10:                                    # roof tank
            im[top - 5:top, x + 3:x + 8] = (*r_[1], 255); im[top - 6, x + 3:x + 8] = (*r_[3], 255); im[top - 7:top, x + 5] = (*r_[0], 255)
        elif shape == 4:                                               # crenellated tower
            for cx in range(x, x + w, 4):
                im[top - 3:top, cx:cx + 2] = (*r_[2], 255); im[top - 3, cx:cx + 2] = (*r_[3], 255)
            if detail > 0.4 and w > 8:
                im[top + 6:top + 12, x + w // 2 - 1:x + w // 2 + 1] = (0, 0, 0, 0)
        elif shape == 5:                                               # broken wall: a stepped top with an arch opening
            im[top:top + 4, x + w // 2:x + w] = (0, 0, 0, 0)
            if detail > 0.4 and h > 18:
                ah = min(14, h - 6); ax = x + w // 2 - 3
                im[base_y - ah:base_y, ax:ax + 6] = (0, 0, 0, 0); im[base_y - ah - 3:base_y - ah, ax + 1:ax + 5] = (0, 0, 0, 0)
        if detail > 0.5 and not ruins:
            for cl_x in range(x + 2, x + w - 3, 8):                    # lit windows come in clusters: a block on or off
                if rng.random() < lit * 3:
                    for wy in range(top + 3, base_y - 3, 4):
                        if rng.random() < 0.55:
                            im[wy:wy + 2, cl_x:cl_x + 2] = (*win, 255)
                            if rng.random() < 0.4 and cl_x + 4 < x + w - 1:
                                im[wy:wy + 2, cl_x + 4:cl_x + 5] = (*win, 255)
        x += w
    return im


def ground(W, H, P, rng, base, base_y, tufts=True, tone=None):
    """near ground: a dark band, a light edge row, and a few 3-5 px tufts in two tones (not a comb of single blades)"""
    r_ = ramp(base, 0.0, P); im = blank(W, H); yy, xx = grid(W, H); prof = base_y + np.round(1.5 * np.sin(2 * math.pi * 4 * np.arange(W) / W + rng.uniform(0, 6))).astype(int)
    put(im, yy >= prof[xx], r_[1]); put(im, (yy >= prof[xx]) & (yy < prof[xx] + 2), r_[3]); put(im, (yy >= prof[xx] + 8) & (yy < prof[xx] + 9) & checker(xx, yy), r_[0]); put(im, yy >= prof[xx] + 9, r_[0])
    if tufts:
        for x0 in range(2, W - 6, 11):
            if rng.random() < 0.7:
                x1 = x0 + int(rng.integers(0, 8)); n = int(rng.integers(3, 6))
                for j in range(n):
                    hh = int(rng.integers(2, 6)); xj = (x1 + j - n // 2) % W; im[max(prof[xj] - hh, 0):prof[xj], xj] = (*r_[3 if j % 2 else 2], 255)
    return im


def foreground(W, H, P, rng, base, base_y, kind="rocks", n=5):
    """a silhouette layer for scroll above 1: dark rocks (flat top, lit upper left) or reeds, with gaps so the play area stays clear"""
    r_ = ramp(base, 0.0, P); im = blank(W, H); yy, xx = grid(W, H)
    if kind == "reeds":
        for x0 in rng.integers(0, W, n * 5):
            hh = int(rng.integers(12, 30)); lean = int(rng.integers(-2, 3))
            for j in range(hh):
                im[base_y - j, (int(x0) + (lean * j) // hh) % W] = (*r_[0], 255)
            for j in range(3):
                im[base_y - hh - j, (int(x0) + lean) % W] = (*r_[1], 255)
        put(im, yy >= base_y, r_[0]); return im
    for k in range(n):
        cx = int(k * W / n + rng.integers(-12, 12)); rx = int(rng.integers(8, 16)); ry = int(rng.integers(4, 8)); dx = wrapdx(xx, cx, W)
        m = (dx / rx) ** 2 + ((yy - (base_y - ry)) / ry) ** 2 <= 1; m &= yy <= base_y + 6; put(im, m, r_[1]); put(im, m & (dx / (rx - 2) + (yy - (base_y - ry)) / (ry - 1) < -0.9), r_[3]); put(im, m & ~np.roll(m, 1, 0), r_[0])
    put(im, yy >= base_y + 4, r_[0]); return im


# ------------------------------------------------------------------ space, caves
def planet(W, H, P, rng, base, cy=70, rad=34):
    """a planet disc with banded tones and a terminator (shadow side right), one ring of checker glow"""
    r_ = ramp(base, 0.0, P); im = blank(W, H); yy, xx = grid(W, H); cx = int(rng.integers(90, 230)); d2 = (xx - cx) ** 2 + (yy - cy) ** 2
    put(im, d2 <= (rad + 3) ** 2, mix(r_[1], P["top"], .5)); put(im, d2 <= rad ** 2, r_[2]); put(im, (d2 <= rad ** 2) & (((yy - cy) // 7) % 2 == 0), r_[3])
    put(im, (d2 <= rad ** 2) & ((xx - cx) ** 2 + (yy - cy) ** 2 > (rad - 14 + ((xx - cx) * 0)) ** 2) & ((xx - cx) > 6 + (yy - cy) ** 2 * 0.012), r_[1])
    put(im, (d2 <= (rad + 3) ** 2) & (d2 > rad ** 2) & checker(xx, yy), r_[4]); put(im, (d2 <= rad ** 2) & ~np.roll(d2 <= rad ** 2, 1, 0), r_[4]); return im


def nebula(W, H, P, rng, base, n=5):
    r_ = ramp(base, 0.3, P); im = blank(W, H); yy, xx = grid(W, H)
    for _ in range(n):
        cx, cy = int(rng.integers(0, W)), int(rng.integers(20, H - 60)); rx, ry = int(rng.integers(30, 70)), int(rng.integers(12, 28)); dx = wrapdx(xx, cx, W); d = (dx / rx) ** 2 + ((yy - cy) / ry) ** 2
        put(im, (d <= 1) & checker(xx, yy), r_[1]); put(im, d <= 0.55, r_[1]); put(im, (d <= 0.2), r_[2])
    return im


def ceiling(W, H, P, rng, base, t, depth=34, n=14, crystals=False, top0=0):
    """cave ceiling with stalactites (tapered triangles hanging from the top edge, wrapped) and, optionally, a few lit crystals"""
    r_ = ramp(base, t, P); im = blank(W, H); yy, xx = grid(W, H); prof = np.full(W, top0 + depth // 2) + np.round(3 * np.sin(2 * math.pi * 3 * np.arange(W) / W + rng.uniform(0, 6))).astype(int)
    put(im, yy <= prof[xx], r_[1])
    for _ in range(n):
        x0 = int(rng.integers(0, W)); ln = int(rng.integers(8, depth)); hw = int(rng.integers(2, 6))
        for j in range(ln):
            half = max(0, int(hw * (1 - j / ln)))
            for dx in range(-half, half + 1):
                im[prof[x0 % W] + j, (x0 + dx) % W] = (*(r_[3] if dx < -half // 2 and half > 1 else r_[1] if dx < half else r_[0]), 255)
    put(im, (yy <= prof[xx]) & (yy > prof[xx] - 2), r_[0])
    if crystals:
        for _ in range(5):
            x0 = int(rng.integers(0, W)); y0 = int(prof[x0 % W] + rng.integers(8, 20)); c = mix("#6ee7ff", P["light"], .3)
            for dy in range(-3, 4):
                for dx in range(-(3 - abs(dy)) // 2, (3 - abs(dy)) // 2 + 1):
                    im[(y0 + dy), (x0 + dx) % W] = (*c, 255)
    return im
