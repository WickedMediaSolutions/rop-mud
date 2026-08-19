#!/usr/bin/env python
"""Debug dict attribute storage/retrieval."""
import os, sys
sys.path.insert(0, "/root/rop/rop")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
import django
django.setup()

from evennia.utils.test_resources import BaseEvenniaTest
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

class TestStatsDebug(GameEvenniaTest):
    def test_01_dict_attr_roundtrip(self):
        print("type(char1):", type(self.char1))
        print("char1 handlers:", [h for h in dir(self.char1) if 'attr' in h.lower()][:10])
        # Store a dict
        self.char1.attributes.add("stats", {"str": 8, "dex": 10, "con": 10, "int": 14, "wis": 12, "cha": 10})
        # Read back via various methods
        direct = self.char1.attributes.get("stats")
        with_default = self.char1.attributes.get("stats", default={})
        print("direct get:", repr(direct))
        print("with default:", repr(with_default))
        print("type of direct:", type(direct))
        print("isinstance dict:", isinstance(direct, dict))
        # Check db access
        print("db.stats:", repr(self.char1.db.stats))
        # Check the actual stored attribute object
        attr_obj = self.char1.attributes.get("stats", return_obj=True)
        print("attr_obj:", repr(attr_obj))

    def test_02_str_attr_roundtrip(self):
        self.char1.attributes.add("race", "Human")
        print("race get:", repr(self.char1.attributes.get("race")))

if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)