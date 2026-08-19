"""
General Commands for 'rop'

Provides:
  look self    - examine your own character
  inventory (i) - standard inventory alias
  equipment (eq) - standard equipment alias
  rest         - increase HP and MV regeneration speed
  meditate     - significantly boost MP regeneration (magic users only)
  consider     - estimate odds against a target monster
  recall       - teleport to faction home (level 30+)
  who          - list online players with clan tags
  rules        - display server rules and guidelines
"""

from commands.command import Command
from evennia import search_object
from evennia.accounts.models import AccountDB
from evennia.objects.models import ObjectDB


class CmdLookSelf(Command):
    """
    Examine your own character.

    Usage:
      look self
      look me

    Displays your character's physical description, current health, mana,
    movement points, and any equipped gear.
    """

    key = "lookself"
    aliases = ["look me", "examine self", "ex self"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        char = caller

        # Build the display
        lines = []
        lines.append(f"|w{char.key}|n")
        lines.append("-" * 40)

        # Race & Class
        race = char.attributes.get("race", default="Unknown")
        charclass = char.attributes.get("class", default="Unknown")
        level = char.attributes.get("level", default=1)
        lines.append(f"|cRace:|n {race}   |cClass:|n {charclass}   |cLevel:|n {level}")

        # Stats
        stats = char.attributes.get("stats", default={})
        if stats:
            stat_str = "  ".join(
                f"|c{k.upper()}:|n {v}" for k, v in stats.items()
            )
            lines.append(stat_str)

        # Health / Mana / Movement
        hp = char.attributes.get("hp", default=100)
        max_hp = char.attributes.get("max_hp", default=100)
        mana = char.attributes.get("mana", default=50)
        max_mana = char.attributes.get("max_mana", default=50)
        mv = char.attributes.get("mv", default=100)
        max_mv = char.attributes.get("max_mv", default=100)

        lines.append(f"|rHP:|n {hp}/{max_hp}   |bMana:|n {mana}/{max_mana}   |yMV:|n {mv}/{max_mv}")

        # Alignment & Warpoints
        alignment = char.attributes.get("alignment", default="Neutral")
        warpoints = char.attributes.get("warpoints", default=0)
        lines.append(f"|cAlignment:|n {alignment}   |cWarpoints:|n {warpoints}")

        # Physical description
        desc = char.db.desc
        if desc:
            lines.append("")
            lines.append("|wDescription:|n")
            lines.append(desc)
        else:
            lines.append("")
            lines.append("|wDescription:|n")
            lines.append(f"A {race} {charclass} of level {level}, ready for adventure.")

        # Armor Set Bonuses
        from world.armor_sets import ArmorSetChecker
        checker = ArmorSetChecker(char)
        set_display = checker.format_display()
        if set_display:
            lines.append(set_display.strip())

        # Equipment
        lines.append("")
        lines.append("|wEquipment:|n")
        equipped = char.attributes.get("equipped", default={})
        if equipped:
            for slot, item_name in equipped.items():
                lines.append(f"  |c{slot.capitalize()}:|n {item_name}")
        else:
            lines.append("  |yNothing equipped.|n")

        # Inventory count
        inv = char.contents
        if inv:
            item_count = len([obj for obj in inv if not obj.destination])
            lines.append(f"\n|wInventory:|n {item_count} item(s). Type |wi|n or |winventory|n to see them.")

        caller.msg("\n".join(lines))


class CmdRest(Command):
    """
    Sit down and rest to recover health and movement faster.

    Usage:
      rest

    While resting, your Health (HP) and Movement (MV) points regenerate
    at an accelerated rate.  Resting ends automatically if you move,
    enter combat, or use the command again to stand up.

    Standing regeneration is slow; resting roughly doubles your recovery
    speed for HP and MV.
    """

    key = "rest"
    aliases = ["sit"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        # Check if already resting
        current_pos = caller.attributes.get("position", default="standing")
        if current_pos == "resting":
            caller.attributes.add("position", "standing")
            caller.attributes.add("is_resting", False)
            caller.attributes.add("is_meditating", False)
            caller.msg("|yYou stand up and stretch, ending your rest.|n")
            caller.location.msg_contents(
                f"|y{caller.key} stands up.|n", exclude=caller
            )
            return

        # Cannot rest and meditate simultaneously
        if current_pos == "meditating":
            caller.attributes.add("is_meditating", False)
            caller.msg("|yYou cease meditating and settle down to rest instead.|n")

        caller.attributes.add("position", "resting")
        caller.attributes.add("is_resting", True)
        caller.attributes.add("is_meditating", False)
        caller.msg(
            "|gYou settle down to rest. Your HP and MV will regenerate faster.|n\n"
            "|w(Use |yrest|w again, move, or fight to stand up.)|n"
        )
        caller.location.msg_contents(
            f"|g{caller.key} sits down to rest.|n", exclude=caller
        )


class CmdRent(Command):
    """
    Rent a room at the inn for accelerated recovery.

    Usage:
      rent

    Pay gold to rent a comfortable room. While rented, you gain
    doubled HP/MV/MP regeneration for as long as you stay in the room.
    Cost scales with your level.

    This is an economic gold sink - high-level characters pay more.
    """

    key = "rent"
    aliases = ["rentroom", "inn"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        from world.economy import calculate_inn_cost, get_money, remove_money, format_money_brief

        # Check if already rented
        if caller.attributes.get("has_rented_room", default=False):
            caller.msg("|yYou have already rented a room here. Enjoy your stay!|n")
            return

        cost = calculate_inn_cost(caller)

        if not remove_money(caller, cost):
            carried = get_money(caller)
            caller.msg(
                f"|rYou need {format_money_brief(cost)} to rent a room. "
                f"(You have {format_money_brief(carried)}.)|n"
            )
            return

        # Grant rented bonus via attribute
        caller.attributes.add("has_rented_room", True)
        caller.attributes.add("resting_bonus", 2)  # 2x recovery multi while rested
        caller.attributes.add("position", "resting")
        caller.attributes.add("is_resting", True)
        caller.msg(
            f"|gYou pay |Y{format_money_brief(cost)}|g for a comfortable room.|n\n"
            f"|cYou settle into the rented room. Recovery rates are doubled!|n\n"
            f"|w(Leave the room or type |yrent|w again to end your stay.)|n"
        )

        # Put caller in resting mode
        if caller.location:
            caller.location.msg_contents(
                f"|g{caller.key} rents a room and settles in to rest.|n",
                exclude=[caller],
            )


class CmdMeditate(Command):
    """
    Enter a deep meditative trance to rapidly recover Mana.

    Usage:
      meditate

    Requires a magic-using class (Mage, Cleric, Druid, Warlock,
    Necromancer, or Paladin).  While meditating your Mana (MP)
    regenerates significantly faster than normal.

    Meditation ends automatically if you move, enter combat, or use
    the command again.
    """

    key = "meditate"
    aliases = ["med", "trance"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    # Classes that can meditate
    MAGIC_CLASSES = {"Mage", "Cleric", "Druid", "Warlock", "Necromancer", "Paladin"}

    def func(self):
        caller = self.caller

        charclass = caller.attributes.get("class", default="Unknown")

        # Check if already meditating
        current_pos = caller.attributes.get("position", default="standing")
        if current_pos == "meditating":
            caller.attributes.add("position", "standing")
            caller.attributes.add("is_meditating", False)
            caller.msg("|yYou open your eyes and rise from your meditative trance.|n")
            caller.location.msg_contents(
                f"|y{caller.key} emerges from a deep trance.|n", exclude=caller
            )
            return

        # Check magic class requirement
        if charclass not in self.MAGIC_CLASSES:
            caller.msg(
                "|rYou lack the arcane discipline required to meditate.|n\n"
                "|wOnly magic-using classes (Mage, Cleric, Druid, Warlock, "
                "Necromancer, Paladin) can enter a meditative trance.|n"
            )
            return

        # Cannot meditate and rest simultaneously
        if current_pos == "resting":
            caller.attributes.add("is_resting", False)
            caller.msg("|yYou stop resting and assume a meditative posture instead.|n")

        caller.attributes.add("position", "meditating")
        caller.attributes.add("is_meditating", True)
        caller.attributes.add("is_resting", False)
        caller.msg(
            "|bYou close your eyes and enter a deep meditative trance. "
            "Your Mana will regenerate much faster.|n\n"
            "|w(Use |ymeditate|w again, move, or fight to break the trance.)|n"
        )
        caller.location.msg_contents(
            f"|b{caller.key} settles into a meditative trance.|n", exclude=caller
        )


class CmdConsider(Command):
    """
    Compare your strength against a target monster.

    Usage:
      consider <target>
      con <target>

    Evaluates your level and stats relative to the target and returns
    a color-coded estimate of your odds in a fight:

      |gGreen  |n- Easy target, you should win handily.
      |YYellow |n- A fair fight; be prepared.
      |rRed    |n- Dangerous; you would likely die.

    The estimate accounts for level difference and relative stat totals.
    """

    key = "consider"
    aliases = ["con"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.target_name = self.args.strip() if self.args else ""

    def func(self):
        caller = self.caller

        if not self.target_name:
            caller.msg("|yUsage: consider <target>  (e.g. consider goblin)|n")
            return

        # Search for the target in the current room
        target_list = caller.search(
            self.target_name,
            candidates=caller.location.contents,
            quiet=True,
        )

        if not target_list or len(target_list) == 0:
            caller.msg(f"|rYou don't see '{self.target_name}' here.|n")
            return

        target = target_list[0]

        # Only consider NPCs / monsters
        if target == caller:
            caller.msg("|yYou size yourself up. You'd probably win... and lose.|n")
            return

        if hasattr(target, 'is_pc') and target.is_pc:
            caller.msg(
                f"|y{target.key} is another adventurer. "
                f"Only they know their true strength.|n"
            )
            return

        # Gather player stats
        player_level = caller.attributes.get("level", default=1)
        player_stats = caller.attributes.get("stats", default={})
        player_stat_total = sum(player_stats.values()) if player_stats else 0

        # Gather target stats
        target_level = target.attributes.get("level", default=1)
        target_stats = target.attributes.get("stats", default={})
        target_stat_total = sum(target_stats.values()) if target_stats else 0

        # Calculate level difference
        level_diff = player_level - target_level

        # Calculate stat ratio (player total / target total)
        if target_stat_total > 0:
            stat_ratio = player_stat_total / target_stat_total
        else:
            stat_ratio = 2.0  # Assume player is stronger if target has no stats

        # Determine difficulty
        # Easy: player is 5+ levels above OR stat ratio >= 1.5
        # Fair: level diff between -4 and +4 OR stat ratio between 0.7 and 1.5
        # Deadly: player is 5+ levels below OR stat ratio < 0.7
        if level_diff >= 5 or stat_ratio >= 1.5:
            difficulty = "easy"
        elif level_diff <= -5 or stat_ratio < 0.7:
            difficulty = "deadly"
        else:
            difficulty = "fair"

        # Build response messages
        messages = {
            "easy": (
                f"|gYou consider {target.key} carefully...|n\n"
                f"|gAn easy target. You should have no trouble at all.|n"
            ),
            "fair": (
                f"|YYou consider {target.key} carefully...|n\n"
                f"|YLooks like a fair fight. Stay on your guard.|n"
            ),
            "deadly": (
                f"|rYou consider {target.key} carefully...|n\n"
                f"|rYou would surely die. Flee while you still can!|n"
            ),
        }

        caller.msg(messages[difficulty])


class CmdPrompt(Command):
    """
    Toggle the MajorMUD-style status prompt on or off.

    Usage:
      prompt

    By default, all players see a colour-coded status line showing
    [HP / MP / MV / EXP] at the bottom of the screen after every
    command.  Use this command to hide or restore that prompt.

    When toggled ON you will immediately see the current status line.
    When toggled OFF the prompt line will be suppressed until you
    use |yprompt|n again.
    """

    key = "prompt"
    aliases = ["statusbar", "stbar"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        current = caller.attributes.get("prompt_enabled", default=True)

        if current:
            caller.attributes.add("prompt_enabled", False)
            caller.msg("|yStatus prompt is now |rOFF|y.|n")
            caller.msg("|w(Use |yprompt|w again to re-enable it.)|n")
        else:
            caller.attributes.add("prompt_enabled", True)
            caller.msg("|yStatus prompt is now |gON|y.|n")
            # Show the prompt immediately so the player sees the effect.
            caller.msg(prompt=caller.get_status_prompt())


class CmdRecall(Command):
    """
    Instantly teleport back to your faction's home starting room.

    Usage:
      recall

    Requires level 30 or higher.  When invoked, you are immediately
    transported to your faction's home:

      Good-aligned characters  -> Aethelgard - The Grand Sanctum
      Evil-aligned characters  -> Gorgoroth - The Blood Forge

    This ability has no mana or movement cost and can be used from
    anywhere in the realm.
    """

    key = "recall"
    aliases = ["return", "gate"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    # Home room search keys by alignment
    HOME_ROOMS = {
        "Good": "Aethelgard - The Grand Sanctum",
        "Evil": "Gorgoroth - The Blood Forge",
    }

    def func(self):
        caller = self.caller

        # Level check
        level = caller.attributes.get("level", default=1)
        if level < 30:
            caller.msg(
                "|rYou lack the spiritual fortitude to recall.|n\n"
                f"|wRecall becomes available at level 30. "
                f"You are currently level {level}.|n"
            )
            return

        # Determine faction home
        alignment = caller.attributes.get("alignment", default="Good")
        home_key = self.HOME_ROOMS.get(alignment)

        if not home_key:
            caller.msg("|rYour alignment is unknown. You cannot recall.|n")
            return

        # Search for the home room
        from evennia import search_object
        home_rooms = search_object(home_key)

        if not home_rooms or len(home_rooms) == 0:
            caller.msg(
                "|rThe mystical link to your home has been severed.|n\n"
                "|wContact an administrator — the recall destination "
                "could not be found.|n"
            )
            return

        home = home_rooms[0]

        # Prevent recalling if already there
        if caller.location == home:
            caller.msg("|yYou are already at your faction home.|n")
            return

        # Perform the recall
        caller.msg(
            "|bYou close your eyes and focus your will...|n\n"
            "|gA warm light envelops you, and when it fades, "
            f"you find yourself standing in |w{home.key}|g.|n"
        )
        caller.location.msg_contents(
            f"|b{caller.key} is surrounded by a brilliant light and vanishes!|n",
            exclude=caller,
        )
        caller.move_to(home)
        home.msg_contents(
            f"|bA brilliant light coalesces as {caller.key} appears from nowhere.|n",
            exclude=caller,
        )
        caller.msg(home.return_appearance(caller))


class CmdWho(Command):
    """
    Show all currently online player characters with their clan tags.

    Usage:
      who

    Displays a formatted list of all online adventurers, sorted by level
    (highest first).  Each entry shows the player's name, race, class,
    level, alignment, and active clan.

    Clan tags appear in the clan's faction color (green for Good clans,
    red for Evil clans).
    """

    key = "who"
    aliases = ["who", "players"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    # Valid filter keywords for faction/alignment
    ALIGN_FILTERS = {
        "good": "Good",
        "evil": "Evil",
        "neutral": "Neutral",
    }

    def parse(self):
        self.filter_args = (self.args or "").strip().lower()

    def func(self):
        caller = self.caller

        # Gather all online player characters
        from typeclasses.characters import Character

        online_chars = []
        for char in ObjectDB.objects.all():
            if not hasattr(char, 'sessions') or char.sessions.count() == 0:
                continue
            # Only include Character instances
            if not isinstance(char, Character):
                continue
            online_chars.append(char)

        if not online_chars:
            caller.msg("|yNo adventurers are currently roaming the realm.|n")
            return

        # ---- Phase 6.9 — Filtering ----
        filter_tokens = self.filter_args.split() if self.filter_args else []
        align_filter = None
        level_filter = None
        class_filter = None

        for token in filter_tokens:
            if token in self.ALIGN_FILTERS:
                align_filter = self.ALIGN_FILTERS[token]
            elif token.isdigit():
                level_filter = int(token)
            elif token and not align_filter:
                # Treat as a class name partial match
                class_filter = token

        if align_filter or level_filter or class_filter:
            filtered = []
            for char in online_chars:
                alignment = char.attributes.get("alignment", default="?")
                level = char.attributes.get("level", default=1)
                charclass = char.attributes.get("character_class", default=None)
                if not charclass:
                    charclass = char.attributes.get("class", default="")

                if align_filter and alignment != align_filter:
                    continue
                if level_filter and level != level_filter:
                    continue
                if class_filter and class_filter not in charclass.lower():
                    continue
                filtered.append(char)
            online_chars = filtered

        if not online_chars:
            caller.msg("|yNo online characters match that filter.|n")
            return

        # Sort by level descending
        online_chars.sort(
            key=lambda c: c.attributes.get("level", default=1),
            reverse=True,
        )

        lines = []
        # Colorful header bar
        lines.append("|Y|h" + "=" * 78 + "|n")
        lines.append("|c|h  Adventurers of the Realm|n")
        lines.append("|Y|h" + "=" * 78 + "|n")
        lines.append("")
        # Column header with ANSI colors
        lines.append(
            f"|w|h{'Name':<19} {'Race':<15} {'Class':<13} {'Lvl':>3} "
            f"{'Align':<6} {'Clan':<10} {'PvP':<4} Status|n"
        )
        lines.append("|Y" + "-" * 78 + "|n")

        from commands.clan import CLANS
        from time import time

        from world.alignment_system import is_outlaw
        from world.tick_combat import CombatHandler

        for char in online_chars:
            race = char.attributes.get("race", default="?")
            # Read class from character_class (set during chargen) with fallback
            charclass = char.attributes.get("character_class", default=None)
            if not charclass:
                charclass = char.attributes.get("class", default="None")
            if charclass == "?" or charclass is None:
                charclass = "Unclassed"
            level = char.attributes.get("level", default=1)
            alignment = char.attributes.get("alignment", default="?")

            # Idle time calculation
            idle_seconds = 0
            if hasattr(char, 'sessions') and char.sessions.count() > 0:
                session = char.sessions.get()[0]
                if hasattr(session, 'cmd_last') and session.cmd_last:
                    idle_seconds = int(time() - session.cmd_last)
            if idle_seconds < 60:
                idle_str = "|gnow|n"
            elif idle_seconds < 3600:
                idle_str = f"|y{idle_seconds // 60}m|n"
            elif idle_seconds < 86400:
                idle_str = f"|r{idle_seconds // 3600}h|n"
            else:
                idle_str = f"|R{idle_seconds // 86400}d|n"

            # Color-code alignment
            if alignment == "Good":
                align_str = f"|g{alignment:<6}|n"
            elif alignment == "Evil":
                align_str = f"|r{alignment:<6}|n"
            else:
                align_str = f"|y{alignment:<6}|n"

            # Determine clan display
            clan = char.attributes.get("clan", default=None)
            if clan:
                clan_data = CLANS.get(clan, {})
                clan_align = clan_data.get("alignment", "Neutral")
                if clan_align == "Good":
                    clan_display = f"|g[{clan}]|n"
                elif clan_align == "Evil":
                    clan_display = f"|r[{clan}]|n"
                else:
                    clan_display = f"|w[{clan}]|n"
            else:
                clan_display = "|y-|n"

            # Color-code level
            if level >= 50:
                level_str = f"|Y{level:>3}|n"
            elif level >= 30:
                level_str = f"|c{level:>3}|n"
            else:
                level_str = f"|w{level:>3}|n"

            # ---- Phase 6.9 — PvP status ----
            pvp_on = bool(char.attributes.get("pvp_enabled", default=False))
            pvp_str = "|gON|n" if pvp_on else "|rOFF|n"

            # ---- Phase 6.9 — Status markers (outlaw + fighting) ----
            status_parts = [idle_str]
            if CombatHandler.is_in_combat(char):
                status_parts.append("|R[FIGHTING]|n")
            try:
                if is_outlaw(char):
                    status_parts.append("|r[OUTLAW]|n")
            except Exception:
                pass
            status_str = " ".join(status_parts)

            lines.append(
                f"|w{char.key:<19}|n {race:<15} {charclass:<13} "
                f"{level_str} {align_str} {clan_display:<10} {pvp_str:<4} {status_str}"
            )

        lines.append("")
        lines.append("|Y" + "-" * 78 + "|n")
        # Footer summary count
        count = len(online_chars)
        lines.append(f"|wTotal Online:|g {count} adventurer(s)|n")

        caller.msg("\n".join(lines))


class CmdStats(Command):
    """
    Display realm statistics — total counts of rooms, mobs, NPCs,
    shopkeepers, items, exits, players, and accounts.

    Usage:
      stats

    Shows a comprehensive breakdown of every entity type in the game
    world, including faction distribution for mobs and alignment
    distribution for player characters.
    """

    key = "stats"
    aliases = ["statistics", "realmstats"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        all_objects = list(ObjectDB.objects.all())

        # --- Rooms ---
        rooms = [o for o in all_objects if o.__class__.__name__ == "Room"]

        # --- Exits ---
        exits = [o for o in all_objects if o.destination]

        # --- Items (MUDItem typeclass) ---
        items = [
            o for o in all_objects
            if hasattr(o, 'typeclass_path') and o.typeclass_path.endswith("MUDItem")
        ]

        # --- Mobs (Mob typeclass or db.is_mob) ---
        mobs = [
            o for o in all_objects
            if (
                (hasattr(o, 'typeclass_path') and o.typeclass_path.endswith("Mob"))
                or o.attributes.get("is_mob", default=False)
            )
        ]

        # --- NPCs (NPC typeclass or db.is_npc) ---
        npcs = [
            o for o in all_objects
            if (
                (hasattr(o, 'typeclass_path') and o.typeclass_path.endswith("NPC"))
                or o.attributes.get("is_npc", default=False)
            )
        ]

        # --- Shopkeepers (Shopkeeper typeclass or db.is_vendor) ---
        shops = [
            o for o in all_objects
            if (
                (hasattr(o, 'typeclass_path') and o.typeclass_path.endswith("Shopkeeper"))
                or o.attributes.get("is_vendor", default=False)
            )
        ]

        # --- Player Characters (Character typeclass with accounts) ---
        from typeclasses.characters import Character
        players = [
            o for o in all_objects
            if isinstance(o, Character)
        ]

        # --- Accounts ---
        accounts = list(AccountDB.objects.all())

        # --- Faction breakdown for mobs ---
        good_mobs = [m for m in mobs if m.attributes.get("faction", "") == "good"]
        evil_mobs = [m for m in mobs if m.attributes.get("faction", "") == "evil"]
        neutral_mobs = [m for m in mobs if m.attributes.get("faction", "") == "neutral"]

        # --- Aggro breakdown ---
        aggro_mobs = [m for m in mobs if m.attributes.get("aggro", default=False)]
        passive_mobs = [m for m in mobs if not m.attributes.get("aggro", default=False)]

        # --- Alignment breakdown for players ---
        good_players = [p for p in players if p.attributes.get("alignment", "") == "Good"]
        evil_players = [p for p in players if p.attributes.get("alignment", "") == "Evil"]
        neutral_players = [p for p in players if p.attributes.get("alignment", "") not in ("Good", "Evil")]

        # --- Online players ---
        online_players = [p for p in players if hasattr(p, 'sessions') and p.sessions.count() > 0]

        # --- Items on ground vs in inventories ---
        items_on_ground = [
            i for i in items
            if i.location and i.location.__class__.__name__ == "Room"
        ]
        items_in_inventory = len(items) - len(items_on_ground)

        # --- Zone breakdown for rooms ---
        zones = {}
        for room in rooms:
            zone_tags = room.tags.get(category="zone")
            if zone_tags:
                zone_name = zone_tags[0] if isinstance(zone_tags, (list, tuple)) else zone_tags
                zones[zone_name] = zones.get(zone_name, 0) + 1

        # --- Build output ---
        lines = []
        lines.append("|Y|h" + "=" * 55 + "|n")
        lines.append("|c|h           Realm Statistics|n")
        lines.append("|Y|h" + "=" * 55 + "|n")
        lines.append("")

        # World Structure
        lines.append("|w|h--- World Structure ---|n")
        lines.append(f"  |cRooms:|n  {len(rooms)}")
        lines.append(f"  |cExits:|n  {len(exits)}")
        if zones:
            lines.append(f"  |cZones:|n  {len(zones)}")
            for zone_name, count in sorted(zones.items()):
                lines.append(f"    |w{zone_name}:|n {count} rooms")
        lines.append("")

        # Entities
        lines.append("|w|h--- Entities ---|n")
        lines.append(f"  |cMobs:|n       {len(mobs)}")
        lines.append(f"    |gGood:|n      {len(good_mobs)}")
        lines.append(f"    |rEvil:|n      {len(evil_mobs)}")
        lines.append(f"    |yNeutral:|n   {len(neutral_mobs)}")
        lines.append(f"    |RAggressive:|n {len(aggro_mobs)}")
        lines.append(f"    |YPassive:|n    {len(passive_mobs)}")
        lines.append(f"  |cNPCs:|n       {len(npcs)}")
        lines.append(f"  |cShopkeepers:|n {len(shops)}")
        lines.append("")

        # Items
        lines.append("|w|h--- Items ---|n")
        lines.append(f"  |cTotal Items:|n       {len(items)}")
        lines.append(f"  |cOn Ground:|n         {len(items_on_ground)}")
        lines.append(f"  |cIn Inventories:|n    {items_in_inventory}")
        lines.append("")

        # Players & Accounts
        lines.append("|w|h--- Players & Accounts ---|n")
        lines.append(f"  |cCharacters:|n  {len(players)}")
        lines.append(f"    |gGood:|n      {len(good_players)}")
        lines.append(f"    |rEvil:|n      {len(evil_players)}")
        lines.append(f"    |yNeutral:|n   {len(neutral_players)}")
        lines.append(f"  |cOnline Now:|n  {len(online_players)}")
        lines.append(f"  |cAccounts:|n    {len(accounts)}")
        lines.append("")

        # Grand Total
        total_entities = len(mobs) + len(npcs) + len(shops) + len(items) + len(players)
        lines.append("|Y|h" + "-" * 55 + "|n")
        lines.append(f"|W|h  Grand Total Entities: {total_entities}|n")
        lines.append("|Y|h" + "=" * 55 + "|n")

        caller.msg("\n".join(lines))


class CmdRules(Command):
    """
    Display the server rules and guidelines.

    Usage:
      rules
      help rules

    Shows the full list of server rules covering general conduct,
    accounts, channels, and punishments.
    """

    key = "rules"
    aliases = ["guidelines", "serverrules"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        """Display the server rules."""
        from world.rules import RULES_TEXT
        self.caller.msg(RULES_TEXT)


# Aliases for test compatibility / standard MUD command names
CmdLook = CmdLookSelf
CmdInventory = CmdLookSelf  # inventory is handled by Evennia default
CmdSay = CmdLookSelf        # say is handled by Evennia default
CmdPose = CmdLookSelf       # pose is handled by Evennia default


class CmdExits(Command):
    """
    List all visible exits from the current room with their short names.

    Usage:
      exits

    Displays each exit direction with its short alias (e.g. north (n))
    so you can quickly see which directions are available without
    reading the full room description.
    """

    key = "exits"
    aliases = ["ex"]
    help_category = "Movement"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        location = caller.location

        if not location:
            caller.msg("|rYou are floating in the void — there are no exits.|n")
            return

        visible_exits = []
        for ex in location.exits:
            if hasattr(ex, "is_hidden_door") and ex.is_hidden_door():
                continue
            key = ex.key.lower()
            from typeclasses.exits import DIRECTION_ALIASES
            aliases = DIRECTION_ALIASES.get(key, [])
            alias_str = f" ({', '.join(aliases)})" if aliases else ""
            visible_exits.append(f"|g{key}{alias_str}|n")

        if not visible_exits:
            caller.msg("|yThere are no obvious exits.|n")
            return

        caller.msg(f"|wObvious exits:|n {', '.join(visible_exits)}")


class CmdExamine(Command):
    """
    Examine an object, item, or character in detail.

    Usage:
      examine <target>
      ex <target>

    Shows detailed information about the target:
      - Items: weight, value, durability, armor, magic resist, stat bonuses, damage
      - Characters: same as look
      - Rooms: same as look
    """

    key = "examine"
    aliases = ["ex", "exam"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.target_name = self.args.strip() if self.args else ""

    def func(self):
        caller = self.caller

        if not self.target_name:
            caller.msg("|yUsage: examine <target>  (e.g. examine sword, ex goblin)|n")
            return

        # Search for the target
        candidates = []
        if caller.location:
            candidates = caller.location.contents
        # Also search inventory
        candidates = list(candidates) + [obj for obj in caller.contents if not getattr(obj, "destination", None)]

        target_list = caller.search(
            self.target_name,
            candidates=candidates,
            quiet=True,
        )

        if not target_list or len(target_list) == 0:
            caller.msg(f"|rYou don't see '{self.target_name}' here.|n")
            return

        target = target_list[0]

        # Build detailed examine output
        lines = []
        lines.append(f"|w{target.key}|n")
        lines.append("-" * 50)

        # Item-specific details
        is_item = hasattr(target, "attributes") and (
            target.attributes.has("weight") or
            target.attributes.has("value") or
            target.attributes.has("damage") or
            target.attributes.has("armor")
        )

        if is_item:
            weight = target.attributes.get("weight", default=0)
            value = target.attributes.get("value", default=0)
            durability = target.attributes.get("durability", default=None)
            max_durability = target.attributes.get("max_durability", default=None)
            armor = target.attributes.get("armor", default=0)
            magic_resist = target.attributes.get("magic_resist", default=0)
            damage = target.attributes.get("damage", default=0)
            damage_type = target.attributes.get("damage_type", default="")
            stat_bonuses = target.attributes.get("stat_bonuses", default={})
            item_type = target.attributes.get("item_type", default="")

            if item_type:
                lines.append(f"|cType:|n {item_type}")
            if weight:
                lines.append(f"|cWeight:|n {weight}")
            if value:
                lines.append(f"|cValue:|n {value} gold")
            if durability is not None and max_durability is not None:
                pct = int(durability / max_durability * 100) if max_durability > 0 else 0
                color = "|g" if pct > 75 else ("|y" if pct > 50 else ("|r" if pct > 25 else "|R"))
                lines.append(f"|cDurability:|n {color}{durability}/{max_durability} ({pct}%)|n")
            if damage > 0:
                dt_str = f" ({damage_type})" if damage_type else ""
                lines.append(f"|cDamage:|n {damage}{dt_str}")
            if armor > 0:
                lines.append(f"|cArmor:|n {armor}")
            if magic_resist > 0:
                lines.append(f"|cMagic Resist:|n {magic_resist}")
            if stat_bonuses:
                bonus_str = ", ".join(f"|g+{v} {k.upper()}|n" for k, v in stat_bonuses.items())
                lines.append(f"|cStat Bonuses:|n {bonus_str}")

            # Description
            desc = target.db.desc
            if desc:
                lines.append(f"\n|wDescription:|n {desc}")
        else:
            # For characters/NPCs, delegate to return_appearance
            if hasattr(target, "return_appearance"):
                caller.msg(target.return_appearance(caller))
                return
            else:
                lines.append("|yNothing special to examine.|n")

        caller.msg("\n".join(lines))


class CmdScan(Command):
    """
    Scan the surrounding area for nearby rooms and visible exits.

    Usage:
      scan

    Gives a brief overview of what lies in each direction from your
    current position, showing the name of each adjacent room without
    actually moving there.
    """

    key = "scan"
    aliases = ["scout", "survey"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        location = caller.location

        if not location:
            caller.msg("|rYou are floating in the void — there is nothing to scan.|n")
            return

        lines = []
        lines.append("|wYou scan the surrounding area...|n")
        lines.append("")

        found_any = False
        for ex in location.exits:
            if hasattr(ex, "is_hidden_door") and ex.is_hidden_door():
                continue
            dest = ex.destination
            if not dest:
                continue
            found_any = True
            direction = ex.key.lower()
            dest_name = dest.key
            # Count mobs in destination
            mob_count = 0
            for obj in dest.contents:
                if hasattr(obj, "attributes") and obj.attributes.get("is_mob", False):
                    mob_count += 1
            mob_str = f" |r[{mob_count} mob(s)]|n" if mob_count > 0 else ""
            lines.append(f"  |g{direction:<12}|n → |w{dest_name}|n{mob_str}")

        if not found_any:
            lines.append("|yThere are no visible exits to scan.|n")

        caller.msg("\n".join(lines))


class CmdBrief(Command):
    """
    Toggle brief mode — suppress room descriptions on re-entry.

    Usage:
      brief

    When brief mode is ON, moving into a room you have already visited
    will only show the room title and exits, skipping the long
    description.  This is ideal for quickly navigating familiar areas.

    Use |yverbose|n to turn brief mode off and see full descriptions
    again.
    """

    key = "brief"
    aliases = ["compact"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        current = caller.attributes.get("brief_mode", default=False)

        if current:
            caller.msg("|yBrief mode is already ON. Use |yverbose|y to turn it off.|n")
            return

        caller.attributes.add("brief_mode", True)
        caller.msg(
            "|gBrief mode is now ON.|n\n"
            "|wRoom descriptions will be suppressed for rooms you have "
            "already visited. Use |yverbose|w to see full descriptions again.|n"
        )


class CmdVerbose(Command):
    """
    Turn off brief mode — show full room descriptions on every entry.

    Usage:
      verbose

    Restores the default behaviour where every room shows its full
    description, regardless of whether you have visited it before.
    """

    key = "verbose"
    aliases = ["full"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        current = caller.attributes.get("brief_mode", default=False)

        if not current:
            caller.msg("|yVerbose mode is already ON (brief mode is OFF).|n")
            return

        caller.attributes.add("brief_mode", False)
        caller.msg(
            "|gVerbose mode is now ON.|n\n"
            "|wFull room descriptions will be shown on every entry.|n"
        )


class CmdWarpoints(Command):
    """
    Display the Warpoints leaderboard — the top PvP champions of the realm.

    Usage:
      warpoints
      wp
      topkills

    Shows the top 20 players ranked by total Warpoints earned from
    cross-faction PvP kills.  Each entry displays rank, name, level,
    faction, and total Warpoints.

    Warpoints are earned by slaying players of the opposing faction.
    Same-faction kills do NOT award Warpoints and incur Infamy instead.
    """

    key = "warpoints"
    aliases = ["wp", "topkills", "topwp"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    # Number of entries to show on the leaderboard
    LEADERBOARD_SIZE = 20

    def func(self):
        caller = self.caller

        from typeclasses.characters import Character
        from evennia.objects.models import ObjectDB

        # Gather all characters that have warpoints
        ranked = []
        for obj in ObjectDB.objects.all():
            if not isinstance(obj, Character):
                continue
            wp = obj.attributes.get("warpoints", default=0)
            if wp > 0:
                ranked.append({
                    "name": obj.key,
                    "level": obj.attributes.get("level", default=1),
                    "alignment": obj.attributes.get("alignment", default="?"),
                    "warpoints": wp,
                })

        if not ranked:
            caller.msg(
                "|yNo Warpoints have been earned yet. "
                "Be the first to claim glory in battle!|n"
            )
            return

        # Sort by warpoints descending, then level descending
        ranked.sort(key=lambda c: (-c["warpoints"], -c["level"]))

        # Limit to top N
        top = ranked[:self.LEADERBOARD_SIZE]

        lines = []
        lines.append("|Y|h===== Warpoints Leaderboard =====|n")
        lines.append("")
        lines.append(
            f"|c{'Rank':>4}  {'Name':<20} {'Lvl':>3}  {'Faction':<6}  Warpoints|n"
        )
        lines.append("-" * 55)

        for i, char in enumerate(top, 1):
            # Color-code rank
            if i == 1:
                rank_str = f"|Y{i:>4}|n"
            elif i == 2:
                rank_str = f"|w{i:>4}|n"
            elif i == 3:
                rank_str = f"|r{i:>4}|n"
            else:
                rank_str = f"{i:>4}"

            # Color-code faction
            if char["alignment"] == "Good":
                faction_str = f"|g{char['alignment']:<6}|n"
            elif char["alignment"] == "Evil":
                faction_str = f"|r{char['alignment']:<6}|n"
            else:
                faction_str = f"{char['alignment']:<6}"

            lines.append(
                f"{rank_str}  |w{char['name']:<20}|n "
                f"{char['level']:>3}  {faction_str}  "
                f"|Y{char['warpoints']}|n"
            )

        lines.append("")
        lines.append(
            f"|wShowing top {len(top)} of {len(ranked)} "
            f"warriors with Warpoints.|n"
        )

        caller.msg("\n".join(lines))


class CmdSleep(Command):
    """
    Lie down and sleep to recover rapidly.

    Usage:
      sleep

    While sleeping, your HP, Mana, and MV regenerate at the fastest
    possible rate.  However, you are completely helpless — any attack
    against you while sleeping deals extra damage.

    Sleep ends automatically if you move, enter combat, or use the
    |ywake|n command.
    """

    key = "sleep"
    aliases = ["slumber"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        from world.tick_combat import CombatHandler
        if CombatHandler.is_in_combat(caller):
            caller.msg("|rYou cannot sleep while in combat!|n")
            return

        current_pos = caller.attributes.get("position", default="standing")
        if current_pos == "sleeping":
            caller.msg("|yYou are already asleep. Use |ywake|y to wake up.|n")
            return

        caller.attributes.add("position", "sleeping")
        caller.attributes.add("is_resting", False)
        caller.attributes.add("is_meditating", False)
        caller.msg(
            "|cYou lie down and drift off to sleep.|n\n"
            "|w(You are |rVULNERABLE|w while sleeping — attacks deal extra damage! "
            "Use |ywake|w to wake up.)|n"
        )
        caller.location.msg_contents(
            f"|c{caller.key} lies down and falls asleep.|n", exclude=caller
        )


class CmdWake(Command):
    """
    Wake up and stand up from any resting, meditating, or sleeping state.

    Usage:
      wake
      stand

    Returns you to a standing position, ending any rest, meditation,
    or sleep state.
    """

    key = "wake"
    aliases = ["stand", "awaken"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        current_pos = caller.attributes.get("position", default="standing")
        if current_pos == "standing":
            caller.msg("|yYou are already standing.|n")
            return

        caller.attributes.add("position", "standing")
        caller.attributes.add("is_resting", False)
        caller.attributes.add("is_meditating", False)

        if current_pos == "sleeping":
            caller.msg("|gYou wake up and rise to your feet.|n")
            caller.location.msg_contents(
                f"|g{caller.key} wakes up and stands.|n", exclude=caller
            )
        else:
            caller.msg("|gYou stand up.|n")
            caller.location.msg_contents(
                f"|g{caller.key} stands up.|n", exclude=caller
            )


class CmdStamina(Command):
    """
    Display your current stamina level.

    Usage:
      stamina
      sp

    Shows your current stamina points and maximum stamina.  Stamina is
    consumed by physical combat skills (kick, bash, backstab, disarm)
    and regenerates over time based on your position.
    """

    key = "stamina"
    aliases = ["sp", "endurance"]
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller

        stamina = caller.attributes.get("stamina", default=100)
        max_stamina = caller.attributes.get("max_stamina", default=100)

        pct = int(stamina / max_stamina * 100) if max_stamina > 0 else 0
        if pct > 75:
            color = "|g"
        elif pct > 50:
            color = "|y"
        elif pct > 25:
            color = "|r"
        else:
            color = "|R"

        caller.msg(
            f"|wStamina:|n {color}{stamina}/{max_stamina} ({pct}%)|n\n"
            f"|wStamina is used by combat skills and regenerates over time.|n"
        )


class CmdRevive(Command):
    """
    Revive an unconscious ally before they bleed out.

    Usage:
      revive <player>

    You must be in the same room as the unconscious player.  Reviving
    restores them to 1 HP and returns them to a standing position.
    Only works on players who are UNCONSCIOUS (bleeding out), not dead.
    """

    key = "revive"
    aliases = ["rescue"]
    help_category = "Combat"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("|yUsage: revive <player>|n")
            return

        # Find the target in the same room
        target_name = self.args
        location = caller.location
        if not location:
            caller.msg("|rYou are nowhere.|n")
            return

        target = None
        for obj in location.contents:
            if obj.key.lower() == target_name.lower():
                target = obj
                break

        if not target:
            caller.msg(f"|rNo one named '{target_name}' is here.|n")
            return

        if target == caller:
            caller.msg("|rYou cannot revive yourself.|n")
            return

        # Check target is a player character
        if not getattr(target, "has_account", False):
            caller.msg(f"|r{target.key} is not a player character.|n")
            return

        # Check target is UNCONSCIOUS
        from world.combat_state import CombatStateMachine, CombatState
        state = CombatStateMachine.get_state(target)
        if state != CombatState.UNCONSCIOUS:
            caller.msg(f"|r{target.key} is not unconscious.|n")
            return

        # Revive the target
        CombatStateMachine.set_state(target, CombatState.IDLE)

        # Restore 1 HP so they're alive
        target.attributes.add("hp", 1)

        # Clear the bleed-out timer
        target.attributes.add("unconscious_expires", 0)

        # Set position to standing
        target.attributes.add("position", "standing")
        target.attributes.add("is_resting", False)
        target.attributes.add("is_meditating", False)

        # Messages
        caller.msg(f"|gYou revive {target.key}, bringing them back from the brink of death!|n")
        target.msg(f"|g{caller.key} revives you! You gasp and open your eyes.|n")
        location.msg_contents(
            f"|g{caller.key} revives {target.key}, who stirs back to consciousness!|n",
            exclude=[caller, target],
        )
