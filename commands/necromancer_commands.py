"""
Necromancer Class Commands — Raise Undead Minions

Commands:
  raise <type>        — Raise an undead minion from a corpse
  dismiss [number]    — Dismiss a minion
  dismissall          — Dismiss all minions
  minions             — List your active minions
"""

from commands.command import Command
from evennia import utils
from world.necromancer_system import (
    raise_minion, dismiss_minion, dismiss_all_minions,
    get_active_minions, get_available_minion_types,
    get_minion_cap, MINION_TYPES,
)


class CmdRaiseMinion(Command):
    """
    Raise an undead minion from a corpse.

    Usage:
      raise <type>

    Available minion types (based on level):
      skeleton     (Lvl 1)  — Brittle skeletal warrior, slash damage
      zombie       (Lvl 4)  — Durable corpse, disease touch
      wraith       (Lvl 8)  — Ethereal spirit, life drain
      bone_golem   (Lvl 14) — Massive construct, cleave
      lich         (Lvl 20) — Undead spellcaster, shadow bolt

    Requires a corpse in the room and costs mana.
    You can control up to 1 minion per 2 levels (rounded up).
    """

    key = "raise"
    aliases = ["raiseminion"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        if not args:
            available = get_available_minion_types(caller)
            cap = get_minion_cap(caller)
            count = len(get_active_minions(caller))

            caller.msg("|c═══════ Raise Undead Minion ═══════|n")
            caller.msg(f"|cControl:|n {count}/{cap} minions")
            caller.msg("|cAvailable types:|n " + ", ".join(available) if available else "none")
            caller.msg("|cUsage: raise <type>|n")
            return

        success, msg = raise_minion(caller, args)
        caller.msg(msg)

        if success:
            caller.location.msg_contents(
                f"|w{caller.key} raises a {MINION_TYPES.get(args, {}).get('name', 'minion', )} from a corpse!|n",
                exclude=[caller],
            )


class CmdDismiss(Command):
    """
    Dismiss an undead minion.

    Usage:
      dismiss [number]

    Dismisses a specific minion by number (1-based) as shown in 'minions'.
    Without a number, dismisses the first minion.

    Use 'dismissall' to dismiss all minions at once.
    """

    key = "dismiss"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        index = 0
        if args:
            try:
                index = int(args) - 1
                if index < 0:
                    caller.msg("Minion number must be 1 or higher.")
                    return
            except ValueError:
                caller.msg("Usage: dismiss [number]")
                return

        success, msg = dismiss_minion(caller, index)
        caller.msg(msg)


class CmdDismissAll(Command):
    """
    Dismiss all undead minions.

    Usage:
      dismissall
    """

    key = "dismissall"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        success, msg = dismiss_all_minions(caller)
        caller.msg(msg)


class CmdMinions(Command):
    """
    List your active undead minions.

    Usage:
      minions

    Shows HP, damage, and special abilities of each active minion.
    """

    key = "minions"
    aliases = ["undead"]
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        minions = get_active_minions(caller)
        cap = get_minion_cap(caller)

        output = ["|c═══════ Undead Minions ═══════|n"]
        output.append(f"|cControl:|n {len(minions)}/{cap}")

        if not minions:
            output.append("  |yYou have no active minions.|n")
        else:
            for i, m in enumerate(minions, 1):
                hp_pct = int(m['hp'] / max(1, m['max_hp']) * 100)
                hp_color = "|g" if hp_pct > 50 else "|y" if hp_pct > 25 else "|r"

                output.append(f"  {i}. |w{m['name']}|n [{hp_color}{m['hp']}/{m['max_hp']} HP|n]")
                output.append(f"     DMG: {m['damage']} ({m['damage_type']}), ATK Speed: {m['attack_speed']}s")
                if m.get("special"):
                    special_desc = {
                        "disease_touch": "10% poison on hit",
                        "life_drain": "Heals master for 25% dmg",
                        "cleave": "20% AoE cleave",
                        "shadow_bolt": "Bonus magic damage",
                    }
                    output.append(f"     Special: |M{special_desc.get(m['special'], m['special'])}|n")

        caller.msg("\n".join(output))