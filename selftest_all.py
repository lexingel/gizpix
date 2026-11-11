# SPDX-License-Identifier: AGPL-3.0-or-later
"""Runs every Gizpix selftest and prints ok/FAIL per tool. python selftest_all.py"""
import subprocess, sys, os
H = os.path.dirname(os.path.abspath(__file__))
TOOLS = ["layers/pix_layer.py", "prep/pix_snap.py", "layers/paperdoll.py", "clean/clean_frames.py", "clean/palette_lock.py",
         "clean/repair_outline.py", "clean/fill_pinholes.py", "check/check_8dir.py", "check/apply_pixel_fixes.py", "rig/xform.py", "check/pixel_lint.py", "check/tile_check.py", "clean/speck_fix.py", "sheets/trim_frames.py", "sheets/align_frames.py", "check/palette_diff.py", "color/hue_shift.py"]
bad = 0
for t in TOOLS:
    r = subprocess.run([sys.executable, os.path.join(H, t), "selftest"], capture_output=True, text=True)
    ok = r.returncode == 0 and "ok" in r.stdout
    bad += not ok; print(("ok   " if ok else "FAIL ") + t)
r = subprocess.run([sys.executable, os.path.join(H, "experiments", "anim_chain", "chain_test.py")], capture_output=True, text=True)
ok = r.returncode == 0 and "chain ok" in r.stdout
bad += not ok; print(("ok   " if ok else "FAIL ") + "animation chain end to end (experiments/anim_chain/chain_test.py)")
r = subprocess.run([sys.executable, os.path.join(H, "experiments", "anim_chain", "tools_real_test.py")], capture_output=True, text=True)
ok = r.returncode == 0 and "real-frame tools ok" in r.stdout
bad += not ok; print(("ok   " if ok else "FAIL ") + "tools on real frames with injected defects (experiments/anim_chain/tools_real_test.py)" + ("" if ok else ": " + r.stdout[-300:]))
r = subprocess.run([sys.executable, "-m", "pixdraw", "selftest"], capture_output=True, text=True, cwd=H)         # package, run as a module
ok = r.returncode == 0 and "ok" in r.stdout
bad += not ok; print(("ok   " if ok else "FAIL ") + "pixdraw (python -m pixdraw selftest)")
r = subprocess.run([sys.executable, os.path.join(H, "ui", "server.py"), "selftest"], capture_output=True, text=True)                  # the local web interface: token, host check, staging then Save, image routes
ok = r.returncode == 0 and "ui selftest ok" in r.stdout
bad += not ok; print(("ok   " if ok else "FAIL ") + "web interface (python ui/server.py selftest)" + ("" if ok else ": " + (r.stderr or r.stdout)[-200:]))
import importlib.util                                                       # the gizpix.py registry: every path exists, every docstring reads, the commands run
spec = importlib.util.spec_from_file_location("gizpix", os.path.join(H, "gizpix.py")); pt = importlib.util.module_from_spec(spec); spec.loader.exec_module(pt)
miss = [n for n, (g, rel, _) in pt.TOOLS.items() if not os.path.exists(os.path.join(H, rel[7:] + "/__init__.py" if rel.startswith("module:") else rel))]
untracked = [os.path.relpath(os.path.join(r, f), H).replace(os.sep, "/") for r, d, fs in os.walk(H) for f in fs if f.endswith(".py") and r.split(os.sep)[-1] in ("layers", "prep", "check", "clean", "color", "sheets", "rig")
             and os.path.relpath(os.path.join(r, f), H).replace(os.sep, "/") not in [v[1] for v in pt.TOOLS.values()] and f != "labelled_grid_example.py"]
r = subprocess.run([sys.executable, os.path.join(H, "gizpix.py"), "list"], capture_output=True, text=True); r2 = subprocess.run([sys.executable, os.path.join(H, "gizpix.py"), "help", "pix_layer"], capture_output=True, text=True)
okp = not miss and not untracked and r.returncode == 0 and "pix_layer" in r.stdout and r2.returncode == 0 and "cut" in r2.stdout
from concurrent.futures import ThreadPoolExecutor
def _h(item):
    n, (g, rel, _) = item
    if rel.startswith("module:"): return n, True
    q = subprocess.run([sys.executable, os.path.join(H, rel), "-h"], capture_output=True, text=True); return n, q.returncode == 0 and bool(q.stdout.strip())
with ThreadPoolExecutor(6) as ex: nohelp = [n for n, ok in ex.map(_h, pt.TOOLS.items()) if not ok]          # every tool: -h prints its documentation on stdout and exits 0
okp = okp and not nohelp
bad += not okp; print(("ok   " if okp else "FAIL ") + "gizpix.py registry"+ (f" -h fails: {nohelp}" if nohelp else "") + (f" missing: {miss}" if miss else "") + (f" not registered: {untracked}" if untracked else ""))
names = []                                                                # tool code carries no generator name (the README says which generators the sample frames came from)
for root, dirs, files in os.walk(H):
    dirs[:] = [d for d in dirs if d not in ("experiments", ".git", "assets_dl", "__pycache__", "draw", "page_build")]
    for f in files:
        if f.endswith((".py", ".json")) and f not in ("selftest_all.py", "selftest.py"):
            if any(w in open(os.path.join(root, f), encoding="utf-8", errors="ignore").read().lower() for w in ("pixellab", "vfx_workbench", "animate_image", "/pga-")): names.append(os.path.relpath(os.path.join(root, f), H))
bad += bool(names); print(("ok   " if not names else "FAIL ") + "no generator name in tool code" + (": " + ", ".join(names) if names else ""))
sys.exit(bad)
