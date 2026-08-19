"""
Phase 6 — MOB_PROTOTYPES and ITEM_PROTOTYPES for Rites of Passage.

All batch zone ``@spawn`` references are backed by entries here so that
``MobSpawner``, ``ShopkeeperNPC.buy_item()``, and the ``CmdSpawn`` admin
command can create objects at runtime.

Two registries are exported:

    - MOB_PROTOTYPES   — tutorial NPCs, guildmasters, guards, and spawners
    - ITEM_PROTOTYPES  — shop inventory items (weapons, armor, potions, etc.)
"""

MOB_PROTOTYPES: dict = {}
ITEM_PROTOTYPES: dict = {}


# ============================================================================
# Helper factories
# ============================================================================

def _mob(**kwargs):
    """Return a prototype dict for a character-type mob."""
    proto = {"typeclass": "typeclasses.characters.Character", **kwargs}
    # Ensure attributes list exists
    if "attrs" not in proto:
        proto["attrs"] = []
    return proto


def _npc(**kwargs):
    """Return a prototype dict for a generic NPC (also Character-based)."""
    return _mob(**kwargs)


def _guildmaster(**kwargs):
    """Return a prototype dict for a GuildmasterNPC."""
    return {"typeclass": "world.guildmaster.GuildmasterNPC", **kwargs}


def _shopkeeper(**kwargs):
    """Return a prototype dict for a ShopkeeperNPC."""
    return {"typeclass": "world.shopkeeper.ShopkeeperNPC", **kwargs}


def _spawner(**kwargs):
    """Return a prototype dict for a MobSpawner."""
    return {"typeclass": "typeclasses.objects.MobSpawner", **kwargs}


def _item(**kwargs):
    """Return a prototype dict for an inventory item."""
    return {"typeclass": "typeclasses.objects.Object", **kwargs}


# ============================================================================
# ITEM_PROTOTYPES — Shop inventory items bought by players
# ============================================================================

# ----- Weapons -----
ITEM_PROTOTYPES["iron_sword"] = _item(
    key="Iron Longsword",
    attrs=[
        ("item_type", "weapon_sword"),
        ("slot", "main_hand"),
        ("weight", 5.0),
        ("value", 50),
        ("durability", 100),
        ("max_durability", 100),
        ("damage", 8),
        ("damage_type", "slash"),
    ],
)

ITEM_PROTOTYPES["iron_mace"] = _item(
    key="Blessed Practice Mace",
    attrs=[
        ("item_type", "weapon_mace"),
        ("slot", "main_hand"),
        ("weight", 6.0),
        ("value", 45),
        ("durability", 100),
        ("max_durability", 100),
        ("damage", 7),
        ("damage_type", "blunt"),
    ],
)

ITEM_PROTOTYPES["oak_staff"] = _item(
    key="Oak Quarterstaff",
    attrs=[
        ("item_type", "weapon_staff"),
        ("slot", "two_hand"),
        ("weight", 4.0),
        ("value", 30),
        ("durability", 80),
        ("max_durability", 80),
        ("damage", 5),
        ("damage_type", "blunt"),
    ],
)

ITEM_PROTOTYPES["iron_dagger"] = _item(
    key="Worn Iron Dagger",
    attrs=[
        ("item_type", "weapon_dagger"),
        ("slot", "main_hand"),
        ("weight", 2.0),
        ("value", 35),
        ("durability", 90),
        ("max_durability", 90),
        ("damage", 5),
        ("damage_type", "pierce"),
    ],
)

ITEM_PROTOTYPES["hunting_bow"] = _item(
    key="Short Hunting Bow",
    attrs=[
        ("item_type", "weapon_bow"),
        ("slot", "ranged"),
        ("weight", 3.0),
        ("value", 55),
        ("durability", 80),
        ("max_durability", 80),
        ("damage", 7),
        ("damage_type", "pierce"),
    ],
)

ITEM_PROTOTYPES["demon_blade"] = _item(
    key="Demon-Forged Blade",
    attrs=[
        ("item_type", "weapon_sword"),
        ("slot", "main_hand"),
        ("weight", 6.0),
        ("value", 150),
        ("durability", 120),
        ("max_durability", 120),
        ("damage", 12),
        ("damage_type", "slash"),
        ("stat_bonuses", {"str": 1}),
    ],
)

ITEM_PROTOTYPES["shadow_staff"] = _item(
    key="Shadow Staff",
    attrs=[
        ("item_type", "weapon_staff"),
        ("slot", "two_hand"),
        ("weight", 4.0),
        ("value", 100),
        ("durability", 90),
        ("max_durability", 90),
        ("damage", 7),
        ("damage_type", "magic_shadow"),
        ("stat_bonuses", {"int": 1}),
    ],
)

# ----- Armor -----
ITEM_PROTOTYPES["leather_armor"] = _item(
    key="Patched Leather Armor",
    attrs=[
        ("item_type", "armor_light"),
        ("slot", "chest"),
        ("weight", 8.0),
        ("value", 35),
        ("durability", 100),
        ("max_durability", 100),
        ("armor", 3),
    ],
)

ITEM_PROTOTYPES["chainmail"] = _item(
    key="Initiate Chainmail",
    attrs=[
        ("item_type", "armor_medium"),
        ("slot", "chest"),
        ("weight", 15.0),
        ("value", 80),
        ("durability", 120),
        ("max_durability", 120),
        ("armor", 5),
    ],
)

ITEM_PROTOTYPES["cloth_robes"] = _item(
    key="Simple Cloth Robes",
    attrs=[
        ("item_type", "armor_cloth"),
        ("slot", "chest"),
        ("weight", 3.0),
        ("value", 10),
        ("durability", 70),
        ("max_durability", 70),
        ("armor", 1),
    ],
)

ITEM_PROTOTYPES["wooden_shield"] = _item(
    key="Wooden Shield",
    attrs=[
        ("item_type", "armor_medium"),
        ("slot", "off_hand"),
        ("weight", 10.0),
        ("value", 30),
        ("durability", 90),
        ("max_durability", 90),
        ("armor", 4),
    ],
)

ITEM_PROTOTYPES["obsidian_plate"] = _item(
    key="Obsidian Plate",
    attrs=[
        ("item_type", "armor_heavy"),
        ("slot", "chest"),
        ("weight", 25.0),
        ("value", 150),
        ("durability", 150),
        ("max_durability", 150),
        ("armor", 9),
        ("magic_resist", 5),
    ],
)

# ----- Consumables -----
ITEM_PROTOTYPES["health_potion"] = _item(
    key="Health Potion",
    attrs=[
        ("item_type", "potion"),
        ("weight", 0.5),
        ("value", 25),
        ("durability", 1),
        ("max_durability", 1),
        ("heal_amount", 30),
    ],
)

ITEM_PROTOTYPES["mana_potion"] = _item(
    key="Mana Potion",
    attrs=[
        ("item_type", "potion"),
        ("weight", 0.5),
        ("value", 25),
        ("durability", 1),
        ("max_durability", 1),
        ("mana_restore", 25),
    ],
)

ITEM_PROTOTYPES["blood_elixir"] = _item(
    key="Blood Elixir",
    attrs=[
        ("item_type", "potion"),
        ("weight", 0.5),
        ("value", 45),
        ("durability", 1),
        ("max_durability", 1),
        ("heal_amount", 50),
    ],
)

ITEM_PROTOTYPES["travel_rations"] = _item(
    key="Travel Rations",
    attrs=[
        ("item_type", "food"),
        ("weight", 2.0),
        ("value", 5),
        ("durability", 1),
        ("max_durability", 1),
    ],
)


# ============================================================================
# MOB_PROTOTYPES — Characters, NPCs, spawners
# ============================================================================

# ---------------------------------------------------------------------------
# AETHELGARD TOWN (Good)
# ---------------------------------------------------------------------------

MOB_PROTOTYPES["tutorial_guide"] = _npc(
    key="Tutorial Guide",
    attrs=[
        ("is_npc", True),
        ("is_mob", False),
        ("level", 50),
        ("alignment", "Good"),
        ("faction", "good"),
    ],
)

MOB_PROTOTYPES["paladin_guildmaster"] = _guildmaster(
    key="Sir Aldric the Pure",
    attrs=[
        ("is_npc", True),
        ("guild_class", "Paladin"),
        ("alignment", "Good"),
        ("faction", "good"),
    ],
)

MOB_PROTOTYPES["cleric_guildmaster"] = _guildmaster(
    key="High Priestess Seraphina",
    attrs=[
        ("is_npc", True),
        ("guild_class", "Cleric"),
        ("alignment", "Good"),
        ("faction", "good"),
    ],
)

MOB_PROTOTYPES["mage_guildmaster"] = _guildmaster(
    key="Archmage Merdion",
    attrs=[
        ("is_npc", True),
        ("guild_class", "Mage"),
        ("alignment", "Good"),
        ("faction", "good"),
    ],
)

MOB_PROTOTYPES["general_shopkeeper"] = _shopkeeper(
    key="Marta the Peddler",
    attrs=[
        ("is_npc", True),
        ("is_vendor", True),
        ("shop_type", "general"),
        ("shop_buy_mult", 0.50),
        ("shop_sell_mult", 1.20),
        ("alignment", "Good"),
        ("shop_inventory", [
            {"item_key": "travel_rations", "price": 5, "quantity": 20},
            {"item_key": "iron_dagger", "price": 40, "quantity": 5},
            {"item_key": "health_potion", "price": 30, "quantity": 10},
            {"item_key": "mana_potion", "price": 30, "quantity": 10},
        ]),
    ],
)

MOB_PROTOTYPES["weaponsmith_shopkeeper"] = _shopkeeper(
    key="Thoren Ironhand",
    attrs=[
        ("is_npc", True),
        ("is_vendor", True),
        ("shop_type", "weapons"),
        ("shop_buy_mult", 0.45),
        ("shop_sell_mult", 1.25),
        ("alignment", "Good"),
        ("shop_inventory", [
            {"item_key": "iron_sword", "price": 55, "quantity": 5},
            {"item_key": "iron_mace", "price": 50, "quantity": 5},
            {"item_key": "hunting_bow", "price": 60, "quantity": 3},
            {"item_key": "oak_staff", "price": 35, "quantity": 5},
            {"item_key": "iron_dagger", "price": 40, "quantity": 8},
        ]),
    ],
)

MOB_PROTOTYPES["armorer_shopkeeper"] = _shopkeeper(
    key="Brynn Shield-Wright",
    attrs=[
        ("is_npc", True),
        ("is_vendor", True),
        ("shop_type", "armor"),
        ("shop_buy_mult", 0.45),
        ("shop_sell_mult", 1.25),
        ("alignment", "Good"),
        ("shop_inventory", [
            {"item_key": "leather_armor", "price": 40, "quantity": 5},
            {"item_key": "chainmail", "price": 90, "quantity": 3},
            {"item_key": "cloth_robes", "price": 15, "quantity": 5},
            {"item_key": "wooden_shield", "price": 35, "quantity": 5},
        ]),
    ],
)

MOB_PROTOTYPES["potion_shopkeeper"] = _shopkeeper(
    key="Elara Duskbrew",
    attrs=[
        ("is_npc", True),
        ("is_vendor", True),
        ("shop_type", "potions"),
        ("shop_buy_mult", 0.40),
        ("shop_sell_mult", 1.30),
        ("alignment", "Good"),
        ("shop_inventory", [
            {"item_key": "health_potion", "price": 30, "quantity": 15},
            {"item_key": "mana_potion", "price": 30, "quantity": 15},
        ]),
    ],
)

MOB_PROTOTYPES["good_city_guard"] = _mob(
    key="Aethelgard Guard",
    attrs=[
        ("is_npc", True),
        ("is_mob", True),
        ("level", 25),
        ("stats", {"str": 16, "dex": 14, "con": 15, "int": 10, "wis": 12, "cha": 10}),
        ("hp", 200),
        ("max_hp", 200),
        ("alignment", "Good"),
        ("faction", "good"),
        ("xp_value", 150),
        ("gold_min", 10),
        ("gold_max", 30),
        ("damage_type", "slash"),
        ("loot_table", [
            {"item_key": "iron_sword", "weight": 0.15, "min_qty": 1, "max_qty": 1},
            {"item_key": "chainmail", "weight": 0.10, "min_qty": 1, "max_qty": 1},
            {"item_key": "health_potion", "weight": 0.20, "min_qty": 1, "max_qty": 2},
        ]),
    ],
)

# ---------------------------------------------------------------------------
# GORGOROTH TOWN (Evil)
# ---------------------------------------------------------------------------

MOB_PROTOTYPES["dark_tutorial_guide"] = _npc(
    key="Dark Tutor",
    attrs=[
        ("is_npc", True),
        ("is_mob", False),
        ("level", 50),
        ("alignment", "Evil"),
        ("faction", "evil"),
    ],
)

MOB_PROTOTYPES["warrior_guildmaster"] = _guildmaster(
    key="Warmaster Gorath",
    attrs=[
        ("is_npc", True),
        ("guild_class", "Warrior"),
        ("alignment", "Evil"),
        ("faction", "evil"),
    ],
)

MOB_PROTOTYPES["warlock_guildmaster"] = _guildmaster(
    key="Cult-Mistress Vexia",
    attrs=[
        ("is_npc", True),
        ("guild_class", "Warlock"),
        ("alignment", "Evil"),
        ("faction", "evil"),
    ],
)

MOB_PROTOTYPES["necromancer_guildmaster"] = _guildmaster(
    key="Bone-Lord Morath",
    attrs=[
        ("is_npc", True),
        ("guild_class", "Necromancer"),
        ("alignment", "Evil"),
        ("faction", "evil"),
    ],
)

MOB_PROTOTYPES["evil_general_shopkeeper"] = _shopkeeper(
    key="Grimm the Scavenger",
    attrs=[
        ("is_npc", True),
        ("is_vendor", True),
        ("shop_type", "general"),
        ("shop_buy_mult", 0.50),
        ("shop_sell_mult", 1.20),
        ("alignment", "Evil"),
        ("shop_inventory", [
            {"item_key": "travel_rations", "price": 5, "quantity": 20},
            {"item_key": "iron_dagger", "price": 40, "quantity": 5},
            {"item_key": "blood_elixir", "price": 50, "quantity": 8},
            {"item_key": "health_potion", "price": 30, "quantity": 10},
        ]),
    ],
)

MOB_PROTOTYPES["evil_weaponsmith_shopkeeper"] = _shopkeeper(
    key="Razgor Steel-Biter",
    attrs=[
        ("is_npc", True),
        ("is_vendor", True),
        ("shop_type", "weapons"),
        ("shop_buy_mult", 0.45),
        ("shop_sell_mult", 1.25),
        ("alignment", "Evil"),
        ("shop_inventory", [
            {"item_key": "demon_blade", "price": 160, "quantity": 3},
            {"item_key": "shadow_staff", "price": 110, "quantity": 3},
            {"item_key": "iron_sword", "price": 55, "quantity": 5},
            {"item_key": "iron_dagger", "price": 40, "quantity": 8},
        ]),
    ],
)

MOB_PROTOTYPES["evil_armorer_shopkeeper"] = _shopkeeper(
    key="Borgath the Iron",
    attrs=[
        ("is_npc", True),
        ("is_vendor", True),
        ("shop_type", "armor"),
        ("shop_buy_mult", 0.45),
        ("shop_sell_mult", 1.25),
        ("alignment", "Evil"),
        ("shop_inventory", [
            {"item_key": "obsidian_plate", "price": 160, "quantity": 2},
            {"item_key": "chainmail", "price": 90, "quantity": 3},
            {"item_key": "leather_armor", "price": 40, "quantity": 5},
            {"item_key": "wooden_shield", "price": 35, "quantity": 5},
        ]),
    ],
)

MOB_PROTOTYPES["evil_potion_shopkeeper"] = _shopkeeper(
    key="Sythra Venom-Drip",
    attrs=[
        ("is_npc", True),
        ("is_vendor", True),
        ("shop_type", "potions"),
        ("shop_buy_mult", 0.40),
        ("shop_sell_mult", 1.30),
        ("alignment", "Evil"),
        ("shop_inventory", [
            {"item_key": "health_potion", "price": 30, "quantity": 15},
            {"item_key": "blood_elixir", "price": 50, "quantity": 10},
        ]),
    ],
)

MOB_PROTOTYPES["evil_city_guard"] = _mob(
    key="Gorgoroth Sentinel",
    attrs=[
        ("is_npc", True),
        ("is_mob", True),
        ("level", 25),
        ("stats", {"str": 16, "dex": 12, "con": 16, "int": 8, "wis": 10, "cha": 6}),
        ("hp", 220),
        ("max_hp", 220),
        ("alignment", "Evil"),
        ("faction", "evil"),
        ("xp_value", 150),
        ("gold_min", 10),
        ("gold_max", 30),
        ("damage_type", "blunt"),
        ("loot_table", [
            {"item_key": "iron_mace", "weight": 0.15, "min_qty": 1, "max_qty": 1},
            {"item_key": "obsidian_plate", "weight": 0.08, "min_qty": 1, "max_qty": 1},
            {"item_key": "blood_elixir", "weight": 0.20, "min_qty": 1, "max_qty": 2},
        ]),
    ],
)

# ---------------------------------------------------------------------------
# NEWBIE ZONE (Levels 1-5)
# ---------------------------------------------------------------------------

MOB_PROTOTYPES["newbie_quest_npc"] = _npc(
    key="Old Trapper",
    attrs=[
        ("is_npc", True),
        ("is_mob", False),
        ("level", 5),
        ("alignment", "Neutral"),
        ("faction", "neutral"),
    ],
)

# Spawner for passive rabbits
MOB_PROTOTYPES["rabbit_spawner"] = _spawner(
    key="Rabbit Meadow Spawner",
    attrs=[
        ("prototype", "rabbit"),
        ("max_spawned", 5),
        ("respawn_delay", 30),
    ],
)

# Spawner for goblin scouts
MOB_PROTOTYPES["goblin_scout_spawner"] = _spawner(
    key="Goblin Scout Spawner",
    attrs=[
        ("prototype", "goblin_scout"),
        ("max_spawned", 4),
        ("respawn_delay", 30),
    ],
)

# Actual mobs spawned by the spawners
MOB_PROTOTYPES["rabbit"] = _mob(
    key="rabbit",
    attrs=[
        ("is_mob", True),
        ("level", 1),
        ("stats", {"str": 3, "dex": 16, "con": 5, "int": 2, "wis": 4, "cha": 3}),
        ("hp", 8),
        ("max_hp", 8),
        ("alignment", "Neutral"),
        ("faction", "neutral"),
        ("xp_value", 3),
        ("gold_min", 0),
        ("gold_max", 1),
        ("damage_type", "blunt"),
        ("loot_table", [
            {"item_key": "travel_rations", "weight": 0.30, "min_qty": 1, "max_qty": 1},
        ]),
    ],
)

MOB_PROTOTYPES["goblin_scout"] = _mob(
    key="goblin scout",
    attrs=[
        ("is_mob", True),
        ("level", 2),
        ("stats", {"str": 8, "dex": 12, "con": 9, "int": 7, "wis": 6, "cha": 4}),
        ("hp", 22),
        ("max_hp", 22),
        ("alignment", "Evil"),
        ("faction", "evil"),
        ("xp_value", 18),
        ("gold_min", 2),
        ("gold_max", 5),
        ("damage_type", "pierce"),
        ("loot_table", [
            {"item_key": "iron_dagger", "weight": 0.15, "min_qty": 1, "max_qty": 1},
            {"item_key": "cloth_robes", "weight": 0.10, "min_qty": 1, "max_qty": 1},
            {"item_key": "travel_rations", "weight": 0.25, "min_qty": 1, "max_qty": 1},
        ]),
    ],
)

# ---------------------------------------------------------------------------
# DARKWOOD FOREST (Levels 5-15)
# ---------------------------------------------------------------------------

MOB_PROTOTYPES["wolf_pack_spawner"] = _spawner(
    key="Wolf Pack Spawner",
    attrs=[
        ("prototype", "darkwood_wolf"),
        ("max_spawned", 4),
        ("respawn_delay", 45),
    ],
)

MOB_PROTOTYPES["darkwood_wolf"] = _mob(
    key="timber wolf",
    attrs=[
        ("is_mob", True),
        ("level", 6),
        ("stats", {"str": 12, "dex": 15, "con": 10, "int": 3, "wis": 5, "cha": 4}),
        ("hp", 55),
        ("max_hp", 55),
        ("alignment", "Neutral"),
        ("faction", "neutral"),
        ("xp_value", 50),
        ("gold_min", 0),
        ("gold_max", 3),
        ("damage_type", "pierce"),
        ("loot_table", [
            {"item_key": "travel_rations", "weight": 0.35, "min_qty": 1, "max_qty": 2},
        ]),
    ],
)

MOB_PROTOTYPES["shadow_alpha_wolf"] = _mob(
    key="Shadow Alpha Wolf",
    attrs=[
        ("is_mob", True),
        ("is_boss", True),
        ("level", 15),
        ("stats", {"str": 18, "dex": 20, "con": 16, "int": 6, "wis": 8, "cha": 5}),
        ("hp", 350),
        ("max_hp", 350),
        ("alignment", "Evil"),
        ("faction", "evil"),
        ("xp_value", 600),
        ("gold_min", 30),
        ("gold_max", 60),
        ("damage_type", "slash"),
        ("loot_table", [
            {"item_key": "leather_armor", "weight": 0.30, "min_qty": 1, "max_qty": 1},
            {"item_key": "health_potion", "weight": 0.40, "min_qty": 1, "max_qty": 3},
            {"item_key": "iron_sword", "weight": 0.15, "min_qty": 1, "max_qty": 1},
        ]),
    ],
)

MOB_PROTOTYPES["bandit_spawner"] = _spawner(
    key="Bandit Camp Spawner",
    attrs=[
        ("prototype", "bandit"),
        ("max_spawned", 4),
        ("respawn_delay", 45),
    ],
)

MOB_PROTOTYPES["bandit"] = _mob(
    key="bandit",
    attrs=[
        ("is_mob", True),
        ("level", 8),
        ("stats", {"str": 13, "dex": 12, "con": 12, "int": 9, "wis": 8, "cha": 7}),
        ("hp", 80),
        ("max_hp", 80),
        ("alignment", "Evil"),
        ("faction", "evil"),
        ("xp_value", 90),
        ("gold_min", 5),
        ("gold_max", 15),
        ("damage_type", "slash"),
        ("loot_table", [
            {"item_key": "iron_dagger", "weight": 0.20, "min_qty": 1, "max_qty": 1},
            {"item_key": "leather_armor", "weight": 0.15, "min_qty": 1, "max_qty": 1},
            {"item_key": "health_potion", "weight": 0.15, "min_qty": 1, "max_qty": 1},
            {"item_key": "travel_rations", "weight": 0.25, "min_qty": 1, "max_qty": 2},
        ]),
    ],
)

MOB_PROTOTYPES["bandit_chief"] = _mob(
    key="Bandit Chief",
    attrs=[
        ("is_mob", True),
        ("is_boss", True),
        ("level", 12),
        ("stats", {"str": 16, "dex": 14, "con": 15, "int": 11, "wis": 10, "cha": 12}),
        ("hp", 280),
        ("max_hp", 280),
        ("alignment", "Evil"),
        ("faction", "evil"),
        ("xp_value", 400),
        ("gold_min", 40),
        ("gold_max", 80),
        ("damage_type", "slash"),
        ("loot_table", [
            {"item_key": "iron_sword", "weight": 0.40, "min_qty": 1, "max_qty": 1},
            {"item_key": "chainmail", "weight": 0.30, "min_qty": 1, "max_qty": 1},
            {"item_key": "health_potion", "weight": 0.50, "min_qty": 2, "max_qty": 4},
            {"item_key": "wooden_shield", "weight": 0.25, "min_qty": 1, "max_qty": 1},
        ]),
    ],
)

MOB_PROTOTYPES["giant_spider_spawner"] = _spawner(
    key="Giant Spider Spawner",
    attrs=[
        ("prototype", "giant_spider"),
        ("max_spawned", 3),
        ("respawn_delay", 45),
    ],
)

MOB_PROTOTYPES["giant_spider"] = _mob(
    key="giant spider",
    attrs=[
        ("is_mob", True),
        ("level", 9),
        ("stats", {"str": 10, "dex": 17, "con": 11, "int": 2, "wis": 4, "cha": 2}),
        ("hp", 85),
        ("max_hp", 85),
        ("alignment", "Neutral"),
        ("faction", "neutral"),
        ("xp_value", 100),
        ("gold_min", 0),
        ("gold_max", 8),
        ("damage_type", "pierce"),
        ("poison_on_hit", True),
        ("loot_table", [
            {"item_key": "health_potion", "weight": 0.15, "min_qty": 1, "max_qty": 1},
        ]),
    ],
)

MOB_PROTOTYPES["dark_cultist_spawner"] = _spawner(
    key="Dark Cultist Spawner",
    attrs=[
        ("prototype", "dark_cultist"),
        ("max_spawned", 3),
        ("respawn_delay", 45),
    ],
)

MOB_PROTOTYPES["dark_cultist"] = _mob(
    key="dark cultist",
    attrs=[
        ("is_mob", True),
        ("level", 11),
        ("stats", {"str": 9, "dex": 11, "con": 10, "int": 16, "wis": 14, "cha": 6}),
        ("hp", 95),
        ("max_hp", 95),
        ("mana", 80),
        ("max_mana", 80),
        ("alignment", "Evil"),
        ("faction", "evil"),
        ("xp_value", 160),
        ("gold_min", 8),
        ("gold_max", 20),
        ("damage_type", "magic_shadow"),
        ("spells", ["shadows"]),
        ("loot_table", [
            {"item_key": "shadow_staff", "weight": 0.10, "min_qty": 1, "max_qty": 1},
            {"item_key": "cloth_robes", "weight": 0.25, "min_qty": 1, "max_qty": 1},
            {"item_key": "mana_potion", "weight": 0.30, "min_qty": 1, "max_qty": 2},
            {"item_key": "blood_elixir", "weight": 0.15, "min_qty": 1, "max_qty": 1},
        ]),
    ],
)

# ---------------------------------------------------------------------------
# HIGH-LEVEL ZONES (Levels 15-80)
# ---------------------------------------------------------------------------

MOB_PROTOTYPES["crimson_warlord"] = _mob(
    key="Crimson Warlord",
    attrs=[
        ("is_mob", True),
        ("is_boss", True),
        ("level", 30),
        ("stats", {"str": 22, "dex": 18, "con": 20, "int": 14, "wis": 14, "cha": 16}),
        ("hp", 1500),
        ("max_hp", 1500),
        ("alignment", "Evil"),
        ("faction", "evil"),
        ("xp_value", 3000),
        ("gold_min", 200),
        ("gold_max", 500),
        ("damage_type", "slash"),
        ("loot_table", [
            {"item_key": "demon_blade", "weight": 0.35, "min_qty": 1, "max_qty": 1},
            {"item_key": "obsidian_plate", "weight": 0.30, "min_qty": 1, "max_qty": 1},
            {"item_key": "health_potion", "weight": 0.60, "min_qty": 3, "max_qty": 6},
            {"item_key": "blood_elixir", "weight": 0.40, "min_qty": 2, "max_qty": 4},
        ]),
    ],
)

MOB_PROTOTYPES["frost_giant_spawner"] = _spawner(
    key="Frost Giant Spawner",
    attrs=[
        ("prototype", "frost_giant"),
        ("max_spawned", 2),
        ("respawn_delay", 60),
    ],
)

MOB_PROTOTYPES["frost_giant"] = _mob(
    key="frost giant",
    attrs=[
        ("is_mob", True),
        ("level", 40),
        ("stats", {"str": 26, "dex": 10, "con": 24, "int": 9, "wis": 12, "cha": 8}),
        ("hp", 2500),
        ("max_hp", 2500),
        ("alignment", "Evil"),
        ("faction", "evil"),
        ("xp_value", 6000),
        ("gold_min", 100),
        ("gold_max", 300),
        ("damage_type", "blunt"),
        ("loot_table", [
            {"item_key": "iron_mace", "weight": 0.25, "min_qty": 1, "max_qty": 1},
            {"item_key": "chainmail", "weight": 0.20, "min_qty": 1, "max_qty": 1},
            {"item_key": "health_potion", "weight": 0.40, "min_qty": 2, "max_qty": 5},
            {"item_key": "travel_rations", "weight": 0.30, "min_qty": 2, "max_qty": 4},
        ]),
    ],
)

MOB_PROTOTYPES["nether_overlord"] = _mob(
    key="Nether Overlord",
    attrs=[
        ("is_mob", True),
        ("is_boss", True),
        ("level", 80),
        ("stats", {"str": 30, "dex": 22, "con": 28, "int": 26, "wis": 24, "cha": 20}),
        ("hp", 15000),
        ("max_hp", 15000),
        ("mana", 3000),
        ("max_mana", 3000),
        ("alignment", "Evil"),
        ("faction", "evil"),
        ("xp_value", 50000),
        ("gold_min", 2000),
        ("gold_max", 10000),
        ("damage_type", "magic_fire"),
        ("spells", ["fireball", "blight"]),
        ("loot_table", [
            {"item_key": "demon_blade", "weight": 0.50, "min_qty": 1, "max_qty": 1},
            {"item_key": "shadow_staff", "weight": 0.50, "min_qty": 1, "max_qty": 1},
            {"item_key": "obsidian_plate", "weight": 0.40, "min_qty": 1, "max_qty": 1},
            {"item_key": "health_potion", "weight": 0.80, "min_qty": 5, "max_qty": 10},
            {"item_key": "blood_elixir", "weight": 0.60, "min_qty": 3, "max_qty": 8},
            {"item_key": "mana_potion", "weight": 0.50, "min_qty": 3, "max_qty": 6},
        ]),
    ],
)
