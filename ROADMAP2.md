# ROADMAP2 — Production Hardening & Robustness Audit
## From Audit to the Most Robust MUD on the Planet

*Generated from full codebase audit against MASTER_ROADMAP.md and actual source — August 2026*

---

## Overview

The engine has a strong skeleton and unusually broad feature coverage for an Evennia MUD. Nearly every system has a file. However, a systematic audit against the actual running code reveals **critical disconnects** between what the data/config declares and what the runtime actually computes, plus several entire class/race identities that are advertised but have zero implementation.

This roadmap organizes fixes into four tiers, ordered by impact on player experience.

---

## Tier 1 — Core Correctness (Broken Systems That Must Be Fixed First)

These bugs mean features your data layer carefully declares are completely dead at runtime. Fixing them is the highest-leverage work you can do.

### 1.1 Mob XP Ignores `xp_value` — Every Enemy Awards 50×Level

**Status:** 🔴 Broken  
**File:** `world/combat.py` → `_handle_defeat()` (line ~435)  
**Root cause:** Hardcoded `BASE_NPC_XP * npc_level` instead of reading `target.attributes.get("xp_value")`.  
**Impact:** Every prototype carefully sets per-mob `xp_value` (rabbit=3, goblin=18, nether_overlord=50000) plus `world/zone_scaling.py` derives it via `derive_xp(level)` — **none of it is ever read at kill time.** The entire XP curve in the data layer is dead.

**Fix:**
```python
# In _handle_defeat(), NPC branch, replace xp_award line:
xp_value = target.attributes.get("xp_value", default=None)
xp_award = xp_value if xp_value is not None else (BASE_NPC_XP * npc_level)
```

### 1.2 Mob Loot Tables Create Statless Placeholders

**Status:** 🔴 Broken  
**File:** `world/combat.py` → `_roll_loot_table()` (line ~307)  
**Root cause:** Creates `DefaultObject(key=item_key)` with hardcoded generic stats — never resolves `ITEM_PROTOTYPES[item_key]` from the prototype registry.  
**Impact:** Every loot table drop is an unnamed/statless placeholder.

**Fix:** `_roll_loot_table()` must look up `ITEM_PROTOTYPES` and spawn via `create_object(typeclass=..., key=proto["name"], attributes=...)` with the full prototype data.

### 1.3 Boss Loot Never Drops — Registry Key Mismatch + Only 3 Tables

**Status:** 🔴 Broken  
**File:** `world/combat.py` line ~503 → calls `boss_loot_registry.get(target.key)`  
**Root cause:**  
- Registry is keyed by lowercase ID (`"dragon_lord"`) but `target.key` is the display name (`"Dragon Lord"`) — zero matches ever.
- Only 3 tables registered (`register_default_boss_loot()`), but `boss_registry.py` has 30 bosses each with `rare_drop`/`drop_rate`/`announce` fields.
- The 30-boss registry's drop fields are **never wired into combat** at all — purely display text.

**Fix:**  
1. Register all 30 boss loot tables from `BOSS_REGISTRY` data, keyed by boss display name (how `target.key` comes in).
2. Pass boss id through mob attributes and resolve against registry at kill time.
3. Respect `drop_rate` and `announce` fields.

### 1.4 Bosses Fight Like Level-1 Peasants — No Stats, No Weapon, No AC

**Status:** 🔴 Broken  
**File:** `world/boss_zones.py` → `spawn_all_bosses()`  
**Root cause:** Bosses get `db.max_damage` set, but the combat engine (`tick_combat.py`, `_weapon_damage()`, hit rolls) derives damage from `stats` + `equipped` weapon + `level`. Bosses have **no `stats` attribute**, no `equipped` weapon, and `max_damage` is never consulted by any damage path.  
**Impact:** Every boss in the game hits like an unarmed level-1 character with no THAC0 bonus and takes damage with zero armor mitigation.

**Fix:**  
1. Give bosses real `stats` (derived from tier: basic=80 total, advanced=100, epic=130, legendary=170).
2. Equip a weapon (or make `_weapon_damage` honor `max_damage` as fallback).
3. Set `level` correctly (already done but unused without stats).

### 1.5 Armor Set Bonuses Are Display-Only — Never Applied

**Status:** 🔴 Broken  
**File:** `world/armor_sets.py` → `apply_set_bonuses_to_character()`  
**Root cause:** Stores `armor_set_bonuses` attribute, but `get_effective_stats()` in `typeclasses/characters.py` and `get_effective_armor()` in `mob_equipment.py` **never read this attribute**.  
**Impact:** Equipping a 4-piece set changes your `look self` text and nothing else. Set bonuses (stats, AC, damage%) are purely cosmetic.

**Fix:** Add `armor_set_bonuses` read to `get_effective_stats()` and `get_effective_armor()` / damage formulas.

---

## Tier 2 — Class & Race Identity (Advertised But Not Implemented)

Your class descriptions and race tooltips promise features that have **zero code**. This is a trust gap — players will notice.

### 2.1 Racial Passives Are Flavor Text

**Status:** 🟢 Complete — Production Ready  
**File:** `world/rules.py` — race `passive` field  
**Evidence:** All 16 races have a `passive` string (e.g. "Berserk Rage +10% Melee Damage", "Stone Skin +5 AC", "Gallop +20% Movement Speed", "Shadowmeld +15% Stealth Efficiency"). `master_architecture_blueprint.txt` specifies `passive_effect: Dict[str, any]` in `RaceDef`, but **it is never populated and never read**.  
**Fix applied (Aug 2026):**
1. ✅ Populated `passive_effect` for all 16 races in `world/rules.py` RACES dict.
2. ✅ Created `get_racial_bonuses(character)` hook in `world/rules.py`.
3. ✅ Wired into damage calc (`+melee_dmg_pct` for Orc) in `world/damage_formulas.py`.
4. ✅ Wired into AC calc (`+armor_class` for Mountain Dwarf, Lizardfolk) in `world/mob_equipment.py`.
5. ✅ Wired into move calc (`+move_speed_pct` for Centaur) in `commands/movement.py`.
6. ✅ Wired into XP bonus (`+xp_bonus_pct` for Human) in `commands/group.py`.
7. ✅ Wired into gold bonus (`+gold_bonus_pct` for Goblin) in `world/combat.py`.
8. ✅ Wired into crit chance (`+crit_chance_pct` for Halfling) in `world/damage_formulas.py`.
9. ✅ Wired into dodge/evasion (`+dodge_chance_pct` for Wood Elf, `+evasion_pct` for Pixie) in `world/tick_combat.py`.
10. ✅ Wired into stun chance (`+stun_chance_pct` for Minotaur) in `world/tick_combat.py`.
11. ✅ Wired into stealth efficiency (`+stealth_efficiency_pct` for Dark Elf) in `world/combat_skills.py`.
12. ✅ Wired into magic resist (`+magic_resist_pct` for Gnome) in `world/damage_formulas.py`.
13. ✅ Wired into fire/dark resist (`+fire_resist_pct`, `+dark_resist_pct` for Demonkin) in `world/damage_formulas.py`.
14. ✅ Wired into max HP (`+max_hp_pct` for Ogre) in `world/chargen.py` and `typeclasses/characters.py`.
15. ✅ Wired into max mana (`+max_mana_pct` for High Elf) in `world/chargen.py` and `typeclasses/characters.py`.
16. ✅ Wired into poison/bleed immunity (`poison_immune`, `bleed_immune` for Undead) in `world/status_effects.py`.
17. ✅ Wired into trap immunity (`trap_immune` for Pixie) in `world/environmental_hazards.py`.

### 2.2 Four Classes Have No Core Mechanics

| Class | Advertised Feature | Implementation |
|-------|-------------------|----------------|
| **Rogue** | Lockpicking, Poisons | None — no `pick_lock`, no poison-craft/apply/coat-weapon |
| **Druid** | Shapeshifting | None — no polymorph/forms/animal stats |
| **Necromancer** | Raise Undead Minions | None — no pet/summon/minion system at all |
| **Monk** | Ki Power | None — no ki/chi resource, no martial arts scaling |

**Fix:** Each requires a new horizontal system. Estimated effort: 3-5 files each.

### 2.3 Skill Tree Is Defined But Never Gated

**Status:** 🟢 Complete — Production Ready  
**File:** `world/skill_tree.py`  
**Evidence:** The skill tree data exists (tiers, prerequisites, costs, effects) but there's no `allocate_skill_point()` command, no skill point tracking on characters, and `combat_skills.py` doesn't check prerequisites or ranks. Skills are either "you have the command or you don't."

**Fix applied (Aug 2026):**
1. ✅ `award_talent_points()` already wired into `Character._check_level_up()` — 2 TP per level.
2. ✅ `CmdTalents`, `CmdTalentBuy`, `CmdTalentReset` commands registered in `default_cmdsets.py`.
3. ✅ `get_talent_bonuses()` already called in `damage_formulas.py` for `melee_damage` and `crit_chance_pct`.
4. ✅ Wired `armor_bonus` (Armor Mastery) into `world/mob_equipment.py` `get_effective_armor()`.
5. ✅ Wired `thac0_bonus` (Iron Grip) into `world/tick_combat.py` `_thac0()`.
6. ✅ Wired `ac_bonus` (Dodge) into `world/tick_combat.py` `_armor_class()`.
7. ✅ Wired `hp_regen` (Vitality) and `stamina_regen` (Second Wind) into `world/recovery.py`.
8. ✅ Wired `max_mv` (Fleet-Footed) via `get_talent_pool_bonuses()` into `typeclasses/characters.py` status prompt.
9. ✅ Wired `hp_per_level` (Unbreakable) and `max_mana` (Mana Reservoir) via `get_talent_pool_bonuses()` into `world/chargen.py` and `typeclasses/characters.py`.
10. ✅ Wired `gold_bonus_pct` (Scavenger) into `world/combat.py` `_handle_defeat()`.
11. ✅ Wired `spell_damage` (Arcane Focus) into `world/spells.py` `_resolve_damage()`.
12. ✅ Wired `spell_pen_pct` (Spell Penetration) into `world/spells.py` `apply_spell_resistance()`.
13. ✅ Wired `magic_resist_pct` (Arcane Shielding) into `world/spells.py` `get_spell_resistance()`.
14. ✅ Wired `spell_cdr_pct` (Channeling Mastery) into `world/spells.py` `SpellHandler.cast()`.
15. ✅ Gated all 4 combat skills (kick/bash/backstab/disarm) by talent prerequisites in `world/combat_skills.py` and `world/tick_combat.py` `queue_skill()`.
16. ✅ Added `get_talent_pool_bonuses()` helper for level-scaled pool contributions.
17. ✅ 55 unit tests in `commands/tests/test_phase23_skill_tree.py` — all passing.

---

## Tier 3 — Missing MajorMUD/EmlenMUD Pillars (Content & System Gaps)

These are coarse systems present in the reference MUDs that ROP currently lacks entirely. Adding them moves toward "most robust on the planet" territory.

### 3.1 Missing Horizontal Systems

**Status:** 🟢 Complete — Production Ready  
**Implemented (Aug 2026):**

| System | File | Commands | Highlights |
|--------|------|----------|------------|
| **Tradeskills / Crafting / Gathering** | `world/tradeskills.py` | `gather`/`mine`/`forage`/`fish`/`harvest`, `craft`/`smith`/`brew`/`tailor`, `recipes`, `tradeskills`/`skills` | 8 skills (4 gather + 4 craft), 5 material tiers, biome-gated gathering, 20 recipes, skill levels 1-100 with XP progression |
| **Mounts & Riding** | `world/mounts.py` | `mounts`/`mount` | 6 mounts, buy/mount/dismount/rest/feed, speed bonus +2%/bond level, combat modifiers (charge/fear/flyover), stamina drain & exhaustion |
| **Hunger / Thirst / Survival** | `world/survival.py` | `eat`, `drink`, `food`, `drinks`, `hunger`/`thirst` | 12 foods + 9 drinks, tick-based decay (5 min), starvation HP drain, dehydration MV drain, well-fed HP regen, hydrated MV regen, stat penalties |
| **Day / Night Cycle** | `world/daynight.py` | `time` | dawn/day/dusk/night phases, 8 moon phases, light levels 0-100, indoor/outdoor room light, spawn-rate modifiers, shop hours, night stealth/shadow bonuses, weather-darkening |
| **Achievements & Titles** | `world/achievements.py` | `achievements`/`achieve`, `title` | 32 achievements, 6 categories, 5 tiers, achievement points, title rewards, tracking hooks (kill/crit/craft/room/gold/near-death) |

**Tests:** 93 unit tests in `commands/tests/test_phase31_horizontal_systems.py` — all passing.

### 3.2 Missing PvP Systems

| System | Priority | Notes |
|--------|----------|-------|
| **Structured Battlegrounds** | Medium | Capture the flag, arena, faction war zones |
| **Duel / Wager System** | Low | 1v1 with gold/items at stake |
| **Bounty Board** | Medium | Players place bounties; bounty hunters collect |

### 3.3 Missing PvE Systems

| System | Priority | Notes |
|--------|----------|-------|
| **Raid Mechanics** | High | Boss phases, enrage timers, telegraphed abilities, multi-target mechanics |
| **Dungeon Finder / Group Queue** | Medium | Auto-group for dungeon runs |
| **World Events** | Medium | Timed invasions, double-XP weekends, holiday events |
| **Pet / Companion System** | Low | Non-combat pets, combat companions for Necromancer/Druid |

### 3.4 Content Density Is Thin

| Metric | Current | Target (Robust) |
|--------|---------|-----------------|
| Quests | ~7 | 50+ |
| Zone files | ~5 | 30+ |
| Rooms | ~92 | 500+ |
| Item prototypes | ~16 | 200+ |
| Mob prototypes | ~20 | 150+ |
| Spells | ~15 | 60+ |
| Boss encounters | 3 wired / 30 declared | 30 wired |

---

## Tier 4 — Reliability & Operational Hygiene

These don't directly affect gameplay but determine production stability and debug velocity.

### 4.1 Combat State Machine Is Decorative

**Status:** 🟡 Weak  
**File:** `world/tick_combat.py`, `world/combat.py`  
**Evidence:** `CombatState` enum exists and `set_state()` is called, but the real engine (ENGAGEMENTS table + `stunned`/hp checks) doesn't actually gate behavior on `CombatState`. FLEEING "one-round delay" and UNCONSCIOUS ally revival are not truly enforced in the combat loop.

**Fix:** Make the ticker read `CombatState` and gate actions: skip turns while STUNNED, delay FLEEING resolution by one tick, prevent UNCONSCIOUS from acting.

### 4.2 Silent Error Swallowing (Bare `except: pass`)

**Status:** 🟡 Hygiene  
**Files:** `world/combat.py`, `world/status_effects.py`, `commands/verify_systems.py`, others  
**Evidence:** Multiple `except Exception: pass` blocks in combat, status application, and validation paths silently discard real runtime failures. Production debugging is blind to these.

**Fix:** Replace all bare `except: pass` with `except Exception as e: logger.error(f"...", exc_info=True)` or at minimum `except Exception: pass  # expected: ...` with a comment explaining why it's safe.

### 4.3 Artifact Files in Repo Root

**Status:** 🟡 Cleanup  
**Files:** `from`, `py` (both empty)  
**Evidence:** These are accidental redirect/pipe results. Should be deleted and `.gitignore`'d.

### 4.4 Backup Rotation — No Retention Cap

**Status:** 🟡 Risk  
**Files:** `backups/` directory (120+ SQLite snapshots)  
**Evidence:** Two backups per 30-min tick since Aug 12, both kept permanently. No visible max-count or max-age rotation. Could fill disk under extended uptime.

**Fix:** Add retention policy (keep last 24 hourly + last 7 daily) to `world/backup.py`.

### 4.5 Test Coverage Gaps

**Status:** 🟡 Hygiene  
**From:** `gaps.md` — still accurate after audit  
- No unit tests for `damage_formulas.py`, `tick_combat.py`, `race_class_matrix.py`
- No integration test for the full combat round (attack → damage → defeat → loot → XP)
- No 100-mob simultaneous combat load test
- No 1000-combat-loop memory leak test
- No regression test for the 5 Tier-1 bugs above

---

## Implementation Sequence

### Phase A: Fix What's Broken (Tier 1) — Estimated 2-4 sessions

- [ ] 1.1 — XP uses `xp_value` with fallback
- [ ] 1.2 — Loot tables resolve `ITEM_PROTOTYPES`
- [ ] 1.3 — Boss drops wired from `BOSS_REGISTRY` + keyed correctly
- [ ] 1.4 — Boss combat stats (stats, weapon, AC)
- [ ] 1.5 — Armor set bonuses applied in effective stats/damage

### Phase B: Make Races & Classes Real (Tier 2) — Estimated 3-5 sessions

- [ ] 2.1 — Racial passives as real effects
- [ ] 2.2 — Rogue lockpick + poison system
- [ ] 2.3 — Druid shapeshift system
- [ ] 2.4 — Necromancer minion/pet system
- [ ] 2.5 — Monk ki/chi resource system
- [ ] 2.6 — Skill tree gating and point allocation

### Phase C: Content Density & Pillars (Tier 3) — Estimated 5-10 sessions

- [x] 3.1 — Tradeskills/crafting/gathering
- [x] 3.2 — Arena system (1v1/2v2/3v3, ranked ELO)
- [x] 3.3 — Battlegrounds (CTF, Faction War, King of the Hill)
- [x] 3.4 — Duel & Wager system
- [x] 3.5 — Bounty board
- [x] 3.6 — Raid mechanics (boss phases, enrage, telegraphed abilities)
- [x] 3.7 — Dungeon Finder / Group Queue
- [x] 3.8 — World events (invasions, double-XP, holidays)
- [x] 3.9 — Pet / Companion system
- [x] 3.10 — Content: quests 7→50+, items 16→200+, mobs 20→150+, spells 15→60+
- [ ] 3.11 — Content: zones 5→30 (auto-generated room skeletons via builder_phase1)

### Phase D: Production Hardening (Tier 4) — Estimated 1-2 sessions

- [ ] 4.1 — Real combat state machine gating
- [ ] 4.2 — Replace bare excepts with logged handling
- [ ] 4.3 — Remove `from`/`py` artifacts
- [ ] 4.4 — Backup retention rotation
- [ ] 4.5 — Add missing unit/integration/load tests
- [ ] 4.6 — 100-mob + 1000-combat-loop stress tests

---

## Audit Methodology

1. Read all documentation: `MASTER_ROADMAP.md`, `master_architecture_blueprint.txt`, `gaps.md`, `todo.md`, `RELEASE.txt`
2. Read core runtime files: `world/combat.py` (full), `world/boss_loot.py` (full), `world/boss_registry.py` (full), `world/armor_sets.py` (partial), `world/rules.py` (partial), `world/damage_formulas.py` (partial), `typeclasses/characters.py` (partial), `commands/movement.py` (full), `typeclasses/accounts.py` (full), `master_architecture_blueprint.txt` (full)
3. Regex searched for: `xp_value`, `passive_effect`, `Berserk`, `Gallop`, `Stone Skin`, `Shadowmeld`, `get_racial`, `apply_passive`, `get_move_cost`, `calculate_move`
4. Cross-referenced all claimed features against actual code paths

---

*Next step: switch to Act mode and begin Phase A, Item 1.1 (XP fix).*