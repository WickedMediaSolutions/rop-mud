"""
Numbered Broadcast Channels (bc) for 'rop'

Provides:
  bc <channel_number>       -- Tune into a specific broadcast channel.
  bc <message>              -- Send a message to everyone on your channel.
  bc leave  /  bc off       -- Leave your current broadcast channel.

Broadcast channels are cross-faction — anyone on the same channel number
can read and reply, regardless of alignment.
"""

from commands.command import Command


class CmdBc(Command):
    """
    Tune into or broadcast on a numbered radio-style channel.

    Usage:
      bc <channel_number>       -- Tune into channel <number> (e.g. bc 21)
      bc <message>              -- Broadcast a message to your current channel
      bc leave  /  bc off       -- Leave your current broadcast channel

    Messages are displayed as:
      |c[BC 21]|n Player: Hey everyone on 21!

    Anyone on the same channel number can read and reply, regardless of
    faction alignment.
    """

    key = "bc"
    aliases = []
    help_category = "Communication"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        args = self.args.strip() if self.args else ""

        if not args:
            self._show_usage(caller)
            return

        # --- "leave" or "off" subcommand ---
        if args.lower() in ("leave", "off"):
            self._leave_channel(caller)
            return

        # --- If args is purely numeric, treat as channel tune-in ---
        if self._is_channel_number(args):
            self._tune_channel(caller, args)
            return

        # --- Leading number followed by message: tune first, then send ---
        #     e.g. "bc 21 Hello everyone" — tune to 21 AND send "Hello everyone"
        parts = args.split(None, 1)
        if self._is_channel_number(parts[0]) and len(parts) > 1:
            channel = parts[0]
            message = parts[1]
            self._tune_channel(caller, channel)
            self._broadcast(caller, message)
            return

        # --- Everything else: treat as a broadcast message ---
        current_channel = caller.attributes.get("bc_channel", default=None)
        if current_channel is None:
            caller.msg(
                "|yYou are not tuned into any broadcast channel.|n\n"
                "|yUsage: bc <channel_number> to tune in first (e.g. |wbc 21|y)|n"
            )
            return

        self._broadcast(caller, args)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_channel_number(self, text):
        """Return True if text is a purely numeric channel number."""
        try:
            int(text)
            return True
        except ValueError:
            return False

    def _show_usage(self, caller):
        """Display usage information."""
        current = caller.attributes.get("bc_channel", default=None)
        if current is not None:
            caller.msg(
                f"|wBroadcast Channel:|n You are currently tuned to |cchannel {current}|n.\n"
                f"|yUsage:|n bc <message> to speak, |ybc leave|n to leave."
            )
        else:
            caller.msg(
                "|wBroadcast Channels:|n\n"
                "|yUsage:|n\n"
                "  |wbc <number>|n    — Tune into a channel (e.g. |wb|w|c 21|n)\n"
                "  |wbc <message>|n   — Broadcast a message to your channel\n"
                "  |wbc leave|n       — Leave your current channel"
            )

    def _tune_channel(self, caller, raw_number):
        """Tune the caller into a specific broadcast channel."""
        try:
            channel = int(raw_number)
        except ValueError:
            caller.msg("|yThat is not a valid channel number.|n")
            return

        if channel < 1:
            caller.msg("|yChannel number must be 1 or higher.|n")
            return

        old_channel = caller.attributes.get("bc_channel", default=None)
        caller.attributes.add("bc_channel", channel)

        if old_channel == channel:
            caller.msg(
                f"|gYou are already tuned into |c[BC {channel}]|g.|n\n"
                f"|yUse |wbc <message>|y to speak on this channel.|n"
            )
        elif old_channel is not None:
            caller.msg(
                f"|gYou switch from |c[BC {old_channel}]|g to |c[BC {channel}]|g.|n"
            )
        else:
            caller.msg(
                f"|gYou tune into |c[BC {channel}]|g.|n\n"
                f"|yUse |wbc <message>|y to speak, |wbc leave|y to leave.|n"
            )

    def _leave_channel(self, caller):
        """Remove the caller from their current broadcast channel."""
        current = caller.attributes.get("bc_channel", default=None)
        if current is None:
            caller.msg("|yYou are not tuned into any broadcast channel.|n")
            return

        caller.attributes.add("bc_channel", None)
        caller.msg(f"|rYou leave |c[BC {current}]|r.|n")

    def _broadcast(self, caller, message):
        """Send a message to all online players on the same BC channel."""
        channel = caller.attributes.get("bc_channel", default=None)
        if channel is None:
            caller.msg("|yYou are not tuned into any broadcast channel.|n")
            return

        from evennia.objects.objects import DefaultCharacter

        formatted = f"|c[BC {channel}]|n {caller.key}: {message}"
        sender_feedback = f"|c[BC {channel}]|n You say: {message}"

        recipients = 0
        all_chars = DefaultCharacter.objects.all_family()
        for char in all_chars:
            char_channel = char.attributes.get("bc_channel", default=None)
            if char_channel is not None and int(char_channel) == int(channel):
                if char == caller:
                    char.msg(sender_feedback)
                else:
                    char.msg(formatted)
                recipients += 1

        # If no other recipients were found (just the sender), inform them
        if recipients <= 1:
            caller.msg("|y(No one else is currently on this channel.)|n")


# Alias for test compatibility
CmdBroadcast = CmdBc
