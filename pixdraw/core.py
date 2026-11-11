# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixdraw.core - canvas, projections, textured faces. Pure numpy + PIL.

A scene is described in 3-D world units (x = width, y = depth away from the viewer, z = up). A projection maps those three axes to screen
vectors; a face is any flat quad/polygon in the world with two direction vectors, textured by a material function of its own (u, v)."""
import math
import numpy as np
from PIL import Image, ImageDraw

PROJECTIONS = {
    # screen pixels per world unit along x, y, z
    "iso":  {"EX": (1.0, 0.25), "EY": (0.6, -0.15), "EZ": (0.0, -1.0), "back": False, "right": True},
    "top":  {"EX": (1.0, 0.0), "EY": (0.0, -0.6), "EZ": (0.0, -1.0), "back": True, "right": False},
    "side": {"EX": (1.0, 0.0), "EY": (0.0, 0.0), "EZ": (0.0, -1.0), "back": False, "right": False},
}


def hexc(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class View:
    """projection + screen origin; P(x, y, z) -> screen point, V(dx, dy, dz) -> screen vector"""
    def __init__(self, name="iso", origin=(0, 0)):
        p = PROJECTIONS[name]; self.name = name; self.EX, self.EY, self.EZ = p["EX"], p["EY"], p["EZ"]; self.back, self.right = p["back"], p["right"]; self.O = origin

    def V(self, dx, dy, dz): return (dx * self.EX[0] + dy * self.EY[0] + dz * self.EZ[0], dx * self.EX[1] + dy * self.EY[1] + dz * self.EZ[1])
    def P(self, x, y, z): v = self.V(x, y, z); return (self.O[0] + v[0], self.O[1] + v[1])


class Cv:
    def __init__(s, w, h): s.a = np.zeros((h, w, 4), np.uint8); s.w, s.h = w, h

    def px(s, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < s.w and 0 <= y < s.h: s.a[y, x] = (*c[:3], 255)

    def grid(s, rows, pal, x0, y0, mx=False):
        """text-grid sprite: '.' transparent, other characters index `pal`; mx mirrors the left half"""
        for j, r in enumerate(rows):
            r = r + r[::-1] if mx else r
            for i, ch in enumerate(r):
                if ch not in ". ": s.px(x0 + i, y0 + j, pal[ch])

    def plane(s, pts, shader):
        m = Image.new("L", (s.w, s.h), 0); ImageDraw.Draw(m).polygon([(float(x), float(y)) for x, y in pts], fill=255); ys, xs = np.nonzero(np.array(m))
        for y, x in zip(ys, xs):
            col = shader(x, y)
            if col is not None: s.px(x, y, col)

    def line(s, p, q, c):
        n = int(max(abs(q[0] - p[0]), abs(q[1] - p[1]))) + 1
        for i in range(n + 1): s.px(round(p[0] + (q[0] - p[0]) * i / max(1, n)), round(p[1] + (q[1] - p[1]) * i / max(1, n)), c)

    def tidy(s):
        """remove 1-px spikes (<=1 opaque 4-neighbour) and fill 1-px notches (>=3) with the most common neighbour colour, twice: clean silhouettes before the outline"""
        import collections
        for _ in range(2):
            op = s.a[..., 3] > 0; p = np.pad(op, 1); n = sum(p[1 + dy:1 + dy + s.h, 1 + dx:1 + dx + s.w].astype(int) for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)))
            spike = op & (n <= 1)
            for y, x in zip(*np.nonzero(~op & (n >= 3))):
                nb = [tuple(s.a[y + dy, x + dx, :3]) for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)) if 0 <= y + dy < s.h and 0 <= x + dx < s.w and op[y + dy, x + dx]]
                s.a[y, x] = (*collections.Counter(nb).most_common(1)[0][0], 255)
            s.a[spike] = 0

    def ring(s, col):
        op = s.a[..., 3] > 0; p = np.pad(op, 1); r = np.zeros_like(op)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)): r |= p[1 + dy:1 + dy + s.h, 1 + dx:1 + dx + s.w]
        s.a[r & ~op] = (*col, 255)

    def img(s): return Image.fromarray(s.a)


def face3(c, view, o3, a3, b3, poly, mat, ramp, shift=0, overlays=()):
    """a textured flat face. o3 = world point of (u,v)=(0,0); a3, b3 = world direction vectors (length 1 = 1 unit of u / v); poly = polygon in (u,v);
    mat(u, v) -> tone class int (colour = ramp[1 + class + shift]), a ready RGB tuple, or None (leave the pixel empty); shift = int or fn(u, v);
    overlays = [(u0, v0, u1, v1, fn(lu, lv, w, h, shift) -> RGB)]. Faces that are edge-on in this projection are skipped."""
    o = view.P(*o3); a = view.V(*a3); b = view.V(*b3); det = a[0] * b[1] - a[1] * b[0]
    if abs(det) < 1e-6: return None
    pts = [(o[0] + u * a[0] + v * b[0], o[1] + u * a[1] + v * b[1]) for u, v in poly]

    def shader(x, y):
        dx, dy = x - o[0], y - o[1]; u = (dx * b[1] - dy * b[0]) / det; v = (a[0] * dy - a[1] * dx) / det
        sh = shift(u, v) if callable(shift) else shift
        for u0, v0, u1, v1, fn in overlays:
            if u0 <= u < u1 and v0 <= v < v1: return fn(u - u0, v - v0, u1 - u0, v1 - v0, sh)
        k = mat(u, v)
        return k if (k is None or isinstance(k, tuple)) else ramp[max(0, min(len(ramp) - 1, 1 + k + sh))]
    c.plane(pts, shader); return pts


def box(c, view, x, y, z, w, d, h, mat, ramp, shifts=(1, -1, 1)):
    """an axis-aligned box: front face (y = const), right face (x = const, iso only), top face. shifts = tone steps (front, right, top)"""
    face3(c, view, (x, y, z), (1, 0, 0), (0, 0, 1), [(0, 0), (w, 0), (w, h), (0, h)], mat, ramp, shifts[0])
    if view.right: face3(c, view, (x + w, y, z), (0, 1, 0), (0, 0, 1), [(0, 0), (d, 0), (d, h), (0, h)], mat, ramp, shifts[1])
    face3(c, view, (x, y, z + h), (1, 0, 0), (0, 1, 0), [(0, 0), (w, 0), (w, d), (0, d)], lambda u, v: 3, ramp, shifts[2])


def beam(c, view, p3, q3, cols, off=(0, 1)):
    """a thick line between two world points: len(cols) parallel lines, first colour first, each shifted by `off` screen pixels"""
    p, q = view.P(*p3), view.P(*q3)
    for i, col in enumerate(cols): c.line((p[0] + i * off[0], p[1] + i * off[1]), (q[0] + i * off[0], q[1] + i * off[1]), col)


def snap(im, palette):
    """nearest-colour snap of every opaque pixel to a fixed palette (list of RGB)"""
    pal = np.array(palette, float); a = np.array(im); m = a[..., 3] > 0
    d = ((a[m][:, None, :3].astype(float) - pal[None]) ** 2).sum(-1); a[m, :3] = pal[d.argmin(1)].astype(np.uint8); return Image.fromarray(a)
