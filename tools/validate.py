#!/usr/bin/env python3
"""Static checks for the generated packs (run after build.py).

    python3 tools/validate.py [path/to/@minecraft/vanilla-data/lib/mojang-block.d.ts]

Checks cross references that the game would otherwise only report in its
content log: geometry <-> animations, textures, events <-> component groups,
loot tables, item icons, language strings, and every block id / block state
used by the castle functions (when Mojang's vanilla-data typings are given).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BP = ROOT / "packs" / "DinosAndDragons_BP"
RP = ROOT / "packs" / "DinosAndDragons_RP"

errors: list[str] = []


def err(msg):
    errors.append(msg)


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception as e:  # noqa: BLE001
        err(f"{p}: invalid JSON: {e}")
        return {}


def main():
    jsons = {p: load(p) for pack in (BP, RP) for p in pack.rglob("*.json")}
    print(f"parsed {len(jsons)} JSON files")

    # geometry
    geos = {}
    for p in (RP / "models" / "entity").glob("*.geo.json"):
        g = jsons[p]["minecraft:geometry"][0]
        d = g["description"]
        bones = {b["name"]: b for b in g["bones"]}
        for b in g["bones"]:
            if b.get("parent") and b["parent"] not in bones:
                err(f"{p.name}: bone {b['name']} has unknown parent {b['parent']}")
            for c in b.get("cubes", []):
                w, h, dd = c["size"]
                u, v = c["uv"]
                if u + 2 * (w + dd) > d["texture_width"] or v + dd + h > d["texture_height"]:
                    err(f"{p.name}: cube uv out of texture in bone {b['name']}")
        geos[d["identifier"]] = (d, bones)

    anims = {}
    for p in (RP / "animations").glob("*.json"):
        for k, v in jsons[p]["animations"].items():
            anims[k] = v
    controllers = {}
    for p in (RP / "animation_controllers").glob("*.json"):
        controllers.update(jsons[p]["animation_controllers"])
    rcs = {}
    for p in (RP / "render_controllers").glob("*.json"):
        rcs.update(jsons[p]["render_controllers"])
    lang = (RP / "texts" / "en_US.lang").read_text()

    for p in (RP / "entity").glob("*.json"):
        ce = jsons[p]["minecraft:client_entity"]["description"]
        ident = ce["identifier"]
        geo_id = ce["geometry"]["default"]
        if geo_id not in geos:
            err(f"{p.name}: unknown geometry {geo_id}")
            continue
        d, bones = geos[geo_id]
        tex = RP / (ce["textures"]["default"] + ".png")
        if not tex.exists():
            err(f"{p.name}: missing texture {tex}")
        else:
            im = Image.open(tex)
            if im.size != (d["texture_width"], d["texture_height"]):
                err(f"{p.name}: texture size {im.size} != geometry {d['texture_width']}x{d['texture_height']}")
        for rc in ce["render_controllers"]:
            if rc not in rcs:
                err(f"{p.name}: unknown render controller {rc}")
        for short, full in ce["animations"].items():
            if full.startswith("controller."):
                if full not in controllers:
                    err(f"{p.name}: unknown controller {full}")
                    continue
                for st in controllers[full]["states"].values():
                    for a in st["animations"]:
                        name = a if isinstance(a, str) else next(iter(a))
                        if name not in ce["animations"]:
                            err(f"{p.name}: controller uses undefined short name {name}")
                continue
            if full not in anims:
                err(f"{p.name}: unknown animation {full}")
                continue
            for bone in anims[full].get("bones", {}):
                if bone not in bones:
                    err(f"{p.name}: animation {full} targets missing bone {bone}")
        for a in ce["scripts"]["animate"]:
            name = a if isinstance(a, str) else next(iter(a))
            if name not in ce["animations"]:
                err(f"{p.name}: animate references unknown {name}")
        if f"entity.{ident}.name=" not in lang:
            err(f"lang missing entity name for {ident}")
        if f"item.spawn_egg.entity.{ident}.name=" not in lang:
            err(f"lang missing spawn egg name for {ident}")
        if not (BP / "entities" / f"{ident.split(':')[1]}.json").exists():
            err(f"{ident}: client entity without behaviour entity")

    # behaviour entities
    def walk_events(obj, found):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("event", "on_rider_enter_event", "on_rider_exit_event") and isinstance(v, str):
                    found.add(v)
                walk_events(v, found)
        elif isinstance(obj, list):
            for x in obj:
                walk_events(x, found)

    for p in (BP / "entities").glob("*.json"):
        e = jsons[p]["minecraft:entity"]
        groups = set(e["component_groups"])
        events = e["events"]
        for name, ev in events.items():
            for key in ("add", "remove"):
                for g in ev.get(key, {}).get("component_groups", []):
                    if g not in groups:
                        err(f"{p.name}: event {name} uses unknown group {g}")
            for prop in ev.get("set_property", {}):
                if prop not in e["description"].get("properties", {}):
                    err(f"{p.name}: event {name} sets unknown property {prop}")
        used = set()
        walk_events(e["component_groups"], used)
        walk_events(e["components"], used)
        for u in used:
            if u not in events:
                err(f"{p.name}: references undefined event {u}")
        loot = e["components"].get("minecraft:loot", {}).get("table")
        if loot and not (BP / loot).exists():
            err(f"{p.name}: missing loot table {loot}")
        ident = e["description"]["identifier"]
        if not (BP / "spawn_rules" / p.name).exists():
            err(f"{p.name}: no spawn rules")
        else:
            sr = jsons[BP / "spawn_rules" / p.name]["minecraft:spawn_rules"]["description"]["identifier"]
            if sr != ident:
                err(f"{p.name}: spawn rule identifier {sr} != {ident}")
        # every component must exist in exactly one place for the swap groups
        for gname, g in e["component_groups"].items():
            for comp in g:
                if comp in e["components"]:
                    err(f"{p.name}: {comp} in both components and group {gname}")

    # items
    itex = jsons[RP / "textures" / "item_texture.json"]["texture_data"]
    for p in (BP / "items").glob("*.json"):
        it = jsons[p]["minecraft:item"]
        icon = it["components"]["minecraft:icon"]["textures"]["default"]
        if icon not in itex:
            err(f"{p.name}: icon {icon} not in item_texture.json")
        elif not (RP / (itex[icon]["textures"] + ".png")).exists():
            err(f"{p.name}: icon texture file missing")

    # scripts reference functions that exist
    js = (BP / "scripts" / "species.js").read_text()
    n = int(re.search(r"CASTLE_PARTS = (\d+)", js).group(1))
    for i in range(1, n + 1):
        if not (BP / "functions" / "dd" / "castle" / f"part_{i}.mcfunction").exists():
            err(f"missing castle function part_{i}")

    # castle blocks against vanilla data
    if len(sys.argv) > 1:
        check_blocks(Path(sys.argv[1]))

    for f in (BP / "functions").rglob("*.mcfunction"):
        lines = [ln for ln in f.read_text().splitlines() if ln and not ln.startswith("#")]
        if len(lines) > 10000:
            err(f"{f.name}: more than 10000 commands")

    if errors:
        print("\n".join("ERROR: " + e for e in errors))
        sys.exit(1)
    print("all checks passed")


def check_blocks(dts: Path):
    src = dts.read_text()
    blocks = set(re.findall(r'= "minecraft:([a-z0-9_]+)"', src))
    superset = dict(re.findall(r"\['([a-z_:]+)'\]\?: (number|boolean|string);", src))
    states_for = {}
    for name, body in re.findall(r"export type (\w+)States = Pick<BlockStateSuperset, ([^>]+)>;", src):
        states_for[name] = re.findall(r"'([a-z_:]+)'", body)
    pascal = lambda s: "".join(w.capitalize() for w in s.split("_"))  # noqa: E731
    cmd_re = re.compile(r"^(fill|setblock) ((?:~-?\d+ ?){3,6}) ?([a-z_]+)(?: \[(.*?)\])?(?: (\w+))?$")
    checked = 0
    for f in (BP / "functions").rglob("*.mcfunction"):
        for ln in f.read_text().splitlines():
            if not ln or ln.startswith("#") or ln.startswith("function") or ln.startswith("setworldspawn"):
                continue
            m = cmd_re.match(ln)
            if not m:
                err(f"{f.name}: cannot parse '{ln}'")
                continue
            block, states, mode = m.group(3), m.group(4), m.group(5)
            checked += 1
            if block != "air" and block not in blocks:
                err(f"{f.name}: unknown block {block}")
            if mode and mode not in ("replace", "destroy", "hollow", "keep", "outline"):
                err(f"{f.name}: bad fill mode {mode}")
            if states:
                allowed = states_for.get(pascal(block), [])
                for k, v in re.findall(r'"([^"]+)"=([^,\]]+)', states):
                    if k not in allowed:
                        err(f"{f.name}: block {block} has no state {k} (allowed {allowed})")
                    t = superset.get(k)
                    if t == "boolean" and v not in ("true", "false"):
                        err(f"{f.name}: state {k} expects boolean, got {v}")
                    if t == "number" and not v.lstrip("-").isdigit():
                        err(f"{f.name}: state {k} expects number, got {v}")
                    if t == "string" and not v.startswith('"'):
                        err(f"{f.name}: state {k} expects string, got {v}")
    print(f"checked {checked} castle commands against {len(blocks)} vanilla blocks")


if __name__ == "__main__":
    main()
