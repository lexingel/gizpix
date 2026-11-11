# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixdraw.parts - doors, windows, awnings, props, lantern light, smoke, flags. Everything takes its colours from the style."""
import math
import numpy as np
from .core import Cv


def _c(ramp, i): return ramp[max(0, min(len(ramp) - 1, i))]


def window(S, lit=False):
    g = S["ramps"]["glow" if lit else "glass"]; t = S["ramps"]["trim"]

    def f(lu, lv, w, h, sh):
        if lu < 1 or lu >= w - 1 or lv < 1 or lv >= h - 1 or abs(lu - w / 2) < 0.6 or abs(lv - h / 2) < 0.6: return _c(t, 3 + sh)
        return _c(g, (4 if (lu + (h - lv)) < w * 0.5 else 2) + sh)
    return f


def door(S):
    d = S["ramps"]["door"]; t = S["ramps"]["trim"]; g = S["ramps"]["glow"]

    def f(lu, lv, w, h, sh):
        if lu < 1 or lu >= w - 1 or lv >= h - 1: return _c(t, 3 + sh)
        if abs(lu - (w - 3.5)) < 0.7 and abs(lv - h * 0.45) < 0.7: return _c(g, 5 + sh)       # handle
        return _c(d, (1 if math.floor(lu) % 3 == 0 else 2) + sh)
    return f


def awning(S, t=0.0, L=10.0, stripe=5, slant=0.7):
    """awning material: slanted stripes that ripple with phase t (0..1), lit top rows, shaded lower rows, scalloped lower edge (None = empty pixel)"""
    a, b = S["ramps"]["awning_a"], S["ramps"]["awning_b"]; ph = 2 * math.pi * t

    def mat(u, v):
        if v > L - 1.6 and (math.floor(u + 1.4 * math.sin(ph - u * 0.14)) // 3) % 2 == 0: return None
        s = math.floor((u + slant * v * 1.4 + 2.4 * math.sin(ph - u * 0.14)) / stripe) % 2
        top, low = v < 2.2, v > L - 3.2
        ramp = a if s == 0 else b
        return _c(ramp, 5 if top else (2 if low else 4))
    return mat


# ---- screen-space props (drawn into a temporary canvas, ringed, then pasted) -------------------------------------------------------------------

def _paste(c, tmp, x0, y0, ring):
    tmp.ring(ring); a = tmp.a; m = a[..., 3] > 0; h, w = m.shape
    for y, x in zip(*np.nonzero(m)):
        if 0 <= y0 + y < c.h and 0 <= x0 + x < c.w: c.a[y0 + y, x0 + x] = a[y, x]


def sack(c, S, x, y, s=1.0, tied=True):
    """a grain sack standing on the screen point (x, y)"""
    r = S["ramps"]["cloth"]; rx, ry = max(3, round(5 * s)), max(4, round(7 * s)); tmp = Cv(2 * rx + 6, ry + 10)
    cx, by = rx + 3, ry + 7
    for j in range(-ry, 1):
        for i in range(-rx, rx + 1):
            e = (i / rx) ** 2 + ((j + ry * 0.45) / (ry * 0.62)) ** 2
            if e <= 1.0 and j > -ry + 1:
                li = 3 + int(round(-1.6 * (i / rx) - 0.8 * ((j + ry * 0.5) / ry))); tmp.px(cx + i, by + j, _c(r, li))
    if tied:
        for i in (-1, 0, 1): tmp.px(cx + i, by - ry + 1, _c(r, 1)); tmp.px(cx + i, by - ry, _c(r, 2))
        tmp.px(cx, by - ry - 1, _c(r, 0))
    tmp.px(cx - 1, by - ry // 2, _c(r, 5))                                     # highlight
    _paste(c, tmp, int(x - cx), int(y - by), S["outline"])


def barrel(c, S, x, y, w=10, h=14):
    """a barrel (staves, two hoops, lid) standing on the screen point (x, y)"""
    wd, hp = S["ramps"]["wood"], S["ramps"]["prop"]; tmp = Cv(w + 6, h + 8); cx, by = (w + 6) // 2, h + 5
    for j in range(h):
        t = j / (h - 1); half = w / 2 * (1 + 0.1 * math.sin(math.pi * t)) - 0.5
        for i in range(-int(half), int(half) + 1):
            nx = i / max(1, half); li = 3 + int(round(-1.7 * nx)); col = _c(wd, li - (1 if math.floor(i / 2.5) % 2 else 0))
            if j in (round(h * 0.22), round(h * 0.72)): col = _c(hp, 3 + int(round(-1.2 * nx)))
            tmp.px(cx + i, by - h + j + 2, col)
    for i in range(-w // 2 + 1, w // 2):                                       # lid
        for j in (-1, 0, 1):
            if (i / (w / 2)) ** 2 + (j / 1.6) ** 2 <= 1: tmp.px(cx + i, by - h + 1 + j, _c(wd, 5 - (1 if i > w // 4 else 0)))
    _paste(c, tmp, int(x - cx), int(y - by), S["outline"])


# ---- light and air --------------------------------------------------------------------------------------------------------------------------

def _palette_by_light(S):
    cols = {c for k in ("wall", "roof", "stone", "trim", "door", "prop", "wood", "cloth") for c in S["ramps"][k]}
    return sorted(cols, key=lambda c: 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2])


def light_steps(c, S, cx, cy, radius, steps=(3, 2, 1)):
    """lantern light done the pixel-art way: every nearby pixel steps up the style's own colours (solid bands, no additive halo)"""
    pal = np.array(_palette_by_light(S), float); n = len(pal)
    ys, xs = np.nonzero(c.a[..., 3] > 0)
    for y, x in zip(ys, xs):
        d = math.hypot(x - cx, y - cy)
        if d > radius or d < 2.2: continue
        cur = c.a[y, x, :3].astype(float); dist = np.sqrt(((pal - cur) ** 2).sum(1)); k = int(dist.argmin())
        if dist[k] > 40: continue
        step = steps[0] if d < radius * 0.5 else (steps[1] if d < radius * 0.75 else steps[2])
        c.a[y, x, :3] = pal[min(n - 1, k + step)].astype(np.uint8)


def lantern(c, S, x, y, t=0.0, sway=1):
    """hanging lantern with a flickering flame and stepped light; the flicker is periodic in t"""
    ph = 2 * math.pi * t; sw = round(sway * math.sin(ph - 0.7)); fl = 0.5 + 0.5 * math.sin(ph) + 0.3 * math.sin(3 * ph); g = S["ramps"]["glow"]
    flame = _c(g, 3 + int(fl * 2.4) % 3); dk = S["ramps"]["door"][0]
    for yy in range(int(y) - 5, int(y)): c.px(x + sw // 2, yy, dk)
    for j, row in enumerate(("kkk", "kok", "kok", "kkk")):
        for i, ch in enumerate(row): c.px(x - 1 + sw + i, y + j, dk if ch == "k" else flame)
    light_steps(c, S, x + sw, y + 1.5, 8.5 * (1 + 0.3 * (fl > 1.2) - 0.25 * (fl < 0.4)))


def smoke(c, S, x, y, t=0.0, puffs=3, rise=16):
    """chimney smoke: puffs grow, drift, then shrink and fade through the stone ramp (loops in t)"""
    r = S["ramps"]["stone"]
    for j in range(puffs):
        p = (t + j / puffs) % 1; s = p / 0.7 if p < 0.7 else 1 - (p - 0.7) / 0.3
        if s <= 0.05: continue
        cx = x + p * 8 + math.sin(p * 6 + j) * 1.5; cy = y - p * rise; rr = 0.7 + 3.6 * s; col = _c(r, 5 - int(p * 3)); hi = _c(r, 6)
        for yy in range(int(cy - rr) - 1, int(cy + rr) + 2):
            for xx in range(int(cx - rr) - 1, int(cx + rr) + 2):
                d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                if d2 < (rr - 0.4) ** 2: c.px(xx, yy, hi if (xx < cx - rr * 0.2 and yy < cy - rr * 0.2 and rr > 2.2) else col)


def flag(c, S, x, y, t=0.0, w=9, h=5):
    """a pennant on a pole whose tip is at (x, y)"""
    ph = 2 * math.pi * t; cl = S["ramps"]["awning_a"]; dk = S["ramps"]["door"][0]
    for yy in range(int(y), int(y) + h + 6): c.px(x, yy, dk)
    for i in range(1, w):
        off = round(1.4 * math.sin(ph - i * 0.7)); hh = max(1, round(h * (1 - i / (w * 1.15))))
        for j in range(hh): c.px(x + i, y + 1 + j + off, _c(cl, 4 - (1 if j == hh - 1 else 0)))
