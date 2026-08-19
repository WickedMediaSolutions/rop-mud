"""
Exits

Exits are connectors between Rooms. An exit always has a destination property
set and has a single command defined on itself with the same name as its key,
for allowing Characters to traverse the exit to its destination.

"""

from evennia.objects.objects import DefaultExit

from .objects import ObjectParent

# Full direction name -> short alias mapping
DIRECTION_ALIASES = {
    "north": ["n"],
    "south": ["s"],
    "east": ["e"],
    "west": ["w"],
    "northeast": ["ne"],
    "northwest": ["nw"],
    "southeast": ["se"],
    "southwest": ["sw"],
    "up": ["u"],
    "down": ["d"],
}

# Reverse mapping: any alias or full name to canonical direction name
ALIAS_TO_DIRECTION = {}
for canonical, aliases in DIRECTION_ALIASES.items():
    ALIAS_TO_DIRECTION[canonical] = canonical
    for alias in aliases:
        ALIAS_TO_DIRECTION[alias] = canonical

# Opposite direction mapping (used when creating exits)
OPPOSITE_DIRECTIONS = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "northeast": "southwest",
    "southwest": "northeast",
    "northwest": "southeast",
    "southeast": "northwest",
    "up": "down",
    "down": "up",
}

# Set of all valid direction keys/aliases for fast membership tests
VALID_DIRECTIONS = set(ALIAS_TO_DIRECTION.keys())


def normalize_direction(direction):
    """Convert any direction alias (e.g. 'n', 'ne') to canonical name ('north', 'northeast')."""
    return ALIAS_TO_DIRECTION.get(direction.lower().strip(), direction.lower().strip())


def get_opposite(direction):
    """Return the opposite direction for a given canonical or alias direction."""
    canonical = normalize_direction(direction)
    return OPPOSITE_DIRECTIONS.get(canonical, None)


class Exit(ObjectParent, DefaultExit):
    """
    Exits are connectors between rooms. Exits are normal Objects except
    they define the `destination` property and override some hooks
    and methods to represent the exits.

    Extends the default Exit to support diagonal directions (ne, nw, se, sw)
    and short direction aliases (n, s, e, w, u, d).

    Phase 1.2: Exits also act as doors. An exit with `closed` or `locked`
    state is not traversable and is hidden from the room's "Obvious exits"
    line. Use the `open`, `close`, `lock` and `unlock` commands to
    manipulate these states.

    Phase 6.x: Bidirectional aliases.  Exits created with short keys
    (e.g. 'n') automatically gain the canonical full-name alias ('north'),
    and exits created with full names gain the short alias.  This ensures
    CmdMove.func() can resolve the exit regardless of which convention
    the builder used.
    """

    def at_object_creation(self):
        """Set up the exit with proper aliases based on direction key."""
        super().at_object_creation()

        # Phase 1.2: Door state defaults. All exits start open/unlocked.
        self.db.closed = False
        self.db.locked = False

        # Bidirectional aliases: add both short and canonical forms so
        # the exit is reachable via any valid direction token.
        self._add_direction_aliases()

    def _add_direction_aliases(self):
        """
        Add every valid direction alias for this exit's key so that the
        CmdMove.func() fallback alias check always finds the exit.

        Strategy:
          - Normalise the key to its canonical name (e.g. 'n' → 'north').
          - If the canonical name is a recognised direction, add ALL of
            its aliases (short forms) AND the canonical name itself.
          - This handles both conventions: short-key exits get full-name
            aliases, and full-name exits get short-key aliases.
        """
        canonical = normalize_direction(self.key)
        if canonical in DIRECTION_ALIASES:
            for alias in DIRECTION_ALIASES[canonical]:
                self.aliases.add(alias)
            # Also add the canonical name itself so full-name lookups work
            self.aliases.add(canonical)

    def at_cmdset_get(self, **kwargs):
        """
        Prevent exits from providing their own movement commands.

        CmdMove (in commands/movement.py) handles all directional movement
        (n, s, e, w, ne, nw, se, sw, u, d and full names).  If exits also
        register commands with the same keys/aliases, Evennia's command
        handler sees multiple matches and forces the player to disambiguate
        (e.g. "se-1" vs "se-2").  Returning None here suppresses the
        auto-generated exit command so CmdMove is the sole handler.
        """
        return None

    # ------------------------------------------------------------------
    # Phase 1.2 — Door state helpers
    # ------------------------------------------------------------------

    def is_closed(self):
        """Return True if this exit is currently closed."""
        return bool(self.db.closed)

    def is_locked(self):
        """Return True if this exit is currently locked."""
        return bool(self.db.locked)

    def is_hidden_door(self):
        """
        Return True if this exit should not be listed as an obvious exit.

        A closed or locked door is not an "obvious" way out, so it is
        hidden from the room's exit line. The `open`/`unlock` commands can
        still match it by name/alias directly from the room's exits.
        """
        return self.is_closed() or self.is_locked()

    def at_traverse(self, traversing_object, target_location, **kwargs):
        """
        Block traversal through closed or locked doors.

        A locked door cannot be opened by movement alone; a closed door must
        be explicitly opened first. Both produce a failure message rather
        than letting the character pass through.
        """
        if self.is_locked():
            traversing_object.msg("|rIt's locked.|n")
            self.at_failed_traverse(traversing_object)
            return

        if self.is_closed():
            traversing_object.msg("|rIt's closed.|n")
            self.at_failed_traverse(traversing_object)
            return

        super().at_traverse(traversing_object, target_location, **kwargs)