"""
Realm Cleanup Script
====================
Wipes ALL rooms, exits, objects, NPCs, mobs, items, and non-admin accounts.
Keeps only the 'mohican' admin account.

Run in `evennia shell`:
    import world.cleanup as cleanup
    cleanup.wipe_all()
"""

from evennia.objects.models import ObjectDB
from evennia.accounts.models import AccountDB


def wipe_all():
    """
    Destroy every object in the database except the 'mohican' account.
    This includes: rooms, exits, characters, NPCs, mobs, items, etc.
    """
    print("=" * 60)
    print("  REALM CLEANUP - WIPING ALL OBJECTS")
    print("=" * 60)

    # --- 1. Nuke all non-admin accounts ---
    accounts = list(AccountDB.objects.all())
    deleted_accounts = 0
    for acct in accounts:
        if acct.username.lower() != "mohican":
            acct.delete()
            deleted_accounts += 1
    print(f"Deleted {deleted_accounts} non-admin accounts.")

    # --- 2. Nuke all objects (rooms, exits, chars, items, everything) ---
    objects = list(ObjectDB.objects.all())
    total = len(objects)
    print(f"Found {total} total objects. Deleting...")

    # Delete in reverse dependency order: items first, then characters/NPCs,
    # then exits, then rooms. But Django handles cascading, so we can just
    # delete everything. However, to avoid issues with contents being deleted
    # before containers, we sort by typeclass priority.
    priority_order = {
        "MUDItem": 0,
        "Shopkeeper": 1,
        "NPC": 1,
        "Mob": 1,
        "Character": 1,
        "Exit": 2,
        "Room": 3,
    }

    def sort_key(obj):
        name = obj.__class__.__name__
        return priority_order.get(name, 99)

    objects.sort(key=sort_key)

    deleted = 0
    for obj in objects:
        try:
            obj.delete()
            deleted += 1
        except Exception as e:
            print(f"  WARNING: Could not delete {obj.key!r} ({obj.__class__.__name__}): {e}")

    print(f"Deleted {deleted}/{total} objects.")

    # --- 3. Verify ---
    remaining_objects = list(ObjectDB.objects.all())
    remaining_accounts = list(AccountDB.objects.all())
    print(f"\nRemaining objects:  {len(remaining_objects)}")
    print(f"Remaining accounts: {len(remaining_accounts)}")
    for acct in remaining_accounts:
        print(f"  Account: {acct.username}")

    print("=" * 60)
    print("  CLEANUP COMPLETE")
    print("=" * 60)


def status():
    """Quick status check of the database."""
    objects = list(ObjectDB.objects.all())
    accounts = list(AccountDB.objects.all())

    rooms = [o for o in objects if o.__class__.__name__ == "Room"]
    exits = [o for o in objects if o.__class__.__name__ == "Exit"]
    chars = [o for o in objects if o.__class__.__name__ == "Character"]

    print(f"Objects total:  {len(objects)}")
    print(f"  Rooms:        {len(rooms)}")
    print(f"  Exits:        {len(exits)}")
    print(f"  Characters:   {len(chars)}")
    print(f"  Other:        {len(objects) - len(rooms) - len(exits) - len(chars)}")
    print(f"Accounts:       {len(accounts)}")
    for acct in accounts:
        print(f"  - {acct.username}")