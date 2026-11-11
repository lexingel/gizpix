# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixdraw.export - PNG, GIF, sprite sheet + JSON (TexturePacker "hash" frames + Aseprite-style frameTags, so Godot/Phaser/Unity importers read it)."""
import json, os
from PIL import Image


def save_gif(frames, path, ms=120):
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=ms, loop=0, disposal=2, transparency=0)


def sheet(frames, name, cols=None, pad=1, ms=120, scale=1):
    """(image, json dict): frames laid out in a grid, all cells the size of the biggest frame, with one animation tag 'idle'"""
    cols = cols or len(frames); rows = -(-len(frames) // cols); w = max(f.width for f in frames); h = max(f.height for f in frames)
    im = Image.new("RGBA", (cols * (w + pad) + pad, rows * (h + pad) + pad), (0, 0, 0, 0)); fr = {}
    for i, f in enumerate(frames):
        x, y = pad + (i % cols) * (w + pad), pad + (i // cols) * (h + pad); im.paste(f, (x + (w - f.width) // 2, y + (h - f.height)));
        fr[f"{name}_{i}"] = {"frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False, "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h}, "sourceSize": {"w": w, "h": h}, "duration": ms}
    meta = {"app": "pixdraw", "image": f"{name}_sheet.png", "format": "RGBA8888", "size": {"w": im.width, "h": im.height}, "scale": "1",
            "frameTags": [{"name": "idle", "from": 0, "to": len(frames) - 1, "direction": "forward"}] if len(frames) > 1 else []}
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        for f in fr.values():
            for k in ("frame", "spriteSourceSize"): f[k] = {q: val * scale for q, val in f[k].items()}
            f["sourceSize"] = {q: val * scale for q, val in f["sourceSize"].items()}
        meta["size"] = {"w": im.width, "h": im.height}
    return im, {"frames": fr, "meta": meta}


def export(frames, out_dir, name, ms=120, scale=1):
    """writes NAME.png (frame 0), and for animations NAME.gif, NAME_sheet.png, NAME_sheet.json; scale = nearest-neighbour enlargement of the files"""
    os.makedirs(out_dir, exist_ok=True); up = (lambda im: im.resize((im.width * scale, im.height * scale), Image.NEAREST)) if scale != 1 else (lambda im: im)
    paths = [os.path.join(out_dir, name + ".png")]; up(frames[0]).save(paths[0])
    if len(frames) > 1:
        save_gif([up(f) for f in frames], os.path.join(out_dir, name + ".gif"), ms); paths.append(os.path.join(out_dir, name + ".gif"))
        im, js = sheet(frames, name, ms=ms, scale=scale); im.save(os.path.join(out_dir, name + "_sheet.png"))
        with open(os.path.join(out_dir, name + "_sheet.json"), "w") as f: json.dump(js, f, indent=1)
        paths += [os.path.join(out_dir, name + "_sheet.png"), os.path.join(out_dir, name + "_sheet.json")]
    return paths
