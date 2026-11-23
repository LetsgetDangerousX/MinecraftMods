"""Tiny modelling toolkit for Bedrock entity geometry.

A creature is described as bones made of boxes ("cubes").  This module
packs every cube onto a box-UV texture atlas, paints that atlas
procedurally (scales, bellies, stripes, eyes, teeth ...) and writes the
Bedrock `.geo.json` plus the matching `.png` texture.

It also contains a small software renderer used to produce preview images
of the models so they can be checked without launching the game.

Coordinate conventions follow Bedrock geometry: units are pixels
(16 = one block), +Y is up and the creature faces -Z.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np
from PIL import Image


# --------------------------------------------------------------------------
# Painting
# --------------------------------------------------------------------------

def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def scale_rgb(c, f):
    return tuple(max(0, min(255, c[i] * f)) for i in range(3))


@dataclass
class Paint:
    base: str
    belly: str | None = None        # colour of the underside
    top: str | None = None          # colour of the upper face (default: darker base)
    pattern: str | None = None      # stripes | spots | scales | bands | veins | plates
    pattern_color: str | None = None
    eyes: str | None = None         # eye colour -> draws eyes on the side faces
    teeth: bool = False             # white teeth along the lower edge
    ridge: str | None = None        # stripe along the middle of the top face
    noise: float = 0.07
    belly_frac: float = 0.35        # how much of each side fades to the belly colour
    glow_tip: str | None = None     # colour the far (+Z or tip) end of the cube
    edge: str | None = None         # darker outline colour on the side faces


class Painter:
    """Paints the six box-UV faces of a cube."""

    def __init__(self, img: np.ndarray, seed: int):
        self.img = img
        self.rng = random.Random(seed)

    def put(self, x, y, c, a=255):
        h, w = self.img.shape[:2]
        if 0 <= x < w and 0 <= y < h:
            self.img[y, x, 0] = int(max(0, min(255, c[0])))
            self.img[y, x, 1] = int(max(0, min(255, c[1])))
            self.img[y, x, 2] = int(max(0, min(255, c[2])))
            self.img[y, x, 3] = a

    def paint_cube(self, u, v, size, p: Paint):
        w, h, d = size
        base = hex_rgb(p.base)
        belly = hex_rgb(p.belly) if p.belly else base
        top = hex_rgb(p.top) if p.top else scale_rgb(base, 0.85)
        pat = hex_rgb(p.pattern_color) if p.pattern_color else scale_rgb(base, 0.6)
        rng = self.rng

        def jitter(c):
            f = 1.0 + rng.uniform(-p.noise, p.noise)
            return scale_rgb(c, f)

        # face rectangles: name -> (x0, y0, fw, fh)
        faces = {
            "top": (u + d, v, w, d),
            "bottom": (u + d + w, v, w, d),
            "side_a": (u, v + d, d, h),          # front edge at high x
            "front": (u + d, v + d, w, h),
            "side_b": (u + d + w, v + d, d, h),  # front edge at low x
            "back": (u + 2 * d + w, v + d, w, h),
        }

        spot_seeds = [(rng.random(), rng.random(), rng.uniform(0.6, 1.4)) for _ in range(6)]

        for name, (x0, y0, fw, fh) in faces.items():
            for fy in range(fh):
                for fx in range(fw):
                    # vertical fraction (0 top .. 1 bottom) for side-ish faces
                    ty = (fy + 0.5) / max(fh, 1)
                    tx = (fx + 0.5) / max(fw, 1)
                    if name == "top":
                        c = top
                        if p.ridge and abs(tx - 0.5) < max(0.5 / fw, 0.18):
                            c = hex_rgb(p.ridge)
                    elif name == "bottom":
                        c = belly
                    else:
                        c = base
                        if p.belly and ty > 1 - p.belly_frac:
                            t = (ty - (1 - p.belly_frac)) / p.belly_frac
                            c = mix(base, belly, min(1.0, t * 1.6))
                        # darker towards the top edge
                        c = scale_rgb(c, 0.9 + 0.1 * ty)
                    # patterns
                    if p.pattern == "stripes" and name in ("side_a", "side_b", "top"):
                        if (fx // 2) % 3 == 0 and ty < 0.75:
                            c = mix(c, pat, 0.75)
                    elif p.pattern == "bands" and name not in ("bottom",):
                        span = fw if name in ("side_a", "side_b", "top", "bottom") else 0
                        if span and (fx % 4) == 0:
                            c = mix(c, pat, 0.6)
                    elif p.pattern == "spots" and name != "bottom":
                        for sx, sy, sr in spot_seeds:
                            if (tx - sx) ** 2 * fw * fw + (ty - sy) ** 2 * fh * fh < (sr * 1.2) ** 2:
                                c = mix(c, pat, 0.7)
                    elif p.pattern == "scales":
                        if (fx + fy) % 2 == 0:
                            c = scale_rgb(c, 0.92)
                    elif p.pattern == "veins" and name in ("top", "bottom"):
                        # membrane veins running along the depth direction
                        if fw >= 6 and fx % max(3, fw // 4) == 0:
                            c = mix(c, pat, 0.8)
                    elif p.pattern == "plates":
                        if fy % 3 == 0:
                            c = mix(c, pat, 0.5)
                    if p.glow_tip and name in ("side_a", "side_b", "front", "back"):
                        if ty < 0.34:
                            c = mix(c, hex_rgb(p.glow_tip), 0.8)
                    if p.edge and name in ("side_a", "side_b", "front", "back"):
                        if fy == 0 or fy == fh - 1:
                            c = mix(c, hex_rgb(p.edge), 0.5)
                    self.put(x0 + fx, y0 + fy, jitter(c))

        if p.eyes:
            self._eyes(faces, d, h, hex_rgb(p.eyes))
        if p.teeth:
            self._teeth(faces, w, d, h)

    def _eyes(self, faces, d, h, col):
        eh = 2 if h >= 5 else 1
        ew = 2 if d >= 6 else 1
        ey = max(1, h // 4)
        pupil = (20, 16, 14)
        white = (235, 230, 210)
        # side_a: front at high x
        x0, y0, fw, fh = faces["side_a"]
        ex = x0 + fw - 1 - ew - max(1, fw // 6)
        for yy in range(eh):
            for xx in range(ew):
                self.put(ex + xx, y0 + ey + yy, col)
        self.put(ex + ew - 1, y0 + ey + eh - 1, pupil) if ew > 1 else None
        self.put(ex - 1, y0 + ey, white) if ew > 1 else None
        # side_b: front at low x (mirror)
        x0, y0, fw, fh = faces["side_b"]
        ex = x0 + max(1, fw // 6) + 1
        for yy in range(eh):
            for xx in range(ew):
                self.put(ex + xx, y0 + ey + yy, col)
        self.put(ex, y0 + ey + eh - 1, pupil) if ew > 1 else None
        self.put(ex + ew, y0 + ey, white) if ew > 1 else None
        # brow ridge
        for xx in range(ew + 2):
            self.put(faces["side_a"][0] + faces["side_a"][2] - 2 - ew - max(1, faces["side_a"][2] // 6) + xx,
                     faces["side_a"][1] + ey - 1,
                     scale_rgb(self.img[faces["side_a"][1] + ey - 1, faces["side_a"][0], :3], 0.7))
            self.put(faces["side_b"][0] + max(1, faces["side_b"][2] // 6) + xx,
                     faces["side_b"][1] + ey - 1,
                     scale_rgb(self.img[faces["side_b"][1] + ey - 1, faces["side_b"][0], :3], 0.7))

    def _teeth(self, faces, w, d, h):
        tooth = (240, 236, 220)
        for name in ("side_a", "side_b", "front"):
            x0, y0, fw, fh = faces[name]
            for fx in range(fw):
                if fx % 2 == 0:
                    self.put(x0 + fx, y0 + fh - 1, tooth)


# --------------------------------------------------------------------------
# Model description
# --------------------------------------------------------------------------

@dataclass
class Cube:
    origin: tuple
    size: tuple
    paint: Paint
    pivot: tuple | None = None
    rotation: tuple | None = None
    inflate: float = 0.0
    uv: tuple = (0, 0)


@dataclass
class Bone:
    name: str
    parent: str | None
    pivot: tuple
    rotation: tuple | None = None
    cubes: list = field(default_factory=list)


class Model:
    def __init__(self, ident: str, visible_bounds=(6, 5, (0, 2, 0))):
        self.ident = ident
        self.bones: list[Bone] = []
        self.visible_bounds = visible_bounds
        self.tex_w = 64
        self.tex_h = 64
        self.texture: np.ndarray | None = None

    # -- building helpers --------------------------------------------------
    def bone(self, name, parent=None, pivot=(0, 0, 0), rotation=None):
        b = Bone(name, parent, tuple(pivot), tuple(rotation) if rotation else None)
        self.bones.append(b)
        return b

    def get(self, name) -> Bone:
        for b in self.bones:
            if b.name == name:
                return b
        raise KeyError(name)

    def cube(self, bone: str | Bone, origin, size, paint: Paint, pivot=None, rotation=None, inflate=0.0):
        b = self.get(bone) if isinstance(bone, str) else bone
        size = tuple(int(round(s)) for s in size)
        c = Cube(tuple(origin), size, paint,
                 tuple(pivot) if pivot else None,
                 tuple(rotation) if rotation else None, inflate)
        b.cubes.append(c)
        return c

    def mirror_bone(self, name: str, new_name: str, new_parent=None):
        """Copy a bone mirrored across X (used for left/right limbs)."""
        src = self.get(name)
        px, py, pz = src.pivot
        rot = None
        if src.rotation:
            rx, ry, rz = src.rotation
            rot = (rx, -ry, -rz)
        nb = self.bone(new_name, new_parent if new_parent is not None else src.parent, (-px, py, pz), rot)
        for c in src.cubes:
            ox, oy, oz = c.origin
            sx, sy, sz = c.size
            cp = None
            cr = None
            if c.pivot:
                cp = (-c.pivot[0], c.pivot[1], c.pivot[2])
            if c.rotation:
                cr = (c.rotation[0], -c.rotation[1], -c.rotation[2])
            nb.cubes.append(Cube((-(ox + sx), oy, oz), c.size, c.paint, cp, cr, c.inflate))
        return nb

    # -- texture -----------------------------------------------------------
    def pack(self):
        cubes = [c for b in self.bones for c in b.cubes]
        items = []
        for c in cubes:
            w, h, d = c.size
            items.append((2 * (w + d), d + h, c))
        items.sort(key=lambda t: (-t[1], -t[0]))
        widest = max(t[0] for t in items)
        tex_w = 64
        while tex_w < widest:
            tex_w *= 2
        # try widths until the atlas is roughly square
        best = None
        for tw in (tex_w, tex_w * 2, tex_w * 4):
            x = y = shelf_h = 0
            placements = []
            for fw, fh, c in items:
                if x + fw > tw:
                    x = 0
                    y += shelf_h
                    shelf_h = 0
                placements.append((x, y, c))
                x += fw
                shelf_h = max(shelf_h, fh)
            total_h = y + shelf_h
            th = 16
            while th < total_h:
                th *= 2
            score = max(tw, th)
            if best is None or score < best[0] or (score == best[0] and tw * th < best[1] * best[2]):
                best = (score, tw, th, placements)
        _, self.tex_w, self.tex_h, placements = best
        for x, y, c in placements:
            c.uv = (x, y)

    def paint(self, seed=1):
        self.pack()
        img = np.zeros((self.tex_h, self.tex_w, 4), dtype=np.uint8)
        i = 0
        for b in self.bones:
            for c in b.cubes:
                Painter(img, seed * 1000 + i).paint_cube(c.uv[0], c.uv[1], c.size, c.paint)
                i += 1
        self.texture = img

    # -- export ------------------------------------------------------------
    def geometry_json(self):
        bones = []
        for b in self.bones:
            jb = {"name": b.name, "pivot": [round(v, 3) for v in b.pivot]}
            if b.parent:
                jb["parent"] = b.parent
            if b.rotation:
                jb["rotation"] = [round(v, 3) for v in b.rotation]
            if b.cubes:
                jc = []
                for c in b.cubes:
                    e = {"origin": [round(v, 3) for v in c.origin], "size": list(c.size), "uv": list(c.uv)}
                    if c.inflate:
                        e["inflate"] = c.inflate
                    if c.pivot:
                        e["pivot"] = [round(v, 3) for v in c.pivot]
                    if c.rotation:
                        e["rotation"] = [round(v, 3) for v in c.rotation]
                    jc.append(e)
                jb["cubes"] = jc
            bones.append(jb)
        vw, vh, vo = self.visible_bounds
        return {
            "format_version": "1.12.0",
            "minecraft:geometry": [{
                "description": {
                    "identifier": self.ident,
                    "texture_width": self.tex_w,
                    "texture_height": self.tex_h,
                    "visible_bounds_width": vw,
                    "visible_bounds_height": vh,
                    "visible_bounds_offset": list(vo),
                },
                "bones": bones,
            }],
        }

    def save_texture(self, path):
        Image.fromarray(self.texture, "RGBA").save(path)


# --------------------------------------------------------------------------
# Preview renderer
# --------------------------------------------------------------------------
# Bedrock geometry is stored mirrored on X compared to how it is displayed
# (this is how Blockbench imports it).  Bone rotations [rx, ry, rz] are
# displayed as an extrinsic X->Y->Z rotation by (-rx, -ry, rz) in that
# mirrored space.  The renderer converts to display space first.

def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _rot(r):
    if not r:
        return np.eye(3)
    rx, ry, rz = (math.radians(v) for v in r)
    return _rz(rz) @ _ry(-ry) @ _rx(-rx)


def _affine(pivot, rot):
    """4x4 matrix for rotating about pivot (pivot already in display space)."""
    m = np.eye(4)
    p = np.array(pivot, dtype=float)
    R = _rot(rot)
    m[:3, :3] = R
    m[:3, 3] = p - R @ p
    return m


def render_preview(model: Model, pose: dict | None = None, yaw=35.0, pitch=20.0,
                   size=(640, 480), scale_px=None, bg=(0, 0, 0, 0)):
    """Render model with orthographic projection. pose: bone -> extra rotation."""
    pose = pose or {}
    tex = model.texture.astype(np.float32)
    th, tw = tex.shape[:2]
    by_name = {b.name: b for b in model.bones}
    world = {}

    def bone_mat(b):
        if b.name in world:
            return world[b.name]
        parent = world_mat(by_name[b.parent]) if b.parent else np.eye(4)
        rot = list(b.rotation) if b.rotation else [0, 0, 0]
        if b.name in pose:
            rot = [rot[i] + pose[b.name][i] for i in range(3)]
        pv = (-b.pivot[0], b.pivot[1], b.pivot[2])
        m = parent @ _affine(pv, rot)
        world[b.name] = m
        return m

    def world_mat(b):
        return bone_mat(b)

    quads = []  # (corners 4x3, uv rect, shade_normal)
    for b in model.bones:
        M = world_mat(b)
        for c in b.cubes:
            ox, oy, oz = c.origin
            w, h, d = c.size
            inf = c.inflate
            x0, x1 = -(ox + w) - inf, -ox + inf
            y0, y1 = oy - inf, oy + h + inf
            z0, z1 = oz - inf, oz + d + inf
            Mc = M
            if c.rotation:
                pv = (-c.pivot[0], c.pivot[1], c.pivot[2])
                Mc = M @ _affine(pv, c.rotation)
            u, v = c.uv
            # display space: north = -Z (front), east = +X
            # each face: corners (top-left, top-right, bottom-left) as seen from outside
            P = lambda x, y, z: (x, y, z)
            faces = [
                # front / north (z0), viewed from -Z: left = +X
                ((P(x1, y1, z0), P(x0, y1, z0), P(x1, y0, z0)), (u + d, v + d, w, h)),
                # back / south (z1), viewed from +Z: left = -X
                ((P(x0, y1, z1), P(x1, y1, z1), P(x0, y0, z1)), (u + 2 * d + w, v + d, w, h)),
                # east (+X, x1) viewed from +X: left = +Z (back), right = -Z (front)
                ((P(x1, y1, z1), P(x1, y1, z0), P(x1, y0, z1)), (u, v + d, d, h)),
                # west (-X, x0) viewed from -X: left = -Z (front)
                ((P(x0, y1, z0), P(x0, y1, z1), P(x0, y0, z0)), (u + d + w, v + d, d, h)),
                # up: texture region rows run back->front (front edge at bottom)
                ((P(x1, y1, z1), P(x0, y1, z1), P(x1, y1, z0)), (u + d, v, w, d)),
                # down
                ((P(x1, y0, z0), P(x0, y0, z0), P(x1, y0, z1)), (u + d + w, v, w, d)),
            ]
            for (a, bb, cc), rect in faces:
                pts = []
                for p in (a, bb, cc):
                    q = Mc @ np.array([p[0], p[1], p[2], 1.0])
                    pts.append(q[:3])
                quads.append((np.array(pts), rect))

    # camera
    yr, pr = math.radians(yaw), math.radians(pitch)
    cam = _rx(pr) @ _ry(yr)  # rotate world into view (view looks down -Z)
    allp = []
    for pts, _ in quads:
        a, b, c = pts
        d4 = b + c - a
        for p in (a, b, c, d4):
            allp.append(cam @ p)
    allp = np.array(allp)
    W, H = size
    mn, mx = allp.min(0), allp.max(0)
    if scale_px is None:
        scale_px = 0.9 * min(W / max(1e-6, mx[0] - mn[0]), H / max(1e-6, mx[1] - mn[1]))
    cx, cy = (mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2

    img = np.zeros((H, W, 4), dtype=np.float32)
    img[:, :] = bg
    zbuf = np.full((H, W), -1e9, dtype=np.float32)
    light = np.array([0.4, 0.8, 0.45])
    light /= np.linalg.norm(light)

    for pts, (ru, rv, rw, rh) in quads:
        if rw <= 0 or rh <= 0:
            continue
        a, b, c = (cam @ p for p in pts)
        e1, e2 = b - a, c - a
        n = np.cross(e1, e2)
        if np.linalg.norm(n) < 1e-9:
            continue
        nn = n / np.linalg.norm(n)
        # orientation: outward normal should face the camera (+Z in view)
        if nn[2] > 0:
            pass
        shade = 0.55 + 0.45 * max(0.0, float(np.dot(-nn if nn[2] < 0 else nn, light)))
        # project
        A = np.array([(a[0] - cx) * scale_px + W / 2, -(a[1] - cy) * scale_px + H / 2])
        E1 = np.array([e1[0] * scale_px, -e1[1] * scale_px])
        E2 = np.array([e2[0] * scale_px, -e2[1] * scale_px])
        det = E1[0] * E2[1] - E1[1] * E2[0]
        if abs(det) < 1e-6:
            continue
        corners = np.array([A, A + E1, A + E2, A + E1 + E2])
        x0, y0 = np.floor(corners.min(0)).astype(int)
        x1, y1 = np.ceil(corners.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, W - 1), min(y1, H - 1)
        if x1 < x0 or y1 < y0:
            continue
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        px = xs + 0.5 - A[0]
        py = ys + 0.5 - A[1]
        s = (px * E2[1] - py * E2[0]) / det
        t = (E1[0] * py - E1[1] * px) / det
        inside = (s >= 0) & (s <= 1) & (t >= 0) & (t <= 1)
        if not inside.any():
            continue
        z = a[2] + s * e1[2] + t * e2[2]
        tu = np.clip((ru + s * rw).astype(int), 0, tw - 1)
        tv = np.clip((rv + t * rh).astype(int), 0, th - 1)
        col = tex[tv, tu]
        vis = inside & (z > zbuf[ys, xs]) & (col[..., 3] > 10)
        zbuf[ys[vis], xs[vis]] = z[vis]
        rgb = col[..., :3] * shade
        img[ys[vis], xs[vis], :3] = rgb[vis]
        img[ys[vis], xs[vis], 3] = 255
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA")
