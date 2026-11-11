"""make_demos.py - regenerate the three README pictures in images/ from the bundled sample frames and pixdraw.  python experiments/demos/make_demos.py
  1. outfit_layer.png : base | outfit | cut layer | layer worn on the base   (pix_layer cut on samples/walk_frames, frames 0, 3, 6, robe east)
  2. repair.png       : a damaged frame, then speck_fix + fill_pinholes, with pixel_lint numbers
  3. village.gif      : pixdraw scene, two styles side by side, looping
Needs only the repository; no network, no generator."""
import glob, json, os, random, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "samples", "walk_frames"); OUT = os.path.join(ROOT, "images"); os.makedirs(OUT, exist_ok=True)
def px(*a, cwd=ROOT):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "gizpix.py"), *map(str, a)], capture_output=True, text=True, cwd=cwd)
    if r.returncode: raise SystemExit(f"{a[:3]} failed: {r.stderr[-300:]}")
    return r.stdout
BG = (52, 52, 64, 255)
def on_bg(im, s=3):
    im = im.convert("RGBA"); b = Image.new("RGBA", im.size, BG); b.alpha_composite(im); return b.resize((im.width * s, im.height * s), Image.NEAREST)
def sheet(cols, labels, pad=8, top=22):
    h = max(c.height for c in cols); w = sum(c.width for c in cols) + pad * (len(cols) + 1); s = Image.new("RGBA", (w, h + top + pad), (30, 30, 38, 255)); d = ImageDraw.Draw(s); x = pad
    for c, l in zip(cols, labels): s.paste(c, (x, top)); d.text((x + 2, 5), l, fill=(230, 230, 230)); x += c.width + pad
    return s

# 1. outfit layer
T = tempfile.mkdtemp(prefix="demo_"); b, o = T + "/b", T + "/o"; os.makedirs(b); os.makedirs(o)
for i in range(8): shutil.copy(f"{SRC}/base/east/{i}.png", f"{b}/{i}.png"); shutil.copy(f"{SRC}/robe/east/{i}.png", f"{o}/{i}.png")
px("pix_layer", "cut", b, o, T + "/L", "--name", "robe", "--solid", "--drop-skin", "auto", "--bits", "--drop-parts")
rows = []
for i in (0, 3, 6):
    base, outfit, layer = (Image.open(p).convert("RGBA") for p in (f"{b}/{i}.png", f"{o}/{i}.png", f"{T}/L/robe/{i}.png")); worn = base.copy(); worn.alpha_composite(layer)
    rows.append(sheet([on_bg(x) for x in (base, outfit, layer, worn)], ["base", "outfit (generated)", "cut layer", "layer on base"]))
W = max(r.width for r in rows); img = Image.new("RGBA", (W, sum(r.height for r in rows)), (30, 30, 38, 255)); y = 0
for r in rows: img.paste(r, (0, y)); y += r.height
img.save(f"{OUT}/outfit_layer.png")

# 2. repair
fr = np.array(Image.open(f"{SRC}/base/east/2.png").convert("RGBA")); dam = fr.copy(); random.seed(3); ys, xs = np.nonzero(fr[..., 3] > 0)
core = [(y, x) for y, x in zip(ys, xs) if (fr[y - 1:y + 2, x - 1:x + 2, 3] > 0).all()]
for k, (y, x) in enumerate(random.sample(core, 14)): dam[y, x, :3] = ((255 - 9 * k) % 256, (40 + 53 * k) % 256, (200 + 31 * k) % 256)      # off-palette colour specks, each a different colour (speck_fix only touches RARE colours)
for y, x in random.sample(core, 8): dam[y, x, 3] = 0                                       # pinholes
os.makedirs(T + "/r", exist_ok=True); Image.fromarray(dam).save(T + "/r/damaged.png"); shutil.copy(T + "/r/damaged.png", T + "/r/fixed.png")
px("speck_fix", T + "/r/damaged.png", T + "/r/step1.png"); px("fill_pinholes", T + "/r/step1.png", "--out", T + "/r/o"); shutil.copy(T + "/r/o/step1.png", T + "/r/fixed.png")
def lint(p):
    j = json.loads(px("pixel_lint", p, "--json")); r = j[0] if isinstance(j, list) else (j.get("results") or list(j.values()))[0]; return r
def flags(p):
    r = lint(p); return ", ".join(f"{k} {v}" for k, v in r.items() if k in ("lone_px", "speck_px", "specks", "pinholes", "holes") and isinstance(v, (int, float)))
cols = [on_bg(Image.open(f"{SRC}/base/east/2.png"), 4), on_bg(Image.open(T + "/r/damaged.png"), 4), on_bg(Image.open(T + "/r/fixed.png"), 4)]
sheet(cols, ["original", "damaged (14 specks, 8 pinholes)", "speck_fix + fill_pinholes"]).save(f"{OUT}/repair.png")

# 3. village: the two styles side by side in one looping GIF
gifs = []
for st in ("dark_fantasy", "bright_cartoon"):
    px("pixdraw", "scene", os.path.join(ROOT, "pixdraw", "examples", "village.json"), "--style", st, "--out", T + "/v_" + st, "--name", "v", "--frames", 8, "--scale", 3)
    gifs.append(Image.open(T + f"/v_{st}/v.gif"))
n = min(g.n_frames for g in gifs); out = []
for k in range(n):
    fs = []
    for g in gifs: g.seek(k); fs.append(g.convert("RGBA"))
    w = sum(f.width for f in fs) + 8; c = Image.new("RGBA", (w, max(f.height for f in fs)), (30, 30, 38, 255)); x = 0
    for f in fs: c.paste(f, (x, 0)); x += f.width + 8
    out.append(c.convert("P", palette=Image.ADAPTIVE, colors=64))
out[0].save(f"{OUT}/village.gif", save_all=True, append_images=out[1:], duration=gifs[0].info.get("duration", 120), loop=0, disposal=2)
shutil.rmtree(T, ignore_errors=True)
