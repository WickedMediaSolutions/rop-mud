"""
Performance Monitoring for 'rop' — Phase 10

Provides lightweight runtime metrics collection without external
profiling dependencies.

Features:
  - record_timing(section, seconds) — record a timing sample
  - get_section_stats(section)       — aggregate stats for a section
  - get_server_metrics()             — full snapshot of server metrics
  - get_top_objects()                — object/script/account counts
  - reset_metrics()                  — clear all collected samples

Metrics are kept in an in-memory registry (module global) and are also
mirrored to a persistent Script so they survive @reload where possible.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# In-memory registry (fast path, always available)
# ---------------------------------------------------------------------------

_lock = threading.RLock()

_metrics: Dict[str, Dict[str, Any]] = {
    "server_start_time": 0.0,
    "command_count": 0,
    "command_timings": {},   # command_name -> {"count": N, "total": secs, "max": secs}
    "section_timings": {},   # section -> {"count": N, "total": secs, "max": secs}
    "combat_rounds": 0,
    "mob_tick_count": 0,
    "network_msgs": 0,
}

_server_start_time = time.time()
_metrics["server_start_time"] = _server_start_time

_METRIC_SCRIPT_KEY = "performance_metrics_script"


# ---------------------------------------------------------------------------
# Recording API
# ---------------------------------------------------------------------------

def record_timing(section: str, seconds: float) -> None:
    """
    Record a timing sample for a named section.

    This is intentionally lock-protected and cheap so it can be wrapped
    around hot paths without measurable overhead.
    """
    with _lock:
        entry = _metrics["section_timings"].setdefault(
            section, {"count": 0, "total": 0.0, "max": 0.0}
        )
        entry["count"] += 1
        entry["total"] += seconds
        if seconds > entry["max"]:
            entry["max"] = seconds


def record_command(command_name: str, seconds: float) -> None:
    """Record execution time for a command."""
    with _lock:
        entry = _metrics["command_timings"].setdefault(
            command_name, {"count": 0, "total": 0.0, "max": 0.0}
        )
        entry["count"] += 1
        entry["total"] += seconds
        if seconds > entry["max"]:
            entry["max"] = seconds
        _metrics["command_count"] += 1


def increment_counter(counter_name: str, amount: int = 1) -> None:
    """Increment a named counter (e.g. 'combat_rounds', 'mob_tick_count')."""
    with _lock:
        _metrics[counter_name] = _metrics.get(counter_name, 0) + amount


# ---------------------------------------------------------------------------
# Snapshot API
# ---------------------------------------------------------------------------

def get_section_stats(section: str) -> Dict[str, Any]:
    """Return aggregate stats for a named timing section."""
    with _lock:
        entry = _metrics["section_timings"].get(section)
        if not entry:
            return {"section": section, "count": 0, "total": 0.0, "avg": 0.0, "max": 0.0}
        avg = entry["total"] / entry["count"] if entry["count"] else 0.0
        return {
            "section": section,
            "count": entry["count"],
            "total": entry["total"],
            "avg": avg,
            "max": entry["max"],
        }


def get_command_stats(command_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return command timing stats.

    If command_name is provided, returns a single-entry list. Otherwise
    returns all commands sorted by total time descending.
    """
    with _lock:
        if command_name:
            entry = _metrics["command_timings"].get(command_name)
            if not entry:
                return []
            return [_format_command_entry(command_name, entry)]

        entries = []
        for name, entry in _metrics["command_timings"].items():
            entries.append(_format_command_entry(name, entry))
        entries.sort(key=lambda e: e["total"], reverse=True)
        return entries


def _format_command_entry(name: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    avg = entry["total"] / entry["count"] if entry["count"] else 0.0
    return {
        "command": name,
        "count": entry["count"],
        "total": entry["total"],
        "avg": avg,
        "max": entry["max"],
    }


def get_server_metrics() -> Dict[str, Any]:
    """
    Return a comprehensive metrics snapshot.

    Includes uptime, command stats, section stats, and counters.
    """
    with _lock:
        uptime = time.time() - _metrics["server_start_time"]

        command_entries = []
        for name, entry in _metrics["command_timings"].items():
            command_entries.append(_format_command_entry(name, entry))
        command_entries.sort(key=lambda e: e["total"], reverse=True)

        section_entries = []
        for name, entry in _metrics["section_timings"].items():
            avg = entry["total"] / entry["count"] if entry["count"] else 0.0
            section_entries.append({
                "section": name,
                "count": entry["count"],
                "total": entry["total"],
                "avg": avg,
                "max": entry["max"],
            })
        section_entries.sort(key=lambda e: e["total"], reverse=True)

        result = {
            "uptime_seconds": uptime,
            "command_count": _metrics["command_count"],
            "combat_rounds": _metrics.get("combat_rounds", 0),
            "mob_tick_count": _metrics.get("mob_tick_count", 0),
            "network_msgs": _metrics.get("network_msgs", 0),
            "top_commands": command_entries[:20],
            "section_timings": section_entries,
        }
        result.update(_get_entity_counts())
        return result


def _get_entity_counts() -> Dict[str, int]:
    """Count database entities (handled standalone for testability)."""
    return get_entity_counts()


def get_entity_counts() -> Dict[str, int]:
    """Return counts of objects, scripts, accounts, channels, etc."""
    try:
        from evennia.objects.models import ObjectDB
        from evennia.scripts.models import ScriptDB
        from evennia.accounts.models import AccountDB
        from evennia.comms.models import ChannelDB, Msg

        counts = {
            "objects": ObjectDB.objects.count(),
            "scripts": ScriptDB.objects.count(),
            "accounts": AccountDB.objects.count(),
            "channels": ChannelDB.objects.count(),
            "messages": Msg.objects.count(),
        }
        try:
            from evennia.players.models import PlayerDB
            counts["players"] = PlayerDB.objects.count()
        except Exception:
            counts["players"] = 0
        return counts
    except Exception:
        return {}


def get_top_objects(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Return the most "active" objects by recent activity, useful for
    spotting rogue scripts or runaway mobs.
    """
    try:
        from evennia.objects.models import ObjectDB

        # Sort by date_modified (most recently touched first)
        objs = ObjectDB.objects.exclude(db_date_modified=None).order_by(
            "-db_date_modified"
        )[:limit]

        results = []
        for obj in objs:
            results.append({
                "dbref": f"#{obj.id}",
                "key": obj.db_key,
                "typeclass": obj.db_typeclass_path,
                "date_modified": obj.db_date_modified,
            })
        return results
    except Exception:
        return []


def get_running_scripts(limit: int = 20) -> List[Dict[str, Any]]:
    """Return currently running/paused global scripts."""
    try:
        from evennia.scripts.models import ScriptDB

        scripts = ScriptDB.objects.filter(db_is_active=True)[:limit]
        results = []
        for s in scripts:
            results.append({
                "dbref": f"#{s.id}",
                "key": s.db_key,
                "typeclass": s.db_typeclass_path,
                "interval": getattr(s, "db_interval", 0),
                "repeats": getattr(s, "db_repeats", 0),
                "remaining": getattr(s, "db_remaining_repeats", 0),
            })
        return results
    except Exception:
        return []


def reset_metrics() -> None:
    """Reset all in-memory performance metrics."""
    global _metrics, _server_start_time
    with _lock:
        _server_start_time = time.time()
        _metrics = {
            "server_start_time": _server_start_time,
            "command_count": 0,
            "command_timings": {},
            "section_timings": {},
            "combat_rounds": 0,
            "mob_tick_count": 0,
            "network_msgs": 0,
        }


def persist_metrics() -> bool:
    """
    Persist the current metrics snapshot to a Script attribute.

    Used for crash/post-mortem analysis. Returns True on success.
    """
    try:
        from evennia.scripts.models import ScriptDB
        from evennia import create_script

        scripts = ScriptDB.objects.filter(db_key=_METRIC_SCRIPT_KEY)
        script = scripts[0] if scripts else create_script(
            "evennia.scripts.scripts.DefaultScript",
            key=_METRIC_SCRIPT_KEY,
            persistent=True,
            autostart=False,
        )
        if not script:
            return False

        with _lock:
            snapshot = dict(_metrics)
        script.attributes.add("metrics_snapshot", snapshot)
        return True
    except Exception:
        return False


def timeit(section: str):
    """
    Context manager for conveniently timing a block of code.

    Usage:
        from world.performance import timeit
        with timeit("combat_round"):
            do_work()
    """
    class _Timer:
        def __init__(self, section):
            self.section = section

        def __enter__(self):
            self.start = time.time()
            return self

        def __exit__(self, *args):
            elapsed = time.time() - self.start
            record_timing(self.section, elapsed)

    return _Timer(section)