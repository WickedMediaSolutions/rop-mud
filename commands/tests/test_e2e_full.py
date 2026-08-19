#!/usr/bin/env python
"""Complete end-to-end integration test for all major subsystems."""
from __future__ import annotations
import sys, os, random, unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
import django; django.setup()


class MockAttributeHandler:
    def __init__(self, data=None):
        self._store = dict(data) if data else {}
    def get(self, key, default=None):
        return self._store.get(key, default)
    def add(self, key, value):
        self._store[key] = value
    def set(self, key, value):
        self._store[key] = value

class MockNDB:
    def __init__(self):
        self._store = {}
    def __getattr__(self, name):
        if name == "_store":
            raise AttributeError(name)
        if name not in self._store:
            raise AttributeError(name)
        return self._store[name]
    def __setattr__(self, name, value):
        if name == "_store":
            super().__setattr__(name, value)
        else:
            self._store[name] = value

class MockBase:
    _id_counter = 0
    def __init__(self, key="mock"):
        MockBase._id_counter += 1
        self.id = MockBase._id_counter
        self.key = key
        self.attributes = MockAttributeHandler()
        self.db = MagicMock()
        self.ndb = MockNDB()
        self.location = None
        self.has_account = False
        self.contents = []
        self.tags = MagicMock()
        self.tags.get.return_value = None
        self.locks = MagicMock()
        self.msg_contents = MagicMock()
        self.scripts = MagicMock()
        self.scripts.add = lambda cls: MagicMock(id=999)
    def msg(self, text=None, **kwargs): pass

    @property
    def spells(self):
        from world.spells import SpellHandler
        return SpellHandler(self)

    @property
    def quests(self):
        from world.quests import QuestHandler
        return QuestHandler(self)


def mk(**kw):
    c = MockBase(kw.get("key", "Test"))
    c.has_account = kw.get("has_account", True)
    a = c.attributes
    a.add("race", kw.get("race", "Human"))
    a.add("class", kw.get("cls", "Warrior"))
    a.add("level", kw.get("level", 1))
    a.add("alignment", kw.get("alignment", "Neutral"))
    a.add("hp", kw.get("hp", 100))
    a.add("max_hp", kw.get("max_hp", 100))
    a.add("mana", kw.get("mana", 50))
    a.add("max_mana", kw.get("max_mana", 50))
    a.add("mv", kw.get("mv", 100))
    a.add("max_mv", kw.get("max_mv", 100))
    a.add("xp", kw.get("xp", 0))
    a.add("xp_to_level", 1000)
    stats = kw.get("stats", {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
    a.add("stats", stats)
    a.add("money", kw.get("money", 0))
    a.add("alignment_points", 0)
    a.add("warpoints", 0)
    a.add("kills", 0)
    a.add("stamina", 100)
    a.add("max_stamina", 100)
    a.add("equipped", {})
    a.add("learned_spells", kw.get("learned_spells", []))
    a.add("position", "standing")
    a.add("autoloot", False)
    a.add("autosac", False)
    a.add("shield_amount", 0)
    a.add("spell_cooldowns", {})
    a.add("chargen_completed", True)
    a.add("prompt_enabled", True)
    for k, v in kw.items():
        if k not in ["key", "has_account", "race", "cls", "level", "alignment", "hp", "max_hp",
                      "mana", "max_mana", "mv", "max_mv", "xp", "stats", "money",
                      "learned_spells"]:
            a.add(k, v)
    return c


def mk_room(key="Room", safe_zone=False):
    r = MockBase(key)
    r.attributes.add("safe_zone", safe_zone)
    return r


def _reset():
    import world.tick_combat as tc
    tc.ENGAGEMENTS.clear()
    tc.COMBAT_SCRIPT_UID = None


# ===== TESTS =====

class TestMovement(unittest.TestCase):
    def setUp(self): _reset()
    def test_01_cmdmove_exists(self):
        from commands.movement import CmdMove
        self.assertTrue(hasattr(CmdMove, "func"))
    def test_02_move_cost_positive(self):
        from commands.movement import get_move_cost
        c = mk(key="Traveler", mv=100)
        self.assertGreater(get_move_cost(c), 0)


class TestCombat(unittest.TestCase):
    def setUp(self): _reset()

    def test_01_player_vs_mob_to_death(self):
        from world.tick_combat import CombatHandler, _execute_attack_round
        p = mk(key="Hero", level=10, hp=500, max_hp=500,
               stats={"str": 20, "dex": 16, "con": 16, "int": 10, "wis": 10, "cha": 10})
        m = mk(key="Goblin", has_account=False, hp=80, max_hp=80, level=3)
        room = mk_room("Cave")
        p.location = room
        m.location = room
        CombatHandler.start_combat(p, m)
        self.assertTrue(CombatHandler.is_in_combat(p))
        rounds = 0
        for _ in range(100):
            if not CombatHandler.is_in_combat(p):
                break
            _execute_attack_round(p, m)
            rounds += 1
            if m.attributes.get("hp") <= 0:
                break
            _execute_attack_round(m, p)
            rounds += 1
            if p.attributes.get("hp") <= 0:
                break
        self.assertGreater(rounds, 0)
        self.assertLess(rounds, 100)

    def test_02_npc_death_cleanup(self):
        from world.tick_combat import CombatHandler, ENGAGEMENTS, _handle_target_death
        a = mk(key="Killer", hp=100, max_hp=100)
        mob = mk(key="Mob", has_account=False, hp=5, max_hp=5)
        room = mk_room("Room")
        a.location = room
        mob.location = room
        CombatHandler.start_combat(a, mob)
        mob.attributes.add("hp", 0)
        _handle_target_death(a, mob)
        self.assertNotIn(mob.id, ENGAGEMENTS)

    def test_03_flee_works(self):
        from world.tick_combat import CombatHandler
        a = mk(key="Fleer", hp=100, max_hp=100, level=50,
               stats={"str": 10, "dex": 50, "con": 10, "int": 10, "wis": 10, "cha": 10})
        b = mk(key="B", hp=100, max_hp=100, level=1)
        room = mk_room("Room")
        a.location = room
        b.location = room
        CombatHandler.start_combat(a, b)
        self.assertTrue(CombatHandler.is_in_combat(a))
        orig = random.random
        try:
            random.random = lambda: 0.0
            CombatHandler.attempt_flee(a)
        finally:
            random.random = orig
        self.assertFalse(CombatHandler.is_in_combat(a))

    def test_04_get_target(self):
        from world.tick_combat import CombatHandler
        a = mk(key="A", hp=99999, max_hp=99999)
        b = mk(key="B", hp=99999, max_hp=99999)
        room = mk_room("Room")
        a.location = room
        b.location = room
        CombatHandler.start_combat(a, b)
        t = CombatHandler.get_target(a)
        self.assertIsNotNone(t)
        self.assertEqual(t.id, b.id)

    def test_05_player_unconscious_then_dead(self):
        from world.tick_combat import _handle_target_death
        from world.combat_state import CombatStateMachine, CombatState
        k = mk(key="Killer", hp=100, max_hp=100)
        v = mk(key="Victim", hp=99999, max_hp=99999)
        room = mk_room("Room")
        k.location = room
        v.location = room
        CombatStateMachine.set_state(v, CombatState.ENGAGING)
        CombatStateMachine.set_state(v, CombatState.FIGHTING)
        v.attributes.add("hp", 0)
        _handle_target_death(k, v)
        self.assertEqual(CombatStateMachine.get_state(v), CombatState.UNCONSCIOUS)
        CombatStateMachine.set_state(v, CombatState.UNCONSCIOUS)
        v.attributes.add("hp", 0)
        _handle_target_death(k, v)
        self.assertEqual(CombatStateMachine.get_state(v), CombatState.IDLE)


class TestEconomy(unittest.TestCase):
    def setUp(self): _reset()
    def test_01_money(self):
        c = mk(money=1000)
        self.assertEqual(c.attributes.get("money"), 1000)
    def test_02_currency(self):
        from world.shopkeeper import convert_currency
        r = convert_currency(1234)
        self.assertIn("gold", r.lower())
    def test_03_parse(self):
        from world.shopkeeper import parse_currency
        self.assertEqual(parse_currency("100"), 100)
    def test_04_carry(self):
        from world.encumbrance import get_carry_capacity
        w = mk(stats={"str": 5, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        s = mk(stats={"str": 18, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        self.assertGreater(get_carry_capacity(s), get_carry_capacity(w))
    def test_05_encumbrance_zero(self):
        from world.encumbrance import get_encumbrance_penalty
        c = mk()
        self.assertEqual(get_encumbrance_penalty(c), 0.0)
    def test_06_effective_stats(self):
        from world.encumbrance import get_effective_stats
        c = mk(stats={"str": 14, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10})
        s = get_effective_stats(c)
        for k in ["str", "dex", "con", "int", "wis", "cha"]:
            self.assertIn(k, s)


class TestGroups(unittest.TestCase):
    def setUp(self): _reset()
    def test_01_split_xp_no_crash(self):
        from commands.group import split_group_xp
        c = mk(key="Solo")
        try:
            split_group_xp(c, 100)
        except Exception as e:
            self.fail(str(e))
    def test_02_format_status(self):
        from commands.group import format_group_status
        c = mk(key="GL")
        self.assertIsInstance(format_group_status(c), str)


class TestMobAI(unittest.TestCase):
    def setUp(self): _reset()
    def test_01_aggro_returns_bool(self):
        from world.mob_ai import check_mob_aggro, MobDisposition, MobAIData
        mob = mk(key="Mob")
        ai = MobAIData(disposition=MobDisposition.AGGRESSIVE)
        mob.attributes.add("mob_ai", ai)
        mob.attributes.add("alignment", "Evil")
        mob.attributes.add("level", 5)
        player = mk(key="P", alignment="Good", level=1)
        self.assertIsInstance(check_mob_aggro(mob, player), bool)
    def test_02_passive_no_aggro(self):
        from world.mob_ai import check_mob_aggro, MobDisposition, MobAIData
        mob = mk(key="Cow")
        ai = MobAIData(disposition=MobDisposition.PASSIVE)
        mob.attributes.add("mob_ai", ai)
        self.assertFalse(check_mob_aggro(mob, mk()))
    def test_03_casting_stat(self):
        from world.mob_ai import get_npc_casting_stat, MobAIData
        mob = mk(key="Caster")
        ai = MobAIData(mana_pool=100, max_mana=100)
        mob.attributes.add("mob_ai", ai)
        self.assertGreater(get_npc_casting_stat(mob), 10)
    def test_04_same_faction_no_aggro(self):
        from world.mob_ai import check_mob_aggro, MobDisposition, MobAIData
        guard = mk(key="Guard", alignment="Good", level=10)
        ai = MobAIData(disposition=MobDisposition.GUARDIAN)
        guard.attributes.add("mob_ai", ai)
        cit = mk(key="Cit", alignment="Good", level=1)
        self.assertFalse(check_mob_aggro(guard, cit))


class TestStatusEffects(unittest.TestCase):
    def setUp(self): _reset()
    def test_01_bleed_apply(self):
        from world.status_effects import ActiveEffects, create_bleed_effect
        c = mk(hp=100, max_hp=100)
        effects = ActiveEffects(c)
        effects.apply_effect(create_bleed_effect(damage=5, duration=30.0))
        self.assertTrue(effects.has_effect("bleed"))
    def test_02_stun_blocks_act(self):
        from world.status_effects import ActiveEffects, create_stun_effect
        c = mk()
        e = ActiveEffects(c)
        e.apply_effect(create_stun_effect(duration=10.0))
        self.assertFalse(e.can_act())
    def test_03_root_blocks_move(self):
        from world.status_effects import ActiveEffects, create_root_effect
        c = mk()
        e = ActiveEffects(c)
        e.apply_effect(create_root_effect(duration=10.0))
        self.assertFalse(e.can_move())
        self.assertTrue(e.can_act())
    def test_04_poison_type(self):
        from world.status_effects import create_poison_effect, StatusEffectSlot
        ef = create_poison_effect(damage=8, duration=18.0)
        self.assertEqual(ef.name, "Poisoned")
        self.assertEqual(ef.slot, StatusEffectSlot.POISON)
    def test_05_bleeds_stack(self):
        from world.status_effects import ActiveEffects, create_bleed_effect, StatusEffectCategory
        c = mk(hp=500, max_hp=500)
        e = ActiveEffects(c)
        e.apply_effect(create_bleed_effect(damage=5, duration=15.0))
        e.apply_effect(create_bleed_effect(damage=3, duration=10.0))
        self.assertEqual(len(e.get_effects(StatusEffectCategory.DOT)), 2)
    def test_06_clear_all(self):
        from world.status_effects import ActiveEffects, create_bleed_effect, create_stun_effect
        c = mk(hp=500, max_hp=500)
        e = ActiveEffects(c)
        e.apply_effect(create_bleed_effect(damage=5, duration=15.0))
        e.apply_effect(create_stun_effect(duration=6.0))
        self.assertEqual(len(e.get_effects()), 2)
        e.clear_all()
        self.assertEqual(len(e.get_effects()), 0)


class TestSpells(unittest.TestCase):
    def setUp(self): _reset()
    def test_01_available_spells(self):
        from world.spells import SpellHandler
        m = mk(key="Mage", race="High Elf", cls="Mage", level=50, mana=500, max_mana=500,
               learned_spells=["lightningbolt", "shadowbolt", "fireball"],
               stats={"str": 10, "dex": 14, "con": 10, "int": 20, "wis": 16, "cha": 12})
        h = SpellHandler(m)
        self.assertGreater(len(h.available_spells()), 0)
    def test_02_warrior_no_cast(self):
        from world.spells import SpellHandler
        w = mk(key="War", cls="Warrior", level=80)
        can, reason = SpellHandler(w).can_cast("fireball")
        self.assertFalse(can)
        self.assertGreater(len(reason), 0)
    def test_03_mana_getter_setter(self):
        from world.spells import SpellHandler
        m = mk(mana=200, max_mana=200)
        h = SpellHandler(m)
        self.assertEqual(h.mana, 200)
        h.mana = 100
        self.assertEqual(h.mana, 100)
    def test_04_scaled_value(self):
        from world.spells import scaled_value
        self.assertEqual(scaled_value(10, 3, 5), 25)
    def test_05_spell_detail(self):
        from world.spells import format_spell_detail
        r = format_spell_detail("sparks")
        self.assertIsInstance(r, str)
        self.assertGreater(len(r), 0)
    def test_06_spells_by_level(self):
        from world.spells import get_spells_for_level
        spells = get_spells_for_level(1)
        self.assertIsInstance(spells, list)
        for s in spells:
            self.assertLessEqual(s["level"], 1)


class TestAlignment(unittest.TestCase):
    def setUp(self): _reset()
    def test_01_adjust(self):
        from world.alignment_system import AlignmentSystem
        c = mk()
        self.assertEqual(AlignmentSystem.adjust_alignment(c, 500), 500)
        self.assertEqual(AlignmentSystem.adjust_alignment(c, -300), 200)
    def test_02_clamp(self):
        from world.alignment_system import AlignmentSystem
        c = mk()
        self.assertEqual(AlignmentSystem.adjust_alignment(c, 5000), 1000)
        self.assertEqual(AlignmentSystem.adjust_alignment(c, -99999), -1000)
    def test_03_good_vs_evil(self):
        from world.alignment_system import AlignmentSystem
        c = mk()
        c.attributes.add("alignment_points", 800)
        self.assertEqual(AlignmentSystem.get_alignment(c), "Good")
        c.attributes.add("alignment_points", -800)
        self.assertEqual(AlignmentSystem.get_alignment(c), "Evil")
    def test_04_outlaw(self):
        from world.alignment_system import AlignmentSystem, is_outlaw
        c = mk()
        self.assertFalse(is_outlaw(c))
        AlignmentSystem.set_outlaw(c, 300)
        self.assertTrue(is_outlaw(c))
        AlignmentSystem.clear_outlaw(c)
        self.assertFalse(is_outlaw(c))


class TestQuests(unittest.TestCase):
    def setUp(self): _reset()
    def test_01_handler_type(self):
        from world.quests import QuestHandler
        self.assertIsInstance(mk().quests, QuestHandler)
    def test_02_report_kill(self):
        try:
            mk().quests.report_kill("Goblin Scout")
        except Exception as e:
            self.fail(str(e))
    def test_03_status(self):
        j, a = mk().quests.status()
        self.assertIsInstance(j, str)
        self.assertIsInstance(a, list)
    def test_04_completed(self):
        c = mk().quests.get_completed_count()
        self.assertIsInstance(c, int)
        self.assertGreaterEqual(c, 0)


class TestStats(unittest.TestCase):
    def setUp(self): _reset()
    def test_01_all_16_races(self):
        from world.rules import RACES
        for name, data in RACES.items():
            self.assertIn("stats", data)
            self.assertIn("start_room", data)
            for s in ["str", "dex", "con", "int", "wis", "cha"]:
                self.assertIn(s, data["stats"])
    def test_02_classes(self):
        from world.rules import CLASSES
        self.assertEqual(len(CLASSES), 10)
        for name, data in CLASSES.items():
            self.assertIn("hp_per_level", data)
            self.assertIn("mana_per_level", data)
    def test_03_xp(self):
        from world.rules import xp_to_level
        self.assertEqual(xp_to_level(1), 1000)
        self.assertEqual(xp_to_level(50), 50000)
    def test_04_bonuses(self):
        from world.rules import stats_on_level_up
        for s in ["str", "dex", "con", "int", "wis", "cha"]:
            self.assertEqual(stats_on_level_up().get(s), 1)
    def test_05_prompt_true(self):
        self.assertTrue(mk().attributes.get("prompt_enabled"))


class TestTHAC0(unittest.TestCase):
    def setUp(self): _reset()
    def test_01_thac0(self):
        from world.tick_combat import _thac0
        self.assertGreater(_thac0(mk(level=1)), _thac0(mk(level=30)))
    def test_02_ac(self):
        from world.tick_combat import _armor_class
        w = mk(stats={"str": 10, "dex": 1, "con": 1, "int": 10, "wis": 10, "cha": 10})
        s = mk(stats={"str": 10, "dex": 20, "con": 20, "int": 10, "wis": 10, "cha": 10})
        self.assertGreater(_armor_class(w), _armor_class(s))
    def test_03_hit_bounds(self):
        from world.tick_combat import _hit_roll
        god = mk(level=80, stats={"str": 10, "dex": 50, "con": 10, "int": 10, "wis": 10, "cha": 10})
        weak = mk(level=1, stats={"str": 10, "dex": 1, "con": 1, "int": 1, "wis": 1, "cha": 1})
        hits = sum(1 for _ in range(500) if _hit_roll(god, weak))
        self.assertLess(hits, 499)
        hits_rev = sum(1 for _ in range(500) if _hit_roll(weak, god))
        self.assertGreater(hits_rev, 0)
    def test_04_weapon_dmg(self):
        from world.tick_combat import _weapon_damage
        self.assertGreaterEqual(_weapon_damage(mk()), 1)
    def test_05_flee_chance(self):
        from world.tick_combat import _flee_chance
        c = _flee_chance(mk(level=1), mk(level=50))
        self.assertGreaterEqual(c, 0.10)
        self.assertLessEqual(c, 0.90)
    def test_06_stat_helpers(self):
        from world.tick_combat import _stat, _level, _alive
        c = mk()
        self.assertEqual(_stat(c, "nonexistent", 42), 42)
        self.assertEqual(_level(c), 1)
        self.assertTrue(_alive(c))
        c.attributes.add("hp", 0)
        self.assertFalse(_alive(c))


if __name__ == "__main__":
    unittest.main(verbosity=2)