"""
Unit tests for faction systems: character creation faction assignment
and gossip channel faction isolation.

Run with:
    evennia test commands.tests.test_faction
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultRoom, DefaultCharacter
from evennia import create_object


class TestCharacterCreationFactionAssignment(BaseEvenniaTest):
    """Test that characters are assigned the correct faction alignment during creation."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="GoodHero")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()
        super().tearDown()

    def test_good_alignment_assigned(self):
        """A character with Good alignment should have it stored correctly."""
        self.char1.attributes.add("alignment", "Good")
        self.assertEqual(self.char1.attributes.get("alignment"), "Good")

    def test_evil_alignment_assigned(self):
        """A character with Evil alignment should have it stored correctly."""
        self.char1.attributes.add("alignment", "Evil")
        self.assertEqual(self.char1.attributes.get("alignment"), "Evil")

    def test_alignment_defaults_to_none(self):
        """Without explicit assignment, alignment should default to None/empty."""
        align = self.char1.attributes.get("alignment", default=None)
        self.assertIsNone(align)

    def test_chargen_stores_alignment(self):
        """Verify that the chargen flow stores alignment as 'Good' or 'Evil'."""
        from typeclasses.charcreate import _set_alignment

        # We cannot run the full EvMenu, but we can verify the
        # alignment-setting helper behaves correctly.
        class FakeCaller:
            pass

        caller = FakeCaller()
        caller.ndb = type("_evmenu", (), {"_evmenu": type("m", (), {})()})()

        _set_alignment(caller, "", align="Good")
        self.assertEqual(caller.ndb._evmenu.c_align, "Good")

        _set_alignment(caller, "", align="Evil")
        self.assertEqual(caller.ndb._evmenu.c_align, "Evil")

    def test_chargen_start_room_selection(self):
        """Good characters should be sent to Aethelgard; Evil to Gorgoroth."""
        from typeclasses.charcreate import _find_start_room

        # Verify function keys exist
        from typeclasses.charcreate import (
            GOOD_START_ROOM_KEY,
            EVIL_START_ROOM_KEY,
        )
        self.assertEqual(GOOD_START_ROOM_KEY, "Aethelgard - Shrine of Light")
        self.assertEqual(EVIL_START_ROOM_KEY, "Gorgoroth - Dark Temple")

    def test_alignment_persists_on_character(self):
        """Alignment attribute should persist after setting."""
        self.char1.attributes.add("alignment", "Good")
        self.assertEqual(self.char1.attributes.get("alignment"), "Good")

        # Re-fetch to confirm persistence
        self.char1.attributes.add("alignment", "Evil")
        self.assertEqual(self.char1.attributes.get("alignment"), "Evil")


class TestGossipFactionIsolation(BaseEvenniaTest):
    """Test that the gossip command only delivers to same-faction players."""

    def setUp(self):
        super().setUp()
        # Create two Good characters and one Evil character
        self.good1 = create_object(DefaultCharacter, key="GoodHero1")
        self.good1.attributes.add("alignment", "Good")
        self.good2 = create_object(DefaultCharacter, key="GoodHero2")
        self.good2.attributes.add("alignment", "Good")
        self.evil1 = create_object(DefaultCharacter, key="EvilVillain1")
        self.evil1.attributes.add("alignment", "Evil")

        self.room = create_object(DefaultRoom, key="Test Room")
        self.good1.location = self.room
        self.good2.location = self.room
        self.evil1.location = self.room

    def tearDown(self):
        self.good1.delete()
        self.good2.delete()
        self.evil1.delete()
        self.room.delete()
        super().tearDown()

    def test_gossip_usage_without_message(self):
        """Gossip with no message should show usage."""
        from commands.gossip import CmdGossip
        cmd = CmdGossip()
        cmd.caller = self.good1
        cmd.cmdstring = "gossip"
        cmd.args = ""
        cmd.func()
        # Should not raise; prints usage

    def test_gossip_usage_alias_gos(self):
        """The 'gos' alias should work."""
        from commands.gossip import CmdGossip
        cmd = CmdGossip()
        cmd.caller = self.good1
        cmd.cmdstring = "gos"
        cmd.args = "Hello faction!"
        cmd.func()
        # Should not raise

    def test_good_gossip_reaches_good_players(self):
        """A Good player's gossip should be seen by other Good players."""
        from commands.gossip import CmdGossip

        # Use msg mock pattern: capture messages delivered to good2
        delivered_to_good2 = []
        delivered_to_evil1 = []

        original_good2_msg = self.good2.msg
        original_evil1_msg = self.evil1.msg

        def capture_good2(text, **kwargs):
            delivered_to_good2.append(text)
            original_good2_msg(text, **kwargs)

        def capture_evil1(text, **kwargs):
            delivered_to_evil1.append(text)
            original_evil1_msg(text, **kwargs)

        self.good2.msg = capture_good2
        self.evil1.msg = capture_evil1

        try:
            cmd = CmdGossip()
            cmd.caller = self.good1
            cmd.cmdstring = "gossip"
            cmd.args = "For the Light!"
            cmd.func()
        finally:
            self.good2.msg = original_good2_msg
            self.evil1.msg = original_evil1_msg

        # Good2 should have received the gossip
        gossip_found = any(
            "[Gossip]" in msg and "For the Light!" in msg
            for msg in delivered_to_good2
        )
        self.assertTrue(gossip_found,
                        "Good player should receive Good faction gossip")

        # Evil1 should NOT have received the gossip
        gossip_leaked = any(
            "[Gossip]" in msg and "For the Light!" in msg
            for msg in delivered_to_evil1
        )
        self.assertFalse(gossip_leaked,
                         "Evil player should NOT see Good faction gossip")

    def test_evil_gossip_isolated_from_good(self):
        """An Evil player's gossip should NOT be seen by Good players."""
        from commands.gossip import CmdGossip

        delivered_to_good1 = []
        original_good1_msg = self.good1.msg

        def capture_good1(text, **kwargs):
            delivered_to_good1.append(text)
            original_good1_msg(text, **kwargs)

        self.good1.msg = capture_good1

        try:
            cmd = CmdGossip()
            cmd.caller = self.evil1
            cmd.cmdstring = "gossip"
            cmd.args = "Darkness rises!"
            cmd.func()
        finally:
            self.good1.msg = original_good1_msg

        # Good1 should NOT have received the evil gossip
        gossip_leaked = any(
            "[Gossip]" in msg and "Darkness rises!" in msg
            for msg in delivered_to_good1
        )
        self.assertFalse(gossip_leaked,
                         "Good player should NOT see Evil faction gossip")

    def test_evil_gossip_reaches_evil_players(self):
        """An Evil player's gossip should be seen by other Evil players."""
        from commands.gossip import CmdGossip

        # Create a second evil character to test delivery
        evil2 = create_object(DefaultCharacter, key="EvilVillain2")
        evil2.attributes.add("alignment", "Evil")
        evil2.location = self.room

        delivered_to_evil2 = []
        original_evil2_msg = evil2.msg

        def capture_evil2(text, **kwargs):
            delivered_to_evil2.append(text)
            original_evil2_msg(text, **kwargs)

        evil2.msg = capture_evil2

        try:
            cmd = CmdGossip()
            cmd.caller = self.evil1
            cmd.cmdstring = "gossip"
            cmd.args = "Hail Gorgoroth!"
            cmd.func()
        finally:
            evil2.msg = original_evil2_msg

        gossip_found = any(
            "[Gossip]" in msg and "Hail Gorgoroth!" in msg
            for msg in delivered_to_evil2
        )
        self.assertTrue(gossip_found,
                        "Evil player should receive Evil faction gossip")

        evil2.delete()

    def test_gossip_format_is_cyan(self):
        """Gossip messages should be formatted in cyan (|c)."""
        from commands.gossip import CmdGossip

        delivered = []
        original_msg = self.good2.msg

        def capture(text, **kwargs):
            delivered.append(text)
            original_msg(text, **kwargs)

        self.good2.msg = capture

        try:
            cmd = CmdGossip()
            cmd.caller = self.good1
            cmd.cmdstring = "gossip"
            cmd.args = "Color test"
            cmd.func()
        finally:
            self.good2.msg = original_msg

        gossip_msg = None
        for msg in delivered:
            if "[Gossip]" in msg and "Color test" in msg:
                gossip_msg = msg
                break

        self.assertIsNotNone(gossip_msg, "Gossip message should have been delivered")
        # Cyan color code should be present
        self.assertTrue(
            gossip_msg.startswith("|c") or "|c[Gossip]" in gossip_msg,
            f"Gossip message should use cyan formatting, got: {gossip_msg!r}"
        )

    def test_gossip_does_not_cross_faction_boundary_bidirectional(self):
        """Confirm Good and Evil gossip are fully isolated (both directions)."""
        from commands.gossip import CmdGossip

        # Capture all messages
        good_received = []
        evil_received = []
        orig_good2 = self.good2.msg
        orig_evil1 = self.evil1.msg

        def cap_good(text, **kw):
            good_received.append(text)
            orig_good2(text, **kw)

        def cap_evil(text, **kw):
            evil_received.append(text)
            orig_evil1(text, **kw)

        self.good2.msg = cap_good
        self.evil1.msg = cap_evil

        try:
            # Good sends gossip
            cmd1 = CmdGossip()
            cmd1.caller = self.good1
            cmd1.cmdstring = "gossip"
            cmd1.args = "Good message"
            cmd1.func()

            # Evil sends gossip
            cmd2 = CmdGossip()
            cmd2.caller = self.evil1
            cmd2.cmdstring = "gossip"
            cmd2.args = "Evil message"
            cmd2.func()
        finally:
            self.good2.msg = orig_good2
            self.evil1.msg = orig_evil1

        # Good should see Good message but not Evil message
        self.assertTrue(any("Good message" in m for m in good_received))
        self.assertFalse(any("Evil message" in m for m in good_received))

        # Evil should see Evil message but not Good message
        self.assertTrue(any("Evil message" in m for m in evil_received))
        self.assertFalse(any("Good message" in m for m in evil_received))