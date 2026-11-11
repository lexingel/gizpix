# SPDX-License-Identifier: AGPL-3.0-or-later
"""tile_check.py - does a tile repeat without a visible seam? Measures only.
  python tile_check.py tile.png [more.png ...]          one tile per file
  python tile_check.py atlas.png --grid 16               cut an atlas into 16x16 tiles, check each
  python tile_check.py selftest
Numbers per tile (tiled 2x2 in the mind's eye):
  seam      mean colour step across the wrap-around seam divided by the mean step between neighbouring columns/rows inside the tile
            (about 1 = invisible, > 2 = visible seam). Computed on rows and columns separately: seam_x, seam_y.
  gradient  brightness difference between the two halves of the tile (a gradient tiles into stripes), as a share of full brightness
  edge_rows share of pixels on the outermost ring that is the darkest colour (an emphasised tile edge shows the grid)
Only for tiles meant to repeat: a transition/edge tile or a block face is not supposed to wrap, ignore its flags."""
import sys, os, numpy as np
from PIL import Image

def tile_stats(a):
    op = a[..., 3] > 0; rgb = a[..., :3].astype(float); H, W = op.shape
    if op.mean() < 0.9: return {"note": "has transparent pixels, not a plain repeating tile"}
    step = lambda x, y: np.abs(x - y).sum(-1)
    inner_x = step(rgb[:, 1:], rgb[:, :-1]).mean(); inner_y = step(rgb[1:], rgb[:-1]).mean()
    seam_x = step(rgb[:, 0], rgb[:, -1]).mean() / max(inner_x, 1e-6); seam_y = step(rgb[0], rgb[-1]).mean() / max(inner_y, 1e-6)
    lum = rgb.mean(-1); grad = max(abs(lum[:, :W // 2].mean() - lum[:, W // 2:].mean()), abs(lum[:H // 2].mean() - lum[H // 2:].mean())) / 255
    dark = lum <= np.percentile(lum, 10); ring = np.zeros_like(dark); ring[0, :] = ring[-1, :] = ring[:, 0] = ring[:, -1] = True
    edge = float((dark & ring).sum() / ring.sum()); inner_dark = float((dark & ~ring).sum() / (~ring).sum())
    r = {"seam_x": round(float(seam_x), 2), "seam_y": round(float(seam_y), 2), "gradient": round(float(grad), 3), "edge_dark": round(edge, 2), "inner_dark": round(inner_dark, 2)}
    f = []
    if max(seam_x, seam_y) > 2.0: f.append("visible seam")
    if grad > 0.08: f.append("gradient (stripes when tiled)")
    if edge > 3 * max(inner_dark, 0.03) and edge > 0.3: f.append("emphasised tile edge")
    r["flags"] = f; return r

def selftest():
    rng = np.random.default_rng(0); ok = np.zeros((16, 16, 4), np.uint8); ok[..., 3] = 255; ok[..., :3] = rng.integers(90, 130, (16, 16, 3))
    ok[:, 8:] = ok[:, :8]; ok[8:] = ok[:8]                                  # periodic noise: wraps cleanly
    ok[:, -1] = ok[:, 0]; assert not tile_stats(ok)["flags"], tile_stats(ok)
    g = ok.copy(); g[..., :3] = np.linspace(40, 220, 16)[None, :, None].astype(np.uint8); r = tile_stats(g); assert "gradient (stripes when tiled)" in r["flags"] and "visible seam" in r["flags"], r
    e = ok.copy(); e[0, :, :3] = e[-1, :, :3] = e[:, 0, :3] = e[:, -1, :3] = 5; assert "emphasised tile edge" in tile_stats(e)["flags"], tile_stats(e)
    print("selftest ok")

if __name__ == "__main__":
    A = sys.argv[1:]
    if A == ["selftest"]: selftest(); sys.exit()
    if not A or "-h" in A or "--help" in A: print(__doc__); sys.exit(0 if A else 2)
    if "--grid" in A and (A.index("--grid") + 1 >= len(A) or not A[A.index("--grid") + 1].isdigit()): print("tile_check: --grid needs a number, e.g. --grid 16", file=sys.stderr); sys.exit(2)
    grid = int(A[A.index("--grid") + 1]) if "--grid" in A else 0; files = [x for i, x in enumerate(A) if not x.startswith("--") and (i == 0 or A[i - 1] != "--grid")]
    for f in files:
        if not os.path.isfile(f): print(f"tile_check: no such file: {f}", file=sys.stderr); sys.exit(2)
        a = np.array(Image.open(f).convert("RGBA"))
        tiles = [(f"{f} [{j},{i}]", a[j * grid:(j + 1) * grid, i * grid:(i + 1) * grid]) for j in range(a.shape[0] // grid) for i in range(a.shape[1] // grid)] if grid else [(f, a)]
        for name, t in tiles: print(name, tile_stats(t))
