#!/usr/bin/env python
"""Debug the give_item and encumbrance test failures."""
import os, sys
sys.path.insert(0, "/root/rop/rop")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
import django
django.setup()

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultObject
from evennia import create_object
from typeclasses.accounts import Account
from typeclasses.characters import Character
from typeclasses.rooms import Room
from typeclasses.exits import Exit
from typeclasses.objects import Object

class GameEvenniaTest(BaseEvenniaTest):
    account_typeclass = Account
    character_typeclass = Character
    room_typeclass = Room
    exit_typeclass = Exit
    object_typeclass = Object

class TestDebug(GameEvenniaTest):
    def test_01_encumbrance_stats(self):
        from world.encumbrance import get_carry_capacity, _get_stats
        self.char1.attributes.add("stats", {"str": 8, "dex": 10, "con": 10, "int": 14, "wis": 12, "cha": 10})
        self.char2.attributes.add("stats", {"str": 18, "dex": 14, "con": 14, "int": 8, "wis": 8, "cha": 6})
        s1 = _get_stats(self.char1)
        s2 = _get_stats(self.char2)
        print("CHAR1 stats:", s1)
        print("CHAR2 stats:", s2)
        print("CHAR1 cap:", get_carry_capacity(self.char1))
        print("CHAR2 cap:", get_carry_capacity(self.char2))

    def test_02_give_item_debug(self):
        from commands.drop import CmdGive
        self.char1.location = self.room1
        self.char2.location = self.room1
        item = create_object(DefaultObject, key="Rusty Sword", location=self.char1)
        item.attributes.add("value", 10)
        print("char1 has_account:", self.char1.has_account)
        print("char2 has_account:", self.char2.has_account)
        print("char2 key:", self.char2.key)
        print("room contents keys:", [o.key for o in self.room1.contents])
        cmd = CmdGive()
        cmd.caller = self.char1
        cmd.cmdstring = "give"
        cmd.args = f"rusty sword to {self.char2.key}"
        cmd.parse()
        print("args_raw:", cmd.args_raw)
        cmd.func()
        print("char1 contents after:", [o.key for o in self.char1.contents])
        print("char2 contents after:", [o.key for o in self.char2.contents])

if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)