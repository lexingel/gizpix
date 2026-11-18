"""Village parallax v3: loop-locked layer widths (the whole stack closes after 2880 frames = 48 s, so the GIF is a real one-way loop), props/lamps/villagers placed in the gaps, no palette quantising, sun on the lit side.
Run: python build_village3.py OUT_DIR [seed]"""
import sys, os, json, math, subprocess, shutil, collections, glob
import numpy as np
from PIL import Image
_H = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.dirname(_H), os.path.join(os.path.dirname(_H), 'parallax'), _H]
import _layers as LY
from pixdraw import render
import props
import uniq

OUT = sys.argv[1]; SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1
os.makedirs(OUT, exist_ok=True)
VW, VH, HEAD = 320, 180, 24
H = VH + HEAD; W = 1440; NF = 8; WC, WM, WF = 360, 720, 1440      # widths: clouds, mountains, far village + orchard; street + foreground use W. Each divides (px per frame x 2880)
P = dict(LY.HOURS["noon"]); P.update(dict(top="#4f94dc", mid="#98cdee", bottom="#f7eecb", haze="#dbe7e6", light="#fff0bd", shadow="#37497c", cloud="#ffffff"))
R = np.random.default_rng(SEED)


def haze(im, t):
    a = np.array(im.convert("RGBA")); m = a[..., 3] > 0; hz = np.array(LY.hexc(P["haze"]), float)
    lum = a[..., :3].astype(float) @ [0.3, 0.59, 0.11] / 255; tt = np.where(m & (lum < 0.33) & (t >= 0.3), min(1.0, t + 0.35), t)[..., None]   # far outlines fade into the haze
    a[..., :3] = np.where(m[..., None], np.round(a[..., :3] * (1 - tt) + hz * tt), a[..., :3]).astype(np.uint8); return Image.fromarray(a)


def stamp(layer, im, x, base_y):
    Wl = layer.width
    for dx in (-Wl, 0, Wl):
        if -im.width < x + dx < Wl:
            layer.alpha_composite(im, (int(x + dx), int(base_y - im.height)))


import colorsys
_hc = {}


def roof_hue(frames, hue):
    """give a building another roof (and awning) colour: pixels that are red (hue near 0, saturated) take the target hue, same saturation and value; one source colour becomes one new colour"""
    out = []
    for im in frames:
        a = np.array(im.convert("RGBA")); m = a[..., 3] > 0
        for c in {tuple(v) for v in a[m][:, :3]}:
            if (c, hue) not in _hc:
                h, sa, v = colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255); red = (h < 0.045 or h > 0.95) and sa > 0.35
                _hc[(c, hue)] = tuple(int(round(q * 255)) for q in colorsys.hsv_to_rgb(hue, sa, v)) if red else c
        flat = a[..., :3].reshape(-1, 3); mm = m.reshape(-1)
        for c in {tuple(v) for v in flat[mm]}:
            if _hc[(c, hue)] != c:
                sel = mm & (flat == np.array(c)).all(1); flat[sel] = _hc[(c, hue)]
        a[..., :3] = flat.reshape(a.shape[0], a.shape[1], 3); out.append(Image.fromarray(a))
    return out


HUES = [0.0, 0.0, 0.58, 0.35, 0.08, 0.75, 0.12]                                 # red twice as likely; blue, green, orange-brown, purple, yellow-brown


def contour(arr):
    return np.argmax(arr[..., 3] > 0, 0)


layers = []


def save(name, frames, sx, sy, pf, depth, dc, fe=10):
    frames = frames if isinstance(frames, list) else [frames]
    for i, f in enumerate(frames):
        (f if isinstance(f, Image.Image) else Image.fromarray(f)).save(os.path.join(OUT, name + ("" if i == 0 else "_%d" % i) + ".png"))
    d = dict(file=name + ".png", scroll=[sx, sy], px_per_frame=pf, depth=depth, depth_check=dc, repeat="x")
    if len(frames) > 1:
        d["frames"] = [name + "_%d.png" % i for i in range(1, len(frames))]; d["frame_every"] = fe
    layers.append(d)


WALLS = ["plaster", "planks", "brick", "stone"]; ROOFS = ["shingles", "tiles", "thatch"]


def house_spec(kind, small=False):
    """a random building spec: type, wall and roof material, size and details"""
    sp = {"proj": "side", "type": kind, "wall": str(R.choice(WALLS)), "roof_mat": str(R.choice(ROOFS))}
    if kind in ("house", "cottage"):
        sp["roof"] = "hip" if R.random() < 0.25 else "gable"
        if small:
            sp.update({"W": int(R.integers(20, 28)), "D": int(R.integers(12, 15)), "fh": 14, "floors": 1})
        else:
            sp.update({"W": int(R.integers(34, 54)), "D": int(R.integers(16, 26)), "fh": int(R.integers(17, 22)), "floors": 2 if (kind == "house" and R.random() < 0.4) else 1})
        if sp["roof"] == "hip" and sp.get("W", 40) < sp.get("D", 20):
            sp["W"] = sp["D"] + 2
        if R.random() < 0.7:
            sp.update({"chimney": True, "smoke": bool(R.random() < 0.7)})
    elif kind == "inn":
        sp.update({"lit": True, "lantern": bool(R.random() < 0.6), "smoke": bool(R.random() < 0.5)})
    elif kind == "stall":
        sp.update({"awning": True})
    return sp


# ---- sky, sun, clouds, mountains
save("sky", LY.sky(320, H, P, 6), 0, 0, 0, 100, False)
save("sun", LY.disc(320, H, P, np.random.default_rng(SEED + 1), HEAD, VH, cx=int(np.random.default_rng(SEED + 1).integers(40, 110))), 0, 0, 0, 99, False)
save("clouds", LY.clouds(WC, H, P, np.random.default_rng(SEED + 2), HEAD + 8, HEAD + 40, n=4), 0.0625, 0.0, 0.125, 90, False)
save("mountains", LY.mountains(WM, H, P, np.random.default_rng(SEED + 3), "#7b9ccf", 0.5, int(H * .60), int(H * .30), n_peaks=5, snow=True, fog=True), 0.125, 0.1, 0.25, 70, True)

# ---- far village: 18 small houses at random spots, two windmills
hills = Image.fromarray(LY.hills(WF, H, P, np.random.default_rng(SEED + 4), "#79ab69", 0.42, int(H * .72), int(H * .05), detail=0.0, harmonics=(1, 2, 3)))
ground = contour(np.array(hills))
variants = []
for i in range(10):
    kind = "cottage" if i % 3 == 0 else "house"; variants.append([haze(f, 0.40) for f in roof_hue(render(house_spec(kind, small=True), "bright_cartoon", frames=NF), float(R.choice(HUES)))])
mills = [haze(props.windmill(f / NF, 0.62).image(1), 0.36) for f in range(NF)]
mills2 = [haze(props.windmill(((f / NF) + 0.5) % 1.0, 0.5).image(1), 0.38) for f in range(NF)]
spots = []; x = 10
while x < WF - 30:
    spots.append(x); x += int(R.integers(40, 96))
vidx = [(k * 7 + int(R.integers(0, 3))) % len(variants) for k in range(len(spots))]
mill_at = {int(R.integers(2, len(spots) // 2)): mills, int(R.integers(len(spots) // 2 + 1, len(spots) - 1)): mills2}
frames = []
for f in range(NF):
    L_ = hills.copy()
    for k, x in enumerate(spots):
        if k in mill_at:
            im = mill_at[k][f]
        else:
            im = variants[vidx[k]][f]
        stamp(L_, im, x, ground[(x + im.width // 2) % WF] + 3)
    frames.append(L_)
save("far_village", frames, 0.25, 0.25, 0.5, 50, True)

# ---- orchard
save("orchard", LY.trees(WF, H, P, np.random.default_rng(SEED + 5), "#5a9a70", 0.35, int(H * .835), hmin=22, hmax=40, n_clusters=10, per=3, loners=8, broadleaf=0.9, ground_t=0.45), 0.5, 0.45, 1, 30, True)

# ---- main street
YG = int(H * .90)
road = np.zeros((H, W, 4), np.uint8); yy, xx = np.mgrid[0:H, 0:W]
grass = LY.ramp("#58a84a", 0.0, P); dirt = LY.ramp("#c9a070", 0.0, P)
road[yy >= YG] = (*dirt[2], 255); road[(yy >= YG) & (yy < YG + 2)] = (*grass[3], 255); road[(yy >= YG + 2) & (yy < YG + 4)] = (*grass[2], 255)
road[(yy >= YG + 4) & (yy < YG + 5) & ((xx + yy) % 2 == 0)] = (*grass[1], 255)
rr = np.random.default_rng(SEED + 6)
for _ in range(260):
    x, y = int(rr.integers(0, W)), int(rr.integers(YG + 6, H - 1)); road[y, x:x + int(rr.integers(1, 3))] = (*dirt[1 if rr.random() < .6 else 3], 255)
road[(yy >= H - 8) & (yy < H - 7) & ((xx + yy) % 2 == 0)] = (*dirt[1], 255); road[yy >= H - 7] = (*dirt[1], 255)
street_base = Image.fromarray(road)

SPECIAL_AT = {1: "church", 3: "barn", 6: "townhall", 8: "smithy", 9: "bakery", 12: "inn_big"}    # one-off buildings at fixed positions in the row
KINDS = ["house", "house", "cottage", "cottage", "inn", "stall", "house", "tower"]
buildings = []                                                                  # (frames, x)
x = 6; last_kind = None; towers = 0; EVENTS = {5, 11}; event_gaps = set()
while x < W - 70:
    kind = str(R.choice(KINDS)); sp_name = SPECIAL_AT.get(len(buildings))
    if kind == last_kind or (kind == "tower" and towers >= 2):
        kind = "house"
    last_kind = kind; towers += kind == "tower"
    fr = roof_hue(uniq.special(sp_name, NF) if sp_name else render(house_spec(kind), "bright_cartoon", frames=NF), float(R.choice(HUES))); w = fr[0].width
    if x + w > W + 4:
        break
    buildings.append((fr, x)); x += w + int(R.integers(8, 44))
    if len(buildings) in EVENTS:
        x += 100; event_gaps.add(len(buildings) - 1)                                # a field: an extra 100 px gap
gaps = []                                                                       # free spans between buildings: (start, end)
for (fr, bx), (fr2, bx2) in zip(buildings, buildings[1:] + [(buildings[0][0], buildings[0][1] + W)]):
    gaps.append((bx + fr[0].width, bx2))
prop_pool = [("fence_a", props.fence(5).image(1)), ("fence_b", props.fence(3).image(1)), ("hay", props.haystack().image(1)), ("cart", props.cart().image(1)), ("flowers", props.flowers(30).image(1)), ("bush", props.bush(26, 15, flowers="#f3d34a").image(1))]
placed = []; lamps = []; men_at = []
fence_a, fence_b = props.fence(5).image(1), props.fence(3).image(1); hay = props.haystack().image(1); cart = props.cart().image(1)
small = [("flowers", props.flowers(30).image(1)), ("bush", props.bush(26, 15, flowers="#f3d34a").image(1)), ("fence", fence_b), ("hay", hay)]
lamp_im = props.lamp(True, pole=14).image(1); well_im = props.well().image(1)
prop_y = {"cart": 9, "hay": 7}
for gi, (gs, ge) in enumerate(gaps):
    span = ge - gs
    if gi in event_gaps and span >= 100 and gi == min(event_gaps) :                 # a field: hay, a cart and a fence spread over the gap
        pass
    if gi in event_gaps and span >= 100 and gi != min(event_gaps):                  # a square: a well in the middle, a lamp and two villagers
        placed.append((well_im, gs + span // 2 - 13, YG + 8)); lamps.append(gs + 8)
        men_at += [gs + span // 2 - 30, gs + span // 2 + 24]; continue
    if gi in event_gaps and span >= 100:
        for im, nm, fx in ((fence_a, "fence", 0.0), (hay, "hay", 0.3), (cart, "cart", 0.6)):
            placed.append((im, gs + 6 + int((span - 40) * fx), YG + prop_y.get(nm, 6)))
        if len(men_at) < 6:
            men_at.append(ge - 16)
        continue
    if span < 12:
        continue
    roll = R.random()
    if roll < 0.30 and span >= 22:
        lamps.append(gs + span // 2 - 9)
    elif roll < 0.62 and span >= 26 and len(men_at) < 6:
        men_at.append(gs + span // 2)
    else:
        nm, im = small[int(R.integers(0, len(small)))]
        if im.width <= span + 6:
            placed.append((im, gs + max(0, (span - im.width) // 2), YG + prop_y.get(nm, 6)))
men_sets = [("#d05a4a", "#4a5a8a", "#5a3a2a"), ("#4a9a6a", "#6a4a3a", "#2a2a2a"), ("#e0b44c", "#5a4a7a", "#a06a3a"), ("#8a5ac0", "#3a4a3a", "#4a3a2a"), ("#e8e8e8", "#4a4a6a", "#8a8a8a"), ("#d07a3a", "#3a5a6a", "#5a2a1a")]
men = [(props.villager(0, m[0], m[1], hair=m[2], height=17, facing=(1 if i % 2 == 0 else -1)).image(1), props.villager(1, m[0], m[1], hair=m[2], height=17, facing=(1 if i % 2 == 0 else -1)).image(1), mx) for i, (m, mx) in enumerate(zip(men_sets, men_at))]
lamp_x = lamps
frames = []
for f in range(NF):
    L_ = street_base.copy()
    for fr, bx in buildings:
        stamp(L_, fr[f], bx, YG + 4)
    for im, px, py in placed:
        stamp(L_, im, px, py)
    for lxp in lamp_x:
        stamp(L_, lamp_im, lxp, YG + 5)
    for a_, b_, mx in men:
        stamp(L_, a_ if (f // 4) % 2 == 0 else b_, mx, YG + 8)
    frames.append(L_)
save("street", frames, 1.0, 0.8, 2, 10, True)

# ---- walkers: two layers that move with the street plus their own walking speed (0.5 px per frame = 30 px/s), whole-pixel, 8 walk frames of 4 engine frames each.
# Left walkers: screen speed 2.5 px/frame (7200 px per 2880 frames = 5 x W). Right walkers: 1.5 px/frame (4320 = 3 x W). Both close with the 2880-frame loop.
WALK = [("#d05a4a", "#4a5a8a", "#5a3a2a"), ("#4a9a6a", "#6a4a3a", "#2a2a2a"), ("#e0b44c", "#5a4a7a", "#a06a3a"), ("#8a5ac0", "#3a4a3a", "#4a3a2a"), ("#d07a3a", "#3a5a6a", "#5a2a1a"), ("#e8e8e8", "#4a4a6a", "#8a8a8a")]
for nm, face, pf, auto, who in (("walkers_l", -1, 2.5, 30, (0, 2, 4)), ("walkers_r", 1, 1.5, -30, (1, 3, 5))):
    base_x = sorted(int(R.integers(60, 420)) + k * 480 for k in range(3)); wf = []
    for f in range(NF):
        L_ = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for k, who_i in enumerate(who):
            sh, pa, ha = WALK[who_i]
            stamp(L_, props.villager(f, sh, pa, hair=ha, height=17, facing=face, action="walk").image(1), base_x[k], YG + 15)
        wf.append(L_)
    save(nm, wf, 1.0, 0.8, pf, 8, False, fe=4); layers[-1]["autoscroll_px_s"] = auto

# ---- foreground: random bushes and flowers at irregular spots
fg = Image.new("RGBA", (W, H), (0, 0, 0, 0)); fr_ = np.random.default_rng(SEED + 7); x = 8
while x < W:
    kind = int(fr_.integers(0, 4))
    im = props.bush(int(fr_.integers(16, 32)), int(fr_.integers(10, 18)), flowers=("#f3d34a" if kind == 0 else "#e8575a" if kind == 1 else None)).image(1) if kind < 3 else props.flowers(int(fr_.integers(20, 34))).image(1)
    stamp(fg, im, x, H + 1); x += im.width + int(fr_.integers(30, 150))
save("foreground", fg, 2.0, 0.9, 4, 0, False)

spec = {"name": "village", "viewport": [VW, VH], "fps": 60, "camera_px_per_s": 120, "background": "#4f94dc", "layers": layers}
json.dump(spec, open(os.path.join(OUT, "stack.json"), "w"), indent=1)


print("buildings", len(buildings), "far houses", len(spots), "props", len(placed), "lamps", len(lamp_x), "villagers", len(men))
