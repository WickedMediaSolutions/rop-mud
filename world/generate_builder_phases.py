import os

os.makedirs("world", exist_ok=True)

# =====================================================================
# PHASE 1: Room Objects & Tagged Instantiation
# =====================================================================
phase1_code = '''# world/builder_phase1.py
from evennia import create_object, search_tag

EVIL_TOWNS = [
    ("duradune", "Duradune (The Desert Gate)"),
    ("freshwater_springs", "Freshwater Springs"),
    ("drow_city", "Drow Caverns City"),
    ("brimstone_keep", "Brimstone Keep (Starter Hub)"),
    ("gloomhold", "Gloomhold"),
    ("rotwood_enclave", "Rotwood Enclave"),
    ("blight_hollow", "Blight-Hollow"),
    ("ashen_outpost", "Ashen Outpost"),
    ("sorrows_reach", "Sorrow's Reach"),
    ("blood_forge", "The Blood-Forge Citadel"),
    ("malice_bay", "Malice Bay"),
    ("vile_grave", "Vile-Grave Necropolis"),
    ("hellfire_spire", "Hellfire Spire")
]

EVIL_ZONES = {
    "brimstone_courtyard": {"name": "Brimstone Courtyard (Starter 1-10)", "count": 150, "color": "|r", "level_range": (1, 10), "aggro": False},
    "the_junction": {"name": "The Junction of Great Paths", "count": 200, "color": "|R", "level_range": (10, 18), "aggro": True},
    "verdant_mire": {"name": "Verdant Mire Swamp", "count": 350, "color": "|g", "level_range": (15, 25), "aggro": True},
    "obsidian_ridge": {"name": "The Obsidian Ridge", "count": 250, "color": "|x", "level_range": (20, 30), "aggro": True},
    "drow_caverns_sub": {"name": "Drow Caverns Sub-Level", "count": 400, "color": "|M", "level_range": (30, 45), "aggro": True},
    "rotwood_forest": {"name": "Rotwood Forest", "count": 300, "color": "|G", "level_range": (18, 28), "aggro": True},
    "blighted_chasm": {"name": "The Blighted Chasm", "count": 250, "color": "|r", "level_range": (25, 35), "aggro": True},
    "screaming_canyons": {"name": "Screaming Canyons", "count": 200, "color": "|Y", "level_range": (22, 32), "aggro": True},
    "ashen_wastes": {"name": "Ashen Wastes", "count": 300, "color": "|w", "level_range": (28, 38), "aggro": True},
    "blood_river_delta": {"name": "Blood-River Delta", "count": 300, "color": "|R", "level_range": (30, 40), "aggro": True},
    "bone_fields": {"name": "The Bone Fields", "count": 250, "color": "|W", "level_range": (32, 42), "aggro": True},
    "dread_valley": {"name": "Dread Valley", "count": 250, "color": "|m", "level_range": (35, 45), "aggro": True},
    "vile_grounds": {"name": "Vile Necropolis Grounds", "count": 350, "color": "|x", "level_range": (40, 50), "aggro": True},
    "desolation_pass": {"name": "Desolation Pass", "count": 200, "color": "|r", "level_range": (38, 48), "aggro": True},
    "under_tunnels": {"name": "Under-Tunnels Maze", "count": 300, "color": "|M", "level_range": (25, 40), "aggro": True}
}

GOOD_TOWNS = [
    ("adaar", "Adaar Haven (The Desert Gate)"),
    ("havencrest", "Havencrest"),
    ("sunspire_keep", "Sunspire Keep (Starter Hub)"),
    ("silverwood_village", "Silverwood Village"),
    ("oakhaven", "Oakhaven"),
    ("stoneguard_hold", "Stoneguard Hold"),
    ("dawn_light_bay", "Dawn-Light Bay"),
    ("riverbend", "Riverbend"),
    ("high_meadow", "High-Meadow"),
    ("astraea", "Astraea Sanctuary"),
    ("eldergrove_town", "Eldergrove"),
    ("vales_end", "Vales-End"),
    ("iron_watch", "Iron-Watch Castle")
]

GOOD_ZONES = {
    "sunspire_meadows": {"name": "Sunspire Meadows (Starter 1-10)", "count": 150, "color": "|Y", "level_range": (1, 10), "aggro": False},
    "the_crossroads": {"name": "The Crossroads of Light", "count": 200, "color": "|W", "level_range": (10, 18), "aggro": True},
    "whispering_ridge": {"name": "Whispering Ridge Hills", "count": 350, "color": "|g", "level_range": (15, 25), "aggro": True},
    "silverwood_forest": {"name": "Silverwood Forest", "count": 300, "color": "|G", "level_range": (18, 28), "aggro": True},
    "stoneguard_mines": {"name": "Stoneguard Mines", "count": 400, "color": "|y", "level_range": (30, 45), "aggro": True},
    "golden_plains": {"name": "Golden Plains", "count": 300, "color": "|Y", "level_range": (20, 30), "aggro": True},
    "sunken_valley": {"name": "The Sunken Valley", "count": 250, "color": "|c", "level_range": (22, 32), "aggro": True},
    "mist_veiled_woods": {"name": "Mist-Veiled Woods", "count": 250, "color": "|C", "level_range": (25, 35), "aggro": True},
    "eldergrove_thicket": {"name": "Eldergrove Thicket", "count": 300, "color": "|g", "level_range": (28, 38), "aggro": True},
    "echoing_caverns": {"name": "Echoing Caverns", "count": 250, "color": "|w", "level_range": (30, 40), "aggro": True},
    "highland_pass": {"name": "Highland Pass", "count": 200, "color": "|W", "level_range": (32, 42), "aggro": True},
    "dawn_light_coast": {"name": "Dawn-Light Coast", "count": 250, "color": "|B", "level_range": (35, 45), "aggro": True},
    "astraea_ruins": {"name": "Astraea Holy Ruins", "count": 350, "color": "|C", "level_range": (40, 50), "aggro": True},
    "serpent_river": {"name": "Serpent River Path", "count": 200, "color": "|b", "level_range": (25, 35), "aggro": True},
    "iron_pass_ridge": {"name": "Iron-Pass Ridge", "count": 300, "color": "|w", "level_range": (38, 48), "aggro": True}
}

NEUTRAL_ZONES = {
    "great_sun_wastes": {"name": "Great Sun Wastes (Desert)", "count": 2500, "color": "|y", "level_range": (25, 40), "aggro": True},
    "northern_ancient_forest": {"name": "Northern Ancient Forest", "count": 1500, "color": "|G", "level_range": (20, 35), "aggro": True},
    "south_shore": {"name": "South Shore Coastal Wastes", "count": 1500, "color": "|B", "level_range": (35, 50), "aggro": True}
}

ALL_ZONES = {**EVIL_ZONES, **GOOD_ZONES, **NEUTRAL_ZONES}

def get_or_create_room(key, room_id, zone, desc=""):
    existing = search_tag(room_id, category="room_id")
    if existing:
        room = existing[0]
        room.db.desc = desc
        return room
    
    room = create_object("typeclasses.rooms.Room", key=key)
    room.tags.add(room_id, category="room_id")
    room.tags.add(zone, category="zone")
    room.db.desc = desc
    return room


def _clean_zone_name(raw_name: str) -> str:
    """Strip debug suffixes from zone names."""
    import re
    clean = re.sub(
        r"\\s*\\((?:\s*(?:Starter|Tier|Levels?|Lvl|Zone)\s*[,\d\s\-]+)\\)",
        "",
        raw_name,
        flags=re.IGNORECASE,
    ).strip()
    return clean


def build_phase1():
    print("[Phase 1] Instantiating room skeletons across East/West realms & Neutral Desert...")
    total_created = 0
    for zone_key, data in ALL_ZONES.items():
        clean_name = _clean_zone_name(data["name"])
        print(f" -> Building {clean_name} ({data['count']} rooms)...")
        for i in range(1, data['count'] + 1):
            room_id = f"{zone_key}_{i}"
            # Use clean zone name — no debug suffixes in room titles.
            title = f"{data['color']}{clean_name}|n"
            desc = f"You are traveling through {clean_name}."
            get_or_create_room(title, room_id, zone_key, desc)
            total_created += 1
            
    print(f"[Phase 1 COMPLETE] Verified/created {total_created} room skeletons.")
'''

# =====================================================================
# PHASE 2: Symmetrical 10-Way Meandering Exit Topology
# =====================================================================
phase2_code = '''# world/builder_phase2.py
from evennia import create_object, search_tag

OPPOSITE_DIRECTIONS = {
    "n": "s", "s": "n", "e": "w", "w": "e",
    "ne": "sw", "sw": "ne", "nw": "se", "se": "nw",
    "u": "d", "d": "u"
}

def link_rooms_by_tag(source_id, target_id, direction):
    src_list = search_tag(source_id, category="room_id")
    tgt_list = search_tag(target_id, category="room_id")
    
    if not src_list or not tgt_list:
        return False
        
    src_room = src_list[0]
    tgt_room = tgt_list[0]
    opp_dir = OPPOSITE_DIRECTIONS.get(direction)
    
    if not src_room.search(direction, candidates=src_room.exits, quiet=True):
        create_object("typeclasses.exits.Exit", key=direction, location=src_room, destination=tgt_room)
        
    if opp_dir and not tgt_room.search(opp_dir, candidates=tgt_room.exits, quiet=True):
        create_object("typeclasses.exits.Exit", key=opp_dir, location=tgt_room, destination=src_room)
        
    return True

def build_phase2():
    print("[Phase 2] Linking meandering 10-way exit topologies & regional trade paths...")
    
    import world.builder_phase1 as p1
    linked_count = 0
    
    # 1. Meandering Grid Connections per zone (Non-linear winding)
    dirs = ["e", "se", "s", "sw", "w", "nw", "n", "ne"]
    for zone in p1.ALL_ZONES.keys():
        rooms = search_tag(zone, category="zone")
        count = len(rooms)
        for i in range(1, count):
            src_id = f"{zone}_{i}"
            tgt_id = f"{zone}_{i+1}"
            chosen_dir = dirs[i % len(dirs)]
            if link_rooms_by_tag(src_id, tgt_id, chosen_dir):
                linked_count += 1
                
    # 2. STRICT DESERT GATEWAY ACCESS
    # Evil Access: Duradune East Gate -> Great Sun Wastes
    link_rooms_by_tag("the_junction_1", "great_sun_wastes_1", "e")
    # Good Access: Adaar Haven West Gate -> Great Sun Wastes
    link_rooms_by_tag("the_crossroads_1", "great_sun_wastes_2500", "w")
    
    # 3. ANCIENT TRADE PATH (North Neutral Connector)
    # Freshwater Springs (Swamp/Evil) -> Northern Ancient Forest -> Havencrest (Hills/Good)
    link_rooms_by_tag("verdant_mire_350", "northern_ancient_forest_1", "n")
    link_rooms_by_tag("northern_ancient_forest_1500", "whispering_ridge_1", "e")
    
    # 4. SOUTH SHORE CONNECTORS
    # SW Evil Caverns -> South Shore -> SE Good Iron-Pass
    link_rooms_by_tag("desolation_pass_200", "south_shore_1", "s")
    link_rooms_by_tag("south_shore_1500", "iron_pass_ridge_300", "e")

    print(f"[Phase 2 COMPLETE] Linked {linked_count} meandering regional sections and major trade corridors.")
'''

# =====================================================================
# PHASE 3: Town Infrastructure, Vendors, Mobs, Equipment Drops & Bosses
# =====================================================================
phase3_code = '''# world/builder_phase3.py
from evennia import create_object, search_tag
import random

BOSS_LOOT_TABLES = {
    "lich_queen": [
        {"key": "Shadow-Woven Mantle", "type": "armor", "slot": "chest"},
        {"key": "Vampiric Blade", "type": "weapon", "slot": "wield"}
    ],
    "arch_fiend": [
        {"key": "Hellfire Aegis", "type": "armor", "slot": "shield"},
        {"key": "Infernal Soul Ring", "type": "ring", "slot": "finger"}
    ],
    "mountain_golem": [
        {"key": "Aegis of the Crag", "type": "armor", "slot": "shield"},
        {"key": "Granite Hammer", "type": "weapon", "slot": "wield"}
    ],
    "celestial_sentinel": [
        {"key": "Radiant Sun-Blade", "type": "weapon", "slot": "wield"},
        {"key": "Halo of Dawn", "type": "helm", "slot": "head"}
    ],
    "dune_stalker": [
        {"key": "Sand-Strider Boots", "type": "boots", "slot": "feet"},
        {"key": "Scimitar of the Sun", "type": "weapon", "slot": "wield"}
    ],
    "kraken_spawn": [
        {"key": "Tidal Wave Trident", "type": "weapon", "slot": "wield"},
        {"key": "Depth-Dweller Scale Mail", "type": "armor", "slot": "chest"}
    ]
}

def spawn_town_vendors(room, town_name):
    vendors = ["Banker", "Weapon Vendor", "Armor Vendor", "Food Vendor"]
    for v in vendors:
        v_key = f"{town_name} {v}"
        if not room.search(v_key, quiet=True):
            npc = create_object("typeclasses.objects.Object", key=v_key, location=room)
            npc.tags.add("spawned_vendor", category="spawn")

def spawn_mob(room, mob_name, level, is_aggro, faction, equipped_items=None):
    if room.search(mob_name, quiet=True):
        return None
    mob = create_object("typeclasses.objects.Object", key=mob_name, location=room)
    mob.db.level = level
    mob.db.is_aggro = is_aggro
    mob.db.faction = faction
    mob.db.currency_drop = (level * 5, level * 25)  # Random Gold/Silver range
    
    # Equip weapons/armor directly onto mob (dropped onto corpse on death)
    mob.db.equipment = equipped_items or []
    mob.tags.add("realm_mob", category="spawn")
    return mob

def build_phase3():
    print("[Phase 3] Spawning town vendors, level-scaled mobs, equipment drops, and world bosses...")
    import world.builder_phase1 as p1
    
    # 1. Spawn Town Amenities for Evil & Good Towns
    for t_key, t_name in p1.EVIL_TOWNS:
        rm = search_tag(f"{t_key}_1", category="room_id") or search_tag("the_junction_1", category="room_id")
        if rm:
            spawn_town_vendors(rm[0], t_name)
            
    for t_key, t_name in p1.GOOD_TOWNS:
        rm = search_tag(f"{t_key}_1", category="room_id") or search_tag("the_crossroads_1", category="room_id")
        if rm:
            spawn_town_vendors(rm[0], t_name)

    # 2. Spawn Starter Zone Passive Mobs (Levels 1-10)
    starter_evil = search_tag("brimstone_courtyard_1", category="room_id")
    if starter_evil:
        spawn_mob(starter_evil[0], "Imp Hatchling", 2, False, "evil", [{"key": "Lesser Chitin Dagger", "slot": "wield"}])
        spawn_mob(starter_evil[0], "Lesser Hellhound", 5, False, "evil")
        
    starter_good = search_tag("sunspire_meadows_1", category="room_id")
    if starter_good:
        spawn_mob(starter_good[0], "Prairie Fox", 2, False, "good")
        spawn_mob(starter_good[0], "Wandering Fawn", 4, False, "good")

    # 3. Spawn Boss Entities
    bosses = [
        ("drow_caverns_sub_400", "Lich Queen Vaelira", 45, "evil", BOSS_LOOT_TABLES["lich_queen"]),
        ("vile_grounds_350", "Arch-Fiend Malagor", 50, "evil", BOSS_LOOT_TABLES["arch_fiend"]),
        ("stoneguard_mines_400", "High-Mountain Golem", 45, "good", BOSS_LOOT_TABLES["mountain_golem"]),
        ("astraea_ruins_350", "Celestial Sentinel", 50, "good", BOSS_LOOT_TABLES["celestial_sentinel"]),
        ("great_sun_wastes_1250", "Anubis the Dune Stalker", 40, "neutral", BOSS_LOOT_TABLES["dune_stalker"]),
        ("south_shore_1500", "Kraken-Spawn Leviathan", 50, "neutral", BOSS_LOOT_TABLES["kraken_spawn"])
    ]
    
    for tag, name, lvl, fac, loot in bosses:
        rm = search_tag(tag, category="room_id")
        if rm:
            boss = spawn_mob(rm[0], f"Level {lvl} {name}", lvl, True, fac, loot)
            if boss:
                boss.db.is_boss = True
                print(f" -> Instantiated Boss: {name} (Level {lvl}) at {tag}")

    print("[Phase 3 COMPLETE] Towns, mobs, loot tables, and bosses instantiated.")
'''

# =====================================================================
# PHASE 4: Database Wipe, Master Runner & Integrity Validation
# =====================================================================
phase4_code = '''# world/builder_phase4.py
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

def build_all():
    print("=== STARTING FULL MODULAR EVENNIA REALM BUILD ===")
    wipe_realm()
    p1.build_phase1()
    p2.build_phase2()
    p3.build_phase3()
    validate_realm()
    print("=== FULL REALM BUILD COMPLETE ===")
'''

with open("world/builder_phase1.py", "w") as f:
    f.write(phase1_code)

with open("world/builder_phase2.py", "w") as f:
    f.write(phase2_code)

with open("world/builder_phase3.py", "w") as f:
    f.write(phase3_code)

with open("world/builder_phase4.py", "w") as f:
    f.write(phase4_code)

print("SUCCESS: Generated world/builder_phase1.py, builder_phase2.py, builder_phase3.py, and builder_phase4.py!")
