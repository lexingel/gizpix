# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixdraw.templates - buildings from a few parameters. A spec is a dict; `type` picks a preset, every other key overrides it.

  type        house cottage inn tower keep stall           W, D        footprint (x, y) in world units; pixel size follows the projection
  proj        iso | top | side                              floors, fh  storeys and storey height (fh >= 14)
  roof        gable | hip | flat                            pitch       roof rise per unit run (hip needs W >= D)
  wall        planks stone brick plaster ...                roof_mat    shingles tiles thatch flagstone ... (flat roofs default to flagstone)
  chimney smoke lit awning open_front lantern flag battlements door  : switches
  windows (per storey), win_w, win_h, door_w, door_h, chimney_fx, chimney_fy, chimney_w : sizes and places (defaults follow fh and W)
  ground (soft footprint shadow), plinth (stone course at the foot), side_gable "roof"|"wall" (side view: gable end shingled like a roof, or wall-coloured with rake slabs)
  props       [{"kind": "crate"|"barrel"|"sack", "x": world x or "fx": fraction of W, "y": .. or "fy": fraction of D, "z": .., "w": .., "s": ..}]
Animation (t in 0..1, loops): lantern flicker, awning ripple, chimney smoke, flag."""
import math
from PIL import Image
from .core import View, Cv, PROJECTIONS, face3, box, beam, snap
from .materials import MATERIALS, ramp_of
from .styles import load_style
from . import parts as P
from . import extras as X

DEFAULTS = {"proj": "iso", "W": 44, "D": 30, "floors": 2, "fh": 18, "roof": "gable", "pitch": 0.55, "overhang": 2.5, "wall": "planks", "roof_mat": "shingles",
            "chimney": True, "smoke": True, "lit": True, "awning": False, "open_front": False, "props": [], "lantern": False, "flag": False, "battlements": False, "door": True, "ground": True, "plinth": True, "side_gable": "roof", "dormers": 0, "wing": False, "round": False}
PRESETS = {
    "cottage": {"W": 30, "D": 24, "floors": 1, "fh": 20, "pitch": 0.7, "roof_mat": "thatch", "wall": "plaster"},
    "house": {"W": 38, "D": 26, "floors": 1, "fh": 22},
    "inn": {"W": 48, "D": 30, "floors": 2, "fh": 18},
    "tower": {"W": 24, "D": 24, "floors": 4, "fh": 16, "roof": "hip", "pitch": 0.9, "wall": "stone", "chimney": False, "flag": True, "smoke": False},
    "keep": {"W": 46, "D": 34, "floors": 3, "fh": 16, "roof": "flat", "wall": "stone", "battlements": True, "chimney": False, "smoke": False, "flag": True},
    "round_tower": {"round": True, "W": 26, "D": 26, "floors": 4, "fh": 16, "roof": "cone", "pitch": 0.9, "wall": "stone", "roof_mat": "tiles", "chimney": False, "flag": True, "smoke": False},
    "stall": {"W": 44, "D": 30, "floors": 1, "fh": 24, "open_front": True, "awning": True, "lantern": True, "chimney": False, "smoke": False, "door": False,
              "props": [{"kind": "crate", "fx": 0.11, "fy": 0.17, "z": 0, "w": 11}, {"kind": "crate", "fx": 0.16, "fy": 0.2, "z": 11, "w": 8}, {"kind": "barrel", "fx": 0.75, "fy": 0.23},
                        {"kind": "sack", "fx": -0.07, "fy": -0.2}, {"kind": "sack", "fx": 0.14, "fy": -0.33, "s": 0.8}]},
}


def spec_of(spec):
    """merge defaults + preset + user keys and validate; raises ValueError naming the key. Idempotent: a spec that came out of spec_of is returned as it is"""
    if spec.get("_done"): return spec
    t = spec.get("type", "")
    if t and t not in PRESETS: raise ValueError(f"unknown type {t!r}; choose one of {', '.join(PRESETS)}")
    known = set(DEFAULTS) | {"type", "windows", "win_w", "win_h", "door_w", "door_h", "chimney_fx", "chimney_fy", "chimney_w"} | {k for p in PRESETS.values() for k in p}
    unknown = sorted(k for k in spec if k not in known)
    if unknown:
        import difflib
        near = difflib.get_close_matches(unknown[0], sorted(known), 1)
        raise ValueError(f"unknown spec key {unknown[0]!r}" + (f"; did you mean {near[0]!r}?" if near else "") + f" (known keys: {', '.join(sorted(known - {'_done'}))})")
    sp = {**DEFAULTS, **PRESETS.get(t, {}), **spec}
    for k in ("W", "D", "fh", "pitch", "overhang"):
        try: sp[k] = float(sp[k])
        except (TypeError, ValueError): raise ValueError(f"{k} must be a number, got {sp[k]!r}") from None
    try: sp["floors"] = int(sp["floors"])
    except (TypeError, ValueError): raise ValueError(f"floors must be a whole number, got {sp['floors']!r}") from None
    if sp["proj"] not in PROJECTIONS: raise ValueError(f"unknown proj {sp['proj']!r}; choose one of {', '.join(PROJECTIONS)}")
    if sp["roof"] not in ("gable", "hip", "flat", "cone"): raise ValueError(f"unknown roof {sp['roof']!r}; choose gable, hip, flat or cone (cone is for round buildings)")
    if sp["round"]:
        if sp["roof"] not in ("cone", "flat"): raise ValueError("a round building needs roof cone or flat")
        sp["D"] = sp["W"]                                                # W is the diameter
        if sp["wing"] or sp["dormers"]: raise ValueError("wing and dormers are for rectangular buildings")
    elif sp["roof"] == "cone": raise ValueError("roof cone needs round=true (try type=round_tower)")
    if sp["roof"] == "flat" and "roof_mat" not in spec and "roof_mat" not in PRESETS.get(t, {}): sp["roof_mat"] = "flagstone"
    for k in ("wall", "roof_mat"):
        if sp[k] not in MATERIALS: raise ValueError(f"unknown material {sp[k]!r} for {k!r}; known: {', '.join(MATERIALS)}")
    if sp["W"] < 12 or sp["D"] < 12: raise ValueError("W and D must be at least 12 world units")
    if sp["floors"] < 1 or sp["floors"] > 12: raise ValueError("floors must be 1 to 12")
    if sp["W"] > 400 or sp["D"] > 400: raise ValueError("W and D must be at most 400 world units")
    if sp["fh"] < 14: raise ValueError("fh (storey height) must be at least 14")
    if sp["pitch"] <= 0 and sp["roof"] != "flat": raise ValueError("pitch must be > 0 for gable and hip roofs")
    if sp["proj"] == "top": sp["pitch"] *= 0.65                       # in the 3/4 view roofs are drawn 35% flatter (they stack on top of the walls)
    try: sp["dormers"] = int(sp["dormers"])
    except (TypeError, ValueError): raise ValueError(f"dormers must be a whole number, got {sp['dormers']!r}") from None
    if not 0 <= sp["dormers"] <= 4: raise ValueError("dormers must be 0 to 4")
    if (sp["dormers"] or sp["wing"]) and (sp["roof"] != "gable" or sp["proj"] == "side"): raise ValueError("dormers and wing need a gable roof and the iso or top projection")
    if sp["wing"] and sp["open_front"]: raise ValueError("a wing cannot be combined with open_front")
    if sp["wing"]:
        w = sp["wing"] if isinstance(sp["wing"], dict) else {}
        try: sp["wing_w"] = float(w.get("w", round(sp["D"] * 0.62))); sp["wing_l"] = float(w.get("l", 14))
        except (TypeError, ValueError): raise ValueError(f"wing: w and l must be numbers, got {w!r}") from None
        if set(w) - {"w", "l"}: raise ValueError(f"wing: unknown key {sorted(set(w) - {'w', 'l'})[0]!r}; use w and l")
        if not 12 <= sp["wing_w"] <= sp["D"] or sp["wing_l"] < 8 or sp["wing_w"] > sp["W"] - 14: raise ValueError(f"wing: w must be 12..min(D, W-14) and l at least 8 (got w={sp['wing_w']}, l={sp['wing_l']})")
    if sp["roof"] == "hip" and sp["W"] < sp["D"]: raise ValueError("a hip roof needs W >= D (its ridge runs along x); swap W and D or use a gable roof")
    sp["_done"] = True
    return sp


def _dims(sp):
    """sizes of openings, defaults follow the storey height and the width"""
    W, fh = sp["W"], sp["fh"]; nw = int(sp.get("windows", max(1, int(W // 14)))); slot = W / nw
    ww = min(sp.get("win_w", 8), slot - 3); wh = min(sp.get("win_h", 8), fh * 0.5); dw = min(sp.get("door_w", 10), slot - 2); dh = min(sp.get("door_h", 15), fh * 0.85)
    return nw, max(3, ww), max(3, wh), max(4, dw), max(6, dh), (fh - max(3, wh)) * 0.55


def _openings(S, sp, depth_fracs=None):
    """overlays for the front wall (or for the gable end when depth_fracs is given)"""
    fh, fl = sp["fh"], sp["floors"]; nw, ww, wh, dw, dh, wy = _dims(sp); ov = []
    if depth_fracs is not None:
        for i in range(fl):
            for f in depth_fracs: ov.append((sp["D"] * f - ww / 2, i * fh + wy, sp["D"] * f + ww / 2, i * fh + wy + wh, P.window(S, lit=(i > 0 and sp["lit"]))))
        return ov
    W = sp["W"]
    for i in range(fl):
        for j in range(nw):
            cu = W * (j + 0.5) / nw
            if i == 0 and j == 0 and sp["door"] and not sp["wing"]: ov.append((cu - dw / 2, 0, cu + dw / 2, dh, P.door(S)))
            else: ov.append((cu - ww / 2, i * fh + wy, cu + ww / 2, i * fh + wy + wh, P.window(S, lit=(i > 0 and sp["lit"] and j % 2 == 0))))
    return ov


def _plinth(sp, S, wall_mat, ramp, shift, lo=3.0):
    """wall material wrapper: a stone course in the lowest `lo` units (skipped for stone/brick walls and when sp['plinth'] is off)"""
    if not sp["plinth"] or sp["wall"] in ("stone", "brick"): return wall_mat
    st = S["ramps"]["stone"]; col = st[max(0, min(len(st) - 1, 2 + shift))]; dark = st[max(0, min(len(st) - 1, 1 + shift))]
    return lambda u, v: (dark if v >= lo - 1 else col) if v < lo else wall_mat(u, v)


def _pos(pr, sp):
    return (pr["x"] if "x" in pr else pr.get("fx", 0) * sp["W"], pr["y"] if "y" in pr else pr.get("fy", 0) * sp["D"], pr.get("z", 0))


def _prop(c, v, S, pr, sp):
    R = S["ramps"]; x, y, z = _pos(pr, sp); k = pr.get("kind", "crate"); w = pr.get("w", 9)
    if k == "crate": box(c, v, x, y, z, w, w * 0.8, w * 0.9, MATERIALS["planks"], R["crate"], (1, -1, 1))
    elif k == "barrel": sx, sy = v.P(x, y, z); P.barrel(c, S, sx, sy, int(pr.get("w", 10)), int(pr.get("h", 14)))
    elif k == "sack": sx, sy = v.P(x, y, z); P.sack(c, S, sx, sy, pr.get("s", 1.0))
    else: raise ValueError(f"unknown prop kind {k!r}; choose crate, barrel or sack")


def _ridge(c, v, S, sp, t):
    """long wall in front, ridge along x: iso shows front wall + gable end + roof slope, top shows front wall + both slopes"""
    R = S["ramps"]; W, D, fh, fl = sp["W"], sp["D"], sp["fh"], sp["floors"]; Hh = fl * fh; pitch = sp["pitch"]; ox = oy = sp["overhang"]; kind = sp["roof"]
    Rise = pitch * D / 2 if kind != "flat" else 0; n = math.hypot(1, pitch); cs, sn = 1 / n, pitch / n; zE = Hh - pitch * oy; T = R["trim"]
    wm, rm = MATERIALS[sp["wall"]], MATERIALS[sp["roof_mat"]]; WR = ramp_of(S, sp["wall"], "wall"); RR = ramp_of(S, sp["roof_mat"], "roof"); marks = {}
    if sp["open_front"]:
        face3(c, v, (0, 0, 0), (1, 0, 0), (0, 1, 0), [(0, 0), (W, 0), (W, D), (0, D)], MATERIALS["planks"], R["wood"], -1)
        face3(c, v, (0, D, 0), (1, 0, 0), (0, 0, 1), [(0, 0), (W, 0), (W, Hh), (0, Hh)], wm, R["interior"], 1)
    if v.right:
        poly = [(0, 0), (D, 0), (D, Hh), (D / 2, Hh + Rise), (0, Hh)] if kind == "gable" else [(0, 0), (D, 0), (D, Hh), (0, Hh)]
        ov = [] if sp["open_front"] else _openings(S, sp, (0.3, 0.7))
        face3(c, v, (W, 0, 0), (0, 1, 0), (0, 0, 1), poly, _plinth(sp, S, wm, WR, -1), WR, lambda u, w: -1 - int(w > Hh - 3) - int(w < 2), ov)
    if not sp["open_front"]:
        face3(c, v, (0, 0, 0), (1, 0, 0), (0, 0, 1), [(0, 0), (W, 0), (W, Hh), (0, Hh)], _plinth(sp, S, wm, WR, 1), WR, lambda u, w: 1 - int(w > Hh - 3), _openings(S, sp))
    for pr in sp["props"]:
        if _pos(pr, sp)[1] >= 0: _prop(c, v, S, pr, sp)
    if sp["open_front"]:
        for x in (-1, W - 3): box(c, v, x, -1, 0, 4, 3, Hh, MATERIALS["planks"], R["wood"], (1, -1, 1))
    Lw = (D / 2 + oy) / cs
    if kind in ("gable", "hip"):
        top_l, top_r = (0, W + 2 * ox) if kind == "gable" else (D / 2 + ox, W - D / 2 + ox)
        sh = lambda u, w: -int(w < 3) + int(w > Lw - 4)                      # shadow under the eave, catch-light along the ridge
        face3(c, v, (-ox, -oy, zE), (1, 0, 0), (0, cs, sn), [(0, 0), (W + 2 * ox, 0), (top_r, Lw), (top_l, Lw)], rm, RR, sh)
        if v.back: face3(c, v, (-ox, D + oy, zE), (1, 0, 0), (0, -cs, sn), [(0, 0), (W + 2 * ox, 0), (top_r, Lw), (top_l, Lw)], rm, RR, -1)
        if kind == "hip":
            Lw2 = (D / 2 + ox) / cs
            if v.right or v.back: face3(c, v, (W + ox, -oy, zE), (0, 1, 0), (-cs, 0, sn), [(0, 0), (D + 2 * oy, 0), (D / 2 + oy, Lw2)], rm, RR, -1)
            if v.back: face3(c, v, (-ox, -oy, zE), (0, 1, 0), (cs, 0, sn), [(0, 0), (D + 2 * oy, 0), (D / 2 + oy, Lw2)], rm, RR, -1)
        beam(c, v, (-ox, -oy, zE), (W + ox, -oy, zE), [T[5], T[3], T[1]])
        if kind == "gable":
            beam(c, v, (-ox, D / 2, Hh + Rise), (W + ox, D / 2, Hh + Rise), [T[5], T[2]])
            if v.right:
                apex = (W + ox * 0.3, D / 2, Hh + Rise)
                beam(c, v, (W + ox, -oy, zE), apex, [T[5], T[3], T[1]], off=(1, 0)); beam(c, v, apex, (W, D, Hh), [T[4], T[2]], off=(1, 0))
        elif v.right:
            beam(c, v, (W + ox, -oy, zE), (W - D / 2, D / 2, Hh + Rise), [T[5], T[3]], off=(1, 0)); beam(c, v, (W + ox, -oy, zE), (W + ox, D + oy, zE), [T[4], T[2]], off=(1, 0))
        marks["apex"] = v.P(W / 2, D / 2, Hh + Rise)
    else:                                                         # flat roof: deck, parapet, merlons
        face3(c, v, (0, 0, Hh), (1, 0, 0), (0, 1, 0), [(0, 0), (W, 0), (W, D), (0, D)], rm, RR, 0)
        box(c, v, 0, 0, Hh, W, 2, 3, MATERIALS["plain"], WR, (1, -1, 1)); box(c, v, W - 2, 0, Hh, 2, D, 3, MATERIALS["plain"], WR, (1, -1, 1))
        if v.back: box(c, v, 0, D - 2, Hh, W, 2, 3, MATERIALS["plain"], WR, (0, -1, 1))
        if sp["battlements"]:
            for x in range(0, int(W) - 4, 8): box(c, v, x, 0, Hh + 3, 5, 2, 4, MATERIALS["stone"], WR, (1, -1, 1))
            for y in range(0, int(D) - 4, 8): box(c, v, W - 2, y, Hh + 3, 2, 5, 4, MATERIALS["stone"], WR, (1, -1, 1))
        marks["apex"] = v.P(W * 0.12, D * 0.45, Hh + 3)
    if v.right: beam(c, v, (W, 0, 0), (W, 0, Hh), [S["seam"]])
    if sp["dormers"]: X.dormers(c, v, S, sp, zE)
    if sp["wing"]: X.wing(c, v, S, sp, zE, _plinth)
    if sp["chimney"] and kind == "gable":
        cw = min(sp.get("chimney_w", 7), W / 4); xc, yc = W * sp.get("chimney_fx", 0.72), D * sp.get("chimney_fy", 0.22); z0 = zE + pitch * (yc + oy) - 1; z1 = Hh + Rise + 7
        box(c, v, xc, yc, z0, cw, cw * 0.85, z1 - z0, MATERIALS["stone"], R["stone"], (0, -1, 1)); marks["chimney"] = v.P(xc + cw / 2, yc + cw * 0.4, z1)
    if sp["awning"]:
        if sp["open_front"]: x0, wa, zt, zb, ay = -1, W + 2, Hh - 2, Hh - 9, 7
        else: nw, ww, wh, dw, dh, wy = _dims(sp); x0, wa, zt, zb, ay = W / nw / 2 - dw / 2 - 2, dw + 4, dh + 2, dh - 3, 6
        L = math.hypot(ay, zt - zb)
        face3(c, v, (x0, 0, zt), (1, 0, 0), (0, -ay / L, (zb - zt) / L), [(0, 0), (wa, 0), (wa, L), (0, L)], P.awning(S, t, L), R["awning_a"], 0)
        lp = v.P(x0 + wa * 0.62, -ay, zb); marks["lantern"] = (lp[0], lp[1] + 3)
    for pr in sp["props"]:
        if _pos(pr, sp)[1] < 0: _prop(c, v, S, pr, sp)
    return marks


def _side(c, v, S, sp, t):
    """gable end towards the viewer (platformer view): wall + roof slabs / hip trapezoid / flat roof"""
    R = S["ramps"]; W, fh, fl = sp["W"], sp["fh"], sp["floors"]; Hh = fl * fh; pitch = sp["pitch"]; ox = sp["overhang"]; kind = sp["roof"]; T = R["trim"]
    wm, rm = MATERIALS[sp["wall"]], MATERIALS[sp["roof_mat"]]; WR = ramp_of(S, sp["wall"], "wall"); RR = ramp_of(S, sp["roof_mat"], "roof"); marks = {}
    Rise = pitch * W / 2 if kind != "flat" else 0; as_roof = kind == "gable" and sp["side_gable"] == "roof"
    poly = [(0, 0), (W, 0), (W, Hh), (W / 2, Hh + Rise), (0, Hh)] if (kind == "gable" and not as_roof) else [(0, 0), (W, 0), (W, Hh), (0, Hh)]
    face3(c, v, (0, 0, 0), (1, 0, 0), (0, 0, 1), poly, _plinth(sp, S, wm, WR, 1), R["interior"] if sp["open_front"] else WR, lambda u, w: 1 - int(w > Hh - 3), [] if sp["open_front"] else _openings(S, sp))
    for x in (0, W - 2): face3(c, v, (x, 0, 0), (1, 0, 0), (0, 0, 1), [(0, 0), (2, 0), (2, Hh), (0, Hh)], lambda u, w: 2, T, 1 if x == 0 else 0)     # corner pilasters
    for pr in sp["props"]: _prop(c, v, S, pr, sp)
    if sp["open_front"]:
        for x in (-1, W - 3): box(c, v, x, 0, 0, 4, 2, Hh, MATERIALS["planks"], R["wood"], (1, -1, 1))
    if kind == "gable" and as_roof:
        z0 = Hh - pitch * ox
        face3(c, v, (0, 0, 0), (1, 0, 0), (0, 0, 1), [(-ox, z0), (W + ox, z0), (W / 2, Hh + Rise)], rm, RR, lambda u, w: -int(w < z0 + 3) + int(w > Hh + Rise - 5))
        beam(c, v, (-ox, 0, z0), (W / 2, 0, Hh + Rise), [T[5]]); beam(c, v, (W + ox, 0, z0), (W / 2, 0, Hh + Rise), [T[3]])
        beam(c, v, (-ox, 0, z0), (W + ox, 0, z0), [T[3], T[1]])
        marks["apex"] = v.P(W / 2, 0, Hh + Rise)
    elif kind == "gable":
        for sgn in (1, -1):
            x0, x1 = (-ox, W / 2) if sgn == 1 else (W + ox, W / 2); z0 = Hh - pitch * ox
            face3(c, v, (0, 0, 0), (1, 0, 0), (0, 0, 1), [(x0, z0), (x1, Hh + Rise), (x1, Hh + Rise - 4), (x0, z0 - 4)], rm, RR, 1 if sgn == 1 else 0)
            beam(c, v, (x0, 0, z0), (x1, 0, Hh + Rise), [T[5]]); beam(c, v, (x0, 0, z0 - 4), (x1, 0, Hh + Rise - 4), [T[1]])
        marks["apex"] = v.P(W / 2, 0, Hh + Rise)
    elif kind == "hip":
        face3(c, v, (0, 0, 0), (1, 0, 0), (0, 0, 1), [(-ox, Hh - 1), (W + ox, Hh - 1), (W * 0.7, Hh + Rise), (W * 0.3, Hh + Rise)], rm, RR, 0)
        beam(c, v, (-ox, 0, Hh - 1), (W + ox, 0, Hh - 1), [T[5], T[2]]); marks["apex"] = v.P(W / 2, 0, Hh + Rise)
    else:
        box(c, v, -1, 0, Hh, W + 2, 2, 3, MATERIALS["plain"], WR, (1, -1, 1)); marks["apex"] = v.P(W * 0.12, 0, Hh + 3)
        if sp["battlements"]:
            for x in range(0, int(W) - 4, 8): box(c, v, x, 0, Hh + 3, 5, 2, 4, MATERIALS["stone"], WR, (1, -1, 1))
    if sp["chimney"] and kind == "gable":
        cw = min(sp.get("chimney_w", 7), W / 4); xc = W * sp.get("chimney_fx", 0.72); z1 = Hh + Rise * (1 - (xc - W / 2) / (W / 2)) + 6
        box(c, v, xc, 0, Hh, cw, 2, z1 - Hh, MATERIALS["stone"], R["stone"], (0, -1, 1)); marks["chimney"] = v.P(xc + cw / 2, 0, z1)
    if sp["awning"]:
        if sp["open_front"]: x0, wa, zt = -1, W + 2, Hh - 2
        else: nw, ww, wh, dw, dh, wy = _dims(sp); x0, wa, zt = W / nw / 2 - dw / 2 - 2, dw + 4, dh + 2
        face3(c, v, (x0, 0, zt), (1, 0, 0), (0, 0, -1), [(0, 0), (wa, 0), (wa, 4), (0, 4)], P.awning(S, t, 4), R["awning_a"], 0)
        marks["lantern"] = (v.P(x0 + wa * 0.62, 0, zt - 4)[0], v.P(x0, 0, zt - 4)[1] + 3)
    return marks


def _extent(sp):
    """projected bounding box of everything that can be drawn (generous), used for the canvas and the origin"""
    v = View(sp["proj"], (0, 0)); W, D = sp["W"], sp["D"]; Hh = sp["floors"] * sp["fh"]; Rise = sp["pitch"] * (W if sp["proj"] == "side" else D) / 2; o = sp["overhang"] + 3
    ys = [-o - 14 - (sp["wing_l"] if sp.get("wing") else 0)] + [_pos(p, sp)[1] for p in sp["props"]]; xs = [-o - 14] + [_pos(p, sp)[0] for p in sp["props"]]
    pts = [v.V(x, y, z) for x in (min(xs), 0, W + o, max(xs + [W + o])) for y in (min(ys), 0, D + o) for z in (0, Hh + Rise + 28)]
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


def scene(spec, S, t=0.0, size=None):
    """one RGBA frame of the scene at animation phase t; the canvas follows the projected size unless `size` is given"""
    t = round(t % 1, 9)                                           # phase 1.0 == phase 0.0 exactly (loops)
    sp = spec_of(spec); x0, y0, x1, y1 = _extent(sp); m = 12
    size = size or (int(x1 - x0) + 2 * m, int(y1 - y0) + 2 * m); v = View(sp["proj"], (m - x0, m - y0)); c = Cv(*size)
    marks = (X.round_building(c, v, S, sp, _plinth) if sp["round"] else (_side if sp["proj"] == "side" else _ridge)(c, v, S, sp, t))
    c.tidy()
    if sp["lantern"] and "lantern" in marks: P.lantern(c, S, marks["lantern"][0], marks["lantern"][1], t)
    c.ring(S["outline"])
    if sp["smoke"] and "chimney" in marks: P.smoke(c, S, marks["chimney"][0], marks["chimney"][1] - 1, t)
    if sp["flag"] and "apex" in marks: P.flag(c, S, marks["apex"][0], marks["apex"][1] - 11, t)
    im = c.img()
    if sp["ground"]: im = Image.alpha_composite(_ground(sp, S, v, size), im)         # footprint shadow under the building (after the outline, so it has none)
    return snap(im, S["palette"]) if S["palette"] else im


def _ground(sp, S, v, size):
    """soft footprint shadow: a flat solid patch under the building, a little longer to the right (light from the left)"""
    g = Cv(*size); col = S["ramps"]["ground"][1]; W, D = sp["W"], sp["D"]
    if sp["round"]: X.round_ground(sp, v, g, col); return g.img()
    if sp["proj"] == "side": pts = [v.P(-3, 0, 0), v.P(W + 7, 0, 0), v.P(W + 5, 0, -2), v.P(-1, 0, -2)]
    elif sp["proj"] == "top": pts = [v.P(-2.5, -4, 0), v.P(W + 4, -4, 0), v.P(W + 4, 3, 0), v.P(-2.5, 3, 0)]            # seen from above only the front strip peeks out
    else: pts = [v.P(-2.5, -3, 0), v.P(W + 7, -3, 0), v.P(W + 7, D + 3, 0), v.P(-2.5, D + 3, 0)]
    g.plane(pts, lambda x, y: col); return g.img()


def render(spec, style, frames=1, size=None, pad=2):
    """list of cropped RGBA frames (same crop for all frames so the animation does not jump)"""
    S = load_style(style); ims = [scene(spec, S, i / frames, size) for i in range(frames)]
    bb = [im.getbbox() for im in ims]; x0 = min(b[0] for b in bb) - pad; y0 = min(b[1] for b in bb) - pad; x1 = max(b[2] for b in bb) + pad; y1 = max(b[3] for b in bb) + pad
    return [im.crop((x0, y0, x1, y1)) for im in ims]
