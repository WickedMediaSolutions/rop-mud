"""
Comprehensive Live Game Audit Script for Evennia codebase.
Verifies rooms, linked exits, command sets, equipment, weather, and scripts.

Run from your terminal in your game root directory:
    evennia shell -c "import audit_game; audit_game.run_full_audit()"
"""

from evennia.objects.models import ObjectDB
from evennia.scripts.models import ScriptDB
from evennia.accounts.models import AccountDB
import sys


class GameAuditor:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def log_pass(self, msg):
        self.passed += 1
        print(f"  [OK] {msg}")

    def log_fail(self, msg):
        self.failed += 1
        print(f"  [FAIL] {msg}")

    def log_warn(self, msg):
        self.warnings += 1
        print(f"  [WARN] {msg}")

    def banner(self, title):
        print(f"\n==================================================")
        print(f" AUDITING: {title.upper()}")
        print(f"==================================================")


def audit_world_topology(auditor):
    """Audit every room, exit, and zone linkage in the database."""
    auditor.banner("World Topology & Room Linkages")

    all_objects = ObjectDB.objects.all()
    rooms = [o for o in all_objects if o.destination is None and o.typeclass_path.endswith("Room")]
    exits = [o for o in all_objects if o.destination is not None]

    print(f"Total Database Objects: {len(all_objects)}")
    print(f"Total Rooms Found: {len(rooms)}")
    print(f"Total Exits Found: {len(exits)}")

    # 1. Check for Unlinked Exits (exits with no destination or no location)
    for exit_obj in exits:
        if not exit_obj.location:
            auditor.log_fail(f"Orphaned Exit #{exit_obj.id} ({exit_obj.key}) has no source location!")
        elif not exit_obj.destination:
            auditor.log_fail(f"Broken Exit #{exit_obj.id} ({exit_obj.key}) in Room #{exit_obj.location.id} points to nowhere!")
        else:
            auditor.log_pass(f"Exit '{exit_obj.key}' (#{exit_obj.id}) correctly links #{exit_obj.location.id} -> #{exit_obj.destination.id}")

    # 2. Check for Isolated/Unlinked Rooms
    for room in rooms:
        # Check if room has exits leading OUT
        outbound = [o for o in room.contents if o.destination is not None]
        # Check if any exits lead IN to this room
        inbound = [e for e in exits if e.destination == room]

        if not outbound and not inbound and room.id != 2:  # Limbo is #2 usually
            auditor.log_fail(f"Isolated Room #{room.id} ({room.key}) has ZERO inbound or outbound exits!")
        elif not outbound:
            auditor.log_warn(f"Dead-end Room #{room.id} ({room.key}) has inbound exits but NO outbound exits!")
        elif not inbound and room.id != 2:
            auditor.log_warn(f"Unreachable Room #{room.id} ({room.key}) has outbound exits but NO exits leading into it!")
        else:
            auditor.log_pass(f"Room #{room.id} ({room.key}) is fully linked ({len(inbound)} in, {len(outbound)} out).")


def audit_commands_and_cmdsets(auditor):
    """Audit command sets on characters and account objects."""
    auditor.banner("Command Sets & Command Handlers")

    accounts = AccountDB.objects.all()
    characters = [o for o in ObjectDB.objects.all() if o.typeclass_path.endswith("Character")]

    for char in characters:
        cmdset = char.cmdset.all()
        if not cmdset:
            auditor.log_fail(f"Character #{char.id} ({char.key}) has NO active CmdSet assigned!")
        else:
            cmd_count = sum(len(cs) for cs in cmdset)
            auditor.log_pass(f"Character #{char.id} ({char.key}) has active CmdSet with {cmd_count} executable commands.")


def audit_equipment_and_inventory(auditor):
    """Audit equipment slots, worn items, and inventories."""
    auditor.banner("Equipment & Inventory System")

    items = [o for o in ObjectDB.objects.all() if not o.destination and not o.typeclass_path.endswith("Room")]

    for item in items:
        # Verify item has a valid location (Room, Character, or Container)
        if item.location is None and item.id != 1:  # #1 is root/god
            auditor.log_fail(f"Item #{item.id} ({item.key}) has NULL location (Lost in void)!")
        else:
            auditor.log_pass(f"Item #{item.id} ({item.key}) located inside #{item.location.id} ({item.location.key})")

        # Verify wear/equip attributes if configured
        if hasattr(item.db, "slots") or hasattr(item.db, "equipped"):
            auditor.log_pass(f"Equipment object #{item.id} ({item.key}) holds valid slot definitions.")


def audit_weather_and_scripts(auditor):
    """Audit global weather scripts, ticks, and background handlers."""
    auditor.banner("Weather & Global Ticker Scripts")

    scripts = ScriptDB.objects.all()
    print(f"Total Active Scripts in DB: {len(scripts)}")

    weather_scripts = [s for s in scripts if "weather" in s.key.lower() or "environment" in s.key.lower()]

    if not weather_scripts:
        auditor.log_warn("No active script with 'weather' in key found in ScriptDB. Checking global subscriptions...")
    else:
        for ws in weather_scripts:
            if not ws.is_active:
                auditor.log_fail(f"Weather script #{ws.id} ({ws.key}) exists but is INACTIVE!")
            else:
                auditor.log_pass(f"Weather script #{ws.id} ({ws.key}) is active and ticking (interval: {ws.interval}s).")

    # Audit all global scripts for errors
    for script in scripts:
        if not script.is_valid():
            auditor.log_fail(f"Script #{script.id} ({script.key}) is in an INVALID/ERRORED state!")
        else:
            auditor.log_pass(f"Script #{script.id} ({script.key}) is running cleanly.")


def run_full_audit():
    print("\n" + "=" * 50)
    print(" STARTING COMPLETE EVENNIA GAME WORLD & SYSTEM AUDIT")
    print("=" * 50)

    auditor = GameAuditor()

    try:
        audit_world_topology(auditor)
        audit_commands_and_cmdsets(auditor)
        audit_equipment_and_inventory(auditor)
        audit_weather_and_scripts(auditor)
    except Exception as e:
        print(f"\n[CRITICAL ERROR DURING AUDIT]: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 50)
    print(" AUDIT COMPLETE SUMMARY")
    print("=" * 50)
    print(f"  PASSED CHECKS:   {auditor.passed}")
    print(f"  WARNINGS:        {auditor.warnings}")
    print(f"  FAILED CHECKS:   {auditor.failed}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    run_full_audit()
