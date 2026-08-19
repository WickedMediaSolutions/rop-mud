"""
Realm Administration Commands for 'rop'
========================================

Provides:
  - CmdVerifyRealm  — ``@verifyrealm`` — walks the room graph, checks
                       zone mob density, faction exclusivity, boss
                       placement, and prints a detailed status report.
  - CmdPopulateRealm — ``@populaterealm`` — runs the full realm
                       population pipeline (misaligned cleanup, faction
                       territory stamping, zone mob population, boss
                       placement, town services).
"""

from commands.command import Command


class CmdSanitizeRooms(Command):
    """
    Strip debug suffixes from all room titles across the realm.

    Usage:
      @sanitizerooms [dryrun]

    Scans every room in the database and permanently removes
    parenthetical level tags, coordinate numbers, and location
    tracking suffixes from room titles.

    Examples of transformations:
      "Brimstone Courtyard (Starter 1-10) - Location 2" → "Brimstone Courtyard"
      "Sunspire Meadows (Starter 1-10) - Location 5"    → "Sunspire Meadows"
      "Rolling Plains of Aethelgard (73,16)"             → "Rolling Plains of Aethelgard"

    Zone metadata (level ranges, tier, coordinates) is extracted
    and stored as room attributes before the title is cleaned.

    Use ``dryrun`` to preview changes without modifying anything.
    """

    key = "@sanitizerooms"
    aliases = ["sanitizerooms", "cleanroomtitles", "fixtitles"]
    locks = "cmd:perm(Admin) or perm(Builder)"
    help_category = "Admin"
    auto_help = True

    def func(self):
        caller = self.caller
        args = (self.args or "").strip().lower()
        dry_run = args == "dryrun"

        mode = "|yDRY RUN|n (no changes)" if dry_run else "|gLIVE RUN|n (titles will be updated)"
        caller.msg(f"|Y[RoomSanitizer] Starting room title sanitization — {mode}|n")

        try:
            from world.room_titles import sanitize_all_rooms, format_sanitization_report
            summary = sanitize_all_rooms(dry_run=dry_run)
            report = format_sanitization_report(summary)
            caller.msg(report)
        except Exception as err:
            caller.msg(f"|r[RoomSanitizer] Sanitization failed: {err}|n")
            return

        # Notify builder channel
        try:
            from evennia import ChannelDB
            builder_channel = ChannelDB.objects.filter(db_key__iexact="builder").first()
            if builder_channel:
                action = "dry-run" if dry_run else "cleaned"
                builder_channel.msg(
                    f"[RoomSanitizer] {caller.key} {action} room titles: "
                    f"total={summary['total_rooms']} changed={summary['changed']}"
                )
        except Exception:
            pass


class CmdVerifyRealm(Command):
    """
    Run a comprehensive realm audit.

    Usage:
      @verifyrealm [full]

    Without arguments, performs a fast audit of zone populations,
    boss placement, faction alignment, and hub connectivity.

    With the ``full`` argument, also performs a BFS graph walk from
    each faction hub to verify zone reachability (expensive on large
    realms).

    Results are printed to the caller and also sent to the builder
    channel if available.
    """

    key = "@verifyrealm"
    aliases = ["verifyrealm", "checkspawns"]
    locks = "cmd:perm(Admin) or perm(Builder)"
    help_category = "Admin"
    auto_help = True

    def func(self):
        caller = self.caller
        args = (self.args or "").strip().lower()
        full_walk = args == "full"

        caller.msg("|Y[RealmAudit] Running realm verification...|n")

        try:
            from world.realm_verify import verify_realm
            result = verify_realm(full_walk=full_walk)
        except Exception as err:
            caller.msg(f"|r[RealmAudit] Verification failed: {err}|n")
            return

        # Send report to caller
        caller.msg(result["report"])

        # Summary line to builder channel
        summary = result.get("summary", {})
        issues = result.get("issues", [])
        criticals = sum(1 for i in issues if i["severity"] == "critical")
        warnings = sum(1 for i in issues if i["severity"] == "warning")
        infos = sum(1 for i in issues if i["severity"] == "info")

        status = "|gCLEAN|n" if not issues else f"|r{criticals}C {warnings}W {infos}I|n"
        try:
            from evennia import ChannelDB
            builder_channel = ChannelDB.objects.filter(db_key__iexact="builder").first()
            if builder_channel:
                builder_channel.msg(
                    f"[RealmAudit] {caller.key} verified realm: "
                    f"zones={summary.get('zones_audited', 0)} "
                    f"bosses={summary.get('bosses', {}).get('present', 0)}/"
                    f"{summary.get('bosses', {}).get('total', 0)} "
                    f"misaligned={summary.get('misaligned_mobs', 0)} "
                    f"issues={status}"
                )
        except Exception:
            pass


class CmdPopulateRealm(Command):
    """
    Run the full realm population pipeline.

    Usage:
      @populaterealm [noclean]

    This command:
      1. Removes misaligned spawns (Evil mobs in Good zones and vice versa).
      2. Stamps faction territory and alignment restrictions on every zone room.
      3. Builds faction city services and starter-zone vendors/trainers.
      4. Populates every zone with level-appropriate XP mobs.
      5. Populates faction towns with guards, vendors, and trainers.
      6. Links faction cities to their 1-10 newbie zones.
      7. Places all 30 registered bosses into their lairs.

    Use ``noclean`` to skip the misaligned spawn cleanup step.

    WARNING: This operation can create thousands of database objects.
    It is idempotent — existing alive mobs are counted before topping
    rooms up, so it is safe to run multiple times.
    """

    key = "@populaterealm"
    aliases = ["populaterealm", "poprealm"]
    locks = "cmd:perm(Admin) or perm(Builder)"
    help_category = "Admin"
    auto_help = True

    def func(self):
        caller = self.caller
        args = (self.args or "").strip().lower()
        clear_misaligned = "noclean" not in args

        caller.msg("|Y[RealmPop] Starting full realm population pipeline...|n")
        caller.msg("|WThis may take a while depending on realm size.|n")

        try:
            from world.realm_population import populate_realm
            report = populate_realm(clear_misaligned=clear_misaligned)
        except Exception as err:
            caller.msg(f"|r[RealmPop] Population failed: {err}|n")
            return

        # Build a human-readable summary
        lines = []
        lines.append("|Y" + "=" * 60 + "|n")
        lines.append("|cREALM POPULATION COMPLETE|n")
        lines.append("|Y" + "=" * 60 + "|n")

        if clear_misaligned:
            m = report.get("misaligned", {})
            lines.append(f"  |wMisaligned Cleanup:|n {m.get('removed', 0)} mobs removed")

        t = report.get("territory", {})
        lines.append(f"  |wTerritory Stamped:|n "
                     f"Good={t.get('good', 0)} Evil={t.get('evil', 0)} "
                     f"Neutral={t.get('neutral', 0)} "
                     f"(restricted: G={t.get('restricted_good', 0)} E={t.get('restricted_evil', 0)})")

        s = report.get("starters", {})
        lines.append(f"  |wStarter Services:|n "
                     f"Good vendors={s.get('good_vendors', 0)} trainers={s.get('good_trainers', 0)}  "
                     f"Evil vendors={s.get('evil_vendors', 0)} trainers={s.get('evil_trainers', 0)}")

        z = report.get("zones", {})
        lines.append(f"  |wZone Population:|n "
                     f"{z.get('zones', 0)} zones, {z.get('rooms', 0)} rooms, "
                     f"{z.get('spawned', 0)} mobs spawned "
                     f"({z.get('skipped_safe', 0)} safe rooms skipped)")

        tw = report.get("towns", {})
        lines.append(f"  |wFaction Towns:|n "
                     f"Good={tw.get('good_towns', 0)} Evil={tw.get('evil_towns', 0)} "
                     f"NPCs={tw.get('npcs', 0)}")

        lk = report.get("links", {})
        lines.append(f"  |wStarter Links:|n {lk.get('linked', 0)} exits created")

        b = report.get("bosses", {})
        lines.append(f"  |wBosses:|n {b.get('placed', 0)} placed "
                     f"(missing lair={b.get('missing_lair', 0)} "
                     f"missing registry={b.get('missing_registry', 0)})")

        lines.append("|Y" + "=" * 60 + "|n")

        caller.msg("\n".join(lines))

        # Notify builder channel
        try:
            from evennia import ChannelDB
            builder_channel = ChannelDB.objects.filter(db_key__iexact="builder").first()
            if builder_channel:
                builder_channel.msg(
                    f"[RealmPop] {caller.key} populated realm: "
                    f"zones={z.get('zones', 0)} mobs={z.get('spawned', 0)} "
                    f"bosses={b.get('placed', 0)}"
                )
        except Exception:
            pass