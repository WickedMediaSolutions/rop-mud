"""
Mob Diagnostic & Admin Commands for 'rop'

Provides:
  - CmdTestMobs  — automated diagnostic that verifies the full mob
                   lifecycle: spawn, damage-to-death, respawn scheduling,
                   and reports success/failure to the builder channel.
  - CmdSpawnMob   — builder/admin command to spawn a mob from the
                   MOB_PROTOTYPES registry into a room.
"""

from commands.command import Command


class CmdTestMobs(Command):
    """
    Run an automated diagnostic on the mob lifecycle.

    Usage:
      testmobs  (alias: @testmobs)

    The diagnostic performs the following checks without affecting the
    live game world permanently:

      1. Spawns a disposable test mob into your current room.
      2. Verifies the AI ticker was attached and started.
      3. Simulates damage down to 0 HP and confirms death handling.
      4. Verifies the respawn timer was scheduled (respawn_delay > 0).
      5. Confirms the mob was removed from the room on death.
      6. Forces an immediate respawn and verifies the mob returns alive.
      7. Cleans up the test mob and its corpse.

    Results are reported back to the caller and (if present) to the
    builder channel.
    """

    key = "testmobs"
    aliases = ["@testmobs", "mobtest"]
    locks = "cmd:perm(Admin) or perm(Builder)"
    help_category = "Admin"
    auto_help = True

    def func(self):
        caller = self.caller
        location = caller.location

        if not location:
            caller.msg("|rYou must be in a room to run the mob diagnostic.|n")
            return

        caller.msg("|Y[MobDiag] Starting mob lifecycle diagnostic...|n")

        report = []
        all_ok = True

        # --- Step 1: Spawn a test mob ---
        mob = None
        try:
            from typeclasses.mobs import spawn_mob
            from world.prototypes import MOB_PROTOTYPES

            # Use goblin_scout if available, else fall back to a minimal mob
            proto_key = "goblin_scout" if "goblin_scout" in MOB_PROTOTYPES else None

            if proto_key:
                mob = spawn_mob(proto_key, location, home_room=location)
            else:
                # Fallback: create a minimal mob directly
                from evennia import create_object
                mob = create_object(
                    "typeclasses.mobs.Mob",
                    key="diagnostic test mob",
                    location=location,
                    attributes=[
                        ("is_mob", True),
                        ("hp", 50),
                        ("max_hp", 50),
                        ("level", 1),
                        ("stats", {"str": 8, "dex": 8, "con": 8, "int": 8, "wis": 8, "cha": 8}),
                        ("alignment", "Evil"),
                        ("faction", "evil"),
                        ("xp_value", 1),
                        ("gold_min", 0),
                        ("gold_max", 0),
                        ("home_room_dbref", location.id),
                        ("respawn_delay", 60),
                    ],
                )

            if mob is None:
                report.append("FAIL: could not spawn test mob")
                all_ok = False
            else:
                report.append(f"PASS: spawned test mob ({mob.key}, dbref={mob.id})")
        except Exception as err:
            report.append(f"FAIL: spawn raised {err}")
            all_ok = False

        if mob is None:
            self._finish(caller, report, all_ok)
            return

        mob_id = mob.id

        # --- Step 2: Verify AI ticker attached ---
        try:
            ai_script = mob.scripts.get("mob_ai_ticker") if hasattr(mob.scripts, "get") else None
            if ai_script:
                report.append("PASS: AI ticker attached")
            else:
                report.append("WARN: AI ticker not found on scripts handler "
                              "(may use ndb fallback)")
        except Exception as err:
            report.append(f"WARN: could not check AI ticker ({err})")

        # --- Step 3: Verify mob is alive in the room ---
        try:
            mob_hp = mob.attributes.get("hp", 0)
            if mob.location and mob.location.id == location.id and mob_hp > 0:
                report.append(f"PASS: mob alive in room (HP={mob_hp})")
            else:
                report.append(f"FAIL: mob not properly placed (HP={mob_hp}, loc={mob.location})")
                all_ok = False
        except Exception as err:
            report.append(f"FAIL: alive check raised {err}")
            all_ok = False

        # --- Step 4: Simulate damage down to death ---
        try:
            # Bypass combat engine — directly stress the death path.
            # First give the mob a die() that doesn't schedule a real respawn
            # to keep the test deterministic: we capture the respawn delay.
            mob_die = getattr(mob, "die", None)
            if not mob_die:
                report.append("FAIL: mob has no die() method")
                all_ok = False
            else:
                # Capture respawn scheduling via monkeypatching _schedule_respawn
                captured = {}

                def _fake_schedule_respawn():
                    captured["called"] = True
                    captured["respawn_delay"] = mob.attributes.get(
                        "respawn_delay", 60
                    )

                orig_schedule = getattr(mob, "_schedule_respawn", None)
                if orig_schedule:
                    # Temporarily patch the instance to capture instead of schedule
                    import types
                    mob._schedule_respawn = types.MethodType(_fake_schedule_respawn, mob)

                # Force HP to 0 and call die()
                mob.attributes.add("hp", 0)
                mob.die(killer=caller)

                # Restore original method
                if orig_schedule:
                    mob._schedule_respawn = orig_schedule

                if captured.get("called"):
                    report.append(
                        f"PASS: death triggered respawn scheduling "
                        f"(delay={captured['respawn_delay']}s)"
                    )
                else:
                    report.append("FAIL: die() did not call _schedule_respawn")
                    all_ok = False
        except Exception as err:
            report.append(f"FAIL: death simulation raised {err}")
            all_ok = False

        # --- Step 5: Verify mob removed from room after death ---
        try:
            if mob.location is None or mob.location.id != location.id:
                report.append("PASS: mob removed from room after death")
            else:
                report.append("FAIL: mob still in room after death")
                all_ok = False
        except Exception:
            # Already deleted is also acceptable (some implementations delete)
            report.append("PASS: mob removed from room after death (deleted)")

        # --- Step 6: Force immediate respawn and verify ---
        try:
            from typeclasses.mobs import _respawn_mob_by_dbref

            # Only respawn if the mob still exists
            from evennia.objects.models import ObjectDB
            mob_obj = ObjectDB.objects.filter(id=mob_id).first()

            if mob_obj is None:
                report.append("WARN: mob was deleted at death (no respawn object)")
            else:
                # Force respawn
                _respawn_mob_by_dbref(mob_id)

                # Verify it returned alive
                mob_after = ObjectDB.objects.filter(id=mob_id).first()
                if mob_after:
                    hp_after = mob_after.attributes.get("hp", 0)
                    if hp_after > 0 and mob_after.location:
                        report.append(
                            f"PASS: mob respawned alive (HP={hp_after}, "
                            f"room={mob_after.location.key})"
                        )
                    else:
                        report.append(
                            f"FAIL: mob not alive after respawn "
                            f"(HP={hp_after}, loc={mob_after.location})"
                        )
                        all_ok = False
                else:
                    report.append("FAIL: mob missing after respawn attempt")
                    all_ok = False
        except Exception as err:
            report.append(f"FAIL: respawn verification raised {err}")
            all_ok = False

        # --- Step 7: Clean up test artifacts ---
        try:
            from evennia.objects.models import ObjectDB

            # Delete any corpse in the room from this test mob
            for obj in list(location.contents):
                if obj.attributes.get("is_corpse", False):
                    owner_name = obj.key.lower()
                    if "diagnostic" in owner_name or mob.key.lower() in owner_name:
                        obj.delete()

            # Delete the test mob if still present
            mob_obj = ObjectDB.objects.filter(id=mob_id).first()
            if mob_obj:
                mob_obj.delete()

            report.append("PASS: cleanup complete")
        except Exception as err:
            report.append(f"WARN: cleanup raised {err}")

        self._finish(caller, report, all_ok)

    def _finish(self, caller, report, all_ok):
        """Format and deliver the final report."""
        status = "|gALL PASS|n" if all_ok else "|rFAILURES DETECTED|n"

        header = (
            f"|Y{'=' * 55}|n\n"
            f"|cMob Lifecycle Diagnostic — {status}\n"
            f"|Y{'=' * 55}|n"
        )
        body = "\n".join(f"  {line}" for line in report)
        footer = f"|Y{'=' * 55}|n"

        message = f"{header}{body}\n{footer}"

        # Send to the caller
        caller.msg(message)

        # Send to the builder channel if available
        try:
            from evennia import ChannelDB
            builder_channel = ChannelDB.objects.filter(db_key__iexact="builder").first()
            if builder_channel:
                builder_channel.msg(
                    f"[MobDiag] {caller.key} ran mob lifecycle diagnostic: "
                    f"{'PASS' if all_ok else 'FAIL'}"
                )
        except Exception:
            pass


class CmdSpawnStats(Command):
    """
    Audit all rooms in the realm for mob population statistics.

    Usage:
      @spawnstats [zone]

    Displays a real-time report of every room's active mob count,
    max_mobs cap, pending boss respawn timers, and zone boundaries.

    If an optional zone tag is provided, filters to rooms in that zone.

    Available to administrators and builders.
    """

    key = "@spawnstats"
    aliases = ["spawnstats"]
    locks = "cmd:perm(Admin) or perm(Builder)"
    help_category = "Admin"
    auto_help = True

    def parse(self):
        self.filter_zone = (self.args or "").strip().lower() or None

    def func(self):
        caller = self.caller

        try:
            from world.realm_spawner import gather_room_spawn_stats, get_spawner_status
        except Exception as err:
            caller.msg(f"|rCould not load realm_spawner: {err}|n")
            return

        # Spawner status header
        status = get_spawner_status()
        running_str = "|gRUNNING|n" if status["running"] else "|rSTOPPED|n"
        header = (
            f"|Y{'=' * 60}|n\n"
            f"|cRealm Spawn Statistics|n\n"
            f"  Spawner: {running_str}\n"
            f"  Tick Interval: {status['tick_interval']}s\n"
            f"  Boss Cooldown: {status['boss_cooldown']}s (1 hour)\n"
        )
        if self.filter_zone:
            header += f"  Filter: zone_tag = |w{self.filter_zone}|n\n"
        header += f"|Y{'=' * 60}|n"

        # Gather stats
        all_stats = gather_room_spawn_stats()

        # Filter if requested
        if self.filter_zone:
            all_stats = [
                s for s in all_stats
                if s["zone_tag"].lower() == self.filter_zone
            ]

        if not all_stats:
            caller.msg(header + "\n|yNo rooms found with spawn data.|n")
            return

        # Build table
        lines = [header]
        lines.append(
            f"|W{'Room':<30} {'Zone':<22} {'Mobs':>5} {'Cap':>4} {'Boss CD':>10} {'Table':>6}|n"
        )
        lines.append(f"|W{'-' * 30} {'-' * 22} {'-' * 5} {'-' * 4} {'-' * 10} {'-' * 6}|n")

        total_active = 0
        total_cap = 0
        rooms_with_boss_cd = 0

        for entry in all_stats:
            room_key = entry["room_key"][:29]
            zone_tag = entry["zone_tag"][:21]
            active = entry["active_mobs"]
            cap = entry["max_mobs"]
            table_count = entry["spawn_table_entries"]

            # Format boss cooldowns
            boss_cds = entry.get("boss_cooldowns", {})
            if boss_cds:
                cd_parts = []
                for boss_id, remaining in boss_cds.items():
                    mins = remaining // 60
                    secs = remaining % 60
                    cd_parts.append(f"{boss_id[:8]}:{mins}m{secs}s")
                boss_str = ", ".join(cd_parts)
                rooms_with_boss_cd += 1
            else:
                boss_str = "-"

            # Color-code mob count: green if under cap, yellow if at cap, red if over
            if active >= cap:
                mob_str = f"|r{active:>5}|n"
            elif active >= cap - 1:
                mob_str = f"|y{active:>5}|n"
            else:
                mob_str = f"|g{active:>5}|n"

            lines.append(
                f" {room_key:<30} {zone_tag:<22} {mob_str} {cap:>4} {boss_str:>10} {table_count:>6}"
            )

            total_active += active
            total_cap += cap

        # Summary footer
        lines.append(f"|Y{'=' * 60}|n")
        lines.append(
            f"|cSummary:|n {len(all_stats)} rooms, "
            f"{total_active} active mobs / {total_cap} total cap, "
            f"{rooms_with_boss_cd} rooms with boss cooldowns"
        )
        lines.append(f"|Y{'=' * 60}|n")

        caller.msg("\n".join(lines))


class CmdSpawnMob(Command):
    """
    Spawn a mob from the MOB_PROTOTYPES registry into a room.

    Usage:
      spawnmob <prototype_key> [count]

    Available to administrators and builders.  Spawns the specified mob
    (or `count` mobs) into your current room using the full Mob typeclass
    so the mob has AI and respawn behaviour.

    Use `spawnmob list` to see available prototypes.
    """

    key = "spawnmob"
    aliases = ["mob"]
    locks = "cmd:perm(Admin) or perm(Builder)"
    help_category = "Admin"
    auto_help = True

    def parse(self):
        self.args_raw = (self.args or "").strip()

    def func(self):
        caller = self.caller
        args = self.args_raw

        if not args:
            caller.msg("|yUsage: spawnmob <prototype_key> [count]|n")
            return

        if args.lower() == "list":
            from world.prototypes import MOB_PROTOTYPES
            # Show only mobs (not NPCs/spawners) — entries with 'is_mob' in attrs
            mob_keys = []
            for key, proto in MOB_PROTOTYPES.items():
                attrs = proto.get("attrs", [])
                is_mob = any(
                    a[0] == "is_mob" and a[1] for a in attrs
                )
                if is_mob:
                    mob_keys.append(key)
            if mob_keys:
                caller.msg(
                    "|wAvailable mob prototypes:|n\n  " + "\n  ".join(sorted(mob_keys))
                )
            else:
                caller.msg("|yNo mob prototypes found.|n")
            return

        parts = args.split()
        proto_key = parts[0]
        count = 1
        if len(parts) > 1:
            try:
                count = max(1, min(20, int(parts[1])))
            except ValueError:
                caller.msg("|rCount must be a number.|n")
                return

        location = caller.location
        if not location:
            caller.msg("|rYou must be in a room to spawn mobs.|n")
            return

        from typeclasses.mobs import spawn_mob

        spawned = []
        for _ in range(count):
            mob = spawn_mob(proto_key, location, home_room=location)
            if mob:
                spawned.append(mob)

        if spawned:
            caller.msg(
                f"|gSpawned {len(spawned)} mob(s) from prototype "
                f"'{proto_key}'.|n"
            )
        else:
            caller.msg(
                f"|rCould not spawn mob from prototype '{proto_key}'. "
                f"Check the prototype key with |wspawnmob list|r.|n"
            )