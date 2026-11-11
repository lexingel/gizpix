# SPDX-License-Identifier: AGPL-3.0-or-later
"""dirs_check.py: cut layers from skeleton-v3 walk frames in all 8 directions (frames 0 and 4), with and without --bits; writes dirs_check.png (base | outfit | layer | layer+bits, bits-removed in magenta)."""
import subprocess, sys, os, shutil, tempfile
from PIL import Image
import numpy as np
L = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "layers", "pix_layer.py")
FR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "samples", "walk_frames")
FLAG = sys.argv[1:] or ["--bits"]
DIRS = ["south", "south-east", "east", "north-east", "north", "north-west", "west", "south-west"]
def cut(o, d, i, flag):
    t = tempfile.mkdtemp(); os.makedirs(t + "/b"); os.makedirs(t + "/o")
    shutil.copy(f"{FR}/base/{d}/{i}.png", t + "/b/south.png"); shutil.copy(f"{FR}/{o}/{d}/{i}.png", t + "/o/south.png")
    subprocess.run([sys.executable, L, "cut", t + "/b", t + "/o", t + "/l", "--name", "x", "--solid", "--drop-skin", "auto", *flag], capture_output=True)
    p = t + "/l/x/south.png"; a = np.array(Image.open(p)) if os.path.exists(p) else np.zeros((96, 96, 4), np.uint8); shutil.rmtree(t, ignore_errors=True); return a
rows = []; stats = {}
for o in ("pauld", "robe"):
    for d in DIRS:
        for i in (0, 4):
            a, b = cut(o, d, i, []), cut(o, d, i, FLAG); gone = (a[..., 3] > 0) & (b[..., 3] == 0); m = b.copy(); m[gone] = (255, 0, 255, 255)
            stats.setdefault((o, d), []).append(((a[..., 3] > 0).sum(), int(gone.sum())))
            if i == 0: rows.append([Image.open(f"{FR}/base/{d}/{i}.png"), Image.open(f"{FR}/{o}/{d}/{i}.png"), Image.fromarray(a), Image.fromarray(m)])
for k, v in stats.items(): print(k, "layer px", sum(x[0] for x in v) // len(v), "bits removed", sum(x[1] for x in v) // len(v))
for half in (0, 1):
    rs = rows[half * 8:(half + 1) * 8]; sh = Image.new("RGB", (4 * 98, 8 * 98), (70, 70, 80))
    for r, row in enumerate(rs):
        for c, im in enumerate(row): sh.paste(im, (c * 98 + 1, r * 98 + 1), im.convert("RGBA"))
    sfx = "" if FLAG == ["--bits"] else "_" + FLAG[0].strip("-"); sh.resize((sh.width * 2, sh.height * 2), Image.NEAREST).save("dirs_check_" + ["pauld", "robe"][half] + sfx + ".png")
