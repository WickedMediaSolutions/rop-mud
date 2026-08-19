"""
Enchanter NPC System for 'rop'
==============================

Provides:
  - EnchanterNPC typeclass — NPC that upgrades item rarity for gold
  - CmdEnchant command — enchant <item>
  - get_item_rarity() / upgrade_item_rarity() — standalone helpers

Upgrade paths:
  Common → Uncommon (costs 50 gold)
  Uncommon → Rare (costs 150 gold)
  Rare → Epic (costs 400 gold)
  Epic → Legendary (costs 1000 gold)

Each upgrade scales the item's damage/armor and value by the rarity multiplier,
and adds the appropriate rarity label and color prefix to the item name.
"""

from __future__ import annotations

from typing import Tuple

from world.mob_equipment import RARITY_TIERS

# ---------------------------------------------------------------------------
# Lazy Evennia imports — same pattern as mob_equipment.py
# ---------------------------------------------------------------------------

# Command class (for CmdEnchant)
_BaseCommand = None

def _get_base_command():
    """Lazy-load Command to avoid import errors in test environments."""
    global _BaseCommand
    if _BaseCommand is None:
        try:
            from commands.command import Command as BC
            _BaseCommand = BC
        except ImportError:
            _BaseCommand = object
    return _BaseCommand


# DefaultCharacter (for EnchanterNPC)
_DefaultCharacter = None


def _get_default_character():
    """Lazy-load DefaultCharacter to avoid import errors in test environments."""
    global _DefaultCharacter
    if _DefaultCharacter is None:
        try:
            from evennia.objects.objects import DefaultCharacter as DC
            _DefaultCharacter = DC
        except ImportError:
            # Return a fallback base for test environments
            _DefaultCharacter = object
    return _DefaultCharacter


# Ordered rarity progression
RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]

# Gold cost to upgrade to each tier
UPGRADE_COSTS = {
    "uncommon":  50,
    "rare":     150,
    "epic":     400,
    "legendary": 1000,
}


def get_item_rarity(item) -> str:
    """
    Return the rarity of an item, defaulting to 'common'.
    Checks the _rarity attribute stored at item creation time.
    """
    if not hasattr(item, "attributes"):
        return "common"
    stored = item.attributes.get("_rarity", default="common")
    return stored if stored else "common"


def upgrade_item_rarity(item, target_rarity: str) -> bool:
    """
    Apply the rarity upgrade to an item in-place.

    Args:
        item: The item object.
        target_rarity: The target rarity ('uncommon', 'rare', 'epic', 'legendary').

    Returns:
        True on success, False if upgrade not valid.
    """
    if not hasattr(item, "attributes"):
        return False

    current = get_item_rarity(item)
    if target_rarity not in RARITY_ORDER:
        return False
    if current not in RARITY_ORDER:
        return False
    if RARITY_ORDER.index(target_rarity) <= RARITY_ORDER.index(current):
        return False

    rarity_info = RARITY_TIERS.get(target_rarity, RARITY_TIERS["common"])
    current_info = RARITY_TIERS.get(current, RARITY_TIERS["common"])

    # Compute multiplier relative to current
    old_mult = current_info["mult"]
    new_mult = rarity_info["mult"]
    relative_mult = new_mult / old_mult if old_mult > 0 else new_mult

    # Scale damage
    dmg = item.attributes.get("damage", default=0)
    if dmg > 0:
        item.attributes.add("damage", max(1, int(dmg * relative_mult)))

    # Scale armor
    armor = item.attributes.get("armor", default=0)
    if armor > 0:
        item.attributes.add("armor", max(1, int(armor * relative_mult)))

    # Scale value
    value = item.attributes.get("value", default=1)
    item.attributes.add("value", max(1, int(value * relative_mult)))

    # Update rarity attributes
    item.attributes.add("_rarity", target_rarity)
    item.attributes.add("_rarity_color", rarity_info["color"])

    # Update the item's key to reflect new rarity
    label = rarity_info["label"]
    color = rarity_info["color"]
    name = str(item.key)
    # Strip existing rarity/color prefixes
    for old_rarity in RARITY_ORDER:
        old_info = RARITY_TIERS.get(old_rarity, {})
        old_color = old_info.get("color", "")
        old_label = old_info.get("label", "")
        if old_color and old_label:
            prefix = f"{old_color}{old_label} "
            if name.startswith(prefix):
                name = name[len(prefix):]
        # Also strip the closing ANSI
        if "|n" in name:
            name = name.replace("|n", "")
        # Strip plain text label (no color)
        plain_prefix = f"{old_label} "
        if name.startswith(plain_prefix):
            name = name[len(plain_prefix):]

    item.key = f"{color}{label} {name.strip()}|n"

    return True


# ---------------------------------------------------------------------------
# EnchanterNPC typeclass
# ---------------------------------------------------------------------------

class EnchanterNPC(_get_default_character()):
    """NPC that upgrades item rarity for gold."""

    def at_object_creation(self):
        if hasattr(super(), "at_object_creation"):
            super().at_object_creation()
        self.db.is_enchanter = True

    def enchant_item(self, character, item_name: str) -> Tuple[bool, str]:
        """
        Upgrade an item to the next rarity tier.

        Args:
            character: The player character.
            item_name: Name of the item to enchant.

        Returns:
            (success, message) tuple.
        """
        # Find the item
        for obj in character.contents:
            if getattr(obj, "destination", None):
                continue
            if obj.key.lower() == item_name.lower():
                current = get_item_rarity(obj)
                if current not in RARITY_ORDER:
                    return False, "That item cannot be enchanted."

                idx = RARITY_ORDER.index(current)
                if idx >= len(RARITY_ORDER) - 1:
                    return False, "That item is already at maximum rarity."

                target = RARITY_ORDER[idx + 1]
                cost = UPGRADE_COSTS.get(target, 999999)

                from world.economy import get_money, remove_money
                gold = get_money(character)
                if gold < cost:
                    return False, f"You need {cost} gold to enchant this item (have {gold})."

                if not remove_money(character, cost):
                    return False, f"You need {cost} gold to enchant this item."

                if not upgrade_item_rarity(obj, target):
                    return False, "Failed to upgrade the item."

                return True, f"You enchant {obj.key}! It is now |g{target.upper()}|n. Cost: {cost} gold."

        return False, "You don't have that item."


class CmdEnchant(_get_base_command()):
    """
    Upgrade an item's rarity at an Enchanter NPC.

    Usage:
      enchant <item>

    Enchanting increases an item's rarity tier, scaling its stats.
    You must be in the same room as an Enchanter NPC.

    Costs:
      Uncommon: 50 gold
      Rare: 150 gold
      Epic: 400 gold
      Legendary: 1000 gold
    """

    key = "enchant"
    aliases = ["upgrade"]
    locks = "cmd:all()"
    help_category = "Commerce"

    def parse(self):
        self.target = self.args.strip()

    def func(self):
        caller = self.caller
        if not self.target:
            caller.msg("|yUsage: enchant <item>|n")
            return

        location = caller.location
        if not location:
            return

        npc = None
        for obj in location.contents:
            if isinstance(obj, EnchanterNPC):
                npc = obj
                break

        if not npc:
            caller.msg("|yThere is no enchanter here.|n")
            return

        ok, msg = npc.enchant_item(caller, self.target)
        if ok:
            caller.msg(f"|g{msg}|n")
            caller.location.msg_contents(
                f"|m{caller.key} enchants an item at {npc.key}.|n",
                exclude=[caller],
            )
        else:
            caller.msg(f"|r{msg}|n")