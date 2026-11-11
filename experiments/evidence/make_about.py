# SPDX-License-Identifier: AGPL-3.0-or-later
"""make_about.py FRAMES_DIR [OUT_DIR] - the extra pictures used by ABOUT.md.

FRAMES_DIR has the layout of samples/walk_frames but holds real AI-generated frames (not in this repository).
Writes to images/about/ (CC0, like images/evidence/):
  recolour_real.png   a robe frame: original | whole picture turned | only the blue robe turned | only the robe, other way
  walk_sheet.png      the 8 frames of a walk packed by make_sheet (4 columns) and the JSON size line
  walk_robe.gif       preview_gif of the same walk
  styles.png          one inn drawn by pixdraw in the five bundled styles (needs no frames)
Run:  python experiments/evidence/make_about.py PATH/TO/frames"""
import json, os, shutil, subprocess, sys, tempfile
from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BG = (217, 232, 214, 255); PAPER = (246, 250, 244, 255); INK = (28, 42, 34, 255)


def gz(*a):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "gizpix.py"), *map(str, a)], capture_output=True, text=True, cwd=ROOT)
    if r.returncode: raise SystemExit(f"gizpix {' '.join(map(str, a))} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def load(p): return Image.open(p).convert("RGBA")


def tile(im, z, box=None, bg=BG):
    if box: im = im.crop(box)
    im = im.resize((im.width * z, im.height * z), Image.NEAREST); t = Image.new("RGBA", im.size, bg); t.alpha_composite(im); return t


def row(tiles, labels, title, path, pad=10):
    w, h = tiles[0].size; top = 46
    out = Image.new("RGB", (len(tiles) * (w + pad) + pad, top + h + pad), PAPER[:3]); d = ImageDraw.Draw(out)
    d.text((pad, 8), title, fill=INK[:3])
    for i, (t, lab) in enumerate(zip(tiles, labels)):
        d.text((pad + i * (w + pad), 28), lab, fill=INK[:3]); out.paste(t.convert("RGB"), (pad + i * (w + pad), top))
    out.save(path); print("wrote", path)


def recolour(src, out, work):
    f = f"{src}/robe/east/3.png"; box = load(f).getchannel("A").getbbox(); box = (box[0] - 6, box[1] - 6, box[2] + 6, box[3] + 6)
    variants = [("original", None), ("whole picture, hue +120", ["--hue", "120"]), ("only the blue robe, +120", ["--hue", "120", "--range", "0.55,0.72"]),
                ("only the blue robe, -100", ["--hue", "-100", "--range", "0.55,0.72"])]
    tiles = []
    for k, (lab, args) in enumerate(variants):
        p = f
        if args: d = os.path.join(work, f"hs{k}"); gz("hue_shift", f, "--out", d, *args); p = os.path.join(d, "3.png")
        tiles.append(tile(load(p), 4, box))
    row(tiles, [v[0] for v in variants], "hue_shift on one frame of the walk", f"{out}/recolour_real.png")


def sheet(src, out, work):
    frames = [f"{src}/robe/east/{i}.png" for i in range(8)]; base = os.path.join(work, "sheet")
    gz("make_sheet", base, *frames, "--cols", "4", "--fps", "10")
    im = load(base + ".png"); im = im.resize((im.width * 2, im.height * 2), Image.NEAREST); t = Image.new("RGBA", im.size, BG); t.alpha_composite(im)
    t.convert("RGB").save(f"{out}/walk_sheet.png"); print("wrote", f"{out}/walk_sheet.png", im.size)
    j = json.load(open(base + ".json", encoding="utf-8")); print("sheet json keys:", list(j)[:6])
    gz("preview_gif", f"{out}/walk_robe.gif", frames[0], *frames, "--beat", "even", "--fps", "10", "--scale", "3"); print("wrote", f"{out}/walk_robe.gif")


def styles(out, work):
    names = ["dark_fantasy", "bright_cartoon", "desert", "frost", "retro16"]; tiles = []
    for n in names:
        d = os.path.join(work, "st_" + n); gz("pixdraw", "build", "type=inn,proj=iso,floors=2", "--style", n, "--out", d, "--name", "inn", "--scale", "3")
        tiles.append(load(os.path.join(d, "inn.png")))
    w = max(t.width for t in tiles); h = max(t.height for t in tiles)
    row([tile(t, 1, None) if t.size == (w, h) else _pad(t, w, h) for t in tiles], [n.replace("_", " ") for n in names], "pixdraw: the same inn in the five styles", f"{out}/styles.png")


def _pad(t, w, h):
    c = Image.new("RGBA", (w, h), BG); c.alpha_composite(t, ((w - t.width) // 2, h - t.height)); return c


def main(argv):
    if not argv: raise SystemExit(__doc__)
    src = os.path.abspath(argv[0]); out = os.path.abspath(argv[1]) if len(argv) > 1 else os.path.join(ROOT, "images", "about")
    os.makedirs(out, exist_ok=True); work = tempfile.mkdtemp(prefix="about_")
    try: recolour(src, out, work); sheet(src, out, work); styles(out, work)
    finally: shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__": main(sys.argv[1:])
