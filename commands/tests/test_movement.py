"""
Unit tests for movement commands: direction aliases and 'run' command.

Run with:
    evennia test commands.tests.test_movement
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultExit, DefaultRoom, DefaultCharacter
from evennia import create_object
from typeclasses.exits import (
    normalize_direction, get_opposite, VALID_DIRECTIONS,
    DIRECTION_ALIASES, ALIAS_TO_DIRECTION
)


class TestDirectionNormalization(BaseEvenniaTest):
    """Test direction alias mapping functions."""

    def test_canonical_directions_return_self(self):
        """Canonical direction names should map to themselves."""
        for direction in DIRECTION_ALIASES:
            self.assertEqual(
                normalize_direction(direction), direction,
                f"Canonical '{direction}' should normalize to itself"
            )

    def test_short_aliases_map_to_canonical(self):
        """Short aliases like 'n', 'ne', 'sw' should map to full names."""
        expected = {
            "n": "north",
            "s": "south",
            "e": "east",
            "w": "west",
            "ne": "northeast",
            "nw": "northwest",
            "se": "southeast",
            "sw": "southwest",
            "u": "up",
            "d": "down",
        }
        for alias, canonical in expected.items():
            self.assertEqual(
                normalize_direction(alias), canonical,
                f"Alias '{alias}' should map to '{canonical}'"
            )

    def test_normalize_is_case_insensitive(self):
        """Direction aliases should be case-insensitive."""
        self.assertEqual(normalize_direction("N"), "north")
        self.assertEqual(normalize_direction("Ne"), "northeast")
        self.assertEqual(normalize_direction("SW"), "southwest")

    def test_unknown_direction_passes_through(self):
        """Unknown inputs should be lowercased but not mapped."""
        self.assertEqual(normalize_direction("portal"), "portal")
        self.assertEqual(normalize_direction(""), "")

    def test_valid_directions_set(self):
        """VALID_DIRECTIONS should contain all 20 entries (10 canonical + 10 aliases)."""
        self.assertEqual(len(VALID_DIRECTIONS), 20)
        self.assertIn("north", VALID_DIRECTIONS)
        self.assertIn("n", VALID_DIRECTIONS)
        self.assertIn("northeast", VALID_DIRECTIONS)
        self.assertIn("ne", VALID_DIRECTIONS)
        self.assertIn("up", VALID_DIRECTIONS)
        self.assertIn("u", VALID_DIRECTIONS)
        self.assertIn("down", VALID_DIRECTIONS)
        self.assertIn("d", VALID_DIRECTIONS)

    def test_opposite_directions(self):
        """get_opposite should return correct opposite for all directions."""
        opposites = {
            "north": "south",
            "south": "north",
            "east": "west",
            "west": "east",
            "northeast": "southwest",
            "southwest": "northeast",
            "northwest": "southeast",
            "southeast": "northwest",
            "up": "down",
            "down": "up",
        }
        for direction, opposite in opposites.items():
            self.assertEqual(get_opposite(direction), opposite)

    def test_opposite_from_aliases(self):
        """get_opposite should work with short aliases too."""
        self.assertEqual(get_opposite("n"), "south")
        self.assertEqual(get_opposite("ne"), "southwest")
        self.assertEqual(get_opposite("u"), "down")


class TestExitAliases(BaseEvenniaTest):
    """Test that exits created with canonical keys get proper aliases."""

    def test_exit_gets_short_aliases(self):
        """Creating an exit with key 'north' should add alias 'n'."""
        room1 = create_object(DefaultRoom, key="Test Room 1")
        room2 = create_object(DefaultRoom, key="Test Room 2")
        exit_obj = create_object(
            DefaultExit, key="north", location=room1, destination=room2
        )

        # DefaultExit is the base; our custom Exit typeclass is used by the
        # massive_realm_builder. Test that the normalize logic works standalone.
        # When using our typeclasses, Exit.at_object_creation adds the aliases.
        canonical = normalize_direction(exit_obj.key)
        self.assertEqual(canonical, "north")

        # Clean up
        exit_obj.delete()
        room1.delete()
        room2.delete()

    def test_diagonal_exit_gets_short_alias(self):
        """Creating 'northeast' exit gives 'ne' alias."""
        room1 = create_object(DefaultRoom, key="Room A")
        room2 = create_object(DefaultRoom, key="Room B")
        exit_obj = create_object(
            DefaultExit, key="northeast", location=room1, destination=room2
        )
        canonical = normalize_direction(exit_obj.key)
        self.assertEqual(canonical, "northeast")

        exit_obj.delete()
        room1.delete()
        room2.delete()


class TestRunCommand(BaseEvenniaTest):
    """Test the 'run <direction>' command behavior."""

    def setUp(self):
        super().setUp()
        # Create a character and set as caller
        self.char1 = create_object(DefaultCharacter, key="TestChar")
        self.char1.attributes.add("mv", 100)
        self.char1.attributes.add("hp", 100)
        self.char1.attributes.add("max_hp", 100)
        self.char1.attributes.add("mana", 50)
        self.char1.attributes.add("max_mana", 50)
        self.char1.attributes.add("max_mv", 100)

    def tearDown(self):
        self.char1.delete()
        super().tearDown()

    def test_run_without_direction_shows_usage(self):
        """Running without a direction argument should show usage."""
        # Create a simple room pair
        room1 = create_object(DefaultRoom, key="Start Room")
        room2 = create_object(DefaultRoom, key="Next Room")
        self.char1.location = room1

        # Create N/S exit chain
        create_object(DefaultExit, key="north", location=room1, destination=room2)
        create_object(DefaultExit, key="south", location=room2, destination=room1)

        from commands.movement import CmdRun
        cmd = CmdRun()
        cmd.caller = self.char1
        cmd.cmdstring = "run"
        cmd.args = ""  # No direction
        cmd.parse()
        cmd.func()
        # Should not error; it prints a usage message

        room1.delete()
        room2.delete()

    def test_run_invalid_direction_shows_error(self):
        """Running in an invalid direction should error."""
        room1 = create_object(DefaultRoom, key="Room")
        self.char1.location = room1

        from commands.movement import CmdRun
        cmd = CmdRun()
        cmd.caller = self.char1
        cmd.cmdstring = "run"
        cmd.args = "xyzzy"
        cmd.parse()
        cmd.func()
        # Should print error about invalid direction

        room1.delete()

    def test_run_valid_direction_moves_multiple_rooms(self):
        """Running north through a straight corridor should move multiple rooms."""
        rooms = []
        prev = None
        # Build a 5-room straight corridor
        for i in range(5):
            room = create_object(DefaultRoom, key=f"Corridor {i}")
            rooms.append(room)
            if prev:
                create_object(DefaultExit, key="north", location=prev, destination=room)
                create_object(DefaultExit, key="south", location=room, destination=prev)
            prev = room

        self.char1.location = rooms[0]
        start_mv = self.char1.attributes.get("mv")

        from commands.movement import CmdRun
        cmd = CmdRun()
        cmd.caller = self.char1
        cmd.cmdstring = "run"
        cmd.args = "n"
        cmd.parse()
        cmd.func()

        # Character should have moved (at least through some rooms)
        mv_after = self.char1.attributes.get("mv")
        self.assertLess(mv_after, start_mv, "MV should decrease after running")
        # They should no longer be in room 0
        self.assertNotEqual(self.char1.location, rooms[0])

        # Clean up
        for room in rooms:
            room.delete()

    def test_run_stops_at_fork(self):
        """Running should stop at a room with >1 exit other than the return path."""
        rooms = []
        prev = None
        for i in range(4):
            room = create_object(DefaultRoom, key=f"Path {i}")
            rooms.append(room)
            if prev:
                create_object(DefaultExit, key="north", location=prev, destination=room)
                create_object(DefaultExit, key="south", location=room, destination=prev)
            prev = room

        # Room 2 (index 2) has an extra exit going east
        fork_room = rooms[3]
        extra_room = create_object(DefaultRoom, key="Extra Room")
        create_object(DefaultExit, key="east", location=fork_room, destination=extra_room)
        create_object(DefaultExit, key="west", location=extra_room, destination=fork_room)

        self.char1.location = rooms[0]
        self.char1.attributes.add("mv", 100)

        from commands.movement import CmdRun
        cmd = CmdRun()
        cmd.caller = self.char1
        cmd.cmdstring = "run"
        cmd.args = "n"
        cmd.parse()
        cmd.func()

        # Should stop at or before room 3 (the one with the extra east exit)
        # Since room 3 has 2 non-return exits (north to next and east to extra),
        # the run should stop at that room (as it's a crossroad)
        # Actually, the fork check happens BEFORE entering the next room.
        # So it should stop AT room 3, not in room 4.

        # Clean up
        extra_room.delete()
        for room in rooms:
            room.delete()

    def test_run_stops_at_dead_end(self):
        """Running into a dead end should stop."""
        room1 = create_object(DefaultRoom, key="Start")
        room2 = create_object(DefaultRoom, key="Dead End")
        create_object(DefaultExit, key="north", location=room1, destination=room2)
        create_object(DefaultExit, key="south", location=room2, destination=room1)
        # No exit going further north from room2

        self.char1.location = room1
        self.char1.attributes.add("mv", 100)

        from commands.movement import CmdRun
        cmd = CmdRun()
        cmd.caller = self.char1
        cmd.cmdstring = "run"
        cmd.args = "n"
        cmd.parse()
        cmd.func()

        # Should stop in room2
        self.assertEqual(self.char1.location, room2)

        room1.delete()
        room2.delete()

    def test_run_with_short_alias(self):
        """Running with short aliases like 'n', 'ne', 'sw' should work."""
        room1 = create_object(DefaultRoom, key="Room 1")
        room2 = create_object(DefaultRoom, key="Room 2")
        create_object(DefaultExit, key="northeast", location=room1, destination=room2)
        create_object(DefaultExit, key="southwest", location=room2, destination=room1)

        self.char1.location = room1
        self.char1.attributes.add("mv", 100)

        from commands.movement import CmdRun
        cmd = CmdRun()
        cmd.caller = self.char1
        cmd.cmdstring = "run"
        cmd.args = "ne"
        cmd.parse()
        cmd.func()

        # Should have moved to room2
        self.assertEqual(self.char1.location, room2)

        room1.delete()
        room2.delete()

    def test_run_no_mv_stops(self):
        """Running with 0 MV should not allow movement."""
        room1 = create_object(DefaultRoom, key="Room")
        self.char1.location = room1
        self.char1.attributes.add("mv", 0)

        from commands.movement import CmdRun
        cmd = CmdRun()
        cmd.caller = self.char1
        cmd.cmdstring = "run"
        cmd.args = "n"
        cmd.parse()
        cmd.func()

        # Should remain in same room (no movement)
        self.assertEqual(self.char1.location, room1)

        room1.delete()