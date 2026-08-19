"""
Database Migration Framework for 'rop'
======================================

Provides a versioned migration system that tracks schema changes and
applies them in order on server startup.  Migrations are idempotent —
each migration runs at most once.

Architecture:
  - ``Migration`` class: a single schema/data change with an ``apply()``
    and optional ``rollback()`` method.
  - ``MIGRATIONS`` registry: ordered list of migrations keyed by version.
  - ``MigrationManager``: applies pending migrations, tracks applied
    versions in a persistent Evennia Script.
  - ``run_migrations()``: entry point called from ``at_server_init()``.

Usage:
    from world.migrations import run_migrations
    run_migrations()  # safe to call multiple times — only runs pending

Adding a new migration:
    1. Add a new ``Migration`` instance to the ``MIGRATIONS`` list below.
    2. Increment the version number.
    3. Implement ``apply()`` and optionally ``rollback()``.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from evennia.scripts.scripts import DefaultScript
from evennia.utils import logger

# ---------------------------------------------------------------------------
# Migration registry
# ---------------------------------------------------------------------------

class Migration:
    """A single versioned database migration."""

    def __init__(
        self,
        version: int,
        name: str,
        description: str,
        apply_fn: Callable[[], bool],
        rollback_fn: Optional[Callable[[], bool]] = None,
    ):
        self.version = version
        self.name = name
        self.description = description
        self._apply = apply_fn
        self._rollback = rollback_fn

    def apply(self) -> bool:
        """Run the migration. Returns True on success."""
        try:
            return self._apply()
        except Exception as exc:
            logger.log_err(
                f"[MIGRATION] Migration v{self.version} '{self.name}' "
                f"failed: {exc}"
            )
            return False

    def rollback(self) -> bool:
        """Roll back the migration. Returns True on success."""
        if self._rollback is None:
            logger.log_info(
                f"[MIGRATION] No rollback defined for v{self.version} "
                f"'{self.name}'."
            )
            return False
        try:
            return self._rollback()
        except Exception as exc:
            logger.log_err(
                f"[MIGRATION] Rollback v{self.version} '{self.name}' "
                f"failed: {exc}"
            )
            return False


# ---------------------------------------------------------------------------
# Migration definitions — add new migrations here in version order
# ---------------------------------------------------------------------------

def _migration_001_ensure_character_attrs() -> bool:
    """
    Ensure all Character objects have the required base attributes
    (hp, max_hp, mana, max_mana, mv, max_mv, level, xp, stats, etc.).
    This is a defensive migration that fills in defaults for any
    characters created before the attribute system was finalized.
    """
    from evennia.objects.models import ObjectDB

    default_attrs = {
        "hp": 100,
        "max_hp": 100,
        "mana": 50,
        "max_mana": 50,
        "mv": 100,
        "max_mv": 100,
        "level": 1,
        "xp": 0,
        "xp_to_next": 1000,
        "stats": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        "position": "standing",
        "stamina": 100,
        "max_stamina": 100,
        "alignment": "Neutral",
        "faction": "Unaffiliated",
        "copper": 0,
        "silver": 0,
        "gold": 0,
        "bank_copper": 0,
        "bank_silver": 0,
        "bank_gold": 0,
        "pvp_enabled": False,
        "auto_loot": False,
        "auto_sacrifice": False,
        "combat_brief": False,
    }

    updated = 0
    for obj in ObjectDB.objects.filter(db_typeclass_path__endswith="Character"):
        if not hasattr(obj, "has_account") or not obj.has_account:
            continue
        for attr_name, default_val in default_attrs.items():
            if not obj.attributes.has(attr_name):
                obj.attributes.add(attr_name, default_val)
                updated += 1

    if updated > 0:
        logger.log_info(
            f"[MIGRATION 001] Set {updated} missing default attributes "
            f"on Character objects."
        )
    return True


def _migration_002_ensure_mob_tags() -> bool:
    """
    Ensure all Mob objects have the 'realm_mob' tag with category 'spawn'.
    This tag is used by the reboot persistence system to identify realm mobs.
    """
    from evennia.objects.models import ObjectDB

    tagged = 0
    for mob in ObjectDB.objects.filter(db_typeclass_path__endswith="Mob"):
        if not mob.tags.has("realm_mob", category="spawn"):
            mob.tags.add("realm_mob", category="spawn")
            tagged += 1

    if tagged > 0:
        logger.log_info(
            f"[MIGRATION 002] Tagged {tagged} mobs with 'realm_mob' tag."
        )
    return True


def _migration_003_ensure_room_zone_tags() -> bool:
    """
    Ensure all Room objects have a 'zone_tag' attribute.  Rooms without
    one get assigned based on their location in the realm hierarchy or
    default to 'sunspire_meadows' (the starter zone).
    """
    from evennia.objects.models import ObjectDB

    updated = 0
    for room in ObjectDB.objects.filter(db_typeclass_path__endswith="Room"):
        if not room.attributes.has("zone_tag"):
            room.attributes.add("zone_tag", "sunspire_meadows")
            updated += 1
        if not room.attributes.has("max_mobs"):
            room.attributes.add("max_mobs", 3)
            updated += 1

    if updated > 0:
        logger.log_info(
            f"[MIGRATION 003] Set {updated} missing zone attributes on rooms."
        )
    return True


def _migration_004_ensure_exit_bidirectional() -> bool:
    """
    Ensure all Exit objects have a return exit (bidirectional travel).
    For each one-way exit, attempt to create or link a return exit.
    This is a best-effort migration — some exits may be intentionally
    one-way (e.g., trap doors, portals).
    """
    from evennia.objects.models import ObjectDB

    fixed = 0
    for exit_obj in ObjectDB.objects.filter(db_typeclass_path__endswith="Exit"):
        try:
            if not exit_obj.location or not exit_obj.destination:
                continue
            # Check if return exit exists.
            return_exists = False
            for ret_exit in exit_obj.destination.contents:
                if (
                    hasattr(ret_exit, "destination")
                    and ret_exit.destination == exit_obj.location
                ):
                    return_exists = True
                    break
            if not return_exists:
                # Store the return reference on the exit itself.
                exit_obj.attributes.add("needs_return_exit", True)
                fixed += 1
        except Exception:
            continue

    if fixed > 0:
        logger.log_info(
            f"[MIGRATION 004] Flagged {fixed} one-way exits for return-exit "
            f"creation."
        )
    return True


def _migration_005_cleanup_stale_scripts() -> bool:
    """
    Remove any orphaned or duplicate Evennia Scripts that may have
    accumulated from repeated reloads or crashes.
    """
    from evennia.scripts.models import ScriptDB

    removed = 0
    # Find duplicate scripts (same key, multiple instances).
    seen_keys: Dict[str, List[int]] = {}
    for script in ScriptDB.objects.all():
        key = script.db_key
        if key not in seen_keys:
            seen_keys[key] = []
        seen_keys[key].append(script.id)

    for key, ids in seen_keys.items():
        if len(ids) > 1:
            # Keep the first one, delete the rest.
            for script_id in ids[1:]:
                try:
                    script = ScriptDB.objects.get(id=script_id)
                    script.delete()
                    removed += 1
                except Exception:
                    pass

    if removed > 0:
        logger.log_info(
            f"[MIGRATION 005] Removed {removed} duplicate scripts."
        )
    return True


# ---------------------------------------------------------------------------
# Ordered migration list — add new migrations at the END
# ---------------------------------------------------------------------------

MIGRATIONS: List[Migration] = [
    Migration(
        version=1,
        name="ensure_character_attrs",
        description="Set default attributes on all Character objects.",
        apply_fn=_migration_001_ensure_character_attrs,
    ),
    Migration(
        version=2,
        name="ensure_mob_tags",
        description="Tag all Mob objects with 'realm_mob' for persistence.",
        apply_fn=_migration_002_ensure_mob_tags,
    ),
    Migration(
        version=3,
        name="ensure_room_zone_tags",
        description="Set zone_tag and max_mobs on all Room objects.",
        apply_fn=_migration_003_ensure_room_zone_tags,
    ),
    Migration(
        version=4,
        name="ensure_exit_bidirectional",
        description="Flag one-way exits for return-exit creation.",
        apply_fn=_migration_004_ensure_exit_bidirectional,
    ),
    Migration(
        version=5,
        name="cleanup_stale_scripts",
        description="Remove duplicate/orphaned Evennia Scripts.",
        apply_fn=_migration_005_cleanup_stale_scripts,
    ),
]


# ---------------------------------------------------------------------------
# Migration Manager
# ---------------------------------------------------------------------------

class MigrationTrackerScript(DefaultScript):
    """
    Persistent script that tracks which migrations have been applied.

    Stores a list of applied migration version numbers in the
    ``applied_versions`` attribute.
    """

    def at_script_creation(self):
        self.key = "migration_tracker"
        self.desc = "Tracks applied database migration versions"
        self.persistent = True
        if not self.attributes.has("applied_versions"):
            self.attributes.add("applied_versions", [])


def _get_tracker() -> MigrationTrackerScript:
    """Get or create the migration tracker script."""
    from evennia.scripts.models import ScriptDB

    tracker = ScriptDB.objects.filter(db_key="migration_tracker").first()
    if tracker is None:
        tracker = MigrationTrackerScript.create(
            "migration_tracker", autostart=False
        )
    return tracker


def get_applied_versions() -> List[int]:
    """Return list of already-applied migration version numbers."""
    try:
        tracker = _get_tracker()
        return list(tracker.attributes.get("applied_versions", default=[]))
    except Exception:
        return []


def mark_applied(version: int) -> None:
    """Record that a migration version has been applied."""
    try:
        tracker = _get_tracker()
        applied = list(tracker.attributes.get("applied_versions", default=[]))
        if version not in applied:
            applied.append(version)
            applied.sort()
            tracker.attributes.add("applied_versions", applied)
    except Exception as exc:
        logger.log_err(f"[MIGRATION] Failed to mark v{version} as applied: {exc}")


def mark_rolled_back(version: int) -> None:
    """Remove a migration version from the applied list."""
    try:
        tracker = _get_tracker()
        applied = list(tracker.attributes.get("applied_versions", default=[]))
        if version in applied:
            applied.remove(version)
            tracker.attributes.add("applied_versions", applied)
    except Exception as exc:
        logger.log_err(f"[MIGRATION] Failed to mark v{version} as rolled back: {exc}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_migrations() -> Dict[str, Any]:
    """
    Apply all pending migrations in version order.

    Called from ``at_server_init()`` on every server start.  Safe to
    call multiple times — already-applied migrations are skipped.

    Returns a stats dict:
        {
            "applied": [1, 2, ...],    # versions applied this run
            "skipped": [3, 4, ...],    # versions already applied
            "failed": [5, ...],        # versions that failed
            "total_pending": 3,
            "total_applied": 2,
            "total_failed": 0,
        }
    """
    applied_versions = get_applied_versions()
    stats: Dict[str, Any] = {
        "applied": [],
        "skipped": [],
        "failed": [],
        "total_pending": 0,
        "total_applied": 0,
        "total_failed": 0,
    }

    pending = [m for m in MIGRATIONS if m.version not in applied_versions]
    stats["total_pending"] = len(pending)

    if not pending:
        logger.log_info("[MIGRATION] All migrations up to date — nothing to apply.")
        return stats

    logger.log_info(
        f"[MIGRATION] Found {len(pending)} pending migration(s): "
        f"{[m.name for m in pending]}"
    )

    for migration in sorted(pending, key=lambda m: m.version):
        logger.log_info(
            f"[MIGRATION] Applying v{migration.version}: {migration.name} — "
            f"{migration.description}"
        )
        success = migration.apply()
        if success:
            mark_applied(migration.version)
            stats["applied"].append(migration.version)
            stats["total_applied"] += 1
            logger.log_info(
                f"[MIGRATION] v{migration.version} '{migration.name}' applied."
            )
        else:
            stats["failed"].append(migration.version)
            stats["total_failed"] += 1
            logger.log_err(
                f"[MIGRATION] v{migration.version} '{migration.name}' FAILED — "
                f"stopping migration run."
            )
            break  # Stop on first failure to avoid cascading issues.

    # Log summary.
    logger.log_info(
        f"[MIGRATION] Run complete: {stats['total_applied']} applied, "
        f"{stats['total_failed']} failed, "
        f"{len(applied_versions)} previously applied."
    )

    return stats


def rollback_migration(version: int) -> bool:
    """
    Roll back a specific migration by version number.

    Returns True if the rollback succeeded.
    """
    migration = next((m for m in MIGRATIONS if m.version == version), None)
    if migration is None:
        logger.log_err(f"[MIGRATION] No migration found with version {version}.")
        return False

    applied = get_applied_versions()
    if version not in applied:
        logger.log_info(
            f"[MIGRATION] v{version} is not applied — nothing to roll back."
        )
        return True

    logger.log_info(
        f"[MIGRATION] Rolling back v{version}: {migration.name}"
    )
    success = migration.rollback()
    if success:
        mark_rolled_back(version)
        logger.log_info(f"[MIGRATION] v{version} rolled back.")
    else:
        logger.log_err(f"[MIGRATION] v{version} rollback FAILED.")
    return success


def show_migration_status() -> str:
    """
    Return a human-readable migration status report.

    Suitable for display via an admin command or server log.
    """
    applied = get_applied_versions()
    lines = []
    lines.append("=" * 50)
    lines.append("  Database Migration Status")
    lines.append("=" * 50)

    for migration in MIGRATIONS:
        status = "APPLIED" if migration.version in applied else "PENDING"
        lines.append(
            f"  v{migration.version:03d} [{status:8s}] {migration.name}"
        )
        lines.append(f"           {migration.description}")

    lines.append("-" * 50)
    lines.append(
        f"  Total: {len(MIGRATIONS)} migrations "
        f"({len(applied)} applied, {len(MIGRATIONS) - len(applied)} pending)"
    )
    lines.append("=" * 50)
    return "\n".join(lines)