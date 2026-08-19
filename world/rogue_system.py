"""
Rogue Class Core Mechanics — Lockpicking & Poison System

Provides:
  - Lockpicking: DEX-based skill to unlock locked doors/chests
  - Poison Crafting: Create poisons from ingredients
  - Poison Application: Coat weapons with poison for on-hit DoT
  - Integration with combat (poison applied on melee hit)
  - Integration with exits (locked doors)

Commands (in commands/rogue_commands.py):
  - picklock <target>     — attempt to pick a lock
  - craftpoison [type]    — craft a poison vial
  - applypoison <weapon>  — coat a weapon with poison
"""

import random
import time
from typing import Optional, Tuple, Dict, Any

# ---------------------------------------------------------------------------
# Lockpicking Constants
# ---------------------------------------------------------------------------

# Lock difficulty tiers
LOCK_DIFFICULTY = {
    "simple": {"dc": 10, "name": "Simple Lock", "break_chance": 0.0},
    "standard": {"dc": 15, "name": "Standard Lock", "break_chance": 0.05},
    "complex": {"dc": 20, "name": "Complex Lock", "break_chance": 0.10},
    "masterwork": {"dc": 25, "name": "Masterwork Lock", "break_chance": 0.15},
    "arcane": {"dc": 30, "name": "Arcane Lock", "break_chance": 0.0},
}

# Lockpick tool quality modifiers
LOCKPICK_QUALITY = {
    "crude": -3,
    "standard": 0,
    "fine": 3,
    "masterwork": 6,
    "enchanted": 10,
}

# Cooldown between lockpick attempts (seconds)
LOCKPICK_COOLDOWN = 3.0

# ---------------------------------------------------------------------------
# Poison System Constants
# ---------------------------------------------------------------------------

POISON_RECIPES = {
    "weak_poison": {
        "name": "Weak Poison",
        "damage_per_tick": 3,
        "duration": 12.0,
        "tick_interval": 3.0,
        "min_level": 1,
        "craft_dc": 10,
        "ingredients": ["nightshade_petal", "water_vial"],
        "charges": 3,
    },
    "standard_poison": {
        "name": "Standard Poison",
        "damage_per_tick": 6,
        "duration": 15.0,
        "tick_interval": 3.0,
        "min_level": 5,
        "craft_dc": 15,
        "ingredients": ["nightshade_petal", "spider_venom", "water_vial"],
        "charges": 4,
    },
    "strong_poison": {
        "name": "Strong Poison",
        "damage_per_tick": 10,
        "duration": 18.0,
        "tick_interval": 3.0,
        "min_level": 10,
        "craft_dc": 20,
        "ingredients": ["nightshade_petal", "spider_venom", "scorpion_tail", "water_vial"],
        "charges": 5,
    },
    "deadly_poison": {
        "name": "Deadly Poison",
        "damage_per_tick": 15,
        "duration": 20.0,
        "tick_interval": 3.0,
        "min_level": 15,
        "craft_dc": 25,
        "ingredients": ["nightshade_petal", "spider_venom", "scorpion_tail", "wyvern_stinger", "water_vial"],
        "charges": 6,
    },
    "paralytic_toxin": {
        "name": "Paralytic Toxin",
        "damage_per_tick": 5,
        "duration": 10.0,
        "tick_interval": 3.0,
        "min_level": 8,
        "craft_dc": 18,
        "ingredients": ["nightshade_petal", "spider_venom", "ghost_cap", "water_vial"],
        "charges": 3,
        "bonus_effect": "stun",
        "stun_chance": 0.15,
        "stun_duration": 3.0,
    },
    "weakening_venom": {
        "name": "Weakening Venom",
        "damage_per_tick": 4,
        "duration": 16.0,
        "tick_interval": 4.0,
        "min_level": 6,
        "craft_dc": 16,
        "ingredients": ["spider_venom", "rotten_flesh", "water_vial"],
        "charges": 4,
        "bonus_effect": "stat_debuff",
        "debuff_stat": "str",
        "debuff_amount": 3,
    },
}

# ---------------------------------------------------------------------------
# Lockpicking Engine
# ---------------------------------------------------------------------------

def get_lockpick_bonus(character) -> int:
    """
    Calculate the lockpick bonus for a character based on:
    - DEX modifier
    - Level bonus (+1 per 2 levels)
    - Lockpick tool quality
    - Rogue class bonus (+5 flat bonus for Rogues)

    Returns total bonus as an integer.
    """
    stats = _get_stats(character)
    dex = stats.get("dex", 10)
    level = _get_level(character)
    char_class = _get_class(character)

    # Base: DEX modifier
    bonus = max(0, (dex - 10) // 2)

    # Level scaling
    bonus += level // 2

    # Rogue class bonus
    if char_class == "Rogue":
        bonus += 5

    # Lockpick tool quality
    tool_quality = character.attributes.get("lockpick_quality", "standard") if hasattr(character, "attributes") else "standard"
    bonus += LOCKPICK_QUALITY.get(tool_quality, 0)

    return bonus


def attempt_lockpick(character, target, lock_difficulty: str = "standard") -> Tuple[bool, str]:
    """
    Attempt to pick a lock on a target (door, chest, etc.).

    Args:
        character: The character attempting to pick the lock.
        target: The locked object (exit, chest, etc.).
        lock_difficulty: One of LOCK_DIFFICULTY keys.

    Returns:
        (success: bool, message: str)
    """
    # Class check
    char_class = _get_class(character)
    if char_class != "Rogue":
        return False, "Only Rogues have the skill to pick locks."

    # Level check
    level = _get_level(character)
    if level < 1:
        return False, "You are too inexperienced to pick locks."

    # Cooldown check
    if hasattr(character, "attributes"):
        last_attempt = character.attributes.get("last_lockpick_time", 0)
        if time.time() - last_attempt < LOCKPICK_COOLDOWN:
            remaining = LOCKPICK_COOLDOWN - (time.time() - last_attempt)
            return False, f"You must wait {remaining:.1f}s before attempting another lockpick."

    # Get lock data
    lock_data = LOCK_DIFFICULTY.get(lock_difficulty, LOCK_DIFFICULTY["standard"])
    dc = lock_data["dc"]
    lock_name = lock_data["name"]
    break_chance = lock_data["break_chance"]

    # Calculate bonus and roll
    bonus = get_lockpick_bonus(character)
    roll = random.randint(1, 20)
    total = roll + bonus

    # Update cooldown
    if hasattr(character, "attributes"):
        character.attributes.add("last_lockpick_time", time.time())

    if total >= dc:
        # Success
        return True, f"You successfully pick the {lock_name}! (Roll: {roll} + {bonus} = {total} vs DC {dc})"
    elif roll == 1:
        # Critical failure — break lockpick
        if random.random() < break_chance:
            if hasattr(character, "attributes"):
                character.attributes.add("lockpick_quality", "crude")
            return False, f"Your lockpick snaps in the {lock_name}! (Critical failure)"
        return False, f"You fail to pick the {lock_name}. (Roll: {roll} + {bonus} = {total} vs DC {dc})"
    else:
        # Normal failure
        if random.random() < break_chance:
            # Downgrade lockpick quality
            current_quality = character.attributes.get("lockpick_quality", "standard") if hasattr(character, "attributes") else "standard"
            quality_order = ["crude", "standard", "fine", "masterwork", "enchanted"]
            idx = quality_order.index(current_quality) if current_quality in quality_order else 1
            new_idx = max(0, idx - 1)
            if hasattr(character, "attributes"):
                character.attributes.add("lockpick_quality", quality_order[new_idx])
            return False, f"Your lockpick is damaged! Quality reduced to {quality_order[new_idx]}. (Roll: {roll} + {bonus} = {total} vs DC {dc})"
        return False, f"You fail to pick the {lock_name}. (Roll: {roll} + {bonus} = {total} vs DC {dc})"


# ---------------------------------------------------------------------------
# Poison Crafting Engine
# ---------------------------------------------------------------------------

def get_known_poisons(character) -> list:
    """Return list of poison keys the character knows how to craft."""
    if not hasattr(character, "attributes"):
        return []
    return character.attributes.get("known_poisons", default=["weak_poison"])


def learn_poison_recipe(character, poison_key: str) -> Tuple[bool, str]:
    """
    Teach a character a new poison recipe.

    Returns (success, message).
    """
    if poison_key not in POISON_RECIPES:
        return False, "Unknown poison recipe."

    recipe = POISON_RECIPES[poison_key]
    level = _get_level(character)

    if level < recipe["min_level"]:
        return False, f"You must be level {recipe['min_level']} to learn {recipe['name']}."

    known = get_known_poisons(character)
    if poison_key in known:
        return False, f"You already know how to craft {recipe['name']}."

    known.append(poison_key)
    if hasattr(character, "attributes"):
        character.attributes.add("known_poisons", known)
    return True, f"You learn the recipe for {recipe['name']}!"


def craft_poison(character, poison_key: str) -> Tuple[bool, str]:
    """
    Attempt to craft a poison vial.

    Checks:
    - Character knows the recipe
    - Has required ingredients
    - Passes craft DC check (INT + level bonus)

    Returns (success, message).
    """
    if poison_key not in POISON_RECIPES:
        return False, "Unknown poison recipe."

    recipe = POISON_RECIPES[poison_key]

    # Check if character knows the recipe
    known = get_known_poisons(character)
    if poison_key not in known:
        return False, f"You don't know how to craft {recipe['name']}."

    # Check level
    level = _get_level(character)
    if level < recipe["min_level"]:
        return False, f"You must be level {recipe['min_level']} to craft {recipe['name']}."

    # Check ingredients
    if not _has_ingredients(character, recipe["ingredients"]):
        missing = _get_missing_ingredients(character, recipe["ingredients"])
        return False, f"Missing ingredients: {', '.join(missing)}."

    # Craft roll (INT-based)
    stats = _get_stats(character)
    int_val = stats.get("int", 10)
    craft_bonus = max(0, (int_val - 10) // 2) + (level // 3)
    roll = random.randint(1, 20)
    total = roll + craft_bonus

    if total < recipe["craft_dc"]:
        # Failure — lose ingredients
        _consume_ingredients(character, recipe["ingredients"])
        return False, f"Crafting fails! The ingredients are wasted. (Roll: {roll} + {craft_bonus} = {total} vs DC {recipe['craft_dc']})"

    # Success — consume ingredients, create poison
    _consume_ingredients(character, recipe["ingredients"])

    # Add poison vial to inventory
    poison_item = _create_poison_item(poison_key, recipe)
    if hasattr(character, "attributes"):
        poisons = character.attributes.get("poison_vials", default=[])
        if not isinstance(poisons, list):
            poisons = []
        poisons.append(poison_item)
        character.attributes.add("poison_vials", poisons)

    return True, f"You successfully craft a vial of {recipe['name']}! ({recipe['charges']} charges)"


def apply_poison_to_weapon(character, poison_index: int = 0) -> Tuple[bool, str]:
    """
    Apply a poison from inventory to the character's equipped weapon.

    Args:
        character: The character applying poison.
        poison_index: Index of the poison vial in inventory (0-based).

    Returns (success, message).
    """
    if not hasattr(character, "attributes"):
        return False, "Invalid character."

    poisons = character.attributes.get("poison_vials", default=[])
    if not poisons:
        return False, "You have no poison vials."

    if poison_index < 0 or poison_index >= len(poisons):
        return False, f"Invalid poison vial. You have {len(poisons)} vial(s). Use 'applypoison <number>'."

    # Check equipped weapon
    equipped = character.attributes.get("equipped", default={})
    weapon_slots = ["main_hand", "two_handed", "weapon", "two_hand"]
    has_weapon = any(slot in equipped for slot in weapon_slots)
    if not has_weapon:
        return False, "You must have a weapon equipped to apply poison."

    # Get the poison
    poison_data = poisons.pop(poison_index)
    character.attributes.add("poison_vials", poisons)

    # Apply to weapon
    character.attributes.add("weapon_poison", poison_data)
    character.attributes.add("weapon_poison_charges", poison_data.get("charges", 3))

    return True, f"You coat your weapon with {poison_data['name']}! ({poison_data['charges']} strikes remaining)"


def get_weapon_poison(character) -> Optional[Dict[str, Any]]:
    """Return the currently applied weapon poison data, or None."""
    if not hasattr(character, "attributes"):
        return None
    return character.attributes.get("weapon_poison", default=None)


def consume_weapon_poison_charge(character) -> Optional[Dict[str, Any]]:
    """
    Consume one charge of weapon poison on hit.
    Returns the poison data if still active, None if expired.
    """
    if not hasattr(character, "attributes"):
        return None

    poison = character.attributes.get("weapon_poison", default=None)
    if not poison:
        return None

    charges = character.attributes.get("weapon_poison_charges", 0)
    charges -= 1

    if charges <= 0:
        character.attributes.add("weapon_poison", None)
        character.attributes.add("weapon_poison_charges", 0)
        return None

    character.attributes.add("weapon_poison_charges", charges)
    return poison


def apply_poison_on_hit(attacker, target) -> Optional[str]:
    """
    Called when a Rogue with a poisoned weapon hits a target.
    Applies the poison DoT effect to the target.

    Returns a message string or None.
    """
    poison = consume_weapon_poison_charge(attacker)
    if not poison:
        return None

    # Create poison status effect
    from world.status_effects import create_poison_effect, apply_status_effect

    source_level = _get_level(attacker)
    source_stat = _get_stats(attacker).get("dex", 10)

    effect = create_poison_effect(
        damage=poison["damage_per_tick"],
        duration=poison["duration"],
        tick_interval=poison["tick_interval"],
        source=attacker,
        source_level=source_level,
        source_stat=source_stat,
    )

    applied, msg = apply_status_effect(target, effect, caster=attacker)

    # Handle bonus effects
    bonus_messages = []
    if poison.get("bonus_effect") == "stun":
        if random.random() < poison.get("stun_chance", 0.15):
            from world.status_effects import create_stun_effect
            stun = create_stun_effect(
                duration=poison.get("stun_duration", 3.0),
                source=attacker,
                source_level=source_level,
                source_stat=source_stat,
            )
            apply_status_effect(target, stun, caster=attacker)
            bonus_messages.append(f"|m{target.key} is stunned by the poison!|n")

    elif poison.get("bonus_effect") == "stat_debuff":
        from world.status_effects import create_stat_debuff_effect
        debuff = create_stat_debuff_effect(
            stat=poison.get("debuff_stat", "str"),
            amount=poison.get("debuff_amount", 3),
            duration=poison["duration"],
            source=attacker,
            source_level=source_level,
            source_stat=source_stat,
        )
        apply_status_effect(target, debuff, caster=attacker)
        bonus_messages.append(f"|y{target.key}'s {poison.get('debuff_stat', 'str').upper()} is weakened!|n")

    result = f"|g{poison['name']} applied to {target.key}!|n"
    if bonus_messages:
        result += " " + " ".join(bonus_messages)

    return result


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _get_stats(character) -> Dict[str, int]:
    """Safely fetch stats dict."""
    if hasattr(character, "attributes"):
        stats = character.attributes.get("stats", default={})
        if stats and hasattr(stats, "items"):
            return {str(k): int(v) for k, v in stats.items()}
    return {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}


def _get_level(character) -> int:
    """Safely fetch level."""
    if hasattr(character, "attributes"):
        return character.attributes.get("level", default=1)
    return 1


def _get_class(character) -> str:
    """Safely fetch class."""
    if hasattr(character, "attributes"):
        return character.attributes.get("class", default="Warrior")
    return "Warrior"


def _has_ingredients(character, required: list) -> bool:
    """Check if character has all required ingredients."""
    if not hasattr(character, "attributes"):
        return False
    inventory_ingredients = character.attributes.get("ingredients", default={})
    if not isinstance(inventory_ingredients, dict):
        return False
    for ing in required:
        if inventory_ingredients.get(ing, 0) <= 0:
            return False
    return True


def _get_missing_ingredients(character, required: list) -> list:
    """Return list of missing ingredient names."""
    if not hasattr(character, "attributes"):
        return required
    inventory_ingredients = character.attributes.get("ingredients", default={})
    if not isinstance(inventory_ingredients, dict):
        return required
    return [ing for ing in required if inventory_ingredients.get(ing, 0) <= 0]


def _consume_ingredients(character, required: list):
    """Remove one of each required ingredient from character."""
    if not hasattr(character, "attributes"):
        return
    inventory_ingredients = character.attributes.get("ingredients", default={})
    if not isinstance(inventory_ingredients, dict):
        inventory_ingredients = {}
    for ing in required:
        current = inventory_ingredients.get(ing, 0)
        if current > 0:
            inventory_ingredients[ing] = current - 1
    character.attributes.add("ingredients", inventory_ingredients)


def _create_poison_item(poison_key: str, recipe: dict) -> dict:
    """Create a poison vial item dict for storage."""
    return {
        "key": poison_key,
        "name": recipe["name"],
        "damage_per_tick": recipe["damage_per_tick"],
        "duration": recipe["duration"],
        "tick_interval": recipe["tick_interval"],
        "charges": recipe["charges"],
        "bonus_effect": recipe.get("bonus_effect"),
        "stun_chance": recipe.get("stun_chance", 0),
        "stun_duration": recipe.get("stun_duration", 0),
        "debuff_stat": recipe.get("debuff_stat"),
        "debuff_amount": recipe.get("debuff_amount", 0),
    }