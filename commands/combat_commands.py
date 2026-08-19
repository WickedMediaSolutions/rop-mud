"""
Combat Commands for 'rop' — MajorMUD-Style Tick-Based Combat

Provides:
  CmdKill / CmdK   — Initiate tick-based combat with a target
  CmdFlee          — Attempt to flee from combat (chance-based)
  CmdStop          — Stop auto-attack / disengage from combat
"""

from commands.command import Command
from world.tick_combat import CombatHandler


class CmdKill(Command):
    """
    Attack a target, initiating tick-based combat.

    Usage:
      kill <target>
      k <target>

    Enters you into auto-attack combat with the specified target.
    Every combat round (approx. 2.5 seconds), you will automatically
    attempt to hit the target.  Combat continues until one of you
    dies, flees, or stops attacking.

    If you are already attacking the target, you will be notified.
    """

    key = "kill"
    aliases = ["k"]
    locks = "cmd:all()"
    help_category = "Combat"
    auto_help = True

    def parse(self):
        """Extract the target name from the argument string."""
        self.target_name = self.args.strip() if self.args else ""

    def func(self):
        caller = self.caller

        if not self.target_name:
            caller.msg("|yUsage: kill <target>|n")
            return

        # Search for target in the current room
        location = caller.location
        if not location:
            caller.msg("|rYou are nowhere; there is nothing to fight.|n")
            return

        target = caller.search(
            self.target_name,
            candidates=location.contents,
            quiet=True,
        )

        if not target or len(target) == 0:
            caller.msg(f"|rYou don't see '{self.target_name}' here.|n")
            return

        target = target[0]

        # Cannot attack self
        if target == caller:
            caller.msg("|rYou cannot attack yourself.|n")
            return

        # Check for safe zone
        if location.attributes.get("safe_zone", False):
            caller.msg("|rYou cannot fight in a safe zone.|n")
            return

        # Check PvP permissions if target is a player
        if target.has_account:
            from world.combat import _is_pvp_allowed
            allowed, reason = _is_pvp_allowed(caller, target)
            if not allowed:
                caller.msg(f"|r{reason}|n")
                return

        # Start tick-based combat
        CombatHandler.start_combat(caller, target)


class CmdFlee(Command):
    """
    Attempt to flee from combat.

    Usage:
      flee
      retreat

    Attempts to disengage from your current combat target.
    Success is based on your level, DEX, and your opponent's level.
    There is always a chance to fail — if you fail, the combat
    continues and your opponent gets to keep attacking.

    A successful flee ends combat for both you and your current
    opponent (if they are only fighting you).
    """

    key = "flee"
    aliases = ["retreat"]
    locks = "cmd:all()"
    help_category = "Combat"
    auto_help = True

    def func(self):
        caller = self.caller

        if not CombatHandler.is_in_combat(caller):
            caller.msg("|yYou are not in combat.|n")
            return

        CombatHandler.attempt_flee(caller)


class CmdCombatBrief(Command):
    """
    Toggle condensed combat output (battle spam control).

    Usage:
      combatbrief
      battle-spam

    When enabled, combat messages are condensed to a single line per
    attack (damage numbers only, no flavor text).  This is useful for
    reducing spam during large battles or long grinding sessions.
    """

    key = "combatbrief"
    aliases = ["battle-spam", "combatlog"]
    locks = "cmd:all()"
    help_category = "Combat"
    auto_help = True

    def func(self):
        caller = self.caller
        current = caller.attributes.get("combat_brief", False)
        new_value = not current
        caller.attributes.add("combat_brief", new_value)
        if new_value:
            caller.msg("|gCombat output is now CONDENSED (damage numbers only).|n")
        else:
            caller.msg("|yCombat output is now VERBOSE (full flavor text).|n")


class CmdStop(Command):
    """
    Stop attacking and disengage from combat.

    Usage:
      stop
      autoattack off

    Immediately ends your current combat session.  You will stop
    auto-attacking your target and leave combat.  Your opponent
    may continue fighting you if they still have you targeted.

    This is a guaranteed disengage (unlike flee, which can fail).
    """

    key = "stop"
    aliases = ["autoattack"]
    locks = "cmd:all()"
    help_category = "Combat"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip().lower()

    def func(self):
        caller = self.caller

        # Support "autoattack off" syntax
        if self.args == "off":
            if not CombatHandler.is_in_combat(caller):
                caller.msg("|yYou are not in combat.|n")
                return
            CombatHandler.stop_combat(caller)
            caller.msg("|yYou stop attacking and disengage from combat.|n")
            return

        # "stop" with no arguments (or unrecognized arguments)
        if not self.args:
            if not CombatHandler.is_in_combat(caller):
                caller.msg("|yYou are not in combat.|n")
                return
            CombatHandler.stop_combat(caller)
            caller.msg("|yYou stop attacking and disengage from combat.|n")
            return

        # If they typed "autoattack on" or something else
        if self.args.lower() == "on":
            caller.msg("|yAuto-attack is always enabled during combat. Use |wkill <target>|y to start.|n")
        else:
            caller.msg("|yUsage: stop  or  autoattack off|n")