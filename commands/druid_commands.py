"""
Druid Class Commands — Shapeshifting System

Commands:
  shift <form>     — Transform into an animal form
  revert            — Return to humanoid form
  forms             — List available shapeshift forms
"""

from commands.command import Command
from evennia import utils
from world.druid_system import (
    shapeshift, revert, get_available_forms,
    get_current_form, get_form_bonuses,
    SHAPESHIFT_FORMS,
)


class CmdShift(Command):
    """
    Transform into an animal form.

    Usage:
      shift <form>

    Available forms (based on level):
      wolf    (Lvl 1)  — Swift hunter, +DEX, +STR, +move speed
      bear    (Lvl 8)  — Mighty bruiser, +STR, +CON, +AC, +max HP
      cat     (Lvl 12) — Nimble predator, +DEX, +dodge, +crit
      eagle   (Lvl 16) — Evasion master, +DEX, +WIS, +dodge
      treant  (Lvl 20) — Living fortress, +STR, +CON, +AC, +max HP

    Each form costs mana. Use 'revert' to return to normal.
    Use 'forms' to see your available forms.
    """

    key = "shift"
    aliases = ["shapeshift"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        if not args:
            # Show available forms
            available = get_available_forms(caller)
            if not available:
                caller.msg("You don't have any shapeshift forms available.")
                return

            current = get_current_form(caller)
            caller.msg("|c═══════ Available Shapeshift Forms ═══════|n")
            for form_key in available:
                form_data = SHAPESHIFT_FORMS.get(form_key, {})
                marker = "|g[ACTIVE]|n" if current == form_key else ""
                caller.msg(
                    f"  |g{form_key.lower()}|n (Lvl {form_data.get('min_level', 1)}) "
                    f"— {form_data.get('description', '')} {marker}"
                )
            caller.msg("|cUsage: shift <form>|n")
            return

        success, msg = shapeshift(caller, args)
        caller.msg(msg)

        if success:
            caller.location.msg_contents(
                f"|g{caller.key} shifts into {SHAPESHIFT_FORMS.get(args, {}).get('name', args)}!|n",
                exclude=[caller],
            )


class CmdRevert(Command):
    """
    Return to your natural humanoid form.

    Usage:
      revert

    Reverts any active shapeshift form, restoring your original stats,
    HP maximum, and armor.
    """

    key = "revert"
    aliases = ["unshift"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        success, msg = revert(caller)
        caller.msg(msg)

        if success:
            caller.location.msg_contents(
                f"|y{caller.key} reverts to natural form.|n",
                exclude=[caller],
            )


class CmdForms(Command):
    """
    List available shapeshift forms and their bonuses.

    Usage:
      forms

    Shows all forms you can currently use based on your level,
    along with their stat modifiers and descriptions.
    """

    key = "forms"
    aliases = ["druidforms"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        available = get_available_forms(caller)
        current = get_current_form(caller)

        output = ["|c═══════ Druid Shapeshift Forms ═══════|n"]

        if not available:
            output.append("  |yNo forms available. You must be level 1+ Druid.|n")
        else:
            for form_key in available:
                form_data = SHAPESHIFT_FORMS.get(form_key, {})
                marker = "|g<< ACTIVE >>|n" if current == form_key else ""
                stat_mods = form_data.get("stat_mods", {})
                stat_str = ", ".join(
                    f"{k.upper()}: {'+' if v > 0 else ''}{v}"
                    for k, v in stat_mods.items() if v != 0
                )

                output.append(f"  |g{form_data['name']}|n (Lvl {form_data['min_level']}, {form_data['mana_cost']} mana) {marker}")
                if stat_str:
                    output.append(f"    Stats: {stat_str}")
                if form_data.get("armor_bonus"):
                    output.append(f"    AC: +{form_data['armor_bonus']}")
                if form_data.get("max_hp_pct"):
                    output.append(f"    Max HP: {form_data['max_hp_pct']:+d}%")
                if form_data.get("melee_dmg_pct"):
                    output.append(f"    Melee DMG: +{form_data['melee_dmg_pct']}%")
                if form_data.get("dodge_pct"):
                    output.append(f"    Dodge: {form_data['dodge_pct']:+d}%")
                if form_data.get("crit_chance_pct"):
                    output.append(f"    Crit: +{form_data['crit_chance_pct']}%")
                output.append("")

        caller.msg("\n".join(output))