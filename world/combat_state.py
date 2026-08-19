"""
Combat State Machine for 'rop' — MajorMUD-Style State Tracking

Provides:
  - CombatState enum (IDLE, ENGAGING, FIGHTING, FLEEING, STUNNED, UNCONSCIOUS, DEAD)
  - CombatStateMachine with validated transitions
"""

from enum import Enum, auto


class CombatState(Enum):
    IDLE = auto()           # Not in combat
    ENGAGING = auto()       # First round, initiating attack
    FIGHTING = auto()       # Active auto-attack rounds
    FLEEING = auto()        # Attempting to flee (one-round delay)
    STUNNED = auto()        # Cannot act this round
    UNCONSCIOUS = auto()    # HP = 0, pending death/rescue
    DEAD = auto()           # Defeated, awaiting respawn/corpse


class CombatStateMachine:
    """Per-character combat state with transition validation."""

    VALID_TRANSITIONS = {
        CombatState.IDLE:         [CombatState.ENGAGING],
        CombatState.ENGAGING:     [CombatState.FIGHTING, CombatState.FLEEING, CombatState.IDLE],
        CombatState.FIGHTING:     [CombatState.FLEEING, CombatState.STUNNED, CombatState.UNCONSCIOUS, CombatState.DEAD, CombatState.IDLE],
        CombatState.FLEEING:      [CombatState.IDLE, CombatState.FIGHTING],  # Success → IDLE, Fail → FIGHTING
        CombatState.STUNNED:      [CombatState.FIGHTING, CombatState.UNCONSCIOUS],
        CombatState.UNCONSCIOUS:  [CombatState.DEAD, CombatState.IDLE],  # IDLE = revived
        CombatState.DEAD:         [CombatState.IDLE],  # After respawn
    }

    @staticmethod
    def get_state(character) -> CombatState:
        """Get the current combat state of a character."""
        if hasattr(character, "ndb") and hasattr(character.ndb, "combat_state"):
            return character.ndb.combat_state
        return CombatState.IDLE

    @staticmethod
    def set_state(character, new_state: CombatState) -> bool:
        """Set the combat state with transition validation. Returns True if valid."""
        current = CombatStateMachine.get_state(character)
        if new_state not in CombatStateMachine.VALID_TRANSITIONS.get(current, []):
            return False
        if hasattr(character, "ndb"):
            character.ndb.combat_state = new_state
        return True

    @staticmethod
    def is_acting(character) -> bool:
        """Return True if the character can act (not stunned, unconscious, or dead)."""
        state = CombatStateMachine.get_state(character)
        return state not in (CombatState.STUNNED, CombatState.UNCONSCIOUS, CombatState.DEAD)