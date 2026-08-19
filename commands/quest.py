"""
Quest Commands for 'rop'

Provides:
  quest list     - Show quests available from NPCs in the current room
  quest accept <id>  - Accept a quest from an NPC
  quest status   - Show active quest journal
  quest complete <id> - Turn in a completed quest for rewards
  quest abandon <id>  - Abandon an active quest
"""

from commands.command import Command


class CmdQuest(Command):
    """
    Manage quests.

    Usage:
      quest list           - See available quests from NPCs in the room
      quest accept <id>    - Accept a quest
      quest status         - View your active quest journal
      quest complete <id>  - Turn in a completed quest for rewards
      quest abandon <id>   - Abandon an active quest
      quest completed      - List quests you have finished

    Quest types:
      KILL   - Defeat a certain number of enemies
      FETCH  - Collect and deliver specific items
      TALK   - Speak with a specific NPC
    """

    key = "quest"
    aliases = ["quests"]
    help_category = "Adventuring"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        args = self.args.strip() if self.args else ""
        handler = caller.quests

        # Parse subcommand
        parts = args.split(None, 1)
        subcmd = parts[0].lower() if parts else "status"
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            self._cmd_list(caller, handler)
        elif subcmd == "accept":
            self._cmd_accept(caller, handler, subargs)
        elif subcmd == "complete":
            self._cmd_complete(caller, handler, subargs)
        elif subcmd == "abandon":
            self._cmd_abandon(caller, handler, subargs)
        elif subcmd == "completed":
            self._cmd_completed(caller, handler)
        elif subcmd == "status":
            self._cmd_status(caller, handler)
        else:
            caller.msg(
                "|yUsage:|n quest list | accept <id> | status | complete <id> | "
                "abandon <id> | completed|n"
            )

    def _cmd_list(self, caller, handler):
        """Show available quests from NPCs in the room."""
        available = handler.list_available()
        if not available:
            caller.msg("|yNo quests available here. Find an NPC who needs help.|n")
            return

        # Group quests by NPC
        by_npc = {}
        for npc, qdef in available:
            by_npc.setdefault(npc, []).append(qdef)

        lines = ["|w=== Available Quests ===|n"]
        for npc, quests in by_npc.items():
            lines.append(f"|c{npc.key}|n offers:")
            for qdef in quests:
                type_label = qdef.quest_type.upper()
                lines.append(
                    f"  |w[{qdef.id}]|n |y[{type_label}]|n {qdef.name} "
                    f"(Level {qdef.level_required}+)"
                )
                lines.append(f"    {qdef.description}")
                # Show rewards summary
                reward_parts = []
                if qdef.rewards.get("xp"):
                    reward_parts.append(f"{qdef.rewards['xp']} XP")
                if qdef.rewards.get("gold"):
                    reward_parts.append(f"{qdef.rewards['gold']} Gold")
                if qdef.rewards.get("faction"):
                    reward_parts.append(f"Faction: {qdef.rewards['faction']:+d}")
                if reward_parts:
                    lines.append(f"    |yRewards:|n {', '.join(reward_parts)}")
                lines.append("")
        caller.msg("\n".join(lines))

    def _cmd_accept(self, caller, handler, quest_id):
        """Accept a quest by ID."""
        if not quest_id:
            caller.msg("|yUsage: quest accept <id>|n")
            caller.msg("Use |wquest list|n to see available quest IDs.")
            return

        success, message = handler.accept(quest_id.strip())
        if success:
            caller.msg(f"|g{message}|n")
        else:
            caller.msg(f"|r{message}|n")

    def _cmd_status(self, caller, handler):
        """Show active quest journal."""
        text, active = handler.status()
        caller.msg(text)

    def _cmd_complete(self, caller, handler, quest_id):
        """Turn in a completed quest for rewards."""
        if not quest_id:
            caller.msg("|yUsage: quest complete <id>|n")
            return

        success, message = handler.complete(quest_id.strip())
        if success:
            caller.msg(f"|g{message}|n")
        else:
            caller.msg(f"|r{message}|n")

    def _cmd_abandon(self, caller, handler, quest_id):
        """Abandon an active quest."""
        if not quest_id:
            caller.msg("|yUsage: quest abandon <id>|n")
            return

        success, message = handler.abandon(quest_id.strip())
        if success:
            caller.msg(f"|y{message}|n")
        else:
            caller.msg(f"|r{message}|n")

    def _cmd_completed(self, caller, handler):
        """Show completed quests."""
        completed = handler._load_completed()
        if not completed:
            caller.msg("|yYou have not completed any quests yet.|n")
            return

        from world.quests import quest_registry

        lines = ["|w=== Completed Quests ===|n"]
        for qid in sorted(completed):
            qdef = quest_registry.get(qid)
            if qdef:
                lines.append(f"  |g[COMPLETE]|n {qdef.name} ({qdef.quest_type.upper()})")
            else:
                lines.append(f"  |g[COMPLETE]|n {qid} (quest definition removed)")
        caller.msg("\n".join(lines))
