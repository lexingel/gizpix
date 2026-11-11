# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixfx selftest: every effect is deterministic, loops close, one-shots end empty, nothing is cropped; palette and option handling; sheet, JSON and GIF export.
python -m pixfx selftest   (no golden hashes: float maths can differ by a pixel between platforms, so the checks are about properties, not bytes)"""
import json, os, tempfile
import numpy as np
from PIL import Image, ImageSequence
from . import engine
from .export import write_all
from .ramps import resolve


def run():
    reg = engine.registry(); assert len(reg) >= 12, len(reg)
    for eid in sorted(reg):
        bad = engine.check(eid); assert not bad, (eid, bad)
        m, meta = reg[eid]; assert {"id", "name", "loop", "duration", "size", "about"} <= set(meta), eid
    fr = engine.render("fire/torch", {"palette": "ice"}); fr2 = engine.render("fire/torch", {"palette": "ice"})
    assert all(np.array_equal(np.array(a), np.array(b)) for a, b in zip(fr, fr2)), "same options must give the same frames"
    other = engine.render("fire/torch", {"seed": 9}); assert any(not np.array_equal(np.array(a), np.array(b)) for a, b in zip(fr, other)), "seed must change something"
    assert engine.render("impacts/hit-spark", {"flip": True})[1].size == (72, 72)
    for bad_opt in ({"nope": 1},):
        try: engine.options(engine.get("fire/torch")[1], bad_opt); raise SystemExit("an unknown option must be an error")
        except KeyError: pass
    try: resolve("not-a-palette"); raise SystemExit("an unknown palette must be an error")
    except ValueError: pass
    assert resolve("#102,#215,#43a")[1] == (34, 17, 85)
    for eid in ("fire/torch", "explosions/small-explosion"):
        m, meta = engine.get(eid); frames = engine.render(eid, frames=6)
        with tempfile.TemporaryDirectory() as d:
            paths = write_all(frames, d, "x", meta, {}, 12, scale=2)
            assert len(paths) == 4 and all(os.path.getsize(p) > 0 for p in paths), paths
            js = json.load(open(os.path.join(d, "x_sheet.json"), encoding="utf-8")); assert js["meta"]["pixfx"]["frames"] == 6 and js["meta"]["pixfx"]["loop"] == meta["loop"]
            with Image.open(os.path.join(d, "x.gif")) as g: n = sum(1 for _ in ImageSequence.Iterator(g))
            assert n >= 6, n
    print(f"pixfx selftest ok ({len(reg)} effects)"); return 0
