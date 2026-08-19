"""
Base Mob Typeclass for 'rop' — Full Lifecycle, AI, and Respawn

Provides:
  - Mob base class inheriting from DefaultCharacter
  - Automated respawn on death with configurable delay
  - AI tick system: aggro checking, random wandering, idle handling
  - Corpse creation and cleanup on death
  - Memory-safe timer management (no leaks, no orphaned timers)
  - Proactive aggro: aggressive mobs attack players on sight (room entry + periodic)
  - Retaliation: mobs lock onto attackers when damaged

Architecture:
  Each mob runs a lightweight MobAIScript (Evennia Script) that ticks
  every 5 seconds.  The script handles aggro detection, wandering, and
  idle behaviour.  On death the mob creates a corpse, removes itself
  from the room, and schedules a deferred respawn via Evennia's
  utils.delay.  The respawn callback re-creates the mob at its home
  location and restarts the AI ticker.

Integration points:
  - world.tick_combat.CombatHandler  — mobs enter/exit combat
  - world.combat._handle_defeat      — NPC death path (already handles mobs)
  - world.mob_ai.check_mob_aggro     — aggro decision logic
  - typeclasses.rooms.Room           — spawner hooks call spawn_mob()
"""

from __future__ import annotations

import random
import time
from typing import Any, Optional, TYPE_CHECKING

from evennia.objects.objects import DefaultCharacter
from evennia.scripts.scripts import DefaultScript
from evennia.utils import delay

if TYPE_CHECKING:
    from typeclasses.rooms import Room

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default seconds between AI ticks
MOB_AI_TICK_INTERVAL = 5.0

# Default seconds before a dead mob respawns
DEFAULT_RESPAWN_DELAY = 60

# Chance per AI tick that a wandering mob will attempt to move (0.0-1.0)
DEFAULT_WANDER_CHANCE = 0.15

# Maximum rooms a mob will wander from its home before turning back
DEFAULT_WANDER_RADIUS = 5

# Minimum seconds between successful wander movements.
# Prevents mobs from jittering or spamming room entry/exit logs.
# Mobs must wait at least this long after moving before wandering again.
DEFAULT_WANDER_COOLDOWN = 45


# ---------------------------------------------------------------------------
# MobAIScript — per-mob AI ticker
# ---------------------------------------------------------------------------

class MobAIScript(DefaultScript):
    """
    Lightweight per-mob AI script.

    Attached to each Mob instance.  Ticks every MOB_AI_TICK_INTERVAL
    seconds and runs the mob's AI logic: aggro check, wandering, idle.
    Automatically stops when the mob is deleted or despawned.
    """

    def at_script_creation(self):
        self.key = "mob_ai_ticker"
        self.desc = "Per-mob AI behaviour ticker"
        self.interval = MOB_AI_TICK_INTERVAL
        self.persistent = False
        self.start_delay = True

    def at_repeat(self):
        """Execute one AI tick for the attached mob."""
        mob = self.obj
        if mob is None:
            self.stop()
            return

        # If the mob is dead or deleted, stop the script
        if not _mob_is_alive(mob):
            self.stop()
            return

        # Run the mob's AI logic
        mob.ai_tick()

    def at_stop(self):
        """Clean up the mob's reference to this script."""
        mob = self.obj
        if mob is not None and hasattr(mob, "ndb"):
            try:
                mob.ndb.ai_script = None
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mob_is_alive(mob: Any) -> bool:
    """Return True if the mob exists and has HP > 0."""
    if mob is None:
        return False
    try:
        hp = mob.attributes.get("hp", 0)
        return hp > 0
    except Exception:
        return False


def _mob_is_in_combat(mob: Any) -> bool:
    """Return True if the mob is currently engaged in combat."""
    try:
        from world.tick_combat import CombatHandler
        return CombatHandler.is_in_combat(mob)
    except Exception:
        return False


def _get_room_exits(room: Any) -> list:
    """Return a list of usable exit objects from the given room."""
    if room is None:
        return []
    try:
        return [ex for ex in room.exits if ex.destination]
    except Exception:
        return []


def _is_player(obj: Any) -> bool:
    """Return True if obj is a player character (has an account)."""
    return bool(getattr(obj, "has_account", False))


def _is_aggressive_mob(mob: Any) -> bool:
    """
    Return True if the mob is aggressive and should attack players on sight.

    Checks in order:
      1. ``aggressive`` attribute (bool) — simplest flag.
      2. ``mob_ai`` attribute with AGGRESSIVE or GUARDIAN disposition.
      3. ``is_aggro`` attribute (legacy).
    """
    try:
        if mob.attributes.get("aggressive", False):
            return True
    except Exception:
        pass

    try:
        from world.mob_ai import MobDisposition
        ai = mob.attributes.get("mob_ai")
        if ai and ai.disposition in (MobDisposition.AGGRESSIVE, MobDisposition.GUARDIAN):
            return True
    except Exception:
        pass

    try:
        if mob.attributes.get("is_aggro", False):
            return True
    except Exception:
        pass

    return False


# ---------------------------------------------------------------------------
# Mob — base typeclass for all mobile entities
# ---------------------------------------------------------------------------

class Mob(DefaultCharacter):
    """
    Base typeclass for all mobile (AI-driven) entities.

    Mobs are non-player characters that can be hostile, neutral, or
    passive.  They have a full lifecycle:

      1. Spawned into a room (by a room spawner or admin command).
      2. AI ticker starts — checks for aggro, wanders, idles.
      3. When HP reaches 0, the mob dies:
         a. Corpse is created via world.combat._handle_defeat.
         b. Mob is removed from the room.
         c. A deferred respawn is scheduled.
      4. After respawn_delay seconds, the mob respawns at its home room.

    Attributes (persistent, stored on self.attributes):
      - is_mob (bool)            — always True for Mob instances
      - home_room_dbref (int)    — dbref of the spawn/home room
      - respawn_delay (int)      — seconds before respawn (default 60)
      - wander_chance (float)    — probability of wandering per AI tick
      - wander_radius (int)      — max rooms from home before turning back
      - mob_ai (MobAIData)       — AI disposition, aggro radius, etc.
      - aggressive (bool)        — if True, attacks players on sight
      - is_aggro (bool)          — legacy aggressive flag
      - faction (str)            — faction tag for social aggro
      - level (int)              — mob level
      - stats (dict)             — STR/DEX/CON/INT/WIS/CHA
      - hp / max_hp (int)        — health
      - alignment (str)          — Good/Evil/Neutral
      - xp_value (int)           — XP awarded on kill
      - gold_min / gold_max (int)— coin drop range
      - damage_type (str)        — slash/pierce/blunt/etc.
      - loot_table (list)        — loot drop table
    """

    def at_object_creation(self):
        """Set up default mob attributes on first creation."""
        super().at_object_creation()

        # Core mob identity
        self.attributes.add("is_mob", True)

        # Respawn configuration
        if not self.attributes.has("home_room_dbref"):
            self.attributes.add("home_room_dbref", None)
        if not self.attributes.has("respawn_delay"):
            self.attributes.add("respawn_delay", DEFAULT_RESPAWN_DELAY)

        # AI behaviour
        if not self.attributes.has("wander_chance"):
            self.attributes.add("wander_chance", DEFAULT_WANDER_CHANCE)
        if not self.attributes.has("wander_radius"):
            self.attributes.add("wander_radius", DEFAULT_WANDER_RADIUS)

        # Aggression flag — simple boolean for "attacks on sight"
        if not self.attributes.has("aggressive"):
            self.attributes.add("aggressive", False)

        # Default stats if not set by prototype
        if not self.attributes.has("level"):
            self.attributes.add("level", 1)
        if not self.attributes.has("stats"):
            self.attributes.add("stats", {
                "str": 10, "dex": 10, "con": 10,
                "int": 10, "wis": 10, "cha": 10,
            })
        if not self.attributes.has("hp"):
            self.attributes.add("hp", 20)
        if not self.attributes.has("max_hp"):
            self.attributes.add("max_hp", 20)
        if not self.attributes.has("alignment"):
            self.attributes.add("alignment", "Neutral")
        if not self.attributes.has("faction"):
            self.attributes.add("faction", "neutral")
        if not self.attributes.has("xp_value"):
            self.attributes.add("xp_value", 10)
        if not self.attributes.has("gold_min"):
            self.attributes.add("gold_min", 0)
        if not self.attributes.has("gold_max"):
            self.attributes.add("gold_max", 3)
        if not self.attributes.has("damage_type"):
            self.attributes.add("damage_type", "slash")

        # Tag for room display classification
        self.tags.add("realm_mob", category="spawn")

    def at_init(self):
        """Called when the mob is loaded into memory (server start/reload)."""
        super().at_init()

        # Store home room on first init if not already set
        if self.location and not self.attributes.get("home_room_dbref"):
            self.attributes.add("home_room_dbref", self.location.id)

        # Start the AI ticker if the mob is alive
        if _mob_is_alive(self):
            self._start_ai_ticker()

    def at_object_delete(self):
        """Clean up AI script and cancel pending respawn before deletion."""
        # Stop the AI ticker
        self._stop_ai_ticker()

        # Cancel any pending respawn deferred action (persistent task id)
        try:
            task_id = getattr(self.ndb, "respawn_task_id", None)
            if task_id is not None:
                from evennia.scripts.taskhandler import TASK_HANDLER
                TASK_HANDLER.remove(task_id)
                self.ndb.respawn_task_id = None
        except Exception:
            pass

        # Clean up combat references
        try:
            from world.tick_combat import CombatHandler
            CombatHandler.stop_combat(self)
        except Exception:
            pass

        # Clear non-persistent state
        if hasattr(self, "ndb"):
            try:
                self.ndb.clear()
            except Exception:
                pass

        return super().at_object_delete()

    # ------------------------------------------------------------------
    # Movement hooks — proactive aggro on room entry
    # ------------------------------------------------------------------

    def at_after_move(self, source_location, **kwargs):
        """
        Called after the mob has moved into a new room.

        If the mob is aggressive, it immediately scans the new room for
        players and initiates combat against the first valid target.
        This ensures wandering aggressive mobs attack players on sight
        without waiting for the next AI tick.
        """
        super().at_after_move(source_location, **kwargs)

        if not _mob_is_alive(self):
            return
        if _mob_is_in_combat(self):
            return
        if not _is_aggressive_mob(self):
            return

        location = self.location
        if location is None:
            return

        # Scan for players in the new room and attack the first valid target.
        for obj in location.contents:
            if obj == self:
                continue
            if not _is_player(obj):
                continue
            if not _mob_is_alive(obj):
                continue

            # Use the aggro check from mob_ai if available, otherwise
            # aggressive mobs attack any player regardless of alignment.
            try:
                from world.mob_ai import check_mob_aggro
                if not check_mob_aggro(self, obj):
                    continue
            except Exception:
                pass

            # Initiate combat!
            try:
                from world.tick_combat import CombatHandler
                if not CombatHandler.is_in_combat(self):
                    location.msg_contents(
                        f"|R{self.key} snarls and attacks {obj.key}!|n"
                    )
                    CombatHandler.start_combat(self, obj)
                    return
            except Exception:
                pass

    # ------------------------------------------------------------------
    # AI Ticker management
    # ------------------------------------------------------------------

    def _start_ai_ticker(self) -> None:
        """Start the MobAIScript on this mob if not already running."""
        # Avoid double-starting
        existing = self.scripts.get("mob_ai_ticker")
        if existing:
            return

        try:
            script = self.scripts.add(MobAIScript)
            if script and hasattr(self, "ndb"):
                self.ndb.ai_script = script
        except Exception:
            pass

    def _stop_ai_ticker(self) -> None:
        """Stop the MobAIScript on this mob."""
        try:
            existing = self.scripts.get("mob_ai_ticker")
            if existing:
                existing.stop()
        except Exception:
            pass
        if hasattr(self, "ndb"):
            try:
                self.ndb.ai_script = None
            except Exception:
                pass

    # ------------------------------------------------------------------
    # AI Behaviour
    # ------------------------------------------------------------------

    def ai_tick(self) -> None:
        """
        Execute one AI tick.

        Priority order:
          1. If in combat, mana regen + flee check handled by combat engine.
          2. Out of combat: mana regen, then patrol, then aggro check,
             faction warfare, then random wandering, then idle.
        """
        if not _mob_is_alive(self):
            return

        # 1. Already fighting — combat engine handles everything
        if _mob_is_in_combat(self):
            return

        # --- Phase 5: Mana regeneration (out of combat) ---
        try:
            from world.mob_ai import regen_npc_mana
            regen_npc_mana(self)
        except Exception:
            pass

        # 2. Aggro check — look for players in the current room
        if self._check_aggro():
            return

        # --- Phase 5: Faction warfare — check for opposing faction mobs ---
        if self._check_faction_warfare():
            return

        # --- Phase 5: Patrol path movement ---
        if self._try_patrol():
            return

        # 3. Random wandering
        # Only wander if no patrol path is set (patrol takes priority)
        try:
            from world.mob_ai import MobAIData
            ai = self.attributes.get("mob_ai")
            has_patrol = ai and hasattr(ai, "patrol_path") and ai.patrol_path
        except Exception:
            has_patrol = False

        if not has_patrol and self._should_wander():
            self._try_wander()

    def _check_aggro(self) -> bool:
        """
        Check for players in the current room and attack if appropriate.

        Aggressive mobs (aggressive=True, is_aggro=True, or AGGRESSIVE/GUARDIAN
        disposition) will attack players on sight.  Neutral mobs only attack
        when provoked (via at_damage retaliation).

        Returns True if the mob initiated combat.
        """
        location = self.location
        if location is None:
            return False

        # Only aggressive mobs initiate combat proactively.
        if not _is_aggressive_mob(self):
            return False

        # Use the existing mob_ai.aggro_check if available
        try:
            from world.mob_ai import check_mob_aggro
        except Exception:
            return False

        for obj in location.contents:
            if obj == self:
                continue
            if not _is_player(obj):
                continue
            if not _mob_is_alive(obj):
                continue

            if check_mob_aggro(self, obj):
                # Initiate combat
                try:
                    from world.tick_combat import CombatHandler
                    if not CombatHandler.is_in_combat(self):
                        self.location.msg_contents(
                            f"|R{self.key} attacks {obj.key}!|n"
                        )
                        CombatHandler.start_combat(self, obj)
                        return True
                except Exception:
                    pass

        return False

    def _should_wander(self) -> bool:
        """Return True if the mob should attempt to wander this tick."""
        wander_chance = self.attributes.get("wander_chance", DEFAULT_WANDER_CHANCE)
        if wander_chance <= 0:
            return False
        return random.random() < wander_chance

    def _try_wander(self) -> bool:
        """
        Attempt to move to a random adjacent room.

        Validates:
          - Wander cooldown: mobs must wait DEFAULT_WANDER_COOLDOWN
            seconds between successful movements to prevent jittering.
          - Exit availability and destination existence.
          - Safe zone avoidance.
          - Wander radius from home room.
          - Zone boundary: destination must share the same ``zone_tag``
            as the mob's current room (if zone_tag is set).
          - Occupancy cap: destination must be under its ``max_mobs``
            limit before the mob steps in.

        Returns True if the mob successfully moved.
        """
        location = self.location
        if location is None:
            return False

        # --- Wander cooldown check ---
        # Prevents mobs from jittering between rooms on every AI tick.
        # Mobs must wait at least DEFAULT_WANDER_COOLDOWN seconds after
        # their last successful wander before moving again.
        now = time.time()
        last_wander = self.attributes.get("last_wander_time", 0)
        wander_cooldown = self.attributes.get("wander_cooldown", DEFAULT_WANDER_COOLDOWN)
        if now - last_wander < wander_cooldown:
            return False

        exits = _get_room_exits(location)
        if not exits:
            return False

        # Determine the mob's current zone tag for boundary enforcement.
        current_zone = location.attributes.get("zone_tag", default=None)

        # Filter exits: don't wander into safe zones, wrong zones, or full rooms.
        valid_exits = []
        for ex in exits:
            dest = ex.destination
            if dest is None:
                continue
            # Don't wander into safe zones
            if dest.attributes.get("safe_zone", False):
                continue
            # Check wander radius from home
            if not self._within_wander_radius(dest):
                continue
            # Zone boundary validation: abort if destination zone differs.
            if current_zone is not None:
                dest_zone = dest.attributes.get("zone_tag", default=None)
                if dest_zone is not None and dest_zone != current_zone:
                    continue
            # Occupancy check: abort if destination room is full.
            if not self._room_has_capacity(dest):
                continue
            valid_exits.append(ex)

        if not valid_exits:
            return False

        chosen_exit = random.choice(valid_exits)
        destination = chosen_exit.destination

        try:
            # Announce departure
            if location:
                location.msg_contents(
                    f"|W{self.key} wanders {chosen_exit.key}.|n"
                )

            self.move_to(destination, quiet=False)

            # Record the wander timestamp for cooldown enforcement.
            self.attributes.add("last_wander_time", time.time())

            # Announce arrival
            if destination:
                destination.msg_contents(
                    f"|W{self.key} wanders in.|n"
                )
            return True
        except Exception:
            return False

    def _room_has_capacity(self, room: Any) -> bool:
        """
        Return True if the target room is under its ``max_mobs`` cap.

        Counts alive realm mobs currently in the room and compares
        against the room's ``max_mobs`` attribute.  If the room has
        no ``max_mobs`` set, defaults to allowing entry (cap of 3).
        """
        if room is None:
            return False
        try:
            max_mobs = room.attributes.get("max_mobs", default=3)
            current = 0
            for obj in room.contents:
                if not hasattr(obj, "attributes"):
                    continue
                if not obj.attributes.get("is_mob", False):
                    continue
                hp = obj.attributes.get("hp", 0)
                if hp > 0:
                    current += 1
            return current < max_mobs
        except Exception:
            return True  # If we can't check, allow movement.

    def _within_wander_radius(self, room: Any) -> bool:
        """
        Return True if the given room is within wander_radius of the
        mob's home room.

        Uses BFS (breadth-first search) through exits to compute the
        shortest path distance from the home room.  Caches the distance
        on each visited room's ndb to avoid recomputation across mobs.
        """
        wander_radius = self.attributes.get("wander_radius", DEFAULT_WANDER_RADIUS)
        if wander_radius <= 0:
            return True  # No radius restriction

        home_dbref = self.attributes.get("home_room_dbref")
        if home_dbref is None:
            return True  # No home set, allow wandering

        # If the room IS the home, always allow
        if room.id == home_dbref:
            return True

        # Check the ndb cache first (set by a previous BFS from this home).
        cache_key = f"_wander_dist_{home_dbref}"
        try:
            cached = getattr(room.ndb, cache_key, None)
            if cached is not None:
                return cached <= wander_radius
        except Exception:
            pass

        # Resolve the home room object.
        try:
            from evennia.objects.models import ObjectDB
            home_room = ObjectDB.objects.filter(id=home_dbref).first()
        except Exception:
            home_room = None

        if home_room is None:
            return True  # Home room no longer exists

        # BFS from home room outward up to wander_radius + 1 steps.
        from collections import deque
        visited: Dict[int, int] = {home_room.id: 0}
        queue = deque([(home_room, 0)])

        while queue:
            current, dist = queue.popleft()
            if dist > wander_radius:
                continue

            # Cache the distance on the current room's ndb.
            try:
                setattr(current.ndb, cache_key, dist)
            except Exception:
                pass

            # Explore exits to adjacent rooms.
            try:
                exits = current.exits
            except Exception:
                continue

            for ex in exits:
                dest = ex.destination
                if dest is None:
                    continue
                if dest.id in visited:
                    continue
                # Skip safe zones (mobs shouldn't wander into them).
                try:
                    if dest.attributes.get("safe_zone", False):
                        continue
                except Exception:
                    pass
                visited[dest.id] = dist + 1
                queue.append((dest, dist + 1))

        # Check if the target room was reached.
        distance = visited.get(room.id)
        if distance is not None:
            return distance <= wander_radius

        # Room not reachable within the search radius — deny.
        return False

    # ------------------------------------------------------------------
    # Phase 5: Faction warfare — mob vs mob aggro
    # ------------------------------------------------------------------

    def _check_faction_warfare(self) -> bool:
        """
        Scan the room for opposing faction mobs and attack if appropriate.

        Only aggressive/guardian mobs with ``aggro_other_mobs=True`` in
        their MobAIData will initiate faction warfare.

        Returns True if the mob initiated combat against another mob.
        """
        location = self.location
        if location is None:
            return False

        try:
            from world.mob_ai import check_mob_vs_mob_aggro
        except Exception:
            return False

        for obj in location.contents:
            if obj == self:
                continue
            if not hasattr(obj, "attributes"):
                continue
            if not obj.attributes.get("is_mob", False):
                continue
            if not _mob_is_alive(obj):
                continue

            if check_mob_vs_mob_aggro(self, obj):
                try:
                    from world.tick_combat import CombatHandler
                    if not CombatHandler.is_in_combat(self):
                        location.msg_contents(
                            f"|R{self.key} snarls and attacks {obj.key}!|n"
                        )
                        CombatHandler.start_combat(self, obj)
                        return True
                except Exception:
                    pass

        return False

    # ------------------------------------------------------------------
    # Phase 5: Patrol path movement
    # ------------------------------------------------------------------

    def _try_patrol(self) -> bool:
        """
        Attempt to move along the mob's patrol path.

        Uses ``world.mob_ai.advance_patrol()`` to get the next waypoint
        room key, then attempts to move there via available exits.

        Returns True if the mob successfully moved toward a patrol waypoint.
        """
        try:
            from world.mob_ai import advance_patrol
            next_room_key = advance_patrol(self)
        except Exception:
            return False

        if next_room_key is None:
            return False

        location = self.location
        if location is None:
            return False

        # Find an exit whose destination matches the patrol waypoint key
        exits = _get_room_exits(location)
        for ex in exits:
            dest = ex.destination
            if dest is None:
                continue
            # Match by room key (case-insensitive)
            dest_key = dest.key if hasattr(dest, "key") else ""
            if dest_key.lower() == next_room_key.lower():
                try:
                    location.msg_contents(
                        f"|W{self.key} patrols {ex.key}.|n"
                    )
                    self.move_to(dest, quiet=False)
                    if dest:
                        dest.msg_contents(
                            f"|W{self.key} arrives on patrol.|n"
                        )
                    return True
                except Exception:
                    return False

        return False

    # ------------------------------------------------------------------
    # Death & Respawn
    # ------------------------------------------------------------------

    def die(self, killer: Any = None) -> None:
        """
        Handle mob death.

        1. Stop the AI ticker.
        2. Create a corpse via world.combat._handle_defeat (which handles
           XP awards, loot drops, and corpse creation for NPCs).
        3. Remove the mob from its current room.
        4. Schedule a deferred respawn.
        5. If this is a boss mob, record the death timestamp for the
           1-hour cooldown.

        This method is called by _handle_target_death in tick_combat.py
        which already calls _handle_defeat for NPCs.  We hook in here
        to add the respawn scheduling on top of the standard death flow.
        """
        # Stop AI ticker
        self._stop_ai_ticker()

        # Clear combat state
        try:
            from world.tick_combat import CombatHandler
            CombatHandler.stop_combat(self)
        except Exception:
            pass

        # Record boss death for cooldown tracking.
        try:
            is_boss = self.attributes.get("is_boss", False)
            if is_boss:
                from world.realm_spawner import record_boss_death
                record_boss_death(self)
        except Exception:
            pass

        # Schedule respawn
        self._schedule_respawn()

    def _schedule_respawn(self) -> None:
        """
        Schedule a deferred respawn after respawn_delay seconds.

        Uses Evennia's utils.delay which is safe across server reloads
        (persistent deferred tasks).  The mob is NOT deleted — it stays
        in the database but is moved to None location.  On respawn it
        is moved back to its home room and its HP is restored.
        """
        respawn_delay = self.attributes.get("respawn_delay", DEFAULT_RESPAWN_DELAY)

        # Store the home room dbref for the respawn callback
        home_dbref = self.attributes.get("home_room_dbref")
        if home_dbref is None and self.location:
            home_dbref = self.location.id
            self.attributes.add("home_room_dbref", home_dbref)

        # Move the mob to None (limbo) — it still exists in the DB
        # but is not in any room.  The corpse was already created by
        # _handle_defeat before this method is called.
        try:
            self.move_to(None, quiet=True)
        except Exception:
            pass

        # Schedule the respawn.  We pass the module-level function directly
        # with the dbref as argument so the task is picklable and survives
        # server restarts (persistent=True).
        mob_dbref = self.id

        try:
            task_id = delay(
                respawn_delay,
                _respawn_mob_by_dbref,
                mob_dbref,
                persistent=True,
            )
            if hasattr(self, "ndb"):
                self.ndb.respawn_task_id = task_id
        except Exception:
            # Fallback: if delay fails, try to respawn immediately
            _respawn_mob_by_dbref(mob_dbref)

    # ------------------------------------------------------------------
    # Combat hooks
    # ------------------------------------------------------------------

    def at_damage(self, damage: int, attacker: Any = None) -> None:
        """
        Called when the mob takes damage from any source.

        Retaliation logic:
          - PASSIVE mobs never fight back.
          - All other mobs (NEUTRAL, AGGRESSIVE, GUARDIAN) lock onto the
            attacker and begin counter-attacking on the next combat tick.
          - If the mob is already in combat with someone else, it adds
            the new attacker as an additional target.
          - Mobs with ``aggressive=True`` or ``is_aggro=True`` always
            retaliate regardless of mob_ai disposition.
        """
        if not _mob_is_alive(self):
            return
        if attacker is None or attacker == self:
            return

        # Check if this mob should retaliate.
        # Passive mobs (explicit MobDisposition.PASSIVE) never fight back.
        try:
            from world.mob_ai import MobDisposition
            ai = self.attributes.get("mob_ai")
            if ai and ai.disposition == MobDisposition.PASSIVE:
                return
        except Exception:
            pass

        # Auto-engage: lock onto the attacker and enter combat.
        try:
            from world.tick_combat import CombatHandler

            if not CombatHandler.is_in_combat(self):
                # Not fighting anyone yet — start combat with the attacker.
                CombatHandler.start_combat(self, attacker)
                if self.location:
                    self.location.msg_contents(
                        f"|R{self.key} turns on {attacker.key} with fury!|n"
                    )
            else:
                # Already fighting — add this attacker as an additional target
                # if not already engaged with them.
                existing_targets = CombatHandler.get_targets(self)
                if attacker not in existing_targets:
                    CombatHandler.start_combat(self, attacker)
                    if self.location:
                        self.location.msg_contents(
                            f"|R{self.key} also turns its attention to {attacker.key}!|n"
                        )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Respawn helper (module-level, called by deferred callback)
# ---------------------------------------------------------------------------

def _respawn_mob_by_dbref(dbref: int) -> None:
    """
    Respawn a mob by its database ID.

    Looks up the mob, restores its HP, moves it to its home room,
    and restarts the AI ticker.  If the mob no longer exists or the
    home room is gone, nothing happens.
    """
    try:
        from evennia.objects.models import ObjectDB
        mob = ObjectDB.objects.filter(id=dbref).first()
    except Exception:
        return

    if mob is None:
        return

    # Restore HP to full
    try:
        max_hp = mob.attributes.get("max_hp", 20)
        mob.attributes.add("hp", max_hp)
    except Exception:
        return

    # Find home room
    home_dbref = mob.attributes.get("home_room_dbref")
    home_room = None
    if home_dbref:
        try:
            home_room = ObjectDB.objects.filter(id=home_dbref).first()
        except Exception:
            pass

    if home_room is None:
        # Home room is gone — delete the mob
        try:
            mob.delete()
        except Exception:
            pass
        return

    # Move to home room
    try:
        mob.move_to(home_room, quiet=False)
        home_room.msg_contents(
            f"|W{mob.key} appears!|n"
        )
    except Exception:
        return

    # Re-equip the mob with level-appropriate gear (respawned mobs must not
    # be naked).  The original gear was transferred to the corpse on death,
    # so we generate a fresh loadout plus a new coin drop.
    try:
        from world.mob_equipment import equip_mob, generate_mob_coins
        from world.prototypes import MOB_PROTOTYPES

        proto_key = mob.attributes.get("prototype_key", default="")
        proto = MOB_PROTOTYPES.get(proto_key, {})

        mob_class = "Warrior"
        faction = "Neutral"
        for attr in proto.get("attrs", []):
            if attr[0] in ("guild_class", "mob_class"):
                mob_class = attr[1]
            elif attr[0] == "faction":
                faction = attr[1]

        equip_mob(mob, mob_class=mob_class, faction=faction)

        mob_level = mob.attributes.get("level", 1)
        coins = generate_mob_coins(mob_level)
        mob.attributes.add("copper_coins", coins.get("copper", 0))
        mob.attributes.add("silver_coins", coins.get("silver", 0))
        mob.attributes.add("gold_coins", coins.get("gold", 0))
    except Exception:
        pass

    # Restart AI ticker
    if hasattr(mob, "_start_ai_ticker"):
        try:
            mob._start_ai_ticker()
        except Exception:
            pass

    # Clear the respawn task reference
    if hasattr(mob, "ndb"):
        try:
            mob.ndb.respawn_task_id = None
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Spawn helper — creates a Mob from a prototype dict
# ---------------------------------------------------------------------------

def spawn_mob(
    prototype_key: str,
    location: Any,
    home_room: Optional[Any] = None,
    **overrides,
) -> Optional[Mob]:
    """
    Spawn a Mob from a prototype definition.

    Args:
        prototype_key: Key in world.prototypes.MOB_PROTOTYPES.
        location: The room to spawn the mob into.
        home_room: The mob's home room for respawn (defaults to location).
        **overrides: Additional attributes to set on the mob.

    Returns:
        The spawned Mob instance, or None on failure.
    """
    from evennia import create_object
    from world.prototypes import MOB_PROTOTYPES

    proto = MOB_PROTOTYPES.get(prototype_key)
    if proto is None:
        return None

    # Build creation kwargs from prototype
    creation_kwargs = {
        "key": proto.get("key", prototype_key),
        "location": location,
    }

    # Copy attributes from prototype
    attrs = list(proto.get("attrs", []))
    # Add home room
    home = home_room or location
    if home:
        attrs.append(("home_room_dbref", home.id))
    # Add overrides
    for k, v in overrides.items():
        attrs.append((k, v))
    creation_kwargs["attributes"] = attrs

    # Use the mob typeclass
    creation_kwargs["typeclass"] = "typeclasses.mobs.Mob"

    try:
        mob = create_object(**creation_kwargs)
        # Ensure the mob tag is set
        mob.tags.add("realm_mob", category="spawn")

        # --- Auto-equip the mob with level-appropriate gear ---
        _auto_equip_spawned_mob(mob, proto)

        # Start AI ticker
        mob._start_ai_ticker()
        return mob
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Room spawner helper — called by room hooks
# ---------------------------------------------------------------------------

def spawn_mobs_for_room(
    room: Any,
    spawn_entries: list,
) -> list:
    """
    Spawn all mobs defined in spawn_entries for a room.

    Args:
        room: The room to spawn mobs into.
        spawn_entries: List of dicts with keys:
            - prototype (str): prototype key
            - count (int): max simultaneous mobs of this type
            - respawn_delay (int, optional): override default respawn delay

    Returns:
        List of spawned Mob instances.
    """
    spawned = []
    for entry in spawn_entries:
        proto_key = entry.get("prototype", "")
        count = entry.get("count", 1)
        respawn_delay = entry.get("respawn_delay", None)

        # Count existing alive mobs of this prototype in the room
        existing_count = _count_alive_mobs_in_room(room, proto_key)

        # Spawn up to the configured count
        to_spawn = max(0, count - existing_count)
        for _ in range(to_spawn):
            overrides = {}
            if respawn_delay is not None:
                overrides["respawn_delay"] = respawn_delay
            mob = spawn_mob(proto_key, room, home_room=room, **overrides)
            if mob:
                spawned.append(mob)

    return spawned


def _count_alive_mobs_in_room(room: Any, prototype_key: str) -> int:
    """Count how many alive mobs of a given prototype are in the room."""
    if room is None:
        return 0
    count = 0
    for obj in room.contents:
        if not hasattr(obj, "attributes"):
            continue
        if not obj.attributes.get("is_mob", False):
            continue
        if not _mob_is_alive(obj):
            continue
        # Check if this mob matches the prototype by key prefix
        # (prototype key is used as part of the mob's key)
        if obj.key.lower().startswith(prototype_key.lower()):
            count += 1
        elif obj.attributes.get("prototype_key", "") == prototype_key:
            count += 1
    return count


def _auto_equip_spawned_mob(mob: Any, proto: dict) -> None:
    """
    Automatically equip a freshly spawned mob with level-appropriate gear.

    Called by ``spawn_mob()`` immediately after the mob is created.
    Generates a weapon, armor pieces, and coins based on the mob's
    level and class, then stores the equipped items on the mob.

    Args:
        mob: The newly created Mob instance.
        proto: The prototype dict used to create the mob.
    """
    try:
        from world.mob_equipment import equip_mob, generate_mob_coins

        # Determine mob class from prototype attrs
        mob_class = "Warrior"
        faction = "Neutral"
        attrs = proto.get("attrs", [])
        for attr in attrs:
            if attr[0] == "guild_class" or attr[0] == "mob_class":
                mob_class = attr[1]
            if attr[0] == "faction":
                faction = attr[1]

        # Equip the mob with weapons and armor
        equip_mob(mob, mob_class=mob_class, faction=faction)

        # Generate and store coin drops
        mob_level = mob.attributes.get("level", 1)
        coins = generate_mob_coins(mob_level)
        mob.attributes.add("copper_coins", coins.get("copper", 0))
        mob.attributes.add("silver_coins", coins.get("silver", 0))
        mob.attributes.add("gold_coins", coins.get("gold", 0))

        # Store prototype key for respawn tracking
        mob.attributes.add("prototype_key", proto.get("key", ""))

    except Exception:
        pass
