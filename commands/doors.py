"""
Door Commands for 'rop'

Phase 1.2 — Provides open, close, lock, and unlock commands for exits
that act as doors.  An exit must have `closed` / `locked` attributes
(managed by the Exit typeclass) for these commands to have any effect.
"""

from commands.command import Command


class CmdOpen(Command):
    """
    Open a closed door or exit.

    Usage:
      open <direction>
      open north
      open door

    Opens a closed exit in the specified direction.  If the exit is
    locked you must unlock it first.  If the exit is already open
    nothing happens.
    """

    key = "open"
    aliases = []
    help_category = "Movement"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.target = self.args.strip().lower() if self.args else ""

    def func(self):
        caller = self.caller
        location = caller.location

        if not self.target:
            caller.msg("|yUsage: open <direction>  (e.g. open north, open door)|n")
            return

        if not location:
            caller.msg("|rYou have no location — you cannot open anything.|n")
            return

        exit_obj = self._find_exit(location, self.target)
        if not exit_obj:
            caller.msg(f"|rYou see no '{self.target}' here to open.|n")
            return

        if not hasattr(exit_obj, "is_closed"):
            caller.msg(f"|r{exit_obj.key} is not a door.|n")
            return

        if not exit_obj.is_closed():
            caller.msg(f"|y{exit_obj.key} is already open.|n")
            return

        if exit_obj.is_locked():
            caller.msg(f"|r{exit_obj.key} is locked. You must unlock it first.|n")
            return

        exit_obj.db.closed = False
        caller.msg(f"|gYou open {exit_obj.key}.|n")
        location.msg_contents(
            f"|g{caller.key} opens {exit_obj.key}.|n", exclude=caller
        )

    @staticmethod
    def _find_exit(location, target):
        """Find an exit in *location* matching *target* by key or alias."""
        from typeclasses.exits import normalize_direction, DIRECTION_ALIASES

        canonical = normalize_direction(target)
        search_keys = {canonical}
        search_keys.update(DIRECTION_ALIASES.get(canonical, []))

        for ex in location.exits:
            if ex.key.lower() in search_keys:
                return ex
            if any(alias in search_keys for alias in ex.aliases.all()):
                return ex

        # Fallback: match by key substring (e.g. "door")
        for ex in location.exits:
            if target in ex.key.lower():
                return ex

        return None


class CmdClose(Command):
    """
    Close an open door or exit.

    Usage:
      close <direction>
      close north
      close door

    Closes an open exit in the specified direction.  If the exit is
    already closed nothing happens.
    """

    key = "close"
    aliases = ["shut"]
    help_category = "Movement"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.target = self.args.strip().lower() if self.args else ""

    def func(self):
        caller = self.caller
        location = caller.location

        if not self.target:
            caller.msg("|yUsage: close <direction>  (e.g. close north, close door)|n")
            return

        if not location:
            caller.msg("|rYou have no location — you cannot close anything.|n")
            return

        exit_obj = CmdOpen._find_exit(location, self.target)
        if not exit_obj:
            caller.msg(f"|rYou see no '{self.target}' here to close.|n")
            return

        if not hasattr(exit_obj, "is_closed"):
            caller.msg(f"|r{exit_obj.key} is not a door.|n")
            return

        if exit_obj.is_closed():
            caller.msg(f"|y{exit_obj.key} is already closed.|n")
            return

        exit_obj.db.closed = True
        caller.msg(f"|gYou close {exit_obj.key}.|n")
        location.msg_contents(
            f"|g{caller.key} closes {exit_obj.key}.|n", exclude=caller
        )


class CmdLock(Command):
    """
    Lock a closed door or exit.

    Usage:
      lock <direction>
      lock north
      lock door

    Locks a closed exit in the specified direction.  The exit must be
    closed before it can be locked.  If the exit is already locked
    nothing happens.
    """

    key = "lock"
    aliases = []
    help_category = "Movement"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.target = self.args.strip().lower() if self.args else ""

    def func(self):
        caller = self.caller
        location = caller.location

        if not self.target:
            caller.msg("|yUsage: lock <direction>  (e.g. lock north, lock door)|n")
            return

        if not location:
            caller.msg("|rYou have no location — you cannot lock anything.|n")
            return

        exit_obj = CmdOpen._find_exit(location, self.target)
        if not exit_obj:
            caller.msg(f"|rYou see no '{self.target}' here to lock.|n")
            return

        if not hasattr(exit_obj, "is_locked"):
            caller.msg(f"|r{exit_obj.key} is not a door.|n")
            return

        if exit_obj.is_locked():
            caller.msg(f"|y{exit_obj.key} is already locked.|n")
            return

        if not exit_obj.is_closed():
            caller.msg(f"|rYou must close {exit_obj.key} before you can lock it.|n")
            return

        exit_obj.db.locked = True
        caller.msg(f"|gYou lock {exit_obj.key}.|n")
        location.msg_contents(
            f"|g{caller.key} locks {exit_obj.key}.|n", exclude=caller
        )


class CmdUnlock(Command):
    """
    Unlock a locked door or exit.

    Usage:
      unlock <direction>
      unlock north
      unlock door

    Unlocks a locked exit in the specified direction.  The exit remains
    closed — use |yopen|n afterwards to pass through.  If the exit is
    already unlocked nothing happens.
    """

    key = "unlock"
    aliases = []
    help_category = "Movement"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.target = self.args.strip().lower() if self.args else ""

    def func(self):
        caller = self.caller
        location = caller.location

        if not self.target:
            caller.msg("|yUsage: unlock <direction>  (e.g. unlock north, unlock door)|n")
            return

        if not location:
            caller.msg("|rYou have no location — you cannot unlock anything.|n")
            return

        exit_obj = CmdOpen._find_exit(location, self.target)
        if not exit_obj:
            caller.msg(f"|rYou see no '{self.target}' here to unlock.|n")
            return

        if not hasattr(exit_obj, "is_locked"):
            caller.msg(f"|r{exit_obj.key} is not a door.|n")
            return

        if not exit_obj.is_locked():
            caller.msg(f"|y{exit_obj.key} is already unlocked.|n")
            return

        exit_obj.db.locked = False
        caller.msg(f"|gYou unlock {exit_obj.key}.|n")
        location.msg_contents(
            f"|g{caller.key} unlocks {exit_obj.key}.|n", exclude=caller
        )