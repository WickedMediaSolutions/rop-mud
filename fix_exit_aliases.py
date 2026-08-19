#!/usr/bin/env python
"""
One-shot migration: add full-name aliases to every directional exit.

Run this ONCE from the command line after deploying the updated
typeclasses/exits.py and commands/movement.py:

    evennia shell
    > @py from fix_exit_aliases import fix_all_exits; fix_all_exits()

Or directly:
    python fix_exit_aliases.py

What it does:
  - Iterates over all exits whose keys are short direction abbreviations
    (n, s, e, w, ne, nw, se, sw, u, d).
  - Adds the full canonical name as an alias (e.g. 'n' -> 'north').
  - Also adds the short alias itself (idempotent).
  - Reports how many exits were updated.

This is a one-time migration.  Any exit created AFTER the new
Exit.at_object_creation() code is deployed will automatically get
bidirectional aliases.
"""

import django
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

try:
    django.setup()
except Exception as e:
    print(f"django.setup() failed: {e}", file=sys.stderr)
    raise SystemExit(1)

from evennia.objects.models import ObjectDB
from typeclasses.exits import DIRECTION_ALIASES, normalize_direction

SHORT_TO_CANONICAL = {}
for canonical, shorts in DIRECTION_ALIASES.items():
    for short in shorts:
        SHORT_TO_CANONICAL[short] = canonical


def fix_all_exits(dry_run=False):
    """
    Add full-name aliases to every directional exit in the database.

    Keyword Args:
        dry_run (bool): If True, print what would be changed without
            actually saving.
    """
    updated = 0
    skipped = 0

    # Only fetch exits with short-direction keys.  We use values() to avoid
    # instantiating full Evennia objects (which can trigger at_init hooks).
    short_keys = list(SHORT_TO_CANONICAL.keys())
    exit_rows = ObjectDB.objects.filter(
        db_typeclass_path__iendswith="exit",
        db_key__in=short_keys,
    ).exclude(db_destination__isnull=True).values("id", "db_key")

    print(f"Found {exit_rows.count()} short-key directional exits.")

    for row in exit_rows:
        canonical = SHORT_TO_CANONICAL.get(row["db_key"])
        if canonical is None:
            skipped += 1
            continue

        try:
            # Fetch the full object so we can modify aliases
            obj = ObjectDB.objects.get(id=row["id"])
            current_aliases = set(obj.aliases.all())

            new_aliases = set()
            new_aliases.add(canonical)  # full name, e.g. 'north'
            for short in DIRECTION_ALIASES.get(canonical, []):
                new_aliases.add(short)

            # Only add aliases that aren't already present
            aliases_to_add = new_aliases - current_aliases
            if aliases_to_add:
                if not dry_run:
                    for alias in aliases_to_add:
                        obj.aliases.add(alias)
                updated += 1
                if updated % 1000 == 0:
                    print(f"  ... processed {updated} exits so far")
            else:
                skipped += 1
        except Exception as e:
            print(f"  ERROR on exit id={row['id']}: {e}", file=sys.stderr)

    print(f"\nDone.  Updated: {updated}, Already correct: {skipped}")

    if dry_run:
        print("(DRY RUN — no changes saved)")
    else:
        print("Changes saved to database.")


if __name__ == "__main__":
    fix_all_exits()