# Gizpix handout for coding agents

Gizpix is a local, free, offline pixel-art toolkit (version 0.2.0): about 30 command-line tools behind one entry point, a `pixdraw` package that draws buildings from parameters, and a local web interface for people. It makes no network calls and no AI or generator calls; it reads and writes PNG, GIF and JSON files. Python 3.10+ with `numpy`, `Pillow`, `scipy` (`opencv-python` only for `warp_layer`). Code: AGPL-3.0-or-later; the sprites you make with it are yours.

Everything in this file was checked against the tools on 2026-11-11 (help texts, and real runs on the bundled `samples/walk_frames`). Numbers come from `MEASUREMENTS.md`, the tools' own help, or those runs.

## 1. How to call it

```bash
python gizpix.py list              # every tool, grouped, one line each
python gizpix.py find outline      # tools whose name, purpose or docstring mention a word
python gizpix.py help pix_layer    # the tool's own documentation (nothing runs)
python gizpix.py pix_layer -h      # the same from the tool itself (exit 0)
python gizpix.py pixel_lint a.png  # run a tool: its name, then its arguments (`run` before the name is optional)
python gizpix.py doctor            # packages + every selftest + every tool's -h; all lines should say ok
python gizpix.py path              # prints the Gizpix folder
python gizpix.py ui                # the local web interface (for people; see section 8)
```

- From a clone: `python gizpix.py ...` run from any folder (`python D:\path\to\gizpix.py ...` works). After `pip install git+https://github.com/lexingel/gizpix.git` the command is just `gizpix ...`; `gizpix path` tells you where the bundled samples and `pixdraw/examples` live. Everywhere below, read `gizpix` for `python gizpix.py` if you installed it.
- Relative paths in your arguments mean **your** current folder, not the Gizpix folder. Repo-relative paths such as `pixdraw/examples/village.json` only work from inside the Gizpix folder; from anywhere else use `$(gizpix path)/pixdraw/examples/village.json` (or the absolute path).
- A wrong tool name prints suggestions and exits 2 (`pixlayer` -> "did you mean pix_layer, warp_layer, pixdraw?").
- Exit codes: `-h` exits 0; a missing file or bad option gives a one-line error and exit 2 (a few older tools print a Python traceback instead: read its last line). Measuring tools exit 0 even when they flag something; use `--strict` where it exists to get exit 1.
- Windows PowerShell does not expand `*.png`. Tools that take a list of files and expand globs themselves: `despeckle`, `qa`, `hue_shift`, `make_sheet` (quote the pattern: `"frames\*.png"`). For the others pass the files explicitly or let your shell expand them (Git Bash / cmd `for`). Folder-taking tools (`fill_pinholes`, `pix_layer`, `clean_frames`, `palette_lock`, `repair_outline`) need no glob.

## 2. Standing rules for agents

1. **Never spend generator credits.** Gizpix needs none. If a job needs new frames (a re-roll, a contrasting outfit, a base without hair), stop and ask the user before generating anything.
2. **Never claim a result without looking at the picture.** Numbers do not replace eyes. Make a contact sheet at a whole-number zoom (`contact_sheet out.png a.png b.png --scale 3`) and open it. Judge at 3x or another whole number, nearest-neighbour, never a smooth resize.
3. **Clean frames before you review them**, so you judge the art, not the specks. Clean in the order of recipe A.
4. **Work on copies.** Pass `--out` whenever a tool has it (section 4 lists the in-place tools). Never run a cleaner over the user's only copy.
5. **Cleaners can delete real pixels.** Measured costs are in section 7. Compare before and after at zoom.
6. **Do not optimise a number over the picture.** A lint score can be gamed by flattening shading.
7. **A measuring tool's "FLAGS: none" is not a clean bill.** `pixel_lint` counted 1-2 of 5 injected specks per frame (it only counts a speck whose four neighbours agree with each other) and raised no flag. Look.
8. **Tell the user the limits** (section 7) when you hand over a layer, a cleaned set or a snapped image: one generator, one character; dark on dark leaves holes.
9. If a tool is not in `python gizpix.py list`, it is not part of the kit (`experiments/`, `draw/`, `page_build/` are harnesses and history).
10. After changing any tool, run `python gizpix.py doctor`; for `pixdraw` also `python gizpix.py pixdraw golden` (a changed render fails on purpose; `--update` only for an intended change; prints SKIPPED when the Pillow version differs from the one that made the hashes).

## 3. Task to tool

| You want to | Tool | Measures or changes | Notes |
|---|---|---|---|
| Quality numbers for a sprite (specks, thick outline, stair steps, blurry alpha, colour count) | `pixel_lint a.png [b.png ...] [--json] [--strict]` | measures | Native size only: a 3x upscale is flagged "thick outline" (thick_line 0.996 on a clean sample). More than 40 colours is flagged. |
| Colour drift between frames, directions or states | `palette_diff REF.png OTHER.png ... [--tol 24] [--strict PCT] [--json]` | measures | Per file: % exact, % near (within `--tol`), % NEW, and the biggest new colours with their nearest reference colour. |
| Batch sanity before a human looks (empty, cropped at edge, off-palette, flashes) | `qa FILES [--anim] [--opaque] [--anchor approved.png] [--sheet flagged.png] [--strict]` | measures | Accepts a quoted glob. `--anim` also flags flashes and size changes between frames. |
| Does a tile repeat without a seam | `tile_check tile.png` or `tile_check atlas.png --grid 16` | measures | seam about 1 = invisible, above 2 = visible. Only for tiles meant to wrap. |
| Check an 8-direction set (stills, walk, compass preview, mirror, light) | `check_8dir stills DIR` / `walk DIR` / `compass DIR out.png` / `mirror SRC DST` / `light DIR` | measures (mirror writes new files) | `walk DIR` expects `DIR/<direction>/0.png ...`; it runs with fewer than 8 directions and prints flags. |
| Fix lone wrong-coloured pixels | `speck_fix IN.png OUT.png [--tol 120] [--rare 2]` | changes (one file at a time) | Only fixes a speck whose exact colour is used by at most `--rare` pixels. Five specks of one colour in a frame: 0 fixed at the default, 5 fixed with `--rare 5`. A folder is not accepted (exit 2): loop over files. |
| Fix many lone pixels in noisy generator frames | `despeckle FRAMES... [--out DIR] [--tol 90]` | changes | Caught 5 of 5 same-colour specks where `speck_fix` caught 0, but on real frames it also changed about 10 natural lone pixels (eye glints) per set. Use on frames that have the defect. |
| Close one-pixel holes inside a sprite | `fill_pinholes PATH... --out DIR` | changes | PATH = file, folder, or root of folders. 24 of 24 injected pinholes closed on the samples. 2-3 px slivers between limbs are left alone. |
| Close breaks in a dark 1 px outline | `repair_outline fix IN_DIR OUT_DIR [--min-dark 2] [--y-min ROW]` | changes colours only | Only on noisy generator output; on clean sprites it made things worse. |
| Holes, cracks and white dots in soft-shaded (100+ colour) sprites | `painterly_clean FRAMES... --out DIR [--marks DIR] [--holes-only] [--ref ref.png]` | changes | `--marks` writes a before/after/changes picture at 3x: look before keeping. `--holes-only` on frames with sparks, embers, trails. |
| Flashes and streaks a generator painted into frames | `scrub DIR 0 1 2 ... [--tol 40]` | changes | Writes `<i>_s.png` next to the input. Cleared a 14 px streak but changed 16 of 971 natural pixels on real frames. |
| Colour shift of key poses against the standing sprite | `colormatch STANDING.png FRAMES... --out DIR` | changes colours | Run after `scrub`, before the sheet. In place without `--out` (originals copied to `orig/`). |
| Frames drawn a few px above the ground | `ground_snap STANDING.png PADX,PADY FRAMES... --check` then without `--check` and with `--out DIR` | changes position | Not for jumps or flying. `--fx 5,6` skips frames with no feet on purpose. |
| Whole-animation clean-up with a reference palette | `clean_frames clean IN_DIR OUT_DIR --ref REF.png [--snap] [--ground-row ROW]` | changes | Needs `--ref`. Writes `clean_report.json`. `--snap` recolours instead of dropping off-palette pixels (use on painterly sprites). |
| Snap frames to the character's own palette | `palette_lock lock IN_DIR OUT_DIR --ref STILL.png [...] [--max-dist 60]` | changes colours | Pixels farther than `--max-dist` from every palette colour are left alone and reported. |
| Audit trail of single-pixel edits | `apply_pixel_fixes FIXES.json FRAMES_ROOT` | changes **in place, always** | Each edit printed before -> after. Copy the frames first. |
| Line frames up on one feet row / body column | `align_frames FRAMES... --out DIR [--y feet\|top\|none] [--x mass\|bbox\|none] [--to X,Y]` | changes position | Prints each shift. A walk's lowest row moves 1-2 px as the feet swap: aligning it flattens that bob. Use for drifted key poses, not a walk that looks right (the samples shift 0,0). |
| Crop frames to one shared box | `trim_frames FRAMES... --out DIR [--pad N] [--each]` | crops | One box for all (same size and anchor); prints `x0,y0,x1,y1`. `--each` only for loose sprites. |
| Put a sprite on a bigger canvas | `pad_sprite in.png out.png W H X [Y]` | new file | Prints the offset to record for the engine. |
| Sprite sheet + JSON | `make_sheet OUT_BASE FRAMES... (--fps 12 \| --durations ms,ms,... \| --beat light\|swing) [--cols N] [--godot]` | new files | Aseprite "array" JSON (`frames[].frame`, `duration`, `meta`); `--godot` also writes a `.tres`. |
| Preview GIF | `preview_gif out.gif - FRAMES... --faithful --fps 12 [--scale 3]` | new file | `--faithful` = exactly your frames, transparent, 1:1 unless `--scale`. Without it the GIF adds a standing beat and holds meant for attack swings and needs a still as the second argument. |
| Contact sheet for review | `contact_sheet out.png a.png b.png c.png [--row d.png e.png] [--scale 3] [--cols 10]` | new file | `--scale 3` gives a 3x nearest-neighbour sheet (864x576 for six 96 px frames). One `--row` per row. |
| Turn an upscaled or off-grid picture into real pixels | `pix_snap in.png out.png --cells W H` or `--candidates` | new file | Give the cell count when you know it: exact result on a 3x upscale (100% colours match). Auto size got the width wrong (87x96 for a 96x96 sprite) on that same clean upscale: do not trust auto; use `--candidates` and pick by eye. |
| Cut an outfit or armour layer from base vs base+outfit frames | `pix_layer cut BASE_DIR OUTFIT_DIR OUT_DIR --name robe --solid --drop-skin auto --bits --drop-parts` | new files | Recipe B. |
| One base/edit pair, with checks; stack layers on a base | `paperdoll extract BASE.png EDIT.png --out DIR --name hat [--region x0,y0,x1,y1] [--tol 18]` / `paperdoll compose BASE.png LAYER.png [LAYER2.png ...] --out final.png` | new files | `extract` writes `NAME.layer.png`, `NAME.check.png`, `NAME.report.json` and exits 1 when a check fails. `compose` prints nothing on success. |
| Recolour by turning the hue (all colours or one hue range) | `hue_shift FRAMES... --out DIR --hue DEG [--range LO,HI] [--sat M] [--val M] [--keep-dark V]` | new files | Same colour -> same result in every frame. `--hue` is degrees (-180..180); `--range` is 0..1 on the wheel (red 0, yellow .17, green .33, cyan .5, blue .67) and wraps when LO > HI (`0.9,0.05` = reds). Outline (value below 0.12) untouched. |
| Send a named colour group (red, skin, grey ...) to a colour | `recolor_groups STILL.png --groups` then `recolor_groups STILL.png FRAMES... --swap red=#2e8b57 --out DIR` | new files | The first file is the still that sets the mapping; frames follow it. `--out` is required. Skin never moves unless named. |
| Snap to a fixed palette | `apply_palette PALETTE FRAMES... --out DIR [--colors N]` | changes (in place without `--out`) | PALETTE = `.hex`/`.txt` (one `#rrggbb` per line), `.png` swatches, an analysis `.json`, comma-separated hex, or `auto --colors N`. No dithering. |
| Draw a building, a gallery, a village; no reference, no AI | `pixdraw build SPEC [--style S] --out DIR [--name N] [--frames 8] [--scale 3] [--ms 120]`, `pixdraw scene FILE.json ...`, `pixdraw gallery out.png --style S` | new files | Recipe C. |
| Move a standing layer onto walk frames; code walks | `warp_layer`, `rig_walk2`, `xform` | experimental | Motion is limited (a few px at 64 px); `warp_layer` improved a real pair by 15 px of 3250. Needs OpenCV. Prefer layers cut from real walk frames. |

## 4. Input and output conventions

- **Folders of frames** are `0.png, 1.png, ...` or `south.png, east.png, ...`. Tools that sort by number read `*.png` sorted by the number in the name.
- **`--out DIR`** writes `DIR/<same file names>` and never touches the input. Tools that write into `--out` refuse two inputs with the same file name (`hue_shift`, `align_frames`, `trim_frames`: "two inputs share the file name '0.png'", exit 2). `recolor_groups` does not refuse: passing the still again among the frames just writes it twice.
- **In place unless you pass `--out`**: `fill_pinholes`, `colormatch` (keeps originals in `orig/`), `despeckle`, `ground_snap`, `painterly_clean`, `apply_palette`. **Always in place**: `apply_pixel_fixes`. **Writes next to the input**: `scrub` (`<i>_s.png`). **Positional output**: `speck_fix IN OUT`, `clean_frames clean IN OUT`, `palette_lock lock IN OUT`, `repair_outline fix IN OUT`, `pix_layer cut ... OUT_DIR`, `pad_sprite IN OUT`, `pix_snap IN OUT`, `make_sheet OUT_BASE`, `preview_gif OUT`, `contact_sheet OUT`.
- `pix_layer cut` writes `OUT_DIR/<name>/<frame>.png`. `pixdraw build` writes `DIR/NAME.png` and with `--frames` also `NAME.gif`, `NAME_sheet.png`, `NAME_sheet.json`; the default NAME is `TYPE_VIEW`, so pass `--name` when drawing the same type twice into one folder.
- The web interface writes only on Save, into a new folder under `./gizpix_out` of the folder it was started from (`--out-root DIR` changes that).
- Measuring tools print to stdout; `--json` where offered.

## 5. Recipes (each line was run as written)

### A. Clean 8 walk frames, measure, pack

```bash
# 1. look first (numbers), then at a sheet
python gizpix.py pixel_lint frames/0.png frames/1.png
python gizpix.py contact_sheet before.png frames/0.png frames/3.png frames/6.png --scale 3

# 2. specks: one file at a time; raise --rare if the same wrong colour repeats
for i in 0 1 2 3 4 5 6 7; do python gizpix.py speck_fix frames/$i.png step1/$i.png; done      # PowerShell: foreach ($i in 0..7) { ... }
# noisy generator output instead:  python gizpix.py despeckle "frames\*.png" --out step1

# 3. pinholes, a folder at a time
python gizpix.py fill_pinholes step1 --out fixed             # prints "24 pinholes filled"

# 4. did the colours stay the character's?  then look again
python gizpix.py palette_diff frames/0.png fixed/0.png
python gizpix.py contact_sheet after.png frames/0.png fixed/0.png --row frames/3.png fixed/3.png --scale 3

# 5. pack
python gizpix.py make_sheet out/walk fixed/0.png fixed/1.png fixed/2.png fixed/3.png fixed/4.png fixed/5.png fixed/6.png fixed/7.png --fps 12
python gizpix.py preview_gif out/walk.gif - fixed/0.png fixed/1.png fixed/2.png fixed/3.png fixed/4.png fixed/5.png fixed/6.png fixed/7.png --faithful --fps 12 --scale 3
```

For generated attack clips the longer chain is `speck_fix -> fill_pinholes -> colormatch -> ground_snap -> clean_frames -> palette_lock -> qa -> make_sheet -> preview_gif`; `experiments/anim_chain/chain_test.py` runs it end to end on the bundled samples (exit codes, frame count and size only, not art quality).

### B. Cut an outfit layer from walk frames and check it

Inputs: a folder of **base** frames (the character without the outfit) and a folder of **outfit** frames (the same character wearing it): same pose, same size, same file names, from one pose-driven animation. A base frame without a partner is skipped with a warning on stderr; a size mismatch is an error.

```bash
python gizpix.py pix_layer cut samples/walk_frames/base/east samples/walk_frames/robe/east layers --name robe --solid --drop-skin auto --bits --drop-parts
#   -> layers/robe/0.png ... 7.png;  prints "auto skin: (...)", per-frame "parts hair N, boots N", and "raw 2830 -> clean 2780"
python gizpix.py paperdoll compose samples/walk_frames/base/east/0.png layers/robe/0.png --out worn0.png
python gizpix.py palette_diff samples/walk_frames/robe/east/0.png worn0.png layers/robe/0.png      # worn: 99.6% exact on the samples
python gizpix.py contact_sheet check.png samples/walk_frames/base/east/0.png samples/walk_frames/robe/east/0.png layers/robe/0.png worn0.png --scale 3
```

Options (measured on real generated frames, see `MEASUREMENTS.md`):
- `--solid`: drops sparse specks and small detached pieces (the generator re-shades skin per frame).
- `--drop-skin auto`: learns the skin colour from the base and removes skin-coloured leaks. It never deletes more than 40% of a frame's layer. It **switches itself off on dark skin** and prints a WARNING saying so (on a synthetically darkened pair it ate a dark robe). `near` learns any body colour (green, grey) but lost real armour where outfit colours sit near the body palette: keep `auto`.
- `--drop-hue LO,HI`: removes novel saturated bright colours in a hue range (0..1): for **hair** the generator re-shades (orange `0.02,0.10`). An outfit of the same hue would be eaten: check first.
- `--bits`: drops small (<= 30 px) detached body-coloured specks. Can eat a belt buckle or a forearm edge.
- `--drop-parts` (with `--bits`): removes hair tips and boot slivers attached to the outfit, using the hair and the lowest 12 rows of the base of the same frame. Real-frame leaks 125 -> 0, 155 -> 4, 54 -> 0, 88 -> 0 with 6, 1, 14, 1 real bright pixels lost. Prints `SKIP` for a part whose ramp contains an outfit colour. Pass all frames of one direction together (it learns outfit colours across them). It cannot fill holes.
- `--outline`: puts back the layer's own dark 1 px outline.
- Wear it in code: `PIL.Image.alpha_composite(base, layer)`. On real frames the composite matches the generated outfit frame at silhouette IoU 0.95-0.98, but the bare base already matches at 0.87-0.94, so judge by eye.

### C. Buildings and villages with `pixdraw`

```bash
python gizpix.py pixdraw build "type=inn,proj=iso,floors=3" --style dark_fantasy --out out --name inn_dark --frames 8 --scale 3
python gizpix.py pixdraw build "type=inn,proj=iso,floors=3" --style frost        --out out --name inn_frost --frames 8
python gizpix.py pixdraw build "type=inn,proj=iso,floors=3" --style retro16      --out out --name inn_retro --frames 8
#   -> out/inn_frost.png, inn_frost.gif, inn_frost_sheet.png, inn_frost_sheet.json (TexturePacker "hash" frames + Aseprite frameTags)
python gizpix.py pixdraw build "type=cottage,wing=true,dormers=2" --style bright_cartoon --out out --name cottage_wing
python gizpix.py pixdraw build '{"type":"inn","wing":{"w":20,"l":16}}' --out out --name inn_wing      # dict values need JSON
python gizpix.py pixdraw scene "$(python gizpix.py path)/pixdraw/examples/village.json" --style frost --out out --name village --frames 8
python gizpix.py pixdraw gallery gallery.png --style desert       # every preset x view
python gizpix.py pixdraw styles ; python gizpix.py pixdraw presets ; python gizpix.py pixdraw materials
```

- Types: `house cottage inn tower round_tower keep stall`. Views: `iso`, `top` (3/4 RPG), `side` (platformer). Styles: `bright_cartoon dark_fantasy desert frost retro16`, or a path to your own style `.json`.
- Roofs `gable hip flat` (+ `cone` for round). `dormers` (0-4) and `wing` need a gable roof and `iso`/`top`. Materials `planks stone brick plaster thatch shingles tiles plain`. Switches `chimney smoke lit awning open_front lantern flag door ground plinth`. Full key table: `pixdraw/README.md`.
- Scenes: `building`, `tree` (`kind` round/pine), `bush`, `well`, `fence`, `path`; items are drawn in y order; buildings animate, the rest is still.
- A spec mistake is a one-line error naming the key with a suggestion and the known keys, exit 2 (`flors` -> "did you mean 'floors'?").
- `extract-style a.png b.png --out my_style.json` makes a starting style from your sprites by grouping colours by hue; a red roof and a pink wall end up in one group. Edit the result.
- Quality: clean game-sprite or placeholder level; buildings and simple props only, no characters, no text.
- Python: `from pixdraw import render, compose` with the Gizpix folder on `sys.path`.

### D. Recolour one part of a character

```bash
python gizpix.py recolor_groups robe/0.png --groups                                   # red 41.9%, black 25.2%, orange 14.0%, skin 12.8%, yellow 6.0%
python gizpix.py recolor_groups robe/0.png robe/1.png ... robe/7.png --swap red=#2e8b57 --out green
python gizpix.py hue_shift "robe\*.png" --out hue --hue 120 --range 0.9,0.05          # same effect by hue range: 294 px per frame
python gizpix.py palette_diff robe/0.png green/0.png                                 # 41.9% NEW = exactly the red group moved
```

`recolor_groups` names the groups for you; `hue_shift --range` needs you to know where the colour sits on the wheel. Both leave skin and outline alone unless told otherwise.

## 6. Reading the output

- `pixel_lint`: one dict per file plus `FLAGS:`. `lone_px` = isolated pixels + specks; `thick_line` = share of dark outline pixels in 2x2 blocks (about 0.05 on a clean 1 px outline, 0.996 on an upscale); `stair_break`, `soft_alpha`, `colors`. Flags are advisory thresholds.
- `palette_diff`: `exact` / `near` / `NEW` percentages per file and the new colours as `#rrggbbxCOUNT(~nearest)`. Transparent pixels are ignored.
- `pix_layer cut`: `raw N -> clean M` pixel counts; `WARNING` lines on stderr (dark skin, unpaired frames); `SKIP` from `--drop-parts`.
- `paperdoll extract`: a JSON line with `ok`, `fails`, `layer_px`, `over_body_px`, `body_loss`, `bbox`, `roundtrip_bad_px`; exit 1 when a check fails.
- `align_frames` / `trim_frames`: a shift `dx,dy` or a box per frame: store it if the engine needs the original offsets.
- `pix_snap`: `{'cells': (W, H), ... 'candidates': ...}`; without `--cells`, treat `cells` as a guess.
- `check_8dir walk`: a table (feet line, bob, phase vs east) then `FLAGS:` with advice ("judge it by eye at 6x").

## 7. Known limits and traps

- **One generator, one character.** The layer tools were developed and measured on one character from one skeleton-driven generator; those AI frames are **not bundled**. The bundled `samples/walk_frames` (96x96, east and south, 8 frames: `base`, `robe`, `pauld`, dark pair `dbase`/`drobe`) are drawn from code by `samples/make_samples.py`, so they are clean and counts on them differ from `MEASUREMENTS.md`. `doctor` runs the chain and defect tests on these code-drawn samples.
- **Dark outfit over dark skin or dark trousers leaves holes.** On the real dark pair the east layer has holes (see `images/evidence/dark_east_holes.png` in MEASUREMENTS.md); south was fine. Colour rules cannot add missing pixels. The fix is on the generation side (contrasting outfit colour, or a base without hair and boots): ask the user.
- **Repaired pixels take a neighbour colour**, not the original: after `speck_fix` + `fill_pinholes` on real frames, 5 injected colours became 3, 4 and 5 off-palette colours, not zero.
- **`speck_fix` skips repeated colours**: a speck colour used by more than `--rare` (default 2) pixels in the file is treated as a palette colour and kept. On real frames it fixed 77% of injected specks and wrongly changed 0.7 natural details per clean sprite.
- **`despeckle` and `repair_outline` damage clean sprites** (natural lone pixels, intact outlines). Only on frames that have the defect.
- **`--bits` and `--drop-parts` can remove a few real pixels** (a belt buckle, a forearm edge). Look at 3x.
- **`--drop-skin auto` is off on dark skin** (it prints the WARNING); `--drop-hue` eats an outfit of the hair's hue.
- **`align_frames --y feet` flattens a walk's natural 1-2 px bob.** Only for drifted frames.
- **`pixel_lint` on an upscale** flags "thick outline" by design; it under-counts specks on edges and raises no flag for them.
- **`pix_snap` auto size is unreliable** even on a clean 3x upscale in this check (87x96 instead of 96x96): pass `--cells`, else `--candidates` and pick by eye. On 240 real images auto recovered the true size on 57 of 120 regular-grid images.
- **`extract-style`** groups by hue only; it is a starting point to edit.
- **`top`-view buildings with a wing** read less clearly than `iso`.
- **Windows only so far.** The code is plain Python and should run elsewhere, but nothing else was tested.
- **`ground_snap`** is wrong for jumps and flying; **`tile_check`** is wrong for edge tiles that are not meant to wrap.

## 8. The web interface and the installed command

- `python gizpix.py ui [--port 8765] [--no-open] [--out-root DIR]` starts a standard-library server on 127.0.0.1 only (per-run token, localhost Host check, no free-form commands) and opens the browser. Four jobs: Clean & measure, Cut outfit layer, Draw buildings, Recolour & pack. Previews at whole-number zoom; frames as columns with numbers; every result shows the exact command it ran; runs are staged in a temp folder and copied to a **new** folder under the output root only on Save. Stop with Ctrl+C. Self-test: `python ui/server.py selftest` (also part of `doctor`).
- It is for people. If the user wants to review what you made, tell them to start it; you keep using the commands (the UI runs the same ones, so your command lines reproduce its results).
- `pip install git+https://github.com/lexingel/gizpix.git` installs the `gizpix` command (entry point `gizpix_toolkit.gizpix:cli`), the samples, the UI and `pixdraw`. `pip install .` from a clone does the same. Not on PyPI. The wheel was installed into a clean virtual environment on 2026-11-11 and `gizpix doctor`, `gizpix ui` and the tools ran from it.

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `speck_fix: no such file: <folder>` | It takes one file in, one file out. Loop over the frames. |
| `speck_fix` prints `0 pixels fixed` but specks are visible | The same wrong colour is used more than 2 times: `--rare 5` (or more), or `despeckle` for noisy output. |
| `recolor_groups.py: error: give --out DIR` | `--out` is required for `--swap`. |
| `pixdraw: no such scene file: pixdraw/examples/village.json` | Repo-relative path from another folder. Use `$(gizpix path)/pixdraw/examples/village.json`. |
| `two inputs share the file name '0.png'` (exit 2) | Run once per folder, or rename. |
| `pix_layer: WARNING: N PNG(s) in the base folder have no outfit partner` | File names differ between the folders; the unpaired frames are skipped. |
| `pix_layer: X.png has size ... in the base but ... in the outfit folder` | Base and outfit must be the same canvas size. |
| `WARNING: dark skin ... --drop-skin is skipped` | Expected on dark skin; use `--drop-hue` for hair and look for holes. |
| `pixel_lint` flags "thick outline" on a clean sprite | It is an upscale. Lint the native-size file. |
| `*.png` passed literally (Windows) | Only `despeckle`, `qa`, `hue_shift`, `make_sheet` expand globs; list the files for the others. |
| `golden` prints SKIPPED | Pillow version differs from the one that made the hashes; `pixdraw golden --update` makes local ones. |
| `doctor` says `note cv2` | OpenCV is optional; only `warp_layer` needs it. |
| A measuring tool exits 0 although it flagged something | By design; add `--strict` where it exists. |

## 10. Where things are

`gizpix.py` (entry point and the TOOLS registry) · `layers/ prep/ check/ clean/ color/ sheets/ rig/` (the tools) · `pixdraw/` (own README, selftest, `golden.json` with 50 render hashes) · `ui/` (server + web files) · `samples/walk_frames/` + `samples/make_samples.py` · `README.md` (tool table, install, licence) · `ABOUT.md` (plain-language overview) · `MEASUREMENTS.md` (numbers and evidence pictures in `images/evidence/`) · `CHANGELOG.md` · `experiments/` (harnesses; `anim_chain/` holds the two tests `doctor` runs; `skeleton_v3/` holds scripts only, the frames they measured are not in the repository) · `assets_dl/` (third-party test assets, kept out of git; the `pix_snap` real-art numbers and LPC layer tests can only be re-run where they exist). The repository has a GitHub remote (`lexingel/gizpix`); check with the user before publishing or redistributing anything.
