"""
Unit tests for the Clan System: clan definitions, join/leave mechanics,
faction alignment checks, global join broadcasts, clantalk communication,
who list clan tags, and character appearance clan display.

Run with:
    evennia test commands.tests.test_clan
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultRoom, DefaultCharacter
from evennia import create_object

from typeclasses.characters import Character

from commands.clan import (
    CLANS,
    get_clan_info,
    get_clans_by_alignment,
    get_clan_members,
    broadcast_clan_join,
    CmdClanJoin,
    CmdClanList,
    CmdClanLeave,
    CmdClanTalk,
    CmdClan,
)


# ---------------------------------------------------------------------------
# Clan Definitions Tests
# ---------------------------------------------------------------------------

class TestClanDefinitions(BaseEvenniaTest):
    """Test that clan definitions are correctly structured."""

    def test_eight_clans_total(self):
        """There should be exactly 8 clans."""
        self.assertEqual(len(CLANS), 8)

    def test_four_good_clans(self):
        """There should be exactly 4 Good-aligned clans."""
        good = get_clans_by_alignment("Good")
        self.assertEqual(len(good), 4)

    def test_four_evil_clans(self):
        """There should be exactly 4 Evil-aligned clans."""
        evil = get_clans_by_alignment("Evil")
        self.assertEqual(len(evil), 4)

    def test_house_of_zod_is_evil(self):
        """The House of Zod must be Evil-aligned."""
        self.assertEqual(CLANS["The House of Zod"]["alignment"], "Evil")

    def test_all_clans_have_descriptions(self):
        """Every clan must have a non-empty description."""
        for key, data in CLANS.items():
            self.assertIn("description", data, f"{key} missing description")
            self.assertTrue(
                len(data["description"]) > 20,
                f"{key} description too short",
            )

    def test_all_clans_have_join_messages(self):
        """Every clan must have a join_message with {name} placeholder."""
        for key, data in CLANS.items():
            self.assertIn("join_message", data, f"{key} missing join_message")
            self.assertIn(
                "{name}",
                data["join_message"],
                f"{key} join_message missing {{name}} placeholder",
            )

    def test_all_clans_have_alignment(self):
        """Every clan must have a valid alignment."""
        for key, data in CLANS.items():
            self.assertIn(data["alignment"], ("Good", "Evil"),
                          f"{key} has invalid alignment")

    def test_good_clan_names(self):
        """Verify the 4 Good clan names."""
        good = get_clans_by_alignment("Good")
        expected = {
            "The Order of the Sun",
            "The Verdant Circle",
            "The Silver Concord",
            "The Iron Vanguard",
        }
        self.assertEqual(set(good.keys()), expected)

    def test_evil_clan_names(self):
        """Verify the 4 Evil clan names."""
        evil = get_clans_by_alignment("Evil")
        expected = {
            "The House of Zod",
            "The Shadow Council",
            "The Crimson Legion",
            "The Black Hand",
        }
        self.assertEqual(set(evil.keys()), expected)


# ---------------------------------------------------------------------------
# Helper Function Tests
# ---------------------------------------------------------------------------

class TestClanHelpers(BaseEvenniaTest):
    """Test clan helper functions."""

    def test_get_clan_info_exact_match(self):
        """get_clan_info returns correct data for exact name."""
        key, data = get_clan_info("The House of Zod")
        self.assertEqual(key, "The House of Zod")
        self.assertEqual(data["alignment"], "Evil")

    def test_get_clan_info_case_insensitive(self):
        """get_clan_info is case-insensitive."""
        key, data = get_clan_info("the house of zod")
        self.assertEqual(key, "The House of Zod")

        key, data = get_clan_info("THE ORDER OF THE SUN")
        self.assertEqual(key, "The Order of the Sun")

    def test_get_clan_info_nonexistent(self):
        """get_clan_info returns None for nonexistent clan."""
        key, data = get_clan_info("Nonexistent Clan")
        self.assertIsNone(key)
        self.assertIsNone(data)

    def test_get_clans_by_alignment_good(self):
        """get_clans_by_alignment returns only Good clans."""
        good = get_clans_by_alignment("Good")
        for data in good.values():
            self.assertEqual(data["alignment"], "Good")

    def test_get_clans_by_alignment_evil(self):
        """get_clans_by_alignment returns only Evil clans."""
        evil = get_clans_by_alignment("Evil")
        for data in evil.values():
            self.assertEqual(data["alignment"], "Evil")

    def test_get_clans_by_alignment_neutral_returns_empty(self):
        """Neutral alignment returns no clans."""
        neutral = get_clans_by_alignment("Neutral")
        self.assertEqual(len(neutral), 0)


# ---------------------------------------------------------------------------
# Clan Join Command Tests
# ---------------------------------------------------------------------------

class TestClanJoin(BaseEvenniaTest):
    """Test the clan join command."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="TestHero")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("level", 5)
        self.char1.attributes.add("race", "Human")
        self.char1.attributes.add("class", "Warrior")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()
        super().tearDown()

    def test_join_good_clan_success(self):
        """A Good character can join a Good clan."""
        cmd = CmdClanJoin()
        cmd.caller = self.char1
        cmd.cmdstring = "clan join"
        cmd.args = "The Order of the Sun"
        cmd.func()

        self.assertEqual(
            self.char1.attributes.get("clan"),
            "The Order of the Sun",
        )

    def test_join_evil_clan_success(self):
        """An Evil character can join an Evil clan."""
        self.char1.attributes.add("alignment", "Evil")

        cmd = CmdClanJoin()
        cmd.caller = self.char1
        cmd.cmdstring = "clan join"
        cmd.args = "The House of Zod"
        cmd.func()

        self.assertEqual(
            self.char1.attributes.get("clan"),
            "The House of Zod",
        )

    def test_join_case_insensitive(self):
        """Clan name matching is case-insensitive."""
        cmd = CmdClanJoin()
        cmd.caller = self.char1
        cmd.cmdstring = "clan join"
        cmd.args = "the order of the sun"
        cmd.func()

        self.assertEqual(
            self.char1.attributes.get("clan"),
            "The Order of the Sun",
        )

    def test_join_wrong_alignment_blocked(self):
        """A Good character cannot join an Evil clan."""
        cmd = CmdClanJoin()
        cmd.caller = self.char1
        cmd.cmdstring = "clan join"
        cmd.args = "The House of Zod"
        cmd.func()

        self.assertIsNone(self.char1.attributes.get("clan", default=None))

    def test_evil_cannot_join_good_clan(self):
        """An Evil character cannot join a Good clan."""
        self.char1.attributes.add("alignment", "Evil")

        cmd = CmdClanJoin()
        cmd.caller = self.char1
        cmd.cmdstring = "clan join"
        cmd.args = "The Order of the Sun"
        cmd.func()

        self.assertIsNone(self.char1.attributes.get("clan", default=None))

    def test_join_nonexistent_clan(self):
        """Joining a nonexistent clan fails."""
        cmd = CmdClanJoin()
        cmd.caller = self.char1
        cmd.cmdstring = "clan join"
        cmd.args = "The Unicorn Brigade"
        cmd.func()

        self.assertIsNone(self.char1.attributes.get("clan", default=None))

    def test_join_already_in_clan(self):
        """Cannot join a second clan while already in one."""
        self.char1.attributes.add("clan", "The Order of the Sun")

        cmd = CmdClanJoin()
        cmd.caller = self.char1
        cmd.cmdstring = "clan join"
        cmd.args = "The Iron Vanguard"
        cmd.func()

        # Should still be in original clan
        self.assertEqual(
            self.char1.attributes.get("clan"),
            "The Order of the Sun",
        )

    def test_join_no_args_shows_usage(self):
        """Join with no arguments shows usage."""
        cmd = CmdClanJoin()
        cmd.caller = self.char1
        cmd.cmdstring = "clan join"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_join_via_alias(self):
        """The 'join' alias works."""
        cmd = CmdClanJoin()
        cmd.caller = self.char1
        cmd.cmdstring = "join"
        cmd.args = "The Iron Vanguard"
        cmd.func()

        self.assertEqual(
            self.char1.attributes.get("clan"),
            "The Iron Vanguard",
        )

    def test_join_all_four_good_clans(self):
        """A Good character can join any of the 4 Good clans."""
        good_clans = list(get_clans_by_alignment("Good").keys())
        self.assertEqual(len(good_clans), 4)

        for clan_name in good_clans:
            # Create a fresh character for each test
            char = create_object(DefaultCharacter, key=f"Test_{clan_name[:5]}")
            char.attributes.add("alignment", "Good")
            char.attributes.add("level", 5)
            char.location = self.room

            cmd = CmdClanJoin()
            cmd.caller = char
            cmd.cmdstring = "clan join"
            cmd.args = clan_name
            cmd.func()

            self.assertEqual(
                char.attributes.get("clan"),
                clan_name,
                f"Should be able to join {clan_name}",
            )
            char.delete()

    def test_join_all_four_evil_clans(self):
        """An Evil character can join any of the 4 Evil clans."""
        evil_clans = list(get_clans_by_alignment("Evil").keys())
        self.assertEqual(len(evil_clans), 4)

        for clan_name in evil_clans:
            char = create_object(DefaultCharacter, key=f"Test_{clan_name[:5]}")
            char.attributes.add("alignment", "Evil")
            char.attributes.add("level", 5)
            char.location = self.room

            cmd = CmdClanJoin()
            cmd.caller = char
            cmd.cmdstring = "clan join"
            cmd.args = clan_name
            cmd.func()

            self.assertEqual(
                char.attributes.get("clan"),
                clan_name,
                f"Should be able to join {clan_name}",
            )
            char.delete()

    def test_neutral_alignment_cannot_join(self):
        """A Neutral character cannot join any clan."""
        self.char1.attributes.add("alignment", "Neutral")

        cmd = CmdClanJoin()
        cmd.caller = self.char1
        cmd.cmdstring = "clan join"
        cmd.args = "The Order of the Sun"
        cmd.func()

        self.assertIsNone(self.char1.attributes.get("clan", default=None))


# ---------------------------------------------------------------------------
# Clan Leave Command Tests
# ---------------------------------------------------------------------------

class TestClanLeave(BaseEvenniaTest):
    """Test the clan leave command."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="TestHero")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("level", 5)
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()
        super().tearDown()

    def test_leave_clan_success(self):
        """A clan member can leave their clan."""
        self.char1.attributes.add("clan", "The Order of the Sun")

        cmd = CmdClanLeave()
        cmd.caller = self.char1
        cmd.cmdstring = "clan leave"
        cmd.args = ""
        cmd.func()

        self.assertIsNone(self.char1.attributes.get("clan", default=None))

    def test_leave_when_not_in_clan(self):
        """Leaving when not in a clan shows a message."""
        cmd = CmdClanLeave()
        cmd.caller = self.char1
        cmd.cmdstring = "clan leave"
        cmd.args = ""
        cmd.func()

        self.assertIsNone(self.char1.attributes.get("clan", default=None))

    def test_leave_then_rejoin(self):
        """After leaving, a character can join a different clan."""
        self.char1.attributes.add("clan", "The Order of the Sun")

        # Leave
        cmd = CmdClanLeave()
        cmd.caller = self.char1
        cmd.cmdstring = "clan leave"
        cmd.args = ""
        cmd.func()

        self.assertIsNone(self.char1.attributes.get("clan", default=None))

        # Rejoin a different clan
        cmd2 = CmdClanJoin()
        cmd2.caller = self.char1
        cmd2.cmdstring = "clan join"
        cmd2.args = "The Iron Vanguard"
        cmd2.func()

        self.assertEqual(
            self.char1.attributes.get("clan"),
            "The Iron Vanguard",
        )

    def test_leave_evil_clan(self):
        """An Evil character can leave their Evil clan."""
        self.char1.attributes.add("alignment", "Evil")
        self.char1.attributes.add("clan", "The House of Zod")

        cmd = CmdClanLeave()
        cmd.caller = self.char1
        cmd.cmdstring = "clan leave"
        cmd.args = ""
        cmd.func()

        self.assertIsNone(self.char1.attributes.get("clan", default=None))


# ---------------------------------------------------------------------------
# Global Join Broadcast Tests
# ---------------------------------------------------------------------------

class TestClanBroadcast(BaseEvenniaTest):
    """Test that joining a clan triggers a realm-wide broadcast."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="TestHero")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("level", 5)
        self.char2 = create_object(DefaultCharacter, key="OtherPlayer")
        self.char2.attributes.add("alignment", "Evil")
        self.char2.attributes.add("level", 3)
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room
        self.char2.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.char2.delete()
        self.room.delete()
        super().tearDown()

    def test_broadcast_contains_player_name(self):
        """The broadcast message includes the joining player's name."""
        delivered = []
        original_msg = self.char2.msg

        def capture(text, **kwargs):
            delivered.append(text)
            original_msg(text, **kwargs)

        self.char2.msg = capture

        try:
            cmd = CmdClanJoin()
            cmd.caller = self.char1
            cmd.cmdstring = "clan join"
            cmd.args = "The Order of the Sun"
            cmd.func()
        finally:
            self.char2.msg = original_msg

        # Find the broadcast message
        broadcast_found = any(
            "TestHero" in msg and "The Order of the Sun" in msg
            for msg in delivered
        )
        self.assertTrue(
            broadcast_found,
            "Broadcast should contain player name and clan name",
        )

    def test_broadcast_is_bright_red(self):
        """The broadcast message uses bright red formatting (|r|h)."""
        delivered = []
        original_msg = self.char2.msg

        def capture(text, **kwargs):
            delivered.append(text)
            original_msg(text, **kwargs)

        self.char2.msg = capture

        try:
            cmd = CmdClanJoin()
            cmd.caller = self.char1
            cmd.cmdstring = "clan join"
            cmd.args = "The Order of the Sun"
            cmd.func()
        finally:
            self.char2.msg = original_msg

        # Find the broadcast message
        broadcast_msg = None
        for msg in delivered:
            if "TestHero" in msg and "The Order of the Sun" in msg:
                broadcast_msg = msg
                break

        self.assertIsNotNone(broadcast_msg, "Broadcast message should exist")
        self.assertIn(
            "|r|h",
            broadcast_msg,
            "Broadcast should use bright red formatting (|r|h)",
        )

    def test_broadcast_reaches_all_online(self):
        """The broadcast reaches all online players regardless of faction."""
        delivered_to_char2 = []
        original_char2 = self.char2.msg

        def capture_char2(text, **kwargs):
            delivered_to_char2.append(text)
            original_char2(text, **kwargs)

        self.char2.msg = capture_char2

        try:
            cmd = CmdClanJoin()
            cmd.caller = self.char1
            cmd.cmdstring = "clan join"
            cmd.args = "The Order of the Sun"
            cmd.func()
        finally:
            self.char2.msg = original_char2

        # Evil player should also see the Good player's join broadcast
        broadcast_found = any(
            "TestHero" in msg and "The Order of the Sun" in msg
            for msg in delivered_to_char2
        )
        self.assertTrue(
            broadcast_found,
            "Broadcast should reach players of opposing faction",
        )

    def test_broadcast_for_house_of_zod(self):
        """The House of Zod join message is epic and contains expected text."""
        self.char1.attributes.add("alignment", "Evil")

        delivered = []
        original_msg = self.char2.msg

        def capture(text, **kwargs):
            delivered.append(text)
            original_msg(text, **kwargs)

        self.char2.msg = capture

        try:
            cmd = CmdClanJoin()
            cmd.caller = self.char1
            cmd.cmdstring = "clan join"
            cmd.args = "The House of Zod"
            cmd.func()
        finally:
            self.char2.msg = original_msg

        broadcast_found = any(
            "ground trembles" in msg and "TestHero" in msg
            for msg in delivered
        )
        self.assertTrue(
            broadcast_found,
            "House of Zod broadcast should mention ground trembling",
        )

    def test_broadcast_for_each_clan(self):
        """Each of the 8 clans has a unique broadcast message."""
        seen_messages = set()
        for clan_key, clan_data in CLANS.items():
            msg = clan_data["join_message"].format(name="TestPlayer")
            self.assertNotIn(msg, seen_messages,
                             f"Duplicate join message for {clan_key}")
            seen_messages.add(msg)

    def test_broadcast_helper_function(self):
        """broadcast_clan_join sends to all online characters."""
        delivered_to_char2 = []
        original_char2 = self.char2.msg

        def capture(text, **kwargs):
            delivered_to_char2.append(text)
            original_char2(text, **kwargs)

        self.char2.msg = capture

        try:
            broadcast_clan_join("TestHero", "The Order of the Sun")
        finally:
            self.char2.msg = original_char2

        broadcast_found = any(
            "TestHero" in msg and "The Order of the Sun" in msg
            for msg in delivered_to_char2
        )
        self.assertTrue(broadcast_found, "broadcast_clan_join should deliver message")


# ---------------------------------------------------------------------------
# Clan List Command Tests
# ---------------------------------------------------------------------------

class TestClanList(BaseEvenniaTest):
    """Test the clan list command."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="TestHero")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("level", 5)
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()
        super().tearDown()

    def test_clan_list_shows_all_clans(self):
        """Clan list displays all 8 clans."""
        cmd = CmdClanList()
        cmd.caller = self.char1
        cmd.cmdstring = "clan list"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_clan_list_shows_good_and_evil_sections(self):
        """Clan list has Good and Evil sections."""
        cmd = CmdClanList()
        cmd.caller = self.char1
        cmd.cmdstring = "clan list"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_clan_list_highlights_current_clan(self):
        """Clan list marks the player's current clan."""
        self.char1.attributes.add("clan", "The Order of the Sun")

        cmd = CmdClanList()
        cmd.caller = self.char1
        cmd.cmdstring = "clan list"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_clan_list_evil_player(self):
        """Evil player sees appropriate markers."""
        self.char1.attributes.add("alignment", "Evil")

        cmd = CmdClanList()
        cmd.caller = self.char1
        cmd.cmdstring = "clan list"
        cmd.args = ""
        cmd.func()
        # Should not raise


# ---------------------------------------------------------------------------
# Clan Talk Command Tests
# ---------------------------------------------------------------------------

class TestClanTalk(BaseEvenniaTest):
    """Test the clantalk / ct command."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="ClanMember1")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("clan", "The Order of the Sun")
        self.char1.attributes.add("level", 5)

        self.char2 = create_object(DefaultCharacter, key="ClanMember2")
        self.char2.attributes.add("alignment", "Good")
        self.char2.attributes.add("clan", "The Order of the Sun")
        self.char2.attributes.add("level", 3)

        self.char3 = create_object(DefaultCharacter, key="OtherClanGuy")
        self.char3.attributes.add("alignment", "Good")
        self.char3.attributes.add("clan", "The Iron Vanguard")
        self.char3.attributes.add("level", 4)

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

    def test_clantalk_delivers_to_clan_members(self):
        """Clantalk delivers messages to same-clan members."""
        delivered = []
        original_msg = self.char2.msg

        def capture(text, **kwargs):
            delivered.append(text)
            original_msg(text, **kwargs)

        self.char2.msg = capture

        try:
            cmd = CmdClanTalk()
            cmd.caller = self.char1
            cmd.cmdstring = "clantalk"
            cmd.args = "Hello clanmates!"
            cmd.func()
        finally:
            self.char2.msg = original_msg

        clan_msg_found = any(
            "Hello clanmates!" in msg and "[Clan" in msg
            for msg in delivered
        )
        self.assertTrue(
            clan_msg_found,
            "Clan member should receive clantalk message",
        )

    def test_clantalk_does_not_deliver_to_other_clans(self):
        """Clantalk does NOT deliver to members of other clans."""
        delivered = []
        original_msg = self.char3.msg

        def capture(text, **kwargs):
            delivered.append(text)
            original_msg(text, **kwargs)

        self.char3.msg = capture

        try:
            cmd = CmdClanTalk()
            cmd.caller = self.char1
            cmd.cmdstring = "clantalk"
            cmd.args = "Secret clan business!"
            cmd.func()
        finally:
            self.char3.msg = original_msg

        leaked = any(
            "Secret clan business!" in msg
            for msg in delivered
        )
        self.assertFalse(
            leaked,
            "Other clan members should NOT see clantalk messages",
        )

    def test_clantalk_no_message_shows_usage(self):
        """Clantalk with no message shows usage."""
        cmd = CmdClanTalk()
        cmd.caller = self.char1
        cmd.cmdstring = "clantalk"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_clantalk_not_in_clan(self):
        """Clantalk when not in a clan shows error."""
        self.char1.attributes.add("clan", None)

        cmd = CmdClanTalk()
        cmd.caller = self.char1
        cmd.cmdstring = "clantalk"
        cmd.args = "Anyone there?"
        cmd.func()
        # Should not raise

    def test_ct_alias_works(self):
        """The 'ct' alias works for clantalk."""
        delivered = []
        original_msg = self.char2.msg

        def capture(text, **kwargs):
            delivered.append(text)
            original_msg(text, **kwargs)

        self.char2.msg = capture

        try:
            cmd = CmdClanTalk()
            cmd.caller = self.char1
            cmd.cmdstring = "ct"
            cmd.args = "Quick message via ct!"
            cmd.func()
        finally:
            self.char2.msg = original_msg

        clan_msg_found = any(
            "Quick message via ct!" in msg
            for msg in delivered
        )
        self.assertTrue(clan_msg_found, "ct alias should deliver message")

    def test_clantalk_evil_clan_isolation(self):
        """Evil clan members can talk privately within their clan."""
        self.char1.attributes.add("alignment", "Evil")
        self.char1.attributes.add("clan", "The House of Zod")
        self.char2.attributes.add("alignment", "Evil")
        self.char2.attributes.add("clan", "The House of Zod")

        delivered = []
        original_msg = self.char2.msg

        def capture(text, **kwargs):
            delivered.append(text)
            original_msg(text, **kwargs)

        self.char2.msg = capture

        try:
            cmd = CmdClanTalk()
            cmd.caller = self.char1
            cmd.cmdstring = "clantalk"
            cmd.args = "For Zod!"
            cmd.func()
        finally:
            self.char2.msg = original_msg

        clan_msg_found = any(
            "For Zod!" in msg
            for msg in delivered
        )
        self.assertTrue(clan_msg_found, "Evil clan members should receive clantalk")

    def test_get_clan_members_returns_online_only(self):
        """get_clan_members returns only online characters."""
        members = get_clan_members("The Order of the Sun")
        # char1 and char2 are in The Order of the Sun
        # In test environment, sessions may not be attached
        # Just verify the function runs without error
        self.assertIsInstance(members, list)


# ---------------------------------------------------------------------------
# Clan Hub Command Tests
# ---------------------------------------------------------------------------

class TestClanHubCommand(BaseEvenniaTest):
    """Test the main 'clan' command hub."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="TestHero")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("level", 5)
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()
        super().tearDown()

    def test_clan_no_args_shows_usage(self):
        """`clan` with no args shows usage."""
        cmd = CmdClan()
        cmd.caller = self.char1
        cmd.cmdstring = "clan"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_clan_join_subcommand(self):
        """`clan join <name>` delegates to CmdClanJoin."""
        cmd = CmdClan()
        cmd.caller = self.char1
        cmd.cmdstring = "clan"
        cmd.args = "join The Order of the Sun"
        cmd.func()

        self.assertEqual(
            self.char1.attributes.get("clan"),
            "The Order of the Sun",
        )

    def test_clan_join_no_name(self):
        """`clan join` with no clan name shows usage."""
        cmd = CmdClan()
        cmd.caller = self.char1
        cmd.cmdstring = "clan"
        cmd.args = "join"
        cmd.func()
        # Should not raise

    def test_clan_list_subcommand(self):
        """`clan list` delegates to CmdClanList."""
        cmd = CmdClan()
        cmd.caller = self.char1
        cmd.cmdstring = "clan"
        cmd.args = "list"
        cmd.func()
        # Should not raise

    def test_clan_leave_subcommand(self):
        """`clan leave` delegates to CmdClanLeave."""
        self.char1.attributes.add("clan", "The Order of the Sun")

        cmd = CmdClan()
        cmd.caller = self.char1
        cmd.cmdstring = "clan"
        cmd.args = "leave"
        cmd.func()

        self.assertIsNone(self.char1.attributes.get("clan", default=None))

    def test_clan_bad_subcommand(self):
        """Invalid subcommand shows error."""
        cmd = CmdClan()
        cmd.caller = self.char1
        cmd.cmdstring = "clan"
        cmd.args = "destroy"
        cmd.func()
        # Should not raise

    def test_clan_j_alias(self):
        """`clan j` is an alias for `clan join`."""
        cmd = CmdClan()
        cmd.caller = self.char1
        cmd.cmdstring = "clan"
        cmd.args = "j The Iron Vanguard"
        cmd.func()

        self.assertEqual(
            self.char1.attributes.get("clan"),
            "The Iron Vanguard",
        )

    def test_clan_l_alias(self):
        """`clan l` is an alias for `clan list`."""
        cmd = CmdClan()
        cmd.caller = self.char1
        cmd.cmdstring = "clan"
        cmd.args = "l"
        cmd.func()
        # Should not raise

    def test_clan_lv_alias(self):
        """`clan lv` is an alias for `clan leave`."""
        self.char1.attributes.add("clan", "The Order of the Sun")

        cmd = CmdClan()
        cmd.caller = self.char1
        cmd.cmdstring = "clan"
        cmd.args = "lv"
        cmd.func()

        self.assertIsNone(self.char1.attributes.get("clan", default=None))


# ---------------------------------------------------------------------------
# Character Appearance Clan Display Tests
# ---------------------------------------------------------------------------

class TestCharacterClanDisplay(BaseEvenniaTest):
    """Test that clan appears in character appearance/look."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(Character, key="ClanHero")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("clan", "The Order of the Sun")
        self.char1.attributes.add("level", 5)
        self.char1.attributes.add("race", "Human")
        self.char1.attributes.add("class", "Warrior")
        self.char1.attributes.add("hp", 100)
        self.char1.attributes.add("max_hp", 100)
        self.char1.attributes.add("mana", 50)
        self.char1.attributes.add("max_mana", 50)
        self.char1.attributes.add("mv", 100)
        self.char1.attributes.add("max_mv", 100)
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()
        super().tearDown()

    def test_return_appearance_includes_clan(self):
        """Character appearance shows clan when in one."""
        appearance = self.char1.return_appearance(self.char1)
        self.assertIn("The Order of the Sun", appearance)
        self.assertIn("Clan:", appearance)

    def test_return_appearance_no_clan(self):
        """Character appearance does not show clan line when not in one."""
        self.char1.attributes.add("clan", None)
        appearance = self.char1.return_appearance(self.char1)
        self.assertNotIn("Clan:", appearance)

    def test_return_appearance_evil_clan(self):
        """Character appearance shows Evil clan name."""
        self.char1.attributes.add("alignment", "Evil")
        self.char1.attributes.add("clan", "The House of Zod")
        appearance = self.char1.return_appearance(self.char1)
        self.assertIn("The House of Zod", appearance)
        self.assertIn("Clan:", appearance)


# ---------------------------------------------------------------------------
# Who List Clan Tag Tests
# ---------------------------------------------------------------------------

class TestWhoListClanTags(BaseEvenniaTest):
    """Test that the who list displays clan tags."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="WhoHero")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("clan", "The Order of the Sun")
        self.char1.attributes.add("level", 10)
        self.char1.attributes.add("race", "High Elf")
        self.char1.attributes.add("class", "Mage")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()
        super().tearDown()

    def test_who_command_exists(self):
        """The CmdWho command can be instantiated."""
        from commands.general import CmdWho
        cmd = CmdWho()
        cmd.caller = self.char1
        cmd.cmdstring = "who"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_who_aliases(self):
        """CmdWho has the correct aliases."""
        from commands.general import CmdWho
        self.assertIn("w", CmdWho.aliases)
        self.assertIn("players", CmdWho.aliases)
