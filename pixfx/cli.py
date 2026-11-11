# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixfx - draw pixel-art effects (fire, explosions, hits, lightning, magic, pickups, weather) from code. No reference image, no AI, no network.

  python gizpix.py pixfx list [WORD]                       the effects, with a one-line description
  python gizpix.py pixfx show ID                           options, size, duration of one effect
  python gizpix.py pixfx render ID [-o key=value ...] [--frames N] [--fps N] [--scale S] [--out DIR] [--name N] [--bg #rrggbb|none] [--no-gif] [--no-sheet] [--no-contact]
  python gizpix.py pixfx check [ID ...]                    quality checks (deterministic, loops close, one-shots end empty, nothing cropped)
  python gizpix.py pixfx gallery out.png [--scale S]       one picture with a mid-animation frame of every effect
Options (-o): palette=ice (a ramp name, or hex colours dark to bright: '#102,#215,#43a'), seed=7, light=0.6, flip=true, plus the effect's own (see `show`)."""
import argparse, json, os, sys
from . import engine
from .ramps import RAMPS
from .export import write_all, contact_sheet, DARK


def _val(s):
    try: return json.loads(s)
    except ValueError: return s


def _opts(items):
    d = {}
    for it in items or []:
        if "=" not in it: raise SystemExit(f"pixfx: option '{it}' must be key=value")
        k, v = it.split("=", 1); d[k.strip()] = _val(v.strip())
    return d


def _bg(s):
    if s is None: return DARK
    if s.lower() in ("none", "transparent"): return None
    from .core import hex2rgb
    return hex2rgb(s if len(s.lstrip("#")) == 6 else "".join(c * 2 for c in s.lstrip("#")))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == "selftest":
            from .selftest import run; return run()
        if cmd == "list":
            w = rest[0].lower() if rest else ""; cat = None
            for eid, (m, meta) in sorted(engine.registry().items()):
                if w and w not in (eid + " " + meta["name"] + " " + meta.get("about", "") + " " + " ".join(meta.get("tags", []))).lower(): continue
                if eid.split("/")[0] != cat: cat = eid.split("/")[0]; print(f"\n[{cat}]")
                print(f"  {eid:26s} {'loop' if meta['loop'] else 'once'} {meta['duration']:>4}s {meta['size'][0]}x{meta['size'][1]:<4} {meta['about']}")
            print("\nPalettes: " + ", ".join(sorted(RAMPS))); return 0
        if cmd == "show":
            m, meta = engine.get(rest[0]); print(f"{meta['id']}  {meta['name']}  ({'loop' if meta['loop'] else 'one-shot'}, {meta['duration']} s, {meta['size'][0]}x{meta['size'][1]} px, {meta.get('fps', 12)} fps)\n{meta['about']}")
            print("options:", json.dumps({**engine.COMMON, **meta.get("options", {})})); return 0
        if cmd == "check":
            ids = rest or sorted(engine.registry()); bad = 0
            for eid in ids:
                p = engine.check(eid); bad += bool(p); print(("ok   " if not p else "FAIL ") + eid + ("" if not p else ": " + "; ".join(p)))
            return 1 if bad else 0
        if cmd == "gallery":
            ap = argparse.ArgumentParser(prog="pixfx gallery"); ap.add_argument("out"); ap.add_argument("--scale", type=int, default=2); a = ap.parse_args(rest)
            frames = []
            for eid in sorted(engine.registry()):
                fr = engine.render(eid, bg=DARK); frames.append(fr[len(fr) // 3])
            from PIL import Image
            W = max(f.width for f in frames); H = max(f.height for f in frames); frames = [f if f.size == (W, H) else _centre(f, W, H) for f in frames]
            contact_sheet(frames, a.out, scale=a.scale); print(a.out); return 0
        if cmd == "render":
            ap = argparse.ArgumentParser(prog="pixfx render"); ap.add_argument("id"); ap.add_argument("-o", "--opt", action="append"); ap.add_argument("--frames", type=int); ap.add_argument("--fps", type=int)
            ap.add_argument("--scale", type=int, default=4); ap.add_argument("--out", default="pixfx_out"); ap.add_argument("--name"); ap.add_argument("--bg"); ap.add_argument("--no-gif", action="store_true")
            ap.add_argument("--no-sheet", action="store_true"); ap.add_argument("--no-contact", action="store_true"); a = ap.parse_args(rest)
            m, meta = engine.get(a.id); given = _opts(a.opt); o = engine.options(meta, given); fps = a.fps or meta.get("fps", 12)
            frames = engine.render(a.id, given, frames=a.frames, fps=fps)
            name = a.name or meta["id"].split("/")[-1]
            for p in write_all(frames, a.out, name, meta, dict(o), fps, scale=a.scale, gif=not a.no_gif, sheet=not a.no_sheet, contact=not a.no_contact, bg=_bg(a.bg)): print(p)
            return 0
    except (KeyError, ValueError) as e:
        print(f"pixfx: {e.args[0] if e.args else e}", file=sys.stderr); return 2
    print(f"pixfx: unknown command '{cmd}'. Commands: list, show, render, check, gallery, selftest", file=sys.stderr); return 2


def _centre(f, W, H):
    from PIL import Image
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); c.alpha_composite(f, ((W - f.width) // 2, (H - f.height) // 2)); return c
