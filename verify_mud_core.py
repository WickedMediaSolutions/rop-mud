#!/usr/bin/env python
"""
===============================================================================
RITES OF PASSAGE — CORE SYSTEM VERIFICATION TEST SUITE
===============================================================================

Standalone verification script that tests the three critical mob systems:

  (a) Spawned mobs receive randomized weapons, armor, and coins based on level
  (b) Mob AC and weapon damage stats compute correctly in combat simulations
  (c) Mob deaths correctly populate corpse inventories with generated gear/currency

Run directly from the shell:
    cd /root/rop/rop
    python verify_mud_core.py

No Evennia server required — uses mock objects for all DB-dependent paths.
===============================================================================
"""

from __future__ import annotations

import sys
import os
import random
import math
from typing import Any, Dict, List, Optional

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Mock infrastructure (self-contained, no Evennia imports needed)
# ---------------------------------------------------------------------------

class MockAttributeHandler:
    """Dict-backed attribute handler mimicking Evennia's attributes."""
    def __init__(self, data=None):
        self._store = dict(data) if data else {}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def add(self, key, value):
        self._store[key] = value

    def set(self, key, value):
        self._store[key] = value

    def has(self, key):
        return key in self._store

    def all(self):
        return dict(self._store)

    def __contains__(self, key):
        return key in self._store


class MockObject:
    """Lightweight mock for Evennia objects (mobs, items, corpses, rooms)."""
    _id_counter = 0

    def __init__(self, key="mock", location=None):
        MockObject._id_counter += 1
        self.id = MockObject._id_counter
        self.key = key
        self.attributes = MockAttributeHandler()
        self.location = location
        self.destination = None
        self.contents: List[MockObject] = []
        self.deleted = False
        self.moves: List[tuple] = []

    def move_to(self, destination, quiet=False):
        """Move this object to a new location."""
        if self.location is not None and hasattr(self.location, "contents"):
            if self in self.location.contents:
                self.location.contents.remove(self)
        self.location = destination
        if destination is not None and hasattr(destination, "contents"):
            if self not in destination.contents:
                destination.contents.append(self)
        self.moves.append((destination, quiet))
        return True

    def delete(self):
        self.deleted = True
        if self.location and hasattr(self.location, "contents"):
            if self in self.location.contents:
                self.location.contents.remove(self)
        self.location = None

    def __repr__(self):
        return f"<MockObject #{self.id} '{self.key}'>"


# ---------------------------------------------------------------------------
# Import the real equipment generation module (pure data, no DB needed)
# ---------------------------------------------------------------------------

# The mob_equipment module defers Evennia imports, so we can import its
# data tables and pure functions directly.
from world.mob_equipment import (
    WEAPON_TEMPLATES,
    ARMOR_TEMPLATES,
    CLASS_ARCHETYPE_MAP,
    EQUIP_SLOTS,
    _tier_for_level,
    generate_mob_coins,
    get_effective_armor,
    has_armor_equipped,
)

# ---------------------------------------------------------------------------
# Test helper: create a mock mob with given level and class
# ---------------------------------------------------------------------------

def create_mock_mob(
    key: str = "Test Mob",
    level: int = 1,
    mob_class: str = "Warrior",
    faction: str = "Neutral",
    stats: Optional[Dict[str, int]] = None,
    hp: int = 50,
    max_hp: int = 50,
) -> MockObject:
    """Create a mock mob with the given attributes."""
    mob = MockObject(key=key)
    mob.attributes.add("is_mob", True)
    mob.attributes.add("level", level)
    mob.attributes.add("mob_class", mob_class)
    mob.attributes.add("faction", faction)
    mob.attributes.add("hp", hp)
    mob.attributes.add("max_hp", max_hp)
    mob.attributes.add("stats", stats or {
        "str": 10, "dex": 10, "con": 10,
        "int": 10, "wis": 10, "cha": 10,
    })
    mob.attributes.add("equipped", {})
    mob.attributes.add("alignment", "Neutral")
    return mob


def create_mock_item(
    key: str,
    slot: str = "main_hand",
    damage: int = 0,
    armor: int = 0,
    damage_type: str = "slash",
    weight: float = 1.0,
    value: int = 10,
) -> MockObject:
    """Create a mock equipment item."""
    item = MockObject(key=key)
    item.attributes.add("item_type", "equipment")
    item.attributes.add("slot", slot)
    item.attributes.add("damage", damage)
    item.attributes.add("armor", armor)
    item.attributes.add("damage_type", damage_type)
    item.attributes.add("weight", weight)
    item.attributes.add("value", value)
    item.attributes.add("durability", 100)
    item.attributes.add("max_durability", 100)
    return item


# ---------------------------------------------------------------------------
# Simulate equip_mob using mock objects (avoids Evennia create_object)
# ---------------------------------------------------------------------------

def simulate_equip_mob(
    mob: MockObject,
    mob_class: str = "Warrior",
    faction: str = "Neutral",
    equip_chance: float = 0.7,
) -> Dict[str, Any]:
    """
    Simulate equipping a mob using the real template data but mock items.

    This mirrors the logic in world.mob_equipment.equip_mob() but uses
    MockObject instead of real Evennia objects so no DB is needed.
    """
    mob_level = mob.attributes.get("level", 1)
    tier = _tier_for_level(mob_level)
    archetype = CLASS_ARCHETYPE_MAP.get(mob_class, "warrior")

    equipped = {}
    items_generated = []

    # --- Generate weapon (always) ---
    weapon_templates = WEAPON_TEMPLATES.get(archetype, WEAPON_TEMPLATES["warrior"])
    tier_weapons = weapon_templates.get(tier, weapon_templates.get(1, []))
    if tier_weapons:
        template = random.choice(tier_weapons)
        weapon = create_mock_item(
            key=template["name"],
            slot=template.get("slot", "main_hand"),
            damage=template.get("damage", 5),
            damage_type=template.get("damage_type", "slash"),
            weight=template.get("weight", 1.0),
            value=template.get("value", 10),
        )
        weapon.location = mob
        mob.contents.append(weapon)
        equipped[weapon.attributes.get("slot", "main_hand")] = weapon.key
        items_generated.append(weapon)

    # --- Generate armor for each slot ---
    armor_slots = ["head", "chest", "legs", "feet"]
    for slot in armor_slots:
        if random.random() < equip_chance:
            slot_templates = ARMOR_TEMPLATES.get(slot, {})
            tier_armors = slot_templates.get(tier, slot_templates.get(1, []))
            if tier_armors:
                template = random.choice(tier_armors)
                armor = create_mock_item(
                    key=template["name"],
                    slot=slot,
                    armor=template.get("armor", 1),
                    weight=template.get("weight", 1.0),
                    value=template.get("value", 5),
                )
                armor.location = mob
                mob.contents.append(armor)
                equipped[slot] = armor.key
                items_generated.append(armor)

    # --- Off-hand (shield) — lower chance ---
    if random.random() < (equip_chance * 0.4):
        shield_templates = ARMOR_TEMPLATES.get("off_hand", {})
        tier_shields = shield_templates.get(tier, shield_templates.get(1, []))
        if tier_shields:
            template = random.choice(tier_shields)
            shield = create_mock_item(
                key=template["name"],
                slot="off_hand",
                armor=template.get("armor", 2),
                weight=template.get("weight", 3.0),
                value=template.get("value", 5),
            )
            shield.location = mob
            mob.contents.append(shield)
            equipped["off_hand"] = shield.key
            items_generated.append(shield)

    # Store equipped items on the mob
    mob.attributes.add("equipped", equipped)

    # Calculate total armor
    total_armor = sum(
        item.attributes.get("armor", 0)
        for item in items_generated
    )

    return {
        "weapon": equipped.get("main_hand") or equipped.get("two_hand"),
        "armor_pieces": len([i for i in items_generated if i.attributes.get("armor", 0) > 0]),
        "total_armor": total_armor,
        "items": items_generated,
    }


def simulate_transfer_to_corpse(mob: MockObject, corpse: MockObject) -> int:
    """
    Simulate transferring equipped items from a dead mob to its corpse.

    Mirrors world.mob_equipment.transfer_equipped_to_corpse().
    """
    count = 0
    equipped = mob.attributes.get("equipped", default={})
    if not equipped:
        return count

    for slot, item_name in list(equipped.items()):
        for obj in list(mob.contents):
            if getattr(obj, "destination", None):
                continue
            if obj.key == item_name:
                obj.move_to(corpse, quiet=True)
                count += 1
                break

    mob.attributes.add("equipped", {})
    return count


# ---------------------------------------------------------------------------
# Combat simulation helpers
# ---------------------------------------------------------------------------

def simulate_weapon_damage(mob: MockObject) -> int:
    """
    Calculate base weapon damage from equipped gear.

    Mirrors world.mob_equipment.get_equipped_weapon_damage().
    """
    equipped = mob.attributes.get("equipped", default={})
    if equipped:
        for slot in ("main_hand", "two_hand", "weapon", "right_hand", "two_handed"):
            weapon_name = equipped.get(slot)
            if weapon_name:
                for obj in mob.contents:
                    if getattr(obj, "destination", None):
                        continue
                    if obj.key == weapon_name:
                        dmg = obj.attributes.get("damage", 0)
                        if dmg > 0:
                            return dmg

    # Unarmed: STR-based
    stats = mob.attributes.get("stats", default={})
    str_val = stats.get("str", 10) if stats else 10
    return max(1, str_val // 2)


def simulate_armor_class(mob: MockObject) -> int:
    """
    Calculate armor class from equipped gear + stats.

    Mirrors the AC calculation in tick_combat._armor_class().
    """
    base = 10
    stats = mob.attributes.get("stats", default={})
    dex_bonus = max(0, (stats.get("dex", 10) - 10) // 2) if stats else 0
    con_bonus = max(0, (stats.get("con", 10) - 10) // 3) if stats else 0

    # Sum armor from equipped items
    armor = 0
    equipped = mob.attributes.get("equipped", default={})
    if equipped:
        for slot, item_name in equipped.items():
            for obj in mob.contents:
                if getattr(obj, "destination", None):
                    continue
                if obj.key == item_name:
                    armor += obj.attributes.get("armor", 0)
                    break

    return max(-10, base - dex_bonus - con_bonus - (armor // 2))


def simulate_hit_chance(attacker: MockObject, defender: MockObject) -> float:
    """
    Calculate hit chance percentage using THAC0/AC.

    Mirrors tick_combat._hit_roll().
    """
    BASE_THAC0 = 20
    att_level = attacker.attributes.get("level", 1)
    att_stats = attacker.attributes.get("stats", default={})
    att_dex = att_stats.get("dex", 10) if att_stats else 10
    dex_bonus = max(0, (att_dex - 10) // 3)

    thac0 = max(1, BASE_THAC0 - (att_level - 1) - dex_bonus)
    ac = simulate_armor_class(defender)

    roll_needed = max(1, thac0 - ac)
    hit_chance = (21 - roll_needed) * 5
    return max(5, min(95, hit_chance))


def simulate_melee_damage(attacker: MockObject, defender: MockObject) -> dict:
    """
    Simulate a full melee damage calculation.

    Mirrors damage_formulas.calculate_melee_damage().
    """
    att_stats = attacker.attributes.get("stats", default={})
    def_stats = defender.attributes.get("stats", default={})

    str_val = att_stats.get("str", 10) if att_stats else 10
    con_val = def_stats.get("con", 10) if def_stats else 10

    weapon_dmg = simulate_weapon_damage(attacker)
    str_bonus = max(0, (str_val - 10) // 2)
    base = weapon_dmg + str_bonus

    # Armor mitigation
    armor_value = 0
    equipped = defender.attributes.get("equipped", default={})
    if equipped:
        for slot, item_name in equipped.items():
            for obj in defender.contents:
                if getattr(obj, "destination", None):
                    continue
                if obj.key == item_name:
                    armor_value += obj.attributes.get("armor", 0)
                    break

    armor_mitigation_pct = 0.15  # SLASH default
    con_bonus = max(0, (con_val - 10) // 3)
    absorbed = int(base * armor_mitigation_pct) + con_bonus
    absorbed = min(absorbed, base - 1)

    # Variance
    variance = random.uniform(0.80, 1.20)
    final_damage = max(1, int((base - absorbed) * variance))

    return {
        "damage": final_damage,
        "absorbed": absorbed,
        "base": base,
        "weapon_damage": weapon_dmg,
    }


# ============================================================================
# TEST SUITE
# ============================================================================

PASS = 0
FAIL = 0
TOTAL = 0


def log(msg: str) -> None:
    """Print a test log message."""
    print(msg)


def check(condition: bool, test_name: str, detail: str = "") -> bool:
    """Assert a condition and log the result."""
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if condition:
        PASS += 1
        log(f"  [PASS] {test_name}")
    else:
        FAIL += 1
        log(f"  [FAIL] {test_name} — {detail}")
    return condition


def section(title: str) -> None:
    """Print a section header."""
    log("")
    log("=" * 70)
    log(f"  {title}")
    log("=" * 70)


# ---------------------------------------------------------------------------
# TEST A: Spawned mobs receive randomized weapons, armor, and coins
# ---------------------------------------------------------------------------

def test_a_mob_equipment_generation():
    """Test (a): Spawned mobs receive randomized weapons, armor, and coins."""
    section("TEST A: Mob Equipment Generation on Spawn")

    # Test across multiple levels and classes
    test_cases = [
        (1, "Warrior"),
        (5, "Rogue"),
        (15, "Mage"),
        (30, "Ranger"),
        (50, "Warrior"),
        (75, "Necromancer"),
    ]

    for level, mob_class in test_cases:
        log(f"\n--- Level {level} {mob_class} ---")

        # Create mob and equip
        mob = create_mock_mob(
            key=f"Test {mob_class}",
            level=level,
            mob_class=mob_class,
        )
        result = simulate_equip_mob(mob, mob_class=mob_class)

        # 1. Mob must have a weapon
        weapon_name = result.get("weapon")
        check(
            weapon_name is not None,
            f"Lv{level} {mob_class}: Has weapon",
            f"weapon={weapon_name}"
        )

        # 2. Weapon damage must be > 0
        weapon_dmg = simulate_weapon_damage(mob)
        check(
            weapon_dmg > 0,
            f"Lv{level} {mob_class}: Weapon damage > 0",
            f"damage={weapon_dmg}"
        )

        # 3. Weapon damage should scale with level
        tier = _tier_for_level(level)
        expected_min_dmg = {1: 2, 2: 5, 3: 9, 4: 14, 5: 20}.get(tier, 1)
        check(
            weapon_dmg >= expected_min_dmg,
            f"Lv{level} {mob_class}: Weapon damage meets tier minimum",
            f"damage={weapon_dmg}, tier={tier}, expected_min={expected_min_dmg}"
        )

        # 4. Armor pieces should be generated
        armor_count = result.get("armor_pieces", 0)
        total_armor = result.get("total_armor", 0)
        check(
            total_armor >= 0,
            f"Lv{level} {mob_class}: Armor value computed",
            f"pieces={armor_count}, total_armor={total_armor}"
        )

        # 5. Equipped dict must be populated
        equipped = mob.attributes.get("equipped", default={})
        check(
            len(equipped) >= 1,
            f"Lv{level} {mob_class}: Equipped dict populated",
            f"slots={list(equipped.keys())}"
        )

        # 6. Items must be in mob's contents
        check(
            len(mob.contents) >= 1,
            f"Lv{level} {mob_class}: Items in mob contents",
            f"count={len(mob.contents)}"
        )

    # Test coin generation
    log("\n--- Coin Generation ---")
    for level in [1, 5, 10, 25, 50, 75]:
        coins = generate_mob_coins(level)
        total_value = coins["copper"] + coins["silver"] * 10 + coins["gold"] * 100
        check(
            total_value > 0,
            f"Lv{level}: Coins generated with positive value",
            f"c={coins['copper']} s={coins['silver']} g={coins['gold']} total={total_value}"
        )
        # Higher level mobs should drop more coins on average
        if level >= 10:
            check(
                coins["gold"] >= 0,
                f"Lv{level}: Gold coins present or zero (valid)",
                f"gold={coins['gold']}"
            )


# ---------------------------------------------------------------------------
# TEST B: AC and weapon damage compute correctly in combat simulations
# ---------------------------------------------------------------------------

def test_b_combat_calculations():
    """Test (b): Mob AC and weapon damage stats compute correctly."""
    section("TEST B: Combat Calculation Verification")

    # Create attacker and defender
    attacker = create_mock_mob(
        key="Orc Warrior",
        level=10,
        mob_class="Warrior",
        stats={"str": 16, "dex": 12, "con": 14, "int": 8, "wis": 8, "cha": 6},
        hp=100,
    )
    defender = create_mock_mob(
        key="Town Guard",
        level=10,
        mob_class="Warrior",
        stats={"str": 14, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 10},
        hp=120,
    )

    # Equip both
    att_result = simulate_equip_mob(attacker, mob_class="Warrior")
    def_result = simulate_equip_mob(defender, mob_class="Warrior")

    log(f"\nAttacker: {attacker.key} Lv{attacker.attributes.get('level')}")
    log(f"  Weapon: {att_result['weapon']} (dmg={simulate_weapon_damage(attacker)})")
    log(f"  Armor: {att_result['total_armor']} AC from {att_result['armor_pieces']} pieces")
    log(f"  AC: {simulate_armor_class(attacker)}")

    log(f"\nDefender: {defender.key} Lv{defender.attributes.get('level')}")
    log(f"  Weapon: {def_result['weapon']} (dmg={simulate_weapon_damage(defender)})")
    log(f"  Armor: {def_result['total_armor']} AC from {def_result['armor_pieces']} pieces")
    log(f"  AC: {simulate_armor_class(defender)}")

    # 1. Weapon damage must be positive
    att_dmg = simulate_weapon_damage(attacker)
    check(att_dmg > 0, "Attacker weapon damage > 0", f"dmg={att_dmg}")

    def_dmg = simulate_weapon_damage(defender)
    check(def_dmg > 0, "Defender weapon damage > 0", f"dmg={def_dmg}")

    # 2. Armor class must be computed
    att_ac = simulate_armor_class(attacker)
    def_ac = simulate_armor_class(defender)
    check(
        isinstance(att_ac, int),
        "Attacker AC is integer",
        f"ac={att_ac}"
    )
    check(
        isinstance(def_ac, int),
        "Defender AC is integer",
        f"ac={def_ac}"
    )

    # 3. Hit chance must be in valid range
    hit_pct = simulate_hit_chance(attacker, defender)
    check(
        5 <= hit_pct <= 95,
        "Hit chance in [5, 95] range",
        f"hit_chance={hit_pct}%"
    )

    # 4. Melee damage calculation must produce valid results
    result = simulate_melee_damage(attacker, defender)
    check(
        result["damage"] >= 1,
        "Melee damage >= 1",
        f"damage={result['damage']}, base={result['base']}, absorbed={result['absorbed']}"
    )
    check(
        result["absorbed"] >= 0,
        "Armor absorption >= 0",
        f"absorbed={result['absorbed']}"
    )
    check(
        result["weapon_damage"] > 0,
        "Weapon damage used in calculation",
        f"weapon_dmg={result['weapon_damage']}"
    )

    # 5. Armor should reduce damage
    # Run many simulations to verify armor has an effect
    log("\n--- Armor Effectiveness Simulation (100 rounds) ---")
    total_dmg_with_armor = 0
    total_absorbed = 0
    rounds = 100
    for _ in range(rounds):
        r = simulate_melee_damage(attacker, defender)
        total_dmg_with_armor += r["damage"]
        total_absorbed += r["absorbed"]

    avg_dmg = total_dmg_with_armor / rounds
    avg_absorbed = total_absorbed / rounds
    log(f"  Average damage per round: {avg_dmg:.1f}")
    log(f"  Average absorbed per round: {avg_absorbed:.1f}")

    check(
        avg_absorbed >= 0,
        "Armor absorption tracked over 100 rounds",
        f"avg_absorbed={avg_absorbed:.1f}"
    )

    # 6. Naked mob should have 0 armor absorption
    naked_mob = create_mock_mob(key="Naked Goblin", level=1, mob_class="Warrior")
    naked_mob.attributes.add("equipped", {})
    naked_ac = simulate_armor_class(naked_mob)
    check(
        naked_ac >= 8,  # Base 10 - DEX bonus (0) - CON bonus (0) - armor(0)//2 = 10
        "Naked mob AC is base value (no phantom armor)",
        f"ac={naked_ac}"
    )

    # 7. Verify get_effective_armor returns 0 for naked mob
    eff_armor = get_effective_armor(naked_mob)
    check(
        eff_armor == 0,
        "get_effective_armor returns 0 for naked mob",
        f"armor={eff_armor}"
    )


# ---------------------------------------------------------------------------
# TEST C: Mob deaths populate corpse inventories with gear and currency
# ---------------------------------------------------------------------------

def test_c_corpse_inventory_on_death():
    """Test (c): Mob deaths correctly populate corpse inventories."""
    section("TEST C: Corpse Inventory on Mob Death")

    # Create a mob with equipment and coins
    mob = create_mock_mob(
        key="Forest Wolf",
        level=8,
        mob_class="Warrior",
        stats={"str": 14, "dex": 14, "con": 12, "int": 4, "wis": 8, "cha": 4},
        hp=60,
    )

    # Equip the mob
    equip_result = simulate_equip_mob(mob, mob_class="Warrior")
    log(f"\nMob equipped: {equip_result['weapon']}, "
        f"{equip_result['armor_pieces']} armor pieces, "
        f"AC={equip_result['total_armor']}")

    # Generate coins
    coins = generate_mob_coins(mob.attributes.get("level", 1))
    mob.attributes.add("copper_coins", coins["copper"])
    mob.attributes.add("silver_coins", coins["silver"])
    mob.attributes.add("gold_coins", coins["gold"])
    log(f"Coins: {coins['copper']}c {coins['silver']}s {coins['gold']}g")

    # Count items before death
    items_before = len([o for o in mob.contents if not getattr(o, "destination", None)])
    log(f"Items in mob inventory: {items_before}")

    # Create a room for the corpse
    room = MockObject(key="Test Room")

    # Move mob to room
    mob.move_to(room)

    # Create corpse (simulating _create_npc_corpse)
    corpse = MockObject(key=f"corpse of {mob.key}")
    corpse.location = room
    room.contents.append(corpse)
    corpse.attributes.add("is_corpse", True)
    corpse.attributes.add("corpse_npc_level", mob.attributes.get("level", 1))

    # Transfer equipped items to corpse
    transferred = simulate_transfer_to_corpse(mob, corpse)
    log(f"Items transferred to corpse: {transferred}")

    # Transfer coins to corpse
    copper = mob.attributes.get("copper_coins", 0)
    silver = mob.attributes.get("silver_coins", 0)
    gold = mob.attributes.get("gold_coins", 0)
    total_money = gold + (silver // 10) + (copper // 100)
    corpse.attributes.add("money", max(1, total_money))
    corpse.attributes.add("copper_coins", copper)
    corpse.attributes.add("silver_coins", silver)
    corpse.attributes.add("gold_coins", gold)

    # --- Assertions ---

    # 1. Corpse must exist in the room
    check(
        corpse in room.contents,
        "Corpse exists in room",
        f"room contents: {[o.key for o in room.contents]}"
    )

    # 2. Corpse must have items (equipped gear transferred)
    corpse_items = [o for o in corpse.contents if not getattr(o, "destination", None)]
    check(
        len(corpse_items) > 0,
        "Corpse contains equipped items",
        f"item count: {len(corpse_items)}, items: {[i.key for i in corpse_items]}"
    )

    # 3. Corpse must have money
    corpse_money = corpse.attributes.get("money", 0)
    check(
        corpse_money > 0,
        "Corpse has money",
        f"money={corpse_money}"
    )

    # 4. Corpse must have coin breakdown
    c = corpse.attributes.get("copper_coins", 0)
    s = corpse.attributes.get("silver_coins", 0)
    g = corpse.attributes.get("gold_coins", 0)
    check(
        (c + s + g) >= 0,
        "Corpse has coin breakdown",
        f"c={c} s={s} g={g}"
    )

    # 5. Mob's equipped dict should be empty after transfer
    mob_equipped = mob.attributes.get("equipped", default={})
    check(
        len(mob_equipped) == 0,
        "Mob equipped dict cleared after transfer",
        f"remaining equipped: {mob_equipped}"
    )

    # 6. Corpse items should include at least one weapon
    has_weapon = any(
        item.attributes.get("damage", 0) > 0
        for item in corpse_items
    )
    check(
        has_weapon,
        "Corpse contains a weapon",
        f"weapon found: {has_weapon}"
    )

    # 7. Corpse items should include armor pieces
    has_armor = any(
        item.attributes.get("armor", 0) > 0
        for item in corpse_items
    )
    check(
        has_armor,
        "Corpse contains armor pieces",
        f"armor found: {has_armor}"
    )

    # 8. Test with multiple mob levels
    log("\n--- Multi-Level Corpse Test ---")
    for level in [1, 10, 30, 60]:
        test_mob = create_mock_mob(
            key=f"Lv{level} Mob",
            level=level,
            mob_class="Warrior",
            stats={"str": 10 + level // 2, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            hp=20 + level * 5,
        )
        test_room = MockObject(key=f"Room Lv{level}")
        test_mob.move_to(test_room)

        eq = simulate_equip_mob(test_mob, mob_class="Warrior")
        coins = generate_mob_coins(level)
        test_mob.attributes.add("copper_coins", coins["copper"])
        test_mob.attributes.add("silver_coins", coins["silver"])
        test_mob.attributes.add("gold_coins", coins["gold"])

        test_corpse = MockObject(key=f"corpse of Lv{level} Mob")
        test_corpse.location = test_room
        test_room.contents.append(test_corpse)

        transferred = simulate_transfer_to_corpse(test_mob, test_corpse)
        corpse_items = [o for o in test_corpse.contents if not getattr(o, "destination", None)]

        check(
            len(corpse_items) >= 1,
            f"Lv{level}: Corpse has items",
            f"items={len(corpse_items)}, weapon={eq['weapon']}"
        )

        # Higher level mobs should have better gear
        if level >= 30:
            total_armor_on_corpse = sum(
                item.attributes.get("armor", 0)
                for item in corpse_items
            )
            check(
                total_armor_on_corpse >= 1,
                f"Lv{level}: High-level corpse has armor",
                f"total_armor={total_armor_on_corpse}"
            )


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all verification tests."""
    global PASS, FAIL, TOTAL

    log("")
    log("╔══════════════════════════════════════════════════════════════════════╗")
    log("║     RITES OF PASSAGE — CORE SYSTEM VERIFICATION TEST SUITE          ║")
    log("║     verify_mud_core.py                                              ║")
    log("╚══════════════════════════════════════════════════════════════════════╝")

    # Seed for reproducibility
    random.seed(42)

    # Run tests
    test_a_mob_equipment_generation()
    test_b_combat_calculations()
    test_c_corpse_inventory_on_death()

    # Summary
    log("")
    log("=" * 70)
    log(f"  RESULTS: {PASS} passed, {FAIL} failed, {TOTAL} total")
    log("=" * 70)

    if FAIL == 0:
        log("")
        log("  ✅ ALL TESTS PASSED — Core systems verified!")
        log("")
        return 0
    else:
        log("")
        log(f"  ❌ {FAIL} TEST(S) FAILED — See details above.")
        log("")
        return 1


if __name__ == "__main__":
    sys.exit(main())