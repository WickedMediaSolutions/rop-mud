"""
Raid Mechanics System for 'rop'
================================
Provides advanced PvE boss encounter mechanics:
  - Multi-phase boss fights with transitions
  - Enrage timers (soft and hard)
  - Telegraphed abilities (dodgeable ground effects)
  - Multi-target mechanics (adds, split damage, tank swaps)
  - Raid lockouts and cooldowns

Usage:
  from world.raid_mechanics import RaidBoss, RaidManager, RaidEncounter
"""

from __future__ import annotations

import random
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from evennia import create_object, search_object
    from evennia.objects.models import ObjectDB
except Exception:
    create_object = None
    search_object = None
    ObjectDB = None


# ===========================================================================
# RAID BOSS PHASES
# ===========================================================================

class BossPhase:
    """Defines a single boss phase with its own abilities and triggers."""

    def __init__(self, phase_id: str, name: str, hp_threshold: float,
                 duration: Optional[int] = None):
        """
        Args:
            phase_id: Unique phase identifier.
            name: Display name of the phase.
            hp_threshold: HP percentage (0-100) at which this phase starts.
            duration: Optional max duration in seconds. None = until next threshold.
        """
        self.phase_id = phase_id
        self.name = name
        self.hp_threshold = hp_threshold
        self.duration = duration
        self.abilities: List[Dict[str, Any]] = []
        self.entry_message = f"|R|h{name} begins!|n"
        self.exit_message = ""

    def add_ability(self, name: str, ability_type: str, damage: int = 0,
                    cooldown: int = 10, target_type: str = "single",
                    telegraph_time: int = 3, extra: Optional[Dict] = None):
        """
        Add an ability to this phase.

        Args:
            name: Ability display name.
            ability_type: "damage", "aoe", "stun", "heal", "summon_adds", "enrage".
            damage: Base damage (if applicable).
            cooldown: Seconds between casts.
            target_type: "single", "aoe", "random", "tank", "healer".
            telegraph_time: Seconds of warning before the ability fires.
            extra: Additional params (radius, dot_duration, etc).
        """
        self.abilities.append({
            "name": name,
            "type": ability_type,
            "damage": damage,
            "cooldown": cooldown,
            "target_type": target_type,
            "telegraph_time": telegraph_time,
            "extra": extra or {},
            "last_cast": 0,
        })
        return self

    def is_ready(self, ability: Dict, now: float) -> bool:
        """Check if an ability is off cooldown."""
        return (now - ability["last_cast"]) >= ability["cooldown"]


class RaidBoss:
    """
    Represents a raid boss with multi-phase mechanics, enrage timers,
    and telegraphed abilities.
    """

    def __init__(self, boss_id: str, name: str, level: int, max_hp: int,
                 max_damage: int, tier: str = "epic"):
        self.boss_id = boss_id
        self.name = name
        self.level = level
        self.max_hp = max_hp
        self.max_damage = max_damage
        self.tier = tier
        self.phases: List[BossPhase] = []
        self.current_phase_idx = 0
        self.current_phase: Optional[BossPhase] = None
        self.enrage_timer_soft: Optional[int] = None  # seconds
        self.enrage_timer_hard: Optional[int] = None  # seconds
        self.enrage_started_at: Optional[float] = None
        self.is_enraged = False
        self.is_hard_enraged = False
        self.adds: List[Any] = []  # summoned adds
        self.fight_started_at: Optional[float] = None
        self.raid_instance_id: Optional[str] = None
        self.defeated = False

    def add_phase(self, phase: BossPhase) -> "RaidBoss":
        """Add a phase to the boss fight."""
        self.phases.append(phase)
        # Sort phases by hp_threshold descending (start at 100%)
        self.phases.sort(key=lambda p: p.hp_threshold, reverse=True)
        return self

    def set_enrage_timers(self, soft: int = 480, hard: int = 600) -> "RaidBoss":
        """Set enrage timers in seconds."""
        self.enrage_timer_soft = soft
        self.enrage_timer_hard = hard
        return self

    def start_fight(self) -> str:
        """Start the boss fight and enter the first phase."""
        self.fight_started_at = time.time()
        self.enrage_started_at = time.time()
        self.current_phase_idx = 0
        if self.phases:
            self.current_phase = self.phases[0]
            return self.enter_phase(0)
        return f"{self.name} does not have any phases defined."

    def enter_phase(self, phase_idx: int) -> str:
        """Enter a specific phase and announce it."""
        if phase_idx >= len(self.phases):
            return "Invalid phase."

        self.current_phase_idx = phase_idx
        self.current_phase = self.phases[phase_idx]
        return self.current_phase.entry_message

    def check_phase_transition(self, hp_percent: float) -> Optional[str]:
        """
        Check if the boss should transition to a new phase based on HP.

        Args:
            hp_percent: Current HP percentage (0-100).

        Returns:
            Transition message if a new phase starts, else None.
        """
        if self.defeated:
            return None

        # Check phases from highest index (lowest threshold) to current
        for idx, phase in enumerate(self.phases):
            if hp_percent <= phase.hp_threshold and idx > self.current_phase_idx:
                return self.enter_phase(idx)

        return None

    def get_phase_abilities(self) -> List[Dict[str, Any]]:
        """Get abilities for the current phase."""
        if not self.current_phase:
            return []
        return self.current_phase.abilities

    def check_enrage(self) -> str:
        """
        Check if the boss has reached enrage timers.

        Returns:
            Enrage message if triggered, else empty string.
        """
        if self.enrage_started_at is None:
            return ""

        elapsed = time.time() - self.enrage_started_at

        if (self.enrage_timer_hard and elapsed >= self.enrage_timer_hard
                and not self.is_hard_enraged):
            self.is_hard_enraged = True
            self.is_enraged = True
            return f"|R|h{self.name} enters a FRENZIED state! Damage massively increased!|n"

        if (self.enrage_timer_soft and elapsed >= self.enrage_timer_soft
                and not self.is_enraged):
            self.is_enraged = True
            return f"|R|h{self.name} is ENRAGED! Its attacks grow more powerful!|n"

        return ""

    def get_enrage_damage_multiplier(self) -> float:
        """Get damage multiplier from enrage state."""
        if self.is_hard_enraged:
            return 3.0
        if self.is_enraged:
            return 1.75
        return 1.0

    def summon_adds(self, add_name: str, count: int, level: int,
                    hp: int, damage: int) -> List[Any]:
        """Summon adds during the fight."""
        new_adds = []
        for _ in range(count):
            adds = self.adds
            add = {
                "name": add_name,
                "level": level,
                "hp": hp,
                "max_hp": hp,
                "damage": damage,
                "is_add": True,
                "summoned_at": time.time(),
            }
            new_adds.append(add)
        self.adds.extend(new_adds)
        return new_adds

    def get_alive_adds(self) -> List[Any]:
        """Get all currently alive adds."""
        return [add for add in self.adds if add.get("hp", 0) > 0]

    def defeat(self) -> str:
        """Mark the boss as defeated and clean up."""
        self.defeated = True
        self.adds = []
        return f"|Y|h{self.name} has been defeated!|n"


# ===========================================================================
# RAID INSTANCE
# ===========================================================================

class RaidInstance:
    """Represents a single raid group's instance of a raid encounter."""

    def __init__(self, raid_id: str, raid_name: str, boss: RaidBoss,
                 min_players: int = 5, max_players: int = 20,
                 min_level: int = 1, recommended_level: int = 50,
                 lockout_hours: int = 7 * 24):
        self.raid_id = raid_id
        self.raid_name = raid_name
        self.boss = boss
        self.min_players = min_players
        self.max_players = max_players
        self.min_level = min_level
        self.recommended_level = recommended_level
        self.lockout_hours = lockout_hours
        self.members: List[Any] = []
        self.leader: Optional[Any] = None
        self.status = "forming"  # forming, ready, active, completed, failed
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.ended_at: Optional[float] = None
        self.raid_room: Any = None
        self.deaths: int = 0
        self.attempts: int = 0

    @property
    def player_count(self) -> int:
        return len(self.members)

    def add_member(self, character: Any) -> Tuple[bool, str]:
        """Add a player to the raid group."""
        if self.status != "forming":
            return False, "This raid has already started."
        if len(self.members) >= self.max_players:
            return False, "Raid group is full."
        if character in self.members:
            return False, "You are already in this raid."

        char_level = character.attributes.get("level", default=1)
        if char_level < self.min_level:
            return False, f"You must be level {self.min_level} to join this raid."

        self.members.append(character)
        if self.leader is None:
            self.leader = character
        return True, f"Joined {self.raid_name} raid."

    def remove_member(self, character: Any) -> Tuple[bool, str]:
        """Remove a player from the raid group."""
        if character not in self.members:
            return False, "You are not in this raid."
        self.members.remove(character)
        if character == self.leader and self.members:
            self.leader = self.members[0]
        elif character == self.leader:
            self.leader = None
        return True, f"Left {self.raid_name} raid."

    def start(self) -> Tuple[bool, str]:
        """Start the raid encounter."""
        if self.status != "forming":
            return False, "Raid has already started."
        if self.player_count < self.min_players:
            return False, f"Need at least {self.min_players} players. Currently {self.player_count}."

        self.status = "active"
        self.started_at = time.time()
        self.attempts += 1
        return True, f"{self.raid_name} has begun!"

    def end(self, result: str = "completed") -> str:
        """End the raid encounter."""
        self.status = result
        self.ended_at = time.time()
        if result == "completed":
            return f"|Y|h{self.raid_name} completed!|n"
        elif result == "failed":
            return f"|r{self.raid_name} failed. Better luck next time!|n"
        return f"{self.raid_name} ended."

    @property
    def duration_seconds(self) -> int:
        if self.started_at is None:
            return 0
        end = self.ended_at or time.time()
        return int(end - self.started_at)


# ===========================================================================
# RAID MANAGER (includes Dungeon Finder / Group Queue)
# ===========================================================================

class RaidManager:
    """
    Manages raid instances and group queuing.

    Also provides the Dungeon Finder / Group Queue system:
      - Players queue for dungeons/raids by level range
      - Auto-group when enough players match
      - Role assignment (tank/dps/healer)
    """

    def __init__(self):
        self._raid_instances: Dict[str, RaidInstance] = {}
        self._player_raid: Dict[int, str] = {}  # dbref -> raid_id
        self._raid_templates: Dict[str, RaidBoss] = {}
        self._dungeon_queue: List[Dict[str, Any]] = []  # queued players
        self._group_queue: Dict[str, List[Any]] = {
            "tank": [],
            "dps": [],
            "healer": [],
        }
        self._raid_lockouts: Dict[int, Dict[str, float]] = {}  # dbref -> {raid_id: unlock_at}

    # ---- Raid Templates ----

    def register_raid_template(self, raid_id: str, boss: RaidBoss,
                               raid_name: str, min_players: int = 5,
                               max_players: int = 20, min_level: int = 1,
                               recommended_level: int = 50,
                               lockout_hours: int = 168) -> None:
        """Register a raid template."""
        self._raid_templates[raid_id] = boss
        boss.raid_name = raid_name
        boss.min_players = min_players
        boss.max_players = max_players
        boss.min_level = min_level
        boss.recommended_level = recommended_level
        boss.lockout_hours = lockout_hours

    def list_raid_templates(self) -> List[Dict[str, Any]]:
        """List all available raid templates."""
        result = []
        for raid_id, boss in self._raid_templates.items():
            result.append({
                "raid_id": raid_id,
                "name": getattr(boss, "raid_name", raid_id),
                "boss": boss.name,
                "level": boss.level,
                "min_players": getattr(boss, "min_players", 5),
                "max_players": getattr(boss, "max_players", 20),
                "recommended_level": getattr(boss, "recommended_level", boss.level),
                "tier": boss.tier,
            })
        return result

    # ---- Raid Instance Management ----

    def create_raid(self, raid_id: str, leader: Any) -> Tuple[bool, str]:
        """Create a new raid instance from a template."""
        boss = self._raid_templates.get(raid_id)
        if not boss:
            return False, f"Unknown raid: {raid_id}"

        # Check lockout
        if not self._check_lockout(leader, raid_id):
            return False, f"You are locked out of {boss.name}. Raid lockout active."

        raid_inst_id = f"raid_{uuid.uuid4().hex[:8]}"
        instance = RaidInstance(
            raid_inst_id,
            getattr(boss, "raid_name", raid_id),
            boss,
            min_players=getattr(boss, "min_players", 5),
            max_players=getattr(boss, "max_players", 20),
            min_level=getattr(boss, "min_level", 1),
            recommended_level=getattr(boss, "recommended_level", boss.level),
            lockout_hours=getattr(boss, "lockout_hours", 168),
        )
        self._raid_instances[raid_inst_id] = instance
        ok, msg = instance.add_member(leader)
        if ok:
            self._player_raid[leader.id] = raid_inst_id
        else:
            del self._raid_instances[raid_inst_id]
        return ok, f"Raid instance created: {instance.raid_name}" if ok else msg

    def join_raid(self, character: Any, raid_inst_id: str) -> Tuple[bool, str]:
        """Join an existing raid instance."""
        instance = self._raid_instances.get(raid_inst_id)
        if not instance:
            return False, "Raid instance not found."

        ok, msg = instance.add_member(character)
        if ok:
            self._player_raid[character.id] = raid_inst_id
        return ok, msg

    def leave_raid(self, character: Any) -> Tuple[bool, str]:
        """Leave the current raid."""
        raid_id = self._player_raid.get(character.id)
        if not raid_id:
            return False, "You are not in a raid."

        instance = self._raid_instances.get(raid_id)
        if instance:
            ok, msg = instance.remove_member(character)
            self._player_raid.pop(character.id, None)
            if instance.player_count == 0:
                del self._raid_instances[raid_id]
            return ok, msg
        return False, "Raid instance not found."

    def get_player_raid(self, character: Any) -> Optional[RaidInstance]:
        """Get the raid instance a player is in."""
        raid_id = self._player_raid.get(character.id)
        if raid_id:
            return self._raid_instances.get(raid_id)
        return None

    def list_raid_instances(self) -> List[Dict[str, Any]]:
        """List all forming/active raid instances."""
        result = []
        for raid in self._raid_instances.values():
            if raid.status in ("forming", "active"):
                result.append({
                    "raid_id": raid.raid_id,
                    "name": raid.raid_name,
                    "boss": raid.boss.name,
                    "status": raid.status,
                    "players": raid.player_count,
                    "min_players": raid.min_players,
                    "max_players": raid.max_players,
                    "leader": raid.leader.key if raid.leader else "None",
                })
        return result

    # ---- Lockouts ----

    def _check_lockout(self, character: Any, raid_id: str) -> bool:
        """Check if a player is locked out of a raid."""
        lockouts = self._raid_lockouts.get(character.id, {})
        unlock_at = lockouts.get(raid_id, 0)
        return time.time() >= unlock_at

    def apply_lockout(self, character: Any, raid_id: str, hours: int = 168) -> None:
        """Apply a raid lockout to a player."""
        lockouts = self._raid_lockouts.get(character.id, {})
        lockouts[raid_id] = time.time() + (hours * 3600)
        self._raid_lockouts[character.id] = lockouts

    def get_lockout_time(self, character: Any, raid_id: str) -> int:
        """Get remaining lockout time in seconds."""
        lockouts = self._raid_lockouts.get(character.id, {})
        unlock_at = lockouts.get(raid_id, 0)
        return max(0, int(unlock_at - time.time()))

    # ---- Dungeon Finder / Group Queue ----

    def queue_dungeon(self, character: Any, role: str = "dps") -> Tuple[bool, str]:
        """
        Add a player to the dungeon finder queue.

        Args:
            character: The player queuing.
            role: "tank", "dps", or "healer".

        Returns:
            (success, message)
        """
        if role not in ("tank", "dps", "healer"):
            return False, "Invalid role. Choose tank, dps, or healer."

        # Remove from any existing queue
        self.dequeue_dungeon(character)

        char_level = character.attributes.get("level", default=1)
        self._dungeon_queue.append({
            "character": character,
            "role": role,
            "level": char_level,
            "queued_at": time.time(),
        })
        self._group_queue[role].append(character)

        character.msg(f"|g[Dungeon Finder] You have queued as {role.upper()}. "
                      f"({len(self._dungeon_queue)} player(s) in queue)|n")

        # Try to form a group
        self._try_form_dungeon_group()

        return True, f"Queued for dungeon as {role.upper()}."

    def dequeue_dungeon(self, character: Any) -> Tuple[bool, str]:
        """Remove a player from the dungeon finder queue."""
        removed = False
        for entry in list(self._dungeon_queue):
            if entry["character"] == character:
                self._dungeon_queue.remove(entry)
                removed = True

        for role in ("tank", "dps", "healer"):
            if character in self._group_queue[role]:
                self._group_queue[role].remove(character)
                removed = True

        if not removed:
            return False, "You are not in the dungeon queue."
        character.msg(f"|y[Dungeon Finder] You have left the queue.|n")
        return True, "Left the dungeon queue."

    def _try_form_dungeon_group(self) -> Optional[Dict[str, Any]]:
        """Try to form a dungeon group (1 tank, 3 dps, 1 healer)."""
        if (len(self._group_queue["tank"]) >= 1
                and len(self._group_queue["dps"]) >= 3
                and len(self._group_queue["healer"]) >= 1):
            tank = self._group_queue["tank"].pop(0)
            dps = [self._group_queue["dps"].pop(0) for _ in range(3)]
            healer = self._group_queue["healer"].pop(0)

            group = {
                "tank": tank,
                "dps": dps,
                "healer": healer,
                "formed_at": time.time(),
                "group_id": f"dungeon_group_{uuid.uuid4().hex[:8]}",
            }

            # Remove from queue
            for entry in list(self._dungeon_queue):
                for member in [tank] + dps + [healer]:
                    if entry["character"] == member:
                        self._dungeon_queue.remove(entry)

            # Notify all members
            names = [tank.key] + [d.key for d in dps] + [healer.key]
            for member in [tank] + dps + [healer]:
                member.msg(
                    f"|Y|h[Dungeon Finder] Group formed!|n\n"
                    f"|wTank: {tank.key}|n\n"
                    f"|wDPS: {', '.join(d.key for d in dps)}|n\n"
                    f"|wHealer: {healer.key}|n"
                )
                member.msg("|gA dungeon instance will be created for your group.|n")

            # Auto-create a dungeon instance for the group
            self._auto_create_dungeon_for_group(group)

            return group
        return None

    def _auto_create_dungeon_for_group(self, group: Dict[str, Any]) -> None:
        """Auto-create a dungeon instance for a formed group."""
        try:
            from world.dungeon_instances import create_instance, DUNGEON_BLUEPRINTS

            # Pick a dungeon based on average level
            avg_level = sum(
                member.attributes.get("level", 1)
                for member in [group["tank"]] + group["dps"] + [group["healer"]]
            ) // 5

            blueprint_key = None
            for key, bp in DUNGEON_BLUEPRINTS.items():
                if bp["level_min"] <= avg_level <= bp["level_max"] + 10:
                    blueprint_key = key
                    break

            if blueprint_key:
                all_members = [group["tank"]] + group["dps"] + [group["healer"]]
                result = create_instance(blueprint_key, group["tank"], group_members=all_members[1:])
                if result["success"]:
                    for member in all_members:
                        member.msg(
                            f"|g[Dungeon Finder] You have been placed in the "
                            f"{DUNGEON_BLUEPRINTS[blueprint_key]['name']} instance!|n"
                        )
        except Exception:
            pass

    def get_queue_status(self) -> Dict[str, int]:
        """Get dungeon finder queue counts by role."""
        return {
            "tank": len(self._group_queue["tank"]),
            "dps": len(self._group_queue["dps"]),
            "healer": len(self._group_queue["healer"]),
            "total": len(self._dungeon_queue),
        }


# Global raid manager
raid_manager = RaidManager()


# ===========================================================================
# DEFAULT RAID ENCOUNTERS
# ===========================================================================

def register_default_raids():
    """Register the default raid encounters."""
    # --- Raid 1: The Obsidian Citadel (Level 30-40) ---
    boss1 = RaidBoss("obsidian_citadel", "Obsidian Warlord Kael", 40, 50000, 150, "epic")
    boss1.set_enrage_timers(soft=420, hard=540)

    phase1 = BossPhase("p1", "Phase 1: Reign of Fire", 100)
    phase1.add_ability("Fireball Volley", "aoe", damage=120, cooldown=15, target_type="aoe", telegraph_time=3)
    phase1.add_ability("Searing Strike", "damage", damage=200, cooldown=8, target_type="tank", telegraph_time=2)
    phase1.add_ability("Flame Patch", "damage", damage=80, cooldown=12, target_type="random", telegraph_time=4, extra={"dot_duration": 8})
    phase1.entry_message = "|R|hObsidian Warlord Kael raises his molten blade! Fire rains from above!|n"

    phase2 = BossPhase("p2", "Phase 2: Call of the Legion", 50)
    phase2.add_ability("Summon Fire Elementals", "summon_adds", cooldown=25, target_type="aoe", telegraph_time=5, extra={"add_name": "Fire Elemental", "add_count": 3, "add_level": 35, "add_hp": 5000, "add_damage": 60})
    phase2.add_ability("Infernal Cleave", "aoe", damage=180, cooldown=10, target_type="aoe", telegraph_time=3)
    phase2.add_ability("Molten Armor", "heal", cooldown=30, target_type="self", telegraph_time=0, extra={"heal_amount": 5000})
    phase2.entry_message = "|Y|hKael slams his fist into the ground! 'Rise, my legion!'|n"

    phase3 = BossPhase("p3", "Phase 3: Annihilation", 25)
    phase3.add_ability("Meteor Shower", "aoe", damage=250, cooldown=18, target_type="aoe", telegraph_time=5)
    phase3.add_ability("Warlord's Wrath", "damage", damage=350, cooldown=8, target_type="tank", telegraph_time=2)
    phase3.add_ability("Lava Eruption", "aoe", damage=150, cooldown=14, target_type="random", telegraph_time=4, extra={"radius": 2})
    phase3.entry_message = "|R|h'ENOUGH! You will all BURN!' Kael enters a state of pure rage!|n"

    boss1.add_phase(phase1)
    boss1.add_phase(phase2)
    boss1.add_phase(phase3)
    raid_manager.register_raid_template("obsidian_citadel", boss1, "The Obsidian Citadel", min_players=5, max_players=15, min_level=30, recommended_level=40)

    # --- Raid 2: The Frozen Throne (Level 45-55) ---
    boss2 = RaidBoss("frozen_throne", "Frost Queen Seraphine", 55, 80000, 200, "legendary")
    boss2.set_enrage_timers(soft=480, hard=600)

    phase1 = BossPhase("p1", "Phase 1: Glacial Storm", 100)
    phase1.add_ability("Ice Shard Barrage", "aoe", damage=180, cooldown=12, target_type="aoe", telegraph_time=3)
    phase1.add_ability("Freezing Touch", "stun", damage=50, cooldown=15, target_type="random", telegraph_time=2, extra={"stun_duration": 3})
    phase1.add_ability("Frost Nova", "aoe", damage=200, cooldown=20, target_type="aoe", telegraph_time=4)
    phase1.entry_message = "|C|hThe Frost Queen rises from her throne, a blizzard howling around her!|n"

    phase2 = BossPhase("p2", "Phase 2: Winter's Embrace", 40)
    phase2.add_ability("Summon Ice Golems", "summon_adds", cooldown=22, target_type="aoe", telegraph_time=5, extra={"add_name": "Ice Golem", "add_count": 2, "add_level": 42, "add_hp": 8000, "add_damage": 70})
    phase2.add_ability("Permafrost", "aoe", damage=220, cooldown=14, target_type="aoe", telegraph_time=3)
    phase2.add_ability("Hypothermia", "dot", damage=100, cooldown=10, target_type="random", telegraph_time=2, extra={"dot_duration": 12})
    phase2.entry_message = "|C|h'Feel winter's eternal cold!' Seraphine summons her frozen minions!|n"

    boss2.add_phase(phase1)
    boss2.add_phase(phase2)
    raid_manager.register_raid_template("frozen_throne", boss2, "The Frozen Throne", min_players=8, max_players=20, min_level=45, recommended_level=55)

    # --- Raid 3: The Void Threshold (Level 60-80) ---
    boss3 = RaidBoss("void_threshold", "The Void World-Eater", 80, 150000, 300, "legendary")
    boss3.set_enrage_timers(soft=600, hard=720)

    phase1 = BossPhase("p1", "Phase 1: Cosmic Hunger", 100)
    phase1.add_ability("Void Bolt Volley", "aoe", damage=300, cooldown=15, target_type="aoe", telegraph_time=4)
    phase1.add_ability("Reality Rend", "damage", damage=450, cooldown=9, target_type="tank", telegraph_time=3)
    phase1.add_ability("Singularity", "aoe", damage=250, cooldown=18, target_type="random", telegraph_time=5, extra={"pull_effect": True})
    phase1.entry_message = "|x|hThe World-Eater awakens, its maw drinking in the very fabric of reality!|n"

    phase2 = BossPhase("p2", "Phase 2: Echoes of the Void", 60)
    phase2.add_ability("Summon Void Spawn", "summon_adds", cooldown=20, target_type="aoe", telegraph_time=5, extra={"add_name": "Void Spawn", "add_count": 4, "add_level": 60, "add_hp": 12000, "add_damage": 100})
    phase2.add_ability("Black Hole", "aoe", damage=400, cooldown=16, target_type="aoe", telegraph_time=5)
    phase2.add_ability("Gravity Crush", "damage", damage=500, cooldown=11, target_type="random", telegraph_time=3)
    phase2.entry_message = "|x|h'Feel the weight of infinite nothingness!' The World-Eater tears open reality!|n"

    phase3 = BossPhase("p3", "Phase 3: Oblivion", 25)
    phase3.add_ability("Supernova", "aoe", damage=600, cooldown=20, target_type="aoe", telegraph_time=6)
    phase3.add_ability("Entropy", "dot", damage=300, cooldown=12, target_type="all", telegraph_time=2, extra={"dot_duration": 15})
    phase3.add_ability("Void Annihilation", "damage", damage=800, cooldown=10, target_type="tank", telegraph_time=3)
    phase3.entry_message = "|R|h'ALL SHALL RETURN TO NOTHING!' The World-Eater begins consuming the realm!|n"

    boss3.add_phase(phase1)
    boss3.add_phase(phase2)
    boss3.add_phase(phase3)
    raid_manager.register_raid_template("void_threshold", boss3, "The Void Threshold", min_players=10, max_players=25, min_level=60, recommended_level=80)

    return raid_manager.list_raid_templates()