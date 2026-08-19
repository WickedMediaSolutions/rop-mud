"""
Test script for Orc Warrior fix — Race/Class spell gating.
Run with: python test_orc_warrior_fix.py
"""

import sys
import os

# Add the project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock Evennia modules before importing our code
import types

# Mock evennia module
evennia_mock = types.ModuleType("evennia")
evennia_mock.utils = types.ModuleType("evennia.utils")
evennia_mock.utils.evtable = types.ModuleType("evennia.utils.evtable")
evennia_mock.utils.search = types.ModuleType("evennia.utils.search")
evennia_mock.utils.delay = lambda *args, **kwargs: None
evennia_mock.objects = types.ModuleType("evennia.objects")
evennia_mock.objects.objects = types.ModuleType("evennia.objects.objects")
evennia_mock.scripts = types.ModuleType("evennia.scripts")
evennia_mock.scripts.scripts = types.ModuleType("evennia.scripts.scripts")
evennia_mock.objects.models = types.ModuleType("evennia.objects.models")

# Mock EvTable
class MockEvTable:
    def __init__(self, *args, **kwargs):
        self.rows = []
    def add_row(self, *args):
        self.rows.append(args)
    def __str__(self):
        return "\n".join(" | ".join(str(c) for c in row) for row in self.rows)

evennia_mock.utils.evtable.EvTable = MockEvTable

sys.modules["evennia"] = evennia_mock
sys.modules["evennia.utils"] = evennia_mock.utils
sys.modules["evennia.utils.evtable"] = evennia_mock.utils.evtable
sys.modules["evennia.utils.search"] = evennia_mock.utils.search
sys.modules["evennia.utils.delay"] = evennia_mock.utils.delay
sys.modules["evennia.objects"] = evennia_mock.objects
sys.modules["evennia.objects.objects"] = evennia_mock.objects.objects
sys.modules["evennia.objects.models"] = evennia_mock.objects.models
sys.modules["evennia.scripts"] = evennia_mock.scripts
sys.modules["evennia.scripts.scripts"] = evennia_mock.scripts.scripts

# Mock commands.command
commands_mock = types.ModuleType("commands")
commands_mock.command = types.ModuleType("commands.command")
class MockCommand:
    pass
commands_mock.command.Command = MockCommand
sys.modules["commands"] = commands_mock
sys.modules["commands.command"] = commands_mock.command

# Mock typeclasses
typeclasses_mock = types.ModuleType("typeclasses")
typeclasses_mock.characters = types.ModuleType("typeclasses.characters")
typeclasses_mock.objects = types.ModuleType("typeclasses.objects")
typeclasses_mock.rooms = types.ModuleType("typeclasses.rooms")
sys.modules["typeclasses"] = typeclasses_mock
sys.modules["typeclasses.characters"] = typeclasses_mock.characters
sys.modules["typeclasses.objects"] = typeclasses_mock.objects
sys.modules["typeclasses.rooms"] = typeclasses_mock.rooms


# Mock character class
class MockCharacter:
    """Simulates an Evennia character with attributes."""
    def __init__(self, name, race, char_class, level=1):
        self.key = name
        self._attrs = {
            "race": race,
            "class": char_class,
            "level": level,
            "stats": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "hp": 100,
            "max_hp": 100,
            "mana": 50,
            "max_mana": 50,
            "spell_cooldowns": {},
            "learned_spells": [],
        }
        self.has_account = True
        self.location = None
        self.contents = []
        self.ndb = type("ndb", (), {})()
        self.attributes = _AttrHandler(self._attrs)


class _AttrHandler:
    def __init__(self, attrs):
        self._attrs = attrs

    def get(self, key, default=None):
        return self._attrs.get(key, default)

    def add(self, key, value):
        self._attrs[key] = value

    def set(self, key, value):
        self._attrs[key] = value

    def has(self, key):
        return key in self._attrs


# Now import our modules
from world.race_class_matrix import (
    can_cast_spells, can_learn_spell, can_use_skill,
    is_race_class_valid, get_valid_classes_for_race,
    RACE_CLASS_MATRIX, CLASS_SPELL_SCHOOLS, CLASS_MAX_SPELL_LEVEL,
    RACE_MAX_SPELL_LEVEL
)
from world.spells import SPELLS, get_spell, SpellHandler


# ============================================================================
# TEST CASES
# ============================================================================

PASS = 0
FAIL = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}  {detail}")


print("=" * 60)
print("TEST 1: Orc Warrior — should NOT be able to cast spells")
print("=" * 60)

orc_warrior = MockCharacter("Grommash", "Orc", "Warrior", level=5)

test("can_cast_spells() returns False",
     can_cast_spells(orc_warrior) == False,
     f"Got: {can_cast_spells(orc_warrior)}")

test("can_learn_spell('sparks') returns False",
     can_learn_spell(orc_warrior, "sparks")[0] == False,
     f"Reason: {can_learn_spell(orc_warrior, 'sparks')[1]}")

test("can_learn_spell('minorheal') returns False",
     can_learn_spell(orc_warrior, "minorheal")[0] == False,
     f"Reason: {can_learn_spell(orc_warrior, 'minorheal')[1]}")

test("can_learn_spell('fireball') returns False",
     can_learn_spell(orc_warrior, "fireball")[0] == False,
     f"Reason: {can_learn_spell(orc_warrior, 'fireball')[1]}")

# SpellHandler.available_spells should return empty list
handler = SpellHandler(orc_warrior)
available = handler.available_spells()
test("available_spells() returns empty list",
     len(available) == 0,
     f"Got {len(available)} spells: {[s['name'] for s in available]}")

# SpellHandler.can_cast should reject
ok, err = handler.can_cast("sparks")
test("handler.can_cast('sparks') returns False",
     ok == False,
     f"Error: {err}")

# Verify the error message mentions the right reason
test("can_cast error mentions 'Warrior' or 'school'",
     "warrior" in err.lower() or "school" in err.lower() or "cannot" in err.lower(),
     f"Error: {err}")


print()
print("=" * 60)
print("TEST 2: High Elf Mage — SHOULD be able to cast spells")
print("=" * 60)

elf_mage = MockCharacter("Elrond", "High Elf", "Mage", level=5)

test("can_cast_spells() returns True",
     can_cast_spells(elf_mage) == True,
     f"Got: {can_cast_spells(elf_mage)}")

test("can_learn_spell('sparks') returns True",
     can_learn_spell(elf_mage, "sparks")[0] == True,
     f"Reason: {can_learn_spell(elf_mage, 'sparks')[1]}")

test("can_learn_spell('minorheal') returns False (Mage can't cast restoration)",
     can_learn_spell(elf_mage, "minorheal")[0] == False,
     f"Reason: {can_learn_spell(elf_mage, 'minorheal')[1]}")

# Fireball is level 20 — level 5 mage can't learn it yet
test("can_learn_spell('fireball') returns False (level 20 required, mage is level 5)",
     can_learn_spell(elf_mage, "fireball")[0] == False,
     f"Reason: {can_learn_spell(elf_mage, 'fireball')[1]}")

handler2 = SpellHandler(elf_mage)
available2 = handler2.available_spells()
test("available_spells() returns spells",
     len(available2) > 0,
     f"Got {len(available2)} spells")

# Should include Sparks (level 1 evocation)
spell_names = [s["name"] for s in available2]
test("'Sparks' is in available spells",
     "Sparks" in spell_names,
     f"Available: {spell_names}")

ok2, err2 = handler2.can_cast("sparks")
test("handler.can_cast('sparks') returns True",
     ok2 == True,
     f"Error: {err2}")


print()
print("=" * 60)
print("TEST 3: Human Paladin — restoration OK, evocation capped at 40")
print("=" * 60)

# Low level Paladin — should be able to cast restoration spells
pally_low = MockCharacter("Arthur", "Human", "Paladin", level=5)

test("can_cast_spells() returns True",
     can_cast_spells(pally_low) == True)

test("can_learn_spell('minorheal') returns True (restoration)",
     can_learn_spell(pally_low, "minorheal")[0] == True,
     f"Reason: {can_learn_spell(pally_low, 'minorheal')[1]}")

test("can_learn_spell('sparks') returns False (evocation not allowed for Paladin)",
     can_learn_spell(pally_low, "sparks")[0] == False,
     f"Reason: {can_learn_spell(pally_low, 'sparks')[1]}")

# High level Paladin — restoration should still work, evocation still blocked
pally_high = MockCharacter("Lancelot", "Human", "Paladin", level=50)

# Divine Restoration is level 44 — Paladin restoration cap is 40, so blocked
test("can_learn_spell('divinerestoration') returns False (Paladin restoration cap is 40, spell is 44)",
     can_learn_spell(pally_high, "divinerestoration")[0] == False,
     f"Reason: {can_learn_spell(pally_high, 'divinerestoration')[1]}")

test("can_learn_spell('fireball') returns False (evocation not allowed for Paladin)",
     can_learn_spell(pally_high, "fireball")[0] == False,
     f"Reason: {can_learn_spell(pally_high, 'fireball')[1]}")

# Paladin restoration cap at 40 — Divine Restoration is level 44, should be blocked
test("can_learn_spell('divinerestoration') blocked by level 40 cap",
     can_learn_spell(pally_high, "divinerestoration")[0] == False,
     f"Reason: {can_learn_spell(pally_high, 'divinerestoration')[1]}")


print()
print("=" * 60)
print("TEST 4: Race/Class Matrix Validation")
print("=" * 60)

test("Orc + Warrior is valid",
     is_race_class_valid("Orc", "Warrior") == True)

test("Orc + Mage is invalid",
     is_race_class_valid("Orc", "Mage") == False)

test("High Elf + Mage is valid",
     is_race_class_valid("High Elf", "Mage") == True)

test("High Elf + Necromancer is invalid",
     is_race_class_valid("High Elf", "Necromancer") == False)

test("Ogre only has Warrior",
     get_valid_classes_for_race("Ogre") == ["Warrior"],
     f"Got: {get_valid_classes_for_race('Ogre')}")

test("Human has all 10 classes",
     len(get_valid_classes_for_race("Human")) == 10,
     f"Got {len(get_valid_classes_for_race('Human'))} classes")


print()
print("=" * 60)
print("TEST 5: Race-level spell restrictions (Orc/Ogre/Minotaur)")
print("=" * 60)

# Orc Warlock — Warlock can cast evocation, but Orc race blocks all spells
orc_warlock = MockCharacter("Gul'dan", "Orc", "Warlock", level=10)
test("Orc Warlock: can_cast_spells() returns True (class allows it)",
     can_cast_spells(orc_warlock) == True)
test("Orc Warlock: can_learn_spell('sparks') returns False (race blocks)",
     can_learn_spell(orc_warlock, "sparks")[0] == False,
     f"Reason: {can_learn_spell(orc_warlock, 'sparks')[1]}")

# Ogre Warrior — Warrior can't cast anyway, but race also blocks
ogre_warrior = MockCharacter("Gronk", "Ogre", "Warrior", level=5)
test("Ogre Warrior: can_cast_spells() returns False",
     can_cast_spells(ogre_warrior) == False)

# Minotaur Warlock — Warlock can cast, but Minotaur race blocks
mino_warlock = MockCharacter("Taurus", "Minotaur", "Warlock", level=10)
test("Minotaur Warlock: can_cast_spells() returns True (class allows)",
     can_cast_spells(mino_warlock) == True)
test("Minotaur Warlock: can_learn_spell('sparks') returns False (race blocks)",
     can_learn_spell(mino_warlock, "sparks")[0] == False,
     f"Reason: {can_learn_spell(mino_warlock, 'sparks')[1]}")


print()
print("=" * 60)
print("TEST 6: Combat Skills Gating")
print("=" * 60)

test("Orc Warrior can use kick",
     can_use_skill(orc_warrior, "kick")[0] == True)

test("Orc Warrior can use bash",
     can_use_skill(orc_warrior, "bash")[0] == True)

test("Orc Warrior can use disarm",
     can_use_skill(orc_warrior, "disarm")[0] == True)

test("Orc Warrior cannot use backstab",
     can_use_skill(orc_warrior, "backstab")[0] == False,
     f"Reason: {can_use_skill(orc_warrior, 'backstab')[1]}")

test("High Elf Mage cannot use kick",
     can_use_skill(elf_mage, "kick")[0] == False,
     f"Reason: {can_use_skill(elf_mage, 'kick')[1]}")

test("Rogue can use backstab",
     can_use_skill(MockCharacter("Shadow", "Human", "Rogue", 5), "backstab")[0] == True)


# ============================================================================
# SUMMARY
# ============================================================================
print()
print("=" * 60)
total = PASS + FAIL
print(f"RESULTS: {PASS}/{total} passed, {FAIL}/{total} failed")
if FAIL == 0:
    print("🎉 ALL TESTS PASSED — Orc Warrior fix is working correctly!")
else:
    print(f"⚠️  {FAIL} test(s) FAILED — review the output above.")
print("=" * 60)

sys.exit(0 if FAIL == 0 else 1)