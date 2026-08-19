"""
Unit tests for the Numbered Broadcast Channels (bc) command.

Tests:
  - Tuning into a channel (bc <number>)
  - Switching between channels
  - Broadcasting messages to channel members
  - Leaving a channel (bc leave / bc off)
  - Cross-faction messaging (no alignment isolation)
  - Message format includes channel number
  - Multicast delivers to all on same channel, not others
  - Edge cases: no args, not tuned, invalid number, channel < 1

Run with:
    evennia test commands.tests.test_broadcast
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia import create_object
from evennia.objects.objects import DefaultRoom, DefaultCharacter

from commands.broadcast import CmdBc


# ---------------------------------------------------------------------------
# Channel Tuning Tests
# ---------------------------------------------------------------------------

class TestBcTune(BaseEvenniaTest):
    """Test the bc channel tuning functionality."""

    def setUp(self):
        super().setUp()
        self.char = create_object(DefaultCharacter, key="TestPlayer")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_tune_into_channel_21(self):
        """`bc 21` tunes the player into channel 21."""
        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = "21"
        cmd.func()

        self.assertEqual(self.char.attributes.get("bc_channel"), 21)

    def test_tune_into_channel_1(self):
        """`bc 1` tunes the player into channel 1."""
        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = "1"
        cmd.func()

        self.assertEqual(self.char.attributes.get("bc_channel"), 1)

    def test_tune_into_channel_999(self):
        """`bc 999` tunes the player into channel 999."""
        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = "999"
        cmd.func()

        self.assertEqual(self.char.attributes.get("bc_channel"), 999)

    def test_switch_channel(self):
        """Switching channels updates the tuned channel."""
        self.char.attributes.add("bc_channel", 21)

        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = "42"
        cmd.func()

        self.assertEqual(self.char.attributes.get("bc_channel"), 42)

    def test_tune_to_same_channel_no_change(self):
        """Tuning to the same channel does not change anything."""
        self.char.attributes.add("bc_channel", 21)

        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = "21"
        cmd.func()

        self.assertEqual(self.char.attributes.get("bc_channel"), 21)

    def test_channel_less_than_1_rejected(self):
        """Channel numbers less than 1 are rejected."""
        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = "0"
        cmd.func()

        self.assertIsNone(self.char.attributes.get("bc_channel", default=None))

    def test_non_numeric_channel_rejected(self):
        """Non-numeric channel arguments do not tune."""
        self.char.attributes.add("bc_channel", 21)  # pre-tuned

        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = "abc"
        cmd.func()

        # Non-numeric input should be treated as a message, not change channel
        # Since char is already on channel 21, it should stay on 21
        self.assertEqual(self.char.attributes.get("bc_channel"), 21)

    def test_no_args_shows_usage(self):
        """`bc` with no arguments shows usage."""
        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = ""
        cmd.func()
        # Should not raise


# ---------------------------------------------------------------------------
# Channel Leave Tests
# ---------------------------------------------------------------------------

class TestBcLeave(BaseEvenniaTest):
    """Test leaving broadcast channels."""

    def setUp(self):
        super().setUp()
        self.char = create_object(DefaultCharacter, key="TestPlayer")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_leave_channel(self):
        """`bc leave` removes the player from the channel."""
        self.char.attributes.add("bc_channel", 21)

        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = "leave"
        cmd.func()

        self.assertIsNone(self.char.attributes.get("bc_channel", default=None))

    def test_leave_off_alias(self):
        """`bc off` also leaves the channel."""
        self.char.attributes.add("bc_channel", 21)

        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = "off"
        cmd.func()

        self.assertIsNone(self.char.attributes.get("bc_channel", default=None))

    def test_leave_case_insensitive(self):
        """`bc LEAVE` or `bc Off` works case-insensitively."""
        self.char.attributes.add("bc_channel", 21)

        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = "LEAVE"
        cmd.func()

        self.assertIsNone(self.char.attributes.get("bc_channel", default=None))

    def test_leave_when_not_tuned(self):
        """`bc leave` when not on a channel shows an error message."""
        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = "leave"
        cmd.func()

        self.assertIsNone(self.char.attributes.get("bc_channel", default=None))


# ---------------------------------------------------------------------------
# Broadcasting Tests
# ---------------------------------------------------------------------------

class TestBcBroadcast(BaseEvenniaTest):
    """Test broadcasting messages on BC channels."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="PlayerOne")
        self.char1.attributes.add("bc_channel", 21)
        self.char2 = create_object(DefaultCharacter, key="PlayerTwo")
        self.char2.attributes.add("bc_channel", 21)
        self.char3 = create_object(DefaultCharacter, key="PlayerThree")
        self.char3.attributes.add("bc_channel", 42)  # different channel
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room
        self.char2.location = self.room
        self.char3.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.char2.delete()
        self.char3.delete()
        self.room.delete()
        super().tearDown()

    def test_broadcast_to_channel_members(self):
        """A message sent on channel 21 reaches other members of channel 21."""
        delivered = []
        original_msg = self.char2.msg

        def capture(text, **kwargs):
            delivered.append(str(text))
            original_msg(text, **kwargs)

        self.char2.msg = capture

        try:
            cmd = CmdBc()
            cmd.caller = self.char1
            cmd.cmdstring = "bc"
            cmd.args = "Hello channel 21!"
            cmd.func()
        finally:
            self.char2.msg = original_msg

        msg_found = any(
            "Hello channel 21!" in msg and "[BC 21]" in msg for msg in delivered
        )
        self.assertTrue(msg_found, "Channel 21 member should receive the message")

    def test_broadcast_does_not_leak_to_other_channels(self):
        """A message on channel 21 does NOT reach channel 42 members."""
        delivered = []
        original_msg = self.char3.msg

        def capture(text, **kwargs):
            delivered.append(str(text))
            original_msg(text, **kwargs)

        self.char3.msg = capture

        try:
            cmd = CmdBc()
            cmd.caller = self.char1
            cmd.cmdstring = "bc"
            cmd.args = "Secret on 21!"
            cmd.func()
        finally:
            self.char3.msg = original_msg

        leaked = any("Secret on 21!" in msg for msg in delivered)
        self.assertFalse(leaked, "Other channel members should NOT see messages")

    def test_broadcast_format_includes_channel_number(self):
        """The broadcast message format is '[BC <N>] Sender: message'."""
        delivered = []
        original_msg = self.char2.msg

        def capture(text, **kwargs):
            delivered.append(str(text))
            original_msg(text, **kwargs)

        self.char2.msg = capture

        try:
            cmd = CmdBc()
            cmd.caller = self.char1
            cmd.cmdstring = "bc"
            cmd.args = "Test format!"
            cmd.func()
        finally:
            self.char2.msg = original_msg

        # Find the channel message (not the sender feedback)
        channel_msg = None
        for msg in delivered:
            if "[BC 21]" in msg and "PlayerOne" in msg and "Test format!" in msg:
                channel_msg = msg
                break

        self.assertIsNotNone(channel_msg, "Formatted message should be delivered")
        self.assertIn("|c[BC 21]|n", channel_msg, "Channel tag should be cyan colored")
        self.assertIn("PlayerOne:", channel_msg, "Sender name should be included")

    def test_sender_gets_self_feedback(self):
        """The sender receives a confirmation message with 'You say'."""
        delivered = []
        original_msg = self.char1.msg

        def capture(text, **kwargs):
            delivered.append(str(text))
            original_msg(text, **kwargs)

        self.char1.msg = capture

        try:
            cmd = CmdBc()
            cmd.caller = self.char1
            cmd.cmdstring = "bc"
            cmd.args = "Testing self feedback"
            cmd.func()
        finally:
            self.char1.msg = original_msg

        feedback_found = any(
            "[BC 21]" in msg and "You say:" in msg and "Testing self feedback" in msg
            for msg in delivered
        )
        self.assertTrue(feedback_found, "Sender should get self-feedback message")

    def test_broadcast_not_tuned(self):
        """Broadcasting without being tuned shows an error."""
        self.char1.attributes.add("bc_channel", None)

        cmd = CmdBc()
        cmd.caller = self.char1
        cmd.cmdstring = "bc"
        cmd.args = "Anyone there?"
        cmd.func()
        # Should not raise

    def test_broadcast_empty_message(self):
        """Broadcasting an empty message after tuning to a channel."""
        # This is handled by the no-args check in func()
        cmd = CmdBc()
        cmd.caller = self.char1
        cmd.cmdstring = "bc"
        cmd.args = ""
        cmd.func()
        # Should show usage, not broadcast nothing

    def test_cross_faction_messaging(self):
        """BC channels are cross-faction — Good and Evil can chat together."""
        self.char1.attributes.add("alignment", "Good")
        self.char2.attributes.add("alignment", "Evil")
        # Both on channel 21

        delivered = []
        original_msg = self.char2.msg

        def capture(text, **kwargs):
            delivered.append(str(text))
            original_msg(text, **kwargs)

        self.char2.msg = capture

        try:
            cmd = CmdBc()
            cmd.caller = self.char1
            cmd.cmdstring = "bc"
            cmd.args = "Faction doesn't matter here!"
            cmd.func()
        finally:
            self.char2.msg = original_msg

        msg_found = any(
            "Faction doesn't matter here!" in msg and "[BC 21]" in msg
            for msg in delivered
        )
        self.assertTrue(
            msg_found,
            "Evil character should receive Good character's BC message",
        )

    def test_no_recipients_on_empty_channel(self):
        """When no one else is on the channel, the sender is informed."""
        # Remove char2 from channel 21 so char1 is alone
        self.char2.attributes.add("bc_channel", None)

        delivered = []
        original_msg = self.char1.msg

        def capture(text, **kwargs):
            delivered.append(str(text))
            original_msg(text, **kwargs)

        self.char1.msg = capture

        try:
            cmd = CmdBc()
            cmd.caller = self.char1
            cmd.cmdstring = "bc"
            cmd.args = "Is anyone out there?"
            cmd.func()
        finally:
            self.char1.msg = original_msg

        no_one_found = any(
            "No one else is currently on this channel" in msg
            for msg in delivered
        )
        self.assertTrue(
            no_one_found,
            "Sender should be notified when no one else is on the channel",
        )


# ---------------------------------------------------------------------------
# Combined Tune + Broadcast Tests
# ---------------------------------------------------------------------------

class TestBcTuneAndBroadcast(BaseEvenniaTest):
    """Test the combined `bc <number> <message>` syntax."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="Sender")
        self.char2 = create_object(DefaultCharacter, key="Receiver")
        self.char2.attributes.add("bc_channel", 21)
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room
        self.char2.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.char2.delete()
        self.room.delete()
        super().tearDown()

    def test_tune_and_send_one_command(self):
        """`bc 21 Hello world` tunes to 21 AND sends 'Hello world'."""
        delivered = []
        original_msg = self.char2.msg

        def capture(text, **kwargs):
            delivered.append(str(text))
            original_msg(text, **kwargs)

        self.char2.msg = capture

        try:
            cmd = CmdBc()
            cmd.caller = self.char1
            cmd.cmdstring = "bc"
            cmd.args = "21 Hello world from tune+sendsyntax!"
            cmd.func()
        finally:
            self.char2.msg = original_msg

        # Channel should be set to 21
        self.assertEqual(self.char1.attributes.get("bc_channel"), 21)

        # Message should have been delivered
        msg_found = any(
            "Hello world from tune+sendsyntax!" in msg and "[BC 21]" in msg
            for msg in delivered
        )
        self.assertTrue(msg_found, "Combined tune+send should deliver message")


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------

class TestBcEdgeCases(BaseEvenniaTest):
    """Test edge cases for the BC command."""

    def setUp(self):
        super().setUp()
        self.char = create_object(DefaultCharacter, key="TestPlayer")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_untuned_shows_usage(self):
        """`bc` when untuned shows full usage."""
        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_tuned_shows_channel_in_usage(self):
        """`bc` when tuned shows current channel info."""
        self.char.attributes.add("bc_channel", 55)

        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_negative_channel_number_rejected(self):
        """Negative channel numbers (-5) are rejected."""
        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = "-5"
        cmd.func()

        self.assertIsNone(self.char.attributes.get("bc_channel", default=None))

    def test_multiple_players_on_same_channel_all_receive(self):
        """Three players on the same channel all receive messages."""
        char_a = create_object(DefaultCharacter, key="PlayerA")
        char_a.attributes.add("bc_channel", 99)
        char_b = create_object(DefaultCharacter, key="PlayerB")
        char_b.attributes.add("bc_channel", 99)
        char_c = create_object(DefaultCharacter, key="PlayerC")
        char_c.attributes.add("bc_channel", 99)
        char_a.location = self.room
        char_b.location = self.room
        char_c.location = self.room

        delivered_b = []
        delivered_c = []
        original_b = char_b.msg
        original_c = char_c.msg

        def capture_b(text, **kwargs):
            delivered_b.append(str(text))
            original_b(text, **kwargs)

        def capture_c(text, **kwargs):
            delivered_c.append(str(text))
            original_c(text, **kwargs)

        char_b.msg = capture_b
        char_c.msg = capture_c

        try:
            cmd = CmdBc()
            cmd.caller = char_a
            cmd.cmdstring = "bc"
            cmd.args = "Channel 99 party!"
            cmd.func()
        finally:
            char_b.msg = original_b
            char_c.msg = original_c
            char_a.delete()
            char_b.delete()
            char_c.delete()

        msg_b = any("Channel 99 party!" in m for m in delivered_b)
        msg_c = any("Channel 99 party!" in m for m in delivered_c)
        self.assertTrue(msg_b, "Player B should receive the message")
        self.assertTrue(msg_c, "Player C should receive the message")

    def test_leave_then_rejoin(self):
        """After leaving, a player can tune into a new channel."""
        self.char.attributes.add("bc_channel", 21)

        # Leave
        cmd = CmdBc()
        cmd.caller = self.char
        cmd.cmdstring = "bc"
        cmd.args = "leave"
        cmd.func()

        self.assertIsNone(self.char.attributes.get("bc_channel", default=None))

        # Rejoin a different channel
        cmd2 = CmdBc()
        cmd2.caller = self.char
        cmd2.cmdstring = "bc"
        cmd2.args = "77"
        cmd2.func()

        self.assertEqual(self.char.attributes.get("bc_channel"), 77)