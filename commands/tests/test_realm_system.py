"""
Comprehensive Realm System Test Suite for 'rop'
================================================
End-to-end integration tests covering all major gameplay systems:

  PART 1  — Boss Registry & Lair Construction
  PART 2  — Dungeon Expansion Chains
  PART 3  — Zone Tier & Level Scaling
  PART 4  — Character Creation & Faction Alignment
  PART 5  — Combat & Death Mechanics
  PART 6  — PvP, Safe Zones & Warpoints
  PART 7  — Looting, Sacrifice & Auto-Loot
  PART 8  — Banking System
  PART 9  — Quest System
  PART 10 — Leveling & XP
  PART 11 — Weather & Climate
  PART 12 — Equipment, Armor Sets & Stats
  PART 13 — Group & Clan Systems
  PART 14 — Gossip & Broadcast Channels
  PART 15 — Announcements & MOTD
  PART 16 — Backup System
  PART 17 — Rules, Help & Prompt
  PART 18 — Boss Loot Tables (Rarity System)
  PART 19 — Movement Commands
  PART 20 — Spell System

Run with:
    evennia test commands.tests.test_realm_system
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import (
    DefaultRoom,
    DefaultCharacter,
    DefaultObject,
    DefaultExit,
)
from evennia import create_object


# ============================================================================
# PART 1 — Boss Registry & Lair Construction
# ============================================================================

class TestBossRegistry(BaseEvenniaTest):
    """Verify the 30-boss database integrity and spawner logic."""

    def test_registry_has_30_bosses(self):
        from world.boss_registry import BOSS_REGISTRY
        self.assertEqual(len(BOSS_REGISTRY), 30,
                         "BOSS_REGISTRY must contain exactly 30 bosses")

    def test_evil_faction_bosses_count(self):
        from world.boss_registry import BOSS_REGISTRY
        evil = [b for b in BOSS_REGISTRY.values()
                if b["faction"] == "Gorgoroth Horde"]
        self.assertEqual(len(evil), 15,
                         "Must have exactly 15 Gorgoroth Horde evil bosses")

    def test_good_faction_bosses_count(self):
        from world.boss_registry import BOSS_REGISTRY
        good = [b for b in BOSS_REGISTRY.values()
                if b["faction"] == "Aethelgard Alliance"]
        self.assertEqual(len(good), 15,
                         "Must have exactly 15 Aethelgard Alliance good bosses")

    def test_boss_levels_all_in_range(self):
        from world.boss_registry import BOSS_REGISTRY
        for boss_id, data in BOSS_REGISTRY.items():
            self.assertGreaterEqual(data["level"], 8,
                                     f"{boss_id}: level must be >= 8")
            self.assertLessEqual(data["level"], 50,
                                 f"{boss_id}: level must be <= 50")

    def test_boss_hp_scales_with_level(self):
        from world.boss_registry import BOSS_REGISTRY
        for boss_id, data in BOSS_REGISTRY.items():
            min_expected = data["level"] * 80
            max_expected = data["level"] * 300
            self.assertGreaterEqual(data["hp"], min_expected,
                                    f"{boss_id}: HP too low for level {data['level']}")
            self.assertLessEqual(data["hp"], max_expected,
                                 f"{boss_id}: HP too high for level {data['level']}")

    def test_boss_max_damage_scales_with_level(self):
        from world.boss_registry import BOSS_REGISTRY
        for boss_id, data in BOSS_REGISTRY.items():
            self.assertGreaterEqual(data["max_damage"], data["level"] * 2,
                                     f"{boss_id}: max_damage too low")
            self.assertLessEqual(data["max_damage"], data["level"] * 5,
                                 f"{boss_id}: max_damage too high")

    def test_all_bosses_have_rare_drops(self):
        from world.boss_registry import BOSS_REGISTRY
        for boss_id, data in BOSS_REGISTRY.items():
            self.assertIsNotNone(data.get("rare_drop"),
                                 f"{boss_id}: missing rare_drop")
            self.assertNotEqual(data["rare_drop"], "",
                                f"{boss_id}: rare_drop is empty")

    def test_all_bosses_have_announce_strings(self):
        from world.boss_registry import BOSS_REGISTRY
        for boss_id, data in BOSS_REGISTRY.items():
            self.assertIn("{killer}", data.get("announce", ""),
                          f"{boss_id}: announce missing {{killer}} placeholder")

    def test_boss_registry_keys_match_room_lookup(self):
        from world.boss_registry import BOSS_REGISTRY, BOSS_ROOM_LOOKUP
        for boss_id in BOSS_REGISTRY:
            self.assertIn(boss_id, BOSS_ROOM_LOOKUP,
                          f"{boss_id}: missing from BOSS_ROOM_LOOKUP")

    def test_boss_room_lookup_has_30_entries(self):
        from world.boss_registry import BOSS_ROOM_LOOKUP
        self.assertEqual(len(BOSS_ROOM_LOOKUP), 30)


class TestBossLairConstruction(BaseEvenniaTest):
    """Verify boss lair room creation via build_boss_lairs()."""

    def test_boss_lairs_builds_30_rooms(self):
        from world.boss_zones import build_boss_lairs
        lairs = build_boss_lairs()
        self.assertEqual(len(lairs), 30)
        # Cleanup
        for room in lairs.values():
            room.delete()

    def test_boss_lair_rooms_have_boss_lair_tag(self):
        from world.boss_zones import build_boss_lairs
        lairs = build_boss_lairs()
        for boss_id, room in lairs.items():
            tag_keys = room.tags.get(category="room_type", return_objs=False)
            self.assertIn("boss_lair", tag_keys,
                          f"{boss_id}: room missing boss_lair tag")
        for room in lairs.values():
            room.delete()

    def test_boss_lair_rooms_have_boss_id_tag(self):
        from world.boss_zones import build_boss_lairs
        lairs = build_boss_lairs()
        for boss_id, room in lairs.items():
            tag_keys = room.tags.get(category="boss_id", return_objs=False)
            self.assertIn(boss_id, tag_keys,
                          f"{boss_id}: room missing boss_id tag")
        for room in lairs.values():
            room.delete()

    def test_boss_lair_rooms_have_descriptions(self):
        from world.boss_zones import build_boss_lairs
        lairs = build_boss_lairs()
        for boss_id, room in lairs.items():
            self.assertIsNotNone(room.db.desc,
                                 f"{boss_id}: room missing description")
            self.assertNotEqual(room.db.desc, "",
                                f"{boss_id}: room description is empty")
        for room in lairs.values():
            room.delete()

    def test_boss_lair_rooms_flagged_is_boss_lair(self):
        from world.boss_zones import build_boss_lairs
        lairs = build_boss_lairs()
        for boss_id, room in lairs.items():
            self.assertTrue(room.db.is_boss_lair,
                            f"{boss_id}: is_boss_lair flag not set")
        for room in lairs.values():
            room.delete()


# ============================================================================
# PART 2 — Dungeon Expansion Chains
# ============================================================================

class TestDungeonExpansions(BaseEvenniaTest):
    """Verify the 30 dungeon expansion chain builder."""

    def test_expansions_builds_30_dungeons(self):
        from world.boss_expansions import build_dungeon_expansions
        expansions = build_dungeon_expansions()
        self.assertEqual(len(expansions), 30)
        for rooms in expansions.values():
            for room in rooms:
                room.delete()

    def test_dungeon_chains_have_4_to_10_rooms(self):
        from world.boss_expansions import build_dungeon_expansions
        expansions = build_dungeon_expansions()
        for dungeon_id, rooms in expansions.items():
            self.assertGreaterEqual(len(rooms), 4,
                                    f"{dungeon_id}: fewer than 4 rooms")
            self.assertLessEqual(len(rooms), 10,
                                 f"{dungeon_id}: more than 10 rooms")
        for rooms in expansions.values():
            for room in rooms:
                room.delete()

    def test_dungeon_rooms_have_dungeon_tags(self):
        from world.boss_expansions import build_dungeon_expansions
        expansions = build_dungeon_expansions()
        for dungeon_id, rooms in expansions.items():
            for room in rooms:
                tag_keys = room.tags.get(category="room_type", return_objs=False)
                self.assertIn("dungeon_expansion", tag_keys)
        for rooms in expansions.values():
            for room in rooms:
                room.delete()

    def test_dungeon_final_room_has_boss_entrance_tag(self):
        from world.boss_expansions import build_dungeon_expansions
        expansions = build_dungeon_expansions()
        for dungeon_id, rooms in expansions.items():
            final_room = rooms[-1]
            tags = final_room.tags.get(category="boss_entrance", return_objs=False)
            self.assertTrue(tags,
                            f"{dungeon_id}: final room missing boss_entrance tag")
        for rooms in expansions.values():
            for room in rooms:
                room.delete()

    def test_dungeon_first_room_has_entrance_tag(self):
        from world.boss_expansions import build_dungeon_expansions
        expansions = build_dungeon_expansions()
        for dungeon_id, rooms in expansions.items():
            tag_keys = rooms[0].tags.get(category="room_type", return_objs=False)
            self.assertIn("dungeon_entrance", tag_keys,
                          f"{dungeon_id}: first room missing dungeon_entrance tag")
        for rooms in expansions.values():
            for room in rooms:
                room.delete()

    def test_dungeon_rooms_have_descriptions(self):
        from world.boss_expansions import build_dungeon_expansions
        expansions = build_dungeon_expansions()
        for dungeon_id, rooms in expansions.items():
            for i, room in enumerate(rooms):
                self.assertIsNotNone(room.db.desc,
                                     f"{dungeon_id} room {i}: missing desc")
                self.assertNotEqual(room.db.desc, "",
                                    f"{dungeon_id} room {i}: empty desc")
        for rooms in expansions.values():
            for room in rooms:
                room.delete()

    def test_evil_and_good_dungeon_counts(self):
        from world.boss_expansions import DUNGEON_EXPANSIONS
        evil = [d for d in DUNGEON_EXPANSIONS if d[2] == "evil"]
        good = [d for d in DUNGEON_EXPANSIONS if d[2] == "good"]
        self.assertEqual(len(evil), 15)
        self.assertEqual(len(good), 15)


# ============================================================================
# PART 3 — Zone Tier & Level Scaling
# ============================================================================

class TestZoneLevels(BaseEvenniaTest):
    """Verify zone level tier system."""

    def test_zone_tier_map_has_all_zones(self):
        from world.zone_levels import (
            TIER_1_ZONES, TIER_2_ZONES, TIER_3_ZONES,
            TIER_4_ZONES, TIER_5_ZONES
        )
        total = (len(TIER_1_ZONES) + len(TIER_2_ZONES) +
                 len(TIER_3_ZONES) + len(TIER_4_ZONES) +
                 len(TIER_5_ZONES))
        self.assertGreater(total, 20, "Expected 20+ zones across all tiers")

    def test_tier_1_zones_levels_1_to_5(self):
        from world.zone_levels import get_zone_level_range, TIER_1_ZONES
        for zone in TIER_1_ZONES:
            lmin, lmax = get_zone_level_range(zone)
            self.assertEqual(lmin, 1)
            self.assertEqual(lmax, 5)

    def test_tier_5_zones_levels_61_to_80(self):
        from world.zone_levels import get_zone_level_range, TIER_5_ZONES
        for zone in TIER_5_ZONES:
            lmin, lmax = get_zone_level_range(zone)
            self.assertEqual(lmin, 61)
            self.assertEqual(lmax, 80)

    def test_unknown_zone_falls_back_to_1_5(self):
        from world.zone_levels import get_zone_level_range
        lmin, lmax = get_zone_level_range("Atlantis")
        self.assertEqual(lmin, 1)
        self.assertEqual(lmax, 5)

    def test_get_zone_tier_for_name_works(self):
        from world.zone_levels import get_zone_tier_for_name
        info = get_zone_tier_for_name("Emerald Forest")
        self.assertIsNotNone(info)
        tier, lmin, lmax, danger = info
        self.assertEqual(tier, 2)
        self.assertEqual(danger, "caution")

    def test_danger_levels_are_valid(self):
        from world.zone_levels import ZONE_TIER_MAP
        valid_dangers = {"safe", "caution", "danger", "deadly"}
        for zone, (tier, lmin, lmax, danger) in ZONE_TIER_MAP.items():
            self.assertIn(danger, valid_dangers,
                          f"{zone}: invalid danger level '{danger}'")

    def test_all_tiers_have_valid_level_ranges(self):
        from world.zone_levels import ZONE_TIER_MAP
        for zone, (tier, lmin, lmax, danger) in ZONE_TIER_MAP.items():
            self.assertGreaterEqual(lmin, 1, f"{zone}: min level too low")
            self.assertLessEqual(lmax, 80, f"{zone}: max level too high")
            self.assertLessEqual(lmin, lmax,
                                 f"{zone}: min > max ({lmin} > {lmax})")

    def test_scale_mob_level_returns_reasonable_values(self):
        from world.zone_levels import scale_mob_level
        result = scale_mob_level(1, 5, 3)
        self.assertGreaterEqual(result, 1)
        self.assertLessEqual(result, 5)

    def test_should_be_aggressive_returns_bool(self):
        from world.zone_levels import should_be_aggressive
        result = should_be_aggressive("danger")
        self.assertIsInstance(result, bool)


# ============================================================================
# PART 4 — Character Creation & Faction Alignment
# ============================================================================

class TestCharacterCreation(BaseEvenniaTest):
    """Verify chargen and faction alignment."""

    def test_good_races_exist(self):
        from world.rules import RACES
        good = [r for r, data in RACES.items() if data.get("alignment") == "Good"]
        self.assertGreaterEqual(len(good), 1, "Need at least 1 Good race")

    def test_evil_races_exist(self):
        from world.rules import RACES
        evil = [r for r, data in RACES.items() if data.get("alignment") == "Evil"]
        self.assertGreaterEqual(len(evil), 1, "Need at least 1 Evil race")

    def test_16_total_races(self):
        from world.rules import RACES
        self.assertEqual(len(RACES), 16, "Expected 16 total races (8 Good / 8 Evil)")

    def test_classes_exist(self):
        from world.rules import CLASSES
        self.assertGreaterEqual(len(CLASSES), 1, "Need at least 1 class")

    def test_alignment_attribute_persists(self):
        char = create_object(DefaultCharacter, key="AlignTest")
        char.attributes.add("alignment", "Good")
        self.assertEqual(char.attributes.get("alignment"), "Good")
        char.attributes.add("alignment", "Evil")
        self.assertEqual(char.attributes.get("alignment"), "Evil")
        char.delete()

    def test_faction_defaults_to_none(self):
        char = create_object(DefaultCharacter, key="NoFaction")
        self.assertIsNone(char.attributes.get("faction", default=None))
        char.delete()

    def test_start_room_keys_defined(self):
        from typeclasses.charcreate import (
            GOOD_START_ROOM_KEY,
            EVIL_START_ROOM_KEY,
        )
        self.assertEqual(GOOD_START_ROOM_KEY, "Aethelgard - Shrine of Light")
        self.assertEqual(EVIL_START_ROOM_KEY, "Gorgoroth - Dark Temple")

    def test_set_alignment_helper(self):
        from typeclasses.charcreate import _set_alignment

        class FakeCaller:
            pass

        caller = FakeCaller()
        caller.ndb = type("_evmenu", (), {
            "_evmenu": type("m", (), {})()
        })()

        _set_alignment(caller, "", align="Good")
        self.assertEqual(caller.ndb._evmenu.c_align, "Good")

        _set_alignment(caller, "", align="Evil")
        self.assertEqual(caller.ndb._evmenu.c_align, "Evil")


# ============================================================================
# PART 5 — Combat & Death Mechanics
# ============================================================================

class TestCombatSystem(BaseEvenniaTest):
    """Verify combat state machine, damage, and death."""

    def test_combat_state_enum_exists(self):
        from world.combat_state import CombatState
        self.assertTrue(hasattr(CombatState, "IDLE"))
        self.assertTrue(hasattr(CombatState, "FIGHTING"))
        self.assertTrue(hasattr(CombatState, "DEAD"))

    def test_damage_calculator_exists(self):
        from world.combat_state import DamageCalculator
        calc = DamageCalculator()
        self.assertIsNotNone(calc)

    def test_turn_resolver_exists(self):
        from world.combat_state import TurnResolver
        res = TurnResolver()
        self.assertIsNotNone(res)

    def test_regeneration_constants(self):
        from world.combat_state import (
            HP_REGEN_STANDING,
            HP_REGEN_RESTING,
        )
        self.assertGreater(HP_REGEN_STANDING, 0)
        self.assertGreater(HP_REGEN_RESTING, HP_REGEN_STANDING)

    def test_combat_engine_init(self):
        from world.combat_state import CombatEngine
        engine = CombatEngine()
        self.assertIsNotNone(engine)

    def test_corpse_creation_function_exists(self):
        from world.combat import _create_npc_corpse
        self.assertTrue(callable(_create_npc_corpse))

    def test_auto_loot_function_exists(self):
        from world.combat import _auto_loot_corpse
        self.assertTrue(callable(_auto_loot_corpse))

    def test_auto_sac_function_exists(self):
        from world.combat import _auto_sac_corpse
        self.assertTrue(callable(_auto_sac_corpse))


# ============================================================================
# PART 6 — PvP, Safe Zones & Warpoints
# ============================================================================

class TestPvPAndSafeZones(BaseEvenniaTest):
    """Verify PvP mechanics and safe zone protection."""

    def test_safe_zone_flag_default_false(self):
        room = create_object(DefaultRoom, key="TempSafe")
        self.assertFalse(room.db.safe_zone)
        room.delete()

    def test_safe_zone_flag_set(self):
        room = create_object(DefaultRoom, key="SafeRoom")
        room.db.safe_zone = True
        self.assertTrue(room.db.safe_zone)
        room.delete()

    def test_no_pvp_in_safe_zone(self):
        from commands.pvp import is_safe_zone
        room = create_object(DefaultRoom, key="Sanctuary")
        room.db.safe_zone = True
        self.assertTrue(is_safe_zone(room))
        room.delete()

    def test_pvp_allowed_in_wild_zone(self):
        from commands.pvp import is_safe_zone
        room = create_object(DefaultRoom, key="Wilderness")
        room.db.safe_zone = False
        self.assertFalse(is_safe_zone(room))
        room.delete()

    def test_warpoints_attribute_exists(self):
        char = create_object(DefaultCharacter, key="Warrior")
        char.attributes.add("warpoints", 0)
        self.assertEqual(char.attributes.get("warpoints"), 0)
        char.delete()

    def test_warpoints_increment(self):
        char = create_object(DefaultCharacter, key="Warrior")
        char.attributes.add("warpoints", 5)
        char.attributes.add("warpoints", 10)
        self.assertEqual(char.attributes.get("warpoints"), 10)
        char.delete()


# ============================================================================
# PART 7 — Looting, Sacrifice & Auto-Loot
# ============================================================================

class TestLootSystem(BaseEvenniaTest):
    """Verify loot and sacrifice mechanics."""

    def test_calculate_sac_reward_returns_tuple(self):
        from commands.loot import calculate_sac_reward
        result = calculate_sac_reward(5)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_sac_reward_scales_with_level(self):
        from commands.loot import calculate_sac_reward
        _, gold1 = calculate_sac_reward(1)
        _, gold10 = calculate_sac_reward(10)
        self.assertGreaterEqual(gold10, gold1,
                                "Sacrifice gold should scale with level")

    def test_corpse_creation(self):
        from commands.loot import _make_corpse
        room = create_object(DefaultRoom, key="LootRoom")
        corpse = _make_corpse("Goblin", room, npc_level=3, money=15)
        self.assertIsNotNone(corpse)
        self.assertIn("corpse", corpse.key.lower())
        self.assertTrue(corpse.attributes.get("is_corpse"))
        self.assertEqual(corpse.attributes.get("corpse_npc_level"), 3)
        self.assertEqual(corpse.attributes.get("money"), 15)
        corpse.delete()
        room.delete()

    def test_autoloot_command_exists(self):
        from commands.loot import CmdAutoLoot
        self.assertTrue(issubclass(CmdAutoLoot, object))

    def test_autosac_command_exists(self):
        from commands.loot import CmdAutoSac
        self.assertTrue(issubclass(CmdAutoSac, object))

    def test_loot_command_exists(self):
        from commands.loot import CmdLoot
        self.assertTrue(issubclass(CmdLoot, object))

    def test_sacrifice_command_exists(self):
        from commands.loot import CmdSacrifice
        self.assertTrue(issubclass(CmdSacrifice, object))


# ============================================================================
# PART 8 — Banking System
# ============================================================================

class TestBankingSystem(BaseEvenniaTest):
    """Verify bank deposit, withdraw, and balance."""

    def test_bank_teller_detection(self):
        room = create_object(DefaultRoom, key="Bank")
        teller = create_object(
            DefaultObject,
            key="Gringotts Teller",
            location=room,
            attributes=[("is_bank_teller", True)],
        )
        self.assertTrue(teller.attributes.get("is_bank_teller"))
        teller.delete()
        room.delete()

    def test_bank_deposit_command_exists(self):
        from commands.bank import CmdDeposit
        self.assertTrue(issubclass(CmdDeposit, object))

    def test_bank_withdraw_command_exists(self):
        from commands.bank import CmdWithdraw
        self.assertTrue(issubclass(CmdWithdraw, object))

    def test_bank_balance_command_exists(self):
        from commands.bank import CmdBalance
        self.assertTrue(issubclass(CmdBalance, object))

    def test_bank_gold_stored_in_attribute(self):
        char = create_object(DefaultCharacter, key="Banker")
        char.attributes.add("bank_gold", 500)
        self.assertEqual(char.attributes.get("bank_gold"), 500)
        char.delete()

    def test_bank_gold_independent_of_money(self):
        char = create_object(DefaultCharacter, key="Banker")
        char.attributes.add("money", 100)
        char.attributes.add("bank_gold", 1000)
        self.assertEqual(char.attributes.get("money"), 100)
        self.assertEqual(char.attributes.get("bank_gold"), 1000)
        char.delete()

    def test_deposit_transfers_money_to_bank(self):
        from commands.bank import CmdDeposit
        room = create_object(DefaultRoom, key="Bank")
        teller = create_object(
            DefaultObject,
            key="Bank Teller",
            location=room,
            attributes=[("is_bank_teller", True)],
        )
        char = create_object(DefaultCharacter, key="Banker")
        char.location = room
        char.attributes.add("money", 500)
        char.attributes.add("bank_gold", 0)

        cmd = CmdDeposit()
        cmd.caller = char
        cmd.args = "200"
        cmd.func()

        self.assertEqual(char.attributes.get("money"), 300)
        self.assertEqual(char.attributes.get("bank_gold"), 200)

        char.delete()
        teller.delete()
        room.delete()

    def test_withdraw_transfers_bank_to_money(self):
        from commands.bank import CmdWithdraw
        room = create_object(DefaultRoom, key="Bank")
        teller = create_object(
            DefaultObject,
            key="Bank Teller",
            location=room,
            attributes=[("is_bank_teller", True)],
        )
        char = create_object(DefaultCharacter, key="Banker")
        char.location = room
        char.attributes.add("money", 0)
        char.attributes.add("bank_gold", 1000)

        cmd = CmdWithdraw()
        cmd.caller = char
        cmd.args = "300"
        cmd.func()

        self.assertEqual(char.attributes.get("money"), 300)
        self.assertEqual(char.attributes.get("bank_gold"), 700)

        char.delete()
        teller.delete()
        room.delete()

    def test_withdraw_insufficient_funds(self):
        from commands.bank import CmdWithdraw
        room = create_object(DefaultRoom, key="Bank")
        teller = create_object(
            DefaultObject,
            key="Bank Teller",
            location=room,
            attributes=[("is_bank_teller", True)],
        )
        char = create_object(DefaultCharacter, key="Banker")
        char.location = room
        char.attributes.add("money", 0)
        char.attributes.add("bank_gold", 50)

        cmd = CmdWithdraw()
        cmd.caller = char
        cmd.args = "200"
        cmd.func()

        self.assertEqual(char.attributes.get("money"), 0)
        self.assertEqual(char.attributes.get("bank_gold"), 50)

        char.delete()
        teller.delete()
        room.delete()


# ============================================================================
# PART 9 — Quest System
# ============================================================================

class TestQuestSystem(BaseEvenniaTest):
    """Verify quest definitions, registry, and lifecycle."""

    def test_quest_registry_has_quests(self):
        from world.quests import quest_registry
        self.assertGreater(len(quest_registry), 0,
                           "Quest registry should have at least 1 quest")

    def test_quest_definition_creation(self):
        from world.quests import QuestDefinition
        q = QuestDefinition(
            id="test_quest",
            name="Test Quest",
            description="A test.",
            quest_type="kill",
            target_key="goblin",
            target_count=5,
            rewards={"xp": 100, "gold": 50},
            giver_npc_key="Test Giver",
            level_required=1,
        )
        self.assertEqual(q.id, "test_quest")
        self.assertEqual(q.name, "Test Quest")
        self.assertEqual(q.quest_type, "kill")
        self.assertEqual(q.target_count, 5)

    def test_active_quest_creation(self):
        from world.quests import ActiveQuest
        aq = ActiveQuest(quest_id="test_quest", quest_name="Test")
        self.assertEqual(aq.quest_id, "test_quest")
        self.assertEqual(aq.progress, 0)
        self.assertFalse(aq.completed)

    def test_active_quest_progress(self):
        from world.quests import ActiveQuest
        aq = ActiveQuest(quest_id="test_quest", quest_name="Test",
                         target_count=5)
        aq.advance(3)
        self.assertEqual(aq.progress, 3)
        self.assertFalse(aq.completed)
        aq.advance(2)
        self.assertEqual(aq.progress, 5)
        self.assertTrue(aq.completed)

    def test_quest_handler_attach_to_character(self):
        from world.quests import QuestHandler
        char = create_object(DefaultCharacter, key="Quester")
        handler = QuestHandler(char)
        self.assertEqual(handler.owner, char)
        char.delete()

    def test_quest_command_exists(self):
        from commands.quest import CmdQuest
        self.assertTrue(issubclass(CmdQuest, object))

    def test_register_default_quests_function_exists(self):
        from world.quests import register_default_quests
        self.assertTrue(callable(register_default_quests))


# ============================================================================
# PART 10 — Leveling & XP
# ============================================================================

class TestLevelingXp(BaseEvenniaTest):
    """Verify XP formula and level-up mechanics."""

    def test_xp_to_level_formula(self):
        from world.rules import xp_to_level
        self.assertEqual(xp_to_level(1), 1000)
        self.assertEqual(xp_to_level(5), 5000)
        self.assertEqual(xp_to_level(10), 10000)
        self.assertEqual(xp_to_level(80), 80000)

    def test_xp_to_level_increasing(self):
        from world.rules import xp_to_level
        for level in range(1, 80):
            self.assertGreater(xp_to_level(level + 1), xp_to_level(level),
                               f"XP requirement should increase at level {level}")

    def test_stats_on_level_up_returns_all_six(self):
        from world.rules import stats_on_level_up
        bonuses = stats_on_level_up()
        expected = {"str": 1, "dex": 1, "con": 1, "int": 1, "wis": 1, "cha": 1}
        self.assertEqual(bonuses, expected)

    def test_character_level_defaults(self):
        char = create_object(DefaultCharacter, key="Noob")
        self.assertIsNone(char.attributes.get("level", default=None))
        char.delete()

    def test_character_level_and_xp_persistence(self):
        char = create_object(DefaultCharacter, key="Hero")
        char.attributes.add("level", 5)
        char.attributes.add("xp", 4500)
        self.assertEqual(char.attributes.get("level"), 5)
        self.assertEqual(char.attributes.get("xp"), 4500)
        char.delete()

    def test_level_up_thresholds(self):
        from world.rules import xp_to_level
        # Level 1 -> 2 needs 1000 XP
        # Level 5 -> 6 needs 5000 XP
        self.assertEqual(xp_to_level(1), 1000)
        self.assertEqual(xp_to_level(5), 5000)


# ============================================================================
# PART 11 — Weather & Climate
# ============================================================================

class TestWeatherSystem(BaseEvenniaTest):
    """Verify weather engine, climates, and formatting."""

    def test_climate_detection(self):
        from world.weather import get_climate
        self.assertEqual(get_climate("Emerald Forest"), "temperate")
        self.assertEqual(get_climate("Scorched Dunes"), "desert")
        self.assertEqual(get_climate("Highland Pass"), "cold")
        self.assertEqual(get_climate("Blackfen Marsh"), "wet")
        self.assertEqual(get_climate("Unknown Zone"), "temperate")

    def test_pick_weather_returns_valid_state(self):
        from world.weather import pick_weather, WEATHER_STATES
        import random
        rng = random.Random(42)
        for _ in range(50):
            state = pick_weather("Emerald Forest", rng)
            self.assertIn(state, WEATHER_STATES)

    def test_weather_exempt_indoor(self):
        from world.weather import is_weather_exempt
        room = create_object(DefaultRoom, key="Indoor")
        room.attributes.add("indoor", True)
        self.assertTrue(is_weather_exempt(room))
        room.delete()

    def test_weather_exempt_safe_zone(self):
        from world.weather import is_weather_exempt
        room = create_object(DefaultRoom, key="Safe")
        room.db.safe_zone = True
        self.assertTrue(is_weather_exempt(room))
        room.delete()

    def test_weather_not_exempt_outdoor(self):
        from world.weather import is_weather_exempt
        room = create_object(DefaultRoom, key="Forest")
        self.assertFalse(is_weather_exempt(room))
        room.delete()

    def test_format_weather_line_has_content(self):
        from world.weather import format_weather_line
        room = create_object(DefaultRoom, key="Test Weather")
        line = format_weather_line(room)
        self.assertIn("The sky is", line)
        room.delete()

    def test_format_weather_short_has_ansi(self):
        from world.weather import format_weather_short
        room = create_object(DefaultRoom, key="Test Weather")
        short = format_weather_short(room)
        self.assertIn("|", short)
        self.assertIn("[", short)
        room.delete()

    def test_weather_states_is_dict(self):
        from world.weather import WEATHER_STATES
        self.assertIsInstance(WEATHER_STATES, dict)
        self.assertGreater(len(WEATHER_STATES), 0)

    def test_climates_is_dict(self):
        from world.weather import CLIMATES
        self.assertIsInstance(CLIMATES, dict)
        self.assertGreater(len(CLIMATES), 0)


# ============================================================================
# PART 12 — Equipment, Armor Sets & Stats
# ============================================================================

class TestEquipmentAndStats(BaseEvenniaTest):
    """Verify equipment slots, armor sets, and stat display."""

    def test_armor_sets_exist(self):
        from world.armor_sets import ARMOR_SETS
        self.assertIsInstance(ARMOR_SETS, dict)
        self.assertGreater(len(ARMOR_SETS), 0)

    def test_equipment_slots_defined(self):
        char = create_object(DefaultCharacter, key="Geared")
        # Common equipment slots
        slots = ["head", "torso", "legs", "feet", "main_hand", "off_hand"]
        for slot in slots:
            char.attributes.add(f"equip_{slot}", None)
        for slot in slots:
            self.assertIsNone(char.attributes.get(f"equip_{slot}"))
        char.delete()

    def test_stats_display(self):
        from commands.stats import CmdStats
        self.assertTrue(issubclass(CmdStats, object))

    def test_generate_stats_function_exists(self):
        from generate_stats import generate_stats
        self.assertTrue(callable(generate_stats))

    def test_character_core_stats(self):
        char = create_object(DefaultCharacter, key="StatTest")
        stats = {"str": 10, "dex": 12, "con": 14, "int": 16, "wis": 13, "cha": 8}
        char.attributes.add("stats", stats)
        stored = char.attributes.get("stats")
        self.assertEqual(stored["str"], 10)
        self.assertEqual(stored["int"], 16)
        char.delete()


# ============================================================================
# PART 13 — Group & Clan Systems
# ============================================================================

class TestGroupAndClan(BaseEvenniaTest):
    """Verify group and clan command existence."""

    def test_group_command_exists(self):
        from commands.group import CmdGroup
        self.assertTrue(issubclass(CmdGroup, object))

    def test_clan_command_exists(self):
        from commands.clan import CmdClan
        self.assertTrue(issubclass(CmdClan, object))

    def test_group_creation(self):
        from commands.group import CmdGroupCreate
        self.assertTrue(issubclass(CmdGroupCreate, object))

    def test_group_invite(self):
        from commands.group import CmdGroupInvite
        self.assertTrue(issubclass(CmdGroupInvite, object))


# ============================================================================
# PART 14 — Gossip & Broadcast Channels
# ============================================================================

class TestChannels(BaseEvenniaTest):
    """Verify gossip and broadcast command existence."""

    def test_gossip_command_exists(self):
        from commands.gossip import CmdGossip
        self.assertTrue(issubclass(CmdGossip, object))

    def test_broadcast_command_exists(self):
        from commands.broadcast import CmdBroadcast
        self.assertTrue(issubclass(CmdBroadcast, object))

    def test_ooc_command_exists(self):
        from commands.gossip import CmdOOC
        self.assertTrue(issubclass(CmdOOC, object))


# ============================================================================
# PART 15 — Announcements & MOTD
# ============================================================================

class TestAnnouncementsAndMOTD(BaseEvenniaTest):
    """Verify announcements and MOTD systems."""

    def test_announcements_module_exists(self):
        from world import announcements
        self.assertIsNotNone(announcements)

    def test_motd_module_exists(self):
        from world import motd
        self.assertIsNotNone(motd)

    def test_announcement_command_exists(self):
        from commands.announcements import CmdAnnounce
        self.assertTrue(issubclass(CmdAnnounce, object))


# ============================================================================
# PART 16 — Backup System
# ============================================================================

class TestBackupSystem(BaseEvenniaTest):
    """Verify backup command and world backup module."""

    def test_backup_command_exists(self):
        from commands.backup import CmdBackup
        self.assertTrue(issubclass(CmdBackup, object))

    def test_world_backup_module_exists(self):
        from world import backup
        self.assertIsNotNone(backup)

    def test_backup_function_exists(self):
        from world.backup import perform_backup
        self.assertTrue(callable(perform_backup))


# ============================================================================
# PART 17 — Rules, Help & Prompt
# ============================================================================

class TestRulesAndHelp(BaseEvenniaTest):
    """Verify rules text, help entries, and prompt system."""

    def test_rules_text_exists(self):
        from world.rules import RULES_TEXT
        self.assertIsInstance(RULES_TEXT, str)
        self.assertGreater(len(RULES_TEXT), 100)

    def test_rules_contains_conduct_section(self):
        from world.rules import RULES_TEXT
        self.assertIn("GENERAL CONDUCT", RULES_TEXT)

    def test_help_entries_exist(self):
        from world.help_entries import HELP_ENTRIES
        self.assertIsInstance(HELP_ENTRIES, list)
        self.assertGreater(len(HELP_ENTRIES), 0)

    def test_rules_command_exists(self):
        from commands.rules import CmdRules
        self.assertTrue(issubclass(CmdRules, object))

    def test_prompt_display(self):
        from commands.prompt import CmdPrompt
        self.assertTrue(issubclass(CmdPrompt, object))


# ============================================================================
# PART 18 — Boss Loot Tables (Rarity System)
# ============================================================================

class TestBossLootRarity(BaseEvenniaTest):
    """Verify boss loot table, rarity tiers, and drop mechanics."""

    def test_rarity_constants_exist(self):
        from world.boss_loot import (
            RARITY_COMMON, RARITY_UNCOMMON, RARITY_RARE,
            RARITY_EPIC, RARITY_LEGENDARY,
        )
        self.assertEqual(RARITY_COMMON, "common")
        self.assertEqual(RARITY_RARE, "rare")
        self.assertEqual(RARITY_EPIC, "epic")
        self.assertEqual(RARITY_LEGENDARY, "legendary")

    def test_boss_only_rarities(self):
        from world.boss_loot import BOSS_ONLY_RARITIES
        self.assertIn("rare", BOSS_ONLY_RARITIES)
        self.assertIn("epic", BOSS_ONLY_RARITIES)
        self.assertIn("legendary", BOSS_ONLY_RARITIES)

    def test_rarity_colors_exist(self):
        from world.boss_loot import RARITY_COLORS
        self.assertIn("common", RARITY_COLORS)
        self.assertIn("legendary", RARITY_COLORS)

    def test_loot_entry_creation(self):
        from world.boss_loot import LootEntry, RARITY_LEGENDARY
        entry = LootEntry("Test Sword", rarity=RARITY_LEGENDARY, drop_chance=5)
        self.assertEqual(entry.item_key, "Test Sword")
        self.assertEqual(entry.rarity, RARITY_LEGENDARY)
        self.assertEqual(entry.drop_chance, 5)

    def test_loot_entry_drop_chance_clamped(self):
        from world.boss_loot import LootEntry
        entry = LootEntry("Test", drop_chance=150)
        self.assertEqual(entry.drop_chance, 100)
        entry2 = LootEntry("Test2", drop_chance=-5)
        self.assertEqual(entry2.drop_chance, 1)

    def test_boss_loot_table_creation(self):
        from world.boss_loot import BossLootTable, RARITY_EPIC
        table = BossLootTable("Test Boss")
        table.add_item("Epic Axe", RARITY_EPIC, 10)
        self.assertEqual(len(table.entries), 1)
        self.assertEqual(table.entries[0].item_key, "Epic Axe")

    def test_boss_loot_handler_roll_returns_list(self):
        from unittest.mock import patch
        from world.boss_loot import BossLootTable, BossLootHandler, RARITY_RARE
        table = BossLootTable("Test Boss")
        table.add_item("Rare Ring", RARITY_RARE, 100)  # 100% drop
        handler = BossLootHandler()
        # No physical objects are spawned during this test, so patch out
        # item creation and verify the roll returns an empty list.
        with patch.object(BossLootHandler, "_create_loot_item",
                          return_value=None):
            drops = handler.roll_boss_loot(table)
        self.assertIsInstance(drops, list)
        self.assertEqual(len(drops), 0)

    def test_boss_loot_handler_dry_roll(self):
        from unittest.mock import patch
        from world.boss_loot import BossLootTable, BossLootHandler, RARITY_RARE
        table = BossLootTable("Test Boss")
        table.add_item("Rare Ring", RARITY_RARE, 5)  # 5% drop chance
        handler = BossLootHandler()
        # Force a high roll (100) so no drop occurs on the 5% chance.
        with patch("random.randint", return_value=100):
            drops = handler.roll_boss_loot(table)
        self.assertIsInstance(drops, list)
        self.assertEqual(len(drops), 0)


# ============================================================================
# PART 19 — Movement Commands
# ============================================================================

class TestMovementCommands(BaseEvenniaTest):
    """Verify the master CmdMove and directional movement."""

    def test_move_west_then_east(self):
        room_a = create_object(DefaultRoom, key="Room A")
        room_b = create_object(DefaultRoom, key="Room B")
        create_object(DefaultExit, key="west", location=room_a,
                      destination=room_b)
        create_object(DefaultExit, key="east", location=room_b,
                      destination=room_a)

        self.char1.location = room_a

        from commands.movement import CmdMove

        cmd = CmdMove()
        cmd.caller = self.char1
        cmd.cmdstring = "w"
        cmd.args = ""
        cmd.func()
        self.assertEqual(self.char1.location, room_b)

        cmd = CmdMove()
        cmd.caller = self.char1
        cmd.cmdstring = "e"
        cmd.args = ""
        cmd.func()
        self.assertEqual(self.char1.location, room_a)

        room_a.delete()
        room_b.delete()

    def test_move_north_then_south(self):
        room_a = create_object(DefaultRoom, key="Room A")
        room_b = create_object(DefaultRoom, key="Room B")
        create_object(DefaultExit, key="north", location=room_a,
                      destination=room_b)
        create_object(DefaultExit, key="south", location=room_b,
                      destination=room_a)

        self.char1.location = room_a

        from commands.movement import CmdMove

        cmd = CmdMove()
        cmd.caller = self.char1
        cmd.cmdstring = "n"
        cmd.args = ""
        cmd.func()
        self.assertEqual(self.char1.location, room_b)

        cmd = CmdMove()
        cmd.caller = self.char1
        cmd.cmdstring = "s"
        cmd.args = ""
        cmd.func()
        self.assertEqual(self.char1.location, room_a)

        room_a.delete()
        room_b.delete()

    def test_move_no_exit_stays_in_place(self):
        room = create_object(DefaultRoom, key="Dead End")
        self.char1.location = room

        from commands.movement import CmdMove

        cmd = CmdMove()
        cmd.caller = self.char1
        cmd.cmdstring = "n"
        cmd.args = ""
        cmd.func()
        self.assertEqual(self.char1.location, room)

        room.delete()


# ============================================================================
# PART 20 — Spell System
# ============================================================================

class TestSpellSystem(BaseEvenniaTest):
    """Verify spell definitions, level gates, and spell commands."""

    def test_spells_dictionary_exists(self):
        from world.spells import SPELLS
        self.assertIsInstance(SPELLS, dict)
        self.assertGreater(len(SPELLS), 0)

    def test_get_spells_for_level(self):
        from world.spells import get_spells_for_level
        spells = get_spells_for_level(1)
        self.assertIsInstance(spells, list)

    def test_cast_command_exists(self):
        from commands.spells import CmdCast
        self.assertTrue(issubclass(CmdCast, object))

    def test_spells_command_exists(self):
        from commands.spells import CmdSpells
        self.assertTrue(issubclass(CmdSpells, object))

    def test_spell_level_gating(self):
        from world.spells import get_spells_for_level
        low_spells = get_spells_for_level(1)
        high_spells = get_spells_for_level(50)
        self.assertGreaterEqual(len(high_spells), len(low_spells),
                                "Higher levels should have >= spells")


# ============================================================================
# PART 21 — General Commands
# ============================================================================

class TestGeneralCommands(BaseEvenniaTest):
    """Verify general command existence and basic functionality."""

    def test_look_command_exists(self):
        from commands.general import CmdLook
        self.assertTrue(issubclass(CmdLook, object))

    def test_who_command_exists(self):
        from commands.general import CmdWho
        self.assertTrue(issubclass(CmdWho, object))

    def test_say_command_exists(self):
        from commands.general import CmdSay
        self.assertTrue(issubclass(CmdSay, object))

    def test_pose_command_exists(self):
        from commands.general import CmdPose
        self.assertTrue(issubclass(CmdPose, object))

    def test_inventory_command_exists(self):
        from commands.general import CmdInventory
        self.assertTrue(issubclass(CmdInventory, object))


# ============================================================================
# PART 22 — Drop / Take Coin Commands
# ============================================================================

class TestDropTakeCoins(BaseEvenniaTest):
    """Verify coin drop and take commands."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="CoinRoom")
        self.char1.location = self.room

    def tearDown(self):
        self.room.delete()
        super().tearDown()

    def test_drop_coins(self):
        from commands.drop import CmdDropCoins
        self.char1.attributes.add("money", 500)

        cmd = CmdDropCoins()
        cmd.caller = self.char1
        cmd.args = "200"
        cmd.func()

        self.assertEqual(self.char1.attributes.get("money"), 300)
        self.assertEqual(self.room.attributes.get("ground_gold"), 200)

    def test_drop_coins_not_enough(self):
        from commands.drop import CmdDropCoins
        self.char1.attributes.add("money", 50)

        cmd = CmdDropCoins()
        cmd.caller = self.char1
        cmd.args = "200"
        cmd.func()

        self.assertEqual(self.char1.attributes.get("money"), 50)
        self.assertEqual(self.room.attributes.get("ground_gold", 0), 0)

    def test_take_coins(self):
        from commands.drop import CmdTakeCoins
        self.room.attributes.add("ground_gold", 200)

        cmd = CmdTakeCoins()
        cmd.caller = self.char1
        cmd.args = "150"
        cmd.func()

        self.assertEqual(self.room.attributes.get("ground_gold"), 50)
        self.assertEqual(self.char1.attributes.get("money"), 150)

    def test_take_coins_all(self):
        from commands.drop import CmdTakeCoins
        self.room.attributes.add("ground_gold", 200)

        cmd = CmdTakeCoins()
        cmd.caller = self.char1
        cmd.args = "all"
        cmd.func()

        self.assertEqual(self.room.attributes.get("ground_gold"), 0)
        self.assertEqual(self.char1.attributes.get("money"), 200)


# ============================================================================
# PART 23 — Faction Starter System
# ============================================================================

class TestFactionStarter(BaseEvenniaTest):
    """Verify faction starter gear and shops."""

    def test_faction_starter_build_function_exists(self):
        from world.faction_starter import build_faction_starters
        self.assertTrue(callable(build_faction_starters))

    def test_good_starter_rooms_defined(self):
        from world.faction_starter import GOOD_START_ROOMS
        self.assertGreater(len(GOOD_START_ROOMS), 0)

    def test_evil_starter_rooms_defined(self):
        from world.faction_starter import EVIL_START_ROOMS
        self.assertGreater(len(EVIL_START_ROOMS), 0)

    def test_good_starter_gear_has_slots(self):
        from world.faction_starter import GOOD_STARTER_GEAR
        expected_slots = {"head", "torso", "legs", "feet",
                          "main_hand", "two_hand", "off_hand"}
        self.assertTrue(expected_slots.issubset(set(GOOD_STARTER_GEAR.keys())))

    def test_evil_starter_gear_has_slots(self):
        from world.faction_starter import EVIL_STARTER_GEAR
        expected_slots = {"head", "torso", "legs", "feet",
                          "main_hand", "two_hand", "off_hand"}
        self.assertTrue(expected_slots.issubset(set(EVIL_STARTER_GEAR.keys())))

    def test_starter_gear_has_required_fields(self):
        from world.faction_starter import GOOD_STARTER_GEAR, EVIL_STARTER_GEAR
        for gear_set in (GOOD_STARTER_GEAR, EVIL_STARTER_GEAR):
            for slot, item in gear_set.items():
                self.assertIn("key", item)
                self.assertIn("desc", item)
                self.assertIn("required_level", item)
                self.assertEqual(item["required_level"], 1)


# ============================================================================
# PART 24 — Realm Population
# ============================================================================

class TestRealmPopulation(BaseEvenniaTest):
    """Verify realm population module and mob templates."""

    def test_populate_all_function_exists(self):
        from world.populate_realm import populate_all
        self.assertTrue(callable(populate_all))

    def test_clear_all_mobs_function_exists(self):
        from world.populate_realm import clear_all_mobs
        self.assertTrue(callable(clear_all_mobs))

    def test_npc_typeclass_exists(self):
        from world.populate_realm import NPC
        self.assertTrue(issubclass(NPC, DefaultCharacter))

    def test_mob_typeclass_exists(self):
        from world.populate_realm import Mob
        self.assertTrue(issubclass(Mob, DefaultCharacter))

    def test_good_evil_neutral_weapon_lists(self):
        from world.populate_realm import (
            GOOD_WEAPONS, EVIL_WEAPONS, DESERT_WEAPONS
        )
        self.assertGreater(len(GOOD_WEAPONS), 0)
        self.assertGreater(len(EVIL_WEAPONS), 0)
        self.assertGreater(len(DESERT_WEAPONS), 0)

    def test_good_evil_neutral_armor_lists(self):
        from world.populate_realm import (
            GOOD_ARMOR, EVIL_ARMOR, DESERT_ARMOR
        )
        self.assertGreater(len(GOOD_ARMOR), 0)
        self.assertGreater(len(EVIL_ARMOR), 0)
        self.assertGreater(len(DESERT_ARMOR), 0)

    def test_classify_room_function_exists(self):
        from world.populate_realm import classify_room
        self.assertTrue(callable(classify_room))


# ============================================================================
# PART 25 — Command Set Registration
# ============================================================================

class TestCommandSets(BaseEvenniaTest):
    """Verify that all command sets are properly imported and registered."""

    def test_default_cmdsets_module_imports(self):
        from commands.default_cmdsets import CharacterCmdSet
        self.assertIsNotNone(CharacterCmdSet)

    def test_unloggedin_cmds_exist(self):
        from commands.unloggedin import UnloggedinCmdSet
        self.assertIsNotNone(UnloggedinCmdSet)

    def test_weather_command_exists(self):
        from commands.weather import CmdWeather
        self.assertTrue(issubclass(CmdWeather, object))


# ============================================================================
# PART 26 — Builder Phase Modules
# ============================================================================

class TestBuilderPhases(BaseEvenniaTest):
    """Verify all builder phase modules are importable."""

    def test_builder_phase1_imports(self):
        from world.builder_phase1 import build_phase1
        self.assertTrue(callable(build_phase1))

    def test_builder_phase2_imports(self):
        from world.builder_phase2 import build_phase2
        self.assertTrue(callable(build_phase2))

    def test_builder_phase3_imports(self):
        from world.builder_phase3 import build_phase3
        self.assertTrue(callable(build_phase3))

    def test_builder_phase4_imports(self):
        from world.builder_phase4 import build_all
        self.assertTrue(callable(build_all))

    def test_batch_world_build_imports(self):
        from world.batch_world_build import build_world
        self.assertTrue(callable(build_world))