"""
New Player Experience for 'rop'

Provides:
  - WELCOME_BANNER — colourful ANSI ASCII art shown on first login
  - STARTING_GEAR — per-class starting equipment package
  - grant_starting_gear(character) — equip starter items and place in inventory
  - register_first_quest() — register the "Kill 3 Goblin Scouts" tutorial quest
  - first_login_banner(character) — the one-time welcome banner string
"""

from evennia import create_object


# ---------------------------------------------------------------------------
# Welcome banner (shown once, immediately after character creation)
# ---------------------------------------------------------------------------

WELCOME_BANNER = """
|y+==================================================================+
|y|                                                                  |
|y|    |c|hRITES OF PASSAGE|n                                          |
|y|    |wA realm at war. A hero rises.|n                                |
|y|                                                                  |
|y|  |gWelcome, {name} the {race} {cls}!|n                               |
|y|                                                                  |
|y|  |wType |yhelp new player|w for a step-by-step starter guide.|n     |
|y|  |wType |yquest|w near the Tutorial Guide to begin your journey.|n |
|y|                                                                  |
|y+==================================================================+
"""


# ---------------------------------------------------------------------------
# Per-class starting gear
# ---------------------------------------------------------------------------

STARTING_GEAR = {
    "Warrior": {
        "weapon": ("Rusty Short Sword", "weapon_sword", 5, "slash"),
        "armor": ("Patched Leather Armor", "armor_light", 3),
        "gold": 15,
    },
    "Paladin": {
        "weapon": ("Blessed Practice Mace", "weapon_mace", 5, "blunt"),
        "armor": ("Initiate Chainmail", "armor_medium", 5),
        "gold": 15,
    },
    "Cleric": {
        "weapon": ("Wooden Quarterstaff", "weapon_staff", 4, "blunt"),
        "armor": ("Acolyte Robes", "armor_cloth", 1),
        "gold": 15,
    },
    "Mage": {
        "weapon": ("Apprentice Wand", "weapon_wand", 3, "arcane"),
        "armor": ("Simple Cloth Robes", "armor_cloth", 1),
        "gold": 15,
    },
    "Rogue": {
        "weapon": ("Worn Iron Dagger", "weapon_dagger", 4, "pierce"),
        "armor": ("Patchwork Leathers", "armor_light", 2),
        "gold": 20,
    },
    "Warlock": {
        "weapon": ("Cultist Athame", "weapon_dagger", 4, "pierce"),
        "armor": ("Shadowspun Robes", "armor_cloth", 1),
        "gold": 15,
    },
    "Druid": {
        "weapon": ("Knotted Oak Staff", "weapon_staff", 4, "blunt"),
        "armor": ("Woven Hide Vest", "armor_light", 2),
        "gold": 15,
    },
    "Ranger": {
        "weapon": ("Short Hunting Bow", "weapon_bow", 5, "pierce"),
        "armor": ("Supple Leather Armor", "armor_light", 2),
        "gold": 20,
    },
    "Monk": {
        "weapon": ("Wrapped Fist Wraps", "weapon_fist", 3, "blunt"),
        "armor": ("Humble Gi", "armor_cloth", 1),
        "gold": 15,
    },
    "Necromancer": {
        "weapon": ("Bone Ritual Dagger", "weapon_dagger", 4, "pierce"),
        "armor": ("Faded Grave Robes", "armor_cloth", 1),
        "gold": 15,
    },
}


def _create_starter_item(key, item_type, armor, damage, damage_type):
    """Build a basic starter equipment item and create it via Evennia."""
    return create_object(
        "typeclasses.objects.Object",
        key=key,
        attributes=[
            ("item_type", item_type),
            ("weight", 2.0),
            ("value", 5),
            ("durability", 100),
            ("max_durability", 100),
            ("armor", armor),
            ("damage", damage),
            ("damage_type", damage_type),
        ],
    )


def grant_starting_gear(character):
    """
    Grant the character its class-appropriate starting package.

    Creates the starter weapon and armor, auto-equips them into the
    `equipped` attribute, places them in inventory, and grants starter gold.

    Returns a list of human-readable messages describing what was granted.
    """
    char_class = character.attributes.get("class", default="Warrior")
    gear = STARTING_GEAR.get(char_class, STARTING_GEAR["Warrior"])

    weapon_key, weapon_type, weapon_dmg, weapon_dmg_type = gear["weapon"]
    armor_key, armor_type, armor_val = gear["armor"]
    gold = gear["gold"]

    messages = []

    # Create & equip weapon
    try:
        weapon_obj = _create_starter_item(
            weapon_key, weapon_type, 0, weapon_dmg, weapon_dmg_type
        )
        weapon_obj.location = character
    except Exception:
        weapon_obj = None

    # Create & equip armor
    try:
        armor_obj = _create_starter_item(
            armor_key, armor_type, armor_val, 0, "blunt"
        )
        armor_obj.location = character
    except Exception:
        armor_obj = None

    # Auto-equip: store names in equipped dict keyed by slot
    equipped = character.attributes.get("equipped", default={})
    if equipped is None or not hasattr(equipped, "items"):
        equipped = {}
    else:
        equipped = {str(k): v for k, v in equipped.items()}
    equipped["main_hand"] = weapon_key
    equipped["chest"] = armor_key
    character.attributes.add("equipped", equipped)

    # Starter gold
    character.attributes.add("gold", gold)

    if weapon_obj:
        messages.append(f"  |gEquipped:|n {weapon_key} (main hand)")
    if armor_obj:
        messages.append(f"  |gEquipped:|n {armor_key} (chest)")
    messages.append(f"  |gGold:|n {gold} gold")

    return messages


# ---------------------------------------------------------------------------
# First quest: "Kill 3 Goblin Scouts"
# ---------------------------------------------------------------------------

def register_first_quest():
    """
    Register the newbie tutorial quest so both factions can accept it.
    Idempotent — safe to call on every server boot.
    """
    from world.quests import QuestDefinition, quest_registry

    quest_id = "first_goblin_scouts"
    if quest_registry.get(quest_id) is not None:
        return

    quest_registry.register(QuestDefinition(
        id=quest_id,
        name="Goblin Scouts",
        description=(
            "Prove your mettle by slaying 3 goblin scouts lurking in the "
            "newbie zone outside the city."
        ),
        quest_type="kill",
        target_key="goblin scout",
        target_count=3,
        rewards={"xp": 75, "gold": 30, "faction": 1},
        giver_npc_key="Tutorial Guide",
        level_required=1,
        completion_text=(
            "Well fought! The goblin scouts have been dealt with. "
            "You have taken your first steps toward legend."
        ),
    ))


# ---------------------------------------------------------------------------
# First-login banner helper
# ---------------------------------------------------------------------------

def first_login_banner(character):
    """Return the formatted one-time welcome banner for *character*."""
    race = character.attributes.get("race", default="Adventurer")
    cls = character.attributes.get("class", default="Wanderer")
    return WELCOME_BANNER.format(name=character.key, race=race, cls=cls)