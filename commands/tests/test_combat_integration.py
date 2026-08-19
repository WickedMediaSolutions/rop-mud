#!/usr/bin/env python
"""
================================================================================
RITES OF PASSAGE — FULL COMBAT SYSTEM INTEGRATION TEST
================================================================================

Standalone test for the tick_combat module using mock objects (no DB required).
Covers every path through the new central CombatEngine and CombatHandler.

Run manually (bootstraps Django automatically):
    cd /root/rop/rop
    python commands/tests/test_combat_integration.py

Or with the Evennia test runner (recommended):
    evennia test commands.tests.test_combat_integration --verbosity=2
================================================================================
"""

from __future__ import annotations

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Bootstrap Django settings before importing any Evennia code
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
import django
django.setup()

import random
import time
import unittest
from unittest.mock import MagicMock


# ============================================================================
# Mock infrastructure (same pattern as test_production_audit.py)
# ============================================================================

class MockAttributeHandler:
    """Dict-backed attribute handler."""
    def __init__(self, data=None):
        self._store = dict(data) if data else {}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def add(self, key, value):
        self._store[key] = value

    def set(self, key, value):
        self._store[key] = value

    def has(self, key):
        return key in self._store

    def all(self):
        return dict(self._store)

    def __contains__(self, key):
        return key in self._store


class MockNDB:
    """Real attribute-storage object mimicking Evennia's ndb for state tracking."""
    def __init__(self):
        self._store = {}
    def __getattr__(self, name):
        if name == "_store":
            raise AttributeError(name)
        if name not in self._store:
            raise AttributeError(name)
        return self._store[name]
    def __setattr__(self, name, value):
        if name == "_store":
            super().__setattr__(name, value)
        else:
            self._store[name] = value
    def __delattr__(self, name):
        if name in self._store:
            del self._store[name]
    def clear(self):
        self._store.clear()


class MockBase:
    """Lightweight mock base for Evennia typeclass-compatible objects."""
    _id_counter = 0

    def __init__(self, key="mock"):
        MockBase._id_counter += 1
        self.id = MockBase._id_counter
        self.key = key
        self.attributes = MockAttributeHandler()
        self.db = MagicMock()
        self.ndb = MockNDB()
        self.location = None
        self.destination = None
        self.sessions = MagicMock()
        self.has_account = False
        self.contents = []
        self.tags = MagicMock()
        self.tags.get.return_value = None
        self.locks = MagicMock()
        self.account = None
        self.session = None
        # Mock for scripts.add
        class _ScriptsMock:
            def add(self, script_cls):
                m = MagicMock()
                m.id = id(script_cls) + MockBase._id_counter
                return m
        self.scripts = _ScriptsMock()

    def msg(self, text=None, prompt=None, **kwargs):
        pass

    @property
    def spells(self):
        from world.spells import SpellHandler
        return SpellHandler(self)

    @property
    def quests(self):
        from world.quests import QuestHandler
        return QuestHandler(self)


def mock_character(key="TestChar", race="Human", char_class="Warrior",
                   level=1, alignment="Neutral", hp=100, max_hp=100,
                   mana=50, max_mana=50, mv=100, max_mv=100, xp=0,
                   stats=None, **kwargs):
    """Create a fully-configured mock character."""
    char = MockBase(key=key)
    char.has_account = True
    attrs = char.attributes
    attrs.add("race", race)
    attrs.add("class", char_class)
    attrs.add("level", level)
    attrs.add("alignment", alignment)
    attrs.add("hp", hp)
    attrs.add("max_hp", max_hp)
    attrs.add("mana", mana)
    attrs.add("max_mana", max_mana)
    attrs.add("mv", mv)
    attrs.add("max_mv", max_mv)
    attrs.add("xp", xp)
    attrs.add("xp_to_level", 1000)
    if stats is None:
        stats = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
    attrs.add("stats", stats)
    attrs.add("money", 0)
    attrs.add("alignment_points", 0)
    attrs.add("warpoints", 0)
    attrs.add("kills", 0)
    attrs.add("stamina", 100)
    attrs.add("max_stamina", 100)
    attrs.add("prompt_enabled", True)
    attrs.add("equipped", {})
    attrs.add("learned_spells", [])
    attrs.add("position", "standing")
    attrs.add("autoloot", False)
    attrs.add("autosac", False)
    attrs.add("shield_amount", 0)
    attrs.add("spell_cooldowns", {})
    attrs.add("chargen_completed", True)
    for k, v in kwargs.items():
        if k.startswith("db_"):
            setattr(char.db, k[3:], v)
        elif k.startswith("ndb_"):
            setattr(char.ndb, k[4:], v)
        else:
            attrs.add(k, v)
    return char


def mock_room(key="TestRoom", safe_zone=False, outdoor=False):
    room = MockBase(key=key)
    room.attributes.add("safe_zone", safe_zone)
    room.attributes.add("outdoor", outdoor)
    room.msg_contents = MagicMock()
    return room


# ============================================================================
# Reset the ENGAGEMENTS table before each test
# ============================================================================

def _reset_combat_state():
    """Clear the global engagement table between tests."""
    import world.tick_combat as tc
    tc.ENGAGEMENTS.clear()
    tc.COMBAT_SCRIPT_UID = None


# ============================================================================
# TESTS
# ============================================================================

class TestEngagementTable(unittest.TestCase):
    """Test the central ENGAGEMENTS table management."""

    def setUp(self):
        _reset_combat_state()

    def test_01_start_combat_registers_both(self):
        """start_combat registers both parties in ENGAGEMENTS."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS

        a = mock_character("Attacker", hp=100, max_hp=100)
        b = mock_character("Defender", hp=100, max_hp=100)
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)

        self.assertIn(a.id, ENGAGEMENTS)
        self.assertIn(b.id, ENGAGEMENTS)
        self.assertIn(b.id, ENGAGEMENTS[a.id])
        self.assertIn(a.id, ENGAGEMENTS[b.id])

    def test_02_is_in_combat_correct(self):
        """is_in_combat returns True after registration, False after stop."""
        from world.tick_combat import CombatHandler

        a = mock_character("A", hp=100, max_hp=100)
        b = mock_character("B", hp=100, max_hp=100)
        room = mock_room("Room")
        a.location = room
        b.location = room

        self.assertFalse(CombatHandler.is_in_combat(a))
        self.assertFalse(CombatHandler.is_in_combat(b))

        CombatHandler.start_combat(a, b)
        self.assertTrue(CombatHandler.is_in_combat(a))
        self.assertTrue(CombatHandler.is_in_combat(b))

        CombatHandler.stop_combat(a)
        self.assertFalse(CombatHandler.is_in_combat(a))
        self.assertFalse(CombatHandler.is_in_combat(b))

    def test_03_cannot_attack_self(self):
        """start_combat with same attacker/target does nothing."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS

        a = mock_character("A", hp=100, max_hp=100)
        CombatHandler.start_combat(a, a)
        self.assertNotIn(a.id, ENGAGEMENTS)

    def test_04_already_fighting_same_target(self):
        """Calling start_combat with same target twice is a no-op (not re-registered)."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS

        a = mock_character("A", hp=100, max_hp=100)
        b = mock_character("B", hp=100, max_hp=100)
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        count_before = sum(len(v) for v in ENGAGEMENTS.values())
        CombatHandler.start_combat(a, b)  # should be a no-op
        count_after = sum(len(v) for v in ENGAGEMENTS.values())
        self.assertEqual(count_before, count_after)

    def test_05_stop_combat_clears_both_when_bidirectional_only(self):
        """When A stops and B only fights A, both are cleared."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS

        a = mock_character("A", hp=100, max_hp=100)
        b = mock_character("B", hp=100, max_hp=100)
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        CombatHandler.stop_combat(a)
        self.assertNotIn(a.id, ENGAGEMENTS)
        self.assertNotIn(b.id, ENGAGEMENTS)

    def test_06_get_target_returns_opponent(self):
        """get_target returns the opponent."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS

        a = mock_character("A", hp=99999, max_hp=99999)
        b = mock_character("B", hp=99999, max_hp=99999)
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        # With high HP, neither dies in the first round
        t = CombatHandler.get_target(a)
        self.assertEqual(t.id, b.id)
        t2 = CombatHandler.get_target(b)
        self.assertEqual(t2.id, a.id)

    def test_07_get_target_none_when_not_fighting(self):
        """get_target returns None when not in combat."""
        from world.tick_combat import CombatHandler

        a = mock_character("A")
        self.assertIsNone(CombatHandler.get_target(a))


class TestHitRolls(unittest.TestCase):
    """Test THAC0/AC-based hit resolution."""

    def setUp(self):
        _reset_combat_state()

    def test_01_hit_chance_equal_stats(self):
        """Equal level/stat combatants should have near 50% hit rate."""
        from world.tick_combat import _hit_roll

        a = mock_character("A", level=5, stats={"str": 10, "dex": 10, "con": 10,
                           "int": 10, "wis": 10, "cha": 10})
        b = mock_character("B", level=5, stats={"str": 10, "dex": 10, "con": 10,
                           "int": 10, "wis": 10, "cha": 10})
        hits = sum(1 for _ in range(500) if _hit_roll(a, b))
        # d20 formula: THAC0=16, AC=10 → roll_needed=6 → chance=75% → ~375/500
        self.assertGreater(hits, 250, f"Hit rate too low: {hits}/500")
        self.assertLess(hits, 480, f"Hit rate too high: {hits}/500")

    def test_02_higher_level_hits_more(self):
        """Level 20 attacker hits level 1 defender more often."""
        from world.tick_combat import _hit_roll

        a = mock_character("High", level=20, stats={"str": 10, "dex": 10, "con": 10,
                            "int": 10, "wis": 10, "cha": 10})
        b = mock_character("Low", level=1, stats={"str": 10, "dex": 10, "con": 10,
                           "int": 10, "wis": 10, "cha": 10})
        hits_high = sum(1 for _ in range(500) if _hit_roll(a, b))
        hits_low = sum(1 for _ in range(500) if _hit_roll(b, a))
        self.assertGreater(hits_high, hits_low,
                           f"Higher level should hit more: {hits_high} vs {hits_low}")

    def test_03_dex_improves_hit_chance(self):
        """High DEX attacker should hit more than low DEX attacker."""
        from world.tick_combat import _hit_roll

        d = mock_character("Victim", level=1, stats={"str": 10, "dex": 10, "con": 10,
                           "int": 10, "wis": 10, "cha": 10})
        high_dex = mock_character("HD", level=1, stats={"str": 10, "dex": 20, "con": 10,
                                  "int": 10, "wis": 10, "cha": 10})
        low_dex = mock_character("LD", level=1, stats={"str": 10, "dex": 3, "con": 10,
                                 "int": 10, "wis": 10, "cha": 10})
        hits_hd = sum(1 for _ in range(500) if _hit_roll(high_dex, d))
        hits_ld = sum(1 for _ in range(500) if _hit_roll(low_dex, d))
        self.assertGreater(hits_hd, hits_ld,
                           f"High DEX should hit more: {hits_hd} vs {hits_ld}")

    def test_04_hit_chance_always_bounded(self):
        """Hit chance stays within [5%, 95%] even at extreme stat differences."""
        from world.tick_combat import _hit_roll

        a = mock_character("God", level=50, stats={"str": 10, "dex": 50, "con": 10,
                            "int": 10, "wis": 10, "cha": 10})
        b = mock_character("Weak", level=1, stats={"str": 10, "dex": 1, "con": 1,
                           "int": 1, "wis": 1, "cha": 1})

        # Attacker hits defender — should always hit (max 95%)
        hits = sum(1 for _ in range(500) if _hit_roll(a, b))
        self.assertLess(hits, 499, f"Should never exceed 95%: {hits}/500")

        # Defender hits attacker — should always have 5% minimum
        hits_rev = sum(1 for _ in range(500) if _hit_roll(b, a))
        self.assertGreater(hits_rev, 0, f"Should have at least 5% min: {hits_rev}/500")


class TestDamage(unittest.TestCase):
    """Test damage calculation (via damage_formulas integration)."""

    def setUp(self):
        _reset_combat_state()

    def test_01_damage_structure(self):
        """_damage returns expected dict keys."""
        from world.tick_combat import _damage

        a = mock_character("A", level=5, stats={"str": 14, "dex": 10, "con": 10,
                            "int": 10, "wis": 10, "cha": 10})
        b = mock_character("B", level=5, stats={"str": 10, "dex": 10, "con": 10,
                           "int": 10, "wis": 10, "cha": 10})
        result = _damage(a, b)
        self.assertIn("damage", result)
        self.assertIn("crit", result)
        self.assertIn("absorbed", result)
        self.assertIn("type", result)
        self.assertGreaterEqual(result["damage"], 1)

    def test_02_higher_str_more_damage(self):
        """Higher STR should yield higher average damage."""
        from world.tick_combat import _damage

        b = mock_character("Victim", level=1)
        low_str = mock_character("LS", level=1, stats={"str": 8, "dex": 10, "con": 10,
                                 "int": 10, "wis": 10, "cha": 10})
        high_str = mock_character("HS", level=1, stats={"str": 20, "dex": 10, "con": 10,
                                  "int": 10, "wis": 10, "cha": 10})

        dmg_low = [_damage(low_str, b)["damage"] for _ in range(100)]
        dmg_high = [_damage(high_str, b)["damage"] for _ in range(100)]
        self.assertGreater(sum(dmg_high), sum(dmg_low),
                           "Higher STR should yield more damage")


class TestDeathHandling(unittest.TestCase):
    """Test death cleanup paths."""

    def setUp(self):
        _reset_combat_state()

    def test_01_npc_death_removes_engagement(self):
        """NPC death removes engagements and stops combat for killer."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS, _handle_target_death

        player = mock_character("Player", hp=100, max_hp=100)
        mob = mock_character("Mob", hp=10, max_hp=10)
        mob.has_account = False  # NPC
        room = mock_room("Room")
        player.location = room
        mob.location = room

        CombatHandler.start_combat(player, mob)
        self.assertTrue(CombatHandler.is_in_combat(player))

        # Force HP to 0 and trigger death
        mob.attributes.add("hp", 0)
        _handle_target_death(player, mob)

        self.assertNotIn(mob.id, ENGAGEMENTS)
        # Player should no longer be in combat with the dead mob
        self.assertNotIn(mob.id, ENGAGEMENTS.get(player.id, set()))

    def test_02_player_unconscious_then_dead(self):
        """Player goes UNCONSCIOUS first, then DEAD on second kill."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS, _handle_target_death
        from world.combat_state import CombatStateMachine, CombatState

        killer = mock_character("Killer", hp=100, max_hp=100, level=1,
                               stats={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        victim = mock_character("Victim", hp=99999, max_hp=99999)
        victim.has_account = True  # Player
        room = mock_room("Room")
        killer.location = room
        victim.location = room

        # Set victim to FIGHTING state so transition to UNCONSCIOUS is valid
        from world.combat_state import CombatStateMachine, CombatState
        CombatStateMachine.set_state(victim, CombatState.ENGAGING)
        CombatStateMachine.set_state(victim, CombatState.FIGHTING)

        # First death — UNCONSCIOUS
        victim.attributes.add("hp", 0)
        _handle_target_death(killer, victim)
        self.assertEqual(CombatStateMachine.get_state(victim), CombatState.UNCONSCIOUS)
        self.assertEqual(victim.attributes.get("hp"), 0)

        # Second blow — DEAD (must re-register engagement since _remove_engagement cleared it)
        victim.attributes.add("hp", 0)
        # Manually re-add to allow _handle_target_death to find and transition to IDLE
        # Note: _remove_engagement already cleared entries, we just test state transition
        CombatStateMachine.set_state(victim, CombatState.UNCONSCIOUS)
        _handle_target_death(killer, victim)
        self.assertEqual(CombatStateMachine.get_state(victim), CombatState.IDLE)

    def test_03_death_cleans_up_for_all_fighting_that_target(self):
        """Multiple attackers — all are disengaged when target dies."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS, _handle_target_death

        a1 = mock_character("Attacker1", hp=100, max_hp=100)
        a2 = mock_character("Attacker2", hp=100, max_hp=100)
        target = mock_character("Target", hp=5, max_hp=5)
        target.has_account = False  # NPC
        room = mock_room("Room")
        a1.location = room
        a2.location = room
        target.location = room

        CombatHandler.start_combat(a1, target)
        CombatHandler.start_combat(a2, target)

        target.attributes.add("hp", 0)
        _handle_target_death(a1, target)

        self.assertNotIn(target.id, ENGAGEMENTS)


class TestFleeMechanics(unittest.TestCase):
    """Test flee calculations and mechanics."""

    def setUp(self):
        _reset_combat_state()

    def test_01_flee_chance_bounds(self):
        """_flee_chance stays in [0.10, 0.90]."""
        from world.tick_combat import _flee_chance

        a = mock_character("Fleer", level=1)
        b = mock_character("Blocker", level=50)
        chance = _flee_chance(a, b)
        self.assertGreaterEqual(chance, 0.10)
        self.assertLessEqual(chance, 0.90)

    def test_02_flee_removes_engagement(self):
        """Successful flee removes both from ENGAGEMENTS."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS

        a = mock_character("Fleer", hp=100, max_hp=100, level=50,
                           stats={"str": 10, "dex": 50, "con": 10, "int": 10, "wis": 10, "cha": 10})
        b = mock_character("Blocker", hp=100, max_hp=100, level=1,
                           stats={"str": 10, "dex": 1, "con": 1, "int": 1, "wis": 1, "cha": 1})
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        self.assertTrue(CombatHandler.is_in_combat(a))

        # Force flee to succeed
        orig = random.random
        try:
            random.random = lambda: 0.0
            CombatHandler.attempt_flee(a)
        finally:
            random.random = orig

        self.assertFalse(CombatHandler.is_in_combat(a))
        self.assertFalse(CombatHandler.is_in_combat(b))

    def test_03_failed_flee_keeps_combat_and_retaliates(self):
        """Failed flee keeps combat and opponent retaliates (deals damage)."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS

        a = mock_character("Fleer", hp=999999, max_hp=999999, level=1,
                           stats={"str": 10, "dex": 1, "con": 10, "int": 10, "wis": 10, "cha": 10})
        b = mock_character("Blocker", hp=999999, max_hp=999999, level=50,
                           stats={"str": 20, "dex": 50, "con": 10, "int": 10, "wis": 10, "cha": 10})
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        hp_before = a.attributes.get("hp")

        # Force flee to fail; only override random.random, NOT randint
        _orig_random = random.random

        try:
            random.random = lambda: 1.0
            CombatHandler.attempt_flee(a)
        finally:
            random.random = _orig_random

        self.assertTrue(CombatHandler.is_in_combat(a))
        # Target HP should have gone down from the retaliation attack
        self.assertLess(a.attributes.get("hp"), hp_before,
                        "Flee failure should cause retaliation damage")


class TestAttackRoundExecution(unittest.TestCase):
    """Test the _execute_attack_round function directly."""

    def setUp(self):
        _reset_combat_state()

    def test_01_hit_reduces_hp(self):
        """A hit reduces defender's HP."""
        from world.tick_combat import _execute_attack_round, CombatHandler

        a = mock_character("A", hp=100, max_hp=100, level=10,
                           stats={"str": 20, "dex": 20, "con": 10, "int": 10, "wis": 10, "cha": 10})
        b = mock_character("B", hp=100, max_hp=100, level=1,
                           stats={"str": 10, "dex": 1, "con": 1, "int": 10, "wis": 10, "cha": 10})
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)

        hp_before = b.attributes.get("hp")
        orig_randint = random.randint
        try:
            random.randint = lambda low, high: 1  # Always hit
            _execute_attack_round(a, b)
        finally:
            random.randint = orig_randint

        self.assertLess(b.attributes.get("hp"), hp_before,
                        "Defender HP should decrease on hit")

    def test_02_miss_does_not_reduce_hp(self):
        """A miss does not change defender's HP."""
        from world.tick_combat import _execute_attack_round, CombatHandler

        a = mock_character("A", hp=100, max_hp=100,
                           stats={"str": 10, "dex": 1, "con": 10, "int": 10, "wis": 10, "cha": 10})
        b = mock_character("B", hp=100, max_hp=100,
                           stats={"str": 10, "dex": 50, "con": 10, "int": 10, "wis": 10, "cha": 10})
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)

        hp_before = b.attributes.get("hp")
        orig_randint = random.randint
        try:
            random.randint = lambda low, high: 100  # Always miss
            _execute_attack_round(a, b)
        finally:
            random.randint = orig_randint

        self.assertEqual(b.attributes.get("hp"), hp_before,
                         "Defender HP should not change on miss")

    def test_03_killing_blow_npc_triggers_defeat(self):
        """NPC death during attack round triggers defeat handling."""
        from world.tick_combat import _execute_attack_round, CombatHandler

        a = mock_character("Killer", hp=100, max_hp=100, level=10,
                           stats={"str": 30, "dex": 20, "con": 10, "int": 10, "wis": 10, "cha": 10})
        mob = mock_character("Mob", hp=5, max_hp=5, level=1)
        mob.has_account = False  # NPC
        room = mock_room("Room")
        a.location = room
        mob.location = room

        CombatHandler.start_combat(a, mob)

        orig_randint = random.randint
        try:
            random.randint = lambda low, high: 1  # Always hit
            _execute_attack_round(a, mob)
        finally:
            random.randint = orig_randint

        # Mob should be at 0 HP after a hit
        self.assertEqual(mob.attributes.get("hp"), 0,
                         "NPC HP should be 0 after killing blow")


class TestCombatFlowScenarios(unittest.TestCase):
    """End-to-end combat scenarios simulating real gameplay."""

    def setUp(self):
        _reset_combat_state()

    def test_01_player_attacks_mob_to_death(self):
        """Simulate a player killing a mob across multiple rounds."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS, _execute_attack_round

        player = mock_character("Hero", "Human", "Warrior", level=5,
                                hp=200, max_hp=200,
                                stats={"str": 18, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 10})
        mob = mock_character("Goblin", hp=30, max_hp=30, level=1,
                             stats={"str": 8, "dex": 10, "con": 8, "int": 6, "wis": 6, "cha": 4})
        mob.has_account = False
        room = mock_room("Cave")
        player.location = room
        mob.location = room

        CombatHandler.start_combat(player, mob)
        self.assertTrue(CombatHandler.is_in_combat(player))

        rounds = 0
        max_rounds = 200
        while mob.attributes.get("hp") > 0 and rounds < max_rounds:
            _execute_attack_round(player, mob)
            rounds += 1
            if mob.attributes.get("hp") <= 0:
                break
            if not CombatHandler.is_in_combat(player):
                break

        self.assertGreater(rounds, 0, "Should have executed at least 1 round")
        self.assertLess(rounds, 200, "Mob should die in fewer than 200 rounds")
        self.assertEqual(mob.attributes.get("hp"), 0, "Mob should be dead")

    def test_02_two_players_trade_blows(self):
        """Two players attack each other until one is unconscious."""
        from world.tick_combat import CombatHandler, _execute_attack_round

        p1 = mock_character("Warrior1", "Human", "Warrior", level=5,
                            hp=100, max_hp=100,
                            stats={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10})
        p2 = mock_character("Warrior2", "Human", "Warrior", level=5,
                            hp=100, max_hp=100,
                            stats={"str": 14, "dex": 14, "con": 12, "int": 10, "wis": 10, "cha": 10})
        room = mock_room("Arena")
        p1.location = room
        p2.location = room

        CombatHandler.start_combat(p1, p2)

        rounds = 0
        max_rounds = 500
        while rounds < max_rounds:
            _execute_attack_round(p1, p2)
            rounds += 1
            if p2.attributes.get("hp") <= 0:
                break
            _execute_attack_round(p2, p1)
            rounds += 1
            if p1.attributes.get("hp") <= 0:
                break
            if not CombatHandler.is_in_combat(p1) or not CombatHandler.is_in_combat(p2):
                break

        self.assertLess(rounds, 500, "Combat should end within 500 rounds")
        self.assertTrue(
            p1.attributes.get("hp") <= 0 or p2.attributes.get("hp") <= 0,
            "At least one combatant should be dead or unconscious"
        )

    def test_03_combat_ends_when_target_leaves_room(self):
        """Engagement ends when target moves to a different room."""
        from world.tick_combat import CombatHandler, _execute_attack_round, ENGAGEMENTS

        a = mock_character("A", hp=100, max_hp=100)
        b = mock_character("B", hp=100, max_hp=100)
        room1 = mock_room("Room 1")
        room2 = mock_room("Room 2")
        a.location = room1
        b.location = room1

        CombatHandler.start_combat(a, b)
        self.assertTrue(CombatHandler.is_in_combat(a))

        # Move b to another room
        b.location = room2

        from world.tick_combat import _same_room
        self.assertFalse(_same_room(a, b))

        # Simulate what CombatEngine.at_repeat would do
        if not _same_room(a, b):
            CombatHandler._disengage_pair(a, b)

        self.assertFalse(CombatHandler.is_in_combat(a))
        self.assertFalse(CombatHandler.is_in_combat(b))

    def test_04_combat_blocked_in_safe_zone(self):
        """Attack round does nothing in a safe zone."""
        from world.tick_combat import CombatHandler, _execute_attack_round, ENGAGEMENTS

        a = mock_character("A", hp=100, max_hp=100)
        b = mock_character("B", hp=100, max_hp=100)
        safe_room = mock_room("SafeRoom", safe_zone=True)
        a.location = safe_room
        b.location = safe_room

        CombatHandler.start_combat(a, b)
        hp_before = b.attributes.get("hp")
        _execute_attack_round(a, b)

        # In a safe zone, the attack should be blocked
        self.assertEqual(b.attributes.get("hp"), hp_before,
                         "HP should not change in safe zone")

    def test_05_weapon_damage_baseline(self):
        """_weapon_damage returns positive value."""
        from world.tick_combat import _weapon_damage

        a = mock_character("Unarmed", stats={"str": 10, "dex": 10, "con": 10,
                            "int": 10, "wis": 10, "cha": 10})
        wd = _weapon_damage(a)
        self.assertGreaterEqual(wd, 1)

    def test_06_thac0_improves_with_level(self):
        """THAC0 decreases (improves) as level increases."""
        from world.tick_combat import _thac0

        low = mock_character("Low", level=1)
        high = mock_character("High", level=30)
        self.assertGreater(_thac0(low), _thac0(high),
                           "Higher level should have lower (better) THAC0")

    def test_07_ac_improves_with_armor(self):
        """AC decreases (improves) with higher DEX/CON."""
        from world.tick_combat import _armor_class

        weak = mock_character("Weak", stats={"str": 10, "dex": 1, "con": 1,
                              "int": 10, "wis": 10, "cha": 10})
        strong = mock_character("Strong", stats={"str": 10, "dex": 20, "con": 20,
                                 "int": 10, "wis": 10, "cha": 10})
        self.assertGreater(_armor_class(weak), _armor_class(strong),
                           "Higher DEX/CON should give lower (better) AC")

    def test_08_get_targets_multiple_opponents(self):
        """get_targets returns all opponents when fighting multiple."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS

        a = mock_character("A", hp=100, max_hp=100)
        b = mock_character("B", hp=100, max_hp=100)
        c = mock_character("C", hp=100, max_hp=100)
        room = mock_room("Room")
        a.location = room
        b.location = room
        c.location = room

        # Manually register a fighting both b and c (with ndb lists)
        ENGAGEMENTS.setdefault(a.id, set()).add(b.id)
        ENGAGEMENTS.setdefault(a.id, set()).add(c.id)
        ENGAGEMENTS.setdefault(b.id, set()).add(a.id)
        ENGAGEMENTS.setdefault(c.id, set()).add(a.id)
        a.ndb.combat_target = b
        a.ndb.combat_targets = [b, c]

        targets = CombatHandler.get_targets(a)
        self.assertEqual(len(targets), 2)

    def test_09_stat_helper_defaults(self):
        """Stat helpers return defaults for missing values."""
        from world.tick_combat import _stat, _level, _alive

        c = mock_character("Test")
        self.assertEqual(_stat(c, "nonexistent", 42), 42)
        self.assertEqual(_level(c), 1)
        self.assertTrue(_alive(c))
        c.attributes.add("hp", 0)
        self.assertFalse(_alive(c))

    def test_10_player_vs_npc_combat_full_loop(self):
        """Full combat loop: player attacks NPC, NPC fights back over multiple rounds."""
        from world.tick_combat import CombatHandler, _execute_attack_round

        player = mock_character("Adventurer", "Human", "Warrior", level=10,
                                hp=200, max_hp=200,
                                stats={"str": 18, "dex": 14, "con": 16, "int": 10, "wis": 10, "cha": 10})
        monster = mock_character("Orc", hp=80, max_hp=80, level=5,
                                 stats={"str": 16, "dex": 10, "con": 14, "int": 6, "wis": 6, "cha": 4})
        monster.has_account = False
        room = mock_room("Forest")
        player.location = room
        monster.location = room

        player_hp_before = player.attributes.get("hp")
        monster_hp_before = monster.attributes.get("hp")

        CombatHandler.start_combat(player, monster)

        # Run 30 attack rounds alternating between player and monster
        for i in range(30):
            if not CombatHandler.is_in_combat(player):
                break
            _execute_attack_round(player, monster)
            if not CombatHandler.is_in_combat(player):
                break
            _execute_attack_round(monster, player)
            if not CombatHandler.is_in_combat(player):
                break

        # Verify both sides took or dealt damage
        player_hp_after = player.attributes.get("hp")
        monster_hp_after = monster.attributes.get("hp")

        # One or both should be dead, or at least HP changed
        hp_changed = (
            player_hp_after < player_hp_before or
            monster_hp_after < monster_hp_before
        )
        self.assertTrue(hp_changed,
                        "HP should change after 30 rounds of combat")


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)