# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixdraw.materials - every material is a function (u, v) -> tone class 0..3 (0 seam, 1 low, 2 high, 3 highlight) or a ready RGB tuple.
The style's colour ramp turns the class into a colour, shifted darker or lighter per face by the light. Add your own with register()."""
import math


def _h(a, b): return ((int(a) * 73856093) ^ (int(b) * 19349663)) & 0xffff


def planks(u, v, row=4, st=11):
    k = math.floor(v / row); r = math.floor(v) % row; seg = math.floor((u + k * 7) / 11)
    if r > 0 and (math.floor(u) + (k * 5) % st) % (2 * st) == 0: return 0
    return 3 if r == 0 else (0 if r == row - 1 else (1 if (k + seg) % 2 else 2))


def shingles(u, v, row=4, w=6):
    k = math.floor(v / row); r = math.floor(v) % row; uu = math.floor(u + (k % 2) * (w // 2)) % w
    if uu == 0 and r < row - 1: return 0
    if _h(math.floor(u / w) + k * 3, k) % 23 == 0 and r: return 1
    return 3 if r == 0 else (1 if r == row - 1 else 2)


def tiles(u, v): return shingles(u, v, 5, 9)


def stone(u, v, bw=9, bh=5):
    k = math.floor(v / bh); r = math.floor(v) % bh; uu = math.floor(u + (k % 2) * (bw // 2)); c = uu % bw
    if r == bh - 1 or c == 0: return 0
    return 3 if r == 0 else (1 if _h(uu // bw, k) % 3 == 0 else 2)


def brick(u, v): return stone(u, v, 6, 3)


def plaster(u, v):
    """flat wall with a few deliberate hairline cracks (no random speckle)"""
    cu, cv = math.floor(u / 18), math.floor(v / 14)
    if _h(cu, cv) % 5 == 0:
        lu, lv = math.floor(u) - cu * 18 - 5, math.floor(v) - cv * 14 - 3
        if 0 <= lu < 5 and lv == lu: return 1
    return 2


def thatch(u, v):
    k = math.floor(v / 3); r = math.floor(v) % 3; h = _h(math.floor(u + k), k) % 7
    return 3 if r == 0 and h < 4 else (1 if h == 0 else 2)


def flagstone(u, v): return stone(u, v, 10, 8)


def plain(u, v): return 2


MATERIALS = {"planks": planks, "shingles": shingles, "tiles": tiles, "stone": stone, "brick": brick, "plaster": plaster, "thatch": thatch, "flagstone": flagstone, "plain": plain}
# which colour ramp of the style a material uses (default: wall / roof)
MATERIAL_RAMP = {"stone": "stone", "brick": "stone", "flagstone": "stone", "plaster": "wall", "planks": "wall", "shingles": "roof", "tiles": "roof", "thatch": "roof"}


def register(name, fn, ramp="wall"):
    """add a material; `ramp` = the style role whose colours it uses (wall, roof, stone, trim, wood ...)"""
    MATERIALS[name] = fn; MATERIAL_RAMP[name] = ramp


def ramp_of(S, name, default="wall"): return S["ramps"][MATERIAL_RAMP.get(name, default)]
