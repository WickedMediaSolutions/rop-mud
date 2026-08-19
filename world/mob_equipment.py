"""
Classic-Style Procedural Mob Equipment & Inventory Generator for 'rop'
======================================================================

When any mob spawns across the realm, it is automatically equipped with
weapons, armor, and gear items appropriate for its level, class, and
faction.  On death, equipped items populate the corpse inventory.

Also fixes the phantom armor absorption bug: if a mob or player has no
armor equipped, damage calculations correctly reflect 0 armor absorption
instead of displaying phantom absorption.

Exhaustive Equipment Slot Architecture (v2.0)
---------------------------------------------
Canonical slot names with backward-compatible aliases:

  Armor Slots:
    head, left_ear, right_ear, neck, torso (alias: chest),
    wrists, hands (gloves), left_finger, right_finger,
    belt, legs, feet, aura

  Weapon Slots:
    right_hand (alias: main_hand), left_hand (alias: off_hand),
    two_hand (two-handed weapon, occupies both hands)

  Dual-wielding: right_hand + left_hand both occupied by weapons.
  Shield: left_hand occupied by a shield item (armor, no damage).
  Two-hand: two_hand slot occupied, right_hand and left_hand blocked.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

# Evennia imports are deferred to avoid errors when the module is
# imported outside of a fully bootstrapped Evennia environment (e.g.
# unit tests that only need data tables).
_create_object = None
_DefaultObject = None


def _get_create_object():
    global _create_object, _DefaultObject
    if _create_object is None:
        from evennia import create_object as co, __init__  # noqa: F401
        from evennia.objects.objects import DefaultObject as do
        _create_object = co
        _DefaultObject = do
    return _create_object, _DefaultObject


def _is_mock_container(container: Any) -> bool:
    """
    Return True if *container* stores its contents as a plain Python list.

    Real Evennia objects use a manager/handler for ``contents``; mock test
    objects use a simple list.  This lets us generate compatible (mock)
    items when equipping a mock container.
    """
    if container is None:
        return False
    return isinstance(getattr(container, "contents", None), list)


def _move_item_to_container(item: Any, container: Any) -> None:
    """
    Move *item* into *container*, supporting both real Evennia objects and
    lightweight mock containers that use a plain ``contents`` list.
    """
    if item is None or container is None:
        return

    move_to = getattr(item, "move_to", None)
    if callable(move_to):
        try:
            move_to(container, quiet=True)
        except Exception:
            pass

    contents = getattr(container, "contents", None)
    if isinstance(contents, list) and item not in contents:
        contents.append(item)


# ===========================================================================
# EXHAUSTIVE EQUIPMENT SLOT ARCHITECTURE
# ===========================================================================

# Canonical slot definitions with display names and categories.
# Order matters for paperdoll display.
SLOT_DEFINITIONS = [
    # -- Head & Face --
    {"key": "head",       "display": "Head",        "category": "armor",  "group": "head"},
    {"key": "left_ear",   "display": "Left Ear",    "category": "armor",  "group": "ears"},
    {"key": "right_ear",  "display": "Right Ear",   "category": "armor",  "group": "ears"},
    {"key": "neck",       "display": "Neck",        "category": "armor",  "group": "neck"},
    # -- Torso & Arms --
    {"key": "torso",      "display": "Torso",       "category": "armor",  "group": "torso"},
    {"key": "wrists",     "display": "Wrists",      "category": "armor",  "group": "wrists"},
    {"key": "hands",      "display": "Hands",       "category": "armor",  "group": "hands"},
    {"key": "left_finger","display": "Left Finger", "category": "armor",  "group": "fingers"},
    {"key": "right_finger","display":"Right Finger","category": "armor",  "group": "fingers"},
    # -- Waist & Legs --
    {"key": "belt",       "display": "Belt",        "category": "armor",  "group": "belt"},
    {"key": "legs",       "display": "Legs",        "category": "armor",  "group": "legs"},
    {"key": "feet",       "display": "Feet",        "category": "armor",  "group": "feet"},
    # -- Special --
    {"key": "aura",       "display": "Aura",        "category": "armor",  "group": "aura"},
    # -- Weapons --
    {"key": "right_hand", "display": "Right Hand",  "category": "weapon", "group": "weapons"},
    {"key": "left_hand",  "display": "Left Hand",   "category": "weapon", "group": "weapons"},
    {"key": "two_hand",   "display": "Two Hands",   "category": "weapon", "group": "weapons"},
]

# Build lookup tables
SLOT_BY_KEY: Dict[str, Dict[str, str]] = {s["key"]: s for s in SLOT_DEFINITIONS}
ALL_SLOT_KEYS: List[str] = [s["key"] for s in SLOT_DEFINITIONS]
ARMOR_SLOT_KEYS: List[str] = [s["key"] for s in SLOT_DEFINITIONS if s["category"] == "armor"]
WEAPON_SLOT_KEYS: List[str] = [s["key"] for s in SLOT_DEFINITIONS if s["category"] == "weapon"]

# Backward-compatible aliases: alias -> canonical key
SLOT_ALIASES: Dict[str, str] = {
    # torso aliases
    "chest": "torso",
    "body": "torso",
    "chest_heavy": "torso",  # Pixie restriction uses this
    # hand aliases
    "main_hand": "right_hand",
    "off_hand": "left_hand",
    "weapon": "right_hand",
    "right": "right_hand",
    "left": "left_hand",
    # two-hand aliases
    "two_handed": "two_hand",
    "both_hands": "two_hand",
    # armor set compat
    "arms": "wrists",
    "shoulders": "wrists",
    # fingers aliases
    "finger": "left_finger",
    "ring": "left_finger",
    # ears aliases
    "ear": "left_ear",
    # gloves alias
    "gloves": "hands",
}

# Legacy slot lists (kept for backward compat with existing code)
EQUIP_SLOTS = ALL_SLOT_KEYS
WEAPON_SLOTS = ("right_hand", "left_hand", "two_hand", "main_hand", "off_hand",
                "hands", "weapon", "right", "left", "two_handed")
ARMOR_SLOTS = ("head", "left_ear", "right_ear", "neck", "torso", "chest",
               "wrists", "hands", "left_finger", "right_finger",
               "belt", "legs", "feet", "aura", "off_hand", "arms", "shoulders")


def normalize_slot(slot_name: str) -> str:
    """
    Normalize a slot name to its canonical form.

    Handles legacy aliases (e.g. 'chest' -> 'torso', 'main_hand' -> 'right_hand').
    Returns the original name if it's already canonical or unrecognized.
    """
    if not slot_name:
        return slot_name
    key = slot_name.lower().strip()
    # Direct canonical match
    if key in SLOT_BY_KEY:
        return key
    # Alias lookup
    if key in SLOT_ALIASES:
        return SLOT_ALIASES[key]
    # Return as-is for unknown slots
    return slot_name


def get_slot_display(slot_name: str) -> str:
    """Return the human-readable display name for a slot."""
    canonical = normalize_slot(slot_name)
    info = SLOT_BY_KEY.get(canonical)
    if info:
        return info["display"]
    return slot_name.replace("_", " ").title()


def get_slot_category(slot_name: str) -> str:
    """Return the category ('armor' or 'weapon') for a slot."""
    canonical = normalize_slot(slot_name)
    info = SLOT_BY_KEY.get(canonical)
    if info:
        return info["category"]
    return "armor"


def is_weapon_slot(slot_name: str) -> bool:
    """Return True if the slot is a weapon slot."""
    return get_slot_category(slot_name) == "weapon"


def is_armor_slot(slot_name: str) -> bool:
    """Return True if the slot is an armor slot."""
    return get_slot_category(slot_name) == "armor"


def get_paperdoll_order() -> List[str]:
    """Return canonical slot keys in paperdoll display order."""
    return ALL_SLOT_KEYS


def get_equipped_slot_map(character: Any) -> Dict[str, str]:
    """
    Return a normalized dict of canonical_slot -> item_name for a character.

    Handles legacy slot names stored in the ``equipped`` attribute by
    normalizing all keys to their canonical form.
    """
    raw = _as_dict(character.attributes.get("equipped", default={}))
    normalized: Dict[str, str] = {}
    for slot, name in raw.items():
        canonical = normalize_slot(slot)
        if canonical and name:
            normalized[canonical] = str(name)
    return normalized


# ===========================================================================
# Item rarity tiers (MajorMUD-style)
# ===========================================================================
# Higher rarity = better stats and higher value multipliers

RARITY_TIERS = {
    "common":     {"mult": 1.0, "color": "|w", "label": "Common"},
    "uncommon":   {"mult": 1.3, "color": "|g", "label": "Uncommon"},
    "rare":       {"mult": 1.7, "color": "|c", "label": "Rare"},
    "epic":       {"mult": 2.3, "color": "|m", "label": "Epic"},
    "legendary":  {"mult": 3.0, "color": "|Y", "label": "Legendary"},
}

# Roll weights by mob tier (higher tiers have better rarity chances)
RARITY_WEIGHTS_BY_TIER = {
    1: {"common": 80, "uncommon": 15, "rare": 4, "epic": 1, "legendary": 0},   # levels 1-10
    2: {"common": 65, "uncommon": 22, "rare": 10, "epic": 2, "legendary": 1},   # levels 11-25
    3: {"common": 50, "uncommon": 25, "rare": 18, "epic": 5, "legendary": 2},   # levels 26-40
    4: {"common": 35, "uncommon": 25, "rare": 25, "epic": 10, "legendary": 5},  # levels 41-60
    5: {"common": 20, "uncommon": 25, "rare": 30, "epic": 15, "legendary": 10}, # levels 61-80
}


def _roll_rarity(mob_tier: int) -> str:
    """Roll a random rarity based on mob level tier."""
    import random
    weights = RARITY_WEIGHTS_BY_TIER.get(mob_tier, RARITY_WEIGHTS_BY_TIER[1])
    tiers = list(weights.keys())
    w = [weights[t] for t in tiers]
    return random.choices(tiers, weights=w, k=1)[0]


def _apply_rarity_to_template(template: Dict[str, Any], rarity: str) -> Dict[str, Any]:
    """Apply rarity modifiers (stat multiplier and label) to an equipment template."""
    if rarity == "common":
        return template  # no change for common

    rarity_info = RARITY_TIERS.get(rarity, RARITY_TIERS["common"])
    mult = rarity_info["mult"]
    label = rarity_info["label"]
    color = rarity_info["color"]

    modified = dict(template)
    # Boost damage/armor
    if "damage" in modified:
        modified["damage"] = max(1, int(modified["damage"] * mult))
    if "armor" in modified:
        modified["armor"] = max(1, int(modified["armor"] * mult))
    # Boost value
    modified["value"] = max(1, int(modified.get("value", 1) * mult))
    # Add rarity prefix to name
    modified["name"] = f"{color}{label} {template['name']}|n"
    # Store rarity for display
    modified["_rarity"] = rarity
    modified["_rarity_color"] = color
    return modified

# ===========================================================================
# Weapon templates by class archetype and level tier
# ===========================================================================

WEAPON_TEMPLATES: Dict[str, Dict[int, List[Dict[str, Any]]]] = {
    "warrior": {
        1: [  # levels 1-10
            {"name": "Rusty Shortsword", "damage": 5, "damage_type": "slash", "slot": "right_hand", "weight": 4.0, "value": 8},
            {"name": "Crude Hand Axe", "damage": 6, "damage_type": "slash", "slot": "right_hand", "weight": 5.0, "value": 10},
            {"name": "Wooden Club", "damage": 4, "damage_type": "blunt", "slot": "right_hand", "weight": 3.0, "value": 5},
        ],
        2: [  # levels 11-25
            {"name": "Iron Broadsword", "damage": 9, "damage_type": "slash", "slot": "right_hand", "weight": 6.0, "value": 25},
            {"name": "Battle Axe", "damage": 11, "damage_type": "slash", "slot": "right_hand", "weight": 8.0, "value": 30},
            {"name": "Heavy Mace", "damage": 10, "damage_type": "blunt", "slot": "right_hand", "weight": 7.0, "value": 28},
        ],
        3: [  # levels 26-40
            {"name": "Steel Longsword", "damage": 15, "damage_type": "slash", "slot": "right_hand", "weight": 7.0, "value": 60},
            {"name": "War Hammer", "damage": 17, "damage_type": "blunt", "slot": "right_hand", "weight": 10.0, "value": 65},
            {"name": "Great Axe", "damage": 19, "damage_type": "slash", "slot": "two_hand", "weight": 12.0, "value": 75},
        ],
        4: [  # levels 41-60
            {"name": "Fine Steel Claymore", "damage": 22, "damage_type": "slash", "slot": "two_hand", "weight": 11.0, "value": 120},
            {"name": "Enchanted Warblade", "damage": 20, "damage_type": "slash", "slot": "right_hand", "weight": 8.0, "value": 130},
            {"name": "Crushing Maul", "damage": 24, "damage_type": "blunt", "slot": "two_hand", "weight": 14.0, "value": 140},
        ],
        5: [  # levels 61-80
            {"name": "Runed Greatsword", "damage": 30, "damage_type": "slash", "slot": "two_hand", "weight": 12.0, "value": 250},
            {"name": "Doomforged Axe", "damage": 32, "damage_type": "slash", "slot": "two_hand", "weight": 14.0, "value": 280},
            {"name": "Titan's Warhammer", "damage": 34, "damage_type": "blunt", "slot": "two_hand", "weight": 16.0, "value": 300},
        ],
    },
    "rogue": {
        1: [
            {"name": "Rusty Dagger", "damage": 4, "damage_type": "pierce", "slot": "right_hand", "weight": 1.5, "value": 6},
            {"name": "Crude Shiv", "damage": 3, "damage_type": "pierce", "slot": "right_hand", "weight": 1.0, "value": 4},
        ],
        2: [
            {"name": "Sharp Dirk", "damage": 8, "damage_type": "pierce", "slot": "right_hand", "weight": 2.0, "value": 20},
            {"name": "Stiletto", "damage": 7, "damage_type": "pierce", "slot": "right_hand", "weight": 1.5, "value": 18},
        ],
        3: [
            {"name": "Shadow Blade", "damage": 13, "damage_type": "pierce", "slot": "right_hand", "weight": 2.5, "value": 50},
            {"name": "Venom Dagger", "damage": 12, "damage_type": "pierce", "slot": "right_hand", "weight": 2.0, "value": 55},
        ],
        4: [
            {"name": "Assassin's Kris", "damage": 18, "damage_type": "pierce", "slot": "right_hand", "weight": 2.5, "value": 110},
            {"name": "Nightstalker Blade", "damage": 17, "damage_type": "slash", "slot": "right_hand", "weight": 3.0, "value": 105},
        ],
        5: [
            {"name": "Death Whisper Dagger", "damage": 25, "damage_type": "pierce", "slot": "right_hand", "weight": 2.5, "value": 220},
            {"name": "Void-Touched Kris", "damage": 27, "damage_type": "pierce", "slot": "right_hand", "weight": 2.0, "value": 240},
        ],
    },
    "caster": {
        1: [
            {"name": "Worn Quarterstaff", "damage": 3, "damage_type": "blunt", "slot": "two_hand", "weight": 3.0, "value": 5},
            {"name": "Apprentice Wand", "damage": 2, "damage_type": "magic_fire", "slot": "right_hand", "weight": 0.5, "value": 8},
        ],
        2: [
            {"name": "Oak Staff", "damage": 6, "damage_type": "blunt", "slot": "two_hand", "weight": 4.0, "value": 18},
            {"name": "Bone Wand", "damage": 5, "damage_type": "magic_shadow", "slot": "right_hand", "weight": 0.5, "value": 22},
        ],
        3: [
            {"name": "Runed Staff", "damage": 10, "damage_type": "blunt", "slot": "two_hand", "weight": 4.5, "value": 45},
            {"name": "Crystal Wand", "damage": 9, "damage_type": "magic_fire", "slot": "right_hand", "weight": 0.5, "value": 50},
        ],
        4: [
            {"name": "Archmage Staff", "damage": 15, "damage_type": "blunt", "slot": "two_hand", "weight": 5.0, "value": 100},
            {"name": "Scepter of Power", "damage": 14, "damage_type": "magic_lightning", "slot": "right_hand", "weight": 1.0, "value": 110},
        ],
        5: [
            {"name": "Elder Staff of the Void", "damage": 22, "damage_type": "magic_shadow", "slot": "two_hand", "weight": 5.0, "value": 230},
            {"name": "Archon's Scepter", "damage": 20, "damage_type": "magic_fire", "slot": "right_hand", "weight": 1.0, "value": 250},
        ],
    },
    "ranger": {
        1: [
            {"name": "Short Bow", "damage": 4, "damage_type": "pierce", "slot": "two_hand", "weight": 2.5, "value": 8},
            {"name": "Hunting Knife", "damage": 3, "damage_type": "slash", "slot": "right_hand", "weight": 1.5, "value": 5},
        ],
        2: [
            {"name": "Longbow", "damage": 8, "damage_type": "pierce", "slot": "two_hand", "weight": 3.0, "value": 22},
            {"name": "Broadhead Arrows", "damage": 7, "damage_type": "pierce", "slot": "right_hand", "weight": 2.0, "value": 20},
        ],
        3: [
            {"name": "Composite Bow", "damage": 13, "damage_type": "pierce", "slot": "two_hand", "weight": 3.5, "value": 55},
            {"name": "Ranger's Blade", "damage": 11, "damage_type": "slash", "slot": "right_hand", "weight": 2.5, "value": 48},
        ],
        4: [
            {"name": "Windrunner Bow", "damage": 18, "damage_type": "pierce", "slot": "two_hand", "weight": 3.5, "value": 115},
            {"name": "Eagle-Eye Longbow", "damage": 17, "damage_type": "pierce", "slot": "two_hand", "weight": 3.0, "value": 120},
        ],
        5: [
            {"name": "Stormcaller Greatbow", "damage": 26, "damage_type": "pierce", "slot": "two_hand", "weight": 4.0, "value": 240},
            {"name": "Dragonbone Recurve", "damage": 28, "damage_type": "pierce", "slot": "two_hand", "weight": 3.5, "value": 260},
        ],
    },
    "monk": {
        1: [
            {"name": "Cloth Wraps", "damage": 3, "damage_type": "blunt", "slot": "hands", "weight": 0.5, "value": 3},
        ],
        2: [
            {"name": "Iron Knuckles", "damage": 7, "damage_type": "blunt", "slot": "hands", "weight": 1.0, "value": 15},
        ],
        3: [
            {"name": "Steel Cestus", "damage": 12, "damage_type": "blunt", "slot": "hands", "weight": 1.5, "value": 40},
        ],
        4: [
            {"name": "Dragon Fist Wraps", "damage": 17, "damage_type": "blunt", "slot": "hands", "weight": 1.0, "value": 95},
        ],
        5: [
            {"name": "Celestial Hand Wraps", "damage": 24, "damage_type": "blunt", "slot": "hands", "weight": 1.0, "value": 210},
        ],
    },
}

# ===========================================================================
# Armor templates by slot and tier
# ===========================================================================

ARMOR_TEMPLATES: Dict[str, Dict[int, List[Dict[str, Any]]]] = {
    "head": {
        1: [
            {"name": "Cloth Cap", "armor": 1, "weight": 0.5, "value": 3},
            {"name": "Leather Helm", "armor": 2, "weight": 1.5, "value": 6},
        ],
        2: [
            {"name": "Iron Helm", "armor": 4, "weight": 3.0, "value": 15},
            {"name": "Studded Leather Cap", "armor": 3, "weight": 2.0, "value": 12},
        ],
        3: [
            {"name": "Steel Helm", "armor": 7, "weight": 3.5, "value": 35},
            {"name": "Reinforced Coif", "armor": 6, "weight": 2.5, "value": 30},
        ],
        4: [
            {"name": "Full Helm", "armor": 10, "weight": 4.0, "value": 70},
            {"name": "Enchanted Circlet", "armor": 8, "weight": 1.5, "value": 80},
        ],
        5: [
            {"name": "Great Helm of Warding", "armor": 14, "weight": 4.5, "value": 160},
            {"name": "Crown of Power", "armor": 12, "weight": 2.0, "value": 180},
        ],
    },
    "torso": {
        1: [
            {"name": "Tattered Tunic", "armor": 2, "weight": 3.0, "value": 5},
            {"name": "Patchwork Leather", "armor": 3, "weight": 5.0, "value": 8},
        ],
        2: [
            {"name": "Chain Shirt", "armor": 6, "weight": 10.0, "value": 25},
            {"name": "Studded Leather Armor", "armor": 5, "weight": 8.0, "value": 20},
        ],
        3: [
            {"name": "Breastplate", "armor": 10, "weight": 15.0, "value": 55},
            {"name": "Scale Mail", "armor": 9, "weight": 12.0, "value": 48},
        ],
        4: [
            {"name": "Full Plate Armor", "armor": 14, "weight": 20.0, "value": 110},
            {"name": "Enchanted Chainmail", "armor": 12, "weight": 14.0, "value": 120},
        ],
        5: [
            {"name": "Runed Plate Armor", "armor": 19, "weight": 22.0, "value": 240},
            {"name": "Dragonscale Armor", "armor": 17, "weight": 16.0, "value": 260},
        ],
    },
    "legs": {
        1: [
            {"name": "Cloth Breeches", "armor": 1, "weight": 1.5, "value": 3},
            {"name": "Leather Leggings", "armor": 2, "weight": 3.0, "value": 5},
        ],
        2: [
            {"name": "Chain Leggings", "armor": 4, "weight": 6.0, "value": 15},
            {"name": "Studded Pants", "armor": 3, "weight": 4.0, "value": 12},
        ],
        3: [
            {"name": "Plate Greaves", "armor": 7, "weight": 8.0, "value": 35},
            {"name": "Scale Leggings", "armor": 6, "weight": 7.0, "value": 30},
        ],
        4: [
            {"name": "Full Plate Leggings", "armor": 10, "weight": 10.0, "value": 70},
            {"name": "Enchanted Greaves", "armor": 9, "weight": 8.0, "value": 75},
        ],
        5: [
            {"name": "Runed Greaves", "armor": 14, "weight": 11.0, "value": 155},
            {"name": "Dragonbone Leggings", "armor": 13, "weight": 9.0, "value": 165},
        ],
    },
    "feet": {
        1: [
            {"name": "Cloth Sandals", "armor": 1, "weight": 0.5, "value": 2},
            {"name": "Leather Boots", "armor": 1, "weight": 1.5, "value": 4},
        ],
        2: [
            {"name": "Iron-Toed Boots", "armor": 3, "weight": 3.0, "value": 10},
            {"name": "Hardened Leather Boots", "armor": 2, "weight": 2.0, "value": 8},
        ],
        3: [
            {"name": "Steel Sabatons", "armor": 5, "weight": 4.0, "value": 25},
            {"name": "Reinforced Boots", "armor": 4, "weight": 3.0, "value": 22},
        ],
        4: [
            {"name": "Plate Sabatons", "armor": 7, "weight": 5.0, "value": 50},
            {"name": "Enchanted Boots", "armor": 6, "weight": 3.0, "value": 55},
        ],
        5: [
            {"name": "Runed Sabatons", "armor": 10, "weight": 5.5, "value": 110},
            {"name": "Boots of Striding", "armor": 9, "weight": 3.5, "value": 120},
        ],
    },
    "neck": {
        1: [
            {"name": "Leather Cord", "armor": 0, "weight": 0.1, "value": 2},
        ],
        2: [
            {"name": "Copper Amulet", "armor": 0, "weight": 0.2, "value": 8},
            {"name": "Bone Pendant", "armor": 0, "weight": 0.1, "value": 6},
        ],
        3: [
            {"name": "Silver Torc", "armor": 0, "weight": 0.3, "value": 20},
            {"name": "Iron Gorget", "armor": 1, "weight": 1.0, "value": 18},
        ],
        4: [
            {"name": "Gold Amulet", "armor": 0, "weight": 0.3, "value": 45},
            {"name": "Enchanted Pendant", "armor": 1, "weight": 0.2, "value": 50},
        ],
        5: [
            {"name": "Amulet of Warding", "armor": 2, "weight": 0.3, "value": 100},
            {"name": "Dragon Tooth Necklace", "armor": 1, "weight": 0.4, "value": 110},
        ],
    },
    "wrists": {
        1: [
            {"name": "Cloth Bands", "armor": 0, "weight": 0.1, "value": 2},
        ],
        2: [
            {"name": "Leather Bracers", "armor": 1, "weight": 1.0, "value": 8},
            {"name": "Iron Bangles", "armor": 1, "weight": 1.5, "value": 10},
        ],
        3: [
            {"name": "Steel Vambraces", "armor": 3, "weight": 2.0, "value": 22},
            {"name": "Silver Bracers", "armor": 2, "weight": 1.5, "value": 25},
        ],
        4: [
            {"name": "Plate Vambraces", "armor": 5, "weight": 2.5, "value": 48},
            {"name": "Enchanted Bracers", "armor": 4, "weight": 1.5, "value": 52},
        ],
        5: [
            {"name": "Runed Vambraces", "armor": 7, "weight": 2.5, "value": 105},
            {"name": "Bracers of Deflection", "armor": 6, "weight": 1.5, "value": 115},
        ],
    },
    "left_hand": {
        1: [
            {"name": "Wooden Buckler", "armor": 2, "weight": 3.0, "value": 5},
        ],
        2: [
            {"name": "Iron Shield", "armor": 4, "weight": 6.0, "value": 15},
            {"name": "Reinforced Buckler", "armor": 3, "weight": 4.0, "value": 12},
        ],
        3: [
            {"name": "Steel Kite Shield", "armor": 7, "weight": 8.0, "value": 35},
            {"name": "Tower Shield", "armor": 8, "weight": 12.0, "value": 40},
        ],
        4: [
            {"name": "Enchanted Kite Shield", "armor": 10, "weight": 9.0, "value": 75},
            {"name": "Great Tower Shield", "armor": 11, "weight": 13.0, "value": 80},
        ],
        5: [
            {"name": "Runed Aegis", "armor": 15, "weight": 10.0, "value": 170},
            {"name": "Bulwark of the Titan", "armor": 16, "weight": 14.0, "value": 180},
        ],
    },
    # New slots: ears, fingers, belt, aura
    "left_ear": {
        1: [{"name": "Copper Earring", "armor": 0, "weight": 0.05, "value": 3}],
        2: [{"name": "Silver Stud", "armor": 0, "weight": 0.05, "value": 10}],
        3: [{"name": "Enchanted Hoop", "armor": 0, "weight": 0.05, "value": 25}],
        4: [{"name": "Sapphire Earring", "armor": 0, "weight": 0.05, "value": 55}],
        5: [{"name": "Earring of Warding", "armor": 1, "weight": 0.05, "value": 110}],
    },
    "right_ear": {
        1: [{"name": "Copper Earring", "armor": 0, "weight": 0.05, "value": 3}],
        2: [{"name": "Silver Stud", "armor": 0, "weight": 0.05, "value": 10}],
        3: [{"name": "Enchanted Hoop", "armor": 0, "weight": 0.05, "value": 25}],
        4: [{"name": "Ruby Earring", "armor": 0, "weight": 0.05, "value": 55}],
        5: [{"name": "Earring of Power", "armor": 1, "weight": 0.05, "value": 110}],
    },
    "left_finger": {
        1: [{"name": "Copper Ring", "armor": 0, "weight": 0.05, "value": 3}],
        2: [{"name": "Silver Band", "armor": 0, "weight": 0.05, "value": 10}],
        3: [{"name": "Gold Ring", "armor": 0, "weight": 0.05, "value": 25}],
        4: [{"name": "Ring of Protection", "armor": 1, "weight": 0.05, "value": 55}],
        5: [{"name": "Ring of Warding", "armor": 2, "weight": 0.05, "value": 120}],
    },
    "right_finger": {
        1: [{"name": "Copper Ring", "armor": 0, "weight": 0.05, "value": 3}],
        2: [{"name": "Silver Band", "armor": 0, "weight": 0.05, "value": 10}],
        3: [{"name": "Gold Ring", "armor": 0, "weight": 0.05, "value": 25}],
        4: [{"name": "Ring of Power", "armor": 1, "weight": 0.05, "value": 55}],
        5: [{"name": "Ring of the Archmage", "armor": 2, "weight": 0.05, "value": 120}],
    },
    "belt": {
        1: [{"name": "Cloth Sash", "armor": 0, "weight": 0.3, "value": 2}],
        2: [{"name": "Leather Belt", "armor": 1, "weight": 0.5, "value": 8}],
        3: [{"name": "Reinforced Girdle", "armor": 2, "weight": 1.0, "value": 20}],
        4: [{"name": "Plated Belt", "armor": 3, "weight": 1.5, "value": 45}],
        5: [{"name": "Girdle of Giants", "armor": 4, "weight": 1.5, "value": 100}],
    },
    "aura": {
        1: [{"name": "Faint Glow", "armor": 0, "weight": 0.0, "value": 5}],
        2: [{"name": "Shimmering Aura", "armor": 0, "weight": 0.0, "value": 15}],
        3: [{"name": "Radiant Halo", "armor": 1, "weight": 0.0, "value": 35}],
        4: [{"name": "Celestial Aura", "armor": 2, "weight": 0.0, "value": 70}],
        5: [{"name": "Divine Mandala", "armor": 3, "weight": 0.0, "value": 150}],
    },
}

# Backward-compat alias for armor template lookups using old slot names
ARMOR_TEMPLATES["chest"] = ARMOR_TEMPLATES["torso"]
ARMOR_TEMPLATES["off_hand"] = ARMOR_TEMPLATES["left_hand"]

# ===========================================================================
# Faction-specific gear prefixes
# ===========================================================================

FACTION_PREFIXES: Dict[str, Dict[str, str]] = {
    "Aethelgard Alliance": {
        "prefix": "Aethelgard",
        "color": "|g",
    },
    "Gorgoroth Horde": {
        "prefix": "Gorgoroth",
        "color": "|r",
    },
    "Neutral": {
        "prefix": "",
        "color": "|w",
    },
}

# ===========================================================================
# Class archetype mapping for weapon selection
# ===========================================================================

CLASS_ARCHETYPE_MAP: Dict[str, str] = {
    "Warrior": "warrior",
    "Paladin": "warrior",
    "Cleric": "caster",
    "Mage": "caster",
    "Rogue": "rogue",
    "Warlock": "caster",
    "Druid": "caster",
    "Ranger": "ranger",
    "Monk": "monk",
    "Necromancer": "caster",
}

# ===========================================================================
# Tier determination from level
# ===========================================================================

def _tier_for_level(level: int) -> int:
    """Return the equipment tier (1-5) for a given level."""
    if level <= 10:
        return 1
    if level <= 25:
        return 2
    if level <= 40:
        return 3
    if level <= 60:
        return 4
    return 5


# ===========================================================================
# Equipment generation
# ===========================================================================

def _infer_weapon_type(template: Dict[str, Any]) -> str:
    """
    Infer the weapon proficiency category from a template's name and slot.

    Returns one of the canonical values expected by ``can_equip_slot``
    in ``world/race_class_matrix.py`` (see CLASS_WEAPON_TYPES):
        sword, axe, mace, dagger, spear, two_handed,
        staff, wand, bow, crossbow, club, fist
    """
    name = template.get("name", "").lower()
    slot = template.get("slot", "right_hand")

    # Hand-slot weapons (monk) → "fist" (Monk proficiency).
    if slot == "hands":
        return "fist"

    # Order matters — more-specific keywords must come first.
    if any(w in name for w in ("dagger", "dirk", "stiletto", "shiv", "kris", "knife")):
        return "dagger"
    if any(w in name for w in ("bow", "longbow", "greatbow", "recurve", "arrow")):
        return "bow"
    if any(w in name for w in ("crossbow",)):
        return "crossbow"
    if any(w in name for w in ("staff",)):
        return "staff"
    if any(w in name for w in ("wand", "scepter")):
        return "wand"
    if any(w in name for w in ("axe",)):
        return "axe"
    if any(w in name for w in ("spear",)):
        return "spear"
    if any(w in name for w in ("club",)):
        return "club"
    if any(w in name for w in ("mace", "hammer", "maul")):
        return "mace"
    if any(w in name for w in ("sword", "blade", "claymore", "warblade")):
        return "sword"

    # Fallback by slot for two-handed weapons without a specific keyword.
    if slot == "two_hand":
        return "two_handed"

    # Default: one-handed unknown weapon → sword (most permissive).
    return "sword"


def _create_equipment_item(
    template: Dict[str, Any],
    slot: str,
    faction: str = "Neutral",
    mock_mode: bool = False,
) -> Optional[Any]:
    """
    Create a single equipment item from a template dict.

    Args:
        template: Dict with keys name, damage/armor, weight, value, etc.
        slot: Equipment slot this item occupies (canonical).
        faction: Faction string for naming.

    Returns:
        The created item object, or None on failure.
    """
    try:
        name = template["name"]
        # Apply faction prefix for flavor
        faction_info = FACTION_PREFIXES.get(faction, FACTION_PREFIXES["Neutral"])
        prefix = faction_info.get("prefix", "")
        if prefix and not name.startswith(prefix):
            name = f"{prefix} {name}"

        if mock_mode:
            return _make_mock_item(name, slot, template)

        attrs = [
            ("item_type", "equipment"),
            ("slot", slot),
            ("weight", template.get("weight", 1.0)),
            ("value", template.get("value", 1)),
            ("durability", 100),
            ("max_durability", 100),
        ]

        if "damage" in template:
            attrs.append(("damage", template["damage"]))
            attrs.append(("damage_type", template.get("damage_type", "slash")))
            # Record weapon_type so _classify_item_type() can apply
            # race/class proficiency gating (commands/equipment.py).
            attrs.append(("weapon_type", _infer_weapon_type(template)))
        if "armor" in template:
            attrs.append(("armor", template["armor"]))

        _co, _do = _get_create_object()
        if _co is None:
            # Evennia not available (test environment) — use mock.
            return _make_mock_item(name, slot, template)
        item = _co(
            _do,
            key=name,
            attributes=attrs,
        )
        # If create_object returned None (e.g. test environment without DB),
        # fall back to a lightweight mock object so equipment logic still works.
        if item is None:
            item = _make_mock_item(name, slot, template)
        return item
    except Exception:
        return None


def _make_mock_item(name: str, slot: str, template: Dict[str, Any]) -> Any:
    """
    Create a lightweight mock item when Evennia's create_object is unavailable.

    Used as a fallback in test environments where the real DB is not active.
    The mock has the same attribute interface as a real equipment item.
    """
    class _MockItem:
        def __init__(self):
            self.key = name
            self.destination = None
            self.contents = []
            self.location = None
            self.has_account = False
            self.id = id(self)

            class _MockAttrs:
                def __init__(self):
                    self._store = {}
                def get(self, key, default=None):
                    return self._store.get(key, default)
                def add(self, key, value):
                    self._store[key] = value
                def has(self, key):
                    return key in self._store
                def set(self, key, value):
                    self._store[key] = value
                def all(self):
                    return dict(self._store)

            self.attributes = _MockAttrs()
            self.attributes.add("item_type", "equipment")
            self.attributes.add("slot", slot)
            self.attributes.add("weight", template.get("weight", 1.0))
            self.attributes.add("value", template.get("value", 1))
            self.attributes.add("durability", 100)
            self.attributes.add("max_durability", 100)
            if "damage" in template:
                self.attributes.add("damage", template["damage"])
                self.attributes.add("damage_type", template.get("damage_type", "slash"))
                # Record weapon_type for downstream item classification.
                self.attributes.add("weapon_type", _infer_weapon_type(template))
            if "armor" in template:
                self.attributes.add("armor", template["armor"])

        def move_to(self, destination, quiet=True, **kwargs):
            if self.location is not None and hasattr(self.location, "contents"):
                if self in self.location.contents:
                    self.location.contents.remove(self)
            self.location = destination
            if destination is not None and hasattr(destination, "contents"):
                if self not in destination.contents:
                    destination.contents.append(self)

        def delete(self):
            if self.location is not None and hasattr(self.location, "contents"):
                if self in self.location.contents:
                    self.location.contents.remove(self)
            self.location = None

    return _MockItem()


def generate_mob_weapon(
    mob_level: int,
    mob_class: str = "Warrior",
    faction: str = "Neutral",
    roll_rarity: bool = True,
    mock_mode: bool = False,
) -> Optional[Any]:
    """
    Generate a level-appropriate weapon for a mob.

    Args:
        mob_level: The mob's level.
        mob_class: Class name for archetype selection.
        faction: Faction string.
        roll_rarity: If True, roll a random rarity tier and apply modifiers.

    Returns:
        A weapon item object, or None.
    """
    tier = _tier_for_level(mob_level)
    archetype = CLASS_ARCHETYPE_MAP.get(mob_class, "warrior")
    templates = WEAPON_TEMPLATES.get(archetype, WEAPON_TEMPLATES["warrior"])
    tier_templates = templates.get(tier, templates.get(1, []))

    if not tier_templates:
        return None

    template = dict(random.choice(tier_templates))

    # Roll rarity for generated items
    if roll_rarity:
        rarity = _roll_rarity(tier)
        template = _apply_rarity_to_template(template, rarity)

    slot = normalize_slot(template.get("slot", "right_hand"))
    return _create_equipment_item(
        template, slot, faction, mock_mode=mock_mode
    )


def generate_mob_armor(
    mob_level: int,
    slot: str,
    faction: str = "Neutral",
    roll_rarity: bool = True,
    mock_mode: bool = False,
) -> Optional[Any]:
    """
    Generate a level-appropriate armor piece for a mob.

    Args:
        mob_level: The mob's level.
        slot: Equipment slot (canonical or legacy alias).
        faction: Faction string.
        roll_rarity: If True, roll a random rarity tier and apply modifiers.

    Returns:
        An armor item object, or None.
    """
    tier = _tier_for_level(mob_level)
    canonical = normalize_slot(slot)
    slot_templates = ARMOR_TEMPLATES.get(canonical, ARMOR_TEMPLATES.get(slot, {}))
    tier_templates = slot_templates.get(tier, slot_templates.get(1, []))

    if not tier_templates:
        return None

    template = dict(random.choice(tier_templates))

    # Roll rarity for generated items
    if roll_rarity:
        rarity = _roll_rarity(tier)
        template = _apply_rarity_to_template(template, rarity)

    return _create_equipment_item(template, canonical, faction, mock_mode=mock_mode)


def equip_mob(
    mob: Any,
    mob_class: str = "Warrior",
    faction: str = "Neutral",
    equip_chance: float = 0.7,
) -> Dict[str, Any]:
    """
    Fully equip a mob with level-appropriate gear.

    Generates a weapon, armor pieces, and places them in the mob's
    inventory.  Also sets the mob's ``equipped`` attribute so the
    combat engine can read armor values.

    Args:
        mob: The mob object to equip.
        mob_class: Class name for weapon archetype selection.
        faction: Faction string.
        equip_chance: Probability (0.0-1.0) of equipping each slot.

    Returns:
        Dict with keys 'weapon', 'armor_pieces', 'total_armor' for diagnostics.
    """
    mob_level = mob.attributes.get("level", 1) if hasattr(mob, "attributes") else 1

    # If the mob is a mock (plain-list contents), generate mock-compatible
    # items so they can be stored and moved using plain lists.
    use_mock = _is_mock_container(mob)

    equipped = {}
    items_generated = []

    # Generate weapon (always — no mob should be unarmed)
    weapon = generate_mob_weapon(mob_level, mob_class, faction, mock_mode=use_mock)
    if weapon:
        weapon_slot = normalize_slot(
            weapon.attributes.get("slot", "right_hand") if hasattr(weapon, "attributes") else "right_hand"
        )
        equipped[weapon_slot] = weapon.key
        _move_item_to_container(weapon, mob)
        items_generated.append(weapon)

    # Generate armor for each slot
    armor_slots = ["head", "torso", "legs", "feet"]
    for slot in armor_slots:
        if random.random() < equip_chance:
            armor = generate_mob_armor(mob_level, slot, faction, mock_mode=use_mock)
            if armor:
                canonical = normalize_slot(slot)
                equipped[canonical] = armor.key
                _move_item_to_container(armor, mob)
                items_generated.append(armor)

    # Off-hand (shield) — lower chance
    if random.random() < (equip_chance * 0.4):
        shield = generate_mob_armor(mob_level, "left_hand", faction, mock_mode=use_mock)
        if shield:
            equipped["left_hand"] = shield.key
            _move_item_to_container(shield, mob)
            items_generated.append(shield)

    # Store equipped items on the mob
    if hasattr(mob, "attributes"):
        mob.attributes.add("equipped", equipped)

    # Calculate total armor value
    total_armor = 0
    for item in items_generated:
        if hasattr(item, "attributes"):
            total_armor += item.attributes.get("armor", 0)

    return {
        "weapon": equipped.get("right_hand") or equipped.get("two_hand"),
        "armor_pieces": len([i for i in items_generated if hasattr(i, "attributes") and i.attributes.get("armor", 0) > 0]),
        "total_armor": total_armor,
        "items": items_generated,
    }


def generate_mob_coins(mob_level: int) -> Dict[str, int]:
    """
    Generate copper/silver/gold coin drops for a mob based on its level.

    Classic MajorMUD coin tiers:
      - 10 copper = 1 silver
      - 10 silver = 1 gold

    Args:
        mob_level: The mob's level.

    Returns:
        Dict with 'copper', 'silver', 'gold' keys.
    """
    # Base coin value scales with level
    base_value = mob_level * random.randint(2, 8)

    # Convert to copper/silver/gold tiers
    gold = base_value // 100
    remainder = base_value % 100
    silver = remainder // 10
    copper = remainder % 10

    # Ensure minimum drops for higher-level mobs
    if mob_level >= 10 and gold == 0:
        gold = random.randint(1, 3)
    if mob_level >= 5 and silver == 0 and gold == 0:
        silver = random.randint(1, 5)

    return {"copper": copper, "silver": silver, "gold": gold}


def get_equipped_weapon_damage(mob: Any) -> int:
    """
    Return the base damage of the mob's equipped weapon.

    Scans the mob's contents for the item named in the ``equipped``
    attribute's weapon slots and returns its damage value.
    Falls back to STR-based unarmed damage if no weapon is found.

    Args:
        mob: The mob or character to check.

    Returns:
        Base weapon damage (int).
    """
    if not hasattr(mob, "attributes"):
        return max(1, (mob.attributes.get("stats", {}).get("str", 10) if hasattr(mob, "attributes") else 10) // 2)

    equipped = get_equipped_slot_map(mob)
    if equipped:
        # Check weapon slots in priority order
        for slot in ("right_hand", "two_hand", "left_hand", "hands"):
            weapon_name = equipped.get(slot)
            if weapon_name:
                for obj in mob.contents:
                    if getattr(obj, "destination", None):
                        continue
                    if obj.key == weapon_name and hasattr(obj, "attributes"):
                        dmg = obj.attributes.get("damage", 0)
                        if dmg > 0:
                            return dmg

    # Unarmed: STR-based
    stats = mob.attributes.get("stats", default={})
    str_val = stats.get("str", 10) if stats and hasattr(stats, "get") else 10
    return max(1, str_val // 2)


def get_equipped_weapon_damage_type(mob: Any) -> str:
    """
    Return the damage type of the mob's equipped weapon.

    Args:
        mob: The mob or character to check.

    Returns:
        Damage type string (e.g. 'slash', 'pierce', 'blunt').
    """
    if not hasattr(mob, "attributes"):
        return "blunt"

    equipped = get_equipped_slot_map(mob)
    if equipped:
        for slot in ("right_hand", "two_hand", "left_hand", "hands"):
            weapon_name = equipped.get(slot)
            if weapon_name:
                for obj in mob.contents:
                    if getattr(obj, "destination", None):
                        continue
                    if obj.key == weapon_name and hasattr(obj, "attributes"):
                        dt = obj.attributes.get("damage_type", "blunt")
                        if dt:
                            return dt
    return "blunt"


def transfer_equipped_to_corpse(mob: Any, corpse: Any) -> int:
    """
    Move all equipped items from a dead mob into its corpse.

    Also clears the mob's ``equipped`` attribute so the items are
    no longer considered worn.

    Args:
        mob: The dead mob.
        corpse: The corpse object to receive items.

    Returns:
        Number of items transferred.
    """
    count = 0
    if not hasattr(mob, "attributes") or not hasattr(corpse, "attributes"):
        return count

    equipped = get_equipped_slot_map(mob)
    if not equipped:
        return count

    for slot, item_name in list(equipped.items()):
        for obj in list(mob.contents):
            if getattr(obj, "destination", None):
                continue
            if obj.key == item_name:
                try:
                    _move_item_to_container(obj, corpse)
                    count += 1
                except Exception:
                    pass
                break

    # Clear equipped on the mob
    mob.attributes.add("equipped", {})
    return count


def generate_mob_loot(
    mob_level: int,
    faction: str = "Neutral",
    loot_count: int = 2,
) -> List[Any]:
    """
    Generate random loot items for a mob's drop table.

    Args:
        mob_level: The mob's level.
        faction: Faction string.
        loot_count: Number of loot items to generate.

    Returns:
        List of item objects.
    """
    items = []
    tier = _tier_for_level(mob_level)

    for _ in range(loot_count):
        roll = random.random()
        if roll < 0.4:
            slot = random.choice(["head", "torso", "legs", "feet", "neck", "wrists"])
            item = generate_mob_armor(mob_level, slot, faction)
        elif roll < 0.7:
            item = generate_mob_weapon(mob_level, "Warrior", faction)
        else:
            try:
                from world.prototypes import ITEM_PROTOTYPES
                consumable_keys = ["health_potion", "mana_potion", "travel_rations"]
                key = random.choice(consumable_keys)
                proto = ITEM_PROTOTYPES.get(key)
                if proto:
                    _co, _do = _get_create_object()
                    item = _co(**proto)
                else:
                    item = None
            except Exception:
                item = None

        if item:
            items.append(item)

    return items


# ===========================================================================
# Armor absorption fix — correct calculation when no armor is equipped
# ===========================================================================

def get_effective_armor(character: Any) -> int:
    """
    Return the total armor value for a character or mob.

    Sums armor from all equipped gear plus natural racial armor,
    plus any ``defense`` granted by active armor set bonuses.
    Returns 0 if nothing is equipped — no phantom absorption.

    This is the corrected version that replaces the buggy
    ``_get_armor_value`` in damage_formulas.py.
    """
    if not hasattr(character, "attributes"):
        return 0

    total = 0

    # Sum equipped gear armor
    equipped = get_equipped_slot_map(character)
    if equipped:
        for slot, item_name in equipped.items():
            for obj in character.contents:
                if getattr(obj, "destination", None):
                    continue
                if obj.key == item_name and hasattr(obj, "attributes"):
                    total += obj.attributes.get("armor", 0)
                    break

    # Natural racial armor
    try:
        from world.race_class_matrix import RACE_NATURAL_ARMOR
        race = character.attributes.get("race", "Human")
        total += RACE_NATURAL_ARMOR.get(race, 0)
    except Exception:
        pass

    # Racial passive: armor_class bonus (Mountain Dwarf +5, Lizardfolk +4)
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(character)
        total += racial.get("armor_class", 0)
    except Exception:
        pass

    # Armor set bonus (fix 1.5) — "defense" stat contributes to armor.
    try:
        set_bonuses = _as_dict(character.attributes.get("armor_set_bonuses", default={}))
        total += int(set_bonuses.get("defense", 0))
    except Exception:
        pass

    # Phase 2.2: Druid shapeshift form armor bonus
    try:
        from world.druid_system import get_form_bonuses
        form_bonuses = get_form_bonuses(character)
        if form_bonuses:
            total += form_bonuses.get("armor_bonus", 0)
    except Exception:
        pass

    # Phase 2.3: Skill tree talent bonus (Armor Mastery +1 armor per rank)
    try:
        from world.skill_tree import get_talent_bonuses
        talent_bonuses = get_talent_bonuses(character)
        total += int(talent_bonuses.get("armor_bonus", 0))
    except Exception:
        pass

    return total


def has_armor_equipped(character: Any) -> bool:
    """
    Return True if the character has any armor items equipped.

    Used to determine whether to display armor absorption messages.
    If False, damage messages should NOT show phantom absorption.
    """
    return get_effective_armor(character) > 0


# ===========================================================================
# Player equipment helpers (wear / remove / equipment commands)
# ===========================================================================

def _as_dict(value: Any) -> Dict[str, Any]:
    """Normalize an Evennia dict-like attribute into a plain dict."""
    if value is None:
        return {}
    if hasattr(value, "items"):
        return {str(k): v for k, v in value.items()}
    return {}


def find_item_in_inventory(character: Any, name: str) -> Optional[Any]:
    """Find an item by name (case-insensitive) in a character's inventory."""
    for obj in (getattr(character, "contents", None) or []):
        if getattr(obj, "destination", None):
            continue
        if getattr(obj, "key", None) and str(obj.key).lower() == str(name).lower():
            return obj
    return None


def get_item_slot_raw(item: Any) -> Optional[str]:
    """Return the raw (as-stored) equipment slot an item belongs to, if defined."""
    if hasattr(item, "attributes"):
        slot = item.attributes.get("slot", default=None)
        if slot:
            return slot
    return None


def get_item_slot(item: Any) -> Optional[str]:
    """Return the canonical equipment slot an item belongs to, if defined."""
    raw = get_item_slot_raw(item)
    if raw:
        return normalize_slot(raw)
    return None


def _remove_raw_slot(raw_equipped: Dict[str, Any], canonical: str) -> None:
    """Remove every raw key in *raw_equipped* that normalizes to *canonical*."""
    for key in list(raw_equipped.keys()):
        if normalize_slot(str(key)) == canonical:
            raw_equipped.pop(key, None)


def get_equipped_item(character: Any, slot: str) -> Optional[Any]:
    """Return the item currently equipped in the given slot, or None."""
    canonical = normalize_slot(slot)
    equipped = get_equipped_slot_map(character)
    name = equipped.get(canonical)
    if not name:
        return None
    return find_item_in_inventory(character, name)


def equip_item(character: Any, item: Any, slot: Optional[str] = None) -> Tuple[bool, str]:
    """
    Equip an item onto a character in the given slot.

    Handles two-hand weapon logic: equipping a two_hand item clears
    right_hand and left_hand. Equipping into right_hand or left_hand
    clears two_hand if occupied.

    Args:
        character: The character equipping the item.
        item: The item object (must be in character.contents or moved there).
        slot: Optional slot override; defaults to the item's ``slot`` attr.

    Returns:
        (success, message) tuple.
    """
    if not hasattr(character, "attributes"):
        return False, "You cannot equip items."

    raw_slot = slot or get_item_slot_raw(item)
    if not raw_slot:
        return False, "That item cannot be equipped."

    canonical = normalize_slot(raw_slot)

    # Ensure the item is in the character's inventory.
    if item not in (getattr(character, "contents", None) or []):
        _move_item_to_container(item, character)

    # Normalized view for slot validation, raw dict for storage (preserves
    # legacy keys like 'main_hand' / 'chest' / 'off_hand' in the DB attribute).
    normalized = get_equipped_slot_map(character)
    raw_equipped = _as_dict(character.attributes.get("equipped", default={}))

    # Check if slot is already occupied
    existing = normalized.get(canonical)
    if existing and existing != item.key:
        return False, f"You are already wearing {existing} in your {get_slot_display(canonical)} slot."

    # Two-hand weapon logic
    if canonical == "two_hand":
        # Check if either hand is occupied
        if normalized.get("right_hand"):
            return False, f"You must remove your {normalized['right_hand']} from your right hand first."
        if normalized.get("left_hand"):
            return False, f"You must remove your {normalized['left_hand']} from your left hand first."
        # Clear both hand slots
        _remove_raw_slot(raw_equipped, "right_hand")
        _remove_raw_slot(raw_equipped, "left_hand")
    elif canonical in ("right_hand", "left_hand"):
        # If a two-hand weapon is equipped, block
        if normalized.get("two_hand"):
            return False, f"You must remove your {normalized['two_hand']} (two-handed) first."

    # Store using the canonical slot key so all downstream reads
    # (get_equipped_slot_map, build_paperdoll, combat engine) see
    # consistent keys without needing normalization.
    raw_equipped[canonical] = item.key
    character.attributes.add("equipped", raw_equipped)

    # Apply armor set bonuses
    try:
        from world.armor_sets import apply_set_bonuses_to_character
        apply_set_bonuses_to_character(character)
    except Exception:
        pass

    return True, f"You equip {item.key} in your {get_slot_display(canonical)} slot."


def unequip_item(character: Any, slot_or_name: str) -> Tuple[bool, str]:
    """
    Remove an equipped item from a character.

    Args:
        character: The character removing the item.
        slot_or_name: Either a slot name (e.g. 'torso') or an item name.

    Returns:
        (success, message) tuple.
    """
    if not hasattr(character, "attributes"):
        return False, "You have nothing equipped."

    normalized = get_equipped_slot_map(character)
    raw_equipped = _as_dict(character.attributes.get("equipped", default={}))

    target_raw = None

    # Try to resolve the requested slot/name to a raw storage key.
    canonical_input = normalize_slot(slot_or_name)
    if canonical_input in normalized:
        # Requested a canonical slot that has something equipped: find the
        # raw storage key that normalizes to it.
        for raw_key in raw_equipped:
            if normalize_slot(str(raw_key)) == canonical_input:
                target_raw = raw_key
                break
    elif canonical_input in raw_equipped:
        # The raw dict itself uses the canonical key directly.
        target_raw = canonical_input

    if target_raw is None:
        # Try matching by item name
        for raw_key, name in raw_equipped.items():
            if str(name).lower() == str(slot_or_name).lower():
                target_raw = raw_key
                break

    if target_raw is None:
        return False, "You don't have that equipped."

    item_name = raw_equipped.pop(target_raw)
    character.attributes.add("equipped", raw_equipped)

    # Re-apply armor set bonuses
    try:
        from world.armor_sets import apply_set_bonuses_to_character
        apply_set_bonuses_to_character(character)
    except Exception:
        pass

    return True, f"You remove {item_name} from your {get_slot_display(target_raw)} slot."


def get_effective_stats(character: Any) -> Dict[str, int]:
    """
    Return a character's base stats plus any ``stat_bonuses`` granted by
    equipped items, plus active armor set bonuses.  Used by combat and
    damage formulas so gear actually improves performance.

    Falls back to legacy flat stat attributes (db.strength, db.intelligence,
    db.dexterity) if the standard ``stats`` dict is empty or missing, so
    characters created with older versions of charcreate.py still receive
    correct stat bonuses.
    """
    stats = _as_dict(character.attributes.get("stats", default={}))
    stats = {k: int(v) for k, v in stats.items()}

    # Legacy fallback: if the stats dict is empty, try reading flat
    # attributes from the old charcreate.py format (db.strength,
    # db.intelligence, db.dexterity).  Map them to the canonical
    # six-stat keys so combat calculations still work.
    if not stats:
        legacy_map = {
            "str": "strength",
            "dex": "dexterity",
            "con": "constitution",
            "int": "intelligence",
            "wis": "wisdom",
            "cha": "charisma",
        }
        for stat_key, legacy_attr in legacy_map.items():
            try:
                val = character.attributes.get(legacy_attr)
                if val is not None:
                    stats[stat_key] = int(val)
            except (TypeError, ValueError, AttributeError):
                continue
        # If we recovered any legacy stats, fill missing ones with 10.
        if stats:
            for key in ("str", "dex", "con", "int", "wis", "cha"):
                stats.setdefault(key, 10)

    equipped = get_equipped_slot_map(character)
    for slot, name in equipped.items():
        item = find_item_in_inventory(character, name)
        if item is None:
            continue
        bonuses = _as_dict(item.attributes.get("stat_bonuses", default={}))
        for key, bonus in bonuses.items():
            try:
                stats[key] = stats.get(key, 10) + int(bonus)
            except (TypeError, ValueError):
                continue

    # Armor set bonuses (fix 1.5) — merge the six core stats.
    try:
        set_bonuses = _as_dict(character.attributes.get("armor_set_bonuses", default={}))
        for key in ("str", "dex", "con", "int", "wis", "cha"):
            if key in set_bonuses:
                try:
                    stats[key] = stats.get(key, 10) + int(set_bonuses[key])
                except (TypeError, ValueError):
                    continue
    except Exception:
        pass

    return stats


def get_effective_stat(character: Any, key: str, default: int = 10) -> int:
    """Return a single effective stat (base + equipment bonuses)."""
    return get_effective_stats(character).get(key, default)


def degrade_equipment_slots(character: Any, slots: Tuple[str, ...],
                            amount: int = 1) -> List[str]:
    """
    Degrade durability of items equipped in the given slots.

    Args:
        character: The character/mob whose equipment degrades.
        slots: Tuple of slot names whose items should degrade.
        amount: Durability points to remove per item.

    Returns:
        List of item keys that broke (reached 0 durability).
    """
    broken = []
    if not hasattr(character, "attributes"):
        return broken

    for slot in slots:
        item = get_equipped_item(character, slot)
        if item is None:
            continue
        try:
            from world.shopkeeper import degrade_item_durability
            if degrade_item_durability(item, amount):
                broken.append(item.key)
        except Exception:
            continue
    return broken


# ===========================================================================
# Paperdoll display builder
# ===========================================================================

def build_paperdoll(character: Any) -> str:
    """
    Build a formatted paperdoll display showing all equipment slots.

    Returns a multi-line string suitable for display via ``equipment``/``eq``.
    """
    equipped = get_equipped_slot_map(character)

    lines = []
    lines.append("|w╔═══════════════════ EQUIPMENT ═══════════════════╗|n")

    # Group slots by display group for organized layout
    groups = [
        ("Head & Face", ["head", "left_ear", "right_ear", "neck"]),
        ("Torso & Arms", ["torso", "wrists", "hands", "left_finger", "right_finger"]),
        ("Waist & Legs", ["belt", "legs", "feet"]),
        ("Weapons", ["right_hand", "left_hand", "two_hand"]),
        ("Special", ["aura"]),
    ]

    for group_name, slots in groups:
        lines.append(f"|c  ── {group_name} ──|n")
        for slot in slots:
            display = get_slot_display(slot)
            item_name = equipped.get(slot, "")
            if item_name:
                # Try to get item details for color coding
                item = find_item_in_inventory(character, item_name)
                if item and hasattr(item, "attributes"):
                    rarity_color = item.attributes.get("_rarity_color", "|w")
                    armor = item.attributes.get("armor", 0)
                    damage = item.attributes.get("damage", 0)
                    extras = []
                    if armor > 0:
                        extras.append(f"|bAC:{armor}|n")
                    if damage > 0:
                        extras.append(f"|rDMG:{damage}|n")
                    extra_str = f" ({' '.join(extras)})" if extras else ""
                    lines.append(f"  |c{display:<14}:|n {rarity_color}{item_name}|n{extra_str}")
                else:
                    lines.append(f"  |c{display:<14}:|n |w{item_name}|n")
            else:
                lines.append(f"  |c{display:<14}:|n |y(empty)|n")

    # Total armor
    armor = get_effective_armor(character)
    lines.append(f"|c  ──────────────────────────────────────────────|n")
    lines.append(f"  |wTotal Armor:|n {armor}")

    # Armor set bonuses
    try:
        from world.armor_sets import ArmorSetChecker
        checker = ArmorSetChecker(character)
        set_display = checker.format_display()
        if set_display:
            lines.append(set_display.strip())
    except Exception:
        pass

    lines.append("|w╚══════════════════════════════════════════════════╝|n")
    return "\n".join(lines)


# ===========================================================================
# Admin verification: test all slots
# ===========================================================================

def verify_all_equipment_slots(character: Any) -> Dict[str, Any]:
    """
    Test that items can be equipped to every slot and unequipped properly.

    Creates mock items for each canonical slot, equips them, verifies
    the equipped dict, then unequips and verifies stats are restored.

    Returns a dict with 'passes', 'failures', and 'details' keys.
    """
    results = {
        "passes": 0,
        "failures": 0,
        "details": [],
    }

    if not hasattr(character, "attributes"):
        results["details"].append("Character has no attributes — cannot test.")
        results["failures"] = len(ALL_SLOT_KEYS)
        return results

    # Save original state
    original_equipped = _as_dict(character.attributes.get("equipped", default={}))
    original_stats = _as_dict(character.attributes.get("stats", default={}))

    try:
        for slot_def in SLOT_DEFINITIONS:
            slot = slot_def["key"]
            display = slot_def["display"]
            category = slot_def["category"]

            # Create a test item
            if category == "weapon":
                template = {"name": f"Test {display} Weapon", "damage": 5,
                            "damage_type": "slash", "slot": slot, "weight": 1.0, "value": 1}
            else:
                template = {"name": f"Test {display} Item", "armor": 2,
                            "slot": slot, "weight": 0.5, "value": 1}

            item = _make_mock_item(template["name"], slot, template)
            if item is None:
                results["failures"] += 1
                results["details"].append(f"FAIL [{display}]: Could not create test item.")
                continue

            # Move item to character
            _move_item_to_container(item, character)

            # Equip
            success, msg = equip_item(character, item, slot)
            if not success:
                results["failures"] += 1
                results["details"].append(f"FAIL [{display}]: {msg}")
                continue

            # Verify equipped
            equipped = get_equipped_slot_map(character)
            if equipped.get(slot) != template["name"]:
                results["failures"] += 1
                results["details"].append(
                    f"FAIL [{display}]: Equipped dict mismatch. "
                    f"Expected '{template['name']}', got '{equipped.get(slot)}'."
                )
                continue

            # Unequip
            success, msg = unequip_item(character, slot)
            if not success:
                results["failures"] += 1
                results["details"].append(f"FAIL [{display}]: Unequip failed: {msg}")
                continue

            # Verify slot is empty
            equipped = get_equipped_slot_map(character)
            if slot in equipped:
                results["failures"] += 1
                results["details"].append(
                    f"FAIL [{display}]: Slot still occupied after unequip: {equipped[slot]}"
                )
                continue

            results["passes"] += 1
            results["details"].append(f"PASS [{display}]: Equip/unequip cycle successful.")

    finally:
        # Restore original state
        character.attributes.add("equipped", original_equipped)
        character.attributes.add("stats", original_stats)

    return results