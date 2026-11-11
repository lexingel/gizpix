# Gizpix — what was measured

Numbers behind the claims in `README.md` and `HANDOUT.md`. The layer and clean-up measurements were made on **real AI-generated walk frames from a skeleton-driven sprite generator** (one character, eight directions, bare base plus a robe, pauldrons and a dark-skin pair), with the scripts in `experiments/` and the self-tests. Those frames are **not in the repository**; the pictures made from them are in `images/evidence/` and are rebuilt with `python experiments/evidence/make_evidence.py PATH/TO/frames`. Treat the layer-cutting results as **one character from one generator**; other generators and characters are untested.

The bundled `samples/walk_frames/` are different frames: small characters drawn by `samples/make_samples.py` so the tools can be tried without any generator. They are clean, so counts on them differ from the numbers below.

## What the tools did on real frames

Each picture is a 4× nearest-neighbour zoom with the same crop in every row (frames 0, 3 and 6 of the walk).

**Robe, walking east.** The layer follows the walk and keeps the hem and sleeves; the generator re-draws the whole body, so the bare base under it is not identical to the body in the outfit frame.

![Robe layer, east](images/evidence/layer_robe_east.png)

**Pauldrons, walking south.** Shoulder plates and gauntlets are cut; the far forearm is thin in some frames because that is what the generator drew.

![Pauldron layer, south](images/evidence/layer_pauld_south.png)

**Hair tips and boots (`--drop-parts`).** Pixels the option removed are red in the third column. The cut without the option keeps hair strands at the shoulders and a boot sliver at the hem.

![Hair tips and boots removed](images/evidence/parts_robe_south.png)

**Dark skin with a dark robe, walking east (a known failure).** The layer has holes and, in frame 6, orange hair pixels, because the robe and the body underneath are close in colour and the removal rules cannot add missing pixels. The fix is on the generation side.

![Dark pair, east](images/evidence/dark_east_holes.png)

**Clean-up.** Five off-palette specks and three pinholes were injected into each of three frames; `speck_fix` then `fill_pinholes` was run. Pinholes went from 3 to 0 in every frame and the specks no longer stand out. The repaired pixels take a colour from their neighbourhood, so they are not always the original colour: counting colours that are not in the original frame, 5 injected colours became 3, 4 and 5 (frames 0, 3, 6), not zero.

![Injected defects and repair](images/evidence/clean_real.png)

## Outfit layers (`pix_layer cut`)

Cut layer, pixels per frame (plain cut → `--solid --drop-skin auto`): pauldrons east 430 → 206, south 526 → 310; robe east 673 → 472, south 923 → 699. Skin-coloured share of the layer falls from 0.16–0.27 to 0.03.

All 8 directions, both outfits: layers are clean by eye and follow the walk; the far arm is thin in some directions because that is what the generator drew.

Wear test (composite of base + cut layer against the generated outfit frame, 2 outfits × 8 directions × 8 frames): silhouette IoU 0.95–0.98. The bare base alone already scores 0.87–0.94, so the layer adds about 0.01–0.10. Colour match 0.66–0.85 (strict, the generator re-shades the whole body). Judge by eye.

`--drop-skin` guard: it never deletes more than 40% of a frame's layer (a red shirt on light skin lost 100% before the guard, IoU 0.01 → 0.84 with it). `auto` skips itself on dark skin. `near` learns body colours from the base (any hue) and works on green or grey skins but loses real armour on pairs whose outfit colours sit near the body palette.

### Hair tips and boots (`--bits`, `--drop-parts`)

Leaked hair tips and boot slivers stay attached to the outfit after the colour rules because the generator re-draws the body in new shades (0 layer pixels exactly equal a base colour). A pure colour rule, a "same colour under it" position test and a motion test were all tried and did not separate them.

`--bits` drops small detached body-like groups (≤ 30 px). `--drop-parts` takes the hair and the boots (lowest 12 rows) from the base of the same pose and drops layer pixels there that lie on that part's own colour ramp; a part whose ramp contains an outfit colour is skipped. Measured with `experiments/skeleton_v3/parts_check.py` (8 frames of a direction cut together):

| pair | leak before | after | bright outfit px lost |
|---|---|---|---|
| robe, south | 125 | 0 | 6 |
| robe, east | 155 | 4 | 1 |
| pauldrons, south | 54 | 0 | 14 |
| pauldrons, east | 88 | 0 | 1 |
| dark pair | guard switches the part off, 0 px dropped over 16 frames | | |

### Dark skin + dark outfit

`--drop-skin auto` is off on dark skin. On the real dark pair the south layer is complete with `--solid --drop-hue LO,HI --bits` (hue of the hair), but the **east** layer has holes: the dark robe lies over dark trousers and boots, the outfit/base difference is too small, and a removal rule cannot add missing pixels. This needs a change on the generation side (a contrasting outfit colour, or a base without boots and hair).

## Cleaning tools on real frames

Defects injected into the walk frames (`experiments/anim_chain/tools_real_test.py`): `scrub` cleared a 14 px white streak but changed 16 of 971 natural pixels; `despeckle` fixed 6 of 6 specks and changed about 10 natural single pixels; `repair_outline` repaired 5 of 5 broken outline pixels; `painterly_clean`, `apply_palette`, `recolor_groups`, `pad_sprite`, `apply_pixel_fixes`, `tile_check` and `rig_walk2` behaved as documented. `warp_layer` works but improved the match by only 15 px on this pair. `despeckle` and `repair_outline` can damage clean sprites (natural single pixels, intact outlines): use them on frames that have the defect.

`align_frames` flattens the walk's natural 1–2 px bob when it aligns the feet row; use it for frames whose ground line drifted.

## Snapping (`pix_snap`)

On 240 real pixel-art images (Kenney CC0 16×16 tiles and sprites, re-scaled and warped) automatic exact-grid detection recovered the true size on 57/120 regular-grid images against 27/120 for the other method compared. Elastic-grid size scoring was tried and dropped (worse than the dip rule). For warped images pass `--candidates`.

## pixdraw

`python gizpix.py pixdraw golden` checks SHA-256 hashes of 50 fixed renders (Pillow-version aware); `pixdraw selftest` renders 105 combinations and checks determinism, loop closure, palettes and `pixel_lint` bounds. `extract-style` assigns roles by position (the colour group that sits highest in the sprites becomes the roof): on 33 sample sprites the band colour distance between sprites and renders went from 49.7 to 48.6 for single sprites and 31.5 to 30.7 for the whole set (lower is better) — a small gain; the output is a starting point to edit.

## Known limits

- One character, one generator, one animation template; other sources are untested.
- Dark outfit over dark body parts: holes (see above).
- `--bits` and `--drop-parts` can remove a few real pixels (belt buckle, forearm edge): look at the result.
- `top`-view buildings with an L-wing read less clearly than `iso`.
- Tested on Windows only.
