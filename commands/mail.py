"""
Mail / Messaging System for 'rop'

Provides:
  mail send <player> <subject>  - Send a message to another player
  mail read [number]            - Read your mail (latest or specific)
  mail list                     - List all mail in your inbox
  mail delete <number>          - Delete a message
  mail reply <number> <message> - Reply to a message

Mail is stored as a list of dicts on the recipient's character.
Messages persist across logins. Offline delivery is supported.
"""

from commands.command import Command
from evennia.objects.objects import DefaultCharacter
import time


# ---------------------------------------------------------------------------
# MAIL DATA STRUCTURE
# ---------------------------------------------------------------------------
# Each mail message is a dict:
# {
#     "id": int (1-based index in inbox),
#     "sender": str,
#     "recipient": str,
#     "subject": str,
#     "body": str,
#     "timestamp": float (epoch),
#     "read": bool,
# }
# Stored as character.attributes.get("mail_inbox", default=[])
# ---------------------------------------------------------------------------


def get_inbox(character):
    """Return the character's mail inbox list."""
    inbox = character.attributes.get("mail_inbox", default=None)
    if inbox is None:
        return []
    if isinstance(inbox, list):
        return inbox
    return []


def set_inbox(character, inbox):
    """Save the character's mail inbox."""
    character.attributes.add("mail_inbox", inbox)


def get_unread_count(character):
    """Return the number of unread messages."""
    inbox = get_inbox(character)
    return sum(1 for msg in inbox if not msg.get("read", False))


def find_player_character(name):
    """Find a player character by name (case-insensitive)."""
    for char in DefaultCharacter.objects.all():
        if char.key.lower() == name.lower():
            if hasattr(char, 'has_account') and char.has_account:
                return char
    return None


def format_timestamp(ts):
    """Format a Unix timestamp into a human-readable string."""
    from datetime import datetime
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d %H:%M")


def deliver_mail(sender_name, recipient_name, subject, body):
    """
    Deliver a mail message to a recipient's inbox.
    Returns (success: bool, message: str).
    """
    recipient = find_player_character(recipient_name)
    if not recipient:
        return False, f"No player named '{recipient_name}' found."

    inbox = get_inbox(recipient)
    msg_id = len(inbox) + 1

    message = {
        "id": msg_id,
        "sender": sender_name,
        "recipient": recipient_name,
        "subject": subject,
        "body": body,
        "timestamp": time.time(),
        "read": False,
    }
    inbox.append(message)
    set_inbox(recipient, inbox)

    # Notify recipient if online
    if hasattr(recipient, 'sessions') and recipient.sessions.count() > 0:
        recipient.msg(
            f"|g[Mail] You have a new message from |w{sender_name}|g!|n\n"
            f"|wUse |ymail read|w to read it.|n"
        )

    return True, f"Message sent to {recipient_name}."


# ---------------------------------------------------------------------------
# COMMANDS
# ---------------------------------------------------------------------------

class CmdMailSend(Command):
    """
    Send a mail message to another player.

    Usage:
      mail send <player> = <subject> / <message>

    The message will be delivered immediately. If the recipient is
    offline, they will see it when they next log in.

    Example:
      mail send Thrain = Hello / Just checking in!
    """

    key = "mailsend"
    aliases = []
    help_category = "Communication"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg(
                "|yUsage: mail send <player> = <subject> / <message>|n\n"
                "|wExample: mail send Thrain = Hello / How are you?|n"
            )
            return

        # Parse: player = subject / body
        # Split on first '='
        if '=' not in self.args:
            caller.msg(
                "|yUsage: mail send <player> = <subject> / <message>|n\n"
                "|wUse '=' to separate player from subject/message.|n"
            )
            return

        player_part, rest = self.args.split('=', 1)
        player_name = player_part.strip()
        rest = rest.strip()

        if not player_name:
            caller.msg("|yYou must specify a recipient.|n")
            return

        if player_name.lower() == caller.key.lower():
            caller.msg("|rYou cannot send mail to yourself.|n")
            return

        # Check if sender is ignoring recipient (shouldn't block mail sending,
        # but we check if recipient is ignoring sender)
        recipient = find_player_character(player_name)
        if not recipient:
            caller.msg(f"|rNo player named '{player_name}' found.|n")
            return

        # Check if recipient is ignoring sender
        try:
            from commands.social import is_ignoring
            if is_ignoring(recipient, caller.key):
                caller.msg(f"|r{player_name} is not accepting messages from you.|n")
                return
        except ImportError:
            pass

        # Parse subject and body
        if '/' in rest:
            subject, body = rest.split('/', 1)
            subject = subject.strip()
            body = body.strip()
        else:
            subject = rest[:50] if len(rest) > 50 else rest
            body = rest

        if not subject:
            subject = "(No subject)"

        if not body:
            body = "(No message)"

        # Truncate long subjects
        if len(subject) > 60:
            subject = subject[:57] + "..."

        success, msg = deliver_mail(caller.key, player_name, subject, body)
        if success:
            caller.msg(f"|g{msg}|n")
            caller.msg(f"|wSubject: |n{subject}")
            caller.msg(f"|wMessage: |n{body}")
        else:
            caller.msg(f"|r{msg}|n")


class CmdMailRead(Command):
    """
    Read a mail message from your inbox.

    Usage:
      mail read [number]

    If no number is given, reads the most recent unread message.
    Otherwise reads the message with the given number.
    """

    key = "mailread"
    aliases = []
    help_category = "Communication"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller
        inbox = get_inbox(caller)

        if not inbox:
            caller.msg("|yYour inbox is empty.|n")
            return

        msg_num = None
        if self.args:
            try:
                msg_num = int(self.args)
            except ValueError:
                caller.msg("|yUsage: mail read [number] — number must be a positive integer.|n")
                return

        if msg_num is not None:
            # Find message by ID
            msg = None
            for m in inbox:
                if m["id"] == msg_num:
                    msg = m
                    break
            if not msg:
                caller.msg(f"|rNo message #{msg_num} in your inbox.|n")
                return
        else:
            # Find most recent unread
            unread = [m for m in inbox if not m.get("read", False)]
            if unread:
                msg = unread[-1]  # Most recent unread
            else:
                msg = inbox[-1]  # Most recent overall

        # Display the message
        lines = []
        lines.append("|Y|h" + "=" * 60 + "|n")
        lines.append(f"|wMessage #{msg['id']}|n")
        lines.append(f"|cFrom:|n    |w{msg['sender']}|n")
        lines.append(f"|cTo:|n      |w{msg['recipient']}|n")
        lines.append(f"|cDate:|n    |w{format_timestamp(msg['timestamp'])}|n")
        lines.append(f"|cSubject:|n |w{msg['subject']}|n")
        lines.append("|Y" + "-" * 60 + "|n")
        lines.append(msg["body"])
        lines.append("|Y|h" + "=" * 60 + "|n")

        caller.msg("\n".join(lines))

        # Mark as read
        msg["read"] = True
        set_inbox(caller, inbox)


class CmdMailList(Command):
    """
    List all messages in your inbox.

    Usage:
      mail list
      mail

    Shows message number, sender, subject, date, and read status.
    """

    key = "maillist"
    aliases = []
    help_category = "Communication"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        inbox = get_inbox(caller)

        if not inbox:
            caller.msg("|yYour inbox is empty.|n")
            return

        lines = []
        lines.append("|Y|h" + "=" * 65 + "|n")
        lines.append("|w|h  Mail Inbox|n")
        lines.append("|Y|h" + "=" * 65 + "|n")
        lines.append("")
        lines.append(f"|w{'#':>3}  {'Status':<6} {'From':<16} {'Subject':<25} {'Date':<12}|n")
        lines.append("|Y" + "-" * 65 + "|n")

        for msg in inbox:
            status = "|gNEW|n" if not msg.get("read", False) else "|yread|n"
            sender = msg["sender"][:15]
            subject = msg["subject"][:24]
            date_str = format_timestamp(msg["timestamp"])[:11]

            lines.append(
                f"|w{msg['id']:>3}|n  {status:<6} |w{sender:<16}|n "
                f"{subject:<25} {date_str:<12}"
            )

        lines.append("")
        lines.append("|Y" + "-" * 65 + "|n")
        unread = get_unread_count(caller)
        lines.append(f"|w{len(inbox)} message(s) — {unread} unread.|n")
        lines.append("|wUse |ymail read <#>|w to read a message.|n")
        caller.msg("\n".join(lines))


class CmdMailDelete(Command):
    """
    Delete a mail message from your inbox.

    Usage:
      mail delete <number>

    Permanently removes the message with the given number.
    """

    key = "maildelete"
    aliases = []
    help_category = "Communication"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("|yUsage: mail delete <number>|n")
            return

        try:
            msg_num = int(self.args)
        except ValueError:
            caller.msg("|yUsage: mail delete <number> — number must be a positive integer.|n")
            return

        inbox = get_inbox(caller)

        # Find and remove the message
        new_inbox = []
        deleted = None
        for msg in inbox:
            if msg["id"] == msg_num:
                deleted = msg
            else:
                new_inbox.append(msg)

        if deleted is None:
            caller.msg(f"|rNo message #{msg_num} in your inbox.|n")
            return

        # Re-index remaining messages
        for i, msg in enumerate(new_inbox, 1):
            msg["id"] = i

        set_inbox(caller, new_inbox)
        caller.msg(f"|gMessage #{msg_num} ('{deleted['subject']}') deleted.|n")


class CmdMailReply(Command):
    """
    Reply to a mail message.

    Usage:
      mail reply <number> = <message>

    Sends a reply to the sender of the specified message.
    """

    key = "mailreply"
    aliases = []
    help_category = "Communication"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg(
                "|yUsage: mail reply <number> = <message>|n\n"
                "|wExample: mail reply 1 = Thanks for the message!|n"
            )
            return

        if '=' not in self.args:
            caller.msg(
                "|yUsage: mail reply <number> = <message>|n\n"
                "|wUse '=' to separate the message number from your reply.|n"
            )
            return

        num_part, body = self.args.split('=', 1)
        num_part = num_part.strip()
        body = body.strip()

        try:
            msg_num = int(num_part)
        except ValueError:
            caller.msg("|yThe message number must be a positive integer.|n")
            return

        if not body:
            caller.msg("|yYou must provide a reply message.|n")
            return

        inbox = get_inbox(caller)

        # Find the original message
        original = None
        for msg in inbox:
            if msg["id"] == msg_num:
                original = msg
                break

        if not original:
            caller.msg(f"|rNo message #{msg_num} in your inbox.|n")
            return

        # Send reply
        subject = f"Re: {original['subject']}"
        success, result_msg = deliver_mail(caller.key, original["sender"], subject, body)

        if success:
            caller.msg(f"|gReply sent to {original['sender']}.|n")
        else:
            caller.msg(f"|r{result_msg}|n")


class CmdMail(Command):
    """
    Main mail command hub.

    Usage:
      mail send <player> = <subject> / <message>  - Send a message
      mail read [number]                           - Read messages
      mail list                                    - List inbox
      mail delete <number>                         - Delete a message
      mail reply <number> = <message>              - Reply to a message
      mail                                         - Show inbox
    """

    key = "mail"
    aliases = []
    help_category = "Communication"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            # Default to showing inbox
            cmd = CmdMailList()
            cmd.caller = caller
            cmd.cmdstring = "mail"
            cmd.args = ""
            cmd.func()
            return

        parts = self.args.split(maxsplit=1)
        subcommand = parts[0].lower()
        sub_args = parts[1] if len(parts) > 1 else ""

        if subcommand in ("send", "s"):
            if not sub_args:
                caller.msg(
                    "|yUsage: mail send <player> = <subject> / <message>|n"
                )
                return
            cmd = CmdMailSend()
            cmd.caller = caller
            cmd.cmdstring = "mail send"
            cmd.args = sub_args
            cmd.func()

        elif subcommand in ("read", "r"):
            cmd = CmdMailRead()
            cmd.caller = caller
            cmd.cmdstring = "mail read"
            cmd.args = sub_args
            cmd.func()

        elif subcommand in ("list", "l", "inbox"):
            cmd = CmdMailList()
            cmd.caller = caller
            cmd.cmdstring = "mail list"
            cmd.args = ""
            cmd.func()

        elif subcommand in ("delete", "del", "d"):
            if not sub_args:
                caller.msg("|yUsage: mail delete <number>|n")
                return
            cmd = CmdMailDelete()
            cmd.caller = caller
            cmd.cmdstring = "mail delete"
            cmd.args = sub_args
            cmd.func()

        elif subcommand in ("reply", "rep", "rpl"):
            if not sub_args:
                caller.msg("|yUsage: mail reply <number> = <message>|n")
                return
            cmd = CmdMailReply()
            cmd.caller = caller
            cmd.cmdstring = "mail reply"
            cmd.args = sub_args
            cmd.func()

        else:
            caller.msg(
                "|yUnknown mail subcommand.|n\n"
                "|wValid: send, read, list, delete, reply|n"
            )