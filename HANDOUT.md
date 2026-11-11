# Gizpix — handout for agents

Gizpix is a local, free pixel-art toolkit (run everything from the repository folder). It makes **no network calls and no AI/generator calls**; it reads and writes PNG/GIF/JSON files. Needs Python 3.10+ with `numpy`, `Pillow`, `scipy` (`opencv-python` only for `warp_layer`). The code is under **AGPL-3.0-or-later** (`LICENSE`). Sprites and images you make with it are not covered by the licence.

## 1. Start here

```bash
python gizpix.py doctor          # packages + every selftest + every tool's -h + real-frame tests; all lines should say "ok"
python gizpix.py list            # all tools, grouped, one line each
python gizpix.py find outline    # which tool mentions "outline"
python gizpix.py help pix_layer  # the tool's own documentation (nothing is run)
python gizpix.py pixel_lint a.png   # run a tool: its name, then its normal arguments (the word `run` is optional)
```

`doctor` takes about a minute. Run from any folder: relative paths in your arguments mean **your** current folder. Every tool prints its documentation with `-h` (exit 0) and give a one-line error and exit code 2 for a missing file or a bad option (a few older tools may still print a Python error: read its last line); measuring tools exit 0 even when they flag something (use `--strict` where it exists).

## 2. What to use when

| You want to… | Use | Notes |
|---|---|---|
| Know if a sprite looks clean (specks, thick outline, stair-steps, blurry alpha, colour count) | `pixel_lint a.png [--strict]` | Measures only. Use the **native-size** sprite: a scaled-up image is flagged "thick outline" by design. Flags are advisory thresholds (for example more than 40 colours is flagged, so a 45-colour generated sprite exits 1 under `--strict`). |
| Compare colours between directions, states or frames | `palette_diff REF.png OTHER.png ...` | Per file: % exact, % near (re-shaded, within `--tol`), % new colours, and the biggest new ones. `--strict PCT` exits 1 above PCT % new. |
| Fix lone wrong pixels / pinholes / broken outline | `speck_fix IN OUT`, `fill_pinholes PATH --out DIR`, `repair_outline fix IN_DIR OUT_DIR` | `speck_fix` is the safe default. `repair_outline` and `despeckle` only for noisy generator output (on clean sprites they made it worse). |
| Clean a whole animation | `clean_frames`, `palette_lock`, `colormatch`, `ground_snap`, `scrub`, `despeckle` | Chain tested end to end (section 5). |
| Line frames up (same feet row / body column) | `align_frames FRAMES... --out DIR [--y feet] [--x mass]` | Whole-pixel moves, prints each shift. In a walk the lowest row moves 1–2 px as the feet swap: aligning it flattens that natural bob. Use it for frames whose ground line drifted. |
| Crop frames to their shared content | `trim_frames FRAMES... --out DIR [--pad N]` | One shared box, same size and anchor in every frame, prints the box. |
| Make an off-grid / upscaled "pixel art" picture into real pixels | `pix_snap in.png out.png --cells W H` | Reliable when you **give the cell count**. Auto size detection works on a clean integer upscale (a 3× nearest upscale) but not on AI-generated pictures: use `--candidates`. |
| Cut an outfit / armour layer from base vs base+outfit | `pix_layer cut BASE_DIR OUTFIT_DIR OUT_DIR --name robe ...` | Recipe 1 below. |
| Recolour: turn a hue, or send named groups to colours | `hue_shift IN... --out DIR --hue 120 [--range LO,HI]`, `recolor_groups IN... --swap blue=crimson --out DIR` | `hue_shift` is a pure colour→colour function (same colour, same result, in every frame; outline untouched). `recolor_groups --groups` lists a sprite's groups first. |
| Snap to a palette | `apply_palette PALETTE IN... --out DIR` | PALETTE = `.hex`/`.txt` (one `#rrggbb` per line), `.png` swatches, an analysis `.json`, comma-separated hex, or `auto --colors N`. No dithering. |
| Check an 8-direction set, a tile seam, a QA pass | `check_8dir`, `tile_check`, `qa` | Measure only. |
| Frames → sprite sheet + JSON, preview GIF, contact sheet, canvas padding | `make_sheet`, `preview_gif`, `contact_sheet`, `pad_sprite` | Sheet JSON is Aseprite/TexturePacker style (`frames`, `meta.frameTags`); Godot, Phaser, Unity importers read it. |
| Draw a building or a whole village **with no reference and no AI** | `pixdraw` | Recipe 2 below. |
| Code rigs and warping layers onto moving frames | `rig_walk2`, `warp_layer`, `xform` | Experimental: motion is limited (a few px at 64 px size). |

`list` shows everything, including `paperdoll`, `apply_pixel_fixes`, `painterly_clean`, `rig_walk`.

## 3. Recipe 1 — outfit layer from walk frames (tested on one character from one generator: 8 directions × 8 frames × 2 outfits, plus a dark-skin pair east/south)

Inputs: a folder of **base** frames (character without the outfit) and a folder of **outfit** frames (same character with it), **same pose, same size, same file names** (`0.png … 7.png`, or `south.png`, `east.png` …). A base frame without an outfit partner is skipped with a warning on stderr. They must come from one pose-driven animation (a separately redrawn walk does not line up).

```bash
python gizpix.py pix_layer cut base_frames outfit_frames layers --name robe --solid --drop-skin auto --bits --drop-parts
# -> layers/robe/0.png … 7.png: only the outfit, transparent elsewhere
```

Options (all measured, numbers in `MEASUREMENTS.md`):
- `--solid` drops sparse specks and small detached pieces (the generator re-shades skin each frame).
- `--drop-skin auto` learns the skin colour from the base and removes skin-coloured leaks. It **skips itself on dark skin** (on a synthetically darkened copy of the light pair it ate a dark brown robe: IoU against the light pair's layer 0.35–0.42 where a plain cut gave 0.86; the real dark pair has no truth layer, so no IoU exists for it). `near` is an alternative for non-orange skins; it was better for one robe and worse for armour and dark pairs: keep `auto`.
- `--drop-hue LO,HI` removes novel saturated bright colours in a hue range (hue 0..1): the tool for **hair** that the generator re-shades (orange `0.02,0.10`). It removed the hair fringe on the dark-skin pair (992 → 772 px). Check the hair's hue first: an outfit of the same hue would be eaten.
- `--bits` (opt-in) drops small detached body-coloured specks (a boot pixel floating beside armour). It can eat a few real pixels (a belt buckle, a forearm edge): look at the result.
- `--drop-parts` (opt-in, use with `--bits`) removes **hair tips and boot slivers that hang on the outfit**: it takes the hair and the boots (lowest 12 rows) from the base of the same pose and drops layer pixels there that sit on that part's own colour ramp. Measured on the skeleton-v3 walk (robe and pauldrons, south and east, 8 frames each; `experiments/skeleton_v3/parts_check.py`): leak 125 → 0, 155 → 4, 54 → 0, 88 → 0; 6, 1, 14, 1 bright outfit pixels lost. A part whose ramp contains an outfit colour is left alone (prints `SKIP`), so a dark brown robe over brown boots keeps its boots-side pixels; on the real dark pair it drops nothing. Pass all frames of a direction together (it learns the outfit colours over them). It cannot fill holes.
- `--outline` puts back the layer's own dark 1 px outline.
- Wear it: `PIL.Image.alpha_composite(base_frame, layer_frame)`. On the walk (128 frames) the composite's silhouette matches the generated outfit frame at IoU 0.95–0.98, while the bare base already matches it at 0.87–0.94, so the layer adds about 0.01–0.10 (the number mostly reflects that the body is the same). Colour match is 0.66–0.85 (strict). Judge by eye.

Limits (tell the user): without `--drop-parts`, hair tips and boots touching the outfit stay in the layer (a few to ~30 px per frame; invisible on the original body, visible if the layer is worn by a body with other hair/boot colours). Where an outfit lies over a body part of almost the same colour (a dark robe over dark trousers) the layer has holes: on the real dark pair the **east** layer lost roughly a third of the robe and is not usable, the south layer is fine. Colour cannot see it. Always view the layer at 3× next to the base before approving it. `--bits` alone cannot remove attached hair/boot leaks; `--drop-parts` (base-derived hair and boot regions plus ramp colour) does on the light pairs and cannot help the dark-skin east layer, whose problem is missing pixels.

The bundled sample frames are drawn from code (`samples/make_samples.py`): a small character walking east and south, bare and in a robe or pauldrons, with a dark-skin pair. Gizpix never calls a generator; if you generate frames yourself, ask the user before spending generation credits.

## 4. Recipe 2 — buildings and villages with `pixdraw`

```bash
python gizpix.py pixdraw build "type=inn,proj=iso,floors=3" --style dark_fantasy --out out --frames 8 --scale 3
python gizpix.py pixdraw build "type=cottage,wing=true,dormers=2" --style bright_cartoon --out out --name cottage_wing
python gizpix.py pixdraw build '{"type":"inn","wing":{"w":20,"l":16}}' --out out --name inn_wing      # dict values need the JSON form; --name keeps files apart (the default name is TYPE_VIEW)
python gizpix.py pixdraw scene pixdraw/examples/village.json --style frost --out out --frames 8
python gizpix.py pixdraw gallery gallery.png --style desert          # every preset × view
python gizpix.py pixdraw -h                                           # build, gallery, scene, styles, materials, presets, extract-style, selftest, golden
python gizpix.py pixdraw golden                                        # (also works from any folder; `python -m pixdraw` needs the Gizpix folder as the current folder)
```

- Types `house cottage inn tower round_tower keep stall`; views `iso`, `top` (3/4 RPG), `side` (platformer); styles `dark_fantasy bright_cartoon desert frost retro16` (JSON; `extract-style` makes a starting style from your own sprites, grouping colours by hue, which cannot separate a red roof from a pink wall).
- Roofs `gable hip flat` (+ `cone` for round buildings). `dormers` (0–4) and `wing` (an L-plan) need a gable roof and `iso`/`top`.
- Scenes (`compose`): `building`, `tree` (`kind` round/pine), `bush`, `well`, `fence` (also `"axis": "y"`), `path`. Items are drawn in y order.
- Animated: lantern, awning, chimney smoke, flag, looping. `--frames 8` writes `NAME.gif`, `NAME_sheet.png`, `NAME_sheet.json`.
- Python: put the repository folder on `sys.path`, `from pixdraw import render, compose`.
- Spec mistakes (an unknown key such as `flors`, a bad value, `floors` outside 1–12, `W`/`D` above 400) give a one-line error naming the key and exit 2. Full guide: `pixdraw/README.md`. Quality: clean game-sprite / placeholder level, not hand-painted art; buildings and simple props only.

## 5. Tested on real frames

`doctor` runs these, so a green `doctor` means they passed on the current machine:
- `experiments/anim_chain/chain_test.py`: `speck_fix → fill_pinholes → colormatch → ground_snap → clean_frames → palette_lock → qa → make_sheet → preview_gif` on 8 real frames (checks exit codes, frame count, frame size; not how good the art is).
- `experiments/anim_chain/tools_real_test.py`: defects injected into real frames and measured: `scrub` (a 14 px white streak: all cleared, but also 16 of 971 natural pixels), `despeckle` (6 of 6 specks fixed, ~10 natural lone pixels changed too), `repair_outline` (5 of 5 broken outline pixels repaired, silhouette unchanged), `apply_palette`, `recolor_groups`, `hue_shift`, `painterly_clean`, `pad_sprite`, `apply_pixel_fixes`, `tile_check`, `align_frames`, `palette_diff`, `rig_walk2`, `warp_layer` (it runs; its last line compares the layer with the truth frames: 3250 px of difference without the warp, 3235 with it, so the warp improved the match by 15 px, i.e. almost nothing here).
- Also exercised by hand: `pix_layer`, `pixdraw`, `pixel_lint`, `contact_sheet`, `check_8dir`, `trim_frames`.

Pixel *quality* of the cleaners' output is judged by eye, not by these tests.

## 5b. The web interface (for people, not for agents)

`python gizpix.py ui` opens a local web page (localhost only, per-run token) where a person can run the four jobs and review results by eye: previews at whole-number zoom, an exposure sheet with per-frame numbers, the exact command of every run. It runs the same tools as the commands above, writes into a staging folder first, and copies to a **new** folder only when the person presses Save, so it never overwrites anything. If a person asks to review what you produced, tell them to run it; do not drive it yourself (use the commands). Its self-test: `python ui/server.py selftest` (part of `selftest_all.py`).

## 6. Which tools overwrite your input

In place **unless you pass `--out`**: `fill_pinholes`, `colormatch` (keeps originals in `orig/`), `despeckle`, `ground_snap`, `painterly_clean`, `apply_palette`. Always in place: `apply_pixel_fixes`. Tools that write into `--out` refuse two inputs with the same file name (the second would overwrite the first): `align_frames`, `trim_frames`, `hue_shift`. Writes `<i>_s.png` next to the input: `scrub`. Writes elsewhere: `speck_fix IN OUT`, `clean_frames clean IN_DIR OUT_DIR`, `palette_lock lock IN_DIR OUT_DIR`, `repair_outline fix IN_DIR OUT_DIR`, `pix_layer cut ... OUT_DIR`, `align_frames`/`trim_frames`/`hue_shift`/`recolor_groups --out DIR`, `pixdraw --out`. Pass `--out` whenever it exists.

## 7. Rules of the road

1. **Look at it.** Open the result at 3× nearest-neighbour (`contact_sheet`, or `pixdraw --scale`); never a smooth resize. Numbers do not replace eyes.
2. **Don't optimise the number over the picture.** A lint score can be gamed by flattening the shading.
3. **Cleaners can delete real pixels** (measured costs above). Work on copies; compare before/after.
4. The tools never invent art over yours: cleaners only remove, move or recolour; `pixdraw` draws only its own buildings.
5. If a tool is not in `list`, it is not part of the kit (`experiments/` and `draw/` are test material and history; `page_build/` is an unrelated page template).
6. After changing anything run `python gizpix.py doctor`. For `pixdraw` also `python -m pixdraw golden` (a changed render fails on purpose; `--update` only for an intended change; it prints SKIPPED when the Pillow version differs from the one that made the hashes).
7. Generation credits are the user's: never spend them without approval; Gizpix does not need them.

## 8. Where things are

The repository root — `gizpix.py` (entry point) · `layers/ prep/ check/ clean/ color/ sheets/ rig/` (the tools) · `pixdraw/` (building drawer: own README, selftest, golden hashes) · `README.md` (tool table with the evidence per tool) · `MEASUREMENTS.md` (what was measured, with numbers) · `experiments/` (harnesses; `skeleton_v3/` holds the walk frames and scripts, `anim_chain/` the end-to-end tests) · `docs/` (reading notes). A local git repository: no remote, nothing published. Third-party test assets (`assets_dl/`) are kept out of git, so the numbers that depend on them (`pix_snap` real-art runs, LPC layer tests) can only be re-run on this machine.
