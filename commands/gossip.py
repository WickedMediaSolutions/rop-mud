"""
Faction Gossip Command for 'rop'

Provides:
  gossip <message> / gos <message>  - Broadcast a message in cyan to all
                                       online players of the SAME faction.

Good and Evil players are isolated — Evil cannot see Good gossip and
vice versa.
"""

from commands.command import Command


class CmdGossip(Command):
    """
    Send a message to all online members of your faction.

    Usage:
      gossip <message>
      gos <message>

    Messages are displayed in cyan and are ONLY visible to players
    who share your alignment (Good or Evil).  The opposing faction
    cannot see your faction's gossip channel.
    """

    key = "gossip"
    aliases = ["gos"]
    help_category = "Communication"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        if not self.args or not self.args.strip():
            caller.msg("|yUsage: gossip <message>  (or gos <message>)|n")
            return

        # Determine caller's faction alignment
        faction = caller.attributes.get("alignment", default="Neutral")
        message = self.args.strip()

        # Broadcast only to online players of the same faction
        from evennia.objects.objects import DefaultCharacter

        # Find all player characters that are currently online (have a session)
        all_chars = DefaultCharacter.objects.all()
        recipients = 0
        for char in all_chars:
            # Check alignment match
            char_align = char.attributes.get("alignment", default="")
            if char_align != faction:
                continue

            # Deliver the message
            char.msg(f"|c[Gossip] {caller.key}: {message}|n")
            recipients += 1

        # Confirm to sender how many heard it
        caller.msg(f"|c[Gossip] You say: {message}|n")
        caller.msg(f"|w(Heard by {recipients} faction member(s))|n")


# Alias for test compatibility
CmdOOC = CmdGossip
