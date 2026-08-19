"""
Unit tests for Phase 9 Quest System enhancements:
  - Branching NPC dialogue (world/quest_dialogue.py)
  - Quest chains / story arcs
  - Daily / repeatable quests
  - Level-scaled rewards
  - Group quest sharing
  - Talk command (commands/talk.py)

Run with:
    evennia test commands.tests.test_phase9_quests
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultRoom, DefaultObject
from evennia import create_object

from typeclasses.characters import Character
from world.quests import (
    QuestDefinition,
    QuestRegistry,
    ActiveQuest,
    QuestHandler,
    quest_registry,
)
from world.quest_dialogue import (
    DialogueNode,
    DialogueTree,
    DialogueRegistry,
    DialogueSession,
    dialogue_registry,
    register_default_dialogues,
)


def setup_phase9_quests():
    """Register a clean set of Phase 9 quests."""
    quest_registry.clear()

    # Quest chain
    quest_registry.register(QuestDefinition(
        id="chain_part1",
        name="Chain Part 1",
        description="First part of the saga.",
        quest_type="kill",
        target_key="wolf",
        target_count=2,
        rewards={"xp": 50, "gold": 25},
        giver_npc_key="Test NPC",
        chain_id="wolf_saga",
        chain_order=0,
    ))
    quest_registry.register(QuestDefinition(
        id="chain_part2",
        name="Chain Part 2",
        description="Second part of the saga.",
        quest_type="kill",
        target_key="bear",
        target_count=3,
        rewards={"xp": 100, "gold": 50},
        giver_npc_key="Test NPC",
        chain_id="wolf_saga",
        chain_order=1,
        prereq_quests=["chain_part1"],
    ))

    # Daily quest
    quest_registry.register(QuestDefinition(
        id="daily_rats",
        name="Daily Rat Hunt",
        description="Kill 2 rats (daily).",
        quest_type="kill",
        target_key="rat",
        target_count=2,
        rewards={"xp": 40, "gold": 20},
        giver_npc_key="Test NPC",
        daily=True,
        repeatable=True,
    ))

    # Level-scaled quest
    quest_registry.register(QuestDefinition(
        id="scaled_quest",
        name="Scaled Quest",
        description="Rewards scale with level.",
        quest_type="kill",
        target_key="orc",
        target_count=5,
        rewards={"xp": 100, "gold": 50},
        giver_npc_key="Test NPC",
        scale_rewards=True,
    ))


class TestQuestDefinitionNewFields(BaseEvenniaTest):
    """Test the new QuestDefinition fields added in Phase 9."""

    def setUp(self):
        super().setUp()
        quest_registry.clear()

    def tearDown(self):
        quest_registry.clear()
        super().tearDown()

    def test_new_fields_default(self):
        """Default values for new fields are safe."""
        q = QuestDefinition(
            id="test", name="Test", description="d",
            quest_type="kill", target_key="x",
        )
        self.assertFalse(q.daily)
        self.assertIsNone(q.chain_id)
        self.assertEqual(q.chain_order, 0)
        self.assertFalse(q.scale_rewards)

    def test_new_fields_custom(self):
        """Custom values for new fields are preserved."""
        q = QuestDefinition(
            id="test", name="Test", description="d",
            quest_type="kill", target_key="x",
            daily=True, chain_id="my_chain", chain_order=2,
            scale_rewards=True,
        )
        self.assertTrue(q.daily)
        self.assertEqual(q.chain_id, "my_chain")
        self.assertEqual(q.chain_order, 2)
        self.assertTrue(q.scale_rewards)

    def test_get_scaled_rewards_enabled(self):
        """Rewards scale when scale_rewards=True."""
        q = QuestDefinition(
            id="test", name="Test", description="d",
            quest_type="kill", target_key="x",
            rewards={"xp": 100, "gold": 50},
            level_required=1,
            scale_rewards=True,
        )
        # Level 5 => diff 4 => xp * 1.6, gold * 1.4
        scaled = q.get_scaled_rewards(5)
        self.assertEqual(scaled["xp"], int(100 * 1.6))
        self.assertEqual(scaled["gold"], int(50 * 1.4))

    def test_get_scaled_rewards_disabled(self):
        """Rewards unchanged when scale_rewards=False."""
        q = QuestDefinition(
            id="test", name="Test", description="d",
            quest_type="kill", target_key="x",
            rewards={"xp": 100, "gold": 50},
            scale_rewards=False,
        )
        scaled = q.get_scaled_rewards(10)
        self.assertEqual(scaled["xp"], 100)
        self.assertEqual(scaled["gold"], 50)

    def test_get_scaled_rewards_no_negative(self):
        """Scaling never reduces below base (level below required clamps to 0)."""
        q = QuestDefinition(
            id="test", name="Test", description="d",
            quest_type="kill", target_key="x",
            rewards={"xp": 100, "gold": 50},
            level_required=10,
            scale_rewards=True,
        )
        scaled = q.get_scaled_rewards(5)
        self.assertEqual(scaled["xp"], 100)
        self.assertEqual(scaled["gold"], 50)


class TestQuestRegistryChainAndDaily(BaseEvenniaTest):
    """Test registry methods for chains and daily quests."""

    def setUp(self):
        super().setUp()
        quest_registry.clear()

    def tearDown(self):
        quest_registry.clear()
        super().tearDown()

    def test_get_by_chain_sorted(self):
        """get_by_chain returns quests sorted by chain_order."""
        q2 = QuestDefinition(
            id="c2", name="C2", description="d",
            quest_type="kill", target_key="x", chain_id="c", chain_order=2,
        )
        q0 = QuestDefinition(
            id="c0", name="C0", description="d",
            quest_type="kill", target_key="x", chain_id="c", chain_order=0,
        )
        q1 = QuestDefinition(
            id="c1", name="C1", description="d",
            quest_type="kill", target_key="x", chain_id="c", chain_order=1,
        )
        quest_registry.register(q2)
        quest_registry.register(q0)
        quest_registry.register(q1)

        chain = quest_registry.get_by_chain("c")
        self.assertEqual([q.id for q in chain], ["c0", "c1", "c2"])

    def test_get_by_chain_empty(self):
        """Empty chain returns empty list."""
        self.assertEqual(quest_registry.get_by_chain("nonexistent"), [])

    def test_get_daily_quests(self):
        """get_daily_quests returns only daily quests."""
        quest_registry.register(QuestDefinition(
            id="d1", name="D1", description="d",
            quest_type="kill", target_key="x", daily=True,
        ))
        quest_registry.register(QuestDefinition(
            id="d2", name="D2", description="d",
            quest_type="kill", target_key="x", daily=False,
        ))
        daily = quest_registry.get_daily_quests()
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0].id, "d1")


class TestQuestHandlerChains(BaseEvenniaTest):
    """Test quest chain progression via QuestHandler."""

    def setUp(self):
        super().setUp()
        self.char = create_object(Character, key="ChainHero")
        self.char.attributes.add("level", 5)
        self.room = create_object(DefaultRoom, key="Chain Room")
        self.char.location = self.room
        self.npc = create_object(DefaultObject, key="Test NPC")
        self.npc.location = self.room
        setup_phase9_quests()

    def tearDown(self):
        self.char.delete()
        self.npc.delete()
        self.room.delete()
        quest_registry.clear()
        super().tearDown()

    def test_chain_progress_empty(self):
        """Chain progress starts at 0."""
        c, t, n = self.char.quests.get_chain_progress("wolf_saga")
        self.assertEqual(c, 0)
        self.assertEqual(t, 2)
        self.assertEqual(n, "chain_part1")

    def test_chain_progress_after_first(self):
        """Chain progress updates after completing first quest."""
        self.char.quests.accept("chain_part1")
        self.char.quests.report_kill("wolf")
        self.char.quests.report_kill("wolf")
        self.char.quests.complete("chain_part1")

        c, t, n = self.char.quests.get_chain_progress("wolf_saga")
        self.assertEqual(c, 1)
        self.assertEqual(t, 2)
        self.assertEqual(n, "chain_part2")

    def test_chain_progress_complete(self):
        """Chain progress is full after completing all quests."""
        # Part 1
        self.char.quests.accept("chain_part1")
        self.char.quests.report_kill("wolf")
        self.char.quests.report_kill("wolf")
        self.char.quests.complete("chain_part1")

        # Part 2
        self.char.quests.accept("chain_part2")
        self.char.quests.report_kill("bear")
        self.char.quests.report_kill("bear")
        self.char.quests.report_kill("bear")
        self.char.quests.complete("chain_part2")

        c, t, n = self.char.quests.get_chain_progress("wolf_saga")
        self.assertEqual(c, 2)
        self.assertEqual(t, 2)
        self.assertIsNone(n)

    def test_chain_part2_blocked_until_part1(self):
        """Part 2 is not available until Part 1 is completed."""
        available = self.char.quests.list_available()
        ids = {q.id for _, q in available}
        self.assertIn("chain_part1", ids)
        self.assertNotIn("chain_part2", ids)

    def test_chain_part2_available_after_part1(self):
        """Part 2 becomes available after Part 1 is completed."""
        self.char.quests.accept("chain_part1")
        self.char.quests.report_kill("wolf")
        self.char.quests.report_kill("wolf")
        self.char.quests.complete("chain_part1")

        available = self.char.quests.list_available()
        ids = {q.id for _, q in available}
        self.assertIn("chain_part2", ids)


class TestQuestHandlerDaily(BaseEvenniaTest):
    """Test daily quest reset mechanics."""

    def setUp(self):
        super().setUp()
        self.char = create_object(Character, key="DailyHero")
        self.char.attributes.add("level", 5)
        self.room = create_object(DefaultRoom, key="Daily Room")
        self.char.location = self.room
        self.npc = create_object(DefaultObject, key="Test NPC")
        self.npc.location = self.room
        setup_phase9_quests()

    def tearDown(self):
        self.char.delete()
        self.npc.delete()
        self.room.delete()
        quest_registry.clear()
        super().tearDown()

    def test_daily_quest_completes_and_reappears(self):
        """A daily (repeatable) quest reappears after completion."""
        self.char.quests.accept("daily_rats")
        self.char.quests.report_kill("rat")
        self.char.quests.report_kill("rat")
        self.char.quests.complete("daily_rats")

        # Since daily=repeatable, it should be available again
        available = self.char.quests.list_available()
        ids = {q.id for _, q in available}
        self.assertIn("daily_rats", ids)

    def test_daily_reset_initial_state(self):
        """No daily resets recorded initially."""
        resets = self.char.quests._load_daily_resets()
        self.assertEqual(resets, {})

    def test_daily_reset_not_triggered_early(self):
        """Daily reset does not trigger within 24 hours."""
        import time
        resets = self.char.quests._load_daily_resets()
        resets["daily_rats"] = time.time()  # just now
        self.char.quests._save_daily_resets(resets)

        # Complete the quest first
        self.char.quests.accept("daily_rats")
        self.char.quests.report_kill("rat")
        self.char.quests.report_kill("rat")
        self.char.quests.complete("daily_rats")

        # Reset should NOT trigger since <24h
        result = self.char.quests._check_daily_reset("daily_rats")
        self.assertFalse(result)
        self.assertTrue(self.char.quests.has_completed("daily_rats"))

    def test_daily_reset_triggers_after_24h(self):
        """Daily reset triggers after 24 hours."""
        import time
        resets = self.char.quests._load_daily_resets()
        resets["daily_rats"] = time.time() - 90000  # 25 hours ago
        self.char.quests._save_daily_resets(resets)

        # Complete the quest first
        self.char.quests.accept("daily_rats")
        self.char.quests.report_kill("rat")
        self.char.quests.report_kill("rat")
        self.char.quests.complete("daily_rats")

        # Reset should trigger since >24h
        result = self.char.quests._check_daily_reset("daily_rats")
        self.assertTrue(result)
        self.assertFalse(self.char.quests.has_completed("daily_rats"))


class TestQuestHandlerScaledRewards(BaseEvenniaTest):
    """Test level-scaled reward grants."""

    def setUp(self):
        super().setUp()
        self.char = create_object(Character, key="ScaleHero")
        self.char.attributes.add("level", 5)
        self.room = create_object(DefaultRoom, key="Scale Room")
        self.char.location = self.room
        self.npc = create_object(DefaultObject, key="Test NPC")
        self.npc.location = self.room
        setup_phase9_quests()

    def tearDown(self):
        self.char.delete()
        self.npc.delete()
        self.room.delete()
        quest_registry.clear()
        super().tearDown()

    def test_scaled_rewards_applied(self):
        """Scaled quest grants scaled XP/gold at higher level."""
        self.char.quests.accept("scaled_quest")
        for _ in range(5):
            self.char.quests.report_kill("orc")
        self.char.quests.complete("scaled_quest")

        # Level 5, base level 1 => diff 4
        expected_xp = int(100 * 1.6)
        expected_gold = int(50 * 1.4)
        self.assertEqual(self.char.attributes.get("xp"), expected_xp)
        self.assertEqual(self.char.attributes.get("gold"), expected_gold)


class TestDialogueSystem(BaseEvenniaTest):
    """Test branching dialogue system."""

    def setUp(self):
        super().setUp()
        dialogue_registry.clear()

    def tearDown(self):
        dialogue_registry.clear()
        super().tearDown()

    def test_dialogue_node_basic(self):
        """DialogueNode stores text and choices."""
        node = DialogueNode(
            id="start", text="Hello!", choices=[("A", "next"), ("B", None)],
        )
        self.assertEqual(node.id, "start")
        self.assertEqual(node.text, "Hello!")
        self.assertEqual(len(node.choices), 2)

    def test_dialogue_node_conditions(self):
        """DialogueNode conditions are evaluated."""
        from evennia import create_object
        char = create_object(Character, key="DLHero")
        char.attributes.add("level", 1)

        node = DialogueNode(id="n", text="x", conditions={"min_level": 5})
        self.assertFalse(node.evaluate_conditions(char))

        char.attributes.add("level", 10)
        self.assertTrue(node.evaluate_conditions(char))

        char.delete()

    def test_dialogue_node_effects_flags(self):
        """DialogueNode effects set flags."""
        from evennia import create_object
        char = create_object(Character, key="DLEff")
        char.attributes.add("level", 1)

        node = DialogueNode(id="n", text="x", effects={"set_flag": "met"})
        node.apply_effects(char)
        flags = char.attributes.get("dialogue_flags", default=set())
        self.assertIn("met", flags)

        # Clear flag
        node2 = DialogueNode(id="n2", text="x", effects={"clear_flag": "met"})
        node2.apply_effects(char)
        flags = char.attributes.get("dialogue_flags", default=set())
        self.assertNotIn("met", flags)

        char.delete()

    def test_dialogue_tree_choices(self):
        """DialogueTree presents available choices."""
        tree = DialogueTree(id="t", npc_key="NPC", start_node="start")
        tree.add_node(DialogueNode(
            id="start", text="Welcome", choices=[("Go", "next"), ("Bye", None)],
        ))
        tree.add_node(DialogueNode(id="next", text="Next node", choices=[("End", None)]))

        from evennia import create_object
        char = create_object(Character, key="DLTree")
        char.attributes.add("level", 1)

        start = tree.get_start_node(char)
        self.assertEqual(start.id, "start")

        choices = tree.get_available_choices(start, char)
        self.assertEqual(len(choices), 2)
        self.assertEqual(choices[0][1].id, "next")
        self.assertIsNone(choices[1][1])

        char.delete()

    def test_dialogue_tree_conditional_choice_hidden(self):
        """Conditional choices are hidden when conditions unmet."""
        tree = DialogueTree(id="t", npc_key="NPC", start_node="start")
        tree.add_node(DialogueNode(
            id="start", text="Welcome",
            choices=[("Public", "pub"), ("Secret", "secret")],
        ))
        tree.add_node(DialogueNode(id="pub", text="Public path", choices=[("End", None)]))
        tree.add_node(DialogueNode(
            id="secret", text="Secret path", choices=[("End", None)],
            conditions={"min_level": 10},
        ))

        from evennia import create_object
        char = create_object(Character, key="DLCond")
        char.attributes.add("level", 1)

        start = tree.get_start_node(char)
        choices = tree.get_available_choices(start, char)
        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0][1].id, "pub")

        char.delete()

    def test_dialogue_registry(self):
        """DialogueRegistry registers and retrieves trees."""
        tree = DialogueTree(id="t", npc_key="NPC", start_node="start")
        tree.add_node(DialogueNode(id="start", text="Hi", choices=[("Bye", None)]))
        dialogue_registry.register(tree)

        self.assertEqual(dialogue_registry.get("t"), tree)
        self.assertEqual(dialogue_registry.get_by_npc("NPC"), [tree])
        self.assertEqual(dialogue_registry.get_by_npc("Other"), [])
        self.assertEqual(len(dialogue_registry.all()), 1)

        dialogue_registry.clear()
        self.assertEqual(len(dialogue_registry.all()), 0)

    def test_dialogue_registry_type_check(self):
        """Registering non-DialogueTree raises TypeError."""
        with self.assertRaises(TypeError):
            dialogue_registry.register("not a tree")

    def test_dialogue_session_choice(self):
        """DialogueSession choose() transitions between nodes."""
        tree = DialogueTree(id="t", npc_key="NPC", start_node="start")
        tree.add_node(DialogueNode(
            id="start", text="Welcome", choices=[("Go", "next"), ("Bye", None)],
        ))
        tree.add_node(DialogueNode(id="next", text="Next node", choices=[("End", None)]))

        from evennia import create_object
        char = create_object(Character, key="DLSession")
        char.attributes.add("level", 1)

        session = DialogueSession(char, tree)
        self.assertTrue(session.is_active)
        self.assertEqual(session.current_node.id, "start")

        # Choose "Go"
        success, _ = session.choose(1)
        self.assertTrue(success)
        self.assertEqual(session.current_node.id, "next")
        self.assertTrue(session.is_active)

        # Choose "End" (None terminates)
        success, _ = session.choose(1)
        self.assertTrue(success)
        self.assertFalse(session.is_active)

        char.delete()

    def test_dialogue_session_invalid_choice(self):
        """Invalid choice index returns error."""
        tree = DialogueTree(id="t", npc_key="NPC", start_node="start")
        tree.add_node(DialogueNode(id="start", text="Hi", choices=[("Bye", None)]))

        from evennia import create_object
        char = create_object(Character, key="DLInv")
        char.attributes.add("level", 1)

        session = DialogueSession(char, tree)
        success, msg = session.choose(5)
        self.assertFalse(success)
        self.assertIn("Invalid choice", msg)

        success, msg = session.choose(0)
        self.assertFalse(success)

        char.delete()


class TestDefaultDialogues(BaseEvenniaTest):
    """Test default dialogue registration."""

    def setUp(self):
        super().setUp()
        dialogue_registry.clear()

    def tearDown(self):
        dialogue_registry.clear()
        super().tearDown()

    def test_register_default_dialogues(self):
        """Default dialogues register correctly."""
        register_default_dialogues()
        trees = dialogue_registry.all()
        self.assertEqual(len(trees), 3)
        ids = {t.id for t in trees}
        self.assertIn("good_quartermaster", ids)
        self.assertIn("evil_quartermaster", ids)
        self.assertIn("town_guard", ids)

    def test_register_default_dialogues_idempotent(self):
        """Registering twice is safe."""
        register_default_dialogues()
        register_default_dialogues()
        self.assertEqual(len(dialogue_registry.all()), 3)


class TestTalkCommand(BaseEvenniaTest):
    """Test the talk command."""

    def setUp(self):
        super().setUp()
        dialogue_registry.clear()
        self.char = create_object(Character, key="TalkHero")
        self.char.attributes.add("level", 5)
        self.room = create_object(DefaultRoom, key="Talk Room")
        self.char.location = self.room

        # Register a dialogue tree for an NPC
        self.npc = create_object(DefaultObject, key="Guard")
        self.npc.location = self.room

        tree = DialogueTree(id="guard", npc_key="Guard", start_node="start")
        tree.add_node(DialogueNode(
            id="start", text="Halt!", choices=[("Hi", "next"), ("Bye", None)],
        ))
        tree.add_node(DialogueNode(id="next", text="Hello there.", choices=[("Bye", None)]))
        dialogue_registry.register(tree)

    def tearDown(self):
        self.char.delete()
        self.npc.delete()
        self.room.delete()
        dialogue_registry.clear()
        super().tearDown()

    def test_talk_start_conversation(self):
        """talk <npc> starts a conversation."""
        from commands.talk import CmdTalk
        cmd = CmdTalk()
        cmd.caller = self.char
        cmd.cmdstring = "talk"
        cmd.args = "Guard"
        cmd.func()

        session = self.char.ndb.dialogue_session if hasattr(self.char, 'ndb') else None
        self.assertIsNotNone(session)
        self.assertTrue(session.is_active)

    def test_talk_start_no_npc(self):
        """talk with no matching NPC shows error."""
        from commands.talk import CmdTalk
        cmd = CmdTalk()
        cmd.caller = self.char
        cmd.cmdstring = "talk"
        cmd.args = "Nobody"
        cmd.func()

        session = self.char.ndb.dialogue_session if hasattr(self.char, 'ndb') else None
        self.assertIsNone(session)

    def test_talk_choose_option(self):
        """talk <number> chooses an option."""
        from commands.talk import CmdTalk
        # Start conversation
        cmd = CmdTalk()
        cmd.caller = self.char
        cmd.cmdstring = "talk"
        cmd.args = "Guard"
        cmd.func()

        # Choose option 1
        cmd2 = CmdTalk()
        cmd2.caller = self.char
        cmd2.cmdstring = "talk"
        cmd2.args = "1"
        cmd2.func()

        session = self.char.ndb.dialogue_session if hasattr(self.char, 'ndb') else None
        self.assertIsNotNone(session)
        self.assertTrue(session.is_active)
        self.assertEqual(session.current_node.id, "next")

    def test_talk_end_conversation(self):
        """talk end ends the conversation."""
        from commands.talk import CmdTalk
        cmd = CmdTalk()
        cmd.caller = self.char
        cmd.cmdstring = "talk"
        cmd.args = "Guard"
        cmd.func()

        cmd2 = CmdTalk()
        cmd2.caller = self.char
        cmd2.cmdstring = "talk"
        cmd2.args = "end"
        cmd2.func()

        session = self.char.ndb.dialogue_session if hasattr(self.char, 'ndb') else None
        self.assertIsNone(session)

    def test_talk_no_active_choice(self):
        """talk <number> with no active session shows error (no crash)."""
        from commands.talk import CmdTalk
        cmd = CmdTalk()
        cmd.caller = self.char
        cmd.cmdstring = "talk"
        cmd.args = "1"
        cmd.func()
        # Should not raise

    def test_talk_status_no_session(self):
        """talk with no args and no session shows usage."""
        from commands.talk import CmdTalk
        cmd = CmdTalk()
        cmd.caller = self.char
        cmd.cmdstring = "talk"
        cmd.args = ""
        cmd.func()
        # Should not raise


class TestGroupQuestSharing(BaseEvenniaTest):
    """Test group quest progress sharing."""

    def setUp(self):
        super().setUp()
        quest_registry.clear()

        self.room = create_object(DefaultRoom, key="Share Room")

        self.leader = create_object(Character, key="Leader")
        self.leader.attributes.add("level", 5)
        self.leader.location = self.room

        self.member = create_object(Character, key="Member")
        self.member.attributes.add("level", 5)
        self.member.location = self.room

        # Put both in the same group
        group_id = "group_test_share"
        self.leader.attributes.add("group_id", group_id)
        self.leader.attributes.add("group_leader", True)
        self.member.attributes.add("group_id", group_id)
        self.member.attributes.add("group_leader", False)

        # Register a kill quest and have both accept it via NPC
        self.npc = create_object(DefaultObject, key="Test NPC")
        self.npc.location = self.room

        quest_registry.register(QuestDefinition(
            id="group_kill",
            name="Group Kill",
            description="Kill 3 wolves together.",
            quest_type="kill",
            target_key="wolf",
            target_count=3,
            rewards={"xp": 100, "gold": 50},
            giver_npc_key="Test NPC",
        ))

        # Both accept the quest
        self.leader.quests.accept("group_kill")
        self.member.quests.accept("group_kill")

    def tearDown(self):
        self.leader.delete()
        self.member.delete()
        self.npc.delete()
        self.room.delete()
        quest_registry.clear()
        super().tearDown()

    def test_share_progress_to_member(self):
        """Leader's kill shares progress with group member."""
        self.leader.quests.report_kill("wolf")

        _, member_aq = self.member.quests._find_active("group_kill")
        self.assertEqual(member_aq.progress, 1)

    def test_share_progress_not_double_count_leader(self):
        """Leader's own progress is exactly 1 after a single kill."""
        self.leader.quests.report_kill("wolf")
        _, leader_aq = self.leader.quests._find_active("group_kill")
        self.assertEqual(leader_aq.progress, 1)

    def test_no_share_when_not_grouped(self):
        """No sharing when characters are not grouped."""
        self.member.attributes.add("group_id", None)

        self.leader.quests.report_kill("wolf")
        _, member_aq = self.member.quests._find_active("group_kill")
        self.assertEqual(member_aq.progress, 0)

    def test_share_progress_completes_member(self):
        """Member completes when leader completes shared objective."""
        self.leader.quests.report_kill("wolf")
        self.leader.quests.report_kill("wolf")
        self.leader.quests.report_kill("wolf")

        _, member_aq = self.member.quests._find_active("group_kill")
        self.assertTrue(member_aq.is_complete)
        self.assertEqual(member_aq.progress, 3)

    def test_share_progress_standalone(self):
        """share_progress method directly shares progress."""
        self.leader.quests.share_progress("group_kill", "wolf", 1)
        _, member_aq = self.member.quests._find_active("group_kill")
        self.assertEqual(member_aq.progress, 1)

    def test_share_progress_no_group_returns_zero(self):
        """share_progress returns 0 when not in a group."""
        self.leader.attributes.add("group_id", None)
        result = self.leader.quests.share_progress("group_kill", "wolf", 1)
        self.assertEqual(result, 0)