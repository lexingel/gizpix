# SPDX-License-Identifier: AGPL-3.0-or-later
"""recolor_groups.py - a colour variant of a sprite and its frames: colours sorted into groups (skin, white/grey/black
neutrals, hue families), each named group sent to a named colour while every pixel keeps its place on the light-to-
dark ramp. Exact per colour, so pixels stay pixels; the still and every animation frame get the same mapping. Free.

    python recolor_groups.py hero.png --groups                                   # what the sprite is made of
    python recolor_groups.py hero.png frames/*.png --swap red=indigo --swap blue=#b9ad94 --out variant/

The still sets the mapping (its colours' groups and lightness); a frame colour the still lacks takes the group of
its nearest still colour. Skin never moves unless named. Writes DIR/<same names>. --selftest runs offline checks.
(From pixel-forge's palette tool, 2026-10-21.)
"""
import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image



def oklab(rgb: np.ndarray) -> np.ndarray:
    """sRGB 0-255 (..., 3) to OKLab."""
    c = rgb.astype(np.float64) / 255
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    lms = c @ np.array([[0.4122214708, 0.2119034982, 0.0883024619], [0.5363325363, 0.6806995451, 0.2817188376],
                        [0.0514459929, 0.1073969566, 0.6299787005]])
    lms = np.cbrt(lms)
    return lms @ np.array([[0.2104542553, 1.9779984951, 0.0259040371], [0.7936177850, -2.4285922050, 0.7827717662],
                           [-0.0040720468, 0.4505937099, -0.8086757660]])


# target colours as OKLCH (lightness, chroma, hue degrees): picked off sRGB swatches
NAMED = {
    "crimson": (0.44, 0.16, 22), "red": (0.56, 0.19, 28), "scarlet": (0.60, 0.20, 35), "orange": (0.70, 0.16, 55),
    "gold": (0.78, 0.13, 85), "yellow": (0.88, 0.15, 100), "olive": (0.58, 0.10, 115), "green": (0.60, 0.15, 145),
    "emerald": (0.55, 0.12, 160), "teal": (0.60, 0.09, 195), "cyan": (0.75, 0.10, 210), "blue": (0.55, 0.15, 255),
    "navy": (0.35, 0.10, 265), "indigo": (0.42, 0.14, 285), "purple": (0.50, 0.15, 305), "violet": (0.55, 0.16, 295),
    "magenta": (0.60, 0.20, 335), "pink": (0.75, 0.11, 355), "brown": (0.45, 0.07, 60), "white": (0.95, 0.01, 90),
    "silver": (0.78, 0.01, 250), "grey": (0.60, 0.00, 0), "black": (0.22, 0.01, 280), "bone": (0.88, 0.03, 85),
}
HUES = [("red", 0, 40), ("orange", 40, 70), ("yellow", 70, 110), ("green", 110, 170), ("teal", 170, 220),
        ("blue", 220, 275), ("purple", 275, 330), ("pink", 330, 360)]


def _lch(lab: np.ndarray) -> np.ndarray:
    return np.stack([lab[..., 0], np.hypot(lab[..., 1], lab[..., 2]), np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360], -1)


def _rgb(lab: np.ndarray) -> np.ndarray:
    """OKLab -> sRGB 0-255 (clipped)."""
    m1 = np.array([[1.0, 1.0, 1.0], [0.3963377774, -0.1055613458, -0.0894841775], [0.2158037573, -0.0638541728, -1.2914855480]])
    lms = (lab @ m1) ** 3
    m2 = np.array([[4.0767416621, -1.2684380046, -0.0041960863], [-3.3077115913, 2.6097574011, -0.7034186147],
                   [0.2309699292, -0.3413193965, 1.7076147010]])
    c = np.clip(lms @ m2, 0, 1)
    c = np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
    return np.round(c * 255).astype(np.uint8)


def group_of(rgb: np.ndarray) -> np.ndarray:
    """Group name per colour, (N, 3) uint8 -> (N,) str."""
    lch = _lch(oklab(rgb))
    out = np.empty(len(rgb), dtype=object)
    for i, (l, c, h) in enumerate(lch):
        if c < 0.035 or (c < 0.07 and l >= 0.62 and 50 <= h <= 110):   # cream and its shadows count as white
            out[i] = "white" if l >= 0.62 else ("black" if l < 0.38 else "grey")
        elif 30 <= h <= 75 and 0.06 <= c <= 0.13 and 0.55 <= l <= 0.85:
            out[i] = "skin"
        else:
            out[i] = next(n for n, a, b in HUES if a <= h < b)
    return out


def group_of_px(px: np.ndarray) -> np.ndarray:
    """group_of for many pixels (repeats share one lookup)."""
    cols, inv = np.unique(px, axis=0, return_inverse=True)
    return group_of(cols)[inv.ravel()]


def groups(img: Image.Image) -> dict:
    """{group: share of opaque pixels}, biggest first: what a body is made of, to pick swaps from."""
    a = np.array(img.convert("RGBA"))
    px = a[a[..., 3] >= 128][:, :3]
    cols, n = np.unique(px, axis=0, return_counts=True)
    g = group_of(cols)
    tot = {}
    for name, k in zip(g, n):
        tot[name] = tot.get(name, 0) + int(k)
    s = sum(tot.values()) or 1
    return dict(sorted(((k, round(v / s, 3)) for k, v in tot.items()), key=lambda kv: -kv[1]))


def parse(swaps: list) -> dict:
    """GROUP=COLOUR, COLOUR a name from NAMED or a hex colour (#rrggbb, added to NAMED as its OKLCH)."""
    out = {}
    for s in swaps:
        g, c = (v.strip() for v in s.split("="))
        if c.startswith('#') and len(c) == 7:
            rgb = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)]], np.uint8)
            l, ch, h = _lch(oklab(rgb))[0]
            NAMED[c] = (float(l), float(ch), float(h))
        elif c not in NAMED:
            raise ValueError("unknown colour %r (known: %s, or #rrggbb)" % (c, ", ".join(sorted(NAMED))))
        out[g] = c
    return out


class Swap:
    """Built on a reference image (the still): its colours' groups and each group's mean lightness. Applied to any
    image of the same body (frames too): a colour not in the still takes the group of its nearest still colour."""

    def __init__(self, still: Image.Image, swaps: dict):
        a = np.array(still.convert("RGBA"))
        self.cols = np.unique(a[a[..., 3] >= 128][:, :3], axis=0)
        self.lab = oklab(self.cols)
        self.grp = group_of(self.cols)
        self.swaps = swaps
        self.mean_l = {g: float(self.lab[self.grp == g][:, 0].mean()) for g in set(self.grp)}

    def colour(self, rgb: np.ndarray) -> np.ndarray:
        """(N, 3) uint8 -> (N, 3) uint8."""
        lab = oklab(rgb)
        near = ((lab[:, None] - self.lab[None]) ** 2).sum(-1).argmin(1)
        g = self.grp[near]
        out = rgb.copy()
        for name, target in self.swaps.items():
            sel = g == name
            if not sel.any():
                continue
            tl, tc, th = NAMED[target]
            l = tl + (lab[sel, 0] - self.mean_l.get(name, tl))   # the ramp kept around the target's lightness
            l = np.clip(l, 0.05, 0.98)
            c = np.full(sel.sum(), tc) * np.clip(1.0 - np.abs(l - tl) * 0.8, 0.4, 1.0)   # ramp ends a little greyer
            h = np.radians(th)
            out[sel] = _rgb(np.stack([l, c * np.cos(h), c * np.sin(h)], -1))
        return out

    def __call__(self, img: Image.Image) -> Image.Image:
        a = np.array(img.convert("RGBA"))
        on = a[..., 3] > 0
        if not on.any():
            return img.convert("RGBA")
        cols, inv = np.unique(a[on][:, :3], axis=0, return_inverse=True)
        a[on, :3] = self.colour(cols)[inv.ravel()]
        return Image.fromarray(a, "RGBA")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    ap.add_argument('still')
    ap.add_argument('frames', nargs='*')
    ap.add_argument('--swap', action='append', default=[], metavar='GROUP=COLOUR')
    ap.add_argument('--groups', action='store_true')
    ap.add_argument('--out')
    a = ap.parse_args()
    still = Image.open(a.still).convert('RGBA')
    if a.groups or not a.swap:
        for g, share in groups(still).items():
            print('%-7s %5.1f%%' % (g, share * 100))
        print('colours:', ', '.join(sorted(NAMED)))
        return
    if not a.out:
        ap.error('give --out DIR')
    swap = Swap(still, parse(a.swap))
    os.makedirs(a.out, exist_ok=True)
    for f in [a.still] + a.frames:
        swap(Image.open(f)).save(os.path.join(a.out, os.path.basename(f)))
    print('%d image(s) -> %s' % (1 + len(a.frames), a.out))


def selftest() -> None:
    """white goes crimson and keeps its light-to-dark order; skin stays."""
    px = np.array([[[240, 236, 225, 255], [200, 196, 186, 255], [225, 170, 130, 255]]], dtype=np.uint8)
    img = Image.fromarray(px, 'RGBA')
    out = np.array(Swap(img, parse(['white=crimson']))(img)).astype(int)
    assert out[0, 0, 0] > out[0, 0, 2] and out[0, 0, 0] > out[0, 0, 1], out[0, 0]
    assert out[0, 0, :3].sum() > out[0, 1, :3].sum()
    assert tuple(out[0, 2]) == (225, 170, 130, 255)
    dark = np.array(Swap(img, parse(['white=#6e6a60']))(img)).astype(int)
    assert dark[0, 0, :3].sum() < out[0, 0, :3].sum() + 200 and dark[0, 0, :3].mean() < 150, dark[0, 0]   # a hex target lands near its lightness
    print('selftest OK')


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        selftest()
    else:
        main()
