# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixart.core - an indexed pixel-art canvas that does the craft for you. Pure numpy + PIL + scipy.

The idea: the caller (a person or an AI agent) says WHAT is where - masks built from on-grid shapes - and which colour ramp and form each part has.
The canvas does the pixel craft the books ask for: hue-shifted ramps, one light for every part, form shading in a few flat tones, tone clusters without
specks, a 1 px light-aware outline, cast shadows between parts, optional inner anti-aliasing and checker dither, and a lint that measures the result.
Every pixel is (ramp, tone), never a free colour, so the palette stays small and exact. KNOWLEDGE.md has the rules and where they come from."""
import colorsys, importlib.util, json, math, os
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOL, WARM = 0.70, 0.14                     # hue shadows drift to (blue-violet) and highlights drift to (yellow)
LIGHTS = {"tl": (-0.5, -0.6), "tr": (0.5, -0.6), "top": (0.0, -0.75), "l": (-0.75, -0.2), "r": (0.75, -0.2), "front": (0.0, -0.3)}
# light value (0..1) -> tone index, per ramp length: the base tone gets the most room, the highlight the least
THRESH = {2: [.45], 3: [.3, .85], 4: [.25, .70, .94], 5: [.12, .36, .70, .94], 6: [.1, .28, .5, .74, .95]}
PALETTES = {   # well-known public palettes, for export(palette=...)
    "pico8": "000000 1d2b53 7e2553 008751 ab5236 5f574f c2c3c7 fff1e8 ff004d ffa300 ffec27 00e436 29adff 83769c ff77a8 ffccaa",
    "sweetie16": "1a1c2c 5d275d b13e53 ef7d57 ffcd75 a7f070 38b764 257179 29366f 3b5dc9 41a6f6 73eff7 f4f4f4 94b0c2 566c86 333c57",
    "db16": "140c1c 442434 30346d 4e4a4e 854c30 346524 d04648 757161 597dce d27d2c 8595a1 6daa2c d2aa99 6dc2ca dad45e deeed6",
    "gameboy": "0f380f 306230 8bac0f 9bbc0f",
}


def rgb(c):
    if isinstance(c, str):
        c = c.lstrip("#"); c = "".join(ch * 2 for ch in c) if len(c) == 3 else c      # "#888" = "#888888"
        if len(c) != 6: raise ValueError(f"colour {c!r}: write it as #rrggbb or #rgb")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(int(v) for v in c[:3])


def _hsv(h, s, v): return tuple(int(round(x * 255)) for x in colorsys.hsv_to_rgb(h % 1, min(1, max(0, s)), min(1, max(0, v))))
def _toward(h, target, amt): d = (target - h + 0.5) % 1 - 0.5; return h + max(-amt, min(amt, d))      # at most `amt` of the wheel, the short way, never past the target
def lum(c): return (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255


class Ramp:
    """the tones of one material, dark -> light, plus its own outline colour (`line`, tone -1)"""
    def __init__(s, cols, line=None, name="", base=None):
        s.cols = [rgb(c) for c in cols]; s.name = name; s.base = (len(s.cols) - 1) // 2 if base is None else base      # base = the tone a flat fill uses
        if line: s.line = rgb(line)
        else:
            h, sa, v = colorsys.rgb_to_hsv(*[x / 255 for x in s.cols[0]]); s.line = _hsv(_toward(h, COOL, 0.04) if sa > 0.08 else COOL, min(1, sa + 0.15), v * 0.55)
    def __len__(s): return len(s.cols)
    def __repr__(s): return f"Ramp {s.name or ''} line #%02x%02x%02x tones " % s.line + " ".join("#%02x%02x%02x" % c for c in s.cols) + f" base={s.base}"


def ramp(base, n=4, shift=1.0, contrast=1.0, name=""):
    """a ramp around one base colour (the local colour = tone (n-1)//2; a near-white base becomes the top tone). Shadows get darker, a little more saturated and drift toward blue-violet;
    highlights get lighter, less saturated and drift toward yellow (shift=0 keeps the hue). contrast > 1 widens the value steps (small sprites, strong light)."""
    h, s, v = colorsys.rgb_to_hsv(*[x / 255 for x in rgb(base)]); b = n - 1 if (v > 0.92 and s < 0.25) else (n - 1) // 2; grey = s < 0.08      # a near-white base has no room above it: it becomes the top tone
    yellow = 1.25 if (not grey and 0.10 < h < 0.20) else 1.0            # yellow needs a bigger step to read
    cols = []
    for i in range(n):
        k = abs(i - b)
        if i < b: hh, ss, vv = _toward(h, COOL, 0.03 * k * shift), s + (1 - s) * (0.05 if b == n - 1 else 0.14) * k, v * ((0.84 if b == n - 1 else 0.74) ** (k * contrast * yellow))     # whites shade gently
        elif i > b: hh, ss, vv = _toward(h, WARM, 0.035 * k * shift), s * ((0.6 if v > 0.9 else 0.74) ** k), v + (1 - v) * (1 - 0.62 ** (k * contrast)) + 0.02 * k
        else: hh, ss, vv = h, s, v
        if grey: hh, ss = (COOL, 0.05 + 0.04 * k) if i < b else (WARM, 0.03 + 0.03 * k) if i > b else (h, s)
        cols.append(_hsv(hh, ss, vv))
    return Ramp(cols, name=name, base=b)


def ramp9(hue, step=20, n=9, name=""):
    """the wide 9-swatch ramp of the Slynyrd Pixelblog: hue (degrees) at the darkest swatch, +step degrees per swatch toward the light; saturation rises to 75 in the
    middle and falls to 15, brightness 15 -> 100. Vivid and strongly hue-shifted: the look of bright game art. n < 9 keeps evenly spread swatches (n=5: every second).
    A flat fill uses the middle swatch.
    Where the recipe would make a swatch darker than the one before it (blue ramps), that swatch is eased lighter so the tones stay in order."""
    S = (20, 40, 60, 70, 75, 60, 45, 30, 15); B = (15, 30, 45, 60, 70, 80, 90, 95, 100); idx = [round(i * 8 / (n - 1)) for i in range(n)] if n > 1 else [4]
    cols = []
    for i in idx:
        h, sa, b = ((hue + step * (i - 4)) % 360) / 360, S[i] / 100, B[i] / 100; col = _hsv(h, sa, b)
        while cols and lum(col) < lum(cols[-1]) + 0.03 and (sa > 0.1 or b < 1):       # pure blues are darker than their neighbours: ease saturation, then brightness, until the order holds
            sa = max(0.1, sa - 0.05); b = min(1.0, b + 0.02); col = _hsv(h, sa, b)
        cols.append(col)
    return Ramp(cols, name=name)


# ---- masks: plain numpy bool arrays the size of the canvas; combine with | & ~ ----
_house = None
def house(name, n=None):
    """a ramp of the HOUSE palette (house_palette.json: measured from the game's own item icons), with the game's dark line colour and the game's tone shares:
    steel iron silver leather wood gold copper red navy sapphire purple teal (iron = dark worn weapon metal, steel = brighter polished metal). A hex colour picks the family with the nearest tone. n = fewer tones (2..7, evenly picked).
    Fills with a house ramp put the tone borders where the game puts them (steel and leather mostly dark with a small highlight, gold mostly bright)."""
    global _house
    if _house is None: _house = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "house_palette.json"), encoding="utf-8"))
    R = _house["ramps"]
    if name not in R:
        try: c = rgb(name)
        except Exception: raise KeyError(f"house: no ramp {name!r}; choose {' '.join(R)} or give a hex colour")
        name = min(R, key=lambda k: min(sum((a - b) ** 2 for a, b in zip(rgb(t), c)) for t in R[k]["tones"]))
    tones, share = R[name]["tones"], R[name]["share"]; m = len(tones); n = min(n or m, m); idx = [round(i * (m - 1) / max(n - 1, 1)) for i in range(n)]
    grp = [sum(sh for j, sh in enumerate(share) if min(range(n), key=lambda i: abs(idx[i] - j)) == g) for g in range(n)]; out = Ramp([tones[i] for i in idx], line=_house["ink"], name=name)
    z = np.linspace(-1, 1, 64); X, Y = np.meshgrid(z, z); k = X * X + Y * Y < 1; lx, ly = LIGHTS["tl"]; lz = math.sqrt(1 - lx * lx - ly * ly)
    Lv = np.clip(X * lx + Y * ly + np.sqrt(np.clip(1 - X * X - Y * Y, 0, 1)) * lz, 0, 1)[k]      # ponytail: tone borders come from a top-left lit ball; other forms and lights get the same borders, measure per form if it shows
    out.th = [max(float(np.quantile(Lv, min(q, 0.995))), 0.06 + 0.04 * i) for i, q in enumerate(np.cumsum(grp)[:-1])]; return out      # the floor keeps the darkest tones in use: a ball's far side is one flat 0


def shift(m, dx, dy):
    out = np.zeros_like(m); h, w = m.shape[:2]; src = m[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)]
    out[max(0, dy):max(0, dy) + src.shape[0], max(0, dx):max(0, dx) + src.shape[1]] = src; return out


def grow(m, n=1, diag=False): return m.copy() if n < 1 else ndi.binary_dilation(m, ndi.generate_binary_structure(2, 2 if diag else 1), iterations=n)
def shrink(m, n=1, diag=False): return m.copy() if n < 1 else ndi.binary_erosion(m, ndi.generate_binary_structure(2, 2 if diag else 1), iterations=n)


def rim(m, dx, dy):
    """the crescent of m left uncovered when a copy of m moves by (dx, dy): rim(gem, 2, 1) = a sliver 2 px wide on the left and 1 px on the top.
    For edge lights on gems and glass, the far inner wall of a ring, the back of a lens seen at an angle. The part both copies share is `m & shift(m, dx, dy)`."""
    return m & ~shift(m, dx, dy)


def palette_of(path, n=32):
    """the n most used colours of an image as hex strings, dark to light: the house palette of existing game art.
    Pick tones from it for Ramp([...]), or pass it as save(path, palette=palette_of(ref)) to snap a drawing to it."""
    a = np.array(Image.open(path).convert("RGBA")); cols, cnt = np.unique(a[a[..., 3] > 0][:, :3], axis=0, return_counts=True)
    return ["#%02x%02x%02x" % tuple(c) for c in sorted(cols[np.argsort(-cnt)[:n]].tolist(), key=lum)]


def flipx(m, axis=None):
    """mirror a mask left-right about the canvas middle, or about the pixel edge x = axis"""
    if axis is None: return m[:, ::-1].copy()
    out = np.zeros_like(m); w = m.shape[1]; xs = np.arange(w); src = 2 * axis - 1 - xs; ok = (src >= 0) & (src < w); out[:, xs[ok]] = m[:, src[ok]]; return out


def sym(m, axis=None): return m | flipx(m, axis)


def _pixel_perfect(pts):
    """drop the corner pixel of every L so a 1 px line never doubles up"""
    out = []; i = 0
    while i < len(pts):
        if 0 < i < len(pts) - 1 and out:
            p, c, n = out[-1], pts[i], pts[i + 1]
            if (p[0] == c[0] or p[1] == c[1]) and (n[0] == c[0] or n[1] == c[1]) and p[0] != n[0] and p[1] != n[1]: i += 1; continue
        out.append(pts[i]); i += 1
    return out


def _bres(p, q):
    (x0, y0), (x1, y1) = p, q; dx, dy = abs(x1 - x0), -abs(y1 - y0); sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1); e = dx + dy; out = []
    while True:
        out.append((x0, y0))
        if (x0, y0) == (x1, y1): return out
        e2 = 2 * e
        if e2 >= dy: e += dy; x0 += sx
        if e2 <= dx: e += dx; y0 += sy


def _nb(a, fill):
    """the 8 neighbours of every cell as 8 arrays: N S W E, then the four diagonals"""
    p = np.pad(a, 1, constant_values=fill); H, W = a.shape
    return [p[1 + dy:H + 1 + dy, 1 + dx:W + 1 + dx] for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1))]


_lint_mod = None
def _pixel_lint():
    global _lint_mod
    if _lint_mod is None:
        sp = importlib.util.spec_from_file_location("pixel_lint", os.path.join(ROOT, "check", "pixel_lint.py")); _lint_mod = importlib.util.module_from_spec(sp); sp.loader.exec_module(_lint_mod)
    return _lint_mod.lint


class Canvas:
    """w x h pixels; light = a name from LIGHTS or (lx, ly) pointing TOWARD the light (y up is negative). One light for the whole picture."""
    def __init__(s, w, h, light="tl"):
        s.w, s.h = w, h; s.rid = np.full((h, w), -1, np.int16); s.tone = np.zeros((h, w), np.int8)
        s.lock = np.zeros((h, w), bool); s.ol = np.zeros((h, w), bool); s.ramps = []; s._auto = {}
        lx, ly = LIGHTS[light] if isinstance(light, str) else light; s.L = (lx, ly, math.sqrt(max(0.05, 1 - lx * lx - ly * ly)))
        s.yy, s.xx = np.mgrid[0:h, 0:w]

    # ---- ramps ----
    def _r(s, r):
        if not isinstance(r, Ramp):
            key = str(r); r = s._auto.get(key) or s._auto.setdefault(key, ramp(r))
        for i, q in enumerate(s.ramps):
            if q is r: return i
        s.ramps.append(r); return len(s.ramps) - 1

    # ---- shapes (all return masks; x, y = top-left pixel, w, h in pixels) ----
    def empty(s): return np.zeros((s.h, s.w), bool)

    def rect(s, x, y, w, h, r=0):
        m = s.empty(); m[max(0, y):max(0, y + h), max(0, x):max(0, x + w)] = True
        for i in range(r):
            for j in range(r):
                if (r - i - 0.5) ** 2 + (r - j - 0.5) ** 2 > (r - 0.5) ** 2 + 0.26:
                    for px, py in ((x + i, y + j), (x + w - 1 - i, y + j), (x + i, y + h - 1 - j), (x + w - 1 - i, y + h - 1 - j)):
                        if 0 <= px < s.w and 0 <= py < s.h: m[py, px] = False
        return m

    def oval(s, x, y, w, h, angle=0):
        """ellipse filling the box; even sizes give the classic symmetric pixel circles (8 -> rows 4 6 8 8 8 8 6 4). angle (degrees, clockwise on screen) tilts it about its centre."""
        dx, dy = s.xx + 0.5 - (x + w / 2), s.yy + 0.5 - (y + h / 2)
        if angle: a = math.radians(angle); dx, dy = dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)
        return (dx / (w / 2)) ** 2 + (dy / (h / 2)) ** 2 <= 1.0

    def ring(s, x, y, w, h, t=2, angle=0, t2=None):
        """an oval band: t px thick at the sides, t2 px at the top and bottom (default t). Finger rings, hoops, cage wires, rims; t != t2 = a band seen at an angle."""
        t2 = t if t2 is None else t2; return s.oval(x, y, w, h, angle) & ~s.oval(x + t, y + t2, w - 2 * t, h - 2 * t2, angle)

    def poly(s, pts):
        im = Image.new("1", (s.w, s.h), 0); ImageDraw.Draw(im).polygon([(int(x), int(y)) for x, y in pts], fill=1, outline=1); return np.array(im, bool)

    def _path(s, pts, w):
        m = s.empty()
        for x, y in _pixel_perfect(pts):
            if 0 <= x < s.w and 0 <= y < s.h: m[y, x] = True
        w = int(round(w))
        if w > 1: m = ndi.binary_dilation(m, np.ones((w, w), bool))
        return m

    def line(s, pts, w=1):
        """pixel-perfect polyline through integer points, w px thick"""
        pts = [(int(round(x)), int(round(y))) for x, y in pts]; path = []
        for p, q in zip(pts, pts[1:]): path += _bres(p, q)[(1 if path else 0):]
        return s._path(path or pts, w)

    def _spline(s, pts, closed):
        P = [tuple(map(float, p)) for p in pts]; n = len(P); out = []; idx = (lambda i: i % n) if closed else (lambda i: min(max(i, 0), n - 1))
        for i in range(n if closed else n - 1):
            p0, p1, p2, p3 = P[idx(i - 1)], P[idx(i)], P[idx(i + 1)], P[idx(i + 2)]
            for t in np.linspace(0, 1, 24, endpoint=False):
                out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t * t + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t ** 3) for k in (0, 1)))
        return out + [P[0] if closed else P[-1]]

    def curve(s, pts, w=1, closed=False, w1=None):
        """smooth pixel-perfect curve THROUGH the points (Catmull-Rom spline); closed=True joins the ends.
        w1 = the width at the last point: the curve tapers from w to w1 (tentacles, tails, horns, vines; widths may be fractions)."""
        if w1 is not None:
            sm = s._spline(pts, closed); n = len(sm) - 1; m = s.empty()
            for i in range(n): m |= s.limb(sm[i], sm[i + 1], w + (w1 - w) * i / n, w + (w1 - w) * (i + 1) / n)
            return m
        samples = [(int(round(x)), int(round(y))) for x, y in s._spline(pts, closed)]; path = []
        for p, q in zip(samples, samples[1:]):
            if p != q: path += _bres(p, q)[(1 if path else 0):]
        return s._path(path or samples[:1], w)

    def blob(s, pts):
        """a filled organic shape whose edge passes through the points (points may lie outside the canvas)"""
        im = Image.new("1", (s.w, s.h), 0); ImageDraw.Draw(im).polygon([(round(x), round(y)) for x, y in s._spline(pts, True)], fill=1, outline=1); return np.array(im, bool)

    def limb(s, p0, p1, w0, w1=None):
        """a tapered capsule from point p0 to p1 (float coordinates), w0 px wide at p0 and w1 at p1: arms, legs, tails, necks, blades. Use with pixart.rig joints: c.limb(*j["arm_f_up"], 4, 3)"""
        (x0, y0), (x1, y1) = p0, p1; w1 = w0 if w1 is None else w1; dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy
        px, py = s.xx + 0.5, s.yy + 0.5; t = np.clip(((px - x0) * dx + (py - y0) * dy) / L2, 0, 1) if L2 > 1e-9 else np.zeros((s.h, s.w))
        return np.hypot(px - (x0 + dx * t), py - (y0 + dy * t)) <= (w0 + (w1 - w0) * t) / 2 + 0.05

    def pipe(s, pts, r=None, w=4, w1=None, caps="round", span=None, lo=0, hi=None, closed=False):
        """a round bar that follows a smooth curve through pts and tapers from w px to w1 px: horns, handles, hafts, tails, tentacles, bent blades. Returns (mask, u, v):
        u = 0..1 along the curve, v = -1..1 across it (+ = right of the direction of travel), so parts can be placed in the bar's own space: a band is `m & (abs(u - 0.4) < 0.05)`,
        the far edge `m & (v > 0.5)`. With a ramp r the bar is shaded across its width as a cylinder under the canvas light. caps: round | flat (cut square at both ends).
        span=(u0, u1) keeps only that stretch: call again with another ramp and a span to paint a metal band or a grip over the bar.
        closed=True joins the ends into a loop: a torus-shaded ring of any shape (key bow, shield rim, bracelet, a tilted ring from c.spaced points of an oval)."""
        sm = np.array(s._spline(pts, closed), float); seg = np.diff(sm, axis=0); ln = np.hypot(seg[:, 0], seg[:, 1]); keep = ln > 1e-9; a = sm[:-1][keep]; seg = seg[keep]; ln = ln[keep]
        if not len(ln): return s.empty(), np.zeros((s.h, s.w)), np.zeros((s.h, s.w))
        cum = np.concatenate([[0], np.cumsum(ln)]); tot = cum[-1]; px, py = s.xx + 0.5, s.yy + 0.5; best = np.full((s.h, s.w), 1e9); u = np.zeros((s.h, s.w)); side = np.zeros((s.h, s.w)); tx = np.zeros((s.h, s.w)); ty = np.zeros((s.h, s.w)); over = np.zeros((s.h, s.w), bool)
        for i in range(len(ln)):
            dx, dy = seg[i]; t0 = ((px - a[i, 0]) * dx + (py - a[i, 1]) * dy) / ln[i] ** 2; t = np.clip(t0, 0, 1); ex, ey = px - (a[i, 0] + dx * t), py - (a[i, 1] + dy * t); d = np.hypot(ex, ey); k = d < best
            best[k] = d[k]; u[k] = ((cum[i] + t * ln[i]) / tot)[k]; side[k] = np.sign(dx * ey - dy * ex)[k]; tx[k] = dx / ln[i]; ty[k] = dy / ln[i]; over[k] = ((i == 0) & (t0 < 0) | (i == len(ln) - 1) & (t0 > 1))[k]
        half = np.maximum((w + ((w if w1 is None else w1) - w) * u) / 2, 0.5); m = best <= half + 0.05; v = np.clip(side * best / half, -1, 1)
        if caps == "flat" and not closed: m &= ~over
        if span: m &= (u >= span[0]) & (u <= span[1])
        if r is not None and m.any():
            ri = s._r(r); R = s.ramps[ri]; n = len(R); lx, ly, lz = s.L; nz = np.sqrt(1 - v * v)
            t = s._quant(np.clip(v * (-ty * lx + tx * ly) + nz * lz + 0.08, 0, 1), n, th=getattr(R, "th", None)); t = np.clip(s._declutter(t, m, 2), lo, n - 1 if hi is None else hi)
            s.rid[m] = ri; s.tone[m] = t[m]; s.ol[m] = False; s.lock[m] = False
        return m, u, v

    def spaced(s, pts, n, closed=False, offset=0.0):
        """n points evenly spaced along the smooth curve through pts (whole pixels): rivets round a rim, studs on a strap, beads, stitches, teeth.
        closed=True treats pts as a loop (n points all the way round); offset 0..1 slides them along. Example: for x, y in c.spaced(rim_pts, 8, closed=True): c.px(x, y, iron, 5)"""
        sm = np.array(s._spline(pts, closed), float); ln = np.hypot(*np.diff(sm, axis=0).T); cum = np.concatenate([[0], np.cumsum(ln)]); tot = cum[-1]
        at = ((np.arange(n) + offset) / n * tot) if closed else (np.linspace(0, 1, n) * tot if n > 1 else np.array([tot / 2]))
        return [(int(round(np.interp(a % tot if closed else a, cum, sm[:, 0]) - 0.5)), int(round(np.interp(a % tot if closed else a, cum, sm[:, 1]) - 0.5))) for a in at]

    def ellipse_pts(s, cx, cy, rx, ry, angle=0, n=16):
        """n points round an ellipse (centre, radii, tilt in degrees): feed them to pipe(closed=True) for a shaded ring or to spaced() for rivets"""
        t = np.linspace(0, 2 * np.pi, n, endpoint=False); ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle)); x, y = rx * np.cos(t), ry * np.sin(t)
        return [(cx + a * ca - b * sa, cy + a * sa + b * ca) for a, b in zip(x, y)]

    def segments(s, m, u, n, gap=0, lit=True):
        """cut the painted mask m into n plates along the coordinate u (u from pipe(), or s.xx / s.yy / any number per pixel): finger lames, armour bands, plank rows, scales on a tail.
        Each cut becomes a seam (dark line, lit lip beyond it, see seam()); gap = extra empty pixels at each cut. Returns the list of plate masks, first to last along u."""
        vals = u[m]
        if not len(vals) or n < 2: return [m]
        edges = np.linspace(vals.min(), vals.max() + 1e-9, n + 1); idx = np.clip(np.searchsorted(edges, u, side="right") - 1, 0, n - 1); plates = [m & (idx == i) for i in range(n)]
        cut = s.empty()
        for a, b in zip(plates, plates[1:]): cut |= a & grow(b)
        if gap: s.erase(grow(cut, gap - 1) & m); plates = [p & ~grow(cut, gap - 1) for p in plates]
        elif lit: s.seam(cut, within=m)
        else: s.retone(cut, delta=-1)
        return plates

    def flip(s):
        """mirror the whole painted canvas left to right, in place (draw one boot, then flip a copy and paste it). Light stays where it was drawn, so shade the copy again if that matters."""
        for k in ("rid", "tone", "ol", "lock"): setattr(s, k, getattr(s, k)[:, ::-1].copy())
        return s

    def chain(s, j, names, w0, w1=None):
        """a tapered run of limbs over several bones (neck, tail, wing finger): w0 px at the start of the first bone, w1 at the end of the last"""
        w1 = w0 if w1 is None else w1; n = len(names); m = s.empty()
        for i, nm in enumerate(names): m |= s.limb(*j[nm], w0 + (w1 - w0) * i / n, w0 + (w1 - w0) * (i + 1) / n)
        return m

    def membrane(s, root, tips, sag=0.25):
        """a wing or fin skin: from `root` (the wrist / shoulder) out to each finger tip in `tips` (in order), the edge between two tips scalloped inward by `sag`.
        Paint it BEFORE the finger bones, in a lighter or more orange ramp than the body, flat or form="grad"; darken alternate panels with retone for depth."""
        pts = [root]
        for a, b in zip(tips, tips[1:]):
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2; pts += [a, (mx + (root[0] - mx) * sag, my + (root[1] - my) * sag)]
        return s.poly(pts + [tips[-1]])

    def bow(s, hand, string_hand=None, length=30, angle=180, belly=4, arrow=True):
        """a bow held at `hand` (the grip), standing along `angle` (rig degrees, 180 = upright), facing +x. Returns (bow, string, arrow) masks.
        string_hand = None: at rest, a straight string and no arrow. With a point: the string is a V to that hand, the tips are pulled back and the arrow runs
        from that hand through the grip. Paint the bow before outline(); paint string and arrow AFTER outline() (1 px lines must not be outlined)."""
        a = math.radians(angle); ux, uy = math.sin(a), math.cos(a); nx, ny = -uy, ux; nx, ny = (nx, ny) if nx < 0 else (-nx, -ny)      # (nx, ny) points back toward the archer
        pull = 0 if string_hand is None else min(length * 0.12, math.hypot(string_hand[0] - hand[0], string_hand[1] - hand[1]) * 0.15)
        tips = [(hand[0] + ux * k * length / 2 + nx * (belly + pull), hand[1] + uy * k * length / 2 + ny * (belly + pull)) for k in (1, -1)]
        bow = s.curve([tips[0], ((tips[0][0] + hand[0]) / 2 + nx * belly * 0.3, (tips[0][1] + hand[1]) / 2 + ny * belly * 0.3), hand, ((tips[1][0] + hand[0]) / 2 + nx * belly * 0.3, (tips[1][1] + hand[1]) / 2 + ny * belly * 0.3), tips[1]], w=2)
        if string_hand is None: return bow, s.line([tips[0], tips[1]]), s.empty()
        string = s.line([tips[0], string_hand]) | s.line([string_hand, tips[1]])
        dx, dy = hand[0] - string_hand[0], hand[1] - string_hand[1]; d = max(math.hypot(dx, dy), 1e-6)
        return bow, string, (s.line([string_hand, (hand[0] + dx / d * 4, hand[1] + dy / d * 4)]) if arrow else s.empty())

    def crescent(s, cx, cy, r, a0, a1, w=3):
        """a slash trail: an arc of radius r around (cx, cy) from angle a0 to a1 (rig degrees: 0 down, 90 right, 180 up), a 1 px point at a0 (where the swing began) growing to w px at a1 (where the blade is now); the outer edge is the path of the weapon tip.
        Paint it flat in 2-3 light tones, no outline, for 1-2 frames; it follows the path of the weapon tip."""
        px, py = s.xx + 0.5 - cx, s.yy + 0.5 - cy; ang = np.degrees(np.arctan2(px, py)); lo, hi = min(a0, a1), max(a0, a1)
        f = ((ang - lo) % 360) / max(hi - lo, 1e-6); inside = f <= 1; g = f if a1 >= a0 else 1 - f; th = w * np.minimum(g * 1.15, 1) * np.minimum((1 - g) * 12 + 0.5, 1)      # grows from a 1 px point at a0 to full width near a1
        return inside & (np.abs(np.hypot(px, py) - r + th / 2) <= th / 2) & (th > 0.6)

    def grid(s, rows, x=0, y=0, ch=None):
        """mask from text rows: every character that is not '.' or ' ' (or only the characters in `ch`)"""
        m = s.empty()
        for j, r in enumerate(rows):
            for i, c in enumerate(r):
                if (c in ch if ch else c not in ". ") and 0 <= x + i < s.w and 0 <= y + j < s.h: m[y + j, x + i] = True
        return m

    # ---- paint ----
    def _bbox(s, m, box):
        if box: x, y, w, h = box; return x, y, x + w - 1, y + h - 1
        ys, xs = np.nonzero(m); return xs.min(), ys.min(), xs.max(), ys.max()

    def _span(s, m, axis):
        """per-row (axis x) or per-column (axis y) position -1..1 across the mask's own extent on that line: follows tapered shapes"""
        a = m if axis == "x" else m.T; idx = np.arange(a.shape[1])[None, :]; lo = np.where(a, idx, 10 ** 6).min(1, keepdims=True); hi = np.where(a, idx, -1).max(1, keepdims=True)
        n = (idx + 0.5 - (lo + hi + 1) / 2) / np.maximum((hi - lo + 1) / 2, 0.5); return n if axis == "x" else n.T

    def _quant(s, Lv, n, dither=0, even=False, th=None):
        th = [k / n for k in range(1, n)] if even else th or THRESH.get(n) or [(k / n) ** 0.8 for k in range(1, n)]
        if dither: Lv = Lv + (np.array([[0.0, 0.5], [0.75, 0.25]])[s.yy % 2, s.xx % 2] - 0.375) * dither / n
        return np.searchsorted(th, Lv, side="right").astype(np.int8)

    def _declutter(s, t, m, min_px=3):
        """tone clusters smaller than min_px join their biggest neighbour tone: no specks, no ragged band edges"""
        for _ in range(2):
            for v in np.unique(t[m]):
                lab, k = ndi.label(m & (t == v))
                if k < 2 and (lab > 0).sum() >= min_px: continue
                sizes = ndi.sum(np.ones_like(lab), lab, range(1, k + 1))
                for i in np.nonzero(sizes < min_px)[0] + 1:
                    c = lab == i; ring = grow(c) & m & ~c
                    if ring.any(): vals, cnt = np.unique(t[ring], return_counts=True); t[c] = vals[cnt.argmax()]
        return t

    def fill(s, m, r, form="flat", tone=None, lo=0, hi=None, box=None, depth=None, axis="x", bands=None, dither=0, rim=False, shadow=False, sep=False, lock=False, centre=None):
        """paint mask m with ramp r (a Ramp, or a hex colour = automatic 4-tone ramp). Returns m.
        form: flat (one tone: `tone`, default the base) | ball (sphere/ellipsoid over the mask's box, or `box`) | tube (cylinder; axis 'x' = upright, shade runs across)
              | puff (rounded from the outline inward, any shape; `depth` px = how far in the rounding goes, small = a bevel) | slab (flat with a lit and a dark 1 px edge)
              | grad (even tone steps along the light direction) | bands (tones listed in `bands`, e.g. "0122310", spread across `axis`: metal, glass)
              | glow (lit from INSIDE: brightest at `centre` = (x, y), default the middle of the mask, darker toward its edge: lantern glass, flames, magic, lit gems)
        lo, hi clamp the tones used. dither 0..1 = checker dither at the tone borders. rim = reflected light on the far edge.
        shadow = darken what lies just beyond this part, away from the light (cast shadow). sep = a dark line of the underlying colour around this part."""
        ri = s._r(r); R = s.ramps[ri]; n = len(R); m = m & np.ones((s.h, s.w), bool)
        if not m.any(): return m
        lx, ly, lz = s.L; sx, sy = int(np.sign(lx)), int(np.sign(ly)); under = (s.rid >= 0) & ~m
        if sep: e = grow(m) & under; s.tone[e] = -1
        if shadow:
            e = (shift(m, -sx, -sy) | shift(m, 0, -sy if sy else 1)) & under & ~s.ol & (s.tone > 0); s.tone[e] -= 1
        if form == "flat": t = np.full((s.h, s.w), R.base if tone is None else tone, np.int8)
        elif form == "ball":
            x0, y0, x1, y1 = s._bbox(m, box); nx = (s.xx + 0.5 - (x0 + x1 + 1) / 2) / ((x1 - x0 + 1) / 2); ny = (s.yy + 0.5 - (y0 + y1 + 1) / 2) / ((y1 - y0 + 1) / 2)
            r2 = nx * nx + ny * ny; k = np.sqrt(np.maximum(r2, 1)); nx, ny = nx / k, ny / k; nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0, 1))
            t = s._quant(np.clip(nx * lx + ny * ly + nz * lz, 0, 1), n, dither, th=getattr(R, 'th', None)); t = t if dither else s._declutter(t, m, 2)
        elif form == "tube":
            nn = np.clip(s._span(m, axis), -1, 1); nz = np.sqrt(1 - nn * nn); t = s._quant(np.clip(nn * (lx if axis == "x" else ly) + nz * lz + 0.08, 0, 1), n, dither, th=getattr(R, 'th', None)); t = t if dither else s._declutter(t, m, 2)
        elif form == "puff":
            d = ndi.distance_transform_edt(m) - 0.5; k = depth or max(d.max(), 1); u = np.clip(d / k, 0, 1); z = ndi.gaussian_filter(np.sqrt(1 - (1 - u) ** 2) * k, 0.7)
            gy, gx = np.gradient(z); nrm = np.sqrt(gx * gx + gy * gy + 1); t = s._quant(np.clip((-gx * lx - gy * ly + lz) / nrm, 0, 1), n, dither, th=getattr(R, 'th', None)); t = t if dither else s._declutter(t, m)
        elif form == "slab":
            b = R.base if tone is None else tone; t = np.full((s.h, s.w), b, np.int8)
            lit = m & ((~shift(m, -sx, 0) if sx else False) | (~shift(m, 0, -sy) if sy else False)); dark = m & ((~shift(m, sx, 0) if sx else False) | (~shift(m, 0, sy) if sy else False)) & ~lit
            t[lit] = b + 1; t[dark] = b - 1
        elif form == "grad":
            p = s.xx * lx + s.yy * ly; a, b = p[m].min(), p[m].max(); t = s._quant((p - a) / max(b - a, 1e-6) * 0.999, n, dither, even=True)
        elif form == "bands":
            f = np.clip((s._span(m, axis) + 1) / 2, 0, 0.999); t = np.array([int(c) for c in bands], np.int8)[(f * len(bands)).astype(int)]
        elif form == "glow":
            ys, xs = np.nonzero(m); cx, cy = centre or (xs.mean() + 0.5, ys.mean() + 0.5); d = np.hypot(s.xx + 0.5 - cx, s.yy + 0.5 - cy)
            t = s._quant(np.clip(1 - d / max(d[m].max(), 1e-6), 0, 0.999), n, dither, even=True)
        else: raise ValueError(f"unknown form {form!r}; choose flat, ball, tube, puff, slab, grad, bands or glow")
        t = np.clip(t, -1 if tone == -1 else lo, n - 1 if hi is None else hi)                     # tone=-1 = the ramp's outline colour
        if rim and n >= 4:
            ys, xs = np.nonzero(m); far = ((s.xx - xs.mean()) * lx + (s.yy - ys.mean()) * ly) < -0.35 * max(np.ptp(xs), np.ptp(ys), 1) / 2
            e = m & ~shrink(m) & far & (t == 0); t[e] = 1
        s.rid[m] = ri; s.tone[m] = t[m]; s.ol[m] = False; s.lock[m] = lock; return m

    def px(s, x, y, r, tone=None):
        """one deliberate pixel (eye, glint); protected from clean-up and counted as intended by the lint"""
        if 0 <= x < s.w and 0 <= y < s.h: ri = s._r(r); R = s.ramps[ri]; s.rid[y, x] = ri; s.tone[y, x] = R.base if tone is None else max(-1, min(len(R) - 1, tone)); s.lock[y, x] = True      # a tone past the ramp's end takes the end tone; s.ol[y, x] = False

    def put(s, rows, key, x=0, y=0):
        """hand-placed pixels from text rows; key = {"a": (ramp, tone), ...}; '.' and ' ' are skipped. For faces, small details, anything a shape cannot say."""
        for j, row in enumerate(rows):
            for i, c in enumerate(row):
                if c not in ". ":
                    if c not in key: raise KeyError(f"put: letter {c!r} at row {j}, column {i} is not in the key ({' '.join(key)})")
                    s.px(x + i, y + j, *key[c])

    def retone(s, m, delta=None, tone=None):
        """shift or set the tone of already painted pixels (texture marks, a darker far-side limb, a light band)"""
        m = m & (s.rid >= 0) & ~s.ol
        for i, R in enumerate(s.ramps):
            k = m & (s.rid == i); s.tone[k] = np.clip(s.tone[k].astype(int) + delta if tone is None else tone, 0, len(R) - 1)
        s.lock[m] = True; return m

    def texture(s, m, cell=4, seed=0, deltas=(-1, 0, 0, 1)):
        """hammered metal, stone chips, bark, mottled hide: split the painted mask m into irregular cells about `cell` px across and shift each cell's tone by a random pick
        from `deltas`. Use after fill, before outline; the same seed gives the same texture. Then hand-place a few glints and dents with px so it does not read as noise."""
        m = m & (s.rid >= 0) & ~s.ol; ys, xs = np.nonzero(m)
        if not len(ys): return m
        rng = np.random.default_rng(seed); k = min(len(ys), max(2, len(ys) // (cell * cell))); pick = rng.choice(len(ys), k, replace=False)
        seeds = np.zeros((s.h, s.w), int); seeds[ys[pick], xs[pick]] = np.arange(1, k + 1); iy, ix = ndi.distance_transform_edt(seeds == 0, return_distances=False, return_indices=True)
        d = rng.choice(deltas, k)[seeds[iy, ix] - 1]
        for v in set(d[m].tolist()) - {0}: s.retone(m & (d == v), delta=v)
        return m

    def seam(s, m, within=None):
        """a panel line, plate edge, rib or groove: the pixels of m go one tone darker and the pixels just beyond them, away from the light, one tone lighter (the edge that catches the light)"""
        sx, sy = int(np.sign(s.L[0])), int(np.sign(s.L[1])); lit = (shift(m, -sx, 0) | shift(m, 0, -sy)) & ~m
        if within is not None: m, lit = m & within, lit & within
        s.retone(lit, delta=1); return s.retone(m, delta=-1)

    def links(s, pts, r, tones=(2, 0), period=2):
        """a chain or beaded cord along a polyline: 1 px wide, `period` px of each tone in turn. Paint it AFTER outline() so it stays thin. Returns its mask."""
        pts = [(int(round(x)), int(round(y))) for x, y in pts]; path = []
        for p, q in zip(pts, pts[1:]): path += _bres(p, q)[(1 if path else 0):]
        path = _pixel_perfect(path)
        for i, (x, y) in enumerate(path): s.px(x, y, r, tones[(i // period) % len(tones)])
        return s._path(path, 1)

    def erase(s, m): s.rid[m] = -1; s.ol[m] = False; s.lock[m] = False; return m

    # ---- finishing passes ----
    def outline(s, mode="selout", color=None, mask=None, rim=None, lines=None):
        """1 px outline on the empty pixels around the silhouette (never doubles at corners).
        selout: each part's own dark line colour, one step lighter where the edge faces the light | dark: own line colour everywhere | black: one colour (`color`, default a tinted near-black)
        rim = (ramp, tone): the outline pixels that face the light take this colour instead (a pale rim light on the lit edge, dark line elsewhere: glass, ghosts, moonlit things)
        lines = {ramp: colour}: the outline next to that part takes that colour, in any mode (a dark red line round a flame, a deep blue one round a gem, a brown one round parchment)"""
        sil = (s.rid >= 0) if mask is None else mask; free = s.rid < 0; ring = grow(sil) & ~sil & free; done = s.empty(); lx, ly, _ = s.L
        if mode == "black": gi = s._r(Ramp([color or "#1c1420"], line=color or "#1c1420"))
        if rim: rr = s._r(rim[0])
        lmap = [(s._r(R), s._r(Ramp([col], line=col))) for R, col in (lines or {}).items()]
        for dx, dy in sorted(((1, 0), (-1, 0), (0, 1), (0, -1)), key=lambda d: d[0] * lx + d[1] * ly):      # shadow-side sources first: corners go dark
            cand = ring & shift(sil, dx, dy) & ~done; ys, xs = np.nonzero(cand)
            if rim and dx * lx + dy * ly > 0.3: s.rid[ys, xs] = rr; s.tone[ys, xs] = rim[1]
            elif mode == "black": s.rid[ys, xs] = gi; s.tone[ys, xs] = 0
            else: s.rid[ys, xs] = s.rid[ys - dy, xs - dx]; s.tone[ys, xs] = 0 if (mode == "selout" and dx * lx + dy * ly > 0.3) else -1
            for R, li in lmap:
                k = s.rid[ys - dy, xs - dx] == R if not (rim and dx * lx + dy * ly > 0.3) else np.zeros(len(ys), bool)
                s.rid[ys[k], xs[k]] = li; s.tone[ys[k], xs[k]] = 0
            done |= cand
        s.ol |= ring; return ring

    def aa(s):
        """inner anti-aliasing, the careful kind: the fill pixel in the inside corner of an outline stair goes one tone darker. Never touches the outer edge. For sprites of about 48 px and up."""
        o = s.ol; c = ~o & (s.rid >= 0) & ~s.lock & (s.tone > 0)
        k = c & ((shift(o, 1, 0) | shift(o, -1, 0)) & (shift(o, 0, 1) | shift(o, 0, -1))); s.tone[k] -= 1; return k

    def _defects(s):
        """tone-cluster faults among the pixels the engine shaded (hand-placed, re-toned and outline pixels are left out): (specks, spurs, target key per pixel, bands)
        speck = a pixel with no same-colour neighbour | spur = a 1 px bump of one tone into the next tone of the same material | band = a hairline tone band: 1 px wide for 5 px or more, squeezed between two other tones of its own material"""
        body = (s.rid >= 0) & ~s.ol; key = np.where(body, s.rid.astype(int) * 32 + s.tone + 1, -1); nb = _nb(key, -1); free = body & ~s.lock
        n4 = sum((x == key).astype(int) for x in nb[:4]); n8 = n4 + sum((x == key).astype(int) for x in nb[4:]); to = np.full(key.shape, -1); spur = s.empty()
        for v in nb[:4]:
            k = free & ~spur & (n4 == 1) & (n8 >= 2) & (v >= 0) & (v != key) & (v // 32 == key // 32) & (sum((x == v).astype(int) for x in nb[:4]) == 3); spur |= k; to[k] = v[k]
        speck = free & (n8 == 0)
        for y, x in zip(*np.nonzero(speck)):
            vs = [int(v[y, x]) for v in nb[:4] if v[y, x] >= 0]; own = [v for v in vs if v // 32 == key[y, x] // 32] or vs
            if own: to[y, x] = max(set(own), key=own.count)
        band = s.empty()
        for v in np.unique(key[free]):
            reg = key == v; mid = [(x >= 0) & (x != v) & (x // 32 == v // 32) for x in nb[:4]]; mid = (mid[0] & mid[1]) | (mid[2] & mid[3])      # other tones of the same material on both sides
            lab, k = ndi.label(reg & ~ndi.binary_opening(reg, np.ones((2, 2), bool)) & free & mid, np.ones((3, 3)))
            if k: band |= np.isin(lab, np.nonzero(np.bincount(lab.ravel())[1:] >= 5)[0] + 1)
        return speck & (to >= 0), spur, to, band

    def tidy(s, bands=False):
        """clean-up of the engine's own shading, safe to call any time after the fills (before or after outline): single-pixel tone specks join their surroundings and 1 px bumps
        on a tone border are pushed back, so tone edges run clean. Hand-placed pixels (px, put, retone, texture, lock=True) and the silhouette are never touched.
        bands=True also dissolves hairline tone bands (1 px wide, 5 px or longer) into the tone beside them: fewer, broader tone shapes. It also eats thin rim lights and slab edges
        the engine made, so look at the result and keep it only if it reads better. Returns {"specks": n, "spurs": n, "bands": n}."""
        out = {"specks": 0, "spurs": 0, "bands": 0}
        for _ in range(3):
            speck, spur, to, _b = s._defects(); k = speck | spur
            if not k.any(): break
            out["specks"] += int(speck.sum()); out["spurs"] += int(spur.sum()); s.rid[k] = to[k] // 32; s.tone[k] = to[k] % 32 - 1
        if bands:
            band = s._defects()[3]; out["bands"] = int(band.sum()); key = np.where((s.rid >= 0) & ~s.ol, s.rid.astype(int) * 32 + s.tone + 1, -1)
            for _ in range(4):                                   # grow the neighbouring tones into the band, one ring at a time
                if not band.any(): break
                nb = _nb(np.where(band, -1, key), -1)[:4]; done = s.empty()
                for y, x in zip(*np.nonzero(band)):
                    vs = [int(v[y, x]) for v in nb if v[y, x] >= 0 and v[y, x] // 32 == key[y, x] // 32]
                    if vs: key[y, x] = min(vs, key=lambda v: (-vs.count(v), abs(v - key[y, x]))); done[y, x] = True
                band &= ~done
                if not done.any(): break
            k = (s.rid >= 0) & ~s.ol; s.tone[k] = (key[k] % 32 - 1).astype(np.int8)
            if out["bands"]: s.tidy()
        return out

    def paste(s, other, x=0, y=0):
        """draw another canvas on top at (x, y): build each object on its own canvas (own outline), then compose the scene"""
        for i, R in enumerate(other.ramps):
            ri = s._r(R); ys, xs = np.nonzero(other.rid == i); ok = (ys + y >= 0) & (ys + y < s.h) & (xs + x >= 0) & (xs + x < s.w); ys, xs = ys[ok], xs[ok]
            s.rid[ys + y, xs + x] = ri; s.tone[ys + y, xs + x] = other.tone[ys, xs]; s.ol[ys + y, xs + x] = other.ol[ys, xs]; s.lock[ys + y, xs + x] = True

    def text(s, string, x, y, r, font="5x7", bold=False, style="flat", tone=None, shadow=False, spacing=1, mono=False, r2=None):
        """pixel lettering; (x, y) = top-left of the capital height. See font.py. Returns the mask of the letters (pass it to outline(mask=...))."""
        from .font import draw_text
        return draw_text(s, string, x, y, r, font, bold, style, tone, shadow, spacing, mono, r2)

    def merge_colors(s, dist=30):
        """palette clean-up: of two used colours closer than `dist` (sum of RGB differences) the rarer becomes the commoner one (shared darks, shared highlights).
        Changes the Ramp objects; on animations call it on one frame only, with ramps shared by all frames."""
        from collections import Counter
        cnt = Counter(); slots = {}
        for i, R in enumerate(s.ramps):
            for t in np.unique(s.tone[s.rid == i]):
                col = R.line if t < 0 else R.cols[t]; cnt[col] += int(((s.rid == i) & (s.tone == t)).sum()); slots.setdefault(col, []).append((R, int(t)))
        merged = 0
        for col in sorted(cnt, key=cnt.get):
            near = [o for o in cnt if o != col and cnt[o] >= cnt[col] and sum(abs(a - b) for a, b in zip(o, col)) < dist]
            if not near: continue
            to = max(near, key=cnt.get); merged += 1; cnt[to] += cnt.pop(col)
            for R, t in slots.pop(col):
                if t < 0: R.line = to
                else: R.cols[t] = to
                slots.setdefault(to, []).append((R, t))
        return merged

    # ---- output ----
    def rgba(s):
        a = np.zeros((s.h, s.w, 4), np.uint8)
        for i, R in enumerate(s.ramps):
            m = s.rid == i
            if m.any(): a[m, :3] = np.array([R.line] + R.cols, np.uint8)[np.clip(s.tone[m].astype(int) + 1, 0, len(R))]; a[m, 3] = 255
        return a

    def image(s, scale=1, bg=None, palette=None):
        """PIL image; scale = whole-number nearest-neighbour enlargement; bg = flat background colour; palette = a PALETTES name or a list of colours to snap to"""
        a = s.rgba()
        if palette:
            pal = np.array([rgb(c) for c in (PALETTES[palette].split() if isinstance(palette, str) else palette)], float); m = a[..., 3] > 0
            a[m, :3] = pal[((a[m][:, None, :3].astype(float) - pal[None]) ** 2).sum(-1).argmin(1)].astype(np.uint8)
        im = Image.fromarray(a)
        if bg is not None: b = Image.new("RGBA", im.size, (*rgb(bg), 255)); b.alpha_composite(im); im = b
        return im.resize((s.w * scale, s.h * scale), Image.NEAREST) if scale != 1 else im

    def save(s, path, scale=1, bg=None, palette=None):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True); s.image(scale, bg, palette).save(path); return path

    def silhouette(s, path, scale=4):
        """the one-colour shape on mid grey: check THIS before shading anything. If the subject cannot be named from it, fix the masses, not the colours."""
        a = s.rgba(); a[a[..., 3] > 0, :3] = (16, 16, 20); im = Image.new("RGBA", (s.w, s.h), (150, 150, 156, 255)); im.alpha_composite(Image.fromarray(a))
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True); im.resize((s.w * scale, s.h * scale), Image.NEAREST).save(path); return path

    def preview(s, path, palette=None):
        """the review sheet to LOOK at: big on mid grey, 1x and 2x on dark / light / brown, the one-colour silhouette, greyscale, and the palette"""
        im = s.image(palette=palette); big = max(2, min(16, 320 // max(s.w, s.h))); pad = 8
        W = s.w * big + pad * 3 + max(s.w * 3 + pad * 2, s.w * 4); H = max(s.h * big, s.h * 7 + pad * 5) + pad * 2 + 14
        sheet = Image.new("RGBA", (W, H), (96, 96, 104, 255)); sheet.alpha_composite(im.resize((s.w * big, s.h * big), Image.NEAREST), (pad, pad))
        x = s.w * big + pad * 2; y = pad
        for bg in ((24, 20, 32), (232, 228, 216), (110, 84, 60)):
            t = Image.new("RGBA", (s.w * 3 + pad * 2, s.h * 2), (*bg, 255)); t.alpha_composite(im, (2, s.h // 2)); t.alpha_composite(im.resize((s.w * 2, s.h * 2), Image.NEAREST), (s.w + pad, 0)); sheet.alpha_composite(t, (x, y)); y += s.h * 2 + pad
        a = np.array(im); sil = a.copy(); sil[a[..., 3] > 0, :3] = (16, 16, 20); g = a.copy(); g[..., :3] = (a[..., :3] @ np.array([0.299, 0.587, 0.114]))[..., None]
        for k, arr in enumerate((sil, g)): t = Image.new("RGBA", (s.w * 2, s.h * 2), (200, 200, 200, 255)); t.alpha_composite(Image.fromarray(arr).resize((s.w * 2, s.h * 2), Image.NEAREST)); sheet.alpha_composite(t, (x + k * (s.w * 2 + pad // 2), y))
        cols = sorted({tuple(c) for c in a[a[..., 3] > 0][:, :3].tolist()}, key=lum); d = ImageDraw.Draw(sheet); sw = max(4, min(12, (W - 2 * pad) // max(1, len(cols))))
        for i, c in enumerate(cols): d.rectangle([pad + i * sw, H - 14, pad + (i + 1) * sw - 1, H - 4], fill=(*c, 255))
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True); sheet.save(path); return path

    def lint(s, budget=None, quiet=False):
        """measure the picture against the rules (KNOWLEDGE.md): returns (numbers, flags). Flags are advice: fix them or decide they are intended."""
        a = s.rgba(); op = a[..., 3] > 0; r, flags = _pixel_lint()(a)
        if not op.any(): return r, flags
        cols = sorted({tuple(c) for c in a[op][:, :3].tolist()}, key=lum); budget = budget or (16 if max(s.w, s.h) <= 48 else 32); r["colors"] = len(cols)
        if len(cols) > budget: flags.append(f"{len(cols)} colours, budget {budget}: drop tones or share ramps")
        near = [(p, q) for i, p in enumerate(cols) for q in cols[i + 1:] if sum(abs(x - y) for x, y in zip(p, q)) < 30]
        if near: flags.append("near-duplicate colours (merge or push apart): " + ", ".join("#%02x%02x%02x~#%02x%02x%02x" % (*p, *q) for p, q in near[:4]))
        if (0, 0, 0) in cols: flags.append("pure black used: take a tinted dark instead")
        full = op.all()
        body0 = op & ~s.ol
        if not full and s.ol.any() and (body0[0].any() or body0[-1].any() or body0[:, 0].any() or body0[:, -1].any()): flags.append("the sprite touches the canvas edge (" + ", ".join(n for n, e in (("top", body0[0]), ("bottom", body0[-1]), ("left", body0[:, 0]), ("right", body0[:, -1])) if e.any()) + "): leave 1 px for the outline")
        sil = op & ~s.ol
        if not full and sil.sum() > 30:
            lost = sil & ~ndi.binary_opening(sil, np.ones((2, 2), bool)) & ~s.lock; r["thin_share"] = round(float(lost.sum() / sil.sum()), 2)      # hand-placed and re-toned pixels are intended; they still count as body around their neighbours
            if r["thin_share"] > 0.15: flags.append(f"thin parts: {int(lost.sum())} px are only 1 px wide (cannot be shaded; fine for a blade tip or a string)")
        for i, R in enumerate(s.ramps):
            used = sorted(set(s.tone[(s.rid == i) & (s.tone >= 0)].tolist()))
            for p, q in zip(used, used[1:]):
                if lum(R.cols[q]) - lum(R.cols[p]) < 0.05: flags.append(f"ramp {R.name or i}: tones {p} and {q} are too close in brightness to tell apart")
        a16 = a[..., :3].astype(int); part = (s.rid >= 0) & ~s.ol; close = 0
        for dx, dy in ((1, 0), (0, 1)):
            q = part & shift(part, dx, dy) & (s.rid != shift(s.rid, dx, dy)) & (np.abs(a16 - shift(a16, dx, dy)).sum(-1) < 40); close += int(q.sum())
        if close > 3: flags.append(f"{close} px where two different materials touch in nearly the same colour (they merge: clamp one with lo= / hi=, or change a base colour)")
        body = (s.rid >= 0) & ~s.ol & ~s.lock; key = s.rid.astype(int) * 16 + s.tone; alone = body.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)): alone &= shift(key + 1000, dx, dy) != key + 1000
        r["orphan_px"] = int(alone.sum())
        if alone.sum() > max(2, 0.01 * op.sum()): flags.append(f"{int(alone.sum())} single-pixel tone specks (tidy() removes them), e.g. at {[(int(x), int(y)) for y, x in zip(*np.nonzero(alone))][:5]}")
        _sp, spur, _to, band = s._defects(); r["spur_px"] = int(spur.sum()); r["band_px"] = int(band.sum())
        if r["spur_px"] > max(2, 0.01 * op.sum()): flags.append(f"{r['spur_px']} one-pixel bumps on tone borders (tidy() pushes them back)")
        if not quiet:
            print(f"lint {s.w}x{s.h}: {r['colors']} colours, opaque {r['opaque_px']} px, pillow {r.get('pillow')}, light_x {r.get('light_x')}, stair_break {r.get('stair_break')}, thick_line {r.get('thick_line')}, band_px {r['band_px']}")
            print("  flags: " + ("; ".join(flags) if flags else "none"))
        return r, flags


def lint_all(frames, budget=None):
    """lint every frame of an animation or sheet (a list of canvases, or rows of them): prints and returns {flag: number of frames that raise it}"""
    flat = [f for r in frames for f in (r if isinstance(r, (list, tuple)) else [r])]; out = {}
    for f in flat:
        for fl in f.lint(budget, quiet=True)[1]: key = fl.split(":")[0].split(" (")[0]; key = "".join(ch for ch in key if not ch.isdigit()).strip(); out[key] = out.get(key, 0) + 1
    print(f"lint of {len(flat)} frames: " + ("; ".join(f"{k} x{v}" for k, v in sorted(out.items(), key=lambda kv: -kv[1])) or "no flags")); return out


def export(frames, out_dir, name, scale=1, ms=120, palette=None):
    """a Canvas or a list of Canvases (animation frames, all the same size) -> NAME.png (frame 0), and for animations NAME.gif + NAME_sheet.png + NAME_sheet.json.
    ms = one delay, or a list with a delay per frame (hold the peaks longer). Returns the paths."""
    import sys
    if ROOT not in sys.path: sys.path.insert(0, ROOT)
    from pixdraw.export import export as _ex
    frames = frames if isinstance(frames, (list, tuple)) else [frames]
    return _ex([f.image(palette=palette) for f in frames], out_dir, name, ms=ms, scale=scale)


def sheet(rows, path, scale=1, pad=0, bg=None):
    """a sprite sheet from rows of frames ([[Canvas, ...], ...]: one row per direction or action, one column per frame; all canvases the same size).
    bg=None keeps it transparent (the game file); a colour makes a review sheet. Returns (path, cell width, cell height)."""
    w, h = rows[0][0].w * scale, rows[0][0].h * scale; n = max(len(r) for r in rows)
    im = Image.new("RGBA", (n * (w + pad) + pad, len(rows) * (h + pad) + pad), (*rgb(bg), 255) if bg is not None else (0, 0, 0, 0))
    for y, r in enumerate(rows):
        for x, f in enumerate(r): im.alpha_composite(f.image(scale), (pad + x * (w + pad), pad + y * (h + pad)))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True); im.save(path); return path, w, h


def strip(frames, path, scale=4, bg=(96, 96, 104), sil=False):
    """all frames side by side, enlarged `scale` times, for looking at an animation as stills (this is the image for the blind naming check).
    sil=True draws every frame as its one-colour silhouette: the silhouette-first check for an animation."""
    ims = [f.image(scale) for f in frames]
    if sil: ims = [Image.merge("RGBA", (*Image.new("RGB", im.size, (16, 16, 20)).split(), im.split()[3])) for im in ims]
    w, h = ims[0].size; sh = Image.new("RGBA", (len(ims) * (w + 4) + 4, h + 8), (*bg, 255))
    for i, im in enumerate(ims): sh.alpha_composite(im, (4 + i * (w + 4), 4))
    sh.save(path); return path
