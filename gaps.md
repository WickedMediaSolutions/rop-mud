# Rites of Passage — Remaining Gaps Task List

> **Generated:** 2026-08-14
> **Source:** `todo.md`
> **Purpose:** Consolidated list of all integration gaps, TODOs, and unimplemented features that still need to be completed.

---

## Phase 1: 10-Way Navigation & Core Engine Fixes

### 1.2 Exit Rendering & Room Appearance
- [x] Add exit lock validation — exits with `lock` or `closed` state should not appear in exit list or be traversable — `typeclasses/exits.py` `is_hidden_door()`, `at_traverse()` blocks closed/locked
- [x] Implement `CmdOpen`, `CmdClose`, `CmdLock`, `CmdUnlock` commands — `commands/doors.py`
- [x] Implement `brief` / `verbose` mode toggle (suppress room descriptions on re-entry) — `commands/general.py` `CmdBrief`, `CmdVerbose`

### 1.3 Movement Cost & MV Drain
- [x] Make `CmdMove` deduct 1 MV per room traversed (single-step movement) — `commands/movement.py`
- [ ] Apply encumbrance penalty to movement MV cost
- [x] Implement standalone `exits` command (list visible exits with short names) — `commands/general.py` `CmdExits`

### 1.4 Look / Examine / Scan System
- [x] Implement `examine <object>` — detailed item stats (weight, value, durability, armor, magic resist, stat bonuses) — `commands/general.py` `CmdExamine`
- [x] Implement `scan` — brief list of nearby rooms/visible exits without moving — `commands/general.py` `CmdScan`
- [x] Look at another player shows gear/alignment/level — `typeclasses/characters.py` `return_appearance()`

---

## Phase 2: Race, Class & Faction Matrix

### 2.5 Faction/Alignment System Integration
- [x] Implement room entry restrictions based on alignment (e.g., Evil blocked from Good temples) — `typeclasses/rooms.py` `at_object_receive()`
- [x] Guard NPCs auto-aggro opposite-faction players entering their city — `typeclasses/rooms.py` `at_object_receive()`
- [x] Vendor pricing modifiers based on faction alignment (same-faction discount, opposite-faction markup) — `world/shopkeeper.py` `_apply_faction_pricing()`
- [x] PvP flag integration — Good vs Evil auto-allow PvP without explicit toggle — `world/combat.py` `_is_pvp_allowed()`
- [x] Show outlaw status in `look` and `who` command outputs — `commands/general.py` `CmdWho`, `typeclasses/characters.py` `return_appearance()`
- [ ] Check outlaw expiry on command execution (currently only in garbage collection)

### 2.6 Lock Function Registration
- [x] Register `can_use_skill` lock function for skill command gating — `server/conf/lockfuncs.py`
- [x] Register `can_equip_slot` lock function for equipment restriction enforcement — `server/conf/lockfuncs.py`

---

## Phase 3: Combat Engine & Ability Integration

### 3.3 Combat State Machine
- [x] Integrate combat state machine into `CombatScript.at_repeat()` — check stunned/dead before attacking — `world/tick_combat.py` checks STUNNED/UNCONSCIOUS/DEAD
- [ ] Call `CombatStateMachine.set_state()` in combat flow — `set_state()` exists but is never called; states never transition
- [ ] Add one-round delay before FLEEING state resolves
- [ ] Add UNCONSCIOUS revival mechanic by allies

### 3.5 Mob AI & Aggro System
- [x] Hook `trigger_social_aggro()` into `CombatHandler.start_combat()` — `world/tick_combat.py` line 453
- [x] Implement room `at_object_receive()` hook for aggro-on-sight — `typeclasses/rooms.py`
- [x] Enforce `leash_room` and `max_chase_rooms` — mobs shouldn't chase indefinitely — `world/tick_combat.py` `CombatScript.at_repeat()`
- [x] Implement mob spellcasting AI (mobs with `spells` attribute cast during combat) — `world/tick_combat.py` `CombatScript.at_repeat()`, `world/mob_ai.py`
- [x] Implement mob mana tracking — `world/mob_ai.py` `npc_cast_spell()` deducts mana
- [x] Implement mob escape/flee AI (retreat when low HP) — `world/tick_combat.py` `CombatScript.at_repeat()`

### 3.6 PvP Combat Integration
- [x] Faction-based auto-PvP — Good vs Evil attackable without explicit toggle — `world/combat.py` `_is_pvp_allowed()`
- [ ] Group PvP — grouped players share PvP flag state
- [x] Integrate warpoint award on opposite-faction kill into death handler — `world/combat.py` `_award_warpoints()`
- [x] Implement infamy tracking for same-faction kills — `world/combat.py` `_apply_infamy()`

---

## Phase 4: Loot, Corpses, Spawners & Economy

### 4.1 Corpse System
- [x] Implement mob loot tables (`loot_table` attribute with weighted drops) — `world/combat.py` `_roll_loot_table()`
- [x] Integrate corpse loot rolling into `_handle_defeat()` — `world/combat.py`
- [x] Implement gold drop on mob death — `world/combat.py` `_handle_defeat()`
- [x] Corpse shows contents in room (`Here lies:` contents list) — `typeclasses/rooms.py` `get_display_things()`

### 4.2 Mob Spawner System
- [x] Create `MobSpawner` typeclass in `typeclasses/objects.py`
- [x] Add spawner rooms to zone batch files — all 5 batch zone files
- [ ] Ensure GarbageCollectionScript does NOT delete spawner-tracked mobs — currently GC deletes all mobs in empty rooms regardless of spawner ownership

### 4.3 Mob Prototype Enhancements
- [x] Add `mob_ai` attribute to all mob prototypes — `world/prototypes.py`
- [ ] Add `loot_table` attribute to all mob prototypes
- [x] Add `faction` attribute to all mob prototypes — `world/prototypes.py`
- [x] Add `xp_value` attribute to all mob prototypes — `world/prototypes.py`
- [x] Add `gold_min` / `gold_max` attributes to all mob prototypes — `world/prototypes.py`
- [x] Add `poison_on_hit` attribute for venomous mobs — `world/prototypes.py` (giant_spider)
- [x] Add `spells` attribute for spellcasting mobs — `world/prototypes.py` (dark_cultist, nether_overlord)
- [x] Add `damage_type` attribute for mob natural attacks — `world/prototypes.py`

### 4.4 Economy & Vendors
- [x] Place shopkeepers in zones (batch files) — all 5 batch zone files
- [x] Implement currency conversion (100 copper = 10 silver = 1 gold) — `world/shopkeeper.py` `convert_currency()`
- [x] Define shop inventory for shopkeepers — `world/prototypes.py` `shop_inventory` attrs
- [x] Implement vendor faction pricing — `world/shopkeeper.py` `_apply_faction_pricing()`
- [x] Implement item durability degradation logic — `world/shopkeeper.py` `degrade_item_durability()`

### 4.5 Drop/Give/Take Commands
- [x] Implement `give <item> to <character>` command — `commands/drop.py` `CmdGive`
- [x] Implement `put <item> in <container>` command — `commands/drop.py` `CmdPut`
- [x] Implement `get <item> from <container>` command — `commands/drop.py` `CmdGet`

---

## Phase 5: Guildmasters, Practice System & Recovery Loops

### 5.1 Practice System
- [ ] Call `award_practice_points()` in `Character._check_level_up()`
- [x] Place guildmasters in zones — all batch zone files
- [x] Add permanent skill-unlock indication after `train_skill()` — `world/guildmaster.py` stores `trained_skills` on character

### 5.2 Recovery & Positional States
- [x] Implement `CmdSleep` — `commands/general.py`
- [x] Implement `CmdWake` — `commands/general.py`
- [x] Fix RecoveryScript attribute name mismatch (uses `position`, commands use `is_resting`/`is_meditating`) — `world/recovery.py` uses `position` attribute
- [x] Position changes broadcast room messages — `commands/general.py` CmdRest, CmdMeditate, CmdSleep, CmdWake
- [x] Sleeping characters vulnerable to extra damage — `world/combat.py` `apply_physical_damage()` (+50% when sleeping)
- [x] Start RecoveryScript on server boot — `server/conf/at_server_startstop.py`
- [x] Improve standing regen rates — `world/recovery.py` `POSITION_REGEN_RATES`

### 5.3 Stamina System
- [x] Scale max stamina with CON or level (currently hardcoded 100) — `world/recovery.py` scales with CON and level
- [x] Display stamina in prompt or status — `typeclasses/characters.py` `get_status_prompt()`
- [x] Initialize stamina on character creation — initialized on first access with default 100
- [x] Add `stamina` command — `commands/general.py` `CmdStamina`

---

## Phase 6: World Building, Content Pipelines & Polish

### 6.1 Batch Zone Building Pipeline
- [x] Create `world/batch_zones/` directory with `.ev` templates
- [x] Create `aethelgard_town.ev` (Good starting town) — 18 rooms, 4 shops, 5 guildmasters, 2 guards, 1 tutorial NPC
- [x] Create `gorgoroth_town.ev` (Evil starting town) — 18 rooms, 4 shops, 5 guildmasters, 2 guards, 1 tutorial NPC
- [x] Create `newbie_zone.ev` (Levels 1-5) — 25 rooms, 1 quest NPC, 2 spawners
- [x] Create `darkwood_forest.ev` (Levels 5-15) — 20 rooms, 6 spawners, 1 mini-boss
- [x] Create additional zones for levels 15-30, 30-50, 50-80 — `high_level_zones.ev` with 3 zones, 3 bosses

### 6.2 Room ANSI Color Standards
- [x] Document color standards in builder guide — `world/builder_guide.md`
- [x] Enforce standards via batch file validation script — `world/validate_batch_zones.py`

### 6.3 NPC & Mob Building Standards
- [x] Document required mob attributes (level, stats, hp, alignment, faction, xp, gold, mob_ai)
- [x] Document aggressive mob configuration
- [x] Document boss mob configuration
- [x] Document city guard configuration
- [x] Document vendor configuration
- [x] Document guildmaster configuration

### 6.4 Item Building Standards
- [x] Document equipment item attributes
- [x] Document weapon attributes
- [x] Document armor attributes
- [x] Document rings/amulets attributes
- [x] Document consumables attributes
- [x] Document quest items attributes
- [x] Document containers attributes

### 6.5 Help File System
- [x] `help races` — `world/help_entries.py`
- [x] `help classes`
- [x] `help matrix`
- [x] `help combat`
- [x] `help spells`
- [x] `help pvp`
- [x] `help recovery`
- [x] `help economy`
- [x] `help movement`
- [x] `help factions`
- [x] `help guildmasters`
- [x] `help quests`
- [x] `help clans`
- [x] `help groups`
- [x] `help newbie`

### 6.6 New Player Experience
- [x] Welcome message with ANSI ASCII art banner on first login — `world/new_player_experience.py`
- [x] Starting equipment package per class (auto-equipped) — `grant_starting_gear()`
- [x] Tutorial NPC in starting room — spawned in both town batch files
- [x] First quest: "Kill 3 Goblin Scouts" — `register_first_quest()`
- [x] Level 1-3 newbie zone with only passive/neutral mobs — `newbie_zone.ev`

### 6.7 Status Prompt Enhancements
- [x] Hide `[MP: X/Y]` for non-mana classes — `get_status_prompt()` checks `can_cast_spells()`
- [x] Add stance indicator (`[REST]`, `[MEDITATE]`, `[SLEEP]`)
- [x] Add combat indicator (`[FIGHTING]`)
- [x] Add outlaw indicator (`[OUTLAW]`)
- [x] Add stamina segment (`[SP: X/100]`)
- [x] Make prompt segments configurable via `prompt` command — `CmdPrompt` toggles on/off

### 6.8 Character Look Enhancements
- [x] Self-look: show encumbrance level — `return_appearance()` in `typeclasses/characters.py`
- [x] Self-look: show equipment durability summary — `_get_equipment_durability_summary()`
- [x] Self-look: show current position
- [x] Self-look: show practice points remaining
- [x] Other-character look: show alignment, level, visible gear
- [x] Other-character look: show outlaw status
- [x] NPC look: show con result inline — `CmdConsider` in `commands/general.py`
- [x] Item examine: weight, value, durability, armor, magic resist, stat bonuses, damage, damage type — `CmdExamine`

### 6.9 Who List Enhancements
- [x] Show outlaw status for outlawed players
- [x] Show PvP status
- [x] `who good` / `who evil` alignment filter
- [x] `who <class>` filter
- [x] `who <level range>` filter

### 6.10 Server Startup & Administration
- [x] Start RecoveryScript on server boot — `at_server_startstop.py`
- [x] Start GarbageCollectionScript on server boot — `at_server_startstop.py`
- [x] Initialize stamina on all existing characters (migration) — stamina initialized on first access with default 100
- [x] Initialize `practice_session` on all existing characters — initialized on first access via `award_practice_points()`
- [x] Add `reload` admin command — `commands/admin.py` `CmdReload`
- [x] Add `goto <room>` admin command — `CmdGoto`
- [x] Add `spawn <prototype>` admin command — `CmdSpawn`
- [x] Add `set <attr> = <value>` admin command — `CmdSet`

### 6.11 Memory Leak Prevention & Stability
- [x] Audit `delay()` calls for weak references / cleanup
- [x] Audit Script objects stop on owner deletion
- [x] Clear ndb references on stop_combat/delete/script-stop
- [x] Add `at_object_delete()` cleanup hook to Character — `typeclasses/characters.py`
- [x] Add orphan script detection in GarbageCollectionScript
- [x] Add database integrity check for equipped items
- [x] Add periodic save of dirty attributes

### 6.12 Testing & Validation
- [ ] Unit tests for `race_class_matrix.py`
- [ ] Unit tests for `damage_formulas.py`
- [ ] Unit tests for `tick_combat.py`
- [ ] Integration test: Orc Warrior spell gating
- [ ] Integration test: High Elf Mage spellbook
- [ ] Integration test: Warrior vs Goblin full loop
- [ ] Integration test: Good vs Evil PvP
- [ ] Integration test: guildmaster train → learn spell
- [ ] Load test: 100 mobs in room
- [ ] Memory test: 1000 combat loops

---

## File-Level TODOs

- [x] Create `MobSpawner` typeclass in `typeclasses/objects.py`
- [x] Create all zone batch files in `world/batch_zones/`
- [x] Create all help file entries in `world/help_entries.py`
- [x] Create startup hooks in `server/conf/at_server_startstop.py`
- [x] Create `MOB_PROTOTYPES` and `ITEM_PROTOTYPES` in `world/prototypes.py` — all batch zone @spawn references backed by prototypes

---

## Summary of Remaining Gaps (8 items)

| # | Phase | Item | Priority |
|---|-------|------|----------|
| 1 | 1.3 | Apply encumbrance penalty to movement MV cost | Medium |
| 2 | 2.5 | Check outlaw expiry on command execution | Low |
| 3 | 3.3 | Call `CombatStateMachine.set_state()` in combat flow | High |
| 4 | 3.3 | Add one-round delay before FLEEING state resolves | Medium |
| 5 | 3.3 | Add UNCONSCIOUS revival mechanic by allies | Low |
| 6 | 3.6 | Group PvP — grouped players share PvP flag state | Medium |
| 7 | 4.2 | GarbageCollectionScript must not delete spawner-tracked mobs | High |
| 8 | 4.3 | Add `loot_table` attribute to all mob prototypes | Medium |
| 9 | 5.1 | Call `award_practice_points()` in `Character._check_level_up()` | High |