"""
Mounts & Riding System for 'rop'
================================

Provides:
  - Mount definitions with speed, HP, and combat bonuses
  - Mount ownership, summoning, and dismissing
  - Mount movement speed bonus applied to travel
  - Mounted combat modifiers (charge bonus, stability)
  - Mount fatigue/endurance management

Design:
  - Mounts stored as character attributes: mount_key, mount_name, mount_level
  - Mount speed bonus applied via get_mount_speed_bonus()
  - Mounted state tracked via mount_active attribute
  - Mount types: horse, warhorse, wolf, griffon, dragon, etc.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Mount definitions
# ---------------------------------------------------------------------------

MOUNTS = {
    "riding_horse": {
        "name": "Riding Horse",
        "desc": "A sturdy, dependable horse for everyday travel.",
        "speed_bonus_pct": 15,
        "max_hp": 100,
        "cost": 50,
        "min_level": 1,
        "combat_bonus": {"charge_damage_pct": 0},
        "stamina_drain": 5,
    },
    "warhorse": {
        "name": "Warhorse",
        "desc": "A powerful steed bred for battle.",
        "speed_bonus_pct": 20,
        "max_hp": 200,
        "cost": 250,
        "min_level": 10,
        "combat_bonus": {"charge_damage_pct": 25},
        "stamina_drain": 8,
    },
    "dire_wolf": {
        "name": "Dire Wolf",
        "desc": "A fierce, loyal wolf that strikes fear into enemies.",
        "speed_bonus_pct": 25,
        "max_hp": 180,
        "cost": 400,
        "min_level": 20,
        "combat_bonus": {"charge_damage_pct": 20, "intimidate_pct": 10},
        "stamina_drain": 10,
    },
    "griffon": {
        "name": "Griffon",
        "desc": "A majestic winged beast, swift as the wind.",
        "speed_bonus_pct": 35,
        "max_hp": 300,
        "cost": 1000,
        "min_level": 35,
        "combat_bonus": {"charge_damage_pct": 35, "flyover_pct": 15},
        "stamina_drain": 12,
    },
    "nightmare": {
        "name": "Nightmare",
        "desc": "A shadowy steed wreathed in hellfire.",
        "speed_bonus_pct": 30,
        "max_hp": 350,
        "cost": 1500,
        "min_level": 40,
        "combat_bonus": {"charge_damage_pct": 40, "fear_pct": 20},
        "stamina_drain": 12,
    },
    "dragon_mount": {
        "name": "Dragon Mount",
        "desc": "A legendary dragon that carries its rider into battle.",
        "speed_bonus_pct": 50,
        "max_hp": 600,
        "cost": 5000,
        "min_level": 60,
        "combat_bonus": {"charge_damage_pct": 60, "flyover_pct": 30, "fear_pct": 25},
        "stamina_drain": 20,
    },
}

# Mount XP needed to level up
MOUNT_XP_PER_LEVEL = 50
MOUNT_MAX_LEVEL = 50

# Cooldown between mount summon/dismiss (seconds)
MOUNT_COOLDOWN = 10.0


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_mount_data(character: Any) -> Optional[Dict]:
    """Get a character's mount data dict."""
    try:
        return character.attributes.get("mount_data", None)
    except Exception:
        return None


def _save_mount_data(character: Any, data: Dict) -> None:
    """Save a character's mount data dict."""
    try:
        character.attributes.add("mount_data", data)
    except Exception:
        pass


def _has_mount(character: Any) -> bool:
    """Check if a character owns a mount."""
    data = _get_mount_data(character)
    return bool(data and data.get("key"))


def _is_mounted(character: Any) -> bool:
    """Check if a character is currently mounted."""
    try:
        return character.attributes.get("mounted", False)
    except Exception:
        return False


def _get_mount_level(character: Any) -> int:
    """Get a character's mount level for their owned mount."""
    data = _get_mount_data(character)
    if not data:
        return 1
    return data.get("level", 1)


def _get_mount_xp(character: Any) -> int:
    """Get a character's mount XP."""
    data = _get_mount_data(character)
    if not data:
        return 0
    return data.get("xp", 0)


def _get_mount_hp(character: Any) -> int:
    """Get a character's mount current HP."""
    data = _get_mount_data(character)
    if not data:
        return 0
    return data.get("hp", 0)


def _add_mount_xp(character: Any, xp: int) -> Tuple[int, bool]:
    """Add XP to the character's mount. Returns (new_level, did_level_up)."""
    data = _get_mount_data(character)
    if not data:
        return 1, False

    current_level = data.get("level", 1)
    if current_level >= MOUNT_MAX_LEVEL:
        return current_level, False

    current_xp = data.get("xp", 0)
    new_xp = current_xp + xp
    xp_needed = current_level * MOUNT_XP_PER_LEVEL

    did_level_up = False
    while new_xp >= xp_needed and current_level < MOUNT_MAX_LEVEL:
        new_xp -= xp_needed
        current_level += 1
        xp_needed = current_level * MOUNT_XP_PER_LEVEL
        did_level_up = True

    data["level"] = current_level
    data["xp"] = new_xp
    _save_mount_data(character, data)
    return current_level, did_level_up


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_mounts() -> List[Dict]:
    """List all mount definitions."""
    result = []
    for key, mount in MOUNTS.items():
        result.append({
            "key": key,
            "name": mount["name"],
            "desc": mount["desc"],
            "speed_bonus_pct": mount["speed_bonus_pct"],
            "max_hp": mount["max_hp"],
            "cost": mount["cost"],
            "min_level": mount["min_level"],
        })
    return sorted(result, key=lambda m: m["min_level"])


def buy_mount(character: Any, mount_key: str) -> Tuple[bool, str]:
    """Purchase a mount for a character."""
    if mount_key not in MOUNTS:
        return False, f"Unknown mount: {mount_key}. Use 'mounts list' to see available mounts."

    if _has_mount(character):
        return False, "You already own a mount. Dismiss it first if you wish to buy another."

    mount = MOUNTS[mount_key]
    char_level = character.attributes.get("level", 1) if hasattr(character, "attributes") else 1
    if char_level < mount["min_level"]:
        return False, f"You must be level {mount['min_level']} to buy a {mount['name']}."

    # Check gold
    from world.economy import remove_money
    if not remove_money(character, mount["cost"]):
        return False, f"You don't have enough gold for a {mount['name']} (cost: {mount['cost']})."

    data = {
        "key": mount_key,
        "name": mount["name"],
        "level": 1,
        "xp": 0,
        "hp": mount["max_hp"],
        "max_hp": mount["max_hp"],
        "purchased_at": time.time(),
    }
    _save_mount_data(character, data)
    return True, f"You purchase a |Y{mount['name']}|n for {mount['cost']} gold!"


def mount_up(character: Any) -> Tuple[bool, str]:
    """Mount the character's owned mount."""
    if not _has_mount(character):
        return False, "You don't own a mount."

    if _is_mounted(character):
        return False, "You are already mounted."

    data = _get_mount_data(character)
    if data.get("hp", 0) <= 0:
        return False, f"Your {data['name']} is exhausted and must rest first."

    try:
        character.attributes.add("mounted", True)
    except Exception:
        pass

    # Apply speed bonus
    mount = MOUNTS.get(data["key"], {})
    speed_bonus = mount.get("speed_bonus_pct", 0)
    mount_level = data.get("level", 1)
    total_speed_bonus = speed_bonus + (mount_level - 1) * 2  # +2% per mount level

    try:
        character.attributes.add("mount_speed_bonus", total_speed_bonus)
    except Exception:
        pass

    return True, f"You mount your |Y{data['name']}|n. Movement speed +{total_speed_bonus}%!"


def dismount(character: Any) -> Tuple[bool, str]:
    """Dismount the character."""
    if not _is_mounted(character):
        return False, "You are not mounted."

    try:
        character.attributes.add("mounted", False)
        character.attributes.add("mount_speed_bonus", 0)
    except Exception:
        pass

    return True, "You dismount."


def get_mount_speed_bonus(character: Any) -> int:
    """Get the current mount speed bonus percentage for movement cost reduction."""
    if not _is_mounted(character):
        return 0
    try:
        return character.attributes.get("mount_speed_bonus", 0)
    except Exception:
        return 0


def get_mount_combat_bonuses(character: Any) -> Dict[str, int]:
    """Get mounted combat bonuses for the character."""
    if not _is_mounted(character):
        return {}

    data = _get_mount_data(character)
    if not data:
        return {}

    mount = MOUNTS.get(data["key"], {})
    combat_bonus = mount.get("combat_bonus", {})
    mount_level = data.get("level", 1)

    # Scale combat bonuses with mount level
    scaled = {}
    for key, value in combat_bonus.items():
        scaled[key] = value + (mount_level - 1) * 2
    return scaled


def drain_mount_stamina(character: Any) -> Tuple[int, bool]:
    """
    Drain mount stamina during travel/combat. Returns (new_hp, exhausted).

    Call periodically during movement. When HP reaches 0, the mount is
    exhausted and the character auto-dismounts.
    """
    if not _is_mounted(character):
        return 0, False

    data = _get_mount_data(character)
    if not data:
        return 0, False

    mount = MOUNTS.get(data["key"], {})
    drain = mount.get("stamina_drain", 5)
    current_hp = data.get("hp", 0)
    new_hp = max(0, current_hp - drain)
    data["hp"] = new_hp
    _save_mount_data(character, data)

    if new_hp <= 0:
        dismount(character)
        return 0, True  # exhausted
    return new_hp, False


def rest_mount(character: Any) -> Tuple[bool, str]:
    """Rest the character's mount, restoring HP."""
    data = _get_mount_data(character)
    if not data:
        return False, "You don't own a mount."

    max_hp = data.get("max_hp", 100)
    current_hp = data.get("hp", 0)

    if current_hp >= max_hp:
        return False, f"Your {data['name']} is already fully rested."

    new_hp = min(max_hp, current_hp + max_hp // 2)
    data["hp"] = new_hp
    _save_mount_data(character, data)
    return True, f"You rest your {data['name']}. It recovers to {new_hp}/{max_hp} HP."


def feed_mount(character: Any) -> Tuple[bool, str]:
    """Feed the mount, granting XP and restoring stamina."""
    data = _get_mount_data(character)
    if not data:
        return False, "You don't own a mount."

    from world.survival import consume_food
    ok, msg = consume_food(character, 1)
    if not ok:
        return False, msg

    # Restore HP and grant XP
    max_hp = data.get("max_hp", 100)
    restored = max_hp // 4
    data["hp"] = min(max_hp, data.get("hp", 0) + restored)
    _save_mount_data(character, data)

    new_level, did_level_up = _add_mount_xp(character, 10)

    result_msg = f"You feed your {data['name']}. It recovers {restored} HP and gains 10 XP."
    if did_level_up:
        result_msg += f"\n|YYour {data['name']} reached bond level {new_level}!|n"
    return True, result_msg


def get_mount_info(character: Any) -> Optional[Dict]:
    """Get full mount info for a character."""
    if not _has_mount(character):
        return None

    data = _get_mount_data(character)
    mount = MOUNTS.get(data["key"], {})
    level = data.get("level", 1)
    xp = data.get("xp", 0)
    xp_needed = level * MOUNT_XP_PER_LEVEL

    return {
        "key": data["key"],
        "name": data["name"],
        "desc": mount.get("desc", ""),
        "level": level,
        "xp": xp,
        "xp_needed": xp_needed,
        "hp": data.get("hp", 0),
        "max_hp": data.get("max_hp", 0),
        "speed_bonus_pct": mount.get("speed_bonus_pct", 0),
        "mounted": _is_mounted(character),
        "combat_bonus": mount.get("combat_bonus", {}),
    }