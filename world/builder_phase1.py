# world/builder_phase1.py
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
        r"\s*\((?:\s*(?:Starter|Tier|Levels?|Lvl|Zone)\s*[,\d\s\-]+)\)",
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
