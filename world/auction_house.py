"""
Auction House / Trading Post System for 'rop'
==============================================

Provides:
  - AuctionHouse global singleton — stores all active listings
  - AuctionListing — data class for a single listing
  - CmdAuction — player command: auction <list|sell|buy|cancel|search>
  - CmdAuctionHouse — alias: ah

Features:
  - Players can list items for sale at a set price
  - Players can browse active listings
  - Players can buy items directly (gold deducted, item transferred)
  - Sellers can cancel their own listings
  - Listings persist across server restarts via Evennia attributes
  - 10% auction house fee on sales (configurable)
  - Maximum 10 active listings per player
  - Listings expire after 7 days

Usage:
  auction list              — Browse all active listings
  auction sell <item> <price> — List an item for sale
  auction buy <id>          — Purchase a listing by ID
  auction cancel <id>       — Cancel your own listing
  auction search <keyword>  — Search listings by name
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AUCTION_FEE_PCT = 0.10          # 10% fee on sale price
MAX_LISTINGS_PER_PLAYER = 10    # Max active listings per character
LISTING_EXPIRY_SECONDS = 604800  # 7 days

# ---------------------------------------------------------------------------
# Lazy Evennia imports
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Auction Listing Data Class
# ---------------------------------------------------------------------------

class AuctionListing:
    """
    Represents a single item listed for sale on the auction house.

    Attributes:
        listing_id: Unique integer ID for this listing.
        seller_key: The character key (name) of the seller.
        seller_dbref: The dbref of the seller character.
        item_key: The name/key of the item being sold.
        item_data: Serialized item attributes for reconstruction.
        price: Asking price in gold.
        created_at: Unix timestamp when the listing was created.
        expires_at: Unix timestamp when the listing expires.
    """

    def __init__(
        self,
        listing_id: int,
        seller_key: str,
        seller_dbref: str,
        item_key: str,
        item_data: Dict[str, Any],
        price: int,
        created_at: Optional[float] = None,
        expires_at: Optional[float] = None,
    ):
        self.listing_id = listing_id
        self.seller_key = seller_key
        self.seller_dbref = seller_dbref
        self.item_key = item_key
        self.item_data = item_data
        self.price = price
        self.created_at = created_at or time.time()
        self.expires_at = expires_at or (self.created_at + LISTING_EXPIRY_SECONDS)

    @property
    def is_expired(self) -> bool:
        """Check if this listing has passed its expiry time."""
        return time.time() > self.expires_at

    @property
    def time_remaining(self) -> str:
        """Human-readable time remaining string."""
        remaining = max(0, self.expires_at - time.time())
        if remaining <= 0:
            return "Expired"
        days = int(remaining // 86400)
        hours = int((remaining % 86400) // 3600)
        if days > 0:
            return f"{days}d {hours}h"
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def serialize(self) -> Dict[str, Any]:
        """Convert to a dict for storage in Evennia attributes."""
        return {
            "listing_id": self.listing_id,
            "seller_key": self.seller_key,
            "seller_dbref": self.seller_dbref,
            "item_key": self.item_key,
            "item_data": self.item_data,
            "price": self.price,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "AuctionListing":
        """Restore an AuctionListing from stored data."""
        return cls(
            listing_id=data["listing_id"],
            seller_key=data["seller_key"],
            seller_dbref=data["seller_dbref"],
            item_key=data["item_key"],
            item_data=data["item_data"],
            price=data["price"],
            created_at=data.get("created_at"),
            expires_at=data.get("expires_at"),
        )

    def __repr__(self):
        return f"<AuctionListing #{self.listing_id} '{self.item_key}' @ {self.price}g by {self.seller_key}>"


# ---------------------------------------------------------------------------
# Auction House Singleton
# ---------------------------------------------------------------------------

class AuctionHouse:
    """
    Global auction house manager.

    Stores all active listings and provides methods for listing,
    buying, cancelling, and searching.  Listings are persisted via
    Evennia's GlobalScript attributes so they survive server restarts.

    Usage:
        ah = AuctionHouse()
        listing_id = ah.list_item(seller, item, price)
        ah.buy_item(buyer, listing_id)
        ah.cancel_listing(seller, listing_id)
        listings = ah.get_active_listings()
    """

    # Global script reference (set during server init)
    _global_script = None

    def __init__(self):
        self._next_id = 1

    # ---- Internal helpers ----

    def _get_storage(self) -> Dict[int, Dict[str, Any]]:
        """Load the listings dict from the global script, or return empty dict."""
        if AuctionHouse._global_script is None:
            return {}
        raw = AuctionHouse._global_script.attributes.get(
            "auction_listings", default={}
        )
        return raw if raw else {}

    def _save_storage(self, data: Dict[int, Dict[str, Any]]) -> None:
        """Persist the listings dict to the global script."""
        if AuctionHouse._global_script is not None:
            AuctionHouse._global_script.attributes.add("auction_listings", data)

    def _get_next_id(self) -> int:
        """Get the next available listing ID and persist it."""
        if AuctionHouse._global_script is not None:
            next_id = AuctionHouse._global_script.attributes.get(
                "auction_next_id", default=1
            )
            AuctionHouse._global_script.attributes.add("auction_next_id", next_id + 1)
            return next_id
        # Fallback for test environments
        nid = self._next_id
        self._next_id += 1
        return nid

    def _serialize_item(self, item: Any) -> Dict[str, Any]:
        """
        Extract relevant attributes from an item for storage.
        The actual item is moved to a holding room until sold or cancelled.
        """
        data = {
            "key": str(item.key),
            "damage": 0,
            "armor": 0,
            "value": 1,
            "rarity": "common",
            "rarity_color": "|w",
            "durability": 100,
            "max_durability": 100,
        }
        if hasattr(item, "attributes"):
            data["damage"] = item.attributes.get("damage", default=0) or 0
            data["armor"] = item.attributes.get("armor", default=0) or 0
            data["value"] = item.attributes.get("value", default=1) or 1
            data["rarity"] = item.attributes.get("_rarity", default="common") or "common"
            data["rarity_color"] = item.attributes.get("_rarity_color", default="|w") or "|w"
            data["durability"] = item.attributes.get("durability", default=100) or 100
            data["max_durability"] = item.attributes.get("max_durability", default=100) or 100
        return data

    def _recreate_item(self, item_data: Dict[str, Any]) -> Any:
        """
        Recreate an item object from stored data.
        Returns the created item, or None on failure.
        """
        try:
            from evennia import create_object
            item = create_object(
                key=item_data.get("key", "Unknown Item"),
                typeclass="typeclasses.objects.Object",
            )
            if hasattr(item, "attributes"):
                item.attributes.add("damage", item_data.get("damage", 0))
                item.attributes.add("armor", item_data.get("armor", 0))
                item.attributes.add("value", item_data.get("value", 1))
                item.attributes.add("_rarity", item_data.get("rarity", "common"))
                item.attributes.add("_rarity_color", item_data.get("rarity_color", "|w"))
                item.attributes.add("durability", item_data.get("durability", 100))
                item.attributes.add("max_durability", item_data.get("max_durability", 100))
            return item
        except Exception:
            return None

    def _get_holding_room(self) -> Any:
        """
        Get or create the auction holding room where listed items are stored.
        Items sit here until sold or the listing is cancelled.
        """
        from evennia import search_object
        rooms = search_object("auction_holding_room")
        if rooms:
            return rooms[0]
        # Create the holding room if it doesn't exist
        from evennia import create_object
        room = create_object(
            key="auction_holding_room",
            typeclass="typeclasses.rooms.Room",
        )
        # Make it inaccessible to players
        room.db.desc = "A secure vault for auction items. Players cannot enter."
        return room

    # ---- Public API ----

    def get_active_listings(self) -> List[AuctionListing]:
        """
        Return all non-expired listings, sorted by listing ID.
        Automatically cleans up expired listings.
        """
        storage = self._get_storage()
        active = []
        expired_ids = []

        for lid, data in storage.items():
            listing = AuctionListing.deserialize(data)
            if listing.is_expired:
                expired_ids.append(lid)
            else:
                active.append(listing)

        # Clean up expired listings
        if expired_ids:
            for lid in expired_ids:
                del storage[lid]
            self._save_storage(storage)

        active.sort(key=lambda x: x.listing_id)
        return active

    def get_player_listings(self, seller_dbref: str) -> List[AuctionListing]:
        """Return all active listings for a specific seller."""
        all_listings = self.get_active_listings()
        return [l for l in all_listings if l.seller_dbref == seller_dbref]

    def get_player_listing_count(self, seller_dbref: str) -> int:
        """Return the number of active listings for a seller."""
        return len(self.get_player_listings(seller_dbref))

    def list_item(self, seller: Any, item: Any, price: int) -> Tuple[bool, str]:
        """
        List an item for sale on the auction house.

        Args:
            seller: The character listing the item.
            item: The item object to list.
            price: Asking price in gold.

        Returns:
            (success, message) tuple.
        """
        # Validate price
        if price < 1:
            return False, "Price must be at least 1 gold."

        # Check listing limit
        seller_dbref = str(seller.dbref) if hasattr(seller, "dbref") else str(seller.id)
        current_count = self.get_player_listing_count(seller_dbref)
        if current_count >= MAX_LISTINGS_PER_PLAYER:
            return False, (
                f"You already have {current_count} active listings "
                f"(max {MAX_LISTINGS_PER_PLAYER}). Cancel some first."
            )

        # Serialize item data
        item_data = self._serialize_item(item)

        # Create listing
        listing_id = self._get_next_id()
        listing = AuctionListing(
            listing_id=listing_id,
            seller_key=str(seller.key),
            seller_dbref=seller_dbref,
            item_key=str(item.key),
            item_data=item_data,
            price=price,
        )

        # Move item to holding room
        holding_room = self._get_holding_room()
        try:
            item.move_to(holding_room, quiet=True)
        except Exception:
            # Fallback: just set location
            item.location = holding_room

        # Store listing
        storage = self._get_storage()
        storage[listing_id] = listing.serialize()
        self._save_storage(storage)

        return True, (
            f"|gListed '{item.key}' for {price} gold. "
            f"Listing ID: #{listing_id}. "
            f"A {int(AUCTION_FEE_PCT * 100)}% fee will be deducted when sold.|n"
        )

    def buy_item(self, buyer: Any, listing_id: int) -> Tuple[bool, str]:
        """
        Purchase a listed item.

        Args:
            buyer: The character buying the item.
            listing_id: The ID of the listing to purchase.

        Returns:
            (success, message) tuple.
        """
        storage = self._get_storage()
        data = storage.get(listing_id)
        if not data:
            return False, "Listing not found."

        listing = AuctionListing.deserialize(data)

        if listing.is_expired:
            del storage[listing_id]
            self._save_storage(storage)
            return False, "That listing has expired."

        # Can't buy your own listing
        buyer_dbref = str(buyer.dbref) if hasattr(buyer, "dbref") else str(buyer.id)
        if buyer_dbref == listing.seller_dbref:
            return False, "You cannot buy your own listing."

        # Check buyer has enough gold
        from world.economy import get_money, remove_money, add_money
        buyer_gold = get_money(buyer)
        if buyer_gold < listing.price:
            return False, (
                f"You need {listing.price} gold to buy this item "
                f"(you have {buyer_gold})."
            )

        # Calculate fee
        fee = max(1, int(listing.price * AUCTION_FEE_PCT))
        seller_proceeds = listing.price - fee

        # Deduct gold from buyer
        if not remove_money(buyer, listing.price):
            return False, "Failed to deduct gold."

        # Find the item in the holding room and transfer to buyer
        holding_room = self._get_holding_room()
        item_found = None
        for obj in holding_room.contents:
            if obj.key == listing.item_key:
                item_found = obj
                break

        if item_found:
            try:
                item_found.move_to(buyer, quiet=True)
            except Exception:
                item_found.location = buyer
        else:
            # Item was lost — recreate from stored data
            item_found = self._recreate_item(listing.item_data)
            if item_found:
                item_found.location = buyer
            else:
                # Refund buyer if item can't be recreated
                add_money(buyer, listing.price)
                return False, "Failed to locate or recreate the item. Gold refunded."

        # Credit seller
        try:
            from evennia import search_object
            sellers = search_object(listing.seller_dbref)
            if sellers:
                seller = sellers[0]
                add_money(seller, seller_proceeds)
                seller.msg(
                    f"|g[Auction] Your listing '{listing.item_key}' sold for "
                    f"{listing.price} gold! You receive {seller_proceeds} gold "
                    f"after a {fee} gold fee.|n"
                )
        except Exception:
            pass

        # Remove listing from storage
        del storage[listing_id]
        self._save_storage(storage)

        buyer.msg(
            f"|g[Auction] You purchased '{listing.item_key}' for "
            f"{listing.price} gold!|n"
        )

        return True, (
            f"You bought '{listing.item_key}' from {listing.seller_key} "
            f"for {listing.price} gold."
        )

    def cancel_listing(self, seller: Any, listing_id: int) -> Tuple[bool, str]:
        """
        Cancel your own listing and return the item.

        Args:
            seller: The character cancelling the listing.
            listing_id: The ID of the listing to cancel.

        Returns:
            (success, message) tuple.
        """
        storage = self._get_storage()
        data = storage.get(listing_id)
        if not data:
            return False, "Listing not found."

        listing = AuctionListing.deserialize(data)

        # Verify ownership
        seller_dbref = str(seller.dbref) if hasattr(seller, "dbref") else str(seller.id)
        if seller_dbref != listing.seller_dbref:
            return False, "You can only cancel your own listings."

        # Find the item in the holding room and return to seller
        holding_room = self._get_holding_room()
        item_found = None
        for obj in holding_room.contents:
            if obj.key == listing.item_key:
                item_found = obj
                break

        if item_found:
            try:
                item_found.move_to(seller, quiet=True)
            except Exception:
                item_found.location = seller
        else:
            # Recreate from stored data
            item_found = self._recreate_item(listing.item_data)
            if item_found:
                item_found.location = seller

        # Remove listing
        del storage[listing_id]
        self._save_storage(storage)

        seller.msg(f"|y[Auction] Listing #{listing_id} cancelled. Item returned.|n")
        return True, f"Listing #{listing_id} cancelled. '{listing.item_key}' returned to you."

    def search_listings(self, keyword: str) -> List[AuctionListing]:
        """Search active listings by item name (case-insensitive substring)."""
        all_listings = self.get_active_listings()
        keyword_lower = keyword.lower()
        return [l for l in all_listings if keyword_lower in l.item_key.lower()]

    def format_listing(self, listing: AuctionListing) -> str:
        """Format a single listing for display."""
        return (
            f"  |w#{listing.listing_id:<5}|n "
            f"|c{listing.item_key:<30}|n "
            f"|Y{listing.price:<8}g|n "
            f"by |g{listing.seller_key:<15}|n "
            f"|w{listing.time_remaining}|n"
        )

    def format_listings(self, listings: List[AuctionListing]) -> str:
        """Format a list of listings for display."""
        if not listings:
            return "|yNo active listings.|n"

        lines = [
            "|w=== Auction House Listings ===|n",
            f"  {'|wID|n':<6} {'|wItem|n':<31} {'|wPrice|n':<9} {'|wSeller|n':<16} {'|wExpires|n':<10}",
            "  " + "-" * 70,
        ]
        for listing in listings:
            lines.append(self.format_listing(listing))
        lines.append(f"\n  |w{len(listings)} listing(s) total.|n")
        return "\n".join(lines)


# Global singleton
auction_house = AuctionHouse()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

class CmdAuction(_get_base_command()):
    """
    Access the Auction House / Trading Post.

    Usage:
      auction list              — Browse all active listings
      auction sell <item> <price> — List an item for sale
      auction buy <id>          — Purchase a listing by ID
      auction cancel <id>       — Cancel your own listing
      auction search <keyword>  — Search listings by item name

    The auction house charges a 10% fee on all sales.
    You may have up to 10 active listings at a time.
    Listings expire after 7 days.
    """

    key = "auction"
    aliases = ["ah"]
    locks = "cmd:all()"
    help_category = "Commerce"

    def parse(self):
        self.args = self.args.strip()
        parts = self.args.split(None, 2)
        self.subcmd = parts[0].lower() if parts else ""
        self.arg1 = parts[1] if len(parts) > 1 else ""
        self.arg2 = parts[2] if len(parts) > 2 else ""

    def func(self):
        caller = self.caller

        if not self.subcmd or self.subcmd in ("list", "browse"):
            self._cmd_list(caller)
        elif self.subcmd == "sell":
            self._cmd_sell(caller)
        elif self.subcmd == "buy":
            self._cmd_buy(caller)
        elif self.subcmd == "cancel":
            self._cmd_cancel(caller)
        elif self.subcmd == "search":
            self._cmd_search(caller)
        else:
            caller.msg(
                "|yUsage: auction <list|sell|buy|cancel|search> [args]|n\n"
                "  auction list              — Browse all listings\n"
                "  auction sell <item> <price> — List an item for sale\n"
                "  auction buy <id>          — Purchase a listing\n"
                "  auction cancel <id>       — Cancel your listing\n"
                "  auction search <keyword>  — Search by item name"
            )

    def _cmd_list(self, caller):
        """Display all active listings."""
        listings = auction_house.get_active_listings()
        caller.msg(auction_house.format_listings(listings))

    def _cmd_sell(self, caller):
        """List an item for sale."""
        if not self.arg1:
            caller.msg("|yUsage: auction sell <item> <price>|n")
            return

        item_name = self.arg1
        try:
            price = int(self.arg2)
        except (ValueError, TypeError):
            caller.msg("|yUsage: auction sell <item> <price> — price must be a number.|n")
            return

        if price < 1:
            caller.msg("|yPrice must be at least 1 gold.|n")
            return

        # Find the item in caller's inventory
        item = None
        for obj in caller.contents:
            if getattr(obj, "destination", None):
                continue
            if obj.key.lower() == item_name.lower():
                item = obj
                break

        if not item:
            caller.msg(f"|yYou don't have an item called '{item_name}'.|n")
            return

        ok, msg = auction_house.list_item(caller, item, price)
        if ok:
            caller.msg(msg)
        else:
            caller.msg(f"|r{msg}|n")

    def _cmd_buy(self, caller):
        """Purchase a listing by ID."""
        if not self.arg1:
            caller.msg("|yUsage: auction buy <listing_id>|n")
            return

        try:
            listing_id = int(self.arg1)
        except ValueError:
            caller.msg("|yListing ID must be a number.|n")
            return

        ok, msg = auction_house.buy_item(caller, listing_id)
        if ok:
            caller.msg(f"|g{msg}|n")
        else:
            caller.msg(f"|r{msg}|n")

    def _cmd_cancel(self, caller):
        """Cancel your own listing."""
        if not self.arg1:
            caller.msg("|yUsage: auction cancel <listing_id>|n")
            return

        try:
            listing_id = int(self.arg1)
        except ValueError:
            caller.msg("|yListing ID must be a number.|n")
            return

        ok, msg = auction_house.cancel_listing(caller, listing_id)
        if ok:
            caller.msg(f"|g{msg}|n")
        else:
            caller.msg(f"|r{msg}|n")

    def _cmd_search(self, caller):
        """Search listings by keyword."""
        if not self.arg1:
            caller.msg("|yUsage: auction search <keyword>|n")
            return

        results = auction_house.search_listings(self.arg1)
        if results:
            caller.msg(
                f"|w=== Search Results for '{self.arg1}' ===|n\n"
                f"{auction_house.format_listings(results)}"
            )
        else:
            caller.msg(f"|yNo listings found matching '{self.arg1}'.|n")