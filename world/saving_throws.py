"""
Saving Throws System for 'rop'

Provides:
  - Five saving throw categories: Poison, Death, Petrification, Rod, Spell
  - Racial base saving throw modifiers
  - Class-based saving throw progression
  - Saving throw roll resolver with stat bonuses
  - Difficulty class (DC) calculation
  - Integration with status effects and spell casting
"""

import random
from enum import Enum
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Saving Throw Categories
# ---------------------------------------------------------------------------

class SavingThrow(Enum):
    """The five classic saving throw categories."""
    POISON = "poison"               # Poison, disease, toxins
    DEATH = "death"                 # Death magic, life-drain, instant-kill
    PETRIFICATION = "petrification" # Paralysis, petrification, polymorph
    ROD = "rod"                     # Wands, staves, rods
    SPELL = "spell"                 # Spells, spell-like abilities


SAVING_THROW_DISPLAY = {
    SavingThrow.POISON: "|gPoison|n",
    SavingThrow.DEATH: "|rDeath|n",
    SavingThrow.PETRIFICATION: "|mPetrification|n",
    SavingThrow.ROD: "|yRod|n",
    SavingThrow.SPELL: "|cSpell|n",
}


# ---------------------------------------------------------------------------
# Base Saving Throw Table (by level)
# ---------------------------------------------------------------------------
# Each entry is a dict mapping SavingThrow -> base save value (lower is better).
# These are the target numbers the character must roll >= to succeed on a d20.
# L1-10 values are the floor; higher levels get progressive improvements.

BASE_SAVES_BY_LEVEL = {
    # level: {poison, death, petrification, rod, spell}
    1:  {SavingThrow.POISON: 14, SavingThrow.DEATH: 13, SavingThrow.PETRIFICATION: 16, SavingThrow.ROD: 15, SavingThrow.SPELL: 17},
    2:  {SavingThrow.POISON: 14, SavingThrow.DEATH: 13, SavingThrow.PETRIFICATION: 16, SavingThrow.ROD: 15, SavingThrow.SPELL: 17},
    3:  {SavingThrow.POISON: 13, SavingThrow.DEATH: 12, SavingThrow.PETRIFICATION: 15, SavingThrow.ROD: 14, SavingThrow.SPELL: 16},
    4:  {SavingThrow.POISON: 13, SavingThrow.DEATH: 12, SavingThrow.PETRIFICATION: 15, SavingThrow.ROD: 14, SavingThrow.SPELL: 16},
    5:  {SavingThrow.POISON: 12, SavingThrow.DEATH: 11, SavingThrow.PETRIFICATION: 14, SavingThrow.ROD: 13, SavingThrow.SPELL: 15},
    6:  {SavingThrow.POISON: 12, SavingThrow.DEATH: 11, SavingThrow.PETRIFICATION: 14, SavingThrow.ROD: 13, SavingThrow.SPELL: 15},
    7:  {SavingThrow.POISON: 11, SavingThrow.DEATH: 10, SavingThrow.PETRIFICATION: 13, SavingThrow.ROD: 12, SavingThrow.SPELL: 14},
    8:  {SavingThrow.POISON: 11, SavingThrow.DEATH: 10, SavingThrow.PETRIFICATION: 13, SavingThrow.ROD: 12, SavingThrow.SPELL: 14},
    9:  {SavingThrow.POISON: 10, SavingThrow.DEATH: 9,  SavingThrow.PETRIFICATION: 12, SavingThrow.ROD: 11, SavingThrow.SPELL: 13},
    10: {SavingThrow.POISON: 10, SavingThrow.DEATH: 9,  SavingThrow.PETRIFICATION: 12, SavingThrow.ROD: 11, SavingThrow.SPELL: 13},
    11: {SavingThrow.POISON: 9,  SavingThrow.DEATH: 8,  SavingThrow.PETRIFICATION: 11, SavingThrow.ROD: 10, SavingThrow.SPELL: 12},
    12: {SavingThrow.POISON: 9,  SavingThrow.DEATH: 8,  SavingThrow.PETRIFICATION: 11, SavingThrow.ROD: 10, SavingThrow.SPELL: 12},
    13: {SavingThrow.POISON: 8,  SavingThrow.DEATH: 7,  SavingThrow.PETRIFICATION: 10, SavingThrow.ROD: 9,  SavingThrow.SPELL: 11},
    14: {SavingThrow.POISON: 8,  SavingThrow.DEATH: 7,  SavingThrow.PETRIFICATION: 10, SavingThrow.ROD: 9,  SavingThrow.SPELL: 11},
    15: {SavingThrow.POISON: 7,  SavingThrow.DEATH: 6,  SavingThrow.PETRIFICATION: 9,  SavingThrow.ROD: 8,  SavingThrow.SPELL: 10},
    16: {SavingThrow.POISON: 7,  SavingThrow.DEATH: 6,  SavingThrow.PETRIFICATION: 9,  SavingThrow.ROD: 8,  SavingThrow.SPELL: 10},
    17: {SavingThrow.POISON: 6,  SavingThrow.DEATH: 5,  SavingThrow.PETRIFICATION: 8,  SavingThrow.ROD: 7,  SavingThrow.SPELL: 9},
    18: {SavingThrow.POISON: 6,  SavingThrow.DEATH: 5,  SavingThrow.PETRIFICATION: 8,  SavingThrow.ROD: 7,  SavingThrow.SPELL: 9},
    19: {SavingThrow.POISON: 5,  SavingThrow.DEATH: 4,  SavingThrow.PETRIFICATION: 7,  SavingThrow.ROD: 6,  SavingThrow.SPELL: 8},
    20: {SavingThrow.POISON: 5,  SavingThrow.DEATH: 4,  SavingThrow.PETRIFICATION: 7,  SavingThrow.ROD: 6,  SavingThrow.SPELL: 8},
}


# ---------------------------------------------------------------------------
# Racial Saving Throw Bonuses
# ---------------------------------------------------------------------------
# Positive values are bonuses (improve save), negative are penalties.

RACIAL_SAVE_BONUSES = {
    # Good Races
    "Human":          {SavingThrow.POISON: 0, SavingThrow.DEATH: 0, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 0, SavingThrow.SPELL: 0},
    "High Elf":       {SavingThrow.POISON: 0, SavingThrow.DEATH: 0, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 1, SavingThrow.SPELL: 2},
    "Wood Elf":       {SavingThrow.POISON: 0, SavingThrow.DEATH: 0, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 0, SavingThrow.SPELL: 1},
    "Mountain Dwarf": {SavingThrow.POISON: 2, SavingThrow.DEATH: 1, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 1, SavingThrow.SPELL: -1},
    "Stout Halfling": {SavingThrow.POISON: 2, SavingThrow.DEATH: 0, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 1, SavingThrow.SPELL: 1},
    "Gnome":          {SavingThrow.POISON: 0, SavingThrow.DEATH: 0, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 2, SavingThrow.SPELL: 1},
    "Centaur":        {SavingThrow.POISON: 1, SavingThrow.DEATH: 0, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 0, SavingThrow.SPELL: -1},
    "Pixie":          {SavingThrow.POISON: -1, SavingThrow.DEATH: -1, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 2, SavingThrow.SPELL: 2},
    # Evil Races
    "Orc":            {SavingThrow.POISON: 1, SavingThrow.DEATH: 1, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 0, SavingThrow.SPELL: -2},
    "Dark Elf":       {SavingThrow.POISON: 0, SavingThrow.DEATH: 0, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 0, SavingThrow.SPELL: 2},
    "Undead":         {SavingThrow.POISON: 2, SavingThrow.DEATH: 2, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: -1, SavingThrow.SPELL: -1},
    "Goblin":         {SavingThrow.POISON: 1, SavingThrow.DEATH: -1, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 1, SavingThrow.SPELL: -1},
    "Minotaur":       {SavingThrow.POISON: 2, SavingThrow.DEATH: 1, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: -2, SavingThrow.SPELL: -2},
    "Lizardfolk":     {SavingThrow.POISON: 2, SavingThrow.DEATH: 0, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 0, SavingThrow.SPELL: -1},
    "Ogre":           {SavingThrow.POISON: 2, SavingThrow.DEATH: 1, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: -2, SavingThrow.SPELL: -2},
    "Demonkin":       {SavingThrow.POISON: 0, SavingThrow.DEATH: 1, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 1, SavingThrow.SPELL: 1},
}


# ---------------------------------------------------------------------------
# Class-based Saving Throw Progression
# ---------------------------------------------------------------------------
# Bonus per N levels.  E.g., magic classes get better spell saves.

CLASS_SAVE_PROGRESSION = {
    # class_name: {save_type: bonus_per_5_levels}
    "Warrior":  {SavingThrow.POISON: 1, SavingThrow.DEATH: 2, SavingThrow.PETRIFICATION: 1, SavingThrow.ROD: 0, SavingThrow.SPELL: 0},
    "Rogue":    {SavingThrow.POISON: 1, SavingThrow.DEATH: 1, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 2, SavingThrow.SPELL: 0},
    "Cleric":   {SavingThrow.POISON: 1, SavingThrow.DEATH: 2, SavingThrow.PETRIFICATION: 1, SavingThrow.ROD: 1, SavingThrow.SPELL: 1},
    "Mage":     {SavingThrow.POISON: 0, SavingThrow.DEATH: 0, SavingThrow.PETRIFICATION: 1, SavingThrow.ROD: 2, SavingThrow.SPELL: 2},
    "Paladin":  {SavingThrow.POISON: 2, SavingThrow.DEATH: 2, SavingThrow.PETRIFICATION: 1, SavingThrow.ROD: 1, SavingThrow.SPELL: 1},
    "Ranger":   {SavingThrow.POISON: 2, SavingThrow.DEATH: 1, SavingThrow.PETRIFICATION: 0, SavingThrow.ROD: 1, SavingThrow.SPELL: 0},
    "Druid":    {SavingThrow.POISON: 2, SavingThrow.DEATH: 1, SavingThrow.PETRIFICATION: 1, SavingThrow.ROD: 1, SavingThrow.SPELL: 1},
    "Warlock":  {SavingThrow.POISON: 0, SavingThrow.DEATH: 1, SavingThrow.PETRIFICATION: 1, SavingThrow.ROD: 2, SavingThrow.SPELL: 2},
    "Berserker":{SavingThrow.POISON: 1, SavingThrow.DEATH: 2, SavingThrow.PETRIFICATION: 1, SavingThrow.ROD: 0, SavingThrow.SPELL: -1},
    "Necromancer":{SavingThrow.POISON: 2, SavingThrow.DEATH: 2, SavingThrow.PETRIFICATION: 1, SavingThrow.ROD: 1, SavingThrow.SPELL: 1},
    "Shaman":   {SavingThrow.POISON: 2, SavingThrow.DEATH: 1, SavingThrow.PETRIFICATION: 1, SavingThrow.ROD: 1, SavingThrow.SPELL: 1},
    "Shadowknight":{SavingThrow.POISON: 1, SavingThrow.DEATH: 2, SavingThrow.PETRIFICATION: 1, SavingThrow.ROD: 1, SavingThrow.SPELL: 1},
}


# ---------------------------------------------------------------------------
# Stat Modifiers for Saving Throws
# ---------------------------------------------------------------------------

def _get_stat_bonus(stats: dict, save_type: SavingThrow) -> int:
    """
    Determine the stat bonus for a given saving throw.
    - Poison: Constitution protects
    - Death: Constitution protects
    - Petrification: Constitution protects
    - Rod: Dexterity (dodge) protects
    - Spell: Wisdom (willpower) protects
    """
    if not stats:
        return 0

    if save_type in (SavingThrow.POISON, SavingThrow.DEATH, SavingThrow.PETRIFICATION):
        stat = stats.get("con", 10)
    elif save_type == SavingThrow.ROD:
        stat = stats.get("dex", 10)
    elif save_type == SavingThrow.SPELL:
        stat = stats.get("wis", 10)
    else:
        return 0

    # Standard D&D-style bonus: (stat - 10) // 2
    return (stat - 10) // 2


# ---------------------------------------------------------------------------
# Core Saving Throw Functions
# ---------------------------------------------------------------------------

def get_base_save(character, save_type: SavingThrow) -> int:
    """
    Get the base saving throw target number for a character.
    Lower is better (character must roll >= this on a d20).
    Takes into account level, race, class, and any attribute bonuses.
    """
    if not hasattr(character, "attributes"):
        return 20  # worst case

    level = character.attributes.get("level", default=1)
    race = character.attributes.get("race", default="Human")
    char_class = character.attributes.get("class", default="Warrior")
    stats = character.attributes.get("stats", default={})

    # Clamp level to the table
    clamp_level = max(1, min(20, level))

    # Base save from level table
    base = BASE_SAVES_BY_LEVEL.get(clamp_level, BASE_SAVES_BY_LEVEL[20])
    save_value = base.get(save_type, 20)

    # Racial bonus
    racial_bonus = RACIAL_SAVE_BONUSES.get(race, {}).get(save_type, 0)
    save_value -= racial_bonus  # positive bonus decreases save target

    # Class progression bonus (bonus per 5 levels)
    class_prog = CLASS_SAVE_PROGRESSION.get(char_class, {}).get(save_type, 0)
    class_bonus = (level // 5) * class_prog
    save_value -= class_bonus

    # Stat bonus
    stat_bonus = _get_stat_bonus(stats, save_type)
    save_value -= stat_bonus

    # Clamp: minimum save of 2 (always a chance to fail), maximum of 20
    return max(2, min(20, save_value))


def calculate_dc(caster_level: int, caster_stat: int = 10, spell_level: int = 1) -> int:
    """
    Calculate the Difficulty Class for a spell/effect.
    DC = 10 + (caster_level // 2) + (caster_stat_bonus) + spell_level
    """
    stat_bonus = (caster_stat - 10) // 2
    return 10 + (caster_level // 2) + stat_bonus + spell_level


def roll_saving_throw(character, save_type: SavingThrow, dc: int = 0,
                      caster_level: int = 0, caster_stat: int = 10,
                      spell_level: int = 1) -> Tuple[bool, int, int]:
    """
    Perform a saving throw for a character.

    Args:
        character: The character making the save.
        save_type: The type of saving throw.
        dc: A fixed DC (if provided, overrides calculated DC).
        caster_level: Level of the caster / effect source.
        caster_stat: The casting stat of the source (default 10).
        spell_level: Effective spell level of the effect.

    Returns:
        Tuple of (passed: bool, roll: int, dc_used: int)
    """
    base_save = get_base_save(character, save_type)

    if dc == 0:
        dc = calculate_dc(caster_level, caster_stat, spell_level)

    roll = random.randint(1, 20)

    # Natural 20 always succeeds
    if roll == 20:
        return True, roll, dc

    # Natural 1 always fails
    if roll == 1:
        return False, roll, dc

    # Roll must be >= the target save number
    # Adjust: the base_save is the number needed on the die
    # But we're using a standard d20 vs DC system:
    # Roll + (20 - base_save) >= DC
    save_bonus = 20 - base_save
    total = roll + save_bonus
    passed = total >= dc

    return passed, roll, dc


def format_save_result(character, save_type: SavingThrow, passed: bool,
                       roll: int, dc: int) -> str:
    """Format a saving throw result for display."""
    display = SAVING_THROW_DISPLAY.get(save_type, str(save_type))
    if passed:
        return (f"|g{character.key} saves vs {display}|g! (Roll: {roll}, DC: {dc})|n")
    else:
        return (f"|r{character.key} fails save vs {display}|r! (Roll: {roll}, DC: {dc})|n")


def get_save_bonus_display(character) -> str:
    """
    Return a human-readable summary of the character's saving throw bonuses.
    """
    if not hasattr(character, "attributes"):
        return ""

    lines = []
    for save_type in SavingThrow:
        base = get_base_save(character, save_type)
        bonus = 20 - base
        display = SAVING_THROW_DISPLAY.get(save_type, save_type.value)
        sign = "+" if bonus >= 0 else ""
        lines.append(f"  {display}: {sign}{bonus}")

    return "\n".join(lines)