"""
Banking System for 'rop'

Commands:
  deposit <amount>  - Deposit gold into your bank account
  deposit all       - Deposit all carried gold
  withdraw <amount> - Withdraw gold from your bank account
  balance / bank    - Check your bank balance and carried gold

Bank gold is stored in the 'bank_gold' attribute, completely separate from
carried 'money'.  Death only affects carried money, so banked gold is 100% safe.
"""

from commands.command import Command


class CmdDeposit(Command):
    """
    Deposit gold into your bank account.

    Usage:
      deposit <amount>
      deposit all

    Gold stored in the bank is completely safe from death penalties.
    You must be in a room with a Bank Teller to use this command.
    """

    key = "deposit"
    aliases = ["dep"]
    help_category = "Banking"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        # Check for bank teller in the room
        if not self._has_bank_teller():
            caller.msg("|rYou must be at a bank to deposit gold.|n")
            return

        if not args:
            caller.msg("|yUsage: deposit <amount> |w or |ydeposit all|n")
            return

        carried = caller.attributes.get("money", default=0)

        if args == "all":
            amount = carried
        else:
            try:
                amount = int(args)
            except ValueError:
                caller.msg("|rInvalid amount. Use a number or 'all'.|n")
                return
            if amount <= 0:
                caller.msg("|rYou must deposit a positive amount.|n")
                return

        if amount > carried:
            caller.msg(
                f"|rYou don't have that much gold. "
                f"You are carrying {carried} gold.|n"
            )
            return

        if carried == 0:
            caller.msg("|yYou have no gold to deposit.|n")
            return

        # Bank transaction fee: 1% of deposit amount (minimum 1 gold)
        fee = max(1, int(amount * 0.01))
        total_cost = amount + fee
        if carried < total_cost:
            caller.msg(
                f"|rYou need {total_cost} gold ({amount} deposit + {fee} fee). "
                f"You are carrying {carried} gold.|n"
            )
            return

        # Perform the deposit
        caller.attributes.add("money", carried - total_cost)
        current_bank = caller.attributes.get("bank_gold", default=0)
        caller.attributes.add("bank_gold", current_bank + amount)

        caller.msg(
            f"|gYou deposit {amount} gold into your bank account. (Fee: {fee} gold)|n\n"
            f"|cBank Balance: |w{current_bank + amount} gold|n\n"
            f"|cCarried: |w{carried - total_cost} gold|n"
        )

    def _has_bank_teller(self):
        """Check if there is a Bank Teller NPC in the caller's current room."""
        location = self.caller.location
        if not location:
            return False
        for obj in location.contents:
            if obj.attributes.get("is_bank_teller", default=False):
                return True
        return False


class CmdWithdraw(Command):
    """
    Withdraw gold from your bank account.

    Usage:
      withdraw <amount>

    You must be in a room with a Bank Teller to use this command.
    """

    key = "withdraw"
    aliases = ["wd"]
    help_category = "Banking"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        # Check for bank teller in the room
        if not self._has_bank_teller():
            caller.msg("|rYou must be at a bank to withdraw gold.|n")
            return

        if not args:
            caller.msg("|yUsage: withdraw <amount>|n")
            return

        try:
            amount = int(args)
        except ValueError:
            caller.msg("|rInvalid amount. Use a number.|n")
            return

        if amount <= 0:
            caller.msg("|rYou must withdraw a positive amount.|n")
            return

        bank_balance = caller.attributes.get("bank_gold", default=0)

        if amount > bank_balance:
            caller.msg(
                f"|rYou don't have that much gold in the bank. "
                f"Your bank balance is {bank_balance} gold.|n"
            )
            return

        if bank_balance == 0:
            caller.msg("|yYou have no gold in the bank to withdraw.|n")
            return

        # Perform the withdrawal
        caller.attributes.add("bank_gold", bank_balance - amount)
        carried = caller.attributes.get("money", default=0)
        caller.attributes.add("money", carried + amount)

        caller.msg(
            f"|gYou withdraw {amount} gold from your bank account.|n\n"
            f"|cBank Balance: |w{bank_balance - amount} gold|n\n"
            f"|cCarried: |w{carried + amount} gold|n"
        )

    def _has_bank_teller(self):
        """Check if there is a Bank Teller NPC in the caller's current room."""
        location = self.caller.location
        if not location:
            return False
        for obj in location.contents:
            if obj.attributes.get("is_bank_teller", default=False):
                return True
        return False


class CmdBalance(Command):
    """
    Check your bank balance and carried gold.

    Usage:
      balance
      bank

    You do NOT need to be at a bank to check your balance.
    """

    key = "balance"
    aliases = ["bank"]
    help_category = "Banking"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        from world.economy import display_wealth

        caller.msg(
            f"|y{'=' * 40}|n\n"
            f"{display_wealth(caller)}\n"
            f"|y{'=' * 40}|n"
        )
