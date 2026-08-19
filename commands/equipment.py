"""
Player Equipment Commands for 'rop'

Commands:
  wear <item>       - Equip a weapon/armor item from your inventory
  wield <item>      - Alias for wear
  equip <item>      - Alias for wear

  remove <item|slot>- Take off an equipped item
  unwield <item>    - Alias for remove

  equipment / eq    - Display a full paperdoll of equipped items
  inventory / i     - List inventory items with equipment slot info

  equipverify       - ADMIN: audit that every slot can equip/unequip
"""

from __future__ import annotations

from typing import Dict, List, Optional

from commands.command import Command


# ---------------------------------------------------------------------------
# Item classification helpers (best-effort, used for race/class gating)
# ---------------------------------------------------------------------------

def _classify_item_type(item) -> str:
    """
    Return an item_type string compatible with ``can_equip_slot`` gating.

    Returns '' when the item type cannot be determined (no gating applied).
    """
    if not hasattr(item, "attributes"):
        return ""

    explicit = item.attributes.get("item_type", default=None)
    if explicit and explicit not in ("equipment", "", None):
        return explicit

    if item.attributes.get("weapon_type", default=None):
        return f"weapon_{item.attributes.get('weapon_type')}"
    if item.attributes.get("armor_type", default=None):
        return f"armor_{item.attributes.get('armor_type')}"

    # Generic mob loot: damage => weapon, armor => armor.  We don't apply
    # weapon/armor proficiency restrictions to generic mob drops.
    return ""


def _tracked_item_names(character) -> Dict[str, str]:
    """
    Return a mapping of normalized equipped slot -> item name for a character.

    Uses the canonical slot map from ``world.mob_equipment`` so every
    downstream display and validation path reads consistent slot keys.
    """
    try:
        from world.mob_equipment import get_equipped_slot_map
        return get_equipped_slot_map(character)
    except Exception:
        raw = character.attributes.get("equipped", default={})
        if hasattr(raw, "items"):
            return {str(k): str(v) for k, v in raw.items()}
        return {}


def _is_equipped(character, item) -> bool:
    """Return True if the item's name is present in the equipped map."""
    if not hasattr(item, "key"):
        return False
    for name in _tracked_item_names(character).values():
        if str(name).lower() == str(item.key).lower():
            return True
    return False


# ---------------------------------------------------------------------------
# Equipment command set
# ---------------------------------------------------------------------------

class CmdWear(Command):
    """
    Equip an item from your inventory.

    Usage:
      wear <item>
      wield <item>
      equip <item>

    Wearing an item moves it into one of your equipment slots and applies
    its benefits (weapon damage, armor, or stat bonuses) in combat.
    """

    key = "wear"
    aliases = ["wield", "equip"]
    help_category = "Equipment"
    locks = "cmd:all()"

    def parse(self):
        self.target = self.args.strip()

    def func(self):
        caller = self.caller
        if not self.target:
            caller.msg("|yUsage: wear <item>|n")
            return

        from world.mob_equipment import find_item_in_inventory, get_item_slot, equip_item
        from world.race_class_matrix import can_equip_slot

        item = find_item_in_inventory(caller, self.target)
        if item is None:
            caller.msg(f"|rYou don't have '{self.target}'.|n")
            return

        slot = get_item_slot(item)
        if not slot:
            caller.msg(f"|r{item.key} cannot be equipped.|n")
            return

        # Race/class restriction check.
        item_type = _classify_item_type(item)
        if item_type:
            allowed, reason = can_equip_slot(caller, slot, item_type)
            if not allowed:
                caller.msg(f"|r{reason}|n")
                return

        success, message = equip_item(caller, item, slot)
        if success:
            caller.msg(f"|g{message}|n")
        else:
            caller.msg(f"|r{message}|n")


class CmdRemove(Command):
    """
    Remove an equipped item.

    Usage:
      remove <item>
      remove <slot>       (e.g. remove torso, remove right_hand)

    The item remains in your inventory after being removed.
    """

    key = "remove"
    aliases = ["unwield"]
    help_category = "Equipment"
    locks = "cmd:all()"

    def parse(self):
        self.target = self.args.strip().lower()

    def func(self):
        caller = self.caller
        if not self.target:
            caller.msg("|yUsage: remove <item|slot>|n")
            return

        from world.mob_equipment import unequip_item

        success, message = unequip_item(caller, self.target)
        if success:
            caller.msg(f"|g{message}|n")
        else:
            caller.msg(f"|r{message}|n")


class CmdEquipment(Command):
    """
    Display a full paperdoll of your currently equipped items.

    Usage:
      equipment
      eq
    """

    key = "equipment"
    aliases = ["eq"]
    help_category = "Equipment"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        try:
            from world.mob_equipment import build_paperdoll
            caller.msg(build_paperdoll(caller))
        except Exception:
            # Fallback: legacy list display
            self._legacy_display(caller)

    def _legacy_display(self, caller):
        from world.mob_equipment import get_equipped_slot_map, get_effective_armor

        equipped = get_equipped_slot_map(caller)
        if not equipped:
            caller.msg("|yYou are not wearing or wielding anything.|n")
            return

        lines = ["|w=== Your Equipment ===|n"]
        for slot, name in equipped.items():
            from world.mob_equipment import get_slot_display
            display = get_slot_display(slot)
            lines.append(f"  |c{display:<14}:|n {name}")
        lines.append(f"|wTotal Armor: |n{get_effective_armor(caller)}")
        caller.msg("\n".join(lines))


class CmdInventory(Command):
    """
    List all items you are carrying, marking equipped items.

    Usage:
      inventory
      i
    """

    key = "inventory"
    aliases = ["i", "inv"]
    help_category = "Equipment"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        items = [obj for obj in (getattr(caller, "contents", None) or [])
                 if not getattr(obj, "destination", None)]

        if not items:
            caller.msg("|yYou are not carrying anything.|n")
            return

        equipped_names = _tracked_item_names(caller)

        lines = ["|w=== Your Inventory ===|n"]
        for obj in items:
            if not hasattr(obj, "key"):
                continue
            # Determine slot (if any) from item attribute or equipped map
            slot = None
            if hasattr(obj, "attributes"):
                slot = obj.attributes.get("slot", default=None)

            equipped_slot = None
            for s, name in equipped_names.items():
                if str(name).lower() == str(obj.key).lower():
                    equipped_slot = s
                    break

            marker = ""
            if equipped_slot:
                from world.mob_equipment import get_slot_display
                marker = f" |g[equipped: {get_slot_display(equipped_slot)}]|n"
            elif slot:
                from world.mob_equipment import get_slot_display
                marker = f" |w[{get_slot_display(slot)}]|n"

            lines.append(f"  |w{obj.key}|n{marker}")

        caller.msg("\n".join(lines))


class CmdEquipmentVerify(Command):
    """
    Audit the equipment system by equipping/unequipping every slot.

    Usage:
      equipverify

    Admin only. Creates temporary test items, equips them into every
    canonical slot (including aura and dual-hand weapons), verifies the
    equipped map, then unequips and confirms slots are cleared.
    """

    key = "equipverify"
    aliases = ["verifyequipment", "eqverify"]
    help_category = "Admin"
    locks = "cmd:perm(Admin)"

    def func(self):
        caller = self.caller
        from world.mob_equipment import verify_all_equipment_slots

        caller.msg("|wRunning equipment slot audit...|n")
        results = verify_all_equipment_slots(caller)

        lines = []
        lines.append(
            f"|wEquipment Audit: |g{results['passes']} passed|w, "
            f"|r{results['failures']} failed|n"
        )
        for detail in results["details"]:
            if detail.startswith("PASS"):
                lines.append(f"  |g{detail}|n")
            else:
                lines.append(f"  |r{detail}|n")

        caller.msg("\n".join(lines))