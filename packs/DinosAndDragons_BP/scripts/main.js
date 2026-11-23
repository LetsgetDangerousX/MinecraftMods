// @ts-check
// Dinos & Dragons - gameplay script
//
//  * Builds the spawn castle the first time someone joins a new world and
//    moves the world spawn into its courtyard.
//  * Dragon Horn: breath attack while riding a dragon, roar while riding a
//    dinosaur, or calls your sitting creatures back to you on foot.
//  * Castle Blueprint: builds another castle where you stand (sneak + use).
//  * Safety: riders who hop off a flying dragon get slow falling.
//
// Chat commands (cheats on):  /scriptevent dd:castle   /scriptevent dd:help
//                             /scriptevent dd:spawn_all  /scriptevent dd:setspawn
import { world, system, ItemStack, EntityDamageCause, GameMode } from "@minecraft/server";
import { SPECIES, CASTLE_PARTS } from "./species.js";

const CASTLE_KEY = "dd:castle";
const KIT_TAG = "dd_kit";
const NEW_WORLD_TICKS = 20 * 60 * 5; // worlds younger than 5 minutes get the castle automatically
const SPAWN_OFFSET = { x: 0, y: 1, z: 8 }; // courtyard, just inside the gate

/** @type {Map<string, number>} */
const hornCooldown = new Map();
/** @type {Map<string, boolean>} */
const wasRidingDragon = new Map();
let building = false;

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

/** @param {string} typeId */
function speciesOf(typeId) {
  if (!typeId.startsWith("dd:")) return undefined;
  return SPECIES[/** @type {keyof typeof SPECIES} */ (typeId.slice(3))];
}

/** @param {import("@minecraft/server").Player} player */
function mountOf(player) {
  try {
    const riding = player.getComponent("minecraft:riding");
    const mount = riding?.entityRidingOn;
    if (mount && speciesOf(mount.typeId)) return mount;
  } catch {
    // ignore
  }
  return undefined;
}

/** @param {import("@minecraft/server").Vector3} a @param {import("@minecraft/server").Vector3} b @param {number} s */
const add = (a, b, s = 1) => ({ x: a.x + b.x * s, y: a.y + b.y * s, z: a.z + b.z * s });

/** @param {import("@minecraft/server").Player} player @param {string} msg */
function tell(player, msg) {
  try {
    player.sendMessage(msg);
  } catch {
    // player left
  }
}

/** @param {import("@minecraft/server").Dimension} dim @param {string} cmd */
function run(dim, cmd) {
  try {
    return dim.runCommand(cmd).successCount;
  } catch (e) {
    console.warn(`[Dinos&Dragons] command failed: ${cmd} -> ${e}`);
    return 0;
  }
}

// ---------------------------------------------------------------------------
// castle
// ---------------------------------------------------------------------------

const SKIP_GROUND = ["air", "leaves", "log", "wood", "vine", "short_grass", "tall_grass", "fern", "flower",
  "bush", "snow_layer", "water", "sapling", "mushroom", "dandelion", "poppy", "tulip", "orchid", "allium",
  "bluet", "daisy", "cornflower", "lily", "rose", "peony", "lilac", "kelp", "seagrass", "cactus", "reeds",
  "sugar_cane", "bamboo", "dripleaf", "azalea", "moss_carpet", "pumpkin", "melon", "sweet_berry", "petals",
  "leaf_litter", "dry_grass", "firefly"];

/**
 * Finds the natural ground height at x,z (ignores trees, plants and snow layers).
 * @param {import("@minecraft/server").Dimension} dim @param {number} x @param {number} z @param {number} startY
 */
function groundY(dim, x, z, startY) {
  for (let y = Math.min(startY + 24, 300); y > startY - 40; y--) {
    let block;
    try {
      block = dim.getBlock({ x, y, z });
    } catch {
      return undefined;
    }
    if (!block) return undefined;
    const id = block.typeId.replace("minecraft:", "");
    if (SKIP_GROUND.some((s) => id.includes(s))) continue;
    return y;
  }
  return undefined;
}

/** Median ground height around a point so the castle sits on the average terrain. */
function castleBaseY(/** @type {import("@minecraft/server").Dimension} */ dim, /** @type {number} */ cx,
  /** @type {number} */ cz, /** @type {number} */ startY) {
  const heights = [];
  for (const dx of [-16, 0, 16]) {
    for (const dz of [-16, 0, 16]) {
      const h = groundY(dim, cx + dx, cz + dz, startY);
      if (h !== undefined) heights.push(h);
    }
  }
  if (heights.length === 0) return Math.floor(startY) - 1;
  heights.sort((a, b) => a - b);
  return heights[Math.floor(heights.length / 2)];
}

/**
 * Builds the castle centred on (cx, cz). Calls done(origin) when finished.
 * @param {import("@minecraft/server").Dimension} dim
 * @param {number} cx @param {number} cz @param {number} startY
 * @param {(o: import("@minecraft/server").Vector3) => void} done
 */
function buildCastle(dim, cx, cz, startY, done) {
  building = true;
  const area = `${cx - 30} ${startY - 20} ${cz - 30} ${cx + 30} ${startY + 20} ${cz + 30}`;
  run(dim, `tickingarea remove dd_castle`);
  run(dim, `tickingarea add ${area} dd_castle`);
  let waited = 0;
  const wait = system.runInterval(() => {
    waited++;
    let loaded = true;
    for (const [dx, dz] of [[-29, -29], [29, -29], [-29, 29], [29, 29], [0, 0]]) {
      try {
        if (!dim.getBlock({ x: cx + dx, y: startY, z: cz + dz })) loaded = false;
      } catch {
        loaded = false;
      }
    }
    if (!loaded && waited < 200) return;
    system.clearRun(wait);
    const y = castleBaseY(dim, cx, cz, startY);
    const origin = { x: cx, y, z: cz };
    let part = 1;
    const step = system.runInterval(() => {
      run(dim, `execute positioned ${cx} ${y} ${cz} run function dd/castle/part_${part}`);
      part++;
      if (part > CASTLE_PARTS) {
        system.clearRun(step);
        run(dim, `tickingarea remove dd_castle`);
        building = false;
        done(origin);
      }
    }, 3);
  }, 5);
}

/** @param {import("@minecraft/server").Vector3} origin */
function spawnPointOf(origin) {
  return add(origin, SPAWN_OFFSET);
}

/** @param {import("@minecraft/server").Player} player @param {import("@minecraft/server").Vector3} origin */
function sendToCourtyard(player, origin) {
  const p = spawnPointOf(origin);
  player.teleport({ x: p.x + 0.5, y: p.y, z: p.z + 0.5 }, {
    dimension: world.getDimension("overworld"),
    facingLocation: { x: origin.x + 0.5, y: origin.y + 3, z: origin.z - 10 },
  });
}

/** @param {import("@minecraft/server").Player} player */
function buildSpawnCastle(player) {
  const dim = world.getDimension("overworld");
  const cx = Math.floor(player.location.x);
  const cz = Math.floor(player.location.z);
  world.setDynamicProperty(CASTLE_KEY, "building");
  player.onScreenDisplay.setTitle("§6Dinos & Dragons", { subtitle: "Building your castle...", fadeInDuration: 10, stayDuration: 60, fadeOutDuration: 20 });
  buildCastle(dim, cx, cz, Math.floor(player.location.y), (origin) => {
    world.setDynamicProperty(CASTLE_KEY, JSON.stringify(origin));
    world.setDefaultSpawnLocation(spawnPointOf(origin));
    for (const p of world.getAllPlayers()) {
      if (p.dimension.id === dim.id) sendToCourtyard(p, origin);
    }
    world.sendMessage("§6[Dinos & Dragons]§r Welcome to your castle! It is your spawn point - decorate it however you like.");
    world.sendMessage("§7Type §f/scriptevent dd:help§7 (cheats on) or read the Creature Guide below.");
    for (const p of world.getAllPlayers()) {
      p.onScreenDisplay.setTitle("§6Welcome home!", { subtitle: "Tame dragons and dinosaurs", fadeInDuration: 10, stayDuration: 60, fadeOutDuration: 20 });
    }
  });
}

// ---------------------------------------------------------------------------
// players joining
// ---------------------------------------------------------------------------

/** @param {import("@minecraft/server").Player} player */
function giveKit(player) {
  if (player.hasTag(KIT_TAG)) return;
  player.addTag(KIT_TAG);
  const inv = player.getComponent("minecraft:inventory")?.container;
  if (!inv) return;
  inv.addItem(new ItemStack("dd:dragon_horn", 1));
  inv.addItem(new ItemStack("minecraft:cooked_beef", 16));
  inv.addItem(new ItemStack("minecraft:wheat", 16));
  guide(player);
}

/** @param {import("@minecraft/server").Player} player */
function guide(player) {
  tell(player, "§6=== Creature Guide ===");
  for (const id of Object.keys(SPECIES)) {
    const s = SPECIES[/** @type {keyof typeof SPECIES} */ (id)];
    const food = s.tame.slice(0, 4).map((t) => t.replace(/_/g, " ")).join(", ");
    tell(player, `§e${s.name}§r - tame with: §a${food}`);
  }
  tell(player, "§7Feed a wild creature until hearts appear, then tap it to ride. Sneak + tap: stay / follow.");
  tell(player, "§7Dragons fly where you look; press jump to climb. Use the §fDragon Horn§7 while riding to breathe/roar.");
}

world.afterEvents.playerSpawn.subscribe((ev) => {
  if (!ev.initialSpawn) return;
  const player = ev.player;
  system.runTimeout(() => {
    if (!player.isValid) return;
    giveKit(player);
    const state = world.getDynamicProperty(CASTLE_KEY);
    if (state !== undefined || building) return;
    if (player.dimension.id !== "minecraft:overworld") return;
    if (world.getAbsoluteTime() < NEW_WORLD_TICKS) {
      buildSpawnCastle(player);
    } else {
      // Existing world: never bulldoze someone's base. Hand them a blueprint instead.
      world.setDynamicProperty(CASTLE_KEY, "skipped");
      player.getComponent("minecraft:inventory")?.container?.addItem(new ItemStack("dd:castle_blueprint", 1));
      tell(player, "§6[Dinos & Dragons]§r This world already existed, so no castle was built automatically.");
      tell(player, "§7Stand where you want it, then §fsneak + use the Castle Blueprint§7 (it clears a 57x57 area!).");
    }
  }, 40);
});

// ---------------------------------------------------------------------------
// Dragon Horn & Castle Blueprint
// ---------------------------------------------------------------------------

const BREATH = {
  fire: { particle: "dd:fire_breath", sound: "mob.blaze.shoot", range: 14 },
  frost: { particle: "dd:frost_breath", sound: "mob.snowgolem.shoot", range: 14 },
  spores: { particle: "dd:spore_breath", sound: "mob.blaze.breathe", range: 12 },
  storm: { particle: "dd:storm_breath", sound: "mob.ravager.roar", range: 16 },
};
const FRIENDLY = ["player", "villager", "wandering_trader", "irongolem", "inanimate"];

/**
 * @param {import("@minecraft/server").Player} player
 * @param {import("@minecraft/server").Entity} mount
 * @param {keyof typeof BREATH} kind
 */
function breathe(player, mount, kind) {
  const b = BREATH[kind];
  const dim = player.dimension;
  const dir = player.getViewDirection();
  const s = speciesOf(mount.typeId);
  const mouth = add(add(mount.location, { x: 0, y: (s?.height ?? 2) * 0.85, z: 0 }), dir, 2.5);
  for (let i = 0; i <= b.range; i += 1.5) {
    const p = add(mouth, dir, i);
    try {
      dim.spawnParticle(b.particle, p);
    } catch {
      break;
    }
  }
  dim.playSound(b.sound, mouth, { volume: 1.2, pitch: 0.8 });
  const targets = dim.getEntities({ location: add(mouth, dir, b.range / 2), maxDistance: b.range / 2 + 2, excludeFamilies: FRIENDLY });
  for (const e of targets) {
    if (!e.isValid || e.id === mount.id) continue;
    if (!e.getComponent("minecraft:health") || e.getComponent("minecraft:is_tamed")) continue;
    const to = { x: e.location.x - mouth.x, y: e.location.y + 0.8 - mouth.y, z: e.location.z - mouth.z };
    const len = Math.hypot(to.x, to.y, to.z) || 1;
    const dot = (to.x * dir.x + to.y * dir.y + to.z * dir.z) / len;
    if (dot < 0.8 || len > b.range + 1) continue; // ~37 degree cone
    try {
      if (kind === "fire") {
        e.setOnFire(6, true);
        e.applyDamage(7, { cause: EntityDamageCause.fire, damagingEntity: player });
      } else if (kind === "frost") {
        e.applyDamage(6, { cause: EntityDamageCause.freezing, damagingEntity: player });
        e.addEffect("slowness", 120, { amplifier: 3 });
      } else if (kind === "spores") {
        e.applyDamage(3, { cause: EntityDamageCause.magic, damagingEntity: player });
        e.addEffect("poison", 120, { amplifier: 1 });
      } else {
        e.applyDamage(9, { cause: EntityDamageCause.lightning, damagingEntity: player });
        e.applyKnockback({ x: dir.x * 1.6, z: dir.z * 1.6 }, 0.5);
      }
    } catch {
      // entity may have died mid-loop
    }
  }
}

/** @param {import("@minecraft/server").Player} player @param {import("@minecraft/server").Entity} mount */
function roar(player, mount) {
  const dim = player.dimension;
  const big = mount.typeId === "dd:trex" || mount.typeId === "dd:brachiosaurus";
  dim.playSound("mob.ravager.roar", mount.location, { volume: 2, pitch: big ? 0.7 : 1.2 });
  for (let a = 0; a < 360; a += 30) {
    const r = (a * Math.PI) / 180;
    try {
      dim.spawnParticle("dd:roar", add(mount.location, { x: Math.cos(r) * 2, y: 1.5, z: Math.sin(r) * 2 }));
    } catch {
      break;
    }
  }
  const radius = big ? 10 : 7;
  for (const e of dim.getEntities({ location: mount.location, maxDistance: radius, families: ["monster"] })) {
    const dx = e.location.x - mount.location.x;
    const dz = e.location.z - mount.location.z;
    const d = Math.hypot(dx, dz) || 1;
    try {
      e.applyKnockback({ x: (dx / d) * 2.2, z: (dz / d) * 2.2 }, 0.6);
      e.applyDamage(big ? 6 : 3, { cause: EntityDamageCause.entityAttack, damagingEntity: mount });
      e.addEffect("weakness", 160, { amplifier: 1 });
    } catch {
      // ignore
    }
  }
  if (!big) player.addEffect("speed", 100, { amplifier: 1, showParticles: false });
  mount.addEffect("speed", 100, { amplifier: 1, showParticles: false });
}

/** Horn on foot: every sitting creature you own within 64 blocks gets up and follows you. */
function callCreatures(/** @type {import("@minecraft/server").Player} */ player) {
  let n = 0;
  for (const e of player.dimension.getEntities({ location: player.location, maxDistance: 64, families: ["dd_creature"] })) {
    const tame = e.getComponent("minecraft:tameable");
    if (tame?.tamedToPlayerId !== player.id) continue;
    if (e.getProperty("dd:sitting") === true) {
      e.triggerEvent("dd:stand");
      n++;
    }
  }
  player.dimension.playSound("raid.horn", player.location, { volume: 0.6, pitch: 1.4 });
  tell(player, n > 0 ? `§aYour horn calls ${n} creature${n > 1 ? "s" : ""} to follow you.` : "§7Ride a dragon or dinosaur and use the horn to breathe or roar. On foot it calls your sitting creatures.");
}

/** @param {import("@minecraft/server").Player} player @param {import("@minecraft/server").ItemStack} item */
function onUse(player, item) {
  const now = system.currentTick;
  const last = hornCooldown.get(player.id) ?? -100;
  if (item.typeId === "dd:dragon_horn") {
    if (now - last < 16) return;
    hornCooldown.set(player.id, now);
    const mount = mountOf(player);
    if (!mount) return callCreatures(player);
    const s = speciesOf(mount.typeId);
    if (s?.kind === "dragon" && s.breath && s.breath in BREATH) {
      breathe(player, mount, /** @type {keyof typeof BREATH} */ (s.breath));
    } else {
      roar(player, mount);
    }
  } else if (item.typeId === "dd:castle_blueprint") {
    if (now - last < 40 || building) return;
    hornCooldown.set(player.id, now);
    if (!player.isSneaking) {
      tell(player, "§eSneak and use the blueprint to build a castle centred where you stand. It clears a 57x57 area!");
      return;
    }
    if (player.dimension.id !== "minecraft:overworld") {
      tell(player, "§cCastles can only be built in the Overworld.");
      return;
    }
    const inv = player.getComponent("minecraft:inventory")?.container;
    if (inv && player.getGameMode() !== GameMode.Creative) {
      const slot = player.selectedSlotIndex;
      const held = inv.getItem(slot);
      if (held?.typeId === "dd:castle_blueprint") {
        if (held.amount > 1) {
          held.amount -= 1;
          inv.setItem(slot, held);
        } else {
          inv.setItem(slot, undefined);
        }
      }
    }
    buildSpawnCastle(player);
  }
}

world.afterEvents.itemUse.subscribe((ev) => onUse(ev.source, ev.itemStack));
world.afterEvents.itemStartUse.subscribe((ev) => onUse(ev.source, ev.itemStack));

// ---------------------------------------------------------------------------
// riding upkeep
// ---------------------------------------------------------------------------

system.runInterval(() => {
  // Keep the dragons' "ridden" state in sync even if a mount/dismount event was missed.
  for (const dimId of ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"]) {
    let dragons;
    try {
      dragons = world.getDimension(dimId).getEntities({ families: ["dragon"] });
    } catch {
      continue;
    }
    for (const d of dragons) {
      try {
        const rideable = d.getComponent("minecraft:rideable");
        const ridden = (rideable?.getRiders().length ?? 0) > 0;
        const flag = d.getProperty("dd:ridden") === true;
        if (ridden && !flag) d.triggerEvent("dd:mounted");
        else if (!ridden && flag) d.triggerEvent("dd:dismounted");
      } catch {
        // unloaded
      }
    }
  }
}, 10);

system.runInterval(() => {
  for (const player of world.getAllPlayers()) {
    const mount = mountOf(player);
    const onDragon = !!mount && speciesOf(mount.typeId)?.kind === "dragon";
    if (!onDragon && wasRidingDragon.get(player.id) && !player.isOnGround) {
      player.addEffect("slow_falling", 200, { showParticles: false });
    }
    wasRidingDragon.set(player.id, onDragon);
  }
}, 2);

world.afterEvents.playerLeave.subscribe((ev) => {
  wasRidingDragon.delete(ev.playerId);
  hornCooldown.delete(ev.playerId);
});

// ---------------------------------------------------------------------------
// /scriptevent commands
// ---------------------------------------------------------------------------

system.afterEvents.scriptEventReceive.subscribe((ev) => {
  const player = ev.sourceEntity;
  if (!player || player.typeId !== "minecraft:player") return;
  const p = /** @type {import("@minecraft/server").Player} */ (player);
  switch (ev.id) {
    case "dd:castle":
      if (building) return tell(p, "§eA castle is already being built.");
      buildSpawnCastle(p);
      break;
    case "dd:setspawn": {
      const loc = { x: Math.floor(p.location.x), y: Math.floor(p.location.y), z: Math.floor(p.location.z) };
      world.setDefaultSpawnLocation(loc);
      tell(p, `§aWorld spawn set to ${loc.x} ${loc.y} ${loc.z}.`);
      break;
    }
    case "dd:spawn_all": {
      let i = 0;
      for (const id of Object.keys(SPECIES)) {
        const a = (i++ / Object.keys(SPECIES).length) * Math.PI * 2;
        p.dimension.spawnEntity(`dd:${id}`, { x: p.location.x + Math.cos(a) * 12, y: p.location.y + 1, z: p.location.z + Math.sin(a) * 12 });
      }
      break;
    }
    case "dd:help":
      guide(p);
      tell(p, "§7Commands: /scriptevent dd:castle (build here), dd:setspawn, dd:spawn_all, dd:help");
      break;
  }
});
