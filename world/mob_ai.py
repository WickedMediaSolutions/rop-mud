"""
Mob AI System for 'rop' — Hostility, Aggro, and Social Aggro

Provides:
  - MobDisposition enum (PASSIVE, NEUTRAL, AGGRESSIVE, GUARDIAN)
  - MobAIData dataclass
  - check_mob_aggro() — level threshold, alignment hostility
  - trigger_social_aggro() — nearby allied mobs assist
  - Phase 1.2: NPC spell usage and saving throw awareness
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, List, Tuple
import random


class MobDisposition(Enum):
    PASSIVE = "passive"       # Never attacks first
    NEUTRAL = "neutral"       # Attacks if provoked (attacked first)
    AGGRESSIVE = "aggressive" # Attacks on sight within aggro radius
    GUARDIAN = "guardian"     # Aggressive + calls nearby allies


@dataclass
class MobAIData:
    disposition: MobDisposition = MobDisposition.NEUTRAL
    aggro_radius: int = 0           # 0 = same room only, 1+ = adjacent rooms
    assist_radius: int = 0          # 0 = no social aggro, 1+ = help allies in N rooms
    assist_faction: str = ""        # Only assist mobs with matching faction tag
    leash_room: Optional[Any] = None  # Won't chase beyond this room
    max_chase_rooms: int = 3        # Max rooms to chase a fleeing player
    level_threshold: int = 5        # Won't aggro players more than N levels below

    # Phase 1.2: NPC spellcasting
    spell_list: List[str] = field(default_factory=list)  # List of spell keys
    cast_chance: float = 0.3        # Chance to cast a spell per round (0-1)
    mana_pool: int = 0              # NPC mana for spellcasting
    max_mana: int = 0               # Max NPC mana
    prefer_heal_at_pct: float = 0.3  # Cast heal when HP below this %

    # Phase 5: Morale/flee system
    morale_threshold: float = 0.20  # HP % below which mob may attempt to flee
    flee_chance: float = 0.0        # 0 = never flees, 1 = always attempts when below threshold

    # Phase 5: Mana regeneration
    mana_regen_per_tick: int = 1    # Mana regained per AI tick (out of combat)

    # Phase 5: Patrol paths
    patrol_path: List[str] = field(default_factory=list)  # List of room keys to patrol
    patrol_loop: bool = False       # True = loop, False = ping-pong
    patrol_pause_ticks: int = 2     # AI ticks to pause at each waypoint
    _patrol_idx: int = 0            # Current patrol waypoint index (internal)
    _patrol_forward: bool = True    # Direction for ping-pong (internal)
    _patrol_pause_counter: int = 0  # Ticks spent at current waypoint (internal)

    # Phase 5: Faction warfare
    aggro_other_mobs: bool = False  # True = attacks opposing faction mobs on sight


def check_mob_aggro(mob, player) -> bool:
    """Called when a player enters a room. Returns True if mob should attack."""
    ai = mob.attributes.get("mob_ai") if hasattr(mob, "attributes") else None
    if not ai:
        return False

    if ai.disposition == MobDisposition.PASSIVE:
        return False

    if ai.disposition == MobDisposition.NEUTRAL:
        return False  # Only attacks when attacked first

    # Aggressive/Guardian: check level threshold
    player_level = player.attributes.get("level", 1) if hasattr(player, "attributes") else 1
    mob_level = mob.attributes.get("level", 1) if hasattr(mob, "attributes") else 1
    if mob_level - player_level > ai.level_threshold:
        return False  # Player too low level, not worth aggro

    # Check alignment hostility
    player_align = player.attributes.get("alignment", "") if hasattr(player, "attributes") else ""
    mob_align = mob.attributes.get("alignment", "") if hasattr(mob, "attributes") else ""
    if player_align == mob_align and mob_align:
        return False  # Same faction, no aggro

    return True


def trigger_social_aggro(attacked_mob, attacker):
    """When a mob is attacked, nearby allied mobs may join the fight."""
    ai = attacked_mob.attributes.get("mob_ai") if hasattr(attacked_mob, "attributes") else None
    if not ai or ai.assist_radius <= 0:
        return

    location = attacked_mob.location if hasattr(attacked_mob, "location") else None
    if not location:
        return

    assist_faction = ai.assist_faction or (attacked_mob.attributes.get("faction", "") if hasattr(attacked_mob, "attributes") else "")

    from world.tick_combat import CombatHandler

    for obj in location.contents:
        if obj == attacked_mob or obj == attacker:
            continue
        if not hasattr(obj, "attributes"):
            continue
        obj_ai = obj.attributes.get("mob_ai")
        if not obj_ai:
            continue
        obj_faction = obj.attributes.get("faction", "")
        if assist_faction and obj_faction == assist_faction:
            # This mob assists!
            if not CombatHandler.is_in_combat(obj):
                CombatHandler.start_combat(obj, attacker)
                if hasattr(location, "msg_contents"):
                    location.msg_contents(f"|R{obj.key} rushes to aid {attacked_mob.key}!|n")


# ---------------------------------------------------------------------------
# Phase 1.2 — NPC Spell Usage & Saving Throw Awareness
# ---------------------------------------------------------------------------

def get_npc_casting_stat(mob) -> int:
    """Get the NPC's effective casting stat for spell DC calculations."""
    ai = mob.attributes.get("mob_ai") if hasattr(mob, "attributes") else None
    if ai and ai.max_mana > 0:
        # Scale casting stat based on mana pool (higher mana = stronger caster)
        return min(30, 10 + (ai.max_mana // 10))
    stats = mob.attributes.get("stats", {}) if hasattr(mob, "attributes") else {}
    if stats:
        return max(stats.get("int", 10), stats.get("wis", 10))
    return 10


def decide_npc_spell(mob, target) -> Optional[Tuple[str, Any]]:
    """
    Decide which spell an NPC should cast this round.
    Returns (spell_key, target) or None if no spell should be cast.

    Phase 1.2: NPCs now consider:
      - Their own HP (cast heals when low)
      - Target's saving throws (prefer spells the target is weak against)
      - Available mana
    """
    ai = mob.attributes.get("mob_ai") if hasattr(mob, "attributes") else None
    if not ai or not ai.spell_list:
        return None

    # Check if NPC should cast at all this round
    if random.random() > ai.cast_chance:
        return None

    # Check mana
    if ai.mana_pool <= 0:
        return None

    from world.spells import get_spell, _resolve_mana_cost

    mob_level = mob.attributes.get("level", 1) if hasattr(mob, "attributes") else 1
    mob_hp = mob.attributes.get("hp", 0) if hasattr(mob, "attributes") else 0
    mob_max_hp = mob.attributes.get("max_hp", 100) if hasattr(mob, "attributes") else 100
    hp_pct = mob_hp / max(mob_max_hp, 1)

    # Phase 1.2: Consider target's saving throws
    target_save_weakness = None
    if hasattr(target, "attributes"):
        from world.saving_throws import get_base_save, SavingThrow
        # Find the target's weakest save
        saves = {}
        for st in SavingThrow:
            saves[st] = get_base_save(target, st)
        # Higher save number = weaker save (harder to roll)
        if saves:
            target_save_weakness = max(saves, key=saves.get)

    # Prioritize healing if low on HP
    if hp_pct < ai.prefer_heal_at_pct:
        for spell_key in ai.spell_list:
            spell = get_spell(spell_key)
            if not spell:
                continue
            eff = spell["effect"]
            if eff.get("type") == "heal":
                cost = _resolve_mana_cost(spell, mob_level)
                if ai.mana_pool >= cost:
                    return (spell_key, mob)

    # Pick a random offensive spell from the list
    offensive_spells = []
    for spell_key in ai.spell_list:
        spell = get_spell(spell_key)
        if not spell:
            continue
        eff = spell["effect"]
        etype = eff.get("type", "")
        if etype in ("damage", "lifesteal", "stun", "debuff", "debuff_all"):
            cost = _resolve_mana_cost(spell, mob_level)
            if ai.mana_pool >= cost:
                offensive_spells.append(spell)

    if not offensive_spells:
        return None

    # Phase 1.2: Prefer spells that target the player's weakest save
    if target_save_weakness:
        save_map = {
            SavingThrow.POISON: "poison",
            SavingThrow.DEATH: "death",
            SavingThrow.PETRIFICATION: "petrification",
            SavingThrow.ROD: "rod",
            SavingThrow.SPELL: "spell",
        }
        weak_save_str = save_map.get(target_save_weakness, "spell")

        # Score spells: bonus if the spell uses the target's weak save
        scored = []
        for spell in offensive_spells:
            score = random.random()
            if spell.get("save_type", "spell") == weak_save_str:
                score += 0.5  # Bonus for targeting weak save
            scored.append((spell, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        chosen = scored[0][0]
    else:
        chosen = random.choice(offensive_spells)

    return (chosen["key"], target)


def npc_cast_spell(mob, spell_key: str, target) -> Tuple[bool, str]:
    """
    Execute a spell cast by an NPC.
    Returns (success: bool, message: str).

    Phase 1.2: Integrates saving throw awareness.
    """
    from world.spells import get_spell, SpellHandler, _resolve_mana_cost

    spell = get_spell(spell_key)
    if not spell:
        return False, "Unknown spell."

    ai = mob.attributes.get("mob_ai") if hasattr(mob, "attributes") else None
    mob_level = mob.attributes.get("level", 1) if hasattr(mob, "attributes") else 1

    cost = _resolve_mana_cost(spell, mob_level)
    if ai and ai.mana_pool < cost:
        return False, "Not enough mana."

    # Deduct mana
    if ai:
        ai.mana_pool -= cost
        mob.attributes.add("mob_ai", ai)

    # Use SpellHandler to cast
    handler = SpellHandler(mob)
    success, msg = handler.cast(spell_key, target=target, caller=mob)

    return success, msg


def npc_check_saving_throw(mob, save_type: str, dc: int) -> bool:
    """
    Check if an NPC makes a saving throw against an effect.
    Returns True if the NPC saved.

    Phase 1.2: NPCs now have saving throw awareness.
    """
    if not hasattr(mob, "attributes"):
        return False

    from world.saving_throws import roll_saving_throw, SavingThrow

    save_map = {
        "poison": SavingThrow.POISON,
        "death": SavingThrow.DEATH,
        "petrification": SavingThrow.PETRIFICATION,
        "rod": SavingThrow.ROD,
        "spell": SavingThrow.SPELL,
    }
    st = save_map.get(save_type, SavingThrow.SPELL)

    passed, roll, dc_used = roll_saving_throw(mob, st, dc=dc)
    return passed


def get_npc_damage_resistances(mob) -> dict:
    """
    Return NPC damage resistances for Phase 1.2 integration.
    Checks the mob's damage_resistances attribute.
    """
    if not hasattr(mob, "attributes"):
        return {}
    return mob.attributes.get("damage_resistances", default={})


def get_npc_damage_immunities(mob) -> set:
    """Return NPC damage immunities."""
    if not hasattr(mob, "attributes"):
        return set()
    immunities = mob.attributes.get("damage_immunities", default=None)
    if not immunities:
        return set()
    if isinstance(immunities, list):
        return set(immunities)
    return immunities


# ---------------------------------------------------------------------------
# Phase 5 — Mob Flee / Morale System
# ---------------------------------------------------------------------------

MOB_FLEE_ATTEMPT_COOLDOWN = 30  # Seconds between flee attempts


def should_mob_flee(mob) -> bool:
    """
    Determine if a mob should attempt to flee from combat.
    
    Checks:
      - Mob has MobAIData with flee_chance > 0
      - HP percentage is below morale_threshold
      - Mob is not a boss (bosses never flee)
      - Mob is not already fleeing / hasn't recently attempted
    
    Returns True if the mob should attempt to flee this round.
    """
    if not hasattr(mob, "attributes"):
        return False

    # Bosses never flee
    if mob.attributes.get("is_boss", False):
        return False

    ai = mob.attributes.get("mob_ai")
    if not ai or ai.flee_chance <= 0:
        return False

    # Check flee attempt cooldown
    last_flee = mob.attributes.get("last_flee_attempt", 0)
    import time
    if time.time() - last_flee < MOB_FLEE_ATTEMPT_COOLDOWN:
        return False

    # Check HP threshold
    hp = mob.attributes.get("hp", 0)
    max_hp = mob.attributes.get("max_hp", 100)
    if max_hp <= 0:
        return False
    hp_pct = hp / max_hp

    return hp_pct < ai.morale_threshold


def attempt_mob_flee(mob) -> Tuple[bool, str]:
    """
    Attempt to flee from combat. Rolls flee_chance against random.
    
    Returns (success: bool, message: str).
    On success, stops combat via CombatHandler and returns True.
    On failure, records the attempt and returns False.
    """
    if not hasattr(mob, "attributes"):
        return False, ""

    ai = mob.attributes.get("mob_ai")
    if not ai:
        return False, ""

    import time
    mob.attributes.add("last_flee_attempt", time.time())

    # Flee chance scales with how low HP is (more desperate = harder to stop)
    hp = mob.attributes.get("hp", 0)
    max_hp = mob.attributes.get("max_hp", 100)
    hp_pct = hp / max(max_hp, 1)
    desperation_bonus = max(0, (ai.morale_threshold - hp_pct) * 2)
    effective_chance = min(0.90, ai.flee_chance + desperation_bonus)

    if random.random() < effective_chance:
        # Successful flee
        from world.tick_combat import CombatHandler
        CombatHandler.stop_combat(mob)
        mob_name = mob.key if hasattr(mob, "key") else "The creature"
        msg = f"|y{mob_name} flees in panic!|n"
        loc = getattr(mob, "location", None)
        if loc and hasattr(loc, "msg_contents"):
            loc.msg_contents(msg)
        return True, msg
    else:
        mob_name = mob.key if hasattr(mob, "key") else "The creature"
        msg = f"|y{mob_name} tries to flee but is cornered!|n"
        loc = getattr(mob, "location", None)
        if loc and hasattr(loc, "msg_contents"):
            loc.msg_contents(msg)
        return False, msg


# ---------------------------------------------------------------------------
# Phase 5 — Mana Regeneration (out of combat)
# ---------------------------------------------------------------------------

def regen_npc_mana(mob) -> int:
    """
    Regenerate mana for an NPC that is not in combat.
    Called during ai_tick when the mob is idle or wandering.
    
    Returns the amount of mana regenerated.
    """
    ai = mob.attributes.get("mob_ai") if hasattr(mob, "attributes") else None
    if not ai:
        return 0
    if ai.mana_pool >= ai.max_mana:
        return 0
    if ai.mana_regen_per_tick <= 0:
        return 0

    regen_amount = ai.mana_regen_per_tick
    ai.mana_pool = min(ai.max_mana, ai.mana_pool + regen_amount)
    mob.attributes.add("mob_ai", ai)
    return regen_amount


# ---------------------------------------------------------------------------
# Phase 5 — Patrol Path Movement
# ---------------------------------------------------------------------------

def advance_patrol(mob) -> Optional[str]:
    """
    Advance a patrolling mob toward its next waypoint.
    
    Called during ai_tick for mobs with patrol_path set.
    Returns the next room key to move toward, or None if pausing/idle.
    """
    ai = mob.attributes.get("mob_ai") if hasattr(mob, "attributes") else None
    if not ai or not ai.patrol_path:
        return None

    # If pausing at current waypoint, decrement counter and stay
    if ai._patrol_pause_counter > 0:
        ai._patrol_pause_counter -= 1
        mob.attributes.add("mob_ai", ai)
        return None

    # Get current patrol target
    path = ai.patrol_path
    if not path:
        return None

    idx = ai._patrol_idx
    if idx < 0 or idx >= len(path):
        idx = 0
        ai._patrol_idx = 0

    # Advance to next waypoint
    if ai.patrol_loop:
        # Loop: cycle through waypoints
        next_idx = (idx + 1) % len(path)
    else:
        # Ping-pong: reverse direction at ends
        if ai._patrol_forward:
            next_idx = idx + 1
            if next_idx >= len(path):
                next_idx = len(path) - 2 if len(path) > 1 else 0
                ai._patrol_forward = False
        else:
            next_idx = idx - 1
            if next_idx < 0:
                next_idx = 1 if len(path) > 1 else 0
                ai._patrol_forward = True

    ai._patrol_idx = next_idx
    ai._patrol_pause_counter = ai.patrol_pause_ticks  # Pause at new waypoint
    mob.attributes.add("mob_ai", ai)

    return path[next_idx]


# ---------------------------------------------------------------------------
# Phase 5 — Faction Warfare (Mob vs Mob Aggro)
# ---------------------------------------------------------------------------

def check_mob_vs_mob_aggro(mob, other_mob) -> bool:
    """
    Determine if an aggressive mob should attack another mob.
    
    Conditions:
      - Attacker has aggro_other_mobs=True
      - Target is a mob (is_mob attribute)
      - Different faction (not same, not neutral on either side)
      - Both are alive and aggressive
    """
    if not hasattr(mob, "attributes") or not hasattr(other_mob, "attributes"):
        return False

    # Target must be a mob
    if not other_mob.attributes.get("is_mob", False):
        return False

    ai = mob.attributes.get("mob_ai")
    if not ai or not ai.aggro_other_mobs:
        return False

    # Only aggressive/guardian mobs initiate faction warfare
    if ai.disposition not in (MobDisposition.AGGRESSIVE, MobDisposition.GUARDIAN):
        return False

    # Both must be alive
    mob_hp = mob.attributes.get("hp", 0)
    other_hp = other_mob.attributes.get("hp", 0)
    if mob_hp <= 0 or other_hp <= 0:
        return False

    # Must be different, non-neutral factions
    mob_faction = mob.attributes.get("faction", "")
    other_faction = other_mob.attributes.get("faction", "")
    if not mob_faction or not other_faction:
        return False
    if mob_faction == other_faction:
        return False
    if mob_faction == "Neutral" or other_faction == "Neutral":
        return False

    # Check level threshold (don't attack much weaker mobs)
    mob_level = mob.attributes.get("level", 1)
    other_level = other_mob.attributes.get("level", 1)
    if mob_level - other_level > ai.level_threshold:
        return False

    # Other mob must not already be in combat (to avoid dogpiling)
    from world.tick_combat import CombatHandler
    if CombatHandler.is_in_combat(other_mob):
        return False

    return True


# ---------------------------------------------------------------------------
# Phase 5 — Rare / Elite Spawn Variants
# ---------------------------------------------------------------------------

# Spawn tier configuration
SPAWN_TIER_CONFIG = {
    "rare_chance": 0.08,       # 8% chance for rare
    "elite_chance": 0.02,      # 2% chance for elite (within rare rolls)
    "rare": {
        "name_prefix": "{Rare} ",
        "ansi_color": "|Y",     # Yellow
        "stat_mult": 1.5,
        "hp_mult": 2.0,
        "xp_mult": 3.0,
        "gold_mult": 3.0,
        "min_mob_level": 5,     # Only mobs level 5+ can be rare
    },
    "elite": {
        "name_prefix": "{Elite} ",
        "ansi_color": "|M",     # Magenta
        "stat_mult": 2.0,
        "hp_mult": 3.0,
        "xp_mult": 5.0,
        "gold_mult": 5.0,
        "min_mob_level": 15,    # Only mobs level 15+ can be elite
    },
}


def determine_spawn_tier(mob_level: int, is_boss: bool = False) -> str:
    """
    Determine if a mob should spawn as normal, rare, or elite.
    
    Returns 'normal', 'rare', or 'elite'.
    Bosses, already-rare mobs, and low-level mobs stay normal.
    """
    if is_boss:
        return "normal"

    if mob_level < SPAWN_TIER_CONFIG["rare"]["min_mob_level"]:
        return "normal"

    roll = random.random()

    if mob_level >= SPAWN_TIER_CONFIG["elite"]["min_mob_level"]:
        if roll < SPAWN_TIER_CONFIG["elite_chance"]:
            return "elite"

    if roll < SPAWN_TIER_CONFIG["elite_chance"] + SPAWN_TIER_CONFIG["rare_chance"]:
        return "rare"

    return "normal"


def apply_spawn_tier(name: str, stats: dict, hp: int, xp: int,
                     gold_min: int, gold_max: int, tier: str) -> Tuple[str, dict, int, int, int, int]:
    """
    Apply rare/elite multipliers to a mob's base attributes.
    
    Returns updated (name, stats, hp, xp_value, gold_min, gold_max).
    """
    if tier == "normal":
        return name, stats, hp, xp, gold_min, gold_max

    tier_cfg = SPAWN_TIER_CONFIG.get(tier, {})
    if not tier_cfg:
        return name, stats, hp, xp, gold_min, gold_max

    name = tier_cfg["name_prefix"] + name
    stats = {k: int(v * tier_cfg["stat_mult"]) for k, v in stats.items()}
    hp = int(hp * tier_cfg["hp_mult"])
    xp = int(xp * tier_cfg["xp_mult"])
    gold_min = int(gold_min * tier_cfg["gold_mult"])
    gold_max = int(gold_max * tier_cfg["gold_mult"])

    return name, stats, hp, xp, gold_min, gold_max


def get_spawn_tier_ansi(tier: str) -> str:
    """Return the ANSI color code for a spawn tier."""
    if tier == "normal":
        return "|W"
    tier_cfg = SPAWN_TIER_CONFIG.get(tier, {})
    return tier_cfg.get("ansi_color", "|W")


# ---------------------------------------------------------------------------
# Phase 5 — Mob Combat Skill Assignment
# ---------------------------------------------------------------------------

# Mob type to allowed combat skills mapping
MOB_COMBAT_SKILLS = {
    "warrior": ["kick"],
    "brute": ["kick", "bash"],
    "rogue": ["kick", "disarm"],
    "monk": ["kick", "bash"],
}

# Chance per combat round that a mob uses a skill (if eligible)
MOB_SKILL_CHANCE_PER_ROUND = 0.20


def get_mob_combat_skills(mob_class: str = "warrior") -> List[str]:
    """Return the list of combat skill keys a mob type can use."""
    mob_class_lower = mob_class.lower() if mob_class else "warrior"
    return MOB_COMBAT_SKILLS.get(mob_class_lower, ["kick"])


def select_mob_combat_skill(mob, skill_chance: float = MOB_SKILL_CHANCE_PER_ROUND) -> Optional[str]:
    """
    Randomly select a combat skill for the mob to use this round.
    Returns a skill key string or None.
    
    Skill eligibility depends on mob level vs skill min_level.
    """
    ai = mob.attributes.get("mob_ai") if hasattr(mob, "attributes") else None
    if not ai:
        return None

    mob_class = mob.attributes.get("class", "warrior") if hasattr(mob, "attributes") else "warrior"
    mob_level = mob.attributes.get("level", 1) if hasattr(mob, "attributes") else 1

    allowed_skills = get_mob_combat_skills(mob_class)

    # Filter by level eligibility
    from world.combat_skills import COMBAT_SKILLS
    eligible = []
    for skill_name in allowed_skills:
        skill = COMBAT_SKILLS.get(skill_name)
        if not skill:
            continue
        if mob_level >= skill.get("min_level", 1):
            eligible.append(skill_name)

    if not eligible:
        return None

    # Roll chance
    if random.random() > skill_chance:
        return None

    return random.choice(eligible)


# ---------------------------------------------------------------------------
# Phase 5 — Spell List Assignment for Realm Mobs
# ---------------------------------------------------------------------------

# Spell type -> spell list progression (spell keys added at each level threshold)
MOB_SPELL_PROGRESSION = {
    "caster": [
        (1, "sparks"),
        (3, "minorheal"),
        (5, "frostsnap"),
        (8, "arcanedart"),
        (10, "stoneskin"),
        (15, "fireball"),
        (20, "chainlightning"),
        (25, "deathspell"),
    ],
    "healer": [
        (1, "minorheal"),
        (5, "curepoison"),
        (10, "greaterheal"),
        (15, "massheal"),
    ],
    "hybrid": [
        (3, "sparks"),
        (5, "minorheal"),
        (8, "frostsnap"),
    ],
}


def get_mob_spell_list(mob_type: str = "warrior", level: int = 1) -> List[str]:
    """Return the spell list for a mob based on its type and level."""
    if mob_type not in MOB_SPELL_PROGRESSION:
        return []

    spells = []
    for req_level, spell_key in MOB_SPELL_PROGRESSION[mob_type]:
        if level >= req_level:
            spells.append(spell_key)

    return spells


def guess_mob_type_from_name(name: str) -> str:
    """Guess a mob's spellcasting type from its name."""
    name_lower = name.lower() if name else ""

    # Caster keywords
    caster_keywords = ["acolyte", "cultist", "mage", "wizard", "sorcerer",
                       "witch", "warlock", "necromancer", "elementalist",
                       "dark acolyte", "infernal cultist", "forest witch",
                       "nether reaver", "void behemoth", "astral devourer",
                       "shaman", "druid"]
    for kw in caster_keywords:
        if kw in name_lower:
            return "caster"

    # Healer keywords
    healer_keywords = ["cleric", "priest", "healer", "medic"]
    for kw in healer_keywords:
        if kw in name_lower:
            return "healer"

    # Hybrid keywords
    hybrid_keywords = ["paladin", "ranger", "monk", "bard", "druid"]
    for kw in hybrid_keywords:
        if kw in name_lower:
            return "hybrid"

    return "warrior"


def get_mob_mana_pool(mob_type: str, level: int) -> int:
    """Return the mana pool size for a mob type at a given level."""
    if mob_type in ("caster", "healer"):
        return level * 8
    elif mob_type == "hybrid":
        return level * 4
    return 0
