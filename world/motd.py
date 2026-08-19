"""
Message of the Day (MOTD) system.

Renders the colourful welcome banner players see when logging in.
The MOTD includes:
  - A central welcome header
  - Current game news & tips
  - A brief rules reminder
"""

import random
from datetime import datetime


# ---------------------------------------------------------------------------
# MOTD Templates  (one is chosen at random each login for variety)
# ---------------------------------------------------------------------------

MOTD_TEMPLATES = [
    # Template 0 — standard welcome
    """
|y+=============================================================+
|y|                                                             |
|y|   |c|hWelcome back to Realms of Patience, |w{name}|c|h!|n
|y|                                                             |
|y+=============================================================+

|wCurrent Server Time: |c{time}|n

|g>> |wPlayer Tip:|n {tip}

|wType |yhelp|w for a list of commands, or |yhelp new player|w to get started.
|wType |yrules|w to review the server guidelines.

|y=================================================================|n
""",

    # Template 1 — shorter, more concise
    """
|m+-------------------------------------------------------------+
|m|                                                             |
|m|     |cWelcome, |w{name}|c! The realm awaits your return.|n
|m|                                                             |
|m+-------------------------------------------------------------+

|wServer Time: |c{time}|n

|g>> |wTip:|n {tip}

|wCommands: |yhelp rules|w | |ywho|w | |yinv|w | |yeq|w | |yscore|n

|m---------------------------------------------------------------|n
""",

    # Template 2 — lore-themed
    """
|r+=============================================================+
|r|                                                             |
|r|   |YThe winds of fate stir once more...|n
|r|   |c|h{name}|c steps into the light.|n
|r|                                                             |
|r+=============================================================+

|wServer Time: |c{time}|n

|g>> |wAdventurer's Wisdom:|n {tip}

|wNeed assistance? |yhelp|w and |yhelp rules|w are always available.
|wSee who's online with |ywho|w.
|wView your stats with |yscore|w.

|r=================================================================|n
""",
]


# ---------------------------------------------------------------------------
# Rotating Tips  (shown randomly in the MOTD)
# ---------------------------------------------------------------------------

MOTD_TIPS = [
    "Type |yhelp new player|w for a beginner's guide to the realm.",
    "Use |yrecall|w (level 30+) to instantly return to your faction home.",
    "You can toggle the status prompt with |yprompt|w.",
    "Meditate to recover mana faster — use |ymeditate|w.",
    "Rest to recover health and stamina faster — use |yrest|w.",
    "Group up with other players! Type |yhelp group|w to learn how.",
    "Check your net worth at any time with |yworth|w.",
    "Report bugs with |ybug <description>|w. Every report helps!",
    "Found a typo? Use |ytypo <description>|w to let staff know.",
    "Type |ywho|w to see who else is roaming the realm.",
    "Deposit gold in the bank to earn interest — use |ybank|w.",
    "You can tune into broadcast channels with |ybc <number>|w.",
    "Check active quests with |yquest|w.",
    "Join a faction for exclusive perks — ask in |ygossip|w!",
    "Read the server rules with |yrules|w or |yhelp rules|w.",
    "Your |yalignment|w determines which cities welcome you.",
    "Use |yconsider <target>|w before picking a fight.",
    "The |ygossip|w channel is realm-wide OOC chat.",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_random_tip():
    """Return a random player tip string."""
    return random.choice(MOTD_TIPS)


def render_motd(character):
    """
    Build and return the complete MOTD string for the given character.

    Args:
        character: The Character instance that just logged in.

    Returns:
        str: A fully-coloured MOTD block ready for display.
    """
    name = character.key if character else "Adventurer"
    now = datetime.utcnow()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    tip = get_random_tip()

    template = random.choice(MOTD_TEMPLATES)
    return template.format(name=name, time=time_str, tip=tip)