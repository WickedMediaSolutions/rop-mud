# Rites of Passage — Builder Guide & Content Standards

This guide documents the standards for building rooms, NPCs, mobs, and items.
All new content must follow these conventions so that the game renders,
validates, and balances correctly.

---

## 1. Room ANSI Color Standards

Room appearance is handled automatically by `typeclasses/rooms.py`, but
descriptions and titles must use the following color conventions:

| Element          | Code  | Color   | Example |
|------------------|-------|---------|---------|
| Room title       | `\|c` | cyan    | `\|cThe Grand Sanctum\|n` |
| Room description | `\|W` | grey    | body text (plain, no code needed for body) |
| Obvious exits    | `\|g` | green   | handled automatically |
| Hostile mobs     | `\|425`| pink   | handled automatically |
| Players          | `\|y` | yellow  | handled automatically |
| NPCs             | `\|W` | grey    | handled automatically |
| Ground items     | `\|w` | white   | handled automatically |
| Coins            | `\|Y` | gold    | handled automatically |

**Rules:**
- Never manually color room titles or exit lines; the typeclass does it.
- Use `|W` for grey body text in embedded descriptions.
- Always terminate ANSI codes with `|n`.
- Avoid raw escape sequences; use Evennia markup only.

---

## 2. NPC & Mob Building Standards

Every mob MUST carry the following attributes (via prototype `attrs` or
`@spawn`/`set` in batch files):

- `level` — int, mob level
- `stats` — dict `{"str","dex","con","int","wis","cha"}`
- `hp` / `max_hp` — int
- `alignment` — "Good", "Evil", or "Neutral"
- `faction` — "good", "evil", "neutral", or a specific faction tag
- `xp_value` — int, overriding default XP formula
- `gold_min` / `gold_max` — int, gold drop range
- `mob_ai` — `MobAIData` instance (disposition, aggro radius, assist radius)

### Aggressive mobs
```python
mob_ai = MobAIData(
    disposition=MobDisposition.AGGRESSIVE,
    aggro_radius=0,
)
```

### Boss mobs
```python
mob_ai = MobAIData(
    disposition=MobDisposition.GUARDIAN,
    assist_radius=1,
    assist_faction="boss_name",
)
```

### City guards
```python
mob_ai = MobAIData(
    disposition=MobDisposition.GUARDIAN,
    assist_faction="city_guard",
)
# alignment = "Good" or "Evil"
```

### Vendors
Typeclass `ShopkeeperNPC`, with:
- `db.shop_inventory` — list of `{"item_key", "price", "quantity"}`
- `db.shop_buy_mult = 0.50`
- `db.shop_sell_mult = 1.20`

### Guildmasters
Typeclass `GuildmasterNPC`, with:
- `db.guild_class` — the class this guildmaster serves

### Optional mob attributes
- `poison_on_hit` — bool, venomous mobs
- `spells` — list, spellcasting mobs
- `damage_type` — "slash"/"pierce"/"blunt" for natural attacks
- `loot_table` — list of `{"item_key", "weight", "min_qty", "max_qty"}`

---

## 3. Item Building Standards

Every equipment item MUST have:

- `weight` — float, kg
- `value` — int, gold
- `durability` / `max_durability` — int
- `stat_bonuses` — dict `{"str": 2}` (optional)
- `armor` — int (if armor)
- `magic_resist` — float (if magic item)

### Weapons
- `damage` — int, base damage
- `damage_type` — "slash"/"pierce"/"blunt"
- `item_type` — "weapon_sword", "weapon_axe", "weapon_dagger", etc.
- `slot` — "main_hand", "off_hand", "two_hand", "ranged"

### Armor
- `armor` — int, armor value
- `item_type` — "armor_light", "armor_medium", "armor_heavy", "armor_cloth"
- `slot` — "head", "neck", "shoulders", "chest", "arms", "hands",
  "waist", "legs", "feet", "ring_left", "ring_right"

### Rings / Amulets
- `item_type` — "ring", "necklace"
- `stat_bonuses` and optional `magic_resist`

### Consumables
- `item_type` — "potion", "scroll", "food"
- `heal_amount` or `spell_effect` — effect

### Quest items
- `item_type` — "quest"
- `quest_id` — string linking to quest chain

### Containers
- `item_type` — "container"
- `capacity` — int, max weight it can hold

---

## 4. Batch Zone File Conventions

Zones live in `world/batch_zones/*.ev`. Use these batch commands:

- `dig <room key>` — create a room (or move into it if it exists)
- `@desc <text>` — set room description (applies to current room)
- `@open <exitname>=<key> to <destination key>` — create a two-way exit
- `@spawn <prototype>` — spawn an object from a prototype
- `@tel here` — teleport the last spawned object to the current room
- `@tags/set room-zone:<name>` — tag a room with its zone

**Important:** `dig` uses a room's key for lookups. Use the same key
consistently when linking exits.

---

## 5. Validation

Run the validation script after editing any `.ev` file:

```python
# in evennia shell
from world.validate_batch_zones import validate_all_zones
validate_all_zones()
```

It checks that:
- Every `@open` destination has a matching `dig` room
- Every `@spawn` prototype is defined
- Rooms referenced by exits exist