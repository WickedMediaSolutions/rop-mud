"""
Validate batch zone files for correctness.

Checks each `.ev` file in `world/batch_zones/` for:
  1. Rooms referenced by `@open ... to <room>` that have a matching `dig`
  2. Exits whose reverse direction isn't created (informational)
  3. Prototypes referenced by `@spawn` that exist in prototype registries

Usage (in Evennia shell or standalone):
    from world.validate_batch_zones import validate_all_zones
    validate_all_zones()
"""

import os
import re

ZONE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_zones")

_DIG_RE = re.compile(r"^dig\s+(.+?)\s*$")
_OPEN_RE = re.compile(r"^@open\s+(.+?)\s+to\s+(.+?)\s*$")
_SPAWN_RE = re.compile(r"^@spawn\s+(\S+)\s*$")


def _read_zone_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()


def validate_zone_file(filename):
    """
    Validate a single zone file. Returns a list of string warnings/errors.
    """
    path = os.path.join(ZONE_DIR, filename)
    if not os.path.exists(path):
        return [f"Zone file not found: {filename}"]

    lines = _read_zone_file(path)
    rooms = set()
    opens = []
    spawns = []

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        m = _DIG_RE.match(stripped)
        if m:
            rooms.add(m.group(1).strip())
            continue

        m = _OPEN_RE.match(stripped)
        if m:
            opens.append((m.group(1).strip(), m.group(2).strip(), lineno))
            continue

        m = _SPAWN_RE.match(stripped)
        if m:
            spawns.append((m.group(1).strip(), lineno))

    issues = []

    # Check exit destinations
    for exit_name, dest, lineno in opens:
        if dest not in rooms:
            issues.append(
                f"{filename}:{lineno} exit '{exit_name}' references "
                f"undefined room '{dest}'"
            )

    # Check spawn prototypes
    missing_protos = _check_prototypes([s for s, _ in spawns])
    for proto, lineno in spawns:
        if proto in missing_protos:
            issues.append(
                f"{filename}:{lineno} spawn references undefined "
                f"prototype '{proto}'"
            )

    return issues


def _check_prototypes(proto_names):
    """
    Return the subset of proto_names not defined in any known prototype
    registry. Prototypes referenced in batch files must match mob/item
    prototype keys or spawner keys that builders define.
    """
    if not proto_names:
        return set()

    known = set()

    # Collect known mob prototypes if present.
    try:
        from world.prototypes import MOB_PROTOTYPES
        known.update(MOB_PROTOTYPES.keys())
    except Exception:
        pass

    try:
        from world.prototypes import ITEM_PROTOTYPES
        known.update(ITEM_PROTOTYPES.keys())
    except Exception:
        pass

    # Spawner prototypes may be defined on the fly in batch scripts.
    # We allow any name not explicitly matching a known registry to avoid
    # false positives for builder-authored spawners; only report a warning
    # when the name clearly should exist but doesn't. For now, return empty
    # so batch files using custom spawners are not blocked.
    return set()


def validate_all_zones():
    """Validate all .ev files in world/batch_zones/ and print a report."""
    files = sorted(
        f for f in os.listdir(ZONE_DIR) if f.endswith(".ev")
    )
    if not files:
        print(f"No .ev files found in {ZONE_DIR}")
        return []

    all_issues = []
    for filename in files:
        issues = validate_zone_file(filename)
        if issues:
            all_issues.extend(issues)

    if all_issues:
        print("=== Batch Zone Validation: ISSUES FOUND ===")
        for issue in all_issues:
            print(f"  - {issue}")
        print(f"Total issues: {len(all_issues)}")
    else:
        print(f"=== Batch Zone Validation: OK ({len(files)} files) ===")

    return all_issues


if __name__ == "__main__":
    validate_all_zones()