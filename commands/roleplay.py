"""
Roleplay Support System for 'rop'

Provides:
  emote <text>       - Perform a custom emote/action (visible to room)
  emote <text> @target - Direct an emote at a target
  pose <text>        - Alternate alias for emote
  rpdesc <text>      - Set your roleplay description (separate from look desc)
  rpinfo <player>    - View another player's roleplay info
  rpstatus <status>  - Set your roleplay status (e.g. "Open to RP")

Enriches the roleplaying experience with customizable emotes and
extended character descriptions.
"""

from commands.command import Command
from evennia.objects.objects import DefaultCharacter


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def find_player_character(name):
    """Find a player character by name (case-insensitive)."""
    for char in DefaultCharacter.objects.all():
        if char.key.lower() == name.lower():
            if hasattr(char, 'has_account') and char.has_account:
                return char
    return None


def get_rp_description(character):
    """Return the character's roleplay description, or None."""
    return character.attributes.get("rp_description", default=None)


def get_rp_status(character):
    """Return the character's roleplay status, or None."""
    return character.attributes.get("rp_status", default=None)


# ---------------------------------------------------------------------------
# COMMANDS
# ---------------------------------------------------------------------------

class CmdEmote(Command):
    """
    Perform a custom emote or action visible to everyone in the room.

    Usage:
      emote <text>
      emote <text> @ <target>
      pose <text>
      pose <text> @ <target>

    Examples:
      emote waves happily.
      emote grins at @goblin
      pose bows deeply.

    The emote is displayed as "YourName <text>" to others, and
    "You <text>" to yourself. When directed at a target with @,
    the target's name is substituted into the emote text.
    """

    key = "emote"
    aliases = ["pose", "act", "rp", "emote", "em"]
    help_category = "Roleplay"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("|yUsage: emote <text> [@ <target>]|n")
            return

        text = self.args
        target_name = None
        target = None

        # Check for @target syntax
        if '@' in text:
            parts = text.split('@', 1)
            text = parts[0].strip()
            target_name = parts[1].strip()

            # Find the target in the room
            if target_name and caller.location:
                for obj in caller.location.contents:
                    if obj.key.lower() == target_name.lower():
                        target = obj
                        break

            if not target_name:
                caller.msg("|yUsage: emote <text> @ <target>|n")
                return

            if not target:
                caller.msg(f"|rYou don't see '{target_name}' here.|n")
                return

        # Clean up text (remove leading punctuation quirks)
        if not text:
            text = "does something."
        elif not text.endswith(('.', '!', '?')):
            text += "."

        # Build the messages
        if target:
            others_msg = f"|c{caller.key} {text} {target.key}|n"
            self_msg = f"|cYou {text} {target.key}|n"
            target_msg = f"|c{caller.key} {text} you|n"
        else:
            others_msg = f"|c{caller.key} {text}|n"
            self_msg = f"|cYou {text}|n"

        # Send to room and self
        if caller.location:
            if target:
                caller.location.msg_contents(
                    others_msg, exclude=[caller, target]
                )
                target.msg(target_msg)
            else:
                caller.location.msg_contents(others_msg, exclude=caller)

        caller.msg(self_msg)


class CmdRpDesc(Command):
    """
    Set your roleplay description.

    Usage:
      rpdesc <text>

    This description is displayed separately from your base look
    description and provides more detailed roleplaying context.
    """

    key = "rpdesc"
    aliases = ["rpdescription", "roleplaydesc"]
    help_category = "Roleplay"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            current = get_rp_description(caller)
            if current:
                caller.msg("|wYour current roleplay description:|n")
                caller.msg(current)
            else:
                caller.msg(
                    "|yYou don't have a roleplay description set.|n\n"
                    "|wUse |yrpdesc <text>|w to set one.|n"
                )
            return

        caller.attributes.add("rp_description", self.args)
        caller.msg("|gYour roleplay description has been updated.|n")


class CmdRpInfo(Command):
    """
    View another player's roleplay information.

    Usage:
      rpinfo <player>
      rpinfo

    Shows a player's roleplay description and status.
    """

    key = "rpinfo"
    aliases = ["rplook", "rpview"]
    help_category = "Roleplay"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        # If no argument, show own info
        if not self.args:
            target = caller
        else:
            # Try to find in room first
            target = None
            if caller.location:
                for obj in caller.location.contents:
                    if obj.key.lower() == self.args.lower():
                        target = obj
                        break

            # If not in room, search all players
            if not target:
                target = find_player_character(self.args)

            if not target:
                caller.msg(f"|rNo player named '{self.args}' found.|n")
                return

        lines = []
        lines.append(f"|w=== {target.key} — Roleplay Info ===|n")
        lines.append("")

        # RP status
        status = get_rp_status(target)
        if status:
            lines.append(f"|cRP Status:|n {status}")
        else:
            lines.append(f"|cRP Status:|n |yNot set|n")

        # RP description
        rpdesc = get_rp_description(target)
        if rpdesc:
            lines.append("")
            lines.append("|cRoleplay Description:|n")
            lines.append(rpdesc)
        else:
            lines.append("")
            lines.append("|yThis player has not set a roleplay description.|n")

        # Basic info
        race = target.attributes.get("race", default="Unknown")
        charclass = target.attributes.get("class", default="Unknown")
        level = target.attributes.get("level", default=1)
        alignment = target.attributes.get("alignment", default="?")
        lines.append("")
        lines.append(f"|cRace:|n {race}   |cClass:|n {charclass}   |cLevel:|n {level}")
        lines.append(f"|cAlignment:|n {alignment}")

        caller.msg("\n".join(lines))


class CmdRpStatus(Command):
    """
    Set your roleplay status.

    Usage:
      rpstatus <text>
      rpstatus

    Examples:
      rpstatus Open to RP
      rpstatus In character - approach me!
      rpstatus (no argument shows current status)

    Other players can see your status via |yrpinfo <name>|w.
    """

    key = "rpstatus"
    aliases = ["rps", "roleplaystatus"]
    help_category = "Roleplay"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            current = get_rp_status(caller)
            if current:
                caller.msg(f"|wYour current roleplay status: |c{current}|n")
            else:
                caller.msg(
                    "|yYou haven't set a roleplay status.|n\n"
                    "|wUse |yrpstatus <text>|w to set one.|n\n"
                    "|wExamples: |yrpstatus Open to RP|w, |yrpstatus In character|n"
                )
            return

        caller.attributes.add("rp_status", self.args)
        caller.msg(f"|gYour roleplay status is now: |c{self.args}|n")


# Alias for test compatibility
CmdPose = CmdEmote