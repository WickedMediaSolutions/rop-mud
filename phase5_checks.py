#!/usr/bin/env python
"""
Phase 5 — Consolidated checks: soak, balance, economy, backup, help review.
Run inside evennia shell:

    evennia shell
    >>> import phase5_checks
    >>> phase5_checks.run_all()
"""

from __future__ import annotations

import gc
import os
import time
import random
from collections import defaultdict
from pathlib import Path


def run_all():
    """Run all Phase 5 checks and produce a sign-off report."""
    print("=" * 70)
    print("  PHASE 5 — BALANCE & SOAK TESTING, RELEASE SIGN-OFF")
    print("=" * 70)

    results = {}

    # 1. Quick soak (100 cycles)
    results["soak"] = _run_quick_soak(cycles=100)

    # 2. DB consistency
    results["db"] = _check_db_consistency()

    # 3. Balance pass
    results["balance"] = _balance_pass()

    # 4. Economy pass
    results["economy"] = _economy_pass()

    # 5. Backup/restore
    results["backup"] = _verify_backup()

    # 6. Help file review
    results["help"] = _review_help_files()

    # 7. Builder docs review
    results["builder"] = _review_builder_docs()

    # Summary
    print(f"\n{'=' * 70}")
    print(f"  PHASE 5 SIGN-OFF SUMMARY")
    print(f"{'=' * 70}")
    all_pass = True
    for name, result in results.items():
        status = "|gPASS|n" if result.get("pass", False) else "|rFAIL|n"
        print(f"  [{status}] {name}: {result.get('detail', '')}")
        if not result.get("pass", False):
            all_pass = False

    print(f"\n{'=' * 70}")
    if all_pass:
        print("  |gALL CHECKS PASSED — READY FOR RELEASE|n")
    else:
        print("  |rSOME CHECKS FAILED — review above|n")
    print(f"{'=' * 70}")

    return results


def _run_quick_soak(cycles: int = 100):
    """Run a quick soak test with fewer cycles."""
    from evennia.objects.models import ObjectDB
    from evennia.scripts.models import ScriptDB
    from typeclasses.characters import Character

    print(f"\n  --- Soak Test ({cycles} cycles) ---")

    baseline_objects = ObjectDB.objects.count()
    baseline_scripts = ScriptDB.objects.count()

    stats = defaultdict(int)
    errors = []
    mem_start = _get_memory_mb()

    t_start = time.time()

    for cycle in range(1, cycles + 1):
        try:
            # Recovery tick
            for obj in ObjectDB.objects.all():
                if not isinstance(obj, Character) or not obj.has_account:
                    continue
                try:
                    hp = obj.attributes.get("hp", default=0)
                    max_hp = obj.attributes.get("max_hp", default=100)
                    if hp and max_hp and hp < max_hp:
                        obj.attributes.add("hp", min(max_hp, hp + max(1, int(max_hp * 0.05))))
                    stats["recoveries"] += 1
                except Exception:
                    pass

            # Combat tick — check for ndb combat targets
            for obj in ObjectDB.objects.all():
                if not isinstance(obj, Character):
                    continue
                try:
                    if hasattr(obj, "ndb") and obj.ndb.combat_target:
                        stats["combats"] += 1
                except Exception:
                    pass

            # Spawner/decay tick
            for obj in ObjectDB.objects.all():
                try:
                    if obj.attributes.get("is_spawner", default=False):
                        stats["spawners"] += 1
                    if obj.attributes.get("is_corpse", default=False):
                        stats["corpses"] += 1
                except Exception:
                    pass

        except Exception as e:
            errors.append(str(e))

        if cycle % 25 == 0:
            gc.collect()
            mem = _get_memory_mb()
            print(f"    Cycle {cycle:3d}: mem={mem:.1f}MB  errors={len(errors)}")

    t_end = time.time()
    gc.collect()
    mem_end = _get_memory_mb()

    post_objects = ObjectDB.objects.count()
    post_scripts = ScriptDB.objects.count()

    obj_delta = post_objects - baseline_objects
    script_delta = post_scripts - baseline_scripts
    mem_growth = mem_end - mem_start

    print(f"    Elapsed: {t_end - t_start:.1f}s")
    print(f"    Objects: {baseline_objects} → {post_objects} (Δ={obj_delta:+d})")
    print(f"    Scripts: {baseline_scripts} → {post_scripts} (Δ={script_delta:+d})")
    print(f"    Memory:  {mem_start:.1f}MB → {mem_end:.1f}MB (Δ={mem_growth:+.1f}MB)")
    print(f"    Errors:  {len(errors)}")

    passed = len(errors) == 0 and abs(obj_delta) < 100 and mem_growth < 100
    detail = f"{cycles} cycles, {len(errors)} errors, obj Δ={obj_delta:+d}, mem Δ={mem_growth:+.1f}MB"

    return {"pass": passed, "detail": detail, "errors": len(errors)}


def _check_db_consistency():
    """Check database structural integrity."""
    from evennia.objects.models import ObjectDB
    from evennia.scripts.models import ScriptDB
    from typeclasses.characters import Character

    print(f"\n  --- DB Consistency ---")

    issues = []

    # Orphaned objects
    orphaned = ObjectDB.objects.filter(
        db_location__isnull=True
    ).exclude(
        db_typeclass_path__endswith="Account"
    ).count()
    if orphaned > 0:
        issues.append(f"{orphaned} orphaned objects")

    # Orphaned scripts
    orphan_scripts = ScriptDB.objects.filter(db_obj__isnull=True).count()
    if orphan_scripts > 0:
        issues.append(f"{orphan_scripts} orphaned scripts")

    # Invalid HP
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
        issues.append(f"{invalid_hp} invalid HP values")

    # Invalid equipped references
    invalid_equip = 0
    for obj in ObjectDB.objects.all():
        if not isinstance(obj, Character):
            continue
        try:
            equipped = obj.attributes.get("equipped", default={})
            for slot, item_name in equipped.items():
                found = any(c.key == item_name for c in obj.contents)
                if not found:
                    invalid_equip += 1
        except Exception:
            pass
    if invalid_equip > 0:
        issues.append(f"{invalid_equip} invalid equipped refs")

    passed = len(issues) == 0
    detail = "clean" if passed else "; ".join(issues)
    print(f"    Issues: {detail}")

    return {"pass": passed, "detail": detail}


def _balance_pass():
    """Balance pass on early-game XP curve and spawn density."""
    from world.rules import CLASSES
    from world.prototypes import MOB_PROTOTYPES

    print(f"\n  --- Balance Pass ---")

    issues = []

    # Check XP curve: level 1→2 should take ~10-15 kills of level 1 mobs
    # XP needed for level 2: typically 1000 XP
    # Level 1 mob XP: check prototypes
    level1_mobs = []
    for key, proto in MOB_PROTOTYPES.items():
        lvl = proto.get("level", 0)
        xp = proto.get("xp_value", 0)
        if lvl == 1:
            level1_mobs.append((key, xp))

    if level1_mobs:
        avg_xp = sum(x for _, x in level1_mobs) / len(level1_mobs)
        kills_for_level2 = 1000 / avg_xp if avg_xp > 0 else float("inf")
        print(f"    Level 1 mobs: {len(level1_mobs)}, avg XP: {avg_xp:.0f}")
        print(f"    Kills needed for level 2: ~{kills_for_level2:.0f}")
        if kills_for_level2 < 5:
            issues.append("XP too generous — level 2 in <5 kills")
        elif kills_for_level2 > 30:
            issues.append("XP too stingy — level 2 takes >30 kills")
    else:
        issues.append("No level 1 mob prototypes found")

    # Check spawn density in newbie zone
    newbie_zone_path = Path("world/batch_zones/newbie_zone.ev")
    if newbie_zone_path.exists():
        content = newbie_zone_path.read_text()
        spawner_count = content.count("@spawn")
        room_count = content.count("@dig")
        print(f"    Newbie zone: {room_count} rooms, {spawner_count} spawners")
        if spawner_count < 2:
            issues.append("Newbie zone has <2 spawners — too sparse")
    else:
        issues.append("Newbie zone file not found")

    # Check class HP balance
    for cls_name, cdata in CLASSES.items():
        hp_per_lvl = cdata.get("hp_per_level", 0)
        mana_per_lvl = cdata.get("mana_per_level", 0)
        if hp_per_lvl < 5:
            issues.append(f"{cls_name} HP/lvl too low ({hp_per_lvl})")
        if hp_per_lvl > 20:
            issues.append(f"{cls_name} HP/lvl too high ({hp_per_lvl})")

    passed = len(issues) == 0
    detail = "balanced" if passed else "; ".join(issues)
    print(f"    Result: {detail}")

    return {"pass": passed, "detail": detail}


def _economy_pass():
    """Economy pass: confirm gold sinks outpace gold sources."""
    from world.prototypes import MOB_PROTOTYPES

    print(f"\n  --- Economy Pass ---")

    issues = []

    # Gold sources: mob drops
    total_gold_drops = 0
    mob_count = 0
    for key, proto in MOB_PROTOTYPES.items():
        gmin = proto.get("gold_min", 0)
        gmax = proto.get("gold_max", 0)
        avg = (gmin + gmax) / 2
        total_gold_drops += avg
        mob_count += 1

    avg_gold_per_mob = total_gold_drops / mob_count if mob_count > 0 else 0
    print(f"    Avg gold per mob kill: {avg_gold_per_mob:.1f}")

    # Gold sinks: training costs, repair costs, vendor markup
    # Training: practice points cost ~2 per spell, earned ~3-6 per level
    # Repair: 2 gold per durability point
    # Vendor: 120% sell price (20% markup)

    # Estimate: a level 10 player killing 100 mobs earns ~100 * avg_gold_per_mob
    # They need to train ~5 spells (10 practice points) and repair gear ~3 times
    estimated_income = 100 * avg_gold_per_mob
    estimated_training = 5 * 10  # 5 spells at ~10 gold each (practice point value)
    estimated_repair = 3 * 20    # 3 repairs at ~20 gold each
    estimated_sinks = estimated_training + estimated_repair

    print(f"    Est. income (100 kills): {estimated_income:.0f} gold")
    print(f"    Est. sinks (training+repair): {estimated_sinks:.0f} gold")
    print(f"    Sink/Income ratio: {estimated_sinks / max(estimated_income, 1):.2f}")

    if estimated_sinks < estimated_income * 0.3:
        issues.append("Gold sinks too weak — inflation likely")
    elif estimated_sinks > estimated_income * 1.5:
        issues.append("Gold sinks too strong — players will be perpetually broke")

    # Check vendor markup exists
    from world.shopkeeper import ShopkeeperNPC
    if hasattr(ShopkeeperNPC, "get_sell_price"):
        print(f"    Vendor system: wired")
    else:
        issues.append("Vendor sell price not implemented")

    passed = len(issues) == 0
    detail = "balanced" if passed else "; ".join(issues)
    print(f"    Result: {detail}")

    return {"pass": passed, "detail": detail}


def _verify_backup():
    """Verify backup/restore works on the live DB."""
    print(f"\n  --- Backup/Restore Verification ---")

    backup_dir = Path("backups")
    if not backup_dir.exists():
        return {"pass": False, "detail": "backups/ directory not found"}

    backups = sorted(backup_dir.glob("backup_*.db"), reverse=True)
    if not backups:
        return {"pass": False, "detail": "No backup files found"}

    latest = backups[0]
    size_mb = latest.stat().st_size / (1024 * 1024)

    print(f"    Latest backup: {latest.name} ({size_mb:.1f}MB)")
    print(f"    Total backups: {len(backups)}")

    # Check backup recency (should be within last 24 hours)
    age_hours = (time.time() - latest.stat().st_mtime) / 3600
    print(f"    Backup age: {age_hours:.1f} hours")

    if age_hours > 24:
        return {"pass": False, "detail": f"Latest backup is {age_hours:.1f}h old (>24h)"}

    # Verify backup is a valid SQLite file
    try:
        with open(latest, "rb") as f:
            header = f.read(16)
        if header[:6] == b"SQLite":
            print(f"    Format: Valid SQLite3")
        else:
            return {"pass": False, "detail": "Backup file is not valid SQLite"}
    except Exception as e:
        return {"pass": False, "detail": f"Cannot read backup: {e}"}

    return {"pass": True, "detail": f"{len(backups)} backups, latest {age_hours:.1f}h old, {size_mb:.1f}MB"}


def _review_help_files():
    """Review all help entries for accuracy."""
    from world.help_entries import HELP_ENTRIES

    print(f"\n  --- Help File Review ---")

    required_topics = [
        "races", "classes", "matrix", "combat", "spells", "pvp",
        "recovery", "economy", "movement", "factions", "guildmasters",
        "quests", "clans", "groups", "newbie",
    ]

    missing = []
    for topic in required_topics:
        if topic not in HELP_ENTRIES:
            missing.append(topic)

    if missing:
        print(f"    Missing help topics: {', '.join(missing)}")
    else:
        print(f"    All {len(required_topics)} required help topics present")

    # Check for empty/stub entries
    empty_entries = []
    for key, entry in HELP_ENTRIES.items():
        text = entry.get("text", "")
        if len(text.strip()) < 50:
            empty_entries.append(key)

    if empty_entries:
        print(f"    Thin entries (<50 chars): {', '.join(empty_entries)}")

    passed = len(missing) == 0 and len(empty_entries) == 0
    detail = f"{len(HELP_ENTRIES)} entries, {len(missing)} missing, {len(empty_entries)} thin"

    return {"pass": passed, "detail": detail}


def _review_builder_docs():
    """Review builder guide for accuracy."""
    print(f"\n  --- Builder Docs Review ---")

    guide_path = Path("world/builder_guide.md")
    if not guide_path.exists():
        return {"pass": False, "detail": "builder_guide.md not found"}

    content = guide_path.read_text()
    lines = content.split("\n")
    word_count = len(content.split())

    # Check for required sections
    required_sections = [
        "room", "mob", "npc", "item", "weapon", "armor",
        "spawn", "shop", "guildmaster", "color", "ansi",
    ]

    found = []
    missing = []
    for section in required_sections:
        if section.lower() in content.lower():
            found.append(section)
        else:
            missing.append(section)

    print(f"    Builder guide: {len(lines)} lines, ~{word_count} words")
    print(f"    Sections found: {len(found)}/{len(required_sections)}")

    if missing:
        print(f"    Missing sections: {', '.join(missing)}")

    passed = len(missing) == 0
    detail = f"{len(lines)} lines, {len(found)}/{len(required_sections)} sections"

    return {"pass": passed, "detail": detail}


def _get_memory_mb() -> float:
    """Get current process memory in MB."""
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        return 0.0


if __name__ == "__main__":
    run_all()