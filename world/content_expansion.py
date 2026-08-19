"""
Content Expansion Module for 'rop' — Phase 3.4
===============================================
Programmatically generates scaled items and mobs across all level tiers
to reach target density: 200+ items, 150+ mobs.

Called at server init to populate ITEM_PROTOTYPES and MOB_PROTOTYPES
in world.prototypes with level-appropriate, statted content.

Generation rules:
  - Items scale with tier: damage/armor/value increase per level bracket
  - Mobs scale with level: stats, HP, XP, gold all derived from level
  - Each tier gets weapons, armor pieces, consumables, and mobs
  - Named items have unique flavor and stat bonuses
"""

from __future__ import annotations

import random
from typing import Any, Dict, List


# ===========================================================================
# ITEM GENERATION
# ===========================================================================

# Weapon base templates by type
WEAPON_TEMPLATES = {
    "sword": {"slot": "main_hand", "damage_type": "slash", "weight_base": 5.0, "value_base": 50},
    "axe": {"slot": "main_hand", "damage_type": "slash", "weight_base": 7.0, "value_base": 55},
    "mace": {"slot": "main_hand", "damage_type": "blunt", "weight_base": 6.0, "value_base": 45},
    "dagger": {"slot": "main_hand", "damage_type": "pierce", "weight_base": 2.0, "value_base": 35},
    "staff": {"slot": "two_hand", "damage_type": "blunt", "weight_base": 4.0, "value_base": 40},
    "bow": {"slot": "ranged", "damage_type": "pierce", "weight_base": 3.0, "value_base": 55},
    "greatsword": {"slot": "two_hand", "damage_type": "slash", "weight_base": 12.0, "value_base": 80},
    "spear": {"slot": "two_hand", "damage_type": "pierce", "weight_base": 5.0, "value_base": 50},
    "wand": {"slot": "main_hand", "damage_type": "arcane", "weight_base": 1.0, "value_base": 60},
}

# Armor base templates by slot
ARMOR_TEMPLATES = {
    "chest": {"slot": "chest", "weight_base": 10.0, "value_base": 60, "armor_base": 5},
    "head": {"slot": "head", "weight_base": 3.0, "value_base": 30, "armor_base": 2},
    "legs": {"slot": "legs", "weight_base": 6.0, "value_base": 40, "armor_base": 3},
    "feet": {"slot": "feet", "weight_base": 3.0, "value_base": 25, "armor_base": 2},
    "hands": {"slot": "hands", "weight_base": 2.0, "value_base": 25, "armor_base": 2},
    "wrists": {"slot": "wrists", "weight_base": 1.5, "value_base": 20, "armor_base": 1},
    "shield": {"slot": "off_hand", "weight_base": 8.0, "value_base": 40, "armor_base": 4},
    "robe": {"slot": "chest", "weight_base": 2.0, "value_base": 50, "armor_base": 1},
}

# Material tiers with stat multipliers
MATERIAL_TIERS = {
    1: {"name": "Rusted", "damage_mult": 0.6, "armor_mult": 0.6, "value_mult": 0.5, "durability": 60},
    2: {"name": "Iron", "damage_mult": 1.0, "armor_mult": 1.0, "value_mult": 1.0, "durability": 100},
    3: {"name": "Steel", "damage_mult": 1.3, "armor_mult": 1.3, "value_mult": 1.5, "durability": 130},
    4: {"name": "Mithril", "damage_mult": 1.6, "armor_mult": 1.6, "value_mult": 2.5, "durability": 160},
    5: {"name": "Adamantite", "damage_mult": 2.0, "armor_mult": 2.0, "value_mult": 4.0, "durability": 200},
    6: {"name": "Dragonbone", "damage_mult": 2.5, "armor_mult": 2.5, "value_mult": 6.0, "durability": 250},
    7: {"name": "Ethereal", "damage_mult": 3.0, "armor_mult": 3.0, "value_mult": 10.0, "durability": 300},
}

# Level brackets to material tier mapping
LEVEL_TO_TIER = {
    (1, 5): 1,
    (6, 15): 2,
    (16, 25): 3,
    (26, 40): 4,
    (41, 55): 5,
    (56, 70): 6,
    (71, 80): 7,
}


def _get_tier(level: int) -> int:
    """Get material tier for a given level."""
    for (lo, hi), tier in LEVEL_TO_TIER.items():
        if lo <= level <= hi:
            return tier
    return 7


def _get_tier_name(level: int) -> str:
    """Get material name for a given level."""
    return MATERIAL_TIERS[_get_tier(level)]["name"]


def _scale_damage(base: int, level: int) -> int:
    """Scale weapon damage by level."""
    tier = _get_tier(level)
    mult = MATERIAL_TIERS[tier]["damage_mult"]
    return max(1, int(base * mult * (1 + level * 0.05)))


def _scale_armor(base: int, level: int) -> int:
    """Scale armor value by level."""
    tier = _get_tier(level)
    mult = MATERIAL_TIERS[tier]["armor_mult"]
    return max(1, int(base * mult * (1 + level * 0.04)))


def _scale_value(base: int, level: int) -> int:
    """Scale gold value by level."""
    tier = _get_tier(level)
    mult = MATERIAL_TIERS[tier]["value_mult"]
    return max(1, int(base * mult * (1 + level * 0.1)))


def _scale_durability(level: int) -> int:
    """Get durability for a given level."""
    tier = _get_tier(level)
    return MATERIAL_TIERS[tier]["durability"]


# Weapon name prefixes by tier
WEAPON_PREFIXES = {
    1: ["Rusted", "Worn", "Cracked", "Dull"],
    2: ["Iron", "Sturdy", "Solid", "Tempered"],
    3: ["Steel", "Fine", "Keen", "Polished"],
    4: ["Mithril", "Gleaming", "Enchanted", "Runed"],
    5: ["Adamantite", "Forged", "Blessed", "Ancient"],
    6: ["Dragonbone", "Elemental", "Titan-Forged", "Sovereign"],
    7: ["Ethereal", "Celestial", "Divine", "Cosmic"],
}

# Armor name prefixes by tier
ARMOR_PREFIXES = {
    1: ["Patched", "Worn", "Tattered", "Frayed"],
    2: ["Iron", "Sturdy", "Reinforced", "Solid"],
    3: ["Steel", "Fine", "Polished", "Tempered"],
    4: ["Mithril", "Enchanted", "Runed", "Gleaming"],
    5: ["Adamantite", "Blessed", "Ancient", "Fortified"],
    6: ["Dragonbone", "Elemental", "Titan-Forged", "Sovereign"],
    7: ["Ethereal", "Celestial", "Divine", "Cosmic"],
}

# Armor slot display names
ARMOR_SLOT_NAMES = {
    "chest": ["Breastplate", "Cuirass", "Chestguard", "Tunic", "Hauberk"],
    "head": ["Helm", "Crown", "Coif", "Circlet", "Greathelm"],
    "legs": ["Greaves", "Leggings", "Tassets", "Chausses", "Cuisses"],
    "feet": ["Boots", "Greaves", "Sabatons", "Treads", "Sollerets"],
    "hands": ["Gauntlets", "Gloves", "Grips", "Handguards", "Bracers"],
    "wrists": ["Bracers", "Wristguards", "Vambraces", "Armlets", "Cuffs"],
    "shield": ["Shield", "Aegis", "Buckler", "Bulwark", "Targe"],
    "robe": ["Robes", "Vestments", "Raiment", "Garb", "Shroud"],
}


def generate_all_items() -> Dict[str, Dict[str, Any]]:
    """
    Generate 200+ item prototypes across all level tiers.

    Returns:
        Dict of {item_key: prototype_dict} to merge into ITEM_PROTOTYPES.
    """
    items: Dict[str, Dict[str, Any]] = {}

    # ---- Weapons (8 types x 7 tiers = 56) ----
    for weapon_type, template in WEAPON_TEMPLATES.items():
        for tier_num in range(1, 8):
            level = tier_num * 10 + 5  # representative level
            prefix = random.choice(WEAPON_PREFIXES[tier_num])
            name = f"{prefix} {weapon_type.title()}"
            key = f"gen_{weapon_type}_tier{tier_num}"

            items[key] = {
                "typeclass": "typeclasses.objects.Object",
                "key": name,
                "attributes": [
                    ("item_type", f"weapon_{weapon_type}"),
                    ("slot", template["slot"]),
                    ("weight", template["weight_base"] * (1 + tier_num * 0.1)),
                    ("value", _scale_value(template["value_base"], level)),
                    ("durability", _scale_durability(level)),
                    ("max_durability", _scale_durability(level)),
                    ("damage", _scale_damage(5 + tier_num * 3, level)),
                    ("damage_type", template["damage_type"]),
                    ("required_level", max(1, level - 5)),
                ],
            }

    # ---- Armor (8 slots x 7 tiers = 56) ----
    for slot, template in ARMOR_TEMPLATES.items():
        for tier_num in range(1, 8):
            level = tier_num * 10 + 5
            prefix = random.choice(ARMOR_PREFIXES[tier_num])
            slot_name = random.choice(ARMOR_SLOT_NAMES[slot])
            name = f"{prefix} {slot_name}"
            key = f"gen_armor_{slot}_tier{tier_num}"

            items[key] = {
                "typeclass": "typeclasses.objects.Object",
                "key": name,
                "attributes": [
                    ("item_type", f"armor_{slot}"),
                    ("slot", template["slot"]),
                    ("weight", template["weight_base"] * (1 + tier_num * 0.1)),
                    ("value", _scale_value(template["value_base"], level)),
                    ("durability", _scale_durability(level)),
                    ("max_durability", _scale_durability(level)),
                    ("armor", _scale_armor(template["armor_base"], level)),
                    ("required_level", max(1, level - 5)),
                ],
            }

    # ---- Consumables (5 types x 5 tiers = 25) ----
    consumable_types = [
        ("health_potion", "Health Potion", "heal_amount", 30),
        ("mana_potion", "Mana Potion", "mana_restore", 25),
        ("elixir", "Elixir", "heal_amount", 50),
        ("antidote", "Antidote", "cure_poison", 1),
        ("scroll", "Scroll", "spell_power", 10),
    ]

    for ctype, cname, attr_key, base_val in consumable_types:
        for tier_num in range(1, 6):
            level = tier_num * 15
            prefix = ["Minor", "Lesser", "", "Greater", "Superior"][tier_num - 1]
            name = f"{prefix} {cname}".strip()
            key = f"gen_{ctype}_tier{tier_num}"

            attributes = [
                ("item_type", "consumable"),
                ("weight", 0.5),
                ("value", _scale_value(15, level)),
                ("durability", 1),
                ("max_durability", 1),
            ]
            if attr_key in ("heal_amount", "mana_restore", "spell_power"):
                attributes.append((attr_key, base_val * tier_num))
            else:
                attributes.append((attr_key, base_val))

            items[key] = {
                "typeclass": "typeclasses.objects.Object",
                "key": name,
                "attributes": attributes,
            }

    # ---- Jewelry & Accessories (4 types x 5 tiers = 20) ----
    jewelry_types = [
        ("ring", "Ring", "finger1"),
        ("amulet", "Amulet", "neck"),
        ("belt", "Belt", "waist"),
        ("cloak", "Cloak", "back"),
    ]

    for jtype, jname, jslot in jewelry_types:
        for tier_num in range(1, 6):
            level = tier_num * 15
            prefix = ["Copper", "Silver", "Gold", "Platinum", "Mythril"][tier_num - 1]
            name = f"{prefix} {jname}"
            key = f"gen_{jtype}_tier{tier_num}"

            items[key] = {
                "typeclass": "typeclasses.objects.Object",
                "key": name,
                "attributes": [
                    ("item_type", "jewelry"),
                    ("slot", jslot),
                    ("weight", 0.3),
                    ("value", _scale_value(30, level)),
                    ("durability", _scale_durability(level)),
                    ("max_durability", _scale_durability(level)),
                    ("armor", _scale_armor(1, level)),
                    ("required_level", max(1, level - 5)),
                ],
            }

    # ---- Named Unique Items (50+ unique named items) ----
    named_items = _generate_named_items()
    items.update(named_items)

    return items


def _generate_named_items() -> Dict[str, Dict[str, Any]]:
    """Generate 50+ uniquely named items with flavor."""
    items: Dict[str, Dict[str, Any]] = {}

    named_weapons = [
        ("flamebrand", "Flamebrand", "sword", 25, 18, "fire", {"str": 3, "int": 2}),
        ("frostbite", "Frostbite", "dagger", 20, 14, "cold", {"dex": 4}),
        ("thunderstrike", "Thunderstrike", "mace", 30, 20, "lightning", {"str": 4}),
        ("shadowfang", "Shadowfang", "dagger", 35, 22, "shadow", {"dex": 5, "int": 2}),
        ("dawnbreaker", "Dawnbreaker", "greatsword", 40, 28, "holy", {"str": 5, "wis": 3}),
        ("voidreaver", "Voidreaver", "staff", 45, 25, "shadow", {"int": 6, "wis": 3}),
        ("stormcaller", "Stormcaller", "bow", 38, 24, "lightning", {"dex": 5}),
        ("earthshaker", "Earthshaker", "mace", 42, 30, "blunt", {"str": 6, "con": 3}),
        ("soulrender", "Soulrender", "axe", 48, 32, "shadow", {"str": 5, "int": 3}),
        ("starfall", "Starfall", "wand", 50, 28, "arcane", {"int": 7, "wis": 4}),
        ("blooddrinker", "Blooddrinker", "sword", 55, 35, "slash", {"str": 6, "con": 4}),
        ("windfury", "Windfury", "spear", 44, 26, "lightning", {"dex": 6}),
        ("doomhammer", "Doomhammer", "mace", 60, 40, "blunt", {"str": 8, "con": 5}),
        ("nightblade", "Nightblade", "dagger", 52, 30, "shadow", {"dex": 7, "int": 4}),
        ("sunfire_staff", "Sunfire Staff", "staff", 58, 32, "fire", {"int": 8, "wis": 5}),
    ]

    for key, name, wtype, level, damage, dtype, bonuses in named_weapons:
        items[f"named_{key}"] = {
            "typeclass": "typeclasses.objects.Object",
            "key": name,
            "attributes": [
                ("item_type", f"weapon_{wtype}"),
                ("slot", WEAPON_TEMPLATES.get(wtype, {}).get("slot", "main_hand")),
                ("weight", WEAPON_TEMPLATES.get(wtype, {}).get("weight_base", 5)),
                ("value", _scale_value(100, level)),
                ("durability", _scale_durability(level)),
                ("max_durability", _scale_durability(level)),
                ("damage", damage),
                ("damage_type", dtype),
                ("required_level", max(1, level - 5)),
                ("stat_bonuses", bonuses),
                ("rarity", "rare" if level < 40 else "epic" if level < 60 else "legendary"),
            ],
        }

    named_armors = [
        ("dragonscale_plate", "Dragonscale Plate", "chest", 45, 25, {"con": 6, "str": 3}),
        ("shadow_weave_robes", "Shadow Weave Robes", "robe", 40, 8, {"int": 6, "wis": 3}),
        ("titan_helm", "Titan-Forged Helm", "head", 50, 15, {"str": 5, "con": 4}),
        ("phoenix_feather_cloak", "Phoenix Feather Cloak", "back", 35, 5, {"dex": 4, "int": 3}),
        ("guardian_aegis", "Guardian's Aegis", "shield", 48, 22, {"con": 7, "str": 3}),
        ("windwalker_boots", "Windwalker Boots", "feet", 38, 10, {"dex": 6}),
        ("spellweave_gloves", "Spellweave Gloves", "hands", 42, 8, {"int": 5, "wis": 3}),
        ("ironheart_legplates", "Ironheart Legplates", "legs", 46, 18, {"con": 5, "str": 4}),
        ("arcane_bracers", "Arcane Bracers", "wrists", 36, 6, {"int": 4, "wis": 2}),
        ("crown_of_stars", "Crown of Stars", "head", 55, 18, {"int": 7, "wis": 5}),
        ("void_touched_vestments", "Void-Touched Vestments", "robe", 52, 10, {"int": 8, "wis": 4}),
        ("adamantite_bulwark", "Adamantite Bulwark", "shield", 58, 28, {"con": 8, "str": 5}),
        ("celestial_raiment", "Celestial Raiment", "chest", 60, 30, {"int": 8, "wis": 6}),
        ("dragonlord_gauntlets", "Dragonlord Gauntlets", "hands", 54, 12, {"str": 6, "con": 5}),
        ("stormrider_greaves", "Stormrider Greaves", "feet", 56, 14, {"dex": 7, "str": 4}),
    ]

    for key, name, slot, level, armor, bonuses in named_armors:
        items[f"named_{key}"] = {
            "typeclass": "typeclasses.objects.Object",
            "key": name,
            "attributes": [
                ("item_type", f"armor_{slot}"),
                ("slot", slot),
                ("weight", ARMOR_TEMPLATES.get(slot, {}).get("weight_base", 5)),
                ("value", _scale_value(120, level)),
                ("durability", _scale_durability(level)),
                ("max_durability", _scale_durability(level)),
                ("armor", armor),
                ("required_level", max(1, level - 5)),
                ("stat_bonuses", bonuses),
                ("rarity", "rare" if level < 40 else "epic" if level < 60 else "legendary"),
            ],
        }

    named_jewelry = [
        ("ring_of_power", "Ring of Power", "finger1", 30, {"str": 3, "int": 3}),
        ("amulet_of_protection", "Amulet of Protection", "neck", 25, {"con": 4}),
        ("belt_of_giant_strength", "Belt of Giant Strength", "waist", 35, {"str": 6}),
        ("cloak_of_shadows", "Cloak of Shadows", "back", 28, {"dex": 5}),
        ("ring_of_wisdom", "Ring of Wisdom", "finger1", 32, {"wis": 5, "int": 3}),
        ("pendant_of_vitality", "Pendant of Vitality", "neck", 40, {"con": 6, "str": 3}),
        ("sash_of_agility", "Sash of Agility", "waist", 38, {"dex": 6}),
        ("mantle_of_intellect", "Mantle of Intellect", "back", 42, {"int": 7}),
        ("signet_of_the_archmage", "Signet of the Archmage", "finger1", 50, {"int": 8, "wis": 5}),
        ("talisman_of_immortality", "Talisman of Immortality", "neck", 55, {"con": 8, "str": 4}),
    ]

    for key, name, slot, level, bonuses in named_jewelry:
        items[f"named_{key}"] = {
            "typeclass": "typeclasses.objects.Object",
            "key": name,
            "attributes": [
                ("item_type", "jewelry"),
                ("slot", slot),
                ("weight", 0.3),
                ("value", _scale_value(80, level)),
                ("durability", _scale_durability(level)),
                ("max_durability", _scale_durability(level)),
                ("armor", _scale_armor(1, level)),
                ("required_level", max(1, level - 5)),
                ("stat_bonuses", bonuses),
                ("rarity", "rare" if level < 40 else "epic" if level < 60 else "legendary"),
            ],
        }

    return items


# ===========================================================================
# MOB GENERATION
# ===========================================================================

# Mob archetypes with stat distributions
MOB_ARCHETYPES = {
    "brute": {"str_pct": 0.35, "dex_pct": 0.15, "con_pct": 0.30, "int_pct": 0.05, "wis_pct": 0.08, "cha_pct": 0.07, "hp_mult": 1.3, "dmg_mult": 1.2, "xp_mult": 1.0},
    "skirmisher": {"str_pct": 0.20, "dex_pct": 0.35, "con_pct": 0.15, "int_pct": 0.10, "wis_pct": 0.10, "cha_pct": 0.10, "hp_mult": 0.8, "dmg_mult": 1.0, "xp_mult": 1.0},
    "caster": {"str_pct": 0.08, "dex_pct": 0.12, "con_pct": 0.15, "int_pct": 0.35, "wis_pct": 0.20, "cha_pct": 0.10, "hp_mult": 0.7, "dmg_mult": 1.3, "xp_mult": 1.2},
    "tank": {"str_pct": 0.25, "dex_pct": 0.10, "con_pct": 0.35, "int_pct": 0.08, "wis_pct": 0.12, "cha_pct": 0.10, "hp_mult": 1.6, "dmg_mult": 0.8, "xp_mult": 1.1},
    "assassin": {"str_pct": 0.15, "dex_pct": 0.40, "con_pct": 0.12, "int_pct": 0.10, "wis_pct": 0.10, "cha_pct": 0.13, "hp_mult": 0.7, "dmg_mult": 1.4, "xp_mult": 1.1},
    "balanced": {"str_pct": 0.20, "dex_pct": 0.20, "con_pct": 0.20, "int_pct": 0.15, "wis_pct": 0.15, "cha_pct": 0.10, "hp_mult": 1.0, "dmg_mult": 1.0, "xp_mult": 1.0},
}

# Mob names by level bracket and archetype
MOB_NAMES = {
    (1, 5): {
        "brute": ["Young Boar", "Angry Bull", "Large Rat"],
        "skirmisher": ["Forest Wolf", "Cave Bat", "Giant Wasp"],
        "caster": ["Forest Sprite", "Mud Shaman", "Lesser Imp"],
        "tank": ["Rock Crab", "Thorn Beast", "Moss Golem"],
        "assassin": ["Shadow Rat", "Vine Stalker", "Night Weasel"],
        "balanced": ["Wild Dog", "Giant Toad", "Forest Snake"],
    },
    (6, 15): {
        "brute": ["Hill Ogre", "Berserker Orc", "Cave Troll"],
        "skirmisher": ["Dire Wolf", "Hobgoblin Raider", "Giant Scorpion"],
        "caster": ["Dark Acolyte", "Goblin Shaman", "Witch Doctor"],
        "tank": ["Stone Golem", "Iron Sentinel", "Bone Construct"],
        "assassin": ["Shadow Stalker", "Nightblade Rogue", "Venom Spider"],
        "balanced": ["Bandit Marauder", "Orc Grunt", "Cave Crawler"],
    },
    (16, 30): {
        "brute": ["Mountain Ogre", "War Troll", "Minotaur Brute"],
        "skirmisher": ["Wyvern Hatchling", "Griffin Chick", "Sabertooth"],
        "caster": ["Shadow Mage", "Blood Warlock", "Necromancer Acolyte"],
        "tank": ["Iron Golem", "Granite Elemental", "Crystal Guardian"],
        "assassin": ["Drow Assassin", "Phase Spider", "Shadow Panther"],
        "balanced": ["Orc Warrior", "Mercenary Captain", "Gnoll Pack Leader"],
    },
    (31, 50): {
        "brute": ["Fire Giant", "Frost Ogre", "Magma Brute"],
        "skirmisher": ["Wyvern", "Manticore", "Chimera Spawn"],
        "caster": ["Lich Apprentice", "Demonologist", "Void Caller"],
        "tank": ["Adamantite Golem", "Obsidian Elemental", "Dragon Turtle"],
        "assassin": ["Death Stalker", "Void Assassin", "Spectral Reaper"],
        "balanced": ["Orc Warlord", "Dark Knight", "Fallen Paladin"],
    },
    (51, 70): {
        "brute": ["Elder Giant", "Titan Spawn", "Magma Lord"],
        "skirmisher": ["Elder Wyvern", "Chimera", "Storm Griffin"],
        "caster": ["Arch Lich", "Void Archmage", "Demon Lord"],
        "tank": ["Diamond Golem", "Primordial Elemental", "Ancient Guardian"],
        "assassin": ["Nether Stalker", "Abyssal Reaper", "Shadow Dragon Spawn"],
        "balanced": ["Death Knight", "Chaos Knight", "Fallen Champion"],
    },
    (71, 80): {
        "brute": ["World Breaker", "Titan Colossus", "Apocalypse Brute"],
        "skirmisher": ["Ancient Dragon Spawn", "Cosmic Horror", "Void Drake"],
        "caster": ["Elder Lich King", "Void Sovereign", "Chaos Archmage"],
        "tank": ["Eternal Guardian", "Cosmic Golem", "Primordial Titan"],
        "assassin": ["Death Incarnate", "Void Reaper", "Eternal Shadow"],
        "balanced": ["Fallen God", "Chaos Lord", "Apocalypse Knight"],
    },
}


def _derive_mob_stats(level: int, archetype: str) -> Dict[str, int]:
    """Derive balanced stats for a mob based on level and archetype."""
    arch = MOB_ARCHETYPES.get(archetype, MOB_ARCHETYPES["balanced"])
    total = 30 + level * 3  # total stat points

    return {
        "str": max(3, int(total * arch["str_pct"])),
        "dex": max(3, int(total * arch["dex_pct"])),
        "con": max(3, int(total * arch["con_pct"])),
        "int": max(3, int(total * arch["int_pct"])),
        "wis": max(3, int(total * arch["wis_pct"])),
        "cha": max(3, int(total * arch["cha_pct"])),
    }


def _derive_mob_hp(level: int, archetype: str) -> int:
    """Derive HP for a mob."""
    arch = MOB_ARCHETYPES.get(archetype, MOB_ARCHETYPES["balanced"])
    base = 20 + level * 8
    return int(base * arch["hp_mult"])


def _derive_mob_damage(level: int, archetype: str) -> int:
    """Derive max damage for a mob."""
    arch = MOB_ARCHETYPES.get(archetype, MOB_ARCHETYPES["balanced"])
    base = 3 + level * 1.5
    return max(1, int(base * arch["dmg_mult"]))


def _derive_mob_xp(level: int, archetype: str) -> int:
    """Derive XP value for a mob."""
    arch = MOB_ARCHETYPES.get(archetype, MOB_ARCHETYPES["balanced"])
    base = level * level * 2
    return int(base * arch["xp_mult"])


def _derive_mob_gold(level: int) -> tuple:
    """Derive gold drop range for a mob."""
    return (level * 2, level * 6)


def _get_mob_name(level: int, archetype: str) -> str:
    """Get a mob name for the given level and archetype."""
    for (lo, hi), names in MOB_NAMES.items():
        if lo <= level <= hi:
            return random.choice(names.get(archetype, names["balanced"]))
    return random.choice(MOB_NAMES[(71, 80)]["balanced"])


def generate_all_mobs() -> Dict[str, Dict[str, Any]]:
    """
    Generate 150+ mob prototypes across all level tiers.

    Returns:
        Dict of {mob_key: prototype_dict} to merge into MOB_PROTOTYPES.
    """
    mobs: Dict[str, Dict[str, Any]] = {}

    # Generate mobs for each archetype at various levels
    archetypes = list(MOB_ARCHETYPES.keys())
    levels = [1, 3, 5, 8, 10, 12, 15, 18, 20, 22, 25, 28, 30, 33, 35, 38,
              40, 43, 45, 48, 50, 53, 55, 58, 60, 63, 65, 68, 70, 73, 75, 78, 80]

    count = 0
    for level in levels:
        for arch in archetypes:
            name = _get_mob_name(level, arch)
            key = f"gen_{arch}_lvl{level}"
            stats = _derive_mob_stats(level, arch)
            hp = _derive_mob_hp(level, arch)
            dmg = _derive_mob_damage(level, arch)
            xp = _derive_mob_xp(level, arch)
            gold_min, gold_max = _derive_mob_gold(level)

            # Determine faction based on level bracket
            if level <= 15:
                faction = random.choice(["Neutral", "Gorgoroth Horde", "Aethelgard Alliance"])
            elif level <= 40:
                faction = random.choice(["Gorgoroth Horde", "Aethelgard Alliance"])
            else:
                faction = random.choice(["Gorgoroth Horde", "Aethelgard Alliance", "Neutral"])

            # Damage type based on archetype
            dmg_types = {
                "brute": "blunt",
                "skirmisher": "slash",
                "caster": "arcane",
                "tank": "blunt",
                "assassin": "pierce",
                "balanced": "slash",
            }

            mobs[key] = {
                "typeclass": "typeclasses.characters.Character",
                "key": name,
                "attributes": [
                    ("is_mob", True),
                    ("level", level),
                    ("stats", stats),
                    ("hp", hp),
                    ("max_hp", hp),
                    ("alignment", "Evil" if faction == "Gorgoroth Horde" else "Good" if faction == "Aethelgard Alliance" else "Neutral"),
                    ("faction", faction),
                    ("xp_value", xp),
                    ("gold_min", gold_min),
                    ("gold_max", gold_max),
                    ("damage_type", dmg_types.get(arch, "slash")),
                    ("loot_table", _generate_loot_table(level)),
                ],
            }
            count += 1

    # Generate named elite mobs (mini-bosses)
    named_mobs = _generate_named_mobs()
    mobs.update(named_mobs)

    return mobs


def _generate_loot_table(level: int) -> List[Dict[str, Any]]:
    """Generate a loot table for a mob based on level."""
    loot = []
    # Always chance for gold-only drop
    if level <= 10:
        loot.append({"item_key": "health_potion", "weight": 0.15, "min_qty": 1, "max_qty": 1})
        loot.append({"item_key": "travel_rations", "weight": 0.20, "min_qty": 1, "max_qty": 2})
    elif level <= 25:
        loot.append({"item_key": "health_potion", "weight": 0.20, "min_qty": 1, "max_qty": 2})
        loot.append({"item_key": "mana_potion", "weight": 0.15, "min_qty": 1, "max_qty": 1})
        loot.append({"item_key": "gen_sword_tier2", "weight": 0.10, "min_qty": 1, "max_qty": 1})
    elif level <= 45:
        loot.append({"item_key": "health_potion", "weight": 0.25, "min_qty": 2, "max_qty": 4})
        loot.append({"item_key": "mana_potion", "weight": 0.20, "min_qty": 1, "max_qty": 3})
        loot.append({"item_key": "gen_armor_chest_tier3", "weight": 0.10, "min_qty": 1, "max_qty": 1})
    elif level <= 65:
        loot.append({"item_key": "health_potion", "weight": 0.30, "min_qty": 3, "max_qty": 6})
        loot.append({"item_key": "mana_potion", "weight": 0.25, "min_qty": 2, "max_qty": 4})
        loot.append({"item_key": "gen_sword_tier5", "weight": 0.08, "min_qty": 1, "max_qty": 1})
    else:
        loot.append({"item_key": "health_potion", "weight": 0.35, "min_qty": 4, "max_qty": 8})
        loot.append({"item_key": "mana_potion", "weight": 0.30, "min_qty": 3, "max_qty": 6})
        loot.append({"item_key": "gen_armor_chest_tier6", "weight": 0.08, "min_qty": 1, "max_qty": 1})
    return loot


def _generate_named_mobs() -> Dict[str, Dict[str, Any]]:
    """Generate 30+ named elite mobs."""
    mobs: Dict[str, Dict[str, Any]] = {}

    named = [
        ("elite_orc_warlord", "Orc Warlord Gruumsh", 25, "brute", "Gorgoroth Horde"),
        ("elite_shadow_mage", "Shadow Mage Vex", 28, "caster", "Gorgoroth Horde"),
        ("elite_forest_guardian", "Forest Guardian Oakheart", 22, "tank", "Aethelgard Alliance"),
        ("elite_drow_assassin", "Drow Assassin Zilvra", 30, "assassin", "Gorgoroth Horde"),
        ("elite_paladin_commander", "Paladin Commander Aldric", 32, "tank", "Aethelgard Alliance"),
        ("elite_fire_elemental", "Fire Elemental Ignis", 35, "caster", "Neutral"),
        ("elite_ice_wraith", "Ice Wraith Frostbane", 38, "assassin", "Gorgoroth Horde"),
        ("elite_stone_colossus", "Stone Colossus Granitus", 40, "tank", "Neutral"),
        ("elite_blood_warlock", "Blood Warlock Morath", 42, "caster", "Gorgoroth Horde"),
        ("elite_holy_crusader", "Holy Crusader Seraphina", 44, "brute", "Aethelgard Alliance"),
        ("elite_void_stalker", "Void Stalker Nihil", 46, "assassin", "Gorgoroth Horde"),
        ("elite_storm_drake", "Storm Drake Tempest", 48, "skirmisher", "Neutral"),
        ("elite_death_knight", "Death Knight Mortis", 50, "brute", "Gorgoroth Horde"),
        ("elite_archdruid", "Archdruid Thornweaver", 52, "caster", "Aethelgard Alliance"),
        ("elite_chaos_beast", "Chaos Beast Entropus", 55, "brute", "Neutral"),
        ("elite_abyssal_lord", "Abyssal Lord Tenebris", 58, "caster", "Gorgoroth Horde"),
        ("elite_celestial_guardian", "Celestial Guardian Luminara", 60, "tank", "Aethelgard Alliance"),
        ("elite_nether_dragon", "Nether Dragon Umbra", 62, "skirmisher", "Gorgoroth Horde"),
        ("elite_titan_avatar", "Titan Avatar Goliath", 65, "brute", "Neutral"),
        ("elite_lich_king", "Lich King Azrael", 68, "caster", "Gorgoroth Horde"),
        ("elite_divine_avatar", "Divine Avatar Solarius", 70, "balanced", "Aethelgard Alliance"),
        ("elite_void_sovereign", "Void Sovereign Null", 72, "caster", "Gorgoroth Horde"),
        ("elite_eternal_warden", "Eternal Warden Aegis", 74, "tank", "Aethelgard Alliance"),
        ("elite_chaos_knight", "Chaos Knight Discord", 76, "brute", "Neutral"),
        ("elite_apocalypse_dragon", "Apocalypse Dragon Ruin", 78, "skirmisher", "Gorgoroth Horde"),
        ("elite_cosmic_horror", "Cosmic Horror Azathoth", 80, "caster", "Neutral"),
    ]

    for key, name, level, arch, faction in named:
        stats = _derive_mob_stats(level, arch)
        hp = _derive_mob_hp(level, arch) * 3  # Elite mobs have 3x HP
        dmg = _derive_mob_damage(level, arch) * 2  # Elite mobs have 2x damage
        xp = _derive_mob_xp(level, arch) * 5  # Elite mobs give 5x XP
        gold_min, gold_max = _derive_mob_gold(level)
        gold_min *= 5
        gold_max *= 5

        dmg_types = {
            "brute": "blunt", "skirmisher": "slash", "caster": "arcane",
            "tank": "blunt", "assassin": "pierce", "balanced": "slash",
        }

        mobs[key] = {
            "typeclass": "typeclasses.characters.Character",
            "key": name,
            "attributes": [
                ("is_mob", True),
                ("is_boss", True),
                ("level", level),
                ("stats", stats),
                ("hp", hp),
                ("max_hp", hp),
                ("alignment", "Evil" if faction == "Gorgoroth Horde" else "Good" if faction == "Aethelgard Alliance" else "Neutral"),
                ("faction", faction),
                ("xp_value", xp),
                ("gold_min", gold_min),
                ("gold_max", gold_max),
                ("damage_type", dmg_types.get(arch, "slash")),
                ("loot_table", _generate_loot_table(level)),
            ],
        }

    return mobs


# ===========================================================================
# REGISTRATION
# ===========================================================================

def register_expanded_content():
    """
    Register all generated items and mobs into the prototype registries.

    Called at server init. Idempotent — won't duplicate entries.
    """
    try:
        from world.prototypes import ITEM_PROTOTYPES, MOB_PROTOTYPES

        # Generate and merge items
        new_items = generate_all_items()
        for key, proto in new_items.items():
            if key not in ITEM_PROTOTYPES:
                ITEM_PROTOTYPES[key] = proto

        # Generate and merge mobs
        new_mobs = generate_all_mobs()
        for key, proto in new_mobs.items():
            if key not in MOB_PROTOTYPES:
                MOB_PROTOTYPES[key] = proto

        return len(new_items), len(new_mobs)
    except Exception:
        return 0, 0