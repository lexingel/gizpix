"""8-direction wizard (purple robe, pointed hat, staff), ~36 px tall with the hat. Walk + staff cast, as sprite sheets.
Run: python wizard.py   -> out/  (change the colours in the ramps below, the size in BODY/CELL)"""
import os, sys
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from pixart import Canvas, Ramp, ramp, humanoid, mannequin8, face_point, body_width, sheet, strip, export
from pixart.poses import ACTIONS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
DIRS8 = ("S", "SE", "E", "NE", "N", "NW", "W", "SW")          # row order of both sheets
CW, CH = 96, 72; GROUND = 66; ROOT_X = 48; BODY = 29      # cell 96x72: room for the raised staff and the bolt                # body 29 px + hat = about 36-37 px

robe = ramp("#6b3fa6", n=3, name="robe"); skin = ramp("#e8b48c", n=3, name="skin"); shoe = ramp("#4a3528", n=3, name="shoe")
beard = ramp("#e6e2ee", n=3, name="beard"); wood = ramp("#8a5a3c", n=3, name="staff"); gold = ramp("#e0b040", n=3, name="gold")
gem = Ramp(["#3aa8d8", "#8fe8f8"], name="gem"); glow = Ramp(["#58c8f0", "#b8f4ff", "#ffffff"], name="glow"); eye = Ramp(["#241a2c"], name="eye")

rig = humanoid(BODY, 3.5)
rig.add("weapon", "arm_f_lo", 20)          # staff above the right hand
rig.add("staff_lo", "arm_f_lo", 11)        # staff below the hand (always weapon - 180)
rig.add("fx", "weapon", 9, 90)             # a point in front of the staff tip: where the spell flies (projected per direction)
rig.lat["arm_f_up"] = 9                 # staff hand held away from the body, so the staff does not cross the face in SE / SW
H = rig.size["head"]


def staff_pose(pose, walk):
    if walk: pose = dict(pose, arm_f_up=8, arm_f_lo=38, weapon=178)        # the staff arm does not swing: staff carried upright
    if not walk and pose["weapon"] < 116: pose = dict(pose, weapon=160)                    # ready pose: staff upright, not levelled like a spear
    if pose.get("root", (0, 0))[0] < 0: pose = dict(pose, root=(0, pose["root"][1]))          # a backward root shift gives head and torso a negative depth and mannequin8 then shades the face as a far-side part
    pose = dict(pose, spine=min(pose["spine"], 180))                                          # same reason: no leaning back
    return dict(pose, staff_lo=pose["weapon"] - 180, fx=90)


def none(c, j, b): return c.empty()


def robe_fn(c, j, b):
    (hx, hy), (sx, sy) = j["spine"]; bw = body_width(rig, j)
    xs = [j["foot_f"][0][0], j["foot_b"][0][0], j["foot_f"][1][0], j["foot_b"][1][0]]
    l = min(min(xs) - 1, hx - bw / 2 - 2); r = max(max(xs) + 1, hx + bw / 2 + 2)                  # the hem follows the feet: it sways in the walk
    m = c.limb((hx, hy + 1), (sx, sy + 1), bw + 1, bw) | c.poly([(hx - bw / 2, hy - 2), (hx + bw / 2, hy - 2), (r, GROUND - 2), (l, GROUND - 2)])
    c.fill(m, robe, form="tube", shadow=True)
    c.retone(c.rect(int(l), GROUND - 3, int(r - l) + 1, 1) & m, delta=-1)                           # dark hem
    return m


def sleeve_fn(c, j, b):
    m = c.limb(*j[b], 3.5, 4 if b.endswith("lo") else 3.5); c.fill(m, robe, form="tube", shadow=j[b][1][1] > j["head"][0][1] + 2)      # a raised arm must not shade the face
    if j.depth[b] < 0: c.retone(m, delta=-1)
    if b.endswith("lo"): x, y = j[b][1]; m = m | c.fill(c.rect(int(round(x)) - 1, int(round(y)) - 1, 2, 2), skin, tone=1)   # hand
    return m


def staff_fn(c, j, b):
    m = c.fill(c.limb(*j[b], 2, 2), wood, tone=1)
    if b == "weapon": x, y = j[b][1]; m = m | c.fill(c.oval(int(round(x)) - 2, int(round(y)) - 2, 4, 4), gem, tone=1)
    return m


def hat_fn(c, j, b):
    bx, by, _ = face_point(rig, j, 0, 0, 0.42); tx, ty, _ = face_point(rig, j, -0.45, 0, 1.45)      # brim centre; tip, bent back
    fx, fy, front = face_point(rig, j, 0.5, 0, -0.1)
    m = c.empty()
    if front:                                                                                        # beard: only where the face shows
        qx, qy, _ = face_point(rig, j, 0.3, 0, -0.5)
        m = m | c.fill(c.poly([(qx - 3, qy), (qx + 3, qy), (qx + 0.5, qy + 5), (qx - 0.5, qy + 5)]), beard, form="flat", tone=2, shadow=True)
    else:                                                                                            # from behind: grey hair hides the head
        cx, cy, _ = face_point(rig, j, 0, 0, -0.1)
        m = m | c.fill(c.rect(int(round(cx - H * 0.5)), int(round(cy - H * 0.35)), int(round(H)), int(round(H * 0.95)), r=2), beard, form="flat", tone=1)
    cone = c.poly([(bx - H * 0.5, by), (bx + H * 0.5, by), (tx + 0.5, ty), (tx - 0.5, ty)])
    brim = c.oval(int(round(bx - H * 0.95)), int(round(by - 1)), int(round(H * 1.9)), 4)
    c.fill(brim, robe, form="flat", tone=0, shadow=True); c.fill(cone, robe, form="tube")
    c.fill(c.rect(int(round(bx - H * 0.45)), int(round(by)) - 2, int(round(H * 0.9)), 1) & cone, gold, tone=1)   # hat band
    return m | cone | brim


PAINT = {"spine": robe_fn, "leg_f_up": none, "leg_f_lo": none, "leg_b_up": none, "leg_b_lo": none, "arm_f_up": sleeve_fn, "arm_f_lo": sleeve_fn,
         "arm_b_up": sleeve_fn, "arm_b_lo": sleeve_fn, "weapon": staff_fn, "staff_lo": staff_fn, "fx": none, "head+": hat_fn}


def spell(c, j, tag, i):
    """effects after the outline (no outline on glow): charge halo on the raised staff, bolt flying forward on the release"""
    (tx, ty), (fx, fy) = j["fx"]; tx, ty = int(round(tx)), int(round(ty))
    if i in (1, 2):                                                           # charging: halo grows
        r = 2 + i; c.fill(c.oval(tx - r, ty - r, 2 * r, 2 * r), glow, tone=0); c.fill(c.oval(tx - r + 2, ty - r + 2, 2 * r - 4, 2 * r - 4), glow, tone=2)
    if i in (3, 4):                                                           # release: streak from the tip + ball in front
        k = 0.7 if i == 3 else 1.3; ex, ey = tx + (fx - tx) * k, ty + (fy - ty) * k
        c.fill(c.line([(tx, ty), (int(round(ex)), int(round(ey)))], w=2), glow, tone=0 if i == 4 else 1)
        c.fill(c.oval(int(round(ex)) - 3, int(round(ey)) - 3, 6, 6), glow, tone=1); c.fill(c.oval(int(round(ex)) - 1, int(round(ey)) - 1, 3, 3), glow, tone=2)


def frame(pose, d, tag="", i=0, action="walk", flat=False):
    c = Canvas(CW, CH, light="tl")
    j = rig.solve(staff_pose(pose, action == "walk"), root_x=ROOT_X, ground=GROUND, direction=d)
    mannequin8(c, rig, j, skin, robe, robe, shoes=shoe, eye=eye, paint=PAINT)
    if not flat:
        c.outline("dark")
        if action == "cast": spell(c, j, tag, i)
    return c


def build(action, flat=False):
    return [[frame(p, d, tag, i, action, flat) for i, (p, ms, tag) in enumerate(ACTIONS[action])] for d in DIRS8]


if __name__ == "__main__":
    if "sil" in sys.argv:                                                     # step 1: silhouettes only
        w = build("walk", flat=True); k = build("cast", flat=True)
        strip([r[0] for r in w] + [r[2] for r in k], os.path.join(OUT, "sil_dirs.png"), sil=True)
        strip(w[2] + k[2], os.path.join(OUT, "sil_E.png"), sil=True); sys.exit()
    walk = build("walk"); cast = build("cast")
    walk[0][0].merge_colors()
    for name, rows in (("walk", walk), ("cast", cast)):
        print(sheet(rows, os.path.join(OUT, f"wizard_{name}_sheet.png")))
        sheet(rows, os.path.join(OUT, f"wizard_{name}_review.png"), scale=4, bg="#606068")
    for c, n in ((walk[0][0], "walk_S"), (cast[1][2], "cast_SE_hold"), (walk[4][0], "walk_N")):
        print(n); c.lint(); c.preview(os.path.join(OUT, f"wizard_{n}_preview.png"))
    export(walk[1], OUT, "wizard_walk_SE", scale=6, ms=[m for _, m, _ in ACTIONS["walk"]])
    export(cast[1], OUT, "wizard_cast_SE", scale=6, ms=[m for _, m, _ in ACTIONS["cast"]])
    sheet([cast[1]], os.path.join(OUT, "wizard_cast_SE_strip.png"), scale=6, bg="#606068")   # strip() crashes without sil=True (pixart bug), sheet() of one row does the same
    sheet([[r[0] for r in walk]], os.path.join(OUT, "wizard_dirs_strip.png"), scale=6, bg="#606068")
