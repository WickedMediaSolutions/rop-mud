"""
Realm-Wide Room Title Sanitization for 'rop'
=============================================

A database migration utility that sanitizes every room title across the
entire realm.  Strips out immersion-breaking meta-development tags,
parenthetical level notes, and tracking numbers.

Examples of transformations:
  "Brimstone Courtyard (Starter 1-10) - Location 2"
    → "Brimstone Courtyard"

  "Rolling Plains of Aethelgard (73,16)"
    → "Rolling Plains of Aethelgard"

  "Emerald Forest (Tier 2, 6-15)"
    → "Emerald Forest"

All zone bounds and tracking data are stored safely in room attributes
(``zone_level_min``, ``zone_level_max``, ``zone_tier``, ``zone_tag``),
never in public titles.

Provides:
  - sanitize_room_title() — clean a single room name string.
  - sanitize_all_rooms()   — walk every room in the DB and sanitize.
  - extract_zone_metadata() — parse zone info from a dirty title and
    store it as attributes.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

# strip_ansi is imported lazily in functions that need it to avoid
# import errors when Evennia isn't fully bootstrapped.
_STRIP_ANSI = None

def _get_strip_ansi():
    global _STRIP_ANSI
    if _STRIP_ANSI is None:
        try:
            from evennia.utils.ansi import strip_ansi as _sa
            _STRIP_ANSI = _sa
        except Exception:
            # Fallback to no-op identity when Evennia isn't bootstrapped.
            _STRIP_ANSI = lambda s: s
    return _STRIP_ANSI

# ---------------------------------------------------------------------------
# Regex patterns for meta-development cruft
# ---------------------------------------------------------------------------

# Parenthetical level notes: "(Starter 1-10)", "(Tier 2, 6-15)", "(Levels 1-5)"
_PAREN_LEVEL_RE = re.compile(
    r"\s*\((?:\s*(?:Starter|Tier|Levels?|Lvl|Zone)\s*[,\d\s\-]+)\)",
    re.IGNORECASE,
)

# Trailing coordinate numbers: "(73,16)", "(5, 10)"
_COORD_SUFFIX_RE = re.compile(r"\s*\(\d+,\s*\d+\)$")

# Trailing " - Location N" or " - Room N" or " - Area N"
_LOCATION_SUFFIX_RE = re.compile(
    r"\s*-\s*(?:Location|Room|Area|Spawn|Node)\s*\d+\s*$",
    re.IGNORECASE,
)

# Trailing " [N]" or " [Tier N]" or " [Zone N]"
_BRACKET_SUFFIX_RE = re.compile(
    r"\s*\[(?:\s*(?:Tier|Zone|Level|Lvl)\s*\d+)\]\s*$",
    re.IGNORECASE,
)

# Any remaining parenthetical that looks like metadata: "(1-5)", "(safe)", etc.
_GENERIC_META_PAREN_RE = re.compile(
    r"\s*\((?:safe|caution|danger|deadly|\d+\s*[-–]\s*\d+)\)\s*$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Zone metadata extraction from dirty titles
# ---------------------------------------------------------------------------

def extract_zone_metadata(title: str) -> Dict[str, Any]:
    """
    Parse zone metadata from a dirty room title and return it as a dict.

    Detects:
      - Level ranges: "(1-5)", "(Starter 1-10)", "(Tier 2, 6-15)"
      - Danger labels: "(safe)", "(caution)", "(danger)", "(deadly)"
      - Coordinates: "(73,16)"
      - Location numbers: "- Location 2"

    Returns a dict with keys that can be stored as room attributes.
    """
    metadata: Dict[str, Any] = {}
    _strip = _get_strip_ansi()
    clean = _strip(title)

    # Level range: "(1-5)", "(1 - 5)", "(Starter 1-10)", "(Tier 2, 6-15)"
    level_match = re.search(
        r"\((?:\s*(?:Starter|Tier|Levels?|Lvl|Zone)\s*[,\d\s]*)?(\d+)\s*[-–]\s*(\d+)\)",
        clean,
        re.IGNORECASE,
    )
    if level_match:
        lmin = int(level_match.group(1))
        lmax = int(level_match.group(2))
        metadata["zone_level_min"] = min(lmin, lmax)
        metadata["zone_level_max"] = max(lmin, lmax)

    # Tier number: "(Tier 2, ...)" or "[Tier 3]"
    tier_match = re.search(r"(?:Tier|Zone)\s*(\d+)", clean, re.IGNORECASE)
    if tier_match:
        metadata["zone_tier"] = int(tier_match.group(1))

    # Danger label
    danger_match = re.search(
        r"\((safe|caution|danger|deadly)\)",
        clean,
        re.IGNORECASE,
    )
    if danger_match:
        metadata["zone_danger"] = danger_match.group(1).lower()

    # Coordinates
    coord_match = re.search(r"\((\d+),\s*(\d+)\)", clean)
    if coord_match:
        metadata["coord_x"] = int(coord_match.group(1))
        metadata["coord_y"] = int(coord_match.group(2))

    # Location number
    loc_match = re.search(
        r"-\s*(?:Location|Room|Area|Spawn|Node)\s*(\d+)",
        clean,
        re.IGNORECASE,
    )
    if loc_match:
        metadata["location_number"] = int(loc_match.group(1))

    return metadata


def sanitize_room_title(title: str) -> str:
    """
    Strip all meta-development cruft from a room title.

    Returns a clean, atmospheric room name suitable for public display.
    """
    clean = _get_strip_ansi()(title).strip()

    # Apply each stripping pattern in order.
    clean = _PAREN_LEVEL_RE.sub("", clean)
    clean = _COORD_SUFFIX_RE.sub("", clean)
    clean = _LOCATION_SUFFIX_RE.sub("", clean)
    clean = _BRACKET_SUFFIX_RE.sub("", clean)
    clean = _GENERIC_META_PAREN_RE.sub("", clean)

    # Collapse multiple spaces and strip again.
    clean = re.sub(r"\s{2,}", " ", clean).strip()

    # If the title became empty after stripping, return a safe fallback.
    if not clean:
        return "A Featureless Room"

    return clean


def sanitize_room(room: Any, dry_run: bool = False) -> Dict[str, Any]:
    """
    Sanitize a single room's title and store zone metadata as attributes.

    Args:
        room: The room object to sanitize.
        dry_run: If True, don't actually modify the room — just report.

    Returns:
        Dict with keys: 'original', 'cleaned', 'changed', 'metadata', 'dry_run'.
    """
    original = room.db_key or room.key or ""
    cleaned = sanitize_room_title(original)
    metadata = extract_zone_metadata(original)

    changed = cleaned != original

    if not dry_run and changed:
        # Update the room's key to the clean title.
        try:
            room.db_key = cleaned
            # Also store zone metadata as attributes.
            for key, value in metadata.items():
                room.attributes.add(key, value)
        except Exception:
            pass

    return {
        "original": original,
        "cleaned": cleaned,
        "changed": changed,
        "metadata": metadata,
        "dry_run": dry_run,
    }


def sanitize_all_rooms(dry_run: bool = False) -> Dict[str, Any]:
    """
    Walk every room in the database and sanitize its title.

    Args:
        dry_run: If True, only report what would change without modifying.

    Returns:
        Summary dict:
          {
            "total_rooms": int,
            "changed": int,
            "unchanged": int,
            "errors": int,
            "dry_run": bool,
            "details": list of per-room reports (only for changed rooms),
          }
    """
    summary = {
        "total_rooms": 0,
        "changed": 0,
        "unchanged": 0,
        "errors": 0,
        "dry_run": dry_run,
        "details": [],
    }

    try:
        from evennia.objects.models import ObjectDB
        rooms = ObjectDB.objects.filter(db_typeclass_path__endswith="Room")
    except Exception:
        return summary

    for room in rooms:
        summary["total_rooms"] += 1
        try:
            report = sanitize_room(room, dry_run=dry_run)
            if report["changed"]:
                summary["changed"] += 1
                summary["details"].append(report)
            else:
                summary["unchanged"] += 1
        except Exception:
            summary["errors"] += 1

    return summary


def format_sanitization_report(summary: Dict[str, Any]) -> str:
    """
    Format a human-readable report from sanitize_all_rooms() output.
    """
    lines = []
    lines.append("|Y" + "=" * 60 + "|n")
    lines.append("|cRoom Title Sanitization Report|n")
    lines.append("|Y" + "=" * 60 + "|n")
    lines.append("")

    mode = "|yDRY RUN|n (no changes made)" if summary["dry_run"] else "|gLIVE RUN|n (titles updated)"
    lines.append(f"  Mode:       {mode}")
    lines.append(f"  Total rooms:  {summary['total_rooms']}")
    lines.append(f"  Changed:      |g{summary['changed']}|n")
    lines.append(f"  Unchanged:    {summary['unchanged']}")
    if summary["errors"]:
        lines.append(f"  Errors:       |r{summary['errors']}|n")
    lines.append("")

    details = summary.get("details", [])
    if details:
        lines.append("|wChanged Titles:|n")
        lines.append("|Y" + "-" * 60 + "|n")
        for d in details[:50]:  # Cap at 50 to avoid flooding
            lines.append(f"  |rBEFORE:|n {d['original']}")
            lines.append(f"  |gAFTER: |n {d['cleaned']}")
            meta = d.get("metadata", {})
            if meta:
                meta_str = ", ".join(f"{k}={v}" for k, v in sorted(meta.items()))
                lines.append(f"  |cMETA:  |n {meta_str}")
            lines.append("")
        if len(details) > 50:
            lines.append(f"  ... and {len(details) - 50} more changes.")
        lines.append("")

    lines.append("|Y" + "=" * 60 + "|n")
    return "\n".join(lines)