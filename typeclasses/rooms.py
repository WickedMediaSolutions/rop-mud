"""
Room

Rooms are simple containers that have no location of their own.

"""

import re

from evennia.objects.objects import DefaultRoom
from evennia.utils.ansi import strip_ansi

from .objects import ObjectParent

# Regex to strip trailing coordinate numbers like "Zone Name (73,16)"
_COORD_SUFFIX_RE = re.compile(r"\s*\(\d+,\d+\)$")


class Room(ObjectParent, DefaultRoom):
    """
    Rooms are like any Object, except their location is None
    (which is default). They also use basetype_setup() to
    add locks so they cannot be puppeted or picked up.
    (to change that, use at_object_creation instead)

    Provides immersive, detailed room descriptions. When generating
    descriptions via the world builder, rooms should receive rich,
    paragraph-length descriptions that immerse the player in the setting.

    Display layout (top to bottom):

      Weather line
      |c Room Title          (cyan blue)
      |W  Description text   (grey)
      |g Obvious exits: southeast, north  (green, full direction names)
      |M Also here: |505 mob_name, |y player_name, |W npc_name|n  (|M=purple header, |425=pink mobs, |y=yellow players, |W=grey NPCs)
      |b You notice: |w item_name, gold|n  (blue header, items+coins in white, one line)

    Mob Spawning:
      Rooms can define a `spawn_table` attribute — a list of dicts with
      keys `prototype` (str), `count` (int), and optional `respawn_delay`
      (int).  On server start (at_init) the room populates its mobs.
      When a mob dies and respawns, it returns to this room automatically.
      Duplicate spawning is prevented by counting existing alive mobs.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.safe_zone = False
        self.db.alignment_restricted = None
        # Mob spawn table: list of {"prototype": str, "count": int, "respawn_delay": int}
        self.attributes.add("spawn_table", [])
        # Room population cap — max simultaneous alive mobs allowed.
        if not self.attributes.has("max_mobs"):
            self.attributes.add("max_mobs", 3)
        # Zone tag for boundary enforcement during mob wandering.
        if not self.attributes.has("zone_tag"):
            self.attributes.add("zone_tag", None)

    def at_init(self):
        """Populate mobs on server start/reload if a spawn_table is defined."""
        super().at_init()
        self._populate_mobs()
        # Ensure the global realm spawner is running.
        self._ensure_realm_spawner()

    def _populate_mobs(self):
        """
        Spawn all mobs defined in this room's spawn_table.

        Called on at_init (server start/reload).  Prevents duplicate
        spawning by counting existing alive mobs of each prototype
        already in the room.
        """
        spawn_table = self.attributes.get("spawn_table", default=[])
        if not spawn_table:
            return

        try:
            from typeclasses.mobs import spawn_mobs_for_room
            spawn_mobs_for_room(self, spawn_table)
        except Exception:
            pass

    def _ensure_realm_spawner(self):
        """
        Ensure the global realm respawn script is running.

        Called on every room's at_init.  Uses a module-level flag to
        avoid starting the spawner more than once per server reload.
        """
        try:
            from world.realm_spawner import start_realm_spawner
            start_realm_spawner()
        except Exception:
            pass

    def at_object_receive(self, obj, source_location, **kwargs):
        """
        Phase 2.5: Alignment-based room entry restrictions.
        Also triggers guard aggro checks when players enter rooms
        containing opposite-faction guards.
        """
        super().at_object_receive(obj, source_location, **kwargs)

        # --- Alignment restriction check ---
        restriction = self.attributes.get("alignment_restricted", default=None)
        if restriction:
            char_align = obj.attributes.get("alignment", default="Neutral") if hasattr(obj, "attributes") else "Neutral"
            if char_align != restriction and char_align != "Neutral":
                obj.msg(f"|rA powerful force prevents you from entering — this area is for the {restriction} only!|n")
                if source_location:
                    obj.move_to(source_location, quiet=True)
                    obj.msg(f"|yYou are pushed back to {source_location.key}.|n")
                return

        # --- Guard aggro check ---
        if hasattr(obj, "has_account") and obj.has_account:
            char_align = obj.attributes.get("alignment", default="Neutral")
            for content in self.contents:
                if self._is_guard(content):
                    guard_align = content.attributes.get("alignment", default="")
                    if guard_align and char_align and guard_align != char_align and char_align != "Neutral":
                        from world.tick_combat import CombatHandler
                        if not CombatHandler.is_in_combat(content):
                            content.msg(f"|R{content.key} lunges at {obj.key}!|n")
                            CombatHandler.start_combat(content, obj)
                        break

                from world.mob_ai import check_mob_aggro
                if check_mob_aggro(content, obj):
                    from world.tick_combat import CombatHandler
                    if not CombatHandler.is_in_combat(content):
                        content.msg(f"|R{content.key} attacks {obj.key}!|n")
                        CombatHandler.start_combat(content, obj)
                    break

    def return_appearance(self, looker, **kwargs):
        """
        Assemble the full room display in the correct order:
          1. Weather (above title)
          2. Room Title (cyan blue)
          3. Description (grey)
          4. Obvious exits (green, full direction names)
          5. Also here: (purple header, all on one line)
          6. You notice: (blue header, items+coins in white, one line)
        """
        if not looker:
            return ""

        parts = []

        weather = self._get_weather_line()
        if weather:
            parts.append(weather)

        name = self.get_display_name(looker, **kwargs)
        parts.append(name)

        desc = self.get_display_desc(looker, **kwargs)
        if desc:
            parts.append(desc)

        exits = self.get_display_exits(looker, **kwargs)
        if exits:
            parts.append(exits)

        chars = self.get_display_characters(looker, **kwargs)
        if chars:
            parts.append(chars)

        things = self.get_display_things(looker, **kwargs)
        if things:
            parts.append(things)

        return "\n".join(parts)

    def get_display_name(self, looker=None, **kwargs):
        """
        Return the player-visible name of this room in cyan (|c).
        Strips any pre-existing ANSI from the key so hardcoded colours
        (e.g. |Y from fix_realm_setup) don't override the wrapped cyan.
        Also strips trailing coordinate numbers like (73,16).
        """
        name = super().get_display_name(looker, **kwargs)
        name = _COORD_SUFFIX_RE.sub("", name)
        name = strip_ansi(name)
        return f"|c{name}|n"

    def get_display_desc(self, looker, **kwargs):
        """Return the room description coloured grey (|W)."""
        desc = self.db.desc
        if desc:
            return f"|W{desc}|n"
        return super().get_display_desc(looker, **kwargs)

    # ------------------------------------------------------------------
    # Entity classification helpers
    #
    # Mobs in this codebase are spawned as plain DefaultObjects.
    # Detection paths:
    #   - db.is_mob / db.is_npc / db.is_vendor  (prototype-based NPCs)
    #   - db.is_aggro                            (spawned mobs)
    #   - tag "realm_mob"                        (spawned mobs)
    #   - db.level + db.faction                  (generic spawned creatures)
    # ------------------------------------------------------------------

    @staticmethod
    def _is_creature(obj):
        """
        Return True if the object is any kind of creature that should
        appear under 'Also here' (mob, NPC, vendor, player).
        """
        if obj.has_account:
            return True
        if obj.attributes.get("is_mob", default=False):
            return True
        if obj.attributes.get("is_npc", default=False):
            return True
        if obj.attributes.get("is_vendor", default=False):
            return True
        # Spawned mobs (from spawn_mob) use is_aggro and the realm_mob tag
        if obj.attributes.get("is_aggro") is not None:
            return True
        if obj.tags.has("realm_mob", category="spawn"):
            return True
        # Objects with a level + faction are creatures (spawned mobs)
        if obj.attributes.has("level") and obj.attributes.has("faction"):
            return True
        return False

    @staticmethod
    def _is_hostile(obj):
        """Return True if the object is a hostile/attackable mob."""
        is_mob = obj.attributes.get("is_mob", default=False)
        aggro = obj.attributes.get("aggro", default=False)
        if is_mob and aggro:
            return True
        if obj.attributes.get("is_aggro", default=False):
            return True
        return False

    @staticmethod
    def _is_mob_entity(obj):
        """
        Return True if the object is a mob/monster (hostile or passive).
        Mobs appear in PINK under 'Also here'.

        Distinguished from service NPCs (guards, vendors, guildmasters,
        tutorial guides) which appear in GREY.
        """
        if obj.has_account:
            return False
        if obj.attributes.get("is_mob", default=False):
            return True
        # Spawned mobs have is_aggro set (even False for passive mobs)
        if obj.attributes.get("is_aggro") is not None:
            return True
        if obj.tags.has("realm_mob", category="spawn"):
            return True
        # Objects with level + faction are mobs unless they're vendors/NPCs
        if obj.attributes.has("level") and obj.attributes.has("faction"):
            if obj.attributes.get("is_vendor", default=False):
                return False
            if obj.attributes.get("is_npc", default=False):
                return False
            return True
        return False

    @staticmethod
    def _is_guard(obj):
        """
        Return True if the object is a guard/protector NPC.
        Guards are non-hostile mobs/NPCs whose name contains guard-like keywords.
        """
        if not Room._is_creature(obj):
            return False
        if Room._is_hostile(obj):
            return False
        name = obj.key.lower() if obj.key else ""
        guard_keywords = (
            "guard", "knight", "sentinel", "protector", "paladin",
            "militia", "defender", "warden", "watchman",
        )
        return any(kw in name for kw in guard_keywords)

    @staticmethod
    def _is_vendor(obj):
        """Return True if the object is a vendor/shopkeeper."""
        return bool(obj.attributes.get("is_vendor", default=False))

    @staticmethod
    def _is_item(obj):
        """
        Return True if the object is an inanimate item on the ground
        (not a creature, room, or exit).
        """
        from evennia.objects.objects import DefaultCharacter
        if obj.destination:
            return False
        if obj.is_typeclass("typeclasses.rooms.Room"):
            return False
        if isinstance(obj, DefaultCharacter):
            return False
        if Room._is_creature(obj):
            return False
        return True

    # ------------------------------------------------------------------
    # Display methods
    # ------------------------------------------------------------------

    def _get_ground_coins(self):
        """Return a string describing ground currency, or ''."""
        gold = self.attributes.get("ground_gold", default=0) or 0
        if gold:
            return f"{gold} gold"
        return ""

    def _get_weather_line(self):
        """Return the current weather line for this room, or ''."""
        from world.weather import format_weather_line
        return format_weather_line(self)

    def get_display_exits(self, looker, **kwargs):
        """
        Format the exit line in green with FULL direction names:
        |gObvious exits:|n southeast, north
        """
        from typeclasses.exits import normalize_direction

        exits = self.exits
        if not exits:
            return ""

        visible_exits = [
            ex for ex in exits
            if (ex.access(looker, "view") or ex.access(looker, "traverse"))
            and not (hasattr(ex, "is_hidden_door") and ex.is_hidden_door())
        ]
        if not visible_exits:
            return ""

        exit_names = []
        for ex in visible_exits:
            raw_name = ex.get_display_name(looker, **kwargs)
            full_name = normalize_direction(raw_name)
            exit_names.append(full_name)

        formatted_exits = ", ".join(f"|g{name}|n" for name in sorted(exit_names))
        return f"|gObvious exits:|n {formatted_exits}"

    def get_display_characters(self, looker, **kwargs):
        """
        Format characters/NPCs/mobs under a single |M Also here: |n header,
        ALL on one line, colour-coded:

          |425 mob_names    (pink)         — ALL mobs (hostile or passive)
          |y  player_names  (bright yellow) — player characters
          |W  npc_names     (grey)         — guards, vendors, guildmasters, tutorial NPCs
        """
        characters = [
            obj for obj in self.contents
            if self._is_creature(obj)
        ]
        if not characters:
            return ""

        mobs = []
        players = []
        npcs = []

        for char in characters:
            if char.has_account:
                players.append(char)
            elif self._is_mob_entity(char):
                mobs.append(char)
            else:
                npcs.append(char)

        entries = []

        for obj in mobs:
            entries.append(f"|425{obj.key}|n")

        for obj in players:
            entries.append(f"|y{obj.key}|n")

        for obj in npcs:
            entries.append(f"|W{obj.key}|n")

        if not entries:
            return ""

        # |M = dark magenta = purple
        return f"|MAlso here:|n {', '.join(entries)}"

    def get_display_things(self, looker, **kwargs):
        """
        Format items and currency lying on the ground, all on ONE line:

          |b You notice: |w Rusty Dagger, 45 gold|n
        """
        items = [obj for obj in self.contents if self._is_item(obj)]
        coins = self._get_ground_coins()

        if not items and not coins:
            return ""

        entries = []

        if items:
            for item in items:
                name = item.get_display_name(looker, **kwargs)
                entries.append(name)

        if coins:
            entries.append(coins)

        if not entries:
            return ""

        formatted = ", ".join(f"|w{entry}|n" for entry in entries)
        return f"|bYou notice:|n {formatted}"