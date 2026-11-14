# pixart - draw pixel art from code, with the craft built in

You say what is where (masks from on-grid shapes), which colour ramp and which form each part has. pixart does the pixel craft: hue-shifted ramps,
one light for every part, form shading in a few flat tones, clean tone clusters, a 1 px light-aware outline, cast shadows, and a lint that measures the result.
**No reference image, no AI generation.** Pure Python (numpy, Pillow, scipy). The craft rules and their sources are in [KNOWLEDGE.md](KNOWLEDGE.md).

```bash
python gizpix.py pixart new mushroom --size 32x32 --dir work     # starter script work/mushroom.py; edit it, then: python work/mushroom.py
python gizpix.py pixart examples --out out                       # 14 worked recipes: potion sword heart slime tree chest hero cat knight dir8 coin flame logo scene
python gizpix.py pixart guide                                    # the craft rules
```
```python
import sys; sys.path.insert(0, r"path	o\your\Gizpixolder")
from pixart import Canvas, Ramp, ramp, shrink, grow, shift, sym, export

c = Canvas(32, 32, light="tl")
cap = ramp("#c8402f"); stem = ramp("#e8dcc0", n=3)
c.fill(c.rect(13, 16, 6, 11, r=1), stem, form="tube")
c.fill(c.oval(5, 5, 22, 16) & (c.yy < 17), cap, form="ball", box=(5, 5, 22, 22), shadow=True)
c.outline(); c.lint(); c.preview("out/mushroom_preview.png"); c.save("out/mushroom.png")
```

## The loop

1. **Plan**: size, view, light, 2-4 materials, the subject's identifying features (KNOWLEDGE.md section 1).
2. **Draw** back to front: masks -> `fill` -> details -> `outline`.
3. **Measure and look**: `c.lint()` prints numbers and flags; `c.preview(path)` writes the review sheet (big view, 1x and 2x on dark / light / brown, silhouette, greyscale, palette). Open it and judge it at 1x.
4. **Fix** what the flags and your eyes found; repeat 2-3 times at most; `c.save()` / `export()`.

## Canvas

`Canvas(w, h, light="tl")` - light is a name (`tl tr top l r front`) or `(lx, ly)` pointing toward the light (up is negative y). `c.xx`, `c.yy` are coordinate grids for cutting masks (`mask & (c.yy < 17)`).

### Shapes -> masks (numpy bool arrays; combine with `|`, `&`, `~`)

| call | gives |
|---|---|
| `c.rect(x, y, w, h, r=0)` | box, `r` = rounded corner radius |
| `c.oval(x, y, w, h, angle=0)` | ellipse filling the box (symmetric pixel circles); `angle` degrees tilts it clockwise about its centre |
| `c.ring(x, y, w, h, t=2, angle=0, t2=None)` | an oval band `t` px thick at the sides, `t2` at top and bottom: rings, hoops, cage wires, a band seen at an angle |
| `c.poly([(x, y), ...])` | filled polygon |
| `c.line([(x, y), ...], w=1)` | pixel-perfect polyline, `w` px thick |
| `c.curve([(x, y), ...], w=1, closed=False, w1=None)` | smooth pixel-perfect curve through the points; with `w1` it tapers from `w` to `w1` px (tentacles, tails, horns, vines) |
| `c.blob([(x, y), ...])` | filled organic shape through the points (points may lie off-canvas) |
| `c.grid(rows, x, y)` | mask from text rows (`#` = on, `.` = off): exact shapes by hand |
| `rim(m, dx, dy)` | the crescent of `m` left uncovered when a copy moves by `(dx, dy)`: edge lights on gems and glass, the far inner wall of a ring, the back of a lens (`m & shift(m, dx, dy)` is the shared part) |
| `shrink(m, n)`, `grow(m, n)`, `shift(m, dx, dy)`, `flipx(m, axis)`, `sym(m, axis)` | inset, outset, move, mirror, make symmetric. `axis` is the pixel EDGE to mirror about: on a 48 px canvas the middle is `axis=24` (columns 23 and 24 swap); leave it out for the canvas middle. A small mask shrunk by 2 may have nothing left: check `m.sum()` |

Coordinates: `x, y` is the top-left pixel, sizes in pixels; `(0, 0)` is the top-left of the canvas.

### Colour

`ramp("#c8402f", n=4, shift=1.0, contrast=1.0, name="")` builds the tones of one material around a base colour: tone 0 darkest ... tone n-1 highlight, base at `(n-1)//2`, plus its own outline colour (tone -1).
`ramp9(hue_degrees, step=20, n=9)` is the wide, vivid, strongly hue-shifted ramp of bright game art (9 swatches, or `n=5` for every second one); hue is given at the darkest swatch plus 4 steps, e.g. `ramp9(100, n=5)` for foliage. `Ramp(["#...", ...], line="#...")` takes explicit colours, dark to light. Passing a hex string where a ramp is expected makes an automatic 4-tone ramp. Reuse one ramp object for every part of the same material: that is what keeps the palette small. `print(my_ramp)` shows its colours. A near-white base (cream, white fur, bone) has no room above it, so it becomes the TOP tone and the other tones are its shadows (`my_ramp.base` tells you which tone is the base colour).

### Paint

`c.fill(mask, ramp, form="flat", tone=None, lo=0, hi=None, box=None, depth=None, axis="x", bands=None, dither=0, rim=False, shadow=False, sep=False)`

| form | shape it shades | notes |
|---|---|---|
| `flat` | one tone (`tone`, default the base) | faces of boxes, small parts |
| `ball` | sphere / ellipsoid over the mask's box | `box=(x, y, w, h)` to shade a cut-off mask as part of a bigger ball |
| `tube` | cylinder; follows tapered masks | `axis="x"` upright (shade runs across), `"y"` lying down |
| `puff` | any shape, rounded from its edge inward | `depth` px: small = bevel, default = fully rounded |
| `slab` | flat with a 1 px lit edge and a 1 px dark edge | boxes, planks, buttons |
| `grad` | even tone steps along the light direction | skies, blades; `dither=` works well here |
| `bands` | tones you list, spread across `axis` | `bands="1320"`: metal, glass, stripes |
| `glow` | lit from INSIDE: brightest at `centre=(x, y)` (default the middle), darker toward the edge | lantern glass, flames, magic, lit gems; the other forms only know the canvas light |

`lo` / `hi` clamp the tones used (`lo=1` keeps a part from going very dark). `rim=True` adds reflected light on the far edge. `shadow=True` darkens what lies just beyond this part away from the light (a cast shadow on the parts under it). `sep=True` draws a dark line of the underlying colour around this part. The cast shadow is 1 px (one tone darker) and only falls on parts painted BEFORE this one; for a deeper shadow (under a chin, under a cap) use `c.retone(c.rect(...) & body_mask, delta=-1)`.

`c.put(rows, {"a": (ramp, tone)}, x, y)` hand-places pixels from text rows; `c.px(x, y, ramp, tone)` one pixel; `c.retone(mask, delta=-1)` or `tone=2` changes the tone of painted pixels (seams, grain, a darker far limb); `c.erase(mask)`. A tone past the end of the ramp takes the end tone.

Surface helpers (after `fill`, before `outline`): `c.texture(mask, cell=4, seed=0, deltas=(-1, 0, 0, 1))` breaks a smooth fill into irregular tone chips (hammered metal, stone, bark, hide; then hand-place a few glints so it does not read as noise); `c.seam(line_mask, within=part)` is a groove with its light-catching edge (plates, ribs, panel lines). `c.links(points, ramp, tones=(2, 0), period=2)` is a 1 px chain of alternating tones: paint it AFTER `outline()`.

### Finish

- White or very light subjects: `selout` makes the lit edge too pale to see on light backgrounds; use `outline("dark")`. A gap in the silhouette narrower than 3 px fills with outline (a 2 px notch becomes a dark tooth). `fill(mask, ramp, tone=-1)` paints the ramp's outline colour (ground shadows, deep cracks). A ground shadow under a floating thing: `c.fill(c.rect(x, y, w, 2, r=1), dark_ramp, tone=-1)`, wider when the thing is lower.
- `c.outline(mode="selout" | "dark" | "black", color=None, mask=None, rim=None)` - 1 px outline on the free pixels around the silhouette (or around `mask`). Leave 1 px of margin. `rim=(ramp, tone)` paints the outline pixels facing the light in that colour (a pale rim light on the lit edge, dark line elsewhere).
- `c.aa()` - careful inner anti-aliasing (inside corners of outline stairs go one tone darker). Sprites of about 48 px and up.
- `c.paste(other, x, y)` - compose: build each object on its own canvas, paste far to near.
- `house(name, n=None)` - a ramp of the HOUSE palette (`house_palette.json`, measured from the game's 121 item icons): `steel iron silver leather wood gold copper red navy sapphire purple teal` (`iron` = the dark worn metal of the game's weapons and armour, `steel` = brighter), 7 tones each, with the game's dark line colour. A hex colour picks the family with the nearest tone; `n` = fewer tones. A house ramp also carries the game's tone shares, so `ball`, `tube` and `puff` fills put the tone borders where the game does (steel and leather mostly dark with a small highlight, gold mostly bright). For game assets use it instead of `ramp()`. Limits: families are split by hue, not by material, and the borders are fitted on a top-left lit ball.
- `c.pipe(pts, r=None, w=4, w1=None, caps="round", span=None, lo=0, hi=None)` - a round bar along a smooth curve through `pts`, tapering from `w` to `w1` px, shaded across its width as a cylinder (with a ramp `r`): horns, handles, hafts, tails, tentacles. Returns `(mask, u, v)`: `u` 0..1 along the curve, `v` -1..1 across it, so details go in the bar's own space (`m & (abs(u - 0.4) < 0.05)` = a band, `m & (v > 0.5)` = the far edge). `span=(u0, u1)` keeps one stretch: call again with another ramp to paint a metal band or a grip. `caps="flat"` cuts the ends square.
- `c.pipe(..., closed=True)` - the same bar joined into a loop: a torus-shaded ring of any shape (key bow, shield rim, bracelet). Give it `c.ellipse_pts(cx, cy, rx, ry, angle=0, n=16)` for a tilted oval ring.
- `c.spaced(pts, n, closed=False, offset=0)` - `n` whole-pixel points evenly spaced along the smooth curve through `pts`: rivets round a rim, studs on a strap, beads, stitches, teeth.
- `c.segments(m, u, n, gap=0)` - cut a painted mask into `n` plates along a coordinate `u` (from `pipe()`, or `c.xx` / `c.yy`): finger lames, armour bands, plank rows. Each cut becomes a seam; `gap` cuts empty pixels instead. Returns the plate masks.
- `c.flip()` - mirror the whole painted canvas left to right, in place (one boot, then a flipped copy pasted beside it).
- `c.outline(..., lines={ramp: "#rrggbb"})` - the outline next to that part takes its own colour in any mode (dark red round a flame, deep blue round a gem).
- `c.tidy(bands=False)` - clean-up of the engine's own shading, before or after `outline()`: single-pixel tone specks join their surroundings and 1 px bumps on a tone border are pushed back. Hand-placed pixels (`px`, `put`, `retone`, `texture`, `lock=True`) and the silhouette are never touched. `bands=True` also dissolves hairline tone bands (1 px wide, 5 px or longer, between two other tones of the same material) into the tone beside them: broader tone shapes, but it also eats thin engine-made highlights, so compare before keeping it. Returns the counts. Lint reports the same faults as `orphan_px`, `spur_px` (flagged) and `band_px` (a number only: planks and stripes are bands too).
- `c.merge_colors(dist=30)` - palette clean-up at the end: of two near-identical used colours the rarer becomes the commoner (shared darks and highlights). Clears most "near-duplicate" flags. It edits the ramps, so in an animation create the ramps once and call it on one frame.
- `c.text(string, x, y, ramp, font="5x7" | "3x5", bold=False, style="flat" | "grad" | "bevel" | "bands" | "chrome", shadow=False, mono=False, spacing=1, r2=None)` - lettering; returns the letters' mask (`c.outline("black", mask=m)`). `text_size(string, font, bold)` gives `(w, h)` for centring. Turkish letters are in the 5x7 font (leave 3 px above and 2 below the line).

### Output

- `c.lint(budget=None, quiet=False)` -> `(numbers, flags)` (it prints the report itself unless `quiet=True`); `c.preview(path)`; `c.save(path, scale=1, bg=None, palette=None)`; `c.image(scale, bg, palette)` -> PIL image.
- `export(canvas_or_frames, out_dir, name, scale=1, ms=120, palette=None)` - `NAME.png` (frame 0); for a list of frames also GIF, sprite sheet and JSON; `ms` may be a list with one delay per frame (hold the peaks longer). `lint()` and `preview()` look at one canvas: run them on frame 0 and on the most extreme frame (Godot / Phaser / Unity importers read it). `strip(frames, path)` lays frames side by side for review.
- `palette=` a name from `PALETTES` (`pico8 sweetie16 db16 gameboy`) or a list of colours: every pixel is snapped to it.

### Matching existing game art

Tested 2026-11-13 against four real game assets: the plain engine pass looked "drawn by code" every time; icons of 32-40 px came close to the originals only after matching the reference and 6-9 look-and-fix rounds with hand-placed pixels; a 170 px monster did not get there.

- `python -m pixart measure REF.png --view ref_grid.png` prints size, palette (hex, dark to light), outline colours, edge brightness per side and light direction, and writes an enlarged copy with a coordinate grid. Take the canvas size, outline colour and light from it.
- Colours: build `Ramp([...], line=...)` from the printed palette instead of `ramp()` (its hue-shift recipe does not reproduce a game's own colours). `palette_of(path, n=32)` returns the list; `c.save(path, palette=palette_of(ref))` snaps a drawing to it.
- `python -m pixart compare REF.png mine.png -o cmp.png` puts them side by side; two images of the same size also get a difference map (red = brightness off by more than 40, yellow = drawn in only one). Each round: look, name the 3 worst differences, fix, compare with the previous round and go back if it is not better.
- `python -m pixart refs --style S11 --subject potion --size 24-40 --sheet out/refs.png [--out DIR]` finds hand-made sprites of a subject in a style in the local reference collection (`PixTools/refs`, `index.csv`; tiers open / copyleft / private / ai; packs whose licence forbids AI use are never offered) and draws a contact sheet; `--out` copies them for `look --ref`. `python -m pixart look mine.png --style S11` measures against the style's profile (`knowledge/style_profiles.json`, 23 styles measured on the hand-made refs). Details and the profile table: `knowledge/references.md`. The profile follows the drawing's size bucket (<=24, 25-32, 33-48, >48 px) when that bucket has 20+ sprites from 2+ packs; `python -m pixart profiles` re-measures it.
- Candidates and the user's picks: `python -m pixart cands a.png b.png [c.png] -o DIR --style S11 --axis roughness` puts 2-3 candidates on one numbered sheet (enlarged, 1x on dark and light, with their numbers) and writes `cands.json`; `python -m pixart pick DIR/cands.json N [--judge user|claude|agent]` records the pick in `knowledge/picks.jsonl`; `python -m pixart calibrate [--judge user|all]` says how often the picked one was closer to the style profile (50% = a coin), per style and size and per number.
- `python -m pixart look mine.png --ref REF.png` (or `--ref FOLDER`) prints numbers for how hand-made an image looks and how far it is from the reference: `colours`, `orphans` (pixels with no same-colour neighbour), `small` (pixels in clusters of 1-3), `busy` (pixels touching another colour), `run` (mean run of one colour), `step` (brightness jump between touching colours), `range`, `edge` (outline / inside brightness). `distance` is the mean gap in spreads of the reference set. On the four test targets it put every hand-finished version closer than the plain engine pass; it measures likeness of texture, not whether the picture is good.
- `exemplars/` holds accepted game-asset scripts with an INDEX.md; start a new asset from the nearest one.

Animation = a function of `t` (0..1) that returns a finished canvas; call it for each frame (see `slime`, `coin`, `flame` in `examples.py`).

## Figures: rig, poses, animation

Describe a figure by joint angles, not pixel coordinates. `c.limb(p0, p1, w0, w1)` draws a tapered capsule between two points; a rig gives you the points.

```python
from pixart import humanoid, quadruped, mannequin, head_mask, pose_at, export
from pixart.poses import ACTIONS, P, tween

rig = humanoid(height=40, heads=4)            # side view; bones: spine head arm_{f,b}_{up,lo} leg_{f,b}_{up,lo} foot_{f,b}; _b = far side, _f = near side
rig.add("weapon", "arm_f_lo", 17)             # a bone on the near hand (length in px)
frames, ms = [], []
for pose, t, tag in ACTIONS["slash"]:         # idle walk run slash thrust smash stab bow punch kick shoot block hurt cast
    c = Canvas(72, 60); j = rig.solve(pose, root_x=26, ground=56)     # j[bone] = (start point, end point); the lowest foot stands on y = ground
    parts = mannequin(c, rig, j, skin, top, bottom)                   # a plain figure (far limbs first and darker); or paint your own parts with c.limb(*j[bone], w0, w1)
    if tag == "smear": c.fill(c.crescent(*j["arm_f_up"][0], 27, 232, 118, 7), smear, tone=1)     # the swing frame: trail instead of blade
    else: c.fill(c.limb(*j["weapon"], 2, 1.5), blade, tone=1)
    c.outline(); frames.append(c); ms.append(t)
export(frames, "out", "knight_slash", scale=4, ms=ms)
```

- **Angles** are absolute and the same for every bone: 0 = hanging down, 90 = forward (the way the figure faces), 180 = up, -90 = back. `humanoid(facing=-1)` looks left.
- **Your own pose**: `P(spine=165, arm_f_up=120, weapon=200, root=(2, 0))` = the fighting stance with those bones changed; `root` moves the hips (forward px, down px). `pose_at([(0, A), (0.3, B, "out"), (1, A)], t)` blends keys (eases: linear in out inout snap hold); `tween(ACTIONS["walk"], 1, loop=True)` adds in-betweens.
- **Your own rig**: `Rig({"body": (None, 18, 92, 0), "neck": ("body", 9, 140, 1.0), ...})` = `{bone: (parent, length, rest angle, where on the parent it starts 0..1)}`; `quadruped(length, height)` is ready-made (bones body neck head tail leg_{f,h}{f,b}_{up,lo}). Wings, tails and necks are just more bones; `rig.rest()` is the rest pose to edit.
- `head_mask(c, j["head"], size, wide=1.0)` gives an oval head on the head bone. `c.crescent(cx, cy, r, a0, a1, w)` is the slash trail: a0 = where the swing began, a1 = where the blade is now.
- Draw order is yours: far-side limbs and items first, body, head, near-side limbs last. See `examples.knight`.
- `c.silhouette(path)` saves the one-colour shape: look at it BEFORE shading a complex subject.
- The study notes behind the poses (stances, key poses, measurements per weapon, 8 directions, timing, materials, subject plans) are in `knowledge/`; `knowledge/INDEX.md` says which file to read for which subject.

### Rig and figure reference

| call | what it does |
|---|---|
| `humanoid(height=40, heads=4, facing=1)` | side-view person. `rig.size` = `{"head", "torso", "limb", "height"}` suggested widths in px |
| `quadruped(length=30, height=22, facing=1, neck=None, tail=None)` | four-legged animal; the far leg pair stands a little behind the near pair |
| `Rig({bone: (parent, length, rest_angle, at)})`, `rig.add(name, parent, length, angle=0, at=1.0, back=0)` | your own skeleton; `at` = where on the parent the bone starts (0 start, 1 end); `back` = how far the bone also reaches behind its start (a shaft held in the middle) |
| `rig.chain(name, parent, n, length, angle=0, curl=0, at=1.0)` -> names | n bones end to end, each turned `curl` more than the last: necks, tails, wing fingers. Two chains with opposite curl make an S |
| `rig.solve(pose=None, root_x=0, root_y=0, ground=None, feet=None)` -> `j` | `j[bone] = (start, end)`. `ground` = the y the lowest foot stands on; feet default to every bone named `leg...` or `foot...` (pass `feet=[...]` for other names) |
| `rig.turn(pose, bone, delta)` | a copy of the pose with the bone AND everything attached to it rotated: flap a whole wing, wag a tail |
| `rig.rest()` | the rest pose as a dict to edit |
| `far(j, dx=-2, dy=-1, only=[...])` | the same joints shifted: the far-side twin of a wing or limb (paint first, one tone darker) |
| `c.limb(p0, p1, w0, w1)`, `c.chain(j, names, w0, w1)` | one tapered capsule; a tapered run over a chain of bones |
| `c.membrane(root, tips, sag=0.25)` | wing or fin skin from the wrist out to the finger tips, scalloped between them. Paint before the finger bones, lighter than the body; leave an empty gap between the wing's leading edge and the neck or the silhouette fuses |
| `c.bow(hand, string_hand=None, length=30, angle=180, belly=4)` -> `(bow, string, arrow)` | a bow at the grip hand; with `string_hand` the string is a V to that hand and the arrow is nocked; `None` = at rest |
| `c.crescent(cx, cy, r, a0, a1, w)` | slash trail from angle a0 (start of the swing) to a1 (the blade now) |
| `c.empty()` | an empty mask to start unions from |
| `strip(frames, path, scale=4, sil=False)` | frames side by side, enlarged; `sil=True` = the silhouettes of all frames |
| `lint_all(frames_or_rows)` | lint every frame; prints and returns how many frames raise each flag |
| `hold(frames, **bones)` (in `pixart.poses`) | the same action with some bones fixed in every frame |
| `sheet(rows, path, scale=1, pad=0, bg=None)` | rows of frames (directions x frames, or actions x frames) as one sprite sheet |

**The pose library** (`pixart.poses.ACTIONS[name]` = list of `(pose, ms, tag)`; a pose is a plain dict of bone angles, change one with `dict(pose, arm_b_up=48)`; `P(...)` builds a NEW pose from the fighting stance):

| action | frames | tags in order | notes |
|---|---|---|---|
| `idle` | 2 | hold, hold | 1 px breathing |
| `walk`, `run` | 8 | | loops; contact, down, passing, up, then legs swapped |
| `slash` | 7 | -, -, hold, smear, hit, -, - | overhead cut; swing frame gets `c.crescent` instead of the blade |
| `thrust` | 6 | -, hold, smear, hit, -, - | sword or spear; one line from rear heel to tip |
| `smash` | 8 | -, -, -, hold, smear, hit, -, - | heavy two-hand weapon; the spine folds |
| `stab` | 4 | -, hold, hit, - | knife; no smear |
| `bow` | 6 | -, -, hold, release, hold, - | arm_f holds the bow, arm_b draws: paint arm_b over the torso here; add arrow-flight frames yourself |
| `punch`, `kick` | 4, 5 | -, hold, hit, ... | the kick chambers the knee first |
| `shoot` | 5 | hold, hit, -, -, - | recoil is small; flash on the hit frame only |
| `block` | 4 | -, -, hold, - | the shield arm is arm_b |
| `hurt` | 3 | hit, hold, - | |
| `cast` | 6 | -, -, hold, release, hold, - | staff or hand raised, then thrown forward |

`tween(frames, extra=1, loop=False)` returns the same kind of list with eased in-betweens added (never before a smear frame). `pose_at(keys, t, loop=False)` takes `[(time, pose)]` or `[(time, pose, ease)]`.

**Order of painting**: far-side limbs and items, body, head, near-side limbs, `outline()`, and only then 1 px things that must stay thin: bow string, arrow, whiskers, fishing line, a blade edge highlight. An outline around a 1 px line turns it into a 3 px bar.

**Canvas size for a figure with a weapon**: body height + 8 above (raised weapon, plume) + 4 below; width = body height x 1.5 for melee swings, x 1.8 when something flies off (arrow, spell). A 40 px knight fits 72x60, a 48 px archer 88x64, a 64 px-long dragon with spread wings wants about 96x80: if the subject plan does not fit the requested size, shrink the parts, not the margin.

### Directions: front, back and all 8 from one pose

A pose is defined once (in the figure's own side plane). `rig.solve(pose, direction=...)` turns it to face any way in a top-down 3/4 view. Nothing is mirrored, so the weapon stays in the right hand, the shield on the left arm and the light on one side in every direction.

```python
from pixart import humanoid, mannequin8, face_point, sheet, DIRS       # DIRS: E 0, SE 45, S 90 (toward the viewer), SW 135, W 180, NW 225, N 270, NE 315
rig = humanoid(36, 4); rig.add("weapon", "arm_f_lo", 13); rig.add("shield", "arm_b_lo", 1, 90)       # _f bones = the figure's right side, _b = its left
rows = []
for d in ("S", "SE", "E", "NE", "N", "NW", "W", "SW"):
    row = []
    for pose, ms, tag in ACTIONS["walk"]:
        c = Canvas(56, 52); j = rig.solve(pose, root_x=28, ground=48, direction=d)       # j.order = bones far -> near, j.depth[bone], j.dir
        mannequin8(c, rig, j, skin, tunic, legs, eye=eye, paint={"weapon": draw_weapon, "shield": draw_shield, "head+": draw_hair})
        c.outline("dark"); row.append(c)
    rows.append(row)
sheet(rows, "out/hero_walk_sheet.png")                       # the game file: one row per direction, one column per frame, transparent
sheet(rows, "out/hero_walk_review.png", scale=3, bg="#606068")   # the one to look at
```

- `mannequin8(c, rig, j, skin, top, bottom, shoes=None, eye=None, paint=None)` paints every bone in depth order, far-side parts one tone darker, the torso wider toward front and back, eyes where the face shows. `paint = {bone: fn(c, j, bone)}` draws your own things inside that order (extra bones such as weapon, shield, cape, or a replacement for a standard bone); `"head+"` runs right after the head (hair, helmet, beard). Each fn returns its mask.
- Painting everything yourself: `for b in j.order: ...` with `c.limb(*j[b], w0, w1)`; `body_width(rig, j)` gives the torso width for the direction; `j.depth[b] < 0` means the part is on the far side.
- `face_point(rig, j, fwd, lat, up)` -> `(x, y, visible)`: a point on the head in head sizes from its centre (eyes `fwd=0.22, lat=+-0.22`; the hair mass sits at `fwd=-0.18, up=0.12`; `visible` is False when the point is on the far side, e.g. the face from behind: then draw hair only).
- `tilt` (default 0.45) is how much ground depth shows as height: 0 = a flat side-on game, 0.45 = the usual RPG view, 0.5 = "isometric" 2:1.
- Things the projection does for you: the body is narrow from the side and wide from the front, a weapon pointing at the viewer shortens to a stub, a step toward the viewer becomes a small vertical foot shift, the far arm and leg go behind the body.
- Things it does not do: the head and torso are still an oval and a capsule (no nose, no chest shape), so add the identifying details per direction in `paint` using `face_point` and `j.depth`. Only the humanoid has sideways offsets (`rig.lat`); for your own rig set `rig.lat = {"wing_r_0": 5, "wing_l_0": -5}` (children inherit).
- 4-direction games use `("S", "E", "N", "W")`. `examples.adventurer8` is the full pattern (hair that covers the head from behind, shield arm held in guard during attacks).
- Check a set by eye on the review sheet (same height, same feet line, same palette in every row) and with `lint_all(rows)`, which lints every frame and counts the flags.
- **Hide a bone** (legs under a robe): `paint={"leg_f_up": lambda c, j, b: c.empty(), ...}`. A robe or skirt is your own shape on the `spine` entry: a trapezoid from the shoulders to a hem a few px above the feet, wider at the hem; let the hem follow the feet by 1 px so a walk still reads.
- **Hats and helmets** go in `"head+"`: the top of the head is `face_point(rig, j, 0, 0, 0.5)`, a brim sits at about `up=0.4`. Eyes are painted after `"head+"`, 2 px tall on the head's centre row, so hair and brims cannot bury them.
- **Staffs, spears, anything held in the middle**: `rig.add("weapon", "arm_f_lo", 18, back=12)` reaches 18 px beyond the hand and 12 px behind it. The library poses are tuned for a sword (weapon level or raised to strike); to carry something upright use `hold(ACTIONS["walk"], arm_f_up=20, arm_f_lo=80, weapon=180)`, and `hold(...)` likewise fixes a shield arm or straightens a lean.
- **Cell size**: `sheet()` clips what does not fit and says nothing. Size the canvas from the most extended frame (raised staff, flying bolt), then run `lint_all(rows)`: "touches the canvas edge" on any frame means the cell is too small. `humanoid(height)` is the BODY height: a tall hat or plume comes on top of it.
- A point in front of the figure in the current direction (where a spell or arrow should appear): add a helper bone, e.g. `rig.add("fx", "weapon", 9, 90)`, and use `j["fx"][1]`.

## Lint flags

| flag | meaning | usual fix |
|---|---|---|
| N colours, budget B | palette too big (16 up to 48 px, else 32) | fewer tones (`n=3`), share ramps |
| near-duplicate colours | two colours nobody can tell apart | one ramp for both, or move a base colour |
| pure black used | | a tinted dark |
| touches the canvas edge | no room for the outline | move or shrink, or a bigger canvas |
| thin parts | much of the silhouette is 1 px wide | make limbs 2 px (fine for a string or a blade tip) |
| ramp: tones too close | a step that will not read | `contrast=1.3`, or fewer tones |
| single-pixel tone specks | noise in the shading | simpler form, or `put` them on purpose (hand-placed pixels are not counted) |
| two materials touch in nearly the same colour | e.g. cream spots inside a pale highlight | `hi=` / `lo=` on one of them, or another base colour |
| pillow shading / lone pixels / thick outline / irregular edge steps / flat contrast / harsh contrast | from `pixel_lint` | see `python gizpix.py help pixel_lint` |

`irregular edge steps` (`stair_break` over 0.5) has no location: thick curves (`curve(w=4)` tails) and small triangles (ears) raise it; smooth what you can see at 1x and keep the flag if the silhouette looks clean. `pillow` is the correlation of brightness with distance from the edge: only below -0.5 is it a problem.

Flags are advice. An effect such as a flame is allowed its "flat contrast"; say why you keep a flag.

## Limits (deliberate)

- pixart places pixels exactly but does not know what a cat looks like: the drawing plan is yours (or your agent's). The examples are the starting points.
- No blur, no soft alpha, no free colours: every pixel is a tone of a ramp. That is the point.
- `aa()` only does the safe inner corners; outer-edge AA against a known background is not built.
- Lettering: capitals, digits, punctuation, Turkish; lower case is drawn as capitals.
- Drop step: `knowledge/drop_brief.md` is the prompt for a sub-agent that drops the weakest of 3 candidates on a blind sheet; the user picks from the 2 left (batch100: the user's pick survived 88/100).
