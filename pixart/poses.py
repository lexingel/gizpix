# SPDX-License-Identifier: AGPL-3.0-or-later
"""pixart.poses - a library of key poses for the side-view `humanoid` rig, with timing. Built from the weapon reference study (knowledge/weapons_*.md)
and the animation research (knowledge/animation_and_cleanup.md). Angles are rig angles (0 down, 90 forward, 180 up, -90 back).

  ACTIONS[name] = [(pose, ms, tag), ...]     one entry per frame, pose-to-pose: the key poses ARE the frames. tag: "" | "hold" | "smear" | "hit" | "release"
  for pose, ms, tag in ACTIONS["slash"]: j = rig.solve(pose, root_x=24, ground=52); ...draw...; on tag == "smear" also paint c.crescent(...)
  more in-betweens: tween(ACTIONS["slash"], 1) inserts one eased frame between every two keys (never across a smear: a swing stays one frame)

Actions: idle walk run slash thrust smash stab bow punch kick shoot block hurt cast.
Rules they follow: staggered feet and bent knees in every stance; anticipation is held, the swing is ONE frame with a smear, the end pose is held longer than
anything else, recovery is slower than the strike; a thrust is one straight line from the rear heel to the weapon tip; heavy weapons fold the spine 45-80 degrees,
light ones 10-30; the body steps or leans INTO the hit (root moves forward)."""
from .rig import lerp_pose, EASES

STANCE = {"spine": 174, "head": 178, "leg_f_up": 26, "leg_f_lo": 6, "leg_b_up": -16, "leg_b_lo": -32, "foot_f": 90, "foot_b": 90,
          "arm_f_up": 30, "arm_f_lo": 85, "arm_b_up": 18, "arm_b_lo": 70, "weapon": 115}


def P(**kw):
    """a pose = the fighting stance with some bones changed; root=(forward px, down px) moves the hips"""
    p = dict(STANCE); p.update(kw); return p


def _swap(p):
    q = dict(p)
    for a, b in (("leg_f_up", "leg_b_up"), ("leg_f_lo", "leg_b_lo"), ("arm_f_up", "arm_b_up"), ("arm_f_lo", "arm_b_lo"), ("foot_f", "foot_b")): q[a], q[b] = p[b], p[a]
    return q


def _cycle(half, ms):
    """a walk or run: the second half is the first with the legs and arms swapped"""
    return [(p, ms, "") for p in half] + [(_swap(p), ms, "") for p in half]


UP = {"spine": 178, "head": 180, "weapon": 100}
_walk = [dict(UP, leg_f_up=28, leg_f_lo=20, leg_b_up=-20, leg_b_lo=-34, arm_f_up=-22, arm_f_lo=-4, arm_b_up=22, arm_b_lo=42, foot_f=75, foot_b=110),     # contact: front heel down, legs widest
         dict(UP, leg_f_up=24, leg_f_lo=-4, leg_b_up=-26, leg_b_lo=-58, arm_f_up=-14, arm_f_lo=4, arm_b_up=14, arm_b_lo=34, foot_f=90, foot_b=140),      # down: front knee takes the weight (lowest)
         dict(UP, leg_f_up=2, leg_f_lo=-2, leg_b_up=22, leg_b_lo=-48, arm_f_up=0, arm_f_lo=12, arm_b_up=4, arm_b_lo=20, foot_f=90, foot_b=120),          # passing: swing leg folds past the standing leg
         dict(UP, leg_f_up=-12, leg_f_lo=-14, leg_b_up=38, leg_b_lo=4, arm_f_up=14, arm_f_lo=30, arm_b_up=-12, arm_b_lo=2, foot_f=100, foot_b=80)]        # up: push off (highest)
_run = [dict(spine=164, head=172, weapon=100, leg_f_up=48, leg_f_lo=20, leg_b_up=-30, leg_b_lo=-80, arm_f_up=-50, arm_f_lo=40, arm_b_up=50, arm_b_lo=140, foot_f=80, foot_b=150),
        dict(spine=162, head=170, weapon=100, leg_f_up=20, leg_f_lo=-10, leg_b_up=-10, leg_b_lo=-100, arm_f_up=-25, arm_f_lo=60, arm_b_up=25, arm_b_lo=120, foot_f=90, foot_b=160),
        dict(spine=164, head=172, weapon=100, leg_f_up=-10, leg_f_lo=-25, leg_b_up=45, leg_b_lo=-50, arm_f_up=10, arm_f_lo=95, arm_b_up=-10, arm_b_lo=80, foot_f=110, foot_b=120),
        dict(spine=166, head=174, weapon=100, leg_f_up=-35, leg_f_lo=-50, leg_b_up=62, leg_b_lo=10, arm_f_up=40, arm_f_lo=130, arm_b_up=-40, arm_b_lo=50, foot_f=140, foot_b=85)]

ACTIONS = {
    "idle": [(P(), 400, "hold"), (P(root=(0, 1), spine=173, arm_f_lo=83, weapon=113), 400, "hold")],                      # breathing: 1 px, two long frames
    "walk": _cycle(_walk, 120),                                                                                          # 8 frames; 4 frames: keep contact + passing (every second) at 240 ms
    "run": _cycle(_run, 80),
    # overhead / diagonal cut with a light or medium blade: wind-up held, ONE swing frame with the smear, end pose held, slow recovery
    "slash": [(P(), 80, ""),
              (P(spine=186, head=182, arm_f_up=165, arm_f_lo=205, arm_b_up=150, arm_b_lo=200, weapon=225, leg_f_up=18, root=(-1, 0)), 70, ""),
              (P(spine=188, head=183, arm_f_up=170, arm_f_lo=210, arm_b_up=155, arm_b_lo=205, weapon=232, leg_f_up=16, root=(-1, 0)), 140, "hold"),
              (P(spine=158, head=170, arm_f_up=105, arm_f_lo=98, arm_b_up=95, arm_b_lo=92, weapon=118, leg_f_up=40, leg_f_lo=8, leg_b_up=-34, leg_b_lo=-34, root=(3, 0)), 60, "smear"),
              (P(spine=150, head=166, arm_f_up=72, arm_f_lo=62, arm_b_up=64, arm_b_lo=58, weapon=52, leg_f_up=42, leg_f_lo=6, leg_b_up=-36, leg_b_lo=-36, root=(4, 1)), 180, "hit"),
              (P(spine=158, head=172, arm_f_up=60, arm_f_lo=70, arm_b_up=50, arm_b_lo=64, weapon=70, leg_f_up=36, root=(3, 0)), 100, ""),
              (P(), 100, "")],
    # thrust with sword or spear: pull back, lunge to one straight line heel -> tip, hold, pull back
    "thrust": [(P(), 80, ""),
               (P(spine=184, arm_f_up=-25, arm_f_lo=70, arm_b_up=-40, arm_b_lo=60, weapon=92, leg_f_up=18, root=(-2, 0)), 130, "hold"),
               (P(spine=148, head=165, arm_f_up=96, arm_f_lo=92, arm_b_up=80, arm_b_lo=88, weapon=90, leg_f_up=56, leg_f_lo=2, leg_b_up=-46, leg_b_lo=-46, root=(5, 1)), 60, "smear"),
               (P(spine=148, head=165, arm_f_up=96, arm_f_lo=92, arm_b_up=80, arm_b_lo=88, weapon=90, leg_f_up=56, leg_f_lo=2, leg_b_up=-46, leg_b_lo=-46, root=(5, 1)), 200, "hit"),
               (P(spine=166, arm_f_up=40, arm_f_lo=80, weapon=95, leg_f_up=36, root=(2, 0)), 100, ""),
               (P(), 100, "")],
    # heavy two-hand overhead (hammer, great axe, mace): slow lift, short top, 1 frame down, long low hold; the spine folds
    "smash": [(P(), 100, ""),
              (P(spine=182, arm_f_up=110, arm_f_lo=150, arm_b_up=100, arm_b_lo=140, weapon=170, root=(0, 1)), 110, ""),
              (P(spine=192, head=186, arm_f_up=175, arm_f_lo=215, arm_b_up=165, arm_b_lo=210, weapon=235, leg_f_up=14, root=(-2, 0)), 110, ""),
              (P(spine=196, head=188, arm_f_up=180, arm_f_lo=225, arm_b_up=170, arm_b_lo=218, weapon=245, leg_f_up=12, root=(-2, -1)), 180, "hold"),
              (P(spine=140, head=160, arm_f_up=110, arm_f_lo=100, arm_b_up=100, arm_b_lo=95, weapon=128, leg_f_up=44, leg_f_lo=4, leg_b_up=-36, leg_b_lo=-36, root=(3, 1)), 60, "smear"),
              (P(spine=120, head=150, arm_f_up=62, arm_f_lo=50, arm_b_up=55, arm_b_lo=46, weapon=42, leg_f_up=50, leg_f_lo=-6, leg_b_up=-38, leg_b_lo=-44, root=(4, 3)), 260, "hit"),
              (P(spine=140, head=162, arm_f_up=50, arm_f_lo=60, arm_b_up=44, arm_b_lo=56, weapon=60, leg_f_up=42, root=(3, 2)), 140, ""),
              (P(), 120, "")],
    # knife: short arc from the elbow, almost no wind-up, no big smear
    "stab": [(P(arm_f_up=20, arm_f_lo=110, weapon=120), 80, ""),
             (P(spine=180, arm_f_up=-30, arm_f_lo=95, weapon=100, root=(-1, 0)), 70, "hold"),
             (P(spine=160, head=170, arm_f_up=88, arm_f_lo=92, weapon=90, leg_f_up=40, leg_b_up=-30, leg_b_lo=-34, root=(3, 0)), 120, "hit"),
             (P(arm_f_up=20, arm_f_lo=110, weapon=120), 90, "")],
    # bow: the FRONT arm (arm_f) holds the bow, the BACK arm (arm_b) draws - paint that back arm OVER the torso for this action, or the draw is hidden.
    # Bow, string and arrow: c.bow(j["arm_f_lo"][1], string_hand=j["arm_b_lo"][1]) on the hold frame, string_hand=None after the release; add 1-2 arrow-flight frames yourself.
    # bow (bow in the front hand = weapon bone held upright; the back hand draws): raise, draw to the jaw (string = V to the back hand), release (only the string hand moves), follow
    "bow": [(P(spine=178, arm_f_up=40, arm_f_lo=60, arm_b_up=30, arm_b_lo=80, weapon=180), 120, ""),
            (P(spine=180, arm_f_up=92, arm_f_lo=90, arm_b_up=70, arm_b_lo=95, weapon=180), 100, ""),
            (P(spine=182, head=180, arm_f_up=92, arm_f_lo=90, arm_b_up=-100, arm_b_lo=100, weapon=180), 260, "hold"),
            (P(spine=182, head=180, arm_f_up=92, arm_f_lo=90, arm_b_up=-95, arm_b_lo=40, weapon=180), 60, "release"),
            (P(spine=180, arm_f_up=92, arm_f_lo=90, arm_b_up=-100, arm_b_lo=10, weapon=170), 180, "hold"),
            (P(spine=178, arm_f_up=40, arm_f_lo=60, arm_b_up=30, arm_b_lo=80, weapon=180), 120, "")],
    # straight punch: guard at the chin, one line rear heel -> spine -> fist at contact
    "punch": [(P(arm_f_up=35, arm_f_lo=150, arm_b_up=25, arm_b_lo=145), 90, ""),
              (P(spine=180, arm_f_up=-10, arm_f_lo=140, arm_b_up=30, arm_b_lo=150, root=(-1, 0)), 70, "hold"),
              (P(spine=152, head=166, arm_f_up=92, arm_f_lo=90, arm_b_up=10, arm_b_lo=140, leg_f_up=42, leg_b_up=-36, leg_b_lo=-36, root=(3, 0)), 140, "hit"),
              (P(arm_f_up=35, arm_f_lo=150, arm_b_up=25, arm_b_lo=145), 100, "")],
    # front kick: chamber the knee first, torso leans AWAY, then snap out
    "kick": [(P(arm_f_up=35, arm_f_lo=150, arm_b_up=25, arm_b_lo=145), 90, ""),
             (P(spine=188, arm_f_up=35, arm_f_lo=150, arm_b_up=25, arm_b_lo=145, leg_f_up=95, leg_f_lo=-10, foot_f=60, leg_b_up=-4, leg_b_lo=-8), 90, "hold"),
             (P(spine=205, head=196, arm_f_up=20, arm_f_lo=120, arm_b_up=-20, arm_b_lo=100, leg_f_up=98, leg_f_lo=92, foot_f=150, leg_b_up=-6, leg_b_lo=-10), 150, "hit"),
             (P(spine=188, leg_f_up=95, leg_f_lo=-10, foot_f=60, leg_b_up=-4, leg_b_lo=-8, arm_f_up=35, arm_f_lo=150), 80, ""),
             (P(arm_f_up=35, arm_f_lo=150, arm_b_up=25, arm_b_lo=145), 100, "")],
    # pistol / rifle shot: recoil is small - only the arms and gun move (1 px back, or the forearm tips up 45 degrees); muzzle flash 1-2 frames, no bigger than the head
    "shoot": [(P(spine=172, arm_f_up=90, arm_f_lo=90, arm_b_up=80, arm_b_lo=92, weapon=90), 120, "hold"),
              (P(spine=172, arm_f_up=90, arm_f_lo=90, arm_b_up=80, arm_b_lo=92, weapon=90), 50, "hit"),
              (P(spine=176, arm_f_up=94, arm_f_lo=128, arm_b_up=84, arm_b_lo=120, weapon=135, root=(-1, 0)), 70, ""),
              (P(spine=174, arm_f_up=92, arm_f_lo=104, arm_b_up=82, arm_b_lo=100, weapon=104), 80, ""),
              (P(spine=172, arm_f_up=90, arm_f_lo=90, arm_b_up=80, arm_b_lo=92, weapon=90), 100, "")],
    # shield on the back arm: it jumps up and forward in one frame, the body hardly moves
    "block": [(P(), 80, ""), (P(spine=176, arm_b_up=75, arm_b_lo=120, arm_f_up=10, arm_f_lo=60, weapon=60, root=(-1, 1)), 60, ""),
              (P(spine=178, arm_b_up=80, arm_b_lo=125, arm_f_up=10, arm_f_lo=60, weapon=60, root=(-2, 1)), 300, "hold"), (P(), 100, "")],
    "hurt": [(P(spine=200, head=208, arm_f_up=-40, arm_f_lo=20, arm_b_up=-30, arm_b_lo=10, weapon=40, leg_f_up=10, root=(-3, 0)), 80, "hit"),
             (P(spine=192, head=198, arm_f_up=-20, arm_f_lo=40, arm_b_up=-10, arm_b_lo=30, weapon=70, root=(-4, 1)), 160, "hold"), (P(), 120, "")],
    # spell: staff or hand raised, held, thrust forward on the release
    "cast": [(P(), 100, ""), (P(spine=184, arm_f_up=150, arm_f_lo=170, weapon=190, arm_b_up=-20, arm_b_lo=40, root=(-1, 0)), 120, ""),
             (P(spine=186, arm_f_up=160, arm_f_lo=178, weapon=195, arm_b_up=-25, arm_b_lo=35, root=(-1, -1)), 260, "hold"),
             (P(spine=164, arm_f_up=95, arm_f_lo=92, weapon=120, arm_b_up=-30, arm_b_lo=20, leg_f_up=36, root=(2, 0)), 80, "release"),
             (P(spine=166, arm_f_up=92, arm_f_lo=90, weapon=118, arm_b_up=-30, arm_b_lo=20, leg_f_up=36, root=(2, 0)), 220, "hold"), (P(), 120, "")],
}
LOOPS = ("idle", "walk", "run")


def hold(frames, **bones):
    """the same action with some bones fixed in every frame: carry a staff upright through a walk (hold(ACTIONS["walk"], arm_f_up=20, arm_f_lo=80, weapon=180)),
    keep a shield arm in guard through a slash (hold(ACTIONS["slash"], arm_b_up=45, arm_b_lo=95)), or straighten a lean (spine=180)."""
    return [(dict(p, **bones), ms, tag) for p, ms, tag in frames]


def tween(frames, extra=1, loop=False):
    """insert `extra` eased in-betweens between consecutive keys, sharing the first key's time; nothing is inserted before a "smear" frame (a swing is one frame)"""
    out = []; pairs = list(zip(frames, frames[1:] + (frames[:1] if loop else [])))
    for (p0, ms, tag), (p1, _, tag1) in pairs:
        if tag1 == "smear" or tag == "hold" and p0 == p1: out.append((p0, ms, tag)); continue
        out.append((p0, ms / (extra + 1), tag))
        for k in range(1, extra + 1): out.append((lerp_pose(p0, p1, EASES["inout"](k / (extra + 1))), ms / (extra + 1), ""))
    if not loop: out.append(frames[-1])
    return out
