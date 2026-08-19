"""
Unit tests for the `rules` command and RULES_TEXT constant.

Covers:
  - CmdRules key and aliases
  - Executing `rules` displays RULES_TEXT
  - RULES_TEXT is a non-empty string
  - RULES_TEXT contains expected rule categories
  - CmdRules is importable and callable

Run with:
    evennia test commands.tests.test_rules
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia import create_object
from evennia.objects.objects import DefaultCharacter, DefaultRoom

from commands.general import CmdRules
from world.rules import RULES_TEXT


class TestRulesText(BaseEvenniaTest):
    """Test the RULES_TEXT constant in world/rules.py."""

    def test_rules_text_is_non_empty_string(self):
        """RULES_TEXT is a non-empty string."""
        self.assertIsInstance(RULES_TEXT, str)
        self.assertGreater(len(RULES_TEXT.strip()), 0)

    def test_rules_text_contains_expected_sections(self):
        """RULES_TEXT contains the expected rule categories."""
        sections = [
            "GENERAL CONDUCT",
            "ACCOUNT RULES",
            "CHANNEL RULES",
            "PUNISHMENTS",
        ]
        for section in sections:
            self.assertIn(
                section, RULES_TEXT,
                f"RULES_TEXT should contain section: {section}"
            )

    def test_rules_text_contains_ansi_color_codes(self):
        """RULES_TEXT uses ANSI color codes for formatting."""
        self.assertIn("|", RULES_TEXT, "RULES_TEXT should contain ANSI codes")

    def test_rules_text_has_header(self):
        """RULES_TEXT has a recognizable header."""
        self.assertIn("Rules of the Realm", RULES_TEXT)

    def test_rules_text_contains_rule_numbers(self):
        """RULES_TEXT contains numbered rules."""
        for i in range(1, 16):
            self.assertIn(
                f"Rule {i}:", RULES_TEXT,
                f"RULES_TEXT should contain Rule {i}"
            )


class TestCmdRulesDefinition(BaseEvenniaTest):
    """Test the CmdRules command class definition."""

    def test_cmd_rules_key_is_rules(self):
        """CmdRules has key='rules'."""
        self.assertEqual(CmdRules.key, "rules")

    def test_cmd_rules_has_help_category(self):
        """CmdRules has a help_category."""
        self.assertTrue(hasattr(CmdRules, "help_category"))
        self.assertIsInstance(CmdRules.help_category, str)

    def test_cmd_rules_has_aliases(self):
        """CmdRules has at least one alias."""
        self.assertIsInstance(CmdRules.aliases, list)
        self.assertGreater(len(CmdRules.aliases), 0)
        self.assertIn("guidelines", CmdRules.aliases)

    def test_cmd_rules_locks_allow_all(self):
        """CmdRules is accessible to all players."""
        self.assertTrue(hasattr(CmdRules, "locks"))


class TestCmdRulesExecution(BaseEvenniaTest):
    """Test the execution of CmdRules."""

    def setUp(self):
        super().setUp()
        self.char = create_object(DefaultCharacter, key="RuleReader")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_rules_command_displays_rules_text(self):
        """Executing `rules` sends RULES_TEXT to the caller."""
        delivered = []
        original_msg = self.char.msg

        def capture(text=None, **kwargs):
            if text is not None:
                delivered.append(str(text))
            original_msg(text=text, **kwargs)

        self.char.msg = capture

        try:
            cmd = CmdRules()
            cmd.caller = self.char
            cmd.cmdstring = "rules"
            cmd.args = ""
            cmd.func()
        finally:
            self.char.msg = original_msg

        self.assertEqual(len(delivered), 1, "Should deliver exactly one message")
        self.assertIn("GENERAL CONDUCT", delivered[0])
        self.assertIn("Rules of the Realm", delivered[0])

    def test_rules_command_output_matches_constant(self):
        """The output of `rules` matches RULES_TEXT exactly."""
        delivered = []
        original_msg = self.char.msg

        def capture(text=None, **kwargs):
            if text is not None:
                delivered.append(str(text))
            original_msg(text=text, **kwargs)

        self.char.msg = capture

        try:
            cmd = CmdRules()
            cmd.caller = self.char
            cmd.cmdstring = "rules"
            cmd.args = ""
            cmd.func()
        finally:
            self.char.msg = original_msg

        self.assertEqual(delivered[0], RULES_TEXT)

    def test_rules_command_ignores_extra_args(self):
        """`rules some extra text` still displays the full rules."""
        delivered = []
        original_msg = self.char.msg

        def capture(text=None, **kwargs):
            if text is not None:
                delivered.append(str(text))
            original_msg(text=text, **kwargs)

        self.char.msg = capture

        try:
            cmd = CmdRules()
            cmd.caller = self.char
            cmd.cmdstring = "rules"
            cmd.args = "extra junk"
            cmd.func()
        finally:
            self.char.msg = original_msg

        self.assertEqual(len(delivered), 1)
        self.assertIn("GENERAL CONDUCT", delivered[0])