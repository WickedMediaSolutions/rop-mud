"""
Unit tests for the Banking System: deposit, withdraw, balance, and
bank gold safety from death penalties.

Run with:
    evennia test commands.tests.test_bank
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultRoom, DefaultCharacter, DefaultObject
from evennia import create_object

from commands.bank import CmdDeposit, CmdWithdraw, CmdBalance


# ---------------------------------------------------------------------------
# Helper: create a room with a bank teller
# ---------------------------------------------------------------------------

def _create_bank_room():
    """Create a room with a Bank Teller NPC for testing."""
    room = create_object(DefaultRoom, key="Bank Test Room")
    teller = create_object(
        DefaultObject,
        key="Test Bank Teller",
        location=room,
        attributes=[("is_bank_teller", True)],
    )
    return room, teller


# ---------------------------------------------------------------------------
# Deposit Tests
# ---------------------------------------------------------------------------

class TestDeposit(BaseEvenniaTest):
    """Test the deposit command."""

    def setUp(self):
        super().setUp()
        self.room, self.teller = _create_bank_room()
        self.char = create_object(DefaultCharacter, key="Banker")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.teller.delete()
        self.room.delete()
        super().tearDown()

    def test_deposit_specific_amount(self):
        """Depositing a specific amount transfers gold to bank."""
        self.char.attributes.add("money", 500)
        self.char.attributes.add("bank_gold", 0)

        cmd = CmdDeposit()
        cmd.caller = self.char
        cmd.cmdstring = "deposit"
        cmd.args = "200"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 300)
        self.assertEqual(self.char.attributes.get("bank_gold"), 200)

    def test_deposit_all(self):
        """Depositing 'all' transfers all carried gold."""
        self.char.attributes.add("money", 750)
        self.char.attributes.add("bank_gold", 100)

        cmd = CmdDeposit()
        cmd.caller = self.char
        cmd.cmdstring = "deposit"
        cmd.args = "all"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 0)
        self.assertEqual(self.char.attributes.get("bank_gold"), 850)

    def test_deposit_all_when_zero(self):
        """Depositing 'all' when carrying 0 gold does nothing."""
        self.char.attributes.add("money", 0)
        self.char.attributes.add("bank_gold", 50)

        cmd = CmdDeposit()
        cmd.caller = self.char
        cmd.cmdstring = "deposit"
        cmd.args = "all"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 0)
        self.assertEqual(self.char.attributes.get("bank_gold"), 50)

    def test_deposit_more_than_carried(self):
        """Cannot deposit more gold than carried."""
        self.char.attributes.add("money", 100)
        self.char.attributes.add("bank_gold", 0)

        cmd = CmdDeposit()
        cmd.caller = self.char
        cmd.cmdstring = "deposit"
        cmd.args = "500"
        cmd.func()

        # Should not change
        self.assertEqual(self.char.attributes.get("money"), 100)
        self.assertEqual(self.char.attributes.get("bank_gold"), 0)

    def test_deposit_negative_amount(self):
        """Cannot deposit a negative amount."""
        self.char.attributes.add("money", 100)
        self.char.attributes.add("bank_gold", 0)

        cmd = CmdDeposit()
        cmd.caller = self.char
        cmd.cmdstring = "deposit"
        cmd.args = "-50"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 100)
        self.assertEqual(self.char.attributes.get("bank_gold"), 0)

    def test_deposit_zero(self):
        """Cannot deposit zero gold."""
        self.char.attributes.add("money", 100)
        self.char.attributes.add("bank_gold", 0)

        cmd = CmdDeposit()
        cmd.caller = self.char
        cmd.cmdstring = "deposit"
        cmd.args = "0"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 100)
        self.assertEqual(self.char.attributes.get("bank_gold"), 0)

    def test_deposit_invalid_string(self):
        """Invalid string input is rejected."""
        self.char.attributes.add("money", 100)
        self.char.attributes.add("bank_gold", 0)

        cmd = CmdDeposit()
        cmd.caller = self.char
        cmd.cmdstring = "deposit"
        cmd.args = "abc"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 100)
        self.assertEqual(self.char.attributes.get("bank_gold"), 0)

    def test_deposit_no_args_shows_usage(self):
        """Deposit with no args shows usage message."""
        self.char.attributes.add("money", 100)

        cmd = CmdDeposit()
        cmd.caller = self.char
        cmd.cmdstring = "deposit"
        cmd.args = ""
        cmd.func()

        # Should not raise, money unchanged
        self.assertEqual(self.char.attributes.get("money"), 100)

    def test_deposit_no_bank_teller(self):
        """Cannot deposit without a bank teller in the room."""
        # Move char to a room without a teller
        other_room = create_object(DefaultRoom, key="No Bank Room")
        self.char.location = other_room
        self.char.attributes.add("money", 200)
        self.char.attributes.add("bank_gold", 0)

        cmd = CmdDeposit()
        cmd.caller = self.char
        cmd.cmdstring = "deposit"
        cmd.args = "100"
        cmd.func()

        # Money should not change
        self.assertEqual(self.char.attributes.get("money"), 200)
        self.assertEqual(self.char.attributes.get("bank_gold"), 0)

        self.char.location = self.room
        other_room.delete()

    def test_deposit_no_location(self):
        """Deposit handles characters with no location gracefully."""
        self.char.location = None
        self.char.attributes.add("money", 100)

        cmd = CmdDeposit()
        cmd.caller = self.char
        cmd.cmdstring = "deposit"
        cmd.args = "50"
        cmd.func()

        # Should not change (no teller available)
        self.assertEqual(self.char.attributes.get("money"), 100)

        self.char.location = self.room

    def test_deposit_multiple_times(self):
        """Multiple deposits accumulate correctly."""
        self.char.attributes.add("money", 1000)
        self.char.attributes.add("bank_gold", 0)

        for amount in [100, 200, 50]:
            cmd = CmdDeposit()
            cmd.caller = self.char
            cmd.cmdstring = "deposit"
            cmd.args = str(amount)
            cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 650)
        self.assertEqual(self.char.attributes.get("bank_gold"), 350)

    def test_deposit_default_bank_gold_zero(self):
        """Characters with no bank_gold attribute default to 0."""
        self.char.attributes.add("money", 300)
        # Don't set bank_gold at all

        cmd = CmdDeposit()
        cmd.caller = self.char
        cmd.cmdstring = "deposit"
        cmd.args = "100"
        cmd.func()

        self.assertEqual(self.char.attributes.get("bank_gold"), 100)
        self.assertEqual(self.char.attributes.get("money"), 200)


# ---------------------------------------------------------------------------
# Withdraw Tests
# ---------------------------------------------------------------------------

class TestWithdraw(BaseEvenniaTest):
    """Test the withdraw command."""

    def setUp(self):
        super().setUp()
        self.room, self.teller = _create_bank_room()
        self.char = create_object(DefaultCharacter, key="Withdrawer")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.teller.delete()
        self.room.delete()
        super().tearDown()

    def test_withdraw_specific_amount(self):
        """Withdrawing a specific amount transfers gold from bank to carried."""
        self.char.attributes.add("money", 50)
        self.char.attributes.add("bank_gold", 500)

        cmd = CmdWithdraw()
        cmd.caller = self.char
        cmd.cmdstring = "withdraw"
        cmd.args = "200"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 250)
        self.assertEqual(self.char.attributes.get("bank_gold"), 300)

    def test_withdraw_more_than_balance(self):
        """Cannot withdraw more than bank balance."""
        self.char.attributes.add("money", 50)
        self.char.attributes.add("bank_gold", 100)

        cmd = CmdWithdraw()
        cmd.caller = self.char
        cmd.cmdstring = "withdraw"
        cmd.args = "500"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 50)
        self.assertEqual(self.char.attributes.get("bank_gold"), 100)

    def test_withdraw_zero_balance(self):
        """Cannot withdraw when bank balance is zero."""
        self.char.attributes.add("money", 50)
        self.char.attributes.add("bank_gold", 0)

        cmd = CmdWithdraw()
        cmd.caller = self.char
        cmd.cmdstring = "withdraw"
        cmd.args = "100"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 50)
        self.assertEqual(self.char.attributes.get("bank_gold"), 0)

    def test_withdraw_negative_amount(self):
        """Cannot withdraw a negative amount."""
        self.char.attributes.add("money", 50)
        self.char.attributes.add("bank_gold", 200)

        cmd = CmdWithdraw()
        cmd.caller = self.char
        cmd.cmdstring = "withdraw"
        cmd.args = "-50"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 50)
        self.assertEqual(self.char.attributes.get("bank_gold"), 200)

    def test_withdraw_zero(self):
        """Cannot withdraw zero gold."""
        self.char.attributes.add("money", 50)
        self.char.attributes.add("bank_gold", 200)

        cmd = CmdWithdraw()
        cmd.caller = self.char
        cmd.cmdstring = "withdraw"
        cmd.args = "0"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 50)
        self.assertEqual(self.char.attributes.get("bank_gold"), 200)

    def test_withdraw_invalid_string(self):
        """Invalid string input is rejected."""
        self.char.attributes.add("money", 50)
        self.char.attributes.add("bank_gold", 200)

        cmd = CmdWithdraw()
        cmd.caller = self.char
        cmd.cmdstring = "withdraw"
        cmd.args = "xyz"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 50)
        self.assertEqual(self.char.attributes.get("bank_gold"), 200)

    def test_withdraw_no_args_shows_usage(self):
        """Withdraw with no args shows usage message."""
        self.char.attributes.add("bank_gold", 200)

        cmd = CmdWithdraw()
        cmd.caller = self.char
        cmd.cmdstring = "withdraw"
        cmd.args = ""
        cmd.func()

        # Should not raise
        self.assertEqual(self.char.attributes.get("bank_gold"), 200)

    def test_withdraw_no_bank_teller(self):
        """Cannot withdraw without a bank teller in the room."""
        other_room = create_object(DefaultRoom, key="No Teller Room")
        self.char.location = other_room
        self.char.attributes.add("money", 50)
        self.char.attributes.add("bank_gold", 300)

        cmd = CmdWithdraw()
        cmd.caller = self.char
        cmd.cmdstring = "withdraw"
        cmd.args = "100"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 50)
        self.assertEqual(self.char.attributes.get("bank_gold"), 300)

        self.char.location = self.room
        other_room.delete()

    def test_withdraw_no_location(self):
        """Withdraw handles characters with no location gracefully."""
        self.char.location = None
        self.char.attributes.add("bank_gold", 200)

        cmd = CmdWithdraw()
        cmd.caller = self.char
        cmd.cmdstring = "withdraw"
        cmd.args = "50"
        cmd.func()

        self.assertEqual(self.char.attributes.get("bank_gold"), 200)

        self.char.location = self.room

    def test_withdraw_multiple_times(self):
        """Multiple withdrawals accumulate correctly."""
        self.char.attributes.add("money", 0)
        self.char.attributes.add("bank_gold", 1000)

        for amount in [100, 200, 50]:
            cmd = CmdWithdraw()
            cmd.caller = self.char
            cmd.cmdstring = "withdraw"
            cmd.args = str(amount)
            cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 350)
        self.assertEqual(self.char.attributes.get("bank_gold"), 650)

    def test_withdraw_default_money_zero(self):
        """Characters with no money attribute default to 0 for carried."""
        self.char.attributes.add("bank_gold", 300)
        # Don't set money at all

        cmd = CmdWithdraw()
        cmd.caller = self.char
        cmd.cmdstring = "withdraw"
        cmd.args = "100"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 100)
        self.assertEqual(self.char.attributes.get("bank_gold"), 200)


# ---------------------------------------------------------------------------
# Balance Tests
# ---------------------------------------------------------------------------

class TestBalance(BaseEvenniaTest):
    """Test the balance command."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="Balance Room")
        self.char = create_object(DefaultCharacter, key="Balancer")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_balance_shows_both_values(self):
        """Balance command shows both bank and carried gold."""
        self.char.attributes.add("money", 150)
        self.char.attributes.add("bank_gold", 350)

        cmd = CmdBalance()
        cmd.caller = self.char
        cmd.cmdstring = "balance"
        cmd.args = ""
        cmd.func()

        # Should not raise

    def test_balance_defaults_to_zero(self):
        """Balance shows 0 for unset attributes."""
        # Don't set money or bank_gold

        cmd = CmdBalance()
        cmd.caller = self.char
        cmd.cmdstring = "balance"
        cmd.args = ""
        cmd.func()

        # Should not raise, defaults to 0

    def test_balance_no_location(self):
        """Balance works without being in any room (no teller needed)."""
        self.char.location = None
        self.char.attributes.add("money", 100)
        self.char.attributes.add("bank_gold", 200)

        cmd = CmdBalance()
        cmd.caller = self.char
        cmd.cmdstring = "balance"
        cmd.args = ""
        cmd.func()

        # Should not raise — balance doesn't require a teller
        self.char.location = self.room

    def test_bank_alias_works(self):
        """The 'bank' alias works the same as 'balance'."""
        self.char.attributes.add("money", 50)
        self.char.attributes.add("bank_gold", 500)

        cmd = CmdBalance()
        cmd.caller = self.char
        cmd.cmdstring = "bank"
        cmd.args = ""
        cmd.func()

        # Should not raise


# ---------------------------------------------------------------------------
# Bank Gold Safety from Death Tests
# ---------------------------------------------------------------------------

class TestBankGoldSafety(BaseEvenniaTest):
    """
    Verify that bank_gold is NOT affected by death mechanics.

    The death handler in world/combat.py only transfers the 'money'
    attribute to the corpse.  'bank_gold' is a separate attribute
    that should survive death untouched.
    """

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="Death Test Room")
        self.char = create_object(DefaultCharacter, key="Victim")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_bank_gold_survives_create_corpse(self):
        """
        After create_corpse is called, bank_gold remains on the character.

        create_corpse() in world/combat.py only transfers 'money' to the
        corpse and zeros it on the victim.  bank_gold is untouched.
        """
        from world.combat import create_corpse

        self.char.attributes.add("money", 500)
        self.char.attributes.add("bank_gold", 1000)

        killer = create_object(DefaultCharacter, key="Killer")
        killer.location = self.room

        corpse = create_corpse(self.char, killer)

        # Carried money should be zeroed (transferred to corpse)
        self.assertEqual(self.char.attributes.get("money"), 0)

        # Bank gold should be completely untouched
        self.assertEqual(self.char.attributes.get("bank_gold"), 1000)

        # Corpse should have the money
        self.assertEqual(corpse.attributes.get("money"), 500)

        # Cleanup
        corpse.delete()
        killer.delete()

    def test_bank_gold_survives_full_defeat(self):
        """
        After _handle_defeat, bank_gold is preserved.

        The full death flow (XP loss, corpse creation, respawn) should
        never touch bank_gold.
        """
        from world.combat import _handle_defeat

        self.char.attributes.add("money", 300)
        self.char.attributes.add("bank_gold", 2000)
        self.char.attributes.add("xp", 5000)
        self.char.attributes.add("hp", 100)
        self.char.attributes.add("max_hp", 100)
        self.char.attributes.add("mana", 50)
        self.char.attributes.add("max_mana", 50)
        self.char.attributes.add("mv", 100)
        self.char.attributes.add("max_mv", 100)
        self.char.attributes.add("alignment", "Good")
        self.char.attributes.add("level", 5)

        # Set home to the current room so respawn stays here
        self.char.home = self.room

        killer = create_object(DefaultCharacter, key="Slayer")
        killer.location = self.room

        _handle_defeat(self.char, killer)

        # Carried money should be zeroed
        self.assertEqual(self.char.attributes.get("money"), 0)

        # Bank gold must survive intact
        self.assertEqual(self.char.attributes.get("bank_gold"), 2000)

        # Clean up any corpse created
        for obj in self.room.contents:
            if obj.attributes.get("is_corpse", default=False):
                obj.delete()
        killer.delete()

    def test_bank_gold_survives_defeat_with_no_initial_money(self):
        """
        Defeat with zero carried money still preserves bank_gold.
        """
        from world.combat import _handle_defeat

        self.char.attributes.add("money", 0)
        self.char.attributes.add("bank_gold", 5000)
        self.char.attributes.add("xp", 3000)
        self.char.attributes.add("hp", 100)
        self.char.attributes.add("max_hp", 100)
        self.char.attributes.add("mana", 50)
        self.char.attributes.add("max_mana", 50)
        self.char.attributes.add("mv", 100)
        self.char.attributes.add("max_mv", 100)
        self.char.attributes.add("alignment", "Good")
        self.char.attributes.add("level", 3)

        self.char.home = self.room

        killer = create_object(DefaultCharacter, key="Slayer2")
        killer.location = self.room

        _handle_defeat(self.char, killer)

        self.assertEqual(self.char.attributes.get("money"), 0)
        self.assertEqual(self.char.attributes.get("bank_gold"), 5000)

        for obj in self.room.contents:
            if obj.attributes.get("is_corpse", default=False):
                obj.delete()
        killer.delete()

    def test_bank_gold_persists_after_deposit_and_defeat(self):
        """
        Full flow: deposit gold, then die — bank_gold is preserved.
        """
        from world.combat import _handle_defeat

        # Set up bank teller room
        bank_room, teller = _create_bank_room()
        self.char.location = bank_room
        self.char.attributes.add("money", 1000)
        self.char.attributes.add("bank_gold", 0)

        # Deposit 600 gold
        cmd = CmdDeposit()
        cmd.caller = self.char
        cmd.cmdstring = "deposit"
        cmd.args = "600"
        cmd.func()

        self.assertEqual(self.char.attributes.get("money"), 400)
        self.assertEqual(self.char.attributes.get("bank_gold"), 600)

        # Now move to death room and die
        self.char.location = self.room
        self.char.attributes.add("xp", 5000)
        self.char.attributes.add("hp", 100)
        self.char.attributes.add("max_hp", 100)
        self.char.attributes.add("mana", 50)
        self.char.attributes.add("max_mana", 50)
        self.char.attributes.add("mv", 100)
        self.char.attributes.add("max_mv", 100)
        self.char.attributes.add("alignment", "Good")
        self.char.attributes.add("level", 5)
        self.char.home = self.room

        killer = create_object(DefaultCharacter, key="Slayer3")
        killer.location = self.room

        _handle_defeat(self.char, killer)

        # Carried 400 gold is lost to corpse
        self.assertEqual(self.char.attributes.get("money"), 0)

        # Bank gold of 600 is completely safe
        self.assertEqual(self.char.attributes.get("bank_gold"), 600)

        # Cleanup
        for obj in self.room.contents:
            if obj.attributes.get("is_corpse", default=False):
                obj.delete()
        killer.delete()
        teller.delete()
        bank_room.delete()