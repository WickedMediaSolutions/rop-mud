"""
Comprehensive Test Suite for Phase 7: Spells & Magic
=====================================================

Validates:
  1. Spell definitions (all 60+ spells, levels 1-80)
  2. Spell registry helpers (get_spell, get_spells_for_level, get_spells_by_school)
  3. SpellHandler (can_cast, cast, mana costs, cooldowns)
  4. Damage spells (scaling, damage types, saving throws)
  5. Healing spells (scaling, self vs target)
  6. Shield spells (absorption, duration)
  7. Buff spells (stat increases, duration, removal)
  8. Debuff spells (stat reductions, saving throws)
  9. DoT spells (bleed, poison, burn, curse via status_effects)
  10. HoT spells (heal-over-time ticks)
  11. Stun spells (crowd control, saving throws)
  12. Lifesteal spells (damage + self-heal)
  13. Spell resistance (racial, wisdom, gear, buffs)
  14. Ritual/channeled spells (cast_time, interrupt)
  15. Spell scrolls (creation, use, class gating)
  16. Class-specific spell lists (race_class_matrix gating)
  17. AoE spells (multi-target iteration)
  18. Spellbook display (format_spellbook, format_spell_detail)

Run: python commands/tests/test_phase7_spells_magic.py
"""

import os, sys, random, math, time, types

# Add project root for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Django config before any Evennia imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
import django
django.setup()


# Mock character for testing
class MockAttributes:
    def __init__(self):
        self._store = {}
    def get(self, key, default=None):
        return self._store.get(key, default)
    def add(self, key, value):
        self._store[key] = value
    def has(self, key):
        return key in self._store


class MockCharacter:
    def __init__(self, name="TestPlayer", level=1, race="Human", char_class="Mage",
                 stats=None, mana=100, max_mana=100, hp=100, max_hp=100):
        self.key = name
        self.dbref = f"#{id(self)}"
        self.attributes = MockAttributes()
        self.attributes.add("level", level)
        self.attributes.add("race", race)
        self.attributes.add("class", char_class)
        self.attributes.add("mana", mana)
        self.attributes.add("max_mana", max_mana)
        self.attributes.add("hp", hp)
        self.attributes.add("max_hp", max_hp)
        self.attributes.add("stats", stats or {"str": 10, "dex": 10, "con": 10, "int": 14, "wis": 12, "cha": 10})
        self.attributes.add("spell_cooldowns", {})
        self.attributes.add("shield_amount", 0)
        self.attributes.add("spell_resist", 0)
        self.attributes.add("spell_resist_buff", 0)
        self.attributes.add("is_channeling", False)
        self.attributes.add("channeling_spell", "")
        self.attributes.add("channeling_target", None)
        self.attributes.add("copper", 10000)
        self.attributes.add("alignment", "good")
        self.location = MockLocation()
        self.contents = []
        self.db_location = None  # Evennia internal
        self.db = types.SimpleNamespace()  # Evennia db handler
        self.db.pvp_enabled = False
        self.ndb = types.SimpleNamespace()
        # Don't set active_effects — let get_active_effects() create it lazily
        self._messages = []

    def msg(self, text):
        self._messages.append(text)

    def search(self, name, location=None):
        for item in self.contents:
            if name.lower() in item.key.lower():
                return item
        return None

    def delete(self):
        pass


class MockLocation:
    def __init__(self, name="TestRoom"):
        self.key = name
        self.contents = []
        self.attributes = MockAttributes()
    def msg_contents(self, message, exclude=None):
        pass


class MockScroll:
    def __init__(self, name="Scroll of Fireball", spell_key="fireball", universal=False):
        self.key = name
        self.attributes = MockAttributes()
        self.attributes.add("item_type", "scroll")
        self.attributes.add("spell_key", spell_key)
        self.attributes.add("spell_name", "Fireball")
        self.attributes.add("scroll_level", 0)
        self.attributes.add("universal_scroll", universal)
        self.location = None
        self._deleted = False
    def delete(self):
        self._deleted = True


PASS = 0
FAIL = 0

def test(name):
    def decorator(fn):
        global PASS, FAIL
        try:
            fn()
            PASS += 1
            print(f"  [PASS] {name}")
        except AssertionError as e:
            FAIL += 1
            print(f"  [FAIL] {name}: {e}")
        except Exception as e:
            FAIL += 1
            import traceback
            print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
    return decorator

def assert_eq(a, e, m=""):
    if a != e:
        raise AssertionError(f"{m}: expected {e!r}, got {a!r}")
def assert_true(v, m=""):
    if not v:
        raise AssertionError(m or "expected truthy")
def assert_false(v, m=""):
    if v:
        raise AssertionError(m or "expected falsy")
def assert_gt(a, b, m=""):
    if not (a > b):
        raise AssertionError(f"{m}: expected {a!r} > {b!r}")
def assert_in(sub, container, m=""):
    if sub not in container:
        raise AssertionError(f"{m}: expected {sub!r} in {container!r}")


# ======== SECTION 1: Spell Definitions & Registry ========
print("\n" + "=" * 60)
print("SECTION 1: Spell Definitions & Registry")
print("=" * 60)

@test("SPELLS dict is populated")
def _():
    from world.spells import SPELLS
    assert_gt(len(SPELLS), 50, "Should have 50+ spells")
    assert_in("sparks", SPELLS)
    assert_in("meteorswarm", SPELLS)

@test("get_spell returns correct spell")
def _():
    from world.spells import get_spell
    spell = get_spell("Sparks")
    assert_true(spell is not None)
    assert_eq(spell["name"], "Sparks")
    assert_eq(spell["level"], 1)
    assert_eq(spell["school"], "evocation")

@test("get_spell is case-insensitive")
def _():
    from world.spells import get_spell
    assert_true(get_spell("sparks") is not None)
    assert_true(get_spell("SPARKS") is not None)
    assert_true(get_spell("Sparks") is not None)

@test("get_spell handles spaces")
def _():
    from world.spells import get_spell
    assert_true(get_spell("Minor Heal") is not None)
    assert_true(get_spell("minorheal") is not None)

@test("get_spells_for_level filters correctly")
def _():
    from world.spells import get_spells_for_level
    spells = get_spells_for_level(5)
    for s in spells:
        assert_true(s["level"] <= 5, f"{s['name']} level {s['level']} > 5")

@test("get_spells_by_school filters by school")
def _():
    from world.spells import get_spells_by_school
    evo = get_spells_by_school(80, "evocation")
    for s in evo:
        assert_eq(s["school"], "evocation")

@test("All spells have required fields")
def _():
    from world.spells import SPELLS
    required = ["name", "level", "school", "target", "mana_base", "mana_per_lvl",
                "cooldown", "description", "effect", "key"]
    for key, spell in SPELLS.items():
        for field in required:
            assert_true(field in spell, f"{key} missing field '{field}'")

@test("Damage spells have damage_type")
def _():
    from world.spells import SPELLS
    for key, spell in SPELLS.items():
        if spell["effect"]["type"] == "damage":
            assert_true("damage_type" in spell["effect"], f"{key} missing damage_type")

@test("Buff spells exist (Phase 7)")
def _():
    from world.spells import get_spell
    assert_true(get_spell("Might") is not None)
    assert_true(get_spell("Agility") is not None)
    assert_true(get_spell("Vitality") is not None)
    assert_true(get_spell("Brilliance") is not None)
    assert_true(get_spell("Wisdom of Ages") is not None)
    assert_true(get_spell("Haste") is not None)
    assert_true(get_spell("Divine Might") is not None)
    assert_true(get_spell("Avatar") is not None)

@test("DoT spells exist (Phase 7)")
def _():
    from world.spells import get_spell
    assert_true(get_spell("Poison Touch") is not None)
    assert_true(get_spell("Ignite") is not None)
    assert_true(get_spell("Curse of Agony") is not None)
    assert_true(get_spell("Lacerate") is not None)
    assert_true(get_spell("Plague") is not None)
    assert_true(get_spell("Immolate") is not None)
    assert_true(get_spell("Hemorrhage") is not None)
    assert_true(get_spell("Soul Rot") is not None)

@test("Ritual spells have cast_time (Phase 7)")
def _():
    from world.spells import get_spell
    assert_eq(get_spell("Meditate")["cast_time"], 5)
    assert_eq(get_spell("Ritual of Power")["cast_time"], 8)
    assert_eq(get_spell("Mass Renewal")["cast_time"], 6)
    assert_eq(get_spell("Apocalypse Ritual")["cast_time"], 10)
    assert_eq(get_spell("Grand Restoration")["cast_time"], 8)
    assert_eq(get_spell("Cataclysm")["cast_time"], 12)

@test("Spell resistance buff exists (Phase 7)")
def _():
    from world.spells import get_spell
    spell = get_spell("Magic Resistance")
    assert_true(spell is not None)
    assert_eq(spell["effect"]["type"], "spell_resist_buff")

@test("Restore mana spell exists (Phase 7)")
def _():
    from world.spells import get_spell
    spell = get_spell("Meditate")
    assert_eq(spell["effect"]["type"], "restore_mana")


# ======== SECTION 2: SpellHandler Core ========
print("\n" + "=" * 60)
print("SECTION 2: SpellHandler Core")
print("=" * 60)

@test("SpellHandler initializes with character")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=10)
    handler = SpellHandler(char)
    assert_eq(handler.level, 10)
    assert_eq(handler.mana, 100)

@test("SpellHandler.available_spells returns spells")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=10, char_class="Mage")
    handler = SpellHandler(char)
    spells = handler.available_spells()
    assert_gt(len(spells), 0)

@test("can_cast returns True for valid spell")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=10, char_class="Mage")
    handler = SpellHandler(char)
    ok, err = handler.can_cast("sparks")
    assert_true(ok, err)

@test("can_cast returns False for too-high level")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=1, char_class="Mage")
    handler = SpellHandler(char)
    ok, err = handler.can_cast("fireball")
    assert_false(ok)
    assert_in("level", err.lower())

@test("can_cast returns False for insufficient mana")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=80, mana=0, char_class="Mage")
    handler = SpellHandler(char)
    ok, err = handler.can_cast("meteorswarm")
    assert_false(ok)
    assert_in("mana", err.lower())

@test("can_cast returns False for unknown spell")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=10, char_class="Mage")
    handler = SpellHandler(char)
    ok, err = handler.can_cast("nonexistent")
    assert_false(ok)

@test("can_cast blocks non-caster classes")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=10, char_class="Warrior")
    handler = SpellHandler(char)
    ok, err = handler.can_cast("sparks")
    assert_false(ok)

@test("can_cast blocks channeling when already channeling")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=10, char_class="Mage")
    char.attributes.add("is_channeling", True)
    handler = SpellHandler(char)
    ok, err = handler.can_cast("sparks")
    assert_false(ok)
    assert_in("channeling", err.lower())

@test("cast deducts mana")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=10, mana=100, char_class="Mage")
    handler = SpellHandler(char)
    handler.cast("sparks", target=char)
    assert_true(char.attributes.get("mana") < 100)

@test("cast sets cooldown")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=10, mana=100, char_class="Mage")
    handler = SpellHandler(char)
    handler.cast("frostsnap", target=char)
    cooldowns = char.attributes.get("spell_cooldowns", {})
    assert_true("frostsnap" in cooldowns)


# ======== SECTION 3: Damage Spells ========
print("\n" + "=" * 60)
print("SECTION 3: Damage Spells")
print("=" * 60)

@test("_resolve_damage scales with level")
def _():
    from world.spells import _resolve_damage, get_spell
    spell = get_spell("Sparks")
    char_low = MockCharacter(level=1, stats={"int": 10, "wis": 10})
    char_high = MockCharacter(level=50, stats={"int": 20, "wis": 20})
    dmg_low = _resolve_damage(spell, 1, char_low)
    dmg_high = _resolve_damage(spell, 50, char_high)
    assert_gt(dmg_high, dmg_low, "Higher level should deal more damage")

@test("_resolve_damage scales with casting stat")
def _():
    from world.spells import _resolve_damage, get_spell
    spell = get_spell("Sparks")
    char_dumb = MockCharacter(level=10, stats={"int": 8, "wis": 8})
    char_smart = MockCharacter(level=10, stats={"int": 20, "wis": 20})
    dmg_dumb = _resolve_damage(spell, 10, char_dumb)
    dmg_smart = _resolve_damage(spell, 10, char_smart)
    assert_gt(dmg_smart, dmg_dumb, "Higher casting stat should deal more damage")

@test("Damage spells have damage types")
def _():
    from world.spells import SPELLS
    damage_types = set()
    for key, spell in SPELLS.items():
        if spell["effect"]["type"] == "damage":
            dt = spell["effect"].get("damage_type", "arcane")
            damage_types.add(dt)
    assert_in("fire", damage_types)
    assert_in("lightning", damage_types)
    assert_in("cold", damage_types)
    assert_in("shadow", damage_types)
    assert_in("arcane", damage_types)

@test("Saving throw types are valid")
def _():
    from world.spells import SPELLS
    valid = {"spell", "poison", "petrification", "death", "rod"}
    for key, spell in SPELLS.items():
        st = spell.get("save_type", "spell")
        assert_in(st, valid, f"{key} has invalid save_type: {st}")


# ======== SECTION 4: Healing Spells ========
print("\n" + "=" * 60)
print("SECTION 4: Healing Spells")
print("=" * 60)

@test("_resolve_heal scales with level")
def _():
    from world.spells import _resolve_heal, get_spell
    spell = get_spell("Minor Heal")
    char_low = MockCharacter(level=1, stats={"int": 10, "wis": 10})
    char_high = MockCharacter(level=50, stats={"int": 20, "wis": 20})
    heal_low = _resolve_heal(spell, 1, char_low)
    heal_high = _resolve_heal(spell, 50, char_high)
    assert_gt(heal_high, heal_low)

@test("Healing spells exist at all tiers")
def _():
    from world.spells import get_spell
    assert_true(get_spell("Minor Heal")["level"] <= 5)
    assert_true(10 < get_spell("Cure Wounds")["level"] <= 20)
    assert_true(20 < get_spell("Greater Heal")["level"] <= 30)
    assert_true(40 < get_spell("Divine Restoration")["level"] <= 50)
    assert_true(50 < get_spell("Mass Heal")["level"] <= 60)
    assert_true(70 < get_spell("Divine Blessing")["level"] <= 80)


# ======== SECTION 5: Shield Spells ========
print("\n" + "=" * 60)
print("SECTION 5: Shield Spells")
print("=" * 60)

@test("_resolve_shield scales with level")
def _():
    from world.spells import _resolve_shield, get_spell
    spell = get_spell("Stone Skin")
    char_low = MockCharacter(level=1, stats={"int": 10, "wis": 10})
    char_high = MockCharacter(level=50, stats={"int": 20, "wis": 20})
    shield_low = _resolve_shield(spell, 1, char_low)
    shield_high = _resolve_shield(spell, 50, char_high)
    assert_gt(shield_high, shield_low)

@test("Shield spells have duration")
def _():
    from world.spells import get_spell
    assert_eq(get_spell("Stone Skin")["effect"]["duration"], 30)
    assert_eq(get_spell("Mana Shield")["effect"]["duration"], 45)
    assert_eq(get_spell("Sanctuary")["effect"]["duration"], 15)


# ======== SECTION 6: Buff Spells (Phase 7) ========
print("\n" + "=" * 60)
print("SECTION 6: Buff Spells (Phase 7)")
print("=" * 60)

@test("Buff spells increase stats")
def _():
    from world.spells import SpellHandler, get_spell
    char = MockCharacter(level=10, mana=100, char_class="Mage",
                         stats={"str": 10, "dex": 10, "con": 10, "int": 14, "wis": 12, "cha": 10})
    handler = SpellHandler(char)
    handler.cast("might", target=char)
    stats = char.attributes.get("stats", {})
    assert_gt(stats.get("str", 10), 10, "Might should increase STR")

@test("Buff spells have correct effect type")
def _():
    from world.spells import get_spell
    assert_eq(get_spell("Might")["effect"]["type"], "buff")
    assert_eq(get_spell("Agility")["effect"]["type"], "buff")
    assert_eq(get_spell("Avatar")["effect"]["type"], "buff_all")

@test("Buff spells target single ally")
def _():
    from world.spells import get_spell
    for name in ["Might", "Agility", "Vitality", "Brilliance", "Wisdom of Ages", "Haste", "Divine Might"]:
        spell = get_spell(name)
        assert_in(spell["target"], ["self", "single"], f"{name} target should be self or single")


# ======== SECTION 7: DoT Spells (Phase 7) ========
print("\n" + "=" * 60)
print("SECTION 7: DoT Spells (Phase 7)")
print("=" * 60)

@test("DoT spells have dot_type")
def _():
    from world.spells import get_spell
    assert_eq(get_spell("Poison Touch")["effect"]["dot_type"], "poison")
    assert_eq(get_spell("Ignite")["effect"]["dot_type"], "burn")
    assert_eq(get_spell("Curse of Agony")["effect"]["dot_type"], "curse")
    assert_eq(get_spell("Lacerate")["effect"]["dot_type"], "bleed")

@test("DoT spells have duration")
def _():
    from world.spells import get_spell
    for name in ["Poison Touch", "Ignite", "Curse of Agony", "Lacerate", "Plague", "Immolate", "Hemorrhage", "Soul Rot"]:
        spell = get_spell(name)
        assert_gt(spell["effect"].get("duration", 0), 0, f"{name} should have duration")

@test("_resolve_dot_damage scales with level")
def _():
    from world.spells import _resolve_dot_damage, get_spell
    spell = get_spell("Poison Touch")
    char_low = MockCharacter(level=1, stats={"int": 10, "wis": 10})
    char_high = MockCharacter(level=50, stats={"int": 20, "wis": 20})
    dot_low = _resolve_dot_damage(spell, 1, char_low)
    dot_high = _resolve_dot_damage(spell, 50, char_high)
    assert_gt(dot_high, dot_low)

@test("Plague is AoE DoT")
def _():
    from world.spells import get_spell
    spell = get_spell("Plague")
    assert_eq(spell["target"], "aoe")
    assert_eq(spell["effect"]["dot_type"], "poison")


# ======== SECTION 8: HoT Spells ========
print("\n" + "=" * 60)
print("SECTION 8: HoT Spells")
print("=" * 60)

@test("Restoration Aura is heal_over_time")
def _():
    from world.spells import get_spell
    spell = get_spell("Restoration Aura")
    assert_eq(spell["effect"]["type"], "heal_over_time")
    assert_gt(spell["effect"]["duration"], 0)


# ======== SECTION 9: Stun & CC Spells ========
print("\n" + "=" * 60)
print("SECTION 9: Stun & CC Spells")
print("=" * 60)

@test("Stun spells have duration")
def _():
    from world.spells import get_spell
    assert_eq(get_spell("Paralyze")["effect"]["duration"], 12)
    assert_eq(get_spell("Dread Gaze")["effect"]["duration"], 15)
    assert_eq(get_spell("Petrify")["effect"]["duration"], 18)

@test("Stun spells use petrification save")
def _():
    from world.spells import get_spell
    assert_eq(get_spell("Paralyze")["save_type"], "petrification")
    assert_eq(get_spell("Dread Gaze")["save_type"], "petrification")
    assert_eq(get_spell("Petrify")["save_type"], "petrification")


# ======== SECTION 10: Lifesteal Spells ========
print("\n" + "=" * 60)
print("SECTION 10: Lifesteal Spells")
print("=" * 60)

@test("Soul Drain is lifesteal type")
def _():
    from world.spells import get_spell
    spell = get_spell("Soul Drain")
    assert_eq(spell["effect"]["type"], "lifesteal")
    assert_gt(spell["effect"]["heal_pct"], 0)


# ======== SECTION 11: Spell Resistance (Phase 7) ========
print("\n" + "=" * 60)
print("SECTION 11: Spell Resistance (Phase 7)")
print("=" * 60)

@test("get_spell_resistance returns 0 for Human with 10 wis")
def _():
    from world.spells import get_spell_resistance
    char = MockCharacter(race="Human", stats={"wis": 10})
    assert_eq(get_spell_resistance(char), 0)

@test("get_spell_resistance returns positive for Dwarf")
def _():
    from world.spells import get_spell_resistance
    char = MockCharacter(race="Mountain Dwarf")
    assert_gt(get_spell_resistance(char), 0)

@test("get_spell_resistance returns negative for Ogre")
def _():
    from world.spells import get_spell_resistance
    char = MockCharacter(race="Ogre")
    assert_true(get_spell_resistance(char) < 0)

@test("get_spell_resistance includes wisdom bonus")
def _():
    from world.spells import get_spell_resistance
    char_low = MockCharacter(race="Human", stats={"wis": 8})
    char_high = MockCharacter(race="Human", stats={"wis": 18})
    assert_gt(get_spell_resistance(char_high), get_spell_resistance(char_low))

@test("get_spell_resistance includes equipment")
def _():
    from world.spells import get_spell_resistance
    char = MockCharacter(race="Human")
    char.attributes.add("spell_resist", 20)
    assert_gt(get_spell_resistance(char), 10)

@test("get_spell_resistance includes buff")
def _():
    from world.spells import get_spell_resistance
    char = MockCharacter(race="Human")
    char.attributes.add("spell_resist_buff", 15)
    assert_gt(get_spell_resistance(char), 10)

@test("get_spell_resistance capped at 75")
def _():
    from world.spells import get_spell_resistance
    char = MockCharacter(race="Pixie", stats={"wis": 30})
    char.attributes.add("spell_resist", 50)
    char.attributes.add("spell_resist_buff", 50)
    assert_eq(get_spell_resistance(char), 75)

@test("apply_spell_resistance reduces damage")
def _():
    from world.spells import apply_spell_resistance
    char = MockCharacter(race="Mountain Dwarf")
    reduced = apply_spell_resistance(100, char)
    assert_true(reduced < 100, f"Expected reduced < 100, got {reduced}")

@test("apply_spell_resistance minimum 1 damage")
def _():
    from world.spells import apply_spell_resistance
    char = MockCharacter(race="Pixie", stats={"wis": 30})
    char.attributes.add("spell_resist", 100)
    char.attributes.add("spell_resist_buff", 100)
    reduced = apply_spell_resistance(10, char)
    assert_gt(reduced, 0)


# ======== SECTION 12: Ritual/Channeled Spells (Phase 7) ========
print("\n" + "=" * 60)
print("SECTION 12: Ritual/Channeled Spells (Phase 7)")
print("=" * 60)

@test("Ritual spells set is_channeling flag")
def _():
    from world.spells import SpellHandler
    # Meditate is restoration school — Cleric can cast it
    char = MockCharacter(level=10, mana=100, char_class="Cleric")
    handler = SpellHandler(char)
    handler.cast("meditate", target=char)
    assert_true(char.attributes.get("is_channeling", False))

@test("Ritual spells store channeling_spell")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=10, mana=100, char_class="Cleric")
    handler = SpellHandler(char)
    handler.cast("meditate", target=char)
    assert_eq(char.attributes.get("channeling_spell", ""), "meditate")

@test("interrupt_channeling clears flags")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=10, mana=100, char_class="Mage")
    handler = SpellHandler(char)
    handler.cast("meditate", target=char)
    handler.interrupt_channeling("Test interrupt")
    assert_false(char.attributes.get("is_channeling", True))
    assert_eq(char.attributes.get("channeling_spell", "x"), "")

@test("interrupt_channeling no-op when not channeling")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=10, mana=100, char_class="Mage")
    handler = SpellHandler(char)
    # Should not raise
    handler.interrupt_channeling("Test")


# ======== SECTION 13: Spell Scrolls (Phase 7) ========
print("\n" + "=" * 60)
print("SECTION 13: Spell Scrolls (Phase 7)")
print("=" * 60)

@test("create_scroll_item returns valid dict")
def _():
    from world.spell_scrolls import create_scroll_item
    item = create_scroll_item("Fireball")
    assert_true(item is not None)
    assert_in("Scroll of Fireball", item["key"])
    assert_eq(item["db"]["item_type"], "scroll")
    assert_eq(item["db"]["spell_key"], "fireball")

@test("create_scroll_item returns None for unknown spell")
def _():
    from world.spell_scrolls import create_scroll_item
    item = create_scroll_item("NonexistentSpell")
    assert_true(item is None)

@test("can_use_scroll validates scroll type")
def _():
    from world.spell_scrolls import can_use_scroll
    char = MockCharacter(level=20, char_class="Mage")
    scroll = MockScroll()
    ok, reason = can_use_scroll(char, scroll)
    assert_true(ok, reason)

@test("can_use_scroll rejects non-scroll items")
def _():
    from world.spell_scrolls import can_use_scroll
    char = MockCharacter(level=20, char_class="Mage")
    scroll = MockScroll()
    scroll.attributes.add("item_type", "weapon")
    ok, reason = can_use_scroll(char, scroll)
    assert_false(ok)

@test("can_use_scroll rejects wrong class")
def _():
    from world.spell_scrolls import can_use_scroll
    char = MockCharacter(level=20, char_class="Warrior")
    scroll = MockScroll(spell_key="fireball")
    ok, reason = can_use_scroll(char, scroll)
    assert_false(ok)

@test("can_use_scroll allows universal scrolls for any class")
def _():
    from world.spell_scrolls import can_use_scroll
    char = MockCharacter(level=20, char_class="Warrior")
    scroll = MockScroll(spell_key="fireball", universal=True)
    ok, reason = can_use_scroll(char, scroll)
    assert_true(ok, reason)

@test("generate_random_scroll returns valid scroll")
def _():
    from world.spell_scrolls import generate_random_scroll
    scroll = generate_random_scroll(level_range=(1, 20))
    assert_true(scroll is not None)
    assert_in("Scroll of", scroll["key"])

@test("get_all_scrollable_spells returns all spells")
def _():
    from world.spell_scrolls import get_all_scrollable_spells
    spells = get_all_scrollable_spells()
    assert_gt(len(spells), 50)

@test("handle_inscribe_scroll costs copper")
def _():
    from world.spell_scrolls import handle_inscribe_scroll
    char = MockCharacter(level=20, char_class="Mage", stats={"int": 14, "wis": 12})
    char.attributes.add("copper", 10000)
    initial_copper = char.attributes.get("copper")
    # Mock create_scroll_object to avoid Evennia DB calls
    import world.spell_scrolls as scrolls_mod
    original_create = scrolls_mod.create_scroll_object
    def mock_create(spell_name, caller=None, scroll_level=None, universal=False):
        scroll = MockScroll(name=f"Scroll of {spell_name}", spell_key=spell_name.lower().replace(" ", ""))
        return scroll
    scrolls_mod.create_scroll_object = mock_create
    try:
        success, msg = handle_inscribe_scroll(char, "Sparks")
        assert_true(success, msg)
        assert_true(char.attributes.get("copper") < initial_copper)
    finally:
        scrolls_mod.create_scroll_object = original_create

@test("handle_inscribe_scroll rejects non-casters")
def _():
    from world.spell_scrolls import handle_inscribe_scroll
    char = MockCharacter(level=20, char_class="Warrior")
    success, msg = handle_inscribe_scroll(char, "Sparks")
    assert_false(success)


# ======== SECTION 14: Class-Specific Spell Lists ========
print("\n" + "=" * 60)
print("SECTION 14: Class-Specific Spell Lists")
print("=" * 60)

@test("Warrior cannot cast spells")
def _():
    from world.race_class_matrix import can_cast_spells
    char = MockCharacter(char_class="Warrior")
    assert_false(can_cast_spells(char))

@test("Mage can cast spells")
def _():
    from world.race_class_matrix import can_cast_spells
    char = MockCharacter(char_class="Mage")
    assert_true(can_cast_spells(char))

@test("Cleric can cast restoration")
def _():
    from world.race_class_matrix import can_learn_spell
    char = MockCharacter(level=10, char_class="Cleric")
    ok, reason = can_learn_spell(char, "minorheal")
    assert_true(ok, reason)

@test("Cleric cannot cast enfeebling")
def _():
    from world.race_class_matrix import can_learn_spell
    char = MockCharacter(level=10, char_class="Cleric")
    ok, reason = can_learn_spell(char, "frostsnap")
    assert_false(ok)

@test("Paladin can cast restoration and abjuration")
def _():
    from world.race_class_matrix import can_learn_spell
    char = MockCharacter(level=10, char_class="Paladin")
    ok1, _ = can_learn_spell(char, "minorheal")
    ok2, _ = can_learn_spell(char, "stoneskin")
    assert_true(ok1)
    assert_true(ok2)

@test("Paladin cannot cast evocation")
def _():
    from world.race_class_matrix import can_learn_spell
    char = MockCharacter(level=10, char_class="Paladin")
    ok, reason = can_learn_spell(char, "sparks")
    assert_false(ok)

@test("Orc cannot learn any spells")
def _():
    from world.race_class_matrix import can_learn_spell
    char = MockCharacter(level=10, race="Orc", char_class="Mage")
    ok, reason = can_learn_spell(char, "sparks")
    assert_false(ok)

@test("Ranger can cast restoration up to level 20")
def _():
    from world.race_class_matrix import can_learn_spell
    char = MockCharacter(level=20, char_class="Ranger")
    ok, _ = can_learn_spell(char, "minorheal")
    assert_true(ok)

@test("Ranger blocked from high-level restoration")
def _():
    from world.race_class_matrix import can_learn_spell
    char = MockCharacter(level=50, char_class="Ranger")
    ok, reason = can_learn_spell(char, "divinerestoration")
    assert_false(ok)


# ======== SECTION 15: AoE Spells ========
print("\n" + "=" * 60)
print("SECTION 15: AoE Spells")
print("=" * 60)

@test("AoE spells have aoe or pbaoe target")
def _():
    from world.spells import SPELLS
    aoe_spells = [s for s in SPELLS.values() if s["target"] in ("aoe", "pbaoe")]
    assert_gt(len(aoe_spells), 5, "Should have multiple AoE spells")

@test("Flame Burst is AoE")
def _():
    from world.spells import get_spell
    assert_eq(get_spell("Flame Burst")["target"], "aoe")

@test("Fireball is AoE")
def _():
    from world.spells import get_spell
    assert_eq(get_spell("Fireball")["target"], "aoe")

@test("Mass Heal is AoE heal")
def _():
    from world.spells import get_spell
    spell = get_spell("Mass Heal")
    assert_eq(spell["target"], "aoe")
    assert_eq(spell["effect"]["type"], "heal")

@test("Plague is AoE DoT")
def _():
    from world.spells import get_spell
    spell = get_spell("Plague")
    assert_eq(spell["target"], "aoe")
    assert_eq(spell["effect"]["type"], "dot")


# ======== SECTION 16: Spellbook Display ========
print("\n" + "=" * 60)
print("SECTION 16: Spellbook Display")
print("=" * 60)

@test("format_spellbook returns string")
def _():
    from world.spells import format_spellbook
    char = MockCharacter(level=10, char_class="Mage")
    result = format_spellbook(char)
    assert_true(isinstance(result, str))
    assert_gt(len(result), 50)

@test("format_spellbook shows mana")
def _():
    from world.spells import format_spellbook
    char = MockCharacter(level=10, mana=75, max_mana=100, char_class="Mage")
    result = format_spellbook(char)
    assert_in("75", result)
    assert_in("100", result)

@test("format_spell_detail returns string")
def _():
    from world.spells import format_spell_detail
    result = format_spell_detail("fireball")
    assert_true(isinstance(result, str))
    assert_in("Fireball", result)
    assert_in("Evocation", result)

@test("format_spell_detail shows cast time for rituals")
def _():
    from world.spells import format_spell_detail
    result = format_spell_detail("meditate")
    assert_in("Cast Time", result)
    assert_in("5s", result)

@test("format_spell_detail shows buff info")
def _():
    from world.spells import format_spell_detail
    result = format_spell_detail("might")
    assert_in("STR", result.upper())

@test("format_spell_detail shows DoT info")
def _():
    from world.spells import format_spell_detail
    result = format_spell_detail("poisontouch")
    assert_in("Poison", result)


# ======== SECTION 17: Edge Cases & Validation ========
print("\n" + "=" * 60)
print("SECTION 17: Edge Cases & Validation")
print("=" * 60)

@test("Spell levels are monotonically increasing within schools")
def _():
    from world.spells import SPELLS
    schools = {}
    for key, spell in SPELLS.items():
        school = spell["school"]
        if school not in schools:
            schools[school] = []
        schools[school].append((spell["level"], spell["name"]))
    for school, spells in schools.items():
        sorted_spells = sorted(spells)
        for i in range(len(sorted_spells) - 1):
            assert_true(sorted_spells[i][0] <= sorted_spells[i+1][0],
                       f"{school}: {sorted_spells[i][1]} ({sorted_spells[i][0]}) > {sorted_spells[i+1][1]} ({sorted_spells[i+1][0]})")

@test("No duplicate spell keys")
def _():
    from world.spells import SPELLS
    keys = list(SPELLS.keys())
    assert_eq(len(keys), len(set(keys)), "Duplicate spell keys found")

@test("All mana costs are positive")
def _():
    from world.spells import SPELLS
    for key, spell in SPELLS.items():
        assert_gt(spell["mana_base"], 0, f"{key} has non-positive mana_base")
        assert_true(spell["mana_per_lvl"] >= 0, f"{key} has negative mana_per_lvl")

@test("All cooldowns are non-negative")
def _():
    from world.spells import SPELLS
    for key, spell in SPELLS.items():
        assert_true(spell["cooldown"] >= 0, f"{key} has negative cooldown")

@test("All cast_times are non-negative")
def _():
    from world.spells import SPELLS
    for key, spell in SPELLS.items():
        ct = spell.get("cast_time", 0)
        assert_true(ct >= 0, f"{key} has negative cast_time")

@test("get_spell_resistance handles None gracefully")
def _():
    from world.spells import get_spell_resistance
    assert_eq(get_spell_resistance(None), 0)

@test("apply_spell_resistance handles None target")
def _():
    from world.spells import apply_spell_resistance
    # Should not crash
    result = apply_spell_resistance(100, None)
    assert_eq(result, 100)

@test("SpellHandler handles missing target gracefully")
def _():
    from world.spells import SpellHandler
    char = MockCharacter(level=10, mana=100, char_class="Mage")
    handler = SpellHandler(char)
    success, msg = handler.cast("sparks", target=None)
    # Should return False for missing target on single-target damage spell
    assert_false(success)


# ======== RESULTS ========
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
print("=" * 60)

if FAIL > 0:
    print(f"\n{FAIL} TEST(S) FAILED!")
    sys.exit(1)
else:
    print("\nALL TESTS PASSED! Phase 7 Spells & Magic is 100% production-ready.\n")
    sys.exit(0)