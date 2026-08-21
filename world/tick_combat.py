"""
Central Combat Engine for 'rop' — MajorMUD/EmlenMUD Round-Robin Combat

Provides:
  - CombatEngine: a single persistent Evennia Script that ticks every 2-3
    seconds, iterating a central engagement table and processing combat
    rounds for every active pairing.
  - CombatHandler: public static API for commands to start/stop/flee combat.
  - THAC0/AC hit resolution and damage integration via damage_formulas.
  - Death cleanup that removes engagements and triggers _handle_defeat.
  - Combat skills integration (kick, bash, backstab, disarm) in auto-attack.
  - Ranged combat (bows/crossbows) with range-aware attack logic.
  - Two-weapon fighting / dual-wield off-hand attacks.
  - Stun/incapacitate effects that skip combat rounds.
  - Combat log / battle spam control (brief mode).

Architecture:
  ENGAGEMENTS[dbref] = {dbref, dbref, ...}   — who this entity is fighting
  A single CombatEngine script runs on the first room/global object and
  drives ALL combat rounds.  When the last engagement is removed the
  script stops itself.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from typeclasses.characters import Character

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMBAT_TICK_INTERVAL = 2.5          # seconds between rounds
BASE_HIT_CHANCE = 50                # percentage at equal THAC0 vs AC
HIT_CHANCE_PER_DIFF = 5             # +5% per point of (THAC0 - AC)
MIN_HIT_CHANCE = 5                  # always at least 5% chance to hit
MAX_HIT_CHANCE = 95                 # always at least 5% chance to miss
BASE_THAC0 = 20                     # THAC0 at level 1 (lower = better)
MIN_DAMAGE = 1
BASE_FLEE_CHANCE = 0.65
FLEE_LEVEL_CAP = 20

# Off-hand attack constants
OFFHAND_DAMAGE_MULT = 0.6           # off-hand does 60% damage
OFFHAND_HIT_PENALTY = -2            # -2 THAC0 penalty for off-hand
DUAL_WIELD_CLASSES = {"Warrior", "Rogue", "Ranger", "Monk"}

# Ranged combat constants
RANGED_WEAPON_TYPES = {"bow", "crossbow", "longbow", "shortbow"}
RANGED_MIN_RANGE = 1                # same room
RANGED_MAX_RANGE = 1                # adjacent rooms (future: multi-room)

# Stun constants
STUN_DURATION_SECONDS = 3.0         # default stun duration

# ---------------------------------------------------------------------------
# Central engagement table (module-level, in-memory, rebuilt on reload)
# ---------------------------------------------------------------------------

ENGAGEMENTS: Dict[int, Set[int]] = {}       # dbref -> set of opponent dbrefs
COMBAT_SCRIPT_UID: Optional[int] = None     # dbref of the object hosting the script


def _alive(obj: Any) -> bool:
    """Return True if the object exists, has attributes, and HP > 0."""
    if obj is None:
        return False
    try:
        hp = obj.attributes.get("hp", 0)
        return hp > 0
    except Exception:
        return False


def _player(obj: Any) -> bool:
    """Return True if obj is a player character (has an account)."""
    return bool(getattr(obj, "has_account", False))


def _same_room(a: Any, b: Any) -> bool:
    """Return True if both objects share the same non-None location."""
    try:
        aloc = a.location
        bloc = b.location
        if aloc is None or bloc is None:
            return False
        return aloc.id == bloc.id
    except Exception:
        return False


def _stat(obj: Any, key: str, default: int = 10) -> int:
    """Safely fetch a stat from a character or mob (including gear bonuses)."""
    try:
        from world.mob_equipment import get_effective_stat
        return int(get_effective_stat(obj, key, default))
    except Exception:
        pass
    try:
        stats = obj.attributes.get("stats", {})
        if stats is not None and hasattr(stats, "items"):
            return int(stats.get(key, default))
    except Exception:
        pass
    return default


def _level(obj: Any) -> int:
    """Safely fetch the level of a character or mob."""
    try:
        return obj.attributes.get("level", 1)
    except Exception:
        return 1


def _weapon_damage(character: Any) -> int:
    """Calculate base weapon damage from equipped gear or unarmed STR.

    Uses the centralized ``world.mob_equipment.get_equipped_weapon_damage``
    helper which scans the character's equipped items for weapon damage.
    Falls back to STR-based unarmed damage if no weapon is found.
    """
    try:
        from world.mob_equipment import get_equipped_weapon_damage
        return get_equipped_weapon_damage(character)
    except Exception:
        str_val = _stat(character, "str", 10)
        return max(1, str_val // 2)


def _thac0(character: Any) -> int:
    """
    Classic THAC0: starts at BASE_THAC0 and improves by 1 per level.
    Lower THAC0 = better at hitting.
    """
    lvl = _level(character)
    dex_bonus = max(0, (_stat(character, "dex", 10) - 10) // 3)
    # Phase 2.3: Iron Grip talent grants +1 THAC0 per rank (lower = better).
    try:
        from world.skill_tree import get_talent_bonuses
        thac0_bonus = int(get_talent_bonuses(character).get("thac0_bonus", 0))
    except Exception:
        thac0_bonus = 0
    return max(1, BASE_THAC0 - (lvl - 1) - dex_bonus - thac0_bonus)


def _armor_class(character: Any) -> int:
    """
    Classic descending AC: base 10, reduced by armor, DEX, and CON.
    Lower AC = harder to hit.
    """
    base = 10
    dex_bonus = max(0, (_stat(character, "dex", 10) - 10) // 2)
    con_bonus = max(0, (_stat(character, "con", 10) - 10) // 3)
    try:
        from world.damage_formulas import _get_armor_value
        armor = _get_armor_value(character)
    except Exception:
        armor = 0
    # Phase 2.3: Dodge talent grants +1 AC per rank (harder to hit = lower AC).
    try:
        from world.skill_tree import get_talent_bonuses
        ac_bonus = int(get_talent_bonuses(character).get("ac_bonus", 0))
    except Exception:
        ac_bonus = 0
    return max(-10, base - dex_bonus - con_bonus - (armor // 2) - ac_bonus)


def _hit_roll(attacker: Any, defender: Any, thac0_penalty: int = 0) -> bool:
    """
    Classic THAC0-based attack roll using d20 semantics.

    In classic D&D:  d20 + AC >= THAC0  to hit.
    Equivalently:    d20 >= THAC0 - AC.
    So roll_needed = THAC0 - AC, and hit_chance = (21 - roll_needed) * 5%.
    Clamped to [MIN_HIT_CHANCE, MAX_HIT_CHANCE].

    Racial passives (Wood Elf dodge +10%, Pixie evasion +15%) reduce the
    attacker's effective hit chance by the defender's dodge/evasion bonus.

    Args:
        attacker: The attacking character/mob.
        defender: The defending character/mob.
        thac0_penalty: Optional penalty applied to the attacker's THAC0
            (positive = worse, used for off-hand attacks). Default 0.
    """
    atk_thac0 = _thac0(attacker) + thac0_penalty
    def_ac = _armor_class(defender)
    roll_needed = max(1, atk_thac0 - def_ac)
    hit_chance = (21 - roll_needed) * 5
    hit_chance = max(MIN_HIT_CHANCE, min(MAX_HIT_CHANCE, hit_chance))

    # Racial passive: dodge chance (Wood Elf +10%) and evasion (Pixie +15%).
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(defender)
        dodge_pct = racial.get("dodge_chance_pct", 0)
        evasion_pct = racial.get("evasion_pct", 0)
        total_avoid = dodge_pct + evasion_pct
        if total_avoid > 0:
            hit_chance = max(MIN_HIT_CHANCE, hit_chance - total_avoid)
    except Exception:
        pass

    # Phase 2.2: Monk passive dodge bonus (WIS-based)
    try:
        from world.monk_system import get_passive_dodge_bonus
        monk_dodge = get_passive_dodge_bonus(defender)
        if monk_dodge > 0:
            hit_chance = max(MIN_HIT_CHANCE, hit_chance - monk_dodge)
    except Exception:
        pass

    # Phase 2.2: Druid shapeshift form dodge bonus
    try:
        from world.druid_system import get_form_bonuses
        form_bonuses = get_form_bonuses(defender)
        if form_bonuses:
            form_dodge = form_bonuses.get("dodge_pct", 0)
            if form_dodge != 0:
                hit_chance = max(MIN_HIT_CHANCE, hit_chance + form_dodge)
    except Exception:
        pass

    return random.randint(1, 100) <= hit_chance


def _damage(attacker: Any, defender: Any) -> dict:
    """Calculate physical damage using the damage_formulas engine.

    Damage type is read from the attacker's equipped weapon so that
    slash/pierce/blunt/magic weapons behave correctly against armor.
    """
    from world.damage_formulas import calculate_melee_damage, DamageType
    wd = _weapon_damage(attacker)
    dt = DamageType.SLASH
    try:
        # Prefer the cached type set by combat skills, then the weapon.
        if hasattr(attacker, "ndb") and hasattr(attacker.ndb, "cached_damage_type"):
            dt = attacker.ndb.cached_damage_type
        else:
            from world.mob_equipment import get_equipped_weapon_damage_type
            dt_str = get_equipped_weapon_damage_type(attacker)
            dt = DamageType(dt_str)
    except Exception:
        pass
    return calculate_melee_damage(attacker, defender, wd, dt)


def _flee_chance(fleer: Any, opponent: Any) -> float:
    """Calculate flee success probability."""
    f_level = _level(fleer)
    f_dex = _stat(fleer, "dex", 10)
    o_level = _level(opponent)
    level_diff = f_level - o_level
    level_factor = max(-0.30, min(0.30, level_diff * 0.015))
    dex_bonus = max(0, (f_dex - 10) * 0.01)
    chance = BASE_FLEE_CHANCE + level_factor + dex_bonus
    return max(0.10, min(0.90, chance))


# ---------------------------------------------------------------------------
# Ranged combat helpers
# ---------------------------------------------------------------------------

def _is_ranged_weapon(character: Any) -> bool:
    """Return True if the character has a ranged weapon equipped."""
    try:
        from world.mob_equipment import get_equipped_slot_map
        equipped = get_equipped_slot_map(character)
        if equipped:
            for slot in ("right_hand", "two_hand", "left_hand", "hands"):
                weapon_name = equipped.get(slot)
                if weapon_name:
                    name_lower = str(weapon_name).lower()
                    for rtype in RANGED_WEAPON_TYPES:
                        if rtype in name_lower:
                            return True
    except Exception:
        pass
    return False


def _has_offhand_weapon(character: Any) -> bool:
    """Return True if the character has a weapon in the left-hand slot."""
    try:
        from world.mob_equipment import get_equipped_slot_map
        equipped = get_equipped_slot_map(character)
        if equipped:
            offhand_name = equipped.get("left_hand")
            if offhand_name:
                for obj in character.contents:
                    if getattr(obj, "destination", None):
                        continue
                    if obj.key == offhand_name and hasattr(obj, "attributes"):
                        dmg = obj.attributes.get("damage", 0)
                        if dmg > 0:
                            return True
    except Exception:
        pass
    return False


def _can_dual_wield(character: Any) -> bool:
    """Return True if the character's class allows dual-wielding."""
    try:
        char_class = character.attributes.get("class", "Warrior")
        return char_class in DUAL_WIELD_CLASSES
    except Exception:
        return False


def _is_stunned(character: Any) -> bool:
    """Return True if the character is currently stunned."""
    try:
        return character.attributes.get("stunned", False)
    except Exception:
        return False


def _is_stealthed(character: Any) -> bool:
    """Return True if the character is currently stealthed/hidden."""
    try:
        return character.attributes.get("stealthed", False)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# CombatEngine — single global script
# ---------------------------------------------------------------------------

def _get_default_script_base():
    """Lazy import to avoid requiring Django for pure-function tests."""
    from evennia.scripts.scripts import DefaultScript
    return DefaultScript


class CombatEngine(_get_default_script_base()):
    """
    Central round-robin combat ticker.

    This script is created once (on any room or object) when the first
    engagement is registered.  It ticks every COMBAT_TICK_INTERVAL seconds,
    iterating all active engagement pairs and resolving one attack round
    per pairing.  When no engagements remain it stops automatically.
    """

    def at_script_creation(self):
        self.key = "combat_engine"
        self.desc = "Central round-robin combat engine"
        self.interval = COMBAT_TICK_INTERVAL
        self.persistent = False
        self.start_delay = True

    def at_repeat(self):
        """Process one round for every active engagement pairing.

        Each combatant attacks each of their opponents once per tick.
        Bidirectional: if A fights B, both A->B and B->A are resolved
        in the same tick so mobs always counter-attack.
        """
        global ENGAGEMENTS

        if not ENGAGEMENTS:
            self.stop()
            return

        # Snapshot keys to avoid mutation-during-iteration issues
        combatants = list(ENGAGEMENTS.keys())

        # Track which pairs have already exchanged blows this tick
        # to avoid double-processing (A->B and B->A in the same tick).
        resolved_pairs: Set[tuple] = set()

        for dbref in combatants:
            opponents = ENGAGEMENTS.get(dbref)
            if not opponents:
                self._remove_engagement(dbref)
                continue

            attacker = _resolve_dbref(dbref)
            if attacker is None or not _alive(attacker):
                self._remove_engagement(dbref)
                continue

            # For each opponent this attacker is fighting, execute one round
            for opp_dbref in list(opponents):
                pair_key = (min(dbref, opp_dbref), max(dbref, opp_dbref))
                if pair_key in resolved_pairs:
                    continue
                resolved_pairs.add(pair_key)

                opponent = _resolve_dbref(opp_dbref)
                if opponent is None or not _alive(opponent):
                    self._remove_engagement_pair(dbref, opp_dbref)
                    continue

                if not _same_room(attacker, opponent):
                    # Target left the room — stop combat between this pair
                    CombatHandler._disengage_pair(attacker, opponent)
                    continue

                # --- Ranged combat tick: process ranged-mode characters ---
                try:
                    from world.ranged_combat import RangedCombatHandler
                    RangedCombatHandler.tick_ranged_combat(attacker)
                except Exception:
                    pass

                # --- Bidirectional round: both combatants attack each other ---
                # Attacker -> Opponent
                _execute_attack_round(attacker, opponent)

                # Opponent -> Attacker (counter-attack), if both still alive
                # and still in the same room and still engaged.
                if (_alive(attacker) and _alive(opponent)
                        and _same_room(attacker, opponent)
                        and attacker.id in ENGAGEMENTS
                        and opp_dbref in ENGAGEMENTS.get(attacker.id, set())):
                    _execute_attack_round(opponent, attacker)

        # Refresh the status prompt for every player still engaged so it
        # stays pinned to the bottom of their screen after the tick's
        # combat spam scrolls it out of view.
        self._send_combat_prompts()

        if not ENGAGEMENTS:
            self.stop()

    def _send_combat_prompts(self):
        """Send a fresh status prompt to every player in a live engagement.

        Combat tick output is delivered as regular scrolling text, which
        pushes the transient prompt line off screen.  Re-sending the prompt
        after each tick keeps it visible and up-to-date with the latest
        HP/SP/MV values without waiting for the player to type a command.
        """
        global ENGAGEMENTS
        sent: Set[int] = set()
        for dbref in ENGAGEMENTS.keys():
            combatant = _resolve_dbref(dbref)
            if combatant is None or not _player(combatant):
                continue
            try:
                if combatant.id in sent:
                    continue
                sent.add(combatant.id)

                from typeclasses.characters import Character
                if not isinstance(combatant, Character):
                    continue
                if not combatant.attributes.get("prompt_enabled", default=True):
                    continue
                combatant.msg(prompt=combatant.get_status_prompt())
            except Exception:
                pass

    def at_stop(self):
        """Clean up when the engine shuts down."""
        global ENGAGEMENTS, COMBAT_SCRIPT_UID
        ENGAGEMENTS.clear()
        COMBAT_SCRIPT_UID = None

    def is_valid(self) -> bool:
        """Return True while engagements exist."""
        return bool(ENGAGEMENTS)

    # ------------------------------------------------------------------
    # Internal helpers for engagement table management
    # ------------------------------------------------------------------

    @staticmethod
    def _remove_engagement(dbref: int) -> None:
        """Remove all engagements for a given dbref from the table."""
        global ENGAGEMENTS
        opponents = ENGAGEMENTS.pop(dbref, set())
        for opp in opponents:
            opp_set = ENGAGEMENTS.get(opp)
            if opp_set:
                opp_set.discard(dbref)
                if not opp_set:
                    ENGAGEMENTS.pop(opp, None)

    @staticmethod
    def _remove_engagement_pair(dbref_a: int, dbref_b: int) -> None:
        """Remove a mutual engagement pair from the table."""
        global ENGAGEMENTS
        a_set = ENGAGEMENTS.get(dbref_a)
        if a_set:
            a_set.discard(dbref_b)
            if not a_set:
                ENGAGEMENTS.pop(dbref_a, None)
        b_set = ENGAGEMENTS.get(dbref_b)
        if b_set:
            b_set.discard(dbref_a)
            if not b_set:
                ENGAGEMENTS.pop(dbref_b, None)


# ---------------------------------------------------------------------------
# Resolve a dbref back to an Evennia object
# ---------------------------------------------------------------------------

def _resolve_dbref(dbref: int) -> Any:
    """Look up an Evennia object by its database id.  Returns None on failure."""
    try:
        from evennia.objects.models import ObjectDB
        return ObjectDB.objects.filter(id=dbref).first()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------------

def _degrade_equipment_on_hit(attacker: Any, defender: Any) -> None:
    """
    Degrade durability of the attacker's weapon and the defender's armor
    when a hit lands.

    Durability reaches 0 -> item is "broken".  This is intentionally
    best-effort and safely no-ops when equipment attributes are absent
    (e.g. in tests using light mocks).
    """
    try:
        from world.mob_equipment import degrade_equipment_slots
        degrade_equipment_slots(attacker, ("right_hand", "two_hand", "left_hand", "hands"), 1)
        degrade_equipment_slots(defender, ("head", "torso", "legs", "feet", "left_hand"), 1)
    except Exception:
        pass


def _is_brief_combat(character: Any) -> bool:
    """Return True if the character has brief combat mode enabled."""
    try:
        return character.attributes.get("combat_brief", False)
    except Exception:
        return False


def _apply_damage_msg(attacker: Any, defender: Any, damage: int,
                      is_crit: bool = False, absorbed: int = 0,
                      is_offhand: bool = False, is_ranged: bool = False,
                      skill_name: str = "") -> None:
    """Apply HP damage to defender and send MajorMUD-style messages.

    Also fires ``defender.at_damage`` so mobs can retaliate (lock onto the
    attacker and begin counter-attacking) when they first take a hit.
    """
    try:
        current_hp = defender.attributes.get("hp", 0)
    except Exception:
        return
    actual = min(damage, max(0, current_hp))
    new_hp = max(0, current_hp - actual)
    try:
        defender.attributes.add("hp", new_hp)
    except Exception:
        return

    # Notify the defender they were hit and allow retaliation hooks to fire.
    try:
        defender.at_damage(actual, attacker)
    except Exception:
        pass

    aname = attacker.key if hasattr(attacker, "key") else "Someone"
    dname = defender.key if hasattr(defender, "key") else "something"

    crit_part = " |Y|hCRITICAL!|n" if is_crit else ""
    absorb_part = f" |b[Armor absorbs {absorbed}]|n" if absorbed > 0 else ""
    offhand_part = " |w(off-hand)|n" if is_offhand else ""
    ranged_part = " |c(ranged)|n" if is_ranged else ""
    skill_part = f" |M[{skill_name}]|n" if skill_name else ""

    # Brief mode: only show damage numbers, no flavor text
    if _is_brief_combat(attacker):
        attacker.msg(
            f"|r-{actual} HP -> {dname}|n{crit_part}{offhand_part}{ranged_part}{skill_part}"
        )
    else:
        attacker.msg(
            "|rYou hit {dname} for {actual} damage!|n{crit_part}{absorb_part}{offhand_part}{ranged_part}{skill_part}".format(
                dname=dname, actual=actual, crit_part=crit_part, absorb_part=absorb_part,
                offhand_part=offhand_part, ranged_part=ranged_part, skill_part=skill_part
            )
        )

    if _player(defender):
        if _is_brief_combat(defender):
            defender.msg(
                f"|r-{actual} HP <- {aname}|n{crit_part}{offhand_part}{ranged_part}{skill_part}"
            )
        else:
            defender.msg(
                "|r{aname} hits you for {actual} damage!|n{crit_part}{absorb_part}{offhand_part}{ranged_part}{skill_part}".format(
                    aname=aname, actual=actual, crit_part=crit_part, absorb_part=absorb_part,
                    offhand_part=offhand_part, ranged_part=ranged_part, skill_part=skill_part
                )
            )

    location = getattr(attacker, "location", None)
    if location:
        exclude = [attacker, defender] if _player(defender) else [attacker]
        location.msg_contents(
            "|r{aname} hits {dname} for {actual} damage!|n{crit_part}{absorb_part}{offhand_part}{ranged_part}{skill_part}".format(
                aname=aname, dname=dname, actual=actual, crit_part=crit_part, absorb_part=absorb_part,
                offhand_part=offhand_part, ranged_part=ranged_part, skill_part=skill_part
            ),
            exclude=exclude,
        )


# ---------------------------------------------------------------------------
# Round execution
# ---------------------------------------------------------------------------

def _execute_attack_round(attacker: Any, defender: Any) -> None:
    """Execute one full attack round: hit roll -> damage -> apply -> death check.

    Handles:
      - Stunned state (skip round)
      - Queued combat skills (kick, bash, backstab, disarm)
      - Ranged weapons (bows/crossbows)
      - Two-weapon fighting (off-hand attack)
      - Standard melee attack
      - Rogue poison-on-hit (Phase 2.2)
      - Necromancer minion combat ticks (Phase 2.2)
      - Monk ki regeneration (Phase 2.2)
    """
    aname = attacker.key if hasattr(attacker, "key") else "Someone"
    dname = defender.key if hasattr(defender, "key") else "something"

    # Phase 2.2: Monk ki regeneration on each combat tick
    try:
        from world.monk_system import regenerate_ki
        regenerate_ki(attacker)
    except Exception:
        pass

    # Phase 2.2: Necromancer minions attack alongside master
    try:
        from world.necromancer_system import minion_combat_tick
        minion_msgs = minion_combat_tick(attacker, defender)
        for msg in minion_msgs:
            attacker.msg(msg)
    except Exception:
        pass

    # Safety: no combat in safe zones
    try:
        loc = attacker.location
        if loc and loc.attributes.get("safe_zone", False):
            if _player(attacker):
                attacker.msg("|rCombat is not allowed in safe zones.|n")
            CombatHandler.stop_combat(attacker)
            return
    except Exception:
        pass

    # --- Stun check: stunned characters skip their attack round ---
    if _is_stunned(attacker):
        if _player(attacker):
            attacker.msg("|mYou are stunned and cannot act!|n")
        if _player(defender):
            defender.msg(f"|m{aname} is stunned and cannot act.|n")
        loc = getattr(attacker, "location", None)
        if loc:
            exclude = [attacker, defender] if _player(defender) else [attacker]
            loc.msg_contents(f"|m{aname} reels, stunned!|n", exclude=exclude)
        return

    # --- Phase 5: Mob flee/morale check ---
    from world.mob_ai import should_mob_flee, attempt_mob_flee
    if not _player(attacker) and should_mob_flee(attacker):
        success, msg = attempt_mob_flee(attacker)
        if success:
            return  # Mob fled successfully
        # On failure, attacker still gets their normal attack this round

    # --- Phase 5: NPC spellcasting in combat ---
    from world.mob_ai import decide_npc_spell, npc_cast_spell
    if not _player(attacker):
        spell_decision = decide_npc_spell(attacker, defender)
        if spell_decision:
            spell_key, spell_target = spell_decision
            loc = getattr(attacker, "location", None)
            if loc:
                loc.msg_contents(
                    f"|b{aname} chants arcane words...|n",
                    exclude=[attacker] if not _player(defender) else [attacker, defender],
                )
            npc_cast_spell(attacker, spell_key, spell_target)
            return  # Spell takes the attack round

    # --- Phase 5: Mob combat skill usage ---
    from world.mob_ai import select_mob_combat_skill
    if not _player(attacker):
        mob_skill = select_mob_combat_skill(attacker)
        if mob_skill:
            # Queue the skill temporarily for this round
            try:
                if hasattr(attacker, "ndb"):
                    attacker.ndb.queued_skill = mob_skill
            except Exception:
                pass

    # --- Check for queued combat skill ---
    skill_name = _get_queued_skill(attacker)
    if skill_name:
        _execute_skill_round(attacker, defender, skill_name)
        return

    # --- Ranged attack ---
    if _is_ranged_weapon(attacker):
        _execute_ranged_round(attacker, defender)
        return

    # --- Standard melee attack ---
    # Hit roll
    if not _hit_roll(attacker, defender):
        if not _is_brief_combat(attacker):
            attacker.msg(f"You swing at {dname} and miss!")
        if _player(defender) and not _is_brief_combat(defender):
            defender.msg(f"{aname} swings at you and misses!")
        loc = getattr(attacker, "location", None)
        if loc:
            exclude = [attacker, defender] if _player(defender) else [attacker]
            loc.msg_contents(f"{aname} swings at {dname} and misses!", exclude=exclude)
        return

    # Hit — calculate damage
    result = _damage(attacker, defender)
    dmg = result.get("damage", MIN_DAMAGE)
    is_crit = result.get("crit", False)
    absorbed = result.get("absorbed", 0)

    _apply_damage_msg(attacker, defender, dmg, is_crit=is_crit, absorbed=absorbed)

    # Equipment durability degradation on successful hit.
    _degrade_equipment_on_hit(attacker, defender)

    # Phase 2.2: Rogue poison-on-hit (apply poison when weapon is coated)
    try:
        from world.rogue_system import apply_poison_on_hit
        poison_msg = apply_poison_on_hit(attacker, defender)
        if poison_msg:
            attacker.msg(poison_msg)
            if _player(defender):
                defender.msg(poison_msg)
    except Exception:
        pass

    # Racial passive: stun chance on hit (Minotaur +10%).
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(attacker)
        stun_pct = racial.get("stun_chance_pct", 0)
        if stun_pct > 0 and random.random() < (stun_pct / 100.0):
            if hasattr(defender, "attributes"):
                defender.attributes.add("stunned", True)
                defender.msg("|mYou have been stunned by a mighty blow!|n")
                from evennia.utils import delay
                delay(STUN_DURATION_SECONDS, lambda t=defender: t.attributes.add("stunned", False) if hasattr(t, "attributes") else None)
    except Exception:
        pass

    # Death check
    if not _alive(defender):
        _handle_target_death(attacker, defender)
        return

    # --- Two-weapon fighting: off-hand attack ---
    if _can_dual_wield(attacker) and _has_offhand_weapon(attacker):
        _execute_offhand_round(attacker, defender)


def _execute_ranged_round(attacker: Any, defender: Any) -> None:
    """Execute a ranged attack round (bow/crossbow)."""
    aname = attacker.key if hasattr(attacker, "key") else "Someone"
    dname = defender.key if hasattr(defender, "key") else "something"

    # Ranged hit roll (uses DEX bonus instead of STR)
    if not _hit_roll(attacker, defender):
        if not _is_brief_combat(attacker):
            attacker.msg(f"Your shot at {dname} misses!")
        if _player(defender) and not _is_brief_combat(defender):
            defender.msg(f"{aname} shoots at you and misses!")
        loc = getattr(attacker, "location", None)
        if loc:
            exclude = [attacker, defender] if _player(defender) else [attacker]
            loc.msg_contents(f"{aname} shoots at {dname} and misses!", exclude=exclude)
        return

    # Ranged damage uses DEX for bonus instead of STR
    from world.damage_formulas import calculate_melee_damage, DamageType
    wd = _weapon_damage(attacker)
    try:
        from world.mob_equipment import get_equipped_weapon_damage_type
        dt_str = get_equipped_weapon_damage_type(attacker)
        dt = DamageType(dt_str)
    except Exception:
        dt = DamageType.PIERCE

    result = calculate_melee_damage(attacker, defender, wd, dt)
    dmg = result.get("damage", MIN_DAMAGE)
    is_crit = result.get("crit", False)
    absorbed = result.get("absorbed", 0)

    _apply_damage_msg(attacker, defender, dmg, is_crit=is_crit, absorbed=absorbed,
                      is_ranged=True)

    # Death check
    if not _alive(defender):
        _handle_target_death(attacker, defender)


def _execute_offhand_round(attacker: Any, defender: Any) -> None:
    """Execute an off-hand attack with reduced damage and accuracy.

    Uses the ``thac0_penalty`` parameter on ``_hit_roll()`` instead of
    monkey-patching the module-level ``_thac0`` function, making this
    safe for any future concurrent processing model.
    """
    aname = attacker.key if hasattr(attacker, "key") else "Someone"
    dname = defender.key if hasattr(defender, "key") else "something"

    # Off-hand hit roll with penalty passed directly to _hit_roll.
    penalty = abs(OFFHAND_HIT_PENALTY)

    if not _hit_roll(attacker, defender, thac0_penalty=penalty):
        if not _is_brief_combat(attacker):
            attacker.msg(f"Your off-hand swing at {dname} misses!")
        return

    # Off-hand damage (reduced)
    from world.damage_formulas import calculate_melee_damage, DamageType
    wd = max(1, int(_weapon_damage(attacker) * OFFHAND_DAMAGE_MULT))
    try:
        from world.mob_equipment import get_equipped_weapon_damage_type
        dt_str = get_equipped_weapon_damage_type(attacker)
        dt = DamageType(dt_str)
    except Exception:
        dt = DamageType.SLASH

    result = calculate_melee_damage(attacker, defender, wd, dt)
    dmg = result.get("damage", MIN_DAMAGE)
    is_crit = result.get("crit", False)
    absorbed = result.get("absorbed", 0)

    _apply_damage_msg(attacker, defender, dmg, is_crit=is_crit, absorbed=absorbed,
                      is_offhand=True)

    # Death check
    if not _alive(defender):
        _handle_target_death(attacker, defender)


def _get_queued_skill(character: Any) -> str:
    """Return the name of a queued combat skill, or empty string."""
    try:
        if hasattr(character, "ndb") and hasattr(character.ndb, "queued_skill"):
            skill = character.ndb.queued_skill
            if skill:
                return skill
    except Exception:
        pass
    return ""


def _clear_queued_skill(character: Any) -> None:
    """Clear the queued combat skill."""
    try:
        if hasattr(character, "ndb"):
            character.ndb.queued_skill = ""
    except Exception:
        pass


def _execute_skill_round(attacker: Any, defender: Any, skill_name: str) -> None:
    """Execute a combat skill within the auto-attack round."""
    from world.combat_skills import execute_skill_attack
    aname = attacker.key if hasattr(attacker, "key") else "Someone"

    # Clear the queued skill before execution to prevent re-triggering
    _clear_queued_skill(attacker)

    msg = execute_skill_attack(attacker, defender, skill_name)
    if _player(attacker):
        attacker.msg(msg)


# ---------------------------------------------------------------------------
# Death handling
# ---------------------------------------------------------------------------

def _handle_target_death(killer: Any, victim: Any) -> None:
    """
    Handle death of a combat target.
    NPCs: immediate death -> _handle_defeat.
    Players: UNCONSCIOUS with bleed-out timer (allies can revive).
    """
    global ENGAGEMENTS

    vname = victim.key if hasattr(victim, "key") else "something"
    kname = killer.key if hasattr(killer, "key") else "Someone"

    from world.combat_state import CombatStateMachine, CombatState

    # --- NPC death ---
    if not _player(victim):
        CombatStateMachine.set_state(victim, CombatState.DEAD)
        loc = getattr(victim, "location", None)
        if loc:
            loc.msg_contents(f"|R{vname} drops to the ground, dead.|n")

        # Remove all engagements involving victim
        CombatEngine._remove_engagement(victim.id)

        # Stop any legacy combat script on victim
        try:
            victim_script = getattr(victim.ndb, "combat_script", None)
            if victim_script:
                victim_script.stop()
        except Exception:
            pass
        if hasattr(victim, "ndb"):
            try:
                victim.ndb.combat_target = None
                victim.ndb.in_combat = False
            except Exception:
                pass

        try:
            from world.combat import _handle_defeat
            _handle_defeat(victim, killer)
        except Exception:
            pass
        return

    # --- Player death ---
    if CombatStateMachine.get_state(victim) == CombatState.UNCONSCIOUS:
        # Already bleeding out — finishing blow
        CombatStateMachine.set_state(victim, CombatState.DEAD)
        loc = getattr(victim, "location", None)
        if loc:
            loc.msg_contents(f"|R{vname} has been slain while unconscious!|n")

        CombatEngine._remove_engagement(victim.id)
        try:
            victim_script = getattr(victim.ndb, "combat_script", None)
            if victim_script:
                victim_script.stop()
        except Exception:
            pass
        if hasattr(victim, "ndb"):
            try:
                victim.ndb.combat_target = None
                victim.ndb.in_combat = False
            except Exception:
                pass

        try:
            from world.combat import _handle_defeat
            _handle_defeat(victim, killer)
        except Exception:
            pass
        CombatStateMachine.set_state(victim, CombatState.IDLE)
        return

    # First time hitting 0 HP: UNCONSCIOUS with bleed-out
    CombatStateMachine.set_state(victim, CombatState.UNCONSCIOUS)
    UNCONSCIOUS_BLEED_SECONDS = 60
    try:
        victim.attributes.add("unconscious_expires", time.time() + UNCONSCIOUS_BLEED_SECONDS)
    except Exception:
        pass

    loc = getattr(victim, "location", None)
    if loc:
        loc.msg_contents(
            f"|R{vname} collapses, unconscious and bleeding out!|n"
            f"|y(Allies have {UNCONSCIOUS_BLEED_SECONDS}s to revive them.)|n"
        )

    # Remove all engagements involving victim
    CombatEngine._remove_engagement(victim.id)

    try:
        victim_script = getattr(victim.ndb, "combat_script", None)
        if victim_script:
            victim_script.stop()
    except Exception:
        pass
    if hasattr(victim, "ndb"):
        try:
            victim.ndb.combat_target = None
            victim.ndb.in_combat = False
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CombatHandler — public API
# ---------------------------------------------------------------------------

class CombatHandler:
    """Static API for starting, stopping, and querying combat."""

    @staticmethod
    def is_in_combat(character: Any) -> bool:
        """Return True if the character has an active engagement."""
        global ENGAGEMENTS
        try:
            return character.id in ENGAGEMENTS
        except Exception:
            return False

    @staticmethod
    def get_targets(character: Any):
        """Return a list of opponents the character is currently fighting."""
        # Try direct ndb list first (works without DB)
        try:
            ndb_list = character.ndb.combat_targets
            if ndb_list and isinstance(ndb_list, list):
                alive = [t for t in ndb_list if hasattr(t, "id") and _alive(t)]
                if alive:
                    return alive
        except Exception:
            pass

        # Fall back: resolve via DB lookup from ENGAGEMENTS table
        global ENGAGEMENTS
        try:
            opponents = ENGAGEMENTS.get(character.id, set())
        except Exception:
            return []
        result = []
        for dbref in opponents:
            obj = _resolve_dbref(dbref)
            if obj is None:
                try:
                    ndb_target = character.ndb.combat_target
                    if ndb_target is not None and ndb_target.id == dbref:
                        obj = ndb_target
                except Exception:
                    pass
            if obj is not None:
                result.append(obj)
        return result

    @staticmethod
    def get_target(character: Any):
        """Return the first opponent (convenience for single-target combat)."""
        targets = CombatHandler.get_targets(character)
        return targets[0] if targets else None

    # ------------------------------------------------------------------
    # Start combat
    # ------------------------------------------------------------------

    @staticmethod
    def start_combat(character: Any, target: Any) -> None:
        """
        Register an engagement between character and target.

        Creates the global CombatEngine script if it doesn't exist yet.
        Engages both sides automatically.  Sends appropriate messages.
        Executes one immediate attack round for the initiator.
        """
        global ENGAGEMENTS, COMBAT_SCRIPT_UID

        if character is None or target is None:
            return
        if character == target:
            if _player(character):
                character.msg("|rYou cannot attack yourself.|n")
            return

        # Already fighting this exact target?
        if CombatHandler.is_in_combat(character):
            existing = ENGAGEMENTS.get(character.id, set())
            if target.id in existing:
                if _player(character):
                    character.msg(f"|yYou are already attacking {target.key}!|n")
                return

        # --- Store direct refs in ndb for fast retrieval ---
        try:
            character.ndb.combat_target = target
            if not hasattr(character.ndb, "combat_targets") or character.ndb.combat_targets is None:
                character.ndb.combat_targets = []
            character.ndb.combat_targets.append(target)

            target.ndb.combat_target = character
            if not hasattr(target.ndb, "combat_targets") or target.ndb.combat_targets is None:
                target.ndb.combat_targets = []
            target.ndb.combat_targets.append(character)
        except Exception:
            pass

        # --- Register engagement ---
        ENGAGEMENTS.setdefault(character.id, set()).add(target.id)
        ENGAGEMENTS.setdefault(target.id, set()).add(character.id)

        # --- Ensure the global CombatEngine is running ---
        if COMBAT_SCRIPT_UID is None:
            # Host the script on the attacker's location (or self as fallback)
            host = getattr(character, "location", None) or character
            try:
                engine = host.scripts.add(CombatEngine)
                if engine:
                    COMBAT_SCRIPT_UID = engine.id
            except Exception:
                pass

        # --- State machine ---
        from world.combat_state import CombatStateMachine, CombatState
        CombatStateMachine.set_state(character, CombatState.ENGAGING)
        CombatStateMachine.set_state(character, CombatState.FIGHTING)
        CombatStateMachine.set_state(target, CombatState.ENGAGING)
        CombatStateMachine.set_state(target, CombatState.FIGHTING)

        # --- Messages ---
        if _player(character):
            character.msg(f"|RYou engage {target.key} in combat!|n")
        if _player(target):
            target.msg(f"|R{character.key} attacks you!|n")
        loc = getattr(character, "location", None)
        if loc:
            exclude = [character, target] if _player(target) else [character]
            loc.msg_contents(
                f"|R{character.key} engages {target.key} in combat!|n",
                exclude=exclude,
            )

        # --- Social aggro ---
        try:
            from world.mob_ai import trigger_social_aggro
            trigger_social_aggro(target, character)
        except Exception:
            pass

        # --- First attack round (immediate) ---
        _execute_attack_round(character, target)

    # ------------------------------------------------------------------
    # Stop combat
    # ------------------------------------------------------------------

    @staticmethod
    def stop_combat(character: Any) -> None:
        """
        Disengage a character from all combat.

        Removes all engagement entries for this character.  If the opponent
        was only fighting this character (and no one else), the opponent is
        also disengaged.
        """
        global ENGAGEMENTS
        if character is None:
            return
        try:
            cid = character.id
        except Exception:
            return

        opponents = ENGAGEMENTS.pop(cid, set())
        for opp_id in opponents:
            opp_set = ENGAGEMENTS.get(opp_id)
            if opp_set:
                opp_set.discard(cid)
                if not opp_set:
                    ENGAGEMENTS.pop(opp_id, None)
            # Also clear ndb on opponent
            opp_obj = _resolve_dbref(opp_id)
            if opp_obj and hasattr(opp_obj, "ndb"):
                try:
                    opp_obj.ndb.in_combat = False
                    opp_obj.ndb.combat_target = None
                    opp_obj.ndb.combat_targets = []
                except Exception:
                    pass

        # Clear ndb on character
        if hasattr(character, "ndb"):
            try:
                character.ndb.in_combat = False
                character.ndb.combat_target = None
                character.ndb.combat_targets = []
            except Exception:
                pass

        if _player(character):
            character.msg("|yYou disengage from combat.|n")

    @staticmethod
    def _disengage_pair(a: Any, b: Any) -> None:
        """Remove a single engagement pairing between two characters."""
        global ENGAGEMENTS
        try:
            aid = a.id
            bid = b.id
        except Exception:
            return
        a_set = ENGAGEMENTS.get(aid)
        if a_set:
            a_set.discard(bid)
            if not a_set:
                ENGAGEMENTS.pop(aid, None)
        b_set = ENGAGEMENTS.get(bid)
        if b_set:
            b_set.discard(aid)
            if not b_set:
                ENGAGEMENTS.pop(bid, None)

        if _player(a):
            a.msg(f"|y{b.key} has left combat range.|n")
        if _player(b):
            b.msg(f"|y{a.key} has left combat range.|n")

    # ------------------------------------------------------------------
    # Flee
    # ------------------------------------------------------------------

    @staticmethod
    def attempt_flee(character: Any) -> bool:
        """
        Attempt to flee from combat.  Roll flee chance.  On success, stop
        combat.  On failure, the opponent gets a free attack this round.
        Returns True if the flee attempt succeeded.
        """
        if not CombatHandler.is_in_combat(character):
            if _player(character):
                character.msg("|yYou are not in combat.|n")
            return False

        target = CombatHandler.get_target(character)
        if target is None:
            CombatHandler.stop_combat(character)
            return True

        chance = _flee_chance(character, target)
        roll = random.random()
        success = roll < chance

        aname = character.key if hasattr(character, "key") else "Someone"
        tname = target.key if hasattr(target, "key") else "something"

        if _player(character):
            character.msg(f"|yYou attempt to flee from {tname}!|n")
        if _player(target):
            target.msg(f"|y{aname} attempts to flee!|n")

        if success:
            if _player(character):
                character.msg(f"|gYou flee from combat with {tname}!|n")
            if _player(target):
                target.msg(f"|y{aname} flees from combat!|n")
            loc = getattr(character, "location", None)
            if loc:
                exclude = [character, target] if _player(target) else [character]
                loc.msg_contents(f"|y{aname} flees from combat with {tname}!|n",
                                 exclude=exclude)
            CombatHandler.stop_combat(character)
            return True
        else:
            if _player(character):
                character.msg(f"|rYou try to flee but {tname} blocks your escape!|n")
            if _player(target):
                target.msg(f"|y{aname} tries to flee but you block their escape!|n")
            loc = getattr(character, "location", None)
            if loc:
                exclude = [character, target] if _player(target) else [character]
                loc.msg_contents(
                    f"|y{aname} tries to flee from {tname} but fails!|n",
                    exclude=exclude,
                )
            # Opponent gets a free attack round
            _execute_attack_round(target, character)
            return False

    # ------------------------------------------------------------------
    # Combat skill queueing
    # ------------------------------------------------------------------

    @staticmethod
    def queue_skill(character: Any, skill_name: str) -> Tuple[bool, str]:
        """
        Queue a combat skill for the next auto-attack round.

        Args:
            character: The character using the skill.
            skill_name: The skill key (kick, bash, backstab, disarm).

        Returns:
            (success, message) tuple.
        """
        if not CombatHandler.is_in_combat(character):
            return False, "You are not in combat."

        from world.combat_skills import COMBAT_SKILLS
        skill = COMBAT_SKILLS.get(skill_name)
        if not skill:
            return False, f"Unknown skill: {skill_name}"

        # Check class permission
        from world.race_class_matrix import can_use_skill
        allowed, reason = can_use_skill(character, skill_name)
        if not allowed:
            return False, reason

        # Phase 2.3: Check talent prerequisite (skill tree gating)
        talent_prereq = skill.get("talent_prereq")
        talent_rank = skill.get("talent_rank", 0)
        if talent_prereq and talent_rank > 0:
            try:
                from world.skill_tree import _get_session, TALENT_DEFINITIONS
                session = _get_session(character)
                current_rank = session.talents.get(talent_prereq, 0)
                if current_rank < talent_rank:
                    talent_name = TALENT_DEFINITIONS.get(talent_prereq, {}).get("name", talent_prereq)
                    return False, f"You need {talent_name} rank {talent_rank} to use {skill['name']} (you have rank {current_rank})."
            except Exception:
                pass

        # Check level
        char_level = character.attributes.get("level", 1) if hasattr(character, "attributes") else 1
        if char_level < skill["min_level"]:
            return False, f"You must be level {skill['min_level']} to use {skill['name']}."

        # Check stamina
        stamina = character.attributes.get("stamina", default=100) if hasattr(character, "attributes") else 100
        if stamina < skill["stamina_cost"]:
            return False, f"Not enough stamina for {skill['name']} (need {skill['stamina_cost']}, have {stamina})."

        # Check cooldown
        cooldowns = character.attributes.get("skill_cooldowns", {}) if hasattr(character, "attributes") else {}
        remaining = cooldowns.get(skill_name, 0) - time.time()
        if remaining > 0:
            return False, f"{skill['name']} is on cooldown for {int(remaining)}s."

        # Check stealth requirement for backstab
        if skill.get("requires_stealth", False):
            is_stealthed = character.attributes.get("stealthed", False) if hasattr(character, "attributes") else False
            if not is_stealthed:
                return False, "You must be hidden to backstab."

        # Queue the skill
        try:
            if hasattr(character, "ndb"):
                character.ndb.queued_skill = skill_name
        except Exception:
            return False, "Could not queue skill."

        return True, f"You prepare to use {skill['name']}!"


# ---------------------------------------------------------------------------
# Convenience re-exports
# ---------------------------------------------------------------------------

def is_in_combat(character: Any) -> bool:
    """Convenience wrapper for CombatHandler.is_in_combat()."""
    return CombatHandler.is_in_combat(character)


# ---------------------------------------------------------------------------
# Backward-compatibility aliases for modules that imported old names
# ---------------------------------------------------------------------------

_roll_attack_hit = _hit_roll
_calculate_damage = _damage
_calculate_flee_chance = _flee_chance
_is_alive = _alive
_is_player = _player
_get_stat = _stat
_get_level = _level
_get_weapon_damage = _weapon_damage


def _apply_damage_to_target(attacker: Any, defender: Any, damage: int,
                            is_crit: bool = False, absorbed: int = 0) -> None:
    """Backward-compat alias for _apply_damage_msg."""
    _apply_damage_msg(attacker, defender, damage, is_crit=is_crit, absorbed=absorbed)


# ---------------------------------------------------------------------------
# ENGAGEMENTS table rebuild on @reload
# ---------------------------------------------------------------------------

def rebuild_engagements_from_active_combat() -> int:
    """
    Rebuild the in-memory ENGAGEMENTS table from active combat scripts
    and mob AI states after a server reload.

    Scans all objects that have ndb.in_combat or ndb.combat_target set
    and re-registers their engagements.  This prevents combat state loss
    on @reload.

    Returns the number of engagements rebuilt.
    """
    global ENGAGEMENTS, COMBAT_SCRIPT_UID

    count = 0
    ENGAGEMENTS.clear()
    COMBAT_SCRIPT_UID = None

    try:
        from evennia.objects.models import ObjectDB
        from typeclasses.characters import Character

        # Scan all objects for combat state
        for obj in ObjectDB.objects.all():
            if not isinstance(obj, Character):
                continue
            if not hasattr(obj, "ndb"):
                continue

            try:
                targets = getattr(obj.ndb, "combat_targets", None)
                if targets and isinstance(targets, list):
                    for target in targets:
                        if target is None:
                            continue
                        try:
                            tid = target.id
                            oid = obj.id
                            ENGAGEMENTS.setdefault(oid, set()).add(tid)
                            ENGAGEMENTS.setdefault(tid, set()).add(oid)
                            count += 1
                        except Exception:
                            continue
            except Exception:
                continue

        # If we rebuilt any engagements, restart the combat engine
        if count > 0 and ENGAGEMENTS:
            # Find a suitable host for the combat engine
            try:
                first_dbref = next(iter(ENGAGEMENTS))
                first_obj = _resolve_dbref(first_dbref)
                if first_obj:
                    host = getattr(first_obj, "location", None) or first_obj
                    engine = host.scripts.add(CombatEngine)
                    if engine:
                        COMBAT_SCRIPT_UID = engine.id
            except Exception:
                pass

    except Exception:
        pass

    return count