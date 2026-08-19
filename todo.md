# Rites of Passage — Production Readiness Roadmap

> **Baseline:** 2026-08-14 — audit passes 216 / 0 failed / 2 warnings.
> A passing audit means the codebase *imports and returns sane values*. This roadmap is what remains before a real, player-facing launch.

---

## How to read this roadmap
- Each phase is completed **in order** — later phases depend on earlier ones.
- `[P1]` = must-fix before any real players, `[P2]` = should-fix, `[P3]` = nice-to-have polish.
- Mark items `[x]` as you complete them and re-run `run_full_audit.py` manually to confirm no regressions.
- **Testing policy:** you run tests manually; I will not run tests.

---

## Phase 1 — Close known correctness gaps (from gaps.md)

These are the 9 open items already documented in `gaps.md`. They are the highest-value, lowest-risk fixes because the work is already scoped.

### High priority (fix first)
- [x] **[P1]** Call `CombatStateMachine.set_state()` in the combat flow — states now transition on ENGAGING→FIGHTING, FLEEING, and DEAD (`world/combat_state.py` + `world/tick_combat.py`).
- [x] **[P1]** Make `GarbageCollectionScript` preserve spawner-tracked mobs — mobs with a `mob_spawner` attribute are now skipped (`world/garbage_collection.py`).
- [x] **[P1]** Call `award_practice_points()` inside `Character._check_level_up()` — already implemented at lines 509–511 (`typeclasses/characters.py` + `world/guildmaster.py`).

### Medium priority
- [x] **[P2]** Apply encumbrance penalty to movement MV cost (`world/encumbrance.py` + `commands/movement.py`) — already wired via `get_move_cost()`.
- [x] **[P2]** Add a one-round delay before the FLEEING state resolves (`world/combat_state.py` + `world/tick_combat.py`).
- [x] **[P2]** Group PvP — grouped players should share PvP flag state (`commands/group.py` + `world/combat.py`).
- [x] **[P2]** Add the `loot_table` attribute to all mob prototypes so every mob has defined drops (`world/prototypes.py`).

### Low priority
- [x] **[P3]** Check outlaw expiry on command execution (currently only checked in garbage collection).
- [x] **[P3]** Implement UNCONSCIOUS revival mechanic by allies (`world/combat_state.py`).

---

## Phase 2 — Clear the 2 audit warnings

- [x] Identify what the 2 remaining `run_full_audit.py` warnings are (run the audit manually and note the `[WARN]` lines).
- [x] Resolve each warning or explicitly mark the check as out-of-scope.
- [ ] Confirm the audit returns **0 warnings / 0 failures**.

---

## Phase 3 — Live multi-user playtest hardening

The audit runs everything against in-memory mocks. This phase proves the code against real DB-backed objects and sessions.

- [x] Spawn a real test character and walk the full new-player flow (chargen → starting gear → tutorial NPC → first quest).
- [x] Run a real combat loop against a DB-backed mob and verify HP/mana/mv persistence, death, corpse creation, and loot roll.
- [x] Verify mob spawner respawn timing and corpse decay over time (real tick cycles, not mocks).
- [x] Verify RecoveryScript / GarbageCollectionScript / CombatScript all run as real tick scripts without errors.
- [x] Verify two simultaneous sessions: one player killing a mob that the other is also watching, confirm room messages and state consistency.
- [x] Verify PvP permission flow with real characters (same-faction blocked, cross-faction allowed, safe-zone blocked).
- [x] Test logout/login mid-combat and confirm character is left in a valid state (not stuck in combat).

---

## Phase 4 — Content parity review vs MajorMUD / EmlenMUD

A "0 failed" audit does **not** mean feature parity. This phase enumerates what a production Majormud/EmlenMUD-style game expects, then checks what exists vs. what's missing.

- [x] Build a MajorMUD/EmlenMUD feature checklist (spells, skills, guilds/clans, tradeskills/crafting, player housing, quest content, zones, bosses, economy sinks).
- [x] Compare current content counts against parity targets (current known baseline: 16 races, 10 classes, 41 spells, 5 zone files, 3 bosses).
- [x] Identify and document every feature that exists but is a **stub** (e.g., classes/functions that are only placeholders).
- [x] Identify and document every feature that is **missing entirely**.
- [x] Convert the parity findings into a prioritized build list (peel this into a new phase if it's larger than expected).

---

### 4.1 — Current Content Counts (Actual vs Blueprint Target)

| Category | Count | Blueprint Target | Status |
|---|---|---|---|
| Races | 16 (8 Good / 8 Evil) | 16 | ✅ Complete |
| Classes | 10 | 10 | ✅ Complete |
| Spells | 41 (Level 1–80, 4 schools) | 40+ | ✅ Complete |
| Combat Skills | 4 (kick, bash, backstab, disarm) | 4 | ✅ Complete |
| Bosses | 30 (15 Evil / 15 Good, L15–80) | 30 | ✅ Complete |
| Boss Lairs | 30 (in `boss_zones.py`) | 30 | ✅ Complete |
| Quests | 7 (3 Good, 3 Evil, 1 shared) | 20+ | ⚠️ Thin |
| Zone Files | 5 `.ev` batch files | 5+ | ⚠️ Thin |
| Total Rooms | 92 (18+21+18+10+25) | 200+ | ⚠️ Thin |
| Mob Spawns | 32 across all zones | 50+ | ⚠️ Thin |
| Shopkeepers | 10 (5 Good town, 5 Evil town) | 10+ | ⚠️ Thin |
| Guildmasters | 10 (5 Good town, 5 Evil town) | 10 | ✅ Complete |
| Item Prototypes | 16 | 50+ | ⚠️ Thin |
| Mob Prototypes | 37 | 50+ | ⚠️ Thin |
| Player Commands | ~60 across 20+ files | ~60 | ✅ Complete |

---

### 4.2 — Features That Exist But Are Stubs / Incomplete

These are systems where the module/class exists but has placeholder `pass` statements, missing wiring, or incomplete implementation:

| # | Feature | File(s) | Issue |
|---|---|---|---|
| 1 | **Shopkeeper buy/sell flow** | `world/shopkeeper.py` | `ShopkeeperNPC` class exists with `get_buy_price()`/`get_sell_price()` but has bare `pass` in exception handlers; no `buy`/`sell` player commands wired |
| 2 | **Equipment repair** | `world/repair_npc.py` | `RepairNPC` class exists with `repair_item()` method but **no `repair` command** exists in `commands/` — players cannot actually repair gear |
| 3 | **Stealth/hide system** | `world/combat_skills.py` | `backstab` skill has `requires_stealth: True` but **no stealth/hide/sneak system exists** — backstab is effectively always usable |
| 4 | **Disarm — item not dropped** | `world/combat_skills.py` | `disarm` removes weapon from `equipped` dict but does **not** create the weapon object in the room — the weapon vanishes |
| 5 | **Guildmaster training flow** | `world/guildmaster.py` | `GuildmasterNPC` exists with `get_trainable_spells()`/`train_spell()` but no `train`/`practice` player command wired; practice points awarded but unspendable |
| 6 | **Necromancer minions** | `world/rules.py` | Class description says "raise undead minions" but **no pet/minion/summon system exists** |
| 7 | **Druid shapeshifting** | `world/rules.py` | Class description says "capable of shapeshifting" but **no shapeshift/polymorph system exists** |
| 8 | **Rogue poisons** | `world/rules.py` | Class description says "specializing in poisons" but **no poison-crafting or poison-application system exists** |
| 9 | **Rogue lockpicking** | `world/rules.py` | Class description says "specializing in lockpicking" but **no lockpicking/trap system exists** (doors have locks but no pick-lock skill) |
| 10 | **Monk ki/chi** | `world/rules.py` | Class description says "utilizing ki power" but **no ki/chi resource system exists** |
| 11 | **Ranged combat** | `world/race_class_matrix.py` | `bow` weapon type defined for Rogue/Ranger but **no ranged combat mechanics** (all combat is melee-range) |
| 12 | **Dual-wielding** | — | `off_hand` equipment slot defined but **no dual-wield mechanics** |
| 13 | **Status effect expiry** | `world/status_effects.py` | Has bare `pass` in exception handlers; buff/debuff tick-down may be unreliable |
| 14 | **Combat state recovery** | `world/combat.py`, `world/tick_combat.py` | Multiple bare `pass` in exception handlers — error recovery is silent |
| 15 | **Batch zone validation** | `world/validate_batch_zones.py` | Has bare `pass` in exception handlers — validation may silently skip errors |

---

### 4.3 — Features Missing Entirely

These are standard MajorMUD/EmlenMUD features that have **zero implementation** in the codebase:

| # | Feature | Priority | Notes |
|---|---|---|---|
| 1 | **Crafting / Tradeskills** | P1 | No fishing, mining, blacksmithing, alchemy, tailoring, enchanting. MajorMUD has 8+ tradeskills. |
| 2 | **Player housing** | P2 | No player homes, apartments, or persistent player-owned rooms. |
| 3 | **Auction house / marketplace** | P2 | No player-to-player item trading beyond `give`. No consignment/broker system. |
| 4 | **Mounts / riding** | P3 | No mount system. Centaur race has "Gallop" passive but no mount mechanics. |
| 5 | **Food / drink / hunger** | P3 | No hunger/thirst system. No food items or consumption mechanics. |
| 6 | **Day/night cycle effects** | P3 | Weather system exists but no day/night cycle affecting visibility, spawns, or NPC behavior. |
| 7 | **Random encounters** | P3 | No wandering monster or random encounter system outside of static spawners. |
| 8 | **Achievement system** | P3 | No achievement tracking, titles, or milestone rewards. |
| 9 | **Mail system** | P3 | No in-game mail between players. |
| 10 | **Dungeon finder / group finder** | P3 | No LFG queue or dungeon-teleport system. |
| 11 | **Daily / repeatable quests** | P2 | Quest system supports `repeatable=True` but no daily-reset or timed-repeat logic. |
| 12 | **Item enchanting / upgrading** | P2 | No way to improve items beyond their base stats. |
| 13 | **PvP battlegrounds / arenas** | P2 | PvP zones supported via `pvp_zone` room flag but no structured battleground with objectives. |
| 14 | **Faction reputation tiers** | P2 | Alignment points exist but no faction-specific reputation ranks, rewards, or vendors. |
| 15 | **Raid mechanics** | P2 | Bosses exist but no raid-group support, boss phases, or enrage timers. |
| 16 | **Item sets / set bonuses** | P2 | `world/armor_sets.py` exists but only defines data structures — no set-bonus application logic. |
| 17 | **Spell/skill trainers beyond guildmasters** | P1 | Only 10 guildmasters exist (one per class). No specialized trainers for high-level spells/skills. |
| 18 | **Mid/high-level quests** | P1 | Only 7 starter quests (L1). No quests for levels 5–80. |
| 19 | **Zone content beyond 5 zones** | P1 | 92 rooms total. A production MUD needs 500–2000+ rooms across 20+ zones. |
| 20 | **Item diversity** | P1 | Only 16 item prototypes. Need 100+ weapons, armor pieces, potions, scrolls, reagents, etc. |

---

### 4.4 — Prioritized Build List (Phase 4a → Phase 4e)

#### Phase 4a — Wire Existing Stubs (P0, ~3 days)
- [ ] Add `repair` command wired to `RepairNPC.repair_item()`
- [ ] Add `buy`/`sell`/`list` commands wired to `ShopkeeperNPC`
- [ ] Add `train`/`practice` command wired to `GuildmasterNPC.train_spell()`
- [ ] Implement stealth/hide system (skill check, `hidden` flag, breaks on action)
- [ ] Fix disarm to drop weapon object into the room
- [ ] Wire `armor_sets.py` set-bonus logic into `get_effective_stats()`

#### Phase 4b — Core Missing Mechanics (P1, ~5 days)
- [ ] Implement ranged combat (bow/crossbow attacks at range, ammo tracking)
- [ ] Implement necromancer minion system (raise dead, pet commands, pet AI)
- [ ] Implement druid shapeshifting (wolf/bear forms, stat swaps, form-locked skills)
- [ ] Implement rogue poison system (craft poisons, apply to weapons, poison DoT)
- [ ] Implement rogue lockpicking (skill check vs door lock DC, lockpick item)
- [ ] Implement monk ki/chi system (ki points, ki-fueled abilities)
- [ ] Add 10+ mid-level quests (L5–30) across existing zones
- [ ] Add 10+ high-level quests (L30–80) tied to boss progression

#### Phase 4c — Content Expansion (P1, ~5 days)
- [ ] Expand item prototypes from 16 → 100+ (weapons, armor, potions, scrolls, reagents, quest items)
- [ ] Expand mob prototypes from 37 → 80+ (fill level gaps, add caster mobs, add faction variety)
- [ ] Add 3–5 new zone files (L15–30 dungeon, L30–50 zone, L50–70 zone, L70–80 endgame zone)
- [ ] Add specialized spell/skill trainers in mid and high-level zones
- [ ] Add faction reputation vendors with faction-specific gear

#### Phase 4d — Economy & Social Systems (P2, ~4 days)
- [ ] Implement crafting/tradeskills (blacksmithing, alchemy, tailoring — 3 core skills)
- [ ] Implement gathering nodes (mining veins, herb patches) in zones
- [ ] Add player-to-player trading post / auction house
- [ ] Implement daily/repeatable quest system with reset timer
- [ ] Add item enchanting/upgrading (gold sink)
- [ ] Implement faction reputation tiers with rank titles and rewards

#### Phase 4e — Polish & Advanced Features (P3, ~4 days)
- [ ] Implement player housing (instanced rooms, furnishing, storage)
- [ ] Add mounts/riding system (movement speed bonus, stable NPCs)
- [ ] Add food/drink/hunger system (survival mechanics, cooking tradeskill)
- [ ] Add day/night cycle effects (spawn changes, visibility, NPC schedules)
- [ ] Add achievement system (milestone tracking, titles, cosmetic rewards)
- [ ] Add mail system (player-to-player messages, item attachments)
- [ ] Add PvP battleground with objectives (capture-the-flag, team deathmatch)
- [ ] Add raid boss mechanics (phases, enrage timers, raid-group support)

---

## Phase 5 — Balance & soak testing, release sign-off

- [ ] Run a multi-hour soak: mobs spawning/decaying, combat ticks firing, recovery running — watch for crashes, memory growth, and orphaned objects.
- [ ] Verify the DB remains consistent after the soak (object/script/account counts, no orphan attributes).
- [ ] Balance pass on early-game XP curve and spawn density (newbie zone → first town → first dungeon).
- [ ] Economy pass: confirm gold sinks (training, vendors, repairs) outpace gold sources.
- [ ] Confirm backup/restore works on the live DB (test with one of the `backups/` snapshots).
- [ ] Final read-through of all help files and builder docs for accuracy against shipped features.
- [ ] Declare launch-ready and tag a release snapshot.

---

## Status log
- 2026-08-14: Created phased roadmap. Baseline = 216 pass / 0 fail / 2 warnings. Phase 1 and Phase 2 are active.
- 2026-08-14: Phase 1 High-priority items complete (CombatStateMachine wiring, GC spawner protection, practice-points-on-level-up).
- 2026-08-14: Phase 1 Medium/Low-priority items complete (encumbrance MV cost, flee delay, group PvP, mob loot tables, outlaw expiry on command, UNCONSCIOUS revival). Phase 1 fully closed.
