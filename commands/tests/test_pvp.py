"""
Unit tests for PvP mechanics, safe zones, death penalties, and corpses.

Run with:
    evennia test commands.tests.test_pvp
"""

from unittest.mock import patch

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultRoom, DefaultCharacter, DefaultObject
from evennia import create_object


# ---------------------------------------------------------------------------
# Safe Zone Tests
# ---------------------------------------------------------------------------

class TestSafeZones(BaseEvenniaTest):
    """Test that safe zones prevent combat."""

    def setUp(self):
        super().setUp()
        self.safe_room = create_object(DefaultRoom, key="Safe Room")
        self.safe_room.db.safe_zone = True
        self.wild_room = create_object(DefaultRoom, key="Wild Room")
        self.wild_room.db.safe_zone = False

        # Use self.char1 (already puppeted by self.account) as attacker.
        # self.char1 HAS has_account = True via BaseEvenniaTest.
        self.attacker = self.char1
        self.attacker.attributes.add("alignment", "Good")
        self.attacker.attributes.add("stats", {"str": 10, "dex": 10, "con": 10,
                                                "int": 10, "wis": 10, "cha": 10})

        # self.char2 is puppeted by self.account2 and has has_account = True.
        self.target = self.char2
        self.target.attributes.add("alignment", "Evil")
        self.target.attributes.add("stats", {"str": 10, "dex": 10, "con": 10,
                                              "int": 10, "wis": 10, "cha": 10})
        self.target.attributes.add("hp", 100)
        self.target.attributes.add("max_hp", 100)

    def tearDown(self):
        self.safe_room.delete()
        self.wild_room.delete()
        super().tearDown()

    def test_safe_room_flag_default_false(self):
        """New rooms should default to safe_zone = False."""
        room = create_object(DefaultRoom, key="Temp")
        self.assertFalse(room.db.safe_zone)
        room.delete()

    def test_safe_room_flag_on(self):
        """Rooms with safe_zone = True should be detected."""
        self.assertTrue(self.safe_room.db.safe_zone)

    def test_safe_zone_blocks_pvp(self):
        """Combat should be blocked in a safe zone."""
        self.attacker.location = self.safe_room
        self.target.location = self.safe_room
        from world.combat import _is_pvp_allowed
        allowed, reason = _is_pvp_allowed(self.attacker, self.target)
        self.assertFalse(allowed, "PvP should be blocked in a safe zone")
        self.assertIn("safe zone", reason.lower())

    def test_wilderness_allows_pvp_opposing_factions(self):
        """Outside safe zones, opposing-faction PvP is always allowed."""
        self.attacker.location = self.wild_room
        self.target.location = self.wild_room
        from world.combat import _is_pvp_allowed
        allowed, _ = _is_pvp_allowed(self.attacker, self.target)
        self.assertTrue(allowed,
                        "Opposing-faction PvP should be allowed outside safe zones")

    def test_apply_physical_damage_blocked_in_safe_zone(self):
        """apply_physical_damage should return 0 in safe zone."""
        self.attacker.location = self.safe_room
        self.target.location = self.safe_room
        from world.combat import apply_physical_damage
        result = apply_physical_damage(self.attacker, self.target, 50)
        self.assertEqual(result, 0, "No damage should be dealt in safe zone")

    def test_apply_magic_damage_blocked_in_safe_zone(self):
        """apply_magic_damage should return 'Combat prevented.' in safe zone."""
        self.attacker.location = self.safe_room
        self.target.location = self.safe_room
        from world.combat import apply_magic_damage
        result = apply_magic_damage(self.attacker, self.target, 50, "Test Spell")
        self.assertEqual(result, "Combat prevented.")

    def test_safe_zone_lock_function(self):
        """safe_zone() lockfunc should return True for safe rooms."""
        from server.conf.lockfuncs import safe_zone
        self.assertTrue(safe_zone(None, self.safe_room))
        self.assertFalse(safe_zone(None, self.wild_room))


# ---------------------------------------------------------------------------
# PvP Flag Tests (same-faction)
# ---------------------------------------------------------------------------

class TestPvpFlags(BaseEvenniaTest):
    """Test the pvp on/off toggle and same-faction PvP logic."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="Test Arena")
        self.room.db.safe_zone = False

        # Use char1/char2 from BaseEvenniaTest which have accounts
        self.good_a = self.char1
        self.good_a.attributes.add("alignment", "Good")
        self.good_a.attributes.add("stats", {"str": 10, "dex": 10, "con": 10,
                                              "int": 10, "wis": 10, "cha": 10})
        self.good_a.location = self.room

        self.good_b = self.char2
        self.good_b.attributes.add("alignment", "Good")
        self.good_b.attributes.add("stats", {"str": 10, "dex": 10, "con": 10,
                                              "int": 10, "wis": 10, "cha": 10})
        self.good_b.attributes.add("hp", 100)
        self.good_b.attributes.add("max_hp", 100)
        self.good_b.location = self.room

    def tearDown(self):
        self.room.delete()
        super().tearDown()

    def test_pvp_default_off(self):
        """New characters should have PvP disabled by default (None/False)."""
        self.assertFalse(self.good_a.db.pvp_enabled)

    def test_pvp_on_command(self):
        """CmdPvp with 'on' argument should set pvp_enabled to True."""
        from commands.pvp import CmdPvp
        cmd = CmdPvp()
        cmd.caller = self.good_a
        cmd.cmdstring = "pvp"
        cmd.args = "on"
        cmd.func()
        self.assertTrue(self.good_a.db.pvp_enabled)

    def test_pvp_off_command(self):
        """CmdPvp with 'off' argument should set pvp_enabled to False."""
        self.good_a.db.pvp_enabled = True
        from commands.pvp import CmdPvp
        cmd = CmdPvp()
        cmd.caller = self.good_a
        cmd.cmdstring = "pvp"
        cmd.args = "off"
        cmd.func()
        self.assertFalse(self.good_a.db.pvp_enabled)

    def test_pvp_status_command(self):
        """CmdPvp with no args should show current status without error."""
        from commands.pvp import CmdPvp
        cmd = CmdPvp()
        cmd.caller = self.good_a
        cmd.cmdstring = "pvp"
        cmd.args = ""
        cmd.func()
        # Should not raise

    def test_pvp_invalid_arg(self):
        """CmdPvp with invalid args should show usage."""
        from commands.pvp import CmdPvp
        cmd = CmdPvp()
        cmd.caller = self.good_a
        cmd.cmdstring = "pvp"
        cmd.args = "maybe"
        cmd.func()
        # Should not raise

    def test_same_faction_pvp_disabled_by_default(self):
        """Two Good-aligned characters cannot PvP unless both enable it."""
        from world.combat import _is_pvp_allowed
        allowed, reason = _is_pvp_allowed(self.good_a, self.good_b)
        self.assertFalse(allowed, "Same-faction PvP should be blocked "
                                  "when neither has pvp on")
        self.assertIn("PvP disabled", reason)

    def test_same_faction_pvp_attacker_on_target_off(self):
        """When only attacker has PvP on, same-faction PvP still blocked."""
        self.good_a.db.pvp_enabled = True
        from world.combat import _is_pvp_allowed
        allowed, reason = _is_pvp_allowed(self.good_a, self.good_b)
        self.assertFalse(allowed)
        self.assertIn("PvP disabled", reason)

    def test_same_faction_pvp_both_on(self):
        """When both have PvP on, same-faction PvP is allowed."""
        self.good_a.db.pvp_enabled = True
        self.good_b.db.pvp_enabled = True
        from world.combat import _is_pvp_allowed
        allowed, _ = _is_pvp_allowed(self.good_a, self.good_b)
        self.assertTrue(allowed, "Same-faction PvP should be allowed "
                                 "when both have pvp on")

    def test_combat_always_allowed_vs_npc(self):
        """Attacking an NPC (no account) should always be allowed."""
        npc = create_object(DefaultCharacter, key="Goblin")
        npc.location = self.room
        from world.combat import _is_pvp_allowed
        allowed, _ = _is_pvp_allowed(self.good_a, npc)
        self.assertTrue(allowed, "Attacking NPCs should always be allowed")
        npc.delete()


# ---------------------------------------------------------------------------
# Death Penalty & Corpse Tests
# ---------------------------------------------------------------------------

class TestDeathPenalties(BaseEvenniaTest):
    """Test XP loss on death and corpse creation."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="Battlefield")
        self.room.db.safe_zone = False

        self.killer = self.char1
        self.killer.attributes.add("alignment", "Evil")
        self.killer.attributes.add("stats", {"str": 10, "dex": 10, "con": 10,
                                              "int": 10, "wis": 10, "cha": 10})

        self.victim = self.char2
        self.victim.attributes.add("alignment", "Good")
        self.victim.attributes.add("stats", {"str": 10, "dex": 10, "con": 10,
                                              "int": 10, "wis": 10, "cha": 10})
        self.victim.attributes.add("hp", 10)
        self.victim.attributes.add("max_hp", 100)
        self.victim.attributes.add("xp", 5000)
        self.victim.attributes.add("level", 5)
        self.victim.attributes.add("max_mana", 50)
        self.victim.attributes.add("max_mv", 100)
        self.victim.attributes.add("money", 250)
        self.victim.home = self.room  # fallback respawn point
        self.victim.location = self.room
        self.killer.location = self.room

    def tearDown(self):
        # Clean up any corpses that may have been created
        for obj in list(self.room.contents):
            if obj not in (self.killer, self.victim):
                try:
                    obj.delete()
                except Exception:
                    pass
        self.room.delete()
        super().tearDown()

    def test_xp_loss_on_death(self):
        """Death should reduce current XP by DEATH_XP_LOSS_PERCENT (10%)."""
        from world.combat import _handle_defeat, DEATH_XP_LOSS_PERCENT

        original_xp = self.victim.attributes.get("xp", 0)
        expected_loss = int(original_xp * DEATH_XP_LOSS_PERCENT / 100)
        _handle_defeat(self.victim, self.killer)

        new_xp = self.victim.attributes.get("xp", 0)
        self.assertEqual(new_xp, original_xp - expected_loss,
                         f"XP should drop from {original_xp} to "
                         f"{original_xp - expected_loss}, got {new_xp}")

    def test_corpse_created_on_death(self):
        """A corpse should be created at the victim's location on death."""
        from world.combat import _handle_defeat
        _handle_defeat(self.victim, self.killer)

        # The victim moves away, but the corpse stays
        corpses = [obj for obj in self.room.contents
                   if obj.attributes.get("is_corpse")]
        self.assertEqual(len(corpses), 1,
                         "One corpse should be created on death")
        corpse = corpses[0]
        self.assertIn("corpse of", corpse.key.lower())

    def test_corpse_contains_inventory(self):
        """The corpse should hold the victim's inventory items."""
        # Give the victim an item
        sword = create_object(DefaultObject, key="Iron Sword")
        sword.location = self.victim

        from world.combat import _handle_defeat
        _handle_defeat(self.victim, self.killer)

        corpses = [obj for obj in self.room.contents
                   if obj.attributes.get("is_corpse")]
        self.assertEqual(len(corpses), 1)
        corpse = corpses[0]

        corpse_contents = [obj.key for obj in corpse.contents]
        self.assertIn("Iron Sword", corpse_contents)

        # Cleanup
        sword.delete()

    def test_corpse_contains_money(self):
        """The corpse should hold the victim's coins."""
        from world.combat import _handle_defeat
        _handle_defeat(self.victim, self.killer)

        corpses = [obj for obj in self.room.contents
                   if obj.attributes.get("is_corpse")]
        self.assertEqual(len(corpses), 1)
        corpse = corpses[0]
        self.assertEqual(corpse.attributes.get("money"), 250)

    def test_victim_money_zero_after_death(self):
        """Victim should have 0 money after death (transferred to corpse)."""
        from world.combat import _handle_defeat
        _handle_defeat(self.victim, self.killer)
        self.assertEqual(self.victim.attributes.get("money"), 0)

    def test_corpse_owner_id_set(self):
        """Corpse should record the victim's id as owner."""
        from world.combat import _handle_defeat
        victim_id = self.victim.id
        _handle_defeat(self.victim, self.killer)

        corpses = [obj for obj in self.room.contents
                   if obj.attributes.get("is_corpse")]
        self.assertEqual(len(corpses), 1)
        corpse = corpses[0]
        self.assertEqual(corpse.attributes.get("corpse_owner_id"), victim_id)

    def test_corpse_has_owner_timer(self):
        """Corpse should have a created_at timestamp and owner-only timer."""
        from world.combat import _handle_defeat, CORPSE_OWNER_ONLY_SECONDS
        _handle_defeat(self.victim, self.killer)

        corpses = [obj for obj in self.room.contents
                   if obj.attributes.get("is_corpse")]
        self.assertEqual(len(corpses), 1)
        corpse = corpses[0]
        self.assertIsNotNone(corpse.attributes.get("corpse_created_at"))
        self.assertEqual(corpse.attributes.get("corpse_owner_only_seconds"),
                         CORPSE_OWNER_ONLY_SECONDS)

    def test_hp_restored_on_respawn(self):
        """After death and respawn, HP should be restored to max."""
        from world.combat import _handle_defeat
        _handle_defeat(self.victim, self.killer)
        max_hp = self.victim.attributes.get("max_hp", 100)
        current_hp = self.victim.attributes.get("hp", 0)
        self.assertEqual(current_hp, max_hp,
                         "HP should be fully restored on respawn")

    def test_no_xp_loss_when_xp_is_zero(self):
        """If XP is 0, death should not result in negative XP."""
        self.victim.attributes.add("xp", 0)
        from world.combat import _handle_defeat
        _handle_defeat(self.victim, self.killer)
        self.assertEqual(self.victim.attributes.get("xp"), 0)

    def test_create_corpse_no_location(self):
        """create_corpse() should return None if victim has no location."""
        self.victim.location = None
        from world.combat import create_corpse
        corpse = create_corpse(self.victim, self.killer)
        self.assertIsNone(corpse)


# ---------------------------------------------------------------------------
# Corpse Looting Timer Tests
# ---------------------------------------------------------------------------

class TestCorpseLootTimer(BaseEvenniaTest):
    """Test that corpses have proper owner-only looting timers."""

    def setUp(self):
        super().setUp()
        self.room = create_object(DefaultRoom, key="Graveyard")
        self.room.db.safe_zone = False

    def tearDown(self):
        for obj in list(self.room.contents):
            try:
                obj.delete()
            except Exception:
                pass
        self.room.delete()
        super().tearDown()

    def test_corpse_created_at_is_now(self):
        """The corpse creation timestamp should be recent."""
        import time
        from world.combat import create_corpse, CORPSE_OWNER_ONLY_SECONDS

        victim = create_object(DefaultCharacter, key="Fallen")
        killer = create_object(DefaultCharacter, key="Slayer")
        victim.location = self.room

        before = time.time()
        corpse = create_corpse(victim, killer)
        after = time.time()

        self.assertIsNotNone(corpse)
        created_at = corpse.attributes.get("corpse_created_at")
        self.assertGreaterEqual(created_at, before)
        self.assertLessEqual(created_at, after)
        self.assertEqual(corpse.attributes.get("corpse_owner_only_seconds"),
                         CORPSE_OWNER_ONLY_SECONDS)

        corpse.delete()
        victim.delete()
        killer.delete()

    def test_corpse_loot_timer_still_owner_only(self):
        """A fresh corpse should be within its owner-only window."""
        from world.combat import create_corpse, CORPSE_OWNER_ONLY_SECONDS
        import time

        victim = create_object(DefaultCharacter, key="Fallen2")
        killer = create_object(DefaultCharacter, key="Slayer2")
        victim.location = self.room

        corpse = create_corpse(victim, killer)
        created_at = corpse.attributes.get("corpse_created_at")
        elapsed = time.time() - created_at
        self.assertLess(elapsed, CORPSE_OWNER_ONLY_SECONDS,
                        "Fresh corpse should still be owner-only")

        corpse.delete()
        victim.delete()
        killer.delete()

    def test_corpse_not_lootable_by_other_player(self):
        """A non-owner should be blocked from looting during the timer."""
        from world.combat import create_corpse

        owner = create_object(DefaultCharacter, key="Owner")
        stranger = create_object(DefaultCharacter, key="Stranger")
        owner.location = self.room

        # Put an item in the owner's inventory
        ring = create_object(DefaultObject, key="Gold Ring")
        ring.location = owner

        corpse = create_corpse(owner, stranger)
        self.assertIsNotNone(corpse)

        # Verify the corpse exists and contains the ring
        corpse_contents = [obj.key for obj in corpse.contents]
        self.assertIn("Gold Ring", corpse_contents)

        # The stranger should NOT be the owner
        self.assertNotEqual(stranger.id,
                            corpse.attributes.get("corpse_owner_id"))

        ring.delete()
        corpse.delete()
        owner.delete()
        stranger.delete()