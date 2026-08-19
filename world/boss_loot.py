"""
Boss-Only Rare Loot Table System for 'rop'

Provides:
  - Rarity tiers (Rare, Epic, Legendary)
  - BossLootTable: defines which items a boss can drop + drop rates
  - BossLootHandler: manages loot drops when a boss is killed
  - Boss-only flag: rare+ items can only drop from boss monsters

Usage:
  from world.boss_loot import BossLootTable, BossLootHandler, RARITY_RARE, \
      RARITY_EPIC, RARITY_LEGENDARY

  # Define a boss loot table
  loot_table = BossLootTable("Dragon Lord")
  loot_table.add_item("Dragon's Fang Dagger", RARITY_LEGENDARY, 5)
  loot_table.add_item("Dragonscale Shield", RARITY_EPIC, 12)
  loot_table.add_item("Drake Bone Amulet", RARITY_RARE, 15)

  # Handle boss death
  handler = BossLootHandler()
  dropped = handler.roll_boss_loot(loot_table)
  for item in dropped:
      item.move_to(killer, quiet=True)
"""

import random
from evennia import create_object
from evennia.objects.objects import DefaultObject

# ---------------------------------------------------------------------------
# Rarity Constants
# ---------------------------------------------------------------------------

RARITY_COMMON = "common"
RARITY_UNCOMMON = "uncommon"
RARITY_RARE = "rare"
RARITY_EPIC = "epic"
RARITY_LEGENDARY = "legendary"

# Items of rare+ rarity are boss-only
BOSS_ONLY_RARITIES = {RARITY_RARE, RARITY_EPIC, RARITY_LEGENDARY}

# Rarity display colors
RARITY_COLORS = {
    RARITY_COMMON: "|w",       # white
    RARITY_UNCOMMON: "|g",     # green
    RARITY_RARE: "|b",         # blue
    RARITY_EPIC: "|m",         # magenta/purple
    RARITY_LEGENDARY: "|Y",    # bright yellow/gold
}

# ---------------------------------------------------------------------------
# Loot Entry
# ---------------------------------------------------------------------------


class LootEntry:
    """
    A single entry in a boss loot table.

    Attributes:
        item_key: The key/name for the item to create on drop.
        rarity: One of the RARITY_* constants.
        drop_chance: Percent chance (1-100) this item drops on kill.
        item_data: Optional dict of extra attributes to set on the created item.
    """

    def __init__(self, item_key, rarity=RARITY_RARE, drop_chance=10,
                 item_data=None):
        self.item_key = item_key
        self.rarity = rarity
        self.drop_chance = min(100, max(1, drop_chance))
        self.item_data = item_data or {}

    def get_display_name(self):
        """Return a color-coded display name for this loot entry."""
        color = RARITY_COLORS.get(self.rarity, "|w")
        return f"{color}{self.item_key} [{self.rarity.upper()}]|n"


# ---------------------------------------------------------------------------
# Boss Loot Table
# ---------------------------------------------------------------------------


class BossLootTable:
    """
    Defines the loot table for a specific boss monster.

    Each boss can have multiple LootEntry items with different
    rarities and drop chances.  All items in this table are
    boss-only and cannot drop from normal mobs.
    """

    def __init__(self, boss_key):
        self.boss_key = boss_key
        self.entries = []  # list of LootEntry

    def add_item(self, item_key, rarity=RARITY_RARE, drop_chance=10,
                 item_data=None):
        """
        Add an item to this boss's loot table.

        Args:
            item_key: Display name / key for the dropped item.
            rarity: RARITY_RARE, RARITY_EPIC, or RARITY_LEGENDARY.
            drop_chance: Percent chance (1-100) per kill.
            item_data: Optional dict of attributes for the created object.
        """
        entry = LootEntry(item_key, rarity, drop_chance, item_data)
        self.entries.append(entry)
        return entry

    def __repr__(self):
        return (f"<BossLootTable {self.boss_key} "
                f"({len(self.entries)} items)>")


# ---------------------------------------------------------------------------
# Boss Loot Handler
# ---------------------------------------------------------------------------


class BossLootHandler:
    """
    Handles rolling boss loot tables and creating dropped items.

    Attach this to boss NPCs that should drop rare+ loot on death.
    """

    @staticmethod
    def roll_boss_loot(loot_table):
        """
        Roll against a boss loot table and return list of created items.

        Each entry in the loot table is rolled independently, so a boss
        can drop multiple rare items at once if lucky.

        Args:
            loot_table: A BossLootTable instance.

        Returns:
            List of created DefaultObject items that dropped.
        """
        dropped = []
        for entry in loot_table.entries:
            roll = random.randint(1, 100)
            if roll <= entry.drop_chance:
                item = BossLootHandler._create_loot_item(entry)
                if item:
                    dropped.append(item)
        return dropped

    @staticmethod
    def _create_loot_item(entry):
        """
        Create a physical item object from a LootEntry.

        The created object gets:
          - The item key as its name
          - rarity and boss_only flags
          - Any extra item_data attributes
        """
        attrs = [
            ("desc", (f"A {entry.rarity} item dropped by a powerful foe. "
                      f"Rarity: {entry.rarity.upper()}")),
            ("item_type", "equipment"),
            ("rarity", entry.rarity),
            ("boss_only_drop", True),
            ("value_gold", BossLootHandler._value_for_rarity(entry.rarity)),
        ]

        # Apply any extra attributes from item_data
        for key, value in entry.item_data.items():
            attrs.append((key, value))

        try:
            item = create_object(
                DefaultObject,
                key=entry.item_key,
                attributes=attrs,
            )
            return item
        except Exception:
            return None

    @staticmethod
    def _value_for_rarity(rarity):
        """Gold value based on rarity tier."""
        return {
            RARITY_RARE: 250,
            RARITY_EPIC: 750,
            RARITY_LEGENDARY: 2000,
        }.get(rarity, 100)

    @staticmethod
    def get_drop_display(dropped_items):
        """
        Build a color-coded display string for dropped items.

        Args:
            dropped_items: List of item objects that dropped.

        Returns:
            A formatted string for room announcements.
        """
        if not dropped_items:
            return ""

        parts = []
        for item in dropped_items:
            rarity = item.attributes.get("rarity", RARITY_COMMON)
            color = RARITY_COLORS.get(rarity, "|w")
            parts.append(
                f"{color}{item.key} [{rarity.upper()}]|n"
            )
        return ", ".join(parts)


# ---------------------------------------------------------------------------
# Boss Flag Helpers
# ---------------------------------------------------------------------------


def mark_as_boss(npc):
    """
    Mark an NPC as a boss monster.
    Boss monsters use boss loot tables and cannot drop from normal trash tables.
    """
    npc.attributes.add("is_boss", True)


def is_boss(npc):
    """Check if an NPC is flagged as a boss."""
    return npc.attributes.get("is_boss", False) is True


def mark_as_trash_mob(npc):
    """
    Explicitly mark an NPC as a normal/trash mob.
    Trash mobs cannot drop rare, epic, or legendary items.
    """
    npc.attributes.add("is_trash_mob", True)


def can_drop_rare(npc):
    """
    Check if an NPC is allowed to drop rare+ items.
    Only bosses can drop rare, epic, and legendary loot.
    """
    return is_boss(npc)


# ---------------------------------------------------------------------------
# Registry: maintains all boss loot tables
# ---------------------------------------------------------------------------


class BossLootRegistry:
    """
    Central registry mapping boss keys to their loot tables.

    When a boss dies, the combat handler can look up the boss's
    loot table here and roll for drops.
    """

    def __init__(self):
        self._tables = {}  # boss_key -> BossLootTable

    def register(self, loot_table):
        """Register a BossLootTable."""
        if not isinstance(loot_table, BossLootTable):
            raise TypeError("Must register a BossLootTable instance")
        self._tables[loot_table.boss_key.lower()] = loot_table

    def get(self, boss_key):
        """Retrieve the loot table for a boss by key, or None."""
        return self._tables.get(boss_key.lower())

    def all(self):
        """Return all registered loot tables."""
        return list(self._tables.values())

    def clear(self):
        """Remove all loot tables (useful for testing)."""
        self._tables.clear()

    def __len__(self):
        """Return number of registered boss loot tables."""
        return len(self._tables)


# Global boss loot registry
boss_loot_registry = BossLootRegistry()


# ---------------------------------------------------------------------------
# Default Boss Loot Tables (built-in bosses)
# ---------------------------------------------------------------------------


def register_default_boss_loot():
    """
    Register all 30 boss loot tables from BOSS_REGISTRY data.

    Each boss in boss_registry.py has a rare_drop item with drop_rate
    and announce fields.  We register a BossLootTable per boss, keyed
    by the boss display name (target.key at kill time) so the combat
    handler can look it up correctly.

    Also registers fallback legacy tables for backwards compatibility.
    Called at server startup.
    """
    boss_loot_registry.clear()

    try:
        from world.boss_registry import BOSS_REGISTRY
    except Exception:
        BOSS_REGISTRY = {}

    for boss_id, data in BOSS_REGISTRY.items():
        boss_name = data.get("name", boss_id)
        rare_drop = data.get("rare_drop", "")
        drop_rate = data.get("drop_rate", 5)
        drop_stats = data.get("drop_stats", "")
        boss_level = data.get("level", 1)

        if not rare_drop:
            continue

        # Determine rarity based on drop_rate (lower = rarer)
        if drop_rate <= 5:
            rarity = RARITY_LEGENDARY
        elif drop_rate <= 8:
            rarity = RARITY_EPIC
        else:
            rarity = RARITY_RARE

        table = BossLootTable(boss_name)
        table.add_item(rare_drop, rarity, drop_rate, {
            "slot": "main_hand",
            "damage": boss_level // 2 + 5,
            "required_level": max(1, boss_level - 5),
            "desc": drop_stats,
        })
        # Also store the announce text on the table for later use
        table.announce = data.get("announce", "")
        boss_loot_registry.register(table)

    # --- Legacy hardcoded fallbacks (backwards compat) ---
    # These are kept so existing tests and code that reference
    # "Dragon Lord", "Shadow Lord", "Lich King" still work.
    _register_legacy_tables()


def _register_legacy_tables():
    """Register legacy hardcoded boss tables for backwards compatibility."""
    # --- Dragon Lord ---
    dragon_lord = BossLootTable("Dragon Lord")
    dragon_lord.add_item("Dragon's Fang Dagger", RARITY_LEGENDARY, 5, {
        "slot": "main_hand", "damage": 45, "stat_str": 10,
        "stat_agi": 8, "required_level": 45,
    })
    dragon_lord.add_item("Dragonscale Breastplate", RARITY_LEGENDARY, 5, {
        "slot": "torso", "armor_class": 40, "stat_con": 12,
        "stat_str": 6, "required_level": 45,
    })
    dragon_lord.add_item("Wyrmfire Amulet", RARITY_EPIC, 10, {
        "slot": "neck", "armor_class": 8, "stat_int": 8,
        "required_level": 40,
    })
    dragon_lord.add_item("Dragonbone Ring", RARITY_EPIC, 10, {
        "slot": "finger1", "armor_class": 5, "stat_str": 6,
        "required_level": 38,
    })
    dragon_lord.add_item("Drake Hide Leggings", RARITY_RARE, 15, {
        "slot": "legs", "armor_class": 20, "stat_agi": 6,
        "required_level": 30,
    })
    dragon_lord.add_item("Lava-Core Warhelm", RARITY_RARE, 15, {
        "slot": "head", "armor_class": 18, "stat_str": 5,
        "stat_con": 5, "required_level": 32,
    })
    boss_loot_registry.register(dragon_lord)

    # --- Shadow Lord ---
    shadow_lord = BossLootTable("Shadow Lord")
    shadow_lord.add_item("Shadowstalker Cowl", RARITY_LEGENDARY, 5, {
        "slot": "head", "armor_class": 22, "stat_agi": 12,
        "stat_int": 6, "required_level": 42,
    })
    shadow_lord.add_item("Umbral Dagger", RARITY_EPIC, 10, {
        "slot": "main_hand", "damage": 38, "stat_agi": 10,
        "required_level": 38,
    })
    shadow_lord.add_item("Cloak of Shadows", RARITY_EPIC, 10, {
        "slot": "robe", "armor_class": 15, "stat_agi": 8,
        "required_level": 36,
    })
    shadow_lord.add_item("Night-Stalker Greaves", RARITY_RARE, 15, {
        "slot": "feet", "armor_class": 14, "stat_agi": 8,
        "required_level": 28,
    })
    shadow_lord.add_item("Void-Touched Wristguards", RARITY_RARE, 15, {
        "slot": "wrists", "armor_class": 10, "stat_int": 6,
        "required_level": 26,
    })
    boss_loot_registry.register(shadow_lord)

    # --- Lich King ---
    lich_king = BossLootTable("Lich King")
    lich_king.add_item("Soul Reaper Scythe", RARITY_LEGENDARY, 5, {
        "slot": "two_hand", "damage": 50, "stat_int": 14,
        "stat_str": 4, "required_level": 48,
    })
    lich_king.add_item("Crown of Undeath", RARITY_EPIC, 10, {
        "slot": "head", "armor_class": 20, "stat_int": 10,
        "required_level": 40,
    })
    lich_king.add_item("Bone-Carved Pendant", RARITY_RARE, 15, {
        "slot": "neck", "armor_class": 6, "stat_int": 6,
        "required_level": 30,
    })
    lich_king.add_item("Gravewalker Boots", RARITY_RARE, 15, {
        "slot": "feet", "armor_class": 12, "stat_int": 5,
        "required_level": 28,
    })
    boss_loot_registry.register(lich_king)
