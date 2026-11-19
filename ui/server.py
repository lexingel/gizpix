# SPDX-License-Identifier: AGPL-3.0-or-later
"""gizpix ui - a local web interface for Gizpix. Standard library + the packages Gizpix already needs; no network beyond localhost.

  python gizpix.py ui [--port 8765] [--no-open] [--out-root DIR]
  python ui/server.py selftest

Starts a small server on 127.0.0.1 only and opens the browser. The page drives the same command-line tools (each result shows the exact command it ran).
Safety: only the job templates below run (no free-form commands, no shell); every run writes into a temporary staging folder, and a result reaches the output root only when you press Save,
as a NEW folder (never over your files or an earlier result);
requests need a per-run token and a localhost Host header. Stop it with Ctrl+C."""
import argparse, base64, io, json, os, re, secrets, shutil, subprocess, sys, tempfile, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); WEB = os.path.join(HERE, "web")
GIZPIX = os.path.join(ROOT, "gizpix.py")
sys.path.insert(0, ROOT)
STATE = {"token": secrets.token_urlsafe(18), "out_root": os.path.join(os.getcwd(), "gizpix_out"), "stage": tempfile.mkdtemp(prefix="gizpix_stage_"), "made": set(), "port": 0, "uploads": {}, "runs": {}}


def natkey(s): return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]
def shown(args): return "python gizpix.py " + " ".join(a if re.fullmatch(r"[\w./:\\=,+-]+", a) else '"' + a.replace('"', '\\"') + '"' for a in args)
def clean_path(p): return os.path.abspath(os.path.expanduser(str(p).strip().strip('"')))
def rel(p):
    try: return os.path.relpath(p, os.getcwd()) if os.path.commonpath([p, os.getcwd()]) == os.getcwd() else p
    except ValueError: return p
class Bad(Exception): pass


def pngs(path):
    """a PNG file, or the PNGs of a folder in natural order"""
    p = clean_path(path)
    if os.path.isfile(p): return [p] if p.lower().endswith(".png") else (_ for _ in ()).throw(Bad(f"not a PNG file: {p}"))
    if not os.path.isdir(p): raise Bad(f"no such file or folder: {p}")
    fs = sorted((os.path.join(p, f) for f in os.listdir(p) if f.lower().endswith(".png")), key=lambda f: natkey(os.path.basename(f)))
    if not fs: raise Bad(f"no PNG files in {p}")
    return fs


def prune_stage(new, name, keep=8):
    """staging folders of one kind (run_x, bg_seam, ...) pile up within a session: keep the newest `keep`, delete older ones. Only folders this server made inside its own staging folder are touched."""
    if os.path.dirname(new) != STATE["stage"]: return
    kind = [d for d in STATE["made"] if os.path.dirname(d) == STATE["stage"] and re.sub(r"_\d+$", "", os.path.basename(d)) == name and os.path.isdir(d)]
    for d in sorted(kind, key=os.path.getmtime, reverse=True)[keep:]:
        shutil.rmtree(d, ignore_errors=True); STATE["made"].discard(d)


def new_dir(root, name):
    """a fresh folder that did not exist before: results never land in or over anything already there"""
    root = clean_path(root or STATE["out_root"]); os.makedirs(root, exist_ok=True); name = re.sub(r"[^\w.-]+", "_", name or "result").strip("._") or "result"
    if name.lower() in RESERVED: name = "_" + name
    for i in range(1, 1000):
        d = os.path.join(root, name if i == 1 else f"{name}_{i}")
        try: os.mkdir(d); STATE["made"].add(d); prune_stage(d, name); return d
        except FileExistsError: continue
    raise Bad("could not make an output folder")


LOCAL = threading.local()                       # the run (progress and Stop) the current request belongs to
STOPPED = "Stopped. Nothing from this run was saved; your files are untouched."


def kill_tree(p):
    try:
        if sys.platform.startswith("win"): subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        else:
            import signal
            os.killpg(p.pid, signal.SIGKILL)
    except Exception:
        try: p.kill()
        except Exception: pass


def run_tool(args, timeout=900, cwd=None):
    run = getattr(LOCAL, "run", None)
    if run and run["stopped"]: raise Bad(STOPPED)
    kw = {} if sys.platform.startswith("win") else {"start_new_session": True}
    p = subprocess.Popen([sys.executable, GIZPIX, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd or os.getcwd(), **kw)
    if run: run["procs"].add(p); run["cmd"] = shown(args); run["step"] += 1
    try: out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(p); p.communicate(); raise
    finally:
        if run: run["procs"].discard(p)
    if run and run["stopped"]: raise Bad(STOPPED)
    return {"command": shown(args), "code": p.returncode, "out": (out or "").strip(), "err": (err or "").strip()}


def stop_run(rid):
    run = STATE["runs"].get(rid)
    if not run: return {"stopped": False}
    run["stopped"] = True
    for p in list(run["procs"]): kill_tree(p)
    return {"stopped": True}


def progress(rid):
    run = STATE["runs"].get(rid)
    return {"running": bool(run), "elapsed": round(time.time() - run["start"], 1) if run else 0, "cmd": run["cmd"] if run else "", "step": run["step"] if run else 0, "stopped": bool(run and run["stopped"])}


def lint(files):
    r = run_tool(["pixel_lint", *files, "--json"])
    try: return json.loads(r["out"])
    except ValueError: raise Bad("pixel_lint gave no result: " + (r["err"] or r["out"])[:200])


def fileinfo(p):
    from PIL import Image
    im = Image.open(p).convert("RGBA"); a = im.getchannel("A"); return {"path": p, "name": os.path.basename(p), "w": im.width, "h": im.height, "opaque": sum(1 for v in a.getdata() if v)}


# ---- jobs --------------------------------------------------------------------------------------------------------------------------------------------------------------
def counts(path):
    """what the clean-up targets, counted on the image itself: pixels whose exact colour appears at most twice (odd-colour specks), and transparent pixels with four opaque neighbours (pinholes)"""
    import numpy as np
    from PIL import Image
    a = np.array(Image.open(path).convert("RGBA")); op = a[..., 3] > 0; cols = a[..., :3].reshape(-1, 3).astype(np.int64); key = cols[:, 0] * 65536 + cols[:, 1] * 256 + cols[:, 2]
    u, inv, cnt = np.unique(key[op.reshape(-1)], return_inverse=True, return_counts=True); odd = int((cnt[inv] <= 2).sum()) if len(u) else 0
    pad = np.pad(op, 1); hole = ~op & pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
    return {"odd_px": odd, "pinholes": int(hole.sum())}


def job_clean(p):
    files = pngs(p["input"]); out = new_dir(p.get("out_root"), "clean"); cmds = []; dst = [os.path.join(out, os.path.basename(f)) for f in files]
    before = {f: counts(f) for f in files}
    for f, d in zip(files, dst):
        if p.get("speck_fix", True):
            r = run_tool(["speck_fix", f, d]); cmds.append(r["command"])
            if r["code"]: raise Bad(r["err"] or r["out"])
        else: shutil.copy(f, d)
    if p.get("fill_pinholes", True):
        r = run_tool(["fill_pinholes", *dst]); cmds.append(r["command"])
        if r["code"]: raise Bad(r["err"] or r["out"])
    after = {d: counts(d) for d in dst}; keys = ("odd_px", "pinholes"); import numpy as np
    from PIL import Image
    rows = [{"name": os.path.basename(f), "original": f, "result": d, "w": Image.open(f).width, "h": Image.open(f).height, "changed": int((np.array(Image.open(f).convert("RGBA")) != np.array(Image.open(d).convert("RGBA"))).any(-1).sum()), **{k: {"before": before[f].get(k), "after": after[d].get(k)} for k in keys}} for f, d in zip(files, dst)]
    return {"out": out, "commands": cmds, "note": "fill_pinholes edits only the copies in the new result folder, never your files.", "rows": rows, "totals": {**{k: {"before": sum(r[k]["before"] or 0 for r in rows), "after": sum(r[k]["after"] or 0 for r in rows)} for k in keys}, "changed": sum(r["changed"] for r in rows)}}


def job_layer(p):
    base, outfit = clean_path(p["base"]), clean_path(p["outfit"]); name = re.sub(r"[^\w-]+", "_", p.get("name") or "layer") or "layer"
    out = new_dir(p.get("out_root"), "layer"); opt = p.get("options", {}); args = ["pix_layer", "cut", base, outfit, out, "--name", name]
    if opt.get("solid", True): args.append("--solid")
    skin = opt.get("drop_skin", "auto")
    if skin in ("auto", "near"): args += ["--drop-skin", skin]
    for key, flag in (("bits", "--bits"), ("drop_parts", "--drop-parts"), ("outline", "--outline")):
        if opt.get(key): args.append(flag)
    r = run_tool(args)
    if r["code"]: raise Bad(r["err"] or r["out"] or "pix_layer failed")
    layers = sorted((os.path.join(out, name, f) for f in os.listdir(os.path.join(out, name)) if f.endswith(".png")), key=lambda f: natkey(os.path.basename(f)))
    notes = [l for l in (r["out"] + "\n" + r["err"]).splitlines() if "WARNING" in l or "SKIP" in l or "parts " in l]
    return {"out": out, "layer_dir": os.path.join(out, name), "commands": [r["command"]], "summary": r["out"].splitlines()[-1] if r["out"] else "", "notes": notes,
            "files": [fileinfo(f) for f in layers]}


def spec_string(s):
    kv = {"type": s.get("type", "inn"), "proj": s.get("proj", "iso")}
    for k in ("floors", "dormers"):
        if s.get(k) not in (None, "", 0, "0"): kv[k] = int(s[k])
    for k in ("wing", "lantern"):
        if s.get(k): kv[k] = "true"
    return ",".join(f"{k}={v}" for k, v in kv.items())


def job_draw_preview(p):
    import pixdraw
    from PIL import Image
    from pixdraw.cli import parse_spec as _ps  # noqa: the same spec parser the command line uses
    spec = _ps(spec_string(p)); img = pixdraw.render(spec, p.get("style", "dark_fantasy"))[0].convert("RGBA"); k = max(1, min(int(p.get("scale", 3)), 8))
    big = img.resize((img.width * k, img.height * k), Image.NEAREST); buf = io.BytesIO(); big.save(buf, "PNG")
    return {"png": base64.b64encode(buf.getvalue()).decode(), "w": img.width, "h": img.height, "spec": spec_string(p), "command": shown(["pixdraw", "build", spec_string(p), "--style", p.get("style", "dark_fantasy"), "--out", "draw_out", "--name", re.sub(r"[^\w-]+", "_", p.get("name") or p.get("type", "building")) or "building", "--scale", str(k), *(["--frames", str(int(p["frames"]))] if int(p.get("frames", 1)) > 1 else [])])}


def job_draw_save(p):
    out = new_dir(p.get("out_root"), "draw"); name = re.sub(r"[^\w-]+", "_", p.get("name") or p.get("type", "building")) or "building"
    args = ["pixdraw", "build", spec_string(p), "--style", p.get("style", "dark_fantasy"), "--out", out, "--name", name, "--scale", str(int(p.get("scale", 3)))]
    if int(p.get("frames", 1)) > 1: args += ["--frames", str(int(p["frames"]))]
    r = run_tool(args)
    if r["code"]: raise Bad(r["err"] or r["out"])
    return {"out": out, "commands": [r["command"]], "files": sorted(os.listdir(out))}


def job_hue(p):
    files = pngs(p["input"]); out = new_dir(p.get("out_root"), "recolour"); args = ["hue_shift", *files, "--out", out, "--hue", str(float(p.get("hue", 0)))]
    for k in ("sat", "val"):
        if p.get(k) not in (None, "", 1, 1.0, "1"): args += [f"--{k}", str(float(p[k]))]
    if p.get("range"): args += ["--range", str(p["range"])]
    r = run_tool(args)
    if r["code"]: raise Bad(r["err"] or r["out"])
    from PIL import Image
    return {"out": out, "commands": [folder_glob_shown("hue_shift", files, ["--out", out, *args[args.index("--hue"):]])], "rows": [{"name": os.path.basename(f), "original": f, "result": os.path.join(out, os.path.basename(f)), "w": Image.open(f).width, "h": Image.open(f).height} for f in files], "log": r["out"]}


def folder_glob(cmd, files, still=False):
    """show many frames of one folder as folder/*.png in the displayed command (the real run used the full list)"""
    d = os.path.dirname(files[0])
    if len(files) < 3 or any(os.path.dirname(f) != d for f in files): return cmd
    out = cmd
    for f in sorted(set(files), key=len, reverse=True): out = out.replace(" " + f, "").replace(' "' + f + '"', "").replace(" " + rel(f), "")
    t = out.split(" ", 4)   # python gizpix.py TOOL OUT REST
    return " ".join(t[:4] + ([rel(files[0]).replace("\\", "/")] if still else []) + [rel(d).replace("\\", "/") + "/*.png"] + t[4:]) if len(t) == 5 else out


def glob_shown(tool, head, files, tail, still=None):
    """a runnable displayed command with one argv: TOOL HEAD folder/*.png TAIL (the frames of one folder shown as a glob), quoted once"""
    d = os.path.dirname(files[0])
    if len(files) < 3 or any(os.path.dirname(f) != d for f in files): return shown([tool, *head, *([still] if still else []), *files, *tail])
    return shown([tool, *head, *([rel(still)] if still else []), rel(d).replace(chr(92), "/") + "/*.png", *tail])


def folder_glob_shown(tool, files, rest):
    """a runnable displayed command: TOOL folder/*.png REST (used when the frames share one folder)"""
    d = os.path.dirname(files[0])
    if len(files) < 3 or any(os.path.dirname(f) != d for f in files): return shown([tool, *files, *rest])
    return shown([tool, rel(d).replace(chr(92), "/") + "/*.png", *rest])


def job_pack(p):
    files = pngs(p["input"]); out = new_dir(p.get("out_root"), "pack"); name = re.sub(r"[^\w-]+", "_", p.get("name") or "sheet") or "sheet"; fps = str(float(p.get("fps", 12))); cmds = []
    sheet = run_tool(["make_sheet", os.path.join(out, name), *files, "--fps", fps]); cmds.append(glob_shown("make_sheet", [os.path.join(out, name)], files, ["--fps", fps]))
    if sheet["code"]: raise Bad(sheet["err"] or sheet["out"])
    if p.get("gif", True) and len(files) > 1:
        g = run_tool(["preview_gif", os.path.join(out, name + ".gif"), files[0], *files, "--beat", "even", "--fps", fps, "--scale", str(int(p.get("scale", 3)))]); cmds.append(glob_shown("preview_gif", [os.path.join(out, name + ".gif")], files, ["--beat", "even", "--fps", fps, "--scale", str(int(p.get("scale", 3)))], still=files[0]))
        if g["code"]: raise Bad(g["err"] or g["out"])
    from PIL import Image
    w, h = Image.open(files[0]).size; f = float(fps)
    return {"out": out, "commands": cmds, "files": sorted(os.listdir(out)), "info": {"frames": len(files), "w": w, "h": h, "fps": int(f) if f == int(f) else f}}


def job_lint(p):
    files = pngs(p["input"]); return {"rows": [{"name": os.path.basename(f), "path": f, **v} for f, v in lint(files).items()], "command": shown(["pixel_lint", *map(rel, files[:3]), "--json"] + (["..."] if len(files) > 3 else []))}


def job_sample_damaged(p):
    """a copy of the sample walk frames with off-palette specks and pinholes, so a first-time user can try the clean-up"""
    import random
    import numpy as np
    from PIL import Image
    src = os.path.join(ROOT, "samples", "walk_frames", "base", "east"); out = new_dir(p.get("out_root"), "sample_damaged"); rng = random.Random(3)
    for f in sorted(os.listdir(src), key=natkey):
        a = np.array(Image.open(os.path.join(src, f)).convert("RGBA")); ys, xs = np.nonzero(a[..., 3] > 0)
        core = [(y, x) for y, x in zip(ys, xs) if (a[y - 1:y + 2, x - 1:x + 2, 3] > 0).all()]
        for k, (y, x) in enumerate(rng.sample(core, 6)): a[y, x, :3] = ((255 - 37 * k) % 256, (40 + 53 * k) % 256, (200 + 31 * k) % 256)
        for y, x in rng.sample(core, 3): a[y, x, 3] = 0
        Image.fromarray(a).save(os.path.join(out, f))
    return {"out": out, "files": len(os.listdir(out))}


# ---- the task home: what a path holds, every registered tool, a generic runner -----------------------------------------------------------------------------------------
UI_JOB = {"pix_parallax": "bg", "speck_fix": "clean", "fill_pinholes": "clean", "pix_layer": "layer", "pixdraw": "draw", "hue_shift": "recolor", "make_sheet": "recolor", "preview_gif": "recolor"}     # tools that have their own screen
DEFAULT_ARGS = {"pix_parallax": "check {json} --strict", "pix_village": "kit {out}", "pixel_lint": "{in}", "pixdraw": "", "pixart": "", "make_sheet": "{out}/sheet {in}", "preview_gif": "{out}/preview.gif {in}", "pix_snap": "{in} {out}/snapped.png", "align_frames": "{in} --out {out}", "trim_frames": "{in} --out {out}", "colormatch": "{in} --out {out}", "pad_sprite": "{in} {out}/padded.png 192 256 24", "despeckle": "{in} --out {out}", "painterly_clean": "{in} --out {out}", "recolor_groups": "{in} --groups", "apply_palette": "auto {in} --colors 16", "pix_mixel": "{in}", "tile_check": "{in}", "qa": "{in}"}
MANUAL = {"palette_lock", "repair_outline", "ground_snap", "apply_pixel_fixes", "paperdoll", "rig_walk", "rig_walk2", "warp_layer", "clean_frames", "check_8dir", "xform", "contact_sheet"}      # tools whose arguments cannot be guessed: the runner opens their usage
NOT_RUNNABLE = {"ui", "doctor"}                                                                                                                                 # tools the generic runner never starts
HELP_CACHE = {}
RESERVED = {"con", "prn", "aux", "nul", *{f"com{i}" for i in range(1, 10)}, *{f"lpt{i}" for i in range(1, 10)}}      # Windows device names are never file or folder names here
SAVED_KINDS = (".png", ".gif", ".json", ".txt", ".md", ".html", ".tscn", ".hex", ".gpl")


def tools_list():
    import gizpix
    return [{"name": n, "group": g, "description": d, "screen": UI_JOB.get(n), "manual": n in MANUAL, "args": "" if n in MANUAL else DEFAULT_ARGS.get(n, "{in}")} for n, (g, rel_, d) in gizpix.TOOLS.items() if n not in NOT_RUNNABLE]


def tool_help(name):
    import gizpix
    if name not in gizpix.TOOLS or name in NOT_RUNNABLE: raise Bad("unknown tool")
    if name not in HELP_CACHE:
        r = run_tool(["help", name], timeout=90); HELP_CACHE[name] = (r["out"] or r["err"])[:6000]
    return {"name": name, "text": HELP_CACHE[name]}


def detect(path):
    """say what a path holds (frames, a sprite, a background stack, folders of frames), with a few numbers, and which jobs fit. Reads only; nothing is written. Large images are not measured, so it stays quick."""
    p = clean_path(path)
    if not os.path.exists(p): raise Bad(f"no such file or folder: {p}")
    if os.path.isfile(p):
        if p.lower().endswith(".json"):
            try: spec = json.load(open(p, encoding="utf-8"))
            except ValueError: raise Bad("this JSON file cannot be read")
            if isinstance(spec, dict) and isinstance(spec.get("layers"), list): return {"kind": "stack", "path": os.path.dirname(p), "json": p, "n": len(spec["layers"]), "thumbs": [], "facts": [f"{len(spec['layers'])} layers", "a background stack"], "defects": 0}
            raise Bad("this JSON file is not a background stack (no layers list)")
        files = pngs(p)
    else:
        if os.path.isfile(os.path.join(p, "stack.json")): return detect(os.path.join(p, "stack.json"))
        try: files = pngs(p)
        except Bad:
            subs = []
            for d in sorted(os.listdir(p), key=natkey):
                dp = os.path.join(p, d)
                if not os.path.isdir(dp) or d.startswith("."): continue
                if any(f.lower().endswith(".png") for f in os.listdir(dp)): subs.append(d)
                else:
                    for d2 in sorted(os.listdir(dp), key=natkey):
                        if os.path.isdir(os.path.join(dp, d2)) and any(f.lower().endswith(".png") for f in os.listdir(os.path.join(dp, d2))): subs.append(d + "/" + d2)
            if subs: return {"kind": "folders", "path": p, "n": len(subs), "subs": subs[:40], "thumbs": [], "facts": [f"{len(subs)} folders with PNG files: " + ", ".join(subs[:6]) + (" ..." if len(subs) > 6 else "")], "defects": 0}
            raise Bad(f"no PNG files in {p}, or in the folders directly inside it")
    from PIL import Image
    import numpy as np
    sizes = sorted({Image.open(f).size for f in files[:64]}); odd = pin = 0; cols = set(); measured = 0
    for f in files[:8]:
        if Image.open(f).width * Image.open(f).height > 1_000_000: continue
        measured += 1; c = counts(f); odd += c["odd_px"]; pin += c["pinholes"]
        a = np.array(Image.open(f).convert("RGBA")); cols.update(map(tuple, np.unique(a[a[..., 3] > 0][:, :3], axis=0)[:400].tolist()))
    n = len(files); facts = [f"{n} frame" + ("" if n == 1 else "s"), " ".join(f"{w}x{h}" for w, h in sizes[:3]) + (" (sizes differ)" if len(sizes) > 1 else "")]
    if measured: facts.append(f"{len(cols)} colours" if len(cols) < 400 else "400+ colours")
    defects = odd + pin
    facts.append((f"{odd} odd-colour pixels, {pin} pinholes" if defects else "no specks or pinholes found") if measured else "large images: not measured here")
    return {"kind": "frames" if n > 1 else "sprite", "path": p, "n": n, "sizes": [list(x) for x in sizes[:4]], "colours": len(cols), "odd_px": odd, "pinholes": pin, "defects": defects, "measured": measured > 0, "thumbs": files[:8], "facts": facts}

def clean_tb(t):
    """a Python traceback is cut to its last line: the user needs the reason, not the frames (and not the install paths)"""
    t = (t or "").strip()
    if "Traceback (most recent call last)" in t:
        lines = [l for l in t.splitlines() if l.strip()]
        return lines[-1].strip() if lines else t
    return t


def tailtxt(t, n=800):
    """the end of a long message, cut at a line boundary (never mid-word) with a leading ellipsis"""
    t = (t or "").strip()
    if len(t) <= n: return t
    keep = []; size = 0
    for line in reversed(t.splitlines()):
        if size + len(line) + 1 > n and keep: break
        keep.append(line[-n:]); size += len(line) + 1
    return "... " + "\n".join(reversed(keep))


def tool_run(p):
    """run one registered tool on COPIES of the input: nothing the user owns is edited. Arguments are split by spaces, never passed to a shell, and may only hold plain words and the placeholders
    {in} (the staged PNG files), {indir}, {json} (the staged stack.json) and {out} (the result folder, which is what Save copies). The tool runs with the result folder as its working directory, so a relative
    output name lands in the result folder; new files it writes next to the staged inputs, and changed copies, are collected into it too."""
    import gizpix, hashlib
    tool = p.get("tool", "")
    if tool not in gizpix.TOOLS or tool in NOT_RUNNABLE: raise Bad("unknown tool")
    toks = str(p.get("args", "")).split()
    for t in toks:
        if not re.fullmatch(r"(\{(?:out|indir|json)\}/?)?[\w.,:+=#%-]*|\{in\}", t) or ".." in t or t in (".", "..") or re.match(r"[A-Za-z]:", t): raise Bad(f"argument not allowed: {t!r}. Use plain words and numbers, and {{in}}, {{indir}}, {{json}}, {{out}} for files and folders.")
    out = new_dir(p.get("out_root"), "run_" + tool); sd = tempfile.mkdtemp(prefix="in_", dir=os.path.dirname(out)); inp = (p.get("input") or "").strip(); staged = []; jsn = ""; origin = {}
    try:
        if inp:
            src = clean_path(inp)
            if os.path.isfile(src): items = [src]
            elif os.path.isdir(src): items = sorted((os.path.join(src, f) for f in os.listdir(src) if os.path.isfile(os.path.join(src, f)) and f.lower().endswith(SAVED_KINDS)), key=lambda f: natkey(os.path.basename(f)))
            else: raise Bad(f"no such file or folder: {src}")
            if len(items) > 300 or sum(os.path.getsize(f) for f in items) > 200_000_000: raise Bad("too many or too large input files (limit 300 files, 200 MB)")
            for f in items:
                d = os.path.join(sd, os.path.basename(f)); shutil.copy(f, d); staged.append(d); origin[d] = f
                if f.lower().endswith(".json") and (not jsn or os.path.basename(f) == "stack.json"): jsn = d
        srcdir = (src if os.path.isdir(src) else os.path.dirname(src)) if inp else sd
        names0 = set(os.listdir(sd)); hashes = {f: hashlib.sha1(open(f, "rb").read()).digest() for f in staged}
        pngf = [f for f in staged if f.lower().endswith(".png")]; args = []
        for t in toks:
            if t == "{in}": args += pngf or staged
            else: args.append(t.replace("{indir}", sd).replace("{json}", jsn or sd).replace("{out}", out))
        r = run_tool([tool, *args], timeout=900, cwd=out); r["err"] = clean_tb(r["err"])
        for f in staged:                                                                  # a tool that edits in place edited the copies: put the changed copies in the result folder
            if hashlib.sha1(open(f, "rb").read()).digest() != hashes[f]: shutil.copy(f, os.path.join(out, os.path.basename(f)))
        for f in set(os.listdir(sd)) - names0:                                            # new files a tool wrote next to its inputs
            if os.path.isfile(os.path.join(sd, f)): shutil.copy(os.path.join(sd, f), os.path.join(out, f))
        files = sorted(os.listdir(out), key=natkey); imgs = []
        from PIL import Image
        for f in files:
            if f.lower().endswith((".png", ".gif")):
                try: w, h = Image.open(os.path.join(out, f)).size
                except Exception: continue
                imgs.append({"path": os.path.join(out, f), "name": f, "w": w, "h": h})
        back = lambda t: t.replace(sd + os.sep, srcdir + os.sep).replace(sd, srcdir)     # show the paths the user gave, not the staging copies
        if r["code"] and not files: raise Bad(tailtxt(back(r["err"] or r["out"] or f"{tool} failed")))
        shown_args = [back(origin.get(a, a)) for a in args]                               # one argv, quoted once by shown(): a path with spaces stays runnable
        text = back(r["out"] + ("\n" + r["err"] if r["err"] else "")).replace(out, "<result folder>")
        return {"out": out, "commands": [shown([tool, *shown_args])], "code": r["code"], "text": tailtxt(text, 6000), "files": files, "images": imgs[:24], "n_images": len(imgs)}
    finally:
        shutil.rmtree(sd, ignore_errors=True)


def upload_new(p):
    d = tempfile.mkdtemp(prefix="up_", dir=STATE["stage"]); STATE["uploads"][os.path.basename(d)] = {"dir": d, "n": 0, "bytes": 0}; return {"id": os.path.basename(d), "path": d}


def upload_file(q, data):
    u = STATE["uploads"].get(q.get("id", [""])[0])
    if not u: raise Bad("unknown upload")
    name = os.path.basename((q.get("name", [""])[0]).replace("\\", "/"))
    if name.startswith(".") or name.split(".")[0].lower() in RESERVED or not name.lower().endswith(SAVED_KINDS) or not re.fullmatch(r"[\w .()+,#-]+\.\w+", name): raise Bad(f"file type or name not accepted: {name}")
    if u["n"] >= 400 or u["bytes"] + len(data) > 200_000_000: raise Bad("too many or too large files (limit 400 files, 200 MB)")
    dst = os.path.join(u["dir"], name)
    if os.path.exists(dst): raise Bad(f"two dropped files are both called {name}; drop one folder at a time")
    open(dst, "wb").write(data); u["n"] += 1; u["bytes"] += len(data); return {"saved": name, "n": u["n"]}



# ---- backgrounds: open a parallax stack, draw one, export it --------------------------------------------------------------------------------------------------------
def _pp():
    d = os.path.join(ROOT, "parallax")
    if d not in sys.path: sys.path.insert(0, d)
    import pix_parallax
    return pix_parallax


def bg_open(p):
    """what a background stack holds: one row per layer (size, speed, loop, notes, flags), the stack's own flags, and a live preview page (a self-contained HTML canvas) in the staging folder"""
    pp = _pp(); path = clean_path(p.get("path", "")); js = os.path.join(path, "stack.json") if os.path.isdir(path) else path
    if not os.path.isfile(js): raise Bad("no stack.json found at " + path)
    try:
        spec = pp.load_spec(js); rep = pp.check(spec)
    except (Exception, SystemExit) as e: raise Bad(f"this stack cannot be read: {e}")
    layers = []
    for L, row in zip(spec["layers"], rep["layers"]):
        mine = [f.split(": ", 1)[1] if ": " in f else f for f in rep["flags"] if f.startswith(L["file"] + ":")]
        layers.append({"file": L["file"], "path": L["path"], "w": row["size"][0], "h": row["size"][1], "scroll": L["scroll"], "px": L["px_per_frame"], "repeat": L["repeat"], "frames": 1 + len(L.get("frame_paths", [])), "notes": row["notes"], "flags": mine})
    old = STATE.get("preview_dir")
    if old and os.path.isdir(old): shutil.rmtree(old, ignore_errors=True); STATE["made"].discard(old)         # one live preview folder at a time
    out = STATE["preview_dir"] = new_dir(p.get("out_root"), "bg_preview"); html = pp.preview_html(spec, os.path.join(out, "preview.html"))
    general = [f for f in rep["flags"] if not any(f.startswith(l["file"] + ":") for l in layers)]
    return {"json": js, "name": spec["name"], "viewport": spec["viewport"], "fps": spec["fps"], "camera": spec.get("camera_px_per_s"), "loop_frames": rep["loop_frames"], "loop_seconds": rep["loop_seconds"], "layers": layers, "general": general, "preview": html}


PRESET_HOURS = ("dawn", "noon", "dusk", "night")


def bg_draw(p):
    """draw a stack from code into a new staged folder (a preset, or the village) and open it"""
    out = new_dir(p.get("out_root"), "bg_village" if p.get("village") else "bg_" + re.sub(r"[^a-z_]", "", str(p.get("preset", "preset"))))
    seed = str(int(p.get("seed", 1) or 1))
    if p.get("village"): r_ = run_tool(["pix_village", "stack", out, seed], timeout=900)
    else:
        pp = _pp(); preset = p.get("preset", "dusk_hills")
        if preset not in pp.PRESETS: raise Bad("unknown preset")
        args = ["pix_parallax", "draw", "--preset", preset, "--out", out, "--seed", seed]
        if p.get("hour") in PRESET_HOURS: args += ["--hour", p["hour"]]
        if p.get("pace") in ("walk", "run"): args += ["--pace", p["pace"]]
        r_ = run_tool(args, timeout=900)
    if r_["code"]: raise Bad(tailtxt(r_["err"] or r_["out"] or "drawing failed", 600))
    d = bg_open({"path": out, "out_root": p["out_root"]}); d["commands"] = [r_["command"]]; d["drawn"] = out; return d


EXPORT_FORMATS = {"tiled": "stack.tmj", "phaser": "stack_phaser.js", "css": "stack.css", "ldtk": "stack_ldtk.json", "json": "stack_export.json"}


def bg_export(p):
    """export a stack for an engine into a new staged folder (Save copies it); never writes next to the stack"""
    js = clean_path(p.get("json", ""))
    if not os.path.isfile(js): raise Bad("no stack.json at " + js)
    target = p.get("target", "godot"); out = new_dir(p.get("out_root"), "bg_" + re.sub(r"[^a-z]", "", target))
    if target == "godot":
        args = ["pix_parallax", "export", js, "--godot", out, "--mode", "loop" if p.get("mode") == "loop" else "camera"]
        z = str(p.get("min_zoom", "")).strip()
        if z:
            try: assert 0 < float(z) <= 1
            except (ValueError, AssertionError): raise Bad("minimum zoom must be a number above 0 and up to 1, for example 0.5")
            args += ["--min-zoom", z]
    elif target == "gif": args = ["pix_parallax", "preview", js, os.path.join(out, "preview.gif"), "--scale", "2"]
    elif target in EXPORT_FORMATS: args = ["pix_parallax", "export", js, "--format", target, "--out", os.path.join(out, EXPORT_FORMATS[target])]
    else: raise Bad("unknown export target")
    r_ = run_tool(args, timeout=900)
    files = sorted(os.listdir(out), key=natkey)
    if r_["code"] and not files: raise Bad(tailtxt(r_["err"] or r_["out"] or "export failed", 600))
    return {"out": out, "commands": [r_["command"]], "code": r_["code"], "text": (r_["out"] + ("\n" + r_["err"] if r_["err"] else "")).replace(out, "<result folder>")[-3000:], "files": files}


def bg_seam(p):
    """the wrap of one layer shown rolled by half, red line at the join"""
    src = clean_path(p.get("path", ""))
    if not src.lower().endswith(".png") or not os.path.isfile(src): raise Bad("not a layer image")
    out = new_dir(p.get("out_root"), "bg_seam"); dst = os.path.join(out, "seam.png"); r_ = run_tool(["pix_parallax", "seam", src, "--view", dst])
    if r_["code"] or not os.path.exists(dst): raise Bad(tailtxt(r_["err"] or r_["out"] or "seam view failed", 400))
    return {"png": dst, "text": r_["out"][-400:]}


def bg_heal(p):
    """heal the wrap seam of one layer: the stack is copied to a new staged folder and the layer is replaced there by the healed copy (pixels are only moved, never new colours); the original stack is untouched"""
    js = clean_path(p.get("json", "")); layer = str(p.get("layer", "")); how = p.get("method", "profile")
    if how not in ("profile", "mincut"): raise Bad("method must be profile or mincut")
    try: band = int(p.get("band") or 24); assert 1 <= band <= 400
    except (ValueError, AssertionError): raise Bad("band must be a whole number from 1 to 400")
    pp = _pp()
    try: spec = pp.load_spec(js)
    except (Exception, SystemExit) as e: raise Bad(f"this stack cannot be read: {e}")
    L = next((x for x in spec["layers"] if x["file"] == layer), None)
    if not L or os.path.basename(layer) != layer: raise Bad("no such layer in this stack")
    if L.get("frame_paths"): raise Bad("this layer is animated: heal each frame with the command line (pix_parallax seam FRAME --heal ...)")
    out = new_dir(p.get("out_root"), "bg_healed"); src = os.path.dirname(js)
    for f in os.listdir(src):
        if f.lower().endswith((".png", ".json")) and os.path.isfile(os.path.join(src, f)): shutil.copy(os.path.join(src, f), os.path.join(out, f))
    tgt = os.path.join(out, layer); tmp = os.path.join(out, "_healed.png")
    r_ = run_tool(["pix_parallax", "seam", tgt, "--heal", how, "--out", tmp, "--band", str(band)])
    if r_["code"] or not os.path.exists(tmp): raise Bad(tailtxt(r_["err"] or r_["out"] or "healing failed", 600))
    os.replace(tmp, tgt)
    d = bg_open({"path": out, "out_root": p["out_root"]}); d["commands"] = [r_["command"].replace(tgt, layer).replace(tmp, "healed_" + layer)]; d["drawn"] = out; d["healed"] = {"layer": layer, "method": how, "band": band, "text": r_["out"][-400:]}
    return d


JOBS = {"clean": job_clean, "layer": job_layer, "draw/preview": job_draw_preview, "draw/save": job_draw_save, "hue": job_hue, "pack": job_pack, "lint": job_lint, "sample/damaged": job_sample_damaged, "tool/run": tool_run, "upload/new": upload_new, "bg/open": bg_open, "bg/draw": bg_draw, "bg/export": bg_export, "bg/seam": bg_seam, "bg/heal": bg_heal, "detect": lambda p: detect(p.get("path", ""))}


def state():
    s = os.path.join(ROOT, "samples", "walk_frames"); sets = {}
    if os.path.isdir(s):
        for k in sorted(os.listdir(s)):
            for d in sorted(os.listdir(os.path.join(s, k))): sets.setdefault(k, []).append(os.path.join(s, k, d))
    from pixdraw import PRESETS, list_styles
    import gizpix
    return {"version": gizpix.__version__, "cwd": os.getcwd(), "out_root": STATE["out_root"], "sample_root": s if os.path.isdir(s) else "", "samples": sets, "buildings": sorted(PRESETS), "styles": list(list_styles()), "presets": list(_pp().PRESETS), "hours": list(PRESET_HOURS),
            "recent": [{"name": os.path.basename(d), "path": d} for d in sorted((d for d in STATE["made"] if os.path.dirname(d) == STATE["stage"] and os.path.isdir(d) and os.listdir(d) and not os.path.basename(d).startswith(("bg_preview", "bg_seam", "up_", "in_", "sample_"))), key=os.path.getmtime, reverse=True)[:8]]}


def listing(path):
    p = clean_path(path or os.getcwd())
    if os.path.isfile(p): p = os.path.dirname(p)
    if not os.path.isdir(p): raise Bad(f"no such folder: {p}")
    ents = sorted(os.listdir(p), key=natkey); dirs = [e for e in ents if os.path.isdir(os.path.join(p, e)) and not e.startswith(".")]
    return {"path": p, "parent": os.path.dirname(p) if os.path.dirname(p) != p else None, "dirs": dirs[:300], "pngs": [e for e in ents if e.lower().endswith(".png")][:300]}


def png_bytes(path, scale, crop=False):
    from PIL import Image
    p = clean_path(path)
    if not p.lower().endswith((".png", ".gif")) or not os.path.isfile(p): raise Bad("not an image file")
    im = Image.open(p).convert("RGBA"); k = max(1, min(int(scale or 1), 8))
    if crop:                                    # thumbnails: the content box at its true size, so pixels are never resampled
        bb = im.getchannel("A").getbbox()
        if bb: im = im.crop((max(0, bb[0] - 1), max(0, bb[1] - 1), min(im.width, bb[2] + 1), min(im.height, bb[3] + 1)))
    if im.width * k > 4096 or im.height * k > 4096: k = 1
    buf = io.BytesIO(); (im.resize((im.width * k, im.height * k), Image.NEAREST) if k > 1 else im).save(buf, "PNG"); return buf.getvalue()


def worn_bytes(base, layer, scale):
    from PIL import Image
    b = Image.open(clean_path(base)).convert("RGBA"); l = Image.open(clean_path(layer)).convert("RGBA")
    if b.size != l.size: raise Bad("base and layer have different sizes")
    b.alpha_composite(l); k = max(1, min(int(scale or 1), 8)); buf = io.BytesIO(); (b.resize((b.width * k, b.height * k), Image.NEAREST) if k > 1 else b).save(buf, "PNG"); return buf.getvalue()


def save_result(b):
    """copy a staged result into the output root as a new folder"""
    src = clean_path(b.get("from", ""))
    if src not in STATE["made"] or os.path.dirname(src) != STATE["stage"]: raise Bad("only a result made in this session can be saved")
    dst = new_dir(STATE["out_root"], b.get("name") or os.path.basename(src)); shutil.rmtree(dst); shutil.copytree(src, dst); STATE["made"].add(dst)
    return {"out": dst, "from": src}


def diff_bytes(a, b, scale):
    """the changed pixels between two same-size images, marked in red over the faded result (what a tool actually touched)"""
    from PIL import Image, ImageChops
    A = Image.open(clean_path(a)).convert("RGBA"); B = Image.open(clean_path(b)).convert("RGBA")
    if A.size != B.size: raise Bad("images have different sizes")
    ch = ImageChops.difference(A, B).convert("RGBA"); mask = ch.point(lambda v: 255 if v else 0).convert("L").point(lambda v: 255 if v else 0)
    px = [(0, 0, 0)] ; out = Image.new("RGBA", A.size, (0, 0, 0, 0)); faded = B.copy(); faded.putalpha(B.getchannel("A").point(lambda v: v // 3)); out.alpha_composite(faded)
    chm = Image.new("L", A.size, 0); chm.putdata([255 if any(p) else 0 for p in ch.getdata()]); red = Image.new("RGBA", A.size, (208, 59, 47, 255)); out.paste(red, (0, 0), chm)
    k = max(1, min(int(scale or 1), 8)); buf = io.BytesIO(); (out.resize((out.width * k, out.height * k), Image.NEAREST) if k > 1 else out).save(buf, "PNG"); return buf.getvalue()


def raw_file(path):
    p = clean_path(path)
    if not os.path.isfile(p) or not any(p.startswith(m + os.sep) for m in STATE["made"]): raise Bad("only files of results made in this session are served")
    ext = p.rsplit(".", 1)[-1].lower()
    if ext not in ("gif", "png", "json", "html"): raise Bad("not a result file type")
    return open(p, "rb").read(), {"gif": "image/gif", "png": "image/png", "json": "application/json", "html": "text/html; charset=utf-8"}[ext]


def pick_folder(start):
    """the operating system's own folder dialog, run in a child process (tkinter must own its thread); '' when cancelled"""
    code = "import sys,tkinter as t;from tkinter import filedialog as f;r=t.Tk();r.withdraw();r.attributes('-topmost',True);print(f.askdirectory(initialdir=sys.argv[1] or None,mustexist=True) or '')"
    st = clean_path(start) if start else os.getcwd()
    try: r = subprocess.run([sys.executable, "-c", code, st if os.path.isdir(st) else os.getcwd()], capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired: return {"path": ""}
    if r.returncode: raise Bad("The folder dialog is not available here. Use Browse or type the path.")
    return {"path": os.path.normpath(r.stdout.strip()) if r.stdout.strip() else ""}


def reveal(path):
    p = clean_path(path)
    if p not in STATE["made"] and os.path.dirname(p) not in STATE["made"]: raise Bad("only folders this session made can be opened")
    if sys.platform.startswith("win"): os.startfile(p)       # noqa
    elif sys.platform == "darwin": subprocess.Popen(["open", p])
    else: subprocess.Popen(["xdg-open", p])
    return {"opened": p}


def err_of(e):
    """an HTTP status and a message that names the problem without leaking paths or Python internals"""
    if isinstance(e, Bad): return 400, str(e)
    if isinstance(e, KeyError): return 400, f"missing field {e}"
    if isinstance(e, json.JSONDecodeError): return 400, "the request body is not valid JSON"
    if isinstance(e, subprocess.TimeoutExpired): return 400, "the tool took too long and was stopped"
    if isinstance(e, (ValueError, TypeError, AttributeError)): return 400, "the request was not understood"
    if isinstance(e, OSError): return 400, "that file or folder could not be read or written, or it is not an image Gizpix can read"
    return 500, f"internal error ({type(e).__name__})"


class H(BaseHTTPRequestHandler):
    server_version = "gizpix-ui"
    def log_message(self, *a): pass
    def _ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]; origin = self.headers.get("Origin")
        if origin:
            o = urlparse(origin)
            if o.hostname not in ("127.0.0.1", "localhost") or o.port != STATE["port"]: return False
        return host in ("127.0.0.1", "localhost")
    def _send(self, code, body, ctype="application/json", csp=False):
        if isinstance(body, (dict, list)): body = json.dumps(body).encode()
        elif isinstance(body, str): body = body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        if csp: self.send_header("Content-Security-Policy", "sandbox allow-scripts")                     # a result page that is opened directly runs in the same sandbox as in the preview frame
        self.end_headers(); self.wfile.write(body)
    def _auth(self, q): return secrets.compare_digest(self.headers.get("X-Gizpix-Token") or (q.get("t", [""])[0]), STATE["token"])
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if not self._ok(): return self._send(403, {"error": "forbidden host"})
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, open(os.path.join(WEB, "index.html"), encoding="utf8").read().replace("{{TOKEN}}", STATE["token"]), "text/html; charset=utf-8")
            if u.path.startswith("/static/"):
                f = os.path.normpath(os.path.join(WEB, u.path[len("/static/"):]))
                if not f.startswith(WEB + os.sep) or not os.path.isfile(f): return self._send(404, {"error": "not found"})
                ct = {"css": "text/css", "js": "text/javascript", "svg": "image/svg+xml", "woff2": "font/woff2"}.get(f.rsplit(".", 1)[-1], "application/octet-stream")
                return self._send(200, open(f, "rb").read(), ct + ("; charset=utf-8" if ct.startswith("text") else ""))
            if not self._auth(q): return self._send(403, {"error": "bad token"})
            if u.path == "/api/state": return self._send(200, state())
            if u.path == "/api/progress": return self._send(200, progress(q.get("run", [""])[0]))
            if u.path == "/api/tools": return self._send(200, tools_list())
            if u.path == "/api/tool-help": return self._send(200, tool_help(q.get("name", [""])[0]))
            if u.path == "/api/detect": return self._send(200, detect(q.get("path", [""])[0]))
            if u.path == "/api/ls": return self._send(200, listing(q.get("path", [""])[0]))
            if u.path == "/api/png": return self._send(200, png_bytes(q["path"][0], q.get("scale", ["1"])[0], q.get("crop", [""])[0] == "1"), "image/png")
            if u.path == "/api/diff": return self._send(200, diff_bytes(q["a"][0], q["b"][0], q.get("scale", ["1"])[0]), "image/png")
            if u.path == "/api/raw": body, ct = raw_file(q["path"][0]); return self._send(200, body, ct, csp=ct.startswith("text/html"))
            if u.path == "/api/worn": return self._send(200, worn_bytes(q["base"][0], q["layer"][0], q.get("scale", ["1"])[0]), "image/png")
            return self._send(404, {"error": "not found"})
        except Exception as e: code, msg = err_of(e); return self._send(code, {"error": msg})
    def do_POST(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if not self._ok(): return self._send(403, {"error": "forbidden host"})
        if not self._auth(q): return self._send(403, {"error": "bad token"})
        try:
            n = max(0, int(self.headers.get("Content-Length") or 0))
            if u.path != "/api/upload" and n > 1_000_000: raise Bad("the request is too large")
            if u.path == "/api/upload":
                if n > 30_000_000: raise Bad("file too large (limit 30 MB)")
                return self._send(200, upload_file(q, self.rfile.read(n)))
            body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            if not isinstance(body, dict): raise Bad("the request body must be a JSON object")
            if u.path == "/api/reveal": return self._send(200, reveal(body.get("path", "")))
            if u.path == "/api/pick-folder": return self._send(200, pick_folder(body.get("path", "")))
            if u.path == "/api/save": return self._send(200, save_result(body))
            if u.path == "/api/stop": return self._send(200, stop_run(str(body.get("run", ""))))
            if u.path == "/api/out-root":
                nr = clean_path(body.get("path") or STATE["out_root"])
                if os.path.isfile(nr): raise Bad("the output folder must be a folder, not a file")
                STATE["out_root"] = nr; return self._send(200, {"out_root": STATE["out_root"]})
            job = u.path[len("/api/job/"):] if u.path.startswith("/api/job/") else None
            if job in JOBS:
                body["out_root"] = STATE["stage"]; rid = str(body.pop("_run", "") or ""); run = None
                if re.fullmatch(r"[A-Za-z0-9_-]{6,48}", rid): run = STATE["runs"][rid] = {"start": time.time(), "procs": set(), "cmd": "", "step": 0, "stopped": False}
                LOCAL.run = run
                try: return self._send(200, JOBS[job](body))      # runs only ever stage; Save copies to the output root
                finally:
                    LOCAL.run = None
                    if run: STATE["runs"].pop(rid, None)
            return self._send(404, {"error": "unknown job"})
        except Exception as e: code, msg = err_of(e); return self._send(code, {"error": msg})


def make_server(port=8765):
    for p in ([port] if port == 0 else range(port, port + 20)):
        try: srv = ThreadingHTTPServer(("127.0.0.1", p), H); STATE["port"] = srv.server_address[1]; return srv
        except OSError: continue
    raise SystemExit(f"gizpix ui: no free port near {port}")


def selftest():
    import urllib.request, urllib.error
    t = tempfile.mkdtemp(prefix="gizpix_ui_"); STATE["out_root"] = t; stage = STATE["stage"]; srv = make_server(0); th = threading.Thread(target=srv.serve_forever, daemon=True); th.start(); base = f"http://127.0.0.1:{STATE['port']}"
    def get(path, auth=True, data=None):
        req = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None, headers={"X-Gizpix-Token": STATE["token"]} if auth else {})
        try: return urllib.request.urlopen(req, timeout=300).read()
        except urllib.error.HTTPError as e: return e.code
    try:
        assert b"gizpix" in get("/", False).lower(), "index"
        assert get("/api/state", False) == 403, "state must need the token"
        s = json.loads(get("/api/state")); assert s["buildings"] and "samples" in s
        _d = os.path.join(ROOT, "samples", "walk_frames", "base", "east"); _c = folder_glob_shown("hue_shift", [os.path.join(_d, f"{i}.png") for i in range(3)], ["--out", "o", "--hue", "1"])
        assert "--out *" not in _c and _c.split(" --out ")[0].endswith("*.png\""), _c      # the glob is an input, never the value of --out
        req = urllib.request.Request(base + "/api/state", headers={"X-Gizpix-Token": STATE["token"], "Host": "evil.example"})
        try: urllib.request.urlopen(req); raise AssertionError("foreign Host accepted")
        except urllib.error.HTTPError as e: assert e.code == 403
        dmg = json.loads(get("/api/job/sample/damaged", data={})); assert dmg["files"] == 8
        c = json.loads(get("/api/job/clean", data={"input": dmg["out"]})); assert c["totals"]["changed"] >= 20 and c["totals"]["odd_px"]["after"] < c["totals"]["odd_px"]["before"], c["totals"]
        assert os.path.dirname(c["out"]) == stage and dmg["out"] != c["out"], "runs only write to the staging folder"
        assert not os.listdir(t), "nothing reaches the output root before Save"
        sv = json.loads(get("/api/save", data={"from": c["out"], "name": "cleaned"})); assert os.path.dirname(sv["out"]) == t and len(os.listdir(sv["out"])) == 8
        sv2 = json.loads(get("/api/save", data={"from": c["out"], "name": "cleaned"})); assert sv2["out"] != sv["out"], "a second save never overwrites the first"
        assert get("/api/save", data={"from": t, "name": "x"}) == 400, "only staged results can be saved"
        sample = os.path.join(ROOT, "samples", "walk_frames"); L = json.loads(get("/api/job/layer", data={"base": os.path.join(sample, "base", "east"), "outfit": os.path.join(sample, "robe", "east"), "name": "robe"}))
        assert len(L["files"]) == 8 and L["files"][0]["opaque"] > 100, L
        assert get("/api/png?t=" + STATE["token"] + "&path=" + L["files"][0]["path"] + "&scale=3")[:4] == b"\x89PNG"
        assert get("/api/worn?t=" + STATE["token"] + "&base=" + os.path.join(sample, "base", "east", "0.png") + "&layer=" + L["files"][0]["path"])[:4] == b"\x89PNG"
        d = json.loads(get("/api/job/draw/preview", data={"type": "inn", "proj": "iso", "style": "dark_fantasy"})); assert d["w"] > 20 and base64.b64decode(d["png"])[:4] == b"\x89PNG"
        r0 = c["rows"][0]; assert get("/api/diff?t=" + STATE["token"] + "&a=" + r0["original"] + "&b=" + r0["result"])[:4] == b"\x89PNG"
        assert get("/api/raw?t=" + STATE["token"] + "&path=" + r0["result"])[:4] == b"\x89PNG" and get("/api/raw?t=" + STATE["token"] + "&path=" + os.path.join(ROOT, "gizpix.py")) == 400
        assert get("/api/job/layer", data={"base": "/no/such", "outfit": "/no/such"}) == 400
        assert get("/api/png?t=" + STATE["token"] + "&path=" + os.path.join(ROOT, "LICENSE")) == 400, "only images are served"
        tl = json.loads(get("/api/tools")); assert any(x["name"] == "pix_village" for x in tl) and any(x["screen"] == "clean" for x in tl) and not any(x["name"] == "ui" for x in tl)
        assert "usage" in json.loads(get("/api/tool-help?t=" + STATE["token"] + "&name=pixel_lint"))["text"].lower() or json.loads(get("/api/tool-help?t=" + STATE["token"] + "&name=pixel_lint"))["text"]
        dt = json.loads(get("/api/detect?t=" + STATE["token"] + "&path=" + dmg["out"])); assert dt["kind"] == "frames" and dt["n"] == 8 and dt["defects"] > 0 and len(dt["thumbs"]) == 8, dt
        assert json.loads(get("/api/detect?t=" + STATE["token"] + "&path=" + os.path.join(sample, "base")))["kind"] == "folders"
        assert get("/api/detect?t=" + STATE["token"] + "&path=" + os.path.join(t, "nope")) == 400
        tr = json.loads(get("/api/job/tool/run", data={"tool": "pixel_lint", "input": dmg["out"], "args": "{in}"})); assert tr["code"] == 0 and os.path.dirname(tr["out"]) == stage and "0.png" in tr["text"], tr
        for bad in ("{in} --out C:/x", "{in} ../x", "{in} ; calc", "{in} $HOME", "{in} \\x"): assert get("/api/job/tool/run", data={"tool": "pixel_lint", "input": dmg["out"], "args": bad}) == 400, bad
        assert get("/api/job/tool/run", data={"tool": "ui", "input": "", "args": ""}) == 400 and get("/api/job/tool/run", data={"tool": "rm", "input": "", "args": ""}) == 400
        before_bytes = open(os.path.join(dmg["out"], "0.png"), "rb").read(); ip = json.loads(get("/api/job/tool/run", data={"tool": "fill_pinholes", "input": dmg["out"], "args": "{in}"}))
        assert open(os.path.join(dmg["out"], "0.png"), "rb").read() == before_bytes and "0.png" in ip["files"], "an in-place tool edits copies, and the changed copy lands in the result folder"
        bgd = json.loads(get("/api/job/bg/draw", data={"preset": "dusk_hills", "seed": 3})); assert len(bgd["layers"]) >= 6 and bgd["loop_frames"] and os.path.dirname(bgd["drawn"]) == stage, bgd["loop_frames"]
        assert get("/api/raw?t=" + STATE["token"] + "&path=" + bgd["preview"])[:9].lower() == b"<!doctype", "the live preview page is served"
        assert json.loads(get("/api/job/bg/open", data={"path": bgd["drawn"]}))["name"] == bgd["name"]
        ex = json.loads(get("/api/job/bg/export", data={"json": bgd["json"], "target": "godot", "mode": "camera"})); assert any(f.endswith(".tscn") for f in ex["files"]), ex["files"]
        assert any(f.endswith(".css") for f in json.loads(get("/api/job/bg/export", data={"json": bgd["json"], "target": "css"}))["files"])
        assert get("/api/job/bg/export", data={"json": bgd["json"], "target": "nope"}) == 400 and get("/api/job/bg/export", data={"json": bgd["json"], "target": "godot", "min_zoom": "5"}) == 400
        assert get("/api/job/bg/open", data={"path": t}) == 400 and get("/api/job/bg/draw", data={"preset": "../x"}) == 400
        sm = json.loads(get("/api/job/bg/seam", data={"path": bgd["layers"][0]["path"]})); assert get("/api/png?t=" + STATE["token"] + "&path=" + sm["png"])[:4] == b"\x89PNG"
        sp0 = json.loads(open(bgd["json"]).read()); ly = next(l for l in bgd["layers"] if l["frames"] == 1 and l["repeat"] in ("x", "xy") and l["w"] > 100)
        hl = json.loads(get("/api/job/bg/heal", data={"json": bgd["json"], "layer": ly["file"], "method": "mincut", "band": 8})); hly = next(l for l in hl["layers"] if l["file"] == ly["file"])
        assert hly["w"] == ly["w"] - 8 and hl["healed"]["layer"] == ly["file"] and os.path.dirname(hl["drawn"]) == stage and hl["json"] != bgd["json"], (hly["w"], ly["w"])
        from PIL import Image as _I
        assert _I.open(ly["path"]).width == ly["w"], "the original layer is untouched"
        assert get("/api/job/bg/heal", data={"json": bgd["json"], "layer": ly["file"], "method": "x"}) == 400 and get("/api/job/bg/heal", data={"json": bgd["json"], "layer": "../x.png"}) == 400 and get("/api/job/bg/heal", data={"json": bgd["json"], "layer": ly["file"], "band": 0}) == 400
        import time as _t
        res = {}
        def _long(): res["r"] = get("/api/job/bg/draw", data={"village": True, "seed": 2, "_run": "selftest-run-1"})
        th2 = threading.Thread(target=_long); th2.start(); _t.sleep(3)
        pr = json.loads(get("/api/progress?t=" + STATE["token"] + "&run=selftest-run-1")); assert pr["running"] and "pix_village" in pr["cmd"], pr
        t0 = _t.time(); assert json.loads(get("/api/stop", data={"run": "selftest-run-1"}))["stopped"]; th2.join(60)
        assert res["r"] == 400 and _t.time() - t0 < 30, ("a stopped run ends quickly with an error", res, _t.time() - t0)
        assert not json.loads(get("/api/progress?t=" + STATE["token"] + "&run=selftest-run-1"))["running"]
        for bad in ("{in} --out D:esc", "{in} .", "{in} ..", "x:y"): assert get("/api/job/tool/run", data={"tool": "pixel_lint", "input": dmg["out"], "args": bad}) == 400, bad
        cwd0 = set(os.listdir(os.getcwd())); ms = json.loads(get("/api/job/tool/run", data={"tool": "make_sheet", "input": dmg["out"], "args": "mysheet {in}"}))
        assert set(os.listdir(os.getcwd())) == cwd0 and "mysheet.png" in ms["files"], ("a tool's relative output lands in the result folder, never in the server's cwd", ms["files"])
        assert "make_sheet" in ms["commands"][0] and not any(x.startswith("in_") for x in os.listdir(stage)), "staged input copies are removed"
        assert get("/api/png?t=" + STATE["token"]) == 400 and get("/api/diff?t=" + STATE["token"] + "&a=" + os.path.join(ROOT, "gizpix.py") + "&b=" + os.path.join(ROOT, "gizpix.py")) == 400
        req = urllib.request.Request(base + "/api/stop", data=b"[1,2]", headers={"X-Gizpix-Token": STATE["token"]})
        try: urllib.request.urlopen(req); raise AssertionError("array body accepted")
        except urllib.error.HTTPError as e: assert e.code == 400
        dd = json.loads(get("/api/detect?t=" + STATE["token"] + "&path=" + os.path.join(ROOT, "samples", "walk_frames"))); assert dd["kind"] == "folders" and any("/" in x for x in dd["subs"]), dd
        tl2 = {x["name"]: x for x in tl}; one = os.path.join(dmg["out"], "0.png")
        for name in ("align_frames", "trim_frames", "colormatch", "preview_gif", "scrub", "despeckle", "painterly_clean", "pix_mixel", "tile_check", "qa", "recolor_groups", "apply_palette", "make_sheet", "pixel_lint", "pix_snap", "pad_sprite"):
            rr = get("/api/job/tool/run", data={"tool": name, "input": one if name in ("pix_snap", "pad_sprite") else dmg["out"], "args": tl2[name]["args"]})
            assert not isinstance(rr, int), ("the default arguments of " + name + " must run", tl2[name]["args"], rr)
        assert all(tl2[n]["manual"] and tl2[n]["args"] == "" for n in ("palette_lock", "paperdoll", "rig_walk")) and not tl2["make_sheet"]["manual"]
        up = json.loads(get("/api/job/upload/new", data={})); req = urllib.request.Request(base + "/api/upload?id=" + up["id"] + "&name=a.png", data=open(os.path.join(dmg["out"], "0.png"), "rb").read(), headers={"X-Gizpix-Token": STATE["token"]})
        assert json.loads(urllib.request.urlopen(req).read())["n"] == 1
        req = urllib.request.Request(base + "/api/upload?id=" + up["id"] + "&name=evil.exe", data=b"x", headers={"X-Gizpix-Token": STATE["token"]})
        try: urllib.request.urlopen(req); raise AssertionError("exe accepted")
        except urllib.error.HTTPError as e: assert e.code == 400
    finally: srv.shutdown(); shutil.rmtree(t, ignore_errors=True); shutil.rmtree(stage, ignore_errors=True)
    print("ui selftest ok")


def main(argv):
    if argv[:1] == ["selftest"]: selftest(); return 0
    ap = argparse.ArgumentParser(prog="gizpix ui", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765); ap.add_argument("--no-open", action="store_true"); ap.add_argument("--out-root", help="where results are written (a new subfolder per run); default ./gizpix_out")
    a = ap.parse_args(argv)
    if a.out_root: STATE["out_root"] = clean_path(a.out_root)
    import glob as _g                                                       # folders of crashed earlier sessions (older than a day) are removed
    for old in _g.glob(os.path.join(tempfile.gettempdir(), "gizpix_stage_*")):
        try:
            if old != STATE["stage"] and time.time() - os.path.getmtime(old) > 86400: shutil.rmtree(old, ignore_errors=True)
        except OSError: pass
    srv = make_server(a.port); url = f"http://127.0.0.1:{STATE['port']}/"; print(f"Gizpix UI: {url}   (Save puts results in {STATE['out_root']}; Ctrl+C stops)")
    if not a.no_open: threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nstopped")
    finally: shutil.rmtree(STATE["stage"], ignore_errors=True)
    return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
