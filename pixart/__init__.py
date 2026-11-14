# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixart - draw pixel art from code, with the craft rules built in. No reference image, no AI generation. See README.md (API) and KNOWLEDGE.md (the rules).
    from pixart import Canvas, ramp
    c = Canvas(32, 32); red = ramp("#c8402f")
    c.fill(c.oval(8, 10, 16, 16), red, form="ball", rim=True); c.outline(); c.lint(); c.preview("out/apple_preview.png"); c.save("out/apple.png")"""
from .core import Canvas, Ramp, ramp, ramp9, house, rgb, shift, grow, shrink, flipx, sym, rim, palette_of, export, strip, sheet, lint_all, PALETTES, LIGHTS
from .font import text_size
from .rig import Rig, humanoid, quadruped, pose_at, lerp_pose, mannequin, mannequin8, head_mask, far, body_width, face_point, DIRS

__all__ = ["Canvas", "Ramp", "ramp", "ramp9", "rgb", "shift", "grow", "shrink", "flipx", "sym", "export", "strip", "PALETTES", "LIGHTS", "text_size", "Rig", "humanoid", "quadruped", "pose_at", "lerp_pose", "mannequin", "mannequin8", "head_mask", "far", "body_width", "face_point", "DIRS", "sheet", "lint_all", "rim", "palette_of", "house"]
