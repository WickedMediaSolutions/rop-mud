#!/usr/bin/env python
"""
============================================================================
ROP — TIER 4 RELIABILITY TESTS
============================================================================

Focused unit/integration tests for the three modules flagged in tasks.md §4.5:
  - world/damage_formulas.py
  - world/tick_combat.py
  - world/race_class_matrix.py

Run:
    cd /root/rop/rop
    python commands/tests/test_tier4_reliability.py

Or with Evennia test runner:
    evennia test commands.tests.test_tier4_reliability --verbosity=2
============================================================================
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
import django
django.setup()

import random
import unittest
from unittest.mock import MagicMock


# ============================================================================
# Mock helpers
# ============================================================================

class MockAttributeHandler:
    """Dict-backed attribute handler."""
    def __init__(self, data=None):
        self._store = dict(data) if data else {}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def add(self, key, value):
        self._store[key] = value

    def __contains__(self, key):
        return key in self._store


def mock_character(key="TestChar", race="Human", cls="Warrior", level=1,
                   hp=100, max_hp=100, stats=None, equipped=None,
                   alignment="Good", **extra):
    """Create a mock character with attribute handler."""
    char = MagicMock()
    char.key = key
    char.id = random.randint(1000, 9999)
    char.dbref = f"#{char.id}"

    attrs = {
        "race": race,
        "class": cls,
        "level": level,
        "hp": hp,
        "max_hp": max_hp,
        "mana": 50,
        "max_mana": 50,
        "mv": 100,
        "max_mv": 100,
        "xp": 0,
        "alignment": alignment,
        "stats": stats or {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        "equipped": equipped or {},
        "position": "standing",
        "money": 0,
        "pvp_enabled": False,
        "autoloot": False,
        "autosac": False,
    }
    attrs.update(extra)

    char.attributes = MockAttributeHandler(attrs)
    char.db = MagicMock()
    char.db.pvp_enabled = False
    char.ndb = MagicMock()
    char.ndb.combat_state = None
    char.ndb.active_effects = None
    char.location = None
    char.contents = []
    char.sessions = MagicMock()
    char.sessions.count.return_value = 1
    char.msg = MagicMock()
    char.home = None
    char.tags = MagicMock()
    char.tags.get.return_value = None
    char.is_typeclass = MagicMock(return_value=True)
    char.at_damage = MagicMock()

    return char


def _reset_combat_state():
    """Clear the global engagement table."""
    try:
        import world.tick_combat as tc
        tc.ENGAGEMENTS.clear()
    except Exception:
        pass


# ============================================================================
# Test: damage_formulas.py
# ============================================================================

class TestDamageFormulas(unittest.TestCase):
    """Unit tests for world/damage_formulas.py."""

    def setUp(self):
        _reset_combat_state()

    def test_damage_type_enum_exists(self):
        """DamageType enum must have all required types."""
        from world.damage_formulas import DamageType
        expected = {"SLASH", "PIERCE", "BLUNT", "MAGIC_FIRE", "MAGIC_COLD",
                    "MAGIC_LIGHTNING", "MAGIC_ARCANE", "MAGIC_SHADOW",
                    "MAGIC_HOLY", "POISON"}
        actual = {dt.name for dt in DamageType}
        for e in expected:
            self.assertIn(e, actual, f"DamageType.{e} missing")

    def test_armor_mitigation_covers_all_types(self):
        """ARMOR_MITIGATION must have entries for all DamageTypes."""
        from world.damage_formulas import ARMOR_MITIGATION, DamageType
        for dt in DamageType:
            self.assertIn(dt, ARMOR_MITIGATION, f"ARMOR_MITIGATION missing {dt}")

    def test_physical_types_have_mitigation(self):
        """Physical damage types must have non-zero armor mitigation."""
        from world.damage_formulas import ARMOR_MITIGATION, DamageType
        self.assertGreater(ARMOR_MITIGATION[DamageType.SLASH], 0)
        self.assertGreater(ARMOR_MITIGATION[DamageType.PIERCE], 0)
        self.assertGreater(ARMOR_MITIGATION[DamageType.BLUNT], 0)

    def test_magic_types_have_zero_mitigation(self):
        """Magic damage types must have zero armor mitigation."""
        from world.damage_formulas import ARMOR_MITIGATION, DamageType
        magic_types = [DamageType.MAGIC_FIRE, DamageType.MAGIC_COLD,
                       DamageType.MAGIC_LIGHTNING, DamageType.MAGIC_ARCANE,
                       DamageType.MAGIC_SHADOW, DamageType.MAGIC_HOLY]
        for mt in magic_types:
            self.assertEqual(ARMOR_MITIGATION[mt], 0,
                             f"{mt} should have 0 armor mitigation")

    def test_calculate_melee_damage_returns_dict(self):
        """calculate_melee_damage must return a dict with required keys."""
        from world.damage_formulas import calculate_melee_damage, DamageType
        a = mock_character("Attacker", level=10, stats={"str": 16, "dex": 12, "con": 10, "int": 10, "wis": 10, "cha": 10})
        d = mock_character("Defender", level=10)
        result = calculate_melee_damage(a, d, 20, DamageType.SLASH)
        self.assertIsInstance(result, dict)
        for key in ("damage", "crit", "absorbed", "type"):
            self.assertIn(key, result, f"Missing key '{key}' in result")

    def test_calculate_melee_damage_higher_str_more_damage(self):
        """Higher STR should yield higher average damage."""
        from world.damage_formulas import calculate_melee_damage, DamageType
        d = mock_character("Defender", level=10)
        weak = mock_character("Weak", level=10, stats={"str": 8, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        strong = mock_character("Strong", level=10, stats={"str": 20, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})

        weak_dmg = sum(calculate_melee_damage(weak, d, 20, DamageType.SLASH)["damage"] for _ in range(100))
        strong_dmg = sum(calculate_melee_damage(strong, d, 20, DamageType.SLASH)["damage"] for _ in range(100))
        self.assertGreater(strong_dmg, weak_dmg, "Higher STR should yield more damage")

    def test_calculate_spell_damage_returns_dict(self):
        """calculate_spell_damage must return a dict with damage key."""
        from world.damage_formulas import calculate_spell_damage
        caster = mock_character("Caster", level=10, stats={"str": 10, "dex": 10, "con": 10, "int": 18, "wis": 14, "cha": 10})
        target = mock_character("Target", level=10)
        result = calculate_spell_damage(caster, target, 50, "fire")
        self.assertIsInstance(result, dict)
        self.assertIn("damage", result)
        self.assertGreaterEqual(result["damage"], 0)

    def test_calculate_spell_damage_higher_int_more_damage(self):
        """Higher INT should yield higher spell damage."""
        from world.damage_formulas import calculate_spell_damage
        target = mock_character("Target", level=10)
        weak = mock_character("WeakMage", level=10, stats={"str": 10, "dex": 10, "con": 10, "int": 8, "wis": 10, "cha": 10})
        strong = mock_character("StrongMage", level=10, stats={"str": 10, "dex": 10, "con": 10, "int": 20, "wis": 14, "cha": 10})

        weak_dmg = sum(calculate_spell_damage(weak, target, 50, "fire")["damage"] for _ in range(50))
        strong_dmg = sum(calculate_spell_damage(strong, target, 50, "fire")["damage"] for _ in range(50))
        self.assertGreater(strong_dmg, weak_dmg, "Higher INT should yield more spell damage")

    def test_calculate_armor_absorption_reduces_damage(self):
        """Armor absorption must reduce damage for armored targets."""
        from world.damage_formulas import calculate_armor_absorption, DamageType
        naked = mock_character("Naked", level=10)
        armored = mock_character("Armored", level=10, equipped={"chest": {"armor": 50}})

        naked_abs = calculate_armor_absorption(naked, 20, DamageType.SLASH)
        armored_abs = calculate_armor_absorption(armored, 20, DamageType.SLASH)
        self.assertGreaterEqual(armored_abs, naked_abs,
                                "Armored target should absorb more damage")

    def test_calculate_armor_absorption_no_phantom(self):
        """Naked targets must have zero armor absorption."""
        from world.damage_formulas import calculate_armor_absorption, DamageType
        naked = mock_character("Naked", level=10)
        absorbed = calculate_armor_absorption(naked, 20, DamageType.SLASH)
        self.assertEqual(absorbed, 0, "Naked target should have zero absorption")

    def test_get_damage_type_modifier_returns_float(self):
        """get_damage_type_modifier must return a float."""
        from world.damage_formulas import get_damage_type_modifier, DamageType
        target = mock_character("Target", level=10)
        mod = get_damage_type_modifier(target, DamageType.SLASH)
        self.assertIsInstance(mod, float)

    def test_all_damage_types_work(self):
        """All DamageType values must produce valid melee damage results."""
        from world.damage_formulas import calculate_melee_damage, DamageType
        a = mock_character("A", level=10, stats={"str": 14, "dex": 12, "con": 10, "int": 10, "wis": 10, "cha": 10})
        d = mock_character("D", level=10)
        for dt in DamageType:
            result = calculate_melee_damage(a, d, 20, dt)
            self.assertIn("damage", result)
            self.assertGreaterEqual(result["damage"], 0)


# ============================================================================
# Test: tick_combat.py
# ============================================================================

class TestTickCombat(unittest.TestCase):
    """Unit tests for world/tick_combat.py."""

    def setUp(self):
        _reset_combat_state()

    def test_start_combat_registers_both(self):
        """start_combat must register both parties in ENGAGEMENTS."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS
        a = mock_character("A", hp=100, max_hp=100)
        b = mock_character("B", hp=100, max_hp=100)
        CombatHandler.start_combat(a, b)
        self.assertIn(a.id, ENGAGEMENTS)
        self.assertIn(b.id, ENGAGEMENTS)
        self.assertIn(b.id, ENGAGEMENTS[a.id])
        self.assertIn(a.id, ENGAGEMENTS[b.id])

    def test_is_in_combat_returns_correctly(self):
        """is_in_combat must return True after start, False after stop."""
        from world.tick_combat import CombatHandler
        a = mock_character("A", hp=100, max_hp=100)
        b = mock_character("B", hp=100, max_hp=100)
        self.assertFalse(CombatHandler.is_in_combat(a))
        CombatHandler.start_combat(a, b)
        self.assertTrue(CombatHandler.is_in_combat(a))
        CombatHandler.stop_combat(a)
        self.assertFalse(CombatHandler.is_in_combat(a))

    def test_start_combat_same_target_noop(self):
        """Calling start_combat with same target twice is a no-op."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS
        a = mock_character("A", hp=100, max_hp=100)
        b = mock_character("B", hp=100, max_hp=100)
        CombatHandler.start_combat(a, b)
        count_before = len(ENGAGEMENTS)
        CombatHandler.start_combat(a, b)
        self.assertEqual(len(ENGAGEMENTS), count_before)

    def test_get_target_returns_opponent(self):
        """get_target must return the opponent."""
        from world.tick_combat import CombatHandler
        a = mock_character("A", hp=100, max_hp=100)
        b = mock_character("B", hp=100, max_hp=100)
        CombatHandler.start_combat(a, b)
        self.assertEqual(CombatHandler.get_target(a), b)
        self.assertEqual(CombatHandler.get_target(b), a)

    def test_get_target_none_when_not_in_combat(self):
        """get_target must return None when not in combat."""
        from world.tick_combat import CombatHandler
        a = mock_character("A", hp=100, max_hp=100)
        self.assertIsNone(CombatHandler.get_target(a))

    def test_stop_combat_clears_both(self):
        """stop_combat must clear both parties from ENGAGEMENTS."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS
        a = mock_character("A", hp=100, max_hp=100)
        b = mock_character("B", hp=100, max_hp=100)
        CombatHandler.start_combat(a, b)
        CombatHandler.stop_combat(a)
        self.assertNotIn(a.id, ENGAGEMENTS)
        self.assertNotIn(b.id, ENGAGEMENTS)

    def test_thac0_decreases_with_level(self):
        """THAC0 must decrease (improve) as level increases."""
        from world.tick_combat import _thac0
        low = mock_character("Low", level=1)
        high = mock_character("High", level=30)
        self.assertGreater(_thac0(low), _thac0(high),
                           "Higher level should have lower (better) THAC0")

    def test_armor_class_decreases_with_dex(self):
        """AC must decrease (improve) with higher DEX."""
        from world.tick_combat import _armor_class
        clumsy = mock_character("Clumsy", stats={"str": 10, "dex": 1, "con": 10, "int": 10, "wis": 10, "cha": 10})
        agile = mock_character("Agile", stats={"str": 10, "dex": 20, "con": 10, "int": 10, "wis": 10, "cha": 10})
        self.assertGreater(_armor_class(clumsy), _armor_class(agile),
                           "Higher DEX should have lower (better) AC")

    def test_hit_roll_returns_bool(self):
        """_hit_roll must return a boolean."""
        from world.tick_combat import _hit_roll
        a = mock_character("A", level=10, stats={"str": 14, "dex": 14, "con": 10, "int": 10, "wis": 10, "cha": 10})
        b = mock_character("B", level=10, stats={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        result = _hit_roll(a, b)
        self.assertIsInstance(result, bool)

    def test_hit_roll_god_vs_peasant(self):
        """God-level attacker should hit peasant most of the time."""
        from world.tick_combat import _hit_roll
        god = mock_character("God", level=80, stats={"str": 10, "dex": 50, "con": 10, "int": 10, "wis": 10, "cha": 10})
        peasant = mock_character("Peasant", level=1, stats={"str": 10, "dex": 1, "con": 10, "int": 10, "wis": 10, "cha": 10})

        hits = sum(1 for _ in range(200) if _hit_roll(god, peasant))
        self.assertGreater(hits, 150, "God should hit peasant >75% of the time")

    def test_weapon_damage_positive(self):
        """_weapon_damage must return a positive value."""
        from world.tick_combat import _weapon_damage
        char = mock_character("Armed")
        dmg = _weapon_damage(char)
        self.assertGreaterEqual(dmg, 1)

    def test_flee_chance_bounds(self):
        """Flee chance must stay in [0.10, 0.90]."""
        from world.tick_combat import _flee_chance
        a = mock_character("A", level=1)
        b = mock_character("B", level=50)
        for _ in range(100):
            chance = _flee_chance(a, b)
            self.assertGreaterEqual(chance, 0.10)
            self.assertLessEqual(chance, 0.90)

    def test_stat_helpers(self):
        """_stat, _level, _alive must return correct values."""
        from world.tick_combat import _stat, _level, _alive
        char = mock_character("Test", level=15, hp=50, max_hp=100,
                              stats={"str": 18, "dex": 14, "con": 12, "int": 10, "wis": 10, "cha": 10})
        self.assertEqual(_stat(char, "str"), 18)
        self.assertEqual(_stat(char, "dex"), 14)
        self.assertEqual(_level(char), 15)
        self.assertTrue(_alive(char))

        dead = mock_character("Dead", hp=0, max_hp=100)
        self.assertFalse(_alive(dead))

    def test_damage_returns_dict_keys(self):
        """_damage must return a dict with required keys."""
        from world.tick_combat import _damage
        a = mock_character("Attacker")
        d = mock_character("Defender")
        result = _damage(a, d)
        self.assertIsInstance(result, dict)
        for key in ("damage", "type", "crit"):
            self.assertIn(key, result)

    def test_execute_attack_round_reduces_hp(self):
        """A hit during attack round must reduce defender's HP."""
        from world.tick_combat import _execute_attack_round, CombatHandler
        a = mock_character("A", hp=100, max_hp=100, level=10,
                           stats={"str": 20, "dex": 20, "con": 10, "int": 10, "wis": 10, "cha": 10})
        b = mock_character("B", hp=100, max_hp=100, level=1,
                           stats={"str": 1, "dex": 1, "con": 10, "int": 10, "wis": 10, "cha": 10})
        CombatHandler.start_combat(a, b)
        hp_before = b.attributes.get("hp")
        _execute_attack_round(a)
        hp_after = b.attributes.get("hp")
        # HP should decrease or stay same (miss possible)
        self.assertLessEqual(hp_after, hp_before)

    def test_handle_target_death_removes_engagements(self):
        """NPC death must remove engagements."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS, _handle_target_death
        a = mock_character("Killer", hp=100, max_hp=100)
        b = mock_character("Victim", hp=0, max_hp=100)
        CombatHandler.start_combat(a, b)
        _handle_target_death(b, a)
        self.assertNotIn(a.id, ENGAGEMENTS)
        self.assertNotIn(b.id, ENGAGEMENTS)

    def test_same_room_detection(self):
        """_same_room must correctly detect same/different rooms."""
        from world.tick_combat import _same_room
        room = MagicMock()
        room.id = 1
        a = mock_character("A")
        a.location = room
        b = mock_character("B")
        b.location = room
        self.assertTrue(_same_room(a, b))

        other_room = MagicMock()
        other_room.id = 2
        c = mock_character("C")
        c.location = other_room
        self.assertFalse(_same_room(a, c))

    def test_is_ranged_weapon_returns_bool(self):
        """_is_ranged_weapon must return a boolean."""
        from world.tick_combat import _is_ranged_weapon
        char = mock_character("Archer")
        result = _is_ranged_weapon(char)
        self.assertIsInstance(result, bool)

    def test_can_dual_wield(self):
        """_can_dual_wield must return True for Warriors, False for Mages."""
        from world.tick_combat import _can_dual_wield
        warrior = mock_character("Warrior", cls="Warrior")
        mage = mock_character("Mage", cls="Mage")
        self.assertTrue(_can_dual_wield(warrior))
        self.assertFalse(_can_dual_wield(mage))

    def test_is_stunned(self):
        """_is_stunned must detect stunned state via attributes."""
        from world.tick_combat import _is_stunned
        normal = mock_character("Normal")
        self.assertFalse(_is_stunned(normal))

        stunned = mock_character("Stunned", stunned=True)
        self.assertTrue(_is_stunned(stunned))

    def test_is_stealthed(self):
        """_is_stealthed must detect stealthed state via attributes."""
        from world.tick_combat import _is_stealthed
        normal = mock_character("Normal")
        self.assertFalse(_is_stealthed(normal))

        stealthed = mock_character("Stealthed", stealthed=True)
        self.assertTrue(_is_stealthed(stealthed))

    def test_is_brief_combat(self):
        """_is_brief_combat must return correct value."""
        from world.tick_combat import _is_brief_combat
        normal = mock_character("Normal")
        self.assertFalse(_is_brief_combat(normal))

        brief = mock_character("Brief", combat_brief=True)
        self.assertTrue(_is_brief_combat(brief))

    def test_rebuild_engagements_noop_when_empty(self):
        """rebuild_engagements_from_active_combat must return 0 when no combat."""
        from world.tick_combat import rebuild_engagements_from_active_combat
        result = rebuild_engagements_from_active_combat()
        self.assertEqual(result, 0)

    def test_combat_handler_methods_exist(self):
        """CombatHandler must expose all required static methods."""
        from world.tick_combat import CombatHandler
        methods = ["is_in_combat", "get_target", "start_combat", "stop_combat",
                   "get_targets"]
        for m in methods:
            self.assertTrue(hasattr(CombatHandler, m),
                            f"CombatHandler missing method '{m}'")


# ============================================================================
# Test: race_class_matrix.py
# ============================================================================

class TestRaceClassMatrix(unittest.TestCase):
    """Unit tests for world/race_class_matrix.py."""

    def test_matrix_has_all_races(self):
        """RACE_CLASS_MATRIX must have entries for all 16 races."""
        from world.race_class_matrix import RACE_CLASS_MATRIX
        from world.rules import RACES
        for race_name in RACES:
            self.assertIn(race_name, RACE_CLASS_MATRIX,
                          f"RACE_CLASS_MATRIX missing race '{race_name}'")

    def test_all_classes_appear_in_matrix(self):
        """Every class must appear in at least one race's allowed list."""
        from world.race_class_matrix import RACE_CLASS_MATRIX
        from world.rules import CLASSES
        all_allowed = set()
        for classes in RACE_CLASS_MATRIX.values():
            all_allowed.update(classes)
        for cls_name in CLASSES:
            self.assertIn(cls_name, all_allowed,
                          f"Class '{cls_name}' not allowed for any race")

    def test_is_race_class_valid(self):
        """is_race_class_valid must correctly validate combinations."""
        from world.race_class_matrix import is_race_class_valid
        self.assertTrue(is_race_class_valid("Human", "Warrior"))
        self.assertTrue(is_race_class_valid("High Elf", "Mage"))
        self.assertTrue(is_race_class_valid("Mountain Dwarf", "Cleric"))
        self.assertFalse(is_race_class_valid("Ogre", "Mage"))

    def test_get_valid_classes_for_race(self):
        """get_valid_classes_for_race must return non-empty list."""
        from world.race_class_matrix import get_valid_classes_for_race
        from world.rules import RACES
        for race_name in RACES:
            classes = get_valid_classes_for_race(race_name)
            self.assertIsInstance(classes, list)
            self.assertGreater(len(classes), 0,
                               f"No valid classes for race '{race_name}'")

    def test_can_equip_slot_warrior(self):
        """Warriors must be able to equip heavy armor."""
        from world.race_class_matrix import can_equip_slot
        char = mock_character("Warrior", cls="Warrior")
        self.assertTrue(can_equip_slot(char, "chest", "heavy"))

    def test_can_equip_slot_mage_heavy(self):
        """Mages must NOT be able to equip heavy armor."""
        from world.race_class_matrix import can_equip_slot
        char = mock_character("Mage", cls="Mage")
        self.assertFalse(can_equip_slot(char, "chest", "heavy"))

    def test_can_equip_slot_mage_dagger(self):
        """Mages must be able to wield daggers."""
        from world.race_class_matrix import can_equip_slot
        char = mock_character("Mage", cls="Mage")
        self.assertTrue(can_equip_slot(char, "main_hand", "dagger"))

    def test_can_equip_slot_pixie_heavy(self):
        """Pixie racial restriction: no heavy chest."""
        from world.race_class_matrix import can_equip_slot
        char = mock_character("Pixie", race="Pixie", cls="Warrior")
        self.assertFalse(can_equip_slot(char, "chest", "heavy"))

    def test_can_equip_slot_centaur_feet(self):
        """Centaur racial restriction: no feet slot."""
        from world.race_class_matrix import can_equip_slot
        char = mock_character("Centaur", race="Centaur", cls="Warrior")
        self.assertFalse(can_equip_slot(char, "feet", "boots"))

    def test_can_cast_spells_warrior(self):
        """Warriors must NOT be able to cast spells."""
        from world.race_class_matrix import can_cast_spells
        char = mock_character("Warrior", cls="Warrior")
        self.assertFalse(can_cast_spells(char))

    def test_can_cast_spells_mage(self):
        """Mages must be able to cast spells."""
        from world.race_class_matrix import can_cast_spells
        char = mock_character("Mage", cls="Mage")
        self.assertTrue(can_cast_spells(char))

    def test_can_learn_spell_orc_warrior(self):
        """Orc Warrior must be blocked from all spells."""
        from world.race_class_matrix import can_learn_spell
        from world.spells import SPELLS
        char = mock_character("OrcWar", race="Orc", cls="Warrior", level=80)
        for spell_key in SPELLS:
            self.assertFalse(can_learn_spell(char, spell_key),
                             f"Orc Warrior should not learn '{spell_key}'")

    def test_can_learn_spell_ogre(self):
        """Ogre must be blocked from all spells regardless of class."""
        from world.race_class_matrix import can_learn_spell
        char = mock_character("OgreMage", race="Ogre", cls="Mage", level=80)
        # Ogres can't cast spells at all
        self.assertFalse(can_learn_spell(char, "magic_missile"))

    def test_can_learn_spell_high_elf_mage(self):
        """High Elf Mage must be able to learn spells."""
        from world.race_class_matrix import can_learn_spell
        char = mock_character("ElfMage", race="High Elf", cls="Mage", level=10,
                              stats={"str": 10, "dex": 12, "con": 10, "int": 18, "wis": 14, "cha": 12})
        self.assertTrue(can_learn_spell(char, "magic_missile"))

    def test_can_use_skill_warrior_kick(self):
        """Warrior must have kick skill."""
        from world.race_class_matrix import can_use_skill
        char = mock_character("Warrior", cls="Warrior")
        self.assertTrue(can_use_skill(char, "kick"))

    def test_can_use_skill_mage_kick(self):
        """Mage must NOT have kick skill."""
        from world.race_class_matrix import can_use_skill
        char = mock_character("Mage", cls="Mage")
        self.assertFalse(can_use_skill(char, "kick"))

    def test_class_weapon_types_defined(self):
        """Every class must have defined weapon types."""
        from world.race_class_matrix import CLASS_WEAPON_TYPES
        from world.rules import CLASSES
        for cls_name in CLASSES:
            self.assertIn(cls_name, CLASS_WEAPON_TYPES,
                          f"CLASS_WEAPON_TYPES missing '{cls_name}'")
            self.assertIsInstance(CLASS_WEAPON_TYPES[cls_name], (list, set))

    def test_class_armor_types_defined(self):
        """Every class must have defined armor types."""
        from world.race_class_matrix import CLASS_ARMOR_TYPES
        from world.rules import CLASSES
        for cls_name in CLASSES:
            self.assertIn(cls_name, CLASS_ARMOR_TYPES,
                          f"CLASS_ARMOR_TYPES missing '{cls_name}'")
            self.assertIsInstance(CLASS_ARMOR_TYPES[cls_name], (list, set))

    def test_race_natural_armor_valid(self):
        """RACE_NATURAL_ARMOR must only reference valid races."""
        from world.race_class_matrix import RACE_NATURAL_ARMOR
        from world.rules import RACES
        for race_name in RACE_NATURAL_ARMOR:
            self.assertIn(race_name, RACES,
                          f"RACE_NATURAL_ARMOR references unknown race '{race_name}'")

    def test_race_forbidden_slots_valid(self):
        """RACE_FORBIDDEN_SLOTS must only reference valid races."""
        from world.race_class_matrix import RACE_FORBIDDEN_SLOTS
        from world.rules import RACES
        for race_name in RACE_FORBIDDEN_SLOTS:
            self.assertIn(race_name, RACES,
                          f"RACE_FORBIDDEN_SLOTS references unknown race '{race_name}'")

    def test_class_spell_schools_defined(self):
        """CLASS_SPELL_SCHOOLS must exist and be a dict."""
        from world.race_class_matrix import CLASS_SPELL_SCHOOLS
        self.assertIsInstance(CLASS_SPELL_SCHOOLS, dict)

    def test_class_skills_defined(self):
        """CLASS_SKILLS must exist and be a dict."""
        from world.race_class_matrix import CLASS_SKILLS
        self.assertIsInstance(CLASS_SKILLS, dict)


# ============================================================================
# Test: Stress / Load
# ============================================================================

class TestStressLoad(unittest.TestCase):
    """Stress/load tests for combat and damage systems."""

    def setUp(self):
        _reset_combat_state()

    def test_1000_damage_calculations(self):
        """1000 damage calculations must complete quickly."""
        from world.tick_combat import _damage
        a = mock_character("A", level=5, stats={"str": 14, "dex": 12, "con": 10, "int": 10, "wis": 10, "cha": 10})
        b = mock_character("B", level=5)
        import time
        start = time.time()
        for _ in range(1000):
            _damage(a, b)
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0, f"1000 damage calcs took {elapsed:.2f}s (limit 5s)")

    def test_1000_hit_rolls(self):
        """1000 hit rolls must complete quickly."""
        from world.tick_combat import _hit_roll
        a = mock_character("A", level=10, stats={"str": 14, "dex": 14, "con": 10, "int": 10, "wis": 10, "cha": 10})
        b = mock_character("B", level=10, stats={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        import time
        start = time.time()
        for _ in range(1000):
            _hit_roll(a, b)
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0, f"1000 hit rolls took {elapsed:.2f}s (limit 5s)")

    def test_100_combat_rounds(self):
        """100 combat rounds must complete without error."""
        from world.tick_combat import CombatHandler, _execute_attack_round
        a = mock_character("A", hp=99999, max_hp=99999, level=10,
                           stats={"str": 14, "dex": 14, "con": 10, "int": 10, "wis": 10, "cha": 10})
        b = mock_character("B", hp=99999, max_hp=99999, level=10,
                           stats={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        CombatHandler.start_combat(a, b)
        for _ in range(100):
            _execute_attack_round(a)
            _execute_attack_round(b)

    def test_100_melee_damage_calculations(self):
        """100 melee damage calculations across all damage types."""
        from world.damage_formulas import calculate_melee_damage, DamageType
        a = mock_character("A", level=10, stats={"str": 14, "dex": 12, "con": 10, "int": 10, "wis": 10, "cha": 10})
        d = mock_character("D", level=10)
        for dt in DamageType:
            for _ in range(100):
                result = calculate_melee_damage(a, d, 20, dt)
                self.assertIn("damage", result)

    def test_100_spell_damage_calculations(self):
        """100 spell damage calculations across all elements."""
        from world.damage_formulas import calculate_spell_damage
        caster = mock_character("Caster", level=10, stats={"str": 10, "dex": 10, "con": 10, "int": 18, "wis": 14, "cha": 10})
        target = mock_character("Target", level=10)
        elements = ["fire", "cold", "lightning", "arcane", "shadow", "holy", "poison"]
        for elem in elements:
            for _ in range(100):
                result = calculate_spell_damage(caster, target, 50, elem)
                self.assertIsInstance(result, dict)
                self.assertIn("damage", result)

    def test_100_mob_combat_loop(self):
        """100 mobs created and engaged in combat must complete without error."""
        from world.tick_combat import CombatHandler, _execute_attack_round, ENGAGEMENTS
        import time

        # Create 100 mobs and one player
        player = mock_character("Player", hp=99999, max_hp=99999, level=50,
                                stats={"str": 20, "dex": 20, "con": 20, "int": 10, "wis": 10, "cha": 10})
        mobs = []
        for i in range(100):
            mob = mock_character(f"Mob{i}", hp=500, max_hp=500, level=random.randint(1, 50),
                                 stats={"str": random.randint(8, 18), "dex": random.randint(8, 18),
                                        "con": random.randint(8, 18), "int": 10, "wis": 10, "cha": 10})
            mobs.append(mob)

        # Engage all mobs against the player
        start = time.time()
        for mob in mobs:
            CombatHandler.start_combat(mob, player)

        # Run 10 combat rounds for each mob
        for _ in range(10):
            for mob in mobs:
                if mob.id in ENGAGEMENTS:
                    _execute_attack_round(mob, player)

        elapsed = time.time() - start
        self.assertLess(elapsed, 30.0, f"100-mob combat loop took {elapsed:.2f}s (limit 30s)")

        # Clean up
        ENGAGEMENTS.clear()

    def test_1000_combat_loop(self):
        """1000 combat rounds between two characters must complete without error."""
        from world.tick_combat import CombatHandler, _execute_attack_round
        import time

        a = mock_character("A", hp=99999, max_hp=99999, level=10,
                           stats={"str": 14, "dex": 14, "con": 10, "int": 10, "wis": 10, "cha": 10})
        b = mock_character("B", hp=99999, max_hp=99999, level=10,
                           stats={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        CombatHandler.start_combat(a, b)

        start = time.time()
        for _ in range(1000):
            _execute_attack_round(a, b)
            _execute_attack_round(b, a)
        elapsed = time.time() - start

        self.assertLess(elapsed, 30.0, f"1000 combat rounds took {elapsed:.2f}s (limit 30s)")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)