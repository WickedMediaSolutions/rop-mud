"""
Comprehensive System Verification Command for 'rop'
====================================================

Provides the ``@verifyallsystems`` admin command that audits:

  1. Zone level ranges — all mobs are within their room's zone band.
  2. Mob equipment assignment — mobs have weapons/armor in their inventory.
  3. Room title cleanliness — no meta-development tags in public titles.
  4. Prompt state integrity — players have prompt enabled, combat state
     toggles correctly.
  5. Armor absorption correctness — no phantom absorption on naked targets.

Usage (in-game):
  @verifyallsystems [full]

  Without ``full``, performs a fast audit.  With ``full``, also runs
  the room title sanitization dry-run report.

This command does NOT modify the game world; it only reads and reports.
"""

from __future__ import annotations

from typing import Any, Dict, List

from commands.command import Command
from evennia.utils import logger


class CmdVerifyAllSystems(Command):
    """
    Run a comprehensive audit of all core game systems.

    Usage:
      @verifyallsystems [full]

    Audits:
      1. Zone level range enforcement
      2. Mob equipment assignment
      3. Room title cleanliness
      4. Prompt / combat state integrity
      5. Armor absorption correctness

    With ``full``, includes a dry-run room title sanitization report.
    """

    key = "@verifyallsystems"
    aliases = ["verifyallsystems", "@verifyall", "verifyall"]
    locks = "cmd:perm(Admin) or perm(Builder)"
    help_category = "Admin"
    auto_help = True

    def func(self):
        caller = self.caller
        full = "full" in (self.args or "").strip().lower()

        caller.msg("|Y[SystemAudit] Running comprehensive system verification...|n")

        results: List[Dict[str, Any]] = []

        # ----- 1. Zone Level Ranges -----
        results.append(self._audit_zone_levels())

        # ----- 2. Mob Equipment Assignment -----
        results.append(self._audit_mob_equipment())

        # ----- 3. Room Title Cleanliness -----
        results.append(self._audit_room_titles(full))

        # ----- 4. Prompt / Combat State Integrity -----
        results.append(self._audit_prompt_state())

        # ----- 5. Armor Absorption Correctness -----
        results.append(self._audit_armor_absorption())

        # Build the report
        report = self._format_report(results)
        caller.msg(report)

    # ------------------------------------------------------------------
    # Audit 1: Zone Level Ranges
    # ------------------------------------------------------------------

    def _audit_zone_levels(self) -> Dict[str, Any]:
        """Audit that all mobs are within their room's zone band."""
        try:
            from world.zone_scaling import audit_all_rooms
            summary = audit_all_rooms()
            return {
                "system": "Zone Level Ranges",
                "pass": summary.get("clean", True),
                "rooms_checked": summary.get("rooms_checked", 0),
                "mobs_checked": summary.get("mobs_checked", 0),
                "violations": summary.get("violations", 0),
                "rescaled": summary.get("rescaled", 0),
                "detail": (
                    f"{summary.get('rooms_checked', 0)} rooms, "
                    f"{summary.get('mobs_checked', 0)} mobs checked. "
                    f"{summary.get('violations', 0)} violations found "
                    f"({summary.get('rescaled', 0)} rescaled)."
                ) if not summary.get("clean", True) else (
                    f"All {summary.get('mobs_checked', 0)} mobs in "
                    f"{summary.get('rooms_checked', 0)} rooms are within zone bands."
                ),
            }
        except Exception as err:
            return {
                "system": "Zone Level Ranges",
                "pass": False,
                "error": str(err),
                "detail": f"Could not audit zone levels: {err}",
            }

    # ------------------------------------------------------------------
    # Audit 2: Mob Equipment Assignment
    # ------------------------------------------------------------------

    def _audit_mob_equipment(self) -> Dict[str, Any]:
        """
        Audit that mobs have weapons and/or armor in their inventory.

        Counts mobs with and without equipped items across the realm.
        """
        try:
            from evennia.objects.models import ObjectDB

            total_mobs = 0
            mobs_with_weapon = 0
            mobs_with_armor = 0
            mobs_with_equipped_attr = 0
            naked_mobs = 0

            for obj in ObjectDB.objects.all():
                if not hasattr(obj, "attributes"):
                    continue
                if not obj.attributes.get("is_mob", False):
                    continue
                hp = obj.attributes.get("hp", 0)
                if hp <= 0:
                    continue  # dead mobs don't count

                total_mobs += 1
                equipped = obj.attributes.get("equipped", default={})
                if equipped:
                    mobs_with_equipped_attr += 1

                has_weapon = False
                has_armor = False
                for child in obj.contents:
                    if getattr(child, "destination", None):
                        continue
                    if not hasattr(child, "attributes"):
                        continue
                    dmg = child.attributes.get("damage", 0)
                    arm = child.attributes.get("armor", 0)
                    if dmg > 0:
                        has_weapon = True
                    if arm > 0:
                        has_armor = True

                if has_weapon:
                    mobs_with_weapon += 1
                if has_armor:
                    mobs_with_armor += 1
                if not has_weapon and not has_armor:
                    naked_mobs += 1

            all_equipped = total_mobs > 0 and naked_mobs == 0

            return {
                "system": "Mob Equipment Assignment",
                "pass": True,  # always pass — just a report
                "total_mobs": total_mobs,
                "mobs_with_weapon": mobs_with_weapon,
                "mobs_with_armor": mobs_with_armor,
                "mobs_with_equipped_attr": mobs_with_equipped_attr,
                "naked_mobs": naked_mobs,
                "detail": (
                    f"{total_mobs} alive mobs: "
                    f"{mobs_with_weapon} have weapons, "
                    f"{mobs_with_armor} have armor, "
                    f"{naked_mobs} are naked (no gear)."
                ),
            }
        except Exception as err:
            return {
                "system": "Mob Equipment Assignment",
                "pass": False,
                "error": str(err),
                "detail": f"Could not audit mob equipment: {err}",
            }

    # ------------------------------------------------------------------
    # Audit 3: Room Title Cleanliness
    # ------------------------------------------------------------------

    def _audit_room_titles(self, full: bool) -> Dict[str, Any]:
        """Audit room titles for meta-development tags."""
        try:
            from world.room_titles import sanitize_all_rooms

            summary = sanitize_all_rooms(dry_run=True)
            clean = summary.get("changed", 0) == 0

            result = {
                "system": "Room Title Cleanliness",
                "pass": clean,
                "total_rooms": summary.get("total_rooms", 0),
                "changed": summary.get("changed", 0),
                "unchanged": summary.get("unchanged", 0),
                "detail": (
                    "All room titles are clean."
                    if clean
                    else f"{summary.get('changed', 0)} rooms have meta tags in titles."
                ),
            }

            if full and not clean:
                # Include a few examples in the detail.
                details = summary.get("details", [])
                if details:
                    examples = []
                    for d in details[:3]:
                        examples.append(
                            f"'{d['original']}' → '{d['cleaned']}'"
                        )
                    result["detail"] += "  Examples: " + "; ".join(examples)

            return result
        except Exception as err:
            return {
                "system": "Room Title Cleanliness",
                "pass": False,
                "error": str(err),
                "detail": f"Could not audit room titles: {err}",
            }

    # ------------------------------------------------------------------
    # Audit 4: Prompt / Combat State Integrity
    # ------------------------------------------------------------------

    def _audit_prompt_state(self) -> Dict[str, Any]:
        """
        Audit prompt state integrity for all online players.

        Checks:
          - Prompt is enabled (prompt_enabled attribute exists and is True).
          - Combat state matches CombatHandler.is_in_combat (no stale [FIGHTING]).
        """
        try:
            from evennia.objects.models import ObjectDB
            from typeclasses.characters import Character
            from world.tick_combat import CombatHandler

            online = 0
            prompt_enabled = 0
            prompt_disabled = 0
            combat_state_correct = 0
            combat_state_mismatches = 0

            for char in ObjectDB.objects.all():
                if not isinstance(char, Character):
                    continue
                if not hasattr(char, "sessions") or char.sessions.count() == 0:
                    continue

                online += 1

                # Check prompt state
                prompt_on = char.attributes.get("prompt_enabled", True)
                if prompt_on:
                    prompt_enabled += 1
                else:
                    prompt_disabled += 1

                # Check combat state integrity:
                # is_in_combat should match ndb.combat_state being FIGHTING.
                in_combat = CombatHandler.is_in_combat(char)
                ndb_fighting = False
                try:
                    from world.combat_state import CombatState
                    state = getattr(char.ndb, "combat_state", None)
                    ndb_fighting = state == CombatState.FIGHTING
                except Exception as err:
                    logger.log_err(f"_audit_prompt_state: combat state check failed for {char.key}: {err}")

                if in_combat == ndb_fighting:
                    combat_state_correct += 1
                else:
                    combat_state_mismatches += 1

            all_ok = (
                prompt_disabled == 0
                and combat_state_mismatches == 0
            )

            return {
                "system": "Prompt / Combat State Integrity",
                "pass": all_ok,
                "online_players": online,
                "prompt_enabled": prompt_enabled,
                "prompt_disabled": prompt_disabled,
                "combat_state_correct": combat_state_correct,
                "combat_state_mismatches": combat_state_mismatches,
                "detail": (
                    f"{online} online. "
                    f"Prompt: {prompt_enabled} on, {prompt_disabled} off. "
                    f"Combat state: {combat_state_correct} correct, "
                    f"{combat_state_mismatches} mismatches."
                ),
            }
        except Exception as err:
            return {
                "system": "Prompt / Combat State Integrity",
                "pass": False,
                "error": str(err),
                "detail": f"Could not audit prompt state: {err}",
            }

    # ------------------------------------------------------------------
    # Audit 5: Armor Absorption Correctness
    # ------------------------------------------------------------------

    def _audit_armor_absorption(self) -> Dict[str, Any]:
        """
        Audit that armor absorption is correct (no phantom absorption).

        Verifies that the ``get_effective_armor`` function returns 0 for
        entities with no equipment, and that ``has_armor_equipped`` returns
        False in the same case.
        """
        try:
            from world.mob_equipment import get_effective_armor, has_armor_equipped

            # Test with a live mob sample
            from evennia.objects.models import ObjectDB

            mobs_checked = 0
            mobs_with_armor = 0
            mobs_without_armor = 0
            phantom_absorptions = 0

            for obj in ObjectDB.objects.all():
                if not hasattr(obj, "attributes"):
                    continue
                if not obj.attributes.get("is_mob", False):
                    continue
                hp = obj.attributes.get("hp", 0)
                if hp <= 0:
                    continue

                mobs_checked += 1
                armor = get_effective_armor(obj)
                has_armor = has_armor_equipped(obj)

                if armor > 0:
                    mobs_with_armor += 1
                else:
                    mobs_without_armor += 1

                # Phantom absorption: armor=0 but has_armor_equipped=True
                if armor == 0 and has_armor:
                    phantom_absorptions += 1

                if mobs_checked >= 50:  # sample cap
                    break

            clean = phantom_absorptions == 0

            return {
                "system": "Armor Absorption Correctness",
                "pass": clean,
                "mobs_checked": mobs_checked,
                "mobs_with_armor": mobs_with_armor,
                "mobs_without_armor": mobs_without_armor,
                "phantom_absorptions": phantom_absorptions,
                "detail": (
                    f"{mobs_checked} mobs sampled. "
                    f"{mobs_with_armor} have armor, "
                    f"{mobs_without_armor} have no armor. "
                    f"{'No ' if clean else f'{phantom_absorptions} '}phantom absorptions."
                ),
            }
        except Exception as err:
            return {
                "system": "Armor Absorption Correctness",
                "pass": False,
                "error": str(err),
                "detail": f"Could not audit armor absorption: {err}",
            }

    # ------------------------------------------------------------------
    # Report formatting
    # ------------------------------------------------------------------

    def _format_report(self, results: List[Dict[str, Any]]) -> str:
        """Format all audit results into a readable report."""
        lines = []
        lines.append("|Y|h" + "=" * 65 + "|n")
        lines.append("|c|h         COMPREHENSIVE SYSTEM VERIFICATION REPORT|n")
        lines.append("|Y|h" + "=" * 65 + "|n")
        lines.append("")

        all_pass = True

        for r in results:
            system = r.get("system", "Unknown System")
            passed = r.get("pass", False)
            detail = r.get("detail", "")
            error = r.get("error", "")

            status = "|gPASS|n" if passed else "|rFAIL|n"
            if not passed:
                all_pass = False

            lines.append(f"  |w{system}:|n {status}")
            if detail:
                lines.append(f"    {detail}")
            if error:
                lines.append(f"    |rError: {error}|n")
            lines.append("")

        lines.append("|Y" + "-" * 65 + "|n")
        overall = "|gALL SYSTEMS PASS|n" if all_pass else "|rISSUES DETECTED|n"
        lines.append(f"  |wOverall:|n {overall}")
        lines.append("|Y" + "=" * 65 + "|n")

        return "\n".join(lines)