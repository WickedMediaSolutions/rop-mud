"""
Zone Auto-Generator for 'rop' — Tier 3.4b
==========================================
Programmatically generates 25 new batch zone (.ev) files across all level
brackets (1–80), bringing total batch zones from 5 to 30.

Each generated zone includes:
  - 15–40 interconnected rooms with atmospheric descriptions
  - Explicit bidirectional exits (each emitted inline with its source room,
    matching Evennia's batch `@open` current-room semantics)
  - Level-appropriate mob spawns (`@spawn` + `@tel here`, matching the
    proven pattern used by existing hand-authored `.ev` zones)
  - A `room-zone` tag for the realm spawner / zone discovery systems

Zone Distribution:
  - Tier 1 (L1–10):   5 zones  (starter areas, safe)
  - Tier 2 (L11–25):  6 zones  (early wilderness)
  - Tier 3 (L26–40):  6 zones  (mid-game)
  - Tier 4 (L41–60):  5 zones  (deep wilderness)
  - Tier 5 (L61–80):  3 zones  (end-game)

Usage:
  from world.zone_generator import generate_all_zones
  generate_all_zones()  # writes .ev files to world/batch_zones/

  from evennia import batch_process
  batch_process("world.batch_zones.silverwood_glade")
"""

from __future__ import annotations

import os
import random
from typing import Dict, List, Tuple

# Output directory
BATCH_ZONES_DIR = os.path.join(os.path.dirname(__file__), "batch_zones")

# Mob levels available from world.content_expansion.generate_all_mobs().
# Generated mob keys are of the form `gen_<archetype>_lvl<level>`.
AVAILABLE_MOB_LEVELS = [
    1, 3, 5, 8, 10, 12, 15, 18, 20, 22, 25, 28, 30, 33, 35, 38,
    40, 43, 45, 48, 50, 53, 55, 58, 60, 63, 65, 68, 70, 73, 75, 78, 80,
]

MOB_ARCHETYPES = ["brute", "skirmisher", "caster", "tank", "assassin", "balanced"]

# ===========================================================================
# ZONE DEFINITIONS — 25 new zones
# ===========================================================================

# Each zone: (file_key, display_name, level_min, level_max, room_count, theme, faction)
ZONE_DEFS: List[Tuple[str, str, int, int, int, str, str]] = [
    # ---- Tier 1: L1–10 (Starter / Safe) ----
    ("silverwood_glade", "Silverwood Glade", 1, 8, 18, "Enchanted forest glade with gentle streams and friendly woodland creatures", "Aethelgard Alliance"),
    ("brimstone_foothills", "Brimstone Foothills", 1, 8, 18, "Volcanic foothills with bubbling mud pits and hardy scrub", "Gorgoroth Horde"),
    ("meadowbrook_vale", "Meadowbrook Vale", 3, 10, 20, "Peaceful valley with babbling brooks and grazing deer", "Aethelgard Alliance"),
    ("sunless_hollow", "Sunless Hollow", 3, 10, 20, "Dim cavern entrance with phosphorescent fungi and skittering things", "Gorgoroth Horde"),
    ("crossroads_inn", "Crossroads Inn & Stables", 1, 10, 15, "Busy waystation where travelers from all realms meet", "Neutral"),

    # ---- Tier 2: L11–25 (Early Wilderness) ----
    ("thornwood_forest", "Thornwood Forest", 11, 22, 25, "Dense, thorny woodland with hidden paths and lurking predators", "Neutral"),
    ("crystal_caverns", "Crystal Caverns", 12, 24, 22, "Glittering underground caves filled with luminescent crystals", "Neutral"),
    ("windscar_plateau", "Windscar Plateau", 14, 25, 20, "Windswept highland plateau with ancient standing stones", "Aethelgard Alliance"),
    ("sulfur_mines", "Sulfur Mines of Gorgoroth", 13, 23, 22, "Acrid mining tunnels where slave laborers extract brimstone", "Gorgoroth Horde"),
    ("moonlit_thicket", "Moonlit Thicket", 15, 25, 20, "Eerie forest that only reveals its paths under moonlight", "Neutral"),
    ("copper_vein_depths", "Copper Vein Depths", 11, 20, 18, "Abandoned copper mine now inhabited by subterranean creatures", "Neutral"),

    # ---- Tier 3: L26–40 (Mid-Game) ----
    ("sunken_temple", "Sunken Temple of the Ancients", 26, 38, 30, "Partially submerged temple ruins with waterlogged chambers", "Neutral"),
    ("scorpion_desert", "Scorpion Desert Expanse", 28, 40, 28, "Vast desert with towering dunes and giant scorpion nests", "Neutral"),
    ("frozen_tundra", "Frozen Tundra of the North", 30, 40, 25, "Icy wasteland with howling winds and ancient glaciers", "Neutral"),
    ("blightwood_marsh", "Blightwood Marsh", 26, 36, 25, "Fetid swamp where twisted trees drip with poisonous sap", "Gorgoroth Horde"),
    ("celestial_plateau", "Celestial Plateau", 28, 40, 22, "High-altitude mesa where the stars feel close enough to touch", "Aethelgard Alliance"),
    ("magma_chambers", "Magma Chambers", 30, 40, 24, "Volcanic tunnels with rivers of molten rock and fire elementals", "Gorgoroth Horde"),

    # ---- Tier 4: L41–60 (Deep Wilderness) ----
    ("dragonbone_graveyard", "Dragonbone Graveyard", 41, 55, 30, "Ancient battlefield littered with the skeletal remains of dragons", "Neutral"),
    ("shadowfell_citadel", "Shadowfell Citadel", 43, 58, 28, "Foreboding dark fortress where shadows move of their own accord", "Gorgoroth Horde"),
    ("aetherial_spire", "Aetherial Spire", 42, 56, 25, "Towering crystal spire that channels raw magical energy", "Aethelgard Alliance"),
    ("abyssal_rift", "Abyssal Rift", 45, 60, 26, "Gaping chasm that tears through reality into the void beyond", "Neutral"),
    ("petrified_forest", "Petrified Forest of Ages", 41, 54, 24, "Ancient forest turned to stone, with fossilized creatures frozen mid-stride", "Neutral"),

    # ---- Tier 5: L61–80 (End-Game) ----
    ("throne_of_chaos", "Throne of Chaos", 61, 78, 35, "The seat of ultimate power where reality bends and breaks", "Neutral"),
    ("celestial_citadel", "Celestial Citadel of Light", 62, 80, 32, "Floating fortress of pure radiance, last bastion against the void", "Aethelgard Alliance"),
    ("nether_abyss", "Nether Abyss", 63, 80, 33, "The deepest pit of the underworld where ancient evils slumber", "Gorgoroth Horde"),
]

# ===========================================================================
# ROOM DESCRIPTION TEMPLATES
# ===========================================================================

# Placeholders are drawn from WORD_POOLS below.  All placeholders used
# mid-sentence have lowercase pool values to avoid capitalization artifacts.
# The first character of every description is capitalized post-fill.

ROOM_TEMPLATES = {
    "forest": [
        "Ancient {trees} tower overhead, their {canopy} canopy filtering the {light} into dancing patterns on the forest floor. The air smells of {scent}, and the ground is carpeted with {ground}.",
        "A narrow trail winds through the {density} undergrowth. You hear {sounds} echoing among the {trees} and spot {detail} half-hidden in the {ground}.",
        "You have found a small clearing where {light} streams through a break in the {trees} overhead. You notice {detail} resting here, and the forest seems to hold its breath around you.",
        "The {trees} grow {density} here, their {adjective} branches intertwining overhead. You hear {sounds} drifting on the breeze, and the path ahead looks {condition}.",
    ],
    "cavern": [
        "The cave opens into a {size} chamber where {light} reflects off {mineral} formations on the walls. You hear {sounds} echoing from deeper within, and the air is {temperature} and {adjective}.",
        "Stalactites hang like {adjective} teeth from the ceiling of this {size} cavern. {mineral} deposits glitter in the {light}, and you hear {sounds} reverberating through the stone.",
        "A {size} tunnel narrows ahead, its walls slick with {substance}. The {light} here is {adjective}, and you hear {sounds} that seem to come from everywhere at once.",
        "You enter a {adjective} grotto where {mineral} crystals pulse with a faint inner {light}. You notice {detail} carved into the stone floor, and the air hums with {adjective} energy.",
    ],
    "mountain": [
        "The trail clings to the mountainside, with a {adjective} drop on one side and {adjective} cliffs on the other. {light} bathes the peaks ahead, and the wind carries {sounds}.",
        "You stand on a {adjective} ridge overlooking a {size} valley below. You notice {detail} marking the path forward, and you hear {sounds} drifting up from the depths.",
        "Jagged rocks jut from the {adjective} slope like {adjective} sentinels. The air is thin and {temperature}, and {light} casts long shadows across the stone.",
        "A {adjective} plateau offers a moment of rest from the climb. You notice {detail} arranged here, and the view stretches to the {adjective} horizon.",
    ],
    "desert": [
        "Endless dunes of {adjective} sand stretch in every direction, their crests sculpted by the {adjective} wind. The {light} is harsh and unforgiving, and you see {detail} shimmering in the heat haze.",
        "You trudge through a {adjective} expanse of cracked earth and scattered {detail}. The {light} beats down mercilessly, and the vast emptiness swallows all sound.",
        "A {adjective} oasis appears ahead, and you see {detail} near the water's edge. The air here is slightly cooler, and you can hear faint sounds of life.",
        "The desert floor gives way to a {adjective} canyon of weathered {adjective} stone. {light} filters down from above, and you hear {sounds} echoing through the narrow passage.",
    ],
    "swamp": [
        "{adjective} water stretches between gnarled {trees}, their roots disappearing into the murky depths. You hear {sounds} in the heavy air and see {detail} floating on the stagnant surface.",
        "Your boots sink into the {adjective} muck with every step. {light} barely penetrates the {adjective} canopy, and you hear {sounds} coming from the {adjective} shadows.",
        "A {adjective} boardwalk of rotting planks provides precarious passage through the {adjective} marsh. You see {detail} watching from the water, and {sounds} drift through the mist.",
        "The swamp opens into a {adjective} bayou where {light} reflects off the dark water. You notice {detail} hanging from the {trees}, and the air is thick with the smell of {scent}.",
    ],
    "ruins": [
        "Crumbling {adjective} walls rise from the {ground}, remnants of a {adjective} civilization. You see {detail} carved into the weathered stone, and {sounds} drift through the {adjective} halls.",
        "You pick your way through {adjective} rubble that was once a {adjective} structure. {light} streams through gaps in the ceiling, illuminating {detail} on the floor.",
        "A {adjective} archway still stands defiantly amid the {adjective} ruins. You notice {detail} marking the keystone, and {sounds} seem to emanate from the stones themselves.",
        "The {adjective} chamber you have entered must once have been important. You notice {detail} dominating the center, with {light} pooling around it like a {adjective} blessing.",
    ],
    "volcanic": [
        "The ground trembles beneath your feet as {adjective} vents hiss {adjective} steam nearby. Rivers of {adjective} lava flow through channels in the {adjective} rock, and the air burns with each breath.",
        "You navigate a {adjective} ledge above a {adjective} pool of molten rock. {light} from the lava paints the cavern in {adjective} hues, and you hear {sounds} rumbling from deep below.",
        "Obsidian formations jut from the {adjective} floor like {adjective} blades. The heat is {adjective}, and you see {detail} scorched into the stone.",
        "A {adjective} chamber opens before you, dominated by a {adjective} magma vent. You hear {sounds} of {adjective} power reverberating through the rock, and see {detail} glowing with inner fire.",
    ],
    "tundra": [
        "A {adjective} expanse of snow and ice stretches to the {adjective} horizon. The {light} is pale and distant, and {sounds} are muffled by the {adjective} cold.",
        "Your breath crystallizes in the {adjective} air as you cross the {adjective} tundra. You see {detail} breaking the monotony of white, and {sounds} howl across the frozen waste.",
        "A {adjective} crevasse splits the ice ahead, its depths a {adjective} blue. {light} glitters off the frozen walls, and you hear {sounds} echoing from the abyss.",
        "You find shelter in the lee of a {adjective} ice formation. You notice {detail} frozen within the crystalline walls, while the {light} creates {adjective} patterns through the ice.",
    ],
    "citadel": [
        "The {adjective} architecture of this {adjective} fortress speaks of {adjective} power. You see {detail} adorning the walls, and {sounds} of {adjective} purpose echo through the halls.",
        "You walk through a {adjective} corridor lined with {detail}. The {light} here is {adjective}, and something seems to watch your every step.",
        "A {adjective} chamber opens before you, its ceiling lost in {adjective} shadow. You notice {detail} standing at its center, and {light} radiates from an unseen source.",
        "The {adjective} battlements offer a view of the {adjective} realm below. You see {detail} etched into the parapet, and {sounds} of {adjective} wind whip past.",
    ],
}

# Word pools for template filling.  Lowercase and plural-safe values only.
WORD_POOLS = {
    "trees": ["oaks", "pines", "willows", "ash trees", "elms", "cypresses", "ironwoods", "bloodoaks"],
    "canopy": ["dense", "emerald", "dark", "shimmering", "ancient", "tangled"],
    "light": ["sunlight", "moonlight", "faint luminescence", "filtered light", "ethereal radiance", "dim luminescence"],
    "scent": ["damp earth", "wildflowers", "pine resin", "decay", "ozone", "incense", "brimstone"],
    "ground": ["fallen leaves", "thick moss", "exposed roots", "cracked stone", "soft loam", "scattered bones"],
    "density": ["dense", "thick", "tangled", "sparse", "twisted", "overgrown"],
    "sounds": ["strange whispers", "distant howls", "dripping echoes", "faint chants", "low rumbling tremors", "muffled voices", "skittering claws"],
    "detail": ["a weathered statue", "ancient runes", "a discarded weapon", "flickering torchlight", "a dark bloodstain", "scattered offerings", "a broken altar"],
    "adjective": ["ancient", "crumbling", "majestic", "foreboding", "ethereal", "desolate", "pristine", "corrupted", "shimmering", "darkened"],
    "condition": ["treacherous", "well-worn", "overgrown", "barely visible", "blocked by debris", "slick with moisture"],
    "size": ["vast", "narrow", "sprawling", "cramped", "cavernous", "immense"],
    "mineral": ["quartz", "obsidian", "amethyst", "glowing crystal", "iron", "silver"],
    "temperature": ["frigid", "sweltering", "pleasantly cool", "unbearably hot", "deathly cold"],
    "substance": ["moisture", "a strange slime", "crystalline deposits", "soot", "ancient blood"],
}


def _fill_template(template: str) -> str:
    """Fill a room description template with theme-appropriate words."""
    result = template
    for key, words in WORD_POOLS.items():
        placeholder = "{" + key + "}"
        while placeholder in result:
            result = result.replace(placeholder, random.choice(words), 1)
    # Capitalize the first character so descriptions never begin lowercase.
    if result:
        result = result[0].upper() + result[1:]
    return result


def _get_theme_for_zone(theme: str) -> str:
    """Map a zone theme string to a room template category."""
    theme_lower = theme.lower()
    if any(w in theme_lower for w in ["forest", "wood", "glade", "thicket", "grove", "meadow", "vale"]):
        return "forest"
    if any(w in theme_lower for w in ["cavern", "cave", "mine", "depths", "tunnel", "hollow"]):
        return "cavern"
    if any(w in theme_lower for w in ["mountain", "peak", "ridge", "plateau", "highland", "mesa", "spire"]):
        return "mountain"
    if any(w in theme_lower for w in ["desert", "dune", "waste", "expanse", "sand"]):
        return "desert"
    if any(w in theme_lower for w in ["swamp", "marsh", "bog", "mire", "bayou", "fen"]):
        return "swamp"
    if any(w in theme_lower for w in ["ruin", "temple", "tomb", "ancient", "graveyard"]):
        return "ruins"
    if any(w in theme_lower for w in ["volcanic", "magma", "lava", "brimstone", "sulfur", "fire"]):
        return "volcanic"
    if any(w in theme_lower for w in ["tundra", "frozen", "ice", "glacier", "snow"]):
        return "tundra"
    if any(w in theme_lower for w in ["citadel", "fortress", "castle", "keep", "throne", "spire"]):
        return "citadel"
    return "forest"  # default


def _snap_level(level: int) -> int:
    """Snap a level to the nearest available generated-mob level."""
    return min(AVAILABLE_MOB_LEVELS, key=lambda l: abs(l - level))


def _levels_in_range(level_min: int, level_max: int) -> List[int]:
    """Return available mob levels within [level_min, level_max]."""
    return [l for l in AVAILABLE_MOB_LEVELS if level_min <= l <= level_max]


def _generate_room_layout(room_count: int) -> List[List[Tuple[str, int]]]:
    """
    Generate a connected grid layout.

    Returns a list over room indices, each entry listing ``(direction,
    target_idx)`` exits for that source room.  Every connection is already
    bidirectional (both rooms reference each other).
    """
    cols = max(3, int(room_count ** 0.5) + 1)
    adj = {(-1, 0): "north", (1, 0): "south", (0, 1): "east", (0, -1): "west"}
    reverse = {"north": "south", "south": "north", "east": "west", "west": "east"}

    # Each room's exits keyed by target index so we never emit duplicate
    # directions (e.g. two "east" exits from the same room).
    exits: List[List[Tuple[str, int]]] = [[] for _ in range(room_count)]
    used_dir = [set() for _ in range(room_count)]

    def _link(src: int, dst: int, direction: str) -> None:
        if direction in used_dir[src] or dst in {t for _, t in exits[src]}:
            return
        used_dir[src].add(direction)
        exits[src].append((direction, dst))

    # Grid edges (bidirectional).
    for i in range(room_count):
        r, c = i // cols, i % cols
        for (dr, dc), direction in adj.items():
            nr, nc = r + dr, c + dc
            if 0 <= nr and 0 <= nc < cols:
                j = nr * cols + nc
                if j < room_count:
                    _link(i, j, direction)
                    _link(j, i, reverse[direction])

    # A few extra non-linear links for exploration variety.
    for i in range(room_count):
        for j in range(i + 2, min(i + 5, room_count)):
            if random.random() < 0.15:
                ri, ci = i // cols, i % cols
                rj, cj = j // cols, j % cols
                if abs(ri - rj) > abs(ci - cj):
                    d = "south" if rj > ri else "north"
                else:
                    d = "east" if cj > ci else "west"
                _link(i, j, d)
                _link(j, i, reverse[d])

    return exits


def _generate_zone_file(
    file_key: str,
    display_name: str,
    level_min: int,
    level_max: int,
    room_count: int,
    theme: str,
    faction: str,
) -> str:
    """Generate a complete .ev batch file for a zone."""
    template_theme = _get_theme_for_zone(theme)
    templates = ROOM_TEMPLATES.get(template_theme, ROOM_TEMPLATES["forest"])
    layout = _generate_room_layout(room_count)

    # Level-appropriate mob prototypes that actually exist.
    available_levels = _levels_in_range(level_min, level_max)
    if not available_levels:
        available_levels = [_snap_level((level_min + level_max) // 2)]

    lines: List[str] = []
    lines.append(f"# {display_name} — Level {level_min}-{level_max}")
    lines.append(f"# Auto-generated zone: {theme}")
    lines.append(f"# Faction: {faction}")
    lines.append(f"# Rooms: {room_count}")
    lines.append("#")
    lines.append("# Usage (in Evennia shell):")
    lines.append("#   from evennia import batch_process")
    lines.append(f"#   batch_process(\"world.batch_zones.{file_key}\")")
    lines.append("")

    zone_tag = file_key

    # Room names — guaranteed unique so @open targets are unambiguous.
    suffixes = [
        "Crossroads", "Path", "Clearing", "Depths", "Ridge", "Grotto",
        "Passage", "Overlook", "Hollow", "Ascent", "Descent", "Chamber",
        "Gallery", "Nook", "Bend", "Stretch", "Expanse", "Thicket",
        "Grove", "Ledge",
    ]
    room_names: List[str] = []
    used_names = set()
    for i in range(room_count):
        if i == 0:
            name = f"{display_name} - Entrance"
        elif i == room_count - 1:
            name = f"{display_name} - Heart"
        else:
            name = f"{display_name} - {random.choice(suffixes)}"
            counter = 2
            while name in used_names:
                name = f"{display_name} - {random.choice(suffixes)} {counter}"
                counter += 1
        used_names.add(name)
        room_names.append(name)

    # Rooms (each with its own inline exits — required by Evennia batch @open)
    for i in range(room_count):
        desc = _fill_template(random.choice(templates))
        lines.append(f"# --- Room {i + 1}/{room_count} ---")
        lines.append(f"dig {room_names[i]}")
        lines.append(f"@desc {desc}")
        lines.append(f"@tags/set room-zone:{zone_tag}")

        # Populate non-entrance rooms with level-scaled mobs.
        # The entrance stays clear to provide a safe landing zone.
        if i > 0 and random.random() < 0.7:
            for _ in range(random.randint(1, 2)):
                arch = random.choice(MOB_ARCHETYPES)
                lvl = random.choice(available_levels)
                lines.append(f"@spawn gen_{arch}_lvl{lvl}")
                lines.append("@tel here")

        # Inline exits — @open targets the room most recently dug.
        for direction, j in layout[i]:
            lines.append(f"@open {direction}={direction} to {room_names[j]}")

        lines.append("")

    total_edges = sum(len(e) for e in layout)
    lines.append(
        f"# Zone '{display_name}' complete — {room_count} rooms, "
        f"{total_edges} directed exits."
    )

    return "\n".join(lines)


def generate_all_zones() -> int:
    """
    Generate all 25 new zone .ev files in world/batch_zones/.
    Idempotent: existing files are left untouched.

    Returns the number of zone files written.
    """
    os.makedirs(BATCH_ZONES_DIR, exist_ok=True)

    generated = 0
    for file_key, display_name, level_min, level_max, room_count, theme, faction in ZONE_DEFS:
        filepath = os.path.join(BATCH_ZONES_DIR, f"{file_key}.ev")
        if os.path.exists(filepath):
            continue

        content = _generate_zone_file(
            file_key, display_name, level_min, level_max,
            room_count, theme, faction
        )
        with open(filepath, "w") as f:
            f.write(content)
        generated += 1

    return generated


def get_zone_count() -> int:
    """Return the current count of .ev zone files in batch_zones/."""
    if not os.path.isdir(BATCH_ZONES_DIR):
        return 0
    return len([f for f in os.listdir(BATCH_ZONES_DIR) if f.endswith(".ev")])


if __name__ == "__main__":
    count = generate_all_zones()
    total = get_zone_count()
    print(f"Generated {count} new zone files.")
    print(f"Total zones in batch_zones/: {total}")