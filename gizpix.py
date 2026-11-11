#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""gizpix - one entry point for the Gizpix pixel-art toolkit (clean, layers, checks, sheets, drawing). Local, free, no network, no AI calls.

  python gizpix.py list                       every tool, grouped, with a one-line purpose
  python gizpix.py find WORD                  tools whose name, purpose or docstring mention WORD
  python gizpix.py help TOOL                  the tool's own documentation (its docstring; nothing is run)
  python gizpix.py run TOOL [args ...]        run a tool (the word `run` is optional: `python gizpix.py pixel_lint a.png`)
  python gizpix.py doctor                     check Python packages, then run every selftest
  python gizpix.py ui [--port N] [--no-open]  open the local web interface (browser, localhost only)
  python gizpix.py path                       print the Gizpix folder

Run it from anywhere; the paths are resolved from this file. Read HANDOUT.md first for what to use when."""
__version__ = "0.2.0"   # keep in step with pyproject.toml and CHANGELOG.md
import ast, os, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
# name: (group, path relative to ROOT or "module:NAME", one-line purpose)
TOOLS = {
    "pixdraw": ("draw", "module:pixdraw", "draw pixel-art buildings from parameters (3 views, 5 styles, animation, sprite sheet) and compose scenes; no reference image, no AI"),
    "pix_layer": ("layers", "layers/pix_layer.py", "cut an outfit layer out of base-vs-outfit sprites or walk frames (new-colour key, skin drop, solid, outline, bits, drop-parts)"),
    "paperdoll": ("layers", "layers/paperdoll.py", "difference-based layer extract + compose + checks (region, drift, palette key)"),
    "pix_snap": ("prep", "prep/pix_snap.py", "turn an upscaled / off-grid pixel-art image back into real pixels"),
    "pixel_lint": ("check", "check/pixel_lint.py", "pixel-art quality numbers: specks, thick lines, stair breaks, blurry alpha, palette (measures only)"),
    "tile_check": ("check", "check/tile_check.py", "does a tile repeat without a visible seam (measures only)"),
    "check_8dir": ("check", "check/check_8dir.py", "QA of an 8-direction sprite set: poses, walk, compass, mirrors (measures only)"),
    "palette_diff": ("check", "check/palette_diff.py", "compare the colours of directions/states/frames with a reference sprite: exact, near, new colours (measures only)"),
    "qa": ("check", "check/qa.py", "automatic checks of generated images before a human looks"),
    "apply_pixel_fixes": ("check", "check/apply_pixel_fixes.py", "apply an explicit, auditable list of single-pixel edits"),
    "speck_fix": ("clean", "clean/speck_fix.py", "repair lone odd-coloured pixels (safer than despeckle)"),
    "clean_frames": ("clean", "clean/clean_frames.py", "frame clean-up: binary alpha, palette key, specks, ground line (removes and moves pixels only)"),
    "palette_lock": ("clean", "clean/palette_lock.py", "snap every pixel to the character's own palette"),
    "fill_pinholes": ("clean", "clean/fill_pinholes.py", "close one-pixel holes inside a sprite"),
    "repair_outline": ("clean", "clean/repair_outline.py", "close breaks in a dark 1 px outline (only on noisy generator output)"),
    "despeckle": ("clean", "clean/despeckle.py", "clear lone pixels from animation frames (only on very noisy output)"),
    "scrub": ("clean", "clean/scrub.py", "clear flashes and streaks painted in by an animation generator"),
    "colormatch": ("clean", "clean/colormatch.py", "fix colour shift of key poses / in-betweens against the standing sprite"),
    "ground_snap": ("clean", "clean/ground_snap.py", "drop floating frames onto the foot line"),
    "painterly_clean": ("clean", "clean/painterly_clean.py", "close holes and white specks in soft-shaded sprites"),
    "apply_palette": ("color", "color/apply_palette.py", "snap pixels to a fixed palette (no dithering)"),
    "hue_shift": ("color", "color/hue_shift.py", "recolour by turning the hue (optionally one hue range, saturation/value scale); same colour -> same result in every frame"),
    "recolor_groups": ("color", "color/recolor_groups.py", "colour variants by colour group (skin, neutrals, hue families)"),
    "make_sheet": ("sheets", "sheets/make_sheet.py", "pack frames into a sprite sheet + JSON (Aseprite/TexturePacker style)"),
    "contact_sheet": ("sheets", "sheets/contact_sheet.py", "contact sheet of many images for review"),
    "preview_gif": ("sheets", "sheets/preview_gif.py", "shareable preview GIF from frames"),
    "align_frames": ("sheets", "sheets/align_frames.py", "move frames by whole pixels so the feet line (and optionally the body column) is the same in every frame; prints the shifts"),
    "trim_frames": ("sheets", "sheets/trim_frames.py", "crop frames to their shared content box (same size, same anchor); prints the box"),
    "pad_sprite": ("sheets", "sheets/pad_sprite.py", "paste a sprite onto a larger transparent canvas"),
    "xform": ("rig", "rig/xform.py", "2D affine part transforms for code rigs (library; has a selftest)"),
    "rig_walk": ("rig", "rig/rig_walk.py", "first rig test: walk a standing sprite by shifting row/column bands (superseded by rig_walk2)"),
    "rig_walk2": ("rig", "rig/rig_walk2.py", "walk a standing sprite and its layers with a part tree"),
    "warp_layer": ("rig", "rig/warp_layer.py", "move a standing layer onto moving base frames by optical flow"),
}


def doc_of(rel):
    """the module docstring of a tool, read without running it"""
    p = os.path.join(ROOT, rel)
    try: return ast.get_docstring(ast.parse(open(p, encoding="utf-8", errors="replace").read())) or "(no docstring)"
    except (OSError, SyntaxError) as e: return f"(cannot read {rel}: {e})"


def command(name, args):
    group, rel, _ = TOOLS[name]
    if rel.startswith("module:"): return [sys.executable, "-m", rel[7:], *args], ROOT
    return [sys.executable, os.path.join(ROOT, rel), *args], ROOT


def cmd_list():
    last = None
    for name, (group, rel, purpose) in sorted(TOOLS.items(), key=lambda kv: (kv[1][0], kv[0])):
        if group != last: print(f"\n[{group}]"); last = group
        print(f"  {name:18s} {purpose}")
    print("\nMore: python gizpix.py help TOOL   |   python gizpix.py find WORD   |   HANDOUT.md")


def cmd_find(word):
    w = word.lower(); hit = False
    for name, (group, rel, purpose) in sorted(TOOLS.items()):
        d = doc_of(rel[7:] + "/__init__.py" if rel.startswith("module:") else rel)
        if w in name.lower() or w in purpose.lower() or w in d.lower(): print(f"  {name:18s} [{group}] {purpose}"); hit = True
    if not hit: print(f"nothing mentions {word!r}; python gizpix.py list shows everything")


def cmd_help(name):
    group, rel, purpose = TOOLS[name]
    print(f"{name} [{group}] - {purpose}\nrun: python {os.path.join(ROOT, 'gizpix.py')} {name} ...\n")
    if rel.startswith("module:"):
        print(doc_of(rel[7:] + "/__init__.py")); print("\nSubcommands: python -m pixdraw -h  (build, gallery, scene, styles, materials, presets, extract-style, selftest, golden); full guide: pixdraw/README.md")
    else: print(doc_of(rel))


def cmd_doctor():
    bad = 0
    print("Python", sys.version.split()[0], "-", sys.executable)
    for mod, need in (("numpy", True), ("PIL", True), ("scipy", True), ("cv2", False)):
        try: __import__(mod); print(f"  ok   {mod}")
        except Exception as e:
            print(f"  {'FAIL' if need else 'note'} {mod}: {e}" + ("" if need else "  (optional: only warp_layer uses it)")); bad += need
    if bad: print("install the missing packages (pip install numpy pillow scipy) and run again"); return 1
    return subprocess.run([sys.executable, os.path.join(ROOT, "selftest_all.py")], cwd=ROOT).returncode


def main(argv):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0
    if argv[0] in ("--version", "version"): print("gizpix", __version__); return 0
    c, rest = argv[0], argv[1:]
    if c == "list": cmd_list(); return 0
    if c == "path": print(ROOT); return 0
    if c == "doctor": return cmd_doctor()
    if c == "ui": return subprocess.run([sys.executable, os.path.join(ROOT, "ui", "server.py"), *rest], cwd=os.getcwd()).returncode
    if c == "find":
        if not rest: print("usage: gizpix.py find WORD"); return 2
        cmd_find(" ".join(rest)); return 0
    if c == "help":
        if not rest or rest[0] not in TOOLS: print("usage: gizpix.py help TOOL   (python gizpix.py list shows the names)"); return 2
        cmd_help(rest[0]); return 0
    if c == "run": c, rest = (rest[0] if rest else ""), rest[1:]
    if c not in TOOLS:
        import difflib
        close = list(dict.fromkeys([n for n in TOOLS if c and (c in n or n in c)] + difflib.get_close_matches(c, list(TOOLS), 3, 0.5) + difflib.get_close_matches(c.replace("-", "_"), list(TOOLS), 3, 0.5)))
        print(f"gizpix: unknown tool {c!r}" + (f"; did you mean {', '.join(close)}?" if close else "; python gizpix.py list shows the tools")); return 2
    cmd, _ = command(c, rest)
    return _run_pixdraw(cmd) if TOOLS[c][1].startswith("module:") else subprocess.run(cmd).returncode      # scripts run where the caller is, so relative paths mean what the caller thinks


def _run_pixdraw(cmd):
    """pixdraw is a package: it must be importable (Gizpix folder on the path) while the user's own relative paths still resolve from where they are"""
    env = dict(os.environ); env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(cmd, env=env).returncode


def cli(): sys.exit(main(sys.argv[1:]))   # the `gizpix` command made by pip install


if __name__ == "__main__": cli()
