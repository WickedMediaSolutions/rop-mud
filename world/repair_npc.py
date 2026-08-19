"""
Repair NPC System for 'rop'

Provides:
  - RepairNPC typeclass
  - repair_item() — restore durability for gold
  - CmdRepair command
"""

from typing import Tuple

from evennia.objects.objects import DefaultCharacter
from commands.command import Command


class RepairNPC(DefaultCharacter):
    """NPC that repairs damaged equipment for gold."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.repair_cost_per_point = 2  # Gold per durability point restored

    def repair_item(self, character, item_name: str) -> Tuple[bool, str]:
        """Repair an item, restoring durability to max."""
        for obj in character.contents:
            if getattr(obj, "destination", None):
                continue
            if obj.key.lower() == item_name.lower():
                max_dur = obj.attributes.get("max_durability", default=100) if hasattr(obj, "attributes") else 100
                current_dur = obj.attributes.get("durability", default=max_dur) if hasattr(obj, "attributes") else max_dur
                if current_dur >= max_dur:
                    return False, "That item is already at full durability."
                damage = max_dur - current_dur
                cost = damage * self.db.repair_cost_per_point
                gold = character.attributes.get("money", default=0) if hasattr(character, "attributes") else 0
                if gold < cost:
                    return False, f"You need {cost} gold (have {gold})."
                if hasattr(character, "attributes"):
                    character.attributes.add("money", gold - cost)
                if hasattr(obj, "attributes"):
                    obj.attributes.add("durability", max_dur)
                return True, f"Repaired {obj.key} for {cost} gold."
        return False, "You don't have that item."


class CmdRepair(Command):
    """Repair a damaged item at a repair NPC."""
    key = "repair"
    locks = "cmd:all()"
    help_category = "Commerce"

    def parse(self):
        self.target = self.args.strip()

    def func(self):
        caller = self.caller
        if not self.target:
            caller.msg("|yUsage: repair <item>|n")
            return

        location = caller.location
        if not location:
            return

        npc = None
        for obj in location.contents:
            if isinstance(obj, RepairNPC):
                npc = obj
                break

        if not npc:
            caller.msg("|yThere is no repair NPC here.|n")
            return

        ok, msg = npc.repair_item(caller, self.target)
        if ok:
            caller.msg(f"|g{msg}|n")
        else:
            caller.msg(f"|r{msg}|n")