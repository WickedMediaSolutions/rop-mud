# world/builder_phase3.py
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
