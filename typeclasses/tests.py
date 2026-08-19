"""
Unit tests for typeclasses — movement via CmdMove.

Run with:
    evennia test typeclasses.tests
"""

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultRoom, DefaultExit
from evennia import create_object


class TestCmdMove(BaseEvenniaTest):
    """Test the master CmdMove command for single-letter directional movement."""

    def test_move_west_then_east(self):
        """Moving 'w' through a west exit should change location, then 'e' returns."""
        room_a = create_object(DefaultRoom, key="Room A")
        room_b = create_object(DefaultRoom, key="Room B")
        create_object(DefaultExit, key="west", location=room_a, destination=room_b)
        create_object(DefaultExit, key="east", location=room_b, destination=room_a)

        self.char1.location = room_a

        from commands.movement import CmdMove

        # Move west from A to B
        cmd = CmdMove()
        cmd.caller = self.char1
        cmd.cmdstring = "w"
        cmd.args = ""
        cmd.func()
        self.assertEqual(self.char1.location, room_b,
                         "Moving 'w' should place character in Room B")

        # Move east from B back to A
        cmd = CmdMove()
        cmd.caller = self.char1
        cmd.cmdstring = "e"
        cmd.args = ""
        cmd.func()
        self.assertEqual(self.char1.location, room_a,
                         "Moving 'e' should return character to Room A")

        room_a.delete()
        room_b.delete()