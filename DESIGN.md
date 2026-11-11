---
name: Gizpix
description: A local pixel-art toolkit UI laid out as an animation exposure sheet, with frames as columns and a checker's red pencil on what needs a look.
colors:
  sheet: "#d9e8d6"
  sheet-raised: "#e8f1e5"
  plate: "#c3d6bf"
  field: "#f6faf4"
  ink: "#1c2a22"
  ink-soft: "#3a4e41"
  rule: "#8fa690"
  rail: "#1c2a22"
  rail-ink: "#e3eee0"
  rail-dim: "#a9bfaa"
  rail-hover: "#2a3e32"
  blue-pencil: "#2d6cdf"
  blue-pencil-deep: "#1d54c0"
  blue-wash: "#c9dcf5"
  red-pencil: "#c4352a"
  red-pencil-deep: "#a42a20"
  red-wash: "#f3d9d4"
typography:
  head:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: "0.01em"
  section:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.08em"
  body:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.45
  note:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.4
  figure:
    fontFamily: "JetBrains Mono, ui-monospace, Consolas, monospace"
    fontSize: "1.0625rem"
    fontWeight: 500
    lineHeight: 1.2
rounded:
  hairline: "2px"
  base: "3px"
  pencil: "999px"
spacing:
  s1: "4px"
  s2: "8px"
  s3: "12px"
  s4: "16px"
  s5: "24px"
  s6: "32px"
components:
  button:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "0 16px"
    height: "40px"
  button-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
  button-primary:
    backgroundColor: "{colors.blue-pencil}"
    textColor: "#ffffff"
    rounded: "{rounded.base}"
    padding: "0 16px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.blue-pencil-deep}"
  button-small:
    height: "32px"
    padding: "0 12px"
  panel:
    backgroundColor: "{colors.sheet-raised}"
    rounded: "{rounded.base}"
    padding: "12px 16px"
  input:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "9px 11px"
    height: "40px"
  rail-job:
    textColor: "{colors.rail-ink}"
    rounded: "{rounded.base}"
    padding: "12px 8px"
  rail-job-current:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
  pencil-mark:
    textColor: "{colors.red-pencil-deep}"
    rounded: "{rounded.pencil}"
    padding: "1px 10px"
  notice:
    backgroundColor: "{colors.red-wash}"
    rounded: "{rounded.base}"
    padding: "12px 16px"
  command:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.rail-ink}"
    rounded: "{rounded.base}"
    padding: "12px"
---

# Design System: Gizpix

## Overview

**Creative North Star: "The Exposure Sheet"**

Gizpix looks like the timing sheet an animator keeps beside the light table. Frames are columns with their numbers above them. A checker's pencil does the marking: blue for the frame you are on, red for the frame that needs a look. The screen sits on pale green sheet stock, with a deep green-grey rail down the left edge for the four jobs. Everything else is hairline ruling, plain type and the user's own pixels.

The mood is calm, exact and a little stationery-like. It is dense enough to show eight frames and their numbers without scrolling, and quiet enough that the 3x sprite previews carry the page. The build rejects the category-default tool shell (grey sidebar, floating cards, a single blue accent on white). The only ornament is the sheet tint itself.

**Key Characteristics:**
- Pale green sheet ground and a dark green rail, light theme only (`color-scheme: light`).
- Frames as table columns; every job reuses the sheet: Clean shows repair counts, Cut shows layer pixels and "Look at", Recolour shows before/after columns.
- Two pencils only. Blue means selection, focus and the primary action. Red means a mark or warning and nothing else.
- Condensed grotesque for heads, labels and column numbers; plain sans for reading; mono for numbers and commands.
- Flat. Hairline 1px rules and tonal steps do all the depth work.
- Previews are real pixels: nearest-neighbour, whole-number zoom, never resampled.

## Colors

A green-tinted paper palette with ink, one blue pencil and one red pencil. No neutral is grey; every neutral leans green.

### Primary
- **Blue Pencil** (#2d6cdf): selection and action. Primary button, checked boxes and sliders, focus rings, selected segmented tab, selected-frame top edge, text selection.
- **Blue Pencil Deep** (#1d54c0): the same pencil as text or hover. Primary hover, current flow step, saved confirmation, current job number.
- **Blue Wash** (#c9dcf5): the selected frame column and folder-picker row hover.

### Secondary
- **Red Pencil** (#c4352a): marks only. The oval around a frame that needs a look, and the border of the warning notice.
- **Red Pencil Deep** (#a42a20): red as text (mark label, notice heading, unchecked-frames flag).
- **Red Wash** (#f3d9d4): warning notice background.

### Neutral
- **Sheet Stock** (#d9e8d6): page ground, sheet header cells, current rail job.
- **Raised Sheet** (#e8f1e5): panels, table body, busy-sweep ends.
- **Plate Green** (#c3d6bf): the ground behind sprite previews, so transparent sprites sit on a visible tone.
- **Field Paper** (#f6faf4): inputs, selects and the inline folder picker.
- **Ink** (#1c2a22): body text, button borders, the command block. Same value as the rail.
- **Soft Ink** (#3a4e41): secondary text, field borders, row heads, hints.
- **Ruled Line** (#8fa690): panel borders, header underline, sheet outlines. Interior sheet lines are Ink at 22% opacity.
- **Rail Ink** (#e3eee0), **Rail Dim** (#a9bfaa), **Rail Hover** (#2a3e32): text, quiet text and hover on the dark rail.

### Named Rules
**The Two Pencils Rule.** Blue marks where you are and what you can do; red marks what is wrong. Neither colours a surface decoratively, and neither is ever the only signal: the red oval carries the words "Needs a look" and the blue column carries the frame number.

**The Green Neutral Rule.** Every neutral is tinted toward the sheet green. A grey or pure white surface is off-system; the field white (#f6faf4) is the lightest value.

## Typography

**Head Font:** Barlow Condensed (with Arial Narrow, sans-serif), weights 500, 600, 700
**Body Font:** Barlow (with system-ui, sans-serif), weights 400, 500, 600
**Number/Command Font:** JetBrains Mono (with ui-monospace, Consolas), weights 400, 500

**Character:** A condensed grotesque that reads like printed column heads on a form, paired with its own plainer sibling for reading text. Mono is reserved for anything a person might compare digit by digit or paste into a terminal. All three are self-hosted (OFL) so the UI never calls the network.

### Hierarchy
- **Head** (700, 1.875rem, 1.05): page title, one per job.
- **Flow step number** (700, 1.5rem, 1): the large 1-4 in the Load / Options / Review / Save strip and the wordmark.
- **Section** (700, 1.0625rem, 1.2, 0.08em, uppercase): panel and section headings (Review, Options, Result, Save).
- **Subhead** (600, 0.9375rem, 1.2, 0.04em, uppercase, Soft Ink): h3 inside panels, frame captions, sheet row heads at 0.8125rem.
- **Body** (400, 0.9375rem, 1.45): reading text, capped near 62ch for intros and empty states.
- **Note** (400, 0.8125rem, 1.4): hints, field small text, legend, footnotes.
- **Figure** (500, 1.0625rem mono; 0.9375rem inside the sheet with tabular numerals): pixel counts, frame numbers, zoom, scrubber value. Command block is 0.8125rem mono at 1.55.

### Named Rules
**The Mono-For-Numbers Rule.** Counts, frame indices and commands are mono; labels for them are condensed. A number in the body sans is a slip.

**The Heading Is A Heading Rule.** Uppercase tracked condensed type is used only on real section, subsection and row headings. It is not a decorative label above other headings.

## Layout

A two-column app shell: a 168px sticky rail and a fluid main area. Main carries a header (title, intro, four-step flow) over a hairline, then a work column and a 296px side column (Options, Result, Save, Command), 20px apart. The work column holds the load line, the three previews, the scrubber and zoom tools, and the exposure sheet. Once a result exists, the Load form folds into one line so previews and sheet fit the first viewport, and Save sits above Command so the primary action stays visible.

Spacing is a 4px-based scale (4, 8, 12, 16, 24, 32), used for gaps and panel padding; panels pad 12px by 16px and sections stack at 24px. Density is moderate and table-tight: sheet cells pad 8px by 10px.

Responsive: at 1180px and below the side column drops under the work column and stops being sticky; at 820px and below the rail becomes a top bar with the jobs in a 2-column grid, the rail footer hides, and main padding shrinks. Previews never fall below 2x at narrow widths. At 1000px tall and 1181px wide or more the side column sticks beneath the top.

### Named Rules
**The Whole-Zoom Rule.** Sprites are shown at integer zoom, `image-rendering: pixelated`, with no resampling. Sheet thumbnails are cropped to the content box at true size.

## Elevation & Depth

Flat. There are no drop shadows. Depth comes from tone (sheet, raised sheet, plate, field) and 1px rules. The only shadow-like device is the inset 2px blue line along the top of a selected frame column, and it is a marking, not elevation. The one animated surface is the busy state, a slow horizontal sweep between Raised Sheet and Plate Green, which stops under reduced motion along with all transitions.

### Named Rules
**The Flat-Sheet Rule.** Nothing floats. A new surface is a bordered, tinted rectangle, never a shadowed card or a modal; even the folder picker opens inline.

## Shapes

Nearly square. Controls, panels, inputs, notices and the sprite ground use a 3px corner; small interior items (focus ring, picker rows, sheet header buttons) use 2px. The one round shape is the red pencil oval (fully rounded, 2px red border) that circles a frame needing a look; it is a hand-drawn mark and is not reused as a pill button or tag. Borders are 1px; empty states use a 1px dashed Soft Ink border. Previews and the exposure sheet are right-angled and unclipped.

## Components

### Buttons
- **Shape:** 3px corners, 1px Ink border, 40px tall (small 32px, icon 32px square), 600-weight Barlow.
- **Default:** transparent with Ink text. Hover inverts to Ink fill with Sheet Stock text, 160ms ease-out.
- **Primary:** Blue Pencil fill, white text, one per screen (Save copies). Hover deepens to Blue Pencil Deep. Disabled keeps its colour at 45% opacity on secondary buttons.
- **Segmented tabs:** a single bordered strip of condensed 600-weight buttons with 1px dividers; the selected segment is Blue Pencil with white text.
- **Focus:** 2px Blue Pencil outline, 2px offset; on the dark rail the outline is a light blue (#9fc3ff) and inset.

### Containers (Panel)
- **Corner:** 3px. **Background:** Raised Sheet. **Border:** 1px Ruled Line. **Padding:** 12px 16px. Panels sit flush in the side column with a 16px gap and carry a Section heading.

### Inputs / Fields
- **Style:** Field Paper background, 1px Soft Ink border, 3px corners, 40px minimum height, 9px by 11px padding. Hover darkens the border to Ink. Labels sit above in weight 500; hints below in Note size.
- **Controls:** checkboxes 18px and range sliders use Blue Pencil as the accent colour.
- **Focus:** the global 2px blue outline.

### Navigation (Rail)
- Dark green rail with the uppercase condensed wordmark, four numbered jobs (mono number in Rail Dim plus condensed 500-weight label), and a footer line "Runs offline" with the originals-untouched promise above a Soft Ink rule.
- **Current job:** inverted to a Sheet Stock block with Ink text and a Blue Pencil Deep number. Hover is Rail Hover. On narrow screens the rail is a top bar with a two-column job grid.

### Exposure Sheet (signature)
- A bordered table in Raised Sheet: frames are columns (condensed 700 numeral heads on Sheet Stock), rows are named in sticky left row heads (uppercase condensed, Soft Ink). Cell lines are Ink at 22%, numbers are mono with tabular figures, thumbnails are true-size crops. The selected frame column is Blue Wash with a 2px Blue Pencil top edge. A frame to inspect gets the red oval and the words "Needs a look"; a checked-by-eye checkbox row closes the sheet. A legend line explains the marks. The sheet scrolls horizontally inside its own border rather than shrinking.

### Flow Strip
- Four condensed steps: Load, Options, Review, Save, each with a large numeral. Done steps get a blue check, the current step is Blue Pencil Deep bold with a 2px underlined numeral.

### Notice, Empty and Busy States
- **Notice:** Red Wash, 1px Red Pencil border, 3px corners, Red Pencil Deep subhead, dark red body text. Used for honest limits (for example dark skin under a dark outfit) and flagged frames; never for success.
- **Empty:** dashed Soft Ink border, bold uppercase condensed lead, explanation capped at 62ch.
- **Busy:** the sweeping plate-green gradient block, at least 120px high.

### Command Block
- Ink background, Rail Ink text, 0.8125rem mono, wrapped, 3px corners; always paired with a Copy button, because the UI teaches the command line.

## Do's and Don'ts

### Do:
- **Do** use Blue Pencil (#2d6cdf) only for selection, focus, the one primary action and checked controls.
- **Do** mark a frame that needs attention with the red oval plus words; keep red for marks and warnings.
- **Do** show every preview as true pixels at integer zoom on Plate Green, and pair it with measured counts in mono.
- **Do** build new results as columns in the exposure sheet with named row heads before inventing a new layout.
- **Do** keep depth to tone and 1px rules; open pickers and details inline.
- **Do** give every control a visible 2px blue focus ring and a 40px (or 32px small) target.
- **Do** keep all UI text in strings.js and the three fonts self-hosted.

### Don't:
- **Don't** use a grey or white neutral, a drop shadow, a modal, or a floating card; the world is flat green sheet stock.
- **Don't** use red decoratively, or as the only signal of a problem.
- **Don't** resample, smooth or fractionally scale a sprite preview.
- **Don't** use the red oval as a generic tag or pill, or add pills elsewhere.
- **Don't** set a number in the body sans, or set a decorative uppercase label above a heading.
- **Don't** claim a result is perfect; show the limit in a notice where the user decides.
