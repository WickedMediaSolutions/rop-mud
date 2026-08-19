"""
Monk Class Core Mechanics — Ki Power System

Provides:
  - Ki resource pool (scales with WIS + level)
  - Ki regeneration (passive over time)
  - Martial arts scaling (unarmed damage scales with level + DEX)
  - Ki abilities: Flurry of Blows, Stunning Strike, Chi Heal, Meditate
  - Combo point system (build combo, spend on finishers)
  - Integration with combat (unarmed damage, dodge, ki abilities)

Commands (in commands/monk_commands.py):
  - flurry          — spend ki for rapid attacks
  - stunningstrike  — spend ki to stun target
  - chiheal         — spend ki to heal self
  - meditate        — enter meditation to regenerate ki faster
  - ki              — display ki pool status
"""

import random
import time
from typing import Optional, Tuple, Dict, Any

# ---------------------------------------------------------------------------
# Ki Constants
# ---------------------------------------------------------------------------

# Base ki pool at level 1
BASE_KI = 20

# Ki gained per level
KI_PER_LEVEL = 5

# Ki gained per point of WIS above 10
KI_PER_WIS = 3

# Passive ki regeneration per tick (every 6 seconds)
KI_REGEN_PER_TICK = 1

# Meditation ki regeneration multiplier
MEDITATION_KI_MULT = 3.0

# Maximum combo points
MAX_COMBO_POINTS = 5

# ---------------------------------------------------------------------------
# Martial Arts Scaling
# ---------------------------------------------------------------------------

# Base unarmed damage at level 1
BASE_UNARMED_DAMAGE = 4

# Unarmed damage per level
UNARMED_DAMAGE_PER_LEVEL = 1.5

# Unarmed damage per DEX above 10
UNARMED_DAMAGE_PER_DEX = 0.5

# Dodge bonus per level (passive)
DODGE_PER_LEVEL = 0.5  # percentage points

# ---------------------------------------------------------------------------
# Ki Abilities
# ---------------------------------------------------------------------------

KI_ABILITIES = {
    "flurry": {
        "name": "Flurry of Blows",
        "min_level": 1,
        "ki_cost": 10,
        "cooldown": 6.0,
        "description": "Unleash a rapid series of strikes for 3x unarmed attacks.",
        "attacks": 3,
        "damage_mult": 0.7,  # Each hit does 70% of normal unarmed damage
    },
    "stunning_strike": {
        "name": "Stunning Strike",
        "min_level": 4,
        "ki_cost": 15,
        "cooldown": 12.0,
        "description": "A precise strike that can stun the target.",
        "stun_chance": 0.30,
        "stun_duration": 4.0,
        "damage_mult": 1.2,
    },
    "chi_heal": {
        "name": "Chi Heal",
        "min_level": 6,
        "ki_cost": 20,
        "cooldown": 15.0,
        "description": "Channel ki to heal wounds.",
        "heal_pct": 0.20,  # Heal 20% of max HP
    },
    "tiger_palm": {
        "name": "Tiger Palm",
        "min_level": 10,
        "ki_cost": 12,
        "cooldown": 8.0,
        "description": "A powerful open-palm strike that builds combo points.",
        "damage_mult": 1.5,
        "combo_gain": 2,
    },
    "dragon_kick": {
        "name": "Dragon Kick",
        "min_level": 14,
        "ki_cost": 25,
        "cooldown": 20.0,
        "description": "A devastating kick finisher. Consumes all combo points for bonus damage.",
        "damage_mult": 2.0,
        "combo_required": 3,
        "combo_dmg_per_point": 0.3,  # +30% damage per combo point consumed
    },
    "serenity": {
        "name": "Serenity",
        "min_level": 18,
        "ki_cost": 30,
        "cooldown": 60.0,
        "description": "Enter a state of perfect focus. Full ki restore + 50% dodge for 10s.",
        "dodge_bonus": 50,
        "dodge_duration": 10.0,
    },
}

# ---------------------------------------------------------------------------
# Ki Engine
# ---------------------------------------------------------------------------

def is_monk(character) -> bool:
    """Return True if the character's class is Monk."""
    return _get_class(character) == "Monk"


def get_max_ki(character) -> int:
    """
    Calculate the maximum ki pool for a Monk.

    Formula: BASE_KI + (level * KI_PER_LEVEL) + ((WIS - 10) * KI_PER_WIS)
    """
    level = _get_level(character)
    stats = _get_stats(character)
    wis = stats.get("wis", 10)
    wis_bonus = max(0, (wis - 10) * KI_PER_WIS)
    return BASE_KI + (level * KI_PER_LEVEL) + wis_bonus


def get_current_ki(character) -> int:
    """Return the character's current ki points."""
    if not hasattr(character, "attributes"):
        return 0
    return character.attributes.get("ki", default=0)


def get_combo_points(character) -> int:
    """Return the character's current combo points."""
    if not hasattr(character, "attributes"):
        return 0
    return character.attributes.get("combo_points", default=0)


def get_unarmed_damage(character) -> int:
    """
    Calculate the Monk's unarmed damage.

    Formula: BASE_UNARMED_DAMAGE + (level * UNARMED_DAMAGE_PER_LEVEL)
             + ((DEX - 10) * UNARMED_DAMAGE_PER_DEX)

    This is used when the Monk has no weapon equipped (or fist weapon).
    """
    level = _get_level(character)
    stats = _get_stats(character)
    dex = stats.get("dex", 10)
    dex_bonus = max(0, (dex - 10) * UNARMED_DAMAGE_PER_DEX)
    return int(BASE_UNARMED_DAMAGE + (level * UNARMED_DAMAGE_PER_LEVEL) + dex_bonus)


def get_passive_dodge_bonus(character) -> float:
    """
    Return the Monk's passive dodge bonus (percentage points).
    Only applies to Monks.
    """
    if not is_monk(character):
        return 0.0
    level = _get_level(character)
    return level * DODGE_PER_LEVEL


def initialize_ki(character):
    """Initialize the ki pool for a new Monk character."""
    if not hasattr(character, "attributes"):
        return
    max_ki = get_max_ki(character)
    character.attributes.add("ki", max_ki)
    character.attributes.add("combo_points", 0)
    character.attributes.add("last_ki_regen", time.time())


def regenerate_ki(character) -> int:
    """
    Regenerate ki passively over time.
    Called periodically (e.g., every 6 seconds).

    Returns the amount of ki regenerated.
    """
    if not is_monk(character):
        return 0

    if not hasattr(character, "attributes"):
        return 0

    last_regen = character.attributes.get("last_ki_regen", time.time())
    now = time.time()
    elapsed = now - last_regen

    # Regenerate every 6 seconds
    regen_interval = 6.0
    if elapsed < regen_interval:
        return 0

    ticks = int(elapsed / regen_interval)
    if ticks <= 0:
        return 0

    # Check if meditating
    is_meditating = character.attributes.get("position", default="standing") == "meditating"
    regen_per_tick = KI_REGEN_PER_TICK
    if is_meditating:
        regen_per_tick = int(KI_REGEN_PER_TICK * MEDITATION_KI_MULT)

    total_regen = ticks * regen_per_tick
    max_ki = get_max_ki(character)
    current_ki = get_current_ki(character)
    new_ki = min(max_ki, current_ki + total_regen)

    character.attributes.add("ki", new_ki)
    character.attributes.add("last_ki_regen", now)

    return new_ki - current_ki


def spend_ki(character, amount: int) -> bool:
    """
    Attempt to spend ki points.
    Returns True if successful, False if insufficient ki.
    """
    if not hasattr(character, "attributes"):
        return False

    current = get_current_ki(character)
    if current < amount:
        return False

    character.attributes.add("ki", current - amount)
    return True


def add_combo_points(character, amount: int):
    """Add combo points to the character."""
    if not hasattr(character, "attributes"):
        return
    current = get_combo_points(character)
    new_total = min(MAX_COMBO_POINTS, current + amount)
    character.attributes.add("combo_points", new_total)


def consume_combo_points(character, amount: int) -> int:
    """
    Consume combo points. Returns the number actually consumed.
    """
    if not hasattr(character, "attributes"):
        return 0
    current = get_combo_points(character)
    consumed = min(current, amount)
    character.attributes.add("combo_points", current - consumed)
    return consumed


# ---------------------------------------------------------------------------
# Ki Ability Execution
# ---------------------------------------------------------------------------

def use_flurry(character, target) -> Tuple[bool, str]:
    """
    Execute Flurry of Blows: 3 rapid unarmed strikes.

    Returns (success, message).
    """
    ability = KI_ABILITIES["flurry"]

    if not is_monk(character):
        return False, "Only Monks can use ki abilities."

    level = _get_level(character)
    if level < ability["min_level"]:
        return False, f"You must be level {ability['min_level']} to use {ability['name']}."

    if not spend_ki(character, ability["ki_cost"]):
        return False, f"Not enough ki for {ability['name']} (need {ability['ki_cost']})."

    # Cooldown check
    cooldowns = character.attributes.get("ki_cooldowns", {}) if hasattr(character, "attributes") else {}
    remaining = cooldowns.get("flurry", 0) - time.time()
    if remaining > 0:
        return False, f"{ability['name']} is on cooldown for {int(remaining)}s."

    # Execute attacks
    unarmed_dmg = get_unarmed_damage(character)
    total_dmg = 0
    hits = 0
    messages = []

    for _ in range(ability["attacks"]):
        # Hit roll (85% base for Monk)
        if random.random() < 0.85:
            dmg = max(1, int(unarmed_dmg * ability["damage_mult"] * random.uniform(0.8, 1.2)))
            total_dmg += dmg
            hits += 1

    if hits == 0:
        messages.append(f"Your {ability['name']} misses completely!")
    else:
        if hasattr(target, "attributes"):
            hp = target.attributes.get("hp", 0)
            target.attributes.add("hp", max(0, hp - total_dmg))
        messages.append(f"|g{ability['name']}: {hits}/{ability['attacks']} hits for {total_dmg} damage!|n")

        # Build 1 combo point
        add_combo_points(character, 1)

    # Set cooldown
    if hasattr(character, "attributes"):
        cooldowns["flurry"] = time.time() + ability["cooldown"]
        character.attributes.add("ki_cooldowns", cooldowns)

    # Check death
    if hasattr(target, "attributes") and target.attributes.get("hp", 0) <= 0:
        try:
            from world.tick_combat import _handle_target_death
            _handle_target_death(character, target)
        except Exception:
            pass

    return True, " ".join(messages)


def use_stunning_strike(character, target) -> Tuple[bool, str]:
    """
    Execute Stunning Strike: single hit with stun chance.

    Returns (success, message).
    """
    ability = KI_ABILITIES["stunning_strike"]

    if not is_monk(character):
        return False, "Only Monks can use ki abilities."

    level = _get_level(character)
    if level < ability["min_level"]:
        return False, f"You must be level {ability['min_level']} to use {ability['name']}."

    if not spend_ki(character, ability["ki_cost"]):
        return False, f"Not enough ki for {ability['name']} (need {ability['ki_cost']})."

    cooldowns = character.attributes.get("ki_cooldowns", {}) if hasattr(character, "attributes") else {}
    remaining = cooldowns.get("stunning_strike", 0) - time.time()
    if remaining > 0:
        return False, f"{ability['name']} is on cooldown for {int(remaining)}s."

    unarmed_dmg = get_unarmed_damage(character)
    dmg = max(1, int(unarmed_dmg * ability["damage_mult"] * random.uniform(0.8, 1.2)))

    if hasattr(target, "attributes"):
        hp = target.attributes.get("hp", 0)
        target.attributes.add("hp", max(0, hp - dmg))

    msg = f"|g{ability['name']} hits for {dmg} damage!|n"

    # Stun check
    if random.random() < ability["stun_chance"]:
        try:
            from world.status_effects import create_stun_effect, apply_status_effect
            stun = create_stun_effect(
                duration=ability["stun_duration"],
                source=character,
                source_level=level,
                source_stat=_get_stats(character).get("dex", 10),
            )
            apply_status_effect(target, stun, caster=character)
            msg += f" |m{target.key} is stunned!|n"
        except Exception:
            pass

    # Build 1 combo point
    add_combo_points(character, 1)

    if hasattr(character, "attributes"):
        cooldowns["stunning_strike"] = time.time() + ability["cooldown"]
        character.attributes.add("ki_cooldowns", cooldowns)

    if hasattr(target, "attributes") and target.attributes.get("hp", 0) <= 0:
        try:
            from world.tick_combat import _handle_target_death
            _handle_target_death(character, target)
        except Exception:
            pass

    return True, msg


def use_chi_heal(character) -> Tuple[bool, str]:
    """
    Execute Chi Heal: heal self for a percentage of max HP.

    Returns (success, message).
    """
    ability = KI_ABILITIES["chi_heal"]

    if not is_monk(character):
        return False, "Only Monks can use ki abilities."

    level = _get_level(character)
    if level < ability["min_level"]:
        return False, f"You must be level {ability['min_level']} to use {ability['name']}."

    if not spend_ki(character, ability["ki_cost"]):
        return False, f"Not enough ki for {ability['name']} (need {ability['ki_cost']})."

    cooldowns = character.attributes.get("ki_cooldowns", {}) if hasattr(character, "attributes") else {}
    remaining = cooldowns.get("chi_heal", 0) - time.time()
    if remaining > 0:
        return False, f"{ability['name']} is on cooldown for {int(remaining)}s."

    max_hp = character.attributes.get("max_hp", 100) if hasattr(character, "attributes") else 100
    heal = int(max_hp * ability["heal_pct"])
    hp = character.attributes.get("hp", 0) if hasattr(character, "attributes") else 0
    new_hp = min(max_hp, hp + heal)
    actual_heal = new_hp - hp

    if hasattr(character, "attributes"):
        character.attributes.add("hp", new_hp)
        cooldowns["chi_heal"] = time.time() + ability["cooldown"]
        character.attributes.add("ki_cooldowns", cooldowns)

    return True, f"|g{ability['name']} restores {actual_heal} HP!|n"


def use_tiger_palm(character, target) -> Tuple[bool, str]:
    """
    Execute Tiger Palm: powerful strike that builds combo points.

    Returns (success, message).
    """
    ability = KI_ABILITIES["tiger_palm"]

    if not is_monk(character):
        return False, "Only Monks can use ki abilities."

    level = _get_level(character)
    if level < ability["min_level"]:
        return False, f"You must be level {ability['min_level']} to use {ability['name']}."

    if not spend_ki(character, ability["ki_cost"]):
        return False, f"Not enough ki for {ability['name']} (need {ability['ki_cost']})."

    cooldowns = character.attributes.get("ki_cooldowns", {}) if hasattr(character, "attributes") else {}
    remaining = cooldowns.get("tiger_palm", 0) - time.time()
    if remaining > 0:
        return False, f"{ability['name']} is on cooldown for {int(remaining)}s."

    unarmed_dmg = get_unarmed_damage(character)
    dmg = max(1, int(unarmed_dmg * ability["damage_mult"] * random.uniform(0.8, 1.2)))

    if hasattr(target, "attributes"):
        hp = target.attributes.get("hp", 0)
        target.attributes.add("hp", max(0, hp - dmg))

    add_combo_points(character, ability["combo_gain"])
    combo = get_combo_points(character)

    if hasattr(character, "attributes"):
        cooldowns["tiger_palm"] = time.time() + ability["cooldown"]
        character.attributes.add("ki_cooldowns", cooldowns)

    if hasattr(target, "attributes") and target.attributes.get("hp", 0) <= 0:
        try:
            from world.tick_combat import _handle_target_death
            _handle_target_death(character, target)
        except Exception:
            pass

    return True, f"|g{ability['name']} hits for {dmg} damage! Combo: {combo}/{MAX_COMBO_POINTS}|n"


def use_dragon_kick(character, target) -> Tuple[bool, str]:
    """
    Execute Dragon Kick: finisher that consumes combo points for bonus damage.

    Returns (success, message).
    """
    ability = KI_ABILITIES["dragon_kick"]

    if not is_monk(character):
        return False, "Only Monks can use ki abilities."

    level = _get_level(character)
    if level < ability["min_level"]:
        return False, f"You must be level {ability['min_level']} to use {ability['name']}."

    combo = get_combo_points(character)
    if combo < ability["combo_required"]:
        return False, f"Need {ability['combo_required']} combo points for {ability['name']} (have {combo})."

    if not spend_ki(character, ability["ki_cost"]):
        return False, f"Not enough ki for {ability['name']} (need {ability['ki_cost']})."

    cooldowns = character.attributes.get("ki_cooldowns", {}) if hasattr(character, "attributes") else {}
    remaining = cooldowns.get("dragon_kick", 0) - time.time()
    if remaining > 0:
        return False, f"{ability['name']} is on cooldown for {int(remaining)}s."

    # Consume combo points for bonus damage
    consumed = consume_combo_points(character, combo)
    bonus_mult = 1.0 + (consumed * ability["combo_dmg_per_point"])

    unarmed_dmg = get_unarmed_damage(character)
    dmg = max(1, int(unarmed_dmg * ability["damage_mult"] * bonus_mult * random.uniform(0.8, 1.2)))

    if hasattr(target, "attributes"):
        hp = target.attributes.get("hp", 0)
        target.attributes.add("hp", max(0, hp - dmg))

    if hasattr(character, "attributes"):
        cooldowns["dragon_kick"] = time.time() + ability["cooldown"]
        character.attributes.add("ki_cooldowns", cooldowns)

    if hasattr(target, "attributes") and target.attributes.get("hp", 0) <= 0:
        try:
            from world.tick_combat import _handle_target_death
            _handle_target_death(character, target)
        except Exception:
            pass

    return True, f"|R{ability['name']} CRITS for {dmg} damage! ({consumed} combo points consumed)|n"


def use_serenity(character) -> Tuple[bool, str]:
    """
    Execute Serenity: full ki restore + massive dodge buff.

    Returns (success, message).
    """
    ability = KI_ABILITIES["serenity"]

    if not is_monk(character):
        return False, "Only Monks can use ki abilities."

    level = _get_level(character)
    if level < ability["min_level"]:
        return False, f"You must be level {ability['min_level']} to use {ability['name']}."

    if not spend_ki(character, ability["ki_cost"]):
        return False, f"Not enough ki for {ability['name']} (need {ability['ki_cost']})."

    cooldowns = character.attributes.get("ki_cooldowns", {}) if hasattr(character, "attributes") else {}
    remaining = cooldowns.get("serenity", 0) - time.time()
    if remaining > 0:
        return False, f"{ability['name']} is on cooldown for {int(remaining)}s."

    # Full ki restore
    max_ki = get_max_ki(character)
    if hasattr(character, "attributes"):
        character.attributes.add("ki", max_ki)
        cooldowns["serenity"] = time.time() + ability["cooldown"]
        character.attributes.add("ki_cooldowns", cooldowns)

        # Dodge buff
        character.attributes.add("serenity_dodge_bonus", ability["dodge_bonus"])
        character.attributes.add("serenity_dodge_expires", time.time() + ability["dodge_duration"])

    return True, f"|c{ability['name']}! Ki fully restored. +{ability['dodge_bonus']}% dodge for {ability['dodge_duration']}s.|n"


def get_serenity_dodge_bonus(character) -> float:
    """Return the current Serenity dodge bonus, or 0 if expired."""
    if not hasattr(character, "attributes"):
        return 0.0
    expires = character.attributes.get("serenity_dodge_expires", 0)
    if time.time() > expires:
        return 0.0
    return character.attributes.get("serenity_dodge_bonus", 0)


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