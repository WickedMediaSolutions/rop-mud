"""
Unit tests for the Auto-Leveling & Skill Acquisition system.

Tests:
  - XP award triggers level-up at threshold
  - Level-up increments level, max HP, max MP, max MV, base stats
  - Spells are granted automatically when the required level is reached
  - Bright level-up announcement is sent to the player
  - Multi-level jumps from large XP awards
  - xp_to_level formula correctness (world.rules)

Run with:
    evennia test commands.tests.test_leveling
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia import create_object
from evennia.objects.objects import DefaultRoom, DefaultCharacter

from typeclasses.characters import Character

from world.rules import xp_to_level, stats_on_level_up, CLASSES
from world.spells import SPELLS, get_spells_for_level


# ---------------------------------------------------------------------------
# XP Formula Tests
# ---------------------------------------------------------------------------

class TestXpFormula(BaseEvenniaTest):
    """Test the xp_to_level formula."""

    def test_level_1_needs_1000(self):
        """Level 1 requires 1000 XP to reach level 2."""
        self.assertEqual(xp_to_level(1), 1000)

    def test_level_5_needs_5000(self):
        """Level 5 requires 5000 XP."""
        self.assertEqual(xp_to_level(5), 5000)

    def test_level_10_needs_10000(self):
        """Level 10 requires 10000 XP."""
        self.assertEqual(xp_to_level(10), 10000)

    def test_level_80_needs_80000(self):
        """Level 80 requires 80000 XP."""
        self.assertEqual(xp_to_level(80), 80000)

    def test_stats_on_level_up_returns_all_six(self):
        """stats_on_level_up returns +1 for all six core stats."""
        bonuses = stats_on_level_up()
        expected = {"str": 1, "dex": 1, "con": 1, "int": 1, "wis": 1, "cha": 1}
        self.assertEqual(bonuses, expected)


# ---------------------------------------------------------------------------
# Auto-Leveling Tests (Character)
# ---------------------------------------------------------------------------

class TestAutoLeveling(BaseEvenniaTest):
    """Test the auto-leveling system on the Character class."""

    def setUp(self):
        super().setUp()
        self.char = create_object(Character, key="TestHero")
        self.char.attributes.add("level", 1)
        self.char.attributes.add("xp", 0)
        self.char.attributes.add("xp_to_level", xp_to_level(1))
        self.char.attributes.add("max_hp", 100)
        self.char.attributes.add("hp", 100)
        self.char.attributes.add("max_mana", 50)
        self.char.attributes.add("mana", 50)
        self.char.attributes.add("max_mv", 100)
        self.char.attributes.add("mv", 100)
        self.char.attributes.add("class", "Warrior")
        self.char.attributes.add("race", "Human")
        self.char.attributes.add(
            "stats", {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        )
        self.char.attributes.add("learned_spells", [])
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_level_up_from_1000_xp(self):
        """Awarding 1000 XP to a level-1 character triggers level-up to level 2."""
        self.char.award_xp(1000)

        self.assertEqual(self.char.attributes.get("level"), 2)
        # 1000 XP spent on level 1, remaining 0
        self.assertEqual(self.char.attributes.get("xp"), 0)
        self.assertEqual(self.char.attributes.get("xp_to_level"), xp_to_level(2))

    def test_level_up_increases_max_hp(self):
        """Level-up increases max_hp by the class hp_per_level."""
        warrior_hp = CLASSES["Warrior"]["hp_per_level"]  # 15
        old_max_hp = self.char.attributes.get("max_hp")

        self.char.award_xp(1000)

        new_max_hp = self.char.attributes.get("max_hp")
        self.assertEqual(new_max_hp, old_max_hp + warrior_hp)

    def test_level_up_increases_max_mana(self):
        """Level-up increases max_mana by the class mana_per_level."""
        warrior_mana = CLASSES["Warrior"]["mana_per_level"]  # 2
        old_max_mana = self.char.attributes.get("max_mana")

        self.char.award_xp(1000)

        new_max_mana = self.char.attributes.get("max_mana")
        self.assertEqual(new_max_mana, old_max_mana + warrior_mana)

    def test_level_up_increases_max_mv(self):
        """Level-up increases max_mv by 5."""
        old_max_mv = self.char.attributes.get("max_mv")

        self.char.award_xp(1000)

        new_max_mv = self.char.attributes.get("max_mv")
        self.assertEqual(new_max_mv, old_max_mv + 5)

    def test_level_up_increases_base_stats(self):
        """Level-up increases all six core stats by +1."""
        old_stats = dict(self.char.attributes.get("stats"))

        self.char.award_xp(1000)

        new_stats = self.char.attributes.get("stats")
        for stat in ("str", "dex", "con", "int", "wis", "cha"):
            self.assertEqual(
                new_stats[stat],
                old_stats[stat] + 1,
                f"{stat.upper()} should increase by 1 on level-up",
            )

    def test_level_up_refills_hp_to_max(self):
        """Level-up refills HP to the new max."""
        # Wound the character first
        self.char.attributes.add("hp", 50)

        self.char.award_xp(1000)

        max_hp = self.char.attributes.get("max_hp")
        hp = self.char.attributes.get("hp")
        self.assertEqual(hp, max_hp, "HP should be refilled to max on level-up")

    def test_level_up_refills_mana_to_max(self):
        """Level-up refills mana to the new max."""
        self.char.attributes.add("mana", 10)

        self.char.award_xp(1000)

        max_mana = self.char.attributes.get("max_mana")
        mana = self.char.attributes.get("mana")
        self.assertEqual(mana, max_mana, "Mana should be refilled to max on level-up")

    def test_level_up_refills_mv_to_max(self):
        """Level-up refills MV to the new max."""
        self.char.attributes.add("mv", 30)

        self.char.award_xp(1000)

        max_mv = self.char.attributes.get("max_mv")
        mv = self.char.attributes.get("mv")
        self.assertEqual(mv, max_mv, "MV should be refilled to max on level-up")

    def test_multi_level_jump(self):
        """A huge XP award triggers multiple level-ups in sequence."""
        # Level 1 → 2 needs 1000, 2 → 3 needs 2000, 3 → 4 needs 3000 = 6000 total
        self.char.attributes.add("level", 1)
        self.char.attributes.add("xp_to_level", xp_to_level(1))

        self.char.award_xp(6000)

        self.assertEqual(self.char.attributes.get("level"), 4)
        self.assertEqual(self.char.attributes.get("xp"), 0)
        self.assertEqual(self.char.attributes.get("xp_to_level"), xp_to_level(4))

    def test_no_level_up_when_under_threshold(self):
        """Awarding XP below the threshold does not level up."""
        self.char.award_xp(500)

        self.assertEqual(self.char.attributes.get("level"), 1)
        self.assertEqual(self.char.attributes.get("xp"), 500)

    def test_accumulated_xp_triggers_level_up(self):
        """Multiple small XP awards accumulate to trigger level-up."""
        self.char.award_xp(300)
        self.assertEqual(self.char.attributes.get("level"), 1)

        self.char.award_xp(300)
        self.assertEqual(self.char.attributes.get("level"), 1)

        self.char.award_xp(400)
        # 300+300+400 = 1000, should level up
        self.assertEqual(self.char.attributes.get("level"), 2)
        self.assertEqual(self.char.attributes.get("xp"), 0)

    def test_level_up_announcement_sent(self):
        """A level-up announcement message is sent to the player."""
        delivered = []
        original_msg = self.char.msg

        def capture(text, **kwargs):
            delivered.append(str(text))
            original_msg(text, **kwargs)

        self.char.msg = capture

        try:
            self.char.award_xp(1000)
        finally:
            self.char.msg = original_msg

        announcement_found = any(
            "LEVEL UP" in msg and "Level 2" in msg for msg in delivered
        )
        self.assertTrue(
            announcement_found,
            "Level-up should send a bright announcement to the player",
        )

    def test_level_up_announcement_is_bright(self):
        """The level-up announcement uses bright / highlight color codes."""
        delivered = []
        original_msg = self.char.msg

        def capture(text, **kwargs):
            delivered.append(str(text))
            original_msg(text, **kwargs)

        self.char.msg = capture

        try:
            self.char.award_xp(1000)
        finally:
            self.char.msg = original_msg

        announcement = None
        for msg in delivered:
            if "LEVEL UP" in msg:
                announcement = msg
                break

        self.assertIsNotNone(announcement, "Level-up announcement should exist")
        self.assertIn("|y|h", announcement, "Announcement should use bright formatting")
        self.assertIn("|c|h", announcement, "Announcement should use bright cyan")


# ---------------------------------------------------------------------------
# Skill / Spell Acquisition Tests
# ---------------------------------------------------------------------------

class TestSkillAcquisition(BaseEvenniaTest):
    """Test automatic spell/skill granting on level-up."""

    def setUp(self):
        super().setUp()
        self.char = create_object(Character, key="TestMage")
        self.char.attributes.add("level", 1)
        self.char.attributes.add("xp", 0)
        self.char.attributes.add("xp_to_level", xp_to_level(1))
        self.char.attributes.add("max_hp", 100)
        self.char.attributes.add("hp", 100)
        self.char.attributes.add("max_mana", 50)
        self.char.attributes.add("mana", 50)
        self.char.attributes.add("max_mv", 100)
        self.char.attributes.add("mv", 100)
        self.char.attributes.add("class", "Mage")
        self.char.attributes.add("race", "High Elf")
        self.char.attributes.add(
            "stats", {"str": 7, "dex": 12, "con": 8, "int": 14, "wis": 12, "cha": 11}
        )
        self.char.attributes.add("learned_spells", [])
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_level_1_spells_granted_at_start(self):
        """Spells that require level 1 should be learnable (test _grant_spells_for_level)."""
        new = self.char._grant_spells_for_level(1)
        self.assertIn("Sparks", new)
        self.assertIn("Minor Heal", new)

    def test_level_1_spells_stored_in_learned(self):
        """After granting level 1 spells, learned_spells contains them."""
        self.char._grant_spells_for_level(1)
        learned = self.char.attributes.get("learned_spells", [])
        self.assertIn("Sparks", learned)
        self.assertIn("Minor Heal", learned)

    def test_level_5_spells_granted(self):
        """At level 5, Stone Skin should be granted."""
        new = self.char._grant_spells_for_level(5)
        self.assertIn("Stone Skin", new)

    def test_level_20_spells_granted(self):
        """At level 20, Fireball should be granted."""
        new = self.char._grant_spells_for_level(20)
        self.assertIn("Fireball", new)

    def test_no_duplicate_spell_granting(self):
        """Calling _grant_spells_for_level twice does not duplicate entries."""
        self.char._grant_spells_for_level(1)
        self.char._grant_spells_for_level(1)

        learned = self.char.attributes.get("learned_spells", [])
        sparks_count = sum(1 for s in learned if s == "Sparks")
        self.assertEqual(sparks_count, 1, "Spell should only appear once in learned list")

    def test_no_spells_at_empty_level(self):
        """A level with no spell definitions returns empty list."""
        new = self.char._grant_spells_for_level(2)
        self.assertEqual(new, [], "Level 2 has no spells defined")

    def test_spells_granted_consecutive_levels(self):
        """Verifying spells are granted at multiple consecutive levels."""
        all_granted = []
        for lvl in range(1, 6):
            all_granted.extend(self.char._grant_spells_for_level(lvl))

        self.assertIn("Sparks", all_granted)          # level 1
        self.assertIn("Minor Heal", all_granted)      # level 1
        self.assertIn("Arcane Dart", all_granted)     # level 3
        self.assertIn("Stone Skin", all_granted)       # level 5

    def test_level_80_spell_meteor_swarm(self):
        """At level 80, Meteor Swarm should be granted."""
        new = self.char._grant_spells_for_level(80)
        self.assertIn("Meteor Swarm", new)

    def test_all_level_1_spells_count(self):
        """There are exactly 2 spells at level 1."""
        level_1 = [s for s in SPELLS.values() if s["level"] == 1]
        self.assertEqual(len(level_1), 2)


# ---------------------------------------------------------------------------
# Level-up with Different Classes
# ---------------------------------------------------------------------------

class TestClassSpecificLevelUp(BaseEvenniaTest):
    """Test that different classes get different HP/Mana on level-up."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="Test Room")

    def tearDown(self):
        self.room.delete()
        super().tearDown()

    def _create_char(self, class_name):
        char = create_object(Character, key=f"Test{class_name}")
        char.attributes.add("level", 1)
        char.attributes.add("xp", 0)
        char.attributes.add("xp_to_level", xp_to_level(1))
        char.attributes.add("max_hp", 100)
        char.attributes.add("hp", 100)
        char.attributes.add("max_mana", 50)
        char.attributes.add("mana", 50)
        char.attributes.add("max_mv", 100)
        char.attributes.add("mv", 100)
        char.attributes.add("class", class_name)
        char.attributes.add("race", "Human")
        char.attributes.add(
            "stats", {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        )
        char.attributes.add("learned_spells", [])
        char.location = self.room
        return char

    def test_mage_gets_6_hp_16_mana(self):
        """Mage gets 6 HP and 16 mana per level."""
        char = self._create_char("Mage")
        try:
            char.award_xp(1000)
            # HP went from 100 → 106
            self.assertEqual(char.attributes.get("max_hp"), 106)
            # Mana went from 50 → 66
            self.assertEqual(char.attributes.get("max_mana"), 66)
        finally:
            char.delete()

    def test_warrior_gets_15_hp_2_mana(self):
        """Warrior gets 15 HP and 2 mana per level."""
        char = self._create_char("Warrior")
        try:
            char.award_xp(1000)
            self.assertEqual(char.attributes.get("max_hp"), 115)
            self.assertEqual(char.attributes.get("max_mana"), 52)
        finally:
            char.delete()

    def test_cleric_gets_10_hp_12_mana(self):
        """Cleric gets 10 HP and 12 mana per level."""
        char = self._create_char("Cleric")
        try:
            char.award_xp(1000)
            self.assertEqual(char.attributes.get("max_hp"), 110)
            self.assertEqual(char.attributes.get("max_mana"), 62)
        finally:
            char.delete()

    def test_necromancer_gets_7_hp_15_mana(self):
        """Necromancer gets 7 HP and 15 mana per level."""
        char = self._create_char("Necromancer")
        try:
            char.award_xp(1000)
            self.assertEqual(char.attributes.get("max_hp"), 107)
            self.assertEqual(char.attributes.get("max_mana"), 65)
        finally:
            char.delete()