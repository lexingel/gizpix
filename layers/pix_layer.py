# SPDX-License-Identifier: AGPL-3.0-or-later
"""pix_layer.py - cut an outfit layer out of a generated outfit sprite, with the "new colour" clean-up.

  python pix_layer.py cut BASE_DIR OUTFIT_DIR OUT_DIR --name robe [--drop-hue 0.02,0.10] [--solid] [--drop-skin 0.7|auto|near] [--outline] [--bits] [--drop-parts]
  python pix_layer.py selftest

BASE_DIR and OUTFIT_DIR hold the same-named PNGs per direction (south.png, east.png, ...).
Writes OUT_DIR/<name>/<direction>.png: the layer after clean-up, and prints raw -> clean pixel counts.

What it does (measured numbers: MEASUREMENTS.md, scripts in experiments/skeleton_v3):
  1. paperdoll.py extract per direction (difference to the base, detached bits under 5% dropped).
  2. Key = colours of the raw layers that are NOT in the base palette (appear >= 2 times over all directions),
     plus the dark outline (RGB sum < 150).
  3. Extract again, keeping only key colours.
--solid : for animation frames. Drops sparse specks (re-shaded skin) and small pieces; walk test: layer 530 -> ~310 px/frame, mostly skin gone, ~2 real px lost.
--outline : put back the layer's own dark 1 px outline (paperdoll.py's thin-line filter removes it). LPC test: shirt kept 86% -> see README.
--bits    : after --drop-skin, drop specks (<= 30 px groups) that look like body (hair, boots) and are nearer to the base colours than to the outfit. Skeleton-v3 walk test: removes the hair-red tips on pauldrons.
--drop-parts : after --bits: drop hair-tip and boot leaks that are attached to the outfit. From the base of the SAME direction it takes the hair (warm components that reach the upper 40% of the silhouette)
  and the boots (the lowest 12 rows), widens them by 3 px, and drops layer pixels in there whose colour lies on that part's own colour ramp (RGB < 45 and hue within 0.06, or both grey) and is nearer to it than to the
  outfit's own colours. A part is left alone (prints SKIP) when an outfit colour itself lies on its ramp (a dark brown robe over brown boots). Walk test (skeleton-v3, robe and pauldrons, south and east, 8 frames each):
  hair/boot leak 125 -> 0, 155 -> 4, 54 -> 0, 88 -> 0 (experiments/skeleton_v3/parts_check.py); 6, 1, 14, 1 genuine bright px lost; on the dark pair it drops 0 (guard). Does nothing for holes (dark skin east layer). ponytail: constants fixed, tune in code.
--drop-skin V : for animation frames, drop bright orange skin tones (hue<=0.10, sat>0.3, value>V; 0.7 worked); use with --solid. Walk test pair 1: 530 -> 199 px/frame, hand-made cuirass layer 205 px, 1.75 extra, 6 lost.
--drop-skin near : learn the body colours from the base itself (any hue: green, grey, dark skin too) and drop layer pixels within RGB distance 40 of them.
  All --drop-skin modes refuse to delete more than 40% of a frame's layer (prints WARNING, keeps the frame as it was).
--drop-hue LO,HI : also drop novel colours that are saturated (>0.5) and bright (>0.35) with a hue in that range (0..1). The base character's hair is
  redrawn in slightly new shades by the generator, so they count as "new"; the test used 0.02,0.10 (orange).
Costs: 12-23% of the real layer pixels were lost too (neck, shading). Does not work when the outfit colour is
the same as the base colour (not tested). Local, free, copies only.
"""
import os, sys, json, glob, shutil, subprocess, tempfile, colorsys, collections
import numpy as np
from PIL import Image

DOMINANT = 0.10  # a colour holding this share of all layer pixels counts as outfit for --drop-skin near
MAX_DROP = 0.6   # --drop-skin may remove at most 40% of a layer; more means it is eating the outfit, so it is skipped
def _die(msg):
    """one-line error on stderr, exit 2 (usage / input problems)"""
    print(msg, file=sys.stderr); sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
EXTRACT = os.path.join(HERE, "paperdoll.py")

def _extract(base, edit, out, extra=()):
    r = subprocess.run([sys.executable, EXTRACT, "extract", base, edit, "--out", out, "--spur", "0.05", *extra],
                       capture_output=True, text=True)
    try:
        rep_ = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        raise SystemExit("paperdoll.py failed: " + (r.stdout + r.stderr)[-300:])
    if not os.path.exists(os.path.join(out, "layer.layer.png")):                  # a hard failure (size mismatch, base == outfit): say so in paperdoll's own words
        _die(f"pix_layer: {os.path.basename(edit)} against {os.path.basename(base)}: " + "; ".join(rep_.get("fails") or ["no layer was produced"]))
    return rep_

def _colours(img):
    a = np.array(Image.open(img).convert("RGBA"))
    return [tuple(int(v) for v in p) for p in a[a[..., 3] > 0][:, :3]]

def _in_hue(c, hue):
    if not hue: return False
    h, sat, val = colorsys.rgb_to_hsv(*[x / 255 for x in c])
    return hue[0] <= h <= hue[1] and sat > 0.5 and val > 0.35

def solid_only(path, neigh=4, share=0.3):
    """Animation frames: the generator re-shades the skin each frame, which leaks as sparse specks. Keep only dense parts:
    twice drop pixels with < `neigh` of 8 neighbours, then drop pieces smaller than `share` of the biggest piece."""
    from scipy.ndimage import convolve, label
    a = np.array(Image.open(path).convert("RGBA")); k = a[..., 3] > 0; K = np.ones((3, 3)); K[1, 1] = 0
    for _ in range(2): k &= convolve(k.astype(int), K, mode="constant") >= neigh
    if k.any():
        lab, _ = label(k, np.ones((3, 3))); sz = np.bincount(lab.ravel())[1:]
        k = np.isin(lab, [j + 1 for j, z in enumerate(sz) if z >= share * sz.max()])
    a[~k] = 0; Image.fromarray(a).save(path)

def _hsv(rgb):
    rgb = rgb / 255.0; mx = rgb.max(-1); mn = rgb.min(-1); d = np.maximum(mx - mn, 1e-6); r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6
    return h, np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0), mx

def auto_skin(base_dir):
    """Learn the skin from the base itself: its orange-ish, not-dark pixels (hue <= 0.12, value > 0.4). Returns (hue_hi, sat_lo, sat_hi, vthr) where
    vthr = 0.72 x the median value of those pixels (0.82 left skin on pair 2; 0.72 gives ~0.62 on pair 1 and ~0.69 on pair 2)."""
    px = np.concatenate([np.array(Image.open(q).convert("RGBA"))[np.array(Image.open(q).convert("RGBA"))[..., 3] > 0][:, :3] for q in glob.glob(os.path.join(base_dir, "*.png"))])
    h, sat, v = _hsv(px.astype(float)); m = (h <= 0.12) & (v > 0.4) & (sat > 0.15)
    if m.sum() < 20: return None
    return (0.12, float(np.percentile(sat[m], 3)) * 0.85, float(np.percentile(sat[m], 97)) * 1.15, float(np.median(v[m])) * 0.72)

def restore_outline(path, base_png, outfit_png, rounds=2):
    """paperdoll.py drops thin lines (a 1 px outline is never part of a 2x2 block), so a layer loses its own dark outline (14% of a test shirt).
    Put back every pixel that (a) differs between outfit and base, (b) is dark (RGB sum < 150) and (c) touches the layer (8 neighbours). Bounded by the real diff, so
    it cannot invent pixels; it can add outline-coloured pixels of the body that merely changed shade next to the layer."""
    from scipy.ndimage import binary_dilation
    L = np.array(Image.open(path).convert("RGBA")); o = np.array(Image.open(outfit_png).convert("RGBA")); b = np.array(Image.open(base_png).convert("RGBA"))
    diff = (o[..., 3] > 0) & ((b[..., 3] == 0) | (np.abs(o[..., :3].astype(int) - b[..., :3]).sum(-1) >= 1)); dark = o[..., :3].astype(int).sum(-1) < 150
    have = L[..., 3] > 0
    for _ in range(rounds):
        add = diff & dark & ~have & binary_dilation(have, np.ones((3, 3), bool)); have = have | add
    new = have & ~(L[..., 3] > 0); L[new] = o[new]; Image.fromarray(L).save(path)

def base_palette(base_dir, min_n=3):
    """Colours the base body really uses (skin, hair, eyes; dark outline excluded), from all directions. The base has no outfit, so these ARE the body colours."""
    c = collections.Counter()
    for q in glob.glob(os.path.join(base_dir, "*.png")): c.update(_colours(q))
    return np.array([k for k, n in c.items() if n >= min_n and sum(k) >= 150], float)

def _dist(a, pal): return np.sqrt(((a[..., None, :3].astype(float) - pal[None, None]) ** 2).sum(-1)).min(-1)

def outfit_core(paths, pal, thr):
    """Label the outfit's own colours: layer colours (over all directions) that are far (>= 2 x thr) from every body colour. These are surely outfit."""
    c = collections.Counter()
    for q in paths: c.update(_colours(q))
    cols = np.array([k for k, n in c.items() if n >= 2], float)
    if not len(cols): return np.zeros((0, 3))
    dist = np.sqrt(((cols[:, None] - pal[None]) ** 2).sum(-1)).min(-1); tot = sum(c.values())
    big = np.array([c[tuple(int(v) for v in k)] >= DOMINANT * tot for k in cols]) & (dist >= 12)   # a flat colour that fills the layer is the outfit, even if it resembles skin
    return cols[(dist >= 2 * thr) | big]

def drop_near(path, pal, thr, core=None):
    """Compare each layer pixel with two labelled colour sets: BODY (the base's own colours) and OUTFIT (the confident outfit colours).
    A pixel goes only if it is within `thr` of a body colour AND nearer to the body set than to the outfit set. The generator re-shades the body
    slightly, it does not recolour it, so a re-shaded skin pixel is close to skin; a shade of a leather shirt is closer to the shirt's own colours.
    Works for any skin hue. Without an outfit set it falls back to the distance rule alone."""
    a = np.array(Image.open(path).convert("RGBA")); m = a[..., 3] > 0
    d = _dist(a, pal); gone = m & (d < thr)
    if core is not None and len(core): gone &= d < _dist(a, core)
    a[gone] = 0; Image.fromarray(a).save(path)

def drop_bits(path, pal, core, thr=45.0, maxsz=30):
    """Leaks that survive --drop-skin are hair and boot pixels the generator re-drew a little differently. Take the layer pixels that look like body (within `thr` of a
    base colour and nearer to it than to the outfit's own colours), group touching ones, and drop the groups of <= `maxsz` pixels that stick out of the layer (under half of their surrounding ring is layer). A big body-coloured piece (steel next to a
    grey shirt) is kept: only specks go."""
    from scipy.ndimage import label
    a = np.array(Image.open(path).convert("RGBA")); m = a[..., 3] > 0
    if not m.any(): return
    d = _dist(a, pal); body = m & (d < thr) & (a[..., :3].astype(int).sum(-1) >= 150)          # dark pixels are outline, never a leak
    if core is not None and len(core): body &= d < _dist(a, core)
    lab, n = label(body, np.ones((3, 3)))
    from scipy.ndimage import binary_dilation
    for j in range(1, n + 1):
        g = lab == j
        if g.sum() > maxsz: continue
        ring = binary_dilation(g, np.ones((3, 3), bool)) & ~g
        if (ring & m).sum() < 0.5 * ring.sum(): a[g] = 0          # sticks out of the layer: a leak. A body-coloured detail inside the outfit (a gold belt) is surrounded by it and stays
    Image.fromarray(a).save(path)

def _warm(a, sat=0.25):
    h, s, _ = _hsv(a[..., :3].astype(float)); return (a[..., 3] > 0) & ((h <= 0.12) | (h >= 0.95)) & (s > sat) & (a[..., :3].astype(int).sum(-1) >= 60)

def _ramp_dist(px, ramp, dh=0.06):
    """RGB distance to the nearest ramp colour whose hue is within dh of the pixel's (circular), or both are grey (sat < 0.2); 1e9 when none qualifies"""
    if not len(ramp): return np.full(px.shape[:-1], 1e9)
    hp, sp, _ = _hsv(px.astype(float)); hr, sr, _ = _hsv(ramp.astype(float))
    dd = np.sqrt(((px[..., None, :].astype(float) - ramp[None, None]) ** 2).sum(-1)); dhue = np.abs(hp[..., None] - hr[None, None]); dhue = np.minimum(dhue, 1 - dhue)
    return np.where((dhue <= dh) | ((sp[..., None] < 0.2) & (sr[None, None] < 0.2)), dd, 1e9).min(-1)

def drop_parts(path, base_png, core, R=3, T=45.0, hair_top=0.4, boot_rows=12):
    """Hair tips and boot slivers that hang on the outfit. Parts come from the base frame itself: hair = warm 8-connected components (>= 40 px) that reach the top 40% of the silhouette, boots = its lowest
    `boot_rows` rows. A layer pixel goes if it lies within R px of a part, its colour is on that part's ramp (distance < T, same hue) and nearer to it than to the outfit core `core`.
    A part whose ramp contains an outfit colour is skipped. Returns {part: pixels dropped or 'SKIP'}."""
    from scipy.ndimage import label, binary_dilation
    a = np.array(Image.open(path).convert("RGBA")); base = np.array(Image.open(base_png).convert("RGBA")); m = a[..., 3] > 0; info = {}
    bm = (base[..., 3] > 0) & (base[..., :3].astype(int).sum(-1) >= 90)                    # outline is not a body part
    if not m.any() or not bm.any(): return info
    ys = np.nonzero(bm.any(1))[0]; top, bot = ys.min(), ys.max(); parts = []
    lab, n = label(_warm(base) & bm, np.ones((3, 3)))
    for j in range(1, n + 1):
        g = lab == j
        if g.sum() >= 40 and np.nonzero(g.any(1))[0].min() < top + hair_top * (bot - top): parts.append(("hair", g))
    parts.append(("boots", bm & (np.arange(base.shape[0])[:, None] > bot - boot_rows)))
    dcore = _dist(a, core) if core is not None and len(core) else np.full(m.shape, 1e9); gone = np.zeros_like(m)
    for name, g in parts:
        ramp = np.unique(base[g][:, :3], axis=0).astype(float)
        if core is not None and len(core) and (_ramp_dist(core[None].astype(np.uint8), ramp) < T).any(): info[name] = "SKIP"; continue
        hit = m & binary_dilation(g, np.ones((3, 3), bool), iterations=R) & (_ramp_dist(a[..., :3], ramp) < T) & (_ramp_dist(a[..., :3], ramp) < dcore) & ~gone
        gone |= hit; info[name] = int(info.get(name, 0) if isinstance(info.get(name, 0), int) else 0) + int(hit.sum())
    a[gone] = 0; Image.fromarray(a).save(path); return info

def drop_skin(path, spec):
    """Skin leaks as bright orange tones. spec = a number (value threshold; hue <= 0.10, sat > 0.3) or the tuple from auto_skin
    (hue <= hi, sat inside the base skin's range, value > vthr). Leather/cloth in the same hue is darker or more saturated."""
    if isinstance(spec, dict): return drop_near(path, spec["pal"], spec["thr"], spec.get("core"))
    a = np.array(Image.open(path).convert("RGBA")); h, sat, v = _hsv(a[..., :3].astype(float))
    if isinstance(spec, tuple): hi, slo, shi, vt = spec; m = (h <= hi) & (sat >= slo) & (sat <= shi) & (v > vt)
    else: m = (h <= 0.10) & (sat > 0.3) & (v > spec)
    a[m] = 0; Image.fromarray(a).save(path)

def cut(base_dir, outfit_dir, out_dir, name, drop_hue=None, solid=False, skin_v=None, outline=False, bits=False, parts=False):
    if skin_v == "near":
        pal = base_palette(base_dir); skin_v = {"pal": pal, "thr": 40.0} if len(pal) else None; print("near skin: %d body colours" % len(pal))
    elif skin_v == "auto":
        skin_v = auto_skin(base_dir); print("auto skin:", tuple(round(v, 2) for v in skin_v) if skin_v else None)
        if skin_v and skin_v[3] < 0.5: print("WARNING: dark skin (threshold %.2f): the colour rule would drop dark outfit pixels (a dark brown robe lost 60%% of its pixels in the skeleton-v3 test) while a plain cut leaks little on dark skin, so --drop-skin is skipped" % skin_v[3]); skin_v = None
    for d_ in (base_dir, outfit_dir):
        if not os.path.isdir(d_): _die(f"pix_layer: not a folder: {d_}  (BASE_DIR and OUTFIT_DIR are folders of same-named PNGs)")
    dirs = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(outfit_dir, "*.png")))
    if not dirs: _die("pix_layer: no PNGs in " + outfit_dir)
    unpaired = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(base_dir, "*.png")) if os.path.splitext(os.path.basename(p))[0] not in dirs)
    if unpaired: print(f"pix_layer: WARNING: {len(unpaired)} PNG(s) in the base folder have no outfit partner and are skipped: {', '.join(unpaired[:6])}{' ...' if len(unpaired) > 6 else ''}", file=sys.stderr)
    for d_ in dirs:
        bp, op = os.path.join(base_dir, d_ + ".png"), os.path.join(outfit_dir, d_ + ".png")
        if not os.path.exists(bp): _die(f"pix_layer: {d_}.png is in the outfit folder but not in the base folder {base_dir}")
        sb, so = Image.open(bp).size, Image.open(op).size
        if sb != so: _die(f"pix_layer: {d_}.png has size {sb[0]}x{sb[1]} in the base but {so[0]}x{so[1]} in the outfit folder")
    work = tempfile.mkdtemp(prefix="pixlayer_")
    base_pal = set()
    for d in dirs: base_pal |= set(_colours(os.path.join(base_dir, d + ".png")))
    count = collections.Counter()
    for d in dirs:
        out = os.path.join(work, "raw", d)
        _extract(os.path.join(base_dir, d + ".png"), os.path.join(outfit_dir, d + ".png"), out)
        count.update(_colours(os.path.join(out, "layer.layer.png")))
    keep = [c for c, n in count.items() if n >= 2 and ((c not in base_pal and not _in_hue(c, drop_hue)) or sum(c) < 150)]
    if not keep: raise SystemExit("no colours left in the key: the outfit looks like the base")
    key = np.zeros((1, len(keep), 4), np.uint8)
    for i, c in enumerate(keep): key[0, i] = (*c, 255)
    keyf = os.path.join(work, "key.png"); Image.fromarray(key).save(keyf)
    os.makedirs(os.path.join(out_dir, name), exist_ok=True)
    raw_px = clean_px = 0
    for d in dirs:
        out = os.path.join(work, "clean", d)
        _extract(os.path.join(base_dir, d + ".png"), os.path.join(outfit_dir, d + ".png"), out, ("--keep-palette", keyf, "--key-tol", "1"))
        shutil.copy(os.path.join(out, "layer.layer.png"), os.path.join(out_dir, name, d + ".png"))
    if isinstance(skin_v, dict): skin_v["core"] = outfit_core([os.path.join(out_dir, name, d + ".png") for d in dirs], skin_v["pal"], skin_v["thr"])
    if bits or parts:
        bpal = base_palette(base_dir); bcore = outfit_core([os.path.join(out_dir, name, d + ".png") for d in dirs], bpal, 45.0) if len(bpal) else None
        if not len(bpal): bits = parts = False
    for d in dirs:
        if skin_v:
            lp = os.path.join(out_dir, name, d + ".png"); before = len(_colours(lp)); keep_copy = lp + ".bak"; shutil.copy(lp, keep_copy); drop_skin(lp, skin_v)
            after = len(_colours(lp))
            if before and after < MAX_DROP * before:
                shutil.copy(keep_copy, lp); print(f"WARNING: --drop-skin would delete {100 - 100 * after / before:.0f}% of {d}, skipped (outfit colour looks like skin)")
            os.remove(keep_copy)
        if bits: drop_bits(os.path.join(out_dir, name, d + ".png"), bpal, bcore)
        if parts:
            info = drop_parts(os.path.join(out_dir, name, d + ".png"), os.path.join(base_dir, d + ".png"), bcore)
            if info: print(f"{d}: parts " + ", ".join(f"{k} {v}" for k, v in info.items()))
        if solid: solid_only(os.path.join(out_dir, name, d + ".png"))
        if outline: restore_outline(os.path.join(out_dir, name, d + ".png"), os.path.join(base_dir, d + ".png"), os.path.join(outfit_dir, d + ".png"))
        raw_px += len(_colours(os.path.join(work, "raw", d, "layer.layer.png")))
        clean_px += len(_colours(os.path.join(out_dir, name, d + ".png")))
    shutil.rmtree(work, ignore_errors=True)
    print(f"{name}: {len(dirs)} files, key {len(keep)} colours, layer pixels raw {raw_px} -> clean {clean_px}")

def selftest():
    t = tempfile.mkdtemp(prefix="pixlayer_t_")
    for sub in ("base", "edit"): os.makedirs(os.path.join(t, sub))
    hair, hair2, blue, line = (200, 100, 20, 255), (210, 110, 25, 255), (30, 60, 160, 255), (10, 5, 5, 255)
    for d in ("south", "east"):
        b = np.zeros((24, 24, 4), np.uint8); b[4:20, 8:16] = (120, 120, 120, 255); b[2:6, 8:16] = hair
        e = b.copy(); e[2:6, 8:16] = hair2; e[10:19, 7:17] = blue; e[10:19, 7] = line; e[10:19, 16] = line  # outfit + redrawn hair
        Image.fromarray(b).save(os.path.join(t, "base", d + ".png")); Image.fromarray(e).save(os.path.join(t, "edit", d + ".png"))
    cut(os.path.join(t, "base"), os.path.join(t, "edit"), os.path.join(t, "out"), "robe", (0.02, 0.10))
    for d in ("south", "east"):
        a = np.array(Image.open(os.path.join(t, "out", "robe", d + ".png")).convert("RGBA")); m = a[..., 3] > 0
        assert m.any(), "layer empty"
        cols = {tuple(p) for p in a[m][:, :3]}
        assert (30, 60, 160) in cols, "outfit colour lost"
        assert (210, 110, 25) not in cols, "redrawn hair leaked"
    # --drop-parts: a hair tip and a boot sliver hang on the robe (new shades, touching it); a gold belt over the torso must stay; a robe in the boots' colour must switch the part off
    def parts_case(robe, tag):
        for sub in ("pb", "pe"): os.makedirs(os.path.join(t, tag + sub), exist_ok=True)
        hairc, boot, grey = (200, 100, 20, 255), (90, 50, 20, 255), (120, 120, 120, 255)
        b = np.zeros((48, 32, 4), np.uint8); b[6:45, 12:20] = grey; b[2:9, 11:21] = hairc; b[40:47, 11:21] = boot
        e = b.copy(); e[12:37, 10:22] = robe; e[22:24, 10:22] = (190, 150, 40, 255); e[9:13, 10:14] = (208, 108, 24, 255); e[37:41, 11:15] = (92, 52, 22, 255)
        Image.fromarray(b).save(os.path.join(t, tag + "pb", "south.png")); Image.fromarray(e).save(os.path.join(t, tag + "pe", "south.png"))
        res = {}
        for flag in (False, True):
            cut(os.path.join(t, tag + "pb"), os.path.join(t, tag + "pe"), os.path.join(t, tag + "po"), "L", parts=flag); res[flag] = np.array(Image.open(os.path.join(t, tag + "po", "L", "south.png")).convert("RGBA"))
        return res
    r = parts_case((30, 60, 160, 255), "blue")
    assert r[False][9:13, 10:14, 3].any() and r[False][37:41, 11:15, 3].any(), "the test leaks are not in the plain cut"
    assert not r[True][9:11, 10:14, 3].any() and not r[True][38:41, 11:15, 3].any(), "hair tip / boot sliver not dropped"
    assert (r[True][22:24, 12:20, 3] > 0).all() and (r[True][14:20, 12:20, 3] > 0).all(), "belt or robe lost"
    r = parts_case((110, 64, 30, 255), "brown")
    assert r[True][38:41, 11:15, 3].any() and not r[True][9:11, 10:14, 3].any(), "a robe on the boots' ramp must switch only the boot part off (hair still works)"
    shutil.rmtree(t, ignore_errors=True); print("selftest ok")

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["selftest"]: selftest()
    elif a[:1] == ["cut"] and len(a) >= 4:
        KNOWN = {"--name", "--drop-hue", "--drop-skin", "--solid", "--outline", "--bits", "--drop-parts"}; bad = [x for x in a[4:] if x.startswith("--") and x not in KNOWN]
        if bad: _die(f"pix_layer: unknown option {bad[0]!r}; known: {', '.join(sorted(KNOWN))}")
        def val(flag, cast=str):
            if flag not in a: return None
            i = a.index(flag) + 1
            if i >= len(a) or a[i].startswith("--"): _die(f"pix_layer: {flag} needs a value")
            try: return cast(a[i])
            except ValueError: _die(f"pix_layer: bad value for {flag}: {a[i]!r}" + (" (wants LO,HI e.g. 0.02,0.10)" if flag == "--drop-hue" else ""))
        def _hue(v):
            t = tuple(float(x) for x in v.split(","))
            if len(t) != 2: raise ValueError
            return t
        name = val("--name") or "layer"; hue = val("--drop-hue", _hue)
        skin = val("--drop-skin", lambda v: v if v in ("auto", "near") else float(v))
        cut(a[1], a[2], a[3], name, hue, "--solid" in a, skin, "--outline" in a, "--bits" in a, "--drop-parts" in a)
    else: print(__doc__); sys.exit(0 if a[:1] in (["-h"], ["--help"]) else 2)
