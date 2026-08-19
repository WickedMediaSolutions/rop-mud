"""
Centralized Economy & Currency Module for 'rop'
================================================

Provides:
  - format_money() — unified coin display (copper/silver/gold)
  - add_money() / remove_money() — safe character money operations
  - get_money_display() — convenient character money string
  - Money constants and conversion helpers

All coin-related display in the MUD should flow through this module
to ensure consistent formatting everywhere.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Coin tier constants (MajorMUD classic)
# ---------------------------------------------------------------------------

COPPER_PER_SILVER = 10
SILVER_PER_GOLD = 10
COPPER_PER_GOLD = COPPER_PER_SILVER * SILVER_PER_GOLD  # 100


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_money(total_gold: int, *, brief: bool = False) -> str:
    """
    Convert a raw gold amount into a human-readable currency string.

    Currency tiers: 100 copper = 10 silver = 1 gold

    Args:
        total_gold: Total gold (copper subunit stored as 1/100th gold).
        brief: If True, return short form like "12g 3s 5c".

    Returns:
        Color-coded currency string.
    """
    if total_gold is None or total_gold < 0:
        total_gold = 0

    # Convert to copper for precise tier breakdown
    total_copper = int(total_gold * COPPER_PER_GOLD)

    gold = total_copper // COPPER_PER_GOLD
    remainder = total_copper % COPPER_PER_GOLD
    silver = remainder // COPPER_PER_SILVER
    copper = remainder % COPPER_PER_SILVER

    if total_copper == 0:
        return "|r0 copper|n"

    parts = []
    if gold > 0:
        if brief:
            parts.append(f"|Y{gold}g|n")
        else:
            label = "gold piece" if gold == 1 else "gold"
            parts.append(f"|Y{gold} {label}|n")
    if silver > 0:
        if brief:
            parts.append(f"|w{silver}s|n")
        else:
            label = "silver piece" if silver == 1 else "silver"
            parts.append(f"|w{silver} {label}|n")
    if copper > 0:
        if brief:
            parts.append(f"|r{copper}c|n")
        else:
            label = "copper piece" if copper == 1 else "copper"
            parts.append(f"|r{copper} {label}|n")

    return ", ".join(parts)


def format_money_brief(total_gold: int) -> str:
    """Short form like '|Y12g|n |w3s|n |r5c|n'."""
    return format_money(total_gold, brief=True)


def format_money_long(total_gold: int) -> str:
    """Long form like '12 gold, 3 silver, 5 copper'."""
    return format_money(total_gold, brief=False)


# ---------------------------------------------------------------------------
# Character money accessors
# ---------------------------------------------------------------------------

def get_money(character: Any) -> int:
    """
    Return the character's carried money (in gold-equivalent).
    """
    if not hasattr(character, "attributes"):
        return 0
    return character.attributes.get("money", default=0) or 0


def get_bank_money(character: Any) -> int:
    """Return the character's banked money (in gold-equivalent)."""
    if not hasattr(character, "attributes"):
        return 0
    return character.attributes.get("bank_gold", default=0) or 0


def add_money(character: Any, amount: int) -> int:
    """
    Add gold to a character's carried wealth.

    Args:
        character: The character object.
        amount: Amount of gold to add.

    Returns:
        New total carried gold.
    """
    if not hasattr(character, "attributes"):
        return 0
    current = get_money(character)
    new_total = max(0, current + amount)
    character.attributes.add("money", new_total)
    return new_total


def remove_money(character: Any, amount: int) -> bool:
    """
    Remove gold from a character's carried wealth.

    Args:
        character: The character object.
        amount: Amount of gold to remove.

    Returns:
        True if successful, False if insufficient funds.
    """
    if not hasattr(character, "attributes"):
        return False
    current = get_money(character)
    if current < amount:
        return False
    character.attributes.add("money", current - amount)
    return True


def has_enough_money(character: Any, amount: int) -> bool:
    """Check if character has at least the given amount of gold."""
    return get_money(character) >= amount


def display_wealth(character: Any) -> str:
    """
    Return a formatted string showing carried + banked wealth.
    Used by 'balance', 'look self', and other info displays.
    """
    carried = get_money(character)
    bank = get_bank_money(character)
    lines = [
        f"|cCarried:|n {format_money_brief(carried)}",
        f"|cBanked: |n {format_money_brief(bank)}",
        f"|cTotal:  |n {format_money_brief(carried + bank)}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Coin breakdown helpers
# ---------------------------------------------------------------------------

def gold_to_copper(gold: int) -> int:
    """Convert gold to copper pieces."""
    return gold * COPPER_PER_GOLD


def gold_to_silver(gold: int) -> int:
    """Convert gold to silver pieces."""
    return gold * SILVER_PER_GOLD


def copper_to_gold(copper: int) -> int:
    """Convert copper to gold (integer division)."""
    return copper // COPPER_PER_GOLD


# ---------------------------------------------------------------------------
# Brief prompt money segment
# ---------------------------------------------------------------------------

def get_prompt_money_segment(character: Any) -> str:
    """
    Return a compact money segment for the status prompt.
    Format: [Gold: 12g 3s 5c]
    """
    total = get_money(character)
    if total == 0:
        return "|w[Gold: 0]|n"
    return f"|w[Gold: {format_money_brief(total)}]|n"


# ---------------------------------------------------------------------------
# Economic sink: tax calculation
# ---------------------------------------------------------------------------

def calculate_transaction_tax(amount: int, tax_rate: float = 0.05) -> int:
    """
    Calculate a gold tax on a transaction.

    Args:
        amount: Transaction amount in gold.
        tax_rate: Tax as decimal (default 5%).

    Returns:
        Tax amount in gold (minimum 1 if any tax applies).
    """
    tax = int(amount * tax_rate)
    return max(1, tax) if amount > 0 else 0


# ---------------------------------------------------------------------------
# Inn rent cost calculation
# ---------------------------------------------------------------------------

def calculate_inn_cost(character: Any, hours: int = 1) -> int:
    """
    Calculate inn rental cost based on character level.

    Higher-level characters pay more for lodgings (they have more money).
    """
    level = 1
    if hasattr(character, "attributes"):
        level = character.attributes.get("level", default=1) or 1

    # Base cost + level scaling
    base = 5  # 5 gold base
    scaled = base + (level // 5)  # +1 gold per 5 levels
    return max(1, scaled * hours)