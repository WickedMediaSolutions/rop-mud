"""
Admin & Builder Commands for 'rop' — Phase 6.10

Provides:
  - CmdReload   — soft-reload the Evennia server (Admin)
  - CmdGoto     — teleport to a room / player (Admin)
  - CmdSpawn    — spawn a prototype (Admin / Builder)
  - CmdSet      — view/set an attribute on an object (Admin)

All commands are permission-gated via Evennia lock strings so they are
automatically restricted to the Admin / Builder permission groups.
"""

from commands.command import Command


class CmdReload(Command):
    """
    Soft-reload the Evennia server.

    Usage:
      reload

    Available to administrators only. This performs an Evennia server
    reload without dropping connected players, reloading all typeclasses,
    modules, and hooks. Use carefully — any unsaved changes are lost.
    """

    key = "reload"
    aliases = ["rld"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"
    auto_help = True

    def func(self):
        caller = self.caller
        caller.msg("|YSoft-reloading the server...|n")
        try:
            import evennia
            evennia.SESSION_HANDLER.announce_all(
                "|Y[Server] Soft reload initiated by an administrator.|n"
            )
            evennia.SESSION_HANDLER.portal_restart_server()
        except Exception as err:
            caller.msg(f"|rReload failed: {err}|n")


class CmdGoto(Command):
    """
    Teleport to a room or player.

    Usage:
      goto <room | player>

    Available to administrators only. Searches for the target by key or
    dbref and moves you there immediately, displaying the destination's
    appearance.
    """

    key = "goto"
    aliases = ["gt"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"
    auto_help = True

    def parse(self):
        self.target = (self.args or "").strip()

    def func(self):
        caller = self.caller
        if not self.target:
            caller.msg("|yUsage: goto <room or player>|n")
            return

        from evennia import search_object
        results = search_object(self.target)

        if not results:
            caller.msg(f"|rCannot find '{self.target}'.|n")
            return

        destination = results[0]

        # If target is a player, go to their location
        if hasattr(destination, "location") and destination.location:
            destination = destination.location

        if not destination:
            caller.msg("|rThat target has no location to go to.|n")
            return

        caller.msg(f"|gYou teleport to {destination.key}.|n")
        caller.move_to(destination, quiet=False)
        caller.msg(destination.return_appearance(caller))


class CmdSpawn(Command):
    """
    Spawn an object from a prototype.

    Usage:
      spawn <prototype_key> [in <location>]

    Available to administrators and builders. The prototype is looked up
    in the game's prototype registry (module or db prototypes). If a
    location is omitted, the object spawns in your current room.
    """

    key = "spawn"
    aliases = ["sp"]
    locks = "cmd:perm(Admin) or perm(Builder)"
    help_category = "Admin"
    auto_help = True

    def parse(self):
        self.args_raw = (self.args or "").strip()

    def func(self):
        caller = self.caller
        args = self.args_raw

        if not args:
            caller.msg("|yUsage: spawn <prototype_key> [in <location>]|n")
            return

        location = caller.location
        proto_key = args

        # Optional "in <location>" suffix
        if " in " in args.lower():
            head, loc_name = args.lower().split(" in ", 1)
            proto_key = head.strip()
            loc_name = loc_name.strip()
            from evennia import search_object
            loc_results = search_object(loc_name)
            if loc_results:
                location = loc_results[0]
            else:
                caller.msg(f"|rCannot find location '{loc_name}'.|n")
                return

        from evennia.prototypes import spawner
        try:
            spawned_objects = list(spawner.spawn(proto_key, caller=caller))
        except Exception as err:
            caller.msg(f"|rSpawn failed: {err}|n")
            return

        if not spawned_objects:
            caller.msg(f"|yPrototype '{proto_key}' produced no objects.|n")
            return

        for obj in spawned_objects:
            if location is not None:
                obj.location = location
            caller.msg(f"|gSpawned {obj.get_display_name(caller)}.|n")
        caller.msg(
            f"|gSpawned {len(spawned_objects)} object(s) from prototype "
            f"'{proto_key}'.|n"
        )


class CmdSet(Command):
    """
    View or set an attribute on an object.

    Usage:
      set <target> <attribute>
      set <target> <attribute> = <value>

    Available to administrators and builders. With no '=' the command
    shows the current value; with '=' it assigns the new value (numeric
    values are auto-converted). Values of "true"/"false" are stored as
    booleans.
    """

    key = "set"
    aliases = ["attr"]
    locks = "cmd:perm(Admin) or perm(Builder)"
    help_category = "Admin"
    auto_help = True

    def parse(self):
        self.args_raw = (self.args or "").strip()

    def func(self):
        caller = self.caller
        args = self.args_raw

        if not args:
            caller.msg("|yUsage: set <target> <attribute> [= <value>]|n")
            return

        if "=" in args:
            lhs, raw_value = args.split("=", 1)
            lhs = lhs.strip()
            raw_value = raw_value.strip()
        else:
            lhs = args
            raw_value = None

        parts = lhs.split()
        if len(parts) < 2:
            caller.msg("|yUsage: set <target> <attribute> [= <value>]|n")
            return

        target_name = parts[0]
        attr_name = parts[1]

        from evennia import search_object
        results = search_object(target_name)
        if not results:
            caller.msg(f"|rCannot find '{target_name}'.|n")
            return

        obj = results[0]

        if raw_value is None:
            # Read mode
            current = obj.attributes.get(attr_name, default=None)
            caller.msg(f"|w{obj.key}.{attr_name}|n = |c{current!r}|n")
            return

        # Write mode: coerce value
        value = self._coerce_value(raw_value)
        obj.attributes.add(attr_name, value)
        caller.msg(f"|gSet {obj.key}.{attr_name} = {value!r}|n")

    def _coerce_value(self, raw_value):
        """Coerce a string value to int/float/bool where appropriate."""
        lowered = raw_value.lower()
        if lowered in ("true", "yes", "on"):
            return True
        if lowered in ("false", "no", "off"):
            return False

        try:
            return int(raw_value)
        except ValueError:
            pass

        try:
            return float(raw_value)
        except ValueError:
            pass

        return raw_value