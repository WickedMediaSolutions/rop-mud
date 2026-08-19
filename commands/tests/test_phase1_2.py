"""
Unit tests for Phase 1.2 — Status Effects, Saving Throws & Damage Types

Tests cover:
  - Damage type classification and multipliers
  - Saving throw calculations (race, class, level, stat bonuses)
  - Status effect creation, stacking, and tick processing
  - SpellHandler integration with saves and damage types
  - NPC spell decision making
"""

import sys
import os
import unittest

# Ensure we can import world modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ===========================================================================
# Mock Character for testing
# ===========================================================================

class MockAttributes:
    """Simulates Evennia's attribute handler."""
    def __init__(self, data=None):
        self._data = data or {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def add(self, key, value):
        self._data[key] = value

    def set(self, key, value):
        self._data[key] = value

    def has(self, key):
        return key in self._data


class MockCharacter:
    """A minimal mock character for testing."""
    def __init__(self, name="TestChar", level=5, race="Human", char_class="Warrior",
                 stats=None, alignment="Good"):
        self.key = name
        self.id = 1
        self.attributes = MockAttributes({
            "level": level,
            "race": race,
            "class": char_class,
            "stats": stats or {"str": 12, "dex": 10, "con": 14, "int": 10, "wis": 12, "cha": 10},
            "alignment": alignment,
            "hp": 100,
            "max_hp": 100,
            "mana": 50,
            "max_mana": 50,
            "mv": 100,
            "max_mv": 100,
            "xp": 0,
            "xp_to_level": 1000,
            "warpoints": 0,
            "shield_amount": 0,
            "spell_cooldowns": {},
            "learned_spells": [],
            "prompt_enabled": True,
            "chargen_completed": True,
        })
        self.location = None
        self.ndb = type('ndb', (), {})()
        self.db = type('db', (), {})()

    def msg(self, text=None, prompt=None, **kwargs):
        pass


# ===========================================================================
# Test: Damage Types
# ===========================================================================

class TestDamageTypes(unittest.TestCase):

    def setUp(self):
        from world import damage_types
        self.dt = damage_types

    def test_classify_standard_types(self):
        self.assertEqual(self.dt.classify_damage_type("fire"), "fire")
        self.assertEqual(self.dt.classify_damage_type("cold"), "cold")
        self.assertEqual(self.dt.classify_damage_type("lightning"), "lightning")
        self.assertEqual(self.dt.classify_damage_type("acid"), "acid")
        self.assertEqual(self.dt.classify_damage_type("poison"), "poison")
        self.assertEqual(self.dt.classify_damage_type("holy"), "holy")
        self.assertEqual(self.dt.classify_damage_type("shadow"), "shadow")
        self.assertEqual(self.dt.classify_damage_type("arcane"), "arcane")

    def test_classify_aliases(self):
        self.assertEqual(self.dt.classify_damage_type("ice"), "cold")
        self.assertEqual(self.dt.classify_damage_type("frost"), "cold")
        self.assertEqual(self.dt.classify_damage_type("electric"), "lightning")
        self.assertEqual(self.dt.classify_damage_type("dark"), "shadow")
        self.assertEqual(self.dt.classify_damage_type("magic"), "arcane")

    def test_classify_physical_types(self):
        self.assertEqual(self.dt.classify_damage_type("slashing"), "slashing")
        self.assertEqual(self.dt.classify_damage_type("piercing"), "piercing")
        self.assertEqual(self.dt.classify_damage_type("bludgeoning"), "bludgeoning")

    def test_classify_unknown_type(self):
        self.assertEqual(self.dt.classify_damage_type("unknown_type"), "arcane")

    def test_get_damage_multiplier_normal(self):
        char = MockCharacter()
        mult = self.dt.get_damage_multiplier(char, "fire")
        self.assertEqual(mult, 1.0)

    def test_get_damage_multiplier_immune(self):
        char = MockCharacter()
        char.attributes.add("damage_immunities", {"fire"})
        mult = self.dt.get_damage_multiplier(char, "fire")
        self.assertEqual(mult, 0.0)

    def test_get_damage_multiplier_resistant(self):
        char = MockCharacter()
        char.attributes.add("damage_resistances", {"cold": "resistant"})
        mult = self.dt.get_damage_multiplier(char, "cold")
        self.assertEqual(mult, 0.5)

    def test_get_damage_multiplier_vulnerable(self):
        char = MockCharacter()
        char.attributes.add("damage_resistances", {"holy": "vulnerable"})
        mult = self.dt.get_damage_multiplier(char, "holy")
        self.assertEqual(mult, 1.5)

    def test_apply_damage_with_type(self):
        char = MockCharacter()
        char.attributes.add("damage_resistances", {"fire": "resistant"})
        result = self.dt.apply_damage_with_type(100, "fire", char)
        self.assertEqual(result, 50)

    def test_set_damage_resistance(self):
        char = MockCharacter()
        self.dt.set_damage_resistance(char, "lightning", "vulnerable")
        resistances = char.attributes.get("damage_resistances", {})
        self.assertEqual(resistances["lightning"], "vulnerable")

    def test_add_damage_immunity(self):
        char = MockCharacter()
        self.dt.add_damage_immunity(char, "poison")
        immunities = char.attributes.get("damage_immunities")
        self.assertIn("poison", immunities)


# ===========================================================================
# Test: Saving Throws
# ===========================================================================

class TestSavingThrows(unittest.TestCase):

    def setUp(self):
        from world import saving_throws
        self.st = saving_throws

    def test_get_base_save_level_1_human_warrior(self):
        char = MockCharacter(level=1, race="Human", char_class="Warrior")
        save = self.st.get_base_save(char, self.st.SavingThrow.POISON)
        # Base table: poison=14, human bonus=0, stat bonus: con=14 -> (14-10)//2=2
        # So save_value = 14 - 0 - 0 - 2 = 12
        self.assertEqual(save, 12)

    def test_get_base_save_dwarf_poison(self):
        char = MockCharacter(level=1, race="Dwarf", char_class="Warrior",
                             stats={"str": 12, "dex": 10, "con": 14, "int": 10, "wis": 12, "cha": 10})
        save = self.st.get_base_save(char, self.st.SavingThrow.POISON)
        # Base: 14, dwarf bonus: 2, stat: con=14->2
        # save = 14 - 2 - 0 - 2 = 10
        self.assertEqual(save, 10)

    def test_get_base_save_elf_spell(self):
        char = MockCharacter(level=1, race="Elf", char_class="Mage",
                             stats={"str": 10, "dex": 12, "con": 10, "int": 16, "wis": 14, "cha": 12})
        save = self.st.get_base_save(char, self.st.SavingThrow.SPELL)
        # Base: spell=17, elf bonus: 2, class mage: 0 (level//5=0), stat: wis=14->2
        # save = 17 - 2 - 0 - 2 = 13
        self.assertEqual(save, 13)

    def test_get_base_save_level_20_mage_spell(self):
        char = MockCharacter(level=20, race="Elf", char_class="Mage",
                             stats={"str": 10, "dex": 12, "con": 10, "int": 20, "wis": 20, "cha": 12})
        save = self.st.get_base_save(char, self.st.SavingThrow.SPELL)
        # Base: spell=8 (level 20), elf bonus: 2, class mage: level//5=4 * 2 = 8, stat: wis=20 -> 5
        # save = 8 - 2 - 8 - 5 = -7, clamped to 2
        self.assertEqual(save, 2)

    def test_calculate_dc(self):
        dc = self.st.calculate_dc(caster_level=10, caster_stat=18, spell_level=3)
        # DC = 10 + (10//2) + ((18-10)//2) + 3 = 10 + 5 + 4 + 3 = 22
        self.assertEqual(dc, 22)

    def test_roll_saving_throw_nat20(self):
        char = MockCharacter()
        # Force a nat 20 by patching random.randint
        import random
        original = random.randint
        random.randint = lambda a, b: 20
        passed, roll, dc = self.st.roll_saving_throw(char, self.st.SavingThrow.SPELL, dc=30)
        self.assertTrue(passed)
        self.assertEqual(roll, 20)
        random.randint = original

    def test_roll_saving_throw_nat1(self):
        char = MockCharacter()
        import random
        original = random.randint
        random.randint = lambda a, b: 1
        passed, roll, dc = self.st.roll_saving_throw(char, self.st.SavingThrow.SPELL, dc=5)
        self.assertFalse(passed)
        self.assertEqual(roll, 1)
        random.randint = original

    def test_save_bonus_display(self):
        char = MockCharacter()
        display = self.st.get_save_bonus_display(char)
        self.assertIn("Poison", display)
        self.assertIn("Death", display)
        self.assertIn("Petrification", display)
        self.assertIn("Rod", display)
        self.assertIn("Spell", display)


# ===========================================================================
# Test: Status Effects
# ===========================================================================

class TestStatusEffects(unittest.TestCase):

    def setUp(self):
        from world import status_effects
        self.se = status_effects

    def test_create_bleed_effect(self):
        effect = self.se.create_bleed_effect(damage=5, duration=15.0)
        self.assertEqual(effect.name, "Bleeding")
        self.assertEqual(effect.key, "bleed")
        self.assertEqual(effect.category, self.se.StatusEffectCategory.DOT)
        self.assertEqual(effect.slot, self.se.StatusEffectSlot.BLEED)
        self.assertEqual(effect.damage_per_tick, 5)
        self.assertEqual(effect.damage_type, "slashing")
        self.assertEqual(effect.duration, 15.0)
        self.assertGreater(effect.save_dc, 0)

    def test_create_poison_effect(self):
        effect = self.se.create_poison_effect(damage=8, duration=18.0)
        self.assertEqual(effect.name, "Poisoned")
        self.assertEqual(effect.damage_type, "poison")
        self.assertEqual(effect.save_type, "poison")

    def test_create_burn_effect(self):
        effect = self.se.create_burn_effect(damage=10, duration=12.0)
        self.assertEqual(effect.name, "Burning")
        self.assertEqual(effect.damage_type, "fire")
        self.assertTrue(effect.break_on_damage)
        self.assertGreater(effect.break_chance, 0)

    def test_create_curse_effect(self):
        effect = self.se.create_curse_effect(damage=6, duration=20.0)
        self.assertEqual(effect.name, "Cursed")
        self.assertEqual(effect.damage_type, "shadow")

    def test_create_stun_effect(self):
        effect = self.se.create_stun_effect(duration=6.0)
        self.assertEqual(effect.name, "Stunned")
        self.assertEqual(effect.category, self.se.StatusEffectCategory.MEZ)
        self.assertEqual(effect.slot, self.se.StatusEffectSlot.STUN)

    def test_create_root_effect(self):
        effect = self.se.create_root_effect(duration=8.0)
        self.assertEqual(effect.name, "Rooted")
        self.assertEqual(effect.slot, self.se.StatusEffectSlot.ROOT)
        self.assertTrue(effect.break_on_damage)

    def test_create_stat_debuff_effect(self):
        effect = self.se.create_stat_debuff_effect(stat="str", amount=5, duration=20.0)
        self.assertEqual(effect.name, "Impaired STR")
        self.assertEqual(effect.stat_affected, "str")
        self.assertEqual(effect.stat_amount, 5)

    def test_create_resist_debuff_effect(self):
        effect = self.se.create_resist_debuff_effect(resist_type="fire", amount=20, duration=15.0)
        self.assertEqual(effect.name, "Vulnerable to fire")
        self.assertEqual(effect.resist_type, "fire")

    def test_active_effects_apply_and_check(self):
        char = MockCharacter()
        effects = self.se.ActiveEffects(char)

        bleed = self.se.create_bleed_effect(damage=5, duration=15.0)
        applied, msg = effects.apply_effect(bleed)
        self.assertTrue(applied)
        self.assertTrue(effects.has_effect("bleed"))
        self.assertTrue(effects.has_effect_in_slot(self.se.StatusEffectSlot.BLEED))

    def test_active_effects_stun_blocks_act(self):
        char = MockCharacter()
        effects = self.se.ActiveEffects(char)

        stun = self.se.create_stun_effect(duration=6.0)
        effects.apply_effect(stun)
        self.assertTrue(effects.is_stunned())
        self.assertFalse(effects.can_act())

    def test_active_effects_root_blocks_move(self):
        char = MockCharacter()
        effects = self.se.ActiveEffects(char)

        root = self.se.create_root_effect(duration=8.0)
        effects.apply_effect(root)
        self.assertTrue(effects.is_rooted())
        self.assertFalse(effects.can_move())

    def test_active_effects_clear_all(self):
        char = MockCharacter()
        effects = self.se.ActiveEffects(char)

        effects.apply_effect(self.se.create_bleed_effect(damage=5, duration=15.0))
        effects.apply_effect(self.se.create_poison_effect(damage=8, duration=18.0))
        effects.apply_effect(self.se.create_stun_effect(duration=6.0))

        self.assertEqual(len(effects.get_effects()), 3)
        effects.clear_all()
        self.assertEqual(len(effects.get_effects()), 0)

    def test_stun_stacking_refreshes(self):
        char = MockCharacter()
        effects = self.se.ActiveEffects(char)

        stun1 = self.se.create_stun_effect(duration=6.0)
        stun2 = self.se.create_stun_effect(duration=10.0)

        effects.apply_effect(stun1)
        applied, _ = effects.apply_effect(stun2)

        self.assertTrue(applied)
        self.assertEqual(len(effects.get_effects()), 1)  # Only one stun

    def test_bleed_stacking_allows_multiple(self):
        char = MockCharacter()
        effects = self.se.ActiveEffects(char)

        effects.apply_effect(self.se.create_bleed_effect(damage=5, duration=15.0))
        effects.apply_effect(self.se.create_bleed_effect(damage=3, duration=10.0))

        bleeds = effects.get_effects(self.se.StatusEffectCategory.DOT)
        self.assertEqual(len(bleeds), 2)  # Bleeds stack

    def test_effect_display(self):
        char = MockCharacter()
        effects = self.se.ActiveEffects(char)

        effects.apply_effect(self.se.create_bleed_effect(damage=5, duration=15.0))
        effects.apply_effect(self.se.create_stun_effect(duration=6.0))

        display = effects.get_effect_display()
        self.assertIn("Bleeding", display)
        self.assertIn("Stunned", display)


# ===========================================================================
# Test: SpellHandler Integration
# ===========================================================================

class TestSpellHandlerIntegration(unittest.TestCase):

    def test_spell_damage_type_assigned(self):
        from world.spells import get_spell
        spell = get_spell("fireball")
        self.assertIsNotNone(spell)
        self.assertEqual(spell["effect"].get("damage_type"), "fire")

        spell = get_spell("lightningbolt")
        self.assertIsNotNone(spell)
        self.assertEqual(spell["effect"].get("damage_type"), "lightning")

        spell = get_spell("iceshard")
        self.assertIsNotNone(spell)
        self.assertEqual(spell["effect"].get("damage_type"), "cold")

        spell = get_spell("shadowbolt")
        self.assertIsNotNone(spell)
        self.assertEqual(spell["effect"].get("damage_type"), "shadow")

    def test_spell_save_type_assigned(self):
        from world.spells import get_spell
        spell = get_spell("paralyze")
        self.assertIsNotNone(spell)
        self.assertEqual(spell.get("save_type"), "petrification")
        self.assertTrue(spell.get("save_negates"))

        spell = get_spell("souldrain")
        self.assertIsNotNone(spell)
        self.assertEqual(spell.get("save_type"), "death")
        self.assertTrue(spell.get("save_negates"))


# ===========================================================================
# Test: NPC AI
# ===========================================================================

class TestNPCAI(unittest.TestCase):

    def test_get_npc_casting_stat(self):
        from world.mob_ai import get_npc_casting_stat, MobAIData
        char = MockCharacter()
        # No mob_ai
        stat = get_npc_casting_stat(char)
        self.assertEqual(stat, 12)

        # With mob_ai and mana
        ai = MobAIData(mana_pool=50, max_mana=100)
        char.attributes.add("mob_ai", ai)
        stat = get_npc_casting_stat(char)
        self.assertEqual(stat, 20)  # 10 + (100//10) = 20

    def test_npc_check_saving_throw(self):
        from world.mob_ai import npc_check_saving_throw
        char = MockCharacter()
        # Test with a very high DC - should fail
        saved = npc_check_saving_throw(char, "spell", 50)
        self.assertFalse(saved)

    def test_get_npc_damage_resistances(self):
        from world.mob_ai import get_npc_damage_resistances
        char = MockCharacter()
        char.attributes.add("damage_resistances", {"fire": "resistant"})
        resists = get_npc_damage_resistances(char)
        self.assertEqual(resists.get("fire"), "resistant")

    def test_get_npc_damage_immunities(self):
        from world.mob_ai import get_npc_damage_immunities
        char = MockCharacter()
        char.attributes.add("damage_immunities", {"poison", "fire"})
        immunities = get_npc_damage_immunities(char)
        self.assertIn("poison", immunities)
        self.assertIn("fire", immunities)


if __name__ == "__main__":
    unittest.main()