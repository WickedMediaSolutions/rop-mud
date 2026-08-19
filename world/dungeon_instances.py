"""
Dungeon Instance System for 'rop'
==================================

Provides private and group-based instanced dungeons.  Each party/player
gets their own copy of the dungeon, complete with fresh mobs, loot,
and boss spawns.  Instances are temporary and expire after a timeout
or when all players leave.

Features:
  - ``create_instance(blueprint, owner)`` — create a new dungeon instance
  - ``destroy_instance(instance_id)`` — clean up an expired instance
  - ``get_player_instance(player)`` — find the instance a player is in
  - ``list_active_instances()`` — list all live instances
  - ``DUNGEON_BLUEPRINTS`` — predefined dungeon templates

Blueprints define:
  - Room layout (list of room descriptors and exit connections)
  - Mob spawns per room
  - Boss room + boss prototype
  - Level range
  - Instance timeout (minutes)
  - Difficulty modifier

Usage (admin/command):
    from world.dungeon_instances import create_instance, DUNGEON_BLUEPRINTS
    result = create_instance("goblin_warrens", caller)
"""

from __future__ import annotations

import random
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from evennia import create_object
    from evennia.objects.models import ObjectDB
    from typeclasses.rooms import Room
    from typeclasses.exits import Exit
except Exception:
    create_object = None
    ObjectDB = None
    Room = None
    Exit = None


# ---------------------------------------------------------------------------
# Instance Tracking (in-memory, rebuilt on @reload via at_server_start)
# ---------------------------------------------------------------------------

# active_instances: {instance_id -> InstanceRecord}
_active_instances: Dict[str, "InstanceRecord"] = {}

# player_to_instance: {player.dbref -> instance_id}
_player_to_instance: Dict[int, str] = {}

# Instance timeout in seconds (30 minutes default)
DEFAULT_INSTANCE_TIMEOUT = 1800


class InstanceRecord:
    """Tracks a single dungeon instance's metadata."""

    def __init__(
        self,
        instance_id: str,
        blueprint_key: str,
        owner: Any,
        rooms: List[Any],
        boss_room: Optional[Any],
        created_at: float,
        timeout: int,
        is_group: bool = False,
        group_members: Optional[Set[int]] = None,
    ):
        self.instance_id = instance_id
        self.blueprint_key = blueprint_key
        self.owner_dbref = owner.id if owner is not None else -1
        self.rooms = rooms  # list of room objects
        self.boss_room = boss_room
        self.created_at = created_at
        self.timeout = timeout
        self.is_group = is_group
        self.group_members = group_members or set()
        self.destroyed = False

    def is_expired(self) -> bool:
        """Return True if this instance has exceeded its timeout."""
        return (time.time() - self.created_at) > self.timeout

    def add_player(self, player: Any) -> None:
        """Track a player entering this instance."""
        _player_to_instance[player.id] = self.instance_id
        if self.is_group:
            self.group_members.add(player.id)

    def remove_player(self, player: Any) -> None:
        """Track a player leaving this instance."""
        _player_to_instance.pop(player.id, None)
        if self.is_group:
            self.group_members.discard(player.id)

    @property
    def player_count(self) -> int:
        """Number of players currently in the instance."""
        count = 0
        for pid, iid in list(_player_to_instance.items()):
            if iid == self.instance_id:
                count += 1
        return count


# ---------------------------------------------------------------------------
# Dungeon Blueprints
# ---------------------------------------------------------------------------

# A blueprint is a dict defining a dungeon's structure.
# Rooms are defined as {key, desc, exits, mobs, is_boss_room, is_safe}
# Exits connect rooms using their position index (0-based) in the rooms list.

DUNGEON_BLUEPRINTS: Dict[str, Dict[str, Any]] = {
    "goblin_warrens": {
        "name": "Goblin Warrens",
        "level_min": 3,
        "level_max": 8,
        "timeout_minutes": 30,
        "difficulty": 1.0,
        "min_players": 1,
        "max_players": 5,
        "rooms": [
            {
                "key": "Goblin Warrens - Entrance",
                "desc": "A narrow, foul-smelling tunnel descends into the earth. Crude goblin markings are scratched into the walls, and the distant sound of chittering echoes from below.",
                "exits": {"down": 1},
                "mobs": [{"name": "Goblin Scout", "level": 3, "count": 2}],
                "is_boss_room": False,
                "is_safe": True,
            },
            {
                "key": "Goblin Warrens - Main Tunnel",
                "desc": "The tunnel opens into a wider passage, its floor littered with bones and refuse. Torches sputter in wall sconces, casting dancing shadows. Passages lead in multiple directions.",
                "exits": {"up": 0, "north": 2, "east": 3},
                "mobs": [{"name": "Goblin Warrior", "level": 5, "count": 3}],
                "is_boss_room": False,
            },
            {
                "key": "Goblin Warrens - Storeroom",
                "desc": "Crude shelves line the walls of this chamber, stacked with stolen goods — broken weapons, torn cloth, and a few glinting coins. The air is thick with the stench of goblin.",
                "exits": {"south": 1},
                "mobs": [{"name": "Goblin Scout", "level": 4, "count": 1}],
                "is_boss_room": False,
            },
            {
                "key": "Goblin Warrens - The Chief's Den",
                "desc": "A spacious cavern hung with trophies of past victims. At the far end, a massive goblin chieftain sits upon a throne of skulls, a wicked axe across his knees.",
                "exits": {"west": 1},
                "mobs": [{"name": "Goblin Chieftain", "level": 8, "count": 1}],
                "is_boss_room": True,
            },
        ],
    },
    "haunted_crypt": {
        "name": "Haunted Crypt",
        "level_min": 10,
        "level_max": 18,
        "timeout_minutes": 45,
        "difficulty": 1.3,
        "min_players": 1,
        "max_players": 5,
        "rooms": [
            {
                "key": "Haunted Crypt - Entrance",
                "desc": "A weathered stone door creaks open to reveal a dark staircase descending into the earth. Cold air, heavy with the smell of damp stone and decay, wafts upward.",
                "exits": {"down": 1},
                "mobs": [],
                "is_boss_room": False,
                "is_safe": True,
            },
            {
                "key": "Haunted Crypt - Burial Chamber",
                "desc": "Stone sarcophagi line the walls of this vast hall, their lids cracked and askew. Faint, ghostly light filters from somewhere above, and the air is deathly still.",
                "exits": {"up": 0, "north": 2, "east": 3},
                "mobs": [{"name": "Skeleton", "level": 10, "count": 3}, {"name": "Zombie", "level": 11, "count": 2}],
                "is_boss_room": False,
            },
            {
                "key": "Haunted Crypt - Treasure Vault",
                "desc": "This small chamber once held the crypt's riches. Now only a few tarnished coins and a shattered urn remain, guarded by restless spirits.",
                "exits": {"south": 1},
                "mobs": [{"name": "Wraith", "level": 14, "count": 2}],
                "is_boss_room": False,
            },
            {
                "key": "Haunted Crypt - Sarcophagus of the Lich",
                "desc": "At the heart of the crypt stands an ornate sarcophagus of black marble, pulsing with dark energy. The air crackles as the Lich rises to defend its domain.",
                "exits": {"west": 1},
                "mobs": [{"name": "Crypt Lich", "level": 18, "count": 1}],
                "is_boss_room": True,
            },
        ],
    },
    "spider_caverns": {
        "name": "Spider Caverns",
        "level_min": 20,
        "level_max": 30,
        "timeout_minutes": 45,
        "difficulty": 1.5,
        "min_players": 1,
        "max_players": 6,
        "rooms": [
            {
                "key": "Spider Caverns - Webbed Entrance",
                "desc": "Thick, sticky webbing covers the cave mouth. The air is warm and damp, carrying a faint skittering sound from deep within.",
                "exits": {"north": 1},
                "mobs": [{"name": "Cave Spider", "level": 20, "count": 3}],
                "is_boss_room": False,
                "is_safe": True,
            },
            {
                "key": "Spider Caverns - Egg Chamber",
                "desc": "Hundreds of pale, pulsating eggs cluster on the floor and walls. Workers scuttle about, tending the brood. The air is thick with a musty, organic smell.",
                "exits": {"south": 0, "east": 2, "west": 3},
                "mobs": [{"name": "Giant Spider", "level": 24, "count": 4}],
                "is_boss_room": False,
            },
            {
                "key": "Spider Caverns - Feeding Grounds",
                "desc": "Cocoons of silk-wrapped prey hang from the ceiling — some still twitching. The floor is littered with drained husks and shed exoskeletons.",
                "exits": {"west": 1},
                "mobs": [{"name": "Giant Spider", "level": 26, "count": 2}],
                "is_boss_room": False,
            },
            {
                "key": "Spider Caverns - The Broodmother's Lair",
                "desc": "A monstrous spider, bloated and ancient, dominates this vast chamber. Her many eyes glint with malevolent intelligence as she guards her eternal brood.",
                "exits": {"east": 1},
                "mobs": [{"name": "Broodmother Spider", "level": 30, "count": 1}],
                "is_boss_room": True,
            },
        ],
    },
    "dragon_lair": {
        "name": "Dragon's Lair",
        "level_min": 50,
        "level_max": 65,
        "timeout_minutes": 60,
        "difficulty": 2.5,
        "min_players": 2,
        "max_players": 8,
        "rooms": [
            {
                "key": "Dragon's Lair - Mountain Entrance",
                "desc": "A massive cave mouth gapes in the mountainside, its edges scorched black. Heat radiates from within, and the ground trembles with a low, rumbling snore.",
                "exits": {"north": 1},
                "mobs": [{"name": "Fire Elemental", "level": 50, "count": 2}],
                "is_boss_room": False,
                "is_safe": True,
            },
            {
                "key": "Dragon's Lair - Treasure Passage",
                "desc": "The tunnel widens into a glittering hall. Gold coins, gems, and artifacts are heaped in careless mounds. Several smaller drakes slumber amid the treasure.",
                "exits": {"south": 0, "north": 2, "east": 3},
                "mobs": [{"name": "Drake", "level": 55, "count": 3}],
                "is_boss_room": False,
            },
            {
                "key": "Dragon's Lair - Magma Chamber",
                "desc": "A river of molten rock splits this chamber in two. The heat is nearly unbearable, and the air shimmers. Only a narrow stone bridge crosses the magma.",
                "exits": {"south": 1},
                "mobs": [{"name": "Hellhound", "level": 60, "count": 2}],
                "is_boss_room": False,
            },
            {
                "key": "Dragon's Lair - The Hoard Chamber",
                "desc": "The great dragon lies coiled upon a mountain of treasure, smoke curling from its nostrils. One eye opens — you have been noticed.",
                "exits": {"west": 1},
                "mobs": [{"name": "Elder Dragon", "level": 65, "count": 1}],
                "is_boss_room": True,
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Instance Creation
# ---------------------------------------------------------------------------

def _generate_instance_id() -> str:
    """Generate a unique instance identifier."""
    return f"inst_{uuid.uuid4().hex[:12]}"


def _create_room(key: str, desc: str, is_safe: bool = False) -> Any:
    """Create a single instanced room."""
    if Room is None or create_object is None:
        return None
    room = create_object(Room, key=key)
    if room:
        room.db.desc = desc
        if is_safe:
            room.attributes.add("safe_zone", True)
        room.attributes.add("is_instance_room", True)
    return room


def _spawn_instance_mobs(room: Any, mob_defs: List[Dict[str, Any]], level_mult: float = 1.0):
    """Spawn mobs in an instance room."""
    if not mob_defs:
        return
    try:
        from world.mob_ai import spawn_mob
        for mob_def in mob_defs:
            count = mob_def.get("count", 1)
            for _ in range(count):
                level = int(mob_def["level"] * level_mult)
                level = max(1, level)
                spawn_mob(
                    room,
                    name=mob_def["name"],
                    level=level,
                    faction=mob_def.get("faction", "Neutral"),
                    aggro=mob_def.get("aggro", True),
                )
    except Exception:
        pass


def create_instance(
    blueprint_key: str,
    owner: Any,
    group_members: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Create a new dungeon instance from a blueprint.

    Args:
        blueprint_key: Key in DUNGEON_BLUEPRINTS.
        owner: The player creating the instance.
        group_members: Optional list of other players to share with.

    Returns:
        {"success": bool, "instance_id": str, "rooms": [...], "error": str}
    """
    blueprint = DUNGEON_BLUEPRINTS.get(blueprint_key)
    if blueprint is None:
        return {"success": False, "instance_id": "", "rooms": [],
                "error": f"Unknown blueprint: {blueprint_key}"}

    # Check if player already has an active instance
    existing = get_player_instance(owner)
    if existing:
        return {"success": False, "instance_id": "", "rooms": [],
                "error": "You are already in an active dungeon instance. Leave it first."}

    if create_object is None:
        return {"success": False, "instance_id": "", "rooms": [],
                "error": "Evennia not available — cannot create rooms."}

    rooms = blueprint["rooms"]
    instance_id = _generate_instance_id()
    created_rooms: List[Any] = []
    boss_room: Optional[Any] = None
    is_group = bool(group_members)
    member_set: Set[int] = set()

    # Create all rooms
    room_objects: List[Any] = []
    for i, room_def in enumerate(rooms):
        room = _create_room(
            f"{room_def['key']} [{instance_id}]",
            room_def["desc"],
            room_def.get("is_safe", False),
        )
        if room is None:
            # Cleanup on failure
            for r in created_rooms:
                try:
                    r.delete()
                except Exception:
                    pass
            return {"success": False, "instance_id": "", "rooms": [],
                    "error": f"Failed to create room {i}"}
        room_objects.append(room)
        created_rooms.append(room)

    # Create exits between rooms
    for i, room_def in enumerate(rooms):
        source_room = room_objects[i]
        for direction, target_idx in room_def["exits"].items():
            target_room = room_objects[target_idx]
            try:
                # Create forward exit
                create_object(Exit, key=direction, location=source_room,
                              destination=target_room)
                # Create reverse exit
                from typeclasses.exits import get_opposite
                reverse = get_opposite(direction)
                if reverse:
                    create_object(Exit, key=reverse, location=target_room,
                                  destination=source_room)
            except Exception:
                pass

    # Spawn mobs
    level_mult = blueprint.get("difficulty", 1.0)
    for i, room_def in enumerate(rooms):
        room = room_objects[i]
        _spawn_instance_mobs(room, room_def.get("mobs", []), level_mult)
        if room_def.get("is_boss_room"):
            boss_room = room

    # Link entrance to caller's current room
    entrance = room_objects[0]
    try:
        caller_room = owner.location
        if caller_room:
            create_object(Exit, key="enter dungeon", location=caller_room,
                          destination=entrance)
    except Exception:
        pass

    # Create return exit from entrance back to caller's room
    try:
        caller_room = owner.location
        if caller_room:
            create_object(Exit, key="leave dungeon", location=entrance,
                          destination=caller_room)
    except Exception:
        pass

    # Register the instance
    record = InstanceRecord(
        instance_id=instance_id,
        blueprint_key=blueprint_key,
        owner=owner,
        rooms=created_rooms,
        boss_room=boss_room,
        created_at=time.time(),
        timeout=blueprint["timeout_minutes"] * 60,
        is_group=is_group,
        group_members=member_set,
    )
    _active_instances[instance_id] = record
    record.add_player(owner)

    # Add group members
    if group_members:
        for member in group_members:
            if member != owner:
                record.add_player(member)

    # Move the owner into the entrance
    try:
        owner.move_to(entrance)
    except Exception:
        pass

    return {
        "success": True,
        "instance_id": instance_id,
        "rooms": created_rooms,
        "error": "",
    }


def destroy_instance(instance_id: str) -> bool:
    """Destroy an instance and clean up all its rooms/mobs."""
    record = _active_instances.pop(instance_id, None)
    if record is None:
        return False

    record.destroyed = True

    # Remove all player references
    for pid, iid in list(_player_to_instance.items()):
        if iid == instance_id:
            del _player_to_instance[pid]

    # Move any remaining players out, then delete rooms
    for room in record.rooms:
        try:
            # Teleport any players still inside to their recall point
            for obj in list(room.contents):
                if obj.has_account:
                    try:
                        recall = obj.attributes.get("recall_room")
                        if recall:
                            obj.move_to(recall)
                        else:
                            # Try faction hub
                            obj.home and obj.move_to(obj.home)
                    except Exception:
                        pass
            room.delete()
        except Exception:
            pass

    return True


def get_player_instance(player: Any) -> Optional[InstanceRecord]:
    """Return the instance record for a player, or None."""
    iid = _player_to_instance.get(player.id)
    if iid:
        return _active_instances.get(iid)
    return None


def list_active_instances() -> List[Dict[str, Any]]:
    """Return summary info for all active instances."""
    results = []
    now = time.time()
    for iid, record in list(_active_instances.items()):
        remaining = int(record.timeout - (now - record.created_at))
        if remaining <= 0:
            destroy_instance(iid)
            continue
        results.append({
            "instance_id": iid,
            "blueprint": record.blueprint_key,
            "players": record.player_count,
            "created_ago": int(now - record.created_at),
            "remaining": remaining,
            "is_group": record.is_group,
        })
    return results


def cleanup_expired_instances() -> int:
    """Destroy all expired instances. Returns count destroyed."""
    count = 0
    for iid in list(_active_instances.keys()):
        record = _active_instances.get(iid)
        if record and record.is_expired():
            destroy_instance(iid)
            count += 1
    return count


# ---------------------------------------------------------------------------
# Instance command helpers (for use by command modules)
# ---------------------------------------------------------------------------

def cmd_create_instance(caller: Any, args: str) -> str:
    """Handle '@dungeon create <blueprint>' command."""
    blueprint_key = args.strip().lower()
    if not blueprint_key:
        available = ", ".join(DUNGEON_BLUEPRINTS.keys())
        return f"Available dungeons: {available}"

    if blueprint_key not in DUNGEON_BLUEPRINTS:
        return f"Unknown dungeon. Available: {', '.join(DUNGEON_BLUEPRINTS.keys())}"

    bp = DUNGEON_BLUEPRINTS[blueprint_key]
    level = caller.attributes.get("level", 1)
    if level < bp["level_min"]:
        return (f"You must be at least level {bp['level_min']} to enter "
                f"{bp['name']}. You are level {level}.")
    if level > bp["level_max"] + 10:
        return f"Your level ({level}) is too high for {bp['name']} (max {bp['level_max']})."

    result = create_instance(blueprint_key, caller)
    if result["success"]:
        return f"You enter the {bp['name']} dungeon instance!"
    return result.get("error", "Failed to create dungeon instance.")


def cmd_leave_instance(caller: Any) -> str:
    """Handle '@dungeon leave' command."""
    record = get_player_instance(caller)
    if record is None:
        return "You are not in a dungeon instance."

    record.remove_player(caller)

    # Move to caller's home or safe location
    try:
        recall = caller.attributes.get("recall_room")
        if recall:
            caller.move_to(recall)
            msg = "You leave the dungeon and return to your recall point."
        else:
            msg = "You leave the dungeon."
    except Exception:
        msg = "You leave the dungeon."

    # If no players left, destroy
    if record.player_count == 0:
        destroy_instance(record.instance_id)

    return msg


def cmd_list_instances(caller: Any) -> str:
    """Handle '@dungeon list' command."""
    active = list_active_instances()
    if not active:
        return "No active dungeon instances."

    lines = ["|cActive Dungeon Instances:|n"]
    for inst in active:
        minutes = inst["remaining"] // 60
        lines.append(
            f"  {inst['instance_id'][:20]}... — {inst['blueprint']} "
            f"({inst['players']} players, {minutes}min remaining)"
        )
    return "\n".join(lines)


def get_active_instances_map() -> Dict[str, "InstanceRecord"]:
    """Return a copy of the active instances map (for persistence/system checks)."""
    return dict(_active_instances)