"""64 px red dragon, side view (faces right), wings spread, idle wing-flap loop.
Run: python dragon.py          -> out/dragon.png, dragon_x8.png, dragon_silhouette.png, dragon_preview.png, dragon_strip.png, dragon.gif (+ sheet, json)
     python dragon.py flat     -> silhouette stage only (flat fills)
Change the colours in the ramps below; change the pose in REST; change the flap in FLAP / MS."""
import os, sys
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from pixart import Canvas, Ramp, ramp, shift, export, strip, Rig

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
FLAT = "flat" in sys.argv

red = ramp("#c23a2e", n=4, name="scales")
belly = ramp("#e2b46a", n=3, name="belly")
memb = ramp("#e07a3a", n=3, name="membrane")
bone = ramp("#e8dcc0", n=3, name="horn")
dark = Ramp(["#2a1620"], name="eye")
eye = Ramp(["#ffe45a"], name="iris")

# bone: (parent, length, rest angle, where on the parent it starts). 0 = down, 90 = forward, 180 = up, -90 = back
rig = Rig({
    "body": (None, 15, 98, 0),
    "neck": ("body", 11, 138, 1.0), "neck2": ("neck", 9, 176, 1.0), "head": ("neck2", 12, 100, 1.0),
    "tail": ("body", 6, -72, 0), "tail2": ("tail", 6, -92, 1.0), "tail3": ("tail2", 5, -125, 1.0), "tail4": ("tail3", 5, -165, 1.0),
    "leg_fb_up": ("body", 8, 32, 0.9), "leg_fb_lo": ("leg_fb_up", 8, 2, 1.0),
    "leg_hb_up": ("body", 8, -28, 0.05), "leg_hb_lo": ("leg_hb_up", 8, -8, 1.0),
    "leg_ff_up": ("body", 8, -2, 0.8), "leg_ff_lo": ("leg_ff_up", 8, 6, 1.0),
    "leg_hf_up": ("body", 8, 28, 0.15), "leg_hf_lo": ("leg_hf_up", 8, -18, 1.0),
    "wing_up": ("body", 8, 225, 0.6), "wing_lo": ("wing_up", 16, 188, 1.0),
    "f1": ("wing_lo", 19, 228, 1.0), "f2": ("wing_lo", 19, 260, 1.0), "f3": ("wing_lo", 19, 294, 1.0),
})
REST = rig.rest()
FLAP = [-0.5, -0.1, 0.6, 1.0, 0.6, -0.1]          # -1 = wings up, +1 = wings down
MS = [240, 110, 110, 240, 110, 110]               # hold the two extremes


def wing(c, j, far):
    (s, e), (_, w) = j["wing_up"], j["wing_lo"]
    tips = [j[b][1] for b in ("f1", "f2", "f3")]
    back = (j["body"][0][0] + 3, j["body"][0][1] - 5)                     # where the trailing edge meets the back
    pts = [e, w]
    for a, b in zip(tips, tips[1:] + [back]):                             # scalloped trailing edge: the membrane sags toward the wrist between fingers
        mid = ((a[0] + b[0]) / 2 * 0.5 + w[0] * 0.5, (a[1] + b[1]) / 2 * 0.5 + w[1] * 0.5)
        pts += [a, mid]
    pts += [back, s]
    m = c.poly([(round(x), round(y)) for x, y in pts])
    c.fill(m, memb, form="flat" if FLAT else "grad", lo=0, hi=1 if far else 2)
    arm = c.limb(s, e, 4, 3) | c.limb(e, w, 3, 2)
    fingers = c.empty()
    for b in ("f1", "f2", "f3"): fingers |= c.limb(*j[b], 2, 1)
    c.fill(arm | fingers, red, tone=0 if far else 1)
    if far: c.retone(m, delta=-1)
    else: c.fill(c.limb(w, (w[0] + 2, w[1] - 3), 2, 1), bone, tone=2)       # thumb claw at the wrist
    return m | arm | fingers


def dragon(f=0.0):
    """f = flap, -1 (up) .. +1 (down). Returns a finished canvas."""
    c = Canvas(64, 64, light="tl")
    d = 20 * f
    pose = dict(REST, wing_up=REST["wing_up"] + d * 0.5, wing_lo=REST["wing_lo"] + d * 0.4,
                f1=REST["f1"] + d * 0.8, f2=REST["f2"] + d, f3=REST["f3"] + d * 1.1,
                neck2=REST["neck2"] - 3 * f, tail4=REST["tail4"] + 12 * f)       # overlapping action: head and tail tip answer the wings
    j = rig.solve(pose, root_x=23, ground=61)
    form = (lambda n: "flat") if FLAT else (lambda n: n)

    jf = {k: ((a[0] + 4, a[1] - 1), (b[0] + 4, b[1] - 1)) for k, (a, b) in j.items()}   # far wing: same wing, a bit ahead and higher, darker
    wing(c, jf, far=True)
    for b in ("leg_fb_up", "leg_fb_lo", "leg_hb_up", "leg_hb_lo"):                # far legs, one tone darker
        c.retone(c.fill(c.limb(*j[b], 4, 2.5), red), delta=-1)

    tail = c.empty()
    for b, w0, w1 in (("tail", 8, 6), ("tail2", 6, 4.5), ("tail3", 4.5, 3), ("tail4", 3, 2)): tail |= c.limb(*j[b], w0, w1)
    c.fill(tail, red, form=form("puff"))
    tx, ty = j["tail4"][1]
    c.fill(c.poly([(round(tx) - 3, round(ty) - 3), (round(tx) + 2, round(ty) - 4), (round(tx) + 1, round(ty) + 2)]), red, tone=1)   # spade tip
    for b in ("tail", "tail2", "tail3"):                                         # tail spikes
        (ax, ay), (bx, by) = j[b]; mx, my = round((ax + bx) / 2), round((ay + by) / 2)
        c.fill(c.poly([(mx - 2, my - 2), (mx + 1, my - 2), (mx - 1, my - 6)]), bone, tone=1)

    hip, chest = j["body"]
    body = c.oval(round(hip[0]) - 4, round(hip[1]) - 6, round(chest[0] - hip[0]) + 10, 12)
    c.fill(body, red, form=form("ball"))
    c.fill(body & ~shift(body, 0, -3) & (c.xx > hip[0]), belly, tone=1)             # belly plates

    n0, n1, n2 = j["neck"][0], j["neck"][1], j["neck2"][1]
    for k in range(3):                                                           # neck spikes, behind the neck
        x = n1[0] + (n2[0] - n1[0]) * k / 2 - 3; y = n1[1] + (n2[1] - n1[1]) * k / 2 + 2
        c.fill(c.poly([(round(x), round(y) - 1), (round(x), round(y) + 2), (round(x) - 3, round(y) - 2)]), bone, tone=1)
    neck = c.limb(n0, n1, 9, 6) | c.limb(n1, n2, 6, 5)
    c.fill(neck, red, form=form("tube"))
    c.fill(neck & ~shift(neck, -2, 0) & (c.yy > n2[1] + 2), belly, tone=1)          # throat

    for b in ("leg_hf_up", "leg_hf_lo", "leg_ff_up", "leg_ff_lo"):               # near legs
        c.fill(c.limb(*j[b], 5 if b.endswith("up") else 3.5, 3), red, form=form("tube"))
    for b in ("leg_fb_lo", "leg_hb_lo", "leg_hf_lo", "leg_ff_lo"):               # feet with a light claw
        x, y = j[b][1]; x, y = round(x), round(y)
        c.fill(c.rect(x - 1, y - 1, 5, 2), red, tone=0 if "b_" in b else 1); c.px(x + 4, y, bone, 2)

    h0, h1 = j["head"]
    c.fill(c.limb((h0[0] - 1, h0[1] - 1), (h0[0] - 9, h0[1] - 7), 2.5, 1), bone, form=form("tube"))    # horn sweeps back
    jaw = c.limb((h0[0] + 1, h0[1] + 3), (h1[0] - 2, h1[1] + 5), 2.5, 1.5)                               # lower jaw, slightly open
    c.fill(jaw, red, tone=0)
    skull = c.limb(h0, h1, 7, 4)
    c.fill(skull, red, form=form("puff"), shadow=True)
    ex, ey = round(h0[0]) + 2, round(h0[1]) - 2
    c.put(["ee", "ek"], {"e": (eye, 0), "k": (dark, 0)}, ex, ey)                                     # eye: the pixels that matter most
    c.px(round(h1[0]) - 1, round(h1[1]) - 1, dark, 0)                                                # nostril
    for k in (2, 4): c.px(round(h1[0]) - k, round(h1[1]) + 2, bone, 2)                               # teeth

    wing(c, j, far=False)
    c.outline("selout")
    return c


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    c = dragon(-0.3)                                    # the still: wings open, slightly raised
    c.silhouette(os.path.join(OUT, "dragon_silhouette.png"))
    if FLAT: sys.exit()
    frames = [dragon(f) for f in FLAP]
    frames[0].merge_colors(); c = dragon(-0.3)
    for name, fr in (("still", c), ("wings up", frames[0]), ("wings down", frames[3])):
        print(name, fr.lint()[1])
    c.preview(os.path.join(OUT, "dragon_preview.png"))
    c.save(os.path.join(OUT, "dragon.png")); c.save(os.path.join(OUT, "dragon_x8.png"), scale=8)
    os.makedirs(os.path.join(OUT, "anim"), exist_ok=True)
    export(frames, os.path.join(OUT, "anim"), "dragon_idle", scale=6, ms=MS)
    strip(frames, os.path.join(OUT, "dragon_strip.png"))
    print(sorted(os.listdir(OUT)), sorted(os.listdir(os.path.join(OUT, "anim"))))
