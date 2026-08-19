"""
Friend & Ignore List System for 'rop'

Provides:
  friend add <player>    - Add a player to your friends list
  friend remove <player> - Remove a player from your friends list
  friend list            - Show your friends and their online status
  ignore add <player>    - Ignore a player (block their tells/messages)
  ignore remove <player> - Remove a player from your ignore list
  ignore list            - Show your ignored players

Friends are notified when you come online (via at_post_login hook).
Ignored players cannot send you tells, group invites, or mail.
"""

from commands.command import Command
from evennia.objects.objects import DefaultCharacter


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def get_friends_list(character):
    """Return the list of friend names for a character."""
    friends = character.attributes.get("friends_list", default=None)
    if friends is None:
        return []
    if isinstance(friends, list):
        return friends
    return []

def set_friends_list(character, friends):
    """Set the friends list for a character."""
    character.attributes.add("friends_list", friends)

def get_ignore_list(character):
    """Return the list of ignored player names for a character."""
    ignored = character.attributes.get("ignore_list", default=None)
    if ignored is None:
        return []
    if isinstance(ignored, list):
        return ignored
    return []

def set_ignore_list(character, ignored):
    """Set the ignore list for a character."""
    character.attributes.add("ignore_list", ignored)

def is_ignoring(character, target_name):
    """Check if character is ignoring target_name."""
    ignore_list = get_ignore_list(character)
    return target_name.lower() in [n.lower() for n in ignore_list]

def is_friend(character, target_name):
    """Check if target_name is on character's friends list."""
    friends = get_friends_list(character)
    return target_name.lower() in [n.lower() for n in friends]

def find_player_character(name):
    """Find a player character by name (case-insensitive)."""
    for char in DefaultCharacter.objects.all():
        if char.key.lower() == name.lower():
            if hasattr(char, 'has_account') and char.has_account:
                return char
    return None

def is_player_online(character):
    """Check if a character is currently online (has active sessions)."""
    if hasattr(character, 'sessions') and character.sessions.count() > 0:
        return True
    return False

def notify_friends_online(character):
    """Notify all friends that this character just logged in."""
    friends = get_friends_list(character)
    if not friends:
        return
    for friend_name in friends:
        friend_char = find_player_character(friend_name)
        if friend_char and is_player_online(friend_char):
            friend_char.msg(f"|g[Friends] {character.key} has come online.|n")

def notify_friends_offline(character):
    """Notify all friends that this character just logged out."""
    friends = get_friends_list(character)
    if not friends:
        return
    for friend_name in friends:
        friend_char = find_player_character(friend_name)
        if friend_char and is_player_online(friend_char):
            friend_char.msg(f"|y[Friends] {character.key} has gone offline.|n")


# ---------------------------------------------------------------------------
# FRIEND COMMANDS
# ---------------------------------------------------------------------------

class CmdFriendAdd(Command):
    """
    Add a player to your friends list.

    Usage:
      friend add <player>

    You will be notified when friends come online or go offline.
    """

    key = "friendadd"
    aliases = []
    help_category = "Social"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("|yUsage: friend add <player>|n")
            return

        target_name = self.args

        if target_name.lower() == caller.key.lower():
            caller.msg("|rYou cannot add yourself as a friend.|n")
            return

        # Check target exists
        target = find_player_character(target_name)
        if not target:
            caller.msg(f"|rNo player named '{target_name}' found.|n")
            return

        friends = get_friends_list(caller)
        if target.key.lower() in [f.lower() for f in friends]:
            caller.msg(f"|y{target.key} is already on your friends list.|n")
            return

        friends.append(target.key)
        set_friends_list(caller, friends)
        caller.msg(f"|g{target.key} has been added to your friends list.|n")

        # Notify the target if they're online
        if is_player_online(target):
            target.msg(f"|g[Friends] {caller.key} has added you as a friend.|n")


class CmdFriendRemove(Command):
    """
    Remove a player from your friends list.

    Usage:
      friend remove <player>
    """

    key = "friendremove"
    aliases = []
    help_category = "Social"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("|yUsage: friend remove <player>|n")
            return

        target_name = self.args
        friends = get_friends_list(caller)

        # Find exact match (case-insensitive)
        removed = None
        new_friends = []
        for f in friends:
            if f.lower() == target_name.lower():
                removed = f
            else:
                new_friends.append(f)

        if removed is None:
            caller.msg(f"|y'{target_name}' is not on your friends list.|n")
            return

        set_friends_list(caller, new_friends)
        caller.msg(f"|y{removed} has been removed from your friends list.|n")


class CmdFriendList(Command):
    """
    Show your friends list with online status.

    Usage:
      friend list
      friends
    """

    key = "friendlist"
    aliases = ["friends"]
    help_category = "Social"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        friends = get_friends_list(caller)

        if not friends:
            caller.msg("|yYour friends list is empty.|n")
            caller.msg("|wUse |yfriend add <player>|w to add friends.|n")
            return

        lines = []
        lines.append("|w=== Your Friends ===|n")
        lines.append("")

        online_count = 0
        for friend_name in friends:
            friend_char = find_player_character(friend_name)
            if friend_char and is_player_online(friend_char):
                level = friend_char.attributes.get("level", default=1)
                location = friend_char.location.key if friend_char.location else "Unknown"
                lines.append(f"  |g●|n |w{friend_name}|n |c(Lvl {level})|n - |gOnline|n @ |c{location}|n")
                online_count += 1
            else:
                lines.append(f"  |r○|n |w{friend_name}|n - |rOffline|n")

        lines.append("")
        lines.append(f"|w{online_count}/{len(friends)} friends online.|n")
        caller.msg("\n".join(lines))


class CmdFriend(Command):
    """
    Manage your friends list.

    Usage:
      friend add <player>    - Add a friend
      friend remove <player> - Remove a friend
      friend list            - Show friends list
      friends                - Shorthand for friend list
    """

    key = "friend"
    aliases = []
    help_category = "Social"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            # Default to showing list
            cmd = CmdFriendList()
            cmd.caller = caller
            cmd.cmdstring = "friend"
            cmd.args = ""
            cmd.func()
            return

        parts = self.args.split(maxsplit=1)
        subcommand = parts[0].lower()
        sub_args = parts[1] if len(parts) > 1 else ""

        if subcommand in ("add", "a"):
            if not sub_args:
                caller.msg("|yUsage: friend add <player>|n")
                return
            cmd = CmdFriendAdd()
            cmd.caller = caller
            cmd.cmdstring = "friend add"
            cmd.args = sub_args
            cmd.func()

        elif subcommand in ("remove", "rem", "r", "delete", "del"):
            if not sub_args:
                caller.msg("|yUsage: friend remove <player>|n")
                return
            cmd = CmdFriendRemove()
            cmd.caller = caller
            cmd.cmdstring = "friend remove"
            cmd.args = sub_args
            cmd.func()

        elif subcommand in ("list", "l", "show"):
            cmd = CmdFriendList()
            cmd.caller = caller
            cmd.cmdstring = "friend list"
            cmd.args = ""
            cmd.func()

        else:
            caller.msg(
                "|yUnknown friend subcommand.|n\n"
                "|wUsage: friend add <player> | friend remove <player> | friend list|n"
            )


# ---------------------------------------------------------------------------
# IGNORE COMMANDS
# ---------------------------------------------------------------------------

class CmdIgnoreAdd(Command):
    """
    Ignore a player — block their tells, group invites, and mail.

    Usage:
      ignore add <player>

    Ignored players cannot send you private messages, group invitations,
    or mail. You will not see their messages in any channel.
    """

    key = "ignoreadd"
    aliases = []
    help_category = "Social"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("|yUsage: ignore add <player>|n")
            return

        target_name = self.args

        if target_name.lower() == caller.key.lower():
            caller.msg("|rYou cannot ignore yourself.|n")
            return

        # Check target exists
        target = find_player_character(target_name)
        if not target:
            caller.msg(f"|rNo player named '{target_name}' found.|n")
            return

        ignored = get_ignore_list(caller)
        if target.key.lower() in [i.lower() for i in ignored]:
            caller.msg(f"|yYou are already ignoring {target.key}.|n")
            return

        ignored.append(target.key)
        set_ignore_list(caller, ignored)
        caller.msg(f"|rYou are now ignoring {target.key}.|n")
        caller.msg("|wThey cannot send you tells, group invites, or mail.|n")


class CmdIgnoreRemove(Command):
    """
    Stop ignoring a player.

    Usage:
      ignore remove <player>
    """

    key = "ignoreremove"
    aliases = []
    help_category = "Social"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("|yUsage: ignore remove <player>|n")
            return

        target_name = self.args
        ignored = get_ignore_list(caller)

        removed = None
        new_ignored = []
        for i in ignored:
            if i.lower() == target_name.lower():
                removed = i
            else:
                new_ignored.append(i)

        if removed is None:
            caller.msg(f"|yYou are not ignoring '{target_name}'.|n")
            return

        set_ignore_list(caller, new_ignored)
        caller.msg(f"|gYou are no longer ignoring {removed}.|n")


class CmdIgnoreList(Command):
    """
    Show your ignore list.

    Usage:
      ignore list
      ignored
    """

    key = "ignorelist"
    aliases = ["ignored"]
    help_category = "Social"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        ignored = get_ignore_list(caller)

        if not ignored:
            caller.msg("|yYou are not ignoring anyone.|n")
            return

        lines = []
        lines.append("|r=== Ignored Players ===|n")
        lines.append("")
        for name in ignored:
            lines.append(f"  |r✗|n |w{name}|n")
        lines.append("")
        lines.append(f"|w{len(ignored)} player(s) ignored.|n")
        lines.append("|wUse |yignore remove <player>|w to stop ignoring someone.|n")
        caller.msg("\n".join(lines))


class CmdIgnore(Command):
    """
    Manage your ignore list.

    Usage:
      ignore add <player>    - Ignore a player
      ignore remove <player> - Stop ignoring a player
      ignore list            - Show ignored players
      ignored                - Shorthand for ignore list
    """

    key = "ignore"
    aliases = []
    help_category = "Social"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            cmd = CmdIgnoreList()
            cmd.caller = caller
            cmd.cmdstring = "ignore"
            cmd.args = ""
            cmd.func()
            return

        parts = self.args.split(maxsplit=1)
        subcommand = parts[0].lower()
        sub_args = parts[1] if len(parts) > 1 else ""

        if subcommand in ("add", "a"):
            if not sub_args:
                caller.msg("|yUsage: ignore add <player>|n")
                return
            cmd = CmdIgnoreAdd()
            cmd.caller = caller
            cmd.cmdstring = "ignore add"
            cmd.args = sub_args
            cmd.func()

        elif subcommand in ("remove", "rem", "r", "delete", "del"):
            if not sub_args:
                caller.msg("|yUsage: ignore remove <player>|n")
                return
            cmd = CmdIgnoreRemove()
            cmd.caller = caller
            cmd.cmdstring = "ignore remove"
            cmd.args = sub_args
            cmd.func()

        elif subcommand in ("list", "l", "show"):
            cmd = CmdIgnoreList()
            cmd.caller = caller
            cmd.cmdstring = "ignore list"
            cmd.args = ""
            cmd.func()

        else:
            caller.msg(
                "|yUnknown ignore subcommand.|n\n"
                "|wUsage: ignore add <player> | ignore remove <player> | ignore list|n"
            )