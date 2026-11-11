# SPDX-License-Identifier: AGPL-3.0-or-later
"""tools_real_test.py - the tools that only had -h/selftest, run on REAL frames (skeleton-v3 robe/base walk, 96 px) with injected defects and sanity checks on the output.
Each line states what was injected and what was measured; exit 1 if a check fails. Works in a temp folder, never touches the frames. python tools_real_test.py"""
import glob, json, os, random, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FR = os.path.join(ROOT, "samples", "walk_frames")
T = tempfile.mkdtemp(prefix="realtools_"); fails = 0
def sh(*args):
    return subprocess.run([sys.executable, os.path.join(ROOT, "gizpix.py"), *map(str, args)], capture_output=True, text=True, cwd=T)
def A(p): return np.array(Image.open(p).convert("RGBA"))
def report(name, ok, note):
    global fails; fails += not ok; print(("ok   " if ok else "FAIL ") + f"{name}: {note}")
def fresh(sub):
    d = os.path.join(T, sub); os.makedirs(d, exist_ok=True); return d
raw = fresh("raw")
for p in glob.glob(os.path.join(FR, "robe", "east", "*.png")): shutil.copy(p, raw)

# scrub: a 14 px white streak painted into frame 3
a = A(raw + "/3.png"); clean3 = a.copy(); streak = [(30 + i // 7, 70 + i) for i in range(14)]
for y, x in streak: a[y, x] = (255, 255, 255, 255)
Image.fromarray(a).save(raw + "/3.png"); r = sh("scrub", raw, "3"); b = A(raw + "/3_s.png")
gone = sum(b[y, x, 3] == 0 for y, x in streak); other = int(((b[..., 3] != clean3[..., 3]) | (b[..., :3] != clean3[..., :3]).any(-1)).sum()) - (14 - gone)
report("scrub", r.returncode == 0 and gone >= 12 and other <= 30, f"white streak of 14 px: {gone} cleared; {max(other, 0)} natural pixels of {int((clean3[..., 3] > 0).sum())} changed too (colours that the first and last frame do not have)")

# despeckle: 6 magenta specks on opaque pixels of frame 4
a = A(raw + "/4.png"); orig4 = a.copy(); ys, xs = np.nonzero(a[..., 3] > 0); random.seed(1); inj = []
for k in range(6):
    j = random.randrange(len(xs)); y, x = int(ys[j]), int(xs[j]); a[y, x] = (255, 0, 255, 255); inj.append((y, x))
Image.fromarray(a).save(raw + "/4.png"); r = sh("despeckle", raw + "/4.png", "--out", T + "/desp"); d = A(T + "/desp/4.png")
fixed = sum(tuple(d[y, x, :3]) != (255, 0, 255) or d[y, x, 3] == 0 for y, x in inj); changed = int(((d != a).any(-1)).sum()) - fixed
report("despeckle", r.returncode == 0 and fixed >= 5 and changed <= 25, f"6 injected specks: {fixed} fixed; {changed} natural pixels changed too (the cost: lone real pixels such as glints)")

# repair_outline: recolour 5 outline-edge pixels (dark, on the silhouette edge, >= 2 dark neighbours) to a skin colour
a = A(raw + "/2.png"); op = a[..., 3] > 0; dark = a[..., :3].astype(int).sum(-1) < 150; picks = []
for y in range(1, 95):
    for x in range(1, 95):
        if op[y, x] and dark[y, x] and not (op[y - 1, x] and op[y + 1, x] and op[y, x - 1] and op[y, x + 1]) and dark[y - 1:y + 2, x - 1:x + 2].sum() >= 4 and all(abs(y - py) + abs(x - px) > 8 for py, px in picks): picks.append((y, x))
picks = picks[:5]; broken = a.copy()
for y, x in picks: broken[y, x, :3] = (200, 150, 100)
os.makedirs(T + "/ro_in", exist_ok=True); Image.fromarray(broken).save(T + "/ro_in/0.png"); r = sh("repair_outline", "fix", T + "/ro_in", T + "/ro_out"); f = A(T + "/ro_out/0.png")
back = sum(f[y, x, :3].astype(int).sum() < 150 for y, x in picks)
report("repair_outline", r.returncode == 0 and (f[..., 3] == broken[..., 3]).all() and back >= 3, f"{len(picks)} outline pixels broken: {back} repaired, silhouette unchanged")

# apply_palette: the base's own colours as a .hex file, applied to the robe frame
base0 = A(FR + "/base/east/0.png"); cols = sorted({"#%02x%02x%02x" % tuple(p[:3]) for p in base0[base0[..., 3] > 0]}); open(T + "/pal.hex", "w").write("\n".join(cols))
r = sh("apply_palette", T + "/pal.hex", raw + "/2.png", "--out", T + "/ap"); o = A(T + "/ap/2.png"); allowed = {tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in cols}
report("apply_palette", r.returncode == 0 and {tuple(p[:3]) for p in o[o[..., 3] > 0]} <= allowed and (o[..., 3] == A(raw + "/2.png")[..., 3]).all(), f"{len(cols)} palette colours; output stays inside them, alpha unchanged")
r = sh("apply_palette", T + "/no_such.hex", raw + "/2.png", "--out", T + "/ap2")
report("apply_palette missing palette file", r.returncode == 2 and "Traceback" not in r.stderr, "a path-like palette that does not exist gives a clear error, exit 2")

# recolor_groups: blue -> crimson on the tunic, outline and skin untouched
src = FR + "/base/east/0.png"; r = sh("recolor_groups", src, "--swap", "blue=crimson", "--out", T + "/rg"); s0, s1 = A(src), A(T + "/rg/0.png")
ch = (s0[..., :3] != s1[..., :3]).any(-1) & (s0[..., 3] > 0); dk = (s0[..., :3].astype(int).sum(-1) < 60)
report("recolor_groups", r.returncode == 0 and 100 < ch.sum() < 900 and not (ch & dk).any() and (s0[..., 3] == s1[..., 3]).all(), f"blue -> crimson: {int(ch.sum())} pixels recoloured, no outline pixel touched, alpha unchanged")

# painterly_clean: a 1 px hole punched into the robe
a = A(raw + "/2.png"); op = a[..., 3] > 0; core = [(y, x) for y in range(2, 94) for x in range(2, 94) if op[y - 2:y + 3, x - 2:x + 3].all()]
y, x = core[len(core) // 2]; a[y, x, 3] = 0; os.makedirs(T + "/pc_in", exist_ok=True); Image.fromarray(a).save(T + "/pc_in/2.png"); r = sh("painterly_clean", T + "/pc_in/2.png", "--out", T + "/pc"); q = A(T + "/pc/2.png")
report("painterly_clean", r.returncode == 0 and q[y, x, 3] == 255, "a 1 px hole inside the body is closed")

# pad_sprite
r = sh("pad_sprite", FR + "/base/east/0.png", T + "/padded.png", 128, 128, 16); pad = Image.open(T + "/padded.png"); off = [int(v) for v in r.stdout.split()[-2:]]
report("pad_sprite", r.returncode == 0 and pad.size == (128, 128) and len(off) == 2, f"canvas {pad.size}, reported offset {off[0]},{off[1]}")

# apply_pixel_fixes: delete, set, fill on a copy
root = fresh("fx/east"); shutil.copy(raw + "/2.png", root + "/2.png"); a = A(root + "/2.png"); ys, xs = np.nonzero(a[..., 3] > 0); y, x = int(ys[10]), int(xs[10])
json.dump([{"dir": "east", "frame": 2, "op": "delete", "x": x, "y": y, "why": "test"}], open(T + "/fixes.json", "w")); r = sh("apply_pixel_fixes", T + "/fixes.json", T + "/fx")
report("apply_pixel_fixes", r.returncode == 0 and A(root + "/2.png")[y, x, 3] == 0, f"delete at {x},{y} applied")

# tile_check: a seamless and a seamed synthetic tile
rng = np.random.RandomState(0); t1 = np.zeros((16, 16, 4), np.uint8); t1[..., 3] = 255; t1[..., :3] = 120
t2 = t1.copy(); t2[:, 8:, :3] = 200; Image.fromarray(t1).save(T + "/flat.png"); Image.fromarray(t2).save(T + "/halves.png")
r = sh("tile_check", T + "/flat.png", T + "/halves.png"); lines = r.stdout.strip().splitlines()
report("tile_check", r.returncode == 0 and len(lines) == 2 and lines[0] != lines[1], "a flat tile and a two-halves tile give different numbers")

# rig_walk2 and warp_layer: the robe layer of the standing south frame
stand_b, stand_o = FR + "/base/south/0.png", FR + "/robe/south/0.png"; os.makedirs(T + "/L/b", exist_ok=True); os.makedirs(T + "/L/o", exist_ok=True)
shutil.copy(stand_b, T + "/L/b/south.png"); shutil.copy(stand_o, T + "/L/o/south.png"); sh("pix_layer", "cut", T + "/L/b", T + "/L/o", T + "/L/out", "--name", "robe", "--solid", "--drop-skin", "auto"); layer = T + "/L/out/robe/south.png"
r = sh("rig_walk2", stand_b, T + "/rw", layer); n = len(glob.glob(T + "/rw/*.png"))
report("rig_walk2", r.returncode == 0 and n >= 4, f"{n} files written for the standing base + robe layer")
try: import cv2
except ImportError: cv2 = None
if cv2 is None: print("skip warp_layer: opencv-python is not installed (optional, only warp_layer needs it)")
else:
    r = sh("warp_layer", stand_b, layer, FR + "/base/south", T + "/wl", "--truth", FR + "/robe/south"); n = len(glob.glob(T + "/wl/*.png"))
    report("warp_layer", r.returncode == 0 and n >= 8, f"{n} files; last line: {(r.stdout.strip().splitlines() or [''])[-1][:110]}")

# align_frames: the feet row of every east base frame ends up the same; palette_diff and hue_shift on the same frames
frs = sorted(glob.glob(FR + "/base/east/*.png"), key=lambda q: int(os.path.basename(q)[:-4])); r = sh("align_frames", *frs, "--out", T + "/al", "--y", "feet")
rows = {int(np.nonzero(A(q)[..., 3])[0].max()) for q in glob.glob(T + "/al/*.png")}
report("align_frames", r.returncode == 0 and len(rows) == 1 and len(glob.glob(T + "/al/*.png")) == 8, f"8 walk frames: feet row {rows} in every frame (the walk's own 1-2 px bob is removed)")
r = sh("palette_diff", FR + "/base/east/0.png", FR + "/base/east/3.png", FR + "/robe/east/0.png", "--json"); js = json.loads(r.stdout)["others"]
report("palette_diff", r.returncode == 0 and js[FR + "/base/east/3.png"]["exact_pct"] == 100.0 and js[FR + "/robe/east/0.png"]["new_pct"] > 30, f"another base frame {js[FR + '/base/east/3.png']['exact_pct']}% exact; the robe frame {js[FR + '/robe/east/0.png']['new_pct']}% new colours")
r = sh("hue_shift", FR + "/base/east/0.png", "--out", T + "/hs0", "--hue", 120, "--range", "0.55,0.72"); r2 = sh("hue_shift", FR + "/base/east/1.png", "--out", T + "/hs1", "--hue", 120, "--range", "0.55,0.72")
m = {}; ok = True
for n in (0, 1):
    src, dst = A(FR + f"/base/east/{n}.png"), A(T + f"/hs{n}/{n}.png")
    for (y, x) in zip(*np.nonzero(src[..., 3] > 0)):
        k = tuple(src[y, x, :3]); v = tuple(dst[y, x, :3]); ok &= m.setdefault(k, v) == v
chg = int(((A(FR + "/base/east/0.png")[..., :3] != A(T + "/hs0/0.png")[..., :3]).any(-1)).sum())
report("hue_shift", r.returncode == 0 and r2.returncode == 0 and ok and chg > 100, f"blue tunic turned 120 degrees: {chg} pixels; the same colour maps to the same result across two frames")

shutil.rmtree(T, ignore_errors=True); print("real-frame tools " + ("FAILED" if fails else "ok")); sys.exit(1 if fails else 0)
