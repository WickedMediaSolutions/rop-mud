"""
Necromancer Class Core Mechanics — Raise Undead Minions System

Provides:
  - Minion types (skeleton, zombie, wraith, bone_golem, lich)
  - Raise dead from corpses in the room
  - Minion management (summon, dismiss, command)
  - Minion combat integration (auto-attacks alongside master)
  - Minion scaling with Necromancer level
  - Minion cap based on level

Commands (in commands/necromancer_commands.py):
  - raise <type>     — raise a minion from a corpse
  - dismiss [minion] — dismiss a minion
  - minions          — list your active minions
  - command <minion> <action> — order a minion
"""

import random
import time
from typing import Optional, Tuple, Dict, Any, List

# ---------------------------------------------------------------------------
# Minion Types
# ---------------------------------------------------------------------------

MINION_TYPES = {
    "skeleton": {
        "name": "Skeleton Warrior",
        "min_level": 1,
        "mana_cost": 20,
        "hp_per_level": 8,
        "damage_per_level": 2,
        "armor_per_level": 0.5,
        "attack_speed": 3.0,  # seconds between attacks
        "damage_type": "slash",
        "description": "A brittle but relentless skeletal warrior.",
        "special": None,
    },
    "zombie": {
        "name": "Zombie",
        "min_level": 4,
        "mana_cost": 30,
        "hp_per_level": 12,
        "damage_per_level": 1.5,
        "armor_per_level": 1.0,
        "attack_speed": 4.0,
        "damage_type": "blunt",
        "description": "A shambling corpse with surprising durability.",
        "special": "disease_touch",  # 10% chance to apply poison on hit
    },
    "wraith": {
        "name": "Wraith",
        "min_level": 8,
        "mana_cost": 40,
        "hp_per_level": 6,
        "damage_per_level": 3,
        "armor_per_level": 0.2,
        "attack_speed": 2.5,
        "damage_type": "magic_shadow",
        "description": "An ethereal spirit that drains life force.",
        "special": "life_drain",  # Heals master for 25% of damage dealt
    },
    "bone_golem": {
        "name": "Bone Golem",
        "min_level": 14,
        "mana_cost": 60,
        "hp_per_level": 18,
        "damage_per_level": 3.5,
        "armor_per_level": 2.0,
        "attack_speed": 5.0,
        "damage_type": "blunt",
        "description": "A massive construct of fused bone and dark magic.",
        "special": "cleave",  # 20% chance to hit all enemies in room
    },
    "lich": {
        "name": "Lich",
        "min_level": 20,
        "mana_cost": 100,
        "hp_per_level": 10,
        "damage_per_level": 5,
        "armor_per_level": 1.0,
        "attack_speed": 3.0,
        "damage_type": "magic_shadow",
        "description": "A powerful undead spellcaster bound to your will.",
        "special": "shadow_bolt",  # Ranged magic attack, ignores armor
    },
}

# Maximum minions per Necromancer level
MINION_CAP_PER_LEVEL = 0.5  # 1 minion per 2 levels, rounded up

# ---------------------------------------------------------------------------
# Minion Data Class (stored as dict on character attributes)
# ---------------------------------------------------------------------------

def create_minion_data(minion_type: str, master_level: int) -> Dict[str, Any]:
    """
    Create a minion data dict for storage on the master's attributes.

    Args:
        minion_type: Key in MINION_TYPES.
        master_level: Level of the Necromancer.

    Returns:
        Dict with minion stats.
    """
    template = MINION_TYPES.get(minion_type)
    if not template:
        return {}

    level = master_level
    return {
        "type": minion_type,
        "name": template["name"],
        "hp": template["hp_per_level"] * level,
        "max_hp": template["hp_per_level"] * level,
        "damage": int(template["damage_per_level"] * level),
        "armor": int(template["armor_per_level"] * level),
        "attack_speed": template["attack_speed"],
        "damage_type": template["damage_type"],
        "special": template["special"],
        "last_attack": 0.0,
        "created_at": time.time(),
    }


# ---------------------------------------------------------------------------
# Necromancer Engine
# ---------------------------------------------------------------------------

def is_necromancer(character) -> bool:
    """Return True if the character's class is Necromancer."""
    return _get_class(character) == "Necromancer"


def get_minion_cap(character) -> int:
    """Return the maximum number of minions the character can control."""
    level = _get_level(character)
    return max(1, int(level * MINION_CAP_PER_LEVEL + 0.5))


def get_active_minions(character) -> List[Dict[str, Any]]:
    """Return list of active minion data dicts."""
    if not hasattr(character, "attributes"):
        return []
    minions = character.attributes.get("minions", default=[])
    if not isinstance(minions, list):
        return []
    return minions


def get_minion_count(character) -> int:
    """Return the number of active minions."""
    return len(get_active_minions(character))


def has_corpse_in_room(character) -> bool:
    """
    Check if there's a corpse in the character's current room.
    A corpse is any object with 'corpse' in its key or tags.
    """
    location = character.location if hasattr(character, "location") else None
    if not location:
        return False

    for obj in location.contents:
        if not hasattr(obj, "key"):
            continue
        if "corpse" in obj.key.lower():
            return True
        if hasattr(obj, "tags") and obj.tags.has("corpse", category="death"):
            return True

    return False


def raise_minion(character, minion_type: str) -> Tuple[bool, str]:
    """
    Raise an undead minion from a corpse in the room.

    Args:
        character: The Necromancer.
        minion_type: Key in MINION_TYPES.

    Returns (success, message).
    """
    if not is_necromancer(character):
        return False, "Only Necromancers can raise undead minions."

    if minion_type not in MINION_TYPES:
        return False, f"Unknown minion type '{minion_type}'. Use 'minions' to see available types."

    template = MINION_TYPES[minion_type]

    # Level check
    level = _get_level(character)
    if level < template["min_level"]:
        return False, f"You must be level {template['min_level']} to raise a {template['name']}."

    # Minion cap check
    cap = get_minion_cap(character)
    current = get_minion_count(character)
    if current >= cap:
        return False, f"You can only control {cap} minion(s). Dismiss one first."

    # Corpse check
    if not has_corpse_in_room(character):
        return False, "There is no corpse here to raise."

    # Mana cost
    mana = character.attributes.get("mana", default=0) if hasattr(character, "attributes") else 0
    mana_cost = template["mana_cost"]
    if mana < mana_cost:
        return False, f"Not enough mana to raise a {template['name']} (need {mana_cost}, have {mana})."

    # Create minion
    minion_data = create_minion_data(minion_type, level)

    # Deduct mana
    if hasattr(character, "attributes"):
        character.attributes.add("mana", mana - mana_cost)

        # Add minion to list
        minions = get_active_minions(character)
        minions.append(minion_data)
        character.attributes.add("minions", minions)

    # Consume a corpse in the room
    _consume_corpse(character)

    return True, f"You raise a {template['name']}! ({minion_data['hp']} HP, {minion_data['damage']} DMG)"


def dismiss_minion(character, minion_index: int = 0) -> Tuple[bool, str]:
    """
    Dismiss a minion.

    Args:
        character: The Necromancer.
        minion_index: Index of the minion to dismiss (0-based).

    Returns (success, message).
    """
    minions = get_active_minions(character)
    if not minions:
        return False, "You have no active minions."

    if minion_index < 0 or minion_index >= len(minions):
        return False, f"Invalid minion. You have {len(minions)} minion(s). Use 'minions' to list them."

    minion = minions.pop(minion_index)
    if hasattr(character, "attributes"):
        character.attributes.add("minions", minions)

    return True, f"You dismiss your {minion['name']}."


def dismiss_all_minions(character) -> Tuple[bool, str]:
    """Dismiss all active minions."""
    minions = get_active_minions(character)
    if not minions:
        return False, "You have no active minions."

    count = len(minions)
    if hasattr(character, "attributes"):
        character.attributes.add("minions", [])

    return True, f"You dismiss all {count} minion(s)."


def get_available_minion_types(character) -> list:
    """Return list of minion type keys available at the character's level."""
    level = _get_level(character)
    available = []
    for mtype, mdata in MINION_TYPES.items():
        if level >= mdata["min_level"]:
            available.append(mtype)
    return available


def minion_combat_tick(character, target) -> List[str]:
    """
    Process one combat tick for all active minions.
    Each minion attacks if its attack speed cooldown has elapsed.

    Called by the combat engine during auto-attack rounds.

    Returns list of message strings.
    """
    minions = get_active_minions(character)
    if not minions:
        return []

    messages = []
    now = time.time()

    for i, minion in enumerate(minions):
        # Check attack cooldown
        last_attack = minion.get("last_attack", 0)
        attack_speed = minion.get("attack_speed", 3.0)
        if now - last_attack < attack_speed:
            continue

        # Minion attacks
        minion["last_attack"] = now

        # Hit roll (simplified: 80% base hit chance)
        hit_chance = 0.80
        if random.random() > hit_chance:
            messages.append(f"|WYour {minion['name']} misses {target.key}.|n")
            continue

        # Damage
        base_dmg = minion["damage"]
        variance = random.uniform(0.8, 1.2)
        dmg = max(1, int(base_dmg * variance))

        # Apply damage to target
        if hasattr(target, "attributes"):
            hp = target.attributes.get("hp", 0)
            target.attributes.add("hp", max(0, hp - dmg))

        messages.append(f"|WYour {minion['name']} attacks {target.key} for {dmg} damage.|n")

        # Special effects
        special = minion.get("special")
        if special == "disease_touch":
            if random.random() < 0.10:
                try:
                    from world.status_effects import create_poison_effect, apply_status_effect
                    effect = create_poison_effect(
                        damage=3, duration=10.0, tick_interval=3.0,
                        source=character, source_level=_get_level(character),
                        source_stat=_get_stats(character).get("int", 10),
                    )
                    apply_status_effect(target, effect, caster=character)
                    messages.append(f"|gYour {minion['name']} infects {target.key} with disease!|n")
                except Exception:
                    pass

        elif special == "life_drain":
            heal = max(1, dmg // 4)
            if hasattr(character, "attributes"):
                hp = character.attributes.get("hp", 0)
                max_hp = character.attributes.get("max_hp", 100)
                character.attributes.add("hp", min(max_hp, hp + heal))
            messages.append(f"|mYour {minion['name']} drains {heal} life from {target.key}.|n")

        elif special == "cleave":
            if random.random() < 0.20:
                # Hit all enemies in the room
                location = character.location if hasattr(character, "location") else None
                if location:
                    for obj in location.contents:
                        if obj == character or obj == target:
                            continue
                        if not hasattr(obj, "attributes"):
                            continue
                        # Only hit mobs in combat
                        try:
                            from world.tick_combat import CombatHandler
                            if CombatHandler.is_in_combat(obj):
                                cleave_dmg = max(1, dmg // 2)
                                hp = obj.attributes.get("hp", 0)
                                obj.attributes.add("hp", max(0, hp - cleave_dmg))
                                messages.append(f"|RYour {minion['name']} cleaves {obj.key} for {cleave_dmg} damage!|n")
                        except Exception:
                            pass

        elif special == "shadow_bolt":
            # Bonus magic damage
            bonus = int(base_dmg * 0.5)
            if hasattr(target, "attributes"):
                hp = target.attributes.get("hp", 0)
                target.attributes.add("hp", max(0, hp - bonus))
            messages.append(f"|MYour {minion['name']} fires a shadow bolt for {bonus} extra damage!|n")

        # Check if target died
        if hasattr(target, "attributes") and target.attributes.get("hp", 0) <= 0:
            try:
                from world.tick_combat import _handle_target_death
                _handle_target_death(character, target)
            except Exception:
                pass
            break

    # Save updated minion data
    if hasattr(character, "attributes"):
        character.attributes.add("minions", minions)

    return messages


def minion_take_damage(character, damage: int) -> Tuple[int, List[str]]:
    """
    Distribute incoming damage to minions first (they tank for the master).
    Returns (remaining_damage, messages).

    Minions absorb damage before the master takes any.
    """
    minions = get_active_minions(character)
    if not minions:
        return damage, []

    messages = []
    remaining = damage

    for i, minion in enumerate(minions):
        if remaining <= 0:
            break

        minion_hp = minion["hp"]
        if minion_hp <= 0:
            continue

        absorbed = min(remaining, minion_hp)
        minion["hp"] -= absorbed
        remaining -= absorbed

        if minion["hp"] <= 0:
            messages.append(f"|RYour {minion['name']} is destroyed!|n")
            minion["hp"] = 0
        else:
            messages.append(f"|yYour {minion['name']} absorbs {absorbed} damage ({minion['hp']} HP remaining).|n")

    # Remove dead minions
    minions = [m for m in minions if m["hp"] > 0]
    if hasattr(character, "attributes"):
        character.attributes.add("minions", minions)

    return remaining, messages


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


def _consume_corpse(character):
    """Remove one corpse from the character's current room."""
    location = character.location if hasattr(character, "location") else None
    if not location:
        return

    for obj in location.contents:
        if not hasattr(obj, "key"):
            continue
        if "corpse" in obj.key.lower():
            try:
                obj.delete()
            except Exception:
                pass
            return
        if hasattr(obj, "tags") and obj.tags.has("corpse", category="death"):
            try:
                obj.delete()
            except Exception:
                pass
            return