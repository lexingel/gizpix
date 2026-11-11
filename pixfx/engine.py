# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixfx.engine - effect registry, rendering of frames, checks and export.

An effect module defines META (a dict) and draw(f, t, o): f is a core.Frame, t in [0, 1], o the merged options (dict-like with attribute access).
META keys: id 'category/name', name, loop (True = t runs 0..1 and wraps; False = a one-shot, t = 0..1 inclusive and it must end empty), duration (s),
size (w, h), pivot (x, y) = where the effect's origin is, options = {name: default}, about (one line), tags."""
import glob, importlib, json, os, pkgutil
import numpy as np
from PIL import Image
from .core import Frame
from .ramps import resolve


class Opts(dict):
    __getattr__ = dict.get


COMMON = {"palette": None, "seed": 1, "light": 1.0, "flip": False}


def _modules():
    from . import effects
    return [importlib.import_module(f"{effects.__name__}.{m.name}") for m in pkgutil.iter_modules(effects.__path__)]


def registry():
    reg = {}
    for m in _modules():
        for meta in getattr(m, "EFFECTS", [getattr(m, "META", None)]):
            if meta: reg[meta["id"]] = (m, meta)
    from . import spec
    for p in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "recipes", "*.json"))):    # recipes shipped with Gizpix
        m, meta = spec.load(p); reg[meta["id"]] = (m, meta)
    return reg


def get(eid):
    if eid.lower().endswith(".json"):                                                            # a recipe file of your own
        if not os.path.exists(eid): raise KeyError(f"recipe file '{eid}' not found")
        from . import spec
        try: return spec.load(eid)
        except ValueError as e: raise KeyError(str(e)) from None
    reg = registry()
    if eid in reg: return reg[eid]
    near = [k for k in reg if eid in k or k.split("/")[-1] == eid]
    if len(near) == 1: return reg[near[0]]
    raise KeyError(f"unknown effect '{eid}'" + (f"; did you mean {', '.join(near)}?" if near else "; see `pixfx list`"))


def options(meta, given=None):
    o = Opts({**COMMON, **meta.get("options", {})})
    for k, v in (given or {}).items():
        if k not in o: raise KeyError(f"'{meta['id']}' has no option '{k}'. Options: {', '.join(sorted(o))}")
        o[k] = v
    return o


def n_frames(meta, frames=None, fps=None):
    return int(frames) if frames else max(2, round(meta["duration"] * (fps or meta.get("fps", 12))))


def render_frame(mod, meta, o, t):
    w, h = meta["size"]; f = Frame(w, h); (meta.get("draw") or mod.draw)(f, t, o); return f


def render(eid, given=None, frames=None, fps=None, bg=None):
    """list of RGBA PIL images, one per frame. Loops sample t = i/n (so frame n would equal frame 0); one-shots sample t = i/(n-1)."""
    mod, meta = get(eid); o = options(meta, given); o.palette = o.palette; n = n_frames(meta, frames, fps); out = []
    for i in range(n):
        t = i / n if meta["loop"] else i / (n - 1)
        im = render_frame(mod, meta, o, t).image(bg=bg, light=float(o.light))
        out.append(im.transpose(Image.FLIP_LEFT_RIGHT) if o.flip else im)
    return out


def check(eid, given=None):
    """quality checks; returns a list of problems (empty = clean)"""
    mod, meta = get(eid); o = options(meta, given); n = n_frames(meta); bad = []; w, h = meta["size"]
    a = render_frame(mod, meta, o, 0.0); b = render_frame(mod, meta, o, 0.0)
    if not (np.array_equal(a.rgb, b.rgb) and np.array_equal(a.a, b.a)): bad.append("not deterministic: two renders of the same frame differ")
    if meta["loop"]:
        s = render_frame(mod, meta, o, 1.0)
        if not (np.array_equal(a.a, s.a) and np.array_equal(a.rgb[a.a > 0], s.rgb[s.a > 0])): bad.append("loop does not close: t=1 differs from t=0")
    else:
        e = render_frame(mod, meta, o, 1.0)
        if (e.a > 0).sum() > 0 or (e.light.max() > 0.05): bad.append(f"one-shot does not end empty: {(e.a > 0).sum()} pixels left at t=1")
    edge = 0
    for i in range(n):
        t = i / n if meta["loop"] else i / (n - 1); f = render_frame(mod, meta, o, t)
        edge += int((f.a[0] > 0).sum() + (f.a[-1] > 0).sum() + (f.a[:, 0] > 0).sum() + (f.a[:, -1] > 0).sum())
    if edge and not meta.get("tile"): bad.append(f"{edge} pixels touch the canvas edge over the animation (cropped? make the canvas bigger)")
    return bad
