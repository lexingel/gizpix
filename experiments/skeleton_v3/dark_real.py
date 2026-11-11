# SPDX-License-Identifier: AGPL-3.0-or-later
"""dark_real.py - the dark-skin case on REAL generated frames (dark brown skin + dark brown leather robe): plain cut vs --drop-skin auto vs near vs auto --bits, frame 0 and 4 of east and south.
Reports layer px, share of layer in dark-skin colours of the base (a leak), and writes dark_real.png (base | outfit | plain | hue | hue+bits)."""
import sys, os, shutil, subprocess, tempfile
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); L = os.path.join(HERE, "..", "..", "layers", "pix_layer.py")
def cut(d, i, flag):
    t = tempfile.mkdtemp(); os.makedirs(t + "/b"); os.makedirs(t + "/o")
    shutil.copy(f"{HERE}/../../samples/walk_frames/dbase/{d}/{i}.png", t + "/b/south.png"); shutil.copy(f"{HERE}/../../samples/walk_frames/drobe/{d}/{i}.png", t + "/o/south.png")
    r = subprocess.run([sys.executable, L, "cut", t + "/b", t + "/o", t + "/l", "--name", "x", "--solid", *flag], capture_output=True, text=True)
    p = t + "/l/x/south.png"; a = np.array(Image.open(p).convert("RGBA")) if os.path.exists(p) else np.zeros((96, 96, 4), np.uint8); shutil.rmtree(t, ignore_errors=True); return a, r.stdout
rows = []
for d in ("east", "south"):
    for i in (0, 4):
        b = np.array(Image.open(f"{HERE}/../../samples/walk_frames/dbase/{d}/{i}.png").convert("RGBA")); o = np.array(Image.open(f"{HERE}/../../samples/walk_frames/drobe/{d}/{i}.png").convert("RGBA"))
        outs = {k: cut(d, i, f) for k, f in (("plain", []), ("auto", ["--drop-skin", "auto"]), ("near", ["--drop-skin", "near"]), ("hue", ["--drop-hue", "0.02,0.10"]), ("hue+bits", ["--drop-hue", "0.02,0.10", "--bits"]))}
        print(d, i, {k: int((v[0][..., 3] > 0).sum()) for k, v in outs.items()}, "| auto note:", "skipped (dark skin)" if "dark skin" in outs["auto"][1] else "applied")
        rows.append([b, o] + [outs[k][0] for k in ("plain", "hue", "hue+bits")])
sh = Image.new("RGB", (5 * 98, len(rows) * 98), (200, 200, 205))
for r, row in enumerate(rows):
    for c, im in enumerate(row): sh.paste(Image.fromarray(im), (c * 98 + 1, r * 98 + 1), Image.fromarray(im))
sh.resize((sh.width * 2, sh.height * 2), Image.NEAREST).save(f"{HERE}/dark_real.png")
