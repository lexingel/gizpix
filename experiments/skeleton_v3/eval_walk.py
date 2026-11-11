# SPDX-License-Identifier: AGPL-3.0-or-later
"""eval_walk.py BASE_DIR OUTFIT_DIR [--truth DIR] [--drop-hue LO,HI]
Same-named PNG walk frames (0.png ... n.png): the character without and with the outfit. Reports what decides whether paperdolling works on the frames:
  1. alignment : per-frame silhouette IoU base vs outfit (skeleton-driven frames should be ~1.0; independently generated frames drift)
  2. stability : share of pixels that are identical in both frames where both are opaque (low = the generator re-shaded the body = skin leaks)
  3. layers    : px/frame of the cut layer (plain / --solid --drop-skin auto / --solid --drop-skin near), and the share of layer pixels in skin hues (hue<=0.12, sat>0.15, value>0.4)
Layout differs from pix_layer (it wants direction names), so the frames are copied to a temp dir as 'f00.png'... --truth DIR: hand-made layer frames (same names/order); adds IoU and kept share per mode. Free, local. Run on an old pair and on a skeleton-v3 pair to compare."""
import os, sys, glob, shutil, subprocess, tempfile
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); LAYER = os.path.join(HERE, "..", "..", "layers", "pix_layer.py")
def load(d): return [np.array(Image.open(p).convert("RGBA")) for p in sorted(glob.glob(os.path.join(d, "*.png")))]
def hsv(a):
    rgb = a[..., :3] / 255.0; mx = rgb.max(-1); mn = rgb.min(-1); dd = np.maximum(mx - mn, 1e-6); r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.where(mx == r, ((g - b) / dd) % 6, np.where(mx == g, (b - r) / dd + 2, (r - g) / dd + 4)) / 6
    return h, np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0), mx
def tr(L, T):
    tp = fp = fn = 0
    for a, b in zip(L, T): l, t = a[..., 3] > 0, b[..., 3] > 0; tp += (l & t).sum(); fp += (l & ~t).sum(); fn += (t & ~l).sum()
    return f" | vs truth IoU {tp / max(1, tp + fp + fn):.2f} kept {tp / max(1, tp + fn):.2f}"
def main(bd, od, extra, truth=None):
    T = load(truth) if truth else None
    B, O = load(bd), load(od); n = min(len(B), len(O)); assert n, "no frames"
    iou = [((B[i][..., 3] > 0) & (O[i][..., 3] > 0)).sum() / max(1, ((B[i][..., 3] > 0) | (O[i][..., 3] > 0)).sum()) for i in range(n)]
    same = []
    for i in range(n):
        both = (B[i][..., 3] > 0) & (O[i][..., 3] > 0); same.append((np.abs(B[i][..., :3].astype(int) - O[i][..., :3]).sum(-1)[both] == 0).mean() if both.any() else 0)
    print(f"{n} frames | alignment IoU mean {np.mean(iou):.2f} min {np.min(iou):.2f} | stability (identical pixels) mean {np.mean(same):.2f} min {np.min(same):.2f}")
    t = tempfile.mkdtemp(prefix="evalwalk_")
    for k, A in (("base", B), ("outfit", O)):
        os.makedirs(f"{t}/{k}")
        for i in range(n): Image.fromarray(A[i]).save(f"{t}/{k}/f{i:02d}.png")
    for tag, opts in (("plain", []), ("solid+auto", ["--solid", "--drop-skin", "auto"]), ("solid+near", ["--solid", "--drop-skin", "near"])):
        out = f"{t}/out_{tag}"; r = subprocess.run([sys.executable, LAYER, "cut", f"{t}/base", f"{t}/outfit", out, "--name", "L", *opts, *extra], capture_output=True, text=True)
        L = load(f"{out}/L") if os.path.isdir(f"{out}/L") else []
        if not L: print(f"{tag:11s} no layer: {(r.stdout + r.stderr)[-120:]}"); continue
        px = [(a[..., 3] > 0).sum() for a in L]; hh = []; warns = sum("WARNING" in l for l in r.stdout.splitlines())
        for a in L:
            m = a[..., 3] > 0; h, s, v = hsv(a); hh.append(((h <= 0.12) & (s > 0.15) & (v > 0.4) & m).sum() / max(1, m.sum()))
        print(f"{tag:11s} layer px/frame {np.mean(px):6.0f} (min {min(px)}, max {max(px)}) | skin-hue share {np.mean(hh):.2f} | warnings {warns}" + (tr(L, T) if T else ""))
    shutil.rmtree(t, ignore_errors=True)
if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2: print(__doc__); sys.exit()
    truth = None
    if "--truth" in a: i = a.index("--truth"); truth = a[i + 1]; a = a[:i] + a[i + 2:]
    main(a[0], a[1], a[2:], truth)
