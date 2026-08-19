"""
Evennia-shell verification for movement/exit fix.

Paste the following lines into an Evennia shell (``evennia shell``) or
run each block individually to confirm the fix is working.

This script requires an active database.  It is NOT a Django test —
it validates the in-game behaviour against the live/cached objects.
"""

# ================================================================
# BLOCK 1 — CmdMove parser coverage
# ================================================================
# from evennia.commands.cmdset import CmdSet
# from evennia.commands.cmdparser import build_matches
# from commands.movement import CmdMove
# 
# cmd = CmdMove()
# cs = CmdSet(None)
# cs.add(cmd)
# 
# for raw in ["n", "north", "ne", "northeast", "se", "southeast"]:
#     matches = build_matches(raw, cs, include_prefixes=True)
#     print(f"  {raw:12s} -> {'OK' if matches else 'MISSING'}")

# EXPECTED: all lines show "OK"


# ================================================================
# BLOCK 2 — Exit alias coverage (per-exit)
# ================================================================
# from evennia.objects.models import ObjectDB
# 
# exits = ObjectDB.objects.filter(
#     db_typeclass_path__iendswith="exit",
#     db_key__in=["n", "ne", "nw", "se", "sw", "e", "w", "s", "north", "south"],
# ).exclude(db_destination__isnull=True)[:10]
# 
# for ex in exits:
#     aliases = list(ex.aliases.all())
#     print(f"  key={ex.key!r:8s}  aliases={aliases}")


# ================================================================
# BLOCK 3 — Live traversal test (requires a character in a room)
# ================================================================
# from evennia.objects.models import ObjectDB
# from commands.movement import CmdMove
# 
# # Find a room that has exits, and a character in it
# room = ObjectDB.objects.filter(
#     db_typeclass_path__iendswith="rooms.Room",
# ).exclude(db_location__isnull=False).first()
# 
# if room:
#     exits_present = list(room.exits)
#     print(f"Room: {room.key}")
#     print(f"Exits: {[e.key for e in exits_present]}")
#     
#     # Find a character in the room
#     char = None
#     for obj in room.contents:
#         if obj.has_account:
#             char = obj
#             break
#     
#     if char:
#         print(f"Character: {char.key} at {char.location.key}")
#         for ex in exits_present[:3]:
#             cmd = CmdMove()
#             cmd.caller = char
#             raw = ex.key
#             cmd.cmdstring = raw
#             cmd.args = ""
#             print(f"  Testing '{raw}' ...")
#             cmd.func()
#             print(f"  New location: {char.location.key}")
#             # Move back
#             char.move_to(room)
#     else:
#         print("No character found in room — skipping live test")
# else:
#     print("No room found — skipping live test")


# ================================================================
# BLOCK 4 — Migration dry-run
# ================================================================
# from fix_exit_aliases import fix_all_exits
# fix_all_exits(dry_run=True)
# fix_all_exits(dry_run=False)  # run for real

# EXPECTED: ~27,400 exits updated, no errors