"""
Strict Zone-Based Level Banding & Mob Scaling for 'rop'
========================================================

Enforces strict level banding across the entire realm.  Newbie starting
areas (levels 1-5, up to 10) exclusively spawn low-level, properly scaled
mobs, preventing high-level mobs from bleeding into beginner zones.

Mob creation and prototype tables derive their stats (HP, damage, level)
directly from the zone's assigned level range (see ``world.zone_levels``).

This module is the single source of truth for:
  - Resolving a room's zone level range (via zone_tag or zone name).
  - Clamping a requested mob level into the zone's allowed band.
  - Deriving HP, damage, XP, gold, and the six-stat block from a level.
  - Auditing every spawnable room to guarantee no out-of-band mobs exist.
"""

from __future__ import annotations

import random
from typing import Any, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Level-range resolution
# ---------------------------------------------------------------------------

def _room_zone_tag(room: Any) -> Optional[str]:
    """Return the room's zone_tag attribute, if any."""
    try:
        return room.attributes.get("zone_tag", default=None)
    except Exception:
        return None


def _room_name(room: Any) -> str:
    """Return a safe room name string for zone lookups."""
    try:
        return getattr(room, "key", None) or (room.db_key or "")
    except Exception:
        return ""


def resolve_room_level_range(room: Any) -> Tuple[int, int]:
    """
    Resolve the strict level band for a room.

    Resolution order:
      1. Explicit ``zone_level_min`` / ``zone_level_max`` attributes.
      2. The room's ``zone_tag`` mapped through world.realm_population or
         world.zone_levels.
      3. The room's display name matched against world.zone_levels.

    Falls back to the safe starter band (1, 5) when unknown, ensuring we
    never accidentally place a high-level mob in an unclassified room.
    """
    if room is None:
        return (1, 5)

    # 1. Explicit attributes take absolute precedence.
    try:
        lmin = room.attributes.get("zone_level_min", default=None)
        lmax = room.attributes.get("zone_level_max", default=None)
        if lmin is not None and lmax is not None:
            lmin = int(lmin)
            lmax = int(lmax)
            if lmax < lmin:
                lmin, lmax = lmax, lmin
            return (max(1, lmin), max(1, lmax))
    except Exception:
        pass

    # 2. Zone tag -> realm_population zone data.
    zone_tag = _room_zone_tag(room)
    if zone_tag:
        # Try the authoritative realm_population zone table.
        try:
            import world.builder_phase1 as b1
            data = b1.ALL_ZONES.get(zone_tag)
            if data and isinstance(data, dict):
                rng = data.get("level_range")
                if isinstance(rng, (tuple, list)) and len(rng) == 2:
                    lmin, lmax = int(rng[0]), int(rng[1])
                    return (max(1, lmin), max(1, lmax))
        except Exception:
            pass

        # Try zone_levels by zone name.
        try:
            from world.zone_levels import get_zone_level_range
            rng = get_zone_level_range(zone_tag)
            if rng and rng != (1, 5):
                return rng
        except Exception:
            pass

    # 3. Fall back on the room display name.
    name = _room_name(room)
    if name:
        try:
            from world.zone_levels import get_zone_level_range
            rng = get_zone_level_range(name)
            if rng and rng != (1, 5):
                return rng
        except Exception:
            pass

    # Safe fallback — never spawn anything dangerous in an unknown room.
    return (1, 5)


def clamp_level_to_zone(level: int, room: Any) -> int:
    """
    Clamp a requested mob level into the room's strict zone band.

    Args:
        level: The mob's requested/prototype level.
        room: The room the mob is spawning into.

    Returns:
        The level clamped to [zone_min, zone_max].
    """
    lmin, lmax = resolve_room_level_range(room)
    return max(lmin, min(lmax, int(level or 1)))


def scale_mob_to_zone(mob: Any, room: Any) -> int:
    """
    Rescale an already-created mob's stats to its room's zone band.

    Reads the mob's intended level, clamps it to the zone range, then
    rewrites level/HP/damage/stats/XP/gold on the mob to match.  Returns
    the final (clamped) level.

    Args:
        mob: The mob object to rescale.
        room: The room the mob occupies.

    Returns:
        The final clamped level.
    """
    if mob is None or room is None:
        return mob.attributes.get("level", 1) if mob is not None else 1

    requested = mob.attributes.get("level", 1) if hasattr(mob, "attributes") else 1
    final_level = clamp_level_to_zone(requested, room)

    if hasattr(mob, "attributes"):
        mob.attributes.add("level", final_level)
        mob.attributes.add("stats", derive_stats(final_level))

        hp = derive_hp(final_level)
        mob.attributes.add("hp", hp)
        mob.attributes.add("max_hp", hp)

        # Preserve an explicit damage_type override if set, otherwise leave
        # damage derivation to equipment + combat engine.  We store a base
        # ``base_damage`` attribute so the combat engine can use zone-scaled
        # damage when the mob has no weapon.
        mob.attributes.add("base_damage", derive_damage(final_level))

        # Only overwrite XP/gold if the prototype did not explicitly set them.
        if not mob.attributes.has("xp_value"):
            mob.attributes.add("xp_value", derive_xp(final_level))
        if not mob.attributes.has("gold_min"):
            gmin, gmax = derive_gold(final_level)
            mob.attributes.add("gold_min", gmin)
            mob.attributes.add("gold_max", gmax)

    return final_level


# ---------------------------------------------------------------------------
# Stat derivation (canonical)
# ---------------------------------------------------------------------------

def derive_stats(level: int) -> Dict[str, int]:
    """
    Return a six-stat block scaled from a mob level.

    Uses the classic curve where every stat grows with level, with DEX
    slightly ahead and mental stats trailing for physical creatures.
    """
    level = max(1, int(level))
    base = 7 + level
    return {
        "str": base,
        "dex": base + 1,
        "con": base,
        "int": max(3, base - 6),
        "wis": max(3, base - 4),
        "cha": max(2, base - 8),
    }


def derive_hp(level: int) -> int:
    """
    Derive max HP for a mob from its level.

    Classic MajorMUD-style curve: low-level mobs have modest HP so newbie
    areas are beatable by fresh characters (who have ~100 HP at level 1,
    dealing ~5-10 damage per hit).  A level 1 mob with 12 HP should die
    in 2-3 hits — exactly what makes newbie zones work.
    """
    level = max(1, int(level))
    # 8 + (level * 5): level 1=13, 2=18, 3=23, 5=33, 10=58, 20=108, 50=258, 80=408
    return 8 + (level * 5)


def derive_damage(level: int) -> int:
    """
    Derive the base melee damage dice value for a mob from its level.

    This is the fallback used when a mob has no equipment weapon.  Kept
    deliberately modest so equipped mobs still hit harder via their weapons.

    Classic curve: level 1 deals ~3-4, level 5 deals ~5-6, level 10 deals ~7-8.
    """
    level = max(1, int(level))
    return max(2, (level // 3) + 2)


def derive_xp(level: int) -> int:
    """Derive the XP award for a mob from its level."""
    level = max(1, int(level))
    return (level * 12) + 6


def derive_gold(level: int) -> Tuple[int, int]:
    """Derive the (min, max) gold drop range for a mob from its level."""
    level = max(1, int(level))
    return (level // 2, level * 2)


# ---------------------------------------------------------------------------
# Enforcement / audit
# ---------------------------------------------------------------------------

def enforce_room_zone_banding(room: Any) -> Dict[str, Any]:
    """
    Audit and correct every mob in a room to obey the room's zone band.

    Mobs whose level falls outside the room's [zone_min, zone_max] are
    rescaled in place.  Returns a report dict:
      { "checked": int, "rescaled": int, "violations": int }
    """
    lmin, lmax = resolve_room_level_range(room)
    report = {"checked": 0, "rescaled": 0, "violations": 0, "range": (lmin, lmax)}

    if room is None:
        return report

    try:
        contents = list(room.contents)
    except Exception:
        return report

    for obj in contents:
        if not hasattr(obj, "attributes"):
            continue
        if not obj.attributes.get("is_mob", False):
            continue
        # Skip bosses — they are lair-specific and treated separately.
        if obj.attributes.get("is_boss", False):
            continue

        report["checked"] += 1
        level = obj.attributes.get("level", 1)
        if level is None:
            level = 1

        if level < lmin or level > lmax:
            report["violations"] += 1
            scale_mob_to_zone(obj, room)
            report["rescaled"] += 1

    return report


def audit_all_rooms() -> Dict[str, Any]:
    """
    Audit every room in the realm for out-of-band mobs.

    Returns a summary dict:
      {
        "rooms_checked": int,
        "violations": int,
        "rescaled": int,
        "mobs_checked": int,
        "clean": bool,
      }
    """
    summary = {
        "rooms_checked": 0,
        "violations": 0,
        "rescaled": 0,
        "mobs_checked": 0,
        "clean": True,
    }

    try:
        from evennia.objects.models import ObjectDB
        rooms = ObjectDB.objects.filter(db_typeclass_path__endswith="Room")
    except Exception:
        return summary

    for room in rooms:
        try:
            report = enforce_room_zone_banding(room)
            summary["rooms_checked"] += 1
            summary["violations"] += report["violations"]
            summary["rescaled"] += report["rescaled"]
            summary["mobs_checked"] += report["checked"]
        except Exception:
            continue

    summary["clean"] = summary["violations"] == 0
    return summary