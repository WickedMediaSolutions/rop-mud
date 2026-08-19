"""
Phase 3.2 / 3.3 / 3.4 Tests — PvP, Raid, World Events, Pets, Content Density
==============================================================================
Tests for:
  - Arena system (queue, match formation, ELO)
  - Battleground system (create, join, scoring)
  - Duel system (challenge, accept, wager, resolve)
  - Bounty system (place, claim, cancel)
  - Raid mechanics (phases, enrage, abilities)
  - Dungeon finder (queue, group formation)
  - World events (create, start, multipliers)
  - Pet system (adopt, combat, bonding)
  - Quest expansion (50+ quests registered)
  - Spell expansion (60+ spells registered)
  - Content expansion (200+ items, 150+ mobs)
"""

import random
import time
import unittest

# Use stub character for testing without Evennia DB
class StubAttrHandler:
    """Minimal Evennia-compatible attribute handler wrapper."""

    def __init__(self):
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def add(self, key, value):
        self._data[key] = value

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data


class StubCharacter:
    """Minimal character stub for testing systems."""

    _next_id = 1

    def __init__(self, key="TestChar", level=10):
        self.key = key
        self.id = StubCharacter._next_id
        StubCharacter._next_id += 1
        self.attributes = StubAttrHandler()
        self.db = type("DB", (), {"pvp_enabled": True})()
        self.location = None
        self.home = None
        self.contents = []
        self.messages = []
        self.has_account = True

        # Set default attributes
        self.attributes.add("level", level)
        self.attributes.add("stats", {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        self.attributes.add("hp", 100)
        self.attributes.add("max_hp", 100)
        self.attributes.add("mana", 50)
        self.attributes.add("max_mana", 50)
        self.attributes.add("mv", 100)
        self.attributes.add("max_mv", 100)
        self.attributes.add("gold", 5000)
        self.attributes.add("xp", 0)
        self.attributes.add("alignment", "Good")
        self.attributes.add("race", "Human")
        self.attributes.add("class", "Warrior")

    def msg(self, text):
        self.messages.append(text)

    def move_to(self, location, quiet=False):
        self.location = location


class StubRoom:
    """Minimal room stub."""

    def __init__(self, key="TestRoom"):
        self.key = key
        self.contents = []

    def msg_contents(self, text, exclude=None):
        exclude = exclude or []
        for obj in self.contents:
            if obj not in exclude and hasattr(obj, "msg"):
                obj.msg(text)


# ===========================================================================
# PvP SYSTEM TESTS (3.2)
# ===========================================================================

class TestArenaSystem(unittest.TestCase):
    """Test arena queue and match formation."""

    def setUp(self):
        from world.pvp_systems import arena_manager
        self.am = arena_manager
        # Clear queues and matches for testing
        for q in self.am._queues.values():
            q.clear()
        self.am._matches.clear()

    def test_join_queue_valid(self):
        char = StubCharacter("ArenaPlayer")
        ok, msg = self.am.join_queue(char, "1v1_unranked")
        self.assertTrue(ok)
        self.assertIn("1v1_unranked", msg)

    def test_join_queue_invalid(self):
        char = StubCharacter("ArenaPlayer")
        ok, msg = self.am.join_queue(char, "9v9_ranked")
        self.assertFalse(ok)

    def test_match_formation(self):
        chars = [StubCharacter(f"Player{i}") for i in range(4)]
        for char in chars:
            self.am.join_queue(char, "1v1_unranked")

        # Should have formed 2 matches
        self.assertTrue(len(self.am._matches) > 0)

    def test_leave_queue(self):
        char = StubCharacter("ArenaPlayer")
        self.am.join_queue(char, "1v1_unranked")
        ok, msg = self.am.leave_queue(char)
        self.assertTrue(ok)
        self.assertEqual(len(self.am._queues["1v1_unranked"]), 0)

    def test_elo_tracking(self):
        char1 = StubCharacter("EloPlayer1", level=20)
        char2 = StubCharacter("EloPlayer2", level=20)
        from world.pvp_systems import ArenaMatch
        match = ArenaMatch("test_match", [char1], [char2], "1v1", ranked=True)
        match.status = "active"
        match.started_at = time.time()

        self.am._matches["test_match"] = match
        # Set initial ELOs
        self.am._elo_ratings[char1.id] = 1200
        self.am._elo_ratings[char2.id] = 1200

        ok, msg = self.am.report_victory("test_match", "team_a")
        self.assertTrue(ok)
        self.assertGreater(self.am.get_elo(char1), 1200)
        self.assertLess(self.am.get_elo(char2), 1200)


class TestBattlegroundSystem(unittest.TestCase):
    """Test battleground creation and management."""

    def setUp(self):
        from world.pvp_systems import battleground_manager
        self.bm = battleground_manager
        self.bm._battlegrounds.clear()
        self.bm._player_bg.clear()

    def test_create_battleground(self):
        bg, msg = self.bm.create_battleground("ctf")
        self.assertIsNotNone(bg)
        self.assertIn("Capture the Flag", msg)

    def test_create_invalid_bg(self):
        bg, msg = self.bm.create_battleground("invalid_type")
        self.assertIsNone(bg)

    def test_join_battleground(self):
        bg, _ = self.bm.create_battleground("ctf")
        char = StubCharacter("BGPlayer")
        ok, msg = self.bm.join_battleground(char, bg.bg_id, "team_a")
        self.assertTrue(ok)
        self.assertIn(char, bg.team_a)

    def test_battleground_start(self):
        bg, _ = self.bm.create_battleground("faction_war")
        for i in range(6):
            char = StubCharacter(f"Faction{i}")
            team = "team_a" if i < 3 else "team_b"
            self.bm.join_battleground(char, bg.bg_id, team)

        ok, msg = bg.start()
        self.assertTrue(ok)
        self.assertEqual(bg.status, "active")

    def test_capture_flag(self):
        bg, _ = self.bm.create_battleground("ctf")
        bg.start() if len(bg.team_a) > 0 and len(bg.team_b) > 0 else None
        # Manually add players
        bg.team_a = [StubCharacter("A1")]
        bg.team_b = [StubCharacter("B1")]
        won = bg.capture_flag("team_a")
        self.assertEqual(bg.team_a_score, 1)
        self.assertFalse(won)  # Need 3 captures


class TestDuelSystem(unittest.TestCase):
    """Test duel challenges and wagers."""

    def setUp(self):
        from world.pvp_systems import duel_manager
        self.dm = duel_manager
        self.dm._challenges.clear()
        self.dm._player_duel.clear()

    def test_challenge(self):
        challenger = StubCharacter("Challenger")
        target = StubCharacter("Target")
        room = StubRoom()
        challenger.location = room
        target.location = room
        room.contents = [challenger, target]

        ok, msg = self.dm.challenge(challenger, target, wager_gold=100)
        self.assertTrue(ok)
        self.assertIn("challenge", msg.lower())

    def test_accept_duel(self):
        challenger = StubCharacter("Challenger")
        target = StubCharacter("Target")
        room = StubRoom()
        challenger.location = room
        target.location = room
        room.contents = [challenger, target]

        self.dm.challenge(challenger, target, wager_gold=100)
        ok, msg = self.dm.accept(target)
        self.assertTrue(ok)

    def test_duel_wager_resolution(self):
        challenger = StubCharacter("Challenger")
        target = StubCharacter("Target")
        room = StubRoom()
        challenger.location = room
        target.location = room
        room.contents = [challenger, target]

        challenger_before = challenger.attributes["gold"]
        target_before = target.attributes["gold"]

        self.dm.challenge(challenger, target, wager_gold=100)
        self.dm.accept(target)
        ok, msg = self.dm.resolve_duel(challenger, target)
        self.assertTrue(ok)
        # Winner gets 2x wager
        self.assertEqual(challenger.attributes["gold"], challenger_before + 100)


class TestBountySystem(unittest.TestCase):
    """Test bounty board."""

    def setUp(self):
        from world.pvp_systems import bounty_board
        self.bb = bounty_board
        self.bb._bounties.clear()

    def test_place_bounty_insufficient_gold(self):
        placer = StubCharacter("Placer")
        placer.attributes["gold"] = 50
        ok, msg = self.bb.place_bounty(placer, "Target", 100)
        self.assertFalse(ok)

    def test_place_bounty_below_minimum(self):
        placer = StubCharacter("Placer")
        ok, msg = self.bb.place_bounty(placer, "Target", 50)
        self.assertFalse(ok)
        self.assertIn("Minimum", msg)

    def test_cancel_bounty(self):
        # Directly add a bounty then cancel it
        from world.pvp_systems import Bounty
        bounty = Bounty("bounty_test", "Target", "Placer", 200)
        self.bb._bounties["bounty_test"] = bounty
        self.bb._bounty_escrow["bounty_test"] = 200

        placer = StubCharacter("Placer")
        ok, msg = self.bb.cancel_bounty(placer, "bounty_test")
        self.assertTrue(ok)
        self.assertEqual(bounty.status, "expired")


# ===========================================================================
# RAID MECHANICS TESTS (3.3)
# ===========================================================================

class TestRaidMechanics(unittest.TestCase):
    """Test raid boss phases, enrage, and abilities."""

    def setUp(self):
        from world.raid_mechanics import RaidBoss, BossPhase
        self.RaidBoss = RaidBoss
        self.BossPhase = BossPhase

    def test_phase_transition(self):
        boss = self.RaidBoss("test_boss", "Test Boss", 50, 10000, 100, "epic")
        p1 = self.BossPhase("p1", "Phase 1", 100)
        p2 = self.BossPhase("p2", "Phase 2", 50)
        p3 = self.BossPhase("p3", "Phase 3", 25)
        boss.add_phase(p1)
        boss.add_phase(p2)
        boss.add_phase(p3)

        # Start fight at 100% HP
        msg = boss.start_fight()
        self.assertEqual(boss.current_phase_idx, 0)

        # Drop to 40% - should transition to phase 2
        msg = boss.check_phase_transition(40.0)
        self.assertIsNotNone(msg)
        self.assertEqual(boss.current_phase_idx, 1)

        # Drop to 20% - should transition to phase 3
        msg = boss.check_phase_transition(20.0)
        self.assertIsNotNone(msg)
        self.assertEqual(boss.current_phase_idx, 2)

    def test_enrage_timer(self):
        boss = self.RaidBoss("test_boss", "Test Boss", 50, 10000, 100)
        boss.set_enrage_timers(soft=100, hard=200)
        boss.start_fight()

        # Manually set enrage time to trigger hard enrage (past both timers)
        boss.enrage_started_at = time.time() - 300
        msg = boss.check_enrage()
        self.assertIn("FRENZIED", msg.upper())
        self.assertTrue(boss.is_hard_enraged)

    def test_enrage_damage_multiplier(self):
        boss = self.RaidBoss("test_boss", "Test Boss", 50, 10000, 100)
        self.assertEqual(boss.get_enrage_damage_multiplier(), 1.0)

        boss.is_enraged = True
        self.assertGreater(boss.get_enrage_damage_multiplier(), 1.0)

        boss.is_hard_enraged = True
        self.assertGreater(boss.get_enrage_damage_multiplier(), 2.0)

    def test_summon_adds(self):
        boss = self.RaidBoss("test_boss", "Test Boss", 50, 10000, 100)
        adds = boss.summon_adds("Fire Elemental", 3, 35, 5000, 60)
        self.assertEqual(len(adds), 3)
        self.assertEqual(len(boss.get_alive_adds()), 3)

    def test_register_default_raids(self):
        from world.raid_mechanics import register_default_raids, raid_manager
        templates = register_default_raids()
        self.assertGreaterEqual(len(templates), 3)
        self.assertIn("obsidian_citadel", raid_manager._raid_templates)
        self.assertIn("frozen_throne", raid_manager._raid_templates)
        self.assertIn("void_threshold", raid_manager._raid_templates)


class TestDungeonFinder(unittest.TestCase):
    """Test dungeon finder queue."""

    def setUp(self):
        from world.raid_mechanics import raid_manager
        self.rm = raid_manager
        self.rm._dungeon_queue.clear()
        for q in self.rm._group_queue.values():
            q.clear()

    def test_queue_dungeon_valid_role(self):
        char = StubCharacter("QPlayer")
        ok, msg = self.rm.queue_dungeon(char, "dps")
        self.assertTrue(ok)

    def test_queue_dungeon_invalid_role(self):
        char = StubCharacter("QPlayer")
        ok, msg = self.rm.queue_dungeon(char, "gatherer")
        self.assertFalse(ok)

    def test_dequeue(self):
        char = StubCharacter("QPlayer")
        self.rm.queue_dungeon(char, "tank")
        ok, msg = self.rm.dequeue_dungeon(char)
        self.assertTrue(ok)
        self.assertEqual(self.rm.get_queue_status()["tank"], 0)


# ===========================================================================
# WORLD EVENTS TESTS (3.3)
# ===========================================================================

class TestWorldEvents(unittest.TestCase):
    """Test world event system."""

    def setUp(self):
        from world.world_events import world_event_manager
        self.wem = world_event_manager
        self.wem._events.clear()
        self.wem._active_event_types.clear()

    def test_create_event(self):
        event, msg = self.wem.create_event("double_xp")
        self.assertIsNotNone(event)
        self.assertTrue(event.is_active)
        self.assertEqual(event.xp_multiplier, 2.0)

    def test_create_duplicate_event(self):
        self.wem.create_event("double_xp")
        event2, msg = self.wem.create_event("double_xp")
        self.assertIsNone(event2)

    def test_xp_multiplier(self):
        self.wem.create_event("double_xp")
        self.assertEqual(self.wem.get_active_xp_multiplier(), 2.0)

    def test_gold_multiplier(self):
        self.wem.create_event("double_gold")
        self.assertEqual(self.wem.get_active_gold_multiplier(), 2.0)

    def test_cancel_event(self):
        event, _ = self.wem.create_event("double_xp")
        ok, msg = self.wem.cancel_event(event.event_id)
        self.assertTrue(ok)
        self.assertEqual(event.status, "cancelled")

    def test_register_holidays(self):
        from world.world_events import register_default_holidays
        holidays = register_default_holidays()
        self.assertGreaterEqual(len(holidays), 6)


# ===========================================================================
# PET SYSTEM TESTS (3.3)
# ===========================================================================

class TestPetSystem(unittest.TestCase):
    """Test pet/companion system."""

    def setUp(self):
        from world.pet_system import pet_manager
        self.pm = pet_manager
        self.pm._player_pets.clear()
        self.pm._active_pet.clear()

    def test_adopt_pet_success(self):
        char = StubCharacter("PetOwner", level=10)
        ok, msg = self.pm.adopt_pet(char, "cat")
        self.assertTrue(ok)
        pets = self.pm.get_pets(char)
        self.assertEqual(len(pets), 1)
        self.assertEqual(pets[0].name, "Black Cat")

    def test_adopt_pet_level_gate(self):
        char = StubCharacter("PetOwner", level=1)
        ok, msg = self.pm.adopt_pet(char, "dragon_companion")
        self.assertFalse(ok)
        self.assertIn("level", msg.lower())

    def test_adopt_pet_insufficient_gold(self):
        char = StubCharacter("PetOwner", level=50)
        char.attributes["gold"] = 10
        ok, msg = self.pm.adopt_pet(char, "baby_phoenix")
        self.assertFalse(ok)

    def test_pet_leveling(self):
        from world.pet_system import Pet
        pet = Pet("p1", "wolf_companion", "Owner")
        leveled = pet.gain_xp(200)
        self.assertTrue(leveled)
        self.assertEqual(pet.level, 2)

    def test_pet_bonding(self):
        from world.pet_system import Pet
        pet = Pet("p1", "cat", "Owner")
        bonused = pet.gain_bond(60)
        self.assertTrue(bonused)
        self.assertEqual(pet.bond_level, 2)

    def test_pet_combat(self):
        char = StubCharacter("PetOwner", level=20)
        target = StubCharacter("Target", level=20)
        self.pm.adopt_pet(char, "wolf_companion")
        messages = self.pm.pet_combat_tick(char, target)
        # Should produce some combat message
        self.assertGreaterEqual(len(messages), 1)

    def test_pet_release(self):
        char = StubCharacter("PetOwner", level=10)
        self.pm.adopt_pet(char, "cat")
        pet = self.pm.get_pets(char)[0]
        ok, msg = self.pm.release_pet(char, pet.pet_id)
        self.assertTrue(ok)
        self.assertEqual(len(self.pm.get_pets(char)), 0)


# ===========================================================================
# CONTENT DENSITY TESTS (3.4)
# ===========================================================================

class TestQuestExpansion(unittest.TestCase):
    """Test quest count expanded to 50+."""

    @classmethod
    def setUpClass(cls):
        """Configure Django settings for Evennia imports."""
        import os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
        import django
        django.setup()

    def test_quest_count(self):
        from world.quests import register_default_quests, quest_registry
        register_default_quests()
        count = len(quest_registry)
        self.assertGreaterEqual(count, 50, f"Expected >=50 quests, got {count}")

    def test_daily_quests(self):
        from world.quests import register_default_quests, quest_registry
        register_default_quests()
        daily = quest_registry.get_daily_quests()
        self.assertGreaterEqual(len(daily), 4)

    def test_quest_chains(self):
        from world.quests import register_default_quests, quest_registry
        register_default_quests()
        wolf_saga = quest_registry.get_by_chain("wolf_saga")
        self.assertEqual(len(wolf_saga), 3)
        shadow_conspiracy = quest_registry.get_by_chain("shadow_conspiracy")
        self.assertEqual(len(shadow_conspiracy), 3)


class TestSpellExpansion(unittest.TestCase):
    """Test spell count expanded to 60+."""

    @classmethod
    def setUpClass(cls):
        """Configure Django settings for Evennia imports."""
        import os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
        import django
        django.setup()

    def test_spell_count(self):
        import world.spells as spells
        count = len(spells.SPELLS)
        self.assertGreaterEqual(count, 60, f"Expected >=60 spells, got {count}")

    def test_spell_helpers(self):
        import world.spells as spells

        spell = spells.get_spell("Judgment")
        self.assertIsNotNone(spell, "Judgment spell should exist")
        self.assertEqual(spell["level"], 80)

        available = spells.get_spells_for_level(50)
        self.assertGreaterEqual(len(available), 30, f"Expected >=30 spells at level 50, got {len(available)}")


class TestContentExpansion(unittest.TestCase):
    """Test generated items and mobs reach target density."""

    def test_item_generation_count(self):
        from world.content_expansion import generate_all_items
        items = generate_all_items()
        self.assertGreaterEqual(len(items), 200)

    def test_mob_generation_count(self):
        from world.content_expansion import generate_all_mobs
        mobs = generate_all_mobs()
        self.assertGreaterEqual(len(mobs), 150)

    def test_item_scaling(self):
        from world.content_expansion import generate_all_items, _scale_damage, _scale_armor
        items = generate_all_items()
        # Low-tier item should have lower damage than high-tier
        low_sword = items["gen_sword_tier1"]
        high_sword = items["gen_sword_tier7"]
        low_dmg = dict(low_sword["attrs"])["damage"]
        high_dmg = dict(high_sword["attrs"])["damage"]
        self.assertGreater(high_dmg, low_dmg)

    def test_mob_scaling(self):
        from world.content_expansion import generate_all_mobs
        mobs = generate_all_mobs()
        low_mob = mobs["gen_brute_lvl5"]
        high_mob = mobs["gen_brute_lvl80"]
        low_hp = dict(low_mob["attrs"])["hp"]
        high_hp = dict(high_mob["attrs"])["hp"]
        self.assertGreater(high_hp, low_hp)

    def test_named_items_have_rarity(self):
        from world.content_expansion import generate_all_items
        items = generate_all_items()
        # Check some named items exist
        self.assertIn("named_flamebrand", items)
        self.assertIn("named_dragonscale_plate", items)
        # Verify rarity attribute
        flamebrand_attrs = dict(items["named_flamebrand"]["attrs"])
        self.assertIn("rarity", flamebrand_attrs)


# ===========================================================================
# INTEGRATION TEST — Full System Check
# ===========================================================================

class TestIntegrationAllSystems(unittest.TestCase):
    """Verify all new systems can be imported and instantiated."""

    @classmethod
    def setUpClass(cls):
        """Configure Django settings for Evennia imports."""
        import os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
        import django
        django.setup()

    def test_all_imports(self):
        from world.pvp_systems import arena_manager, battleground_manager, duel_manager, bounty_board
        from world.raid_mechanics import RaidBoss, BossPhase, raid_manager
        from world.world_events import WorldEvent, world_event_manager
        from world.pet_system import Pet, pet_manager
        from world.content_expansion import generate_all_items, generate_all_mobs
        from commands.pvp_commands import CmdArenaQueue, CmdBattleground, CmdDuel, CmdBounty
        from commands.raid_commands import CmdRaid, CmdDungeonFinder, CmdWorldEvent, CmdPet
        self.assertTrue(True)

    def test_all_managers_exist(self):
        from world.pvp_systems import arena_manager, battleground_manager, duel_manager, bounty_board
        from world.raid_mechanics import raid_manager
        from world.world_events import world_event_manager
        from world.pet_system import pet_manager
        self.assertIsNotNone(arena_manager)
        self.assertIsNotNone(battleground_manager)
        self.assertIsNotNone(duel_manager)
        self.assertIsNotNone(bounty_board)
        self.assertIsNotNone(raid_manager)
        self.assertIsNotNone(world_event_manager)
        self.assertIsNotNone(pet_manager)


if __name__ == "__main__":
    unittest.main()