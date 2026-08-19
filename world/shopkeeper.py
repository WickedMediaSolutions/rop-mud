"""
Shopkeeper & Vendor System for 'rop'

Provides:
  - ShopkeeperNPC typeclass
  - get_buy_price() / get_sell_price()
  - CmdBuy, CmdSell, CmdList (shop inventory), CmdAppraise commands
"""

from typing import Dict, List, Tuple

from evennia.objects.objects import DefaultCharacter
from commands.command import Command


# ---------------------------------------------------------------------------
# ShopkeeperHandler — convenience alias for external consumers
# ---------------------------------------------------------------------------


class ShopkeeperHandler:
    """Handler for shopkeeper-related operations (currency, pricing, etc.)."""
    pass


# ---------------------------------------------------------------------------
# Phase 4.4 — Currency Conversion
# ---------------------------------------------------------------------------

def convert_currency(gold: int) -> str:
    """
    Convert raw gold amount to a human-readable currency string.
    100 copper = 10 silver = 1 gold.
    """
    if gold <= 0:
        return "0 gold"
    g = gold
    s = g // 10
    c = g * 100
    parts = []
    if g > 0:
        parts.append(f"|Y{g} gold|n")
    if s > 0:
        parts.append(f"|w{s} silver|n")
    if c > 0:
        parts.append(f"|r{c} copper|n")
    return ", ".join(parts)


def parse_currency(amount_str: str) -> int:
    """
    Parse a currency string like '10g', '50s', '100c' into raw gold.
    Returns 0 if unparseable.
    """
    amount_str = amount_str.strip().lower()
    if not amount_str:
        return 0
    try:
        if amount_str.endswith("g"):
            return int(amount_str[:-1])
        elif amount_str.endswith("s"):
            return int(amount_str[:-1]) // 10
        elif amount_str.endswith("c"):
            return int(amount_str[:-1]) // 100
        else:
            return int(amount_str)
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Phase 4.4 — Item Durability Degradation
# ---------------------------------------------------------------------------

def degrade_item_durability(item, amount: int = 1) -> bool:
    """
    Degrade an item's durability by *amount* points.
    Returns True if the item broke (durability reached 0).
    """
    if not hasattr(item, "attributes"):
        return False
    durability = item.attributes.get("durability", default=None)
    max_durability = item.attributes.get("max_durability", default=None)
    if durability is None or max_durability is None:
        return False
    new_dur = max(0, durability - amount)
    item.attributes.add("durability", new_dur)
    return new_dur <= 0


class ShopkeeperNPC(DefaultCharacter):
    """NPC that buys/sells items. Inventory is stored as attributes."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.shop_inventory = []     # List of {"item_key": str, "price": int, "quantity": int}
        self.db.shop_buy_mult = 0.50    # Buys at 50% of item value
        self.db.shop_sell_mult = 1.20   # Sells at 120% of item value
        self.db.shop_type = "general"   # "general", "weapons", "armor", "magic", "potions"

    def get_buy_price(self, item, character=None) -> int:
        """
        Price the shop pays to buy an item from a player.
        Phase 4.4: Applies faction-based pricing modifier.
        """
        base_value = item.attributes.get("value", default=1) if hasattr(item, "attributes") else 1
        price = max(1, int(base_value * self.db.shop_buy_mult))
        if character:
            price = self._apply_faction_pricing(character, price, is_buying=True)
        return price

    def get_sell_price(self, item_key: str, character=None) -> int:
        """
        Price the shop charges to sell an item to a player.
        Phase 4.4: Applies faction-based pricing modifier.
        """
        for entry in self.db.shop_inventory:
            if entry["item_key"] == item_key:
                price = entry["price"]
                if character:
                    price = self._apply_faction_pricing(character, price, is_buying=False)
                return price
        return 0

    def _apply_faction_pricing(self, character, price: int, is_buying: bool = True) -> int:
        """
        Phase 4.4: Adjust price based on faction alignment match.
        Same faction: 10% discount (buying) / 10% bonus (selling).
        Opposite faction: 20% markup (buying) / 20% penalty (selling).
        """
        shop_align = self.attributes.get("alignment", default="") if hasattr(self, "attributes") else ""
        char_align = character.attributes.get("alignment", default="") if hasattr(character, "attributes") else ""
        if not shop_align or not char_align:
            return price
        if shop_align == char_align:
            if is_buying:
                return max(1, int(price * 1.10))
            else:
                return max(1, int(price * 0.90))
        else:
            if is_buying:
                return max(1, int(price * 0.80))
            else:
                return max(1, int(price * 1.20))

    def get_shop_inventory_display(self) -> List[Dict]:
        """Return formatted inventory list for display."""
        return self.db.shop_inventory

    def buy_item(self, character, item_key: str) -> Tuple[bool, str]:
        """Sell an item from shop inventory to a player."""
        for entry in self.db.shop_inventory:
            if entry["item_key"] == item_key:
                if entry.get("quantity", 0) <= 0:
                    return False, "That item is out of stock."
                price = entry["price"]
                gold = character.attributes.get("money", default=0) if hasattr(character, "attributes") else 0
                if gold < price:
                    return False, f"You need {price} gold (have {gold})."
                # Deduct gold
                if hasattr(character, "attributes"):
                    character.attributes.add("money", gold - price)
                # Reduce stock
                entry["quantity"] = entry.get("quantity", 1) - 1
                self.db.shop_inventory = self.db.shop_inventory  # trigger save
                # Create item and give to player
                from evennia import create_object
                from world.prototypes import ITEM_PROTOTYPES
                proto = ITEM_PROTOTYPES.get(item_key)
                if proto:
                    item = create_object(**proto)
                    item.location = character
                    return True, f"You buy {item.key} for {price} gold."
                return False, "Item prototype not found."
        return False, "That item is not sold here."

    def sell_item(self, character, item) -> Tuple[bool, str]:
        """Buy an item from a player."""
        price = self.get_buy_price(item)
        if price <= 0:
            return False, "This shop is not interested in that item."
        gold = character.attributes.get("money", default=0) if hasattr(character, "attributes") else 0
        if hasattr(character, "attributes"):
            character.attributes.add("money", gold + price)
        # Remove item from player
        item.delete()
        return True, f"You sell {item.key} for {price} gold."


# ---------------------------------------------------------------------------
# Shop Commands
# ---------------------------------------------------------------------------

class CmdBuy(Command):
    """Buy an item from a shopkeeper."""
    key = "buy"
    locks = "cmd:all()"
    help_category = "Commerce"

    def parse(self):
        self.target = self.args.strip()

    def func(self):
        caller = self.caller
        if not self.target:
            caller.msg("|yUsage: buy <item>|n")
            return

        location = caller.location
        if not location:
            return

        shop = None
        for obj in location.contents:
            if isinstance(obj, ShopkeeperNPC):
                shop = obj
                break

        if not shop:
            caller.msg("|yThere is no shopkeeper here.|n")
            return

        ok, msg = shop.buy_item(caller, self.target)
        if ok:
            caller.msg(f"|g{msg}|n")
        else:
            caller.msg(f"|r{msg}|n")


class CmdSell(Command):
    """Sell an item to a shopkeeper."""
    key = "sell"
    locks = "cmd:all()"
    help_category = "Commerce"

    def parse(self):
        self.target = self.args.strip()

    def func(self):
        caller = self.caller
        if not self.target:
            caller.msg("|yUsage: sell <item>|n")
            return

        location = caller.location
        if not location:
            return

        shop = None
        for obj in location.contents:
            if isinstance(obj, ShopkeeperNPC):
                shop = obj
                break

        if not shop:
            caller.msg("|yThere is no shopkeeper here.|n")
            return

        # Find item in inventory
        item = None
        for obj in caller.contents:
            if getattr(obj, "destination", None):
                continue
            if obj.key.lower() == self.target.lower():
                item = obj
                break

        if not item:
            caller.msg(f"|rYou don't have '{self.target}'.|n")
            return

        ok, msg = shop.sell_item(caller, item)
        if ok:
            caller.msg(f"|g{msg}|n")
        else:
            caller.msg(f"|r{msg}|n")


class CmdShopList(Command):
    """List items for sale at a shopkeeper."""
    key = "list"
    aliases = ["shop"]
    locks = "cmd:all()"
    help_category = "Commerce"

    def func(self):
        caller = self.caller
        location = caller.location
        if not location:
            return

        shop = None
        for obj in location.contents:
            if isinstance(obj, ShopkeeperNPC):
                shop = obj
                break

        if not shop:
            caller.msg("|yThere is no shopkeeper here.|n")
            return

        inventory = shop.get_shop_inventory_display()
        if not inventory:
            caller.msg(f"|y{shop.key} has nothing for sale right now.|n")
            return

        out = f"|w=== {shop.key} — Inventory ===|n\n"
        for entry in inventory:
            qty = entry.get("quantity", 0)
            if qty <= 0:
                continue
            out += f"  |c{entry['item_key']}|n — |Y{entry['price']} gold|n (x{qty})\n"
        caller.msg(out)


class CmdAppraise(Command):
    """Appraise an item to see its value."""
    key = "appraise"
    aliases = ["value"]
    locks = "cmd:all()"
    help_category = "Commerce"

    def parse(self):
        self.target = self.args.strip()

    def func(self):
        caller = self.caller
        if not self.target:
            caller.msg("|yUsage: appraise <item>|n")
            return

        # Find item in inventory
        item = None
        for obj in caller.contents:
            if getattr(obj, "destination", None):
                continue
            if obj.key.lower() == self.target.lower():
                item = obj
                break

        if not item:
            caller.msg(f"|rYou don't have '{self.target}'.|n")
            return

        value = item.attributes.get("value", default=0) if hasattr(item, "attributes") else 0
        caller.msg(f"|c{item.key}|n is worth approximately |Y{value} gold|n.")