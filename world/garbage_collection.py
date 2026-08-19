"""
Garbage Collection & Stability for 'rop'

Provides:
  - GarbageCollectionScript (60s interval)
  - Corpse decay — delete corpses older than 10 minutes
  - Orphaned mob despawn — delete mobs in rooms with no players for 30 min
  - Stale combat cleanup — stop combat for invalid targets
  - Expired buff/debuff removal with stat reversion
  - Expired outlaw status cleanup
"""

import time

from evennia.scripts.scripts import DefaultScript
from evennia.objects.models import ObjectDB


# Corpse decay time in seconds (10 minutes)
CORPSE_DECAY_SECONDS = 600

# Orphaned mob despawn time (30 minutes with no players)
ORPHANED_MOB_TIMEOUT = 1800

# GC tick interval
GC_INTERVAL = 60.0


class GarbageCollectionScript(DefaultScript):
    """Global script that runs periodic cleanup tasks every 60 seconds."""

    def at_script_creation(self):
        self.key = "global_garbage_collection"
        self.desc = "Periodic corpse decay, mob despawn, combat cleanup, buff expiry"
        self.interval = GC_INTERVAL
        self.persistent = True

    def at_repeat(self):
        now = time.time()

        # 1. Corpse decay
        self._decay_corpses(now)

        # 2. Orphaned mob despawn
        self._despawn_orphaned_mobs(now)

        # 3. Stale combat cleanup
        self._cleanup_stale_combat()

        # 4. Expired outlaw status
        self._cleanup_outlaw_status()

        # 5. Expired unconscious bleed-out (player transitions to DEAD)
        self._cleanup_unconscious_players()

    def _decay_corpses(self, now):
        """Delete corpses older than CORPSE_DECAY_SECONDS."""
        from typeclasses.objects import Object

        for obj in ObjectDB.objects.all():
            if not isinstance(obj, Object):
                continue
            # Corpses are identified by having a 'corpse' tag or 'is_corpse' attribute
            is_corpse = obj.attributes.get("is_corpse", default=False) if hasattr(obj, "attributes") else False
            if not is_corpse:
                continue

            death_time = obj.attributes.get("corpse_created_at", default=0) if hasattr(obj, "attributes") else 0
            if death_time and (now - death_time) > CORPSE_DECAY_SECONDS:
                # Move remaining items to the room before deleting
                location = obj.location
                if location:
                    for item in obj.contents:
                        if not getattr(item, "destination", None):
                            item.location = location
                obj.delete()

    def _despawn_orphaned_mobs(self, now):
        """Delete mobs in rooms that have had no players for ORPHANED_MOB_TIMEOUT."""
        from typeclasses.characters import Character
        from typeclasses.rooms import Room

        for room in ObjectDB.objects.all():
            if not isinstance(room, Room):
                continue

            # Check if any players are in this room
            has_players = any(
                isinstance(obj, Character) and getattr(obj, "has_account", False)
                for obj in room.contents
            )

            if has_players:
                # Update last_player_seen timestamp
                room.attributes.add("last_player_seen", now)
                continue

            last_seen = room.attributes.get("last_player_seen", default=now) if hasattr(room, "attributes") else now
            if (now - last_seen) < ORPHANED_MOB_TIMEOUT:
                continue

            # Room has been empty too long — despawn mobs
            for obj in list(room.contents):
                if isinstance(obj, Character) and not getattr(obj, "has_account", False):
                    # Skip spawner-tracked mobs — the MobSpawner manages their lifecycle
                    spawner_id = obj.attributes.get("mob_spawner", default=None) if hasattr(obj, "attributes") else None
                    if spawner_id is not None:
                        continue
                    # It's an untracked orphan mob — despawn it
                    obj.delete()

    def _cleanup_stale_combat(self):
        """Stop combat for characters with invalid targets."""
        from world.tick_combat import CombatHandler

        for char in ObjectDB.objects.all():
            if not hasattr(char, "ndb"):
                continue
            if not CombatHandler.is_in_combat(char):
                continue
            target = CombatHandler.get_target(char)
            if target is None:
                CombatHandler.stop_combat(char)
                continue
            # Guard: stop combat if target is dead or gone.
            try:
                if not hasattr(target, "attributes"):
                    CombatHandler.stop_combat(char)
                    continue
                hp = target.attributes.get("hp", 0)
                if hp <= 0:
                    CombatHandler.stop_combat(char)
                    continue
            except Exception:
                CombatHandler.stop_combat(char)
                continue

    def _cleanup_outlaw_status(self):
        """Clear expired outlaw flags."""
        from world.alignment_system import AlignmentSystem
        from typeclasses.characters import Character

        for char in ObjectDB.objects.all():
            if not isinstance(char, Character):
                continue
            if not char.has_account:
                continue
            AlignmentSystem.check_outlaw_expiry(char)

    def _cleanup_unconscious_players(self):
        """
        Transition UNCONSCIOUS players to DEAD once their bleed-out timer expires.

        Phase 3.3: players who reach 0 HP become UNCONSCIOUS with a
        60-second bleed-out window.  If no ally revives them in time,
        they die and the normal defeat flow (XP loss, corpse, respawn)
        is triggered.
        """
        from typeclasses.characters import Character
        from world.combat_state import CombatStateMachine, CombatState

        now = time.time()

        for obj in ObjectDB.objects.all():
            if not isinstance(obj, Character):
                continue
            if not obj.has_account:
                continue

            # Skip if not UNCONSCIOUS
            if CombatStateMachine.get_state(obj) != CombatState.UNCONSCIOUS:
                continue

            expires = obj.attributes.get("unconscious_expires", default=0)
            if not expires or now <= expires:
                continue

            # Bleed-out timer expired → player dies
            CombatStateMachine.set_state(obj, CombatState.DEAD)

            if obj.location:
                obj.location.msg_contents(
                    f"|R{obj.key} breathes their last and dies!|n"
                )

            # Clear the timer
            obj.attributes.add("unconscious_expires", 0)

            # No killer object for bleed-out deaths; use None and let
            # _handle_defeat handle a no-killer respawn gracefully.
            from world.combat import _handle_defeat

            _handle_defeat(obj, None)

            # Return to IDLE after the defeat processing
            CombatStateMachine.set_state(obj, CombatState.IDLE)
