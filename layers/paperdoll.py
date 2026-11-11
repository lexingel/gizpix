# SPDX-License-Identifier: AGPL-3.0-or-later
"""Paperdoll layer extractor + checker. Local only, no generator calls.

  extract BASE EDIT --out DIR [--name hat] [--region x0,y0,x1,y1] [--tol 18] [--min-px 2]
  compose BASE LAYER [LAYER...] --out final.png      (layers bottom to top)
  selftest

Layer pixels are copied from the generator's edit, never drawn. Exit 1 when a check fails.
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage

# ponytail: fixed limits, tune per project once real generated edits show their drift
MAX_BODY_LOSS = 0.02   # base-opaque pixels that turn transparent in the edit (body shifted/redrawn)
MIN_KEPT = 0.70        # clean-up may remove at most 30% of the layer
MAX_BODY_CHANGE = 0.40  # base-opaque pixels recoloured/covered (a full-body redraw)


def load(p):
    return np.asarray(Image.open(p).convert("RGBA")).astype(np.int16)


def over(base, layer):
    """Alpha-composite layer over base; both int16 RGBA, layer alpha is 0 or 255."""
    out = base.copy()
    m = layer[..., 3] > 0
    out[m] = layer[m]
    return out


def diff_mask(base, edit, tol):
    # alpha-aware: pixels that are transparent in both are equal whatever their hidden RGB
    ba, ea = base[..., 3], edit[..., 3]
    d_alpha = np.abs(ba - ea) > tol
    both = (ba > 0) & (ea > 0)
    d_rgb = both & (np.abs(base[..., :3] - edit[..., :3]).max(-1) > tol)
    return d_alpha | d_rgb


def extract(base, edit, tol=18, min_px=2, region=None, clip=False, ref=None, drift=0, key=None, key_tol=40, spur=0.0, thin=False, split_y=None, key_tol_low=None, key_max_sum=None):
    rep = {"ok": True, "fails": [], "notes": []}
    if base.shape != edit.shape:
        return None, {"ok": False, "fails": [f"size mismatch {base.shape[1]}x{base.shape[0]} vs {edit.shape[1]}x{edit.shape[0]}"], "notes": []}
    body = base[..., 3] > 0
    mask = diff_mask(base, edit, tol)
    clipped_out = np.zeros_like(mask)
    drift_px = 0
    if drift:
        # local clean-up: on body pixels a small colour change is shading drift from the redraw, not the item
        l1 = np.abs(base[..., :3] - edit[..., :3]).sum(-1)
        dr = mask & body & (edit[..., 3] > 0) & (l1 < drift)
        drift_px = int(dr.sum()); mask &= ~dr; clipped_out |= dr
        if drift_px:
            rep["notes"].append(f"{drift_px} body-shading drift px dropped (colour change < {drift})")
    # drop specks
    lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
    sizes = ndimage.sum(mask, lab, range(1, n + 1)) if n else []
    # specks: tiny components, and anything under 2% of the changed area (recolour drift on the body)
    floor = max(min_px, 0.02 * mask.sum())
    dropped = 0
    speck = np.zeros_like(mask)
    for i, s in enumerate(sizes, 1):
        if s < floor:
            mask[lab == i] = False
            speck |= lab == i
            dropped += 1
    if dropped:
        rep["notes"].append(f"{dropped} speck components dropped (< {floor:.0f}px)")
    if not mask.any():
        rep["ok"] = False
        rep["fails"].append("no addition detected")
        return None, rep
    lost = (body & (edit[..., 3] == 0)).sum() / max(body.sum(), 1)
    changed = (body & mask).sum() / max(body.sum(), 1)
    rep.update(layer_px=int(mask.sum()), over_empty_px=int((mask & ~body).sum()),
               over_body_px=int((mask & body).sum()), body_loss=round(float(lost), 4),
               body_change=round(float(changed), 4))
    if lost > MAX_BODY_LOSS:
        rep["fails"].append(f"body lost {lost:.1%} of its pixels (shifted or redrawn)")
    if changed > MAX_BODY_CHANGE and not region:
        rep["fails"].append(f"{changed:.1%} of the body changed (full redraw, not one addition)")
    if region:
        # with a region, redraw = changes outside it (a head item legitimately covers much of a small body)
        x0, y0, x1, y1 = region
        xs_ = np.arange(mask.shape[1])[None, :]; ys_ = np.arange(mask.shape[0])[:, None]
        outside = ~((xs_ >= x0) & (xs_ <= x1) & (ys_ >= y0) & (ys_ <= y1))
        out_px = int((mask & outside).sum())
        rep["outside_region_px"] = out_px
        judged, total = out_px, int(mask.sum())
        if key is not None:
            # with the item's palette known, only item-coloured pixels outside the region count as overflow;
            # the rest is body shading from the redraw and is clipped (the palette key would drop it anyway)
            kp = np.unique(key[key[..., 3] > 0][:, :3], axis=0)
            inpal = np.abs(edit[..., None, :3] - kp[None, None, :, :]).sum(-1).min(-1) < key_tol
            inpal &= edit[..., :3].sum(-1) > 180   # the dark outline is shared with the body: not evidence either way
            cand = mask & inpal
            lab3, _ = ndimage.label(cand, structure=np.ones((3, 3)))
            touch = np.unique(lab3[cand & ~outside]); touch = touch[touch > 0]
            joined = np.isin(lab3, touch)
            # real overflow = item-coloured pixels outside the box that are joined to the piece inside it;
            # detached item-coloured bits outside (leg and head shading in leather-like browns) are body noise
            judged = int((cand & outside & joined).sum()); total = int(cand.sum())
            rep["outside_item_coloured_px"] = judged
            rep["outside_detached_px"] = int((cand & outside & ~joined).sum())
        if clip:
            # local clean-up (approved): strays outside the item's region are dropped; too many = a redraw, fail
            if judged > 0.15 * total:
                rep["fails"].append(f"{judged} of {total} changed pixels outside the region (body redrawn)")
            clipped_out |= mask & outside
            mask &= ~outside
            if out_px:
                rep["notes"].append(f"{out_px} px outside the region clipped (local clean-up)")
        elif out_px:
            rep["fails"].append(f"{out_px} changed pixels outside the expected region")
        rep["layer_px"] = int(mask.sum())
        if not mask.any():
            rep["ok"] = False
            rep["fails"].append("nothing left inside the region")
            return None, rep
    ys, xs = np.nonzero(mask)
    rep["bbox"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    # copy the generator's pixels, binary alpha (reported)
    layer = np.zeros_like(edit)
    layer[mask] = edit[mask]
    soft = int(((layer[..., 3] > 0) & (layer[..., 3] < 255)).sum())
    layer[..., 3] = np.where(layer[..., 3] >= 128, 255, 0)
    layer[layer[..., 3] == 0] = 0
    if soft:
        rep["notes"].append(f"{soft} soft-alpha pixels snapped to 0/255")
    if key is not None or spur or thin:
        removed = np.zeros_like(mask)
        before = int((layer[..., 3] > 0).sum())
        if key is not None:
            # local clean-up: keep only pixels in the item's own colours (a still layer of the same item);
            # skin/shading changes from a redrawn body are not in that palette
            pal = np.unique(key[key[..., 3] > 0][:, :3], axis=0)
            if key_max_sum is not None:
                pal = pal[pal.sum(-1) <= key_max_sum]    # the still layer can carry skin-toned pixels: leave them out of the key
            m = layer[..., 3] > 0
            d = np.abs(layer[..., None, :3] - pal[None, None, :, :]).sum(-1).min(-1)
            tol = np.full(d.shape, key_tol)
            if split_y is not None and key_tol_low is not None:
                tol[split_y:] = key_tol_low          # below the split (tassets, hems) use their own tolerance
            off = m & (d >= tol)
            removed |= off
            layer[off] = 0
            rep["notes"].append(f"palette key: {int(off.sum())} px outside the item's {len(pal)} colours dropped")
        if spur:
            # detached slivers (arm outlines of a redrawn body): drop components under spur x the largest
            m = layer[..., 3] > 0
            lab2, n2 = ndimage.label(m, structure=np.ones((3, 3)))
            if n2 > 1:
                sz = np.asarray(ndimage.sum(m, lab2, range(1, n2 + 1)))
                for i, z in enumerate(sz, 1):
                    if z < spur * sz.max():
                        removed |= lab2 == i
                        layer[lab2 == i] = 0
                rep["notes"].append(f"{int((sz < spur * sz.max()).sum())} detached slivers dropped (< {spur:.0%} of the largest piece)")
        if thin:
            # one-pixel lines sticking out of the piece (outline slivers, antennas): keep only pixels that sit in a
            # fully opaque 2x2 block; an outline next to fill survives, a lone line does not
            m = layer[..., 3] > 0
            q = m[:-1, :-1] & m[1:, :-1] & m[:-1, 1:] & m[1:, 1:]
            k2 = np.zeros_like(m)
            k2[:-1, :-1] |= q; k2[1:, :-1] |= q; k2[:-1, 1:] |= q; k2[1:, 1:] |= q
            cut = m & ~k2
            if split_y is not None:
                cut[split_y:] = False                 # no thin filter below the split: narrow tassets are real
            removed |= cut
            layer[cut] = 0
            rep["notes"].append(f"thin lines: {int(cut.sum())} px dropped (not in a 2x2 block)")
        clipped_out |= removed
        if not (layer[..., 3] > 0).any():
            rep["ok"] = False
            rep["fails"].append("nothing left after clean-up")
            return None, rep
        rep["layer_px"] = int((layer[..., 3] > 0).sum())
        rep["kept_after_cleanup"] = round(rep["layer_px"] / max(before, 1), 2)
        if rep["kept_after_cleanup"] < MIN_KEPT:
            rep["fails"].append(f"clean-up removed {1 - rep['kept_after_cleanup']:.0%} of the layer (palette key or thin filter too strict for this view)")
    if ref is not None:
        # local clean-up (approved): snap to the colours of the same item's south layer
        pal = np.unique(ref[ref[..., 3] > 0][:, :3], axis=0)
        if len(pal):
            m = layer[..., 3] > 0
            px = layer[m][:, :3]
            nearest = pal[np.abs(px[:, None, :] - pal[None, :, :]).sum(-1).argmin(1)]
            rep["notes"].append(f"palette matched to reference layer ({len(pal)} colours, {int((nearest != px).any(1).sum())} px recoloured)")
            layer[m, :3] = nearest
    # round trip: base + layer vs edit, everywhere
    rt = over(base, layer)
    bad = int((diff_mask(rt, edit, tol) & ~speck & ~clipped_out).sum())  # dropped specks / clipped strays differ on purpose
    rep["roundtrip_bad_px"] = bad
    if ref is None and bad > max(2, mask.sum() * 0.02):
        rep["fails"].append(f"round trip differs from the edit in {bad} pixels")
    rep["ok"] = not rep["fails"]
    return layer, rep


def align(base, edit):
    """Pad a smaller base into the edit's canvas at the offset where the silhouettes overlap best.
    skeleton-v3 grows a 64px walk to 96px; the base sits inside it at a fixed offset."""
    h, w = base.shape[:2]; H, W = edit.shape[:2]
    if (h, w) == (H, W) or h > H or w > W:
        return base, (0, 0)
    e = edit[..., 3] > 0; b = base[..., 3] > 0; best = None
    for dy in range(H - h + 1):
        for dx in range(W - w + 1):
            q = np.zeros((H, W), bool); q[dy:dy + h, dx:dx + w] = b
            sc = (q & e).sum() - 0.5 * (q ^ e).sum()
            if best is None or sc > best[0]:
                best = (sc, dx, dy)
    out = np.zeros_like(edit); out[best[2]:best[2] + h, best[1]:best[1] + w] = base
    return out, (best[1], best[2])


def save(a, p):
    Image.fromarray(a.astype(np.uint8), "RGBA").save(p)


def preview(base, edit, layer, scale=3):
    """base | edit | layer | base+layer on a checkerboard. Inspection aid only, never a deliverable."""
    h, w = base.shape[:2]
    cb = np.zeros((h, w, 4), np.int16)
    yy, xx = np.mgrid[:h, :w]
    cb[...] = np.where(((yy // 4 + xx // 4) % 2)[..., None] == 0, [200, 200, 200, 255], [150, 150, 150, 255])
    tiles = [over(cb, t) for t in (base, edit, layer, over(base, layer))]
    row = np.concatenate([np.pad(t, ((0, 0), (0, 2), (0, 0)), constant_values=255) for t in tiles], 1)
    return np.kron(row, np.ones((scale, scale, 1), np.int16))


def cmd_extract(a):
    base, edit = load(a.base), load(a.edit)
    region = [int(v) for v in a.region.split(",")] if a.region else None
    ref = load(a.match) if a.match else None
    key = load(a.keep_palette) if a.keep_palette else None
    if a.align:
        base, off = align(base, edit)
        print(f"aligned base into {edit.shape[1]}x{edit.shape[0]} at offset {off}", file=sys.stderr)
        save(base, os.path.join(a.out, f"{a.name}.base.png")) if os.makedirs(a.out, exist_ok=True) is None else None
    layer, rep = extract(base, edit, a.tol, a.min_px, region, a.clip, ref, a.drift, key, a.key_tol, a.spur, a.thin, a.split_y, a.key_tol_low, a.key_max_sum)
    os.makedirs(a.out, exist_ok=True)
    if layer is not None:
        save(layer, os.path.join(a.out, f"{a.name}.layer.png"))
        save(preview(base, edit, layer), os.path.join(a.out, f"{a.name}.check.png"))
    json.dump(rep, open(os.path.join(a.out, f"{a.name}.report.json"), "w"), indent=1)
    print(json.dumps(rep))
    return 0 if rep["ok"] else 1


def cmd_compose(a):
    img = load(a.base)
    for p in a.layers:
        l = load(p)
        if l.shape != img.shape:
            sys.exit(f"{p}: size differs from base")
        img = over(img, l)
    save(img, a.out)
    return 0


def selftest():
    B = np.zeros((32, 32, 4), np.int16)
    B[8:28, 10:22] = [230, 180, 140, 255]            # body
    B[2:8, 12:20] = [230, 180, 140, 255]             # head
    E = B.copy()
    E[0:4, 11:21] = [90, 90, 100, 255]               # helmet over the top of the head
    layer, rep = extract(B, E)
    assert rep["ok"], rep
    assert (layer[0:4, 11:21, 3] == 255).all() and layer[8:, :, 3].sum() == 0
    assert (over(B, layer) == E).all()
    # region check
    _, rep = extract(B, E, region=(0, 20, 31, 31))
    assert not rep["ok"] and "outside" in rep["fails"][0]
    # body shifted by 1px -> rejected
    S = np.roll(B, 1, axis=1)
    S[0:4, 11:21] = [90, 90, 100, 255]
    _, rep = extract(B, S)
    assert not rep["ok"], rep
    # nothing changed
    _, rep = extract(B, B.copy())
    assert not rep["ok"] and "no addition" in rep["fails"][0]
    # size mismatch
    _, rep = extract(B, np.zeros((16, 16, 4), np.int16))
    assert not rep["ok"]
    # specks under min_px are dropped
    N = B.copy(); N[30, 30] = [255, 0, 0, 255]; N[0:4, 11:21] = E[0:4, 11:21]
    layer, rep = extract(B, N)
    assert rep["ok"] and layer[30, 30, 3] == 0
    # palette key: a skin-toned pixel inside the layer is dropped, helmet colours stay
    P = E.copy(); P[0:4, 11:21] = [90, 90, 100, 255]
    P[8, 14] = [236, 186, 146, 255]                   # shading drift inside the body, same hue as skin
    ref = np.zeros_like(P); ref[0:4, 11:21] = [90, 90, 100, 255]
    layer, rep = extract(B, P, key=ref)
    assert rep["ok"] and layer[8, 14, 3] == 0 and (layer[0:4, 11:21, 3] == 255).all(), rep
    # detached sliver: a 1x8 dark line away from the helmet is dropped with spur, the helmet stays
    S2 = E.copy(); S2[10:18, 4] = [20, 20, 20, 255]
    layer, rep = extract(B, S2, min_px=2, spur=0.25)
    assert rep["ok"] and layer[10:18, 4, 3].sum() == 0 and (layer[0:4, 11:21, 3] == 255).all(), rep
    # overflow gate: item-coloured bits detached outside the region are noise, a joined extension is overflow
    ref2 = np.zeros_like(E); ref2[0:4, 11:21] = [90, 90, 100, 255]
    D1 = E.copy(); D1[0:4, 11:21] = [90, 90, 100, 255]; D1[28:31, 11:14] = [90, 90, 100, 255]   # detached, below the region
    layer, rep = extract(B, D1, region=(0, 0, 31, 20), clip=True, key=ref2)
    assert rep["ok"] and rep["outside_detached_px"] > 0 and rep["outside_item_coloured_px"] == 0, rep
    J1 = E.copy(); J1[0:24, 11:21] = [90, 90, 100, 255]                                      # helmet runs on down the body
    _, rep = extract(B, J1, region=(0, 0, 31, 8), clip=True, key=ref2)
    assert not rep["ok"] and rep["outside_item_coloured_px"] > 0, rep
    # thin lines: a 1px antenna above the helmet is dropped, the helmet and its outline stay
    T = E.copy(); T[0:4, 11:21] = [90, 90, 100, 255]; T[0:3, 5] = [20, 20, 20, 255]
    layer, rep = extract(B, T, thin=True)
    assert rep["ok"] and layer[0:3, 5, 3].sum() == 0 and (layer[0:4, 11:21, 3] == 255).all(), rep
    # key-max-sum: a light skin-toned colour in the reference is not part of the key
    refL = np.zeros_like(E); refL[0:4, 11:21] = [90, 90, 100, 255]; refL[5, 11] = [236, 186, 146, 255]
    PL = E.copy(); PL[0:4, 11:21] = [90, 90, 100, 255]; PL[8:10, 14:16] = [236, 186, 146, 255]
    layer, rep = extract(B, PL, key=refL, key_max_sum=400, key_tol=20)
    assert rep["ok"] and layer[8:10, 14:16, 3].sum() == 0, rep
    # split: a 1px line above the split row is thinned away, the same line below it stays
    T2 = E.copy(); T2[0:4, 11:21] = [90, 90, 100, 255]; T2[0:3, 5] = [20, 20, 20, 255]; T2[20:23, 5] = [20, 20, 20, 255]
    layer, rep = extract(B, T2, thin=True, split_y=15)
    assert layer[0:3, 5, 3].sum() == 0 and layer[20:23, 5, 3].sum() == 255 * 3, rep
    # align: a 32px base inside a 48px edit at offset (6, 9) is found
    big = np.zeros((48, 48, 4), np.int16); big[9:41, 6:38] = E
    ab, off = align(B, big)
    assert off == (6, 9), off
    layer, rep = extract(ab, big)
    assert rep["ok"] and layer[9:13, 17:27, 3].sum() == 255 * 40 and rep["layer_px"] == 40, rep
    print("selftest ok")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest="cmd", required=True)
    e = s.add_parser("extract"); e.add_argument("base"); e.add_argument("edit")
    e.add_argument("--out", required=True); e.add_argument("--name", default="layer")
    e.add_argument("--region"); e.add_argument("--clip", action="store_true"); e.add_argument("--align", action="store_true", help="pad a smaller base into the edit canvas at the best-overlap offset"); e.add_argument("--keep-palette", help="same item's still layer PNG: keep only pixels in its colours"); e.add_argument("--key-tol", type=int, default=40); e.add_argument("--key-max-sum", type=int, help="ignore key colours brighter than this RGB sum (skin tones leaked into the still layer)"); e.add_argument("--split-y", type=int, help="row where the lower part starts (no thin filter, own key tolerance)"); e.add_argument("--key-tol-low", type=int, help="key tolerance below --split-y"); e.add_argument("--thin", action="store_true", help="drop one-pixel lines sticking out of the layer"); e.add_argument("--spur", type=float, default=0.0, help="drop detached pieces smaller than this fraction of the largest (0 = off)"); e.add_argument("--drift", type=int, default=0, help="drop body pixels whose colour changed by less than this (sum of RGB)"); e.add_argument("--match", help="reference layer PNG (same item, other direction) to snap colours to"); e.add_argument("--tol", type=int, default=18); e.add_argument("--min-px", type=int, default=2)
    c = s.add_parser("compose"); c.add_argument("base"); c.add_argument("layers", nargs="+"); c.add_argument("--out", required=True)
    s.add_parser("selftest")
    a = p.parse_args()
    if a.cmd == "selftest":
        selftest()
    else:
        sys.exit(cmd_extract(a) if a.cmd == "extract" else cmd_compose(a))
