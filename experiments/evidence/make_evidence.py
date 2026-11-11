# SPDX-License-Identifier: AGPL-3.0-or-later
"""make_evidence.py FRAMES_DIR [OUT_DIR] - the pictures behind MEASUREMENTS.md, made from REAL generator frames.

FRAMES_DIR has the layout of samples/walk_frames but holds AI-generated frames (base, robe, pauld, dbase, drobe, each
<direction>/0..7.png). Those frames are not in this repository; the pictures made from them are (images/evidence/).
Writes:
  layer_robe_east.png, layer_pauld_south.png   base | outfit | cut layer | layer worn on base (frames 0, 3, 6)
  parts_robe_south.png                          cut without and with --drop-parts, leaked hair/boot pixels in red
  dark_east_holes.png                           the dark pair, east: the layer with holes (a known limit)
  clean_real.png                                injected specks/pinholes on a real frame, before and after repair
Needs numpy and Pillow. No network, no generator.   python experiments/evidence/make_evidence.py PATH/TO/frames"""
import os, random, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
Z = 4                                                  # whole-number zoom
BG = (217, 232, 214, 255); INK = (28, 42, 34, 255); RED = (196, 53, 42, 255)


def gz(*a):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "gizpix.py"), *map(str, a)], capture_output=True, text=True, cwd=ROOT)
    if r.returncode: raise SystemExit(f"gizpix {' '.join(map(str, a))} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def load(p): return Image.open(p).convert("RGBA")


def tile(im, crop=None):
    if crop: im = im.crop(crop)
    im = im.resize((im.width * Z, im.height * Z), Image.NEAREST); t = Image.new("RGBA", im.size, BG); t.alpha_composite(im); return t


def montage(rows, labels, title, path):
    """rows: list of lists of tiles; labels: column labels"""
    w, h = rows[0][0].size; pad = 10; top = 46; left = 0
    W = len(rows[0]) * (w + pad) + pad; H = top + len(rows) * (h + pad) + pad
    out = Image.new("RGBA", (W, H), (246, 250, 244, 255)); d = ImageDraw.Draw(out)
    d.text((pad, 8), title, fill=INK)
    for c, lab in enumerate(labels): d.text((pad + c * (w + pad), 28), lab, fill=INK)
    for r, row in enumerate(rows):
        for c, t in enumerate(row): out.alpha_composite(t, (pad + c * (w + pad), top + r * (h + pad)))
    out.convert("RGB").save(path); print("wrote", path)


def ubox(dirs, frames):
    ims = [load(f"{d}/{i}.png") for d in dirs for i in frames]; return bbox(*ims)


def worn(base, layer):
    b = base.copy(); b.alpha_composite(layer); return b


def cut(base_dir, outfit_dir, work, name, *flags):
    gz("pix_layer", "cut", base_dir, outfit_dir, work, "--name", name, *flags); return os.path.join(work, name)


def bbox(*ims):
    bb = [im.getchannel("A").getbbox() for im in ims]; bb = [b for b in bb if b]
    x0 = min(b[0] for b in bb) - 4; y0 = min(b[1] for b in bb) - 4; x1 = max(b[2] for b in bb) + 4; y1 = max(b[3] for b in bb) + 4
    return (max(0, x0), max(0, y0), min(96, x1), min(96, y1))


def layer_figure(src, out, work, pair, view, frames=(0, 3, 6), name=None):
    b, o = os.path.join(src, "base" if pair != "dark" else "dbase", view), os.path.join(src, {"robe": "robe", "pauld": "pauld", "dark": "drobe"}[pair], view)
    lay = cut(b, o, work, f"{pair}_{view}", "--solid", "--drop-skin", "auto", "--bits", "--drop-parts")
    rows = []; box = ubox([b, o], frames)
    for i in frames:
        B, O, L = load(f"{b}/{i}.png"), load(f"{o}/{i}.png"), load(f"{lay}/{i}.png")
        rows.append([tile(x, box) for x in (B, O, L, worn(B, L))])
    montage(rows, ["base", "outfit (generated)", "cut layer", "layer worn on base"], f"{pair} {view}: frames " + ", ".join(map(str, frames)), out)


def parts_figure(src, out, work):
    b, o = f"{src}/base/south", f"{src}/robe/south"
    plain = cut(b, o, work, "plain", "--solid", "--drop-skin", "auto", "--bits"); parts = cut(b, o, work, "parts", "--solid", "--drop-skin", "auto", "--bits", "--drop-parts")
    rows = []; box = ubox([b, o], (0, 3, 6))
    for i in (0, 3, 6):
        B, O, P, Q = load(f"{b}/{i}.png"), load(f"{o}/{i}.png"), load(f"{plain}/{i}.png"), load(f"{parts}/{i}.png")
        gone = np.array(P)[..., 3] > 0; gone &= ~(np.array(Q)[..., 3] > 0)           # pixels --drop-parts removed
        mark = np.array(P); mark[gone] = (196, 53, 42, 255)
        rows.append([tile(x, box) for x in (O, P, Image.fromarray(mark), Q)])
    montage(rows, ["outfit (generated)", "without --drop-parts", "removed (red)", "with --drop-parts"], "robe south: hair tips and boots", out)


def clean_figure(src, out, work):
    rng = random.Random(5); b = f"{src}/robe/east"; d = os.path.join(work, "dmg"); os.makedirs(d, exist_ok=True); rows = []
    for i in (0, 3, 6):
        a = np.array(load(f"{b}/{i}.png")); ys, xs = np.nonzero(a[..., 3] > 0)
        core = [(y, x) for y, x in zip(ys, xs) if (a[y - 1:y + 2, x - 1:x + 2, 3] > 0).all()]
        for k, (y, x) in enumerate(rng.sample(core, 8)):
            if k < 5: a[y, x, :3] = [(40 + 60 * k) % 256, 210 - 30 * k, 90 + 25 * k]; a[y, x, 3] = 255       # off-palette speck
            else: a[y, x, 3] = 0                                                                              # pinhole
        Image.fromarray(a).save(f"{d}/{i}.png")
    o1 = os.path.join(work, "sp"); o2 = os.path.join(work, "ph")
    os.makedirs(o1, exist_ok=True)
    for i in (0, 3, 6): gz("speck_fix", f"{d}/{i}.png", f"{o1}/{i}.png")
    gz("fill_pinholes", o1, "--out", o2)
    box = ubox([b], (0, 3, 6))
    for i in (0, 3, 6):
        rows.append([tile(load(f"{p}/{i}.png"), box) for p in (b, d, o2)])
    montage(rows, ["original", "damaged (5+3)", "repaired"], "robe east: injected defects and repair", out)


def main(argv):
    if not argv: raise SystemExit(__doc__)
    src = os.path.abspath(argv[0]); out = os.path.abspath(argv[1]) if len(argv) > 1 else os.path.join(ROOT, "images", "evidence")
    os.makedirs(out, exist_ok=True); work = tempfile.mkdtemp(prefix="evidence_")
    try:
        layer_figure(src, f"{out}/layer_robe_east.png", work, "robe", "east")
        layer_figure(src, f"{out}/layer_pauld_south.png", work, "pauld", "south")
        parts_figure(src, f"{out}/parts_robe_south.png", work)
        layer_figure(src, f"{out}/dark_east_holes.png", work, "dark", "east", frames=(0, 3, 6))
        clean_figure(src, f"{out}/clean_real.png", work)
    finally: shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__": main(sys.argv[1:])
