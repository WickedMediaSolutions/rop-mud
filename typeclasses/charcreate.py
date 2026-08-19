"""
Character Creation EvMenu for Evennia.
Classic MUD style (MajorMUD / DikuMUD / Warcraft).

Flow: Name -> Good/Evil Alignment -> Race -> Class -> Confirm -> Spawn in Faction Town
"""
from evennia import create_object
from evennia.utils import delay, search
from evennia.objects.models import ObjectDB

# ---------------------------------------------------------------------------
# CONFIGURATION & FACTION START ROOMS
# ---------------------------------------------------------------------------
GOOD_START_ROOM_KEY = "Aethelgard - Shrine of Light"
EVIL_START_ROOM_KEY = "Gorgoroth - Dark Temple"

# ---------------------------------------------------------------------------
# ROOM LOOKUP HELPER
# ---------------------------------------------------------------------------

def _search_faction_start_by_alignment(alignment):
    """
    Return the first faction starter room matching an alignment keyword.

    Returns None when no matching room exists (e.g. the realm hasn't been
    seeded yet).
    """
    if not alignment:
        return None
    keyword = "Aethelgard" if alignment.lower() == "good" else "Gorgoroth"
    matches = ObjectDB.objects.filter(
        db_typeclass_path__endswith="Room",
        db_key__icontains=keyword,
    )
    return matches[0] if matches else None


def _alert_and_repopulate_start_rooms(alignment, room_ref):
    """
    Alert staff and attempt an automatic rebuild of the faction start rooms
    when start-room lookup fails.

    This prevents a new character being silently dropped into Limbo (#2).
    """
    from evennia.utils import logger

    logger.log_err(
        f"charcreate._find_start_room: alignment={alignment!r} "
        f"start-room lookup failed for {room_ref!r}"
    )

    # Persistent admin alert via the audit log.
    try:
        from world.admin_log import log_admin_action
        log_admin_action(
            None,
            "autofix",
            "faction_start_rooms",
            f"Auto-populating starter areas (alignment={alignment!r}, "
            f"lookup failed for {room_ref!r})",
        )
    except Exception:
        pass

    # Attempt to rebuild faction starter rooms idempotently.
    try:
        from world.faction_starter import build_faction_starters
        build_faction_starters()
    except Exception as err:
        logger.log_err(
            f"charcreate._find_start_room: auto-populate failed: {err}"
        )


def _find_start_room(room_key, alignment):
    """
    Resolve a start-room by key with multiple fallback strategies.

    Strategy:
      1. exact key match
      2. substring match
      3. alignment keyword fallback
      4. alert staff + auto-populate faction rooms, retry alignment search
      5. Limbo (last resort)

    Survives realm wipes/reseeds because searches are key-based.
    """
    # step 1: exact key match
    matches = ObjectDB.objects.filter(
        db_typeclass_path__endswith="Room",
        db_key__iexact=room_key,
    )
    if matches:
        return matches[0]
    # step 2: substring match
    matches = ObjectDB.objects.filter(
        db_typeclass_path__endswith="Room",
        db_key__icontains=room_key,
    )
    if matches:
        return matches[0]
    # step 3: alignment keyword fallback
    faction_room = _search_faction_start_by_alignment(alignment)
    if faction_room:
        return faction_room
    # step 4: alert staff and attempt auto-populate, then retry
    _alert_and_repopulate_start_rooms(alignment or "unknown", room_key)
    faction_room = _search_faction_start_by_alignment(alignment)
    if faction_room:
        return faction_room
    # step 5: Limbo (last resort)
    return search.search_object("#2")[0]


# ---------------------------------------------------------------------------
# DATA TABLES
# ---------------------------------------------------------------------------

# Race tables synced with world/rules.py (16 races: 8 Good, 8 Evil).
# Each entry mirrors the canonical RACES dict stats for consistency.
RACES_GOOD = {
    "Human": {"desc": "Versatile and ambitious, Humans adapt quickly to any discipline.", "hp": 100, "mana": 50, "str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
    "High Elf": {"desc": "Noble and ancient, highly attuned to arcane forces.", "hp": 80, "mana": 120, "str": 7, "dex": 12, "con": 8, "int": 14, "wis": 12, "cha": 11},
    "Wood Elf": {"desc": "Swift forest dwellers with uncanny instincts and deadly aim.", "hp": 90, "mana": 80, "str": 8, "dex": 14, "con": 9, "int": 10, "wis": 13, "cha": 10},
    "Mountain Dwarf": {"desc": "Resilient, stout warriors crafted from stone and iron.", "hp": 120, "mana": 30, "str": 13, "dex": 8, "con": 14, "int": 8, "wis": 10, "cha": 7},
    "Stout Halfling": {"desc": "Small in stature but incredibly nimble and surprisingly tough.", "hp": 85, "mana": 40, "str": 6, "dex": 15, "con": 11, "int": 9, "wis": 10, "cha": 13},
    "Gnome": {"desc": "Master inventors and magical tinkers with brilliant minds.", "hp": 75, "mana": 110, "str": 5, "dex": 11, "con": 9, "int": 15, "wis": 12, "cha": 10},
    "Centaur": {"desc": "Powerful half-human, half-horse guardians of the open plains.", "hp": 130, "mana": 20, "str": 12, "dex": 11, "con": 12, "int": 8, "wis": 10, "cha": 7},
    "Pixie": {"desc": "Tiny winged fae creatures with incredible agility and innate glamour.", "hp": 70, "mana": 100, "str": 4, "dex": 16, "con": 6, "int": 13, "wis": 11, "cha": 14},
}

RACES_EVIL = {
    "Orc": {"desc": "Brutal frontline warmongers who thrive on bloodshed.", "hp": 130, "mana": 20, "str": 14, "dex": 9, "con": 13, "int": 6, "wis": 7, "cha": 5},
    "Dark Elf": {"desc": "Subterranean assassins and dark sorcerers who strike from shadows.", "hp": 80, "mana": 115, "str": 8, "dex": 14, "con": 8, "int": 13, "wis": 10, "cha": 9},
    "Undead": {"desc": "Reanimated corpses bound by dark magic, feeling no pain.", "hp": 90, "mana": 100, "str": 10, "dex": 8, "con": 14, "int": 11, "wis": 11, "cha": 2},
    "Goblin": {"desc": "Cunning, greedy scavengers who rely on speed and underhanded tactics.", "hp": 70, "mana": 60, "str": 7, "dex": 15, "con": 9, "int": 11, "wis": 7, "cha": 5},
    "Minotaur": {"desc": "Massive bovine behemoths capable of crushing enemies underfoot.", "hp": 145, "mana": 15, "str": 15, "dex": 7, "con": 14, "int": 5, "wis": 8, "cha": 5},
    "Lizardfolk": {"desc": "Cold-blooded reptilian hunters with thick scaled hide.", "hp": 125, "mana": 40, "str": 11, "dex": 11, "con": 13, "int": 7, "wis": 9, "cha": 4},
    "Ogre": {"desc": "Towering giants possessing crushing brute strength and massive health.", "hp": 160, "mana": 10, "str": 16, "dex": 5, "con": 15, "int": 4, "wis": 5, "cha": 3},
    "Demonkin": {"desc": "Fiendish mortals carrying the bloodline of the Nether Hells.", "hp": 95, "mana": 105, "str": 10, "dex": 10, "con": 10, "int": 13, "wis": 9, "cha": 12},
}

# Classes synced with world/rules.py (10 classes).
# Each entry includes hp_per_level and mana_per_level for derived stat calculation.
CLASSES = {
    "Warrior": {"desc": "Frontline heavy armor juggernauts specializing in weapons and shields.", "primary": "Strength", "hp_per_level": 15, "mana_per_level": 2},
    "Paladin": {"desc": "Holy crusaders blending heavy melee combat with healing and defense.", "primary": "Strength / Piety", "hp_per_level": 13, "mana_per_level": 6},
    "Cleric": {"desc": "Divine casters devoted to mending allies and purging enemies.", "primary": "Wisdom", "hp_per_level": 10, "mana_per_level": 12},
    "Mage": {"desc": "Masters of destructive elemental magic and arcane utility.", "primary": "Intelligence", "hp_per_level": 6, "mana_per_level": 16},
    "Rogue": {"desc": "Stealthy combatants specializing in lockpicking, poisons, and critical strikes.", "primary": "Dexterity", "hp_per_level": 9, "mana_per_level": 4},
    "Warlock": {"desc": "Dark casters who drain soul energy and deal damage over time.", "primary": "Intelligence", "hp_per_level": 8, "mana_per_level": 14},
    "Druid": {"desc": "Nature guardians capable of shapeshifting, healing, and casting storms.", "primary": "Wisdom", "hp_per_level": 10, "mana_per_level": 10},
    "Ranger": {"desc": "Deadly marksmen and wilderness trackers adept at ranged combat.", "primary": "Dexterity", "hp_per_level": 10, "mana_per_level": 6},
    "Monk": {"desc": "Unarmed martial artists utilizing speed, ki power, and strikes.", "primary": "Dexterity", "hp_per_level": 11, "mana_per_level": 5},
    "Necromancer": {"desc": "Commanders of death who raise undead minions and siphon life force.", "primary": "Intelligence", "hp_per_level": 7, "mana_per_level": 15},
}


# ---------------------------------------------------------------------------
# EVMENU NODE FUNCTIONS
# ---------------------------------------------------------------------------

def node_start(caller, raw_string, **kwargs):
    """Step 1: Enter Character Name."""
    text = "|c=== CHARACTER CREATION ===|n\n\nPlease enter your desired character name:"
    options = {"key": "_default", "goto": _store_name}
    return text, options


def _store_name(caller, raw_string, **kwargs):
    name = raw_string.strip().capitalize()
    if not name or len(name) < 3:
        caller.msg("|rNames must be at least 3 characters long.|n")
        return "node_start"

    if search.object_search(name):
        caller.msg("|rThat name is already taken! Please choose another.|n")
        return "node_start"

    # Store on menu session memory
    if hasattr(caller, "ndb") and hasattr(caller.ndb, "_evmenu"):
        caller.ndb._evmenu.c_name = name
    return "node_select_alignment"


def node_select_alignment(caller, raw_string, **kwargs):
    """Step 2: Choose Alignment (Good vs Evil)."""
    menu = getattr(caller.ndb, "_evmenu", None)
    name = getattr(menu, "c_name", "Unknown") if menu else "Unknown"
    
    text = f"Character Name: |w{name}|n\n\nSelect your Alignment:"
    options = [
        {"desc": "Good", "goto": (_set_alignment, {"align": "Good"})},
        {"desc": "Evil", "goto": (_set_alignment, {"align": "Evil"})},
    ]
    return text, options


def _set_alignment(caller, raw_string, align="Good", **kwargs):
    if hasattr(caller, "ndb") and hasattr(caller.ndb, "_evmenu"):
        caller.ndb._evmenu.c_align = align
    if align == "Good":
        return "node_select_good_race"
    return "node_select_evil_race"


def node_select_good_race(caller, raw_string, **kwargs):
    """Step 3a: Select Good Race."""
    menu = getattr(caller.ndb, "_evmenu", None)
    name = getattr(menu, "c_name", "Unknown") if menu else "Unknown"
    
    text = f"Name: |w{name}|n | Alignment: |gGood|n\n\nChoose your Race:"
    options = []
    for race_name, info in RACES_GOOD.items():
        options.append({
            "desc": f"{race_name.ljust(15)} - {info['desc']}",
            "goto": (_set_race, {"race": race_name}),
        })
    return text, options


def node_select_evil_race(caller, raw_string, **kwargs):
    """Step 3b: Select Evil Race."""
    menu = getattr(caller.ndb, "_evmenu", None)
    name = getattr(menu, "c_name", "Unknown") if menu else "Unknown"

    text = f"Name: |w{name}|n | Alignment: |rEvil|n\n\nChoose your Race:"
    options = []
    for race_name, info in RACES_EVIL.items():
        options.append({
            "desc": f"{race_name.ljust(15)} - {info['desc']}",
            "goto": (_set_race, {"race": race_name}),
        })
    return text, options


def _set_race(caller, raw_string, race="Human", **kwargs):
    if hasattr(caller, "ndb") and hasattr(caller.ndb, "_evmenu"):
        caller.ndb._evmenu.c_race = race
    return "node_select_class"


def node_select_class(caller, raw_string, **kwargs):
    """Step 4: Select Class."""
    menu = getattr(caller.ndb, "_evmenu", None)
    name = getattr(menu, "c_name", "Unknown") if menu else "Unknown"
    align = getattr(menu, "c_align", "Good") if menu else "Good"
    race = getattr(menu, "c_race", "Human") if menu else "Human"

    text = (
        f"Name: |w{name}|n | Alignment: |w{align}|n | "
        f"Race: |w{race}|n\n\nChoose your Class:"
    )
    options = []
    for class_name, info in CLASSES.items():
        options.append({
            "desc": f"{class_name.ljust(14)} [{info['primary']}] - {info['desc']}",
            "goto": (_set_class, {"cls": class_name}),
        })
    return text, options


def _set_class(caller, raw_string, cls="Warrior", **kwargs):
    if hasattr(caller, "ndb") and hasattr(caller.ndb, "_evmenu"):
        caller.ndb._evmenu.c_class = cls
    return "node_confirm"


def node_confirm(caller, raw_string, **kwargs):
    """Step 5: Confirm Selections."""
    menu = getattr(caller.ndb, "_evmenu", None)
    name = getattr(menu, "c_name", "Unknown") if menu else "Unknown"
    align = getattr(menu, "c_align", "Good") if menu else "Good"
    race = getattr(menu, "c_race", "Human") if menu else "Human"
    cls = getattr(menu, "c_class", "Warrior") if menu else "Warrior"

    race_dict = RACES_GOOD if align == "Good" else RACES_EVIL
    race_data = race_dict.get(race, {"hp": 100, "mana": 50, "str": 10, "int": 10, "dex": 10})

    text = (
        f"|c=== CHARACTER SUMMARY ===|n\n"
        f" Name:       |w{name}|n\n"
        f" Alignment:  |w{align}|n\n"
        f" Race:       |w{race}|n\n"
        f" Class:      |w{cls}|n\n"
        f" Base HP:    |g{race_data.get('hp', 100)}|n\n"
        f" Base Mana:  |c{race_data.get('mana', 50)}|n\n"
        f" Base Stats: STR {race_data.get('str', 10)} | INT {race_data.get('int', 10)} | DEX {race_data.get('dex', 10)}\n\n"
        f"Create this character?"
    )
    options = [
        {"key": ("Yes", "y"), "goto": _create_character},
        {"key": ("No", "n"), "goto": "node_start"},
    ]
    return text, options


def _create_character(caller, raw_string, **kwargs):
    """Step 6: Instantiate Object, Assign Attributes, & Spawn."""
    menu = getattr(caller.ndb, "_evmenu", None)
    
    # Retrieve choices stored on the menu object
    name = getattr(menu, "c_name", "Unknown") if menu else "Unknown"
    align = getattr(menu, "c_align", "Good") if menu else "Good"
    race = getattr(menu, "c_race", "Human") if menu else "Human"
    cls = getattr(menu, "c_class", "Warrior") if menu else "Warrior"

    # Identify account and active session
    account = caller.account if hasattr(caller, "account") else caller
    session = caller.session if hasattr(caller, "session") else None
    if not session:
        sessions = account.sessions.get()
        session = sessions[0] if sessions else None

    # Determine spawn location based on alignment using key-based lookup
    room_key = GOOD_START_ROOM_KEY if align == "Good" else EVIL_START_ROOM_KEY
    start_room = _find_start_room(room_key, align)

    # Create character object
    try:
        new_char = create_object(
            "typeclasses.characters.Character",
            key=name,
            location=start_room,
            home=start_room,
        )
    except Exception as err:
        caller.msg(f"|rError creating character: {err}|n")
        return "node_confirm"

    race_dict = RACES_GOOD if align == "Good" else RACES_EVIL
    stats = race_dict.get(race, {"hp": 100, "mana": 50, "str": 10, "int": 10, "dex": 10})

    # Set stats and attributes using the standard format
    # so all downstream systems (combat, damage formulas, equipment
    # gating, return_appearance) read consistent attribute keys.
    new_char.db.race = race
    new_char.attributes.add("race", race)
    new_char.db.alignment = align
    new_char.attributes.add("alignment", align)
    new_char.db.character_class = cls
    new_char.attributes.add("class", cls)
    new_char.db.level = 1
    new_char.attributes.add("level", 1)

    # Standard six-stat dict using the synced race data (now includes all 6 stats).
    base_stats = {
        "str": stats.get("str", 10),
        "dex": stats.get("dex", 10),
        "con": stats.get("con", 10),
        "int": stats.get("int", 10),
        "wis": stats.get("wis", 10),
        "cha": stats.get("cha", 10),
    }
    new_char.db.stats = dict(base_stats)
    new_char.attributes.add("stats", dict(base_stats))

    new_char.db.max_hp = stats["hp"]
    new_char.attributes.add("max_hp", stats["hp"])
    new_char.db.hp = stats["hp"]
    new_char.attributes.add("hp", stats["hp"])
    new_char.db.max_mana = stats["mana"]
    new_char.attributes.add("max_mana", stats["mana"])
    new_char.db.mana = stats["mana"]
    new_char.attributes.add("mana", stats["mana"])

    # Initialize all attributes that the modern chargen standard expects
    new_char.attributes.add("mv", 100)
    new_char.attributes.add("max_mv", 100)
    new_char.attributes.add("xp", 0)
    new_char.attributes.add("xp_to_level", 1000)
    new_char.attributes.add("stamina", 100)
    new_char.attributes.add("max_stamina", 100)
    new_char.db.position = "standing"
    new_char.attributes.add("position", "standing")
    new_char.attributes.add("equipped", {})

    # Initialize save bonuses
    new_char.attributes.add("save_bonuses", {})

    # Mark chargen as complete so at_post_login() doesn't re-launch.
    new_char.db.chargen_completed = True
    new_char.attributes.add("chargen_completed", True)

    # Initialize practice session and reputation
    try:
        from world.guildmaster import PracticeSession
        new_char.db.practice_session = PracticeSession()
    except Exception:
        pass
    try:
        from world.reputation import ReputationSystem
        ReputationSystem.initialize(new_char)
    except Exception:
        pass

    # Grant class-appropriate starting equipment and gold
    try:
        from world.new_player_experience import grant_starting_gear
        gear_messages = grant_starting_gear(new_char)
        if gear_messages:
            caller.msg("\n".join(gear_messages))
    except Exception:
        pass

    # Security Lock & account binding
    new_char.locks.add(f"puppet:id({new_char.id}) or pid({account.id}) or perm(Admin)")
    account.characters.add(new_char)

    caller.msg(f"|gCharacter '{name}' created! Spawning in {start_room.key}...|n")

    # Gracefully shut down the active EvMenu instance to prevent lingering menu commands
    if menu and hasattr(menu, "close_menu"):
        menu.close_menu()

    # Schedule the puppet attach after a 0.2s delay to allow menu teardown to complete
    if session:
        delay(0.2, account.puppet_object, session, new_char)

    return None