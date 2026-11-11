# Changelog

## 0.2.0
- `experiments/evidence/make_evidence.py` and `images/evidence/`: pictures of the layer, `--drop-parts`, dark-skin failure and clean-up tools on real generated frames; `MEASUREMENTS.md` rewritten around them.
- `pip install` support: the `gizpix` command (`pip install git+https://github.com/lexingel/gizpix.git`).
- Web interface: a `Choose folder…` button opens the operating system's own folder dialog (Browse stays as a fallback); Pack shows `folder/*.png` in its command; `#demo-recolor` and `#demo-pack` captures.
- Sample frames are now drawn from code (`samples/make_samples.py`), so they share Gizpix's licence; the earlier AI-generated frames are no longer bundled.
- `python gizpix.py ui`: a local web interface (Python standard library server on 127.0.0.1, plain HTML/CSS/JS, no build step, self-hosted open fonts) for the four jobs: clean & measure, cut outfit layer, draw buildings, recolour & pack. Results are staged first and saved only on request, always to a new folder; each result shows its exact command; previews use whole-number nearest-neighbour zoom; frames are shown as exposure-sheet columns.
- `ui/design_options/`: the six design sketches that were scored before the interface was built.
- Web interface self-test added to `selftest_all.py`.

## 0.1.0 — first shareable version
- 33 command-line tools behind one entry point (`gizpix.py list | find | help | doctor | run`), plus the `pixdraw` building and village drawer.
- Layers: `pix_layer cut` with skin drop (`--drop-skin auto|near`), `--solid`, `--outline`, `--bits` and `--drop-parts` (hair tips and boots).
- Measure: `pixel_lint`, `palette_diff`, `tile_check`, `check_8dir`, `qa`.
- Clean: `speck_fix`, `fill_pinholes`, `painterly_clean`, `scrub`, `colormatch`, `ground_snap`, `palette_lock`, `clean_frames`, `despeckle`, `repair_outline`.
- Colour and frames: `hue_shift`, `recolor_groups`, `apply_palette`, `align_frames`, `trim_frames`, `make_sheet`, `preview_gif`, `contact_sheet`, `pad_sprite`, `pix_snap`.
- `pixdraw`: seven building types, three views, five JSON styles, dormers, an L-shaped wing, round towers, scenes (trees, fences, paths, wells), `extract-style` (roles by position in your sprites), golden-hash regression test.
- Sample walk frames in `samples/walk_frames/`, measured results in `MEASUREMENTS.md`, handout for coding agents in `HANDOUT.md`.
- Licence: AGPL-3.0-or-later.
