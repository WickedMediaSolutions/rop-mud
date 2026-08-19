"""
Druid Class Core Mechanics — Shapeshifting System

Provides:
  - Animal forms with distinct stat templates
  - Transform/revert logic that modifies stats, HP, AC, and damage
  - Form-level gating (unlocked by level)
  - Integration with combat (forms apply melee bonuses)
  - Mana cost and duration tracking

Forms:
  - Wolf       (level 1): +2 STR, +3 DEX, +2 CON, +15% move speed, bite damage
  - Bear       (level 8): +6 STR, -2 DEX, +6 CON, +10 AC, maul damage
  - Cat        (level 12): +4 DEX, +2 STR, +10% dodge, +15% crit, claw damage
  - Eagle      (level 16): +4 DEX, +2 WIS, +20% dodge, +10% move, talon damage
  - Treant     (level 20): +8 STR, +8 CON, -4 DEX, +25 AC, +40% max HP, slam damage

Commands (in commands/druid_commands.py):
  - shift <form>   — transform into an animal form
  - revert         — return to humanoid form
  - forms          — list available forms
"""

import time
from typing import Optional, Tuple, Dict, Any

# ---------------------------------------------------------------------------
# Shapeshift Forms
# ---------------------------------------------------------------------------

SHAPESHIFT_FORMS = {
    "wolf": {
        "name": "Wolf Form",
        "min_level": 1,
        "mana_cost": 15,
        "duration": 0,  # 0 = permanent until reverted
        "stat_mods": {"str": 2, "dex": 3, "con": 2, "int": -1, "wis": 0, "cha": -1},
        "armor_bonus": 0,
        "max_hp_pct": 10,
        "move_speed_pct": 15,
        "dodge_pct": 5,
        "crit_chance_pct": 0,
        "melee_dmg_pct": 15,
        "damage_type": "pierce",
        "description": "A swift hunter. +2 STR, +3 DEX, +15% move speed, bite attacks.",
    },
    "bear": {
        "name": "Bear Form",
        "min_level": 8,
        "mana_cost": 30,
        "duration": 0,
        "stat_mods": {"str": 6, "dex": -2, "con": 6, "int": 0, "wis": 0, "cha": -1},
        "armor_bonus": 10,
        "max_hp_pct": 25,
        "move_speed_pct": -5,
        "dodge_pct": -5,
        "crit_chance_pct": 0,
        "melee_dmg_pct": 25,
        "damage_type": "blunt",
        "description": "A mighty bruiser. +6 STR, +6 CON, +10 AC, +25% max HP, maul attacks.",
    },
    "cat": {
        "name": "Cat Form",
        "min_level": 12,
        "mana_cost": 35,
        "duration": 0,
        "stat_mods": {"str": 2, "dex": 4, "con": 1, "int": 0, "wis": 1, "cha": 0},
        "armor_bonus": 0,
        "max_hp_pct": 0,
        "move_speed_pct": 10,
        "dodge_pct": 10,
        "crit_chance_pct": 15,
        "melee_dmg_pct": 20,
        "damage_type": "slash",
        "description": "A nimble predator. +4 DEX, +10% dodge, +15% crit, claw attacks.",
    },
    "eagle": {
        "name": "Eagle Form",
        "min_level": 16,
        "mana_cost": 40,
        "duration": 0,
        "stat_mods": {"str": 0, "dex": 4, "con": 0, "int": 0, "wis": 2, "cha": 0},
        "armor_bonus": 0,
        "max_hp_pct": -5,
        "move_speed_pct": 10,
        "dodge_pct": 20,
        "crit_chance_pct": 10,
        "melee_dmg_pct": 10,
        "damage_type": "pierce",
        "description": "A master of evasion. +4 DEX, +2 WIS, +20% dodge, talon attacks.",
    },
    "treant": {
        "name": "Treant Form",
        "min_level": 20,
        "mana_cost": 50,
        "duration": 0,
        "stat_mods": {"str": 8, "dex": -4, "con": 8, "int": 0, "wis": 2, "cha": -1},
        "armor_bonus": 25,
        "max_hp_pct": 40,
        "move_speed_pct": -15,
        "dodge_pct": -10,
        "crit_chance_pct": 0,
        "melee_dmg_pct": 30,
        "damage_type": "blunt",
        "description": "A living fortress. +8 STR, +8 CON, +25 AC, +40% max HP, slam attacks.",
    },
}

# ---------------------------------------------------------------------------
# Shapeshift Engine
# ---------------------------------------------------------------------------

def get_available_forms(character) -> list:
    """Return list of form keys available at the character's level."""
    level = _get_level(character)
    available = []
    for form_key, form_data in SHAPESHIFT_FORMS.items():
        if level >= form_data["min_level"]:
            available.append(form_key)
    return available


def is_druid(character) -> bool:
    """Return True if the character's class is Druid."""
    return _get_class(character) == "Druid"


def get_current_form(character) -> Optional[str]:
    """Return the character's current shapeshift form key, or None."""
    if not hasattr(character, "attributes"):
        return None
    return character.attributes.get("shapeshift_form", default=None)


def get_form_bonuses(character) -> Dict[str, Any]:
    """
    Return the bonuses dict for the character's current shapeshift form,
    or an empty dict if not shifted.

    This is the central hook for other systems (combat, movement, AC, etc.)
    to apply forms.
    """
    form_key = get_current_form(character)
    if not form_key:
        return {}

    form_data = SHAPESHIFT_FORMS.get(form_key, {})
    return {
        "form_key": form_key,
        "stat_mods": form_data.get("stat_mods", {}),
        "armor_bonus": form_data.get("armor_bonus", 0),
        "max_hp_pct": form_data.get("max_hp_pct", 0),
        "move_speed_pct": form_data.get("move_speed_pct", 0),
        "dodge_pct": form_data.get("dodge_pct", 0),
        "crit_chance_pct": form_data.get("crit_chance_pct", 0),
        "melee_dmg_pct": form_data.get("melee_dmg_pct", 0),
        "damage_type": form_data.get("damage_type", "slash"),
    }


def shapeshift(character, form_key: str) -> Tuple[bool, str]:
    """
    Transform a Druid into an animal form.

    Args:
        character: The Druid character.
        form_key: The form to shift into (one of SHAPESHIFT_FORMS keys).

    Returns (success, message).
    """
    if not is_druid(character):
        return False, "Only Druids can shapeshift."

    if form_key not in SHAPESHIFT_FORMS:
        return False, f"Unknown form '{form_key}'. Use 'forms' to list available forms."

    form_data = SHAPESHIFT_FORMS[form_key]

    # Level check
    level = _get_level(character)
    if level < form_data["min_level"]:
        return False, f"You must be level {form_data['min_level']} to shift into {form_data['name']}."

    # Already in this form?
    if get_current_form(character) == form_key:
        return False, f"You are already in {form_data['name']}."

    # Mana cost
    mana = character.attributes.get("mana", default=0) if hasattr(character, "attributes") else 0
    mana_cost = form_data["mana_cost"]
    if mana < mana_cost:
        return False, f"Not enough mana to shift into {form_data['name']} (need {mana_cost}, have {mana})."

    # Save original stats if not already saved
    if hasattr(character, "attributes"):
        if not character.attributes.get("original_stats", default=None):
            original_stats = _get_stats(character)
            character.attributes.add("original_stats", original_stats)

        # Deduct mana
        character.attributes.add("mana", mana - mana_cost)

        # Apply stat mods
        stats = _get_stats(character)
        stat_mods = form_data["stat_mods"]
        for stat_key, mod in stat_mods.items():
            stats[stat_key] = stats.get(stat_key, 10) + mod
        character.attributes.add("stats", stats)

        # Record form
        character.attributes.add("shapeshift_form", form_key)

        # Apply max HP bonus
        max_hp_pct = form_data["max_hp_pct"]
        if max_hp_pct != 0:
            max_hp = character.attributes.get("max_hp", default=100)
            new_max_hp = int(max_hp * (1.0 + max_hp_pct / 100.0))
            character.attributes.add("max_hp", new_max_hp)
            hp = character.attributes.get("hp", default=100)
            character.attributes.add("hp", min(hp + (new_max_hp - max_hp), new_max_hp))

    return True, f"You shift into {form_data['name']}! {form_data['description']}"


def revert(character) -> Tuple[bool, str]:
    """
    Revert a Druid from animal form back to humanoid form.

    Returns (success, message).
    """
    form_key = get_current_form(character)
    if not form_key:
        return False, "You are not in a shapeshifted form."

    form_data = SHAPESHIFT_FORMS.get(form_key, {})

    if hasattr(character, "attributes"):
        # Restore original stats
        original_stats = character.attributes.get("original_stats", default=None)
        if original_stats:
            character.attributes.add("stats", dict(original_stats))
            character.attributes.add("original_stats", None)
        else:
            # Fallback: reverse the stat mods
            stats = _get_stats(character)
            stat_mods = form_data.get("stat_mods", {})
            for stat_key, mod in stat_mods.items():
                stats[stat_key] = stats.get(stat_key, 10) - mod
            character.attributes.add("stats", stats)

        # Revert max HP bonus
        max_hp_pct = form_data.get("max_hp_pct", 0)
        if max_hp_pct != 0:
            max_hp = character.attributes.get("max_hp", default=100)
            new_max_hp = int(max_hp / (1.0 + max_hp_pct / 100.0))
            character.attributes.add("max_hp", new_max_hp)
            hp = character.attributes.get("hp", default=100)
            character.attributes.add("hp", min(hp, new_max_hp))

        # Clear form
        character.attributes.add("shapeshift_form", None)

    return True, f"You revert to your natural form."


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