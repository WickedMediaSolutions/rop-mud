"""
Unit tests for general commands: rest, meditate, consider, recall.

Run with:
    evennia test commands.tests.test_general
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultRoom, DefaultCharacter
from evennia import create_object


class TestRestCommand(BaseEvenniaTest):
    """Test the 'rest' command."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="TestChar")
        self.char1.attributes.add("hp", 80)
        self.char1.attributes.add("max_hp", 100)
        self.char1.attributes.add("mana", 50)
        self.char1.attributes.add("max_mana", 50)
        self.char1.attributes.add("mv", 60)
        self.char1.attributes.add("max_mv", 100)
        self.char1.attributes.add("level", 5)
        self.char1.attributes.add("race", "Human")
        self.char1.attributes.add("class", "Warrior")
        self.char1.attributes.add("alignment", "Good")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()
        super().tearDown()

    def test_rest_starts_resting(self):
        """Starting rest should set is_resting flag."""
        self.assertFalse(self.char1.attributes.get("is_resting", default=False))

        from commands.general import CmdRest
        cmd = CmdRest()
        cmd.caller = self.char1
        cmd.cmdstring = "rest"
        cmd.args = ""
        cmd.func()

        self.assertTrue(self.char1.attributes.get("is_resting", default=False))

    def test_rest_toggle_stops_resting(self):
        """Using rest while already resting should stop resting."""
        self.char1.attributes.add("is_resting", True)

        from commands.general import CmdRest
        cmd = CmdRest()
        cmd.caller = self.char1
        cmd.cmdstring = "rest"
        cmd.args = ""
        cmd.func()

        self.assertFalse(self.char1.attributes.get("is_resting", default=False))

    def test_rest_stops_meditation(self):
        """Starting rest while meditating should stop meditation."""
        self.char1.attributes.add("is_meditating", True)

        from commands.general import CmdRest
        cmd = CmdRest()
        cmd.caller = self.char1
        cmd.cmdstring = "rest"
        cmd.args = ""
        cmd.func()

        self.assertTrue(self.char1.attributes.get("is_resting", default=False))
        self.assertFalse(self.char1.attributes.get("is_meditating", default=False))


class TestMeditateCommand(BaseEvenniaTest):
    """Test the 'meditate' command."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="TestChar")
        self.char1.attributes.add("hp", 80)
        self.char1.attributes.add("max_hp", 100)
        self.char1.attributes.add("mana", 30)
        self.char1.attributes.add("max_mana", 50)
        self.char1.attributes.add("mv", 100)
        self.char1.attributes.add("max_mv", 100)
        self.char1.attributes.add("level", 5)
        self.char1.attributes.add("race", "High Elf")
        self.char1.attributes.add("class", "Mage")
        self.char1.attributes.add("alignment", "Good")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()
        super().tearDown()

    def test_meditate_starts_meditating(self):
        """A magic user should be able to start meditating."""
        self.assertFalse(self.char1.attributes.get("is_meditating", default=False))

        from commands.general import CmdMeditate
        cmd = CmdMeditate()
        cmd.caller = self.char1
        cmd.cmdstring = "meditate"
        cmd.args = ""
        cmd.func()

        self.assertTrue(self.char1.attributes.get("is_meditating", default=False))

    def test_meditate_toggle_stops_meditating(self):
        """Using meditate while already meditating should stop."""
        self.char1.attributes.add("is_meditating", True)

        from commands.general import CmdMeditate
        cmd = CmdMeditate()
        cmd.caller = self.char1
        cmd.cmdstring = "meditate"
        cmd.args = ""
        cmd.func()

        self.assertFalse(self.char1.attributes.get("is_meditating", default=False))

    def test_non_magic_class_cannot_meditate(self):
        """A Warrior should not be able to meditate."""
        self.char1.attributes.add("class", "Warrior")

        from commands.general import CmdMeditate
        cmd = CmdMeditate()
        cmd.caller = self.char1
        cmd.cmdstring = "meditate"
        cmd.args = ""
        cmd.func()

        self.assertFalse(self.char1.attributes.get("is_meditating", default=False))

    def test_meditate_stops_resting(self):
        """Starting meditation while resting should stop resting."""
        self.char1.attributes.add("is_resting", True)

        from commands.general import CmdMeditate
        cmd = CmdMeditate()
        cmd.caller = self.char1
        cmd.cmdstring = "meditate"
        cmd.args = ""
        cmd.func()

        self.assertTrue(self.char1.attributes.get("is_meditating", default=False))
        self.assertFalse(self.char1.attributes.get("is_resting", default=False))

    def test_all_magic_classes_can_meditate(self):
        """All six magic-using classes should be able to meditate."""
        magic_classes = ["Mage", "Cleric", "Druid", "Warlock", "Necromancer", "Paladin"]

        from commands.general import CmdMeditate

        for cls_name in magic_classes:
            self.char1.attributes.add("class", cls_name)
            self.char1.attributes.add("is_meditating", False)

            cmd = CmdMeditate()
            cmd.caller = self.char1
            cmd.cmdstring = "meditate"
            cmd.args = ""
            cmd.func()

            self.assertTrue(
                self.char1.attributes.get("is_meditating", default=False),
                f"Class '{cls_name}' should be able to meditate"
            )
            # Reset for next iteration
            self.char1.attributes.add("is_meditating", False)

    def test_non_magic_classes_rejected(self):
        """Warrior, Rogue, Ranger, Monk should not be able to meditate."""
        non_magic = ["Warrior", "Rogue", "Ranger", "Monk"]

        from commands.general import CmdMeditate

        for cls_name in non_magic:
            self.char1.attributes.add("class", cls_name)
            self.char1.attributes.add("is_meditating", False)

            cmd = CmdMeditate()
            cmd.caller = self.char1
            cmd.cmdstring = "meditate"
            cmd.args = ""
            cmd.func()

            self.assertFalse(
                self.char1.attributes.get("is_meditating", default=False),
                f"Class '{cls_name}' should NOT be able to meditate"
            )


class TestConsiderCommand(BaseEvenniaTest):
    """Test the 'consider' / 'con' command."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="TestChar")
        self.char1.attributes.add("hp", 100)
        self.char1.attributes.add("max_hp", 100)
        self.char1.attributes.add("mana", 50)
        self.char1.attributes.add("max_mana", 50)
        self.char1.attributes.add("mv", 100)
        self.char1.attributes.add("max_mv", 100)
        self.char1.attributes.add("level", 10)
        self.char1.attributes.add("stats", {
            "str": 12, "dex": 10, "con": 11, "int": 10, "wis": 10, "cha": 10
        })
        self.char1.attributes.add("race", "Human")
        self.char1.attributes.add("class", "Warrior")
        self.char1.attributes.add("alignment", "Good")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()
        super().tearDown()

    def test_consider_without_target_shows_usage(self):
        """Consider with no argument should show usage."""
        from commands.general import CmdConsider
        cmd = CmdConsider()
        cmd.caller = self.char1
        cmd.cmdstring = "consider"
        cmd.args = ""
        cmd.parse()
        cmd.func()
        # Should not raise; prints usage message

    def test_consider_missing_target(self):
        """Consider with a target not in the room should show error."""
        from commands.general import CmdConsider
        cmd = CmdConsider()
        cmd.caller = self.char1
        cmd.cmdstring = "consider"
        cmd.args = "nonexistent"
        cmd.parse()
        cmd.func()
        # Should not raise; prints not-found message

    def test_consider_easy_target(self):
        """A much weaker target should be 'easy'."""
        goblin = create_object(DefaultCharacter, key="goblin")
        goblin.attributes.add("level", 2)
        goblin.attributes.add("stats", {
            "str": 6, "dex": 8, "con": 5, "int": 3, "wis": 4, "cha": 2
        })
        goblin.location = self.room

        from commands.general import CmdConsider
        cmd = CmdConsider()
        cmd.caller = self.char1
        cmd.cmdstring = "consider"
        cmd.args = "goblin"
        cmd.parse()
        cmd.func()
        # Should not raise; prints easy message

        goblin.delete()

    def test_consider_deadly_target(self):
        """A much stronger target should be 'deadly'."""
        dragon = create_object(DefaultCharacter, key="dragon")
        dragon.attributes.add("level", 50)
        dragon.attributes.add("stats", {
            "str": 30, "dex": 20, "con": 30, "int": 25, "wis": 25, "cha": 20
        })
        dragon.location = self.room

        from commands.general import CmdConsider
        cmd = CmdConsider()
        cmd.caller = self.char1
        cmd.cmdstring = "consider"
        cmd.args = "dragon"
        cmd.parse()
        cmd.func()
        # Should not raise; prints deadly message

        dragon.delete()

    def test_consider_fair_target(self):
        """A similarly-leveled target should be 'fair'."""
        orc = create_object(DefaultCharacter, key="orc")
        orc.attributes.add("level", 9)
        orc.attributes.add("stats", {
            "str": 14, "dex": 9, "con": 13, "int": 6, "wis": 7, "cha": 5
        })
        orc.location = self.room

        from commands.general import CmdConsider
        cmd = CmdConsider()
        cmd.caller = self.char1
        cmd.cmdstring = "consider"
        cmd.args = "orc"
        cmd.parse()
        cmd.func()
        # Should not raise; prints fair message

        orc.delete()

    def test_consider_self(self):
        """Considering yourself should give a humorous response."""
        from commands.general import CmdConsider
        cmd = CmdConsider()
        cmd.caller = self.char1
        cmd.cmdstring = "consider"
        cmd.args = self.char1.key
        cmd.parse()
        cmd.func()
        # Should not raise

    def test_consider_target_with_no_stats(self):
        """A target with no stats should default to easy (stat_ratio >= 1.5)."""
        slime = create_object(DefaultCharacter, key="slime")
        slime.attributes.add("level", 1)
        # No stats attribute set
        slime.location = self.room

        from commands.general import CmdConsider
        cmd = CmdConsider()
        cmd.caller = self.char1
        cmd.cmdstring = "consider"
        cmd.args = "slime"
        cmd.parse()
        cmd.func()
        # Should not raise; defaults to easy

        slime.delete()

    def test_con_alias_works(self):
        """The 'con' alias should work the same as 'consider'."""
        goblin = create_object(DefaultCharacter, key="goblin")
        goblin.attributes.add("level", 2)
        goblin.attributes.add("stats", {
            "str": 6, "dex": 8, "con": 5, "int": 3, "wis": 4, "cha": 2
        })
        goblin.location = self.room

        from commands.general import CmdConsider
        cmd = CmdConsider()
        cmd.caller = self.char1
        cmd.cmdstring = "con"
        cmd.args = "goblin"
        cmd.parse()
        cmd.func()
        # Should not raise

        goblin.delete()


class TestRecallCommand(BaseEvenniaTest):
    """Test the 'recall' command."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="TestChar")
        self.char1.attributes.add("hp", 100)
        self.char1.attributes.add("max_hp", 100)
        self.char1.attributes.add("mana", 50)
        self.char1.attributes.add("max_mana", 50)
        self.char1.attributes.add("mv", 100)
        self.char1.attributes.add("max_mv", 100)
        self.char1.attributes.add("race", "Human")
        self.char1.attributes.add("class", "Warrior")
        self.char1.attributes.add("alignment", "Good")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()
        super().tearDown()

    def test_recall_below_level_30_fails(self):
        """Characters below level 30 cannot recall."""
        self.char1.attributes.add("level", 15)

        from commands.general import CmdRecall
        cmd = CmdRecall()
        cmd.caller = self.char1
        cmd.cmdstring = "recall"
        cmd.args = ""
        cmd.func()

        # Should still be in the same room
        self.assertEqual(self.char1.location, self.room)

    def test_recall_at_level_30_succeeds(self):
        """Characters at level 30+ can recall to their faction home."""
        self.char1.attributes.add("level", 30)

        # Create the home room
        home = create_object(DefaultRoom, key="Aethelgard - The Grand Sanctum")

        from commands.general import CmdRecall
        cmd = CmdRecall()
        cmd.caller = self.char1
        cmd.cmdstring = "recall"
        cmd.args = ""
        cmd.func()

        # Should have moved to the home room
        self.assertEqual(self.char1.location, home)

        home.delete()

    def test_recall_evil_faction(self):
        """Evil characters should recall to Gorgoroth."""
        self.char1.attributes.add("level", 35)
        self.char1.attributes.add("alignment", "Evil")

        home = create_object(DefaultRoom, key="Gorgoroth - The Blood Forge")

        from commands.general import CmdRecall
        cmd = CmdRecall()
        cmd.caller = self.char1
        cmd.cmdstring = "recall"
        cmd.args = ""
        cmd.func()

        self.assertEqual(self.char1.location, home)

        home.delete()

    def test_recall_already_at_home(self):
        """Recalling while already at home should notify the player."""
        self.char1.attributes.add("level", 30)

        home = create_object(DefaultRoom, key="Aethelgard - The Grand Sanctum")
        self.char1.location = home

        from commands.general import CmdRecall
        cmd = CmdRecall()
        cmd.caller = self.char1
        cmd.cmdstring = "recall"
        cmd.args = ""
        cmd.func()

        # Should still be at home
        self.assertEqual(self.char1.location, home)

        home.delete()

    def test_recall_home_not_found(self):
        """If the home room doesn't exist, should show error."""
        self.char1.attributes.add("level", 30)

        from commands.general import CmdRecall
        cmd = CmdRecall()
        cmd.caller = self.char1
        cmd.cmdstring = "recall"
        cmd.args = ""
        cmd.func()

        # Should remain in the same room
        self.assertEqual(self.char1.location, self.room)

    def test_recall_level_29_fails(self):
        """Level 29 should still fail (boundary test)."""
        self.char1.attributes.add("level", 29)

        from commands.general import CmdRecall
        cmd = CmdRecall()
        cmd.caller = self.char1
        cmd.cmdstring = "recall"
        cmd.args = ""
        cmd.func()

        self.assertEqual(self.char1.location, self.room)

    def test_recall_level_30_boundary(self):
        """Level 30 exactly should succeed (boundary test)."""
        self.char1.attributes.add("level", 30)

        home = create_object(DefaultRoom, key="Aethelgard - The Grand Sanctum")

        from commands.general import CmdRecall
        cmd = CmdRecall()
        cmd.caller = self.char1
        cmd.cmdstring = "recall"
        cmd.args = ""
        cmd.func()

        self.assertEqual(self.char1.location, home)

        home.delete()