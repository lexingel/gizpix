# SPDX-License-Identifier: AGPL-3.0-or-later
"""pad_sprite.py <sprite.png> <out.png> <canvas_w> <canvas_h> <x> [y]
Pastes a standing sprite onto a bigger transparent canvas so a swing has room. y defaults to
"feet on the bottom edge" (the lowest drawn row, not the file's bottom: empty rows under the feet hang below). Prints the offset to record for the engine (where the sprite's
top-left sits on the padded frames). Then upload <out.png> to your generator (it must accept a PNG input).

  python pad_sprite.py hero.png hero_pad.png 192 256 24        # hero: 72 px in front, room above
  python pad_sprite.py boss.png boss_pad.png 256 256 80        # boss facing left: room on the left
"""
import sys as _sys
if any(_a in ("-h", "--help") for _a in _sys.argv[1:]): print(__doc__); _sys.exit(0)     # -h always prints the documentation, exit 0
import sys
for _s in (sys.stdout, sys.stderr):   # Windows consoles: never crash on non-ASCII text
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
    sys.exit(__doc__)
from PIL import Image

src, out, w, h, x = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
im = Image.open(src).convert('RGBA')
feet = im.getbbox()[3] if im.getbbox() else im.height   # rows below this are empty
y = int(sys.argv[6]) if len(sys.argv) > 6 else h - feet
assert x + im.width <= w and y + feet <= h and y >= 0, 'sprite does not fit the canvas'
c = Image.new('RGBA', (w, h))
c.alpha_composite(im.crop((0, 0, im.width, feet)), (x, y))
c.save(out)
print('offset', x, y)
