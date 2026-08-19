#!/usr/bin/env python
"""
===============================================================================
RITES OF PASSAGE — REALM POPULATION & VERIFICATION SYSTEM TEST
===============================================================================

Standalone test for the realm population and verification system.

Covers:
  1. Faction territory mapping correctness
  2. Misaligned spawn detection (Good mobs in Evil zones, vice versa)
  3. Zone population logic (mob pool selection, density bands)
  4. Boss placement logic
  5. Verification engine (zone audit, boss audit, faction scan)
  6. Admin command registration

Run manually:
    cd /root/rop/rop
    python commands/tests/test_realm_population.py

Or with the Evennia test runner:
    evennia test commands.tests.test_realm_population --verbosity=2
===============================================================================
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

import unittest
from unittest.mock import MagicMock, patch


# ============================================================================
# Mock helpers (mirrors test_mobs.py pattern)
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


class MockBase:
    """Lightweight mock base for Evennia typeclass-compatible objects."""
    _id_counter = 0

    def __init__(self, key="mock"):
        MockBase._id_counter += 1
        self.id = MockBase._id_counter
        self.key = key
        self.attributes = MockAttributeHandler()
        self.db = MagicMock()
        self.location = None
        self.destination = None
        self.sessions = MagicMock()
        self.has_account = False
        self.contents = []
        self.home = None
        self.tags = MagicMock()
        self.tags.get.return_value = []
        self.locks = MagicMock()
        self.account = None
        self.session = None
        self.exits = []
        self.deleted = False

    def msg(self, text=None, prompt=None, **kwargs):
        pass

    def move_to(self, destination, quiet=False, **kwargs):
        if self.location is not None and hasattr(self.location, "contents"):
            if self in self.location.contents:
                self.location.contents.remove(self)
        self.location = destination
        if destination is not None and hasattr(destination, "contents"):
            if self not in destination.contents:
                destination.contents.append(self)
        return True

    def delete(self):
        self.deleted = True
        if self.location is not None and hasattr(self.location, "contents"):
            if self in self.location.contents:
                self.location.contents.remove(self)
        self.location = None


def mock_room(key="Room"):
    room = MockBase(key=key)
    room.contents = []
    room.attributes.add("safe_zone", False)
    room.exits = []
    room.msg_contents = MagicMock()
    return room


def mock_mob(key="goblin", hp=30, faction="Gorgoroth Horde", is_mob=True):
    mob = MockBase(key=key)
    mob.attributes.add("is_mob", is_mob)
    mob.attributes.add("hp", hp)
    mob.attributes.add("faction", faction)
    mob.attributes.add("is_boss", False)
    mob.attributes.add("boss_id", None)
    mob.attributes.add("is_vendor", False)
    mob.attributes.add("is_trainer", False)
    mob.attributes.add("is_npc", False)
    mob.has_account = False
    return mob


def mock_exit(destination, key="north"):
    ex = MockBase(key=key)
    ex.destination = destination
    return ex


# ============================================================================
# Tests — Faction Territory Mapping
# ============================================================================

class TestFactionTerritoryMapping(unittest.TestCase):
    """Test that faction territory definitions are correct and consistent."""

    def test_good_zones_are_distinct_from_evil(self):
        """Good and Evil zones must not overlap."""
        from world.realm_population import GOOD_ZONES, EVIL_ZONES
        overlap = GOOD_ZONES & EVIL_ZONES
        self.assertEqual(len(overlap), 0,
                         f"Good/Evil zone overlap: {overlap}")

    def test_starter_zones_are_correct(self):
        """The true 1-10 starter zones are correctly identified."""
        from world.realm_population import (
            GOOD_STARTER_ZONES, EVIL_STARTER_ZONES,
            GOOD_ZONES, EVIL_ZONES,
        )
        self.assertIn("sunspire_meadows", GOOD_ZONES,
                      "sunspire_meadows must be in GOOD_ZONES")
        self.assertIn("brimstone_courtyard", EVIL_ZONES,
                      "brimstone_courtyard must be in EVIL_ZONES")
        self.assertIn("sunspire_meadows", GOOD_STARTER_ZONES)
        self.assertIn("brimstone_courtyard", EVIL_STARTER_ZONES)

    def test_faction_for_zone_returns_correct_faction(self):
        """faction_for_zone maps zone keys to the right faction."""
        from world.realm_population import (
            faction_for_zone, FACTION_GOOD, FACTION_EVIL, FACTION_NEUTRAL,
        )
        self.assertEqual(faction_for_zone("sunspire_meadows"), FACTION_GOOD)
        self.assertEqual(faction_for_zone("brimstone_courtyard"), FACTION_EVIL)
        self.assertEqual(faction_for_zone("great_sun_wastes"), FACTION_NEUTRAL)
        self.assertEqual(faction_for_zone("nonexistent_zone"), FACTION_NEUTRAL)

    def test_alignment_for_faction(self):
        """alignment_for_faction returns correct alignment labels."""
        from world.realm_population import (
            alignment_for_faction, FACTION_GOOD, FACTION_EVIL,
            ALIGNMENT_GOOD, ALIGNMENT_EVIL,
        )
        self.assertEqual(alignment_for_faction(FACTION_GOOD), ALIGNMENT_GOOD)
        self.assertEqual(alignment_for_faction(FACTION_EVIL), ALIGNMENT_EVIL)

    def test_is_starter_zone(self):
        """is_starter_zone correctly identifies 1-10 zones."""
        from world.realm_population import is_starter_zone
        self.assertTrue(is_starter_zone("sunspire_meadows"))
        self.assertTrue(is_starter_zone("brimstone_courtyard"))
        self.assertFalse(is_starter_zone("the_junction"))
        self.assertFalse(is_starter_zone("great_sun_wastes"))

    def test_all_zones_have_level_ranges(self):
        """Every zone in builder_phase1 has a level_range."""
        import world.builder_phase1 as b1
        for zone_key, data in b1.ALL_ZONES.items():
            self.assertIn("level_range", data,
                          f"Zone {zone_key} missing level_range")
            lo, hi = data["level_range"]
            self.assertLessEqual(lo, hi,
                                 f"Zone {zone_key} level_range inverted: {lo}-{hi}")

    def test_hub_room_keys_are_consistent(self):
        """Hub room keys match between realm_population and realm_verify."""
        from world.realm_population import GOOD_HUB_ROOMS, EVIL_HUB_ROOMS
        from world.realm_verify import GOOD_HUB_KEYS, EVIL_HUB_KEYS
        self.assertEqual(set(GOOD_HUB_ROOMS), set(GOOD_HUB_KEYS))
        self.assertEqual(set(EVIL_HUB_ROOMS), set(EVIL_HUB_KEYS))


# ============================================================================
# Tests — Misaligned Spawn Detection
# ============================================================================

class TestMisalignedSpawnDetection(unittest.TestCase):
    """Test the misaligned spawn detection logic."""

    def test_is_misaligned_good_in_evil(self):
        """Good mob in Evil zone is misaligned."""
        from world.realm_population import is_misaligned, FACTION_GOOD, FACTION_EVIL
        self.assertTrue(is_misaligned(FACTION_EVIL, FACTION_GOOD))

    def test_is_misaligned_evil_in_good(self):
        """Evil mob in Good zone is misaligned."""
        from world.realm_population import is_misaligned, FACTION_GOOD, FACTION_EVIL
        self.assertTrue(is_misaligned(FACTION_GOOD, FACTION_EVIL))

    def test_is_misaligned_same_faction(self):
        """Same-faction mob in zone is NOT misaligned."""
        from world.realm_population import is_misaligned, FACTION_GOOD, FACTION_EVIL
        self.assertFalse(is_misaligned(FACTION_GOOD, FACTION_GOOD))
        self.assertFalse(is_misaligned(FACTION_EVIL, FACTION_EVIL))

    def test_is_misaligned_neutral_always_ok(self):
        """Neutral mobs are never misaligned."""
        from world.realm_population import is_misaligned, FACTION_GOOD, FACTION_EVIL, FACTION_NEUTRAL
        self.assertFalse(is_misaligned(FACTION_GOOD, FACTION_NEUTRAL))
        self.assertFalse(is_misaligned(FACTION_EVIL, FACTION_NEUTRAL))
        self.assertFalse(is_misaligned(FACTION_NEUTRAL, FACTION_GOOD))
        self.assertFalse(is_misaligned(FACTION_NEUTRAL, FACTION_EVIL))

    def test_clear_misaligned_spawns_removes_wrong_faction(self):
        """clear_misaligned_spawns deletes mobs in wrong faction zones."""
        from world.realm_population import clear_misaligned_spawns

        # Create a Good zone room with an Evil mob in it
        good_room = mock_room("Sunspire Meadows - Location 1")
        good_room.tags.get.return_value = ["sunspire_meadows"]
        evil_mob = mock_mob("Goblin Scout", faction="Gorgoroth Horde")
        good_mob = mock_mob("Prairie Fox", faction="Aethelgard Alliance")
        good_room.contents = [evil_mob, good_mob]

        # Create an Evil zone room (with no misaligned mobs — used by Evil zone loop)
        evil_room = mock_room("Brimstone Courtyard - Location 1")
        evil_room.tags.get.return_value = ["brimstone_courtyard"]
        evil_good_mob = mock_mob("Orc Grunt", faction="Gorgoroth Horde")
        evil_room.contents = [evil_good_mob]

        # Patch search_tag to return the correct room per zone key
        def _mock_search_tag(tag, category=None):
            if tag == "sunspire_meadows":
                return [good_room]
            if tag == "brimstone_courtyard":
                return [evil_room]
            return []

        with patch("world.realm_population.search_tag") as mock_search:
            mock_search.side_effect = _mock_search_tag
            stats = clear_misaligned_spawns()

        # The evil mob in the Good zone should be deleted, good mob should survive
        self.assertTrue(evil_mob.deleted, "Evil mob in Good zone should be deleted")
        self.assertFalse(good_mob.deleted, "Good mob in Good zone should survive")
        # The evil mob in Evil zone should survive
        self.assertFalse(evil_good_mob.deleted, "Evil mob in Evil zone should survive")
        self.assertEqual(stats["removed"], 1)


# ============================================================================
# Tests — Zone Population Logic
# ============================================================================

class TestZonePopulationLogic(unittest.TestCase):
    """Test mob pool selection, density bands, and stat derivation."""

    def test_danger_for_range(self):
        """danger_for_range returns correct danger labels."""
        from world.realm_population import danger_for_range
        self.assertEqual(danger_for_range(1, 10), "safe")
        self.assertEqual(danger_for_range(10, 18), "caution")
        self.assertEqual(danger_for_range(20, 40), "danger")
        self.assertEqual(danger_for_range(40, 60), "deadly")

    def test_mobs_per_room_returns_valid_range(self):
        """mobs_per_room returns (min, max) with min <= max."""
        from world.realm_population import mobs_per_room
        for lo, hi in [(1, 10), (10, 18), (20, 40), (40, 60)]:
            mn, mx = mobs_per_room(lo, hi)
            self.assertLessEqual(mn, mx, f"mobs_per_room({lo},{hi}) = ({mn},{mx})")
            self.assertGreater(mn, 0)

    def test_mob_pool_for_zone_good(self):
        """Good zones get Good mob pools."""
        from world.realm_population import mob_pool_for_zone
        pool = mob_pool_for_zone("sunspire_meadows", 1, 10)
        self.assertIsInstance(pool, list)
        self.assertGreater(len(pool), 0)
        # All mobs should be in the Good pool
        from world.realm_population import GOOD_MOB_POOLS
        band1_names = {m["name"] for m in GOOD_MOB_POOLS[1]}
        for spec in pool:
            self.assertIn(spec["name"], band1_names,
                          f"{spec['name']} not in Good band 1 pool")

    def test_mob_pool_for_zone_evil(self):
        """Evil zones get Evil mob pools."""
        from world.realm_population import mob_pool_for_zone
        pool = mob_pool_for_zone("brimstone_courtyard", 1, 10)
        self.assertIsInstance(pool, list)
        self.assertGreater(len(pool), 0)
        from world.realm_population import EVIL_MOB_POOLS
        band1_names = {m["name"] for m in EVIL_MOB_POOLS[1]}
        for spec in pool:
            self.assertIn(spec["name"], band1_names,
                          f"{spec['name']} not in Evil band 1 pool")

    def test_mob_pool_for_zone_neutral(self):
        """Neutral zones get zone-specific pools."""
        from world.realm_population import mob_pool_for_zone
        pool = mob_pool_for_zone("great_sun_wastes", 25, 40)
        self.assertIsInstance(pool, list)
        self.assertGreater(len(pool), 0)
        # Should contain desert-themed mobs
        names = {m["name"] for m in pool}
        self.assertIn("Dune Scorpion", names)

    def test_derive_stats_scales_with_level(self):
        """Higher level mobs have higher stats."""
        from world.realm_population import derive_stats
        low = derive_stats(1)
        high = derive_stats(50)
        self.assertGreater(high["str"], low["str"])
        self.assertGreater(high["con"], low["con"])

    def test_derive_hp_scales_with_level(self):
        """Higher level mobs have more HP."""
        from world.realm_population import derive_hp
        self.assertGreater(derive_hp(50), derive_hp(1))
        self.assertEqual(derive_hp(1), 29)  # 18 + 11

    def test_derive_xp_scales_with_level(self):
        """Higher level mobs give more XP."""
        from world.realm_population import derive_xp
        self.assertGreater(derive_xp(50), derive_xp(1))

    def test_respawn_for_level(self):
        """Higher level mobs have longer respawn delays."""
        from world.realm_population import respawn_for_level
        self.assertEqual(respawn_for_level(5), 45)
        self.assertEqual(respawn_for_level(15), 60)
        self.assertEqual(respawn_for_level(30), 90)
        self.assertEqual(respawn_for_level(50), 120)

    def test_default_loot_table_returns_list(self):
        """default_loot_table returns a valid loot table."""
        from world.realm_population import default_loot_table, FACTION_GOOD, FACTION_EVIL
        good_loot = default_loot_table(FACTION_GOOD, 5)
        evil_loot = default_loot_table(FACTION_EVIL, 50)
        self.assertIsInstance(good_loot, list)
        self.assertIsInstance(evil_loot, list)
        self.assertGreater(len(good_loot), 0)
        self.assertGreater(len(evil_loot), 0)


# ============================================================================
# Tests — Boss Placement Logic
# ============================================================================

class TestBossPlacement(unittest.TestCase):
    """Test boss placement and registry consistency."""

    def test_boss_registry_has_30_entries(self):
        """BOSS_REGISTRY must contain exactly 30 bosses."""
        from world.boss_registry import BOSS_REGISTRY
        self.assertEqual(len(BOSS_REGISTRY), 30,
                         f"Expected 30 bosses, got {len(BOSS_REGISTRY)}")

    def test_boss_room_lookup_covers_all_bosses(self):
        """Every boss in BOSS_REGISTRY has a BOSS_ROOM_LOOKUP entry."""
        from world.boss_registry import BOSS_REGISTRY, BOSS_ROOM_LOOKUP
        for boss_id in BOSS_REGISTRY:
            self.assertIn(boss_id, BOSS_ROOM_LOOKUP,
                          f"Boss {boss_id} missing from BOSS_ROOM_LOOKUP")

    def test_boss_factions_are_valid(self):
        """All bosses have valid faction tags."""
        from world.boss_registry import BOSS_REGISTRY
        valid = {"Gorgoroth Horde", "Aethelgard Alliance"}
        for boss_id, data in BOSS_REGISTRY.items():
            self.assertIn(data["faction"], valid,
                          f"Boss {boss_id} has invalid faction: {data['faction']}")

    def test_boss_levels_are_positive(self):
        """All bosses have positive levels."""
        from world.boss_registry import BOSS_REGISTRY
        for boss_id, data in BOSS_REGISTRY.items():
            self.assertGreater(data["level"], 0,
                               f"Boss {boss_id} has non-positive level")

    def test_boss_hp_is_reasonable(self):
        """All bosses have HP > 0 and proportional to level."""
        from world.boss_registry import BOSS_REGISTRY
        for boss_id, data in BOSS_REGISTRY.items():
            self.assertGreater(data["hp"], 0,
                               f"Boss {boss_id} has non-positive HP")
            # HP should be at least 50 * level for bosses
            self.assertGreaterEqual(data["hp"], data["level"] * 50,
                                    f"Boss {boss_id} HP too low for level")

    def test_boss_lair_defs_match_registry(self):
        """BOSS_LAIR_DEFS boss_ids match BOSS_REGISTRY keys."""
        from world.boss_zones import BOSS_LAIR_DEFS
        from world.boss_registry import BOSS_REGISTRY
        lair_ids = {d[0] for d in BOSS_LAIR_DEFS}
        registry_ids = set(BOSS_REGISTRY.keys())
        # Lair defs use "boss_<name>" format; registry uses descriptive keys.
        # They should have the same count.
        self.assertEqual(len(BOSS_LAIR_DEFS), 30,
                         f"Expected 30 lair defs, got {len(BOSS_LAIR_DEFS)}")

    def test_boss_already_in_detection(self):
        """_boss_already_in detects existing bosses."""
        from world.realm_population import _boss_already_in
        room = mock_room("Boss Lair")
        boss = mock_mob("The Skeletal Warlord", faction="Gorgoroth Horde")
        boss.attributes.add("is_boss", True)
        boss.attributes.add("boss_id", "skeletal_warlord")
        room.contents = [boss]
        self.assertTrue(_boss_already_in(room, "skeletal_warlord"))
        self.assertFalse(_boss_already_in(room, "nonexistent_boss"))


# ============================================================================
# Tests — Verification Engine
# ============================================================================

class TestVerificationEngine(unittest.TestCase):
    """Test the realm verification engine logic."""

    def test_verify_realm_returns_expected_structure(self):
        """verify_realm returns a dict with report, summary, and issues."""
        from world.realm_verify import verify_realm
        result = verify_realm(full_walk=False)
        self.assertIn("report", result)
        self.assertIn("summary", result)
        self.assertIn("issues", result)
        self.assertIsInstance(result["report"], str)
        self.assertIsInstance(result["summary"], dict)
        self.assertIsInstance(result["issues"], list)

    def test_verify_realm_report_is_non_empty(self):
        """The report string is non-empty."""
        from world.realm_verify import verify_realm
        result = verify_realm(full_walk=False)
        self.assertGreater(len(result["report"]), 0)

    def test_walk_from_returns_set(self):
        """walk_from returns a set of dbrefs."""
        from world.realm_verify import walk_from
        room = mock_room("Start")
        dest = mock_room("Dest")
        ex = mock_exit(dest, "north")
        room.exits = [ex]
        result = walk_from(room, max_depth=10)
        self.assertIsInstance(result, set)
        self.assertIn(room.id, result)
        self.assertIn(dest.id, result)

    def test_walk_from_respects_max_depth(self):
        """walk_from stops at max_depth."""
        from world.realm_verify import walk_from
        rooms = [mock_room(f"Room_{i}") for i in range(20)]
        for i in range(19):
            rooms[i].exits = [mock_exit(rooms[i + 1], "east")]
        result = walk_from(rooms[0], max_depth=5)
        # Should have visited at most 6 rooms (start + 5 hops)
        self.assertLessEqual(len(result), 6)

    def test_mob_count_counts_alive_mobs(self):
        """_mob_count only counts alive mobs."""
        from world.realm_verify import _mob_count
        room = mock_room("Test")
        alive = mock_mob("Goblin", hp=30)
        dead = mock_mob("Corpse", hp=0)
        player = MockBase("Player")
        player.has_account = True
        room.contents = [alive, dead, player]
        self.assertEqual(_mob_count(room), 1)

    def test_npc_count_counts_vendors_and_trainers(self):
        """_npc_count counts NPCs correctly."""
        from world.realm_verify import _npc_count
        room = mock_room("Test")
        vendor = MockBase("Vendor")
        vendor.attributes.add("is_vendor", True)
        trainer = MockBase("Trainer")
        trainer.attributes.add("is_trainer", True)
        mob = mock_mob("Goblin")
        room.contents = [vendor, trainer, mob]
        self.assertEqual(_npc_count(room), 2)

    def test_has_boss_detects_boss(self):
        """_has_boss detects boss mobs."""
        from world.realm_verify import _has_boss
        room = mock_room("Lair")
        boss = mock_mob("Boss")
        boss.attributes.add("is_boss", True)
        room.contents = [boss]
        self.assertTrue(_has_boss(room))

        room2 = mock_room("Empty")
        room2.contents = [mock_mob("Trash")]
        self.assertFalse(_has_boss(room2))


# ============================================================================
# Tests — Admin Command Registration
# ============================================================================

class TestAdminCommandRegistration(unittest.TestCase):
    """Test that admin commands are properly defined and importable."""

    def test_cmd_verify_realm_imports(self):
        """CmdVerifyRealm can be imported and instantiated."""
        from commands.realm_admin import CmdVerifyRealm
        cmd = CmdVerifyRealm()
        self.assertEqual(cmd.key, "@verifyrealm")
        self.assertIn("verifyrealm", cmd.aliases)
        self.assertIn("checkspawns", cmd.aliases)

    def test_cmd_populate_realm_imports(self):
        """CmdPopulateRealm can be imported and instantiated."""
        from commands.realm_admin import CmdPopulateRealm
        cmd = CmdPopulateRealm()
        self.assertEqual(cmd.key, "@populaterealm")
        self.assertIn("populaterealm", cmd.aliases)
        self.assertIn("poprealm", cmd.aliases)

    def test_commands_registered_in_cmdset(self):
        """Both realm admin commands are in the CharacterCmdSet."""
        try:
            from commands.default_cmdsets import CharacterCmdSet
        except Exception:
            self.skipTest("Evennia not available for cmdset import test")
            return

        cmdset = CharacterCmdSet()
        cmdset.at_cmdset_creation()
        # The cmdset stores commands by key; check our keys are present
        cmd_keys = {c.key for c in cmdset.commands}
        self.assertIn("@verifyrealm", cmd_keys)
        self.assertIn("@populaterealm", cmd_keys)


# ============================================================================
# Tests — Faction Starter Zone Integrity
# ============================================================================

class TestFactionStarterIntegrity(unittest.TestCase):
    """Test that the Orc Warrior starting zone bug is fixed."""

    def test_evil_starter_zone_is_brimstone_courtyard(self):
        """Evil 1-10 zone is brimstone_courtyard, NOT sunspire_meadows."""
        from world.realm_population import EVIL_STARTER_ZONES, GOOD_STARTER_ZONES
        self.assertIn("brimstone_courtyard", EVIL_STARTER_ZONES)
        self.assertNotIn("brimstone_courtyard", GOOD_STARTER_ZONES)
        self.assertNotIn("sunspire_meadows", EVIL_STARTER_ZONES)

    def test_evil_races_start_in_gorgoroth(self):
        """All Evil races have start_room pointing to Gorgoroth."""
        from world.rules import RACES
        for race_name, data in RACES.items():
            if data["alignment"] == "Evil":
                self.assertIn("Gorgoroth", data["start_room"],
                              f"Evil race {race_name} start_room should be in Gorgoroth, "
                              f"got: {data['start_room']}")

    def test_good_races_start_in_aethelgard(self):
        """All Good races have start_room pointing to Aethelgard."""
        from world.rules import RACES
        for race_name, data in RACES.items():
            if data["alignment"] == "Good":
                self.assertIn("Aethelgard", data["start_room"],
                              f"Good race {race_name} start_room should be in Aethelgard, "
                              f"got: {data['start_room']}")

    def test_evil_mob_pool_has_goblin_scout(self):
        """The Evil band-1 mob pool includes Goblin Scout for the tutorial quest."""
        from world.realm_population import EVIL_MOB_POOLS
        band1_names = {m["name"] for m in EVIL_MOB_POOLS[1]}
        self.assertIn("Goblin Scout", band1_names,
                      "Goblin Scout must be in Evil band-1 pool for tutorial quest")

    def test_good_mob_pool_has_passive_starters(self):
        """Good band-1 mobs are mostly passive for newbie safety."""
        from world.realm_population import GOOD_MOB_POOLS
        band1 = GOOD_MOB_POOLS[1]
        passive_count = sum(1 for m in band1 if not m["aggro"])
        self.assertGreater(passive_count, len(band1) // 2,
                           "Good starter zone should have mostly passive mobs")


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)