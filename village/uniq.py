"""landmark and one-off buildings for the village, all from pixdraw specs (+ a few pixels for the cross)"""
import sys
import os
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.path.dirname(os.path.abspath(__file__))]
import numpy as np
from PIL import Image
from pixdraw import render

BASE = {"proj": "side"}
SPECS = {
    "barn": {"type": "house", "wall": "planks", "roof_mat": "thatch", "W": 58, "D": 28, "fh": 24, "floors": 1, "chimney": False, "smoke": False, "door_w": 18, "door_h": 18, "pitch": 0.55},
    "smithy": {"type": "cottage", "wall": "stone", "roof_mat": "shingles", "W": 36, "D": 22, "fh": 17, "chimney": True, "smoke": True, "props": [{"kind": "barrel", "fx": 0.8, "fy": 0.25}, {"kind": "crate", "fx": 0.15, "fy": 0.2, "z": 0, "w": 9}]},
    "bakery": {"type": "house", "wall": "plaster", "roof_mat": "tiles", "W": 40, "D": 22, "fh": 19, "floors": 1, "awning": True, "lantern": True, "chimney": True, "smoke": True},
    "townhall": {"type": "inn", "wall": "brick", "roof_mat": "tiles", "W": 58, "D": 28, "floors": 3, "fh": 15, "flag": True, "smoke": False, "lantern": True},
    "inn_big": {"type": "inn", "wall": "stone", "roof_mat": "shingles", "W": 52, "floors": 2, "lantern": True, "smoke": True},
    "cottage_tall": {"type": "cottage", "floors": 2, "W": 28, "fh": 15, "wall": "planks", "roof_mat": "tiles", "chimney": True, "smoke": True},
}


def special(name, frames):
    if name == "church":
        return church(frames)
    return render({**BASE, **SPECS[name]}, "bright_cartoon", frames=frames)


def church(frames):
    tw = render({**BASE, "type": "tower", "W": 18, "D": 18, "floors": 4, "fh": 15, "roof": "hip", "pitch": 1.4, "wall": "stone", "roof_mat": "tiles", "flag": False}, "bright_cartoon", frames=frames)
    nv = render({**BASE, "type": "house", "W": 58, "D": 24, "floors": 1, "fh": 26, "wall": "plaster", "roof_mat": "tiles", "chimney": False, "smoke": False, "door_w": 12, "door_h": 18, "pitch": 0.8}, "bright_cartoon", frames=frames)
    out = []
    for t, n in zip(tw, nv):
        pad = 7; W = t.width + n.width - 5; H = max(t.height, n.height) + pad
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); c.alpha_composite(n, (t.width - 5, H - n.height)); c.alpha_composite(t, (0, H - t.height))
        a = np.array(t); col = t.width // 2; top = int(np.argmax(a[:, col, 3] > 0)); ty = H - t.height + top
        gold, dk = (240, 200, 70, 255), (150, 110, 40, 255)
        px = c.load()
        for dy in range(6):
            px[col, ty - 1 - dy] = gold if dy else dk
        for dx in (-1, 1):
            px[col + dx, ty - 4] = gold
        out.append(c)
    return out


if __name__ == "__main__":
    names = ["church", "barn", "smithy", "bakery", "townhall", "inn_big", "cottage_tall"]; ims = [special(n, 1)[0] for n in names]
    W = sum(i.width for i in ims) + 10 * len(ims); H = max(i.height for i in ims) + 10
    s = Image.new("RGBA", (W, H), (150, 190, 230, 255)); x = 5
    for i in ims:
        s.alpha_composite(i, (x, H - 5 - i.height)); x += i.width + 10
    s.resize((W * 3, H * 3), Image.NEAREST).save("uniq_sheet.png"); print(W, H)
