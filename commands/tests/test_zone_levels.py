"""
Unit tests for the Zone Level & Difficulty Scaling System.

Verifies:
  - Zone tier assignments (level ranges per zone)
  - Mob level scaling per tier
  - Aggressive behavior per tier
  - Room tag integrity after building
"""
from django.test import TestCase
from world.zone_levels import (
    get_zone_tier_for_name,
    get_zone_level_range,
    get_danger_level,
    scale_mob_level,
    should_be_aggressive,
    TIER_1_ZONES,
    TIER_2_ZONES,
    TIER_3_ZONES,
    TIER_4_ZONES,
    TIER_5_ZONES,
    ROOM_TAG_ZONE_TIER,
    ROOM_TAG_LEVEL_MIN,
    ROOM_TAG_LEVEL_MAX,
    ROOM_TAG_DANGER,
)


class TestZoneTierLookups(TestCase):
    """Verify every zone resolves to the correct tier and level range."""

    def test_tier_1_zones(self):
        for zone in TIER_1_ZONES:
            info = get_zone_tier_for_name(zone)
            self.assertIsNotNone(info, f"Zone '{zone}' not found in tier map")
            tier, lmin, lmax, danger = info
            self.assertEqual(tier, 1, f"{zone}: expected tier 1, got {tier}")
            self.assertEqual(lmin, 1, f"{zone}: expected min level 1, got {lmin}")
            self.assertEqual(lmax, 5, f"{zone}: expected max level 5, got {lmax}")
            self.assertEqual(danger, "safe", f"{zone}: expected danger 'safe', got {danger}")

    def test_tier_2_zones(self):
        for zone in TIER_2_ZONES:
            info = get_zone_tier_for_name(zone)
            self.assertIsNotNone(info, f"Zone '{zone}' not found in tier map")
            tier, lmin, lmax, danger = info
            self.assertEqual(tier, 2, f"{zone}: expected tier 2, got {tier}")
            self.assertEqual(lmin, 6, f"{zone}: expected min level 6, got {lmin}")
            self.assertEqual(lmax, 15, f"{zone}: expected max level 15, got {lmax}")
            self.assertEqual(danger, "caution", f"{zone}: expected danger 'caution', got {danger}")

    def test_tier_3_zones(self):
        for zone in TIER_3_ZONES:
            info = get_zone_tier_for_name(zone)
            self.assertIsNotNone(info, f"Zone '{zone}' not found in tier map")
            tier, lmin, lmax, danger = info
            self.assertEqual(tier, 3, f"{zone}: expected tier 3, got {tier}")
            self.assertEqual(lmin, 16, f"{zone}: expected min level 16, got {lmin}")
            self.assertEqual(lmax, 40, f"{zone}: expected max level 40, got {lmax}")
            self.assertEqual(danger, "danger", f"{zone}: expected danger 'danger', got {danger}")

    def test_tier_4_zones(self):
        for zone in TIER_4_ZONES:
            info = get_zone_tier_for_name(zone)
            self.assertIsNotNone(info, f"Zone '{zone}' not found in tier map")
            tier, lmin, lmax, danger = info
            self.assertEqual(tier, 4, f"{zone}: expected tier 4, got {tier}")
            self.assertEqual(lmin, 41, f"{zone}: expected min level 41, got {lmin}")
            self.assertEqual(lmax, 60, f"{zone}: expected max level 60, got {lmax}")
            self.assertEqual(danger, "deadly", f"{zone}: expected danger 'deadly', got {danger}")

    def test_tier_5_zones(self):
        for zone in TIER_5_ZONES:
            info = get_zone_tier_for_name(zone)
            self.assertIsNotNone(info, f"Zone '{zone}' not found in tier map")
            tier, lmin, lmax, danger = info
            self.assertEqual(tier, 5, f"{zone}: expected tier 5, got {tier}")
            self.assertEqual(lmin, 61, f"{zone}: expected min level 61, got {lmin}")
            self.assertEqual(lmax, 80, f"{zone}: expected max level 80, got {lmax}")
            self.assertEqual(danger, "deadly", f"{zone}: expected danger 'deadly', got {danger}")

    def test_zone_name_with_coordinates(self):
        """Ensure zone names with (x,y) coordinates still resolve correctly."""
        info = get_zone_tier_for_name("Rolling Plains of Aethelgard (5,10)")
        self.assertIsNotNone(info)
        self.assertEqual(info[0], 1)

        info = get_zone_tier_for_name("Dusk Coast (37,2)")
        self.assertIsNotNone(info)
        self.assertEqual(info[0], 5)

        info = get_zone_tier_for_name("Scorched Dunes (99,1)")
        self.assertIsNotNone(info)
        self.assertEqual(info[0], 3)

    def test_unknown_zone_returns_none(self):
        """Unknown zone names return None."""
        self.assertIsNone(get_zone_tier_for_name("Nonexistent Zone"))
        self.assertIsNone(get_zone_tier_for_name(""))

    def test_convenience_functions(self):
        """get_zone_level_range and get_danger_level return expected values."""
        lmin, lmax = get_zone_level_range("Emerald Forest")
        self.assertEqual(lmin, 6)
        self.assertEqual(lmax, 15)

        danger = get_danger_level("Emerald Forest")
        self.assertEqual(danger, "caution")

        # Fallback for unknown zone
        lmin2, lmax2 = get_zone_level_range("Nowhere")
        self.assertEqual(lmin2, 1)
        self.assertEqual(lmax2, 5)

        danger2 = get_danger_level("Nowhere")
        self.assertEqual(danger2, "safe")


class TestMobLevelScaling(TestCase):
    """Verify mob level scaling maps base levels into tier ranges."""

    def test_tier_1_scaling_no_change(self):
        """Tier 1: base levels 1-5 stay in range."""
        self.assertEqual(scale_mob_level(1, 1), 1)
        self.assertEqual(scale_mob_level(3, 1), 3)
        self.assertEqual(scale_mob_level(5, 1), 5)

    def test_tier_2_scaling_offset_5(self):
        """Tier 2: base level + 5, clamped to 6-15."""
        self.assertEqual(scale_mob_level(1, 2), 6)
        self.assertEqual(scale_mob_level(5, 2), 10)
        self.assertEqual(scale_mob_level(12, 2), 15)  # clamped

    def test_tier_3_scaling_offset_15(self):
        """Tier 3: base level + 15, clamped to 16-40."""
        self.assertEqual(scale_mob_level(1, 3), 16)
        self.assertEqual(scale_mob_level(10, 3), 25)
        self.assertEqual(scale_mob_level(30, 3), 40)  # clamped

    def test_tier_4_scaling_offset_40(self):
        """Tier 4: base level + 40, clamped to 41-60."""
        self.assertEqual(scale_mob_level(1, 4), 41)
        self.assertEqual(scale_mob_level(10, 4), 50)
        self.assertEqual(scale_mob_level(25, 4), 60)  # clamped

    def test_tier_5_scaling_offset_60(self):
        """Tier 5: base level + 60, clamped to 61-80."""
        self.assertEqual(scale_mob_level(1, 5), 61)
        self.assertEqual(scale_mob_level(10, 5), 70)
        self.assertEqual(scale_mob_level(30, 5), 80)  # clamped

    def test_scaling_clamps_at_bounds(self):
        """Verify clamping for all tiers."""
        self.assertEqual(scale_mob_level(0, 1), 1)   # low clamp tier 1
        self.assertEqual(scale_mob_level(99, 1), 5)   # high clamp tier 1
        self.assertEqual(scale_mob_level(99, 5), 80)  # high clamp tier 5
        self.assertEqual(scale_mob_level(0, 5), 61)   # low clamp tier 5


class TestAggressionBehavior(TestCase):
    """Verify aggression rules per tier."""

    def test_tier_1_never_aggressive(self):
        """Safe zones: all mobs are passive regardless of base_aggro."""
        self.assertFalse(should_be_aggressive(1, False))
        self.assertFalse(should_be_aggressive(1, True))

    def test_tier_2_respects_base_aggro(self):
        """Caution zones: aggression matches the base template flag."""
        self.assertFalse(should_be_aggressive(2, False))
        self.assertTrue(should_be_aggressive(2, True))

    def test_tier_3_always_aggressive(self):
        """Danger zones: all mobs are aggressive."""
        self.assertTrue(should_be_aggressive(3, False))
        self.assertTrue(should_be_aggressive(3, True))

    def test_tier_4_always_aggressive(self):
        """Deadly zones: always aggressive."""
        self.assertTrue(should_be_aggressive(4, False))
        self.assertTrue(should_be_aggressive(4, True))

    def test_tier_5_always_aggressive(self):
        """End-game zones: always aggressive."""
        self.assertTrue(should_be_aggressive(5, False))
        self.assertTrue(should_be_aggressive(5, True))

    def test_unknown_tier_defaults_aggressive(self):
        """Tier 6+ (unknown) should be treated as dangerous — aggressive."""
        self.assertTrue(should_be_aggressive(6, False))
        self.assertTrue(should_be_aggressive(99, False))


class TestTagConstants(TestCase):
    """Verify tag constants are consistent strings."""

    def test_tag_constant_values(self):
        self.assertEqual(ROOM_TAG_ZONE_TIER, "zone_tier")
        self.assertEqual(ROOM_TAG_LEVEL_MIN, "zone_level_min")
        self.assertEqual(ROOM_TAG_LEVEL_MAX, "zone_level_max")
        self.assertEqual(ROOM_TAG_DANGER, "zone_danger")