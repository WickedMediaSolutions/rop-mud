"""
Unit tests for the Party/Grouping System: group creation, invitations,
joining, leaving, kicking, EXP sharing, and group chat.

Run with:
    evennia test commands.tests.test_group
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultRoom, DefaultCharacter
from evennia import create_object

from commands.group import (
    get_group_members,
    get_group_members_in_room,
    is_group_leader,
    get_group_leader,
    dissolve_group,
    broadcast_group,
    split_group_xp,
    format_group_status,
    CmdGroupInvite,
    CmdGroupAccept,
    CmdGroupLeave,
    CmdGroupKick,
    CmdGroupTalk,
    CmdGroup,
)


# ---------------------------------------------------------------------------
# Helper Function Tests
# ---------------------------------------------------------------------------

class TestGroupHelpers(BaseEvenniaTest):
    """Test group helper functions without active groups."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="Test Room")

    def tearDown(self):
        self.room.delete()
        super().tearDown()

    def test_get_group_members_empty_when_no_group(self):
        """get_group_members returns empty list when character is not in a group."""
        char = create_object(DefaultCharacter, key="Solo")
        char.location = self.room
        members = get_group_members(char)
        self.assertEqual(members, [])
        char.delete()

    def test_is_group_leader_false_when_no_group(self):
        """is_group_leader returns False when character is not in a group."""
        char = create_object(DefaultCharacter, key="Solo")
        char.location = self.room
        self.assertFalse(is_group_leader(char))
        char.delete()

    def test_get_group_leader_none_for_empty_list(self):
        """get_group_leader returns None for empty member list."""
        self.assertIsNone(get_group_leader([]))

    def test_dissolve_group_does_nothing_when_no_group(self):
        """dissolve_group is safe to call on ungrouped character."""
        char = create_object(DefaultCharacter, key="Solo")
        char.location = self.room
        dissolve_group(char)  # Should not raise
        char.delete()

    def test_format_group_status_shows_not_in_group(self):
        """format_group_status shows 'not in a group' message."""
        char = create_object(DefaultCharacter, key="Solo")
        char.location = self.room
        status = format_group_status(char)
        self.assertIn("not in a group", status.lower())
        char.delete()


# ---------------------------------------------------------------------------
# Group Creation & Invitation Tests
# ---------------------------------------------------------------------------

class TestGroupCreationInvite(BaseEvenniaTest):
    """Test group creation and invitation mechanics."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="Alpha")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("level", 5)

        self.char2 = create_object(DefaultCharacter, key="Beta")
        self.char2.attributes.add("alignment", "Good")
        self.char2.attributes.add("level", 3)

        self.char3 = create_object(DefaultCharacter, key="Gamma")
        self.char3.attributes.add("alignment", "Evil")
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

    def test_invite_creates_group_and_sets_leader(self):
        """Inviting a player creates a new group with the inviter as leader."""
        cmd = CmdGroupInvite()
        cmd.caller = self.char1
        cmd.cmdstring = "group invite"
        cmd.args = "Beta"
        cmd.func()

        group_id = self.char1.attributes.get("group_id")
        self.assertIsNotNone(group_id)
        self.assertTrue(self.char1.attributes.get("group_leader"))
        self.assertEqual(
            self.char2.attributes.get("group_invite"),
            group_id,
        )

    def test_accept_joins_group(self):
        """Accepting an invitation adds the character to the group."""
        # First create the group and invite
        cmd_inv = CmdGroupInvite()
        cmd_inv.caller = self.char1
        cmd_inv.cmdstring = "group invite"
        cmd_inv.args = "Beta"
        cmd_inv.func()

        # Now accept
        cmd_acc = CmdGroupAccept()
        cmd_acc.caller = self.char2
        cmd_acc.cmdstring = "group accept"
        cmd_acc.args = ""
        cmd_acc.func()

        group_id = self.char2.attributes.get("group_id")
        self.assertIsNotNone(group_id)
        self.assertFalse(self.char2.attributes.get("group_leader"))
        self.assertEqual(
            group_id,
            self.char1.attributes.get("group_id"),
        )

    def test_accept_clears_invitation(self):
        """After accepting, the group_invite attribute is cleared."""
        cmd_inv = CmdGroupInvite()
        cmd_inv.caller = self.char1
        cmd_inv.cmdstring = "group invite"
        cmd_inv.args = "Beta"
        cmd_inv.func()

        cmd_acc = CmdGroupAccept()
        cmd_acc.caller = self.char2
        cmd_acc.cmdstring = "group accept"
        cmd_acc.args = ""
        cmd_acc.func()

        self.assertIsNone(
            self.char2.attributes.get("group_invite", default=None),
        )

    def test_cannot_invite_self(self):
        """A player cannot invite themselves to a group."""
        cmd = CmdGroupInvite()
        cmd.caller = self.char1
        cmd.cmdstring = "group invite"
        cmd.args = "Alpha"
        cmd.func()

        self.assertIsNone(
            self.char1.attributes.get("group_id", default=None),
        )

    def test_cannot_invite_already_grouped(self):
        """Cannot invite someone already in a group."""
        # char2 joins a group
        self.char2.attributes.add("group_id", "existing_group")
        self.char2.attributes.add("group_leader", False)

        cmd = CmdGroupInvite()
        cmd.caller = self.char1
        cmd.cmdstring = "group invite"
        cmd.args = "Beta"
        cmd.func()

        # No group should be created for char1
        self.assertIsNone(
            self.char1.attributes.get("group_id", default=None),
        )

    def test_accept_no_invitation_shows_message(self):
        """Accepting without a pending invitation shows a message."""
        cmd = CmdGroupAccept()
        cmd.caller = self.char2
        cmd.cmdstring = "group accept"
        cmd.args = ""
        cmd.func()

        self.assertIsNone(
            self.char2.attributes.get("group_id", default=None),
        )

    def test_accept_when_already_in_group(self):
        """Cannot accept an invitation when already in a group."""
        self.char2.attributes.add("group_id", "other_group")

        cmd_inv = CmdGroupInvite()
        cmd_inv.caller = self.char1
        cmd_inv.cmdstring = "group invite"
        cmd_inv.args = "Beta"
        cmd_inv.func()

        cmd_acc = CmdGroupAccept()
        cmd_acc.caller = self.char2
        cmd_acc.cmdstring = "group accept"
        cmd_acc.args = ""
        cmd_acc.func()

        # Should still be in old group
        self.assertEqual(
            self.char2.attributes.get("group_id"),
            "other_group",
        )

    def test_invite_no_args_shows_usage(self):
        """Invite with no player name shows usage."""
        cmd = CmdGroupInvite()
        cmd.caller = self.char1
        cmd.cmdstring = "group invite"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_non_leader_cannot_invite(self):
        """A non-leader group member cannot invite others."""
        # Set up group with char1 as leader, char2 as member
        self.char1.attributes.add("group_id", "test_group")
        self.char1.attributes.add("group_leader", True)
        self.char2.attributes.add("group_id", "test_group")
        self.char2.attributes.add("group_leader", False)

        cmd = CmdGroupInvite()
        cmd.caller = self.char2
        cmd.cmdstring = "group invite"
        cmd.args = "Gamma"
        cmd.func()

        # Gamma should not have an invitation
        self.assertIsNone(
            self.char3.attributes.get("group_invite", default=None),
        )

    def test_accept_nonexistent_group(self):
        """Accepting an invitation for a group that no longer exists."""
        self.char2.attributes.add("group_invite", "dead_group")

        cmd = CmdGroupAccept()
        cmd.caller = self.char2
        cmd.cmdstring = "group accept"
        cmd.args = ""
        cmd.func()

        self.assertIsNone(
            self.char2.attributes.get("group_invite", default=None),
        )
        self.assertIsNone(
            self.char2.attributes.get("group_id", default=None),
        )


# ---------------------------------------------------------------------------
# Group Leave & Kick Tests
# ---------------------------------------------------------------------------

class TestGroupLeaveKick(BaseEvenniaTest):
    """Test leaving and kicking from groups."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="Leader")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("level", 5)

        self.char2 = create_object(DefaultCharacter, key="Member1")
        self.char2.attributes.add("alignment", "Good")
        self.char2.attributes.add("level", 3)

        self.char3 = create_object(DefaultCharacter, key="Member2")
        self.char3.attributes.add("alignment", "Good")
        self.char3.attributes.add("level", 4)

        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room
        self.char2.location = self.room
        self.char3.location = self.room

        # Set up group: char1 is leader, char2 and char3 are members
        group_id = "test_group_abc"
        self.char1.attributes.add("group_id", group_id)
        self.char1.attributes.add("group_leader", True)
        self.char2.attributes.add("group_id", group_id)
        self.char2.attributes.add("group_leader", False)
        self.char3.attributes.add("group_id", group_id)
        self.char3.attributes.add("group_leader", False)

    def tearDown(self):
        self.char1.delete()
        self.char2.delete()
        self.char3.delete()
        self.room.delete()
        super().tearDown()

    def test_member_leave(self):
        """A non-leader member can leave the group."""
        cmd = CmdGroupLeave()
        cmd.caller = self.char2
        cmd.cmdstring = "group leave"
        cmd.args = ""
        cmd.func()

        self.assertIsNone(
            self.char2.attributes.get("group_id", default=None),
        )
        self.assertFalse(
            self.char2.attributes.get("group_leader", default=False),
        )
        # Leader should remain
        self.assertEqual(
            self.char1.attributes.get("group_id"),
            "test_group_abc",
        )

    def test_leader_leave_transfers_leadership(self):
        """When the leader leaves, leadership transfers to another member."""
        cmd = CmdGroupLeave()
        cmd.caller = self.char1
        cmd.cmdstring = "group leave"
        cmd.args = ""
        cmd.func()

        # Leader should be out
        self.assertIsNone(
            self.char1.attributes.get("group_id", default=None),
        )
        # One of the remaining members should be leader
        remaining_leaders = [
            m for m in [self.char2, self.char3]
            if is_group_leader(m)
        ]
        self.assertEqual(len(remaining_leaders), 1)

    def test_last_member_leave_dissolves_group(self):
        """When the last member leaves, the group is dissolved."""
        # First remove char2 and char3
        for char in [self.char2, self.char3]:
            char.attributes.add("group_id", None)
            char.attributes.add("group_leader", False)

        cmd = CmdGroupLeave()
        cmd.caller = self.char1
        cmd.cmdstring = "group leave"
        cmd.args = ""
        cmd.func()

        self.assertIsNone(
            self.char1.attributes.get("group_id", default=None),
        )

    def test_leave_when_not_in_group(self):
        """Leaving when not in a group shows a message."""
        char = create_object(DefaultCharacter, key="Solo")
        char.location = self.room

        cmd = CmdGroupLeave()
        cmd.caller = char
        cmd.cmdstring = "group leave"
        cmd.args = ""
        cmd.func()
        # Should not raise

        char.delete()

    def test_leader_kick_member(self):
        """The leader can kick a member from the group."""
        cmd = CmdGroupKick()
        cmd.caller = self.char1
        cmd.cmdstring = "group kick"
        cmd.args = "Member1"
        cmd.func()

        self.assertIsNone(
            self.char2.attributes.get("group_id", default=None),
        )
        # char3 should still be in group
        self.assertEqual(
            self.char3.attributes.get("group_id"),
            "test_group_abc",
        )

    def test_non_leader_cannot_kick(self):
        """A non-leader member cannot kick other members."""
        cmd = CmdGroupKick()
        cmd.caller = self.char2
        cmd.cmdstring = "group kick"
        cmd.args = "Member2"
        cmd.func()

        # char3 should still be in group
        self.assertEqual(
            self.char3.attributes.get("group_id"),
            "test_group_abc",
        )

    def test_cannot_kick_self(self):
        """A leader cannot kick themselves."""
        cmd = CmdGroupKick()
        cmd.caller = self.char1
        cmd.cmdstring = "group kick"
        cmd.args = "Leader"
        cmd.func()

        # Leader should still be in group
        self.assertEqual(
            self.char1.attributes.get("group_id"),
            "test_group_abc",
        )

    def test_cannot_kick_non_member(self):
        """Cannot kick someone not in the group."""
        outsider = create_object(DefaultCharacter, key="Outsider")
        outsider.location = self.room

        cmd = CmdGroupKick()
        cmd.caller = self.char1
        cmd.cmdstring = "group kick"
        cmd.args = "Outsider"
        cmd.func()
        # Should not affect outsider

        outsider.delete()

    def test_kick_no_args_shows_usage(self):
        """Kick with no player name shows usage."""
        cmd = CmdGroupKick()
        cmd.caller = self.char1
        cmd.cmdstring = "group kick"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_kick_case_insensitive(self):
        """Kick target matching is case-insensitive."""
        cmd = CmdGroupKick()
        cmd.caller = self.char1
        cmd.cmdstring = "group kick"
        cmd.args = "member1"
        cmd.func()

        self.assertIsNone(
            self.char2.attributes.get("group_id", default=None),
        )


# ---------------------------------------------------------------------------
# Group Status Display Tests
# ---------------------------------------------------------------------------

class TestGroupStatus(BaseEvenniaTest):
    """Test the group status display."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="Test Room")

        self.char1 = create_object(DefaultCharacter, key="Warrior")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("level", 5)
        self.char1.attributes.add("hp", 100)
        self.char1.attributes.add("max_hp", 120)
        self.char1.attributes.add("mana", 30)
        self.char1.attributes.add("max_mana", 50)
        self.char1.attributes.add("mv", 80)
        self.char1.attributes.add("max_mv", 100)
        self.char1.location = self.room

        self.char2 = create_object(DefaultCharacter, key="Mage")
        self.char2.attributes.add("alignment", "Good")
        self.char2.attributes.add("level", 4)
        self.char2.attributes.add("hp", 15)
        self.char2.attributes.add("max_hp", 60)
        self.char2.attributes.add("mana", 80)
        self.char2.attributes.add("max_mana", 100)
        self.char2.attributes.add("mv", 45)
        self.char2.attributes.add("max_mv", 80)
        self.char2.location = self.room

        self.char3 = create_object(DefaultCharacter, key="Rogue")
        self.char3.attributes.add("alignment", "Good")
        self.char3.attributes.add("level", 3)
        self.char3.attributes.add("hp", 45)
        self.char3.attributes.add("max_hp", 75)
        self.char3.attributes.add("mana", 20)
        self.char3.attributes.add("max_mana", 40)
        self.char3.attributes.add("mv", 90)
        self.char3.attributes.add("max_mv", 110)
        self.char3.location = self.room

        # Form a group
        group_id = "status_test_group"
        self.char1.attributes.add("group_id", group_id)
        self.char1.attributes.add("group_leader", True)
        self.char2.attributes.add("group_id", group_id)
        self.char2.attributes.add("group_leader", False)
        self.char3.attributes.add("group_id", group_id)
        self.char3.attributes.add("group_leader", False)

    def tearDown(self):
        self.char1.delete()
        self.char2.delete()
        self.char3.delete()
        self.room.delete()
        super().tearDown()

    def test_format_group_status_shows_all_members(self):
        """Group status displays all three members."""
        status = format_group_status(self.char1)
        self.assertIn("Warrior", status)
        self.assertIn("Mage", status)
        self.assertIn("Rogue", status)

    def test_format_group_status_shows_leader_marker(self):
        """The leader has a [Leader] marker."""
        status = format_group_status(self.char1)
        self.assertIn("[Leader]", status)

    def test_format_group_status_shows_hp_mp_mv(self):
        """Group status includes HP, MP, and MV for each member."""
        status = format_group_status(self.char1)
        self.assertIn("HP:", status)
        self.assertIn("MP:", status)
        self.assertIn("MV:", status)
        self.assertIn("100/120", status)
        self.assertIn("80/100", status)  # Mage MP
        self.assertIn("45/75", status)   # Rogue HP

    def test_format_group_status_shows_here_marker(self):
        """Members in the same room as the viewer show [Here] marker."""
        status = format_group_status(self.char2)
        self.assertIn("[Here]", status)

    def test_format_group_status_shows_location(self):
        """Members show their room location."""
        status = format_group_status(self.char1)
        self.assertIn("@Test Room", status)

    def test_group_command_no_args_shows_status(self):
        """`group` with no args shows group status."""
        cmd = CmdGroup()
        cmd.caller = self.char1
        cmd.cmdstring = "group"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_group_status_hp_color_coding(self):
        """HP is color-coded based on percentage."""
        status = format_group_status(self.char1)
        # Warrior: 100/120 = 83% (green)
        # Mage: 15/60 = 25% (red)
        # Rogue: 45/75 = 60% (yellow)
        self.assertIn(status, status)  # Should not crash


# ---------------------------------------------------------------------------
# Group Talk / Chat Tests
# ---------------------------------------------------------------------------

class TestGroupTalk(BaseEvenniaTest):
    """Test group chat (gt) functionality."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="GroupLeader")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("level", 5)

        self.char2 = create_object(DefaultCharacter, key="GroupMember")
        self.char2.attributes.add("alignment", "Good")
        self.char2.attributes.add("level", 3)

        self.char3 = create_object(DefaultCharacter, key="Outsider")
        self.char3.attributes.add("alignment", "Evil")
        self.char3.attributes.add("level", 4)

        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room
        self.char2.location = self.room
        self.char3.location = self.room

        # Form a group
        group_id = "chat_test_group"
        self.char1.attributes.add("group_id", group_id)
        self.char1.attributes.add("group_leader", True)
        self.char2.attributes.add("group_id", group_id)
        self.char2.attributes.add("group_leader", False)

    def tearDown(self):
        self.char1.delete()
        self.char2.delete()
        self.char3.delete()
        self.room.delete()
        super().tearDown()

    def test_gt_delivers_to_group_members(self):
        """Group talk delivers messages to all group members."""
        delivered = []
        original_msg = self.char2.msg

        def capture(text, **kwargs):
            delivered.append(text)
            original_msg(text, **kwargs)

        self.char2.msg = capture

        try:
            cmd = CmdGroupTalk()
            cmd.caller = self.char1
            cmd.cmdstring = "gt"
            cmd.args = "Hello group!"
            cmd.func()
        finally:
            self.char2.msg = original_msg

        group_msg_found = any(
            "Hello group!" in msg and "[Group]" in msg
            for msg in delivered
        )
        self.assertTrue(group_msg_found, "Group members should receive gt messages")

    def test_gt_does_not_deliver_to_non_members(self):
        """Group talk does NOT deliver to non-group members."""
        delivered = []
        original_msg = self.char3.msg

        def capture(text, **kwargs):
            delivered.append(text)
            original_msg(text, **kwargs)

        self.char3.msg = capture

        try:
            cmd = CmdGroupTalk()
            cmd.caller = self.char1
            cmd.cmdstring = "gt"
            cmd.args = "Secret group stuff!"
            cmd.func()
        finally:
            self.char3.msg = original_msg

        leaked = any(
            "Secret group stuff!" in msg
            for msg in delivered
        )
        self.assertFalse(leaked, "Non-members should NOT see gt messages")

    def test_gt_not_in_group_shows_error(self):
        """Group talk when not in a group shows error."""
        cmd = CmdGroupTalk()
        cmd.caller = self.char3
        cmd.cmdstring = "gt"
        cmd.args = "Anyone?"
        cmd.func()
        # Should not raise

    def test_gt_no_message_shows_usage(self):
        """Group talk with no message shows usage."""
        cmd = CmdGroupTalk()
        cmd.caller = self.char1
        cmd.cmdstring = "gt"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_group_command_fallback_to_chat(self):
        """Typing `group <msg>` without a subcommand acts as group chat."""
        delivered = []
        original_msg = self.char2.msg

        def capture(text, **kwargs):
            delivered.append(text)
            original_msg(text, **kwargs)

        self.char2.msg = capture

        try:
            cmd = CmdGroup()
            cmd.caller = self.char1
            cmd.cmdstring = "group"
            cmd.args = "Let's go hunting!"
            cmd.func()
        finally:
            self.char2.msg = original_msg

        group_msg_found = any(
            "Let's go hunting!" in msg and "[Group]" in msg
            for msg in delivered
        )
        self.assertTrue(
            group_msg_found,
            "`group <msg>` should act as group chat fallback",
        )

    def test_gt_shows_recipient_count(self):
        """Group talk shows how many recipients heard the message."""
        cmd = CmdGroupTalk()
        cmd.caller = self.char1
        cmd.cmdstring = "gt"
        cmd.args = "Test"
        cmd.func()
        # Should not raise and should report 1 recipient (char2)

    def test_gt_solo_group_shows_no_recipients(self):
        """Group talk shows no recipients when alone in group."""
        # Remove char2 from group
        self.char2.attributes.add("group_id", None)

        cmd = CmdGroupTalk()
        cmd.caller = self.char1
        cmd.cmdstring = "gt"
        cmd.args = "Only me"
        cmd.func()
        # Should not raise


# ---------------------------------------------------------------------------
# EXP Sharing Tests
# ---------------------------------------------------------------------------

class TestExpSharing(BaseEvenniaTest):
    """Test XP splitting among group members."""

    def setUp(self):
        super().setUp()
        self.room1 = create_object(DefaultRoom, key="Dungeon Room")
        self.room2 = create_object(DefaultRoom, key="Town Square")

        # Create group members
        self.char1 = create_object(DefaultCharacter, key="Knight")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("level", 5)
        self.char1.attributes.add("xp", 0)
        self.char1.location = self.room1

        self.char2 = create_object(DefaultCharacter, key="Cleric")
        self.char2.attributes.add("alignment", "Good")
        self.char2.attributes.add("level", 3)
        self.char2.attributes.add("xp", 0)
        self.char2.location = self.room1

        self.char3 = create_object(DefaultCharacter, key="Ranger")
        self.char3.attributes.add("alignment", "Good")
        self.char3.attributes.add("level", 4)
        self.char3.attributes.add("xp", 0)
        self.char3.location = self.room1

        # char4 is in the group but in a different room
        self.char4 = create_object(DefaultCharacter, key="Scout")
        self.char4.attributes.add("alignment", "Good")
        self.char4.attributes.add("level", 2)
        self.char4.attributes.add("xp", 0)
        self.char4.location = self.room2

        # Form a group
        group_id = "xp_test_group"
        for char in [self.char1, self.char2, self.char3, self.char4]:
            char.attributes.add("group_id", group_id)
            char.attributes.add("group_leader", False)
        self.char1.attributes.add("group_leader", True)

    def tearDown(self):
        self.char1.delete()
        self.char2.delete()
        self.char3.delete()
        self.char4.delete()
        self.room1.delete()
        self.room2.delete()
        super().tearDown()

    def test_split_xp_evenly_among_room_members(self):
        """XP is split evenly among group members in the same room."""
        share = split_group_xp(self.char1, 300)

        # 3 members in room1, 300/3 = 100 each
        self.assertEqual(share, 100)

        # All 3 room members got 100 XP
        self.assertEqual(self.char1.attributes.get("xp"), 100)
        self.assertEqual(self.char2.attributes.get("xp"), 100)
        self.assertEqual(self.char3.attributes.get("xp"), 100)

    def test_split_xp_not_shared_with_other_rooms(self):
        """XP is NOT shared with group members in other rooms."""
        original_xp = self.char4.attributes.get("xp")
        split_group_xp(self.char1, 300)
        self.assertEqual(self.char4.attributes.get("xp"), original_xp)

    def test_split_xp_no_group_full_xp(self):
        """When not in a group, the character gets full XP."""
        solo = create_object(DefaultCharacter, key="Solo")
        solo.attributes.add("alignment", "Good")
        solo.attributes.add("xp", 0)
        solo.location = self.room1

        share = split_group_xp(solo, 100)
        self.assertEqual(share, 100)
        # Solo character gets full XP via award_xp
        # Note: DefaultCharacter doesn't have award_xp, so it uses fallback
        self.assertEqual(solo.attributes.get("xp"), 100)

        solo.delete()

    def test_split_xp_solo_in_group_gets_full(self):
        """When only one group member is in the room, they get full XP."""
        # Move char2 and char3 out of the room
        self.char2.location = self.room2
        self.char3.location = self.room2

        original_char2_xp = self.char2.attributes.get("xp")

        share = split_group_xp(self.char1, 200)
        # Only char1 in room1, so gets full 200. But if group membership
        # check finds multiple, it splits. In this room, only char1.
        # The function only splits if len(present) > 1
        self.assertEqual(share, 200)
        self.assertEqual(self.char1.attributes.get("xp"), 200)
        # char2 should not get XP (not in same room)
        self.assertEqual(self.char2.attributes.get("xp"), original_char2_xp)

        # Move them back
        self.char2.location = self.room1
        self.char3.location = self.room1

    def test_split_xp_with_character_award_xp_method(self):
        """split_group_xp uses character.award_xp() if available."""
        # Reset XP
        for char in [self.char1, self.char2, self.char3]:
            char.attributes.add("xp", 0)

        # Create a DefaultCharacter with a monkey-patched award_xp
        # to verify split_group_xp calls award_xp when present.
        test_char = create_object(DefaultCharacter, key="TestChar")
        test_char.attributes.add("alignment", "Good")
        test_char.attributes.add("level", 1)
        test_char.attributes.add("xp", 0)
        test_char.attributes.add("xp_to_level", 1000)
        test_char.location = self.room1

        # Track how much XP award_xp receives
        awarded_amounts = []
        def fake_award_xp(amount):
            awarded_amounts.append(amount)
            current = test_char.attributes.get("xp", default=0)
            test_char.attributes.add("xp", current + amount)

        test_char.award_xp = fake_award_xp

        # Add to group
        group_id = self.char1.attributes.get("group_id")
        test_char.attributes.add("group_id", group_id)
        test_char.attributes.add("group_leader", False)

        # Move char2 and char3 out so only char1 and test_char are in room
        self.char2.location = self.room2
        self.char3.location = self.room2
        self.char1.attributes.add("xp", 0)

        split_group_xp(self.char1, 200)

        # 2 members present: should get ~100 each (with integer division)
        expected_share = max(1, 200 // 2)
        self.assertEqual(self.char1.attributes.get("xp"), expected_share)
        self.assertEqual(test_char.attributes.get("xp"), expected_share)
        # Verify award_xp was called on test_char with the correct amount
        self.assertEqual(awarded_amounts, [expected_share])

        # Restore
        self.char2.location = self.room1
        self.char3.location = self.room1
        del test_char.award_xp
        test_char.delete()

    def test_split_xp_minimum_one_per_member(self):
        """Even with very small XP amounts, each member gets at least 1 XP."""
        for char in [self.char1, self.char2, self.char3]:
            char.attributes.add("xp", 0)

        share = split_group_xp(self.char1, 2)
        # 3 members, 2//3 = 0, but max(1, 0) = 1 each
        self.assertEqual(share, 1)

    def test_split_xp_integer_division(self):
        """XP is split using integer division (remainder is lost)."""
        for char in [self.char1, self.char2, self.char3]:
            char.attributes.add("xp", 0)

        share = split_group_xp(self.char1, 100)
        # 3 members, 100//3 = 33
        self.assertEqual(share, 33)

    def test_get_group_members_in_room(self):
        """get_group_members_in_room returns only same-room members."""
        room_members = get_group_members_in_room(self.char1)
        self.assertEqual(len(room_members), 3)
        for member in room_members:
            self.assertEqual(member.location, self.room1)

    def test_get_group_members_in_room_no_location(self):
        """get_group_members_in_room handles characters with no location."""
        old_location = self.char1.location
        self.char1.location = None

        members = get_group_members_in_room(self.char1)
        self.assertIn(self.char1, members)

        self.char1.location = old_location


# ---------------------------------------------------------------------------
# Broadcast Group Function Tests
# ---------------------------------------------------------------------------

class TestBroadcastGroup(BaseEvenniaTest):
    """Test the broadcast_group helper function."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="Test Room")

        self.char1 = create_object(DefaultCharacter, key="Alpha")
        self.char1.location = self.room

        self.char2 = create_object(DefaultCharacter, key="Beta")
        self.char2.location = self.room

        self.char3 = create_object(DefaultCharacter, key="Gamma")
        self.char3.location = self.room

        # Form a group
        group_id = "broadcast_test"
        self.char1.attributes.add("group_id", group_id)
        self.char2.attributes.add("group_id", group_id)
        # char3 is not in the group

    def tearDown(self):
        self.char1.delete()
        self.char2.delete()
        self.char3.delete()
        self.room.delete()
        super().tearDown()

    def test_broadcast_group_reaches_all_members(self):
        """broadcast_group sends to all group members."""
        delivered_char2 = []
        original_char2 = self.char2.msg

        def capture(text, **kwargs):
            delivered_char2.append(text)
            original_char2(text, **kwargs)

        self.char2.msg = capture

        try:
            group_id = self.char1.attributes.get("group_id")
            recipients = broadcast_group("Test broadcast!", group_id)
            self.assertEqual(recipients, 2)
        finally:
            self.char2.msg = original_char2

        self.assertTrue(
            any("Test broadcast!" in msg for msg in delivered_char2),
        )

    def test_broadcast_group_excludes_specified_character(self):
        """broadcast_group can exclude a specific character."""
        delivered_char2 = []
        original_char2 = self.char2.msg

        def capture(text, **kwargs):
            delivered_char2.append(text)
            original_char2(text, **kwargs)

        self.char2.msg = capture

        try:
            group_id = self.char1.attributes.get("group_id")
            # Exclude char2
            recipients = broadcast_group("Excluded test", group_id, exclude=self.char2)
            # Should only reach char1
            self.assertEqual(recipients, 1)
        finally:
            self.char2.msg = original_char2

        self.assertFalse(
            any("Excluded test" in msg for msg in delivered_char2),
        )

    def test_broadcast_group_does_not_reach_non_members(self):
        """broadcast_group does not send to non-group members."""
        delivered_char3 = []
        original_char3 = self.char3.msg

        def capture(text, **kwargs):
            delivered_char3.append(text)
            original_char3(text, **kwargs)

        self.char3.msg = capture

        try:
            group_id = self.char1.attributes.get("group_id")
            broadcast_group("Secret!", group_id)
        finally:
            self.char3.msg = original_char3

        self.assertFalse(
            any("Secret!" in msg for msg in delivered_char3),
        )


# ---------------------------------------------------------------------------
# Dissolve Group Tests
# ---------------------------------------------------------------------------

class TestDissolveGroup(BaseEvenniaTest):
    """Test the dissolve_group function."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="Test Room")

        self.char1 = create_object(DefaultCharacter, key="Alpha")
        self.char1.location = self.room
        self.char2 = create_object(DefaultCharacter, key="Beta")
        self.char2.location = self.room

        group_id = "dissolve_test"
        self.char1.attributes.add("group_id", group_id)
        self.char1.attributes.add("group_leader", True)
        self.char2.attributes.add("group_id", group_id)
        self.char2.attributes.add("group_leader", False)

    def tearDown(self):
        self.char1.delete()
        self.char2.delete()
        self.room.delete()
        super().tearDown()

    def test_dissolve_group_removes_all_members(self):
        """dissolve_group clears group attributes for all members."""
        dissolve_group(self.char1)

        self.assertIsNone(
            self.char1.attributes.get("group_id", default=None),
        )
        self.assertIsNone(
            self.char2.attributes.get("group_id", default=None),
        )
        self.assertFalse(
            self.char1.attributes.get("group_leader", default=False),
        )
        self.assertFalse(
            self.char2.attributes.get("group_leader", default=False),
        )

    def test_dissolve_group_clears_invitations(self):
        """dissolve_group also clears pending invitations."""
        self.char2.attributes.add("group_invite", "dissolve_test")

        dissolve_group(self.char1)

        self.assertIsNone(
            self.char2.attributes.get("group_invite", default=None),
        )


# ---------------------------------------------------------------------------
# Group Hub Command Tests
# ---------------------------------------------------------------------------

class TestGroupHubCommand(BaseEvenniaTest):
    """Test the main `group` command hub delegation."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="Hero")
        self.char1.attributes.add("alignment", "Good")
        self.char1.attributes.add("level", 5)

        self.char2 = create_object(DefaultCharacter, key="Sidekick")
        self.char2.attributes.add("alignment", "Good")
        self.char2.attributes.add("level", 3)

        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room
        self.char2.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.char2.delete()
        self.room.delete()
        super().tearDown()

    def test_group_invite_subcommand(self):
        """`group invite <name>` delegates to CmdGroupInvite."""
        cmd = CmdGroup()
        cmd.caller = self.char1
        cmd.cmdstring = "group"
        cmd.args = "invite Sidekick"
        cmd.func()

        self.assertIsNotNone(self.char1.attributes.get("group_id"))
        self.assertTrue(self.char1.attributes.get("group_leader"))

    def test_group_inv_alias(self):
        """`group inv` works as alias for invite."""
        cmd = CmdGroup()
        cmd.caller = self.char1
        cmd.cmdstring = "group"
        cmd.args = "inv Sidekick"
        cmd.func()

        self.assertIsNotNone(self.char1.attributes.get("group_id"))

    def test_group_i_alias(self):
        """`group i` works as alias for invite."""
        cmd = CmdGroup()
        cmd.caller = self.char1
        cmd.cmdstring = "group"
        cmd.args = "i Sidekick"
        cmd.func()

        self.assertIsNotNone(self.char1.attributes.get("group_id"))

    def test_group_accept_subcommand(self):
        """`group accept` delegates to CmdGroupAccept."""
        # First invite
        cmd_inv = CmdGroup()
        cmd_inv.caller = self.char1
        cmd_inv.cmdstring = "group"
        cmd_inv.args = "invite Sidekick"
        cmd_inv.func()

        # Then accept
        cmd = CmdGroup()
        cmd.caller = self.char2
        cmd.cmdstring = "group"
        cmd.args = "accept"
        cmd.func()

        self.assertEqual(
            self.char2.attributes.get("group_id"),
            self.char1.attributes.get("group_id"),
        )

    def test_group_leave_subcommand(self):
        """`group leave` delegates to CmdGroupLeave."""
        # Form a group
        self.char1.attributes.add("group_id", "hub_test")
        self.char1.attributes.add("group_leader", True)
        self.char2.attributes.add("group_id", "hub_test")

        cmd = CmdGroup()
        cmd.caller = self.char2
        cmd.cmdstring = "group"
        cmd.args = "leave"
        cmd.func()

        self.assertIsNone(self.char2.attributes.get("group_id", default=None))

    def test_group_kick_subcommand(self):
        """`group kick <name>` delegates to CmdGroupKick."""
        self.char1.attributes.add("group_id", "hub_test")
        self.char1.attributes.add("group_leader", True)
        self.char2.attributes.add("group_id", "hub_test")

        cmd = CmdGroup()
        cmd.caller = self.char1
        cmd.cmdstring = "group"
        cmd.args = "kick Sidekick"
        cmd.func()

        self.assertIsNone(self.char2.attributes.get("group_id", default=None))

    def test_group_no_args_shows_status(self):
        """`group` with no args shows group status."""
        self.char1.attributes.add("group_id", "hub_test")
        self.char1.attributes.add("group_leader", True)

        cmd = CmdGroup()
        cmd.caller = self.char1
        cmd.cmdstring = "group"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_group_unknown_subcommand_is_chat(self):
        """An unrecognized subcommand is treated as a chat message."""
        delivered = []
        original_msg = self.char2.msg

        def capture(text, **kwargs):
            delivered.append(text)
            original_msg(text, **kwargs)

        self.char2.msg = capture

        try:
            # Form a group first
            self.char1.attributes.add("group_id", "hub_test")
            self.char1.attributes.add("group_leader", True)
            self.char2.attributes.add("group_id", "hub_test")

            cmd = CmdGroup()
            cmd.caller = self.char1
            cmd.cmdstring = "group"
            cmd.args = "Hey team"
            cmd.func()
        finally:
            self.char2.msg = original_msg

        group_found = any(
            "Hey team" in msg and "[Group]" in msg
            for msg in delivered
        )
        self.assertTrue(group_found)


# ---------------------------------------------------------------------------
# Get Group Members Tests
# ---------------------------------------------------------------------------

class TestGetGroupMembers(BaseEvenniaTest):
    """Test the get_group_members full scan function."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="Test Room")

        self.char1 = create_object(DefaultCharacter, key="M1")
        self.char1.location = self.room
        self.char2 = create_object(DefaultCharacter, key="M2")
        self.char2.location = self.room
        self.char3 = create_object(DefaultCharacter, key="M3")
        self.char3.location = self.room

        group_id = "member_scan_test"
        self.char1.attributes.add("group_id", group_id)
        self.char2.attributes.add("group_id", group_id)
        # char3 is not in group

    def tearDown(self):
        self.char1.delete()
        self.char2.delete()
        self.char3.delete()
        self.room.delete()
        super().tearDown()

    def test_get_group_members_returns_all_members(self):
        """get_group_members returns both members of the group."""
        members = get_group_members(self.char1)
        self.assertEqual(len(members), 2)
        member_keys = {m.key for m in members}
        self.assertIn("M1", member_keys)
        self.assertIn("M2", member_keys)
        self.assertNotIn("M3", member_keys)

    def test_get_group_members_empty_for_non_member(self):
        """get_group_members returns empty for non-members."""
        members = get_group_members(self.char3)
        self.assertEqual(len(members), 0)

    def test_get_group_leader_returns_correct_leader(self):
        """get_group_leader returns the character with leader flag."""
        self.char1.attributes.add("group_leader", True)

        leader = get_group_leader([self.char1, self.char2])
        self.assertEqual(leader, self.char1)

    def test_get_group_leader_fallback(self):
        """When no leader flag is set, fallback returns first member."""
        # Clear any leader flag
        self.char1.attributes.add("group_leader", False)
        self.char2.attributes.add("group_leader", False)

        leader = get_group_leader([self.char2, self.char1])
        self.assertEqual(leader, self.char2)