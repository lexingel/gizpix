# SPDX-License-Identifier: AGPL-3.0-or-later
"""chain_test.py - run the documented animation clean-up chain end to end on real frames (skeleton-v3 robe walk, east, 8 frames) and check each step's exit code and output.
Steps: speck_fix -> fill_pinholes --out -> colormatch -> ground_snap --check -> clean_frames -> palette_lock -> qa --anim -> make_sheet -> preview_gif --faithful.
Writes into a temp folder, prints one line per step, exits 1 if any step fails. python chain_test.py"""
import glob, json, os, shutil, subprocess, sys, tempfile
from PIL import Image
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = sorted(glob.glob(os.path.join(ROOT, "samples", "walk_frames", "robe", "east", "*.png")))
T = tempfile.mkdtemp(prefix="chain_"); fails = 0
def run(name, *args, expect=0, check=None):
    global fails
    r = subprocess.run([sys.executable, os.path.join(ROOT, "gizpix.py"), *map(str, args)], capture_output=True, text=True, cwd=T)
    ok = r.returncode == expect and (check() if check else True); fails += not ok
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  exit {r.returncode}: {(r.stderr or r.stdout).strip()[-200:]}")); return r
def frames(d): return sorted(glob.glob(os.path.join(T, d, "*.png")), key=lambda p: int(os.path.basename(p)[:-4]) if os.path.basename(p)[:-4].isdigit() else 0)
assert len(SRC) == 8, SRC
os.makedirs(T + "/raw"); [shutil.copy(p, T + "/raw/" + os.path.basename(p)) for p in SRC]
os.makedirs(T + "/sf")
for p in frames("raw"): run("speck_fix " + os.path.basename(p), "speck_fix", p, T + "/sf/" + os.path.basename(p))
run("fill_pinholes --out", "fill_pinholes", T + "/sf", "--out", T + "/fp", check=lambda: len(frames("fp")) == 8)
run("fill_pinholes on a typo exits 2", "fill_pinholes", T + "/nope", expect=2)
run("colormatch", "colormatch", T + "/raw/0.png", *frames("fp"), "--out", T + "/cm", check=lambda: len(glob.glob(T + "/cm/*.png")) == 8)
run("ground_snap --check", "ground_snap", T + "/raw/0.png", "0,0", *frames("fp"), "--check")
run("clean_frames", "clean_frames", "clean", T + "/fp", T + "/cf", "--ref", T + "/raw/0.png", "--snap", check=lambda: len(frames("cf")) == 8 and os.path.exists(T + "/cf/clean_report.json"))
run("palette_lock", "palette_lock", "lock", T + "/cf", T + "/pl", "--ref", T + "/raw/0.png", T + "/raw/4.png", check=lambda: len(frames("pl")) == 8)
run("qa --anim", "qa", *frames("pl"), "--anim")
run("make_sheet", "make_sheet", T + "/walk", *frames("pl"), "--fps", 12, check=lambda: len(json.load(open(T + "/walk.json"))["frames"]) == 8)
run("preview_gif --faithful", "preview_gif", T + "/walk.gif", "-", *frames("pl"), "--faithful", "--fps", 12, check=lambda: Image.open(T + "/walk.gif").n_frames == 8)
sizes = {Image.open(p).size for p in frames("pl")}; print("frame sizes after the chain:", sizes); fails += len(sizes) != 1
shutil.rmtree(T, ignore_errors=True); print("chain " + ("FAILED" if fails else "ok")); sys.exit(1 if fails else 0)
