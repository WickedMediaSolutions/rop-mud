"""
Environmental Hazards System for 'rop'
========================================

Adds environmental damage to rooms — lava, traps, poison gas,
freezing cold, and other hazards that affect players and mobs.

Features:
  - ``HAZARD_TYPES`` — predefined hazard definitions
  - ``apply_hazard_to_room(room, hazard_type)`` — set a room's hazard
  - ``remove_hazard_from_room(room)`` — clear hazard
  - ``process_room_hazard(room)`` — tick-based hazard damage
  - ``get_room_hazard(room)`` — inspect current hazard
  - ``check_trap(player, action)`` — detect/disarm traps

Hazard Types:
  - Lava/Magma: Fire damage per tick
  - Poison Gas: Damage over time, ignores armor
  - Freezing Cold: Cold damage + movement slow
  - Spike Trap: One-time physical damage on entry
  - Pit Trap: Fall damage + temporary stun
  - Cursed Ground: Magic damage, healing reduced

Integration:
  - Room.at_object_receive triggers entry hazards
  - Global ticker applies periodic hazard damage
  - Saving throws can reduce/negate hazard damage
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

try:
    from evennia.utils.ansi import strip_ansi
except Exception:
    strip_ansi = lambda x: str(x or "")


# ---------------------------------------------------------------------------
# Hazard Type Definitions
# ---------------------------------------------------------------------------

# Each hazard type defines:
#   damage: base damage per tick
#   damage_type: "fire" | "cold" | "poison" | "physical" | "magic"
#   tick_interval: seconds between damage ticks (0 = on-entry only)
#   armor_penetration: 0.0 (fully armored) to 1.0 (ignores armor)
#   saving_throw: ("fortitude" | "reflex" | "will", DC) or None
#   save_reduces: "half" | "negate" | "none"
#   effects: list of additional effect strings

HAZARD_TYPES: Dict[str, Dict[str, Any]] = {
    "lava": {
        "name": "Molten Lava",
        "description": "The ground is covered in searing, molten rock. The heat is unbearable.",
        "damage": 15,
        "damage_type": "fire",
        "tick_interval": 10,
        "armor_penetration": 0.5,
        "saving_throw": ("reflex", 15),
        "save_reduces": "half",
        "effects": ["burning"],
        "room_desc": "|RThe floor glows with molten lava, radiating intense heat.|n",
    },
    "poison_gas": {
        "name": "Poison Gas",
        "description": "A thick, greenish miasma hangs in the air, burning your lungs.",
        "damage": 8,
        "damage_type": "poison",
        "tick_interval": 15,
        "armor_penetration": 1.0,
        "saving_throw": ("fortitude", 12),
        "save_reduces": "half",
        "effects": [],
        "room_desc": "|gA noxious green gas fills the chamber, stinging your eyes and throat.|n",
    },
    "freezing_cold": {
        "name": "Freezing Cold",
        "description": "Bitter, unnatural cold permeates this place. Your movements slow.",
        "damage": 6,
        "damage_type": "cold",
        "tick_interval": 20,
        "armor_penetration": 0.3,
        "saving_throw": ("fortitude", 14),
        "save_reduces": "half",
        "effects": ["slowed"],
        "room_desc": "|cFrigid air bites at your skin, and ice crystals form on every surface.|n",
    },
    "spike_trap": {
        "name": "Spike Trap",
        "description": "Sharpened spikes spring from hidden panels in the floor!",
        "damage": 25,
        "damage_type": "physical",
        "tick_interval": 0,  # One-time on entry
        "armor_penetration": 0.8,
        "saving_throw": ("reflex", 16),
        "save_reduces": "negate",
        "effects": ["bleeding"],
        "room_desc": "|YYou notice small holes in the walls and floor — a trap mechanism.|n",
    },
    "pit_trap": {
        "name": "Pit Trap",
        "description": "The floor gives way beneath you, plunging you into darkness!",
        "damage": 20,
        "damage_type": "physical",
        "tick_interval": 0,  # One-time on entry
        "armor_penetration": 0.0,
        "saving_throw": ("reflex", 14),
        "save_reduces": "negate",
        "effects": ["stunned"],
        "room_desc": "|WA section of the floor looks suspiciously unstable.|n",
    },
    "cursed_ground": {
        "name": "Cursed Ground",
        "description": "The very earth here is tainted by dark magic. Your life force drains away.",
        "damage": 10,
        "damage_type": "magic",
        "tick_interval": 12,
        "armor_penetration": 1.0,
        "saving_throw": ("will", 16),
        "save_reduces": "half",
        "effects": ["healing_reduced"],
        "room_desc": "|MDark energy crackles across the ground, and the air hums with malevolence.|n",
    },
    "acid_pool": {
        "name": "Acid Pool",
        "description": "Bubbling pools of corrosive acid eat away at everything they touch.",
        "damage": 12,
        "damage_type": "poison",
        "tick_interval": 10,
        "armor_penetration": 0.7,
        "saving_throw": ("reflex", 13),
        "save_reduces": "half",
        "effects": ["armor_damage"],
        "room_desc": "|gSizzling pools of green acid dot the floor, filling the air with acrid fumes.|n",
    },
    "lightning_storm": {
        "name": "Lightning Storm",
        "description": "Crackling bolts of electricity arc through the chamber!",
        "damage": 18,
        "damage_type": "magic",
        "tick_interval": 30,
        "armor_penetration": 0.2,
        "saving_throw": ("reflex", 18),
        "save_reduces": "half",
        "effects": ["stunned"],
        "room_desc": "|Y|bBolts of lightning dance across the ceiling, filling the room with ozone.|n",
    },
    "crushing_walls": {
        "name": "Crushing Walls",
        "description": "The walls are slowly closing in, threatening to crush everything between them!",
        "damage": 30,
        "damage_type": "physical",
        "tick_interval": 25,
        "armor_penetration": 0.6,
        "saving_throw": ("fortitude", 20),
        "save_reduces": "half",
        "effects": [],
        "room_desc": "|RThe walls grind inward with a deafening rumble. The room is shrinking!|n",
    },
}


# ---------------------------------------------------------------------------
# Hazard Application
# ---------------------------------------------------------------------------

def apply_hazard_to_room(room: Any, hazard_type: str) -> bool:
    """
    Set a room's environmental hazard.

    Args:
        room: The room object.
        hazard_type: Key in HAZARD_TYPES.

    Returns:
        True if applied, False if hazard_type is invalid.
    """
    hazard = HAZARD_TYPES.get(hazard_type)
    if hazard is None:
        return False

    try:
        room.attributes.add("env_hazard", hazard_type)
        room.attributes.add("env_hazard_data", hazard)
    except Exception:
        return False

    return True


def remove_hazard_from_room(room: Any) -> bool:
    """Remove a room's environmental hazard."""
    try:
        room.attributes.add("env_hazard", None)
        room.attributes.add("env_hazard_data", None)
        return True
    except Exception:
        return False


def get_room_hazard(room: Any) -> Optional[Dict[str, Any]]:
    """Return the hazard data dict for a room, or None."""
    try:
        hazard_type = room.attributes.get("env_hazard", default=None)
        if hazard_type:
            return HAZARD_TYPES.get(hazard_type, room.attributes.get("env_hazard_data"))
    except Exception:
        pass
    return None


def get_room_hazard_type(room: Any) -> Optional[str]:
    """Return the hazard type key for a room, or None."""
    try:
        return room.attributes.get("env_hazard", default=None)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Hazard Processing
# ---------------------------------------------------------------------------

def _make_saving_throw(target: Any, save_type: str, dc: int) -> bool:
    """Attempt a saving throw. Returns True if saved."""
    try:
        from world.saving_throws import make_saving_throw
        return make_saving_throw(target, save_type, dc)
    except Exception:
        pass

    # Fallback: simple roll
    try:
        stats = target.attributes.get("stats", default={})
        bonus = 0
        if save_type == "fortitude":
            bonus = (stats.get("con", 10) - 10) // 2
        elif save_type == "reflex":
            bonus = (stats.get("dex", 10) - 10) // 2
        elif save_type == "will":
            bonus = (stats.get("wis", 10) - 10) // 2
        roll = random.randint(1, 20) + bonus
        return roll >= dc
    except Exception:
        return False


def _calculate_hazard_damage(
    hazard: Dict[str, Any],
    target: Any,
) -> Tuple[int, str]:
    """
    Calculate actual damage after saves and mitigation.

    Returns (damage, result_string).
    """
    base_damage = hazard["damage"]
    damage_type = hazard["damage_type"]

    # Saving throw
    save_info = hazard.get("saving_throw")
    saved = False
    if save_info:
        save_type, dc = save_info
        saved = _make_saving_throw(target, save_type, dc)

    if saved and hazard.get("save_reduces") == "negate":
        return (0, f"|g{save_type.upper()} save — damage negated!|n")
    elif saved and hazard.get("save_reduces") == "half":
        base_damage = max(1, base_damage // 2)

    # Armor mitigation
    armor_pen = hazard.get("armor_penetration", 0.0)
    if armor_pen < 1.0:
        try:
            from world.damage_formulas import calculate_armor_absorption, DamageType
            dt_map = {
                "fire": DamageType.FIRE,
                "cold": DamageType.COLD,
                "poison": DamageType.POISON,
                "physical": DamageType.SLASH,
                "magic": DamageType.MAGIC,
            }
            dt = dt_map.get(damage_type, DamageType.SLASH)
            absorbed = calculate_armor_absorption(target, base_damage, dt)
            absorbed = int(absorbed * (1.0 - armor_pen))
            base_damage = max(1, base_damage - absorbed)
        except Exception:
            pass

    result = f"|R{base_damage} {damage_type} damage|n"
    if saved:
        result += f" |y(half on save)|n"

    return (base_damage, result)


def process_room_hazard(room: Any) -> List[Dict[str, Any]]:
    """
    Apply hazard damage to all creatures in a room.

    Should be called by a global ticker script.

    Returns:
      List of {target, damage, result_msg} dicts for affected creatures.
    """
    hazard = get_room_hazard(room)
    if hazard is None:
        return []

    results = []

    # Skip one-shot traps that already triggered
    if hazard.get("tick_interval", 0) == 0:
        return []

    try:
        contents = list(room.contents)
    except Exception:
        return results

    for obj in contents:
        # Only affect creatures (players and mobs)
        if not hasattr(obj, "attributes"):
            continue
        is_player = getattr(obj, "has_account", False)
        is_mob = obj.attributes.get("is_mob", False) or obj.attributes.get("is_aggro") is not None

        if not (is_player or is_mob):
            continue

        damage, result_str = _calculate_hazard_damage(hazard, obj)

        if damage <= 0:
            continue

        try:
            hp = obj.attributes.get("hp", 0) or 0
            new_hp = max(0, hp - damage)
            obj.attributes.add("hp", new_hp)
        except Exception:
            continue

        # Apply effects
        for effect in hazard.get("effects", []):
            try:
                _apply_hazard_effect(obj, effect)
            except Exception:
                pass

        # Notify
        hazard_name = hazard.get("name", "Environmental Hazard")
        msg_in = f"|R[ENV] {hazard_name} deals {result_str}!|n [HP: {new_hp}]"
        try:
            obj.msg(msg_in)
        except Exception:
            pass

        # Notify others in room
        name = getattr(obj, "key", "Something")
        msg_others = f"|R{name} is hurt by the {hazard_name}!|n"
        for other in contents:
            if other is obj and hasattr(other, "msg"):
                continue
            try:
                if hasattr(other, "msg"):
                    other.msg(msg_others)
            except Exception:
                pass

        results.append({
            "target": name,
            "damage": damage,
            "result": result_str,
        })

        # Death check for mobs
        if is_mob and new_hp <= 0:
            try:
                from world.tick_combat import CombatHandler
                CombatHandler.handle_death(obj, None)
            except Exception:
                pass

    return results


def process_entry_hazard(room: Any, entrant: Any) -> Optional[str]:
    """
    Process one-shot hazards (traps) when something enters a room.

    Should be called from Room.at_object_receive.

    Returns:
        A message string if a trap was triggered, None otherwise.
    """
    hazard = get_room_hazard(room)
    if hazard is None:
        return None

    # Only process one-shot traps here; tick-based hazards handled by ticker
    tick_interval = hazard.get("tick_interval", 0)
    if tick_interval != 0:
        return None

    is_player = getattr(entrant, "has_account", False)
    is_mob = entrant.attributes.get("is_mob", False) if hasattr(entrant, "attributes") else False

    if not (is_player or is_mob):
        return None

    # Racial passive: trap immunity (Pixie).
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(entrant)
        if racial.get("trap_immune"):
            name = getattr(entrant, "key", "Something")
            entrant.msg("|gYour wings flutter as you glide over the trap unharmed!|n")
            return f"|g{name} glides over the trap unharmed!|n"
    except Exception:
        pass

    damage, result_str = _calculate_hazard_damage(hazard, entrant)

    if damage <= 0:
        return None

    try:
        hp = entrant.attributes.get("hp", 0) or 0
        new_hp = max(0, hp - damage)
        entrant.attributes.add("hp", new_hp)
    except Exception:
        return None

    # Apply effects
    for effect in hazard.get("effects", []):
        try:
            _apply_hazard_effect(entrant, effect)
        except Exception:
            pass

    hazard_name = hazard.get("name", "Trap")
    name = getattr(entrant, "key", "Something")
    msg = f"|R[TRAP] {name} triggers {hazard_name} — {result_str}!|n [HP: {new_hp}]"

    # Notify everyone in the room
    try:
        for obj in room.contents:
            if hasattr(obj, "msg"):
                obj.msg(msg)
    except Exception:
        pass

    return msg


def _apply_hazard_effect(target: Any, effect: str) -> None:
    """Apply a hazard effect to a target."""
    if effect == "burning":
        # Small DoT already handled by tick, mark for display
        target.attributes.add("is_burning", True)
    elif effect == "slowed":
        target.attributes.add("movement_slowed", True)
    elif effect == "stunned":
        # Apply short stun
        try:
            from world.combat_state import CombatState
            state = target.attributes.get("combat_state")
            if state == "FIGHTING":
                target.attributes.add("combat_state", "STUNNED")
        except Exception:
            pass
    elif effect == "bleeding":
        target.attributes.add("is_bleeding", True)
    elif effect == "healing_reduced":
        target.attributes.add("healing_reduced", True)
    elif effect == "armor_damage":
        # Placeholder for equipment damage
        pass


# ---------------------------------------------------------------------------
# Hazard Ticker (called by global tick script)
# ---------------------------------------------------------------------------

def tick_all_room_hazards() -> Dict[str, Any]:
    """
    Process hazards for all rooms.  Call from a global ticker.

    Returns summary:
      {"rooms_processed": int, "hazards_triggered": int, "total_damage": int}
    """
    summary = {"rooms_processed": 0, "hazards_triggered": 0, "total_damage": 0}

    try:
        from evennia.objects.models import ObjectDB
        rooms = ObjectDB.objects.filter(db_typeclass_path__endswith="Room")
    except Exception:
        return summary

    for room in rooms:
        hazard_type = get_room_hazard_type(room)
        if hazard_type is None:
            continue
        summary["rooms_processed"] += 1
        results = process_room_hazard(room)
        if results:
            summary["hazards_triggered"] += 1
            for r in results:
                summary["total_damage"] += r.get("damage", 0)

    return summary


# ---------------------------------------------------------------------------
# Trap Detection & Disarming
# ---------------------------------------------------------------------------

def check_trap(player: Any, action: str = "detect") -> str:
    """
    Attempt to detect or disarm a trap in the current room.

    Args:
        player: The player attempting the action.
        action: "detect" or "disarm"

    Returns:
        A formatted message string.
    """
    room = player.location
    if room is None:
        return "You are nowhere."

    hazard = get_room_hazard(room)
    if hazard is None:
        if action == "detect":
            return "You find no traps here."
        return "There is nothing to disarm here."

    # Only traps (one-shot) can be detected/disarmed
    if hazard.get("tick_interval", 0) != 0:
        if action == "detect":
            return f"You sense {hazard.get('name', 'danger')} here, but it's not a trap you can disarm."
        return f"This {hazard.get('name', 'hazard')} cannot be disarmed — find another way around."

    # Skill check
    try:
        stats = player.attributes.get("stats", default={})
        dex = stats.get("dex", 10)
        wis = stats.get("wis", 10)
        level = player.attributes.get("level", 1)
        bonus = (dex - 10) // 2 + level // 5
    except Exception:
        bonus = 0

    roll = random.randint(1, 20) + bonus

    if action == "detect":
        dc = 12
        if roll >= dc:
            hazard_name = hazard.get("name", "trap")
            desc = hazard.get("room_desc", "")
            return f"|gYou detect a {hazard_name}!|n {desc}"
        else:
            return "You fail to detect any traps. Perhaps there are none... or perhaps they are well hidden."

    elif action == "disarm":
        # Must detect first (tracked via temporary attr)
        detected = player.attributes.get("last_trap_detected", default=None)
        if detected != room.id:
            return "|yYou should detect traps first before attempting to disarm.|n"

        dc = 15
        if roll >= dc:
            remove_hazard_from_room(room)
            player.attributes.add("last_trap_detected", None)
            # XP reward
            try:
                xp = player.attributes.get("xp", 0) or 0
                player.attributes.add("xp", xp + 15)
            except Exception:
                pass
            return "|gYou successfully disarm the trap! (+15 XP)|n"
        else:
            # Oops — trigger the trap
            result = process_entry_hazard(room, player)
            return f"|rYour attempt fails!\n{result}|n" if result else "|rYour attempt fails!|n"

    return "Unknown action. Use 'detect' or 'disarm'."


def mark_trap_detected(player: Any) -> None:
    """Record that the player detected a trap in their current room."""
    room = player.location
    if room:
        try:
            player.attributes.add("last_trap_detected", room.id)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Room Display Integration
# ---------------------------------------------------------------------------

def get_hazard_room_desc(room: Any) -> str:
    """
    Return a warning/description string for a room's hazard.
    Should be appended to room descriptions for visible hazards.
    """
    hazard = get_room_hazard(room)
    if hazard is None:
        return ""
    return hazard.get("room_desc", "")


def get_hazard_list() -> List[Dict[str, Any]]:
    """Return a summary of all available hazard types for admin reference."""
    result = []
    for key, data in HAZARD_TYPES.items():
        result.append({
            "key": key,
            "name": data["name"],
            "damage": data["damage"],
            "damage_type": data["damage_type"],
            "tick_interval": data["tick_interval"],
            "is_trap": data["tick_interval"] == 0,
        })
    return result