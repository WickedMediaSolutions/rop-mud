"""
Global Weather Ticker for 'rop'.

A persistent background script that periodically updates the weather in
outdoor rooms across the realm.  Modeled after the announcement ticker in
`world/announcements.py`.

Weather state lives on each room's `ndb.current_weather` (non-persistent),
while this script handles the gradual transitions and notifies players in
affected rooms when the weather changes.
"""

import random

from evennia.scripts.scripts import DefaultScript
from evennia.objects.models import ObjectDB

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# How often (seconds) the ticker runs to re-evaluate weather transitions.
TICK_INTERVAL = 60

# Chance (0-1) that any given outdoor room transitions per tick.  This
# keeps weather changes from happening everywhere simultaneously.
TRANSITION_CHANCE = 0.35


class WeatherScript(DefaultScript):
    """
    Persistent global script that periodically advances room weather.

    Each tick, a fraction of outdoor rooms transition one step along their
    climate ladder, and players in rooms whose weather changed are notified.
    """

    def at_script_creation(self):
        """Set up the script on first creation."""
        self.key = "weather_script"
        self.desc = "Periodic realm-wide weather ticker"
        self.persistent = True
        self.interval = TICK_INTERVAL

    def at_repeat(self):
        """Advance weather for a subset of outdoor rooms."""
        from typeclasses.rooms import Room
        from world.weather import (
            format_weather_line,
            get_current_weather,
            is_weather_exempt,
            transition_weather,
        )

        rooms = [obj for obj in ObjectDB.objects.all() if isinstance(obj, Room)]
        if not rooms:
            return

        changed = []
        for room in rooms:
            if is_weather_exempt(room):
                continue

            # First tick: ensure every outdoor room has an initial weather.
            if get_current_weather(room) is None:
                from world.weather import pick_weather

                room.ndb.current_weather = pick_weather(room.get_display_name())

            if random.random() < TRANSITION_CHANCE:
                old = get_current_weather(room)
                new = transition_weather(room)
                if new and new != old:
                    changed.append(room)

        # Notify players in rooms whose weather changed.
        for room in changed:
            weather_line = format_weather_line(room)
            if not weather_line:
                continue
            for obj in room.contents:
                if obj.has_account:
                    obj.msg(weather_line)