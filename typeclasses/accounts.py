"""
Account Typeclass

The Account represents the out-of-character (OOC) user logged into the game.
"""

from evennia.accounts.accounts import DefaultAccount, DefaultGuest
from evennia.utils.evmenu import EvMenu


class Account(DefaultAccount):
    """
    Custom Account class handling post-login routing and character selection.
    """

    def at_pre_login(self, session=None, **kwargs):
        """
        Called just before the account is logged in.

        Enforces the ban system: banned accounts are denied login and
        their session is disconnected with the ban reason.
        """
        from commands.moderation import is_banned, get_ban_info

        if is_banned(self):
            info = get_ban_info(self)
            reason = info.get("reason", "No reason given")
            if info.get("permanent"):
                duration = "permanently"
            else:
                secs = info.get("expires_in", 0)
                if secs >= 3600:
                    duration = f"for {secs // 3600}h {(secs % 3600) // 60}m"
                elif secs >= 60:
                    duration = f"for {secs // 60}m"
                else:
                    duration = f"for {secs}s"
            self.msg(f"|rYou are banned {duration}: {reason}|n")
            if session:
                try:
                    session.disconnect()
                except Exception:
                    pass
            return

        super().at_pre_login(session=session, **kwargs)

    def at_post_login(self, session=None, **kwargs):
        """
        Called right after logging in.
        """
        from commands.moderation import is_banned, is_muted, get_ban_info

        # Double-check ban in case at_pre_login was bypassed
        if is_banned(self):
            info = get_ban_info(self)
            reason = info.get("reason", "No reason given")
            self.msg(f"|rYou are banned: {reason}|n")
            if session:
                try:
                    session.disconnect()
                except Exception:
                    pass
            return

        # Call parent — may fail if AUTO_PUPPET_ON_LOGIN is False and
        # _last_puppet doesn't exist.  We handle puppet ourselves below.
        try:
            super().at_post_login(session=session, **kwargs)
        except Exception:
            pass

        # Notify if muted
        if is_muted(self):
            self.msg(
                "|yYou are currently muted and cannot use public channels.|n"
            )

        # If account has no characters, launch character creation
        characters = list(self.characters.all())
        if not characters:
            self.msg("|YWelcome to Rites of Passage!  Creating your first character...|n")
            from world.chargen import start_chargen
            start_chargen(self)
            return

        # Existing account -> Puppet active/last character
        try:
            last_char = self.db._last_puppet
        except Exception:
            last_char = None

        if last_char and last_char in characters:
            target_char = last_char
        else:
            target_char = characters[0]

        # Avoid re-puppeting if already attached to this character
        if session and getattr(session, 'puppet', None) != target_char:
            self.msg(f"|gLogging in as {target_char.key}...|n")
            try:
                self.puppet_object(session, target_char)
            except Exception as err:
                self.msg(f"|rError logging in: {err}|n")
                self.msg("|yType |wlook|y to see your surroundings.|n")
        else:
            # Already puppeted — send a welcome message so the screen
            # isn't blank.
            self.msg(f"|gWelcome back, {target_char.key}!|n")
            self.msg("|wType |clook|w to see your surroundings.|n")


class Guest(DefaultGuest):
    """
    This class is used for guest logins.
    """

    pass