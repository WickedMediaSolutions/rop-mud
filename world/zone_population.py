"""
Zone Population Density Auditor & Auto-Balancer for 'rop'
==========================================================

Audits every room in the realm against expected mob counts from
world.builder_phase1.ALL_ZONES and enforces minimum population
density thresholds.  Provides:

  - ``audit_zone_density()``  — per-zone density report
  - ``enforce_minimum_density()`` — auto-spawns mobs in underpopulated rooms
  - ``balance_zone(zone_key)``  — target a single zone for rebalancing
  - ``zone_density_report()``  — human-readable summary

Population rules:
  - Every non-safe, non-boss, non-town room must have at least 1 mob.
  - Town/hub rooms must have at least 1 NPC (guard/vendor/etc).
  - Rooms with spawn_tables get their own population logic; this tool
    only fills rooms that are completely barren.
  - Level ranges from world.zone_scaling are respected when spawning
    filler mobs.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

try:
    from evennia.objects.models import ObjectDB
    from evennia.utils.ansi import strip_ansi
except Exception:
    ObjectDB = None
    strip_ansi = lambda x: str(x or "")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_MOBS_PER_HOSTILE_ROOM = 1
MIN_NPCS_PER_TOWN_ROOM = 1
DENSITY_LEVELS = {
    "desolate": (0, 0),
    "sparse": (1, 2),
    "normal": (2, 4),
    "dense": (3, 6),
    "swarming": (5, 10),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_room(obj: Any) -> bool:
    """Return True if obj is a Room typeclass instance."""
    try:
        return obj.is_typeclass("typeclasses.rooms.Room")
    except Exception:
        return False


def _is_mob(obj: Any) -> bool:
    """Return True if obj is a living realm mob."""
    try:
        if not hasattr(obj, "attributes"):
            return False
        if obj.attributes.get("is_mob", default=False):
            return obj.attributes.get("hp", 0) > 0
        if obj.attributes.get("is_aggro") is not None:
            return True
        if obj.tags.has("realm_mob", category="spawn"):
            return True
    except Exception:
        pass
    return False


def _is_npc(obj: Any) -> bool:
    """Return True if obj is a service NPC (vendor, guard, etc)."""
    try:
        if not hasattr(obj, "attributes"):
            return False
        return (
            obj.attributes.get("is_vendor", False)
            or obj.attributes.get("is_trainer", False)
            or obj.attributes.get("is_npc", False)
        )
    except Exception:
        return False


def _is_safe_zone(room: Any) -> bool:
    """Return True if room is a safe zone (town, hub, sanctuary)."""
    try:
        return bool(room.attributes.get("safe_zone", False))
    except Exception:
        return False


def _is_town_room(room: Any) -> bool:
    """Return True if room is in a town/hub."""
    try:
        if _is_safe_zone(room):
            return True
        zone_tag = room.attributes.get("zone_tag", default=None)
        if zone_tag and isinstance(zone_tag, str):
            town_zones = {"aethelgard_town", "gorgoroth_town", "sunspire_meadows",
                          "brimstone_courtyard", "town"}
            return zone_tag.lower() in town_zones
    except Exception:
        pass
    return False


def _is_boss_room(room: Any) -> bool:
    """Return True if room contains a boss or is a boss lair."""
    try:
        for obj in room.contents:
            if hasattr(obj, "attributes"):
                if obj.attributes.get("is_boss") or obj.attributes.get("boss_id"):
                    return True
    except Exception:
        pass
    return False


def _has_spawn_table(room: Any) -> bool:
    """Return True if room has a defined spawn_table."""
    try:
        tbl = room.attributes.get("spawn_table", default=[])
        return bool(tbl)
    except Exception:
        return False


def _room_zone_levels(room: Any) -> Tuple[int, int]:
    """Get level range for a room via zone_scaling."""
    try:
        from world.zone_scaling import resolve_room_level_range
        return resolve_room_level_range(room)
    except Exception:
        return (1, 5)


def _count_mobs(room: Any) -> int:
    """Count alive mobs in a room."""
    count = 0
    try:
        for obj in room.contents:
            if _is_mob(obj):
                count += 1
    except Exception:
        pass
    return count


def _count_npcs(room: Any) -> int:
    """Count service NPCs in a room."""
    count = 0
    try:
        for obj in room.contents:
            if _is_npc(obj):
                count += 1
    except Exception:
        pass
    return count


# ---------------------------------------------------------------------------
# Density Audit
# ---------------------------------------------------------------------------

def audit_zone_density() -> Dict[str, Any]:
    """
    Audit every room in the realm for population density.

    Returns:
      {
        "rooms_total": int,
        "rooms_populated": int,
        "rooms_barren": int,
        "rooms_overpopulated": int,
        "town_rooms_without_npcs": int,
        "per_zone": {zone_key: {...}},
        "issues": [{room, zone, mobs, expected, issue}, ...],
      }
    """
    summary: Dict[str, Any] = {
        "rooms_total": 0,
        "rooms_populated": 0,
        "rooms_barren": 0,
        "rooms_overpopulated": 0,
        "town_rooms_without_npcs": 0,
        "per_zone": {},
        "issues": [],
    }

    per_zone: Dict[str, Dict[str, Any]] = {}

    try:
        rooms = ObjectDB.objects.filter(db_typeclass_path__endswith="Room")
    except Exception:
        return summary

    for room in rooms:
        summary["rooms_total"] += 1

        zone_tag = room.attributes.get("zone_tag", default="unknown") or "unknown"
        if zone_tag not in per_zone:
            per_zone[zone_tag] = {"total": 0, "populated": 0, "barren": 0,
                                  "overpopulated": 0, "mobs": 0, "npcs": 0}
        per_zone[zone_tag]["total"] += 1

        mob_count = _count_mobs(room)
        npc_count = _count_npcs(room)
        per_zone[zone_tag]["mobs"] += mob_count
        per_zone[zone_tag]["npcs"] += npc_count

        is_barren = mob_count == 0
        is_over = mob_count > 10

        # Boss rooms and safe zones skip density checks
        if _is_boss_room(room):
            per_zone[zone_tag]["populated"] += 1
            summary["rooms_populated"] += 1
            continue

        if _is_town_room(room) and _is_safe_zone(room):
            per_zone[zone_tag]["populated"] += 1
            summary["rooms_populated"] += 1
            if npc_count < MIN_NPCS_PER_TOWN_ROOM:
                summary["town_rooms_without_npcs"] += 1
            continue

        if _has_spawn_table(room):
            per_zone[zone_tag]["populated"] += 1
            summary["rooms_populated"] += 1
            continue

        if is_barren:
            per_zone[zone_tag]["barren"] += 1
            summary["rooms_barren"] += 1
            summary["issues"].append({
                "room_key": room.key,
                "zone": zone_tag,
                "mobs": 0,
                "expected_min": MIN_MOBS_PER_HOSTILE_ROOM,
                "issue": "barren",
            })
        elif is_over:
            per_zone[zone_tag]["overpopulated"] += 1
            summary["rooms_overpopulated"] += 1
            summary["issues"].append({
                "room_key": room.key,
                "zone": zone_tag,
                "mobs": mob_count,
                "expected_max": 10,
                "issue": "overpopulated",
            })
        else:
            per_zone[zone_tag]["populated"] += 1
            summary["rooms_populated"] += 1

    summary["per_zone"] = per_zone
    return summary


# ---------------------------------------------------------------------------
# Filler Mob Spawning
# ---------------------------------------------------------------------------

_FILLER_MOB_NAMES = {
    # Level 1-5: newbie wildlife
    1: ["Wild Boar", "Giant Rat", "Young Wolf", "Goblin Scout", "Forest Snake",
        "Crazed Squirrel", "Mud Crab", "Stray Dog", "Bandit Novice", "Kobold"],
    # Level 6-15: tougher creatures
    2: ["Wolf", "Goblin Warrior", "Skeleton", "Zombie", "Giant Bat",
        "Hobgoblin", "Bandit", "Cave Spider", "Orc Grunt", "Ghoul"],
    # Level 16-40: mid-game
    3: ["Dire Wolf", "Orc Warrior", "Wraith", "Troll", "Giant Scorpion",
        "Ogre", "Wyvern Hatchling", "Shadow Beast", "Gargoyle", "Hill Giant"],
    # Level 41-60: dangerous
    4: ["Fire Elemental", "Stone Golem", "Drake", "Basilisk", "Minotaur",
        "Wyvern", "Manticore", "Spectre", "Chimera", "Hellhound"],
    # Level 61-80: end-game
    5: ["Ancient Dragon", "Lich", "Demon Lord", "Beholder", "Death Knight",
        "Phoenix", "Dread Wraith", "Pit Fiend", "Elder Elemental", "Kraken Spawn"],
}

_FILLER_MOB_PROTOTYPES = {
    "Wild Boar": {"level": 1, "faction": "Neutral", "aggro": True},
    "Giant Rat": {"level": 1, "faction": "Neutral", "aggro": True},
    "Young Wolf": {"level": 2, "faction": "Neutral", "aggro": True},
    "Goblin Scout": {"level": 3, "faction": "Gorgoroth Horde", "aggro": True},
    "Forest Snake": {"level": 1, "faction": "Neutral", "aggro": False},
    "Crazed Squirrel": {"level": 1, "faction": "Neutral", "aggro": True},
    "Mud Crab": {"level": 1, "faction": "Neutral", "aggro": False},
    "Stray Dog": {"level": 2, "faction": "Neutral", "aggro": False},
    "Bandit Novice": {"level": 4, "faction": "Neutral", "aggro": True},
    "Kobold": {"level": 2, "faction": "Gorgoroth Horde", "aggro": True},
    "Wolf": {"level": 7, "faction": "Neutral", "aggro": True},
    "Goblin Warrior": {"level": 8, "faction": "Gorgoroth Horde", "aggro": True},
    "Skeleton": {"level": 6, "faction": "Neutral", "aggro": True},
    "Zombie": {"level": 6, "faction": "Neutral", "aggro": True},
    "Giant Bat": {"level": 9, "faction": "Neutral", "aggro": True},
    "Hobgoblin": {"level": 10, "faction": "Gorgoroth Horde", "aggro": True},
    "Bandit": {"level": 11, "faction": "Neutral", "aggro": True},
    "Cave Spider": {"level": 12, "faction": "Neutral", "aggro": True},
    "Orc Grunt": {"level": 13, "faction": "Gorgoroth Horde", "aggro": True},
    "Ghoul": {"level": 14, "faction": "Neutral", "aggro": True},
    "Dire Wolf": {"level": 20, "faction": "Neutral", "aggro": True},
    "Orc Warrior": {"level": 24, "faction": "Gorgoroth Horde", "aggro": True},
    "Wraith": {"level": 28, "faction": "Neutral", "aggro": True},
    "Troll": {"level": 30, "faction": "Gorgoroth Horde", "aggro": True},
    "Giant Scorpion": {"level": 22, "faction": "Neutral", "aggro": True},
    "Ogre": {"level": 32, "faction": "Gorgoroth Horde", "aggro": True},
    "Wyvern Hatchling": {"level": 35, "faction": "Neutral", "aggro": True},
    "Shadow Beast": {"level": 38, "faction": "Neutral", "aggro": True},
    "Gargoyle": {"level": 36, "faction": "Neutral", "aggro": True},
    "Hill Giant": {"level": 40, "faction": "Gorgoroth Horde", "aggro": True},
    "Fire Elemental": {"level": 45, "faction": "Neutral", "aggro": True},
    "Stone Golem": {"level": 43, "faction": "Neutral", "aggro": False},
    "Drake": {"level": 48, "faction": "Neutral", "aggro": True},
    "Basilisk": {"level": 50, "faction": "Neutral", "aggro": True},
    "Minotaur": {"level": 52, "faction": "Neutral", "aggro": True},
    "Wyvern": {"level": 55, "faction": "Neutral", "aggro": True},
    "Manticore": {"level": 56, "faction": "Neutral", "aggro": True},
    "Spectre": {"level": 58, "faction": "Neutral", "aggro": True},
    "Chimera": {"level": 59, "faction": "Neutral", "aggro": True},
    "Hellhound": {"level": 60, "faction": "Gorgoroth Horde", "aggro": True},
    "Ancient Dragon": {"level": 68, "faction": "Neutral", "aggro": True},
    "Lich": {"level": 72, "faction": "Gorgoroth Horde", "aggro": True},
    "Demon Lord": {"level": 75, "faction": "Gorgoroth Horde", "aggro": True},
    "Beholder": {"level": 70, "faction": "Neutral", "aggro": True},
    "Death Knight": {"level": 74, "faction": "Gorgoroth Horde", "aggro": True},
    "Phoenix": {"level": 78, "faction": "Aethelgard Alliance", "aggro": False},
    "Dread Wraith": {"level": 76, "faction": "Gorgoroth Horde", "aggro": True},
    "Pit Fiend": {"level": 79, "faction": "Gorgoroth Horde", "aggro": True},
    "Elder Elemental": {"level": 77, "faction": "Neutral", "aggro": False},
    "Kraken Spawn": {"level": 80, "faction": "Neutral", "aggro": True},
}


def _pick_filler_mob(room: Any) -> Optional[Dict[str, Any]]:
    """Pick a filler mob appropriate for the room's level range."""
    lmin, lmax = _room_zone_levels(room)
    mid = (lmin + lmax) // 2

    if mid <= 5:
        tier = 1
    elif mid <= 15:
        tier = 2
    elif mid <= 40:
        tier = 3
    elif mid <= 60:
        tier = 4
    else:
        tier = 5

    names = _FILLER_MOB_NAMES.get(tier, _FILLER_MOB_NAMES[1])
    name = random.choice(names)
    proto = _FILLER_MOB_PROTOTYPES.get(name)

    if proto is None:
        return None

    # Determine faction based on zone
    try:
        zone_tag = room.attributes.get("zone_tag", default="")
        import world.builder_phase1 as b1
        if zone_tag in b1.GOOD_ZONES:
            faction = "Aethelgard Alliance"
        elif zone_tag in b1.EVIL_ZONES:
            faction = "Gorgoroth Horde"
        else:
            faction = proto.get("faction", "Neutral")
    except Exception:
        faction = proto.get("faction", "Neutral")

    level = max(lmin, min(lmax, proto["level"]))

    return {
        "name": name,
        "level": level,
        "faction": faction,
        "aggro": proto.get("aggro", True),
    }


def _spawn_filler_mob(room: Any, spawn_data: Dict[str, Any]) -> bool:
    """Spawn a single filler mob in the given room. Returns True on success."""
    try:
        from world.mob_ai import spawn_mob
        from world.zone_scaling import scale_mob_to_zone

        mob = spawn_mob(
            room,
            name=spawn_data["name"],
            level=spawn_data["level"],
            faction=spawn_data["faction"],
            aggro=spawn_data["aggro"],
        )
        if mob:
            scale_mob_to_zone(mob, room)
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------

def enforce_minimum_density(room_limit: int = 50) -> Dict[str, Any]:
    """
    Auto-populate barren rooms with level-appropriate filler mobs.

    Args:
        room_limit: Maximum number of rooms to fill in one pass (safety cap).

    Returns:
        {"filled": int, "failed": int, "skipped": int, "details": [...]}
    """
    result = {"filled": 0, "failed": 0, "skipped": 0, "details": []}

    try:
        rooms = ObjectDB.objects.filter(db_typeclass_path__endswith="Room")
    except Exception:
        return result

    count = 0
    for room in rooms:
        if count >= room_limit:
            break

        if _is_boss_room(room):
            continue
        if _is_safe_zone(room) or _is_town_room(room):
            continue
        if _has_spawn_table(room):
            continue
        if _count_mobs(room) >= MIN_MOBS_PER_HOSTILE_ROOM:
            continue

        count += 1
        spawn_data = _pick_filler_mob(room)
        if spawn_data is None:
            result["skipped"] += 1
            result["details"].append({"room": room.key, "status": "skipped",
                                      "reason": "no suitable filler"})
            continue

        success = _spawn_filler_mob(room, spawn_data)
        if success:
            result["filled"] += 1
            result["details"].append({
                "room": room.key,
                "status": "filled",
                "mob": spawn_data["name"],
                "level": spawn_data["level"],
            })
        else:
            result["failed"] += 1
            result["details"].append({
                "room": room.key,
                "status": "failed",
                "reason": "spawn error",
            })

    return result


def balance_zone(zone_key: str) -> Dict[str, Any]:
    """
    Target a single zone for population balancing.

    Args:
        zone_key: The zone tag to balance (e.g., "emerald_forest").

    Returns:
        Same structure as enforce_minimum_density().
    """
    result = {"filled": 0, "failed": 0, "skipped": 0, "details": []}

    try:
        from evennia import search_tag
        rooms = list(search_tag(zone_key, category="zone"))
    except Exception:
        return result

    for room in rooms:
        if _is_boss_room(room):
            continue
        if _is_safe_zone(room) or _is_town_room(room):
            continue
        if _has_spawn_table(room):
            continue
        if _count_mobs(room) >= MIN_MOBS_PER_HOSTILE_ROOM:
            continue

        spawn_data = _pick_filler_mob(room)
        if spawn_data is None:
            result["skipped"] += 1
            continue

        success = _spawn_filler_mob(room, spawn_data)
        if success:
            result["filled"] += 1
            result["details"].append({
                "room": room.key,
                "status": "filled",
                "mob": spawn_data["name"],
                "level": spawn_data["level"],
            })
        else:
            result["failed"] += 1

    return result


def get_zone_density_summary(zone_key: str) -> Dict[str, Any]:
    """Get a detailed density summary for a single zone."""
    try:
        from evennia import search_tag
        rooms = list(search_tag(zone_key, category="zone"))
    except Exception:
        return {"zone": zone_key, "rooms": 0}

    total = len(rooms)
    populated = 0
    barren = 0
    total_mobs = 0

    for room in rooms:
        mc = _count_mobs(room)
        total_mobs += mc
        if mc > 0:
            populated += 1
        else:
            barren += 1

    return {
        "zone": zone_key,
        "rooms": total,
        "populated_rooms": populated,
        "barren_rooms": barren,
        "total_mobs": total_mobs,
        "density": (total_mobs / total) if total > 0 else 0,
    }


# ---------------------------------------------------------------------------
# Report Formatting
# ---------------------------------------------------------------------------

def zone_density_report() -> str:
    """Return a formatted ANSI report of zone population density."""
    audit = audit_zone_density()

    lines = []
    lines.append("|Y" + "=" * 65 + "|n")
    lines.append("|cZONE POPULATION DENSITY REPORT|n")
    lines.append("|Y" + "=" * 65 + "|n")
    lines.append("")
    lines.append(f"  |wTotal Rooms:    |n {audit['rooms_total']}")
    lines.append(f"  |wPopulated:      |n |g{audit['rooms_populated']}|n")
    lines.append(f"  |wBarren:         |n |r{audit['rooms_barren']}|n")
    lines.append(f"  |wOverpopulated:  |n |y{audit['rooms_overpopulated']}|n")
    lines.append(f"  |wTown issues:    |n |y{audit['town_rooms_without_npcs']}|n")
    lines.append("")

    per_zone = audit.get("per_zone", {})
    if per_zone:
        lines.append("  |wPer-Zone Breakdown:|n")
        lines.append(f"  {'Zone':<24} {'Total':>5} {'Pop':>5} {'Barren':>6} {'Mobs':>5} {'Density':>8}")
        lines.append(f"  {'-' * 53}")
        for zone_key in sorted(per_zone):
            z = per_zone[zone_key]
            density = (z["mobs"] / z["total"]) if z["total"] > 0 else 0
            density_label = (
                "|rDESOLATE|n" if density == 0
                else "|ySPARSE|n" if density < 1.0
                else "|gNORMAL|n" if density < 2.5
                else "|cDENSE|n" if density < 5.0
                else "|YSWARMING|n"
            )
            lines.append(f"  {zone_key:<24} {z['total']:>5} {z['populated']:>5} "
                         f"{z['barren']:>6} {z['mobs']:>5} {density_label}")
        lines.append("")

    issues = audit.get("issues", [])
    if issues:
        lines.append(f"  |rIssues ({len(issues)}):|n")
        for i in issues[:20]:
            lines.append(f"    {i['issue']}: {i['room_key']}")
        if len(issues) > 20:
            lines.append(f"    ... and {len(issues) - 20} more.")
        lines.append("")

    lines.append("|Y" + "=" * 65 + "|n")
    return "\n".join(lines)