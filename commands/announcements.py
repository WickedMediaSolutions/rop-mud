"""
Announcement Command for 'rop'

Provides:
  announce <message>  - Broadcast a server-wide announcement (admin only)
"""

from commands.command import Command


class CmdAnnounce(Command):
    """
    Broadcast a server-wide announcement to all online players.

    Usage:
      announce <message>

    Only available to administrators. The message is displayed in bright
    yellow to all currently connected players.
    """

    key = "announce"
    aliases = ["ann", "shout"]
    help_category = "Admin"
    locks = "cmd:perm(Admin)"
    auto_help = True

    def func(self):
        caller = self.caller

        if not self.args or not self.args.strip():
            caller.msg("|yUsage: announce <message>|n")
            return

        message = self.args.strip()

        from evennia.objects.objects import DefaultCharacter

        recipients = 0
        for char in DefaultCharacter.objects.all_family():
            if hasattr(char, 'sessions') and char.sessions.count() > 0:
                char.msg(f"|Y[Announcement] {message}|n")
                recipients += 1

        caller.msg(f"|gAnnouncement sent to {recipients} player(s).|n")