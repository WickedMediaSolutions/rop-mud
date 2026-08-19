"""
MajorMUD-Inspired Item Generator for 'rop'
Supports 16 Races (8 Good / 8 Evil) and 10 Classes across 14 Equipment Slots.
"""

import random
from django.db import transaction
from evennia import create_object
from evennia.objects.objects import DefaultObject
from world.rules import RACES, CLASSES

# ---------------------------------------------------------------------------
# CONSTANTS & TIERS
# ---------------------------------------------------------------------------

SLOTS = [
    "head", "neck", "ears", "finger1", "finger2", 
    "wrists", "torso", "belt", "legs", "feet", 
    "robe", "main_hand", "off_hand", "two_hand"
]

TIERS = {
    1: {"level_min": 1,  "level_max": 10, "stat_mod": (1, 5),   "ac_mod": (1, 4),   "dmg_mod": (2, 8)},
    2: {"level_min": 11, "level_max": 25, "stat_mod": (6, 12),  "ac_mod": (5, 10),  "dmg_mod": (9, 18)},
    3: {"level_min": 26, "level_max": 40, "stat_mod": (13, 22), "ac_mod": (11, 18), "dmg_mod": (19, 32)},
    4: {"level_min": 41, "level_max": 50, "stat_mod": (23, 35), "ac_mod": (19, 28), "dmg_mod": (33, 50)}
}

# ---------------------------------------------------------------------------
# PREFIXES & CLASS WEAPON TABLES
# ---------------------------------------------------------------------------

PREFIXES = {
    "Warrior":     ["Ironclad", "Bloodforged", "Gladiator's", "Heavy", "Dreadnought's", "Valorous"],
    "Paladin":     ["Holy", "Radiant", "Sunforged", "Blessed", "Sanctified", "Righteous"],
    "Cleric":      ["Devout", "Sacred", "Divine", "Graceful", "Anointed", "Hallowed"],
    "Mage":        ["Arcane", "Ethereal", "Rune-Carved", "Astral", "Sorcerer's", "Spellwoven"],
    "Rogue":       ["Shadowy", "Venomous", "Silent", "Nightstalker's", "Sly", "Phantom"],
    "Warlock":     ["Corrupted", "Hellfire", "Abyssal", "Demon-Forged", "Malevolent", "Void-Touched"],
    "Druid":       ["Sylvan", "Verdant", "Wildheart", "Bark-Knotted", "Primal", "Nature's"],
    "Ranger":      ["Windrunner's", "Hunter's", "Pathfinder's", "Stalker's", "Keen", "Swift"],
    "Monk":        ["Iron-Fist", "Zenith", "Flowing", "Ashen-Hand", "Disciplined", "Wind-Walker"],
    "Necromancer": ["Blighted", "Bone-Carved", "Grave-Bound", "Soul-Drainer", "Spectral", "Rotting"]
}

SUFFIXES = [
    "of Power", "of the Bear", "of the Falcon", "of Might", "of the Abyssal Void",
    "of the Sanctum", "of Vitality", "of Destruction", "of Wisdom", "of Precision",
    "of the Phoenix", "of Dread", "of the Titan", "of Storms", "of Shadow"
]

WEAPONS_BY_CLASS = {
    "Warrior":     [("Longsword", "main_hand"), ("Battleaxe", "main_hand"), ("Greatsword", "two_hand"), ("Warhammer", "two_hand")],
    "Paladin":     [("Holy Avenger", "two_hand"), ("Sunblade", "main_hand"), ("Blessed Morningstar", "main_hand")],
    "Cleric":      [("Heavy Mace", "main_hand"), ("Judgement Flail", "main_hand"), ("Sanctified Scepter", "main_hand")],
    "Mage":        [("Runed Staff", "two_hand"), ("Spellfire Wand", "main_hand"), ("Arcane Dagger", "main_hand")],
    "Rogue":       [("Shadow Dagger", "main_hand"), ("Stiletto", "main_hand"), ("Shortsword of Venom", "main_hand")],
    "Warlock":     [("Soul-Stealer Scythe", "two_hand"), ("Demon Tooth Dagger", "main_hand"), ("Void Wand", "main_hand")],
    "Druid":       [("Ironwood Staff", "two_hand"), ("Primal Sickle", "main_hand"), ("Oak Club", "main_hand")],
    "Ranger":      [("Composite Longbow", "two_hand"), ("Hunting Recurve", "two_hand"), ("Twin Hunting Daggers", "main_hand")],
    "Monk":        [("Iron Cestus", "main_hand"), ("Quarterstaff of Balance", "two_hand"), ("Weighted Knuckles", "main_hand")],
    "Necromancer": [("Bone Scepter", "main_hand"), ("Gravedigger Dagger", "main_hand"), ("Blighted Staff", "two_hand")]
}

ARMOR_BY_SLOT = {
    "head":     ["Helmet", "Coif", "Circlet", "Crown", "Greathelm", "Hood", "Mask"],
    "neck":     ["Amulet", "Pendant", "Torc", "Choker", "Necklace"],
    "ears":     ["Earring", "Ear Cuff", "Stud", "Ear Hoop"],
    "finger1":  ["Ring", "Band", "Signet", "Loop"],
    "finger2":  ["Ring", "Band", "Signet", "Loop"],
    "wrists":   ["Bracers", "Vambraces", "Wristguards", "Bangles"],
    "torso":    ["Breastplate", "Hauberk", "Tunic", "Cuirass", "Vestment", "Chainmail"],
    "belt":     ["Girdle", "Belt", "Cinch", "Sash", "Waistguard"],
    "legs":     ["Greaves", "Leggings", "Chausses", "Pants", "Plateguards"],
    "feet":     ["Boots", "Sabatons", "Treads", "Sandals", "Greaves"],
    "robe":     ["Vestment Robe", "Arcane Mantle", "Silk Robe", "Shadow Cloak Robe", "Ethereal Vesture"],
    "off_hand": ["Tower Shield", "Kite Shield", "Buckler", "Tome of Power", "Aegis", "Skull Orb"]
}

FOOD_AND_CONSUMABLES = [
    # Good / Neutral Rations
    {"key": "Dried Salted Ration", "type": "food", "heal": 15, "desc": "A tough piece of salted meat that restores minor health."},
    {"key": "Roast Boar Meat", "type": "food", "heal": 40, "desc": "Hearty roast meat favored by travelers and adventurers."},
    {"key": "Elven Waybread", "type": "food", "heal": 80, "desc": "Nutritious baked bread capable of sustaining long journeys."},
    {"key": "Flask of Dwarven Ale", "type": "drink", "heal": 25, "desc": "Strong dwarven brew that restores vitality."},
    {"key": "Moonberry Juice", "type": "drink", "heal": 60, "desc": "A glowing sweet nectar that refreshes health and focus."},
    
    # Evil Rations
    {"key": "Charred Meat Chunk", "type": "food", "heal": 35, "desc": "A coarse chunk of roasted beast meat popular in Gorgoroth."},
    {"key": "Dragon Steak", "type": "food", "heal": 150, "desc": "A rare, spicy delicacy that restores high amounts of health."},
    {"key": "Blood-Wine Horn", "type": "drink", "heal": 75, "desc": "A viscous dark brew favored by Gorgoroth warriors."},
    
    # Potions & Elixirs
    {"key": "Minor Health Potion", "type": "potion", "heal": 50, "desc": "A small glass vial filled with glowing red liquid."},
    {"key": "Greater Health Potion", "type": "potion", "heal": 150, "desc": "A potent red elixir that seals deep wounds."},
    {"key": "Superior Health Potion", "type": "potion", "heal": 350, "desc": "An intoxicating crimson draught capable of mending vital injuries."},
    {"key": "Minor Mana Elixir", "type": "potion", "mana": 40, "desc": "A blue shimmering liquid that restores spent magic energy."},
    {"key": "Greater Mana Elixir", "type": "potion", "mana": 120, "desc": "A bright blue potion pulsing with raw magical power."},
    {"key": "Elixir of Titan Strength", "type": "buff", "stat": "strength", "val": 10, "desc": "Temporarily grants immense physical power."},
    {"key": "Potion of Swiftness", "type": "buff", "stat": "agility", "val": 10, "desc": "Increases speed and dodging capabilities."}
]


# ---------------------------------------------------------------------------
# ITEM CREATION ENGINE
# ---------------------------------------------------------------------------

def create_equipment_item(name, slot, cls, race, align, tier_num):
    """Creates a single equipment piece bound to race, alignment, class, and slot."""
    t_data = TIERS[tier_num]
    req_level = random.randint(t_data["level_min"], t_data["level_max"])
    
    # Stats based on class archetype
    str_mod = random.randint(*t_data["stat_mod"]) if cls in ["Warrior", "Paladin", "Ranger", "Monk"] else 0
    int_mod = random.randint(*t_data["stat_mod"]) if cls in ["Mage", "Warlock", "Cleric", "Necromancer"] else 0
    agi_mod = random.randint(*t_data["stat_mod"]) if cls in ["Rogue", "Ranger", "Druid", "Monk"] else 0
    
    ac_val = random.randint(*t_data["ac_mod"]) if slot not in ["main_hand", "two_hand"] else 0
    dmg_val = random.randint(*t_data["dmg_mod"]) if slot in ["main_hand", "two_hand"] else 0

    desc = (
        f"A Tier {tier_num} {name}. Crafted for {race} ({align}) {cls}s. "
        f"Requires level {req_level} to equip in the {slot.replace('_', ' ')} slot."
    )

    item = create_object(
        DefaultObject,
        key=name,
        attributes=[
            ("desc", desc),
            ("item_type", "equipment"),
            ("slot", slot),
            ("required_class", cls),
            ("required_race", race),
            ("alignment", align),
            ("required_level", req_level),
            ("tier", tier_num),
            ("armor_class", ac_val),
            ("damage", dmg_val),
            ("stat_str", str_mod),
            ("stat_int", int_mod),
            ("stat_agi", agi_mod),
            ("value_gold", req_level * 18 * tier_num)
        ]
    )
    return item


def create_consumable_item(data):
    """Creates food, drinks, and potions."""
    item = create_object(
        DefaultObject,
        key=data["key"],
        attributes=[
            ("desc", data["desc"]),
            ("item_type", data["type"]),
            ("heal_amount", data.get("heal", 0)),
            ("mana_amount", data.get("mana", 0)),
            ("buff_stat", data.get("stat", None)),
            ("buff_value", data.get("val", 0)),
            ("value_gold", data.get("heal", 20) // 2)
        ]
    )
    return item


def wipe_previous_items():
    """Wipes old template items to avoid database duplication."""
    print("Purging previous generated item templates...")
    count = 0
    all_objs = DefaultObject.objects.all()
    for obj in all_objs:
        if obj.db.item_type in ["equipment", "food", "drink", "potion", "buff"]:
            obj.delete()
            count += 1
    print(f"Purged {count} previous items.")


def generate_all_items():
    """Generates equipment mapping to all 16 Races and 10 Classes."""
    print("=== STARTING ITEM GENERATION FOR 16 RACES & 10 CLASSES ===")

    all_races = list(RACES.keys())
    all_classes = list(CLASSES.keys())

    with transaction.atomic():
        wipe_previous_items()
        items_created = 0

        for tier_num in range(1, 5):
            for cls in all_classes:
                prefix_list = PREFIXES[cls]
                
                # Pick 4 races for this class per tier to balance item variance
                target_races = random.sample(all_races, 4)
                
                for race in target_races:
                    align = RACES[race]["alignment"]
                    
                    # 1) Armor across all slots
                    for slot, base_names in ARMOR_BY_SLOT.items():
                        base_name = random.choice(base_names)
                        prefix = random.choice(prefix_list)
                        suffix = random.choice(SUFFIXES) if tier_num >= 2 else ""
                        
                        full_name = f"{race}'s {prefix} {base_name} {suffix}".strip()
                        create_equipment_item(full_name, slot, cls, race, align, tier_num)
                        items_created += 1

                    # 2) Weapons
                    weapons = WEAPONS_BY_CLASS[cls]
                    for base_wep, slot in weapons:
                        prefix = random.choice(prefix_list)
                        suffix = random.choice(SUFFIXES) if tier_num >= 2 else ""
                        
                        full_name = f"{race}'s {prefix} {base_wep} {suffix}".strip()
                        create_equipment_item(full_name, slot, cls, race, align, tier_num)
                        items_created += 1

        # 3) Consumables
        for c_data in FOOD_AND_CONSUMABLES:
            create_consumable_item(c_data)
            items_created += 1

    print("==================================================")
    print(f" SUCCESS! Generated {items_created} items & consumables.")
    print(f" Linked with 16 Races ({len(all_races)}) & 10 Classes ({len(all_classes)}).")
    print("==================================================")


if __name__ == "__main__":
    generate_all_items()