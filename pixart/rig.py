# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixart.rig - skeletons and poses, so a figure is described by joint angles instead of pixel coordinates.

  rig = humanoid(height=40, heads=4)                 # or quadruped(...), or Rig({...}) of your own
  rig.add("weapon", "arm_f_lo", 16)                  # a bone on the near hand
  j = rig.solve(pose, root_x=24, ground=44)          # name -> ((x0, y0), (x1, y1)); the lowest foot stands on `ground`, so the body bobs by itself
  mannequin(c, rig, j, skin, top, bottom)            # a plain figure to dress up; or paint your own parts with c.limb(*j["arm_f_up"], 4, 3)
  pose = pose_at(KEYS, t)                            # KEYS = [(time 0..1, pose, ease)], interpolated; loop=True wraps

ANGLES (degrees) are absolute, the same for every bone: 0 = hanging straight down, 90 = pointing forward (the way the figure faces), 180 = straight up,
-90 = pointing backward. An upright spine is 180, leaning forward 165. Bones not named in a pose keep the rig's rest angle. facing = 1 looks right, -1 left.
Names ending _b are the far (back) limbs: paint them first and one tone darker; _f are the near ones."""
import math

DIRS = {"E": 0, "SE": 45, "S": 90, "SW": 135, "W": 180, "NW": 225, "N": 270, "NE": 315}      # the way the figure faces; S = toward the viewer


class Joints(dict):
    """solved joints; with a direction also .order (bone names far -> near: paint in this order), .depth (per bone, + = nearer the viewer), .dir (degrees)"""
    order = (); depth = {}; dir = None


EASES = {"linear": lambda t: t, "in": lambda t: t * t, "out": lambda t: 1 - (1 - t) ** 2, "inout": lambda t: t * t * (3 - 2 * t), "hold": lambda t: 0.0, "snap": lambda t: 1 - (1 - t) ** 4}


class Rig:
    """bones = {name: (parent or None, length, rest angle, at)}; `at` = where on the parent it starts (0 = the parent's start, 1 = its end)"""
    def __init__(s, bones, facing=1): s.bones = dict(bones); s.facing = facing; s.lat = {}      # lat = sideways offset of a bone from the body's middle plane (+ = the figure's right)

    def side(s, bone):
        while bone is not None:
            if bone in s.lat: return s.lat[bone]
            bone = s.bones[bone][0]
        return 0.0

    def add(s, name, parent, length, angle=0, at=1.0, back=0):
        """back = how far the bone also reaches BEHIND its start point (a staff or spear held in the middle: add("weapon", "arm_f_lo", 20, back=12)); c.limb(*j[name]) then draws the whole shaft"""
        s.bones[name] = (parent, length, angle, at); s.back = getattr(s, "back", {}); s.back[name] = back; return s

    def _solve_dir(s, pose, root_x, root_y, ground, feet, deg, tilt):
        f0 = s.facing; s.facing = 1
        try: flat = s.solve(pose, 0, 0, None, feet)                    # (forward, down) in the figure's own side plane
        finally: s.facing = f0
        c, sn = math.cos(math.radians(deg)), math.sin(math.radians(deg)); out = Joints(); depth = {}
        for k, (a, b) in flat.items():
            l = s.side(k); pts = []; zs = []
            for f, d in (a, b): z = f * sn + l * c; pts.append((root_x + f * c - l * sn, root_y + d + z * tilt)); zs.append(z)
            out[k] = tuple(pts); depth[k] = sum(zs) / 2
        feet = feet or [k for k in s.bones if k.startswith(("leg", "foot"))]
        if ground is not None:
            low = max((out[f][1][1] for f in feet if f in out), default=None)
            if low is not None:
                sh = ground - low
                for k, (a, b) in list(out.items()): out[k] = ((a[0], a[1] + sh), (b[0], b[1] + sh))
        order = sorted(out, key=lambda k: depth[k])
        for k in list(order):                                         # a bone on the body's middle plane never hides behind its own parent (the head always sits on top of the spine)
            p = s.bones[k][0]
            if p in order and s.side(k) == 0 and order.index(k) < order.index(p): order.remove(k); order.insert(order.index(p) + 1, k)
        out.depth = depth; out.dir = deg; out.order = order; return out

    def chain(s, name, parent, n, length, angle=0, curl=0, at=1.0):
        """n bones name_0 .. name_{n-1} end to end (necks, tails, wing fingers, tentacles): total `length`, first at `angle`, each next one turned by `curl` more
        (curl alternating in sign across two chains makes an S). Returns the bone names, for Canvas.chain and turn()."""
        names = [f"{name}_{i}" for i in range(n)]
        for i, nm in enumerate(names): s.add(nm, parent if i == 0 else names[i - 1], length / n, angle + curl * i, at if i == 0 else 1.0)
        return names

    def children(s, bone):
        out = [bone]
        for k, v in s.bones.items():
            if v[0] in out and k not in out: out.append(k)
        return out

    def turn(s, pose, bone, delta):
        """a copy of `pose` with `bone` AND everything attached to it rotated by `delta` degrees (flap a whole wing, swing a whole arm, wag a tail)"""
        q = dict(pose or {})
        for k in s.children(bone): q[k] = q.get(k, s.bones[k][2]) + delta
        return q

    def rest(s): return {k: v[2] for k, v in s.bones.items()}

    def solve(s, pose=None, root_x=0, root_y=0, ground=None, feet=None, direction=None, tilt=0.45):
        """name -> ((x0, y0), (x1, y1)). ground = the y the lowest foot stands on; feet = the bones that count as feet (default: every bone whose name starts with leg or foot).
        direction = None: plain side view (uses rig.facing). direction = "S" / "NE" / degrees (E 0, S 90, W 180, N 270): the SAME pose turned to face that way in a top-down
        3/4 view; `tilt` = how much ground depth shows as screen height (0 = flat side-on camera, 0.45 = usual RPG view). The result then has .order (paint far -> near) and .depth."""
        if direction is not None: return s._solve_dir(pose, root_x, root_y, ground, feet, DIRS[direction] if isinstance(direction, str) else direction, tilt)
        feet = feet or [k for k in s.bones if k.startswith(("leg", "foot"))]
        pose = pose or {}; out = {}; dx, dy = pose.get("root", (0, 0))
        def get(name):
            if name in out: return out[name]
            parent, length, rest, at = s.bones[name]; a = math.radians(pose.get(name, rest))
            if parent is None: p0 = (root_x + dx * s.facing, root_y + dy)
            else: (ax, ay), (bx, by) = get(parent); p0 = (ax + (bx - ax) * at, ay + (by - ay) * at)
            out[name] = (p0, (p0[0] + math.sin(a) * length * s.facing, p0[1] + math.cos(a) * length)); return out[name]
        back = getattr(s, "back", {})
        for k in s.bones: get(k)
        for k, bk in back.items():                                    # shafts held in the middle: move the start point back along the bone (children still hang from the far end)
            if bk and k in out: (ax, ay), (bx, by) = out[k]; L = max(math.hypot(bx - ax, by - ay), 1e-6); out[k] = ((ax - (bx - ax) / L * bk, ay - (by - ay) / L * bk), (bx, by))
        if ground is not None:
            low = max((out[f][1][1] for f in feet if f in out), default=None)
            if low is not None: sh = ground - low; out = {k: ((a[0], a[1] + sh), (b[0], b[1] + sh)) for k, (a, b) in out.items()}
        return out


def humanoid(height=40, heads=4, facing=1):
    """side-view person `height` px tall and `heads` heads tall (2-3 chibi, 4-5 game hero, 7 realistic). Bones: spine head arm_{f,b}_{up,lo} leg_{f,b}_{up,lo} foot_{f,b}"""
    hd = height / heads; rest = height - hd; torso = rest * 0.45; leg = rest * 0.55; arm = torso * 1.05
    r = Rig({"spine": (None, torso, 180, 0), "head": ("spine", hd, 180, 1.0)}, facing)
    for side in ("b", "f"):
        r.add(f"arm_{side}_up", "spine", arm * 0.5, 5, 0.88); r.add(f"arm_{side}_lo", f"arm_{side}_up", arm * 0.5, 15)
        r.add(f"leg_{side}_up", "spine", leg * 0.5, 4 if side == "f" else -4, 0.0); r.add(f"leg_{side}_lo", f"leg_{side}_up", leg * 0.5, 0); r.add(f"foot_{side}", f"leg_{side}_lo", max(2, hd * 0.3), 90)
    r.size = {"head": hd, "torso": max(3, height / 5.5), "limb": max(2, height / 11), "height": height}
    sh, hp = r.size["torso"] * 1.0, r.size["torso"] * 0.42                                         # shoulder and hip half-widths: _f = the figure's right side (weapon hand), _b = its left (shield arm)
    r.lat = {"arm_f_up": sh, "arm_b_up": -sh, "leg_f_up": hp, "leg_b_up": -hp}; return r


def quadruped(length=30, height=22, facing=1, neck=None, tail=None):
    """side-view four-legged animal: body `length` long, `height` at the shoulder. Bones: body (hip -> shoulder) neck head tail leg_{f,h}{f,b}_{up,lo}
    (f = front pair, h = hind pair; second letter f = near side, b = far side). Cat: long tail, short neck; horse: long neck and legs; wolf: in between."""
    leg = height * 0.55; neck = length * 0.3 if neck is None else neck; tail = length * 0.6 if tail is None else tail
    r = Rig({"body": (None, length * 0.6, 92, 0), "neck": ("body", neck, 140, 1.0), "head": ("neck", length * 0.3, 80, 1.0), "tail": ("body", tail, -120, 0.0)}, facing)
    for side in ("b", "f"):
        o = -9 if side == "b" else 5                                                              # the far pair stands a little behind the near pair, so all four legs show
        r.add(f"leg_f{side}_up", "body", leg * 0.5, o, 0.95); r.add(f"leg_f{side}_lo", f"leg_f{side}_up", leg * 0.5, o - 8)
        r.add(f"leg_h{side}_up", "body", leg * 0.5, o + 10, 0.0); r.add(f"leg_h{side}_lo", f"leg_h{side}_up", leg * 0.5, o - 17)
    r.size = {"body": max(4, height * 0.45), "limb": max(2, height / 9), "head": max(4, height * 0.38), "height": height}; return r


def _mix_angle(a, b, t): return a + ((b - a + 180) % 360 - 180) * t if abs(b - a) > 180 and False else a + (b - a) * t      # plain: 170 -> 190 goes over the top, write 190 not -170


def lerp_pose(a, b, t):
    out = {}
    for k in set(a) | set(b):
        if k == "root": (ax, ay), (bx, by) = a.get(k, (0, 0)), b.get(k, (0, 0)); out[k] = (ax + (bx - ax) * t, ay + (by - ay) * t)
        elif k in a and k in b: out[k] = _mix_angle(a[k], b[k], t)
        else: out[k] = a.get(k, b.get(k))
    return out


def pose_at(keys, t, loop=False):
    """keys = [(time, pose)] or [(time, pose, ease into this key)], times rising in 0..1. ease: linear in out inout snap hold (hold = stay on the previous key, then cut).
    loop=True also blends from the last key back to the first across t = 1."""
    ks = [(k[0], k[1], k[2] if len(k) > 2 else "inout") for k in keys]
    if loop: ks = ks + [(ks[0][0] + 1.0, ks[0][1], ks[0][2])]; t = t % 1.0
    if t <= ks[0][0]: return dict(ks[0][1])
    for (t0, p0, _), (t1, p1, e) in zip(ks, ks[1:]):
        if t <= t1: return lerp_pose(p0, p1, EASES[e]((t - t0) / max(t1 - t0, 1e-9)))
    return dict(ks[-1][1])


def far(j, dx=-2, dy=-1, only=None):
    """the same joints moved by (dx, dy): the far-side twin of a wing, arm or leg (paint it first and darker). only = a list of bone names"""
    return {k: ((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)) for k, (a, b) in j.items() if only is None or k in only}


def body_width(rig, j, front=1.9):
    """torso width in px for a direction-solved figure: the side-view width when facing E/W, `front` times that when facing S/N"""
    return rig.size["torso"] * (1 + (front - 1) * abs(math.sin(math.radians(j.dir or 0))))


def face_point(rig, j, fwd=0.22, lat=0.0, up=0.0):
    """a point on the head for a direction-solved figure: fwd / lat / up in head sizes from the head's centre (eyes: fwd 0.22, lat +-0.22; hair mass: fwd -0.18, up 0.12; top of the head: up 0.5). Returns (x, y, visible)"""
    (ax, ay), (bx, by) = j["head"]; hd = rig.size["head"]; a = math.radians(j.dir or 0); c, sn = math.cos(a), math.sin(a)
    f, l = fwd * hd, lat * hd; return ((ax + bx) / 2 + f * c - l * sn, (ay + by) / 2 - up * hd + (f * sn + l * c) * 0.3, f * sn + l * c > -0.12 * hd)


def mannequin8(c, rig, j, skin, top, bottom, shoes=None, eye=None, paint=None):
    """a plain person from direction-solved joints (rig.solve(pose, direction="SE", ...)): every bone painted in j.order (far -> near), parts on the far side one tone
    darker, torso widened toward the front and back views, eyes where the face shows. Returns {bone: mask}.
    paint = {bone: fn(c, j, bone)} draws your own things IN the depth order: extra bones (weapon, shield, cape) or a replacement for a standard bone;
    paint={"head+": fn} runs right after the head (hair, helmet, face details). That is what keeps sword and shield correctly in front or behind in every direction."""
    z = rig.size; w = z["limb"]; shoes = shoes or bottom; m = {}; tw = body_width(rig, j)
    paint = paint or {}
    for b in j.order:
        dark = j.depth[b] < -0.6 and b not in ("spine", "head")          # only limbs go dark on the far side, never the head or torso (a backward lean must not shade the face)
        if b in paint: m[b] = paint[b](c, j, b); continue
        if b == "spine":
            (ax, ay), (bx, by) = j[b]; cut = (tw - z["torso"]) / 2; L = max(math.hypot(bx - ax, by - ay), 1e-6); ux, uy = (bx - ax) / L, (by - ay) / L      # a wide torso must not grow taller: pull the round ends in
            m[b] = c.fill(c.limb((ax + ux * cut, ay + uy * cut), (bx - ux * cut, by - uy * cut), tw, tw * 0.92), top, form="tube", shadow=True)
        elif b == "head":
            m[b] = c.fill(head_mask(c, j[b], z["head"]), skin, form="ball", lo=1, shadow=True)
            if "head+" in paint: paint["head+"](c, j, b)
            for lat in (-0.22, 0.22):                                  # eyes last, so hair, hat brim or beard cannot bury them (2 px tall, at the head's centre row and the one below)
                x, y, vis = face_point(rig, j, 0.22, lat)
                if vis and eye is not None: c.px(int(x), int(y), eye, 0); c.px(int(x), int(y) + 1, eye, 0)
        elif b.startswith("arm"): m[b] = c.fill(c.limb(*j[b], w, w - 0.5), top if b.endswith("up") else skin, form="flat" if dark else "tube", shadow=not dark)
        elif b.startswith("leg"): m[b] = c.fill(c.limb(*j[b], w + 1, w), bottom, form="flat" if dark else "tube")
        elif b.startswith("foot"): m[b] = c.fill(c.limb(*j[b], w, w), shoes)
        else: continue
        if dark: c.retone(m[b], delta=-1)
    return m


def head_mask(c, bone, size, wide=1.0):
    """an oval head sitting on the head bone (centre = the bone's middle), `size` px tall and size * wide across"""
    (x0, y0), (x1, y1) = bone; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; w = size * wide
    return c.oval(int(round(cx - w / 2)), int(round(cy - size / 2)), int(round(w)), int(round(size)))


def mannequin(c, rig, j, skin, top, bottom, shoes=None, far=-1):
    """a plain side-view person from solved joints: far limbs first and one tone darker, then torso, head, near limbs. Returns {part: mask} so you can add hair, a face, armour.
    Paint a weapon yourself before or after the near arm, depending on which hand holds it."""
    z = rig.size; w = z["limb"]; shoes = shoes or bottom; m = {}
    def part(name, ramp, w0, w1, **kw): m[name] = c.fill(c.limb(*j[name], w0, w1), ramp, **kw); return m[name]
    for side in ("b", "f"):
        if side == "f": part("spine", top, z["torso"], z["torso"] * 0.9, form="tube", shadow=True); m["head"] = c.fill(head_mask(c, j["head"], z["head"]), skin, form="ball", lo=1, shadow=True)
        dark = side == "b"
        for leg in (f"leg_{side}_up", f"leg_{side}_lo"): part(leg, bottom, w + 1, w, form="flat" if dark else "tube");  dark and c.retone(m[leg], delta=far)
        part(f"foot_{side}", shoes, w, w); dark and c.retone(m[f"foot_{side}"], delta=far)
        if side == "b":
            for arm in ("arm_b_up", "arm_b_lo"): part(arm, top if arm.endswith("up") else skin, w, w - 0.5); c.retone(m[arm], delta=far)
    for arm in ("arm_f_up", "arm_f_lo"): part(arm, top if arm.endswith("up") else skin, w, w - 0.5, form="tube", shadow=True)
    return m
