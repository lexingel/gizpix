# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixdraw.styles - a style is plain data (JSON): colour ramps per material role, outline/seam colour, optional fixed palette. Nothing about a style is hard-coded.

  {"name": "...", "license": "...", "outline": "#080505", "seam": "#1d0b10", "palette": null | ["#rrggbb", ...],
   "ramps": {"wall": {"h": [0.97, 0.03], "s": 0.34, "v": [0.14, 0.50], "n": 7, "ends": 0.7}   # hue drifts dark -> light, short way round
             "roof": ["#...", "#...", ...]}}                                                # or an explicit list, dark -> light
Roles: wall roof stone trim glass glow door awning_a awning_b prop wood cloth crate interior ground. Missing roles are derived from the ones present."""
import colorsys, json, os
import numpy as np
from PIL import Image
from .core import hexc

HERE = os.path.dirname(os.path.abspath(__file__))
ROLES = ("wall", "roof", "stone", "trim", "glass", "glow", "door", "awning_a", "awning_b", "prop", "wood", "cloth")


def hsv(h, s, v): return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h % 1, min(1, max(0, s)), min(1, max(0, v))))


def make_ramp(h, s, v, n=7, ends=0.7):
    """dark -> light; hue drifts from h[0] (shadows) to h[1] (highlights) the short way round the wheel; saturation eases at both ends"""
    h0, h1 = h; h1 = h0 + max(-0.25, min(0.25, (h1 - h0 + 0.5) % 1 - 0.5))        # drift capped at 0.25 of the wheel: more breaks palette snapping
    return [hsv(h0 + (h1 - h0) * i / (n - 1), s * (1 - (1 - ends) * abs(2 * i / (n - 1) - 1)), v[0] + (v[1] - v[0]) * i / (n - 1)) for i in range(n)]


def _ramp(spec):
    if isinstance(spec, list): return [hexc(x) for x in spec]
    return make_ramp(spec["h"], spec["s"], spec["v"], spec.get("n", 7), spec.get("ends", 0.7))


def load_style(name):
    """name of a bundled style (styles/NAME.json), a path to a JSON file, or an already loaded dict"""
    if isinstance(name, dict): d = name
    else:
        bundled = os.path.join(HERE, "styles", name + ".json")
        p = bundled if os.path.exists(bundled) and not name.endswith(".json") and os.sep not in name and "/" not in name else name
        if not os.path.exists(p): raise ValueError(f"unknown style {name!r}; bundled: {', '.join(list_styles())}, or give a path to a .json file")
        with open(p, encoding="utf-8") as f: d = json.load(f)
    S = {"name": d.get("name", "style"), "license": d.get("license", ""), "outline": hexc(d["outline"]), "seam": hexc(d.get("seam", d["outline"])),
         "palette": [hexc(x) for x in d["palette"]] if d.get("palette") else None, "ramps": {k: _ramp(v) for k, v in d["ramps"].items()}}
    R = S["ramps"]
    for need in ("wall", "roof", "trim"):
        if need not in R: raise ValueError(f"style {S['name']!r} needs a {need!r} ramp")
    R.setdefault("stone", R["wall"]); R.setdefault("glass", R["trim"]); R.setdefault("glow", R["trim"]); R.setdefault("door", R["wall"])
    R.setdefault("awning_a", R["roof"]); R.setdefault("awning_b", R["trim"]); R.setdefault("prop", R["stone"]); R.setdefault("wood", R["wall"]); R.setdefault("cloth", R["trim"]); R.setdefault("crate", R["wood"]); R.setdefault("interior", R["door"]); R.setdefault("ground", R["wall"])
    return S


def list_styles(): return sorted(f[:-5] for f in os.listdir(os.path.join(HERE, "styles")) if f.endswith(".json"))


def _hue_clusters(hs, w, k=3):
    """weighted circular k-means on hue; returns a list of (member mask) for the non-empty clusters, biggest first"""
    ang = hs[:, 0] * 2 * np.pi; cent = []
    for i in np.argsort(-w):                                            # seeds: the heaviest colours that are at least 0.08 of the wheel apart
        if all(abs(((hs[i, 0] - c + 0.5) % 1) - 0.5) > 0.08 for c in cent): cent.append(hs[i, 0])
        if len(cent) == k: break
    cent = np.array(cent)
    for _ in range(12):
        lab = np.abs(((hs[:, 0][:, None] - cent[None] + 0.5) % 1) - 0.5).argmin(1)
        for j in range(len(cent)):
            m = lab == j
            if m.any(): cent[j] = (np.angle(np.average(np.exp(1j * ang[m]), weights=w[m])) / (2 * np.pi)) % 1
    groups = [lab == j for j in range(len(cent)) if (lab == j).any()]
    return sorted(groups, key=lambda m: -w[m].sum())


def extract_style(paths, out=None, name="extracted", n=24):
    """a starting-point style from the user's OWN sprites: the most used colours become the fixed palette; chromatic colours are grouped by hue (up to 3 groups,
    the group sitting highest in the sprites = roof, the heaviest of the rest = wall, then trim, the darkest of the wall group = door); greys become the stone ramp; the brightest saturated colour sets the glow.
    Each ramp takes its group's own hue, saturation and value spread. Not a copy of the sprites; edit the result."""
    import collections
    cnt = collections.Counter(); ysum = collections.Counter()                                         # ysum: how far down the sprite (0 top, 1 bottom of its silhouette) a colour sits, summed over its pixels
    for p in paths:
        a = np.array(Image.open(p).convert("RGBA")); op = a[..., 3] > 0; cnt.update(map(tuple, a[op][:, :3]))
        if op.any():
            ys, xs = np.nonzero(op); y0, y1 = ys.min(), ys.max(); rel = (ys - y0) / max(1, y1 - y0)
            for c, r in zip(map(tuple, a[ys, xs][:, :3].tolist()), rel): ysum[c] += float(r)
    pal = [c for c, _ in cnt.most_common(n)]; ymean = np.array([ysum[c] / cnt[c] for c in pal])
    hs = np.array([colorsys.rgb_to_hsv(*[x / 255 for x in c]) for c in pal]); w = np.array([cnt[c] for c in pal], float)
    dark = hs[:, 2] < 0.16; chroma = (hs[:, 1] > 0.18) & ~dark; grey = (hs[:, 1] <= 0.18) & ~dark

    def stats(m, fall):
        if not m.any(): return fall
        h = float(np.angle(np.average(np.exp(2j * np.pi * hs[m, 0]), weights=w[m])) / (2 * np.pi)) % 1; v = hs[m, 2]; lo, hi = float(np.percentile(v, 5)), float(np.percentile(v, 95)); mid = (lo + hi) / 2
        return (h, float(np.average(hs[m, 1], weights=w[m])), max(0.08, min(lo, mid - 0.2)), min(1.0, max(hi, mid + 0.2)))        # a ramp needs room: at least 0.4 of value range
    allc = stats(chroma | grey, (0.05, 0.3, 0.15, 0.7)); groups = [g for g in (_hue_clusters(hs[chroma], w[chroma]) if chroma.sum() > 1 else []) if w[chroma][g].sum() >= 0.06 * w[chroma].sum()]        # tiny hue groups are noise (an outline colour, a single glint)
    idx = np.nonzero(chroma)[0]; G = [stats(np.isin(np.arange(len(pal)), idx[g]), allc) for g in groups]
    if len(groups) > 1:                                                                  # roles by position: the group that sits highest in the sprites is the roof, the heaviest of the rest the wall, then the trim
        gy = [float(np.average(ymean[idx[g]], weights=w[idx[g]])) for g in groups]; gw = [float(w[idx[g]].sum()) for g in groups]
        roof_i = int(np.argmin(gy)); rest = sorted((i for i in range(len(groups)) if i != roof_i), key=lambda i: -gw[i]); order = [rest[0], roof_i] + rest[1:]; G = [G[i] for i in order]
    G = G + [allc] * 3
    wall, roof, trim = G[0], (G[1] if len(groups) > 1 else (G[0][0] - 0.03, G[0][1], G[0][2] * 0.8, G[0][3] * 0.85)), (G[2] if len(groups) > 2 else (G[0][0] + 0.03, G[0][1] * 0.9, G[0][2], min(1.0, G[0][3] * 1.15)))
    stone = stats(grey, (allc[0], allc[1] * 0.3, allc[2], allc[3])); glowm = chroma & (hs[:, 2] > 0.7) & (hs[:, 1] > 0.4); glow = stats(glowm, (0.1, 0.7, 0.4, 1.0))
    r = lambda t, dh=0.04, sm=1.0, vm=(1.0, 1.0): {"h": [round(t[0], 3), round(t[0] + dh, 3)], "s": round(min(0.95, max(0.05, t[1] * sm)), 3), "v": [round(t[2] * vm[0], 3), round(min(1.0, t[3] * vm[1]), 3)], "n": 7}
    d = {"name": name, "license": "derived from the user's own sprites", "outline": "#%02x%02x%02x" % min(pal, key=sum), "palette": ["#%02x%02x%02x" % c for c in pal],
         "ramps": {"wall": r(wall), "roof": r(roof), "trim": r(trim), "stone": r(stone, 0.03), "door": r(wall, 0.03, 1.1, (0.6, 0.7)),
                   "glow": {"h": [round(glow[0], 3), round(glow[0] + 0.07, 3)], "s": round(min(0.95, glow[1]), 3), "v": [0.4, 1.0], "n": 7}, "glass": {"h": [0.6, 0.55], "s": 0.4, "v": [round(allc[2], 3), round(allc[3], 3)], "n": 7}}}
    if out:
        with open(out, "w", encoding="utf-8") as f: json.dump(d, f, indent=1)
    return d
