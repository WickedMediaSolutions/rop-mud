"""
Player Housing System for 'rop'

Provides:
  house buy              - Purchase a personal room (costs gold)
  house home             - Teleport to your house
  house invite <player>  - Allow a player to visit your house
  house uninvite <player>- Revoke a player's access
  house list             - List invited players
  house desc <text>      - Set your house description
  house name <name>      - Rename your house
  house lock             - Lock your house (no visitors)
  house unlock           - Unlock your house (invited players can enter)

Each player can own one house. Houses are private rooms created
dynamically when purchased. Only the owner and invited players
can enter.
"""

from commands.command import Command
from evennia.objects.objects import DefaultCharacter
from evennia import create_object, search_object


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

HOUSE_COST = 500  # Gold cost to buy a house
HOUSE_ZONE_NAME = "Player Housing District"


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def get_house_room(character):
    """Return the character's house room, or None if they don't own one."""
    house_dbref = character.attributes.get("house_dbref", default=None)
    if not house_dbref:
        return None
    try:
        from evennia.objects.models import ObjectDB
        room = ObjectDB.objects.filter(id=house_dbref).first()
        if room:
            return room
    except Exception:
        pass
    # Fallback: search by key
    results = search_object(f"House of {character.key}")
    if results:
        return results[0]
    return None


def get_house_owner(room):
    """Return the owner character of a house room, or None."""
    owner_name = room.attributes.get("house_owner", default=None)
    if not owner_name:
        return None
    for char in DefaultCharacter.objects.all():
        if char.key.lower() == owner_name.lower():
            return char
    return None


def is_house_room(room):
    """Check if a room is a player house."""
    if not room:
        return False
    return room.attributes.get("is_player_house", default=False)


def can_enter_house(character, house_room):
    """Check if a character can enter a house room."""
    if not is_house_room(house_room):
        return True  # Not a house, anyone can enter

    owner = get_house_owner(house_room)
    if not owner:
        return True  # No owner, allow entry

    # Owner always allowed
    if character.key.lower() == owner.key.lower():
        return True

    # Check if locked
    if house_room.attributes.get("house_locked", default=False):
        return False

    # Check invite list
    invited = house_room.attributes.get("house_invited", default=[])
    if isinstance(invited, list):
        if character.key.lower() in [n.lower() for n in invited]:
            return True

    return False


def get_invited_list(house_room):
    """Return the list of invited player names."""
    invited = house_room.attributes.get("house_invited", default=None)
    if invited is None:
        return []
    if isinstance(invited, list):
        return invited
    return []


def set_invited_list(house_room, invited):
    """Set the invited list for a house room."""
    house_room.attributes.add("house_invited", invited)


def find_housing_district():
    """Find or create the central housing district room."""
    results = search_object(HOUSE_ZONE_NAME)
    if results:
        return results[0]

    # Create the housing district
    try:
        district = create_object(
            "typeclasses.rooms.Room",
            key=HOUSE_ZONE_NAME,
        )
        if district:
            district.db.desc = (
                "A quiet, well-kept district lined with modest homes and "
                "cottages. A cobblestone path winds between the residences, "
                "each bearing a polished brass nameplate beside the door. "
                "The air smells of fresh bread and chimney smoke."
            )
            district.attributes.add("is_safe_zone", True)
            return district
    except Exception:
        pass
    return None


def create_house_room(character):
    """Create a new house room for a character. Returns the room or None."""
    try:
        room = create_object(
            "typeclasses.rooms.Room",
            key=f"House of {character.key}",
        )
        if not room:
            return None

        room.db.desc = (
            f"A cozy, well-appointed home belonging to {character.key}. "
            f"The walls are adorned with personal trophies and mementos "
            f"from adventures across the realm. A warm hearth crackles "
            f"in the corner, and comfortable furnishings invite rest."
        )
        room.attributes.add("is_player_house", True)
        room.attributes.add("house_owner", character.key)
        room.attributes.add("house_locked", False)
        room.attributes.add("house_invited", [])
        room.attributes.add("is_safe_zone", True)

        # Connect to housing district
        district = find_housing_district()
        if district:
            # Create bidirectional exit
            exit_to_house = create_object(
                "typeclasses.exits.Exit",
                key=f"house of {character.key}",
                location=district,
                destination=room,
            )
            exit_to_district = create_object(
                "typeclasses.exits.Exit",
                key="out",
                location=room,
                destination=district,
            )

        return room
    except Exception:
        return None


# ---------------------------------------------------------------------------
# COMMANDS
# ---------------------------------------------------------------------------

class CmdHouseBuy(Command):
    """
    Purchase a personal house.

    Usage:
      house buy

    Costs 500 gold. You will receive a private room in the Player
    Housing District that only you (and invited guests) can enter.
    """

    key = "housebuy"
    aliases = []
    help_category = "Housing"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        # Check if already own a house
        existing = get_house_room(caller)
        if existing:
            caller.msg(
                f"|yYou already own a house: |w{existing.key}|y.|n\n"
                f"|wUse |yhouse home|w to go there.|n"
            )
            return

        # Check gold
        from world.economy import get_money, remove_money, format_money_brief
        if not remove_money(caller, HOUSE_COST):
            carried = get_money(caller)
            caller.msg(
                f"|rYou need {format_money_brief(HOUSE_COST)} to buy a house. "
                f"(You have {format_money_brief(carried)}.)|n"
            )
            return

        # Create the house
        room = create_house_room(caller)
        if not room:
            # Refund
            from world.economy import add_money
            add_money(caller, HOUSE_COST)
            caller.msg("|rFailed to create your house. Your gold has been refunded.|n")
            return

        # Store house reference on character
        caller.attributes.add("house_dbref", room.id)

        caller.msg(
            f"|gCongratulations! You are now the proud owner of |w{room.key}|g!|n\n"
            f"|wCost: |Y{format_money_brief(HOUSE_COST)}|n\n"
            f"|wUse |yhouse home|w to teleport to your house.|n"
            f"|wUse |yhouse invite <player>|w to allow friends to visit.|n"
        )


class CmdHouseHome(Command):
    """
    Teleport to your house.

    Usage:
      house home

    Instantly transports you to your personal house.
    """

    key = "househome"
    aliases = []
    help_category = "Housing"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        house = get_house_room(caller)
        if not house:
            caller.msg(
                "|yYou don't own a house.|n\n"
                f"|wUse |yhouse buy|w to purchase one ({HOUSE_COST} gold).|n"
            )
            return

        if caller.location == house:
            caller.msg("|yYou are already at your house.|n")
            return

        caller.msg(f"|gYou make your way home to |w{house.key}|g.|n")
        if caller.location:
            caller.location.msg_contents(
                f"|g{caller.key} heads home.|n", exclude=caller
            )
        caller.move_to(house)
        house.msg_contents(
            f"|g{caller.key} arrives home.|n", exclude=caller
        )
        caller.msg(house.return_appearance(caller))


class CmdHouseInvite(Command):
    """
    Invite a player to visit your house.

    Usage:
      house invite <player>

    Invited players can enter your house even when it's locked.
    """

    key = "houseinvite"
    aliases = []
    help_category = "Housing"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        house = get_house_room(caller)
        if not house:
            caller.msg("|yYou don't own a house.|n")
            return

        if not self.args:
            caller.msg("|yUsage: house invite <player>|n")
            return

        target_name = self.args

        if target_name.lower() == caller.key.lower():
            caller.msg("|rYou already have access to your own house.|n")
            return

        # Check target exists
        target = None
        for char in DefaultCharacter.objects.all():
            if char.key.lower() == target_name.lower():
                target = char
                break

        if not target:
            caller.msg(f"|rNo player named '{target_name}' found.|n")
            return

        invited = get_invited_list(house)
        if target.key.lower() in [n.lower() for n in invited]:
            caller.msg(f"|y{target.key} is already invited to your house.|n")
            return

        invited.append(target.key)
        set_invited_list(house, invited)
        caller.msg(f"|g{target.key} can now visit your house.|n")

        # Notify target if online
        if hasattr(target, 'sessions') and target.sessions.count() > 0:
            target.msg(
                f"|g{caller.key} has invited you to visit their house!|n\n"
                f"|wUse |yhouse visit {caller.key}|w to go there.|n"
            )


class CmdHouseUninvite(Command):
    """
    Revoke a player's access to your house.

    Usage:
      house uninvite <player>
    """

    key = "houseuninvite"
    aliases = []
    help_category = "Housing"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        house = get_house_room(caller)
        if not house:
            caller.msg("|yYou don't own a house.|n")
            return

        if not self.args:
            caller.msg("|yUsage: house uninvite <player>|n")
            return

        target_name = self.args
        invited = get_invited_list(house)

        removed = None
        new_invited = []
        for name in invited:
            if name.lower() == target_name.lower():
                removed = name
            else:
                new_invited.append(name)

        if removed is None:
            caller.msg(f"|y'{target_name}' is not on your house invite list.|n")
            return

        set_invited_list(house, new_invited)
        caller.msg(f"|y{removed} can no longer visit your house.|n")


class CmdHouseList(Command):
    """
    List players invited to your house.

    Usage:
      house list
    """

    key = "houselist"
    aliases = []
    help_category = "Housing"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        house = get_house_room(caller)
        if not house:
            caller.msg("|yYou don't own a house.|n")
            return

        invited = get_invited_list(house)
        locked = house.attributes.get("house_locked", default=False)

        lines = []
        lines.append(f"|w=== {house.key} ===|n")
        lines.append(f"|cLocked:|n {'|rYes|n' if locked else '|gNo|n'}")
        lines.append("")

        if not invited:
            lines.append("|yNo players are invited to your house.|n")
        else:
            lines.append("|wInvited Players:|n")
            for name in invited:
                # Check if online
                online = False
                for char in DefaultCharacter.objects.all():
                    if char.key.lower() == name.lower():
                        if hasattr(char, 'sessions') and char.sessions.count() > 0:
                            online = True
                        break
                status = "|gOnline|n" if online else "|rOffline|n"
                lines.append(f"  |w{name}|n - {status}")

        lines.append("")
        lines.append("|wUse |yhouse invite <player>|w to add guests.|n")
        caller.msg("\n".join(lines))


class CmdHouseDesc(Command):
    """
    Set your house description.

    Usage:
      house desc <text>

    Customize the description players see when they enter your house.
    """

    key = "housedesc"
    aliases = []
    help_category = "Housing"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        house = get_house_room(caller)
        if not house:
            caller.msg("|yYou don't own a house.|n")
            return

        if not self.args:
            caller.msg("|yUsage: house desc <description text>|n")
            return

        house.db.desc = self.args
        caller.msg(f"|gYour house description has been updated.|n")


class CmdHouseName(Command):
    """
    Rename your house.

    Usage:
      house name <new name>

    Changes the name displayed on your house.
    """

    key = "housename"
    aliases = []
    help_category = "Housing"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        house = get_house_room(caller)
        if not house:
            caller.msg("|yYou don't own a house.|n")
            return

        if not self.args:
            caller.msg("|yUsage: house name <new name>|n")
            return

        old_name = house.key
        house.key = self.args
        caller.msg(f"|gYour house has been renamed from '{old_name}' to '{self.args}'.|n")


class CmdHouseLock(Command):
    """
    Lock your house — no visitors allowed.

    Usage:
      house lock

    When locked, only you can enter your house. Invited players
    are temporarily denied access until you unlock.
    """

    key = "houselock"
    aliases = []
    help_category = "Housing"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        house = get_house_room(caller)
        if not house:
            caller.msg("|yYou don't own a house.|n")
            return

        if house.attributes.get("house_locked", default=False):
            caller.msg("|yYour house is already locked.|n")
            return

        house.attributes.add("house_locked", True)
        caller.msg("|rYour house is now locked. No visitors may enter.|n")


class CmdHouseUnlock(Command):
    """
    Unlock your house — invited players can enter again.

    Usage:
      house unlock
    """

    key = "houseunlock"
    aliases = []
    help_category = "Housing"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        house = get_house_room(caller)
        if not house:
            caller.msg("|yYou don't own a house.|n")
            return

        if not house.attributes.get("house_locked", default=False):
            caller.msg("|yYour house is already unlocked.|n")
            return

        house.attributes.add("house_locked", False)
        caller.msg("|gYour house is now unlocked. Invited players may enter.|n")


class CmdHouseVisit(Command):
    """
    Visit another player's house (if invited).

    Usage:
      house visit <player>

    You must be on the owner's invite list to enter.
    """

    key = "housevisit"
    aliases = []
    help_category = "Housing"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("|yUsage: house visit <player>|n")
            return

        owner_name = self.args

        # Find the owner
        owner = None
        for char in DefaultCharacter.objects.all():
            if char.key.lower() == owner_name.lower():
                owner = char
                break

        if not owner:
            caller.msg(f"|rNo player named '{owner_name}' found.|n")
            return

        house = get_house_room(owner)
        if not house:
            caller.msg(f"|y{owner.key} doesn't own a house.|n")
            return

        if not can_enter_house(caller, house):
            caller.msg(
                f"|rYou are not invited to {owner.key}'s house.|n\n"
                f"|wAsk them to use |yhouse invite {caller.key}|w.|n"
            )
            return

        if caller.location == house:
            caller.msg("|yYou are already there.|n")
            return

        caller.msg(f"|gYou visit |w{house.key}|g.|n")
        if caller.location:
            caller.location.msg_contents(
                f"|g{caller.key} heads off to visit {owner.key}'s house.|n",
                exclude=caller,
            )
        caller.move_to(house)
        house.msg_contents(
            f"|g{caller.key} arrives for a visit.|n", exclude=caller
        )
        caller.msg(house.return_appearance(caller))


class CmdHouse(Command):
    """
    Main house command hub.

    Usage:
      house buy               - Purchase a house (500 gold)
      house home              - Go to your house
      house invite <player>   - Invite a player
      house uninvite <player> - Revoke invitation
      house list              - List invited players
      house desc <text>       - Set house description
      house name <name>       - Rename your house
      house lock              - Lock your house
      house unlock            - Unlock your house
      house visit <player>    - Visit another player's house
    """

    key = "house"
    aliases = []
    help_category = "Housing"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg(
                "|yHouse Commands:|n\n"
                "  |whouse buy|n               - Purchase a house (500 gold)\n"
                "  |whouse home|n              - Go to your house\n"
                "  |whouse invite <player>|n   - Invite a player\n"
                "  |whouse uninvite <player>|n - Revoke invitation\n"
                "  |whouse list|n              - List invited players\n"
                "  |whouse desc <text>|n       - Set house description\n"
                "  |whouse name <name>|n       - Rename your house\n"
                "  |whouse lock|n              - Lock your house\n"
                "  |whouse unlock|n            - Unlock your house\n"
                "  |whouse visit <player>|n    - Visit another's house\n"
            )
            return

        parts = self.args.split(maxsplit=1)
        subcommand = parts[0].lower()
        sub_args = parts[1] if len(parts) > 1 else ""

        if subcommand in ("buy", "purchase"):
            cmd = CmdHouseBuy()
            cmd.caller = caller
            cmd.cmdstring = "house buy"
            cmd.args = ""
            cmd.func()

        elif subcommand in ("home", "go", "enter"):
            cmd = CmdHouseHome()
            cmd.caller = caller
            cmd.cmdstring = "house home"
            cmd.args = ""
            cmd.func()

        elif subcommand in ("invite", "inv", "add"):
            if not sub_args:
                caller.msg("|yUsage: house invite <player>|n")
                return
            cmd = CmdHouseInvite()
            cmd.caller = caller
            cmd.cmdstring = "house invite"
            cmd.args = sub_args
            cmd.func()

        elif subcommand in ("uninvite", "uninv", "remove", "kick"):
            if not sub_args:
                caller.msg("|yUsage: house uninvite <player>|n")
                return
            cmd = CmdHouseUninvite()
            cmd.caller = caller
            cmd.cmdstring = "house uninvite"
            cmd.args = sub_args
            cmd.func()

        elif subcommand in ("list", "guests", "who"):
            cmd = CmdHouseList()
            cmd.caller = caller
            cmd.cmdstring = "house list"
            cmd.args = ""
            cmd.func()

        elif subcommand in ("desc", "describe", "description"):
            cmd = CmdHouseDesc()
            cmd.caller = caller
            cmd.cmdstring = "house desc"
            cmd.args = sub_args
            cmd.func()

        elif subcommand in ("name", "rename"):
            if not sub_args:
                caller.msg("|yUsage: house name <new name>|n")
                return
            cmd = CmdHouseName()
            cmd.caller = caller
            cmd.cmdstring = "house name"
            cmd.args = sub_args
            cmd.func()

        elif subcommand in ("lock", "close"):
            cmd = CmdHouseLock()
            cmd.caller = caller
            cmd.cmdstring = "house lock"
            cmd.args = ""
            cmd.func()

        elif subcommand in ("unlock", "open"):
            cmd = CmdHouseUnlock()
            cmd.caller = caller
            cmd.cmdstring = "house unlock"
            cmd.args = ""
            cmd.func()

        elif subcommand in ("visit", "goto"):
            if not sub_args:
                caller.msg("|yUsage: house visit <player>|n")
                return
            cmd = CmdHouseVisit()
            cmd.caller = caller
            cmd.cmdstring = "house visit"
            cmd.args = sub_args
            cmd.func()

        else:
            caller.msg(
                f"|yUnknown house subcommand: '{subcommand}'.|n\n"
                "|wValid: buy, home, invite, uninvite, list, desc, name, lock, unlock, visit|n"
            )