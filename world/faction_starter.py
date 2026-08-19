"""
Faction Starter Shops & Trainers for 'rop'

Places free starter NPCs in both faction starting areas:
  - Good: Aethelgard - Shrine of Light & Aethelgard - The Grand Sanctum
  - Evil: Gorgoroth - Dark Temple & Gorgoroth - The Blood Forge

Each faction gets:
  - A Gear Quartermaster offering FREE basic armour and weapons (levels 1-5)
  - A Spell Trainer offering FREE starter spells (levels 1-5)

All gear and spells cost 0 gold.
"""

from evennia import create_object, search_object
from evennia.objects.objects import DefaultRoom, DefaultObject


# ---------------------------------------------------------------------------
# FACTION ROOM KEYS (used for creation and lookup)
# ---------------------------------------------------------------------------

GOOD_START_ROOMS = [
    "Aethelgard - Shrine of Light",
    "Aethelgard - The Grand Sanctum",
]
EVIL_START_ROOMS = [
    "Gorgoroth - Dark Temple",
    "Gorgoroth - The Blood Forge",
]


# ---------------------------------------------------------------------------
# STARTER GEAR (free, level 1-5)
# ---------------------------------------------------------------------------

GOOD_STARTER_GEAR = {
    "head": {
        "key": "Worn Iron Helm",
        "desc": "A simple but sturdy iron helm issued to new Aethelgard recruits.",
        "armor_class": 3,
        "required_level": 1,
    },
    "torso": {
        "key": "Recruit's Chainmail Vest",
        "desc": "Light chainmail bearing the sunburst crest of Aethelgard.",
        "armor_class": 6,
        "required_level": 1,
    },
    "legs": {
        "key": "Leather Leggings",
        "desc": "Reinforced leather leggings offering modest protection.",
        "armor_class": 3,
        "required_level": 1,
    },
    "feet": {
        "key": "Iron-Toed Boots",
        "desc": "Sturdy marching boots tipped with iron caps.",
        "armor_class": 2,
        "required_level": 1,
    },
    "main_hand": {
        "key": "Training Longsword",
        "desc": "A well-balanced steel longsword for fledgling warriors.",
        "damage": 8,
        "required_level": 1,
    },
    "two_hand": {
        "key": "Recruit's Greatsword",
        "desc": "A heavy two-handed blade for those who favour brute force.",
        "damage": 12,
        "required_level": 1,
    },
    "off_hand": {
        "key": "Wooden Round Shield",
        "desc": "A simple painted shield bearing the Aethelgard sun.",
        "armor_class": 4,
        "required_level": 1,
    },
}

EVIL_STARTER_GEAR = {
    "head": {
        "key": "Spiked Skullcap",
        "desc": "Dark iron headgear with cruel spikes, standard Gorgoroth issue.",
        "armor_class": 3,
        "required_level": 1,
    },
    "torso": {
        "key": "Dark Recruit's Breastplate",
        "desc": "Blackened plate bearing the jagged crest of Gorgoroth.",
        "armor_class": 6,
        "required_level": 1,
    },
    "legs": {
        "key": "Darkhide Leg-Wraps",
        "desc": "Tough hide leg-guards favoured by Gorgoroth footsoldiers.",
        "armor_class": 3,
        "required_level": 1,
    },
    "feet": {
        "key": "Iron Greaves",
        "desc": "Heavy iron greaves that crush anything underfoot.",
        "armor_class": 2,
        "required_level": 1,
    },
    "main_hand": {
        "key": "Jagged Shortsword",
        "desc": "A serrated blade designed to inflict messy wounds.",
        "damage": 8,
        "required_level": 1,
    },
    "two_hand": {
        "key": "Brutal War Axe",
        "desc": "A massive two-handed axe favoured by Gorgoroth berserkers.",
        "damage": 12,
        "required_level": 1,
    },
    "off_hand": {
        "key": "Spiked Tower Shield",
        "desc": "A black iron shield bristling with sharp spikes.",
        "armor_class": 4,
        "required_level": 1,
    },
}


# ---------------------------------------------------------------------------
# STARTER SPELLS (free, levels 1-5)
# ---------------------------------------------------------------------------

STARTER_SPELLS_KEYS = [
    "sparks",
    "minorheal",
    "arcanedart",
    "stoneskin",
    "frostsnap",
]


# ---------------------------------------------------------------------------
# NPC CREATION HELPERS
# ---------------------------------------------------------------------------

def _create_gear_vendor(location, faction_name, gear_table):
    """Create a quartermaster NPC holding free starter gear."""
    vendor = create_object(
        DefaultObject,
        key=f"{faction_name} Quartermaster",
        location=location,
        attributes=[
            ("desc", f"A grizzled {faction_name} quartermaster handing out free "
                     f"starter equipment to new recruits. Type |wbuy list|n "
                     f"to see what is available."),
            ("is_vendor", True),
            ("vendor_type", "gear"),
            ("faction", faction_name),
            ("vendor_gold_cost", 0),          # FREE
        ],
    )
    vendor.db.desc = vendor.attributes.get("desc")
    return vendor


def _create_bank_teller(location, faction_name):
    """Create a Bank Teller NPC in the given room."""
    teller = create_object(
        DefaultObject,
        key=f"{faction_name} Bank Teller",
        location=location,
        attributes=[
            ("desc", f"A stern {faction_name} bank teller stands behind a reinforced "
                     f"counter, ready to handle deposits and withdrawals. "
                     f"Type |wdeposit <amount>|n, |wwithdraw <amount>|n, "
                     f"or |wbalance|n to manage your account."),
            ("is_bank_teller", True),
            ("faction", faction_name),
        ],
    )
    teller.db.desc = teller.attributes.get("desc")
    return teller


def _create_spell_trainer(location, faction_name):
    """Create a spell trainer NPC offering free starter spells."""
    trainer = create_object(
        DefaultObject,
        key=f"{faction_name} Spell Trainer",
        location=location,
        attributes=[
            ("desc", f"A wise {faction_name} spell instructor offering free "
                     f"starter spells to new adepts. Type |wspells|n or "
                     f"|wspells list|n to see what you can learn."),
            ("is_trainer", True),
            ("trainer_type", "spells"),
            ("faction", faction_name),
            ("available_spells", STARTER_SPELLS_KEYS),
            ("trainer_gold_cost", 0),          # FREE
        ],
    )
    trainer.db.desc = trainer.attributes.get("desc")
    return trainer


def _create_starter_gear_item(location, slot, gear_data, faction_name):
    """Spawn a single piece of starter gear directly in the room."""
    item = create_object(
        DefaultObject,
        key=gear_data["key"],
        location=location,
        attributes=[
            ("desc", gear_data["desc"]),
            ("item_type", "equipment"),
            ("slot", slot),
            ("required_level", gear_data.get("required_level", 1)),
            ("armor_class", gear_data.get("armor_class", 0)),
            ("damage", gear_data.get("damage", 0)),
            ("faction", faction_name),
            ("value_gold", 0),                  # FREE
            ("is_starter_gear", True),
        ],
    )
    return item


def _ensure_room_exists(room_key, desc, faction_name):
    """Find or create a faction starting room."""
    # Search for exact match first
    from evennia.objects.models import ObjectDB
    matches = ObjectDB.objects.filter(
        db_typeclass_path__endswith="Room",
        db_key__iexact=room_key,
    )
    if matches:
        return matches[0]

    # Create the room
    room = create_object(
        DefaultRoom,
        key=room_key,
        attributes=[
            ("desc", desc),
            ("faction", faction_name),
        ],
    )
    return room


# ---------------------------------------------------------------------------
# MAIN BUILDER
# ---------------------------------------------------------------------------

def build_faction_starters():
    """
    Build or refresh all faction starter rooms, vendors, and trainers.

    Idempotent — will not duplicate existing NPCs or gear.
    Called from evennia's `at_initial_setup` or manually.
    """
    print("=== BUILDING FACTION STARTER AREAS ===")

    # ---- GOOD FACTION ----
    good_shrine_desc = (
        "A sacred chamber bathed in warm golden light. Sunbeams stream through "
        "stained-glass windows depicting the heroic deeds of the first paladins "
        "of Aethelgard. White marble pillars rise to a vaulted ceiling, and the "
        "air is thick with the scent of incense. A shimmering font of holy water "
        "stands at the chamber's heart, and robed acolytes move silently between "
        "the pews. This is where every hero of the Light begins their journey. "
        "Exits lead |wout|n to the Grand Sanctum."
    )
    good_sanctum_desc = (
        "The Grand Sanctum of Aethelgard rises around you in breathtaking majesty. "
        "Polished white marble floors stretch beneath soaring arches, while golden "
        "banners bearing the radiant sun crest ripple in a gentle breeze. Paladins "
        "in gleaming plate armour stand vigil along the walls, their presence a "
        "silent promise of protection. High above, a crystalline dome captures "
        "the light of the heavens and scatters it in prismatic rays across the "
        "hall. Exits lead |wout|n to the city streets."
    )

    for room_key in GOOD_START_ROOMS:
        desc = good_shrine_desc if "Shrine" in room_key else good_sanctum_desc
        room = _ensure_room_exists(room_key, desc, "Good")
        # Mark starter city rooms as safe zones
        room.db.safe_zone = True

        # Only add NPCs/gear if they don't already exist here
        existing_vendors = [obj for obj in room.contents
                            if obj.attributes.get("is_vendor")]
        existing_trainers = [obj for obj in room.contents
                             if obj.attributes.get("is_trainer")]
        existing_tellers = [obj for obj in room.contents
                            if obj.attributes.get("is_bank_teller")]

        if not existing_vendors:
            vendor = _create_gear_vendor(room, "Good", GOOD_STARTER_GEAR)
            for slot, gear_data in GOOD_STARTER_GEAR.items():
                _create_starter_gear_item(room, slot, gear_data, "Good")

        if not existing_trainers:
            _create_spell_trainer(room, "Good")

        if not existing_tellers:
            _create_bank_teller(room, "Good")

    # ---- EVIL FACTION ----
    evil_temple_desc = (
        "A vast subterranean temple carved from black volcanic stone. Crimson "
        "runes pulse with dark energy along the walls, casting flickering shadows "
        "that seem to move of their own accord. Iron braziers burn with unnatural "
        "flame, filling the air with the scent of brimstone and char. Dark-robed "
        "acolytes chant in guttural tongues before a massive altar of obsidian. "
        "This is where the forces of Darkness forge their champions. "
        "Exits lead |wout|n to the Blood Forge."
    )
    evil_forge_desc = (
        "The Blood Forge roars in the heart of Gorgoroth, a colossal foundry of "
        "black iron and eternal fire. Rivers of molten metal course through channels "
        "carved into the obsidian floor, and the thunderous clang of the Great Anvil "
        "reverberates through your bones. Hulking forgemasters with scarred flesh "
        "and iron aprons labour ceaselessly, quenching freshly forged darksteel in "
        "troughs of blood. Jagged spires loom overhead against a crimson sky. "
        "Exits lead |wout|n to the city streets."
    )

    for room_key in EVIL_START_ROOMS:
        desc = evil_temple_desc if "Temple" in room_key else evil_forge_desc
        room = _ensure_room_exists(room_key, desc, "Evil")
        # Mark starter city rooms as safe zones
        room.db.safe_zone = True

        existing_vendors = [obj for obj in room.contents
                            if obj.attributes.get("is_vendor")]
        existing_trainers = [obj for obj in room.contents
                             if obj.attributes.get("is_trainer")]
        existing_tellers = [obj for obj in room.contents
                            if obj.attributes.get("is_bank_teller")]

        if not existing_vendors:
            vendor = _create_gear_vendor(room, "Evil", EVIL_STARTER_GEAR)
            for slot, gear_data in EVIL_STARTER_GEAR.items():
                _create_starter_gear_item(room, slot, gear_data, "Evil")

        if not existing_trainers:
            _create_spell_trainer(room, "Evil")

        if not existing_tellers:
            _create_bank_teller(room, "Evil")

    print("=== FACTION STARTER AREAS COMPLETE ===")


if __name__ == "__main__":
    build_faction_starters()