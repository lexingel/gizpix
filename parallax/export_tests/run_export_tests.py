# SPDX-License-Identifier: AGPL-3.0-or-later
"""run_export_tests.py - checks the pix_parallax text exports in the real tools. Not part of selftest_all (needs Chrome or Edge, the internet for Phaser, and Tiled).
  python run_export_tests.py [--chrome PATH] [--tiled PATH]
Draws the dusk_hills preset into a temp folder, then:
  css     Chrome through Playwright (pip install playwright): at scroll 640 every layer is at -factor x 640 px, and with reduced motion on they stay still
  phaser  Chrome headless + Phaser 3.80.1 from cdnjs: the snippet runs and its canvas equals the pix_parallax preview pixel for pixel at two camera positions
  tiled   Tiled --export-map tmx: the exported JSON loads and keeps parallaxx / parallaxy
Prints one ok / FAIL / skipped line per test; exit 1 if any FAIL."""
import math, os, sys, re, json, base64, io, html, shutil, subprocess, tempfile, argparse, threading, http.server, functools
import numpy as np
from PIL import Image

H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(H))
import pix_parallax as p

CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "google-chrome", "chromium", "msedge"]
TILED = [r"C:\Program Files\Tiled\tiled.exe", "tiled"]


def find(c):
    return next((x for x in c if os.path.exists(x) or shutil.which(x)), None)


def dump(chrome, url, budget=8000):
    r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--window-size=640,360", f"--virtual-time-budget={budget}", "--dump-dom", url], capture_output=True, text=True, timeout=120, encoding="utf-8", errors="ignore")
    return r.stdout


def t_css(chrome, d, sp):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, "needs `pip install playwright` (it drives the installed Chrome; headless --dump-dom does not render scroll timelines reliably)"
    names = [os.path.splitext(L["file"])[0] for L in sp["layers"]]; css = p.export_text(sp, "css")
    f = os.path.join(d, "css_test.html")
    open(f, "w").write("<!doctype html><meta charset=utf-8><style>%sbody{margin:0}</style><div class=stage>%s</div><div id=sp style='height:10px'></div>" % (css, "".join('<div class="layer %s"></div>' % n for n in names)))
    probe = "Object.fromEntries(%s.map(n=>[n,+new DOMMatrix(getComputedStyle(document.querySelector('.layer.'+n)).transform).m41.toFixed(1)]))" % json.dumps(names)
    res = {}
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel="chrome", headless=True)
        for rm in ("no-preference", "reduce"):
            pg = br.new_page(viewport={"width": 640, "height": 360}, reduced_motion=rm); pg.goto("file:///" + f.replace(os.sep, "/"))
            pg.evaluate("document.getElementById('sp').style.width=(document.documentElement.clientWidth+1280)+'px'")
            pg.evaluate("document.documentElement.scrollLeft=640"); pg.wait_for_timeout(300); res[rm] = pg.evaluate(probe)
        br.close()
    want = {L["file"][:-4]: -round(640 * L["scroll"][0], 1) + 0.0 for L in sp["layers"]}
    ok = all(abs(res["no-preference"][n] - want[n]) < 0.6 for n in names) and all(v == 0 for v in res["reduce"].values())
    return ok, f"scroll 640: layers move by factor x 640 px; reduced motion keeps them still ({res['no-preference']})"


def t_phaser(chrome, d, sp):
    s = p.export_text(sp, "phaser"); pre = s.split("// preload()")[1].split("// create()")[0]; cre = s.split("// create()")[1].split("// update()")[0]; upd = s.split("// update()")[1].split("\n", 1)[1]
    page = ("<!doctype html><meta charset=utf-8><body style='margin:0'><script src='https://cdnjs.cloudflare.com/ajax/libs/phaser/3.80.1/phaser.min.js'></script><script>"
            "class S extends Phaser.Scene{preload(){" + pre + "}create(){" + cre + "}update(){" + upd + "}}"
            "const G=new Phaser.Game({type:Phaser.CANVAS,width:320,height:180,pixelArt:true,antialias:false,roundPixels:true,scene:S,parent:document.body,backgroundColor:'#000'});"
            "setTimeout(()=>{const sc=G.scene.scenes[0];const run=(x,y)=>{sc.cameras.main.scrollX=x;sc.cameras.main.scrollY=y;for(let i=0;i<3;i++)G.step(performance.now()+i*16,16)};"
            "run(0,0);run(0,0);run(0,0);const a=G.canvas.toDataURL();run(200,-10);const b=G.canvas.toDataURL();"
            "for(const [i,v] of [[0,a],[1,b]]){const t=document.createElement('textarea');t.id='png'+i;t.textContent=v;document.body.appendChild(t)}document.title='RESULT'},1500);</script>")
    open(os.path.join(d, "phaser_test.html"), "w").write(page)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(type("Q", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}), directory=d))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        out = dump(chrome, f"http://127.0.0.1:{srv.server_port}/phaser_test.html")
    finally:
        srv.shutdown()
    lay = [(L, p._rgba(L["path"])) for L in sp["layers"]]; res = []
    for k, (cx, cy) in enumerate(((0, 0), (200, -10))):
        m = re.search(r'<textarea id="png%d">(.*?)</textarea>' % k, out, re.S)
        if not m:
            return False, "no canvas (offline? Phaser could not load)"
        g = np.array(Image.open(io.BytesIO(base64.b64decode(html.unescape(m.group(1)).strip().split(",", 1)[1]))).convert("RGB"))
        e = p.frame_at(sp, lay, [int(math.floor(cx * L["scroll"][0] + 0.5)) for L, _ in lay], -cy)[..., :3]; res.append(round(float((g == e).all(-1).mean()), 4))
    return res == [1.0, 1.0], f"pixel match {res}"


def t_tiled(tiled, d, sp):
    j = os.path.join(d, "dusk.tmj"); open(j, "w").write(p.export_text(sp, "tiled")); o = os.path.join(d, "out.tmx")
    subprocess.run([tiled, "--export-map", "tmx", j, o], capture_output=True, timeout=120)
    if not os.path.exists(o):
        return False, "Tiled wrote no file"
    x = open(o).read(); ok = all(f'name="{os.path.splitext(L["file"])[0]}"' in x for L in sp["layers"]) and 'parallaxx="0.25"' in x and 'parallaxy="0.8"' in x
    return ok, re.search(r'tiledversion="([^"]*)"', x).group(1) if 'tiledversion' in x else ""


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument("--chrome"); ap.add_argument("--tiled"); a = ap.parse_args(argv)
    chrome, tiled = a.chrome or find(CHROME), a.tiled or find(TILED); d = tempfile.mkdtemp(); sp = p.load_spec(p.draw("dusk_hills", d, seed=3)); bad = 0
    for name, tool, fn in (("css", chrome, t_css), ("phaser", chrome, t_phaser), ("tiled", tiled, t_tiled)):
        if not tool:
            print(f"skipped {name} (tool not found)"); continue
        try:
            ok, info = fn(tool, d, sp)
        except Exception as e:
            ok, info = False, f"{type(e).__name__}: {e}"
        if ok is None:
            print(f"skipped {name}: {info}"); continue
        bad += not ok; print(("ok   " if ok else "FAIL ") + name + "  " + str(info)[:200])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
