"""
Day / Night Cycle System for 'rop'
===================================

Provides:
  - Global time-of-day tracking with dawn/day/dusk/night phases
  - Light level affecting visibility, spawn rates, and NPC behavior
  - Room darkness calculation (indoor vs outdoor)
  - Weather interaction (cloudy nights darker)
  - Time-based shop hours and NPC schedules

Design:
  - Time stored as a single global attribute: game_time (seconds since epoch)
  - DAY_LENGTH = 2 hours real time (7200s) = one full game day
  - Phases: dawn (5%), day (40%), dusk (5%), night (50%)
  - LIGHT_LEVELS: 0 (pitch black) to 100 (full daylight)
  - Outdoor rooms get dynamic light; indoor rooms fixed light
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Game day length in real seconds (2 hours = 1 game day)
DAY_LENGTH_SECONDS = 7200

# Phase durations as fraction of day
DAWN_FRACTION = 0.05
DAY_FRACTION = 0.40
DUSK_FRACTION = 0.05
NIGHT_FRACTION = 0.50  # remainder

# Phase names
PHASE_DAWN = "dawn"
PHASE_DAY = "day"
PHASE_DUSK = "dusk"
PHASE_NIGHT = "night"

# Light levels per phase
LIGHT_LEVELS = {
    PHASE_DAWN: 50,
    PHASE_DAY: 100,
    PHASE_DUSK: 40,
    PHASE_NIGHT: 10,
}

# Moon phases (affect night light)
MOON_PHASES = ["new_moon", "waxing_crescent", "first_quarter", "waxing_gibbous",
               "full_moon", "waning_gibbous", "last_quarter", "waning_crescent"]

# Moon light bonus (added to night light)
MOON_LIGHT_BONUS = {
    "new_moon": 0,
    "waxing_crescent": 3,
    "first_quarter": 6,
    "waxing_gibbous": 10,
    "full_moon": 15,
    "waning_gibbous": 10,
    "last_quarter": 6,
    "waning_crescent": 3,
}

# Visibility thresholds
LIGHT_DARK_THRESHOLD = 25
LIGHT_DIM_THRESHOLD = 50
LIGHT_BRIGHT_THRESHOLD = 80

# NPC behavior modifiers by phase
SPAWN_RATE_MODIFIERS = {
    PHASE_DAWN: 0.8,
    PHASE_DAY: 1.0,
    PHASE_DUSK: 1.2,
    PHASE_NIGHT: 1.5,  # more dangerous mobs at night
}

# Shop hours
SHOP_OPEN_HOUR = 6   # 6am game time
SHOP_CLOSE_HOUR = 22  # 10pm game time


# ---------------------------------------------------------------------------
# Global time helpers
# ---------------------------------------------------------------------------

def _get_global_time(container: Any = None) -> float:
    """Get the global game time. Falls back to real time if not set."""
    try:
        if container is not None and hasattr(container, "attributes"):
            gt = container.attributes.get("game_time", None)
            if gt is not None:
                return float(gt)
    except Exception:
        pass
    # Fallback: derive from real time
    return time.time()


def _set_global_time(container: Any, game_time: float) -> None:
    """Set the global game time."""
    try:
        container.attributes.add("game_time", game_time)
    except Exception:
        pass


def get_game_time(container: Any = None) -> float:
    """Get the current game time (seconds since game epoch)."""
    return _get_global_time(container)


def get_day_progress(container: Any = None) -> float:
    """Get progress through the current game day (0.0 to 1.0)."""
    game_time = _get_global_time(container)
    return (game_time % DAY_LENGTH_SECONDS) / DAY_LENGTH_SECONDS


def get_time_of_day(container: Any = None) -> str:
    """Get the current phase of day: dawn, day, dusk, or night."""
    progress = get_day_progress(container)

    if progress < DAWN_FRACTION:
        return PHASE_DAWN
    elif progress < DAWN_FRACTION + DAY_FRACTION:
        return PHASE_DAY
    elif progress < DAWN_FRACTION + DAY_FRACTION + DUSK_FRACTION:
        return PHASE_DUSK
    else:
        return PHASE_NIGHT


def get_moon_phase(container: Any = None) -> str:
    """Get the current moon phase."""
    game_time = _get_global_time(container)
    # One moon cycle = 28 game days
    moon_cycle = 28 * DAY_LENGTH_SECONDS
    progress = (game_time % moon_cycle) / moon_cycle
    index = int(progress * len(MOON_PHASES)) % len(MOON_PHASES)
    return MOON_PHASES[index]


def get_game_hour(container: Any = None) -> int:
    """Get the current game hour (0-23)."""
    progress = get_day_progress(container)
    return int(progress * 24) % 24


def get_game_minute(container: Any = None) -> int:
    """Get the current game minute (0-59)."""
    progress = get_day_progress(container)
    return int(progress * 24 * 60) % 60


# ---------------------------------------------------------------------------
# Light levels
# ---------------------------------------------------------------------------

def get_light_level(container: Any = None) -> int:
    """Get the current ambient light level (0-100)."""
    phase = get_time_of_day(container)
    light = LIGHT_LEVELS.get(phase, 100)

    # Moon bonus at night
    if phase == PHASE_NIGHT:
        moon = get_moon_phase(container)
        light += MOON_LIGHT_BONUS.get(moon, 0)

    return max(0, min(100, light))


def get_room_light(room: Any, container: Any = None) -> int:
    """
    Get the light level for a specific room, accounting for indoor/outdoor.

    Outdoor rooms use ambient light; indoor rooms use their own light source
    (torches, lanterns, etc.) or fixed illumination.
    """
    try:
        is_outdoor = room.attributes.get("outdoor", True)
    except Exception:
        is_outdoor = True

    if is_outdoor:
        # Weather can reduce light
        ambient = get_light_level(container)
        try:
            from world.weather import get_current_weather
            weather = get_current_weather(room)
            if weather and weather.get("cloudy"):
                ambient = int(ambient * 0.7)
            if weather and weather.get("stormy"):
                ambient = int(ambient * 0.5)
        except Exception:
            pass
        return ambient

    # Indoor — check for room light source
    try:
        light = room.attributes.get("light_level", None)
        if light is not None:
            return int(light)
    except Exception:
        pass

    # Default indoor light (torch-lit)
    return 60


def get_visibility_text(light: int) -> str:
    """Get a textual description of visibility based on light level."""
    if light <= 0:
        return "pitch black"
    elif light <= LIGHT_DARK_THRESHOLD:
        return "very dark"
    elif light <= LIGHT_DIM_THRESHOLD:
        return "dim"
    elif light <= LIGHT_BRIGHT_THRESHOLD:
        return "bright"
    else:
        return "full daylight"


def get_light_description(room: Any, container: Any = None) -> str:
    """Get a colored description of the room's current light level."""
    light = get_room_light(room, container)
    visibility = get_visibility_text(light)
    phase = get_time_of_day(container)

    color = "|w"
    if light <= 0:
        color = "|D"
    elif light <= LIGHT_DARK_THRESHOLD:
        color = "|d"
    elif light <= LIGHT_DIM_THRESHOLD:
        color = "|w"
    elif light <= LIGHT_BRIGHT_THRESHOLD:
        color = "|Y"
    else:
        color = "|W"

    phase_colors = {
        PHASE_DAWN: "|y",
        PHASE_DAY: "|Y",
        PHASE_DUSK: "|m",
        PHASE_NIGHT: "|b",
    }
    phase_color = phase_colors.get(phase, "|w")

    return f"It is {phase_color}{phase}{phase_color} and {color}{visibility}{color} here."


# ---------------------------------------------------------------------------
# Gameplay modifiers
# ---------------------------------------------------------------------------

def get_spawn_rate_modifier(container: Any = None) -> float:
    """Get the mob spawn rate modifier for the current phase."""
    phase = get_time_of_day(container)
    return SPAWN_RATE_MODIFIERS.get(phase, 1.0)


def is_shop_open(container: Any = None) -> bool:
    """Check if shops are currently open based on game time."""
    hour = get_game_hour(container)
    return SHOP_OPEN_HOUR <= hour < SHOP_CLOSE_HOUR


def get_night_bonuses(container: Any = None) -> Dict[str, float]:
    """
    Get gameplay modifiers for the current phase.

    Night: stealth +20%, shadow damage +10%
    Dawn: stamina regen +10%
    Day: max visibility (no modifiers)
    Dusk: crit chance +5%
    """
    phase = get_time_of_day(container)
    bonuses = {}

    if phase == PHASE_NIGHT:
        bonuses["stealth_efficiency_pct"] = 20.0
        bonuses["shadow_damage_pct"] = 10.0
    elif phase == PHASE_DAWN:
        bonuses["stamina_regen_pct"] = 10.0
    elif phase == PHASE_DUSK:
        bonuses["crit_chance_pct"] = 5.0

    return bonuses


def format_time(container: Any = None) -> str:
    """Format the current game time as a display string."""
    hour = get_game_hour(container)
    minute = get_game_minute(container)
    phase = get_time_of_day(container)
    moon = get_moon_phase(container).replace("_", " ").title()

    ampm = "AM" if hour < 12 else "PM"
    hour_12 = hour % 12
    if hour_12 == 0:
        hour_12 = 12

    return f"{hour_12}:{minute:02d} {ampm} | {phase.title()} | Moon: {moon}"