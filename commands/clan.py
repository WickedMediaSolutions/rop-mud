"""
Clan System for 'rop'

Provides:
  clan join <name> / join <clan_name>  - Join a clan matching your faction
  clan list                            - View all Good/Evil clans
  clan leave                           - Leave your current clan
  clantalk <msg> / ct <msg>           - Private clan communication

8 Clans: 4 Good, 4 Evil with custom lore and realm-wide join broadcasts.
"""

from commands.command import Command
from evennia import search_object


# ---------------------------------------------------------------------------
# CLAN DEFINITIONS
# ---------------------------------------------------------------------------

CLANS = {
    # Evil Clans
    "The House of Zod": {
        "alignment": "Evil",
        "description": (
            "The supreme dark power in the realm. The House of Zod commands "
            "legions of fallen warriors, dark sorcerers, and infernal beasts. "
            "Their citadel pierces the blackened sky of Gorgoroth, a monument "
            "to conquest and domination. Only the most ruthless may wear the "
            "mark of Zod."
        ),
        "join_message": (
            "The ground trembles as {name} joins The House of Zod! "
            "The sky darkens and a fell wind howls through the realm. "
            "Another soul has pledged fealty to the Dark Lord!"
        ),
    },
    "The Shadow Council": {
        "alignment": "Evil",
        "description": (
            "A clandestine cabal of dark mages, necromancers, and warlocks "
            "who pull the strings of power from the shadows. The Shadow Council "
            "hoards forbidden knowledge and bends the very fabric of reality "
            "to their will. Their sigil is a shrouded eye wreathed in black flame."
        ),
        "join_message": (
            "Whispers echo through the darkness as {name} joins The Shadow Council! "
            "Ancient tomes rustle and candles flicker — the Council's ranks swell "
            "with another master of the forbidden arts."
        ),
    },
    "The Crimson Legion": {
        "alignment": "Evil",
        "description": (
            "An unstoppable war machine forged in blood and iron. The Crimson Legion "
            "marches beneath a banner of dripping red, their berserkers and "
            "blood-mages leaving naught but ash and ruin in their wake. "
            "Strength is their only law; slaughter, their only tribute."
        ),
        "join_message": (
            "War drums thunder across the realm as {name} joins The Crimson Legion! "
            "The scent of blood and iron fills the air — another warrior has sworn "
            "the oath of eternal carnage!"
        ),
    },
    "The Black Hand": {
        "alignment": "Evil",
        "description": (
            "An elite brotherhood of assassins, spies, and shadowblades whose "
            "influence stretches into every throne room and dark alley of the realm. "
            "The Black Hand trades in secrets and death, their silent blades carving "
            "destinies from the darkness. None see their mark — until it is too late."
        ),
        "join_message": (
            "A cold shiver runs down the spines of kings as {name} joins The Black Hand! "
            "Shadows deepen and daggers gleam in the dark — the Brotherhood of the Blade "
            "claims another silent killer."
        ),
    },
    # Good Clans
    "The Order of the Sun": {
        "alignment": "Good",
        "description": (
            "The most revered order of paladins, clerics, and holy knights in Aethelgard. "
            "The Order of the Sun stands as a beacon of hope against the darkness, their "
            "radiant blades and blessed shields defending the innocent. Their crest is a "
            "golden sunburst upon a field of pure white."
        ),
        "join_message": (
            "A brilliant golden light floods the realm as {name} joins The Order of the Sun! "
            "Trumpets sound from the heavens and the faithful rejoice — a new champion of "
            "the Light has risen!"
        ),
    },
    "The Verdant Circle": {
        "alignment": "Good",
        "description": (
            "Guardians of the ancient wilds, the Verdant Circle is a fellowship of druids, "
            "rangers, and nature-wardens who protect the sacred groves and primeval forests "
            "of the realm. Their power flows from the living earth itself, and their sigil "
            "is an oak tree encircled by emerald vines."
        ),
        "join_message": (
            "The forests whisper and ancient trees creak with joy as {name} joins "
            "The Verdant Circle! Flowers bloom in impossible places and the wild places "
            "of the realm welcome their newest guardian."
        ),
    },
    "The Silver Concord": {
        "alignment": "Good",
        "description": (
            "A grand alliance of scholars, mages, and artificers dedicated to the pursuit "
            "of knowledge and the preservation of ancient wisdom. The Silver Concord's "
            "towering libraries and arcane academies are the envy of the realm. Their "
            "sigil is an open book beneath a crescent moon of silver."
        ),
        "join_message": (
            "Arcane energy ripples through the realm as {name} joins The Silver Concord! "
            "Ancient bells chime in forgotten libraries and the stars shine brighter — "
            "a new mind has joined the pursuit of eternal wisdom."
        ),
    },
    "The Iron Vanguard": {
        "alignment": "Good",
        "description": (
            "The shield-wall of civilisation, the Iron Vanguard is a stalwart brotherhood "
            "of warriors, guardians, and siege-masters who defend the borders of Aethelgard "
            "against the encroaching darkness. Their sigil is a clenched iron gauntlet "
            "before a fortress wall."
        ),
        "join_message": (
            "A mighty horn blast echoes across the realm as {name} joins The Iron Vanguard! "
            "Shields are raised and swords are lifted in salute — the bulwark of the realm "
            "grows stronger with another steadfast defender!"
        ),
    },
}


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def get_clan_info(clan_name):
    """
    Retrieve clan definition by name (case-insensitive).
    Returns (clan_key, clan_data) or (None, None).
    """
    for key, data in CLANS.items():
        if key.lower() == clan_name.lower():
            return key, data
    return None, None


def get_clans_by_alignment(alignment):
    """Return a dict of {clan_key: clan_data} for the given alignment."""
    return {k: v for k, v in CLANS.items() if v["alignment"] == alignment}


def get_clan_members(clan_name):
    """
    Return a list of all player characters belonging to the given clan.
    """
    from evennia.objects.objects import DefaultCharacter

    members = []
    for char in DefaultCharacter.objects.all():
        char_clan = char.attributes.get("clan", default=None)
        if char_clan and char_clan.lower() == clan_name.lower():
            members.append(char)
    return members


def broadcast_clan_join(player_name, clan_name):
    """
    Broadcast a realm-wide BRIGHT RED join message to ALL players.
    """
    from evennia.objects.objects import DefaultCharacter

    _, data = get_clan_info(clan_name)
    if not data:
        return

    join_message = data["join_message"].format(name=player_name)
    formatted = f"|r|h{join_message}|n"

    for char in DefaultCharacter.objects.all():
        char.msg(formatted)


# ---------------------------------------------------------------------------
# COMMANDS
# ---------------------------------------------------------------------------

class CmdClanJoin(Command):
    """
    Join a clan matching your faction alignment.

    Usage:
      clan join <clan_name>
      join <clan_name>

    Your faction alignment (Good or Evil) determines which clans are
    available to you.  Joining a clan triggers a realm-wide announcement
    in bright red text visible to all online players.

    Use |yclan list|n to see all available clans and their descriptions.
    """

    key = "clanjoin"
    aliases = ["join"]
    help_category = "Clan"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg(
                "|yUsage: clan join <clan_name>   (or join <clan_name>)|n\n"
                "|wUse |yclan list|w to see available clans.|n"
            )
            return

        clan_name = self.args

        # Check if already in a clan
        current_clan = caller.attributes.get("clan", default=None)
        if current_clan:
            caller.msg(
                f"|rYou are already a member of |w{current_clan}|r.|n\n"
                f"|wUse |yclan leave|w first if you wish to change clans.|n"
            )
            return

        # Validate clan exists
        clan_key, clan_data = get_clan_info(clan_name)
        if not clan_key:
            caller.msg(
                f"|rNo clan named '{clan_name}' exists.|n\n"
                "|wUse |yclan list|w to see all available clans.|n"
            )
            return

        # Check faction alignment
        char_alignment = caller.attributes.get("alignment", default="Neutral")
        if clan_data["alignment"] != char_alignment:
            caller.msg(
                f"|rThe {clan_key} is a {clan_data['alignment']}-aligned clan.|n"
                f"|rYour alignment is {char_alignment}. "
                f"You cannot join a clan of the opposing faction.|n"
            )
            return

        # Join the clan
        caller.attributes.add("clan", clan_key)
        caller.msg(
            f"|gYou have sworn fealty to |w{clan_key}|g!|n\n"
            f"|w{clan_data['description']}|n\n"
            f"|wUse |yclantalk <msg>|w or |yct <msg>|w to communicate "
            f"with your clanmates.|n"
        )

        # Realm-wide broadcast
        broadcast_clan_join(caller.key, clan_key)


class CmdClanList(Command):
    """
    List all clans in the realm.

    Usage:
      clan list

    Displays all Good and Evil clans along with their descriptions.
    Clans matching your alignment are highlighted.
    """

    key = "clanlist"
    aliases = []
    help_category = "Clan"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        char_alignment = caller.attributes.get("alignment", default="Neutral")
        current_clan = caller.attributes.get("clan", default=None)

        lines = []
        lines.append("|w=== Clans of the Realm ===|n")
        lines.append("")

        for alignment in ("Good", "Evil"):
            color = "|g" if alignment == "Good" else "|r"
            lines.append(f"{color}--- {alignment} Clans ---|n")

            for clan_key, clan_data in CLANS.items():
                if clan_data["alignment"] != alignment:
                    continue

                marker = ""
                if current_clan and current_clan.lower() == clan_key.lower():
                    marker = " |y[YOUR CLAN]|n"
                elif alignment == char_alignment:
                    marker = " |g[Available]|n"
                else:
                    marker = " |r[Opposing Faction]|n"

                lines.append(f"  |w{clan_key}|n{marker}")
                lines.append(f"    {clan_data['description']}")
                lines.append("")

        lines.append("|wUse |yclan join <name>|w to join a clan matching your alignment.|n")
        caller.msg("\n".join(lines))


class CmdClanLeave(Command):
    """
    Leave your current clan.

    Usage:
      clan leave

    Abandons your clan membership.  You may join another clan at any time.
    """

    key = "clanleave"
    aliases = []
    help_category = "Clan"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        current_clan = caller.attributes.get("clan", default=None)
        if not current_clan:
            caller.msg(
                "|yYou are not currently a member of any clan.|n\n"
                "|wUse |yclan list|w to see available clans.|n"
            )
            return

        caller.attributes.add("clan", None)
        caller.msg(
            f"|yYou have renounced your allegiance to |w{current_clan}|y.|n\n"
            "|wYou are now clanless. Use |yclan list|w to see other clans.|n"
        )


class CmdClanTalk(Command):
    """
    Send a private message to all online members of your clan.

    Usage:
      clantalk <message>
      ct <message>

    Messages are displayed in bright yellow and are ONLY visible to
    other online members of your clan.
    """

    key = "clantalk"
    aliases = ["ct"]
    help_category = "Clan"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        if not self.args or not self.args.strip():
            caller.msg(
                "|yUsage: clantalk <message>  (or ct <message>)|n"
            )
            return

        # Check clan membership
        clan_name = caller.attributes.get("clan", default=None)
        if not clan_name:
            caller.msg(
                "|rYou are not a member of any clan.|n\n"
                "|wUse |yclan list|w to see available clans and "
                "|yclan join <name>|w to join one.|n"
            )
            return

        message = self.args.strip()
        prefix = f"|Y[Clan|n |w{clan_name}|n|Y] {caller.key}:|n {message}"

        # Deliver to all online clan members
        members = get_clan_members(clan_name)
        recipients = 0
        for char in members:
            if char != caller:
                char.msg(prefix)
                recipients += 1

        # Confirm to sender
        caller.msg(prefix)
        if recipients > 0:
            caller.msg(
                f"|w(Heard by {recipients} clan member(s))|n"
            )
        else:
            caller.msg("|w(No other clan members are currently online)|n")


class CmdClan(Command):
    """
    Main clan command hub.

    Usage:
      clan join <clan_name>  - Join a clan
      clan list              - List all clans
      clan leave             - Leave your current clan

    For clan communication, use |yclantalk <msg>|n or |yct <msg>|n.
    """

    key = "clan"
    aliases = []
    help_category = "Clan"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg(
                "|yUsage:|n\n"
                "  |wclan join <clan_name>|n  - Join a clan\n"
                "  |wclan list|n              - List all clans\n"
                "  |wclan leave|n             - Leave your current clan\n"
                "  |wclantalk <msg>|n         - Talk to clan members\n"
                "  |wct <msg>|n               - Shorthand for clantalk\n"
            )
            return

        parts = self.args.split(maxsplit=1)
        subcommand = parts[0].lower()
        sub_args = parts[1] if len(parts) > 1 else ""

        if subcommand == "join" or subcommand == "j":
            if not sub_args:
                caller.msg("|yUsage: clan join <clan_name>|n")
                return
            # Delegate to CmdClanJoin
            cmd = CmdClanJoin()
            cmd.caller = caller
            cmd.cmdstring = "clan join"
            cmd.args = sub_args
            cmd.func()

        elif subcommand == "list" or subcommand == "l":
            cmd = CmdClanList()
            cmd.caller = caller
            cmd.cmdstring = "clan list"
            cmd.args = ""
            cmd.func()

        elif subcommand == "leave" or subcommand == "lv":
            cmd = CmdClanLeave()
            cmd.caller = caller
            cmd.cmdstring = "clan leave"
            cmd.args = ""
            cmd.func()

        else:
            caller.msg(
                f"|rUnknown clan subcommand: '{subcommand}'|n\n"
                "|wValid subcommands: join, list, leave|n"
            )