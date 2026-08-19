"""
Damage Formulas for 'rop' — MajorMUD-Style Combat Math

Provides:
  - DamageType enum (SLASH, PIERCE, BLUNT, MAGIC_FIRE, etc.)
  - ARMOR_MITIGATION per damage type
  - calculate_melee_damage() with STR/DEX/CON scaling, crits, armor
  - calculate_magic_damage() with INT/WIS scaling, magic resistance
  - _get_armor_value() — sum equipped armor + natural racial armor
  - _get_magic_resist() — sum gear magic resist
"""

import random
from enum import Enum
from typing import Dict, Optional


class DamageType(Enum):
    SLASH = "slash"
    PIERCE = "pierce"
    BLUNT = "blunt"
    MAGIC_FIRE = "magic_fire"
    MAGIC_COLD = "magic_cold"
    MAGIC_LIGHTNING = "magic_lightning"
    MAGIC_SHADOW = "magic_shadow"
    MAGIC_HOLY = "magic_holy"
    POISON = "poison"
    BLEED = "bleed"


# Armor mitigation per damage type (percentage reduction)
ARMOR_MITIGATION: Dict[DamageType, float] = {
    DamageType.SLASH:   0.15,   # Chain/plate good vs slashing
    DamageType.PIERCE:  0.10,   # Harder to mitigate piercing
    DamageType.BLUNT:   0.05,   # Blunt crushes through armor
    DamageType.MAGIC_FIRE: 0.0, # Armor doesn't help vs magic
    DamageType.MAGIC_COLD: 0.0,
    DamageType.MAGIC_LIGHTNING: 0.0,
    DamageType.MAGIC_SHADOW: 0.0,
    DamageType.MAGIC_HOLY: 0.0,
    DamageType.POISON:  0.0,
    DamageType.BLEED:   0.0,
}


def calculate_melee_damage(attacker, defender, weapon_damage: int, damage_type: DamageType) -> dict:
    """
    Full melee damage calculation incorporating:
    - Base weapon damage
    - STR bonus (+1 per 2 STR above 10)
    - Critical hit chance (based on DEX, +1% per DEX above 10, min 2%)
    - Armor mitigation (based on defender's equipped armor + CON)
    - Damage type modifiers
    - Random variance (+-20%)

    Returns: {"damage": int, "crit": bool, "absorbed": int, "type": DamageType}
    """
    stats_att = _get_stats(attacker)
    stats_def = _get_stats(defender)

    str_val = stats_att.get("str", 10)
    dex_val = stats_att.get("dex", 10)
    con_val = stats_def.get("con", 10)

    # Base damage
    str_bonus = max(0, (str_val - 10) // 2)
    base = weapon_damage + str_bonus

    # Talent bonuses (Phase 14 Sprint 1)
    try:
        from world.skill_tree import get_talent_bonuses
        talent_bonuses = get_talent_bonuses(attacker)
        base += talent_bonuses.get("melee_damage", 0)
    except Exception:
        pass

    # Racial passive: melee damage bonus (Orc +10%)
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(attacker)
        melee_dmg_pct = racial.get("melee_dmg_pct", 0)
        if melee_dmg_pct:
            base = int(base * (1.0 + melee_dmg_pct / 100.0))
    except Exception:
        pass

    # Phase 2.2: Druid shapeshift form melee damage bonus
    try:
        from world.druid_system import get_form_bonuses
        form = get_form_bonuses(attacker)
        if form:
            form_dmg_pct = form.get("melee_dmg_pct", 0)
            if form_dmg_pct:
                base = int(base * (1.0 + form_dmg_pct / 100.0))
    except Exception:
        pass

    # Critical hit check (DEX-based)
    crit_chance = max(0.02, (dex_val - 10) * 0.01)  # 1% per DEX above 10, min 2%
    # Talent crit bonus
    try:
        from world.skill_tree import get_talent_bonuses
        talent_bonuses = get_talent_bonuses(attacker)
        crit_chance += talent_bonuses.get("crit_chance_pct", 0) * 0.01
    except Exception:
        pass
    # Racial passive: crit chance (Halfling +5%)
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(attacker)
        crit_chance += racial.get("crit_chance_pct", 0) * 0.01
    except Exception:
        pass
    # Phase 2.2: Druid shapeshift form crit chance bonus
    try:
        from world.druid_system import get_form_bonuses
        form = get_form_bonuses(attacker)
        if form:
            crit_chance += form.get("crit_chance_pct", 0) * 0.01
    except Exception:
        pass
    is_crit = random.random() < crit_chance
    if is_crit:
        base = int(base * 1.5)  # 50% bonus on crit

    # Armor mitigation — only applies when the defender actually has armor.
    armor_value = _get_armor_value(defender)
    if armor_value > 0:
        armor_mitigation_pct = ARMOR_MITIGATION.get(damage_type, 0.10)
        con_bonus = max(0, (con_val - 10) // 3)  # CON adds flat reduction
        absorbed = int(base * armor_mitigation_pct) + con_bonus
        absorbed = min(absorbed, base - 1)  # Always do at least 1 damage
    else:
        absorbed = 0

    # Variance
    variance = random.uniform(0.80, 1.20)
    final_damage = max(1, int((base - absorbed) * variance))

    return {
        "damage": final_damage,
        "crit": is_crit,
        "absorbed": absorbed,
        "type": damage_type,
    }


def calculate_magic_damage(caster, target, spell_base: int, spell_per_level: int,
                           damage_type: DamageType) -> dict:
    """Magic damage: scales with INT/WIS, reduced by magic resistance."""
    stats_caster = _get_stats(caster)
    stats_target = _get_stats(target)

    casting_stat = max(stats_caster.get("int", 10), stats_caster.get("wis", 10))
    caster_level = _get_level(caster)

    base = spell_base + (spell_per_level * caster_level) + int(casting_stat * 0.6)

    # Magic resistance (based on target WIS + any resist gear)
    wis_resist = max(0, (stats_target.get("wis", 10) - 10) * 0.02)  # 2% per WIS above 10
    gear_resist = _get_magic_resist(target)  # From equipment

    # Racial passive: magic resistance (Gnome +10%) and elemental resistances
    # (Demonkin +15% fire/dark).  Initialize racial to {} so the elemental
    # checks are safe even if get_racial_bonuses() raises.
    racial = {}
    racial_resist = 0.0
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(target)
        racial_resist += racial.get("magic_resist_pct", 0) * 0.01
    except Exception:
        pass

    # Racial passive: fire/dark resistance (Demonkin +15% each)
    if damage_type == DamageType.MAGIC_FIRE:
        racial_resist += racial.get("fire_resist_pct", 0) * 0.01
    elif damage_type == DamageType.MAGIC_SHADOW:
        racial_resist += racial.get("dark_resist_pct", 0) * 0.01

    total_resist = min(0.75, wis_resist + gear_resist + racial_resist)  # Cap at 75%

    final = max(1, int(base * (1.0 - total_resist)))
    return {"damage": final, "type": damage_type, "resisted_pct": total_resist}


def _get_armor_value(character) -> int:
    """
    Sum armor values from all equipped gear + natural racial armor.

    Fixed: Returns 0 when nothing is equipped — no phantom absorption.
    Uses world.mob_equipment.get_effective_armor for canonical calculation.
    """
    try:
        from world.mob_equipment import get_effective_armor
        return get_effective_armor(character)
    except Exception:
        # Fallback inline calculation
        equipped = _get_equipped(character)
        total = 0
        if equipped and hasattr(equipped, "items"):
            for slot, item_name in equipped.items():
                for obj in character.contents:
                    if not getattr(obj, "destination", None) and obj.key == item_name:
                        total += obj.attributes.get("armor", default=0)

        from world.race_class_matrix import RACE_NATURAL_ARMOR
        race = _get_race(character)
        total += RACE_NATURAL_ARMOR.get(race, 0)
        return total


def _get_magic_resist(character) -> float:
    """Sum magic resistance from gear and racial bonuses."""
    equipped = _get_equipped(character)
    total = 0.0
    for slot, item_name in equipped.items():
        for obj in character.contents:
            if not getattr(obj, "destination", None) and obj.key == item_name:
                total += obj.attributes.get("magic_resist", default=0.0)
    return total


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_stats(obj) -> Dict[str, int]:
    """Safely fetch stats dict from a character or mob.

    Uses effective stats (base stats + equipment ``stat_bonuses``) when
    the equipment helpers are available, falling back to raw stats.
    """
    if hasattr(obj, "attributes"):
        try:
            from world.mob_equipment import get_effective_stats
            return get_effective_stats(obj)
        except Exception:
            pass
        stats = obj.attributes.get("stats", default={})
        if stats is not None and hasattr(stats, "items"):
            return {str(k): int(v) for k, v in stats.items()}
    return {}


def _get_level(obj) -> int:
    """Safely fetch the level of a character or mob."""
    if hasattr(obj, "attributes"):
        return obj.attributes.get("level", default=1)
    return 1


def _get_race(obj) -> str:
    """Safely fetch the race of a character."""
    if hasattr(obj, "attributes"):
        return obj.attributes.get("race", default="Human")
    return "Human"


def _get_equipped(obj) -> Dict[str, str]:
    """Safely fetch equipped items dict."""
    if hasattr(obj, "attributes"):
        eq = obj.attributes.get("equipped", default={})
        if eq is not None and hasattr(eq, "items"):
            return {str(k): str(v) for k, v in eq.items()}
    return {}


# ---------------------------------------------------------------------------
# Spell damage (simplified API for audit compat)
# ---------------------------------------------------------------------------

def calculate_spell_damage(caster, target, spell_base: int, element: str) -> dict:
    """
    Simplified spell damage calculation for audit/test compatibility.

    Args:
        caster: Character casting the spell.
        target: Target character/mob.
        spell_base: Base damage of the spell.
        element: Element string (e.g. "fire", "cold", "lightning").

    Returns: dict with "damage", "type", "resisted_pct" keys.
    """
    # Map element string to DamageType
    element_map = {
        "fire": DamageType.MAGIC_FIRE,
        "cold": DamageType.MAGIC_COLD,
        "lightning": DamageType.MAGIC_LIGHTNING,
        "shadow": DamageType.MAGIC_SHADOW,
        "holy": DamageType.MAGIC_HOLY,
        "poison": DamageType.POISON,
        "bleed": DamageType.BLEED,
    }
    dt = element_map.get(element.lower(), DamageType.MAGIC_FIRE)
    return calculate_magic_damage(caster, target, spell_base, 0, dt)


# ---------------------------------------------------------------------------
# Damage type modifier helper
# ---------------------------------------------------------------------------

def get_damage_type_modifier(damage_type: DamageType, target) -> float:
    """
    Return a damage modifier based on the target's vulnerabilities/resistances
    to a specific damage type.

    Returns a float multiplier (e.g. 1.0 for normal, 1.25 for weak, 0.75 for resistant).
    """
    if not hasattr(target, "attributes"):
        return 1.0

    # Check for explicit resistances/vulnerabilities on the target
    resistances = target.attributes.get("resistances", default={})
    if resistances is not None and hasattr(resistances, "items"):
        if damage_type.value in resistances:
            return 1.0 - resistances[damage_type.value]

    vulnerabilities = target.attributes.get("vulnerabilities", default={})
    if vulnerabilities is not None and hasattr(vulnerabilities, "items"):
        if damage_type.value in vulnerabilities:
            return 1.0 + vulnerabilities[damage_type.value]

    return 1.0


# ---------------------------------------------------------------------------
# Armor absorption helper
# ---------------------------------------------------------------------------

def calculate_armor_absorption(target, base_damage: int, damage_type: DamageType) -> int:
    """
    Calculate how much of base_damage is absorbed by the target's armor.

    Fixed: Returns 0 absorption when the target has no armor equipped,
    preventing phantom "[Armor absorbs 0]" messages.

    Returns the amount absorbed (int).
    """
    if not hasattr(target, "attributes"):
        return 0

    armor_value = _get_armor_value(target)

    # FIX: If no armor is equipped, absorption is always 0.
    if armor_value <= 0:
        return 0

    stats = _get_stats(target)
    con_val = stats.get("con", 10)

    armor_mitigation_pct = ARMOR_MITIGATION.get(damage_type, 0.10)
    con_bonus = max(0, (con_val - 10) // 3)
    absorbed = int(base_damage * armor_mitigation_pct) + con_bonus

    # Apply armor value as a cap on absorption.
    absorbed = min(absorbed, armor_value)

    return min(absorbed, base_damage - 1)
