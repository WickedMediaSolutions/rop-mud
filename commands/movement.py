"""
Movement Commands for 'rop'

Provides:
  run <direction>  - keep moving in a direction until blocked, at a fork, or out of MV
"""

from commands.command import Command
from typeclasses.exits import normalize_direction, VALID_DIRECTIONS, DIRECTION_ALIASES, ALIAS_TO_DIRECTION


def get_move_speed_multiplier(character) -> float:
    """
    Return the racial movement speed multiplier (e.g. 1.2 for Centaur's
    +20% Gallop passive), or 1.0 when the character has no such bonus.

    This is the canonical hook for racial move-speed passives so other
    systems (movement, run, chasing, etc.) can share the same value.
    """
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(character)
        pct = racial.get("move_speed_pct", 0)
        return 1.0 + (pct / 100.0)
    except Exception:
        return 1.0


def get_move_cost(character) -> int:
    """
    Return the MV cost for moving one room.

    Base cost is 1 MV.  Encumbered characters (carrying above capacity)
    pay an additional MV per step, up to +1 for full overload.

    Racial movement speed bonuses (e.g. Centaur Gallop +20%) accumulate
    fractional "movement credit".  When the accumulated credit reaches a
    full MV, the next move is free — which yields exactly the advertised
    percentage of extra distance for the same MV pool.
    """
    try:
        from world.encumbrance import get_encumbrance_penalty
        penalty = get_encumbrance_penalty(character)
        cost = 1 + round(penalty)
    except Exception:
        cost = 1

    # Racial passive: movement speed (Centaur +20%).
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(character)
        speed_pct = racial.get("move_speed_pct", 0)
        if speed_pct > 0 and cost > 0:
            credit = character.attributes.get("move_speed_credit", default=0.0)
            try:
                credit = float(credit)
            except (TypeError, ValueError):
                credit = 0.0
            credit += speed_pct / 100.0
            if credit >= 1.0:
                cost = max(0, cost - 1)
                credit -= 1.0
            character.attributes.add("move_speed_credit", credit)
    except Exception:
        pass

    return cost


def _find_exit_in_room(room, canonical_direction, include_doors=False):
    """
    Return the first exit in *room* whose canonical direction matches
    *canonical_direction*, or None.

    Matching strategy (in order):
      1. Normalise the exit's key to canonical and compare.
      2. Check the exit's aliases for the canonical name.
      3. Also check aliases for every short alias of the canonical
         direction (so exits created with the short key are found even
         before their bidirectional aliases are populated).

    When *include_doors* is False (default), closed/locked doors are
    skipped.  When True, they are returned so the caller can inspect
    their state.
    """
    if not room:
        return None
    for ex in room.exits:
        if not include_doors and hasattr(ex, "is_hidden_door") and ex.is_hidden_door():
            continue
        # 1) Direct canonical match on the key
        ex_canonical = ALIAS_TO_DIRECTION.get(ex.key.lower(), ex.key.lower())
        if ex_canonical == canonical_direction:
            return ex
        # 2) The exit may have the canonical name as an alias
        ex_aliases_lower = [a.lower() for a in ex.aliases.all()]
        if canonical_direction in ex_aliases_lower:
            return ex
        # 3) Also check short aliases of the canonical direction
        for short in DIRECTION_ALIASES.get(canonical_direction, []):
            if short in ex_aliases_lower:
                return ex
    return None


class CmdMove(Command):
    """
    Master Direction Command Set — handles all single-letter and full
    directional movement without relying on exit object aliases.

    Usage:
      n, s, e, w, ne, nw, se, sw, u, d
      north, south, east, west, northeast, northwest, southeast, southwest, up, down

    Maps short inputs to canonical direction names, finds the matching
    exit in the current room, and traverses it.  If no exit exists in
    that direction the player is told they cannot go that way.
    """

    key = "n"
    aliases = [
        "north", "n", "south", "s", "east", "e", "west", "w",
        "northeast", "ne", "northwest", "nw",
        "southeast", "se", "southwest", "sw",
        "up", "u", "down", "d",
    ]
    priority = 10
    help_category = "Movement"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        raw = self.cmdstring.strip().lower()
        canonical = ALIAS_TO_DIRECTION.get(raw, raw)

        location = caller.location
        if not location:
            caller.msg("You cannot go that way.")
            return

        # First try to find an open exit
        exit_obj = _find_exit_in_room(location, canonical)

        if exit_obj and exit_obj.destination:
            mv = caller.attributes.get("mv", default=100)
            cost = get_move_cost(caller)
            if mv < cost:
                caller.msg("|rYou are too exhausted to move.|n")
                return
            caller.attributes.add("mv", mv - cost)
            # Break stealth on movement
            try:
                from world.combat_skills import break_stealth
                break_stealth(caller, reason="move")
            except Exception:
                pass
            exit_obj.at_traverse(caller, exit_obj.destination)
            return

        # No open exit found — check if there's a closed/locked door
        door = _find_exit_in_room(location, canonical, include_doors=True)
        if door:
            if hasattr(door, "is_locked") and door.is_locked():
                caller.msg("|rIt's locked.|n")
            elif hasattr(door, "is_closed") and door.is_closed():
                caller.msg("|rIt's closed.|n")
            else:
                caller.msg("You cannot go that way.")
        else:
            caller.msg(f"|rYou see no exit to the {canonical}.|n")


class CmdRun(Command):
    """
    Dash through multiple rooms in one direction.

    Usage:
      run <direction>
      run n
      run northeast

    Your character keeps moving in the chosen direction until they hit a wall,
    enter a room with branching paths (more than one exit other than the return
    direction), or run out of movement points (MV).

    This is ideal for covering long stretches of open road or hallway quickly.
    """

    key = "run"
    aliases = ["dash", "sprint"]
    help_category = "Movement"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.direction = self.args.strip().lower() if self.args else ""

    def func(self):
        caller = self.caller

        if not self.direction:
            caller.msg("|yUsage: run <direction>  (e.g. run n, run northeast)|n")
            return

        # Normalize the direction
        canonical = normalize_direction(self.direction)
        if canonical not in VALID_DIRECTIONS:
            caller.msg(
                f"|r'{self.direction}' is not a valid direction. "
                f"Use: n, s, e, w, ne, nw, se, sw, u, d|n"
            )
            return

        # Get movement points
        mv = caller.attributes.get("mv", default=100)
        if mv <= 0:
            caller.msg("|rYou are too exhausted to run.|n")
            return

        rooms_traversed = 0
        current_room = caller.location

        while mv > 0:
            exit_obj = _find_exit_in_room(current_room, canonical)

            if not exit_obj:
                if rooms_traversed == 0:
                    caller.msg(f"|rYou cannot go {canonical} from here.|n")
                else:
                    caller.msg(
                        f"|gYou run {canonical} through {rooms_traversed} room(s) "
                        f"and stop at a dead end.|n"
                    )
                return

            # Check for forks: are there other exits besides the one we entered from
            # and the one we're about to take?
            destination = exit_obj.destination
            if destination:
                # Get the return direction (opposite of our travel direction)
                from typeclasses.exits import get_opposite
                reverse = get_opposite(canonical)

                # Count exits in the next room that aren't the way we came
                other_exits = []
                for ex in destination.exits:
                    key_lower = ex.key.lower()
                    if key_lower == reverse or any(
                        alias in [a.lower() for a in ex.aliases.all()]
                        for alias in (DIRECTION_ALIASES.get(reverse, []))
                    ):
                        continue
                    other_exits.append(ex)

                if len(other_exits) > 1 and rooms_traversed > 0:
                    caller.msg(
                        f"|gYou run {canonical} through {rooms_traversed} room(s) "
                        f"and stop at a crossroads in {destination.key}.|n"
                    )
                    return

            # Traverse the exit
            caller.move_to(exit_obj.destination)
            rooms_traversed += 1
            mv -= get_move_cost(caller)

            # Update the character's MV
            caller.attributes.add("mv", mv)
            current_room = caller.location

        # Ran out of movement points
        caller.msg(
            f"|yYou run {canonical} through {rooms_traversed} room(s) "
            f"but are now too tired to continue.|n"
        )

        # Show the room we stopped in
        caller.msg(caller.location.return_appearance(caller))


class CmdLookDir(Command):
    """
    Look in a specific direction to see what lies beyond.

    Usage:
      look <direction>
      l <direction>

    Examples:
      look north
      l n
      look up

    Peers into the adjacent room without moving there.  If the exit is
    a closed or locked door you will be told its state.  If there is no
    exit in that direction you will be told so.
    """

    key = "look"
    aliases = ["l"]
    help_category = "Movement"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip()

    def func(self):
        caller = self.caller

        if not self.args:
            # No direction given — show current room (default look)
            if caller.location:
                caller.msg(caller.location.return_appearance(caller))
            else:
                caller.msg("|rYou are floating in the void.|n")
            return

        # Normalize the direction argument
        raw = self.args.lower()
        canonical = ALIAS_TO_DIRECTION.get(raw, raw)

        # If the argument is NOT a recognized direction, fall back to
        # default look behavior (examine an object/character in the room).
        # Special-case "me" and "self" to delegate to CmdLookSelf.
        if raw not in VALID_DIRECTIONS:
            if raw in ("me", "self"):
                caller.execute_cmd("lookself")
            else:
                caller.execute_cmd(f"examine {self.args}")
            return

        location = caller.location
        if not location:
            caller.msg("|rYou are nowhere — there is nothing to look at.|n")
            return

        # Check for a door first (include closed/locked)
        door = _find_exit_in_room(location, canonical, include_doors=True)

        if door:
            if hasattr(door, "is_locked") and door.is_locked():
                caller.msg(f"|rThe {canonical} door is locked.|n")
                return
            if hasattr(door, "is_closed") and door.is_closed():
                caller.msg(f"|rThe {canonical} door is closed.|n")
                return

            # Open exit — show the destination room
            dest = door.destination
            if dest:
                caller.msg(f"|wYou look to the {canonical}:|n")
                caller.msg(dest.return_appearance(caller))
            else:
                caller.msg(f"|rThe {canonical} exit leads nowhere.|n")
        else:
            caller.msg(f"|rYou see no exit to the {canonical}.|n")
