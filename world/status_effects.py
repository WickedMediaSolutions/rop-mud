"""
Status Effects System for 'rop'

Provides:
  - 4 DoT (Damage over Time) templates: Bleed, Poison, Burn, Curse
  - 2 Mez (Crowd Control) templates: Stun, Root
  - 2 Debuff templates: Stat Reduction, Resist Reduction
  - StatusEffect data class for tracking active effects
  - Apply/remove/tick lifecycle management
  - Integration with saving throws for resist/break checks
"""

import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, List, Any, Dict, Tuple
from evennia.utils import logger


# ---------------------------------------------------------------------------
# Status Effect Categories
# ---------------------------------------------------------------------------

class StatusEffectCategory(Enum):
    DOT = "dot"            # Damage over Time
    MEZ = "mez"            # Crowd Control (stun, root, fear, etc.)
    DEBUFF = "debuff"      # Stat / resist reduction


class StatusEffectSlot(Enum):
    """Targeting categories for stacking rules."""
    BLEED = "bleed"         # Physical DoT - multiple can stack
    POISON = "poison"       # Poison DoT - multiple can stack
    BURN = "burn"           # Fire DoT - multiple can stack
    CURSE = "curse"         # Shadow/curse DoT - multiple can stack
    STUN = "stun"           # Stun - highest duration wins, refreshes
    ROOT = "root"           # Root - highest duration wins, refreshes
    FEAR = "fear"           # Fear - highest duration wins, refreshes
    STAT_DEBUFF = "stat_debuff"   # Stat reduction - overwrites same stat
    RESIST_DEBUFF = "resist_debuff"  # Resistance reduction


# ---------------------------------------------------------------------------
# Status Effect Data Class
# ---------------------------------------------------------------------------

@dataclass
class StatusEffect:
    """Represents an active status effect on a character."""
    name: str                          # Display name
    key: str                           # Unique key for lookup
    category: StatusEffectCategory     # Dot / Mez / Debuff
    slot: StatusEffectSlot             # Stacking slot
    duration: float                    # Total duration in seconds
    remaining: float                   # Remaining duration in seconds
    tick_interval: float               # Seconds between ticks (for DoTs)
    last_tick: float = 0.0             # Timestamp of last tick
    damage_per_tick: int = 0           # Damage per tick (for DoTs)
    damage_type: str = "arcane"        # Damage type for DoTs
    stat_affected: str = ""            # Which stat is debuffed (for debuffs)
    stat_amount: int = 0               # Amount of reduction (for debuffs)
    resist_type: str = ""              # Which resist is reduced (for resist debuffs)
    resist_amount: int = 0             # Amount of resist reduction
    source: Optional[Any] = None       # The caster / source of the effect
    source_level: int = 0              # Level of the source
    source_stat: int = 10              # Casting stat of the source
    save_type: str = "spell"           # Saving throw type for break checks
    save_dc: int = 0                   # DC for periodic break checks
    break_on_damage: bool = False      # Whether damage can break the effect
    break_chance: float = 0.0          # Chance (0-1) to break on damage
    damage_threshold: int = 0          # Min damage to trigger break check
    on_apply: Optional[Callable] = None     # Callback when effect is applied
    on_remove: Optional[Callable] = None    # Callback when effect is removed
    on_tick: Optional[Callable] = None      # Callback each tick
    created_at: float = 0.0            # Timestamp when effect was created
    icon: str = ""                     # Display icon for effect list

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.last_tick == 0.0:
            self.last_tick = self.created_at
        if self.remaining == 0.0 and self.duration > 0:
            self.remaining = self.duration
        if not self.icon:
            self.icon = self._default_icon()

    def _default_icon(self) -> str:
        """Return a default icon based on category."""
        if self.category == StatusEffectCategory.DOT:
            return "|r[DoT]|n"
        elif self.category == StatusEffectCategory.MEZ:
            return "|m[CC]|n"
        elif self.category == StatusEffectCategory.DEBUFF:
            return "|y[Debuff]|n"
        return ""

    def is_expired(self) -> bool:
        return self.remaining <= 0

    def should_tick(self) -> bool:
        """Check if it's time for this effect to tick."""
        if self.category != StatusEffectCategory.DOT:
            return False
        if self.tick_interval <= 0:
            return False
        now = time.time()
        return (now - self.last_tick) >= self.tick_interval

    def mark_tick(self):
        self.last_tick = time.time()


# ---------------------------------------------------------------------------
# Status Effect Templates
# ---------------------------------------------------------------------------

# ======================== 4 DoT Templates ========================

def create_bleed_effect(damage: int = 5, duration: float = 15.0, tick_interval: float = 3.0,
                        source=None, source_level: int = 1, source_stat: int = 10,
                        save_dc: int = 0) -> StatusEffect:
    """
    Bleed: Physical slashing damage over time.
    Stacks multiple bleeds. No save to remove, duration-based only.
    """
    if save_dc == 0:
        from world.saving_throws import calculate_dc
        save_dc = calculate_dc(source_level, source_stat, 1)
    return StatusEffect(
        name="Bleeding",
        key="bleed",
        category=StatusEffectCategory.DOT,
        slot=StatusEffectSlot.BLEED,
        duration=duration,
        remaining=duration,
        tick_interval=tick_interval,
        damage_per_tick=damage,
        damage_type="slashing",
        source=source,
        source_level=source_level,
        source_stat=source_stat,
        save_type="death",
        save_dc=save_dc,
        break_on_damage=False,
        break_chance=0.0,
        icon="|r[BLEED]|n",
    )


def create_poison_effect(damage: int = 8, duration: float = 18.0, tick_interval: float = 3.0,
                         source=None, source_level: int = 1, source_stat: int = 10,
                         save_dc: int = 0) -> StatusEffect:
    """
    Poison: Toxic damage over time.
    Stacks multiple poisons. Periodic save vs poison to shake off early.
    """
    if save_dc == 0:
        from world.saving_throws import calculate_dc
        save_dc = calculate_dc(source_level, source_stat, 2)
    return StatusEffect(
        name="Poisoned",
        key="poison",
        category=StatusEffectCategory.DOT,
        slot=StatusEffectSlot.POISON,
        duration=duration,
        remaining=duration,
        tick_interval=tick_interval,
        damage_per_tick=damage,
        damage_type="poison",
        source=source,
        source_level=source_level,
        source_stat=source_stat,
        save_type="poison",
        save_dc=save_dc,
        break_on_damage=False,
        break_chance=0.0,
        icon="|g[POISON]|n",
    )


def create_burn_effect(damage: int = 10, duration: float = 12.0, tick_interval: float = 3.0,
                       source=None, source_level: int = 1, source_stat: int = 10,
                       save_dc: int = 0) -> StatusEffect:
    """
    Burn: Fire damage over time.
    Stacks multiple burns. Higher damage, shorter duration.
    """
    if save_dc == 0:
        from world.saving_throws import calculate_dc
        save_dc = calculate_dc(source_level, source_stat, 1)
    return StatusEffect(
        name="Burning",
        key="burn",
        category=StatusEffectCategory.DOT,
        slot=StatusEffectSlot.BURN,
        duration=duration,
        remaining=duration,
        tick_interval=tick_interval,
        damage_per_tick=damage,
        damage_type="fire",
        source=source,
        source_level=source_level,
        source_stat=source_stat,
        save_type="spell",
        save_dc=save_dc,
        break_on_damage=True,
        break_chance=0.1,
        damage_threshold=5,
        icon="|R[BURN]|n",
    )


def create_curse_effect(damage: int = 6, duration: float = 20.0, tick_interval: float = 4.0,
                        source=None, source_level: int = 1, source_stat: int = 10,
                        save_dc: int = 0) -> StatusEffect:
    """
    Curse: Shadow damage over time.
    Stacks multiple curses. Longest duration, periodic save vs spell.
    """
    if save_dc == 0:
        from world.saving_throws import calculate_dc
        save_dc = calculate_dc(source_level, source_stat, 3)
    return StatusEffect(
        name="Cursed",
        key="curse",
        category=StatusEffectCategory.DOT,
        slot=StatusEffectSlot.CURSE,
        duration=duration,
        remaining=duration,
        tick_interval=tick_interval,
        damage_per_tick=damage,
        damage_type="shadow",
        source=source,
        source_level=source_level,
        source_stat=source_stat,
        save_type="spell",
        save_dc=save_dc,
        break_on_damage=False,
        break_chance=0.0,
        icon="|M[CURSE]|n",
    )


# ======================== 2 Mez (Crowd Control) Templates ========================

def create_stun_effect(duration: float = 6.0, source=None, source_level: int = 1,
                       source_stat: int = 10, save_dc: int = 0,
                       break_on_damage: bool = True, break_chance: float = 0.0) -> StatusEffect:
    """
    Stun: Target cannot act.
    Non-stacking (highest duration wins). Damage may break (by default, does not break).
    Periodic save to break free.
    """
    if save_dc == 0:
        from world.saving_throws import calculate_dc
        save_dc = calculate_dc(source_level, source_stat, 2)
    return StatusEffect(
        name="Stunned",
        key="stun",
        category=StatusEffectCategory.MEZ,
        slot=StatusEffectSlot.STUN,
        duration=duration,
        remaining=duration,
        tick_interval=0,
        damage_per_tick=0,
        source=source,
        source_level=source_level,
        source_stat=source_stat,
        save_type="petrification",
        save_dc=save_dc,
        break_on_damage=break_on_damage,
        break_chance=break_chance,
        damage_threshold=0,
        icon="|m[STUN]|n",
    )


def create_root_effect(duration: float = 8.0, source=None, source_level: int = 1,
                       source_stat: int = 10, save_dc: int = 0,
                       break_on_damage: bool = True, break_chance: float = 0.25) -> StatusEffect:
    """
    Root: Target cannot move or flee but can still act.
    Non-stacking (highest duration wins). Damage breaks with chance.
    Periodic save to break free.
    """
    if save_dc == 0:
        from world.saving_throws import calculate_dc
        save_dc = calculate_dc(source_level, source_stat, 1)
    return StatusEffect(
        name="Rooted",
        key="root",
        category=StatusEffectCategory.MEZ,
        slot=StatusEffectSlot.ROOT,
        duration=duration,
        remaining=duration,
        tick_interval=0,
        damage_per_tick=0,
        source=source,
        source_level=source_level,
        source_stat=source_stat,
        save_type="petrification",
        save_dc=save_dc,
        break_on_damage=break_on_damage,
        break_chance=break_chance,
        damage_threshold=3,
        icon="|G[ROOT]|n",
    )


# ======================== 2 Debuff Templates ========================

def create_stat_debuff_effect(stat: str = "str", amount: int = 5, duration: float = 20.0,
                              source=None, source_level: int = 1, source_stat: int = 10,
                              save_dc: int = 0) -> StatusEffect:
    """
    Stat Reduction: Reduce a specific stat by a flat amount.
    Overwrites existing debuff on the same stat.
    """
    if save_dc == 0:
        from world.saving_throws import calculate_dc
        save_dc = calculate_dc(source_level, source_stat, 2)
    return StatusEffect(
        name=f"Impaired {stat.upper()}",
        key=f"debuff_{stat}",
        category=StatusEffectCategory.DEBUFF,
        slot=StatusEffectSlot.STAT_DEBUFF,
        duration=duration,
        remaining=duration,
        tick_interval=0,
        damage_per_tick=0,
        stat_affected=stat,
        stat_amount=amount,
        source=source,
        source_level=source_level,
        source_stat=source_stat,
        save_type="spell",
        save_dc=save_dc,
        break_on_damage=False,
        break_chance=0.0,
        icon="|y[STAT-]|n",
    )


def create_resist_debuff_effect(resist_type: str = "fire", amount: int = 20,
                                duration: float = 15.0, source=None, source_level: int = 1,
                                source_stat: int = 10, save_dc: int = 0) -> StatusEffect:
    """
    Resist Reduction: Reduce resistance to a specific damage type.
    Overwrites existing debuff on the same resist type.
    """
    if save_dc == 0:
        from world.saving_throws import calculate_dc
        save_dc = calculate_dc(source_level, source_stat, 2)
    return StatusEffect(
        name=f"Vulnerable to {resist_type}",
        key=f"debuff_resist_{resist_type}",
        category=StatusEffectCategory.DEBUFF,
        slot=StatusEffectSlot.RESIST_DEBUFF,
        duration=duration,
        remaining=duration,
        tick_interval=0,
        damage_per_tick=0,
        resist_type=resist_type,
        resist_amount=amount,
        source=source,
        source_level=source_level,
        source_stat=source_stat,
        save_type="spell",
        save_dc=save_dc,
        break_on_damage=False,
        break_chance=0.0,
        icon="|y[RESIST-]|n",
    )


# ---------------------------------------------------------------------------
# Active Effects Manager
# ---------------------------------------------------------------------------

class ActiveEffects:
    """
    Manages all active status effects on a character.
    Handles stacking rules, tick processing, and removal.
    """

    def __init__(self, character):
        self.character = character
        self._effects: List[StatusEffect] = []
        self._load_from_character()

    def _load_from_character(self):
        """Load persisted effects from character attributes."""
        if not hasattr(self.character, "attributes"):
            return
        stored = self.character.attributes.get("active_effects", default=None)
        if stored:
            for data in stored:
                try:
                    effect = StatusEffect(**data)
                    self._effects.append(effect)
                except Exception as err:
                    logger.log_err(f"ActiveEffects._load_from_character: failed to load effect: {err}")

    def _save_to_character(self):
        """Persist current effects to character attributes."""
        if not hasattr(self.character, "attributes"):
            return
        data = []
        for effect in self._effects:
            data.append(vars(effect).copy())
        self.character.attributes.add("active_effects", data)

    def get_effects(self, category: Optional[StatusEffectCategory] = None) -> List[StatusEffect]:
        """Return all active effects, optionally filtered by category."""
        if category:
            return [e for e in self._effects if e.category == category]
        return list(self._effects)

    def get_effect_by_slot(self, slot: StatusEffectSlot) -> Optional[StatusEffect]:
        """Get the first active effect in a given slot."""
        for e in self._effects:
            if e.slot == slot:
                return e
        return None

    def has_effect(self, key: str) -> bool:
        """Check if a specific effect is active."""
        for e in self._effects:
            if e.key == key:
                return True
        return False

    def has_effect_in_slot(self, slot: StatusEffectSlot) -> bool:
        """Check if any effect in the given slot is active."""
        return self.get_effect_by_slot(slot) is not None

    def is_stunned(self) -> bool:
        """Check if character is stunned and cannot act."""
        return self.has_effect_in_slot(StatusEffectSlot.STUN)

    def is_rooted(self) -> bool:
        """Check if character is rooted and cannot move."""
        return self.has_effect_in_slot(StatusEffectSlot.ROOT)

    def can_act(self) -> bool:
        """Check if character can act (not stunned)."""
        return not self.is_stunned()

    def can_move(self) -> bool:
        """Check if character can move (not rooted)."""
        return not self.is_rooted()

    def apply_effect(self, effect: StatusEffect) -> Tuple[bool, str]:
        """
        Apply a status effect to the character.
        Handles stacking rules per slot type.

        Returns (applied: bool, message: str).
        """
        # Racial passive: poison/bleed immunity (Undead).
        try:
            from world.rules import get_racial_bonuses
            racial = get_racial_bonuses(self.character)
            if racial.get("poison_immune") and effect.slot == StatusEffectSlot.POISON:
                return False, "You are immune to poison."
            if racial.get("bleed_immune") and effect.slot == StatusEffectSlot.BLEED:
                return False, "You are immune to bleeding."
        except Exception as err:
            logger.log_err(f"ActiveEffects.apply_effect: racial bonus check failed: {err}")

        # Check stacking rules
        if effect.slot in (StatusEffectSlot.STUN, StatusEffectSlot.ROOT, StatusEffectSlot.FEAR):
            # Non-stacking: overwrite if new duration is higher
            existing = self.get_effect_by_slot(effect.slot)
            if existing:
                if effect.duration > existing.remaining:
                    self._remove_effect_internal(existing, "superseded")
                    self._effects.append(effect)
                    self._save_to_character()
                    if effect.on_apply:
                        effect.on_apply(self.character, effect)
                    return True, f"{effect.name} effect is renewed (stronger)."
                else:
                    existing.remaining = max(existing.remaining, effect.duration)
                    self._save_to_character()
                    return False, f"{effect.name} is already in effect (stronger version persists)."

        elif effect.slot in (StatusEffectSlot.STAT_DEBUFF, StatusEffectSlot.RESIST_DEBUFF):
            existing = self.get_effect_by_slot(effect.slot)
            if existing:
                if (effect.slot == StatusEffectSlot.STAT_DEBUFF and
                        existing.stat_affected == effect.stat_affected):
                    self._remove_effect_internal(existing, "superseded")
                elif (effect.slot == StatusEffectSlot.RESIST_DEBUFF and
                      existing.resist_type == effect.resist_type):
                    self._remove_effect_internal(existing, "superseded")

        # Stacking slots (DoTs): always add
        self._effects.append(effect)
        self._save_to_character()

        if effect.on_apply:
            effect.on_apply(self.character, effect)

        return True, f"{effect.name} applied!"

    def remove_effect(self, effect: StatusEffect, reason: str = "expired"):
        """Remove a specific effect."""
        self._remove_effect_internal(effect, reason)
        self._save_to_character()

    def remove_effect_by_slot(self, slot: StatusEffectSlot, reason: str = "expired"):
        """Remove all effects in a given slot."""
        for e in list(self._effects):
            if e.slot == slot:
                self._remove_effect_internal(e, reason)
        self._save_to_character()

    def _remove_effect_internal(self, effect: StatusEffect, reason: str):
        """Internal removal without saving."""
        if effect in self._effects:
            self._effects.remove(effect)
            if effect.category == StatusEffectCategory.DEBUFF:
                self._undo_debuff(effect)
            if effect.on_remove:
                effect.on_remove(self.character, effect)

    def _undo_debuff(self, effect: StatusEffect):
        """Restore stats that were reduced by a debuff."""
        if effect.stat_affected:
            stats = self.character.attributes.get("stats", default={})
            if stats:
                stats[effect.stat_affected] = stats.get(effect.stat_affected, 10) + effect.stat_amount
                self.character.attributes.add("stats", stats)
        if effect.resist_type:
            resistances = self.character.attributes.get("damage_resistances", default={})
            if resistances and effect.resist_type in resistances:
                del resistances[effect.resist_type]
                if any(resistances):
                    self.character.attributes.add("damage_resistances", resistances)
                else:
                    self.character.attributes.add("damage_resistances", {})

    def tick(self, current_time: Optional[float] = None) -> List[str]:
        """
        Process all active effects for a tick.
        Returns a list of messages to display.
        """
        if current_time is None:
            current_time = time.time()

        messages = []
        to_remove = []

        for effect in self._effects:
            elapsed = current_time - effect.last_tick
            effect.remaining -= elapsed

            if effect.is_expired():
                to_remove.append(effect)
                messages.append(f"|g{effect.name} has worn off.|n")
                continue

            if effect.category == StatusEffectCategory.DOT and effect.should_tick():
                effect.mark_tick()
                dmg = effect.damage_per_tick

                from world.damage_types import apply_damage_with_type
                dmg = apply_damage_with_type(dmg, effect.damage_type, self.character)

                if dmg > 0:
                    hp = self.character.attributes.get("hp", 0)
                    actual = min(dmg, hp)
                    self.character.attributes.add("hp", max(0, hp - actual))
                    messages.append(
                        f"|r{effect.name} deals {actual} {effect.damage_type} damage to you.|n"
                    )

                    if effect.key == "burn" and effect.break_on_damage:
                        if random.random() < effect.break_chance:
                            to_remove.append(effect)
                            messages.append(f"|gThe {effect.name} effect is extinguished!|n")
                            continue

                if self.character.attributes.get("hp", 0) <= 0:
                    from world.combat import _handle_defeat
                    _handle_defeat(self.character, effect.source or self.character)
                    break

            if effect.category == StatusEffectCategory.MEZ and effect.save_dc > 0:
                if current_time - effect.last_tick >= 3.0:
                    effect.mark_tick()
                    from world.saving_throws import roll_saving_throw, SavingThrow
                    save_map = {
                        "petrification": SavingThrow.PETRIFICATION,
                        "spell": SavingThrow.SPELL,
                        "poison": SavingThrow.POISON,
                        "death": SavingThrow.DEATH,
                        "rod": SavingThrow.ROD,
                    }
                    save_type = save_map.get(effect.save_type, SavingThrow.SPELL)
                    passed, roll, dc = roll_saving_throw(
                        self.character, save_type, dc=effect.save_dc
                    )
                    if passed:
                        to_remove.append(effect)
                        messages.append(
                            f"|gYou break free from {effect.name}! (Save: {roll} vs DC {dc})|n"
                        )

        for effect in to_remove:
            if effect in self._effects:
                self._remove_effect_internal(effect, "expired")

        if to_remove:
            self._save_to_character()

        return messages

    def check_break_on_damage(self, damage: int) -> List[str]:
        """Check if any mez effects should break due to damage taken."""
        messages = []
        to_remove = []

        for effect in self._effects:
            if effect.category == StatusEffectCategory.MEZ and effect.break_on_damage:
                if damage >= effect.damage_threshold:
                    if random.random() < effect.break_chance:
                        to_remove.append(effect)
                        messages.append(f"|gThe damage breaks {effect.name}!|n")

        for effect in to_remove:
            self._remove_effect_internal(effect, "damage_break")

        if to_remove:
            self._save_to_character()

        return messages

    def get_effect_display(self) -> str:
        """Return a compact display string of all active effects."""
        if not self._effects:
            return ""

        parts = []
        for effect in self._effects:
            remaining = f"{effect.remaining:.0f}s"
            parts.append(f"{effect.icon} {effect.name} ({remaining})")

        return " | ".join(parts)

    def clear_all(self):
        """Remove all active effects."""
        for effect in list(self._effects):
            self._remove_effect_internal(effect, "cleared")
        self._effects.clear()
        self._save_to_character()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def apply_status_effect(target, effect: StatusEffect, caster=None) -> Tuple[bool, str]:
    """
    Apply a status effect to a target, with saving throw check.
    Returns (applied: bool, message: str).
    """
    if not hasattr(target, "attributes"):
        return False, "Invalid target."

    if effect.save_dc > 0:
        from world.saving_throws import roll_saving_throw, SavingThrow
        save_map = {
            "poison": SavingThrow.POISON,
            "death": SavingThrow.DEATH,
            "petrification": SavingThrow.PETRIFICATION,
            "rod": SavingThrow.ROD,
            "spell": SavingThrow.SPELL,
        }
        save_type = save_map.get(effect.save_type, SavingThrow.SPELL)
        passed, roll, dc = roll_saving_throw(target, save_type, dc=effect.save_dc)

        if passed:
            from world.saving_throws import format_save_result
            return False, format_save_result(target, save_type, True, roll, dc)

    if not hasattr(target, "ndb") or not hasattr(target.ndb, "active_effects") or target.ndb.active_effects is None:
        target.ndb.active_effects = ActiveEffects(target)

    effects_manager = target.ndb.active_effects
    return effects_manager.apply_effect(effect)


def get_active_effects(target) -> ActiveEffects:
    """Get or create the ActiveEffects manager for a target."""
    if not hasattr(target, "ndb"):
        return None
    if not hasattr(target.ndb, "active_effects"):
        target.ndb.active_effects = ActiveEffects(target)
    return target.ndb.active_effects