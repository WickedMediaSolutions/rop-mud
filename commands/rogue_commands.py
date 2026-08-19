"""
Rogue Class Commands — Lockpicking & Poison System

Commands:
  picklock <target>      — Attempt to pick a lock on a door or container
  craftpoison <type>     — Craft a poison vial using ingredients
  applypoison [index]     — Coat your weapon with a poison vial
  poisons                 — List your poison vials and weapon poison status
  listpoisons             — List known poison recipes
  learnpoison <type>      — Learn a new poison recipe
  lockpicktool [quality]  — Check or upgrade your lockpick tool
"""

from commands.command import Command
from evennia import utils
from world.rogue_system import (
    attempt_lockpick, craft_poison, apply_poison_to_weapon,
    get_known_poisons, learn_poison_recipe, get_weapon_poison,
    POISON_RECIPES, LOCKPICK_QUALITY, get_lockpick_bonus,
)


class CmdPickLock(Command):
    """
    Attempt to pick a lock.

    Usage:
      picklock <direction>
      picklock <object>

    Only Rogues can pick locks. Success depends on your DEX, level,
    lockpick tool quality, and the lock's difficulty.

    Lockpicking has a 3-second cooldown between attempts.
    On critical failure or bad luck, your lockpick may break or degrade.
    """

    key = "picklock"
    aliases = ["pick"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        if not args:
            caller.msg("Usage: picklock <direction or object>")
            return

        # Try to find the target
        target = None
        lock_difficulty = "standard"

        # Check if it's an exit (direction)
        location = caller.location
        if hasattr(location, "exits"):
            for ex in location.exits:
                if ex.key.lower() == args.lower() or ex.aliases.get(args.lower(), False):
                    target = ex
                    break

        if not target:
            # Try to find an object in the room
            for obj in location.contents:
                if obj.key.lower() == args.lower() or (hasattr(obj, "aliases") and obj.aliases.get(args.lower(), False)):
                    target = obj
                    break

        if not target:
            caller.msg(f"You don't see '{args}' here to pick.")
            return

        # Determine lock difficulty from target attributes
        if hasattr(target, "attributes"):
            lock_difficulty = target.attributes.get("lock_difficulty", "standard")

        # Attempt lockpick
        success, msg = attempt_lockpick(caller, target, lock_difficulty)
        caller.msg(msg)

        if success:
            # Unlock the target
            if hasattr(target, "attributes"):
                target.attributes.add("locked", False)
            if hasattr(target, "locks"):
                if "locked:true()" in str(getattr(target, "locks", "")):
                    target.locks.add("traverse:true()")
            caller.location.msg_contents(
                f"|g*click*|n {caller.key} picks the lock on {target.key}.",
                exclude=[caller],
            )


class CmdCraftPoison(Command):
    """
    Craft a poison vial from ingredients.

    Usage:
      craftpoison <type>

    Available poison types depend on your level and known recipes.
    Use 'listpoisons' to see what you can craft.

    Crafting requires the listed ingredients and an INT-based skill check.
    On failure, ingredients are consumed but no poison is created.
    """

    key = "craftpoison"
    aliases = ["cpoison"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        if not args:
            caller.msg("Usage: craftpoison <type>")
            caller.msg("Available types: " + ", ".join(get_known_poisons(caller)))
            return

        success, msg = craft_poison(caller, args)
        caller.msg(msg)


class CmdApplyPoison(Command):
    """
    Coat your weapon with poison.

    Usage:
      applypoison [number]

    Applies a poison vial from your inventory to your equipped weapon.
    Valid vials are numbered starting at 1. If no number given, uses the first vial.

    Each application gives a limited number of charges. The poison effect
    applies on melee hits and deals damage over time.
    """

    key = "applypoison"
    aliases = ["applyp"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        index = 0
        if args:
            try:
                index = int(args) - 1  # Convert to 0-based
                if index < 0:
                    caller.msg("Poison vial number must be 1 or higher.")
                    return
            except ValueError:
                caller.msg("Usage: applypoison [number]")
                return

        success, msg = apply_poison_to_weapon(caller, index)
        caller.msg(msg)


class CmdListPoisons(Command):
    """
    List your poison vials and weapon poison status.

    Usage:
      poisons
    """

    key = "poisons"
    aliases = ["pstatus"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller

        if not hasattr(caller, "attributes"):
            caller.msg("You have no poison vials.")
            return

        vials = caller.attributes.get("poison_vials", default=[])
        output = []

        output.append("|c═══════ Poison Inventory ═══════|n")

        if vials:
            for i, vial in enumerate(vials, 1):
                output.append(
                    f"  {i}. |g{vial['name']}|n — {vial['damage_per_tick']} dmg/tick, "
                    f"{vial['duration']}s, {vial['charges']} charges"
                )
        else:
            output.append("  |y(no poison vials)|n")

        output.append("")

        # Weapon poison status
        weapon_poison = get_weapon_poison(caller)
        if weapon_poison:
            charges = caller.attributes.get("weapon_poison_charges", 0)
            output.append(
                f"  |rWeapon Coating:|n {weapon_poison['name']} — {charges} strikes remaining"
            )
        else:
            output.append("  |rWeapon Coating:|n None")

        caller.msg("\n".join(output))


class CmdListRecipes(Command):
    """
    List known poison recipes.

    Usage:
      listpoisons
    """

    key = "listpoisons"
    aliases = ["precipes"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        known = get_known_poisons(caller)

        output = ["|c═══════ Known Poison Recipes ═══════|n"]

        if not known:
            output.append("  |yYou don't know any poison recipes.|n")
        else:
            for key in known:
                recipe = POISON_RECIPES.get(key, {})
                if recipe:
                    output.append(
                        f"  |g{recipe['name']}|n (Lvl {recipe['min_level']}) — "
                        f"{recipe['damage_per_tick']} dmg/tick, {recipe['duration']}s"
                    )
                    output.append(f"    DC: {recipe['craft_dc']} | Ingredients: {', '.join(recipe['ingredients'])}")

        caller.msg("\n".join(output))


class CmdLearnPoison(Command):
    """
    Learn a new poison recipe.

    Usage:
      learnpoison <type>

    You must be high enough level to learn the recipe.
    """

    key = "learnpoison"
    aliases = ["lpoison"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        if not args:
            caller.msg("Usage: learnpoison <type>")
            caller.msg("Available types: " + ", ".join(POISON_RECIPES.keys()))
            return

        success, msg = learn_poison_recipe(caller, args)
        caller.msg(msg)


class CmdLockpickTool(Command):
    """
    Check or upgrade your lockpick tool.

    Usage:
      lockpicktool            — Check your current tool quality
      lockpicktool upgrade    — Attempt to upgrade (requires materials)

    Tool quality tiers: crude < standard < fine < masterwork < enchanted
    """

    key = "lockpicktool"
    aliases = ["lptool"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        if not hasattr(caller, "attributes"):
            caller.msg("You don't have a lockpick tool.")
            return

        current = caller.attributes.get("lockpick_quality", "standard")
        bonus = LOCKPICK_QUALITY.get(current, 0)
        total_bonus = get_lockpick_bonus(caller)

        if args == "upgrade":
            # Check if at max quality
            quality_order = ["crude", "standard", "fine", "masterwork", "enchanted"]
            idx = quality_order.index(current) if current in quality_order else 1
            if idx >= len(quality_order) - 1:
                caller.msg("Your lockpick tool is already at maximum quality.")
                return

            # Upgrade cost (simplified: gold cost)
            upgrade_cost = (idx + 1) * 50
            gold = caller.attributes.get("gold_coins", 0)
            if gold < upgrade_cost:
                caller.msg(f"Upgrading to {quality_order[idx + 1]} costs {upgrade_cost} gold. You have {gold}.")
                return

            caller.attributes.add("gold_coins", gold - upgrade_cost)
            caller.attributes.add("lockpick_quality", quality_order[idx + 1])
            caller.msg(f"You upgrade your lockpick to |g{quality_order[idx + 1]}|n quality! (Cost: {upgrade_cost} gold)")
            return

        caller.msg(f"|cLockpick Tool:|n {current.capitalize()} (Bonus: +{bonus})")
        caller.msg(f"|cTotal Lockpick Skill:|n +{total_bonus}")