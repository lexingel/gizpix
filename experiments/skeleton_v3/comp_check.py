# SPDX-License-Identifier: AGPL-3.0-or-later
"""comp_check.py - the real paperdoll composition: base walk frame + the layer cut from the outfit walk frame, composited, compared with the generated outfit frame.
Per frame: match = share of the outfit's opaque pixels where composite colour is within 36 (RGB sum diff) of the outfit pixel; IoU = silhouette overlap; extra = composite pixels that the outfit frame does not have.
Writes comp_<outfit>_<dir>.gif (base | composite | generated outfit, x4) for east and south, and prints a table. python comp_check.py"""
import sys, os, shutil, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); L = os.path.join(HERE, "..", "..", "layers", "pix_layer.py")
DIRS = ["south", "south-east", "east", "north-east", "north", "north-west", "west", "south-west"]
def ld(o, d, i): return Image.open(f"{HERE}/../../samples/walk_frames/{o}/{d}/{i}.png").convert("RGBA")
def cut(o, d, i):
    t = tempfile.mkdtemp(); os.makedirs(t + "/b"); os.makedirs(t + "/o"); ld("base", d, i).save(t + "/b/south.png"); ld(o, d, i).save(t + "/o/south.png")
    subprocess.run([sys.executable, L, "cut", t + "/b", t + "/o", t + "/l", "--name", "x", "--solid", "--drop-skin", "auto"], capture_output=True)
    p = t + "/l/x/south.png"; im = Image.open(p).convert("RGBA") if os.path.exists(p) else Image.new("RGBA", (96, 96)); im.load(); shutil.rmtree(t, ignore_errors=True); return im
def job(a):
    o, d, i = a; base, out, lay = ld("base", d, i), ld(o, d, i), cut(o, d, i); comp = Image.alpha_composite(base, lay)
    c, g = np.array(comp), np.array(out); mc, mg = c[..., 3] > 0, g[..., 3] > 0; close = np.abs(c[..., :3].astype(int) - g[..., :3]).sum(-1) <= 36
    mb = np.array(base)[..., 3] > 0
    return (o, d, i), (float((mg & mc & close).sum() / max(1, mg.sum())), float((mc & mg).sum() / max(1, (mc | mg).sum())), int((mc & ~mg).sum()), float((mb & mg).sum() / max(1, (mb | mg).sum()))), (base, comp, out)
jobs = [(o, d, i) for o in ("pauld", "robe") for d in DIRS for i in range(8)]
with ThreadPoolExecutor(4) as ex: res = list(ex.map(job, jobs))
tab = {}
for (o, d, i), m, _ in res: tab.setdefault((o, d), []).append(m)
print("outfit    direction    match  IoU   extra px/frame   bare-base IoU (base alone vs the generated outfit frame)")
for (o, d), v in tab.items(): print(f"{o:8s}  {d:11s}  {np.mean([x[0] for x in v]):.2f}  {np.mean([x[1] for x in v]):.2f}  {np.mean([x[2] for x in v]):.1f}            {np.mean([x[3] for x in v]):.2f}")
for o in ("pauld", "robe"):
    for d in ("east", "south"):
        fr = []
        for (oo, dd, i), _, ims in res:
            if oo == o and dd == d:
                sh = Image.new("RGBA", (3 * 98, 98), (70, 70, 80, 255))
                for k, im in enumerate(ims): sh.paste(im, (k * 98 + 1, 1), im)
                fr.append(sh.resize((sh.width * 3, sh.height * 3), Image.NEAREST).convert("P", palette=Image.ADAPTIVE))
        fr[0].save(f"{HERE}/comp_{o}_{d}.gif", save_all=True, append_images=fr[1:], duration=120, loop=0)
