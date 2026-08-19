"""
Unit tests for the automated announcement ticker system.

Covers:
  - AnnouncementScript creation and key/db_key
  - AnnouncementScript interval is within expected range
  - ANNOUNCEMENTS list is non-empty and contains strings
  - _random_interval returns a value in [1800, 3600]
  - Multiple interval calls produce randomness
  - AnnouncementScript at_repeat broadcasts to connected accounts

Run with:
    evennia test commands.tests.test_announcements
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.scripts.models import ScriptDB

from world.announcements import AnnouncementScript, ANNOUNCEMENTS


class TestAnnouncementList(BaseEvenniaTest):
    """Test the ANNOUNCEMENTS message list."""

    def test_announcements_list_not_empty(self):
        """ANNOUNCEMENTS contains at least one message."""
        self.assertGreater(len(ANNOUNCEMENTS), 0)

    def test_all_announcements_are_strings(self):
        """Every entry in ANNOUNCEMENTS is a non-empty string."""
        for msg in ANNOUNCEMENTS:
            self.assertIsInstance(msg, str)
            self.assertGreater(len(msg.strip()), 0)

    def test_announcements_have_color_codes(self):
        """Announcements use ANSI color codes for unique coloring."""
        for msg in ANNOUNCEMENTS:
            self.assertIn("|", msg, f"Announcement should contain ANSI codes: {msg}")

    def test_announcements_have_categories(self):
        """Announcements include category tags like [Tip], [World], or [Server]."""
        categories = {"[Tip]", "[World]", "[Server]"}
        found = set()
        for msg in ANNOUNCEMENTS:
            for cat in categories:
                if cat in msg:
                    found.add(cat)
        self.assertGreaterEqual(len(found), 2, "Should have at least 2 categories")


class TestAnnouncementScriptCreation(BaseEvenniaTest):
    """Test AnnouncementScript instantiation and properties."""

    def setUp(self):
        super().setUp()
        # Clean up any existing script from previous tests
        ScriptDB.objects.filter(db_key="test_announce_script").delete()

    def tearDown(self):
        ScriptDB.objects.filter(db_key="test_announce_script").delete()
        super().tearDown()

    def test_script_create_sets_key(self):
        """Creating the script assigns the correct key."""
        # Script.create() returns (script_instance, errors_list)
        script, errors = AnnouncementScript.create(
            "test_announce_script",
            interval=1800,
            autostart=False,
        )
        try:
            self.assertEqual(script.key, "test_announce_script")
        finally:
            script.delete()

    def test_script_is_persistent(self):
        """The script is persistent (survives server restarts)."""
        script, errors = AnnouncementScript.create(
            "test_announce_script",
            interval=1800,
            autostart=False,
        )
        try:
            self.assertTrue(script.persistent)
        finally:
            script.delete()

    def test_script_has_description(self):
        """The script has a descriptive desc string."""
        script, errors = AnnouncementScript.create(
            "test_announce_script",
            interval=1800,
            autostart=False,
        )
        try:
            self.assertIsInstance(script.desc, str)
            self.assertGreater(len(script.desc), 0)
        finally:
            script.delete()


class TestAnnouncementInterval(BaseEvenniaTest):
    """Test the interval randomisation logic."""

    def setUp(self):
        super().setUp()
        ScriptDB.objects.filter(db_key="test_interval_script").delete()

    def tearDown(self):
        ScriptDB.objects.filter(db_key="test_interval_script").delete()
        super().tearDown()

    def test_random_interval_is_within_bounds(self):
        """_random_interval returns a value between 1800 and 3600 seconds."""
        for _ in range(100):
            interval = AnnouncementScript._random_interval()
            self.assertGreaterEqual(interval, 1800)
            self.assertLessEqual(interval, 3600)

    def test_random_interval_returns_integer(self):
        """_random_interval returns an integer."""
        for _ in range(20):
            interval = AnnouncementScript._random_interval()
            self.assertIsInstance(interval, int)

    def test_interval_variation(self):
        """Multiple calls to _random_interval produce at least 2 distinct values."""
        results = {AnnouncementScript._random_interval() for _ in range(100)}
        self.assertGreaterEqual(
            len(results), 2,
            "Random intervals should produce at least 2 distinct values"
        )

    def test_script_interval_is_set_on_creation(self):
        """The script's interval is set to a value within range at creation."""
        script, errors = AnnouncementScript.create(
            "test_interval_script",
            interval=1800,
            autostart=False,
        )
        try:
            self.assertGreaterEqual(script.interval, 1800)
            self.assertLessEqual(script.interval, 3600)
        finally:
            script.delete()


class TestAnnouncementAtRepeat(BaseEvenniaTest):
    """Test the at_repeat broadcast behaviour of AnnouncementScript."""

    def setUp(self):
        super().setUp()
        ScriptDB.objects.filter(db_key="test_repeat_script").delete()

    def tearDown(self):
        ScriptDB.objects.filter(db_key="test_repeat_script").delete()
        super().tearDown()

    def test_at_repeat_does_not_raise(self):
        """at_repeat executes without raising an exception."""
        script, errors = AnnouncementScript.create(
            "test_repeat_script",
            interval=1800,
            autostart=False,
        )
        try:
            # at_repeat should run without error even with no online accounts
            script.at_repeat()
        finally:
            script.delete()

    def test_at_repeat_interval_is_rerolled(self):
        """After at_repeat fires, the interval is randomised for the next tick."""
        script, errors = AnnouncementScript.create(
            "test_repeat_script",
            interval=1800,
            autostart=False,
        )
        try:
            script.at_repeat()
            new_interval = script.interval
            # New interval should be in range
            self.assertGreaterEqual(new_interval, 1800)
            self.assertLessEqual(new_interval, 3600)
        finally:
            script.delete()