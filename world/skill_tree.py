"""
Skill Tree / Talent Point-Buy System for 'rop' — Phase 14 Sprint 1

Provides:
  - TALENT_DEFINITIONS — 15 talents across 3 trees (Martial, Arcane, Survival)
  - TalentSession — tracks unspent talent points + purchased ranks per character
  - award_talent_points(character, level) — called on level-up
  - purchase_talent(character, talent_key) -> (bool, str)
  - get_talent_bonuses(character) -> Dict[str, int] — cumulative stat bonuses
  - CmdTalents, CmdTalentBuy, CmdTalentReset — player commands
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from commands.command import Command


# ---------------------------------------------------------------------------
# Talent definitions — 3 trees, 5 talents each
# ---------------------------------------------------------------------------

TALENT_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    # =====================================================================
    # MARTIAL TREE — physical power, weapon skill, toughness
    # =====================================================================
    "weapon_specialist": {
        "name": "Weapon Specialist",
        "tree": "Martial",
        "max_rank": 5,
        "base_cost": 1,
        "cost_per_rank": 1,             # cost = base_cost + rank * cost_per_rank
        "desc": "Each rank grants +1 melee damage.",
        "effect": {"melee_damage": 1},
        "prereq": None,
        "prereq_rank": 0,
    },
    "armor_mastery": {
        "name": "Armor Mastery",
        "tree": "Martial",
        "max_rank": 5,
        "base_cost": 1,
        "cost_per_rank": 1,
        "desc": "Each rank increases your worn armor value by 1.",
        "effect": {"armor_bonus": 1},
        "prereq": None,
        "prereq_rank": 0,
    },
    "iron_grip": {
        "name": "Iron Grip",
        "tree": "Martial",
        "max_rank": 3,
        "base_cost": 2,
        "cost_per_rank": 1,
        "desc": "Each rank grants +1 THAC0 (better accuracy).",
        "effect": {"thac0_bonus": 1},
        "prereq": "weapon_specialist",
        "prereq_rank": 2,
    },
    "berserker_rage": {
        "name": "Berserker Rage",
        "tree": "Martial",
        "max_rank": 3,
        "base_cost": 2,
        "cost_per_rank": 1,
        "desc": "Each rank grants +2% critical strike chance.",
        "effect": {"crit_chance_pct": 2},
        "prereq": None,
        "prereq_rank": 0,
    },
    "unbreakable": {
        "name": "Unbreakable",
        "tree": "Martial",
        "max_rank": 3,
        "base_cost": 3,
        "cost_per_rank": 1,
        "desc": "Each rank grants +3 max HP per character level.",
        "effect": {"hp_per_level": 3},
        "prereq": "armor_mastery",
        "prereq_rank": 3,
    },

    # =====================================================================
    # ARCANE TREE — magic power, mana, spell potency
    # =====================================================================
    "arcane_focus": {
        "name": "Arcane Focus",
        "tree": "Arcane",
        "max_rank": 5,
        "base_cost": 1,
        "cost_per_rank": 1,
        "desc": "Each rank grants +1 spell damage.",
        "effect": {"spell_damage": 1},
        "prereq": None,
        "prereq_rank": 0,
    },
    "mana_reservoir": {
        "name": "Mana Reservoir",
        "tree": "Arcane",
        "max_rank": 5,
        "base_cost": 1,
        "cost_per_rank": 1,
        "desc": "Each rank grants +5 max mana.",
        "effect": {"max_mana": 5},
        "prereq": None,
        "prereq_rank": 0,
    },
    "spell_penetration": {
        "name": "Spell Penetration",
        "tree": "Arcane",
        "max_rank": 3,
        "base_cost": 2,
        "cost_per_rank": 1,
        "desc": "Each rank ignores 2% of the target's magic resistance.",
        "effect": {"spell_pen_pct": 2},
        "prereq": "arcane_focus",
        "prereq_rank": 2,
    },
    "arcane_shielding": {
        "name": "Arcane Shielding",
        "tree": "Arcane",
        "max_rank": 3,
        "base_cost": 2,
        "cost_per_rank": 1,
        "desc": "Each rank grants +3% magic resistance.",
        "effect": {"magic_resist_pct": 3},
        "prereq": None,
        "prereq_rank": 0,
    },
    "channeling_mastery": {
        "name": "Channeling Mastery",
        "tree": "Arcane",
        "max_rank": 3,
        "base_cost": 3,
        "cost_per_rank": 1,
        "desc": "Each rank reduces spell cooldowns by 5%.",
        "effect": {"spell_cdr_pct": 5},
        "prereq": "arcane_focus",
        "prereq_rank": 3,
    },

    # =====================================================================
    # SURVIVAL TREE — evasion, recovery, utility
    # =====================================================================
    "dodge": {
        "name": "Dodge",
        "tree": "Survival",
        "max_rank": 5,
        "base_cost": 1,
        "cost_per_rank": 1,
        "desc": "Each rank grants +1 AC (harder to hit).",
        "effect": {"ac_bonus": 1},
        "prereq": None,
        "prereq_rank": 0,
    },
    "vitality": {
        "name": "Vitality",
        "tree": "Survival",
        "max_rank": 5,
        "base_cost": 1,
        "cost_per_rank": 1,
        "desc": "Each rank grants +1 HP regen per tick.",
        "effect": {"hp_regen": 1},
        "prereq": None,
        "prereq_rank": 0,
    },
    "fleet_footed": {
        "name": "Fleet-Footed",
        "tree": "Survival",
        "max_rank": 3,
        "base_cost": 2,
        "cost_per_rank": 1,
        "desc": "Each rank grants +5 max movement points.",
        "effect": {"max_mv": 5},
        "prereq": "dodge",
        "prereq_rank": 2,
    },
    "scavenger": {
        "name": "Scavenger",
        "tree": "Survival",
        "max_rank": 3,
        "base_cost": 2,
        "cost_per_rank": 1,
        "desc": "Each rank grants +5% bonus gold from all sources.",
        "effect": {"gold_bonus_pct": 5},
        "prereq": None,
        "prereq_rank": 0,
    },
    "second_wind": {
        "name": "Second Wind",
        "tree": "Survival",
        "max_rank": 3,
        "base_cost": 3,
        "cost_per_rank": 1,
        "desc": "Each rank grants +2 stamina regen per tick.",
        "effect": {"stamina_regen": 2},
        "prereq": "vitality",
        "prereq_rank": 3,
    },
}


# ---------------------------------------------------------------------------
# Talent session per character
# ---------------------------------------------------------------------------

@dataclass
class TalentSession:
    """Tracks unspent talent points and purchased talent ranks for a character."""
    talent_points: int = 0
    talents: Dict[str, int] = field(default_factory=dict)  # talent_key -> rank


def _get_session(character: Any) -> TalentSession:
    """Retrieve or create a TalentSession for the character."""
    if not hasattr(character, "attributes"):
        return TalentSession()
    session = character.attributes.get("talent_session", default=None)
    if session is None or not isinstance(session, TalentSession):
        session = TalentSession()
        character.attributes.add("talent_session", session)
    return session


def _save_session(character: Any, session: TalentSession) -> None:
    """Persist the talent session back to the character."""
    if hasattr(character, "attributes"):
        character.attributes.add("talent_session", session)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Talent points awarded per level, scaled by class archetype
TALENT_POINTS_PER_LEVEL: Dict[str, int] = {
    "Warrior": 2, "Paladin": 2, "Cleric": 2, "Mage": 2,
    "Rogue": 2, "Warlock": 2, "Druid": 2, "Ranger": 2,
    "Monk": 2, "Necromancer": 2,
}


def award_talent_points(character: Any, level: int) -> int:
    """
    Award talent points on level-up.

    Called from ``Character._check_level_up()``.

    Returns the number of points awarded.
    """
    char_class = character.attributes.get("class", default="Warrior") if hasattr(character, "attributes") else "Warrior"
    points = TALENT_POINTS_PER_LEVEL.get(char_class, 2)
    session = _get_session(character)
    session.talent_points += points
    _save_session(character, session)
    character.msg(f"|cYou have earned {points} talent point(s)! (Total unspent: {session.talent_points})|n")
    return points


def purchase_talent(character: Any, talent_key: str) -> Tuple[bool, str]:
    """
    Attempt to purchase one rank of a talent.

    Returns (success, message).
    """
    talent = TALENT_DEFINITIONS.get(talent_key)
    if not talent:
        return False, "Unknown talent."

    session = _get_session(character)
    current_rank = session.talents.get(talent_key, 0)
    max_rank = talent["max_rank"]

    if current_rank >= max_rank:
        return False, f"{talent['name']} is already at max rank ({max_rank})."

    # Check prerequisite
    prereq_key = talent.get("prereq")
    prereq_rank = talent.get("prereq_rank", 0)
    if prereq_key and prereq_rank > 0:
        prereq_current = session.talents.get(prereq_key, 0)
        if prereq_current < prereq_rank:
            prereq_name = TALENT_DEFINITIONS.get(prereq_key, {}).get("name", prereq_key)
            return False, f"Requires {prereq_name} at rank {prereq_rank} (you have {prereq_current})."

    # Calculate cost
    base = talent["base_cost"]
    cost_per = talent["cost_per_rank"]
    cost = base + (current_rank * cost_per)

    if session.talent_points < cost:
        return False, f"Not enough talent points. Need {cost}, have {session.talent_points}."

    # Purchase
    session.talent_points -= cost
    session.talents[talent_key] = current_rank + 1
    _save_session(character, session)

    new_rank = current_rank + 1
    return True, f"You purchase {talent['name']} rank {new_rank}/{max_rank} for {cost} TP. ({session.talent_points} TP remaining)"


def get_talent_bonuses(character: Any) -> Dict[str, int]:
    """
    Return cumulative passive stat bonuses from all purchased talents.

    Called by combat, damage, and recovery systems to apply
    talent bonuses to effective stats.

    Returns dict like {"melee_damage": 3, "armor_bonus": 2, ...}
    """
    session = _get_session(character)
    bonuses: Dict[str, int] = {}

    for talent_key, rank in session.talents.items():
        talent = TALENT_DEFINITIONS.get(talent_key)
        if not talent or rank <= 0:
            continue
        effect = talent.get("effect", {})
        for key, per_rank_value in effect.items():
            bonuses[key] = bonuses.get(key, 0) + (per_rank_value * rank)

    return bonuses


def get_talent_pool_bonuses(character: Any) -> Dict[str, int]:
    """
    Return the talent contributions to derived resource pools.

    These are flat/level-scaled bonuses that are applied on top of a
    character's stored base pools so they remain correct even when
    talents are purchased after a level-up:

      - ``max_hp``:  Unbreakable's hp_per_level bonus × character level
      - ``max_mana``: Mana Reservoir's flat +max mana bonus
      - ``max_mv``:   Fleet-Footed's flat +max movement bonus
    """
    bonuses = get_talent_bonuses(character)
    level = character.attributes.get("level", default=1) if hasattr(character, "attributes") else 1
    return {
        "max_hp": int(bonuses.get("hp_per_level", 0)) * int(level),
        "max_mana": int(bonuses.get("max_mana", 0)),
        "max_mv": int(bonuses.get("max_mv", 0)),
    }


def get_talent_display(character: Any) -> str:
    """Return a formatted display of all talents and their ranks for the character."""
    session = _get_session(character)

    lines = [
        "|w=== Talent Tree ===|n",
        f"|cUnspent Talent Points: |W{session.talent_points}|n",
        "",
    ]

    trees: Dict[str, List[str]] = {"Martial": [], "Arcane": [], "Survival": []}

    for talent_key, talent in TALENT_DEFINITIONS.items():
        tree = talent["tree"]
        rank = session.talents.get(talent_key, 0)
        max_rank = talent["max_rank"]

        rank_bar = ""
        for i in range(max_rank):
            if i < rank:
                rank_bar += "|g★|n"
            else:
                rank_bar += "|y☆|n"

        # Calculate next rank cost
        if rank < max_rank:
            next_cost = talent["base_cost"] + (rank * talent["cost_per_rank"])
            cost_str = f" next: {next_cost} TP"
        else:
            cost_str = " |GMAX|n"

        line = f"  {rank_bar} |c{talent['name']}|n — {talent['desc']} ({cost_str})"
        trees[tree].append(line)

    for tree in ("Martial", "Arcane", "Survival"):
        lines.append(f"|Y--- {tree} ---|n")
        lines.extend(trees[tree])
        lines.append("")

    # Total bonuses summary
    bonuses = get_talent_bonuses(character)
    if bonuses:
        lines.append("|wCumulative Bonuses:|n")
        for key, val in sorted(bonuses.items()):
            label = key.replace("_", " ").title()
            lines.append(f"  |c{label}:|n +{val}")
    else:
        lines.append("|yNo talents purchased yet.|n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

class CmdTalents(Command):
    """
    View your talent tree and purchased ranks.

    Usage:
      talents

    Displays all available talents across the three trees
    (Martial, Arcane, Survival), your current ranks, and
    cumulative bonuses.
    """

    key = "talents"
    aliases = ["talent"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        caller = self.caller
        display = get_talent_display(caller)
        caller.msg(display)


class CmdTalentBuy(Command):
    """
    Spend talent points to purchase or upgrade a talent.

    Usage:
      talent buy <talent name>

    Examples:
      talent buy Weapon Specialist
      talent buy dodge

    Talent points are earned on each level-up.  Use |ytalents|n
    to see all available talents and your current points.
    """

    key = "talent buy"
    aliases = ["tbuy"]
    locks = "cmd:all()"
    help_category = "Character"

    def parse(self):
        self.target = self.args.strip().lower().replace(" ", "_")

    def func(self):
        caller = self.caller
        if not self.target:
            caller.msg("|yUsage: talent buy <name>|n")
            return

        # Fuzzy match: try exact key, then by name
        talent_key = self.target
        if talent_key not in TALENT_DEFINITIONS:
            # Try matching by name (case-insensitive, underscore-insensitive)
            for key, talent in TALENT_DEFINITIONS.items():
                if talent["name"].lower().replace(" ", "_") == self.target:
                    talent_key = key
                    break
            else:
                caller.msg(f"|rUnknown talent '{self.args.strip()}'. Use |ytalents|r to see available talents.|n")
                return

        ok, msg = purchase_talent(caller, talent_key)
        if ok:
            caller.msg(f"|g{msg}|n")
        else:
            caller.msg(f"|r{msg}|n")


class CmdTalentReset(Command):
    """
    Reset all purchased talents and refund all talent points.
    This costs gold and has a cooldown.

    Usage:
      talent reset

    Cost: 100 gold per character level.
    Cooldown: 24 hours.
    """

    key = "talent reset"
    aliases = ["treset"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        caller = self.caller
        session = _get_session(caller)

        total_spent = 0
        for talent_key, rank in session.talents.items():
            talent = TALENT_DEFINITIONS.get(talent_key)
            if not talent:
                continue
            base = talent["base_cost"]
            cost_per = talent["cost_per_rank"]
            for r in range(rank):
                total_spent += base + (r * cost_per)

        if total_spent == 0:
            caller.msg("|yYou have no talents to reset.|n")
            return

        level = caller.attributes.get("level", 1) if hasattr(caller, "attributes") else 1
        cost = level * 100

        # Check gold
        try:
            from world.economy import remove_money
            if not remove_money(caller, cost):
                caller.msg(f"|rYou need {cost} gold to reset your talents.|n")
                return
        except Exception:
            caller.msg("|rGold system unavailable.|n")
            return

        session.talent_points += total_spent
        session.talents.clear()
        _save_session(caller, session)

        caller.msg(
            f"|gTalents reset! {total_spent} talent points refunded "
            f"({session.talent_points} total). {cost} gold spent.|n"
        )