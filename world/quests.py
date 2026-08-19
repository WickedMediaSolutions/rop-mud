"""
Quest System for 'rop'

Provides:
  - Quest definitions (kill, fetch, talk quest types)
  - QuestHandler attached to Character for tracking active/completed quests
  - Reward system: XP, gold, items, faction alignment

Quest Types:
  - "kill"     Kill Mobs (e.g., kill 5 goblins)
  - "fetch"    Fetch/Deliver Items
  - "talk"     Talk to NPC

Usage:
  from world.quests import QuestHandler, QuestDefinition, quest_registry

  # Define a quest
  quest = QuestDefinition(
      id="goblin_slayer",
      name="Goblin Slayer",
      description="Kill 5 goblins plaguing the village.",
      quest_type="kill",
      target_key="goblin",
      target_count=5,
      rewards={"xp": 100, "gold": 50, "faction": 5},
      giver_npc_key="Town Guard",
      level_required=1,
  )
  quest_registry.register(quest)

  # Access handler on character
  char.quests.list_available()  # quests available from NPCs in room
  char.quests.accept("goblin_slayer")
  char.quests.status()
  char.quests.complete("goblin_slayer")
"""

import time
from evennia import search_object
from evennia.objects.objects import DefaultObject


# ---------------------------------------------------------------------------
# QUEST DEFINITION
# ---------------------------------------------------------------------------

class QuestDefinition:
    """
    Data class representing a single quest template.

    Attributes:
        id: Unique string identifier for this quest.
        name: Display name shown to players.
        description: Flavor text / objective description.
        quest_type: One of "kill", "fetch", "talk".
        target_key: The mob key / item key / NPC key to target.
        target_count: Number required (for kill/fetch). Default 1.
        rewards: Dict of reward values, e.g. {"xp": 100, "gold": 50, "items": [], "faction": 5}.
        giver_npc_key: The NPC dbref|key that gives this quest.
        level_required: Minimum player level to accept.
        prereq_quests: List of quest IDs that must be completed before this one.
        repeatable: Whether the quest can be done multiple times.
        completion_text: Message shown when the quest is turned in.
    """

    def __init__(
        self,
        id,
        name,
        description,
        quest_type,
        target_key,
        target_count=1,
        rewards=None,
        giver_npc_key=None,
        level_required=1,
        prereq_quests=None,
        repeatable=False,
        completion_text=None,
        daily=False,
        chain_id=None,
        chain_order=0,
        scale_rewards=False,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.quest_type = quest_type  # "kill", "fetch", "talk"
        self.target_key = target_key
        self.target_count = target_count
        self.rewards = rewards or {}
        self.giver_npc_key = giver_npc_key
        self.level_required = level_required
        self.prereq_quests = prereq_quests or []
        self.repeatable = repeatable
        self.completion_text = completion_text or f"You have completed '{name}'!"
        self.daily = daily  # Daily quest: resets every 24h
        self.chain_id = chain_id  # Quest chain identifier (e.g. "wolf_saga")
        self.chain_order = chain_order  # Position in chain (0 = first)
        self.scale_rewards = scale_rewards  # Whether rewards scale with player level

    def get_scaled_rewards(self, player_level):
        """
        Return rewards scaled to the player's level.

        Scaling formula:
          - XP: base * (1 + (level - level_required) * 0.15)
          - Gold: base * (1 + (level - level_required) * 0.10)
          - Faction: unchanged
          - Items: unchanged
        """
        if not self.scale_rewards:
            return dict(self.rewards)

        scaled = dict(self.rewards)
        level_diff = max(0, player_level - self.level_required)

        if "xp" in scaled:
            scaled["xp"] = int(scaled["xp"] * (1 + level_diff * 0.15))
        if "gold" in scaled:
            scaled["gold"] = int(scaled["gold"] * (1 + level_diff * 0.10))

        return scaled

    def __repr__(self):
        return f"<QuestDefinition {self.id} ({self.quest_type})>"


# ---------------------------------------------------------------------------
# QUEST REGISTRY
# ---------------------------------------------------------------------------

class QuestRegistry:
    """
    Central registry of all quest definitions in the game.

    Quests are registered by their unique ID and can be looked up
    by NPC key to find which quests an NPC offers.
    """

    def __init__(self):
        self._quests = {}  # id -> QuestDefinition

    def register(self, quest):
        """Register a QuestDefinition."""
        if not isinstance(quest, QuestDefinition):
            raise TypeError("Must register a QuestDefinition instance")
        self._quests[quest.id] = quest

    def get(self, quest_id):
        """Retrieve a QuestDefinition by ID, or None."""
        return self._quests.get(quest_id)

    def get_by_npc(self, npc_key):
        """Return list of QuestDefinitions offered by a given NPC key."""
        return [
            q for q in self._quests.values()
            if q.giver_npc_key and q.giver_npc_key.lower() == npc_key.lower()
        ]

    def get_by_chain(self, chain_id):
        """Return all quests in a chain, sorted by chain_order."""
        chain_quests = [
            q for q in self._quests.values()
            if q.chain_id == chain_id
        ]
        chain_quests.sort(key=lambda q: q.chain_order)
        return chain_quests

    def get_daily_quests(self):
        """Return all daily quests."""
        return [q for q in self._quests.values() if q.daily]

    def all(self):
        """Return all registered quests."""
        return list(self._quests.values())

    def clear(self):
        """Remove all quests (useful for testing)."""
        self._quests.clear()

    def __len__(self):
        """Return number of registered quests."""
        return len(self._quests)

    def items(self):
        """Return (id, QuestDefinition) pairs for dict-like access."""
        return self._quests.items()


# Global registry instance
quest_registry = QuestRegistry()
QUEST_REGISTRY = quest_registry  # uppercase alias for backward compat


# ---------------------------------------------------------------------------
# ACTIVE QUEST (per-player instance)
# ---------------------------------------------------------------------------

class ActiveQuest:
    """
    Represents a quest that a player has accepted and is tracking.

    Stores the definition reference and current progress.
    """

    def __init__(self, quest_def=None, progress=0, quest_id=None,
                 quest_name=None, target_count=0):
        if quest_def is not None:
            self.quest_id = quest_def.id
            self.quest_def = quest_def
            self.target_count = quest_def.target_count
        else:
            self.quest_id = quest_id
            self.quest_def = None
            self.quest_name = quest_name
            self.target_count = target_count
        self.progress = progress  # current count toward target_count
        self.completed = self.progress >= self.target_count

    @property
    def is_complete(self):
        """Whether the player has met the target count."""
        return self.progress >= self.target_count

    def advance(self, amount=1):
        """Increment progress. Returns True if quest is now complete."""
        self.target_count = self.target_count or 1
        self.progress = min(self.progress + amount, self.target_count)
        self.completed = self.is_complete
        return self.is_complete

    def serialize(self):
        """Return a dict suitable for storage in attributes."""
        return {
            "quest_id": self.quest_id,
            "progress": self.progress,
        }

    @classmethod
    def deserialize(cls, data, quest_def):
        """Restore an ActiveQuest from stored data and a QuestDefinition."""
        return cls(
            quest_def=quest_def,
            progress=data.get("progress", 0),
        )

    def __repr__(self):
        if self.quest_def is not None:
            return f"<ActiveQuest {self.quest_id} ({self.progress}/{self.quest_def.target_count})>"
        return f"<ActiveQuest {self.quest_id} ({self.progress}/{self.target_count})>"


# ---------------------------------------------------------------------------
# QUEST HANDLER (attached to character)
# ---------------------------------------------------------------------------

class QuestHandler:
    """
    Handler attached to a Character that manages all quest state.

    Provides methods for:
      - list_available()   -- quests offered by NPCs in the current room
      - accept(quest_id)   -- accept a quest from an NPC
      - status()           -- show active quest journal
      - complete(quest_id) -- turn in a completed quest for rewards
      - report_kill(target_key)   -- update kill quest progress
      - report_fetch(item_key, count) -- update fetch quest progress
      - report_talk(npc_key)      -- update talk quest progress

    Attributes used on the character:
      db.active_quests   -- list of serialized active quests
      db.completed_quests -- set of completed quest IDs
    """

    def __init__(self, character):
        self.character = character
        self.owner = character  # alias for test compatibility

    # ---- Internal helpers ----

    def _load_active(self):
        """Load active quests from character attributes."""
        raw = self.character.attributes.get("active_quests", default=[])
        if not raw:
            return []
        active = []
        for data in raw:
            qdef = quest_registry.get(data.get("quest_id"))
            if qdef:
                active.append(ActiveQuest.deserialize(data, qdef))
        return active

    def _save_active(self, active_quests):
        """Persist active quests to character attributes."""
        serialized = [aq.serialize() for aq in active_quests]
        self.character.attributes.add("active_quests", serialized)

    def _load_completed(self):
        """Load set of completed quest IDs."""
        return set(self.character.attributes.get("completed_quests", default=[]) or [])

    def _load_daily_resets(self):
        """Load dict of {quest_id: last_reset_timestamp} for daily quests."""
        return self.character.attributes.get("daily_quest_resets", default={}) or {}

    def _save_daily_resets(self, resets):
        """Persist daily quest reset timestamps."""
        self.character.attributes.add("daily_quest_resets", resets)

    def _check_daily_reset(self, quest_id):
        """
        Check if a daily quest's cooldown has expired (24 hours).
        If so, remove it from completed so it can be re-accepted.
        Returns True if the quest was reset.
        """
        resets = self._load_daily_resets()
        last_reset = resets.get(quest_id, 0)
        now = time.time()
        if now - last_reset >= 86400:  # 24 hours
            completed = self._load_completed()
            if quest_id in completed:
                completed.discard(quest_id)
                self._save_completed(completed)
            resets[quest_id] = now
            self._save_daily_resets(resets)
            return True
        return False

    def check_daily_resets(self):
        """
        Check all daily quests for expired cooldowns and reset them.

        Called automatically by list_available() and can also be called
        from at_post_login hooks to ensure daily quests are available
        when a player logs in after 24+ hours away.

        Returns:
            Number of daily quests that were reset.
        """
        reset_count = 0
        for qdef in quest_registry.get_daily_quests():
            if self._check_daily_reset(qdef.id):
                reset_count += 1
        return reset_count

    def _save_completed(self, completed):
        """Persist completed quest IDs."""
        self.character.attributes.add("completed_quests", list(completed))

    def _find_active(self, quest_id):
        """Return (index, ActiveQuest) for a quest ID, or (None, None)."""
        active = self._load_active()
        for i, aq in enumerate(active):
            if aq.quest_id == quest_id:
                return i, aq
        return None, None

    # ---- Public API ----

    def list_available(self):
        """
        Return a list of QuestDefinitions available to the player.

        Quests come from NPCs in the same room as the character.
        Filters out quests the player doesn't meet requirements for
        and quests already completed (unless repeatable).

        Also triggers daily quest reset checks — if a daily quest's
        24-hour cooldown has expired, it becomes available again.
        """
        character = self.character
        location = character.location
        if not location:
            return []

        # Auto-check daily quest resets before listing
        self.check_daily_resets()

        # Find all NPCs in the room
        npcs = [obj for obj in location.contents
                if obj != character and not obj.has_account]

        completed = self._load_completed()
        active = self._load_active()
        active_ids = {aq.quest_id for aq in active}

        available = []
        for npc in npcs:
            npc_quests = quest_registry.get_by_npc(npc.key)
            for qdef in npc_quests:
                # Skip if already active
                if qdef.id in active_ids:
                    continue
                # Skip if completed and not repeatable
                if qdef.id in completed and not qdef.repeatable:
                    continue
                # Skip if level too low
                player_level = character.attributes.get("level", default=1)
                if player_level < qdef.level_required:
                    continue
                # Skip if prerequisites not met
                if qdef.prereq_quests:
                    if not all(pid in completed for pid in qdef.prereq_quests):
                        continue
                available.append((npc, qdef))
        return available

    def accept(self, quest_id):
        """
        Accept a quest by ID if available from an NPC in the room.

        Returns (True, message) or (False, error_message).
        """
        character = self.character

        # Check already active
        _, existing = self._find_active(quest_id)
        if existing:
            return False, "You have already accepted that quest."

        # Check completed (non-repeatable)
        completed = self._load_completed()
        qdef = quest_registry.get(quest_id)
        if not qdef:
            return False, "That quest does not exist."
        if quest_id in completed and not qdef.repeatable:
            return False, "You have already completed that quest."

        # Verify it's available from an NPC in the room
        available = self.list_available()
        available_ids = {q.id for _, q in available}
        if quest_id not in available_ids:
            return False, "No NPC here offers that quest, or you do not meet the requirements."

        # Accept it
        active = self._load_active()
        active.append(ActiveQuest(qdef))
        self._save_active(active)

        character.msg(f"|g[Quest] Accepted: {qdef.name}|n")
        character.msg(f"|w{qdef.description}|n")
        return True, f"You have accepted the quest: {qdef.name}"

    def status(self):
        """
        Return a formatted string showing the player's active quest journal.

        Also returns the raw active quests for command use.
        """
        active = self._load_active()
        if not active:
            return "|yYou have no active quests.|n", []

        lines = ["|w=== Active Quests ===|n"]
        for aq in active:
            qdef = aq.quest_def
            pct = f"{aq.progress}/{qdef.target_count}"
            type_label = qdef.quest_type.upper()
            lines.append(
                f"  |c[{type_label}]|n {qdef.name} |w(ID: {qdef.id})|n - {qdef.description}"
            )
            lines.append(f"    Progress: |y{pct}|n")
        return "\n".join(lines), active

    def complete(self, quest_id):
        """
        Turn in a completed quest for rewards.

        The player must be in the same room as the quest giver NPC.

        Returns (True, message) or (False, error_message).
        """
        character = self.character

        # Find the active quest
        idx, aq = self._find_active(quest_id)
        if aq is None:
            return False, "You do not have that quest active."

        qdef = aq.quest_def

        # Check progress
        if not aq.is_complete:
            return False, (
                f"You have not completed the quest yet. "
                f"Progress: {aq.progress}/{qdef.target_count}."
            )

        # Check NPC proximity (quest giver must be in same room)
        location = character.location
        if location:
            npcs_in_room = [obj.key.lower() for obj in location.contents
                            if obj != character and not obj.has_account]
            if qdef.giver_npc_key and qdef.giver_npc_key.lower() not in npcs_in_room:
                return False, f"You must return to {qdef.giver_npc_key} to complete this quest."

        # Grant rewards (scaled by player level)
        player_level = character.attributes.get("level", default=1)
        scaled_rewards = qdef.get_scaled_rewards(player_level)
        reward_msgs = self._grant_rewards(scaled_rewards, quest_id)

        # Move from active to completed
        active = self._load_active()
        active.pop(idx)
        self._save_active(active)

        completed = self._load_completed()
        completed.add(quest_id)
        self._save_completed(completed)

        # Notify player
        character.msg(f"|g[Quest] Completed: {qdef.name}!|n")
        character.msg(f"|w{qdef.completion_text}|n")
        for rmsg in reward_msgs:
            character.msg(rmsg)

        return True, f"Quest '{qdef.name}' completed!"

    def _grant_rewards(self, rewards, quest_id=None):
        """
        Apply rewards to the character and return list of formatted messages.

        Supported reward keys:
          - xp: Experience points added.
          - gold: Currency added.
          - items: List of item keys to create and give.
          - faction: Faction alignment points (positive = toward Good).
        """
        character = self.character
        messages = []

        # XP
        xp = rewards.get("xp", 0)
        if xp:
            character.award_xp(xp)
            new_total = character.attributes.get("xp", default=0)
            messages.append(f"  |y+{xp} XP|n (Total: {new_total})")

        # Gold
        gold = rewards.get("gold", 0)
        if gold:
            current_gold = character.attributes.get("gold", default=0)
            character.attributes.add("gold", current_gold + gold)
            messages.append(f"  |y+{gold} Gold|n (Total: {current_gold + gold})")

        # Items
        items = rewards.get("items", [])
        for item_key in items:
            # Create the item and place it in the character's inventory
            try:
                new_item = DefaultObject.create(key=item_key)
                new_item.location = character
                messages.append(f"  |yReceived item:|n {item_key}")
            except Exception:
                messages.append(f"  |rFailed to create item:|n {item_key}")

        # Faction alignment
        faction = rewards.get("faction", 0)
        if faction:
            current_align = character.attributes.get("alignment", default="Neutral")
            # Faction reward nudges alignment in a direction (positive = toward Good)
            # This is a simple numeric tracker alongside the named alignment
            faction_points = character.attributes.get("faction_points", default=0)
            faction_points += faction
            character.attributes.add("faction_points", faction_points)
            sign = "+" if faction > 0 else ""
            messages.append(f"  |y{sign}{faction} Faction Alignment|n (Total points: {faction_points})")

        # --- Reputation System integration ---
        # Quest completion grants reputation with the quest giver's faction
        try:
            from world.reputation import ReputationSystem
            rep_amount = rewards.get("reputation", 0)
            if rep_amount == 0:
                # Default: quest completion gives 100 rep to home faction
                rep_amount = ReputationSystem.REP_COMPLETE_QUEST
            # Determine which faction gets the reputation based on quest giver
            if quest_id:
                qdef = quest_registry.get(quest_id)
                if qdef and hasattr(qdef, 'giver_npc_key') and qdef.giver_npc_key:
                    giver_key = qdef.giver_npc_key.lower()
                    if "aethelgard" in giver_key or "good" in giver_key or "paladin" in giver_key or "cleric" in giver_key or "mage" in giver_key:
                        ReputationSystem.adjust_reputation(character, "aethelgard", rep_amount)
                    elif "gorgoroth" in giver_key or "evil" in giver_key or "warlock" in giver_key or "necromancer" in giver_key:
                        ReputationSystem.adjust_reputation(character, "gorgoroth", rep_amount)
                    else:
                        home_faction = ReputationSystem.get_home_faction(character)
                        ReputationSystem.adjust_reputation(character, home_faction, rep_amount)
                else:
                    home_faction = ReputationSystem.get_home_faction(character)
                    ReputationSystem.adjust_reputation(character, home_faction, rep_amount)
            else:
                home_faction = ReputationSystem.get_home_faction(character)
                ReputationSystem.adjust_reputation(character, home_faction, rep_amount)
        except Exception:
            pass

        if not messages:
            messages.append("  |yNo tangible rewards.|n")

        return messages

    # ---- Progress reporting (called by game systems) ----

    def report_kill(self, target_key):
        """
        Call when the player kills a mob. Auto-advances matching kill quests.

        Returns list of (quest_name, became_complete) for any quests that advanced.
        """
        active = self._load_active()
        updated = []
        for aq in active:
            if aq.quest_def.quest_type == "kill" and aq.quest_def.target_key.lower() == target_key.lower():
                was_complete = aq.is_complete
                now_complete = aq.advance(1)
                updated.append((aq.quest_def.id, aq.quest_def.name, now_complete))
                if now_complete and not was_complete:
                    self.character.msg(
                        f"|g[Quest] Objective complete: {aq.quest_def.name}! "
                        f"Return to {aq.quest_def.giver_npc_key} to claim your reward.|n"
                    )
        self._save_active(active)

        # Phase 9: Share progress with group members
        for quest_id, _, _ in updated:
            if not self.character.attributes.get("group_id", default=None):
                break
            self.share_progress(quest_id, target_key, 1)

        return updated

    def report_fetch(self, item_key, count=1):
        """
        Call when the player acquires an item. Auto-advances matching fetch quests.

        Returns list of (quest_name, became_complete) for any quests that advanced.
        """
        active = self._load_active()
        updated = []
        for aq in active:
            if aq.quest_def.quest_type == "fetch" and aq.quest_def.target_key.lower() == item_key.lower():
                was_complete = aq.is_complete
                now_complete = aq.advance(count)
                updated.append((aq.quest_def.id, aq.quest_def.name, now_complete))
                if now_complete and not was_complete:
                    self.character.msg(
                        f"|g[Quest] Objective complete: {aq.quest_def.name}! "
                        f"Return to {aq.quest_def.giver_npc_key} to deliver the items.|n"
                    )
        self._save_active(active)

        # Phase 9: Share progress with group members
        for quest_id, _, _ in updated:
            if not self.character.attributes.get("group_id", default=None):
                break
            self.share_progress(quest_id, item_key, count)

        return updated

    def report_talk(self, npc_key):
        """
        Call when the player talks to an NPC. Auto-advances matching talk quests.

        Returns list of (quest_name, became_complete) for any quests that advanced.
        """
        active = self._load_active()
        updated = []
        for aq in active:
            if aq.quest_def.quest_type == "talk" and aq.quest_def.target_key.lower() == npc_key.lower():
                was_complete = aq.is_complete
                now_complete = aq.advance(1)
                updated.append((aq.quest_def.id, aq.quest_def.name, now_complete))
                if now_complete and not was_complete:
                    self.character.msg(
                        f"|g[Quest] Objective complete: {aq.quest_def.name}! "
                        f"Return to {aq.quest_def.giver_npc_key} to report.|n"
                    )
        self._save_active(active)
        return updated

    def abandon(self, quest_id):
        """
        Abandon an active quest.

        Returns (True, message) or (False, error_message).
        """
        idx, aq = self._find_active(quest_id)
        if aq is None:
            return False, "You do not have that quest active."
        active = self._load_active()
        name = active.pop(idx).quest_def.name
        self._save_active(active)
        self.character.msg(f"|y[Quest] Abandoned: {name}|n")
        return True, f"You have abandoned the quest: {name}."

    def share_progress(self, quest_id, target_key, count=1):
        """
        Share quest progress with all group members in the same room.

        Called when a player makes progress on a kill/fetch quest.
        All group members in the same room who have the same quest active
        will also receive progress.

        Args:
            quest_id: The quest being progressed.
            target_key: The target key (mob/item/npc).
            count: Amount of progress to share.

        Returns:
            Number of group members who received shared progress.
        """
        character = self.character
        group_id = character.attributes.get("group_id", default=None)
        if not group_id:
            return 0

        location = character.location
        if not location:
            return 0

        shared_count = 0
        # Scan all contents of the room for other player characters in the same group
        for obj in location.contents:
            if obj == character:
                continue
            # Check if this object is in the same group
            obj_group = obj.attributes.get("group_id", default=None)
            if obj_group != group_id:
                continue
            # Check if this object has a quest handler (works for both real players and test chars)
            if not hasattr(obj, 'quests'):
                continue

            # Load member's active quests and find this one
            member_active = obj.quests._load_active()
            member_aq = None
            for aq in member_active:
                if aq.quest_id == quest_id:
                    member_aq = aq
                    break

            if member_aq is None or member_aq.is_complete:
                continue

            qdef = member_aq.quest_def
            if qdef.quest_type == "kill" and qdef.target_key.lower() == target_key.lower():
                pass
            elif qdef.quest_type == "fetch" and qdef.target_key.lower() == target_key.lower():
                pass
            elif qdef.quest_type == "talk" and qdef.target_key.lower() == target_key.lower():
                pass
            else:
                continue

            # Advance and persist the modified list
            was_complete = member_aq.is_complete
            now_complete = member_aq.advance(count)
            obj.quests._save_active(member_active)

            if now_complete and not was_complete:
                obj.msg(
                    f"|g[Quest] Objective complete: {qdef.name}! "
                    f"Return to {qdef.giver_npc_key} to claim your reward.|n"
                )

            shared_count += 1

        return shared_count

    def get_chain_progress(self, chain_id):
        """
        Get progress through a quest chain.

        Returns (completed_count, total_count, next_quest_id).
        """
        chain_quests = quest_registry.get_by_chain(chain_id)
        if not chain_quests:
            return 0, 0, None

        completed = self._load_completed()
        completed_in_chain = [q for q in chain_quests if q.id in completed]
        completed_count = len(completed_in_chain)

        # Find the next uncompleted quest in the chain
        next_quest = None
        for q in chain_quests:
            if q.id not in completed:
                next_quest = q.id
                break

        return completed_count, len(chain_quests), next_quest

    def get_completed_count(self):
        """Return the number of unique quests completed."""
        return len(self._load_completed())

    def has_completed(self, quest_id):
        """Check if the player has completed a specific quest."""
        return quest_id in self._load_completed()

    def is_active(self, quest_id):
        """Check if the player currently has a quest active."""
        _, aq = self._find_active(quest_id)
        return aq is not None


# ---------------------------------------------------------------------------
# DEFAULT QUESTS (built-in starter quests for the game)
# ---------------------------------------------------------------------------

def register_default_quests():
    """
    Register the default quest set for 'rop'.

    Called from at_initial_setup or manually to populate the quest registry.
    """
    # Clear existing to ensure idempotency
    quest_registry.clear()

    # --- Good faction quests ---

    quest_registry.register(QuestDefinition(
        id="good_wolf_hunt",
        name="Wolf Hunt",
        description="Thin the wolf pack near Aethelgard. Kill 3 wolves and report back.",
        quest_type="kill",
        target_key="wolf",
        target_count=3,
        rewards={"xp": 50, "gold": 25, "faction": 2},
        giver_npc_key="Good Quartermaster",
        level_required=1,
        scale_rewards=True,
        completion_text="Well done! The wolf pack has been thinned. Aethelgard thanks you.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_herb_delivery",
        name="Herb Delivery",
        description="Collect 2 healing herbs and deliver them to the Quartermaster.",
        quest_type="fetch",
        target_key="healing herb",
        target_count=2,
        rewards={"xp": 40, "gold": 20, "faction": 1},
        giver_npc_key="Good Quartermaster",
        level_required=1,
        scale_rewards=True,
        completion_text="Thank you for the herbs. Our healers will put them to good use.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_scout_report",
        name="Scout Report",
        description="Speak with the Good Spell Trainer to receive a scout briefing.",
        quest_type="talk",
        target_key="Good Spell Trainer",
        target_count=1,
        rewards={"xp": 30, "gold": 15, "faction": 1},
        giver_npc_key="Good Quartermaster",
        level_required=1,
        scale_rewards=True,
        completion_text="Good. The information you gathered will help us plan our next move.",
    ))

    # --- Evil faction quests ---

    quest_registry.register(QuestDefinition(
        id="evil_rat_extermination",
        name="Rat Extermination",
        description="Clear the tunnels of giant rats. Kill 4 rats and report back.",
        quest_type="kill",
        target_key="rat",
        target_count=4,
        rewards={"xp": 60, "gold": 30, "faction": -2},
        giver_npc_key="Evil Quartermaster",
        level_required=1,
        scale_rewards=True,
        completion_text="Heh. The rats won't bother us anymore. Here's your pay.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_skull_collection",
        name="Skull Collection",
        description="Collect 3 skulls from fallen enemies and bring them to the Quartermaster.",
        quest_type="fetch",
        target_key="skull",
        target_count=3,
        rewards={"xp": 50, "gold": 25, "faction": -2},
        giver_npc_key="Evil Quartermaster",
        level_required=1,
        scale_rewards=True,
        completion_text="Fine trophies. The Dark Lord will be pleased.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_dark_communion",
        name="Dark Communion",
        description="Seek out the Evil Spell Trainer for a dark blessing.",
        quest_type="talk",
        target_key="Evil Spell Trainer",
        target_count=1,
        rewards={"xp": 35, "gold": 15, "faction": -1},
        giver_npc_key="Evil Quartermaster",
        level_required=1,
        scale_rewards=True,
        completion_text="The dark energy courses through you. You feel stronger.",
    ))

    # ================================================================
    # EXPANDED QUESTS — Levels 5-80 (50+ total)
    # ================================================================

    # --- Level 5-10 Quests ---

    quest_registry.register(QuestDefinition(
        id="good_spider_cleanse",
        name="Spider Cleanse",
        description="Clear the spider infestation from the Silverwood Forest. Kill 5 cave spiders.",
        quest_type="kill",
        target_key="cave spider",
        target_count=5,
        rewards={"xp": 120, "gold": 60, "faction": 3},
        giver_npc_key="Good Quartermaster",
        level_required=5,
        scale_rewards=True,
        completion_text="The forest breathes easier now. Thank you, adventurer.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_bandit_threat",
        name="Bandit Threat",
        description="Bandits have been raiding caravans near the Crossroads. Eliminate 4 bandits.",
        quest_type="kill",
        target_key="bandit",
        target_count=4,
        rewards={"xp": 150, "gold": 80, "faction": 4},
        giver_npc_key="Good Quartermaster",
        level_required=8,
        prereq_quests=["good_spider_cleanse"],
        scale_rewards=True,
        completion_text="The roads are safe again. Aethelgard is grateful.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_herb_master",
        name="Master Herbalist",
        description="Collect 5 rare moonbloom herbs from the Whispering Ridge for the healers.",
        quest_type="fetch",
        target_key="moonbloom herb",
        target_count=5,
        rewards={"xp": 100, "gold": 50, "faction": 2},
        giver_npc_key="Good Spell Trainer",
        level_required=6,
        scale_rewards=True,
        completion_text="These herbs will save many lives. You have our thanks.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_goblin_raiders",
        name="Goblin Raiders",
        description="A rival goblin tribe encroaches on our territory. Slay 6 goblin warriors.",
        quest_type="kill",
        target_key="goblin warrior",
        target_count=6,
        rewards={"xp": 140, "gold": 70, "faction": -3},
        giver_npc_key="Evil Quartermaster",
        level_required=5,
        scale_rewards=True,
        completion_text="The goblins will think twice before challenging us again.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_bone_collector",
        name="Bone Collector",
        description="The necromancers need fresh bones. Collect 4 skeletons' bones from the Verdant Mire.",
        quest_type="fetch",
        target_key="skeleton bone",
        target_count=4,
        rewards={"xp": 110, "gold": 55, "faction": -2},
        giver_npc_key="Evil Spell Trainer",
        level_required=6,
        scale_rewards=True,
        completion_text="Excellent specimens. The necromancers will raise a fine army.",
    ))

    # --- Level 11-20 Quests ---

    quest_registry.register(QuestDefinition(
        id="good_orc_invasion",
        name="Orc Invasion",
        description="Orc warbands threaten the Golden Plains. Defeat 8 orc warriors.",
        quest_type="kill",
        target_key="orc warrior",
        target_count=8,
        rewards={"xp": 300, "gold": 150, "faction": 6},
        giver_npc_key="Good Quartermaster",
        level_required=12,
        prereq_quests=["good_bandit_threat"],
        scale_rewards=True,
        completion_text="The orc warband has been broken. The plains are secure.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_troll_slayer",
        name="Troll Slayer",
        description="A troll has been terrorizing farms near Oakhaven. Hunt it down.",
        quest_type="kill",
        target_key="troll",
        target_count=1,
        rewards={"xp": 250, "gold": 200, "faction": 5},
        giver_npc_key="Good Quartermaster",
        level_required=15,
        scale_rewards=True,
        completion_text="The troll is dead! The farmers can sleep peacefully tonight.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_lost_artifact",
        name="Lost Artifact",
        description="Recover the Sunstone Amulet from the Stoneguard Mines.",
        quest_type="fetch",
        target_key="sunstone amulet",
        target_count=1,
        rewards={"xp": 200, "gold": 120, "faction": 4},
        giver_npc_key="Good Spell Trainer",
        level_required=14,
        scale_rewards=True,
        completion_text="The Sunstone Amulet! It still pulses with ancient power.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_scout_highlands",
        name="Scout the Highlands",
        description="Speak with the Highland Watch Captain about enemy movements.",
        quest_type="talk",
        target_key="Highland Watch Captain",
        target_count=1,
        rewards={"xp": 100, "gold": 50, "faction": 2},
        giver_npc_key="Good Quartermaster",
        level_required=11,
        scale_rewards=True,
        completion_text="The intelligence you gathered is invaluable. We'll prepare defenses.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_wraith_hunt",
        name="Wraith Hunt",
        description="Wraiths have escaped the Bone Fields. Bind 5 of them back to service.",
        quest_type="kill",
        target_key="wraith",
        target_count=5,
        rewards={"xp": 280, "gold": 140, "faction": -5},
        giver_npc_key="Evil Quartermaster",
        level_required=13,
        scale_rewards=True,
        completion_text="The wraiths are bound once more. They will serve the Horde.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_dark_tome",
        name="The Dark Tome",
        description="Retrieve the Tome of Shadows from the Drow Caverns for the Spell Trainer.",
        quest_type="fetch",
        target_key="tome of shadows",
        target_count=1,
        rewards={"xp": 220, "gold": 130, "faction": -4},
        giver_npc_key="Evil Spell Trainer",
        level_required=15,
        scale_rewards=True,
        completion_text="The Tome of Shadows... its power is intoxicating. Well done.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_corrupt_guardian",
        name="Corrupt the Guardian",
        description="Speak with the Corrupted Treant in Rotwood Forest and sway it to our cause.",
        quest_type="talk",
        target_key="Corrupted Treant",
        target_count=1,
        rewards={"xp": 180, "gold": 90, "faction": -3},
        giver_npc_key="Evil Quartermaster",
        level_required=12,
        scale_rewards=True,
        completion_text="The treant now serves the Horde. The forest will rot from within.",
    ))

    # --- Level 21-30 Quests ---

    quest_registry.register(QuestDefinition(
        id="good_dragon_scout",
        name="Dragon Scout",
        description="A young drake has been spotted near the Highland Pass. Slay it before it grows.",
        quest_type="kill",
        target_key="drake",
        target_count=1,
        rewards={"xp": 500, "gold": 300, "faction": 8},
        giver_npc_key="Good Quartermaster",
        level_required=22,
        scale_rewards=True,
        completion_text="A drake slain! You've prevented a future catastrophe.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_giant_slayer",
        name="Giant Slayer",
        description="Hill giants have been hurling boulders at Dawn-Light Bay. Eliminate 3 of them.",
        quest_type="kill",
        target_key="hill giant",
        target_count=3,
        rewards={"xp": 600, "gold": 400, "faction": 10},
        giver_npc_key="Good Quartermaster",
        level_required=25,
        scale_rewards=True,
        completion_text="The giants are no more. The coast is safe for our ships.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_crystal_collection",
        name="Crystal Collection",
        description="Gather 6 echo crystals from the Echoing Caverns for the mages.",
        quest_type="fetch",
        target_key="echo crystal",
        target_count=6,
        rewards={"xp": 350, "gold": 200, "faction": 5},
        giver_npc_key="Good Spell Trainer",
        level_required=23,
        scale_rewards=True,
        completion_text="These crystals hum with ancient magic. The mages will be thrilled.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_elder_wisdom",
        name="Wisdom of the Elders",
        description="Seek the wisdom of the Ancient Sage in Eldergrove Thicket.",
        quest_type="talk",
        target_key="Ancient Sage",
        target_count=1,
        rewards={"xp": 200, "gold": 100, "faction": 3},
        giver_npc_key="Good Spell Trainer",
        level_required=21,
        scale_rewards=True,
        completion_text="The sage's words resonate with ancient truth. You feel enlightened.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_shadow_beast",
        name="Shadow Beast Mastery",
        description="Prove your worth by defeating 4 shadow beasts in the Ashen Wastes.",
        quest_type="kill",
        target_key="shadow beast",
        target_count=4,
        rewards={"xp": 550, "gold": 350, "faction": -7},
        giver_npc_key="Evil Quartermaster",
        level_required=24,
        scale_rewards=True,
        completion_text="You have mastered the shadows. The Horde grows stronger.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_blood_river",
        name="Blood River Offering",
        description="Collect 5 blood vials from the Blood-River Delta for dark rituals.",
        quest_type="fetch",
        target_key="blood vial",
        target_count=5,
        rewards={"xp": 400, "gold": 250, "faction": -6},
        giver_npc_key="Evil Spell Trainer",
        level_required=22,
        scale_rewards=True,
        completion_text="The blood vials pulse with dark energy. The ritual can begin.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_demon_pact",
        name="Demon Pact",
        description="Speak with the Demon Herald in the Dread Valley and forge a pact.",
        quest_type="talk",
        target_key="Demon Herald",
        target_count=1,
        rewards={"xp": 300, "gold": 180, "faction": -5},
        giver_npc_key="Evil Spell Trainer",
        level_required=23,
        scale_rewards=True,
        completion_text="The pact is sealed. Demonic power flows through you.",
    ))

    # --- Level 31-40 Quests ---

    quest_registry.register(QuestDefinition(
        id="good_wyvern_hunt",
        name="Wyvern Hunt",
        description="Wyverns have been attacking Iron-Watch Castle. Slay 3 wyverns.",
        quest_type="kill",
        target_key="wyvern",
        target_count=3,
        rewards={"xp": 900, "gold": 600, "faction": 12},
        giver_npc_key="Good Quartermaster",
        level_required=32,
        scale_rewards=True,
        completion_text="The skies are clear. Iron-Watch stands strong thanks to you.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_phoenix_feather",
        name="Phoenix Feather",
        description="Obtain a sacred phoenix feather from the Astraea Holy Ruins.",
        quest_type="fetch",
        target_key="phoenix feather",
        target_count=1,
        rewards={"xp": 700, "gold": 500, "faction": 10},
        giver_npc_key="Good Spell Trainer",
        level_required=35,
        scale_rewards=True,
        completion_text="A phoenix feather! It radiates divine warmth. A priceless relic.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_golem_deactivation",
        name="Golem Deactivation",
        description="Rogue stone golems threaten the Serpent River Path. Destroy 4 of them.",
        quest_type="kill",
        target_key="stone golem",
        target_count=4,
        rewards={"xp": 800, "gold": 550, "faction": 11},
        giver_npc_key="Good Quartermaster",
        level_required=34,
        scale_rewards=True,
        completion_text="The golems have been reduced to rubble. The path is open.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_fire_elemental",
        name="Fire Elemental Binding",
        description="Bind 4 fire elementals from the Hellfire Spire to our service.",
        quest_type="kill",
        target_key="fire elemental",
        target_count=4,
        rewards={"xp": 850, "gold": 580, "faction": -10},
        giver_npc_key="Evil Quartermaster",
        level_required=33,
        scale_rewards=True,
        completion_text="The fire elementals are bound. They will burn our enemies to ash.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_basilisk_venom",
        name="Basilisk Venom",
        description="Harvest basilisk venom from the Screaming Canyons. We need 3 vials.",
        quest_type="fetch",
        target_key="basilisk venom",
        target_count=3,
        rewards={"xp": 750, "gold": 480, "faction": -8},
        giver_npc_key="Evil Spell Trainer",
        level_required=31,
        scale_rewards=True,
        completion_text="Deadly venom. Our assassins will make good use of this.",
    ))

    # --- Level 41-50 Quests ---

    quest_registry.register(QuestDefinition(
        id="good_lich_hunt",
        name="Lich Hunt",
        description="A powerful lich has risen in the Vile Necropolis. Destroy it.",
        quest_type="kill",
        target_key="lich",
        target_count=1,
        rewards={"xp": 1500, "gold": 1000, "faction": 15},
        giver_npc_key="Good Quartermaster",
        level_required=42,
        scale_rewards=True,
        completion_text="The lich is destroyed! Its phylactery shattered. A great evil is vanquished.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_demon_slayer",
        name="Demon Slayer",
        description="A demon lord has crossed into our realm through the Desolation Pass. Banish it.",
        quest_type="kill",
        target_key="demon lord",
        target_count=1,
        rewards={"xp": 1800, "gold": 1200, "faction": 18},
        giver_npc_key="Good Quartermaster",
        level_required=45,
        scale_rewards=True,
        completion_text="The demon lord is banished back to the abyss. The realm is saved.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_holy_relic",
        name="Holy Relic Recovery",
        description="Recover the Chalice of Light from the Desecrated Temple in the Vile Grounds.",
        quest_type="fetch",
        target_key="chalice of light",
        target_count=1,
        rewards={"xp": 1200, "gold": 800, "faction": 14},
        giver_npc_key="Good Spell Trainer",
        level_required=43,
        scale_rewards=True,
        completion_text="The Chalice of Light! Its holy radiance restores hope to Aethelgard.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_death_knight",
        name="Death Knight Recruitment",
        description="Convince the Death Knight in the Bone Fields to join the Horde's army.",
        quest_type="talk",
        target_key="Death Knight",
        target_count=1,
        rewards={"xp": 1000, "gold": 700, "faction": -12},
        giver_npc_key="Evil Quartermaster",
        level_required=41,
        scale_rewards=True,
        completion_text="The Death Knight pledges his blade to the Horde. A powerful ally.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_beholder_eye",
        name="Beholder's Eye",
        description="Claim the central eye of a Beholder from the Under-Tunnels.",
        quest_type="fetch",
        target_key="beholder eye",
        target_count=1,
        rewards={"xp": 1400, "gold": 950, "faction": -14},
        giver_npc_key="Evil Spell Trainer",
        level_required=44,
        scale_rewards=True,
        completion_text="The Beholder's eye still twitches with anti-magic power. Magnificent.",
    ))

    # --- Level 51-60 Quests ---

    quest_registry.register(QuestDefinition(
        id="good_ancient_dragon",
        name="Ancient Dragon Slayer",
        description="An ancient dragon threatens all of Aethelgard. This is your greatest challenge.",
        quest_type="kill",
        target_key="ancient dragon",
        target_count=1,
        rewards={"xp": 3000, "gold": 2500, "faction": 25},
        giver_npc_key="Good Quartermaster",
        level_required=52,
        scale_rewards=True,
        completion_text="LEGENDARY! You have slain an ancient dragon! Songs will be sung for ages.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_kraken_threat",
        name="Kraken Threat",
        description="A kraken spawn terrorizes the Dawn-Light Coast. Defeat it.",
        quest_type="kill",
        target_key="kraken spawn",
        target_count=1,
        rewards={"xp": 2500, "gold": 2000, "faction": 20},
        giver_npc_key="Good Quartermaster",
        level_required=55,
        scale_rewards=True,
        completion_text="The kraken spawn sinks beneath the waves. The coast is safe.",
    ))

    quest_registry.register(QuestDefinition(
        id="good_divine_artifact",
        name="Divine Artifact",
        description="Retrieve the Aegis of Faith from the Celestial Dais.",
        quest_type="fetch",
        target_key="aegis of faith",
        target_count=1,
        rewards={"xp": 2200, "gold": 1800, "faction": 22},
        giver_npc_key="Good Spell Trainer",
        level_required=54,
        scale_rewards=True,
        completion_text="The Aegis of Faith! A divine artifact of immense protective power.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_pit_fiend",
        name="Pit Fiend Commander",
        description="Subjugate a pit fiend in the Hellfire Spire to lead our demonic legions.",
        quest_type="kill",
        target_key="pit fiend",
        target_count=1,
        rewards={"xp": 2800, "gold": 2200, "faction": -22},
        giver_npc_key="Evil Quartermaster",
        level_required=53,
        scale_rewards=True,
        completion_text="The pit fiend kneels before you. Our demonic army has its general.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_void_crystal",
        name="Void Crystal",
        description="Extract a void crystal from the Dread Valley for the grand ritual.",
        quest_type="fetch",
        target_key="void crystal",
        target_count=1,
        rewards={"xp": 2400, "gold": 1900, "faction": -20},
        giver_npc_key="Evil Spell Trainer",
        level_required=51,
        scale_rewards=True,
        completion_text="The void crystal pulses with dark energy. The grand ritual nears completion.",
    ))

    # --- Level 61-80 Quests ---

    quest_registry.register(QuestDefinition(
        id="good_world_eater",
        name="The World-Eater",
        description="The Void World-Eater threatens to consume all of reality. This is the final battle.",
        quest_type="kill",
        target_key="void world-eater",
        target_count=1,
        rewards={"xp": 10000, "gold": 8000, "faction": 50},
        giver_npc_key="Good Quartermaster",
        level_required=65,
        scale_rewards=True,
        completion_text="IMPOSSIBLE! You have defeated the World-Eater! Reality itself is saved!",
    ))

    quest_registry.register(QuestDefinition(
        id="good_phoenix_rising",
        name="Phoenix Rising",
        description="Aid the Sacred Phoenix in its rebirth at the Lost Temple.",
        quest_type="talk",
        target_key="Sacred Phoenix",
        target_count=1,
        rewards={"xp": 3500, "gold": 3000, "faction": 30},
        giver_npc_key="Good Spell Trainer",
        level_required=62,
        scale_rewards=True,
        completion_text="The phoenix rises anew, its flames purifying the land. You are blessed.",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_apocalypse_ritual",
        name="Apocalypse Ritual",
        description="Complete the Apocalypse Ritual by speaking with the Dark Oracle in the Void Threshold.",
        quest_type="talk",
        target_key="Dark Oracle",
        target_count=1,
        rewards={"xp": 4000, "gold": 3500, "faction": -30},
        giver_npc_key="Evil Spell Trainer",
        level_required=63,
        scale_rewards=True,
        completion_text="The ritual is complete. The apocalypse draws near. The Horde shall reign!",
    ))

    quest_registry.register(QuestDefinition(
        id="evil_elder_elemental",
        name="Elder Elemental",
        description="Bind an elder elemental from the Northern Ancient Forest to the Horde's will.",
        quest_type="kill",
        target_key="elder elemental",
        target_count=1,
        rewards={"xp": 5000, "gold": 4000, "faction": -35},
        giver_npc_key="Evil Quartermaster",
        level_required=66,
        scale_rewards=True,
        completion_text="The elder elemental is bound. Nature itself now serves the Horde.",
    ))

    # --- Boss Progression Quests (L30-80, tied to BOSS_REGISTRY) ---

    # Good: Vampire Marquis (L30)
    quest_registry.register(QuestDefinition(
        id="good_vampire_marquis",
        name="Hunt: Vampire Marquis",
        description="The Vampire Marquis terrorizes the Blood Sanctuary. Destroy this ancient evil.",
        quest_type="kill",
        target_key="vampire_marquis",
        target_count=1,
        rewards={"xp": 1200, "gold": 800, "faction": 15, "reputation": 200},
        giver_npc_key="Good Quartermaster",
        level_required=30,
        scale_rewards=True,
        completion_text="The Vampire Marquis crumbles to dust. The Blood Sanctuary is cleansed.",
    ))

    # Evil: Treant Lord (L30)
    quest_registry.register(QuestDefinition(
        id="evil_treant_lord",
        name="Corrupt: Treant Lord",
        description="The Treant Lord guards the Emerald Grove. Destroy this ancient guardian for the Horde.",
        quest_type="kill",
        target_key="treant_lord",
        target_count=1,
        rewards={"xp": 1200, "gold": 800, "faction": -15, "reputation": 200},
        giver_npc_key="Evil Quartermaster",
        level_required=30,
        scale_rewards=True,
        completion_text="The Treant Lord falls! The Emerald Grove will wither without its guardian.",
    ))

    # Good: Demon Overlord (L35)
    quest_registry.register(QuestDefinition(
        id="good_demon_overlord",
        name="Banish: Demon Overlord",
        description="The Demon Overlord commands legions from the Abyssal Rift. Banish it back to the abyss.",
        quest_type="kill",
        target_key="demon_overlord",
        target_count=1,
        rewards={"xp": 1800, "gold": 1200, "faction": 20, "reputation": 300},
        giver_npc_key="Good Quartermaster",
        level_required=35,
        scale_rewards=True,
        completion_text="The Demon Overlord is banished! The Abyssal Rift seals behind it.",
    ))

    # Evil: Sanctified Golem (L35)
    quest_registry.register(QuestDefinition(
        id="evil_sanctified_golem",
        name="Shatter: Sanctified Golem",
        description="The Sanctified Golem protects Aethelgard's holy sites. Reduce it to rubble.",
        quest_type="kill",
        target_key="sanctified_golem",
        target_count=1,
        rewards={"xp": 1800, "gold": 1200, "faction": -20, "reputation": 300},
        giver_npc_key="Evil Quartermaster",
        level_required=35,
        scale_rewards=True,
        completion_text="The Sanctified Golem is rubble. Aethelgard's defenses weaken.",
    ))

    # Good: Hellhound Alpha (L40)
    quest_registry.register(QuestDefinition(
        id="good_hellhound_alpha",
        name="Slay: Hellhound Alpha",
        description="The Hellhound Alpha leads its pack from the Iron Kennel. End its reign.",
        quest_type="kill",
        target_key="hellhound_alpha",
        target_count=1,
        rewards={"xp": 2200, "gold": 1500, "faction": 22, "reputation": 350},
        giver_npc_key="Good Quartermaster",
        level_required=40,
        scale_rewards=True,
        completion_text="The Hellhound Alpha is slain. Its pack scatters without a leader.",
    ))

    # Evil: Sentinel Captain (L40)
    quest_registry.register(QuestDefinition(
        id="evil_sentinel_captain",
        name="Assassinate: Sentinel Captain",
        description="The Sentinel Captain commands Aethelgard's border forces. Eliminate this threat.",
        quest_type="kill",
        target_key="sentinel_captain",
        target_count=1,
        rewards={"xp": 2200, "gold": 1500, "faction": -22, "reputation": 350},
        giver_npc_key="Evil Quartermaster",
        level_required=40,
        scale_rewards=True,
        completion_text="The Sentinel Captain falls. Aethelgard's borders are vulnerable.",
    ))

    # Good: Rotting Behemoth (L45)
    quest_registry.register(QuestDefinition(
        id="good_rotting_behemoth",
        name="Purge: Rotting Behemoth",
        description="The Rotting Behemoth spreads plague from its pit. Cleanse this abomination.",
        quest_type="kill",
        target_key="rotting_behemoth",
        target_count=1,
        rewards={"xp": 2800, "gold": 2000, "faction": 25, "reputation": 400},
        giver_npc_key="Good Quartermaster",
        level_required=45,
        scale_rewards=True,
        completion_text="The Rotting Behemoth dissolves into blessed ash. The plague recedes.",
    ))

    # Evil: Arcane Guardian (L45)
    quest_registry.register(QuestDefinition(
        id="evil_arcane_guardian",
        name="Destroy: Arcane Guardian",
        description="The Arcane Guardian shields the Crystal Cave. Shatter its magical defenses.",
        quest_type="kill",
        target_key="arcane_guardian",
        target_count=1,
        rewards={"xp": 2800, "gold": 2000, "faction": -25, "reputation": 400},
        giver_npc_key="Evil Quartermaster",
        level_required=45,
        scale_rewards=True,
        completion_text="The Arcane Guardian shatters. The Crystal Cave's magic is ours.",
    ))

    # Good: Nightstalker (L50)
    quest_registry.register(QuestDefinition(
        id="good_nightstalker",
        name="Hunt: Nightstalker",
        description="The Nightstalker lurks in the Shadow Lair, preying on travelers. Bring it into the light.",
        quest_type="kill",
        target_key="nightstalker",
        target_count=1,
        rewards={"xp": 3500, "gold": 2500, "faction": 28, "reputation": 500},
        giver_npc_key="Good Quartermaster",
        level_required=50,
        scale_rewards=True,
        completion_text="The Nightstalker is no more. The shadows retreat from the light.",
    ))

    # Evil: Knight Commander (L50)
    quest_registry.register(QuestDefinition(
        id="evil_knight_commander",
        name="Defeat: Knight Commander",
        description="The Knight Commander leads Aethelgard's elite forces. Break their spirit.",
        quest_type="kill",
        target_key="knight_commander",
        target_count=1,
        rewards={"xp": 3500, "gold": 2500, "faction": -28, "reputation": 500},
        giver_npc_key="Evil Quartermaster",
        level_required=50,
        scale_rewards=True,
        completion_text="The Knight Commander is defeated. Aethelgard's morale crumbles.",
    ))

    # Good: Fire Giant King (L55)
    quest_registry.register(QuestDefinition(
        id="good_fire_giant_king",
        name="Topple: Fire Giant King",
        description="The Fire Giant King forges weapons of war in the Obsidian Forge. End his tyranny.",
        quest_type="kill",
        target_key="fire_giant_king",
        target_count=1,
        rewards={"xp": 4500, "gold": 3200, "faction": 32, "reputation": 600},
        giver_npc_key="Good Quartermaster",
        level_required=55,
        scale_rewards=True,
        completion_text="The Fire Giant King falls! The Obsidian Forge grows cold.",
    ))

    # Evil: Inquisitor Valen (L55)
    quest_registry.register(QuestDefinition(
        id="evil_inquisitor_valen",
        name="Silence: Inquisitor Valen",
        description="Inquisitor Valen hunts our agents. Silence this zealot forever.",
        quest_type="kill",
        target_key="inquisitor_valen",
        target_count=1,
        rewards={"xp": 4500, "gold": 3200, "faction": -32, "reputation": 600},
        giver_npc_key="Evil Quartermaster",
        level_required=55,
        scale_rewards=True,
        completion_text="Inquisitor Valen is silenced. Our agents move freely once more.",
    ))

    # Good: High Priestess (L60)
    quest_registry.register(QuestDefinition(
        id="good_high_priestess",
        name="Confront: High Priestess",
        description="The High Priestess leads the Shadow Temple's dark rituals. End her blasphemy.",
        quest_type="kill",
        target_key="high_priestess",
        target_count=1,
        rewards={"xp": 5500, "gold": 4000, "faction": 35, "reputation": 700},
        giver_npc_key="Good Quartermaster",
        level_required=60,
        scale_rewards=True,
        completion_text="The High Priestess is defeated. The Shadow Temple's power is broken.",
    ))

    # Evil: Fallen Angel (L60)
    quest_registry.register(QuestDefinition(
        id="evil_fallen_angel",
        name="Corrupt: Fallen Angel",
        description="The Fallen Angel still clings to remnants of light. Drag it fully into darkness.",
        quest_type="kill",
        target_key="fallen_angel",
        target_count=1,
        rewards={"xp": 5500, "gold": 4000, "faction": -35, "reputation": 700},
        giver_npc_key="Evil Quartermaster",
        level_required=60,
        scale_rewards=True,
        completion_text="The Fallen Angel embraces darkness. A powerful ally joins the Horde.",
    ))

    # Good: Mummy Lord (L65)
    quest_registry.register(QuestDefinition(
        id="good_mummy_lord",
        name="Destroy: Mummy Lord",
        description="The Mummy Lord rises from the Cursed Chamber. Send it back to the grave.",
        quest_type="kill",
        target_key="mummy_lord",
        target_count=1,
        rewards={"xp": 7000, "gold": 5000, "faction": 40, "reputation": 800},
        giver_npc_key="Good Quartermaster",
        level_required=65,
        scale_rewards=True,
        completion_text="The Mummy Lord crumbles to dust. The curse is lifted.",
    ))

    # Evil: Griffin Matriarch (L65)
    quest_registry.register(QuestDefinition(
        id="evil_griffin_matriarch",
        name="Slay: Griffin Matriarch",
        description="The Griffin Matriarch protects Aethelgard's skies. Bring her down.",
        quest_type="kill",
        target_key="griffin_matriarch",
        target_count=1,
        rewards={"xp": 7000, "gold": 5000, "faction": -40, "reputation": 800},
        giver_npc_key="Evil Quartermaster",
        level_required=65,
        scale_rewards=True,
        completion_text="The Griffin Matriarch plummets from the sky. The air is ours.",
    ))

    # Good: Chimera (L70)
    quest_registry.register(QuestDefinition(
        id="good_chimera",
        name="Vanquish: Chimera",
        description="The Chimera's toxic breath poisons the land. End this abomination.",
        quest_type="kill",
        target_key="chimera",
        target_count=1,
        rewards={"xp": 8500, "gold": 6000, "faction": 45, "reputation": 900},
        giver_npc_key="Good Quartermaster",
        level_required=70,
        scale_rewards=True,
        completion_text="The Chimera is vanquished! The land can heal once more.",
    ))

    # Evil: Tide Sovereign (L70)
    quest_registry.register(QuestDefinition(
        id="evil_tide_sovereign",
        name="Drown: Tide Sovereign",
        description="The Tide Sovereign commands the seas for Aethelgard. Sink this ocean lord.",
        quest_type="kill",
        target_key="tide_sovereign",
        target_count=1,
        rewards={"xp": 8500, "gold": 6000, "faction": -45, "reputation": 900},
        giver_npc_key="Evil Quartermaster",
        level_required=70,
        scale_rewards=True,
        completion_text="The Tide Sovereign sinks beneath the waves. The seas belong to the Horde.",
    ))

    # Good: Hydra (L75)
    quest_registry.register(QuestDefinition(
        id="good_hydra",
        name="Decapitate: Hydra",
        description="The Hydra regenerates endlessly in the Venom Pit. Cauterize every head.",
        quest_type="kill",
        target_key="hydra",
        target_count=1,
        rewards={"xp": 10000, "gold": 7500, "faction": 48, "reputation": 1000},
        giver_npc_key="Good Quartermaster",
        level_required=75,
        scale_rewards=True,
        completion_text="The Hydra's last head falls. The Venom Pit is finally silent.",
    ))

    # Evil: Holy Avatar (L75)
    quest_registry.register(QuestDefinition(
        id="evil_holy_avatar",
        name="Desecrate: Holy Avatar",
        description="The Holy Avatar is Aethelgard's living embodiment of light. Extinguish it.",
        quest_type="kill",
        target_key="holy_avatar",
        target_count=1,
        rewards={"xp": 10000, "gold": 7500, "faction": -48, "reputation": 1000},
        giver_npc_key="Evil Quartermaster",
        level_required=75,
        scale_rewards=True,
        completion_text="The Holy Avatar's light fades. Darkness spreads across the land.",
    ))

    # Good: Werewolf Alpha (L80)
    quest_registry.register(QuestDefinition(
        id="good_werewolf_alpha",
        name="Hunt: Werewolf Alpha",
        description="The Werewolf Alpha commands the Howling Den. End the lycanthrope threat.",
        quest_type="kill",
        target_key="werewolf_alpha",
        target_count=1,
        rewards={"xp": 12000, "gold": 9000, "faction": 50, "reputation": 1200},
        giver_npc_key="Good Quartermaster",
        level_required=80,
        scale_rewards=True,
        completion_text="The Werewolf Alpha is slain. The Howling Den falls silent forever.",
    ))

    # Evil: Sacred Phoenix (L80)
    quest_registry.register(QuestDefinition(
        id="evil_sacred_phoenix",
        name="Extinguish: Sacred Phoenix",
        description="The Sacred Phoenix's flames purify the land. Snuff out its eternal fire.",
        quest_type="kill",
        target_key="sacred_phoenix",
        target_count=1,
        rewards={"xp": 12000, "gold": 9000, "faction": -50, "reputation": 1200},
        giver_npc_key="Evil Quartermaster",
        level_required=80,
        scale_rewards=True,
        completion_text="The Sacred Phoenix's flames die. Eternal darkness claims the land.",
    ))

    # Good: World-Eater (L85) — Ultimate Boss
    quest_registry.register(QuestDefinition(
        id="good_world_eater_boss",
        name="The Final Battle: World-Eater",
        description="The World-Eater threatens to consume all reality. This is the ultimate test.",
        quest_type="kill",
        target_key="world_eater",
        target_count=1,
        rewards={"xp": 25000, "gold": 15000, "faction": 100, "reputation": 2000},
        giver_npc_key="Good Quartermaster",
        level_required=85,
        scale_rewards=True,
        completion_text="LEGENDARY! You have defeated the World-Eater! Reality itself is saved! Songs will be sung of this day for millennia.",
    ))

    # Evil: Crusader General (L85) — Ultimate Boss
    quest_registry.register(QuestDefinition(
        id="evil_crusader_general",
        name="The Final Conquest: Crusader General",
        description="The Crusader General is Aethelgard's last hope. Crush their final champion.",
        quest_type="kill",
        target_key="crusader_general",
        target_count=1,
        rewards={"xp": 25000, "gold": 15000, "faction": -100, "reputation": 2000},
        giver_npc_key="Evil Quartermaster",
        level_required=85,
        scale_rewards=True,
        completion_text="THE CRUSADER GENERAL FALLS! Aethelgard's last hope is extinguished. The Horde reigns supreme!",
    ))

    # --- Daily Quests ---

    quest_registry.register(QuestDefinition(
        id="daily_good_patrol",
        name="Daily: Border Patrol",
        description="Patrol the borders and eliminate 3 hostile creatures threatening Aethelgard.",
        quest_type="kill",
        target_key="wolf",
        target_count=3,
        rewards={"xp": 200, "gold": 100, "faction": 3},
        giver_npc_key="Good Quartermaster",
        level_required=5,
        daily=True,
        scale_rewards=True,
        completion_text="The border is secure. Report back tomorrow for another patrol.",
    ))

    quest_registry.register(QuestDefinition(
        id="daily_good_supply_run",
        name="Daily: Supply Run",
        description="Deliver 2 supply crates to the front-line troops.",
        quest_type="fetch",
        target_key="supply crate",
        target_count=2,
        rewards={"xp": 180, "gold": 90, "faction": 2},
        giver_npc_key="Good Quartermaster",
        level_required=5,
        daily=True,
        scale_rewards=True,
        completion_text="The troops are resupplied. Every crate helps the war effort.",
    ))

    quest_registry.register(QuestDefinition(
        id="daily_evil_raid",
        name="Daily: Border Raid",
        description="Raid Aethelgard's borders and slay 3 of their scouts.",
        quest_type="kill",
        target_key="goblin scout",
        target_count=3,
        rewards={"xp": 200, "gold": 100, "faction": -3},
        giver_npc_key="Evil Quartermaster",
        level_required=5,
        daily=True,
        scale_rewards=True,
        completion_text="The scouts are dead. Their intelligence dies with them.",
    ))

    quest_registry.register(QuestDefinition(
        id="daily_evil_dark_offering",
        name="Daily: Dark Offering",
        description="Collect 2 dark essences from fallen enemies for the temple.",
        quest_type="fetch",
        target_key="dark essence",
        target_count=2,
        rewards={"xp": 180, "gold": 90, "faction": -2},
        giver_npc_key="Evil Spell Trainer",
        level_required=5,
        daily=True,
        scale_rewards=True,
        completion_text="The dark essences feed the temple's power. Return tomorrow.",
    ))

    # --- Quest Chains ---

    # Chain: The Wolf Saga (Good)
    quest_registry.register(QuestDefinition(
        id="wolf_saga_1",
        name="The Wolf Saga: Alpha's Howl",
        description="Hunt the alpha wolf terrorizing Sunspire Meadows.",
        quest_type="kill",
        target_key="dire wolf",
        target_count=1,
        rewards={"xp": 300, "gold": 150, "faction": 5},
        giver_npc_key="Good Quartermaster",
        level_required=10,
        chain_id="wolf_saga",
        chain_order=0,
        scale_rewards=True,
        completion_text="The alpha is dead, but you sense a darker force behind the attacks...",
    ))

    quest_registry.register(QuestDefinition(
        id="wolf_saga_2",
        name="The Wolf Saga: Dark Influence",
        description="Investigate the source of the wolf attacks. Speak with the Forest Spirit.",
        quest_type="talk",
        target_key="Forest Spirit",
        target_count=1,
        rewards={"xp": 250, "gold": 120, "faction": 4},
        giver_npc_key="Good Quartermaster",
        level_required=12,
        chain_id="wolf_saga",
        chain_order=1,
        prereq_quests=["wolf_saga_1"],
        scale_rewards=True,
        completion_text="The Forest Spirit reveals a necromancer is corrupting the wildlife!",
    ))

    quest_registry.register(QuestDefinition(
        id="wolf_saga_3",
        name="The Wolf Saga: Necromancer's End",
        description="Confront and defeat the Rogue Necromancer in the Silverwood Forest.",
        quest_type="kill",
        target_key="rogue necromancer",
        target_count=1,
        rewards={"xp": 500, "gold": 300, "faction": 8},
        giver_npc_key="Good Quartermaster",
        level_required=15,
        chain_id="wolf_saga",
        chain_order=2,
        prereq_quests=["wolf_saga_2"],
        scale_rewards=True,
        completion_text="The necromancer is defeated! The forest is healing. You are a hero of Aethelgard.",
    ))

    # Chain: The Shadow Conspiracy (Evil)
    quest_registry.register(QuestDefinition(
        id="shadow_conspiracy_1",
        name="Shadow Conspiracy: First Contact",
        description="Make contact with the Shadow Broker in the Verdant Mire.",
        quest_type="talk",
        target_key="Shadow Broker",
        target_count=1,
        rewards={"xp": 300, "gold": 150, "faction": -5},
        giver_npc_key="Evil Quartermaster",
        level_required=10,
        chain_id="shadow_conspiracy",
        chain_order=0,
        scale_rewards=True,
        completion_text="The Shadow Broker whispers of a traitor within the Horde...",
    ))

    quest_registry.register(QuestDefinition(
        id="shadow_conspiracy_2",
        name="Shadow Conspiracy: Traitor's Blood",
        description="Eliminate the traitorous Horde Captain hiding in the Rotwood Forest.",
        quest_type="kill",
        target_key="horde traitor",
        target_count=1,
        rewards={"xp": 450, "gold": 280, "faction": -7},
        giver_npc_key="Evil Quartermaster",
        level_required=13,
        chain_id="shadow_conspiracy",
        chain_order=1,
        prereq_quests=["shadow_conspiracy_1"],
        scale_rewards=True,
        completion_text="The traitor is dead. But the conspiracy runs deeper than we thought...",
    ))

    quest_registry.register(QuestDefinition(
        id="shadow_conspiracy_3",
        name="Shadow Conspiracy: Mastermind",
        description="Confront the mastermind behind the conspiracy in the Drow Caverns.",
        quest_type="kill",
        target_key="conspiracy mastermind",
        target_count=1,
        rewards={"xp": 600, "gold": 400, "faction": -10},
        giver_npc_key="Evil Quartermaster",
        level_required=16,
        chain_id="shadow_conspiracy",
        chain_order=2,
        prereq_quests=["shadow_conspiracy_2"],
        scale_rewards=True,
        completion_text="The conspiracy is crushed. The Horde is stronger than ever. You are feared.",
    ))
