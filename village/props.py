"""Village props drawn with the Gizpix pixart engine (no reference images, no AI). Every function returns a pixart Canvas (or a list of canvases for animations)."""
import sys, math
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pixart import Canvas, ramp, Ramp, humanoid, mannequin, pose_at, head_mask
from pixart.poses import ACTIONS


def wood(base="#9a6a40"):
    return ramp(base, n=4, name="wood")


def fence(n=5, post_h=14):
    """a picket fence: posts with pointed tops, two rails"""
    w = n * 9 + 4; c = Canvas(w, post_h + 4, light="tl"); wd = wood("#a8744a"); rail = wood("#8e5d38")
    c.fill(c.rect(0, 5, w, 2), rail, form="slab", tone=2); c.fill(c.rect(0, 10, w, 2), rail, form="slab", tone=2)
    for i in range(n + 1):
        x = 2 + i * 9
        c.fill(c.rect(x, 3, 3, post_h - 1) | c.poly([(x, 3), (x + 3, 3), (x + 1, 1)]), wd, form="tube", lo=1, hi=3)
    c.outline(); return c


def lamp(lit=True, pole=30):
    """a lamp post with a lantern; the glow is a few light pixels around the glass"""
    c = Canvas(18, 16 + pole, light="tl"); iron = ramp("#3a3f52", n=4, name="iron"); glass = ramp("#ffd873" if lit else "#7a8590", n=4, name="glass")
    c.fill(c.rect(8, 14, 2, pole), iron, form="tube", axis="x", lo=1); c.fill(c.rect(5, 13 + pole, 8, 2), iron, form="slab", tone=2)
    c.fill(c.rect(4, 4, 10, 10, r=1), glass, form="slab", tone=3 if lit else 1); c.fill(c.poly([(3, 4), (15, 4), (12, 1), (6, 1)]), iron, form="slab", tone=1); c.fill(c.rect(4, 14, 10, 2), iron, tone=1)
    c.fill(c.rect(8, 7, 2, 4), glass, tone=3); c.outline(); return c


def haystack():
    c = Canvas(34, 26, light="tl"); hay = ramp("#e0b44c", n=5, name="hay")
    c.fill(c.oval(2, 6, 30, 22) & (c.yy < 24), hay, form="ball", lo=1, shadow=True)
    for x, y in ((9, 12), (16, 9), (22, 14), (13, 18), (24, 19), (7, 17)):
        c.retone(c.line([(x, y), (x + 3, y + 1)]), delta=-1)
    c.fill(c.rect(3, 22, 28, 2), hay, tone=0); c.outline(); return c


def cart():
    c = Canvas(54, 34, light="tl"); wd = wood("#a06a3c"); dk = wood("#6e4528"); iron = ramp("#4a4f60", n=4, name="iron"); hay = ramp("#e0b44c", n=4, name="hay")
    c.fill(c.rect(6, 10, 34, 11), wd, form="slab", tone=2)
    for x in (13, 21, 29): c.retone(c.rect(x, 10, 1, 11), delta=-1)
    c.fill(c.rect(4, 8, 38, 3), dk, form="slab", tone=2)
    c.fill(c.oval(8, 4, 28, 8) & (c.yy < 10), hay, form="ball", lo=1)                              # a load of hay
    c.fill(c.line([(40, 17), (53, 14)], w=2), dk, tone=1)                                           # the shaft
    for cx in (14, 33):
        c.fill(c.ring(cx - 8, 15, 16, 16, t=2), dk, form="tube", lo=1); c.fill(c.oval(cx - 2, 21, 4, 4), iron, tone=2)
        for a in (0, 45, 90, 135):
            r = 7; dx, dy = r * math.cos(math.radians(a)), r * math.sin(math.radians(a)); c.fill(c.line([(cx - dx, 23 - dy), (cx + dx, 23 + dy)]), dk, tone=1)
    c.outline(); return c


def bush(w=22, h=14, base="#4f9d4a", flowers=None):
    c = Canvas(w + 4, h + 4, light="tl"); leaf = ramp(base, n=5, name="leaf")
    c.fill(c.oval(2, 3, w * 0.62, h), leaf, form="ball", lo=1, shadow=True); c.fill(c.oval(w * 0.35, 1, w * 0.62, h + 1), leaf, form="ball", lo=1, shadow=True)
    if flowers:
        fl = ramp(flowers, n=4, name="flower")
        for x, y in ((6, 8), (11, 5), (15, 9), (9, 11), (18, 6)):
            if x < w and y < h: c.px(x, y, fl, 3)
    c.outline(); return c


def flowers(w=24, colors=("#e8575a", "#f3d34a", "#9a6ae0")):
    """a tuft of grass with flower heads"""
    c = Canvas(w, 14, light="tl"); gr = ramp("#58b04a", n=4, name="gr")
    for i in range(6):
        x = 2 + i * (w - 5) // 6; hh = 5 + (i * 7) % 6
        c.fill(c.line([(x, 13), (x + (i % 3 - 1), 13 - hh)]), gr, tone=1 + (i % 2))
        fl = ramp(colors[i % len(colors)], n=3, name="f%d" % i); c.px(x + (i % 3 - 1), 13 - hh - 1, fl, 2)
        c.px(x + (i % 3 - 1) - 1, 13 - hh - 1, fl, 1); c.px(x + (i % 3 - 1) + 1, 13 - hh - 1, fl, 1)
    return c


def windmill(t=0.0, s=1.0):
    """tower, cap and four sails; the sails turn a quarter turn over t = 0..1 (four sails look the same every 90 degrees, so the loop is exact). s scales every length (0.6 = a small far mill)."""
    S = lambda v: int(round(v * s)); P = lambda pts: [(S(x), S(y)) for x, y in pts]
    c = Canvas(S(70), S(80), light="tl"); wall = ramp("#e9dcc0", n=4, name="plaster"); roof = ramp("#9a4a3c", n=4, name="roof"); wd = wood("#8a5a34"); sail = ramp("#f4efe0", n=4, name="sail")
    c.fill(c.poly(P([(24, 30), (46, 30), (50, 76), (20, 76)])), wall, form="slab", tone=2)
    c.fill(c.rect(S(31), S(58), max(S(9), 3), S(18), r=1 if s > .8 else 0), wd, form="slab", tone=1)
    if s > .8:
        c.fill(c.rect(34, 40, 4, 6), ramp("#7ab8e8", n=3, name="glass"), tone=1)
    c.fill(c.poly(P([(21, 30), (49, 30), (35, 14)])), roof, form="slab", tone=2)
    cx, cy = S(35), S(26); ang0 = 360 * t / 4
    for k in range(4):
        a = math.radians(ang0 + 90 * k + 20); x2, y2 = cx + S(26) * math.cos(a), cy + S(26) * math.sin(a); b = a + math.radians(90)
        p0 = (cx + S(5) * math.cos(a), cy + S(5) * math.sin(a)); w = max(S(6), 3)
        pts = [p0, (x2, y2), (x2 + w * math.cos(b), y2 + w * math.sin(b)), (p0[0] + w * math.cos(b), p0[1] + w * math.sin(b))]
        c.fill(c.poly([(int(round(x)), int(round(y))) for x, y in pts]), sail, form="slab", tone=2)
        c.fill(c.line([(cx, cy), (int(round(x2)), int(round(y2)))]), wd, tone=1)
    c.fill(c.oval(cx - 2, cy - 2, 4, 4), wd, form="ball", lo=1)
    c.outline(); return c


def villager(pose_index=0, shirt="#d05a4a", pants="#4a5a8a", hair="#5a3a2a", height=24, facing=1, action="idle"):
    """a standing person from the pixart rig; two idle poses (a one pixel breath); action="walk" gives the 8-frame walk cycle (pose_index 0..7)"""
    rig = humanoid(height=height, heads=3, facing=facing); skin = ramp("#f0c8a0", n=4, name="skin"); top = ramp(shirt, n=4, name="top"); bot = ramp(pants, n=4, name="bot")
    pose = ACTIONS[action][pose_index % len(ACTIONS[action])][0]
    c = Canvas(26, height + 8, light="tl"); j = rig.solve(pose, root_x=13, ground=height + 5); mannequin(c, rig, j, skin, top, bot)
    hm = head_mask(c, j["head"], rig.size["head"]); ys, xs = hm.nonzero(); cy = ys.min() + (ys.max() - ys.min()) * 0.42
    c.fill(hm & (c.yy < cy), ramp(hair, n=3, name="hair"), form="ball", lo=0, hi=2)                       # hair: the top of the head
    c.outline(); return c


def well():
    """a stone well with a small roof on two posts, a rope and a dark opening"""
    c = Canvas(26, 28, light="tl"); stone = ramp("#9a9aa6", n=4, name="stone"); roof = ramp("#9a4a3c", n=4, name="roof"); wd = wood("#8a5a34")
    c.fill(c.rect(4, 17, 18, 10, r=1), stone, form="slab", tone=2); c.fill(c.rect(5, 17, 16, 3), stone, tone=0)
    c.fill(c.rect(5, 7, 2, 11), wd, form="tube", axis="x", lo=1); c.fill(c.rect(19, 7, 2, 11), wd, form="tube", axis="x", lo=1)
    c.fill(c.poly([(2, 8), (24, 8), (19, 2), (7, 2)]), roof, form="slab", tone=1); c.fill(c.rect(12, 9, 1, 8), wd, tone=1)
    c.outline(); return c
