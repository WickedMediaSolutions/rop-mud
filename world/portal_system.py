"""
Portal / Teleport System for 'rop'
====================================

Provides fast-travel gateways between discovered zones.  Players must
first discover a zone (by physically entering it) before they can
teleport to it.  Portals cost gold and have a cooldown.

Features:
  - ``PORTAL_NETWORK`` — predefined portal locations in hub cities
  - ``discover_zone(player, zone_tag)`` — mark a zone as discovered
  - ``is_zone_discovered(player, zone_tag)`` — check discovery status
  - ``get_teleport_cost(zone_tag)`` — gold cost for teleport
  - ``teleport_player(player, zone_tag)`` — execute teleport
  - ``get_discovered_zones(player)`` — list all discovered zones
  - ``get_teleport_cooldown(player)`` — check remaining cooldown

Portal Rules:
  - Players can only teleport to zones they have previously visited.
  - Teleport costs scale with zone tier (further = more expensive).
  - 5-minute cooldown between teleports.
  - Teleport only works from portal rooms (hub cities).
  - Players arrive at the zone's entry point (first room).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from evennia import search_tag
    from evennia.utils.ansi import strip_ansi
except Exception:
    search_tag = None
    strip_ansi = lambda x: str(x or "")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Cooldown in seconds between teleports
TELEPORT_COOLDOWN = 300  # 5 minutes

# Gold cost by zone tier
TIER_TELEPORT_COSTS = {
    1: 5,    # Starter zones
    2: 25,   # Near outer
    3: 100,  # Mid-game
    4: 500,  # Deep wilderness
    5: 2000, # End-game
}

# Portal rooms — these are the rooms where players can teleport FROM.
# Format: {room_key: faction}
PORTAL_NETWORK: Dict[str, str] = {
    "Aethelgard - Sunlit Square": "Aethelgard Alliance",
    "Aethelgard - The Grand Sanctum": "Aethelgard Alliance",
    "Gorgoroth - Subterranean Barracks": "Gorgoroth Horde",
    "Gorgoroth - The Blood Forge": "Gorgoroth Horde",
}

# Zone entry points — where players arrive when teleporting TO a zone.
# Format: {zone_tag: room_key_to_look_for}
ZONE_ENTRY_POINTS: Dict[str, str] = {
    "sunspire_meadows": "Sunspire Meadows",
    "brimstone_courtyard": "Brimstone Courtyard",
    "rolling_plains": "Rolling Plains of Aethelgard",
    "shadow_fen": "Shadow Fen",
    "emerald_forest": "Emerald Forest",
    "crystal_lake": "Crystal Lake District",
    "silverpine_hills": "Silverpine Hills",
    "blasted_heath": "Blasted Heath",
    "molten_scar": "Molten Scar",
    "golden_farmland": "Golden Farmland",
    "sunrise_coast": "Sunrise Coast",
    "verdant_valley": "Verdant Valley",
    "highland_meadows": "Highland Meadows",
    "ashen_barrens": "Ashen Barrens",
    "thornwood_thickets": "Thornwood Thickets",
    "dusk_coast": "Dusk Coast",
}


# ---------------------------------------------------------------------------
# Discovery Tracking
# ---------------------------------------------------------------------------

def _get_discovery_attr(player: Any) -> Set[str]:
    """Get or create the discovered_zones set on a player."""
    try:
        discovered = player.attributes.get("discovered_zones")
        if discovered is None:
            discovered = set()
            player.attributes.add("discovered_zones", discovered)
        return discovered
    except Exception:
        return set()


def _save_discovery_attr(player: Any, discovered: Set[str]) -> None:
    """Save the discovered_zones set back to the player."""
    try:
        player.attributes.add("discovered_zones", discovered)
    except Exception:
        pass


def discover_zone(player: Any, zone_tag: str) -> bool:
    """
    Mark a zone as discovered by the player.
    Returns True if this was a new discovery.
    """
    discovered = _get_discovery_attr(player)
    if zone_tag in discovered:
        return False
    discovered.add(zone_tag)
    _save_discovery_attr(player, discovered)

    # Auto-discover on room entry is handled by the room typeclass hook
    return True


def is_zone_discovered(player: Any, zone_tag: str) -> bool:
    """Check if a player has discovered a zone."""
    discovered = _get_discovery_attr(player)
    return zone_tag in discovered


def get_discovered_zones(player: Any) -> List[str]:
    """Return a sorted list of zone tags the player has discovered."""
    discovered = _get_discovery_attr(player)
    return sorted(discovered)


# ---------------------------------------------------------------------------
# Portal Room Detection
# ---------------------------------------------------------------------------

def is_portal_room(room: Any) -> bool:
    """Return True if this room is a portal hub."""
    if room is None:
        return False
    room_key = getattr(room, "key", "") or ""
    # Strip ANSI
    try:
        room_key = strip_ansi(room_key)
    except Exception:
        pass
    return room_key in PORTAL_NETWORK


def _find_room_by_key(key: str) -> Optional[Any]:
    """Find a room by its key string."""
    try:
        from evennia import search_object
        results = search_object(key, typeclass="typeclasses.rooms.Room")
        if results:
            return results[0]
    except Exception:
        pass
    return None


def _get_zone_tier(zone_tag: str) -> int:
    """Get the tier of a zone from its tag."""
    try:
        from world.zone_levels import get_zone_level_range
        lmin, lmax = get_zone_level_range(zone_tag)
        return _level_to_tier(lmin)
    except Exception:
        return 1


def _level_to_tier(level: int) -> int:
    """Convert a level to a tier number."""
    if level <= 5:
        return 1
    elif level <= 15:
        return 2
    elif level <= 40:
        return 3
    elif level <= 60:
        return 4
    else:
        return 5


# ---------------------------------------------------------------------------
# Teleport Logic
# ---------------------------------------------------------------------------

def get_teleport_cost(player: Any, zone_tag: str) -> int:
    """
    Get the gold cost to teleport to a zone.

    Returns 0 if the zone is undiscovered (shouldn't be called),
    or the tier-based cost based on destination distance.
    """
    tier = _get_zone_tier(zone_tag)
    return TIER_TELEPORT_COSTS.get(tier, 100)


def get_teleport_cooldown(player: Any) -> int:
    """
    Get remaining teleport cooldown in seconds.
    Returns 0 if ready.
    """
    try:
        last_teleport = player.attributes.get("last_teleport_time", default=0)
        if last_teleport is None:
            return 0
        elapsed = time.time() - float(last_teleport)
        remaining = TELEPORT_COOLDOWN - elapsed
        return max(0, int(remaining))
    except Exception:
        return 0


def teleport_player(player: Any, zone_tag: str) -> Dict[str, Any]:
    """
    Attempt to teleport a player to a discovered zone.

    Returns:
      {"success": bool, "message": str, "cost": int}
    """
    # Check if player is in a portal room
    location = getattr(player, "location", None)
    if not is_portal_room(location):
        return {"success": False, "message": "You must be at a portal location to teleport.",
                "cost": 0}

    # Check discovery
    if not is_zone_discovered(player, zone_tag):
        return {"success": False, "message": f"You have not yet discovered the {zone_tag} zone.",
                "cost": 0}

    # Check cooldown
    cooldown = get_teleport_cooldown(player)
    if cooldown > 0:
        minutes = cooldown // 60
        seconds = cooldown % 60
        return {"success": False,
                "message": f"Teleport on cooldown. Wait {minutes}m {seconds}s.",
                "cost": 0}

    # Check gold
    cost = get_teleport_cost(player, zone_tag)
    try:
        gold = player.attributes.get("gold", default=0) or 0
    except Exception:
        gold = 0

    if gold < cost:
        return {"success": False,
                "message": f"You need {cost} gold to teleport. You have {gold}.",
                "cost": cost}

    # Find destination room
    entry_key = ZONE_ENTRY_POINTS.get(zone_tag)
    if not entry_key:
        return {"success": False, "message": f"No entry point configured for zone {zone_tag}.",
                "cost": 0}

    destination = _find_room_by_key(entry_key)
    if destination is None:
        # Try zone tag search
        try:
            rooms = list(search_tag(zone_tag, category="zone"))
            if rooms:
                destination = rooms[0]
        except Exception:
            pass

    if destination is None:
        return {"success": False,
                "message": f"Destination room for {zone_tag} not found.",
                "cost": 0}

    # Execute teleport
    try:
        player.attributes.add("gold", gold - cost)
        player.attributes.add("last_teleport_time", time.time())
        player.msg(f"|ySpending |w{cost} gold|y, you step through the portal...|n")
        player.move_to(destination)
    except Exception as e:
        return {"success": False, "message": f"Teleport failed: {e}", "cost": 0}

    return {"success": True,
            "message": f"You teleport to {zone_tag.replace('_', ' ').title()}.",
            "cost": cost}


# ---------------------------------------------------------------------------
# Portal Command Helpers
# ---------------------------------------------------------------------------

def cmd_portal_list(caller: Any) -> str:
    """Handle 'portal list' — show discovered zones and costs."""
    if not is_portal_room(caller.location):
        return "You must be standing at a portal to use this command."

    discovered = get_discovered_zones(caller)
    if not discovered:
        return "You have not discovered any zones yet. Explore the realm!"

    cooldown = get_teleport_cooldown(caller)

    lines = ["|c=== Portal Network ==="]
    lines.append("|YDestination          |n |wCost|n  |yStatus|n")
    lines.append("-" * 42)

    for zone_tag in discovered:
        cost = get_teleport_cost(caller, zone_tag)
        display_name = zone_tag.replace("_", " ").title()
        gold = caller.attributes.get("gold", 0) or 0
        if gold >= cost:
            status = "|gAffordable|n"
        else:
            status = "|rToo Expensive|n"
        lines.append(f"  {display_name:<25} {cost:>4}g  {status}")

    lines.append("")
    if cooldown > 0:
        minutes = cooldown // 60
        seconds = cooldown % 60
        lines.append(f"|yCooldown: {minutes}m {seconds}s remaining|n")
    else:
        lines.append("|gPortal ready. Use: portal <destination>|n")

    return "\n".join(lines)


def cmd_portal_travel(caller: Any, args: str) -> str:
    """Handle 'portal <destination>' — teleport to a discovered zone."""
    if not args.strip():
        return cmd_portal_list(caller)

    zone_tag = args.strip().lower().replace(" ", "_")

    # Try to match against discovered zones with partial name
    discovered = get_discovered_zones(caller)
    match = None
    for dz in discovered:
        if dz.startswith(zone_tag) or zone_tag in dz:
            if match is not None:
                return (f"Multiple zones match '{args}'. "
                        f"Be more specific. Discovered: {', '.join(discovered)}")
            match = dz
        if dz == zone_tag:
            match = dz
            break

    if match is None:
        return f"Zone '{args}' not found among your discovered zones."

    result = teleport_player(caller, match)
    return result["message"]


# ---------------------------------------------------------------------------
# Auto-discovery Hook
# ---------------------------------------------------------------------------

def auto_discover_on_enter(player: Any, room: Any) -> Optional[str]:
    """
    Called when a player enters a room. Auto-discovers the room's zone.

    Should be called from Room.at_object_receive or similar hook.

    Returns the zone_tag if newly discovered, None otherwise.
    """
    if not player or not hasattr(player, "has_account"):
        return None
    if not player.has_account:
        return None

    try:
        zone_tag = room.attributes.get("zone_tag", default=None)
        if zone_tag and discover_zone(player, zone_tag):
            player.msg(f"|c[Discovery]|n You have discovered the |Y{zone_tag.replace('_', ' ').title()}|n zone!")
            return zone_tag
    except Exception:
        pass
    return None