# SPDX-License-Identifier: AGPL-3.0-or-later
"""exp3.py - three free checks on the skeleton-v3 walk frames:
 1. wear test   : paste each cut layer onto a recoloured base (warm hair/skin/boots turned teal) and look for leaked orange bits
 2. tolerance   : is a layer 'body' pixel within a 3x3 neighbourhood of a same-coloured base pixel? (position drift check; stands in for a motion check)
 3. dark skin   : dark-skinned pair with a dark brown robe, cut with --drop-skin auto, compared with the light pair's layer (IoU, kept share)
python exp3.py 1|2|3"""
import sys, os, shutil, subprocess, tempfile, colorsys
import numpy as np
from PIL import Image
from scipy.ndimage import maximum_filter
HERE = os.path.dirname(os.path.abspath(__file__)); L = os.path.join(HERE, "..", "..", "layers", "pix_layer.py"); DIRS = ["south", "east", "north", "west"]
def hsv(a):
    rgb = a[..., :3] / 255.0; mx = rgb.max(-1); mn = rgb.min(-1); d = np.maximum(mx - mn, 1e-6); r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6
    return h, np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0), mx
def hsv2rgb(h, s, v):
    out = np.zeros(h.shape + (3,), np.uint8)
    for idx in np.ndindex(h.shape): out[idx] = [int(c * 255) for c in colorsys.hsv_to_rgb(h[idx] % 1, min(1, max(0, s[idx])), min(1, max(0, v[idx])))]
    return out
def recolor(a, warm=None, cool=None):
    """warm=(dh, vmul) applied to warm pixels (hue<=0.12 or >=0.95, sat>0.2); cool=(h_new, vmul) to blue pixels (0.5..0.75, sat>0.3)"""
    a = a.copy(); h, s, v = hsv(a.astype(float)); m = a[..., 3] > 0
    if warm:
        w = m & ((h <= 0.12) | (h >= 0.95)) & (s > 0.2); h2, s2, v2 = h.copy(), s.copy(), v.copy(); h2[w] += warm[0]; v2[w] *= warm[1]; a[w, :3] = hsv2rgb(h2, s2, v2)[w]
    if cool:
        c = m & (h >= 0.5) & (h <= 0.75) & (s > 0.3); h2, s2, v2 = h.copy(), s.copy(), v.copy(); h2[c] = cool[0]; v2[c] *= cool[1]; a[c, :3] = hsv2rgb(h2, s2, v2)[c]
    return a
def cut(base, outfit, flag=()):
    t = tempfile.mkdtemp(); os.makedirs(t + "/b"); os.makedirs(t + "/o"); Image.fromarray(base).save(t + "/b/south.png"); Image.fromarray(outfit).save(t + "/o/south.png")
    r = subprocess.run([sys.executable, L, "cut", t + "/b", t + "/o", t + "/l", "--name", "x", "--solid", *flag], capture_output=True, text=True)
    p = t + "/l/x/south.png"; a = np.array(Image.open(p)) if os.path.exists(p) else np.zeros_like(base); shutil.rmtree(t, ignore_errors=True); return a, r.stdout
ld = lambda o, d, i: np.array(Image.open(f"{HERE}/../../samples/walk_frames/{o}/{d}/{i}.png").convert("RGBA"))
def over(bg, fg): return np.array(Image.alpha_composite(Image.fromarray(bg), Image.fromarray(fg)))
def main(which):
    if which == "1":
        rows = []
        for o in ("pauld", "robe"):
            for d in DIRS:
                base = ld("base", d, 0); lay, _ = cut(base, ld(o, d, 0), ["--drop-skin", "auto"]); teal = recolor(base, warm=(0.5, 1.0))
                rows.append([base, ld(o, d, 0), over(base, lay), over(teal, lay)])
        sh = Image.new("RGB", (4 * 98, len(rows) * 98), (70, 70, 80))
        for r, row in enumerate(rows):
            for c, im in enumerate(row): sh.paste(Image.fromarray(im), (c * 98 + 1, r * 98 + 1), Image.fromarray(im))
        sh.resize((sh.width * 2, sh.height * 2), Image.NEAREST).save(f"{HERE}/wear_test.png"); print("wear_test.png")
    if which == "2":
        for o in ("pauld", "robe"):
            tot = hit = 0
            for d in DIRS:
                base = ld("base", d, 0); lay, _ = cut(base, ld(o, d, 0), ["--drop-skin", "auto"]); m = lay[..., 3] > 0
                for rad in (0, 1, 2):
                    # base colours within radius `rad`: does any base pixel there have almost the same colour?
                    near = np.zeros(m.shape, bool)
                    for dy in range(-rad, rad + 1):
                        for dx in range(-rad, rad + 1):
                            sb = np.roll(np.roll(base, dy, 0), dx, 1); near |= (sb[..., 3] > 0) & (np.abs(sb[..., :3].astype(int) - lay[..., :3]).sum(-1) < 54)
                    near &= m & (lay[..., :3].astype(int).sum(-1) >= 150); print(o, d, "radius", rad, "layer px", int(m.sum()), "have a same-coloured base pixel nearby", int(near.sum()))
    if which == "3":
        res = []
        for o, cool in ((("pauld", None), ("robe", (0.07, 0.55))) if len(sys.argv) < 3 else (("pauld", None),)):
            for d in DIRS:
                b0, o0 = ld("base", d, 0), ld(o, d, 0); truth, _ = cut(b0, o0, ["--drop-skin", "auto"])
                def dark(a):
                    a = recolor(a, warm=(0.0, 0.42), cool=cool); h, sa, v = hsv(a.astype(float)); g = (a[..., 3] > 0) & (sa < 0.35) & (o == "pauld"); a[g, :3] = (a[g, :3] * 0.4).astype(np.uint8); return a      # pauld: grey steel/shirt/trousers go dark too (same rule on base and outfit)
                b1, o1 = dark(b0), dark(o0)
                for name, flag in (("plain", []), ("auto", ["--drop-skin", "auto"]), ("near", ["--drop-skin", "near"])):
                    lay, out = cut(b1, o1, flag); t = truth[..., 3] > 0; l = lay[..., 3] > 0
                    # compare in position only: dark outfit pixels = the same positions as the light outfit's (same geometry)
                    iou = (t & l).sum() / max(1, (t | l).sum()); res.append((o, d, name, int(l.sum()), int(t.sum()), round(iou, 2), round((t & l).sum() / max(1, t.sum()), 2), "WARN" if "WARNING" in out else ""))
        for r in res: print(*r)
main(sys.argv[1] if len(sys.argv) > 1 else "1")
