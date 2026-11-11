# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixdraw selftest: every preset x projection x bundled style renders, is deterministic, animations loop, palette styles stay in their palette, output passes
basic pixel_lint bounds, and the package contains no game-specific names or assets. python -m pixdraw selftest"""
import io, importlib.util, json, os, sys, tempfile
import numpy as np
from PIL import Image
from . import render, scene, compose, list_styles, load_style, PRESETS, extract_style
from .export import export, sheet, save_gif
from .templates import spec_of

HERE = os.path.dirname(os.path.abspath(__file__))


def _lint():
    p = os.path.join(HERE, "..", "check", "pixel_lint.py")
    if not os.path.exists(p): return None
    spec = importlib.util.spec_from_file_location("pixel_lint", p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m.lint


def gif_check(fr):
    """GIF output must show exactly the frames given: one colour is one colour in every frame, and an opaque colour is never
    flagged transparent (an old bug: transparency index 0 was forced, so a ground colour at index 0 vanished or flashed)"""
    from PIL import ImageSequence
    ground = (40, 58, 36, 255)
    cases = {"opaque ground": [Image.new("RGBA", (24, 16), ground) for _ in range(3)],
             "transparent edge": [Image.new("RGBA", (24, 16), (0, 0, 0, 0)) for _ in range(3)]}
    for k, f in enumerate(cases["opaque ground"]): f.putpixel((3 + k, 4), (200, 30 + k, 30, 255))
    for k, f in enumerate(cases["transparent edge"]): f.paste((90, 60, 40, 255), (4, 4, 10 + k, 12))
    many = [Image.effect_noise((40, 40), 80).convert("RGBA") for _ in range(2)]; cases["over 256 colours"] = many
    with tempfile.TemporaryDirectory() as d:
        for name, frames in cases.items():
            p = os.path.join(d, "t.gif"); save_gif(frames, p, 100)
            with Image.open(p) as im: got = [np.array(x.convert("RGBA")) for x in ImageSequence.Iterator(im)]
            assert len(got) == len(frames), (name, "frame count")
            for g, src in zip(got, frames):
                s = np.array(src); opaque = s[..., 3] >= 128
                if name != "over 256 colours": assert np.array_equal(g[opaque][:, :3], s[opaque][:, :3]) and ((g[..., 3] >= 128) == opaque).all(), (name, "frame differs from its source")
                else: assert (np.abs(g[..., :3].astype(int) - s[..., :3].astype(int)).mean() < 12), (name, "quantization too lossy")


def run():
    lint = _lint(); n = 0
    for st in list_styles():
        S = load_style(st)
        for proj in ("iso", "top", "side"):
            for t in PRESETS:
                spec = {"type": t, "proj": proj}; f = render(spec, st)
                assert len(f) == 1 and f[0].mode == "RGBA" and 20 < f[0].width < 160 and 20 < f[0].height < 160, (st, proj, t, f[0].size)
                a = np.array(f[0]); assert (a[..., 3] > 0).sum() > 400, ("nearly empty", st, proj, t)
                assert np.array_equal(a, np.array(render(spec, st)[0])), ("not deterministic", st, proj, t)
                if S["palette"]:
                    cols = {tuple(p) for p in a[a[..., 3] > 0][:, :3]}; assert cols <= {tuple(c) for c in S["palette"]}, ("left the palette", st, proj, t)
                if lint:
                    r = lint(a)[0]; assert r["speck_px"] < 40 and r["thick_line"] < 0.5, (st, proj, t, r["speck_px"], r["thick_line"])
                n += 1
    for bad_spec, word in (({"type": "nope"}, "type"), ({"proj": "x"}, "proj"), ({"W": 5}, "W and D"), ({"floors": 0}, "floors"), ({"fh": 6}, "fh"), ({"wall": "lava"}, "material"),
                           ({"roof": "hip", "W": 20, "D": 40}, "hip"), ({"roof": "cone"}, "roof"), ({"roof": "cone", "round": True, "proj": "iso", "wing": True}, "wing"), ({"dormers": 9}, "dormers"),
                           ({"roof": "flat", "wing": True}, "wing"), ({"wing": True, "proj": "side"}, "wing"), ({"wing": {"w": 5}}, "wing"), ({"round": True, "roof": "gable"}, "round")):
        try: render(bad_spec, "dark_fantasy"); raise AssertionError(("accepted a bad spec", bad_spec))
        except ValueError as e: assert word in str(e), (bad_spec, str(e))
    try: load_style("no_such_style"); raise AssertionError("accepted an unknown style")
    except ValueError: pass
    edge = [{"type": "house", "W": 12, "D": 12}, {"type": "inn", "W": 160, "D": 90, "floors": 3}, {"type": "tower", "floors": 1}, {"type": "tower", "W": 40, "D": 20, "roof": "hip"},
            {"type": "stall", "W": 14}, {"type": "stall", "W": 120}, {"type": "inn", "fh": 14, "floors": 6}, {"type": "cottage", "pitch": 3}, {"type": "keep", "W": 120, "D": 70}]
    for proj in ("iso", "top", "side"):                                  # unusual sizes must render and must not touch the canvas edge (nothing clipped)
        for sp in edge:
            S0 = load_style("dark_fantasy"); im = scene({**sp, "proj": proj}, S0); a = np.array(im)[..., 3] > 0
            assert a.any() and not (a[0].any() or a[-1].any() or a[:, 0].any() or a[:, -1].any()), ("clipped", proj, sp)
    for proj in ("iso", "top"):                                          # dormers, wing and round buildings in every style: render, stay in the palette, do not clip
        for st in list_styles():
            S1 = load_style(st)
            for sp in ({"type": "inn", "dormers": 2}, {"type": "inn", "wing": True}, {"type": "cottage", "wing": {"w": 14, "l": 10}, "dormers": 1}, {"type": "round_tower", "roof": "flat"}, {"type": "round_tower", "W": 40, "floors": 1}):
                im = scene({**sp, "proj": proj}, S1); a = np.array(im); al = a[..., 3] > 0; assert al.sum() > 400 and not (al[0].any() or al[-1].any() or al[:, 0].any() or al[:, -1].any()), ("extras", st, proj, sp)
                if S1["palette"]: assert {tuple(p) for p in a[al][:, :3]} <= {tuple(q) for q in S1["palette"]}, ("left the palette", st, proj, sp)
    for proj in ("iso", "top", "side"):                                  # spec_of is idempotent: a scene must not change when its spec was already normalised (top view once got pitch x0.65 twice)
        sp0 = {"type": "inn", "proj": proj}; assert np.array_equal(np.array(scene(sp0, load_style("dark_fantasy"))), np.array(scene(spec_of(sp0), load_style("dark_fantasy")))), ("spec_of not idempotent", proj)
    for bad_spec, word in (({"floors": "abc"}, "floors"), ({"W": "wide"}, "W"), ({"dormers": "x"}, "dormers")):
        try: render(bad_spec, "dark_fantasy"); raise AssertionError(("accepted", bad_spec))
        except ValueError as e: assert word in str(e), (bad_spec, str(e))
    S = load_style("dark_fantasy")                                       # animation loops: phase 0 == phase 1
    for t in ("stall", "tower", "inn"):
        assert np.array_equal(np.array(scene({"type": t}, S, 0.0)), np.array(scene({"type": t}, S, 1.0))), ("animation does not loop", t)
    fr = render({"type": "stall"}, "bright_cartoon", frames=8); assert len(fr) == 8 and len({f.size for f in fr}) == 1
    assert len({np.array(f).tobytes() for f in fr}) > 1, "frames are all identical"
    im, js = sheet(fr, "x"); assert len(js["frames"]) == 8 and js["meta"]["frameTags"][0]["to"] == 7
    with tempfile.TemporaryDirectory() as d:
        paths = export(fr, d, "stall", scale=2); assert all(os.path.getsize(p) > 0 for p in paths) and len(paths) == 4
        js = json.load(open(os.path.join(d, "stall_sheet.json"))); sz = Image.open(os.path.join(d, "stall_sheet.png")).size; assert js["meta"]["size"] == {"w": sz[0], "h": sz[1]}
        src = os.path.join(d, "s.png"); render({"type": "house"}, "dark_fantasy")[0].save(src)          # style extractor round trip
        out = os.path.join(d, "st.json"); extract_style([src], out); assert render({"type": "inn"}, out)[0].width > 20
    gif_check(fr)
    vj = json.load(open(os.path.join(HERE, "examples", "village.json"), encoding="utf-8"))          # scene composition: renders, loops, deterministic, bad items rejected
    for st in list_styles():
        a = compose(vj["items"], st, tuple(vj["size"]), frames=4); assert len(a) == 4 and a[0].size == tuple(vj["size"]) and np.array(a[0])[..., 3].min() == 255, st
    assert np.array_equal(np.array(compose(vj["items"], "dark_fantasy", tuple(vj["size"]), 4)[0]), np.array(compose(vj["items"], "dark_fantasy", tuple(vj["size"]), 4)[0]))
    for st in list_styles():                                             # pine trees and fences running into the depth
        e = compose([{"tree": 18, "kind": "pine", "x": 40, "y": 60}, {"fence": [10, 50], "x": 15, "axis": "y"}, {"fence": [10, 50], "y": 70}], st, (90, 80)); assert np.array(e[0])[..., 3].min() == 255, st
    for bad_item in ({"tree": 10, "kind": "oak", "x": 5, "y": 5}, {"fence": [1, 9], "axis": "y"}, {"tree": 10}, {"building": {}, "x": 1}, {"fence": [1], "y": 3}, {"path": [[1, 1]]}, {"tree": 1, "bush": 1, "x": 1, "y": 1}):
        try: compose([bad_item], "dark_fantasy"); raise AssertionError(("accepted a bad item", bad_item))
        except ValueError: pass
    bad = []                                                             # nothing game-specific inside the package
    needles = ["guild" + "hold", "market" + "_t1", "pixel" + "lab"]
    for root, _, files in os.walk(HERE):
        for f in files:
            if f.endswith((".py", ".json", ".md")) and f != "selftest.py":
                txt = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read().lower()
                bad += [(f, w) for w in needles if w in txt]
    assert not bad, bad
    from . import golden
    ok, msg = golden.check(); assert ok, msg; print("golden:", msg)
    print(f"pixdraw selftest ok ({n} renders)"); return 0
