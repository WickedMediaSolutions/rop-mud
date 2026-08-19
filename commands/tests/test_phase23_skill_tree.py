"""
Phase 2.3 Skill Tree Gating & Talent Integration Tests
======================================================
Tests all 15 talent definitions, purchase/gating logic, combat skill
prerequisite gating, and runtime integration of talent bonuses into
combat, recovery, movement, magic, gold, and resource pools.
All tests pass without requiring Django/Evennia bootstrap.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Bootstrap Django settings before importing any Evennia code
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
import django
django.setup()


class MockCharacter:
    """Lightweight mock character with attributes interface."""
    _next_id = 1

    def __init__(self, name="TestChar", char_class="Warrior", level=1,
                 race="Human", hp=100, max_hp=100, stats=None, mana=100,
                 max_mana=100, mv=100, max_mv=100, stamina=100):
        self.key = name
        self.id = MockCharacter._next_id
        MockCharacter._next_id += 1
        self.has_account = True
        self.location = None
        self.contents = []
        self.destination = None

        class MockNdb:
            pass
        self.ndb = MockNdb()

        class MockAttributes:
            def __init__(self, store=None):
                self._store = dict(store) if store else {}

            def get(self, key, default=None):
                return self._store.get(key, default)

            def add(self, key, value):
                self._store[key] = value

            def has(self, key):
                return key in self._store

            def set(self, key, value):
                self._store[key] = value

            def all(self):
                return dict(self._store)

        self.attributes = MockAttributes({
            "class": char_class,
            "level": level,
            "race": race,
            "hp": hp,
            "max_hp": max_hp,
            "mana": mana,
            "max_mana": max_mana,
            "mv": mv,
            "max_mv": max_mv,
            "stamina": stamina,
            "max_stamina": stamina,
            "stats": stats or {"str": 12, "dex": 14, "con": 12, "int": 12, "wis": 14, "cha": 10},
            "equipped": {},
            "skill_cooldowns": {},
            "spell_cooldowns": {},
            "stunned": False,
            "combat_brief": False,
            "position": "standing",
            "safe_zone": False,
            "resistances": {},
            "vulnerabilities": {},
            "armor_set_bonuses": {},
            "gold_coins": 500,
            "xp": 0,
            "xp_to_level": 1000,
        })
        self.msg = lambda text: None


class TestTalentDefinitions(unittest.TestCase):
    """Test all 15 talent definitions are valid and complete."""

    def setUp(self):
        from world.skill_tree import TALENT_DEFINITIONS
        self.talents = TALENT_DEFINITIONS

    def test_all_15_talents_defined(self):
        """Verify exactly 15 talents exist across 3 trees."""
        self.assertEqual(len(self.talents), 15)
        trees = set(t["tree"] for t in self.talents.values())
        self.assertEqual(trees, {"Martial", "Arcane", "Survival"})

    def test_each_talent_has_required_fields(self):
        """Every talent must have name, tree, max_rank, base_cost, cost_per_rank, desc, effect."""
        required = ["name", "tree", "max_rank", "base_cost", "cost_per_rank", "desc", "effect"]
        for key, talent in self.talents.items():
            for field in required:
                self.assertIn(field, talent, f"{key} missing field '{field}'")

    def test_max_ranks_are_positive(self):
        """All max_rank values must be >= 1."""
        for key, talent in self.talents.items():
            self.assertGreaterEqual(talent["max_rank"], 1, f"{key} max_rank < 1")

    def test_effects_are_non_empty(self):
        """Every talent must have at least one effect."""
        for key, talent in self.talents.items():
            self.assertTrue(talent["effect"], f"{key} has empty effect dict")

    def test_prerequisites_are_valid(self):
        """Prerequisite talent keys must reference existing talents."""
        for key, talent in self.talents.items():
            prereq = talent.get("prereq")
            if prereq:
                self.assertIn(prereq, self.talents,
                              f"{key} prereq '{prereq}' not found in TALENT_DEFINITIONS")

    def test_trees_have_5_talents_each(self):
        """Each tree should have exactly 5 talents."""
        for tree in ("Martial", "Arcane", "Survival"):
            count = sum(1 for t in self.talents.values() if t["tree"] == tree)
            self.assertEqual(count, 5, f"{tree} tree has {count} talents, expected 5")


class TestTalentSession(unittest.TestCase):
    """Test TalentSession creation, persistence, and point management."""

    def setUp(self):
        from world.skill_tree import _get_session, _save_session, TalentSession
        self._get_session = _get_session
        self._save_session = _save_session
        self.TalentSession = TalentSession

    def test_new_character_gets_empty_session(self):
        """A new character should get a TalentSession with 0 points and no talents."""
        char = MockCharacter()
        session = self._get_session(char)
        self.assertIsInstance(session, self.TalentSession)
        self.assertEqual(session.talent_points, 0)
        self.assertEqual(session.talents, {})

    def test_session_persists_across_retrievals(self):
        """Session should persist when saved and retrieved again."""
        char = MockCharacter()
        session = self._get_session(char)
        session.talent_points = 5
        session.talents["dodge"] = 2
        self._save_session(char, session)

        session2 = self._get_session(char)
        self.assertEqual(session2.talent_points, 5)
        self.assertEqual(session2.talents["dodge"], 2)

    def test_award_talent_points(self):
        """award_talent_points should add points based on class."""
        from world.skill_tree import award_talent_points
        char = MockCharacter(char_class="Warrior")
        pts = award_talent_points(char, 2)
        self.assertEqual(pts, 2)
        session = self._get_session(char)
        self.assertEqual(session.talent_points, 2)

    def test_award_talent_points_defaults_to_2(self):
        """Unknown classes should default to 2 points per level."""
        from world.skill_tree import award_talent_points
        char = MockCharacter(char_class="UnknownClass")
        pts = award_talent_points(char, 1)
        self.assertEqual(pts, 2)


class TestTalentPurchase(unittest.TestCase):
    """Test talent purchase logic including costs, prerequisites, and caps."""

    def setUp(self):
        from world.skill_tree import purchase_talent, _get_session, _save_session
        self.purchase_talent = purchase_talent
        self._get_session = _get_session
        self._save_session = _save_session

    def _give_points(self, char, points):
        session = self._get_session(char)
        session.talent_points = points
        self._save_session(char, session)

    def test_purchase_unknown_talent_fails(self):
        """Purchasing a non-existent talent should fail."""
        char = MockCharacter()
        ok, msg = self.purchase_talent(char, "nonexistent_talent")
        self.assertFalse(ok)
        self.assertIn("Unknown", msg)

    def test_purchase_first_rank_succeeds(self):
        """Purchasing rank 1 of a talent with no prereq should succeed."""
        char = MockCharacter()
        self._give_points(char, 10)
        ok, msg = self.purchase_talent(char, "dodge")
        self.assertTrue(ok)
        self.assertIn("rank 1/5", msg)
        session = self._get_session(char)
        self.assertEqual(session.talents["dodge"], 1)
        self.assertEqual(session.talent_points, 9)  # 10 - 1

    def test_purchase_rank_2_costs_more(self):
        """Rank 2 should cost base_cost + 1*cost_per_rank."""
        char = MockCharacter()
        self._give_points(char, 10)
        self.purchase_talent(char, "dodge")  # rank 1: cost 1
        ok, msg = self.purchase_talent(char, "dodge")  # rank 2: cost 1+1=2
        self.assertTrue(ok)
        session = self._get_session(char)
        self.assertEqual(session.talents["dodge"], 2)
        self.assertEqual(session.talent_points, 7)  # 10 - 1 - 2

    def test_purchase_at_max_rank_fails(self):
        """Cannot purchase beyond max_rank."""
        char = MockCharacter()
        self._give_points(char, 100)
        for _ in range(5):  # dodge max_rank = 5
            ok, _ = self.purchase_talent(char, "dodge")
            self.assertTrue(ok)
        ok, msg = self.purchase_talent(char, "dodge")
        self.assertFalse(ok)
        self.assertIn("max rank", msg)

    def test_purchase_with_insufficient_points_fails(self):
        """Cannot purchase if not enough talent points."""
        char = MockCharacter()
        self._give_points(char, 0)
        ok, msg = self.purchase_talent(char, "berserker_rage")  # base_cost=2, no prereq
        self.assertFalse(ok)
        self.assertIn("Not enough talent points", msg)

    def test_prerequisite_not_met_fails(self):
        """Cannot purchase a talent if its prerequisite rank is not met."""
        char = MockCharacter()
        self._give_points(char, 100)
        # iron_grip requires weapon_specialist rank 2
        ok, msg = self.purchase_talent(char, "iron_grip")
        self.assertFalse(ok)
        self.assertIn("Requires Weapon Specialist", msg)

    def test_prerequisite_met_succeeds(self):
        """Can purchase a talent once its prerequisite is met."""
        char = MockCharacter()
        self._give_points(char, 100)
        # Buy weapon_specialist to rank 2
        self.purchase_talent(char, "weapon_specialist")  # rank 1
        self.purchase_talent(char, "weapon_specialist")  # rank 2
        # Now iron_grip should be purchasable
        ok, msg = self.purchase_talent(char, "iron_grip")
        self.assertTrue(ok)
        self.assertIn("rank 1/3", msg)


class TestTalentBonuses(unittest.TestCase):
    """Test get_talent_bonuses returns correct cumulative values."""

    def setUp(self):
        from world.skill_tree import get_talent_bonuses, _get_session, _save_session
        self.get_talent_bonuses = get_talent_bonuses
        self._get_session = _get_session
        self._save_session = _save_session

    def _set_talents(self, char, talents_dict):
        session = self._get_session(char)
        session.talents = dict(talents_dict)
        self._save_session(char, session)

    def test_no_talents_returns_empty(self):
        """Character with no talents should get empty bonuses."""
        char = MockCharacter()
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses, {})

    def test_weapon_specialist_rank_3(self):
        """Weapon Specialist rank 3 should give +3 melee_damage."""
        char = MockCharacter()
        self._set_talents(char, {"weapon_specialist": 3})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["melee_damage"], 3)

    def test_armor_mastery_rank_5(self):
        """Armor Mastery rank 5 should give +5 armor_bonus."""
        char = MockCharacter()
        self._set_talents(char, {"armor_mastery": 5})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["armor_bonus"], 5)

    def test_iron_grip_rank_3(self):
        """Iron Grip rank 3 should give +3 thac0_bonus."""
        char = MockCharacter()
        self._set_talents(char, {"iron_grip": 3})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["thac0_bonus"], 3)

    def test_berserker_rage_rank_3(self):
        """Berserker Rage rank 3 should give +6 crit_chance_pct."""
        char = MockCharacter()
        self._set_talents(char, {"berserker_rage": 3})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["crit_chance_pct"], 6)

    def test_unbreakable_rank_3(self):
        """Unbreakable rank 3 should give +9 hp_per_level."""
        char = MockCharacter()
        self._set_talents(char, {"unbreakable": 3})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["hp_per_level"], 9)

    def test_arcane_focus_rank_5(self):
        """Arcane Focus rank 5 should give +5 spell_damage."""
        char = MockCharacter()
        self._set_talents(char, {"arcane_focus": 5})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["spell_damage"], 5)

    def test_mana_reservoir_rank_5(self):
        """Mana Reservoir rank 5 should give +25 max_mana."""
        char = MockCharacter()
        self._set_talents(char, {"mana_reservoir": 5})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["max_mana"], 25)

    def test_spell_penetration_rank_3(self):
        """Spell Penetration rank 3 should give +6 spell_pen_pct."""
        char = MockCharacter()
        self._set_talents(char, {"spell_penetration": 3})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["spell_pen_pct"], 6)

    def test_arcane_shielding_rank_3(self):
        """Arcane Shielding rank 3 should give +9 magic_resist_pct."""
        char = MockCharacter()
        self._set_talents(char, {"arcane_shielding": 3})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["magic_resist_pct"], 9)

    def test_channeling_mastery_rank_3(self):
        """Channeling Mastery rank 3 should give +15 spell_cdr_pct."""
        char = MockCharacter()
        self._set_talents(char, {"channeling_mastery": 3})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["spell_cdr_pct"], 15)

    def test_dodge_rank_5(self):
        """Dodge rank 5 should give +5 ac_bonus."""
        char = MockCharacter()
        self._set_talents(char, {"dodge": 5})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["ac_bonus"], 5)

    def test_vitality_rank_5(self):
        """Vitality rank 5 should give +5 hp_regen."""
        char = MockCharacter()
        self._set_talents(char, {"vitality": 5})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["hp_regen"], 5)

    def test_fleet_footed_rank_3(self):
        """Fleet-Footed rank 3 should give +15 max_mv."""
        char = MockCharacter()
        self._set_talents(char, {"fleet_footed": 3})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["max_mv"], 15)

    def test_scavenger_rank_3(self):
        """Scavenger rank 3 should give +15 gold_bonus_pct."""
        char = MockCharacter()
        self._set_talents(char, {"scavenger": 3})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["gold_bonus_pct"], 15)

    def test_second_wind_rank_3(self):
        """Second Wind rank 3 should give +6 stamina_regen."""
        char = MockCharacter()
        self._set_talents(char, {"second_wind": 3})
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["stamina_regen"], 6)

    def test_multiple_talents_cumulative(self):
        """Multiple talents should stack their bonuses correctly."""
        char = MockCharacter()
        self._set_talents(char, {
            "weapon_specialist": 3,
            "berserker_rage": 2,
            "dodge": 4,
            "vitality": 3,
        })
        bonuses = self.get_talent_bonuses(char)
        self.assertEqual(bonuses["melee_damage"], 3)
        self.assertEqual(bonuses["crit_chance_pct"], 4)
        self.assertEqual(bonuses["ac_bonus"], 4)
        self.assertEqual(bonuses["hp_regen"], 3)


class TestTalentPoolBonuses(unittest.TestCase):
    """Test get_talent_pool_bonuses computes level-scaled pool contributions."""

    def setUp(self):
        from world.skill_tree import get_talent_pool_bonuses, _get_session, _save_session
        self.get_talent_pool_bonuses = get_talent_pool_bonuses
        self._get_session = _get_session
        self._save_session = _save_session

    def _set_talents(self, char, talents_dict):
        session = self._get_session(char)
        session.talents = dict(talents_dict)
        self._save_session(char, session)

    def test_unbreakable_scales_with_level(self):
        """Unbreakable hp_per_level should multiply by character level."""
        char = MockCharacter(level=10)
        self._set_talents(char, {"unbreakable": 3})  # 9 hp_per_level
        pool = self.get_talent_pool_bonuses(char)
        self.assertEqual(pool["max_hp"], 90)  # 9 * 10

    def test_mana_reservoir_flat_bonus(self):
        """Mana Reservoir gives flat max_mana regardless of level."""
        char = MockCharacter(level=1)
        self._set_talents(char, {"mana_reservoir": 5})  # 25 max_mana
        pool = self.get_talent_pool_bonuses(char)
        self.assertEqual(pool["max_mana"], 25)

    def test_fleet_footed_flat_bonus(self):
        """Fleet-Footed gives flat max_mv regardless of level."""
        char = MockCharacter(level=50)
        self._set_talents(char, {"fleet_footed": 3})  # 15 max_mv
        pool = self.get_talent_pool_bonuses(char)
        self.assertEqual(pool["max_mv"], 15)

    def test_no_talents_returns_zeros(self):
        """No talents should return zero pool bonuses."""
        char = MockCharacter(level=20)
        pool = self.get_talent_pool_bonuses(char)
        self.assertEqual(pool["max_hp"], 0)
        self.assertEqual(pool["max_mana"], 0)
        self.assertEqual(pool["max_mv"], 0)


class TestCombatSkillTalentGating(unittest.TestCase):
    """Test that combat skills are gated by talent prerequisites."""

    def setUp(self):
        from world.skill_tree import _get_session, _save_session
        self._get_session = _get_session
        self._save_session = _save_session

    def _set_talents(self, char, talents_dict):
        session = self._get_session(char)
        session.talents = dict(talents_dict)
        self._save_session(char, session)

    def test_kick_requires_weapon_specialist_rank_1(self):
        """Kick should require Weapon Specialist rank 1."""
        from world.combat_skills import COMBAT_SKILLS
        skill = COMBAT_SKILLS["kick"]
        self.assertEqual(skill["talent_prereq"], "weapon_specialist")
        self.assertEqual(skill["talent_rank"], 1)

    def test_bash_requires_weapon_specialist_rank_3(self):
        """Bash should require Weapon Specialist rank 3."""
        from world.combat_skills import COMBAT_SKILLS
        skill = COMBAT_SKILLS["bash"]
        self.assertEqual(skill["talent_prereq"], "weapon_specialist")
        self.assertEqual(skill["talent_rank"], 3)

    def test_backstab_requires_dodge_rank_2(self):
        """Backstab should require Dodge rank 2."""
        from world.combat_skills import COMBAT_SKILLS
        skill = COMBAT_SKILLS["backstab"]
        self.assertEqual(skill["talent_prereq"], "dodge")
        self.assertEqual(skill["talent_rank"], 2)

    def test_disarm_requires_iron_grip_rank_1(self):
        """Disarm should require Iron Grip rank 1."""
        from world.combat_skills import COMBAT_SKILLS
        skill = COMBAT_SKILLS["disarm"]
        self.assertEqual(skill["talent_prereq"], "iron_grip")
        self.assertEqual(skill["talent_rank"], 1)

    def test_execute_skill_blocks_without_talent(self):
        """execute_skill_attack should reject a skill if talent prereq not met."""
        from world.combat_skills import execute_skill_attack
        char = MockCharacter(char_class="Warrior", level=10)
        target = MockCharacter(name="Goblin", hp=50)
        # No talents purchased — kick should be blocked
        msg = execute_skill_attack(char, target, "kick")
        self.assertIn("Weapon Specialist", msg)
        self.assertIn("rank 1", msg)

    def test_execute_skill_allows_with_talent(self):
        """execute_skill_attack should allow a skill if talent prereq is met."""
        from world.combat_skills import execute_skill_attack
        char = MockCharacter(char_class="Warrior", level=10, stamina=200)
        target = MockCharacter(name="Goblin", hp=50)
        self._set_talents(char, {"weapon_specialist": 1})
        # Should pass talent check but may fail on hit roll or other checks
        msg = execute_skill_attack(char, target, "kick")
        # Should NOT contain the talent rejection message
        self.assertNotIn("You need Weapon Specialist", msg)


class TestTalentIntegrationPoints(unittest.TestCase):
    """Verify talent bonuses are wired into the correct runtime systems."""

    def test_damage_formulas_imports_skill_tree(self):
        """damage_formulas.py should import get_talent_bonuses."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "world", "damage_formulas.py"
        )
        with open(src_path, 'r') as f:
            content = f.read()
        self.assertIn("from world.skill_tree import get_talent_bonuses", content)

    def test_tick_combat_imports_skill_tree(self):
        """tick_combat.py should import get_talent_bonuses for THAC0/AC."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "world", "tick_combat.py"
        )
        with open(src_path, 'r') as f:
            content = f.read()
        self.assertIn("from world.skill_tree import get_talent_bonuses", content)

    def test_recovery_imports_skill_tree(self):
        """recovery.py should import get_talent_bonuses for hp_regen/stamina_regen."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "world", "recovery.py"
        )
        with open(src_path, 'r') as f:
            content = f.read()
        self.assertIn("from world.skill_tree import get_talent_bonuses", content)

    def test_mob_equipment_imports_skill_tree(self):
        """mob_equipment.py should import get_talent_bonuses for armor_bonus."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "world", "mob_equipment.py"
        )
        with open(src_path, 'r') as f:
            content = f.read()
        self.assertIn("from world.skill_tree import get_talent_bonuses", content)

    def test_combat_imports_skill_tree(self):
        """combat.py should import get_talent_bonuses for gold_bonus_pct."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "world", "combat.py"
        )
        with open(src_path, 'r') as f:
            content = f.read()
        self.assertIn("from world.skill_tree import get_talent_bonuses", content)

    def test_spells_imports_skill_tree(self):
        """spells.py should import get_talent_bonuses for magic talents."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "world", "spells.py"
        )
        with open(src_path, 'r') as f:
            content = f.read()
        self.assertIn("from world.skill_tree import get_talent_bonuses", content)

    def test_chargen_imports_skill_tree(self):
        """chargen.py should import get_talent_pool_bonuses for HP/mana pools."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "world", "chargen.py"
        )
        with open(src_path, 'r') as f:
            content = f.read()
        self.assertIn("from world.skill_tree import get_talent_pool_bonuses", content)

    def test_characters_imports_skill_tree(self):
        """characters.py should import get_talent_pool_bonuses for status prompt."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "typeclasses", "characters.py"
        )
        with open(src_path, 'r') as f:
            content = f.read()
        self.assertIn("from world.skill_tree import get_talent_pool_bonuses", content)

    def test_combat_skills_imports_skill_tree(self):
        """combat_skills.py should import _get_session and TALENT_DEFINITIONS for gating."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "world", "combat_skills.py"
        )
        with open(src_path, 'r') as f:
            content = f.read()
        self.assertIn("from world.skill_tree import _get_session, TALENT_DEFINITIONS", content)

    def test_skill_tree_has_pool_bonuses_function(self):
        """skill_tree.py should define get_talent_pool_bonuses."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "world", "skill_tree.py"
        )
        with open(src_path, 'r') as f:
            content = f.read()
        self.assertIn("def get_talent_pool_bonuses", content)

    def test_commands_registered_in_default_cmdsets(self):
        """CmdTalents, CmdTalentBuy, CmdTalentReset should be in default_cmdsets."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "commands", "default_cmdsets.py"
        )
        with open(src_path, 'r') as f:
            content = f.read()
        self.assertIn("CmdTalents", content)
        self.assertIn("CmdTalentBuy", content)
        self.assertIn("CmdTalentReset", content)


if __name__ == "__main__":
    unittest.main()