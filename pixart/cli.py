# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixart command line.
  python -m pixart new NAME [--size WxH] [--dir DIR]   write a starter drawing script DIR/NAME.py (then edit it and run it with python)
  python -m pixart examples [NAME ...] [--out DIR]      render the worked recipes (preview sheet, PNG, GIF for animations) and print their lint
  python -m pixart lint FILE.png [...]                  measure any PNG with the Gizpix pixel lint
  python -m pixart measure REF.png [--view OUT.png]     read an existing game image: size, palette (hex, dark to light), outline colours per side, light direction; --view writes an enlarged copy with a coordinate grid
  python -m pixart compare REF.png MINE.png [...] -o OUT.png   reference and your drawing(s) side by side at the same height on a dark neutral: LOOK at it every round
  python -m pixart refs [--style S11] [--subject sword] [--size 24-40] [--view icon] [--material iron] [--tier open,copyleft] [--n 24] [--out DIR] [--sheet OUT.png]
                                                       find hand-made reference sprites in the local collection (PixTools/refs, index.csv); --out copies them (then: look --ref DIR), --sheet draws a contact sheet
  python -m pixart look MINE.png [--ref DIR] [--style S11]     how hand-made it looks; --style measures against the style's profile from the collection (knowledge/style_profiles.json)
  python -m pixart cands A.png B.png [C.png] -o DIR [--style S11] [--axis roughness]   2-3 candidates on one numbered sheet for the user to pick from
  python -m pixart pick DIR/cands.json N [--judge user|claude|agent] [--note ...]      record the pick (knowledge/picks.jsonl)
  python -m pixart calibrate [--judge user]            how often the style distance agreed with the picks
  python -m pixart profiles                            re-measure knowledge/style_profiles.json from the refs (per style and size bucket)
  python -m pixart guide                              print KNOWLEDGE.md (the craft rules)      python -m pixart selftest"""
import argparse, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
STARTER = '''"""{name} - pixel art drawn with pixart. Run: python {name}.py   (writes out/{name}.png, out/{name}_preview.png)"""
import os, sys; sys.path.insert(0, r"{root}")
from pixart import Canvas, Ramp, ramp, shrink, grow, shift, flipx, sym, export, strip, text_size
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")      # next to this script, wherever it is run from

c = Canvas({w}, {h}, light="tl")                 # one light for everything: tl, tr, top, l, r, front or (lx, ly)
main = ramp("#c8402f", n=4, name="main")     # a ramp per material: base colour in, hue-shifted tones out

body = c.oval({bx}, {by}, {bw}, {bh})                   # 1. silhouette first: build the big masses as masks
c.fill(body, main, form="ball", rim=True)    # 2. paint each part with a form (flat ball tube puff slab grad bands)
c.put(["aa", "a."], {{"a": (main, 3)}}, {gx}, {gy})   # 3. hand-placed pixels last: glints, eyes, small marks
c.outline("selout")                          # 4. outline pass (selout | dark | black), then look and measure

c.lint()
c.preview(OUT + "/{name}_preview.png")         # LOOK at this file: big view, 1x on three backgrounds, silhouette, greyscale, palette
c.save(OUT + "/{name}.png"); c.save(OUT + "/{name}_x8.png", scale=8)
'''


BG = (58, 56, 62, 255)


def measure(path, view=None, scale=8, rows=False):
    """print what a drawing must match in an existing image; optionally write an enlarged view with a grid line and a number every 8 px"""
    import numpy as np
    from PIL import Image, ImageDraw
    from scipy import ndimage as ndi
    im = Image.open(path).convert("RGBA"); a = np.array(im).astype(int); op = a[..., 3] > 0; L = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]; ys, xs = np.nonzero(op)
    hx = lambda c: "#%02x%02x%02x" % tuple(c)
    cols, cnt = np.unique(a[op][:, :3], axis=0, return_counts=True); top = sorted(np.argsort(-cnt)[:24], key=lambda i: L_of(cols[i]))
    print(f"{path}: {im.width}x{im.height}, drawn box x {xs.min()}-{xs.max()} y {ys.min()}-{ys.max()}, {int(op.sum())} px, {len(cols)} colours")
    print("  palette, dark to light (colour x pixels): " + " ".join(f"{hx(cols[i])}x{cnt[i]}" for i in top))
    edge = op & ~ndi.binary_erosion(op); inner = op & ~edge; ec, en = np.unique(a[edge][:, :3], axis=0, return_counts=True)
    print("  outline colours: " + " ".join(f"{hx(ec[i])}x{en[i]}" for i in np.argsort(-en)[:5]) + f"; edge brightness {L[edge].mean():.0f} vs inside {L[inner].mean():.0f}")
    ey, ex = np.nonzero(edge); cy, cx = ys.mean(), xs.mean()
    print("  edge brightness by side (a lighter side = light-aware outline or rim light): " + ", ".join(f"{n} {L[ey[k], ex[k]].mean():.0f}" for n, k in (("top", ey < cy), ("bottom", ey >= cy), ("left", ex < cx), ("right", ex >= cx)) if k.any()))
    iy, ix = np.nonzero(inner)
    if len(iy) > 8:
        kx, ky = np.corrcoef(L[inner], ix)[0, 1], np.corrcoef(L[inner], iy)[0, 1]; br = np.argsort(-L[inner])[:8]
        print(f"  light: brightness vs x {kx:+.2f}, vs y {ky:+.2f} (negative x = lit from the left, negative y = from the top; both near 0 = lit from inside or flat)")
        print("  brightest pixels (x, y): " + " ".join(f"({x},{y})" for x, y in zip(ix[br].tolist(), iy[br].tolist())))
    if rows:                                                  # the shape row by row: copy it into poly()/put() or compare your mask with it line by line
        print("  rows (y: first-last x of drawn pixels, gaps shown as separate runs):")
        for y in range(ys.min(), ys.max() + 1):
            xs_ = np.nonzero(op[y])[0]; runs = np.split(xs_, np.nonzero(np.diff(xs_) > 1)[0] + 1) if len(xs_) else []
            print(f"   {y:3d}: " + " ".join(f"{r[0]}-{r[-1]}" for r in runs))
    if view:
        bg = Image.new("RGBA", im.size, BG); bg.alpha_composite(im); big = bg.resize((im.width * scale, im.height * scale), Image.NEAREST); d = ImageDraw.Draw(big)
        for v in range(0, max(im.size), 8):
            d.line([(v * scale, 0), (v * scale, big.height)], fill=(255, 255, 255, 60)); d.line([(0, v * scale), (big.width, v * scale)], fill=(255, 255, 255, 60)); d.text((v * scale + 2, 1), str(v), fill=(255, 255, 0, 255)); d.text((1, v * scale + 1), str(v), fill=(255, 255, 0, 255))
        os.makedirs(os.path.dirname(os.path.abspath(view)), exist_ok=True); big.save(view); print("  view:", view)


def L_of(c): return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


LOOK = ("colours", "orphans", "small", "busy", "run", "step", "range", "edge")


def look(path):
    """numbers for how hand-made an image looks: colours, share of pixels with no same-colour neighbour (orphans), share in clusters of 1-3 px (small), share of pixels that touch another colour (busy), mean same-colour run length (run), mean brightness jump where two colours meet (step), brightness spread 5-95 % (range), outline brightness / inside brightness (edge)"""
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    a = np.array(Image.open(path).convert("RGBA")).astype(int); op = a[..., 3] > 0; n = max(1, int(op.sum()))
    key = np.where(op, (a[..., 0] << 16) | (a[..., 1] << 8) | a[..., 2], -1); L = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    same = np.zeros(op.shape, bool); diff = np.zeros(op.shape, bool); steps = []
    for ax in (0, 1):
        k0, k1 = (key[:-1], key[1:]) if ax == 0 else (key[:, :-1], key[:, 1:]); l0, l1 = (L[:-1], L[1:]) if ax == 0 else (L[:, :-1], L[:, 1:])
        s = (k0 == k1) & (k0 >= 0); d = (k0 != k1) & (k0 >= 0) & (k1 >= 0); steps.append(np.abs(l0 - l1)[d])
        for m, t in ((same, s), (diff, d)):
            if ax == 0: m[:-1] |= t; m[1:] |= t
            else: m[:, :-1] |= t; m[:, 1:] |= t
    small = 0
    for k in np.unique(key[op]):
        lab, c = ndi.label(key == k); sz = np.bincount(lab.ravel())[1:]; small += int(sz[sz <= 3].sum())
    runs = int(op.sum(1).astype(bool).sum() + ((key[:, 1:] != key[:, :-1]) & op[:, 1:]).sum() + op.sum(0).astype(bool).sum() + ((key[1:] != key[:-1]) & op[1:]).sum())
    edge = op & ~ndi.binary_erosion(op); inner = op & ~edge; st = np.concatenate(steps)
    return dict(colours=len(np.unique(key[op])), orphans=float((op & ~same).sum()) / n, small=small / n, busy=float(diff.sum()) / n, run=2 * n / max(1, runs),
                step=float(st.mean()) if len(st) else 0.0, range=float(np.percentile(L[op], 95) - np.percentile(L[op], 5)) if op.any() else 0.0,
                edge=float(L[edge].mean() / max(1.0, L[inner].mean())) if inner.any() else 1.0)


SIZES = ((24, "<=24"), (32, "25-32"), (48, "33-48"), (10 ** 6, ">48"))


def size_bucket(px):
    """the size bucket of a drawn size (long side of the opaque box, in px)"""
    return next(name for top, name in SIZES if px <= top)


def drawn_size(path):
    """long side of the opaque box of an image, in px"""
    from PIL import Image
    b = Image.open(path).convert("RGBA").getchannel("A").getbbox()
    return max(b[2] - b[0], b[3] - b[1]) if b else 0


def style_profile(code, size=None):
    """mean and spread of the look numbers for one style code, measured on the hand-made refs (knowledge/style_profiles.json); None for an unknown code.
    With size (px) the profile of that size bucket is used when the style has one (20+ sprites), else the whole style; p["bucket"] says which."""
    import json
    P = json.load(open(os.path.join(HERE, "knowledge", "style_profiles.json"), encoding="utf-8")); p = P.get(code.upper())
    if not p: return None
    b = size and p.get("by_size", {}).get(size_bucket(size))
    b = b if b and b.get("packs", 0) >= 2 else None              # one pack = one artist's habits, not the style's
    p = dict(p, **b, bucket=size_bucket(size)) if b else dict(p, bucket="all sizes" + (f" (no {size_bucket(size)} px profile from 2+ packs)" if size else ""))
    return [p["mean"][k] for k in LOOK], [max(p["sd"][k], 1e-6) for k in LOOK], p


def build_profiles(out=None, cap=60):
    """measure the hand-made refs (open + copyleft tiers, single frames) per style code and per size bucket, at most `cap` sprites per pack; writes knowledge/style_profiles.json"""
    import csv, json, collections
    import numpy as np
    rows = [r for r in csv.DictReader(open(os.path.join(REFS, "index.csv"), encoding="utf-8"))
            if r["pack"].split("/")[0] in ("open", "copyleft") and r["frames"] in ("", "1") and r["view"] != "screenshot"]
    by = collections.defaultdict(list)
    for r in rows:
        for c in r["style_code"].replace("+", "/").split("/"):
            if c.strip(): by[c.strip()].append(r)
    stat = lambda V: {"n": len(V), "mean": {k: round(float(m), 3) for k, m in zip(LOOK, V.mean(0))}, "sd": {k: round(float(d), 3) for k, d in zip(LOOK, V.std(0))},
                      "median": {k: round(float(m), 3) for k, m in zip(LOOK, np.median(V, 0))}}
    res = {}; memo = {}
    capped = lambda rows: [r for pk in sorted({x["pack"] for x in rows}) for g in [[x for x in rows if x["pack"] == pk]] for r in g[::max(1, len(g) // cap)][:cap]]

    def measure_rows(rs):
        vals, sizes, packs = [], [], collections.Counter()
        for r in rs:
            if r["file"] not in memo:
                try: v = look(os.path.join(REFS, r["file"])); memo[r["file"]] = [v[k] for k in LOOK]
                except Exception: memo[r["file"]] = None
            if memo[r["file"]]: vals.append(memo[r["file"]]); sizes.append(int(r["size_class"] or 0)); packs[r["pack"]] += 1
        return np.array(vals), np.array(sizes), packs
    for c in sorted(by):
        V, S, packs = measure_rows(capped(by[c]))
        bs = {}
        for b in (n for _, n in SIZES):                       # each size bucket sampled on its own (at most `cap` per pack inside the bucket)
            Vb, _, pb = measure_rows(capped([r for r in by[c] if size_bucket(int(r["size_class"] or 0)) == b]))
            if len(Vb) >= 20: bs[b] = dict(stat(Vb), packs=len(pb))   # style_profile uses a bucket only when it has 2+ packs
        res[c] = dict(stat(V), packs=len(packs), size_median=int(np.median(S)), size_p10_p90=[int(np.percentile(S, 10)), int(np.percentile(S, 90))],
                      thin=len(V) < 20, top_packs=[p for p, _ in packs.most_common(3)], by_size=bs)
        print(c, res[c]["n"], {b: v["n"] for b, v in res[c]["by_size"].items()}, flush=True)
    res = {"_about": f"look() numbers of hand-made refs per style code and per size bucket (long side of the drawn box; a bucket only with 20+ sprites), "
                     f"open+copyleft tiers, single frames, at most {cap} sprites per pack; rebuild with: python -m pixart profiles", **res}
    out = out or os.path.join(HERE, "knowledge", "style_profiles.json"); json.dump(res, open(out, "w", encoding="utf-8"), indent=1); return out


REFS = os.environ.get("PIXART_REFS", os.path.join(ROOT, "refs"))
TIERS = ("open", "copyleft", "private", "ai")


def no_ai(pack):
    """True when the pack's licence text (source.json, LICENSE*.txt) forbids AI / machine use: such packs are never offered as references"""
    import glob, re
    import json
    sj = os.path.join(REFS, pack, "source.json"); txt = json.load(open(sj, encoding="utf-8")).get("licence", "") if os.path.isfile(sj) else ""   # the licence field, not the collector's notes ("No generative AI was used" is a promise, not a ban)
    txt += " " + " ".join(open(f, encoding="utf-8", errors="ignore").read() for f in glob.glob(os.path.join(REFS, pack, "LICEN[CS]E*.txt")))
    return bool(re.search(r"AI[- ]training|NO-AI|train[^.]{0,40}(machine|[^a-z]AI[^a-z])", txt, re.I))


def refs(style=None, subject=None, size=None, view=None, material=None, tier="open,copyleft", n=24, out=None, sheet=None):
    """reference sprites from the local collection (REFS/index.csv). subject / view / material match as substrings (subject also matches subject_detail and the file name);
    size = "MIN-MAX" or "N" on the drawn size (long side). tier: open, copyleft, private (look only, never copy into a pack), ai (cleaned AI style cards, graded A/B) or all.
    Picks at most n, spread over packs. Returns the file paths."""
    import csv
    idx = os.path.join(REFS, "index.csv")
    if not os.path.isfile(idx): print(f"pixart refs: no collection at {REFS} (set PIXART_REFS)"); return []
    tiers = TIERS if tier == "all" else tuple(t.strip() for t in tier.split(","))
    lo, hi = (0, 10 ** 6) if not size else (lambda v: (int(v[0]), int(v[-1])))(str(size).split("-"))
    has = lambda v, q: not q or q.lower() in v.lower()
    rows = [r for r in csv.DictReader(open(idx, encoding="utf-8")) if r["pack"].split("/")[0] in tiers and (not style or style.upper() in r["style_code"].upper())
            and (not subject or any(has(r[k], subject) for k in ("subject", "subject_detail", "file"))) and has(r["view"], view) and has(r["material"], material)
            and lo <= int(r["size_class"] or 0) <= hi]
    packs = {}
    for r in rows: packs.setdefault(r["pack"], []).append(r)
    for pk in [pk for pk in packs if no_ai(pk)]: del packs[pk]; print(f"  skipped {pk}: its licence forbids AI use")
    rows = [r for v in packs.values() for r in v]
    pick = []; lists = [v[::max(1, len(v) // n)] for v in packs.values()]      # round-robin over packs so one big pack does not fill the list
    while len(pick) < n and any(lists): pick += [l.pop(0) for l in lists if l][:n - len(pick)]
    files = [os.path.join(REFS, r["file"]) for r in pick]
    print(f"{len(rows)} match in {len(packs)} packs; showing {len(files)}" + ("  (private tier: look only, never copy into a pack)" if any(r["pack"].startswith("private") for r in pick) else ""))
    for r, f in zip(pick, files): print(f"  {r['style_code']:4} {r['size_class']:>4}px {r['view']:13} {r['subject']}/{r['subject_detail']}  {f}" + (f"  [{r['notes'].split('grade=')[1][:1]}]" if "grade=" in r["notes"] else ""))
    if out:
        import shutil
        os.makedirs(out, exist_ok=True)
        for r, f in zip(pick, files): shutil.copy(f, os.path.join(out, r["id"].replace("/", "_") + ".png"))
        print("copied to", os.path.abspath(out), "-> python -m pixart look MINE.png --ref", out)
    if sheet and files:
        from PIL import Image
        ims = [Image.open(f).convert("RGBA") for f in files]; cell = 96; cols = min(8, len(ims))
        sh = Image.new("RGBA", (cols * (cell + 6) + 6, ((len(ims) + cols - 1) // cols) * (cell + 6) + 6), BG)
        for i, im in enumerate(ims):
            k = max(1, min(cell // im.width, cell // im.height)); im = im.resize((im.width * k, im.height * k), Image.NEAREST)
            if max(im.size) > cell: im.thumbnail((cell, cell), Image.NEAREST)
            sh.alpha_composite(im, (6 + (i % cols) * (cell + 6) + (cell - im.width) // 2, 6 + (i // cols) * (cell + 6) + (cell - im.height) // 2))
        os.makedirs(os.path.dirname(os.path.abspath(sheet)), exist_ok=True); sh.save(sheet); print("sheet", sheet)
    return files


def look_report(files, ref=None, style=None):
    """print the look numbers of each file; with reference files also how far each is from them (in spreads of the reference set; under 1 = inside the set's normal range)"""
    import glob
    import numpy as np
    out = {}; shown = set()
    refs = [f for r in (ref or []) for f in (sorted(glob.glob(os.path.join(r, "*.png"))) if os.path.isdir(r) else sorted(glob.glob(r)) or [r])]
    if style and not refs and not style_profile(style): print(f"pixart look: no profile for style {style!r} (S01..S23)"); return {}
    if refs:
        R = np.array([[look(f)[k] for k in LOOK] for f in refs]); mu, sd = R.mean(0), np.maximum(R.std(0), 1e-6) if len(refs) > 1 else np.maximum(np.abs(R[0]) * 0.15, 1e-6)
        print(f"reference ({len(refs)} images): " + "  ".join(f"{k} {m:.2f}±{s:.2f}" for k, m, s in zip(LOOK, mu, sd)))
    for f in files:
        v = look(f); line = f"{os.path.basename(f)}: " + "  ".join(f"{k} {v[k]:.2f}" for k in LOOK)
        if style and not refs:                                  # the profile of the drawing's own size bucket
            m_, s_, p = style_profile(style, drawn_size(f)); mu, sd = np.array(m_), np.array(s_)
            if p["bucket"] not in shown:
                shown.add(p["bucket"])
                print(f"style {style.upper()} profile, {p['bucket']} ({p['n']} hand-made sprites, {p['packs']} packs{', THIN sample' if p['thin'] else ''}): " + "  ".join(f"{k} {m:.2f}±{s:.2f}" for k, m, s in zip(LOOK, mu, sd)))
        if refs or style:
            z = (np.array([v[k] for k in LOOK]) - mu) / sd; v["distance"] = float(np.abs(z).mean()); v["z"] = [round(float(x), 3) for x in z]; worst = np.argsort(-np.abs(z))[:3]
            line += f"\n    distance {v['distance']:.2f}; furthest: " + ", ".join(f"{LOOK[i]} {z[i]:+.1f}" for i in worst)
        print(line); out[f] = v
    if out and (refs or style): print("  (a guide, not approval: the numbers do not judge shape, readability or appeal; `python -m pixart calibrate` shows how often they agreed with the user)")
    return out


PICKS = os.environ.get("PIXART_PICKS", os.path.join(HERE, "knowledge", "picks.jsonl"))


def cands(files, out, style=None, axis="", scale=4, plain=False):
    """2-3 candidates on one numbered sheet (enlarged on the dark game neutral, 1x on dark and on light, with their look numbers) for the user to pick from.
    Writes OUT/cands.png, OUT/cand1.png.. and OUT/cands.json (then: pixart pick OUT/cands.json N)."""
    import hashlib, json, time, shutil
    from PIL import Image, ImageDraw
    os.makedirs(out, exist_ok=True)
    nums = look_report(files, style=style) if style else {f: look(f) for f in files}
    ims = [Image.open(f).convert("RGBA") for f in files]; W = max(150, max(i.width for i in ims) * scale); H = max(i.height for i in ims) * scale; g = 16
    sh = Image.new("RGBA", (len(ims) * (W + g) + g, H + max(i.height for i in ims) + 76), BG); d = ImageDraw.Draw(sh)
    for k, (f, im) in enumerate(zip(files, ims)):
        x = g + k * (W + g); big = im.resize((im.width * scale, im.height * scale), Image.NEAREST); sh.alpha_composite(big, (x + (W - big.width) // 2, 20))
        y1 = 32 + H; sh.alpha_composite(im, (x, y1))
        light = Image.new("RGBA", (im.width + 8, im.height + 8), (214, 210, 200, 255)); light.alpha_composite(im, (4, 4)); sh.alpha_composite(light, (x + im.width + 8, y1 - 4))
        v = nums[f]; d.text((x, 4), str(k + 1), fill=(255, 230, 90, 255))
        if not plain: d.text((x, y1 + im.height + 10), f"orph {v['orphans']:.2f}  small {v['small']:.2f}\nrun {v['run']:.2f}  col {v['colours']}" + (f"  dist {v['distance']:.2f}" if "distance" in v else ""), fill=(200, 200, 205, 255))
    sh.save(os.path.join(out, "cands.png"))
    for k, f in enumerate(files): shutil.copy(f, os.path.join(out, f"cand{k + 1}.png"))
    rec = {"date": time.strftime("%Y-%m-%d %H:%M"), "style": (style or "").upper(), "axis": axis, "size": drawn_size(files[0]),
           "cands": [{"file": os.path.abspath(f), "sha": hashlib.sha256(open(f, "rb").read()).hexdigest()[:16], "look": {k: nums[f][k] for k in LOOK},
                      "distance": nums[f].get("distance"), "z": nums[f].get("z")} for f in files]}
    json.dump(rec, open(os.path.join(out, "cands.json"), "w", encoding="utf-8"), indent=1)
    print("sheet", os.path.join(out, "cands.png"), "-> show it to the user, then: python -m pixart pick", os.path.join(out, "cands.json"), "N")
    return os.path.join(out, "cands.png")


def pick(cands_json, n, judge="user", note=""):
    """record which candidate (1-based) was picked: appends one line to knowledge/picks.jsonl (the winner, the losers, their numbers, who judged)"""
    import json
    rec = json.load(open(cands_json, encoding="utf-8")); c = rec.pop("cands")
    if not 1 <= n <= len(c): print(f"pixart pick: N must be 1..{len(c)}"); return None
    rec.update(judge=judge, note=note, winner=c[n - 1], losers=[x for i, x in enumerate(c) if i != n - 1])
    os.makedirs(os.path.dirname(os.path.abspath(PICKS)), exist_ok=True)
    with open(PICKS, "a", encoding="utf-8") as fh: fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"picked {n} ({judge}) -> {PICKS}"); return rec


def calibrate(judge="user", path=None):
    """how often the style distance agreed with the picks: for every winner-loser pair, did the winner sit closer to the hand-made profile? Overall, per style and
    size bucket, and per look number. Returns the overall agreement (0..1), or None when there are no pairs."""
    import json, collections
    path = path or PICKS
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()] if os.path.isfile(path) else []
    recs = [r for r in recs if judge == "all" or r.get("judge") == judge]
    pairs = [(r, r["winner"], l) for r in recs for l in r["losers"] if r["winner"].get("distance") is not None and l.get("distance") is not None]
    if not pairs: print(f"pixart calibrate: no {judge} pairs with style distances in {path}"); return None
    hit = lambda w, l: 1.0 if w["distance"] < l["distance"] else 0.5 if w["distance"] == l["distance"] else 0.0
    groups = collections.defaultdict(list)
    for r, w, l in pairs: groups[(r["style"], size_bucket(r["size"]))].append(hit(w, l))
    tot = sum(hit(w, l) for _, w, l in pairs) / len(pairs)
    print(f"{len(pairs)} {judge} pairs from {len(recs)} picks: the picked one was closer to the hand-made profile in {tot:.0%} (50% = no better than a coin)"
          + ("  -- too few pairs to trust (under 10)" if len(pairs) < 10 else ""))
    for (st, b), h in sorted(groups.items()): print(f"  {st or '-':4} {b:6} {sum(h) / len(h):4.0%} of {len(h)}")
    zp = [(w["z"], l["z"]) for _, w, l in pairs if w.get("z") and l.get("z")]
    if zp: print("  per number, picked one closer on it: " + "  ".join(f"{k} {sum(abs(a[i]) < abs(b[i]) for a, b in zp) / len(zp):.0%}" for i, k in enumerate(LOOK)))
    return tot


def compare(paths, out, height=300, gap=8):
    """the images in a row, each enlarged by a whole number to about `height` px, on the dark neutral the game uses"""
    from PIL import Image
    ims = [Image.open(p).convert("RGBA") for p in paths]
    if len(ims) == 2 and ims[0].size == ims[1].size:   # same size: add a difference map (red = brightness off by more than 40, yellow = drawn in only one of the two)
        import numpy as np
        a, b = (np.array(i).astype(int) for i in ims); oa, ob = a[..., 3] > 0, b[..., 3] > 0; La, Lb = (0.299 * v[..., 0] + 0.587 * v[..., 1] + 0.114 * v[..., 2] for v in (a, b))
        d = np.zeros(a.shape, np.uint8); d[oa | ob] = (40, 40, 44, 255); d[oa & ob & (np.abs(La - Lb) > 40)] = (230, 60, 60, 255); d[oa ^ ob] = (240, 210, 60, 255); ims.append(Image.fromarray(d, "RGBA"))
    ims = [i.resize((i.width * s, i.height * s), Image.NEAREST) for i in ims for s in [max(1, round(height / i.height))]]
    h = max(i.height for i in ims); sheet = Image.new("RGBA", (sum(i.width for i in ims) + gap * (len(ims) + 1), h + 2 * gap), BG); x = gap
    for i in ims: sheet.alpha_composite(i, (x, gap + (h - i.height) // 2)); x += i.width + gap
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); sheet.save(out); return out


def main(argv=None):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    ap = argparse.ArgumentParser(prog="pixart", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("new"); p.add_argument("name"); p.add_argument("--size", default="32x32"); p.add_argument("--dir", default=".")
    p = sub.add_parser("examples"); p.add_argument("names", nargs="*"); p.add_argument("--out", default="pixart_examples")
    p = sub.add_parser("lint"); p.add_argument("files", nargs="+")
    p = sub.add_parser("measure"); p.add_argument("file"); p.add_argument("--view"); p.add_argument("--scale", type=int, default=8); p.add_argument("--rows", action="store_true", help="print the drawn x runs of every row")
    p = sub.add_parser("compare"); p.add_argument("files", nargs="+"); p.add_argument("-o", "--out", required=True); p.add_argument("--height", type=int, default=300)
    p = sub.add_parser("look"); p.add_argument("files", nargs="+"); p.add_argument("--ref", action="append", help="folder, glob or file of existing art to measure against (repeatable)"); p.add_argument("--style", help="style code S01..S23: measure against its hand-made profile")
    p = sub.add_parser("refs")
    for k in ("style", "subject", "size", "view", "material", "out", "sheet"): p.add_argument("--" + k)
    p.add_argument("--tier", default="open,copyleft"); p.add_argument("--n", type=int, default=24)
    p = sub.add_parser("cands"); p.add_argument("files", nargs="+"); p.add_argument("-o", "--out", required=True); p.add_argument("--style"); p.add_argument("--axis", default=""); p.add_argument("--plain", action="store_true", help="no numbers on the sheet (blind judging)")
    p = sub.add_parser("pick"); p.add_argument("cands_json"); p.add_argument("n", type=int); p.add_argument("--judge", default="user", choices=("user", "claude", "agent")); p.add_argument("--note", default="")
    p = sub.add_parser("calibrate"); p.add_argument("--judge", default="user", choices=("user", "claude", "agent", "all"))
    sub.add_parser("profiles"); sub.add_parser("guide"); sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "look": look_report(a.files, a.ref, a.style); return 0
    if a.cmd == "refs": return 0 if refs(a.style, a.subject, a.size, a.view, a.material, a.tier, a.n, a.out, a.sheet) else 1
    if a.cmd == "cands":
        if not 2 <= len(a.files) <= 3: print("pixart cands: give 2 or 3 candidates"); return 2
        cands(a.files, a.out, a.style, a.axis, plain=a.plain); return 0
    if a.cmd == "pick": return 0 if pick(a.cands_json, a.n, a.judge, a.note) else 2
    if a.cmd == "calibrate": calibrate(a.judge); return 0
    if a.cmd == "profiles": print(build_profiles()); return 0
    if a.cmd == "measure": measure(a.file, a.view, a.scale, a.rows); return 0
    if a.cmd == "compare": print(compare(a.files, a.out, a.height)); return 0
    if a.cmd == "new":
        try: w, h = (int(v) for v in a.size.lower().split("x"))
        except ValueError: print(f"pixart: --size must look like 32x32, got {a.size!r}"); return 2
        path = os.path.join(a.dir, a.name + ".py")
        if os.path.exists(path): print(f"pixart: {path} already exists; pick another name"); return 2
        os.makedirs(a.dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f: f.write(STARTER.format(name=a.name, root=ROOT, w=w, h=h, bx=w // 4, by=h // 4, bw=w // 2, bh=h // 2, gx=w // 4 + w // 8, gy=h // 4 + h // 8))
        print(path); print(f"next: edit it, then run  python {path}  and look at out/{a.name}_preview.png next to it"); return 0
    if a.cmd == "examples":
        if ROOT not in sys.path: sys.path.insert(0, ROOT)
        from pixart.examples import EXAMPLES
        from pixart import export, strip
        bad = [n for n in a.names if n not in EXAMPLES]
        if bad: print(f"pixart: unknown example {bad[0]!r}; choose from {', '.join(EXAMPLES)}"); return 2
        for name in a.names or EXAMPLES:
            r = EXAMPLES[name](); frames = r if isinstance(r, list) else [r]; print(f"[{name}]"); frames[0].lint()
            frames[0].preview(os.path.join(a.out, name + "_preview.png")); export(frames, a.out, name)
            if len(frames) > 1: export(frames, a.out, name + "_x6", scale=6); strip(frames, os.path.join(a.out, name + "_strip.png"))
        print("written to", os.path.abspath(a.out)); return 0
    if a.cmd == "lint" and any(not f.lower().endswith((".png", ".gif", ".webp")) for f in a.files):
        print("pixart lint reads images (.png). For a drawing script, call c.lint() inside it, or run the script and lint the PNG it saves."); return 2
    if a.cmd == "lint": return subprocess.run([sys.executable, os.path.join(ROOT, "check", "pixel_lint.py"), *a.files]).returncode
    if a.cmd == "guide": print(open(os.path.join(HERE, "KNOWLEDGE.md"), encoding="utf-8").read()); return 0
    if a.cmd == "selftest":
        if ROOT not in sys.path: sys.path.insert(0, ROOT)
        from pixart.selftest import selftest
        return selftest()
    ap.print_help(); return 0
