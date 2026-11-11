---
version: 1
slug: "ui-web-index-html"
primary_target: "ui/web/index.html"
related_targets: []
---

# Surface brief: Gizpix web UI (ui/web)

Mode: Operate. Scope: the local web app that drives Gizpix's four jobs (Clean & measure, Cut outfit layer, Draw buildings, Recolour & pack). Audience: game developers and pixel-art hobbyists new to the command line, and the owner reviewing results their agents produced. Task: load frames, see what a tool would do, judge the result by eye at 3x and by numbers, save copies, copy the command. Constraints: local only, originals never changed, UI strings in one file for translation, no build step. Chosen by an independent scored review (composite 75.6 of six sketches; detector and heuristic findings from the sketch to be fixed in the build: real scrubber control, 3x previews at true size, no cramped padding or skipped headings, a shape for every job).

## Direction contract

THESIS: The animation exposure sheet: frames are columns on a timing sheet and a checker's red pencil circles what is wrong. The screen refuses the category-default tool shell of a grey sidebar, cards and one blue accent.
OWN-WORLD: Pale green sheet stock (#d9e8d6) under the work area, deep green-grey rail (#1c2a22), ink #1c2a22, blue pencil #2d6cdf for selection and focus, red pencil #d03b2f for marks and warnings only. Condensed grotesque (Barlow Condensed) for column heads, numbers and labels, a readable sans (Barlow) for text, JetBrains Mono for numbers and commands. Hairline rules like ruled sheet lines; no ornament, no textures beyond the sheet tint.
STORY: A newcomer understands in seconds that frames sit side by side with their numbers, picks a job in the rail, sees each frame's result as a column, trusts it because the numbers and the 3x picture agree, copies or learns the command, and saves copies knowing originals stay untouched.
FIRST VIEWPORT: Left rail (four jobs, active one marked, offline and originals-untouched line at the foot). Top: four-step flow (Load, Options, Review, Save). Centre: three true 3x previews in a row (Base, Outfit, Layer worn on base) with a real frame scrubber 0-7 and east/south tabs. Below: the exposure sheet table, frames as columns, rows Layer px, Leak px, Checked; selected frame in blue pencil, a problem frame circled in red pencil. Right column: options checkboxes, result totals, the command with Copy, and the primary Save copies button with its originals line.
FORM: Animation Exposure Sheet, position 1 on my grounded list of seven; seed:6e777cae50e748ac. Signature move: frames as columns with per-frame numbers and a red-pencil circle on the frame that needs a look, reused by every job (Clean shows speck counts per frame, Draw shows a column per animation frame, Recolour and Pack show before/after columns).
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved decisions
UI language is English first; strings are isolated for a Turkish translation. Installable package not decided.

## Recorded adaptations (decided during the build, from the finish review)
- East/south direction tabs are replaced by a sample dropdown and the two folder fields: each direction is just a folder, so a new user can point at any of them.
- The "Leak px" row is replaced by "Look at" (the frame is circled when its layer size is far from the median) because the tool does not measure leaks per frame; the Clean job shows its own measured rows (repaired px, odd-colour px, pinholes).
- Pack mode shows the packed sheet and the preview GIF with the file list, not before/after columns; Recolour keeps before/after columns.
- Sheet thumbnails are cropped to the content box at true size (never resampled).
- Once a result exists the Load form folds into one line so the previews and the sheet fit the first viewport; Save sits above Command so the primary action is in the first viewport; the flagged-frame notice and an unchecked-frames line sit with Save.
- Narrow windows: the rail becomes a 2x2 grid, previews never fall below 2x, the side column drops under the work area.
