"""Spawn castle generator.

Produces Bedrock `/fill` and `/setblock` commands (relative to the castle
centre at ground level, gate facing south) and keeps a voxel model of the
result so a preview image can be rendered.

Layout (top view, north is up):

        T============T          T  corner towers (9x9, 4 storeys, roof deck)
        |   KEEP     |          =  curtain walls 3 thick, 10 high, wall-walk
        |  (3 floors)|  stable  K  keep: great hall + 2 upper floors + roof
        | well       |          G  gatehouse with two guard towers
        T====G=G=====T
"""
from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageDraw

AIR = "air"

# x/z extent of everything the castle touches (inclusive)
EXTENT = 28
Y_MIN, Y_MAX = -10, 46


class Builder:
    def __init__(self):
        n = 2 * EXTENT + 1
        self.grid = np.full((n, Y_MAX - Y_MIN + 1, n), "", dtype=object)
        self.cmds: list[str] = []

    # -- primitives -------------------------------------------------------
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


# Bedrock stairs: weirdo_direction 0=east 1=west 2=south 3=north (side you climb towards)
STAIR_DIR = {"east": 0, "west": 1, "south": 2, "north": 3}
MIRROR_X = {"east": "west", "west": "east", "north": "north", "south": "south"}
MIRROR_Z = {"north": "south", "south": "north", "east": "east", "west": "west"}


def stairs(b: Builder, x, y, z, facing, block="spruce_stairs"):
    b.setblock(x, y, z, block, {"weirdo_direction": STAIR_DIR[facing], "upside_down_bit": False})


def lantern(b: Builder, x, y, z, hanging=False):
    b.setblock(x, y, z, "lantern", {"hanging": hanging})


# --------------------------------------------------------------------------
# Parts
# --------------------------------------------------------------------------
WALL = "stone_bricks"
R_OUT = 22      # outer face of curtain wall
R_IN = 20       # inner face of curtain wall
WALL_TOP = 10   # top block of curtain wall (wall-walk at y=11)


def site(b: Builder):
    e = EXTENT
    # foundation (stone plinth) and ground layer
    b.fill(-e, -8, -e, e, -1, e, "stone")
    b.fill(-e, 0, -e, e, 0, e, "grass_block")
    # clear everything above the ground in chunks below the 32768 fill limit
    y = 1
    while y <= 44:
        b.fill(-e, y, -e, e, min(y + 9, 44), e, AIR)
        y += 10


def curtain_walls(b: Builder):
    for (x1, z1, x2, z2) in [(-R_OUT, -R_OUT, R_OUT, -R_IN), (-R_OUT, R_IN, R_OUT, R_OUT),
                             (-R_OUT, -R_OUT, -R_IN, R_OUT), (R_IN, -R_OUT, R_OUT, R_OUT)]:
        b.fill(x1, 0, z1, x2, WALL_TOP, z2, WALL)
    # wall-walk surface and battlements
    for i in range(-R_OUT, R_OUT + 1):
        if i % 2 == 0:
            for (x, z) in [(i, -R_OUT), (i, R_OUT), (-R_OUT, i), (R_OUT, i)]:
                b.setblock(x, WALL_TOP + 1, z, WALL)
    # inner safety rail
    b.fill(-R_IN, WALL_TOP + 1, -R_IN, R_IN, WALL_TOP + 1, -R_IN, "spruce_fence")
    b.fill(-R_IN, WALL_TOP + 1, R_IN, R_IN, WALL_TOP + 1, R_IN, "spruce_fence")
    b.fill(-R_IN, WALL_TOP + 1, -R_IN, -R_IN, WALL_TOP + 1, R_IN, "spruce_fence")
    b.fill(R_IN, WALL_TOP + 1, -R_IN, R_IN, WALL_TOP + 1, R_IN, "spruce_fence")
    # lanterns on the battlements
    for i in range(-16, 17, 8):
        for (x, z) in [(i, -R_OUT), (i, R_OUT), (-R_OUT, i), (R_OUT, i)]:
            lantern(b, x, WALL_TOP + 2, z)


def corner_tower(b: Builder, sx: int, sz: int):
    """Corner tower; built in the north-west frame and mirrored by (sx, sz)."""
    T = lambda x, z: (sx * x, sz * z)

    def F(x1, y1, z1, x2, y2, z2, block, states=None, mode=None):
        a = T(x1, z1)
        c = T(x2, z2)
        b.fill(a[0], y1, a[1], c[0], y2, c[1], block, states, mode)

    def S(x, y, z, block, states=None):
        p = T(x, z)
        b.setblock(p[0], y, p[1], block, states)

    def stair(x, y, z, facing):
        f = facing
        if sx < 0:
            pass
        if sx > 0:
            f = MIRROR_X[f]
        if sz > 0:
            f = MIRROR_Z[f]
        p = T(x, z)
        stairs(b, p[0], y, p[1], f)

    # shell: x,z in -25..-17, y 0..16 (floor at y=0, roof at y=16)
    F(-25, 0, -25, -17, 16, -17, WALL, mode="hollow")
    F(-24, 0, -24, -18, 0, -18, "spruce_planks")
    # chiseled corner trim
    for (x, z) in [(-25, -25), (-25, -17), (-17, -25), (-17, -17)]:
        F(x, 1, z, x, 16, z, "chiseled_stone_bricks")
    # floors
    for fy in (5, 10):
        F(-24, fy, -24, -18, fy, -18, "spruce_planks")
    # stair runs (north frame): run 1 x=-24 going north, run 2 x=-18 going south, run 3 x=-24 north
    for k in range(5):
        stair(-24, 1 + k, -18 - k, "north")
    F(-24, 5, -21, -24, 5, -18, AIR)        # head room through floor 5
    for k in range(5):
        stair(-18, 6 + k, -23 + k, "south")
    F(-18, 10, -23, -18, 10, -20, AIR)      # head room through floor 10
    for k in range(6):
        stair(-24, 11 + k, -18 - k, "north")
    F(-24, 16, -22, -24, 16, -18, AIR)      # roof hatch
    # doors: courtyard (east face, ground) and wall-walk (east + south faces)
    F(-17, 1, -18, -17, 3, -18, AIR)
    F(-17, 11, -21, -17, 12, -21, AIR)
    F(-21, 11, -17, -21, 12, -17, AIR)
    # arrow-slit windows
    for y in (2, 7, 12):
        S(-25, y, -21, "glass_pane")
        S(-25, y + 1, -21, "glass_pane")
        S(-21, y, -25, "glass_pane")
        S(-21, y + 1, -25, "glass_pane")
    # battlements on the roof
    for i in range(-25, -16):
        if i % 2 == 1:
            S(i, 17, -25, WALL)
            S(i, 17, -17, WALL)
            S(-25, 17, i, WALL)
            S(-17, 17, i, WALL)
    # lights
    lantern_pos = [(-21, 4, -21), (-21, 9, -21), (-21, 15, -21)]
    for (x, y, z) in lantern_pos:
        p = T(x, z)
        lantern(b, p[0], y, p[1], hanging=True)
    p = T(-19, -19)
    lantern(b, p[0], 17, p[1])
    # flag pole
    F(-21, 17, -21, -21, 21, -21, "spruce_fence")
    F(-22, 20, -21, -24, 21, -21, "red_wool")


def gatehouse(b: Builder):
    # gate opening through the south wall
    b.fill(-3, 1, R_IN, 3, 6, R_OUT, AIR)
    b.fill(-2, 7, R_IN, 2, 7, R_OUT, AIR)
    b.fill(-3, 8, R_OUT, 3, 8, R_OUT, "chiseled_stone_bricks")
    b.fill(-4, 0, R_IN - 1, 4, 0, R_OUT + 3, "stone_bricks")
    # guard towers either side of the gate
    for sx in (-1, 1):
        x1, x2 = sx * 4, sx * 8
        b.fill(x1, 0, 19, x2, 14, 25, WALL, mode="hollow")
        b.fill(x1, 0, 19, x1, 14, 19, "chiseled_stone_bricks")
        b.fill(x2, 0, 19, x2, 14, 19, "chiseled_stone_bricks")
        b.fill(x1, 0, 25, x1, 14, 25, "chiseled_stone_bricks")
        b.fill(x2, 0, 25, x2, 14, 25, "chiseled_stone_bricks")
        b.fill(x1 + sx, WALL_TOP, 20, x2 - sx, WALL_TOP, 24, "spruce_planks")
        # doors from the wall walk
        b.fill(x1, 11, 21, x1, 12, 21, AIR)
        b.fill(x2, 11, 21, x2, 12, 21, AIR)
        # windows
        for y in (5, 12):
            b.setblock(sx * 6, y, 25, "iron_bars")
            b.setblock(sx * 6, y + 1, 25, "iron_bars")
        lantern(b, sx * 6, 13, 22, hanging=True)
        for i in range(min(x1, x2), max(x1, x2) + 1):
            if i % 2 == 0:
                b.setblock(i, 15, 19, WALL)
                b.setblock(i, 15, 25, WALL)
        for z in range(19, 26):
            if z % 2 == 1:
                b.setblock(x1, 15, z, WALL)
                b.setblock(x2, 15, z, WALL)
        lantern(b, sx * 6, 15, 22)
    # portcullis hint (decorative bars at the top of the arch, out of the way)
    b.fill(-2, 7, R_OUT, 2, 7, R_OUT, "iron_bars")


KEEP_X = 9
KEEP_Z1, KEEP_Z2 = -18, -4


def keep(b: Builder):
    x, z1, z2 = KEEP_X, KEEP_Z1, KEEP_Z2
    b.fill(-x, 0, z1, x, 18, z2, WALL, mode="hollow")
    # corner pillars rising above the roof
    for cx in (-x, x):
        for cz in (z1, z2):
            b.fill(cx, 0, cz, cx, 21, cz, "chiseled_stone_bricks")
            lantern(b, cx, 22, cz)
    # floors
    b.fill(-x + 1, 0, z1 + 1, x - 1, 0, z2 - 1, "dark_oak_planks")
    b.fill(-x + 1, 6, z1 + 1, x - 1, 6, z2 - 1, "spruce_planks")
    b.fill(-x + 1, 12, z1 + 1, x - 1, 12, z2 - 1, "spruce_planks")
    # stairs: ground -> 6 (west), 6 -> 12 (east), 12 -> roof (west); two blocks wide
    for k in range(6):
        for sx in (-8, -7):
            stairs(b, sx, 1 + k, -6 - k, "north")
    b.fill(-8, 6, -10, -7, 6, -6, AIR)
    for k in range(6):
        for sx in (7, 8):
            stairs(b, sx, 7 + k, -6 - k, "north")
    b.fill(7, 12, -10, 8, 12, -6, AIR)
    for k in range(6):
        for sx in (-8, -7):
            stairs(b, sx, 13 + k, -6 - k, "north")
    b.fill(-8, 18, -10, -7, 18, -6, AIR)
    # front door (south face)
    b.fill(-1, 1, z2, 1, 3, z2, AIR)
    b.setblock(0, 4, z2, AIR)
    b.fill(-2, 5, z2, 2, 5, z2, "chiseled_stone_bricks")
    # windows on every floor
    for base in (2, 8, 14):
        for wx in (-5, 5):
            b.fill(wx, base, z2, wx, base + 2, z2, "glass_pane")
            b.fill(wx, base, z1, wx, base + 2, z1, "glass_pane")
        for wx in (-2, 2):
            b.fill(wx, base, z1, wx, base + 2, z1, "glass_pane")
        for wz in (-15, -11, -7):
            b.fill(-x, base, wz, -x, base + 2, wz, "glass_pane")
            b.fill(x, base, wz, x, base + 2, wz, "glass_pane")
    # great hall: pillars, carpet runner, lights
    for px in (-4, 4):
        for pz in (-14, -8):
            b.fill(px, 1, pz, px, 5, pz, "spruce_log")
    b.fill(-1, 1, z1 + 1, 1, 1, z2 - 1, "red_carpet")
    b.fill(-1, 1, -10, 1, 1, -6, "red_carpet")
    for (lx, lz) in [(0, -8), (0, -14), (-4, -11), (4, -11)]:
        lantern(b, lx, 5, lz, hanging=True)
        lantern(b, lx, 11, lz, hanging=True)
        lantern(b, lx, 17, lz, hanging=True)
    # roof: dragon landing pad and battlements
    b.fill(-4, 18, -15, 4, 18, -7, "smooth_stone")
    for (x1, z1_, x2, z2_) in [(-4, -15, 4, -15), (-4, -7, 4, -7), (-4, -15, -4, -7), (4, -15, 4, -7)]:
        b.fill(x1, 18, z1_, x2, 18, z2_, "polished_deepslate")
    b.fill(-1, 18, -12, 1, 18, -10, "polished_deepslate")
    for i in range(-x, x + 1):
        if i % 2 == 0:
            b.setblock(i, 19, z1, WALL)
            b.setblock(i, 19, z2, WALL)
    for zz in range(z1, z2 + 1):
        if zz % 2 == 0:
            b.setblock(-x, 19, zz, WALL)
            b.setblock(x, 19, zz, WALL)
    # a couple of chests so there is somewhere to put things straight away
    b.setblock(-6, 1, -17, "chest", {"minecraft:cardinal_direction": "south"})
    b.setblock(6, 1, -17, "chest", {"minecraft:cardinal_direction": "south"})
    b.setblock(-6, 1, -5, "crafting_table")


def courtyard(b: Builder):
    # stone path from gate to keep door
    b.fill(-1, 0, KEEP_Z2 + 1, 1, 0, R_IN - 1, "stone_bricks")
    b.fill(-2, 0, 0, 2, 0, 0, "stone_bricks")
    # lantern posts along the path and around the yard
    for z in (2, 9, 16):
        for x in (-3, 3):
            b.fill(x, 1, z, x, 2, z, "spruce_fence")
            lantern(b, x, 3, z)
    for (x, z) in [(-14, -1), (-14, 15), (14, 15), (-17, -14)]:
        b.fill(x, 1, z, x, 2, z, "spruce_fence")
        lantern(b, x, 3, z)
    # well (west side)
    wx, wz = -12, 8
    b.fill(wx - 2, 0, wz - 2, wx + 2, 1, wz + 2, "cobblestone")
    b.fill(wx - 1, -3, wz - 1, wx + 1, 1, wz + 1, "water")
    for (dx, dz) in [(-2, -2), (-2, 2), (2, -2), (2, 2)]:
        b.fill(wx + dx, 2, wz + dz, wx + dx, 3, wz + dz, "spruce_fence")
    b.fill(wx - 2, 4, wz - 2, wx + 2, 4, wz + 2, "spruce_planks")
    lantern(b, wx, 3, wz, hanging=True)


def stables(b: Builder):
    """Open-fronted stable along the east wall for dinosaurs."""
    x1, x2 = 11, 19
    z1, z2 = -16, 6
    b.fill(x1, 0, z1, x2, 0, z2, "spruce_planks")
    b.fill(x1, 8, z1, x2, 8, z2, "spruce_planks")
    b.fill(x1, 9, z1, x2, 9, z2, "dark_oak_planks")
    for z in range(z1, z2 + 1, 5 + 0):
        b.fill(x1, 1, z, x1, 7, z, "spruce_log")
    b.fill(x1, 1, z2, x1, 7, z2, "spruce_log")
    # stall dividers and hay
    for z in (-11, -6, -1, 4):
        b.fill(x1 + 2, 1, z, x2, 1, z, "spruce_fence")
    for z in (-14, -9, -4, 1):
        b.setblock(x2, 1, z, "hay_block")
        b.setblock(x2, 2, z, "hay_block")
        b.setblock(x2 - 1, 1, z, "hay_block")
        lantern(b, 15, 7, z, hanging=True)
    b.setblock(x2, 1, 5, "barrel")


def weathering(b: Builder, seed=7):
    """Sprinkle mossy and cracked bricks over the outside of the walls."""
    rng = random.Random(seed)
    spots = []
    for i in range(-R_OUT, R_OUT + 1):
        for y in range(1, WALL_TOP + 1):
            spots += [(i, y, -R_OUT), (i, y, R_OUT), (-R_OUT, y, i), (R_OUT, y, i)]
    rng.shuffle(spots)
    n = 0
    for (x, y, z) in spots:
        if b.get(x, y, z) != WALL:
            continue
        b.setblock(x, y, z, rng.choice(["mossy_stone_bricks", "cracked_stone_bricks", "mossy_stone_bricks"]))
        n += 1
        if n >= 260:
            break


def build():
    b = Builder()
    parts = []

    def part(fn, *args):
        start = len(b.cmds)
        fn(b, *args)
        return b.cmds[start:]

    parts.append(part(site))
    parts.append(part(curtain_walls) + part(weathering))
    tower_cmds = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            tower_cmds += part(corner_tower, sx, sz)
    parts.append(tower_cmds)
    parts.append(part(gatehouse))
    parts.append(part(keep))
    parts.append(part(courtyard) + part(stables))
    return b, parts


# --------------------------------------------------------------------------
# Preview
# --------------------------------------------------------------------------
COLORS = {
    "stone": (125, 125, 125), "grass_block": (98, 150, 60), "stone_bricks": (122, 121, 122),
    "mossy_stone_bricks": (104, 120, 92), "cracked_stone_bricks": (112, 110, 110),
    "chiseled_stone_bricks": (135, 134, 135), "spruce_planks": (114, 84, 48),
    "dark_oak_planks": (66, 43, 20), "spruce_log": (58, 37, 16), "spruce_stairs": (114, 84, 48),
    "spruce_fence": (100, 74, 42), "lantern": (245, 200, 90), "glass_pane": (175, 210, 225),
    "iron_bars": (150, 150, 155), "red_carpet": (160, 39, 34), "red_wool": (170, 40, 35),
    "smooth_stone": (158, 158, 158), "polished_deepslate": (72, 72, 74), "water": (60, 90, 200),
    "cobblestone": (110, 110, 110), "hay_block": (200, 170, 40), "chest": (160, 110, 40),
    "crafting_table": (130, 90, 55), "barrel": (120, 85, 50),
}


def render(b: Builder, path, cut_y=None, scale=6):
    g = b.grid
    nx, ny, nz = g.shape
    tile = scale
    W = (nx + nz) * tile + 40
    H = (nx + nz) * tile // 2 + ny * tile + 40
    img = Image.new("RGBA", (W, H), (150, 190, 230, 255))
    d = ImageDraw.Draw(img)
    ox, oy = nz * tile + 20, ny * tile + 20
    for s in range(nx + nz - 1):          # back to front
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
    img.save(path)


if __name__ == "__main__":
    import sys
    b, parts = build()
    print("commands:", len(b.cmds), [len(p) for p in parts])
    out = sys.argv[1] if len(sys.argv) > 1 else "castle.png"
    render(b, out)
    render(b, out.replace(".png", "_cut.png"), cut_y=4)
