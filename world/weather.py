"""
Weather Engine for 'rop'.

Provides zone-aware weather states, transition logic, and formatting
helpers used by the Room typeclass and by the global weather ticker.

Currency/zone reimplementation notes:
  - Weather is stored per-room on `room.ndb.current_weather`. This is
    non-persistent so a reload starts fresh with no stale state.
  - Indoor rooms (tag `indoor` or attribute `indoor`/`safe_zone`) and
    rooms with no sky are excluded from weather entirely.
  - Zone weighting uses `world.zone_levels.get_zone_tier_for_name`.
"""

import random

# ---------------------------------------------------------------------------
# Weather states
# ---------------------------------------------------------------------------

# Each state carries a display icon (emoji) and an ANSI colour for its label.
WEATHER_STATES = {
    "clear":        {"label": "Clear",         "icon": "☀", "color": "|Y"},
    "overcast":     {"label": "Overcast",      "icon": "☁", "color": "|W"},
    "light_rain":   {"label": "Light Rain",    "icon": "🌦", "color": "|c"},
    "heavy_rain":   {"label": "Heavy Rain",    "icon": "🌧", "color": "|b"},
    "thunderstorm": {"label": "Thunderstorm",  "icon": "⛈", "color": "|M"},
    "windy":        {"label": "Windy",         "icon": "🌬", "color": "|w"},
    "fog":          {"label": "Foggy",         "icon": "🌫", "color": "|W"},
    "light_snow":   {"label": "Light Snow",    "icon": "🌨", "color": "|c"},
    "heavy_snow":   {"label": "Heavy Snow",    "icon": "❄", "color": "|C"},
    "blizzard":     {"label": "Blizzard",      "icon": "🌨", "color": "|C"},
    "heat_wave":    {"label": "Heat Wave",     "icon": "☀", "color": "|r"},
}

# Ordered intensity ladder.  Weather drifts one step at a time through
# these adjacent states rather than jumping wildly (e.g. Clear -> Overcast
# -> Light Rain -> Heavy Rain -> Thunderstorm).
INTENSITY_LADDER = [
    "clear",
    "overcast",
    "light_rain",
    "heavy_rain",
    "thunderstorm",
]

# Cold-weather ladder (snowy zones).
COLD_LADDER = [
    "clear",
    "overcast",
    "light_snow",
    "heavy_snow",
    "blizzard",
]

# Neutral states that can appear anywhere.
NEUTRAL_STATES = ["clear", "overcast", "windy", "fog"]


# ---------------------------------------------------------------------------
# Zone weighting
# ---------------------------------------------------------------------------

# Each zone "climate" favours a given base ladder and a set of neutral states.
# Keys are substrings matched against the room name.  Order matters: first
# match wins, so place more specific keys before generic ones.
ZONE_CLIMATES = [
    # Snowy mountains / northern coasts
    ("Highland", "cold"),
    ("Pines", "cold"),
    ("Dusk", "cold"),
    ("Snow", "cold"),
    ("Frost", "cold"),
    ("Silverpine", "cold"),
    # Deserts / arid
    ("Scorched", "desert"),
    ("Dunes", "desert"),
    ("Desert", "desert"),
    ("Mesas", "desert"),
    ("Oasis", "desert"),
    ("Salt Flats", "desert"),
    ("Blasted Heath", "desert"),
    ("Molten Scar", "desert"),
    ("Ashen", "desert"),
    # Wetlands / coasts
    ("Marsh", "wet"),
    ("Fen", "wet"),
    ("Coast", "wet"),
    ("Shore", "coastal"),
    ("Beach", "coastal"),
    ("Lake", "wet"),
    # Forest / green
    ("Forest", "temperate"),
    ("Grove", "temperate"),
    ("Glade", "temperate"),
    ("Verdant", "temperate"),
    ("Farm", "temperate"),
    ("Plains", "temperate"),
    ("Meadow", "temperate"),
    ("Hills", "temperate"),
]

# Climate -> (base_ladder, neutral_states, weights)
# Weights apply to the base ladder choices.
CLIMATES = {
    "cold": {
        "ladder": COLD_LADDER,
        "neutrals": ["clear", "overcast", "windy", "fog"],
        "weights": [3, 3, 2, 2, 1],
    },
    "desert": {
        "ladder": ["clear", "clear", "heat_wave", "windy", "overcast"],
        "neutrals": ["clear", "heat_wave", "windy", "overcast"],
        "weights": [5, 2, 2, 1, 1],
    },
    "wet": {
        "ladder": ["clear", "overcast", "light_rain", "heavy_rain", "thunderstorm"],
        "neutrals": ["clear", "overcast", "fog", "windy"],
        "weights": [2, 3, 3, 2, 1],
    },
    "coastal": {
        "ladder": ["clear", "overcast", "windy", "light_rain", "heavy_rain"],
        "neutrals": ["clear", "overcast", "windy", "fog"],
        "weights": [3, 2, 2, 2, 1],
    },
    "temperate": {
        "ladder": INTENSITY_LADDER,
        "neutrals": ["clear", "overcast", "windy", "fog"],
        "weights": [4, 3, 2, 1, 1],
    },
}

# Default climate for zones that don't match anything.
DEFAULT_CLIMATE = "temperate"


def get_climate(room_name):
    """
    Return the climate key for a room based on its display name.

    Args:
        room_name (str): The room's name (key or display name).

    Returns:
        str: One of the CLIMATES keys.
    """
    name = room_name or ""
    for needle, climate in ZONE_CLIMATES:
        if needle.lower() in name.lower():
            return climate
    return DEFAULT_CLIMATE


def pick_weather(room_name, rng=None):
    """
    Pick a new weather state for a room based on its zone climate.

    Args:
        room_name (str): Room display name used for climate lookup.
        rng (random.Random, optional): Inject a seeded RNG for tests.

    Returns:
        str: A key from WEATHER_STATES.
    """
    rng = rng or random
    climate = CLIMATES[get_climate(room_name)]
    ladder = climate["ladder"]
    weights = climate["weights"][: len(ladder)]

    # Mostly pick from the climate's base ladder, occasionally a neutral.
    if rng.random() < 0.8:
        return rng.choices(ladder, weights=weights, k=1)[0]
    return rng.choice(climate["neutrals"])


def is_weather_exempt(room):
    """
    Return True if the room should not receive weather (indoor/safe zones).
    """
    if not room:
        return True
    if getattr(room, "db", None) is None:
        return True

    if room.db.safe_zone:
        return True
    if room.attributes.get("indoor", default=False):
        return True
    if room.tags.has("indoor"):
        return True
    return False


def get_current_weather(room):
    """
    Return the current weather key for a room.

    If the room is weather-exempt, returns None.  If no weather has been
    rolled yet for this room, roll one now and cache it on ndb.
    """
    if is_weather_exempt(room):
        return None

    current = getattr(room, "ndb", None) and room.ndb.current_weather
    if current in WEATHER_STATES:
        return current

    # Roll and cache a fresh state.
    name = room.get_display_name() if hasattr(room, "get_display_name") else room.key
    state = pick_weather(name)
    if getattr(room, "ndb", None) is not None:
        room.ndb.current_weather = state
    return state


def transition_weather(room):
    """
    Shift a room's weather one step along its climate ladder.

    Used by the global ticker so weather changes gradually instead of
    jumping to an unrelated state.  Returns the new weather key.
    """
    if is_weather_exempt(room):
        return None

    name = room.get_display_name() if hasattr(room, "get_display_name") else room.key
    climate = CLIMATES[get_climate(name)]
    ladder = climate["ladder"]

    current = get_current_weather(room)
    if current in ladder:
        idx = ladder.index(current)
        # Random walk: stay, step up, or step down (when possible).
        offset = random.choice(
            [o for o in (-1, 0, 1) if 0 <= idx + o < len(ladder)]
        )
        new_state = ladder[idx + offset]
    else:
        # Current state is a neutral; roll a fresh base-ladder state.
        new_state = pick_weather(name)

    if getattr(room, "ndb", None) is not None:
        room.ndb.current_weather = new_state
    return new_state


def format_weather_line(room):
    """
    Format a single-line weather description for a room, or "" if the room
    is weather-exempt or has no weather.

    Example:
        "|WThe sky is |Y☀ Clear|W.|n"
    """
    state = get_current_weather(room)
    if not state or state not in WEATHER_STATES:
        return ""

    data = WEATHER_STATES[state]
    return f"|WThe sky is {data['color']}{data['icon']} {data['label']}|W.|n"


def format_weather_short(room):
    """
    Format a compact weather segment suitable for the character status
    prompt, or "" if no weather.

    Example:
        "|W[☀ Clear]|n"
    """
    state = get_current_weather(room)
    if not state or state not in WEATHER_STATES:
        return ""

    data = WEATHER_STATES[state]
    return f"{data['color']}[{data['icon']} {data['label']}]|n"