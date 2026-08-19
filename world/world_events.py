"""
World Events System for 'rop'
===============================
Provides timed and scheduled world events:
  - Invasions (mob hordes attacking faction hubs)
  - Double-XP weekends
  - Double-gold events
  - Holiday/seasonal events
  - Boss rush events
  - World announcements

Usage:
  from world.world_events import WorldEventManager, EventScheduler
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from evennia import create_object, search_object
    from evennia.objects.models import ObjectDB
except Exception:
    create_object = None
    search_object = None
    ObjectDB = None


# ===========================================================================
# EVENT TYPES
# ===========================================================================

class WorldEvent:
    """Represents a single world event instance."""

    EVENT_TYPES = {
        "invasion": {
            "name": "Realm Invasion",
            "duration": 600,  # 10 minutes
            "xp_multiplier": 1.0,
            "gold_multiplier": 1.0,
            "description": "Enemy hordes invade the realm! Defend your faction hub!",
        },
        "double_xp": {
            "name": "Double XP Weekend",
            "duration": 172800,  # 48 hours
            "xp_multiplier": 2.0,
            "gold_multiplier": 1.0,
            "description": "All XP gains are doubled! Level up faster!",
        },
        "double_gold": {
            "name": "Golden Hour",
            "duration": 3600,  # 1 hour
            "xp_multiplier": 1.0,
            "gold_multiplier": 2.0,
            "description": "All gold drops are doubled! Get rich quick!",
        },
        "holiday": {
            "name": "Festival of Light",
            "duration": 86400,  # 24 hours
            "xp_multiplier": 1.25,
            "gold_multiplier": 1.25,
            "description": "The Festival of Light is here! Enjoy bonus XP and gold!",
        },
        "boss_rush": {
            "name": "Boss Rush",
            "duration": 3600,  # 1 hour
            "xp_multiplier": 1.5,
            "gold_multiplier": 1.5,
            "description": "All bosses have reduced respawn and drop better loot!",
        },
    }

    def __init__(self, event_id: str, event_type: str,
                 start_time: Optional[float] = None):
        self.event_id = event_id
        self.event_type = event_type
        self.config = self.EVENT_TYPES.get(event_type, self.EVENT_TYPES["double_xp"])
        self.start_time = start_time or time.time()
        self.end_time = self.start_time + self.config["duration"]
        self.status = "scheduled"  # scheduled, active, completed, cancelled
        self.announced = False
        self.invasion_mobs: List[Any] = []
        self.participants: Set[int] = set()  # dbrefs of participants

    @property
    def is_active(self) -> bool:
        return self.status == "active" and time.time() <= self.end_time

    @property
    def is_expired(self) -> bool:
        return time.time() > self.end_time

    @property
    def time_remaining(self) -> int:
        return max(0, int(self.end_time - time.time()))

    @property
    def time_remaining_str(self) -> str:
        remaining = self.time_remaining
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        seconds = remaining % 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    @property
    def xp_multiplier(self) -> float:
        return self.config["xp_multiplier"]

    @property
    def gold_multiplier(self) -> float:
        return self.config["gold_multiplier"]

    @property
    def name(self) -> str:
        return self.config["name"]

    @property
    def description(self) -> str:
        return self.config["description"]

    def start(self) -> str:
        """Start the event."""
        self.status = "active"
        self.start_time = time.time()
        self.end_time = time.time() + self.config["duration"]
        self._announce_start()
        return f"|Y|h[WORLD EVENT] {self.name} has begun!|n {self.description}"

    def end(self) -> str:
        """End the event."""
        self.status = "completed"
        self._cleanup_invasion_mobs()
        self._announce_end()
        return f"|y[WORLD EVENT] {self.name} has ended.|n"

    def cancel(self) -> str:
        """Cancel the event."""
        self.status = "cancelled"
        self._cleanup_invasion_mobs()
        return f"|y[WORLD EVENT] {self.name} has been cancelled.|n"

    def _announce_start(self) -> None:
        """Broadcast event start to all players."""
        try:
            from typeclasses.characters import Character
            for char in ObjectDB.objects.all():
                if isinstance(char, Character) and char.sessions.count() > 0:
                    char.msg(
                        f"|Y|h{'=' * 60}|n\n"
                        f"|Y|h  WORLD EVENT: {self.name.upper()}|n\n"
                        f"|w{self.description}|n\n"
                        f"|wDuration: {self.time_remaining_str}|n\n"
                        f"|Y|h{'=' * 60}|n"
                    )
        except Exception:
            pass

    def _announce_end(self) -> None:
        """Broadcast event end to all players."""
        try:
            from typeclasses.characters import Character
            for char in ObjectDB.objects.all():
                if isinstance(char, Character) and char.sessions.count() > 0:
                    char.msg(f"|y[WORLD EVENT] {self.name} has ended.|n")
        except Exception:
            pass

    def _cleanup_invasion_mobs(self) -> None:
        """Remove invasion mobs when the event ends."""
        for mob in self.invasion_mobs:
            try:
                if hasattr(mob, "delete"):
                    mob.delete()
            except Exception:
                pass
        self.invasion_mobs = []

    def spawn_invasion_mobs(self, count: int = 20, level_range: Tuple[int, int] = (15, 35)) -> int:
        """
        Spawn invasion mobs for invasion-type events.

        Returns:
            Number of mobs spawned.
        """
        if self.event_type != "invasion":
            return 0

        spawned = 0
        try:
            from world.mob_ai import spawn_mob
            from evennia import search_tag

            # Find faction hub rooms to spawn near
            hub_rooms = []
            for hub_key in ["Sunspire Keep (Starter Hub)", "Brimstone Keep (Starter Hub)"]:
                rooms = search_object(hub_key)
                for room in rooms:
                    if room is not None:
                        hub_rooms.append(room)

            if not hub_rooms:
                return 0

            mob_names = ["Invading Orc", "Raiding Goblin", "Marauding Bandit",
                         "Infiltrating Assassin", "Siege Beast", "War Troll"]
            factions = ["Gorgoroth Horde", "Aethelgard Alliance"]

            for _ in range(count):
                room = random.choice(hub_rooms)
                mob_name = random.choice(mob_names)
                level = random.randint(level_range[0], level_range[1])
                faction = random.choice(factions)

                mob = spawn_mob(room, name=mob_name, level=level,
                                faction=faction, aggro=True)
                if mob:
                    mob.attributes.add("is_invasion_mob", True)
                    mob.attributes.add("invasion_event_id", self.event_id)
                    self.invasion_mobs.append(mob)
                    spawned += 1

            # Announce to nearby rooms
            if spawned > 0:
                self._announce_invasion_start(spawned)
        except Exception:
            pass

        return spawned

    def _announce_invasion_start(self, count: int) -> None:
        """Announce invasion start."""
        try:
            from typeclasses.characters import Character
            for char in ObjectDB.objects.all():
                if isinstance(char, Character) and char.sessions.count() > 0:
                    char.msg(
                        f"|R|h[INVASION] {count} enemy forces have entered the realm! "
                        f"Defend your faction hub!|n"
                    )
        except Exception:
            pass


# ===========================================================================
# WORLD EVENT MANAGER
# ===========================================================================

class WorldEventManager:
    """
    Manages all world events.

    Features:
      - Auto-scheduling of events
      - XP/gold multiplier tracking
      - Event participation tracking
      - Holiday calendar
    """

    def __init__(self):
        self._events: Dict[str, WorldEvent] = {}
        self._active_event_types: Set[str] = set()
        self._scheduler: List[Dict[str, Any]] = []
        self._holidays: Dict[str, Dict[str, Any]] = {}

    # ---- Holiday Calendar ----

    def register_holiday(self, holiday_id: str, name: str, month: int, day: int,
                         duration_hours: int = 24, xp_mult: float = 1.25,
                         gold_mult: float = 1.25) -> None:
        """Register a recurring holiday."""
        self._holidays[holiday_id] = {
            "name": name,
            "month": month,
            "day": day,
            "duration_hours": duration_hours,
            "xp_multiplier": xp_mult,
            "gold_multiplier": gold_mult,
        }

    def check_holidays(self, now: float) -> List[str]:
        """
        Check if any holidays should be active today.

        Returns:
            List of holiday IDs that should be active.
        """
        from datetime import datetime
        dt = datetime.fromtimestamp(now)
        active = []
        for holiday_id, config in self._holidays.items():
            if config["month"] == dt.month and config["day"] == dt.day:
                active.append(holiday_id)
        return active

    # ---- Event Management ----

    def create_event(self, event_type: str, start_time: Optional[float] = None) -> Tuple[Optional[WorldEvent], str]:
        """
        Create and schedule a world event.

        Args:
            event_type: One of "invasion", "double_xp", "double_gold", "holiday", "boss_rush".
            start_time: Optional start timestamp. If None, starts immediately.

        Returns:
            (event, message)
        """
        if event_type not in WorldEvent.EVENT_TYPES:
            return None, f"Invalid event type: {event_type}"

        # Check if same type is already active
        if event_type in self._active_event_types:
            return None, f"A {WorldEvent.EVENT_TYPES[event_type]['name']} is already active."

        event_id = f"event_{uuid_str()}"
        event = WorldEvent(event_id, event_type, start_time)

        self._events[event_id] = event

        if start_time is None or start_time <= time.time():
            event.start()
            self._active_event_types.add(event_type)
            # Trigger special handling for invasion
            if event_type == "invasion":
                event.spawn_invasion_mobs()
            return event, f"{event.name} has started!"
        else:
            return event, f"{event.name} scheduled for {start_time}."

    def cancel_event(self, event_id: str) -> Tuple[bool, str]:
        """Cancel a scheduled or active event."""
        event = self._events.get(event_id)
        if not event:
            return False, "Event not found."

        if event.status not in ("scheduled", "active"):
            return False, "Event cannot be cancelled."

        msg = event.cancel()
        self._active_event_types.discard(event.event_type)
        return True, msg

    def get_event(self, event_id: str) -> Optional[WorldEvent]:
        """Get an event by ID."""
        return self._events.get(event_id)

    def get_active_events(self) -> List[WorldEvent]:
        """Get all currently active events."""
        return [e for e in self._events.values() if e.is_active]

    def list_events(self) -> List[Dict[str, Any]]:
        """List all events (active, scheduled, completed)."""
        result = []
        for event in self._events.values():
            result.append({
                "event_id": event.event_id,
                "type": event.event_type,
                "name": event.name,
                "status": event.status,
                "time_remaining": event.time_remaining if event.status == "active" else None,
                "xp_multiplier": event.xp_multiplier,
                "gold_multiplier": event.gold_multiplier,
            })
        return result

    def get_active_xp_multiplier(self) -> float:
        """Get combined XP multiplier from all active events."""
        multiplier = 1.0
        for event in self.get_active_events():
            multiplier *= event.xp_multiplier
        return multiplier

    def get_active_gold_multiplier(self) -> float:
        """Get combined gold multiplier from all active events."""
        multiplier = 1.0
        for event in self.get_active_events():
            multiplier *= event.gold_multiplier
        return multiplier

    def register_participant(self, character: Any, event_id: str) -> None:
        """Track a participant in an event."""
        event = self._events.get(event_id)
        if event and event.is_active:
            event.participants.add(character.id)

    def get_event_participants(self, event_id: str) -> int:
        """Get participant count for an event."""
        event = self._events.get(event_id)
        if event:
            return len(event.participants)
        return 0

    def cleanup_expired(self) -> int:
        """End expired events and clean up. Returns count ended."""
        count = 0
        for event_id in list(self._events.keys()):
            event = self._events[event_id]
            if event.status == "active" and event.is_expired:
                event.end()
                self._active_event_types.discard(event.event_type)
                count += 1
            elif event.status == "scheduled" and event.start_time <= time.time():
                event.start()
                self._active_event_types.add(event.event_type)
                if event.event_type == "invasion":
                    event.spawn_invasion_mobs()
                count += 1
            elif event.status in ("completed", "cancelled") and event.is_expired:
                # Remove old events after 1 hour
                if time.time() - event.end_time > 3600:
                    del self._events[event_id]
        return count

    # ---- Random Event Scheduling ----

    def schedule_random_event(self, min_interval_hours: float = 4,
                              max_interval_hours: float = 12) -> Optional[WorldEvent]:
        """
        Schedule a random world event within a time interval.

        Returns:
            The scheduled event, or None.
        """
        event_types = list(WorldEvent.EVENT_TYPES.keys())
        # Don't schedule duplicate active events
        available = [t for t in event_types if t not in self._active_event_types]
        if not available:
            return None

        event_type = random.choice(available)
        # Random delay
        delay = random.uniform(min_interval_hours, max_interval_hours) * 3600
        start_time = time.time() + delay

        event, _ = self.create_event(event_type, start_time)
        return event

    def auto_start_random_event(self) -> Optional[WorldEvent]:
        """Immediately start a random event (for admin/testing)."""
        event_types = ["invasion", "double_xp", "double_gold", "boss_rush"]
        available = [t for t in event_types if t not in self._active_event_types]
        if not available:
            return None

        event_type = random.choice(available)
        event, _ = self.create_event(event_type)
        return event


def uuid_str() -> str:
    """Generate a short unique string."""
    import uuid
    return uuid.uuid4().hex[:8]


# Global world event manager
world_event_manager = WorldEventManager()


# ===========================================================================
# DEFAULT HOLIDAYS
# ===========================================================================

def register_default_holidays():
    """Register the default holiday calendar."""
    world_event_manager.register_holiday(
        "new_year", "New Year's Celebration", 1, 1, 24, 2.0, 2.0
    )
    world_event_manager.register_holiday(
        "spring_festival", "Spring Festival", 3, 21, 24, 1.5, 1.25
    )
    world_event_manager.register_holiday(
        "summer_solstice", "Summer Solstice", 6, 21, 24, 1.25, 1.5
    )
    world_event_manager.register_holiday(
        "harvest_festival", "Harvest Festival", 9, 22, 24, 1.5, 1.5
    )
    world_event_manager.register_holiday(
        "halloween", "Night of Shadows", 10, 31, 24, 1.5, 2.0
    )
    world_event_manager.register_holiday(
        "winter_festival", "Winter Festival", 12, 21, 24, 2.0, 1.5
    )
    return list(world_event_manager._holidays.keys())