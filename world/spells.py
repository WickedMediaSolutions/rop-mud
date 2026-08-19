"""
Spell System for 'rop' — Level 1 through 80

Spell Categories (Schools):
  - Evocation: Direct damage (single-target and AoE)
  - Restoration: Healing and support
  - Abjuration: Shields, armor buffs, protections
  - Enfeebling: Debuffs, curses, crowd control

Each spell scales with caster level and/or primary casting stat (int or wis).
Damage spells use a base formula:  base_dmg + (caster_level * scale_factor) + (stat_bonus * 0.5)

Cooldowns are tracked per-character in `character.db.spell_cooldowns`.

Phase 7 Complete:
  - Damage types assigned per spell (fire, cold, lightning, shadow, etc.)
  - Saving throw checks on hostile spells
  - Status effect integration for stuns, debuffs, DoTs, and buffs
  - AoE multi-target spells
  - Heal-over-time and Damage-over-time spells
  - Buff spells (stat increases)
  - Spell resistance from gear/racial stats
  - Ritual/channeled spells with casting time
  - Class-specific spell lists via race_class_matrix
"""

import time
from evennia.utils import evtable
from evennia.utils import search

# ---------------------------------------------------------------------------
# SCHOOLS / CATEGORIES
# ---------------------------------------------------------------------------

SCHOOL_EVOCATION = "evocation"
SCHOOL_RESTORATION = "restoration"
SCHOOL_ABJURATION = "abjuration"
SCHOOL_ENFEEBLING = "enfeebling"

SCHOOL_DISPLAY = {
    SCHOOL_EVOCATION: "|rEvocation|n",
    SCHOOL_RESTORATION: "|gRestoration|n",
    SCHOOL_ABJURATION: "|bAbjuration|n",
    SCHOOL_ENFEEBLING: "|mEnfeebling|n",
}

# ---------------------------------------------------------------------------
# TARGET TYPES
# ---------------------------------------------------------------------------

TARGET_SELF = "self"
TARGET_SINGLE = "single"       # single enemy or ally
TARGET_AOE = "aoe"             # all enemies in room
TARGET_PBAOE = "pbaoe"         # point-blank AoE (all enemies in room)

# ---------------------------------------------------------------------------
# HELPER: resolve damage / healing scaling
# ---------------------------------------------------------------------------

def _casting_stat(caster):
    """Return the primary casting stat value (int or wis, whichever is higher)."""
    stats = caster.attributes.get("stats", {})
    if not stats:
        return 10
    return max(stats.get("int", 10), stats.get("wis", 10))


def scaled_value(base, per_level, caster_level, stat_bonus_mult=0.0):
    """
    Return base + per_level * caster_level + stat_bonus_mult * casting_stat.
    """
    stat = _casting_stat(None) if caster_level is None else None
    # stat_bonus is applied at call-site where we have the actual caster
    return int(base + per_level * caster_level)


# ---------------------------------------------------------------------------
# SPELL DEFINITIONS  (Level 1 → 80)
# ---------------------------------------------------------------------------

# Each entry keyed by spell alias (lowercase no spaces).
# Fields:
#   name          — display name
#   level         — level required
#   school        — evocation / restoration / abjuration / enfeebling
#   target        — self / single / aoe / pbaoe
#   mana_base     — base mana cost
#   mana_per_lvl  — additional mana cost per caster level
#   cooldown      — seconds before recast (0 = no cooldown)
#   cast_time     — seconds to channel before spell fires (0 = instant)
#   description   — flavour text
#   effect        — dict with keys depending on school:
#       Evocation:  {"type": "damage", "base": N, "per_level": N, "damage_type": "lightning"|"fire"|...}
#       Restoration: {"type": "heal", "base": N, "per_level": N}
#       Abjuration:  {"type": "shield", "base": N, "per_level": N, "duration": N}
#       Enfeebling:  {"type": "debuff", "stat": "str"|"dex"|..., "amount": N, "duration": N}
#       Buff:        {"type": "buff", "stat": "str"|"dex"|..., "amount": N, "duration": N}
#       DoT:         {"type": "dot", "dot_type": "bleed"|"poison"|"burn"|"curse", "base": N, "per_level": N, "duration": N}
#   save_type     — saving throw category: "spell", "poison", "petrification", "death", "rod"
#   save_negates  — True if saving throw negates the effect entirely

SPELLS = {}

def _spell(**kwargs):
    """Register a spell in the global SPELLS dict."""
    key = kwargs["name"].lower().replace(" ", "")
    kwargs["key"] = key
    # Set defaults
    kwargs.setdefault("save_type", "spell")
    kwargs.setdefault("save_negates", False)
    kwargs.setdefault("cast_time", 0)  # Phase 7: ritual/channeled spells
    SPELLS[key] = kwargs
    return kwargs


# ======================== LEVELS 1–10 ========================

_spell(name="Sparks", level=1, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=5, mana_per_lvl=1, cooldown=0,
       description="Fling a small arc of electrical energy at a single foe.",
       effect={"type": "damage", "base": 8, "per_level": 3, "damage_type": "lightning"},
       save_type="spell", save_negates=False)

_spell(name="Minor Heal", level=1, school=SCHOOL_RESTORATION, target=TARGET_SINGLE,
       mana_base=8, mana_per_lvl=1, cooldown=0,
       description="Mend light wounds of yourself or an ally.",
       effect={"type": "heal", "base": 12, "per_level": 4})

_spell(name="Arcane Dart", level=3, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=8, mana_per_lvl=2, cooldown=0,
       description="A precise bolt of pure mana streaking toward the target.",
       effect={"type": "damage", "base": 14, "per_level": 5, "damage_type": "arcane"},
       save_type="spell", save_negates=False)

_spell(name="Stone Skin", level=5, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=12, mana_per_lvl=2, cooldown=30,
       description="Harden your flesh, granting a temporary boost to armor for 30 seconds.",
       effect={"type": "shield", "base": 5, "per_level": 2, "duration": 30})

_spell(name="Frost Snap", level=7, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=10, mana_per_lvl=1, cooldown=8,
       description="Chill a target, slowing their movements and reducing dexterity for 15 seconds.",
       effect={"type": "debuff", "stat": "dex", "amount": 4, "duration": 15},
       save_type="spell", save_negates=True)

_spell(name="Flame Burst", level=9, school=SCHOOL_EVOCATION, target=TARGET_AOE,
       mana_base=15, mana_per_lvl=3, cooldown=6,
       description="A cone of fire erupts, searing all enemies in the vicinity.",
       effect={"type": "damage", "base": 10, "per_level": 4, "damage_type": "fire"},
       save_type="spell", save_negates=False)

# Phase 7: Buff spell
_spell(name="Might", level=2, school=SCHOOL_ABJURATION, target=TARGET_SINGLE,
       mana_base=8, mana_per_lvl=1, cooldown=10,
       description="Bolster an ally's strength for 30 seconds.",
       effect={"type": "buff", "stat": "str", "amount": 3, "duration": 30})

# Phase 7: DoT spell
_spell(name="Poison Touch", level=4, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=10, mana_per_lvl=1, cooldown=6,
       description="Infect a target with a virulent poison that deals damage over 18 seconds.",
       effect={"type": "dot", "dot_type": "poison", "base": 4, "per_level": 1, "duration": 18},
       save_type="poison", save_negates=True)

# Phase 7: Ritual spell (has cast_time)
_spell(name="Meditate", level=6, school=SCHOOL_RESTORATION, target=TARGET_SELF,
       mana_base=5, mana_per_lvl=0, cooldown=60, cast_time=5,
       description="Enter a deep meditative trance for 5 seconds, restoring a burst of mana.",
       effect={"type": "restore_mana", "base": 15, "per_level": 5})


# ======================== LEVELS 11–20 ========================

_spell(name="Lightning Bolt", level=12, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=18, mana_per_lvl=3, cooldown=4,
       description="Call down a crackling bolt of lightning upon a single enemy.",
       effect={"type": "damage", "base": 28, "per_level": 7, "damage_type": "lightning"},
       save_type="spell", save_negates=False)

_spell(name="Cure Wounds", level=14, school=SCHOOL_RESTORATION, target=TARGET_SINGLE,
       mana_base=20, mana_per_lvl=3, cooldown=0,
       description="A stronger restoration spell that closes deep gashes.",
       effect={"type": "heal", "base": 35, "per_level": 8})

_spell(name="Mana Shield", level=16, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=22, mana_per_lvl=3, cooldown=40,
       description="Surround yourself with a shimmering barrier that absorbs damage. Lasts 45 seconds.",
       effect={"type": "shield", "base": 20, "per_level": 5, "duration": 45})

_spell(name="Enfeeble", level=18, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=16, mana_per_lvl=2, cooldown=12,
       description="Sap the physical strength from a target for 20 seconds.",
       effect={"type": "debuff", "stat": "str", "amount": 8, "duration": 20},
       save_type="spell", save_negates=True)

_spell(name="Fireball", level=20, school=SCHOOL_EVOCATION, target=TARGET_AOE,
       mana_base=25, mana_per_lvl=4, cooldown=8,
       description="Hurl an explosive sphere of fire, engulfing all enemies in the room.",
       effect={"type": "damage", "base": 20, "per_level": 6, "damage_type": "fire"},
       save_type="spell", save_negates=False)

# Phase 7: Buff spell
_spell(name="Agility", level=11, school=SCHOOL_ABJURATION, target=TARGET_SINGLE,
       mana_base=12, mana_per_lvl=2, cooldown=10,
       description="Enhance an ally's dexterity for 30 seconds.",
       effect={"type": "buff", "stat": "dex", "amount": 4, "duration": 30})

# Phase 7: DoT spell
_spell(name="Ignite", level=13, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=14, mana_per_lvl=2, cooldown=5,
       description="Set a target ablaze, dealing fire damage over 12 seconds.",
       effect={"type": "dot", "dot_type": "burn", "base": 6, "per_level": 2, "duration": 12},
       save_type="spell", save_negates=False)

# Phase 7: Ritual spell
_spell(name="Ritual of Power", level=15, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=20, mana_per_lvl=3, cooldown=90, cast_time=8,
       description="Channel arcane energy for 8 seconds, granting a powerful shield for 60 seconds.",
       effect={"type": "shield", "base": 35, "per_level": 8, "duration": 60})


# ======================== LEVELS 21–30 ========================

_spell(name="Greater Heal", level=22, school=SCHOOL_RESTORATION, target=TARGET_SINGLE,
       mana_base=30, mana_per_lvl=4, cooldown=0,
       description="Potent divine energy washes over the target, restoring significant health.",
       effect={"type": "heal", "base": 55, "per_level": 12})

_spell(name="Ice Shard", level=24, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=28, mana_per_lvl=4, cooldown=0,
       description="Launch a razor-sharp shard of ice that pierces through armor.",
       effect={"type": "damage", "base": 50, "per_level": 10, "damage_type": "cold"},
       save_type="spell", save_negates=False)

_spell(name="Curse of Frailty", level=26, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=22, mana_per_lvl=3, cooldown=15,
       description="Weaken a target's constitution, reducing their maximum health for 25 seconds.",
       effect={"type": "debuff", "stat": "con", "amount": 6, "duration": 25},
       save_type="spell", save_negates=True)

_spell(name="Blizzard", level=28, school=SCHOOL_EVOCATION, target=TARGET_AOE,
       mana_base=35, mana_per_lvl=5, cooldown=10,
       description="Summon a freezing blizzard that ravages all enemies in the room.",
       effect={"type": "damage", "base": 30, "per_level": 8, "damage_type": "cold"},
       save_type="spell", save_negates=False)

_spell(name="Magic Armor", level=30, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=30, mana_per_lvl=4, cooldown=45,
       description="Conjure a suit of ethereal armor granting high protection for 60 seconds.",
       effect={"type": "shield", "base": 15, "per_level": 3, "duration": 60})

# Phase 7: Buff spell
_spell(name="Vitality", level=21, school=SCHOOL_ABJURATION, target=TARGET_SINGLE,
       mana_base=18, mana_per_lvl=2, cooldown=12,
       description="Fortify an ally's constitution for 30 seconds.",
       effect={"type": "buff", "stat": "con", "amount": 5, "duration": 30})

# Phase 7: DoT spell
_spell(name="Curse of Agony", level=23, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=20, mana_per_lvl=3, cooldown=8,
       description="Afflict a target with a shadow curse dealing damage over 20 seconds.",
       effect={"type": "dot", "dot_type": "curse", "base": 5, "per_level": 2, "duration": 20},
       save_type="spell", save_negates=True)

# Phase 7: Ritual spell
_spell(name="Mass Renewal", level=25, school=SCHOOL_RESTORATION, target=TARGET_AOE,
       mana_base=35, mana_per_lvl=5, cooldown=30, cast_time=6,
       description="Channel restorative energy for 6 seconds, then heal all allies in the room.",
       effect={"type": "heal", "base": 40, "per_level": 10})


# ======================== LEVELS 31–40 ========================

_spell(name="Thunderclap", level=32, school=SCHOOL_EVOCATION, target=TARGET_PBAOE,
       mana_base=40, mana_per_lvl=5, cooldown=8,
       description="Clap arcane thunder outward, damaging and staggering all nearby foes.",
       effect={"type": "damage", "base": 45, "per_level": 11, "damage_type": "sonic"},
       save_type="spell", save_negates=False)

_spell(name="Regeneration", level=34, school=SCHOOL_RESTORATION, target=TARGET_SINGLE,
       mana_base=38, mana_per_lvl=5, cooldown=0,
       description="Grant a target rapid health regeneration over 30 seconds.",
       effect={"type": "heal", "base": 40, "per_level": 10})

_spell(name="Mind Rot", level=36, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=30, mana_per_lvl=3, cooldown=18,
       description="Cloud the target's intellect, reducing their spell power for 20 seconds.",
       effect={"type": "debuff", "stat": "int", "amount": 10, "duration": 20},
       save_type="spell", save_negates=True)

_spell(name="Lava Burst", level=38, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=38, mana_per_lvl=5, cooldown=3,
       description="Erupt molten rock beneath a single enemy for massive direct damage.",
       effect={"type": "damage", "base": 80, "per_level": 16, "damage_type": "fire"},
       save_type="spell", save_negates=False)

_spell(name="Arcane Barrier", level=40, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=40, mana_per_lvl=5, cooldown=60,
       description="Raise a near-impenetrable arcane barrier absorbing heavy damage for 45 seconds.",
       effect={"type": "shield", "base": 40, "per_level": 8, "duration": 45})

# Phase 7: Buff spell
_spell(name="Brilliance", level=31, school=SCHOOL_ABJURATION, target=TARGET_SINGLE,
       mana_base=22, mana_per_lvl=3, cooldown=12,
       description="Sharpen an ally's intellect for 30 seconds.",
       effect={"type": "buff", "stat": "int", "amount": 6, "duration": 30})

# Phase 7: DoT spell
_spell(name="Lacerate", level=33, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=25, mana_per_lvl=3, cooldown=5,
       description="Cause deep bleeding wounds dealing physical damage over 15 seconds.",
       effect={"type": "dot", "dot_type": "bleed", "base": 8, "per_level": 3, "duration": 15},
       save_type="death", save_negates=False)


# ======================== LEVELS 41–50 ========================

_spell(name="Chain Lightning", level=42, school=SCHOOL_EVOCATION, target=TARGET_AOE,
       mana_base=48, mana_per_lvl=6, cooldown=10,
       description="Arcs of lightning bounce between all enemies in the room.",
       effect={"type": "damage", "base": 55, "per_level": 13, "damage_type": "lightning"},
       save_type="spell", save_negates=False)

_spell(name="Divine Restoration", level=44, school=SCHOOL_RESTORATION, target=TARGET_SINGLE,
       mana_base=50, mana_per_lvl=6, cooldown=0,
       description="Call upon divine power to fully restore a large portion of health.",
       effect={"type": "heal", "base": 110, "per_level": 25})

_spell(name="Paralyze", level=46, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=42, mana_per_lvl=5, cooldown=25,
       description="Freeze a target in place with dark tendrils for 12 seconds.",
       effect={"type": "stun", "duration": 12},
       save_type="petrification", save_negates=True)

_spell(name="Meteor Strike", level=48, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=55, mana_per_lvl=7, cooldown=6,
       description="Call a small meteor from the sky to obliterate a single target.",
       effect={"type": "damage", "base": 130, "per_level": 26, "damage_type": "fire"},
       save_type="spell", save_negates=False)

_spell(name="Aegis of Faith", level=50, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=50, mana_per_lvl=6, cooldown=90,
       description="Envelop yourself in a divine aegis that negates massive damage for 40 seconds.",
       effect={"type": "shield", "base": 60, "per_level": 12, "duration": 40})

# Phase 7: Buff spell
_spell(name="Wisdom of Ages", level=41, school=SCHOOL_ABJURATION, target=TARGET_SINGLE,
       mana_base=28, mana_per_lvl=4, cooldown=15,
       description="Imbue an ally with ancient wisdom for 30 seconds.",
       effect={"type": "buff", "stat": "wis", "amount": 7, "duration": 30})

# Phase 7: DoT spell
_spell(name="Plague", level=43, school=SCHOOL_ENFEEBLING, target=TARGET_AOE,
       mana_base=45, mana_per_lvl=6, cooldown=15,
       description="Spread a virulent plague to all enemies in the room, dealing poison damage over 18 seconds.",
       effect={"type": "dot", "dot_type": "poison", "base": 6, "per_level": 2, "duration": 18},
       save_type="poison", save_negates=False)

# Phase 7: Ritual spell
_spell(name="Apocalypse Ritual", level=45, school=SCHOOL_EVOCATION, target=TARGET_AOE,
       mana_base=60, mana_per_lvl=8, cooldown=60, cast_time=10,
       description="Channel apocalyptic energy for 10 seconds, then unleash devastating fire damage on all enemies.",
       effect={"type": "damage", "base": 100, "per_level": 22, "damage_type": "fire"},
       save_type="spell", save_negates=False)


# ======================== LEVELS 51–60 ========================

_spell(name="Shadow Bolt", level=52, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=55, mana_per_lvl=7, cooldown=2,
       description="Hurl a bolt of pure shadow energy that ignores partial armor.",
       effect={"type": "damage", "base": 160, "per_level": 30, "damage_type": "shadow"},
       save_type="spell", save_negates=False)

_spell(name="Mass Heal", level=54, school=SCHOOL_RESTORATION, target=TARGET_AOE,
       mana_base=70, mana_per_lvl=8, cooldown=0,
       description="Heal yourself and all allies in the same room.",
       effect={"type": "heal", "base": 70, "per_level": 14})

_spell(name="Withering Curse", level=56, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=50, mana_per_lvl=6, cooldown=20,
       description="Lay a crippling curse on the target reducing all stats for 30 seconds.",
       effect={"type": "debuff_all", "amount": 8, "duration": 30},
       save_type="spell", save_negates=True)

_spell(name="Earthquake", level=58, school=SCHOOL_EVOCATION, target=TARGET_PBAOE,
       mana_base=65, mana_per_lvl=8, cooldown=15,
       description="Shatter the ground, dealing heavy damage to all enemies in the room.",
       effect={"type": "damage", "base": 80, "per_level": 16, "damage_type": "bludgeoning"},
       save_type="spell", save_negates=False)

_spell(name="Prismatic Ward", level=60, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=65, mana_per_lvl=8, cooldown=90,
       description="A multi-layered ward that absorbs all magic types for 60 seconds.",
       effect={"type": "shield", "base": 80, "per_level": 16, "duration": 60})

# Phase 7: Buff spell
_spell(name="Haste", level=51, school=SCHOOL_ABJURATION, target=TARGET_SINGLE,
       mana_base=35, mana_per_lvl=5, cooldown=20,
       description="Grant an ally supernatural speed, boosting dexterity for 25 seconds.",
       effect={"type": "buff", "stat": "dex", "amount": 10, "duration": 25})

# Phase 7: DoT spell
_spell(name="Immolate", level=53, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=40, mana_per_lvl=5, cooldown=6,
       description="Engulf a target in searing flames dealing heavy fire damage over 12 seconds.",
       effect={"type": "dot", "dot_type": "burn", "base": 12, "per_level": 4, "duration": 12},
       save_type="spell", save_negates=False)


# ======================== LEVELS 61–70 ========================

_spell(name="Arcane Tempest", level=62, school=SCHOOL_EVOCATION, target=TARGET_AOE,
       mana_base=75, mana_per_lvl=9, cooldown=12,
       description="Unleash a violent storm of arcane energy decimating all foes.",
       effect={"type": "damage", "base": 100, "per_level": 20, "damage_type": "arcane"},
       save_type="spell", save_negates=False)

_spell(name="Restoration Aura", level=64, school=SCHOOL_RESTORATION, target=TARGET_SELF,
       mana_base=70, mana_per_lvl=9, cooldown=30,
       description="An aura of healing that restores health every few seconds for 20 seconds.",
       effect={"type": "heal_over_time", "base": 50, "per_level": 10, "duration": 20})

_spell(name="Dread Gaze", level=66, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=60, mana_per_lvl=7, cooldown=28,
       description="Lock eyes with the target, terrifying them into paralysis for 15 seconds.",
       effect={"type": "stun", "duration": 15},
       save_type="petrification", save_negates=True)

_spell(name="Soul Drain", level=68, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=72, mana_per_lvl=9, cooldown=4,
       description="Rip the life force from a target, dealing damage and healing yourself.",
       effect={"type": "lifesteal", "base": 180, "per_level": 36, "heal_pct": 0.5, "damage_type": "shadow"},
       save_type="death", save_negates=True)

_spell(name="Sanctuary", level=70, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=80, mana_per_lvl=10, cooldown=120,
       description="Create an impenetrable sanctuary absorbing all damage for 15 seconds.",
       effect={"type": "shield", "base": 120, "per_level": 24, "duration": 15})

# Phase 7: Buff spell
_spell(name="Divine Might", level=61, school=SCHOOL_ABJURATION, target=TARGET_SINGLE,
       mana_base=45, mana_per_lvl=6, cooldown=20,
       description="Infuse an ally with divine power, greatly boosting strength for 25 seconds.",
       effect={"type": "buff", "stat": "str", "amount": 12, "duration": 25})

# Phase 7: DoT spell
_spell(name="Hemorrhage", level=63, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=50, mana_per_lvl=6, cooldown=8,
       description="Cause massive internal bleeding dealing heavy physical damage over 15 seconds.",
       effect={"type": "dot", "dot_type": "bleed", "base": 15, "per_level": 5, "duration": 15},
       save_type="death", save_negates=False)

# Phase 7: Ritual spell
_spell(name="Grand Restoration", level=65, school=SCHOOL_RESTORATION, target=TARGET_SINGLE,
       mana_base=60, mana_per_lvl=8, cooldown=45, cast_time=8,
       description="Channel powerful restorative magic for 8 seconds, then unleash a massive heal.",
       effect={"type": "heal", "base": 200, "per_level": 45})


# ======================== LEVELS 71–80 ========================

_spell(name="Apocalypse", level=72, school=SCHOOL_EVOCATION, target=TARGET_AOE,
       mana_base=90, mana_per_lvl=11, cooldown=20,
       description="Rain down apocalyptic fire on every enemy in the room.",
       effect={"type": "damage", "base": 150, "per_level": 28, "damage_type": "fire"},
       save_type="spell", save_negates=False)

_spell(name="Divine Blessing", level=74, school=SCHOOL_RESTORATION, target=TARGET_SINGLE,
       mana_base=95, mana_per_lvl=11, cooldown=0,
       description="A supreme blessing that restores a massive amount of health.",
       effect={"type": "heal", "base": 300, "per_level": 60})

_spell(name="Petrify", level=76, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=80, mana_per_lvl=10, cooldown=35,
       description="Turn a target to stone, stunning them for 18 seconds.",
       effect={"type": "stun", "duration": 18},
       save_type="petrification", save_negates=True)

_spell(name="Void Rift", level=78, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=100, mana_per_lvl=12, cooldown=5,
       description="Open a rift to the void, dealing catastrophic damage to a single target.",
       effect={"type": "damage", "base": 280, "per_level": 55, "damage_type": "shadow"},
       save_type="spell", save_negates=False)

_spell(name="Meteor Swarm", level=80, school=SCHOOL_EVOCATION, target=TARGET_AOE,
       mana_base=110, mana_per_lvl=13, cooldown=25,
       description="Call down a devastating swarm of meteors, the ultimate evocation.",
       effect={"type": "damage", "base": 200, "per_level": 40, "damage_type": "fire"},
       save_type="spell", save_negates=False)

# Phase 7: Ultimate buff
_spell(name="Avatar", level=71, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=70, mana_per_lvl=9, cooldown=120,
       description="Transform into an avatar of power, boosting all stats for 20 seconds.",
       effect={"type": "buff_all", "amount": 10, "duration": 20})

# Phase 7: Ultimate DoT
_spell(name="Soul Rot", level=73, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=65, mana_per_lvl=8, cooldown=12,
       description="Afflict a target with a devastating shadow curse dealing massive damage over 20 seconds.",
       effect={"type": "dot", "dot_type": "curse", "base": 18, "per_level": 6, "duration": 20},
       save_type="spell", save_negates=True)

# Phase 7: Ultimate ritual
_spell(name="Cataclysm", level=75, school=SCHOOL_EVOCATION, target=TARGET_AOE,
       mana_base=100, mana_per_lvl=12, cooldown=90, cast_time=12,
       description="Channel world-shattering power for 12 seconds, then unleash catastrophic damage on all enemies.",
       effect={"type": "damage", "base": 250, "per_level": 50, "damage_type": "fire"},
       save_type="spell", save_negates=False)

# Phase 7: Spell resistance buff
_spell(name="Magic Resistance", level=8, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=15, mana_per_lvl=2, cooldown=30,
       description="Surround yourself with anti-magic wards, gaining spell resistance for 60 seconds.",
       effect={"type": "spell_resist_buff", "amount": 15, "duration": 60})

# ======================== Phase 3.4: EXPANDED SPELLS (60+ total) ========================

# ---- Mid-tier utility & damage fillers (levels 10-35) ----

_spell(name="Arcane Blast", level=10, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=18, mana_per_lvl=3, cooldown=2,
       description="Launch a focused blast of pure arcane energy at a single target.",
       effect={"type": "damage", "base": 26, "per_level": 6, "damage_type": "arcane"},
       save_type="spell", save_negates=False)

_spell(name="Healing Touch", level=8, school=SCHOOL_RESTORATION, target=TARGET_SINGLE,
       mana_base=16, mana_per_lvl=2, cooldown=0,
       description="Lay hands upon a target to mend moderate wounds.",
       effect={"type": "heal", "base": 25, "per_level": 6})

_spell(name="Barrier", level=17, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=24, mana_per_lvl=3, cooldown=35,
       description="Summon a swift protective barrier for 30 seconds.",
       effect={"type": "shield", "base": 25, "per_level": 6, "duration": 30})

_spell(name="Silence", level=19, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=20, mana_per_lvl=2, cooldown=15,
       description="Silence a target, preventing spellcasting for 8 seconds.",
       effect={"type": "debuff", "stat": "int", "amount": 12, "duration": 8},
       save_type="spell", save_negates=True)

_spell(name="Divine Favor", level=27, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=30, mana_per_lvl=4, cooldown=45,
       description="Call upon divine favor, greatly boosting all stats for 30 seconds.",
       effect={"type": "buff_all", "amount": 6, "duration": 30})

_spell(name="Chain Heal", level=29, school=SCHOOL_RESTORATION, target=TARGET_SINGLE,
       mana_base=35, mana_per_lvl=4, cooldown=0,
       description="A powerful heal that also restores nearby allies for a portion of the amount.",
       effect={"type": "heal", "base": 60, "per_level": 12})

_spell(name="Ice Barrier", level=35, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=38, mana_per_lvl=5, cooldown=50,
       description="Encase yourself in ice, absorbing damage for 40 seconds.",
       effect={"type": "shield", "base": 45, "per_level": 9, "duration": 40})

# ---- Crowd-control & support (levels 37-59) ----

_spell(name="Blind", level=37, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=30, mana_per_lvl=3, cooldown=20,
       description="Blind a target, reducing their accuracy for 10 seconds.",
       effect={"type": "debuff", "stat": "dex", "amount": 15, "duration": 10},
       save_type="spell", save_negates=True)

_spell(name="Mass Shield", level=39, school=SCHOOL_ABJURATION, target=TARGET_AOE,
       mana_base=45, mana_per_lvl=5, cooldown=60,
       description="Grant a protective shield to all allies in the room.",
       effect={"type": "shield", "base": 40, "per_level": 8, "duration": 30})

_spell(name="Renewing Wave", level=47, school=SCHOOL_RESTORATION, target=TARGET_AOE,
       mana_base=50, mana_per_lvl=6, cooldown=20,
       description="A wave of restorative energy heals all allies in the room.",
       effect={"type": "heal", "base": 90, "per_level": 18})

_spell(name="Stoneskin Totem", level=49, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=55, mana_per_lvl=6, cooldown=90,
       description="Transform your skin to living stone, absorbing massive damage for 45 seconds.",
       effect={"type": "shield", "base": 70, "per_level": 14, "duration": 45})

_spell(name="Mana Tap", level=52, school=SCHOOL_ENFEEBLING, target=TARGET_SINGLE,
       mana_base=40, mana_per_lvl=5, cooldown=15,
       description="Drain a target's mana, restoring your own.",
       effect={"type": "lifesteal", "base": 50, "per_level": 10, "heal_pct": 0.4, "damage_type": "arcane"},
       save_type="spell", save_negates=True)

_spell(name="Frost Armor", level=55, school=SCHOOL_ABJURATION, target=TARGET_SELF,
       mana_base=60, mana_per_lvl=7, cooldown=60,
       description="Surround yourself with freezing air, absorbing damage and slowing attackers for 50 seconds.",
       effect={"type": "shield", "base": 90, "per_level": 18, "duration": 50})

_spell(name="Lifebloom", level=57, school=SCHOOL_RESTORATION, target=TARGET_SELF,
       mana_base=55, mana_per_lvl=6, cooldown=25,
       description="A bloom of life energy heals you over time for 20 seconds.",
       effect={"type": "heal_over_time", "base": 70, "per_level": 14, "duration": 20})

_spell(name="Time Dilation", level=59, school=SCHOOL_ABJURATION, target=TARGET_SINGLE,
       mana_base=65, mana_per_lvl=7, cooldown=90,
       description="Greatly boost an ally's dexterity and speed for 30 seconds.",
       effect={"type": "buff", "stat": "dex", "amount": 15, "duration": 30})

# ---- Endgame (levels 62-80) ----

_spell(name="Mass Invisibility", level=62, school=SCHOOL_ABJURATION, target=TARGET_AOE,
       mana_base=70, mana_per_lvl=8, cooldown=120,
       description="Grant invisibility to all allies in the room for 15 seconds.",
       effect={"type": "buff_all", "amount": 8, "duration": 15})

_spell(name="Wrath of the Gods", level=64, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=75, mana_per_lvl=9, cooldown=8,
       description="Call down divine wrath on a single target for immense holy damage.",
       effect={"type": "damage", "base": 220, "per_level": 44, "damage_type": "holy"},
       save_type="spell", save_negates=False)

_spell(name="Chaos Bolt", level=66, school=SCHOOL_EVOCATION, target=TARGET_SINGLE,
       mana_base=80, mana_per_lvl=9, cooldown=5,
       description="Unleash a bolt of pure chaos that deals random elemental damage.",
       effect={"type": "damage", "base": 240, "per_level": 48, "damage_type": "chaos"},
       save_type="spell", save_negates=False)

_spell(name="Guardian Spirit", level=68, school=SCHOOL_ABJURATION, target=TARGET_SINGLE,
       mana_base=85, mana_per_lvl=10, cooldown=120,
       description="Summon a guardian spirit to absorb damage for an ally for 30 seconds.",
       effect={"type": "shield", "base": 150, "per_level": 30, "duration": 30})

_spell(name="Mass Resurrection", level=70, school=SCHOOL_RESTORATION, target=TARGET_AOE,
       mana_base=100, mana_per_lvl=12, cooldown=300, cast_time=10,
       description="Channel divine power for 10 seconds, then revive all fallen allies in the room.",
       effect={"type": "heal", "base": 400, "per_level": 80})

_spell(name="Arcane Singularity", level=74, school=SCHOOL_EVOCATION, target=TARGET_AOE,
       mana_base=95, mana_per_lvl=11, cooldown=30,
       description="Create a collapsing arcane singularity, pulling in and damaging all enemies.",
       effect={"type": "damage", "base": 220, "per_level": 42, "damage_type": "arcane"},
       save_type="spell", save_negates=False)

_spell(name="Divine Intervention", level=76, school=SCHOOL_RESTORATION, target=TARGET_SELF,
       mana_base=90, mana_per_lvl=10, cooldown=180,
       description="Call upon the divine to fully restore your health and mana.",
       effect={"type": "heal", "base": 500, "per_level": 100})

_spell(name="World Breaker", level=78, school=SCHOOL_EVOCATION, target=TARGET_AOE,
       mana_base=110, mana_per_lvl=13, cooldown=45,
       description="Shatter the very earth beneath all enemies, dealing massive damage.",
       effect={"type": "damage", "base": 300, "per_level": 60, "damage_type": "bludgeoning"},
       save_type="spell", save_negates=False)

_spell(name="Judgment", level=80, school=SCHOOL_EVOCATION, target=TARGET_AOE,
       mana_base=120, mana_per_lvl=14, cooldown=60, cast_time=6,
       description="Channel ultimate judgment for 6 seconds, then smite all enemies in the room.",
       effect={"type": "damage", "base": 350, "per_level": 70, "damage_type": "holy"},
       save_type="spell", save_negates=False)


# ---------------------------------------------------------------------------
# SPELL REGISTRY HELPERS
# ---------------------------------------------------------------------------

def get_spell(spell_name):
    """Look up a spell by its key (lowercase no spaces)."""
    key = spell_name.lower().replace(" ", "")
    return SPELLS.get(key)


def get_spells_for_level(level):
    """Return all spells available at or below a given level, sorted by level."""
    available = [s for s in SPELLS.values() if s["level"] <= level]
    return sorted(available, key=lambda s: s["level"])


def get_spells_by_school(level, school=None):
    """Return spells for a given level grouped by school."""
    spells = get_spells_for_level(level)
    if school:
        return [s for s in spells if s["school"] == school]
    return spells


# ---------------------------------------------------------------------------
# SPELL RESISTANCE (Phase 7)
# ---------------------------------------------------------------------------

def get_spell_resistance(character) -> int:
    """
    Calculate total spell resistance for a character.
    Sources:
      - Racial base spell resistance
      - Equipment spell resistance bonuses
      - Active spell resistance buffs
      - Wisdom bonus (minor)
    Returns a percentage (0-100) chance to partially resist magic damage.
    """
    if not hasattr(character, "attributes"):
        return 0

    resist = 0

    # Racial spell resistance
    race = character.attributes.get("race", "Human")
    racial_resist = {
        "Mountain Dwarf": 10,
        "Dark Elf": 10,
        "Undead": 5,
        "Demonkin": 8,
        "Pixie": 12,
        "Gnome": 8,
        "High Elf": 5,
        "Orc": -5,
        "Ogre": -10,
        "Minotaur": -5,
    }
    resist += racial_resist.get(race, 0)

    # Wisdom bonus (minor)
    stats = character.attributes.get("stats", {})
    wis = stats.get("wis", 10)
    resist += max(0, (wis - 10) // 2)

    # Equipment spell resistance
    eq_resist = character.attributes.get("spell_resist", 0)
    resist += eq_resist

    # Active spell resistance buff
    buff_resist = character.attributes.get("spell_resist_buff", 0)
    resist += buff_resist

    # Phase 2.3: Arcane Shielding talent grants +3% magic resistance per rank.
    try:
        from world.skill_tree import get_talent_bonuses
        resist += int(get_talent_bonuses(character).get("magic_resist_pct", 0))
    except Exception:
        pass

    return max(-50, min(75, resist))


def apply_spell_resistance(damage: int, target, caster=None) -> int:
    """
    Apply spell resistance to reduce incoming magic damage.
    Returns the reduced damage amount.

    Phase 2.3: If *caster* is supplied, the caster's Spell Penetration
    talent reduces the target's effective magic resistance before damage
    is mitigated.
    """
    resist = get_spell_resistance(target)

    # Phase 2.3: Spell Penetration ignores 2% of target resistance per rank.
    if caster is not None:
        try:
            from world.skill_tree import get_talent_bonuses
            pen_pct = int(get_talent_bonuses(caster).get("spell_pen_pct", 0))
            if pen_pct:
                resist = max(0, resist - pen_pct)
        except Exception:
            pass

    if resist <= 0:
        return damage

    # Each point of resistance reduces damage by 1%, up to 75% max
    reduction_pct = min(0.75, resist / 100.0)
    reduced = int(damage * (1.0 - reduction_pct))
    return max(1, reduced)


# ---------------------------------------------------------------------------
# SPELL RESOLVER  (damage / heal calculations applied to targets)
# ---------------------------------------------------------------------------

def _resolve_mana_cost(spell_def, caster_level):
    """Calc mana cost."""
    return spell_def["mana_base"] + spell_def["mana_per_lvl"] * caster_level


def _resolve_damage(spell_def, caster_level, caster):
    """Calculate raw magic damage."""
    eff = spell_def["effect"]
    base = eff.get("base", 0)
    per_lvl = eff.get("per_level", 0)
    raw = base + per_lvl * caster_level
    # Bonus from casting stat
    stat = _casting_stat(caster)
    raw += int(stat * 0.6)
    # Phase 2.3: Arcane Focus talent grants +1 spell damage per rank.
    try:
        from world.skill_tree import get_talent_bonuses
        raw += int(get_talent_bonuses(caster).get("spell_damage", 0))
    except Exception:
        pass
    return max(1, raw)


def _resolve_heal(spell_def, caster_level, caster):
    """Calculate raw healing amount."""
    eff = spell_def["effect"]
    base = eff.get("base", 0)
    per_lvl = eff.get("per_level", 0)
    raw = base + per_lvl * caster_level
    stat = _casting_stat(caster)
    raw += int(stat * 0.5)
    return max(1, raw)


def _resolve_shield(spell_def, caster_level, caster):
    """Calculate shield absorption amount."""
    eff = spell_def["effect"]
    base = eff.get("base", 0)
    per_lvl = eff.get("per_level", 0)
    raw = base + per_lvl * caster_level
    stat = _casting_stat(caster)
    raw += int(stat * 0.4)
    return max(1, raw)


def _resolve_dot_damage(spell_def, caster_level, caster):
    """Calculate per-tick DoT damage."""
    eff = spell_def["effect"]
    base = eff.get("base", 0)
    per_lvl = eff.get("per_level", 0)
    raw = base + per_lvl * caster_level
    stat = _casting_stat(caster)
    raw += int(stat * 0.2)
    return max(1, raw)


# ---------------------------------------------------------------------------
# SPELL HANDLER  (performs cast logic on the character)
# ---------------------------------------------------------------------------

class SpellHandler:
    """
    Handles spell casting for a character.
    Attached as character.spells.

    Phase 7: Full integration of damage types, saving throws, status effects,
    buffs, DoTs, spell resistance, and ritual/channeled casting.
    """

    def __init__(self, character):
        self.character = character

    @property
    def level(self):
        return self.character.attributes.get("level", 1)

    @property
    def mana(self):
        return self.character.attributes.get("mana", 0)

    @mana.setter
    def mana(self, value):
        self.character.attributes.add("mana", max(0, value))

    @property
    def max_mana(self):
        return self.character.attributes.get("max_mana", 10)

    @property
    def casting_stat(self):
        """Return the casting stat value for save DC calculations."""
        return _casting_stat(self.character)

    def available_spells(self, school=None):
        """Return spells this character can cast (by level), filtered by race/class gating."""
        from world.race_class_matrix import can_learn_spell
        spells = get_spells_by_school(self.level, school=school)
        return [s for s in spells if can_learn_spell(self.character, s["key"])[0]]

    def can_cast(self, spell_name):
        """Check all preconditions: exists, level, mana, cooldown, race/class gating."""
        spell = get_spell(spell_name)
        if not spell:
            return False, "You don't know that spell."

        # ===== CRITICAL GATE: Race/Class permission check =====
        from world.race_class_matrix import can_learn_spell
        allowed, reason = can_learn_spell(self.character, spell_name)
        if not allowed:
            return False, reason
        # ======================================================

        if spell["level"] > self.level:
            return False, f"You must be level {spell['level']} to cast {spell['name']}."

        cost = _resolve_mana_cost(spell, self.level)
        if self.mana < cost:
            return False, f"Not enough mana. You need {cost} MP (have {self.mana})."

        # Cooldown check
        cooldowns = self.character.attributes.get("spell_cooldowns", {})
        if cooldowns:
            remaining = cooldowns.get(spell["key"], 0) - time.time()
            if remaining > 0:
                return False, f"{spell['name']} is on cooldown for {int(remaining)}s."

        # Phase 7: Check if already channeling
        if self.character.attributes.get("is_channeling", False):
            return False, "You are already channeling a spell!"

        return True, None

    def cast(self, spell_name, target=None, caller=None):
        """
        Execute a spell cast. Returns (success: bool, message: str).
        `target` is a character object or None for self-cast.
        `caller` is used for messaging (usually self.character).

        Phase 7: Supports ritual/channeled spells with cast_time.
        """
        if caller is None:
            caller = self.character

        spell = get_spell(spell_name)
        if not spell:
            return False, "You don't know that spell."

        can, err = self.can_cast(spell_name)
        if not can:
            return False, err

        cost = _resolve_mana_cost(spell, self.level)
        self.mana = self.mana - cost

        # Set cooldown (Phase 2.3: Channeling Mastery reduces cooldown by 5% per rank)
        if spell["cooldown"] > 0:
            try:
                from world.skill_tree import get_talent_bonuses
                cdr_pct = int(get_talent_bonuses(self.character).get("spell_cdr_pct", 0))
            except Exception:
                cdr_pct = 0
            effective_cd = max(1, int(spell["cooldown"] * (1.0 - cdr_pct / 100.0)))
            cooldowns = self.character.attributes.get("spell_cooldowns", {})
            cooldowns[spell["key"]] = time.time() + effective_cd
            self.character.attributes.add("spell_cooldowns", cooldowns)

        # Phase 7: Ritual/channeled spells
        cast_time = spell.get("cast_time", 0)
        if cast_time > 0:
            return self._start_channeling(spell, target, caller, cast_time)

        # Instant cast
        return self._execute_spell(spell, target, caller)

    def _start_channeling(self, spell, target, caller, cast_time):
        """Begin channeling a ritual spell. The spell fires after cast_time seconds."""
        self.character.attributes.add("is_channeling", True)
        self.character.attributes.add("channeling_spell", spell["key"])
        self.character.attributes.add("channeling_target", target.dbref if target else None)

        caller.msg(f"|yYou begin channeling |w{spell['name']}|y... ({cast_time}s cast time)|n")
        caller.location.msg_contents(
            f"|y{caller.key} begins channeling |w{spell['name']}|y...|n",
            exclude=[caller]
        )

        from evennia.utils import delay
        delay(cast_time, self._complete_channel, spell, target, caller)
        return True, f"Channeling {spell['name']}..."

    def _complete_channel(self, spell, target, caller):
        """Callback when a channeled spell completes."""
        # Check if channeling was interrupted
        if not self.character.attributes.get("is_channeling", False):
            return

        channeling_spell = self.character.attributes.get("channeling_spell", "")
        if channeling_spell != spell["key"]:
            return

        self.character.attributes.add("is_channeling", False)
        self.character.attributes.add("channeling_spell", "")
        self.character.attributes.add("channeling_target", None)

        # Re-resolve target from dbref
        if target is None:
            stored_dbref = self.character.attributes.get("channeling_target", None)
            if stored_dbref:
                target = search.search_object(stored_dbref)
                if target:
                    target = target[0] if isinstance(target, list) else target

        caller.msg(f"|gYou complete channeling |w{spell['name']}|g!|n")
        caller.location.msg_contents(
            f"|g{caller.key} unleashes |w{spell['name']}|g!|n",
            exclude=[caller]
        )

        success, msg = self._execute_spell(spell, target, caller)
        if success:
            caller.msg(msg)

    def interrupt_channeling(self, reason="Your concentration is broken!"):
        """Interrupt an active channel (called when taking damage, stunned, etc.)."""
        if not self.character.attributes.get("is_channeling", False):
            return

        spell_name = self.character.attributes.get("channeling_spell", "the spell")
        spell = get_spell(spell_name)
        display_name = spell["name"] if spell else spell_name

        self.character.attributes.add("is_channeling", False)
        self.character.attributes.add("channeling_spell", "")
        self.character.attributes.add("channeling_target", None)

        self.character.msg(f"|r{reason}|n")
        self.character.location.msg_contents(
            f"|r{self.character.key}'s channeling of {display_name} is interrupted!|n",
            exclude=[self.character]
        )

    def _execute_spell(self, spell, target, caller):
        """Core spell execution after any channeling completes."""
        school = spell["school"]
        eff = spell["effect"]
        etype = eff.get("type", "damage")
        caster = self.character
        caster_level = self.level

        # --- Resolve by type ---
        if etype == "damage":
            dmg = _resolve_damage(spell, caster_level, caster)
            return self._apply_damage(spell, target, dmg, caller)

        elif etype == "heal":
            heal = _resolve_heal(spell, caster_level, caster)
            return self._apply_heal(spell, target, heal, caller)

        elif etype == "shield":
            shield_amt = _resolve_shield(spell, caster_level, caster)
            duration = eff.get("duration", 30)
            return self._apply_shield(spell, shield_amt, duration, caller)

        elif etype == "debuff":
            stat = eff.get("stat", "str")
            amount = eff.get("amount", 5)
            duration = eff.get("duration", 15)
            return self._apply_debuff(spell, target, stat, amount, duration, caller)

        elif etype == "debuff_all":
            amount = eff.get("amount", 8)
            duration = eff.get("duration", 30)
            return self._apply_debuff_all(spell, target, amount, duration, caller)

        elif etype == "stun":
            duration = eff.get("duration", 10)
            return self._apply_stun(spell, target, duration, caller)

        elif etype == "lifesteal":
            dmg = _resolve_damage(spell, caster_level, caster)
            heal_pct = eff.get("heal_pct", 0.5)
            heal_self = int(dmg * heal_pct)
            ok1, msg1 = self._apply_damage(spell, target, dmg, caller)
            if ok1:
                self._apply_heal_raw(heal_self, caller)
                return True, f"{msg1} You drain {heal_self} life from the target."
            return ok1, msg1

        elif etype == "heal_over_time":
            heal_per_tick = _resolve_heal(spell, caster_level, caster) // 4
            duration = eff.get("duration", 20)
            return self._apply_hot(spell, heal_per_tick, duration, caller)

        # Phase 7: Buff spells
        elif etype == "buff":
            stat = eff.get("stat", "str")
            amount = eff.get("amount", 5)
            duration = eff.get("duration", 30)
            return self._apply_buff(spell, target, stat, amount, duration, caller)

        elif etype == "buff_all":
            amount = eff.get("amount", 10)
            duration = eff.get("duration", 20)
            return self._apply_buff_all(spell, target, amount, duration, caller)

        # Phase 7: DoT spells
        elif etype == "dot":
            dot_type = eff.get("dot_type", "poison")
            dmg_per_tick = _resolve_dot_damage(spell, caster_level, caster)
            duration = eff.get("duration", 15)
            return self._apply_dot(spell, target, dot_type, dmg_per_tick, duration, caller)

        # Phase 7: Spell resistance buff
        elif etype == "spell_resist_buff":
            amount = eff.get("amount", 15)
            duration = eff.get("duration", 60)
            return self._apply_spell_resist_buff(spell, amount, duration, caller)

        # Phase 7: Restore mana
        elif etype == "restore_mana":
            base = eff.get("base", 15)
            per_lvl = eff.get("per_level", 5)
            restore = base + per_lvl * caster_level
            return self._apply_restore_mana(spell, restore, caller)

        return False, "Unknown spell effect type."

    # ---- Saving throw helper ----

    def _check_saving_throw(self, spell, target) -> bool:
        """
        Perform a saving throw against a hostile spell.
        Returns True if the target saved (effect negated).
        """
        save_type = spell.get("save_type", "spell")
        if not save_type:
            return False

        from world.saving_throws import roll_saving_throw, SavingThrow, calculate_dc, format_save_result

        save_map = {
            "poison": SavingThrow.POISON,
            "death": SavingThrow.DEATH,
            "petrification": SavingThrow.PETRIFICATION,
            "rod": SavingThrow.ROD,
            "spell": SavingThrow.SPELL,
        }
        st = save_map.get(save_type, SavingThrow.SPELL)

        dc = calculate_dc(self.level, self.casting_stat, spell["level"])
        passed, roll, dc = roll_saving_throw(target, st, dc=dc)

        if passed:
            msg = format_save_result(target, st, True, roll, dc)
            self.character.msg(msg)
            target.msg(msg)
            return True

        return False

    # ---- Application helpers ----

    def _apply_damage(self, spell, target, dmg, caller):
        if not target:
            return False, "You need a target for that spell."

        # Phase 1.2: Saving throw check (half damage on save, unless save_negates)
        if spell.get("save_negates", False):
            if self._check_saving_throw(spell, target):
                return True, f"{target.key} resists {spell['name']} entirely!"

        # Phase 7: Apply spell resistance (caster passed for Spell Penetration talent)
        dmg = apply_spell_resistance(dmg, target, caster=self.character)

        # Phase 1.2: Apply damage type modifier
        damage_type = spell["effect"].get("damage_type", "arcane")
        from world.damage_types import apply_damage_with_type, DAMAGE_TYPE_DISPLAY
        dmg = apply_damage_with_type(dmg, damage_type, target)

        # Integrate with combat handler if available
        try:
            from world.combat import apply_magic_damage
            result = apply_magic_damage(caster=self.character, target=target, damage=dmg, spell_name=spell["name"])
            # Phase 1.2: Check break-on-damage for mez effects on target
            self._check_break_on_damage(target, dmg)
            return True, result
        except ImportError:
            # Fallback: direct HP reduction
            hp = target.attributes.get("hp", 0)
            max_hp = target.attributes.get("max_hp", 1)
            actual = min(dmg, hp)
            target.attributes.add("hp", max(0, hp - dmg))
            dt_display = DAMAGE_TYPE_DISPLAY.get(damage_type, damage_type)
            caller.msg(f"|rYou cast {spell['name']} on {target.key} for {actual} {dt_display} damage!|n")
            if target != caller:
                target.msg(f"|r{caller.key} casts {spell['name']} on you for {actual} {dt_display} damage!|n")
            caller.location.msg_contents(
                f"|r{caller.key} casts {spell['name']} on {target.key}!|n",
                exclude=[caller, target]
            )
            self._check_break_on_damage(target, dmg)
            return True, f"You hit {target.key} with {spell['name']} for {actual} {dt_display} damage."

    def _check_break_on_damage(self, target, dmg):
        """Check if damage breaks active mez effects on the target."""
        try:
            from world.status_effects import get_active_effects
            effects = get_active_effects(target)
            if effects:
                messages = effects.check_break_on_damage(dmg)
                for msg in messages:
                    target.msg(msg)
                    if target.location:
                        target.location.msg_contents(msg, exclude=[target])
        except ImportError:
            pass

    def _apply_heal(self, spell, target, heal_amt, caller):
        tgt = target or self.character
        max_hp = tgt.attributes.get("max_hp", 100)
        current_hp = tgt.attributes.get("hp", 0)
        healed = min(heal_amt, max_hp - current_hp)
        tgt.attributes.add("hp", current_hp + healed)
        caller.msg(f"|gYou cast {spell['name']} on {tgt.key}, healing for {healed} HP.|n")
        if tgt != caller:
            tgt.msg(f"|g{caller.key} casts {spell['name']} on you, healing {healed} HP.|n")
        caller.location.msg_contents(
            f"|g{caller.key} heals {tgt.key} with {spell['name']}.|n",
            exclude=[caller, tgt]
        )
        return True, f"Healed {tgt.key} for {healed} HP."

    def _apply_heal_raw(self, heal_amt, caller):
        """Heal self without messaging (used internally by lifesteal)."""
        max_hp = caller.attributes.get("max_hp", 100)
        current_hp = caller.attributes.get("hp", 0)
        healed = min(heal_amt, max_hp - current_hp)
        caller.attributes.add("hp", current_hp + healed)

    def _apply_shield(self, spell, amount, duration, caller):
        self.character.attributes.add("shield_amount", amount)
        self.character.attributes.add("shield_expires", 0)
        caller.msg(f"|bYou cast {spell['name']}, gaining a shield absorbing {amount} damage for {duration}s.|n")
        caller.location.msg_contents(
            f"|b{caller.key} is surrounded by a magical barrier.|n",
            exclude=[caller]
        )
        from evennia.utils import delay
        delay(duration, self._remove_shield, caller)
        return True, f"Shield of {amount} absorption applied."

    def _remove_shield(self, caller):
        caller.attributes.add("shield_amount", 0)
        caller.msg("|bYour magical shield fades away.|n")

    def _apply_debuff(self, spell, target, stat, amount, duration, caller):
        if not target:
            return False, "You need a target for that spell."

        # Phase 1.2: Saving throw check
        if spell.get("save_negates", False):
            if self._check_saving_throw(spell, target):
                return True, f"{target.key} resists {spell['name']}!"

        # Phase 1.2: Use status_effects system for debuff tracking
        try:
            from world.status_effects import create_stat_debuff_effect, apply_status_effect
            from world.saving_throws import calculate_dc
            dc = calculate_dc(self.level, self.casting_stat, spell["level"])
            effect = create_stat_debuff_effect(
                stat=stat, amount=amount, duration=duration,
                source=self.character, source_level=self.level,
                source_stat=self.casting_stat, save_dc=dc
            )
            applied, msg = apply_status_effect(target, effect)
            if applied:
                caller.msg(f"|mYou cast {spell['name']} on {target.key}, reducing {stat.upper()} by {amount} for {duration}s.|n")
                target.msg(f"|m{caller.key} casts {spell['name']} on you! Your {stat.upper()} drops by {amount}.|n")
                return True, f"Debuffed {target.key}: -{amount} {stat.upper()}."
            else:
                caller.msg(f"|y{msg}|n")
                return False, msg
        except ImportError:
            # Fallback to old behavior
            stats = target.attributes.get("stats", {})
            original = stats.get(stat, 10)
            stats[stat] = max(1, original - amount)
            target.attributes.add("stats", stats)
            caller.msg(f"|mYou cast {spell['name']} on {target.key}, reducing {stat.upper()} by {amount} for {duration}s.|n")
            target.msg(f"|m{caller.key} casts {spell['name']} on you! Your {stat.upper()} drops by {amount}.|n")
            from evennia.utils import delay
            delay(duration, self._remove_debuff, target, stat, amount)
            return True, f"Debuffed {target.key}: -{amount} {stat.upper()}."

    def _remove_debuff(self, target, stat, amount):
        stats = target.attributes.get("stats", {})
        stats[stat] = stats.get(stat, 10) + amount
        target.attributes.add("stats", stats)
        target.msg(f"|mYour {stat.upper()} returns to normal.|n")

    def _apply_debuff_all(self, spell, target, amount, duration, caller):
        if not target:
            return False, "You need a target for that spell."

        # Phase 1.2: Saving throw check
        if spell.get("save_negates", False):
            if self._check_saving_throw(spell, target):
                return True, f"{target.key} resists {spell['name']}!"

        stats = target.attributes.get("stats", {})
        for s in ["str", "dex", "con", "int", "wis", "cha"]:
            stats[s] = max(1, stats.get(s, 10) - amount)
        target.attributes.add("stats", stats)
        caller.msg(f"|mYou cast {spell['name']} on {target.key}, reducing all stats by {amount} for {duration}s.|n")
        target.msg(f"|m{caller.key} casts {spell['name']} on you! All stats reduced by {amount}.|n")
        from evennia.utils import delay
        delay(duration, self._remove_debuff_all, target, amount)
        return True, f"Cursed {target.key}: all stats -{amount}."

    def _remove_debuff_all(self, target, amount):
        stats = target.attributes.get("stats", {})
        for s in ["str", "dex", "con", "int", "wis", "cha"]:
            stats[s] = stats.get(s, 10) + amount
        target.attributes.add("stats", stats)
        target.msg("|mYour curse lifts. All stats return to normal.|n")

    def _apply_stun(self, spell, target, duration, caller):
        if not target:
            return False, "You need a target for that spell."

        # Phase 1.2: Saving throw check
        if spell.get("save_negates", False):
            if self._check_saving_throw(spell, target):
                return True, f"{target.key} resists {spell['name']}!"

        # Phase 1.2: Use status_effects system for stun tracking
        try:
            from world.status_effects import create_stun_effect, apply_status_effect
            from world.saving_throws import calculate_dc
            dc = calculate_dc(self.level, self.casting_stat, spell["level"])
            effect = create_stun_effect(
                duration=duration, source=self.character,
                source_level=self.level, source_stat=self.casting_stat,
                save_dc=dc, break_on_damage=True, break_chance=0.0
            )
            applied, msg = apply_status_effect(target, effect)
            if applied:
                caller.msg(f"|mYou cast {spell['name']} on {target.key}, stunning them for {duration}s!|n")
                target.msg(f"|m{caller.key} casts {spell['name']} on you! You are stunned for {duration}s!|n")
                return True, f"Stunned {target.key} for {duration}s."
            else:
                caller.msg(f"|y{msg}|n")
                return False, msg
        except ImportError:
            # Fallback to old behavior
            target.attributes.add("stunned", True)
            caller.msg(f"|mYou cast {spell['name']} on {target.key}, stunning them for {duration}s!|n")
            target.msg(f"|m{caller.key} casts {spell['name']} on you! You are stunned for {duration}s!|n")
            from evennia.utils import delay
            delay(duration, self._remove_stun, target)
            return True, f"Stunned {target.key} for {duration}s."

    def _remove_stun(self, target):
        target.attributes.add("stunned", False)
        target.msg("|mYou shake off the stun effect.|n")

    def _apply_hot(self, spell, heal_per_tick, duration, caller):
        caller.msg(f"|gYou cast {spell['name']}, gaining {heal_per_tick} health every 5s for {duration}s.|n")
        caller.location.msg_contents(
            f"|g{caller.key} is surrounded by a healing aura.|n",
            exclude=[caller]
        )
        ticks = duration // 5
        from evennia.utils import delay
        for i in range(ticks):
            delay(5 * (i + 1), self._hot_tick, caller, heal_per_tick)
        return True, f"Regeneration aura active for {duration}s."

    def _hot_tick(self, caller, heal):
        max_hp = caller.attributes.get("max_hp", 100)
        hp = caller.attributes.get("hp", 0)
        healed = min(heal, max_hp - hp)
        caller.attributes.add("hp", hp + healed)
        caller.msg(f"|gYou regenerate {healed} HP.|n")

    # ======================== Phase 7: Buff Spells ========================

    def _apply_buff(self, spell, target, stat, amount, duration, caller):
        """Apply a stat-increasing buff to a target."""
        tgt = target or self.character

        # Use status_effects system for tracking
        try:
            from world.status_effects import StatusEffect, StatusEffectCategory, StatusEffectSlot, apply_status_effect
            from world.saving_throws import calculate_dc

            dc = calculate_dc(self.level, self.casting_stat, spell["level"])
            effect = StatusEffect(
                name=f"Enhanced {stat.upper()}",
                key=f"buff_{stat}",
                category=StatusEffectCategory.DEBUFF,
                slot=StatusEffectSlot.STAT_DEBUFF,
                duration=duration,
                remaining=duration,
                tick_interval=0,
                stat_affected=stat,
                stat_amount=-amount,  # Negative amount = increase (we invert in undo)
                source=self.character,
                source_level=self.level,
                source_stat=self.casting_stat,
                save_dc=dc,
                icon="|b[BUFF]|n",
            )
            # Override the undo to add instead of subtract
            original_undo = effect._undo_debuff if hasattr(effect, '_undo_debuff') else None
            applied, msg = apply_status_effect(tgt, effect)
        except ImportError:
            applied = True
            msg = ""

        # Direct stat modification
        stats = tgt.attributes.get("stats", {})
        original = stats.get(stat, 10)
        stats[stat] = original + amount
        tgt.attributes.add("stats", stats)

        caller.msg(f"|bYou cast {spell['name']} on {tgt.key}, increasing {stat.upper()} by {amount} for {duration}s.|n")
        if tgt != caller:
            tgt.msg(f"|b{caller.key} casts {spell['name']} on you! Your {stat.upper()} increases by {amount}.|n")

        from evennia.utils import delay
        delay(duration, self._remove_buff, tgt, stat, amount)
        return True, f"Buffed {tgt.key}: +{amount} {stat.upper()}."

    def _remove_buff(self, target, stat, amount):
        stats = target.attributes.get("stats", {})
        stats[stat] = max(1, stats.get(stat, 10) - amount)
        target.attributes.add("stats", stats)
        target.msg(f"|bYour {stat.upper()} buff fades.|n")

    def _apply_buff_all(self, spell, target, amount, duration, caller):
        """Apply a buff to all stats."""
        tgt = target or self.character
        stats = tgt.attributes.get("stats", {})
        for s in ["str", "dex", "con", "int", "wis", "cha"]:
            stats[s] = stats.get(s, 10) + amount
        tgt.attributes.add("stats", stats)

        caller.msg(f"|bYou cast {spell['name']}, increasing all stats by {amount} for {duration}s!|n")
        if tgt != caller:
            tgt.msg(f"|b{caller.key} casts {spell['name']} on you! All stats increased by {amount}.|n")

        from evennia.utils import delay
        delay(duration, self._remove_buff_all, tgt, amount)
        return True, f"Buffed {tgt.key}: all stats +{amount}."

    def _remove_buff_all(self, target, amount):
        stats = target.attributes.get("stats", {})
        for s in ["str", "dex", "con", "int", "wis", "cha"]:
            stats[s] = max(1, stats.get(s, 10) - amount)
        target.attributes.add("stats", stats)
        target.msg("|bYour avatar buff fades. All stats return to normal.|n")

    # ======================== Phase 7: DoT Spells ========================

    def _apply_dot(self, spell, target, dot_type, dmg_per_tick, duration, caller):
        """Apply a Damage-over-Time effect using the status_effects system."""
        if not target:
            return False, "You need a target for that spell."

        # Saving throw check
        if spell.get("save_negates", False):
            if self._check_saving_throw(spell, target):
                return True, f"{target.key} resists {spell['name']}!"

        try:
            from world.status_effects import (
                create_bleed_effect, create_poison_effect, create_burn_effect,
                create_curse_effect, apply_status_effect
            )
            from world.saving_throws import calculate_dc

            dc = calculate_dc(self.level, self.casting_stat, spell["level"])
            tick_interval = 3.0

            dot_factory = {
                "bleed": create_bleed_effect,
                "poison": create_poison_effect,
                "burn": create_burn_effect,
                "curse": create_curse_effect,
            }

            factory = dot_factory.get(dot_type)
            if not factory:
                return False, f"Unknown DoT type: {dot_type}"

            effect = factory(
                damage=dmg_per_tick,
                duration=duration,
                tick_interval=tick_interval,
                source=self.character,
                source_level=self.level,
                source_stat=self.casting_stat,
                save_dc=dc,
            )

            applied, msg = apply_status_effect(target, effect)
            if applied:
                dot_names = {"bleed": "Bleeding", "poison": "Poisoned", "burn": "Burning", "curse": "Cursed"}
                dot_name = dot_names.get(dot_type, dot_type.title())
                caller.msg(f"|rYou cast {spell['name']} on {target.key}, inflicting {dot_name} for {dmg_per_tick}/tick over {duration}s.|n")
                target.msg(f"|r{caller.key} casts {spell['name']} on you! You are {dot_name}!|n")
                return True, f"Inflicted {dot_name} on {target.key}."
            else:
                caller.msg(f"|y{msg}|n")
                return False, msg

        except ImportError:
            # Fallback: simple DoT using delay
            caller.msg(f"|rYou cast {spell['name']} on {target.key}, inflicting {dmg_per_tick} damage every 3s for {duration}s.|n")
            target.msg(f"|r{caller.key} casts {spell['name']} on you!|n")
            ticks = duration // 3
            from evennia.utils import delay
            for i in range(ticks):
                delay(3 * (i + 1), self._dot_tick, target, dmg_per_tick, dot_type)
            return True, f"Inflicted DoT on {target.key}."

    def _dot_tick(self, target, dmg, dot_type):
        """Fallback DoT tick handler."""
        hp = target.attributes.get("hp", 0)
        actual = min(dmg, hp)
        target.attributes.add("hp", max(0, hp - actual))
        target.msg(f"|rYou take {actual} {dot_type} damage.|n")

    # ======================== Phase 7: Spell Resistance Buff ========================

    def _apply_spell_resist_buff(self, spell, amount, duration, caller):
        """Apply a temporary spell resistance buff."""
        current = caller.attributes.get("spell_resist_buff", 0)
        caller.attributes.add("spell_resist_buff", current + amount)
        caller.msg(f"|bYou cast {spell['name']}, gaining +{amount}% spell resistance for {duration}s.|n")
        caller.location.msg_contents(
            f"|b{caller.key} is warded against magic.|n",
            exclude=[caller]
        )
        from evennia.utils import delay
        delay(duration, self._remove_spell_resist_buff, caller, amount)
        return True, f"Spell resistance +{amount}% for {duration}s."

    def _remove_spell_resist_buff(self, caller, amount):
        current = caller.attributes.get("spell_resist_buff", 0)
        caller.attributes.add("spell_resist_buff", max(0, current - amount))
        caller.msg("|bYour magic resistance ward fades.|n")

    # ======================== Phase 7: Restore Mana ========================

    def _apply_restore_mana(self, spell, amount, caller):
        """Restore mana to the caster."""
        max_mana = caller.attributes.get("max_mana", 100)
        current_mana = caller.attributes.get("mana", 0)
        restored = min(amount, max_mana - current_mana)
        caller.attributes.add("mana", current_mana + restored)
        caller.msg(f"|bYou cast {spell['name']}, restoring {restored} mana.|n")
        caller.location.msg_contents(
            f"|b{caller.key} meditates and regains mana.|n",
            exclude=[caller]
        )
        return True, f"Restored {restored} mana."


# ---------------------------------------------------------------------------
# DISPLAY HELPERS
# ---------------------------------------------------------------------------

def format_spellbook(character):
    """Return an EvTable string of available spells."""
    level = character.attributes.get("level", 1)
    spells = get_spells_for_level(level)
    mana = character.attributes.get("mana", 0)
    max_mana = character.attributes.get("max_mana", 0)

    if not spells:
        return "|yYou have not learned any spells yet.|n"

    table = evtable.EvTable(
        "|wLvl|n", "|wSpell|n", "|wSchool|n", "|wMana|n", "|wCD|n", "|wCast|n",
        table=[], border="header", header_line_char="~",
        width=85
    )
    for s in spells:
        cost = _resolve_mana_cost(s, level)
        cd = f"{s['cooldown']}s" if s["cooldown"] > 0 else "—"
        cast_t = f"{s.get('cast_time', 0)}s" if s.get("cast_time", 0) > 0 else "—"
        table.add_row(
            str(s["level"]),
            s["name"],
            SCHOOL_DISPLAY.get(s["school"], s["school"]),
            str(cost),
            cd,
            cast_t,
        )
    out = f"|wSpellbook [Mana: {mana}/{max_mana}] — Level {level}|n\n{table}"
    return out


def format_spell_detail(spell_key):
    """Return a detailed description of a single spell."""
    spell = get_spell(spell_key)
    if not spell:
        return "No such spell."
    eff = spell["effect"]
    etype = eff.get("type", "unknown")
    details = []
    if etype == "damage":
        details.append(f"  Damage: {eff['base']} + {eff['per_level']}/level")
        if eff.get("damage_type"):
            from world.damage_types import DAMAGE_TYPE_DISPLAY
            dt = DAMAGE_TYPE_DISPLAY.get(eff["damage_type"], eff["damage_type"])
            details.append(f"  Type: {dt}")
    elif etype == "heal":
        details.append(f"  Healing: {eff['base']} + {eff['per_level']}/level")
    elif etype == "shield":
        details.append(f"  Absorption: {eff['base']} + {eff['per_level']}/level")
        details.append(f"  Duration: {eff.get('duration', '?')}s")
    elif etype == "debuff":
        details.append(f"  Reduces {eff.get('stat', '?').upper()} by {eff.get('amount', '?')}")
        details.append(f"  Duration: {eff.get('duration', '?')}s")
    elif etype == "debuff_all":
        details.append(f"  Reduces all stats by {eff.get('amount', '?')}")
        details.append(f"  Duration: {eff.get('duration', '?')}s")
    elif etype == "stun":
        details.append(f"  Stuns target for {eff.get('duration', '?')}s")
    elif etype == "lifesteal":
        details.append(f"  Damage: {eff['base']} + {eff['per_level']}/level")
        details.append(f"  Heals caster for {int(eff.get('heal_pct', 0.5) * 100)}% of damage dealt")
    elif etype == "heal_over_time":
        details.append(f"  Healing: {eff['base']} + {eff['per_level']}/level over {eff.get('duration', '?')}s")
    elif etype == "buff":
        details.append(f"  Increases {eff.get('stat', '?').upper()} by {eff.get('amount', '?')}")
        details.append(f"  Duration: {eff.get('duration', '?')}s")
    elif etype == "buff_all":
        details.append(f"  Increases all stats by {eff.get('amount', '?')}")
        details.append(f"  Duration: {eff.get('duration', '?')}s")
    elif etype == "dot":
        dot_names = {"bleed": "Bleeding", "poison": "Poison", "burn": "Burning", "curse": "Curse"}
        dot_name = dot_names.get(eff.get("dot_type", "?"), eff.get("dot_type", "?"))
        details.append(f"  Inflicts {dot_name}: {eff['base']} + {eff['per_level']}/level per tick")
        details.append(f"  Duration: {eff.get('duration', '?')}s")
    elif etype == "spell_resist_buff":
        details.append(f"  Spell Resistance: +{eff.get('amount', '?')}%")
        details.append(f"  Duration: {eff.get('duration', '?')}s")
    elif etype == "restore_mana":
        details.append(f"  Mana Restored: {eff['base']} + {eff['per_level']}/level")

    # Cast time
    cast_time = spell.get("cast_time", 0)
    if cast_time > 0:
        details.append(f"  Cast Time: {cast_time}s (channeled)")

    # Phase 1.2: Show saving throw info
    save_type = spell.get("save_type", "spell")
    save_negates = spell.get("save_negates", False)
    if save_type and etype in ("damage", "debuff", "debuff_all", "stun", "lifesteal", "dot"):
        from world.saving_throws import SAVING_THROW_DISPLAY, SavingThrow
        save_map = {
            "poison": SavingThrow.POISON,
            "death": SavingThrow.DEATH,
            "petrification": SavingThrow.PETRIFICATION,
            "rod": SavingThrow.ROD,
            "spell": SavingThrow.SPELL,
        }
        st = save_map.get(save_type, SavingThrow.SPELL)
        sv_display = SAVING_THROW_DISPLAY.get(st, save_type)
        if save_negates:
            details.append(f"  Save: {sv_display} negates")
        else:
            details.append(f"  Save: {sv_display} for half")

    return (
        f"|w{spell['name']}|n (Level {spell['level']})\n"
        f"  School: {SCHOOL_DISPLAY.get(spell['school'], spell['school'])}\n"
        f"  Cost: {spell['mana_base']} + {spell['mana_per_lvl']}/level MP\n"
        f"  Cooldown: {spell['cooldown']}s\n"
        + "\n".join(details) +
        f"\n\n  {spell['description']}"
    )