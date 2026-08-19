"""
Weather commands for 'rop'.

Commands:
  weather / sky  - Show the current weather in your location.
"""

from commands.command import Command


class CmdWeather(Command):
    """
    Look at the sky and report the current weather.

    Usage:
      weather
      sky

    Shows the sky conditions in your current location.  Indoor rooms and
    safe zones have no weather.
    """

    key = "weather"
    aliases = ["sky", "forecast"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        if caller.location is None:
            caller.msg("|yYou are nowhere at all — there is no sky to read.|n")
            return

        from world.weather import format_weather_line, is_weather_exempt

        if is_weather_exempt(caller.location):
            caller.msg("|WYou are indoors; there is no weather here.|n")
            return

        weather_line = format_weather_line(caller.location)
        if weather_line:
            caller.msg(weather_line)
        else:
            caller.msg("|yThe sky is calm and clear.|n")