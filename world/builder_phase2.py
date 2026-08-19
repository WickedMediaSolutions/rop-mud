# world/builder_phase2.py
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
