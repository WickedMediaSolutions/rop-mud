"""
Talk Command for 'rop'

Provides:
  talk <npc>        - Start a conversation with an NPC
  talk <number>     - Choose a dialogue option
  talk end          - End the current conversation
  talk              - Show current conversation status

Integrates with the branching dialogue system in world/quest_dialogue.py.
"""

from commands.command import Command


class CmdTalk(Command):
    """
    Talk to an NPC or continue a conversation.

    Usage:
      talk <npc>        - Start a conversation with an NPC in the room
      talk <number>     - Choose a numbered dialogue option
      talk end          - End the current conversation
      talk              - Show current conversation status

    NPCs with dialogue trees will present branching conversations.
    Your choices may unlock quests, reveal information, or grant rewards.
    """

    key = "talk"
    aliases = ["speak", "converse"]
    help_category = "Adventuring"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        from world.quest_dialogue import (
            dialogue_registry,
            DialogueSession,
        )

        # Check for active dialogue session (non-persistent ndb)
        session = caller.ndb.dialogue_session if hasattr(caller, 'ndb') else None

        if not args:
            # No args: show current conversation status
            if session and session.is_active:
                session.display()
            else:
                caller.msg("|yUsage: talk <npc> | talk <number> | talk end|n")
                caller.msg("|wYou are not currently in a conversation.|n")
            return

        # Handle "end" subcommand
        if args.lower() == "end":
            if session and session.is_active:
                session.end()
                caller.ndb.dialogue_session = None
                caller.msg("|yYou end the conversation.|n")
            else:
                caller.msg("|yYou are not in a conversation.|n")
            return

        # Handle numeric choice
        if args.isdigit():
            choice_num = int(args)
            if not session or not session.is_active:
                caller.msg("|yYou are not in a conversation. Use |wtalk <npc>|y to start one.|n")
                return
            success, msg = session.choose(choice_num)
            if not success:
                caller.msg(f"|r{msg}|n")
            else:
                # Save session state (non-persistent)
                caller.ndb.dialogue_session = session
            return

        # Otherwise, treat args as an NPC name to start a conversation
        npc_name = args

        # Find the NPC in the room
        location = caller.location
        if not location:
            caller.msg("|rYou are nowhere!|n")
            return

        npc = None
        for obj in location.contents:
            if obj != caller and not obj.has_account:
                if obj.key.lower() == npc_name.lower():
                    npc = obj
                    break

        if not npc:
            caller.msg(f"|rThere is no '{npc_name}' here to talk to.|n")
            return

        # Check if NPC has dialogue trees
        trees = dialogue_registry.get_by_npc(npc.key)
        if not trees:
            # Fallback: report talk for quest progress
            try:
                updated = caller.quests.report_talk(npc.key)
                if updated:
                    caller.msg(f"|gYou speak with {npc.key}.|n")
                else:
                    caller.msg(f"|y{npc.key} has nothing to say to you right now.|n")
            except Exception:
                caller.msg(f"|y{npc.key} has nothing to say to you right now.|n")
            return

        # Use the first matching dialogue tree
        tree = trees[0]
        start_node = tree.get_start_node(caller)
        if not start_node:
            caller.msg(f"|y{npc.key} has nothing to say to you right now.|n")
            return

        # Start a new dialogue session (non-persistent ndb)
        session = DialogueSession(caller, tree, start_node)
        caller.ndb.dialogue_session = session
        session.display()
