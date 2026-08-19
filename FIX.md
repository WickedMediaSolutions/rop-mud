# FIX.md — Rites of Passage MUD: Remaining Issues

**Updated:** 2026-08-19  
**Status:** All 19 issues resolved — 3 Critical + 5 High-Priority + 5 Medium + 6 Low.

---

## Low Priority (6 items) — ALL RESOLVED

- [x] **`commands/default_cmdsets.py:25`** — Renamed `CmdList` to `CmdShopList` to avoid shadowing the Python `list` built-in.
- [x] **`typeclasses/objects.py:14-23`** — Added `at_object_creation`, `at_pre_say`, and `return_appearance` hooks to `ObjectParent` mixin.
- [x] **`world/combat.py:69-71`** — `_get_effective_hp()` now defaults to `attributes.get("max_hp", 100)` instead of 0.
- [x] **World build** — `builder_phase4.py` now calls `_run_phase_verify()` after each phase (rooms, exits, populate).
- [x] **`world/chargen.py` / `typeclasses/charcreate.py`** — `_find_start_room()` now alerts staff via `admin_log`, auto-populates faction start rooms via `build_faction_starters()`, then retries alignment search before falling back to Limbo.
- [x] **`world/mob_equipment.py`** — `_create_equipment_item()` and `_make_mock_item()` now set `weapon_type` via `_infer_weapon_type()` using the canonical proficiency categories (`sword`, `axe`, `mace`, `dagger`, `staff`, `wand`, `bow`, `crossbow`, `club`, `fist`, `two_handed`).

---

## Resolved (for reference)

| # | Issue | Resolution |
|---|-------|------------|
| BUG-1 | Duplicate chargen double-login loop | `CHARGEN_MENU` → `world.chargen`, `chargen_completed` flag on new_char |
| BUG-2 | `chargen_completed` set on wrong object | Set on both caller and new_char with `attributes.add` |
| BUG-3 | `charcreate.py` incompatible flat stat format | Standard `stats` dict, all 6 stats, all missing initializations |
| HP-1 | `charcreate.py` races diverged from `rules.py` | Synced to 16 races (8 Good, 8 Evil) |
| HP-2 | `charcreate.py` classes diverged from `rules.py` | Synced to 10 classes, added `hp_per_level`/`mana_per_level` |
| HP-3 | `chargen.py` missing `equipped` init | Added `attributes.add("equipped", {})` |
| HP-4 | `charcreate.py` missing `save_bonuses` | Added `attributes.add("save_bonuses", {})` |
| HP-5 | `get_effective_stats()` no legacy fallback | Added flat-attribute fallback for old characters |
| MED-1 | `_execute_offhand_round()` THAC0 monkey-patching | Refactored to pass `thac0_penalty` parameter through `_hit_roll()` |
| MED-2 | `_within_wander_radius()` always returned True | Implemented BFS distance checking with ndb caching |
| MED-3 | `equip_item()` stored raw slot keys | Now stores canonical slot keys for consistent downstream reads |
| MED-4 | `super().at_post_login()` missing guard | Already had try/except AttributeError guard |
| MED-5 | No one-way exit detection | Added `verify_one_way_exits()` to `realm_verify.py` |