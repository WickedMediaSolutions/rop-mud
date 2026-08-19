from evennia import search_tag, search_object, create_object, AccountDB

def fix_realm():
    print("=== FIXING REALM STARTING ROOMS & ACCOUNT ANCHORS ===")

    # 1. Locate Starter Rooms
    gorgoroth_start = search_tag("brimstone_courtyard_1", category="room_id")
    aethelgard_start = search_tag("sunspire_meadows_1", category="room_id")

    if not gorgoroth_start or not aethelgard_start:
        print("ERROR: Starter rooms not found. Run builder phases first.")
        return

    g_room = gorgoroth_start[0]
    a_room = aethelgard_start[0]

    # Update descriptions and tags
    g_room.key = "|rBrimstone Courtyard [Gorgoroth Horde Starter]|n"
    g_room.db.desc = "The smoldering staging grounds of the Gorgoroth Horde. War drums echo from the jagged volcanic walls."
    g_room.tags.add("start_room_gorgoroth", category="spawn")

    a_room.key = "|YAethelgard Sunspire Citadel [Aethelgard Alliance Starter]|n"
    a_room.db.desc = "The radiant courtyard of the Aethelgard Alliance. Banners of white and gold wave atop granite battlements."
    a_room.tags.add("start_room_aethelgard", category="spawn")

    # 2. Fix Orphaned Accounts & Superusers
    restored_count = 0
    for account in AccountDB.objects.all():
        for char in account.characters:
            if not char.location:
                # Default Superusers/Admins or unassigned characters to Gorgoroth or Aethelgard starter
                if account.is_superuser:
                    char.location = g_room
                    char.home = g_room
                else:
                    char.location = a_room
                    char.home = a_room
                char.save()
                restored_count += 1

    print(f" -> Set Gorgoroth Horde Starter: {g_room.dbref}")
    print(f" -> Set Aethelgard Alliance Starter: {a_room.dbref}")
    print(f" -> Re-anchored {restored_count} orphaned character locations.")
    print("=== SETUP RECOVERY COMPLETE ===")

