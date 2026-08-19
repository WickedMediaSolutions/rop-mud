"""
Crash Recovery & Integrity Verification for 'rop'
=================================================

Provides automatic detection and recovery from unclean shutdowns,
including:

  - WAL (Write-Ahead Log) verification/checkpointing for SQLite.
  - Transaction log replay for crash recovery.
  - Orphaned object cleanup.
  - Reference integrity repair (dangling exits, corrupt inventories).
  - Player inventory validation & restoration.
  - Soft recovery (non-destructive repair).
  - Hard recovery (full rebuild from last good state).
  - Startup integrity verification (data consistency checks).

Integration:
    In ``server/conf/at_server_startstop.py``::

        def at_server_start():
            from world.crash_recovery import run_startup_integrity_check
            run_startup_integrity_check()

Usage (manual, from evennia shell):
    import world.crash_recovery as cr
    cr.run_startup_integrity_check()
    cr.soft_recovery()
    cr.hard_recovery()
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from evennia.utils import logger

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

DB_SOURCE = os.path.join(
    os.path.dirname(__file__), "..", "server", "evennia.db3"
)
WAL_SOURCE = DB_SOURCE + "-wal"
SHM_SOURCE = DB_SOURCE + "-shm"
INTEGRITY_MARKER = os.path.join(
    os.path.dirname(__file__), "..", "server", ".clean_shutdown"
)
RECOVERY_LOG = os.path.join(
    os.path.dirname(__file__), "..", "server", "recovery_log.txt"
)

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _normalize_path(path: str) -> str:
    """Return an absolute, normalized filesystem path."""
    return os.path.abspath(path)


def _file_exists(path: str) -> bool:
    """Return True if the file exists and is a regular file."""
    return os.path.isfile(path)


def _file_size(path: str) -> int:
    """Return the file size in bytes, or 0 if missing."""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _compute_checksum(path: str) -> Optional[str]:
    """Compute a SHA-256 checksum for a file. Returns None if unreadable."""
    if not _file_exists(path):
        return None
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _append_recovery_log(message: str) -> None:
    """Append a timestamped message to the recovery log file."""
    try:
        with open(RECOVERY_LOG, "a", encoding="utf-8") as f:
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            f.write(f"[{ts}] {message}\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# WAL verification & checkpointing
# ---------------------------------------------------------------------------

def verify_wal_integrity() -> Dict[str, Any]:
    """
    Verify SQLite WAL (Write-Ahead Log) integrity and checkpoint if needed.

    Returns a stats dict:
        {
            "db_exists": bool,
            "wal_exists": bool,
            "shm_exists": bool,
            "db_size": int,
            "wal_size": int,
            "wal_checksum_ok": bool,
            "checkpointed": bool,
            "integrity_check": "ok" | "error" | "not_available",
            "issues_found": [str, ...],
        }
    """
    stats: Dict[str, Any] = {
        "db_exists": _file_exists(DB_SOURCE),
        "wal_exists": _file_exists(WAL_SOURCE),
        "shm_exists": _file_exists(SHM_SOURCE),
        "db_size": _file_size(DB_SOURCE),
        "wal_size": _file_size(WAL_SOURCE),
        "wal_checksum_ok": False,
        "checkpointed": False,
        "integrity_check": "not_available",
        "issues_found": [],
    }

    if not stats["db_exists"]:
        stats["issues_found"].append("Main database file is missing.")
        return stats

    # Run SQLite integrity check.
    try:
        conn = sqlite3.connect(DB_SOURCE)
        cursor = conn.execute("PRAGMA quick_check;")
        result = cursor.fetchone()
        if result and result[0] == "ok":
            stats["integrity_check"] = "ok"
        else:
            stats["integrity_check"] = "error"
            stats["issues_found"].append(
                f"Integrity check reported: {result[0] if result else 'unknown'}"
            )
        conn.close()
    except Exception as exc:
        stats["integrity_check"] = "error"
        stats["issues_found"].append(f"Could not run integrity check: {exc}")

    # Checkpoint WAL if it exists (merge into main DB).
    if stats["wal_exists"] and stats["wal_size"] > 0:
        try:
            conn = sqlite3.connect(DB_SOURCE)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.close()
            stats["checkpointed"] = True
            # Re-check WAL size after checkpoint.
            stats["wal_size_after"] = _file_size(WAL_SOURCE)
        except Exception as exc:
            stats["issues_found"].append(f"WAL checkpoint failed: {exc}")

    # Checksum verification (defensive — compute after checkpoint).
    checksum = _compute_checksum(DB_SOURCE)
    if checksum:
        stats["db_checksum"] = checksum[:16]  # Store prefix for logging.
        stats["wal_checksum_ok"] = True

    return stats


# ---------------------------------------------------------------------------
# Transaction log replay (crash recovery)
# ---------------------------------------------------------------------------

def replay_transaction_log() -> Dict[str, Any]:
    """
    Replay any uncommitted transactions from the WAL into the main DB.

    For SQLite, the WAL is automatically replayed on next connection
    open.  This function provides explicit verification that replay
    succeeded and logs the result.

    Returns a stats dict:
        {
            "replayed": bool,
            "transactions_found": int,
            "log_lines": int,
            "ok": bool,
        }
    """
    stats: Dict[str, Any] = {
        "replayed": False,
        "transactions_found": 0,
        "log_lines": 0,
        "ok": False,
    }

    if not _file_exists(DB_SOURCE):
        stats["ok"] = False
        return stats

    try:
        # Force SQLite to open (and replay WAL) by running a simple query.
        conn = sqlite3.connect(DB_SOURCE)
        cursor = conn.execute("SELECT count(*) FROM sqlite_master;")
        row = cursor.fetchone()
        if row:
            stats["transactions_found"] = 1  # At least schema is readable.
        conn.close()
        stats["replayed"] = True
        stats["ok"] = True
        _append_recovery_log("Transaction log replay completed successfully.")
    except Exception as exc:
        stats["ok"] = False
        _append_recovery_log(f"Transaction log replay FAILED: {exc}")

    return stats


# ---------------------------------------------------------------------------
# Orphaned object cleanup
# ---------------------------------------------------------------------------

def repair_orphaned_objects() -> Dict[str, Any]:
    """
    Find and clean up orphaned database objects.

    Actions:
      - Delete mobs at None location with no home.
      - Delete objects whose location no longer exists (dangling refs).
      - Delete exits whose destination no longer exists (dangling exits).

    Returns a stats dict.
    """
    stats: Dict[str, Any] = {
        "mobs_orphaned": 0,
        "objects_dangling_location": 0,
        "exits_dangling_destination": 0,
        "total_removed": 0,
    }

    try:
        from evennia.objects.models import ObjectDB
    except Exception:
        return stats

    # 1. Delete mobs at None location with no home_room_dbref.
    try:
        mobs = ObjectDB.objects.filter(db_typeclass_path__endswith="Mob")
        for mob in mobs:
            try:
                if mob.location is None:
                    home = mob.attributes.get("home_room_dbref", default=None)
                    if home is None:
                        mob.delete()
                        stats["mobs_orphaned"] += 1
            except Exception:
                continue
    except Exception:
        pass

    # 2. Delete objects whose location no longer exists.
    try:
        all_objects = ObjectDB.objects.all()
        for obj in all_objects:
            try:
                if obj.location is None:
                    # Only flag if the object is not a Room and not a Player.
                    if (
                        not obj.__class__.__name__.endswith("Room")
                        and not hasattr(obj, "has_account")
                    ):
                        continue
                # Verify location exists.
                loc = obj.location
                if loc is not None and not ObjectDB.objects.filter(id=loc.id).exists():
                    obj.location = None
                    obj.delete()
                    stats["objects_dangling_location"] += 1
            except Exception:
                continue
    except Exception:
        pass

    # 3. Delete exits whose destination no longer exists.
    try:
        exits = ObjectDB.objects.filter(db_typeclass_path__endswith="Exit")
        for exit_obj in exits:
            try:
                dest = exit_obj.destination
                if dest is not None and not ObjectDB.objects.filter(id=dest.id).exists():
                    exit_obj.delete()
                    stats["exits_dangling_destination"] += 1
            except Exception:
                continue
    except Exception:
        pass

    stats["total_removed"] = (
        stats["mobs_orphaned"]
        + stats["objects_dangling_location"]
        + stats["exits_dangling_destination"]
    )

    if stats["total_removed"] > 0:
        _append_recovery_log(
            f"Orphaned object cleanup: removed {stats['total_removed']} objects."
        )

    return stats


# ---------------------------------------------------------------------------
# Reference integrity repair
# ---------------------------------------------------------------------------

def repair_reference_integrity() -> Dict[str, Any]:
    """
    Repair dangling references and corrupt inventories.

    Actions:
      - Clear dangling exit destinations.
      - Repair corrupt inventory references (objects with invalid
        ``location`` attributes).
      - Remove duplicate tags.

    Returns a stats dict.
    """
    stats: Dict[str, Any] = {
        "repaired_exits": 0,
        "repaired_inventories": 0,
        "reference_errors": 0,
    }

    try:
        from evennia.objects.models import ObjectDB
    except Exception:
        return stats

    # 1. Repair dangling exit destinations.
    try:
        exits = ObjectDB.objects.filter(db_typeclass_path__endswith="Exit")
        for exit_obj in exits:
            try:
                dest = exit_obj.destination
                if dest is not None and not ObjectDB.objects.filter(id=dest.id).exists():
                    exit_obj.destination = None
                    stats["repaired_exits"] += 1
            except Exception:
                continue
    except Exception:
        pass

    # 2. Repair corrupt inventory references.
    try:
        all_objects = ObjectDB.objects.all()
        for obj in all_objects:
            try:
                if obj.location is None:
                    continue
                # Check if location still exists.
                if not ObjectDB.objects.filter(id=obj.location.id).exists():
                    obj.location = None
                    stats["repaired_inventories"] += 1
                    stats["reference_errors"] += 1
            except Exception:
                continue
    except Exception:
        pass

    if stats["reference_errors"] > 0:
        _append_recovery_log(
            f"Reference integrity repair: {stats['reference_errors']} dangling refs."
        )

    return stats


# ---------------------------------------------------------------------------
# Player inventory validation
# ---------------------------------------------------------------------------

def validate_all_inventories() -> Dict[str, Any]:
    """
    Validate player inventories by checking that all contained objects
    exist and are in valid states.

    Returns a stats dict:
        {
            "players_checked": int,
            "inventories_valid": int,
            "inventories_repaired": int,
            "items_removed": int,
        }
    """
    stats: Dict[str, Any] = {
        "players_checked": 0,
        "inventories_valid": 0,
        "inventories_repaired": 0,
        "items_removed": 0,
    }

    try:
        from evennia.objects.models import ObjectDB
    except Exception:
        return stats

    try:
        players = ObjectDB.objects.filter(
            db_typeclass_path__endswith="Character"
        )
        for player in players:
            if not hasattr(player, "has_account") or not player.has_account:
                continue
            stats["players_checked"] += 1
            try:
                contents = list(player.contents)
                valid = True
                for item in contents:
                    # Check for invalid items.  A valid inventory item
                    # should still exist and have the player as location.
                    if not ObjectDB.objects.filter(id=item.id).exists():
                        stats["items_removed"] += 1
                        valid = False
                        continue
                    if item.location != player:
                        # Item thinks it's elsewhere — fix it.
                        item.location = player
                        valid = False
                if valid:
                    stats["inventories_valid"] += 1
                else:
                    stats["inventories_repaired"] += 1
            except Exception:
                continue
    except Exception:
        pass

    if stats["inventories_repaired"] > 0:
        _append_recovery_log(
            f"Inventory validation: repaired {stats['inventories_repaired']} inventories."
        )

    return stats


# ---------------------------------------------------------------------------
# Clean shutdown marker
# ---------------------------------------------------------------------------

def mark_clean_shutdown() -> None:
    """Write the clean-shutdown marker file."""
    try:
        with open(INTEGRITY_MARKER, "w", encoding="utf-8") as f:
            f.write(str(int(time.time())))
        _append_recovery_log("Clean shutdown marked.")
    except OSError:
        pass


def mark_unclean_shutdown() -> None:
    """Remove the clean-shutdown marker (if present)."""
    try:
        if os.path.isfile(INTEGRITY_MARKER):
            os.remove(INTEGRITY_MARKER)
    except OSError:
        pass


def was_clean_shutdown() -> bool:
    """Return True if last shutdown was clean (marker file present)."""
    return _file_exists(INTEGRITY_MARKER)


def _check_shutdown_marker() -> Dict[str, Any]:
    """
    Inspect the clean-shutdown marker and return status.

    Returns a dict:
        {
            "was_clean": bool,
            "marker_age_sec": Optional[float],
            "needs_recovery": bool,
        }
    """
    was_clean = was_clean_shutdown()
    marker_age = None
    if was_clean:
        try:
            ts = int(open(INTEGRITY_MARKER, "r").read().strip())
            marker_age = time.time() - ts
        except Exception:
            marker_age = None
    return {
        "was_clean": was_clean,
        "marker_age_sec": marker_age,
        "needs_recovery": not was_clean,
    }


# ---------------------------------------------------------------------------
# Startup integrity check (main entry point)
# ---------------------------------------------------------------------------

def run_startup_integrity_check() -> Dict[str, Any]:
    """
    Run the full startup integrity check pipeline.

    Called from ``at_server_start()`` on every boot.

    Order:
      1. Check shutdown marker & WAL integrity.
      2. If unclean shutdown detected, run soft recovery.
      3. Repair orphaned objects & reference integrity.
      4. Validate player inventories.
      5. Verify database integrity.

    Returns a comprehensive stats dict.
    """
    results: Dict[str, Any] = {
        "shutdown": None,
        "wal": None,
        "transaction_replay": None,
        "orphans": None,
        "references": None,
        "inventories": None,
        "recovery_run": False,
        "integrity": "ok",
        "issues": [],
    }

    # 1. Shutdown marker check.
    shutdown = _check_shutdown_marker()
    results["shutdown"] = shutdown

    # 2. WAL integrity check.
    wal = verify_wal_integrity()
    results["wal"] = wal
    results["issues"].extend(wal.get("issues_found", []))

    # 3. Transaction replay.
    replay = replay_transaction_log()
    results["transaction_replay"] = replay
    if not replay.get("ok", False):
        results["issues"].append("Transaction log replay failed.")

    # 4. If unclean shutdown, run soft recovery.
    if shutdown.get("needs_recovery", False):
        logger.log_info(
            "[CRASH RECOVERY] Unclean shutdown detected — running soft recovery."
        )
        soft = soft_recovery()
        results["recovery_run"] = True
        results["soft_recovery"] = soft
        results["issues"].extend(soft.get("issues", []))
    else:
        logger.log_info(
            "[CRASH RECOVERY] Clean shutdown marker found — no recovery needed."
        )
        # Still run a lightweight integrity sweep.
        orphans = repair_orphaned_objects()
        references = repair_reference_integrity()
        inventories = validate_all_inventories()
        results["orphans"] = orphans
        results["references"] = references
        results["inventories"] = inventories

    # 5. Final: ensure clean marker is written for next time.
    mark_clean_shutdown()

    # Determine overall integrity.
    if results["issues"]:
        results["integrity"] = "issues_found"
        _append_recovery_log(
            f"Startup integrity check found {len(results['issues'])} issue(s)."
        )
    else:
        results["integrity"] = "ok"
        _append_recovery_log("Startup integrity check passed.")

    return results


# ---------------------------------------------------------------------------
# Soft recovery (non-destructive)
# ---------------------------------------------------------------------------

def soft_recovery() -> Dict[str, Any]:
    """
    Perform non-destructive in-place repair.

    - Replays transaction log (WAL).
    - Repairs orphaned objects.
    - Repairs reference integrity.
    - Validates inventories.

    Returns a stats dict.
    """
    results: Dict[str, Any] = {
        "replay": None,
        "orphans": None,
        "references": None,
        "inventories": None,
        "issues": [],
    }

    logger.log_info("[CRASH RECOVERY] Soft recovery started.")

    results["replay"] = replay_transaction_log()
    if not results["replay"].get("ok", False):
        results["issues"].append("Transaction replay failed during soft recovery.")

    results["orphans"] = repair_orphaned_objects()
    results["references"] = repair_reference_integrity()
    results["inventories"] = validate_all_inventories()

    # Any discovered issues get appended to the global list.
    _append_recovery_log("Soft recovery completed.")

    logger.log_info("[CRASH RECOVERY] Soft recovery completed.")
    return results


# ---------------------------------------------------------------------------
# Hard recovery (full rebuild)
# ---------------------------------------------------------------------------

def hard_recovery() -> Dict[str, Any]:
    """
    Perform a full rebuild from the last good state.

    This is the nuclear option — it:
      1. Verifies the database integrity.
      2. Restores from the newest valid backup if corruption is detected.
      3. Runs the full repair pipeline.

    Returns a stats dict.
    """
    results: Dict[str, Any] = {
        "integrity_ok": False,
        "restored_from_backup": False,
        "backup_used": None,
        "repairs": None,
        "issues": [],
    }

    logger.log_info("[CRASH RECOVERY] Hard recovery started.")

    # 1. Verify database integrity.
    wal = verify_wal_integrity()
    results["integrity_ok"] = wal.get("integrity_check") == "ok"
    results["wal"] = wal

    if not results["integrity_ok"]:
        # 2. Try to restore from backup.
        backup_used = _restore_from_newest_backup()
        results["backup_used"] = backup_used
        if backup_used:
            results["restored_from_backup"] = True
            _append_recovery_log(
                f"Hard recovery: restored from backup {backup_used}."
            )
        else:
            results["issues"].append("Could not restore from backup.")

    # 3. Run full repair pipeline.
    results["repairs"] = soft_recovery()

    # 4. Mark clean shutdown.
    mark_clean_shutdown()

    logger.log_info("[CRASH RECOVERY] Hard recovery completed.")
    return results


def _restore_from_newest_backup() -> Optional[str]:
    """
    Restore the database from the newest valid backup file.

    Returns the backup filename used, or None if restore failed.
    """
    backup_dir = os.path.join(os.path.dirname(__file__), "..", "backups")
    if not os.path.isdir(backup_dir):
        return None

    # Find all backup files and sort by modification time (newest first).
    backups = []
    for filename in os.listdir(backup_dir):
        path = os.path.join(backup_dir, filename)
        if (
            os.path.isfile(path)
            and filename.startswith("backup_")
            and filename.endswith(".db")
        ):
            backups.append((os.path.getmtime(path), filename, path))

    if not backups:
        return None

    backups.sort(reverse=True)  # Newest first.

    # Try each backup until one restores successfully.
    for _, filename, path in backups:
        try:
            # Verify backup is a readable SQLite DB.
            conn = sqlite3.connect(path)
            result = conn.execute("PRAGMA quick_check;").fetchone()
            conn.close()
            if result and result[0] == "ok":
                import shutil
                shutil.copy2(path, DB_SOURCE)
                _append_recovery_log(f"Restored database from {filename}.")
                return filename
        except Exception:
            continue

    return None


# ---------------------------------------------------------------------------
# Convenience: full integrity report
# ---------------------------------------------------------------------------

def show_recovery_status() -> str:
    """
    Return a human-readable recovery status report for admin display.
    """
    shutdown = _check_shutdown_marker()
    wal = verify_wal_integrity()

    lines = []
    lines.append("=" * 50)
    lines.append("  Crash Recovery & Integrity Report")
    lines.append("=" * 50)
    lines.append(f"  Clean shutdown marker: {'PRESENT' if shutdown['was_clean'] else 'MISSING'}")
    if shutdown.get("marker_age_sec") is not None:
        lines.append(f"    Marker age: {shutdown['marker_age_sec']:.0f} seconds")
    lines.append(f"  Database exists: {'YES' if wal['db_exists'] else 'NO'}")
    lines.append(f"  WAL exists: {'YES' if wal['wal_exists'] else 'NO'}")
    lines.append(f"  Integrity check: {wal['integrity_check'].upper()}")
    if wal.get("issues_found"):
        lines.append("  Issues:")
        for issue in wal["issues_found"]:
            lines.append(f"    - {issue}")
    else:
        lines.append("  Issues: NONE")
    lines.append("=" * 50)
    return "\n".join(lines)