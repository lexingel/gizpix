# SPDX-License-Identifier: AGPL-3.0-or-later
"""pix_village.py - a complete village set drawn from code (pixdraw buildings + pixart props, trees, people, animals) and a village parallax stack. No reference images, no AI.
  python pix_village.py kit   OUT_DIR            192 PNG files (63 sprites; people have 2 idle, 8 walk-right and 8 walk-left frames, hen, dog and windmill have frames), transparent, 1x, bottom = ground line, in buildings/ props/ nature/ people/ animals/, plus sheet.png and CATALOG.md
  python pix_village.py stack OUT_DIR [SEED]     a village parallax stack with six walking villagers on the road (stack.json + layers: sky, sun, clouds, mountains, far village, orchard, street, foreground); a 2880-frame (48 s) loop at a walking camera
                                                 (120 px/s). Check it with `pix_parallax check OUT_DIR/stack.json`, preview it with `pix_parallax preview`.
  python pix_village.py selftest
Side view, bright_cartoon style. Buildings come from pixdraw specs (uniq.py holds the one-offs: church, barn, smithy, bakery, town hall); props.py and props2.py hold the pixart props.
Limits: one style (red roofs in the kit; the stack recolours roofs), people walk in both directions (separate left frames), no bridge, water or road tiles, the church is a tower plus a nave pasted together (a few pixels draw the cross)."""
import sys, os, subprocess, tempfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path[:0] = [ROOT, HERE]


def _items():
    from pixdraw import render
    import props, props2, uniq
    items = {}

    def add(cat, name, frames):
        frames = frames if isinstance(frames, list) else [frames]
        items.setdefault(cat, []).append((name, [f.image(1) if hasattr(f, "image") else f for f in frames]))
    B = lambda sp, fr=1: render({"proj": "side", **sp}, "bright_cartoon", frames=fr)
    add("buildings", "cottage_thatch", B({"type": "cottage", "wall": "plaster", "roof_mat": "thatch"}))
    add("buildings", "cottage_plank", B({"type": "cottage", "wall": "planks", "roof_mat": "shingles", "W": 28, "D": 20}))
    add("buildings", "cottage_tall", uniq.special("cottage_tall", 1))
    add("buildings", "house_plaster", B({"type": "house", "wall": "plaster", "roof_mat": "tiles"}))
    add("buildings", "house_brick", B({"type": "house", "wall": "brick", "roof_mat": "tiles", "floors": 2, "W": 40}))
    add("buildings", "house_stone", B({"type": "house", "wall": "stone", "roof_mat": "shingles", "floors": 2, "W": 46, "fh": 18}))
    add("buildings", "inn", B({"type": "inn", "lantern": True, "smoke": True}))
    add("buildings", "inn_big", uniq.special("inn_big", 1))
    add("buildings", "stall", B({"type": "stall"}))
    for n in ("bakery", "smithy", "barn", "townhall", "church"):
        add("buildings", n, uniq.special(n, 1))
    add("buildings", "watchtower", B({"type": "round_tower"}))
    add("buildings", "tower", B({"type": "tower"}))
    add("buildings", "windmill", [props.windmill(f / 8).image(1) for f in range(8)])
    add("props", "well", props.well()); add("props", "lamp_lit", props.lamp(True, 14)); add("props", "lamp_post_tall", props.lamp(True, 30))
    add("props", "fence_3", props.fence(3)); add("props", "fence_5", props.fence(5)); add("props", "haystack", props.haystack()); add("props", "cart", props.cart())
    for n in ("barrel", "crates", "sacks", "signpost", "bench", "trough"):
        add("props", n, getattr(props2, n)())
    add("nature", "oak", props2.oak()); add("nature", "apple_tree", props2.oak(apples=True)); add("nature", "pine", props2.pine()); add("nature", "bush", props.bush(26, 15))
    add("nature", "bush_flowers", props.bush(26, 15, flowers="#f3d34a")); add("nature", "flowers", props.flowers(30)); add("nature", "oak_small", props2.oak(24, 32))
    men = [("farmer", "#d05a4a", "#4a5a8a", "#5a3a2a", 24), ("baker", "#e8e8e8", "#4a4a6a", "#8a8a8a", 24), ("smith", "#4a9a6a", "#6a4a3a", "#2a2a2a", 25), ("merchant", "#8a5ac0", "#3a4a3a", "#4a3a2a", 24),
           ("woman_yellow", "#e0b44c", "#5a4a7a", "#a06a3a", 22), ("woman_orange", "#d07a3a", "#3a5a6a", "#5a2a1a", 22), ("child", "#4a7ad0", "#6a5a3a", "#c08a3a", 14), ("elder", "#8a8a9a", "#5a5a6a", "#d8d8d8", 21)]
    for nm, sh, pa, ha, h in men:
        add("people", nm, [props.villager(i, sh, pa, hair=ha, height=h, facing=1).image(1) for i in (0, 1)])
        add("people", nm + "_walk", [props.villager(i, sh, pa, hair=ha, height=h, facing=1, action="walk").image(1) for i in range(8)])   # 8-frame walk cycle, facing right
        add("people", nm + "_walk_l", [props.villager(i, sh, pa, hair=ha, height=h, facing=-1, action="walk").image(1) for i in range(8)])   # facing left
    add("animals", "hen", [props2.chicken(False), props2.chicken(True)]); add("animals", "dog", [props2.dog(0), props2.dog(1)])
    return items


def kit(out):
    from PIL import Image
    items = _items(); cat = ["# Village set (pixel art, side view, drawn with Gizpix pixdraw + pixart, no AI images)\n", "Every file is a transparent PNG at 1x; the bottom of the sprite is the ground line. `_0`, `_1`... are animation frames (people: two idle poses and an 8-frame walk cycle (`_walk_0..7` facing right, `_walk_l_0..7` facing left; step about 2.3 px per frame at 24 px tall; 120 ms per frame), hen: peck, dog: tail, windmill: 8 sail frames).\n"]; rows = []; n = 0
    for c, lst in items.items():
        os.makedirs(os.path.join(out, c), exist_ok=True); cat.append(f"\n## {c} ({len(lst)})\n")
        for nm, fr in lst:
            if len(fr) == 1:
                fr[0].save(os.path.join(out, c, nm + ".png")); n += 1; cat.append(f"- `{c}/{nm}.png` {fr[0].width}x{fr[0].height}")
            else:
                for i, f in enumerate(fr):
                    f.save(os.path.join(out, c, f"{nm}_{i}.png")); n += 1
                cat.append(f"- `{c}/{nm}_0..{len(fr) - 1}.png` {fr[0].width}x{fr[0].height}, {len(fr)} frames")
        rows.append([fr[0] for _, fr in lst])
    open(os.path.join(out, "CATALOG.md"), "w", encoding="utf-8").write("\n".join(cat) + "\n")
    GAP, MAXW = 10, 760; lines = []
    for ims in rows:
        line, w = [], 0
        for im in ims:
            if w + im.width + GAP > MAXW and line:
                lines.append(line); line, w = [], 0
            line.append(im); w += im.width + GAP
        lines.append(line)
    sh = Image.new("RGBA", (MAXW + 2 * GAP, sum(max(i.height for i in r) + GAP for r in lines) + GAP), (143, 196, 140, 255)); y = GAP
    for r in lines:
        rh = max(i.height for i in r); x = GAP
        for im in r:
            sh.alpha_composite(im, (x, y + rh - im.height)); x += im.width + GAP
        y += rh + GAP
    sh.resize((sh.width * 2, sh.height * 2), Image.NEAREST).save(os.path.join(out, "sheet.png"))
    return {"sprites": n, "categories": {c: len(l) for c, l in items.items()}, "sheet": os.path.join(out, "sheet.png")}


def stack(out, seed=1):
    r = subprocess.run([sys.executable, os.path.join(HERE, "village_stack.py"), out, str(seed)], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("error: " + (r.stderr.strip().splitlines() or ["village_stack failed"])[-1])
    return os.path.join(out, "stack.json")


def selftest():
    t = tempfile.mkdtemp()
    try:
        r = kit(os.path.join(t, "kit")); assert r["sprites"] == 192 and r["categories"] == {"buildings": 17, "props": 13, "nature": 7, "people": 24, "animals": 2}, r
        assert os.path.exists(os.path.join(t, "kit", "CATALOG.md"))
        sj = stack(os.path.join(t, "st"), 3); sys.path.insert(0, os.path.join(ROOT, "parallax"))
        import pix_parallax as pp
        rep = pp.check(pp.load_spec(sj)); assert not rep["flags"] and rep["loop_frames"] == 2880, rep["flags"]
    finally:
        shutil.rmtree(t, ignore_errors=True)
    print("pix_village selftest ok")


def main(argv):
    if len(argv) >= 2 and argv[0] == "kit":
        r = kit(argv[1]); print(f"{r['sprites']} files in {argv[1]}: {r['categories']}; sheet {r['sheet']}"); return 0
    if len(argv) >= 2 and argv[0] == "stack":
        print(stack(argv[1], int(argv[2]) if len(argv) > 2 else 1)); return 0
    if argv[:1] in (["-h"], ["--help"], ["help"]):
        print(__doc__); return 0
    if argv[:1] == ["selftest"]:
        selftest(); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
