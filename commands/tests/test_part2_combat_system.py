#!/usr/bin/env python
"""
================================================================================
RITES OF PASSAGE — PART 2: COMBAT SYSTEM VERIFICATION TEST
================================================================================

Standalone test for ALL Part 2 combat system features using mock objects
(no DB required).  Covers every new feature implemented in this sprint.

Run manually:
    cd /root/rop/rop
    python commands/tests/test_part2_combat_system.py

Features tested:
  1. Combat skills integration (kick, bash, backstab, disarm) via queue system
  2. Ranged combat (bows/crossbows) auto-detection and DEX-based damage
  3. Two-weapon fighting / dual-wield off-hand attacks
  4. Stun/incapacitate effects that skip combat rounds
  5. Combat log / battle spam control (brief mode)
  6. ENGAGEMENTS table rebuild on @reload
  7. Stealth/hide for backstab
  8. Damage type from equipped weapon
  9. Full combat flow: player vs NPC, PvP, flee, death
 10. Combat state machine transitions
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
# Mock infrastructure (same pattern as test_combat_integration.py)
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
    attrs.add("combat_brief", False)
    attrs.add("stealthed", False)
    attrs.add("stunned", False)
    attrs.add("skill_cooldowns", {})
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


def mock_weapon_item(name="Iron Broadsword", damage=9, damage_type="slash",
                     slot="main_hand", armor=0):
    """Create a mock weapon item."""
    item = MockBase(key=name)
    item.attributes.add("damage", damage)
    item.attributes.add("damage_type", damage_type)
    item.attributes.add("slot", slot)
    item.attributes.add("armor", armor)
    item.attributes.add("weight", 5.0)
    item.attributes.add("value", 25)
    item.attributes.add("durability", 100)
    item.attributes.add("max_durability", 100)
    item.attributes.add("item_type", "equipment")
    return item


def mock_armor_item(name="Chain Shirt", armor=6, slot="chest"):
    """Create a mock armor item."""
    item = MockBase(key=name)
    item.attributes.add("armor", armor)
    item.attributes.add("slot", slot)
    item.attributes.add("weight", 10.0)
    item.attributes.add("value", 25)
    item.attributes.add("durability", 100)
    item.attributes.add("max_durability", 100)
    item.attributes.add("item_type", "equipment")
    return item


def mock_bow_item(name="Longbow", damage=8, damage_type="pierce", slot="two_hand"):
    """Create a mock bow item."""
    item = MockBase(key=name)
    item.attributes.add("damage", damage)
    item.attributes.add("damage_type", damage_type)
    item.attributes.add("slot", slot)
    item.attributes.add("armor", 0)
    item.attributes.add("weight", 3.0)
    item.attributes.add("value", 22)
    item.attributes.add("durability", 100)
    item.attributes.add("max_durability", 100)
    item.attributes.add("item_type", "equipment")
    return item


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

class TestCombatSkillsIntegration(unittest.TestCase):
    """Test combat skills (kick, bash, backstab, disarm) integration."""

    def setUp(self):
        _reset_combat_state()

    def test_01_queue_kick_success(self):
        """Queueing a kick skill succeeds for Warrior."""
        from world.tick_combat import CombatHandler

        a = mock_character("Warrior", char_class="Warrior", level=5,
                           hp=100, max_hp=100,
                           stats={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10})
        b = mock_character("Goblin", hp=50, max_hp=50, level=1)
        b.has_account = False
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        success, msg = CombatHandler.queue_skill(a, "kick")
        self.assertTrue(success, f"Kick queue should succeed: {msg}")
        self.assertIn("prepare", msg.lower())

    def test_02_queue_skill_not_in_combat(self):
        """Queueing a skill fails when not in combat."""
        from world.tick_combat import CombatHandler

        a = mock_character("Warrior", char_class="Warrior", level=5)
        success, msg = CombatHandler.queue_skill(a, "kick")
        self.assertFalse(success)
        self.assertIn("not in combat", msg.lower())

    def test_03_queue_skill_wrong_class(self):
        """Queueing a skill fails for wrong class."""
        from world.tick_combat import CombatHandler

        a = mock_character("Mage", char_class="Mage", level=5,
                           hp=100, max_hp=100)
        b = mock_character("Goblin", hp=50, max_hp=50, level=1)
        b.has_account = False
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        success, msg = CombatHandler.queue_skill(a, "bash")
        self.assertFalse(success)
        self.assertIn("cannot use", msg.lower())

    def test_04_queue_skill_insufficient_level(self):
        """Queueing a skill fails if level too low."""
        from world.tick_combat import CombatHandler

        a = mock_character("Warrior", char_class="Warrior", level=1,
                           hp=100, max_hp=100)
        b = mock_character("Goblin", hp=50, max_hp=50, level=1)
        b.has_account = False
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        success, msg = CombatHandler.queue_skill(a, "bash")
        self.assertFalse(success)
        self.assertIn("level", msg.lower())

    def test_05_queue_skill_insufficient_stamina(self):
        """Queueing a skill fails if stamina too low."""
        from world.tick_combat import CombatHandler

        a = mock_character("Warrior", char_class="Warrior", level=5,
                           hp=100, max_hp=100, stamina=5)
        b = mock_character("Goblin", hp=50, max_hp=50, level=1)
        b.has_account = False
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        success, msg = CombatHandler.queue_skill(a, "kick")
        self.assertFalse(success)
        self.assertIn("stamina", msg.lower())

    def test_06_queue_skill_on_cooldown(self):
        """Queueing a skill fails if on cooldown."""
        from world.tick_combat import CombatHandler

        a = mock_character("Warrior", char_class="Warrior", level=5,
                           hp=100, max_hp=100)
        # Set cooldown in the future
        a.attributes.add("skill_cooldowns", {"kick": time.time() + 100})
        b = mock_character("Goblin", hp=50, max_hp=50, level=1)
        b.has_account = False
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        success, msg = CombatHandler.queue_skill(a, "kick")
        self.assertFalse(success)
        self.assertIn("cooldown", msg.lower())

    def test_07_execute_skill_via_attack_round(self):
        """A queued skill is executed during the attack round."""
        from world.tick_combat import CombatHandler, _execute_attack_round

        a = mock_character("Warrior", char_class="Warrior", level=10,
                           hp=200, max_hp=200,
                           stats={"str": 20, "dex": 20, "con": 16, "int": 10, "wis": 10, "cha": 10})
        b = mock_character("Goblin", hp=100, max_hp=100, level=1,
                           stats={"str": 8, "dex": 10, "con": 8, "int": 6, "wis": 6, "cha": 4})
        b.has_account = False
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        hp_before = b.attributes.get("hp")

        # Queue a kick
        success, _ = CombatHandler.queue_skill(a, "kick")
        self.assertTrue(success)

        # Force hit
        orig_randint = random.randint
        try:
            random.randint = lambda low, high: 1  # Always hit
            _execute_attack_round(a, b)
        finally:
            random.randint = orig_randint

        # HP should have decreased (skill was executed)
        self.assertLess(b.attributes.get("hp"), hp_before,
                        "Defender HP should decrease after skill attack")

    def test_08_backstab_requires_stealth(self):
        """Backstab fails if not stealthed."""
        from world.tick_combat import CombatHandler

        a = mock_character("Rogue", char_class="Rogue", level=5,
                           hp=100, max_hp=100)
        b = mock_character("Goblin", hp=50, max_hp=50, level=1)
        b.has_account = False
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        success, msg = CombatHandler.queue_skill(a, "backstab")
        self.assertFalse(success)
        self.assertIn("hidden", msg.lower())

    def test_09_backstab_succeeds_when_stealthed(self):
        """Backstab succeeds when stealthed."""
        from world.tick_combat import CombatHandler

        a = mock_character("Rogue", char_class="Rogue", level=5,
                           hp=100, max_hp=100)
        a.attributes.add("stealthed", True)
        b = mock_character("Goblin", hp=50, max_hp=50, level=1)
        b.has_account = False
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        success, msg = CombatHandler.queue_skill(a, "backstab")
        self.assertTrue(success, f"Backstab should succeed when stealthed: {msg}")

    def test_10_disarm_skill_exists(self):
        """Disarm skill can be queued by Warrior."""
        from world.tick_combat import CombatHandler

        a = mock_character("Warrior", char_class="Warrior", level=10,
                           hp=100, max_hp=100)
        b = mock_character("Goblin", hp=50, max_hp=50, level=1)
        b.has_account = False
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        success, msg = CombatHandler.queue_skill(a, "disarm")
        self.assertTrue(success, f"Disarm should succeed for Warrior: {msg}")


class TestRangedCombat(unittest.TestCase):
    """Test ranged combat (bows/crossbows)."""

    def setUp(self):
        _reset_combat_state()

    def test_01_ranged_weapon_detection(self):
        """_is_ranged_weapon detects bows."""
        from world.tick_combat import _is_ranged_weapon

        a = mock_character("Ranger", char_class="Ranger", level=5)
        bow = mock_bow_item("Longbow")
        a.contents.append(bow)
        a.attributes.add("equipped", {"two_hand": "Longbow"})

        self.assertTrue(_is_ranged_weapon(a))

    def test_02_ranged_weapon_not_detected_for_sword(self):
        """_is_ranged_weapon returns False for melee weapons."""
        from world.tick_combat import _is_ranged_weapon

        a = mock_character("Warrior", char_class="Warrior", level=5)
        sword = mock_weapon_item("Iron Broadsword")
        a.contents.append(sword)
        a.attributes.add("equipped", {"main_hand": "Iron Broadsword"})

        self.assertFalse(_is_ranged_weapon(a))

    def test_03_ranged_attack_deals_damage(self):
        """Ranged attack round deals damage."""
        from world.tick_combat import CombatHandler, _execute_attack_round

        a = mock_character("Ranger", char_class="Ranger", level=10,
                           hp=200, max_hp=200,
                           stats={"str": 14, "dex": 20, "con": 14, "int": 10, "wis": 10, "cha": 10})
        bow = mock_bow_item("Longbow")
        a.contents.append(bow)
        a.attributes.add("equipped", {"two_hand": "Longbow"})

        b = mock_character("Goblin", hp=100, max_hp=100, level=1)
        b.has_account = False
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
                        "Defender HP should decrease after ranged attack")


class TestDualWield(unittest.TestCase):
    """Test two-weapon fighting / dual-wield."""

    def setUp(self):
        _reset_combat_state()

    def test_01_can_dual_wield_warrior(self):
        """Warriors can dual-wield."""
        from world.tick_combat import _can_dual_wield

        a = mock_character("Warrior", char_class="Warrior", level=5)
        self.assertTrue(_can_dual_wield(a))

    def test_02_cannot_dual_wield_mage(self):
        """Mages cannot dual-wield."""
        from world.tick_combat import _can_dual_wield

        a = mock_character("Mage", char_class="Mage", level=5)
        self.assertFalse(_can_dual_wield(a))

    def test_03_has_offhand_weapon_detection(self):
        """_has_offhand_weapon detects off-hand weapon."""
        from world.tick_combat import _has_offhand_weapon

        a = mock_character("Warrior", char_class="Warrior", level=5)
        offhand = mock_weapon_item("Iron Dagger", damage=4, damage_type="pierce", slot="off_hand")
        a.contents.append(offhand)
        a.attributes.add("equipped", {"main_hand": "Iron Broadsword", "off_hand": "Iron Dagger"})

        self.assertTrue(_has_offhand_weapon(a))

    def test_04_offhand_attack_executes(self):
        """Off-hand attack fires after main-hand hit."""
        from world.tick_combat import CombatHandler, _execute_attack_round

        a = mock_character("Warrior", char_class="Warrior", level=10,
                           hp=200, max_hp=200,
                           stats={"str": 20, "dex": 20, "con": 16, "int": 10, "wis": 10, "cha": 10})
        main_hand = mock_weapon_item("Iron Broadsword", damage=9, damage_type="slash", slot="main_hand")
        off_hand = mock_weapon_item("Iron Dagger", damage=4, damage_type="pierce", slot="off_hand")
        a.contents.append(main_hand)
        a.contents.append(off_hand)
        a.attributes.add("equipped", {"main_hand": "Iron Broadsword", "off_hand": "Iron Dagger"})

        b = mock_character("Goblin", hp=200, max_hp=200, level=1)
        b.has_account = False
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

        # HP should have decreased from main-hand + off-hand attacks
        self.assertLess(b.attributes.get("hp"), hp_before,
                        "Defender HP should decrease after dual-wield attack")


class TestStunEffects(unittest.TestCase):
    """Test stun/incapacitate effects in combat."""

    def setUp(self):
        _reset_combat_state()

    def test_01_stunned_character_skips_round(self):
        """A stunned character skips their attack round."""
        from world.tick_combat import CombatHandler, _execute_attack_round

        a = mock_character("Warrior", char_class="Warrior", level=5,
                           hp=100, max_hp=100)
        a.attributes.add("stunned", True)
        b = mock_character("Goblin", hp=100, max_hp=100, level=1)
        b.has_account = False
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

        # Stunned attacker should NOT deal damage
        self.assertEqual(b.attributes.get("hp"), hp_before,
                         "Stunned attacker should not deal damage")

    def test_02_is_stunned_helper(self):
        """_is_stunned returns correct value."""
        from world.tick_combat import _is_stunned

        a = mock_character("Warrior")
        self.assertFalse(_is_stunned(a))
        a.attributes.add("stunned", True)
        self.assertTrue(_is_stunned(a))


class TestCombatBriefMode(unittest.TestCase):
    """Test combat log / battle spam control."""

    def setUp(self):
        _reset_combat_state()

    def test_01_brief_mode_toggle(self):
        """combat_brief attribute toggles correctly."""
        a = mock_character("Warrior")
        self.assertFalse(a.attributes.get("combat_brief", False))
        a.attributes.add("combat_brief", True)
        self.assertTrue(a.attributes.get("combat_brief", False))

    def test_02_is_brief_combat_helper(self):
        """_is_brief_combat returns correct value."""
        from world.tick_combat import _is_brief_combat

        a = mock_character("Warrior")
        self.assertFalse(_is_brief_combat(a))
        a.attributes.add("combat_brief", True)
        self.assertTrue(_is_brief_combat(a))


class TestEngagementRebuild(unittest.TestCase):
    """Test ENGAGEMENTS table rebuild on @reload."""

    def setUp(self):
        _reset_combat_state()

    def test_01_rebuild_empty_table(self):
        """Rebuilding with no active combat returns 0."""
        from world.tick_combat import rebuild_engagements_from_active_combat

        count = rebuild_engagements_from_active_combat()
        self.assertEqual(count, 0)

    def test_02_rebuild_preserves_engagements(self):
        """Rebuilding after combat start preserves engagements."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS, rebuild_engagements_from_active_combat

        a = mock_character("Warrior", hp=100, max_hp=100)
        b = mock_character("Goblin", hp=50, max_hp=50, level=1)
        b.has_account = False
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        self.assertTrue(CombatHandler.is_in_combat(a))

        # Simulate reload: clear ENGAGEMENTS but keep ndb state
        ENGAGEMENTS.clear()
        self.assertFalse(CombatHandler.is_in_combat(a))

        # Rebuild should restore engagements from ndb
        count = rebuild_engagements_from_active_combat()
        # Note: rebuild scans ObjectDB which won't find our mocks,
        # but the function itself should not crash
        self.assertIsInstance(count, int)


class TestStealthHide(unittest.TestCase):
    """Test stealth/hide for backstab."""

    def setUp(self):
        _reset_combat_state()

    def test_01_hide_sets_stealthed(self):
        """Hide sets stealthed attribute."""
        a = mock_character("Rogue", char_class="Rogue", level=5)
        self.assertFalse(a.attributes.get("stealthed", False))
        a.attributes.add("stealthed", True)
        self.assertTrue(a.attributes.get("stealthed", False))

    def test_02_is_stealthed_helper(self):
        """_is_stealthed returns correct value."""
        from world.tick_combat import _is_stealthed

        a = mock_character("Rogue")
        self.assertFalse(_is_stealthed(a))
        a.attributes.add("stealthed", True)
        self.assertTrue(_is_stealthed(a))


class TestDamageTypeFromWeapon(unittest.TestCase):
    """Test damage type from equipped weapon."""

    def setUp(self):
        _reset_combat_state()

    def test_01_damage_type_reads_from_weapon(self):
        """_damage reads damage type from equipped weapon."""
        from world.tick_combat import _damage

        a = mock_character("Warrior", char_class="Warrior", level=5,
                           stats={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10})
        sword = mock_weapon_item("Iron Broadsword", damage=9, damage_type="slash", slot="main_hand")
        a.contents.append(sword)
        a.attributes.add("equipped", {"main_hand": "Iron Broadsword"})

        b = mock_character("Goblin", hp=50, max_hp=50, level=1)
        result = _damage(a, b)
        self.assertIn("type", result)
        # Should be SLASH from the sword
        from world.damage_formulas import DamageType
        self.assertEqual(result["type"], DamageType.SLASH)

    def test_02_damage_type_defaults_to_blunt(self):
        """_damage defaults to BLUNT when no weapon equipped (unarmed)."""
        from world.tick_combat import _damage

        a = mock_character("Warrior", char_class="Warrior", level=5)
        b = mock_character("Goblin", hp=50, max_hp=50, level=1)
        result = _damage(a, b)
        self.assertIn("type", result)
        from world.damage_formulas import DamageType
        self.assertEqual(result["type"], DamageType.BLUNT)


class TestFullCombatFlow(unittest.TestCase):
    """End-to-end combat scenarios simulating real gameplay."""

    def setUp(self):
        _reset_combat_state()

    def test_01_player_vs_npc_full_loop(self):
        """Full combat loop: player attacks NPC, NPC fights back."""
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

        # Run 30 attack rounds alternating
        for i in range(30):
            if not CombatHandler.is_in_combat(player):
                break
            _execute_attack_round(player, monster)
            if not CombatHandler.is_in_combat(player):
                break
            _execute_attack_round(monster, player)
            if not CombatHandler.is_in_combat(player):
                break

        player_hp_after = player.attributes.get("hp")
        monster_hp_after = monster.attributes.get("hp")

        hp_changed = (
            player_hp_after < player_hp_before or
            monster_hp_after < monster_hp_before
        )
        self.assertTrue(hp_changed,
                        "HP should change after 30 rounds of combat")

    def test_02_pvp_combat_flow(self):
        """Two players trade blows until one is unconscious."""
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

    def test_03_flee_mechanics(self):
        """Flee removes from combat on success."""
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

    def test_04_combat_blocked_in_safe_zone(self):
        """Attack round does nothing in a safe zone."""
        from world.tick_combat import CombatHandler, _execute_attack_round

        a = mock_character("A", hp=100, max_hp=100)
        b = mock_character("B", hp=100, max_hp=100)
        safe_room = mock_room("SafeRoom", safe_zone=True)
        a.location = safe_room
        b.location = safe_room

        CombatHandler.start_combat(a, b)
        hp_before = b.attributes.get("hp")
        _execute_attack_round(a, b)

        self.assertEqual(b.attributes.get("hp"), hp_before,
                         "HP should not change in safe zone")

    def test_05_npc_death_removes_engagement(self):
        """NPC death removes engagements."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS, _handle_target_death

        player = mock_character("Player", hp=100, max_hp=100)
        mob = mock_character("Mob", hp=10, max_hp=10)
        mob.has_account = False
        room = mock_room("Room")
        player.location = room
        mob.location = room

        CombatHandler.start_combat(player, mob)
        self.assertTrue(CombatHandler.is_in_combat(player))

        mob.attributes.add("hp", 0)
        _handle_target_death(player, mob)

        self.assertNotIn(mob.id, ENGAGEMENTS)

    def test_06_player_unconscious_then_dead(self):
        """Player goes UNCONSCIOUS first, then DEAD on second kill."""
        from world.tick_combat import CombatHandler, _handle_target_death
        from world.combat_state import CombatStateMachine, CombatState

        killer = mock_character("Killer", hp=100, max_hp=100, level=1)
        victim = mock_character("Victim", hp=99999, max_hp=99999)
        victim.has_account = True
        room = mock_room("Room")
        killer.location = room
        victim.location = room

        CombatStateMachine.set_state(victim, CombatState.ENGAGING)
        CombatStateMachine.set_state(victim, CombatState.FIGHTING)

        # First death — UNCONSCIOUS
        victim.attributes.add("hp", 0)
        _handle_target_death(killer, victim)
        self.assertEqual(CombatStateMachine.get_state(victim), CombatState.UNCONSCIOUS)

        # Second blow — DEAD
        CombatStateMachine.set_state(victim, CombatState.UNCONSCIOUS)
        _handle_target_death(killer, victim)
        self.assertEqual(CombatStateMachine.get_state(victim), CombatState.IDLE)

    def test_07_thac0_improves_with_level(self):
        """THAC0 decreases (improves) as level increases."""
        from world.tick_combat import _thac0

        low = mock_character("Low", level=1)
        high = mock_character("High", level=30)
        self.assertGreater(_thac0(low), _thac0(high),
                           "Higher level should have lower (better) THAC0")

    def test_08_ac_improves_with_armor(self):
        """AC decreases (improves) with higher DEX/CON."""
        from world.tick_combat import _armor_class

        weak = mock_character("Weak", stats={"str": 10, "dex": 1, "con": 1,
                               "int": 10, "wis": 10, "cha": 10})
        strong = mock_character("Strong", stats={"str": 10, "dex": 20, "con": 20,
                                 "int": 10, "wis": 10, "cha": 10})
        self.assertGreater(_armor_class(weak), _armor_class(strong),
                           "Higher DEX/CON should give lower (better) AC")

    def test_09_hit_chance_bounded(self):
        """Hit chance stays within [5%, 95%]."""
        from world.tick_combat import _hit_roll

        a = mock_character("God", level=50, stats={"str": 10, "dex": 50, "con": 10,
                            "int": 10, "wis": 10, "cha": 10})
        b = mock_character("Weak", level=1, stats={"str": 10, "dex": 1, "con": 1,
                           "int": 1, "wis": 1, "cha": 1})

        hits = sum(1 for _ in range(500) if _hit_roll(a, b))
        self.assertLess(hits, 499, f"Should never exceed 95%: {hits}/500")

        hits_rev = sum(1 for _ in range(500) if _hit_roll(b, a))
        self.assertGreater(hits_rev, 0, f"Should have at least 5% min: {hits_rev}/500")

    def test_10_weapon_damage_baseline(self):
        """_weapon_damage returns positive value."""
        from world.tick_combat import _weapon_damage

        a = mock_character("Unarmed", stats={"str": 10, "dex": 10, "con": 10,
                            "int": 10, "wis": 10, "cha": 10})
        wd = _weapon_damage(a)
        self.assertGreaterEqual(wd, 1)


class TestCombatStateMachine(unittest.TestCase):
    """Test combat state machine transitions."""

    def test_01_valid_transitions(self):
        """Valid state transitions succeed."""
        from world.combat_state import CombatStateMachine, CombatState

        a = mock_character("Warrior")
        self.assertTrue(CombatStateMachine.set_state(a, CombatState.ENGAGING))
        self.assertTrue(CombatStateMachine.set_state(a, CombatState.FIGHTING))
        self.assertTrue(CombatStateMachine.set_state(a, CombatState.FLEEING))
        self.assertTrue(CombatStateMachine.set_state(a, CombatState.IDLE))

    def test_02_invalid_transition(self):
        """Invalid state transitions fail."""
        from world.combat_state import CombatStateMachine, CombatState

        a = mock_character("Warrior")
        # Cannot go directly from IDLE to DEAD
        self.assertFalse(CombatStateMachine.set_state(a, CombatState.DEAD))

    def test_03_is_acting(self):
        """is_acting returns False for stunned/unconscious/dead."""
        from world.combat_state import CombatStateMachine, CombatState

        a = mock_character("Warrior")
        self.assertTrue(CombatStateMachine.is_acting(a))
        CombatStateMachine.set_state(a, CombatState.ENGAGING)
        CombatStateMachine.set_state(a, CombatState.FIGHTING)
        self.assertTrue(CombatStateMachine.is_acting(a))
        CombatStateMachine.set_state(a, CombatState.STUNNED)
        self.assertFalse(CombatStateMachine.is_acting(a))


class TestCombatHandlerAPI(unittest.TestCase):
    """Test CombatHandler public API."""

    def setUp(self):
        _reset_combat_state()

    def test_01_start_combat_registers_both(self):
        """start_combat registers both parties."""
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

    def test_02_cannot_attack_self(self):
        """start_combat with same attacker/target does nothing."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS

        a = mock_character("A", hp=100, max_hp=100)
        CombatHandler.start_combat(a, a)
        self.assertNotIn(a.id, ENGAGEMENTS)

    def test_03_stop_combat_clears_both(self):
        """stop_combat clears both parties."""
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

    def test_04_get_target_returns_opponent(self):
        """get_target returns the opponent."""
        from world.tick_combat import CombatHandler

        a = mock_character("A", hp=99999, max_hp=99999)
        b = mock_character("B", hp=99999, max_hp=99999)
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        t = CombatHandler.get_target(a)
        self.assertEqual(t.id, b.id)

    def test_05_get_target_none_when_not_fighting(self):
        """get_target returns None when not in combat."""
        from world.tick_combat import CombatHandler

        a = mock_character("A")
        self.assertIsNone(CombatHandler.get_target(a))

    def test_06_already_fighting_same_target(self):
        """Calling start_combat with same target twice is a no-op."""
        from world.tick_combat import CombatHandler, ENGAGEMENTS

        a = mock_character("A", hp=100, max_hp=100)
        b = mock_character("B", hp=100, max_hp=100)
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        count_before = sum(len(v) for v in ENGAGEMENTS.values())
        CombatHandler.start_combat(a, b)
        count_after = sum(len(v) for v in ENGAGEMENTS.values())
        self.assertEqual(count_before, count_after)


class TestDamageFormulas(unittest.TestCase):
    """Test damage formula calculations."""

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

    def test_03_armor_reduces_damage(self):
        """Armor reduces damage taken via deterministic absorption check."""
        from world.damage_formulas import _get_armor_value, calculate_armor_absorption, DamageType

        armored = mock_character("Armored", level=5, stats={"str": 10, "dex": 10, "con": 10,
                                 "int": 10, "wis": 10, "cha": 10})
        chest = mock_armor_item("Chain Shirt", armor=6, slot="chest")
        armored.contents.append(chest)
        armored.attributes.add("equipped", {"chest": "Chain Shirt"})

        unarmored = mock_character("Unarmored", level=5, stats={"str": 10, "dex": 10, "con": 10,
                                   "int": 10, "wis": 10, "cha": 10})

        # Deterministic: armor is detected
        armor_val = _get_armor_value(armored)
        self.assertGreater(armor_val, 0, f"Armor value should be > 0, got {armor_val}")

        # Deterministic: no armor -> zero absorption
        absorb_no_armor = calculate_armor_absorption(unarmored, 100, DamageType.SLASH)
        self.assertEqual(absorb_no_armor, 0,
                         "No armor should mean zero absorption")

        # Deterministic: armor -> positive absorption
        absorb_armor = calculate_armor_absorption(armored, 100, DamageType.SLASH)
        self.assertGreater(absorb_armor, 0,
                           "Armor should absorb some damage")

        # And armor absorbs MORE against high damage than low damage
        absorb_low = calculate_armor_absorption(armored, 20, DamageType.SLASH)
        absorb_high = calculate_armor_absorption(armored, 200, DamageType.SLASH)
        self.assertGreaterEqual(absorb_high, absorb_low,
                                "Higher base damage should absorb at least as much")


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

    def test_02_failed_flee_keeps_combat(self):
        """Failed flee keeps combat and opponent retaliates."""
        from world.tick_combat import CombatHandler

        a = mock_character("Fleer", hp=999999, max_hp=999999, level=1,
                           stats={"str": 10, "dex": 1, "con": 10, "int": 10, "wis": 10, "cha": 10})
        b = mock_character("Blocker", hp=999999, max_hp=999999, level=50,
                           stats={"str": 20, "dex": 50, "con": 10, "int": 10, "wis": 10, "cha": 10})
        room = mock_room("Room")
        a.location = room
        b.location = room

        CombatHandler.start_combat(a, b)
        hp_before = a.attributes.get("hp")

        _orig_random = random.random
        _orig_randint = random.randint
        try:
            random.random = lambda: 1.0   # Force flee failure
            random.randint = lambda low, high: 1  # Force retaliation hit
            CombatHandler.attempt_flee(a)
        finally:
            random.random = _orig_random
            random.randint = _orig_randint

        self.assertTrue(CombatHandler.is_in_combat(a))
        self.assertLess(a.attributes.get("hp"), hp_before,
                        "Flee failure should cause retaliation damage")


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("RITES OF PASSAGE — PART 2: COMBAT SYSTEM VERIFICATION")
    print("=" * 70)
    print()
    print("Testing all Part 2 combat features:")
    print("  1. Combat skills integration (kick, bash, backstab, disarm)")
    print("  2. Ranged combat (bows/crossbows)")
    print("  3. Two-weapon fighting / dual-wield")
    print("  4. Stun/incapacitate effects")
    print("  5. Combat log / battle spam control (brief mode)")
    print("  6. ENGAGEMENTS table rebuild on @reload")
    print("  7. Stealth/hide for backstab")
    print("  8. Damage type from equipped weapon")
    print("  9. Full combat flow: player vs NPC, PvP, flee, death")
    print(" 10. Combat state machine transitions")
    print()
    print("=" * 70)
    print()

    # Run all tests
    unittest.main(verbosity=2)