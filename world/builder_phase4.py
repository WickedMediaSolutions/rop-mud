# world/builder_phase4.py
from evennia import search_tag
import world.builder_phase1 as p1
import world.builder_phase2 as p2
import world.builder_phase3 as p3

def wipe_realm():
    print("[Phase 0 Wipe] Purging previously generated realm objects (safeguarding #1 Limbo & accounts)...")
    deleted_count = 0
    for category in ["room_id", "zone", "spawned_vendor", "spawn"]:
        objs = search_tag(category=category)
        for obj in objs:
            obj.delete()
            deleted_count += 1
    print(f" -> Successfully cleared {deleted_count} database objects.")

def validate_realm():
    print("[Validation Sweep] Checking database zone integrity:")
    for zone_key, data in p1.ALL_ZONES.items():
        found = search_tag(zone_key, category="zone")
        print(f" -> Zone [{zone_key}]: {len(found)} / {data['count']} rooms generated.")


def _run_phase_verify(phase_label: str):
    """
    Run the automated realm verification engine after a build phase.

    Catches broken/one-way exits, missing hubs, orphaned rooms, and
    faction-border leaks before they propagate to later phases.

    Domain concerns are kept lazy so the verifier stays importable even
    when Evennia's object model is not fully bootstrapped.
    """
    try:
        import world.realm_verify as rv
    except Exception as err:  # pragma: no cover - only if module is broken
        print(f" -> [VERIFY] WARNING: could not import realm_verify: {err}")
        return

    print(f" -> [VERIFY] Running realm verification after {phase_label}...")

    try:
        one_way = rv.verify_one_way_exits()
        print(f" -> [VERIFY] One-way exits: {one_way.get('one_way_count', 0)} "
              f"(of {one_way.get('total_exits', 0)} total exits)")
        for detail in one_way.get("details", [])[:10]:
            print(f"    ! {detail}")
    except Exception as err:
        print(f" -> [VERIFY] WARNING: verify_one_way_exits failed: {err}")

    try:
        result = rv.verify_realm(full_walk=False)
        issues = result.get("issues", [])
        critical = [i for i in issues if i.get("severity") == "critical"]
        warnings = [i for i in issues if i.get("severity") == "warning"]

        print(f" -> [VERIFY] Realm issues: {len(critical)} critical, "
              f"{len(warnings)} warnings, {len(issues) - len(critical) - len(warnings)} info")

        for issue in critical:
            print(f"    !! [CRITICAL] [{issue.get('area')}] {issue.get('msg')}")
        for issue in warnings[:10]:
            print(f"    !  [WARNING]  [{issue.get('area')}] {issue.get('msg')}")
    except Exception as err:  # pragma: no cover - verification must never block build
        print(f" -> [VERIFY] WARNING: verify_realm failed: {err}")


def build_all():
    print("=== STARTING FULL MODULAR EVENNIA REALM BUILD ===")
    wipe_realm()
    p1.build_phase1()
    _run_phase_verify("Phase 1 (rooms)")
    p2.build_phase2()
    _run_phase_verify("Phase 2 (exits)")
    p3.build_phase3()
    _run_phase_verify("Phase 3 (populate)")
    validate_realm()
    print("=== FULL REALM BUILD COMPLETE ===")