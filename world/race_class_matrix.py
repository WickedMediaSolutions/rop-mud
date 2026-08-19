"""
Race/Class Gating Engine for 'rop' — EmlenMUD-Style Permission Matrix

Provides:
  - RaceDef / ClassDef dataclasses
  - RACE_CLASS_MATRIX — 16 races × 10 classes whitelist
  - CLASS_SPELL_SCHOOLS — which schools each class can access
  - CLASS_MAX_SPELL_LEVEL — per-class per-school level caps
  - can_cast_spells(character) -> bool
  - can_learn_spell(character, spell_key) -> (bool, str)
  - can_use_skill(character, skill_key) -> (bool, str)
  - can_equip_slot(character, slot, item_type) -> (bool, str)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RaceDef:
    key: str
    alignment: str
    stats: Dict[str, int]
    allowed_classes: List[str]
    passive: str
    passive_effect: Dict[str, any] = field(default_factory=dict)
    start_room_key: str = ""
    desc: str = ""
    forbidden_slots: List[str] = field(default_factory=list)
    max_spell_level_by_school: Dict[str, int] = field(default_factory=dict)
    natural_armor: int = 0


@dataclass
class ClassDef:
    key: str
    primary_stat: str
    hp_per_level: int
    mana_per_level: int
    desc: str
    allowed_schools: List[str] = field(default_factory=list)
    max_spell_level: Dict[str, int] = field(default_factory=dict)
    class_skills: List[str] = field(default_factory=list)
    allowed_weapon_types: List[str] = field(default_factory=list)
    allowed_armor_types: List[str] = field(default_factory=list)
    practice_costs: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# RACE/CLASS COMPATIBILITY MATRIX (EmlenMUD-Style)
# ---------------------------------------------------------------------------

RACE_CLASS_MATRIX: Dict[str, List[str]] = {
    # GOOD RACES
    "Human":        ["Warrior", "Paladin", "Cleric", "Mage", "Rogue", "Warlock", "Druid", "Ranger", "Monk", "Necromancer"],
    "High Elf":     ["Paladin", "Cleric", "Mage", "Druid", "Ranger", "Monk"],
    "Wood Elf":     ["Cleric", "Mage", "Rogue", "Druid", "Ranger", "Monk"],
    "Mountain Dwarf": ["Warrior", "Paladin", "Cleric", "Rogue"],
    "Stout Halfling": ["Warrior", "Rogue", "Ranger", "Monk"],
    "Gnome":        ["Cleric", "Mage", "Rogue", "Warlock", "Druid"],
    "Centaur":      ["Warrior", "Paladin", "Druid", "Ranger"],
    "Pixie":        ["Mage", "Rogue", "Druid", "Monk"],
    # EVIL RACES
    "Orc":          ["Warrior", "Rogue", "Warlock", "Necromancer"],
    "Dark Elf":     ["Warrior", "Mage", "Rogue", "Warlock", "Necromancer"],
    "Undead":       ["Warrior", "Warlock", "Necromancer"],
    "Goblin":       ["Warrior", "Rogue", "Warlock"],
    "Minotaur":     ["Warrior", "Warlock"],
    "Lizardfolk":   ["Warrior", "Rogue", "Druid"],
    "Ogre":         ["Warrior"],
    "Demonkin":     ["Warrior", "Mage", "Warlock", "Necromancer"],
}

# Class → allowed spell schools (empty list = pure martial, no spells)
CLASS_SPELL_SCHOOLS: Dict[str, List[str]] = {
    "Warrior":      [],
    "Paladin":      ["restoration", "abjuration"],
    "Cleric":       ["restoration", "abjuration", "evocation"],
    "Mage":         ["evocation", "abjuration", "enfeebling"],
    "Rogue":        [],
    "Warlock":      ["evocation", "enfeebling"],
    "Druid":        ["restoration", "evocation", "enfeebling"],
    "Ranger":       ["restoration"],
    "Monk":         [],
    "Necromancer":  ["evocation", "enfeebling", "restoration"],
}

# Class → max spell level per school (overrides global max)
CLASS_MAX_SPELL_LEVEL: Dict[str, Dict[str, int]] = {
    "Paladin":      {"restoration": 40, "abjuration": 40},
    "Ranger":       {"restoration": 20},
}

# Race-level spell restrictions (e.g., Orc can't learn any spells)
RACE_MAX_SPELL_LEVEL: Dict[str, Dict[str, int]] = {
    "Orc":          {"evocation": 0, "restoration": 0, "abjuration": 0, "enfeebling": 0},
    "Ogre":         {"evocation": 0, "restoration": 0, "abjuration": 0, "enfeebling": 0},
    "Minotaur":     {"evocation": 0, "restoration": 0, "abjuration": 0, "enfeebling": 0},
}

# Class skills per class
CLASS_SKILLS: Dict[str, List[str]] = {
    "Warrior":      ["kick", "bash", "disarm"],
    "Paladin":      ["bash"],
    "Cleric":       [],
    "Mage":         [],
    "Rogue":        ["kick", "backstab", "disarm"],
    "Warlock":      [],
    "Druid":        [],
    "Ranger":       ["kick"],
    "Monk":         ["kick"],
    "Necromancer":  [],
}

# Equipment proficiencies
CLASS_WEAPON_TYPES: Dict[str, List[str]] = {
    "Warrior":      ["sword", "axe", "mace", "dagger", "spear", "two_handed"],
    "Paladin":      ["sword", "mace", "two_handed"],
    "Cleric":       ["mace", "staff"],
    "Mage":         ["dagger", "staff", "wand"],
    "Rogue":        ["dagger", "sword", "bow", "crossbow"],
    "Warlock":      ["dagger", "staff", "wand"],
    "Druid":        ["staff", "spear", "club"],
    "Ranger":       ["sword", "bow", "crossbow", "spear", "dagger"],
    "Monk":         ["fist", "staff"],
    "Necromancer":  ["dagger", "staff", "wand"],
}

CLASS_ARMOR_TYPES: Dict[str, List[str]] = {
    "Warrior":      ["light", "medium", "heavy", "shield"],
    "Paladin":      ["light", "medium", "heavy", "shield"],
    "Cleric":       ["cloth", "light", "medium", "shield"],
    "Mage":         ["cloth"],
    "Rogue":        ["cloth", "light"],
    "Warlock":      ["cloth", "light"],
    "Druid":        ["cloth", "light", "medium"],
    "Ranger":       ["cloth", "light", "medium"],
    "Monk":         ["cloth"],
    "Necromancer":  ["cloth"],
}

# Race equipment slot restrictions
RACE_FORBIDDEN_SLOTS: Dict[str, List[str]] = {
    "Pixie": ["chest_heavy", "two_handed", "shoulders"],
    "Centaur": ["feet", "legs"],
}

# Natural armor per race
RACE_NATURAL_ARMOR: Dict[str, int] = {
    "Lizardfolk": 4,
    "Mountain Dwarf": 5,
    "Minotaur": 3,
    "Ogre": 6,
    "Undead": 2,
}


# ---------------------------------------------------------------------------
# GATING ENGINE — Central Permission Checks
# ---------------------------------------------------------------------------

def can_cast_spells(character) -> bool:
    """Master gate: does this character's class allow ANY spellcasting?"""
    char_class = _get_char_class(character)
    schools = CLASS_SPELL_SCHOOLS.get(char_class, [])
    return len(schools) > 0


def can_learn_spell(character, spell_key: str) -> Tuple[bool, str]:
    """
    Check if a character's race/class combination permits learning a spell.
    Returns (allowed, reason).
    Called by: SpellHandler.can_cast(), _grant_spells_for_level(), guildmaster training.
    """
    from world.spells import get_spell

    char_class = _get_char_class(character)
    char_race = _get_char_race(character)
    char_level = _get_char_level(character)

    spell = get_spell(spell_key)
    if not spell:
        return False, "Unknown spell."

    # 1. Class must allow this spell's school
    allowed_schools = CLASS_SPELL_SCHOOLS.get(char_class, [])
    if spell["school"] not in allowed_schools:
        return False, f"{char_class}s cannot cast {spell['school']} spells."

    # 2. Class must allow spells up to this spell's level
    max_lvl_map = CLASS_MAX_SPELL_LEVEL.get(char_class, {})
    max_for_school = max_lvl_map.get(spell["school"], 80)
    if spell["level"] > max_for_school:
        return False, f"{char_class}s can only learn {spell['school']} spells up to level {max_for_school}."

    # 3. Race-level restrictions (e.g., Orc can't learn any spells)
    race_max_map = RACE_MAX_SPELL_LEVEL.get(char_race, {})
    race_max = race_max_map.get(spell["school"], 80)
    if spell["level"] > race_max:
        return False, f"{char_race}s cannot learn {spell['school']} spells above level {race_max}."

    # 4. Character level check
    if spell["level"] > char_level:
        return False, f"You must be level {spell['level']} to learn {spell['name']}."

    return True, ""


def can_use_skill(character, skill_key: str) -> Tuple[bool, str]:
    """Check if a character's class permits using a physical combat skill."""
    char_class = _get_char_class(character)
    class_skills = CLASS_SKILLS.get(char_class, [])
    if skill_key not in class_skills:
        return False, f"{char_class}s cannot use {skill_key}."
    return True, ""


def can_equip_slot(character, slot: str, item_type: str) -> Tuple[bool, str]:
    """Check race/class equipment restrictions."""
    char_race = _get_char_race(character)
    char_class = _get_char_class(character)

    # Race restrictions (e.g., Pixie can't wear heavy armor)
    forbidden = RACE_FORBIDDEN_SLOTS.get(char_race, [])
    if slot in forbidden:
        return False, f"{char_race}s cannot equip items in the {slot} slot."

    # Class armor proficiency
    if item_type.startswith("armor_"):
        armor_type = item_type.replace("armor_", "")
        allowed_armor = CLASS_ARMOR_TYPES.get(char_class, [])
        if armor_type not in allowed_armor:
            return False, f"{char_class}s cannot wear {armor_type} armor."

    # Class weapon proficiency
    if item_type.startswith("weapon_"):
        weapon_type = item_type.replace("weapon_", "")
        allowed_weapons = CLASS_WEAPON_TYPES.get(char_class, [])
        if weapon_type not in allowed_weapons:
            return False, f"{char_class}s cannot wield {weapon_type} weapons."

    return True, ""


def is_race_class_valid(race: str, cls: str) -> bool:
    """Check if a race/class combination is allowed."""
    allowed = RACE_CLASS_MATRIX.get(race, [])
    return cls in allowed


def get_valid_classes_for_race(race: str) -> List[str]:
    """Return the list of class names valid for a given race."""
    return RACE_CLASS_MATRIX.get(race, [])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_char_class(character) -> str:
    """Safely fetch the character's class."""
    if hasattr(character, "attributes"):
        return character.attributes.get("class", default="Warrior")
    return "Warrior"


def _get_char_race(character) -> str:
    """Safely fetch the character's race."""
    if hasattr(character, "attributes"):
        return character.attributes.get("race", default="Human")
    return "Human"


def _get_char_level(character) -> int:
    """Safely fetch the character's level."""
    if hasattr(character, "attributes"):
        return character.attributes.get("level", default=1)
    return 1