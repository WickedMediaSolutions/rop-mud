"""
Tradeskills / Crafting / Gathering System for 'rop'
====================================================

Provides:
  - Gathering: mine, forage, fish, harvest — collect raw materials from rooms
  - Crafting: smith, brew, tailor, enchant — turn materials into items
  - Skill progression: skill levels 1-100, XP per action
  - Material tiers: common, uncommon, rare, epic, legendary
  - Recipe registry with ingredient requirements and output items
  - Integration with economy (sell crafted goods) and equipment (wear crafted gear)

Design:
  - Skill levels stored as character attributes: tradeskill_{name}_level, tradeskill_{name}_xp
  - Recipes defined in RECIPES dict keyed by tradeskill
  - Gathering yields depend on skill level and room biome
  - Crafting success rate scales with skill vs recipe difficulty
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRADESKILLS = {
    "mining": {
        "name": "Mining",
        "desc": "Extract ore and gems from mineral veins.",
        "gather_verb": "mine",
        "tool": "pickaxe",
        "biomes": ["mountain", "cave", "underground", "volcanic"],
    },
    "foraging": {
        "name": "Foraging",
        "desc": "Gather herbs, mushrooms, and wild plants.",
        "gather_verb": "forage",
        "tool": "sickle",
        "biomes": ["forest", "swamp", "plains", "jungle"],
    },
    "fishing": {
        "name": "Fishing",
        "desc": "Catch fish and aquatic creatures.",
        "gather_verb": "fish",
        "tool": "fishing_rod",
        "biomes": ["river", "lake", "ocean", "swamp"],
    },
    "harvesting": {
        "name": "Harvesting",
        "desc": "Collect wood, leather, and animal byproducts.",
        "gather_verb": "harvest",
        "tool": "hatchet",
        "biomes": ["forest", "plains", "jungle", "tundra"],
    },
    "blacksmithing": {
        "name": "Blacksmithing",
        "desc": "Forge weapons and heavy armor from metal.",
        "craft_verb": "smith",
        "station": "anvil",
        "materials": ["iron_ore", "steel_ingot", "mithril_bar", "adamantite_bar"],
    },
    "alchemy": {
        "name": "Alchemy",
        "desc": "Brew potions, elixirs, and poisons.",
        "craft_verb": "brew",
        "station": "alchemy_table",
        "materials": ["herb", "mushroom", "crystal_dust", "essence"],
    },
    "tailoring": {
        "name": "Tailoring",
        "desc": "Sew cloth and leather armor, bags, and accessories.",
        "craft_verb": "tailor",
        "station": "loom",
        "materials": ["cloth", "leather", "silk", "enchanted_thread"],
    },
    "enchanting": {
        "name": "Enchanting",
        "desc": "Imbue items with magical properties.",
        "craft_verb": "enchant",
        "station": "enchanting_table",
        "materials": ["essence", "crystal_dust", "soul_shard", "arcane_core"],
    },
}

# Material tiers and their base value
MATERIAL_TIERS = {
    "common": {"value": 1, "color": "|w", "xp": 5},
    "uncommon": {"value": 5, "color": "|g", "xp": 15},
    "rare": {"value": 25, "color": "|b", "xp": 50},
    "epic": {"value": 100, "color": "|m", "xp": 150},
    "legendary": {"value": 500, "color": "|Y", "xp": 500},
}

# Gathering materials by biome and tier
GATHER_MATERIALS = {
    "mining": {
        "mountain": {
            "common": ["copper_ore", "tin_ore", "stone"],
            "uncommon": ["iron_ore", "silver_ore", "coal"],
            "rare": ["gold_ore", "mithril_ore", "gem_fragment"],
            "epic": ["adamantite_ore", "ruby", "sapphire"],
            "legendary": ["dragon_ore", "diamond", "worldstone_shard"],
        },
        "cave": {
            "common": ["copper_ore", "stone", "flint"],
            "uncommon": ["iron_ore", "coal", "quartz"],
            "rare": ["silver_ore", "gem_fragment", "obsidian"],
            "epic": ["gold_ore", "ruby", "dark_crystal"],
            "legendary": ["diamond", "void_ore", "soul_gem"],
        },
        "underground": {
            "common": ["stone", "flint", "copper_ore"],
            "uncommon": ["iron_ore", "coal", "quartz"],
            "rare": ["mithril_ore", "obsidian", "gem_fragment"],
            "epic": ["adamantite_ore", "dark_crystal", "ruby"],
            "legendary": ["dragon_ore", "diamond", "worldstone_shard"],
        },
        "volcanic": {
            "common": ["obsidian_shard", "stone", "copper_ore"],
            "uncommon": ["iron_ore", "coal", "fire_crystal"],
            "rare": ["gold_ore", "magma_core", "gem_fragment"],
            "epic": ["adamantite_ore", "ruby", "fire_essence"],
            "legendary": ["dragon_ore", "phoenix_heart", "worldstone_shard"],
        },
    },
    "foraging": {
        "forest": {
            "common": ["wild_herb", "berry", "mushroom"],
            "uncommon": ["medicinal_herb", "nightshade", "truffle"],
            "rare": ["moonleaf", "golden_cap", "fey_dust"],
            "epic": ["ancient_root", "phoenix_feather", "dryad_tear"],
            "legendary": ["world_tree_sap", "elder_bloom", "life_fruit"],
        },
        "swamp": {
            "common": ["bog_herb", "mushroom", "frog_leg"],
            "uncommon": ["nightshade", "leech", "swamp_bloom"],
            "rare": ["shadow_cap", "venom_sac", "bog_essence"],
            "epic": ["ancient_root", "hydra_scale", "plague_spore"],
            "legendary": ["death_cap", "lich_essence", "world_tree_sap"],
        },
        "plains": {
            "common": ["wild_herb", "berry", "cotton"],
            "uncommon": ["medicinal_herb", "sunflower", "honey"],
            "rare": ["golden_wheat", "fey_dust", "wind_essence"],
            "epic": ["ancient_root", "phoenix_feather", "storm_flower"],
            "legendary": ["elder_bloom", "life_fruit", "world_tree_sap"],
        },
        "jungle": {
            "common": ["jungle_herb", "berry", "vine"],
            "uncommon": ["medicinal_herb", "exotic_fruit", "spider_silk"],
            "rare": ["moonleaf", "venom_sac", "jungle_essence"],
            "epic": ["ancient_root", "hydra_scale", "carnivorous_plant"],
            "legendary": ["elder_bloom", "life_fruit", "world_tree_sap"],
        },
    },
    "fishing": {
        "river": {
            "common": ["minnow", "carp", "shell"],
            "uncommon": ["trout", "salmon", "crayfish"],
            "rare": ["golden_fish", "pearl", "water_essence"],
            "epic": ["spirit_fish", "river_heart", "aqua_gem"],
            "legendary": ["dragon_carp", "tide_pearl", "leviathan_scale"],
        },
        "lake": {
            "common": ["minnow", "carp", "shell"],
            "uncommon": ["bass", "catfish", "frog"],
            "rare": ["golden_fish", "pearl", "water_essence"],
            "epic": ["spirit_fish", "lake_heart", "aqua_gem"],
            "legendary": ["dragon_carp", "tide_pearl", "leviathan_scale"],
        },
        "ocean": {
            "common": ["sardine", "shell", "seaweed"],
            "uncommon": ["tuna", "crab", "coral"],
            "rare": ["golden_fish", "pearl", "tide_essence"],
            "epic": ["spirit_fish", "shark_tooth", "aqua_gem"],
            "legendary": ["dragon_carp", "tide_pearl", "leviathan_scale"],
        },
        "swamp": {
            "common": ["minnow", "leech", "shell"],
            "uncommon": ["eel", "frog", "crayfish"],
            "rare": ["golden_fish", "swamp_pearl", "bog_essence"],
            "epic": ["spirit_fish", "hydra_scale", "aqua_gem"],
            "legendary": ["dragon_carp", "tide_pearl", "leviathan_scale"],
        },
    },
    "harvesting": {
        "forest": {
            "common": ["wood", "hide", "bone"],
            "uncommon": ["oak_wood", "thick_hide", "antler"],
            "rare": ["ironwood", "dire_hide", "beast_fang"],
            "epic": ["ancient_wood", "dragon_hide", "phoenix_feather"],
            "legendary": ["world_tree_wood", "elder_hide", "titan_bone"],
        },
        "plains": {
            "common": ["wood", "hide", "bone"],
            "uncommon": ["oak_wood", "thick_hide", "feather"],
            "rare": ["ironwood", "dire_hide", "beast_fang"],
            "epic": ["ancient_wood", "dragon_hide", "storm_feather"],
            "legendary": ["world_tree_wood", "elder_hide", "titan_bone"],
        },
        "jungle": {
            "common": ["vine", "hide", "bone"],
            "uncommon": ["hardwood", "thick_hide", "venom_sac"],
            "rare": ["ironwood", "dire_hide", "beast_fang"],
            "epic": ["ancient_wood", "dragon_hide", "hydra_scale"],
            "legendary": ["world_tree_wood", "elder_hide", "titan_bone"],
        },
        "tundra": {
            "common": ["bone", "hide", "ice_shard"],
            "uncommon": ["thick_hide", "antler", "frost_herb"],
            "rare": ["dire_hide", "beast_fang", "frozen_core"],
            "epic": ["dragon_hide", "yeti_fur", "frost_essence"],
            "legendary": ["elder_hide", "titan_bone", "frozen_heart"],
        },
    },
}

# Crafting recipes: {tradeskill: {item_key: {recipe}}}
RECIPES = {
    "blacksmithing": {
        "iron_sword": {
            "name": "Iron Sword",
            "skill_req": 10,
            "materials": {"iron_ore": 3, "coal": 1},
            "output": {"typeclass": "objects", "key": "iron sword", "damage": 8, "damage_type": "slash", "slot": "right_hand", "value": 25},
            "xp": 30,
        },
        "steel_sword": {
            "name": "Steel Sword",
            "skill_req": 30,
            "materials": {"iron_ore": 5, "coal": 3},
            "output": {"typeclass": "objects", "key": "steel sword", "damage": 14, "damage_type": "slash", "slot": "right_hand", "value": 75},
            "xp": 80,
        },
        "iron_chestplate": {
            "name": "Iron Chestplate",
            "skill_req": 15,
            "materials": {"iron_ore": 5, "coal": 2},
            "output": {"typeclass": "objects", "key": "iron chestplate", "armor": 12, "slot": "torso", "value": 40},
            "xp": 50,
        },
        "steel_chestplate": {
            "name": "Steel Chestplate",
            "skill_req": 35,
            "materials": {"iron_ore": 8, "coal": 5},
            "output": {"typeclass": "objects", "key": "steel chestplate", "armor": 20, "slot": "torso", "value": 100},
            "xp": 100,
        },
        "mithril_blade": {
            "name": "Mithril Blade",
            "skill_req": 60,
            "materials": {"mithril_ore": 4, "coal": 2, "gem_fragment": 1},
            "output": {"typeclass": "objects", "key": "mithril blade", "damage": 22, "damage_type": "slash", "slot": "right_hand", "value": 250},
            "xp": 200,
        },
        "adamantite_armor": {
            "name": "Adamantite Plate",
            "skill_req": 85,
            "materials": {"adamantite_ore": 6, "coal": 4, "ruby": 1},
            "output": {"typeclass": "objects", "key": "adamantite plate", "armor": 35, "slot": "torso", "value": 600},
            "xp": 400,
        },
    },
    "alchemy": {
        "health_potion": {
            "name": "Health Potion",
            "skill_req": 5,
            "materials": {"wild_herb": 2, "berry": 1},
            "output": {"typeclass": "objects", "key": "health potion", "heal_hp": 50, "value": 15},
            "xp": 20,
        },
        "mana_potion": {
            "name": "Mana Potion",
            "skill_req": 10,
            "materials": {"medicinal_herb": 2, "mushroom": 1},
            "output": {"typeclass": "objects", "key": "mana potion", "heal_mana": 50, "value": 15},
            "xp": 20,
        },
        "greater_health_potion": {
            "name": "Greater Health Potion",
            "skill_req": 40,
            "materials": {"medicinal_herb": 4, "golden_cap": 1, "crystal_dust": 1},
            "output": {"typeclass": "objects", "key": "greater health potion", "heal_hp": 150, "value": 50},
            "xp": 60,
        },
        "elixir_of_power": {
            "name": "Elixir of Power",
            "skill_req": 70,
            "materials": {"ancient_root": 2, "phoenix_feather": 1, "essence": 3},
            "output": {"typeclass": "objects", "key": "elixir of power", "stat_boost": {"str": 5, "dex": 5}, "duration": 3600, "value": 200},
            "xp": 150,
        },
        "poison_vial": {
            "name": "Poison Vial",
            "skill_req": 25,
            "materials": {"nightshade": 2, "venom_sac": 1},
            "output": {"typeclass": "objects", "key": "poison vial", "poison_damage": 10, "poison_duration": 30, "value": 30},
            "xp": 40,
        },
    },
    "tailoring": {
        "cloth_robe": {
            "name": "Cloth Robe",
            "skill_req": 5,
            "materials": {"cloth": 4, "cotton": 2},
            "output": {"typeclass": "objects", "key": "cloth robe", "armor": 4, "slot": "torso", "value": 15},
            "xp": 20,
        },
        "leather_armor": {
            "name": "Leather Armor",
            "skill_req": 20,
            "materials": {"leather": 5, "thick_hide": 2},
            "output": {"typeclass": "objects", "key": "leather armor", "armor": 10, "slot": "torso", "value": 40},
            "xp": 50,
        },
        "silk_robe": {
            "name": "Silk Robe",
            "skill_req": 50,
            "materials": {"silk": 6, "enchanted_thread": 2, "fey_dust": 1},
            "output": {"typeclass": "objects", "key": "silk robe", "armor": 8, "mana_regen": 3, "slot": "torso", "value": 150},
            "xp": 120,
        },
        "dragonhide_armor": {
            "name": "Dragonhide Armor",
            "skill_req": 80,
            "materials": {"dragon_hide": 4, "enchanted_thread": 3, "phoenix_feather": 1},
            "output": {"typeclass": "objects", "key": "dragonhide armor", "armor": 25, "fire_resist": 15, "slot": "torso", "value": 500},
            "xp": 350,
        },
        "adventurer_bag": {
            "name": "Adventurer's Bag",
            "skill_req": 15,
            "materials": {"leather": 3, "cloth": 2},
            "output": {"typeclass": "objects", "key": "adventurer's bag", "capacity": 20, "value": 30},
            "xp": 30,
        },
    },
    "enchanting": {
        "enchanted_ring": {
            "name": "Enchanted Ring",
            "skill_req": 30,
            "materials": {"gem_fragment": 2, "essence": 3, "crystal_dust": 1},
            "output": {"typeclass": "objects", "key": "enchanted ring", "stat_boost": {"int": 3, "wis": 3}, "slot": "ring", "value": 100},
            "xp": 80,
        },
        "flame_weapon_scroll": {
            "name": "Flame Weapon Scroll",
            "skill_req": 45,
            "materials": {"essence": 4, "fire_essence": 2, "crystal_dust": 2},
            "output": {"typeclass": "objects", "key": "flame weapon scroll", "enchant": "flame_weapon", "duration": 1800, "value": 120},
            "xp": 100,
        },
        "amulet_of_protection": {
            "name": "Amulet of Protection",
            "skill_req": 60,
            "materials": {"soul_shard": 2, "essence": 5, "ruby": 1},
            "output": {"typeclass": "objects", "key": "amulet of protection", "armor": 5, "magic_resist": 10, "slot": "neck", "value": 300},
            "xp": 200,
        },
        "arcane_core": {
            "name": "Arcane Core",
            "skill_req": 90,
            "materials": {"arcane_core": 1, "soul_shard": 3, "diamond": 1, "essence": 10},
            "output": {"typeclass": "objects", "key": "arcane core", "spell_damage": 15, "spell_cdr": 10, "slot": "trinket", "value": 800},
            "xp": 500,
        },
    },
}

# XP required per skill level: level * 10
SKILL_XP_PER_LEVEL = 10
MAX_SKILL_LEVEL = 100

# Cooldown between gathering attempts (seconds)
GATHER_COOLDOWN = 3.0

# Crafting success base chance
BASE_CRAFT_CHANCE = 0.70
CRAFT_CHANCE_PER_SKILL_DIFF = 0.02  # +2% per skill level above recipe req


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_skill_level(character: Any, skill_key: str) -> int:
    """Get a character's skill level for a given tradeskill."""
    try:
        return character.attributes.get(f"tradeskill_{skill_key}_level", 1)
    except Exception:
        return 1


def _get_skill_xp(character: Any, skill_key: str) -> int:
    """Get a character's skill XP for a given tradeskill."""
    try:
        return character.attributes.get(f"tradeskill_{skill_key}_xp", 0)
    except Exception:
        return 0


def _set_skill_level(character: Any, skill_key: str, level: int) -> None:
    """Set a character's skill level."""
    try:
        character.attributes.add(f"tradeskill_{skill_key}_level", max(1, min(MAX_SKILL_LEVEL, level)))
    except Exception:
        pass


def _set_skill_xp(character: Any, skill_key: str, xp: int) -> None:
    """Set a character's skill XP."""
    try:
        character.attributes.add(f"tradeskill_{skill_key}_xp", max(0, xp))
    except Exception:
        pass


def _add_skill_xp(character: Any, skill_key: str, xp: int) -> Tuple[int, bool]:
    """Add XP to a skill. Returns (new_level, did_level_up)."""
    current_level = _get_skill_level(character, skill_key)
    if current_level >= MAX_SKILL_LEVEL:
        return current_level, False

    current_xp = _get_skill_xp(character, skill_key)
    new_xp = current_xp + xp
    xp_needed = current_level * SKILL_XP_PER_LEVEL

    did_level_up = False
    while new_xp >= xp_needed and current_level < MAX_SKILL_LEVEL:
        new_xp -= xp_needed
        current_level += 1
        xp_needed = current_level * SKILL_XP_PER_LEVEL
        did_level_up = True

    _set_skill_level(character, skill_key, current_level)
    _set_skill_xp(character, skill_key, new_xp)
    return current_level, did_level_up


def _get_room_biome(room: Any) -> str:
    """Determine the biome of a room from its attributes."""
    try:
        biome = room.attributes.get("biome", "")
        if biome:
            return biome.lower()
        terrain = room.attributes.get("terrain", "")
        if terrain:
            return terrain.lower()
    except Exception:
        pass
    return "plains"  # default


def _get_material_tier(skill_level: int) -> str:
    """Determine what tier of material a character can gather based on skill."""
    roll = random.random()
    # Higher skill = better chance of higher tier
    if skill_level >= 90 and roll < 0.02:
        return "legendary"
    elif skill_level >= 70 and roll < 0.08:
        return "epic"
    elif skill_level >= 40 and roll < 0.20:
        return "rare"
    elif skill_level >= 15 and roll < 0.40:
        return "uncommon"
    else:
        return "common"


def _has_material(character: Any, material_key: str, amount: int = 1) -> bool:
    """Check if a character has enough of a material in their inventory."""
    try:
        materials = character.attributes.get("tradeskill_materials", {})
        return materials.get(material_key, 0) >= amount
    except Exception:
        return False


def _consume_materials(character: Any, materials_dict: Dict[str, int]) -> bool:
    """Consume materials from character inventory. Returns True if successful."""
    try:
        current = character.attributes.get("tradeskill_materials", {})
        if not isinstance(current, dict):
            current = {}
        for mat, amount in materials_dict.items():
            if current.get(mat, 0) < amount:
                return False
        for mat, amount in materials_dict.items():
            current[mat] = current.get(mat, 0) - amount
            if current[mat] <= 0:
                del current[mat]
        character.attributes.add("tradeskill_materials", current)
        return True
    except Exception:
        return False


def _add_material(character: Any, material_key: str, amount: int = 1) -> None:
    """Add a material to a character's inventory."""
    try:
        materials = character.attributes.get("tradeskill_materials", {})
        if not isinstance(materials, dict):
            materials = {}
        materials[material_key] = materials.get(material_key, 0) + amount
        character.attributes.add("tradeskill_materials", materials)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_skill_info(character: Any, skill_key: str) -> Optional[Dict]:
    """Get full skill info for a character."""
    if skill_key not in TRADESKILLS:
        return None
    skill_def = TRADESKILLS[skill_key]
    level = _get_skill_level(character, skill_key)
    xp = _get_skill_xp(character, skill_key)
    xp_needed = level * SKILL_XP_PER_LEVEL
    return {
        "key": skill_key,
        "name": skill_def["name"],
        "desc": skill_def["desc"],
        "level": level,
        "xp": xp,
        "xp_needed": xp_needed,
        "max_level": MAX_SKILL_LEVEL,
    }


def list_skills(character: Any) -> List[Dict]:
    """List all tradeskills and their levels for a character."""
    result = []
    for key in TRADESKILLS:
        info = get_skill_info(character, key)
        if info:
            result.append(info)
    return result


def gather(character: Any, skill_key: str) -> Tuple[bool, str]:
    """
    Attempt to gather materials using a gathering skill.

    Args:
        character: The character gathering.
        skill_key: The gathering skill (mining, foraging, fishing, harvesting).

    Returns:
        (success, message) tuple.
    """
    if skill_key not in TRADESKILLS:
        return False, f"Unknown gathering skill: {skill_key}"

    skill_def = TRADESKILLS[skill_key]
    if "gather_verb" not in skill_def:
        return False, f"{skill_def['name']} is a crafting skill, not a gathering skill."

    # Check cooldown
    try:
        last_gather = character.attributes.get(f"tradeskill_{skill_key}_last_gather", 0)
        now = time.time()
        if now - last_gather < GATHER_COOLDOWN:
            remaining = GATHER_COOLDOWN - (now - last_gather)
            return False, f"You must wait {remaining:.1f}s before {skill_def['gather_verb']}ing again."
        character.attributes.add(f"tradeskill_{skill_key}_last_gather", now)
    except Exception:
        pass

    # Check room biome
    room = character.location
    if room is None:
        return False, "You must be in a room to gather."

    biome = _get_room_biome(room)
    valid_biomes = skill_def.get("biomes", [])
    if biome not in valid_biomes:
        return False, f"You cannot {skill_def['gather_verb']} here. Valid biomes: {', '.join(valid_biomes)}."

    # Determine material
    skill_level = _get_skill_level(character, skill_key)
    tier = _get_material_tier(skill_level)
    biome_mats = GATHER_MATERIALS.get(skill_key, {}).get(biome, {})
    tier_mats = biome_mats.get(tier, biome_mats.get("common", ["stone"]))

    if not tier_mats:
        return False, "There is nothing to gather here."

    material = random.choice(tier_mats)
    tier_info = MATERIAL_TIERS[tier]

    # Add material and XP
    _add_material(character, material, 1)
    new_level, did_level_up = _add_skill_xp(character, skill_key, tier_info["xp"])

    verb = skill_def["gather_verb"]
    msg = f"You {verb} and find {tier_info['color']}{material.replace('_', ' ').title()}|n! (+{tier_info['xp']} XP)"
    if did_level_up:
        msg += f"\n|Y{skill_def['name']} skill increased to level {new_level}!|n"

    return True, msg


def craft(character: Any, skill_key: str, recipe_key: str) -> Tuple[bool, str]:
    """
    Attempt to craft an item.

    Args:
        character: The character crafting.
        skill_key: The crafting skill (blacksmithing, alchemy, tailoring, enchanting).
        recipe_key: The recipe to craft.

    Returns:
        (success, message) tuple.
    """
    if skill_key not in TRADESKILLS:
        return False, f"Unknown crafting skill: {skill_key}"

    skill_def = TRADESKILLS[skill_key]
    if "craft_verb" not in skill_def:
        return False, f"{skill_def['name']} is a gathering skill, not a crafting skill."

    recipes = RECIPES.get(skill_key, {})
    if recipe_key not in recipes:
        return False, f"Unknown recipe: {recipe_key}. Use 'recipes {skill_key}' to see available recipes."

    recipe = recipes[recipe_key]
    skill_level = _get_skill_level(character, skill_key)

    # Check skill requirement
    if skill_level < recipe["skill_req"]:
        return False, f"You need {skill_def['name']} level {recipe['skill_req']} to craft {recipe['name']} (you are level {skill_level})."

    # Check materials
    if not _consume_materials(character, recipe["materials"]):
        missing = []
        current = character.attributes.get("tradeskill_materials", {})
        for mat, amount in recipe["materials"].items():
            have = current.get(mat, 0)
            if have < amount:
                missing.append(f"{mat.replace('_', ' ').title()} ({have}/{amount})")
        return False, f"You lack materials: {', '.join(missing)}."

    # Craft success roll
    skill_diff = skill_level - recipe["skill_req"]
    success_chance = BASE_CRAFT_CHANCE + (skill_diff * CRAFT_CHANCE_PER_SKILL_DIFF)
    success_chance = max(0.05, min(0.98, success_chance))

    if random.random() > success_chance:
        # Failed — lose half the materials
        refund = {k: v // 2 for k, v in recipe["materials"].items()}
        for mat, amount in refund.items():
            if amount > 0:
                _add_material(character, mat, amount)
        return False, f"Your {skill_def['craft_verb']} attempt fails! You salvage some materials."

    # Success — create item
    output = recipe["output"]
    item_name = output["key"]

    # Add XP
    new_level, did_level_up = _add_skill_xp(character, skill_key, recipe["xp"])

    verb = skill_def["craft_verb"]
    msg = f"You {verb} a |Y{item_name.title()}|n! (+{recipe['xp']} XP)"
    if did_level_up:
        msg += f"\n|Y{skill_def['name']} skill increased to level {new_level}!|n"

    # Try to spawn the item in character's inventory
    try:
        from evennia.utils.create import create_object
        item_attrs = [(k, v) for k, v in output.items() if k not in ("typeclass", "key")]
        obj = create_object(
            typeclass=f"typeclasses.{output.get('typeclass', 'objects')}.Object",
            key=item_name,
            location=character,
            attributes=item_attrs if item_attrs else None,
        )
        if obj:
            msg += f"\n|gYou receive: {item_name.title()}|n"
    except Exception:
        msg += f"\n|y(The {item_name} materializes but cannot be held — contact an admin.)|n"

    return True, msg


def list_recipes(skill_key: str) -> List[Dict]:
    """List all recipes for a crafting skill."""
    recipes = RECIPES.get(skill_key, {})
    result = []
    for key, recipe in recipes.items():
        result.append({
            "key": key,
            "name": recipe["name"],
            "skill_req": recipe["skill_req"],
            "materials": recipe["materials"],
            "xp": recipe["xp"],
        })
    return sorted(result, key=lambda r: r["skill_req"])


def get_materials(character: Any) -> Dict[str, int]:
    """Get all materials a character has."""
    try:
        return character.attributes.get("tradeskill_materials", {})
    except Exception:
        return {}