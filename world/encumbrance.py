"""
Encumbrance & Equipment System for 'rop'

Provides:
  - get_carry_capacity() — 20kg + 5kg per STR
  - get_current_encumbrance() — sum all item weights
  - get_encumbrance_penalty() — movement/combat penalty when overloaded
  - EQUIPMENT_SLOTS list (15 slots)
"""

from typing import Dict, List

# Equipment slots definition
EQUIPMENT_SLOTS = [
    "head",          # Helms, crowns, hoods
    "neck",          # Amulets, necklaces
    "shoulders",     # Pauldrons, mantles
    "chest",         # Chest armor, robes
    "arms",          # Bracers, vambraces
    "hands",         # Gloves, gauntlets
    "waist",         # Belts, girdles
    "legs",          # Leggings, greaves
    "feet",          # Boots, sabatons
    "ring_left",     # Left ring
    "ring_right",    # Right ring
    "main_hand",     # Primary weapon
    "off_hand",      # Shield or off-hand weapon
    "two_handed",    # Two-handed weapon (occupies main_hand + off_hand)
    "ranged",        # Bow, crossbow
]


def get_carry_capacity(character) -> float:
    """Max weight in kg based on STR."""
    stats = _get_stats(character)
    str_val = stats.get("str", 10)
    return 20.0 + (str_val * 5.0)  # 20kg base + 5kg per STR


def get_current_encumbrance(character) -> float:
    """Sum weight of all items in inventory + equipped."""
    total = 0.0
    for obj in character.contents:
        if getattr(obj, "destination", None):
            continue  # Skip exits
        total += obj.attributes.get("weight", default=0.0) if hasattr(obj, "attributes") else 0.0
    return total


def get_encumbrance_penalty(character) -> float:
    """Returns a movement/combat penalty multiplier (0.0 to 1.0)."""
    capacity = get_carry_capacity(character)
    current = get_current_encumbrance(character)
    if current <= capacity:
        return 0.0
    overload_pct = (current - capacity) / capacity
    return min(0.75, overload_pct * 0.5)  # Max 75% penalty


def get_effective_stats(character) -> Dict[str, int]:
    """Return base stats + equipment bonuses."""
    base = dict(_get_stats(character))
    equipped = character.attributes.get("equipped", default={}) if hasattr(character, "attributes") else {}
    if equipped is None or not hasattr(equipped, "items"):
        return base
    for slot, item_name in equipped.items():
        for obj in character.contents:
            if getattr(obj, "destination", None):
                continue
            if obj.key == item_name and hasattr(obj, "attributes"):
                bonuses = obj.attributes.get("stat_bonuses", default={})
                if bonuses is not None and hasattr(bonuses, "items"):
                    for stat, bonus in bonuses.items():
                        base[stat] = base.get(stat, 10) + bonus
    return base


def _get_stats(character) -> Dict[str, int]:
    """Safely fetch stats dict."""
    if hasattr(character, "attributes"):
        stats = character.attributes.get("stats", default={})
        # Evennia may return a _SaverDict (a dict-like persistent wrapper)
        # that does not subclass dict. Coerce it into a plain dict.
        if stats is not None and hasattr(stats, "items"):
            try:
                return {str(k): int(v) for k, v in stats.items()}
            except (TypeError, ValueError):
                return {}
    return {}
