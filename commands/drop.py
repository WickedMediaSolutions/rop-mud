"""
Currency drop/take commands for 'rop'.

Commands:
  dropcoins <amount>  - Drop some carried gold onto the ground
  dropcoins all       - Drop all carried gold onto the ground
  takecoins <amount>  - Pick up gold lying on the ground
  takecoins all       - Pick up all gold lying on the ground

Carried gold is stored on the `money` attribute; gold on the ground is
stored on the current room's `ground_gold` attribute, which the room
display (`get_display_things`) surfaces as the "Coins:" line.
"""

from commands.command import Command


class CmdDropCoins(Command):
    """
    Drop gold onto the ground.

    Usage:
      dropcoins <amount>
      dropcoins all

    Drops the specified amount of carried gold onto the ground in your
    current room.  Other players can then pick it up with `takecoins`.
    """

    key = "dropcoins"
    aliases = ["dropgold", "dropmoney"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        if not caller.location:
            caller.msg("|rYou have nowhere to drop gold.|n")
            return

        amount = self._parse_amount(caller, allow_all=True)
        if amount is None:
            return

        if amount <= 0:
            caller.msg("|yUsage: dropcoins <amount>  or  dropcoins all|n")
            return

        carried = caller.attributes.get("money", default=0) or 0
        if carried < amount:
            caller.msg(
                f"|rYou don't have that much gold. "
                f"You are carrying {carried} gold.|n"
            )
            return

        caller.attributes.add("money", carried - amount)
        ground = caller.location.attributes.get("ground_gold", default=0) or 0
        caller.location.attributes.add("ground_gold", ground + amount)

        caller.msg(f"|gYou drop {amount} gold onto the ground.|n")
        caller.location.msg_contents(
            f"|g{caller.key} drops {amount} gold onto the ground.|n",
            exclude=[caller],
        )

    def _parse_amount(self, caller, allow_all=False):
        """Parse self.args into a positive int, or -1 for 'all'."""
        arg = self.args.strip().lower() if self.args else ""

        if allow_all and arg == "all":
            return caller.attributes.get("money", default=0) or 0

        try:
            amount = int(arg)
        except (TypeError, ValueError):
            return None
        return amount


class CmdTakeCoins(Command):
    """
    Pick up gold from the ground.

    Usage:
      takecoins <amount>
      takecoins all

    Picks up the specified amount of gold from the ground in your current
    room.
    """

    key = "takecoins"
    aliases = ["takegold", "takemoney", "getcoins"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        if not caller.location:
            caller.msg("|rYou have nowhere to take gold from.|n")
            return

        arg = self.args.strip().lower() if self.args else ""
        if arg in ("",):
            caller.msg("|yUsage: takecoins <amount>  or  takecoins all|n")
            return

        ground = caller.location.attributes.get("ground_gold", default=0) or 0
        if ground <= 0:
            caller.msg("|yThere is no gold on the ground here.|n")
            return

        if arg == "all":
            amount = ground
        else:
            try:
                amount = int(arg)
            except (TypeError, ValueError):
                caller.msg("|yUsage: takecoins <amount>  or  takecoins all|n")
                return

        if amount <= 0:
            caller.msg("|yUsage: takecoins <amount>  or  takecoins all|n")
            return

        if amount > ground:
            caller.msg(
                f"|rThere are only {ground} gold on the ground.|n"
            )
            return

        caller.location.attributes.add("ground_gold", ground - amount)
        carried = caller.attributes.get("money", default=0) or 0
        caller.attributes.add("money", carried + amount)

        caller.msg(f"|gYou pick up {amount} gold from the ground.|n")
        caller.location.msg_contents(
            f"|g{caller.key} picks up {amount} gold from the ground.|n",
            exclude=[caller],
        )


class CmdGive(Command):
    """
    Give an item to another character.

    Usage:
      give <item> to <character>

    Transfers one item from your inventory to the target character's
    inventory. Both characters must be in the same room.
    """

    key = "give"
    aliases = ["hand"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args_raw = self.args.strip() if self.args else ""

    def func(self):
        caller = self.caller
        if not self.args_raw:
            caller.msg("|yUsage: give <item> to <character>|n")
            return

        # Parse "item to target"
        if " to " not in self.args_raw.lower():
            caller.msg("|yUsage: give <item> to <character>|n")
            return

        parts = self.args_raw.lower().split(" to ", 1)
        if len(parts) != 2:
            caller.msg("|yUsage: give <item> to <character>|n")
            return
        item_name, target_name = parts[0].strip(), parts[1].strip()

        if not item_name or not target_name:
            caller.msg("|yUsage: give <item> to <character>|n")
            return

        # Find the target character in the room
        target = None
        for obj in caller.location.contents:
            if obj.key.lower() == target_name and hasattr(obj, "has_account") and obj.has_account:
                target = obj
                break
        if not target:
            caller.msg(f"|rYou don't see '{target_name}' here.|n")
            return

        if target == caller:
            caller.msg("|yYou can't give items to yourself.|n")
            return

        # Find the item in caller's inventory
        item = None
        for obj in caller.contents:
            if getattr(obj, "destination", None):
                continue
            if obj.key.lower() == item_name:
                item = obj
                break
        if not item:
            caller.msg(f"|rYou don't have '{item_name}'.|n")
            return

        # Transfer the item
        item.move_to(target, quiet=True)
        caller.msg(f"|gYou give {item.key} to {target.key}.|n")
        target.msg(f"|g{caller.key} gives you {item.key}.|n")
        caller.location.msg_contents(
            f"|g{caller.key} gives {item.key} to {target.key}.|n",
            exclude=[caller, target],
        )


class CmdPut(Command):
    """
    Put an item into a container.

    Usage:
      put <item> in <container>

    Places an item from your inventory into a container object.
    The container must be in your inventory or in the room.
    """

    key = "put"
    aliases = ["place"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args_raw = self.args.strip() if self.args else ""

    def func(self):
        caller = self.caller
        if not self.args_raw:
            caller.msg("|yUsage: put <item> in <container>|n")
            return

        if " in " not in self.args_raw.lower():
            caller.msg("|yUsage: put <item> in <container>|n")
            return

        parts = self.args_raw.lower().split(" in ", 1)
        if len(parts) != 2:
            caller.msg("|yUsage: put <item> in <container>|n")
            return
        item_name, container_name = parts[0].strip(), parts[1].strip()

        if not item_name or not container_name:
            caller.msg("|yUsage: put <item> in <container>|n")
            return

        # Find the item in caller's inventory
        item = None
        for obj in caller.contents:
            if getattr(obj, "destination", None):
                continue
            if obj.key.lower() == item_name:
                item = obj
                break
        if not item:
            caller.msg(f"|rYou don't have '{item_name}'.|n")
            return

        # Find the container in inventory or room
        container = None
        candidates = list(caller.contents) + list(caller.location.contents if caller.location else [])
        for obj in candidates:
            if getattr(obj, "destination", None):
                continue
            if obj.key.lower() == container_name and obj != item:
                container = obj
                break
        if not container:
            caller.msg(f"|rYou don't see '{container_name}' here.|n")
            return

        # Check container capacity
        capacity = container.attributes.get("capacity", default=10) if hasattr(container, "attributes") else 10
        current = len([o for o in container.contents if not getattr(o, "destination", None)])
        if current >= capacity:
            caller.msg(f"|r{container.key} is full.|n")
            return

        item.move_to(container, quiet=True)
        caller.msg(f"|gYou put {item.key} into {container.key}.|n")
        caller.location.msg_contents(
            f"|g{caller.key} puts {item.key} into {container.key}.|n",
            exclude=[caller],
        )


class CmdGet(Command):
    """
    Take an item from a container.

    Usage:
      get <item> from <container>

    Removes an item from a container and places it in your inventory.
    The container must be in your inventory or in the room.
    """

    key = "get"
    aliases = ["take"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args_raw = self.args.strip() if self.args else ""

    def func(self):
        caller = self.caller
        if not self.args_raw:
            caller.msg("|yUsage: get <item> from <container>|n")
            return

        if " from " not in self.args_raw.lower():
            caller.msg("|yUsage: get <item> from <container>|n")
            return

        parts = self.args_raw.lower().split(" from ", 1)
        if len(parts) != 2:
            caller.msg("|yUsage: get <item> from <container>|n")
            return
        item_name, container_name = parts[0].strip(), parts[1].strip()

        if not item_name or not container_name:
            caller.msg("|yUsage: get <item> from <container>|n")
            return

        # Find the container
        container = None
        candidates = list(caller.contents) + list(caller.location.contents if caller.location else [])
        for obj in candidates:
            if getattr(obj, "destination", None):
                continue
            if obj.key.lower() == container_name:
                container = obj
                break
        if not container:
            caller.msg(f"|rYou don't see '{container_name}' here.|n")
            return

        # Find the item in the container
        item = None
        for obj in container.contents:
            if getattr(obj, "destination", None):
                continue
            if obj.key.lower() == item_name:
                item = obj
                break
        if not item:
            caller.msg(f"|r'{container_name}' doesn't contain '{item_name}'.|n")
            return

        item.move_to(caller, quiet=True)
        caller.msg(f"|gYou take {item.key} from {container.key}.|n")
        caller.location.msg_contents(
            f"|g{caller.key} takes {item.key} from {container.key}.|n",
            exclude=[caller],
        )


class CmdGiveGold(Command):
    """
    Give gold to another character.

    Usage:
      givegold <amount> to <character>
      givegold all to <character>

    Transfers carried gold from you to the target character.
    Both characters must be in the same room.
    """

    key = "givegold"
    aliases = ["pay", "sendgold"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args_raw = self.args.strip() if self.args else ""

    def func(self):
        caller = self.caller
        if not self.args_raw:
            caller.msg("|yUsage: givegold <amount> to <character>|n")
            return

        if " to " not in self.args_raw.lower():
            caller.msg("|yUsage: givegold <amount> to <character>|n")
            return

        parts = self.args_raw.split(" to ", 1)
        if len(parts) != 2:
            caller.msg("|yUsage: givegold <amount> to <character>|n")
            return
        amount_str, target_name = parts[0].strip().lower(), parts[1].strip()

        if not amount_str or not target_name:
            caller.msg("|yUsage: givegold <amount> to <character>|n")
            return

        # Find the target character in the room
        target = None
        for obj in (caller.location.contents if caller.location else []):
            if obj.key.lower() == target_name and hasattr(obj, "has_account") and obj.has_account:
                target = obj
                break
        if not target:
            caller.msg(f"|rYou don't see '{target_name}' here.|n")
            return

        if target == caller:
            caller.msg("|yYou can't give gold to yourself.|n")
            return

        # Parse amount
        from world.economy import get_money, remove_money, add_money, format_money_brief
        carried = get_money(caller)

        if amount_str == "all":
            amount = carried
        else:
            try:
                amount = int(amount_str)
            except ValueError:
                caller.msg("|rInvalid amount. Use a number or 'all'.|n")
                return

        if amount <= 0:
            caller.msg("|yYou must give a positive amount.|n")
            return

        if amount > carried:
            caller.msg(
                f"|rYou don't have that much gold. "
                f"You are carrying {format_money_brief(carried)}.|n"
            )
            return

        if not remove_money(caller, amount):
            caller.msg("|rFailed to transfer gold.|n")
            return

        add_money(target, amount)

        caller.msg(
            f"|gYou give {format_money_brief(amount)} to {target.key}.|n"
        )
        target.msg(
            f"|g{caller.key} gives you {format_money_brief(amount)}.|n"
        )
        caller.location.msg_contents(
            f"|g{caller.key} gives some gold to {target.key}.|n",
            exclude=[caller, target],
        )
