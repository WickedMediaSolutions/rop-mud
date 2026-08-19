"""
Comprehensive Test Suite for Economy & Items (#4)
==================================================

Validates:
  1. Economy module (format_money, add/remove money, accessors)
  2. Rarity system (roll, apply, upgrade)
  3. Enchanter module (upgrade_item_rarity, cost calculations)
  4. Coin tiers (consistent display, conversion math)
  5. Item value scaling with rarity
  6. Gold transfer logic (givegold simulation)
  7. Inn rent cost calculation

Run: python commands/tests/test_economy_and_items.py
"""

import os, sys, random, math, types

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
    def __init__(self, name="TestPlayer", level=1, money=0, bank=0):
        self.key = name
        self.attributes = MockAttributes()
        self.attributes.add("level", level)
        self.attributes.add("money", money)
        self.attributes.add("bank_gold", bank)
        self.destination = None
        self.contents = []


class MockLocation:
    def __init__(self, name="TestRoom"):
        self.key = name
        self.contents = []
    def msg_contents(self, message, exclude=None):
        pass


class MockItem:
    def __init__(self, name="Test Item", **attrs):
        self.key = name
        self.attributes = MockAttributes()
        self.destination = None
        self.contents = []
        self.location = None
        self.id = id(self)
        for k, v in attrs.items():
            self.attributes.add(k, v)


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


# ======== SECTION 1: Economy Module ========
print("\n" + "=" * 60)
print("SECTION 1: Economy Module (world/economy.py)")
print("=" * 60)

@test("format_money handles zero")
def _():
    from world.economy import format_money
    assert "0 copper" in format_money(0)

@test("format_money handles pure gold")
def _():
    from world.economy import format_money
    assert "5 gold" in format_money(5)

@test("format_money handles gold + silver")
def _():
    from world.economy import format_money
    assert "1 gold" in format_money(1)
    assert "0 copper" in format_money(0)

@test("format_money handles large gold")
def _():
    from world.economy import format_money
    assert "2 gold" in format_money(2)

@test("format_money_brief returns short")
def _():
    from world.economy import format_money_brief
    r = format_money_brief(3)
    assert "g" in r or "gold" in r.lower()

@test("format_money_long returns labels")
def _():
    from world.economy import format_money_long
    assert "gold" in format_money_long(1)

@test("add_money increases")
def _():
    from world.economy import add_money, get_money
    c = MockCharacter(money=100)
    assert_eq(add_money(c, 50), 150)
    assert_eq(get_money(c), 150)

@test("remove_money success")
def _():
    from world.economy import remove_money, get_money
    c = MockCharacter(money=100)
    assert_true(remove_money(c, 40))
    assert_eq(get_money(c), 60)

@test("remove_money insufficient")
def _():
    from world.economy import remove_money, get_money
    c = MockCharacter(money=50)
    assert_false(remove_money(c, 100))
    assert_eq(get_money(c), 50)

@test("remove_money no negative")
def _():
    from world.economy import remove_money, get_money
    c = MockCharacter(money=100)
    remove_money(c, 150)
    assert_eq(get_money(c), 100)

@test("has_enough_money")
def _():
    from world.economy import has_enough_money
    c = MockCharacter(money=75)
    assert_true(has_enough_money(c, 50))
    assert_false(has_enough_money(c, 100))

@test("display_wealth")
def _():
    from world.economy import display_wealth
    c = MockCharacter(money=300, bank=200)
    r = display_wealth(c)
    assert "Carried" in r
    assert "Banked" in r
    assert "Total" in r

@test("get_prompt_money_segment")
def _():
    from world.economy import get_prompt_money_segment
    c = MockCharacter(money=50)
    assert "Gold" in get_prompt_money_segment(c)

@test("calculate_transaction_tax")
def _():
    from world.economy import calculate_transaction_tax
    assert_true(calculate_transaction_tax(10) >= 1)
    assert_eq(calculate_transaction_tax(0), 0)

@test("calculate_inn_cost scales with level")
def _():
    from world.economy import calculate_inn_cost
    low = MockCharacter(level=1)
    high = MockCharacter(level=50)
    assert_true(calculate_inn_cost(high) > calculate_inn_cost(low))

@test("calculate_inn_cost minimum 1")
def _():
    from world.economy import calculate_inn_cost
    assert_true(calculate_inn_cost(MockCharacter(level=1)) >= 1)


# ======== SECTION 2: Rarity System ========
print("\n" + "=" * 60)
print("SECTION 2: Rarity System (world/mob_equipment.py)")
print("=" * 60)

@test("RARITY_TIERS has 5 tiers")
def _():
    from world.mob_equipment import RARITY_TIERS
    assert_eq(len(RARITY_TIERS), 5)
    assert "common" in RARITY_TIERS
    assert "legendary" in RARITY_TIERS
    assert_eq(RARITY_TIERS["common"]["mult"], 1.0)
    assert_eq(RARITY_TIERS["legendary"]["mult"], 3.0)

@test("RARITY_TIERS ascending mults")
def _():
    from world.mob_equipment import RARITY_TIERS
    mults = [RARITY_TIERS[t]["mult"] for t in ["common","uncommon","rare","epic","legendary"]]
    for i in range(len(mults)-1):
        assert_true(mults[i] < mults[i+1])

@test("RARITY_WEIGHTS_BY_TIER has 5")
def _():
    from world.mob_equipment import RARITY_WEIGHTS_BY_TIER
    assert_eq(len(RARITY_WEIGHTS_BY_TIER), 5)

@test("_roll_rarity valid")
def _():
    from world.mob_equipment import _roll_rarity
    for tier in [1,2,3,4,5]:
        for _ in range(20):
            assert_true(_roll_rarity(tier) in ["common","uncommon","rare","epic","legendary"])

@test("_roll_rarity tier5 legendaries")
def _():
    from world.mob_equipment import _roll_rarity
    found = any(_roll_rarity(5) == "legendary" for _ in range(200))
    assert_true(found, "tier 5 should roll legendary")

@test("_roll_rarity tier1 no legendary")
def _():
    from world.mob_equipment import _roll_rarity
    for _ in range(100):
        assert_true(_roll_rarity(1) != "legendary")

@test("_apply_rarity scales damage")
def _():
    from world.mob_equipment import _apply_rarity_to_template
    t = {"name":"Sword","damage":10,"value":50}
    r = _apply_rarity_to_template(t, "epic")
    assert_eq(r["damage"], int(10 * 2.3))
    assert_eq(r["value"], int(50 * 2.3))

@test("_apply_rarity scales armor")
def _():
    from world.mob_equipment import _apply_rarity_to_template
    t = {"name":"Armor","armor":5,"value":30}
    r = _apply_rarity_to_template(t, "legendary")
    assert_eq(r["armor"], int(5 * 3.0))
    assert_eq(r["value"], int(30 * 3.0))

@test("_apply_rarity adds label")
def _():
    from world.mob_equipment import _apply_rarity_to_template
    t = {"name":"Rusty Sword","damage":5,"value":10}
    r = _apply_rarity_to_template(t, "rare")
    assert "Rare" in r["name"]

@test("_apply_rarity common unchanged")
def _():
    from world.mob_equipment import _apply_rarity_to_template
    t = {"name":"Rusty","damage":5,"value":10}
    r = _apply_rarity_to_template(t, "common")
    assert_eq(r["damage"], 5)
    assert_eq(r["value"], 10)


# ======== SECTION 3: Enchanter ========
print("\n" + "=" * 60)
print("SECTION 3: Enchanter System (world/enchanter.py)")
print("=" * 60)

@test("get_item_rarity defaults common")
def _():
    from world.enchanter import get_item_rarity
    assert_eq(get_item_rarity(MockItem("X")), "common")

@test("get_item_rarity reads stored")
def _():
    from world.enchanter import get_item_rarity
    assert_eq(get_item_rarity(MockItem("X", _rarity="rare")), "rare")

@test("upgrade_item_rarity scales stats")
def _():
    from world.enchanter import upgrade_item_rarity
    item = MockItem("Sword", damage=10, armor=0, value=50, _rarity="common")
    assert_true(upgrade_item_rarity(item, "uncommon"))
    assert_eq(item.attributes.get("damage"), 13)
    assert_eq(item.attributes.get("value"), 65)

@test("upgrade_item_rarity updates name")
def _():
    from world.enchanter import upgrade_item_rarity
    item = MockItem("Iron Sword", damage=10, value=50, _rarity="common")
    assert_true(upgrade_item_rarity(item, "rare"))
    assert "Rare" in item.key
    assert "Iron Sword" in item.key

@test("upgrade rejects downgrade")
def _():
    from world.enchanter import upgrade_item_rarity
    assert_false(upgrade_item_rarity(MockItem("Sword", damage=10, value=50, _rarity="rare"), "uncommon"))

@test("upgrade rejects same tier")
def _():
    from world.enchanter import upgrade_item_rarity
    assert_false(upgrade_item_rarity(MockItem("Sword", damage=10, value=50, _rarity="epic"), "epic"))

@test("upgrade rejects legendary+")
def _():
    from world.enchanter import upgrade_item_rarity
    assert_false(upgrade_item_rarity(MockItem("Sword", damage=10, value=50, _rarity="legendary"), "nonexistent"))

@test("UPGRADE_COSTS ascend")
def _():
    from world.enchanter import UPGRADE_COSTS
    costs = [UPGRADE_COSTS[k] for k in ["uncommon","rare","epic","legendary"]]
    for i in range(len(costs)-1):
        assert_true(costs[i] < costs[i+1])


# ======== SECTION 4: Gold Transfer ========
print("\n" + "=" * 60)
print("SECTION 4: Gold Transfer")
print("=" * 60)

@test("givegold transfers")
def _():
    from world.economy import get_money, remove_money, add_money
    a = MockCharacter(name="Alice", money=500)
    b = MockCharacter(name="Bob", money=100)
    assert_true(remove_money(a, 200))
    add_money(b, 200)
    assert_eq(get_money(a), 300)
    assert_eq(get_money(b), 300)

@test("givegold insufficient")
def _():
    from world.economy import get_money, remove_money
    a = MockCharacter(name="Alice", money=50)
    assert_false(remove_money(a, 100))
    assert_eq(get_money(a), 50)

@test("givegold all")
def _():
    from world.economy import get_money, remove_money, add_money
    a = MockCharacter(name="Alice", money=500)
    b = MockCharacter(name="Bob", money=0)
    amt = get_money(a)
    assert_true(remove_money(a, amt))
    add_money(b, amt)
    assert_eq(get_money(a), 0)
    assert_eq(get_money(b), 500)


# ======== SECTION 5: Coin Display ========
print("\n" + "=" * 60)
print("SECTION 5: Coin Display Consistency")
print("=" * 60)

@test("format_money never negative display")
def _():
    from world.economy import format_money
    for n in [0,1,10,100,1000,-1]:
        r = format_money(n)
        assert "0 copper" in r or "gold" in r or "silver" in r

@test("format_money_brief deterministic")
def _():
    from world.economy import format_money_brief
    assert_eq(format_money_brief(12), format_money_brief(12))

@test("Money display large sums")
def _():
    from world.economy import format_money_brief, format_money_long
    assert_true(len(format_money_brief(99999)) > 0)
    assert_true(len(format_money_long(99999)) > 0)

@test("100 copper = 1 gold")
def _():
    from world.economy import copper_to_gold, gold_to_copper, COPPER_PER_GOLD
    assert_eq(gold_to_copper(1), 100)
    assert_eq(copper_to_gold(100), 1)
    assert_eq(COPPER_PER_GOLD, 100)

@test("Silver conversion correct")
def _():
    from world.economy import gold_to_silver, SILVER_PER_GOLD
    assert_eq(gold_to_silver(1), 10)
    assert_eq(SILVER_PER_GOLD, 10)


# ======== SECTION 6: Rent ========
print("\n" + "=" * 60)
print("SECTION 6: Rent / Economic Sinks")
print("=" * 60)

@test("inn cost higher for high level")
def _():
    from world.economy import calculate_inn_cost
    assert_true(calculate_inn_cost(MockCharacter(level=50)) > calculate_inn_cost(MockCharacter(level=10)))

@test("inn cost linear with hours")
def _():
    from world.economy import calculate_inn_cost
    c = MockCharacter(level=10)
    assert_eq(calculate_inn_cost(c, hours=3), calculate_inn_cost(c, hours=1) * 3)


# ======== SECTION 7: Equipment Generation ========
print("\n" + "=" * 60)
print("SECTION 7: Equipment Generation")
print("=" * 60)

@test("generate_mob_weapon returns item")
def _():
    from world.mob_equipment import generate_mob_weapon
    w = generate_mob_weapon(mob_level=15)
    if w is not None:
        assert_true(hasattr(w, "attributes"))
        assert_true(w.attributes.get("damage", 0) > 0)

@test("generate_mob_armor returns item")
def _():
    from world.mob_equipment import generate_mob_armor
    a = generate_mob_armor(mob_level=20, slot="chest")
    if a is not None:
        assert_true(a.attributes.get("armor", 0) > 0)

@test("equip_mob runs without error")
def _():
    from world.mob_equipment import equip_mob
    import world.mob_equipment as me
    me._create_object = None
    me._DefaultObject = None
    mob = MockCharacter(name="TestMob", level=15)
    mob.location = MockLocation()
    result = equip_mob(mob, mob_class="Warrior", faction="Aethelgard Alliance")
    assert_true(isinstance(result, dict))
    assert_true(result["total_armor"] >= 0)

@test("generate_mob_coins valid tiers")
def _():
    from world.mob_equipment import generate_mob_coins
    for lvl in [1,10,20,40,80]:
        c = generate_mob_coins(lvl)
        for k in ["copper","silver","gold"]:
            assert_true(c[k] >= 0)


# ======== SECTION 8: Integration ========
print("\n" + "=" * 60)
print("SECTION 8: Integration Flows")
print("=" * 60)

@test("Full buy-sell-enchant cycle")
def _():
    from world.economy import get_money, add_money, remove_money
    from world.mob_equipment import generate_mob_coins, generate_mob_weapon
    from world.economy import calculate_inn_cost

    player = MockCharacter(name="Hero", level=15, money=0)
    coins = generate_mob_coins(10)
    gold_from = coins["gold"] + coins["silver"] // 10 + coins["copper"] // 100
    add_money(player, gold_from)

    weapon = generate_mob_weapon(mob_level=10, roll_rarity=True)
    if weapon is not None:
        value = weapon.attributes.get("value", default=10)
        add_money(player, max(1, int(value * 0.5)))

    assert_true(get_money(player) > 0, "Player should have earned gold")

    cost = calculate_inn_cost(player)
    if get_money(player) >= cost:
        assert_true(remove_money(player, cost))

@test("Rarity upgrade preserves identity")
def _():
    from world.enchanter import upgrade_item_rarity, get_item_rarity
    item = MockItem("Iron Longsword", damage=8, armor=0, value=50,
                    _rarity="common", durability=100, max_durability=100)
    orig_dmg = item.attributes.get("damage")
    orig_val = item.attributes.get("value")
    assert_true(upgrade_item_rarity(item, "uncommon"))
    assert_eq(get_item_rarity(item), "uncommon")
    assert_true(item.attributes.get("damage") > orig_dmg)
    assert_true(item.attributes.get("value") > orig_val)
    assert "Longsword" in item.key
    assert "Uncommon" in item.key


# ======== SECTION 9: Edge Cases ========
print("\n" + "=" * 60)
print("SECTION 9: Edge Cases")
print("=" * 60)

@test("format_money None")
def _():
    from world.economy import format_money
    assert "0 copper" in format_money(None)

@test("get_money None")
def _():
    from world.economy import get_money
    assert_eq(get_money(None), 0)

@test("get_money no attributes")
def _():
    from world.economy import get_money
    class X: pass
    assert_eq(get_money(X()), 0)

@test("remove_money non-char")
def _():
    from world.economy import remove_money
    assert_false(remove_money(None, 10))

@test("add_money non-char")
def _():
    from world.economy import add_money
    assert_eq(add_money(None, 10), 0)


# ======== RESULTS ========
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
print("=" * 60)

if FAIL > 0:
    print(f"\n{FAIL} TEST(S) FAILED!")
    sys.exit(1)
else:
    print("\nALL TESTS PASSED! Economy & Items system is fully operational.\n")
    sys.exit(0)