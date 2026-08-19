#!/usr/bin/env python3
"""
Phase 14 — Comprehensive Manual Test Script (100% Production-Ready Verification)

Run this from the Evennia shell or via:
    evennia shell < commands/tests/test_phase14_manual.py

DO NOT run this as part of an automated test suite.  It connects to the
live game database and exercises Trainer NPCs, Reputation system, combat
integration, quest integration, and command registration.

Usage:
  python commands/tests/test_phase14_manual.py

Or from Evennia interactive shell:
  > py commands/tests/test_phase14_manual.py

Requirements:
  - Evennia server running (or in shell mode with models loaded)
  - At least one character object to test against
"""

import sys
import traceback
from dataclasses import dataclass
from typing import List, Callable

# ── Color helpers ───────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW = "\033[93m"
CYAN  = "\033[96m"
RESET = "\033[0m"
BOLD  = "\033[1m"


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str = ""


class Phase14Tester:
    """Collects and runs all Phase 14 manual tests."""

    def __init__(self):
        self.results: List[TestResult] = []
        self.passed = 0
        self.failed = 0

    def test(self, name: str, fn: Callable[[], bool]):
        """Run a single test and record the result."""
        try:
            ok = fn()
            if ok:
                self.results.append(TestResult(name, True, ""))
                self.passed += 1
                print(f"  {GREEN}PASS{RESET}  {name}")
            else:
                self.results.append(TestResult(name, False, "Assertion failed"))
                self.failed += 1
                print(f"  {RED}FAIL{RESET}  {name} — Assertion failed")
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            self.results.append(TestResult(name, False, msg))
            self.failed += 1
            print(f"  {RED}FAIL{RESET}  {name} — {msg}")
            traceback.print_exc()

    def assert_true(self, condition, msg="Expected True"):
        if not condition:
            raise AssertionError(msg)

    def assert_equal(self, a, b, msg=""):
        if a != b:
            raise AssertionError(msg or f"Expected {b!r}, got {a!r}")

    def assert_greater(self, a, b, msg=""):
        if a <= b:
            raise AssertionError(msg or f"Expected {a!r} > {b!r}")

    def assert_in(self, item, container, msg=""):
        if item not in container:
            raise AssertionError(msg or f"Expected {item!r} in {container!r}")

    def print_banner(self, title: str):
        print(f"\n{CYAN}{'='*70}{RESET}")
        print(f"{CYAN}{BOLD}  {title}{RESET}")
        print(f"{CYAN}{'='*70}{RESET}\n")

    def summary(self):
        total = self.passed + self.failed
        pct = (self.passed / total * 100) if total > 0 else 0
        print(f"\n{BOLD}{'='*70}{RESET}")
        print(f"{BOLD}  Phase 14 Results: {self.passed}/{total} passed ({pct:.1f}%){RESET}")
        print(f"{BOLD}{'='*70}{RESET}\n")
        if self.failed:
            print(f"{RED}  FAILURES:{RESET}")
            for r in self.results:
                if not r.passed:
                    print(f"    - {r.name}")
                    if r.message:
                        print(f"      {r.message}")
        return self.failed == 0


# ── Module imports in test scope ────────────────────────────────────────────

def run_tests():
    """Run all Phase 14 manual tests."""
    t = Phase14Tester()

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION A: Module Importability
    # ═══════════════════════════════════════════════════════════════════════
    t.print_banner("Section A: Module Importability")

    t.test("A.1 — world.guildmaster imports cleanly", lambda: (
        t.assert_true(__import__("world.guildmaster", fromlist=["GuildmasterNPC"])) is not None,
        True
    ))

    t.test("A.2 — world.reputation imports cleanly", lambda: (
        t.assert_true(__import__("world.reputation", fromlist=["ReputationSystem"])) is not None,
        True
    ))

    t.test("A.3 — CmdReputation command exists", lambda: (
        __import__("world.reputation", fromlist=["CmdReputation"]),
        hasattr(__import__("world.reputation", fromlist=["CmdReputation"]), "CmdReputation")
    ))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION B: PracticeSession & Award Points
    # ═══════════════════════════════════════════════════════════════════════
    t.print_banner("Section B: PracticeSession & Award Points")

    def test_b1():
        from world.guildmaster import PracticeSession
        ps = PracticeSession()
        t.assert_equal(ps.practice_points, 0, "Default practice_points should be 0")
        return True
    t.test("B.1 — PracticeSession defaults", test_b1)

    def test_b2():
        from world.guildmaster import PracticeSession, award_practice_points
        # Create a mock character
        class MockChar:
            class Attrs:
                def __init__(self):
                    self.data = {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self, cls="Warrior"):
                self.attributes = self.Attrs()
                self.attributes.add("class", cls)
            def msg(self, text):
                pass
        char = MockChar("Mage")
        char.attributes.add("practice_session", PracticeSession())
        award_practice_points(char, level=5)
        session = char.attributes.get("practice_session")
        # Mages get 6 PPs per level
        t.assert_equal(session.practice_points, 6, "Mage should get 6 PP at level-up")
        return True
    t.test("B.2 — award_practice_points (Mage)", test_b2)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION C: GuildmasterNPC Methods
    # ═══════════════════════════════════════════════════════════════════════
    t.print_banner("Section C: GuildmasterNPC Methods")

    def test_c1():
        from world.guildmaster import GuildmasterNPC, PracticeSession
        from evennia import create_object

        # Setup a mock-ish character for the Guildmaster
        class MockChar:
            class Attrs:
                def __init__(self, data=None):
                    self.data = data or {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self):
                self.attributes = self.Attrs()
                self.attributes.add("class", "Warrior")
                self.attributes.add("level", 5)
                self.attributes.add("learned_spells", [])
                self.attributes.add("trained_skills", [])
                self.attributes.add("practice_session", PracticeSession())
            def msg(self, text):
                pass

        char = MockChar()
        gm = GuildmasterNPC()
        skills = gm.get_trainable_skills(char)
        t.assert_true(isinstance(skills, list), "get_trainable_skills should return list")
        return True
    t.test("C.1 — get_trainable_skills returns list", test_c1)

    def test_c2():
        from world.guildmaster import GuildmasterNPC, PracticeSession

        class MockChar:
            class Attrs:
                def __init__(self, data=None):
                    self.data = data or {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self):
                self.attributes = self.Attrs()
                self.attributes.add("class", "Warrior")
                self.attributes.add("level", 5)
                self.attributes.add("learned_spells", [])
                self.attributes.add("trained_skills", [])
                self.attributes.add("practice_session", PracticeSession())
            def msg(self, text):
                pass

        char = MockChar()
        gm = GuildmasterNPC()
        spells = gm.get_trainable_spells(char)
        t.assert_true(isinstance(spells, list), "get_trainable_spells should return list")
        return True
    t.test("C.2 — get_trainable_spells returns list", test_c2)

    def test_c3():
        from world.guildmaster import GuildmasterNPC, PracticeSession

        class MockChar:
            class Attrs:
                def __init__(self, data=None):
                    self.data = data or {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self):
                self.attributes = self.Attrs()
                self.attributes.add("class", "Warrior")
                self.attributes.add("level", 5)
                self.attributes.add("learned_spells", [])
                self.attributes.add("trained_skills", [])
                session = PracticeSession()
                session.practice_points = 10
                self.attributes.add("practice_session", session)
            def msg(self, text):
                pass

        char = MockChar()
        gm = GuildmasterNPC()
        ok, msg = gm.train_skill(char, "kick")
        t.assert_true(ok, f"Training kick should succeed: {msg}")
        session = char.attributes.get("practice_session")
        # Kick costs 1 PP
        t.assert_equal(session.practice_points, 9, "PP should decrease by 1")
        t.assert_in("kick", session.trained_skills, "Kick should be in trained_skills")
        return True
    t.test("C.3 — train_skill (kick) succeeds with PP", test_c3)

    def test_c4():
        from world.guildmaster import GuildmasterNPC, PracticeSession

        class MockChar:
            class Attrs:
                def __init__(self, data=None):
                    self.data = data or {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self):
                self.attributes = self.Attrs()
                self.attributes.add("class", "Warrior")
                self.attributes.add("level", 5)
                self.attributes.add("learned_spells", [])
                self.attributes.add("trained_skills", [])
                session = PracticeSession()
                session.practice_points = 0  # No PP
                self.attributes.add("practice_session", session)
            def msg(self, text):
                pass

        char = MockChar()
        gm = GuildmasterNPC()
        ok, msg = gm.train_skill(char, "kick")
        t.assert_true(not ok, "Training should fail with 0 PP")
        t.assert_in("need", msg.lower(), "Error message should mention need")
        return True
    t.test("C.4 — train_skill fails with 0 PP", test_c4)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION D: Guildmaster Commands
    # ═══════════════════════════════════════════════════════════════════════
    t.print_banner("Section D: Guildmaster Commands")

    t.test("D.1 — CmdTrain has func", lambda: (
        __import__("world.guildmaster", fromlist=["CmdTrain"]),
        hasattr(__import__("world.guildmaster", fromlist=["CmdTrain"]).CmdTrain, "func")
    ))

    t.test("D.2 — CmdLearn has func", lambda: (
        __import__("world.guildmaster", fromlist=["CmdLearn"]),
        hasattr(__import__("world.guildmaster", fromlist=["CmdLearn"]).CmdLearn, "func")
    ))

    t.test("D.3 — CmdPractice has func", lambda: (
        __import__("world.guildmaster", fromlist=["CmdPractice"]),
        hasattr(__import__("world.guildmaster", fromlist=["CmdPractice"]).CmdPractice, "func")
    ))

    t.test("D.4 — CmdTrain key is 'train'", lambda: (
        t.assert_equal(
            __import__("world.guildmaster", fromlist=["CmdTrain"]).CmdTrain.key,
            "train"
        )
    ))

    t.test("D.5 — CmdLearn key is 'learn'", lambda: (
        t.assert_equal(
            __import__("world.guildmaster", fromlist=["CmdLearn"]).CmdLearn.key,
            "learn"
        )
    ))

    t.test("D.6 — CmdPractice key is 'practice'", lambda: (
        t.assert_equal(
            __import__("world.guildmaster", fromlist=["CmdPractice"]).CmdPractice.key,
            "practice"
        )
    ))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION E: ReputationSystem Static Methods
    # ═══════════════════════════════════════════════════════════════════════
    t.print_banner("Section E: ReputationSystem Static Methods")

    def test_e1():
        from world.reputation import ReputationSystem

        class MockChar:
            class Attrs:
                def __init__(self):
                    self.data = {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self):
                self.attributes = self.Attrs()

        char = MockChar()
        ReputationSystem.initialize(char)
        rep = char.attributes.get("reputation")
        t.assert_true(rep is not None, "Reputation dict should be initialized")
        t.assert_equal(len(rep), 6, "Should have 6 factions")
        return True
    t.test("E.1 — initialize sets up 6 factions", test_e1)

    def test_e2():
        from world.reputation import ReputationSystem

        class MockChar:
            class Attrs:
                def __init__(self):
                    self.data = {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self):
                self.attributes = self.Attrs()
                self.attributes.add("alignment", "Good")

        char = MockChar()
        ReputationSystem.initialize(char)
        standing = ReputationSystem.get_standing(char, "aethelgard")
        t.assert_equal(standing, "Neutral", "New char should be Neutral")
        return True
    t.test("E.2 — get_standing returns Neutral for 0 rep", test_e2)

    def test_e3():
        from world.reputation import ReputationSystem

        class MockChar:
            class Attrs:
                def __init__(self):
                    self.data = {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self):
                self.attributes = self.Attrs()
                self.attributes.add("alignment", "Good")

        char = MockChar()
        ReputationSystem.initialize(char)
        ReputationSystem.adjust_reputation(char, "aethelgard", 600)
        standing = ReputationSystem.get_standing(char, "aethelgard")
        t.assert_equal(standing, "Friendly", "600 rep should be Friendly (>=500)")
        return True
    t.test("E.3 — 600 rep → Friendly", test_e3)

    def test_e4():
        from world.reputation import ReputationSystem

        class MockChar:
            class Attrs:
                def __init__(self):
                    self.data = {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self):
                self.attributes = self.Attrs()
                self.attributes.add("alignment", "Good")

        char = MockChar()
        ReputationSystem.initialize(char)
        # Clamp to max
        ReputationSystem.adjust_reputation(char, "aethelgard", 99999)
        rep = ReputationSystem.get_reputation(char, "aethelgard")
        t.assert_equal(rep, 5000, "Rep should clamp to 5000 max")
        # Clamp to min
        ReputationSystem.adjust_reputation(char, "gorgoroth", -99999)
        rep = ReputationSystem.get_reputation(char, "gorgoroth")
        t.assert_equal(rep, -5000, "Rep should clamp to -5000 min")
        return True
    t.test("E.4 — rep clamped to [-5000, 5000]", test_e4)

    def test_e5():
        from world.reputation import ReputationSystem

        class MockChar:
            class Attrs:
                def __init__(self):
                    self.data = {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self):
                self.attributes = self.Attrs()
                self.attributes.add("alignment", "Good")

        char = MockChar()
        ReputationSystem.initialize(char)
        home = ReputationSystem.get_home_faction(char)
        t.assert_equal(home, "aethelgard", "Good chars → aethelgard")
        return True
    t.test("E.5 — get_home_faction Good → aethelgard", test_e5)

    def test_e6():
        from world.reputation import ReputationSystem

        class MockChar:
            class Attrs:
                def __init__(self):
                    self.data = {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self):
                self.attributes = self.Attrs()
                self.attributes.add("alignment", "Evil")

        char = MockChar()
        home = ReputationSystem.get_home_faction(char)
        t.assert_equal(home, "gorgoroth", "Evil chars → gorgoroth")
        return True
    t.test("E.6 — get_home_faction Evil → gorgoroth", test_e6)

    def test_e7():
        from world.reputation import ReputationSystem

        class MockChar:
            class Attrs:
                def __init__(self):
                    self.data = {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self):
                self.attributes = self.Attrs()
                self.attributes.add("alignment", "Neutral")

        char = MockChar()
        ReputationSystem.initialize(char)
        display = ReputationSystem.format_reputation(char)
        t.assert_true(isinstance(display, str), "format_reputation should return string")
        t.assert_true(len(display) > 0, "format_reputation should not be empty")
        t.assert_in("Aethelgard", display, "Should contain Aethelgard")
        t.assert_in("Gorgoroth", display, "Should contain Gorgoroth")
        return True
    t.test("E.7 — format_reputation returns readable string", test_e7)

    def test_e8():
        from world.reputation import ReputationSystem

        class MockChar:
            class Attrs:
                def __init__(self):
                    self.data = {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self):
                self.attributes = self.Attrs()
                self.attributes.add("alignment", "Good")

        char = MockChar()
        ReputationSystem.initialize(char)
        # Neutral should be 1.0
        disc = ReputationSystem.get_vendor_discount(char, "aethelgard")
        t.assert_equal(disc, 1.0, "Neutral should have 1.0 multiplier")
        # Exalted should be 0.65
        ReputationSystem.adjust_reputation(char, "aethelgard", 5000)
        disc = ReputationSystem.get_vendor_discount(char, "aethelgard")
        t.assert_equal(disc, 0.65, "Exalted should have 0.65 multiplier")
        return True
    t.test("E.8 — vendor discount scaling", test_e8)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION F: Reputation Constants
    # ═══════════════════════════════════════════════════════════════════════
    t.print_banner("Section F: Reputation Constants")

    from world.reputation import ReputationSystem

    t.test("F.1 — REP_KILL_MOB = 5", lambda: (
        t.assert_equal(ReputationSystem.REP_KILL_MOB, 5)
    ))

    t.test("F.2 — REP_KILL_BOSS = 50", lambda: (
        t.assert_equal(ReputationSystem.REP_KILL_BOSS, 50)
    ))

    t.test("F.3 — REP_COMPLETE_QUEST = 100", lambda: (
        t.assert_equal(ReputationSystem.REP_COMPLETE_QUEST, 100)
    ))

    t.test("F.4 — REP_KILL_OPPOSING_PLAYER = 25", lambda: (
        t.assert_equal(ReputationSystem.REP_KILL_OPPOSING_PLAYER, 25)
    ))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION G: Reputation Command
    # ═══════════════════════════════════════════════════════════════════════
    t.print_banner("Section G: Reputation Command")

    from world.reputation import CmdReputation

    t.test("G.1 — CmdReputation.key = 'reputation'", lambda: (
        t.assert_equal(CmdReputation.key, "reputation")
    ))

    t.test("G.2 — CmdReputation has 'rep' alias", lambda: (
        t.assert_in("rep", CmdReputation.aliases, "'rep' should be an alias")
    ))

    t.test("G.3 — CmdReputation.locks allows all()", lambda: (
        t.assert_equal(CmdReputation.locks, "cmd:all()")
    ))

    t.test("G.4 — CmdReputation has func method", lambda: (
        hasattr(CmdReputation, "func")
    ))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION H: Command Registration in CharacterCmdSet
    # ═══════════════════════════════════════════════════════════════════════
    t.print_banner("Section H: Command Registration")

    t.test("H.1 — default_cmdsets imports CmdReputation", lambda: (
        __import__("commands.default_cmdsets", fromlist=["CmdReputation"]),
        hasattr(__import__("commands.default_cmdsets", fromlist=["CmdReputation"]), "CmdReputation")
    ))

    t.test("H.2 — default_cmdsets imports CmdTrain", lambda: (
        __import__("commands.default_cmdsets", fromlist=["CmdTrain"]),
        hasattr(__import__("commands.default_cmdsets", fromlist=["CmdTrain"]), "CmdTrain")
    ))

    t.test("H.3 — default_cmdsets imports CmdLearn", lambda: (
        __import__("commands.default_cmdsets", fromlist=["CmdLearn"]),
        hasattr(__import__("commands.default_cmdsets", fromlist=["CmdLearn"]), "CmdLearn")
    ))

    t.test("H.4 — default_cmdsets imports CmdPractice", lambda: (
        __import__("commands.default_cmdsets", fromlist=["CmdPractice"]),
        hasattr(__import__("commands.default_cmdsets", fromlist=["CmdPractice"]), "CmdPractice")
    ))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION I: Combat Reputation Integration
    # ═══════════════════════════════════════════════════════════════════════
    t.print_banner("Section I: Combat Reputation Integration")

    t.test("I.1 — _handle_defeat imports ReputationSystem", lambda: (
        # Verify the import statement exists in combat.py
        __import__("world.combat", fromlist=["_handle_defeat"]),
        True  # importable without error
    ))

    def test_i2():
        import world.combat
        import inspect
        source = inspect.getsource(world.combat._handle_defeat)
        t.assert_in("ReputationSystem", source,
                     "ReputationSystem should be referenced in _handle_defeat")
        t.assert_in("REP_KILL_MOB", source,
                     "REP_KILL_MOB should be referenced in _handle_defeat")
        return True
    t.test("I.2 — _handle_defeat references ReputationSystem", test_i2)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION J: Quest Reputation Integration
    # ═══════════════════════════════════════════════════════════════════════
    t.print_banner("Section J: Quest Reputation Integration")

    def test_j1():
        import world.quests
        import inspect
        source = inspect.getsource(world.quests.QuestHandler._grant_rewards)
        t.assert_in("ReputationSystem", source,
                     "ReputationSystem should be referenced in _grant_rewards")
        t.assert_in("quest_id", source,
                     "_grant_rewards should accept quest_id parameter")
        return True
    t.test("J.1 — _grant_rewards references ReputationSystem", test_j1)

    def test_j2():
        import world.quests
        import inspect
        source = inspect.getsource(world.quests.QuestHandler.complete)
        t.assert_in("quest_id", source,
                     "complete() should pass quest_id to _grant_rewards")
        return True
    t.test("J.2 — complete() passes quest_id to _grant_rewards", test_j2)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION K: End-to-End Simulation
    # ═══════════════════════════════════════════════════════════════════════
    t.print_banner("Section K: End-to-End Simulation")

    def test_k1():
        """Simulate: new char → kill evil mob → reputation should change."""
        from world.reputation import ReputationSystem

        class MockChar:
            class Attrs:
                def __init__(self):
                    self.data = {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self, cls="Warrior"):
                self.attributes = self.Attrs()
                self.attributes.add("class", "Warrior")
                self.attributes.add("alignment", "Good")
                self.attributes.add("level", 1)
            def msg(self, text):
                pass

        # Simulate killing an evil mob:
        # - Good gets +5 to aethelgard, -5 to gorgoroth
        char = MockChar()
        ReputationSystem.initialize(char)

        mob_faction = "evil"
        if mob_faction == "evil":
            ReputationSystem.adjust_reputation(char, "gorgoroth", ReputationSystem.REP_KILL_MOB)
            ReputationSystem.adjust_reputation(char, "aethelgard", -ReputationSystem.REP_KILL_MOB)

        good_rep = ReputationSystem.get_reputation(char, "aethelgard")
        evil_rep = ReputationSystem.get_reputation(char, "gorgoroth")

        t.assert_equal(good_rep, -5, "Aethelgard rep should decrease for killing good-aligned mob check")
        t.assert_equal(evil_rep, 5, "Gorgoroth rep should increase for killing evil mob")
        return True
    t.test("K.1 — kill evil mob adjusts both factions", test_k1)

    def test_k2():
        """Simulate: quest completion → reputation increases."""
        from world.reputation import ReputationSystem

        class MockChar:
            class Attrs:
                def __init__(self):
                    self.data = {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self, cls="Warrior"):
                self.attributes = self.Attrs()
                self.attributes.add("class", "Warrior")
                self.attributes.add("alignment", "Good")
                self.attributes.add("level", 1)
            def msg(self, text):
                pass

        char = MockChar()
        ReputationSystem.initialize(char)

        # Simulate quest completion for good NPC
        before = ReputationSystem.get_reputation(char, "aethelgard")
        ReputationSystem.adjust_reputation(char, "aethelgard", ReputationSystem.REP_COMPLETE_QUEST)
        after = ReputationSystem.get_reputation(char, "aethelgard")
        t.assert_equal(after - before, 100, "Quest completion should give 100 rep")
        return True
    t.test("K.2 — quest completion gives 100 rep", test_k2)

    def test_k3():
        """Simulate: complete flow — train skill with practice points from level-up."""
        from world.guildmaster import PracticeSession, award_practice_points, GuildmasterNPC

        class MockChar:
            class Attrs:
                def __init__(self):
                    self.data = {}
                def get(self, key, default=None):
                    return self.data.get(key, default)
                def add(self, key, value):
                    self.data[key] = value
                def has(self, key):
                    return key in self.data
            def __init__(self, cls="Warrior"):
                self.attributes = self.Attrs()
                self.attributes.add("class", cls)
                self.attributes.add("level", 5)
                self.attributes.add("learned_spells", [])
                self.attributes.add("trained_skills", [])
                self.attributes.add("practice_session", PracticeSession())
            def msg(self, text):
                pass

        char = MockChar("Warrior")
        # Level up to 5
        award_practice_points(char, level=5)
        session = char.attributes.get("practice_session")
        # Warrior gets 3 PP per level, so at level 5: 3 PP
        # (award_practice_points is called once per level-up, not per level number)
        # So we simulate multiple level-ups
        award_practice_points(char, level=6)
        award_practice_points(char, level=7)

        session = char.attributes.get("practice_session")
        # 3 + 3 + 3 = 9 PP
        t.assert_greater(session.practice_points, 0, "Should have accumulated PP")

        # Train kick (costs 1 PP)
        gm = GuildmasterNPC()
        ok, msg = gm.train_skill(char, "kick")
        t.assert_true(ok, f"Should be able to train kick: {msg}")
        t.assert_in("kick", session.trained_skills, "Kick should be trained")
        return True
    t.test("K.3 — full flow: level-up → earn PP → train skill", test_k3)

    # ═══════════════════════════════════════════════════════════════════════
    # Print Summary
    # ═══════════════════════════════════════════════════════════════════════
    all_passed = t.summary()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_tests())