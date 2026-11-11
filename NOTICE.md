# Notice

Gizpix is licensed AGPL-3.0-or-later (see `LICENSE`). Images you make with it are yours; the licence covers the code.

- **Code**: every tool and the `pixdraw` package were written for this project. Some ideas came from public pixel-art practice (rules of thumb for outlines, specks, stair-steps, palette ramps); no code was copied from another project. `pixdraw` also took ideas, not code, from the pixel-art DSL "claude-pxl".
- **Python packages used** (installed separately, not included): numpy (BSD-3-Clause), Pillow (HPND), scipy (BSD-3-Clause), opencv-python (Apache-2.0, optional, only `warp_layer`).
- **Data in the repository**: the palette in `pixdraw/styles/retro16.json` is Sweetie 16 by GrafxKid (CC0). The other pixdraw styles define colours by hue, saturation and value; they contain no third-party palettes. Pictures in `pixdraw/` and `images/` were produced by this code from the bundled data.
- **Fonts** (`ui/web/fonts/`): Barlow, Barlow Condensed (Jeremy Tribby) and JetBrains Mono (JetBrains), all SIL Open Font License 1.1, self-hosted so the interface never contacts a network.
- **Sample frames** (`samples/walk_frames/`): drawn from code by `samples/make_samples.py` for Gizpix, so they are covered by the same licence as the code (AGPL-3.0-or-later). They are simple on purpose; they are not real generator output.
- **Evidence pictures** (`images/evidence/`): crops and cut layers made from AI-generated sprite frames (not distributed). They are derived from generator output, so check the generator's terms before the repository is made public; if they do not allow it, delete that folder and the five image links in `MEASUREMENTS.md` (`python experiments/evidence/make_evidence.py` rebuilds them for anyone who has frames).
- **Measurements** (`MEASUREMENTS.md`) mention public CC0 pixel-art packs (Kenney) that were used for local tests only and are not included.
