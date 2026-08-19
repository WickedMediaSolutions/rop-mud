"""
Reboot Persistence & Startup Population Handler for 'rop'
=========================================================

Guarantees every room across the entire realm is fully populated with
mobs immediately upon server boot, regardless of how the server was
shut down (clean reload, hard crash, or cold start).

Architecture:
  - Hooks into ``server.conf.at_server_startstop.at_server_start()``.
  - Does NOT depend on per-room ``spawn_table`` attributes — uses the
    authoritative mob pools from ``world.realm_population`` and zone
    configuration from ``world.builder_phase1`` to derive what should
    be in each room.
  - Cleans orphaned/stale mob references before spawning.
  - Re-attaches AI tickers to every alive mob.
  - Restarts the global realm respawn script (``RealmRespawnScript``).
  - Prints a clean, itemized summary to the server log so admins can
    verify everything initialized before players log in.

Integration:
    In ``server/conf/at_server_startstop.py``::

        def at_server_start():
            from world.reboot_persistence import handle_server_boot
            handle_server_boot()

Usage (manual, from evennia shell):
    import world.reboot_persistence as rboot
    rboot.handle_server_boot()
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from evennia.utils import logger


# ---------------------------------------------------------------------------
# Public API — called from at_server_start
# ---------------------------------------------------------------------------

def handle_server_boot() -> Dict[str, Any]:
    """
    Master entry point for reboot-persistence population.

    Execution order:
      1. Clean up orphaned/stale mob references.
      2. Sweep every room in the realm, spawning missing mobs.
      3. Re-attach AI tickers to all alive mobs.
      4. Restart the global realm respawn script.
      5. Print a verification summary.

    Returns a stats dict suitable for logging or inspection.
    """
    t0 = time.time()

    # 1. Cleanup orphaned mobs and stale boss cooldown entries.
    cleanup_stats = _cleanup_stale_entities()

    # 2. Full realm population sweep.
    sweep_stats = _sweep_realm_population()

    # 3. Re-attach AI tickers.
    ticker_stats = _restart_all_mob_tickers()

    # 4. Ensure global respawn script is running.
    spawner_ok = _ensure_realm_spawner_running()

    # 5. Print verification summary.
    elapsed = time.time() - t0
    _print_boot_summary(cleanup_stats, sweep_stats, ticker_stats,
                        spawner_ok, elapsed)

    return {
        "cleanup": cleanup_stats,
        "sweep": sweep_stats,
        "tickers": ticker_stats,
        "spawner_running": spawner_ok,
        "elapsed_sec": round(elapsed, 2),
    }


# ---------------------------------------------------------------------------
# 1. Stale entity cleanup
# ---------------------------------------------------------------------------

def _cleanup_stale_entities() -> Dict[str, int]:
    """
    Remove orphaned mobs and stale references left over from hard crashes
    or unclean shutdowns.

    Actions:
      - Delete mob objects residing at ``None`` location with HP <= 0
        (these are dead mobs that failed to properly respawn or were
        orphaned during an unclean shutdown).
      - Clean boss cooldown timestamps for bosses that no longer exist
        (the boss was deleted but the timestamp dict persisted).
      - Remove any dead (HP=0) mobs still lingering in valid rooms
        (shouldn't happen, but defensive).

    Returns a stats dict.
    """
    stats = {
        "deleted_limbo_mobs": 0,
        "deleted_dead_in_room": 0,
        "cleaned_boss_cooldowns": 0,
        "mobs_checked": 0,
    }

    try:
        from evennia.objects.models import ObjectDB
    except Exception:
        return stats

    # Find all mob objects in the database.
    try:
        all_mobs = ObjectDB.objects.filter(
            db_typeclass_path__endswith="Mob"
        )
    except Exception:
        # Fallback: filter by tag.
        try:
            all_mobs = ObjectDB.objects.filter(
                db_tags__db_key="realm_mob",
                db_tags__db_category="spawn",
            )
        except Exception:
            return stats

    valid_boss_ids: Set[str] = set()
    try:
        import world.boss_registry as boss_registry
        valid_boss_ids = set(boss_registry.BOSS_REGISTRY.keys())
    except Exception:
        pass

    for mob in all_mobs:
        stats["mobs_checked"] += 1
        try:
            hp = mob.attributes.get("hp", 0)
            location = mob.location

            if location is None and hp <= 0:
                # Orphaned dead mob in limbo — delete it.
                try:
                    mob.delete()
                    stats["deleted_limbo_mobs"] += 1
                except Exception:
                    pass
            elif location is not None and hp <= 0:
                # Dead mob still in a room — defensive cleanup.
                try:
                    mob.delete()
                    stats["deleted_dead_in_room"] += 1
                except Exception:
                    pass
        except Exception:
            continue

    # Clean stale boss cooldown entries on rooms.
    try:
        rooms = ObjectDB.objects.filter(
            db_typeclass_path__endswith="Room"
        )
        for room in rooms:
            try:
                cooldowns = room.attributes.get(
                    "boss_respawn_timestamps", default={}
                )
                if not cooldowns:
                    continue
                cleaned = {}
                for boss_id, ts in cooldowns.items():
                    if boss_id in valid_boss_ids:
                        cleaned[boss_id] = ts
                    else:
                        stats["cleaned_boss_cooldowns"] += 1
                if len(cleaned) != len(cooldowns):
                    room.attributes.add("boss_respawn_timestamps", cleaned)
            except Exception:
                continue
    except Exception:
        pass

    return stats


# ---------------------------------------------------------------------------
# 2. Full realm population sweep
# ---------------------------------------------------------------------------

def _sweep_realm_population() -> Dict[str, Any]:
    """
    Iterate every room in the database.  For each room that has a valid
    ``zone_tag`` and ``max_mobs`` attribute (set by the realm population
    pipeline), count alive mobs and spawn replacements up to the cap.

    Uses the authoritative mob pools from ``world.realm_population`` to
    generate faction-appropriate, level-appropriate mobs — exactly the
    same pools used by ``populate_zone()``.

    Rooms that are safe zones (town hubs, faction cities) are skipped
    for combat-mob spawning.

    Returns a stats dict with per-zone breakdown.
    """
    stats: Dict[str, Any] = {
        "rooms_checked": 0,
        "rooms_populated": 0,
        "rooms_skipped_safe": 0,
        "rooms_no_zone": 0,
        "mobs_spawned": 0,
        "zones_touched": set(),
        "per_zone": {},
    }

    try:
        from evennia.objects.models import ObjectDB
    except Exception:
        return stats

    try:
        import world.realm_population as rp
        import world.builder_phase1 as b1
    except Exception:
        return stats

    # Build a zone_key -> (level_min, level_max, faction) lookup.
    zone_config: Dict[str, Tuple[int, int, str]] = {}
    for zkey, zdata in b1.ALL_ZONES.items():
        lo, hi = zdata.get("level_range", (1, 5))
        faction = rp.faction_for_zone(zkey)
        zone_config[zkey] = (lo, hi, faction)

    try:
        rooms = ObjectDB.objects.filter(
            db_typeclass_path__endswith="Room"
        )
    except Exception:
        return stats

    for room in rooms:
        stats["rooms_checked"] += 1

        try:
            zone_tag = room.attributes.get("zone_tag", default=None)
        except Exception:
            continue

        if zone_tag is None:
            stats["rooms_no_zone"] += 1
            continue

        # Skip safe zones for combat mob spawning.
        try:
            if room.attributes.get("safe_zone", False):
                stats["rooms_skipped_safe"] += 1
                continue
        except Exception:
            pass

        # Get the room's max_mobs cap.
        try:
            max_mobs = room.attributes.get("max_mobs", default=None)
        except Exception:
            max_mobs = None

        if max_mobs is None:
            # Derive from zone config if possible.
            cfg = zone_config.get(zone_tag)
            if cfg:
                lo, hi = cfg[0], cfg[1]
                _, hi_range = rp.mobs_per_room(lo, hi)
                max_mobs = hi_range
            else:
                max_mobs = 3  # Sensible default.

        # Count alive mobs already in the room.
        current_mobs = _count_alive_realm_mobs(room)

        if current_mobs >= max_mobs:
            continue  # Room is at or above cap.

        # Determine mob pool for this zone.
        cfg = zone_config.get(zone_tag)
        if cfg is None:
            # Unknown zone — skip.
            continue

        lo, hi, faction = cfg
        pool = rp.mob_pool_for_zone(zone_tag, lo, hi)
        if not pool:
            continue

        # Compute target: random within the danger band's range.
        min_per_room, _ = rp.mobs_per_room(lo, hi)
        target = random.randint(min_per_room, max_mobs)
        needed = max(0, target - current_mobs)

        # Spawn mobs.
        spawned_here = 0
        for _ in range(needed):
            spec = random.choice(pool)
            mob_level = max(lo, min(hi, spec["level"]))
            # Safe zones already skipped above, but keep the safe-zone
            # passive-mob rule for the starter danger band.
            danger = rp.danger_for_range(lo, hi)
            if danger == "safe":
                spec_aggro = False
            else:
                spec_aggro = spec.get("aggro", False)

            mob = rp.create_realm_mob(
                room,
                spec["name"],
                faction,
                mob_level,
                spec_aggro,
                damage_type=spec.get("damage_type", "slash"),
                home=room,
            )
            if mob:
                spawned_here += 1

        if spawned_here > 0:
            stats["mobs_spawned"] += spawned_here
            stats["rooms_populated"] += 1
            stats["zones_touched"].add(zone_tag)

            # Per-zone accounting.
            if zone_tag not in stats["per_zone"]:
                stats["per_zone"][zone_tag] = {
                    "rooms": 0,
                    "spawned": 0,
                }
            stats["per_zone"][zone_tag]["rooms"] += 1
            stats["per_zone"][zone_tag]["spawned"] += spawned_here

    # Convert set to count for JSON safety.
    zones_list = sorted(stats["zones_touched"])
    stats["zones_touched"] = len(zones_list)
    stats["zone_names"] = zones_list

    return stats


def _count_alive_realm_mobs(room: Any) -> int:
    """Count alive realm mobs currently in a room."""
    count = 0
    try:
        for obj in room.contents:
            if not hasattr(obj, "attributes"):
                continue
            if not obj.attributes.get("is_mob", False):
                continue
            hp = obj.attributes.get("hp", 0)
            if hp > 0:
                count += 1
    except Exception:
        pass
    return count


# ---------------------------------------------------------------------------
# 3. AI ticker restart
# ---------------------------------------------------------------------------

def _restart_all_mob_tickers() -> Dict[str, int]:
    """
    Iterate every alive mob in the database and ensure its AI ticker
    (MobAIScript) is running.

    After a server reboot, Evennia re-loads all objects from the database
    and calls ``at_init()`` on each, which normally starts the AI ticker.
    However, this is a belt-and-suspenders sweep to catch any mob whose
    ``at_init`` may have been skipped or whose script was orphaned.

    Returns a stats dict.
    """
    stats = {
        "mobs_checked": 0,
        "tickers_started": 0,
        "tickers_already_running": 0,
        "dead_skipped": 0,
    }

    try:
        from evennia.objects.models import ObjectDB
    except Exception:
        return stats

    try:
        all_mobs = ObjectDB.objects.filter(
            db_typeclass_path__endswith="Mob"
        )
    except Exception:
        try:
            all_mobs = ObjectDB.objects.filter(
                db_tags__db_key="realm_mob",
                db_tags__db_category="spawn",
            )
        except Exception:
            return stats

    for mob in all_mobs:
        stats["mobs_checked"] += 1
        try:
            hp = mob.attributes.get("hp", 0)
            if hp <= 0:
                stats["dead_skipped"] += 1
                continue

            # Check if ticker already exists.
            existing = mob.scripts.get("mob_ai_ticker") if hasattr(mob, "scripts") else None
            if existing:
                stats["tickers_already_running"] += 1
                continue

            # Start the ticker.
            if hasattr(mob, "_start_ai_ticker"):
                mob._start_ai_ticker()
                stats["tickers_started"] += 1
        except Exception:
            continue

    return stats


# ---------------------------------------------------------------------------
# 4. Global respawn script
# ---------------------------------------------------------------------------

def _ensure_realm_spawner_running() -> bool:
    """
    Ensure the global RealmRespawnScript is running.

    Returns True if the spawner is active (or was successfully started).
    """
    try:
        from world.realm_spawner import start_realm_spawner, get_spawner_status
        status = get_spawner_status()
        if status.get("running", False):
            return True
        return start_realm_spawner()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 5. Boot summary printer
# ---------------------------------------------------------------------------

def _print_boot_summary(
    cleanup_stats: Dict[str, int],
    sweep_stats: Dict[str, Any],
    ticker_stats: Dict[str, int],
    spawner_ok: bool,
    elapsed: float,
) -> None:
    """
    Print a clean, itemized summary to the server log during boot.

    Format:
        ============================================================
        Realm Population Boot Report
        ============================================================
        Cleanup:
          - Deleted X orphaned limbo mobs
          - Deleted Y dead-in-room mobs
          - Cleaned Z stale boss cooldowns
        Population Sweep:
          - Checked X rooms total
          - Populated Y rooms across Z zones
          - Spawned W missing mobs
          - Skipped S safe-zone rooms, N no-zone rooms
        Ticker Restart:
          - Checked X mobs
          - Started Y missing tickers (Z already running)
        Global Spawner: RUNNING / NOT RUNNING
        Completed in X.XX seconds.
        ============================================================
    """
    lines = []
    lines.append("=" * 60)
    lines.append("  Realm Population Boot Report")
    lines.append("=" * 60)

    # Cleanup section.
    lines.append("  Cleanup:")
    lines.append(
        f"    - Deleted {cleanup_stats.get('deleted_limbo_mobs', 0)} "
        f"orphaned limbo mobs"
    )
    lines.append(
        f"    - Deleted {cleanup_stats.get('deleted_dead_in_room', 0)} "
        f"dead-in-room mobs"
    )
    lines.append(
        f"    - Cleaned {cleanup_stats.get('cleaned_boss_cooldowns', 0)} "
        f"stale boss cooldowns"
    )

    # Sweep section.
    zones_touched = sweep_stats.get("zones_touched", 0)
    lines.append("  Population Sweep:")
    lines.append(
        f"    - Checked {sweep_stats.get('rooms_checked', 0)} rooms total"
    )
    lines.append(
        f"    - Populated {sweep_stats.get('rooms_populated', 0)} rooms "
        f"across {zones_touched} zones"
    )
    lines.append(
        f"    - Spawned {sweep_stats.get('mobs_spawned', 0)} missing mobs"
    )
    lines.append(
        f"    - Skipped {sweep_stats.get('rooms_skipped_safe', 0)} safe-zone "
        f"rooms, {sweep_stats.get('rooms_no_zone', 0)} no-zone rooms"
    )

    # Ticker section.
    lines.append("  Ticker Restart:")
    lines.append(
        f"    - Checked {ticker_stats.get('mobs_checked', 0)} mobs"
    )
    lines.append(
        f"    - Started {ticker_stats.get('tickers_started', 0)} missing "
        f"tickers ({ticker_stats.get('tickers_already_running', 0)} "
        f"already running)"
    )

    # Spawner section.
    spawner_status = "RUNNING" if spawner_ok else "NOT RUNNING"
    lines.append(f"  Global Spawner: {spawner_status}")

    lines.append(f"  Completed in {elapsed:.2f} seconds.")
    lines.append("=" * 60)

    summary = "\n".join(lines)
    logger.log_info(summary)

    # Also print to stdout so it appears in the terminal during boot.
    print(summary)


# ---------------------------------------------------------------------------
# Convenience: individual operations for manual use
# ---------------------------------------------------------------------------

def cleanup_orphaned_mobs() -> Dict[str, int]:
    """Run only the stale-entity cleanup phase."""
    return _cleanup_stale_entities()


def sweep_population() -> Dict[str, Any]:
    """Run only the realm population sweep phase."""
    return _sweep_realm_population()


def restart_tickers() -> Dict[str, int]:
    """Run only the AI ticker restart phase."""
    return _restart_all_mob_tickers()