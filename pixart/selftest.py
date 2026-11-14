# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixart selftest: the building blocks keep their promises and every worked recipe still renders without lint flags."""
import numpy as np


def selftest():
    from .core import Canvas, ramp, lum, _pixel_perfect, _bres
    from .examples import EXAMPLES
    from .font import text_size
    c = Canvas(16, 16)
    assert c.oval(4, 4, 8, 8).sum(1)[4:12].tolist() == [4, 6, 8, 8, 8, 8, 6, 4], "8 px circle rows"
    m = c.curve([(1, 12), (5, 3), (12, 2), (14, 9)]); assert not ((m[:-1, :-1] & m[1:, :-1] & m[:-1, 1:]) | (m[1:, 1:] & m[1:, :-1] & m[:-1, 1:])).any(), "curve has an L corner"
    for base in ("#c8402f", "#e2b23a", "#3f7fc4", "#808080", "#f4f0e0", "#30203a"):
        for n in (3, 4, 5):
            ls = [lum(x) for x in ramp(base, n).cols]; assert all(b - a > 0.03 for a, b in zip(ls, ls[1:])), f"ramp {base} n={n} not rising: {ls}"
    from .core import ramp9
    for hue in (0, 60, 120, 180, 240, 300): ls = [lum(x) for x in ramp9(hue).cols]; assert all(q > p for p, q in zip(ls, ls[1:])) and len(ramp9(hue, n=5)) == 5, f"ramp9 {hue}"
    b = Canvas(16, 16); b.fill(b.oval(2, 2, 12, 12), "#c8402f", form="ball"); ys, xs = np.nonzero(b.tone == 3); assert xs.mean() < 8 and ys.mean() < 8, "highlight is not toward the top-left light"
    ring = b.outline(); assert ring.sum() > 0 and not (ring & (b.tone > 0)).any() and b.rgba()[..., 3].sum() > 0
    from .core import rim, shift, Ramp                       # helpers added after the game-asset test (2026-11-13)
    t = Canvas(40, 40); g = Ramp(["#202020", "#505050", "#808080", "#b0b0b0", "#e0e0e0"]); tilted = t.oval(8, 14, 24, 12, angle=45)
    assert tilted[26, 26] and not tilted[14, 26] and abs(int(tilted.sum()) - int(t.oval(8, 14, 24, 12).sum())) < 20, "a tilted oval keeps its area and leans one way"
    band = t.ring(6, 6, 28, 28, t=4); assert not band[20, 20] and band[20, 7], "ring has a hole"
    tap = t.curve([(4, 36), (14, 20), (30, 10)], w=6, w1=1); assert tap[32:, :].sum() > tap[:14, :].sum() > 0, "tapered curve is thick at the start, thin at the end"
    t.fill(band, g, form="glow", centre=(20, 7)); assert t.tone[7, 20] > t.tone[33, 20], "glow is brightest at its centre"
    t.px(20, 7, g, 99); t.px(20, 8, g, -9); assert t.tone[7, 20] == 4 and t.tone[8, 20] == -1, "px clamps a tone past the ramp"
    before = t.tone.copy(); t.texture(band, cell=3, seed=1); assert (t.tone != before).sum() > 20 and t.tone.max() <= 4 and not (t.rid[~band] >= 0).any(), "texture re-tones inside the mask only"
    _, fl = t.lint(quiet=True); assert not any("thin parts" in x for x in fl), "texture on a 4 px band must not read as thin parts"
    assert rim(band, 2, 0).sum() > 0 and not (rim(band, 2, 0) & shift(band, 2, 0)).any()
    t.seam(t.line([(8, 20), (9, 20)])); t.outline("dark", rim=(g, 4)); assert (t.ol & (t.tone == 4)).any() and (t.ol & (t.tone == -1)).any(), "rim outline: pale on the lit side, dark elsewhere"
    lk = t.links([(2, 2), (2, 9)], g, tones=(4, 0), period=2); assert [int(t.tone[y, 2]) for y in range(2, 10)] == [4, 4, 0, 0, 4, 4, 0, 0] and lk.sum() == 8
    k = Canvas(24, 24); k.fill(k.rect(2, 2, 20, 20), g, tone=2); k.fill(k.rect(2, 2, 20, 8), g, tone=3); k.tone[6, 6] = 0; k.tone[10, 12] = 3; k.px(16, 16, g, 0); k.fill(k.rect(2, 14, 20, 1), g, tone=4)
    _, fl = k.lint(quiet=True); assert _["spur_px"] == 1 and _["orphan_px"] == 1 and _["band_px"] == 20, _
    assert k.tidy() == {"specks": 1, "spurs": 1, "bands": 0} and k.tone[6, 6] == 3 and k.tone[10, 12] == 2 and k.tone[16, 16] == 0 and k.tone[14, 5] == 4, "tidy: speck and spur go, the hand pixel and the band stay"
    assert k.tidy(bands=True)["bands"] == 20 and k.tone[14, 5] == 2 and k.tone[16, 16] == 0, "tidy(bands=True) dissolves the hairline band"
    from .core import house
    hs = house("steel"); hg = house("gold", 4); assert len(hs) == 7 and len(hg) == 4 and house("#7a3e26").name == "copper" and all(q > p for p, q in zip(hs.th, hs.th[1:])) and hs.th[1] > hg.th[1], "house ramps: steel keeps more dark than gold"
    hb = Canvas(24, 24); hb.fill(hb.oval(2, 2, 20, 20), hs, form="ball"); assert (hb.tone[hb.rid >= 0] <= 1).mean() > 0.3 and hb.tone.max() == 6, "a house steel ball is mostly dark with a small highlight"
    from .core import rgb as _rgb, grow as _grow, shrink as _shrink
    assert _rgb("#8af") == (136, 170, 255) and (_grow(band, 0) == band).all() and (_shrink(band, 0) == band).all(), "3-digit hex, grow/shrink by 0"
    pc = Canvas(40, 40); pm, pu, pv = pc.pipe([(4, 34), (16, 30), (30, 16), (34, 5)], hs, w=3, w1=9); pb, _, _ = pc.pipe([(4, 34), (16, 30), (30, 16), (34, 5)], hg, w=3, w1=9, span=(0.6, 0.7))
    assert pm[34, 4] and pm[6, 33] and (pm[:12].sum() > 1.5 * pm[30:].sum()) and pu[34, 4] < 0.1 < 0.9 < pu[6, 33] and 0 < pb.sum() < pm.sum() / 4 and (pc.rid[pb] == pc._r(hg)).all(), "pipe tapers, runs u 0..1, a span paints a band"
    assert pc.tone[pm & (pv < -0.3) & ~pb].mean() > pc.tone[pm & (pv > 0.3) & ~pb].mean(), "pipe: the side toward the light is brighter"
    hi_ = house("iron"); ib = Canvas(24, 24); ib.fill(ib.oval(2, 2, 20, 20), hi_, form="ball"); assert (ib.tone[ib.rid >= 0] <= 1).mean() > (hb.tone[hb.rid >= 0] <= 1).mean(), "an iron ball is darker than a steel ball"
    rc = Canvas(32, 32); rm, ru, rv = rc.pipe(rc.ellipse_pts(16, 16, 11, 7, angle=-20), hi_, w=4, closed=True); assert rm.any() and not rm[16, 16] and rm.sum() > 120, "a closed pipe is a ring with a hole"
    sp = rc.spaced(rc.ellipse_pts(16, 16, 11, 7), 8, closed=True); assert len(sp) == 8 and len(set(sp)) == 8 and all(abs(x - 16) <= 12 and abs(y - 16) <= 8 for x, y in sp), sp
    sg = Canvas(20, 40); fm, fu, _ = sg.pipe([(10, 36), (10, 4)], hi_, w=7, caps="flat"); pl = sg.segments(fm, fu, 4); assert len(pl) == 4 and all(p.sum() > 20 for p in pl) and sum(p.sum() for p in pl) == fm.sum(), "four plates cover the finger"
    fl = Canvas(10, 4); fl.fill(fl.rect(0, 0, 3, 4), g); fl.flip(); assert fl.rid[0, 9] >= 0 and fl.rid[0, 0] < 0, "flip mirrors the painting"
    oc = Canvas(16, 16); fr = house("red", 4); oc.fill(oc.oval(3, 3, 6, 6), fr); oc.fill(oc.rect(9, 3, 4, 8), hs); oc.outline("black", lines={fr: "#5a0f14"}); a_ = oc.rgba()
    assert tuple(a_[2, 5, :3]) == (0x5a, 0x0f, 0x14) and tuple(a_[2, 10, :3]) != (0x5a, 0x0f, 0x14), "lines= recolours only the outline next to that part"
    assert text_size("AB") == (11, 7) and text_size("AB", bold=True) == (13, 7)
    import tempfile, os as _os
    from .core import strip, sheet, lint_all
    from .cli import look, compare
    from PIL import Image as _I
    with tempfile.TemporaryDirectory() as d:   # look: a checkerboard is all orphans with run 1, a flat block has none; compare adds the difference panel
        import numpy as _np
        chk = _np.zeros((8, 8, 4), _np.uint8); chk[..., 3] = 255; chk[::2, ::2, :3] = 255; chk[1::2, 1::2, :3] = 255; flat = chk.copy(); flat[..., :3] = 90
        pa, pb = _os.path.join(d, "a.png"), _os.path.join(d, "b.png"); _I.fromarray(chk, "RGBA").save(pa); _I.fromarray(flat, "RGBA").save(pb); la, lb = look(pa), look(pb)
        assert la["orphans"] == 1 and la["run"] == 1 and la["colours"] == 2 and la["step"] > 200, la
        assert lb["orphans"] == 0 and lb["run"] == 8 and lb["busy"] == 0, lb
        assert _I.open(compare([pa, pb], _os.path.join(d, "c.png"), height=64)).width == 3 * 64 + 4 * 8
    from .rig import humanoid, mannequin8
    from .poses import ACTIONS, hold
    with tempfile.TemporaryDirectory() as td:                       # the review outputs run (strip crashed once without sil=True)
        fr = EXAMPLES["coin"](); strip(fr, _os.path.join(td, "a.png")); strip(fr, _os.path.join(td, "b.png"), sil=True); sheet([fr, fr], _os.path.join(td, "c.png"))
    rg = humanoid(36, 4); rg.add("weapon", "arm_f_lo", 18, back=12)
    for d in ("S", "E", "N", "W"):
        jj = rg.solve(hold(ACTIONS["cast"], weapon=180)[2][0], root_x=28, ground=48, direction=d); cc = Canvas(56, 52); mm = mannequin8(cc, rg, jj, "#e8b48c", "#3f7fc4", "#55466b")
        assert max(p[1] for b in jj for p in jj[b] if b.startswith(("leg", "foot"))) == 48 and mm["head"].any(), f"direction {d}"
        assert abs((jj["weapon"][0][1] - jj["weapon"][1][1]) - 30) < 0.01, "a held shaft keeps its full length"
    from .cli import style_profile, refs, no_ai, REFS, size_bucket
    mu, sd, sp = style_profile("s11"); assert len(mu) == 8 and sp["n"] > 50 and style_profile("S99") is None, "style profile"
    assert style_profile("S11", 30)[2]["bucket"] == "25-32" and style_profile("S11", 40)[2]["bucket"].startswith("all sizes") and size_bucket(24) == "<=24" and size_bucket(49) == ">48", "size buckets (S11 33-48 is one pack, so it falls back)"
    from . import cli as _cli
    with tempfile.TemporaryDirectory() as d:                     # cands -> pick -> calibrate on two synthetic candidates, into a temp picks file
        import numpy as _np
        a_ = _np.zeros((30, 30, 4), _np.uint8); a_[2:28, 2:28] = (90, 70, 50, 255); b_ = a_.copy(); b_[2:28:2, 2:28:3, :3] = 140
        pa, pb = _os.path.join(d, "a.png"), _os.path.join(d, "b.png"); _I.fromarray(a_, "RGBA").save(pa); _I.fromarray(b_, "RGBA").save(pb)
        old, _cli.PICKS = _cli.PICKS, _os.path.join(d, "picks.jsonl")
        try:
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                _cli.cands([pa, pb], _os.path.join(d, "c"), style="S11"); r = _cli.pick(_os.path.join(d, "c", "cands.json"), 2)
                closer = r["winner"]["distance"] < r["losers"][0]["distance"]; ag = _cli.calibrate()
            assert _os.path.isfile(_os.path.join(d, "c", "cands.png")) and r["judge"] == "user" and ag == (1.0 if closer else 0.0), (ag, closer)
            with contextlib.redirect_stdout(io.StringIO()): assert _cli.calibrate("claude") is None, "judges are kept apart"
        finally: _cli.PICKS = old
    if _os.path.isfile(_os.path.join(REFS, "index.csv")):                 # the reference collection is local and optional
        fs = refs(style="S11", subject="potion", n=3); assert len(fs) == 3 and all(_os.path.isfile(f) for f in fs), fs
        assert no_ai("private/clockworkraven/raven-fantasy-icons-free") and not no_ai("open/luizmelo/hero-knight"), "no-AI licence check"
        assert not refs(tier="private", style="S11", n=5000) or not any("clockworkraven" in f for f in refs(tier="private", style="S11", n=5000)), "no-AI packs are never offered"
    bad = 0
    for name, fn in EXAMPLES.items():
        r = fn(); f = (r[0] if isinstance(r, list) else r); _, flags = f.lint(quiet=True); flags = [x for x in flags if (name, x) not in (("flame", "flat contrast"), ("cat", "irregular edge steps"))]
        if flags: print(f"  FAIL {name}: {flags}"); bad += 1
    print("pixart selftest:", "FAILED" if bad else f"ok ({len(EXAMPLES)} recipes clean)"); return 1 if bad else 0
