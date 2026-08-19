"""
Admin Backup Command for 'rop'

Provides:
  CmdBackup  --  Manually trigger an instant database backup.

Usage:
  backup
  backup status

Admin-only command.  Requires the 'admin' permission.
"""

from commands.command import Command


class CmdBackup(Command):
    """
    Manually trigger an instant database backup.

    Usage:
      backup
      backup status

    The 'backup' command saves a timestamped copy of the database to
    the backups/ directory.  It also prunes any backups older than
    7 days to conserve disk space.

    Requires admin permission.

    An automated backup script also runs silently every 30 minutes.
    """

    key = "backup"
    aliases = []
    help_category = "Admin"
    locks = "cmd:perm(Admin)"
    auto_help = True

    def func(self):
        caller = self.caller
        args = self.args.strip().lower() if self.args else ""

        # "status" subcommand — show how many backups exist and disk usage
        if args == "status":
            self._show_status(caller)
            return

        # Default action: run a manual backup
        self._run_backup(caller)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_backup(self, caller):
        """Execute the manual backup and report the result."""
        from world.backup import run_manual_backup

        success, msg = run_manual_backup()
        if success:
            caller.msg(f"|g{msg}|n")
        else:
            caller.msg(f"|rBackup failed:|n {msg}")

    def _show_status(self, caller):
        """Display backup directory statistics."""
        import os
        from world.backup import BACKUP_DIR

        if not os.path.isdir(BACKUP_DIR):
            caller.msg(
                "|yNo backups found.|n The backups/ directory does not exist yet."
            )
            return

        files = sorted(
            [f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_") and f.endswith(".db")],
            reverse=True,
        )

        if not files:
            caller.msg("|yNo backups found.|n The backups/ directory is empty.")
            return

        total_size = sum(
            os.path.getsize(os.path.join(BACKUP_DIR, f)) for f in files
        )

        lines = []
        lines.append("|wDatabase Backup Status|n")
        lines.append("-" * 40)
        lines.append(f"|cTotal backups:|n {len(files)}")
        lines.append(f"|cTotal size:|n   {total_size / (1024*1024):.1f} MB")
        lines.append(f"|cLocation:|n     backups/")
        lines.append("")
        lines.append("|wMost recent backups:|n")

        for f in files[:5]:
            path = os.path.join(BACKUP_DIR, f)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            lines.append(f"  {f}  ({size_mb:.1f} MB)")

        caller.msg("\n".join(lines))