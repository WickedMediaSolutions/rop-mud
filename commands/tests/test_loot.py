"""
Unit tests for the Looting & Sacrifice system.

Tests:
  - Manual sacrifice (sac / sacrifice)
  - Manual looting (loot / loot all)
  - Auto-loot toggle (autoloot)
  - Auto-sacrifice toggle (autosac)
  - Post-combat auto-loot trigger
  - Post-combat auto-sac trigger
  - Post-combat auto-loot + auto-sac combined

Run with:
    evennia test commands.tests.test_loot
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultRoom, DefaultCharacter, DefaultObject
from evennia import create_object

from commands.loot import (
    CmdSacrifice,
    CmdLoot,
    CmdAutoLoot,
    CmdAutoSac,
    calculate_sac_reward,
)
from world.combat import (
    _create_npc_corpse,
    _auto_loot_corpse,
    _auto_sac_corpse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_test_room():
    """Create a clean room for test characters and corpses."""
    return create_object(DefaultRoom, key="Loot Test Room")


def _make_corpse(name="Goblin", location=None, npc_level=1, money=10):
    """Create a standalone corpse object for manual test commands."""
    corpse = create_object(
        DefaultObject,
        key=f"corpse of {name}",
        location=location,
        attributes=[
            ("is_corpse", True),
            ("corpse_npc_level", npc_level),
            ("money", money),
        ],
    )
    return corpse


def _make_corpse_with_items(name="Orc", location=None, npc_level=2, money=25,
                            items=None):
    """Create a corpse that contains physical items."""
    corpse = create_object(
        DefaultObject,
        key=f"corpse of {name}",
        location=location,
        attributes=[
            ("is_corpse", True),
            ("corpse_npc_level", npc_level),
            ("money", money),
        ],
    )
    if items:
        for item in items:
            item.move_to(corpse, quiet=True)
    return corpse


# ---------------------------------------------------------------------------
# Sacrifice command tests
# ---------------------------------------------------------------------------

class TestSacrifice(BaseEvenniaTest):
    """Test the `sac` / `sacrifice` command."""

    def setUp(self):
        super().setUp()
        self.room = _make_test_room()
        self.char = create_object(DefaultCharacter, key="SacTester")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_sac_no_args(self):
        """sac with no args shows usage."""
        before_money = self.char.attributes.get("money", 0)
        cmd = CmdSacrifice()
        cmd.caller = self.char
        cmd.cmdstring = "sac"
        cmd.args = ""
        cmd.func()
        # Money unchanged
        self.assertEqual(self.char.attributes.get("money", 0), before_money)

    def test_sac_non_corpse(self):
        """sac on a non-corpse object does nothing."""
        dummy = create_object(DefaultObject, key="rock", location=self.room,
                              attributes=[("is_corpse", False)])
        before_money = self.char.attributes.get("money", 0)

        cmd = CmdSacrifice()
        cmd.caller = self.char
        cmd.cmdstring = "sac"
        cmd.args = "rock"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money", 0), before_money)
        self.assertTrue(dummy.id)
        dummy.delete()

    def test_sac_corpse_awards_coins_and_destroys(self):
        """Sacrificing a valid corpse awards coins and deletes the corpse."""
        corpse = _make_corpse(name="Goblin", location=self.room,
                              npc_level=3, money=10)
        before_money = self.char.attributes.get("money", 0)

        cmd = CmdSacrifice()
        cmd.caller = self.char
        cmd.cmdstring = "sac"
        cmd.args = "corpse of Goblin"
        cmd.func()

        after_money = self.char.attributes.get("money", 0)
        # Coins should increase
        self.assertGreater(after_money, before_money)
        # Corpse should be gone
        self.assertIsNone(corpse.id)

    def test_sacrifice_alias_works(self):
        """The 'sacrifice' alias also triggers the command."""
        corpse = _make_corpse(name="Bandit", location=self.room,
                              npc_level=2, money=5)
        before_money = self.char.attributes.get("money", 0)

        cmd = CmdSacrifice()
        cmd.caller = self.char
        cmd.cmdstring = "sacrifice"
        cmd.args = "corpse of Bandit"
        cmd.func()

        self.assertGreater(self.char.attributes.get("money", 0), before_money)
        self.assertIsNone(corpse.id)


# ---------------------------------------------------------------------------
# calculate_sac_reward helper test
# ---------------------------------------------------------------------------

class TestSacReward(BaseEvenniaTest):
    """Test the external reward calculator."""

    def test_reward_in_range(self):
        """Reward is between 1 and 5 * level (inclusive)."""
        for level in (1, 2, 3, 5, 10):
            coins, display = calculate_sac_reward(level)
            self.assertGreaterEqual(coins, 1 * level)
            self.assertLessEqual(coins, 5 * level)

    def test_reward_always_positive(self):
        """Even level 1 gives at least 1 coin."""
        for _ in range(20):
            coins, display = calculate_sac_reward(1)
            self.assertGreaterEqual(coins, 1)


# ---------------------------------------------------------------------------
# Loot command tests
# ---------------------------------------------------------------------------

class TestLoot(BaseEvenniaTest):
    """Test the `loot` command."""

    def setUp(self):
        super().setUp()
        self.room = _make_test_room()
        self.char = create_object(DefaultCharacter, key="Looter")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_loot_no_args(self):
        """loot with no args shows usage."""
        cmd = CmdLoot()
        cmd.caller = self.char
        cmd.cmdstring = "loot"
        cmd.args = ""
        cmd.func()

    def test_loot_non_corpse(self):
        """loot on a non-corpse gives error."""
        dummy = create_object(DefaultObject, key="chest", location=self.room,
                              attributes=[("is_corpse", False)])
        before = self.char.attributes.get("money", 0)

        cmd = CmdLoot()
        cmd.caller = self.char
        cmd.cmdstring = "loot"
        cmd.args = "chest"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money", 0), before)
        dummy.delete()

    def test_loot_transfers_money(self):
        """Looting transfers the corpse's money to the caller."""
        corpse = _make_corpse(name="Rat", location=self.room,
                              npc_level=1, money=42)
        before = self.char.attributes.get("money", 0)

        cmd = CmdLoot()
        cmd.caller = self.char
        cmd.cmdstring = "loot"
        cmd.args = "corpse of Rat"
        cmd.func()

        # Money transferred
        self.assertEqual(self.char.attributes.get("money", 0), before + 42)
        # Corpse money zeroed
        self.assertEqual(corpse.attributes.get("money", 0), 0)
        # Corpse still exists (empty frame)
        self.assertIsNotNone(corpse.id)

    def test_loot_transfers_items(self):
        """Looting transfers physical items from corpse to caller."""
        sword = create_object(DefaultObject, key="Rusty Sword")
        shield = create_object(DefaultObject, key="Wooden Shield")
        corpse = _make_corpse_with_items(
            name="Guard", location=self.room, npc_level=2, money=15,
            items=[sword, shield],
        )

        cmd = CmdLoot()
        cmd.caller = self.char
        cmd.cmdstring = "loot"
        cmd.args = "corpse of Guard"
        cmd.func()

        # Items moved to caller
        self.assertIn(sword, self.char.contents)
        self.assertIn(shield, self.char.contents)
        # Money transferred
        self.assertEqual(self.char.attributes.get("money", 0), 15)

    def test_loot_all_works(self):
        """loot all <corpse> works the same as loot <corpse>."""
        corpse = _make_corpse(name="Skeleton", location=self.room,
                              npc_level=1, money=8)
        before = self.char.attributes.get("money", 0)

        cmd = CmdLoot()
        cmd.caller = self.char
        cmd.cmdstring = "loot"
        cmd.args = "all corpse of Skeleton"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money", 0), before + 8)

    def test_loot_empty_corpse(self):
        """Looting a corpse with no money and no items shows correct message."""
        corpse = _make_corpse(name="Peasant", location=self.room,
                              npc_level=1, money=0)

        cmd = CmdLoot()
        cmd.caller = self.char
        cmd.cmdstring = "loot"
        cmd.args = "corpse of Peasant"
        cmd.func()

        # Still exists
        self.assertIsNotNone(corpse.id)


# ---------------------------------------------------------------------------
# Auto-loot / auto-sac toggle tests
# ---------------------------------------------------------------------------

class TestToggles(BaseEvenniaTest):
    """Test autoloot and autosac toggle commands."""

    def setUp(self):
        super().setUp()
        self.char = create_object(DefaultCharacter, key="Toggler")

    def tearDown(self):
        self.char.delete()
        super().tearDown()

    def test_autoloot_toggle_on(self):
        """autoloot toggles from off to on."""
        self.char.attributes.add("autoloot", False)
        cmd = CmdAutoLoot()
        cmd.caller = self.char
        cmd.cmdstring = "autoloot"
        cmd.func()
        self.assertTrue(self.char.attributes.get("autoloot", False))

    def test_autoloot_toggle_off(self):
        """autoloot toggles from on to off."""
        self.char.attributes.add("autoloot", True)
        cmd = CmdAutoLoot()
        cmd.caller = self.char
        cmd.cmdstring = "autoloot"
        cmd.func()
        self.assertFalse(self.char.attributes.get("autoloot", False))

    def test_autosac_toggle_on(self):
        """autosac toggles from off to on."""
        self.char.attributes.add("autosac", False)
        cmd = CmdAutoSac()
        cmd.caller = self.char
        cmd.cmdstring = "autosac"
        cmd.func()
        self.assertTrue(self.char.attributes.get("autosac", False))

    def test_autosac_toggle_off(self):
        """autosac toggles from on to off."""
        self.char.attributes.add("autosac", True)
        cmd = CmdAutoSac()
        cmd.caller = self.char
        cmd.cmdstring = "autosac"
        cmd.func()
        self.assertFalse(self.char.attributes.get("autosac", False))


# ---------------------------------------------------------------------------
# Auto-loot internal helper tests
# ---------------------------------------------------------------------------

class TestAutoLoot(BaseEvenniaTest):
    """Test the _auto_loot_corpse helper function."""

    def setUp(self):
        super().setUp()
        self.room = _make_test_room()
        self.char = create_object(DefaultCharacter, key="AutoLooter")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_auto_loot_money(self):
        """_auto_loot_corpse transfers money."""
        corpse = _make_corpse(name="Wolf", location=self.room,
                              npc_level=2, money=20)
        before = self.char.attributes.get("money", 0)

        _auto_loot_corpse(self.char, corpse)

        self.assertEqual(self.char.attributes.get("money", 0), before + 20)
        self.assertEqual(corpse.attributes.get("money", 0), 0)

    def test_auto_loot_items(self):
        """_auto_loot_corpse transfers items."""
        sword = create_object(DefaultObject, key="Iron Sword")
        corpse = _make_corpse_with_items(
            name="Bandit", location=self.room, npc_level=2, money=10,
            items=[sword],
        )

        _auto_loot_corpse(self.char, corpse)

        self.assertIn(sword, self.char.contents)
        self.assertEqual(self.char.attributes.get("money", 0), 10)

    def test_auto_loot_empty_corpse(self):
        """_auto_loot_corpse on empty corpse doesn't crash."""
        corpse = _make_corpse(name="Slime", location=self.room,
                              npc_level=1, money=0)
        before = self.char.attributes.get("money", 0)

        _auto_loot_corpse(self.char, corpse)

        self.assertEqual(self.char.attributes.get("money", 0), before)
        self.assertIsNotNone(corpse.id)


# ---------------------------------------------------------------------------
# Auto-sac internal helper tests
# ---------------------------------------------------------------------------

class TestAutoSac(BaseEvenniaTest):
    """Test the _auto_sac_corpse helper function."""

    def setUp(self):
        super().setUp()
        self.room = _make_test_room()
        self.char = create_object(DefaultCharacter, key="AutoSacer")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_auto_sac_awards_coins(self):
        """_auto_sac_corpse awards coins and destroys corpse."""
        corpse = _make_corpse(name="Goblin", location=self.room,
                              npc_level=3, money=15)
        before = self.char.attributes.get("money", 0)

        _auto_sac_corpse(self.char, corpse)

        self.assertGreater(self.char.attributes.get("money", 0), before)
        # Corpse deleted
        self.assertIsNone(corpse.id)

    def test_auto_sac_after_loot(self):
        """Auto-sac after auto-loot still awards bonus coins (empty corpse)."""
        sword = create_object(DefaultObject, key="Rusty Sword")
        corpse = _make_corpse_with_items(
            name="Orc", location=self.room, npc_level=2, money=30,
            items=[sword],
        )

        # Loot first
        _auto_loot_corpse(self.char, corpse)
        money_after_loot = self.char.attributes.get("money", 0)

        # Then sac
        _auto_sac_corpse(self.char, corpse)

        # Bonus coins awarded on top of loot
        self.assertGreater(self.char.attributes.get("money", 0),
                           money_after_loot)
        # Corpse gone
        self.assertIsNone(corpse.id)


# ---------------------------------------------------------------------------
# NPC Corpse creation tests
# ---------------------------------------------------------------------------

class TestNpcCorpse(BaseEvenniaTest):
    """Test _create_npc_corpse."""

    def setUp(self):
        super().setUp()
        self.room = _make_test_room()
        self.npc = create_object(DefaultCharacter, key="Test Mob")
        self.npc.location = self.room
        self.npc.attributes.add("level", 5)
        self.killer = create_object(DefaultCharacter, key="Killer")
        self.killer.location = self.room

    def tearDown(self):
        self.killer.delete()
        self.npc.delete()
        self.room.delete()
        super().tearDown()

    def test_npc_corpse_has_level(self):
        """NPC corpse stores the original mob level."""
        corpse = _create_npc_corpse(self.npc, self.killer, npc_level=5)
        self.assertEqual(
            corpse.attributes.get("corpse_npc_level", 0),
            5,
        )

    def test_npc_corpse_is_corpse(self):
        """NPC corpse has is_corpse flag."""
        corpse = _create_npc_corpse(self.npc, self.killer, npc_level=3)
        self.assertTrue(corpse.attributes.get("is_corpse", False))

    def test_npc_corpse_has_money(self):
        """NPC corpse has some money."""
        corpse = _create_npc_corpse(self.npc, self.killer, npc_level=3)
        self.assertGreater(corpse.attributes.get("money", 0), 0)

    def test_npc_corpse_takes_items_from_npc(self):
        """Items on the NPC move into the corpse."""
        sword = create_object(DefaultObject, key="Iron Sword")
        sword.move_to(self.npc, quiet=True)

        corpse = _create_npc_corpse(self.npc, self.killer, npc_level=3)

        self.assertIn(sword, corpse.contents)
        self.assertNotIn(sword, self.npc.contents)