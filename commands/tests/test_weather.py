"""
Unit tests for the weather system and coin drop/take commands.

Covers:
  - Climate detection from room names
  - pick_weather() always returns a valid state
  - Indoor/safe-zone weather exemption
  - format_weather_line() / format_weather_short()
  - CmdWeather reporting
  - CmdDropCoins / CmdTakeCoins money transfer
  - Room ground-coin display

Run with:
    evennia test commands.tests.test_weather
"""

import random

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.objects.objects import DefaultRoom, DefaultCharacter
from evennia import create_object


class TestWeatherEngine(BaseEvenniaTest):
    """Test the pure weather-engine logic."""

    def test_climate_detection(self):
        from world.weather import get_climate
        self.assertEqual(get_climate("Emerald Forest (5,5)"), "temperate")
        self.assertEqual(get_climate("Scorched Dunes (1,1)"), "desert")
        self.assertEqual(get_climate("Highland Pass"), "cold")
        self.assertEqual(get_climate("Blackfen Marsh"), "wet")
        self.assertEqual(get_climate("Unknown Zone"), "temperate")

    def test_pick_weather_returns_valid_state(self):
        from world.weather import pick_weather, WEATHER_STATES
        rng = random.Random(1)
        for _ in range(100):
            state = pick_weather("Emerald Forest", rng)
            self.assertIn(state, WEATHER_STATES)

    def test_is_weather_exempt_safe_zone(self):
        from world.weather import is_weather_exempt
        room = create_object(DefaultRoom, key="Safe Room")
        room.db.safe_zone = True
        self.assertTrue(is_weather_exempt(room))
        room.delete()

    def test_is_weather_exempt_indoor(self):
        from world.weather import is_weather_exempt
        room = create_object(DefaultRoom, key="Indoor Room")
        room.attributes.add("indoor", True)
        self.assertTrue(is_weather_exempt(room))
        room.delete()

    def test_is_weather_exempt_outdoor(self):
        from world.weather import is_weather_exempt
        room = create_object(DefaultRoom, key="Forest Room")
        self.assertFalse(is_weather_exempt(room))
        room.delete()

    def test_format_weather_line_and_short(self):
        from world.weather import format_weather_line, format_weather_short
        room = create_object(DefaultRoom, key="Emerald Forest")
        line = format_weather_line(room)
        short = format_weather_short(room)
        self.assertIn("The sky is", line)
        self.assertIn("[", short)
        # Non-empty and ANSI-coded.
        self.assertIn("|", short)
        room.delete()


class TestWeatherCommand(BaseEvenniaTest):
    """Test the CmdWeather reporting."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="TestChar")
        self.room = create_object(DefaultRoom, key="Emerald Forest")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()

    def test_weather_ok(self):
        from commands.weather import CmdWeather

        captured = []

        def fake_msg(*args, **kwargs):
            captured.append(args[0] if args else "")

        # Assign as a plain function: calling caller.msg(text) does not
        # auto-bind, so args[0] is the message text itself.
        self.char1.msg = fake_msg

        cmd = CmdWeather()
        cmd.caller = self.char1
        cmd.args = ""
        cmd.func()

        self.assertTrue(captured, "Expected a weather message to be sent")
        self.assertIn("The sky is", captured[0])

    def test_weather_indoor(self):
        from commands.weather import CmdWeather

        captured = []

        def fake_msg(*args, **kwargs):
            captured.append(args[0] if args else "")

        self.char1.msg = fake_msg
        self.room.attributes.add("indoor", True)

        cmd = CmdWeather()
        cmd.caller = self.char1
        cmd.args = ""
        cmd.func()

        self.assertTrue(captured, "Expected an indoor-weather message")
        self.assertIn("indoors", captured[0])


class TestCoinCommands(BaseEvenniaTest):
    """Test coin drop/take and room coin display."""

    def setUp(self):
        super().setUp()
        self.char1 = create_object(DefaultCharacter, key="TestChar")
        self.room = create_object(DefaultRoom, key="Test Room")
        self.char1.location = self.room

    def tearDown(self):
        self.char1.delete()
        self.room.delete()

    def test_drop_coins(self):
        from commands.drop import CmdDropCoins
        self.char1.attributes.add("money", 500)

        cmd = CmdDropCoins()
        cmd.caller = self.char1
        cmd.args = "200"
        cmd.func()

        self.assertEqual(self.char1.attributes.get("money"), 300)
        self.assertEqual(self.room.attributes.get("ground_gold"), 200)

    def test_drop_coins_not_enough(self):
        from commands.drop import CmdDropCoins
        self.char1.attributes.add("money", 50)

        cmd = CmdDropCoins()
        cmd.caller = self.char1
        cmd.args = "200"
        cmd.func()

        self.assertEqual(self.char1.attributes.get("money"), 50)
        self.assertEqual(self.room.attributes.get("ground_gold", 0), 0)

    def test_take_coins(self):
        from commands.drop import CmdTakeCoins
        self.room.attributes.add("ground_gold", 200)

        cmd = CmdTakeCoins()
        cmd.caller = self.char1
        cmd.args = "150"
        cmd.func()

        self.assertEqual(self.room.attributes.get("ground_gold"), 50)
        self.assertEqual(self.char1.attributes.get("money"), 150)

    def test_take_coins_all(self):
        from commands.drop import CmdTakeCoins
        self.room.attributes.add("ground_gold", 200)

        cmd = CmdTakeCoins()
        cmd.caller = self.char1
        cmd.args = "all"
        cmd.func()

        self.assertEqual(self.room.attributes.get("ground_gold"), 0)
        self.assertEqual(self.char1.attributes.get("money"), 200)

    def test_room_ground_coin_display(self):
        from typeclasses.rooms import Room
        room = create_object(Room, key="Coin Room")
        room.attributes.add("ground_gold", 45)
        try:
            self.assertEqual(room._get_ground_coins(), "45 gold")
        finally:
            room.delete()
