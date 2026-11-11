# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixdraw - reference-free pixel-art buildings from parameters. See README.md.
    from pixdraw import render, load_style
    frames = render({"type": "inn"}, "dark_fantasy", frames=8)        # list of PIL RGBA images"""
from .templates import render, scene, PRESETS, DEFAULTS
from .styles import load_style, list_styles, extract_style, make_ramp
from .materials import MATERIALS, register as register_material
from .core import PROJECTIONS
from .compose import compose

__all__ = ["render", "scene", "PRESETS", "DEFAULTS", "load_style", "list_styles", "extract_style", "make_ramp", "MATERIALS", "register_material", "PROJECTIONS", "compose"]
