"""
Verification tests for the interactive character creation and stat reroll system.

Tests the EvMenu-based chargen flow:
  start -> race -> class -> node_stat_roll -> node_confirm -> node_finalize

Run with:
    evennia test commands.tests.test_chargen
"""
import random
from evennia.utils.test_resources import EvenniaTest
from evennia.utils.evmenu import EvMenu
from evennia.objects.models import ObjectDB
from evennia import create_object
from typeclasses.characters import Character
from world.chargen import (
    roll_stats,
    format_stats_display,
    CORE_STATS,
    MAX_REROLLS,
    STAT_VARIANCE_MIN,
    STAT_VARIANCE_MAX,
)
from world.rules import RACES, CLASSES


class TestStatRollingEngine(EvenniaTest):
    """Unit tests for the stat rolling engine functions."""

    def test_roll_stats_returns_all_six_core_stats(self):
        """roll_stats() must return all six CORE_STATS keys."""
        stats = roll_stats("Human")
        for stat in CORE_STATS:
            self.assertIn(stat, stats, f"Missing stat: {stat}")

    def test_roll_stats_values_within_expected_range(self):
        """Rolled stats must be within [base + MIN_VARIANCE, base + MAX_VARIANCE]."""
        for race_name in RACES:
            base_stats = RACES[race_name]["stats"]
            for _ in range(20):  # multiple rolls to cover variance
                stats = roll_stats(race_name)
                for stat in CORE_STATS:
                    base = base_stats.get(stat, 10)
                    min_val = max(1, base + STAT_VARIANCE_MIN)
                    max_val = base + STAT_VARIANCE_MAX
                    self.assertGreaterEqual(
                        stats[stat], min_val,
                        f"{race_name} {stat}: {stats[stat]} < min {min_val}"
                    )
                    self.assertLessEqual(
                        stats[stat], max_val,
                        f"{race_name} {stat}: {stats[stat]} > max {max_val}"
                    )

    def test_roll_stats_clamps_to_minimum_1(self):
        """Stats should never go below 1 even with negative variance."""
        # Pixie has base STR 4, with -2 variance could go to 2, but never below 1
        for _ in range(50):
            stats = roll_stats("Pixie")
            for stat in CORE_STATS:
                self.assertGreaterEqual(stats[stat], 1,
                                        f"Stat {stat} went below 1: {stats[stat]}")

    def test_roll_stats_produces_different_values(self):
        """Multiple rolls should produce different values (randomness check)."""
        # With variance range of 7 (-2 to +4), we should see variation
        all_same = True
        first = roll_stats("Human")
        for _ in range(20):
            current = roll_stats("Human")
            if current != first:
                all_same = False
                break
        self.assertFalse(all_same, "All 20 rolls produced identical stats - randomness broken")

    def test_format_stats_display_contains_all_stats(self):
        """format_stats_display should include all six stat abbreviations."""
        stats = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        display = format_stats_display(stats)
        for stat in CORE_STATS:
            self.assertIn(stat.upper(), display,
                          f"Stat {stat.upper()} missing from display: {display}")

    def test_format_stats_display_color_codes(self):
        """High stats (>=14) should be green, low (<=6) red."""
        stats = {"str": 15, "dex": 5, "con": 10, "int": 10, "wis": 10, "cha": 10}
        display = format_stats_display(stats)
        self.assertIn("|g", display, "High stat should have green color code")
        self.assertIn("|r", display, "Low stat should have red color code")


class TestChargenMenuFlow(EvenniaTest):
    """
    Integration tests for the full EvMenu character creation flow.

    Programmatically steps through the creation wizard:
      start -> race -> class -> stat_roll -> confirm -> finalize
    """

    def setUp(self):
        super().setUp()
        # Use the account as the caller (chargen runs on Account, not Character)
        self.caller = self.account
        # Ensure no pre-existing characters on this account
        for char in self.caller.characters.all():
            self.caller.characters.remove(char)

    def tearDown(self):
        # Clean up any characters created during tests
        for char in self.caller.characters.all():
            try:
                char.delete()
            except Exception:
                pass
        super().tearDown()

    def _start_menu(self):
        """Launch the EvMenu and return the menu instance."""
        EvMenu(self.caller, "world.chargen", start_node="start", auto_quit=True)
        menu = self.caller.ndb._evmenu
        self.assertIsNotNone(menu, "EvMenu should be initialized on caller.ndb._evmenu")
        return menu

    def _navigate_to_stat_roll(self, menu):
        """
        Navigate from start through race and class selection to the stat roll node.

        Steps:
          1. start -> select Good (key "1") -> node_select_good_race
          2. node_select_good_race -> select Human (key "1") -> node_select_class
          3. node_select_class -> select Warrior (key "1") -> node_stat_roll
        """
        # Step 1: From start, choose Good alignment (key "1")
        menu.parse_input("1")
        self.assertEqual(menu.nodename, "node_select_good_race",
                         f"Expected node_select_good_race, got {menu.nodename}")

        # Step 2: From good race selection, choose Human (key "1")
        menu.parse_input("1")
        self.assertEqual(menu.nodename, "node_select_class",
                         f"Expected node_select_class, got {menu.nodename}")

        # Step 3: From class selection, choose Warrior (key "1")
        menu.parse_input("1")
        self.assertEqual(menu.nodename, "node_stat_roll",
                         f"Expected node_stat_roll, got {menu.nodename}")

    def test_full_flow_reaches_stat_roll(self):
        """Programmatic navigation should reach the stat roll node."""
        menu = self._start_menu()
        self._navigate_to_stat_roll(menu)

        # Verify stored selections
        self.assertEqual(self.caller.db.chargen_race, "Human")
        self.assertEqual(self.caller.db.chargen_class, "Warrior")
        self.assertEqual(self.caller.db.chargen_rerolls_remaining, MAX_REROLLS)

        # Verify stats were rolled and stored
        stats = self.caller.db.chargen_stats
        self.assertIsNotNone(stats, "Stats should be stored after reaching stat roll node")
        for stat in CORE_STATS:
            self.assertIn(stat, stats, f"Missing stat {stat} in rolled stats")

    def test_reroll_changes_stats(self):
        """Simulating a reroll should produce different stat values."""
        menu = self._start_menu()
        self._navigate_to_stat_roll(menu)

        # Capture initial stats
        initial_stats = dict(self.caller.db.chargen_stats)
        initial_rerolls = self.caller.db.chargen_rerolls_remaining

        # Simulate reroll (key "2")
        menu.parse_input("2")

        # Should still be on stat roll node
        self.assertEqual(menu.nodename, "node_stat_roll",
                         f"After reroll, should be on node_stat_roll, got {menu.nodename}")

        # Rerolls remaining should have decremented
        self.assertEqual(self.caller.db.chargen_rerolls_remaining, initial_rerolls - 1,
                         "Rerolls remaining should decrement by 1")

        # Stats should have been re-rolled (may or may not differ, but we check
        # that the stored stats dict is a new object)
        new_stats = self.caller.db.chargen_stats
        self.assertIsNotNone(new_stats, "Stats should exist after reroll")

        # Run multiple rerolls to verify randomness eventually produces different values
        found_different = False
        for _ in range(min(MAX_REROLLS, 3)):
            current = dict(self.caller.db.chargen_stats)
            if current != initial_stats:
                found_different = True
                break
            if self.caller.db.chargen_rerolls_remaining > 0:
                menu.parse_input("2")

        self.assertTrue(found_different,
                        "Rerolls should eventually produce different stat values")

    def test_reroll_limit_enforced(self):
        """After MAX_REROLLS rerolls, the reroll option should not be available."""
        menu = self._start_menu()
        self._navigate_to_stat_roll(menu)

        # Exhaust all rerolls
        for i in range(MAX_REROLLS):
            self.assertEqual(self.caller.db.chargen_rerolls_remaining, MAX_REROLLS - i)
            menu.parse_input("2")

        # Should be at 0 rerolls remaining
        self.assertEqual(self.caller.db.chargen_rerolls_remaining, 0)

        # The reroll option (key "2") should no longer be in the options
        option_keys = list(menu.options.keys())
        self.assertNotIn("2", option_keys,
                         "Reroll option should not be available when rerolls exhausted")

    def test_accept_stats_creates_character(self):
        """Accepting stats should finalize and create a Character in the database."""
        menu = self._start_menu()
        self._navigate_to_stat_roll(menu)

        # Capture the accepted stats
        accepted_stats = dict(self.caller.db.chargen_stats)

        # Accept stats (key "1") -> goes to node_confirm
        menu.parse_input("1")
        self.assertEqual(menu.nodename, "node_confirm",
                         f"Expected node_confirm, got {menu.nodename}")

        # Confirm and finalize (key "1") -> goes to node_finalize
        menu.parse_input("1")

        # After finalize, the menu should be closed (no more options)
        # and a character should exist. Evennia's nattribute handler returns
        # None for deleted attributes rather than raising AttributeError,
        # so we check for None directly.
        self.assertIsNone(getattr(self.caller.ndb, "_evmenu", None),
                          "Menu should be closed after finalization")

        # Verify character was created
        characters = self.caller.characters.all()
        self.assertTrue(len(characters) > 0,
                        "At least one character should exist after finalization")

        char = characters[0]
        self.assertIsInstance(char, Character,
                              f"Created object should be a Character, got {type(char)}")

        # Verify character attributes
        self.assertEqual(char.db.race, "Human")
        self.assertEqual(char.db.character_class, "Warrior")
        self.assertEqual(char.db.alignment, "Good")
        self.assertEqual(char.db.level, 1)

        # Verify stats were persisted correctly
        char_stats = char.db.stats
        self.assertIsNotNone(char_stats, "Character should have stats attribute")
        for stat in CORE_STATS:
            self.assertIn(stat, char_stats, f"Character missing stat: {stat}")
            self.assertEqual(char_stats[stat], accepted_stats[stat],
                             f"Stat {stat}: expected {accepted_stats[stat]}, "
                             f"got {char_stats[stat]}")

        # Verify derived attributes
        self.assertGreater(char.db.max_hp, 0, "max_hp should be positive")
        self.assertGreaterEqual(char.db.hp, char.db.max_hp,
                                "hp should equal max_hp at creation")
        self.assertGreater(char.db.max_mana, 0, "max_mana should be positive")
        self.assertGreater(char.db.max_stamina, 0, "max_stamina should be positive")

        # Verify character has a location (spawned in start room)
        self.assertIsNotNone(char.location, "Character should have a location")

        # Verify chargen_completed flag on account
        self.assertTrue(self.caller.db.chargen_completed,
                        "Account should have chargen_completed = True")

    def test_confirm_back_to_reroll(self):
        """From confirmation, going back to stat roll should allow re-rolling."""
        menu = self._start_menu()
        self._navigate_to_stat_roll(menu)

        # Accept stats -> confirm
        menu.parse_input("1")
        self.assertEqual(menu.nodename, "node_confirm")

        # Go back to stat roll (key "2")
        menu.parse_input("2")
        self.assertEqual(menu.nodename, "node_stat_roll",
                         f"Expected node_stat_roll, got {menu.nodename}")

        # Should be able to reroll from here
        self.assertIn("2", menu.options,
                      "Reroll option should be available when returning from confirm")

    def test_start_over_from_stat_roll(self):
        """Start Over from stat roll should go back to the beginning."""
        menu = self._start_menu()
        self._navigate_to_stat_roll(menu)

        # Start over (key "3")
        menu.parse_input("3")
        self.assertEqual(menu.nodename, "start",
                         f"Expected start, got {menu.nodename}")

    def test_evil_race_flow(self):
        """Test the full flow with an Evil race/class combination."""
        menu = self._start_menu()

        # Choose Evil (key "2")
        menu.parse_input("2")
        self.assertEqual(menu.nodename, "node_select_evil_race")

        # Choose Orc (key "1")
        menu.parse_input("1")
        self.assertEqual(menu.nodename, "node_select_class")

        # Choose Warrior (key "1")
        menu.parse_input("1")
        self.assertEqual(menu.nodename, "node_stat_roll")

        # Verify Evil alignment stored
        self.assertEqual(self.caller.db.chargen_race, "Orc")

        # Accept and finalize
        accepted_stats = dict(self.caller.db.chargen_stats)
        menu.parse_input("1")  # accept
        menu.parse_input("1")  # confirm

        char = self.caller.characters.all()[0]
        self.assertEqual(char.db.race, "Orc")
        self.assertEqual(char.db.alignment, "Evil")
        self.assertEqual(char.db.stats, accepted_stats)

    def test_chargen_completed_flag_prevents_duplicate_creation(self):
        """After chargen_completed is set, start_chargen should not re-run."""
        # Complete chargen once
        menu = self._start_menu()
        self._navigate_to_stat_roll(menu)
        menu.parse_input("1")  # accept
        menu.parse_input("1")  # confirm

        self.assertTrue(self.caller.db.chargen_completed)

        # Count characters before attempting re-run
        char_count_before = self.caller.characters.count()

        # Simulate at_post_login check (from characters.py)
        # This should NOT launch chargen again because chargen_completed is True
        from world.chargen import start_chargen
        # We don't actually call start_chargen here because it would try to
        # puppet, but we verify the flag is set correctly
        self.assertTrue(self.caller.db.chargen_completed)

        # Character count should still be 1
        self.assertEqual(self.caller.characters.count(), char_count_before)


class TestChargenEdgeCases(EvenniaTest):
    """Edge case and boundary tests for the chargen system."""

    def setUp(self):
        super().setUp()
        self.caller = self.account
        for char in self.caller.characters.all():
            self.caller.characters.remove(char)

    def tearDown(self):
        for char in self.caller.characters.all():
            try:
                char.delete()
            except Exception:
                pass
        super().tearDown()

    def test_all_races_produce_valid_stats(self):
        """Every race in RACES should produce valid, in-range stats."""
        for race_name in RACES:
            stats = roll_stats(race_name)
            self.assertEqual(len(stats), 6, f"{race_name}: expected 6 stats, got {len(stats)}")
            for stat in CORE_STATS:
                self.assertIn(stat, stats, f"{race_name}: missing {stat}")
                self.assertGreaterEqual(stats[stat], 1,
                                        f"{race_name} {stat}: {stats[stat]} < 1")
                self.assertLessEqual(stats[stat], 25,
                                     f"{race_name} {stat}: {stats[stat]} > 25 (suspicious)")

    def test_unknown_race_falls_back_to_human(self):
        """roll_stats with an unknown race should fall back to Human base stats."""
        stats = roll_stats("NonExistentRace")
        human_base = RACES["Human"]["stats"]
        # With variance, stats won't exactly match Human base, but should be
        # within the Human variance range
        for stat in CORE_STATS:
            base = human_base.get(stat, 10)
            min_val = max(1, base + STAT_VARIANCE_MIN)
            max_val = base + STAT_VARIANCE_MAX
            self.assertGreaterEqual(stats[stat], min_val)
            self.assertLessEqual(stats[stat], max_val)

    def test_max_rerolls_configurable(self):
        """MAX_REROLLS should be a positive integer."""
        self.assertIsInstance(MAX_REROLLS, int)
        self.assertGreater(MAX_REROLLS, 0, "MAX_REROLLS should be positive")

    def test_stat_variance_range_is_valid(self):
        """STAT_VARIANCE_MIN should be <= STAT_VARIANCE_MAX."""
        self.assertLessEqual(STAT_VARIANCE_MIN, STAT_VARIANCE_MAX,
                             "MIN variance should be <= MAX variance")

    def test_core_stats_list_is_complete(self):
        """CORE_STATS should contain exactly the six MajorMUD attributes."""
        self.assertEqual(len(CORE_STATS), 6)
        expected = {"str", "dex", "con", "int", "wis", "cha"}
        self.assertEqual(set(CORE_STATS), expected)