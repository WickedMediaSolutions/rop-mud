"""
Realm Verification Engine for 'rop'
=====================================

Pure-query walker and population auditor.  Walks the room graph from
every faction starter hub, checks zone mob density, verifies faction
exclusivity / correct transitions, and produces a detailed status report.

Usage (evennia shell):

    import world.realm_verify as rv
    result = rv.verify_realm(full_walk=True)
    print(result["report"])

The same engine is used by the in-game ``@verifyrealm`` command
(see ``commands/realm_admin.py``).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from evennia import search_tag as _evennia_search_tag
    from evennia.objects.models import ObjectDB
    from evennia.utils.ansi import strip_ansi
except Exception:
    _evennia_search_tag = None
    ObjectDB = None
    strip_ansi = lambda x: str(x or "")

import world.builder_phase1 as b1
import world.boss_registry as boss_registry


# ---------------------------------------------------------------------------
# Constants (mirrored from realm_population to avoid circular imports)
# ---------------------------------------------------------------------------

FACTION_GOOD = "Aethelgard Alliance"
FACTION_EVIL = "Gorgoroth Horde"
FACTION_NEUTRAL = "Neutral"

ALIGNMENT_GOOD = "Good"
ALIGNMENT_EVIL = "Evil"

GOOD_ZONES: Set[str] = set(b1.GOOD_ZONES.keys())
EVIL_ZONES: Set[str] = set(b1.EVIL_ZONES.keys())
NEUTRAL_ZONES: Set[str] = set(b1.NEUTRAL_ZONES.keys())
ALL_ZONES: Set[str] = GOOD_ZONES | EVIL_ZONES | NEUTRAL_ZONES

GOOD_STARTER_ZONES = {"sunspire_meadows"}
EVIL_STARTER_ZONES = {"brimstone_courtyard"}

GOOD_HUB_KEYS = [
    "Aethelgard - Shrine of Light",
    "Aethelgard - The Grand Sanctum",
]
EVIL_HUB_KEYS = [
    "Gorgoroth - Dark Temple",
    "Gorgoroth - The Blood Forge",
]

GOOD_TOWN_NAMES = [name for _key, name in b1.GOOD_TOWNS]
EVIL_TOWN_NAMES = [name for _key, name in b1.EVIL_TOWNS]

BOSS_ROOM_KEYS: Set[str] = set(boss_registry.BOSS_ROOM_LOOKUP.values())


def search_tag(tag: str, category: str = "zone") -> list:
    """Safe search_tag wrapper that returns [] when Evennia is unavailable."""
    if _evennia_search_tag is not None:
        return list(_evennia_search_tag(tag, category=category))
    return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_room_by_key(key: str) -> Optional[Any]:
    """Find a room by exact key, stripped of ANSI."""
    results = None
    try:
        from evennia import search_object
        results = search_object(key, typeclass="typeclasses.rooms.Room")
    except Exception:
        pass
    if results:
        return results[0]
    if ObjectDB is not None:
        stripped = strip_ansi(key).lower()
        for room in ObjectDB.objects.filter(db_typeclass_path__endswith="Room"):
            if strip_ansi(room.db_key or "").lower() == stripped:
                return room
    return None


def _zone_for_room(room: Any) -> Optional[str]:
    """Return the zone key a room belongs to, if any."""
    try:
        tags = room.tags.get(category="zone")
        if tags:
            return tags[0]
    except Exception:
        pass
    return room.attributes.get("zone")


def _faction_territory(room: Any) -> Optional[str]:
    """Return the faction territory attribute of a room."""
    try:
        return room.attributes.get("faction_territory")
    except Exception:
        return None


def _room_is_safe(room: Any) -> bool:
    try:
        return bool(room.attributes.get("safe_zone", False))
    except Exception:
        return False


def _mob_count(room: Any) -> int:
    """Count alive realm mobs in a room."""
    count = 0
    try:
        for obj in room.contents:
            if not hasattr(obj, "attributes"):
                continue
            if not obj.attributes.get("is_mob", False):
                continue
            if obj.attributes.get("hp", 0) > 0:
                count += 1
    except Exception:
        pass
    return count


def _npc_count(room: Any) -> int:
    """Count NPCs (vendors, trainers, guards)."""
    count = 0
    try:
        for obj in room.contents:
            if not hasattr(obj, "attributes"):
                continue
            if obj.attributes.get("is_vendor") or obj.attributes.get("is_trainer") or \
               obj.attributes.get("is_npc"):
                count += 1
    except Exception:
        pass
    return count


def _has_boss(room: Any) -> bool:
    try:
        for obj in room.contents:
            if not hasattr(obj, "attributes"):
                continue
            if obj.attributes.get("is_boss") or obj.attributes.get("boss_id"):
                return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Graph walk
# ---------------------------------------------------------------------------

def walk_from(start_room: Any, max_depth: int = 300) -> Set[int]:
    """
    BFS walk from *start_room* following valid exits.
    Returns the set of room dbrefs reachable within *max_depth* hops.
    """
    visited: Set[int] = set()
    queue: List[Any] = [start_room]
    depth = 0
    while queue and depth < max_depth:
        next_level: List[Any] = []
        for room in queue:
            if room.id in visited:
                continue
            visited.add(room.id)
            try:
                exits = getattr(room, "exits", [])
            except Exception:
                exits = []
            for ex in exits:
                dest = getattr(ex, "destination", None)
                if dest and dest.id not in visited:
                    next_level.append(dest)
        queue = next_level
        depth += 1
    return visited


# ---------------------------------------------------------------------------
# Verification engine
# ---------------------------------------------------------------------------

def verify_one_way_exits() -> Dict[str, Any]:
    """
    Scan all rooms for exits that lack a reciprocal return exit.

    A one-way exit is an exit from room A to room B where room B has
    no exit leading back to room A.  These are common builder mistakes
    that trap players or break mob pathfinding.

    Returns a dict with 'one_way_count', 'total_exits', and 'details'.
    """
    result: Dict[str, Any] = {
        "one_way_count": 0,
        "total_exits": 0,
        "details": [],
    }

    if ObjectDB is None:
        return result

    try:
        rooms = ObjectDB.objects.filter(db_typeclass_path__endswith="Room")
    except Exception:
        return result

    # Build a set of (source_id, dest_id) pairs for all exits.
    exit_pairs: Set[Tuple[int, int]] = set()

    for room in rooms:
        try:
            for ex in room.exits:
                dest = ex.destination
                if dest is None:
                    continue
                result["total_exits"] += 1
                exit_pairs.add((room.id, dest.id))
        except Exception:
            continue

    # Check each exit for a reciprocal.
    for room in rooms:
        try:
            for ex in room.exits:
                dest = ex.destination
                if dest is None:
                    continue
                # Does the destination have an exit back to this room?
                if (dest.id, room.id) not in exit_pairs:
                    result["one_way_count"] += 1
                    result["details"].append(
                        f"One-way: {room.key} (#{room.id}) -> "
                        f"{dest.key} (#{dest.id}) via '{ex.key}'"
                    )
        except Exception:
            continue

    return result


def verify_realm(full_walk: bool = False) -> Dict[str, Any]:
    """
    Run a comprehensive realm audit.

    Parameters:
        full_walk: If True, BFS-walk the graph from each hub and report
                   reachable zone coverage.  Expensive on large realms.

    Returns a dict with:
        report   — formatted ANSI report string
        summary  — dict of key metrics
        issues   — list of issue dicts
    """
    issues: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 1. Hub room existence
    # ------------------------------------------------------------------
    good_hubs = []
    evil_hubs = []
    for key in GOOD_HUB_KEYS:
        room = _find_room_by_key(key)
        if room:
            good_hubs.append(room)
        else:
            issues.append({"severity": "critical", "area": "hubs",
                           "msg": f"Good hub room missing: {key}"})
    for key in EVIL_HUB_KEYS:
        room = _find_room_by_key(key)
        if room:
            evil_hubs.append(room)
        else:
            issues.append({"severity": "critical", "area": "hubs",
                           "msg": f"Evil hub room missing: {key}"})
    summary["good_hubs"] = len(good_hubs)
    summary["evil_hubs"] = len(evil_hubs)

    # ------------------------------------------------------------------
    # 2. Faction city -> starter-zone linkage
    # ------------------------------------------------------------------
    good_shrine = _find_room_by_key(GOOD_HUB_KEYS[0])
    evil_temple = _find_room_by_key(EVIL_HUB_KEYS[0])
    good_starter = evil_starter = None
    try:
        good_starter = search_tag("sunspire_meadows_1", category="room_id")
        good_starter = good_starter[0] if good_starter else None
    except Exception:
        pass
    try:
        evil_starter = search_tag("brimstone_courtyard_1", category="room_id")
        evil_starter = evil_starter[0] if evil_starter else None
    except Exception:
        pass

    summary["good_starter_exists"] = good_starter is not None
    summary["evil_starter_exists"] = evil_starter is not None

    if good_shrine and good_starter:
        exits = [e.destination for e in good_shrine.exits if e.destination]
        if good_starter not in exits:
            issues.append({"severity": "warning", "area": "links",
                           "msg": "Good shrine not directly linked to sunspire_meadows_1"})
    if evil_temple and evil_starter:
        exits = [e.destination for e in evil_temple.exits if e.destination]
        if evil_starter not in exits:
            issues.append({"severity": "warning", "area": "links",
                           "msg": "Evil temple not directly linked to brimstone_courtyard_1"})

    # ------------------------------------------------------------------
    # 3. Zone population audit
    # ------------------------------------------------------------------
    zone_stats: Dict[str, Dict[str, Any]] = {}
    for zone_key in sorted(ALL_ZONES):
        data = b1.ALL_ZONES[zone_key]
        expected = data["count"]
        rooms = list(search_tag(zone_key, category="zone"))
        found = len(rooms)
        total_mobs = sum(_mob_count(r) for r in rooms)
        total_npcs = sum(_npc_count(r) for r in rooms)
        empty_rooms = sum(1 for r in rooms if _mob_count(r) == 0 and not _room_is_safe(r))
        zone_stats[zone_key] = {
            "expected": expected,
            "found": found,
            "mobs": total_mobs,
            "npcs": total_npcs,
            "empty": empty_rooms,
        }
        if found < expected * 0.5:
            issues.append({"severity": "critical", "area": f"zone:{zone_key}",
                           "msg": f"{zone_key}: only {found}/{expected} rooms exist"})
        elif found < expected:
            issues.append({"severity": "warning", "area": f"zone:{zone_key}",
                           "msg": f"{zone_key}: {found}/{expected} rooms (partial)"})
        if total_mobs == 0 and found > 0:
            issues.append({"severity": "warning", "area": f"zone:{zone_key}",
                           "msg": f"{zone_key}: {found} rooms but 0 mobs"})
        if empty_rooms > 0:
            issues.append({"severity": "info", "area": f"zone:{zone_key}",
                           "msg": f"{zone_key}: {empty_rooms} rooms have no mobs"})
    summary["zones_audited"] = len(zone_stats)
    summary["zones"] = zone_stats

    # ------------------------------------------------------------------
    # 4. Boss placement audit
    # ------------------------------------------------------------------
    boss_stats = {"total": 0, "present": 0, "missing": 0}
    for boss_id, data in boss_registry.BOSS_REGISTRY.items():
        boss_stats["total"] += 1
        room_key = boss_registry.BOSS_ROOM_LOOKUP.get(boss_id)
        if not room_key:
            boss_stats["missing"] += 1
            issues.append({"severity": "warning", "area": "bosses",
                           "msg": f"Boss {boss_id}: no room lookup entry"})
            continue
        room = _find_room_by_key(room_key)
        if room is None:
            boss_stats["missing"] += 1
            issues.append({"severity": "warning", "area": "bosses",
                           "msg": f"Boss {boss_id}: lair room '{room_key}' missing"})
        elif _has_boss(room):
            boss_stats["present"] += 1
        else:
            boss_stats["missing"] += 1
            issues.append({"severity": "warning", "area": "bosses",
                           "msg": f"Boss {boss_id}: lair room exists but no boss present"})
    summary["bosses"] = boss_stats

    # ------------------------------------------------------------------
    # 5. Faction misalignment scan
    # ------------------------------------------------------------------
    misaligned = 0
    for zone_key in GOOD_ZONES | EVIL_ZONES:
        expected_faction = FACTION_GOOD if zone_key in GOOD_ZONES else FACTION_EVIL
        for room in search_tag(zone_key, category="zone"):
            for obj in room.contents:
                try:
                    if not hasattr(obj, "attributes") or getattr(obj, "has_account", False):
                        continue
                    mob_faction = obj.attributes.get("faction")
                    if mob_faction is None:
                        continue
                    if obj.attributes.get("is_mob") and mob_faction not in (FACTION_NEUTRAL, expected_faction):
                        misaligned += 1
                except Exception:
                    continue
    summary["misaligned_mobs"] = misaligned
    if misaligned > 0:
        issues.append({"severity": "critical", "area": "faction",
                       "msg": f"{misaligned} misaligned mobs found in faction zones"})

    # ------------------------------------------------------------------
    # 6. Exit / pathing validation (faction border transitions)
    # ------------------------------------------------------------------
    border_issues = 0
    for zone_key in GOOD_ZONES | EVIL_ZONES:
        expected_faction = FACTION_GOOD if zone_key in GOOD_ZONES else FACTION_EVIL
        restricted = zone_key in (GOOD_STARTER_ZONES | EVIL_STARTER_ZONES)
        for room in search_tag(zone_key, category="zone"):
            for ex in getattr(room, "exits", []):
                dest = getattr(ex, "destination", None)
                if dest is None:
                    continue
                dest_zone = _zone_for_room(dest)
                dest_territory = _faction_territory(dest)
                # If restricted zone connects to opposite faction, warn
                if restricted and dest_territory and dest_territory != expected_faction and \
                   dest_territory != FACTION_NEUTRAL:
                    border_issues += 1
                    # Only record the first few to avoid spam
                    if border_issues <= 5:
                        issues.append({"severity": "warning", "area": "borders",
                                       "msg": f"Boundary leak: {room.key} -> {dest.key} "
                                              f"({expected_faction} -> {dest_territory})"})
    summary["border_issues"] = border_issues

    # ------------------------------------------------------------------
    # 7. Graph walk (optional, expensive)
    # ------------------------------------------------------------------
    if full_walk and (good_hubs or evil_hubs):
        if good_hubs:
            good_reachable = walk_from(good_hubs[0])
            good_zone_hits = set()
            for dbref in good_reachable:
                try:
                    room = ObjectDB.objects.filter(id=dbref).first()
                except Exception:
                    continue
                if room is None:
                    continue
                zone = _zone_for_room(room)
                if zone:
                    good_zone_hits.add(zone)
            summary["good_reachable_zones"] = sorted(good_zone_hits)
            missing_good = set(b1.GOOD_ZONES) - good_zone_hits - {"sunspire_meadows"}
            if missing_good:
                issues.append({"severity": "info", "area": "walk",
                               "msg": f"Good zones unreachable from hub: {sorted(missing_good)}"})
        if evil_hubs:
            evil_reachable = walk_from(evil_hubs[0])
            evil_zone_hits = set()
            for dbref in evil_reachable:
                try:
                    room = ObjectDB.objects.filter(id=dbref).first()
                except Exception:
                    continue
                if room is None:
                    continue
                zone = _zone_for_room(room)
                if zone:
                    evil_zone_hits.add(zone)
            summary["evil_reachable_zones"] = sorted(evil_zone_hits)
            missing_evil = set(b1.EVIL_ZONES) - evil_zone_hits - {"brimstone_courtyard"}
            if missing_evil:
                issues.append({"severity": "info", "area": "walk",
                               "msg": f"Evil zones unreachable from hub: {sorted(missing_evil)}"})

    # ------------------------------------------------------------------
    # Build report string
    # ------------------------------------------------------------------
    lines = []
    lines.append("|Y" + "=" * 75 + "|n")
    lines.append("|cREALM VERIFICATION REPORT|n")
    lines.append("|Y" + "=" * 75 + "|n")
    lines.append("")

    # Hubs
    lines.append(f"  |wFaction Hubs:|n Good={summary.get('good_hubs', 0)}  Evil={summary.get('evil_hubs', 0)}")
    lines.append(f"  |wStarter Zones:|n Good={'|gFOUND|n' if summary.get('good_starter_exists') else '|rMISSING|n'}  "
                 f"Evil={'|gFOUND|n' if summary.get('evil_starter_exists') else '|rMISSING|n'}")
    lines.append("")

    # Zones
    lines.append("  |wZone Population:|n")
    lines.append(f"  {'Zone':<26} {'Rooms':>6} {'Mobs':>5} {'NPCs':>5} {'Empty':>5}")
    lines.append(f"  {'-' * 47}")
    for zone_key in sorted(zone_stats):
        z = zone_stats[zone_key]
        data = b1.ALL_ZONES[zone_key]
        f_tag = "|gG|n" if zone_key in GOOD_ZONES else ("|rE|n" if zone_key in EVIL_ZONES else "|yN|n")
        lines.append(f"  {f_tag} {zone_key:<23} {z['found']:>4}/{data['count']:<4} "
                     f"{z['mobs']:>5} {z['npcs']:>5} {z['empty']:>5}")
    lines.append("")

    # Bosses
    bs = summary.get("bosses", {})
    lines.append(f"  |wBosses:|n {bs.get('present', 0)}/{bs.get('total', 0)} present "
                 f"({bs.get('missing', 0)} missing)")
    lines.append("")

    # Faction
    lines.append(f"  |wMisaligned Mobs:|n {summary.get('misaligned_mobs', 0)}")
    lines.append(f"  |wBorder Issues:|n {summary.get('border_issues', 0)}")
    lines.append("")

    # Issues
    if issues:
        lines.append("  |rISSUES:|n")
        for issue in issues:
            sev_color = {"critical": "|r", "warning": "|y", "info": "|w"}
            color = sev_color.get(issue["severity"], "|w")
            lines.append(f"  {color}[{issue['severity'].upper():<8}]|n "
                         f"[{issue['area']}] {issue['msg']}")
        lines.append("")

    if not issues:
        lines.append("  |gNo issues found. Realm is healthy.|n")
        lines.append("")

    lines.append("|Y" + "=" * 75 + "|n")

    return {
        "report": "\n".join(lines),
        "summary": summary,
        "issues": issues,
    }