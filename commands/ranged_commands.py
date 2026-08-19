"""
Ranged Combat Commands for 'rop'
================================
Provides shoot/fire, reload, and throw commands for ranged combat.

Usage:
  shoot <target>  — Fire a ranged weapon at a target
  fire <target>   — Alias for shoot
  reload          — Check ammo count
  throw <target>  — Throw a weapon at a target
"""

from commands.command import Command
from world.ranged_combat import (
    perform_ranged_attack,
    get_ranged_weapon,
    count_ammo,
    get_ammo_type_for_weapon,
    is_thrown_weapon,
    RangedCombatHandler,
    RANGED_ATTACK_COOLDOWN,
)
import time


class CmdShoot(Command):
    """
    Fire a ranged weapon at a target.

    Usage:
      shoot <target>
      fire <target>

    Requires a ranged weapon (bow, crossbow) to be equipped and
    the appropriate ammunition (arrows for bows, bolts for crossbows).

    Ranged attacks use DEX for accuracy and damage instead of STR.
    You get a first-strike bonus against targets not yet in combat.

    Ammo is consumed on each shot. You can recover some ammo from
    corpses after combat.
    """

    key = "shoot"
    aliases = ["fire"]
    locks = "cmd:all()"
    help_category = "Combat"
    auto_help = True

    def parse(self):
        self.target_name = self.args.strip() if self.args else ""

    def func(self):
        caller = self.caller

        if not self.target_name:
            caller.msg("|yUsage: shoot <target>|n")
            return

        # Check cooldown
        if not RangedCombatHandler.can_ranged_attack(caller):
            remaining = RANGED_ATTACK_COOLDOWN - (time.time() - RangedCombatHandler.get_last_ranged_attack(caller))
            caller.msg(f"|yYou must wait {remaining:.1f}s before firing again.|n")
            return

        # Find ranged weapon
        weapon_obj, weapon_type = get_ranged_weapon(caller)
        if weapon_type is None:
            caller.msg("|rYou don't have a ranged weapon equipped.|n")
            caller.msg("|yEquip a bow or crossbow first, then try again.|n")
            return

        # Check ammo for bows/crossbows
        ammo_type = get_ammo_type_for_weapon(weapon_type)
        if ammo_type:
            ammo_count = count_ammo(caller, ammo_type)
            if ammo_count <= 0:
                caller.msg(f"|rYou don't have any {ammo_type}s!|n")
                caller.msg(f"|yBuy {ammo_type}s from a shopkeeper or loot them from enemies.|n")
                return

        # Find target
        location = caller.location
        if not location:
            caller.msg("|rYou are nowhere; there is nothing to shoot.|n")
            return

        target = caller.search(
            self.target_name,
            candidates=location.contents,
            quiet=True,
        )

        if not target or len(target) == 0:
            caller.msg(f"|rYou don't see '{self.target_name}' here.|n")
            return

        target = target[0]

        # Perform the ranged attack
        result = perform_ranged_attack(caller, target, weapon_obj, weapon_type)
        RangedCombatHandler.set_last_ranged_attack(caller)

        # Send messages
        caller.msg(f"|c[Ranged]|n {result['message']}")

        if result["hit"]:
            # Room message
            crit_text = " |r*CRITICAL*|n" if result["crit"] else ""
            location.msg_contents(
                f"|c{caller.key} fires a {result['weapon_type']} at {target.key} "
                f"for {result['damage']} damage!{crit_text}|n",
                exclude=[caller, target],
            )
            # Target message
            if hasattr(target, "has_account") and target.has_account:
                target.msg(
                    f"|r{caller.key} shoots you with a {result['weapon_type']} "
                    f"for {result['damage']} damage!|n"
                )

            # Show remaining ammo
            if result.get("ammo_used"):
                remaining = count_ammo(caller, ammo_type) if ammo_type else 0
                if remaining <= 5 and remaining > 0:
                    caller.msg(f"|yAmmo remaining: {remaining} {ammo_type}(s)|n")
                elif remaining <= 0:
                    caller.msg(f"|rYou are out of {ammo_type}s!|n")

            # Enable ranged mode for tick-based auto-fire
            RangedCombatHandler.set_ranged_mode(caller, True)
            RangedCombatHandler.set_ranged_target(caller, target)


class CmdReload(Command):
    """
    Check your ammunition count for your equipped ranged weapon.

    Usage:
      reload

    Displays how many arrows or bolts you have remaining for your
    currently equipped ranged weapon.
    """

    key = "reload"
    aliases = ["ammo"]
    locks = "cmd:all()"
    help_category = "Combat"
    auto_help = True

    def func(self):
        caller = self.caller

        weapon_obj, weapon_type = get_ranged_weapon(caller)
        if weapon_type is None:
            caller.msg("|yYou don't have a ranged weapon equipped.|n")
            return

        ammo_type = get_ammo_type_for_weapon(weapon_type)
        if not ammo_type:
            caller.msg(f"|yYour {weapon_type} doesn't use ammunition.|n")
            return

        ammo_count = count_ammo(caller, ammo_type)
        if ammo_count > 0:
            caller.msg(f"|gYou have {ammo_count} {ammo_type}(s) remaining for your {weapon_type}.|n")
        else:
            caller.msg(f"|rYou are out of {ammo_type}s for your {weapon_type}!|n")
            caller.msg(f"|yVisit a shopkeeper to buy more {ammo_type}s.|n")


class CmdThrow(Command):
    """
    Throw a weapon at a target.

    Usage:
      throw <target>

    Throws a throwing weapon (throwing dagger, throwing axe, javelin)
    at the target. Thrown weapons land in the room and can be retrieved.

    Thrown weapons use DEX for accuracy and damage.
    """

    key = "throw"
    locks = "cmd:all()"
    help_category = "Combat"
    auto_help = True

    def parse(self):
        self.target_name = self.args.strip() if self.args else ""

    def func(self):
        caller = self.caller

        if not self.target_name:
            caller.msg("|yUsage: throw <target>|n")
            return

        # Check cooldown
        if not RangedCombatHandler.can_ranged_attack(caller):
            remaining = RANGED_ATTACK_COOLDOWN - (time.time() - RangedCombatHandler.get_last_ranged_attack(caller))
            caller.msg(f"|yYou must wait {remaining:.1f}s before throwing again.|n")
            return

        # Find a thrown weapon in inventory
        weapon_obj = None
        weapon_type = None
        for obj in caller.contents:
            if not obj or (hasattr(obj, "destination") and obj.destination):
                continue
            wt = ""
            if hasattr(obj, "attributes"):
                wt = obj.attributes.get("weapon_type", default="")
            if not wt and hasattr(obj, "db"):
                wt = obj.db.weapon_type or ""
            if is_thrown_weapon(obj):
                weapon_obj = obj
                weapon_type = wt
                break

        if weapon_type is None:
            caller.msg("|rYou don't have a throwable weapon.|n")
            caller.msg("|yThrowing daggers, throwing axes, and javelins can be thrown.|n")
            return

        # Find target
        location = caller.location
        if not location:
            caller.msg("|rYou are nowhere; there is nothing to throw at.|n")
            return

        target = caller.search(
            self.target_name,
            candidates=location.contents,
            quiet=True,
        )

        if not target or len(target) == 0:
            caller.msg(f"|rYou don't see '{self.target_name}' here.|n")
            return

        target = target[0]

        # Perform the ranged attack
        result = perform_ranged_attack(caller, target, weapon_obj, weapon_type)
        RangedCombatHandler.set_last_ranged_attack(caller)

        # Send messages
        caller.msg(f"|c[Throw]|n {result['message']}")

        if result["hit"]:
            crit_text = " |r*CRITICAL*|n" if result["crit"] else ""
            location.msg_contents(
                f"|c{caller.key} throws a {result['weapon_type']} at {target.key} "
                f"for {result['damage']} damage!{crit_text}|n",
                exclude=[caller, target],
            )
            if hasattr(target, "has_account") and target.has_account:
                target.msg(
                    f"|r{caller.key} throws a {result['weapon_type']} at you "
                    f"for {result['damage']} damage!|n"
                )