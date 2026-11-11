# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixdraw.compose - several buildings + ground, path, trees, fences, wells in one picture, drawn back to front.

    compose([{"path": [[0, 90], [80, 96], [160, 90]], "w": 9},
             {"building": {"type": "inn"}, "x": 70, "y": 80},          # x, y = where the building stands (bottom centre of its footprint)
             {"tree": 18, "x": 140, "y": 84}, {"fence": [10, 60], "y": 100}], "dark_fantasy", size=(180, 120))

Items: building (a pixdraw spec), tree (size, kind round|pine), bush, well, fence ([x0, x1] + y, or axis "y": [y0, y1] + x), path ([[x, y], ...] + w). Items are sorted by y, so lower ones cover higher ones."""
import math
import numpy as np
from PIL import Image, ImageDraw
from .core import Cv, snap
from .styles import load_style
from .templates import scene, spec_of

KINDS = ("building", "tree", "bush", "well", "fence", "path")


def _h(x, y, k=0): return ((x * 73856093) ^ (y * 19349663) ^ (k * 83492791)) & 0xFFFF      # tiny deterministic hash: the same picture every run


def _grass(S):
    """grass ramp of the style (a green derived from the wall ramp's value range unless the style has its own 'grass')"""
    if "grass" not in S["ramps"]:
        from .styles import make_ramp
        w = S["ramps"]["wall"]; lo, hi = w[0][0] / 255, max(w[-1]) / 255 * 0.85
        S["ramps"]["grass"] = make_ramp([0.34, 0.24], 0.42, [max(0.12, lo), max(0.4, hi)], 7)
    return S["ramps"]["grass"]


def _pine(S, size):
    """a conifer: a short trunk and three stacked tiers, lit from the upper left"""
    G, Wd = _grass(S), S["ramps"]["wood"]; r = max(4, size // 3); h = max(18, size + 6); w = 2 * r + 5; c = Cv(w, h); cx = w // 2
    for y in range(h - 4, h): c.px(cx - 1, y, Wd[3]); c.px(cx, y, Wd[3]); c.px(cx + 1, y, Wd[1])
    for k, (top, wid) in enumerate(((0, r * 0.62), (h * 0.28, r * 0.85), (h * 0.5, r))):
        bot = h - 4 - (2 - k) * (h * 0.12) if k < 2 else h - 4
        for y in range(int(top), int(bot)):
            half = wid * (y - top) / max(1, bot - top)
            for x in range(int(cx - half), int(cx + half) + 1):
                f = (x - cx) / max(1, half); i = 1 if f > 0.45 else 2 if f > -0.15 else 3 if f > -0.6 else 4
                if _h(x, y) % 8 == 0: i = max(1, i - 1)
                if y > bot - 3: i = max(1, i - 1)                          # shadow under each tier
                c.px(x, y, G[i])
    c.tidy(); c.ring(S["outline"]); return c.img(), (w // 2, h - 1)


def _tree(S, size):
    G, Wd = _grass(S), S["ramps"]["wood"]; r = max(5, size // 2); w, h = 2 * r + 4, 2 * r + 9; c = Cv(w, h); cx, cy = w / 2 - 0.5, r + 1.5
    for y in range(h):                                                   # trunk
        for x in range(w):
            if y > cy + r - 2 and abs(x - cx) < 1.8: c.px(x, y, Wd[3] if x < cx else Wd[1])
    def leaf(x, y):
        dx, dy = (x - cx) / r, (y - cy) / r; d = math.hypot(dx, dy * 1.05)
        if d > 1: return None
        k = -(dx * 0.7 + dy * 0.9)                                       # light from the upper left
        i = 1 if k < -0.5 else 2 if k < 0.0 else 3 if k < 0.55 else 4
        if _h(x, y) % 9 == 0 and d < 0.85: i = max(1, i - 1)             # leaf clusters
        return G[i]
    c.plane([(0, 0), (w, 0), (w, h), (0, h)], lambda x, y: leaf(x, y)); c.tidy(); c.ring(S["outline"]); return c.img(), (w // 2, h - 1)


def _bush(S):
    G = _grass(S); c = Cv(15, 10)
    c.plane([(0, 9), (14, 9), (14, 4), (10, 0), (4, 0), (0, 4)], lambda x, y: G[1] if y > 6 else (G[3] if (x < 7 and y < 4) else G[2])); c.tidy(); c.ring(S["outline"]); return c.img(), (8, 9)


def _well(S):
    St, Wd, ro = S["ramps"]["stone"], S["ramps"]["wood"], S["ramps"]["roof"]; c = Cv(20, 24)
    c.plane([(3, 14), (16, 14), (16, 22), (3, 22)], lambda x, y: St[3] if x < 9 else St[2] if (y + x // 3) % 4 else St[1])           # drum
    c.plane([(3, 12), (16, 12), (16, 14), (3, 14)], lambda x, y: St[4])                                                               # rim
    c.plane([(5, 12), (14, 12), (14, 14), (5, 14)], lambda x, y: St[0])                                                               # dark water
    for px in (3, 15): c.plane([(px, 4), (px + 2, 4), (px + 2, 13), (px, 13)], lambda x, y: Wd[3] if x == px else Wd[2])              # posts
    c.plane([(1, 5), (10, 0), (18, 5)], lambda x, y: ro[3] if x < 10 else ro[2]); c.tidy(); c.ring(S["outline"]); return c.img(), (10, 22)


def _fence_y(S, y0, y1):
    """a fence running away from the viewer: stocky posts every 10 px with a rail between them"""
    Wd = S["ramps"]["wood"]; n = int(abs(y1 - y0)) + 1; c = Cv(8, n + 8)
    for y in range(0, n + 1, 10):
        if y + 10 <= n + 6:
            for dy in range(6, 12): c.px(5, y + dy, Wd[2])                   # rail to the next post
        for dy in range(7):
            for dx in range(4): c.px(2 + dx, y + dy, Wd[4] if dy == 0 else Wd[3] if dx < 2 else Wd[1])
    c.tidy(); c.ring(S["outline"]); return c.img()


def _fence(S, x0, x1):
    Wd = S["ramps"]["wood"]; n = int(abs(x1 - x0)) + 1; c = Cv(n + 1, 10)
    for y in (4, 7):                                                     # two rails
        for x in range(n): c.px(x, y, Wd[2])
    for x in range(0, n + 1, 7):                                         # posts
        for y in range(1, 10): c.px(x, y, Wd[4] if y == 1 else Wd[3]); c.px(x + 1, y, Wd[1])
    c.tidy(); c.ring(S["outline"]); return c.img()


def _ground(S, size):
    G = _grass(S); w, h = size; c = Cv(w, h)
    c.plane([(0, 0), (w, 0), (w, h), (0, h)], lambda x, y: G[1] if _h(x, y) % 23 == 0 else G[3] if _h(x, y, 1) % 31 == 0 else G[2]); return c


def _path(S, c, pts, wd):
    St = S["ramps"]["stone"]; m = Image.new("L", (c.w, c.h), 0); d = ImageDraw.Draw(m); p = [tuple(q) for q in pts]
    d.line(p, fill=255, width=int(wd), joint="curve")
    for q in p: d.ellipse((q[0] - wd / 2, q[1] - wd / 2, q[0] + wd / 2, q[1] + wd / 2), fill=255)
    a = np.array(m) > 0; e = a.copy(); pad = np.pad(a, 1)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)): e &= pad[1 + dy:1 + dy + c.h, 1 + dx:1 + dx + c.w]
    ys, xs = np.nonzero(a)
    for y, x in zip(ys, xs): c.px(x, y, St[4] if _h(x, y, 2) % 11 == 0 else St[2] if not e[y, x] else St[3])


def _check(it):
    ks = [k for k in KINDS if k in it]
    if len(ks) != 1: raise ValueError(f"each item needs exactly one of {', '.join(KINDS)} (got {sorted(it)})")
    if ks[0] == "path":
        if len(it["path"]) < 2: raise ValueError("path needs at least two [x, y] points")
    elif ks[0] == "fence" and it.get("axis") == "y":
        if "x" not in it: raise ValueError("a fence with axis y needs x")
    elif "y" not in it or ("x" not in it and ks[0] != "fence"): raise ValueError(f"{ks[0]} needs x and y" if ks[0] != "fence" else "fence needs y")
    if ks[0] == "fence" and len(it["fence"]) != 2: raise ValueError("fence is [x0, x1]")
    return ks[0]


def compose(items, style, size=(180, 120), frames=1):
    """list of RGBA frames (same size, loops); buildings animate, the rest is still"""
    S = load_style(style); kinds = [_check(it) for it in items]; out = []
    sprites = []                                                         # (foot_y, [frame sprites], foot_x_in_sprite, foot_y_in_sprite, x, y)
    for it, k in zip(items, kinds):
        if k == "path": continue
        if k == "building":
            sp = spec_of(it["building"]); ims = [scene(sp, S, i / frames) for i in range(frames)]
            bb = [im.getbbox() for im in ims]; b = (min(q[0] for q in bb), min(q[1] for q in bb), max(q[2] for q in bb), max(q[3] for q in bb))
            fr = [im.crop(b) for im in ims]; fx, fy = fr[0].width // 2, fr[0].height - 3
        elif k == "tree":
            if it.get("kind", "round") not in ("round", "pine"): raise ValueError(f"unknown tree kind {it['kind']!r}; choose round or pine")
            im, (fx, fy) = (_pine if it.get("kind") == "pine" else _tree)(S, int(it["tree"])); fr = [im] * frames
        elif k == "bush": im, (fx, fy) = _bush(S); fr = [im] * frames
        elif k == "well": im, (fx, fy) = _well(S); fr = [im] * frames
        elif it.get("axis") == "y": im = _fence_y(S, *it["fence"]); fr = [im] * frames; fx, fy = 4, im.height - 1; it = {**it, "y": max(it["fence"])}
        else: im = _fence(S, *it["fence"]); fr = [im] * frames; fx, fy = 0, im.height - 1; it = {**it, "x": min(it["fence"])}
        sprites.append((it["y"], fr, fx, fy, it["x"], it["y"], k))
    for t in range(frames):
        g = _ground(S, size)
        for it, k in zip(items, kinds):
            if k == "path": _path(S, g, it["path"], it.get("w", 9))
        sh = Image.new("RGBA", size, (0, 0, 0, 0)); d = ImageDraw.Draw(sh); sc = _grass(S)[1]
        for fy_, fr, fx, fy, x, y, k in sprites:                         # soft ground shadow of trees, bushes and wells (buildings carry their own)
            if k in ("tree", "bush", "well"): d.ellipse((x - fr[0].width * 0.45, y - 2, x + fr[0].width * 0.5, y + 3), fill=(*sc, 255))
        im = Image.alpha_composite(g.img(), sh)
        for fy_, fr, fx, fy, x, y, k in sorted(sprites, key=lambda s: s[0]):
            im.paste(fr[t], (int(round(x - fx)), int(round(y - fy))), fr[t])
        out.append(snap(im, S["palette"]) if S["palette"] else im)
    return out
