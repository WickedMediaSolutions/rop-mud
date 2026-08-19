"""
Quest Item System for 'rop'

Provides:
  - quest_item flag on objects
  - Helper functions to check/restrict quest item behavior
  - Quest items cannot be sold, dropped in public rooms, or traded

Usage:
  from world.quest_items import mark_as_quest_item, is_quest_item, can_drop_item
"""


def mark_as_quest_item(obj):
    """
    Mark an object as a quest item.

    Quest items cannot be:
      - Sold to shopkeepers
      - Dropped in public rooms (non-private)
      - Traded/given to other players
    """
    obj.attributes.add("quest_item", True)
    obj.attributes.add("quest_item_bound", True)


def is_quest_item(obj):
    """Check if an object is flagged as a quest item."""
    return obj.attributes.get("quest_item", False) is True


def can_drop_item(character, obj):
    """
    Check if a character is allowed to drop this item.

    Returns (True, "") if allowed, (False, reason) if not.
    """
    if is_quest_item(obj):
        return False, (
            "|rThat item is bound to you by a quest. "
            "You cannot discard it.|n"
        )
    return True, ""


def can_sell_item(character, obj, shopkeeper=None):
    """
    Check if a character can sell this item to a shopkeeper.

    Returns (True, "") if allowed, (False, reason) if not.
    """
    if is_quest_item(obj):
        return False, (
            "|rThat item is bound to you by a quest. "
            "Shopkeepers will not accept it.|n"
        )
    return True, ""


def can_trade_item(character, obj, target):
    """
    Check if a character can trade/give this item to another player.

    Returns (True, "") if allowed, (False, reason) if not.
    """
    if is_quest_item(obj):
        return False, (
            "|rThat item is bound to you by a quest. "
            "You cannot trade it away.|n"
        )
    return True, ""


def validate_quest_item_movement(obj, source_location, destination):
    """
    Hook that can be called when a quest item is moved.

    Called from at_pre_move or at_pre_drop hooks to prevent
    quest items from being left in public rooms.

    Returns (True, "") if movement is allowed, (False, reason) if blocked.
    """
    if not is_quest_item(obj):
        return True, ""

    # If being moved to a room (dropped), block it
    if destination is not None:
        try:
            # Check if destination is a room typeclass
            from evennia.objects.objects import DefaultRoom
            from typeclasses.rooms import Room
            if isinstance(destination, (DefaultRoom, Room)):
                return False, (
                    "|rYour quest item cannot be left behind. "
                    "It is bound to you.|n"
                )
        except Exception:
            pass

    # Allow moving to other characters/containers (trade validation
    # happens at a higher level via can_trade_item)
    return True, ""
