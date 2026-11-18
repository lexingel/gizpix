"""More village props (pixart): trees, barrels, crates, sacks, signpost, bench, trough, chicken, dog."""
from props import *


def oak(w=34, h=44, base="#4f9d4a", apples=False):
    c = Canvas(w, h, light="tl"); leaf = ramp(base, n=5, name="leaf"); wd = wood("#7a5030"); tx = w // 2 - 3; ty = int(h * 0.55)
    c.fill(c.rect(tx, ty, 6, h - ty), wd, form="tube", axis="x", lo=1); c.fill(c.poly([(tx - 2, h), (tx, h - 5), (tx + 6, h - 5), (tx + 8, h)]), wd, tone=1)
    for ox, oy, ow, oh in ((0.04, 0.30, 0.55, 0.45), (0.42, 0.28, 0.54, 0.46), (0.17, 0.02, 0.66, 0.52)):
        c.fill(c.oval(w * ox, h * oy, w * ow, h * oh), leaf, form="ball", lo=1, shadow=True)
    if apples:
        fr = ramp("#e04a3a", n=3, name="apple")
        for fx, fy in ((0.25, 0.4), (0.55, 0.3), (0.7, 0.5), (0.4, 0.55), (0.5, 0.12)):
            c.px(int(w * fx), int(h * fy), fr, 2)
    c.outline(); return c


def pine(w=24, h=46):
    c = Canvas(w, h, light="tl"); leaf = ramp("#2f7a4a", n=5, name="pine"); wd = wood("#6a4428")
    c.fill(c.rect(w // 2 - 2, h - 9, 4, 9), wd, form="tube", axis="x", lo=1)
    tiers = 4; th = (h - 9) // tiers + 4
    for i in range(tiers):
        y0 = i * (h - 9 - th) // (tiers - 1) if tiers > 1 else 0; ww = 8 + i * (w - 10) // (tiers - 1)
        c.fill(c.poly([(w / 2, y0), (w / 2 + ww / 2, y0 + th), (w / 2 - ww / 2, y0 + th)]), leaf, form="slab", tone=2, lo=1, hi=3)
    c.outline(); return c


def barrel():
    c = Canvas(14, 18, light="tl"); wd = wood("#9a6a40"); iron = ramp("#4a4f60", n=4, name="iron")
    c.fill(c.oval(1, 1, 12, 16), wd, form="ball", lo=1)
    for y in (4, 12): c.fill(c.rect(1, y, 12, 1), iron, tone=2)
    c.outline(); return c


def crates():
    c = Canvas(26, 22, light="tl"); wd = wood("#b0804c"); dk = wood("#7a5030")
    c.fill(c.rect(1, 11, 14, 10), wd, form="slab", tone=2); c.fill(c.rect(13, 14, 12, 7), wd, form="slab", tone=2); c.fill(c.rect(4, 1, 10, 10), wd, form="slab", tone=2)
    for x0, y0, w, h in ((1, 11, 14, 10), (13, 14, 12, 7), (4, 1, 10, 10)):
        c.fill(c.rect(x0, y0, w, 1), dk, tone=1); c.fill(c.rect(x0, y0 + h - 1, w, 1), dk, tone=1); c.fill(c.line([(x0, y0), (x0 + w - 1, y0 + h - 1)]), dk, tone=1)
    c.outline(); return c


def sacks():
    c = Canvas(24, 16, light="tl"); sk = ramp("#d8c49a", n=4, name="sack")
    for x, y, w, h in ((1, 6, 10, 9), (11, 7, 10, 8), (6, 1, 10, 9)):
        c.fill(c.oval(x, y, w, h), sk, form="ball", lo=1); c.fill(c.rect(x + w // 2 - 1, y, 3, 2), sk, tone=0)
    c.outline(); return c


def signpost():
    c = Canvas(28, 34, light="tl"); wd = wood("#8e5d38"); bd = wood("#c49a60")
    c.fill(c.rect(12, 2, 4, 32), wd, form="tube", axis="x", lo=1)
    c.fill(c.poly([(2, 6), (20, 6), (24, 10), (20, 14), (2, 14)]), bd, form="slab", tone=2); c.fill(c.poly([(8, 17), (26, 17), (26, 25), (8, 25), (4, 21)]), bd, form="slab", tone=2)
    for x in (5, 9, 13): c.px(x, 10, wd, 1)
    for x in (12, 16, 20): c.px(x, 21, wd, 1)
    c.outline(); return c


def bench():
    c = Canvas(30, 18, light="tl"); wd = wood("#a8744a"); dk = wood("#6e4528")
    c.fill(c.rect(1, 4, 28, 3), wd, form="slab", tone=2); c.fill(c.rect(1, 9, 28, 3), wd, form="slab", tone=2)
    for x in (3, 24): c.fill(c.rect(x, 4, 3, 13), dk, form="tube", axis="x", lo=1)
    c.outline(); return c


def trough():
    c = Canvas(32, 14, light="tl"); wd = wood("#9a6a40"); w = ramp("#5aa0d8", n=4, name="water")
    c.fill(c.rect(1, 3, 30, 9), wd, form="slab", tone=2); c.fill(c.rect(3, 4, 26, 3), w, tone=2); c.fill(c.rect(4, 4, 8, 1), w, tone=3)
    c.fill(c.rect(3, 11, 3, 3), wood("#6e4528"), tone=1); c.fill(c.rect(26, 11, 3, 3), wood("#6e4528"), tone=1); c.outline(); return c


def chicken(peck=False):
    c = Canvas(16, 14, light="tl"); body = ramp("#f4efe0", n=4, name="hen"); red = ramp("#d04a3a", n=3, name="comb"); beak = ramp("#e0a030", n=3, name="beak"); leg = ramp("#d09040", n=3, name="leg")
    c.fill(c.oval(3, 4, 10, 7), body, form="ball", lo=1); c.fill(c.poly([(12, 5), (15, 3), (14, 8)]), body, tone=1)
    hy = 6 if peck else 1; c.fill(c.oval(1, hy, 5, 5), body, form="ball", lo=1)
    c.px(2, hy - 1, red, 2); c.px(3, hy - 1, red, 2); c.px(0, hy + 2 + (1 if peck else 0), beak, 2)
    c.px(2, hy + 1, ramp("#222222", n=2, name="eye"), 1); c.fill(c.rect(6, 11, 1, 3), leg, tone=1); c.fill(c.rect(9, 11, 1, 3), leg, tone=1)
    c.outline(); return c


def dog(tail=0):
    c = Canvas(26, 16, light="tl"); fur = ramp("#b07a48", n=4, name="fur"); dk = ramp("#6a4428", n=3, name="ear")
    c.fill(c.oval(5, 4, 15, 8), fur, form="ball", lo=1); c.fill(c.oval(1, 1, 8, 7), fur, form="ball", lo=1); c.fill(c.rect(2, 5, 4, 2), fur, tone=2)
    c.fill(c.poly([(2, 1), (4, 0), (5, 4)]), dk, tone=1)
    for x in (6, 9, 16, 19): c.fill(c.rect(x, 11, 2, 5), fur, tone=1)
    c.fill(c.line([(19, 5), (23, 3 - tail)], w=2), fur, tone=2); c.px(3, 3, ramp("#222222", n=2, name="eye"), 1); c.px(1, 4, ramp("#222222", n=2, name="nose"), 1)
    c.outline(); return c
