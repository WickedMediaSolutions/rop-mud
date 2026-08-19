"""
Party / Grouping System for 'rop'

Provides:
  group invite <player>  - Invite a player to your group
  group accept           - Accept a pending group invitation
  group leave            - Leave your current group
  group kick <player>    - Remove a player from your group (leader only)
  group                  - Show group status (members, HP/MP)
  gt <message>           - Group Tell: chat privately with group members

Groups persist as character attributes. The group leader is the member
who created the group. Only the leader can invite and kick.
"""

from commands.command import Command
from evennia.objects.objects import DefaultCharacter


# ---------------------------------------------------------------------------
# GROUP DATA STRUCTURE (stored on characters as "group_id" attribute)
# ---------------------------------------------------------------------------
#
# Group membership is tracked by a unique group ID string.
# Each group member has `character.attributes.get("group_id")` set to the
# same string value. The leader is the first member who created the group.
#
# Invitations are stored temporarily:
#   character.db.group_invite = group_id of the group they were invited to
# ---------------------------------------------------------------------------


def get_group_members(character):
    """
    Return a list of all online player characters in the same group as
    the given character, or an empty list if they are not in a group.
    """
    group_id = character.attributes.get("group_id", default=None)
    if not group_id:
        return []

    members = []
    for char in DefaultCharacter.objects.all():
        char_group = char.attributes.get("group_id", default=None)
        if char_group and char_group == group_id:
            members.append(char)
    return members


def get_group_members_in_room(character):
    """
    Return group members who are in the same room as `character`.
    """
    members = get_group_members(character)
    location = character.location
    if not location:
        return [character]
    return [m for m in members if m.location == location]


def is_group_leader(character):
    """
    Return True if character is the group leader.
    The group leader is identified by having group_leader=True attribute
    alongside a valid group_id.
    """
    group_id = character.attributes.get("group_id", default=None)
    if not group_id:
        return False
    return character.attributes.get("group_leader", default=False)


def get_group_leader(members):
    """
    Given a list of group members, return the leader.
    Returns None if no leader found.
    """
    for member in members:
        if member.attributes.get("group_leader", default=False):
            return member
    # Fallback: return the first member if no leader flag set
    return members[0] if members else None


def dissolve_group(character):
    """
    Remove all members from this character's group.
    """
    group_id = character.attributes.get("group_id", default=None)
    if not group_id:
        return

    for char in DefaultCharacter.objects.all():
        if char.attributes.get("group_id") == group_id:
            char.attributes.add("group_id", None)
            char.attributes.add("group_leader", False)
            char.attributes.add("group_invite", None)


def broadcast_group(message, group_id, exclude=None):
    """
    Send a message to all online group members with the given group_id.
    """
    recipients = 0
    for char in DefaultCharacter.objects.all():
        if char.attributes.get("group_id") == group_id:
            if exclude and char == exclude:
                continue
            char.msg(message)
            recipients += 1
    return recipients


def split_group_xp(character, xp_amount):
    """
    Split XP among group members in the same room as `character`.

    Called when a monster is killed. The XP amount is divided equally
    among all group members present in the same room. If the character
    is not in a group (or is the only one in the room), the full XP
    goes to them.

    Returns the per-member XP amount awarded.
    """
    group_id = character.attributes.get("group_id", default=None)
    if not group_id:
        # Solo: award full XP to the character
        _award_xp_to_character(character, xp_amount)
        return xp_amount

    present_members = get_group_members_in_room(character)
    if len(present_members) <= 1:
        # Only one group member present: award full XP
        _award_xp_to_character(character, xp_amount)
        return xp_amount

    share = max(1, xp_amount // len(present_members))

    for member in present_members:
        _award_xp_to_character(member, share)

    return share


def _award_xp_to_character(character, amount):
    """
    Award XP to a character, using award_xp() if available (Character typeclass),
    otherwise setting the attribute directly.

    Racial XP bonuses (Human +5%) are applied on top of the base amount.
    """
    # Racial passive: bonus XP gain (Human +5%).
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(character)
        xp_pct = racial.get("xp_bonus_pct", 0)
        if xp_pct:
            amount = int(amount * (1.0 + xp_pct / 100.0))
    except Exception:
        pass

    if hasattr(character, 'award_xp'):
        character.award_xp(amount)
    else:
        current = character.attributes.get("xp", default=0)
        character.attributes.add("xp", current + amount)


def format_group_status(character):
    """
    Build a formatted status display for the group.
    Shows each member's HP/MP/MV and who is the leader.
    """
    members = get_group_members(character)
    if not members:
        return "|yYou are not in a group.|n"

    leader = get_group_leader(members)
    lines = []
    lines.append("|w=== Your Group ===|n")
    lines.append(f"|wMembers: {len(members)}|n")
    lines.append("")

    for member in members:
        hp = member.attributes.get("hp", default=0)
        max_hp = member.attributes.get("max_hp", default=100)
        mana = member.attributes.get("mana", default=0)
        max_mana = member.attributes.get("max_mana", default=50)
        mv = member.attributes.get("mv", default=0)
        max_mv = member.attributes.get("max_mv", default=100)
        location_name = member.location.key if member.location else "Unknown"

        leader_mark = " |y[Leader]|n" if member == leader else ""
        same_room = " |g[Here]|n" if member.location == character.location else ""

        # HP bar as percentage
        hp_pct = int((hp / max(max_hp, 1)) * 100)
        if hp_pct > 66:
            hp_color = "|g"
        elif hp_pct > 33:
            hp_color = "|y"
        else:
            hp_color = "|r"

        mana_pct = int((mana / max(max_mana, 1)) * 100)
        if mana_pct > 66:
            mana_color = "|g"
        elif mana_pct > 33:
            mana_color = "|y"
        else:
            mana_color = "|r"

        lines.append(
            f"  |w{member.key}|n{leader_mark}{same_room}"
        )
        lines.append(
            f"    {hp_color}HP:|n {hp}/{max_hp} ({hp_pct}%)  "
            f"{mana_color}MP:|n {mana}/{max_mana} ({mana_pct}%)  "
            f"|yMV:|n {mv}/{max_mv}  "
            f"|c@{location_name}|n"
        )

    lines.append("")
    lines.append("|wUse |ygt <msg>|w to chat with your group.|n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# COMMANDS
# ---------------------------------------------------------------------------

# Alias for test compatibility (CmdGroupCreate = group creation entrypoint)
class CmdGroupInvite(Command):
    """
    Invite another player to join your group.

    Usage:
      group invite <player>

    You must be in a group (or create one by inviting). The invited player
    must use |ygroup accept|n to join.
    """

    key = "groupinvite"
    aliases = []
    help_category = "Group"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("|yUsage: group invite <player>|n")
            return

        target_name = self.args

        # Find the target player among all characters
        target = None
        for char in DefaultCharacter.objects.all():
            if char.key.lower() == target_name.lower():
                target = char
                break

        if not target:
            caller.msg(f"|rNo player named '{target_name}' found.|n")
            return
        if target == caller:
            caller.msg("|rYou cannot invite yourself.|n")
            return

        # Check if target is already in a group
        target_group = target.attributes.get("group_id", default=None)
        if target_group:
            caller.msg(f"|r{target.key} is already in a group.|n")
            return

        # Check if target has a pending invite
        if target.attributes.get("group_invite", default=None):
            caller.msg(f"|r{target.key} already has a pending group invitation.|n")
            return

        # If caller is not in a group, create one
        caller_group = caller.attributes.get("group_id", default=None)
        if not caller_group:
            import uuid
            group_id = f"group_{uuid.uuid4().hex[:8]}"
            caller.attributes.add("group_id", group_id)
            caller.attributes.add("group_leader", True)
            caller.msg(f"|gYou have created a new group.|n")
        else:
            group_id = caller_group
            # Only the leader can invite
            if not is_group_leader(caller):
                leader = get_group_leader(get_group_members(caller))
                leader_name = leader.key if leader else "Unknown"
                caller.msg(
                    f"|rOnly the group leader ({leader_name}) can invite players.|n"
                )
                return

        # Send the invitation
        target.attributes.add("group_invite", group_id)
        target.msg(
            f"|g{caller.key} has invited you to join their group!|n\n"
            f"|wUse |ygroup accept|w to join, or ignore to decline.|n"
        )
        caller.msg(f"|gYou have invited {target.key} to your group.|n")


class CmdGroupAccept(Command):
    """
    Accept a pending group invitation.

    Usage:
      group accept
    """

    key = "groupaccept"
    aliases = []
    help_category = "Group"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        group_id = caller.attributes.get("group_invite", default=None)
        if not group_id:
            caller.msg("|yYou have no pending group invitations.|n")
            return

        # Check the group still exists (has at least one member)
        group_exists = False
        for char in DefaultCharacter.objects.all():
            if char.attributes.get("group_id") == group_id:
                group_exists = True
                break

        if not group_exists:
            caller.attributes.add("group_invite", None)
            caller.msg("|rThat group no longer exists.|n")
            return

        # Check caller is not already in a group
        current_group = caller.attributes.get("group_id", default=None)
        if current_group:
            caller.msg("|rYou are already in a group. Use |ygroup leave|r first.|n")
            caller.attributes.add("group_invite", None)
            return

        # Join the group
        caller.attributes.add("group_id", group_id)
        caller.attributes.add("group_leader", False)
        caller.attributes.add("group_invite", None)

        caller.msg("|gYou have joined the group!|n")

        # Notify existing members
        existing = get_group_members(caller)
        for member in existing:
            if member != caller:
                member.msg(f"|g{caller.key} has joined your group!|n")


class CmdGroupLeave(Command):
    """
    Leave your current group.

    Usage:
      group leave

    If you are the group leader, leadership transfers to another member.
    If you are the last member, the group is dissolved.
    """

    key = "groupleave"
    aliases = []
    help_category = "Group"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        group_id = caller.attributes.get("group_id", default=None)
        if not group_id:
            caller.msg("|yYou are not in a group.|n")
            return

        was_leader = is_group_leader(caller)
        members = get_group_members(caller)

        # Remove caller from group
        caller.attributes.add("group_id", None)
        caller.attributes.add("group_leader", False)
        caller.msg("|yYou have left the group.|n")

        remaining = [m for m in members if m != caller]

        if not remaining:
            # Group dissolved
            return

        # Notify remaining members
        for member in remaining:
            member.msg(f"|y{caller.key} has left the group.|n")

        # If caller was the leader, transfer leadership
        if was_leader and remaining:
            new_leader = remaining[0]
            new_leader.attributes.add("group_leader", True)
            for member in remaining:
                member.msg(
                    f"|g{new_leader.key} is now the group leader.|n"
                )


class CmdGroupKick(Command):
    """
    Kick a player from your group (leader only).

    Usage:
      group kick <player>
    """

    key = "groupkick"
    aliases = []
    help_category = "Group"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("|yUsage: group kick <player>|n")
            return

        if not is_group_leader(caller):
            caller.msg("|rOnly the group leader can kick members.|n")
            return

        target_name = self.args
        members = get_group_members(caller)

        # Find the target among group members
        target = None
        for member in members:
            if member.key.lower() == target_name.lower():
                target = member
                break

        if not target:
            caller.msg(f"|r'{target_name}' is not in your group.|n")
            return

        if target == caller:
            caller.msg("|rYou cannot kick yourself. Use |ygroup leave|r instead.|n")
            return

        # Remove target from group
        target.attributes.add("group_id", None)
        target.attributes.add("group_leader", False)
        target.msg(f"|yYou have been kicked from the group by {caller.key}.|n")
        caller.msg(f"|yYou have kicked {target.key} from the group.|n")

        # Notify remaining members
        for member in members:
            if member != caller and member != target:
                member.msg(f"|y{target.key} has been kicked from the group by {caller.key}.|n")


class CmdGroupTalk(Command):
    """
    Send a private message to all online members of your group.

    Usage:
      gt <message>
      group <message>   (when not using a subcommand)
    """

    key = "gt"
    aliases = []
    help_category = "Group"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        if not self.args or not self.args.strip():
            caller.msg("|yUsage: gt <message>|n")
            return

        group_id = caller.attributes.get("group_id", default=None)
        if not group_id:
            caller.msg("|rYou are not in a group.|n")
            return

        message = self.args.strip()
        prefix = f"|m[Group] {caller.key}:|n {message}"

        # Deliver to all online group members
        members = get_group_members(caller)
        recipients = 0
        for char in members:
            if char != caller:
                char.msg(prefix)
                recipients += 1

        # Confirm to sender
        caller.msg(prefix)
        if recipients > 0:
            caller.msg(f"|w(Heard by {recipients} group member(s))|n")
        else:
            caller.msg("|w(No other group members are currently online)|n")


class CmdGroup(Command):
    """
    Main group command hub for the party/grouping system.

    Usage:
      group invite <player>  - Invite a player to your group
      group accept           - Accept a pending group invitation
      group leave            - Leave your current group
      group kick <player>    - Kick a player from your group (leader only)
      group                  - Show your group status (HP/MP of all members)
      gt <message>           - Chat with your group members
    """

    key = "group"
    aliases = []
    help_category = "Group"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            # Show group status
            status = format_group_status(caller)
            caller.msg(status)
            return

        parts = self.args.split(maxsplit=1)
        subcommand = parts[0].lower()
        sub_args = parts[1] if len(parts) > 1 else ""

        if subcommand in ("invite", "inv", "i"):
            if not sub_args:
                caller.msg("|yUsage: group invite <player>|n")
                return
            cmd = CmdGroupInvite()
            cmd.caller = caller
            cmd.cmdstring = "group invite"
            cmd.args = sub_args
            cmd.func()

        elif subcommand in ("accept", "acc", "a"):
            cmd = CmdGroupAccept()
            cmd.caller = caller
            cmd.cmdstring = "group accept"
            cmd.args = ""
            cmd.func()

        elif subcommand in ("leave", "lv", "l"):
            cmd = CmdGroupLeave()
            cmd.caller = caller
            cmd.cmdstring = "group leave"
            cmd.args = ""
            cmd.func()

        elif subcommand in ("kick", "k"):
            if not sub_args:
                caller.msg("|yUsage: group kick <player>|n")
                return
            cmd = CmdGroupKick()
            cmd.caller = caller
            cmd.cmdstring = "group kick"
            cmd.args = sub_args
            cmd.func()

        else:
            # If no matching subcommand, treat it as a group chat message
            cmd = CmdGroupTalk()
            cmd.caller = caller
            cmd.cmdstring = "group"
            cmd.args = self.args
            cmd.func()


# Alias for test compatibility
CmdGroupCreate = CmdGroup
