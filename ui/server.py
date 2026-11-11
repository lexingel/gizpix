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
STATE = {"token": secrets.token_urlsafe(18), "out_root": os.path.join(os.getcwd(), "gizpix_out"), "stage": tempfile.mkdtemp(prefix="gizpix_stage_"), "made": set(), "port": 0}


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


def new_dir(root, name):
    """a fresh folder that did not exist before: results never land in or over anything already there"""
    root = clean_path(root or STATE["out_root"]); os.makedirs(root, exist_ok=True); name = re.sub(r"[^\w.-]+", "_", name or "result").strip("._") or "result"
    for i in range(1, 1000):
        d = os.path.join(root, name if i == 1 else f"{name}_{i}")
        try: os.mkdir(d); STATE["made"].add(d); return d
        except FileExistsError: continue
    raise Bad("could not make an output folder")


def run_tool(args, timeout=900):
    r = subprocess.run([sys.executable, GIZPIX, *args], capture_output=True, text=True, cwd=os.getcwd(), timeout=timeout)
    return {"command": shown(args), "code": r.returncode, "out": r.stdout.strip(), "err": r.stderr.strip()}


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
        r = run_tool(["fill_pinholes", *dst]); cmds.append(r["command"] + "   (edits only the copies in the new folder)")
        if r["code"]: raise Bad(r["err"] or r["out"])
    after = {d: counts(d) for d in dst}; keys = ("odd_px", "pinholes"); import numpy as np
    from PIL import Image
    rows = [{"name": os.path.basename(f), "original": f, "result": d, "w": Image.open(f).width, "h": Image.open(f).height, "changed": int((np.array(Image.open(f).convert("RGBA")) != np.array(Image.open(d).convert("RGBA"))).any(-1).sum()), **{k: {"before": before[f].get(k), "after": after[d].get(k)} for k in keys}} for f, d in zip(files, dst)]
    return {"out": out, "commands": cmds, "rows": rows, "totals": {**{k: {"before": sum(r[k]["before"] or 0 for r in rows), "after": sum(r[k]["after"] or 0 for r in rows)} for k in keys}, "changed": sum(r["changed"] for r in rows)}}


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
    return {"png": base64.b64encode(buf.getvalue()).decode(), "w": img.width, "h": img.height, "spec": spec_string(p), "command": shown(["pixdraw", "build", spec_string(p), "--style", p.get("style", "dark_fantasy")])}


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


def folder_glob_shown(tool, files, rest):
    """a runnable displayed command: TOOL folder/*.png REST (used when the frames share one folder)"""
    d = os.path.dirname(files[0])
    if len(files) < 3 or any(os.path.dirname(f) != d for f in files): return shown([tool, *files, *rest])
    return shown([tool, rel(d).replace(chr(92), "/") + "/*.png", *rest])


def job_pack(p):
    files = pngs(p["input"]); out = new_dir(p.get("out_root"), "pack"); name = re.sub(r"[^\w-]+", "_", p.get("name") or "sheet") or "sheet"; fps = str(float(p.get("fps", 12))); cmds = []
    sheet = run_tool(["make_sheet", os.path.join(out, name), *files, "--fps", fps]); cmds.append(folder_glob(sheet["command"], files))
    if sheet["code"]: raise Bad(sheet["err"] or sheet["out"])
    if p.get("gif", True) and len(files) > 1:
        g = run_tool(["preview_gif", os.path.join(out, name + ".gif"), files[0], *files, "--beat", "even", "--fps", fps, "--scale", str(int(p.get("scale", 3)))]); cmds.append(folder_glob(g["command"], files, still=True))
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


JOBS = {"clean": job_clean, "layer": job_layer, "draw/preview": job_draw_preview, "draw/save": job_draw_save, "hue": job_hue, "pack": job_pack, "lint": job_lint, "sample/damaged": job_sample_damaged}


def state():
    s = os.path.join(ROOT, "samples", "walk_frames"); sets = {}
    if os.path.isdir(s):
        for k in sorted(os.listdir(s)):
            for d in sorted(os.listdir(os.path.join(s, k))): sets.setdefault(k, []).append(os.path.join(s, k, d))
    from pixdraw import PRESETS, list_styles
    import gizpix
    return {"version": gizpix.__version__, "cwd": os.getcwd(), "out_root": STATE["out_root"], "sample_root": s if os.path.isdir(s) else "", "samples": sets, "buildings": sorted(PRESETS), "styles": list(list_styles())}


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
    if ext not in ("gif", "png", "json"): raise Bad("not a result file type")
    return open(p, "rb").read(), {"gif": "image/gif", "png": "image/png", "json": "application/json"}[ext]


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


class H(BaseHTTPRequestHandler):
    server_version = "gizpix-ui"
    def log_message(self, *a): pass
    def _ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]; origin = self.headers.get("Origin")
        return host in ("127.0.0.1", "localhost") and (not origin or urlparse(origin).hostname in ("127.0.0.1", "localhost"))
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)): body = json.dumps(body).encode()
        elif isinstance(body, str): body = body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
    def _auth(self, q): return secrets.compare_digest(self.headers.get("X-Gizpix-Token") or (q.get("t", [""])[0]), STATE["token"])
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if not self._ok(): return self._send(403, {"error": "forbidden host"})
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, open(os.path.join(WEB, "index.html"), encoding="utf8").read().replace("{{TOKEN}}", STATE["token"]), "text/html; charset=utf-8")
            if u.path.startswith("/static/"):
                f = os.path.normpath(os.path.join(WEB, u.path[len("/static/"):]))
                if not f.startswith(WEB) or not os.path.isfile(f): return self._send(404, {"error": "not found"})
                ct = {"css": "text/css", "js": "text/javascript", "svg": "image/svg+xml", "woff2": "font/woff2"}.get(f.rsplit(".", 1)[-1], "application/octet-stream")
                return self._send(200, open(f, "rb").read(), ct + ("; charset=utf-8" if ct.startswith("text") else ""))
            if not self._auth(q): return self._send(403, {"error": "bad token"})
            if u.path == "/api/state": return self._send(200, state())
            if u.path == "/api/ls": return self._send(200, listing(q.get("path", [""])[0]))
            if u.path == "/api/png": return self._send(200, png_bytes(q["path"][0], q.get("scale", ["1"])[0], q.get("crop", [""])[0] == "1"), "image/png")
            if u.path == "/api/diff": return self._send(200, diff_bytes(q["a"][0], q["b"][0], q.get("scale", ["1"])[0]), "image/png")
            if u.path == "/api/raw": body, ct = raw_file(q["path"][0]); return self._send(200, body, ct)
            if u.path == "/api/worn": return self._send(200, worn_bytes(q["base"][0], q["layer"][0], q.get("scale", ["1"])[0]), "image/png")
            return self._send(404, {"error": "not found"})
        except Bad as e: return self._send(400, {"error": str(e)})
        except Exception as e: return self._send(500, {"error": f"{type(e).__name__}: {e}"})
    def do_POST(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if not self._ok(): return self._send(403, {"error": "forbidden host"})
        if not self._auth(q): return self._send(403, {"error": "bad token"})
        try:
            n = int(self.headers.get("Content-Length") or 0); body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            if u.path == "/api/reveal": return self._send(200, reveal(body.get("path", "")))
            if u.path == "/api/pick-folder": return self._send(200, pick_folder(body.get("path", "")))
            if u.path == "/api/save": return self._send(200, save_result(body))
            if u.path == "/api/out-root":
                STATE["out_root"] = clean_path(body.get("path") or STATE["out_root"]); return self._send(200, {"out_root": STATE["out_root"]})
            job = u.path[len("/api/job/"):] if u.path.startswith("/api/job/") else None
            if job in JOBS:
                body["out_root"] = STATE["stage"]; return self._send(200, JOBS[job](body))      # runs only ever stage; Save copies to the output root
            return self._send(404, {"error": "unknown job"})
        except Bad as e: return self._send(400, {"error": str(e)})
        except KeyError as e: return self._send(400, {"error": f"missing field {e}"})
        except Exception as e: return self._send(500, {"error": f"{type(e).__name__}: {e}"})


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
    finally: srv.shutdown(); shutil.rmtree(t, ignore_errors=True); shutil.rmtree(stage, ignore_errors=True)
    print("ui selftest ok")


def main(argv):
    if argv[:1] == ["selftest"]: selftest(); return 0
    ap = argparse.ArgumentParser(prog="gizpix ui", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765); ap.add_argument("--no-open", action="store_true"); ap.add_argument("--out-root", help="where results are written (a new subfolder per run); default ./gizpix_out")
    a = ap.parse_args(argv)
    if a.out_root: STATE["out_root"] = clean_path(a.out_root)
    srv = make_server(a.port); url = f"http://127.0.0.1:{STATE['port']}/"; print(f"Gizpix UI: {url}   (Save puts results in {STATE['out_root']}; Ctrl+C stops)")
    if not a.no_open: threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nstopped")
    finally: shutil.rmtree(STATE["stage"], ignore_errors=True)
    return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
