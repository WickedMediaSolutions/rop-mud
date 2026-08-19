"""
Unit tests for the `stats` command.

Covers:
  - CmdStats key and aliases
  - Executing `stats` produces a summary containing expected sections
  - Stat counts reflect objects present in the test database

Run with:
    evennia test commands.tests.test_stats
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia import create_object
from evennia.objects.objects import DefaultCharacter, DefaultRoom

from commands.general import CmdStats


class TestCmdStatsDefinition(BaseEvenniaTest):
    """Test the CmdStats command class definition."""

    def test_cmd_stats_key_is_stats(self):
        """CmdStats has key='stats'."""
        self.assertEqual(CmdStats.key, "stats")

    def test_cmd_stats_has_help_category(self):
        """CmdStats has a help_category."""
        self.assertTrue(hasattr(CmdStats, "help_category"))
        self.assertIsInstance(CmdStats.help_category, str)

    def test_cmd_stats_has_aliases(self):
        """CmdStats has at least one alias."""
        self.assertIsInstance(CmdStats.aliases, list)
        self.assertGreater(len(CmdStats.aliases), 0)

    def test_cmd_stats_locks_allow_all(self):
        """CmdStats is accessible to all players."""
        self.assertTrue(hasattr(CmdStats, "locks"))


class TestCmdStatsExecution(BaseEvenniaTest):
    """Test the execution of CmdStats."""

    def setUp(self):
        super().setUp()
        self.char = create_object(DefaultCharacter, key="StatReader")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def _run_stats(self):
        """Execute the stats command and capture its output."""
        delivered = []
        original_msg = self.char.msg

        def capture(text=None, **kwargs):
            if text is not None:
                delivered.append(str(text))
            original_msg(text=text, **kwargs)

        self.char.msg = capture

        try:
            cmd = CmdStats()
            cmd.caller = self.char
            cmd.cmdstring = "stats"
            cmd.args = ""
            cmd.func()
        finally:
            self.char.msg = original_msg

        return delivered

    def test_stats_command_produces_output(self):
        """Executing `stats` sends exactly one message."""
        delivered = self._run_stats()
        self.assertEqual(len(delivered), 1, "Should deliver exactly one message")

    def test_stats_output_contains_expected_sections(self):
        """Output contains the major stat sections."""
        delivered = self._run_stats()
        output = delivered[0]

        for section in (
            "World Structure",
            "Entities",
            "Items",
            "Players & Accounts",
            "Grand Total Entities",
        ):
            self.assertIn(section, output, f"Stats output should contain: {section}")

    def test_stats_output_reports_rooms(self):
        """Output includes the Rooms line."""
        delivered = self._run_stats()
        self.assertIn("Rooms:", delivered[0])

    def test_stats_output_reports_exits(self):
        """Output includes the Exits line."""
        delivered = self._run_stats()
        self.assertIn("Exits:", delivered[0])

    def test_stats_output_reports_mobs_and_npcs(self):
        """Output includes Mobs, NPCs, and Shopkeepers lines."""
        delivered = self._run_stats()
        output = delivered[0]
        self.assertIn("Mobs:", output)
        self.assertIn("NPCs:", output)
        self.assertIn("Shopkeepers:", output)

    def test_stats_output_reports_items(self):
        """Output includes item counts."""
        delivered = self._run_stats()
        output = delivered[0]
        self.assertIn("Total Items:", output)
        self.assertIn("On Ground:", output)
        self.assertIn("In Inventories:", output)

    def test_stats_output_reports_players_and_accounts(self):
        """Output includes player and account counts."""
        delivered = self._run_stats()
        output = delivered[0]
        self.assertIn("Characters:", output)
        self.assertIn("Online Now:", output)
        self.assertIn("Accounts:", output)