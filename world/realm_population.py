"""
Realm-Wide Population & Faction Territory Enforcement System for 'rop'
=======================================================================

A production-grade population and zone-validation engine that:

  1. Explicitly maps the Aethelgard Alliance (Good) territories and the
     Gorgoroth Horde (Evil) territories to their room/zone boundaries,
     including the true 1-10 starter leveling zones (``sunspire_meadows``
     for Good and ``brimstone_courtyard`` for Evil).

  2. Removes or corrects misaligned spawns (e.g. Evil mobs orphaned in
     Sunspire Meadows, Good mobs scattered through Gorgoroth).

  3. Populates every zone with level-appropriate XP mobs by looping room
     tags attached by ``world.builder_phase1``.

  4. Places low-level vendors/trainers in both newbie zones and full
     vendor/guildmaster service hubs in both faction cities.

  5. Places all 30 registered bosses into their correct lairs with long
     respawn timers, faction alignment, XP/gold, and boss loot hooks.

  6. Provides a reusable verification engine (``world.realm_verify``) that
     walks the room graph from every starting hub.

Usage (evennia shell):

    import world.realm_population as rp
    rp.populate_realm()

    # Or run the dry verification report:
    import world.realm_verify as rv
    print(rv.verify_realm()["report"])

The same operations are available in-game via ``@verifyrealm`` and
``@populaterealm`` (see ``commands/realm_admin.py``).
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from evennia import create_object, search_object, search_tag
from evennia.utils.ansi import strip_ansi

import world.builder_phase1 as b1
import world.boss_registry as boss_registry


# ---------------------------------------------------------------------------
# Faction constants
# ---------------------------------------------------------------------------

FACTION_GOOD = "Aethelgard Alliance"
FACTION_EVIL = "Gorgoroth Horde"
FACTION_NEUTRAL = "Neutral"

ALIGNMENT_GOOD = "Good"
ALIGNMENT_EVIL = "Evil"
ALIGNMENT_NEUTRAL = "Neutral"


# ---------------------------------------------------------------------------
# Territory map — explicit boundaries/rooms
# ---------------------------------------------------------------------------

# Zone keys from builder_phase1 (the authoritative room builder).
GOOD_ZONES: set = set(b1.GOOD_ZONES.keys())
EVIL_ZONES: set = set(b1.EVIL_ZONES.keys())
NEUTRAL_ZONES: set = set(b1.NEUTRAL_ZONES.keys())
ALL_ZONES: set = GOOD_ZONES | EVIL_ZONES | NEUTRAL_ZONES

# True 1-10 leveling zones.
GOOD_STARTER_ZONES = {"sunspire_meadows"}
EVIL_STARTER_ZONES = {"brimstone_courtyard"}

# Faction city hub rooms (created by world.faction_starter).
GOOD_HUB_ROOMS = [
    "Aethelgard - Shrine of Light",
    "Aethelgard - The Grand Sanctum",
]
EVIL_HUB_ROOMS = [
    "Gorgoroth - Dark Temple",
    "Gorgoroth - The Blood Forge",
]

# Town names derived from builder_phase1. Each town is anchored to a hub
# room keyed by "<Town Name> (Town Center)".
GOOD_TOWNS = [name for _key, name in b1.GOOD_TOWNS]
EVIL_TOWNS = [name for _key, name in b1.EVIL_TOWNS]


FACTION_TERRITORIES: Dict[str, Dict[str, Any]] = {
    FACTION_GOOD: {
        "alignment": ALIGNMENT_GOOD,
        "zones": GOOD_ZONES,
        "starter_zones": GOOD_STARTER_ZONES,
        "towns": GOOD_TOWNS,
        "hubs": GOOD_HUB_ROOMS,
    },
    FACTION_EVIL: {
        "alignment": ALIGNMENT_EVIL,
        "zones": EVIL_ZONES,
        "starter_zones": EVIL_STARTER_ZONES,
        "towns": EVIL_TOWNS,
        "hubs": EVIL_HUB_ROOMS,
    },
    FACTION_NEUTRAL: {
        "alignment": ALIGNMENT_NEUTRAL,
        "zones": NEUTRAL_ZONES,
        "starter_zones": set(),
        "towns": [],
        "hubs": [],
    },
}


def faction_for_zone(zone_key: str) -> str:
    """Return the owning faction tag for a zone key."""
    if zone_key in GOOD_ZONES:
        return FACTION_GOOD
    if zone_key in EVIL_ZONES:
        return FACTION_EVIL
    if zone_key in NEUTRAL_ZONES:
        return FACTION_NEUTRAL
    return FACTION_NEUTRAL


def alignment_for_faction(faction: str) -> str:
    """Map a faction name to its alignment label."""
    return FACTION_TERRITORIES.get(faction, {}).get("alignment", ALIGNMENT_NEUTRAL)


def is_starter_zone(zone_key: str) -> bool:
    return zone_key in GOOD_STARTER_ZONES or zone_key in EVIL_STARTER_ZONES


# ---------------------------------------------------------------------------
# Danger / density helpers
# ---------------------------------------------------------------------------

def danger_for_range(level_min: int, level_max: int) -> str:
    """Derive a danger label from a zone level band."""
    if level_max <= 10:
        return "safe"
    if level_max <= 18:
        return "caution"
    if level_max <= 40:
        return "danger"
    return "deadly"


def mobs_per_room(level_min: int, level_max: int) -> Tuple[int, int]:
    """
    Return (min, max) mobs per room for a level band.

    Starter zones get a slightly denser floor to support newbie grinding.
    """
    danger = danger_for_range(level_min, level_max)
    if danger == "safe":
        return (2, 3)
    if danger == "caution":
        return (2, 3)
    if danger == "danger":
        return (3, 4)
    return (4, 6)  # deadly


# ---------------------------------------------------------------------------
# Faction mob pools (level bands)
# ---------------------------------------------------------------------------

def _band_for_range(level_min: int, level_max: int) -> int:
    if level_max <= 10:
        return 1
    if level_max <= 18:
        return 2
    if level_max <= 40:
        return 3
    if level_max <= 60:
        return 4
    return 5


GOOD_MOB_POOLS: Dict[int, List[Dict[str, Any]]] = {
    1: [
        {"name": "Prairie Fox", "level": 2, "aggro": False, "damage_type": "pierce"},
        {"name": "Wandering Fawn", "level": 4, "aggro": False, "damage_type": "blunt"},
        {"name": "Timber Stag", "level": 3, "aggro": False, "damage_type": "blunt"},
        {"name": "Meadow Rabbit", "level": 1, "aggro": False, "damage_type": "blunt"},
        {"name": "Farmhand", "level": 2, "aggro": False, "damage_type": "slash"},
        {"name": "Young Boar", "level": 5, "aggro": True, "damage_type": "pierce"},
        {"name": "Militia Scout", "level": 4, "aggro": False, "damage_type": "pierce"},
        {"name": "Aethelgard Acolyte", "level": 6, "aggro": False, "damage_type": "blunt"},
        {"name": "Stray Hound", "level": 3, "aggro": False, "damage_type": "pierce"},
        {"name": "Hill Fox", "level": 2, "aggro": False, "damage_type": "pierce"},
    ],
    2: [
        {"name": "Highway Bandit", "level": 12, "aggro": True, "damage_type": "slash"},
        {"name": "Highland Wolf", "level": 14, "aggro": True, "damage_type": "pierce"},
        {"name": "Hill Brigand", "level": 11, "aggro": True, "damage_type": "slash"},
        {"name": "Cave Bat", "level": 10, "aggro": False, "damage_type": "pierce"},
        {"name": "Forest Thief", "level": 12, "aggro": True, "damage_type": "pierce"},
        {"name": "Stonewatch Recruit", "level": 16, "aggro": False, "damage_type": "slash"},
    ],
    3: [
        {"name": "Highland Bear", "level": 20, "aggro": True, "damage_type": "slash"},
        {"name": "Silverpine Stalker", "level": 25, "aggro": True, "damage_type": "pierce"},
        {"name": "Stoneguard Miner", "level": 28, "aggro": False, "damage_type": "blunt"},
        {"name": "Golden Plains Lion", "level": 30, "aggro": True, "damage_type": "pierce"},
        {"name": "Vale Wraith", "level": 35, "aggro": True, "damage_type": "magic_shadow"},
        {"name": "Mistveil Panther", "level": 33, "aggro": True, "damage_type": "pierce"},
    ],
    4: [
        {"name": "Iron-Bark Treant", "level": 45, "aggro": True, "damage_type": "blunt"},
        {"name": "Storm Roc", "level": 50, "aggro": True, "damage_type": "slash"},
        {"name": "Granite Guardian", "level": 55, "aggro": True, "damage_type": "blunt"},
        {"name": "Serpent Broodmother", "level": 48, "aggro": True, "damage_type": "pierce"},
    ],
    5: [
        {"name": "Celestial Warden", "level": 65, "aggro": True, "damage_type": "magic_fire"},
        {"name": "Dawn Titan", "level": 70, "aggro": True, "damage_type": "blunt"},
        {"name": "Astral Devourer", "level": 75, "aggro": True, "damage_type": "magic_shadow"},
        {"name": "Sunforged Colossus", "level": 80, "aggro": True, "damage_type": "magic_fire"},
    ],
}

EVIL_MOB_POOLS: Dict[int, List[Dict[str, Any]]] = {
    1: [
        {"name": "Blood Imp", "level": 1, "aggro": False, "damage_type": "pierce"},
        {"name": "Imp Hatchling", "level": 2, "aggro": False, "damage_type": "slash"},
        {"name": "Corrupted Peasant", "level": 2, "aggro": True, "damage_type": "slash"},
        {"name": "Goblin Scout", "level": 2, "aggro": True, "damage_type": "pierce"},
        {"name": "Demon Imp", "level": 3, "aggro": True, "damage_type": "pierce"},
        {"name": "Skeletal Servant", "level": 4, "aggro": True, "damage_type": "slash"},
        {"name": "Lesser Hellhound", "level": 5, "aggro": True, "damage_type": "pierce"},
        {"name": "Dark Acolyte", "level": 6, "aggro": True, "damage_type": "magic_shadow"},
        {"name": "Fetid Zombie", "level": 7, "aggro": True, "damage_type": "blunt"},
    ],
    2: [
        {"name": "Skeletal Warrior", "level": 12, "aggro": True, "damage_type": "slash"},
        {"name": "Bone Archer", "level": 14, "aggro": True, "damage_type": "pierce"},
        {"name": "Hellhound", "level": 11, "aggro": True, "damage_type": "pierce"},
        {"name": "Infernal Cultist", "level": 16, "aggro": True, "damage_type": "magic_shadow"},
        {"name": "Cave Stalker", "level": 13, "aggro": True, "damage_type": "pierce"},
    ],
    3: [
        {"name": "Pit Demon", "level": 25, "aggro": True, "damage_type": "slash"},
        {"name": "Shadow Stalker", "level": 28, "aggro": True, "damage_type": "pierce"},
        {"name": "Undead Knight", "level": 30, "aggro": True, "damage_type": "slash"},
        {"name": "Wraith", "level": 35, "aggro": True, "damage_type": "magic_shadow"},
        {"name": "Bone Golem", "level": 33, "aggro": True, "damage_type": "blunt"},
    ],
    4: [
        {"name": "Frost Giant", "level": 45, "aggro": True, "damage_type": "blunt"},
        {"name": "Dread Knight", "level": 50, "aggro": True, "damage_type": "slash"},
        {"name": "Necrotic Abomination", "level": 48, "aggro": True, "damage_type": "blunt"},
        {"name": "Abyssal Horror", "level": 55, "aggro": True, "damage_type": "magic_shadow"},
    ],
    5: [
        {"name": "Nether Reaver", "level": 65, "aggro": True, "damage_type": "magic_shadow"},
        {"name": "Void Behemoth", "level": 70, "aggro": True, "damage_type": "blunt"},
        {"name": "Hellfire Colossus", "level": 75, "aggro": True, "damage_type": "magic_fire"},
        {"name": "Doom Wyrm", "level": 80, "aggro": True, "damage_type": "magic_fire"},
    ],
}

NEUTRAL_MOB_POOLS: Dict[str, List[Dict[str, Any]]] = {
    # Scorched desert — Great Sun Wastes (25-40)
    "great_sun_wastes": [
        {"name": "Desert Camel", "level": 25, "aggro": False, "damage_type": "blunt"},
        {"name": "Dune Scorpion", "level": 28, "aggro": True, "damage_type": "pierce"},
        {"name": "Skeletal Nomad", "level": 30, "aggro": True, "damage_type": "slash"},
        {"name": "Sand Wyrm", "level": 35, "aggro": True, "damage_type": "pierce"},
        {"name": "Dust Wraith", "level": 38, "aggro": True, "damage_type": "magic_shadow"},
    ],
    # Northern Ancient Forest (20-35)
    "northern_ancient_forest": [
        {"name": "Timber Wolf", "level": 22, "aggro": True, "damage_type": "pierce"},
        {"name": "Giant Owl", "level": 25, "aggro": False, "damage_type": "pierce"},
        {"name": "Shadow Panther", "level": 28, "aggro": True, "damage_type": "pierce"},
        {"name": "Corrupted Treant", "level": 30, "aggro": True, "damage_type": "blunt"},
        {"name": "Forest Witch", "level": 33, "aggro": True, "damage_type": "magic_shadow"},
    ],
    # South Shore Coastal Wastes (35-50)
    "south_shore": [
        {"name": "Drowned Sailor", "level": 35, "aggro": True, "damage_type": "slash"},
        {"name": "Coral Guardian", "level": 38, "aggro": False, "damage_type": "blunt"},
        {"name": "Kraken Spawn", "level": 40, "aggro": True, "damage_type": "pierce"},
        {"name": "Tide Wraith", "level": 45, "aggro": True, "damage_type": "magic_shadow"},
        {"name": "Sea Drake", "level": 48, "aggro": True, "damage_type": "pierce"},
    ],
}


def mob_pool_for_zone(zone_key: str, level_min: int, level_max: int) -> List[Dict[str, Any]]:
    """Return the mob pool used to populate a zone."""
    if zone_key in NEUTRAL_ZONES:
        return NEUTRAL_MOB_POOLS.get(zone_key, NEUTRAL_MOB_POOLS["great_sun_wastes"])
    band = _band_for_range(level_min, level_max)
    if zone_key in GOOD_ZONES:
        return GOOD_MOB_POOLS[band]
    return EVIL_MOB_POOLS[band]


# ---------------------------------------------------------------------------
# Mob stat derivation
# ---------------------------------------------------------------------------

def derive_stats(level: int) -> Dict[str, int]:
    """Return a six-stat block scaled from a mob level."""
    base = 7 + level
    return {
        "str": base,
        "dex": base + 1,
        "con": base,
        "int": max(3, base - 6),
        "wis": max(3, base - 4),
        "cha": max(2, base - 8),
    }


def derive_hp(level: int) -> int:
    """
    Derive max HP for a mob from its level.

    Classic MajorMUD-style curve: low-level mobs have modest HP.
    Level 1=13, 2=18, 3=23, 5=33, 10=58, 20=108, 50=258, 80=408.
    """
    level = max(1, int(level))
    return 8 + (level * 5)


def derive_xp(level: int) -> int:
    """
    Derive XP value for a mob from its level.

    Early levels give proportionally more XP to smooth the newbie experience.
    Level 1=25, 2=30, 5=55, 10=120, 20=280, 50=900, 80=1600.
    """
    level = max(1, int(level))
    # Base: 20 + (level * 5) for early levels, scaling up
    if level <= 10:
        return 20 + (level * 5)
    elif level <= 30:
        return 70 + (level * 7)
    elif level <= 60:
        return 280 + (level * 10)
    else:
        return 880 + (level * 12)


def derive_gold(level: int) -> Tuple[int, int]:
    return (level // 2, level * 2)


def default_loot_table(faction: str, level: int) -> List[Dict[str, Any]]:
    """Return a sensible loot table for mobs created procedurally."""
    loot = []
    if level <= 15:
        loot.append({"item_key": "travel_rations", "weight": 0.25, "min_qty": 1, "max_qty": 1})
        loot.append({"item_key": "health_potion", "weight": 0.10, "min_qty": 1, "max_qty": 1})
    else:
        loot.append({"item_key": "health_potion", "weight": 0.20, "min_qty": 1, "max_qty": 2})
        loot.append({"item_key": "mana_potion", "weight": 0.10, "min_qty": 1, "max_qty": 1})

    if faction == FACTION_GOOD:
        loot.append({"item_key": "iron_sword", "weight": 0.06, "min_qty": 1, "max_qty": 1})
        loot.append({"item_key": "leather_armor", "weight": 0.05, "min_qty": 1, "max_qty": 1})
    elif faction == FACTION_EVIL:
        loot.append({"item_key": "iron_dagger", "weight": 0.07, "min_qty": 1, "max_qty": 1})
        loot.append({"item_key": "cloth_robes", "weight": 0.05, "min_qty": 1, "max_qty": 1})
    return loot


def respawn_for_level(level: int) -> int:
    """Respawn delay in seconds; longer-lived as mobs get stronger."""
    if level <= 10:
        return 45
    if level <= 18:
        return 60
    if level <= 40:
        return 90
    return 120


# ---------------------------------------------------------------------------
# Mob / NPC creation primitives
# ---------------------------------------------------------------------------

def create_realm_mob(
    room: Any,
    name: str,
    faction: str,
    level: int,
    aggro: bool,
    damage_type: str = "slash",
    *,
    home: Optional[Any] = None,
    respawn_delay: Optional[int] = None,
    is_boss: bool = False,
    boss_id: Optional[str] = None,
    xp_value: Optional[int] = None,
    gold: Optional[Tuple[int, int]] = None,
    extra_attrs: Optional[List[Tuple[str, Any]]] = None,
) -> Optional[Any]:
    """
    Create a fully-realized ``typeclasses.mobs.Mob`` in ``room``.

    The mob receives ``mob_ai`` (disposition derived from ``aggro``),
    scaled stats, HP, XP, gold, a loot table, and a home room so the
    built-in death/respawn lifecycle works.
    """
    from world.mob_ai import MobAIData, MobDisposition

    if room is None:
        return None

    alignment = alignment_for_faction(faction)
    level = max(1, level)
    stats = derive_stats(level)
    hp = derive_hp(level)
    disposition = MobDisposition.AGGRESSIVE if aggro else MobDisposition.NEUTRAL
    mob_ai = MobAIData(
        disposition=disposition,
        aggro_radius=0,
        assist_faction=faction,
        level_threshold=8,
    )

    # --- Phase 5: Rare/Elite spawn variant ---
    spawn_tier = "normal"
    if not is_boss and level >= 5:
        try:
            from world.mob_ai import determine_spawn_tier, apply_spawn_tier
            spawn_tier = determine_spawn_tier(level, is_boss=is_boss)
            if spawn_tier != "normal":
                name, stats, hp, xp_val, gold_min_val, gold_max_val = apply_spawn_tier(
                    name, dict(stats), hp,
                    xp_value if xp_value is not None else derive_xp(level),
                    (gold or derive_gold(level))[0],
                    (gold or derive_gold(level))[1],
                    spawn_tier,
                )
                xp_value = xp_val
                gold = (gold_min_val, gold_max_val)
        except Exception:
            spawn_tier = "normal"

    # --- Phase 5: Spell list assignment based on mob name/type ---
    spell_list = []
    mana_pool = 0
    max_mana = 0
    cast_chance = 0.0
    try:
        from world.mob_ai import guess_mob_type_from_name, get_mob_spell_list, get_mob_mana_pool
        mob_type = guess_mob_type_from_name(name)
        spell_list = get_mob_spell_list(mob_type, level)
        mana_pool = get_mob_mana_pool(mob_type, level)
        max_mana = mana_pool
        if spell_list:
            cast_chance = 0.25  # 25% chance to cast per round for spellcasting mobs
    except Exception:
        pass

    # --- Phase 5: Assign combat class for skill usage ---
    mob_class_for_skills = "warrior"
    try:
        from world.mob_ai import MOB_COMBAT_SKILLS
        name_lower = name.lower() if name else ""
        if any(kw in name_lower for kw in ["guard", "sentinel", "knight", "warrior"]):
            mob_class_for_skills = "warrior"
        elif any(kw in name_lower for kw in ["ogre", "giant", "troll", "brute", "behemoth", "colossus"]):
            mob_class_for_skills = "brute"
        elif any(kw in name_lower for kw in ["rogue", "thief", "assassin", "stalker", "scout"]):
            mob_class_for_skills = "rogue"
        elif any(kw in name_lower for kw in ["monk", "acolyte"]):
            mob_class_for_skills = "monk"
    except Exception:
        pass

    # --- Phase 5: Determine flee chance based on mob type ---
    flee_chance = 0.0
    morale_threshold = 0.20
    if not is_boss and aggro:
        name_lower = name.lower() if name else ""
        # Cowardly mobs (weak creatures) are more likely to flee
        if any(kw in name_lower for kw in ["imp", "goblin", "rat", "bat", "fox", "rabbit"]):
            flee_chance = 0.50
            morale_threshold = 0.30
        elif any(kw in name_lower for kw in ["bandit", "thief", "scout"]):
            flee_chance = 0.35
            morale_threshold = 0.25

    # Build the MobAIData with Phase 5 fields
    mob_ai = MobAIData(
        disposition=disposition,
        aggro_radius=0,
        assist_faction=faction,
        level_threshold=8,
        spell_list=spell_list,
        cast_chance=cast_chance,
        mana_pool=mana_pool,
        max_mana=max_mana,
        mana_regen_per_tick=max(1, max_mana // 20) if max_mana > 0 else 0,
        morale_threshold=morale_threshold,
        flee_chance=flee_chance,
        aggro_other_mobs=aggro and faction in (FACTION_GOOD, FACTION_EVIL),
    )

    attrs: List[Tuple[str, Any]] = [
        ("is_mob", True),
        ("level", level),
        ("stats", stats),
        ("hp", hp),
        ("max_hp", hp),
        ("alignment", alignment),
        ("faction", faction),
        ("xp_value", xp_value if xp_value is not None else derive_xp(level)),
        ("gold_min", (gold or derive_gold(level))[0]),
        ("gold_max", (gold or derive_gold(level))[1]),
        ("damage_type", damage_type),
        ("is_aggro", aggro),
        ("mob_ai", mob_ai),
        ("loot_table", default_loot_table(faction, level)),
        ("home_room_dbref", home.id if home is not None else room.id),
        ("respawn_delay", respawn_delay if respawn_delay is not None else respawn_for_level(level)),
        ("class", mob_class_for_skills),
    ]
    if spawn_tier != "normal":
        attrs.append(("spawn_tier", spawn_tier))
    if is_boss:
        attrs.append(("is_boss", True))
    if boss_id:
        attrs.append(("boss_id", boss_id))
    if extra_attrs:
        attrs.extend(extra_attrs)

    try:
        mob = create_object(
            "typeclasses.mobs.Mob",
            key=name,
            location=room,
            attributes=attrs,
        )
        mob.tags.add("realm_mob", category="spawn")
        mob._start_ai_ticker()

        # ---- Zone scaling enforcement ----
        try:
            from world.zone_scaling import scale_mob_to_zone
            scale_mob_to_zone(mob, room)
        except Exception:
            pass

        # ---- Procedural equipment assignment ----
        try:
            from world.mob_equipment import equip_mob
            equip_mob(mob, mob_class="Warrior", faction=faction, equip_chance=0.6)
        except Exception:
            pass

        return mob
    except Exception:
        return None


def create_faction_guard(room: Any, faction: str, level: int = 25) -> Optional[Any]:
    """Create a town/starter guard NPC (non-hostile, but territorial)."""
    from world.mob_ai import MobAIData, MobDisposition

    alignment = alignment_for_faction(faction)
    title = "Aethelgard Guard" if faction == FACTION_GOOD else "Gorgoroth Sentinel"
    stats = derive_stats(level)
    hp = derive_hp(level)
    mob_ai = MobAIData(
        disposition=MobDisposition.NEUTRAL,
        aggro_radius=0,
        assist_faction=faction,
        level_threshold=8,
    )
    attrs = [
        ("is_mob", True),
        ("is_npc", True),
        ("level", level),
        ("stats", stats),
        ("hp", hp),
        ("max_hp", hp),
        ("alignment", alignment),
        ("faction", faction),
        ("is_aggro", False),
        ("mob_ai", mob_ai),
        ("xp_value", derive_xp(level)),
        ("gold_min", 5),
        ("gold_max", 20),
        ("damage_type", "slash" if faction == FACTION_GOOD else "blunt"),
        ("home_room_dbref", room.id),
        ("respawn_delay", 120),
    ]
    try:
        guard = create_object("typeclasses.mobs.Mob", key=title, location=room, attributes=attrs)
        guard.tags.add("realm_mob", category="spawn")
        guard._start_ai_ticker()
        return guard
    except Exception:
        return None


def create_vendor(room: Any, faction: str) -> Optional[Any]:
    """Create a generic faction vendor NPC in a room."""
    vendor_name = "Marta the Peddler" if faction == FACTION_GOOD else "Grimm the Scavenger"
    try:
        vendor = create_object(
            "typeclasses.objects.Object",
            key=vendor_name,
            location=room,
            attributes=[
                ("desc", f"{vendor_name} offers goods to travellers of {faction}."),
                ("is_npc", True),
                ("is_vendor", True),
                ("vendor_type", "general"),
                ("faction", faction),
                ("alignment", alignment_for_faction(faction)),
            ],
        )
        return vendor
    except Exception:
        return None


def create_trainer(room: Any, faction: str) -> Optional[Any]:
    """Create a generic faction trainer NPC in a room."""
    trainer_name = "Good Spell Trainer" if faction == FACTION_GOOD else "Evil Spell Trainer"
    try:
        trainer = create_object(
            "typeclasses.objects.Object",
            key=trainer_name,
            location=room,
            attributes=[
                ("desc", f"{trainer_name} instructs new adepts of {faction}."),
                ("is_npc", True),
                ("is_trainer", True),
                ("trainer_type", "spells"),
                ("faction", faction),
                ("alignment", alignment_for_faction(faction)),
                ("available_spells", ["sparks", "minorheal", "arcanedart", "stoneskin", "frostsnap"]),
                ("trainer_gold_cost", 0),
            ],
        )
        return trainer
    except Exception:
        return None


def create_guildmaster(room: Any, faction: str, guild_class: str, level: int = 30) -> Optional[Any]:
    """
    Create a proper GuildmasterNPC in a room for mid/high-level training.

    Guildmasters use the practice-point system (CmdTrain/CmdLearn/CmdPractice)
    and can teach spells and combat skills appropriate to the character's level.
    """
    from world.guildmaster import GuildmasterNPC

    # Class-specific naming and descriptions
    guildmaster_config = {
        "Warrior": {
            "good_name": "Warmaster Gorath",
            "evil_name": "Blade-Lord Krag",
            "desc_good": "A battle-hardened veteran whose scarred plate armour tells a thousand tales of war.",
            "desc_evil": "A brutal warlord whose jagged armour is stained with the blood of countless foes.",
        },
        "Paladin": {
            "good_name": "Sir Aldric the Pure",
            "evil_name": "Fallen Crusader Morvain",
            "desc_good": "A noble knight whose gleaming armour radiates holy conviction.",
            "desc_evil": "A twisted paladin whose once-holy aura now burns with dark fervour.",
        },
        "Cleric": {
            "good_name": "High Priestess Seraphina",
            "evil_name": "Shadow Pontiff Malachar",
            "desc_good": "A serene priestess whose gentle hands channel divine radiance.",
            "desc_evil": "A gaunt pontiff whose whispered prayers call forth unholy power.",
        },
        "Mage": {
            "good_name": "Archmage Merdion",
            "evil_name": "Sorcerer-Lord Vex",
            "desc_good": "A wizened archmage whose eyes crackle with arcane energy.",
            "desc_evil": "A cold-eyed sorcerer wreathed in tendrils of shadow-magic.",
        },
        "Rogue": {
            "good_name": "Shadowmaster Theron",
            "evil_name": "Guildmaster Shade",
            "desc_good": "A lithe figure who moves with the silence of a passing breeze.",
            "desc_evil": "A hooded killer whose very presence seems to dim the light.",
        },
        "Warlock": {
            "good_name": "Cult-Mistress Vexia",
            "evil_name": "Demon-Binder Azgoth",
            "desc_good": "A mysterious woman whose pact with darker powers serves the Light.",
            "desc_evil": "A scarred warlock whose flesh writhes with bound demonic essence.",
        },
        "Druid": {
            "good_name": "Elder Thornwood",
            "evil_name": "Blight-Druid Rotbark",
            "desc_good": "An ancient druid whose beard is woven with living ivy and moss.",
            "desc_evil": "A corrupted nature-priest whose touch withers all that grows.",
        },
        "Ranger": {
            "good_name": "Pathfinder Elara",
            "evil_name": "Darkwood Stalker",
            "desc_good": "A keen-eyed ranger whose bow has never missed its mark.",
            "desc_evil": "A silent hunter who tracks prey through the darkest wilds.",
        },
        "Monk": {
            "good_name": "Grandmaster Shen",
            "evil_name": "Fist of the Abyss",
            "desc_good": "A serene monk whose every movement flows like water.",
            "desc_evil": "A brutal pugilist whose fists are wrapped in chains of black iron.",
        },
        "Necromancer": {
            "good_name": "Bone-Lord Morath",
            "evil_name": "Lich-King Vorlag",
            "desc_good": "A sombre scholar who commands the dead to serve the living.",
            "desc_evil": "A skeletal lich whose eye-sockets burn with cold blue flame.",
        },
    }

    cfg = guildmaster_config.get(guild_class, guildmaster_config["Warrior"])
    is_good = faction == FACTION_GOOD
    name = cfg["good_name"] if is_good else cfg["evil_name"]
    desc = cfg["desc_good"] if is_good else cfg["desc_evil"]

    try:
        gm = create_object(
            "world.guildmaster.GuildmasterNPC",
            key=name,
            location=room,
            attributes=[
                ("desc", f"{name} stands here, ready to train those who prove worthy. {desc}"),
                ("is_npc", True),
                ("is_trainer", True),
                ("is_guildmaster", True),
                ("guild_class", guild_class),
                ("faction", faction),
                ("alignment", alignment_for_faction(faction)),
                ("level", level),
                ("trainer_type", "guildmaster"),
            ],
        )
        return gm
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Guildmaster placement in mid/high-level zones
# ---------------------------------------------------------------------------

# Map each faction town to a recommended guildmaster class based on theme.
TOWN_GUILDMASTER_MAP: Dict[str, List[str]] = {
    # Good towns
    "Adaar Haven (The Desert Gate)": ["Warrior", "Ranger"],
    "Havencrest": ["Cleric", "Paladin"],
    "Sunspire Keep (Starter Hub)": ["Warrior", "Cleric", "Mage", "Rogue"],
    "Silverwood Village": ["Druid", "Ranger"],
    "Oakhaven": ["Druid", "Monk"],
    "Stoneguard Hold": ["Warrior", "Paladin"],
    "Dawn-Light Bay": ["Cleric", "Mage"],
    "Riverbend": ["Rogue", "Ranger"],
    "High-Meadow": ["Druid", "Monk"],
    "Astraea Sanctuary": ["Paladin", "Cleric"],
    "Eldergrove": ["Druid", "Mage"],
    "Vales-End": ["Warrior", "Rogue"],
    "Iron-Watch Castle": ["Paladin", "Warrior"],
    # Evil towns
    "Duradune (The Desert Gate)": ["Warrior", "Warlock"],
    "Freshwater Springs": ["Necromancer", "Rogue"],
    "Drow Caverns City": ["Rogue", "Warlock"],
    "Brimstone Keep (Starter Hub)": ["Warrior", "Warlock", "Necromancer", "Rogue"],
    "Gloomhold": ["Necromancer", "Warlock"],
    "Rotwood Enclave": ["Druid", "Ranger"],
    "Blight-Hollow": ["Necromancer", "Warlock"],
    "Ashen Outpost": ["Warrior", "Rogue"],
    "Sorrow's Reach": ["Warlock", "Necromancer"],
    "The Blood-Forge Citadel": ["Warrior", "Warlock"],
    "Malice Bay": ["Rogue", "Necromancer"],
    "Vile-Grave Necropolis": ["Necromancer", "Warlock"],
    "Hellfire Spire": ["Warlock", "Necromancer"],
}


def create_reputation_vendor(room: Any, faction: str, vendor_faction: str) -> Optional[Any]:
    """
    Create a ReputationVendorNPC in a room for a specific faction.

    These vendors sell faction-specific gear gated by reputation standing.
    """
    from world.reputation import ReputationVendorNPC

    vendor_names = {
        "aethelgard": "Quartermaster Aldric",
        "gorgoroth": "Warmonger Vex",
        "merchants_guild": "Guild Trader Lysandra",
        "arcane_order": "Archivist Merdok",
        "wildlands": "Warden Thornbark",
        "underworld": "Shadow Broker Silas",
    }
    vendor_descs = {
        "aethelgard": "A stern quartermaster in gleaming Aethelgard colours, his tabard bearing the radiant sun crest.",
        "gorgoroth": "A scarred warmonger whose black iron armour is etched with the jagged crest of Gorgoroth.",
        "merchants_guild": "A well-dressed trader with keen eyes and a ledger tucked under one arm.",
        "arcane_order": "A robed archivist whose spectacles glint with arcane light.",
        "wildlands": "A weathered warden clad in living bark and moss, smelling of pine and earth.",
        "underworld": "A hooded figure whose face is hidden in shadow, fingers adorned with stolen rings.",
    }

    name = vendor_names.get(vendor_faction, f"{vendor_faction} Quartermaster")
    desc = vendor_descs.get(vendor_faction, "A faction quartermaster offering gear to those in good standing.")

    try:
        vendor = create_object(
            "world.reputation.ReputationVendorNPC",
            key=name,
            location=room,
            attributes=[
                ("desc", f"{name} stands here, offering faction gear to trusted allies. {desc}"),
                ("is_npc", True),
                ("is_vendor", True),
                ("is_reputation_vendor", True),
                ("vendor_type", "reputation"),
                ("vendor_faction", vendor_faction),
                ("faction", faction),
                ("alignment", alignment_for_faction(faction)),
            ],
        )
        return vendor
    except Exception:
        return None


# Map faction towns to reputation vendor factions.
# Each town gets a rep vendor for its primary faction + sometimes a secondary.
TOWN_REP_VENDOR_MAP: Dict[str, List[str]] = {
    # Good towns — Aethelgard + secondary faction vendors
    "Adaar Haven (The Desert Gate)": ["aethelgard", "merchants_guild"],
    "Havencrest": ["aethelgard", "arcane_order"],
    "Sunspire Keep (Starter Hub)": ["aethelgard", "merchants_guild"],
    "Silverwood Village": ["wildlands", "aethelgard"],
    "Oakhaven": ["wildlands", "aethelgard"],
    "Stoneguard Hold": ["aethelgard"],
    "Dawn-Light Bay": ["aethelgard", "arcane_order"],
    "Riverbend": ["merchants_guild", "aethelgard"],
    "High-Meadow": ["wildlands"],
    "Astraea Sanctuary": ["aethelgard", "arcane_order"],
    "Eldergrove": ["wildlands", "arcane_order"],
    "Vales-End": ["aethelgard"],
    "Iron-Watch Castle": ["aethelgard"],
    # Evil towns — Gorgoroth + secondary faction vendors
    "Duradune (The Desert Gate)": ["gorgoroth", "merchants_guild"],
    "Freshwater Springs": ["gorgoroth", "underworld"],
    "Drow Caverns City": ["underworld", "gorgoroth"],
    "Brimstone Keep (Starter Hub)": ["gorgoroth", "underworld"],
    "Gloomhold": ["gorgoroth", "arcane_order"],
    "Rotwood Enclave": ["wildlands", "gorgoroth"],
    "Blight-Hollow": ["gorgoroth"],
    "Ashen Outpost": ["gorgoroth", "merchants_guild"],
    "Sorrow's Reach": ["gorgoroth", "underworld"],
    "The Blood-Forge Citadel": ["gorgoroth"],
    "Malice Bay": ["underworld", "gorgoroth"],
    "Vile-Grave Necropolis": ["gorgoroth", "arcane_order"],
    "Hellfire Spire": ["gorgoroth", "underworld"],
}


def populate_reputation_vendors() -> Dict[str, int]:
    """
    Place ReputationVendorNPCs in every faction town.

    Each town gets 1-2 reputation vendors from different factions.
    Players must earn reputation standing (Friendly → Exalted) to
    purchase faction-specific gear from these vendors.
    """
    stats = {"placed": 0, "towns_serviced": 0, "skipped": 0}

    for town_name, vendor_factions in TOWN_REP_VENDOR_MAP.items():
        room = find_room_by_key(f"{town_name} (Town Center)")
        if room is None:
            faction = FACTION_GOOD if town_name in GOOD_TOWNS else FACTION_EVIL
            room = _ensure_town_room(town_name, faction)
        if room is None:
            stats["skipped"] += 1
            continue

        faction = FACTION_GOOD if town_name in GOOD_TOWNS else FACTION_EVIL

        # Check which rep vendor factions already exist in this room
        existing_vendor_factions = set()
        for obj in room.contents:
            if hasattr(obj, "attributes") and obj.attributes.get("is_reputation_vendor"):
                existing_vendor_factions.add(obj.attributes.get("vendor_faction", ""))

        placed_here = 0
        for vendor_faction in vendor_factions:
            if vendor_faction in existing_vendor_factions:
                continue
            vendor = create_reputation_vendor(room, faction, vendor_faction)
            if vendor:
                stats["placed"] += 1
                placed_here += 1

        if placed_here > 0:
            stats["towns_serviced"] += 1

    return stats


def populate_guildmasters() -> Dict[str, int]:
    """
    Place GuildmasterNPCs in every faction town for mid/high-level training.

    Each town gets 1-4 guildmasters based on its theme.  Guildmasters use
    the practice-point system (CmdTrain/CmdLearn/CmdPractice) and can teach
    spells and combat skills appropriate to the character's level.

    This covers the L15-80 training gap — players must travel to faction
    towns to learn new abilities as they level up.
    """
    stats = {"placed": 0, "towns_serviced": 0, "skipped": 0}

    for town_name, guild_classes in TOWN_GUILDMASTER_MAP.items():
        room = find_room_by_key(f"{town_name} (Town Center)")
        if room is None:
            # Try to create the town room if it doesn't exist
            faction = FACTION_GOOD if town_name in GOOD_TOWNS else FACTION_EVIL
            room = _ensure_town_room(town_name, faction)
        if room is None:
            stats["skipped"] += 1
            continue

        faction = FACTION_GOOD if town_name in GOOD_TOWNS else FACTION_EVIL

        # Check which guildmasters already exist in this room
        existing_classes = set()
        for obj in room.contents:
            if hasattr(obj, "attributes") and obj.attributes.get("is_guildmaster"):
                existing_classes.add(obj.attributes.get("guild_class", ""))

        placed_here = 0
        for guild_class in guild_classes:
            if guild_class in existing_classes:
                continue
            gm = create_guildmaster(room, faction, guild_class)
            if gm:
                stats["placed"] += 1
                placed_here += 1

        if placed_here > 0:
            stats["towns_serviced"] += 1

    return stats


# ---------------------------------------------------------------------------
# Room lookup helpers
# ---------------------------------------------------------------------------

def find_room_by_key(key: str) -> Optional[Any]:
    """Find a room by exact key, stripping ANSI to guard against styled keys."""
    results = search_object(key, typeclass="typeclasses.rooms.Room")
    if results:
        return results[0]

    from evennia.objects.models import ObjectDB
    stripped = strip_ansi(key).lower()
    for room in ObjectDB.objects.filter(db_typeclass_path__endswith="Room"):
        if strip_ansi(room.db_key or "").lower() == stripped:
            return room
    return None


def find_room_by_tag(tag: str, category: str = "room_id") -> Optional[Any]:
    """Find the first room carrying a given tag/category."""
    results = search_tag(tag, category=category)
    return results[0] if results else None


def rooms_by_zone(zone_key: str) -> List[Any]:
    """Return all rooms tagged with a builder zone key."""
    return list(search_tag(zone_key, category="zone"))


# ---------------------------------------------------------------------------
# Faction territory application
# ---------------------------------------------------------------------------

def apply_faction_territory() -> Dict[str, int]:
    """
    Stamp faction ownership/alignment restrictions onto every zone room.

    Faction starter zones and city hubs become alignment-restricted so
    Evil players cannot wander into alliance starter territory and vice
    versa.  All zone rooms receive a ``faction_territory`` attribute for
    verification and future social/aggro features.
    """
    stats = {"good": 0, "evil": 0, "neutral": 0, "restricted_good": 0, "restricted_evil": 0}

    for zone_key in GOOD_ZONES:
        faction = FACTION_GOOD
        restricted = zone_key in GOOD_STARTER_ZONES
        for room in rooms_by_zone(zone_key):
            room.attributes.add("faction_territory", faction)
            room.attributes.add("zone_tag", zone_key)
            if restricted:
                room.attributes.add("alignment_restricted", ALIGNMENT_GOOD)
                stats["restricted_good"] += 1
            stats["good"] += 1

    for zone_key in EVIL_ZONES:
        faction = FACTION_EVIL
        restricted = zone_key in EVIL_STARTER_ZONES
        for room in rooms_by_zone(zone_key):
            room.attributes.add("faction_territory", faction)
            room.attributes.add("zone_tag", zone_key)
            if restricted:
                room.attributes.add("alignment_restricted", ALIGNMENT_EVIL)
                stats["restricted_evil"] += 1
            stats["evil"] += 1

    for zone_key in NEUTRAL_ZONES:
        for room in rooms_by_zone(zone_key):
            room.attributes.add("faction_territory", FACTION_NEUTRAL)
            room.attributes.add("zone_tag", zone_key)
            stats["neutral"] += 1

    # Faction city hubs are safe zones and alignment-restricted.
    for room_key in GOOD_HUB_ROOMS:
        room = find_room_by_key(room_key)
        if room:
            room.db.safe_zone = True
            room.attributes.add("alignment_restricted", ALIGNMENT_GOOD)
            room.attributes.add("faction_territory", FACTION_GOOD)
    for room_key in EVIL_HUB_ROOMS:
        room = find_room_by_key(room_key)
        if room:
            room.db.safe_zone = True
            room.attributes.add("alignment_restricted", ALIGNMENT_EVIL)
            room.attributes.add("faction_territory", FACTION_EVIL)

    return stats


# ---------------------------------------------------------------------------
# Misaligned spawn cleanup
# ---------------------------------------------------------------------------

def is_misaligned(zone_faction: str, mob_faction: str) -> bool:
    """
    Pure predicate: True when a mob's faction conflicts with a zone owner.

    Neutral mobs are always considered acceptable in any territory.
    Good mobs are misaligned in Evil territory and Evil mobs in Good
    territory.
    """
    if zone_faction == FACTION_NEUTRAL or mob_faction == FACTION_NEUTRAL:
        return False
    return zone_faction != mob_faction


def clear_misaligned_spawns() -> Dict[str, int]:
    """
    Delete mobs whose faction contradicts the zone they inhabit.

    This is the correction for the Sunspire Meadows bug where Evil mobs
    (and later Evil player spawns) were orphaned in alliance territory.
    """
    stats: Dict[str, int] = {"removed": 0, "good_zones": 0, "evil_zones": 0}

    def _mob_faction(obj: Any) -> Optional[str]:
        try:
            if not obj.attributes.get("is_mob", False):
                return None
            return obj.attributes.get("faction", None)
        except Exception:
            return None

    for zone_key in GOOD_ZONES | EVIL_ZONES:
        zone_faction = faction_for_zone(zone_key)
        for room in rooms_by_zone(zone_key):
            for obj in list(room.contents):
                try:
                    if not hasattr(obj, "attributes") or obj.has_account:
                        continue
                    mob_faction = _mob_faction(obj)
                    if mob_faction is None:
                        continue
                    if is_misaligned(zone_faction, mob_faction):
                        obj.delete()
                        stats["removed"] += 1
                except Exception:
                    continue
        if zone_faction == FACTION_GOOD:
            stats["good_zones"] += 1
        else:
            stats["evil_zones"] += 1

    return stats


# ---------------------------------------------------------------------------
# Zone population
# ---------------------------------------------------------------------------

def _count_realm_mobs(room: Any) -> int:
    """Count alive realm mobs currently in a room."""
    count = 0
    try:
        for obj in room.contents:
            if not hasattr(obj, "attributes"):
                continue
            if not obj.attributes.get("is_mob", False):
                continue
            hp = obj.attributes.get("hp", 0)
            if hp > 0:
                count += 1
    except Exception:
        pass
    return count


def populate_zone(zone_key: str, data: Dict[str, Any]) -> Dict[str, int]:
    """
    Populate every room in a single zone with level-appropriate XP mobs.

    Loops the rooms returned by ``search_tag(zone_key, category="zone")``,
    computes a target mob count from the danger band, and tops each room
    up using the appropriate faction mob pool.
    """
    level_min, level_max = data.get("level_range", (1, 5))
    danger = danger_for_range(level_min, level_max)
    faction = faction_for_zone(zone_key)
    pool = mob_pool_for_zone(zone_key, level_min, level_max)
    lo, hi = mobs_per_room(level_min, level_max)

    stats = {"rooms": 0, "spawned": 0, "skipped_safe": 0}

    for room in rooms_by_zone(zone_key):
        stats["rooms"] += 1

        # Never spawn combat mobs inside faction cities/safe hubs.
        if room.attributes.get("safe_zone", False):
            stats["skipped_safe"] += 1
            continue

        # Set the room's max_mobs cap from the danger band.
        room.attributes.add("max_mobs", hi)
        room.attributes.add("zone_tag", zone_key)

        target = random.randint(lo, hi)
        existing = _count_realm_mobs(room)
        for _ in range(max(0, target - existing)):
            spec = random.choice(pool)
            mob_level = max(level_min, min(level_max, spec["level"]))
            # For the safe starter zones, keep creatures passive regardless.
            if danger == "safe":
                spec_aggro = False
            else:
                spec_aggro = spec.get("aggro", False)
            mob = create_realm_mob(
                room,
                spec["name"],
                faction,
                mob_level,
                spec_aggro,
                damage_type=spec.get("damage_type", "slash"),
                home=room,
            )
            if mob:
                stats["spawned"] += 1

    return stats


def populate_all_zones() -> Dict[str, Any]:
    """Populate every mapped zone in the realm."""
    overall = {"zones": 0, "rooms": 0, "spawned": 0, "skipped_safe": 0}
    for zone_key, data in b1.ALL_ZONES.items():
        zstats = populate_zone(zone_key, data)
        overall["zones"] += 1
        overall["rooms"] += zstats["rooms"]
        overall["spawned"] += zstats["spawned"]
        overall["skipped_safe"] += zstats["skipped_safe"]
    return overall


# ---------------------------------------------------------------------------
# Starter services (vendors & trainers in 1-10 zones)
# ---------------------------------------------------------------------------

def populate_faction_starters() -> Dict[str, Any]:
    """
    Build faction city hubs and place low-level vendors/trainers in the
    true 1-10 starter zones.

    Good 1-10 zone: ``sunspire_meadows_1``.
    Evil 1-10 zone: ``brimstone_courtyard_1`` (Orc Warrior start area).
    """
    from world.faction_starter import (
        build_faction_starters,
        _create_gear_vendor,
        _create_spell_trainer,
        GOOD_STARTER_GEAR,
        EVIL_STARTER_GEAR,
    )

    build_faction_starters()

    stats = {"good_vendors": 0, "evil_vendors": 0, "good_trainers": 0, "evil_trainers": 0}

    def _ensure_services(room_tag: str, faction_name: str, gear_table: Dict[str, Any]) -> None:
        room = find_room_by_tag(room_tag, category="room_id")
        if room is None:
            return
        room.attributes.add("faction_territory", faction_name)
        has_vendor = any(
            o.attributes.get("is_vendor") for o in room.contents if hasattr(o, "attributes")
        )
        has_trainer = any(
            o.attributes.get("is_trainer") for o in room.contents if hasattr(o, "attributes")
        )
        if not has_vendor:
            _create_gear_vendor(room, "Good" if faction_name == FACTION_GOOD else "Evil", gear_table)
        if not has_trainer:
            _create_spell_trainer(room, "Good" if faction_name == FACTION_GOOD else "Evil")

    _ensure_services("sunspire_meadows_1", FACTION_GOOD, GOOD_STARTER_GEAR)
    _ensure_services("brimstone_courtyard_1", FACTION_EVIL, EVIL_STARTER_GEAR)

    # Guards inside the newbie zone entrances.
    good_entry = find_room_by_tag("sunspire_meadows_1", category="room_id")
    evil_entry = find_room_by_tag("brimstone_courtyard_1", category="room_id")
    if good_entry and not _room_has_guard(good_entry):
        create_faction_guard(good_entry, FACTION_GOOD, level=10)
        stats["good_trainers"] = stats.get("good_trainers", 0)  # keep keys stable, guard count below
    if evil_entry and not _room_has_guard(evil_entry):
        create_faction_guard(evil_entry, FACTION_EVIL, level=10)

    stats["good_vendors"] = 1 if (_entry_has(good_entry, "is_vendor")) else 0
    stats["evil_vendors"] = 1 if (_entry_has(evil_entry, "is_vendor")) else 0
    stats["good_trainers"] = 1 if (_entry_has(good_entry, "is_trainer")) else 0
    stats["evil_trainers"] = 1 if (_entry_has(evil_entry, "is_trainer")) else 0
    return stats


def _room_has_guard(room: Any) -> bool:
    if room is None:
        return False
    from typeclasses.rooms import Room
    return any(Room._is_guard(o) for o in room.contents)


def _entry_has(room: Any, attr: str) -> bool:
    if room is None:
        return False
    return any(o.attributes.get(attr) for o in room.contents if hasattr(o, "attributes"))


# ---------------------------------------------------------------------------
# Faction towns (lightweight service hubs)
# ---------------------------------------------------------------------------

def _ensure_town_room(town_name: str, faction: str) -> Optional[Any]:
    """Find or create the town center room for a named town."""
    room_key = f"{town_name} (Town Center)"
    room = find_room_by_key(room_key)
    if room is None:
        room = create_object(
            "typeclasses.rooms.Room",
            key=room_key,
            attributes=[
                ("desc", f"The bustling center of {town_name}."),
                ("faction_territory", faction),
            ],
        )
        room.db.safe_zone = True
        room.attributes.add("alignment_restricted", alignment_for_faction(faction))
        room.tags.add("faction_town", category="room_type")
    return room


def populate_towns() -> Dict[str, int]:
    """Create a guard + vendor + trainer hub in every listed faction town."""
    stats = {"good_towns": 0, "evil_towns": 0, "npcs": 0}
    for town_name in GOOD_TOWNS:
        room = _ensure_town_room(town_name, FACTION_GOOD)
        if room:
            if not _room_has_guard(room):
                create_faction_guard(room, FACTION_GOOD, level=20)
                stats["npcs"] += 1
            if not _entry_has(room, "is_vendor"):
                create_vendor(room, FACTION_GOOD)
                stats["npcs"] += 1
            if not _entry_has(room, "is_trainer"):
                create_trainer(room, FACTION_GOOD)
                stats["npcs"] += 1
            stats["good_towns"] += 1

    for town_name in EVIL_TOWNS:
        room = _ensure_town_room(town_name, FACTION_EVIL)
        if room:
            if not _room_has_guard(room):
                create_faction_guard(room, FACTION_EVIL, level=20)
                stats["npcs"] += 1
            if not _entry_has(room, "is_vendor"):
                create_vendor(room, FACTION_EVIL)
                stats["npcs"] += 1
            if not _entry_has(room, "is_trainer"):
                create_trainer(room, FACTION_EVIL)
                stats["npcs"] += 1
            stats["evil_towns"] += 1

    return stats


# ---------------------------------------------------------------------------
# Faction starter linking (city -> 1-10 newbie zone)
# ---------------------------------------------------------------------------

def link_faction_starters() -> Dict[str, int]:
    """
    Guarantee the faction cities connect to their true 1-10 newbie zones:

      Aethelgard - Shrine of Light  -> sunspire_meadows_1
      Gorgoroth  - Dark Temple      -> brimstone_courtyard_1
    """
    from evennia import create_object as make_exit

    stats = {"linked": 0}

    links = [
        ("Aethelgard - Shrine of Light", "sunspire_meadows_1", "room_id", "south"),
        ("Gorgoroth - Dark Temple", "brimstone_courtyard_1", "room_id", "north"),
    ]

    opposite = {
        "north": "south", "south": "north",
        "east": "west", "west": "east",
        "up": "down", "down": "up",
    }

    for city_key, target_tag, category, direction in links:
        city = find_room_by_key(city_key)
        target = find_room_by_tag(target_tag, category=category)
        if city is None or target is None:
            continue
        back = opposite[direction]
        if not city.search(direction):
            make_exit("typeclasses.exits.Exit", key=direction, location=city, destination=target)
            stats["linked"] += 1
        if not target.search(back):
            make_exit("typeclasses.exits.Exit", key=back, location=target, destination=city)
            stats["linked"] += 1

    return stats


# ---------------------------------------------------------------------------
# Boss placement
# ---------------------------------------------------------------------------

def place_bosses() -> Dict[str, Any]:
    """
    Place all 30 registered bosses into their lairs with respawn timers,
    faction alignment, XP/gold, and boss loot/stat hooks.

    The lair rooms are located via ``boss_registry.BOSS_ROOM_LOOKUP`` and
    the ANSI-safe room finder.  Each boss is spawned as a real Mob so it
    participates in the combat engine and respawns after a long delay.
    """
    from world.boss_zones import build_boss_lairs

    # Ensure lair rooms exist before placement.
    build_boss_lairs()

    stats = {"placed": 0, "missing_lair": 0, "missing_registry": 0}

    for boss_id, data in boss_registry.BOSS_REGISTRY.items():
        room_key = boss_registry.BOSS_ROOM_LOOKUP.get(boss_id)
        if not room_key:
            stats["missing_registry"] += 1
            continue
        room = find_room_by_key(room_key)
        if room is None:
            stats["missing_lair"] += 1
            continue

        if _boss_already_in(room, boss_id):
            continue

        faction = data["faction"]
        level = data["level"]
        boss = create_realm_mob(
            room,
            data["name"],
            faction,
            level,
            True,
            damage_type="slash",
            home=room,
            respawn_delay=1800,
            is_boss=True,
            boss_id=boss_id,
            xp_value=level * 50,
            gold=(level * 10, level * 25),
            extra_attrs=[
                ("max_damage", data["max_damage"]),
                ("rare_drop", data["rare_drop"]),
                ("drop_stats", data["drop_stats"]),
                ("drop_rate", data["drop_rate"]),
                ("announce", data["announce"]),
                ("max_hp", data["hp"]),
                ("hp", data["hp"]),
            ],
        )
        if boss:
            stats["placed"] += 1

    return stats


def _boss_already_in(room: Any, boss_id: str) -> bool:
    """Return True if a boss with the exact *boss_id* is already in the room."""
    for obj in room.contents:
        try:
            if obj.attributes.get("boss_id") == boss_id:
                return True
        except Exception:
            continue
    return False


# ---------------------------------------------------------------------------
# Master entry point
# ---------------------------------------------------------------------------

def populate_realm(clear_misaligned: bool = True) -> Dict[str, Any]:
    """
    Run the complete realm population pipeline (idempotent to a practical
    degree — existing alive mobs are counted before topping rooms up).

    Order:
      1. Remove misaligned spawns.
      2. Stamp faction territory/alignment bounds.
      3. Build faction city services + starter-zone vendors/trainers.
      4. Populate every zone with level-appropriate mobs.
      5. Populate faction towns.
      6. Link faction cities to their 1-10 newbie zones.
      7. Place all 30 bosses.
    """
    report: Dict[str, Any] = {}
    if clear_misaligned:
        report["misaligned"] = clear_misaligned_spawns()
    report["territory"] = apply_faction_territory()
    report["starters"] = populate_faction_starters()
    report["zones"] = populate_all_zones()
    report["towns"] = populate_towns()
    report["guildmasters"] = populate_guildmasters()
    report["rep_vendors"] = populate_reputation_vendors()
    report["links"] = link_faction_starters()
    report["bosses"] = place_bosses()
    return report


if __name__ == "__main__":
    import json
    print(json.dumps(populate_realm(), indent=2))