# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixart.font - pixel lettering. Our own glyphs, kept as a 1 px skeleton; weight, shadow and colour are separate passes (the arcade recipe).

  5x7  capitals, digits, punctuation, Turkish letters (accents sit above/below the 7 px capital height: leave 3 px above and 2 below a line that uses them)
  3x5  tiny capitals and digits for HUD numbers and labels (accents are dropped)
bold=True smears every glyph 1 px to the right: 2 px upright stems, 1 px bars - the classic arcade weight. Lower case is drawn as capitals.
style: flat | grad (light top -> dark bottom, same rows in every letter) | bevel (lit top-left edge, dark bottom-right) | bands (highlight top row, shade bottom row)
       | chrome (r = sky ramp down to a light horizon, r2 = earth ramp from dark up to light)
mono=True gives every glyph the same cell (scores and timers must not jitter)."""
import unicodedata
import numpy as np

def _g(s): return s.split("|")

F57 = {k: _g(v) for k, v in {
    "A": ".###.|#...#|#...#|#####|#...#|#...#|#...#", "B": "####.|#...#|#...#|####.|#...#|#...#|####.", "C": ".###.|#...#|#....|#....|#....|#...#|.###.",
    "D": "####.|#...#|#...#|#...#|#...#|#...#|####.", "E": "#####|#....|#....|####.|#....|#....|#####", "F": "#####|#....|#....|####.|#....|#....|#....",
    "G": ".###.|#...#|#....|#.###|#...#|#...#|.###.", "H": "#...#|#...#|#...#|#####|#...#|#...#|#...#", "I": "###|.#.|.#.|.#.|.#.|.#.|###",
    "J": "..###|...#.|...#.|...#.|...#.|#..#.|.##..", "K": "#...#|#..#.|#.#..|##...|#.#..|#..#.|#...#", "L": "#....|#....|#....|#....|#....|#....|#####",
    "M": "#...#|##.##|#.#.#|#.#.#|#...#|#...#|#...#", "N": "#...#|##..#|#.#.#|#.#.#|#..##|#...#|#...#", "O": ".###.|#...#|#...#|#...#|#...#|#...#|.###.",
    "P": "####.|#...#|#...#|####.|#....|#....|#....", "Q": ".###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#", "R": "####.|#...#|#...#|####.|#.#..|#..#.|#...#",
    "S": ".####|#....|#....|.###.|....#|....#|####.", "T": "#####|..#..|..#..|..#..|..#..|..#..|..#..", "U": "#...#|#...#|#...#|#...#|#...#|#...#|.###.",
    "V": "#...#|#...#|#...#|#...#|#...#|.#.#.|..#..", "W": "#...#|#...#|#...#|#.#.#|#.#.#|##.##|#...#", "X": "#...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#",
    "Y": "#...#|#...#|.#.#.|..#..|..#..|..#..|..#..", "Z": "#####|....#|...#.|..#..|.#...|#....|#####",
    "0": ".###.|#...#|#..##|#.#.#|##..#|#...#|.###.", "1": "..#..|.##..|..#..|..#..|..#..|..#..|.###.", "2": ".###.|#...#|....#|...#.|..#..|.#...|#####",
    "3": "####.|....#|....#|.###.|....#|....#|####.", "4": "...#.|..##.|.#.#.|#..#.|#####|...#.|...#.", "5": "#####|#....|####.|....#|....#|#...#|.###.",
    "6": ".###.|#....|#....|####.|#...#|#...#|.###.", "7": "#####|....#|...#.|..#..|..#..|..#..|..#..", "8": ".###.|#...#|#...#|.###.|#...#|#...#|.###.",
    "9": ".###.|#...#|#...#|.####|....#|....#|.###.",
    ".": ".|.|.|.|.|.|#", ",": "..|..|..|..|..|.#|#.", "!": "#|#|#|#|#|.|#", "?": ".###.|#...#|....#|...#.|..#..|.....|..#..", ":": ".|.|#|.|.|#|.",
    "-": "...|...|...|###|...|...|...", "+": ".....|..#..|..#..|#####|..#..|..#..|.....", "/": "....#|....#|...#.|..#..|.#...|#....|#....", "'": "#|#|.|.|.|.|.",
    "(": ".#|#.|#.|#.|#.|#.|.#", ")": "#.|.#|.#|.#|.#|.#|#.", "%": "##..#|##..#|...#.|..#..|.#...|#..##|#..##", "*": ".....|#.#.#|.###.|#####|.###.|#.#.#|.....",
    "=": "....|....|####|....|####|....|....", "<": "...#|..#.|.#..|#...|.#..|..#.|...#", ">": "#...|.#..|..#.|...#|..#.|.#..|#...",
}.items()}
# accents: (base letter, rows above the capitals bottom-up from the letter, rows below)
ACC = {"Ö": ("O", [".#.#.", "....."], []), "Ü": ("U", [".#.#.", "....."], []), "İ": ("I", [".#.", "..."], []), "Ğ": ("G", [".#.#.", "..#..", "....."], []),
       "Ç": ("C", [], ["..#..", ".#..."]), "Ş": ("S", [], ["..#..", ".#..."]), "Â": ("A", ["..#..", ".#.#.", "....."], []), "Î": ("I", [".#.", "#.#", "..."], []), "Û": ("U", ["..#..", ".#.#.", "....."], [])}

F35 = {k: _g(v) for k, v in {
    "A": ".#.|#.#|###|#.#|#.#", "B": "##.|#.#|##.|#.#|##.", "C": ".##|#..|#..|#..|.##", "D": "##.|#.#|#.#|#.#|##.", "E": "###|#..|##.|#..|###", "F": "###|#..|##.|#..|#..",
    "G": ".##|#..|#.#|#.#|.##", "H": "#.#|#.#|###|#.#|#.#", "I": "###|.#.|.#.|.#.|###", "J": "..#|..#|..#|#.#|.#.", "K": "#.#|#.#|##.|#.#|#.#", "L": "#..|#..|#..|#..|###",
    "M": "#.#|###|###|#.#|#.#", "N": "###|#.#|#.#|#.#|#.#", "O": ".#.|#.#|#.#|#.#|.#.", "P": "##.|#.#|##.|#..|#..", "Q": ".#.|#.#|#.#|###|.##", "R": "##.|#.#|##.|#.#|#.#",
    "S": ".##|#..|.#.|..#|##.", "T": "###|.#.|.#.|.#.|.#.", "U": "#.#|#.#|#.#|#.#|###", "V": "#.#|#.#|#.#|#.#|.#.", "W": "#.#|#.#|###|###|#.#", "X": "#.#|#.#|.#.|#.#|#.#",
    "Y": "#.#|#.#|.#.|.#.|.#.", "Z": "###|..#|.#.|#..|###",
    "0": "###|#.#|#.#|#.#|###", "1": ".#.|##.|.#.|.#.|###", "2": "###|..#|###|#..|###", "3": "###|..#|.##|..#|###", "4": "#.#|#.#|###|..#|..#",
    "5": "###|#..|###|..#|###", "6": "###|#..|###|#.#|###", "7": "###|..#|..#|.#.|.#.", "8": "###|#.#|###|#.#|###", "9": "###|#.#|###|..#|###",
    ".": ".|.|.|.|#", ":": ".|#|.|#|.", "!": "#|#|#|.|#", "-": "..|..|##|..|..", "+": "...|.#.|###|.#.|...", "/": "..#|..#|.#.|#..|#..", "?": "##.|..#|.#.|...|.#.", "%": "#.#|..#|.#.|#..|#.#",
}.items()}
FONTS = {"5x7": (F57, 7, 5), "3x5": (F35, 5, 3)}


def _glyph(ch, font):
    """(rows, above, below) for one character, or None"""
    G = FONTS[font][0]
    if ch in G: return G[ch], [], []
    if ch in ACC and font == "5x7": base, up, dn = ACC[ch]; return G[base], up, dn
    plain = unicodedata.normalize("NFD", ch)[0]
    return (G[plain], [], []) if plain in G else None


def layout(string, font="5x7", bold=False, spacing=1, mono=False):
    """[(x offset, rows, above, below)], total width, height of the capitals"""
    G, H, CW = FONTS[font]; out = []; x = 0
    for ch in string.upper().replace("İ", "İ"):
        g = _glyph(ch, font)
        if g is None: x += (CW + bold if mono else 3) + spacing; continue
        rows, up, dn = g; w = len(rows[0]) + bool(bold); cell = CW + bool(bold)
        out.append((x + ((cell - w) // 2 if mono else 0), rows, up, dn)); x += (cell if mono else w) + spacing
    return out, max(0, x - spacing), H


def text_size(string, font="5x7", bold=False, spacing=1, mono=False): _, w, h = layout(string, font, bold, spacing, mono); return w, h


def draw_text(c, string, x, y, r, font="5x7", bold=False, style="flat", tone=None, shadow=False, spacing=1, mono=False, r2=None):
    from .core import shift
    items, W, H = layout(string, font, bold, spacing, mono); M = c.empty()
    def stamp(rows, x0, y0):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch == "#":
                    for k in range(1 + bool(bold)):
                        if 0 <= x0 + i + k < c.w and 0 <= y0 + j < c.h: M[y0 + j, x0 + i + k] = True
    for ox, rows, up, dn in items:
        stamp(rows, x + ox, y); stamp(up, x + ox, y - len(up)); stamp(dn, x + ox, y + H)
    ri = c._r(r); n = len(c.ramps[ri]); b = c.ramps[ri].base if tone is None else tone; row = c.yy - y
    if shadow: sm = shift(M, 1, 1) & ~M; c.fill(sm, r, tone=0, lock=True); c.tone[sm] = -1
    if style == "flat": c.fill(M, r, tone=b, lock=True)
    elif style == "bevel": c.fill(M, r, form="slab", tone=min(max(b, 1), n - 2), lock=True)
    elif style == "grad":
        for j in range(-3, H + 2): c.fill(M & (row == j), r, tone=int(np.clip(n - 1 - max(j, 0) * n // H, 0, n - 1)), lock=True)
    elif style == "bands":
        c.fill(M, r, tone=b, lock=True); c.fill(M & (row <= 0), r, tone=n - 1, lock=True); c.fill(M & (row >= H - 1), r, tone=0, lock=True)
    elif style == "chrome":
        if r2 is None: raise ValueError("style 'chrome' needs r2 = the earth ramp (r is the sky ramp)")
        hz = H // 2; n2 = len(c.ramps[c._r(r2)])
        for j in range(-3, H + 2):
            if j < hz: c.fill(M & (row == j), r, tone=int(np.clip(1 + max(j, 0) * (n - 1) // max(hz - 1, 1), 0, n - 1)), lock=True)
            else: c.fill(M & (row == j), r2, tone=int(np.clip(1 + (j - hz) * (n2 - 1) // (H - hz), 0, n2 - 1)), lock=True)
    else: raise ValueError(f"unknown text style {style!r}; choose flat, grad, bevel, bands or chrome")
    return M
