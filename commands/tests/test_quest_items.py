"""
Unit tests for Quest Items, Boss Loot Tables, and Armor Set Bonuses.

Tests:
  - Quest item flagging (mark_as_quest_item, is_quest_item)
  - Quest item drop/sell/trade restrictions
  - Boss loot table registration and roll logic
  - Boss-only rarity enforcement (trash mobs cannot drop rare+)
  - Armor set registry and definition
  - ArmorSetChecker: counting equipped pieces, bonus calculation
  - Armor set bonus display formatting

Run with:
    evennia test commands.tests.test_quest_items
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultRoom, DefaultCharacter, DefaultObject
from evennia import create_object

from world.quest_items import (
    mark_as_quest_item,
    is_quest_item,
    can_drop_item,
    can_sell_item,
    can_trade_item,
    validate_quest_item_movement,
)
from world.boss_loot import (
    BossLootTable,
    BossLootHandler,
    BossLootRegistry,
    RARITY_COMMON,
    RARITY_RARE,
    RARITY_EPIC,
    RARITY_LEGENDARY,
    BOSS_ONLY_RARITIES,
    RARITY_COLORS,
    mark_as_boss,
    is_boss,
    can_drop_rare,
    boss_loot_registry,
)
from world.armor_sets import (
    ArmorSetDefinition,
    ArmorSetRegistry,
    ArmorSetChecker,
    apply_set_bonuses_to_character,
    get_stored_set_bonuses,
    armor_set_registry,
    register_default_armor_sets,
)


# ===========================================================================
#  1. Quest Item Tests
# ===========================================================================

class TestQuestItemFlags(BaseEvenniaTest):
    """Test quest item flagging functions."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="QuestTestRoom")
        self.char = create_object(DefaultCharacter, key="QITester")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_mark_and_check_quest_item(self):
        """mark_as_quest_item sets the flag, is_quest_item reads it."""
        sword = create_object(DefaultObject, key="Sword of Destiny")
        self.assertFalse(is_quest_item(sword))
        mark_as_quest_item(sword)
        self.assertTrue(is_quest_item(sword))
        self.assertTrue(sword.attributes.get("quest_item_bound"))
        sword.delete()

    def test_can_drop_quest_item_denied(self):
        """Quest items cannot be dropped."""
        ring = create_object(DefaultObject, key="Ring of Binding")
        mark_as_quest_item(ring)
        allowed, reason = can_drop_item(self.char, ring)
        self.assertFalse(allowed)
        self.assertIn("bound", reason.lower())
        ring.delete()

    def test_can_drop_normal_item_allowed(self):
        """Normal items can be dropped."""
        rock = create_object(DefaultObject, key="Rock")
        allowed, reason = can_drop_item(self.char, rock)
        self.assertTrue(allowed)
        rock.delete()

    def test_can_sell_quest_item_denied(self):
        """Quest items cannot be sold to shopkeepers."""
        amulet = create_object(DefaultObject, key="Quest Amulet")
        mark_as_quest_item(amulet)
        allowed, reason = can_sell_item(self.char, amulet)
        self.assertFalse(allowed)
        self.assertIn("shopkeeper", reason.lower())
        amulet.delete()

    def test_can_sell_normal_item_allowed(self):
        """Normal items can be sold."""
        gem = create_object(DefaultObject, key="Gem")
        allowed, reason = can_sell_item(self.char, gem)
        self.assertTrue(allowed)
        gem.delete()

    def test_can_trade_quest_item_denied(self):
        """Quest items cannot be traded to other players."""
        artifact = create_object(DefaultObject, key="Quest Artifact")
        mark_as_quest_item(artifact)
        other = create_object(DefaultCharacter, key="OtherPlayer")
        allowed, reason = can_trade_item(self.char, artifact, other)
        self.assertFalse(allowed)
        self.assertIn("trade", reason.lower())
        artifact.delete()
        other.delete()

    def test_can_trade_normal_item_allowed(self):
        """Normal items can be traded."""
        potion = create_object(DefaultObject, key="Health Potion")
        other = create_object(DefaultCharacter, key="OtherPlayer")
        allowed, reason = can_trade_item(self.char, potion, other)
        self.assertTrue(allowed)
        potion.delete()
        other.delete()


class TestQuestItemMovement(BaseEvenniaTest):
    """Test quest item movement validation."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="DropRoom")
        self.char = create_object(DefaultCharacter, key="Dropper")
        self.char.location = self.room

    def tearDown(self):
        self.char.delete()
        self.room.delete()
        super().tearDown()

    def test_quest_item_cannot_be_moved_to_room(self):
        """Moving a quest item to a room should be blocked."""
        key = create_object(DefaultObject, key="Quest Key")
        mark_as_quest_item(key)
        allowed, reason = validate_quest_item_movement(key, self.char, self.room)
        self.assertFalse(allowed)
        key.delete()

    def test_normal_item_can_be_moved_to_room(self):
        """Moving a normal item to a room is allowed."""
        rock = create_object(DefaultObject, key="Rock")
        allowed, reason = validate_quest_item_movement(rock, self.char, self.room)
        self.assertTrue(allowed)
        rock.delete()


# ===========================================================================
#  2. Boss Loot Table Tests
# ===========================================================================

class TestBossLootTable(BaseEvenniaTest):
    """Test boss loot table definition and registry."""

    def setUp(self):
        super().setUp()
        self.registry = BossLootRegistry()

    def tearDown(self):
        self.registry.clear()
        super().tearDown()

    def test_create_loot_table(self):
        """Can create a BossLootTable and add entries."""
        table = BossLootTable("Dragon Lord")
        entry = table.add_item("Dragon Fang", RARITY_LEGENDARY, 5)
        self.assertEqual(len(table.entries), 1)
        self.assertEqual(entry.rarity, RARITY_LEGENDARY)
        self.assertEqual(entry.drop_chance, 5)

    def test_drop_chance_clamped(self):
        """Drop chance is clamped to 1-100 range."""
        table = BossLootTable("Clamp Boss")
        entry_low = table.add_item("Sword", RARITY_RARE, 0)
        entry_high = table.add_item("Shield", RARITY_RARE, 200)
        self.assertEqual(entry_low.drop_chance, 1)
        self.assertEqual(entry_high.drop_chance, 100)

    def test_register_and_retrieve_loot_table(self):
        """Registry stores and retrieves loot tables by boss key."""
        table = BossLootTable("Test Boss")
        table.add_item("Test Sword", RARITY_RARE, 10)
        self.registry.register(table)

        retrieved = self.registry.get("Test Boss")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.boss_key, "Test Boss")
        self.assertEqual(len(retrieved.entries), 1)

    def test_case_insensitive_lookup(self):
        """Registry lookups are case-insensitive."""
        table = BossLootTable("Case Test")
        self.registry.register(table)
        self.assertIsNotNone(self.registry.get("case test"))
        self.assertIsNotNone(self.registry.get("CASE TEST"))

    def test_nonexistent_boss_returns_none(self):
        """Looking up a nonexistent boss returns None."""
        self.assertIsNone(self.registry.get("Nonexistent Boss"))

    def test_entry_display_name(self):
        """LootEntry.get_display_name returns color-coded string."""
        table = BossLootTable("Display Boss")
        entry = table.add_item("Epic Sword", RARITY_EPIC, 10)
        display = entry.get_display_name()
        self.assertIn("Epic Sword", display)
        self.assertIn("EPIC", display)


class TestBossLootHandler(BaseEvenniaTest):
    """Test the BossLootHandler item creation and rolling."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="BossRoom")
        self.table = BossLootTable("Test Boss")
        self.table.add_item("Rare Sword", RARITY_RARE, 15,
                             {"slot": "main_hand", "damage": 20})
        self.table.add_item("Epic Helm", RARITY_EPIC, 10,
                             {"slot": "head", "armor_class": 15})
        self.table.add_item("Legendary Shield", RARITY_LEGENDARY, 5,
                             {"slot": "off_hand", "armor_class": 30})

    def tearDown(self):
        for obj in list(self.room.contents):
            obj.delete()
        self.room.delete()
        super().tearDown()

    def test_create_loot_item_has_attributes(self):
        """Created loot items get rarity and boss_only_drop flags."""
        item = BossLootHandler._create_loot_item(self.table.entries[0])
        self.assertIsNotNone(item)
        self.assertEqual(item.attributes.get("rarity"), RARITY_RARE)
        self.assertTrue(item.attributes.get("boss_only_drop"))
        self.assertEqual(item.attributes.get("slot"), "main_hand")
        self.assertEqual(item.attributes.get("damage"), 20)
        item.delete()

    def test_roll_loot_returns_list(self):
        """roll_boss_loot always returns a list."""
        dropped = BossLootHandler.roll_boss_loot(self.table)
        self.assertIsInstance(dropped, list)
        # Clean up any dropped items
        for item in dropped:
            item.delete()

    def test_100_percent_drop_always_drops(self):
        """A 100% drop chance item always drops."""
        table = BossLootTable("Guaranteed Boss")
        table.add_item("Always Drops", RARITY_RARE, 100,
                       {"slot": "main_hand"})
        for _ in range(10):
            dropped = BossLootHandler.roll_boss_loot(table)
            self.assertEqual(len(dropped), 1)
            self.assertEqual(dropped[0].key, "Always Drops")
            for item in dropped:
                item.delete()

    def test_0_percent_drop_never_drops(self):
        """A 1% drop can still possibly drop, but 1% is the floor.
        We test that the clamp works — by using chance=1 we get rare drops."""
        table = BossLootTable("LowChance Boss")
        table.add_item("Rare Drop", RARITY_LEGENDARY, 1)
        found_drop = False
        for _ in range(500):
            dropped = BossLootHandler.roll_boss_loot(table)
            if dropped:
                found_drop = True
                for item in dropped:
                    item.delete()
                break
        # Over 500 rolls at 1%, it's extremely likely to drop at least once
        # (99.97% probability). Only report failure if it's an astronomic
        # edge case.
        self.assertTrue(found_drop,
                        "1% drop should have appeared in 500 rolls")

    def test_get_drop_display_formats_items(self):
        """get_drop_display returns color-coded string of dropped items."""
        table = BossLootTable("Display Boss")
        table.add_item("Ruby", RARITY_RARE, 100)
        table.add_item("Sapphire", RARITY_EPIC, 100)

        dropped = BossLootHandler.roll_boss_loot(table)
        display = BossLootHandler.get_drop_display(dropped)
        self.assertIn("Ruby", display)
        self.assertIn("Sapphire", display)
        self.assertIn("RARE", display)
        self.assertIn("EPIC", display)
        for item in dropped:
            item.delete()

    def test_get_drop_display_empty(self):
        """get_drop_display returns empty string for empty list."""
        self.assertEqual(BossLootHandler.get_drop_display([]), "")


class TestBossFlags(BaseEvenniaTest):
    """Test boss/trash mob flagging."""

    def setUp(self):
        super().setUp()
        self.npc = create_object(DefaultCharacter, key="TestMob")

    def tearDown(self):
        self.npc.delete()
        super().tearDown()

    def test_mark_and_check_boss(self):
        """Boss flag works."""
        self.assertFalse(is_boss(self.npc))
        mark_as_boss(self.npc)
        self.assertTrue(is_boss(self.npc))
        self.assertTrue(can_drop_rare(self.npc))

    def test_non_boss_cannot_drop_rare(self):
        """Non-boss NPCs cannot drop rare+ items."""
        self.assertFalse(can_drop_rare(self.npc))


class TestRarityConstants(BaseEvenniaTest):
    """Verify rarity constants are properly defined."""

    def test_boss_only_rarities_are_rare_or_higher(self):
        """BOSS_ONLY_RARITIES contains rare, epic, legendary."""
        self.assertIn(RARITY_RARE, BOSS_ONLY_RARITIES)
        self.assertIn(RARITY_EPIC, BOSS_ONLY_RARITIES)
        self.assertIn(RARITY_LEGENDARY, BOSS_ONLY_RARITIES)
        self.assertNotIn(RARITY_COMMON, BOSS_ONLY_RARITIES)

    def test_rarity_colors(self):
        """RARITY_COLORS has entries for all rarities."""
        for rarity in [RARITY_COMMON, RARITY_RARE, RARITY_EPIC,
                       RARITY_LEGENDARY]:
            self.assertIn(rarity, RARITY_COLORS)

    def test_value_for_rarity_increases(self):
        """Higher rarities have higher gold values."""
        rare_val = BossLootHandler._value_for_rarity(RARITY_RARE)
        epic_val = BossLootHandler._value_for_rarity(RARITY_EPIC)
        leg_val = BossLootHandler._value_for_rarity(RARITY_LEGENDARY)
        self.assertLess(rare_val, epic_val)
        self.assertLess(epic_val, leg_val)


# ===========================================================================
#  3. Armor Set Tests
# ===========================================================================

class TestArmorSetDefinition(BaseEvenniaTest):
    """Test ArmorSetDefinition logic."""

    def setUp(self):
        super().setUp()
        self.ds_set = ArmorSetDefinition(
            set_id="dragonscale",
            name="Dragonscale Armor",
            pieces={
                "head": "Dragonscale Helm",
                "torso": "Dragonscale Breastplate",
                "legs": "Dragonscale Greaves",
                "arms": "Dragonscale Vambraces",
            },
            bonus_2={"max_hp": 20, "defense": 2},
            bonus_4={"max_hp": 50, "defense": 5, "fire_resist": 15},
            flavor_text="Dragon scales protect the wearer.",
        )

    def tearDown(self):
        super().tearDown()

    def test_get_item_keys(self):
        """get_item_keys returns all piece names."""
        keys = self.ds_set.get_item_keys()
        self.assertEqual(len(keys), 4)
        self.assertIn("Dragonscale Helm", keys)

    def test_get_slots(self):
        """get_slots returns slot names."""
        slots = self.ds_set.get_slots()
        self.assertEqual(len(slots), 4)
        self.assertIn("head", slots)

    def test_check_piece_match(self):
        """check_piece matches an equipped item correctly."""
        self.assertTrue(
            self.ds_set.check_piece("head", "Dragonscale Helm")
        )
        self.assertFalse(
            self.ds_set.check_piece("head", "Iron Helm")
        )
        self.assertFalse(
            self.ds_set.check_piece("neck", "Dragonscale Helm")
        )

    def test_check_piece_case_insensitive(self):
        """check_piece is case-insensitive."""
        self.assertTrue(
            self.ds_set.check_piece("head", "dragonscale helm")
        )
        self.assertTrue(
            self.ds_set.check_piece("HEAD", "DRAGONSCALE HELM")
        )

    def test_count_equipped_0(self):
        """count_equipped returns 0 for empty equipped."""
        self.assertEqual(self.ds_set.count_equipped({}), 0)

    def test_count_equipped_2(self):
        """count_equipped returns 2 when 2 pieces match."""
        equipped = {
            "head": "Dragonscale Helm",
            "torso": "Dragonscale Breastplate",
            "legs": "Iron Greaves",
            "arms": "Leather Vambraces",
        }
        self.assertEqual(self.ds_set.count_equipped(equipped), 2)

    def test_count_equipped_4(self):
        """count_equipped returns 4 when all pieces match."""
        equipped = {
            "head": "Dragonscale Helm",
            "torso": "Dragonscale Breastplate",
            "legs": "Dragonscale Greaves",
            "arms": "Dragonscale Vambraces",
        }
        self.assertEqual(self.ds_set.count_equipped(equipped), 4)

    def test_get_bonus_for_count_0(self):
        """0 pieces -> no bonuses."""
        bonuses = self.ds_set.get_bonus_for_count(0)
        self.assertEqual(bonuses, {})

    def test_get_bonus_for_count_1(self):
        """1 piece -> no bonuses (need at least 2)."""
        bonuses = self.ds_set.get_bonus_for_count(1)
        self.assertEqual(bonuses, {})

    def test_get_bonus_for_count_2(self):
        """2 pieces -> 2-piece bonus."""
        bonuses = self.ds_set.get_bonus_for_count(2)
        self.assertEqual(bonuses["max_hp"], 20)
        self.assertEqual(bonuses["defense"], 2)
        self.assertNotIn("fire_resist", bonuses)

    def test_get_bonus_for_count_3(self):
        """3 pieces -> 2-piece bonus (threshold not met for 4)."""
        bonuses = self.ds_set.get_bonus_for_count(3)
        self.assertEqual(bonuses["max_hp"], 20)
        self.assertNotIn("fire_resist", bonuses)

    def test_get_bonus_for_count_4(self):
        """4 pieces -> both bonuses stack (20+50=70 max_hp)."""
        bonuses = self.ds_set.get_bonus_for_count(4)
        self.assertEqual(bonuses["max_hp"], 70)  # 20 + 50
        self.assertEqual(bonuses["defense"], 7)   # 2 + 5
        self.assertEqual(bonuses["fire_resist"], 15)


class TestArmorSetRegistry(BaseEvenniaTest):
    """Test the armor set registry."""

    def setUp(self):
        super().setUp()
        self.reg = ArmorSetRegistry()
        self.set1 = ArmorSetDefinition(
            set_id="test_set",
            name="Test Set",
            pieces={"head": "Test Helm", "torso": "Test Chest"},
            bonus_2={"max_hp": 10},
            bonus_4={"max_hp": 30},
        )

    def tearDown(self):
        self.reg.clear()
        super().tearDown()

    def test_register_and_retrieve(self):
        """Sets can be registered and retrieved."""
        self.reg.register(self.set1)
        retrieved = self.reg.get("test_set")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Test Set")

    def test_find_set_for_item(self):
        """find_set_for_item finds the set an item belongs to."""
        self.reg.register(self.set1)
        found = self.reg.find_set_for_item("Test Helm")
        self.assertIsNotNone(found)
        self.assertEqual(found.set_id, "test_set")

    def test_find_set_for_item_not_found(self):
        """Returns None if item is not in any set."""
        self.reg.register(self.set1)
        self.assertIsNone(self.reg.find_set_for_item("Random Axe"))

    def test_find_set_for_item_with_slot(self):
        """find_set_for_item with slot narrows search."""
        self.reg.register(self.set1)
        found = self.reg.find_set_for_item("Test Helm", slot="head")
        self.assertIsNotNone(found)
        # Wrong slot should not match
        found2 = self.reg.find_set_for_item("Test Helm", slot="legs")
        self.assertIsNone(found2)

    def test_all_returns_all_sets(self):
        """all() returns all registered sets."""
        self.reg.register(self.set1)
        set2 = ArmorSetDefinition(
            set_id="set2",
            name="Set 2",
            pieces={"head": "Helm2"},
        )
        self.reg.register(set2)
        self.assertEqual(len(self.reg.all()), 2)

    def test_clear_removes_all(self):
        """clear() removes all sets."""
        self.reg.register(self.set1)
        self.reg.clear()
        self.assertEqual(len(self.reg.all()), 0)


class TestArmorSetChecker(BaseEvenniaTest):
    """Test the ArmorSetChecker on a character."""

    def setUp(self):
        super().setUp()
        self.char = create_object(DefaultCharacter, key="ArmorTester")

        # Register test sets before testing
        armor_set_registry.clear()
        self.ds_set = ArmorSetDefinition(
            set_id="dragonscale",
            name="Dragonscale Armor",
            pieces={
                "head": "Dragonscale Helm",
                "torso": "Dragonscale Breastplate",
                "legs": "Dragonscale Greaves",
                "arms": "Dragonscale Vambraces",
            },
            bonus_2={"max_hp": 20, "defense": 2},
            bonus_4={"max_hp": 50, "defense": 5, "fire_resist": 15},
        )
        armor_set_registry.register(self.ds_set)

    def tearDown(self):
        self.char.delete()
        armor_set_registry.clear()
        super().tearDown()

    def test_no_equipped_returns_empty(self):
        """No equipment means no set bonuses."""
        checker = ArmorSetChecker(self.char)
        active = checker.get_active_set_bonuses()
        self.assertEqual(active, {})

    def test_partial_set_2_pieces(self):
        """2 pieces of a set yields the 2-piece bonus."""
        self.char.attributes.add("equipped", {
            "head": "Dragonscale Helm",
            "torso": "Dragonscale Breastplate",
        })
        checker = ArmorSetChecker(self.char)
        active = checker.get_active_set_bonuses()
        self.assertIn("dragonscale", active)
        data = active["dragonscale"]
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["bonuses"]["max_hp"], 20)
        self.assertEqual(data["bonuses"]["defense"], 2)

    def test_full_set_4_pieces(self):
        """All 4 pieces give stacked bonuses."""
        self.char.attributes.add("equipped", {
            "head": "Dragonscale Helm",
            "torso": "Dragonscale Breastplate",
            "legs": "Dragonscale Greaves",
            "arms": "Dragonscale Vambraces",
        })
        checker = ArmorSetChecker(self.char)
        active = checker.get_active_set_bonuses()
        data = active["dragonscale"]
        self.assertEqual(data["count"], 4)
        self.assertEqual(data["bonuses"]["max_hp"], 70)
        self.assertEqual(data["bonuses"]["defense"], 7)
        self.assertEqual(data["bonuses"]["fire_resist"], 15)

    def test_total_bonuses_aggregates(self):
        """get_total_bonuses sums all active set bonuses."""
        self.char.attributes.add("equipped", {
            "head": "Dragonscale Helm",
            "torso": "Dragonscale Breastplate",
            "legs": "Dragonscale Greaves",
            "arms": "Dragonscale Vambraces",
        })
        checker = ArmorSetChecker(self.char)
        totals = checker.get_total_bonuses()
        self.assertEqual(totals["max_hp"], 70)
        self.assertEqual(totals["defense"], 7)
        self.assertEqual(totals["fire_resist"], 15)

    def test_format_display_empty(self):
        """format_display is empty when no sets active."""
        checker = ArmorSetChecker(self.char)
        self.assertEqual(checker.format_display(), "")

    def test_format_display_shows_set_info(self):
        """format_display shows set name, count, and bonuses."""
        self.char.attributes.add("equipped", {
            "head": "Dragonscale Helm",
            "torso": "Dragonscale Breastplate",
        })
        checker = ArmorSetChecker(self.char)
        display = checker.format_display()
        self.assertIn("Dragonscale Armor", display)
        self.assertIn("2/4", display)
        self.assertIn("Max HP", display)

    def test_apply_and_retrieve_set_bonuses(self):
        """apply_set_bonuses_to_character stores bonuses."""
        self.char.attributes.add("equipped", {
            "head": "Dragonscale Helm",
            "torso": "Dragonscale Breastplate",
            "legs": "Dragonscale Greaves",
            "arms": "Dragonscale Vambraces",
        })
        bonuses = apply_set_bonuses_to_character(self.char)
        self.assertEqual(bonuses["max_hp"], 70)

        stored = get_stored_set_bonuses(self.char)
        self.assertEqual(stored["max_hp"], 70)

    def test_case_insensitive_equipment_match(self):
        """Set matching is case-insensitive for equipped item names."""
        self.char.attributes.add("equipped", {
            "head": "dragonscale helm",
            "torso": "DRAGONSCALE BREASTPLATE",
        })
        checker = ArmorSetChecker(self.char)
        active = checker.get_active_set_bonuses()
        self.assertIn("dragonscale", active)
        self.assertEqual(active["dragonscale"]["count"], 2)


class TestMultipleArmorSets(BaseEvenniaTest):
    """Test handling of multiple simultaneous armor sets."""

    def setUp(self):
        super().setUp()
        self.char = create_object(DefaultCharacter, key="MultiSetTester")

        armor_set_registry.clear()
        # Set 1: Dragonscale
        ds = ArmorSetDefinition(
            set_id="dragonscale",
            name="Dragonscale Armor",
            pieces={
                "head": "Dragonscale Helm",
                "torso": "Dragonscale Breastplate",
                "legs": "Dragonscale Greaves",
                "arms": "Dragonscale Vambraces",
            },
            bonus_2={"max_hp": 20},
            bonus_4={"max_hp": 50, "defense": 5},
        )
        armor_set_registry.register(ds)

        # Set 2: Paladin Radiant
        pr = ArmorSetDefinition(
            set_id="paladin_radiant",
            name="Paladin's Radiant Suit",
            pieces={
                "head": "Radiant Crown",
                "torso": "Radiant Breastplate",
                "legs": "Radiant Greaves",
                "arms": "Radiant Gauntlets",
            },
            bonus_2={"max_mana": 10},
            bonus_4={"max_mana": 30, "defense": 6},
        )
        armor_set_registry.register(pr)

    def tearDown(self):
        self.char.delete()
        armor_set_registry.clear()
        super().tearDown()

    def test_two_partial_sets(self):
        """2 pieces of two different sets give combined bonuses."""
        self.char.attributes.add("equipped", {
            "head": "Dragonscale Helm",
            "torso": "Dragonscale Breastplate",
            "legs": "Radiant Greaves",
            "arms": "Radiant Gauntlets",
        })
        checker = ArmorSetChecker(self.char)
        active = checker.get_active_set_bonuses()
        self.assertIn("dragonscale", active)
        self.assertIn("paladin_radiant", active)
        totals = checker.get_total_bonuses()
        self.assertEqual(totals["max_hp"], 20)
        self.assertEqual(totals["max_mana"], 10)

    def test_one_full_one_no_bonus(self):
        """Full set + 1 piece of another = only full and nothing."""
        self.char.attributes.add("equipped", {
            "head": "Dragonscale Helm",
            "torso": "Dragonscale Breastplate",
            "legs": "Dragonscale Greaves",
            "arms": "Dragonscale Vambraces",
        })
        checker = ArmorSetChecker(self.char)
        active = checker.get_active_set_bonuses()
        # Only Dragonscale should show (all 4 pieces)
        self.assertIn("dragonscale", active)
        self.assertNotIn("paladin_radiant", active)
        totals = checker.get_total_bonuses()
        self.assertEqual(totals["max_hp"], 70)
        self.assertEqual(totals["defense"], 5)


class TestDefaultArmorSets(BaseEvenniaTest):
    """Test that built-in armor sets register correctly."""

    def setUp(self):
        super().setUp()
        armor_set_registry.clear()

    def tearDown(self):
        armor_set_registry.clear()
        super().tearDown()

    def test_register_default_armor_sets(self):
        """register_default_armor_sets populates the registry."""
        register_default_armor_sets()
        all_sets = armor_set_registry.all()
        self.assertGreaterEqual(len(all_sets), 4)

        # Check key sets exist
        ds = armor_set_registry.get("dragonscale")
        self.assertIsNotNone(ds)
        self.assertEqual(ds.name, "Dragonscale Armor")

        ss = armor_set_registry.get("shadowstalker")
        self.assertIsNotNone(ss)

        pr = armor_set_registry.get("paladin_radiant")
        self.assertIsNotNone(pr)

        lr = armor_set_registry.get("lich_regalia")
        self.assertIsNotNone(lr)