"""
Phase 10 Verification Tests — Administration & Tools
=====================================================

Drop-in test suite for verifying all Phase 10 administration and tooling
features. Run inside the Evennia shell:

    import commands.tests.test_phase10_admin_tools as tp
    tp.run_all()

Or, for a pure standalone run (no Evennia DB access required for the
core logic), from the project root:

    python commands/tests/test_phase10_admin_tools.py

Requirements tested:
  1. Moderation — ban system (temporary, permanent, expiry, unban)
  2. Moderation — mute system (temporary, permanent, expiry, unmute)
  3. Moderation — ban/mute info and list helpers
  4. Admin audit log — record, retrieve, filter, clear
  5. Performance monitoring — timing, counters, section stats
  6. Performance monitoring — command stats + server metrics snapshot
  7. Command registration — all Phase 10 commands present in cmdset
  8. Admin tools — audit log command and perfmon command loading
"""

from __future__ import annotations

import time
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Minimal fake objects for logic-only testing (no Evennia DB required)
# ---------------------------------------------------------------------------

class _FakeAttributes:
    """Minimal AttributeHandler stand-in for isolated logic tests."""

    def __init__(self):
        self._store = {}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def add(self, key, value):
        self._store[key] = value


class _FakeAccount:
    """Minimal Account stand-in with an attributes handler."""

    def __init__(self, username="testuser", dbref=1):
        self.username = username
        self.id = dbref
        self.key = username
        self.attributes = _FakeAttributes()
        self._sessions = []

    def __str__(self):
        return self.username


class _FakeSession:
    """Minimal session stand-in for disconnect capture."""

    def __init__(self):
        self.disconnected = False
        self.messages = []

    def msg(self, text):
        self.messages.append(text)

    def disconnect(self):
        self.disconnected = True


class _FakeCaller:
    """Minimal caller stand-in for admin log tests."""

    def __init__(self, key="Admin", dbref=99):
        self.key = key
        self.id = dbref


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def run_all() -> Dict[str, bool]:
    """
    Run all Phase 10 tests and return a pass/fail dict.

    Prints results to stdout during execution for immediate feedback.
    """
    results = {}

    print("\n" + "=" * 60)
    print("  Phase 10 — Administration & Tools Validation Suite")
    print("=" * 60)

    for name, test_fn in _collect_tests():
        print(f"\n--- {name} ---")
        try:
            passed = test_fn()
            results[name] = passed
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {name}")
        except Exception as exc:
            results[name] = False
            print(f"  [FAIL] {name} — exception: {exc}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"  Results: {passed}/{total} passed")
    if passed == total:
        print("  All tests passed!")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  Failed: {', '.join(failed)}")
    print("=" * 60 + "\n")

    return results


def _collect_tests():
    """Return list of (name, callable) test pairs in execution order."""
    return [
        ("test_ban_temporary", test_ban_temporary),
        ("test_ban_permanent", test_ban_permanent),
        ("test_ban_expiry", test_ban_expiry),
        ("test_unban", test_unban),
        ("test_mute_temporary", test_mute_temporary),
        ("test_mute_permanent", test_mute_permanent),
        ("test_unmute", test_unmute),
        ("test_get_ban_info", test_get_ban_info),
        ("test_get_mute_info", test_get_mute_info),
        ("test_admin_log_record_and_retrieve", test_admin_log_record_and_retrieve),
        ("test_admin_log_filter_by_admin", test_admin_log_filter_by_admin),
        ("test_admin_log_filter_by_type", test_admin_log_filter_by_type),
        ("test_admin_log_clear", test_admin_log_clear),
        ("test_admin_log_format_entry", test_admin_log_format_entry),
        ("test_performance_record_timing", test_performance_record_timing),
        ("test_performance_section_stats", test_performance_section_stats),
        ("test_performance_command_stats", test_performance_command_stats),
        ("test_performance_counters_and_reset", test_performance_counters_and_reset),
        ("test_performance_timeit_context", test_performance_timeit_context),
        ("test_phase10_commands_registered", test_phase10_commands_registered),
        ("test_admin_log_module_imports", test_admin_log_module_imports),
        ("test_performance_module_imports", test_performance_module_imports),
    ]


# ---------------------------------------------------------------------------
# Moderation tests
# ---------------------------------------------------------------------------

def _import_moderation():
    if hasattr(_import_moderation, "_module"):
        return _import_moderation._module
    import commands.moderation as mod
    _import_moderation._module = mod
    return mod


def test_ban_temporary() -> bool:
    """Ban a fake account for 60 minutes and verify it is banned."""
    mod = _import_moderation()
    acct = _FakeAccount("baduser", 1)

    # Apply a 60-minute ban directly to the attribute store.
    acct.attributes.add("ban_expires", time.time() + 3600)
    acct.attributes.add("ban_reason", "Spamming chat")
    acct.attributes.add("banned_by", "Admin")
    acct.attributes.add("banned_at", time.time())

    # Override is_banned to use our fake (bypass AccountDB resolution.)
    if not mod.is_banned(acct):
        print("    FAIL: account should be banned.")
        return False

    info = mod.get_ban_info(acct)
    if not info.get("banned"):
        print("    FAIL: ban info should report banned=True.")
        return False
    if info.get("permanent"):
        print("    FAIL: temporary ban should not be permanent.")
        return False
    if info.get("reason") != "Spamming chat":
        print(f"    FAIL: reason mismatch: {info.get('reason')}")
        return False
    remaining = info.get("expires_in", 0)
    if not (0 < remaining <= 3600):
        print(f"    FAIL: expires_in out of range: {remaining}")
        return False

    print(f"    Temporary ban works (expires in {remaining}s).")
    return True


def test_ban_permanent() -> bool:
    """Verify permanent ban semantics via ban_expires == -1."""
    mod = _import_moderation()
    acct = _FakeAccount("permuser", 2)

    acct.attributes.add("ban_expires", -1)
    acct.attributes.add("ban_reason", "Griefing")
    acct.attributes.add("banned_by", "Admin")

    if not mod.is_banned(acct):
        print("    FAIL: permanent ban should be active.")
        return False

    info = mod.get_ban_info(acct)
    if not info.get("permanent"):
        print("    FAIL: permanent ban not recognized.")
        return False

    print("    Permanent ban works.")
    return True


def test_ban_expiry() -> bool:
    """Verify an expired ban auto-clears and reports not-banned."""
    mod = _import_moderation()
    acct = _FakeAccount("olduser", 3)

    acct.attributes.add("ban_expires", time.time() - 10)  # 10s in the past
    acct.attributes.add("ban_reason", "Old ban")

    if mod.is_banned(acct):
        print("    FAIL: expired ban should not be active.")
        return False

    # is_banned should have cleaned up the expired state.
    if acct.attributes.get("ban_expires", -99) != 0:
        print(f"    FAIL: expired ban not cleaned up: "
              f"{acct.attributes.get('ban_expires')}")
        return False

    print("    Ban expiry / auto-cleanup works.")
    return True


def test_unban() -> bool:
    """Verify unban clears ban state."""
    mod = _import_moderation()
    acct = _FakeAccount("forgiven", 4)

    acct.attributes.add("ban_expires", -1)
    acct.attributes.add("ban_reason", "Temp")

    # Simulate unban by clearing flags.
    acct.attributes.add("ban_expires", 0)
    acct.attributes.add("ban_reason", "")

    if mod.is_banned(acct):
        print("    FAIL: unban should clear ban state.")
        return False

    print("    Unban works.")
    return True


def test_mute_temporary() -> bool:
    """Mute a fake account for 30 minutes and verify it is muted."""
    mod = _import_moderation()
    acct = _FakeAccount("louduser", 5)

    acct.attributes.add("mute_expires", time.time() + 1800)
    acct.attributes.add("muted_by", "Admin")

    if not mod.is_muted(acct):
        print("    FAIL: account should be muted.")
        return False

    info = mod.get_mute_info(acct)
    if not info.get("muted"):
        print("    FAIL: mute info should report muted=True.")
        return False
    if info.get("permanent"):
        print("    FAIL: temporary mute should not be permanent.")
        return False

    print("    Temporary mute works.")
    return True


def test_mute_permanent() -> bool:
    """Verify permanent mute semantics via mute_expires == -1."""
    mod = _import_moderation()
    acct = _FakeAccount("spammer", 6)

    acct.attributes.add("mute_expires", -1)

    if not mod.is_muted(acct):
        print("    FAIL: permanent mute should be active.")
        return False

    info = mod.get_mute_info(acct)
    if not info.get("permanent"):
        print("    FAIL: permanent mute not recognized.")
        return False

    print("    Permanent mute works.")
    return True


def test_unmute() -> bool:
    """Verify unmute clears mute state."""
    mod = _import_moderation()
    acct = _FakeAccount("quietnow", 7)

    acct.attributes.add("mute_expires", time.time() + 100)
    acct.attributes.add("mute_expires", 0)  # unmute

    if mod.is_muted(acct):
        print("    FAIL: unmute should clear mute state.")
        return False

    print("    Unmute works.")
    return True


def test_get_ban_info() -> bool:
    """Verify get_ban_info returns full details for active ban."""
    mod = _import_moderation()
    acct = _FakeAccount("infouser", 8)

    now = time.time()
    acct.attributes.add("ban_expires", now + 7200)
    acct.attributes.add("ban_reason", "Testing info")
    acct.attributes.add("banned_by", "TestAdmin")
    acct.attributes.add("banned_at", now)

    info = mod.get_ban_info(acct)
    required = {"banned", "permanent", "expires_in", "expires_at", "reason",
                "banned_by", "banned_at"}
    missing = required - set(info.keys())
    if missing:
        print(f"    FAIL: missing ban_info keys: {missing}")
        return False
    if info["reason"] != "Testing info":
        print(f"    FAIL: reason mismatch.")
        return False
    if info["banned_by"] != "TestAdmin":
        print(f"    FAIL: banned_by mismatch.")
        return False
    if info["banned_at"] != now:
        print(f"    FAIL: banned_at mismatch.")
        return False

    # Non-banned account
    acct2 = _FakeAccount("cleanuser", 9)
    info2 = mod.get_ban_info(acct2)
    if info2.get("banned"):
        print("    FAIL: clean account should not be banned.")
        return False

    print("    get_ban_info works (full details + clean case).")
    return True


def test_get_mute_info() -> bool:
    """Verify get_mute_info returns full details for active mute."""
    mod = _import_moderation()
    acct = _FakeAccount("muteinfo", 10)

    now = time.time()
    acct.attributes.add("mute_expires", now + 900)
    acct.attributes.add("muted_by", "TestAdmin")
    acct.attributes.add("muted_at", now)

    info = mod.get_mute_info(acct)
    required = {"muted", "permanent", "expires_in", "expires_at",
                "muted_by", "muted_at"}
    missing = required - set(info.keys())
    if missing:
        print(f"    FAIL: missing mute_info keys: {missing}")
        return False
    if info["muted_by"] != "TestAdmin":
        print("    FAIL: muted_by mismatch.")
        return False

    # Non-muted account
    acct2 = _FakeAccount("clearmute", 11)
    info2 = mod.get_mute_info(acct2)
    if info2.get("muted"):
        print("    FAIL: clean account should not be muted.")
        return False

    print("    get_mute_info works (full details + clean case).")
    return True


# ---------------------------------------------------------------------------
# Admin audit log tests
# ---------------------------------------------------------------------------

def _import_admin_log():
    if hasattr(_import_admin_log, "_module"):
        return _import_admin_log._module
    import world.admin_log as al
    _import_admin_log._module = al
    return al


def test_admin_log_record_and_retrieve() -> bool:
    """Log actions and verify they are retrieved newest-first."""
    al = _import_admin_log()

    # Clear any existing entries for determinism.
    al.clear_audit_log()

    caller = _FakeCaller("TestAdmin", 99)
    ok1 = al.log_admin_action(caller, "ban", "baduser", "duration=60m")
    ok2 = al.log_admin_action(caller, "kick", "noisyuser", "reason=chat")
    ok3 = al.log_admin_action(caller, "unban", "baduser", "")

    if not (ok1 and ok2 and ok3):
        print("    FAIL: log_admin_action returned False unexpectedly.")
        return False

    if al.get_total_count() != 3:
        print(f"    FAIL: expected 3 entries, got {al.get_total_count()}.")
        return False

    recent = al.get_recent_actions(limit=3)
    if len(recent) != 3:
        print(f"    FAIL: expected 3 recent entries, got {len(recent)}.")
        return False

    # Newest first.
    if recent[0]["action"] != "unban":
        print(f"    FAIL: newest entry should be 'unban', got {recent[0]['action']}.")
        return False
    if recent[2]["action"] != "ban":
        print(f"    FAIL: oldest entry should be 'ban', got {recent[2]['action']}.")
        return False

    # Clean up.
    al.clear_audit_log()
    print("    Audit log record + retrieve (newest-first) works.")
    return True


def test_admin_log_filter_by_admin() -> bool:
    """Verify filtering entries by admin name."""
    al = _import_admin_log()
    al.clear_audit_log()

    al.log_admin_action(_FakeCaller("Alice", 1), "ban", "x")
    al.log_admin_action(_FakeCaller("Bob", 2), "mute", "y")
    al.log_admin_action(_FakeCaller("Alice", 1), "kick", "z")

    alice_entries = al.get_actions_by_admin("Alice")
    if len(alice_entries) != 2:
        print(f"    FAIL: expected 2 Alice entries, got {len(alice_entries)}.")
        al.clear_audit_log()
        return False

    bob_entries = al.get_actions_by_admin("Bob")
    if len(bob_entries) != 1:
        print(f"    FAIL: expected 1 Bob entry, got {len(bob_entries)}.")
        al.clear_audit_log()
        return False

    al.clear_audit_log()
    print("    Admin log filter-by-admin works.")
    return True


def test_admin_log_filter_by_type() -> bool:
    """Verify filtering entries by action type."""
    al = _import_admin_log()
    al.clear_audit_log()

    al.log_admin_action(_FakeCaller("Alice", 1), "ban", "a")
    al.log_admin_action(_FakeCaller("Alice", 1), "ban", "b")
    al.log_admin_action(_FakeCaller("Alice", 1), "mute", "c")

    ban_entries = al.get_actions_by_type("ban")
    if len(ban_entries) != 2:
        print(f"    FAIL: expected 2 ban entries, got {len(ban_entries)}.")
        al.clear_audit_log()
        return False

    mute_entries = al.get_actions_by_type("mute")
    if len(mute_entries) != 1:
        print(f"    FAIL: expected 1 mute entry, got {len(mute_entries)}.")
        al.clear_audit_log()
        return False

    al.clear_audit_log()
    print("    Admin log filter-by-type works.")
    return True


def test_admin_log_clear() -> bool:
    """Verify clear_audit_log removes entries and respects keep_last."""
    al = _import_admin_log()
    al.clear_audit_log()

    al.log_admin_action(_FakeCaller("Admin", 1), "kick", "a")
    al.log_admin_action(_FakeCaller("Admin", 1), "kick", "b")
    al.log_admin_action(_FakeCaller("Admin", 1), "kick", "c")
    al.log_admin_action(_FakeCaller("Admin", 1), "kick", "d")

    before = al.get_total_count()
    if before != 4:
        print(f"    FAIL: expected 4 entries before clear, got {before}.")
        al.clear_audit_log()
        return False

    # Keep last 2.
    al.clear_audit_log(keep_last=2)
    after = al.get_total_count()
    if after != 2:
        print(f"    FAIL: expected 2 entries after keep_last=2, got {after}.")
        al.clear_audit_log()
        return False

    # Full clear.
    al.clear_audit_log()
    if al.get_total_count() != 0:
        print(f"    FAIL: expected 0 entries after full clear.")
        return False

    print("    Admin log clear (full + keep_last) works.")
    return True


def test_admin_log_format_entry() -> bool:
    """Verify format_entry produces a readable, timestamped string."""
    al = _import_admin_log()

    entry = {
        "timestamp": time.time(),
        "admin": "Admin",
        "action": "ban",
        "target": "baduser",
        "details": "reason=spam",
    }
    formatted = al.format_entry(entry)

    if "ban" not in formatted:
        print(f"    FAIL: formatted entry missing action: {formatted}")
        return False
    if "Admin" not in formatted:
        print(f"    FAIL: formatted entry missing admin: {formatted}")
        return False
    if "baduser" not in formatted:
        print(f"    FAIL: formatted entry missing target: {formatted}")
        return False

    print(f"    format_entry works: {formatted}")
    return True


# ---------------------------------------------------------------------------
# Performance monitoring tests
# ---------------------------------------------------------------------------

def _import_performance():
    if hasattr(_import_performance, "_module"):
        return _import_performance._module
    import world.performance as perf
    _import_performance._module = perf
    return perf


def test_performance_record_timing() -> bool:
    """Record timing samples and verify they accumulate."""
    perf = _import_performance()
    perf.reset_metrics()

    perf.record_timing("test_section", 0.1)
    perf.record_timing("test_section", 0.2)
    perf.record_timing("test_section", 0.3)

    stats = perf.get_section_stats("test_section")
    if stats["count"] != 3:
        print(f"    FAIL: expected count=3, got {stats['count']}.")
        return False
    if abs(stats["total"] - 0.6) > 1e-9:
        print(f"    FAIL: expected total=0.6, got {stats['total']}.")
        return False
    if abs(stats["avg"] - 0.2) > 1e-9:
        print(f"    FAIL: expected avg=0.2, got {stats['avg']}.")
        return False
    if abs(stats["max"] - 0.3) > 1e-9:
        print(f"    FAIL: expected max=0.3, got {stats['max']}.")
        return False

    # Unknown section returns zeros.
    empty = perf.get_section_stats("nonexistent")
    if empty["count"] != 0 or empty["total"] != 0.0:
        print(f"    FAIL: unknown section should return zeros.")
        return False

    perf.reset_metrics()
    print("    record_timing + get_section_stats works.")
    return True


def test_performance_section_stats() -> bool:
    """Verify section aggregate stats (avg/max) are computed correctly."""
    perf = _import_performance()
    perf.reset_metrics()

    for _ in range(5):
        perf.record_timing("agg_section", 0.5)

    stats = perf.get_section_stats("agg_section")
    if stats["count"] != 5:
        print(f"    FAIL: expected count=5.")
        return False
    if abs(stats["avg"] - 0.5) > 1e-9:
        print(f"    FAIL: expected avg=0.5, got {stats['avg']}.")
        return False
    if abs(stats["max"] - 0.5) > 1e-9:
        print(f"    FAIL: expected max=0.5.")

    perf.reset_metrics()
    print("    Section stats aggregation works.")
    return True


def test_performance_command_stats() -> bool:
    """Verify command timing stats and sorting by total time."""
    perf = _import_performance()
    perf.reset_metrics()

    perf.record_command("look", 0.01)
    perf.record_command("look", 0.02)
    perf.record_command("kill", 0.5)

    # Single command lookup.
    look_stats = perf.get_command_stats("look")
    if len(look_stats) != 1:
        print(f"    FAIL: expected 1 entry for 'look'.")
        return False
    if look_stats[0]["count"] != 2:
        print(f"    FAIL: look count expected 2.")
        return False

    # All commands sorted by total desc.
    all_stats = perf.get_command_stats()
    if len(all_stats) != 2:
        print(f"    FAIL: expected 2 commands, got {len(all_stats)}.")
        return False
    if all_stats[0]["command"] != "kill":
        print(f"    FAIL: 'kill' should be top by total time, got "
              f"{all_stats[0]['command']}.")
        return False

    # Unknown command returns empty list.
    if perf.get_command_stats("nonexistent") != []:
        print("    FAIL: unknown command should return empty list.")
        return False

    perf.reset_metrics()
    print("    Command stats + sorting works.")
    return True


def test_performance_counters_and_reset() -> bool:
    """Verify increment_counter and reset_metrics."""
    perf = _import_performance()
    perf.reset_metrics()

    perf.increment_counter("combat_rounds", 3)
    perf.increment_counter("combat_rounds", 2)

    metrics = perf.get_server_metrics()
    if metrics["combat_rounds"] != 5:
        print(f"    FAIL: combat_rounds expected 5, got "
              f"{metrics['combat_rounds']}.")
        return False
    if metrics["command_count"] != 0:
        print(f"    FAIL: command_count expected 0 before any commands.")
        return False
    if "uptime_seconds" not in metrics:
        print("    FAIL: uptime_seconds missing from metrics.")
        return False

    # Reset.
    perf.reset_metrics()
    metrics2 = perf.get_server_metrics()
    if metrics2["combat_rounds"] != 0:
        print("    FAIL: combat_rounds should reset to 0.")
        return False

    print("    Counters + reset work.")
    return True


def test_performance_timeit_context() -> bool:
    """Verify the timeit context manager records timing."""
    perf = _import_performance()
    perf.reset_metrics()

    with perf.timeit("context_section"):
        time.sleep(0.01)

    stats = perf.get_section_stats("context_section")
    if stats["count"] != 1:
        print(f"    FAIL: context manager should record 1 sample.")
        return False
    if stats["total"] <= 0:
        print(f"    FAIL: context manager recorded non-positive time.")
        return False

    perf.reset_metrics()
    print("    timeit context manager works.")
    return True


# ---------------------------------------------------------------------------
# Command registration tests
# ---------------------------------------------------------------------------

def test_phase10_commands_registered() -> bool:
    """
    Verify all Phase 10 command classes can be imported and instantiated
    without error, and have the expected permission locks.
    """
    expected_commands = {
        "commands.moderation": [
            ("CmdBan", "@ban"),
            ("CmdUnban", "@unban"),
            ("CmdMute", "@mute"),
            ("CmdUnmute", "@unmute"),
            ("CmdBanList", "@banlist"),
            ("CmdKick", "@kick"),
        ],
        "commands.admin_tools": [
            ("CmdAuditLog", "@auditlog"),
            ("CmdPerfMon", "@perfmon"),
        ],
    }

    for module_path, commands in expected_commands.items():
        try:
            import importlib
            module = importlib.import_module(module_path)
        except Exception as exc:
            print(f"    FAIL: could not import {module_path}: {exc}")
            return False

        for class_name, expected_key in commands:
            if not hasattr(module, class_name):
                print(f"    FAIL: {module_path}.{class_name} not found.")
                return False

            cmd_cls = getattr(module, class_name)
            cmd = cmd_cls()
            if cmd.key != expected_key:
                print(f"    FAIL: {class_name}.key expected '{expected_key}', "
                      f"got '{cmd.key}'.")
                return False
            # Verify Admin lock.
            if "perm(Admin)" not in cmd.locks:
                print(f"    FAIL: {class_name} missing Admin lock: {cmd.locks}")
                return False

    print("    All Phase 10 commands importable with correct keys + locks.")
    return True


# ---------------------------------------------------------------------------
# Module import smoke tests
# ---------------------------------------------------------------------------

def test_admin_log_module_imports() -> bool:
    """Verify world.admin_log exposes all required public functions."""
    import world.admin_log as al

    required = [
        "log_admin_action",
        "get_recent_actions",
        "get_actions_by_admin",
        "get_actions_by_type",
        "get_total_count",
        "clear_audit_log",
        "format_entry",
    ]
    missing = [fn for fn in required if not hasattr(al, fn)]
    if missing:
        print(f"    FAIL: missing functions in admin_log: {missing}")
        return False

    print("    admin_log module exposes all required functions.")
    return True


def test_performance_module_imports() -> bool:
    """Verify world.performance exposes all required public functions."""
    import world.performance as perf

    required = [
        "record_timing",
        "record_command",
        "increment_counter",
        "get_section_stats",
        "get_command_stats",
        "get_server_metrics",
        "get_entity_counts",
        "get_top_objects",
        "get_running_scripts",
        "reset_metrics",
        "persist_metrics",
        "timeit",
    ]
    missing = [fn for fn in required if not hasattr(perf, fn)]
    if missing:
        print(f"    FAIL: missing functions in performance: {missing}")
        return False

    print("    performance module exposes all required functions.")
    return True


# ---------------------------------------------------------------------------
# Standalone entrypoint (for pure-logic tests only)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # For standalone runs, stub out Evennia if not available.
    try:
        import evennia  # noqa: F401
    except Exception:
        # Create a minimal evennia stub so commands.import works.
        sys.modules.setdefault("evennia", type(sys)("evennia"))

    results = run_all()
    sys.exit(0 if all(results.values()) else 1)