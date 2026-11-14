# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixart.examples - worked recipes. Copy the nearest one and change it; each shows one way of building a subject from parts.
  potion  glass + liquid (item icon)        sword   diagonal blade, two-tone metal        heart   text-grid mask + automatic shading
  slime   one soft mass, squash animation   tree    overlapping spheres, cast shadows     chest   boxes, planks, metal straps
  cat     a 48 px animal: stripes, eyes, tail (blind-test drawing)
  knight  a 40 px armed character on the rig, slash from the pose library
  dir8    adventurer8(): one character walking / fighting in 8 directions from one pose list
  hero    a 24 px character from parts      coin    spin animation                        flame   effect animation, no outline
  logo    lettering styles + Turkish        scene   background by depth, pasted objects
Each function returns a Canvas, or a list of Canvases for an animation."""
import math
import numpy as np
from .core import Canvas, Ramp, ramp, shrink, grow, shift, sym


def potion(liquid="#c8324a"):
    c = Canvas(32, 32); glass = ramp("#a9cbd9", name="glass"); liq = ramp(liquid, name="liquid"); cork = ramp("#b07a45", n=3, name="cork")
    body = c.oval(7, 12, 18, 17); neck = c.rect(13, 7, 6, 7); lip = c.rect(12, 6, 8, 2)
    c.fill(body, glass, form="ball", lo=1)                                   # the glass shell, never very dark
    c.fill(neck, glass, form="tube", lo=1); c.fill(lip, glass, form="slab", tone=2)
    juice = shrink(body, 2) & (c.yy >= 18)                                   # the liquid sits inside the shell, below the fill line
    c.fill(juice, liq, form="ball", box=(9, 14, 14, 13), rim=True)
    c.retone(juice & (c.yy == 18), tone=3)                                   # bright surface line
    c.fill(c.rect(13, 2, 6, 5, r=1), cork, form="tube")
    c.put(["a.", "a.", ".a"], {"a": (glass, 3)}, 10, 15)                     # the glint that says "glass"
    c.outline(); return c


def sword():
    c = Canvas(32, 32); steel = ramp("#aab7c4", n=4, name="steel"); gold = ramp("#d9a531", n=4, name="gold"); grip = ramp("#7a4a34", n=3, name="grip")
    blade = c.poly([(10, 20), (25, 5), (28, 3), (26, 6), (11, 21)]) | c.poly([(10, 20), (12, 22), (27, 7), (28, 3)])
    c.fill(blade, steel, tone=1)
    c.retone(blade & (c.xx + c.yy < 31), tone=2)                             # the face turned to the light; the ridge is the border of the two tones
    c.retone(c.line([(11, 18), (25, 4)]) & blade, tone=3)                    # a bright edge
    c.fill(c.line([(6, 17), (14, 25)], w=2), gold, form="grad", shadow=True) # guard, across the blade
    c.fill(c.line([(8, 23), (5, 26)], w=2), grip, tone=1)
    c.fill(c.rect(2, 26, 4, 4, r=1), gold, form="ball")
    c.outline(); return c


def heart(color="#e23b4e"):
    c = Canvas(16, 16); red = ramp(color, name="heart")
    m = c.grid(["..###...###..", ".#####.#####.", "#############", "#############", "#############", ".###########.", "..#########..", "...#######...", "....#####....", ".....###.....", "......#......"], 1, 2)
    c.fill(m, red, form="puff", depth=4)
    c.put(["aa", "a."], {"a": (red, 3)}, 3, 4)
    c.outline(); return c


def slime(t=0.0, color="#58c26a"):
    """t = 0..1 around one bounce: the mass keeps its volume (wider when lower)"""
    c = Canvas(24, 24); g = ramp(color, name="slime"); dark = Ramp(["#1d2433"], name="eye"); s = math.sin(t * 2 * math.pi)
    w = 18 + 2 * round(s); h = 15 - 2 * round(s); x = 12 - w // 2; y = 21 - h
    body = (c.oval(x, y, w, h + 5) & (c.yy < 21)) | c.rect(x + 1, 17, w - 2, 4, r=1)
    c.fill(body, g, form="ball", box=(x, y, w, h + 6), rim=True)
    ey = y + h // 2
    for ex in (9, 14): c.put(["a", "a"], {"a": (dark, 0)}, ex, ey)
    c.put(["aa", "a."], {"a": (g, 3)}, x + 4, y + 3)
    c.outline(); return c


def slime_anim(n=6): return [slime(i / n) for i in range(n)]


def tree():
    c = Canvas(32, 40); leaf = ramp("#4f9d4a", n=5, name="leaf"); bark = ramp("#8a5a3c", n=4, name="bark")
    trunk = c.poly([(14, 24), (18, 24), (19, 36), (21, 37), (11, 37), (13, 36)])
    c.fill(trunk, bark, form="tube")
    c.retone(c.line([(15, 27), (15, 31)]) | c.line([(17, 30), (17, 34)]), delta=-1)            # bark marks: short, uneven
    for box in ((8, 3, 17, 15), (3, 10, 15, 14), (14, 11, 15, 14), (8, 15, 16, 11)):           # back to front: each lobe is a sphere under the same light
        c.fill(c.oval(*box), leaf, form="ball", lo=1, shadow=True)
    c.outline(); return c


def chest():
    c = Canvas(32, 26); wood = ramp("#9a6238", n=4, name="wood"); iron = ramp("#8d97a6", n=4, name="iron"); gold = ramp("#e0b33a", n=4, name="gold"); dark = Ramp(["#2a1c24"], name="hole")
    body = c.rect(4, 12, 24, 11); lid = c.rect(4, 4, 24, 9, r=3) & (c.yy < 12)
    c.fill(body, wood, form="slab", tone=1)
    for x in (10, 16, 22): c.retone(c.rect(x, 13, 1, 9), delta=-1)                             # plank seams
    c.fill(lid, wood, form="tube", axis="y", lo=1, shadow=True)                               # a rounded lid: cylinder lying down; it shades the body below
    for x in (6, 23): c.fill(c.rect(x, 4, 3, 19) & (body | lid), iron, form="bands", bands="231")
    c.fill(c.rect(4, 11, 24, 1), iron, tone=0)                                                 # the gap under the lid
    c.fill(c.rect(14, 10, 4, 5, r=1), gold, form="slab", tone=2, shadow=True); c.px(15, 12, dark, 0); c.px(16, 12, dark, 0); c.px(15, 13, dark, 0)
    c.outline(); return c


def hero():
    """24 px adventurer seen from the front: big head (identity lives in hair and eyes), 2 px limbs, parts split by colour instead of inner black lines"""
    c = Canvas(24, 24); skin = ramp("#eab892", n=3, name="skin"); hair = ramp("#8a3f2b", n=3, name="hair"); tunic = ramp("#3f7fc4", n=3, name="tunic")
    leg = ramp("#55466b", n=3, name="trousers"); boot = hair; eye = Ramp(["#2a1c2e"], name="eye")
    c.fill(c.rect(9, 18, 2, 4) | c.rect(13, 18, 2, 4), leg, tone=1); c.retone(c.rect(13, 18, 2, 4), delta=-1)      # the leg away from the light is darker
    c.fill(c.rect(8, 21, 3, 2) | c.rect(13, 21, 3, 2), boot, form="slab")
    c.fill(c.rect(8, 12, 8, 7, r=1), tunic, form="tube")
    c.fill(c.rect(8, 16, 8, 1), boot, tone=1)                                                                       # belt
    c.fill(c.rect(6, 13, 2, 5), tunic, tone=2); c.fill(c.rect(16, 13, 2, 5), tunic, tone=0)
    c.fill(c.rect(6, 17, 2, 2) | c.rect(16, 17, 2, 2), skin, tone=1)
    head = c.oval(7, 3, 10, 10)
    c.fill(head, skin, form="ball", lo=1, shadow=True)
    c.fill((c.oval(6, 1, 12, 9) & (c.yy < 6)) | c.rect(6, 5, 2, 5) | c.rect(16, 5, 2, 4) | c.rect(8, 6, 2, 1), hair, form="puff", depth=3)
    c.put(["e..e", "e..e"], {"e": (eye, 0)}, 10, 8); c.px(12, 11, skin, 0)                                          # eyes 2 px tall, 2 px apart; a mouth of dark skin, not black
    c.outline(); c.merge_colors(); return c


def coin(t=0.0):
    c = Canvas(16, 16); gold = ramp("#e2b23a", n=4, name="gold"); w = max(2, round(12 * abs(math.cos(t * math.pi)))); x = 8 - w // 2
    if w <= 3: c.fill(c.rect(x, 2, w, 12, r=0), gold, form="bands", bands="31"[:w] if w < 3 else "321")
    else:
        m = c.oval(x, 2, w, 12); c.fill(m, gold, form="ball", lo=1)
        if w >= 8: c.fill(shrink(m, 2), gold, form="slab", tone=2); c.retone(c.rect(8 - 1, 6, 2, 4) & shrink(m, 3), tone=3)
    c.outline(); return c


def coin_anim(n=6): return [coin(i / n) for i in range(n)]


def flame(t=0.0):
    """outer orange teardrop, inner yellow one that moves every frame but never breaks out, pale core; an effect has no outline"""
    c = Canvas(16, 24); a = t * 2 * math.pi; sw = 1.6 * math.sin(a); fl = 1.5 * math.sin(2 * a + 1)
    red = Ramp(["#c2371f", "#ee6a1c"], name="outer"); yel = Ramp(["#f7a71b", "#fddc4a", "#fff6c4"], name="inner")
    outer = c.blob([(8 + sw, 3 + fl), (10.5 + sw * .6, 9), (13, 15), (11.5, 20), (8, 22), (4.5, 20), (3, 15), (5.5 + sw * .6, 9)])
    c.fill(outer, red, tone=1); c.fill(outer & ~shrink(outer), red, tone=0)
    sw2 = 1.2 * math.sin(a + 1.3)
    inner = c.blob([(8 + sw2, 10 - fl), (10, 15), (10.5, 19), (8, 21), (5.5, 19), (6, 15)]) & shrink(outer, 2)
    c.fill(inner, yel, tone=0); c.fill(shrink(inner), yel, tone=1); c.fill(c.oval(7, 17, 3, 4) & shrink(inner), yel, tone=2)
    if int(t * 8) % 4 == 1: c.px(int(11 + sw), 4, yel, 1)
    if int(t * 8) % 4 == 3: c.px(int(5 + sw), 2, red, 1)
    return c


def flame_anim(n=8): return [flame(i / n) for i in range(n)]


def logo():
    c = Canvas(96, 50); sky = ramp("#4f9be0", n=4, name="sky"); earth = ramp("#c9662b", n=4, name="earth"); ink = ramp("#f2e6c8", n=3, name="ink"); gold = ramp("#e8b63c", n=4, name="gold")
    m = c.text("GIZPIX", 6, 5, sky, bold=True, style="chrome", r2=earth, spacing=2); c.outline("black", mask=m)
    m2 = c.text("ÇİZ ŞÖĞÜT", 6, 22, gold, style="grad", shadow=True)
    c.text("SCORE 00420", 6, 38, ink, font="3x5", mono=True, shadow=True)
    c.merge_colors(); return c


def scene():
    """depth by the book: far = lighter, greyer, flatter, no outline; near = darker, richer, outlined. The sky is its own canvas lit from below (bright horizon)."""
    c = Canvas(96, 64); sky = Canvas(96, 64, light=(0, 0.75)); blue = ramp("#6aaee0", n=5, shift=0.6, name="sky")
    sky.fill(sky.rect(0, 0, 96, 64), blue, form="grad", lo=1, dither=1); c.paste(sky)
    sun = ramp("#f6d55c", n=3, name="sun"); c.fill(c.oval(66, 8, 12, 12), sun, form="ball", lo=1)
    far = ramp("#8fb2b8", n=3, name="far hills"); mid = ramp("#5f9a63", n=4, name="hills"); near = ramp("#6f8f3a", n=4, name="meadow")
    c.fill(c.blob([(-4, 44), (14, 30), (30, 38), (52, 26), (74, 36), (100, 30), (100, 70), (-4, 70)]), far, tone=1)
    hill = c.blob([(-4, 50), (20, 40), (44, 47), (70, 42), (100, 48), (100, 70), (-4, 70)]); c.fill(hill, mid, tone=1); c.retone(hill & ~shift(hill, 0, 1), delta=1)
    ground = c.rect(0, 54, 96, 10); c.fill(ground, near, tone=1); c.retone(ground & (c.yy == 54), delta=1)
    for gx, gy in ((6, 58), (19, 61), (33, 57), (50, 60), (58, 57), (88, 59), (80, 62)): c.retone(c.line([(gx, gy), (gx, gy - 1)]) | c.line([(gx + 2, gy), (gx + 2, gy - 2)]), delta=1)   # grass strokes, short and uneven
    for x, y, w in ((10, 38, 7), (28, 42, 6), (82, 40, 7)): c.fill(c.oval(x, y, w, w + 2), mid, form="ball", lo=0, hi=2); c.fill(c.rect(x + w // 2, y + w + 1, 1, 3), far, tone=0)   # far trees: tiny, no outline
    c.paste(tree(), 44, 18); c.merge_colors(); return c


def cat():
    """48 px sitting tabby, front view: tail behind, pear body, legs, head last; stripes are tone marks, eyes are hand-placed. (Drawn by a first-time user of the skill in the blind test.)"""
    from .core import flipx
    c = Canvas(48, 48, light="tl")
    fur = ramp("#e08a3c", n=4, name="fur")
    cream = ramp("#e8dcc0", n=3, name="cream")       # not lighter: ramp() puts a very light base at the TOP tone and tone 1 turns taupe
    pink = ramp("#e58a8a", n=3, name="pink")
    green = Ramp(["#6fae3c"], name="iris"); dark = Ramp(["#2a1c2e"], name="pupil")

    tail = c.curve([(31, 43), (40, 42), (43, 35), (40, 28)], w=4)                 # tail curls up on the right, behind the body
    c.fill(tail, fur, form="puff", lo=0, hi=2)
    c.retone(tail & ((c.yy % 4) == 0), delta=-1)                                  # tail rings
    body = c.oval(12, 19, 24, 30) & (c.yy < 46)                                   # pear body
    c.fill(body, fur, form="ball", box=(12, 19, 24, 30))
    for y, x0, x1 in ((27, 13, 17), (31, 12, 16), (35, 12, 16), (27, 31, 35), (31, 32, 36), (35, 32, 36)):   # tabby stripes on the flanks
        c.retone(c.line([(x0, y), (x1, y + 1)], w=2) & body, delta=-1)
    chest = c.oval(19, 23, 10, 14)
    c.fill(chest, cream, form="ball", lo=1)
    for x in (18, 25):                                                            # front legs, straight down, 5 px wide
        c.fill(c.rect(x, 31, 5, 14, r=1), fur, form="tube", lo=1)
        c.fill(c.rect(x - 1, 43, 6, 3, r=1), cream, tone=2)                  # white paws
    head = c.oval(11, 5, 26, 20)
    earL = c.poly([(12, 12), (14, 2), (21, 9)]); earR = flipx(earL, 24)
    c.fill(earL | earR, fur, tone=1)
    c.fill(shrink(earL, 2) | shrink(earR, 2), pink, tone=1)
    c.fill(head, fur, form="ball", shadow=True)
    for x in (21, 24, 27):                                                        # forehead stripes
        c.retone(c.line([(x, 6), (x, 9 if x == 24 else 8)]) & head, delta=-1)
    for y in (14, 17):                                                            # cheek stripes
        c.retone((c.line([(12, y), (15, y)]) | c.line([(33, y), (36, y)])) & head, delta=-1)
    c.fill(c.oval(19, 16, 10, 7), cream, form="ball", lo=1)                             # muzzle
    c.put(["nn"], {"n": (pink, 1)}, 23, 17)                                       # nose
    c.put(["m..m", ".mm."], {"m": (pink, 0)}, 22, 19)                             # mouth
    for x in (16, 29):                                                            # eyes: 3x3 green, 1x3 slit pupil, shine top-left
        c.put(["ggg", "ggg", "ggg"], {"g": (green, 0)}, x, 12)
        c.put(["p", "p", "p"], {"p": (dark, 0)}, x + 1, 12)
        c.px(x, 12, cream, 2)
    c.retone(c.rect(23, 37, 2, 6), tone=0)                                        # dark gap between the front legs
    c.outline("selout"); return c


def knight(action="slash"):
    """a 40 px armed character animated from the pose library: rig -> pose per frame -> far side first, body, near side last. One swing frame carries the smear;
    the shield (far arm) is painted before the body, the sword (near hand) after it. Returns (frames, ms list)."""
    from .rig import humanoid, head_mask
    from .poses import ACTIONS
    steel = ramp("#9aa7b8", n=4, name="steel"); cloth = ramp("#a8323a", n=3, name="cloth"); skin = ramp("#e8b48c", n=3, name="skin"); wood = ramp("#8a5a3c", n=3, name="shield")
    blade = Ramp(["#8f9db0", "#dfe8f0", "#ffffff"], name="blade"); smear = Ramp(["#c0cbdc", "#fafaf6"], name="smear")
    rig = humanoid(40, 4); rig.add("weapon", "arm_f_lo", 17); z = rig.size; w = z["limb"]; frames = []; times = []
    for pose, ms, tag in ACTIONS[action]:
        pose = dict(pose, arm_b_up=48, arm_b_lo=96)                                                                                    # the shield arm keeps its guard through the whole swing
        c = Canvas(72, 60); j = rig.solve(pose, root_x=26, ground=56)
        for b in ("leg_b_up", "leg_b_lo", "foot_b"): c.retone(c.fill(c.limb(*j[b], w + 1, w), steel), delta=-1)                 # far leg, one tone darker
        c.retone(c.fill(c.limb(*j["arm_b_up"], w, w), steel), delta=-1)
        hx, hy = j["arm_b_lo"][1]; c.fill(c.oval(int(hx) - 5, int(hy) - 7, 10, 13), wood, form="ball", lo=0, hi=1)                 # shield on the far arm: behind the body
        c.fill(c.limb(*j["spine"], z["torso"], z["torso"] * 0.85), steel, form="tube", shadow=True)
        (sx, sy), _ = j["spine"]; c.fill(c.rect(int(sx) - 4, int(sy) - 2, 9, 5, r=1), cloth, form="slab")                          # tabard skirt at the hips
        for b in ("leg_f_up", "leg_f_lo", "foot_f"): c.fill(c.limb(*j[b], w + 1, w), steel, form="tube")
        head = head_mask(c, j["head"], z["head"]); c.fill(head, steel, form="ball", shadow=True)                                   # helmet
        (ax, ay), (bx, by) = j["head"]; cx, cy = (ax + bx) / 2, (ay + by) / 2
        c.fill(c.rect(int(cx) + 1, int(cy) - 1, 4, 2), Ramp(["#241a2c"]), tone=0)                                                   # visor slit, on the facing side
        c.fill(c.limb((cx - 1, cy - 5), (cx - 6, cy - 9), 3, 2), cloth, tone=2)                                                    # plume: the charm point, trails behind
        if tag == "smear":
            (px, py), _ = j["arm_f_up"]; c.fill(c.crescent(px, py, 27, 232, 118, 7), smear, tone=1)                                # from the wind-up angle to where the blade is now
        else: c.fill(c.limb(*j["weapon"], 2.2, 1.6), blade, tone=1); c.retone(c.limb(*j["weapon"], 1, 1), tone=2)
        for b in ("arm_f_up", "arm_f_lo"): c.fill(c.limb(*j[b], w + 0.5, w), steel, form="tube", shadow=True)
        (gx, gy) = j["arm_f_lo"][1]; c.fill(c.limb((gx - 2, gy + 2), (gx + 2, gy - 2), 2, 2) if tag != "smear" else c.empty(), wood, tone=1)   # crossguard: what makes a line read as a sword
        ol = c.outline("dark"); frames.append(c); times.append(ms)
    frames[4].merge_colors(); return frames, times                                                                                    # ramps are shared by all frames, so one merge fixes every frame


def knight_anim(): return knight()[0]


def adventurer8(action="walk", dirs=("S", "SE", "E", "NE", "N", "NW", "W", "SW")):
    """one character, 8 directions, any action from the pose library: the pose is solved once per direction (rig.solve(direction=...)), so nothing is mirrored -
    the sword stays in the right hand, the shield on the left arm, the light on the same side. Returns {direction: [frames]}; sheet(list(rows.values()), path) packs it."""
    from .rig import humanoid, mannequin8, head_mask, face_point
    from .poses import ACTIONS
    skin = ramp("#e8b48c", n=3, name="skin"); tunic = ramp("#3f8f5a", n=3, name="tunic"); legs = ramp("#5a4a3a", n=3, name="legs"); hair = ramp("#c9772f", n=3, name="hair")
    wood = ramp("#8a5a3c", n=3, name="shield"); blade = Ramp(["#8f9db0", "#e6edf2"], name="blade"); eye = Ramp(["#241a2c"], name="eye")
    rig = humanoid(36, 4); rig.add("weapon", "arm_f_lo", 13); rig.add("shield", "arm_b_lo", 1, 90)
    def weapon(c, j, b): return c.fill(c.limb(*j[b], 2, 1.5), blade, tone=1)
    def shield(c, j, b): x, y = j[b][0]; return c.fill(c.oval(int(x) - 4, int(y) - 6, 8, 11), wood, form="ball", lo=0, hi=1, shadow=True)
    def hair_fn(c, j, b):
        x, y, _ = face_point(rig, j, -0.18, 0, 0.12); h = rig.size["head"]; m = c.oval(int(round(x - h * 0.55)), int(round(y - h * 0.55)), int(round(h * 1.1)), int(round(h * 0.95)))
        ex, ey, front = face_point(rig, j, 0.45, 0, -0.1)                                                                          # the face is cut out of the hair only where it shows; from behind the head is all hair
        if front: m = m & ~c.oval(int(round(ex - h * 0.42)), int(round(ey - h * 0.3)), int(round(h * 0.84)), int(round(h * 0.8)))
        return c.fill(m, hair, form="ball", lo=0)
    rows = {}
    for d in dirs:
        rows[d] = []
        for pose, ms, tag in ACTIONS[action]:
            if action not in ("walk", "run", "idle"): pose = dict(pose, arm_b_up=45, arm_b_lo=95)                                 # the shield arm keeps its guard while the sword arm works
            c = Canvas(56, 52); j = rig.solve(pose, root_x=28, ground=48, direction=d)
            mannequin8(c, rig, j, skin, tunic, legs, eye=eye, paint={"weapon": weapon, "shield": shield, "head+": hair_fn}); c.outline("dark"); rows[d].append(c)
    rows[dirs[0]][0].merge_colors(); return rows                                                                                     # the ramps are shared by every frame


EXAMPLES = {"potion": potion, "sword": sword, "heart": heart, "slime": slime_anim, "tree": tree, "chest": chest, "hero": hero, "cat": cat, "knight": knight_anim, "dir8": lambda: adventurer8(dirs=("SE",))["SE"], "coin": coin_anim, "flame": flame_anim, "logo": logo, "scene": scene}
