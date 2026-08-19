"""
Achievements & Titles System for 'rop'
=======================================

Provides:
  - Achievement definitions with categories, tiers, and unlock conditions
  - Title rewards for completing achievements
  - Achievement tracking per character
  - Broadcast announcements for rare achievements
  - Achievement points and leaderboard integration

Design:
  - Achievements stored as character attribute: achievements (dict of key -> unlocked_at)
  - Active title stored as: active_title
  - Titles unlocked stored as: titles (list of strings)
  - Categories: Combat, Exploration, Crafting, Social, Collection, Challenge
  - Tiers: Bronze, Silver, Gold, Platinum, Legendary
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Achievement definitions
# ---------------------------------------------------------------------------

ACHIEVEMENTS = {
    # === Combat ===
    "first_blood": {
        "name": "First Blood",
        "desc": "Defeat your first enemy.",
        "category": "Combat",
        "tier": "Bronze",
        "points": 5,
        "title": None,
        "condition": {"kills": 1},
    },
    "seasoned_warrior": {
        "name": "Seasoned Warrior",
        "desc": "Defeat 100 enemies.",
        "category": "Combat",
        "tier": "Silver",
        "points": 20,
        "title": "the Seasoned",
        "condition": {"kills": 100},
    },
    "slayer": {
        "name": "Slayer",
        "desc": "Defeat 1,000 enemies.",
        "category": "Combat",
        "tier": "Gold",
        "points": 50,
        "title": "the Slayer",
        "condition": {"kills": 1000},
    },
    "legendary_slayer": {
        "name": "Legendary Slayer",
        "desc": "Defeat 10,000 enemies.",
        "category": "Combat",
        "tier": "Platinum",
        "points": 100,
        "title": "the Legendary Slayer",
        "condition": {"kills": 10000},
    },
    "boss_slayer": {
        "name": "Boss Slayer",
        "desc": "Defeat your first boss.",
        "category": "Combat",
        "tier": "Silver",
        "points": 25,
        "title": "the Boss Slayer",
        "condition": {"boss_kills": 1},
    },
    "dragon_slayer": {
        "name": "Dragon Slayer",
        "desc": "Defeat a dragon boss.",
        "category": "Combat",
        "tier": "Gold",
        "points": 75,
        "title": "the Dragon Slayer",
        "condition": {"dragon_kills": 1},
    },
    "undefeated": {
        "name": "Undefeated",
        "desc": "Win 50 consecutive battles without dying.",
        "category": "Combat",
        "tier": "Platinum",
        "points": 100,
        "title": "the Undefeated",
        "condition": {"consecutive_wins": 50},
    },
    "critical_master": {
        "name": "Critical Master",
        "desc": "Land 500 critical hits.",
        "category": "Combat",
        "tier": "Gold",
        "points": 50,
        "title": "the Critical",
        "condition": {"crits": 500},
    },

    # === Exploration ===
    "explorer": {
        "name": "Explorer",
        "desc": "Visit 50 unique rooms.",
        "category": "Exploration",
        "tier": "Bronze",
        "points": 10,
        "title": "the Explorer",
        "condition": {"rooms_visited": 50},
    },
    "cartographer": {
        "name": "Cartographer",
        "desc": "Visit 200 unique rooms.",
        "category": "Exploration",
        "tier": "Silver",
        "points": 25,
        "title": "the Cartographer",
        "condition": {"rooms_visited": 200},
    },
    "world_traveler": {
        "name": "World Traveler",
        "desc": "Visit 500 unique rooms.",
        "category": "Exploration",
        "tier": "Gold",
        "points": 50,
        "title": "the World Traveler",
        "condition": {"rooms_visited": 500},
    },
    "zone_master": {
        "name": "Zone Master",
        "desc": "Fully explore 10 zones.",
        "category": "Exploration",
        "tier": "Gold",
        "points": 50,
        "title": "the Zone Master",
        "condition": {"zones_explored": 10},
    },
    "portal_hopper": {
        "name": "Portal Hopper",
        "desc": "Use 25 portals.",
        "category": "Exploration",
        "tier": "Silver",
        "points": 20,
        "title": "the Portal Walker",
        "condition": {"portals_used": 25},
    },

    # === Crafting ===
    "apprentice_crafter": {
        "name": "Apprentice Crafter",
        "desc": "Reach level 25 in any tradeskill.",
        "category": "Crafting",
        "tier": "Bronze",
        "points": 10,
        "title": "the Apprentice",
        "condition": {"tradeskill_level": 25},
    },
    "master_crafter": {
        "name": "Master Crafter",
        "desc": "Reach level 75 in any tradeskill.",
        "category": "Crafting",
        "tier": "Silver",
        "points": 30,
        "title": "the Master Crafter",
        "condition": {"tradeskill_level": 75},
    },
    "grandmaster_crafter": {
        "name": "Grandmaster Crafter",
        "desc": "Reach level 100 in any tradeskill.",
        "category": "Crafting",
        "tier": "Gold",
        "points": 75,
        "title": "the Grandmaster",
        "condition": {"tradeskill_level": 100},
    },
    "jack_of_all_trades": {
        "name": "Jack of All Trades",
        "desc": "Reach level 50 in all 8 tradeskills.",
        "category": "Crafting",
        "tier": "Platinum",
        "points": 150,
        "title": "the Jack of All Trades",
        "condition": {"all_tradeskills_50": True},
    },
    "first_craft": {
        "name": "First Craft",
        "desc": "Successfully craft your first item.",
        "category": "Crafting",
        "tier": "Bronze",
        "points": 5,
        "title": None,
        "condition": {"items_crafted": 1},
    },
    "prolific_crafter": {
        "name": "Prolific Crafter",
        "desc": "Craft 500 items.",
        "category": "Crafting",
        "tier": "Gold",
        "points": 50,
        "title": "the Prolific",
        "condition": {"items_crafted": 500},
    },

    # === Social ===
    "social_butterfly": {
        "name": "Social Butterfly",
        "desc": "Send 100 messages on public channels.",
        "category": "Social",
        "tier": "Bronze",
        "points": 10,
        "title": "the Social",
        "condition": {"messages_sent": 100},
    },
    "party_leader": {
        "name": "Party Leader",
        "desc": "Lead 50 group adventures.",
        "category": "Social",
        "tier": "Silver",
        "points": 25,
        "title": "the Party Leader",
        "condition": {"groups_led": 50},
    },
    "mentor": {
        "name": "Mentor",
        "desc": "Help 10 new players reach level 10.",
        "category": "Social",
        "tier": "Gold",
        "points": 50,
        "title": "the Mentor",
        "condition": {"players_mentored": 10},
    },
    "clan_founder": {
        "name": "Clan Founder",
        "desc": "Found or lead a clan with 20+ members.",
        "category": "Social",
        "tier": "Gold",
        "points": 50,
        "title": "the Clan Lord",
        "condition": {"clan_members": 20},
    },

    # === Collection ===
    "gold_hoarder": {
        "name": "Gold Hoarder",
        "desc": "Accumulate 10,000 gold.",
        "category": "Collection",
        "tier": "Silver",
        "points": 20,
        "title": "the Wealthy",
        "condition": {"gold_accumulated": 10000},
    },
    "millionaire": {
        "name": "Millionaire",
        "desc": "Accumulate 1,000,000 gold.",
        "category": "Collection",
        "tier": "Platinum",
        "points": 100,
        "title": "the Millionaire",
        "condition": {"gold_accumulated": 1000000},
    },
    "collector": {
        "name": "Collector",
        "desc": "Collect 50 unique items.",
        "category": "Collection",
        "tier": "Silver",
        "points": 20,
        "title": "the Collector",
        "condition": {"unique_items": 50},
    },
    "mount_enthusiast": {
        "name": "Mount Enthusiast",
        "desc": "Own 3 different mounts.",
        "category": "Collection",
        "tier": "Silver",
        "points": 20,
        "title": "the Rider",
        "condition": {"mounts_owned": 3},
    },

    # === Challenge ===
    "survivor": {
        "name": "Survivor",
        "desc": "Survive with less than 5% HP.",
        "category": "Challenge",
        "tier": "Bronze",
        "points": 10,
        "title": "the Survivor",
        "condition": {"near_death_survives": 1},
    },
    "speed_runner": {
        "name": "Speed Runner",
        "desc": "Reach level 20 in under 4 hours of playtime.",
        "category": "Challenge",
        "tier": "Gold",
        "points": 75,
        "title": "the Swift",
        "condition": {"speed_level_20": True},
    },
    "pacifist": {
        "name": "Pacifist",
        "desc": "Reach level 30 with fewer than 50 kills.",
        "category": "Challenge",
        "tier": "Platinum",
        "points": 150,
        "title": "the Pacifist",
        "condition": {"pacifist_level_30": True},
    },
    "immortal": {
        "name": "Immortal",
        "desc": "Reach level 50 without dying once.",
        "category": "Challenge",
        "tier": "Legendary",
        "points": 250,
        "title": "the Immortal",
        "condition": {"no_death_level_50": True},
    },
    "lone_wolf": {
        "name": "Lone Wolf",
        "desc": "Solo defeat a boss intended for groups.",
        "category": "Challenge",
        "tier": "Legendary",
        "points": 200,
        "title": "the Lone Wolf",
        "condition": {"solo_boss_kill": True},
    },
}

# Achievement tiers and their display colors
TIER_COLORS = {
    "Bronze": "|y",
    "Silver": "|W",
    "Gold": "|Y",
    "Platinum": "|b",
    "Legendary": "|m",
}

# Categories
CATEGORIES = ["Combat", "Exploration", "Crafting", "Social", "Collection", "Challenge"]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_achievements(character: Any) -> Dict[str, float]:
    """Get a character's unlocked achievements dict."""
    try:
        return character.attributes.get("achievements", {})
    except Exception:
        return {}


def _get_titles(character: Any) -> List[str]:
    """Get a character's unlocked titles."""
    try:
        return character.attributes.get("titles", [])
    except Exception:
        return []


def _get_stats(character: Any) -> Dict[str, int]:
    """Get a character's achievement tracking stats."""
    try:
        return character.attributes.get("achievement_stats", {})
    except Exception:
        return {}


def _set_stats(character: Any, stats: Dict[str, int]) -> None:
    """Set a character's achievement tracking stats."""
    try:
        character.attributes.add("achievement_stats", stats)
    except Exception:
        pass


def _increment_stat(character: Any, stat_key: str, amount: int = 1) -> int:
    """Increment a tracking stat and return the new value."""
    stats = _get_stats(character)
    stats[stat_key] = stats.get(stat_key, 0) + amount
    _set_stats(character, stats)
    return stats[stat_key]


def _set_stat(character: Any, stat_key: str, value: int) -> None:
    """Set a tracking stat to a specific value."""
    stats = _get_stats(character)
    stats[stat_key] = value
    _set_stats(character, stats)


def _get_stat(character: Any, stat_key: str) -> int:
    """Get a tracking stat value."""
    return _get_stats(character).get(stat_key, 0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_achievement(character: Any, achievement_key: str) -> Tuple[bool, str]:
    """
    Check if a character meets the condition for an achievement.
    If so, unlock it and return (True, message).
    """
    if achievement_key not in ACHIEVEMENTS:
        return False, ""

    achievements = _get_achievements(character)
    if achievement_key in achievements:
        return False, ""  # Already unlocked

    ach = ACHIEVEMENTS[achievement_key]
    condition = ach["condition"]
    stats = _get_stats(character)

    # Check each condition
    for key, required in condition.items():
        current = stats.get(key, 0)
        if isinstance(required, bool):
            if not current:
                return False, ""
        elif current < required:
            return False, ""

    # Unlock!
    achievements[achievement_key] = time.time()
    try:
        character.attributes.add("achievements", achievements)
    except Exception:
        pass

    # Award title if applicable
    if ach["title"]:
        titles = _get_titles(character)
        if ach["title"] not in titles:
            titles.append(ach["title"])
            try:
                character.attributes.add("titles", titles)
            except Exception:
                pass

    # Award achievement points
    try:
        points = character.attributes.get("achievement_points", 0)
        character.attributes.add("achievement_points", points + ach["points"])
    except Exception:
        pass

    tier_color = TIER_COLORS.get(ach["tier"], "|w")
    msg = f"|Y*** ACHIEVEMENT UNLOCKED ***|n\n{tier_color}[{ach['tier']}] {ach['name']}|n\n{ach['desc']} (+{ach['points']} AP)"
    if ach["title"]:
        msg += f"\n|gTitle unlocked: {ach['title']}|n"

    return True, msg


def check_all_achievements(character: Any) -> List[str]:
    """
    Check all achievements against current stats.
    Returns list of unlock messages.
    """
    messages = []
    for key in ACHIEVEMENTS:
        ok, msg = check_achievement(character, key)
        if ok and msg:
            messages.append(msg)
    return messages


def track_kill(character: Any, is_boss: bool = False, is_dragon: bool = False) -> List[str]:
    """Track a kill for achievement purposes."""
    messages = []
    _increment_stat(character, "kills")
    if is_boss:
        _increment_stat(character, "boss_kills")
    if is_dragon:
        _increment_stat(character, "dragon_kills")

    # Check combat achievements
    for key in ["first_blood", "seasoned_warrior", "slayer", "legendary_slayer",
                "boss_slayer", "dragon_slayer"]:
        ok, msg = check_achievement(character, key)
        if ok and msg:
            messages.append(msg)
    return messages


def track_crit(character: Any) -> List[str]:
    """Track a critical hit."""
    _increment_stat(character, "crits")
    ok, msg = check_achievement(character, "critical_master")
    return [msg] if ok and msg else []


def track_room_visit(character: Any, room_id: int) -> List[str]:
    """Track a room visit."""
    messages = []
    # Track unique rooms via a set stored in stats
    stats = _get_stats(character)
    visited = stats.get("rooms_visited_set", "")
    visited_set = set(visited.split(",")) if visited else set()
    visited_set.add(str(room_id))
    stats["rooms_visited_set"] = ",".join(visited_set)
    stats["rooms_visited"] = len(visited_set)
    _set_stats(character, stats)

    for key in ["explorer", "cartographer", "world_traveler"]:
        ok, msg = check_achievement(character, key)
        if ok and msg:
            messages.append(msg)
    return messages


def track_craft(character: Any) -> List[str]:
    """Track a crafted item."""
    messages = []
    _increment_stat(character, "items_crafted")
    for key in ["first_craft", "prolific_crafter"]:
        ok, msg = check_achievement(character, key)
        if ok and msg:
            messages.append(msg)
    return messages


def track_tradeskill_level(character: Any, level: int) -> List[str]:
    """Track tradeskill level for achievements."""
    messages = []
    _set_stat(character, "tradeskill_level", max(_get_stat(character, "tradeskill_level"), level))
    for key in ["apprentice_crafter", "master_crafter", "grandmaster_crafter"]:
        ok, msg = check_achievement(character, key)
        if ok and msg:
            messages.append(msg)
    return messages


def track_gold(character: Any, total_gold: int) -> List[str]:
    """Track gold accumulation."""
    messages = []
    _set_stat(character, "gold_accumulated", max(_get_stat(character, "gold_accumulated"), total_gold))
    for key in ["gold_hoarder", "millionaire"]:
        ok, msg = check_achievement(character, key)
        if ok and msg:
            messages.append(msg)
    return messages


def track_near_death(character: Any) -> List[str]:
    """Track surviving near-death."""
    _increment_stat(character, "near_death_survives")
    ok, msg = check_achievement(character, "survivor")
    return [msg] if ok and msg else []


def get_achievement_list(character: Any) -> List[Dict]:
    """Get all achievements with unlock status for a character."""
    unlocked = _get_achievements(character)
    result = []
    for key, ach in ACHIEVEMENTS.items():
        result.append({
            "key": key,
            "name": ach["name"],
            "desc": ach["desc"],
            "category": ach["category"],
            "tier": ach["tier"],
            "points": ach["points"],
            "title": ach["title"],
            "unlocked": key in unlocked,
            "unlocked_at": unlocked.get(key, None),
        })
    return sorted(result, key=lambda a: (a["category"], a["tier"], a["name"]))


def get_achievement_points(character: Any) -> int:
    """Get total achievement points."""
    try:
        return character.attributes.get("achievement_points", 0)
    except Exception:
        return 0


def get_active_title(character: Any) -> Optional[str]:
    """Get the character's active title."""
    try:
        return character.attributes.get("active_title", None)
    except Exception:
        return None


def set_active_title(character: Any, title: str) -> Tuple[bool, str]:
    """Set the character's active title."""
    titles = _get_titles(character)
    if title not in titles:
        return False, f"You haven't unlocked the title '{title}'."
    try:
        character.attributes.add("active_title", title)
    except Exception:
        pass
    return True, f"Your title is now: |Y{title}|n"


def clear_title(character: Any) -> Tuple[bool, str]:
    """Clear the character's active title."""
    try:
        character.attributes.add("active_title", None)
    except Exception:
        pass
    return True, "Your title has been cleared."


def get_unlocked_titles(character: Any) -> List[str]:
    """Get all unlocked titles."""
    return _get_titles(character)