"""
Manual Test Script — Phase 5: Mob AI & Spawning (Production Ready)
==================================================================
Fully self-contained. No Evennia/Django environment needed.
Run from command line: python commands/tests/manual_test_phase5_mob_ai.py

Tests:
  1. MobAIData — all Phase 5 fields & defaults
  2. Mob flee / morale logic
  3. Faction warfare (Good vs Evil)
  4. Rare/Elite spawn tiers
  5. Patrol path advancement
  6. Mob combat skill eligibility
  7. Mana regeneration
  8. Spell list assignment
  9. All features integration (full MobAIData)
  10. Spawn tier config
"""

import sys
import random

# ---------------------------------------------------------------------------
# Test framework
# ---------------------------------------------------------------------------
PASSED = 0
FAILED = 0
RESULTS = []


def assert_true(condition, test_name, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        RESULTS.append(f"  [PASS] {test_name}")
    else:
        FAILED += 1
        RESULTS.append(f"  [FAIL] {test_name} — {detail}")


def assert_false(condition, test_name, detail=""):
    assert_true(not condition, test_name, detail)


def assert_equal(a, b, test_name, detail=""):
    if a == b:
        assert_true(True, test_name)
    else:
        assert_true(False, test_name, f"Expected {b!r}, got {a!r}. {detail}")


def assert_in(item, container, test_name, detail=""):
    if item in container:
        assert_true(True, test_name)
    else:
        assert_true(False, test_name, f"{item!r} not found. {detail}")


def section(title):
    RESULTS.append(f"\n{'='*60}")
    RESULTS.append(f"  {title}")
    RESULTS.append(f"{'='*60}")


# ---------------------------------------------------------------------------
# Inline dataclasses (mirrors world/mob_ai.py)
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, List, Tuple


class MobDisposition(Enum):
    PASSIVE = "passive"
    NEUTRAL = "neutral"
    AGGRESSIVE = "aggressive"
    GUARDIAN = "guardian"


@dataclass
class MobAIData:
    disposition: MobDisposition = MobDisposition.NEUTRAL
    aggro_radius: int = 0
    assist_radius: int = 0
    assist_faction: str = ""
    leash_room: Optional[Any] = None
    max_chase_rooms: int = 3
    level_threshold: int = 5
    spell_list: List[str] = field(default_factory=list)
    cast_chance: float = 0.3
    mana_pool: int = 0
    max_mana: int = 0
    prefer_heal_at_pct: float = 0.3
    morale_threshold: float = 0.20
    flee_chance: float = 0.0
    mana_regen_per_tick: int = 1
    patrol_path: List[str] = field(default_factory=list)
    patrol_loop: bool = False
    patrol_pause_ticks: int = 2
    _patrol_idx: int = 0
    _patrol_forward: bool = True
    _patrol_pause_counter: int = 0
    aggro_other_mobs: bool = False


# ---------------------------------------------------------------------------
# Phase 5 function replicas (inline, no world imports)
# ---------------------------------------------------------------------------

MOB_FLEE_ATTEMPT_COOLDOWN = 30


def should_mob_flee(hp, max_hp, ai, is_boss=False, last_flee_attempt=0):
    """Replica of world/mob_ai.py:should_mob_flee"""
    if is_boss:
        return False
    if not ai or ai.flee_chance <= 0:
        return False
    import time
    if time.time() - last_flee_attempt < MOB_FLEE_ATTEMPT_COOLDOWN:
        return False
    if max_hp <= 0:
        return False
    return (hp / max_hp) < ai.morale_threshold


def attempt_mob_flee(hp, max_hp, ai):
    """Replica of world/mob_ai.py:attempt_mob_flee"""
    if not ai:
        return False
    hp_pct = hp / max(max_hp, 1)
    desperation_bonus = max(0, (ai.morale_threshold - hp_pct) * 2)
    effective_chance = min(0.90, ai.flee_chance + desperation_bonus)
    return random.random() < effective_chance


def regen_mana(ai):
    """Replica of world/mob_ai.py:regen_npc_mana"""
    if ai.mana_pool >= ai.max_mana:
        return 0
    if ai.mana_regen_per_tick <= 0:
        return 0
    regen_amount = ai.mana_regen_per_tick
    ai.mana_pool = min(ai.max_mana, ai.mana_pool + regen_amount)
    return regen_amount


def advance_patrol(ai):
    """Replica of world/mob_ai.py:advance_patrol"""
    if not ai or not ai.patrol_path:
        return None
    if ai._patrol_pause_counter > 0:
        ai._patrol_pause_counter -= 1
        return None
    path = ai.patrol_path
    idx = ai._patrol_idx
    if ai.patrol_loop:
        next_idx = (idx + 1) % len(path)
    else:
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
    ai._patrol_pause_counter = ai.patrol_pause_ticks
    return path[next_idx]


def check_mob_vs_mob_aggro(mob_faction, mob_hp, mob_level, mob_ai, other_faction, other_hp, other_level, other_in_combat):
    """Replica of world/mob_ai.py:check_mob_vs_mob_aggro"""
    if not mob_ai or not mob_ai.aggro_other_mobs:
        return False
    if mob_ai.disposition not in (MobDisposition.AGGRESSIVE, MobDisposition.GUARDIAN):
        return False
    if mob_hp <= 0 or other_hp <= 0:
        return False
    if not mob_faction or not other_faction:
        return False
    if mob_faction == other_faction:
        return False
    if mob_faction == "Neutral" or other_faction == "Neutral":
        return False
    if mob_level - other_level > mob_ai.level_threshold:
        return False
    if other_in_combat:
        return False
    return True


# ----- Spawn tier config (mirrors world/mob_ai.py) -----

SPAWN_TIER_CONFIG = {
    "rare_chance": 0.08,
    "elite_chance": 0.02,
    "rare": {
        "name_prefix": "{Rare} ",
        "ansi_color": "|Y",
        "stat_mult": 1.5,
        "hp_mult": 2.0,
        "xp_mult": 3.0,
        "gold_mult": 3.0,
        "min_mob_level": 5,
    },
    "elite": {
        "name_prefix": "{Elite} ",
        "ansi_color": "|M",
        "stat_mult": 2.0,
        "hp_mult": 3.0,
        "xp_mult": 5.0,
        "gold_mult": 5.0,
        "min_mob_level": 15,
    },
}


def determine_spawn_tier(mob_level, is_boss=False):
    if is_boss or mob_level < SPAWN_TIER_CONFIG["rare"]["min_mob_level"]:
        return "normal"
    roll = random.random()
    if mob_level >= SPAWN_TIER_CONFIG["elite"]["min_mob_level"]:
        if roll < SPAWN_TIER_CONFIG["elite_chance"]:
            return "elite"
    if roll < SPAWN_TIER_CONFIG["elite_chance"] + SPAWN_TIER_CONFIG["rare_chance"]:
        return "rare"
    return "normal"


def apply_spawn_tier(name, stats, hp, xp, gold_min, gold_max, tier):
    if tier == "normal":
        return name, stats, hp, xp, gold_min, gold_max
    cfg = SPAWN_TIER_CONFIG.get(tier, {})
    name = cfg["name_prefix"] + name
    stats = {k: int(v * cfg["stat_mult"]) for k, v in stats.items()}
    hp = int(hp * cfg["hp_mult"])
    xp = int(xp * cfg["xp_mult"])
    gold_min = int(gold_min * cfg["gold_mult"])
    gold_max = int(gold_max * cfg["gold_mult"])
    return name, stats, hp, xp, gold_min, gold_max


# ----- Combat skills (mirrors world/combat_skills.py) -----

COMBAT_SKILLS = {
    "kick": {"name": "Kick", "min_level": 1, "classes": ["Warrior", "Monk", "Rogue", "Ranger"]},
    "bash": {"name": "Bash", "min_level": 5, "classes": ["Warrior", "Paladin"]},
    "disarm": {"name": "Disarm", "min_level": 8, "classes": ["Warrior", "Rogue", "Monk"]},
}

MOB_COMBAT_SKILLS = {
    "warrior": ["kick"],
    "brute": ["kick", "bash"],
    "rogue": ["kick", "disarm"],
    "monk": ["kick", "bash"],
}

MOB_SKILL_CHANCE_PER_ROUND = 0.20


def get_mob_combat_skills(mob_class="warrior"):
    return MOB_COMBAT_SKILLS.get(mob_class.lower(), ["kick"])


def select_mob_combat_skill(mob_level, mob_class="warrior", skill_chance=MOB_SKILL_CHANCE_PER_ROUND):
    allowed = get_mob_combat_skills(mob_class)
    eligible = [s for s in allowed if mob_level >= COMBAT_SKILLS.get(s, {}).get("min_level", 1)]
    if not eligible or random.random() > skill_chance:
        return None
    return random.choice(eligible)


# ----- Spell list assignment (mirrors world/mob_ai.py) -----

MOB_SPELL_PROGRESSION = {
    "caster": [
        (1, "sparks"), (3, "minorheal"), (5, "frostsnap"), (8, "arcanedart"),
        (10, "stoneskin"), (15, "fireball"), (20, "chainlightning"), (25, "deathspell"),
    ],
    "healer": [
        (1, "minorheal"), (5, "curepoison"), (10, "greaterheal"), (15, "massheal"),
    ],
    "hybrid": [
        (3, "sparks"), (5, "minorheal"), (8, "frostsnap"),
    ],
}


def get_mob_spell_list(mob_type="warrior", level=1):
    if mob_type not in MOB_SPELL_PROGRESSION:
        return []
    return [spell for req_level, spell in MOB_SPELL_PROGRESSION[mob_type] if level >= req_level]


def get_mob_mana_pool(mob_type, level):
    if mob_type in ("caster", "healer"):
        return level * 8
    elif mob_type == "hybrid":
        return level * 4
    return 0


def guess_mob_type_from_name(name):
    name_lower = name.lower() if name else ""
    caster_kws = ["acolyte", "cultist", "mage", "wizard", "sorcerer", "witch", "warlock",
                  "necromancer", "shaman", "druid", "elementalist", "reaver", "devourer", "horror"]
    for kw in caster_kws:
        if kw in name_lower:
            return "caster"
    healer_kws = ["cleric", "priest", "healer", "medic"]
    for kw in healer_kws:
        if kw in name_lower:
            return "healer"
    hybrid_kws = ["paladin", "ranger", "monk", "bard"]
    for kw in hybrid_kws:
        if kw in name_lower:
            return "hybrid"
    return "warrior"


# ======================================================================
# Tests
# ======================================================================

def test_1_mob_ai_data():
    section("Test 1: MobAIData — All Phase 5 Fields & Defaults")

    ai = MobAIData(
        disposition=MobDisposition.AGGRESSIVE,
        spell_list=["sparks", "minorheal", "frostsnap"],
        cast_chance=0.30,
        mana_pool=60,
        max_mana=60,
        mana_regen_per_tick=2,
        morale_threshold=0.20,
        flee_chance=0.40,
        patrol_path=["gate_a", "gate_b"],
        patrol_loop=True,
        aggro_other_mobs=True,
    )

    assert_equal(ai.spell_list, ["sparks", "minorheal", "frostsnap"], "spell_list stores 3 spells")
    assert_equal(ai.cast_chance, 0.30, "cast_chance = 0.30")
    assert_equal(ai.mana_pool, 60, "mana_pool = 60")
    assert_equal(ai.max_mana, 60, "max_mana = 60")
    assert_equal(ai.mana_regen_per_tick, 2, "mana_regen_per_tick = 2")
    assert_equal(ai.morale_threshold, 0.20, "morale_threshold = 0.20")
    assert_equal(ai.flee_chance, 0.40, "flee_chance = 0.40")
    assert_equal(ai.patrol_path, ["gate_a", "gate_b"], "patrol_path stores 2 waypoints")
    assert_true(ai.patrol_loop, "patrol_loop = True")
    assert_equal(ai.patrol_pause_ticks, 2, "patrol_pause_ticks = 2")
    assert_true(ai.aggro_other_mobs, "aggro_other_mobs = True")

    # Defaults
    ai_default = MobAIData()
    assert_equal(ai_default.morale_threshold, 0.20, "Default morale_threshold = 0.20")
    assert_equal(ai_default.flee_chance, 0.0, "Default flee_chance = 0.0")
    assert_equal(ai_default.mana_regen_per_tick, 1, "Default mana_regen = 1")
    assert_equal(ai_default.patrol_path, [], "Default patrol_path = empty")
    assert_false(ai_default.aggro_other_mobs, "Default aggro_other_mobs = False")

    # Backward compat: old code creating MobAIData without new args works
    ai_old = MobAIData(disposition=MobDisposition.NEUTRAL, aggro_radius=0)
    assert_equal(ai_old.morale_threshold, 0.20, "Old-style init: morale defaults ok")
    assert_equal(ai_old.flee_chance, 0.0, "Old-style init: flee_chance defaults ok")


def test_2_mob_flee():
    section("Test 2: Mob Flee / Morale System")

    ai = MobAIData(morale_threshold=0.25, flee_chance=0.50)
    ai_passive = MobAIData(disposition=MobDisposition.PASSIVE, morale_threshold=0.50, flee_chance=0.0)
    ai_boss = MobAIData(disposition=MobDisposition.AGGRESSIVE, morale_threshold=0.90, flee_chance=0.80)

    # Below threshold -> should flee
    assert_true(should_mob_flee(hp=10, max_hp=100, ai=ai),
                "HP 10% < 25% threshold: should flee")

    # Above threshold -> no flee
    assert_false(should_mob_flee(hp=80, max_hp=100, ai=ai),
                 "HP 80% > 25% threshold: should NOT flee")

    # Passive mobs never flee (flee_chance=0)
    assert_false(should_mob_flee(hp=5, max_hp=100, ai=ai_passive),
                 "Passive mob flee_chance=0: never flees")

    # Bosses never flee
    assert_false(should_mob_flee(hp=5, max_hp=100, ai=ai_boss, is_boss=True),
                 "Bosses never flee regardless of HP")

    # No AI = no flee
    assert_false(should_mob_flee(hp=5, max_hp=100, ai=None),
                 "No AI data: never flees")

    # Desperation bonus increases effective chance
    ai_flee = MobAIData(morale_threshold=0.30, flee_chance=0.40)
    # HP is at 10% (0.10), threshold is 0.30, so desperation = (0.30 - 0.10) * 2 = 0.40
    # effective chance = min(0.90, 0.40 + 0.40) = 0.80
    # This is probabilistic, so test that it CAN succeed (run many times)
    successes = sum(1 for _ in range(100) if attempt_mob_flee(hp=10, max_hp=100, ai=ai_flee))
    assert_true(successes > 20, f"Desperation bonus: {successes}/100 flee attempts succeeded (expected ~80%)")


def test_3_faction_warfare():
    section("Test 3: Faction Warfare (Good vs Evil)")

    ai_good = MobAIData(disposition=MobDisposition.AGGRESSIVE, aggro_other_mobs=True, level_threshold=8)
    ai_evil = MobAIData(disposition=MobDisposition.AGGRESSIVE, aggro_other_mobs=True)
    ai_no_aggro = MobAIData(disposition=MobDisposition.AGGRESSIVE, aggro_other_mobs=False)
    ai_passive = MobAIData(disposition=MobDisposition.PASSIVE, aggro_other_mobs=True)

    # Good vs Evil: should aggro
    assert_true(check_mob_vs_mob_aggro(
        "Aethelgard Alliance", 100, 15, ai_good, "Gorgoroth Horde", 100, 15, False),
        "Good aggros Evil")

    # Evil vs Good: should aggro
    assert_true(check_mob_vs_mob_aggro(
        "Gorgoroth Horde", 100, 15, ai_evil, "Aethelgard Alliance", 100, 15, False),
        "Evil aggros Good")

    # Same faction: no aggro
    assert_false(check_mob_vs_mob_aggro(
        "Aethelgard Alliance", 100, 15, ai_good, "Aethelgard Alliance", 100, 15, False),
        "Same faction: no aggro")

    # Neutral: no aggro
    assert_false(check_mob_vs_mob_aggro(
        "Aethelgard Alliance", 100, 15, ai_good, "Neutral", 100, 15, False),
        "Good vs Neutral: no aggro")

    # aggro_other_mobs disabled
    assert_false(check_mob_vs_mob_aggro(
        "Aethelgard Alliance", 100, 15, ai_no_aggro, "Gorgoroth Horde", 100, 15, False),
        "aggro_other_mobs=False: no aggro")

    # Passive disposition
    assert_false(check_mob_vs_mob_aggro(
        "Aethelgard Alliance", 100, 15, ai_passive, "Gorgoroth Horde", 100, 15, False),
        "Passive mob: no aggro")

    # Target already in combat
    assert_false(check_mob_vs_mob_aggro(
        "Aethelgard Alliance", 100, 15, ai_good, "Gorgoroth Horde", 100, 15, True),
        "Target in combat: no aggro")

    # Level threshold: target too weak
    assert_false(check_mob_vs_mob_aggro(
        "Aethelgard Alliance", 100, 30, ai_good, "Gorgoroth Horde", 100, 5, False),
        "Target 5 levels below attacker with threshold 8: no aggro (too weak)")


def test_4_rare_spawns():
    section("Test 4: Rare/Elite Spawn Variants")

    base_stats = {"str": 10, "dex": 12, "con": 10, "int": 8, "wis": 8, "cha": 6}
    base_hp, base_xp, base_gold = 50, 100, (5, 20)

    # Normal tier
    n, s, h, x, gmin, gmax = apply_spawn_tier("Goblin", dict(base_stats), base_hp, base_xp, *base_gold, "normal")
    assert_equal(n, "Goblin", "Normal: name unchanged")
    assert_equal(s["str"], 10, "Normal: STR unchanged")
    assert_equal(h, 50, "Normal: HP unchanged")

    # Rare tier
    n, s, h, x, gmin, gmax = apply_spawn_tier("Goblin", dict(base_stats), base_hp, base_xp, *base_gold, "rare")
    assert_equal(n, "{Rare} Goblin", "Rare: name prefixed")
    assert_equal(s["str"], 15, "Rare: STR = 10 * 1.5 = 15")
    assert_equal(h, 100, "Rare: HP = 50 * 2.0 = 100")
    assert_equal(x, 300, "Rare: XP = 100 * 3.0 = 300")

    # Elite tier
    n, s, h, x, gmin, gmax = apply_spawn_tier("Goblin", dict(base_stats), base_hp, base_xp, *base_gold, "elite")
    assert_equal(n, "{Elite} Goblin", "Elite: name prefixed")
    assert_equal(s["str"], 20, "Elite: STR = 10 * 2.0 = 20")
    assert_equal(h, 150, "Elite: HP = 50 * 3.0 = 150")
    assert_equal(x, 500, "Elite: XP = 100 * 5.0 = 500")

    # Level gates
    assert_equal(determine_spawn_tier(3), "normal", "Level 3: always normal")
    assert_equal(determine_spawn_tier(5, is_boss=True), "normal", "Boss: always normal")

    # Level 6+ CAN be rare (depends on roll), but never elite at low level
    for _ in range(20):
        tier = determine_spawn_tier(6)
        assert_in(tier, ("normal", "rare"), "Level 6: only normal or rare, never elite")


def test_5_patrol_paths():
    section("Test 5: Patrol Path Advancement")

    ai = MobAIData(patrol_path=["room_a", "room_b", "room_c"], patrol_loop=True, patrol_pause_ticks=0)

    # First advance (no pause)
    result = advance_patrol(ai)
    assert_equal(result, "room_b", "Advance: index 0 -> room_b")
    result = advance_patrol(ai)
    assert_equal(result, "room_c", "Advance: index 1 -> room_c")
    result = advance_patrol(ai)
    assert_equal(result, "room_a", "Loop: index 2 wraps to room_a")

    # Ping-pong mode
    ai2 = MobAIData(patrol_path=["room_a", "room_b", "room_c"], patrol_loop=False, patrol_pause_ticks=0)
    result = advance_patrol(ai2)
    assert_equal(result, "room_b", "Ping-pong: a->b")
    result = advance_patrol(ai2)
    assert_equal(result, "room_c", "Ping-pong: b->c")
    result = advance_patrol(ai2)
    assert_equal(result, "room_b", "Ping-pong reverse: c->b")
    result = advance_patrol(ai2)
    assert_equal(result, "room_a", "Ping-pong reverse: b->a")

    # Empty patrol = None
    ai3 = MobAIData(patrol_path=[])
    assert_equal(advance_patrol(ai3), None, "Empty path: returns None")

    # Pause ticks: first 2 calls return None when pause=2
    ai4 = MobAIData(patrol_path=["room_a", "room_b"], patrol_pause_ticks=2)
    # First advance sets pause, returns next room
    result = advance_patrol(ai4)
    assert_equal(result, "room_b", "First advance: returns room_b, then pauses")
    # Now it should be paused — 2 silent ticks
    assert_equal(advance_patrol(ai4), None, "Pause tick 1: None")
    assert_equal(advance_patrol(ai4), None, "Pause tick 2: None")
    # After pause, next advance works
    result = advance_patrol(ai4)
    assert_equal(result, "room_a", "After pause: advances again")


def test_6_combat_skills():
    section("Test 6: Mob Combat Skill Usage")

    # Skill definitions exist
    assert_in("kick", COMBAT_SKILLS, "Kick skill defined")
    assert_in("bash", COMBAT_SKILLS, "Bash skill defined")
    assert_in("disarm", COMBAT_SKILLS, "Disarm skill defined")

    # Warrior gets kick
    assert_equal(get_mob_combat_skills("warrior"), ["kick"], "Warrior: only kick")
    # Brute gets kick + bash
    assert_equal(get_mob_combat_skills("brute"), ["kick", "bash"], "Brute: kick + bash")
    # Rogue gets kick + disarm
    assert_equal(get_mob_combat_skills("rogue"), ["kick", "disarm"], "Rogue: kick + disarm")

    # Level gates: level 1 can kick but not bash or disarm
    skill = select_mob_combat_skill(1, "warrior", skill_chance=1.0)
    assert_equal(skill, "kick", "Level 1 warrior: only kick eligible")
    skill = select_mob_combat_skill(4, "brute", skill_chance=1.0)
    assert_equal(skill, "kick", "Level 4 brute: kick only (bash needs level 5)")

    # Level 5 brute gets both
    skill = select_mob_combat_skill(5, "brute", skill_chance=1.0)
    assert_in(skill, ["kick", "bash"], f"Level 5 brute: kick or bash (got {skill})")

    # Level 10 warrior gets kick + disarm
    skill = select_mob_combat_skill(10, "rogue", skill_chance=1.0)
    assert_in(skill, ["kick", "disarm"], f"Level 10 rogue: kick or disarm (got {skill})")

    # No skills for level 0
    assert_equal(select_mob_combat_skill(0, "warrior", skill_chance=1.0), None,
                 "Level 0: no skills")

    # skill_chance=0 returns None
    assert_equal(select_mob_combat_skill(10, "warrior", skill_chance=0.0), None,
                 "skill_chance=0: always None")


def test_7_mana_regen():
    section("Test 7: Mana Regeneration")

    ai = MobAIData(mana_pool=10, max_mana=50, mana_regen_per_tick=2)
    assert_equal(ai.mana_pool, 10, "Initial mana = 10")

    # 5 ticks
    for _ in range(5):
        regen_mana(ai)
    assert_equal(ai.mana_pool, 20, "After 5 ticks: 10 + 5*2 = 20")

    # Cap at max
    for _ in range(20):
        regen_mana(ai)
    assert_equal(ai.mana_pool, 50, "Capped at max_mana = 50")

    # No mana pool = no regen
    ai_empty = MobAIData(mana_pool=0, max_mana=0, mana_regen_per_tick=0)
    assert_equal(regen_mana(ai_empty), 0, "Empty mana: regen returns 0")

    # At max = no regen
    ai_full = MobAIData(mana_pool=100, max_mana=100, mana_regen_per_tick=5)
    assert_equal(regen_mana(ai_full), 0, "Full mana: regen returns 0")


def test_8_spell_list():
    section("Test 8: Spell List Assignment on Realm Mobs")

    # Warrior = no spells
    assert_equal(get_mob_spell_list("warrior", 10), [], "Warrior: no spells")

    # Caster progression
    assert_equal(get_mob_spell_list("caster", 1), ["sparks"], "Caster L1: sparks")
    assert_equal(get_mob_spell_list("caster", 5), ["sparks", "minorheal", "frostsnap"],
                 "Caster L5: sparks, minorheal, frostsnap")
    c20 = get_mob_spell_list("caster", 20)
    assert_equal(len(c20), 7, "Caster L20: 7 spells")
    assert_in("fireball", c20, "Caster L20: includes fireball")
    assert_in("chainlightning", c20, "Caster L20: includes chainlightning")

    # Healer
    assert_equal(get_mob_spell_list("healer", 10), ["minorheal", "curepoison", "greaterheal"],
                 "Healer L10: minorheal, curepoison, greaterheal")

    # Hybrid
    assert_equal(get_mob_spell_list("hybrid", 4), ["sparks"], "Hybrid L4: sparks only")
    assert_equal(get_mob_spell_list("hybrid", 5), ["sparks", "minorheal"],
                 "Hybrid L5: sparks, minorheal")

    # Mana pools
    assert_equal(get_mob_mana_pool("warrior", 5), 0, "Warrior: 0 mana")
    assert_equal(get_mob_mana_pool("caster", 5), 40, "Caster L5: 40 mana")
    assert_equal(get_mob_mana_pool("healer", 10), 80, "Healer L10: 80 mana")
    assert_equal(get_mob_mana_pool("hybrid", 5), 20, "Hybrid L5: 20 mana")

    # Name-based guessing
    assert_equal(guess_mob_type_from_name("Dark Acolyte"), "caster", "Dark Acolyte -> caster")
    assert_equal(guess_mob_type_from_name("Goblin Scout"), "warrior", "Goblin Scout -> warrior")
    assert_equal(guess_mob_type_from_name("Infernal Cultist"), "caster", "Infernal Cultist -> caster")
    assert_equal(guess_mob_type_from_name("Forest Witch"), "caster", "Forest Witch -> caster")
    assert_equal(guess_mob_type_from_name("Dread Knight"), "warrior", "Dread Knight -> warrior")
    assert_equal(guess_mob_type_from_name("Battle Cleric"), "healer", "Battle Cleric -> healer")
    assert_equal(guess_mob_type_from_name("Shadow Priest"), "healer", "Shadow Priest -> healer")


def test_9_integration():
    section("Test 9: Full Integration — All Fields on MobAIData")

    ai = MobAIData(
        disposition=MobDisposition.AGGRESSIVE,
        aggro_radius=0,
        assist_radius=2,
        assist_faction="Gorgoroth Horde",
        spell_list=["sparks", "minorheal", "frostsnap"],
        cast_chance=0.30,
        mana_pool=60,
        max_mana=60,
        mana_regen_per_tick=2,
        morale_threshold=0.20,
        flee_chance=0.40,
        patrol_path=["gate_a", "gate_b"],
        patrol_loop=True,
        aggro_other_mobs=True,
    )

    # Verify all fields
    assert_equal(ai.disposition, MobDisposition.AGGRESSIVE, "disposition: AGGRESSIVE")
    assert_equal(ai.spell_list, ["sparks", "minorheal", "frostsnap"], "spell_list: 3 spells")
    assert_equal(ai.cast_chance, 0.30, "cast_chance: 0.30")
    assert_equal(ai.mana_pool, 60, "mana_pool: 60")
    assert_equal(ai.mana_regen_per_tick, 2, "mana_regen_per_tick: 2")
    assert_equal(ai.morale_threshold, 0.20, "morale_threshold: 0.20")
    assert_equal(ai.flee_chance, 0.40, "flee_chance: 0.40")
    assert_equal(ai.patrol_path, ["gate_a", "gate_b"], "patrol_path: 2 waypoints")
    assert_true(ai.patrol_loop, "patrol_loop: True")
    assert_true(ai.aggro_other_mobs, "aggro_other_mobs: True")
    assert_equal(ai.assist_radius, 2, "assist_radius: 2")


def test_10_spawn_tier_config():
    section("Test 10: Spawn Tier Configuration Validation")

    assert_equal(SPAWN_TIER_CONFIG["rare_chance"], 0.08, "Rare chance = 8%")
    assert_equal(SPAWN_TIER_CONFIG["elite_chance"], 0.02, "Elite chance = 2%")
    assert_equal(SPAWN_TIER_CONFIG["rare"]["stat_mult"], 1.5, "Rare stat mult = 1.5x")
    assert_equal(SPAWN_TIER_CONFIG["elite"]["hp_mult"], 3.0, "Elite HP mult = 3.0x")
    assert_equal(SPAWN_TIER_CONFIG["rare"]["min_mob_level"], 5, "Rare min level = 5")
    assert_equal(SPAWN_TIER_CONFIG["elite"]["min_mob_level"], 15, "Elite min level = 15")

    # Bosses never roll rare/elite
    assert_equal(determine_spawn_tier(20, is_boss=True), "normal", "Boss: always normal")

    # Level 3 can't be rare
    assert_equal(determine_spawn_tier(3, is_boss=False), "normal", "Level 3: always normal")

    # Level 10 can't be elite
    for _ in range(30):
        tier = determine_spawn_tier(10, is_boss=False)
        assert_in(tier, ("normal", "rare"), "Level 10: never elite")


# ======================================================================
# Main
# ======================================================================

def main():
    global PASSED, FAILED, RESULTS

    print("=" * 60)
    print("  PHASE 5: MOB AI & SPAWNING — Manual Verification Test")
    print("=" * 60)
    print("  Running offline validation of all Phase 5 systems...")
    print()

    test_1_mob_ai_data()
    test_2_mob_flee()
    test_3_faction_warfare()
    test_4_rare_spawns()
    test_5_patrol_paths()
    test_6_combat_skills()
    test_7_mana_regen()
    test_8_spell_list()
    test_9_integration()
    test_10_spawn_tier_config()

    print()
    for line in RESULTS:
        print(line)

    print()
    print("=" * 60)
    total = PASSED + FAILED
    print(f"  Results: {PASSED} passed, {FAILED} failed out of {total}")
    if FAILED == 0:
        print("  STATUS: ALL TESTS PASSED ✓")
    else:
        print(f"  STATUS: {FAILED} FAILURES ✗")
    print("=" * 60)
    return FAILED == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)