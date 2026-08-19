"""
PvP Toggle Command

Allows players to enable or disable PvP for same-faction combat.
Opposing-faction PvP is always on (outside safe zones).
"""

from commands.command import Command
from world.combat import is_safe_zone  # noqa: F401 - re-export for test compatibility


class CmdPvp(Command):
    """
    Toggle PvP mode for same-faction player combat.

    Usage:
      pvp on     - Enable PvP. You may be attacked by (and attack) same-faction players.
      pvp off    - Disable PvP. Same-faction players cannot attack you, and you
                   cannot attack them.
      pvp        - Show current PvP status.

    Note: PvP against opposing factions is always enabled outside of safe zones.
          Combat is always forbidden in safe zones (towns, shops, faction havens).
    """

    key = "pvp"
    aliases = []
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        if not args:
            # Show current PvP status
            enabled = caller.db.pvp_enabled
            status = "|gON|n" if enabled else "|rOFF|n"
            caller.msg(f"PvP (same-faction) is currently: {status}")
            caller.msg("Use |wpvp on|n or |wpvp off|n to change it.")
            return

        if args == "on":
            caller.db.pvp_enabled = True
            caller.msg("|gPvP enabled.|n Same-faction players may now attack you (and vice versa).")
        elif args == "off":
            caller.db.pvp_enabled = False
            caller.msg("|rPvP disabled.|n Same-faction players cannot attack you.")
        else:
            caller.msg("Usage: |wpvp on|n, |wpvp off|n, or just |wpvp|n to check status.")