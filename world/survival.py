"""
Hunger / Thirst / Survival System for 'rop'
============================================

Provides:
  - Hunger and thirst tracking as character attributes
  - Eat and drink commands with food/water items
  - Starvation and dehydration penalties (stat debuffs, HP drain)
  - Well-fed and hydrated bonuses
  - Food quality tiers affecting satiation
  - Integration with recovery (well-fed boosts HP regen)

Design:
  - hunger: 0-100 (100 = full, 0 = starving)
  - thirst: 0-100 (100 = hydrated, 0 = dehydrated)
  - Both decay over time (tick-based, ~1 point per 5 minutes)
  - Penalties kick in below 25, bonuses above 75
  - Starvation at 0: HP drain, stat penalties
  - Dehydration at 0: MV drain, stat penalties
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HUNGER_MAX = 100
THIRST_MAX = 100
HUNGER_DECAY_PER_TICK = 1       # per 5 minutes
THIRST_DECAY_PER_TICK = 1       # per 5 minutes
SURVIVAL_TICK_SECONDS = 300     # 5 minutes

# Thresholds
STARVING_THRESHOLD = 10
HUNGRY_THRESHOLD = 25
WELL_FED_THRESHOLD = 75
FULL_THRESHOLD = 90

DEHYDRATED_THRESHOLD = 10
THIRSTY_THRESHOLD = 25
HYDRATED_THRESHOLD = 75

# Penalties (applied when below threshold)
STARVATION_HP_DRAIN = 5         # HP lost per tick when starving
STARVATION_STAT_PENALTY = -3    # STR/CON penalty when starving
HUNGRY_STAT_PENALTY = -1        # STR/CON penalty when hungry

DEHYDRATION_MV_DRAIN = 10       # MV lost per tick when dehydrated
DEHYDRATION_STAT_PENALTY = -3   # DEX/WIS penalty when dehydrated
THIRSTY_STAT_PENALTY = -1       # DEX/WIS penalty when thirsty

# Bonuses (applied when above threshold)
WELL_FED_HP_REGEN_BONUS = 2     # Extra HP regen per tick
HYDRATED_MV_REGEN_BONUS = 5     # Extra MV regen per tick

# Food definitions
FOOD_ITEMS = {
    "bread": {"name": "Bread", "hunger_restore": 15, "thirst_restore": 0, "quality": "common", "cost": 2},
    "cheese": {"name": "Cheese", "hunger_restore": 10, "thirst_restore": 0, "quality": "common", "cost": 3},
    "apple": {"name": "Apple", "hunger_restore": 8, "thirst_restore": 5, "quality": "common", "cost": 1},
    "meat_pie": {"name": "Meat Pie", "hunger_restore": 25, "thirst_restore": 0, "quality": "uncommon", "cost": 8},
    "roasted_boar": {"name": "Roasted Boar", "hunger_restore": 40, "thirst_restore": 0, "quality": "uncommon", "cost": 15},
    "stew": {"name": "Hearty Stew", "hunger_restore": 30, "thirst_restore": 10, "quality": "uncommon", "cost": 12},
    "elven_bread": {"name": "Elven Waybread", "hunger_restore": 50, "thirst_restore": 5, "quality": "rare", "cost": 30},
    "dragon_steak": {"name": "Dragon Steak", "hunger_restore": 80, "thirst_restore": 0, "quality": "epic", "cost": 100},
    "ambrosia": {"name": "Ambrosia", "hunger_restore": 100, "thirst_restore": 20, "quality": "legendary", "cost": 500},
    "rations": {"name": "Travel Rations", "hunger_restore": 20, "thirst_restore": 0, "quality": "common", "cost": 5},
    "berries": {"name": "Wild Berries", "hunger_restore": 5, "thirst_restore": 8, "quality": "common", "cost": 1},
    "fish_cooked": {"name": "Cooked Fish", "hunger_restore": 18, "thirst_restore": 0, "quality": "common", "cost": 6},
}

# Drink definitions
DRINK_ITEMS = {
    "water": {"name": "Water", "thirst_restore": 20, "hunger_restore": 0, "quality": "common", "cost": 1},
    "ale": {"name": "Ale", "thirst_restore": 15, "hunger_restore": 3, "quality": "common", "cost": 3},
    "milk": {"name": "Milk", "thirst_restore": 18, "hunger_restore": 5, "quality": "common", "cost": 2},
    "wine": {"name": "Wine", "thirst_restore": 12, "hunger_restore": 2, "quality": "uncommon", "cost": 8},
    "elven_wine": {"name": "Elven Wine", "thirst_restore": 25, "hunger_restore": 5, "quality": "rare", "cost": 25},
    "healing_spring": {"name": "Healing Spring Water", "thirst_restore": 40, "hunger_restore": 0, "quality": "epic", "cost": 50},
    "nectar": {"name": "Divine Nectar", "thirst_restore": 100, "hunger_restore": 10, "quality": "legendary", "cost": 400},
    "tea": {"name": "Herbal Tea", "thirst_restore": 15, "hunger_restore": 0, "quality": "common", "cost": 2},
    "juice": {"name": "Fruit Juice", "thirst_restore": 18, "hunger_restore": 3, "quality": "common", "cost": 3},
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_hunger(character: Any) -> int:
    """Get a character's hunger level."""
    try:
        return character.attributes.get("hunger", HUNGER_MAX)
    except Exception:
        return HUNGER_MAX


def _get_thirst(character: Any) -> int:
    """Get a character's thirst level."""
    try:
        return character.attributes.get("thirst", THIRST_MAX)
    except Exception:
        return THIRST_MAX


def _set_hunger(character: Any, value: int) -> None:
    """Set a character's hunger level."""
    try:
        character.attributes.add("hunger", max(0, min(HUNGER_MAX, value)))
    except Exception:
        pass


def _set_thirst(character: Any, value: int) -> None:
    """Set a character's thirst level."""
    try:
        character.attributes.add("thirst", max(0, min(THIRST_MAX, value)))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_survival_status(character: Any) -> Dict[str, Any]:
    """Get full survival status for a character."""
    hunger = _get_hunger(character)
    thirst = _get_thirst(character)

    # Determine hunger status
    if hunger <= STARVING_THRESHOLD:
        hunger_status = "starving"
        hunger_color = "|R"
    elif hunger <= HUNGRY_THRESHOLD:
        hunger_status = "hungry"
        hunger_color = "|r"
    elif hunger >= FULL_THRESHOLD:
        hunger_status = "full"
        hunger_color = "|G"
    elif hunger >= WELL_FED_THRESHOLD:
        hunger_status = "well-fed"
        hunger_color = "|g"
    else:
        hunger_status = "satisfied"
        hunger_color = "|w"

    # Determine thirst status
    if thirst <= DEHYDRATED_THRESHOLD:
        thirst_status = "dehydrated"
        thirst_color = "|R"
    elif thirst <= THIRSTY_THRESHOLD:
        thirst_status = "thirsty"
        thirst_color = "|r"
    elif thirst >= HYDRATED_THRESHOLD:
        thirst_status = "hydrated"
        thirst_color = "|b"
    else:
        thirst_status = "quenched"
        thirst_color = "|w"

    return {
        "hunger": hunger,
        "hunger_max": HUNGER_MAX,
        "hunger_status": hunger_status,
        "hunger_color": hunger_color,
        "thirst": thirst,
        "thirst_max": THIRST_MAX,
        "thirst_status": thirst_status,
        "thirst_color": thirst_color,
    }


def consume_food(character: Any, food_key: str) -> Tuple[bool, str]:
    """Eat a food item."""
    if food_key not in FOOD_ITEMS:
        return False, f"Unknown food: {food_key}."

    food = FOOD_ITEMS[food_key]
    current_hunger = _get_hunger(character)

    if current_hunger >= HUNGER_MAX:
        return False, "You are too full to eat anything else."

    new_hunger = min(HUNGER_MAX, current_hunger + food["hunger_restore"])
    _set_hunger(character, new_hunger)

    if food["thirst_restore"] > 0:
        current_thirst = _get_thirst(character)
        new_thirst = min(THIRST_MAX, current_thirst + food["thirst_restore"])
        _set_thirst(character, new_thirst)

    msg = f"You eat the {food['name']}. Hunger: {new_hunger}/{HUNGER_MAX}"
    if food["thirst_restore"] > 0:
        msg += f", Thirst: {_get_thirst(character)}/{THIRST_MAX}"
    return True, msg


def consume_drink(character: Any, drink_key: str) -> Tuple[bool, str]:
    """Drink a beverage."""
    if drink_key not in DRINK_ITEMS:
        return False, f"Unknown drink: {drink_key}."

    drink = DRINK_ITEMS[drink_key]
    current_thirst = _get_thirst(character)

    if current_thirst >= THIRST_MAX:
        return False, "You are too hydrated to drink anything else."

    new_thirst = min(THIRST_MAX, current_thirst + drink["thirst_restore"])
    _set_thirst(character, new_thirst)

    if drink["hunger_restore"] > 0:
        current_hunger = _get_hunger(character)
        new_hunger = min(HUNGER_MAX, current_hunger + drink["hunger_restore"])
        _set_hunger(character, new_hunger)

    msg = f"You drink the {drink['name']}. Thirst: {new_thirst}/{THIRST_MAX}"
    if drink["hunger_restore"] > 0:
        msg += f", Hunger: {_get_hunger(character)}/{HUNGER_MAX}"
    return True, msg


def tick_survival(character: Any) -> List[str]:
    """
    Process one survival tick (called every 5 minutes).

    Decays hunger and thirst, applies penalties/bonuses.
    Returns a list of messages to send to the character.
    """
    messages = []
    hunger = _get_hunger(character)
    thirst = _get_thirst(character)

    # Decay
    new_hunger = max(0, hunger - HUNGER_DECAY_PER_TICK)
    new_thirst = max(0, thirst - THIRST_DECAY_PER_TICK)
    _set_hunger(character, new_hunger)
    _set_thirst(character, new_thirst)

    # Starvation penalties
    if new_hunger <= STARVING_THRESHOLD:
        try:
            hp = character.attributes.get("hp", 0)
            if hp > 1:
                character.attributes.add("hp", max(1, hp - STARVATION_HP_DRAIN))
                messages.append("|RYou are starving! You lose {STARVATION_HP_DRAIN} HP.|n")
        except Exception:
            pass
        messages.append("|RYou are starving! Find food immediately!|n")
    elif new_hunger <= HUNGRY_THRESHOLD:
        messages.append("|rYou are getting hungry.|n")

    # Dehydration penalties
    if new_thirst <= DEHYDRATED_THRESHOLD:
        try:
            mv = character.attributes.get("mv", 0)
            if mv > 0:
                character.attributes.add("mv", max(0, mv - DEHYDRATION_MV_DRAIN))
                messages.append("|RYou are dehydrated! You lose {DEHYDRATION_MV_DRAIN} MV.|n")
        except Exception:
            pass
        messages.append("|RYou are severely dehydrated! Find water immediately!|n")
    elif new_thirst <= THIRSTY_THRESHOLD:
        messages.append("|rYou are getting thirsty.|n")

    # Well-fed bonus
    if new_hunger >= WELL_FED_THRESHOLD:
        try:
            hp = character.attributes.get("hp", 0)
            max_hp = character.attributes.get("max_hp", 100)
            if hp < max_hp:
                character.attributes.add("hp", min(max_hp, hp + WELL_FED_HP_REGEN_BONUS))
        except Exception:
            pass

    # Hydrated bonus
    if new_thirst >= HYDRATED_THRESHOLD:
        try:
            mv = character.attributes.get("mv", 0)
            max_mv = character.attributes.get("max_mv", 100)
            if mv < max_mv:
                character.attributes.add("mv", min(max_mv, mv + HYDRATED_MV_REGEN_BONUS))
        except Exception:
            pass

    return messages


def get_survival_stat_modifiers(character: Any) -> Dict[str, int]:
    """Get stat modifiers from survival state for combat/checks."""
    modifiers = {}
    hunger = _get_hunger(character)
    thirst = _get_thirst(character)

    if hunger <= STARVING_THRESHOLD:
        modifiers["str"] = STARVATION_STAT_PENALTY
        modifiers["con"] = STARVATION_STAT_PENALTY
    elif hunger <= HUNGRY_THRESHOLD:
        modifiers["str"] = HUNGRY_STAT_PENALTY
        modifiers["con"] = HUNGRY_STAT_PENALTY

    if thirst <= DEHYDRATED_THRESHOLD:
        modifiers["dex"] = DEHYDRATION_STAT_PENALTY
        modifiers["wis"] = DEHYDRATION_STAT_PENALTY
    elif thirst <= THIRSTY_THRESHOLD:
        modifiers["dex"] = THIRSTY_STAT_PENALTY
        modifiers["wis"] = THIRSTY_STAT_PENALTY

    return modifiers


def list_food() -> List[Dict]:
    """List all food items."""
    result = []
    for key, food in FOOD_ITEMS.items():
        result.append({
            "key": key,
            "name": food["name"],
            "hunger_restore": food["hunger_restore"],
            "thirst_restore": food["thirst_restore"],
            "quality": food["quality"],
            "cost": food["cost"],
        })
    return sorted(result, key=lambda f: f["cost"])


def list_drinks() -> List[Dict]:
    """List all drink items."""
    result = []
    for key, drink in DRINK_ITEMS.items():
        result.append({
            "key": key,
            "name": drink["name"],
            "thirst_restore": drink["thirst_restore"],
            "hunger_restore": drink["hunger_restore"],
            "quality": drink["quality"],
            "cost": drink["cost"],
        })
    return sorted(result, key=lambda d: d["cost"])