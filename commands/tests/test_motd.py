"""
Unit tests for the Message of the Day (MOTD) system.

Covers:
  - render_motd produces a string
  - render_motd includes the character name
  - render_motd includes a tip
  - render_motd handles None character gracefully
  - get_random_tip returns a string from the tips list
  - Multiple calls to render_motd may produce different templates/tips

Run with:
    evennia test commands.tests.test_motd
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia import create_object
from evennia.objects.objects import DefaultCharacter, DefaultRoom
from typeclasses.characters import Character

from world.motd import render_motd, get_random_tip, MOTD_TIPS, MOTD_TEMPLATES


class TestMOTDRendering(BaseEvenniaTest):
    """Test the MOTD render_motd function."""

    def setUp(self):
        super().setUp()
        self.char = create_object(DefaultCharacter, key="TestHero")

    def tearDown(self):
        self.char.delete()
        super().tearDown()

    def test_render_motd_returns_string(self):
        """render_motd returns a non-empty string."""
        result = render_motd(self.char)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_render_motd_includes_character_name(self):
        """The rendered MOTD includes the character's name."""
        result = render_motd(self.char)
        self.assertIn("TestHero", result)

    def test_render_motd_includes_server_time(self):
        """The rendered MOTD includes the server time label."""
        result = render_motd(self.char)
        self.assertIn("Server Time", result)

    def test_render_motd_includes_tip_section(self):
        """The rendered MOTD includes a Tip or Wisdom section."""
        result = render_motd(self.char)
        tip_found = "Tip" in result or "Wisdom" in result
        self.assertTrue(tip_found, "MOTD should contain 'Tip' or 'Wisdom'")

    def test_render_motd_handles_none_character(self):
        """render_motd with None falls back to 'Adventurer'."""
        result = render_motd(None)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
        self.assertIn("Adventurer", result)

    def test_multiple_calls_produce_variation(self):
        """Multiple calls to render_motd can produce different outputs."""
        results = set()
        for _ in range(50):
            results.add(render_motd(self.char))
        # With 3 templates and 18 tips, we should get at least 2 unique results
        self.assertGreaterEqual(
            len(results), 2,
            "Multiple calls should produce at least 2 unique MOTD strings"
        )


class TestMOTDTips(BaseEvenniaTest):
    """Test the MOTD tip system."""

    def test_get_random_tip_returns_string(self):
        """get_random_tip returns a non-empty string."""
        tip = get_random_tip()
        self.assertIsInstance(tip, str)
        self.assertGreater(len(tip), 0)

    def test_get_random_tip_is_from_tips_list(self):
        """get_random_tip returns a tip from the MOTD_TIPS list."""
        tip = get_random_tip()
        self.assertIn(tip, MOTD_TIPS)

    def test_tips_list_is_not_empty(self):
        """MOTD_TIPS contains at least one tip."""
        self.assertGreater(len(MOTD_TIPS), 0)

    def test_tips_list_contains_ansi_color_codes(self):
        """Every tip in MOTD_TIPS uses ANSI color codes."""
        for tip in MOTD_TIPS:
            self.assertIn("|", tip, f"Tip should contain ANSI codes: {tip}")


class TestMOTDTemplates(BaseEvenniaTest):
    """Test the MOTD template definitions."""

    def test_templates_list_is_not_empty(self):
        """MOTD_TEMPLATES contains at least one template."""
        self.assertGreater(len(MOTD_TEMPLATES), 0)

    def test_all_templates_are_strings(self):
        """Every entry in MOTD_TEMPLATES is a string."""
        for template in MOTD_TEMPLATES:
            self.assertIsInstance(template, str)

    def test_templates_contain_placeholders(self):
        """Templates contain {name} and {time} and {tip} format placeholders."""
        for template in MOTD_TEMPLATES:
            self.assertIn("{name}", template)
            self.assertIn("{time}", template)
            self.assertIn("{tip}", template)

    def test_templates_format_without_error(self):
        """All templates can be formatted with valid data."""
        for template in MOTD_TEMPLATES:
            try:
                result = template.format(
                    name="TestChar",
                    time="2026-01-01 00:00:00 UTC",
                    tip="Test tip here.",
                )
                self.assertIsInstance(result, str)
                self.assertGreater(len(result), 0)
            except Exception as e:
                self.fail(f"Template formatting failed: {e}")


class TestMOTDOnLogin(BaseEvenniaTest):
    """Test that MOTD is delivered via at_post_login."""

    def setUp(self):
        super().setUp()
        self.char = create_object(Character, key="LoginHero")
        # Simulate a completed character (chargen already done)
        self.char.db.chargen_completed = True

    def tearDown(self):
        self.char.delete()
        super().tearDown()

    def test_at_post_login_displays_motd_when_chargen_done(self):
        """When chargen is complete, at_post_login displays the MOTD."""
        delivered = []
        original_msg = self.char.msg

        def capture(text=None, **kwargs):
            if text is not None:
                delivered.append(str(text))
            original_msg(text=text, **kwargs)

        self.char.msg = capture

        try:
            self.char.at_post_login()
        finally:
            self.char.msg = original_msg

        # Should have received at least one message with MOTD content
        motd_found = any(
            "Welcome" in msg or "realm" in msg.lower() or "Server Time" in msg
            for msg in delivered
        )
        self.assertTrue(
            motd_found,
            "at_post_login should display MOTD when chargen is complete"
        )

    def test_chargen_not_complete_skips_motd(self):
        """When chargen is not done, MOTD is skipped and chargen launches instead."""
        self.char.db.chargen_completed = False

        delivered = []
        original_msg = self.char.msg

        def capture(text=None, **kwargs):
            if text is not None:
                delivered.append(str(text))
            original_msg(text=text, **kwargs)

        self.char.msg = capture

        try:
            self.char.at_post_login()
        finally:
            self.char.msg = original_msg

        # MOTD should NOT appear among the delivered messages
        motd_found = any(
            "Server Time" in msg or "realm awaits" in msg
            for msg in delivered
        )
        self.assertFalse(
            motd_found,
            "MOTD should not display when chargen is not complete"
        )
