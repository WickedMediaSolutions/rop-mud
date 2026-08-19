"""
Automated Database Backup System for 'rop'

Provides:
  - BackupScript: A persistent Evennia Script that backs up the SQLite
    database every 30 minutes to a dedicated backups/ folder.  Backups
    older than 7 days are automatically pruned to conserve disk space.

  - run_manual_backup(): Utility function that performs an *immediate*
    backup (used by the admin 'backup' command and by the script's
    at_repeat() ticker).  Returns (success_bool, message_string).

To start the automatic backup ticker after a server launch, use:
    from world.backup import BackupScript
    BackupScript.create("auto_backup_script", interval=1800, autostart=True)

To trigger a one-off backup manually, call:
    from world.backup import run_manual_backup
    ok, msg = run_manual_backup()
"""

import os
import shutil
import time
from datetime import datetime, timedelta

from evennia.scripts.scripts import DefaultScript

# ---------------------------------------------------------------------------
# Configurable constants
# ---------------------------------------------------------------------------
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "backups")
DB_SOURCE = os.path.join(os.path.dirname(__file__), "..", "server", "evennia.db3")
MAX_AGE_HOURS = 7 * 24  # 7 days


def _ensure_backup_dir():
    """Create the backup directory if it doesn't already exist."""
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _timestamp() -> str:
    """Return a compact UTC timestamp suitable for filenames, e.g. '2026-08-12_1445'."""
    return datetime.utcnow().strftime("%Y-%m-%d_%H%M")


def _cleanup_old_backups():
    """
    Retention policy: keep last 24 hourly backups + 7 daily backups.

    Strategy:
      1. Collect all backup files with their mtimes.
      2. Sort by mtime descending (newest first).
      3. For each file, determine if it qualifies as an "hourly" keeper
         (one per hour for the last 24 hours) or a "daily" keeper
         (one per day for the last 7 days).
      4. Delete any file that doesn't qualify for either bucket.
    """
    removed = 0
    if not os.path.isdir(BACKUP_DIR):
        return removed

    # Collect backup files with mtimes
    backups = []
    for filename in os.listdir(BACKUP_DIR):
        path = os.path.join(BACKUP_DIR, filename)
        if not os.path.isfile(path):
            continue
        if not filename.startswith("backup_") or not filename.endswith(".db"):
            continue
        backups.append((path, os.path.getmtime(path)))

    if not backups:
        return removed

    # Sort by mtime descending (newest first)
    backups.sort(key=lambda x: x[1], reverse=True)

    now = time.time()
    HOUR = 3600
    DAY = 86400

    # Track which hourly and daily slots we've already filled
    kept_hours = set()   # hour-of-day timestamps (floored to hour)
    kept_days = set()    # day timestamps (floored to day)

    keep = set()

    for path, mtime in backups:
        age = now - mtime

        # Hourly bucket: keep one per hour for the last 24 hours
        if age <= 24 * HOUR:
            hour_slot = int(mtime // HOUR)
            if hour_slot not in kept_hours:
                kept_hours.add(hour_slot)
                keep.add(path)
                continue

        # Daily bucket: keep one per day for the last 7 days
        if age <= 7 * DAY:
            day_slot = int(mtime // DAY)
            if day_slot not in kept_days:
                kept_days.add(day_slot)
                keep.add(path)
                continue

    # Delete files not in the keep set
    for path, _mtime in backups:
        if path not in keep:
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass

    return removed


def run_manual_backup() -> tuple:
    """
    Perform a single database backup immediately.

    Returns:
        (success: bool, message: str) — success is True when the backup
        file was written to disk, False otherwise.
    """
    _ensure_backup_dir()

    if not os.path.isfile(DB_SOURCE):
        return False, (
            f"Database file not found at {DB_SOURCE}.  "
            "Verify Evennia is configured and the database exists."
        )

    dest_name = f"backup_{_timestamp()}.db"
    dest_path = os.path.join(BACKUP_DIR, dest_name)

    try:
        shutil.copy2(DB_SOURCE, dest_path)
    except (OSError, IOError) as err:
        return False, f"Backup failed: {err}"

    # Immediately prune old backups after a successful backup
    removed = _cleanup_old_backups()

    msg = f"Backup saved to backups/{dest_name}"
    if removed:
        msg += f" (pruned {removed} old backup(s))"
    return True, msg


# Alias for test compatibility
perform_backup = run_manual_backup


# ---------------------------------------------------------------------------
# Persistent Evennia Script — automatic ticker every 30 minutes
# ---------------------------------------------------------------------------

class BackupScript(DefaultScript):
    """
    Persistent ticker that backs up the database every 30 minutes.

    Creating this script will start the automatic backup cycle.
    It can be created once at server start (see at_server_startstop.py).
    """

    def at_script_creation(self):
        """Set script metadata on first creation."""
        self.key = "auto_backup_script"
        self.desc = "Automatic database backup every 30 minutes"
        self.interval = 1800        # 30 minutes
        self.start_delay = True     # don't backup instantly on launch
        self.persistent = True
        self.repeats = 0            # run forever

    def at_repeat(self):
        """Called every self.interval seconds."""
        success, msg = run_manual_backup()
        if success:
            print(f"[BACKUP] {msg}")
        else:
            print(f"[BACKUP] ERROR: {msg}")

    def at_start(self):
        """Log startup."""
        print("[BACKUP] Automatic backup script started (every 30 min).")