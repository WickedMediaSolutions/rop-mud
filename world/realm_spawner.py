"""
Realm-Wide Mob Respawn Ticker & Room Population Caps for 'rop'
===============================================================

A persistent Evennia Script that drives the entire realm's mob respawn
cycle.  Every 5 seconds it iterates all rooms that have a ``spawn_table``
and tops them up to their ``max_mobs`` cap.

Key behaviours:
  - XP mobs: respawn every 5 ticks (fast loop) provided the room is under
    its ``max_mobs`` limit.
  - Boss mobs: enforce a strict 1-hour (3600-second) cooldown from the
    moment of death.  Bosses completely ignore the fast 5-tick loop.
  - Newbie zones (``brimstone_courtyard`` and ``sunspire_meadows``) are
    force-initialised on server boot so they are never left empty.

Integration:
  - Started automatically by ``typeclasses.rooms.Room.at_init()`` on the
    first room that loads.
  - Uses ``typeclasses.mobs.spawn_mobs_for_room()`` for actual spawning.
  - Boss cooldown timestamps are stored on the room as
    ``boss_respawn_timestamps`` (dict of boss_id -> unix timestamp).
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Set

from evennia.scripts.scripts import DefaultScript
from evennia.utils import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Interval in seconds between realm-wide respawn checks.
RESPAWN_TICK_INTERVAL = 5.0

# Boss respawn cooldown in seconds (1 hour).
BOSS_RESPAWN_COOLDOWN = 3600

# Newbie zone keys that must be force-initialised on boot.
NEWBIE_ZONE_KEYS = {"brimstone_courtyard", "sunspire_meadows"}

# Global reference to the running script (set on start, cleared on stop).
_ACTIVE_SPAWNER: Optional[int] = None  # dbref of the host object


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_alive_mobs(room: Any) -> int:
    """Count alive realm mobs currently in a room."""
    count = 0
    try:
        for obj in room.contents:
            if not hasattr(obj, "attributes"):
                continue
            if not obj.attributes.get("is_mob", False):
                continue
            hp = obj.attributes.get("hp", 0)
            if hp > 0:
                count += 1
    except Exception:
        pass
    return count


def _count_alive_bosses(room: Any) -> int:
    """Count alive boss mobs currently in a room."""
    count = 0
    try:
        for obj in room.contents:
            if not hasattr(obj, "attributes"):
                continue
            if not obj.attributes.get("is_boss", False):
                continue
            hp = obj.attributes.get("hp", 0)
            if hp > 0:
                count += 1
    except Exception:
        pass
    return count


def _get_boss_cooldowns(room: Any) -> Dict[str, float]:
    """Return the dict of boss_id -> death_timestamp for a room."""
    try:
        return room.attributes.get("boss_respawn_timestamps", default={})
    except Exception:
        return {}


def _set_boss_cooldown(room: Any, boss_id: str, timestamp: float) -> None:
    """Record a boss death timestamp on the room."""
    try:
        cooldowns = dict(room.attributes.get("boss_respawn_timestamps", default={}))
        cooldowns[boss_id] = timestamp
        room.attributes.add("boss_respawn_timestamps", cooldowns)
    except Exception:
        pass


def _clear_boss_cooldown(room: Any, boss_id: str) -> None:
    """Remove a boss cooldown entry after respawn."""
    try:
        cooldowns = dict(room.attributes.get("boss_respawn_timestamps", default={}))
        cooldowns.pop(boss_id, None)
        room.attributes.add("boss_respawn_timestamps", cooldowns)
    except Exception:
        pass


def _room_has_spawn_table(room: Any) -> bool:
    """Return True if the room has a non-empty spawn_table."""
    try:
        table = room.attributes.get("spawn_table", default=[])
        return bool(table)
    except Exception:
        return False


def _get_max_mobs(room: Any) -> int:
    """Return the room's max_mobs cap, defaulting to 3."""
    try:
        return room.attributes.get("max_mobs", default=3)
    except Exception:
        return 3


def _get_zone_tag(room: Any) -> Optional[str]:
    """Return the room's zone_tag, or None."""
    try:
        return room.attributes.get("zone_tag", default=None)
    except Exception:
        return None


def _get_room_spawn_table(room: Any) -> list:
    """Return the room's spawn_table, or empty list."""
    try:
        return room.attributes.get("spawn_table", default=[])
    except Exception:
        return []


# ---------------------------------------------------------------------------
# RealmRespawnScript — global persistent ticker
# ---------------------------------------------------------------------------

class RealmRespawnScript(DefaultScript):
    """
    Global realm-wide mob respawn ticker.

    Runs every RESPAWN_TICK_INTERVAL seconds.  On each tick it iterates
    every room in the database that has a ``spawn_table``, counts alive
    mobs, and spawns replacements up to the room's ``max_mobs`` cap.

    Boss mobs are handled separately: they only respawn after their
    3600-second cooldown has elapsed since their last death timestamp.
    """

    def at_script_creation(self):
        self.key = "realm_respawn_ticker"
        self.desc = "Global realm-wide mob respawn engine"
        self.interval = RESPAWN_TICK_INTERVAL
        self.persistent = False
        self.start_delay = True

    def at_repeat(self):
        """Execute one realm-wide respawn pass."""
        self._respawn_pass()

    def at_start(self):
        """Force-initialise newbie zones on first start."""
        global _ACTIVE_SPAWNER
        _ACTIVE_SPAWNER = self.obj.id if self.obj else None
        self._init_newbie_zones()

    def at_stop(self):
        """Clean up global reference."""
        global _ACTIVE_SPAWNER
        _ACTIVE_SPAWNER = None

    # ------------------------------------------------------------------
    # Respawn pass
    # ------------------------------------------------------------------

    def _respawn_pass(self) -> None:
        """Iterate all rooms with spawn tables and top them up."""
        try:
            from evennia.objects.models import ObjectDB
        except Exception:
            return

        now = time.time()

        try:
            rooms = ObjectDB.objects.filter(
                db_typeclass_path__endswith="Room"
            )
        except Exception:
            return

        for room in rooms:
            try:
                self._process_room(room, now)
            except Exception:
                continue

    def _process_room(self, room: Any, now: float) -> None:
        """Process a single room: top up XP mobs, check boss cooldowns."""
        if not _room_has_spawn_table(room):
            return

        # Safe zones never spawn combat mobs.
        try:
            if room.attributes.get("safe_zone", False):
                return
        except Exception:
            pass

        spawn_table = _get_room_spawn_table(room)
        max_mobs = _get_max_mobs(room)
        current_mobs = _count_alive_mobs(room)

        # --- XP mobs: spawn if under cap ---
        if current_mobs < max_mobs:
            self._spawn_xp_mobs(room, spawn_table, max_mobs, current_mobs)

        # --- Boss mobs: check cooldowns ---
        self._check_boss_respawns(room, spawn_table, now)

    def _spawn_xp_mobs(self, room: Any, spawn_table: list,
                       max_mobs: int, current_mobs: int) -> None:
        """
        Spawn regular XP mobs up to the room's max_mobs cap.

        Only spawns entries that are NOT bosses (no boss_id, no is_boss flag).
        """
        needed = max_mobs - current_mobs
        if needed <= 0:
            return

        # Filter to non-boss entries only.
        xp_entries = [
            entry for entry in spawn_table
            if not entry.get("is_boss", False) and not entry.get("boss_id")
        ]

        if not xp_entries:
            return

        try:
            from typeclasses.mobs import spawn_mobs_for_room
        except Exception:
            return

        # Spawn one mob per tick to avoid flooding a room.
        # We pick the first entry that is under its individual count.
        import random
        entry = random.choice(xp_entries)
        proto_key = entry.get("prototype", "")
        individual_count = entry.get("count", 1)

        # Count existing mobs of this prototype in the room.
        existing_of_type = 0
        try:
            for obj in room.contents:
                if not hasattr(obj, "attributes"):
                    continue
                if not obj.attributes.get("is_mob", False):
                    continue
                hp = obj.attributes.get("hp", 0)
                if hp <= 0:
                    continue
                if obj.key.lower().startswith(proto_key.lower()):
                    existing_of_type += 1
                elif obj.attributes.get("prototype_key", "") == proto_key:
                    existing_of_type += 1
        except Exception:
            pass

        if existing_of_type < individual_count:
            spawn_mobs_for_room(room, [entry])

    def _check_boss_respawns(self, room: Any, spawn_table: list,
                             now: float) -> None:
        """
        Check boss cooldowns and respawn bosses whose timer has elapsed.

        Boss entries have ``is_boss=True`` or a ``boss_id`` key.
        """
        boss_entries = [
            entry for entry in spawn_table
            if entry.get("is_boss", False) or entry.get("boss_id")
        ]

        if not boss_entries:
            return

        cooldowns = _get_boss_cooldowns(room)

        for entry in boss_entries:
            boss_id = entry.get("boss_id") or entry.get("prototype", "")
            proto_key = entry.get("prototype", "")

            # Check if a boss of this type is already alive in the room.
            if _count_alive_bosses(room) > 0:
                # Check specifically for this boss_id.
                found_alive = False
                try:
                    for obj in room.contents:
                        if not hasattr(obj, "attributes"):
                            continue
                        if obj.attributes.get("boss_id", "") == boss_id:
                            hp = obj.attributes.get("hp", 0)
                            if hp > 0:
                                found_alive = True
                                break
                except Exception:
                    pass
                if found_alive:
                    continue

            # Check cooldown.
            death_ts = cooldowns.get(boss_id, 0)
            if death_ts > 0 and (now - death_ts) < BOSS_RESPAWN_COOLDOWN:
                continue  # Still on cooldown.

            # Cooldown elapsed or never set — respawn the boss.
            try:
                from typeclasses.mobs import spawn_mobs_for_room
                spawn_mobs_for_room(room, [entry])
                _clear_boss_cooldown(room, boss_id)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Newbie zone initialisation
    # ------------------------------------------------------------------

    def _init_newbie_zones(self) -> None:
        """
        Force-initialise spawn tables for all 1-10 newbie zones on boot.

        Ensures ``brimstone_courtyard`` (Evil) and ``sunspire_meadows``
        (Good) starter zones are never left empty after a server restart.
        """
        try:
            from evennia import search_tag
        except Exception:
            return

        for zone_key in NEWBIE_ZONE_KEYS:
            try:
                rooms = search_tag(zone_key, category="zone")
                for room in rooms:
                    if not _room_has_spawn_table(room):
                        self._build_newbie_spawn_table(room, zone_key)
                    # Force-populate if empty.
                    current = _count_alive_mobs(room)
                    max_mobs = _get_max_mobs(room)
                    if current < max_mobs:
                        spawn_table = _get_room_spawn_table(room)
                        if spawn_table:
                            try:
                                from typeclasses.mobs import spawn_mobs_for_room
                                spawn_mobs_for_room(room, spawn_table)
                            except Exception:
                                pass
            except Exception:
                continue

    def _build_newbie_spawn_table(self, room: Any, zone_key: str) -> None:
        """
        Build a default spawn table for a newbie zone room that lacks one.

        Uses the faction-appropriate level-1 mob pool from
        ``world.realm_population``.
        """
        try:
            import world.realm_population as rp
            import random

            if zone_key == "sunspire_meadows":
                faction = rp.FACTION_GOOD
                pool = rp.GOOD_MOB_POOLS.get(1, [])
            else:
                faction = rp.FACTION_EVIL
                pool = rp.EVIL_MOB_POOLS.get(1, [])

            if not pool:
                return

            # Pick 2-3 random mob types for this room.
            num_types = random.randint(2, 3)
            chosen = random.sample(pool, min(num_types, len(pool)))

            spawn_table = []
            for spec in chosen:
                spawn_table.append({
                    "prototype": spec["name"].lower().replace(" ", "_"),
                    "count": 1,
                    "respawn_delay": 45,
                    "mob_data": spec,
                })

            room.attributes.add("spawn_table", spawn_table)
            room.attributes.add("max_mobs", 3)
            room.attributes.add("zone_tag", zone_key)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_realm_spawner() -> bool:
    """
    Start the global realm respawn script if not already running.

    Returns True if the spawner was started (or already running).
    """
    global _ACTIVE_SPAWNER

    # Check if already running.
    if _ACTIVE_SPAWNER is not None:
        try:
            from evennia.objects.models import ObjectDB
            host = ObjectDB.objects.filter(id=_ACTIVE_SPAWNER).first()
            if host and host.scripts.get("realm_respawn_ticker"):
                return True
        except Exception:
            pass
        _ACTIVE_SPAWNER = None

    # Find a suitable host object — use the first room we can find.
    try:
        from evennia.objects.models import ObjectDB
        host = ObjectDB.objects.filter(
            db_typeclass_path__endswith="Room"
        ).first()
        if host is None:
            # Fallback: use any object.
            host = ObjectDB.objects.first()
        if host is None:
            logger.log_err("RealmRespawnScript: no host object found to attach script.")
            return False

        script = host.scripts.add(RealmRespawnScript)
        if script:
            _ACTIVE_SPAWNER = host.id
            return True
    except Exception as err:
        logger.log_err(f"RealmRespawnScript: failed to start: {err}")

    return False


def stop_realm_spawner() -> bool:
    """Stop the global realm respawn script if running."""
    global _ACTIVE_SPAWNER

    if _ACTIVE_SPAWNER is None:
        return True

    try:
        from evennia.objects.models import ObjectDB
        host = ObjectDB.objects.filter(id=_ACTIVE_SPAWNER).first()
        if host:
            script = host.scripts.get("realm_respawn_ticker")
            if script:
                script.stop()
    except Exception:
        pass

    _ACTIVE_SPAWNER = None
    return True


def record_boss_death(boss: Any) -> None:
    """
    Record a boss death timestamp for cooldown tracking.

    Called by the mob death path when a boss mob dies.  Stores the
    current unix timestamp on the boss's home room so the respawn
    ticker can enforce the 3600-second cooldown.

    Args:
        boss: The boss mob that just died.
    """
    try:
        boss_id = boss.attributes.get("boss_id", "")
        if not boss_id:
            return

        home_dbref = boss.attributes.get("home_room_dbref")
        if not home_dbref:
            return

        from evennia.objects.models import ObjectDB
        home_room = ObjectDB.objects.filter(id=home_dbref).first()
        if home_room is None:
            return

        _set_boss_cooldown(home_room, boss_id, time.time())
    except Exception:
        pass


def get_spawner_status() -> Dict[str, Any]:
    """
    Return a status dict for the realm spawner.

    Used by the ``@spawnstats`` admin command.
    """
    global _ACTIVE_SPAWNER
    return {
        "running": _ACTIVE_SPAWNER is not None,
        "host_dbref": _ACTIVE_SPAWNER,
        "tick_interval": RESPAWN_TICK_INTERVAL,
        "boss_cooldown": BOSS_RESPAWN_COOLDOWN,
    }


def gather_room_spawn_stats() -> list:
    """
    Gather spawn statistics for every room in the realm.

    Returns a list of dicts, each containing:
      - room_key, room_dbref
      - zone_tag
      - max_mobs
      - active_mobs
      - boss_cooldowns (dict of boss_id -> seconds_remaining)
      - spawn_table_entries (count)

    Used by the ``@spawnstats`` admin command.
    """
    stats = []

    try:
        from evennia.objects.models import ObjectDB
        rooms = ObjectDB.objects.filter(
            db_typeclass_path__endswith="Room"
        )
    except Exception:
        return stats

    now = time.time()

    for room in rooms:
        try:
            entry = {
                "room_key": room.db_key or "(no key)",
                "room_dbref": room.id,
                "zone_tag": _get_zone_tag(room) or "(none)",
                "max_mobs": _get_max_mobs(room),
                "active_mobs": _count_alive_mobs(room),
                "boss_cooldowns": {},
                "spawn_table_entries": len(_get_room_spawn_table(room)),
            }

            # Compute remaining boss cooldowns.
            cooldowns = _get_boss_cooldowns(room)
            for boss_id, death_ts in cooldowns.items():
                elapsed = now - death_ts
                remaining = max(0, BOSS_RESPAWN_COOLDOWN - elapsed)
                entry["boss_cooldowns"][boss_id] = int(remaining)

            stats.append(entry)
        except Exception:
            continue

    return stats