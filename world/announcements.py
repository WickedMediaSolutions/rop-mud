"""
Automated System Announcements (Realm-Wide Ticker).

A background script that periodically broadcasts helpful tips, server
restart warnings, or flavour text to every connected player.  The
interval is randomised between 30 and 60 minutes to keep things fresh.

Uses Evennia's DefaultScript for persistent scheduling.
"""

import random
from evennia.scripts.scripts import DefaultScript
from evennia.accounts.models import AccountDB

# ---------------------------------------------------------------------------
# Announcement messages  (picked at random each tick)
# ---------------------------------------------------------------------------

ANNOUNCEMENTS = [
    # Helpful tips
    "|m[Tip]|n Use |yrest|n to recover health faster when out of combat.",
    "|m[Tip]|n Join a faction for unique perks — type |yhelp factions|n to learn more.",
    "|m[Tip]|n You can check your stats at any time with |yscore|n or |y@|n.",
    "|m[Tip]|n Deposit gold in the bank to earn 2% interest per tick! Use |ybank|n.",
    "|m[Tip]|n Need help? Try |yhelp new player|n for a beginner's guide.",
    "|m[Tip]|n Use |yconsider <target>|n to gauge your odds before a fight.",
    "|m[Tip]|n Read the server rules with |yrules|n or |yhelp rules|n.",
    "|m[Tip]|n Got a bug to report? Use |ybug <description>|n — every report helps!",
    "|m[Tip]|n Found a typo or error? Use |ytypo <description>|n to alert staff.",
    "|m[Tip]|n Use |yrecall|n (level 30+) to teleport back to your faction home.",
    "|m[Tip]|n Check active quests and your progress with |yquest|n.",
    "|m[Tip]|n Group up with other adventurers! |yhelp group|n for details.",
    "|m[Tip]|n Toggle your status prompt on/off with |yprompt|n.",
    "|m[Tip]|n You can send OOC messages realm-wide on the |ygossip|n channel.",
    "|m[Tip]|n Tune into broadcast channels with |ybc <number>|n.",

    # Flavour / world-building
    "|Y[World]|n Strange lights have been spotted near the ruins of Thornwall.",
    "|Y[World]|n Merchants in Aethelgard are paying double for rare herbs this week.",
    "|Y[World]|n The Gorgoroth war drums have fallen silent... for now.",
    "|Y[World]|n A travelling sage offers free skill training in the Crossroads.",
    "|Y[World]|n Rumours speak of a hidden vault beneath the Obsidian Peaks.",

    # Server notices
    "|r[Server]|n Server restarts are announced 15 minutes in advance. Check |yhelp|n for schedule.",
    "|r[Server]|n Please log out before scheduled restarts to avoid losing progress.",
]


# ---------------------------------------------------------------------------
# Announcements Ticker Script
# ---------------------------------------------------------------------------

class AnnouncementScript(DefaultScript):
    """
    Persistent script that broadcasts an automated announcement to all
    online accounts at randomised intervals.

    Interval is re-rolled after each tick between 1800s (30 min) and
    3600s (60 min).
    """

    def at_script_creation(self):
        """Set up the script on first creation."""
        self.key = "auto_announcement_script"
        self.desc = "Periodic system-wide announcement ticker"
        self.persistent = True
        self.interval = self._random_interval()

    def at_repeat(self):
        """Called each time the ticker fires. Broadcasts a random message."""
        msg = random.choice(ANNOUNCEMENTS)

        # Format with a coloured header box
        full_message = (
            f"\n|m+-------{{{{ System Announcement }}}}-------+|n\n"
            f"\n  {msg}\n\n"
            f"|m+-------------------------------------------+|n\n"
        )

        # Send to every connected account
        for acc in AccountDB.objects.all():
            if acc.sessions.count() > 0:
                for session in acc.sessions.all():
                    session.msg(full_message)

        # Re-roll the interval for the next tick
        self.interval = self._random_interval()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _random_interval():
        """Return a random interval between 30 and 60 minutes (in seconds)."""
        return random.randint(1800, 3600)