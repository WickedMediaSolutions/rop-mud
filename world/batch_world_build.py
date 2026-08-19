
# world/batch_world_build.py

"""
This script batch-builds a large, fully connected world map for the Evennia game.
"""

from evennia import create_object
from evennia.utils import search
from typeclasses.rooms import Room
from typeclasses.exits import Exit

# --- Room Definitions ---
# Each dictionary represents a room with its key, description, and exits.
# The exits are defined by the key of the target room.

WORLD_MAP = {
    # --- GOOD REALM (North-West / West) ---
    "Aethelgard - The Grand Sanctum": {
        "desc": "Sunlight streams through magnificent stained-glass windows, illuminating a vast, circular chamber of white marble. Ornate columns carved in the likeness of ancient heroes rise to a vaulted ceiling, and the air hums with a palpable aura of peace and reverence. In the center of the room, a shimmering font of holy water bubbles gently. This is the heart of Aethelgard, a place of solace and strength for all who follow the path of light.",
        "exits": {"east": "Aethelgard - Cathedral Spires"},
    },
    "Aethelgard - Cathedral Spires": {
        "desc": "You stand on a wide balcony high among the spires of Aethelgard's main cathedral. The wind whips gently around you, carrying the distant sounds of the city below. The view is breathtaking, stretching over the sunlit rooftops of the city to the rolling green hills beyond. A narrow, winding staircase leads down into the city proper.",
        "exits": {"west": "Aethelgard - The Grand Sanctum", "down": "Aethelgard - Sunlit Square"},
    },
    "Aethelgard - Sunlit Square": {
        "desc": "You are in the bustling main square of Aethelgard. Citizens in fine clothing and guards in polished armor move about their day, their faces filled with a sense of purpose and security. Market stalls line the perimeter, offering everything from fresh produce to finely crafted weapons. The grand cathedral looms to the north, its spires reaching for the heavens.",
        "exits": {"up": "Aethelgard - Cathedral Spires", "north": "Aethelgard - Paladin Training Grounds", "south": "Aethelgard - City Gates"},
    },
    "Aethelgard - Paladin Training Grounds": {
        "desc": "This open-air courtyard is dedicated to the training of Aethelgard's famed paladins. The rhythmic clash of steel on steel echoes as knights spar in the center of the yard. Racks of blunted weapons and training dummies line the walls. The discipline and devotion of these warriors are evident in their every move.",
        "exits": {"south": "Aethelgard - Sunlit Square"},
    },
    "Aethelgard - City Gates": {
        "desc": "Massive gates of oak and iron stand open, marking the southern entrance to Aethelgard. Two stoic guards, clad in the city's gleaming silver and white armor, stand watch. Beyond the gates, a well-trodden path leads south into the surrounding farmlands.",
        "exits": {"north": "Aethelgard - Sunlit Square", "south": "The Rolling Green Hills"},
    },
    "The Rolling Green Hills": {
        "desc": "You find yourself amidst gentle, rolling hills of vibrant green. The air is fresh and clean, filled with the scent of wildflowers. A few sheep graze peacefully in the distance, their bells tinkling softly. The path continues south, and to the east, you can see the edge of a vast, arid landscape.",
        "exits": {"north": "Aethelgard - City Gates", "south": "Lush Farmland", "east": "Western Edge of the Scorched Desert"},
    },
    "Lush Farmland": {
        "desc": "Expansive fields of golden wheat and other crops stretch out before you, a testament to the prosperity of Aethelgard. A simple farmhouse with a wisp of smoke curling from its chimney sits nearby. The path here is less defined, but you can see a guard outpost to the east.",
        "exits": {"north": "The Rolling Green Hills", "east": "Aethelgard Guard Outpost"},
    },
    "Aethelgard Guard Outpost": {
        "desc": "A sturdy wooden watchtower stands here, offering a commanding view of the surrounding lands. This outpost marks the easternmost border of Aethelgard's direct influence. A few guards are stationed here, their eyes constantly scanning the horizon for any sign of trouble from the desolate lands to the east.",
        "exits": {"west": "Lush Farmland", "east": "Cracked Salt Flats"},
    },

    # --- DEMONIC / EVIL REALM (South-East / East) ---
    "Gorgoroth - The Blood Forge": {
        "desc": "The air is thick with the smell of sulfur, hot metal, and something coppery and foul. Rivers of molten iron flow in channels carved into the black, obsidian floor. Demonic smiths, their skin the color of cooling embers, hammer relentlessly at glowing blades, their monstrous forms silhouetted against the fiery light. This is where the armies of Gorgoroth are armed, a place of unending, brutal industry.",
        "exits": {"west": "Gorgoroth - Iron Chains Causeway"},
    },
    "Gorgoroth - Iron Chains Causeway": {
        "desc": "A narrow causeway of jagged, black iron spans a chasm of unknown depth. Massive, rusted chains hang from the cavern ceiling, swaying ominously. The only way forward is across this treacherous bridge, which leads west towards the main spire of Gorgoroth.",
        "exits": {"east": "Gorgoroth - The Blood Forge", "up": "Gorgoroth - Volcanic Spire Peak", "west": "Gorgoroth - Subterranean Barracks"},
    },
    "Gorgoroth - Volcanic Spire Peak": {
        "desc": "You stand at the pinnacle of Gorgoroth's central spire, a shard of volcanic rock that juts high into the cavernous underworld. The heat is intense, and the air shimmers with fumes rising from the lava pits far below. From this vantage point, you can see the entirety of the subterranean city, a nightmarish landscape of fire and shadow.",
        "exits": {"down": "Gorgoroth - Iron Chains Causeway"},
    },
    "Gorgoroth - Subterranean Barracks": {
        "desc": "This vast, grim cavern serves as the barracks for Gorgoroth's legions. Crude bunks are carved into the rock walls, and the air is filled with the guttural language of its demonic inhabitants. The creatures here are a horrifying mix of twisted forms, all honed for cruelty and war.",
        "exits": {"east": "Gorgoroth - Iron Chains Causeway", "north": "The Gates of Gorgoroth"},
    },
    "The Gates of Gorgoroth": {
        "desc": "Two colossal gates of black iron, adorned with skulls and infernal symbols, mark the northern exit of the subterranean city. Two hulking, demonic sentinels stand guard, their fiery eyes tracking your every move. Beyond the gates lies the desolate surface world.",
        "exits": {"south": "Gorgoroth - Subterranean Barracks", "north": "The Ashen Wastes"},
    },
    "The Ashen Wastes": {
        "desc": "A blanket of grey ash covers everything in sight, muffling all sound. The sky above is a perpetual, sickly yellow-brown haze. Petrified trees, their branches like skeletal fingers, claw at the sky. The ground is cold and dead. To the west, the terrain gives way to jagged canyons.",
        "exits": {"south": "The Gates of Gorgoroth", "west": "Jagged Obsidian Canyons", "north": "Eastern Edge of the Scorched Desert"},
    },
    "Jagged Obsidian Canyons": {
        "desc": "You navigate a treacherous network of canyons carved from razor-sharp obsidian. The black, glassy walls reflect the dim light, creating confusing and distorted images. The wind howls through the narrow passages, sounding like the wails of lost souls. A crude encampment is visible to the north.",
        "exits": {"east": "The Ashen Wastes", "north": "Scorched Encampment"},
    },
    "Scorched Encampment": {
        "desc": "A collection of crude tents and lean-tos, made from scorched hides and scavenged bones, huddles in the shelter of a canyon wall. This is a forward camp for the forces of Gorgoroth. A foul-smelling cooking fire sputters in the center, casting flickering shadows on the grim faces of the demonic soldiers gathered here.",
        "exits": {"south": "Jagged Obsidian Canyons", "west": "Cracked Salt Flats"},
    },

    # --- CENTRAL DIVIDE - THE SCORCHED DESERT ---
    "Western Edge of the Scorched Desert": {
        "desc": "The lush green of the western hills gives way abruptly to a vast, cracked desert. The ground here is a mosaic of dried mud and salt, and the air is noticeably hotter and drier. A sense of profound emptiness emanates from the east, a stark contrast to the vibrant life behind you to the west.",
        "exits": {"west": "The Rolling Green Hills", "east": "Cracked Salt Flats", "north": "Southern Edge of the Boreal Forest"},
    },
    "Cracked Salt Flats": {
        "desc": "You are in the midst of a seemingly endless expanse of white salt flats. The ground is cracked and barren, reflecting the harsh glare of the sun with blinding intensity. The air is still and heavy, and the silence is broken only by the crunch of your footsteps on the salt-crusted earth. The flats stretch in all directions, a formidable natural barrier.",
        "exits": {"west": "Western Edge of the Scorched Desert", "east": "Scorched Encampment"},
    },
    "Eastern Edge of the Scorched Desert": {
        "desc": "The ashen soil of the eastern wastes gradually transitions into the baked earth of the great desert. The air here is thick with a haze of dust and ash, and the oppressive atmosphere of the demonic lands lingers. To the west, the desert stretches as far as the eye can see.",
        "exits": {"east": "The Ashen Wastes", "west": "Towering Sand Dunes"},
    },
    "Towering Sand Dunes": {
        "desc": "Massive dunes of fine, orange sand rise up around you, their crests sculpted into sharp ridges by the relentless wind. The landscape is constantly shifting, making navigation difficult. The sun beats down mercilessly, and the heat is oppressive. An abandoned oasis is nestled among the dunes to the south.",
        "exits": {"east": "Eastern Edge of the Scorched Desert", "south": "Abandoned Oasis", "north": "Ancient Trade Path - Southern Turn"},
    },
    "Abandoned Oasis": {
        "desc": "You discover a small, desolate oasis, a ghost of its former self. A few withered palm trees surround a pool of stagnant, murky water. The skeletons of animals that came here seeking water lie half-buried in the sand. A sense of deep sorrow and loss hangs heavy in the air.",
        "exits": {"north": "Towering Sand Dunes"},
    },

    # --- NORTHERN WILDERNESS - THE ANCIENT BOREAL FOREST ---
    "Southern Edge of the Boreal Forest": {
        "desc": "The arid desert gives way to a line of hardy, windswept pines that mark the southern edge of a vast, ancient forest. The air grows cooler and smells of pine needles and damp earth. A paved stone highway, remarkably well-preserved, runs east and west into the trees.",
        "exits": {"south": "Western Edge of the Scorched Desert", "east": "Ancient Trade Path - West", "north": "The Giant Pines"},
    },
    "Ancient Trade Path - West": {
        "desc": "You are on a wide, paved highway of grey stone that cuts a clear path through the dense forest. The trees here are enormous, their branches forming a thick canopy that filters the sunlight. The road is ancient but still serviceable, a clear corridor for travel. It continues to the east.",
        "exits": {"west": "Southern Edge of the Boreal Forest", "east": "Ancient Trade Path - Central"},
    },
    "The Giant Pines": {
        "desc": "You wander off the main path into a grove of truly colossal pine trees. Their trunks are as wide as small cottages, and their tops are lost in the canopy far above. The forest floor is a soft carpet of fallen needles, and an ancient silence pervades this place.",
        "exits": {"south": "Southern Edge of the Boreal Forest", "east": "Mystical Glade"},
    },
    "Mystical Glade": {
        "desc": "You stumble into a hidden glade where the light filters down in ethereal shafts. A circle of moss-covered standing stones occupies the center of the clearing, and the air feels charged with a strange, quiet energy. This place feels ancient and untouched by the outside world.",
        "exits": {"west": "The Giant Pines", "east": "Ancient Trade Path - Central"},
    },
    "Ancient Trade Path - Central": {
        "desc": "The ancient stone highway continues its path through the heart of the Boreal Forest. The woods are deep and mysterious on either side of the road. To the south lies a mystical glade, and to the north, you can just make out the crumbling shape of some old ruins.",
        "exits": {"west": "Ancient Trade Path - West", "east": "Ancient Trade Path - East", "south": "Mystical Glade", "north": "Hidden Ruins"},
    },
    "Hidden Ruins": {
        "desc": "Partially reclaimed by the forest, you find the crumbling stone walls of an ancient structure. The purpose of these ruins is long forgotten, but the intricate carvings on the remaining stones suggest they were once of great importance. Vines and moss cover everything, and the air is heavy with the weight of history.",
        "exits": {"south": "Ancient Trade Path - Central"},
    },
    "Ancient Trade Path - East": {
        "desc": "The paved highway continues its journey eastward, nearing the edge of the great forest. The trees begin to thin out slightly, allowing more light to reach the forest floor. The road turns south here, leading out of the woods and towards the desert.",
        "exits": {"west": "Ancient Trade Path - Central", "south": "Ancient Trade Path - Southern Turn"},
    },
    "Ancient Trade Path - Southern Turn": {
        "desc": "The ancient trade path makes a sharp turn to the south, leading out of the Boreal Forest and into the northern reaches of the Scorched Desert. The transition is stark, with the cool, damp air of the forest giving way to the dry heat of the dunes.",
        "exits": {"north": "Ancient Trade Path - East", "south": "Towering Sand Dunes"},
    },
}


def build_world():
    """
    This function creates the world based on the WORLD_MAP dictionary.
    """
    # Get or create the start rooms (search by key, not hardcoded dbref)
    good_start_room = search.search_object("Good Start Room", typeclass=Room)
    evil_start_room = search.search_object("Evil Start Room", typeclass=Room)

    if not good_start_room:
        good_start_room = create_object(Room, key="Good Start Room")
    else:
        good_start_room = good_start_room[0]

    if not evil_start_room:
        evil_start_room = create_object(Room, key="Evil Start Room")
    else:
        evil_start_room = evil_start_room[0]

    # A dictionary to hold the newly created room objects
    rooms = {}
    room_count = 0
    exit_count = 0

    # --- First Pass: Create all rooms ---
    print("Creating rooms...")
    for room_key, room_data in WORLD_MAP.items():
        if not search.search_object(room_key, typeclass=Room):
            new_room = create_object(Room, key=room_key)
            new_room.db.desc = room_data["desc"]
            rooms[room_key] = new_room
            room_count += 1
        else:
            # If room already exists, get its object to be used for exit creation
            rooms[room_key] = search.search_object(room_key, typeclass=Room)[0]

    print(f"Created {room_count} new rooms.")

    # --- Second Pass: Create all exits ---
    print("Creating exits...")
    for room_key, room_data in WORLD_MAP.items():
        source_room = rooms.get(room_key)
        if not source_room:
            continue

        for exit_name, dest_key in room_data["exits"].items():
            destination_room = rooms.get(dest_key)
            if not destination_room:
                print(f"  Warning: Destination room '{dest_key}' for exit from '{room_key}' not found. Skipping.")
                continue

            # Create the forward exit
            if not source_room.search(exit_name, typeclass=Exit):
                create_object(Exit, key=exit_name, location=source_room, destination=destination_room)
                exit_count += 1

            # Create the reverse exit
            reverse_exit_map = {
                "north": "south", "south": "north",
                "east": "west", "west": "east",
                "up": "down", "down": "up",
                "northeast": "southwest", "southwest": "northeast",
                "northwest": "southeast", "southeast": "northwest"
            }
            reverse_exit_name = reverse_exit_map.get(exit_name)
            if reverse_exit_name and not destination_room.search(reverse_exit_name, typeclass=Exit):
                create_object(Exit, key=reverse_exit_name, location=destination_room, destination=source_room)
                exit_count += 1

    # --- Third Pass: Link to existing Start Rooms ---
    print("Linking to start rooms...")
    
    # Link Good Start Room (#20) to "Aethelgard - The Grand Sanctum"
    grand_sanctum = rooms.get("Aethelgard - The Grand Sanctum")
    if grand_sanctum:
        # Exit from Start Room to Grand Sanctum
        if not good_start_room.search("out", typeclass=Exit):
            create_object(Exit, key="out", aliases=["begin", "enter"], location=good_start_room, destination=grand_sanctum)
            exit_count += 1
        # Exit from Grand Sanctum back to Start Room (optional, can be admin-only)
        if not grand_sanctum.search("return", typeclass=Exit):
             create_object(Exit, key="return", location=grand_sanctum, destination=good_start_room)
             exit_count += 1


    # Link Evil Start Room (#21) to "Gorgoroth - The Blood Forge"
    blood_forge = rooms.get("Gorgoroth - The Blood Forge")
    if blood_forge:
        # Exit from Start Room to Blood Forge
        if not evil_start_room.search("out", typeclass=Exit):
            create_object(Exit, key="out", aliases=["begin", "enter"], location=evil_start_room, destination=blood_forge)
            exit_count += 1
        # Exit from Blood Forge back to Start Room (optional, can be admin-only)
        if not blood_forge.search("return", typeclass=Exit):
            create_object(Exit, key="return", location=blood_forge, destination=evil_start_room)
            exit_count += 1

    print("\n--- World Build Summary ---")
    print(f"Total new rooms created: {room_count}")
    print(f"Total new exits created: {exit_count}")
    print("---------------------------")
    print("To run this script, use the following command in the Evennia shell:")
    print("py from world.batch_world_build import build_world; build_world()")

