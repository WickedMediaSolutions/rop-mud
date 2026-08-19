"""
Looting and Sacrificing commands for 'rop'

Commands:
  sac / sacrifice <corpse>  - Destroy a corpse, receive coins from the gods
  loot <corpse>             - Take all coins and items from a corpse
  loot all <corpse>         - Same as loot <corpse>
  autoloot                  - Toggle auto-loot on/off
  autosac                   - Toggle auto-sacrifice on/off
"""

import random
from commands.command import Command
from world.combat import _make_corpse  # noqa: F401 - re-export for test compatibility


# ---------------------------------------------------------------------------
# Sacrifice reward: 1-5 copper per mob level
# ---------------------------------------------------------------------------

def calculate_sac_reward(npc_level):
    """
    Calculate the coin reward for sacrificing a corpse.

    Returns (gold_equivalent, coin_display_string).
    Uses unified economy module for display.
    """
    from world.economy import format_money_long
    
    # Copper pieces (100 copper = 1 gold)
    base = random.randint(1, 5)
    copper = base * max(1, npc_level)
    gold_eq = copper / 100
    
    display = format_money_long(gold_eq)
    return gold_eq, display


# ---------------------------------------------------------------------------
# Sacrifice command
# ---------------------------------------------------------------------------

class CmdSacrifice(Command):
    """
    Sacrifice a corpse to the gods for a coin reward.

    Usage:
      sac <corpse>
      sacrifice <corpse>

    The reward scales with the level of the creature whose corpse
    you are sacrificing.  The corpse is destroyed in the process.
    """

    key = "sac"
    aliases = ["sacrifice"]
    help_category = "Looting"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        if not args:
            caller.msg("|yUsage: sac <corpse>|n")
            return

        # Find the target corpse
        corpse = caller.search(args, candidates=caller.location.contents if caller.location else [])
        if not corpse:
            return

        if not corpse.attributes.get("is_corpse", False):
            caller.msg(f"|r{corpse.key} is not a corpse.|n")
            return

        # Get the original mob level stored on the corpse
        npc_level = corpse.attributes.get("corpse_npc_level", default=1)

        # Calculate reward
        coins, display = calculate_sac_reward(npc_level)

        # Add coins to the caller
        current_money = caller.attributes.get("money", default=0)
        caller.attributes.add("money", current_money + coins)

        # Announce
        caller.msg(
            f"|cYou offer {corpse.key} to the gods and receive |W{display}|c!|n"
        )
        if caller.location:
            caller.location.msg_contents(
                f"|c{caller.key} offers {corpse.key} to the gods.|n",
                exclude=[caller],
            )

        # Destroy the corpse
        corpse.delete()


# ---------------------------------------------------------------------------
# Loot command
# ---------------------------------------------------------------------------

class CmdLoot(Command):
    """
    Loot coins and items from a corpse.

    Usage:
      loot <corpse>
      loot all <corpse>

    Transfers all coins and inventory items from the corpse into
    your own inventory.  The empty corpse remains behind as a
    visual reminder.
    """

    key = "loot"
    aliases = []
    help_category = "Looting"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        # Handle "loot all <corpse>" -> strip "all"
        if args.startswith("all "):
            args = args[4:].strip()
        elif args == "all":
            # "loot all" without a target
            caller.msg("|yUsage: loot all <corpse>|n")
            return

        if not args:
            caller.msg("|yUsage: loot <corpse>  or  loot all <corpse>|n")
            return

        # Find the target corpse
        corpse = caller.search(args, candidates=caller.location.contents if caller.location else [])
        if not corpse:
            return

        if not corpse.attributes.get("is_corpse", False):
            caller.msg(f"|r{corpse.key} is not a corpse.|n")
            return

        # Transfer coins
        corpse_money = corpse.attributes.get("money", 0) or 0
        if corpse_money > 0:
            current_money = caller.attributes.get("money", default=0)
            caller.attributes.add("money", current_money + corpse_money)
            corpse.attributes.add("money", 0)

        # Transfer all physical items inside the corpse to the caller
        items = [obj for obj in corpse.contents if not obj.destination]
        item_count = len(items)
        for obj in items:
            obj.move_to(caller, quiet=True)

        # Build result message with unified coin format
        from world.economy import format_money_brief
        parts = []
        if corpse_money > 0:
            parts.append(f"{format_money_brief(corpse_money)}")
        if item_count > 0:
            parts.append(f"|w{item_count} item(s)|n")

        if parts:
            caller.msg(
                f"|gYou loot {corpse.key} and take {', '.join(parts)}.|n"
            )
            if caller.location:
                caller.location.msg_contents(
                    f"|g{caller.key} loots {corpse.key}.|n",
                    exclude=[caller],
                )
        else:
            caller.msg(f"|y{corpse.key} has nothing to loot.|n")


# ---------------------------------------------------------------------------
# Auto-loot toggle
# ---------------------------------------------------------------------------

class CmdAutoLoot(Command):
    """
    Toggle automatic looting of corpses.

    Usage:
      autoloot

    When active, you will automatically loot all coins and items
    from a mob's corpse immediately upon killing it in combat.
    """

    key = "autoloot"
    aliases = []
    help_category = "Looting"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        current = caller.attributes.get("autoloot", default=False)

        if current:
            caller.attributes.add("autoloot", False)
            caller.msg("|yAuto-Loot: |rOFF|n")
        else:
            caller.attributes.add("autoloot", True)
            caller.msg("|yAuto-Loot: |gON|n")


# ---------------------------------------------------------------------------
# Auto-sacrifice toggle
# ---------------------------------------------------------------------------

# Alias for test compatibility
CmdSac = CmdSacrifice


class CmdAutoSac(Command):
    """
    Toggle automatic corpse sacrificing.

    Usage:
      autosac

    When active, you will automatically sacrifice a mob's corpse
    (and receive bonus coins) immediately after combat finishes.
    If both autoloot and autosac are active, autoloot triggers
    first, then the empty corpse is sacrificed.
    """

    key = "autosac"
    aliases = []
    help_category = "Looting"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        current = caller.attributes.get("autosac", default=False)

        if current:
            caller.attributes.add("autosac", False)
            caller.msg("|yAuto-Sacrifice: |rOFF|n")
        else:
            caller.attributes.add("autosac", True)
            caller.msg("|yAuto-Sacrifice: |gON|n")