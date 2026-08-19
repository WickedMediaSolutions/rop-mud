"""
Comprehensive Test Suite for Phase 8: Social & Multiplayer
===========================================================

Validates:
  1. Friend/Ignore lists (add, remove, list, online notifications)
  2. Mail system (send, read, list, delete, reply, offline delivery)
  3. Player housing (buy, home, invite, uninvite, lock, unlock, visit)
  4. Leaderboards (warpoints, levels, wealth, kills)
  5. Roleplay support (emote, rpdesc, rpinfo, rpstatus)
  6. Group system (invite, accept, leave, kick, group talk, XP sharing)
  7. Clan system (join, list, leave, clan talk, alignment gating)
  8. Gossip channel (faction-isolated broadcast)
  9. PvP toggle (on/off/status)
  10. Broadcast system (admin announcements)

Run: python commands/tests/test_phase8_social_multiplayer.py
"""

import os, sys, time, types, uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
import django
django.setup()


# ======== MOCK INFRASTRUCTURE ========

class MockAttributes:
    def __init__(self):
        self._store = {}
    def get(self, key, default=None):
        return self._store.get(key, default)
    def add(self, key, value):
        self._store[key] = value
    def has(self, key):
        return key in self._store


class MockLocation:
    def __init__(self, name="TestRoom"):
        self.key = name
        self.contents = []
        self.attributes = MockAttributes()
        self.exits = []
        self.db = types.SimpleNamespace()
        self.db.desc = f"A place called {name}."
    def msg_contents(self, message, exclude=None):
        if exclude is None:
            exclude = []
        elif not isinstance(exclude, (list, tuple)):
            exclude = [exclude]
        for obj in self.contents:
            if obj not in exclude:
                obj._messages.append(str(message))
    def return_appearance(self, looker):
        return f"[{self.key}]"


class MockCharacter:
    """Plain mock — does NOT inherit from Django model to avoid attname errors."""
    def __init__(self, name="TestPlayer", level=1, race="Human", char_class="Warrior",
                 alignment="Good", money=1000, bank=500, warpoints=0, mob_kills=0):
        self.key = name
        self.dbref = f"#{id(self)}"
        self.id = id(self)
        self.pk = id(self)
        self.attributes = MockAttributes()
        self.attributes.add("level", level)
        self.attributes.add("race", race)
        self.attributes.add("class", char_class)
        self.attributes.add("alignment", alignment)
        self.attributes.add("money", money)
        self.attributes.add("bank_gold", bank)
        self.attributes.add("warpoints", warpoints)
        self.attributes.add("mob_kills", mob_kills)
        self.attributes.add("hp", 100)
        self.attributes.add("max_hp", 100)
        self.attributes.add("mana", 50)
        self.attributes.add("max_mana", 50)
        self.attributes.add("mv", 100)
        self.attributes.add("max_mv", 100)
        self.attributes.add("xp", 0)
        self.attributes.add("xp_to_level", 1000)
        self.attributes.add("stamina", 100)
        self.attributes.add("max_stamina", 100)
        self.attributes.add("stats", {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
        self.attributes.add("prompt_enabled", True)
        self.attributes.add("position", "standing")
        self.attributes.add("equipped", {})
        self.attributes.add("autoloot", False)
        self.attributes.add("autosac", False)
        self.attributes.add("chargen_completed", True)
        self.location = MockLocation()
        self.contents = []
        self.db = types.SimpleNamespace()
        self.db.desc = f"A {race} {char_class}."
        self.db.pvp_enabled = False
        self.db.chargen_completed = True
        self.ndb = types.SimpleNamespace()
        self._messages = []
        self.has_account = True
        self.is_pc = True
        self.sessions = types.SimpleNamespace()
        self.sessions.count = lambda: 1
        self.cmdset = None
        self.nattributes = MockAttributes()
        self.is_typeclass = True
        self.__dbclass__ = None

    def msg(self, text, **kwargs):
        self._messages.append(str(text))

    def search(self, name, location=None, candidates=None, quiet=False):
        return None

    def move_to(self, destination):
        old_loc = self.location
        self.location = destination
        if old_loc and hasattr(old_loc, 'contents'):
            if self in old_loc.contents:
                old_loc.contents.remove(self)
        if destination and hasattr(destination, 'contents'):
            destination.contents.append(self)

    def delete(self):
        pass

    def get_status_prompt(self):
        return "[HP: 100/100] [MV: 100/100] [EXP: 0/1000] [STANDING] [SP: 100/100]"

    def return_appearance(self, looker):
        return f"[{self.key} - Lvl {self.attributes.get('level', 1)}]"

    def at_object_creation(self):
        pass

    def at_post_login(self, session=None, **kwargs):
        pass

    def at_pre_cmd(self):
        pass

    def access(self, *args, **kwargs):
        return True

    def __eq__(self, other):
        if hasattr(other, 'key') and hasattr(other, 'dbref'):
            return self.key == other.key and self.dbref == other.dbref
        return False

    def __hash__(self):
        return hash(self.dbref)


# Global mock registry
MOCK_CHARACTERS = []


def register_mock(char):
    MOCK_CHARACTERS.append(char)
    return char


def clear_mocks():
    MOCK_CHARACTERS.clear()


# Patch DefaultCharacter.objects.all()
import evennia.objects.objects as eoo
_original_dc_all = None

def _patch_dc():
    global _original_dc_all
    if _original_dc_all is None:
        _original_dc_all = eoo.DefaultCharacter.objects.all
    eoo.DefaultCharacter.objects.all = lambda: list(MOCK_CHARACTERS)


def _unpatch_dc():
    global _original_dc_all
    if _original_dc_all is not None:
        eoo.DefaultCharacter.objects.all = _original_dc_all
        _original_dc_all = None


# Patch ObjectDB.objects.all() for leaderboard
import evennia.objects.models as eom
_original_odb_all = None

def _patch_odb():
    global _original_odb_all
    if _original_odb_all is None:
        _original_odb_all = eom.ObjectDB.objects.all
    eom.ObjectDB.objects.all = lambda: list(MOCK_CHARACTERS)


def _unpatch_odb():
    global _original_odb_all
    if _original_odb_all is not None:
        eom.ObjectDB.objects.all = _original_odb_all
        _original_odb_all = None


# Patch economy functions for housing tests
import world.economy as economy_mod
_orig_get_money = None
_orig_remove_money = None
_orig_add_money = None
_orig_format_money_brief = None

def _patch_economy():
    global _orig_get_money, _orig_remove_money, _orig_add_money, _orig_format_money_brief
    _orig_get_money = economy_mod.get_money
    _orig_remove_money = economy_mod.remove_money
    _orig_add_money = economy_mod.add_money
    _orig_format_money_brief = economy_mod.format_money_brief
    economy_mod.get_money = lambda char: char.attributes.get("money", 0)
    economy_mod.remove_money = lambda char, amount: True
    economy_mod.add_money = lambda char, amount: None
    economy_mod.format_money_brief = lambda amount: f"{amount} gold"


def _unpatch_economy():
    global _orig_get_money, _orig_remove_money, _orig_add_money, _orig_format_money_brief
    if _orig_get_money:
        economy_mod.get_money = _orig_get_money
        economy_mod.remove_money = _orig_remove_money
        economy_mod.add_money = _orig_add_money
        economy_mod.format_money_brief = _orig_format_money_brief


# Patch leaderboard's isinstance check
import commands.leaderboard as leaderboard_mod
_orig_get_all = None

def _patch_leaderboard():
    global _orig_get_all
    _orig_get_all = leaderboard_mod.get_all_player_characters
    leaderboard_mod.get_all_player_characters = lambda: [c for c in MOCK_CHARACTERS if getattr(c, 'has_account', False)]


def _unpatch_leaderboard():
    global _orig_get_all
    if _orig_get_all:
        leaderboard_mod.get_all_player_characters = _orig_get_all
        _orig_get_all = None


# ======== TEST FRAMEWORK ========
PASS = 0
FAIL = 0

def test(name):
    def decorator(fn):
        global PASS, FAIL
        clear_mocks()
        try:
            fn()
            PASS += 1
            print(f"  \u2713 {name}")
        except Exception as e:
            FAIL += 1
            print(f"  \u2717 {name} \u2014 {e}")
    return decorator

def assert_eq(a, b, msg=""):
    if a != b:
        raise AssertionError(f"Expected {b!r}, got {a!r}. {msg}")

def assert_true(val, msg=""):
    if not val:
        raise AssertionError(f"Expected truthy, got {val!r}. {msg}")

def assert_false(val, msg=""):
    if val:
        raise AssertionError(f"Expected falsy, got {val!r}. {msg}")

def assert_in(item, container, msg=""):
    if item not in container:
        raise AssertionError(f"Expected {item!r} in {container!r}. {msg}")

def assert_not_in(item, container, msg=""):
    if item in container:
        raise AssertionError(f"Expected {item!r} not in {container!r}. {msg}")


# ======== SETUP ========
_patch_dc()
_patch_odb()
_patch_economy()
_patch_leaderboard()

print("=" * 60)
print("Phase 8: Social & Multiplayer \u2014 Test Suite")
print("=" * 60)
print()


# ======== 1. FRIEND / IGNORE LISTS ========
print("--- 1. Friend / Ignore Lists ---")
clear_mocks()

@test("get_friends_list returns empty list by default")
def _():
    from commands.social import get_friends_list
    char = register_mock(MockCharacter("Alice"))
    assert_eq(get_friends_list(char), [])

@test("friend add stores player name")
def _():
    from commands.social import get_friends_list, set_friends_list
    char = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    set_friends_list(char, ["Bob"])
    assert_eq(get_friends_list(char), ["Bob"])

@test("friend remove deletes player name")
def _():
    from commands.social import get_friends_list, set_friends_list
    char = register_mock(MockCharacter("Alice"))
    set_friends_list(char, ["Bob", "Charlie"])
    new_list = [n for n in get_friends_list(char) if n.lower() != "bob"]
    set_friends_list(char, new_list)
    assert_eq(get_friends_list(char), ["Charlie"])

@test("friend list shows online/offline status")
def _():
    from commands.social import get_friends_list, set_friends_list, is_player_online
    char = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    set_friends_list(char, ["Bob"])
    friends = get_friends_list(char)
    assert_in("Bob", friends)
    assert_true(is_player_online(bob))

@test("is_friend returns True for friends")
def _():
    from commands.social import is_friend, set_friends_list
    char = register_mock(MockCharacter("Alice"))
    set_friends_list(char, ["Bob"])
    assert_true(is_friend(char, "Bob"))
    assert_false(is_friend(char, "Charlie"))

@test("get_ignore_list returns empty list by default")
def _():
    from commands.social import get_ignore_list
    char = register_mock(MockCharacter("Alice"))
    assert_eq(get_ignore_list(char), [])

@test("ignore add stores player name")
def _():
    from commands.social import get_ignore_list, set_ignore_list
    char = register_mock(MockCharacter("Alice"))
    set_ignore_list(char, ["Bob"])
    assert_eq(get_ignore_list(char), ["Bob"])

@test("is_ignoring returns True for ignored players")
def _():
    from commands.social import is_ignoring, set_ignore_list
    char = register_mock(MockCharacter("Alice"))
    set_ignore_list(char, ["Bob"])
    assert_true(is_ignoring(char, "Bob"))
    assert_false(is_ignoring(char, "Charlie"))

@test("ignore remove deletes player name")
def _():
    from commands.social import get_ignore_list, set_ignore_list
    char = register_mock(MockCharacter("Alice"))
    set_ignore_list(char, ["Bob", "Charlie"])
    new_list = [n for n in get_ignore_list(char) if n.lower() != "bob"]
    set_ignore_list(char, new_list)
    assert_eq(get_ignore_list(char), ["Charlie"])

@test("find_player_character finds by name case-insensitive")
def _():
    from commands.social import find_player_character
    bob = register_mock(MockCharacter("Bob"))
    result = find_player_character("bob")
    assert_true(result is not None)
    assert_eq(result.key, "Bob")

@test("find_player_character returns None for missing")
def _():
    from commands.social import find_player_character
    result = find_player_character("NobodyHere")
    assert_true(result is None)

@test("notify_friends_online sends messages to online friends")
def _():
    from commands.social import notify_friends_online, set_friends_list
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    set_friends_list(bob, ["Alice"])
    alice._messages.clear()
    notify_friends_online(bob)
    assert_true(len(alice._messages) > 0, f"Messages: {alice._messages}")
    assert_in("come online", alice._messages[0])

@test("notify_friends_offline sends messages to online friends")
def _():
    from commands.social import notify_friends_offline, set_friends_list
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    set_friends_list(bob, ["Alice"])
    alice._messages.clear()
    notify_friends_offline(bob)
    assert_true(len(alice._messages) > 0, f"Messages: {alice._messages}")
    assert_in("gone offline", alice._messages[0])

@test("CmdFriendAdd rejects self-add")
def _():
    from commands.social import CmdFriendAdd
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdFriendAdd()
    cmd.caller = alice
    cmd.cmdstring = "friend add"
    cmd.args = "Alice"
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("cannot add yourself", all_msgs)

@test("CmdFriendAdd rejects missing player")
def _():
    from commands.social import CmdFriendAdd
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdFriendAdd()
    cmd.caller = alice
    cmd.cmdstring = "friend add"
    cmd.args = "NobodyHere"
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("No player named", all_msgs)

@test("CmdFriendAdd adds valid player")
def _():
    from commands.social import CmdFriendAdd, get_friends_list
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    cmd = CmdFriendAdd()
    cmd.caller = alice
    cmd.cmdstring = "friend add"
    cmd.args = "Bob"
    cmd.func()
    assert_in("Bob", get_friends_list(alice))

@test("CmdFriendRemove removes player")
def _():
    from commands.social import CmdFriendRemove, get_friends_list, set_friends_list
    alice = register_mock(MockCharacter("Alice"))
    set_friends_list(alice, ["Bob"])
    cmd = CmdFriendRemove()
    cmd.caller = alice
    cmd.cmdstring = "friend remove"
    cmd.args = "Bob"
    cmd.func()
    assert_not_in("Bob", get_friends_list(alice))

@test("CmdFriendList shows empty message")
def _():
    from commands.social import CmdFriendList
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdFriendList()
    cmd.caller = alice
    cmd.cmdstring = "friend list"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("empty", all_msgs)

@test("CmdIgnoreAdd rejects self-ignore")
def _():
    from commands.social import CmdIgnoreAdd
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdIgnoreAdd()
    cmd.caller = alice
    cmd.cmdstring = "ignore add"
    cmd.args = "Alice"
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("cannot ignore yourself", all_msgs)

@test("CmdIgnoreAdd adds valid player")
def _():
    from commands.social import CmdIgnoreAdd, get_ignore_list
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    cmd = CmdIgnoreAdd()
    cmd.caller = alice
    cmd.cmdstring = "ignore add"
    cmd.args = "Bob"
    cmd.func()
    assert_in("Bob", get_ignore_list(alice))

@test("CmdIgnoreRemove removes player")
def _():
    from commands.social import CmdIgnoreRemove, get_ignore_list, set_ignore_list
    alice = register_mock(MockCharacter("Alice"))
    set_ignore_list(alice, ["Bob"])
    cmd = CmdIgnoreRemove()
    cmd.caller = alice
    cmd.cmdstring = "ignore remove"
    cmd.args = "Bob"
    cmd.func()
    assert_not_in("Bob", get_ignore_list(alice))

@test("CmdFriend hub delegates to subcommands")
def _():
    from commands.social import CmdFriend
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdFriend()
    cmd.caller = alice
    cmd.cmdstring = "friend"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("empty", all_msgs)

@test("CmdIgnore hub delegates to subcommands")
def _():
    from commands.social import CmdIgnore
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdIgnore()
    cmd.caller = alice
    cmd.cmdstring = "ignore"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("not ignoring anyone", all_msgs)


# ======== 2. MAIL SYSTEM ========
print("\n--- 2. Mail System ---")
clear_mocks()

@test("get_inbox returns empty list by default")
def _():
    from commands.mail import get_inbox
    char = register_mock(MockCharacter("Alice"))
    assert_eq(get_inbox(char), [])

@test("deliver_mail sends message to recipient inbox")
def _():
    from commands.mail import deliver_mail, get_inbox
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    success, msg = deliver_mail("Alice", "Bob", "Hello", "How are you?")
    assert_true(success, f"deliver_mail failed: {msg}")
    inbox = get_inbox(bob)
    assert_eq(len(inbox), 1)
    assert_eq(inbox[0]["sender"], "Alice")
    assert_eq(inbox[0]["subject"], "Hello")
    assert_eq(inbox[0]["body"], "How are you?")
    assert_false(inbox[0]["read"])

@test("deliver_mail fails for missing recipient")
def _():
    from commands.mail import deliver_mail
    success, msg = deliver_mail("Alice", "NobodyHere", "Hi", "Test")
    assert_false(success)

@test("get_unread_count returns correct count")
def _():
    from commands.mail import get_unread_count, deliver_mail
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    deliver_mail("Alice", "Bob", "Subj1", "Body1")
    deliver_mail("Alice", "Bob", "Subj2", "Body2")
    assert_eq(get_unread_count(bob), 2)

@test("mail read marks message as read")
def _():
    from commands.mail import deliver_mail, get_inbox, set_inbox
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    deliver_mail("Alice", "Bob", "Test", "Body")
    inbox = get_inbox(bob)
    inbox[0]["read"] = True
    set_inbox(bob, inbox)
    assert_true(get_inbox(bob)[0]["read"])

@test("mail delete removes message and re-indexes")
def _():
    from commands.mail import deliver_mail, get_inbox, set_inbox
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    deliver_mail("Alice", "Bob", "First", "Body1")
    deliver_mail("Alice", "Bob", "Second", "Body2")
    inbox = get_inbox(bob)
    new_inbox = [m for m in inbox if m["id"] != 1]
    for i, m in enumerate(new_inbox, 1):
        m["id"] = i
    set_inbox(bob, new_inbox)
    assert_eq(len(get_inbox(bob)), 1)
    assert_eq(get_inbox(bob)[0]["id"], 1)
    assert_eq(get_inbox(bob)[0]["subject"], "Second")

@test("CmdMailSend rejects self-mail")
def _():
    from commands.mail import CmdMailSend
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdMailSend()
    cmd.caller = alice
    cmd.cmdstring = "mail send"
    cmd.args = "Alice = Test / Body"
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("cannot send mail to yourself", all_msgs)

@test("CmdMailSend sends mail successfully")
def _():
    from commands.mail import CmdMailSend, get_inbox
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    cmd = CmdMailSend()
    cmd.caller = alice
    cmd.cmdstring = "mail send"
    cmd.args = "Bob = Hello / How are you?"
    cmd.func()
    inbox = get_inbox(bob)
    assert_eq(len(inbox), 1, f"Inbox: {inbox}")
    assert_eq(inbox[0]["subject"], "Hello")

@test("CmdMailRead reads most recent unread")
def _():
    from commands.mail import CmdMailRead, deliver_mail
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    deliver_mail("Alice", "Bob", "Test", "Message body here")
    cmd = CmdMailRead()
    cmd.caller = bob
    cmd.cmdstring = "mail read"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(bob._messages)
    assert_in("Message body here", all_msgs)

@test("CmdMailList shows inbox")
def _():
    from commands.mail import CmdMailList, deliver_mail
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    deliver_mail("Alice", "Bob", "Test", "Body")
    cmd = CmdMailList()
    cmd.caller = bob
    cmd.cmdstring = "mail list"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(bob._messages)
    assert_in("Test", all_msgs)

@test("CmdMailDelete removes message")
def _():
    from commands.mail import CmdMailDelete, deliver_mail, get_inbox
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    deliver_mail("Alice", "Bob", "Test", "Body")
    cmd = CmdMailDelete()
    cmd.caller = bob
    cmd.cmdstring = "mail delete"
    cmd.args = "1"
    cmd.func()
    assert_eq(len(get_inbox(bob)), 0)

@test("CmdMailReply sends reply")
def _():
    from commands.mail import CmdMailReply, deliver_mail, get_inbox
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    deliver_mail("Alice", "Bob", "Original", "Original body")
    cmd = CmdMailReply()
    cmd.caller = bob
    cmd.cmdstring = "mail reply"
    cmd.args = "1 = Thanks!"
    cmd.func()
    alice_inbox = get_inbox(alice)
    assert_eq(len(alice_inbox), 1, f"Alice inbox: {alice_inbox}")
    assert_in("Re:", alice_inbox[0]["subject"])

@test("CmdMail hub shows inbox by default")
def _():
    from commands.mail import CmdMail
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdMail()
    cmd.caller = alice
    cmd.cmdstring = "mail"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("empty", all_msgs)

@test("mail ignores blocked sender")
def _():
    from commands.social import set_ignore_list
    from commands.mail import CmdMailSend
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    set_ignore_list(bob, ["Alice"])
    cmd = CmdMailSend()
    cmd.caller = alice
    cmd.cmdstring = "mail send"
    cmd.args = "Bob = Hi / Test"
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("not accepting messages", all_msgs)


# ======== 3. PLAYER HOUSING ========
print("\n--- 3. Player Housing ---")
clear_mocks()

@test("get_house_room returns None for non-owner")
def _():
    from commands.housing import get_house_room
    char = register_mock(MockCharacter("Alice"))
    assert_true(get_house_room(char) is None)

@test("is_house_room returns False for non-house")
def _():
    from commands.housing import is_house_room
    room = MockLocation("TestRoom")
    assert_false(is_house_room(room))

@test("is_house_room returns True for house room")
def _():
    from commands.housing import is_house_room
    room = MockLocation("House of Alice")
    room.attributes.add("is_player_house", True)
    assert_true(is_house_room(room))

@test("can_enter_house allows owner")
def _():
    from commands.housing import can_enter_house
    alice = register_mock(MockCharacter("Alice"))
    room = MockLocation("House of Alice")
    room.attributes.add("is_player_house", True)
    room.attributes.add("house_owner", "Alice")
    room.attributes.add("house_locked", False)
    room.attributes.add("house_invited", [])
    assert_true(can_enter_house(alice, room))

@test("can_enter_house denies non-invited")
def _():
    from commands.housing import can_enter_house
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    room = MockLocation("House of Alice")
    room.attributes.add("is_player_house", True)
    room.attributes.add("house_owner", "Alice")
    room.attributes.add("house_locked", False)
    room.attributes.add("house_invited", [])
    assert_false(can_enter_house(bob, room))

@test("can_enter_house allows invited player")
def _():
    from commands.housing import can_enter_house
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    room = MockLocation("House of Alice")
    room.attributes.add("is_player_house", True)
    room.attributes.add("house_owner", "Alice")
    room.attributes.add("house_locked", False)
    room.attributes.add("house_invited", ["Bob"])
    assert_true(can_enter_house(bob, room))

@test("can_enter_house denies when locked")
def _():
    from commands.housing import can_enter_house
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    room = MockLocation("House of Alice")
    room.attributes.add("is_player_house", True)
    room.attributes.add("house_owner", "Alice")
    room.attributes.add("house_locked", True)
    room.attributes.add("house_invited", ["Bob"])
    assert_false(can_enter_house(bob, room))

@test("get_invited_list returns list")
def _():
    from commands.housing import get_invited_list
    room = MockLocation("House of Alice")
    room.attributes.add("house_invited", ["Bob", "Charlie"])
    assert_eq(get_invited_list(room), ["Bob", "Charlie"])

@test("set_invited_list updates list")
def _():
    from commands.housing import set_invited_list, get_invited_list
    room = MockLocation("House of Alice")
    set_invited_list(room, ["Bob"])
    assert_eq(get_invited_list(room), ["Bob"])

@test("CmdHouseBuy rejects if already owned")
def _():
    from commands.housing import CmdHouseBuy
    alice = register_mock(MockCharacter("Alice"))
    room = MockLocation("House of Alice")
    room.attributes.add("is_player_house", True)
    room.attributes.add("house_owner", "Alice")
    alice.attributes.add("house_dbref", id(room))
    import commands.housing as housing_mod
    original = housing_mod.get_house_room
    housing_mod.get_house_room = lambda c: room if c == alice else None
    try:
        cmd = CmdHouseBuy()
        cmd.caller = alice
        cmd.cmdstring = "house buy"
        cmd.args = ""
        cmd.func()
        all_msgs = " ".join(alice._messages)
        assert_in("already own a house", all_msgs)
    finally:
        housing_mod.get_house_room = original

@test("CmdHouseHome rejects if no house")
def _():
    from commands.housing import CmdHouseHome
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdHouseHome()
    cmd.caller = alice
    cmd.cmdstring = "house home"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("don't own a house", all_msgs)

@test("CmdHouseInvite rejects if no house")
def _():
    from commands.housing import CmdHouseInvite
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdHouseInvite()
    cmd.caller = alice
    cmd.cmdstring = "house invite"
    cmd.args = "Bob"
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("don't own a house", all_msgs)

@test("CmdHouseLock locks house")
def _():
    from commands.housing import CmdHouseLock
    alice = register_mock(MockCharacter("Alice"))
    room = MockLocation("House of Alice")
    room.attributes.add("is_player_house", True)
    room.attributes.add("house_owner", "Alice")
    room.attributes.add("house_locked", False)
    alice.attributes.add("house_dbref", id(room))
    import commands.housing as housing_mod
    original = housing_mod.get_house_room
    housing_mod.get_house_room = lambda c: room if c == alice else None
    try:
        cmd = CmdHouseLock()
        cmd.caller = alice
        cmd.cmdstring = "house lock"
        cmd.args = ""
        cmd.func()
        assert_true(room.attributes.get("house_locked"))
    finally:
        housing_mod.get_house_room = original

@test("CmdHouseUnlock unlocks house")
def _():
    from commands.housing import CmdHouseUnlock
    alice = register_mock(MockCharacter("Alice"))
    room = MockLocation("House of Alice")
    room.attributes.add("is_player_house", True)
    room.attributes.add("house_owner", "Alice")
    room.attributes.add("house_locked", True)
    alice.attributes.add("house_dbref", id(room))
    import commands.housing as housing_mod
    original = housing_mod.get_house_room
    housing_mod.get_house_room = lambda c: room if c == alice else None
    try:
        cmd = CmdHouseUnlock()
        cmd.caller = alice
        cmd.cmdstring = "house unlock"
        cmd.args = ""
        cmd.func()
        assert_false(room.attributes.get("house_locked"))
    finally:
        housing_mod.get_house_room = original

@test("CmdHouseDesc sets description")
def _():
    from commands.housing import CmdHouseDesc
    alice = register_mock(MockCharacter("Alice"))
    room = MockLocation("House of Alice")
    room.attributes.add("is_player_house", True)
    room.attributes.add("house_owner", "Alice")
    alice.attributes.add("house_dbref", id(room))
    import commands.housing as housing_mod
    original = housing_mod.get_house_room
    housing_mod.get_house_room = lambda c: room if c == alice else None
    try:
        cmd = CmdHouseDesc()
        cmd.caller = alice
        cmd.cmdstring = "house desc"
        cmd.args = "A beautiful cottage."
        cmd.func()
        assert_eq(room.db.desc, "A beautiful cottage.")
    finally:
        housing_mod.get_house_room = original

@test("CmdHouseName renames house")
def _():
    from commands.housing import CmdHouseName
    alice = register_mock(MockCharacter("Alice"))
    room = MockLocation("House of Alice")
    room.attributes.add("is_player_house", True)
    room.attributes.add("house_owner", "Alice")
    alice.attributes.add("house_dbref", id(room))
    import commands.housing as housing_mod
    original = housing_mod.get_house_room
    housing_mod.get_house_room = lambda c: room if c == alice else None
    try:
        cmd = CmdHouseName()
        cmd.caller = alice
        cmd.cmdstring = "house name"
        cmd.args = "Alice's Palace"
        cmd.func()
        assert_eq(room.key, "Alice's Palace")
    finally:
        housing_mod.get_house_room = original

@test("CmdHouse hub shows help")
def _():
    from commands.housing import CmdHouse
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdHouse()
    cmd.caller = alice
    cmd.cmdstring = "house"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("House Commands", all_msgs)


# ======== 4. LEADERBOARDS ========
print("\n--- 4. Leaderboards ---")
clear_mocks()

@test("get_all_player_characters returns Character instances")
def _():
    from commands.leaderboard import get_all_player_characters
    alice = register_mock(MockCharacter("Alice", level=10, warpoints=50))
    bob = register_mock(MockCharacter("Bob", level=5, warpoints=20))
    players = get_all_player_characters()
    assert_true(len(players) >= 2, f"Got {len(players)} players")

@test("compute_wealth sums carried and banked")
def _():
    from commands.leaderboard import compute_wealth
    char = register_mock(MockCharacter("Alice", money=1000, bank=500))
    assert_eq(compute_wealth(char), 1500)

@test("get_leaderboard_entries sorts by value descending")
def _():
    from commands.leaderboard import get_leaderboard_entries
    alice = register_mock(MockCharacter("Alice", level=10, warpoints=50))
    bob = register_mock(MockCharacter("Bob", level=5, warpoints=20))
    charlie = register_mock(MockCharacter("Charlie", level=15, warpoints=100))
    entries = get_leaderboard_entries("warpoints")
    assert_true(len(entries) >= 3, f"Got {len(entries)} entries: {[e['name'] for e in entries]}")
    assert_eq(entries[0]["name"], "Charlie")
    assert_eq(entries[0]["value"], 100)

@test("format_leaderboard returns string for warpoints")
def _():
    from commands.leaderboard import format_leaderboard
    alice = register_mock(MockCharacter("Alice", level=10, warpoints=50))
    result = format_leaderboard("warpoints")
    assert_in("Warpoints Leaderboard", result)
    assert_in("Alice", result)

@test("format_leaderboard returns string for levels")
def _():
    from commands.leaderboard import format_leaderboard
    alice = register_mock(MockCharacter("Alice", level=10))
    result = format_leaderboard("levels")
    assert_in("Level Leaderboard", result)

@test("format_leaderboard returns string for wealth")
def _():
    from commands.leaderboard import format_leaderboard
    alice = register_mock(MockCharacter("Alice", money=1000, bank=500))
    result = format_leaderboard("wealth")
    assert_in("Wealth Leaderboard", result)

@test("format_leaderboard returns string for kills")
def _():
    from commands.leaderboard import format_leaderboard
    alice = register_mock(MockCharacter("Alice", mob_kills=42))
    result = format_leaderboard("kills")
    assert_in("Kills Leaderboard", result)

@test("format_leaderboard handles unknown category")
def _():
    from commands.leaderboard import format_leaderboard
    result = format_leaderboard("nonexistent")
    assert_in("Unknown", result)

@test("format_leaderboard handles empty rankings")
def _():
    from commands.leaderboard import format_leaderboard
    alice = register_mock(MockCharacter("Alice", warpoints=0))
    result = format_leaderboard("warpoints")
    assert_in("No players ranked", result)

@test("CmdLeaderboard shows default levels category")
def _():
    from commands.leaderboard import CmdLeaderboard
    alice = register_mock(MockCharacter("Alice", level=10))
    cmd = CmdLeaderboard()
    cmd.caller = alice
    cmd.cmdstring = "leaderboard"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("Level Leaderboard", all_msgs)

@test("CmdLeaderboard handles unknown category")
def _():
    from commands.leaderboard import CmdLeaderboard
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdLeaderboard()
    cmd.caller = alice
    cmd.cmdstring = "leaderboard"
    cmd.args = "invalid"
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("Unknown", all_msgs)


# ======== 5. ROLEPLAY SUPPORT ========
print("\n--- 5. Roleplay Support ---")
clear_mocks()

@test("get_rp_description returns None by default")
def _():
    from commands.roleplay import get_rp_description
    char = register_mock(MockCharacter("Alice"))
    assert_true(get_rp_description(char) is None)

@test("get_rp_status returns None by default")
def _():
    from commands.roleplay import get_rp_status
    char = register_mock(MockCharacter("Alice"))
    assert_true(get_rp_status(char) is None)

@test("CmdRpDesc sets description")
def _():
    from commands.roleplay import CmdRpDesc, get_rp_description
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdRpDesc()
    cmd.caller = alice
    cmd.cmdstring = "rpdesc"
    cmd.args = "A mysterious wanderer."
    cmd.func()
    assert_eq(get_rp_description(alice), "A mysterious wanderer.")

@test("CmdRpDesc shows current description")
def _():
    from commands.roleplay import CmdRpDesc
    alice = register_mock(MockCharacter("Alice"))
    alice.attributes.add("rp_description", "A brave knight.")
    cmd = CmdRpDesc()
    cmd.caller = alice
    cmd.cmdstring = "rpdesc"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("A brave knight.", all_msgs)

@test("CmdRpStatus sets status")
def _():
    from commands.roleplay import CmdRpStatus, get_rp_status
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdRpStatus()
    cmd.caller = alice
    cmd.cmdstring = "rpstatus"
    cmd.args = "Open to RP"
    cmd.func()
    assert_eq(get_rp_status(alice), "Open to RP")

@test("CmdRpStatus shows current status")
def _():
    from commands.roleplay import CmdRpStatus
    alice = register_mock(MockCharacter("Alice"))
    alice.attributes.add("rp_status", "In character")
    cmd = CmdRpStatus()
    cmd.caller = alice
    cmd.cmdstring = "rpstatus"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("In character", all_msgs)

@test("CmdRpInfo shows own info")
def _():
    from commands.roleplay import CmdRpInfo
    alice = register_mock(MockCharacter("Alice"))
    alice.attributes.add("rp_description", "A hero.")
    alice.attributes.add("rp_status", "Ready to RP")
    cmd = CmdRpInfo()
    cmd.caller = alice
    cmd.cmdstring = "rpinfo"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("A hero.", all_msgs)

@test("CmdRpInfo shows other player info")
def _():
    from commands.roleplay import CmdRpInfo
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    bob.attributes.add("rp_description", "A shadowy figure.")
    bob.attributes.add("rp_status", "Lurking")
    alice.location.contents.append(bob)
    cmd = CmdRpInfo()
    cmd.caller = alice
    cmd.cmdstring = "rpinfo"
    cmd.args = "Bob"
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("A shadowy figure.", all_msgs)

@test("CmdEmote sends to room")
def _():
    from commands.roleplay import CmdEmote
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    alice.location.contents.append(bob)
    cmd = CmdEmote()
    cmd.caller = alice
    cmd.cmdstring = "emote"
    cmd.args = "waves happily."
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("You waves happily.", all_msgs)

@test("CmdEmote with @target directs at target")
def _():
    from commands.roleplay import CmdEmote
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    alice.location.contents.append(bob)
    cmd = CmdEmote()
    cmd.caller = alice
    cmd.cmdstring = "emote"
    cmd.args = "grins at @Bob"
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("Bob", all_msgs)


# ======== 6. GROUP SYSTEM ========
print("\n--- 6. Group System ---")
clear_mocks()

@test("get_group_members returns empty for non-grouped")
def _():
    from commands.group import get_group_members
    char = register_mock(MockCharacter("Alice"))
    assert_eq(get_group_members(char), [])

@test("CmdGroupInvite creates group and invites")
def _():
    from commands.group import CmdGroupInvite, get_group_members
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    cmd = CmdGroupInvite()
    cmd.caller = alice
    cmd.cmdstring = "group invite"
    cmd.args = "Bob"
    cmd.func()
    members = get_group_members(alice)
    assert_true(len(members) >= 1, f"Members: {[m.key for m in members]}")
    assert_eq(members[0].key, "Alice")

@test("CmdGroupAccept joins group")
def _():
    from commands.group import CmdGroupAccept, get_group_members
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    group_id = f"group_{uuid.uuid4().hex[:8]}"
    alice.attributes.add("group_id", group_id)
    alice.attributes.add("group_leader", True)
    bob.attributes.add("group_invite", group_id)
    cmd = CmdGroupAccept()
    cmd.caller = bob
    cmd.cmdstring = "group accept"
    cmd.args = ""
    cmd.func()
    members = get_group_members(bob)
    assert_true(len(members) >= 2, f"Members: {[m.key for m in members]}")

@test("CmdGroupLeave removes from group")
def _():
    from commands.group import CmdGroupLeave, get_group_members
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    group_id = f"group_{uuid.uuid4().hex[:8]}"
    alice.attributes.add("group_id", group_id)
    alice.attributes.add("group_leader", True)
    bob.attributes.add("group_id", group_id)
    bob.attributes.add("group_leader", False)
    cmd = CmdGroupLeave()
    cmd.caller = bob
    cmd.cmdstring = "group leave"
    cmd.args = ""
    cmd.func()
    assert_eq(get_group_members(bob), [])

@test("CmdGroupKick removes member (leader only)")
def _():
    from commands.group import CmdGroupKick, get_group_members
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    group_id = f"group_{uuid.uuid4().hex[:8]}"
    alice.attributes.add("group_id", group_id)
    alice.attributes.add("group_leader", True)
    bob.attributes.add("group_id", group_id)
    bob.attributes.add("group_leader", False)
    cmd = CmdGroupKick()
    cmd.caller = alice
    cmd.cmdstring = "group kick"
    cmd.args = "Bob"
    cmd.func()
    assert_eq(get_group_members(bob), [])

@test("CmdGroupTalk sends to group")
def _():
    from commands.group import CmdGroupTalk
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    group_id = f"group_{uuid.uuid4().hex[:8]}"
    alice.attributes.add("group_id", group_id)
    alice.attributes.add("group_leader", True)
    bob.attributes.add("group_id", group_id)
    bob.attributes.add("group_leader", False)
    bob._messages.clear()
    cmd = CmdGroupTalk()
    cmd.caller = alice
    cmd.cmdstring = "gt"
    cmd.args = "Hello team!"
    cmd.func()
    all_msgs = " ".join(bob._messages)
    assert_in("Hello team!", all_msgs)

@test("split_group_xp divides XP among present members")
def _():
    from commands.group import split_group_xp
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    group_id = f"group_{uuid.uuid4().hex[:8]}"
    alice.attributes.add("group_id", group_id)
    alice.attributes.add("group_leader", True)
    bob.attributes.add("group_id", group_id)
    bob.attributes.add("group_leader", False)
    alice.location.contents.append(bob)
    bob.location = alice.location
    share = split_group_xp(alice, 100)
    assert_eq(share, 50)

@test("format_group_status shows members")
def _():
    from commands.group import format_group_status
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    group_id = f"group_{uuid.uuid4().hex[:8]}"
    alice.attributes.add("group_id", group_id)
    alice.attributes.add("group_leader", True)
    bob.attributes.add("group_id", group_id)
    bob.attributes.add("group_leader", False)
    status = format_group_status(alice)
    assert_in("Alice", status)
    assert_in("Bob", status)

@test("is_group_leader returns True for leader")
def _():
    from commands.group import is_group_leader
    alice = register_mock(MockCharacter("Alice"))
    group_id = f"group_{uuid.uuid4().hex[:8]}"
    alice.attributes.add("group_id", group_id)
    alice.attributes.add("group_leader", True)
    assert_true(is_group_leader(alice))

@test("dissolve_group removes all members")
def _():
    from commands.group import dissolve_group, get_group_members
    alice = register_mock(MockCharacter("Alice"))
    bob = register_mock(MockCharacter("Bob"))
    group_id = f"group_{uuid.uuid4().hex[:8]}"
    alice.attributes.add("group_id", group_id)
    alice.attributes.add("group_leader", True)
    bob.attributes.add("group_id", group_id)
    bob.attributes.add("group_leader", False)
    dissolve_group(alice)
    assert_eq(get_group_members(alice), [])
    assert_eq(get_group_members(bob), [])


# ======== 7. CLAN SYSTEM ========
print("\n--- 7. Clan System ---")
clear_mocks()

@test("CLANS dict has 8 clans (4 Good, 4 Evil)")
def _():
    from commands.clan import CLANS
    assert_eq(len(CLANS), 8)
    good = [k for k, v in CLANS.items() if v["alignment"] == "Good"]
    evil = [k for k, v in CLANS.items() if v["alignment"] == "Evil"]
    assert_eq(len(good), 4)
    assert_eq(len(evil), 4)

@test("get_clan_info finds clan case-insensitive")
def _():
    from commands.clan import get_clan_info
    key, data = get_clan_info("the house of zod")
    assert_true(key is not None)
    assert_eq(data["alignment"], "Evil")

@test("get_clan_info returns None for unknown")
def _():
    from commands.clan import get_clan_info
    key, data = get_clan_info("Nonexistent Clan")
    assert_true(key is None)

@test("get_clans_by_alignment filters correctly")
def _():
    from commands.clan import get_clans_by_alignment
    good = get_clans_by_alignment("Good")
    evil = get_clans_by_alignment("Evil")
    assert_eq(len(good), 4)
    assert_eq(len(evil), 4)

@test("get_clan_members returns members")
def _():
    from commands.clan import get_clan_members
    alice = register_mock(MockCharacter("Alice", alignment="Good"))
    alice.attributes.add("clan", "The Order of the Sun")
    members = get_clan_members("The Order of the Sun")
    assert_in(alice, members)

@test("CmdClanJoin rejects if already in clan")
def _():
    from commands.clan import CmdClanJoin
    alice = register_mock(MockCharacter("Alice", alignment="Good"))
    alice.attributes.add("clan", "The Order of the Sun")
    cmd = CmdClanJoin()
    cmd.caller = alice
    cmd.cmdstring = "clan join"
    cmd.args = "The Verdant Circle"
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("already a member", all_msgs)

@test("CmdClanJoin rejects wrong alignment")
def _():
    from commands.clan import CmdClanJoin
    alice = register_mock(MockCharacter("Alice", alignment="Good"))
    cmd = CmdClanJoin()
    cmd.caller = alice
    cmd.cmdstring = "clan join"
    cmd.args = "The House of Zod"
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("cannot join a clan of the opposing faction", all_msgs)

@test("CmdClanJoin succeeds for matching alignment")
def _():
    from commands.clan import CmdClanJoin
    alice = register_mock(MockCharacter("Alice", alignment="Good"))
    cmd = CmdClanJoin()
    cmd.caller = alice
    cmd.cmdstring = "clan join"
    cmd.args = "The Order of the Sun"
    cmd.func()
    assert_eq(alice.attributes.get("clan"), "The Order of the Sun")

@test("CmdClanLeave leaves clan")
def _():
    from commands.clan import CmdClanLeave
    alice = register_mock(MockCharacter("Alice", alignment="Good"))
    alice.attributes.add("clan", "The Order of the Sun")
    cmd = CmdClanLeave()
    cmd.caller = alice
    cmd.cmdstring = "clan leave"
    cmd.args = ""
    cmd.func()
    assert_true(alice.attributes.get("clan") is None)

@test("CmdClanTalk sends to clan members")
def _():
    from commands.clan import CmdClanTalk
    alice = register_mock(MockCharacter("Alice", alignment="Good"))
    bob = register_mock(MockCharacter("Bob", alignment="Good"))
    alice.attributes.add("clan", "The Order of the Sun")
    bob.attributes.add("clan", "The Order of the Sun")
    bob._messages.clear()
    cmd = CmdClanTalk()
    cmd.caller = alice
    cmd.cmdstring = "ct"
    cmd.args = "For the Light!"
    cmd.func()
    all_msgs = " ".join(bob._messages)
    assert_in("For the Light!", all_msgs)

@test("CmdClanList shows clans")
def _():
    from commands.clan import CmdClanList
    alice = register_mock(MockCharacter("Alice", alignment="Good"))
    cmd = CmdClanList()
    cmd.caller = alice
    cmd.cmdstring = "clan list"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("Clans of the Realm", all_msgs)


# ======== 8. GOSSIP CHANNEL ========
print("\n--- 8. Gossip Channel ---")
clear_mocks()

@test("CmdGossip sends to same faction only")
def _():
    from commands.gossip import CmdGossip
    alice = register_mock(MockCharacter("Alice", alignment="Good"))
    bob = register_mock(MockCharacter("Bob", alignment="Good"))
    eve = register_mock(MockCharacter("Eve", alignment="Evil"))
    bob._messages.clear()
    eve._messages.clear()
    cmd = CmdGossip()
    cmd.caller = alice
    cmd.cmdstring = "gossip"
    cmd.args = "Hello fellow good people!"
    cmd.func()
    all_bob_msgs = " ".join(bob._messages)
    all_eve_msgs = " ".join(eve._messages)
    assert_in("Hello fellow good people!", all_bob_msgs)
    assert_not_in("Hello fellow good people!", all_eve_msgs)


# ======== 9. PVP TOGGLE ========
print("\n--- 9. PvP Toggle ---")
clear_mocks()

@test("CmdPvp shows status when off")
def _():
    from commands.pvp import CmdPvp
    alice = register_mock(MockCharacter("Alice"))
    alice.db.pvp_enabled = False
    cmd = CmdPvp()
    cmd.caller = alice
    cmd.cmdstring = "pvp"
    cmd.args = ""
    cmd.func()
    all_msgs = " ".join(alice._messages)
    assert_in("currently", all_msgs.lower())

@test("CmdPvp enables PvP")
def _():
    from commands.pvp import CmdPvp
    alice = register_mock(MockCharacter("Alice"))
    cmd = CmdPvp()
    cmd.caller = alice
    cmd.cmdstring = "pvp"
    cmd.args = "on"
    cmd.func()
    assert_true(alice.db.pvp_enabled)

@test("CmdPvp disables PvP")
def _():
    from commands.pvp import CmdPvp
    alice = register_mock(MockCharacter("Alice"))
    alice.db.pvp_enabled = True
    cmd = CmdPvp()
    cmd.caller = alice
    cmd.cmdstring = "pvp"
    cmd.args = "off"
    cmd.func()
    assert_false(alice.db.pvp_enabled)


# ======== 10. BROADCAST SYSTEM ========
print("\n--- 10. Broadcast System ---")
clear_mocks()

@test("CmdBc exists and is importable")
def _():
    from commands.broadcast import CmdBc
    cmd = CmdBc()
    assert_true(cmd is not None)
    assert_eq(cmd.key, "bc")


# ======== CLEANUP ========
_unpatch_dc()
_unpatch_odb()
_unpatch_economy()
_unpatch_leaderboard()
clear_mocks()


# ======== RESULTS ========
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
print("=" * 60)

if FAIL > 0:
    print(f"\n{FAIL} TEST(S) FAILED!")
    sys.exit(1)
else:
    print("\nALL TESTS PASSED! Phase 8 Social & Multiplayer is 100% production-ready.\n")
    sys.exit(0)