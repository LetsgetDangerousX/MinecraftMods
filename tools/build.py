#!/usr/bin/env python3
"""Generate the Dinos & Dragons Bedrock add-on.

    python3 tools/build.py

writes
    packs/DinosAndDragons_BP/   behaviour pack (entities, spawn rules, items, castle, scripts)
    packs/DinosAndDragons_RP/   resource pack  (models, textures, animations, sounds, text)
    dist/DinosAndDragons.mcaddon   the file to open on Android / Windows / iOS
    docs/previews/*.png            preview renders
"""
from __future__ import annotations

import json
import shutil
import sys
import uuid
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import castle  # noqa: E402
from creatures import Species, all_species  # noqa: E402
from geo import render_preview  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BP = ROOT / "packs" / "DinosAndDragons_BP"
RP = ROOT / "packs" / "DinosAndDragons_RP"
DIST = ROOT / "dist"
DOCS = ROOT / "docs" / "previews"
SRC = ROOT / "src"

VERSION = [1, 0, 0]
MIN_ENGINE = [1, 21, 90]
ENTITY_FORMAT = "1.21.90"
SCRIPT_API = "2.0.0"
NS = uuid.UUID("6f1d2c3e-1b7a-4c55-9d1e-2a7b9c0d4e11")


def uid(name: str) -> str:
    return str(uuid.uuid5(NS, name))


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def mc(item: str) -> str:
    return item if ":" in item else f"minecraft:{item}"


# --------------------------------------------------------------------------
# Behaviour pack: entities
# --------------------------------------------------------------------------

def entity_json(sp: Species) -> dict:
    dragon = sp.kind == "dragon"
    w, h = sp.collision
    comps = {
        "minecraft:type_family": {"family": sp.family + ["dd_creature", "mob"]},
        "minecraft:health": {"value": sp.health, "max": sp.health},
        "minecraft:collision_box": {"width": w, "height": h},
        "minecraft:attack": {"damage": sp.attack},
        "minecraft:jump.static": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0},
        "minecraft:nameable": {},
        "minecraft:leashable": {},
        "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
        "minecraft:knockback_resistance": {"value": 0.6 if sp.health >= 90 else 0.3},
        "minecraft:follow_range": {"value": 24, "max": 32},
        "minecraft:loot": {"table": f"loot_tables/entities/dd/{sp.id}.json"},
        "minecraft:experience_reward": {"on_death": "query.last_hit_by_player ? 12 : 0"},
        "minecraft:healable": {"items": [{"item": mc(i), "heal_amount": a} for i, a in sp.heal_items]},
        "minecraft:ambient_sound_interval": {"value": 10.0, "range": 16.0, "event_name": "ambient"},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.melee_attack": {"priority": 3, "speed_multiplier": 1.3, "track_target": True},
        "minecraft:behavior.tempt": {"priority": 6, "speed_multiplier": 1.1,
                                     "items": [mc(i) for i in sp.tame_items]},
        "minecraft:behavior.look_at_player": {"priority": 9, "look_distance": 10, "probability": 0.02},
        "minecraft:behavior.random_look_around": {"priority": 10},
        "minecraft:variable_max_auto_step": {"base_value": 1.0625, "controlled_value": 1.5625,
                                             "jump_prevented_value": 0.5625},
    }
    if dragon:
        comps.update({
            "minecraft:can_fly": {},
            "minecraft:movement.fly": {},
            "minecraft:navigation.fly": {"can_path_over_water": True, "can_path_from_air": True,
                                         "avoid_damage_blocks": True},
            "minecraft:damage_sensor": {"triggers": [{"cause": "fall", "deals_damage": "no"}]},
        })
    else:
        comps.update({
            "minecraft:physics": {},
            "minecraft:movement": {"value": sp.speed},
            "minecraft:movement.basic": {"max_turn": 30},
            "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_water": True,
                                          "avoid_damage_blocks": True},
            "minecraft:damage_sensor": {"triggers": [{"cause": "fall", "deals_damage": "yes", "damage_modifier": -6}]},
        })

    wander = ({"minecraft:behavior.random_fly": {"priority": 7, "xz_dist": 14, "y_dist": 5, "y_offset": 1,
                                                  "speed_multiplier": sp.wander_speed + 0.2,
                                                  "can_land_on_trees": False, "avoid_damage_blocks": True}}
              if dragon else
              {"minecraft:behavior.random_stroll": {"priority": 7, "speed_multiplier": sp.wander_speed}})

    groups = {}
    wild = {
        "minecraft:tameable": {"probability": sp.tame_chance, "tame_items": [mc(i) for i in sp.tame_items],
                               "tame_event": {"event": "dd:on_tame", "target": "self"}},
    }
    wild.update(wander)
    if sp.prey:
        wild["minecraft:behavior.nearest_attackable_target"] = {
            "priority": 4, "reselect_targets": True, "must_see": True, "attack_interval": 20,
            "entity_types": [{"filters": {"any_of": [{"test": "is_family", "subject": "other", "value": f}
                                                     for f in sp.prey]},
                              "max_dist": 16}]}
    groups["dd:wild"] = wild

    seats = []
    for i, (x, y, z) in enumerate(sp.seats):
        seat = {"position": [x, y, z], "min_rider_count": i if len(sp.seats) > 1 else 0,
                "max_rider_count": len(sp.seats),
                "third_person_camera_radius": round(min(64.0, max(4.0, 3.0 + sp.scale * 3)), 1),
                "camera_relax_distance_smoothing": 6.0}
        seats.append(seat)
    tamed = {
        "minecraft:is_tamed": {},
        "minecraft:rideable": {
            "seat_count": len(sp.seats), "family_types": ["player"], "crouching_skip_interact": True,
            "interact_text": "action.interact.ride.horse", "dismount_mode": "default",
            "on_rider_enter_event": "dd:mounted", "on_rider_exit_event": "dd:dismounted",
            "seats": seats},
        "minecraft:behavior.player_ride_tamed": {"priority": 0},
        "minecraft:behavior.owner_hurt_by_target": {"priority": 1},
        "minecraft:behavior.owner_hurt_target": {"priority": 2},
        "minecraft:interact": {"interactions": [
            {"on_interact": {"filters": {"all_of": [
                {"test": "is_sneak_held", "subject": "other", "value": True},
                {"test": "is_owner", "subject": "other", "value": True},
                {"test": "bool_property", "subject": "self", "domain": "dd:sitting", "operator": "!=", "value": True}]},
                "event": "dd:sit", "target": "self"},
             "interact_text": "action.interact.dd.stay", "swing": True},
            {"on_interact": {"filters": {"all_of": [
                {"test": "is_sneak_held", "subject": "other", "value": True},
                {"test": "is_owner", "subject": "other", "value": True},
                {"test": "bool_property", "subject": "self", "domain": "dd:sitting", "value": True}]},
                "event": "dd:stand", "target": "self"},
             "interact_text": "action.interact.dd.follow", "swing": True},
        ]},
    }
    if not dragon:
        tamed["minecraft:input_ground_controlled"] = {}
    if sp.carnivore:
        tamed["minecraft:behavior.nearest_attackable_target"] = {
            "priority": 4, "reselect_targets": True, "must_see": True,
            "entity_types": [{"filters": {"all_of": [
                {"test": "is_family", "subject": "other", "value": "monster"},
                {"test": "is_family", "subject": "other", "operator": "not", "value": "creeper"},
                {"test": "is_family", "subject": "other", "operator": "not", "value": "enderman"}]},
                "max_dist": 16}]}
    groups["dd:tamed"] = tamed
    follow = {"minecraft:behavior.follow_owner": {"priority": 5, "speed_multiplier": 1.25,
                                                  "start_distance": 14, "stop_distance": 4}}
    follow.update({k: dict(v, priority=8) for k, v in wander.items()})
    groups["dd:follow"] = follow
    groups["dd:stay"] = {"minecraft:mark_variant": {"value": 1}}

    events = {}
    if dragon:
        groups["dd:unridden"] = {
            "minecraft:physics": {},
            "minecraft:movement": {"value": 0.3},
            "minecraft:flying_speed": {"value": 0.05},
        }
        groups["dd:ridden"] = {
            "minecraft:physics": {"has_gravity": False},
            "minecraft:movement": {"value": sp.fly_speed},
            "minecraft:flying_speed": {"value": sp.fly_speed},
            "minecraft:free_camera_controlled": {"strafe_speed_modifier": 0.7, "backwards_movement_modifier": 0.5},
            "minecraft:vertical_movement_action": {"vertical_velocity": 0.45},
        }
        events["minecraft:entity_spawned"] = {"add": {"component_groups": ["dd:wild", "dd:unridden"]}}
        events["dd:mounted"] = {"remove": {"component_groups": ["dd:stay", "dd:unridden"]},
                                "add": {"component_groups": ["dd:follow", "dd:ridden"]},
                                "set_property": {"dd:sitting": False, "dd:ridden": True}}
        events["dd:dismounted"] = {"remove": {"component_groups": ["dd:ridden"]},
                                   "add": {"component_groups": ["dd:unridden"]},
                                   "set_property": {"dd:ridden": False}}
    else:
        events["minecraft:entity_spawned"] = {"add": {"component_groups": ["dd:wild"]}}
        events["dd:mounted"] = {"remove": {"component_groups": ["dd:stay"]},
                                "add": {"component_groups": ["dd:follow"]},
                                "set_property": {"dd:sitting": False, "dd:ridden": True}}
        events["dd:dismounted"] = {"set_property": {"dd:ridden": False}}
    events["dd:on_tame"] = {"remove": {"component_groups": ["dd:wild"]},
                            "add": {"component_groups": ["dd:tamed", "dd:follow"]},
                            "set_property": {"dd:sitting": False}}
    events["dd:sit"] = {"remove": {"component_groups": ["dd:follow"]}, "add": {"component_groups": ["dd:stay"]},
                        "set_property": {"dd:sitting": True}}
    events["dd:stand"] = {"remove": {"component_groups": ["dd:stay"]}, "add": {"component_groups": ["dd:follow"]},
                          "set_property": {"dd:sitting": False}}

    return {
        "format_version": ENTITY_FORMAT,
        "minecraft:entity": {
            "description": {
                "identifier": f"dd:{sp.id}",
                "spawn_category": "creature",
                "is_spawnable": True,
                "is_summonable": True,
                "properties": {
                    "dd:sitting": {"type": "bool", "default": False, "client_sync": True},
                    "dd:ridden": {"type": "bool", "default": False, "client_sync": True},
                },
            },
            "component_groups": groups,
            "components": comps,
            "events": events,
        },
    }


DINO_GROUND = ["minecraft:grass_block", "minecraft:sand", "minecraft:red_sand", "minecraft:dirt",
               "minecraft:coarse_dirt", "minecraft:podzol", "minecraft:moss_block", "minecraft:mud"]


def spawn_rules_json(sp: Species) -> dict:
    conds = []
    for tag, weight, mn, mx in sp.spawns:
        c = {
            "minecraft:spawns_on_surface": {},
            "minecraft:brightness_filter": {"min": 7, "max": 15, "adjust_for_weather": False},
            "minecraft:weight": {"default": weight},
            "minecraft:herd": {"min_size": mn, "max_size": mx},
            "minecraft:density_limit": {"surface": 2 if sp.kind == "dragon" else 4},
            "minecraft:biome_filter": [
                {"test": "has_biome_tag", "operator": "==", "value": tag},
                {"test": "has_biome_tag", "operator": "!=", "value": "ocean"},
                {"test": "has_biome_tag", "operator": "!=", "value": "river"},
            ],
        }
        if sp.kind == "dino":
            c["minecraft:spawns_on_block_filter"] = DINO_GROUND
        conds.append(c)
    return {"format_version": "1.8.0",
            "minecraft:spawn_rules": {"description": {"identifier": f"dd:{sp.id}", "population_control": "animal"},
                                      "conditions": conds}}


def loot_json(sp: Species) -> dict:
    pools = []
    for item, mn, mx in sp.loot:
        pools.append({"rolls": 1, "entries": [{"type": "item", "name": mc(item), "weight": 1,
                                               "functions": [{"function": "set_count",
                                                              "count": {"min": mn, "max": mx}}]}]})
    return {"pools": pools}


# --------------------------------------------------------------------------
# Resource pack: animations / client entities
# --------------------------------------------------------------------------

def walk_coef(sp: Species):
    a = sp.anim
    leg_world = a["leg_len"] * sp.scale
    return round(38.17 * 6.0 / leg_world, 3), a["walk_amp"]


def animations_json(sp: Species) -> dict:
    a = sp.anim
    pid = sp.id
    c, amp = walk_coef(sp)
    speed = "math.clamp(query.modified_move_speed * 2.2, 0, 1) * (query.is_on_ground ? 1 : 0)"
    walk = {}
    for bone, phase in a["legs"]:
        walk[bone] = {"rotation": [f"math.cos(query.modified_distance_moved * {c} + {phase}) * {amp} * {speed}", 0, 0]}
    for bone, phase in a.get("arms", []):
        walk[bone] = {"rotation": [f"math.cos(query.modified_distance_moved * {c} + {phase}) * 12 * {speed}", 0, 0]}
    for i, bone in enumerate(a["tail"]):
        walk[bone] = {"rotation": [0, f"math.sin(query.modified_distance_moved * {c} - {i * 30}) * {3 + i * 2} * {speed}", 0]}
    if a["biped"]:
        walk["body"] = {"rotation": [0, 0, f"math.sin(query.modified_distance_moved * {c}) * 3 * {speed}"]}
    else:
        walk["body"] = {"position": [0, f"math.abs(math.cos(query.modified_distance_moved * {c})) * 0.6 * {speed}", 0]}

    idle = {}
    for i, bone in enumerate(a["tail"]):
        idle[bone] = {"rotation": [f"math.sin(query.life_time * 45 - {i * 35}) * 1.5",
                                   f"math.sin(query.life_time * 60 - {i * 40}) * {3 + i * 2.5}", 0]}
    for i, bone in enumerate(a["neck"]):
        idle[bone] = {"rotation": [f"math.sin(query.life_time * 40 + {i * 25}) * 2", 0, 0]}
    if a.get("jaw"):
        idle[a["jaw"]] = {"rotation": ["math.pow(math.max(0, math.sin(query.life_time * 22)), 12) * 22", 0, 0]}

    look = {a["head"]: {"rotation": ["query.target_x_rotation * 0.7", "query.target_y_rotation * 0.8", 0]}}

    drop = a["sit_drop"]
    sit = {"root": {"position": [0, -drop, 0]}}
    for bone, _ in a["legs"]:
        sit[bone] = {"rotation": [-90, 0, 0], "position": [0, 0, 0]}
    if a["tail"]:
        sit[a["tail"][0]] = {"rotation": [8, 0, 0]}

    anims = {
        f"animation.dd.{pid}.walk": {"loop": True, "bones": walk},
        f"animation.dd.{pid}.idle": {"loop": True, "bones": idle},
        f"animation.dd.{pid}.look": {"loop": True, "bones": look},
        f"animation.dd.{pid}.sit": {"loop": True, "bones": sit},
    }
    wg = a.get("wings")
    if wg:
        flap = "query.life_time * 300"
        anims[f"animation.dd.{pid}.fly"] = {"loop": True, "bones": {
            wg["l"]: {"rotation": [0, 0, f"math.sin({flap}) * 38"]},
            wg["r"]: {"rotation": [0, 0, f"-math.sin({flap}) * 38"]},
            wg["lt"]: {"rotation": [0, 0, f"math.sin({flap} - 50) * 28"]},
            wg["rt"]: {"rotation": [0, 0, f"-math.sin({flap} - 50) * 28"]},
            "leg_fl": {"rotation": [35, 0, 0]}, "leg_fr": {"rotation": [35, 0, 0]},
            "leg_bl": {"rotation": [55, 0, 0]}, "leg_br": {"rotation": [55, 0, 0]},
            "body": {"position": [0, f"math.sin({flap} + 90) * 0.8", 0]},
            "tail1": {"rotation": [f"math.sin({flap} - 60) * 3", 0, 0]},
        }}
        anims[f"animation.dd.{pid}.fold"] = {"loop": True, "bones": {
            wg["l"]: {"rotation": [0, f"-70 + math.sin(query.life_time * 50) * 2", -25]},
            wg["r"]: {"rotation": [0, f"70 - math.sin(query.life_time * 50) * 2", 25]},
            wg["lt"]: {"rotation": [0, -100, 40]},
            wg["rt"]: {"rotation": [0, 100, -40]},
        }}
    return {"format_version": "1.8.0", "animations": anims}


def wings_controller() -> dict:
    return {"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.dd.dragon.wings": {
            "initial_state": "ground",
            "states": {
                "ground": {"animations": ["fold"], "blend_transition": 0.3,
                           "transitions": [{"air": "!query.is_on_ground && !query.is_in_water"}]},
                "air": {"animations": ["fly"], "blend_transition": 0.3,
                        "transitions": [{"ground": "query.is_on_ground || query.is_in_water"}]},
            }}}}


def client_entity_json(sp: Species) -> dict:
    pid = sp.id
    animations = {
        "walk": f"animation.dd.{pid}.walk",
        "idle": f"animation.dd.{pid}.idle",
        "look": f"animation.dd.{pid}.look",
        "sit": f"animation.dd.{pid}.sit",
    }
    animate = ["walk", "idle", "look", {"sit": "query.property('dd:sitting') ? 1.0 : 0.0"}]
    if sp.kind == "dragon":
        animations.update({"fly": f"animation.dd.{pid}.fly", "fold": f"animation.dd.{pid}.fold",
                           "wings": "controller.animation.dd.dragon.wings"})
        animate.append("wings")
    return {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": f"dd:{pid}",
                "materials": {"default": "entity_alphatest"},
                "textures": {"default": f"textures/entity/dd/{pid}"},
                "geometry": {"default": sp.model.ident},
                "animations": animations,
                "scripts": {"scale": str(sp.scale), "animate": animate},
                "render_controllers": ["controller.render.dd.default"],
                "spawn_egg": {"base_color": sp.egg[0], "overlay_color": sp.egg[1]},
            }
        },
    }


def render_controllers_json():
    return {"format_version": "1.8.0", "render_controllers": {
        "controller.render.dd.default": {
            "geometry": "Geometry.default",
            "materials": [{"*": "Material.default"}],
            "textures": ["Texture.default"],
        }}}


def sounds_json(species):
    ents = {}
    for sp in species:
        s = sp.sounds
        ev = {"ambient": s["ambient"], "hurt": s["hurt"], "death": s["death"],
              "step": {"sound": s["step"], "volume": 0.5}}
        ents[f"dd:{sp.id}"] = {"volume": s["volume"], "pitch": list(s["pitch"]), "events": ev}
    return {"entity_sounds": {"entities": ents}}


PARTICLES = {
    "dd:fire_breath": dict(material="particles_add", colors={"0.0": "#FFFFF0A0", "0.35": "#FFFF8A1C", "1.0": "#AA5A1A10"},
                           size=0.35, grow=0.9, lift=1.2),
    "dd:frost_breath": dict(material="particles_alpha", colors={"0.0": "#FFFFFFFF", "0.5": "#FFBFEFFF", "1.0": "#FF7FC8F0"},
                            size=0.3, grow=0.5, lift=-0.4),
    "dd:spore_breath": dict(material="particles_blend", colors={"0.0": "#FFB8F070", "0.5": "#FF62B040", "1.0": "#80305A20"},
                            size=0.3, grow=0.7, lift=0.4),
    "dd:storm_breath": dict(material="particles_add", colors={"0.0": "#FFFFFFFF", "0.3": "#FFFFF35C", "1.0": "#AA8E6BFF"},
                            size=0.22, grow=0.4, lift=0.0),
    "dd:roar": dict(material="particles_blend", colors={"0.0": "#C0FFFFFF", "1.0": "#00FFFFFF"},
                    size=0.5, grow=1.6, lift=0.2),
}


def particle_json(pid, p):
    return {
        "format_version": "1.10.0",
        "particle_effect": {
            "description": {"identifier": pid,
                            "basic_render_parameters": {"material": p["material"],
                                                        "texture": "textures/particle/particles"}},
            "components": {
                "minecraft:emitter_rate_instant": {"num_particles": 5},
                "minecraft:emitter_lifetime_once": {"active_time": 0.05},
                "minecraft:emitter_shape_sphere": {"radius": 0.35, "direction": "outwards"},
                "minecraft:particle_lifetime_expression": {"max_lifetime": "0.45 + variable.particle_random_1 * 0.35"},
                "minecraft:particle_initial_speed": 0.6,
                "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, p["lift"], 0],
                                                      "linear_drag_coefficient": 1.5},
                "minecraft:particle_appearance_billboard": {
                    "size": [f"{p['size']} + variable.particle_age * {p['grow']}",
                             f"{p['size']} + variable.particle_age * {p['grow']}"],
                    "facing_camera_mode": "rotate_xyz",
                    "uv": {"texture_width": 128, "texture_height": 128,
                           "flipbook": {"base_UV": [56, 0], "size_UV": [8, 8], "step_UV": [-8, 0],
                                        "frames_per_second": 10, "max_frame": 8,
                                        "stretch_to_lifetime": True, "loop": False}}},
                "minecraft:particle_appearance_tinting": {
                    "color": {"interpolant": "variable.particle_age / variable.particle_lifetime",
                              "gradient": p["colors"]}},
            },
        },
    }


# --------------------------------------------------------------------------
# Items & icons
# --------------------------------------------------------------------------

def draw_horn_icon(path):
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    px = img.load()
    ivory, shade, gold, dark = (236, 226, 196, 255), (190, 176, 140, 255), (235, 190, 60, 255), (120, 90, 30, 255)
    pts = [(2, 13), (3, 12), (4, 12), (5, 11), (6, 10), (7, 10), (8, 9), (9, 8), (10, 7), (11, 6), (11, 5), (12, 4), (12, 3)]
    for i, (x, y) in enumerate(pts):
        r = 2 if i < 5 else 1 if i < 10 else 0
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if abs(dx) + abs(dy) <= r + 0 and 0 <= x + dx < 16 and 0 <= y + dy < 16:
                    px[x + dx, y + dy] = shade if dy > 0 else ivory
    for (x, y) in [(5, 10), (5, 11), (6, 11), (4, 11), (6, 9), (5, 12)]:
        px[x, y] = gold
    for (x, y) in [(1, 13), (1, 14), (2, 14), (1, 12), (2, 12)]:
        px[x, y] = dark
    px[12, 2] = ivory
    img.save(path)


def draw_blueprint_icon(path):
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([1, 2, 14, 13], fill=(38, 92, 170, 255), outline=(22, 58, 118, 255))
    w = (225, 238, 255, 255)
    # little castle outline
    d.line([(4, 11), (4, 6), (6, 6), (6, 8), (9, 8), (9, 6), (11, 6), (11, 11), (4, 11)], fill=w)
    d.point([(4, 5), (6, 5), (9, 5), (11, 5)], fill=w)
    d.rectangle([7, 9, 8, 11], fill=w)
    d.line([(1, 2), (1, 13)], fill=(200, 220, 250, 255))
    img.save(path)


def item_json(ident, name, icon, components):
    comps = {"minecraft:icon": {"textures": {"default": icon}}, "minecraft:display_name": {"value": name},
             "minecraft:max_stack_size": 1}
    comps.update(components)
    return {"format_version": "1.21.90",
            "minecraft:item": {"description": {"identifier": ident, "menu_category": {"category": "equipment"}},
                               "components": comps}}


# --------------------------------------------------------------------------
# Icons / previews
# --------------------------------------------------------------------------

def pack_icon(models, path, bg):
    tiles = []
    for m, yaw in models:
        tiles.append(render_preview(m, yaw=yaw, pitch=18, size=(256, 256)))
    img = Image.new("RGBA", (256, 256), bg)
    for t in tiles:
        img.alpha_composite(t)
    img.save(path)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    for d in (BP, RP):
        if d.exists():
            shutil.rmtree(d)
    DIST.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    species = all_species()

    bp_uuid, rp_uuid = uid("bp"), uid("rp")
    write_json(BP / "manifest.json", {
        "format_version": 2,
        "header": {"name": "Dinos & Dragons", "description": "pack.description",
                   "uuid": bp_uuid, "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [
            {"type": "data", "uuid": uid("bp-data"), "version": VERSION},
            {"type": "script", "language": "javascript", "uuid": uid("bp-script"), "version": VERSION,
             "entry": "scripts/main.js"},
        ],
        "dependencies": [
            {"uuid": rp_uuid, "version": VERSION},
            {"module_name": "@minecraft/server", "version": SCRIPT_API},
        ],
        "metadata": {"authors": ["Dinos & Dragons"], "product_type": "addon"},
    })
    write_json(RP / "manifest.json", {
        "format_version": 2,
        "header": {"name": "Dinos & Dragons Resources", "description": "pack.description",
                   "uuid": rp_uuid, "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": uid("rp-res"), "version": VERSION}],
        "dependencies": [{"uuid": bp_uuid, "version": VERSION}],
        "metadata": {"authors": ["Dinos & Dragons"], "product_type": "addon"},
    })

    # ---- creatures -------------------------------------------------------
    for sp in species:
        write_json(BP / "entities" / f"{sp.id}.json", entity_json(sp))
        write_json(BP / "spawn_rules" / f"{sp.id}.json", spawn_rules_json(sp))
        write_json(BP / "loot_tables" / "entities" / "dd" / f"{sp.id}.json", loot_json(sp))
        write_json(RP / "models" / "entity" / f"{sp.id}.geo.json", sp.model.geometry_json())
        (RP / "textures" / "entity" / "dd").mkdir(parents=True, exist_ok=True)
        sp.model.save_texture(RP / "textures" / "entity" / "dd" / f"{sp.id}.png")
        write_json(RP / "entity" / f"{sp.id}.entity.json", client_entity_json(sp))
        write_json(RP / "animations" / f"{sp.id}.animation.json", animations_json(sp))
    write_json(RP / "animation_controllers" / "dd_dragon.animation_controllers.json", wings_controller())
    write_json(RP / "render_controllers" / "dd.render_controllers.json", render_controllers_json())
    write_json(RP / "sounds.json", sounds_json(species))
    for pid, p in PARTICLES.items():
        write_json(RP / "particles" / f"{pid.split(':')[1]}.json", particle_json(pid, p))

    # ---- items -----------------------------------------------------------
    (RP / "textures" / "items").mkdir(parents=True, exist_ok=True)
    draw_horn_icon(RP / "textures" / "items" / "dd_dragon_horn.png")
    draw_blueprint_icon(RP / "textures" / "items" / "dd_castle_blueprint.png")
    write_json(RP / "textures" / "item_texture.json", {
        "resource_pack_name": "dinos_and_dragons", "texture_name": "atlas.items",
        "texture_data": {"dd_dragon_horn": {"textures": "textures/items/dd_dragon_horn"},
                         "dd_castle_blueprint": {"textures": "textures/items/dd_castle_blueprint"}}})
    use = {"minecraft:use_modifiers": {"use_duration": 0.25, "movement_modifier": 1.0}}
    write_json(BP / "items" / "dragon_horn.json", item_json(
        "dd:dragon_horn", "Dragon Horn", "dd_dragon_horn",
        dict(use, **{"minecraft:interact_button": "Use Horn", "minecraft:hand_equipped": True})))
    write_json(BP / "items" / "castle_blueprint.json", item_json(
        "dd:castle_blueprint", "Castle Blueprint", "dd_castle_blueprint",
        dict(use, **{"minecraft:interact_button": "Build Castle", "minecraft:glint": True})))
    write_json(BP / "recipes" / "dragon_horn.json", {
        "format_version": "1.20.10",
        "minecraft:recipe_shapeless": {
            "description": {"identifier": "dd:dragon_horn"}, "tags": ["crafting_table"],
            "ingredients": [{"item": "minecraft:bone"}, {"item": "minecraft:gold_ingot"}, {"item": "minecraft:leather"}],
            "result": {"item": "dd:dragon_horn"}}})
    write_json(BP / "recipes" / "castle_blueprint.json", {
        "format_version": "1.20.10",
        "minecraft:recipe_shaped": {
            "description": {"identifier": "dd:castle_blueprint"}, "tags": ["crafting_table"],
            "pattern": ["SSS", "SPS", "SSS"],
            "key": {"S": {"item": "minecraft:stone_bricks"}, "P": {"item": "minecraft:paper"}},
            "result": {"item": "dd:castle_blueprint"}}})

    # ---- castle functions -----------------------------------------------
    b, parts = castle.build()
    fdir = BP / "functions" / "dd" / "castle"
    fdir.mkdir(parents=True, exist_ok=True)
    for i, cmds in enumerate(parts, 1):
        (fdir / f"part_{i}.mcfunction").write_text(
            f"# Dinos & Dragons castle, part {i}/{len(parts)} (generated by tools/castle.py)\n" + "\n".join(cmds) + "\n")
    (fdir / "build_here.mcfunction").write_text(
        "# Builds the whole castle centred on the executing position (gate faces south).\n"
        "# The spawn point is set in the courtyard just inside the gate.\n"
        + "\n".join(f"function dd/castle/part_{i}" for i in range(1, len(parts) + 1))
        + "\nsetworldspawn ~ ~1 ~8\n")
    castle.render(b, str(DOCS / "castle.png"))
    castle.render(b, str(DOCS / "castle_cutaway.png"), cut_y=4)

    # ---- scripts ---------------------------------------------------------
    (BP / "scripts").mkdir(parents=True, exist_ok=True)
    species_js = {sp.id: {"name": sp.name, "kind": sp.kind, "breath": sp.breath,
                          "tame": sp.tame_items, "height": sp.collision[1]} for sp in species}
    (BP / "scripts" / "species.js").write_text(
        "// Generated by tools/build.py - creature data shared with main.js\n"
        f"export const CASTLE_PARTS = {len(parts)};\n"
        f"export const SPECIES = {json.dumps(species_js, indent=2)};\n")
    shutil.copy(SRC / "main.js", BP / "scripts" / "main.js")

    # ---- text ------------------------------------------------------------
    lang = [
        "pack.name=Dinos & Dragons",
        "pack.description=Tameable dragons and dinosaurs, plus a castle at spawn to call home.",
        "action.interact.dd.stay=Stay",
        "action.interact.dd.follow=Follow",
        "item.dd:dragon_horn=Dragon Horn",
        "item.dd:castle_blueprint=Castle Blueprint",
    ]
    for sp in species:
        lang.append(f"entity.dd:{sp.id}.name={sp.name}")
        lang.append(f"item.spawn_egg.entity.dd:{sp.id}.name={sp.name} Spawn Egg")
    for pack in (BP, RP):
        (pack / "texts").mkdir(parents=True, exist_ok=True)
        (pack / "texts" / "en_US.lang").write_text("\n".join(lang) + "\n")
        write_json(pack / "texts" / "languages.json", ["en_US"])

    # ---- icons & previews --------------------------------------------------
    by_id = {sp.id: sp for sp in species}
    pack_icon([(by_id["fire_dragon"].model, 140)], BP / "pack_icon.png", (60, 40, 70, 255))
    pack_icon([(by_id["trex"].model, 140)], RP / "pack_icon.png", (70, 110, 60, 255))
    tiles = []
    for sp in species:
        im = render_preview(sp.model, yaw=145, pitch=18, size=(420, 320), bg=(150, 190, 230, 255))
        d = ImageDraw.Draw(im)
        d.text((10, 8), sp.name, fill=(20, 20, 30, 255))
        tiles.append(im)
        im.save(DOCS / f"{sp.id}.png")
    sheet = Image.new("RGBA", (420 * 3, 320 * 3))
    for k, im in enumerate(tiles):
        sheet.paste(im, ((k % 3) * 420, (k // 3) * 320))
    sheet.save(DOCS / "creatures.png")

    # ---- package -----------------------------------------------------------
    out = DIST / "DinosAndDragons.mcaddon"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for f in sorted(pack.rglob("*")):
                if f.is_file():
                    z.write(f, Path(pack.name) / f.relative_to(pack))
    print(f"built {out} ({out.stat().st_size // 1024} KB), {len(species)} creatures, "
          f"{len(b.cmds)} castle commands in {len(parts)} parts")


if __name__ == "__main__":
    main()
