"""
Large-Scale Realm Population Script for Evennia
================================================
Populates every room in the realm with NPCs, shopkeepers, and mobs.
Mobs are equipped with faction-appropriate gear and carry gold for loot drops.

Alignment rules:
  - Good regions    -> good/neutral creatures (deer, guards, coyotes)
  - Evil regions    -> evil creatures (skeletal warriors, hellhounds, demons)
  - Desert (neutral) -> mix of good and evil desert creatures
  - Forest (neutral) -> mix of good and evil wilderness creatures

Run manually in `evennia shell`:
    import world.populate_realm as populator
    populator.populate_all()

Or to clear existing population first:
    populator.clear_all_mobs()
    populator.populate_all()
"""

import random
from evennia import create_object
from evennia.objects.models import ObjectDB
from evennia.objects.objects import DefaultObject, DefaultCharacter

# Import shared typeclasses from build_entities to avoid Django model conflicts
from world.build_entities import MUDItem, Shopkeeper


# ---------------------------------------------------------------------------
# 1. Typeclasses (populate_realm-specific only)
# ---------------------------------------------------------------------------

class NPC(DefaultCharacter):
    """Non-combat quest or flavor NPC."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.is_npc = True


class Mob(DefaultCharacter):
    """Combat creature that drops loot on death."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.is_mob = True
        self.db.level = 1
        self.db.faction = "neutral"
        self.db.aggro = False
        self.db.gold = 0


# ---------------------------------------------------------------------------
# 2. Item Templates
# ---------------------------------------------------------------------------

GOOD_WEAPONS = [
    {"key": "Iron Longsword",     "type": "weapon", "value": 50,  "desc": "A sturdy steel longsword with a leather-wrapped hilt."},
    {"key": "Steel Broadsword",   "type": "weapon", "value": 65,  "desc": "A heavy broadsword forged in the Aethelgard armories."},
    {"key": "Oak Shortbow",       "type": "weapon", "value": 45,  "desc": "A flexible hunting bow strung with hemp cord."},
    {"key": "Iron Mace",          "type": "weapon", "value": 55,  "desc": "A brutal iron mace with a flanged head."},
    {"key": "Guardian Spear",     "type": "weapon", "value": 40,  "desc": "A well-balanced spear bearing the crest of Aethelgard."},
    {"key": "Hunting Knife",      "type": "weapon", "value": 20,  "desc": "A simple but sharp skinning knife."},
]

GOOD_ARMOR = [
    {"key": "Leather Armor",      "type": "armor", "value": 30,  "desc": "Hardened leather chestpiece with brass buckles."},
    {"key": "Chainmail Hauberk",  "type": "armor", "value": 80,  "desc": "Interlocking steel rings offering solid protection."},
    {"key": "Iron Shield",        "type": "armor", "value": 35,  "desc": "A round iron-banded wooden shield."},
    {"key": "Steel Greaves",      "type": "armor", "value": 45,  "desc": "Polished steel leg guards."},
    {"key": "Reinforced Helm",    "type": "armor", "value": 40,  "desc": "A steel helm with a protective nose guard."},
]

GOOD_CONSUMABLES = [
    {"key": "Health Potion",      "type": "consumable", "value": 15,  "desc": "A glowing red vial that restores vitality."},
    {"key": "Antidote Vial",      "type": "consumable", "value": 12,  "desc": "A bitter green liquid that neutralizes poisons."},
    {"key": "Travel Rations",     "type": "consumable", "value": 5,   "desc": "Dried meat, hard cheese, and waybread."},
    {"key": "Bandage Roll",       "type": "consumable", "value": 8,   "desc": "Clean linen strips for binding wounds."},
]

EVIL_WEAPONS = [
    {"key": "Demon-Forged Blade", "type": "weapon", "value": 150, "desc": "A jagged black blade pulsing with dark energy."},
    {"key": "Bone Cleaver",       "type": "weapon", "value": 90,  "desc": "A massive axe carved from the femur of a giant."},
    {"key": "Cursed Dagger",      "type": "weapon", "value": 85,  "desc": "A wickedly curved knife dripping with shadow."},
    {"key": "Shadow Staff",       "type": "weapon", "value": 100, "desc": "A twisted wooden staff tipped with a void stone."},
    {"key": "Rusted Greatsword",  "type": "weapon", "value": 70,  "desc": "A corroded but deadly two-handed sword."},
    {"key": "Spiked Flail",       "type": "weapon", "value": 95,  "desc": "A heavy iron ball on a chain, covered in rusted spikes."},
]

EVIL_ARMOR = [
    {"key": "Bone Plate",         "type": "armor", "value": 90,  "desc": "Armor forged from the fused skeletal remains of fallen warriors."},
    {"key": "Obsidian Plate",     "type": "armor", "value": 120, "desc": "Heavy armor crafted from volcanic dark stone."},
    {"key": "Shadow Cloak",       "type": "armor", "value": 60,  "desc": "A tattered cloak that seems to drink in the light."},
    {"key": "Demonhide Tunic",    "type": "armor", "value": 75,  "desc": "Armor stitched from the leathery hide of a pit fiend."},
    {"key": "Iron Shackles",      "type": "armor", "value": 25,  "desc": "Heavy manacles that serve as brutal forearm guards."},
]

EVIL_CONSUMABLES = [
    {"key": "Blood Vial",         "type": "consumable", "value": 30,  "desc": "A vial of thick crimson fluid that pulses with unholy vigor."},
    {"key": "Soul Shard",         "type": "consumable", "value": 50,  "desc": "A fractured crystal containing a trapped, wailing spirit."},
    {"key": "Black Bile Flask",   "type": "consumable", "value": 20,  "desc": "A flask of caustic black ichor that sizzles against glass."},
    {"key": "Bone Dust Pouch",    "type": "consumable", "value": 10,  "desc": "Finely ground bone dust used in dark rituals."},
]

DESERT_WEAPONS = [
    {"key": "Scimitar",           "type": "weapon", "value": 60,  "desc": "A curved desert blade with an ivory hilt."},
    {"key": "Nomad Bow",          "type": "weapon", "value": 50,  "desc": "A compact composite bow used by desert nomads."},
    {"key": "Khopesh",            "type": "weapon", "value": 75,  "desc": "A sickle-shaped sword of ancient design."},
    {"key": "Sand-Crusted Spear", "type": "weapon", "value": 40,  "desc": "A long spear with a blade etched by blowing sand."},
]

DESERT_ARMOR = [
    {"key": "Nomad Robes",        "type": "armor", "value": 25,  "desc": "Light layered robes that protect against heat and sand."},
    {"key": "Turban Wrap",        "type": "armor", "value": 15,  "desc": "A thick cloth headwrap shielding from the desert sun."},
    {"key": "Chitin Breastplate", "type": "armor", "value": 55,  "desc": "Armor crafted from the carapace of a giant desert scorpion."},
]

DESERT_CONSUMABLES = [
    {"key": "Water Flask",        "type": "consumable", "value": 10,  "desc": "Fresh water stored in a stitched leather skin."},
    {"key": "Antivenom Serum",    "type": "consumable", "value": 25,  "desc": "A milky serum that counteracts scorpion and serpent venom."},
    {"key": "Dried Dates",        "type": "consumable", "value": 4,   "desc": "Sweet, energy-rich dates from a desert oasis palm."},
]

FOREST_WEAPONS = [
    {"key": "Hunting Bow",        "type": "weapon", "value": 45,  "desc": "A well-crafted bow used by forest hunters."},
    {"key": "Woodsman Axe",       "type": "weapon", "value": 35,  "desc": "A heavy axe meant for felling trees and foes alike."},
    {"key": "Elm Longbow",        "type": "weapon", "value": 70,  "desc": "A tall longbow carved from ancient elm wood."},
    {"key": "Thorned Staff",      "type": "weapon", "value": 40,  "desc": "A gnarled wooden staff wrapped in thorny vines."},
]

FOREST_ARMOR = [
    {"key": "Hide Jerkin",        "type": "armor", "value": 20,  "desc": "A rough tunic made from cured animal hides."},
    {"key": "Bark Shield",        "type": "armor", "value": 15,  "desc": "A shield of magically hardened tree bark."},
    {"key": "Moss Cloak",         "type": "armor", "value": 30,  "desc": "A living cloak of soft moss that blends into the forest."},
]

FOREST_CONSUMABLES = [
    {"key": "Healing Herb",       "type": "consumable", "value": 10,  "desc": "A fragrant herb that speeds natural healing."},
    {"key": "Forest Berries",     "type": "consumable", "value": 3,   "desc": "A handful of sweet wild berries."},
    {"key": "Spring Water Vial",  "type": "consumable", "value": 8,   "desc": "Crystal-clear water from a forest spring."},
]


# ---------------------------------------------------------------------------
# 3. Mob & NPC Templates
# ---------------------------------------------------------------------------

# --- GOOD REGION CREATURES ---
GOOD_CREATURES = [
    {
        "key": "Wild Deer", "desc": "A graceful deer with soft brown eyes, watching cautiously.",
        "level": 1, "faction": "good", "aggro": False,
        "gold": (0, 3), "weapons": [], "armor": [], "consumables": [],
    },
    {
        "key": "Forest Rabbit", "desc": "A quick brown hare twitching its nose among the bushes.",
        "level": 1, "faction": "good", "aggro": False,
        "gold": (0, 1), "weapons": [], "armor": [], "consumables": [],
    },
    {
        "key": "Coyote", "desc": "A lean, tawny canine with sharp yellow eyes.",
        "level": 2, "faction": "good", "aggro": False,
        "gold": (1, 5), "weapons": [], "armor": [], "consumables": [],
    },
    {
        "key": "Great Elk", "desc": "A towering stag with a crown of majestic antlers.",
        "level": 3, "faction": "good", "aggro": False,
        "gold": (2, 8), "weapons": [], "armor": [], "consumables": [],
    },
    {
        "key": "Brown Bear", "desc": "A massive bear with thick fur and powerful claws.",
        "level": 5, "faction": "good", "aggro": True,
        "gold": (5, 15), "weapons": [], "armor": [], "consumables": [],
    },
    {
        "key": "Town Guard", "desc": "An armored guard in polished steel, watching over the area.",
        "level": 8, "faction": "good", "aggro": False,
        "gold": (10, 30),
        "weapons": [GOOD_WEAPONS[0], GOOD_WEAPONS[3]],  # Iron Longsword, Iron Mace
        "armor": [GOOD_ARMOR[0], GOOD_ARMOR[2]],          # Leather Armor, Iron Shield
        "consumables": [GOOD_CONSUMABLES[0]],              # Health Potion
    },
    {
        "key": "Militia Scout", "desc": "A local defender patrolling the perimeter with a keen eye.",
        "level": 4, "faction": "good", "aggro": False,
        "gold": (5, 20),
        "weapons": [GOOD_WEAPONS[2]],                      # Oak Shortbow
        "armor": [GOOD_ARMOR[0]],                          # Leather Armor
        "consumables": [GOOD_CONSUMABLES[2]],              # Travel Rations
    },
    {
        "key": "Paladin Squire", "desc": "A young squire training to become a holy knight.",
        "level": 6, "faction": "good", "aggro": False,
        "gold": (8, 25),
        "weapons": [GOOD_WEAPONS[1]],                      # Steel Broadsword
        "armor": [GOOD_ARMOR[1], GOOD_ARMOR[4]],           # Chainmail Hauberk, Reinforced Helm
        "consumables": [GOOD_CONSUMABLES[0]],              # Health Potion
    },
    {
        "key": "Farmhand", "desc": "A sturdy farmer taking a break from tending the fields.",
        "level": 2, "faction": "good", "aggro": False,
        "gold": (2, 8),
        "weapons": [GOOD_WEAPONS[5]],                      # Hunting Knife
        "armor": [],
        "consumables": [GOOD_CONSUMABLES[2]],              # Travel Rations
    },
    {
        "key": "Wild Boar", "desc": "A bristly, aggressive boar rooting through the undergrowth.",
        "level": 3, "faction": "good", "aggro": True,
        "gold": (1, 6), "weapons": [], "armor": [], "consumables": [],
    },
]

# --- EVIL REGION CREATURES ---
EVIL_CREATURES = [
    {
        "key": "Skeletal Warrior", "desc": "A reanimated skeleton clutching a rusted blade, eye sockets glowing red.",
        "level": 4, "faction": "evil", "aggro": True,
        "gold": (5, 20),
        "weapons": [EVIL_WEAPONS[4]],                      # Rusted Greatsword
        "armor": [EVIL_ARMOR[0]],                          # Bone Plate
        "consumables": [EVIL_CONSUMABLES[3]],              # Bone Dust Pouch
    },
    {
        "key": "Bone Archer", "desc": "A skeletal archer with glowing crimson eye sockets, arrows nocked.",
        "level": 5, "faction": "evil", "aggro": True,
        "gold": (8, 25),
        "weapons": [EVIL_WEAPONS[2]],                      # Cursed Dagger
        "armor": [EVIL_ARMOR[2]],                          # Shadow Cloak
        "consumables": [EVIL_CONSUMABLES[3]],              # Bone Dust Pouch
    },
    {
        "key": "Hellhound", "desc": "A massive black wolf with skin like cracked lava and fangs dripping molten fire.",
        "level": 6, "faction": "evil", "aggro": True,
        "gold": (10, 35),
        "weapons": [],
        "armor": [EVIL_ARMOR[3]],                          # Demonhide Tunic
        "consumables": [EVIL_CONSUMABLES[2]],              # Black Bile Flask
    },
    {
        "key": "Pit Demon", "desc": "A towering fiend of muscle and horn, encased in smoldering iron plates.",
        "level": 12, "faction": "evil", "aggro": True,
        "gold": (30, 80),
        "weapons": [EVIL_WEAPONS[0], EVIL_WEAPONS[5]],     # Demon-Forged Blade, Spiked Flail
        "armor": [EVIL_ARMOR[1], EVIL_ARMOR[4]],           # Obsidian Plate, Iron Shackles
        "consumables": [EVIL_CONSUMABLES[0], EVIL_CONSUMABLES[1]],  # Blood Vial, Soul Shard
    },
    {
        "key": "Infernal Cultist", "desc": "A hooded figure in tattered robes, chanting dark incantations.",
        "level": 7, "faction": "evil", "aggro": True,
        "gold": (12, 40),
        "weapons": [EVIL_WEAPONS[3]],                      # Shadow Staff
        "armor": [EVIL_ARMOR[2]],                          # Shadow Cloak
        "consumables": [EVIL_CONSUMABLES[0], EVIL_CONSUMABLES[1]],  # Blood Vial, Soul Shard
    },
    {
        "key": "Wraith", "desc": "A translucent, floating specter with hollow eyes and an icy aura.",
        "level": 9, "faction": "evil", "aggro": True,
        "gold": (15, 45),
        "weapons": [],
        "armor": [EVIL_ARMOR[2]],                          # Shadow Cloak
        "consumables": [EVIL_CONSUMABLES[1]],              # Soul Shard
    },
    {
        "key": "Demon Imp", "desc": "A small, winged creature with needle-sharp teeth and a barbed tail.",
        "level": 3, "faction": "evil", "aggro": True,
        "gold": (3, 12),
        "weapons": [EVIL_WEAPONS[2]],                      # Cursed Dagger
        "armor": [],
        "consumables": [EVIL_CONSUMABLES[2]],              # Black Bile Flask
    },
    {
        "key": "Undead Knight", "desc": "A fallen knight in blackened armor, animated by dark magic.",
        "level": 10, "faction": "evil", "aggro": True,
        "gold": (20, 60),
        "weapons": [EVIL_WEAPONS[0], EVIL_WEAPONS[1]],     # Demon-Forged Blade, Bone Cleaver
        "armor": [EVIL_ARMOR[0], EVIL_ARMOR[1]],           # Bone Plate, Obsidian Plate
        "consumables": [EVIL_CONSUMABLES[0]],              # Blood Vial
    },
    {
        "key": "Shadow Stalker", "desc": "A lithe, panther-like beast made of living shadow.",
        "level": 8, "faction": "evil", "aggro": True,
        "gold": (10, 30),
        "weapons": [],
        "armor": [EVIL_ARMOR[3]],                          # Demonhide Tunic
        "consumables": [EVIL_CONSUMABLES[1]],              # Soul Shard
    },
    {
        "key": "Corrupted Peasant", "desc": "A once-innocent villager twisted by demonic corruption, shambling aimlessly.",
        "level": 2, "faction": "evil", "aggro": True,
        "gold": (1, 5),
        "weapons": [EVIL_WEAPONS[4]],                      # Rusted Greatsword
        "armor": [],
        "consumables": [],
    },
]

# --- DESERT CREATURES (Neutral - mix of good and evil) ---
DESERT_GOOD_CREATURES = [
    {
        "key": "Desert Camel", "desc": "A sturdy, humped pack animal chewing calmly on dried scrub.",
        "level": 2, "faction": "good", "aggro": False,
        "gold": (0, 4), "weapons": [], "armor": [], "consumables": [DESERT_CONSUMABLES[0]],
    },
    {
        "key": "Sand Gazelle", "desc": "A swift, elegant creature leaping gracefully across the dunes.",
        "level": 2, "faction": "good", "aggro": False,
        "gold": (0, 3), "weapons": [], "armor": [], "consumables": [],
    },
    {
        "key": "Nomad Scout", "desc": "A weathered desert traveler wrapped in light robes, keeping careful watch.",
        "level": 5, "faction": "good", "aggro": False,
        "gold": (8, 25),
        "weapons": [DESERT_WEAPONS[0]],                    # Scimitar
        "armor": [DESERT_ARMOR[0]],                        # Nomad Robes
        "consumables": [DESERT_CONSUMABLES[0], DESERT_CONSUMABLES[2]],
    },
    {
        "key": "Oasis Herbalist", "desc": "A wise woman collecting rare desert herbs near a watering hole.",
        "level": 3, "faction": "good", "aggro": False,
        "gold": (5, 15),
        "weapons": [DESERT_WEAPONS[3]],                    # Sand-Crusted Spear
        "armor": [DESERT_ARMOR[0]],                        # Nomad Robes
        "consumables": [DESERT_CONSUMABLES[1], DESERT_CONSUMABLES[2]],
    },
]

DESERT_EVIL_CREATURES = [
    {
        "key": "Dune Scorpion", "desc": "A massive arachnid the size of a dog, its venomous stinger twitching.",
        "level": 5, "faction": "evil", "aggro": True,
        "gold": (5, 18),
        "weapons": [],
        "armor": [DESERT_ARMOR[2]],                        # Chitin Breastplate
        "consumables": [DESERT_CONSUMABLES[1]],            # Antivenom Serum
    },
    {
        "key": "Dust Wraith", "desc": "A swirling vortex of biting sand and dark energy, moaning with lost voices.",
        "level": 8, "faction": "evil", "aggro": True,
        "gold": (12, 35),
        "weapons": [],
        "armor": [DESERT_ARMOR[0]],                        # Nomad Robes
        "consumables": [EVIL_CONSUMABLES[1]],              # Soul Shard
    },
    {
        "key": "Skeletal Nomad", "desc": "Sun-bleached bones of a desert warrior, still clutching a curved scimitar.",
        "level": 6, "faction": "evil", "aggro": True,
        "gold": (8, 28),
        "weapons": [DESERT_WEAPONS[0], DESERT_WEAPONS[2]], # Scimitar, Khopesh
        "armor": [DESERT_ARMOR[0], DESERT_ARMOR[1]],       # Nomad Robes, Turban Wrap
        "consumables": [DESERT_CONSUMABLES[0]],
    },
    {
        "key": "Sand Wyrm Hatchling", "desc": "A juvenile sand wyrm, its segmented body undulating beneath the dunes.",
        "level": 7, "faction": "evil", "aggro": True,
        "gold": (10, 30),
        "weapons": [],
        "armor": [DESERT_ARMOR[2]],                        # Chitin Breastplate
        "consumables": [DESERT_CONSUMABLES[1]],
    },
    {
        "key": "Cactus Stalker", "desc": "A gaunt, humanoid creature with thorny, green-brown skin blending into the scrub.",
        "level": 4, "faction": "evil", "aggro": True,
        "gold": (4, 15),
        "weapons": [DESERT_WEAPONS[3]],                    # Sand-Crusted Spear
        "armor": [],
        "consumables": [DESERT_CONSUMABLES[2]],
    },
]

# --- FOREST CREATURES (Neutral - mix of good and evil) ---
FOREST_GOOD_CREATURES = [
    {
        "key": "Forest Stag", "desc": "A magnificent stag with a full rack of antlers, standing proud among the pines.",
        "level": 3, "faction": "good", "aggro": False,
        "gold": (0, 5), "weapons": [], "armor": [], "consumables": [],
    },
    {
        "key": "Woodsman", "desc": "A rugged hunter in furs, axe resting on his shoulder.",
        "level": 5, "faction": "good", "aggro": False,
        "gold": (6, 20),
        "weapons": [FOREST_WEAPONS[1]],                    # Woodsman Axe
        "armor": [FOREST_ARMOR[0]],                        # Hide Jerkin
        "consumables": [FOREST_CONSUMABLES[0], FOREST_CONSUMABLES[1]],
    },
    {
        "key": "Pine Marten", "desc": "A sleek, agile weasel-like creature darting through the branches.",
        "level": 1, "faction": "good", "aggro": False,
        "gold": (0, 2), "weapons": [], "armor": [], "consumables": [],
    },
    {
        "key": "Forest Hermit", "desc": "An old man in moss-covered robes, living in harmony with the ancient woods.",
        "level": 4, "faction": "good", "aggro": False,
        "gold": (4, 15),
        "weapons": [FOREST_WEAPONS[3]],                    # Thorned Staff
        "armor": [FOREST_ARMOR[2]],                        # Moss Cloak
        "consumables": [FOREST_CONSUMABLES[0], FOREST_CONSUMABLES[2]],
    },
    {
        "key": "Giant Owl", "desc": "A massive owl with silent wings and piercing golden eyes.",
        "level": 4, "faction": "good", "aggro": False,
        "gold": (2, 8), "weapons": [], "armor": [], "consumables": [],
    },
]

FOREST_EVIL_CREATURES = [
    {
        "key": "Timber Wolf", "desc": "A large grey wolf with sharp yellow eyes and bared fangs.",
        "level": 3, "faction": "evil", "aggro": True,
        "gold": (2, 10), "weapons": [], "armor": [], "consumables": [],
    },
    {
        "key": "Corrupted Treant", "desc": "A once-noble tree spirit, now twisted by dark magic, its bark oozing black sap.",
        "level": 9, "faction": "evil", "aggro": True,
        "gold": (15, 40),
        "weapons": [FOREST_WEAPONS[3]],                    # Thorned Staff
        "armor": [FOREST_ARMOR[1], FOREST_ARMOR[2]],       # Bark Shield, Moss Cloak
        "consumables": [EVIL_CONSUMABLES[2]],              # Black Bile Flask
    },
    {
        "key": "Shadow Panther", "desc": "A sleek black panther that melts into the shadows, eyes gleaming.",
        "level": 6, "faction": "evil", "aggro": True,
        "gold": (8, 25),
        "weapons": [],
        "armor": [EVIL_ARMOR[3]],                          # Demonhide Tunic
        "consumables": [],
    },
    {
        "key": "Forest Witch", "desc": "A crone in dark rags, brewing foul concoctions in a bubbling cauldron.",
        "level": 7, "faction": "evil", "aggro": True,
        "gold": (10, 35),
        "weapons": [EVIL_WEAPONS[3]],                      # Shadow Staff
        "armor": [EVIL_ARMOR[2]],                          # Shadow Cloak
        "consumables": [EVIL_CONSUMABLES[0], EVIL_CONSUMABLES[2]],
    },
    {
        "key": "Vine Horror", "desc": "A writhing mass of thorned vines animated by a malevolent spirit.",
        "level": 5, "faction": "evil", "aggro": True,
        "gold": (5, 18),
        "weapons": [],
        "armor": [FOREST_ARMOR[2]],                        # Moss Cloak
        "consumables": [FOREST_CONSUMABLES[0]],
    },
]

# --- TOWN / CITY NPCs & SHOPKEEPERS ---
GOOD_TOWN_NPCS = [
    {
        "key": "Royal Herald", "desc": "A messenger in fine livery, announcing decrees to all who pass.",
        "type": "npc",
    },
    {
        "key": "Wandering Bard", "desc": "A minstrel strumming a lute and singing tales of heroic deeds.",
        "type": "npc",
    },
    {
        "key": "Cathedral Acolyte", "desc": "A young acolyte in white robes, tending to the sanctum's eternal flame.",
        "type": "npc",
    },
    {
        "key": "Stable Master", "desc": "A weathered man brushing down a strong destrier, the smell of hay thick around him.",
        "type": "npc",
    },
    {
        "key": "Town Crier", "desc": "A loud-voiced man with a bell, shouting the day's news to the square.",
        "type": "npc",
    },
    {
        "key": "Town Blacksmith", "desc": "A muscular smith with soot-stained hands, hammering glowing metal on an anvil.",
        "type": "shop",
        "items": [GOOD_WEAPONS[0], GOOD_WEAPONS[1], GOOD_WEAPONS[3],
                  GOOD_ARMOR[0], GOOD_ARMOR[1], GOOD_ARMOR[2], GOOD_ARMOR[4]],
    },
    {
        "key": "Alchemist Vane", "desc": "A scholarly woman surrounded by bubbling vials and dusty tomes.",
        "type": "shop",
        "items": [GOOD_CONSUMABLES[0], GOOD_CONSUMABLES[1], GOOD_CONSUMABLES[3],
                  EVIL_CONSUMABLES[0], DESERT_CONSUMABLES[1]],
    },
    {
        "key": "Innkeeper Marla", "desc": "A plump, cheerful woman wiping down a polished oak bar.",
        "type": "shop",
        "items": [GOOD_CONSUMABLES[2], GOOD_CONSUMABLES[3], FOREST_CONSUMABLES[1], FOREST_CONSUMABLES[2]],
    },
    {
        "key": "Fletcher Corwin", "desc": "A wiry man surrounded by bundles of arrows and unfinished bow staves.",
        "type": "shop",
        "items": [GOOD_WEAPONS[2], GOOD_WEAPONS[5], FOREST_WEAPONS[0], FOREST_WEAPONS[2]],
    },
]

EVIL_TOWN_NPCS = [
    {
        "key": "Cult Overseer", "desc": "A robed figure with burning eyes, directing slaves with a barbed whip.",
        "type": "npc",
    },
    {
        "key": "Tortured Prisoner", "desc": "A gaunt, chained captive muttering prayers for a death that will not come.",
        "type": "npc",
    },
    {
        "key": "Demon Herald", "desc": "A winged imp screeching proclamations of the Dark Lord's will.",
        "type": "npc",
    },
    {
        "key": "Soul Peddler", "desc": "A hunched creature with too many fingers, trading in trapped souls.",
        "type": "npc",
    },
    {
        "key": "Malakor the Void Trader", "desc": "A cloaked figure whose eyes glow with eerie purple light.",
        "type": "shop",
        "items": [EVIL_WEAPONS[0], EVIL_WEAPONS[1], EVIL_WEAPONS[3],
                  EVIL_ARMOR[0], EVIL_ARMOR[1], EVIL_ARMOR[2]],
    },
    {
        "key": "Blight Alchemist", "desc": "A plague-ridden alchemist brewing toxins in a cracked cauldron.",
        "type": "shop",
        "items": [EVIL_CONSUMABLES[0], EVIL_CONSUMABLES[1], EVIL_CONSUMABLES[2], EVIL_CONSUMABLES[3]],
    },
    {
        "key": "Flesh Stitcher", "desc": "A grotesque surgeon stitching together body parts on a blood-soaked table.",
        "type": "shop",
        "items": [EVIL_ARMOR[0], EVIL_ARMOR[3], EVIL_ARMOR[4], EVIL_CONSUMABLES[0]],
    },
]

DESERT_TOWN_NPCS = [
    {
        "key": "Oasis Merchant", "desc": "A sun-beaten trader with a laden camel, selling exotic wares.",
        "type": "shop",
        "items": [DESERT_WEAPONS[0], DESERT_WEAPONS[1], DESERT_WEAPONS[2],
                  DESERT_ARMOR[0], DESERT_ARMOR[1],
                  DESERT_CONSUMABLES[0], DESERT_CONSUMABLES[1], DESERT_CONSUMABLES[2]],
    },
    {
        "key": "Nomad Elder", "desc": "A wizened nomad chief sharing tales of the shifting sands.",
        "type": "npc",
    },
    {
        "key": "Desert Guide", "desc": "A scarred tracker who knows every safe path through the wastes.",
        "type": "npc",
    },
]

FOREST_TOWN_NPCS = [
    {
        "key": "Herbalist Sage", "desc": "An ancient woman who knows the secret properties of every forest plant.",
        "type": "shop",
        "items": [FOREST_CONSUMABLES[0], FOREST_CONSUMABLES[1], FOREST_CONSUMABLES[2],
                  GOOD_CONSUMABLES[0], GOOD_CONSUMABLES[1]],
    },
    {
        "key": "Ranger Captain", "desc": "A grizzled ranger who has walked every trail in the Boreal Forest.",
        "type": "npc",
    },
    {
        "key": "Ruins Scholar", "desc": "A dusty academic studying the ancient carvings of the hidden ruins.",
        "type": "npc",
    },
]


# ---------------------------------------------------------------------------
# 4. Helper Functions
# ---------------------------------------------------------------------------

def create_item(tmpl, loc):
    """Create an item from a template dict and place it in a location."""
    item = create_object(MUDItem, key=tmpl["key"], location=loc)
    item.db.desc = tmpl["desc"]
    item.db.value = tmpl["value"]
    item.db.item_type = tmpl["type"]
    return item


def spawn_mob_from_template(tmpl, room):
    """
    Spawn a mob from a template dict into a room.
    Equips the mob with weapons/armor and gives consumables + gold.
    """
    mob = create_object(Mob, key=tmpl["key"], location=room)
    mob.db.desc = tmpl["desc"]
    mob.db.level = tmpl["level"]
    mob.db.faction = tmpl.get("faction", "neutral")
    mob.db.aggro = tmpl.get("aggro", False)

    # Assign random gold within the template's range
    gold_range = tmpl.get("gold", (0, 0))
    mob.db.gold = random.randint(gold_range[0], gold_range[1])

    # Equip weapons
    for weapon_tmpl in tmpl.get("weapons", []):
        item = create_item(weapon_tmpl, loc=mob)
        item.db.is_equipped = True

    # Equip armor
    for armor_tmpl in tmpl.get("armor", []):
        item = create_item(armor_tmpl, loc=mob)
        item.db.is_equipped = True

    # Give consumables (not equipped, just in inventory)
    for consumable_tmpl in tmpl.get("consumables", []):
        create_item(consumable_tmpl, loc=mob)

    return mob


def spawn_town_npc(tmpl, room):
    """Spawn a town NPC or shopkeeper from a template."""
    if tmpl["type"] == "shop":
        vendor = create_object(Shopkeeper, key=tmpl["key"], location=room)
        vendor.db.desc = tmpl["desc"]
        vendor.db.inventory_stock = [create_item(i, loc=vendor) for i in tmpl["items"]]
        return vendor
    else:
        npc = create_object(NPC, key=tmpl["key"], location=room)
        npc.db.desc = tmpl["desc"]
        return npc


# ---------------------------------------------------------------------------
# 5. Room Classification
# ---------------------------------------------------------------------------

def classify_room(room_name):
    """
    Classify a room into a region type based on its name.
    Returns one of: 'good_town', 'good_wild', 'evil_town', 'evil_wild',
                    'desert', 'forest', 'unknown'
    """
    name = room_name.lower()

    # --- GOOD TOWN: Aethelgard city rooms ---
    good_town_keywords = [
        "aethelgard", "sanctum", "cathedral", "sunlit square",
        "paladin training", "city gates",
    ]
    if any(k in name for k in good_town_keywords):
        return "good_town"

    # --- GOOD WILDERNESS: Farmland, hills, guard outpost ---
    good_wild_keywords = [
        "rolling green hills", "lush farmland", "guard outpost",
    ]
    if any(k in name for k in good_wild_keywords):
        return "good_wild"

    # --- EVIL TOWN: Gorgoroth city rooms ---
    evil_town_keywords = [
        "gorgoroth", "blood forge", "iron chains", "volcanic spire",
        "subterranean barracks", "gates of gorgoroth",
    ]
    if any(k in name for k in evil_town_keywords):
        return "evil_town"

    # --- EVIL WILDERNESS: Ashen wastes, canyons, encampment ---
    evil_wild_keywords = [
        "ashen waste", "jagged obsidian", "scorched encampment",
    ]
    if any(k in name for k in evil_wild_keywords):
        return "evil_wild"

    # --- DESERT (Neutral): Scorched Desert rooms ---
    desert_keywords = [
        "scorched desert", "cracked salt flat", "towering sand dune",
        "abandoned oasis", "eastern edge", "western edge",
    ]
    if any(k in name for k in desert_keywords):
        return "desert"

    # --- FOREST (Neutral): Boreal Forest rooms ---
    forest_keywords = [
        "boreal forest", "ancient trade path", "giant pines",
        "mystical glade", "hidden ruins",
    ]
    if any(k in name for k in forest_keywords):
        return "forest"

    return "unknown"


# ---------------------------------------------------------------------------
# 6. Main Population Engine
# ---------------------------------------------------------------------------

def populate_all():
    """
    Scan every room in the realm and populate it with appropriate NPCs,
    shopkeepers, and mobs based on the room's region classification.

    Spawn rules per room:
      - Good towns:   1-2 NPCs/shopkeepers, 1-2 guards
      - Good wild:    1-3 good creatures
      - Evil towns:   1-2 NPCs/shopkeepers, 1-2 demonic guards
      - Evil wild:    2-4 evil creatures
      - Desert:       1-3 mixed good/evil desert creatures
      - Forest:       1-3 mixed good/evil forest creatures
    """
    print("=" * 60)
    print("  REALM POPULATION ENGINE")
    print("=" * 60)

    # Fetch all Room objects via Django ORM
    all_objects = list(ObjectDB.objects.all())
    rooms = [o for o in all_objects
             if o.__class__.__name__ == "Room"]

    total_rooms = len(rooms)
    print(f"\nFound {total_rooms} rooms. Beginning population...\n")

    stats = {
        "good_town": 0, "good_wild": 0,
        "evil_town": 0, "evil_wild": 0,
        "desert": 0, "forest": 0, "unknown": 0,
        "total_npcs": 0, "total_mobs": 0, "total_shopkeepers": 0,
    }

    for room in rooms:
        r_name = room.key
        region = classify_room(r_name)

        if region == "good_town":
            stats["good_town"] += 1
            # Spawn 1-2 town NPCs/shopkeepers
            for _ in range(random.randint(1, 2)):
                tmpl = random.choice(GOOD_TOWN_NPCS)
                spawn_town_npc(tmpl, room)
                if tmpl["type"] == "shop":
                    stats["total_shopkeepers"] += 1
                else:
                    stats["total_npcs"] += 1
            # Spawn 1-2 guards
            for _ in range(random.randint(1, 2)):
                guard_templates = [t for t in GOOD_CREATURES
                                   if t["key"] in ("Town Guard", "Paladin Squire", "Militia Scout")]
                tmpl = random.choice(guard_templates)
                spawn_mob_from_template(tmpl, room)
                stats["total_mobs"] += 1

        elif region == "good_wild":
            stats["good_wild"] += 1
            # Spawn 1-3 good creatures
            count = random.randint(1, 3)
            for _ in range(count):
                tmpl = random.choice(GOOD_CREATURES)
                spawn_mob_from_template(tmpl, room)
                stats["total_mobs"] += 1

        elif region == "evil_town":
            stats["evil_town"] += 1
            # Spawn 1-2 evil NPCs/shopkeepers
            for _ in range(random.randint(1, 2)):
                tmpl = random.choice(EVIL_TOWN_NPCS)
                spawn_town_npc(tmpl, room)
                if tmpl["type"] == "shop":
                    stats["total_shopkeepers"] += 1
                else:
                    stats["total_npcs"] += 1
            # Spawn 1-2 demonic guards
            for _ in range(random.randint(1, 2)):
                guard_templates = [t for t in EVIL_CREATURES
                                   if t["key"] in ("Undead Knight", "Pit Demon", "Skeletal Warrior")]
                tmpl = random.choice(guard_templates)
                spawn_mob_from_template(tmpl, room)
                stats["total_mobs"] += 1

        elif region == "evil_wild":
            stats["evil_wild"] += 1
            # Spawn 2-4 evil creatures (denser evil wilderness)
            count = random.randint(2, 4)
            for _ in range(count):
                tmpl = random.choice(EVIL_CREATURES)
                spawn_mob_from_template(tmpl, room)
                stats["total_mobs"] += 1

        elif region == "desert":
            stats["desert"] += 1
            # Spawn 1-3 mixed desert creatures
            count = random.randint(1, 3)
            for _ in range(count):
                # 50/50 good or evil desert creature
                if random.random() < 0.5:
                    tmpl = random.choice(DESERT_GOOD_CREATURES)
                else:
                    tmpl = random.choice(DESERT_EVIL_CREATURES)
                spawn_mob_from_template(tmpl, room)
                stats["total_mobs"] += 1
            # Oasis gets a merchant
            if "oasis" in r_name.lower():
                tmpl = random.choice(DESERT_TOWN_NPCS)
                spawn_town_npc(tmpl, room)
                if tmpl["type"] == "shop":
                    stats["total_shopkeepers"] += 1
                else:
                    stats["total_npcs"] += 1

        elif region == "forest":
            stats["forest"] += 1
            # Spawn 1-3 mixed forest creatures
            count = random.randint(1, 3)
            for _ in range(count):
                # 50/50 good or evil forest creature
                if random.random() < 0.5:
                    tmpl = random.choice(FOREST_GOOD_CREATURES)
                else:
                    tmpl = random.choice(FOREST_EVIL_CREATURES)
                spawn_mob_from_template(tmpl, room)
                stats["total_mobs"] += 1
            # Ruins and glades get special NPCs
            if any(k in r_name.lower() for k in ("hidden ruins", "mystical glade")):
                tmpl = random.choice(FOREST_TOWN_NPCS)
                spawn_town_npc(tmpl, room)
                if tmpl["type"] == "shop":
                    stats["total_shopkeepers"] += 1
                else:
                    stats["total_npcs"] += 1

        else:
            stats["unknown"] += 1

    # --- Summary ---
    print("=" * 60)
    print("  POPULATION COMPLETE")
    print("=" * 60)
    print(f"  Rooms processed:        {total_rooms}")
    print(f"  Good towns:             {stats['good_town']}")
    print(f"  Good wilderness:        {stats['good_wild']}")
    print(f"  Evil towns:             {stats['evil_town']}")
    print(f"  Evil wilderness:        {stats['evil_wild']}")
    print(f"  Desert (neutral):       {stats['desert']}")
    print(f"  Forest (neutral):       {stats['forest']}")
    if stats["unknown"]:
        print(f"  Unclassified:           {stats['unknown']}")
    print(f"  ---")
    print(f"  Total NPCs spawned:     {stats['total_npcs']}")
    print(f"  Total Shopkeepers:      {stats['total_shopkeepers']}")
    print(f"  Total Mobs spawned:     {stats['total_mobs']}")
    print(f"  Grand total entities:   {stats['total_npcs'] + stats['total_shopkeepers'] + stats['total_mobs']}")
    print("=" * 60)


def clear_all_mobs():
    """
    Destroy all previously spawned mobs, NPCs, shopkeepers, and items
    that were created by this population script. Safe to run before
    re-populating to avoid duplicates.
    """
    print("Clearing existing population...")
    all_objects = list(ObjectDB.objects.all())
    destroyed = 0

    for obj in all_objects:
        # Check if it's one of our population typeclasses
        typeclass = getattr(obj, 'typeclass_path', '')
        if typeclass.endswith(("Mob", "NPC", "Shopkeeper", "MUDItem")):
            # Only delete objects that are in rooms (not in player inventories)
            if hasattr(obj, 'location') and obj.location:
                loc_type = getattr(obj.location, 'typeclass_path', '')
                if loc_type.endswith("Room"):
                    obj.delete()
                    destroyed += 1

    print(f"Destroyed {destroyed} entities.")
    return destroyed


def status():
    """
    Print a summary of the current realm population.
    Useful for checking what's already spawned.
    """
    all_objects = list(ObjectDB.objects.all())
    rooms = [o for o in all_objects
             if o.__class__.__name__ == "Room"]

    mobs = [o for o in all_objects
            if hasattr(o, 'typeclass_path') and o.typeclass_path.endswith("Mob")]
    npcs = [o for o in all_objects
            if hasattr(o, 'typeclass_path') and o.typeclass_path.endswith("NPC")]
    shops = [o for o in all_objects
             if hasattr(o, 'typeclass_path') and o.typeclass_path.endswith("Shopkeeper")]

    print(f"Rooms:       {len(rooms)}")
    print(f"Mobs:        {len(mobs)}")
    print(f"NPCs:        {len(npcs)}")
    print(f"Shopkeepers: {len(shops)}")
    print(f"Total entities: {len(mobs) + len(npcs) + len(shops)}")

    # Faction breakdown
    good_mobs = [m for m in mobs if getattr(m.db, 'faction', '') == 'good']
    evil_mobs = [m for m in mobs if getattr(m.db, 'faction', '') == 'evil']
    neutral_mobs = [m for m in mobs if getattr(m.db, 'faction', '') == 'neutral']
    print(f"  Good mobs:    {len(good_mobs)}")
    print(f"  Evil mobs:    {len(evil_mobs)}")
    print(f"  Neutral mobs: {len(neutral_mobs)}")

    # Gold total
    total_gold = sum(getattr(m.db, 'gold', 0) for m in mobs)
    print(f"  Total mob gold in realm: {total_gold}")