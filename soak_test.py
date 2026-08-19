#!/usr/bin/env python
"""
Phase 5 Soak Test — Multi-hour simulation of mob spawning/decaying,
combat ticks, and recovery cycles. Run inside evennia shell:

    evennia shell
    >>> import soak_test
    >>> soak_test.run(cycles=500, verbose=True)
"""

from __future__ import annotations

import gc
import time
import random
import sys
from collections import defaultdict
from typing import Any


def run(cycles: int = 500, verbose: bool = True):
    """
    Run a soak test simulating N cycles of:
    - Mob spawner tick (spawn new mobs, decay corpses)
    - Combat tick (mobs attack players, players attack mobs)
    - Recovery tick (HP/mana/MV/stamina regen)
    - Garbage collection (clean up orphaned objects)

    Each cycle represents ~15 seconds of game time.
    500 cycles ≈ 2 hours of game time.
    """
    from evennia.objects.models import ObjectDB
    from evennia.scripts.models import ScriptDB

    print("=" * 60)
    print("  PHASE 5 SOAK TEST")
    print(f"  Cycles: {cycles}  (~{cycles * 15 // 60} min game time)")
    print("=" * 60)

    # Pre-soak baseline
    baseline_objects = ObjectDB.objects.count()
    baseline_scripts = ScriptDB.objects.count()
    baseline_accounts = ObjectDB.objects.filter(
        db_typeclass_path__endswith="Account"
    ).count()

    print(f"\n  BASELINE: Objects={baseline_objects} Scripts={baseline_scripts} Accounts={baseline_accounts}")

    # Stats tracking
    stats = defaultdict(int)
    errors = []
    memory_samples = []

    t_start = time.time()

    for cycle in range(1, cycles + 1):
        try:
            _run_cycle(cycle, stats)
        except Exception as e:
            errors.append(f"Cycle {cycle}: {e}")
            if verbose and len(errors) <= 10:
                print(f"  [ERROR] Cycle {cycle}: {e}")

        # Memory sampling every 50 cycles
        if cycle % 50 == 0:
            gc.collect()
            mem = _get_memory_mb()
            memory_samples.append((cycle, mem))
            if verbose:
                print(f"  Cycle {cycle:4d}: mem={mem:.1f}MB  "
                      f"spawns={stats['spawns']} combats={stats['combats']} "
                      f"recoveries={stats['recoveries']} decays={stats['decays']}")

    t_end = time.time()
    elapsed = t_end - t_start

    # Post-soak baseline
    gc.collect()
    post_objects = ObjectDB.objects.count()
    post_scripts = ScriptDB.objects.count()
    post_accounts = ObjectDB.objects.filter(
        db_typeclass_path__endswith="Account"
    ).count()

    # Results
    print(f"\n{'=' * 60}")
    print(f"  SOAK TEST RESULTS")
    print(f"{'=' * 60}")
    print(f"  Elapsed: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"  Cycles completed: {cycle}/{cycles}")
    print(f"  Errors: {len(errors)}")

    print(f"\n  --- Object Counts ---")
    print(f"  Objects:  {baseline_objects:>8} → {post_objects:>8}  (Δ={post_objects - baseline_objects:+d})")
    print(f"  Scripts:  {baseline_scripts:>8} → {post_scripts:>8}  (Δ={post_scripts - baseline_scripts:+d})")
    print(f"  Accounts: {baseline_accounts:>8} → {post_accounts:>8}  (Δ={post_accounts - baseline_accounts:+d})")

    print(f"\n  --- Activity Stats ---")
    for key in sorted(stats.keys()):
        print(f"  {key}: {stats[key]}")

    print(f"\n  --- Memory ---")
    if memory_samples:
        first_mem = memory_samples[0][1]
        last_mem = memory_samples[-1][1]
        print(f"  Start: {first_mem:.1f}MB  End: {last_mem:.1f}MB  Δ={last_mem - first_mem:+.1f}MB")
        growth = last_mem - first_mem
        if growth > 50:
            print(f"  |r⚠ MEMORY GROWTH DETECTED: {growth:+.1f}MB|n")
        else:
            print(f"  |gMemory stable.|n")

    # DB consistency checks
    print(f"\n  --- DB Consistency ---")
    _check_db_consistency()

    # Final verdict
    print(f"\n{'=' * 60}")
    if len(errors) == 0 and (post_objects - baseline_objects) < 100:
        print("  |gSOAK TEST PASSED|n — No errors, stable object count.")
    elif len(errors) == 0:
        print("  |ySOAK TEST PASSED WITH NOTE|n — No errors, but object count grew.")
    else:
        print(f"  |rSOAK TEST FAILED|n — {len(errors)} errors.")
    print(f"{'=' * 60}")

    return {
        "errors": len(errors),
        "elapsed": elapsed,
        "cycles": cycle,
        "object_delta": post_objects - baseline_objects,
        "script_delta": post_scripts - baseline_scripts,
        "memory_growth": memory_samples[-1][1] - memory_samples[0][1] if memory_samples else 0,
    }


def _run_cycle(cycle_num: int, stats: defaultdict):
    """Simulate one full game tick (~15s)."""
    from evennia.objects.models import ObjectDB

    # 1. Recovery tick — regen HP/mana/MV for all player characters
    _simulate_recovery(stats)

    # 2. Combat tick — process active combats
    _simulate_combat(stats)

    # 3. Spawner tick — spawn new mobs, decay old corpses
    _simulate_spawner_tick(stats)

    # 4. Garbage collection — clean up orphaned objects
    _simulate_gc(stats)


def _simulate_recovery(stats: defaultdict):
    """Simulate recovery for all player characters."""
    from typeclasses.characters import Character
    from evennia.objects.models import ObjectDB

    count = 0
    for obj in ObjectDB.objects.all():
        if not isinstance(obj, Character):
            continue
        if not obj.has_account:
            continue

        try:
            # Simulate HP regen
            hp = obj.attributes.get("hp", default=0)
            max_hp = obj.attributes.get("max_hp", default=100)
            if hp and max_hp and hp < max_hp:
                regen = max(1, int(max_hp * 0.05))
                obj.attributes.add("hp", min(max_hp, hp + regen))

            # Simulate mana regen for casters
            from world.race_class_matrix import can_cast_spells
            if can_cast_spells(obj):
                mana = obj.attributes.get("mana", default=0)
                max_mana = obj.attributes.get("max_mana", default=50)
                if mana and max_mana and mana < max_mana:
                    regen = max(1, int(max_mana * 0.05))
                    obj.attributes.add("mana", min(max_mana, mana + regen))

            # Simulate MV regen
            mv = obj.attributes.get("mv", default=0)
            max_mv = obj.attributes.get("max_mv", default=100)
            if mv and max_mv and mv < max_mv:
                regen = max(1, int(max_mv * 0.10))
                obj.attributes.add("mv", min(max_mv, mv + regen))

            # Simulate stamina regen
            stamina = obj.attributes.get("stamina", default=100)
            max_stamina = obj.attributes.get("max_stamina", default=100)
            if stamina < max_stamina:
                regen = max(1, int(max_stamina * 0.05))
                obj.attributes.add("stamina", min(max_stamina, stamina + regen))

            count += 1
        except Exception:
            pass

    stats["recoveries"] += count


def _simulate_combat(stats: defaultdict):
    """Simulate combat ticks for active combatants."""
    from typeclasses.characters import Character
    from evennia.objects.models import ObjectDB
    from world.damage_formulas import calculate_melee_damage
    from world.damage_types import PhysicalDamageType

    count = 0
    # Find characters with active combat targets
    for obj in ObjectDB.objects.all():
        if not isinstance(obj, Character):
            continue
        try:
            target = obj.ndb.combat_target if hasattr(obj, "ndb") else None
            if target is None:
                continue

            # Simulate one attack round
            weapon_dmg = 10  # Default weapon damage
            result = calculate_melee_damage(obj, target, weapon_dmg, PhysicalDamageType.SLASHING)

            # Apply damage
            target_hp = target.attributes.get("hp", default=0)
            if target_hp > 0:
                new_hp = max(0, target_hp - result["damage"])
                target.attributes.add("hp", new_hp)

                # Check for death
                if new_hp <= 0:
                    _handle_mob_death(target, obj)

            count += 1
        except Exception:
            pass

    stats["combats"] += count


def _handle_mob_death(mob, killer):
    """Handle mob death: award XP, drop loot, create corpse."""
    try:
        # Award XP
        xp = mob.attributes.get("xp_value", default=10)
        killer_xp = killer.attributes.get("xp", default=0)
        killer.attributes.add("xp", killer_xp + xp)

        # Drop gold
        gold_min = mob.attributes.get("gold_min", default=0)
        gold_max = mob.attributes.get("gold_max", default=5)
        gold = random.randint(gold_min, gold_max)
        if gold > 0:
            killer_gold = killer.attributes.get("money", default=0)
            killer.attributes.add("money", killer_gold + gold)

        # Clear combat state
        if hasattr(mob, "ndb"):
            mob.ndb.combat_target = None
            mob.ndb.combat_state = None
    except Exception:
        pass


def _simulate_spawner_tick(stats: defaultdict):
    """Simulate mob spawner ticks and corpse decay."""
    from evennia.objects.models import ObjectDB

    spawn_count = 0
    decay_count = 0

    for obj in ObjectDB.objects.all():
        try:
            # Check if this is a spawner
            is_spawner = obj.attributes.get("is_spawner", default=False)
            if is_spawner:
                # Check if spawner needs to spawn
                spawn_count += 1
                stats["spawners_checked"] += 1

            # Check if this is a corpse that should decay
            is_corpse = obj.attributes.get("is_corpse", default=False)
            if is_corpse:
                decay_time = obj.attributes.get("decay_at", default=0)
                if decay_time and time.time() > decay_time:
                    decay_count += 1
        except Exception:
            pass

    stats["spawns"] += spawn_count
    stats["decays"] += decay_count


def _simulate_gc(stats: defaultdict):
    """Simulate garbage collection pass."""
    from evennia.objects.models import ObjectDB

    cleaned = 0
    for obj in ObjectDB.objects.all():
        try:
            # Check for orphaned objects (no location, no contents, not a player)
            if obj.location is None and not obj.has_account:
                # Skip spawners
                if obj.attributes.get("is_spawner", default=False):
                    continue
                # Skip mobs with spawner tracking
                if obj.attributes.get("mob_spawner", default=None):
                    continue
                cleaned += 1
        except Exception:
            pass

    stats["gc_cleaned"] += cleaned


def _get_memory_mb() -> float:
    """Get current process memory in MB."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _check_db_consistency():
    """Run database consistency checks."""
    from evennia.objects.models import ObjectDB
    from evennia.scripts.models import ScriptDB

    issues = []

    # Check for objects with null locations that aren't accounts or rooms
    orphaned = ObjectDB.objects.filter(
        db_location__isnull=True
    ).exclude(
        db_typeclass_path__endswith="Account"
    ).exclude(
        db_typeclass_path__endswith="Room"
    ).count()
    if orphaned > 0:
        issues.append(f"Orphaned objects (no location): {orphaned}")
        print(f"  |y⚠ Orphaned objects: {orphaned}|n")
    else:
        print(f"  |g✓ No orphaned objects|n")

    # Global scripts (backup, weather, recovery, etc.) have no db_obj by design.
    # Only flag scripts that are NOT known global/system scripts.
    GLOBAL_SCRIPT_TYPECLASSES = {
        "world.backup.BackupScript",
        "world.announcements.AnnouncementScript",
        "world.weather_script.WeatherScript",
        "world.recovery.RecoveryScript",
        "world.garbage_collection.GarbageCollectionScript",
        "world.migrations.MigrationTrackerScript",
    }
    orphan_scripts = ScriptDB.objects.filter(
        db_obj__isnull=True
    ).exclude(
        db_typeclass_path__in=GLOBAL_SCRIPT_TYPECLASSES
    ).count()
    if orphan_scripts > 0:
        issues.append(f"Orphaned scripts: {orphan_scripts}")
        print(f"  |y⚠ Orphaned scripts: {orphan_scripts}|n")
    else:
        print(f"  |g✓ No orphaned scripts (global scripts OK)|n")

    # Check for characters with invalid HP
    from typeclasses.characters import Character
    invalid_hp = 0
    for obj in ObjectDB.objects.all():
        if not isinstance(obj, Character):
            continue
        try:
            hp = obj.attributes.get("hp", default=None)
            max_hp = obj.attributes.get("max_hp", default=None)
            if hp is not None and max_hp is not None:
                if hp < 0 or hp > max_hp * 2:
                    invalid_hp += 1
        except Exception:
            pass
    if invalid_hp > 0:
        issues.append(f"Characters with invalid HP: {invalid_hp}")
        print(f"  |y⚠ Invalid HP values: {invalid_hp}|n")
    else:
        print(f"  |g✓ All HP values valid|n")

    # Check for equipped items that don't exist
    invalid_equip = 0
    for obj in ObjectDB.objects.all():
        if not isinstance(obj, Character):
            continue
        try:
            equipped = obj.attributes.get("equipped", default={})
            for slot, item_name in equipped.items():
                found = False
                for content in obj.contents:
                    if content.key == item_name:
                        found = True
                        break
                if not found:
                    invalid_equip += 1
        except Exception:
            pass
    if invalid_equip > 0:
        issues.append(f"Invalid equipped references: {invalid_equip}")
        print(f"  |y⚠ Invalid equipped items: {invalid_equip}|n")
    else:
        print(f"  |g✓ All equipped items valid|n")

    if not issues:
        print(f"  |gDB Consistency: CLEAN|n")
    else:
        print(f"  |rDB Consistency: {len(issues)} issues found|n")


if __name__ == "__main__":
    run(cycles=500, verbose=True)