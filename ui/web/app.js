// SPDX-License-Identifier: AGPL-3.0-or-later
// Gizpix UI. Plain JavaScript, no build step. Every request goes to this machine's own server; nothing leaves it.
(() => {
  const T = window.T, TOKEN = document.querySelector('meta[name="gizpix-token"]').content;
  const JOBS = ["clean", "layer", "draw", "recolor"];
  const S = { job: "layer", info: null, drawers: {} };

  // ---- small helpers --------------------------------------------------------------------------------------------------
  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || (v === false && !k.startsWith("aria-"))) continue;
      if (k === "class") e.className = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else if (v === true && !k.startsWith("aria-")) e.setAttribute(k, ""); else e.setAttribute(k, v);
    }
    for (const c of kids.flat(Infinity)) if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(c));
    return e;
  }
  const $ = (s, r = document) => r.querySelector(s);
  const join = (a, b) => a.replace(/[\\/]+$/, "") + "/" + b;
  const say = msg => { $("#live").textContent = ""; setTimeout(() => { $("#live").textContent = msg; }, 30); };
  async function api(path, body) {
    const r = await fetch(path, { method: body === undefined ? "GET" : "POST", headers: { "X-Gizpix-Token": TOKEN, "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
    const j = await r.json().catch(() => ({ error: "The server sent a reply this page cannot read." }));
    if (!r.ok) throw new Error(j.error || r.statusText);
    return j;
  }
  const q = p => new URLSearchParams({ t: TOKEN, ...p }).toString();
  const png = (path, scale = 1) => "/api/png?" + q({ path, scale });
  const thumb = path => h("div", { class: "thumb" }, h("img", { src: "/api/png?" + q({ path, scale: 1, crop: 1 }), alt: "" }));
  const median = a => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : 0; };
  const fmt = n => (n == null ? "–" : Number(n).toLocaleString("en-US"));
  const safe = t => (t || "").replace(/[^\w.-]+/g, "_").replace(/^[._]+|[._]+$/g, "");
  const short = p => { const c = S.info.cwd.replace(/\\/g, "/"), q = p.replace(/\\/g, "/"); return q.startsWith(c + "/") ? q.slice(c.length + 1) : p; };      // paths relative to where you started the UI
  const outName = () => (S.info.out_root.split(/[\\/]/).filter(Boolean).pop() || "gizpix_out");

  // drawn icons, one stroke weight
  const ICONS = { check: "M3 8.5l3.2 3.2L13 5", up: "M8 13V3M3.5 7.5L8 3l4.5 4.5", left: "M10 3L5 8l5 5", right: "M6 3l5 5-5 5", minus: "M3 8h10", plus: "M3 8h10M8 3v10" };
  function icon(name) {
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg"), p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    for (const [k, v] of Object.entries({ viewBox: "0 0 16 16", width: "16", height: "16", fill: "none", stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "square", "aria-hidden": "true" })) s.setAttribute(k, v);
    p.setAttribute("d", ICONS[name]); s.append(p); return s;
  }
  const slug = t => t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

  // ---- shared widgets -------------------------------------------------------------------------------------------------
  function pathField(label, get, set, onChange) {
    const id = "f-" + slug(label), input = h("input", { type: "text", id, value: get(), spellcheck: "false", autocomplete: "off" }), box = h("div");
    input.addEventListener("input", () => { set(input.value); onChange && onChange(); });
    const open = async start => {
      try {
        const d = await api("/api/ls?" + q({ path: start || input.value || "" }));
        const list = h("ul"); if (d.parent) list.append(h("li", {}, h("button", { type: "button", onclick: () => open(d.parent) }, icon("up"), " " + T.upOneFolder)));
        d.dirs.forEach(n => list.append(h("li", {}, h("button", { type: "button", onclick: () => open(join(d.path, n)) }, n))));
        if (!d.dirs.length) list.append(h("li", { class: "hint", style: "padding:8px 12px" }, T.folderEmpty));
        box.replaceChildren(h("div", { class: "picker" }, h("header", {}, h("code", { title: d.path }, d.path), h("button", { type: "button", class: "btn small", onclick: () => box.replaceChildren() }, T.closePicker)), list,
          h("div", { class: "foot" }, h("span", {}, T.pngCount(d.pngs.length)), h("button", { type: "button", class: "btn small primary", onclick: () => { input.value = d.path; set(d.path); box.replaceChildren(); onChange && onChange(); } }, T.chooseFolder))));
      } catch (e) { box.replaceChildren(h("p", { class: "hint" }, e.message)); }
    };
    const pick = h("button", { type: "button", class: "btn fit", onclick: async e => {
      const b = e.currentTarget; b.disabled = true; b.textContent = T.picking;
      try { const d = await api("/api/pick-folder", { path: input.value }); if (d.path) { input.value = d.path; set(d.path); onChange && onChange(); } } catch (err) { box.replaceChildren(h("p", { class: "hint" }, err.message)); }
      b.disabled = false; b.textContent = T.pickFolder;
    } }, T.pickFolder); pick.title = T.pickTip;
    return h("div", { class: "field" }, h("label", { for: id }, label), h("div", { class: "row" }, input, pick, h("button", { type: "button", class: "btn fit", title: T.browseTip, onclick: () => open() }, T.browse)), box);
  }
  function copyButton(getText) {
    const b = h("button", { type: "button", class: "btn small" }, T.copy);
    b.addEventListener("click", async () => { try { await navigator.clipboard.writeText(getText()); b.textContent = T.copied; say(T.copied); setTimeout(() => (b.textContent = T.copy), 1500); } catch { b.textContent = "Select the text above"; } });
    return b;
  }
  function commandBox(cmds, outPath, savedPath, planned) {
    const text = cmds.map(c => c.split(outPath).join(savedPath || planned || T.resultFolder).split("\\").join("/")).join("\n");
    return h("section", { class: "panel" }, h("h2", {}, T.command), h("pre", { class: "cmd", tabindex: "0" }, text), h("div", { class: "row" }, copyButton(() => text)), h("p", { class: "hint", style: "margin:8px 0 0" }, T.commandHint));
  }
  function savePanel(st, { ready, defaultName, extra }) {
    const nameId = "save-name", name = h("input", { type: "text", id: nameId, value: st.name || defaultName, spellcheck: "false" });
    name.addEventListener("input", () => { st.name = name.value; render(); });      // the command and the folder hint follow the name
    const btn = h("button", { type: "button", class: "btn primary block", disabled: !ready || st.saving }, st.saving ? T.saving : T.saveButton);
    btn.addEventListener("click", async () => {
      st.saving = true; st.error = null; render();
      try { const r = await api("/api/save", { from: st.result.out, name: st.name || defaultName }); st.saved = r.out; say(T.saved); } catch (e) { st.error = e.message; }
      st.saving = false; render();
    });
    return h("section", { class: "panel save" }, h("h2", {}, T.save), extra, h("div", { class: "field" }, h("label", { for: nameId }, T.nameLabel), name),
      h("p", { class: "hint", style: "margin:0 0 8px" }, T.saveCopies(outName() + "/" + (safe(st.name) || defaultName))), btn, h("p", {}, T.originalsUntouched),
      st.saved ? h("p", { class: "saved" }, T.saved + " ", h("code", {}, st.saved), " ", h("button", { type: "button", class: "btn small", onclick: () => api("/api/reveal", { path: st.saved }).catch(e => (st.error = e.message)) }, T.openFolder)) : null);
  }
  // once a result exists the load form folds into one line, so the review (previews and the sheet) sits in the first viewport
  function loadOrSummary(st, full, summary) {
    if (!st.result || st.editLoad) return full;
    return h("section", { class: "panel", style: "display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap" }, h("div", { style: "min-width:0" }, h("h2", { style: "margin:0 0 4px" }, T.load), h("span", { class: "hint", style: "overflow-wrap:anywhere" }, summary)),
      h("button", { type: "button", class: "btn small", onclick: () => { st.editLoad = true; render(); } }, T.change));
  }
  const errorBox = st => st.error ? h("div", { class: "notice", role: "alert" }, h("h3", {}, T.errorTitle), h("p", {}, st.error), h("p", {}, T.errorTry)) : null;
  const empty = (title, text) => h("div", { class: "empty" }, h("b", {}, title), text);
  const busy = text => h("div", { class: "busy", role: "status" }, text);

  function zoomFor(st, frameW, n, avail) {
    let fit = 1; for (let k = 4; k >= 1; k--) if (n * (frameW * k + 2) + 8 * (n - 1) <= avail - 4) { fit = k; break; }
    if (fit < 2 && frameW * 2 + 2 <= avail - 4) fit = 2;      // narrow windows: never below 2x, the plates wrap instead
    return { z: st.zoom || fit, fit };
  }
  function toolsRow(st, count, fit, onChange) {
    const id = "scrub";
    const range = h("input", { type: "range", id, min: 0, max: Math.max(0, count - 1), value: st.frame, "aria-label": T.scrub }), out = h("output", { for: id }, String(st.frame));
    range.addEventListener("input", () => { st.frame = +range.value; out.textContent = range.value; });      // the number follows the thumb; the previews update when it is released, so a drag is never interrupted
    range.addEventListener("change", () => onChange());
    const step = d => () => { st.frame = Math.max(0, Math.min(count - 1, st.frame + d)); onChange(); };
    const z = st.zoom || fit;
    return h("div", { class: "tools" },
      h("div", { class: "scrub" }, h("label", { for: id, style: "margin:0" }, T.frame), h("button", { type: "button", id: "prev", class: "btn small icon", "aria-label": T.prev, onclick: step(-1) }, icon("left")), range, h("button", { type: "button", id: "next", class: "btn small icon", "aria-label": T.next, onclick: step(1) }, icon("right")), out),
      h("div", { class: "zoom" }, T.zoom, h("button", { type: "button", id: "zoom-out", class: "btn small icon", "aria-label": T.zoom + " −", onclick: () => { st.zoom = Math.max(1, z - 1); onChange(); } }, icon("minus")), h("output", {}, z + "×" + (!st.zoom ? " " + T.zoomFit : "")),
        h("button", { type: "button", id: "zoom-in", class: "btn small icon", "aria-label": T.zoom + " +", onclick: () => { st.zoom = Math.min(6, z + 1); onChange(); } }, icon("plus"))));
  }
  const plate = (label, src, w, h_, z) => h("figure", { class: "plate" }, h("figcaption", {}, label), h("div", { class: "ground" }, h("img", { src, width: w * z, height: h_ * z, alt: label })));

  // exposure sheet: frames are columns
  function exposure({ frames, sel, onSelect, rows, checked }) {
    const head = h("tr", {}, h("th", { scope: "col" }, T.rowFrame), ...frames.map((f, i) => h("th", { scope: "col", class: i === sel ? "sel" : "", "aria-current": i === sel ? "true" : null }, h("button", { type: "button", id: "col-" + i, onclick: () => onSelect(i), "aria-label": T.frame + " " + f }, f))));
    const body = rows.map(r => h("tr", {}, h("th", { scope: "row" }, r.label), ...r.cells.map((c, i) => h("td", { class: (i === sel ? "sel " : "") + (r.cls || "") }, c))));
    return h("div", {}, h("div", { class: "sheetwrap" }, h("table", { class: "sheet" }, h("caption", { class: "sr" }, T.sheet), h("thead", {}, head), h("tbody", {}, body))),
      h("div", { class: "legend" }, h("span", {}, h("span", { class: "pencil swatch", "aria-hidden": "true" }), " " + T.needsLook), checked ? h("span", { id: "checkedCount" }, T.checkedCount(checked.size, frames.length)) : null));
  }
  const pencil = (txt, bad) => bad ? h("span", { class: "pencil" }, txt) : txt;
  function checkCell(st, i, n) {
    const c = h("input", { type: "checkbox", id: "chk-" + i, checked: st.checked.has(i), "aria-label": T.rowChecked + " " + i });
    c.addEventListener("change", () => { c.checked ? st.checked.add(i) : st.checked.delete(i); render(); });      // the Save line and the count follow the ticks
    return c;
  }

  // ---- job: cut outfit layer -------------------------------------------------------------------------------------------
  const L = { base: "", outfit: "", opt: { solid: true, drop_skin: "auto", bits: true, drop_parts: true, outline: false }, result: null, busy: false, error: null, frame: 0, zoom: 0, checked: new Set(), name: "robe", saved: null };
  S.drawers.layer = function () {
    const sampleId = "ls", sel = h("select", { id: sampleId }, T.layerSamples.map((s, i) => h("option", { value: i }, s.label)));
    const root = S.info.sample_root;
    const loadSample = () => { const s = T.layerSamples[+sel.value]; L.base = join(root, s.base); L.outfit = join(root, s.outfit); L.result = null; L.saved = null; L.checked = new Set(); L.name = s.outfit.split("/")[0].replace("drobe", "dark_robe"); say(T.useSample); render(); };
    const load = h("section", {}, h("h2", {}, T.load),
      root ? h("div", { class: "field" }, h("label", { for: sampleId }, T.sample), h("div", { class: "row" }, sel, h("button", { type: "button", class: "btn fit", onclick: loadSample }, T.useSample))) : null,
      pathField(T.baseFolder, () => L.base, v => (L.base = v), flowOnly), pathField(T.outfitFolder, () => L.outfit, v => (L.outfit = v), flowOnly), h("p", { class: "hint" }, T.sameNames));
    const run = async () => {
      if (!L.base || !L.outfit) { L.error = T.chooseBoth; return render(); }
      L.editLoad = false; L.busy = true; L.error = null; L.saved = null; L.checked = new Set(); L.frame = 0; render();
      try { L.result = await api("/api/job/layer", { base: L.base, outfit: L.outfit, name: L.name || "layer", options: L.opt }); say(L.result.summary); } catch (e) { L.error = e.message; L.result = null; }
      L.busy = false; render();
    };
    const o = L.opt, chk = (label, key, hint) => h("label", { class: "check" }, h("input", { type: "checkbox", checked: o[key], onchange: e => (o[key] = e.target.checked) }), h("span", {}, label, hint ? h("small", {}, hint) : null));
    const skin = h("select", { id: "skin", onchange: e => (o.drop_skin = e.target.value) }, [["auto", T.skinAuto], ["near", T.skinNear], ["none", T.skinOff]].map(([v, t]) => h("option", { value: v, selected: o.drop_skin === v }, t)));
    const options = h("section", { class: "panel" }, h("h2", {}, T.options), chk(T.optSolid, "solid", T.optSolidHint), h("div", { class: "field" }, h("label", { for: "skin" }, T.optSkin), skin), chk(T.optBits, "bits"), chk(T.optParts, "drop_parts"), chk(T.optOutline, "outline"),
      h("button", { type: "button", class: "btn block" + (L.result ? "" : " primary"), disabled: L.busy, onclick: run }, L.busy ? T.cutting : T.cutLayer));
    let review;
    if (L.busy) review = busy(T.cutting);
    else if (!L.result) review = empty(T.nothingYet, T.emptyLayer);
    else {
      const r = L.result, files = r.files, n = files.length, f = files[Math.min(L.frame, n - 1)], work = $("#view .work") || $("#view"), avail = (work && work.clientWidth) || 900, { z, fit } = zoomFor(L, f.w, 3, avail);
      const px = files.map(x => x.opaque), med = median(px), odd = px.map(v => med && Math.abs(v - med) > 0.25 * med), dark = r.notes.some(t => /dark skin/i.test(t));
      review = h("section", {}, h("h2", {}, T.review),
        h("div", { class: "plates" }, plate(T.base, png(join(L.base, f.name), z), f.w, f.h, z), plate(T.outfit, png(join(L.outfit, f.name), z), f.w, f.h, z), plate(T.worn, "/api/worn?" + q({ base: join(L.base, f.name), layer: f.path, scale: z }), f.w, f.h, z)),
        toolsRow(L, n, fit, render),
        exposure({ frames: files.map((_, i) => i), sel: L.frame, onSelect: i => { L.frame = i; render(); }, checked: L.checked, rows: [
          { label: T.layer, cells: files.map(x => thumb(x.path)) },
          { label: T.rowLayerPx, cls: "num", cells: px.map((v, i) => pencil(fmt(v), odd[i])) },
          { label: T.rowLooksAt, cells: odd.map(b => (b ? T.needsLook : T.looksFine)) },
          { label: T.rowChecked, cells: files.map((_, i) => checkCell(L, i, n)) }] }),
        (dark || odd.some(Boolean)) ? h("div", { class: "notice", role: "note", style: "margin-top:12px" }, h("h3", {}, T.warningTitle), dark ? h("p", {}, T.warnDark) : null, odd.some(Boolean) ? h("p", {}, T.warnDifferent(odd.filter(Boolean).length), " ", ...odd.flatMap((b, i) => b ? [h("button", { type: "button", class: "btn small", onclick: () => { L.frame = i; render(); } }, T.frame + " " + i)] : [])) : null) : null);
    }
    const side = [options];
    if (L.result) {
      const px = L.result.files.map(x => x.opaque);
      side.push(h("section", { class: "panel" }, h("h2", {}, T.results), h("dl", { class: "stats" }, h("dt", {}, T.totalLayer), h("dd", {}, fmt(px.reduce((a, b) => a + b, 0))), h("dt", {}, T.framesStat), h("dd", {}, px.length + " of " + L.result.files[0].w + "×" + L.result.files[0].h)),
        L.result.summary ? h("p", { class: "hint", style: "margin:8px 0 0" }, L.result.summary) : null));
    }
    const flaggedL = L.result ? L.result.files.map((x, i) => i).filter(i => { const px = L.result.files.map(y => y.opaque), m = median(px); return m && Math.abs(px[i] - m) > 0.25 * m && !L.checked.has(i); }) : [];
    side.push(savePanel(L, { ready: !!L.result, defaultName: "robe", extra: flaggedL.length ? h("p", { class: "flag" }, T.unchecked(flaggedL.length)) : null }));
    if (L.result) side.push(commandBox(L.result.commands, L.result.out, L.saved, outName() + "/" + (safe(L.name) || "robe")));
    return { work: [loadOrSummary(L, load, short(L.base) + "  +  " + short(L.outfit)), errorBox(L), review], side, step: L.saved ? 3 : L.result ? 2 : (L.base && L.outfit) ? 1 : 0, done: [!!(L.base && L.outfit), !!L.result, !!L.result, !!L.saved] };
  };

  // ---- job: clean & measure --------------------------------------------------------------------------------------------
  const C = { input: "", opt: { speck_fix: true, fill_pinholes: true }, result: null, busy: false, error: null, frame: 0, zoom: 0, checked: new Set(), name: "cleaned", saved: null, sampleMsg: "" };
  S.drawers.clean = function () {
    const sample = async () => { C.busy = true; C.error = null; render(); try { const r = await api("/api/job/sample/damaged", {}); C.input = r.out; C.result = null; C.saved = null; C.sampleMsg = T.cleanSampleDone; } catch (e) { C.error = e.message; } C.busy = false; render(); };
    const load = h("section", {}, h("h2", {}, T.load), pathField(T.inputFolder, () => C.input, v => (C.input = v), flowOnly), h("div", { class: "row" }, h("button", { type: "button", class: "btn fit", onclick: sample }, T.cleanSample)), C.sampleMsg ? h("p", { class: "hint" }, C.sampleMsg) : null);
    const run = async () => {
      if (!C.input) { C.error = T.chooseOne; return render(); }
      C.editLoad = false; C.busy = true; C.error = null; C.saved = null; C.checked = new Set(); C.frame = 0; render();
      try { C.result = await api("/api/job/clean", { input: C.input, ...C.opt }); say(T.review); } catch (e) { C.error = e.message; C.result = null; }
      C.busy = false; render();
    };
    const o = C.opt, chk = (label, key) => h("label", { class: "check" }, h("input", { type: "checkbox", checked: o[key], onchange: e => (o[key] = e.target.checked) }), h("span", {}, label));
    const options = h("section", { class: "panel" }, h("h2", {}, T.options), chk(T.optSpeck, "speck_fix"), chk(T.optPinholes, "fill_pinholes"), h("button", { type: "button", class: "btn block" + (C.result ? "" : " primary"), disabled: C.busy, onclick: run }, C.busy ? T.repairing : T.runClean));
    let review;
    if (C.busy) review = busy(T.repairing); else if (!C.result) review = empty(T.nothingYet, T.emptyClean);
    else {
      const rows = C.result.rows, n = rows.length, r = rows[Math.min(C.frame, n - 1)], work = $("#view .work"), avail = (work && work.clientWidth) || 900;
      const w = r.w, hh = r.h, { z, fit } = zoomFor(C, w, 3, avail);
      const bad = x => (x.odd_px.after || 0) > 9 || (x.pinholes.after || 0) > 0, badAfter = rows.map(bad), pair = (x, k) => fmt(x[k].before) + " → " + fmt(x[k].after);
      review = h("section", {}, h("h2", {}, T.review),
        h("div", { class: "plates" }, plate(T.original, png(r.original, z), w, hh, z), plate(T.cleaned, png(r.result, z), w, hh, z), plate(T.changed, "/api/diff?" + q({ a: r.original, b: r.result, scale: z }), w, hh, z)),
        toolsRow(C, n, fit, render),
        exposure({ frames: rows.map((_, i) => i), sel: C.frame, onSelect: i => { C.frame = i; render(); }, checked: C.checked, rows: [
          { label: T.rowRepaired, cls: "num", cells: rows.map(x => fmt(x.changed)) },
          { label: T.rowOdd, cls: "num", cells: rows.map(x => pencil(pair(x, "odd_px"), (x.odd_px.after || 0) > 9)) },
          { label: T.rowPinholes, cls: "num", cells: rows.map(x => pencil(pair(x, "pinholes"), (x.pinholes.after || 0) > 0)) },
          { label: T.rowLooksAt, cells: badAfter.map(b => (b ? T.needsLook : T.looksFine)) },
          { label: T.rowChecked, cells: rows.map((_, i) => checkCell(C, i, n)) }] }), h("p", { class: "hint", style: "margin:8px 0 0" }, T.cleanLegend));
    }
    const side = [options];
    if (C.result) { const t = C.result.totals; side.push(h("section", { class: "panel" }, h("h2", {}, T.results), h("dl", { class: "stats" }, h("dt", {}, T.totalChanged), h("dd", {}, fmt(t.changed)), h("dt", {}, T.totalOdd), h("dd", {}, fmt(t.odd_px.before) + " → " + fmt(t.odd_px.after)), h("dt", {}, T.totalPinholes), h("dd", {}, fmt(t.pinholes.before) + " → " + fmt(t.pinholes.after))))); }
    const flaggedC = C.result ? C.result.rows.map((x, i) => i).filter(i => { const x = C.result.rows[i]; return ((x.odd_px.after || 0) > 9 || (x.pinholes.after || 0) > 0) && !C.checked.has(i); }) : [];
    side.push(savePanel(C, { ready: !!C.result, defaultName: "cleaned", extra: flaggedC.length ? h("p", { class: "flag" }, T.unchecked(flaggedC.length)) : null }));
    if (C.result) side.push(commandBox(C.result.commands, C.result.out, C.saved, outName() + "/" + (safe(C.name) || "cleaned")));
    return { work: [loadOrSummary(C, load, short(C.input)), errorBox(C), review], side, step: C.saved ? 3 : C.result ? 2 : C.input ? 1 : 0, done: [!!C.input, !!C.result, !!C.result, !!C.saved] };
  };

  // ---- job: draw buildings ---------------------------------------------------------------------------------------------
  const D = { type: "inn", proj: "iso", style: "dark_fantasy", floors: 2, wing: false, dormers: 0, lantern: false, frames: 1, scale: 3, preview: null, styles: {}, busy: false, error: null, name: "", saved: null, result: null, timer: null, seq: 0 };
  async function drawRefresh() {
    const seq = ++D.seq, base = { type: D.type, proj: D.proj, floors: D.floors, wing: D.wing, dormers: D.dormers, lantern: D.lantern };
    D.busy = true; D.error = null; render();
    try {
      const main = await api("/api/job/draw/preview", { ...base, style: D.style, scale: 4 }); if (seq !== D.seq) return; D.preview = main;
      const others = await Promise.all(S.info.styles.map(s => api("/api/job/draw/preview", { ...base, style: s, scale: 2 }).then(r => [s, r]))); if (seq !== D.seq) return; D.styles = Object.fromEntries(others);
    } catch (e) { if (seq === D.seq) { D.error = e.message; D.preview = null; D.styles = {}; } }
    if (seq === D.seq) { D.busy = false; render(); }
  }
  const drawSoon = () => { clearTimeout(D.timer); D.timer = setTimeout(drawRefresh, 250); };
  S.drawers.draw = function () {
    if (!D.preview && !D.busy && !D.error) setTimeout(drawRefresh, 0);
    const sel = (id, label, opts, key, labels) => h("div", { class: "field" }, h("label", { for: id }, label), h("select", { id, onchange: e => { D[key] = e.target.value; D.saved = null; drawSoon(); } }, opts.map(o => h("option", { value: o, selected: D[key] === o }, labels ? labels[o] : o.replace("_", " ")))));
    const num = (id, label, key, min, max) => h("div", { class: "field" }, h("label", { for: id }, label), h("input", { type: "number", id, min, max, value: D[key], onchange: e => { D[key] = Math.max(min, Math.min(max, +e.target.value || 0)); D.saved = null; drawSoon(); } }));
    const chk = (label, key) => h("label", { class: "check" }, h("input", { type: "checkbox", checked: D[key], onchange: e => { D[key] = e.target.checked; D.saved = null; drawSoon(); } }), h("span", {}, label));
    const controls = h("section", { class: "panel" }, h("h2", {}, T.drawSettings),
      h("div", { class: "row" }, sel("dt", T.drawType, S.info.buildings, "type"), sel("dv", T.drawView, ["iso", "top", "side"], "proj", T.views), sel("ds", T.drawStyle, S.info.styles, "style")),
      h("div", { class: "row" }, num("df", T.drawFloors, "floors", 1, 6), num("dd", T.drawDormers, "dormers", 0, 4), h("div", { class: "fit", style: "align-self:end" }, chk(T.drawWing, "wing"), chk(T.drawLantern, "lantern"))));
    const styleCell = s => { const d = D.styles[s]; return h("td", { class: s === D.style ? "sel" : "" }, d ? h("button", { type: "button", class: "pick", "aria-pressed": s === D.style, onclick: () => { D.style = s; D.saved = null; drawSoon(); } },
      h("img", { src: "data:image/png;base64," + d.png, width: d.w * 2, height: d.h * 2, alt: "", style: "image-rendering:pixelated" }), h("span", { class: "num" }, s.replace("_", " "))) : "…"); };
    let review;
    if (D.error) review = null; else if (!D.preview) review = busy(T.previewing);
    else {
      const p = D.preview;
      review = h("section", {}, h("h2", {}, T.review), h("div", { class: "plates" }, h("figure", { class: "plate" }, h("figcaption", {}, D.type.replace("_", " ") + " · " + T.views[D.proj] + " · " + D.style.replace("_", " ")), h("div", { class: "ground" }, h("img", { src: "data:image/png;base64," + p.png, width: p.w * 4, height: p.h * 4, alt: D.type })))),
        h("div", { class: "styles", style: "margin-top:20px" }, h("h3", {}, T.drawStyles), h("div", { class: "sheetwrap" }, h("table", { class: "sheet" }, h("tbody", {}, h("tr", {}, S.info.styles.map(styleCell)))))));
    }
    const save = async () => {
      D.saving = true; D.error = null; render();
      try { const r = await api("/api/job/draw/save", { type: D.type, proj: D.proj, floors: D.floors, wing: D.wing, dormers: D.dormers, lantern: D.lantern, style: D.style, frames: D.frames, scale: D.scale, name: D.name || D.type });
        D.result = r; const s = await api("/api/save", { from: r.out, name: D.name || D.type }); D.saved = s.out; say(T.saved); } catch (e) { D.error = e.message; }
      D.saving = false; render();
    };
    const sv = h("section", { class: "panel save" }, h("h2", {}, T.save),
      h("div", { class: "row" }, num("dfr", T.drawFrames, "frames", 1, 12), num("dsc", T.drawScale, "scale", 1, 8)),
      h("div", { class: "field" }, h("label", { for: "dn" }, T.nameLabel), h("input", { type: "text", id: "dn", value: D.name || D.type, oninput: e => { D.name = e.target.value; render(); } })),
      h("p", { class: "hint", style: "margin:0 0 8px" }, T.saveCopies(outName() + "/" + (safe(D.name) || D.type))), h("button", { type: "button", class: "btn primary block", disabled: !D.preview || D.saving, onclick: save }, D.saving ? T.saving : T.saveButton), h("p", {}, T.originalsUntouched),
      D.saved ? h("p", { class: "saved" }, T.saved + " ", h("code", {}, D.saved), " ", h("button", { type: "button", class: "btn small", onclick: () => api("/api/reveal", { path: D.saved }).catch(() => {}) }, T.openFolder)) : null);
    const side = [sv]; if (D.preview) side.push(h("section", { class: "panel" }, h("h2", {}, T.command), h("pre", { class: "cmd", tabindex: "0" }, D.preview.command), h("div", { class: "row" }, copyButton(() => D.preview.command))));
    return { work: [controls, errorBox(D), review], side, step: D.saved ? 3 : D.preview ? 2 : 1, done: [true, true, !!D.preview, !!D.saved] };
  };

  // ---- job: recolour & pack --------------------------------------------------------------------------------------------
  const R = { mode: "recolor", input: "", hue: 0, sat: 1, val: 1, range: "", name: "sheet", fps: 12, gif: true, scale: 3, result: null, busy: false, error: null, frame: 0, zoom: 0, checked: new Set(), saved: null, saveName: "" };
  S.drawers.recolor = function () {
    const mode = h("div", { class: "field" }, h("label", {}, T.rcMode), h("div", { class: "seg", role: "group", "aria-label": T.rcMode }, [["recolor", T.rcRecolor], ["pack", T.rcPack]].map(([m, t]) => h("button", { type: "button", id: "mode-" + m, "aria-pressed": R.mode === m, onclick: () => { R.mode = m; R.result = null; R.saved = null; R.error = null; R.stale = false; render(); } }, t))));
    const load = h("section", {}, h("h2", {}, T.load), pathField(T.inputFolder, () => R.input, v => (R.input = v), flowOnly));
    const run = async () => {
      if (!R.input) { R.error = T.chooseOne; return render(); }
      R.editLoad = false; R.stale = false; R.busy = true; R.error = null; R.saved = null; R.checked = new Set(); R.frame = 0; render();
      try { R.result = R.mode === "recolor" ? await api("/api/job/hue", { input: R.input, hue: R.hue, sat: R.sat, val: R.val, range: R.range }) : await api("/api/job/pack", { input: R.input, name: R.name, fps: R.fps, gif: R.gif, scale: R.scale }); say(T.review); } catch (e) { R.error = e.message; R.result = null; }
      R.busy = false; render();
    };
    const dirty = () => { if (!R.result) return; R.stale = true; const n = document.getElementById("stale-note"), b = document.getElementById("run-btn"), sv = document.querySelector(".save .btn.primary"); if (n) n.hidden = false; if (b) b.classList.add("primary"); if (sv) sv.disabled = true; };
    const sld = (id, label, key, min, max, step) => { const out = h("output", { class: "num", for: id }, String(R[key])); return h("div", { class: "field" }, h("label", { for: id }, label, " ", out), h("input", { type: "range", id, min, max, step, value: R[key], oninput: e => { R[key] = +e.target.value; out.textContent = String(R[key]); dirty(); } })); };
    const staleNote = h("p", { class: "hint", id: "stale-note", hidden: !R.stale, role: "status" }, T.staleNote);
    const opts = R.mode === "recolor"
      ? h("section", { class: "panel" }, h("h2", {}, T.options), sld("hu", T.hue, "hue", -180, 180, 1), sld("sa", T.sat, "sat", 0, 2, 0.05), sld("va", T.val, "val", 0, 2, 0.05),
          h("div", { class: "field" }, h("label", { for: "rg" }, T.range), h("input", { type: "text", id: "rg", value: R.range, placeholder: "0.55,0.72", oninput: e => { R.range = e.target.value; dirty(); } }), h("small", {}, T.rangeHint)),
          staleNote, h("button", { type: "button", id: "run-btn", class: "btn block" + (R.result && !R.stale ? "" : " primary"), disabled: R.busy, onclick: run }, R.busy ? T.previewing : T.recolorBtn))
      : h("section", { class: "panel" }, h("h2", {}, T.options), h("div", { class: "field" }, h("label", { for: "pn" }, T.packName), h("input", { type: "text", id: "pn", value: R.name, oninput: e => { R.name = e.target.value; dirty(); } })),
          h("div", { class: "field" }, h("label", { for: "pf" }, T.packFps), h("input", { type: "number", id: "pf", min: 1, max: 60, value: R.fps, onchange: e => { R.fps = +e.target.value || 12; dirty(); } })),
          h("label", { class: "check" }, h("input", { type: "checkbox", checked: R.gif, onchange: e => { R.gif = e.target.checked; dirty(); } }), h("span", {}, T.packGif)),
          staleNote, h("button", { type: "button", id: "run-btn", class: "btn block" + (R.result && !R.stale ? "" : " primary"), disabled: R.busy, onclick: run }, R.busy ? T.previewing : T.packBtn));
    let review;
    if (R.busy) review = busy(T.previewing);
    else if (!R.result) review = empty(T.nothingYet, T.emptyRecolor);
    else if (R.mode === "recolor") {
      const rows = R.result.rows, n = rows.length, r = rows[Math.min(R.frame, n - 1)], work = $("#view .work"), avail = (work && work.clientWidth) || 900;
      const w = r.w, hh = r.h, { z, fit } = zoomFor(R, w, 2, avail);
      review = h("section", {}, h("h2", {}, T.review), h("div", { class: "plates" }, plate(T.before, png(r.original, z), w, hh, z), plate(T.after, png(r.result, z), w, hh, z)), toolsRow(R, n, fit, render),
        exposure({ frames: rows.map((_, i) => i), sel: R.frame, onSelect: i => { R.frame = i; render(); }, checked: R.checked, rows: [
          { label: T.before, cells: rows.map(x => thumb(x.original)) }, { label: T.after, cells: rows.map(x => thumb(x.result)) },
          { label: T.rowChecked, cells: rows.map((_, i) => checkCell(R, i, n)) }] }));
    } else {
      const gif = R.result.files.find(f => f.endsWith(".gif"));
      const png0 = R.result.files.find(f => f.endsWith(".png")), i = R.result.info || {}, raw = f => "/api/raw?" + q({ path: R.result.out + "/" + f });
      review = h("section", {}, h("h2", {}, T.packResult), h("p", { class: "num" }, T.packStats(i.frames, i.w, i.h, i.fps)),
        gif ? h("figure", { class: "gifbox" }, h("img", { src: raw(gif), alt: T.packGifCap }), h("figcaption", {}, T.packGifCap)) : null,
        png0 ? h("figure", { class: "gifbox", style: "margin-top:12px" }, h("img", { src: raw(png0), alt: T.packSheetCap }), h("figcaption", {}, T.packSheetCap)) : null,
        h("ul", {}, R.result.files.map(f => h("li", {}, h("span", { class: "num" }, f), " ", f.endsWith(".json") ? T.packJsonNote : ""))));
    }
    const side = [h("section", { class: "panel" }, mode), opts];
    side.push(savePanel({ get name() { return R.saveName; }, set name(v) { R.saveName = v; }, get result() { return R.result; }, get saved() { return R.saved; }, set saved(v) { R.saved = v; }, get saving() { return R.saving; }, set saving(v) { R.saving = v; }, get error() { return R.error; }, set error(v) { R.error = v; } }, { ready: !!R.result && !R.stale, defaultName: R.mode === "pack" ? "sheet" : "recoloured" }));
    if (R.result) side.push(commandBox(R.result.commands, R.result.out, R.saved, outName() + "/" + (safe(R.saveName) || (R.mode === "pack" ? "sheet" : "recoloured"))));
    return { work: [loadOrSummary(R, load, (R.mode === "pack" ? T.rcPack : T.rcRecolor) + " · " + short(R.input)), errorBox(R), review], side, step: R.saved ? 3 : R.result ? 2 : R.input ? 1 : 0, done: [!!R.input, !!R.result, !!R.result, !!R.saved] };
  };

  // ---- frame ------------------------------------------------------------------------------------------------------------
  const flowOnly = () => { const v = S.drawers[S.job](); drawFlow(v); };
  function drawFlow(v) {
    $("#flow").replaceChildren(...T.steps.map((s, i) => h("li", { "data-state": v.done[i] && i !== v.step ? "done" : "todo", "aria-current": i === v.step ? "step" : null }, h("b", {}, String(i + 1), v.done[i] && i !== v.step ? icon("check") : null), s)));
  }
  function render() {
    const active = document.activeElement, keep = active && active.id, pos = active && active.selectionStart;
    $("#title").textContent = T.jobs[S.job].title; $("#intro").textContent = T.jobs[S.job].intro; document.title = T.jobs[S.job].title + " · Gizpix";
    $("#jobs").replaceChildren(...JOBS.map((j, i) => h("li", {}, h("button", { type: "button", class: "job", "aria-current": j === S.job ? "page" : null, onclick: () => { S.job = j; render(); $("#main").focus(); } }, h("span", { class: "n", title: "Key " + (i + 1) }, String(i + 1)), T.jobs[j].name))));
    const v = S.drawers[S.job]();
    drawFlow(v);
    $("#view").replaceChildren(h("div", { class: "cols" }, h("div", { class: "work" }, v.work), h("div", { class: "side" }, v.side)));
    if (keep) { const e = document.getElementById(keep); if (e) { e.focus(); if (pos != null && e.setSelectionRange) try { e.setSelectionRange(pos, pos); } catch {} } }
  }
  document.addEventListener("keydown", e => {
    const t = e.target, typing = t && (t.tagName === "INPUT" && t.type !== "checkbox" && t.type !== "range" || t.tagName === "SELECT" || t.tagName === "TEXTAREA");
    if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key >= "1" && e.key <= "4") { S.job = JOBS[+e.key - 1]; render(); }
    else if (e.key === "ArrowLeft" || e.key === "ArrowRight") { const st = { layer: L, clean: C, recolor: R }[S.job]; if (st && st.result) { st.frame = Math.max(0, st.frame + (e.key === "ArrowRight" ? 1 : -1)); render(); } }
  });
  let rz; window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => { if ({ layer: L, clean: C, recolor: R }[S.job]?.result) render(); }, 150); });
  api("/api/state").then(info => { S.info = info; $("#railFoot").replaceChildren(h("b", {}, T.railFoot.split(".")[0] + "."), T.railFoot.split(". ")[1] || ""); $("#keys").textContent = T.shortcuts; render();
    const demo = location.hash.replace("#", ""), click = t => [...document.querySelectorAll("button")].find(b => b.textContent.trim() === t)?.click();      // #demo, #demo-dark, #demo-clean, #demo-draw: load a sample and run it (screenshots, quick checks)
    if (demo === "demo" || demo === "demo-dark") { const sel = document.querySelector("#ls"); if (demo === "demo-dark") { sel.value = "3"; } click(T.useSample); setTimeout(() => click(T.cutLayer), 200); }
    else if (demo === "demo-clean") { S.job = "clean"; render(); click(T.cleanSample); setTimeout(() => click(T.runClean), 2500); }
    else if (demo === "demo-draw") { S.job = "draw"; render(); }
    else if (demo === "demo-recolor" || demo === "demo-pack") { S.job = "recolor"; R.mode = demo === "demo-pack" ? "pack" : "recolor"; R.input = S.info.sample_root + "/base/east"; R.hue = 120; render(); setTimeout(() => click(R.mode === "pack" ? T.packBtn : T.recolorBtn), 200); }
  }).catch(e => { $("#view").replaceChildren(h("div", { class: "notice", role: "alert" }, h("h3", {}, T.errorTitle), h("p", {}, e.message))); });
})();
