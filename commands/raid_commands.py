"""
Raid & Dungeon Commands for 'rop'
==================================
Commands for raid management, dungeon finder, and world events.

Commands:
  raid list              - List available raid templates
  raid create <id>       - Create a new raid instance
  raid join <id>         - Join an existing raid
  raid leave             - Leave current raid
  raid status            - Show raid status
  raid start             - Start the raid encounter

  dungeon queue <role>   - Queue for dungeon finder (tank/dps/healer)
  dungeon leave          - Leave dungeon queue
  dungeon status         - Show dungeon finder status

  event list             - List active world events
  event start <type>     - Start a world event (admin)
  event cancel <id>      - Cancel a world event (admin)

  pet adopt <type> [name] - Adopt a pet
  pet list               - List your pets
  pet active <id>        - Set active pet
  pet release <id>       - Release a pet
  pet rename <id> <name> - Rename a pet
  pet feed               - Feed your active pet
  pet rest               - Rest your active pet
"""

from commands.command import Command


class CmdRaid(Command):
    """
    Manage raid instances for large-scale PvE encounters.

    Usage:
      raid list              - List available raid templates
      raid create <id>       - Create a new raid instance
      raid join <id>         - Join an existing raid
      raid leave             - Leave current raid
      raid status            - Show raid status
      raid start             - Start the raid encounter
    """

    key = "raid"
    aliases = []
    locks = "cmd:all()"
    help_category = "PvE"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        from world.raid_mechanics import raid_manager

        if not args:
            caller.msg("Usage: raid list | create <id> | join <id> | leave | status | start")
            return

        parts = args.split(None, 1)
        subcmd = parts[0]
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            templates = raid_manager.list_raid_templates()
            if not templates:
                caller.msg("No raid templates registered.")
                return
            caller.msg("|Y|hAvailable Raids:|n")
            for t in templates:
                caller.msg(
                    f"  [{t['raid_id']}] {t['name']} - "
                    f"Boss: {t['boss']} (Level {t['level']}) "
                    f"|w[{t['tier'].upper()}]|n"
                )
                caller.msg(
                    f"    Players: {t['min_players']}-{t['max_players']} | "
                    f"Recommended Level: {t['recommended_level']}"
                )

        elif subcmd == "create":
            if not subargs:
                caller.msg("Usage: raid create <raid_id>")
                return
            ok, msg = raid_manager.create_raid(subargs, caller)
            caller.msg(msg)

        elif subcmd == "join":
            if not subargs:
                caller.msg("Usage: raid join <raid_instance_id>")
                return
            ok, msg = raid_manager.join_raid(caller, subargs)
            caller.msg(msg)

        elif subcmd == "leave":
            ok, msg = raid_manager.leave_raid(caller)
            caller.msg(msg)

        elif subcmd == "status":
            raid = raid_manager.get_player_raid(caller)
            if not raid:
                caller.msg("You are not in a raid.")
                # Show available raids
                instances = raid_manager.list_raid_instances()
                if instances:
                    caller.msg("|wForming Raids:|n")
                    for inst in instances:
                        caller.msg(
                            f"  [{inst['raid_id'][:8]}] {inst['name']} - "
                            f"{inst['players']}/{inst['max_players']} players "
                            f"(Leader: {inst['leader']})"
                        )
                return
            caller.msg(f"|Y|hRaid: {raid.raid_name}|n")
            caller.msg(f"  Boss: {raid.boss.name} (Level {raid.boss.level})")
            caller.msg(f"  Status: {raid.status}")
            caller.msg(f"  Players: {raid.player_count}/{raid.max_players}")
            caller.msg(f"  Leader: {raid.leader.key if raid.leader else 'None'}")
            if raid.status == "active":
                caller.msg(f"  Duration: {raid.duration_seconds}s")
                caller.msg(f"  Deaths: {raid.deaths}")

        elif subcmd == "start":
            raid = raid_manager.get_player_raid(caller)
            if not raid:
                caller.msg("You are not in a raid. Create one with 'raid create <id>'.")
                return
            if raid.leader != caller:
                caller.msg("Only the raid leader can start the encounter.")
                return
            ok, msg = raid.start()
            caller.msg(msg)
            if ok:
                # Notify all members
                for member in raid.members:
                    if member != caller:
                        member.msg(f"|Y|h[Raid] {caller.key} has started {raid.raid_name}!|n")

        else:
            caller.msg("Usage: raid list | create <id> | join <id> | leave | status | start")


class CmdDungeonFinder(Command):
    """
    Queue for dungeon groups using the Dungeon Finder.

    Usage:
      dungeon queue <role>   - Queue as tank, dps, or healer
      dungeon leave          - Leave the dungeon queue
      dungeon status         - Show queue status

    The Dungeon Finder automatically forms groups of 1 tank, 3 dps, 1 healer
    and creates a dungeon instance for the group.
    """

    key = "dungeon"
    aliases = ["df", "dungeonfinder"]
    locks = "cmd:all()"
    help_category = "PvE"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        from world.raid_mechanics import raid_manager

        if not args:
            caller.msg("Usage: dungeon queue <role> | leave | status")
            caller.msg("Roles: tank, dps, healer")
            return

        parts = args.split(None, 1)
        subcmd = parts[0]
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "queue":
            if not subargs:
                caller.msg("Usage: dungeon queue <role>  (tank, dps, healer)")
                return
            ok, msg = raid_manager.queue_dungeon(caller, subargs)
            caller.msg(msg)

        elif subcmd == "leave":
            ok, msg = raid_manager.dequeue_dungeon(caller)
            caller.msg(msg)

        elif subcmd == "status":
            status = raid_manager.get_queue_status()
            caller.msg("|Y|hDungeon Finder Queue:|n")
            caller.msg(f"  Tanks: {status['tank']}")
            caller.msg(f"  DPS: {status['dps']}")
            caller.msg(f"  Healers: {status['healer']}")
            caller.msg(f"  Total: {status['total']}")

        else:
            caller.msg("Usage: dungeon queue <role> | leave | status")


class CmdWorldEvent(Command):
    """
    View and manage world events.

    Usage:
      event list              - List active world events
      event start <type>      - Start a world event (admin)
      event cancel <id>       - Cancel a world event (admin)

    Event types: invasion, double_xp, double_gold, holiday, boss_rush
    """

    key = "event"
    aliases = ["events", "worldevent"]
    locks = "cmd:all()"
    help_category = "PvE"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        from world.world_events import world_event_manager

        if not args:
            caller.msg("Usage: event list | start <type> | cancel <id>")
            return

        parts = args.split(None, 1)
        subcmd = parts[0]
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            events = world_event_manager.list_events()
            if not events:
                caller.msg("No world events active or scheduled.")
                return
            caller.msg("|Y|hWorld Events:|n")
            for e in events:
                status_color = "|g" if e["status"] == "active" else "|y"
                caller.msg(
                    f"  [{e['event_id'][:8]}] {e['name']} ({e['type']}) "
                    f"{status_color}{e['status']}|n"
                )
                if e["time_remaining"] is not None:
                    caller.msg(f"    Time remaining: {e['time_remaining']}s")
                if e["xp_multiplier"] != 1.0:
                    caller.msg(f"    XP Multiplier: x{e['xp_multiplier']}")
                if e["gold_multiplier"] != 1.0:
                    caller.msg(f"    Gold Multiplier: x{e['gold_multiplier']}")

        elif subcmd == "start":
            if not subargs:
                caller.msg("Usage: event start <type>  (invasion, double_xp, double_gold, holiday, boss_rush)")
                return
            event, msg = world_event_manager.create_event(subargs)
            if event:
                caller.msg(f"|g{msg}|n")
            else:
                caller.msg(f"|r{msg}|n")

        elif subcmd == "cancel":
            if not subargs:
                caller.msg("Usage: event cancel <event_id>")
                return
            ok, msg = world_event_manager.cancel_event(subargs)
            caller.msg(msg)

        else:
            caller.msg("Usage: event list | start <type> | cancel <id>")


class CmdPet(Command):
    """
    Adopt and manage pets and combat companions.

    Usage:
      pet adopt <type> [name]  - Adopt a new pet
      pet list                 - List your pets
      pet active <id>          - Set which pet is active
      pet release <id>         - Release a pet
      pet rename <id> <name>   - Rename a pet
      pet feed                 - Feed your active pet
      pet rest                 - Rest your active pet to full HP

    Pet types:
      Non-combat: cat, dog, raven, fox, dragon_whelp, will_o_wisp, baby_phoenix
      Combat: wolf_companion, bear_companion, panther_companion, golem_companion, dragon_companion
    """

    key = "pet"
    aliases = ["pets", "companion"]
    locks = "cmd:all()"
    help_category = "PvE"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        from world.pet_system import pet_manager, PET_TYPES

        if not args:
            caller.msg("Usage: pet adopt <type> [name] | list | active <id> | release <id> | rename <id> <name> | feed | rest")
            return

        parts = args.split(None, 2)
        subcmd = parts[0].lower()

        if subcmd == "adopt":
            if len(parts) < 2:
                caller.msg("Available pet types:")
                for ptype, pdata in PET_TYPES.items():
                    caller.msg(
                        f"  {ptype}: {pdata['name']} "
                        f"({pdata['type']}, {pdata['cost']}g, Level {pdata['min_level']}+) "
                        f"[{pdata['rarity'].upper()}]"
                    )
                return
            pet_type = parts[1]
            pet_name = parts[2] if len(parts) > 2 else None
            ok, msg = pet_manager.adopt_pet(caller, pet_type, pet_name)
            caller.msg(msg)

        elif subcmd == "list":
            pets = pet_manager.get_pets(caller)
            if not pets:
                caller.msg("You don't have any pets. Adopt one with 'pet adopt <type>'.")
                return
            active_pet = pet_manager.get_active_pet(caller)
            caller.msg("|Y|hYour Pets:|n")
            for pet in pets:
                active_marker = " |g[ACTIVE]|n" if pet == active_pet else ""
                hp_str = f"HP: {pet.hp}/{pet.max_hp}" if pet.type == "combat" else ""
                caller.msg(
                    f"  [{pet.pet_id[:8]}] {pet.get_display_name()} "
                    f"(Level {pet.level}, Bond {pet.bond_level}){active_marker}"
                )
                if hp_str:
                    caller.msg(f"    {hp_str} | DMG: {pet.damage} | Type: {pet.type}")

        elif subcmd == "active":
            if len(parts) < 2:
                caller.msg("Usage: pet active <pet_id>")
                return
            ok, msg = pet_manager.set_active_pet(caller, parts[1])
            caller.msg(msg)

        elif subcmd == "release":
            if len(parts) < 2:
                caller.msg("Usage: pet release <pet_id>")
                return
            ok, msg = pet_manager.release_pet(caller, parts[1])
            caller.msg(msg)

        elif subcmd == "rename":
            if len(parts) < 3:
                caller.msg("Usage: pet rename <pet_id> <new_name>")
                return
            ok, msg = pet_manager.rename_pet(caller, parts[1], parts[2])
            caller.msg(msg)

        elif subcmd == "feed":
            ok, msg = pet_manager.feed_pet(caller)
            caller.msg(msg)

        elif subcmd == "rest":
            ok, msg = pet_manager.rest_pet(caller)
            caller.msg(msg)

        else:
            caller.msg("Usage: pet adopt <type> [name] | list | active <id> | release <id> | rename <id> <name> | feed | rest")