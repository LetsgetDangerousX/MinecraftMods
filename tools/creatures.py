"""Creature models and stats for the Dinos & Dragons add-on.

Every creature is a function that returns a `geo.Model` plus a `Species`
record with its gameplay numbers.  Model units are pixels (16 = 1 block),
+Y is up and the creature faces -Z.  The client-side `scale` makes the
models bigger in game without making the texture higher resolution.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from geo import Model, Paint


@dataclass
class Species:
    id: str
    name: str
    kind: str                     # "dino" or "dragon"
    model: Model
    scale: float                  # client render scale
    collision: tuple              # (width, height) in blocks
    health: int
    attack: int
    speed: float                  # ground speed (also used while ridden on ground)
    tame_items: list
    tame_chance: float
    heal_items: list              # [(item, amount)]
    seats: list                   # [(x, y, z)] in blocks, +z = forward
    egg: tuple                    # (base, overlay) colours
    spawns: list                  # spawn rule conditions (see build.py)
    sounds: dict
    anim: dict                    # bone roles for animation generation
    carnivore: bool = False
    prey: list = field(default_factory=list)
    fly_speed: float = 0.0        # ridden flight speed (dragons)
    breath: str | None = None     # fire | frost | spores | storm | roar
    loot: list = field(default_factory=list)  # [(item, min, max)]
    description: str = ""
    family: list = field(default_factory=list)
    wander_speed: float = 0.6


# --------------------------------------------------------------------------
# Shared paints
# --------------------------------------------------------------------------
IVORY = Paint("#e9dfc4", noise=0.04)
CLAW = Paint("#3a332b", noise=0.05)


def eye_paint(p: Paint, eye: str) -> Paint:
    return Paint(p.base, p.belly, p.top, p.pattern, p.pattern_color, eye, False, p.ridge, p.noise, p.belly_frac)


def teeth_paint(p: Paint) -> Paint:
    return Paint(p.base, p.belly, p.top, None, None, None, True, None, p.noise, p.belly_frac)


# --------------------------------------------------------------------------
# Tyrannosaurus rex
# --------------------------------------------------------------------------

def build_trex():
    m = Model("geometry.dd.trex", visible_bounds=(10, 7, (0, 3, 0)))
    skin = Paint("#6e5b3a", belly="#cdb78c", pattern="stripes", pattern_color="#4a3b24", ridge="#4f3f27")
    plain = Paint("#6e5b3a", belly="#cdb78c")
    head = Paint("#6a5636", belly="#cdb78c", eyes="#f0a020", ridge="#4f3f27")
    m.bone("root", pivot=(0, 0, 0))
    m.bone("body", "root", (0, 30, 2))
    m.cube("body", (-8, 22, -12), (16, 15, 24), skin)
    m.cube("body", (-7, 20, -17), (14, 15, 6), plain)
    m.cube("body", (-7.5, 23, 11), (15, 13, 7), skin)
    m.bone("neck", "body", (0, 32, -16))
    m.cube("neck", (-5, 29, -23), (10, 11, 8), skin)
    m.bone("head", "neck", (0, 34, -22))
    m.cube("head", (-6.5, 32, -34), (13, 11, 12), head)
    m.cube("head", (-5, 32, -45), (10, 7, 11), teeth_paint(plain))
    m.cube("head", (-5.5, 38, -40), (11, 2, 6), Paint("#5a4a2e"))
    m.bone("jaw", "head", (0, 32, -24))
    m.cube("jaw", (-4.5, 28, -44), (9, 4, 19), Paint("#6e5b3a", belly="#d9c79f", teeth=True))
    m.bone("arm_l", "body", (6, 26, -13))
    m.cube("arm_l", (5, 20, -14), (2, 7, 3), plain)
    m.cube("arm_l", (5, 18, -17), (2, 2, 4), CLAW)
    m.mirror_bone("arm_l", "arm_r")
    m.bone("leg_l", "root", (7, 31, 5))
    m.cube("leg_l", (3.5, 17, -1), (7, 15, 12), skin)
    m.cube("leg_l", (4.5, 5, 5), (5, 13, 6), plain)
    m.cube("leg_l", (3.5, 0, -3), (7, 5, 13), plain)
    m.cube("leg_l", (3.5, 0, -5), (7, 2, 2), IVORY)
    m.mirror_bone("leg_l", "leg_r")
    m.bone("tail1", "body", (0, 32, 17))
    m.cube("tail1", (-6, 25, 17), (12, 12, 13), skin)
    m.bone("tail2", "tail1", (0, 31, 29))
    m.cube("tail2", (-4.5, 26, 29), (9, 9, 13), skin)
    m.bone("tail3", "tail2", (0, 30.5, 41))
    m.cube("tail3", (-3, 27, 41), (6, 6, 13), skin)
    m.bone("tail4", "tail3", (0, 30, 53))
    m.cube("tail4", (-1.5, 28, 53), (3, 3, 11), plain)
    m.paint(seed=11)
    s = 1.25
    return Species(
        id="trex", name="Tyrannosaurus Rex", kind="dino", model=m, scale=s,
        collision=(2.4, 3.2), health=120, attack=14, speed=0.28,
        tame_items=["beef", "porkchop", "mutton", "chicken", "rabbit",
                    "cooked_beef", "cooked_porkchop", "cooked_mutton", "cooked_chicken"],
        tame_chance=0.2,
        heal_items=[("beef", 10), ("porkchop", 10), ("mutton", 8), ("cooked_beef", 16), ("cooked_porkchop", 16)],
        seats=[(0, 2.75, 0.45)],
        egg=("#6e5b3a", "#cdb78c"),
        spawns=[("savanna", 6, 1, 1), ("jungle", 3, 1, 1), ("plains", 2, 1, 1)],
        sounds=dict(ambient="mob.ravager.ambient", hurt="mob.ravager.hurt", death="mob.ravager.death",
                    step="mob.ravager.step", pitch=(0.6, 0.75), volume=1.4),
        anim=dict(legs=[("leg_l", 0), ("leg_r", 180)], arms=[("arm_l", 0), ("arm_r", 180)],
                  tail=["tail1", "tail2", "tail3", "tail4"], neck=["neck"], head="head", jaw="jaw",
                  walk_freq=20.0, walk_amp=28.0, leg_len=31, biped=True, sit_drop=24),
        carnivore=True, prey=["cow", "pig", "sheep", "goat"],
        breath="roar",
        loot=[("beef", 3, 7), ("bone", 1, 4), ("leather", 1, 3)],
        description="The tyrant king. Tame it with raw or cooked meat.",
        family=["dinosaur", "trex"],
    )


# --------------------------------------------------------------------------
# Triceratops
# --------------------------------------------------------------------------

def build_triceratops():
    m = Model("geometry.dd.triceratops", visible_bounds=(7, 4, (0, 1.5, 0)))
    skin = Paint("#9a6037", belly="#dcc39a", pattern="scales", ridge="#7a4524")
    head = Paint("#9a6037", belly="#dcc39a", eyes="#2b1d12", ridge="#7a4524")
    frill = Paint("#c97a2e", pattern="spots", pattern_color="#5b2f14", edge="#4a2610")
    beak = Paint("#3d3026", noise=0.04)
    m.bone("root")
    m.bone("body", "root", (0, 18, 0))
    m.cube("body", (-8, 10, -12), (16, 14, 25), skin)
    m.cube("body", (-7, 23, -9), (14, 3, 18), skin)
    m.bone("head", "body", (0, 17, -12))
    m.cube("head", (-5, 10, -22), (10, 10, 11), head)
    m.cube("head", (-3, 9, -27), (6, 7, 5), Paint("#9a6037", belly="#dcc39a"))
    m.cube("head", (-2, 8.5, -29), (4, 5, 2), beak)
    m.cube("head", (-8, 13, -13), (16, 12, 2), frill, pivot=(0, 14, -12), rotation=(-15, 0, 0))
    m.cube("head", (2.5, 18, -32), (2, 2, 13), IVORY, pivot=(3.5, 19, -20), rotation=(-12, 0, 0))
    m.cube("head", (-4.5, 18, -32), (2, 2, 13), IVORY, pivot=(-3.5, 19, -20), rotation=(-12, 0, 0))
    m.cube("head", (-1, 15, -28), (2, 4, 2), IVORY)
    for i, (bone, px, pz, size) in enumerate([("leg_fl", 5.5, -8, (5, 12, 6)), ("leg_bl", 5.5, 7, (6, 13, 7))]):
        m.bone(bone, "root", (px, size[1], pz))
        m.cube(bone, (px - size[0] / 2, 0, pz - size[2] / 2), size, Paint("#8a5532", belly="#6b4026"))
        m.cube(bone, (px - size[0] / 2 - 0.5, 0, pz - size[2] / 2 - 1), (size[0] + 1, 2, 2), CLAW)
    m.mirror_bone("leg_fl", "leg_fr")
    m.mirror_bone("leg_bl", "leg_br")
    m.bone("tail1", "body", (0, 18, 12))
    m.cube("tail1", (-4, 13, 12), (8, 8, 10), skin)
    m.bone("tail2", "tail1", (0, 17, 21))
    m.cube("tail2", (-2.5, 14, 21), (5, 5, 9), skin)
    m.bone("tail3", "tail2", (0, 16.5, 29))
    m.cube("tail3", (-1, 15, 29), (2, 3, 7), skin)
    m.paint(seed=21)
    return Species(
        id="triceratops", name="Triceratops", kind="dino", model=m, scale=1.3,
        collision=(2.2, 2.1), health=90, attack=9, speed=0.24,
        tame_items=["wheat", "apple", "carrot", "sweet_berries", "melon_slice", "hay_block"],
        tame_chance=0.3,
        heal_items=[("wheat", 6), ("apple", 8), ("carrot", 6), ("hay_block", 30)],
        seats=[(0, 1.9, 0.0)],
        egg=("#9a6037", "#c97a2e"),
        spawns=[("plains", 7, 2, 4), ("savanna", 5, 2, 3)],
        sounds=dict(ambient="mob.hoglin.ambient", hurt="mob.hoglin.hurt", death="mob.hoglin.death",
                    step="mob.hoglin.step", pitch=(0.55, 0.7), volume=1.1),
        anim=dict(legs=[("leg_fl", 0), ("leg_fr", 180), ("leg_bl", 180), ("leg_br", 0)],
                  tail=["tail1", "tail2", "tail3"], neck=[], head="head", jaw=None,
                  walk_freq=30.0, walk_amp=30.0, leg_len=12, biped=False, sit_drop=10),
        loot=[("beef", 2, 5), ("leather", 1, 4), ("bone", 0, 2)],
        description="Three horns and a big frill. Tame it with wheat, apples, carrots or berries.",
        family=["dinosaur", "triceratops"],
    )


# --------------------------------------------------------------------------
# Velociraptor
# --------------------------------------------------------------------------

def build_raptor():
    m = Model("geometry.dd.velociraptor", visible_bounds=(5, 3, (0, 1, 0)))
    skin = Paint("#b38a55", belly="#efe0bf", pattern="stripes", pattern_color="#5c3f20", ridge="#5c3f20")
    plain = Paint("#b38a55", belly="#efe0bf")
    feather = Paint("#2f7f7b", noise=0.1, pattern="bands", pattern_color="#1d4f4c")
    m.bone("root")
    m.bone("body", "root", (0, 16, 0))
    m.cube("body", (-3.5, 12, -7), (7, 7, 14), skin)
    m.cube("body", (-1, 19, -6), (2, 1, 11), feather)
    m.bone("neck", "body", (0, 17, -7))
    m.cube("neck", (-2, 15, -11), (4, 8, 5), plain)
    m.cube("neck", (-0.5, 21, -8), (1, 3, 4), feather)
    m.bone("head", "neck", (0, 22, -9))
    m.cube("head", (-2.5, 20, -16), (5, 5, 7), Paint("#b38a55", belly="#efe0bf", eyes="#e8c21c", ridge="#5c3f20"))
    m.cube("head", (-1.5, 20.5, -21), (3, 3, 5), teeth_paint(plain))
    m.cube("head", (-0.5, 25, -15), (1, 2, 6), feather)
    m.bone("jaw", "head", (0, 20.5, -11))
    m.cube("jaw", (-1.5, 19, -20.5), (3, 2, 6), Paint("#b38a55", belly="#efe0bf", teeth=True))
    m.bone("arm_l", "body", (3.5, 15, -5))
    m.cube("arm_l", (3, 11, -6), (2, 5, 2), plain)
    m.cube("arm_l", (3, 10, -8), (2, 1, 3), CLAW)
    m.cube("arm_l", (5, 11, -6), (1, 5, 3), feather)
    m.mirror_bone("arm_l", "arm_r")
    m.bone("leg_l", "root", (3, 15, 2))
    m.cube("leg_l", (1.5, 8, -1), (3, 8, 5), skin)
    m.cube("leg_l", (2, 3, 2), (2, 6, 2), plain)
    m.cube("leg_l", (1.5, 0, -2), (3, 3, 5), plain)
    m.cube("leg_l", (2.5, 2, -3), (1, 3, 1), IVORY)
    m.mirror_bone("leg_l", "leg_r")
    m.bone("tail1", "body", (0, 16, 7))
    m.cube("tail1", (-2.5, 13, 7), (5, 5, 8), skin)
    m.bone("tail2", "tail1", (0, 15.5, 14))
    m.cube("tail2", (-1.5, 14, 14), (3, 3, 9), skin)
    m.bone("tail3", "tail2", (0, 15.5, 22))
    m.cube("tail3", (-1, 14.5, 22), (2, 2, 7), plain)
    m.cube("tail3", (-2.5, 15, 25), (5, 1, 5), feather)
    m.paint(seed=31)
    return Species(
        id="velociraptor", name="Velociraptor", kind="dino", model=m, scale=1.15,
        collision=(0.9, 1.6), health=35, attack=6, speed=0.36,
        tame_items=["chicken", "rabbit", "cooked_chicken", "cooked_rabbit", "cod"],
        tame_chance=0.33,
        heal_items=[("chicken", 6), ("rabbit", 6), ("cooked_chicken", 10), ("cooked_rabbit", 10)],
        seats=[(0, 1.25, 0.1)],
        egg=("#b38a55", "#2f7f7b"),
        spawns=[("forest", 5, 2, 3), ("jungle", 5, 2, 4), ("desert", 4, 2, 3), ("mesa", 4, 2, 3)],
        sounds=dict(ambient="mob.fox.screech", hurt="mob.fox.hurt", death="mob.fox.death",
                    step="mob.wolf.step", pitch=(0.7, 0.9), volume=1.0),
        anim=dict(legs=[("leg_l", 0), ("leg_r", 180)], arms=[("arm_l", 0), ("arm_r", 180)],
                  tail=["tail1", "tail2", "tail3"], neck=["neck"], head="head", jaw="jaw",
                  walk_freq=38.0, walk_amp=35.0, leg_len=15, biped=True, sit_drop=11),
        carnivore=True, prey=["chicken", "rabbit"],
        breath="roar",
        loot=[("chicken", 1, 2), ("feather", 1, 4), ("bone", 0, 2)],
        description="Fast, clever pack hunter. Tame it with chicken, rabbit or fish.",
        family=["dinosaur", "velociraptor"],
    )


# --------------------------------------------------------------------------
# Brachiosaurus
# --------------------------------------------------------------------------

def build_brachio():
    m = Model("geometry.dd.brachiosaurus", visible_bounds=(12, 9, (0, 4, 0)))
    skin = Paint("#7b8c6c", belly="#c4cdb0", pattern="spots", pattern_color="#5b6a4e", ridge="#5b6a4e")
    plain = Paint("#7b8c6c", belly="#c4cdb0")
    leg = Paint("#728263", belly="#5f6d52")
    m.bone("root")
    m.bone("body", "root", (0, 28, 0))
    m.cube("body", (-9, 20, -14), (18, 18, 30), skin)
    m.cube("body", (-8, 33, -17), (16, 8, 12), skin)
    m.bone("neck1", "body", (0, 36, -18))
    m.cube("neck1", (-4.5, 33, -23), (9, 15, 8), plain)
    m.bone("neck2", "neck1", (0, 47, -20))
    m.cube("neck2", (-4, 46, -25), (8, 14, 7), plain)
    m.bone("neck3", "neck2", (0, 59, -22))
    m.cube("neck3", (-3.5, 58, -27), (7, 13, 6), plain)
    m.bone("head", "neck3", (0, 70, -24))
    m.cube("head", (-3.5, 67, -35), (7, 7, 10), Paint("#7b8c6c", belly="#c4cdb0", eyes="#2b2014", ridge="#5b6a4e"))
    m.cube("head", (-2.5, 66.5, -40), (5, 5, 5), plain)
    m.cube("head", (-2, 73, -33), (4, 3, 6), Paint("#6a7a5c"))
    for bone, px, pz, size in [("leg_fl", 6, -8, (6, 26, 6)), ("leg_bl", 6, 10, (7, 23, 7))]:
        m.bone(bone, "root", (px, size[1], pz))
        m.cube(bone, (px - size[0] / 2, 0, pz - size[2] / 2), size, leg)
        m.cube(bone, (px - size[0] / 2 - 0.5, 0, pz - size[2] / 2 - 0.5), (size[0] + 1, 3, size[2] + 1), Paint("#5f6d52"))
    m.mirror_bone("leg_fl", "leg_fr")
    m.mirror_bone("leg_bl", "leg_br")
    m.bone("tail1", "body", (0, 31, 16))
    m.cube("tail1", (-5, 25, 16), (10, 10, 12), skin)
    m.bone("tail2", "tail1", (0, 30, 27))
    m.cube("tail2", (-3.5, 26.5, 27), (7, 7, 12), skin)
    m.bone("tail3", "tail2", (0, 29.5, 38))
    m.cube("tail3", (-2, 27.5, 38), (4, 4, 12), plain)
    m.bone("tail4", "tail3", (0, 29.5, 49))
    m.cube("tail4", (-1, 28.5, 49), (2, 2, 10), plain)
    m.paint(seed=41)
    s = 1.6
    return Species(
        id="brachiosaurus", name="Brachiosaurus", kind="dino", model=m, scale=s,
        collision=(3.0, 4.0), health=160, attack=8, speed=0.2,
        tame_items=["apple", "melon_slice", "sweet_berries", "oak_leaves", "golden_apple"],
        tame_chance=0.25,
        heal_items=[("apple", 10), ("melon_slice", 6), ("sweet_berries", 4), ("golden_apple", 40)],
        seats=[(0, 3.75, 0.7), (0, 3.75, -0.4), (0, 3.65, -1.5)],
        egg=("#7b8c6c", "#c4cdb0"),
        spawns=[("plains", 3, 1, 2), ("savanna", 3, 1, 2), ("jungle", 2, 1, 1)],
        sounds=dict(ambient="mob.sniffer.idle", hurt="mob.sniffer.hurt", death="mob.sniffer.death",
                    step="mob.irongolem.walk", pitch=(0.4, 0.55), volume=1.6),
        anim=dict(legs=[("leg_fl", 0), ("leg_fr", 180), ("leg_bl", 180), ("leg_br", 0)],
                  tail=["tail1", "tail2", "tail3", "tail4"], neck=["neck1", "neck2", "neck3"], head="head",
                  jaw=None, walk_freq=14.0, walk_amp=22.0, leg_len=25, biped=False, sit_drop=19),
        loot=[("beef", 4, 9), ("leather", 2, 5), ("bone", 1, 4)],
        description="A gentle giant with room for three riders. Tame it with apples, melon or berries.",
        family=["dinosaur", "brachiosaurus"],
    )


# --------------------------------------------------------------------------
# Stegosaurus
# --------------------------------------------------------------------------

def build_stego():
    m = Model("geometry.dd.stegosaurus", visible_bounds=(7, 4, (0, 1.5, 0)))
    skin = Paint("#5f7650", belly="#c9cfa4", pattern="spots", pattern_color="#465a3a")
    plain = Paint("#5f7650", belly="#c9cfa4")
    plate = Paint("#c4553a", pattern="plates", pattern_color="#e58a55", edge="#6b2a1b", noise=0.05)
    m.bone("root")
    m.bone("body", "root", (0, 18, 0))
    m.cube("body", (-7, 10, -12), (14, 14, 26), skin)
    m.cube("body", (-6, 23, -6), (12, 3, 16), skin)
    plates = [(-10, 6, 0.5), (-6, 8, -2.5), (-2, 11, 0.5), (2, 12, -2.5), (6, 11, 0.5), (10, 9, -2.5)]
    for z, h, x in plates:
        m.cube("body", (x, 22, z), (2, h, 4), plate)
    m.bone("neck", "body", (0, 16, -12))
    m.cube("neck", (-3, 10, -19), (6, 7, 8), plain)
    m.bone("head", "neck", (0, 13, -18))
    m.cube("head", (-2.5, 8, -26), (5, 6, 8), Paint("#5f7650", belly="#c9cfa4", eyes="#2a1d12"))
    m.cube("head", (-1.5, 8, -29), (3, 4, 3), Paint("#4b5e3f"))
    for bone, px, pz, size in [("leg_fl", 4.5, -8, (4, 11, 5)), ("leg_bl", 5, 8, (5, 15, 7))]:
        m.bone(bone, "root", (px, size[1], pz))
        m.cube(bone, (px - size[0] / 2, 0, pz - size[2] / 2), size, Paint("#56694a", belly="#3f4d36"))
        m.cube(bone, (px - size[0] / 2, 0, pz - size[2] / 2 - 1), (size[0], 2, 1), CLAW)
    m.mirror_bone("leg_fl", "leg_fr")
    m.mirror_bone("leg_bl", "leg_br")
    m.bone("tail1", "body", (0, 18, 14))
    m.cube("tail1", (-4, 14, 13), (8, 8, 10), skin)
    m.cube("tail1", (-1, 21, 15), (2, 6, 4), plate)
    m.bone("tail2", "tail1", (0, 17.5, 22))
    m.cube("tail2", (-2.5, 15, 22), (5, 5, 10), skin)
    m.cube("tail2", (-1, 19, 24), (2, 4, 3), plate)
    m.bone("tail3", "tail2", (0, 17, 31))
    m.cube("tail3", (-1.5, 15.5, 31), (3, 3, 10), plain)
    for z in (34, 38):
        m.cube("tail3", (1.5, 17, z), (6, 1, 1), IVORY, pivot=(1.5, 17.5, z + 0.5), rotation=(0, 0, 30))
        m.cube("tail3", (-7.5, 17, z), (6, 1, 1), IVORY, pivot=(-1.5, 17.5, z + 0.5), rotation=(0, 0, -30))
    m.paint(seed=51)
    return Species(
        id="stegosaurus", name="Stegosaurus", kind="dino", model=m, scale=1.3,
        collision=(2.0, 2.3), health=80, attack=10, speed=0.22,
        tame_items=["wheat", "carrot", "potato", "beetroot", "apple"],
        tame_chance=0.3,
        heal_items=[("wheat", 6), ("carrot", 6), ("potato", 6), ("beetroot", 6), ("apple", 8)],
        seats=[(0, 2.15, 0.35)],
        egg=("#5f7650", "#c4553a"),
        spawns=[("forest", 5, 1, 3), ("taiga", 4, 1, 3), ("plains", 2, 1, 2)],
        sounds=dict(ambient="mob.polarbear.idle", hurt="mob.polarbear.hurt", death="mob.polarbear.death",
                    step="mob.polarbear.step", pitch=(0.55, 0.7), volume=1.0),
        anim=dict(legs=[("leg_fl", 0), ("leg_fr", 180), ("leg_bl", 180), ("leg_br", 0)],
                  tail=["tail1", "tail2", "tail3"], neck=["neck"], head="head", jaw=None,
                  walk_freq=28.0, walk_amp=28.0, leg_len=13, biped=False, sit_drop=10),
        loot=[("beef", 2, 5), ("leather", 1, 3), ("bone", 0, 3)],
        description="Armoured plates and a spiky tail. Tame it with wheat, carrots, potatoes or beetroot.",
        family=["dinosaur", "stegosaurus"],
    )


# --------------------------------------------------------------------------
# Dragons (one parametrised builder, four looks)
# --------------------------------------------------------------------------

DRAGON_LOOKS = {
    "fire": dict(
        skin=Paint("#a8281e", belly="#f0a43a", pattern="scales", ridge="#6e140e"),
        membrane=Paint("#d9622b", belly="#d9622b", pattern="veins", pattern_color="#7a1d12", noise=0.05),
        horn=Paint("#efe3c2", noise=0.04), spike=Paint("#3b1010", noise=0.05),
        eyes="#ffd21f", horns="swept", tail="spade", spikes=6),
    "ice": dict(
        skin=Paint("#d4ecf7", belly="#ffffff", pattern="scales", ridge="#7fd1f0"),
        membrane=Paint("#9fd8ef", belly="#9fd8ef", pattern="veins", pattern_color="#5aa8cc", noise=0.04),
        horn=Paint("#bff3ff", noise=0.03), spike=Paint("#6cc7e8", noise=0.04),
        eyes="#1f4fd1", horns="crown", tail="crystal", spikes=7),
    "forest": dict(
        skin=Paint("#3e7d32", belly="#b8d36b", pattern="spots", pattern_color="#2b5a22", ridge="#2b5a22"),
        membrane=Paint("#62a947", belly="#62a947", pattern="veins", pattern_color="#2f6a24", noise=0.06),
        horn=Paint("#6b4a2a", noise=0.06), spike=Paint("#7cc44f", noise=0.08),
        eyes="#f2b01e", horns="branch", tail="leaf", spikes=5),
    "storm": dict(
        skin=Paint("#3b2f5c", belly="#8e85b5", pattern="stripes", pattern_color="#f5e142", ridge="#f5e142"),
        membrane=Paint("#5b3f8c", belly="#5b3f8c", pattern="veins", pattern_color="#f5e142", noise=0.05),
        horn=Paint("#f1cf45", noise=0.04), spike=Paint("#f5e142", noise=0.04),
        eyes="#fff35c", horns="long", tail="blade", spikes=6),
}


def build_dragon(look: str):
    L = DRAGON_LOOKS[look]
    skin, mem, horn, spike = L["skin"], L["membrane"], L["horn"], L["spike"]
    plain = Paint(skin.base, skin.belly, ridge=skin.ridge)
    m = Model(f"geometry.dd.{look}_dragon", visible_bounds=(12, 6, (0, 2, 0)))
    m.bone("root")
    m.bone("body", "root", (0, 18, 0))
    m.cube("body", (-6, 13, -10), (12, 11, 22), skin)
    m.cube("body", (-5.5, 12, -15), (11, 11, 6), plain)
    n = L["spikes"]
    for i in range(n):
        z = -9 + i * (20 / max(1, n - 1))
        h = 3 if L["horns"] != "crown" else 2
        m.cube("body", (-0.5, 23.5, z), (1, h, 2), spike)
    # neck: two segments rising forward
    m.bone("neck1", "body", (0, 20, -13), rotation=(-35, 0, 0))
    m.cube("neck1", (-3.5, 16.5, -22), (7, 7, 10), plain)
    m.cube("neck1", (-0.5, 23.5, -20), (1, 2, 2), spike)
    m.bone("neck2", "neck1", (0, 20, -21), rotation=(10, 0, 0))
    m.cube("neck2", (-3, 17, -29), (6, 6, 9), plain)
    m.cube("neck2", (-0.5, 23, -26), (1, 2, 2), spike)
    m.bone("head", "neck2", (0, 20, -28), rotation=(25, 0, 0))
    m.cube("head", (-4.5, 17, -36), (9, 7, 9), Paint(skin.base, skin.belly, eyes=L["eyes"], ridge=skin.ridge))
    m.cube("head", (-3.5, 17, -43), (7, 5, 7), teeth_paint(plain))
    m.cube("head", (-2.5, 21.5, -42), (1, 1, 2), Paint("#1b1210"))
    m.cube("head", (1.5, 21.5, -42), (1, 1, 2), Paint("#1b1210"))
    style = L["horns"]
    if style == "swept":
        m.cube("head", (2, 22, -31), (2, 2, 9), horn, pivot=(3, 23, -31), rotation=(-25, -10, 0))
        m.cube("head", (-4, 22, -31), (2, 2, 9), horn, pivot=(-3, 23, -31), rotation=(-25, 10, 0))
    elif style == "crown":
        for x in (-4, -1.5, 0.5, 3):
            m.cube("head", (x, 23, -32), (1, 4, 1), horn, pivot=(x + 0.5, 23, -31.5), rotation=(-30, 0, 0))
        m.cube("head", (4.5, 19, -31), (1, 4, 5), horn)
        m.cube("head", (-5.5, 19, -31), (1, 4, 5), horn)
    elif style == "branch":
        m.cube("head", (2, 22, -31), (2, 2, 6), horn, pivot=(3, 23, -31), rotation=(-40, -15, 0))
        m.cube("head", (-4, 22, -31), (2, 2, 6), horn, pivot=(-3, 23, -31), rotation=(-40, 15, 0))
        m.cube("head", (-1, 24, -35), (2, 2, 6), spike, pivot=(0, 24, -32), rotation=(-20, 0, 0))
    elif style == "long":
        m.cube("head", (2.5, 22, -29), (2, 2, 12), horn, pivot=(3.5, 23, -29), rotation=(-15, -5, 0))
        m.cube("head", (-4.5, 22, -29), (2, 2, 12), horn, pivot=(-3.5, 23, -29), rotation=(-15, 5, 0))
        m.cube("head", (-1, 21.5, -41), (2, 2, 3), horn)
    m.bone("jaw", "head", (0, 18, -35))
    m.cube("jaw", (-3, 15, -42), (6, 2, 8), Paint(skin.base, skin.belly, teeth=True))
    # legs
    m.bone("leg_fl", "root", (5, 17, -8))
    m.cube("leg_fl", (3, 6, -10), (4, 12, 5), plain)
    m.cube("leg_fl", (2.5, 0, -12), (5, 6, 7), plain)
    m.cube("leg_fl", (2.5, 0, -13), (5, 1, 1), CLAW)
    m.mirror_bone("leg_fl", "leg_fr")
    m.bone("leg_bl", "root", (5.5, 18, 7))
    m.cube("leg_bl", (3, 8, 3), (5, 11, 8), skin)
    m.cube("leg_bl", (3, 0, 3), (5, 8, 7), plain)
    m.cube("leg_bl", (3, 0, 2), (5, 1, 1), CLAW)
    m.mirror_bone("leg_bl", "leg_br")
    # tail
    m.bone("tail1", "body", (0, 19, 12))
    m.cube("tail1", (-4, 15, 12), (8, 7, 10), skin)
    m.cube("tail1", (-0.5, 22, 15), (1, 2, 2), spike)
    m.bone("tail2", "tail1", (0, 18.5, 21))
    m.cube("tail2", (-3, 16, 21), (6, 5, 10), skin)
    m.cube("tail2", (-0.5, 21, 24), (1, 2, 2), spike)
    m.bone("tail3", "tail2", (0, 18, 30))
    m.cube("tail3", (-2, 16.5, 30), (4, 4, 10), plain)
    m.bone("tail4", "tail3", (0, 18, 39))
    m.cube("tail4", (-1, 17, 39), (2, 2, 9), plain)
    tail = L["tail"]
    if tail == "spade":
        m.cube("tail4", (-2.5, 17.5, 45), (5, 1, 5), spike)
    elif tail == "crystal":
        m.cube("tail4", (-1.5, 17, 45), (3, 4, 4), horn)
    elif tail == "leaf":
        m.cube("tail4", (-3, 17.5, 44), (6, 1, 6), mem)
    elif tail == "blade":
        m.cube("tail4", (-0.5, 16, 44), (1, 5, 7), horn)
    # wings: arm + membrane, two segments each side
    m.bone("wing_l", "body", (5.5, 23, -6))
    m.cube("wing_l", (5.5, 22, -7), (16, 2, 2), plain)
    m.cube("wing_l", (5.5, 22.5, -5), (16, 1, 15), mem)
    m.bone("wing_tip_l", "wing_l", (21.5, 23, -6))
    m.cube("wing_tip_l", (21.5, 22, -7), (16, 2, 2), plain)
    m.cube("wing_tip_l", (21.5, 22.5, -5), (14, 1, 11), mem)
    m.cube("wing_tip_l", (35.5, 22.5, -5), (2, 1, 5), mem)
    m.cube("wing_tip_l", (37.5, 22, -8), (2, 2, 2), horn)
    m.mirror_bone("wing_l", "wing_r")
    m.mirror_bone("wing_tip_l", "wing_tip_r", new_parent="wing_r")
    m.paint(seed={"fire": 61, "ice": 62, "forest": 63, "storm": 64}[look])
    return m


def dragon_species(look):
    m = build_dragon(look)
    common = dict(kind="dragon", model=m,
                  anim=dict(legs=[("leg_fl", 0), ("leg_fr", 180), ("leg_bl", 180), ("leg_br", 0)],
                            tail=["tail1", "tail2", "tail3", "tail4"], neck=["neck1", "neck2"], head="head",
                            jaw="jaw", walk_freq=26.0, walk_amp=30.0, leg_len=17, biped=False, sit_drop=12,
                            wings=dict(l="wing_l", r="wing_r", lt="wing_tip_l", rt="wing_tip_r")),
                  sounds=dict(ambient="mob.enderdragon.growl", hurt="mob.enderdragon.hit", death="mob.ravager.death",
                              step="mob.ravager.step", flap="mob.enderdragon.flap", pitch=(1.1, 1.35), volume=0.9),
                  carnivore=True, family=["dragon"])
    if look == "fire":
        s = 1.5
        return Species(id="fire_dragon", name="Fire Dragon", scale=s, collision=(2.2, 2.4),
                       health=100, attack=12, speed=0.28, fly_speed=0.06,
                       tame_items=["cooked_beef", "cooked_porkchop", "cooked_mutton", "cooked_chicken", "blaze_powder"],
                       tame_chance=0.25,
                       heal_items=[("cooked_beef", 16), ("cooked_porkchop", 16), ("cooked_mutton", 12), ("blaze_powder", 20)],
                       seats=[(0, 2.2, 0.2)], egg=("#a8281e", "#f0a43a"),
                       spawns=[("mesa", 5, 1, 1), ("desert", 3, 1, 1), ("savanna", 2, 1, 1)],
                       breath="fire", loot=[("blaze_powder", 1, 3), ("leather", 1, 3), ("bone", 1, 2)],
                       description="Breathes fire. Lives in badlands and deserts. Tame it with cooked meat.",
                       prey=["cow", "pig", "sheep"], **common)
    if look == "ice":
        s = 1.4
        return Species(id="ice_dragon", name="Ice Dragon", scale=s, collision=(2.1, 2.2),
                       health=100, attack=11, speed=0.28, fly_speed=0.055,
                       tame_items=["cod", "salmon", "cooked_cod", "cooked_salmon", "tropical_fish"],
                       tame_chance=0.25,
                       heal_items=[("cod", 8), ("salmon", 10), ("cooked_cod", 12), ("cooked_salmon", 14)],
                       seats=[(0, 2.05, 0.2)], egg=("#d4ecf7", "#7fd1f0"),
                       spawns=[("frozen", 6, 1, 1), ("cold", 2, 1, 1)],
                       breath="frost", loot=[("snowball", 2, 6), ("leather", 1, 3), ("bone", 1, 2)],
                       description="Freezes its foes. Lives in snowy lands. Tame it with fish.",
                       prey=["cod", "salmon", "rabbit"], **common)
    if look == "forest":
        s = 1.25
        return Species(id="forest_dragon", name="Forest Dragon", scale=s, collision=(1.9, 1.9),
                       health=80, attack=9, speed=0.32, fly_speed=0.07,
                       tame_items=["apple", "sweet_berries", "glow_berries", "melon_slice", "golden_apple"],
                       tame_chance=0.3,
                       heal_items=[("apple", 10), ("sweet_berries", 6), ("glow_berries", 6), ("golden_apple", 40)],
                       seats=[(0, 1.85, 0.15)], egg=("#3e7d32", "#b8d36b"),
                       spawns=[("forest", 3, 1, 1), ("jungle", 4, 1, 1), ("roofed", 4, 1, 1), ("birch", 2, 1, 1)],
                       breath="spores", loot=[("emerald", 0, 1), ("leather", 1, 3), ("bone", 1, 2)],
                       description="The fastest flyer, with poison spore breath. Tame it with apples or berries.",
                       prey=["rabbit", "chicken"], **common)
    s = 1.6
    return Species(id="storm_dragon", name="Storm Dragon", scale=s, collision=(2.4, 2.6),
                   health=130, attack=14, speed=0.28, fly_speed=0.065,
                   tame_items=["gold_ingot", "golden_carrot", "golden_apple"],
                   tame_chance=0.2,
                   heal_items=[("gold_ingot", 10), ("golden_carrot", 14), ("golden_apple", 40)],
                   seats=[(0, 2.35, 0.25)], egg=("#3b2f5c", "#f5e142"),
                   spawns=[("mountains", 4, 1, 1), ("extreme_hills", 4, 1, 1)],
                   breath="storm", loot=[("gold_ingot", 1, 3), ("leather", 1, 3), ("bone", 1, 2)],
                   description="Biggest of all, crackling with lightning. Lives in the mountains. Tame it with gold.",
                   prey=["goat", "sheep"], **common)


def all_species():
    return [
        dragon_species("fire"), dragon_species("ice"), dragon_species("forest"), dragon_species("storm"),
        build_trex(), build_triceratops(), build_raptor(), build_brachio(), build_stego(),
    ]
