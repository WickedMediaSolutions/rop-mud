"""
Admin Tools Commands for 'rop' — Phase 10

Provides:
  - CmdAuditLog     — @auditlog [count] [admin=<name>] [action=<verb>] [clear]
  - CmdPerfMon      — @perfmon [reset|scripts|objects]
  - CmdModeration   — delegates to @ban/@unban/@mute/@unmute/@banlist/@kick

All commands are Admin-gated.
"""

from __future__ import annotations

from commands.command import Command


class CmdAuditLog(Command):
    """
    View or manage the administrative audit trail.

    Usage:
      @auditlog [count]
      @auditlog admin=<name>
      @auditlog action=<verb>
      @auditlog clear

    Without arguments, shows the 50 most recent administrative actions.
    Use ``admin=`` to filter by administrator name and ``action=`` to
    filter by action type (ban, unban, mute, unmute, kick, reload, etc).

    ``@auditlog clear`` purges the entire audit trail.

    Available to administrators only.
    """

    key = "@auditlog"
    aliases = ["auditlog", "@audit"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"
    auto_help = True

    def parse(self):
        self.args_raw = (self.args or "").strip()

    def func(self):
        caller = self.caller
        args = self.args_raw

        from world.admin_log import (
            get_recent_actions,
            get_actions_by_admin,
            get_actions_by_type,
            clear_audit_log,
            format_entry,
            get_total_count,
        )

        # Clear command
        if args.lower() == "clear":
            removed = clear_audit_log()
            caller.msg(f"|gCleared {removed} audit log entries.|n")
            return

        # Filter parsing
        admin_filter = None
        action_filter = None
        count = 50

        for part in args.split():
            if part.startswith("admin="):
                admin_filter = part.split("=", 1)[1]
            elif part.startswith("action="):
                action_filter = part.split("=", 1)[1]
            else:
                try:
                    count = max(1, min(200, int(part)))
                except ValueError:
                    pass

        # Retrieve entries
        if admin_filter:
            entries = get_actions_by_admin(admin_filter, limit=count)
            header = f"|cAudit Log — admin={admin_filter}|n"
        elif action_filter:
            entries = get_actions_by_type(action_filter, limit=count)
            header = f"|cAudit Log — action={action_filter}|n"
        else:
            entries = get_recent_actions(limit=count)
            header = f"|cAudit Log — {len(entries)} most recent|n"

        total = get_total_count()

        lines = []
        lines.append("|Y" + "=" * 65 + "|n")
        lines.append(f"|c|h              ADMINISTRATIVE AUDIT TRAIL|n")
        lines.append(f"  {header}  (total: {total})")
        lines.append("|Y" + "=" * 65 + "|n")

        if not entries:
            lines.append("  |yNo audit entries found.|n")
        else:
            for entry in entries:
                lines.append("  " + format_entry(entry))

        lines.append("|Y" + "=" * 65 + "|n")

        caller.msg("\n".join(lines))


class CmdPerfMon(Command):
    """
    Display real-time server performance metrics.

    Usage:
      @perfmon
      @perfmon reset
      @perfmon scripts
      @perfmon objects

    Shows uptime, command execution stats, section timings, entity
    counts, and active combat/mob-tick counters.

    ``reset`` clears collected metrics.
    ``scripts`` lists currently running global scripts.
    ``objects`` lists the most recently modified objects.

    Available to administrators only.
    """

    key = "@perfmon"
    aliases = ["perfmon", "@perf", "@metrics"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"
    auto_help = True

    def parse(self):
        self.args_raw = (self.args or "").strip().lower()

    def func(self):
        caller = self.caller
        args = self.args_raw

        from world import performance as perf

        if args == "reset":
            perf.reset_metrics()
            caller.msg("|gPerformance metrics reset.|n")
            return

        if args == "scripts":
            scripts = perf.get_running_scripts()
            lines = []
            lines.append("|Y" + "=" * 65 + "|n")
            lines.append("|c|h              RUNNING GLOBAL SCRIPTS|n")
            lines.append("|Y" + "=" * 65 + "|n")
            if not scripts:
                lines.append("  |yNo active global scripts found.|n")
            else:
                lines.append(
                    f"|W{'Key':<28} {'Type':<40} {'Int':>6} {'Rep':>4}|n"
                )
                for s in scripts:
                    lines.append(
                        f"  {s['key'][:28]:<28} {s['typeclass'][:40]:<40} "
                        f"{s['interval']:>6} {s['repeats']:>4}"
                    )
            lines.append("|Y" + "=" * 65 + "|n")
            caller.msg("\n".join(lines))
            return

        if args == "objects":
            objs = perf.get_top_objects(limit=15)
            lines = []
            lines.append("|Y" + "=" * 65 + "|n")
            lines.append("|c|h              MOST ACTIVE OBJECTS|n")
            lines.append("|Y" + "=" * 65 + "|n")
            if not objs:
                lines.append("  |yNo objects found.|n")
            else:
                for o in objs:
                    lines.append(
                        f"  {o['dbref']} |w{o['key'][:30]}|n "
                        f"({o['typeclass'][:35]})"
                    )
            lines.append("|Y" + "=" * 65 + "|n")
            caller.msg("\n".join(lines))
            return

        # Default: full metrics snapshot
        metrics = perf.get_server_metrics()

        # Format uptime
        uptime = metrics.get("uptime_seconds", 0)
        days = int(uptime // 86400)
        hours = int((uptime % 86400) // 3600)
        mins = int((uptime % 3600) // 60)
        secs = int(uptime % 60)
        uptime_str = f"{days}d {hours}h {mins}m {secs}s"

        lines = []
        lines.append("|Y" + "=" * 65 + "|n")
        lines.append("|c|h              SERVER PERFORMANCE METRICS|n")
        lines.append("|Y" + "=" * 65 + "|n")
        lines.append(f"  |wUptime:|n {uptime_str}")
        lines.append(f"  |wCommands executed:|n {metrics.get('command_count', 0)}")
        lines.append(f"  |wCombat rounds:|n {metrics.get('combat_rounds', 0)}")
        lines.append(f"  |wMob AI ticks:|n {metrics.get('mob_tick_count', 0)}")
        lines.append(f"  |wNetwork messages:|n {metrics.get('network_msgs', 0)}")

        # Entity counts
        ec = {k: v for k, v in metrics.items() if k in (
            "objects", "scripts", "accounts", "channels", "messages", "players"
        )}
        if ec:
            lines.append("")
            lines.append("|w|h  ENTITY COUNTS|n")
            for key, val in sorted(ec.items()):
                lines.append(f"  |w{key.capitalize()}:|n {val}")

        # Top commands
        top_commands = metrics.get("top_commands", [])
        if top_commands:
            lines.append("")
            lines.append("|w|h  TOP COMMANDS BY TOTAL TIME|n")
            lines.append(
                f"|W  {'Command':<18} {'Count':>7} {'Avg(ms)':>9} {'Max(ms)':>9}|n"
            )
            for c in top_commands[:10]:
                avg_ms = c["avg"] * 1000
                max_ms = c["max"] * 1000
                lines.append(
                    f"  {c['command'][:18]:<18} {c['count']:>7} "
                    f"{avg_ms:>9.2f} {max_ms:>9.2f}"
                )

        # Section timings
        sections = metrics.get("section_timings", [])
        if sections:
            lines.append("")
            lines.append("|w|h  SECTION TIMINGS|n")
            lines.append(
                f"|W  {'Section':<24} {'Count':>7} {'Avg(ms)':>9} {'Max(ms)':>9}|n"
            )
            for s in sections[:10]:
                avg_ms = s["avg"] * 1000
                max_ms = s["max"] * 1000
                lines.append(
                    f"  {s['section'][:24]:<24} {s['count']:>7} "
                    f"{avg_ms:>9.2f} {max_ms:>9.2f}"
                )

        lines.append("")
        lines.append("|Y" + "=" * 65 + "|n")
        lines.append("|yUse @perfmon reset|scripts|objects for more options.|n")

        caller.msg("\n".join(lines))