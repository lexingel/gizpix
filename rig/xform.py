# SPDX-License-Identifier: AGPL-3.0-or-later
"""xform.py - 2D affine transforms for pixel-art rigs: parts with a parent chain, rotation about a pivot, nearest-neighbour sampling (palette stays exact).
Idea from Eck, Introduction to Computer Graphics, 2.3-2.4 (modeling transforms, scene graph): a part is drawn in its own coordinates and placed by
translate(pivot) * rotate(angle) * translate(-pivot); a child sits inside its parent's transform. Code is ours.
  M = rot_about(deg, px, py)           3x3 matrix
  M = chain(parent_M, child_M)         child is applied first, then the parent (matrix product parent @ child)
  out = apply(img, M)                  RGBA image, same size, nearest neighbour, no blending
  python xform.py selftest"""
import math
import numpy as np

def translate(dx, dy): return np.array([[1, 0, dx], [0, 1, dy], [0, 0, 1]], float)
def rotate(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg)); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)
def rot_about(deg, px, py): return translate(px, py) @ rotate(deg) @ translate(-px, -py)
def chain(parent, child): return parent @ child

def apply(img, M):
    """Pull each output pixel from the input through the inverse of M (pixel centres at +0.5). No resampling blur: one source pixel per output pixel."""
    H, W = img.shape[:2]; inv = np.linalg.inv(M); yy, xx = np.mgrid[0:H, 0:W]
    sx = inv[0, 0] * (xx + .5) + inv[0, 1] * (yy + .5) + inv[0, 2]; sy = inv[1, 0] * (xx + .5) + inv[1, 1] * (yy + .5) + inv[1, 2]
    ix, iy = np.floor(sx).astype(int), np.floor(sy).astype(int); ok = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
    out = np.zeros_like(img); out[ok] = img[iy[ok], ix[ok]]; return out

def selftest():
    img = np.zeros((9, 9, 4), np.uint8); img[4, 7] = (255, 0, 0, 255)               # one pixel, 3 right of the centre (4,4)
    r = apply(img, rot_about(90, 4.5, 4.5)); ys, xs = np.nonzero(r[..., 3])
    assert len(ys) == 1 and (xs[0], ys[0]) == (4, 7), (xs, ys)                          # 90 deg clockwise (y down): right -> down
    assert np.array_equal(apply(img, np.eye(3)), img), "identity changed the image"
    a, b = translate(2, 0), rot_about(90, 4.5, 4.5)
    assert not np.allclose(a @ b, b @ a), "order must matter (rotate-then-translate != translate-then-rotate)"
    assert apply(img, chain(a, b))[..., 3].sum() == 255, "a pixel got lost or blended"
    print("selftest ok")
if __name__ == "__main__":
    import sys; selftest() if sys.argv[1:] == ["selftest"] else print(__doc__)
