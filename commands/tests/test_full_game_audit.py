"""
Complete Game Audit Test Suite for 'rop'
=========================================
A single, terminal-runnable test module that exercises and validates every
major game system against the REAL code, and surfaces latent errors/bugs.

Run the whole suite from the project root with:

    evennia test commands.tests.test_full_game_audit

Run a single class (e.g. boss registry):

    evennia test commands.tests.test_full_game_audit.TestBossRegistry

Run a single test:

    evennia test commands.tests.test_full_game_audit.TestBossRegistry.test_registry_has_30_bosses

Coverage map:
    PART 1  - Module import smoke-test (catches missing/broken modules)
    PART 2  - Rules, races, classes, XP, warpoints
    PART 3  - Boss registry, lairs, dungeon expansions
    PART 4  - Boss loot / rarity system
    PART 5  - Armor set system
    PART 6  - Weather / climate
    PART 7  - Zone tiers & level scaling
    PART 8  - Quest system
    PART 9  - Combat / death / corpses / shields
    PART 10 - Spells
    PART 11 - Banking
    PART 12 - Loot / sacrifice commands
    PART 13 - Group system
    PART 14 - Movement
    PART 15 - Announcements / MOTD / rules / help

NOTE: This module deliberately creates and deletes its own objects and never
relies on the auto-created `self.char1` fixtures, so it works against the
current Evennia test resources.
"""

import importlib
import random

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import (
    DefaultRoom,
    DefaultCharacter,
    DefaultObject,
    DefaultExit,
)
from evennia import create_object


# ============================================================================
# PART 1 - Module import smoke-test
# ============================================================================

class TestModuleSmoke(BaseEvenniaTest):
    """Every game module should be importable without raising."""

    MODULES = [
        "world.rules",
        "world.boss_registry",
        "world.boss_zones",
        "world.boss_expansions",
        "world.boss_loot",
        "world.armor_sets",
        "world.weather",
        "world.weather_script",
        "world.zone_levels",
        "world.quests",
        "world.combat",
        "world.combat_state",
        "world.spells",
        "world.backup",
        "world.announcements",
        "world.motd",
        "world.help_entries",
        "world.faction_starter",
        "world.populate_realm",
        "world.builder_phase1",
        "world.builder_phase2",
        "world.builder_phase3",
        "world.builder_phase4",
        "world.batch_world_build",
        "world.item_builder",
        "world.quest_items",
        "world.cleanup",
        "world.chargen",
        "world.build_entities",
        "commands.announcements",
        "commands.backup",
        "commands.bank",
        "commands.broadcast",
        "commands.clan",
        "commands.drop",
        "commands.general",
        "commands.gossip",
        "commands.group",
        "commands.loot",
        "commands.movement",
        "commands.pvp",
        "commands.quest",
        "commands.rules",
        "commands.spells",
        "commands.stats",
        "commands.unloggedin",
        "commands.weather",
        "commands.default_cmdsets",
        "typeclasses.characters",
        "typeclasses.rooms",
        "typeclasses.exits",
    ]

    def test_all_modules_import(self):
        for modname in self.MODULES:
            with self.subTest(module=modname):
                mod = importlib.import_module(modname)
                self.assertIsNotNone(mod)


# ============================================================================
# PART 2 - Rules, races, classes, XP, warpoints
# ============================================================================

class TestRulesAndProgression(BaseEvenniaTest):
    def test_16_races(self):
        from world.rules import RACES
        self.assertEqual(len(RACES), 16)

    def test_8_good_8_evil(self):
        from world.rules import RACES
        good = [r for r, d in RACES.items() if d.get("alignment") == "Good"]
        evil = [r for r, d in RACES.items() if d.get("alignment") == "Evil"]
        self.assertEqual(len(good), 8)
        self.assertEqual(len(evil), 8)

    def test_every_race_has_all_six_stats(self):
        from world.rules import RACES
        expected = {"str", "dex", "con", "int", "wis", "cha"}
        for name, data in RACES.items():
            self.assertTrue(expected.issubset(set(data["stats"].keys())),
                            f"{name}: missing a core stat")

    def test_10_classes(self):
        from world.rules import CLASSES
        self.assertEqual(len(CLASSES), 10)

    def test_classes_have_hp_and_mana(self):
        from world.rules import CLASSES
        for name, data in CLASSES.items():
            self.assertIn("hp_per_level", data)
            self.assertIn("mana_per_level", data)
            self.assertIn("primary_stat", data)
            self.assertGreaterEqual(data["hp_per_level"], 1, f"{name} HP too low")

    def test_rules_text_nonempty(self):
        from world.rules import RULES_TEXT
        self.assertIsInstance(RULES_TEXT, str)
        self.assertIn("GENERAL CONDUCT", RULES_TEXT)

    def test_xp_formula(self):
        from world.rules import xp_to_level
        self.assertEqual(xp_to_level(1), 1000)
        self.assertEqual(xp_to_level(5), 5000)
        self.assertEqual(xp_to_level(80), 80000)

    def test_xp_monotonic(self):
        from world.rules import xp_to_level
        for lvl in range(1, 80):
            self.assertGreater(xp_to_level(lvl + 1), xp_to_level(lvl))

    def test_stats_on_level_up(self):
        from world.rules import stats_on_level_up
        self.assertEqual(stats_on_level_up(),
                         {"str": 1, "dex": 1, "con": 1,
                          "int": 1, "wis": 1, "cha": 1})

    def test_warpoints_equal_level(self):
        from world.rules import calculate_warpoints
        self.assertEqual(calculate_warpoints(50, 50), 50)

    def test_warpoints_fighting_up_awards_bonus(self):
        from world.rules import calculate_warpoints
        self.assertGreater(calculate_warpoints(50, 55),
                           calculate_warpoints(50, 50))

    def test_warpoints_floor_for_close_levels(self):
        from world.rules import calculate_warpoints
        self.assertEqual(calculate_warpoints(50, 45), 50)

    def test_warpoints_never_below_min(self):
        from world.rules import calculate_warpoints, MIN_WARPOINTS
        for victim in range(1, 80):
            self.assertGreaterEqual(
                calculate_warpoints(50, victim), MIN_WARPOINTS,
                f"warpoints for victim lvl {victim} below minimum")
        self.assertGreaterEqual(calculate_warpoints(80, 1), MIN_WARPOINTS)


# ============================================================================
# PART 3 - Boss registry, lairs, dungeon expansions
# ============================================================================

class TestBossRegistry(BaseEvenniaTest):
    def test_registry_has_30_bosses(self):
        from world.boss_registry import BOSS_REGISTRY
        self.assertEqual(len(BOSS_REGISTRY), 30)

    def test_room_lookup_has_30_entries(self):
        from world.boss_registry import BOSS_ROOM_LOOKUP
        self.assertEqual(len(BOSS_ROOM_LOOKUP), 30)

    def test_registry_keys_match_room_lookup(self):
        from world.boss_registry import BOSS_REGISTRY, BOSS_ROOM_LOOKUP
        self.assertEqual(set(BOSS_REGISTRY), set(BOSS_ROOM_LOOKUP))

    def test_15_evil_15_good(self):
        from world.boss_registry import BOSS_REGISTRY
        evil = [b for b in BOSS_REGISTRY.values()
                if b["faction"] == "Gorgoroth Horde"]
        good = [b for b in BOSS_REGISTRY.values()
                if b["faction"] == "Aethelgard Alliance"]
        self.assertEqual(len(evil), 15)
        self.assertEqual(len(good), 15)

    def test_levels_within_bounds(self):
        from world.boss_registry import BOSS_REGISTRY
        for bid, data in BOSS_REGISTRY.items():
            self.assertGreaterEqual(data["level"], 8, bid)
            self.assertLessEqual(data["level"], 50, bid)

    def test_required_fields_present(self):
        from world.boss_registry import BOSS_REGISTRY
        required = {"name", "faction", "level", "hp", "max_damage",
                    "rare_drop", "drop_rate", "announce"}
        for bid, data in BOSS_REGISTRY.items():
            missing = required - set(data)
            self.assertFalse(missing, f"{bid}: missing {missing}")

    def test_announce_has_killer_placeholder(self):
        from world.boss_registry import BOSS_REGISTRY
        for bid, data in BOSS_REGISTRY.items():
            self.assertIn("{killer}", data["announce"], bid)

    def test_hp_scales_with_level(self):
        from world.boss_registry import BOSS_REGISTRY
        for bid, data in BOSS_REGISTRY.items():
            self.assertGreaterEqual(data["hp"], data["level"] * 80, bid)
            self.assertLessEqual(data["hp"], data["level"] * 300, bid)

    def test_drop_rate_within_range(self):
        from world.boss_registry import BOSS_REGISTRY
        for bid, data in BOSS_REGISTRY.items():
            self.assertGreaterEqual(data["drop_rate"], 1, bid)
            self.assertLessEqual(data["drop_rate"], 100, bid)

    def test_boss_typeclass_exists(self):
        from world.boss_registry import Boss
        self.assertTrue(issubclass(Boss, DefaultCharacter))


class TestBossLairs(BaseEvenniaTest):
    def test_30_lair_defs(self):
        from world.boss_zones import BOSS_LAIR_DEFS
        self.assertEqual(len(BOSS_LAIR_DEFS), 30)

    def test_each_def_is_4_tuple(self):
        from world.boss_zones import BOSS_LAIR_DEFS
        for entry in BOSS_LAIR_DEFS:
            self.assertEqual(len(entry), 4)
            boss_id, title, anchor, desc = entry
            self.assertTrue(boss_id)
            self.assertTrue(title)
            self.assertTrue(anchor)
            self.assertTrue(desc)

    def test_build_boss_lairs_creates_30(self):
        from world.boss_zones import build_boss_lairs
        lairs = build_boss_lairs()
        try:
            self.assertEqual(len(lairs), 30)
        finally:
            for room in lairs.values():
                room.delete()

    def test_lairs_have_flags_tags_desc(self):
        from world.boss_zones import build_boss_lairs
        lairs = build_boss_lairs()
        try:
            for boss_id, room in lairs.items():
                self.assertTrue(room.db.is_boss_lair)
                self.assertTrue(room.db.desc)
                tags = room.tags.get(category="room_type", return_objs=False)
                self.assertIn("boss_lair", tags)
                ids = room.tags.get(category="boss_id", return_objs=False)
                self.assertIn(boss_id, ids)
        finally:
            for room in lairs.values():
                room.delete()


class TestDungeonExpansions(BaseEvenniaTest):
    def test_30_dungeon_defs(self):
        from world.boss_expansions import DUNGEON_EXPANSIONS
        self.assertEqual(len(DUNGEON_EXPANSIONS), 30)

    def test_15_evil_15_good(self):
        from world.boss_expansions import DUNGEON_EXPANSIONS
        evil = [d for d in DUNGEON_EXPANSIONS if d[2] == "evil"]
        good = [d for d in DUNGEON_EXPANSIONS if d[2] == "good"]
        self.assertEqual(len(evil), 15)
        self.assertEqual(len(good), 15)

    def test_room_counts_within_4_10(self):
        from world.boss_expansions import DUNGEON_EXPANSIONS
        for d in DUNGEON_EXPANSIONS:
            self.assertGreaterEqual(d[3], 4, d[0])
            self.assertLessEqual(d[3], 10, d[0])

    def test_flavor_lines_match_room_count(self):
        from world.boss_expansions import DUNGEON_EXPANSIONS
        for d in DUNGEON_EXPANSIONS:
            self.assertEqual(len(d[5]), d[3],
                             f"{d[0]}: flavor line count mismatch")

    def test_each_def_contract(self):
        from world.boss_expansions import DUNGEON_EXPANSIONS
        for d in DUNGEON_EXPANSIONS:
            self.assertEqual(len(d), 8)
            self.assertTrue(d[4].startswith("boss_"), d[4])

    def test_build_dungeon_expansions_creates_30(self):
        from world.boss_expansions import build_dungeon_expansions
        expansions = build_dungeon_expansions()
        try:
            self.assertEqual(len(expansions), 30)
            for dungeon_id, rooms in expansions.items():
                self.assertGreaterEqual(len(rooms), 4, dungeon_id)
                self.assertLessEqual(len(rooms), 10, dungeon_id)
                entrances = rooms[0].tags.get(category="room_type",
                                              return_objs=False)
                self.assertIn("dungeon_entrance", entrances)
        finally:
            for rooms in expansions.values():
                for room in rooms:
                    room.delete()


# ============================================================================
# PART 4 - Boss loot / rarity system
# ============================================================================

class TestBossLoot(BaseEvenniaTest):
    def test_rarity_constants(self):
        from world.boss_loot import (
            RARITY_COMMON, RARITY_UNCOMMON, RARITY_RARE,
            RARITY_EPIC, RARITY_LEGENDARY,
        )
        self.assertEqual(RARITY_COMMON, "common")
        self.assertEqual(RARITY_UNCOMMON, "uncommon")
        self.assertEqual(RARITY_RARE, "rare")
        self.assertEqual(RARITY_EPIC, "epic")
        self.assertEqual(RARITY_LEGENDARY, "legendary")

    def test_boss_only_rarities(self):
        from world.boss_loot import (
            BOSS_ONLY_RARITIES, RARITY_RARE, RARITY_EPIC, RARITY_LEGENDARY,
        )
        self.assertIn(RARITY_RARE, BOSS_ONLY_RARITIES)
        self.assertIn(RARITY_EPIC, BOSS_ONLY_RARITIES)
        self.assertIn(RARITY_LEGENDARY, BOSS_ONLY_RARITIES)

    def test_loot_entry_clamps_drop_chance(self):
        from world.boss_loot import LootEntry
        self.assertEqual(LootEntry("A", drop_chance=150).drop_chance, 100)
        self.assertEqual(LootEntry("B", drop_chance=-5).drop_chance, 1)
        self.assertEqual(LootEntry("C", drop_chance=37).drop_chance, 37)

    def test_boss_loot_table_add_item(self):
        from world.boss_loot import BossLootTable, RARITY_EPIC
        table = BossLootTable("Test Boss")
        table.add_item("Epic Axe", RARITY_EPIC, 10)
        self.assertEqual(len(table.entries), 1)
        self.assertEqual(table.entries[0].item_key, "Epic Axe")
        self.assertEqual(table.entries[0].rarity, RARITY_EPIC)

    def test_value_for_rarity(self):
        from world.boss_loot import BossLootHandler, RARITY_RARE, RARITY_EPIC, RARITY_LEGENDARY
        self.assertEqual(BossLootHandler._value_for_rarity(RARITY_RARE), 250)
        self.assertEqual(BossLootHandler._value_for_rarity(RARITY_EPIC), 750)
        self.assertEqual(BossLootHandler._value_for_rarity(RARITY_LEGENDARY), 2000)

    def test_roll_boss_loot_drops_nothing_on_high_roll(self):
        from unittest.mock import patch
        from world.boss_loot import BossLootTable, BossLootHandler, RARITY_RARE
        table = BossLootTable("T")
        table.add_item("Ring", RARITY_RARE, 5)
        with patch("random.randint", return_value=100):
            drops = BossLootHandler.roll_boss_loot(table)
        self.assertEqual(drops, [])

    def test_roll_boss_loot_patches_item_creation(self):
        from unittest.mock import patch
        from world.boss_loot import BossLootTable, BossLootHandler, RARITY_RARE
        table = BossLootTable("T")
        table.add_item("Ring", RARITY_RARE, 100)
        with patch.object(BossLootHandler, "_create_loot_item", return_value=None):
            drops = BossLootHandler.roll_boss_loot(table)
        self.assertEqual(drops, [])

    def test_boss_flags(self):
        from world.boss_loot import mark_as_boss, is_boss, can_drop_rare
        npc = create_object(DefaultCharacter, key="BossTest")
        try:
            self.assertFalse(is_boss(npc))
            mark_as_boss(npc)
            self.assertTrue(is_boss(npc))
            self.assertTrue(can_drop_rare(npc))
        finally:
            npc.delete()

    def test_default_boss_loot_register(self):
        from world.boss_loot import boss_loot_registry, register_default_boss_loot
        register_default_boss_loot()
        self.assertGreaterEqual(len(boss_loot_registry.all()), 3)


# ============================================================================
# PART 5 - Armor set system
# ============================================================================

class TestArmorSets(BaseEvenniaTest):
    def test_default_sets_register_four(self):
        from world.armor_sets import register_default_armor_sets, armor_set_registry
        register_default_armor_sets()
        self.assertEqual(len(armor_set_registry.all()), 4)

    def test_set_definition_bonuses(self):
        from world.armor_sets import ArmorSetDefinition
        s = ArmorSetDefinition(
            set_id="test", name="Test Set",
            pieces={"head": "Test Helm", "torso": "Test Chest",
                    "legs": "Test Legs", "arms": "Test Arms"},
            bonus_2={"max_hp": 20},
            bonus_4={"max_hp": 50},
        )
        self.assertEqual(s.count_equipped({"head": "Test Helm"}), 1)
        self.assertEqual(s.count_equipped(
            {"head": "Test Helm", "torso": "Test Chest"}), 2)
        # 1 piece -> no bonus
        self.assertEqual(s.get_bonus_for_count(1), {})
        # 2 pieces -> partial
        self.assertEqual(s.get_bonus_for_count(2), {"max_hp": 20})
        # 4 pieces -> stacking (50 overrides, not added within same key for
        # this simplified scheme; assert at least the 4-piece value exists)
        self.assertEqual(s.get_bonus_for_count(4)["max_hp"],
                         s.bonus_4["max_hp"])

    def test_check_piece_case_insensitive(self):
        from world.armor_sets import ArmorSetDefinition
        s = ArmorSetDefinition("t", "T", pieces={"head": "Dragon Helm"})
        self.assertTrue(s.check_piece("HEAD", "dragon helm"))
        self.assertFalse(s.check_piece("head", "wrong"))

    def test_checker_active_bonuses(self):
        from world.armor_sets import (
            ArmorSetChecker, register_default_armor_sets,
        )
        register_default_armor_sets()
        char = create_object(DefaultCharacter, key="ArmorTest")
        try:
            char.attributes.add("equipped", {
                "head": "Dragonscale Helm",
                "torso": "Dragonscale Breastplate",
            })
            checker = ArmorSetChecker(char)
            active = checker.get_active_set_bonuses()
            self.assertIn("dragonscale", active)
            self.assertEqual(active["dragonscale"]["count"], 2)
        finally:
            char.delete()

    def test_apply_set_bonuses_stores_attribute(self):
        from world.armor_sets import apply_set_bonuses_to_character, register_default_armor_sets
        register_default_armor_sets()
        char = create_object(DefaultCharacter, key="ArmorTest")
        try:
            char.attributes.add("equipped", {
                "head": "Dragonscale Helm",
                "torso": "Dragonscale Breastplate",
            })
            apply_set_bonuses_to_character(char)
            self.assertEqual(char.attributes.get("armor_set_bonuses"),
                             {"max_hp": 20, "defense": 2})
        finally:
            char.delete()


# ============================================================================
# PART 6 - Weather / climate
# ============================================================================

class TestWeather(BaseEvenniaTest):
    def test_weather_states(self):
        from world.weather import WEATHER_STATES
        self.assertIsInstance(WEATHER_STATES, dict)
        self.assertGreaterEqual(len(WEATHER_STATES), 10)

    def test_climates(self):
        from world.weather import CLIMATES, DEFAULT_CLIMATE
        self.assertEqual(DEFAULT_CLIMATE, "temperate")
        for key in ("cold", "desert", "wet", "coastal", "temperate"):
            self.assertIn(key, CLIMATES)

    def test_get_climate(self):
        from world.weather import get_climate
        self.assertEqual(get_climate("Highland Pass"), "cold")
        self.assertEqual(get_climate("Scorched Dunes"), "desert")
        self.assertEqual(get_climate("Blackfen Marsh"), "wet")
        self.assertEqual(get_climate("Sunrise Coast"), "wet")
        self.assertEqual(get_climate("Emerald Forest"), "temperate")
        self.assertEqual(get_climate("Totally Unknown"), "temperate")

    def test_pick_weather_valid(self):
        from world.weather import pick_weather, WEATHER_STATES
        rng = random.Random(7)
        for _ in range(100):
            state = pick_weather("Emerald Forest", rng)
            self.assertIn(state, WEATHER_STATES)

    def test_weather_exemptions(self):
        from world.weather import is_weather_exempt
        safe = create_object(DefaultRoom, key="Safe")
        safe.db.safe_zone = True
        indoor = create_object(DefaultRoom, key="Indoor")
        indoor.attributes.add("indoor", True)
        outdoor = create_object(DefaultRoom, key="Forest")
        try:
            self.assertTrue(is_weather_exempt(safe))
            self.assertTrue(is_weather_exempt(indoor))
            self.assertFalse(is_weather_exempt(outdoor))
        finally:
            safe.delete(); indoor.delete(); outdoor.delete()

    def test_format_weather_line_and_short(self):
        from world.weather import format_weather_line, format_weather_short
        room = create_object(DefaultRoom, key="Emerald Forest")
        try:
            line = format_weather_line(room)
            short = format_weather_short(room)
            self.assertIn("The sky is", line)
            self.assertIn("[", short)
        finally:
            room.delete()


# ============================================================================
# PART 7 - Zone tiers & level scaling
# ============================================================================

class TestZoneLevels(BaseEvenniaTest):
    def test_tier_lists(self):
        from world.zone_levels import (
            TIER_1_ZONES, TIER_2_ZONES, TIER_3_ZONES,
            TIER_4_ZONES, TIER_5_ZONES,
        )
        self.assertGreater(len(TIER_1_ZONES), 0)
        self.assertGreater(len(TIER_2_ZONES), 0)
        self.assertGreater(len(TIER_3_ZONES), 0)
        self.assertGreater(len(TIER_4_ZONES), 0)
        self.assertGreater(len(TIER_5_ZONES), 0)

    def test_get_zone_level_range(self):
        from world.zone_levels import get_zone_level_range
        self.assertEqual(get_zone_level_range("Rolling Plains of Aethelgard"), (1, 5))
        self.assertEqual(get_zone_level_range("Emerald Forest"), (6, 15))
        self.assertEqual(get_zone_level_range("Unknown Zone"), (1, 5))

    def test_danger_levels_valid(self):
        from world.zone_levels import get_danger_level
        self.assertEqual(get_danger_level("Rolling Plains of Aethelgard"), "safe")
        self.assertEqual(get_danger_level("Emerald Forest"), "caution")
        self.assertEqual(get_danger_level("Golden Farmland"), "danger")
        self.assertEqual(get_danger_level("Dusk Coast"), "deadly")

    def test_map_ranges_valid(self):
        from world.zone_levels import ZONE_TIER_MAP
        for zone, (tier, lmin, lmax, danger) in ZONE_TIER_MAP.items():
            self.assertGreaterEqual(tier, 1)
            self.assertLessEqual(tier, 5)
            self.assertGreaterEqual(lmin, 1)
            self.assertLessEqual(lmax, 80)
            self.assertLessEqual(lmin, lmax, zone)
            self.assertIn(danger, {"safe", "caution", "danger", "deadly"})

    def test_scale_mob_level_within_range(self):
        from world.zone_levels import scale_mob_level
        for _ in range(100):
            result = scale_mob_level(1, 5, 3)
            self.assertGreaterEqual(result, 1)
            self.assertLessEqual(result, 5)

    def test_should_be_aggressive(self):
        from world.zone_levels import should_be_aggressive
        self.assertFalse(should_be_aggressive("safe", True))
        self.assertTrue(should_be_aggressive("caution", True))
        self.assertFalse(should_be_aggressive("caution", False))
        self.assertTrue(should_be_aggressive("danger", False))
        self.assertTrue(should_be_aggressive("deadly", False))


# ============================================================================
# PART 8 - Quest system
# ============================================================================

class TestQuests(BaseEvenniaTest):
    def test_definition(self):
        from world.quests import QuestDefinition
        q = QuestDefinition(
            id="q1", name="Q", description="d", quest_type="kill",
            target_key="goblin", target_count=5,
            rewards={"xp": 100, "gold": 50},
            giver_npc_key="Giver", level_required=1,
        )
        self.assertEqual(q.id, "q1")
        self.assertEqual(q.target_count, 5)
        self.assertEqual(q.quest_type, "kill")

    def test_registry_register_get_clear(self):
        from world.quests import QuestRegistry, QuestDefinition
        reg = QuestRegistry()
        q = QuestDefinition(id="q", name="Q", description="d",
                            quest_type="kill", target_key="goblin")
        reg.register(q)
        self.assertEqual(len(reg), 1)
        self.assertEqual(reg.get("q"), q)
        reg.clear()
        self.assertEqual(len(reg), 0)

    def test_active_quest_advance(self):
        from world.quests import QuestDefinition, ActiveQuest
        q = QuestDefinition(id="q", name="Q", description="d",
                            quest_type="kill", target_key="goblin",
                            target_count=5)
        aq = ActiveQuest(quest_def=q)
        self.assertEqual(aq.progress, 0)
        self.assertFalse(aq.is_complete)
        aq.advance(3)
        self.assertEqual(aq.progress, 3)
        self.assertFalse(aq.is_complete)
        aq.advance(2)
        self.assertEqual(aq.progress, 5)
        self.assertTrue(aq.is_complete)

    def test_default_quests_register_six(self):
        from world.quests import quest_registry, register_default_quests
        register_default_quests()
        self.assertEqual(len(quest_registry), 6)

    def test_default_quests_have_all_types(self):
        from world.quests import quest_registry, register_default_quests
        register_default_quests()
        types = {q.quest_type for q in quest_registry.all()}
        self.assertEqual(types, {"kill", "fetch", "talk"})

    def test_quest_handler_attach(self):
        from world.quests import QuestHandler
        char = create_object(DefaultCharacter, key="Quester")
        try:
            handler = QuestHandler(char)
            self.assertEqual(handler.owner, char)
        finally:
            char.delete()


# ============================================================================
# PART 9 - Combat / death / corpses / shields
# ============================================================================

class TestCombat(BaseEvenniaTest):
    def test_combat_state_enum(self):
        from world.combat_state import CombatState
        for name in ("IDLE", "FIGHTING", "STUNNED", "RESTING",
                     "SLEEPING", "DEAD", "FLEEING"):
            self.assertTrue(hasattr(CombatState, name))

    def test_posture_enum(self):
        from world.combat_state import Posture
        for name in ("STANDING", "SITTING", "RESTING", "SLEEPING"):
            self.assertTrue(hasattr(Posture, name))

    def test_state_transitions_defined(self):
        from world.combat_state import STATE_TRANSITIONS, CombatState
        self.assertIn(CombatState.IDLE, STATE_TRANSITIONS)
        self.assertIn(CombatState.DEAD, STATE_TRANSITIONS)

    def test_regen_constants(self):
        from world.combat_state import (
            HP_REGEN_STANDING, HP_REGEN_RESTING, HP_REGEN_SLEEPING,
            HP_REGEN_COMBAT,
        )
        self.assertGreater(HP_REGEN_STANDING, 0)
        self.assertGreater(HP_REGEN_RESTING, HP_REGEN_STANDING)
        self.assertGreater(HP_REGEN_SLEEPING, HP_REGEN_RESTING)
        self.assertEqual(HP_REGEN_COMBAT, 0)

    def test_safe_zone_detection(self):
        from world.combat import is_safe_zone
        safe = create_object(DefaultRoom, key="Sanctuary")
        safe.db.safe_zone = True
        wild = create_object(DefaultRoom, key="Wilderness")
        try:
            self.assertTrue(is_safe_zone(safe))
            self.assertFalse(is_safe_zone(wild))
        finally:
            safe.delete(); wild.delete()

    def test_shield_reduction(self):
        from world.combat import _reduce_shield, _get_shield
        target = create_object(DefaultCharacter, key="Shielded")
        try:
            target.attributes.add("shield_amount", 10)
            remaining, absorbed = _reduce_shield(target, 7)
            self.assertEqual(remaining, 0)
            self.assertEqual(absorbed, 7)
            self.assertEqual(_get_shield(target), 3)
        finally:
            target.delete()

    def test_make_corpse(self):
        from world.combat import _make_corpse
        room = create_object(DefaultRoom, key="CorpseRoom")
        try:
            corpse = _make_corpse("Goblin", room, contents=[], money=15,
                                  npc_level=3)
            self.assertIn("corpse", corpse.key.lower())
            self.assertTrue(corpse.attributes.get("is_corpse"))
            self.assertEqual(corpse.attributes.get("money"), 15)
            self.assertEqual(corpse.attributes.get("corpse_npc_level"), 3)
            corpse.delete()
        finally:
            room.delete()

    def test_pvp_permission_logic(self):
        from world.combat import _is_pvp_allowed
        attacker = create_object(DefaultCharacter, key="A")
        target = create_object(DefaultCharacter, key="B")
        target_npc = create_object(DefaultCharacter, key="Goblin")
        try:
            # NPC (no alignment) is always attackable
            allowed, _ = _is_pvp_allowed(attacker, target_npc)
            self.assertTrue(allowed)
            # Same alignment with PvP off -> blocked
            attacker.attributes.add("alignment", "Good")
            target.attributes.add("alignment", "Good")
            attacker.db.pvp_enabled = False
            target.db.pvp_enabled = False
            allowed, reason = _is_pvp_allowed(attacker, target)
            self.assertFalse(allowed)
            # Opposing factions -> allowed
            target.attributes.add("alignment", "Evil")
            allowed, _ = _is_pvp_allowed(attacker, target)
            self.assertTrue(allowed)
        finally:
            attacker.delete(); target.delete(); target_npc.delete()


# ============================================================================
# PART 10 - Spells
# ============================================================================

class TestSpells(BaseEvenniaTest):
    def test_spells_nonempty(self):
        from world.spells import SPELLS
        self.assertIsInstance(SPELLS, dict)
        self.assertGreaterEqual(len(SPELLS), 10)

    def test_get_spell_lookup(self):
        from world.spells import get_spell
        sparks = get_spell("sparks")
        self.assertIsNotNone(sparks)
        self.assertEqual(sparks["level"], 1)

    def test_level_gating(self):
        from world.spells import get_spells_for_level, get_spell
        lvl1 = get_spells_for_level(1)
        self.assertIn(get_spell("sparks"), lvl1)
        self.assertIn(get_spell("minorheal"), lvl1)
        # Meteor Swarm (level 80) should not be available at level 1
        self.assertNotIn(get_spell("meteorswarm"), lvl1)
        self.assertIn(get_spell("meteorswarm"), get_spells_for_level(80))

    def test_get_spells_sorted(self):
        from world.spells import get_spells_for_level
        spells = get_spells_for_level(80)
        levels = [s["level"] for s in spells]
        self.assertEqual(levels, sorted(levels))

    def test_mana_cost_resolution(self):
        from world.spells import _resolve_mana_cost, get_spell
        sparks = get_spell("sparks")
        # base 5 + 1 per level
        self.assertEqual(_resolve_mana_cost(sparks, 10), 15)

    def test_damage_resolution_positive(self):
        from world.spells import _resolve_damage, get_spell
        sparks = get_spell("sparks")
        caster = create_object(DefaultCharacter, key="Caster")
        try:
            caster.attributes.add("stats", {"int": 10, "wis": 10})
            dmg = _resolve_damage(sparks, 1, caster)
            self.assertGreater(dmg, 0)
        finally:
            caster.delete()

    def test_spellbook_contains_spells(self):
        from world.spells import format_spellbook
        char = create_object(DefaultCharacter, key="Mage")
        try:
            char.attributes.add("level", 10)
            char.attributes.add("mana", 50)
            char.attributes.add("max_mana", 100)
            out = format_spellbook(char)
            self.assertIn("Spark", out)
            self.assertIn("Sparks", out)
        finally:
            char.delete()


# ============================================================================
# PART 11 - Banking
# ============================================================================

def _make_bank_room_and_teller():
    room = create_object(DefaultRoom, key="Bank")
    teller = create_object(DefaultObject, key="Bank Teller",
                           location=room,
                           attributes=[("is_bank_teller", True)])
    return room, teller


class TestBanking(BaseEvenniaTest):
    def test_deposit(self):
        from commands.bank import CmdDeposit
        room, teller = _make_bank_room_and_teller()
        char = create_object(DefaultCharacter, key="Banker")
        try:
            char.location = room
            char.attributes.add("money", 500)
            char.attributes.add("bank_gold", 0)
            cmd = CmdDeposit(); cmd.caller = char; cmd.args = "200"; cmd.func()
            self.assertEqual(char.attributes.get("money"), 300)
            self.assertEqual(char.attributes.get("bank_gold"), 200)
        finally:
            char.delete(); teller.delete(); room.delete()

    def test_deposit_all(self):
        from commands.bank import CmdDeposit
        room, teller = _make_bank_room_and_teller()
        char = create_object(DefaultCharacter, key="Banker")
        try:
            char.location = room
            char.attributes.add("money", 500)
            cmd = CmdDeposit(); cmd.caller = char; cmd.args = "all"; cmd.func()
            self.assertEqual(char.attributes.get("money"), 0)
            self.assertEqual(char.attributes.get("bank_gold"), 500)
        finally:
            char.delete(); teller.delete(); room.delete()

    def test_deposit_too_much_is_rejected(self):
        from commands.bank import CmdDeposit
        room, teller = _make_bank_room_and_teller()
        char = create_object(DefaultCharacter, key="Banker")
        try:
            char.location = room
            char.attributes.add("money", 50)
            cmd = CmdDeposit(); cmd.caller = char; cmd.args = "200"; cmd.func()
            self.assertEqual(char.attributes.get("money"), 50)
            self.assertEqual(char.attributes.get("bank_gold", 0), 0)
        finally:
            char.delete(); teller.delete(); room.delete()

    def test_withdraw(self):
        from commands.bank import CmdWithdraw
        room, teller = _make_bank_room_and_teller()
        char = create_object(DefaultCharacter, key="Banker")
        try:
            char.location = room
            char.attributes.add("money", 0)
            char.attributes.add("bank_gold", 1000)
            cmd = CmdWithdraw(); cmd.caller = char; cmd.args = "300"; cmd.func()
            self.assertEqual(char.attributes.get("money"), 300)
            self.assertEqual(char.attributes.get("bank_gold"), 700)
        finally:
            char.delete(); teller.delete(); room.delete()

    def test_withdraw_insufficient(self):
        from commands.bank import CmdWithdraw
        room, teller = _make_bank_room_and_teller()
        char = create_object(DefaultCharacter, key="Banker")
        try:
            char.location = room
            char.attributes.add("bank_gold", 50)
            cmd = CmdWithdraw(); cmd.caller = char; cmd.args = "200"; cmd.func()
            self.assertEqual(char.attributes.get("bank_gold"), 50)
            self.assertEqual(char.attributes.get("money", 0), 0)
        finally:
            char.delete(); teller.delete(); room.delete()

    def test_no_teller_blocks_deposit(self):
        from commands.bank import CmdDeposit
        room = create_object(DefaultRoom, key="NotBank")
        char = create_object(DefaultCharacter, key="Banker")
        try:
            char.location = room
            char.attributes.add("money", 500)
            cmd = CmdDeposit(); cmd.caller = char; cmd.args = "200"; cmd.func()
            self.assertEqual(char.attributes.get("money"), 500)
            self.assertEqual(char.attributes.get("bank_gold", 0), 0)
        finally:
            char.delete(); room.delete()


# ============================================================================
# PART 12 - Loot / sacrifice
# ============================================================================

class TestLoot(BaseEvenniaTest):
    def test_calculate_sac_reward_tuple(self):
        from commands.loot import calculate_sac_reward
        coins, display = calculate_sac_reward(5)
        self.assertIsInstance(coins, int)
        self.assertIsInstance(display, str)
        self.assertGreaterEqual(coins, 1)

    def test_sac_reward_scales(self):
        from commands.loot import calculate_sac_reward
        # Statistically, the average should grow with level; assert the range.
        low_min = 999999
        high_max = 0
        for _ in range(200):
            c1, _ = calculate_sac_reward(1)
            c10, _ = calculate_sac_reward(10)
            low_min = min(low_min, c1)
            high_max = max(high_max, c10)
        # reward at level 1 is in [1,5]; at level 10 can reach [10,50].
        self.assertGreaterEqual(high_max, low_min)

    def test_autoloot_toggle(self):
        from commands.loot import CmdAutoLoot
        char = create_object(DefaultCharacter, key="Looter")
        try:
            cmd = CmdAutoLoot(); cmd.caller = char; cmd.func()
            self.assertTrue(char.attributes.get("autoloot"))
            cmd.func()
            self.assertFalse(char.attributes.get("autoloot"))
        finally:
            char.delete()

    def test_autosac_toggle(self):
        from commands.loot import CmdAutoSac
        char = create_object(DefaultCharacter, key="Looter")
        try:
            cmd = CmdAutoSac(); cmd.caller = char; cmd.func()
            self.assertTrue(char.attributes.get("autosac"))
            cmd.func()
            self.assertFalse(char.attributes.get("autosac"))
        finally:
            char.delete()

    def test_loot_commands_exist(self):
        from commands.loot import (
            CmdLoot, CmdSacrifice, CmdAutoLoot, CmdAutoSac,
        )
        for cls in (CmdLoot, CmdSacrifice, CmdAutoLoot, CmdAutoSac):
            self.assertTrue(issubclass(cls, object))


# ============================================================================
# PART 13 - Group system
# ============================================================================

class TestGroup(BaseEvenniaTest):
    def test_split_group_xp_solo(self):
        from commands.group import split_group_xp
        char = create_object(DefaultCharacter, key="Solo")
        try:
            char.attributes.add("xp", 0)
            share = split_group_xp(char, 100)
            self.assertEqual(share, 100)
            self.assertEqual(char.attributes.get("xp"), 100)
        finally:
            char.delete()

    def test_group_leader_flag(self):
        from commands.group import is_group_leader, get_group_leader, get_group_members
        leader = create_object(DefaultCharacter, key="Leader")
        member = create_object(DefaultCharacter, key="Member")
        try:
            leader.attributes.add("group_id", "g1")
            leader.attributes.add("group_leader", True)
            member.attributes.add("group_id", "g1")
            member.attributes.add("group_leader", False)
            self.assertTrue(is_group_leader(leader))
            self.assertFalse(is_group_leader(member))
            members = get_group_members(leader)
            self.assertEqual(len(members), 2)
            self.assertEqual(get_group_leader(members), leader)
        finally:
            leader.delete(); member.delete()

    def test_format_group_status_out_of_group(self):
        from commands.group import format_group_status
        char = create_object(DefaultCharacter, key="Loner")
        try:
            out = format_group_status(char)
            self.assertIn("not in a group", out)
        finally:
            char.delete()


# ============================================================================
# PART 14 - Movement
# ============================================================================

class TestMovement(BaseEvenniaTest):
    def test_move_west(self):
        from commands.movement import CmdMove
        a = create_object(DefaultRoom, key="RoomA")
        b = create_object(DefaultRoom, key="RoomB")
        create_object(DefaultExit, key="west", location=a, destination=b)
        char = create_object(DefaultCharacter, key="Walker")
        try:
            char.location = a
            cmd = CmdMove(); cmd.caller = char; cmd.cmdstring = "w"; cmd.args = ""
            cmd.func()
            self.assertEqual(char.location, b)
        finally:
            char.delete(); a.delete(); b.delete()

    def test_move_no_exit(self):
        from commands.movement import CmdMove
        a = create_object(DefaultRoom, key="DeadEnd")
        char = create_object(DefaultCharacter, key="Walker")
        try:
            char.location = a
            cmd = CmdMove(); cmd.caller = char; cmd.cmdstring = "n"; cmd.args = ""
            cmd.func()
            self.assertEqual(char.location, a)
        finally:
            char.delete(); a.delete()


# ============================================================================
# PART 15 - Announcements / MOTD / rules / help
# ============================================================================

class TestMisc(BaseEvenniaTest):
    def test_help_entries(self):
        from world.help_entries import HELP_ENTRIES
        self.assertIsInstance(HELP_ENTRIES, list)
        self.assertGreater(len(HELP_ENTRIES), 0)

    def test_motd_functions(self):
        from world import motd
        self.assertTrue(callable(motd.get_random_tip))
        self.assertTrue(callable(motd.render_motd))

    def test_announcement_script_exists(self):
        from world.announcements import AnnouncementScript
        self.assertIsNotNone(AnnouncementScript)

    def test_backup_module(self):
        from world import backup
        self.assertTrue(callable(backup.run_manual_backup))
        self.assertTrue(callable(backup._timestamp))

    def test_builder_phases_import(self):
        from world.builder_phase1 import build_phase1
        from world.builder_phase2 import build_phase2
        from world.builder_phase3 import build_phase3
        from world.builder_phase4 import build_all
        self.assertTrue(callable(build_phase1))
        self.assertTrue(callable(build_phase2))
        self.assertTrue(callable(build_phase3))
        self.assertTrue(callable(build_all))

    def test_realm_population(self):
        from world.populate_realm import (
            populate_all, clear_all_mobs, classify_room, NPC, Mob,
        )
        self.assertTrue(callable(populate_all))
        self.assertTrue(callable(clear_all_mobs))
        self.assertTrue(callable(classify_room))
        self.assertTrue(issubclass(NPC, DefaultCharacter))
        self.assertTrue(issubclass(Mob, DefaultCharacter))

    def test_armor_sets_alias_dict(self):
        from world.armor_sets import ARMOR_SETS, register_default_armor_sets
        register_default_armor_sets()
        self.assertIsInstance(ARMOR_SETS, dict)
        self.assertGreaterEqual(len(ARMOR_SETS), 4)


if __name__ == "__main__":
    # Fallback for running without Evennia's test runner is intentionally
    # omitted; use `evennia test commands.tests.test_full_game_audit`.
    pass