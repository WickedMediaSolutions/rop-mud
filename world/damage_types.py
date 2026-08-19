"""
Damage Types System for 'rop'

Provides:
  - Standard physical damage types
  - Material-based damage types (silver, cold iron, adamantine)
  - Alignment-based damage types (good, evil, law, chaos)
  - Energy/elemental damage types (fire, cold, lightning, acid, poison, holy, shadow, arcane)
  - Damage type resistance/immunity/vulnerability registry
  - Helper functions to apply damage with type-based modifiers
"""

from enum import Enum
from typing import Dict, Optional, Set


# ---------------------------------------------------------------------------
# Damage Type Enumerations
# ---------------------------------------------------------------------------

class PhysicalDamageType(Enum):
    """Standard physical damage types."""
    SLASHING = "slashing"
    PIERCING = "piercing"
    BLUDGEONING = "bludgeoning"


class MaterialDamageType(Enum):
    """Material-based damage types for bypassing certain resistances."""
    SILVER = "silver"
    COLD_IRON = "cold_iron"
    ADAMANTINE = "adamantine"
    MITHRIL = "mithril"


class AlignmentDamageType(Enum):
    """Alignment-based damage types."""
    GOOD = "good"
    EVIL = "evil"
    LAW = "law"
    CHAOS = "chaos"


class EnergyDamageType(Enum):
    """Energy and elemental damage types."""
    FIRE = "fire"
    COLD = "cold"
    LIGHTNING = "lightning"
    ACID = "acid"
    POISON = "poison"
    HOLY = "holy"
    SHADOW = "shadow"
    ARCANE = "arcane"
    SONIC = "sonic"
    PSYCHIC = "psychic"


# ---------------------------------------------------------------------------
# Damage Type Display Names
# ---------------------------------------------------------------------------

DAMAGE_TYPE_DISPLAY = {
    # Physical
    "slashing": "|wSlashing|n",
    "piercing": "|wPiercing|n",
    "bludgeoning": "|wBludgeoning|n",
    # Material
    "silver": "|WSilver|n",
    "cold_iron": "|wCold Iron|n",
    "adamantine": "|wAdamantine|n",
    "mithril": "|wMithril|n",
    # Alignment
    "good": "|YGood|n",
    "evil": "|rEvil|n",
    "law": "|bLaw|n",
    "chaos": "|mChaos|n",
    # Energy
    "fire": "|RFire|n",
    "cold": "|bCold|n",
    "lightning": "|YLightning|n",
    "acid": "|gAcid|n",
    "poison": "|mPoison|n",
    "holy": "|YHoly|n",
    "shadow": "|MShadow|n",
    "arcane": "|cArcane|n",
    "sonic": "|bSonic|n",
    "psychic": "|mPsychic|n",
}


# ---------------------------------------------------------------------------
# Resistance Multipliers
# ---------------------------------------------------------------------------

RESISTANCE_MULTIPLIERS = {
    "immune": 0.0,       # No damage
    "resistant": 0.5,    # Half damage
    "normal": 1.0,       # Full damage
    "vulnerable": 1.5,   # 50% extra damage
    "weak": 2.0,         # Double damage
}


# ---------------------------------------------------------------------------
# Damaged-By Registry (for mobs / bosses)
# ---------------------------------------------------------------------------

def get_damage_multiplier(target, damage_type: str) -> float:
    """
    Determine the damage multiplier for a target against a specific damage type.

    Checks the target's `damage_resistances` attribute, a dict of damage_type -> resistance_level.
    Falls back to a `damage_immunities` set attribute for full immunity.

    Returns a float multiplier (0.0 for immune, 1.5 for vulnerable, etc.).
    """
    if not hasattr(target, "attributes"):
        return 1.0

    # Check immunities first (set of damage types)
    immunities = target.attributes.get("damage_immunities", default=None)
    if immunities and damage_type in immunities:
        return 0.0

    # Check detailed resistances (dict of damage_type -> resistance_level)
    resistances = target.attributes.get("damage_resistances", default=None)
    if resistances and damage_type in resistances:
        level = resistances[damage_type]
        return RESISTANCE_MULTIPLIERS.get(level, 1.0)

    return 1.0


def apply_damage_with_type(raw_damage: int, damage_type: str, target) -> int:
    """
    Apply a damage multiplier based on the target's resistance/immunity/vulnerability
    to the given damage type.

    Returns the adjusted damage amount (as an integer).
    """
    multiplier = get_damage_multiplier(target, damage_type)
    return max(0, int(raw_damage * multiplier))


def get_resistance_display(target) -> str:
    """
    Return a human-readable string of the target's resistances.
    """
    if not hasattr(target, "attributes"):
        return ""

    immunities = target.attributes.get("damage_immunities", default=None)
    resistances = target.attributes.get("damage_resistances", default=None)

    parts = []
    if immunities:
        for dt in sorted(immunities):
            display = DAMAGE_TYPE_DISPLAY.get(dt, dt)
            parts.append(f"Immune: {display}")

    if resistances:
        for dt, level in sorted(resistances.items()):
            display = DAMAGE_TYPE_DISPLAY.get(dt, dt)
            if level == "resistant":
                parts.append(f"Resists: {display}")
            elif level == "vulnerable":
                parts.append(f"Vulnerable: {display}")
            elif level == "weak":
                parts.append(f"Weak: {display}")

    return ", ".join(parts) if parts else ""


def set_damage_resistance(target, damage_type: str, level: str):
    """Set a resistance level for a target to a specific damage type."""
    if not hasattr(target, "attributes"):
        return
    resistances = target.attributes.get("damage_resistances", default={})
    if resistances is None or not hasattr(resistances, "items"):
        resistances = {}
    else:
        resistances = {str(k): v for k, v in resistances.items()}
    resistances[damage_type] = level
    target.attributes.add("damage_resistances", resistances)


def add_damage_immunity(target, damage_type: str):
    """Add a damage type immunity to a target."""
    if not hasattr(target, "attributes"):
        return
    immunities = target.attributes.get("damage_immunities", default=None)
    if not immunities:
        immunities = set()
    elif isinstance(immunities, list):
        immunities = set(immunities)
    immunities.add(damage_type)
    target.attributes.add("damage_immunities", immunities)


# ---------------------------------------------------------------------------
# Damage Type Lookup
# ---------------------------------------------------------------------------

def classify_damage_type(type_name: str) -> str:
    """
    Normalize a damage type string to its canonical form.
    Returns the type name if recognized, otherwise 'arcane' as default.
    """
    type_name = type_name.lower().strip().replace(" ", "_")

    all_types = set()
    for enum_cls in (PhysicalDamageType, MaterialDamageType, AlignmentDamageType, EnergyDamageType):
        for member in enum_cls:
            all_types.add(member.value)

    if type_name in all_types:
        return type_name

    # Handle common aliases
    aliases = {
        "slash": "slashing",
        "pierce": "piercing",
        "blunt": "bludgeoning",
        "electric": "lightning",
        "ice": "cold",
        "frost": "cold",
        "dark": "shadow",
        "magic": "arcane",
        "mental": "psychic",
        "sound": "sonic",
    }
    return aliases.get(type_name, "arcane")