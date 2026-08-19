#!/usr/bin/env python3
"""
Generate REALM_STATS.txt by querying the Evennia database directly.
Run with: python generate_stats.py
"""
import os
import sys
import django


def generate_stats():
    """Generate REALM_STATS.txt from the Evennia database."""
    # Point Django at Evennia's settings
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "evennia.settings_default")
    os.environ.setdefault("EVENNIA_SETTINGS_MODULE", "server.conf.settings")

    # Add Evennia to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "evennia"))

    import evennia
    evennia._init()

    from evennia.objects.models import ObjectDB
    from evennia.accounts.models import AccountDB

    all_objects = list(ObjectDB.objects.all())

    # Rooms
    rooms = [o for o in all_objects if o.__class__.__name__ == "Room"]

    # Exits
    exits = [o for o in all_objects if o.destination]

    # Items (MUDItem typeclass)
    items = [
        o for o in all_objects
        if hasattr(o, 'typeclass_path') and o.typeclass_path.endswith("MUDItem")
    ]

    # Mobs
    mobs = [
        o for o in all_objects
        if (
            (hasattr(o, 'typeclass_path') and o.typeclass_path.endswith("Mob"))
            or o.attributes.get("is_mob", default=False)
        )
    ]

    # NPCs
    npcs = [
        o for o in all_objects
        if (
            (hasattr(o, 'typeclass_path') and o.typeclass_path.endswith("NPC"))
            or o.attributes.get("is_npc", default=False)
        )
    ]

    # Shopkeepers
    shops = [
        o for o in all_objects
        if (
            (hasattr(o, 'typeclass_path') and o.typeclass_path.endswith("Shopkeeper"))
            or o.attributes.get("is_vendor", default=False)
        )
    ]

    # Player Characters
    from typeclasses.characters import Character
    players = [o for o in all_objects if isinstance(o, Character)]

    # Accounts
    accounts = list(AccountDB.objects.all())

    # Faction breakdown
    good_mobs = [m for m in mobs if m.attributes.get("faction", "") == "good"]
    evil_mobs = [m for m in mobs if m.attributes.get("faction", "") == "evil"]
    neutral_mobs = [m for m in mobs if m.attributes.get("faction", "") == "neutral"]
    aggro_mobs = [m for m in mobs if m.attributes.get("aggro", default=False)]
    passive_mobs = [m for m in mobs if not m.attributes.get("aggro", default=False)]

    # Alignment breakdown
    good_players = [p for p in players if p.attributes.get("alignment", "") == "Good"]
    evil_players = [p for p in players if p.attributes.get("alignment", "") == "Evil"]
    neutral_players = [p for p in players if p.attributes.get("alignment", "") not in ("Good", "Evil")]

    # Online
    online_players = [p for p in players if hasattr(p, 'sessions') and p.sessions.count() > 0]

    # Items on ground vs inventory
    items_on_ground = [i for i in items if i.location and i.location.__class__.__name__ == "Room"]
    items_in_inventory = len(items) - len(items_on_ground)

    # Zones
    zones = {}
    for room in rooms:
        zone_tags = room.tags.get(category="zone")
        if zone_tags:
            zone_name = zone_tags[0] if isinstance(zone_tags, (list, tuple)) else zone_tags
            zones[zone_name] = zones.get(zone_name, 0) + 1

    # Write stats file
    with open("REALM_STATS.txt", "w") as f:
        f.write("=" * 55 + "\n")
        f.write("           Realm Statistics\n")
        f.write("=" * 55 + "\n\n")

        f.write("--- World Structure ---\n")
        f.write(f"  Rooms:  {len(rooms)}\n")
        f.write(f"  Exits:  {len(exits)}\n")
        if zones:
            f.write(f"  Zones:  {len(zones)}\n")
            for zone_name, count in sorted(zones.items()):
                f.write(f"    {zone_name}: {count} rooms\n")
        f.write("\n")

        f.write("--- Entities ---\n")
        f.write(f"  Mobs:       {len(mobs)}\n")
        f.write(f"    Good:      {len(good_mobs)}\n")
        f.write(f"    Evil:      {len(evil_mobs)}\n")
        f.write(f"    Neutral:   {len(neutral_mobs)}\n")
        f.write(f"    Aggressive: {len(aggro_mobs)}\n")
        f.write(f"    Passive:    {len(passive_mobs)}\n")
        f.write(f"  NPCs:       {len(npcs)}\n")
        f.write(f"  Shopkeepers: {len(shops)}\n")
        f.write("\n")

        f.write("--- Items ---\n")
        f.write(f"  Total Items:       {len(items)}\n")
        f.write(f"  On Ground:         {len(items_on_ground)}\n")
        f.write(f"  In Inventories:    {items_in_inventory}\n")
        f.write("\n")

        f.write("--- Players & Accounts ---\n")
        f.write(f"  Characters:  {len(players)}\n")
        f.write(f"    Good:      {len(good_players)}\n")
        f.write(f"    Evil:      {len(evil_players)}\n")
        f.write(f"    Neutral:   {len(neutral_players)}\n")
        f.write(f"  Online Now:  {len(online_players)}\n")
        f.write(f"  Accounts:    {len(accounts)}\n")
        f.write("\n")

        total_entities = len(mobs) + len(npcs) + len(shops) + len(items) + len(players)
        f.write("-" * 55 + "\n")
        f.write(f"  Grand Total Entities: {total_entities}\n")
        f.write("=" * 55 + "\n")

    print("REALM_STATS.txt written successfully.")
    print(f"Rooms: {len(rooms)}, Exits: {len(exits)}, Mobs: {len(mobs)}, NPCs: {len(npcs)}, Shops: {len(shops)}, Items: {len(items)}, Players: {len(players)}, Accounts: {len(accounts)}")


# Alias for test compatibility
generate_stats_report = generate_stats


if __name__ == "__main__":
    generate_stats()