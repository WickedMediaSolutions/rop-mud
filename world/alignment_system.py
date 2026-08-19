"""
Alignment & PvP System for 'rop' — MajorMUD-Style Good/Neutral/Evil Tracking

Provides:
  - AlignmentSystem class
  - Alignment thresholds (Good: 750+, Neutral: -749 to 749, Evil: -750-)
  - get_alignment() — derive from alignment_points
  - adjust_alignment() — clamped to [-1000, 1000]
  - is_outlaw() / set_outlaw() / clear_outlaw()
  - add_bounty() — place bounty on player
"""

import time


class AlignmentSystem:
    """Tracks alignment points, outlaw status, and bounty flags."""

    ALIGNMENT_THRESHOLDS = {
        "Good":     (750, 1000),
        "Neutral":  (-749, 749),
        "Evil":     (-1000, -750),
    }

    @staticmethod
    def get_alignment(character) -> str:
        """Derive alignment label from alignment_points."""
        points = character.attributes.get("alignment_points", default=0) if hasattr(character, "attributes") else 0
        if points >= 750:
            return "Good"
        elif points <= -750:
            return "Evil"
        return "Neutral"

    @staticmethod
    def adjust_alignment(character, amount: int) -> int:
        """Adjust alignment points, clamped to [-1000, 1000]. Returns new value."""
        if not hasattr(character, "attributes"):
            return 0
        current = character.attributes.get("alignment_points", default=0)
        new_val = max(-1000, min(1000, current + amount))
        character.attributes.add("alignment_points", new_val)
        # Update the alignment label
        character.attributes.add("alignment", AlignmentSystem.get_alignment(character))
        return new_val

    @staticmethod
    def is_outlaw(character) -> bool:
        """Check if character has outlaw flag."""
        if not hasattr(character, "attributes"):
            return False
        return character.attributes.get("outlaw", default=False)

    @staticmethod
    def set_outlaw(character, duration_seconds: int = 300) -> None:
        """Mark character as outlaw for N seconds (default 5 min)."""
        if not hasattr(character, "attributes"):
            return
        character.attributes.add("outlaw", True)
        character.attributes.add("outlaw_expires", time.time() + duration_seconds)
        character.msg("|RYou have been marked as an OUTLAW! Other players may attack you freely.|n")

    @staticmethod
    def clear_outlaw(character) -> None:
        """Remove outlaw status."""
        if not hasattr(character, "attributes"):
            return
        character.attributes.add("outlaw", False)
        character.attributes.add("outlaw_expires", 0)
        character.msg("|gYour outlaw status has been cleared.|n")

    @staticmethod
    def check_outlaw_expiry(character) -> bool:
        """Check and clear expired outlaw status. Returns True if cleared."""
        if not AlignmentSystem.is_outlaw(character):
            return False
        expires = character.attributes.get("outlaw_expires", default=0)
        if expires and time.time() > expires:
            AlignmentSystem.clear_outlaw(character)
            return True
        return False

    @staticmethod
    def add_bounty(character, amount: int) -> int:
        """Add bounty gold to a player. Returns new bounty total."""
        if not hasattr(character, "attributes"):
            return 0
        current = character.attributes.get("bounty", default=0)
        new_val = current + amount
        character.attributes.add("bounty", new_val)
        return new_val

    @staticmethod
    def clear_bounty(character) -> None:
        """Clear bounty on a player."""
        if not hasattr(character, "attributes"):
            return
        character.attributes.add("bounty", 0)


# ---------------------------------------------------------------------------
# Alignment change constants for actions
# ---------------------------------------------------------------------------

ALIGNMENT_KILL_SAME_FACTION = -50
ALIGNMENT_KILL_OPPOSITE_FACTION = 25
ALIGNMENT_KILL_AGGRESSIVE_MOB = 1
ALIGNMENT_KILL_PASSIVE_MOB = -5
ALIGNMENT_COMPLETE_GOOD_QUEST = 10
ALIGNMENT_COMPLETE_EVIL_QUEST = -10


# ---------------------------------------------------------------------------
# Module-level convenience helpers
# ---------------------------------------------------------------------------

def is_outlaw(character) -> bool:
    """Module-level helper: return True if *character* is flagged as an outlaw."""
    return AlignmentSystem.is_outlaw(character)


def check_outlaw_expiry(character) -> bool:
    """Module-level helper: check and clear an expired outlaw status."""
    return AlignmentSystem.check_outlaw_expiry(character)


def get_alignment(character) -> str:
    """Module-level helper: derive the alignment label for *character*."""
    return AlignmentSystem.get_alignment(character)


def get_opposing_alignment(alignment: str) -> str:
    """
    Return the opposite faction alignment for a given alignment string.
    Neutral has no true opposite, so returns None.
    """
    if alignment == "Good":
        return "Evil"
    if alignment == "Evil":
        return "Good"
    return None
