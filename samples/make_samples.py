#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Draw the Gizpix sample walk frames from code, so their licence is clean (same as Gizpix, AGPL-3.0-or-later).

Writes samples/walk_frames/{base,robe,pauld,dbase,drobe}/{east,south}/0..7.png  (96x96, transparent).
base/dbase = bare character (light / dark skin); robe, pauld (pauldrons) = the same pose wearing an outfit.
Re-run:  python samples/make_samples.py
"""
import math, os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "walk_frames")
N, S = 8, 96
OL = (28, 22, 34)
SKIN = {"base": [(236, 188, 150), (206, 150, 114)], "dbase": [(120, 78, 52), (92, 58, 40)]}
HAIR = [(92, 52, 30), (64, 34, 20)]
TUNIC = [(70, 96, 150), (48, 68, 112)]
BOOT = [(78, 52, 38), (52, 34, 26)]
ROBE = [(150, 40, 60), (108, 26, 44)]
BELT = (222, 178, 70)
PAULD = [(170, 176, 190), (112, 118, 138)]


def box(d, x0, y0, x1, y1, col):                     # filled box, 1 px outline, col = (light, shade)
    d.rectangle([x0, y0, x1, y1], fill=OL)
    d.rectangle([x0 + 1, y0 + 1, x1 - 1, y1 - 1], fill=col[0])
    if y1 - y0 > 4: d.rectangle([x0 + 1, y1 - 2, x1 - 1, y1 - 1], fill=col[1])


def figure(view, i, skin, outfit):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    t = 2 * math.pi * i / N
    bob = round(abs(math.sin(t)) * 2)
    cx, foot = 48, 84
    sw = round(math.sin(t) * 7)
    top = foot - 12 - bob
    if view == "east":
        for sx in (-sw, sw):                          # far leg first
            lift = 2 if sx > 0 else 0
            box(d, cx - 3 + sx, top, cx + 2 + sx, foot - lift, TUNIC)
            box(d, cx - 4 + sx, foot - 5 - lift, cx + 4 + sx, foot - lift, BOOT)
        box(d, cx - 8, top - 18, cx + 7, top + 1, TUNIC)
        box(d, cx - 3 - sw // 2, top - 16, cx + 2 - sw // 2, top - 2, skin)
        box(d, cx - 6, top - 32, cx + 7, top - 17, skin)
        box(d, cx - 7, top - 34, cx + 7, top - 26, HAIR)
        d.rectangle([cx + 4, top - 24, cx + 5, top - 22], fill=OL)
    else:
        for sx, off in ((sw, 0), (-sw, 6)):
            lift = 2 if sx > 0 else 0
            box(d, cx - 8 + off, top, cx - 3 + off, foot - lift, TUNIC)
            box(d, cx - 9 + off, foot - 5 - lift, cx - 2 + off, foot - lift, BOOT)
        box(d, cx - 10, top - 18, cx + 9, top + 1, TUNIC)
        box(d, cx - 14, top - 17 + sw // 3, cx - 10, top - 3 + sw // 3, skin)
        box(d, cx + 9, top - 17 - sw // 3, cx + 13, top - 3 - sw // 3, skin)
        box(d, cx - 7, top - 32, cx + 7, top - 17, skin)
        box(d, cx - 8, top - 34, cx + 8, top - 27, HAIR)
        d.rectangle([cx - 4, top - 24, cx - 3, top - 22], fill=OL)
        d.rectangle([cx + 3, top - 24, cx + 4, top - 22], fill=OL)
    if outfit == "robe":
        w = 8 if view == "east" else 10
        box(d, cx - w, top - 17, cx + w - 1, top + 8, ROBE)
        d.rectangle([cx - w + 1, top - 7, cx + w - 2, top - 5], fill=BELT)
    if outfit == "pauld":
        if view == "east": box(d, cx - 6, top - 20, cx + 5, top - 13, PAULD)
        else:
            box(d, cx - 15, top - 20, cx - 8, top - 13, PAULD); box(d, cx + 7, top - 20, cx + 14, top - 13, PAULD)
    return im


def main():
    import shutil
    shutil.rmtree(OUT, ignore_errors=True)
    for folder, skin, outfit in (("base", "base", None), ("robe", "base", "robe"), ("pauld", "base", "pauld"),
                                 ("dbase", "dbase", None), ("drobe", "dbase", "robe")):
        for view in ("east", "south"):
            p = os.path.join(OUT, folder, view); os.makedirs(p)
            for i in range(N): figure(view, i, SKIN[skin], outfit).save(os.path.join(p, f"{i}.png"))
    print("wrote", OUT)


if __name__ == "__main__": main()
