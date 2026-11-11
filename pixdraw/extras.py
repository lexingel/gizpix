# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixdraw.extras - the parts that make a plan more than one box: dormers on a gable roof, a wing (L-shaped plan) and round towers with a cone or flat roof.
All take the same (canvas, view, style, spec) as the main builders; templates.py calls them."""
import math
from .core import face3, beam, PROJECTIONS
from .materials import MATERIALS, ramp_of
from . import parts as P


def dormers(c, v, S, sp, zE):
    """sp['dormers'] small shed-roofed dormer windows on the front slope of a gable roof (iso and top)"""
    n = int(sp["dormers"]); W, D, pitch, oy = sp["W"], sp["D"], sp["pitch"], sp["overhang"]; R = S["ramps"]; T = R["trim"]
    wm, WR, RR, rm = MATERIALS[sp["wall"]], ramp_of(S, sp["wall"], "wall"), ramp_of(S, sp["roof_mat"], "roof"), MATERIALS[sp["roof_mat"]]
    w = min(10.0, W / (n * 1.6)); hd = 9.0; dd = 5.0; s = 0.22; ls = math.hypot(1, s); cs2, sn2 = 1 / ls, s / ls; yd = D * 0.16
    lo = sp.get("wing_w", 0) + 4 if sp.get("wing") else 0                      # keep clear of a wing on the left
    for i in range(n):
        xd = lo + (W - lo) * (i + 0.5) / n - w / 2
        if sp["chimney"] and abs(xd + w / 2 - (W * sp.get("chimney_fx", 0.72) + sp.get("chimney_w", 7) / 2)) < w / 2 + sp.get("chimney_w", 7) / 2 + 3: xd -= w + 8      # not on the chimney
        if xd < lo + 2: continue
        z0 = zE + pitch * (yd + oy)
        if v.right: face3(c, v, (xd + w, yd, z0), (0, 1, 0), (0, 0, 1), [(0, 0), (dd, pitch * dd), (dd, hd + s * dd), (0, hd)], wm, WR, -1)               # cheek
        face3(c, v, (xd, yd, z0), (1, 0, 0), (0, 0, 1), [(0, 0), (w, 0), (w, hd), (0, hd)], wm, WR, 1, [(2, 1.5, w - 2, hd - 1.2, P.window(S, lit=sp["lit"] and i % 2 == 0))])
        L = (dd + 1.2) / cs2
        face3(c, v, (xd - 1.5, yd - 1.2, z0 + hd), (1, 0, 0), (0, cs2, sn2), [(0, 0), (w + 3, 0), (w + 3, L), (0, L)], rm, RR, lambda u, q: -int(q < 1.5) + int(q > L - 1.5))
        beam(c, v, (xd - 1.5, yd - 1.2, z0 + hd), (xd + w + 1.5, yd - 1.2, z0 + hd), [T[4], T[2]])


def wing(c, v, S, sp, zE, plinth):
    """an L-shaped plan: a gabled wing on the left end of the front, ridge across the main ridge (its front is a gable wall with the door). Needs a gable main roof."""
    R = S["ramps"]; T = R["trim"]; W, D, fh, fl, pitch, ox = sp["W"], sp["D"], sp["fh"], sp["floors"], sp["pitch"], sp["overhang"]; Hh = fl * fh
    Ww, L = sp["wing_w"], sp["wing_l"]; Rw = pitch * Ww / 2; n = math.hypot(1, pitch); cs, sn = 1 / n, pitch / n; Lw = (Ww / 2 + ox) / cs; xc = Ww / 2
    wm, WR, RR, rm = MATERIALS[sp["wall"]], ramp_of(S, sp["wall"], "wall"), ramp_of(S, sp["roof_mat"], "roof"), MATERIALS[sp["roof_mat"]]
    ov = []
    for i in range(fl):
        if i == 0 and sp["door"]: dw, dh = 9, min(15, fh * 0.85); ov.append((xc - dw / 2, 0, xc + dw / 2, dh, P.door(S)))
        else: ov.append((xc - 4, i * fh + (fh - 8) * 0.55, xc + 4, i * fh + (fh - 8) * 0.55 + 8, P.window(S, lit=(i > 0 and sp["lit"]))))
    if v.right: face3(c, v, (Ww, -L, 0), (0, 1, 0), (0, 0, 1), [(0, 0), (L, 0), (L, Hh), (0, Hh)], plinth(sp, S, wm, WR, -1), WR, lambda u, q: -1 - int(q > Hh - 3) - int(q < 2),
                      [(L * 0.45 - 4, (fh - 8) * 0.55 + i * fh, L * 0.45 + 4, (fh - 8) * 0.55 + i * fh + 8, P.window(S, lit=(i > 0 and sp["lit"]))) for i in range(fl)])
    face3(c, v, (0, -L, 0), (1, 0, 0), (0, 0, 1), [(0, 0), (Ww, 0), (Ww, Hh), (xc, Hh + Rw), (0, Hh)], plinth(sp, S, wm, WR, 1), WR, lambda u, q: 1 - int(q > Hh - 3), ov)
    zr = zE + pitch * (Ww / 2 + ox)                                              # wing ridge height; it meets the main roof at y = Ww/2 (the valley)
    lift = 1 if sp.get("proj") == "top" else 0                                      # from above the wing roof would melt into the main roof: one ramp step lighter
    ya, yb = L + ox + Ww / 2, L                                                  # u along y from the eave at the front: ridge end, and where the eave meets the main eave
    for side, (x0, dx, dirx) in enumerate(((Ww + ox, 1, -cs), (-ox, 0, cs))):    # right slope first, then the left one (visible in the top view)
        if side == 1 and not v.back: continue
        o3 = (x0, -L - ox, zE)
        face3(c, v, o3, (0, 1, 0), (dirx, 0, sn), [(0, 0), (0, Lw), (ya, Lw), (yb, 0)], rm, RR, lambda u, q: -int(q < 3) + int(q > Lw - 4) - (1 if side == 0 else 0) + lift)
    beam(c, v, (-ox, -L - ox, zE), (xc, -L - ox, zE + pitch * (Ww / 2 + ox)), [T[5], T[3]]); beam(c, v, (Ww + ox, -L - ox, zE), (xc, -L - ox, zE + pitch * (Ww / 2 + ox)), [T[4], T[2]], off=(1, 0))
    beam(c, v, (xc, -L - ox, zr), (xc, Ww / 2, zr), [T[5], T[2]]); beam(c, v, (Ww + ox, -ox, zE), (xc, Ww / 2, zr), [T[3], T[1]], off=(1, 0))      # ridge and valley


def _normal_shift(sn):
    return 1 if sn < -0.5 else 0 if sn < 0.1 else -1 if sn < 0.9 else -2


def _visible(v):
    """world vector from the building towards the viewer: the null vector of the projection"""
    a = (v.EX[0], v.EY[0], v.EZ[0]); b = (v.EX[1], v.EY[1], v.EZ[1])
    d = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
    return d if d[1] < 0 or (d[1] == 0 and d[2] > 0) else tuple(-q for q in d)


def round_building(c, v, S, sp, plinth):
    """a round tower: cylinder wall (the wall material wrapped round it), windows and a door, and a cone or flat roof. W is the diameter."""
    R = S["ramps"]; W, fh, fl, pitch, ov = sp["W"], sp["fh"], sp["floors"], sp["pitch"], sp["overhang"]; Hh = fl * fh; r = W / 2; cx = cy = r; T = R["trim"]
    wm, WR, RR, rm = MATERIALS[sp["wall"]], ramp_of(S, sp["wall"], "wall"), ramp_of(S, sp["roof_mat"], "roof"), MATERIALS[sp["roof_mat"]]; mat = plinth(sp, S, wm, WR, 0); marks = {}
    d = _visible(v); wins = []
    for i in range(fl):
        if i == 0 and sp["door"]: wins.append((0.0, 9.0, 0.0, min(15.0, fh * 0.85), P.door(S)))
        else:
            for ph in (-0.62, 0.62): wins.append((ph * r, 6.0, i * fh + (fh - 8) * 0.55, i * fh + (fh - 8) * 0.55 + 8, P.window(S, lit=(i > 0 and sp["lit"] and ph > 0))))

    def put(x, y, z, col): sx, sy = v.P(x, y, z); c.px(sx, sy, col)
    steps = int(2 * math.pi / 0.012)
    for si in range(steps + 1):
        phi = -math.pi + si * 0.012; nx, ny = math.sin(phi), -math.cos(phi)
        if nx * d[0] + ny * d[1] <= 0.02: continue
        sh = _normal_shift(nx); u0 = phi * r; z = 0.0
        while z <= Hh:
            col = None
            for wc, ww, z0, z1, fn in wins:
                if abs(u0 - wc) < ww / 2 and z0 <= z < z1: col = fn(u0 - (wc - ww / 2), z - z0, ww, z1 - z0, sh); break
            if col is None:
                kk = mat(u0, z); col = kk if (kk is None or isinstance(kk, tuple)) else WR[max(0, min(len(WR) - 1, 1 + kk + sh - int(z > Hh - 3)))]
            if col is not None: put(cx + r * nx, cy + r * ny, z, col)
            z += 0.45
    if sp["roof"] == "cone":
        ro = r + ov; Rise = max(8.0, pitch * ro * 1.4); zE = Hh - 1.0; ca = ro / math.hypot(ro, Rise + 1.0); sa = (Rise + 1.0) / math.hypot(ro, Rise + 1.0); slant = math.hypot(ro, Rise + 1.0)
        for si in range(steps + 1):
            phi = -math.pi + si * 0.012; nx, ny = math.sin(phi), -math.cos(phi)
            if nx * ca * d[0] + ny * ca * d[1] + sa * d[2] <= 0.02: continue
            sh = _normal_shift(nx); tt = 0.0
            while tt <= 1.0:
                rad = ro * (1 - tt); z = zE + tt * (Rise + 1.0); uu = phi * ro * (1 - tt * 0.6); vv = tt * slant
                kk = rm(uu, vv); col = kk if (kk is None or isinstance(kk, tuple)) else RR[max(0, min(len(RR) - 1, 1 + kk + sh - int(tt < 0.07) + int(tt > 0.88)))]
                if col is not None: put(cx + rad * nx, cy + rad * ny, z, col)
                tt += 0.006
        marks["apex"] = v.P(cx, cy, zE + Rise + 1.0)
    else:                                                         # flat roof: a parapet ring round the front of the deck, then the deck disc
        for si in range(steps + 1):
            phi = -math.pi + si * 0.012; nx, ny = math.sin(phi), -math.cos(phi)
            if nx * d[0] + ny * d[1] > 0.02:
                z = Hh
                while z < Hh + 3: put(cx + r * nx, cy + r * ny, z, WR[max(0, min(len(WR) - 1, _normal_shift(nx) + (1 if z > Hh + 1.6 else 0)))]); z += 0.45
        rr = r - 1.5
        for a in range(-int(rr * 2), int(rr * 2) + 1):
            for b in range(-int(rr * 2), int(rr * 2) + 1):
                px, py = a / 2, b / 2
                if px * px + py * py <= rr * rr:
                    kk = rm(px * 2, py * 2); put(cx + px, cy + py, Hh + 3, kk if isinstance(kk, tuple) else RR[max(0, min(len(RR) - 1, 1 + (kk or 0)))])
        marks["apex"] = v.P(cx - r * 0.3, cy, Hh + 3)
    return marks


def round_ground(sp, v, g, col):
    r = sp["W"] / 2; import math as m
    pts = [v.P(r + (r + 4) * m.cos(a / 20 * m.pi), r + (r + 4) * m.sin(a / 20 * m.pi) - 1, 0) for a in range(40)]; g.plane(pts, lambda x, y: col)
