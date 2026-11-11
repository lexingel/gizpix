# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixdraw command line:  python -m pixdraw <command> -h   (run from the folder that contains the pixdraw/ directory)"""
import argparse, json, os, sys
from PIL import Image
from . import render, compose, list_styles, extract_style, PRESETS, MATERIALS
from .export import export


def parse_spec(s):
    """SPEC = a .json file, a JSON string, or  type=inn,proj=iso,floors=3"""
    if os.path.exists(s):
        with open(s, encoding="utf-8") as f: return json.load(f)
    if s.strip().startswith("{"): return json.loads(s)
    d = {}
    for kv in s.split(","):
        k, _, v = kv.partition("="); v = v.strip()
        d[k.strip()] = True if v == "true" else False if v == "false" else (int(v) if v.lstrip("-").isdigit() else (float(v) if v.replace(".", "", 1).lstrip("-").isdigit() else v))
    return d


def gallery(out, style="dark_fantasy", scale=3):
    rows = [[render({"type": t, "proj": proj}, style)[0] for t in PRESETS] for proj in ("iso", "top", "side")]
    W = max(sum(i.width for i in r) + 12 * (len(r) + 1) for r in rows); H = sum(max(i.height for i in r) + 14 for r in rows) + 10
    sh = Image.new("RGB", (W, H), (58, 58, 66)); y = 10
    for r in rows:
        x = 12; h = max(j.height for j in r)
        for i in r: sh.paste(i, (x, y + h - i.height), i); x += i.width + 12
        y += h + 14
    sh.resize((sh.width * scale, sh.height * scale), Image.NEAREST).save(out)


def main(argv):
    ap = argparse.ArgumentParser(prog="pixdraw", description="reference-free pixel-art building drawer")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build", help="render one building"); b.add_argument("spec", help="SPEC = a .json file, a JSON string or  type=inn,proj=iso,floors=3")
    b.add_argument("--style", default="dark_fantasy", help="bundled style name or path to a style .json"); b.add_argument("--out", default="out"); b.add_argument("--name")
    b.add_argument("--frames", type=int, default=1, help="animation frames (loops)"); b.add_argument("--scale", type=int, default=1, help="nearest-neighbour enlargement of PNG, GIF and sheet")
    b.add_argument("--ms", type=int, default=120, help="frame time of the GIF / sheet")
    g = sub.add_parser("gallery", help="every preset x projection in one picture"); g.add_argument("out"); g.add_argument("--style", default="dark_fantasy"); g.add_argument("--scale", type=int, default=3)
    sc = sub.add_parser("scene", help="several buildings, trees, fences, paths in one picture"); sc.add_argument("file", help="JSON: a list of items, or {\"size\": [w, h], \"items\": [...]}  (see pixdraw/examples/village.json)")
    sc.add_argument("--style", default="dark_fantasy"); sc.add_argument("--out", default="out"); sc.add_argument("--name"); sc.add_argument("--frames", type=int, default=1); sc.add_argument("--scale", type=int, default=1); sc.add_argument("--ms", type=int, default=120)
    sub.add_parser("styles", help="list bundled styles"); sub.add_parser("materials", help="list materials"); sub.add_parser("presets", help="list building presets")
    e = sub.add_parser("extract-style", help="a starting-point style from YOUR sprites"); e.add_argument("sprites", nargs="+"); e.add_argument("--out", default="style.json"); e.add_argument("--name", default="extracted")
    sub.add_parser("selftest", help="run the package self-test")
    gd = sub.add_parser("golden", help="check (or --update) the hashes of a fixed set of renders"); gd.add_argument("--update", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd is None: ap.print_help(); return 0
    try:
        if a.cmd == "styles": print("\n".join(list_styles()))
        elif a.cmd == "materials": print("\n".join(MATERIALS))
        elif a.cmd == "presets": print("\n".join(PRESETS))
        elif a.cmd == "build":
            spec = parse_spec(a.spec); name = a.name or f"{spec.get('type', 'building')}_{spec.get('proj', 'iso')}"
            print("\n".join(export(render(spec, a.style, frames=a.frames), a.out, name, ms=a.ms, scale=a.scale)))
        elif a.cmd == "scene":
            if not os.path.isfile(a.file): print(f"pixdraw: no such scene file: {a.file}", file=sys.stderr); return 2
            try: d = json.load(open(a.file, encoding="utf-8"))
            except ValueError as e: print(f"pixdraw: {a.file} is not valid JSON: {e}", file=sys.stderr); return 2
            items, size = (d, (180, 120)) if isinstance(d, list) else (d["items"], tuple(d.get("size", (180, 120))))
            print("\n".join(export(compose(items, a.style, size, a.frames), a.out, a.name or os.path.splitext(os.path.basename(a.file))[0], ms=a.ms, scale=a.scale)))
        elif a.cmd == "gallery": gallery(a.out, a.style, a.scale); print(a.out)
        elif a.cmd == "extract-style": extract_style(a.sprites, a.out, a.name); print(a.out)
        elif a.cmd == "golden":
            from . import golden
            if a.update: print(golden.update()); return 0
            ok, msg = golden.check(); print(msg); return 0 if ok else 1
        elif a.cmd == "selftest":
            from .selftest import run
            return run()
    except (ValueError, KeyError) as e:
        print("pixdraw: " + (str(e.args[0]) if isinstance(e, KeyError) and e.args else str(e)), file=sys.stderr); return 2
    return 0
