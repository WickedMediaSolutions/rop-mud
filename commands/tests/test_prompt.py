"""
Unit tests for the MajorMUD-style status prompt.

Covers:
  - get_status_prompt() rendering with expected ANSI color codes
  - prompt_enabled toggle via the 'prompt' command
  - at_pre_cmd prompt delivery

Run with:
    evennia test commands.tests.test_prompt
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultRoom, DefaultCharacter
from evennia import create_object


class TestStatusPrompt(BaseEvenniaTest):
    """Test the MajorMUD-style status prompt rendering and toggling."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="TestChar")
        self.char1.attributes.add("hp", 85)
        self.char1.attributes.add("max_hp", 120)
        self.char1.attributes.add("mana", 30)
        self.char1.attributes.add("max_mana", 65)
        self.char1.attributes.add("mv", 42)
        self.char1.attributes.add("max_mv", 100)
        self.char1.attributes.add("xp", 1450)
        self.char1.attributes.add("xp_to_level", 2000)
        self.char1.attributes.add("level", 8)
        self.char1.attributes.add("race", "Human")
        self.char1.attributes.add("class", "Warrior")
        self.char1.attributes.add("alignment", "Good")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()
        super().tearDown()

    # ------------------------------------------------------------------
    # get_status_prompt() rendering
    # ------------------------------------------------------------------

    def test_prompt_renders_health_in_bright_green(self):
        """HP segment should use bright-green ANSI code |g."""
        # Patch get_status_prompt on this instance since we use DefaultCharacter
        from typeclasses.characters import Character
        self.char1.__class__ = Character
        prompt = self.char1.get_status_prompt()
        self.assertIn("|g[HP: 85/120]|n", prompt)

    def test_prompt_renders_mana_in_cyan(self):
        """MP segment should use cyan ANSI code |c."""
        from typeclasses.characters import Character
        self.char1.__class__ = Character
        prompt = self.char1.get_status_prompt()
        self.assertIn("|c[MP: 30/65]|n", prompt)

    def test_prompt_renders_movement_in_bright_yellow(self):
        """MV segment should use bright-yellow ANSI code |y."""
        from typeclasses.characters import Character
        self.char1.__class__ = Character
        prompt = self.char1.get_status_prompt()
        self.assertIn("|y[MV: 42/100]|n", prompt)

    def test_prompt_renders_experience_in_bright_magenta(self):
        """EXP segment should use bright-magenta ANSI code |m."""
        from typeclasses.characters import Character
        self.char1.__class__ = Character
        prompt = self.char1.get_status_prompt()
        self.assertIn("|m[EXP: 1450/2000]|n", prompt)

    def test_prompt_all_segments_present(self):
        """The full prompt should contain all four stat brackets."""
        from typeclasses.characters import Character
        self.char1.__class__ = Character
        prompt = self.char1.get_status_prompt()
        self.assertIn("[HP:", prompt)
        self.assertIn("[MP:", prompt)
        self.assertIn("[MV:", prompt)
        self.assertIn("[EXP:", prompt)

    def test_prompt_defaults_when_attributes_missing(self):
        """When no stats are set, get_status_prompt returns safe defaults."""
        char2 = create_object(DefaultCharacter, key="FreshChar")
        from typeclasses.characters import Character
        char2.__class__ = Character
        prompt = char2.get_status_prompt()
        self.assertIn("[HP: 100/100]", prompt)
        self.assertIn("[MP: 50/50]", prompt)
        self.assertIn("[MV: 100/100]", prompt)
        self.assertIn("[EXP: 0/1000]", prompt)
        char2.delete()

    # ------------------------------------------------------------------
    # prompt toggle command
    # ------------------------------------------------------------------

    def test_prompt_toggle_off(self):
        """Using 'prompt' when ON should disable it."""
        from typeclasses.characters import Character
        self.char1.__class__ = Character
        self.char1.attributes.add("prompt_enabled", True)

        from commands.general import CmdPrompt
        cmd = CmdPrompt()
        cmd.caller = self.char1
        cmd.cmdstring = "prompt"
        cmd.args = ""
        cmd.func()

        self.assertFalse(
            self.char1.attributes.get("prompt_enabled", default=True)
        )

    def test_prompt_toggle_on(self):
        """Using 'prompt' when OFF should re-enable it."""
        from typeclasses.characters import Character
        self.char1.__class__ = Character
        self.char1.attributes.add("prompt_enabled", False)

        from commands.general import CmdPrompt
        cmd = CmdPrompt()
        cmd.caller = self.char1
        cmd.cmdstring = "prompt"
        cmd.args = ""
        cmd.func()

        self.assertTrue(
            self.char1.attributes.get("prompt_enabled", default=False)
        )

    def test_prompt_enabled_by_default(self):
        """New characters should default to prompt_enabled=True."""
        from typeclasses.characters import Character
        char3 = create_object(DefaultCharacter, key="NewChar")
        char3.__class__ = Character
        enabled = char3.attributes.get("prompt_enabled", default=True)
        self.assertTrue(enabled)
        char3.delete()

    def test_prompt_toggle_cycle(self):
        """Toggling twice should return to the original state."""
        from typeclasses.characters import Character
        self.char1.__class__ = Character
        self.char1.attributes.add("prompt_enabled", True)

        from commands.general import CmdPrompt

        # First toggle: ON -> OFF
        cmd = CmdPrompt()
        cmd.caller = self.char1
        cmd.cmdstring = "prompt"
        cmd.args = ""
        cmd.func()
        self.assertFalse(self.char1.attributes.get("prompt_enabled"))

        # Second toggle: OFF -> ON
        cmd2 = CmdPrompt()
        cmd2.caller = self.char1
        cmd2.cmdstring = "prompt"
        cmd2.args = ""
        cmd2.func()
        self.assertTrue(self.char1.attributes.get("prompt_enabled"))

    # ------------------------------------------------------------------
    # at_pre_cmd hook behaviour
    # ------------------------------------------------------------------

    def test_at_pre_cmd_sends_prompt_when_enabled(self):
        """at_pre_cmd should send a prompt via self.msg(prompt=...) when enabled."""
        from typeclasses.characters import Character
        self.char1.__class__ = Character
        self.char1.attributes.add("prompt_enabled", True)

        # Capture calls to self.msg
        captured = []

        def fake_msg(*args, prompt=None, **kwargs):
            if prompt is not None:
                captured.append(prompt)

        import types
        original_msg = self.char1.msg
        self.char1.msg = types.MethodType(fake_msg, self.char1)

        try:
            self.char1.at_pre_cmd()
        finally:
            self.char1.msg = original_msg

        self.assertEqual(len(captured), 1, "Expected one prompt message")
        self.assertIn("[HP:", captured[0])
        self.assertIn("[MP:", captured[0])
        self.assertIn("[MV:", captured[0])
        self.assertIn("[EXP:", captured[0])

    def test_at_pre_cmd_suppresses_prompt_when_disabled(self):
        """at_pre_cmd should NOT send a prompt when prompt_enabled is False."""
        from typeclasses.characters import Character
        self.char1.__class__ = Character
        self.char1.attributes.add("prompt_enabled", False)

        captured = []

        def fake_msg(*args, prompt=None, **kwargs):
            if prompt is not None:
                captured.append(prompt)

        import types
        original_msg = self.char1.msg
        self.char1.msg = types.MethodType(fake_msg, self.char1)

        try:
            self.char1.at_pre_cmd()
        finally:
            self.char1.msg = original_msg

        self.assertEqual(len(captured), 0, "Expected no prompt when disabled")