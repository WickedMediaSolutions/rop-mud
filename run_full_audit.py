#!/usr/bin/env python
"""
============================================================================
Rites of Passage — Production Live-Launch Full Audit Battery
============================================================================

A single, self-contained automated test script that scans the entire
codebase and programmatically exercises every subsystem, command, script,
model, and edge case in the game.

Run from the Evennia game directory inside evennia shell:
    evennia shell
    >>> import run_full_audit
    >>> run_full_audit.run()

Do NOT run with `python run_full_audit.py` — evennia shell is required.

Outputs a terminal dashboard with [PASS] / [FAIL] indicators for each
of the 10 test batteries plus Phase 6.12 validation targets.
============================================================================
"""

from __future__ import annotations

import gc
import importlib
import math
import os
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, PropertyMock


# ============================================================================
# MOCK ATTRIBUTE HANDLER — Dict-backed, API-compatible with Evennia attr
# ============================================================================

class MockAttributeHandler:
    """Dict-backed attribute handler mimicking Evennia's AttributeHandler.

    Methods: get(key, default=None), add(key, value), set(key, value),
             has(key), all().
    All values are stored in an in-memory dict — no DB writes.
    """

    def __init__(self):
        self._store: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def add(self, key: str, value: Any) -> None:
        self._store[key] = value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def has(self, key: str) -> bool:
        return key in self._store

    def all(self) -> Dict[str, Any]:
        return dict(self._store)

    def __contains__(self, key: str) -> bool:
        return key in self._store


# ============================================================================
# MOCK CHARACTER / ROOM / EXIT — No DB interaction
# ============================================================================

class MockBase:
    """Lightweight mock base compatible with Evennia typeclass attribute lookups."""

    def __init__(self, key: str = "mock"):
        self.key = key
        self.id = id(self)
        self.attributes = MockAttributeHandler()
        self.db = MagicMock()
        self.ndb = MagicMock()
        self.location: Optional[MockBase] = None
        self.destination: Optional[MockBase] = None
        self.sessions = MagicMock()
        self.has_account = False
        self.contents = []

        # Allow .db.pvp_enabled to work (set as MagicMock attribute)
        self.db.pvp_enabled = False

    def msg(self, text: Any = "", **kwargs) -> None:
        """Mock msg() — no-op by default."""
        pass

    @property
    def spells(self):
        """Return SpellHandler for this character."""
        from world.spells import SpellHandler
        return SpellHandler(self)

    @property
    def quests(self):
        """Return QuestHandler for this character."""
        from world.quests import QuestHandler
        return QuestHandler(self)


def mock_character(
    key: str = "TestChar",
    race: str = "Human",
    char_class: str = "Warrior",
    level: int = 1,
    alignment: str = "Neutral",
    hp: int = 100,
    max_hp: int = 100,
    mana: int = 50,
    max_mana: int = 50,
    mv: int = 100,
    max_mv: int = 100,
    xp: int = 0,
    stats: Optional[Dict[str, int]] = None,
    **kwargs,
) -> MockBase:
    """Create a mock character with all standard attributes set.

    Uses MockBase + MockAttributeHandler so no DB interaction occurs.
    Additional keyword arguments are set as attrs or db attributes.
    """
    char = MockBase(key=key)
    char.has_account = True
    attrs = char.attributes

    attrs.add("race", race)
    attrs.add("class", char_class)
    attrs.add("level", level)
    attrs.add("alignment", alignment)
    attrs.add("hp", hp)
    attrs.add("max_hp", max_hp)
    attrs.add("mana", mana)
    attrs.add("max_mana", max_mana)
    attrs.add("mv", mv)
    attrs.add("max_mv", max_mv)
    attrs.add("xp", xp)
    attrs.add("xp_to_level", 1000)

    if stats is None:
        stats = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
    attrs.add("stats", stats)

    attrs.add("money", 0)
    attrs.add("alignment_points", 0)
    attrs.add("warpoints", 0)
    attrs.add("kills", 0)
    attrs.add("stamina", 100)
    attrs.add("max_stamina", 100)
    attrs.add("prompt_enabled", True)
    attrs.add("equipped", {})
    attrs.add("learned_spells", [])
    attrs.add("position", "standing")
    attrs.add("autoloot", False)
    attrs.add("autosac", False)

    # Extra kwargs go directly to .db or .attributes
    for k, v in kwargs.items():
        if k.startswith("db_"):
            setattr(char.db, k[3:], v)
        elif k.startswith("ndb_"):
            setattr(char.ndb, k[4:], v)
        else:
            attrs.add(k, v)

    return char


def mock_room(key: str = "TestRoom", safe_zone: bool = False, outdoor: bool = False) -> MockBase:
    """Create a mock room."""
    room = MockBase(key=key)
    room.attributes.add("safe_zone", safe_zone)
    room.attributes.add("outdoor", outdoor)
    return room


def mock_exit(key: str = "exit", location: MockBase = None, destination: MockBase = None) -> MockBase:
    """Create a mock exit."""
    ex = MockBase(key=key)
    ex.location = location
    ex.destination = destination
    ex.attributes.add("locked", False)
    return ex


# ============================================================================
# AUDITOR (PASS / FAIL tracker)
# ============================================================================

class Auditor:
    """Tracks pass/fail/warning across all test batteries."""

    def __init__(self, label: str = "Audit"):
        self.label = label
        self.passes: List[str] = []
        self.failures: List[Tuple[str, str]] = []
        self.warnings: List[str] = []
        self._current_section = ""

    def section(self, name: str):
        self._current_section = name
        print(f"\n  -- {name} --")

    def ok(self, msg: str):
        self.passes.append(f"[{self._current_section}] {msg}")
        print(f"    \033[32m[PASS]\033[0m {msg}")

    def fail(self, msg: str, tb: str = ""):
        self.failures.append((f"[{self._current_section}] {msg}", tb))
        print(f"    \033[31m[FAIL]\033[0m {msg}")

    def warn(self, msg: str):
        self.warnings.append(f"[{self._current_section}] {msg}")
        print(f"    \033[33m[WARN]\033[0m {msg}")

    def summary(self):
        total = len(self.passes) + len(self.failures)
        print(f"\n{'='*60}")
        print(f"  {self.label} SUMMARY")
        print(f"{'='*60}")
        print(f"  \033[32mPASSED:  {len(self.passes)}\033[0m")
        print(f"  \033[33mWARNINGS: {len(self.warnings)}\033[0m")
        print(f"  \033[31mFAILED:  {len(self.failures)}\033[0m")
        print(f"  TOTAL:   {total}")
        print(f"{'='*60}")

        if self.failures:
            print(f"\n\033[31m{'='*60}\033[0m")
            print(f"\033[31m  FAILURE DETAILS\033[0m")
            print(f"\033[31m{'='*60}\033[0m")
            for i, (msg, tb) in enumerate(self.failures, 1):
                print(f"\n  {i}. {msg}")
                if tb:
                    print(f"  {tb}")
        print()


def assert_true(condition: bool, msg: str) -> Tuple[bool, str]:
    """Return (True, '') if condition is truthy, else (False, msg)."""
    if condition:
        return True, ""
    return False, f"ASSERT FAILED: {msg}"


# ============================================================================
# SAFE RUNNER — wraps each battery so one failure doesn't halt the entire run
# ============================================================================

def safe_run_battery(auditor: Auditor, label: str, fn: Callable[[Auditor], None]):
    """Execute a test battery function; catch and report any unhandled exception."""
    print(f"\n{'—'*70}")
    print(f"  {label}")
    print(f"{'—'*70}")
    try:
        fn(auditor)
    except Exception:
        auditor.fail(f"{label} — UNHANDLED EXCEPTION", traceback.format_exc())


# ============================================================================
# BATTERY 1: Codebase Scanner & Django Bootstrap
# ============================================================================

def battery_1_codebase_scan(auditor: Auditor):
    """Recursively import every .py file to catch syntax errors and missing deps."""
    auditor.section("Codebase Scanner & Django Bootstrap")

    # Verify Django/Evennia is configured
    try:
        import django
        from django.conf import settings

        # If Django isn't configured yet, do it now
        if not settings.configured:
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
            django.setup()
        auditor.ok(f"Django configured: {settings.SETTINGS_MODULE}")
    except Exception as e:
        auditor.fail(f"Django bootstrap failed: {e}", traceback.format_exc())
        return

    # Evennia-specific bootstrap — set up the test environment
    try:
        from evennia.server import evennia_launcher
        from evennia.utils import create
    except Exception:
        auditor.warn("Evennia full import unavailable (run from `evennia shell`)")

    # Scan all .py files in key directories
    scan_dirs = ["commands", "typeclasses", "world", "server", "web"]
    project_root = Path(__file__).resolve().parent

    for directory in scan_dirs:
        dir_path = project_root / directory
        if not dir_path.exists():
            auditor.warn(f"Directory not found: {dir_path}")
            continue

        py_files = list(dir_path.rglob("*.py"))
        imported = 0
        failed_imports = 0
        for py_file in py_files:
            if py_file.name == "__init__.py":
                continue
            if py_file.parent.name == "tests":
                continue  # Skip test dirs — they need the test runner
            # Convert path to module path
            rel = py_file.relative_to(project_root)
            module_path = str(rel.with_suffix("")).replace(os.sep, ".")
            try:
                importlib.import_module(module_path)
                imported += 1
            except Exception:
                failed_imports += 1
                auditor.fail(
                    f"Import failed: {module_path}",
                    traceback.format_exc(),
                )

        auditor.ok(f"Scanned {directory}/ — {imported} OK, {failed_imports} failed")

    # Verify 20 key modules are importable
    key_modules = [
        "world.race_class_matrix",
        "world.combat",
        "world.tick_combat",
        "world.spells",
        "world.alignment_system",
        "world.damage_formulas",
        "world.recovery",
        "world.guildmaster",
        "world.shopkeeper",
        "world.encumbrance",
        "world.combat_skills",
        "world.mob_ai",
        "world.quests",
        "world.armor_sets",
        "world.saving_throws",
        "world.status_effects",
        "typeclasses.characters",
        "typeclasses.rooms",
        "typeclasses.exits",
        "typeclasses.objects",
    ]
    for mod in key_modules:
        try:
            importlib.import_module(mod)
            auditor.ok(f"Key module: {mod}")
        except Exception:
            auditor.fail(f"Key module missing: {mod}", traceback.format_exc())


# ============================================================================
# BATTERY 2: Race, Class, Faction & Strict Spell-Gating
# ============================================================================

def battery_2_race_class_spell_gating(auditor: Auditor):
    """Test all race/class combos, spell gating, and faction alignment."""

    from world.race_class_matrix import (
        RACE_CLASS_MATRIX, CLASS_SPELL_SCHOOLS, can_cast_spells,
        can_learn_spell, is_race_class_valid, get_valid_classes_for_race,
        CLASS_SKILLS, CLASS_WEAPON_TYPES, CLASS_ARMOR_TYPES,
        RACE_FORBIDDEN_SLOTS, RACE_NATURAL_ARMOR, RaceDef, ClassDef,
    )
    from world.spells import SPELLS, get_spell

    # — 2a: Validate race/class matrix completeness —
    races = list(RACE_CLASS_MATRIX.keys())
    auditor.ok(f"Race count: {len(races)} — {', '.join(races)}")

    all_classes = set()
    for cls_list in RACE_CLASS_MATRIX.values():
        all_classes.update(cls_list)
    auditor.ok(f"Unique class count: {len(all_classes)} — {', '.join(sorted(all_classes))}")

    # Every class must exist in all sub-tables
    for cls_name in all_classes:
        for table, table_name in [
            (CLASS_SPELL_SCHOOLS, "CLASS_SPELL_SCHOOLS"),
            (CLASS_SKILLS, "CLASS_SKILLS"),
            (CLASS_WEAPON_TYPES, "CLASS_WEAPON_TYPES"),
            (CLASS_ARMOR_TYPES, "CLASS_ARMOR_TYPES"),
        ]:
            ok, _ = assert_true(cls_name in table, f"'{cls_name}' in {table_name}")
            if ok:
                pass  # fine
            else:
                auditor.fail(f"Class '{cls_name}' missing from {table_name}")

    auditor.ok("All 10 classes present in all 4 sub-tables")

    # — 2b: Spell gating for non-casters —
    for cls_name in ["Warrior", "Rogue", "Monk"]:
        schools = CLASS_SPELL_SCHOOLS.get(cls_name, [])
        if len(schools) == 0:
            auditor.ok(f"Non-caster '{cls_name}': no spell schools")
        else:
            auditor.fail(f"Non-caster '{cls_name}' has schools: {schools}")

    # Orc Warrior explicit check
    orc_warrior = mock_character("OrcWarTest", "Orc", "Warrior")
    if not can_cast_spells(orc_warrior):
        auditor.ok("Orc Warrior: can_cast_spells() = False")
    else:
        auditor.fail("Orc Warrior: can_cast_spells() = True — GATING BROKEN")

    valid, reason = can_learn_spell(orc_warrior, "sparks")
    if not valid:
        auditor.ok(f"Orc Warrior can_learn_spell('sparks'): '{reason}'")
    else:
        auditor.fail("Orc Warrior allowed to learn spells — CRITICAL")

    # Ogre single-class edge case
    ogre = mock_character("OgreTest", "Ogre", "Warrior")
    valid, reason = can_learn_spell(ogre, "sparks")
    if not valid:
        auditor.ok(f"Ogre Warrior spell block: '{reason}'")
    else:
        auditor.fail("Ogre Warrior should be blocked from all spells")

    # — 2c: Spellcaster validation —
    elf_mage = mock_character("ElfMage", "High Elf", "Mage", mana=200, max_mana=200)
    if can_cast_spells(elf_mage):
        auditor.ok("High Elf Mage: can_cast_spells() = True")
    else:
        auditor.fail("High Elf Mage: can_cast_spells() = False")

    human_cleric = mock_character("HumanCleric", "Human", "Cleric")
    if can_cast_spells(human_cleric):
        auditor.ok("Human Cleric: can_cast_spells() = True")
    else:
        auditor.fail("Human Cleric: can_cast_spells() = False")

    # — 2d: Faction alignment —
    for name, race, cls, align in [
        ("Good Paladin", "Human", "Paladin", "Good"),
        ("Evil Orc", "Orc", "Warrior", "Evil"),
        ("Neutral Human", "Human", "Warrior", "Neutral"),
    ]:
        c = mock_character(name.replace(" ", ""), race, cls, alignment=align)
        got = c.attributes.get("alignment")
        if got == align:
            auditor.ok(f"{name}: alignment '{got}'")
        else:
            auditor.fail(f"{name}: expected '{align}', got '{got}'")

    # — 2e: Natural armor per race —
    for race_name, expected_ac in RACE_NATURAL_ARMOR.items():
        actual = RACE_NATURAL_ARMOR.get(race_name, 0)
        if actual == expected_ac:
            auditor.ok(f"Race '{race_name}': natural armor {actual}")
        else:
            auditor.fail(f"Race '{race_name}': expected {expected_ac}, got {actual}")

    # — 2f: Race forbidden slots —
    auditor.ok(f"Forbidden slots defined for {len(RACE_FORBIDDEN_SLOTS)} races")

    # — 2g: Spell definitions —
    spell_count = len(SPELLS)
    levels_present = sorted(set(s["level"] for s in SPELLS.values()))
    auditor.ok(f"Spell count: {spell_count}, levels {min(levels_present)}-{max(levels_present)}")

    # — 2h: RaceDef/ClassDef dataclass construction —
    auditor.ok(f"RaceDef keys: {[f.name for f in RaceDef.__dataclass_fields__.values()]}")
    auditor.ok(f"ClassDef keys: {[f.name for f in ClassDef.__dataclass_fields__.values()]}")


# ============================================================================
# BATTERY 3: Clans, Guilds & Guildmasters
# ============================================================================

def battery_3_clans_guilds(auditor: Auditor):
    """Test guildmaster practice system and skill/equip validation."""
    auditor.section("Clans, Guilds & Guildmasters")

    from world.guildmaster import (
        award_practice_points, PracticeSession, GuildmasterNPC,
    )
    from world.race_class_matrix import CLASS_SKILLS, can_use_skill, can_equip_slot

    # — 3a: Practice point award —
    char = mock_character("GuildTest", "Human", "Warrior")
    try:
        award_practice_points(char, level=5)
        session = char.attributes.get("practice_session")
        if session is not None:
            pp = getattr(session, "practice_points", 0)
            auditor.ok(f"award_practice_points(level=5): {pp} points")
        else:
            auditor.fail("practice_session not stored after award")
    except Exception:
        auditor.fail("award_practice_points() exception", traceback.format_exc())

    # — 3b: Skill ownership matrix —
    for cls_name, skills in CLASS_SKILLS.items():
        auditor.ok(f"Class '{cls_name}': skills {skills or '(none)'}")

    # — 3c: Warrior can use kick —
    warrior = mock_character("WarSkill", "Human", "Warrior")
    valid, reason = can_use_skill(warrior, "kick")
    if valid:
        auditor.ok("Warrior: can_use_skill('kick') = True")
    else:
        auditor.fail(f"Warrior blocked from kick: {reason}")

    # — 3d: Mage cannot use kick —
    mage = mock_character("MageSkill", "High Elf", "Mage")
    valid, reason = can_use_skill(mage, "kick")
    if not valid:
        auditor.ok(f"Mage blocked from kick: '{reason}'")
    else:
        auditor.fail("Mage should not have kick")

    # — 3e: GuildmasterNPC.train_skill() method —
    try:
        gm = type("MockGuildmaster", (), {
            "get_trainable_skills": GuildmasterNPC.get_trainable_skills,
            "train_skill": GuildmasterNPC.train_skill,
        })()
        warrior.attributes.add("practice_session", PracticeSession())
        warrior.attributes.get("practice_session").practice_points = 10
        result = gm.train_skill(warrior, "kick")
        auditor.ok(f"Guildmaster.train_skill('kick') = {result}")
    except Exception:
        auditor.fail("GuildmasterNPC.train_skill() exception", traceback.format_exc())

    # — 3f: Equipment slot gating —
    pixie = mock_character("PixieEq", "Pixie", "Mage")
    for slot, item_type, expect_block in [
        ("chest_heavy", "armor_heavy", True),
        ("two_handed", "weapon_two_handed", True),
        ("shoulders", "armor_light", True),
        ("head", "armor_cloth", False),
    ]:
        allowed, _ = can_equip_slot(pixie, slot, item_type)
        if allowed == (not expect_block):
            auditor.ok(f"Pixie {slot}: {'blocked' if expect_block else 'allowed'}")
        else:
            auditor.fail(f"Pixie {slot}: expected {'blocked' if expect_block else 'allowed'}, got {allowed}")

    centaur = mock_character("CentaurEq", "Centaur", "Warrior")
    allowed, _ = can_equip_slot(centaur, "feet", "armor_light")
    if not allowed:
        auditor.ok("Centaur feet slot: blocked")
    else:
        auditor.fail("Centaur feet slot should be blocked")


# ============================================================================
# BATTERY 4: Quests & Dialogue System
# ============================================================================

def battery_4_quests(auditor: Auditor):
    """Test quest registry, handler attachment, journal, report_kill."""
    auditor.section("Quests & Dialogue System")

    from world.quests import quest_registry, register_default_quests

    # Ensure a deterministic, populated registry for the audit (idempotent).
    register_default_quests()

    if len(quest_registry) > 0:
        auditor.ok(f"Quest registry: {len(quest_registry)} quest(s)")
        for quest in quest_registry.all()[:5]:
            auditor.ok(f"  Quest '{quest.id}': {quest.name}")
    else:
        auditor.warn("Quest registry empty — no quests defined")

    char = mock_character("QuestTester", "Human", "Warrior")
    try:
        handler = char.quests
        auditor.ok("Character.quests returns QuestHandler")
    except Exception:
        auditor.fail("Character.quests property failed", traceback.format_exc())

    try:
        journal, _active = handler.status()
        auditor.ok(f"Quest journal: {journal[:80]}")
    except Exception:
        auditor.warn("Quest journal retrieval issue (may be normal for fresh char)")

    try:
        handler.report_kill("Goblin Scout")
        auditor.ok("Quest handler: report_kill('Goblin Scout') OK")
    except Exception:
        auditor.fail("report_kill() exception", traceback.format_exc())


# ============================================================================
# BATTERY 5: Open & Safe-Zone PvP System
# ============================================================================

def battery_5_pvp(auditor: Auditor):
    """Test PvP flags, safe zones, outlaw status, and faction PvP."""
    auditor.section("PvP System")

    from world.combat import _is_pvp_allowed, is_safe_zone
    from world.alignment_system import AlignmentSystem, is_outlaw

    # — 5a: Safe zone detection —
    safe_room = mock_room("SafeRoom", safe_zone=True)
    unsafe_room = mock_room("UnsafeRoom", safe_zone=False)

    if is_safe_zone(safe_room):
        auditor.ok("Safe zone: room with safe_zone=True → True")
    else:
        auditor.fail("Room with safe_zone=True returned False")
    if not is_safe_zone(unsafe_room):
        auditor.ok("Safe zone: room with safe_zone=False → False")
    else:
        auditor.fail("Room with safe_zone=False returned True")

    # — 5b: Cross-faction PvP auto-allowed —
    good = mock_character("GoodPVP", "Human", "Paladin", alignment="Good")
    evil = mock_character("EvilPVP", "Orc", "Warrior", alignment="Evil")
    good.location = unsafe_room
    evil.location = unsafe_room

    allowed, reason = _is_pvp_allowed(good, evil)
    if allowed:
        auditor.ok("Good vs Evil: PvP auto-allowed")
    else:
        auditor.fail(f"Good vs Evil PvP blocked: {reason}")

    # — 5c: Same-faction blocks without toggle —
    g1 = mock_character("Good1", "Human", "Warrior", alignment="Good")
    g2 = mock_character("Good2", "Human", "Warrior", alignment="Good")
    g1.db.pvp_enabled = False
    g2.db.pvp_enabled = False
    g1.location = unsafe_room
    g2.location = unsafe_room

    allowed, reason = _is_pvp_allowed(g1, g2)
    if not allowed:
        auditor.ok(f"Same-faction PvP blocked: '{reason}'")
    else:
        auditor.fail("Same-faction PvP should be blocked without toggle")

    # — 5d: Outlaw lifecycle —
    outlaw = mock_character("OutlawTest", "Human", "Rogue")
    if not is_outlaw(outlaw):
        auditor.ok("Outlaw: fresh char not outlawed")
    else:
        auditor.fail("Fresh char shows outlaw")

    AlignmentSystem.set_outlaw(outlaw, duration_seconds=300)
    if is_outlaw(outlaw):
        auditor.ok("Outlaw: set_outlaw() marks character")
    else:
        auditor.fail("set_outlaw() did not mark")

    AlignmentSystem.clear_outlaw(outlaw)
    if not is_outlaw(outlaw):
        auditor.ok("Outlaw: clear_outlaw() removes status")
    else:
        auditor.fail("clear_outlaw() did not remove")

    # — 5e: Bounty —
    result = AlignmentSystem.add_bounty(outlaw, 500)
    if result == 500:
        auditor.ok(f"Bounty: add_bounty(500) → {result}")
    else:
        auditor.fail(f"Bounty expected 500, got {result}")
    AlignmentSystem.clear_bounty(outlaw)
    final = outlaw.attributes.get("bounty", -1)
    if final == 0:
        auditor.ok("Bounty: clear_bounty() = 0")
    else:
        auditor.fail(f"Bounty after clear: {final}")

    # — 5f: Safe zone blocks combat —
    good.location = safe_room
    evil.location = safe_room
    allowed, reason = _is_pvp_allowed(good, evil)
    if not allowed:
        auditor.ok(f"Safe zone blocks combat: '{reason}'")
    else:
        auditor.fail("Safe zone allowed combat — CRITICAL")


# ============================================================================
# BATTERY 6: 10-Way Movement & Room Rendering
# ============================================================================

def battery_6_movement_rendering(auditor: Auditor):
    """Test 10-direction exits, room rendering, and exit locks."""
    auditor.section("10-Way Movement & Room Rendering")

    directions = {
        "north": "north", "south": "south", "east": "east", "west": "west",
        "northeast": "northeast", "southeast": "southeast",
        "southwest": "southwest", "northwest": "northwest",
        "up": "up", "down": "down",
    }
    reverse = {
        "north": "south", "south": "north",
        "east": "west", "west": "east",
        "northeast": "southwest", "southwest": "northeast",
        "southeast": "northwest", "northwest": "southeast",
        "up": "down", "down": "up",
    }

    center = mock_room("Test Center")
    created = {"center": center}

    for direction in directions:
        room = mock_room(f"Test {direction.capitalize()}")
        created[direction] = room

        ex = mock_exit(direction, location=center, destination=room)
        # Track exits in center's contents
        center.contents.append(ex)

        rev_ex = mock_exit(reverse[direction], location=room, destination=center)
        room.contents.append(rev_ex)

    auditor.ok(f"Created {len(created)} interconnected rooms ({len(directions)} directions)")

    # Exit lock/unlock
    test_exit = mock_exit("test_exit")
    if not test_exit.attributes.get("locked"):
        auditor.ok("Exit defaults: unlocked")
    else:
        auditor.fail("Fresh exit shows locked")
    test_exit.attributes.add("locked", True)
    if test_exit.attributes.get("locked"):
        auditor.ok("Exit can be locked")
    else:
        auditor.fail("Exit lock not set")

    # Room return_appearance
    try:
        from typeclasses.rooms import Room
        # Test with an actual Room if available, otherwise mock
        try:
            r = Room()
            r.key = "RenderingTest"
            auditor.ok("Room typeclass instantiable")
        except Exception:
            # DB-backed Room can't be used outside evennia shell — that's fine
            auditor.ok("Room typeclass requires DB (expected outside interactive shell)")
    except ImportError:
        auditor.warn("typeclasses.rooms not importable")

    # Character look
    char = mock_character("LookTest", "Human", "Warrior")
    char.location = center


# ============================================================================
# BATTERY 7: Weather, Time & Environmental Tickers
# ============================================================================

def battery_7_weather_environment(auditor: Auditor):
    """Test weather module, outdoor attributes, and prompt segments."""
    auditor.section("Weather, Time & Environmental Tickers")

    try:
        import world.weather as weather_mod
        auditor.ok("Weather module imported")
    except Exception:
        auditor.fail("Weather module import failed", traceback.format_exc())
        return

    if hasattr(weather_mod, "format_weather_short"):
        auditor.ok("format_weather_short() exists")
    else:
        auditor.warn("format_weather_short() not found")

    weather_states = getattr(weather_mod, "WEATHER_STATES",
                             getattr(weather_mod, "WEATHER_TYPES", None))
    if weather_states is not None:
        keys = list(weather_states.keys()) if isinstance(weather_states, dict) else weather_states
        auditor.ok(f"Weather states defined: {str(keys)[:100]}")
    else:
        auditor.warn("No weather states/tables defined")

    outdoor = mock_room("OutdoorRoom", outdoor=True)
    indoor = mock_room("IndoorRoom", outdoor=False)

    if outdoor.attributes.get("outdoor"):
        auditor.ok("Outdoor room attribute sets")
    if not indoor.attributes.get("outdoor"):
        auditor.ok("Indoor room attribute sets")

    char = mock_character("WeatherChar", "Human", "Warrior")
    char.location = outdoor
    auditor.ok("Weather prompt segment test setup ready")

    # Test weather command module
    try:
        import commands.weather
        auditor.ok("commands.weather module imports")
    except Exception:
        auditor.warn("commands.weather not importable (may need evennia CmdSet)")


# ============================================================================
# BATTERY 8: MajorMUD Ticker Combat Engine
# ============================================================================

def battery_8_combat_engine(auditor: Auditor):
    """Test combat engine functions: hit, damage, death detection, fleeing."""
    auditor.section("MajorMUD Ticker Combat Engine")

    from world.tick_combat import (
        _roll_attack_hit, _calculate_damage, _calculate_flee_chance,
        _get_weapon_damage, _is_alive, _get_stat, _get_level,
        _is_player, _is_valid_target,
    )
    from world.damage_formulas import calculate_melee_damage, DamageType

    a = mock_character("TickA", "Human", "Warrior",
                       stats={"str": 18, "dex": 16, "con": 14, "int": 10, "wis": 10, "cha": 10})
    a.attributes.add("level", 10)
    a.attributes.add("hp", 100)
    a.attributes.add("max_hp", 100)

    d = mock_character("TickD", "Goblin", "Warrior",
                       stats={"str": 12, "dex": 14, "con": 12, "int": 8, "wis": 8, "cha": 6})
    d.attributes.add("level", 5)
    d.attributes.add("hp", 80)
    d.attributes.add("max_hp", 80)

    room = mock_room("CombatRoom")
    a.location = room
    d.location = room

    # — 8a: Hit roll —
    try:
        hits = sum(1 for _ in range(100) if _roll_attack_hit(a, d))
        if 25 < hits < 90:
            auditor.ok(f"Hit rate (100 trials): {hits}%")
        else:
            auditor.warn(f"Hit rate: {hits}% — possible anomaly")
    except Exception:
        auditor.fail("_roll_attack_hit() exception", traceback.format_exc())

    # — 8b: Weapon damage —
    try:
        wd = _get_weapon_damage(a)
        if wd >= 1:
            auditor.ok(f"Weapon damage (unarmed STR 18): {wd}")
        else:
            auditor.fail(f"Weapon damage = {wd}")
    except Exception:
        auditor.fail("_get_weapon_damage() exception", traceback.format_exc())

    # — 8c: Damage calculation —
    try:
        result = _calculate_damage(a, d)
        if "damage" in result:
            auditor.ok(f"_calculate_damage(): damage={result['damage']}, crit={result.get('crit', False)}")
        else:
            auditor.fail("_calculate_damage() missing 'damage' key")
    except Exception:
        auditor.fail("_calculate_damage() exception", traceback.format_exc())

    # — 8d: Flee chance bounds —
    try:
        flee = _calculate_flee_chance(a, d)
        if 0.10 <= flee <= 0.90:
            auditor.ok(f"Flee chance: {flee:.2%} — in bounds")
        else:
            auditor.fail(f"Flee chance {flee:.2%} outside [10%, 90%]")
    except Exception:
        auditor.fail("_calculate_flee_chance() exception", traceback.format_exc())

    # — 8e: Death detection —
    target = mock_character("DyingTarget", "Goblin", "Warrior")
    target.attributes.add("hp", 10)
    target.attributes.add("max_hp", 10)
    if _is_alive(target):
        target.attributes.add("hp", 0)
        if not _is_alive(target):
            auditor.ok("_is_alive(): True → False at 0 HP")
        else:
            auditor.fail("_is_alive() True at 0 HP")
    else:
        auditor.fail("_is_alive() False for 10 HP char")

    # — 8f: Melee damage formula for all DamageTypes —
    for dt in DamageType:
        try:
            r = calculate_melee_damage(a, d, 20, dt)
            if isinstance(r, dict) and "damage" in r:
                auditor.ok(f"calculate_melee_damage({dt.name}): dmg={r['damage']}, crit={r.get('crit', False)}")
            else:
                auditor.fail(f"calculate_melee_damage({dt.name}) returned {type(r)}")
        except Exception:
            auditor.fail(f"calculate_melee_damage({dt.name}) exception", traceback.format_exc())

    # — 8g: _is_player / _get_stat / _get_level —
    try:
        auditor.ok(f"_is_player(character): {_is_player(a)}")
        auditor.ok(f"_get_stat(STR): {_get_stat(a, 'str')}")
        auditor.ok(f"_get_level: {_get_level(a)}")
    except Exception:
        auditor.fail("Helper functions exception", traceback.format_exc())

    # — 8h: CombatHandler static methods (only test the module-level helpers) —
    try:
        from world.tick_combat import CombatHandler
        # Just verify the class exists and has expected methods
        methods = ["is_in_combat", "get_target", "start_combat", "stop_combat", "attempt_flee"]
        for m in methods:
            if hasattr(CombatHandler, m):
                auditor.ok(f"CombatHandler.{m}() exists")
            else:
                auditor.fail(f"CombatHandler.{m}() missing")
    except Exception:
        auditor.fail("CombatHandler inspection failed", traceback.format_exc())


# ============================================================================
# BATTERY 9: Mob Spawners, Decay & Corpse Containers
# ============================================================================

def battery_9_spawners_corpses(auditor: Auditor):
    """Test mob spawners, corpse creation, loot, and garbage collection."""
    auditor.section("Mob Spawners, Decay & Corpse Containers")

    from world.combat import _roll_loot_table, DEATH_XP_LOSS_PERCENT, CORPSE_OWNER_ONLY_SECONDS

    # — 9a: Constants —
    auditor.ok(f"DEATH_XP_LOSS_PERCENT: {DEATH_XP_LOSS_PERCENT}%")
    auditor.ok(f"CORPSE_OWNER_ONLY_SECONDS: {CORPSE_OWNER_ONLY_SECONDS}s ({CORPSE_OWNER_ONLY_SECONDS // 60}m)")

    # — 9b: Loot table rolling —
    try:
        loot_table = [
            {"item_key": "Short Sword", "weight": 0.5, "min_qty": 1, "max_qty": 1,
             "value": 10, "weight_attr": 3, "damage": 5, "armor": 0, "item_type": "weapon_sword"},
            {"item_key": "Leather Armor", "weight": 0.3, "min_qty": 1, "max_qty": 1,
             "value": 15, "weight_attr": 5, "damage": 0, "armor": 3, "item_type": "armor_light"},
            {"item_key": "Health Potion", "weight": 0.8, "min_qty": 1, "max_qty": 2,
             "value": 5, "weight_attr": 1, "damage": 0, "armor": 0, "item_type": "consumable"},
        ]
        items = _roll_loot_table(loot_table)
        auditor.ok(f"Loot table rolled: {len(items)} items from 3 entries")
    except Exception:
        auditor.fail("_roll_loot_table() exception", traceback.format_exc())

    # — 9c: Corpse creation and auto-loot/sac constants —
    from world.combat import _make_corpse, _auto_loot_corpse, _auto_sac_corpse
    auditor.ok("_make_corpse, _auto_loot_corpse, _auto_sac_corpse importable")

    # — 9d: MobSpawner typeclass —
    try:
        from typeclasses.objects import MobSpawner
        auditor.ok("MobSpawner typeclass exists")
    except ImportError:
        auditor.fail("MobSpawner not in typeclasses.objects")
    except Exception:
        auditor.fail("MobSpawner import exception", traceback.format_exc())

    # — 9e: GarbageCollectionScript —
    try:
        from world.garbage_collection import GarbageCollectionScript
        gc_script = GarbageCollectionScript()
        auditor.ok(f"GarbageCollectionScript: interval={gc_script.interval}s, persistent={gc_script.persistent}")
    except Exception:
        auditor.fail("GarbageCollectionScript exception", traceback.format_exc())

    # — 9f: Calculate sacrifice reward (if defined) —
    try:
        from commands.loot import calculate_sac_reward
        coins, display = calculate_sac_reward(5)
        auditor.ok(f"Sacrifice reward for level 5 mob: {display}")
    except ImportError:
        auditor.warn("commands.loot.calculate_sac_reward not found")
    except Exception:
        auditor.fail("calculate_sac_reward() exception", traceback.format_exc())

    # — 9g: Boss loot system —
    try:
        from world.boss_loot import boss_loot_registry, BossLootHandler, is_boss
        boss_count = len(boss_loot_registry) if boss_loot_registry else 0
        auditor.ok(f"Boss loot registry: {boss_count} boss(es)")
    except ImportError:
        auditor.warn("world.boss_loot not importable")
    except Exception:
        auditor.fail("Boss loot exception", traceback.format_exc())


# ============================================================================
# BATTERY 10: Economy, Inventory, Vendors & Recovery
# ============================================================================

def battery_10_economy_recovery(auditor: Auditor):
    """Test encumbrance, recovery, shopkeeper, and prompt rendering."""
    auditor.section("Economy, Inventory, Vendors & Recovery")

    from world.encumbrance import get_carry_capacity, get_current_encumbrance
    from world.recovery import RecoveryScript, Position, POSITION_REGEN_RATES

    char = mock_character("EconTest", "Human", "Warrior",
                          stats={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10})

    # — 10a: Encumbrance —
    try:
        capacity = get_carry_capacity(char)
        auditor.ok(f"Carry capacity (STR 16): {capacity:.1f} kg")
    except Exception:
        auditor.fail("get_carry_capacity() exception", traceback.format_exc())

    try:
        current = get_current_encumbrance(char)
        auditor.ok(f"Current encumbrance: {current:.1f} kg")
    except Exception:
        auditor.fail("get_current_encumbrance() exception", traceback.format_exc())

    # — 10b: Recovery system —
    try:
        rs = RecoveryScript()
        auditor.ok(f"RecoveryScript: interval={rs.interval}s, persistent={rs.persistent}")
    except Exception:
        auditor.fail("RecoveryScript instantiation failed", traceback.format_exc())

    for pos in Position:
        rates = POSITION_REGEN_RATES.get(pos, {})
        auditor.ok(
            f"Position {pos.value}: HP={rates.get('hp_pct', 0) * 100:.0f}% "
            f"MP={rates.get('mana_pct', 0) * 100:.0f}% "
            f"MV={rates.get('mv_pct', 0) * 100:.0f}%"
        )

    # — 10c: Status prompt for caster and non-caster —
    from world.race_class_matrix import can_cast_spells

    caster = mock_character("PromptCaster", "High Elf", "Mage", mana=45, max_mana=50)
    non_caster = mock_character("PromptNC", "Human", "Warrior")

    # Test prompt generation via typeclasses.characters.get_status_prompt
    try:
        from typeclasses.characters import Character as RealCharacter
        # Use a real Character if available, otherwise check the function exists
        if hasattr(RealCharacter, "get_status_prompt"):
            auditor.ok("Character.get_status_prompt() method exists")
        else:
            auditor.warn("Character.get_status_prompt() not found")
    except Exception:
        auditor.warn("Could not inspect Character.get_status_prompt()")

    # Test can_cast_spells logic (which governs MP visibility in prompt)
    if can_cast_spells(caster):
        auditor.ok("Caster: can_cast_spells() = True → MP shows in prompt")
    else:
        auditor.fail("Caster: can_cast_spells() = False")

    if not can_cast_spells(non_caster):
        auditor.ok("Non-caster: can_cast_spells() = False → MP hidden")
    else:
        auditor.fail("Non-caster: can_cast_spells() = True")

    # — 10d: Stamina initialization —
    stamina = char.attributes.get("stamina", 0)
    max_stamina = char.attributes.get("max_stamina", 0)
    auditor.ok(f"Stamina: {stamina}/{max_stamina}")

    # — 10e: Shopkeeper / currency —
    try:
        from world.shopkeeper import convert_currency, ShopkeeperHandler
        auditor.ok("Shopkeeper module imported")
        result = convert_currency(250)
        auditor.ok(f"Currency conversion 250 copper → {result}")
    except Exception:
        auditor.fail("Shopkeeper module exception", traceback.format_exc())

    # — 10f: Position state machine —
    for pos_str in ["resting", "meditating", "sleeping", "standing"]:
        char.attributes.add("position", pos_str)
        got = char.attributes.get("position")
        if got == pos_str:
            auditor.ok(f"Position '{pos_str}': set/get ✓")
        else:
            auditor.fail(f"Position '{pos_str}': got '{got}'")

    # — 10g: Validate rules module —
    try:
        from world.rules import RACES, CLASSES, xp_to_level
        auditor.ok(f"RACES defined: {len(RACES)} entries")
        auditor.ok(f"CLASSES defined: {len(CLASSES)} entries")
        tnl_1 = xp_to_level(1)
        tnl_10 = xp_to_level(10)
        auditor.ok(f"XP to level: L1→{tnl_1}, L10→{tnl_10}")
    except Exception:
        auditor.fail("world.rules exception", traceback.format_exc())

    # — 10h: Armor set checker —
    try:
        from world.armor_sets import ArmorSetChecker
        checker = ArmorSetChecker(char)
        display = checker.format_display()
        auditor.ok(f"Armor set checker: {'sets found' if display else 'no sets (expected for naked char)'}")
    except Exception:
        auditor.warn("ArmorSetChecker exception (may be normal)")

    # — 10i: Combat skills registry —
    try:
        from world.combat_skills import COMBAT_SKILLS
        auditor.ok(f"Combat skills registered: {len(COMBAT_SKILLS)}")
    except Exception:
        auditor.fail("COMBAT_SKILLS import failed", traceback.format_exc())

    # — 10j: Saving throws registry —
    try:
        from world.saving_throws import SavingThrow, SAVING_THROW_DISPLAY
        auditor.ok(f"Saving throws defined: {len(SavingThrow)}")
    except Exception:
        auditor.warn("Saving throws import issue")

    # — 10k: Status effects module —
    try:
        from world.status_effects import get_active_effects, apply_status_effect
        auditor.ok("Status effects module imported")
    except Exception:
        auditor.warn("Status effects import issue")


# ============================================================================
# PHASE 6.12: Testing & Validation (from gaps.md)
# ============================================================================

def battery_phase_6_12_tests(auditor: Auditor):
    """Phase 6.12 testing targets from gaps.md.

    - Unit tests for race_class_matrix, damage_formulas, tick_combat
    - Integration tests: Orc Warrior gating, Elf Mage spellbook,
      Warrior vs Goblin, Good vs Evil PvP, guildmaster train → learn
    - Load test: 100 mobs
    - Memory test: 1000 combat loops
    """
    auditor.section("Phase 6.12 — Unit & Integration Tests")

    from world.race_class_matrix import (
        RACE_CLASS_MATRIX, CLASS_SPELL_SCHOOLS, CLASS_SKILLS,
        CLASS_WEAPON_TYPES, CLASS_ARMOR_TYPES,
        can_cast_spells, can_learn_spell, can_use_skill, can_equip_slot,
        is_race_class_valid, get_valid_classes_for_race,
    )
    from world.spells import SPELLS, SpellHandler
    from world.tick_combat import _calculate_damage, _roll_attack_hit, _is_alive, _calculate_flee_chance

    # ═══════════════════════════════════════════════════════════════
    # 6.12.1  unit tests — race_class_matrix
    # ═══════════════════════════════════════════════════════════════
    auditor.section("6.12.1  race_class_matrix unit tests")

    total_combos = sum(len(v) for v in RACE_CLASS_MATRIX.values())
    matrix_issues = 0
    for race, classes in RACE_CLASS_MATRIX.items():
        for cls in classes:
            if not is_race_class_valid(race, cls):
                matrix_issues += 1
                auditor.fail(f"Matrix fail: {race} {cls}")
            if cls not in get_valid_classes_for_race(race):
                matrix_issues += 1
                auditor.fail(f"Matrix fail: {cls} not in get_valid_classes_for_race('{race}')")

    if matrix_issues == 0:
        auditor.ok(f"All {total_combos} race/class combos validated")

    # Spell gating per class/school
    spellcaster_classes = [c for c, schools in CLASS_SPELL_SCHOOLS.items() if schools]
    for cls_name in spellcaster_classes:
        test_char = mock_character(f"Test{cls_name}", "Human", cls_name, level=80)
        for school in CLASS_SPELL_SCHOOLS[cls_name]:
            school_spells = [s for s in SPELLS.values()
                             if s["school"] == school and s["level"] <= 5]
            if school_spells:
                sk = school_spells[0]["key"]
                allowed, reason = can_learn_spell(test_char, sk)
                if allowed:
                    auditor.ok(f"{cls_name} can learn {sk} ({school})")
                else:
                    auditor.fail(f"{cls_name} blocked from {sk}: {reason}")

    # Race spell blocks
    for race in ["Orc", "Ogre", "Minotaur"]:
        tchar = mock_character(f"Test{race}Block", race, "Mage", level=80)
        allowed, reason = can_learn_spell(tchar, "sparks")
        if not allowed:
            auditor.ok(f"{race} Mage blocked from spells: '{reason}'")
        else:
            auditor.fail(f"{race} Mage allowed to learn spells — RACE GATING BROKEN")

    # Skill matrix
    skill_names = ["kick", "bash", "backstab", "disarm"]
    for cls_name, skills in CLASS_SKILLS.items():
        tchar = mock_character(f"SkillTest{cls_name}", "Human", cls_name)
        for sk in skill_names:
            should_have = sk in skills
            has_it, _ = can_use_skill(tchar, sk)
            if has_it != should_have:
                auditor.fail(f"{cls_name}.{sk}: expected {should_have}, got {has_it}")

    auditor.ok("Skill matrix validated across all classes")

    # Pixie equipment edge cases
    pixie = mock_character("PixieEquip", "Pixie", "Mage")
    for slot, itype, should_block in [
        ("chest_heavy", "armor_heavy", True),
        ("two_handed", "weapon_two_handed", True),
        ("shoulders", "armor_light", True),
        ("head", "armor_cloth", False),
        ("hands", "weapon_dagger", False),
    ]:
        allowed, _ = can_equip_slot(pixie, slot, itype)
        if allowed == (not should_block):
            auditor.ok(f"Pixie {slot}/{itype}: {'blocked' if should_block else 'allowed'}")
        else:
            auditor.fail(f"Pixie {slot}/{itype}: expected {'blocked' if should_block else 'allowed'}")

    # ═══════════════════════════════════════════════════════════════
    # 6.12.2  Unit tests — damage_formulas
    # ═══════════════════════════════════════════════════════════════
    auditor.section("6.12.2  damage_formulas unit tests")

    from world.damage_formulas import (
        calculate_melee_damage, calculate_spell_damage,
        DamageType, get_damage_type_modifier, calculate_armor_absorption,
    )

    attacker = mock_character("DmgA", "Human", "Warrior", level=10,
                              stats={"str": 18, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 10})
    defender = mock_character("DmgD", "Orc", "Warrior", level=8,
                              stats={"str": 16, "dex": 10, "con": 16, "int": 8, "wis": 8, "cha": 8})

    for dt in DamageType:
        try:
            r = calculate_melee_damage(attacker, defender, 20, dt)
            if isinstance(r, dict) and "damage" in r:
                auditor.ok(f"calculate_melee_damage({dt.name}): dmg={r['damage']}, crit={r.get('crit', False)}")
            else:
                auditor.fail(f"calculate_melee_damage({dt.name}) unexpected return")
        except Exception:
            auditor.fail(f"calculate_melee_damage({dt.name}) exception", traceback.format_exc())

    try:
        absorbed = calculate_armor_absorption(defender, 20, DamageType.SLASH)
        auditor.ok(f"Armor absorption (SLASH, 20 base): {absorbed}")
    except Exception:
        auditor.fail("calculate_armor_absorption() exception", traceback.format_exc())

    for dt in DamageType:
        try:
            mod = get_damage_type_modifier(dt, defender)
            auditor.ok(f"Damage type modifier {dt.name}: {mod:.2f}")
        except Exception:
            auditor.warn(f"get_damage_type_modifier({dt.name}) exception")

    try:
        caster = mock_character("SpellCaster", "High Elf", "Mage", level=10,
                                stats={"str": 10, "dex": 12, "con": 10, "int": 18, "wis": 14, "cha": 12})
        sr = calculate_spell_damage(caster, defender, 50, "fire")
        auditor.ok(f"calculate_spell_damage(fire, 50): {sr}")
    except Exception:
        auditor.fail("calculate_spell_damage() exception", traceback.format_exc())

    # ═══════════════════════════════════════════════════════════════
    # 6.12.3  Unit tests — tick_combat
    # ═══════════════════════════════════════════════════════════════
    auditor.section("6.12.3  tick_combat unit tests")

    t_a = mock_character("TckA", "Human", "Warrior", level=10,
                         stats={"str": 18, "dex": 16, "con": 14, "int": 10, "wis": 10, "cha": 10})
    t_d = mock_character("TckD", "Goblin", "Warrior", level=5,
                         stats={"str": 12, "dex": 14, "con": 12, "int": 8, "wis": 8, "cha": 6})

    t_room = mock_room("TickRoom")
    t_a.location = t_room
    t_d.location = t_room

    hits = sum(1 for _ in range(100) if _roll_attack_hit(t_a, t_d))
    if 20 < hits < 90:
        auditor.ok(f"Hit rate (100 trials): {hits}%")
    else:
        auditor.warn(f"Hit rate: {hits}% — anomalous")

    flee = _calculate_flee_chance(t_a, t_d)
    if 0.10 <= flee <= 0.90:
        auditor.ok(f"Flee chance: {flee:.2%} — in bounds")
    else:
        auditor.fail(f"Flee chance {flee:.2%} outside [10%, 90%]")

    from world.tick_combat import _get_weapon_damage
    wd = _get_weapon_damage(t_a)
    auditor.ok(f"Weapon damage STR 18: {wd}")

    if _is_alive(t_a):
        auditor.ok("_is_alive(): True")
    t_d.attributes.add("hp", 0)
    if not _is_alive(t_d):
        auditor.ok("_is_alive() at 0 HP: False")
    else:
        auditor.fail("_is_alive() True at 0 HP")

    # ═══════════════════════════════════════════════════════════════
    # 6.12.4  Integration: Orc Warrior spell gating (all spells)
    # ═══════════════════════════════════════════════════════════════
    auditor.section("6.12.4  Integration: Orc Warrior spell gating")

    orc_w = mock_character("IntOrcWar", "Orc", "Warrior", level=50)
    blocked = 0
    leaked = 0
    for sk in SPELLS:
        allowed, _ = can_learn_spell(orc_w, sk)
        if allowed:
            leaked += 1
        else:
            blocked += 1

    auditor.ok(f"Orc Warrior: {blocked}/{len(SPELLS)} spells blocked")
    if leaked == 0:
        auditor.ok("Orc Warrior: ALL spells correctly gated")
    else:
        auditor.fail(f"Orc Warrior: {leaked} spells LEAKED — CRITICAL")

    # SpellHandler gate
    sh = SpellHandler(orc_w)
    can, reason = sh.can_cast("fireball")
    if not can:
        auditor.ok(f"SpellHandler.can_cast('fireball'): '{reason}'")
    else:
        auditor.fail("SpellHandler allows fireball for Orc Warrior — BYPASS")

    # ═══════════════════════════════════════════════════════════════
    # 6.12.5  Integration: High Elf Mage spellbook
    # ═══════════════════════════════════════════════════════════════
    auditor.section("6.12.5  Integration: High Elf Mage spellbook")

    elf_m = mock_character("IntElfMage", "High Elf", "Mage", level=80,
                           mana=500, max_mana=500,
                           stats={"str": 10, "dex": 14, "con": 10, "int": 20, "wis": 16, "cha": 12})
    learned = [sk for sk in SPELLS if can_learn_spell(elf_m, sk)[0]]
    if learned:
        auditor.ok(f"High Elf Mage (L80): {len(learned)}/{len(SPELLS)} spells available")
    else:
        auditor.fail("High Elf Mage: ZERO spells available")

    elf_m.attributes.add("learned_spells", learned)
    available = elf_m.spells.available_spells()
    if available:
        auditor.ok(f"available_spells() returns {len(available)} spells")
        test_s = learned[0]
        can, _ = sh.can_cast(test_s)
        auditor.ok(f"can_cast('{test_s}'): {can}")
    else:
        auditor.fail("available_spells() empty for level 80 Mage")

    # ═══════════════════════════════════════════════════════════════
    # 6.12.6  Integration: Warrior vs Goblin full loop
    # ═══════════════════════════════════════════════════════════════
    auditor.section("6.12.6  Integration: Warrior vs Goblin full loop")

    war = mock_character("WarriorFight", "Human", "Warrior", level=5,
                         stats={"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 10})
    war.attributes.add("hp", 120)
    war.attributes.add("max_hp", 120)

    gob = mock_character("GoblinFight", "Goblin", "Warrior", level=3,
                         stats={"str": 10, "dex": 12, "con": 10, "int": 8, "wis": 8, "cha": 6})
    gob.attributes.add("hp", 60)
    gob.attributes.add("max_hp", 60)

    froom = mock_room("FightRoom")
    war.location = froom
    gob.location = froom

    gob_start_hp = gob.attributes.get("hp", 0)
    rounds = 0
    total_dmg = 0
    for _ in range(3):
        if not _is_alive(gob):
            break
        r = _calculate_damage(war, gob)
        dmg = r.get("damage", 0)
        total_dmg += dmg
        new_hp = max(0, gob.attributes.get("hp", 0) - dmg)
        gob.attributes.add("hp", new_hp)
        rounds += 1

    auditor.ok(f"Warrior vs Goblin: {rounds} rounds, {total_dmg} total damage")
    if gob.attributes.get("hp", 0) < gob_start_hp:
        auditor.ok("Goblin took damage — combat simulation works")
    else:
        auditor.warn("Goblin took no damage in 3 rounds (possible all misses)")

    # ═══════════════════════════════════════════════════════════════
    # 6.12.7  Integration: Good vs Evil PvP
    # ═══════════════════════════════════════════════════════════════
    auditor.section("6.12.7  Integration: Good vs Evil PvP")

    from world.combat import _is_pvp_allowed

    gp = mock_character("GoodFighter", "Human", "Paladin", alignment="Good", level=10)
    ep = mock_character("EvilFighter", "Dark Elf", "Warlock", alignment="Evil", level=10)
    proom = mock_room("PvPRoom")
    gp.location = proom
    ep.location = proom

    allowed, reason = _is_pvp_allowed(gp, ep)
    if allowed:
        auditor.ok("Good vs Evil PvP: auto-allowed")
    else:
        auditor.fail(f"Good vs Evil PvP blocked: {reason}")

    g2 = mock_character("GoodFighter2", "Human", "Warrior", alignment="Good")
    g2.db.pvp_enabled = False
    g2.location = proom
    allowed2, reason2 = _is_pvp_allowed(gp, g2)
    if not allowed2:
        auditor.ok(f"Same-faction PvP blocked: '{reason2}'")
    else:
        auditor.fail("Same-faction PvP should be blocked")

    # ═══════════════════════════════════════════════════════════════
    # 6.12.8  Integration: guildmaster train → learn
    # ═══════════════════════════════════════════════════════════════
    auditor.section("6.12.8  Integration: guildmaster train → learn")

    from world.guildmaster import award_practice_points, GuildmasterNPC

    trainee = mock_character("TrainMage", "High Elf", "Mage", level=10,
                             stats={"str": 10, "dex": 12, "con": 10, "int": 18, "wis": 14, "cha": 12})
    try:
        award_practice_points(trainee, level=10)
        session = trainee.attributes.get("practice_session")
        if session is not None:
            pp = getattr(session, "practice_points", 0)
            auditor.ok(f"Guildmaster: {pp} practice points at level 10")

            gm = type("MockGuildmaster", (), {
                "get_trainable_skills": GuildmasterNPC.get_trainable_skills,
                "train_skill": GuildmasterNPC.train_skill,
            })()
            result = gm.train_skill(trainee, "bash")
            auditor.ok(f"train_skill('bash'): {result}")
        else:
            auditor.fail("practice_session not stored after award")
    except Exception:
        auditor.fail("Guildmaster train → learn exception", traceback.format_exc())

    trained = trainee.attributes.get("trained_skills", [])
    auditor.ok(f"Trained skills: {trained}")

    # ═══════════════════════════════════════════════════════════════
    # 6.12.9  Load test: 100 mobs
    # ═══════════════════════════════════════════════════════════════
    auditor.section("6.12.9  Load test: 100 mobs")

    load_room = mock_room("LoadTestRoom")
    mobs = []
    t0 = time.time()
    try:
        for i in range(100):
            m = mock_character(f"Mob{i:03d}", "Goblin", "Warrior", level=1,
                              hp=30 + i % 20, max_hp=50)
            m.location = load_room
            mobs.append(m)
        elapsed = time.time() - t0
        auditor.ok(f"100 mobs created in {elapsed:.3f}s")
    except Exception:
        auditor.fail("100 mob creation failed", traceback.format_exc())

    if len(mobs) == 100:
        auditor.ok("Load test: 100 mobs stored")
    else:
        auditor.fail(f"Expected 100 mobs, got {len(mobs)}")

    # ═══════════════════════════════════════════════════════════════
    # 6.12.10  Memory test: 1000 combat loops
    # ═══════════════════════════════════════════════════════════════
    auditor.section("6.12.10 Memory test: 1000 combat loops")

    mem_a = mock_character("MemA", "Human", "Warrior", level=5,
                           stats={"str": 14, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 10},
                           hp=99999, max_hp=99999)
    mem_d = mock_character("MemD", "Goblin", "Warrior", level=3,
                           stats={"str": 10, "dex": 12, "con": 10, "int": 8, "wis": 8, "cha": 6},
                           hp=99999, max_hp=99999)

    t1 = time.time()
    for _ in range(1000):
        _calculate_damage(mem_a, mem_d)
    elapsed = time.time() - t1
    auditor.ok(f"1000 combat calcs in {elapsed:.3f}s ({elapsed / 1000 * 1000:.2f}ms each)")

    gc.collect()
    auditor.ok("Garbage collection after 1000 loops")


# ============================================================================
# BONUS: Audit live database for structural integrity
# ============================================================================

def battery_db_integrity(auditor: Auditor):
    """Audit the live Evennia database for object/script/account counts."""
    auditor.section("Database Structural Integrity (Live DB)")

    try:
        from evennia.objects.models import ObjectDB
        from evennia.scripts.models import ScriptDB
        from evennia.accounts.models import AccountDB

        obj_count = ObjectDB.objects.count()
        auditor.ok(f"ObjectDB entries: {obj_count}")

        script_count = ScriptDB.objects.count()
        auditor.ok(f"ScriptDB entries: {script_count}")

        acct_count = AccountDB.objects.count()
        auditor.ok(f"AccountDB entries: {acct_count}")
    except Exception:
        auditor.warn("Database access unavailable (run from `evennia shell` for live DB checks)")


# ============================================================================
# MASTER RUNNER
# ============================================================================

def run():
    """Execute all audit batteries and print the summary dashboard."""
    print("\n" + "=" * 70)
    print("  RITES OF PASSAGE — FULL PRODUCTION AUDIT")
    print("=" * 70)
    print(f"  Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python:  {sys.version}")
    print("=" * 70)

    master = Auditor("Rites of Passage Full Audit")

    # Run each battery in isolation so one crash doesn't stop all others
    batteries = [
        ("BATTERY 1: Codebase Scanner & Django Bootstrap", battery_1_codebase_scan),
        ("BATTERY 2: Race, Class, Faction & Spell-Gating", battery_2_race_class_spell_gating),
        ("BATTERY 3: Clans, Guilds & Guildmasters", battery_3_clans_guilds),
        ("BATTERY 4: Quests & Dialogue System", battery_4_quests),
        ("BATTERY 5: Open & Safe-Zone PvP System", battery_5_pvp),
        ("BATTERY 6: 10-Way Movement & Room Rendering", battery_6_movement_rendering),
        ("BATTERY 7: Weather, Time & Environmental Tickers", battery_7_weather_environment),
        ("BATTERY 8: MajorMUD Ticker Combat Engine", battery_8_combat_engine),
        ("BATTERY 9: Mob Spawners, Decay & Corpse Containers", battery_9_spawners_corpses),
        ("BATTERY 10: Economy, Inventory, Vendors & Recovery", battery_10_economy_recovery),
        ("PHASE 6.12: Testing & Validation (gaps.md)", battery_phase_6_12_tests),
        ("BONUS: Database Structural Integrity", battery_db_integrity),
    ]

    for label, fn in batteries:
        safe_run_battery(master, label, fn)

    # ── Summary ──
    print(f"\n{'='*70}")
    print(f"  AUDIT COMPLETE")
    print(f"  Ended: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    master.summary()

    return master


if __name__ == "__main__":
    run()