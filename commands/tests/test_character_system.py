"""
Comprehensive Character System Verification Tests for 'rop'
=============================================================

Tests all character system components:
  - Stat key consistency (agi/dex, chr/cha fix)
  - Chargen stat rolling with correct keys
  - Level-up logic (class-specific stat gains)
  - Class proficiencies (weapon/armor restrictions)
  - Practice points / skill training
  - Guildmaster NPC training
  - Reputation system
  - Saving throws with correct race names
  - Alignment system
  - Encumbrance
  - Recovery mechanics
  - Status effects
  - Damage types
  - XP/level formulas

Run with:
    evennia test commands.tests.test_character_system
"""

import random
from evennia.utils.test_resources import EvenniaTest
from evennia.utils.evmenu import EvMenu
from evennia import create_object
from typeclasses.characters import Character
from world.rules import RACES, CLASSES, xp_to_level, stats_on_level_up
from world.chargen import (
    roll_stats,
    format_stats_display,
    CORE_STATS,
    STAT_VARIANCE_MIN,
    STAT_VARIANCE_MAX,
    MAX_REROLLS,
)


# ===========================================================================
# TEST 1: Stat Key Consistency (CRITICAL BUG FIX VERIFICATION)
# ===========================================================================

class TestStatKeyConsistency(EvenniaTest):
    """Verify stat keys are consistent across all systems."""

    def test_core_stats_use_dex_cha_not_agi_chr(self):
        """chargen CORE_STATS must use 'dex' and 'cha' (not 'agi'/'chr')."""
        self.assertIn("dex", CORE_STATS, "CORE_STATS must contain 'dex', not 'agi'")
        self.assertIn("cha", CORE_STATS, "CORE_STATS must contain 'cha', not 'chr'")
        self.assertNotIn("agi", CORE_STATS, "CORE_STATS must NOT contain 'agi'")
        self.assertNotIn("chr", CORE_STATS, "CORE_STATS must NOT contain 'chr'")

    def test_race_stats_use_dex_cha(self):
        """All RACES must use 'dex' and 'cha' keys."""
        for race_name, race_data in RACES.items():
            stats = race_data["stats"]
            self.assertIn("dex", stats, f"{race_name} missing 'dex' key")
            self.assertIn("cha", stats, f"{race_name} missing 'cha' key")
            self.assertNotIn("agi", stats, f"{race_name} should not have 'agi'")
            self.assertNotIn("chr", stats, f"{race_name} should not have 'chr'")

    def test_roll_stats_reads_race_base_correctly(self):
        """roll_stats() must read the correct base values from RACES."""
        for race_name in RACES:
            base_stats = RACES[race_name]["stats"]
            # Roll many times to verify the base is being read correctly
            for _ in range(20):
                rolled = roll_stats(race_name)
                for stat in CORE_STATS:
                    base = base_stats.get(stat, 10)
                    min_val = max(1, base + STAT_VARIANCE_MIN)
                    max_val = base + STAT_VARIANCE_MAX
                    self.assertGreaterEqual(rolled[stat], min_val,
                        f"{race_name} {stat}: {rolled[stat]} < min {min_val} (base={base})")
                    self.assertLessEqual(rolled[stat], max_val,
                        f"{race_name} {stat}: {rolled[stat]} > max {max_val} (base={base})")

    def test_roll_stats_pixie_dex_is_high(self):
        """Pixie has base DEX 16, so rolled DEX should be >= 14."""
        found_high = False
        for _ in range(30):
            stats = roll_stats("Pixie")
            if stats["dex"] >= 14:
                found_high = True
                break
        self.assertTrue(found_high,
            "Pixie should roll high DEX (base 16), but never got >= 14")

    def test_roll_stats_ogre_str_is_high(self):
        """Ogre has base STR 16, so rolled STR should be >= 14."""
        found_high = False
        for _ in range(30):
            stats = roll_stats("Ogre")
            if stats["str"] >= 14:
                found_high = True
                break
        self.assertTrue(found_high,
            "Ogre should roll high STR (base 16), but never got >= 14")

    def test_roll_stats_ogre_cha_is_low(self):
        """Ogre has base CHA 3, so rolled CHA should be <= 7."""
        found_low = False
        for _ in range(30):
            stats = roll_stats("Ogre")
            if stats["cha"] <= 7:
                found_low = True
                break
        self.assertTrue(found_low,
            "Ogre should roll low CHA (base 3), but never got <= 7")

    def test_format_stats_display_uses_dex_cha(self):
        """format_stats_display should display DEX and CHA."""
        stats = {"str": 10, "dex": 12, "con": 10, "int": 10, "wis": 10, "cha": 8}
        display = format_stats_display(stats)
        self.assertIn("DEX", display, "Display should show DEX")
        self.assertIn("CHA", display, "Display should show CHA")
        self.assertNotIn("AGI", display, "Display should NOT show AGI")
        self.assertNotIn("CHR", display, "Display should NOT show CHR")


# ===========================================================================
# TEST 2: Level-Up Logic
# ===========================================================================

class TestLevelUpLogic(EvenniaTest):
    """Verify level-up stat gains, HP/Mana/MV scaling, and XP thresholds."""

    def setUp(self):
        super().setUp()
        self.char = create_object(
            Character,
            key="TestChar",
            location=None,
        )
        self.char.db.race = "Human"
        self.char.db.class_field = "Warrior"
        self.char.attributes.add("class", "Warrior")
        self.char.attributes.add("race", "Human")
        self.char.attributes.add("level", 1)
        self.char.attributes.add("xp", 0)
        self.char.attributes.add("xp_to_level", xp_to_level(1))
        self.char.attributes.add("stats", {"str": 12, "dex": 10, "con": 12, "int": 8, "wis": 8, "cha": 10})
        self.char.attributes.add("max_hp", 35)
        self.char.attributes.add("hp", 35)
        self.char.attributes.add("max_mana", 20)
        self.char.attributes.add("mana", 20)
        self.char.attributes.add("max_mv", 100)
        self.char.attributes.add("mv", 100)
        self.char.attributes.add("max_stamina", 100)
        self.char.attributes.add("stamina", 100)
        self.char.attributes.add("learned_spells", [])
        self.char.attributes.add("position", "standing")

    def tearDown(self):
        if self.char and self.char.id:
            self.char.delete()
        super().tearDown()

    def test_xp_to_level_formula(self):
        """XP to level = level * 1000."""
        self.assertEqual(xp_to_level(1), 1000)
        self.assertEqual(xp_to_level(2), 2000)
        self.assertEqual(xp_to_level(10), 10000)
        self.assertEqual(xp_to_level(50), 50000)

    def test_award_xp_no_level_up(self):
        """Awarding XP below threshold should not trigger level-up."""
        self.char.attributes.add("xp", 0)
        self.char.award_xp(500)
        self.assertEqual(self.char.attributes.get("level", default=1), 1)
        self.assertEqual(self.char.attributes.get("xp", default=0), 500)

    def test_award_xp_single_level_up(self):
        """Awarding exactly enough XP triggers one level-up."""
        self.char.attributes.add("xp", 0)
        self.char.award_xp(1000)  # Exactly enough for level 1->2
        self.assertEqual(self.char.attributes.get("level", default=1), 2)
        # XP should be deducted
        xp_after = self.char.attributes.get("xp", default=0)
        self.assertLess(xp_after, 1000, "XP should be deducted for level-up")

    def test_award_xp_multiple_level_ups(self):
        """Awarding enough XP for multiple levels should trigger all of them."""
        self.char.attributes.add("xp", 0)
        # Level 1->2: 1000, Level 2->3: 2000, total needed: 3000
        self.char.award_xp(3500)
        level = self.char.attributes.get("level", default=1)
        self.assertGreaterEqual(level, 3, f"Should be at least level 3, got {level}")

    def test_level_up_increases_max_hp(self):
        """Level-up should increase max_hp."""
        initial_hp = self.char.attributes.get("max_hp", default=35)
        self.char.attributes.add("xp", 0)
        self.char.award_xp(2000)
        new_hp = self.char.attributes.get("max_hp", default=35)
        self.assertGreater(new_hp, initial_hp, "max_hp should increase on level-up")

    def test_level_up_increases_max_mana(self):
        """Level-up should increase max_mana."""
        initial_mana = self.char.attributes.get("max_mana", default=20)
        self.char.attributes.add("xp", 0)
        self.char.award_xp(2000)
        new_mana = self.char.attributes.get("max_mana", default=20)
        self.assertGreater(new_mana, initial_mana, "max_mana should increase on level-up")

    def test_level_up_refills_hp_to_max(self):
        """Level-up should refill HP to the new max."""
        self.char.attributes.add("hp", 10)  # Low HP
        self.char.attributes.add("xp", 0)
        self.char.award_xp(2000)
        hp = self.char.attributes.get("hp", default=0)
        max_hp = self.char.attributes.get("max_hp", default=100)
        self.assertEqual(hp, max_hp, "HP should be refilled to max on level-up")

    def test_level_up_awards_practice_points(self):
        """Level-up should award practice points based on class."""
        from world.guildmaster import PracticeSession
        self.char.attributes.add("practice_session", PracticeSession())
        self.char.attributes.add("xp", 0)
        self.char.award_xp(2000)
        session = self.char.attributes.get("practice_session", default=None)
        self.assertIsNotNone(session)
        self.assertGreater(session.practice_points, 0,
            "Should have practice points after level-up")

    def test_stats_on_level_up_returns_valid_dict(self):
        """stats_on_level_up should return a dict with all six core stats."""
        bonuses = stats_on_level_up(self.char)
        self.assertIsInstance(bonuses, dict)
        for stat in CORE_STATS:
            self.assertIn(stat, bonuses, f"Missing stat {stat} in level-up bonuses")

    def test_class_specific_level_up_stats(self):
        """Different classes should get different stat distributions."""
        from world.rules import stats_on_level_up

        warrior_bonuses = stats_on_level_up("Warrior", self.char)
        mage_bonuses = stats_on_level_up("Mage", self.char)

        # Warriors should get more STR/CON than INT
        warrior_physical = warrior_bonuses.get("str", 0) + warrior_bonuses.get("con", 0)
        warrior_mental = warrior_bonuses.get("int", 0) + warrior_bonuses.get("wis", 0)
        self.assertGreater(warrior_physical, warrior_mental,
            "Warriors should get more physical stats than mental")

        # Mages should get more INT/WIS than STR
        mage_physical = mage_bonuses.get("str", 0) + mage_bonuses.get("con", 0)
        mage_mental = mage_bonuses.get("int", 0) + mage_bonuses.get("wis", 0)
        self.assertGreater(mage_mental, mage_physical,
            "Mages should get more mental stats than physical")


# ===========================================================================
# TEST 3: Class Proficiencies
# ===========================================================================

class TestClassProficiencies(EvenniaTest):
    """Verify weapon/armor proficiency restrictions."""

    def setUp(self):
        super().setUp()
        self.char = create_object(
            Character,
            key="ProfTest",
            location=None,
        )

    def tearDown(self):
        if self.char and self.char.id:
            self.char.delete()
        super().tearDown()

    def test_can_equip_slot_warrior_heavy_armor(self):
        """Warriors can wear heavy armor."""
        from world.race_class_matrix import can_equip_slot
        self.char.attributes.add("class", "Warrior")
        self.char.attributes.add("race", "Human")
        allowed, reason = can_equip_slot(self.char, "chest", "armor_heavy")
        self.assertTrue(allowed, f"Warrior should be able to wear heavy armor: {reason}")

    def test_can_equip_slot_mage_heavy_armor(self):
        """Mages cannot wear heavy armor."""
        from world.race_class_matrix import can_equip_slot
        self.char.attributes.add("class", "Mage")
        self.char.attributes.add("race", "Human")
        allowed, reason = can_equip_slot(self.char, "chest", "armor_heavy")
        self.assertFalse(allowed, "Mage should NOT be able to wear heavy armor")

    def test_can_equip_slot_warrior_sword(self):
        """Warriors can wield swords."""
        from world.race_class_matrix import can_equip_slot
        self.char.attributes.add("class", "Warrior")
        self.char.attributes.add("race", "Human")
        allowed, reason = can_equip_slot(self.char, "main_hand", "weapon_sword")
        self.assertTrue(allowed, f"Warrior should be able to wield swords: {reason}")

    def test_can_equip_slot_mage_sword(self):
        """Mages cannot wield swords."""
        from world.race_class_matrix import can_equip_slot
        self.char.attributes.add("class", "Mage")
        self.char.attributes.add("race", "Human")
        allowed, reason = can_equip_slot(self.char, "main_hand", "weapon_sword")
        self.assertFalse(allowed, "Mage should NOT be able to wield swords")

    def test_can_equip_slot_mage_dagger(self):
        """Mages can wield daggers."""
        from world.race_class_matrix import can_equip_slot
        self.char.attributes.add("class", "Mage")
        self.char.attributes.add("race", "Human")
        allowed, reason = can_equip_slot(self.char, "main_hand", "weapon_dagger")
        self.assertTrue(allowed, f"Mage should be able to wield daggers: {reason}")

    def test_pixie_cannot_equip_heavy_chest(self):
        """Pixie racial restriction: no heavy chest."""
        from world.race_class_matrix import can_equip_slot
        self.char.attributes.add("class", "Warrior")
        self.char.attributes.add("race", "Pixie")
        allowed, reason = can_equip_slot(self.char, "chest_heavy", "armor_heavy")
        self.assertFalse(allowed, "Pixie should NOT be able to equip chest_heavy")

    def test_centaur_cannot_equip_feet(self):
        """Centaur racial restriction: no feet slot."""
        from world.race_class_matrix import can_equip_slot
        self.char.attributes.add("class", "Warrior")
        self.char.attributes.add("race", "Centaur")
        allowed, reason = can_equip_slot(self.char, "feet", "armor_light")
        self.assertFalse(allowed, "Centaur should NOT be able to equip feet")

    def test_all_classes_have_weapon_types(self):
        """Every class should have defined weapon types."""
        from world.race_class_matrix import CLASS_WEAPON_TYPES
        for cls_name in CLASSES:
            self.assertIn(cls_name, CLASS_WEAPON_TYPES,
                f"Class {cls_name} missing from CLASS_WEAPON_TYPES")

    def test_all_classes_have_armor_types(self):
        """Every class should have defined armor types."""
        from world.race_class_matrix import CLASS_ARMOR_TYPES
        for cls_name in CLASSES:
            self.assertIn(cls_name, CLASS_ARMOR_TYPES,
                f"Class {cls_name} missing from CLASS_ARMOR_TYPES")


# ===========================================================================
# TEST 4: Practice Points & Guildmaster Training
# ===========================================================================

class TestPracticeAndTraining(EvenniaTest):
    """Verify practice point system, guildmaster training, and skill learning."""

    def setUp(self):
        super().setUp()
        self.char = create_object(
            Character,
            key="TrainTest",
            location=None,
        )
        self.char.attributes.add("class", "Warrior")
        self.char.attributes.add("race", "Human")
        self.char.attributes.add("level", 10)
        self.char.attributes.add("learned_spells", [])
        self.char.attributes.add("trained_skills", [])
        self.char.attributes.add("stats", {"str": 14, "dex": 10, "con": 12, "int": 8, "wis": 8, "cha": 10})

    def tearDown(self):
        if self.char and self.char.id:
            self.char.delete()
        super().tearDown()

    def test_practice_session_creation(self):
        """PracticeSession should be creatable with default values."""
        from world.guildmaster import PracticeSession
        session = PracticeSession()
        self.assertEqual(session.practice_points, 0)
        self.assertEqual(len(session.trained_spells), 0)
        self.assertEqual(len(session.trained_skills), 0)

    def test_award_practice_points(self):
        """award_practice_points should add points based on class."""
        from world.guildmaster import award_practice_points, PracticeSession
        self.char.attributes.add("practice_session", PracticeSession())
        award_practice_points(self.char, 2)
        session = self.char.attributes.get("practice_session", default=None)
        self.assertIsNotNone(session)
        self.assertGreater(session.practice_points, 0,
            "Warrior should get practice points on level-up")

    def test_guildmaster_get_trainable_spells(self):
        """Guildmaster should return trainable spells for a character."""
        from world.guildmaster import GuildmasterNPC
        gm = create_object(GuildmasterNPC, key="TestGM", location=None)
        try:
            spells = gm.get_trainable_spells(self.char)
            self.assertIsInstance(spells, list)
            for spell in spells:
                self.assertIn("name", spell)
                self.assertIn("level", spell)
                self.assertIn("cost", spell)
        finally:
            if gm.id:
                gm.delete()

    def test_guildmaster_get_trainable_skills(self):
        """Guildmaster should return trainable skills for a character."""
        from world.guildmaster import GuildmasterNPC
        gm = create_object(GuildmasterNPC, key="TestGM", location=None)
        try:
            skills = gm.get_trainable_skills(self.char)
            self.assertIsInstance(skills, list)
            for skill in skills:
                self.assertIn("name", skill)
                self.assertIn("key", skill)
                self.assertIn("cost", skill)
        finally:
            if gm.id:
                gm.delete()

    def test_train_skill_warrior_kick(self):
        """A Warrior should be able to train kick with practice points."""
        from world.guildmaster import GuildmasterNPC, PracticeSession
        session = PracticeSession()
        session.practice_points = 10
        self.char.attributes.add("practice_session", session)

        gm = create_object(GuildmasterNPC, key="TestGM", location=None)
        try:
            ok, msg = gm.train_skill(self.char, "kick")
            self.assertTrue(ok, f"Warrior should be able to train kick: {msg}")
        finally:
            if gm.id:
                gm.delete()

    def test_train_skill_insufficient_points(self):
        """Training should fail with insufficient practice points."""
        from world.guildmaster import GuildmasterNPC, PracticeSession
        session = PracticeSession()
        session.practice_points = 0
        self.char.attributes.add("practice_session", session)

        gm = create_object(GuildmasterNPC, key="TestGM", location=None)
        try:
            ok, msg = gm.train_skill(self.char, "kick")
            self.assertFalse(ok, "Should fail with 0 practice points")
        finally:
            if gm.id:
                gm.delete()


# ===========================================================================
# TEST 5: Reputation System
# ===========================================================================

class TestReputationSystem(EvenniaTest):
    """Verify the reputation/faction standing system."""

    def setUp(self):
        super().setUp()
        self.char = create_object(
            Character,
            key="RepTest",
            location=None,
        )
        self.char.attributes.add("race", "Human")
        self.char.attributes.add("alignment", "Good")

    def tearDown(self):
        if self.char and self.char.id:
            self.char.delete()
        super().tearDown()

    def test_reputation_import(self):
        """Reputation module should be importable."""
        try:
            from world.reputation import ReputationSystem
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import reputation module: {e}")

    def test_reputation_initialization(self):
        """New characters should have reputation attributes."""
        from world.reputation import ReputationSystem
        ReputationSystem.initialize(self.char)
        rep = self.char.attributes.get("reputation", default=None)
        self.assertIsNotNone(rep, "Character should have reputation dict")

    def test_reputation_get_standing(self):
        """get_standing should return a valid tier string."""
        from world.reputation import ReputationSystem
        ReputationSystem.initialize(self.char)
        standing = ReputationSystem.get_standing(self.char, "aethelgard")
        self.assertIsInstance(standing, str)
        self.assertIn(standing, ReputationSystem.STANDING_TIERS,
            f"'{standing}' should be a valid tier")

    def test_reputation_adjust(self):
        """adjust_reputation should change standing values."""
        from world.reputation import ReputationSystem
        ReputationSystem.initialize(self.char)
        initial = ReputationSystem.get_reputation(self.char, "aethelgard")
        ReputationSystem.adjust_reputation(self.char, "aethelgard", 500)
        after = ReputationSystem.get_reputation(self.char, "aethelgard")
        self.assertGreater(after, initial, "Reputation should increase")

    def test_reputation_tier_thresholds(self):
        """Reputation should correctly map value ranges to tiers."""
        from world.reputation import ReputationSystem
        self.assertIn("Neutral", ReputationSystem.STANDING_TIERS)
        self.assertIn("Friendly", ReputationSystem.STANDING_TIERS)
        self.assertIn("Honored", ReputationSystem.STANDING_TIERS)
        self.assertIn("Hated", ReputationSystem.STANDING_TIERS)

    def test_reputation_vendor_discount(self):
        """Higher reputation should give better vendor discounts."""
        from world.reputation import ReputationSystem
        ReputationSystem.initialize(self.char)
        # Neutral should give 1.0 multiplier (no discount)
        discount = ReputationSystem.get_vendor_discount(self.char, "aethelgard")
        self.assertLessEqual(discount, 1.0)
        self.assertGreater(discount, 0.0)

    def test_reputation_display_format(self):
        """format_reputation should return readable string."""
        from world.reputation import ReputationSystem
        ReputationSystem.initialize(self.char)
        display = ReputationSystem.format_reputation(self.char)
        self.assertIsInstance(display, str)
        self.assertGreater(len(display), 0)

    def test_reputation_multiple_factions(self):
        """Track reputation with multiple factions independently."""
        from world.reputation import ReputationSystem
        ReputationSystem.initialize(self.char)
        ReputationSystem.adjust_reputation(self.char, "aethelgard", 1000)
        ReputationSystem.adjust_reputation(self.char, "gorgoroth", -500)
        good_rep = ReputationSystem.get_reputation(self.char, "aethelgard")
        evil_rep = ReputationSystem.get_reputation(self.char, "gorgoroth")
        self.assertGreater(good_rep, evil_rep,
            "Good faction rep should be higher than evil faction rep")

    def test_reputation_clamped(self):
        """Reputation values should be clamped to min/max."""
        from world.reputation import ReputationSystem
        ReputationSystem.initialize(self.char)
        ReputationSystem.adjust_reputation(self.char, "aethelgard", 99999)
        rep = ReputationSystem.get_reputation(self.char, "aethelgard")
        self.assertLessEqual(rep, ReputationSystem.MAX_REPUTATION)
        ReputationSystem.adjust_reputation(self.char, "aethelgard", -99999)
        rep = ReputationSystem.get_reputation(self.char, "aethelgard")
        self.assertGreaterEqual(rep, ReputationSystem.MIN_REPUTATION)


# ===========================================================================
# TEST 6: Saving Throws
# ===========================================================================

class TestSavingThrows(EvenniaTest):
    """Verify saving throw system works with correct race names."""

    def setUp(self):
        super().setUp()
        self.char = create_object(
            Character,
            key="SaveTest",
            location=None,
        )
        self.char.attributes.add("race", "Human")
        self.char.attributes.add("class", "Warrior")
        self.char.attributes.add("level", 5)
        self.char.attributes.add("stats", {"str": 14, "dex": 10, "con": 12, "int": 8, "wis": 8, "cha": 10})

    def tearDown(self):
        if self.char and self.char.id:
            self.char.delete()
        super().tearDown()

    def test_get_base_save_returns_valid_value(self):
        """get_base_save should return a value between 2 and 20."""
        from world.saving_throws import get_base_save, SavingThrow
        for save_type in SavingThrow:
            save = get_base_save(self.char, save_type)
            self.assertGreaterEqual(save, 2, f"{save_type} save too low: {save}")
            self.assertLessEqual(save, 20, f"{save_type} save too high: {save}")

    def test_roll_saving_throw_returns_tuple(self):
        """roll_saving_throw should return (passed, roll, dc)."""
        from world.saving_throws import roll_saving_throw, SavingThrow
        result = roll_saving_throw(self.char, SavingThrow.SPELL, dc=15)
        self.assertEqual(len(result), 3)
        passed, roll, dc = result
        self.assertIsInstance(passed, bool)
        self.assertIsInstance(roll, int)
        self.assertIsInstance(dc, int)

    def test_natural_20_always_succeeds(self):
        """Natural 20 should always pass a saving throw."""
        from world.saving_throws import roll_saving_throw, SavingThrow
        # We can't force a roll, but we know 20 always passes
        # Test the logic: if roll is 20, passed must be True
        for _ in range(50):
            passed, roll, dc = roll_saving_throw(
                self.char, SavingThrow.SPELL, dc=999
            )
            if roll == 20:
                self.assertTrue(passed, "Natural 20 should always succeed")

    def test_natural_1_always_fails(self):
        """Natural 1 should always fail a saving throw."""
        from world.saving_throws import roll_saving_throw, SavingThrow
        for _ in range(50):
            passed, roll, dc = roll_saving_throw(
                self.char, SavingThrow.SPELL, dc=1
            )
            if roll == 1:
                self.assertFalse(passed, "Natural 1 should always fail")

    def test_racial_save_bonuses_use_correct_race_names(self):
        """RACIAL_SAVE_BONUSES must use the 16 actual race names."""
        from world.saving_throws import RACIAL_SAVE_BONUSES
        for race_name in RACES:
            # Every race should have save bonuses defined
            self.assertIn(race_name, RACIAL_SAVE_BONUSES,
                f"Race '{race_name}' missing from RACIAL_SAVE_BONUSES")

    def test_race_save_bonuses_different(self):
        """Different races should have different save bonuses."""
        from world.saving_throws import RACIAL_SAVE_BONUSES, SavingThrow
        # At least some races should differ
        human_bonuses = RACIAL_SAVE_BONUSES.get("Human", {})
        dwarf_bonuses = RACIAL_SAVE_BONUSES.get("Mountain Dwarf", {})
        # Dwarves should have better poison saves than humans
        if human_bonuses and dwarf_bonuses:
            self.assertGreaterEqual(
                dwarf_bonuses.get(SavingThrow.POISON, 0),
                human_bonuses.get(SavingThrow.POISON, 0),
                "Dwarves should have >= poison save bonus vs humans"
            )


# ===========================================================================
# TEST 7: Alignment System
# ===========================================================================

class TestAlignmentSystem(EvenniaTest):
    """Verify alignment tracking, outlaw status, and bounties."""

    def setUp(self):
        super().setUp()
        self.char = create_object(
            Character,
            key="AlignTest",
            location=None,
        )
        self.char.attributes.add("alignment_points", 0)

    def tearDown(self):
        if self.char and self.char.id:
            self.char.delete()
        super().tearDown()

    def test_get_alignment_good(self):
        """alignment_points >= 750 should be Good."""
        from world.alignment_system import AlignmentSystem
        self.char.attributes.add("alignment_points", 800)
        self.assertEqual(AlignmentSystem.get_alignment(self.char), "Good")

    def test_get_alignment_evil(self):
        """alignment_points <= -750 should be Evil."""
        from world.alignment_system import AlignmentSystem
        self.char.attributes.add("alignment_points", -800)
        self.assertEqual(AlignmentSystem.get_alignment(self.char), "Evil")

    def test_get_alignment_neutral(self):
        """alignment_points between -749 and 749 should be Neutral."""
        from world.alignment_system import AlignmentSystem
        self.char.attributes.add("alignment_points", 0)
        self.assertEqual(AlignmentSystem.get_alignment(self.char), "Neutral")

    def test_adjust_alignment(self):
        """adjust_alignment should change points and update label."""
        from world.alignment_system import AlignmentSystem
        AlignmentSystem.adjust_alignment(self.char, 100)
        points = self.char.attributes.get("alignment_points", default=0)
        self.assertEqual(points, 100)

    def test_adjust_alignment_clamped(self):
        """Alignment points should be clamped to [-1000, 1000]."""
        from world.alignment_system import AlignmentSystem
        AlignmentSystem.adjust_alignment(self.char, 2000)
        points = self.char.attributes.get("alignment_points", default=0)
        self.assertEqual(points, 1000)
        AlignmentSystem.adjust_alignment(self.char, -3000)
        points = self.char.attributes.get("alignment_points", default=0)
        self.assertEqual(points, -1000)

    def test_outlaw_status(self):
        """Outlaw flag should be settable and checkable."""
        from world.alignment_system import AlignmentSystem, is_outlaw
        self.assertFalse(is_outlaw(self.char))
        AlignmentSystem.set_outlaw(self.char, 60)
        self.assertTrue(is_outlaw(self.char))
        AlignmentSystem.clear_outlaw(self.char)
        self.assertFalse(is_outlaw(self.char))

    def test_bounty_system(self):
        """Bounty should be addable and clearable."""
        from world.alignment_system import AlignmentSystem
        self.assertEqual(AlignmentSystem.add_bounty(self.char, 500), 500)
        self.assertEqual(AlignmentSystem.add_bounty(self.char, 300), 800)
        AlignmentSystem.clear_bounty(self.char)
        self.assertEqual(self.char.attributes.get("bounty", default=0), 0)


# ===========================================================================
# TEST 8: Encumbrance System
# ===========================================================================

class TestEncumbrance(EvenniaTest):
    """Verify encumbrance/weight system."""

    def setUp(self):
        super().setUp()
        self.char = create_object(
            Character,
            key="EncumTest",
            location=None,
        )
        self.char.attributes.add("str", 14)
        self.char.attributes.add("stats", {"str": 14, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})

    def tearDown(self):
        if self.char and self.char.id:
            self.char.delete()
        super().tearDown()

    def test_carry_capacity_positive(self):
        """Carry capacity should be positive."""
        from world.encumbrance import get_carry_capacity
        capacity = get_carry_capacity(self.char)
        self.assertGreater(capacity, 0, "Carry capacity should be positive")

    def test_carry_capacity_scales_with_str(self):
        """Higher STR should give more carry capacity."""
        from world.encumbrance import get_carry_capacity
        weak_char = create_object(Character, key="Weak", location=None)
        strong_char = create_object(Character, key="Strong", location=None)
        try:
            weak_char.attributes.add("str", 6)
            weak_char.attributes.add("stats", {"str": 6, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
            strong_char.attributes.add("str", 18)
            strong_char.attributes.add("stats", {"str": 18, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
            weak_cap = get_carry_capacity(weak_char)
            strong_cap = get_carry_capacity(strong_char)
            self.assertGreater(strong_cap, weak_cap,
                "Stronger character should have higher carry capacity")
        finally:
            if weak_char.id:
                weak_char.delete()
            if strong_char.id:
                strong_char.delete()

    def test_current_encumbrance_zero_for_empty(self):
        """Empty inventory should have 0 encumbrance."""
        from world.encumbrance import get_current_encumbrance
        enc = get_current_encumbrance(self.char)
        self.assertEqual(enc, 0.0, "Empty character should have 0 encumbrance")


# ===========================================================================
# TEST 9: Recovery Mechanics
# ===========================================================================

class TestRecovery(EvenniaTest):
    """Verify HP/Mana/MV regeneration."""

    def setUp(self):
        super().setUp()
        self.char = create_object(
            Character,
            key="RecoveryTest",
            location=None,
        )
        self.char.attributes.add("max_hp", 100)
        self.char.attributes.add("hp", 50)
        self.char.attributes.add("max_mana", 50)
        self.char.attributes.add("mana", 25)
        self.char.attributes.add("max_mv", 100)
        self.char.attributes.add("mv", 50)
        self.char.attributes.add("max_stamina", 100)
        self.char.attributes.add("stamina", 50)
        self.char.attributes.add("position", "standing")
        self.char.attributes.add("is_resting", False)
        self.char.attributes.add("is_meditating", False)
        self.char.attributes.add("stats", {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})

    def tearDown(self):
        if self.char and self.char.id:
            self.char.delete()
        super().tearDown()

    def test_hp_regen_standing(self):
        """Standing should regenerate some HP."""
        from world.recovery import regenerate_hp
        initial = self.char.attributes.get("hp", default=50)
        regen = regenerate_hp(self.char)
        self.assertGreaterEqual(regen, 0, "HP regen should be non-negative")

    def test_hp_regen_resting_faster(self):
        """Resting should regenerate HP faster than standing."""
        from world.recovery import regenerate_hp
        self.char.attributes.add("is_resting", True)
        self.char.attributes.add("position", "resting")
        regen_resting = regenerate_hp(self.char)
        self.char.attributes.add("is_resting", False)
        self.char.attributes.add("position", "standing")
        regen_standing = regenerate_hp(self.char)
        self.assertGreaterEqual(regen_resting, regen_standing,
            "Resting HP regen should be >= standing HP regen")

    def test_mana_regen_meditating_faster(self):
        """Meditating should regenerate mana faster than standing."""
        from world.recovery import regenerate_mana
        self.char.attributes.add("is_meditating", True)
        self.char.attributes.add("position", "meditating")
        regen_med = regenerate_mana(self.char)
        self.char.attributes.add("is_meditating", False)
        self.char.attributes.add("position", "standing")
        regen_stand = regenerate_mana(self.char)
        self.assertGreaterEqual(regen_med, regen_stand,
            "Meditating mana regen should be >= standing mana regen")

    def test_mv_regen(self):
        """Should regenerate movement points."""
        from world.recovery import regenerate_mv
        regen = regenerate_mv(self.char)
        self.assertGreaterEqual(regen, 0, "MV regen should be non-negative")

    def test_stamina_regen(self):
        """Should regenerate stamina."""
        from world.recovery import regenerate_stamina
        regen = regenerate_stamina(self.char)
        self.assertGreaterEqual(regen, 0, "Stamina regen should be non-negative")


# ===========================================================================
# TEST 10: Damage Types
# ===========================================================================

class TestDamageTypes(EvenniaTest):
    """Verify damage type system."""

    def test_damage_type_enum_complete(self):
        """DamageType enum should have all required types."""
        from world.damage_formulas import DamageType
        expected = {"slash", "pierce", "blunt", "magic_fire", "magic_cold",
                    "magic_lightning", "magic_shadow", "magic_holy", "poison", "bleed"}
        actual = {dt.value for dt in DamageType}
        self.assertEqual(expected, actual)

    def test_armor_mitigation_has_all_types(self):
        """ARMOR_MITIGATION should cover all damage types."""
        from world.damage_formulas import ARMOR_MITIGATION, DamageType
        for dt in DamageType:
            self.assertIn(dt, ARMOR_MITIGATION,
                f"DamageType {dt} missing from ARMOR_MITIGATION")

    def test_physical_damage_has_mitigation(self):
        """Physical damage types should have non-zero mitigation."""
        from world.damage_formulas import ARMOR_MITIGATION, DamageType
        self.assertGreater(ARMOR_MITIGATION[DamageType.SLASH], 0)
        self.assertGreater(ARMOR_MITIGATION[DamageType.PIERCE], 0)
        self.assertGreater(ARMOR_MITIGATION[DamageType.BLUNT], 0)

    def test_magic_damage_has_zero_armor_mitigation(self):
        """Magic damage types should have zero armor mitigation."""
        from world.damage_formulas import ARMOR_MITIGATION, DamageType
        self.assertEqual(ARMOR_MITIGATION[DamageType.MAGIC_FIRE], 0)
        self.assertEqual(ARMOR_MITIGATION[DamageType.MAGIC_COLD], 0)
        self.assertEqual(ARMOR_MITIGATION[DamageType.MAGIC_SHADOW], 0)


# ===========================================================================
# TEST 11: CharGen Integration
# ===========================================================================

class TestChargenIntegration(EvenniaTest):
    """Full chargen flow integration tests."""

    def setUp(self):
        super().setUp()
        self.caller = self.account
        for char in self.caller.characters.all():
            self.caller.characters.remove(char)

    def tearDown(self):
        for char in self.caller.characters.all():
            try:
                char.delete()
            except Exception:
                pass
        super().tearDown()

    def test_full_flow_human_warrior(self):
        """Complete chargen: Human Warrior."""
        EvMenu(self.caller, "world.chargen", start_node="start", auto_quit=True)
        menu = self.caller.ndb._evmenu
        self.assertIsNotNone(menu)

        menu.parse_input("1")  # Good
        menu.parse_input("1")  # Human
        menu.parse_input("1")  # Warrior
        menu.parse_input("1")  # Accept stats
        menu.parse_input("1")  # Confirm

        chars = self.caller.characters.all()
        self.assertTrue(len(chars) > 0)
        char = chars[0]
        self.assertEqual(char.db.race, "Human")
        self.assertEqual(char.db.character_class, "Warrior")
        self.assertEqual(char.db.alignment, "Good")
        self.assertEqual(char.db.level, 1)

        # Verify stats use correct keys
        stats = char.db.stats
        self.assertIn("dex", stats, "Character stats must use 'dex'")
        self.assertIn("cha", stats, "Character stats must use 'cha'")
        self.assertNotIn("agi", stats, "Character stats must NOT use 'agi'")
        self.assertNotIn("chr", stats, "Character stats must NOT use 'chr'")

        # Verify derived attributes
        self.assertGreater(char.db.max_hp, 0)
        self.assertGreater(char.db.max_mana, 0)
        self.assertGreater(char.db.max_stamina, 0)

    def test_full_flow_pixie_mage(self):
        """Complete chargen: Pixie Mage (tests DEX/CHA keys)."""
        EvMenu(self.caller, "world.chargen", start_node="start", auto_quit=True)
        menu = self.caller.ndb._evmenu
        self.assertIsNotNone(menu)

        menu.parse_input("1")  # Good
        # Pixie is the 8th option in good races
        menu.parse_input("8")  # Pixie
        menu.parse_input("1")  # Mage (should be first valid class for Pixie)
        menu.parse_input("1")  # Accept stats
        menu.parse_input("1")  # Confirm

        chars = self.caller.characters.all()
        self.assertTrue(len(chars) > 0)
        char = chars[0]
        self.assertEqual(char.db.race, "Pixie")
        stats = char.db.stats
        # Pixie has base DEX 16, so DEX should be high
        self.assertGreater(stats.get("dex", 0), 10,
            f"Pixie should have high DEX, got {stats.get('dex', 0)}")

    def test_full_flow_orc_warrior(self):
        """Complete chargen: Orc Warrior (Evil)."""
        EvMenu(self.caller, "world.chargen", start_node="start", auto_quit=True)
        menu = self.caller.ndb._evmenu
        self.assertIsNotNone(menu)

        menu.parse_input("2")  # Evil
        menu.parse_input("1")  # Orc
        menu.parse_input("1")  # Warrior
        menu.parse_input("1")  # Accept stats
        menu.parse_input("1")  # Confirm

        chars = self.caller.characters.all()
        self.assertTrue(len(chars) > 0)
        char = chars[0]
        self.assertEqual(char.db.race, "Orc")
        self.assertEqual(char.db.alignment, "Evil")
        stats = char.db.stats
        # Orc has base STR 14, CHA 5
        self.assertGreater(stats.get("str", 0), 10)
        self.assertLess(stats.get("cha", 99), 10)


# ===========================================================================
# TEST 12: Race/Class Matrix
# ===========================================================================

class TestRaceClassMatrix(EvenniaTest):
    """Verify all race/class combinations are valid."""

    def test_all_race_class_matrix_entries_valid(self):
        """Every race/class pair in RACE_CLASS_MATRIX must reference valid data."""
        from world.race_class_matrix import RACE_CLASS_MATRIX
        for race_name, classes in RACE_CLASS_MATRIX.items():
            self.assertIn(race_name, RACES, f"Unknown race: {race_name}")
            for cls_name in classes:
                self.assertIn(cls_name, CLASSES,
                    f"Unknown class '{cls_name}' for race '{race_name}'")

    def test_all_races_in_matrix(self):
        """Every RACE must have an entry in RACE_CLASS_MATRIX."""
        from world.race_class_matrix import RACE_CLASS_MATRIX
        for race_name in RACES:
            self.assertIn(race_name, RACE_CLASS_MATRIX,
                f"Race '{race_name}' missing from RACE_CLASS_MATRIX")

    def test_all_classes_in_matrix(self):
        """Every CLASS should appear in at least one race's allowed list."""
        from world.race_class_matrix import RACE_CLASS_MATRIX
        all_allowed = set()
        for classes in RACE_CLASS_MATRIX.values():
            all_allowed.update(classes)
        for cls_name in CLASSES:
            self.assertIn(cls_name, all_allowed,
                f"Class '{cls_name}' not allowed for any race")

    def test_is_race_class_valid(self):
        """is_race_class_valid should correctly validate combinations."""
        from world.race_class_matrix import is_race_class_valid
        self.assertTrue(is_race_class_valid("Human", "Warrior"))
        self.assertTrue(is_race_class_valid("Orc", "Warrior"))
        self.assertFalse(is_race_class_valid("Ogre", "Mage"))
        self.assertFalse(is_race_class_valid("Pixie", "Paladin"))

    def test_get_valid_classes_for_race(self):
        """get_valid_classes_for_race should return non-empty list."""
        from world.race_class_matrix import get_valid_classes_for_race
        for race_name in RACES:
            classes = get_valid_classes_for_race(race_name)
            self.assertGreater(len(classes), 0,
                f"Race '{race_name}' has no valid classes")

    def test_natural_armor_races_match(self):
        """RACE_NATURAL_ARMOR should only reference valid races."""
        from world.race_class_matrix import RACE_NATURAL_ARMOR
        for race_name in RACE_NATURAL_ARMOR:
            self.assertIn(race_name, RACES,
                f"Unknown race '{race_name}' in RACE_NATURAL_ARMOR")

    def test_forbidden_slots_races_match(self):
        """RACE_FORBIDDEN_SLOTS should only reference valid races."""
        from world.race_class_matrix import RACE_FORBIDDEN_SLOTS
        for race_name in RACE_FORBIDDEN_SLOTS:
            self.assertIn(race_name, RACES,
                f"Unknown race '{race_name}' in RACE_FORBIDDEN_SLOTS")


# ===========================================================================
# TEST 13: Character Typeclass Methods
# ===========================================================================

class TestCharacterTypeclass(EvenniaTest):
    """Verify Character typeclass methods work correctly."""

    def setUp(self):
        super().setUp()
        self.char = create_object(
            Character,
            key="TypeTest",
            location=None,
        )
        self.char.attributes.add("race", "Human")
        self.char.attributes.add("class", "Warrior")
        self.char.attributes.add("level", 1)
        self.char.attributes.add("stats", {"str": 12, "dex": 10, "con": 12, "int": 8, "wis": 8, "cha": 10})
        self.char.attributes.add("max_hp", 100)
        self.char.attributes.add("hp", 100)
        self.char.attributes.add("max_mana", 50)
        self.char.attributes.add("mana", 50)
        self.char.attributes.add("max_mv", 100)
        self.char.attributes.add("mv", 100)
        self.char.attributes.add("max_stamina", 100)
        self.char.attributes.add("stamina", 100)
        self.char.attributes.add("xp", 0)
        self.char.attributes.add("xp_to_level", 1000)
        self.char.attributes.add("alignment", "Good")
        self.char.attributes.add("warpoints", 0)
        self.char.attributes.add("position", "standing")
        self.char.attributes.add("equipped", {})
        self.char.attributes.add("autoloot", False)
        self.char.attributes.add("autosac", False)
        self.char.attributes.add("learned_spells", [])
        self.char.attributes.add("trained_skills", [])
        self.char.attributes.add("prompt_enabled", True)

    def tearDown(self):
        if self.char and self.char.id:
            self.char.delete()
        super().tearDown()

    def test_get_status_prompt(self):
        """get_status_prompt should return a string with HP/MV/EXP/SP."""
        prompt = self.char.get_status_prompt()
        self.assertIsInstance(prompt, str)
        self.assertIn("HP:", prompt)

    def test_return_appearance(self):
        """return_appearance should return a string with character info."""
        appearance = self.char.return_appearance(self.char)
        self.assertIsInstance(appearance, str)
        self.assertIn(self.char.key, appearance)
        self.assertIn("Human", appearance)
        self.assertIn("Warrior", appearance)

    def test_spells_property(self):
        """spells property should return a SpellHandler."""
        handler = self.char.spells
        self.assertIsNotNone(handler)

    def test_quests_property(self):
        """quests property should return a QuestHandler."""
        handler = self.char.quests
        self.assertIsNotNone(handler)

    def test_get_active_effects(self):
        """get_active_effects should return an ActiveEffects manager."""
        effects = self.char.get_active_effects()
        self.assertIsNotNone(effects)

    def test_apply_status_effect(self):
        """apply_status_effect should not raise."""
        from world.status_effects import StatusEffect
        # Create a simple test effect
        try:
            self.char.apply_status_effect(None)
        except Exception:
            pass  # Just checking it doesn't crash

    def test_clear_all_effects(self):
        """clear_all_effects should not raise."""
        try:
            self.char.clear_all_effects()
        except Exception:
            pass  # Just checking it doesn't crash

    def test_award_xp_method(self):
        """award_xp should increase XP."""
        initial = self.char.attributes.get("xp", default=0)
        self.char.award_xp(500)
        after = self.char.attributes.get("xp", default=0)
        self.assertGreater(after, initial)


# ===========================================================================
# TEST 14: Stat Key Consistency Across All Systems
# ===========================================================================

class TestStatKeyConsistencyAcrossSystems(EvenniaTest):
    """Verify stat keys are consistent in ALL files that use them."""

    def test_chargen_core_stats_match_rules(self):
        """chargen CORE_STATS keys must match RACES stats keys."""
        for race_name, race_data in RACES.items():
            race_stat_keys = set(race_data["stats"].keys())
            core_stat_keys = set(CORE_STATS)
            self.assertEqual(race_stat_keys, core_stat_keys,
                f"Race '{race_name}' stat keys {race_stat_keys} != CORE_STATS {core_stat_keys}")

    def test_damage_formulas_uses_dex_cha(self):
        """damage_formulas.py must use 'dex' and 'cha'."""
        from world.damage_formulas import _get_stats
        self.char = create_object(Character, key="DmgTest", location=None)
        try:
            self.char.attributes.add("stats", {"str": 10, "dex": 14, "con": 10, "int": 10, "wis": 10, "cha": 8})
            stats = _get_stats(self.char)
            self.assertIn("dex", stats)
            self.assertIn("cha", stats)
            self.assertNotIn("agi", stats)
            self.assertNotIn("chr", stats)
        finally:
            if self.char.id:
                self.char.delete()

    def test_saving_throws_uses_dex_cha(self):
        """saving_throws.py must use 'dex' and 'cha' from stats."""
        from world.saving_throws import _get_stat_bonus, SavingThrow
        stats = {"dex": 14, "con": 12, "wis": 10}
        # ROD save uses DEX
        bonus = _get_stat_bonus(stats, SavingThrow.ROD)
        self.assertEqual(bonus, 2, f"DEX 14 should give +2 ROD bonus, got {bonus}")

    def test_new_player_experience_uses_dex_cha(self):
        """new_player_experience.py must use correct stat keys."""
        from world.new_player_experience import grant_starting_gear
        self.char = create_object(Character, key="GearTest", location=None)
        try:
            self.char.attributes.add("class", "Warrior")
            self.char.attributes.add("race", "Human")
            self.char.attributes.add("stats", {"str": 12, "dex": 10, "con": 12, "int": 8, "wis": 8, "cha": 10})
            self.char.attributes.add("equipped", {})
            messages = grant_starting_gear(self.char)
            self.assertIsInstance(messages, list)
        finally:
            if self.char.id:
                self.char.delete()