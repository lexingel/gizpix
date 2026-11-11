# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixel_lint.py - automatic pixel-art quality checks (a "lint"): what an artist would flag by eye, as numbers. Only measures, never edits.
  python pixel_lint.py sprite.png [more.png ...] [--json] [--strict]   (--strict: exit 1 if any sprite has a flag; no file -> usage, exit 2)      python pixel_lint.py selftest
Checks (rules of thumb from the pixel-art craft, our own code):
  lone_px      opaque pixels with no opaque neighbour at all, plus 1-pixel colour specks (differ from all 4 neighbours, which agree with each other)
  thick_line   share of dark outline pixels that sit in 2x2 dark blocks (a 1 px outline is the usual goal)
  stair_break  silhouette edge steps: how often neighbouring step lengths differ by more than 1 (even, or two alternating lengths, is clean)
  soft_alpha   pixels with alpha not 0 or 255 (blurry edge: too much anti-alias, or a resized image)
  colors       number of colours; sat_mean / value_spread (p95-p5): weak palette = too many colours, or too flat / too harsh
  pillow       correlation of brightness with distance from the silhouette edge, negative = darkest at the edges (flat "pillow" shading)
  light_x      brightness centre of mass left(-1)..right(+1): compare across directions, it should follow one light source
Flags are advisory thresholds, tune them per project."""
import sys, os, json
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, convolve

def _hsv(rgb):
    rgb = rgb / 255.0; mx = rgb.max(-1); mn = rgb.min(-1); return np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0), mx

def lint(a):
    op = a[..., 3] > 0; rgb = a[..., :3].astype(float); n = int(op.sum()); r = {"opaque_px": n}
    if n == 0: return r, ["empty"]
    K8 = np.ones((3, 3)); K8[1, 1] = 0; nb = convolve(op.astype(int), K8, mode="constant")
    lone = int((op & (nb == 0)).sum())
    H, W = op.shape; pad = np.pad(rgb, ((1, 1), (1, 1), (0, 0)), mode="edge"); po = np.pad(op, 1)
    c = pad[1:-1, 1:-1]; nbs = [pad[:-2, 1:-1], pad[2:, 1:-1], pad[1:-1, :-2], pad[1:-1, 2:]]; nbo = [po[:-2, 1:-1], po[2:, 1:-1], po[1:-1, :-2], po[1:-1, 2:]]
    same = lambda x, y: np.abs(x - y).sum(-1) < 12
    speck = op & np.all([o for o in nbo], 0) & ~np.any([same(c, x) for x in nbs], 0) & same(nbs[0], nbs[1]) & same(nbs[2], nbs[3]) & same(nbs[0], nbs[2])
    r["isolated_px"] = lone; r["speck_px"] = int(speck.sum()); r["lone_px"] = lone + int(speck.sum())
    sat, val = _hsv(rgb); dark = op & (val < 0.2)
    r["thick_line"] = round(float((dark & np.roll(dark, 1, 0) & np.roll(dark, 1, 1) & np.roll(dark, (1, 1), (0, 1)) | dark & np.roll(dark, -1, 0) & np.roll(dark, -1, 1) & np.roll(dark, (-1, -1), (0, 1))).sum() / max(dark.sum(), 1)), 3) if dark.sum() > 10 else 0.0
    steps = []
    for y in range(H):
        xs = np.nonzero(op[y])[0]
        if len(xs): steps.append((xs.min(), xs.max()))
    br = tot = 0
    for side in (0, 1):
        d = np.abs(np.diff([s[side] for s in steps])); runs = []; k = 0
        for v in d:
            if v == 0: k += 1
            else: runs.append(k + 1); k = 0
        for p, q in zip(runs, runs[1:]): tot += 1; br += abs(p - q) > 1
    r["stair_break"] = round(br / tot, 3) if tot >= 8 else 0.0   # fewer steps (tiny sprites) are too few to judge
    al = a[..., 3]; r["soft_alpha"] = int(((al > 0) & (al < 255)).sum())
    cols = np.unique(a[op][:, :3], axis=0); r["colors"] = len(cols); r["sat_mean"] = round(float(sat[op].mean()), 2)
    r["value_spread"] = round(float(np.percentile(val[op], 95) - np.percentile(val[op], 5)), 2)
    dist = distance_transform_edt(op); lum = rgb.mean(-1)
    inner = op & (dist > 1) if (op & (dist > 1)).sum() > 20 else op
    r["pillow"] = round(float(np.corrcoef(dist[inner], lum[inner])[0, 1]), 2) if lum[inner].std() > 1 and dist[inner].std() > 0 else 0.0
    ys, xs = np.nonzero(op); w = lum[op] + 1e-6; cx = (xs.min() + xs.max()) / 2; half = max((xs.max() - xs.min()) / 2, 1)
    r["light_x"] = round(float((np.sum(xs * w) / w.sum() - cx) / half), 2)
    flags = []
    if r["isolated_px"] >= 1: flags.append("lone pixels")   # speck_px is information only: injected specks were not reliably separable from textured shading
    if r["thick_line"] > 0.35: flags.append("thick outline")
    if r["stair_break"] > 0.5: flags.append("irregular edge steps")
    if r["soft_alpha"] > 0.02 * n: flags.append("soft alpha / blurry edge")
    if r["colors"] > 40: flags.append("too many colours")
    if r["value_spread"] < 0.3: flags.append("flat contrast")
    if r["value_spread"] > 0.98: flags.append("harsh contrast")
    if r["pillow"] < -0.5: flags.append("pillow shading")
    return r, flags

def selftest():
    S = 24; base = np.zeros((S, S, 4), np.uint8); yy, xx = np.mgrid[0:S, 0:S]
    body = (xx - 12) ** 2 / 64 + (yy - 12) ** 2 / 100 < 1
    img = base.copy(); img[body] = (200, 120, 90, 255)
    lit = body & (xx < 10); img[lit] = (230, 160, 120, 255)                       # light from the left, flat interior
    edge = body & ~np.roll(np.roll(body, 1, 0) & np.roll(body, -1, 0) & np.roll(body, 1, 1) & np.roll(body, -1, 1), 0, 0)
    img[edge] = (10, 10, 12, 255)
    r, f = lint(img); assert "lone pixels" not in f and "soft alpha / blurry edge" not in f, (r, f)
    d = img.copy(); d[1, 1] = (255, 0, 0, 255); assert "lone pixels" in lint(d)[1]                                # lone pixel
    b = np.array(Image.fromarray(img).resize((96, 96), Image.BICUBIC).resize((24, 24), Image.BILINEAR)); assert lint(b)[0]["soft_alpha"] > r["soft_alpha"], "blur not seen"
    t = img.copy(); t[~body & np.roll(body, 1, 0) | ~body & np.roll(body, -1, 1)] = (10, 10, 12, 255); assert lint(t)[0]["thick_line"] > r["thick_line"], "thick line not seen"
    pil = base.copy(); dist = np.sqrt((xx - 12) ** 2 + (yy - 12) ** 2); pil[body] = np.stack([np.clip(255 - 12 * dist[body] * 2, 20, 255)] * 3 + [np.full(body.sum(), 255)], -1).astype(np.uint8)   # brightest in the centre
    assert lint(pil)[0]["pillow"] > 0.3, lint(pil)[0]
    print("selftest ok", r)

if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["selftest"]: selftest(); sys.exit()
    files = [x for x in a if not x.startswith("--")]
    if not files or "-h" in a or "--help" in a: print(__doc__); sys.exit(0 if ("-h" in a or "--help" in a) else 2)
    as_json = "--json" in a; out = {}
    for p in files:
        if not os.path.isfile(p): print(f"pixel_lint: no such file: {p}", file=sys.stderr); sys.exit(2)
        r, f = lint(np.array(Image.open(p).convert("RGBA"))); out[p] = {**r, "flags": f}
        if not as_json: print(p, r, "FLAGS:", ", ".join(f) or "none")
    if as_json: print(json.dumps(out, indent=1))
    if "--strict" in a and any(v["flags"] for v in out.values()): sys.exit(1)           # --strict: exit 1 when any sprite is flagged (default: measuring never fails)
