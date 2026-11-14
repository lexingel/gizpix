"""Elf archer, 48 px tall, side view: draws the bow and looses an arrow.
python archer.py        -> out/archer.gif, sheet, strip, preview
python archer.py sil    -> flat silhouettes only (step 'silhouette first')"""
import os, sys
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from pixart import Canvas, Ramp, ramp, export, strip, humanoid, head_mask, pose_at
from pixart.poses import ACTIONS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
FLAT = len(sys.argv) > 1 and sys.argv[1] == "sil"
W, H, ROOT_X, GROUND = 88, 64, 28, 60
HALF = 17                                    # half bow length (bow about 0.7 body heights)

skin = ramp("#e9c39a", n=3, name="skin"); green = ramp("#3f8a4a", n=3, name="tunic"); brown = ramp("#7a4f32", n=3, name="leather")
hair = ramp("#e6cf6a", n=3, name="hair"); wood = ramp("#a8703c", n=3, name="bow")
dark = Ramp(["#2a2030"], name="eye"); string = Ramp(["#d8d2c0"], name="string"); steel = Ramp(["#cfd8e0"], name="arrowhead")

rig = humanoid(height=48, heads=5.5); rig.add("weapon", "arm_f_lo", HALF)
z = rig.size; w = z["limb"] - 1               # slender elf limbs

K = ACTIONS["bow"]                            # nock, raise, full draw (hold), release, follow-through (hold), back
half_draw = pose_at([(0, K[1][0]), (1, K[2][0])], 0.5)
# (pose, ms, draw amount 0..1, arrow: "nock" on the string | "fly1" | "fly2" | None)
FULL = dict(K[2][0], arm_b_up=-100, arm_b_lo=100)   # library full draw leaves the string hand at the chest; lift it to the jaw
half_draw = pose_at([(0, K[1][0]), (1, FULL)], 0.5)
SEQ = [(K[0][0], 160, 0.0, "nock"), (K[1][0], 100, 0.0, "nock"), (half_draw, 80, 0.55, "nock"), (FULL, 320, 1.0, "nock"),
       (K[3][0], 60, 0.0, "fly1"), (K[4][0], 90, 0.0, "fly2"), (K[4][0], 160, 0.0, None), (K[5][0], 160, 0.0, None)]


def arrow(c, x0, x1, y, y1=None):
    y1 = y if y1 is None else y1; n = max(1, x1 - x0); yy = lambda x: int(round(y + (y1 - y) * (x - x0) / n))
    c.fill(c.line([(x0, y), (x1, y1)]), brown, tone=0)
    c.fill(c.line([(x1 - 1, yy(x1 - 1)), (x1, y1)]), steel, tone=0)            # head
    c.fill(c.line([(x0, y - 1), (x0 + 1, yy(x0 + 1) - 1)]) | c.line([(x0, y + 1), (x0 + 1, yy(x0 + 1) + 1)]), string, tone=0)   # fletching


def frame(pose, d, arw):
    c = Canvas(W, H, light="tl"); j = rig.solve(pose, root_x=ROOT_X, ground=GROUND)
    f = (lambda m, r, **k: c.fill(m, r, tone=1)) if FLAT else (lambda m, r, **k: c.fill(m, r, **k))
    # far leg
    for b in ("leg_b_up", "leg_b_lo"): c.retone(f(c.limb(*j[b], w + 1, w), green), delta=-1)
    c.retone(f(c.limb(*j["foot_b"], w, w), brown), delta=-1)
    # quiver on the back, behind the torso
    (sx, sy), (nx, ny) = j["spine"]
    f(c.limb((nx - 7, ny - 3), (sx - 5, sy - 4), 4, 3), brown, form="tube")
    c.fill(c.line([(nx - 8, ny - 5), (nx - 7, ny - 6)]) | c.line([(nx - 6, ny - 5), (nx - 5, ny - 7)]), string, tone=0)   # arrow feathers
    # torso + tunic skirt + belt
    f(c.limb(*j["spine"], z["torso"] - 1, z["torso"] - 2), green, form="tube", shadow=True)
    f(c.rect(int(sx) - 4, int(sy) - 2, 9, 6, r=1), green, form="slab")
    c.fill(c.rect(int(sx) - 4, int(sy) - 3, 9, 1), brown, tone=0)
    # near leg
    for b in ("leg_f_up", "leg_f_lo"): f(c.limb(*j[b], w + 1, w), green, form="tube")
    f(c.limb(*j["foot_f"], w, w), brown)
    # head: long hair behind, face, pointed ear, eye
    (ax, ay), (bx, by) = j["head"]; cx, cy = (ax + bx) / 2, (ay + by) / 2; hs = z["head"]
    f(c.blob([(cx - 5, cy - 5), (cx + 1, cy - 6), (cx - 1, cy + 2), (cx - 3, cy + 11), (cx - 7, cy + 10), (cx - 7, cy)]), hair, form="puff")
    head = head_mask(c, j["head"], hs); f(head, skin, form="ball", shadow=True)
    f(head & ((c.yy < cy - 2) | (c.xx < cx - 1)), hair, form="puff")              # hair cap, face stays free in front
    f(c.limb((cx - 1, cy + 1), (cx - 9, cy - 5), 3, 1), skin, tone=1)               # long pointed ear: the elf mark
    c.px(int(cx) + 2, int(cy), dark, 0); c.px(int(cx) + 2, int(cy) - 1, dark, 0)  # eye
    # string arm (pose library: arm_b); drawn over the torso so the draw reads
    for b in ("arm_b_up", "arm_b_lo"): f(c.limb(*j[b], w, w - 0.5), skin if b.endswith("lo") else green, form="tube")
    sh = j["arm_b_lo"][1]                                                        # string hand
    # bow: belly forward, tips pulled back by the draw; string; arrow
    (hx, hy), (tx, ty) = j["weapon"]; ux, uy = (tx - hx) / HALF, (ty - hy) / HALF; kx, ky = uy, -ux   # u along the bow (up), k toward the archer
    pt = lambda a, back: (hx + ux * a + kx * back, hy + uy * a + ky * back)
    L = HALF * (1 - 0.14 * d); back = 4 + 5 * d
    top, bot = pt(L, back), pt(-L, back)
    f(c.curve([top, pt(L * 0.55, 1 + d), (hx, hy), pt(-L * 0.55, 1 + d), bot], w=2), wood)
    f(c.rect(int(sh[0]) - 1, int(sh[1]) - 1, 3, 3), skin, tone=2)                 # string hand, a 3x3 mitten
    # bow arm (near)
    for b in ("arm_f_up", "arm_f_lo"): f(c.limb(*j[b], w, w - 0.5), green if b.endswith("up") else skin, form="tube", shadow=True)
    f(c.rect(int(hx) - 1, int(hy) - 1, 3, 3), skin, tone=2)
    if not FLAT: c.outline("dark")
    # string and arrow after the outline: 1 px lines must stay 1 px
    if arw == "nock":
        apex = sh if sh[0] < top[0] - 1 else None                               # hand behind the chord -> V through the hand
        c.fill(c.line([top, apex, bot] if apex else [top, bot]), string, tone=0)
        ay_ = apex[1] if apex else hy; ax_ = apex[0] if apex else top[0]
        arrow(c, int(ax_), int(hx) + 4, int(round(ay_)), int(round(hy + (hy - ay_) * 4 / max(1, hx - ax_))))
    else:
        c.fill(c.line([top, bot]), string, tone=0)
        if arw == "fly1": arrow(c, int(hx) + 2, int(hx) + 22, int(hy)); c.fill(c.line([(hx - 6, hy), (hx, hy)]), string, tone=0)
        if arw == "fly2": arrow(c, W - 22, W - 3, int(hy)); c.fill(c.line([(W - 34, hy), (W - 24, hy)]), string, tone=0)
    return c


frames = [frame(p, d, a) for p, _, d, a in SEQ]; ms = [m for _, m, _, _ in SEQ]
if FLAT:
    for i in (0, 3, 4): frames[i].silhouette(os.path.join(OUT, f"sil_{i}.png"))
    strip(frames, os.path.join(OUT, "sil_strip.png"))
else:
    frames[3].merge_colors()
    for i in (0, 3):
        print("frame", i, frames[i].lint()[1])
    frames[3].preview(os.path.join(OUT, "archer_preview.png"))
    strip(frames, os.path.join(OUT, "archer_strip.png"))
    export(frames, OUT, "archer", scale=1, ms=ms)
    export(frames, OUT, "archer_x6", scale=6, ms=ms)
