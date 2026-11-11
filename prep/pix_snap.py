# SPDX-License-Identifier: AGPL-3.0-or-later
"""pix_snap.py - turn an upscaled or off-grid "pixel art" image back into real pixels. Local, free, our own code.

  python pix_snap.py in.png out.png [--cells W H] [--tol N] [--lam L]   (lam: how rigid the grid is; 1 elastic .. 8 rigid)
  python pix_snap.py selftest

How it works (one idea, per axis, written from scratch):
  1. Edge profile E[b]: how much the image changes across the boundary at position b (colour + transparency).
  2. A grid with n cells is a path of n-1 cuts from 0 to L. The best path maximises the edge energy it sits on
     (above the average) minus a penalty for cells whose width differs from L/n. A small penalty = elastic grid
     (AI images with uneven pixels), a big one = rigid grid (true upscales). Solved exactly by dynamic programming.
  3. n is chosen by "gain": the score on the real profile minus the score on the same profile shifted by half a cell
     (what the path could capture by luck). With --cells W H the counts are fixed (or +-tol).
  4. Each cell becomes the median colour of its centre; a cell is opaque when most of its centre is.
A clean whole-number nearest-neighbour upscale (every k-wide group of columns and rows identical) is recognised exactly first and comes back pixel for pixel;
noisy, blurred or warped input goes through the dip rule below, which is a guess.
Returns the small image plus a report (cells, gain, ratio to the runner-up) so callers can tell sure from unsure.
"""
import sys, argparse
import numpy as np
from PIL import Image

def edge_profile(a, axis):
    rgb = a[..., :3].astype(float); al = a[..., 3].astype(float); op = al > 0
    if axis == 1:
        d = np.abs(rgb[:, 1:] - rgb[:, :-1]).sum(-1) * (op[:, 1:] & op[:, :-1]) + np.abs(al[:, 1:] - al[:, :-1])
        e = d.mean(0)
    else:
        d = np.abs(rgb[1:] - rgb[:-1]).sum(-1) * (op[1:] & op[:-1]) + np.abs(al[1:] - al[:-1])
        e = d.mean(1)
    e = np.convolve(np.pad(e, 1, mode="edge"), [0.25, 0.5, 0.25], mode="valid")
    e = np.maximum(e - 2 * np.median(e), 0)          # noise floor: sensor-like noise and JPEG dust add a flat level everywhere
    E = np.zeros(len(e) + 2); E[1:-1] = e          # E[b] = change across boundary b (1..L-1); 0 and L are the borders
    return E

def _path(E, n, lam, want_cuts, drift=0.1):
    """Best n-cell path of cuts over positions 0..L (L = len(E)-1). Returns (score, cuts)."""
    L = len(E) - 1; s = L / n
    pos = E[E > 0]
    ref = np.percentile(pos, 90) if len(pos) else 1.0
    G = np.minimum(E / ref, 1.0); G[0] = 0.0; G[L] = 0.0       # a strong edge is worth 1 whatever else is in the image (sparse axes!)
    gmin, gmax = max(1, int(np.floor(0.55 * s))), max(1, int(np.ceil(1.6 * s)))
    gs = np.arange(gmin, gmax + 1); pen = lam * ((gs - s) / s) ** 2
    NEG = -1e18
    dp = np.full(L + 1, NEG); dp[0] = 0.0; back = []
    for k in range(1, n + 1):
        new = np.full(L + 1, NEG); arg = np.zeros(L + 1, np.int32)
        for g, p in zip(gs, pen):
            cand = np.full(L + 1, NEG); cand[g:] = dp[:L + 1 - g] - p
            better = cand > new; new[better] = cand[better]; arg[better] = g
        new = new + G - drift * ((np.arange(L + 1) - k * s) / s) ** 2     # cumulative drift from the uniform grid costs too
        dp = new; back.append(arg)
    score = dp[L]
    if not want_cuts: return score, None
    cuts = [L]; b = L
    for k in range(n - 1, -1, -1):
        b -= int(back[k][b]); cuts.append(b)
    return score, cuts[::-1]

def _rigid_share(E, n, shift):
    """Share of the edge energy that lies at the cuts of a uniform n-cell grid (each cut may move by a few pixels)."""
    L = len(E) - 1; s = L / n; w = max(1, int(round(0.15 * s)))
    pos = np.rint((np.arange(1, n) + shift) * s).astype(int); pos = pos[(pos > w) & (pos < L - w)]
    if len(pos) == 0 or E.sum() <= 0: return 0.0
    win = np.stack([E[pos + d] for d in range(-w, w + 1)]).max(0)
    return float(win.sum() / E.sum())

def _gain(E, n, lam):
    """How far the uniform n-cell grid beats luck: its edge share against the same grid shifted by 0.3..0.7 of a cell,
    in standard deviations (a sparse grid that hits one big edge by chance has a wide luck range, so it scores low)."""
    f0 = _rigid_share(E, n, 0.0)
    nl = np.array([_rigid_share(E, n, k / 10) for k in range(3, 8)])
    return (f0 - nl.mean()) / (nl.std() + 0.01)

def _fft_candidates(E, top=6):
    """Cell counts whose spectrum peaks are the strongest: the true count is usually among them (not always the biggest)."""
    L = len(E) - 1; v = E - E.mean(); F = np.abs(np.fft.rfft(v * np.hanning(len(v)))); F[:4] = 0; F[L // 3:] = 0
    pk = [k for k in range(5, len(F) - 1) if F[k] >= F[k - 1] and F[k] >= F[k + 1] and F[k] > 0]
    return sorted(pk, key=lambda k: -F[k])[:top]

def _flat(D, axis, n, frac=0.6):
    """Mean variance inside the central `frac` of each of n uniform cells (true cells are flat inside)."""
    X = D if axis == 1 else D.transpose(1, 0, 2); H, L, C = X.shape
    S1 = np.concatenate([np.zeros((H, 1, C)), np.cumsum(X, 1)], 1); S2 = np.concatenate([np.zeros((H, 1, C)), np.cumsum(X ** 2, 1)], 1)
    s = L / n; x0 = np.arange(n) * s; m = (1 - frac) / 2 * s
    a = np.rint(x0 + m).astype(int); b = np.minimum(np.maximum(np.rint(x0 + s - m).astype(int), a + 2), L); a = np.minimum(a, b - 2)
    cnt = (b - a)[None, :, None]; mean = (S1[:, b] - S1[:, a]) / cnt
    return float(np.maximum((S2[:, b] - S2[:, a]) / cnt - mean ** 2, 0).sum(-1).mean())

def dip_candidates(a, axis, k=3, nmin=8):
    """Top k distinct cell counts by dip depth (peaks at least 3 apart), best first: [(n, depth), ...]."""
    D = a.astype(float).copy(); D[D[..., 3] == 0] = 0; L = D.shape[1] if axis == 1 else D.shape[0]
    ns = list(range(nmin, L // 3 + 1)); F = np.array([_flat(D, axis, n) for n in ns]); out = []
    r = np.array([np.median([F[j] for j in range(max(0, i - 6), min(len(ns), i + 7)) if abs(j - i) >= 2]) / max(F[i], 1e-3) for i in range(len(ns))])
    for i in np.argsort(-r):
        if all(abs(ns[i] - n) > 2 for n, _ in out): out.append((ns[i], round(float(r[i]), 2)))
        if len(out) == k: break
    return out

def dip_pick(a, axis, nmin=8, frac=0.5):
    """Auto cell count: the smallest n whose interior flatness dips clearly below its neighbours' (depth = neighbour median / own).
    Measured: right (+-1) on 78% of axes on smooth upscales, 21% on elastic grids. Returns (n, depth); depth < ~2 means unsure."""
    D = a.astype(float).copy(); D[D[..., 3] == 0] = 0; L = D.shape[1] if axis == 1 else D.shape[0]
    ns = list(range(nmin, L // 3 + 1)); F = np.array([_flat(D, axis, n) for n in ns]); r = np.zeros(len(ns))
    for i in range(len(ns)):
        nb = [F[j] for j in range(max(0, i - 6), min(len(ns), i + 7)) if abs(j - i) >= 2]
        r[i] = np.median(nb) / max(F[i], 1e-3) if nb else 0
    ok = [n for n, v in zip(ns, r) if v >= frac * r.max() and v >= 1.5]
    n = min(ok) if ok else ns[int(r.argmax())]
    return n, float(r.max())

def fit_axis(E, lam, n_fixed=None, tol=0, n_min=4, drift=0.1, n_auto=None, auto_tol=1):
    L = len(E) - 1
    if n_auto and not n_fixed: n_fixed, tol = n_auto, auto_tol
    if n_fixed:
        rng = [n for n in range(max(n_min, n_fixed - tol), n_fixed + tol + 1) if n <= L]
    else:
        rng = _fft_candidates(E) or list(range(n_min, max(n_min + 1, L // 3 + 1)))
    gains = {n: _gain(E, n, lam) for n in rng}
    best = max(gains, key=gains.get)
    cuts = _path(E, best, lam, True, drift)[1]
    return best, cuts, gains[best], sorted(gains.items(), key=lambda kv: -kv[1])[:3]

def exact_cells(a, axis):
    """cell count when this axis is an exact whole-number nearest-neighbour upscale (every k-wide group of columns/rows identical,
    the largest such k >= 2); None otherwise. A noisy, blurred or warped image is never exact, so it falls through to the dip rule."""
    L = a.shape[axis]
    for k in range(L // 2, 1, -1):
        if L % k: continue
        g = a.reshape(a.shape[0], L // k, k, a.shape[2]) if axis == 1 else a.reshape(L // k, k, a.shape[1], a.shape[2])
        first = g[:, :, :1] if axis == 1 else g[:, :1]
        if (g == first).all(): return L // k
    return None

def sample(a, cx, cy):
    out = np.zeros((len(cy) - 1, len(cx) - 1, 4), np.uint8)
    for j in range(len(cy) - 1):
        for i in range(len(cx) - 1):
            x0, x1, y0, y1 = cx[i], cx[i + 1], cy[j], cy[j + 1]
            mx, my = max(0, (x1 - x0) // 5), max(0, (y1 - y0) // 5)
            c = a[y0 + my:max(y0 + my + 1, y1 - my), x0 + mx:max(x0 + mx + 1, x1 - mx)].reshape(-1, 4)
            opq = c[:, 3] >= 128
            if opq.mean() >= 0.5:
                out[j, i, :3] = np.median(c[opq][:, :3], axis=0); out[j, i, 3] = 255
    return out

def snap(img, cells=None, tol=0, lam=8.0, drift=0.1, min_depth=1.1, auto_tol=0):
    a = np.array(img.convert("RGBA")); H, W = a.shape[:2]
    dx = dy = None; ax = ay = None; ex = ey = None
    if not cells:
        ex, ey = exact_cells(a, 1), exact_cells(a, 0)           # a clean whole-number upscale is recognised exactly, before any guessing
        ax, dx = dip_pick(a, 1); ay, dy = dip_pick(a, 0)
        if dx < min_depth: ax = None
        if dy < min_depth: ay = None
    nx, cx, gx, rx = fit_axis(edge_profile(a, 1), lam, cells[0] if cells else ex, tol, drift=drift, n_auto=ax, auto_tol=auto_tol)
    ny, cy, gy, ry = fit_axis(edge_profile(a, 0), lam, cells[1] if cells else ey, tol, drift=drift, n_auto=ay, auto_tol=auto_tol)
    rep = {"cells": (nx, ny), "exact_upscale": (ex is not None, ey is not None), "dip_depth": (dx and round(dx, 2), dy and round(dy, 2)), "score": (round(float(gx), 2), round(float(gy), 2)),
           "candidates": ([(n, round(float(g), 2)) for n, g in rx], [(n, round(float(g), 2)) for n, g in ry])}
    return Image.fromarray(sample(a, cx, cy), "RGBA"), rep

def selftest():
    rng = np.random.default_rng(3); s = rng.integers(0, 4, (24, 20))
    pal = np.array([[0, 0, 0, 0], [220, 30, 30, 255], [30, 200, 30, 255], [30, 30, 220, 255]], np.uint8)
    big = np.array(Image.fromarray(pal[s], "RGBA").resize((20 * 7, 24 * 7), Image.NEAREST)).astype(float)
    big[..., :3] += rng.normal(0, 4, big[..., :3].shape) * (big[..., 3:] > 0)
    out, rep = snap(Image.fromarray(np.clip(big, 0, 255).astype(np.uint8), "RGBA"))
    assert out.size == (20, 24), (out.size, rep)
    assert np.array(out)[..., 3].astype(bool).tolist() == (pal[s][..., 3] > 0).tolist(), "transparency wrong"
    ex_img = Image.fromarray(pal[s], "RGBA").resize((20 * 3, 24 * 3), Image.NEAREST)          # a clean 3x upscale is found exactly
    out2, rep2 = snap(ex_img); assert out2.size == (20, 24) and rep2["exact_upscale"] == (True, True), rep2
    assert np.array_equal(np.array(out2), pal[s]), "exact upscale must come back pixel for pixel"
    print("selftest ok", rep)

if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]: selftest(); sys.exit()
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--candidates", action="store_true", help="auto size is unreliable: save the 3 best size guesses as dst_WxH.png to pick by eye")
    ap.add_argument("--cells", nargs=2, type=int); ap.add_argument("--tol", type=int, default=0); ap.add_argument("--lam", type=float, default=8.0); ap.add_argument("--drift", type=float, default=0.1)
    a = ap.parse_args()
    if a.candidates:
        im = Image.open(a.src).convert("RGBA"); arr = np.array(im); cx, cy = dip_candidates(arr, 1), dip_candidates(arr, 0); base = a.dst.rsplit(".", 1)[0]
        for (nx, dx), (ny, dy) in zip(cx, cy):
            f = f"{base}_{nx}x{ny}.png"; snap(im, (nx, ny))[0].save(f); print(f, "depth", dx, dy)
        sys.exit()
    out, rep = snap(Image.open(a.src), tuple(a.cells) if a.cells else None, a.tol, a.lam, a.drift)
    out.save(a.dst); print(rep)
