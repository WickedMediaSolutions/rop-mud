"""
Zone Level & Difficulty Scaling System for 'rop'
==================================================

Maps every zone to a predefined level range (tier) based on its distance
from the faction starting hubs (Aethelgard for Good, Gorgoroth for Evil).

Tiers:
    1  – Faction Starter Zones / Towns       Level  1–5
    2  – Near Outer Zones                    Level  6–15
    3  – Mid-Game Wilderness                 Level 16–40
    4  – Deep Wilderness & Dungeon Zones     Level 41–60
    5  – High-Level / End-Game Outer Realms  Level 61–80

Provides tag constants, lookup helpers, and scaling functions used by
the realm builder, mob spawner, and unit tests.
"""

# ---------------------------------------------------------------------------
# Tag constants stored on rooms
# ---------------------------------------------------------------------------
ROOM_TAG_ZONE_TIER      = "zone_tier"       # 1–5
ROOM_TAG_LEVEL_MIN      = "zone_level_min"  # e.g. 1
ROOM_TAG_LEVEL_MAX      = "zone_level_max"  # e.g. 5
ROOM_TAG_DANGER         = "zone_danger"     # "safe", "caution", "danger", "deadly"

# ---------------------------------------------------------------------------
# Per-zone tier assignments
# ---------------------------------------------------------------------------

# Tier 1 — Faction Starter Zones & Towns (Level 1–5)
TIER_1_ZONES = [
    "Rolling Plains of Aethelgard",
    "Shadow Fen",
    "Town",
]

# Tier 2 — Near Outer Zones (Level 6–15)
TIER_2_ZONES = [
    "Emerald Forest",
    "Crystal Lake District",
    "Silverpine Hills",
    "Blasted Heath",
    "Molten Scar",
]

# Tier 3 — Mid-Game Wilderness (Level 16–40)
TIER_3_ZONES = [
    "Golden Farmland",
    "Sunrise Coast",
    "Verdant Valley",
    "Scorched Dunes",
    "Cracked Salt Flats",
    "Ancient Mesas",
    "Whispering Oasis Belt",
    "Sunken Ruins of the Sand",
    "Bone Marshes",
    "Iron Crater Fields",
    "Giant Pines",
    "Trade Path Corridor",
    "Misty Glade Groves",
    "Golden Sand Beaches",
]

# Tier 4 — Deep Wilderness & Dungeon Zones (Level 41–60)
TIER_4_ZONES = [
    "Highland Meadows",
    "Ashen Barrens",
    "Thornwood Thickets",
]

# Tier 5 — High-Level / End-Game Outer Realms (Level 61–80)
TIER_5_ZONES = [
    "Dusk Coast",
]

# Master lookup: zone_name_prefix -> (tier, level_min, level_max, danger)
ZONE_TIER_MAP = {}

def _build_map():
    """Populate ZONE_TIER_MAP from the tier lists above."""
    for zn in TIER_1_ZONES:
        ZONE_TIER_MAP[zn] = (1, 1, 5, "safe")
    for zn in TIER_2_ZONES:
        ZONE_TIER_MAP[zn] = (2, 6, 15, "caution")
    for zn in TIER_3_ZONES:
        ZONE_TIER_MAP[zn] = (3, 16, 40, "danger")
    for zn in TIER_4_ZONES:
        ZONE_TIER_MAP[zn] = (4, 41, 60, "deadly")
    for zn in TIER_5_ZONES:
        ZONE_TIER_MAP[zn] = (5, 61, 80, "deadly")

_build_map()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_zone_tier_for_name(zone_name):
    """
    Given a zone name string (e.g. "Rolling Plains of Aethelgard (5,10)"),
    return (tier, level_min, level_max, danger) or None if unknown.
    """
    for prefix, (tier, lmin, lmax, danger) in ZONE_TIER_MAP.items():
        if zone_name.startswith(prefix):
            return (tier, lmin, lmax, danger)
    return None


def get_zone_level_range(zone_name):
    """
    Convenience: return (level_min, level_max) for a zone name.
    """
    info = get_zone_tier_for_name(zone_name)
    if info:
        return (info[1], info[2])
    return (1, 5)  # safe fallback


def get_danger_level(zone_name):
    """
    Convenience: return the danger string ("safe"/"caution"/"danger"/"deadly")
    for a zone name. Defaults to "safe".
    """
    info = get_zone_tier_for_name(zone_name)
    if info:
        return info[3]
    return "safe"


def scale_mob_level(min_lvl, max_lvl, player_lvl=None):
    """
    Scale a mob level into the given zone range.

    Args:
        min_lvl: Minimum level for the zone.
        max_lvl: Maximum level for the zone.
        player_lvl: Optional player level to bias scaling toward.

    Returns a level clamped to [min_lvl, max_lvl].
    """
    import random
    if player_lvl is not None:
        base = max(min_lvl, min(max_lvl, player_lvl))
    else:
        base = (min_lvl + max_lvl) // 2
    return random.randint(min_lvl, max(base, min_lvl))


def should_be_aggressive(danger_level, base_aggro=True):
    """
    Determine if a mob should be aggressive based on danger level.

    "safe":     NEVER aggressive — mobs passive/defensive
    "caution":  respect base_aggro flag
    "danger":   ALWAYS aggressive
    "deadly":   ALWAYS aggressive

    Args:
        danger_level: One of "safe", "caution", "danger", "deadly".
        base_aggro: Default aggression flag (used for "caution" tier).

    Returns:
        bool: True if the mob should be aggressive.
    """
    if danger_level == "safe":
        return False
    if danger_level == "caution":
        return base_aggro
    return True  # "danger" or "deadly"
