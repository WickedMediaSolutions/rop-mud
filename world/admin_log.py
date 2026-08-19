"""
Admin Audit Logging for 'rop' — Phase 10

Provides a persistent audit trail of all administrative actions.

Features:
  - log_admin_action()   — record an admin action with timestamp
  - get_recent_actions() — retrieve the most recent audit entries
  - get_actions_by_admin() — filter entries by admin name
  - clear_audit_log()    — purge old entries (with retention)

Entries are stored in a dedicated Script object so they persist across
reboots and survive @reload. The script is auto-created on first use.

Log entry format:
  {
      "timestamp": <epoch seconds>,
      "admin": <admin name>,
      "action": <action verb e.g. "ban", "kick", "reload">,
      "target": <target of action>,
      "details": <free-form detail string>,
  }
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

_AUDIT_SCRIPT_KEY = "admin_audit_log_script"
_MAX_ENTRIES = 2000  # rolling cap to bound memory/db growth


def _get_audit_script():
    """Get or create the persistent audit-log script."""
    from evennia.scripts.models import ScriptDB

    # Search first to avoid needless creation
    scripts = ScriptDB.objects.filter(db_key=_AUDIT_SCRIPT_KEY)
    if scripts:
        return scripts[0]

    # Lazily create a script to hold the log
    try:
        from evennia import create_script

        script = create_script(
            "evennia.scripts.scripts.DefaultScript",
            key=_AUDIT_SCRIPT_KEY,
            persistent=True,
            autostart=False,
        )
        if script:
            script.attributes.add("entries", [])
        return script
    except Exception:
        # Fallback: return None; logging becomes a no-op
        return None


def log_admin_action(
    admin: Any,
    action: str,
    target: str = "",
    details: str = "",
) -> bool:
    """
    Record an administrative action in the audit trail.

    Args:
        admin: The caller object performing the action.
        action: Short verb describing the action (e.g. "ban", "kick", "reload").
        target: The subject of the action (e.g. a player name or object).
        details: Any additional context.

    Returns:
        True if the entry was successfully recorded, else False.
    """
    try:
        script = _get_audit_script()
        if script is None:
            return False

        entry = {
            "timestamp": time.time(),
            "admin": getattr(admin, "key", "Unknown"),
            "admin_dbref": f"#{getattr(admin, 'id', 0)}",
            "action": action,
            "target": target,
            "details": details,
        }

        entries = script.attributes.get("entries", default=[])
        entries.append(entry)

        # Rolling cap
        if len(entries) > _MAX_ENTRIES:
            entries = entries[-_MAX_ENTRIES:]

        script.attributes.add("entries", entries)
        return True
    except Exception:
        return False


def get_recent_actions(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Return the most recent audit log entries.

    Args:
        limit: Maximum number of entries to return (newest first).

    Returns:
        A list of entry dicts in reverse chronological order.
    """
    try:
        script = _get_audit_script()
        if script is None:
            return []

        entries = script.attributes.get("entries", default=[])
        return list(reversed(entries[-limit:]))
    except Exception:
        return []


def get_actions_by_admin(admin_name: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Return audit entries for a specific admin.

    Args:
        admin_name: The exact admin name to filter on.
        limit: Maximum number of entries to return.

    Returns:
        A list of entry dicts in reverse chronological order.
    """
    try:
        script = _get_audit_script()
        if script is None:
            return []

        entries = script.attributes.get("entries", default=[])
        filtered = [e for e in entries if e.get("admin") == admin_name]
        return list(reversed(filtered[-limit:]))
    except Exception:
        return []


def get_actions_by_type(action: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Return audit entries of a specific action type.

    Args:
        action: The action verb to filter on (e.g. "ban", "mute").
        limit: Maximum number of entries to return.

    Returns:
        A list of entry dicts in reverse chronological order.
    """
    try:
        script = _get_audit_script()
        if script is None:
            return []

        entries = script.attributes.get("entries", default=[])
        filtered = [e for e in entries if e.get("action") == action]
        return list(reversed(filtered[-limit:]))
    except Exception:
        return []


def get_total_count() -> int:
    """Return the total number of audit log entries."""
    try:
        script = _get_audit_script()
        if script is None:
            return 0
        return len(script.attributes.get("entries", default=[]))
    except Exception:
        return 0


def clear_audit_log(keep_last: int = 0) -> int:
    """
    Clear audit log entries, optionally keeping the most recent N.

    Args:
        keep_last: Number of most recent entries to retain (0 = clear all).

    Returns:
        Number of entries removed.
    """
    try:
        script = _get_audit_script()
        if script is None:
            return 0

        entries = script.attributes.get("entries", default=[])
        removed = len(entries)
        if keep_last > 0:
            entries = entries[-keep_last:]
        else:
            entries = []
        script.attributes.add("entries", entries)
        return max(0, removed - len(entries))
    except Exception:
        return 0


def format_entry(entry: Dict[str, Any]) -> str:
    """
    Format a single audit entry for display.

    Uses ANSI color coding for readability.
    """
    import datetime

    ts = entry.get("timestamp", 0)
    try:
        dt = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        dt = "unknown time"

    admin = entry.get("admin", "Unknown")
    action = entry.get("action", "unknown")
    target = entry.get("target", "")
    details = entry.get("details", "")

    color_action = {
        "ban": "|r",
        "unban": "|g",
        "mute": "|y",
        "unmute": "|g",
        "kick": "|r",
        "reload": "|y",
        "spawn": "|g",
        "set": "|c",
        "goto": "|c",
        "populaterealm": "|y",
        "verifyrealm": "|c",
        "backup": "|g",
    }.get(action, "|w")

    line = f"{color_action}[{dt}] {admin} -> {action}|n"
    if target:
        line += f" |c{target}|n"
    if details:
        line += f" — {details}"
    return line