"""
Zone Discovery & Mapping System for 'rop'
===========================================

Tracks which rooms, zones, and landmarks each player has visited.
Provides fog-of-war style exploration mechanics and a mapping
interface for discovered areas.

Features:
  - ``mark_room_visited(player, room)`` — record room visit
  - ``is_room_discovered(player, room)`` — check if room seen
  - ``get_exploration_progress(player)`` — % of realm explored
  - ``get_zone_map(player, zone_tag)`` — ASCII map of discovered rooms
  - ``EXPLORATION_MILESTONES`` — rewards for exploration progress
  - ``get_discovered_landmarks(player)`` — list found landmarks

Integration:
  - Room.at_object_receive calls mark_room_visited automatically
  - Portal system uses discovery data for fast-travel unlocks
  - Exploration milestones grant XP/gold rewards
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from evennia.objects.models import ObjectDB
    from evennia.utils.ansi import strip_ansi
except Exception:
    ObjectDB = None
    strip_ansi = lambda x: str(x or "")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Exploration milestones: percentage -> (title, xp_reward, gold_reward)
EXPLORATION_MILESTONES: Dict[int, Tuple[str, int, int]] = {
    5: ("Wanderer", 50, 10),
    10: ("Pathfinder", 100, 25),
    25: ("Explorer", 250, 50),
    50: ("Cartographer", 500, 100),
    75: ("Scout of the Realm", 1000, 250),
    90: ("Master Explorer", 2000, 500),
    100: ("Realm Walker", 5000, 1000),
}

# Special landmarks that grant bonus discovery XP
LANDMARK_TAGS = {
    "boss_lair",
    "ancient_ruins",
    "hidden_sanctuary",
    "dragon_roost",
    "city_hub",
    "portal_gate",
}

# Landmark discovery rewards
LANDMARK_XP = 25
LANDMARK_GOLD = 10


# ---------------------------------------------------------------------------
# Discovery Tracking
# ---------------------------------------------------------------------------

def _get_exploration_attr(player: Any) -> Set[int]:
    """Get or create the explored_rooms set on a player (stores room dbrefs)."""
    try:
        explored = player.attributes.get("explored_rooms")
        if explored is None:
            explored = set()
            player.attributes.add("explored_rooms", explored)
        return explored
    except Exception:
        return set()


def _save_exploration_attr(player: Any, explored: Set[int]) -> None:
    """Save the explored_rooms set back to player attributes."""
    try:
        player.attributes.add("explored_rooms", explored)
    except Exception:
        pass


def _get_landmarks_attr(player: Any) -> Set[str]:
    """Get or create discovered_landmarks set on a player."""
    try:
        landmarks = player.attributes.get("discovered_landmarks")
        if landmarks is None:
            landmarks = set()
            player.attributes.add("discovered_landmarks", landmarks)
        return landmarks
    except Exception:
        return set()


def _save_landmarks_attr(player: Any, landmarks: Set[str]) -> None:
    """Save discovered_landmarks to player attributes."""
    try:
        player.attributes.add("discovered_landmarks", landmarks)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Room / Zone Discovery
# ---------------------------------------------------------------------------

def mark_room_visited(player: Any, room: Any) -> bool:
    """
    Record a room as visited by the player.

    Returns True if this was a first-time discovery.
    Also handles:
      - Landmark detection and rewards
      - Zone discovery (via portal_system)
      - Exploration milestone checks

    Should be called from Room.at_object_receive.
    """
    if not player or not hasattr(player, "has_account"):
        return False
    if not player.has_account:
        return False
    if room is None:
        return False

    try:
        room_id = room.id
    except Exception:
        return False

    explored = _get_exploration_attr(player)

    if room_id in explored:
        return False

    explored.add(room_id)
    _save_exploration_attr(player, explored)

    # Check for zone discovery
    try:
        zone_tag = room.attributes.get("zone_tag", default=None)
        if zone_tag:
            from world.portal_system import discover_zone
            discover_zone(player, zone_tag)
    except Exception:
        pass

    # Check for landmark discovery
    try:
        room_tags = room.tags.all(return_key=True) if hasattr(room, "tags") else []
        for tag in room_tags:
            if tag in LANDMARK_TAGS:
                landmarks = _get_landmarks_attr(player)
                if tag not in landmarks:
                    landmarks.add(tag)
                    _save_landmarks_attr(player, landmarks)

                    # Grant bonus rewards
                    try:
                        current_xp = player.attributes.get("xp", default=0) or 0
                        current_gold = player.attributes.get("gold", default=0) or 0
                        player.attributes.add("xp", current_xp + LANDMARK_XP)
                        player.attributes.add("gold", current_gold + LANDMARK_GOLD)
                    except Exception:
                        pass

                    player.msg(
                        f"|Y[Landmark Discovered!]|n {tag.replace('_', ' ').title()} "
                        f"|g(+{LANDMARK_XP} XP, +{LANDMARK_GOLD} gold)|n"
                    )
    except Exception:
        pass

    # Check exploration milestones
    _check_milestones(player)

    return True


def is_room_discovered(player: Any, room: Any) -> bool:
    """Check if a player has visited a specific room."""
    try:
        room_id = room.id
    except Exception:
        return False
    explored = _get_exploration_attr(player)
    return room_id in explored


def get_discovered_landmarks(player: Any) -> List[str]:
    """Return sorted list of discovered landmark tags."""
    landmarks = _get_landmarks_attr(player)
    return sorted(landmarks)


# ---------------------------------------------------------------------------
# Exploration Progress & Milestones
# ---------------------------------------------------------------------------

def get_exploration_progress(player: Any) -> Dict[str, Any]:
    """
    Calculate the player's exploration progress as a percentage.

    Returns:
      {
        "rooms_explored": int,
        "rooms_total": int,
        "percent": float,
        "zones_discovered": int,
        "zones_total": int,
        "title": str,
        "next_milestone": int or None,
      }
    """
    explored = _get_exploration_attr(player)

    rooms_total = 0
    try:
        if ObjectDB is not None:
            rooms_total = ObjectDB.objects.filter(
                db_typeclass_path__endswith="Room"
            ).count()
    except Exception:
        pass

    rooms_explored = len(explored)
    percent = (rooms_explored / rooms_total * 100) if rooms_total > 0 else 0.0

    # Determine exploration title
    title = "Novice"
    for threshold in sorted(EXPLORATION_MILESTONES.keys(), reverse=True):
        if percent >= threshold:
            title = EXPLORATION_MILESTONES[threshold][0]
            break

    # Find next milestone
    next_milestone = None
    for threshold in sorted(EXPLORATION_MILESTONES.keys()):
        if percent < threshold:
            next_milestone = threshold
            break

    # Count zones
    try:
        from world.portal_system import get_discovered_zones
        zones_discovered = len(get_discovered_zones(player))
    except Exception:
        zones_discovered = 0

    try:
        import world.builder_phase1 as b1
        zones_total = len(b1.ALL_ZONES)
    except Exception:
        zones_total = 0

    return {
        "rooms_explored": rooms_explored,
        "rooms_total": rooms_total,
        "percent": round(percent, 1),
        "zones_discovered": zones_discovered,
        "zones_total": zones_total,
        "title": title,
        "next_milestone": next_milestone,
    }


def _get_milestones_attr(player: Any) -> Set[int]:
    """Get or create achieved_milestones set."""
    try:
        milestones = player.attributes.get("exploration_milestones")
        if milestones is None:
            milestones = set()
            player.attributes.add("exploration_milestones", milestones)
        return milestones
    except Exception:
        return set()


def _check_milestones(player: Any) -> Optional[int]:
    """
    Check if player has reached a new exploration milestone.
    Returns the milestone percentage if newly achieved, None otherwise.
    """
    progress = get_exploration_progress(player)
    percent = int(progress["percent"])
    achieved = _get_milestones_attr(player)

    for threshold in sorted(EXPLORATION_MILESTONES.keys()):
        if percent >= threshold and threshold not in achieved:
            achieved.add(threshold)
            player.attributes.add("exploration_milestones", achieved)

            title, xp, gold = EXPLORATION_MILESTONES[threshold]
            try:
                current_xp = player.attributes.get("xp", default=0) or 0
                current_gold = player.attributes.get("gold", default=0) or 0
                player.attributes.add("xp", current_xp + xp)
                player.attributes.add("gold", current_gold + gold)
            except Exception:
                pass

            player.msg(
                f"|Y=== EXPLORATION MILESTONE ===|n\n"
                f"|cYou have explored |W{percent}%|c of the realm!|n\n"
                f"|yTitle Earned:|n |W{title}|n\n"
                f"|gReward: +{xp} XP, +{gold} gold|n"
            )
            return threshold

    return None


# ---------------------------------------------------------------------------
# Zone Map Generation
# ---------------------------------------------------------------------------

def get_zone_map(player: Any, zone_tag: str) -> str:
    """
    Generate an ASCII map of discovered rooms in a zone.

    Renders a grid showing:
      - [ ] Undiscovered room
      - [X] Visited room
      - [P] Player's current location
      - [?] Room whose existence is hinted but not confirmed

    Returns a formatted string suitable for player display.
    """
    try:
        from evennia import search_tag
        rooms = list(search_tag(zone_tag, category="zone"))
    except Exception:
        return f"No rooms found for zone '{zone_tag}'."

    if not rooms:
        return f"No rooms found for zone '{zone_tag}'."

    explored = _get_exploration_attr(player)

    # Group rooms by their zone coordinates
    room_positions: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for room in rooms:
        try:
            x = room.attributes.get("coord_x", default=0) or 0
            y = room.attributes.get("coord_y", default=0) or 0
        except Exception:
            x, y = 0, 0

        is_current = (
            player.location is not None
            and player.location.id == room.id
        )
        is_discovered = room.id in explored or is_current

        key = getattr(room, "key", "?")
        try:
            key = strip_ansi(key)
        except Exception:
            pass

        # Truncate long names
        if len(key) > 25:
            key = key[:22] + "..."

        room_positions[(x, y)] = {
            "key": key,
            "discovered": is_discovered,
            "current": is_current,
        }

    if not room_positions:
        # No coordinate data — render a simple list
        lines = [f"|c=== Zone Map: {zone_tag.replace('_', ' ').title()} ===|n"]
        lines.append(f"Rooms discovered: {len(explored & {r.id for r in rooms})}/{len(rooms)}")
        lines.append("")
        for room in rooms:
            rp = room_positions.get((0, 0))
            marker = "|g[P]|n" if rp and rp["current"] else ("|Y[X]|n" if room.id in explored else "|W[ ]|n")
            lines.append(f"  {marker} {getattr(room, 'key', '?')}")
        return "\n".join(lines)

    # Build coordinate grid
    min_x = min(p[0] for p in room_positions)
    max_x = max(p[0] for p in room_positions)
    min_y = min(p[1] for p in room_positions)
    max_y = max(p[1] for p in room_positions)

    lines = [f"|c=== Zone Map: {zone_tag.replace('_', ' ').title()} ===|n"]
    lines.append(f"|WGrid: ({min_x},{min_y}) to ({max_x},{max_y})|n")
    lines.append("")

    # Header
    lines.append("    " + "".join(f"{x:^3}" for x in range(min_x, max_x + 1)))
    lines.append("    " + "---" * (max_x - min_x + 1))

    for y in range(min_y, max_y + 1):
        row = f"{y:>3}|"
        for x in range(min_x, max_x + 1):
            pos = room_positions.get((x, y))
            if pos is None:
                row += " . "
            elif pos["current"]:
                row += "|g[P]|n"
            elif pos["discovered"]:
                row += "|Y[X]|n"
            else:
                row += "|W[?]|n"
        lines.append(row)

    lines.append("")
    lines.append("|g[P]|n = Your location  |Y[X]|n = Discovered  |W[?]|n = Uncharted  . = Empty")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Exploration Commands
# ---------------------------------------------------------------------------

def cmd_explore_status(caller: Any) -> str:
    """Handle 'explore' or 'map' command — show exploration progress."""
    progress = get_exploration_progress(caller)

    lines = ["|c=== Exploration Progress ===|n"]
    lines.append(f"  |wTitle:|n {progress['title']}")
    lines.append(f"  |wRooms Explored:|n {progress['rooms_explored']}/{progress['rooms_total']} "
                 f"({progress['percent']}%)")
    lines.append(f"  |wZones Discovered:|n {progress['zones_discovered']}/{progress['zones_total']}")

    landmarks = get_discovered_landmarks(caller)
    if landmarks:
        lines.append(f"  |wLandmarks Found:|n {', '.join(landmarks)}")

    if progress["next_milestone"] is not None:
        threshold = progress["next_milestone"]
        title, xp, gold = EXPLORATION_MILESTONES[threshold]
        lines.append(f"  |yNext Milestone:|n {threshold}% — {title} "
                     f"(+{xp} XP, +{gold} gold)")

    # Progress bar
    pct = progress["percent"]
    bar_width = 30
    filled = int(bar_width * pct / 100)
    bar = "|g" + "█" * filled + "|n" + "░" * (bar_width - filled)
    lines.append(f"  [{bar}] {pct}%")

    return "\n".join(lines)


def cmd_map_zone(caller: Any, args: str) -> str:
    """Handle 'map <zone>' command — show ASCII map of a discovered zone."""
    zone_tag = args.strip().lower().replace(" ", "_") if args.strip() else ""

    if not zone_tag:
        from world.portal_system import get_discovered_zones
        discovered = get_discovered_zones(caller)
        if not discovered:
            return "You have not discovered any zones yet. Return with 'map <zone_name>'."
        return "Discovered zones: " + ", ".join(d.replace("_", " ").title() for d in discovered)

    return get_zone_map(caller, zone_tag)