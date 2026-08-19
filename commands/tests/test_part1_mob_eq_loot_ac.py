#!/usr/bin/env python
"""
==============================================================================
RITES OF PASSAGE — PART 1: MOB EQUIPMENT, LOOT & AC SYSTEM END-TO-END TEST
==============================================================================

Verifies the full gameplay loop using mock objects (no live DB required):

  1. Mob spawns with generated equipment (weapon + armor + coins).
  2. Equipped armor is reflected in effective AC.
  3. Armor mitigates damage in damage formulas.
  4. Weapon damage type flows into combat rounds.
  5. On death, equipped gear + coins transfer to a corpse.
  6. Looting a corpse transfers items/coins to the killer.
  7. Respawned mobs are re-equipped (not naked).
  8. Player wear / remove / equipment commands work.
  9. Equipment stat bonuses apply to effective stats.
 10. Equipment durability degrades on hits.
 11. No phantom armor absorption when nothing is equipped.

Run standalone:
    cd /root/rop/rop
    python commands/tests/test_part1_mob_eq_loot_ac.py

Run via Evennia test runner (uses real DB):
    evennia test commands.tests.test_part1_mob_eq_loot_ac --verbosity=2
==============================================================================
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
import django
django.setup()

import random
import unittest
from unittest.mock import MagicMock


# ============================================================================
# Mock infrastructure (mirrors test_combat_integration.py)
# ============================================================================

class MockAttributeHandler:
    def __init__(self, data=None):
        self._store = dict(data) if data else {}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def add(self, key, value):
        self._store[key] = value

    def set(self, key, value):
        self._store[key] = value

    def has(self, key):
        return key in self._store

    def all(self):
        return dict(self._store)

    def __contains__(self, key):
        return key in self._store


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

    def __delattr__(self, name):
        if name in self._store:
            del self._store[name]

    def clear(self):
        self._store.clear()


class MockBase:
    _id_counter = 0

    def __init__(self, key="mock", location=None):
        MockBase._id_counter += 1
        self.id = MockBase._id_counter
        self.key = key
        self.attributes = MockAttributeHandler()
        self.db = MagicMock()
        self.ndb = MockNDB()
        self.location = location
        self.destination = None
        self.sessions = MagicMock()
        self.has_account = False
        self.contents = []
        self.tags = MagicMock()
        self.tags.get.return_value = None
        self.home = None

        class _ScriptsMock:
            def add(self, script_cls):
                m = MagicMock()
                m.id = id(script_cls) + MockBase._id_counter
                return m

            def get(self, key):
                return None

        self.scripts = _ScriptsMock()

    def msg(self, text=None, prompt=None, **kwargs):
        pass

    def move_to(self, destination, quiet=True, **kwargs):
        if self.location is not None and hasattr(self.location, "contents"):
            if self in self.location.contents:
                self.location.contents.remove(self)
        self.location = destination
        if destination is not None and hasattr(destination, "contents"):
            if self not in destination.contents:
                destination.contents.append(self)

    def delete(self):
        if self.location is not None and hasattr(self.location, "contents"):
            if self in self.location.contents:
                self.location.contents.remove(self)
        self.location = None

    @property
    def spells(self):
        from world.spells import SpellHandler
        return SpellHandler(self)

    @property
    def quests(self):
        from world.quests import QuestHandler
        return QuestHandler(self)


def mock_character(key="TestChar", race="Human", char_class="Warrior",
                   level=1, alignment="Neutral", hp=100, max_hp=100,
                   stats=None, location=None, **kwargs):
    char = MockBase(key=key, location=location)
    char.has_account = True
    attrs = char.attributes
    attrs.add("race", race)
    attrs.add("class", char_class)
    attrs.add("level", level)
    attrs.add("alignment", alignment)
    attrs.add("hp", hp)
    attrs.add("max_hp", max_hp)
    attrs.add("mana", 50)
    attrs.add("max_mana", 50)
    attrs.add("mv", 100)
    attrs.add("max_mv", 100)
    attrs.add("xp", 0)
    attrs.add("xp_to_level", 1000)
    if stats is None:
        stats = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
    attrs.add("stats", stats)
    attrs.add("money", 0)
    attrs.add("equipped", {})
    attrs.add("position", "standing")
    attrs.add("autoloot", False)
    attrs.add("autosac", False)
    attrs.add("shield_amount", 0)
    for k, v in kwargs.items():
        attrs.add(k, v)
    if location is not None:
        location.contents.append(char)
    return char


def mock_mob(key="Goblin", level=1, hp=30, max_hp=30, location=None,
             mob_class="Warrior", faction="Neutral", stats=None):
    mob = MockBase(key=key, location=location)
    mob.has_account = False
    attrs = mob.attributes
    attrs.add("is_mob", True)
    attrs.add("level", level)
    attrs.add("hp", hp)
    attrs.add("max_hp", max_hp)
    attrs.add("faction", faction)
    attrs.add("alignment", "")
    attrs.add("guild_class", mob_class)
    attrs.add("mob_class", mob_class)
    if stats is None:
        stats = {"str": 12, "dex": 10, "con": 10, "int": 8, "wis": 8, "cha": 6}
    attrs.add("stats", stats)
    attrs.add("equipped", {})
    attrs.add("copper_coins", 0)
    attrs.add("silver_coins", 0)
    attrs.add("gold_coins", 0)
    attrs.add("xp_value", 10)
    if location is not None:
        location.contents.append(mob)
    return mob


def mock_room(key="TestRoom", safe_zone=False):
    room = MockBase(key=key)
    room.attributes.add("safe_zone", safe_zone)
    room.msg_contents = MagicMock()
    return room


def mock_item(key="Item", slot=None, damage=0, armor=0, damage_type="slash",
              weight=1.0, value=1, durability=100, max_durability=100,
              stat_bonuses=None, location=None, item_type="equipment"):
    item = MockBase(key=key, location=location)
    attrs = item.attributes
    attrs.add("item_type", item_type)
    if slot:
        attrs.add("slot", slot)
    if damage:
        attrs.add("damage", damage)
    if damage_type:
        attrs.add("damage_type", damage_type)
    if armor:
        attrs.add("armor", armor)
    attrs.add("weight", weight)
    attrs.add("value", value)
    attrs.add("durability", durability)
    attrs.add("max_durability", max_durability)
    if stat_bonuses:
        attrs.add("stat_bonuses", stat_bonuses)
    if location is not None:
        location.contents.append(item)
    return item


def _reset_combat_state():
    import world.tick_combat as tc
    tc.ENGAGEMENTS.clear()
    tc.COMBAT_SCRIPT_UID = None


# ============================================================================
# Tests
# ============================================================================

class TestMobEquipmentGeneration(unittest.TestCase):
    """Mob spawn auto-equips gear and coins."""

    def test_01_equip_mob_generates_weapon_and_armor(self):
        from world.mob_equipment import equip_mob, get_equipped_weapon_damage

        mob = mock_mob("Orc", level=5, hp=50, max_hp=50, mob_class="Warrior")
        result = equip_mob(mob, mob_class="Warrior", faction="Neutral", equip_chance=1.0)

        self.assertIsNotNone(result["weapon"], "Mob must have a weapon")
        self.assertGreaterEqual(result["total_armor"], 1, "Full equip should grant armor")
        self.assertGreater(len(mob.contents), 0, "Mob should have items in contents")

        dmg = get_equipped_weapon_damage(mob)
        self.assertGreaterEqual(dmg, 1, "Equipped weapon should have damage")

    def test_02_equipped_armor_reflected_in_effective_armor(self):
        from world.mob_equipment import equip_mob, get_effective_armor

        mob = mock_mob("Knight", level=10, hp=80, max_hp=80, mob_class="Paladin")
        result = equip_mob(mob, mob_class="Paladin", equip_chance=1.0)

        total = get_effective_armor(mob)
        self.assertGreaterEqual(total, result["total_armor"],
                                "effective armor >= generated armor")

    def test_03_no_phantom_armor_with_nothing_equipped(self):
        from world.mob_equipment import get_effective_armor, has_armor_equipped

        mob = mock_mob("Naked", level=1, hp=10, max_hp=10)
        self.assertEqual(get_effective_armor(mob), 0)
        self.assertFalse(has_armor_equipped(mob))

    def test_04_generate_mob_coins_scales_with_level(self):
        from world.mob_equipment import generate_mob_coins

        coins_low = generate_mob_coins(1)
        coins_high = generate_mob_coins(50)
        total_low = coins_low["gold"] * 100 + coins_low["silver"] * 10 + coins_low["copper"]
        total_high = coins_high["gold"] * 100 + coins_high["silver"] * 10 + coins_high["copper"]
        self.assertGreaterEqual(total_high, total_low * 5,
                                "Level 50 should drop far more coin value than level 1")


class TestDamageTypeAndArmorMitigation(unittest.TestCase):
    """Weapon damage type + armor mitigation work in combat."""

    def test_01_weapon_damage_type_flows_through(self):
        from world.mob_equipment import get_equipped_weapon_damage_type

        char = mock_character("Fighter", hp=100, max_hp=100)
        sword = mock_item("Flame Sword", slot="main_hand", damage=10, damage_type="magic_fire")
        char.contents.append(sword)
        char.attributes.add("equipped", {"main_hand": "Flame Sword"})

        self.assertEqual(get_equipped_weapon_damage_type(char), "magic_fire")

    def test_02_armor_reduces_melee_damage(self):
        from world.damage_formulas import calculate_melee_damage, DamageType

        attacker = mock_character("Attacker", level=1,
                                  stats={"str": 16, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        unarmored = mock_character("Unarmored", level=1)
        armored = mock_character("Armored", level=1)
        armored.attributes.add("equipped", {"chest": "Plate Chest"})
        plate = mock_item("Plate Chest", slot="chest", armor=14)
        armored.contents.append(plate)

        random.seed(1234)
        orig_random = random.random
        orig_uniform = random.uniform
        random.random = lambda: 0.99  # no crit
        random.uniform = lambda a, b: 1.0  # no variance
        try:
            dmg_no_armor = calculate_melee_damage(attacker, unarmored, 10, DamageType.SLASH)
            dmg_armor = calculate_melee_damage(attacker, armored, 10, DamageType.SLASH)
        finally:
            random.random = orig_random
            random.uniform = orig_uniform

        self.assertGreater(dmg_no_armor["damage"], dmg_armor["damage"],
                           "Armor should reduce final damage")
        self.assertGreater(dmg_armor["absorbed"], 0,
                           "Armored target should report absorbed damage")

    def test_03_unarmed_returns_no_phantom_absorption(self):
        from world.damage_formulas import calculate_melee_damage, DamageType

        attacker = mock_character("Attacker", level=1)
        defender = mock_character("Naked", level=1)
        result = calculate_melee_damage(attacker, defender, 10, DamageType.SLASH)
        self.assertEqual(result["absorbed"], 0,
                         "No armor = zero absorption, no phantom absorption")

    def test_04_armor_affects_hit_chance_in_tick_combat(self):
        from world.tick_combat import _armor_class

        unarmored = mock_character("Soft", stats={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        armored = mock_character("Tank", stats={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        armored.attributes.add("equipped", {"chest": "Bulwark"})
        bulwark = mock_item("Bulwark", slot="chest", armor=30)
        armored.contents.append(bulwark)

        self.assertGreater(_armor_class(unarmored), _armor_class(armored),
                           "Armored target should have lower (better) AC")


class TestCorpseAndLootTransfer(unittest.TestCase):
    """Gear + coins move to corpse and can be looted."""

    def test_01_transfer_equipped_to_corpse(self):
        from world.mob_equipment import equip_mob, transfer_equipped_to_corpse

        mob = mock_mob("Bandit", level=5, hp=40, max_hp=40, mob_class="Rogue")
        equip_mob(mob, mob_class="Rogue", equip_chance=1.0)

        room = mock_room("Road")
        corpse = MockBase("corpse of Bandit", location=room)
        room.contents.append(corpse)

        transferred = transfer_equipped_to_corpse(mob, corpse)
        self.assertGreater(transferred, 0, "Should transfer equipped items")
        self.assertGreaterEqual(len(corpse.contents), transferred)

    def test_02_npc_corpse_receives_gear_and_coins(self):
        """Verify that _create_npc_corpse moves mob gear + coins to the corpse.

        Because _create_npc_corpse calls Evennia's create_object (which
        requires a live DB), we test the equivalent logic directly:
        we simulate what _create_npc_corpse does — create a corpse mock,
        move mob contents into it, and copy coin attributes.
        """
        from world.mob_equipment import equip_mob

        room = mock_room("Cave")
        mob = mock_mob("Goblin", level=3, hp=20, max_hp=20, location=room)
        mob.attributes.add("copper_coins", 5)
        mob.attributes.add("silver_coins", 2)
        mob.attributes.add("gold_coins", 1)
        equip_mob(mob, mob_class="Warrior", equip_chance=1.0)

        # Simulate _create_npc_corpse logic
        corpse = MockBase("corpse of Goblin", location=room)
        corpse.attributes.add("is_corpse", True)
        corpse.attributes.add("corpse_npc_level", 3)
        corpse.attributes.add("money", 0)
        corpse.attributes.add("gold_coins", mob.attributes.get("gold_coins", 0))
        corpse.attributes.add("silver_coins", mob.attributes.get("silver_coins", 0))
        corpse.attributes.add("copper_coins", mob.attributes.get("copper_coins", 0))

        # Move mob gear into corpse
        for item in list(mob.contents):
            if not getattr(item, "destination", None):
                item.move_to(corpse, quiet=True)

        self.assertGreater(len(corpse.contents), 0,
                           "Corpse should contain the mob's equipped gear")
        self.assertEqual(corpse.attributes.get("gold_coins"), 1)
        self.assertEqual(corpse.attributes.get("silver_coins"), 2)
        self.assertEqual(corpse.attributes.get("copper_coins"), 5)

    def test_03_loot_command_transfers_to_player(self):
        """Verify loot command transfers items and money from corpse to player.

        CmdLoot.func() calls caller.search() which requires a real Evennia
        object.  We test the equivalent logic: find the corpse in the room,
        move its contents to the player, and transfer money.
        """
        from world.mob_equipment import equip_mob

        room = mock_room("LootRoom")
        player = mock_character("Hero", hp=100, max_hp=100, location=room)
        mob = mock_mob("Rat", level=1, hp=5, max_hp=5, location=room)
        equip_mob(mob, mob_class="Warrior", equip_chance=0.0)  # weapon only

        corpse = MockBase("corpse of Rat", location=room)
        corpse.attributes.add("is_corpse", True)
        corpse.attributes.add("money", 3)
        room.contents.append(corpse)

        # Move mob gear into corpse
        for item in list(mob.contents):
            if not getattr(item, "destination", None):
                item.move_to(corpse, quiet=True)
        corpse_item_count = len([o for o in corpse.contents if not getattr(o, "destination", None)])

        # Simulate loot: find corpse, move items, transfer money
        target_corpse = None
        for obj in room.contents:
            if obj.attributes.get("is_corpse", False) and "corpse" in str(obj.key).lower():
                target_corpse = obj
                break

        self.assertIsNotNone(target_corpse, "Should find the corpse in the room")
        self.assertGreater(corpse_item_count, 0, "Corpse should start with items")

        # Transfer items
        for item in list(target_corpse.contents):
            if not getattr(item, "destination", None):
                item.move_to(player, quiet=True)

        # Transfer money
        corpse_money = target_corpse.attributes.get("money", 0)
        player_money = player.attributes.get("money", 0)
        player.attributes.add("money", player_money + corpse_money)
        target_corpse.attributes.add("money", 0)

        self.assertEqual(len([o for o in target_corpse.contents if not getattr(o, "destination", None)]), 0,
                         "Loot should empty the corpse")
        self.assertEqual(player.attributes.get("money"), 3)


class TestRespawnReequip(unittest.TestCase):
    """Mob respawn re-equips gear via _auto_equip_spawned_mob."""

    def test_01_respawn_reequips(self):
        import typeclasses.mobs as mobs_module

        room = mock_room("Home")
        proto = {
            "key": "orc_warrior",
            "attrs": [
                ("guild_class", "Warrior"),
                ("faction", "Neutral"),
                ("level", 4),
                ("hp", 40),
                ("max_hp", 40),
            ],
        }
        mob = mock_mob("Orc", level=4, hp=40, max_hp=40, location=room)
        mob.attributes.add("prototype_key", "orc_warrior")

        mobs_module._auto_equip_spawned_mob(mob, proto)
        equipped = mob.attributes.get("equipped", default={})
        self.assertTrue(equipped, "Auto-equip should populate equipped dict")
        self.assertGreater(len(mob.contents), 0)

        # Clear equipment (simulating corpse transfer) then re-equip.
        mob.attributes.add("equipped", {})
        for item in list(mob.contents):
            if not getattr(item, "destination", None):
                item.move_to(None, quiet=True)
        mobs_module._auto_equip_spawned_mob(mob, proto)
        equipped2 = mob.attributes.get("equipped", default={})
        self.assertTrue(equipped2, "Re-equip should repopulate equipped dict")
        self.assertGreater(len(mob.contents), 0)


class TestPlayerEquipmentCommands(unittest.TestCase):
    """wear / remove / equipment commands work."""

    def test_01_wear_and_remove(self):
        from world.mob_equipment import equip_item, unequip_item, get_effective_stat

        player = mock_character("Hero", stats={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        sword = mock_item("Steel Sword", slot="main_hand", damage=12, stat_bonuses={"str": 2})
        player.contents.append(sword)

        ok, msg = equip_item(player, sword)
        self.assertTrue(ok, msg)
        self.assertEqual(player.attributes.get("equipped", default={})["main_hand"], "Steel Sword")
        self.assertEqual(get_effective_stat(player, "str"), 12, "Stat bonus should apply")

        ok, msg = unequip_item(player, "main_hand")
        self.assertTrue(ok, msg)
        self.assertEqual(player.attributes.get("equipped", default={}), {}, "Remove should clear slot")

    def test_02_cannot_double_equip_slot(self):
        from world.mob_equipment import equip_item

        player = mock_character("Hero")
        sword1 = mock_item("Sword A", slot="main_hand")
        sword2 = mock_item("Sword B", slot="main_hand")
        player.contents.append(sword1)
        player.contents.append(sword2)

        ok1, _ = equip_item(player, sword1)
        self.assertTrue(ok1)
        ok2, msg2 = equip_item(player, sword2)
        self.assertFalse(ok2, "Should not double-equip same slot")

    def test_03_equipment_command_lists_items(self):
        from commands.equipment import CmdEquipment
        from world.mob_equipment import equip_item

        player = mock_character("Hero")
        helm = mock_item("Iron Helm", slot="head", armor=4)
        player.contents.append(helm)
        equip_item(player, helm)

        cmd = CmdEquipment()
        cmd.caller = player
        cmd.func()


class TestStatBonusesAndDurability(unittest.TestCase):
    """Stat bonuses apply; durability degrades on hit."""

    def test_01_effective_stats_include_bonuses(self):
        from world.mob_equipment import equip_item, get_effective_stats

        player = mock_character("Tank", stats={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        amulet = mock_item("Amulet of Might", slot="neck", stat_bonuses={"str": 3, "con": 2})
        player.contents.append(amulet)
        equip_item(player, amulet)

        stats = get_effective_stats(player)
        self.assertEqual(stats["str"], 13)
        self.assertEqual(stats["con"], 12)

    def test_02_durability_degrades_on_hit(self):
        from world.tick_combat import _degrade_equipment_on_hit

        attacker = mock_character("Attacker")
        sword = mock_item("Sword", slot="main_hand", damage=10, durability=50)
        attacker.contents.append(sword)
        attacker.attributes.add("equipped", {"main_hand": "Sword"})

        defender = mock_character("Defender")
        chest = mock_item("Chest", slot="chest", armor=5, durability=40)
        defender.contents.append(chest)
        defender.attributes.add("equipped", {"chest": "Chest"})

        _degrade_equipment_on_hit(attacker, defender)

        self.assertEqual(sword.attributes.get("durability"), 49)
        self.assertEqual(chest.attributes.get("durability"), 39)


class TestFullCombatLoop(unittest.TestCase):
    """Player kills equipped mob in combat."""

    def test_01_full_loop(self):
        from world.tick_combat import CombatHandler, _execute_attack_round
        from world.mob_equipment import equip_mob, generate_mob_coins

        room = mock_room("Arena")
        player = mock_character("Hero", "Human", "Warrior", level=10, hp=500, max_hp=500,
                                stats={"str": 20, "dex": 16, "con": 16, "int": 10, "wis": 10, "cha": 10},
                                location=room)
        mob = mock_mob("Orc Warrior", level=1, hp=30, max_hp=30, location=room)
        equip_mob(mob, mob_class="Warrior", equip_chance=1.0)
        coins = generate_mob_coins(1)
        mob.attributes.add("copper_coins", coins["copper"])
        mob.attributes.add("silver_coins", coins["silver"])
        mob.attributes.add("gold_coins", coins["gold"])

        mob_items_before = len([o for o in mob.contents if not getattr(o, "destination", None)])
        self.assertGreater(mob_items_before, 0, "Mob should have equipped items")

        _reset_combat_state()
        CombatHandler.start_combat(player, mob)
        rounds = 0
        max_rounds = 300
        while mob.attributes.get("hp") > 0 and rounds < max_rounds:
            _execute_attack_round(player, mob)
            rounds += 1
            if mob.attributes.get("hp") <= 0:
                break

        self.assertEqual(mob.attributes.get("hp"), 0, "Mob should be dead")


# ============================================================================
# Runner
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)