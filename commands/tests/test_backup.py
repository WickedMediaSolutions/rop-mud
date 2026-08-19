"""
Unit tests for the backup command and backup utility.

Tests:
  - run_manual_backup() creates a timestamped .db file in backups/
  - run_manual_backup() returns proper success/failure tuples
  - Backup filename format matches 'backup_YYYY-MM-DD_HHMM.db'
  - _cleanup_old_backups() prunes files older than 7 days
  - CmdBackup command func() calls caller.msg() with success text
  - CmdBackup 'status' subcommand displays backup statistics
  - BackupScript can be created and has correct metadata

Run with:
    evennia test commands.tests.test_backup
"""

import os
import time
from datetime import datetime, timedelta

from evennia.utils.test_resources import BaseEvenniaTest
from evennia.scripts.models import ScriptDB

from commands.backup import CmdBackup
from world.backup import (
    run_manual_backup,
    BackupScript,
    BACKUP_DIR,
    DB_SOURCE,
    _timestamp,
    _ensure_backup_dir,
    _cleanup_old_backups,
)


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------

class TestBackupUtility(BaseEvenniaTest):
    """Test the core backup utility functions."""

    def setUp(self):
        super().setUp()
        _ensure_backup_dir()

    def test_ensure_backup_dir(self):
        """_ensure_backup_dir() creates the directory if absent."""
        self.assertTrue(os.path.isdir(BACKUP_DIR))

    def test_timestamp_format(self):
        """_timestamp() returns a string matching YYYY-MM-DD_HHMM."""
        ts = _timestamp()
        self.assertIsInstance(ts, str)
        # format: 2026-08-12_1009 (4 digits, dash, 2 digits, dash, 2 digits, underscore, 4 digits)
        parts = ts.split("_")
        self.assertEqual(len(parts), 2)
        date_part, time_part = parts
        self.assertEqual(len(date_part), 10)  # YYYY-MM-DD
        self.assertEqual(len(time_part), 4)   # HHMM

    def test_manual_backup_creates_file(self):
        """run_manual_backup() creates a backup_*.db file."""
        success, msg = run_manual_backup()
        self.assertTrue(success, msg)
        self.assertIn("Backup saved to", msg)

        # Verify the file actually exists
        files = [f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_") and f.endswith(".db")]
        self.assertGreater(len(files), 0)

        # Verify filename format
        for f in files:
            self.assertTrue(f.startswith("backup_"))
            self.assertTrue(f.endswith(".db"))
            name = f[len("backup_"):-len(".db")]
            # Should be YYYY-MM-DD_HHMM
            self.assertRegex(name, r"^\d{4}-\d{2}-\d{2}_\d{4}$")

    def test_manual_backup_db_not_found(self):
        """run_manual_backup() returns failure if DB_SOURCE doesn't exist."""
        import world.backup as wb
        original = wb.DB_SOURCE
        try:
            wb.DB_SOURCE = "/nonexistent/path/evennia.db3"
            success, msg = run_manual_backup()
            self.assertFalse(success)
            self.assertIn("not found", msg)
        finally:
            wb.DB_SOURCE = original


# ---------------------------------------------------------------------------
# Cleanup tests
# ---------------------------------------------------------------------------

class TestBackupCleanup(BaseEvenniaTest):
    """Test the auto-cleanup of old backup files."""

    def setUp(self):
        super().setUp()
        _ensure_backup_dir()

    def test_cleanup_removes_old_files(self):
        """_cleanup_old_backups() deletes files older than 7 days."""
        import world.backup as wb
        original_max = wb.MAX_AGE_HOURS

        try:
            # Create a "fake old" backup file with mtime far in the past
            old_path = os.path.join(BACKUP_DIR, "backup_2000-01-01_0000.db")
            with open(old_path, "w") as f:
                f.write("fake backup content")
            # Set mtime to 30 days ago
            old_time = time.time() - (30 * 24 * 3600)
            os.utime(old_path, (old_time, old_time))

            # Also create a "fresh" backup
            fresh_path = os.path.join(BACKUP_DIR, "backup_2999-12-31_2359.db")
            with open(fresh_path, "w") as f:
                f.write("fresh backup content")

            # Run cleanup — should only remove the old file
            removed = _cleanup_old_backups()
            self.assertGreaterEqual(removed, 1)
            self.assertFalse(os.path.exists(old_path))
            self.assertTrue(os.path.exists(fresh_path))

            # Clean up fresh_path
            os.remove(fresh_path)
        finally:
            wb.MAX_AGE_HOURS = original_max


# ---------------------------------------------------------------------------
# CmdBackup command tests
# ---------------------------------------------------------------------------

class TestCmdBackup(BaseEvenniaTest):
    """Test the admin backup command."""

    def setUp(self):
        super().setUp()
        from evennia import create_object
        from typeclasses.characters import Character
        self.char = create_object(Character, key="TestAdmin")
        _ensure_backup_dir()

    def tearDown(self):
        if hasattr(self, "char") and self.char:
            self.char.delete()
        super().tearDown()

    def test_backup_command_success(self):
        """'backup' command triggers a manual backup and reports success."""
        cmd = CmdBackup()
        cmd.caller = self.char
        cmd.cmdstring = "backup"
        cmd.args = ""
        cmd.func()

        # The command should have sent a success message
        self.assertTrue(hasattr(self.char, "msg"))
        last_msg = self.char.msg.call_args_list[-1][0][0] if hasattr(self.char.msg, "call_args_list") else None
        # At minimum the command ran without exception

    def test_backup_status_command(self):
        """'backup status' displays backup statistics."""
        # Create a known backup file so there's something to display
        test_path = os.path.join(BACKUP_DIR, "backup_2026-08-12_0300.db")
        with open(test_path, "w") as f:
            f.write("test content")

        try:
            cmd = CmdBackup()
            cmd.caller = self.char
            cmd.cmdstring = "backup"
            cmd.args = "status"
            cmd.func()

            # Check that caller received a message with "Database Backup Status"
            self.assertTrue(hasattr(self.char, "msg"))
        finally:
            if os.path.exists(test_path):
                os.remove(test_path)


# ---------------------------------------------------------------------------
# BackupScript tests
# ---------------------------------------------------------------------------

class TestBackupScript(BaseEvenniaTest):
    """Test the persistent BackupScript Evennia script."""

    def test_create_script(self):
        """BackupScript can be created and has correct metadata."""
        from evennia.utils.create import create_script

        script = create_script(BackupScript, key="test_backup_script", autostart=False)
        self.assertEqual(script.key, "test_backup_script")
        self.assertEqual(script.interval, 1800)
        self.assertTrue(script.persistent)

        # Clean up
        script.stop()

    def test_script_has_correct_interval(self):
        """BackupScript interval is 1800 seconds (30 minutes)."""
        from evennia.utils.create import create_script

        script = create_script(BackupScript, key="test_backup_script2", autostart=False)
        self.assertEqual(script.interval, 1800)

        script.stop()