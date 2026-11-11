# SPDX-License-Identifier: AGPL-3.0-or-later
"""warp_layer.py - move a standing outfit layer onto moving base frames by following the base's own motion (optical flow).
python warp_layer.py BASE_STAND.png LAYER_STAND.png BASE_FRAMES_DIR OUT_DIR [--truth OUTFIT_FRAMES_DIR]
For each frame i: flow from the base frame back to the standing base, pull the layer pixels through it with nearest sampling
(no blending, so the pixel art palette stays exact). With --truth it prints how many pixels differ from the real outfit frame
(base frame + warped layer vs the generated outfit frame), against a no-warp baseline. Local, free."""
import sys as _sys
if any(_a in ("-h", "--help") for _a in _sys.argv[1:]): print(__doc__); _sys.exit(0)     # -h always prints the documentation, exit 0
import sys, os, glob
import numpy as np, cv2
from PIL import Image

def prep(a, up=4):
    g = a.astype(np.float32).copy(); g[a[..., 3] == 0] = 0
    g = np.concatenate([g[..., :3], (a[..., 3:] > 0) * 255.0], -1)
    return cv2.resize(g, None, fx=up, fy=up, interpolation=cv2.INTER_NEAREST)

def flow_back(stand, frame, up=4, win=41, lev=5, poly=7):   # tuned on true LPC layers and the generated walk pair
    s, f = prep(stand, up), prep(frame, up)
    gs = cv2.cvtColor(np.clip(s[..., :3], 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32) + 0.5 * s[..., 3]
    gf = cv2.cvtColor(np.clip(f[..., :3], 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32) + 0.5 * f[..., 3]
    gs, gf = np.clip(gs, 0, 255).astype(np.uint8), np.clip(gf, 0, 255).astype(np.uint8)
    fl = cv2.calcOpticalFlowFarneback(gf, gs, None, 0.5, lev, win, 5, poly, 1.5, 0)      # frame -> stand
    H, W = stand.shape[:2]; fl = cv2.resize(fl, (W, H), interpolation=cv2.INTER_AREA) / up   # back to sprite pixels, rounded below
    return fl

def warp(layer, fl):
    H, W = layer.shape[:2]; yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    mx, my = xx + np.rint(fl[..., 0]), yy + np.rint(fl[..., 1])
    return cv2.remap(layer, mx, my, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

def over(base, layer):
    out = base.copy(); m = layer[..., 3] > 0; out[m] = layer[m]; return out

def diff(a, b):
    am, bm = a[..., 3] > 0, b[..., 3] > 0; both = am & bm
    return int((am ^ bm).sum() + ((np.abs(a[..., :3].astype(int) - b[..., :3]).sum(-1) > 60) & both).sum())

if __name__ == "__main__":
    A = sys.argv[1:]; truth = A[A.index("--truth") + 1] if "--truth" in A else None
    stand = np.array(Image.open(A[0]).convert("RGBA")); layer = np.array(Image.open(A[1]).convert("RGBA")); os.makedirs(A[3], exist_ok=True)
    tot0 = tot1 = 0
    for p in sorted(glob.glob(os.path.join(A[2], "[0-9]*.png"))):
        n = os.path.basename(p); fr = np.array(Image.open(p).convert("RGBA")); w = warp(layer, flow_back(stand, fr))
        comp = over(fr, w); Image.fromarray(comp).save(os.path.join(A[3], n)); Image.fromarray(w).save(os.path.join(A[3], "layer_" + n))
        if truth:
            t = np.array(Image.open(os.path.join(truth, n)).convert("RGBA")); d0, d1 = diff(over(fr, layer), t), diff(comp, t); tot0 += d0; tot1 += d1
            print(n, "no-warp differs", d0, "warped differs", d1)
    if truth: print("total no-warp", tot0, "warped", tot1)
