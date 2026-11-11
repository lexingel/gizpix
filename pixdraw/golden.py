# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixdraw.golden - SHA-256 of a fixed set of renders, so an unintended change in the drawing is caught. python -m pixdraw golden [--update]
The hashes depend on the Pillow version (polygon rasterising); if the stored version differs the check is skipped with a note instead of failing."""
import hashlib, json, os
import numpy as np
import PIL
from . import render, PRESETS

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden.json")
STYLES = ("dark_fantasy", "retro16")
EXTRA = ({"type": "inn", "dormers": 2}, {"type": "inn", "wing": True}, {"type": "cottage", "wing": {"w": 14, "l": 10}, "dormers": 1})


def cases():
    for st in STYLES:
        for proj in ("iso", "top", "side"):
            for t in PRESETS: yield f"{st}/{proj}/{t}", {"type": t, "proj": proj}, st
        for i, sp in enumerate(EXTRA): yield f"{st}/iso/extra{i}", {**sp, "proj": "iso"}, st
        yield f"{st}/top/wing", {"type": "inn", "wing": True, "proj": "top"}, st


def compute():
    return {k: hashlib.sha256(np.array(render(sp, st)[0]).tobytes()).hexdigest()[:16] for k, sp, st in cases()}


def check():
    """(ok, message)"""
    if not os.path.exists(PATH): return True, "no golden.json (run python -m pixdraw golden --update)"
    g = json.load(open(PATH)); 
    if g["pillow"] != PIL.__version__: return True, f"SKIPPED: golden hashes were made with Pillow {g['pillow']}, this is {PIL.__version__}; run python -m pixdraw golden --update here to make local ones"
    now = compute(); bad = [k for k in g["hashes"] if now.get(k) != g["hashes"][k]]; new = [k for k in now if k not in g["hashes"]]
    return (not bad and not new), (f"{len(now)} renders match" if not bad and not new else f"changed: {bad[:6]}{'...' if len(bad) > 6 else ''}; new: {new[:3]}. If intended: python -m pixdraw golden --update")


def update():
    json.dump({"pillow": PIL.__version__, "hashes": compute()}, open(PATH, "w"), indent=1); return PATH
