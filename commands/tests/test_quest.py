"""
Unit tests for the Quest System: QuestRegistry, QuestHandler,
quest commands, and quest lifecycle (accept, progress, complete).

Run with:
    evennia test commands.tests.test_quest
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultRoom, DefaultObject
from evennia import create_object

from typeclasses.characters import Character
from commands.quest import CmdQuest
from world.quests import (
    QuestDefinition,
    QuestRegistry,
    ActiveQuest,
    QuestHandler,
    quest_registry,
    register_default_quests,
)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def setup_test_quests():
    """Register a clean set of test quests. Returns (kill_q, fetch_q, talk_q)."""
    quest_registry.clear()

    kill_q = QuestDefinition(
        id="test_kill_wolves",
        name="Kill Wolves",
        description="Kill 3 wolves.",
        quest_type="kill",
        target_key="wolf",
        target_count=3,
        rewards={"xp": 100, "gold": 50},
        giver_npc_key="Test NPC",
        level_required=1,
    )

    fetch_q = QuestDefinition(
        id="test_fetch_herbs",
        name="Fetch Herbs",
        description="Collect 2 healing herbs.",
        quest_type="fetch",
        target_key="healing herb",
        target_count=2,
        rewards={"xp": 80, "gold": 30, "faction": 2},
        giver_npc_key="Test NPC",
        level_required=1,
    )

    talk_q = QuestDefinition(
        id="test_talk_scout",
        name="Talk to Scout",
        description="Speak with the Scout NPC.",
        quest_type="talk",
        target_key="Scout",
        target_count=1,
        rewards={"xp": 50, "items": ["Iron Sword"]},
        giver_npc_key="Test NPC",
        level_required=1,
    )

    quest_registry.register(kill_q)
    quest_registry.register(fetch_q)
    quest_registry.register(talk_q)

    return kill_q, fetch_q, talk_q


# ---------------------------------------------------------------------------
# QuestDefinition Tests
# ---------------------------------------------------------------------------

class TestQuestDefinition(BaseEvenniaTest):
    """Unit tests for QuestDefinition data class."""

    def test_create_kill_quest(self):
        """Create a kill-type quest definition."""
        q = QuestDefinition(
            id="test",
            name="Test Kill Quest",
            description="Kill things.",
            quest_type="kill",
            target_key="goblin",
            target_count=5,
        )
        self.assertEqual(q.id, "test")
        self.assertEqual(q.quest_type, "kill")
        self.assertEqual(q.target_key, "goblin")
        self.assertEqual(q.target_count, 5)
        self.assertEqual(q.prereq_quests, [])
        self.assertFalse(q.repeatable)

    def test_default_values(self):
        """Default values are set correctly."""
        q = QuestDefinition(
            id="minimal",
            name="Minimal",
            description="A minimal quest.",
            quest_type="talk",
            target_key="NPC",
        )
        self.assertEqual(q.target_count, 1)
        self.assertEqual(q.rewards, {})
        self.assertIsNone(q.giver_npc_key)
        self.assertEqual(q.level_required, 1)
        self.assertEqual(q.prereq_quests, [])
        self.assertFalse(q.repeatable)
        self.assertIn("Minimal", q.completion_text)

    def test_repr_string(self):
        """String representation includes id and type."""
        q = QuestDefinition(
            id="repr_test",
            name="Repr",
            description="Test repr.",
            quest_type="fetch",
            target_key="item",
        )
        r = repr(q)
        self.assertIn("repr_test", r)
        self.assertIn("fetch", r)


# ---------------------------------------------------------------------------
# QuestRegistry Tests
# ---------------------------------------------------------------------------

class TestQuestRegistry(BaseEvenniaTest):
    """Unit tests for QuestRegistry."""

    def setUp(self):
        super().setUp()
        quest_registry.clear()

    def tearDown(self):
        quest_registry.clear()
        super().tearDown()

    def test_register_and_get(self):
        """Register a quest and retrieve it by ID."""
        q = QuestDefinition(
            id="reg_test",
            name="Registry Test",
            description="Testing registration.",
            quest_type="kill",
            target_key="rat",
        )
        quest_registry.register(q)
        self.assertEqual(quest_registry.get("reg_test"), q)
        self.assertIsNone(quest_registry.get("nonexistent"))

    def test_register_non_quest_raises(self):
        """Registering a non-QuestDefinition raises TypeError."""
        with self.assertRaises(TypeError):
            quest_registry.register("not a quest")

    def test_get_by_npc(self):
        """Retrieve quests offered by a specific NPC."""
        q1 = QuestDefinition(
            id="npc_q1",
            name="NPC Q1",
            description="Test.",
            quest_type="kill",
            target_key="orc",
            giver_npc_key="Orc Trainer",
        )
        q2 = QuestDefinition(
            id="npc_q2",
            name="NPC Q2",
            description="Test 2.",
            quest_type="fetch",
            target_key="ore",
            giver_npc_key="Orc Trainer",
        )
        q3 = QuestDefinition(
            id="npc_q3",
            name="NPC Q3",
            description="Test 3.",
            quest_type="talk",
            target_key="Chief",
            giver_npc_key="Elf Elder",
        )
        quest_registry.register(q1)
        quest_registry.register(q2)
        quest_registry.register(q3)

        orc_quests = quest_registry.get_by_npc("Orc Trainer")
        self.assertEqual(len(orc_quests), 2)
        self.assertIn(q1, orc_quests)
        self.assertIn(q2, orc_quests)
        self.assertNotIn(q3, orc_quests)

    def test_get_by_npc_case_insensitive(self):
        """NPC lookup is case-insensitive."""
        q = QuestDefinition(
            id="case_q",
            name="Case Quest",
            description="Test case.",
            quest_type="kill",
            target_key="spider",
            giver_npc_key="Mixed Case NPC",
        )
        quest_registry.register(q)
        result = quest_registry.get_by_npc("mixed case npc")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "case_q")

    def test_get_by_npc_no_npcs(self):
        """Returns empty list when no NPCs registered."""
        q = QuestDefinition(
            id="no_npc",
            name="No NPC",
            description="No NPC quest.",
            quest_type="kill",
            target_key="target",
            giver_npc_key=None,
        )
        quest_registry.register(q)
        result = quest_registry.get_by_npc("Some NPC")
        self.assertEqual(result, [])

    def test_all_returns_all(self):
        """all() returns all registered quests."""
        q1 = QuestDefinition(
            id="all_1", name="A1", description="D1",
            quest_type="kill", target_key="t1",
        )
        q2 = QuestDefinition(
            id="all_2", name="A2", description="D2",
            quest_type="talk", target_key="t2",
        )
        quest_registry.register(q1)
        quest_registry.register(q2)
        all_q = quest_registry.all()
        self.assertEqual(len(all_q), 2)
        self.assertIn(q1, all_q)
        self.assertIn(q2, all_q)

    def test_clear_removes_all(self):
        """clear() removes all registered quests."""
        q = QuestDefinition(
            id="clear_me", name="Clear", description="C",
            quest_type="kill", target_key="t",
        )
        quest_registry.register(q)
        self.assertIsNotNone(quest_registry.get("clear_me"))
        quest_registry.clear()
        self.assertIsNone(quest_registry.get("clear_me"))
        self.assertEqual(quest_registry.all(), [])


# ---------------------------------------------------------------------------
# ActiveQuest Tests
# ---------------------------------------------------------------------------

class TestActiveQuest(BaseEvenniaTest):
    """Unit tests for ActiveQuest progress tracking."""

    def setUp(self):
        super().setUp()
        self.qdef = QuestDefinition(
            id="progress_test",
            name="Progress Quest",
            description="Track progress.",
            quest_type="kill",
            target_key="slime",
            target_count=3,
        )

    def test_initial_progress_zero(self):
        """New ActiveQuest starts at progress 0."""
        aq = ActiveQuest(self.qdef)
        self.assertEqual(aq.progress, 0)
        self.assertFalse(aq.is_complete)

    def test_advance_increments_progress(self):
        """advance() increments progress toward target."""
        aq = ActiveQuest(self.qdef)
        aq.advance()
        self.assertEqual(aq.progress, 1)
        aq.advance()
        self.assertEqual(aq.progress, 2)
        self.assertFalse(aq.is_complete)

    def test_advance_completes_at_target(self):
        """Quest becomes complete when progress reaches target."""
        aq = ActiveQuest(self.qdef)
        aq.advance(1)
        aq.advance(1)
        became_complete = aq.advance(1)
        self.assertEqual(aq.progress, 3)
        self.assertTrue(aq.is_complete)
        self.assertTrue(became_complete)

    def test_advance_cannot_exceed_target(self):
        """Progress does not exceed target_count."""
        aq = ActiveQuest(self.qdef)
        aq.advance(5)
        self.assertEqual(aq.progress, 3)

    def test_serialize_roundtrip(self):
        """Serialize and deserialize preserve state."""
        aq = ActiveQuest(self.qdef, progress=2)
        data = aq.serialize()
        self.assertEqual(data["quest_id"], "progress_test")
        self.assertEqual(data["progress"], 2)

        restored = ActiveQuest.deserialize(data, self.qdef)
        self.assertEqual(restored.quest_id, "progress_test")
        self.assertEqual(restored.progress, 2)


# ---------------------------------------------------------------------------
# QuestHandler Tests (accept, progress, complete)
# ---------------------------------------------------------------------------

class TestQuestHandler(BaseEvenniaTest):
    """Tests for the QuestHandler lifecycle: accept, track, complete."""

    def setUp(self):
        super().setUp()
        self.char = create_object(Character, key="QuestHero")
        self.char.attributes.add("level", 5)
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char.location = self.room

        # Create a test NPC in the room
        self.npc = create_object(DefaultObject, key="Test NPC")
        self.npc.location = self.room

        # Setup quests
        self.kill_q, self.fetch_q, self.talk_q = setup_test_quests()

    def tearDown(self):
        self.char.delete()
        self.npc.delete()
        self.room.delete()
        quest_registry.clear()
        super().tearDown()

    def test_accept_quest_from_npc(self):
        """Accept a quest successfully from an NPC in the room."""
        success, msg = self.char.quests.accept("test_kill_wolves")
        self.assertTrue(success)
        self.assertIn("Kill Wolves", msg)
        self.assertTrue(self.char.quests.is_active("test_kill_wolves"))

    def test_accept_nonexistent_quest(self):
        """Accepting a nonexistent quest fails."""
        success, msg = self.char.quests.accept("nonexistent_quest")
        self.assertFalse(success)
        self.assertIn("does not exist", msg)

    def test_cannot_accept_twice(self):
        """Cannot accept a quest that's already active."""
        self.char.quests.accept("test_kill_wolves")
        success, msg = self.char.quests.accept("test_kill_wolves")
        self.assertFalse(success)
        self.assertIn("already accepted", msg)

    def test_accept_from_wrong_room(self):
        """Cannot accept if NPC is not in the same room."""
        # Move NPC to a different room
        other_room = create_object(DefaultRoom, key="Other Room")
        self.npc.location = other_room

        success, msg = self.char.quests.accept("test_kill_wolves")
        self.assertFalse(success)
        self.assertIn("No NPC here", msg)

        other_room.delete()

    def test_cannot_accept_completed_non_repeatable(self):
        """Cannot re-accept a non-repeatable completed quest."""
        # Complete the quest by advancing progress naturally
        self.char.quests.accept("test_kill_wolves")
        for _ in range(3):
            self.char.quests.report_kill("wolf")
        self.char.quests.complete("test_kill_wolves")

        # Try to accept again from the same NPC
        success, msg = self.char.quests.accept("test_kill_wolves")
        self.assertFalse(success)
        self.assertIn("already completed", msg)

    def test_level_requirement_blocks(self):
        """Low-level character cannot accept high-level quests."""
        self.char.attributes.add("level", 1)
        # Register a high-level quest
        high_q = QuestDefinition(
            id="high_level_q",
            name="High Level",
            description="Requires level 10.",
            quest_type="kill",
            target_key="dragon",
            target_count=1,
            rewards={"xp": 500},
            giver_npc_key="Test NPC",
            level_required=10,
        )
        quest_registry.register(high_q)

        success, msg = self.char.quests.accept("high_level_q")
        self.assertFalse(success)

    def test_accept_multiple_quests(self):
        """Can accept multiple different quests at once."""
        success1, _ = self.char.quests.accept("test_kill_wolves")
        success2, _ = self.char.quests.accept("test_fetch_herbs")
        self.assertTrue(success1)
        self.assertTrue(success2)
        self.assertTrue(self.char.quests.is_active("test_kill_wolves"))
        self.assertTrue(self.char.quests.is_active("test_fetch_herbs"))

    def test_status_shows_active_quests(self):
        """status() returns formatted active quests."""
        self.char.quests.accept("test_kill_wolves")
        text, active = self.char.quests.status()
        self.assertIn("Kill Wolves", text)
        self.assertIn("0/3", text)
        self.assertEqual(len(active), 1)

    def test_status_empty(self):
        """status() indicates no active quests when empty."""
        text, active = self.char.quests.status()
        self.assertIn("no active quests", text)
        self.assertEqual(active, [])

    def test_report_kill_advances_progress(self):
        """report_kill advances matching kill quests."""
        self.char.quests.accept("test_kill_wolves")
        updated = self.char.quests.report_kill("wolf")
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0][0], "test_kill_wolves")
        # Progress should be 1/3
        _, aq = self.char.quests._find_active("test_kill_wolves")
        self.assertEqual(aq.progress, 1)

    def test_report_kill_only_matches_correct_target(self):
        """report_kill only advances quests with matching target_key."""
        self.char.quests.accept("test_kill_wolves")
        updated = self.char.quests.report_kill("orc")
        self.assertEqual(len(updated), 0)  # No match for orc
        _, aq = self.char.quests._find_active("test_kill_wolves")
        self.assertEqual(aq.progress, 0)  # Unchanged

    def test_report_kill_completes_quest(self):
        """report_kill completes the quest when target reached."""
        self.char.quests.accept("test_kill_wolves")
        for _ in range(3):
            self.char.quests.report_kill("wolf")
        _, aq = self.char.quests._find_active("test_kill_wolves")
        self.assertTrue(aq.is_complete)
        self.assertEqual(aq.progress, 3)

    def test_report_kill_case_insensitive(self):
        """Target key matching is case-insensitive."""
        self.char.quests.accept("test_kill_wolves")
        self.char.quests.report_kill("WOLF")
        _, aq = self.char.quests._find_active("test_kill_wolves")
        self.assertEqual(aq.progress, 1)

    def test_report_fetch_advances_progress(self):
        """report_fetch advances matching fetch quests."""
        self.char.quests.accept("test_fetch_herbs")
        updated = self.char.quests.report_fetch("healing herb")
        self.assertEqual(len(updated), 1)
        _, aq = self.char.quests._find_active("test_fetch_herbs")
        self.assertEqual(aq.progress, 1)

    def test_report_fetch_completes_quest(self):
        """report_fetch completes when target count reached."""
        self.char.quests.accept("test_fetch_herbs")
        self.char.quests.report_fetch("healing herb", 2)
        _, aq = self.char.quests._find_active("test_fetch_herbs")
        self.assertTrue(aq.is_complete)

    def test_report_talk_advances_progress(self):
        """report_talk advances matching talk quests."""
        self.char.quests.accept("test_talk_scout")
        updated = self.char.quests.report_talk("Scout")
        self.assertEqual(len(updated), 1)
        _, aq = self.char.quests._find_active("test_talk_scout")
        self.assertEqual(aq.progress, 1)

    def test_report_talk_completes_quest(self):
        """report_talk completes the quest (target_count=1)."""
        self.char.quests.accept("test_talk_scout")
        self.char.quests.report_talk("Scout")
        _, aq = self.char.quests._find_active("test_talk_scout")
        self.assertTrue(aq.is_complete)

    def test_complete_quest_grants_rewards(self):
        """Completing a quest grants XP and gold."""
        self.char.quests.accept("test_kill_wolves")
        # Advance to target
        for _ in range(3):
            self.char.quests.report_kill("wolf")

        self.char.quests.complete("test_kill_wolves")

        self.assertEqual(self.char.attributes.get("xp"), 100)
        self.assertEqual(self.char.attributes.get("gold"), 50)
        self.assertTrue(self.char.quests.has_completed("test_kill_wolves"))
        self.assertFalse(self.char.quests.is_active("test_kill_wolves"))

    def test_complete_quest_grants_faction(self):
        """Completing a quest grants faction points."""
        self.char.quests.accept("test_fetch_herbs")
        self.char.quests.report_fetch("healing herb", 2)
        self.char.quests.complete("test_fetch_herbs")

        self.assertEqual(self.char.attributes.get("faction_points"), 2)

    def test_cannot_complete_without_npc(self):
        """Cannot complete if quest giver NPC is not in room."""
        self.char.quests.accept("test_kill_wolves")
        for _ in range(3):
            self.char.quests.report_kill("wolf")

        # Remove NPC from room
        self.npc.location = None

        success, msg = self.char.quests.complete("test_kill_wolves")
        self.assertFalse(success)
        self.assertIn("return to Test NPC", msg)

    def test_cannot_complete_incomplete_quest(self):
        """Cannot complete a quest that hasn't met the objective."""
        self.char.quests.accept("test_kill_wolves")
        # Only 1 kill out of 3
        self.char.quests.report_kill("wolf")

        success, msg = self.char.quests.complete("test_kill_wolves")
        self.assertFalse(success)
        self.assertIn("not completed", msg)

    def test_cannot_complete_non_active(self):
        """Cannot complete a quest that isn't active."""
        success, msg = self.char.quests.complete("test_kill_wolves")
        self.assertFalse(success)
        self.assertIn("do not have that quest", msg)

    def test_abandon_active_quest(self):
        """Abandoning a quest removes it from active list."""
        self.char.quests.accept("test_kill_wolves")
        self.assertTrue(self.char.quests.is_active("test_kill_wolves"))

        success, msg = self.char.quests.abandon("test_kill_wolves")
        self.assertTrue(success)
        self.assertIn("abandoned", msg)
        self.assertFalse(self.char.quests.is_active("test_kill_wolves"))
        # Not marked as completed
        self.assertFalse(self.char.quests.has_completed("test_kill_wolves"))

    def test_abandon_non_active_fails(self):
        """Cannot abandon a quest that isn't active."""
        success, msg = self.char.quests.abandon("test_kill_wolves")
        self.assertFalse(success)

    def test_get_completed_count(self):
        """get_completed_count returns correct count."""
        self.assertEqual(self.char.quests.get_completed_count(), 0)

        # Complete a quest
        self.char.quests.accept("test_kill_wolves")
        for _ in range(3):
            self.char.quests.report_kill("wolf")
        self.char.quests.complete("test_kill_wolves")

        self.assertEqual(self.char.quests.get_completed_count(), 1)

    def test_list_available_from_npc(self):
        """list_available returns quests from NPCs in the room."""
        available = self.char.quests.list_available()
        self.assertEqual(len(available), 3)  # All 3 quests from Test NPC
        available_ids = {q.id for _, q in available}
        self.assertIn("test_kill_wolves", available_ids)
        self.assertIn("test_fetch_herbs", available_ids)
        self.assertIn("test_talk_scout", available_ids)

    def test_list_available_excludes_active(self):
        """Active quests don't appear in available list."""
        self.char.quests.accept("test_kill_wolves")
        available = self.char.quests.list_available()
        available_ids = {q.id for _, q in available}
        self.assertNotIn("test_kill_wolves", available_ids)
        self.assertIn("test_fetch_herbs", available_ids)

    def test_list_available_excludes_completed(self):
        """Completed quests don't appear in available list (non-repeatable)."""
        self.char.quests.accept("test_kill_wolves")
        for _ in range(3):
            self.char.quests.report_kill("wolf")
        self.char.quests.complete("test_kill_wolves")

        available = self.char.quests.list_available()
        available_ids = {q.id for _, q in available}
        self.assertNotIn("test_kill_wolves", available_ids)

    def test_list_available_empty_room(self):
        """Empty room returns no available quests."""
        # Move NPC out
        self.npc.location = None
        available = self.char.quests.list_available()
        self.assertEqual(available, [])

    def test_list_available_no_location(self):
        """Character with no location returns empty list."""
        self.char.location = None
        available = self.char.quests.list_available()
        self.assertEqual(available, [])

    def test_repeatable_quest_shows_after_completion(self):
        """Repeatable quests appear in available list even after completion."""
        rq = QuestDefinition(
            id="repeatable_quest",
            name="Daily Rats",
            description="Kill rats daily.",
            quest_type="kill",
            target_key="rat",
            target_count=2,
            rewards={"xp": 10},
            giver_npc_key="Test NPC",
            repeatable=True,
        )
        quest_registry.register(rq)

        # Complete it once
        self.char.quests.accept("repeatable_quest")
        for _ in range(2):
            self.char.quests.report_kill("rat")
        self.char.quests.complete("repeatable_quest")

        # Should be available again
        available = self.char.quests.list_available()
        available_ids = {q.id for _, q in available}
        self.assertIn("repeatable_quest", available_ids)

    def test_prerequisite_blocks_unmet(self):
        """Quest with unmet prerequisites does not appear."""
        prereq_q = QuestDefinition(
            id="prereq_quest",
            name="Prerequisite",
            description="You must do this first.",
            quest_type="talk",
            target_key="Elder",
            target_count=1,
            rewards={"xp": 10},
            giver_npc_key="Test NPC",
        )
        dependent_q = QuestDefinition(
            id="dependent_quest",
            name="Dependent",
            description="Requires prerequisite.",
            quest_type="kill",
            target_key="mob",
            target_count=2,
            rewards={"xp": 20},
            giver_npc_key="Test NPC",
            prereq_quests=["prereq_quest"],
        )
        quest_registry.register(prereq_q)
        quest_registry.register(dependent_q)

        available = self.char.quests.list_available()
        available_ids = {q.id for _, q in available}
        self.assertIn("prereq_quest", available_ids)
        self.assertNotIn("dependent_quest", available_ids)

    def test_prerequisite_met_shows_dependent(self):
        """Quest appears once prerequisites are completed."""
        prereq_q = QuestDefinition(
            id="prereq_quest2",
            name="Prerequisite 2",
            description="You must do this first.",
            quest_type="talk",
            target_key="Elder",
            target_count=1,
            rewards={"xp": 10},
            giver_npc_key="Test NPC",
        )
        dependent_q = QuestDefinition(
            id="dependent_quest2",
            name="Dependent 2",
            description="Requires prerequisite.",
            quest_type="kill",
            target_key="mob",
            target_count=2,
            rewards={"xp": 20},
            giver_npc_key="Test NPC",
            prereq_quests=["prereq_quest2"],
        )
        quest_registry.register(prereq_q)
        quest_registry.register(dependent_q)

        # Complete the prereq
        self.char.quests.accept("prereq_quest2")
        self.char.quests.report_talk("Elder")
        self.char.quests.complete("prereq_quest2")

        # Now dependent should be available
        available = self.char.quests.list_available()
        available_ids = {q.id for _, q in available}
        self.assertIn("dependent_quest2", available_ids)


# ---------------------------------------------------------------------------
# Command Tests
# ---------------------------------------------------------------------------

class TestQuestCommands(BaseEvenniaTest):
    """Tests for the quest command (CmdQuest)."""

    def setUp(self):
        super().setUp()
        self.char = create_object(Character, key="QuestCommander")
        self.char.attributes.add("level", 5)
        self.room = create_object(DefaultRoom, key="Cmd Room")
        self.char.location = self.room
        self.npc = create_object(DefaultObject, key="Test NPC")
        self.npc.location = self.room
        self.kill_q, self.fetch_q, self.talk_q = setup_test_quests()

    def tearDown(self):
        self.char.delete()
        self.npc.delete()
        self.room.delete()
        quest_registry.clear()
        super().tearDown()

    def test_quest_list_shows_available(self):
        """`quest list` shows available quests from NPCs."""
        from commands.quest import CmdQuest
        cmd = CmdQuest()
        cmd.caller = self.char
        cmd.cmdstring = "quest"
        cmd.args = "list"
        cmd.func()
        # Should not raise

    def test_quest_list_empty_room(self):
        """`quest list` in empty room shows no-quests message."""
        self.npc.location = None
        from commands.quest import CmdQuest
        cmd = CmdQuest()
        cmd.caller = self.char
        cmd.cmdstring = "quest"
        cmd.args = "list"
        cmd.func()
        # Should not raise

    def test_quest_accept_by_id(self):
        """`quest accept <id>` accepts a quest."""
        from commands.quest import CmdQuest
        cmd = CmdQuest()
        cmd.caller = self.char
        cmd.cmdstring = "quest"
        cmd.args = "accept test_kill_wolves"
        cmd.func()
        self.assertTrue(self.char.quests.is_active("test_kill_wolves"))

    def test_quest_accept_bad_id(self):
        """`quest accept <bad_id>` shows error."""
        from commands.quest import CmdQuest
        cmd = CmdQuest()
        cmd.caller = self.char
        cmd.cmdstring = "quest"
        cmd.args = "accept nonexistent"
        cmd.func()
        self.assertFalse(self.char.quests.is_active("nonexistent"))

    def test_quest_accept_no_args(self):
        """`quest accept` with no args shows usage."""
        from commands.quest import CmdQuest
        cmd = CmdQuest()
        cmd.caller = self.char
        cmd.cmdstring = "quest"
        cmd.args = "accept"
        cmd.func()
        # Should not raise

    def test_quest_status_shows_journal(self):
        """`quest status` shows active quests."""
        self.char.quests.accept("test_kill_wolves")
        from commands.quest import CmdQuest
        cmd = CmdQuest()
        cmd.caller = self.char
        cmd.cmdstring = "quest"
        cmd.args = "status"
        cmd.func()
        # Should not raise

    def test_quest_status_default(self):
        """`quest` with no args shows status (default subcommand)."""
        from commands.quest import CmdQuest
        cmd = CmdQuest()
        cmd.caller = self.char
        cmd.cmdstring = "quest"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_quest_complete_with_progress(self):
        """`quest complete <id>` turns in a completed quest."""
        self.char.quests.accept("test_kill_wolves")
        for _ in range(3):
            self.char.quests.report_kill("wolf")

        from commands.quest import CmdQuest
        cmd = CmdQuest()
        cmd.caller = self.char
        cmd.cmdstring = "quest"
        cmd.args = "complete test_kill_wolves"
        cmd.func()
        self.assertTrue(self.char.quests.has_completed("test_kill_wolves"))

    def test_quest_complete_no_args(self):
        """`quest complete` with no args shows usage."""
        from commands.quest import CmdQuest
        cmd = CmdQuest()
        cmd.caller = self.char
        cmd.cmdstring = "quest"
        cmd.args = "complete"
        cmd.func()
        # Should not raise

    def test_quest_abandon(self):
        """`quest abandon <id>` abandons a quest."""
        self.char.quests.accept("test_kill_wolves")
        from commands.quest import CmdQuest
        cmd = CmdQuest()
        cmd.caller = self.char
        cmd.cmdstring = "quest"
        cmd.args = "abandon test_kill_wolves"
        cmd.func()
        self.assertFalse(self.char.quests.is_active("test_kill_wolves"))

    def test_quest_completed_list(self):
        """`quest completed` shows finished quests."""
        self.char.quests.accept("test_talk_scout")
        self.char.quests.report_talk("Scout")
        self.char.quests.complete("test_talk_scout")

        from commands.quest import CmdQuest
        cmd = CmdQuest()
        cmd.caller = self.char
        cmd.cmdstring = "quest"
        cmd.args = "completed"
        cmd.func()
        # Should not raise

    def test_quest_completed_empty(self):
        """`quest completed` with no completions shows empty message."""
        from commands.quest import CmdQuest
        cmd = CmdQuest()
        cmd.caller = self.char
        cmd.cmdstring = "quest"
        cmd.args = "completed"
        cmd.func()
        # Should not raise

    def test_quest_bad_subcommand(self):
        """Invalid subcommand shows usage."""
        from commands.quest import CmdQuest
        cmd = CmdQuest()
        cmd.caller = self.char
        cmd.cmdstring = "quest"
        cmd.args = "invalid_cmd"
        cmd.func()
        # Should not raise

    def test_quest_aliases(self):
        """The `quests` alias works."""
        self.assertEqual(CmdQuest.aliases, ["quests"])


# ---------------------------------------------------------------------------
# Default Quests Registration
# ---------------------------------------------------------------------------

class TestDefaultQuests(BaseEvenniaTest):
    """Tests for register_default_quests()."""

    def setUp(self):
        super().setUp()
        quest_registry.clear()

    def tearDown(self):
        quest_registry.clear()
        super().tearDown()

    def test_register_default_quests(self):
        """Default quests are registered correctly."""
        register_default_quests()
        all_quests = quest_registry.all()
        self.assertEqual(len(all_quests), 6)

        # Check good quests exist
        good_ids = {"good_wolf_hunt", "good_herb_delivery", "good_scout_report"}
        evil_ids = {"evil_rat_extermination", "evil_skull_collection", "evil_dark_communion"}
        registered_ids = {q.id for q in all_quests}
        self.assertTrue(good_ids.issubset(registered_ids))
        self.assertTrue(evil_ids.issubset(registered_ids))

    def test_default_quests_idempotent(self):
        """Calling register_default_quests twice is safe."""
        register_default_quests()
        register_default_quests()
        self.assertEqual(len(quest_registry.all()), 6)

    def test_default_quests_have_types(self):
        """Each default quest type is represented."""
        register_default_quests()
        types = {q.quest_type for q in quest_registry.all()}
        self.assertIn("kill", types)
        self.assertIn("fetch", types)
        self.assertIn("talk", types)