"""
Moderation Commands for 'rop' — Phase 10

Provides:
  - CmdBan       — @ban <player> [reason] [duration_minutes]
  - CmdUnban     — @unban <player>
  - CmdMute      — @mute <player> [duration_minutes]
  - CmdUnmute    — @unmute <player>
  - CmdBanList   — @banlist
  - CmdKick      — @kick <player> [reason]

All commands are Admin-gated. Ban/mute state is persisted via attributes
on the target Account object and enforced at connection/login time.
"""

from __future__ import annotations

import time
from typing import Optional

from commands.command import Command


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _get_account(target) -> Optional[object]:
    """Resolve a target string to an Account object."""
    from evennia.accounts.models import AccountDB

    if hasattr(target, "account"):
        return target.account
    if hasattr(target, "__dbclass__") and target.__dbclass__.__name__ == "AccountDB":
        return target

    # Try dbref
    if target.startswith("#"):
        try:
            dbref = int(target[1:])
            return AccountDB.objects.filter(id=dbref).first()
        except (ValueError, TypeError):
            pass

    # Try username
    return AccountDB.objects.filter(username__iexact=target).first()


def is_banned(account) -> bool:
    """Check if an account is currently banned."""
    if not account:
        return False
    ban_expires = account.attributes.get("ban_expires", default=0)
    if ban_expires == 0:
        return False
    if ban_expires == -1:  # permanent
        return True
    if time.time() < ban_expires:
        return True
    # Ban expired — clean up
    account.attributes.add("ban_expires", 0)
    account.attributes.add("ban_reason", "")
    return False


def is_muted(account) -> bool:
    """Check if an account is currently muted."""
    if not account:
        return False
    mute_expires = account.attributes.get("mute_expires", default=0)
    if mute_expires == 0:
        return False
    if mute_expires == -1:  # permanent
        return True
    if time.time() < mute_expires:
        return True
    # Mute expired — clean up
    account.attributes.add("mute_expires", 0)
    return False


def get_ban_info(account) -> dict:
    """Get ban details for an account."""
    if not account:
        return {"banned": False}
    ban_expires = account.attributes.get("ban_expires", default=0)
    if ban_expires == 0:
        return {"banned": False}
    if ban_expires == -1:
        return {
            "banned": True,
            "permanent": True,
            "reason": account.attributes.get("ban_reason", default=""),
            "banned_by": account.attributes.get("banned_by", default=""),
            "banned_at": account.attributes.get("banned_at", default=0),
        }
    remaining = ban_expires - time.time()
    if remaining <= 0:
        return {"banned": False}
    return {
        "banned": True,
        "permanent": False,
        "expires_in": int(remaining),
        "expires_at": ban_expires,
        "reason": account.attributes.get("ban_reason", default=""),
        "banned_by": account.attributes.get("banned_by", default=""),
        "banned_at": account.attributes.get("banned_at", default=0),
    }


def get_mute_info(account) -> dict:
    """Get mute details for an account."""
    if not account:
        return {"muted": False}
    mute_expires = account.attributes.get("mute_expires", default=0)
    if mute_expires == 0:
        return {"muted": False}
    if mute_expires == -1:
        return {
            "muted": True,
            "permanent": True,
            "muted_by": account.attributes.get("muted_by", default=""),
            "muted_at": account.attributes.get("muted_at", default=0),
        }
    remaining = mute_expires - time.time()
    if remaining <= 0:
        return {"muted": False}
    return {
        "muted": True,
        "permanent": False,
        "expires_in": int(remaining),
        "expires_at": mute_expires,
        "muted_by": account.attributes.get("muted_by", default=""),
        "muted_at": account.attributes.get("muted_at", default=0),
    }


def get_all_bans() -> list:
    """Return a list of all currently banned accounts."""
    from evennia.accounts.models import AccountDB

    banned = []
    for acct in AccountDB.objects.all():
        if is_banned(acct):
            info = get_ban_info(acct)
            info["username"] = acct.username
            info["dbref"] = f"#{acct.id}"
            banned.append(info)
    return banned


def get_all_mutes() -> list:
    """Return a list of all currently muted accounts."""
    from evennia.accounts.models import AccountDB

    muted = []
    for acct in AccountDB.objects.all():
        if is_muted(acct):
            info = get_mute_info(acct)
            info["username"] = acct.username
            info["dbref"] = f"#{acct.id}"
            muted.append(info)
    return muted


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


class CmdBan(Command):
    """
    Ban a player from the game.

    Usage:
      @ban <player> [reason] [duration_minutes]
      @ban <player> [reason] permanent

    Examples:
      @ban troublemaker Spamming chat 60
      @ban griefer Harassment permanent

    Banned players are disconnected immediately and cannot reconnect
    until the ban expires or is lifted. Use -1 or "permanent" for
    a permanent ban.

    Available to administrators only.
    """

    key = "@ban"
    aliases = ["ban"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"
    auto_help = True

    def parse(self):
        self.args_raw = (self.args or "").strip()

    def func(self):
        caller = self.caller
        args = self.args_raw

        if not args:
            caller.msg("|yUsage: @ban <player> [reason] [duration_minutes|permanent]|n")
            return

        parts = args.split()
        target_name = parts[0]

        # Parse duration and reason
        duration = 60  # default 1 hour
        permanent = False
        reason = "No reason given"

        remaining = parts[1:]
        if remaining:
            # Check if last part is a duration or "permanent"
            last = remaining[-1].lower()
            if last == "permanent" or last == "perm":
                permanent = True
                reason_parts = remaining[:-1]
            else:
                try:
                    duration = int(last)
                    if duration <= 0:
                        permanent = True
                    reason_parts = remaining[:-1]
                except ValueError:
                    reason_parts = remaining

            if reason_parts:
                reason = " ".join(reason_parts)

        # Resolve target
        account = _get_account(target_name)
        if not account:
            caller.msg(f"|rCannot find player '{target_name}'.|n")
            return

        # Check if already banned
        if is_banned(account):
            caller.msg(f"|y{account.username} is already banned.|n")
            return

        # Apply ban
        now = time.time()
        if permanent:
            ban_expires = -1
            duration_str = "permanently"
        else:
            ban_expires = now + (duration * 60)
            if duration >= 1440:
                days = duration // 1440
                hours = (duration % 1440) // 60
                mins = duration % 60
                duration_str = f"for {days}d {hours}h {mins}m"
            elif duration >= 60:
                hours = duration // 60
                mins = duration % 60
                duration_str = f"for {hours}h {mins}m"
            else:
                duration_str = f"for {duration}m"

        account.attributes.add("ban_expires", ban_expires)
        account.attributes.add("ban_reason", reason)
        account.attributes.add("banned_by", caller.key)
        account.attributes.add("banned_at", now)

        # Disconnect all sessions
        if hasattr(account, "sessions"):
            for session in list(account.sessions.all()):
                session.msg(
                    f"|rYou have been banned {duration_str}: {reason}|n"
                )
                session.disconnect()

        # Announce
        caller.msg(
            f"|gBanned {account.username} {duration_str}. Reason: {reason}|n"
        )

        # Log to admin audit trail
        try:
            from world.admin_log import log_admin_action
            log_admin_action(
                admin=caller,
                action="ban",
                target=account.username,
                details=f"duration={duration_str} reason={reason}",
            )
        except Exception:
            pass

        # Notify builder channel
        try:
            from evennia import ChannelDB
            chan = ChannelDB.objects.filter(db_key__iexact="builder").first()
            if chan:
                chan.msg(
                    f"[Admin] {caller.key} banned {account.username} "
                    f"{duration_str}: {reason}"
                )
        except Exception:
            pass


class CmdUnban(Command):
    """
    Remove a ban from a player.

    Usage:
      @unban <player>

    Available to administrators only.
    """

    key = "@unban"
    aliases = ["unban"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"
    auto_help = True

    def parse(self):
        self.target_name = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.target_name:
            caller.msg("|yUsage: @unban <player>|n")
            return

        account = _get_account(self.target_name)
        if not account:
            caller.msg(f"|rCannot find player '{self.target_name}'.|n")
            return

        if not is_banned(account):
            caller.msg(f"|y{account.username} is not currently banned.|n")
            return

        # Remove ban
        account.attributes.add("ban_expires", 0)
        account.attributes.add("ban_reason", "")

        caller.msg(f"|gUnbanned {account.username}.|n")

        # Log
        try:
            from world.admin_log import log_admin_action
            log_admin_action(
                admin=caller,
                action="unban",
                target=account.username,
                details="",
            )
        except Exception:
            pass


class CmdMute(Command):
    """
    Mute a player — prevent them from using public channels.

    Usage:
      @mute <player> [duration_minutes]
      @mute <player> permanent

    Muted players cannot use gossip, broadcast, clan chat, or other
    public communication channels. They can still use tells and
    in-room say.

    Available to administrators only.
    """

    key = "@mute"
    aliases = ["mute"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"
    auto_help = True

    def parse(self):
        self.args_raw = (self.args or "").strip()

    def func(self):
        caller = self.caller
        args = self.args_raw

        if not args:
            caller.msg("|yUsage: @mute <player> [duration_minutes|permanent]|n")
            return

        parts = args.split()
        target_name = parts[0]

        duration = 30  # default 30 minutes
        permanent = False

        if len(parts) > 1:
            last = parts[1].lower()
            if last in ("permanent", "perm"):
                permanent = True
            else:
                try:
                    duration = int(last)
                    if duration <= 0:
                        permanent = True
                except ValueError:
                    pass

        account = _get_account(target_name)
        if not account:
            caller.msg(f"|rCannot find player '{target_name}'.|n")
            return

        if is_muted(account):
            caller.msg(f"|y{account.username} is already muted.|n")
            return

        now = time.time()
        if permanent:
            mute_expires = -1
            duration_str = "permanently"
        else:
            mute_expires = now + (duration * 60)
            if duration >= 60:
                hours = duration // 60
                mins = duration % 60
                duration_str = f"for {hours}h {mins}m"
            else:
                duration_str = f"for {duration}m"

        account.attributes.add("mute_expires", mute_expires)
        account.attributes.add("muted_by", caller.key)
        account.attributes.add("muted_at", now)

        # Notify the player if online
        if hasattr(account, "sessions"):
            for session in account.sessions.all():
                session.msg(
                    f"|rYou have been muted {duration_str} by an administrator.|n"
                )

        caller.msg(f"|gMuted {account.username} {duration_str}.|n")

        # Log
        try:
            from world.admin_log import log_admin_action
            log_admin_action(
                admin=caller,
                action="mute",
                target=account.username,
                details=f"duration={duration_str}",
            )
        except Exception:
            pass


class CmdUnmute(Command):
    """
    Remove a mute from a player.

    Usage:
      @unmute <player>

    Available to administrators only.
    """

    key = "@unmute"
    aliases = ["unmute"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"
    auto_help = True

    def parse(self):
        self.target_name = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.target_name:
            caller.msg("|yUsage: @unmute <player>|n")
            return

        account = _get_account(self.target_name)
        if not account:
            caller.msg(f"|rCannot find player '{self.target_name}'.|n")
            return

        if not is_muted(account):
            caller.msg(f"|y{account.username} is not currently muted.|n")
            return

        account.attributes.add("mute_expires", 0)

        caller.msg(f"|gUnmuted {account.username}.|n")

        # Log
        try:
            from world.admin_log import log_admin_action
            log_admin_action(
                admin=caller,
                action="unmute",
                target=account.username,
                details="",
            )
        except Exception:
            pass


class CmdBanList(Command):
    """
    List all currently banned and muted players.

    Usage:
      @banlist

    Available to administrators only.
    """

    key = "@banlist"
    aliases = ["banlist", "@modlist"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"
    auto_help = True

    def func(self):
        caller = self.caller

        bans = get_all_bans()
        mutes = get_all_mutes()

        lines = []
        lines.append("|Y" + "=" * 65 + "|n")
        lines.append("|c|h              MODERATION STATUS REPORT|n")
        lines.append("|Y" + "=" * 65 + "|n")

        # Bans section
        lines.append("")
        lines.append("|w|h  BANNED PLAYERS|n")
        lines.append("|w  " + "-" * 40 + "|n")
        if not bans:
            lines.append("  |gNo players are currently banned.|n")
        else:
            for b in bans:
                username = b.get("username", "Unknown")
                reason = b.get("reason", "")
                banned_by = b.get("banned_by", "")
                if b.get("permanent"):
                    expires = "|rPERMANENT|n"
                else:
                    secs = b.get("expires_in", 0)
                    if secs >= 3600:
                        expires = f"{secs // 3600}h {(secs % 3600) // 60}m remaining"
                    elif secs >= 60:
                        expires = f"{secs // 60}m remaining"
                    else:
                        expires = f"{secs}s remaining"
                lines.append(
                    f"  |r{username}|n — {reason} (by {banned_by}) [{expires}]"
                )

        # Mutes section
        lines.append("")
        lines.append("|w|h  MUTED PLAYERS|n")
        lines.append("|w  " + "-" * 40 + "|n")
        if not mutes:
            lines.append("  |gNo players are currently muted.|n")
        else:
            for m in mutes:
                username = m.get("username", "Unknown")
                muted_by = m.get("muted_by", "")
                if m.get("permanent"):
                    expires = "|rPERMANENT|n"
                else:
                    secs = m.get("expires_in", 0)
                    if secs >= 3600:
                        expires = f"{secs // 3600}h {(secs % 3600) // 60}m remaining"
                    elif secs >= 60:
                        expires = f"{secs // 60}m remaining"
                    else:
                        expires = f"{secs}s remaining"
                lines.append(
                    f"  |y{username}|n — muted by {muted_by} [{expires}]"
                )

        lines.append("")
        lines.append("|Y" + "=" * 65 + "|n")

        caller.msg("\n".join(lines))


class CmdKick(Command):
    """
    Kick a player from the game.

    Usage:
      @kick <player> [reason]

    Disconnects the player immediately. They can reconnect unless
    also banned.

    Available to administrators only.
    """

    key = "@kick"
    aliases = ["kick"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"
    auto_help = True

    def parse(self):
        self.args_raw = (self.args or "").strip()

    def func(self):
        caller = self.caller
        args = self.args_raw

        if not args:
            caller.msg("|yUsage: @kick <player> [reason]|n")
            return

        parts = args.split()
        target_name = parts[0]
        reason = " ".join(parts[1:]) if len(parts) > 1 else "No reason given"

        account = _get_account(target_name)
        if not account:
            caller.msg(f"|rCannot find player '{target_name}'.|n")
            return

        # Disconnect all sessions
        kicked = False
        if hasattr(account, "sessions"):
            sessions = list(account.sessions.all())
            for session in sessions:
                session.msg(
                    f"|rYou have been kicked by an administrator: {reason}|n"
                )
                session.disconnect()
            kicked = len(sessions) > 0

        if kicked:
            caller.msg(f"|gKicked {account.username}. Reason: {reason}|n")
        else:
            caller.msg(f"|y{account.username} is not currently online.|n")

        # Log
        try:
            from world.admin_log import log_admin_action
            log_admin_action(
                admin=caller,
                action="kick",
                target=account.username,
                details=f"reason={reason}",
            )
        except Exception:
            pass

        # Notify builder channel
        try:
            from evennia import ChannelDB
            chan = ChannelDB.objects.filter(db_key__iexact="builder").first()
            if chan:
                chan.msg(
                    f"[Admin] {caller.key} kicked {account.username}: {reason}"
                )
        except Exception:
            pass