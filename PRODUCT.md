# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Local web app: `python gizpix.py ui` starts a small server on localhost (Python standard library only) and opens the browser; the front end is plain HTML/CSS/JS with no build step and no new dependencies. Confirmed by the owner (recommended option chosen). Not delegated.

## Users

Two audiences, confirmed by the owner:
- Indie game developers and pixel-art hobbyists who generate or draw sprites and want the dull, exact work done (clean frames, cut outfit layers, recolour, pack sheets, draw buildings) without learning a command line.
- The owner and their AI coding agents: the agent runs the commands, the person reviews the result in the UI (before/after, numbers, layers worn on the base) and approves it.

## Product Purpose

Gizpix is a local, free, offline toolkit of about 30 command-line tools for pixel-art sprites. The UI makes the four jobs the owner chose easy to start and easy to judge: cleaning and measuring frames, cutting outfit layers, drawing buildings and villages, and recolouring and packing frames. Success: someone who has never opened a terminal can load frames, see what a tool would do, check the result at pixel level and save it, without any file being changed by accident.

## Positioning

A scriptable, offline chain that works after any sprite generator or hand drawing and never calls a network or an AI service. It measures and shows its work (numbers, before/after, layer worn on the base), and it draws buildings and villages from parameters with no reference image. The UI inherits that promise: nothing leaves the machine.

## Operating Context

- Files in, files out: PNG frames and folders of frames named 0.png..7.png or by direction (south.png, east.png...), JSON specs and styles, GIF and sprite-sheet output.
- Typical flows: (1) load damaged frames, see specks and pinholes flagged, preview the repair, save copies; (2) load a base folder and an outfit folder, cut a layer, view it worn on the base at 3x, save it; (3) choose a building type, style and size, watch a live preview, export PNG/GIF/sheet; (4) shift hue or apply a palette across all frames of an animation consistently, align frames, pack a sheet.
- Judgement happens by eye at 3x and by numbers (`pixel_lint`, `palette_diff`); the tools tell users to always look at the result next to the original.
- Runs on the user's own computer; Python 3.10+ with numpy, Pillow, scipy installed.

## Capabilities and Constraints

- The UI drives the existing tools: every action must map to a real command, and the UI should show that command so people can learn it and agents can reproduce it.
- Tools that edit in place by default (`fill_pinholes`, `colormatch`, `despeckle`, `ground_snap`, `painterly_clean`, `apply_palette`, `apply_pixel_fixes`) must never edit the user's originals from the UI: always write to a separate output folder.
- Layer cutting is measured on one character from one generator; dark outfit over dark skin leaves holes (documented limit): the UI must show warnings and never claim a layer is perfect.
- No network calls from the UI or the server; the server listens on localhost only.
- No accounts, no telemetry, no cloud.
- Terminology to keep: base, outfit, layer, speck, pinhole, ramp, palette, frame, direction, sprite sheet.
- Open decisions (not yet made): UI language (English first, Turkish possible), whether to install as a package, whether the UI ships in the first public release.

## Brand Commitments

Name: Gizpix (renamed from PixTools on 2026-11-11). Offline, no AI calls, free, AGPL-3.0-or-later. No logo, colours or typography exist yet; none are binding.

## Evidence on Hand

- `images/outfit_layer.png`, `images/repair.png`, `images/village.gif`: real before/after demos made by the tools.
- `samples/walk_frames/`: a code-drawn 96x96 character walk cycle, east and south (base, robe, pauldrons, dark-skin pair) for trying the layer tools.
- `pixdraw/gallery_*.png`: renders of every building preset in five styles.
- `MEASUREMENTS.md`: measured results and limits; `HANDOUT.md`: recipes and rules for agents.
- Absent: no user research, no testimonials, no usage data. Do not invent them.

## Product Principles

1. Show the result before touching anything: previews and before/after first, writes only on an explicit save.
2. Never alter originals: outputs always go to a new folder.
3. Numbers and eyes together: every result pairs a pixel-level view (3x, nearest-neighbour) with the measured counts.
4. Teach the command line: show the exact command each click runs, copyable.
5. Be honest about limits: tools state what they cannot do (dark skin, one-generator testing) where the user decides.

## Accessibility & Inclusion

Not specified by the owner. Baseline for a developer tool: keyboard operable, readable contrast, no information by colour alone, UI strings kept in one place so a Turkish translation is possible.
