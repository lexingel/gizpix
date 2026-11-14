# Pixel-art craft rules for pixart

What the sources teach, in our own words, sorted by the step where you need it. Each rule says who carries it:
**[auto]** pixart does it when you use the named call, **[lint]** `c.lint()` measures it, **[you]** you decide and look.

Sources (studied 2026-11-13; sections 14-17 add the user's weapon reference collection and web research, see `knowledge/INDEX.md`): *Pixel Logic* (M. Azzi; ch. 1-6 of the unfinished edition), *Make Your Own Pixel Art* (J. Dawe, M. Humphries),
*Pixel Secrets*, *Arcade Game Typography* (T. Omagari), Derek Yu's pixel-art tutorial (basics + common mistakes), Tsugumo's "So you want to be a pixel artist?".
Where they disagree the more specific one wins and it is said so.

## 0. The ten rules that matter most

1. **Silhouette first.** Filled with one colour, the subject must still be recognisable. Build the big masses, then carve. [you; preview shows it]
2. **One light for the whole picture**, usually above-left. Planes facing it are light, planes facing away are dark. [auto: `Canvas(light=)`]
3. **Shade forms, not outlines.** Every part is a sphere, cylinder, box or soft lump lit from that light. Shade that follows the outline all round is "pillow shading", the classic beginner mistake. [auto: `form=`; lint: `pillow`]
4. **Few tones, far apart.** 3 tones + a highlight per material; 2-3 on small sprites; about 16 colours per sprite, 32 for a scene. Two colours you cannot tell apart are one colour too many. [auto: ramps; lint: colours, near-duplicates, ramp steps]
5. **Shift the hue along a ramp**: shadows cooler (toward blue/purple), highlights warmer (toward yellow), never just "add black / add white". No pure black. [auto: `ramp()`]
6. **Clean lines**: 1 px thick, no doubled corners; along a curve the step lengths shrink steadily into the bend and grow after it; a straight slope keeps one step length. [auto: `line`, `curve`, `oval`, `outline`; lint: `stair_break`, `thick_line`]
7. **Nothing 1 px thick** that needs shading: limbs, branches, handles are at least 2 px. [lint: thin parts]
8. **Outline by role**: light-aware coloured outline ("selout") by default, black for game characters on busy backgrounds, none for backgrounds and effects. Inner lines are a dark tone of the local colour, not black; better still, separate parts by colour. [auto: `outline(mode)`, `sep=`, `shadow=`]
9. **Judge at 1x**, on dark, light and mid backgrounds, and in greyscale. Zoomed in everything looks fine. [auto: `preview()`; you look]
10. **Details last, and fewer than you think.** When it is too small to fit, drop it; do not squeeze it. Stop when it reads.

## 1. Before drawing [you]

- **Canvas size from the smallest feature that must read.** Give that feature the pixels it needs and derive the rest. Usual sizes: 16x16 tile or tiny map sprite, 16x24 small character, 24-32 icon or item, 32 first sprite, 48-64 character with a face, about 100 tall = large fighting-game sprite, up to about 250 for an illustration. Tiles are exact squares (16 or 32). Leave 1 px free all round for the outline.
- Name the subject's **3-5 identifying features** (elephant: trunk, ears, tail) and 1-2 **charm points** to exaggerate; they must survive the picture at half size.
- **One projection per picture**: side view, top-down (camera about 45 degrees: you see fronts and tops), or isometric (lines step 2 px across per 1 px up). Never mix.
- **Palette**: one main colour for most of the subject, one contrasting colour for its features, 2-3 main colours in all. Avoid the naive colour (pure green leaf, pure grey stone): tint it. Warm palettes read friendly, cool ones cold or sad. Start each ramp from a mid base so there is room both ways.
- **Contrast grows as size shrinks**: small sprites need big value steps (`ramp(contrast=1.2)`); strong light means a wide value range, dim light a narrow one.

## 2. Work order

Under about 32 px start from coloured shapes, not from line art (Derek Yu). That is how pixart works at every size:

1. masks for the big masses (silhouette) -> look at the silhouette
2. `fill` each part with its ramp and form, back to front (far parts first)
3. cast shadows between parts (`shadow=True`), far-side limbs one tone darker (`retone`)
4. material marks: a few uneven strokes, not a pattern (`retone` on short lines)
5. hand-placed pixels: eyes, glints, mouth (`put`, `px`)
6. `outline`, then on big sprites `aa`
7. `lint` + `preview`, look, fix, at most a few rounds; then stop

Fix order when cleaning: outline jaggies, shading-edge jaggies, banding, anti-aliasing last.

## 3. Lines and edges

- Run rule on curves: good 4-3-2-1-1-1-1-1-2-3-4, bad 4-3-2-1-1-1-2-1-3 (a short run between two longer ones is a jaggy). [auto in `oval`, `curve`; `stair_break` in lint]
- Straight slopes use one step: all 1s (45 degrees), all 2s (the isometric 2:1), all 3s. Prefer such angles for long straight edges. [you: choose end points so dx is a multiple of dy or the reverse]
- A 1 px line has no L-corners: every line pixel touches two others. [auto: pixel-perfect paths]
- One line weight per picture: all 1 px, or a deliberate 2 px contour with 1 px inner detail.
- The boundary between two tones is a line too: keep it as smooth as the outline. [auto: tone clusters are cleaned]
- Organic things want curves, manufactured things straight edges. A straight waistline or stiff straight limbs give the "cardboard" look.

## 4. Light and form

- Sphere: crescent bands offset toward the light, a small highlight, darkest crescent on the far rim, optionally a thin reflected light on that rim. [`form="ball"`, `rim=True`]
- Cylinder: a light band off-centre toward the light, shadow on the far side. [`form="tube"`, `axis`]
- Box: one flat tone per face: lit face lightest, side middle, away face darkest; no gradient inside a face. [three `fill`s with `tone=`, or `form="slab"` for a lit and a dark edge]
- Cone: wedges from apex to base, the lightest wedge toward the light. [`form="tube"` on a triangle mask follows the taper]
- Any soft shape: rounded from the edge inward but lit from one side. [`form="puff"`; small `depth` = bevel]
- A part between the light and another part **casts a shadow** on it. [`shadow=True` on the upper part]
- More shadow pushes a part back: the far leg is fully dark, the near leg carries the light. [`retone(mask, delta=-1)`]
- Never bright in the middle with both sides dark (front light): it is dull and symmetric. [lint: `light_x` near 0 on a round form is a hint]
- The darkest tone lives inside areas that are already dark, never alone in a bright area.
- Faces get less contrast than bodies; one flat skin tone plus a shadow is enough when small.
- Back light: the side toward the viewer is dark, only a thin rim on the light's side is lit.

## 5. Colour

- A ramp = the tones of one material, dark to light: line colour, shadow, base, light, highlight. [`ramp(base, n)`: n=3 small, 4 default, 5 big]
- Hue shift per step: shadows about 5-10 degrees toward blue/purple and a little more saturated; highlights about 15-20 degrees toward yellow and less saturated (measured from the books' examples). Yellow needs a bigger brightness step than other hues. [auto]
- No pure black, no pure white for shading: darks are tinted (deep purple, dark brown, navy), e.g. one shared dark neutral for every ramp. [auto: each ramp's `line`; lint flags #000000]
- **Share colours** to shrink the palette: one common darkest tone, a mid tone of one ramp used as another's highlight, skin tone for a white shirt. Reduce in this order: drop barely visible tones, replace greys with a neighbour ramp's tone, merge highlights, fuse close ramps, fuse all darks. [you: pass the same `Ramp` to several parts; `export(palette=)` snaps to a fixed palette]
- Two different things that touch must not share the touching colour.
- Focus: the important thing has the highest saturation and contrast. Background: lower contrast than the sprite, or the player has to search for the character.
- Greyscale test: with saturation removed the tones of a ramp must still be clearly ordered. [lint: ramp steps; preview shows greyscale]
- Night version: swap the palette to darker, less saturated colours; do not redraw.

## 6. Outlines

| mode | what | use |
|---|---|---|
| `selout` | each part's own dark line colour, lighter where the edge faces the light | default; sits on dark and light backgrounds |
| `dark` | each part's own dark line colour everywhere | coloured outline, calmer |
| `black` | one dark colour | game characters on busy backgrounds, tiny palettes, lettering |
| none | the darkest tone at the edge does the job | backgrounds, far objects, effects (fire, glow, magic) |

- Outline-to-fill contrast must stay high even when coloured. Thicker and darker pulls forward; thin, light or none pushes back.
- Small sprites: outline the silhouette only; divide the inside by colour and value. A black line across a face or between hair and skin makes a 16 px sprite muddy.
- Selout test: hide the fill; the light direction should be readable from the outline alone.

## 7. Anti-aliasing and dithering (both off by default)

- AA = an in-between colour in the inside corner of a stair step, about half the step long; 1 shade, 2 at most; 45 degree lines get none. Too little beats too much.
- **Never on the outer edge** of a sprite that will sit on an unknown background: inner side of the outline only. Skip it on tiny sprites and between low-contrast colours. [`c.aa()` does only the safe inner corners]
- Dithering: default none. Use it for large gradients (sky), very small palettes, glow edges, rough textures; never on small or animated sprites (it shimmers) and only between two close colours. Checkerboard family only: no two same-colour pixels side by side, rows offset by one. [`fill(dither=0..1)`]
- A smooth even gradient reads as plastic; flat tones with a few nicks read as material.

## 8. Readability

- Features need breathing space: a mouth must not touch nose or chin. No tangents (unrelated shapes that just touch).
- A feature too thin to read gets 2 px by moving its neighbours. A 2x2 pupil reads; a pupil fused with the outline does not.
- Eyes are found first: spend pixels there. Under 1 px of eye: draw the socket shadow instead. One light pixel of eye shine changes the expression; put it in the same spot in both eyes.
- At small sizes replace lines with value: dark pixels separate, the brightest pixels mark edges and key details.
- Three sizes of form: big calm masses, medium shapes, a few small high-contrast details at the focal point.
- Mirror test: flip the picture; if it seems to tip over it is unbalanced.

## 9. Characters

- Proportion follows the job: a big head gives room for a face and identity (chibi: head about half the height); realistic proportions need pose and anatomy to read.
- 16x16 top-down RPG character (Tsugumo): head 10 rows, torso 3, legs 3; eyes 2 px tall, 2 px apart, 1 px from the side of the head, 1 px above the jaw; hair is the main identifier. Even widths have no centre column: plan nose and leg gap for two middle columns.
- Hands: a mitten first; thumb and index define it; separate fingers by tone, not lines.
- Hair: sections that follow the skull, top lightest. Mouth and nose: a skin tone a little darker than the skin shadow, not black.
- Different characters need different silhouettes: vary body shape, hair and pose.

## 10. Materials (recipes; the sources give few, these are the ones they do give plus the standard ones the forms make possible)

- **Metal**: high contrast, hard-edged bands, a bright streak beside a dark one. `form="bands"`, e.g. `"1320"` across a blade or `"231"` on a strap; two tones split by a ridge on a blade.
- **Glass**: light shell that never goes very dark (`lo=1`), the content drawn inside (`shrink`), one diagonal glint, a bright surface line on a liquid.
- **Wood**: `slab` or `tube`, then seams and a few short grain strokes one tone darker; edges dented, not ruler-straight, on old wood.
- **Stone / brick**: irregular dented edges; a worn brick has a solid dark bottom and side edge that breaks into stray pixels toward the middle; darkest tone only inside dark areas.
- **Foliage**: overlapping spheres under one light, lobes separated by a sudden tone change (not black lines), yellow-green where the light hits.
- **Grass**: short strokes of 1-4 px in 2-3 greens, uneven; vertical strokes = tall grass. Light for blades, dark for the ground.
- **Fire**: outer orange teardrop, inner yellow teardrop that moves every frame but never breaks out, pale core, 1-2 px sparks on strong frames; no outline.
- **Glow**: concentric discs, smallest white, each larger one darker; dither the outer edge. **Laser**: white core line with a thinner coloured line each side.
- **Cloth / skin / matte things**: 2-3 soft tones, low contrast. Shiny things: more contrast and a small hard highlight.

## 11. Depth, scenes, tiles

- Distance = lighter, greyer, flatter, less detail, thinner or no outline. Fog recipe: blend toward grey 0 % near, 40 % middle, 80 % far.
- Build every object on its own canvas (own outline), then `paste` into the scene, far to near. Sky and ground can be their own canvas with their own light (bright horizon: light from below).
- Tiles: judge them repeated (3x3), never alone; no feature that returns visibly every tile (long lines, bright blobs); detail spread and wrapping across the edges, not clumped in the centre; one base tile plus 3 variants. Connections meet at the edge midpoint. A flat one-colour tile reads as metal or glass. [`gizpix tile_check`]

## 12. Animation

- Same canvas size and one palette for every frame; no colours flashing in and out. [`export(frames)` shares one palette]
- Frame counts: 2 = only tiny sprites, 3-4 = small walk (contact, down, pass, up), 6-8 = full walk; an attack about 7 with a short wind-up and a held hit frame. No more frames than the motion needs.
- Never equal delays: hold the peak twice as long; ease in and out.
- Draw one finished frame, then move chunks of pixels; redraw only what changes. Keyframes first, on an arc ("path of motion"), with anticipation (weight goes back before going forward).
- Small moves are big: 1 px is 4 % of a 20 px sprite. Breathing on a 100 px sprite is 1-2 px.
- Keep the volume: a squashed blob gets wider. A flipped frame must have its light repaired (in pixart: draw the frame mirrored with masks, the light stays).
- No dithering on moving sprites.

## 13. Lettering (from the arcade fonts)

- Cell 8x8 with one empty column and row for spacing: letters live in 7x7 at most; capitals at least 5 px tall (B E S 2 3 5 6 8 9 need it), 6-7 the norm.
- Classic weight: 2 px upright stems, 1 px bars, 45 degree corner cuts instead of curves. [`text(bold=True)`]
- Counters (the holes of A B R 4 6 8) stay open, also after shadow and outline. Look-alike pairs must differ: O/0, B/8, S/5, D/O, 4/9.
- Numbers get the most care; scores are fixed-width so they do not jitter. [`mono=True`]
- Colour per row, 3-4 colours a glyph: vertical gradient, highlight top row + shade bottom row, bevel (light top-left, dark bottom-right), chrome (blue sky lightening to a white horizon, then dark earth warming downward). [`style=`]
- A drop shadow (1 px right and down) or outline lifts text off a busy background and doubles as the letter gap. Judge real strings at 1x on the real background.

## 14. Armed characters and attack animation (from the weapon reference study; details in `knowledge/weapons_*.md`)

- **Every stance is staggered**: feet 1-1.5 shoulder-widths apart front to back, both knees bent, torso leaning 5-15 degrees forward. A figure standing straight with a weapon reads as a mannequin. [auto: `poses.STANCE`]
- **Keep the weapon clear of the body**: the default sword idle has the hands at the lead hip and the blade 20-30 degrees up-forward, tip at face height, nothing crossing the torso. A weapon drawn over the character's own body disappears.
- **Attack = hold, one swing frame, hold**: anticipation held 2-3 frames, the swing itself ONE frame carrying a smear, the end pose held 2-3 frames (longest), recovery slower than the strike. A 10-frame overhead slam is 3 + 1 + 3 + recovery. [auto: `ACTIONS` timing and tags]
- **Smear**: one flat near-white colour, no outline, appears at full size on its first frame and only decays (269 -> 118 -> 33 px in one reference); a 1 px point where the swing began, 6-8 px thick at the blade; its outer edge is the path of the tip; the blade is not drawn on that frame; 1-1.5 body heights across. Fade without alpha: keep only the rim, split the tail into streaks, or drop to one blue-grey. [auto: `c.crescent`]
- **The weapon decides the trail**: sword = filled crescent (150-180 degree arc from the shoulders); katana 90-180 with a step, the draw cut a flat sweep at chest height; knife = 60-90 degrees from the elbow, no smear; hammer = thin hollow path line plus ground ticks and dust; spear and thrusts = a straight wedge (1 px at the hand, 3-4 at the tip) for 1-3 frames.
- **Thrust**: one straight line from the rear heel through the spine to the tip, rear leg straight, lead knee deep, arms locked, blade level. An arms-only thrust with an upright body reads stiff.
- **Weight shows in the spine and the timing**: light weapons bend the torso 10-30 degrees; two-hand hammers, picks and great axes fold it 45-80 with hips back; their lift takes about 5 frames, the top 2, the downstroke 1-2, the low hold 3.
- **Bow**: at full draw the string is a V of two straight lines meeting at the string hand on the jaw; limbs bend into a deep D; arms and arrow form a T. On release only the string hand moves (back along the jaw), the string goes straight, the bow arm stays up. A straight string with no arrow at full draw is the classic error.
- **Shield**: held at arm's length, top edge under the eye line, sword hand close behind; a round shield spans chin to hip (about 40 % of body height on small sprites). A block is the shield jumping up 5-6 px in one frame while the body moves 1-2 px.
- **Punch and kick**: a straight punch is one line rear heel - spine - fist; a kick needs a knee-chamber frame first and the torso leaning AWAY 30-45 degrees.
- **Guns**: recoil is tiny - only the arms-and-gun layer shifts 1 px back on a 37 px body, or a pistol forearm tips up about 45 degrees for 3 frames. Muzzle flash 1-2 frames, white-yellow, no bigger than the head. Rifle: stock in the rear shoulder, head tipped onto it, torso 10-15 degrees forward, support hand at mid-barrel.
- **How weapons are drawn small**: blade 1-2 px in the brightest tone of the sprite; crossguard a 3-5 px bar across it (the one detail that makes a line a sword); shafts a 1 px colour core in a dark outline; hands 2x2 or 3x3 blobs with no drawn grip; weapon heads oversized (an axe head over half the body height at 45 px).
- **Armour at sprite size**: plate = separate convex plates each with its own top-left highlight on a high-contrast 4-5 step ramp, wide pauldrons, pinched waist; at about 21 px it is 3 steel tones, a helmet dome with a dark slit and one oversized plume. Capes and skirts are pinned at the collar, the hem lags the body by a beat (1-2 px per frame).
- **Hit sparks**: ring or disc -> jagged directional fan with 2-3 streaks -> shards -> dots; about 2 frames to the peak, 8-10 to die; late frames shift hue and thin out rather than darken.

## 15. Timing numbers (web research; details and sources in `knowledge/animation_and_cleanup.md`)

| action | frames | per frame |
|---|---|---|
| idle (breathing) | 2-4 | 300-500 ms |
| walk | 4-8 (contact, down, pass, up; second half = legs swapped) | 100-150 ms |
| run | 6-8 | 60-100 ms |
| attack | wind-up, 1 swing, held impact, recovery | wind-up 60-80 ms a frame, impact held 120-200 ms, recovery 80-100 ms a frame; never uniform |

- A player's total wind-up stays near or under 100 ms or it feels like input lag; an enemy's signal plus strike lasts at least 340 ms so it can be read.
- Hit-stop: freeze both sides on contact, longer for heavier hits, capped (about 8-15 frames at 60 fps for a heavy hit).
- Cutting frames keeps the loop length: 8 frames at 80 ms = 4 frames at 160 ms; drop recoil frames first, then high points, never contact or passing.
- Body bob: 1 px at 16 px, 1-2 px at 32 px, about 4 % of height walking and 12 % running; rise faster than fall. [auto: `rig.solve(ground=)` bobs from the leg poses]
- Squash and stretch: 1-2 px for 1-2 frames, area kept. Hair, capes, tails trail 1-2 frames or move 1 px the opposite way.
- Sub-pixel motion: keep the outline, shift the edge tones through the ramp (1 px over about 5 frames); slow moves only (breathing, a blink), and in all animations of a character or none.
- Clean-up order and stop rule: orphan pixels (a single pixel of a colour, unless it is a highlight, an eye or an AA pixel), jaggies, banding (two neighbouring runs with the same start and end), AA last; stop when a change no longer shows at 1x.

## 16. Directions (details in `knowledge/eight_directions.md`)

- [auto] In pixart nothing needs mirroring: `rig.solve(pose, direction=)` turns one pose to all 8 directions with the weapon hand, shield arm, draw order and light kept right. The rules below are what hand-drawn sets do and what to check for.
- Draw 5, mirror 3: N, NE, E, SE, S are drawn; NW, W, SW are mirrors of NE, E, SE. N and S never mirror. A flip swaps the weapon hand and the shield arm and reverses the light: repair both or accept it knowingly.
- Width by view at the same height: front/back 1.0, 3/4 about 0.8, side 0.45-0.55.
- Draw order with weapon right / shield left: the near-side item over the body, the far-side item behind it. Facing E the weapon is in front, facing W the shield; facing S the shield covers the torso, facing N the body hides it.
- A weapon pointing along the view axis shrinks to a stub; upright staffs and spears keep their length; a bow is a line in N and S.
- Consistency across directions: same height, same feet line, same head volume, same palette, same pivot. Row order differs between asset packs: check the facing by the face, not the label.
- 3/4 from front: shift the centre pixels to one side, far arm and leg slightly higher. Back from front: redraw the head without a face.

## 17. Materials and subjects (details in `knowledge/materials_and_subjects.md`)

- Tones by size: 16 px = base + 1 shadow; 32 px = 3; 48 px = 3-4; 64 px and up = 4-5.
- The length of the highlight is the material: metal a long bright streak, glossy things a few specular pixels, dull things none. Polished metal: high contrast, a sharp 1-2 px highlight on the lit EDGE of a tube (never down the centre), dark reflection beside it; steel speculars are pale blue; gold is yellow with orange shadows and a white specular.
- Flat faces get one tone each; ramps only on curved surfaces (cube = 3 flat tones; gem facets and rock planes the same).
- Fire from inside out: near-white core, yellow, orange, deep red edge, never brown; base still, tips moving. Still water = the scene flipped and a little shorter with aligned highlight dashes.
- Humanoid: 16 px = 2-3 heads, 32 px = 3-4, 48 px and up = 4-6; arms 1 px wide at 16 px; eyes 1x1, then 1x2, then 2x2 with a 1 px shine at 32 px.
- Dragon: 64 px minimum; S-curve neck, tail at least as long as the body, wings built like arms on big shoulders above the front legs; folded wings are one compact shape on the back, spread wings about as wide as the body is long.
- No bottom outline where an object stands on the ground; glowing things get a coloured outline.

## 18. Styles and genres (digest of the Slynyrd Pixelblog, posts 1-64; table and numbers in `knowledge/styles.md`)

- A style is a few parameters: head-to-body ratio, limb thickness, outline on or off, colours per sprite, sprite and tile size, projection. Fix them from the request or the genre it implies before planning the subject.
- Size ladder: 8x16 tiny run 'n gun; 16x16 or 16x32 NES-style hero (3 colours + 1 shared per sprite); 16x32 or 26x32 top-down RPG hero on 16 px tiles; 32x48 fantasy knight; 32x32 isometric unit on a 32 px cube; 48x92 fighter; 29x96 realistic 8-head figure; 16x16 item icons in 6 colours or fewer.
- Build order for characters: colour-coded flat dummy, joint lines, flat local colours, big light clusters, refined clusters, outline last as a darker shade of the neighbouring fill (black only for hardware-era looks).
- Hard things (rocks, mountains, asteroids) are angular planes with one value per facet; soft foliage is stacked sphere-shaded bundles; texture is a few repeated cluster stamps against empty space, never every brick.
- Depth for backgrounds: start from the atmosphere colour; each plane further back is lighter, greyer and nearer the sky hue; behind gameplay push every background layer saturation -20, contrast -15, brightness +15.
- Action readability: bullets and pickups bright with a white outline, ships and enemies dark-outlined.
- Timing by genre (ms per frame): top-down sword 100/50/50/50/100/50, spear 200/50/50/50/150/50, hammer 250/50/50/50/300/100; fighter light 50/100/50/50/50, heavy 50/50/50/100/100/50/50; smear frames 50 ms and only on the strike; head bob is a triangle wave (down 1, down 1, up 2).
- Loops: a parallax layer's speed must divide the canvas width; canvas width = loop frame count gives a perfect loop.
- [auto] `ramp9(hue)` builds the series' 9-swatch ramp (hue +20 degrees per step, S 20-75-15, B 15-100).

## 19. Mistake checklist (what the lint and your eyes look for)

pillow shading - too many or too similar colours - pure black - naive colours - jagged curves, doubled line pixels - 1 px limbs - outline everywhere in black on a tiny sprite -
symmetric front-light shading - banding (stacked tone bands with the same ends hugging each other or the outline) - gradient-tool plastic - dithering on small or moving sprites -
AA on the outer edge - sprite lost on some background - tangents and cramped features - mixed projections or pixel sizes - non-integer scaling, JPG - unequal frame delays.
