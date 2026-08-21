"""
Custom Unloggedin Commands for 'rop'
"""
from evennia import Command


class CmdUnloggedinLook(Command):
    """Look command for unlogged-in users — re-displays the connection screen."""
    key = "look"
    aliases = ["l", "__unloggedin_look_command"]
    locks = "cmd:all()"

    def func(self):
        # Re-display the connection screen from server/conf/connection_screens.py
        try:
            from server.conf.connection_screens import CONNECTION_SCREEN
            self.caller.msg(CONNECTION_SCREEN)
        except Exception:
            self.caller.msg(
                "|YWelcome to Rites of Passage!|n\n"
                "Use |wconnect <username> <password>|n to log in.\n"
                "Use |wcreate <username> <password>|n to create a new account.\n"
                "Type |whelp|n for more information."
            )


class CmdUnloggedinHelp(Command):
    """Help command for unlogged-in users."""
    key = "help"
    aliases = ["h"]
    locks = "cmd:all()"

    def func(self):
        self.caller.msg("Welcome to the Realm of Power! Use |wconnect <username> <password>|n to log in.")


class UnloggedinCmdSet:
    """Command set for unlogged-in users (test compatibility)."""
    pass
