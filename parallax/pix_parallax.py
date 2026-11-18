# SPDX-License-Identifier: AGPL-3.0-or-later
"""pix_parallax.py - parallax layer stacks: check, preview, export to Godot 4, offset view, draw layers from code. Measures and writes new files; never edits a layer in place.
  python pix_parallax.py check   stack.json [--json] [--strict]
  python pix_parallax.py preview stack.json OUT.gif|OUT.html [--frames N] [--scale N] [--subpixel] [--bob PX] [--camera PX_PER_S] [--no-pingpong]    (.html = real-time canvas at the real fps, with a snapping switch)
  python pix_parallax.py export  stack.json --godot DIR [--res-dir res://bg/NAME] [--mode loop|camera] [--min-zoom Z]
  python pix_parallax.py seam    layer.png --view OUT.png [--y]      |      seam layer.png --heal mincut|profile --out NEW.png [--band N]
  python pix_parallax.py export  stack.json --format json|tiled|ldtk|phaser|css [--out FILE]
  python pix_parallax.py review  stack.json OUT.png [--ref IMAGE]      (colours, dither share, run length per layer + a contact sheet)
  python pix_parallax.py draw    --preset NAME --out DIR [--seed N] [--size 320x180] [--hour dawn|noon|dusk|night] [--pace walk|run] [--static] [--force]      (NAME: dusk_hills night_city forest desert snow ocean cave space ruins)
  python pix_parallax.py selftest
Spec (stack.json), layers listed BACK to FRONT:
  {"name": "dusk", "viewport": [320, 180], "fps": 60, "camera_px_per_s": 480, "background": "#000000",
   "layers": [{"file": "hills.png", "scroll": [0.5, 0.3], "px_per_frame": 4, "depth": 30, "repeat": "x"}]}
  scroll        camera multiplier [x, y] (Godot/Tiled convention): 1 = moves with the camera, 0 = fixed, below 1 = farther, above 1 = foreground. One number = both axes.
  px_per_frame  loop speed for `preview` and the divisibility check (a value under 1 means "1 px every 1/v frames"). 0 = does not move.
  depth         bigger = farther (only for the depth-palette check). depth_check: false leaves a layer out of it (sky, stars, clouds). repeat: "x", "xy" or "none".
  frames        an animated layer: `file` is frame 1, `frames` lists the files of the frames after it, `frame_every` = preview frames per animation frame (default 12). The whole cycle must divide the
                loop length (check says so). Godot gets an AnimatedSprite2D; the GIF and HTML previews play it; the other exports use frame 1.
  A layer may be taller than the viewport: the bottom rows show at rest, the extra rows above are headroom for y parallax (see --bob).
What check measures (advisory; flags never edit anything):
  seam         per axis the colour step across the wrap join against the steps inside the layer: seam_rank = share of inner steps (columns holding an edge) at least as big (a join that wraps is 0.05 or more, a cut is about 0),
               seam_excess = join step / the largest inner step. Flag "visible seam" when the join step is at least 4 and more than 1.25 x the largest inner step (a join that is just one more building edge is not flagged: art edges and cuts look alike to a step measure).
               A second look uses the mean of 4 columns on each side (noise a few pixels wide does not hide a cut), and a layer with transparent sky also gets a contour test (the top silhouette must not jump 3 px or more, and more than 1.2 x its largest inner jump, at the join). A join that is among the top 1% of steps but not flagged only gets a note ("possible seam").
               Measured on drawn layers: 0 false alarms on 420 intact layers; a layer cut to a wrong width is caught about 85% for hills and mountains, 72% for clouds, 60% for pines, almost never for grass, streets and skylines (their misses look like one more edge). On 17 real, unwrapped Guildhold paintings 4 are flagged and 9 more get the "possible" note; mirror-extended copies of them are never flagged. Flat layers and transparent layers work.
  loop speed   px_per_frame must divide the layer width (Pixelblog 23 rule) so the loop closes; the frame count of the whole stack is the least common multiple. Under 1 px/frame: "1 px every k frames".
  camera       with camera_px_per_s: scroll x camera px per frame should be a whole number (live camera, whole-pixel heuristic; not verified in an engine).
  size         all layers one height; a repeating layer may be narrower than the viewport (export writes repeat_times); y parallax needs layers taller than the viewport.
  depth        landscape planes (25% of the picture or more): a farther plane should be lighter, or less saturated and lower in contrast, than a nearer one (atmospheric perspective). Advisory; checked on one real CC0 pack, where depth is carried by lightness.
GIF loops: a walking stack closes its loop only after thousands of frames, so a short GIF jumped back to the start. `preview` now ping-pongs by default when the true loop does not fit: the camera goes right for half the frames and back for the other half, every layer ends exactly where it started and the GIF repeats without a jump (--no-pingpong gives a plain excerpt). The HTML preview has no end at all.
Pace: `draw --pace walk` (default) makes a stack for a camera at 120 px/s: the ground moves 2 px per frame and the far layers 1 px every 2, 4 or 8 frames (steady, whole pixels, loop lengths up to 5120 frames). `--pace run` is the old 480 px/s (8 px per frame, a fast runner). `preview --camera PX_S` shows any stack as a live camera at that speed.
Drawn layers (`draw`): one palette per time of day (--hour) and a 5-tone ramp per depth (far = pulled toward the haze), flat colour planes with dither only as one checker row at a tone border, faceted mountains,
clustered trees, lumpy clouds, window clusters, tufts; 9 presets; twinkling stars and moving waves as loop-safe frames. They are clean starting layers and placeholders, not hand-made art. `review` prints colours, dither share and
run length per layer and writes a contact sheet; on the CC0 forest pack the dither share reaches 8% and far runs are 11 to 55 px, which is where the review limits come from.
Limits: the thresholds come from synthetic layers and the code-drawn presets, not from real game art, so tune them on yours. A GIF cannot show 60 fps (20 ms minimum): use `preview OUT.html` for a real-time canvas (snapping switch, camera bob) and judge the feel in the engine.
Tested in Godot 4.7.2 (2026-11-18, parallax/godot_test): the .tscn loads, Parallax2D scroll_scale moves layers at scroll x camera, whole-pixel steps stay smooth with 2D snapping on, a 0.25 px/frame layer steps 1,0,0,0 (stutter), loop mode with a negative autoscroll moves content left, repeat_times 3 covers x when the camera zooms out to 0.5 (y does not: no repeat in y; set min_zoom in the spec and check flags it).
Also measured: loop mode moves a layer at px_per_frame x fps pixels per second (hills: 237 px/s measured for 240; it is time based, so at a refresh rate other than the spec's fps the per-frame step is not whole: 4 px/frame at 144 Hz is 1.67 px per frame); y scroll_scale works the same way (camera up, layers shift down by scroll y x distance); with 2D snapping OFF a layer still steps 0/1 px but about 2.5% of its pixels (fine detail) flicker, so keep snapping on; Camera2D position smoothing turns even whole-pixel speeds into uneven steps at a steady 8 px/frame (clouds 1,0,1; hills 3/4; pines 3/4/5): do not use it. A camera smoothed in your own script (lerp) gives clean steps at a steady speed, and rounding that camera to whole pixels made no measurable difference (Godot's pixel snapping already rounds each layer): the stutter that is left comes only from fractional layer speeds. All 69 layers of the nine drawn presets were run in Godot 4.7.2 with a camera at 8 px/frame: every moving layer stepped by exactly its px/frame (1, 2, 4, 5, 8, 10); the static sky layers cannot be measured that way.
Heal (`seam --heal`, writes a new file, copies pixels only, never new colours): `profile` shifts the last band of columns so the top contour joins; it fixed 4 of 4 cut hills/mountains/pines layers in the drawn presets and 3 of 3 cut silhouette layers of a real CC0 pack, but it can leave a small artifact at the join (a squashed tree, stray dither). `mincut` overlaps the ends and cuts along the cheapest path and makes the layer `band` columns narrower; it looks cleaner on texture and busy shapes but band 16 failed on broad real mountains (band 64 on a 1180 px layer worked): use a band of about 1/20 of the width for big shapes. Look at the result with `seam --view`; the narrower width must still divide px_per_frame.
Real art: the CC0 'Parallax background forest' pack by MatiasVME (OpenGameArt, 1280x360 layers, 8 layers) passes `check` with no seam flags, runs in Godot 4.7.2 with whole-pixel steps (2, 5, 8 and 1 px/frame at 10 px/frame camera) and stays continuous across the 1280 px wrap. Its depth is carried by lightness, which is why the depth check accepts a lighter far plane.
Seam thresholds: checked on 32 layers of 5 CC0 packs (OpenGameArt: MatiasVME forest, ansimuz forest and industrial, mountains-and-clouds, pixel-mountains) plus 15 seeds of the 3 drawn presets. A sweep of 108 threshold combinations (join step 3/4/6, excess 0.8/1/1.25 for both looks, contour jump 2/3 at 1.0/1.2 x) found the current values among the best: 0 false alarms on the 31 real intact layers, 1 on 210 drawn ones; catching cuts is limited by layers where a cut is not visible anyway (36 of 75 cuts of real silhouette layers, 0 of 18 on flat or opaque ones). Lowering the limits only adds false alarms.
Exports tried in the real tools (parallax/export_tests/run_export_tests.py): CSS in Chrome (found and fixed a unitless calc() that disabled the animation), Phaser 3.80.1 (pixel-identical to the preview at two camera positions, after adding the headroom offset), Tiled 1.12.2 (loads, keeps the factors). LDtk was not opened (not installed): its field names come from the official schema.
Camera: the stack's top-left is (0, 0), as for a Camera2D with anchor_mode FIXED_TOP_LEFT (the test project). With the default centred camera offset the root node by (vw/2, vh/2). Every Sprite2D is written with texture_filter = 1 (nearest).
Determinism: `draw` uses numpy's Generator, same machine and numpy version give the same bytes; another numpy version may change the presets.
Godot versions: the load, whole-pixel steps (16 moving layers of 3 presets), loop speed (-240.6 and -240.8 px/s for 240 on 4.3 and 4.4.1, -238.9 on 4.7.2), the 4-frame star animation (7 changes in 240 frames) and the zoom-out 0.5 picture (pixel-identical) were repeated on Godot 4.3 and 4.4.1 and match 4.7.2. Parallax2D needs 4.3+; the 4.1.1 on the author's machine was not used.
Not tested: Godot 4.5 and 4.6, a real game camera.
Exit: 0 ok (flags still print), 1 with --strict when flagged, 2 for a missing file, a bad spec or a bad option."""
import sys, os, json, math, shutil, difflib, argparse
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS_TOP = {"name", "viewport", "fps", "camera_px_per_s", "background", "min_zoom", "layers"}
KEYS_LAYER = {"file", "scroll", "px_per_frame", "depth", "repeat", "autoscroll_px_s", "depth_check", "frames", "frame_every"}


class SpecError(Exception):
    pass


def _unknown(k, known):
    m = difflib.get_close_matches(k, sorted(known), 1)
    return SpecError(f"unknown key '{k}'" + (f" (did you mean '{m[0]}'?)" if m else ""))


def _num(v, what, lo=None, hi=None, positive=False):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")):
        raise SpecError(f"{what} must be a finite number")
    if positive and v <= 0:
        raise SpecError(f"{what} must be above 0")
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise SpecError(f"{what} must be between {lo} and {hi}")
    return float(v)


def load_spec(path):
    try:
        s = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SpecError(f"cannot read spec {path}: {type(e).__name__}")
    if not isinstance(s, dict) or not isinstance(s.get("layers"), list) or not s["layers"]:
        raise SpecError("spec needs a non-empty 'layers' list")
    for k in s:
        if k not in KEYS_TOP:
            raise _unknown(k, KEYS_TOP)
    base = os.path.dirname(os.path.abspath(path))
    s.setdefault("name", os.path.splitext(os.path.basename(path))[0]); s.setdefault("viewport", [320, 180]); s.setdefault("fps", 60); s.setdefault("background", "#000000")
    if not isinstance(s["name"], str) or not s["name"]:
        raise SpecError("name must be a non-empty string")
    vp = s["viewport"]
    if not (isinstance(vp, list) and len(vp) == 2 and all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in vp)):
        raise SpecError("viewport must be [width, height], two whole numbers above 0")
    s["fps"] = _num(s["fps"], "fps", positive=True)
    if s.get("camera_px_per_s") is not None:
        s["camera_px_per_s"] = _num(s["camera_px_per_s"], "camera_px_per_s")
    if s.get("min_zoom") is not None:
        s["min_zoom"] = _num(s["min_zoom"], "min_zoom", 0, 1, positive=True)
    try:
        _hex(s["background"])
    except (ValueError, AttributeError, TypeError):
        raise SpecError("background must be a colour like #1b1a3a")
    seen = set()
    for i, L in enumerate(s["layers"]):
        if not isinstance(L, dict):
            raise SpecError(f"layer {i + 1} must be an object with a 'file', not {type(L).__name__}")
        for k in L:
            if k not in KEYS_LAYER:
                raise _unknown(k, KEYS_LAYER)
        if "file" not in L:
            raise SpecError("every layer needs a 'file'")
        if not isinstance(L["file"], str) or not L["file"]:
            raise SpecError(f"layer {i + 1}: file must be a file name")
        bn = os.path.basename(L["file"]).lower()
        if bn in seen:
            raise SpecError(f"two layers share the file name {bn}: the exports would overwrite each other")
        seen.add(bn)
        sc = L.get("scroll", 1.0); L["scroll_y_set"] = isinstance(sc, list)
        if isinstance(sc, list):
            if len(sc) != 2:
                raise SpecError(f"{L['file']}: scroll must be a number or [x, y]")
            L["scroll"] = [_num(sc[0], "scroll x"), _num(sc[1], "scroll y")]
        else:
            L["scroll"] = [_num(sc, "scroll")] * 2
        L["px_per_frame"] = _num(L.get("px_per_frame", 0), "px_per_frame"); L["depth"] = _num(L.get("depth", 0), "depth"); L.setdefault("repeat", "x"); L.setdefault("depth_check", True)
        if L.get("autoscroll_px_s") is not None:
            L["autoscroll_px_s"] = _num(L["autoscroll_px_s"], "autoscroll_px_s")
        if L["repeat"] not in ("x", "xy", "none"):
            raise SpecError(f"layer {L['file']}: repeat must be x, xy or none")
        fr = L.get("frames", [])
        if not (isinstance(fr, list) and all(isinstance(q, str) and q for q in fr)):
            raise SpecError(f"{L['file']}: frames must be a list of file names (the frames after the first)")
        L["frames"] = fr; L["frame_every"] = int(_num(L.get("frame_every", 12), "frame_every", 1)); L["frame_paths"] = [os.path.join(base, q) for q in fr]
        for q in L.get("frame_paths", []):
            if not os.path.exists(q):
                raise SpecError(f"missing frame file {os.path.basename(q)}")
        L["path"] = os.path.join(base, L["file"])
        if not os.path.exists(L["path"]):
            raise SpecError(f"missing layer file {L['file']}")
    return s


def _rgba(path):
    return np.array(Image.open(path).convert("RGBA"))


def _hex(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------- measures
def seam_stats(a, axis):
    """axis 1 = the x wrap (last column against the first), 0 = the y wrap. Transparent pixels count as one colour."""
    b = a.astype(int); b[b[..., 3] == 0] = 0
    d = np.abs(b - np.roll(b, -1, axis)).max(-1).mean(axis=1 - axis)      # step between i and i+1, the last one is the join
    seam, inner = float(d[-1]), d[:-1]; inner = inner[inner >= 1.0]                          # only columns that hold an edge: flat faces say nothing about a join
    rank = float((inner >= seam).mean()) if len(inner) else None; excess = seam / max(float(inner.max()) if len(inner) else 1.0, 1.0)
    # second, coarser look: mean of 4 columns on each side of every position, so noise a few pixels wide (windows, grass blades) does not hide a cut in the larger shapes
    k = 4; n = b.shape[axis]
    cols = np.moveaxis(b, axis, 0).astype(float); left = sum(np.roll(cols, j, 0) for j in range(k)) / k; right = sum(np.roll(cols, -1 - j, 0) for j in range(k)) / k
    d4 = np.abs(left - right).max(-1).mean(-1); seam4 = float(d4[-1]); keep = np.array([min((i - (n - 1)) % n, (n - 1 - i) % n) > 2 * k for i in range(n)]); inner4 = d4[keep & (d4 >= 1.0)]
    excess4 = seam4 / max(float(inner4.max()) if len(inner4) else 1.0, 1.0)
    vis = bool((seam >= 4 and excess > 1.25) or (seam4 >= 4 and excess4 > 1.25)); out = {"seam": round(seam, 2), "seam_rank": round(rank, 3) if rank is not None else None, "seam_excess": round(excess, 2), "seam4": round(seam4, 2), "seam4_excess": round(excess4, 2)}
    if axis == 1 and (a[..., 3] == 0).mean() > 0.05:                  # a silhouette layer (transparent sky): the top contour must be continuous across the join
        top = np.where((a[..., 3] > 0).any(0), np.argmax(a[..., 3] > 0, 0), a.shape[0]).astype(int); st = np.abs(top - np.roll(top, -1)); jump = int(st[-1]); inn = st[:-1]
        cj = bool(jump >= 3 and jump > 1.2 * (inn.max() if len(inn) else 0)); out["contour_jump"] = jump; out["contour_inner_max"] = int(inn.max()) if len(inn) else 0; vis = vis or cj
    out["visible"] = vis
    return out


def depth_stats(a):
    m = a[..., 3] > 128
    if m.mean() < 0.02:
        return None
    rgb = a[..., :3][m].astype(float) / 255; mx, mn = rgb.max(1), rgb.min(1)
    return {"sat": round(float(np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0).mean()), 3), "contrast": round(float(mx.std()), 3), "value": round(float(mx.mean()), 3), "cover": round(float(m.mean()), 2)}


def divisors(w):
    return [d for d in range(1, w) if w % d == 0]


def speed_info(w, pf):
    """(frames per loop or None, note or None). A negative speed scrolls the other way and is judged by its size."""
    pf = abs(pf)
    if pf == 0:
        return None, None
    if pf > 1 and pf != int(pf):
        from fractions import Fraction
        fr_ = Fraction(pf).limit_denominator(8)
        if abs(float(fr_) - pf) < 1e-9:
            q, p_ = fr_.denominator, fr_.numerator                                    # p_ px every q frames, in whole-pixel steps of floor(n) and floor(n)+1: steady, and it closes after q*w/gcd(w, p_) frames
            return q * w // math.gcd(w, p_), f"{pf:g} px/frame = {p_} px every {q} frames (steps alternate {int(pf)} and {int(pf) + 1}; steady against a layer at {int(pf)} or {int(pf) + 1})"
    if pf >= 1:
        if pf != int(pf) or w % int(pf):
            near = sorted(divisors(w), key=lambda d: abs(d - pf))[:2]
            return None, f"{pf:g} px/frame does not divide {w}: the loop does not close (valid nearby: {', '.join(map(str, sorted(near)))})"
        return w // int(pf), None
    k = round(1 / pf)
    if abs(pf * k - 1) > 1e-9:
        return None, f"{pf:g} px/frame is not 1/k: whole-pixel steps do not repeat evenly and the loop does not close (use 1/2, 1/3, 1/4 ... or a whole number)"
    return w * k, f"{pf:g} px/frame = 1 px every {k} frames (whole pixels, slow)"


def check(spec):
    vw, vh = spec["viewport"]; fps = spec["fps"]; cam = spec.get("camera_px_per_s")
    rows, flags, frames = [], [], []
    for L in spec["layers"]:
        a = _rgba(L["path"]); h, w = a.shape[:2]; name = L["file"]; r = {"file": name, "size": [w, h], "scroll": L["scroll"], "px_per_frame": L["px_per_frame"], "notes": []}
        if L["repeat"] in ("x", "xy"):
            sx = seam_stats(a, 1); r["seam_x"] = sx
            if sx["visible"]:
                flags.append(f"{name}: visible seam at the x wrap (rank {sx['seam_rank']}, excess {sx['seam_excess']})")
            elif sx["seam"] >= 8 and sx["seam_rank"] is not None and sx["seam_rank"] <= 0.01:
                r["notes"].append("possible seam: the join step is among the largest in the layer; look at `seam --view`")
            if w < vw:
                r["notes"].append(f"narrower than the viewport ({w} < {vw}): it repeats on screen; export writes repeat_times {math.ceil(vw / w) + 1} (tested in Godot 4.7.2)")
            fr, note = speed_info(w, L["px_per_frame"])
            if note:
                r["notes"].append(note)
                if "does not" in note:
                    flags.append(f"{name}: {note}")                       # 1 px every k frames is a steady slow scroll: a note, not a flag
            if fr:
                frames.append(fr)
                r["notes"].append(f"loops every {fr} frames ({fr / fps:.1f} s)")
        if L["repeat"] == "xy":
            sy = seam_stats(a, 0); r["seam_y"] = sy
            if sy["visible"]:
                flags.append(f"{name}: visible seam at the y wrap")
        if cam and L["scroll"][0]:
            step = L["scroll"][0] * cam / fps
            r["camera_step_px_per_frame"] = round(step, 4)
            if L["px_per_frame"] and abs(abs(L["px_per_frame"]) - step) > 0.01:
                r["notes"].append(f"loop speed {L['px_per_frame']:g} px/frame is not the camera-mode speed {step:g} px/frame (fine if the two modes are meant to differ)")
            if 0 < abs(step) < 1 and abs(1 / abs(step) - round(1 / abs(step))) < 1e-6:
                r["notes"].append(f"live camera: 1 px every {round(1 / abs(step))} frames (a steady slow scroll)")
            elif abs(step - round(step)) > 1e-6:
                flags.append(f"{name}: live camera moves it {step:g} px/frame, not whole pixels (jitter risk; see scroll {L['scroll'][0]:g} x {cam / fps:g} px/frame)")
        if h < vh:
            flags.append(f"{name}: shorter than the viewport ({h} < {vh})")
        for q in L.get("frame_paths", []):
            if Image.open(q).size != (w, h):
                flags.append(f"{name}: frame {os.path.basename(q)} has a different size")
        if L.get("frame_paths", []):
            r["frames"] = 1 + len(L.get("frame_paths", [])); r["cycle_frames"] = r["frames"] * L.get("frame_every", 12)
        z = spec.get("min_zoom")
        if z and z < 1:
            if L["repeat"] == "none" and w < vw / z:
                flags.append(f"{name}: camera zoomed out to {z:g} shows {vw / z:.0f} px across but this layer does not repeat and is {w} wide")
            if h < vh / z and L["repeat"] != "xy":
                flags.append(f"{name}: camera zoomed out to {z:g} shows {vh / z:.0f} px of height, the layer is {h}: gaps above it (Godot repeats in y only with repeat_size y; use 'repeat': 'xy' or draw it taller)")
        if L["scroll_y_set"] and L["scroll"][1] and L["scroll"][1] < 1 and h > vh:
            r["notes"].append(f"camera may rise {(h - vh) / (1 - L['scroll'][1]):.0f} px before this layer shows a gap above it")
        if L["scroll_y_set"] and L["scroll"][1] and h == vh:
            r["notes"].append("y scroll set but the layer is exactly viewport height: no headroom to move")
        d = depth_stats(a); r["depth_stats"] = d; rows.append((L, r))
    hs = {r["size"][1] for _, r in rows}
    if len(hs) > 1:
        flags.append(f"layer heights differ: {sorted(hs)}")
    sc = [L["scroll"][0] for L in spec["layers"]]
    if any(b < a - 1e-9 for a, b in zip(sc, sc[1:])):
        flags.append("scroll factors are not rising from back to front (layers listed back to front)")
    # atmospheric perspective: only landscape planes (a quarter of the picture or more) are compared; a far plane that is more saturated or higher in contrast is fine when it is lighter (haze by value, as in real packs)
    dl = sorted([(L["depth"], L["file"], r["depth_stats"]) for L, r in rows if L["depth_check"] and r["depth_stats"] and r["depth_stats"]["cover"] >= 0.25], key=lambda t: -t[0])
    for (d1, n1, s1), (d2, n2, s2) in zip(dl, dl[1:]):
        hazier = s1["value"] > s2["value"] + 0.02
        if d1 > d2 and s1["sat"] > s2["sat"] + 0.05 and not hazier:
            flags.append(f"depth palette: {n1} (farther) is more saturated than {n2} and not lighter ({s1['sat']} vs {s2['sat']}, value {s1['value']} vs {s2['value']})")
        if d1 > d2 and s1["contrast"] > s2["contrast"] + 0.05 and not hazier:
            flags.append(f"depth palette: {n1} (farther) has more contrast than {n2} and is not lighter ({s1['contrast']} vs {s2['contrast']})")
    loop = math.lcm(*frames) if frames else None
    for L, r in rows:
        if loop and r.get("cycle_frames") and loop % r["cycle_frames"]:
            flags.append(f"{L['file']}: its {r['frames']}-frame animation (every {L['frame_every']} frames, cycle {r['cycle_frames']}) does not divide the {loop}-frame loop")
    return {"name": spec["name"], "viewport": [vw, vh], "layers": [r for _, r in rows], "loop_frames": loop, "loop_seconds": round(loop / fps, 2) if loop else None, "flags": flags}


# ---------------------------------------------------------------- preview
def _hold_x(a, ox, vw):
    return a[:, (np.arange(vw) + int(ox)) % a.shape[1]]


def frame_at(spec, layers, xs, camy=0.0, idx=0):
    vw, vh = spec["viewport"]; out = np.zeros((vh, vw, 4), np.uint8); out[..., :3] = _hex(spec["background"]); out[..., 3] = 255
    for (L, a), ox in zip(layers, xs):
        if isinstance(a, list):
            a = a[(idx // L.get("frame_every", 12)) % len(a)]                       # animated layer: the frame for this preview frame
        h, w = a.shape[:2]
        if L["repeat"] == "none":
            col = np.zeros((h, vw, 4), np.uint8); src = np.arange(vw) + int(ox); ok = (src >= 0) & (src < w); col[:, ok] = a[:, src[ok]]
        else:
            col = _hold_x(a, ox, vw)
        top = int(np.clip(h - vh - round(camy * L["scroll"][1]), 0, max(h - vh, 0)))
        part = col[top:top + vh] if h >= vh else col
        y0 = vh - part.shape[0]; al = part[..., 3:4].astype(float) / 255
        out[y0:, :, :3] = (part[..., :3] * al + out[y0:, :, :3] * (1 - al)).astype(np.uint8)
    return out


def load_layers(spec):
    """[(layer, array)] with a list of arrays for an animated layer"""
    return [(L, [_rgba(L["path"])] + [_rgba(q) for q in L.get("frame_paths", [])] if L.get("frame_paths", []) else _rgba(L["path"])) for L in spec["layers"]]


def positions(spec, L, i, subpixel):
    if subpixel:
        cam = (spec.get("camera_px_per_s") or 0) / spec["fps"]
        return int(math.floor(L["scroll"][0] * cam * i + 0.5))        # each layer rounds its own position: the jitter policy to avoid
    v = L["px_per_frame"] * i
    return int(math.copysign(math.floor(abs(v)), v))


def _cp(a, b):
    if not (os.path.exists(b) and os.path.samefile(a, b)):
        shutil.copyfile(a, b)


def preview(spec, out, frames=None, scale=3, subpixel=False, bob=0, camera=None, pingpong=None, every=None):
    """GIF of the stack. A GIF cannot hold a long loop: a walking stack closes only after thousands of frames, so a short excerpt jumps back to the start. With ping-pong (the default when the true loop does not
    fit) the camera goes right for half the frames and back for the other half: every layer is exactly where it started when the GIF repeats, whatever its speed or width."""
    sys.path.insert(0, ROOT)
    if every is None:
        every = 3 if spec["fps"] == 60 else 1                                           # 3 engine frames per GIF frame at 50 ms (a GIF delay is a multiple of 10 ms): exactly real time
    if camera is not None:
        spec = dict(spec, camera_px_per_s=camera); subpixel = True                      # camera mode: positions are scroll x camera speed, rounded per layer
    from pixdraw.export import save_gif
    layers = load_layers(spec)
    rep = check(spec); lcm = rep["loop_frames"]; cyc = 1
    for q in rep["layers"]:
        if q.get("cycle_frames"):
            cyc = math.lcm(cyc, q["cycle_frames"])
    cap = 1000 * every
    n = frames or min(lcm or 120, cap)
    if lcm and not frames and lcm <= cap and lcm % every:
        n = frames or min(math.lcm(lcm, every), 4 * cap)                                # whole loop only if the GIF frames land on it
    if pingpong is None:
        pingpong = (lcm is None or lcm > n or subpixel or n % every != 0)
    if pingpong:
        step = math.lcm(2, cyc, every); n = frames or 320 * every // 2; n = -(-n // step) * step            # even, and a whole number of animation cycles: frame n is then frame 0 again
    jmap = (lambda i: i if i <= n // 2 else n - i) if pingpong else (lambda i: i)
    pos = lambda i: [positions(spec, L, jmap(i), subpixel) for L, _ in layers]
    f_end = frame_at(spec, layers, pos(n), 0.0, n)
    closes = bool(np.array_equal(frame_at(spec, layers, pos(0), 0.0, 0), f_end))        # the last frame is followed by the first: only true when frame n equals frame 0
    ims = []
    for i in range(0, n, every):
        camy = bob * (1 - math.cos(2 * math.pi * i / n)) / 2 if bob else 0.0
        f = frame_at(spec, layers, pos(i), camy, i)
        ims.append(Image.fromarray(f).convert("RGB").resize((f.shape[1] * scale, f.shape[0] * scale), Image.NEAREST))
    ms = max(20, round(1000 * every / spec["fps"])); speed = round(ms * spec["fps"] / (1000 * every), 2)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); save_gif(ims, out, ms)
    steps = {L["file"]: [positions(spec, L, i, subpixel) for i in range(12)] for L in spec["layers"] if L["scroll"][0] and (subpixel or L["px_per_frame"])}
    return {"gif": out, "frames": n, "size": [ims[0].width, ims[0].height], "ms_per_frame": ms, "every": every, "real_time_factor": speed, "loop_closes": closes, "first_12_positions": steps, "pingpong": bool(pingpong), "true_loop_frames": lcm}


HTML = """<!doctype html><meta charset=utf-8><title>__NAME__ parallax preview</title>
<style>body{background:#1c1c22;color:#ddd;font:14px system-ui;margin:16px}canvas{image-rendering:pixelated;display:block;border:1px solid #444;max-width:100%}label{margin-right:14px}.r{margin:8px 0}code{color:#9cf}</style>
<h3>__NAME__ <small>(pix_parallax, real-time preview; a flag in check is advice, the engine is the judge)</small></h3>
<canvas id=c width=__VW__ height=__VH__ style="width:__SW__px"></canvas>
<div class=r><label>mode <select id=mode><option value=loop>loop (px_per_frame x fps)</option><option value=camera>camera (scroll x camera speed)</option></select></label>
<label>snap <select id=snap><option value=cam>round camera, then layers</option><option value=layer>round each layer</option><option value=none>no rounding (browser decides)</option></select></label>
<label>camera px/s <input id=cs type=range min=0 max=960 value=__CAM__> <code id=csv></code></label><label>camera y bob px <input id=bob type=range min=0 max=40 value=0></label>
<label><input id=pause type=checkbox> pause</label></div>
<div class=r id=info></div>
<script>
const L=__LAYERS__,VW=__VW__,VH=__VH__,FPS=__FPS__,cv=document.getElementById('c'),cx=cv.getContext('2d');cx.imageSmoothingEnabled=false;
const imgs=L.map(l=>l.srcs.map(s=>{const i=new Image();i.src=s;return i}));
const $=id=>document.getElementById(id);let t0=performance.now(),paused=false,tp=0;
if(matchMedia('(prefers-reduced-motion: reduce)').matches){$('pause').checked=true}
function rnd(v,m){return m==='none'?v:Math.floor(v+0.5)}
function frame(now){
 const t=$('pause').checked?tp:(tp=(now-t0)/1000);const mode=$('mode').value,snap=$('snap').value,cs=+$('cs').value;$('csv').textContent=cs;
 const cam=t*cs,camy=+$('bob').value*(1-Math.cos(t*2))/2,cr=snap==='cam'?rnd(cam):cam;cx.fillStyle='__BG__';cx.fillRect(0,0,VW,VH);
 L.forEach((l,k)=>{const im=imgs[k][Math.floor(t*FPS/l.fe)%imgs[k].length];if(!im.complete)return;const w=im.naturalWidth,h=im.naturalHeight;
  let x=mode==='loop'?t*FPS*l.pf:cr*l.sx;x=snap==='cam'?rnd(x,'r'):rnd(x,snap);
  const top=Math.max(0,Math.min(h-VH,h-VH-rnd(camy*l.sy,snap==='none'?'none':'r'))),dy=h<VH?VH-h:0;
  if(l.rep==='none'){cx.drawImage(im,-x,dy-top);return}
  const xo=((x%w)+w)%w;for(let o=-xo;o<VW;o+=w)cx.drawImage(im,snap==='none'?o:Math.round(o),dy-top);});
 $('info').textContent=L.map(l=>l.name+' '+(mode==='loop'?(l.pf*FPS)+' px/s':(l.sx*cs/FPS).toFixed(2)+' px/frame')).join('   |   ');
 requestAnimationFrame(frame)}
requestAnimationFrame(frame)
</script>"""


def preview_html(spec, out):
    import base64, html as _html
    vw, vh = spec["viewport"]; ls = []
    for L in spec["layers"]:
        srcs = ["data:image/png;base64," + base64.b64encode(open(q, "rb").read()).decode() for q in [L["path"]] + L.get("frame_paths", [])]
        ls.append({"name": _html.escape(os.path.splitext(os.path.basename(L["file"]))[0]), "srcs": srcs, "fe": L.get("frame_every", 12), "sx": L["scroll"][0], "sy": L["scroll"][1], "pf": L["px_per_frame"], "rep": L["repeat"]})
    import html as _html
    h = (HTML.replace("__NAME__", _html.escape(spec["name"])).replace("__LAYERS__", json.dumps(ls)).replace("__VW__", str(vw)).replace("__VH__", str(vh)).replace("__SW__", str(vw * 3))
         .replace("__FPS__", str(spec["fps"])).replace("__CAM__", str(int(spec.get("camera_px_per_s") or 120))).replace("__BG__", spec["background"]))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, "w", encoding="utf-8").write(h)
    return out


# ---------------------------------------------------------------- export
def _id(i, f):
    return f"{i + 1}_" + "".join(c if c.isalnum() else "_" for c in os.path.splitext(f)[0])


def _node(name):
    """A Godot node or file name: letters, digits and _ only (Godot refuses . : @ / " % in node names)."""
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in name) or "layer"


def export_godot(spec, out_dir, res_dir=None, mode="loop", min_zoom=None):
    vw, vh = spec["viewport"]; fps = spec["fps"]; res_dir = (res_dir or f"res://bg/{spec['name']}").rstrip("/")
    os.makedirs(out_dir, exist_ok=True)
    sub = []
    nres = sum(1 + len(L.get("frame_paths", [])) for L in spec["layers"]) + sum(1 for L in spec["layers"] if L.get("frame_paths", [])) + 1
    head = [f'[gd_scene load_steps={nres} format=3]', ""]
    body = [f'[node name="{_node(spec["name"])}" type="Node2D"]', ""]
    for i, L in enumerate(spec["layers"]):
        _cp(L["path"], os.path.join(out_dir, os.path.basename(L["file"])))
        a = Image.open(L["path"]); w, h = a.size; fn = os.path.basename(L["file"]); nm = _node(os.path.splitext(fn)[0])
        head.append(f'[ext_resource type="Texture2D" path="{res_dir}/{fn}" id="{_id(i, fn)}"]')
        fids = []
        for q in L.get("frame_paths", []):
            _cp(q, os.path.join(out_dir, os.path.basename(q))); fq = os.path.basename(q); fids.append(f"{_id(i, fq)}_{len(fids) + 1}")
            head.append(f'[ext_resource type="Texture2D" path="{res_dir}/{fq}" id="{fids[-1]}"]')
        rep = (w if L["repeat"] in ("x", "xy") else 0, h if L["repeat"] == "xy" else 0)
        body += [f'[node name="{nm}" type="Parallax2D" parent="."]']
        if mode == "loop":
            body += ["scroll_scale = Vector2(0, 0)", "ignore_camera_scroll = true"]
            if L["px_per_frame"]:
                body.append(f"autoscroll = Vector2({-L['px_per_frame'] * fps:g}, 0)")
        else:
            body.append(f"scroll_scale = Vector2({L['scroll'][0]:g}, {L['scroll'][1]:g})")
            if L.get("autoscroll_px_s"):
                body.append(f"autoscroll = Vector2({-L['autoscroll_px_s']:g}, 0)")
        if rep != (0, 0):
            body.append(f"repeat_size = Vector2({rep[0]}, {rep[1]})")
            nrep = math.ceil(vw / (min_zoom if min_zoom and min_zoom < 1 else 1) / w) + 1 if (w < vw or (min_zoom and min_zoom < 1)) else 0
            if nrep:
                body.append(f"repeat_times = {nrep}")      # 0.5 zoom on a 320 layer in a 320 view: 3 (tested in Godot 4.7.2)
        if fids:
            allids = [_id(i, fn)] + fids; speed = spec["fps"] / L.get("frame_every", 12)
            frs = ", ".join('{"duration": 1.0, "texture": ExtResource("%s")}' % q for q in allids)
            sub.append(f'[sub_resource type="SpriteFrames" id="SpriteFrames_{i + 1}"]')
            sub.append('animations = [{"frames": [%s], "loop": true, "name": &"default", "speed": %g}]' % (frs, speed)); sub.append("")
            body += ["", f'[node name="Sprite2D" type="AnimatedSprite2D" parent="{nm}"]', f'sprite_frames = SubResource("SpriteFrames_{i + 1}")', 'animation = &"default"', "autoplay = &\"default\"", "texture_filter = 1", "centered = false"]
        else:
            body += ["", f'[node name="Sprite2D" type="Sprite2D" parent="{nm}"]', f'texture = ExtResource("{_id(i, fn)}")', "texture_filter = 1", "centered = false"]
        if h != vh:
            body.append(f"position = Vector2(0, {vh - h})")
        body.append("")
    p = os.path.join(out_dir, _node(spec["name"]) + ".tscn"); open(p, "w", encoding="utf-8", newline="\n").write("\n".join(head + [""] + sub + body))
    return p


# ---------------------------------------------------------------- heal (advisory: writes a NEW file, copies pixels only)
def _colours(a):
    return {tuple(c) for c in a.reshape(-1, 4)}


def heal_mincut(a, band=16):
    """Overlap the last `band` columns on the first `band` and cut along the cheapest path (one path column per row, +-1 per row). The layer becomes `band` columns narrower."""
    h, w = a.shape[:2]; band = min(band, w // 4)
    t, hd = a[:, w - band:].astype(int), a[:, :band].astype(int); t[t[..., 3] == 0] = 0; hd[hd[..., 3] == 0] = 0       # colour under alpha 0 must not steer the cut
    cost = np.abs(t - hd).max(-1).astype(float); cost[:, 0] += 1e6                                                 # path column 0 would join untested columns at the new wrap: keep the path at 1 or more
    acc = cost.copy(); back = np.zeros((h, band), int)
    for y in range(1, h):
        for x in range(band):
            lo, hi = max(x - 1, 0), min(x + 2, band); j = lo + int(np.argmin(acc[y - 1, lo:hi])); acc[y, x] = cost[y, x] + acc[y - 1, j]; back[y, x] = j
    x = int(np.argmin(acc[-1])); path = np.zeros(h, int)
    for y in range(h - 1, -1, -1):
        path[y] = x; x = back[y, x]
    blend = np.where((np.arange(band)[None, :] < path[:, None])[..., None], a[:, w - band:], a[:, :band])      # left of the path: the tail, right of it: the head
    return np.concatenate([blend, a[:, band:w - band]], 1)


def heal_profile(a, band=24):
    """Silhouette layers (transparent sky): make the top contour continuous across the join by shifting the last `band` columns up or down (pixels copied; exposed rows repeat the column edge)."""
    h, w = a.shape[:2]; band = min(band, w // 4)
    if (a[..., 3] == 0).mean() < 0.05:
        raise SpecError("--heal profile needs a silhouette layer (transparent sky); try mincut")
    if not ((a[:, 0, 3] > 0).any() and (a[:, w - 1, 3] > 0).any()):
        raise SpecError("--heal profile needs one ground contour across the whole width: an end column is empty (a cloud or a tree touches the edge). Use mincut, or move the object")
    top = lambda x: int(np.argmax(a[:, x, 3] > 0))
    delta = top(0) - top(w - 1); out = a.copy()
    for k in range(band):
        x = w - band + k; u = (k + 1) / band; sh = int(round(delta * (1 - math.cos(math.pi * u)) / 2)); col = a[:, x]
        if sh > 0:
            out[sh:, x] = col[:h - sh]; out[:sh, x] = (0, 0, 0, 0)
        elif sh < 0:
            out[:h + sh, x] = col[-sh:]; out[h + sh:, x] = col[-1]
    return out


def heal(path, out, how, band=None):
    if os.path.exists(out):
        raise SpecError(f"{out} exists: --heal never overwrites")
    if band is not None and band < 1:
        raise SpecError("--band must be 1 or more")
    a = _rgba(path); before = seam_stats(a, 1); used = min(band or (16 if how == "mincut" else 24), a.shape[1] // 4)
    if used < 1:
        raise SpecError("the layer is too narrow to heal (needs at least 4 columns)")
    b = heal_mincut(a, used) if how == "mincut" else heal_profile(a, used)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); Image.fromarray(b).save(out)
    return {"out": out, "before": before, "after": seam_stats(b, 1), "size_before": list(a.shape[1::-1]), "size_after": list(b.shape[1::-1]), "new_colours": len(_colours(b) - _colours(a)), "band": used}


# ---------------------------------------------------------------- other engines (text snippets)
def _key(l):
    return os.path.splitext(os.path.basename(l["file"]))[0]


def export_text(spec, fmt):
    vw, vh = spec["viewport"]; L = spec["layers"]; nm = spec["name"]
    if fmt == "json":
        return json.dumps(spec, indent=1, default=str)
    if fmt == "tiled":
        # Tiled JSON fields read from doc.mapeditor.org on 2026-11-18: layer parallaxx/parallaxy (default 1, since 1.5), map parallaxoriginx/y (default 0, since 1.8); 1 = moves with the camera, 0 = fixed (same as Godot).
        # Opened with Tiled 1.12.2 (tiled --export-map tmx): imagelayer image / repeatx / parallaxx / parallaxy load and are kept (export_tests/run_export_tests.py).
        lay = [{"id": i + 1, "name": _key(l), "type": "imagelayer", "image": os.path.basename(l["file"]), "repeatx": l["repeat"] in ("x", "xy"), "repeaty": l["repeat"] == "xy",
                "parallaxx": l["scroll"][0], "parallaxy": l["scroll"][1], "opacity": 1, "visible": True, "x": 0, "y": 0} for i, l in enumerate(L)]
        return json.dumps({"type": "map", "version": "1.10", "orientation": "orthogonal", "renderorder": "right-down", "width": max(1, vw // 16), "height": max(1, vh // 16), "tilewidth": 16, "tileheight": 16,
                           "infinite": False, "parallaxoriginx": 0, "parallaxoriginy": 0, "layers": lay, "tilesets": [], "nextlayerid": len(lay) + 1, "nextobjectid": 1}, indent=1)
    if fmt == "ldtk":
        out = [f"// LDtk layer definitions for '{nm}'. LDtk's factor is NOT the Godot/Tiled one. Schema (LDtk 1.5.3): parallaxFactorX/Y 'from -1 to 1, defaults to 0', so 0 = scrolls normally and factor = 1 - scroll.",
               "// parallaxScaling (schema default true) also scales the layer; false keeps the pixel size. A scroll above 2 or below 0 gives a factor outside -1..1."]
        for l in L:
            fx, fy = round(1 - l["scroll"][0], 4), round(1 - l["scroll"][1], 4); bad = "   // OUT OF RANGE" if not (-1 <= fx <= 1 and -1 <= fy <= 1) else ""
            out.append(f'{{"identifier": "{_key(l)}", "parallaxFactorX": {fx}, "parallaxFactorY": {fy}, "parallaxScaling": false}}{bad}')
        return "\n".join(out)
    if fmt == "phaser":
        short = [l["file"] for l in L if Image.open(l["path"]).height < vh]
        if short:
            raise SpecError("phaser export needs layers at least as tall as the viewport (a TileSprite tiles a short texture vertically): " + ", ".join(short))
        out = [f"// Phaser 3 parallax for '{nm}' ({vw}x{vh}). Put the three parts in your scene. tilePositionX/Y: docs.phaser.io TileSprite. Run in Phaser 3.80.1: its canvas equals the pix_parallax preview pixel for pixel (export_tests/run_export_tests.py).",
               "// preload()"] + [f"this.load.image('{_key(l)}', '{os.path.basename(l['file'])}');" for l in L] + ["", "// create()", "this.layers = [];"]
        for l in L:
            hh = Image.open(l["path"]).height
            out.append(f"this.layers.push({{ s: this.add.tileSprite(0, 0, {vw}, {vh}, '{_key(l)}').setOrigin(0, 0).setScrollFactor(0), fx: {l['scroll'][0]}, fy: {l['scroll'][1]}, base: {max(hh - vh, 0)} }});   // base = headroom rows above the view")
        out += ["", "// update(): whole pixels = round the camera first, then each product once", "const cam = this.cameras.main, cx = Math.round(cam.scrollX), cy = Math.round(cam.scrollY);",
                "this.layers.forEach(l => { l.s.tilePositionX = Math.round(cx * l.fx); l.s.tilePositionY = l.base + Math.round(cy * l.fy); });"]
        return "\n".join(out)
    if fmt == "css":
        out = [f"/* '{nm}': scroll-driven parallax, layers back to front (MDN: animation-timeline: scroll()). Run in Chrome (Playwright): at scroll S a layer sits at -S x factor px; reduced motion keeps it still. */",
               f".stage{{position:sticky;left:0;width:{vw}px;height:{vh}px;overflow:hidden}}",
               ".stage .layer{position:absolute;inset:0;background-repeat:repeat-x;background-position:0 100%;image-rendering:pixelated;will-change:transform}",
               "@keyframes slide{to{transform:translateX(calc(var(--range) * var(--f) * -1px))}}",
               "@supports (animation-timeline: scroll()){.stage .layer{width:calc(100% + var(--range) * 1px);animation:slide linear both;animation-timeline:scroll(root x)}}",
               "@media (prefers-reduced-motion: reduce){.stage .layer{animation:none}}"]
        out += [f".layer.{_key(l)}{{background-image:url({os.path.basename(l['file'])});--f:{l['scroll'][0]};--range:{vw * 4}}}" for l in L]
        out.append("/* --range = how far the page can scroll in px (scrollWidth - clientWidth); a layer moves range x factor, so factor 1 keeps pace with the content. */")
        return "\n".join(out)
    raise SpecError("format must be json, tiled, ldtk, phaser or css")


# ---------------------------------------------------------------- review (numbers and a contact sheet for judging a stack, drawn or hand made)
def layer_metrics(a):
    """colours, share of opaque 2x2 cells that are a checker (dither), mean horizontal run length of opaque pixels, opaque share"""
    op = a[..., 3] > 128; cols = len({tuple(c) for c in a[op].reshape(-1, 4)}) if op.any() else 0
    c = a[..., :3].astype(int); h, w = c.shape[:2]
    if h < 2 or w < 2 or not op.any():
        return {"colours": cols, "dither": 0.0, "run": 0.0, "cover": round(float(op.mean()), 2)}
    e = lambda x, y: (np.abs(x - y).sum(-1) > 0)
    chk = (~e(c[:-1, :-1], c[1:, 1:])) & (~e(c[:-1, 1:], c[1:, :-1])) & e(c[:-1, :-1], c[:-1, 1:]) & op[:-1, :-1] & op[1:, 1:] & op[:-1, 1:] & op[1:, :-1]
    cells = op[:-1, :-1] & op[1:, 1:] & op[:-1, 1:] & op[1:, :-1]
    brk = e(c[:, :-1], c[:, 1:]) | (op[:, :-1] != op[:, 1:]); nruns = int(brk[op[:, :-1]].sum()) + int(op[:, 0].sum())
    return {"colours": cols, "dither": round(float(chk.sum() / max(cells.sum(), 1)), 3), "run": round(float(op.sum() / max(nruns, 1)), 1), "cover": round(float(op.mean()), 2)}


def review(spec, out, ref=None):
    from PIL import ImageDraw
    layers = load_layers(spec); rows = []; flags = []
    for L, a in layers:
        a0 = a[0] if isinstance(a, list) else a; m = layer_metrics(a0); m["file"] = L["file"]; m["depth"] = L["depth"]; rows.append(m)
        far = L["depth"] >= 50 and L["depth_check"]
        lim = 16 if far else 64
        if m["colours"] > lim:
            flags.append(f"{L['file']}: {m['colours']} colours (limit {lim} for a {'far' if far else 'near'} layer; share one palette across its frames; reduce by sharing ramps between sprites, not by quantising the layer, which erases small sprites)")
        if m["dither"] > 0.10:
            flags.append(f"{L['file']}: dither share {m['dither'] * 100:.1f}% (a real CC0 pack reaches 8% on gradients; above 10% it reads as a screen of noise)")
        if far and m["cover"] > 0.2 and m["run"] < 5:
            flags.append(f"{L['file']}: mean run {m['run']} px on a far layer (far layers should be flat, runs of 6 or more)")
    base = frame_at(spec, layers, [0] * len(layers), 0.0, 0)[..., :3]; sc = 3
    tiles = [("stack at rest (3x)", Image.fromarray(base).resize((base.shape[1] * sc, base.shape[0] * sc), Image.NEAREST))]
    if ref:
        ri = Image.open(ref).convert("RGB"); tiles.append(("reference (comparison only)", ri.resize((ri.width * sc, ri.height * sc), Image.NEAREST)))
    for (L, a), m in zip(layers, rows):
        a0 = a[0] if isinstance(a, list) else a; bg = Image.new("RGBA", (a0.shape[1], a0.shape[0]), (110, 110, 120, 255)); bg.alpha_composite(Image.fromarray(a0))
        tiles.append((f"{L['file']}  {m['colours']} colours  dither {m['dither'] * 100:.1f}%  run {m['run']}", bg.convert("RGB").resize((a0.shape[1] * 2, a0.shape[0] * 2), Image.NEAREST)))
    wmax = max(t.width for _, t in tiles); y = 6; sheet_h = sum(t.height + 22 for _, t in tiles) + 6
    S = Image.new("RGB", (wmax + 12, sheet_h), (24, 24, 28)); d = ImageDraw.Draw(S)
    for label, t in tiles:
        d.text((6, y), label, fill=(235, 235, 235)); S.paste(t, (6, y + 14)); y += t.height + 22
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); S.save(out)
    return {"sheet": out, "layers": rows, "flags": flags}


# ---------------------------------------------------------------- seam view
def seam_view(path, out, axis_y=False):
    a = _rgba(path); h, w = a.shape[:2]
    if axis_y:
        r = np.roll(a, h // 2, 0).copy(); r[h // 2, :] = (255, 0, 0, 255)
    else:
        r = np.roll(a, w // 2, 1).copy(); r[:, w // 2] = (255, 0, 0, 255)
    bg = Image.new("RGBA", (r.shape[1], r.shape[0]), (60, 60, 66, 255)); bg.alpha_composite(Image.fromarray(r))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    bg.convert("RGB").resize((bg.width * 2, bg.height * 2), Image.NEAREST).save(out)
    return {"view": out, "axis": "y" if axis_y else "x"}


# ---------------------------------------------------------------- draw (layers from code)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _layers as LY

# Presets: hour (time of day) + layers back to front. Layer keys: kind, name, sx/sy (scroll), pf (px per frame), depth, dc (depth check), w (layer width in screens), p (kind parameters).
# Rg(lo, hi) is drawn from the seed; snow=0.6 means "60 % of seeds".
class Rg(tuple):
    """a (lo, hi) range of whole numbers drawn from the seed"""

    def __new__(cls, lo, hi):
        return super().__new__(cls, (lo, hi))


def _L(kind, name, sx, sy, pf, depth, dc=True, w=1, **p):
    return dict(kind=kind, name=name, sx=sx, sy=sy, pf=pf, depth=depth, dc=dc, w=w, p=p)


PRESETS = {
    "dusk_hills": dict(hour="dusk", pal=dict(disc_y=0.50), layers=[
        _L("clouds", "clouds", 0.125, 0.0, 1, 90, False, w=2, n=3),
        _L("mountains", "mountains", 0.25, 0.1, 2, 70, True, w=2, base="#7a6aa8", t=0.55, base_y=0.62, amp=0.26, n_peaks=Rg(2, 3), snow=0.6, fog=True),
        _L("hills", "hills", 0.5, 0.25, 4, 40, True, base="#4a5aa0", t=0.30, base_y=0.78, amp=0.14),
        _L("trees", "pines", 0.625, 0.45, 5, 20, True, base="#2f4a6a", t=0.12, ground_y=0.88, hmin=16, hmax=30, n_clusters=Rg(3, 5), per=6, loners=4),
        _L("ground", "grass", 1.0, 0.8, 8, 5, True, base="#1c3a38", base_y=0.96),
        _L("foreground", "rocks", 1.25, 0.9, 10, 0, False, base="#101c28", base_y=0.97, kind2="rocks", n=4)]),
    "night_city": dict(hour="night", layers=[
        _L("clouds", "clouds", 0.125, 0.0, 1, 90, False, w=2, n=3),
        _L("skyline", "skyline_far", 0.25, 0.1, 2, 70, True, base="#4a4488", t=0.50, base_y=0.86, hmin=40, hmax=80, detail=0.0),
        _L("skyline", "skyline_mid", 0.5, 0.25, 4, 40, True, base="#2a2c5c", t=0.25, base_y=0.92, hmin=40, hmax=95, detail=1.0, lit=0.2),
        _L("ground", "street", 1.0, 0.8, 8, 5, True, base="#14142c", base_y=0.97)]),
    "forest": dict(hour="noon", layers=[
        _L("clouds", "clouds", 0.125, 0.0, 1, 90, False, w=2, n=3),
        _L("hills", "far_hills", 0.25, 0.1, 2, 70, True, w=2, base="#7aa89a", t=0.60, base_y=0.66, amp=0.20, harmonics=(1, 2, 3)),
        _L("trees", "far_pines", 0.5, 0.25, 4, 40, True, base="#4f8a6a", t=0.35, ground_y=0.80, hmin=12, hmax=22, n_clusters=5, per=5, loners=5, broadleaf=0.25),
        _L("trees", "near_pines", 0.75, 0.45, 5, 20, True, base="#2a5a44", t=0.10, ground_y=0.92, hmin=22, hmax=40, n_clusters=4, per=4, loners=3, broadleaf=0.35),
        _L("ground", "grass", 1.0, 0.8, 8, 5, True, base="#1f4a2a", base_y=0.97),
        _L("foreground", "reeds", 1.25, 0.9, 10, 0, False, base="#143018", base_y=0.99, kind2="reeds", n=3)]),
    "desert": dict(hour="noon", pal=dict(top="#e9a45a", mid="#f4c880", bottom="#fbe6b0", haze="#f2cf9a", shadow="#6a3a4a", light="#fff3c0", cloud="#fff3d8"), layers=[
        _L("clouds", "clouds", 0.125, 0.0, 1, 90, False, w=2, n=2),
        _L("mountains", "mesas", 0.25, 0.1, 2, 70, True, w=2, base="#c0705a", t=0.55, base_y=0.62, amp=0.16, n_peaks=Rg(1, 2), fog=True),
        _L("dunes", "dunes_far", 0.5, 0.25, 4, 40, True, base="#e0a05a", t=0.35, base_y=0.78, amp=0.12),
        _L("dunes", "dunes_near", 0.625, 0.45, 5, 20, True, base="#d4883e", t=0.12, base_y=0.9, amp=0.10),
        _L("ground", "sand", 1.0, 0.8, 8, 5, True, base="#b86a38", base_y=0.97),
        _L("foreground", "rocks", 1.25, 0.9, 10, 0, False, base="#5a2a30", base_y=0.98, kind2="rocks", n=3)]),
    "snow": dict(hour="dawn", pal=dict(top="#5a78b8", mid="#a8b4dc", bottom="#e8d8e8", haze="#dde6f2", shadow="#40508a", light="#fff5f0", cloud="#f6eaf2"), layers=[
        _L("clouds", "clouds", 0.125, 0.0, 1, 90, False, w=2, n=3),
        _L("mountains", "mountains", 0.25, 0.1, 2, 70, True, w=2, base="#8aa0d0", t=0.50, base_y=0.62, amp=0.30, n_peaks=Rg(2, 3), snow=True, fog=True),
        _L("mountains", "ridge", 0.5, 0.25, 4, 40, True, w=2, base="#6a86b8", t=0.30, base_y=0.80, amp=0.18, n_peaks=Rg(3, 4), snow=True),
        _L("trees", "pines", 0.625, 0.45, 5, 20, True, base="#3c6a78", t=0.10, ground_y=0.90, hmin=16, hmax=30, n_clusters=4, per=5, loners=3),
        _L("ground", "snowfield", 1.0, 0.8, 8, 5, True, base="#a8bede", base_y=0.97),
        _L("foreground", "rocks", 1.25, 0.9, 10, 0, False, base="#2a3a5a", base_y=0.98, kind2="rocks", n=3)]),
    "ocean": dict(hour="dusk", pal=dict(disc_y=0.46), layers=[
        _L("clouds", "clouds", 0.125, 0.0, 1, 90, False, w=2, n=4),
        _L("hills", "island", 0.25, 0.1, 2, 70, True, w=2, base="#6a5a98", t=0.55, base_y=0.58, amp=0.07, harmonics=(1, 3)),
        _L("waves", "sea_far", 0.5, 0.25, 4, 40, True, base="#4a5aa0", t=0.30, top_y=0.58),
        _L("waves", "sea_near", 0.625, 0.45, 5, 20, True, base="#26407a", t=0.05, top_y=0.80),
        _L("foreground", "rocks", 1.25, 0.9, 10, 0, False, base="#101c28", base_y=0.98, kind2="rocks", n=3)]),
    "cave": dict(hour="night", pal=dict(top="#07070f", bottom="#16122c", haze="#2a2450", shadow="#05050c", light="#9aa8ff", stars=0.0, disc=None, glow=None), layers=[
        _L("ceiling", "ceiling_far", 0.25, 0.1, 2, 70, True, w=2, base="#3a3470", t=0.45, reach=30, n=10),
        _L("mountains", "rock_wall", 0.375, 0.15, 4, 55, True, w=2, base="#34306a", t=0.40, base_y=0.84, amp=0.28, n_peaks=Rg(3, 4)),
        _L("ceiling", "ceiling_near", 0.5, 0.25, 5, 40, True, w=2, base="#2a2858", t=0.15, reach=44, n=14, crystals=True),
        _L("ground", "floor", 1.0, 0.8, 8, 5, True, base="#1c1a3a", base_y=0.96),
        _L("foreground", "rocks", 1.25, 0.9, 10, 0, False, base="#07070f", base_y=0.98, kind2="rocks", n=4)]),
    "space": dict(hour="night", pal=dict(top="#04040c", bottom="#1d1140", haze="#3a2c70", shadow="#04040c", light="#c8d0ff", stars=1.0, disc=None, glow=None), layers=[
        _L("nebula", "nebula", 0.125, 0.05, 1, 90, False, w=2, base="#5a2c8a", n=4),
        _L("planet", "planet", 0.25, 0.1, 2, 70, False, base="#c06a4a"),
        _L("stars", "stars_near", 0.5, 0.25, 4, 40, False, count=1.0),
        _L("ground", "asteroid", 1.0, 0.8, 8, 5, True, base="#3a3050", base_y=0.97)]),
    "ruins": dict(hour="dusk", layers=[
        _L("clouds", "clouds", 0.125, 0.0, 1, 90, False, w=2, n=3),
        _L("mountains", "mountains", 0.25, 0.1, 2, 70, True, w=2, base="#7a6aa8", t=0.55, base_y=0.66, amp=0.22, n_peaks=Rg(2, 3), fog=True),
        _L("skyline", "walls_far", 0.5, 0.25, 4, 40, True, base="#5a5090", t=0.35, base_y=0.90, hmin=30, hmax=70, detail=0.0, ruins=True),
        _L("skyline", "walls_near", 0.625, 0.45, 5, 20, True, base="#3a3868", t=0.12, base_y=0.94, hmin=30, hmax=80, detail=1.0, ruins=True),
        _L("ground", "grass", 1.0, 0.8, 8, 5, True, base="#1c2a3a", base_y=0.97),
        _L("foreground", "rocks", 1.25, 0.9, 10, 0, False, base="#101420", base_y=0.98, kind2="rocks", n=4)]),
}


def _frame_every(total_w):
    """frames of an animation advance every fe preview frames; the 4-frame cycle (4 x fe) must divide the loop"""
    return next(f for f in (20, 16, 12, 10, 8, 5, 4, 2, 1) if total_w % (4 * f) == 0)


# pace: the camera speed the stack is made for. "walk" = 120 px/s (the ground moves 2 px per frame, far layers 1 px every 2, 4 or 8 frames: steady and whole-pixel), "run" = 480 px/s (8 px per frame).
# The preset's speeds are written for "run"; for "walk" each one maps to the next slower whole-pixel speed and the scroll factor follows (scroll = px per frame / camera px per frame).
PACES = {"walk": (120, {1: 0.125, 2: 0.25, 4: 0.5, 5: 1, 8: 2, 10: 4}), "run": (480, None)}


def draw(preset, out_dir, seed=1, size=(320, 180), headroom=24, force=False, hour=None, anim=True, pace="walk"):
    W, vh = size
    if W % 40 or W < 160:
        raise SpecError("draw: width must be a multiple of 40 and at least 160 (so the speeds 1 2 4 5 8 10 divide it)")
    if vh < 64:
        raise SpecError("draw: height must be at least 64")
    if os.path.isdir(out_dir) and os.listdir(out_dir) and not force:
        raise SpecError(f"{out_dir} is not empty: pick a new folder or pass --force")
    if hour is not None and hour not in LY.HOURS:
        raise SpecError("hour must be one of " + ", ".join(LY.HOURS))
    PR = PRESETS[preset]; Pal = dict(LY.HOURS[hour or PR["hour"]]); Pal.update(PR.get("pal", {})); H = vh + headroom; os.makedirs(out_dir, exist_ok=True)
    if pace not in PACES:
        raise SpecError("pace must be walk or run")
    cam, pmap = PACES[pace]
    spec = {"name": preset, "viewport": [W, vh], "fps": 60, "camera_px_per_s": cam, "background": "#%02x%02x%02x" % LY.hexc(Pal["top"]), "layers": []}
    rv = np.random.default_rng(seed * 7919 + 3)

    def save(imgs, name, fe=None, **kw):
        imgs = imgs if isinstance(imgs, list) else [imgs]
        for i, im in enumerate(imgs):
            Image.fromarray(im).save(os.path.join(out_dir, name + ("" if i == 0 else f"_{i}") + ".png"))
        d = dict(file=name + ".png", repeat="x", **kw)
        if len(imgs) > 1 and anim:
            d["frames"] = [f"{name}_{i}.png" for i in range(1, len(imgs))]; d["frame_every"] = fe
        spec["layers"].append(d)

    nf = 4 if anim else 1; fe = _frame_every(W)
    save(LY.sky(W, H, Pal), "sky", scroll=[0, 0], px_per_frame=0, depth=100, depth_check=False)
    if Pal.get("disc") and rv.random() < PR.get("disc_p", 1.0):
        save(LY.disc(W, H, Pal, np.random.default_rng(seed * 1000 + 3), headroom, vh), Pal["disc"], scroll=[0, 0], px_per_frame=0, depth=99, depth_check=False)
    if Pal["stars"] > 0 and preset != "space":
        save(LY.stars(W, H, Pal, np.random.default_rng(seed * 1000 + 2), headroom, headroom + int(vh * .55), nf), "stars", fe, scroll=[0, 0], px_per_frame=0, depth=95, depth_check=False)
    for k, Ld in enumerate(PR["layers"]):
        r = np.random.default_rng(seed * 1000 + 10 + k); kind = Ld["kind"]; Wl = W * Ld["w"]; prm = {q: (int(rv.integers(v[0], v[1] + 1)) if isinstance(v, Rg) else v) for q, v in Ld["p"].items()}
        if isinstance(prm.get("snow"), float) and not isinstance(prm["snow"], bool):
            prm["snow"] = bool(rv.random() < prm["snow"])
        fy = lambda key: int(H * prm[key])
        if kind == "clouds":
            img = LY.clouds(Wl, H, Pal, r, headroom + int(vh * .05), headroom + int(vh * .24), n=prm.get("n", 4) * Ld["w"])
        elif kind == "mountains":
            img = LY.mountains(Wl, H, Pal, r, prm["base"], prm["t"], fy("base_y"), fy("amp"), n_peaks=prm.get("n_peaks", 3) * Ld["w"], snow=bool(prm.get("snow")), fog=bool(prm.get("fog")))
        elif kind == "hills":
            img = LY.hills(Wl, H, Pal, r, prm["base"], prm["t"], fy("base_y"), fy("amp"), harmonics=prm.get("harmonics", (1, 2, 3, 5)))
        elif kind == "dunes":
            img = LY.dunes(Wl, H, Pal, r, prm["base"], prm["t"], fy("base_y"), fy("amp"))
        elif kind == "waves":
            img = LY.waves(Wl, H, Pal, r, prm["base"], prm["t"], fy("top_y"), frames=nf)
        elif kind == "trees":
            img = LY.trees(Wl, H, Pal, r, prm["base"], prm["t"], fy("ground_y"), prm.get("hmin", 16), prm.get("hmax", 30), prm.get("n_clusters", 4), prm.get("per", 6), prm.get("loners", 4), prm.get("broadleaf", 0.0))
        elif kind == "skyline":
            img = LY.skyline(Wl, H, Pal, r, prm["base"], prm["t"], fy("base_y"), prm["hmin"], prm["hmax"], prm.get("detail", 1.0), prm.get("lit", 0.18), prm.get("ruins", False))
        elif kind == "ground":
            img = LY.ground(Wl, H, Pal, r, prm["base"], fy("base_y"))
        elif kind == "foreground":
            img = LY.foreground(Wl, H, Pal, r, prm["base"], fy("base_y"), prm.get("kind2", "rocks"), prm.get("n", 4))
        elif kind == "ceiling":
            img = LY.ceiling(Wl, H, Pal, r, prm["base"], prm["t"], prm.get("reach", 34), prm.get("n", 12) * Ld["w"], bool(prm.get("crystals")), headroom)
        elif kind == "planet":
            img = LY.planet(Wl, H, Pal, r, prm["base"])
        elif kind == "nebula":
            img = LY.nebula(Wl, H, Pal, r, prm["base"], prm.get("n", 4) * Ld["w"])
        elif kind == "stars":
            img = LY.stars(Wl, H, dict(Pal, stars=1.0), r, headroom, headroom + int(vh * .7), nf)
        else:
            raise SpecError("unknown layer kind " + kind)
        pf = pmap[Ld["pf"]] if pmap and Ld["pf"] else Ld["pf"]; sx = round(pf / (cam / 60), 4) if pmap else Ld["sx"]
        save(img, Ld["name"], _frame_every(Wl), scroll=[sx, Ld["sy"]], px_per_frame=pf, depth=Ld["depth"], depth_check=Ld["dc"])
    pth = os.path.join(out_dir, "stack.json"); json.dump(spec, open(pth, "w"), indent=1)
    return pth


# ---------------------------------------------------------------- selftest
def selftest():
    import tempfile
    t = tempfile.mkdtemp(); rng = np.random.default_rng(3); W, H = 128, 48
    # seam metric: a wrapping hill layer passes, a cut one flags, flat and transparent layers run
    x = np.arange(W); prof = (30 - 8 * np.sin(2 * math.pi * 2 * x / W) - 4 * np.sin(2 * math.pi * 5 * x / W + 1)).astype(int)
    def hill(p):
        a = np.zeros((H, W, 4), np.uint8); yy = np.arange(H)[:, None]; a[...] = (40, 60, 120, 255); a[yy >= p[None, :]] = (20, 90, 50, 255); return a
    ok = hill(prof); cut = hill(np.concatenate([prof[:W // 2] - 0, prof[W // 2:] + 12]).clip(0, H - 1)); cut = np.roll(cut, 0, 1)
    assert not seam_stats(ok, 1)["visible"], seam_stats(ok, 1)
    shifted = hill(np.concatenate([np.linspace(8, 36, W // 2).astype(int), np.linspace(36, 8, W // 2).astype(int)])); shifted[:, -W // 2:] = np.roll(shifted, 7, 0)[:, -W // 2:]
    broken = hill(np.linspace(10, 40, W).astype(int)); assert seam_stats(broken, 1)["visible"]
    flat = np.full((H, W, 4), 200, np.uint8); assert not seam_stats(flat, 1)["visible"]
    tr = np.zeros((H, W, 4), np.uint8); tr[30:, 10:40] = (9, 99, 9, 255); assert seam_stats(tr, 1)["seam"] == 0
    # speeds
    assert speed_info(96, 4) == (24, None) and speed_info(96, 5)[0] is None and "4, 6" in speed_info(96, 5)[1].replace("valid nearby: ", "")
    assert speed_info(320, 0.5)[0] == 640 and speed_info(320, 0)[0] is None
    assert divisors(96) == [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48]
    # draw: a preset writes layers and a spec that passes check with no flags; same seed, same bytes
    d1, d2 = os.path.join(t, "a"), os.path.join(t, "b")
    for pr in PRESETS:
        s1 = draw(pr, os.path.join(d1, pr), seed=7); rep = check(load_spec(s1)); assert not rep["flags"], (pr, rep["flags"])
        assert rep["loop_frames"] and rep["loop_frames"] % 320 == 0, rep["loop_frames"]
    draw("dusk_hills", d2, seed=7); draw("forest", os.path.join(t, "c"), seed=7)
    assert open(os.path.join(d1, "dusk_hills", "hills.png"), "rb").read() == open(os.path.join(d2, "hills.png"), "rb").read()
    d3 = os.path.join(t, "d"); draw("dusk_hills", d3, seed=8)
    assert open(os.path.join(d3, "hills.png"), "rb").read() != open(os.path.join(d2, "hills.png"), "rb").read()
    # a hand-broken stack gets the expected flags
    sp = load_spec(os.path.join(d2, "stack.json")); sp["layers"][3]["px_per_frame"] = 3; rep = check(sp)
    assert any("does not divide" in f for f in rep["flags"]), rep["flags"]
    sp = load_spec(os.path.join(d2, "stack.json")); sp["layers"][2], sp["layers"][3] = sp["layers"][3], sp["layers"][2]; assert any("scroll factors" in f for f in check(sp)["flags"])
    sp = load_spec(os.path.join(d2, "stack.json")); sp["viewport"] = [400, 180]; assert any("narrower than the viewport" in n for q in check(sp)["layers"] for n in q["notes"])
    sp = load_spec(os.path.join(d2, "stack.json")); sp["camera_px_per_s"] = 100; assert any("not whole pixels" in f for f in check(sp)["flags"])
    sp = load_spec(os.path.join(d2, "stack.json")); lo = next(L for L in sp["layers"] if L["file"] == "mountains.png"); a = _rgba(lo["path"]); a[a[..., 3] > 0, :3] = (90, 0, 0)      # the far layer made vivid and dark
    Image.fromarray(a).save(lo["path"]); assert any("depth palette" in f for f in check(sp)["flags"])
    # spec errors name the nearest key
    bad = os.path.join(t, "bad.json"); json.dump({"layers": [{"file": "x.png", "scrol": 1}]}, open(bad, "w"))
    try:
        load_spec(bad); assert False
    except SpecError as e:
        assert "scroll" in str(e)
    # preview: loop closes (frame 0 == frame LCM), identical bytes, the jitter demo steps unevenly
    sp = load_spec(os.path.join(d2, "stack.json")); layers = load_layers(sp); lf = check(sp)["loop_frames"]
    f0 = frame_at(sp, layers, [positions(sp, L, 0, False) for L, _ in layers], 0.0, 0); fN = frame_at(sp, layers, [positions(sp, L, lf, False) for L, _ in layers], 0.0, lf); assert (f0 == fN).all()      # animation frames included
    f1 = frame_at(sp, layers, [positions(sp, L, 1, False) for L, _ in layers], 0.0, 1); assert not (f0 == f1).all()
    g = os.path.join(t, "p.gif"); r = preview(sp, g, frames=8, scale=2, pingpong=False); r2 = preview(sp, os.path.join(t, "p2.gif"), frames=8, scale=2, pingpong=False)
    assert open(g, "rb").read() == open(os.path.join(t, "p2.gif"), "rb").read() and not r["loop_closes"]
    sp["camera_px_per_s"] = 100; assert [positions(sp, {"scroll": [0.3, 0]}, i, True) for i in range(6)] == [0, 1, 1, 2, 2, 3]   # 0.5 px/frame: 0,1,1,2,2,3 (rounded) per layer
    # y parallax: the view moves when the camera bobs and the layer has headroom
    sp = load_spec(os.path.join(d2, "stack.json")); layers = [(L, _rgba(L["path"])) for L in sp["layers"]]
    a0 = frame_at(sp, layers, [0] * len(layers), 0.0); a1 = frame_at(sp, layers, [0] * len(layers), 20.0); assert not (a0 == a1).all()
    # godot export: header, every ExtResource defined once and used, node count, centered = false, headroom offset
    tscn = export_godot(sp, os.path.join(t, "g"), "res://bg/x", "camera"); txt = open(tscn).read()
    ids = [l.split('id="')[1].split('"')[0] for l in txt.splitlines() if l.startswith("[ext_resource")]
    assert txt.startswith("[gd_scene load_steps=") and len(ids) == len(set(ids)) == sum(1 + len(L.get("frame_paths", [])) for L in sp["layers"]) and all(f'ExtResource("{i}")' in txt for i in ids)
    assert txt.count("type=\"Parallax2D\"") == len(sp["layers"]) == txt.count("centered = false") and "position = Vector2(0, -24)" in txt and ("scroll_scale = Vector2(%g, %g)" % tuple(next(L for L in sp["layers"] if L["file"] == "hills.png")["scroll"])) in txt
    assert "autoscroll" in open(export_godot(sp, os.path.join(t, "g2"), None, "loop")).read()
    # min_zoom: x is covered by repeat_times, y gets a flag; export writes the right repeat_times
    sp = load_spec(os.path.join(d2, "stack.json")); sp["min_zoom"] = 0.5; assert any("zoomed out to 0.5" in f for f in check(sp)["flags"])
    assert "repeat_times = 3" in open(export_godot(sp, os.path.join(t, "g3"), None, "camera", 0.5)).read() and "repeat_times" not in open(export_godot(sp, os.path.join(t, "g4"), None, "camera")).read()
    h = preview_html(sp, os.path.join(t, "p.html")); txt = open(h, encoding="utf-8").read(); assert txt.count("data:image/png;base64,") == sum(1 + len(L.get("frame_paths", [])) for L in sp["layers"]) and "__" not in txt.replace("__proto__", "")
    # heal: the palette stays, a cut silhouette gets continuous; mincut narrows the layer by the band
    cutl = np.roll(_rgba(os.path.join(d2, "hills.png")), -50, 1)[:, :300]; assert seam_stats(cutl, 1)["visible"]
    hp = heal_profile(cutl, 24); assert not seam_stats(hp, 1)["visible"] and _colours(hp) <= _colours(cutl) | {(0, 0, 0, 0)}, seam_stats(hp, 1)
    hm = heal_mincut(cutl, 16); assert hm.shape[1] == 300 - 16 and _colours(hm) <= _colours(cutl)
    try:
        heal_profile(np.full((20, 40, 4), 255, np.uint8)); assert False
    except SpecError:
        pass
    # other engines: LDtk uses 1 - scroll, Tiled keeps scroll, every snippet names its layers
    spx = load_spec(os.path.join(d2, "stack.json")); lt = export_text(spx, "ldtk"); assert '"parallaxFactorX": 0.5' in lt and '"parallaxFactorX": 1.0' in lt, lt
    td = json.loads(export_text(spx, "tiled")); assert [l["parallaxx"] for l in td["layers"]] == [l["scroll"][0] for l in spx["layers"]] and td["layers"][0]["type"] == "imagelayer"
    assert "-1px" in export_text(spx, "css") and "base: 24" in export_text(spx, "phaser")      # unitless calc() in translateX was a real bug: the animation silently did nothing
    assert "tilePositionX" in export_text(spx, "phaser") and "prefers-reduced-motion" in export_text(spx, "css") and json.loads(export_text(spx, "json"))["name"] == spx["name"]
    # seam view
    v = seam_view(os.path.join(d2, "hills.png"), os.path.join(t, "v.png")); assert Image.open(v["view"]).size == (640, 408)
    # bad specs exit 2 with one line, never a traceback (found by an independent review)
    import io, contextlib
    okpng = os.path.join(t, "ok.png"); Image.fromarray(np.full((32, 64, 4), 255, np.uint8)).save(okpng)
    for k, body in enumerate(({"layers": [{"file": "ok.png", "px_per_frame": [4]}]}, {"layers": [{"file": "ok.png", "scroll": [1]}]}, {"layers": [{"file": 5}]}, {"fps": 0, "layers": [{"file": "ok.png"}]},
                              {"layers": ["ok.png"]}, {"layers": [{"file": "ok.png", "px_per_frame": float("nan")}]}, {"min_zoom": 0, "layers": [{"file": "ok.png"}]}, {"viewport": [0, 10], "layers": [{"file": "ok.png"}]},
                              {"background": "red", "layers": [{"file": "ok.png"}]}, {"layers": [{"file": "ok.png"}, {"file": "ok.png"}]})):
        bp = os.path.join(t, f"bad{k}.json"); json.dump(body, open(bp, "w"))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert main(["check", bp]) == 2 and err.getvalue().count(chr(10)) == 1, (k, err.getvalue())
    # sub-pixel speeds must be 1/k; a loop that does not close is not reported as closed
    assert speed_info(64, 0.3)[0] is None and "not 1/k" in speed_info(64, 0.3)[1] and speed_info(64, 0.25)[0] == 256 and speed_info(64, -4) == (16, None)
    gr = np.zeros((32, 64, 4), np.uint8); gr[..., 3] = 255; gr[..., 0] = (np.arange(64) * 4)[None, :]; grp = os.path.join(t, "gr.png"); Image.fromarray(gr).save(grp)
    sp1 = {"viewport": [64, 32], "fps": 60, "background": "#000000", "name": "t", "layers": [{"file": "gr.png", "path": grp, "scroll": [1, 1], "px_per_frame": 5, "depth": 0, "repeat": "x", "depth_check": True, "scroll_y_set": False}]}
    assert preview(sp1, os.path.join(t, "n.gif"), frames=4, scale=1, pingpong=False)["loop_closes"] is False         # 64 is not a multiple of 5: no loop
    # Godot names are safe and every sprite is nearest-filtered
    spn = load_spec(os.path.join(d2, "stack.json")); spn["name"] = 'a/b"c.d'; tn = export_godot(spn, os.path.join(t, "g5"), None, "camera"); tx = open(tn).read()
    assert os.path.basename(tn) == "a_b_c_d.tscn" and 'name="a_b_c_d"' in tx and tx.count("texture_filter = 1") == len(spn["layers"])
    # draw refuses a folder that already holds files, heal refuses an empty end column and a bad band
    try:
        draw("forest", d2); assert False
    except SpecError:
        pass
    try:
        heal_profile(np.concatenate([np.zeros((20, 8, 4), np.uint8), np.full((20, 40, 4), 255, np.uint8)], 1)); assert False
    except SpecError:
        pass
    try:
        heal(os.path.join(d2, "hills.png"), os.path.join(t, "bb.png"), "mincut", 0); assert False
    except SpecError:
        pass
    # a non-repeating layer moves in the preview and a short one is bottom aligned
    sh = np.zeros((10, 40, 4), np.uint8); sh[..., :] = (255, 0, 0, 255); spx2 = dict(sp1, background="#000000"); Lx = dict(sp1["layers"][0], repeat="none")
    f_a = frame_at(spx2, [(Lx, sh)], [0]); f_b = frame_at(spx2, [(Lx, sh)], [10]); assert f_a[-1, 5, 0] == 255 and f_a[0, 5, 0] == 0 and f_b[-1, 35, 0] == 0 and f_b[-1, 25, 0] == 255
    # all nine presets: the layers wrap (no seam flag), animation cycles divide the loop, review finds nothing to flag; time of day and --static work
    spd = load_spec(draw("dusk_hills", os.path.join(t, "spd"), seed=7)); assert any(L["frame_paths"] for L in spd["layers"]) and not check(spd)["flags"]
    rvw = review(spd, os.path.join(t, "rv.png")); assert not rvw["flags"] and os.path.getsize(rvw["sheet"]) > 2000
    chk = np.zeros((8, 8, 4), np.uint8); chk[..., 3] = 255; chk[::2, ::2, :3] = 255; chk[1::2, 1::2, :3] = 255; assert layer_metrics(chk)["dither"] > 0.9
    for pr in PRESETS:
        sx = load_spec(draw(pr, os.path.join(t, "all_" + pr), seed=11)); rx = check(sx); assert not rx["flags"], (pr, rx["flags"])
        assert not review(sx, os.path.join(t, pr + ".png"))["flags"], pr
    sn = load_spec(draw("night_city", os.path.join(t, "hr"), seed=7, hour="dawn")); assert open(os.path.join(t, "hr", "sky.png"), "rb").read() != open(os.path.join(t, "all_night_city", "sky.png"), "rb").read()
    assert not any(L["frame_paths"] for L in load_spec(draw("forest", os.path.join(t, "st"), seed=7, anim=False))["layers"])
    try:
        draw("forest", os.path.join(t, "badhour"), hour="midnight"); assert False
    except SpecError:
        pass
    tsa = open(export_godot(spd, os.path.join(t, "ga"), "res://bg/a", "camera")).read(); assert "AnimatedSprite2D" in tsa and 'SubResource("SpriteFrames_' in tsa and '"speed": 3' in tsa and "[sub_resource" in tsa
    pp = preview(sp1, os.path.join(t, "pp.gif"), frames=20, scale=1, pingpong=True, every=1); assert pp["loop_closes"] and pp["pingpong"] and pp["frames"] == 20
    spd2 = load_spec(draw("dusk_hills", os.path.join(t, "ppd"), seed=7)); ppd = preview(spd2, os.path.join(t, "ppd.gif"), scale=1, every=1); assert ppd["pingpong"] and ppd["loop_closes"] and ppd["frames"] % 160 == 0, ppd["frames"]
    print("pix_parallax selftest ok")


def main(argv):
    if argv == ["selftest"]:
        selftest(); return 0
    ap = argparse.ArgumentParser(prog="pix_parallax.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check"); c.add_argument("spec"); c.add_argument("--json", action="store_true"); c.add_argument("--strict", action="store_true")
    p = sub.add_parser("preview"); p.add_argument("spec"); p.add_argument("out"); p.add_argument("--frames", type=int); p.add_argument("--scale", type=int, default=3); p.add_argument("--subpixel", action="store_true"); p.add_argument("--bob", type=float, default=0); p.add_argument("--camera", type=float, help="camera speed in px/s: preview as a live camera at that speed (try 60 to 120 for walking)"); p.add_argument("--pingpong", dest="pingpong", action="store_true", default=None, help="camera goes right and back (default when the true loop does not fit in the GIF)"); p.add_argument("--every", type=int, help="engine frames per GIF frame (default 3 at 60 fps = 50 ms, plays at 1.0x real time)"); p.add_argument("--no-pingpong", dest="pingpong", action="store_false", help="a plain excerpt of the loop (it jumps at the end unless the whole loop is shown)")
    e = sub.add_parser("export"); e.add_argument("spec"); e.add_argument("--godot", metavar="DIR"); e.add_argument("--format", choices=("json", "tiled", "ldtk", "phaser", "css")); e.add_argument("--out", metavar="FILE"); e.add_argument("--res-dir"); e.add_argument("--mode", choices=("loop", "camera"), default="loop"); e.add_argument("--min-zoom", type=float, help="smallest camera zoom (0.5 = sees twice as much): sets repeat_times")
    s = sub.add_parser("seam"); s.add_argument("layer"); s.add_argument("--view", metavar="OUT"); s.add_argument("--y", action="store_true"); s.add_argument("--heal", choices=("mincut", "profile")); s.add_argument("--band", type=int); s.add_argument("--out", metavar="OUT")
    v = sub.add_parser("review"); v.add_argument("spec"); v.add_argument("out"); v.add_argument("--ref", metavar="IMAGE", help="a picture to show beside the stack, for comparison only")
    d = sub.add_parser("draw"); d.add_argument("--preset", required=True, choices=sorted(PRESETS)); d.add_argument("--out", required=True); d.add_argument("--seed", type=int, default=1); d.add_argument("--size", default="320x180"); d.add_argument("--force", action="store_true", help="write into a folder that already has files"); d.add_argument("--hour", choices=sorted(LY.HOURS), help="time of day (default: the preset's)"); d.add_argument("--static", action="store_true", help="no animated layers (twinkling stars, moving waves)"); d.add_argument("--pace", choices=("walk", "run"), default="walk", help="camera speed: walk 120 px/s (default) or run 480 px/s")
    try:
        a = ap.parse_args(argv)
    except SystemExit as ex:
        return 0 if ex.code == 0 else 2
    if not a.cmd:
        print(__doc__); return 2
    try:
        if a.cmd == "check":
            r = check(load_spec(a.spec))
            if a.json:
                print(json.dumps(r, indent=1))
            else:
                for L in r["layers"]:
                    sx = L.get("seam_x"); ds = L["depth_stats"] or {}
                    print(f"{L['file']:<16}{L['size'][0]}x{L['size'][1]}  scroll {L['scroll'][0]:g},{L['scroll'][1]:g}  px/frame {L['px_per_frame']:g}  "
                          + (f"seam_x rank {sx['seam_rank'] if sx['seam_rank'] is not None else 'n/a'} excess {sx['seam_excess']}  " if sx else "") + (f"sat {ds.get('sat')} contrast {ds.get('contrast')}" if ds else "") + "".join("  [" + n + "]" for n in L["notes"]))
                print(f"loop: {r['loop_frames']} frames" + (f" ({r['loop_seconds']} s at {load_spec(a.spec)['fps']} fps)" if r["loop_frames"] else ""))
                print("FLAGS:", "; ".join(r["flags"]) if r["flags"] else "none")
            return 1 if (a.strict and r["flags"]) else 0
        if a.cmd == "preview":
            if a.out.lower().endswith(".html"):
                if a.frames or a.subpixel or a.bob or a.scale != 3:
                    print("note: --frames, --scale, --subpixel and --bob belong to the GIF; the HTML page has its own controls", file=sys.stderr)
                print(preview_html(load_spec(a.spec), a.out), "- open in a browser (self-contained)"); return 0
            r = preview(load_spec(a.spec), a.out, a.frames, a.scale, a.subpixel, a.bob, a.camera, a.pingpong, a.every)
            print(f"{r['gif']}  {r['frames']} frames {r['size'][0]}x{r['size'][1]}  {r['ms_per_frame']} ms/frame ({r['every']} engine frames each, plays at {r['real_time_factor']}x real time)  loop closes: {'yes' if r['loop_closes'] else 'no'}" + (f"  (ping-pong: the camera goes right and back; the true loop is {r['true_loop_frames']} frames)" if r["pingpong"] else ""))
            for k, v in r["first_12_positions"].items():
                print(f"  {k}: x positions of the first 12 frames {v}")
            return 0
        if a.cmd == "export":
            sp = load_spec(a.spec)
            if a.format and a.godot:
                raise SpecError("use either --godot DIR or --format NAME, not both")
            if a.format:
                txt = export_text(sp, a.format)
                if a.out:
                    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True); open(a.out, "w", encoding="utf-8").write(txt + "\n"); print(a.out)
                else:
                    print(txt)
                return 0
            if not a.godot:
                raise SpecError("export needs --godot DIR or --format NAME")
            t = export_godot(sp, a.godot, a.res_dir, a.mode, a.min_zoom or sp.get("min_zoom"))
            print(t, "- open in Godot 4.3+ (Parallax2D was experimental in 4.3); put the folder at", (a.res_dir or f"res://bg/{sp['name']}"), "(tested on Godot 4.7.2; zoomed out, x is covered by repeat_times but y is not: run check with min_zoom set)")
            return 0
        if a.cmd == "seam":
            if a.heal:
                if not a.out:
                    raise SpecError("--heal needs --out (it never edits a layer in place)")
                h = heal(a.layer, a.out, a.heal, a.band)
                print(h["out"], f"- {a.heal} band {h['band']}: seam visible {h['before']['visible']} -> {h['after']['visible']}, size {h['size_before']} -> {h['size_after']}, new colours {h['new_colours']}")
                print("  before:", h["before"]); print("  after: ", h["after"])
                print("  look at it (`seam OUT --view v.png`): a heal can move a discontinuity instead of removing it" + ("; the layer is narrower now: re-check that px_per_frame divides the new width" if h["size_after"] != h["size_before"] else ""))
                return 0
            if not a.view:
                raise SpecError("seam needs --view OUT or --heal NAME --out OUT")
            r = seam_view(a.layer, a.view, a.y); print(r["view"], f"- {r['axis']} wrap rolled by half, red line = the join; judge it by eye")
            for ax, nm in ((1, "x"),) + (((0, "y"),) if a.y else ()):
                print(f"  seam_{nm}:", seam_stats(_rgba(a.layer), ax))
            return 0
        if a.cmd == "review":
            rv = review(load_spec(a.spec), a.out, a.ref); print(rv["sheet"])
            for m in rv["layers"]:
                print(f"  {m['file']:<18} colours {m['colours']:>3}  dither {m['dither'] * 100:4.1f}%  mean run {m['run']:>6}  cover {m['cover']}")
            print("REVIEW FLAGS:", "; ".join(rv["flags"]) if rv["flags"] else "none"); return 0
        if a.cmd == "draw":
            w, h = (int(v) for v in a.size.lower().split("x")); sp = draw(a.preset, a.out, a.seed, (w, h), force=a.force, hour=a.hour, anim=not a.static, pace=a.pace); print(sp, "- run: check --strict, then preview"); return 0
    except (SpecError, OSError, ValueError, TypeError, KeyError, IndexError, ZeroDivisionError) as ex:
        print(f"pix_parallax: {type(ex).__name__ if not isinstance(ex, SpecError) else 'error'}: {ex}", file=sys.stderr); return 2
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
