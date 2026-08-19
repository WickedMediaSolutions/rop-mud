"""
Phase 3.1 Horizontal Systems Tests
===================================
Tests for Tradeskills, Mounts, Survival, Day/Night, Achievements.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
import django
django.setup()


class MockCharacter:
    _next_id = 1

    def __init__(self, name="TestChar", level=1, hp=100, max_hp=100, mv=100, max_mv=100,
                 mana=100, max_mana=100, gold=500, stats=None):
        self.key = name
        self.id = MockCharacter._next_id
        MockCharacter._next_id += 1
        self.has_account = True
        self.location = None
        self.contents = []
        self.destination = None

        class MockNdb:
            pass
        self.ndb = MockNdb()

        class MockAttributes:
            def __init__(self, store=None):
                self._store = dict(store) if store else {}

            def get(self, key, default=None):
                return self._store.get(key, default)

            def add(self, key, value):
                self._store[key] = value

            def has(self, key):
                return key in self._store

            def set(self, key, value):
                self._store[key] = value

            def all(self):
                return dict(self._store)

        self.attributes = MockAttributes({
            "level": level,
            "hp": hp,
            "max_hp": max_hp,
            "mv": mv,
            "max_mv": max_mv,
            "mana": mana,
            "max_mana": max_mana,
            "gold_coins": gold,
            "stats": stats or {"str": 12, "dex": 14, "con": 12, "int": 12, "wis": 14, "cha": 10},
            "equipped": {},
            "hunger": 100,
            "thirst": 100,
        })
        self.msg = lambda text: None


class MockRoom:
    _next_id = 1000

    def __init__(self, biome="plains", outdoor=True, light_level=None):
        self.id = MockRoom._next_id
        MockRoom._next_id += 1
        self.key = f"Room_{self.id}"

        class MockAttributes:
            def __init__(self, store=None):
                self._store = dict(store) if store else {}

            def get(self, key, default=None):
                return self._store.get(key, default)

            def add(self, key, value):
                self._store[key] = value

        self.attributes = MockAttributes({
            "biome": biome,
            "outdoor": outdoor,
            "light_level": light_level,
        })


# ============================================================================
# Tradeskills Tests
# ============================================================================

class TestTradeskills(unittest.TestCase):
    def setUp(self):
        from world.tradeskills import TRADESKILLS, RECIPES, GATHER_MATERIALS, MATERIAL_TIERS
        self.TRADESKILLS = TRADESKILLS
        self.RECIPES = RECIPES
        self.GATHER_MATERIALS = GATHER_MATERIALS
        self.MATERIAL_TIERS = MATERIAL_TIERS

    def test_8_tradeskills_defined(self):
        self.assertEqual(len(self.TRADESKILLS), 8)

    def test_4_gathering_skills(self):
        gather_skills = [k for k, v in self.TRADESKILLS.items() if "gather_verb" in v]
        self.assertEqual(len(gather_skills), 4)

    def test_4_crafting_skills(self):
        craft_skills = [k for k, v in self.TRADESKILLS.items() if "craft_verb" in v]
        self.assertEqual(len(craft_skills), 4)

    def test_5_material_tiers(self):
        self.assertEqual(len(self.MATERIAL_TIERS), 5)
        for tier in ["common", "uncommon", "rare", "epic", "legendary"]:
            self.assertIn(tier, self.MATERIAL_TIERS)

    def test_gather_materials_have_all_biomes(self):
        for skill_key, biomes in self.GATHER_MATERIALS.items():
            skill_def = self.TRADESKILLS[skill_key]
            expected_biomes = set(skill_def["biomes"])
            actual_biomes = set(biomes.keys())
            self.assertEqual(expected_biomes, actual_biomes,
                             f"{skill_key} biome mismatch")

    def test_recipes_have_required_fields(self):
        required = ["name", "skill_req", "materials", "output", "xp"]
        for skill_key, recipes in self.RECIPES.items():
            for recipe_key, recipe in recipes.items():
                for field in required:
                    self.assertIn(field, recipe,
                                  f"{skill_key}/{recipe_key} missing {field}")

    def test_gather_unknown_skill_fails(self):
        from world.tradeskills import gather
        char = MockCharacter()
        ok, msg = gather(char, "nonexistent")
        self.assertFalse(ok)

    def test_gather_crafting_skill_fails(self):
        from world.tradeskills import gather
        char = MockCharacter()
        ok, msg = gather(char, "blacksmithing")
        self.assertFalse(ok)

    def test_gather_no_location_fails(self):
        from world.tradeskills import gather
        char = MockCharacter()
        char.location = None
        ok, msg = gather(char, "mining")
        self.assertFalse(ok)

    def test_gather_wrong_biome_fails(self):
        from world.tradeskills import gather
        char = MockCharacter()
        char.location = MockRoom(biome="plains")
        ok, msg = gather(char, "mining")
        self.assertFalse(ok)

    def test_gather_correct_biome_succeeds(self):
        from world.tradeskills import gather
        char = MockCharacter()
        char.location = MockRoom(biome="mountain")
        ok, msg = gather(char, "mining")
        self.assertTrue(ok)
        self.assertIn("mine", msg.lower())

    def test_gather_adds_material(self):
        from world.tradeskills import gather, get_materials
        char = MockCharacter()
        char.location = MockRoom(biome="forest")
        ok, msg = gather(char, "foraging")
        self.assertTrue(ok)
        materials = get_materials(char)
        self.assertGreater(len(materials), 0)

    def test_gather_adds_xp(self):
        from world.tradeskills import gather, _get_skill_xp
        char = MockCharacter()
        char.location = MockRoom(biome="forest")
        gather(char, "foraging")
        xp = _get_skill_xp(char, "foraging")
        self.assertGreater(xp, 0)

    def test_craft_unknown_skill_fails(self):
        from world.tradeskills import craft
        char = MockCharacter()
        ok, msg = craft(char, "nonexistent", "iron_sword")
        self.assertFalse(ok)

    def test_craft_unknown_recipe_fails(self):
        from world.tradeskills import craft
        char = MockCharacter()
        ok, msg = craft(char, "blacksmithing", "nonexistent")
        self.assertFalse(ok)

    def test_craft_insufficient_skill_fails(self):
        from world.tradeskills import craft
        char = MockCharacter()
        ok, msg = craft(char, "blacksmithing", "mithril_blade")  # req 60
        self.assertFalse(ok)

    def test_craft_no_materials_fails(self):
        from world.tradeskills import craft, _set_skill_level
        char = MockCharacter()
        _set_skill_level(char, "blacksmithing", 60)
        ok, msg = craft(char, "blacksmithing", "iron_sword")
        self.assertFalse(ok)

    def test_craft_with_materials_succeeds(self):
        from world.tradeskills import craft, _set_skill_level, _add_material
        char = MockCharacter()
        _set_skill_level(char, "blacksmithing", 60)
        _add_material(char, "iron_ore", 10)
        _add_material(char, "coal", 10)
        ok, msg = craft(char, "blacksmithing", "iron_sword")
        self.assertTrue(ok)

    def test_list_recipes_returns_sorted(self):
        from world.tradeskills import list_recipes
        recipes = list_recipes("blacksmithing")
        self.assertGreater(len(recipes), 0)
        for i in range(len(recipes) - 1):
            self.assertLessEqual(recipes[i]["skill_req"], recipes[i + 1]["skill_req"])

    def test_list_skills_returns_all(self):
        from world.tradeskills import list_skills
        char = MockCharacter()
        skills = list_skills(char)
        self.assertEqual(len(skills), 8)

    def test_skill_level_capped_at_100(self):
        from world.tradeskills import _set_skill_level, _get_skill_level
        char = MockCharacter()
        _set_skill_level(char, "mining", 150)
        self.assertEqual(_get_skill_level(char, "mining"), 100)

    def test_skill_level_min_1(self):
        from world.tradeskills import _set_skill_level, _get_skill_level
        char = MockCharacter()
        _set_skill_level(char, "mining", -5)
        self.assertEqual(_get_skill_level(char, "mining"), 1)


# ============================================================================
# Mounts Tests
# ============================================================================

class TestMounts(unittest.TestCase):
    def setUp(self):
        from world.mounts import MOUNTS
        self.MOUNTS = MOUNTS

    def test_6_mounts_defined(self):
        self.assertEqual(len(self.MOUNTS), 6)

    def test_mounts_have_required_fields(self):
        required = ["name", "desc", "speed_bonus_pct", "max_hp", "cost", "min_level", "combat_bonus", "stamina_drain"]
        for key, mount in self.MOUNTS.items():
            for field in required:
                self.assertIn(field, mount, f"{key} missing {field}")

    def test_list_mounts_returns_all(self):
        from world.mounts import list_mounts
        mounts = list_mounts()
        self.assertEqual(len(mounts), 6)

    def test_buy_unknown_mount_fails(self):
        from world.mounts import buy_mount
        char = MockCharacter()
        ok, msg = buy_mount(char, "nonexistent")
        self.assertFalse(ok)

    def test_buy_mount_too_low_level_fails(self):
        from world.mounts import buy_mount
        char = MockCharacter(level=1)
        ok, msg = buy_mount(char, "dragon_mount")
        self.assertFalse(ok)

    def test_mount_up_without_mount_fails(self):
        from world.mounts import mount_up
        char = MockCharacter()
        ok, msg = mount_up(char)
        self.assertFalse(ok)

    def test_dismount_without_mount_fails(self):
        from world.mounts import dismount
        char = MockCharacter()
        ok, msg = dismount(char)
        self.assertFalse(ok)

    def test_get_mount_speed_bonus_not_mounted(self):
        from world.mounts import get_mount_speed_bonus
        char = MockCharacter()
        self.assertEqual(get_mount_speed_bonus(char), 0)

    def test_get_mount_combat_bonuses_not_mounted(self):
        from world.mounts import get_mount_combat_bonuses
        char = MockCharacter()
        self.assertEqual(get_mount_combat_bonuses(char), {})

    def test_drain_mount_stamina_not_mounted(self):
        from world.mounts import drain_mount_stamina
        char = MockCharacter()
        hp, exhausted = drain_mount_stamina(char)
        self.assertEqual(hp, 0)
        self.assertFalse(exhausted)

    def test_rest_mount_without_mount_fails(self):
        from world.mounts import rest_mount
        char = MockCharacter()
        ok, msg = rest_mount(char)
        self.assertFalse(ok)

    def test_get_mount_info_without_mount(self):
        from world.mounts import get_mount_info
        char = MockCharacter()
        self.assertIsNone(get_mount_info(char))


# ============================================================================
# Survival Tests
# ============================================================================

class TestSurvival(unittest.TestCase):
    def setUp(self):
        from world.survival import FOOD_ITEMS, DRINK_ITEMS
        self.FOOD_ITEMS = FOOD_ITEMS
        self.DRINK_ITEMS = DRINK_ITEMS

    def test_12_food_items(self):
        self.assertEqual(len(self.FOOD_ITEMS), 12)

    def test_9_drink_items(self):
        self.assertEqual(len(self.DRINK_ITEMS), 9)

    def test_food_items_have_required_fields(self):
        required = ["name", "hunger_restore", "thirst_restore", "quality", "cost"]
        for key, food in self.FOOD_ITEMS.items():
            for field in required:
                self.assertIn(field, food, f"{key} missing {field}")

    def test_drink_items_have_required_fields(self):
        required = ["name", "thirst_restore", "hunger_restore", "quality", "cost"]
        for key, drink in self.DRINK_ITEMS.items():
            for field in required:
                self.assertIn(field, drink, f"{key} missing {field}")

    def test_consume_unknown_food_fails(self):
        from world.survival import consume_food
        char = MockCharacter()
        ok, msg = consume_food(char, "nonexistent")
        self.assertFalse(ok)

    def test_consume_unknown_drink_fails(self):
        from world.survival import consume_drink
        char = MockCharacter()
        ok, msg = consume_drink(char, "nonexistent")
        self.assertFalse(ok)

    def test_consume_food_restores_hunger(self):
        from world.survival import consume_food, _get_hunger
        char = MockCharacter()
        char.attributes.add("hunger", 50)
        ok, msg = consume_food(char, "bread")
        self.assertTrue(ok)
        self.assertGreater(_get_hunger(char), 50)

    def test_consume_drink_restores_thirst(self):
        from world.survival import consume_drink, _get_thirst
        char = MockCharacter()
        char.attributes.add("thirst", 50)
        ok, msg = consume_drink(char, "water")
        self.assertTrue(ok)
        self.assertGreater(_get_thirst(char), 50)

    def test_eat_when_full_fails(self):
        from world.survival import consume_food
        char = MockCharacter()
        char.attributes.add("hunger", 100)
        ok, msg = consume_food(char, "bread")
        self.assertFalse(ok)

    def test_drink_when_full_fails(self):
        from world.survival import consume_drink
        char = MockCharacter()
        char.attributes.add("thirst", 100)
        ok, msg = consume_drink(char, "water")
        self.assertFalse(ok)

    def test_get_survival_status(self):
        from world.survival import get_survival_status
        char = MockCharacter()
        status = get_survival_status(char)
        self.assertIn("hunger", status)
        self.assertIn("thirst", status)
        self.assertIn("hunger_status", status)
        self.assertIn("thirst_status", status)

    def test_tick_survival_decays(self):
        from world.survival import tick_survival, _get_hunger, _get_thirst
        char = MockCharacter()
        char.attributes.add("hunger", 100)
        char.attributes.add("thirst", 100)
        tick_survival(char)
        self.assertLess(_get_hunger(char), 100)
        self.assertLess(_get_thirst(char), 100)

    def test_starving_drains_hp(self):
        from world.survival import tick_survival
        char = MockCharacter(hp=50)
        char.attributes.add("hunger", 5)
        char.attributes.add("thirst", 100)
        tick_survival(char)
        self.assertLess(char.attributes.get("hp", 50), 50)

    def test_dehydrated_drains_mv(self):
        from world.survival import tick_survival
        char = MockCharacter(mv=50)
        char.attributes.add("hunger", 100)
        char.attributes.add("thirst", 5)
        tick_survival(char)
        self.assertLess(char.attributes.get("mv", 50), 50)

    def test_well_fed_regen_hp(self):
        from world.survival import tick_survival
        char = MockCharacter(hp=50, max_hp=100)
        char.attributes.add("hunger", 80)
        char.attributes.add("thirst", 100)
        tick_survival(char)
        self.assertGreater(char.attributes.get("hp", 50), 50)

    def test_hydrated_regen_mv(self):
        from world.survival import tick_survival
        char = MockCharacter(mv=50, max_mv=100)
        char.attributes.add("hunger", 100)
        char.attributes.add("thirst", 80)
        tick_survival(char)
        self.assertGreater(char.attributes.get("mv", 50), 50)

    def test_survival_stat_modifiers_starving(self):
        from world.survival import get_survival_stat_modifiers
        char = MockCharacter()
        char.attributes.add("hunger", 5)
        char.attributes.add("thirst", 100)
        mods = get_survival_stat_modifiers(char)
        self.assertIn("str", mods)
        self.assertIn("con", mods)

    def test_survival_stat_modifiers_dehydrated(self):
        from world.survival import get_survival_stat_modifiers
        char = MockCharacter()
        char.attributes.add("hunger", 100)
        char.attributes.add("thirst", 5)
        mods = get_survival_stat_modifiers(char)
        self.assertIn("dex", mods)
        self.assertIn("wis", mods)

    def test_list_food_returns_all(self):
        from world.survival import list_food
        foods = list_food()
        self.assertEqual(len(foods), 12)

    def test_list_drinks_returns_all(self):
        from world.survival import list_drinks
        drinks = list_drinks()
        self.assertEqual(len(drinks), 9)


# ============================================================================
# Day/Night Tests
# ============================================================================

class TestDayNight(unittest.TestCase):
    def test_get_time_of_day_returns_valid_phase(self):
        from world.daynight import get_time_of_day
        phase = get_time_of_day()
        self.assertIn(phase, ["dawn", "day", "dusk", "night"])

    def test_get_light_level_in_range(self):
        from world.daynight import get_light_level
        light = get_light_level()
        self.assertGreaterEqual(light, 0)
        self.assertLessEqual(light, 100)

    def test_get_moon_phase_valid(self):
        from world.daynight import get_moon_phase, MOON_PHASES
        moon = get_moon_phase()
        self.assertIn(moon, MOON_PHASES)

    def test_get_game_hour_in_range(self):
        from world.daynight import get_game_hour
        hour = get_game_hour()
        self.assertGreaterEqual(hour, 0)
        self.assertLessEqual(hour, 23)

    def test_get_game_minute_in_range(self):
        from world.daynight import get_game_minute
        minute = get_game_minute()
        self.assertGreaterEqual(minute, 0)
        self.assertLessEqual(minute, 59)

    def test_get_room_light_outdoor(self):
        from world.daynight import get_room_light
        room = MockRoom(outdoor=True)
        light = get_room_light(room)
        self.assertGreaterEqual(light, 0)
        self.assertLessEqual(light, 100)

    def test_get_room_light_indoor_default(self):
        from world.daynight import get_room_light
        room = MockRoom(outdoor=False)
        light = get_room_light(room)
        self.assertEqual(light, 60)

    def test_get_room_light_indoor_custom(self):
        from world.daynight import get_room_light
        room = MockRoom(outdoor=False, light_level=30)
        light = get_room_light(room)
        self.assertEqual(light, 30)

    def test_get_visibility_text(self):
        from world.daynight import get_visibility_text
        self.assertEqual(get_visibility_text(0), "pitch black")
        self.assertEqual(get_visibility_text(20), "very dark")
        self.assertEqual(get_visibility_text(40), "dim")
        self.assertEqual(get_visibility_text(70), "bright")
        self.assertEqual(get_visibility_text(100), "full daylight")

    def test_get_spawn_rate_modifier(self):
        from world.daynight import get_spawn_rate_modifier
        modifier = get_spawn_rate_modifier()
        self.assertGreaterEqual(modifier, 0.5)
        self.assertLessEqual(modifier, 2.0)

    def test_is_shop_open_returns_bool(self):
        from world.daynight import is_shop_open
        result = is_shop_open()
        self.assertIsInstance(result, bool)

    def test_get_night_bonuses_returns_dict(self):
        from world.daynight import get_night_bonuses
        bonuses = get_night_bonuses()
        self.assertIsInstance(bonuses, dict)

    def test_format_time_returns_string(self):
        from world.daynight import format_time
        time_str = format_time()
        self.assertIsInstance(time_str, str)
        self.assertGreater(len(time_str), 0)

    def test_get_light_description(self):
        from world.daynight import get_light_description
        room = MockRoom(outdoor=True)
        desc = get_light_description(room)
        self.assertIsInstance(desc, str)
        self.assertGreater(len(desc), 0)

    def test_day_progress_in_range(self):
        from world.daynight import get_day_progress
        progress = get_day_progress()
        self.assertGreaterEqual(progress, 0.0)
        self.assertLessEqual(progress, 1.0)


# ============================================================================
# Achievements Tests
# ============================================================================

class TestAchievements(unittest.TestCase):
    def setUp(self):
        from world.achievements import ACHIEVEMENTS, CATEGORIES
        self.ACHIEVEMENTS = ACHIEVEMENTS
        self.CATEGORIES = CATEGORIES

    def test_32_achievements_defined(self):
        self.assertEqual(len(self.ACHIEVEMENTS), 32)

    def test_6_categories(self):
        self.assertEqual(len(self.CATEGORIES), 6)

    def test_achievements_have_required_fields(self):
        required = ["name", "desc", "category", "tier", "points", "title", "condition"]
        for key, ach in self.ACHIEVEMENTS.items():
            for field in required:
                self.assertIn(field, ach, f"{key} missing {field}")

    def test_all_categories_valid(self):
        for key, ach in self.ACHIEVEMENTS.items():
            self.assertIn(ach["category"], self.CATEGORIES,
                          f"{key} has invalid category {ach['category']}")

    def test_all_tiers_valid(self):
        valid_tiers = ["Bronze", "Silver", "Gold", "Platinum", "Legendary"]
        for key, ach in self.ACHIEVEMENTS.items():
            self.assertIn(ach["tier"], valid_tiers,
                          f"{key} has invalid tier {ach['tier']}")

    def test_check_unknown_achievement(self):
        from world.achievements import check_achievement
        char = MockCharacter()
        ok, msg = check_achievement(char, "nonexistent")
        self.assertFalse(ok)

    def test_check_achievement_not_met(self):
        from world.achievements import check_achievement
        char = MockCharacter()
        ok, msg = check_achievement(char, "seasoned_warrior")  # needs 100 kills
        self.assertFalse(ok)

    def test_track_kill_unlocks_first_blood(self):
        from world.achievements import track_kill, _get_achievements
        char = MockCharacter()
        msgs = track_kill(char)
        achievements = _get_achievements(char)
        self.assertIn("first_blood", achievements)
        self.assertGreater(len(msgs), 0)

    def test_track_kill_does_not_unlock_seasoned_warrior(self):
        from world.achievements import track_kill, _get_achievements
        char = MockCharacter()
        track_kill(char)
        achievements = _get_achievements(char)
        self.assertNotIn("seasoned_warrior", achievements)

    def test_track_crit(self):
        from world.achievements import track_crit
        char = MockCharacter()
        msgs = track_crit(char)
        self.assertIsInstance(msgs, list)

    def test_track_room_visit(self):
        from world.achievements import track_room_visit
        char = MockCharacter()
        msgs = track_room_visit(char, 1)
        self.assertIsInstance(msgs, list)

    def test_track_craft(self):
        from world.achievements import track_craft
        char = MockCharacter()
        msgs = track_craft(char)
        self.assertIsInstance(msgs, list)

    def test_track_tradeskill_level(self):
        from world.achievements import track_tradeskill_level
        char = MockCharacter()
        msgs = track_tradeskill_level(char, 30)
        self.assertIsInstance(msgs, list)

    def test_track_gold(self):
        from world.achievements import track_gold
        char = MockCharacter()
        msgs = track_gold(char, 500)
        self.assertIsInstance(msgs, list)

    def test_track_near_death(self):
        from world.achievements import track_near_death
        char = MockCharacter()
        msgs = track_near_death(char)
        self.assertIsInstance(msgs, list)

    def test_get_achievement_list(self):
        from world.achievements import get_achievement_list
        char = MockCharacter()
        achievements = get_achievement_list(char)
        self.assertEqual(len(achievements), 32)

    def test_get_achievement_points_zero(self):
        from world.achievements import get_achievement_points
        char = MockCharacter()
        self.assertEqual(get_achievement_points(char), 0)

    def test_get_active_title_none(self):
        from world.achievements import get_active_title
        char = MockCharacter()
        self.assertIsNone(get_active_title(char))

    def test_set_title_not_unlocked_fails(self):
        from world.achievements import set_active_title
        char = MockCharacter()
        ok, msg = set_active_title(char, "the Slayer")
        self.assertFalse(ok)

    def test_clear_title(self):
        from world.achievements import clear_title
        char = MockCharacter()
        ok, msg = clear_title(char)
        self.assertTrue(ok)

    def test_get_unlocked_titles_empty(self):
        from world.achievements import get_unlocked_titles
        char = MockCharacter()
        self.assertEqual(get_unlocked_titles(char), [])

    def test_check_all_achievements(self):
        from world.achievements import check_all_achievements
        char = MockCharacter()
        msgs = check_all_achievements(char)
        self.assertIsInstance(msgs, list)

    def test_achievement_unlock_awards_points(self):
        from world.achievements import track_kill, get_achievement_points
        char = MockCharacter()
        track_kill(char)
        self.assertGreater(get_achievement_points(char), 0)

    def test_achievement_unlock_awards_title(self):
        from world.achievements import track_kill, get_unlocked_titles
        char = MockCharacter()
        # First Blood has no title, but Seasoned Warrior does
        # We need 100 kills for Seasoned Warrior
        for _ in range(100):
            track_kill(char)
        titles = get_unlocked_titles(char)
        self.assertIn("the Seasoned", titles)


if __name__ == "__main__":
    unittest.main()