"""
World Entity Builder for Evennia
Generates Good/Regular vs. Evil/Demonic regions with mobs, equipment, and shopkeepers.

Run in `evennia shell`:
    import world.build_entities as builder
    builder.build_all()
"""

from evennia import create_object, search_object
from evennia.objects.objects import DefaultObject, DefaultCharacter


class MUDItem(DefaultObject):
    """Base typeclass for weapons, armor, and consumables."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.value = 10
        self.db.item_type = "general"


class Shopkeeper(DefaultCharacter):
    """Shopkeeper NPC that holds inventory for sale."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.is_vendor = True
        self.db.inventory_stock = []


# Item Archetypes
ITEMS_GOOD = [
    {"key": "Iron Longsword", "type": "weapon", "value": 50, "desc": "A sturdy sword crafted from tempered iron."},
    {"key": "Leather Cuirass", "type": "armor", "value": 35, "desc": "Hardened leather protection for the chest."},
    {"key": "Wooden Shield", "type": "armor", "value": 20, "desc": "A heavy wooden shield reinforced with iron bands."},
    {"key": "Health Potion", "type": "consumable", "value": 15, "desc": "A glowing red vial that restores vitality."},
]

ITEMS_EVIL = [
    {"key": "Demon-Forged Blade", "type": "weapon", "value": 150, "desc": "A jagged blade pulsing with dark energy."},
    {"key": "Obsidian Plate", "type": "armor", "value": 120, "desc": "Heavy armor crafted from volcanic dark stone."},
    {"key": "Shadow Staff", "type": "weapon", "value": 100, "desc": "A twisted wooden staff tipped with a void stone."},
    {"key": "Blood Elixir", "type": "consumable", "value": 40, "desc": "A dark crimson liquid that unleashes raw power."},
]


def create_item(template, location=None):
    """Helper to instantiate an item from a template dictionary."""
    item = create_object(
        typeclass=MUDItem,
        key=template["key"],
        location=location
    )
    item.db.desc = template["desc"]
    item.db.value = template["value"]
    item.db.item_type = template["type"]
    return item


def spawn_mob(name, desc, room, level=1, faction="good", equipment_templates=None):
    """Creates a mob character and equips/gives them items."""
    mob = create_object(
        typeclass=DefaultCharacter,
        key=name,
        location=room
    )
    mob.db.desc = desc
    mob.db.level = level
    mob.db.faction = faction
    mob.db.is_mob = True

    if equipment_templates:
        for tmpl in equipment_templates:
            item = create_item(tmpl, location=mob)
            # Mark equipped if it's weapon or armor
            if tmpl["type"] in ("weapon", "armor"):
                item.db.is_equipped = True

    return mob


def spawn_shopkeeper(name, desc, room, inventory_templates):
    """Creates a shopkeeper NPC stocked with specific item inventory."""
    vendor = create_object(
        typeclass=Shopkeeper,
        key=name,
        location=room
    )
    vendor.db.desc = desc

    # Populate vendor stock
    stock_list = []
    for tmpl in inventory_templates:
        item = create_item(tmpl, location=vendor)
        stock_list.append(item)

    vendor.db.inventory_stock = stock_list
    return vendor


def build_all():
    """Main build runner. Finds or creates rooms and spawns entities."""
    print("--- Starting World Entity Generator ---")

    # Locate starting or target rooms (falls back to Room #2 or creates if missing)
    limbo = search_object("#2")
    start_room = limbo[0] if limbo else None

    # -------------------------------------------------------------
    # 1. GOOD REGION: Sanctum & Town Outskirts
    # -------------------------------------------------------------
    print("Generating Good Region entities...")

    # Town Shopkeeper
    shopkeeper = spawn_shopkeeper(
        name="Tobias the Armorer",
        desc="A heavily built man with soot-stained hands and a warm smile.",
        room=start_room,
        inventory_templates=[ITEMS_GOOD[0], ITEMS_GOOD[1], ITEMS_GOOD[2], ITEMS_GOOD[3]]
    )
    print(f"  + Spawned Shopkeeper: {shopkeeper.key}")

    # Good / Regular Mobs
    guard = spawn_mob(
        name="Sanctum Guard",
        desc="A disciplined soldier wearing polished steel and watchful eyes.",
        room=start_room,
        level=5,
        faction="good",
        equipment_templates=[ITEMS_GOOD[0], ITEMS_GOOD[1]]
    )
    print(f"  + Spawned Mob: {guard.key}")

    wolf = spawn_mob(
        name="Timber Wolf",
        desc="A large grey wolf with sharp yellow eyes.",
        room=start_room,
        level=2,
        faction="neutral"
    )
    print(f"  + Spawned Mob: {wolf.key}")

    # -------------------------------------------------------------
    # 2. EVIL REGION: Demonic Wastes
    # -------------------------------------------------------------
    print("Generating Evil Region entities...")

    # Dark Merchant
    dark_vendor = spawn_shopkeeper(
        name="Malakor the Void Trader",
        desc="A cloaked figure whose eyes glow with eerie purple light.",
        room=start_room,
        inventory_templates=[ITEMS_EVIL[0], ITEMS_EVIL[1], ITEMS_EVIL[2], ITEMS_EVIL[3]]
    )
    print(f"  + Spawned Dark Merchant: {dark_vendor.key}")

    # Demonic Mobs
    pit_demon = spawn_mob(
        name="Pit Demon",
        desc="A towering creature of muscle, horn, and burning brimstone.",
        room=start_room,
        level=10,
        faction="evil",
        equipment_templates=[ITEMS_EVIL[0], ITEMS_EVIL[1]]
    )
    print(f"  + Spawned Mob: {pit_demon.key}")

    cultist = spawn_mob(
        name="Infernal Cultist",
        desc="A fanatic whispering dark chants in an unknown tongue.",
        room=start_room,
        level=4,
        faction="evil",
        equipment_templates=[ITEMS_EVIL[2]]
    )
    print(f"  + Spawned Mob: {cultist.key}")

    hellhound = spawn_mob(
        name="Hellhound",
        desc="A canine monster with skin like cracked lava and teeth like daggers.",
        room=start_room,
        level=6,
        faction="evil"
    )
    print(f"  + Spawned Mob: {hellhound.key}")

    print("--- Build Complete! All entities spawned. ---")