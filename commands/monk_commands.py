"""
Monk Class Commands — Ki Power System

Commands:
  flurry [target]     — Spend ki for 3 rapid strikes
  stunningstrike [t]  — Spend ki for a stunning hit
  chiheal              — Spend ki to heal wounds
  tigerpalm [target]  — Powerful strike, builds combo
  dragonkick [target] — Finisher, consumes combo points
  serenity             — Full ki restore + dodge buff
  meditate             — Accelerated ki regeneration
  ki                   — Display ki pool and combo status
"""

from commands.command import Command
from evennia import utils
from world.monk_system import (
    use_flurry, use_stunning_strike, use_chi_heal,
    use_tiger_palm, use_dragon_kick, use_serenity,
    get_current_ki, get_max_ki, get_combo_points,
    get_unarmed_damage, get_passive_dodge_bonus,
    MAX_COMBO_POINTS, KI_ABILITIES,
)


class CmdKi(Command):
    """
    Display your ki pool and combo point status.

    Usage:
      ki

    Shows current ki, max ki, combo points, unarmed damage,
    and passive dodge bonus.
    """

    key = "ki"
    aliases = ["kipool"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        current = get_current_ki(caller)
        max_ki = get_max_ki(caller)
        combo = get_combo_points(caller)
        unarmed = get_unarmed_damage(caller)
        dodge = get_passive_dodge_bonus(caller)

        ki_pct = int(current / max(1, max_ki) * 100)
        ki_color = "|g" if ki_pct > 50 else "|y" if ki_pct > 25 else "|r"

        output = [
            "|c═══════ Monk Ki Status ═══════|n",
            f"  Ki: {ki_color}{current}/{max_ki}|n ({ki_pct}%)",
            f"  Combo: |Y{combo}/{MAX_COMBO_POINTS}|n",
            f"  Unarmed DMG: {unarmed}",
            f"  Passive Dodge: +{dodge:.1f}%",
            "",
            "|cKi Abilities:|n",
        ]

        for key, ability in KI_ABILITIES.items():
            output.append(f"  |g{key.lower()}|n (Lvl {ability['min_level']}, {ability['ki_cost']} ki): {ability['description']}")

        caller.msg("\n".join(output))


class CmdFlurry(Command):
    """
    Unleash a flurry of blows.

    Usage:
      flurry [target]

    Performs 3 rapid unarmed strikes (70% damage each) against your target.
    Builds 1 combo point. 6s cooldown.
    """

    key = "flurry"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        target = _get_target(caller, self.args)
        if target is None:
            caller.msg("Who do you want to flurry?")
            return
        success, msg = use_flurry(caller, target)
        caller.msg(msg)


class CmdStunningStrike(Command):
    """
    A precise strike that can stun.

    Usage:
      stunningstrike [target]

    30% chance to stun target for 4s. Builds 1 combo point. 12s cooldown.
    """

    key = "stunningstrike"
    aliases = ["stun"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        target = _get_target(caller, self.args)
        if target is None:
            caller.msg("Strike who?")
            return
        success, msg = use_stunning_strike(caller, target)
        caller.msg(msg)


class CmdChiHeal(Command):
    """
    Channel ki to heal wounds.

    Usage:
      chiheal

    Heals 20% of your max HP. 15s cooldown.
    """

    key = "chiheal"
    aliases = ["chi"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        success, msg = use_chi_heal(caller)
        caller.msg(msg)


class CmdTigerPalm(Command):
    """
    A powerful open-palm strike.

    Usage:
      tigerpalm [target]

    Deals 150% unarmed damage and builds 2 combo points. 8s cooldown.
    """

    key = "tigerpalm"
    aliases = ["tp"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        target = _get_target(caller, self.args)
        if target is None:
            caller.msg("Strike who?")
            return
        success, msg = use_tiger_palm(caller, target)
        caller.msg(msg)


class CmdDragonKick(Command):
    """
    A devastating kick finisher.

    Usage:
      dragonkick [target]

    Requires 3 combo points. Consumes all combo points for +30% damage each.
    20s cooldown.
    """

    key = "dragonkick"
    aliases = ["dk"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        target = _get_target(caller, self.args)
        if target is None:
            caller.msg("Kick who?")
            return
        success, msg = use_dragon_kick(caller, target)
        caller.msg(msg)


class CmdSerenity(Command):
    """
    Enter a state of perfect focus.

    Usage:
      serenity

    Fully restores ki and grants +50% dodge for 10 seconds. 60s cooldown.
    """

    key = "serenity"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        success, msg = use_serenity(caller)
        caller.msg(msg)

        if success:
            caller.location.msg_contents(
                f"|c{caller.key} enters a state of serene focus!|n",
                exclude=[caller],
            )


class CmdMeditateMonk(Command):
    """
    Enter meditation to accelerate ki regeneration.

    Usage:
      meditatemonk

    While meditating, ki regenerates 3x faster. You cannot act while meditating.
    Use 'stand' to stop meditating.
    """

    key = "meditatemonk"
    aliases = ["monkmed"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller

        if not hasattr(caller, "attributes"):
            return

        current_pos = caller.attributes.get("position", default="standing")
        if current_pos == "meditating":
            caller.msg("You are already meditating.")
            return

        caller.attributes.add("position", "meditating")
        caller.msg("|cYou settle into a meditative trance. Ki regeneration accelerated 3x.|n")
        caller.msg("|yUse 'stand' to stop meditating.|n")
        caller.location.msg_contents(
            f"|c{caller.key} sits down and begins meditating.|n",
            exclude=[caller],
        )


def _get_target(caller, args):
    """Resolve a target from args or current combat target."""
    args = (args or "").strip()
    if args:
        target = caller.search(args)
        if target:
            return target[0] if isinstance(target, list) else target

    # Fall back to combat target
    try:
        from world.tick_combat import CombatHandler
        return CombatHandler.get_target(caller)
    except Exception:
        pass

    return None