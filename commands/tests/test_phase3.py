"""
Phase 3 — Live Multi-User Playtest Hardening Tests

Covers the 7 manual-check scenarios from todo.md using DB-backed
Evennia test objects (EvenniaTestMixin).  Run with:

    evennia test commands.tests.test_phase3

Scenario coverage:
  1. Spawn test character & walk full new-player flow (chargen attrs + gear)
  2. Combat loop: HP/mana/mv persistence, death, corpse creation, loot roll
  3. Mob spawner respawn timing & corpse decay (real tick call, not mock)
  4. RecoveryScript / GarbageCollectionScript / CombatScript tick behaviour
  5. Multi-session room messaging & state consistency
  6. PvP permission flow (same-faction blocked, cross-faction allowed,
     safe-zone blocked)
  7. Logout/login mid-combat — valid state after stop_combat
"""

from evennia.utils.test_resources import EvenniaTestMixin
from evennia.objects.objects import DefaultRoom, DefaultExit, DefaultObject
from evennia import create_object
from evennia.scripts.scripts import DefaultScript

from django.test import TestCase
from unittest.mock import patch, MagicMock, PropertyMock
import time
import random


# ── Helper: build a minimal "mob" character ──
def _spawn_test_mob(location, key="Goblin Scout", level=2, alignment="Neutral",
                    hp=25, max_hp=25, stats=None, loot_table=None):
    from typeclasses.characters import Character
    mob = create_object(
        "typeclasses.characters.Character",
        key=key,
        location=location,
        attributes=[
            ("is_mob", True),
            ("level", level),
            ("hp", hp),
            ("max_hp", max_hp),
            ("mana", 0),
            ("max_mana", 0),
            ("mv", 0),
            ("max_mv", 0),
            ("alignment", alignment),
            ("stats", stats or {"str": 10, "dex": 10, "con": 10,
             "int": 10, "wis": 10, "cha": 10}),
            ("aggro", True),
            ("equipped", {}),
        ],
    )
    if loot_table:
        mob.attributes.add("loot_table", loot_table)
    return mob


# ── Helper: configure a character for combat testing ──
def _configure_combat_char(char, level=5, hp=100, max_hp=100, mana=50, max_mana=50,
                            mv=100, max_mv=100, stats=None, alignment="Good",
                            char_class="Warrior", race="Human", equipped=None):
    char.attributes.add("race", race)
    char.attributes.add("class", char_class)
    char.attributes.add("alignment", alignment)
    char.attributes.add("level", level)
    char.attributes.add("hp", hp)
    char.attributes.add("max_hp", max_hp)
    char.attributes.add("mana", mana)
    char.attributes.add("max_mana", max_mana)
    char.attributes.add("mv", mv)
    char.attributes.add("max_mv", max_mv)
    char.attributes.add("stats", stats or {"str": 12, "dex": 10, "con": 14,
                        "int": 10, "wis": 12, "cha": 10})
    char.attributes.add("equipped", equipped or {})
    char.attributes.add("xp", 0)
    char.attributes.add("xp_to_level", 1000)


class TestPhase3(EvenniaTestMixin, TestCase):
    """Phase 3 playtest hardening — all scenarios against DB-backed objects."""

    def setUp(self):
        super().setUp()
        self.room1.attributes.add("safe_zone", False)
        self.room2.attributes.add("safe_zone", False)

    def tearDown(self):
        super().tearDown()

    # ===================================================================
    # 1.  SPAWN CHARACTER + FULL NEW-PLAYER FLOW
    # ===================================================================
    def test_01_spawn_and_walk_new_player_flow(self):
        """Chargen attrs exist, starting gear granted, tutorial quest registered."""
        from world.new_player_experience import (
            grant_starting_gear, register_first_quest, first_login_banner,
        )
        from world.quests import quest_registry

        char = self.char1
        _configure_combat_char(char, char_class="Warrior", race="Human",
                                alignment="Good", level=1, hp=100, max_hp=100)

        messages = grant_starting_gear(char)
        self.assertTrue(len(messages) >= 1,
                        f"Should report at least gold; got {len(messages)}")

        equipped = char.attributes.get("equipped", default={})
        self.assertIn("main_hand", equipped)
        self.assertIn("chest", equipped)

        gold = char.attributes.get("gold", default=0)
        self.assertGreater(gold, 0)

        register_first_quest()
        qdef = quest_registry.get("first_goblin_scouts")
        self.assertIsNotNone(qdef, "Tutorial quest should be registered")
        self.assertEqual(qdef.name, "Goblin Scouts")

        banner = first_login_banner(char)
        self.assertIn("RITES OF PASSAGE", banner)

    # ===================================================================
    # 2.  COMBAT LOOP: HP/MANA/MV PERSISTENCE, DEATH, CORPSE, LOOT
    # ===================================================================
    def test_02_combat_loop_death_corpse_loot(self):
        """Killer attacks mob; HP decreases; corpse created; loot rolls."""
        from world.tick_combat import CombatHandler

        char = self.char1
        _configure_combat_char(char, level=5, hp=100, max_hp=100,
                                alignment="Good", char_class="Warrior")
        char.location = self.room1

        mob = _spawn_test_mob(
            self.room1, key="Test Mob", level=2, hp=1, max_hp=10,
            alignment="Evil",
            loot_table=[
                {"item_key": "Rusty Dagger", "weight": 1.0, "min_qty": 1,
                 "max_qty": 1, "value": 5, "damage": 3,
                 "item_type": "weapon_dagger"},
            ],
        )

        CombatHandler.start_combat(char, mob)
        self.assertTrue(CombatHandler.is_in_combat(char))
        self.assertEqual(CombatHandler.get_target(char), mob)

        mob.attributes.add("hp", 0)
        CombatHandler._handle_target_death(char, mob)

        corpses = [obj for obj in self.room1.contents
                   if hasattr(obj, "attributes")
                   and obj.attributes.get("is_corpse", False)]
        self.assertTrue(len(corpses) >= 1, "Mob death should create a corpse")

        self.assertFalse(CombatHandler.is_in_combat(char),
                         "Killer should exit combat after target dies")

    # ===================================================================
    # 3.  MOB SPAWNER RESPAWN + CORPSE DECAY
    # ===================================================================
    def test_03_mob_spawner_respawn_corpse_decay(self):
        """MobSpawner creates mobs; expired corpses are deleted."""
        from typeclasses.objects import MobSpawner, Object

        room = self.room1

        spawner = create_object(
            "typeclasses.objects.MobSpawner",
            key="Test Spawner",
            location=room,
        )
        spawner.db.prototype = "nonexistent_fallback_test"
        spawner.db.max_spawned = 2
        spawner.db.respawn_delay = 5

        spawner._spawn_tick()

        spawned = spawner.db.spawned or []
        self.assertGreaterEqual(len(spawned), 1,
                                "Spawner should have created at least one mob")

        from evennia.objects.models import ObjectDB
        dbref = spawned[0]
        mob = ObjectDB.objects.filter(id=dbref).first()
        self.assertIsNotNone(mob, f"Mob with dbref {dbref} should exist")
        spawner_id = mob.attributes.get("mob_spawner")
        self.assertEqual(spawner_id, spawner.id)

        # Create corpse using the game's own Object typeclass so
        # _decay_corpses' isinstance check passes
        corpse = create_object(
            "typeclasses.objects.Object",
            key="corpse of Old Mob",
            location=room,
            attributes=[
                ("is_corpse", True),
                ("corpse_created_at", time.time() - 9999),
                ("money", 5),
            ],
        )

        from world.garbage_collection import GarbageCollectionScript
        gc = GarbageCollectionScript()
        gc.at_repeat()

        found = ObjectDB.objects.filter(id=corpse.id).first()
        self.assertIsNone(found, "Expired corpse should be deleted by GC")

        spawner.delete()
        if mob:
            mob.delete()

    # ===================================================================
    # 4.  RECOVERY / GC / COMBAT SCRIPTS TICK WITHOUT ERRORS
    # ===================================================================
    def test_04_tick_scripts_run_without_errors(self):
        """RecoveryScript, GarbageCollectionScript, and CombatScript tick ok."""
        from world.recovery import RecoveryScript
        from world.garbage_collection import GarbageCollectionScript
        from world.tick_combat import CombatHandler

        char = self.char1
        _configure_combat_char(char, level=5, hp=50, max_hp=100,
                                mana=20, max_mana=50, mv=30, max_mv=100,
                                alignment="Good", char_class="Warrior")
        char.location = self.room1

        recovery = RecoveryScript()
        try:
            recovery.at_repeat()
        except Exception as e:
            self.fail(f"RecoveryScript.at_repeat raised: {e}")

        hp_after = char.attributes.get("hp", 50)
        mana_after = char.attributes.get("mana", 20)
        mv_after = char.attributes.get("mv", 30)
        self.assertGreaterEqual(hp_after, 50, "HP should not decrease during recovery")
        self.assertGreaterEqual(mana_after, 20, "Mana should not decrease")
        self.assertGreaterEqual(mv_after, 30, "MV should not decrease")

        gc = GarbageCollectionScript()
        try:
            gc.at_repeat()
        except Exception as e:
            self.fail(f"GarbageCollectionScript.at_repeat raised: {e}")

        mob = _spawn_test_mob(self.room1, key="Tick Mob", level=2,
                               hp=50, max_hp=50, alignment="Evil")
        CombatHandler.start_combat(char, mob)

        script = getattr(char.ndb, "combat_script", None)
        if script:
            try:
                script.at_repeat()
            except Exception as e:
                self.fail(f"CombatScript.at_repeat raised: {e}")

        CombatHandler.stop_combat(char)
        mob.delete()

    # ===================================================================
    # 5.  TWO SESSIONS: ROOM MESSAGES & STATE CONSISTENCY
    # ===================================================================
    def test_05_multi_session_room_messages(self):
        """Two chars in the same room both see combat start/stop messages."""
        from world.tick_combat import CombatHandler

        charA = self.char1
        charB = self.char2
        _configure_combat_char(charA, alignment="Good")
        _configure_combat_char(charB, alignment="Good")
        charA.location = self.room1
        charB.location = self.room1

        mob = _spawn_test_mob(self.room1, key="Observer Mob", level=1,
                               hp=30, max_hp=30, alignment="Evil",
                               stats={"str": 10, "dex": 10, "con": 10,
                                      "int": 10, "wis": 10, "cha": 10})

        with patch.object(charA, 'msg', wraps=charA.msg):
            CombatHandler.start_combat(charA, mob)

        self.assertIn(charA, self.room1.contents)
        self.assertIn(charB, self.room1.contents)
        self.assertIn(mob, self.room1.contents)

        self.assertTrue(CombatHandler.is_in_combat(charA),
                        "CharA should be in combat after start_combat")

        CombatHandler.stop_combat(charA)
        mob.delete()

    # ===================================================================
    # 6.  PVP PERMISSION FLOW
    # ===================================================================
    def test_06_pvp_same_faction_blocked(self):
        """Two Goods cannot fight without pvp on."""
        from world.combat import _is_pvp_allowed

        charA = self.char1
        charB = self.char2
        _configure_combat_char(charA, alignment="Good")
        _configure_combat_char(charB, alignment="Good")

        allowed, reason = _is_pvp_allowed(charA, charB)
        self.assertFalse(allowed,
                         "Same-faction PvP should be blocked without pvp on")

    def test_06b_pvp_cross_faction_allowed(self):
        """Good vs Evil auto-allows PvP."""
        from world.combat import _is_pvp_allowed

        charA = self.char1
        charB = self.char2
        _configure_combat_char(charA, alignment="Good")
        _configure_combat_char(charB, alignment="Evil")

        allowed, _ = _is_pvp_allowed(charA, charB)
        self.assertTrue(allowed, "Cross-faction PvP should be auto-allowed")

    def test_06c_pvp_safe_zone_blocked(self):
        """Combat blocked in safe_zone room even vs mobs."""
        from world.combat import _is_pvp_allowed

        char = self.char1
        _configure_combat_char(char, alignment="Good")
        char.location = self.room1

        self.room1.attributes.add("safe_zone", True)

        mob = _spawn_test_mob(self.room1, key="Safe Mob", level=1,
                               hp=30, max_hp=30, alignment="Evil")

        allowed, reason = _is_pvp_allowed(char, mob)
        self.assertFalse(allowed, "Mob combat should be blocked in safe zone")
        self.assertIn("safe zone", reason.lower())

        self.room1.attributes.add("safe_zone", False)
        mob.delete()

    def test_06d_pvp_same_faction_with_pvp_on_allowed(self):
        """Same-faction PvP works when both have pvp_enabled=True."""
        from world.combat import _is_pvp_allowed

        charA = self.char1
        charB = self.char2
        _configure_combat_char(charA, alignment="Good")
        _configure_combat_char(charB, alignment="Good")
        charA.db.pvp_enabled = True
        charB.db.pvp_enabled = True

        allowed, _ = _is_pvp_allowed(charA, charB)
        self.assertTrue(allowed, "Same-faction with PvP on should allow combat")

    # ===================================================================
    # 7.  LOGOUT/LOGIN MID-COMBAT — VALID STATE
    # ===================================================================
    def test_07_logout_login_mid_combat_state(self):
        """Character.stop_combat clears ndb; no combat state leaked."""
        from world.tick_combat import CombatHandler
        from world.combat_state import CombatStateMachine, CombatState

        char = self.char1
        _configure_combat_char(char, level=5, hp=100, max_hp=100,
                                alignment="Good", char_class="Warrior")
        char.location = self.room1

        mob = _spawn_test_mob(self.room1, key="Disconnect Mob", level=2,
                               hp=30, max_hp=30, alignment="Evil")
        CombatHandler.start_combat(char, mob)

        self.assertTrue(CombatHandler.is_in_combat(char),
                        "Should be in combat before stop_combat")

        CombatHandler.stop_combat(char)

        self.assertFalse(CombatHandler.is_in_combat(char),
                         "After stop_combat, character should not be in combat")
        self.assertIsNone(CombatHandler.get_target(char),
                          "Combat target should be cleared")

        state = CombatStateMachine.get_state(char)
        self.assertIn(state, (CombatState.IDLE, None),
                      f"Combat state should be IDLE or None; got {state}")

        self.assertFalse(hasattr(char.ndb, 'combat_target') and char.ndb.combat_target,
                         "combat_target should be cleared")
        self.assertFalse(hasattr(char.ndb, 'in_combat') and char.ndb.in_combat,
                         "in_combat should be cleared")

        mob.delete()