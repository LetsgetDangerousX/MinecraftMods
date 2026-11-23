"""Spawn castle generator.

Produces Bedrock `/fill` and `/setblock` commands relative to the castle
centre at ground level (gate facing south) and keeps a voxel model of the
result so preview images can be rendered.

Design notes, following common castle-building advice (mixed stone
palette with dark trims, towers taller than the walls, buttresses to break
up long walls, overhanging machicolated battlements, a proper gatehouse
with a portcullis, a moat with a drawbridge):

    * round corner towers (11 wide) with spiral stairs and pointed slate roofs
    * curtain walls with a sloped plinth, buttresses, corbels and crenellations
    * gatehouse flanked by two round towers, portcullis, banners, drawbridge
    * moat all the way round
    * keep: great hall (fireplace, dais, chandeliers), two upper floors,
      four corner turrets with spires and a roof-top dragon landing pad
    * courtyard: mixed cobble paths, lean-to dinosaur stable, roofed well,
      flower garden, lantern posts everywhere (no monster spawns)
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw

AIR = "air"
WALL = "stone_bricks"
TRIM = "polished_andesite"
DARK = "deepslate_bricks"
ROOF = "deepslate_tiles"
ROOF_STAIR = "deepslate_tile_stairs"
WALL_STAIR = "stone_brick_stairs"
WOOD = "dark_oak_planks"
WOOD_STAIR = "dark_oak_stairs"
BEAM = "stripped_dark_oak_log"
FENCE = "dark_oak_fence"

EXTENT = 33                 # everything the castle touches: -33..33 in x and z
Y_MIN, Y_MAX = -10, 46
CLEAR_TOP = 44

R_OUT, R_IN = 22, 20        # curtain wall outer / inner face
WALL_TOP = 10               # top block of the curtain wall (wall-walk feet at y=11)
MOAT_IN, MOAT_OUT = 29, 31
SPAWN = (0, 1, 10)          # world spawn, on the path just inside the gate

# Bedrock stairs: weirdo_direction 0=east 1=west 2=south 3=north (the side you climb towards)
STAIR_DIR = {"east": 0, "west": 1, "south": 2, "north": 3}


class Builder:
    def __init__(self):
        n = 2 * EXTENT + 1
        self.grid = np.full((n, Y_MAX - Y_MIN + 1, n), "", dtype=object)
        self.cmds: list[str] = []

    @staticmethod
    def _state(states):
        if not states:
            return ""
        parts = []
        for k, v in states.items():
            if isinstance(v, bool):
                vv = "true" if v else "false"
            elif isinstance(v, int):
                vv = str(v)
            else:
                vv = f'"{v}"'
            parts.append(f'"{k}"={vv}')
        return " [" + ",".join(parts) + "]"

    def _set(self, x, y, z, block):
        gx, gy, gz = x + EXTENT, y - Y_MIN, z + EXTENT
        if 0 <= gx < self.grid.shape[0] and 0 <= gy < self.grid.shape[1] and 0 <= gz < self.grid.shape[2]:
            self.grid[gx, gy, gz] = block

    def fill(self, x1, y1, z1, x2, y2, z2, block, states=None, mode=None):
        xa, xb = sorted((x1, x2))
        ya, yb = sorted((y1, y2))
        za, zb = sorted((z1, z2))
        vol = (xb - xa + 1) * (yb - ya + 1) * (zb - za + 1)
        assert vol <= 32768, f"fill too large: {vol}"
        cmd = f"fill ~{xa} ~{ya} ~{za} ~{xb} ~{yb} ~{zb} {block}{self._state(states)}"
        if mode:
            cmd += f" {mode}"
        self.cmds.append(cmd)
        for x in range(xa, xb + 1):
            for y in range(ya, yb + 1):
                for z in range(za, zb + 1):
                    edge = x in (xa, xb) or y in (ya, yb) or z in (za, zb)
                    if mode == "hollow":
                        self._set(x, y, z, block if edge else AIR)
                    elif mode == "outline":
                        if edge:
                            self._set(x, y, z, block)
                    else:
                        self._set(x, y, z, block)

    def setblock(self, x, y, z, block, states=None):
        self.cmds.append(f"setblock ~{x} ~{y} ~{z} {block}{self._state(states)}")
        self._set(x, y, z, block)

    def get(self, x, y, z):
        return self.grid[x + EXTENT, y - Y_MIN, z + EXTENT]

    # -- shapes ----------------------------------------------------------
    def disc(self, cx, cz, r, y1, y2, block, states=None):
        for dx, (lo, hi) in disc_rows(r).items():
            self.fill(cx + dx, y1, cz + lo, cx + dx, y2, cz + hi, block, states)

    def stairs(self, x, y, z, facing, block=WALL_STAIR, upside_down=False):
        self.setblock(x, y, z, block, {"weirdo_direction": STAIR_DIR[facing], "upside_down_bit": upside_down})

    def lantern(self, x, y, z, hanging=False):
        self.setblock(x, y, z, "lantern", {"hanging": hanging})

    def post(self, x, z, height=2):
        self.fill(x, 1, z, x, height, z, FENCE)
        self.lantern(x, height + 1, z)


def disc_cells(r):
    n = int(math.ceil(r))
    return [(dx, dz) for dx in range(-n, n + 1) for dz in range(-n, n + 1) if dx * dx + dz * dz <= r * r]


def disc_rows(r):
    rows = {}
    for dx, dz in disc_cells(r):
        lo, hi = rows.get(dx, (dz, dz))
        rows[dx] = (min(lo, dz), max(hi, dz))
    return rows


def toward_center(dx, dz):
    """Facing for a stair at offset (dx, dz) that climbs towards the centre (None on diagonals)."""
    if abs(dx) > abs(dz):
        return "west" if dx > 0 else "east"
    if abs(dz) > abs(dx):
        return "north" if dz > 0 else "south"
    return None


def cone(b: Builder, cx, cz, base_y, r0, step):
    """Pointed slate roof: shrinking discs with stairs on every exposed edge."""
    y, r = base_y, r0
    while r >= 0.8:
        cells = disc_cells(r)
        inner = set(disc_cells(r - step))
        b.disc(cx, cz, r, y, y, ROOF)
        for dx, dz in cells:
            if (dx, dz) in inner:
                continue
            f = toward_center(dx, dz)
            if f:
                b.stairs(cx + dx, y, cz + dz, f, ROOF_STAIR)
        y += 1
        r -= step
    return y


def flag(b: Builder, x, y, z, color="red_wool", accent="yellow_wool", direction=(1, 0)):
    b.fill(x, y, z, x, y + 3, z, FENCE)
    b.setblock(x, y + 4, z, "lightning_rod")
    dx, dz = direction
    b.fill(x + dx, y + 2, z + dz, x + 2 * dx, y + 3, z + 2 * dz, color)
    b.setblock(x + 2 * dx, y + 3, z + 2 * dz, accent)


# --------------------------------------------------------------------------
# Site
# --------------------------------------------------------------------------

def site(b: Builder):
    e = EXTENT
    b.fill(-e, -8, -e, e, -5, e, "stone")
    b.fill(-e, -4, -e, e, -1, e, "stone")
    b.fill(-e, 0, -e, e, 0, e, "grass_block")
    y = 1
    while y <= CLEAR_TOP:
        b.fill(-e, y, -e, e, min(y + 6, CLEAR_TOP), e, AIR)
        y += 7
    # moat
    a, o = MOAT_IN, MOAT_OUT
    for (x1, z1, x2, z2) in [(-o, -o, o, -a), (-o, a, o, o), (-o, -a + 1, -a, a - 1), (a, -a + 1, o, a - 1)]:
        b.fill(x1, -4, z1, x2, -4, z2, "gravel")
        b.fill(x1, -3, z1, x2, -1, z2, "water")
        b.fill(x1, 0, z1, x2, 0, z2, AIR)
    # drawbridge
    b.fill(-3, 0, a - 2, 3, 0, o + 2, WOOD)
    b.fill(-3, -1, a, 3, -1, o, "spruce_planks")
    b.fill(-4, 1, a - 2, -4, 1, o + 2, FENCE)
    b.fill(4, 1, a - 2, 4, 1, o + 2, FENCE)
    for x in (-4, 4):
        for z in (a - 2, o + 2):
            b.fill(x, 1, z, x, 2, z, BEAM)
            b.lantern(x, 3, z)


# --------------------------------------------------------------------------
# Curtain walls
# --------------------------------------------------------------------------
SIDES = [  # (name, outward axis, sign, inward facing)
    ("north", "z", -1, "south"), ("south", "z", 1, "north"),
    ("west", "x", -1, "east"), ("east", "x", 1, "west"),
]


def wall_positions(name):
    for i in range(-16, 17):
        if name == "south" and abs(i) <= 11:
            continue        # gatehouse and gate towers
        yield i


def curtain_walls(b: Builder, rng: random.Random):
    for (x1, z1, x2, z2) in [(-R_OUT, -R_OUT, R_OUT, -R_IN), (-R_OUT, R_IN, R_OUT, R_OUT),
                             (-R_OUT, -R_OUT, -R_IN, R_OUT), (R_IN, -R_OUT, R_OUT, R_OUT)]:
        b.fill(x1, 0, z1, x2, WALL_TOP, z2, WALL)
    # stone texture: mossy and cobbled near the ground, cracked higher up
    for name, axis, sign, facing in SIDES:
        for i in wall_positions(name):
            for y in range(1, WALL_TOP + 1):
                x, z = (i, sign * R_OUT) if axis == "z" else (sign * R_OUT, i)
                roll = rng.random()
                if y <= 3 and roll < 0.45:
                    b.setblock(x, y, z, rng.choice(["mossy_stone_bricks", "mossy_cobblestone", "cobblestone", "andesite"]))
                elif y <= 7 and roll < 0.2:
                    b.setblock(x, y, z, rng.choice(["cracked_stone_bricks", "mossy_stone_bricks", "tuff_bricks"]))
                elif roll < 0.1:
                    b.setblock(x, y, z, "cracked_stone_bricks")
    # plinth, buttresses, corbels and the overhanging battlements
    o = R_OUT + 1
    for name, axis, sign, facing in SIDES:
        for i in wall_positions(name):
            P = (lambda y, i=i: (i, y, sign * o)) if axis == "z" else (lambda y, i=i: (sign * o, y, i))
            x, _, z = P(0)
            b.setblock(x, 0, z, WALL)
            if i % 6 == 0:
                b.fill(x, 1, z, x, 7, z, WALL)
                b.stairs(x, 8, z, facing)
            else:
                b.stairs(x, 1, z, facing)
            b.stairs(x, 9, z, facing, upside_down=True)
            b.fill(x, WALL_TOP, z, x, WALL_TOP + 1, z, WALL)
            if i % 2 == 0:
                b.setblock(x, WALL_TOP + 2, z, WALL)
            if i % 8 == 4:
                b.lantern(x, WALL_TOP + 3, z)
            # inner rail
            ix, iz = (i, sign * R_IN) if axis == "z" else (sign * R_IN, i)
            b.setblock(ix, WALL_TOP + 1, iz, FENCE)


# --------------------------------------------------------------------------
# Round corner towers with spiral stairs and pointed roofs
# --------------------------------------------------------------------------
RING = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
STEP_FACING = {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}
TOWER_R, TOWER_IN = 5.5, 3.6
TOWER_TOP = 20


def spiral(b: Builder, cx, cz, top):
    for y in range(1, top + 1):
        i = (y - 1) % 8
        px, pz = RING[i - 1]
        x, z = RING[i]
        b.stairs(cx + x, y, cz + z, STEP_FACING[(x - px, z - pz)], WOOD_STAIR)


def corner_tower(b: Builder, cx, cz, rng: random.Random):
    sx, sz = -int(math.copysign(1, cx)), -int(math.copysign(1, cz))   # towards the courtyard
    S = lambda a, c: (cx + sx * a, cz + sz * c)  # noqa: E731
    b.disc(cx, cz, TOWER_R, 0, TOWER_TOP, WALL)
    b.disc(cx, cz, TOWER_R, WALL_TOP + 1, WALL_TOP + 1, TRIM)
    b.disc(cx, cz, TOWER_R, TOWER_TOP, TOWER_TOP, DARK)
    outer = [c for c in disc_cells(TOWER_R) if c[0] ** 2 + c[1] ** 2 > 4.6 ** 2]
    for _ in range(40):
        dx, dz = rng.choice(outer)
        y = rng.randint(1, TOWER_TOP - 1)
        if y != WALL_TOP + 1:
            b.setblock(cx + dx, y, cz + dz, rng.choice(["mossy_stone_bricks", "cracked_stone_bricks", "tuff_bricks"]))
    b.disc(cx, cz, TOWER_IN, 1, TOWER_TOP - 1, AIR)
    b.disc(cx, cz, TOWER_IN, 0, 0, WOOD)
    for fy in (WALL_TOP, 16):
        b.disc(cx, cz, TOWER_IN, fy, fy, "spruce_planks")
        for (x, z) in RING:
            b.setblock(cx + x, fy, cz + z, AIR)
    b.fill(cx, 1, cz, cx, TOWER_TOP - 1, cz, BEAM)
    spiral(b, cx, cz, 16)
    # doors: courtyard (ground) and both wall walks
    for (a, c) in [(3, 2), (2, 3), (3, 3), (4, 3), (3, 4)]:
        x, z = S(a, c)
        b.fill(x, 1, z, x, 3, z, AIR)
    for (a, c) in [(4, 1), (5, 1), (1, 4), (1, 5)]:
        x, z = S(a, c)
        b.fill(x, WALL_TOP + 1, z, x, WALL_TOP + 2, z, AIR)
    # arrow slits facing outwards
    for (a, c) in [(-4, 0), (0, -4)]:
        for y in (4, 12, 17):
            x, z = S(a, c)
            x2, z2 = S(int(a * 1.25), int(c * 1.25))
            b.fill(x, y, z, x, y + 1, z, AIR)
            b.fill(x2, y, z2, x2, y + 1, z2, "glass_pane")
    # lights
    for (y, a, c) in [(WALL_TOP - 1, -2, -2), (15, 2, -2), (TOWER_TOP - 1, -2, 2)]:
        x, z = S(a, c)
        b.lantern(x, y, z, hanging=True)
    # roof and spire
    top = cone(b, cx, cz, TOWER_TOP + 1, 6.6, 0.55)
    flag(b, cx, top, cz, direction=(sx, 0))


# --------------------------------------------------------------------------
# Gatehouse
# --------------------------------------------------------------------------
GATE_TOWER_R = 3.5


def machicolated_ring(b: Builder, cx, cz, r, y_corbel):
    ring = [c for c in disc_cells(r + 1) if c not in set(disc_cells(r))]
    for (dx, dz) in ring:
        f = toward_center(dx, dz)
        if f:
            b.stairs(cx + dx, y_corbel, cz + dz, f, upside_down=True)
        else:
            b.setblock(cx + dx, y_corbel, cz + dz, TRIM)
    b.disc(cx, cz, r + 1, y_corbel + 1, y_corbel + 1, WALL)
    for (dx, dz) in ring:
        b.setblock(cx + dx, y_corbel + 2, cz + dz, WALL)
        if (dx + dz) % 2 == 0:
            b.setblock(cx + dx, y_corbel + 3, cz + dz, WALL)


def gate_tower(b: Builder, cx, cz):
    sgn = 1 if cx > 0 else -1
    b.disc(cx, cz, GATE_TOWER_R, 0, 15, WALL)
    b.disc(cx, cz, GATE_TOWER_R, WALL_TOP + 1, WALL_TOP + 1, TRIM)
    for (dx, dz) in [(-3, 0), (3, 0), (0, 3), (2, 2), (-2, 2)]:
        b.setblock(cx + dx, 3, cz + dz, "mossy_stone_bricks")
    machicolated_ring(b, cx, cz, GATE_TOWER_R, 15)
    b.disc(cx, cz, 2.2, WALL_TOP + 1, 13, AIR)
    b.fill(cx + 3 * sgn, WALL_TOP + 1, cz, cx + 3 * sgn, WALL_TOP + 2, cz, AIR)
    b.fill(cx - 3 * sgn, WALL_TOP + 1, cz, cx - 3 * sgn, WALL_TOP + 2, cz, AIR)
    b.fill(cx, 12, cz + 3, cx, 13, cz + 3, "glass_pane")
    b.fill(cx, 5, cz + 3, cx, 6, cz + 3, "iron_bars")
    b.lantern(cx, 13, cz, hanging=True)
    b.lantern(cx + sgn * 2, 17, cz - 2)
    flag(b, cx, 17, cz, color="blue_wool", accent="white_wool", direction=(sgn, 0))


def gatehouse(b: Builder):
    gate_tower(b, -7, 22)
    gate_tower(b, 7, 22)
    b.fill(-4, 0, 19, 4, 14, 24, WALL)
    # tunnel with a rounded arch
    b.fill(-3, 1, 19, 3, 6, 24, AIR)
    b.fill(-2, 7, 19, 2, 7, 24, AIR)
    b.fill(-1, 8, 19, 1, 8, 24, AIR)
    b.fill(-3, 0, 19, 3, 0, 28, "cobblestone")
    for z in (19, 24):
        for x in (-4, 4):
            b.fill(x, 1, z, x, 6, z, TRIM)
        for (x, y) in [(-3, 7), (3, 7), (-2, 8), (2, 8), (-1, 9), (0, 9), (1, 9)]:
            b.setblock(x, y, z, TRIM)
    b.setblock(0, 9, 24, "chiseled_stone_bricks")
    # portcullis (raised) and lanterns in the passage
    b.fill(-2, 7, 22, 2, 7, 22, "iron_bars")
    b.fill(-1, 8, 22, 1, 8, 22, "iron_bars")
    for x in (-3, 3):
        b.lantern(x, 6, 20, hanging=True)
        b.lantern(x, 6, 23, hanging=True)
    # guard room above the gate (the wall-walk passes through it)
    b.fill(-3, WALL_TOP + 1, 20, 3, 13, 23, AIR)
    b.fill(-3, WALL_TOP, 20, 3, WALL_TOP, 23, "spruce_planks")
    for x in (-2, 2):
        b.fill(x, 11, 24, x, 12, 24, "glass_pane")
        b.fill(x, 11, 19, x, 12, 19, "glass_pane")
    b.lantern(0, 13, 21, hanging=True)
    # banners on the front
    for x in (-3, 3):
        b.fill(x, 9, 24, x, 12, 24, "red_wool")
        b.setblock(x, 11, 24, "yellow_wool")
    # machicolations over the gate
    for x in range(-4, 5):
        b.stairs(x, 13, 25, "north", upside_down=True)
        b.fill(x, 14, 25, x, 15, 25, WALL)
        if x % 2 == 0:
            b.setblock(x, 16, 25, WALL)
    for x in range(-4, 5):
        if x % 2 == 0:
            b.setblock(x, 15, 19, WALL)
    for z in range(19, 25):
        if z % 2 == 1:
            b.setblock(-4, 15, z, WALL)
            b.setblock(4, 15, z, WALL)


# --------------------------------------------------------------------------
# Keep
# --------------------------------------------------------------------------
KX, KZ1, KZ2 = 10, -19, -5
KTOP = 20
TURRETS = [(-KX, KZ1), (KX, KZ1), (-KX, KZ2), (KX, KZ2)]


def in_turret(x, z):
    return any((x - tx) ** 2 + (z - tz) ** 2 <= 2.5 ** 2 for tx, tz in TURRETS)


def keep_exterior(b: Builder, rng: random.Random):
    for (tx, tz) in TURRETS:
        b.disc(tx, tz, 2.5, 0, 24, WALL)
        for y in (8, 14):
            b.disc(tx, tz, 2.5, y, y, TRIM)
        b.disc(tx, tz, 2.5, 24, 24, DARK)
    b.fill(-KX, 0, KZ1, KX, KTOP, KZ2, WALL, mode="hollow")
    for y in (8, 14):
        for (x1, z1, x2, z2) in [(-KX, KZ1, KX, KZ1), (-KX, KZ2, KX, KZ2), (-KX, KZ1, -KX, KZ2), (KX, KZ1, KX, KZ2)]:
            b.fill(x1, y, z1, x2, y, z2, TRIM)
    # weathering low on the walls
    for _ in range(90):
        side = rng.randint(0, 3)
        y = rng.randint(1, 7)
        if side < 2:
            x, z = rng.randint(-KX + 3, KX - 3), (KZ1, KZ2)[side]
        else:
            x, z = (-KX, KX)[side - 2], rng.randint(KZ1 + 3, KZ2 - 3)
        b.setblock(x, y, z, rng.choice(["mossy_stone_bricks", "cracked_stone_bricks", "mossy_cobblestone"]))
    # plinth
    for x in range(-KX - 1, KX + 2):
        for (z, f) in [(KZ1 - 1, "south"), (KZ2 + 1, "north")]:
            if abs(x) <= 3 and z == KZ2 + 1:
                continue
            if not in_turret(x, z):
                b.stairs(x, 1, z, f)
    for z in range(KZ1, KZ2 + 1):
        for (x, f) in [(-KX - 1, "east"), (KX + 1, "west")]:
            if not in_turret(x, z):
                b.stairs(x, 1, z, f)
    # machicolated parapet around the roof
    ring = [(x, KZ1 - 1, "south") for x in range(-KX - 1, KX + 2)] + \
           [(x, KZ2 + 1, "north") for x in range(-KX - 1, KX + 2)] + \
           [(-KX - 1, z, "east") for z in range(KZ1, KZ2 + 1)] + [(KX + 1, z, "west") for z in range(KZ1, KZ2 + 1)]
    for (x, z, f) in ring:
        if in_turret(x, z):
            continue
        b.stairs(x, KTOP - 1, z, f, upside_down=True)
        b.fill(x, KTOP, z, x, KTOP + 1, z, WALL)
        if (x + z) % 2 == 0:
            b.setblock(x, KTOP + 2, z, WALL)
    # windows (tall in the great hall) with trim lintels
    windows = [(x, KZ2) for x in (-7, -4, 4, 7)] + [(x, KZ1) for x in (-8, -5, 5, 8)] + \
              [(-KX, z) for z in (-16, -12, -8)] + [(KX, z) for z in (-16, -8)]
    for (x, z) in windows:
        for (y1, y2) in [(2, 5), (10, 12), (16, 18)]:
            b.fill(x, y1, z, x, y2, z, "glass_pane")
            b.setblock(x, y2 + 1, z, TRIM)
    # banners on the back wall
    for x in (-2, 2):
        b.fill(x, 3, KZ1, x, 6, KZ1, "red_wool")
        b.setblock(x, 5, KZ1, "yellow_wool")
    # front door with a trimmed arch, lantern posts
    b.fill(-1, 1, KZ2, 1, 4, KZ2, AIR)
    b.setblock(0, 5, KZ2, AIR)
    for (x, y) in [(-2, 1), (-2, 2), (-2, 3), (-2, 4), (2, 1), (2, 2), (2, 3), (2, 4), (-1, 5), (1, 5), (0, 6)]:
        b.setblock(x, y, KZ2, TRIM)
    b.post(-3, KZ2 + 1)
    b.post(3, KZ2 + 1)
    # turret roofs
    for (tx, tz) in TURRETS:
        top = cone(b, tx, tz, 25, 3.6, 0.6)
        b.fill(tx, top, tz, tx, top + 1, tz, FENCE)
        b.setblock(tx, top + 2, tz, "lightning_rod")


def keep_interior(b: Builder):
    b.fill(-KX + 1, 0, KZ1 + 1, KX - 1, 0, KZ2 - 1, WOOD)
    b.fill(-KX + 1, 8, KZ1 + 1, KX - 1, 8, KZ2 - 1, "spruce_planks")
    b.fill(-KX + 1, 14, KZ1 + 1, KX - 1, 14, KZ2 - 1, "spruce_planks")
    # stairs: ground -> 8 (west), 8 -> 14 (east), 14 -> roof (west); two wide
    for k in range(8):
        for x in (-9, -8):
            b.stairs(x, 1 + k, -6 - k, "north", WOOD_STAIR)
    b.fill(-9, 8, -12, -8, 8, -6, AIR)
    for k in range(6):
        for x in (8, 9):
            b.stairs(x, 9 + k, -6 - k, "north", WOOD_STAIR)
    b.fill(8, 14, -10, 9, 14, -6, AIR)
    for k in range(6):
        for x in (-9, -8):
            b.stairs(x, 15 + k, -6 - k, "north", WOOD_STAIR)
    b.fill(-9, KTOP, -10, -8, KTOP, -6, AIR)
    b.fill(-7, KTOP + 1, -10, -7, KTOP + 1, -6, FENCE)
    # great hall: pillars, carpet, dais, fireplace, chandeliers
    for x in (-5, 5):
        for z in (-16, -12, -8):
            b.fill(x, 1, z, x, 7, z, BEAM)
    b.fill(-1, 1, -14, 1, 1, KZ2 + 1, "red_carpet")
    b.fill(-4, 1, KZ1 + 1, 4, 1, -16, WOOD)
    for x in range(-4, 5):
        b.stairs(x, 1, -15, "north", WOOD_STAIR)
    b.fill(-1, 2, KZ1 + 1, 1, 2, -16, "red_carpet")
    b.fill(8, 1, -14, 9, 7, -10, "polished_blackstone_bricks")
    b.fill(8, 1, -13, 8, 2, -11, AIR)
    b.setblock(9, 1, -12, "campfire", {"minecraft:cardinal_direction": "west", "extinguished": False})
    for z in (-14, -9):
        for (dx, dz) in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
            b.setblock(dx, 7, z + dz, FENCE)
            b.lantern(dx, 6, z + dz, hanging=True)
    # upper floors: a few lights and storage, otherwise empty for decorating
    for (x, z) in [(-4, -15), (4, -15), (-4, -9), (4, -9)]:
        b.lantern(x, 13, z, hanging=True)
        b.lantern(x, 19, z, hanging=True)
    for x in (-6, 6):
        b.setblock(x, 9, KZ1 + 1, "chest", {"minecraft:cardinal_direction": "south"})
    b.setblock(-6, 1, KZ2 - 1, "crafting_table")
    b.setblock(6, 1, KZ2 - 1, "barrel", {"facing_direction": 1, "open_bit": False})
    # roof: dragon landing pad and a hay nest
    b.fill(-5, KTOP, -16, 5, KTOP, -8, "smooth_stone")
    for (x1, z1, x2, z2) in [(-5, -16, 5, -16), (-5, -8, 5, -8), (-5, -16, -5, -8), (5, -16, 5, -8)]:
        b.fill(x1, KTOP, z1, x2, KTOP, z2, "polished_deepslate")
    b.fill(-1, KTOP, -13, 1, KTOP, -11, "polished_deepslate")
    b.fill(6, KTOP + 1, -17, 8, KTOP + 1, -16, "hay_block")
    b.setblock(7, KTOP + 2, -17, "hay_block")


# --------------------------------------------------------------------------
# Courtyard
# --------------------------------------------------------------------------
PATH_MIX = ["stone_bricks", "cobblestone", "andesite", "mossy_cobblestone", "gravel", "polished_andesite"]


def path(b: Builder, rng, x1, z1, x2, z2):
    b.fill(x1, 0, z1, x2, 0, z2, "stone_bricks")
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for z in range(min(z1, z2), max(z1, z2) + 1):
            if rng.random() < 0.45:
                b.setblock(x, 0, z, rng.choice(PATH_MIX))


def courtyard(b: Builder, rng: random.Random):
    path(b, rng, -1, KZ2 + 1, 1, R_IN - 1)
    path(b, rng, -15, 5, 15, 6)
    for z in (2, 10, 17):
        for x in (-3, 3):
            b.post(x, z)
    for (x, z) in [(-15, -2), (-15, 14), (15, 14), (-17, -16), (15, -18), (-8, 17)]:
        b.post(x, z)
    # roofed well (west)
    wx, wz = -12, 9
    b.fill(wx - 2, 0, wz - 2, wx + 2, 1, wz + 2, "cobblestone")
    b.fill(wx - 2, 1, wz - 2, wx + 2, 1, wz + 2, "mossy_cobblestone", mode="outline")
    b.fill(wx - 1, -3, wz - 1, wx + 1, 1, wz + 1, "water")
    for (dx, dz) in [(-2, -2), (-2, 2), (2, -2), (2, 2)]:
        b.fill(wx + dx, 2, wz + dz, wx + dx, 3, wz + dz, FENCE)
    b.fill(wx - 2, 4, wz - 2, wx + 2, 4, wz + 2, WOOD)
    for i in range(-2, 3):
        b.stairs(wx + i, 4, wz - 2, "south", WOOD_STAIR)
        b.stairs(wx + i, 4, wz + 2, "north", WOOD_STAIR)
    b.fill(wx - 1, 5, wz - 1, wx + 1, 5, wz + 1, WOOD)
    for i in range(-1, 2):
        b.stairs(wx + i, 5, wz - 1, "south", WOOD_STAIR)
        b.stairs(wx + i, 5, wz + 1, "north", WOOD_STAIR)
    b.setblock(wx, 6, wz, WOOD_STAIR.replace("stairs", "slab"), {"minecraft:vertical_half": "bottom"})
    b.lantern(wx, 3, wz, hanging=True)
    # flower garden behind the keep and along the west wall
    flowers = ["poppy", "dandelion", "cornflower", "oxeye_daisy"]
    for _ in range(70):
        x = rng.randint(-19, -12)
        z = rng.randint(-18, 3)
        if b.get(x, 1, z) in ("", AIR) and b.get(x, 0, z) == "grass_block":
            if rng.random() < 0.25:
                b.setblock(x, 1, z, "oak_leaves", {"persistent_bit": True, "update_bit": False})
            else:
                b.setblock(x, 1, z, rng.choice(flowers))
    for _ in range(25):
        x = rng.randint(-18, 10)
        z = rng.randint(12, 18)
        if abs(x) > 4 and b.get(x, 1, z) in ("", AIR) and b.get(x, 0, z) == "grass_block":
            b.setblock(x, 1, z, rng.choice(flowers))


def stables(b: Builder):
    """Lean-to stable along the east wall, tall enough for a brachiosaurus."""
    x1, x2, z1, z2 = 12, 19, -16, 8
    b.fill(x1, 0, z1, x2, 0, z2, "coarse_dirt")
    for (xa, xb, y) in [(18, 19, 9), (16, 17, 8), (14, 15, 7), (12, 13, 6)]:
        b.fill(xa, y, z1 - 1, xb, y, z2 + 1, WOOD_STAIR, {"weirdo_direction": STAIR_DIR["east"], "upside_down_bit": False})
        b.fill(xb, y, z1 - 1, xb, y, z2 + 1, WOOD)
        b.fill(xa, y - 1, z1 - 1, xb, y - 1, z2 + 1, "spruce_planks")
    for z in range(z1, z2 + 1, 6):
        b.fill(x1, 1, z, x1, 4, z, BEAM)
    b.fill(x1, 1, z2, x1, 4, z2, BEAM)
    for z in (-10, -4, 2):
        b.fill(x1 + 3, 1, z, x2, 1, z, FENCE)
    for z in (-14, -8, -2, 4):
        b.fill(x2, 1, z, x2, 2, z, "hay_block")
        b.setblock(x2 - 1, 1, z, "hay_block")
        b.lantern(16, 6, z, hanging=True)


def build():
    rng = random.Random(7)
    b = Builder()
    parts = []

    def part(fn, *args):
        start = len(b.cmds)
        fn(b, *args)
        return b.cmds[start:]

    parts.append(part(site))
    parts.append(part(curtain_walls, rng))
    parts.append(part(corner_tower, -22, -22, rng) + part(corner_tower, 22, -22, rng))
    parts.append(part(corner_tower, -22, 22, rng) + part(corner_tower, 22, 22, rng))
    parts.append(part(gatehouse))
    parts.append(part(keep_exterior, rng))
    parts.append(part(keep_interior))
    parts.append(part(courtyard, rng) + part(stables))
    return b, parts


# --------------------------------------------------------------------------
# Preview
# --------------------------------------------------------------------------
COLORS = {
    "stone": (125, 125, 125), "grass_block": (98, 150, 60), "stone_bricks": (124, 123, 124),
    "mossy_stone_bricks": (104, 122, 90), "cracked_stone_bricks": (112, 110, 110),
    "chiseled_stone_bricks": (138, 137, 138), "mossy_cobblestone": (100, 116, 92), "cobblestone": (112, 112, 112),
    "andesite": (136, 136, 137), "polished_andesite": (156, 160, 158), "tuff_bricks": (98, 102, 96),
    "deepslate_bricks": (70, 70, 72), "deepslate_tiles": (52, 52, 56), "deepslate_tile_stairs": (58, 58, 62),
    "stone_brick_stairs": (120, 119, 120), "spruce_planks": (114, 84, 48), "dark_oak_planks": (66, 43, 20),
    "dark_oak_stairs": (72, 47, 23), "stripped_dark_oak_log": (96, 76, 49), "dark_oak_fence": (66, 43, 20),
    "lantern": (245, 200, 90), "glass_pane": (175, 210, 225), "iron_bars": (150, 150, 155),
    "red_carpet": (160, 39, 34), "red_wool": (170, 40, 35), "yellow_wool": (240, 190, 40),
    "blue_wool": (52, 60, 160), "white_wool": (235, 235, 235), "smooth_stone": (158, 158, 158),
    "polished_deepslate": (72, 72, 74), "water": (60, 90, 200), "hay_block": (200, 170, 40),
    "chest": (160, 110, 40), "crafting_table": (130, 90, 55), "barrel": (120, 85, 50), "gravel": (130, 124, 120),
    "coarse_dirt": (119, 85, 59), "polished_blackstone_bricks": (48, 42, 50), "campfire": (230, 120, 40),
    "lightning_rod": (200, 120, 80), "poppy": (200, 30, 30), "dandelion": (240, 220, 40),
    "cornflower": (70, 100, 220), "oxeye_daisy": (230, 230, 220), "oak_leaves": (60, 120, 40),
    "dark_oak_slab": (66, 43, 20),
}


def render(b: Builder, path_out, cut_y=None, scale=5):
    g = b.grid
    nx, ny, nz = g.shape
    tile = scale
    W = (nx + nz) * tile + 40
    H = (nx + nz) * tile // 2 + ny * tile + 40
    img = Image.new("RGBA", (W, H), (150, 190, 230, 255))
    d = ImageDraw.Draw(img)
    ox, oy = nz * tile + 20, ny * tile + 20
    for s in range(nx + nz - 1):
        for gy in range(ny):
            y = gy + Y_MIN
            if cut_y is not None and y > cut_y:
                continue
            for gx in range(max(0, s - nz + 1), min(nx, s + 1)):
                gz = s - gx
                blk = g[gx, gy, gz]
                if not blk or blk == AIR:
                    continue
                c = COLORS.get(blk, (255, 0, 255))
                px = ox + (gx - gz) * tile
                py = oy + (gx + gz) * tile // 2 - gy * tile
                top = [(px, py - tile // 2), (px + tile, py), (px, py + tile // 2), (px - tile, py)]
                left = [(px - tile, py), (px, py + tile // 2), (px, py + tile // 2 + tile), (px - tile, py + tile)]
                right = [(px + tile, py), (px, py + tile // 2), (px, py + tile // 2 + tile), (px + tile, py + tile)]
                d.polygon(top, fill=c)
                d.polygon(left, fill=tuple(int(v * 0.72) for v in c))
                d.polygon(right, fill=tuple(int(v * 0.86) for v in c))
    # crop empty sky
    bbox = Image.eval(img.convert("L"), lambda v: 255 if v != 177 else 0).getbbox()
    if bbox:
        img = img.crop((max(0, bbox[0] - 10), max(0, bbox[1] - 10), min(W, bbox[2] + 10), min(H, bbox[3] + 10)))
    img.save(path_out)


if __name__ == "__main__":
    import sys
    b, parts = build()
    print("commands:", len(b.cmds), [len(p) for p in parts])
    out = sys.argv[1] if len(sys.argv) > 1 else "castle.png"
    render(b, out)
    render(b, out.replace(".png", "_cut.png"), cut_y=4)
