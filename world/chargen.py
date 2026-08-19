"""
Character Generator (EvMenu) for 'rop'
Handles alignment selection, 16 races, 10 classes, stat rolling/rerolling, and faction spawn.

Flow: start -> race -> class -> node_stat_roll -> node_confirm -> node_finalize
"""
import random
from evennia.utils.evmenu import EvMenu
from evennia.utils.search import search_object
from evennia.objects.models import ObjectDB
from world.rules import RACES, CLASSES

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

# Maximum number of rerolls allowed during stat generation
MAX_REROLLS = 3

# Stat variance range applied on top of base race stats
STAT_VARIANCE_MIN = -2
STAT_VARIANCE_MAX = 4

# The six core attributes in MajorMUD order
CORE_STATS = ["str", "dex", "con", "int", "wis", "cha"]

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


def _alert_and_repopulate_start_rooms(alignment, room_ref, limbo_fallback=False):
    """
    Alert staff and attempt an automatic rebuild of the faction start rooms
    when start-room lookup fails.

    This is the safety net for the last-resort Limbo fallback: rather than
    silently dropping a new character into #2, we log the incident, try to
    recreate the faction starter areas, and then the caller re-runs the
    alignment-keyword search.
    """
    from evennia.utils import logger

    reason = (
        f"start-room lookup failed for {room_ref!r}; "
        f"falling back to Limbo" if limbo_fallback else ""
    )
    logger.log_err(
        f"chargen._find_start_room: alignment={alignment!r} {reason}"
    )

    # Persistent admin alert via the audit log.
    try:
        from world.admin_log import log_admin_action
        log_admin_action(
            None,
            "autofix",
            "faction_start_rooms",
            f"Auto-populating starter areas (alignment={alignment!r}, {reason})",
        )
    except Exception:
        pass

    # Attempt to rebuild faction starter rooms idempotently.
    try:
        from world.faction_starter import build_faction_starters
        build_faction_starters()
    except Exception as err:
        logger.log_err(
            f"chargen._find_start_room: auto-populate failed: {err}"
        )


def _find_start_room(room_key_or_dbref, alignment=None):
    """
    Resolve a start-room specification to an actual Room object.

    Strategy:
    1. If it looks like a dbref (#...), try dbref search first (backward compat).
    2. Try exact key match.
    3. Try partial key match (case-insensitive substring).
    4. Fall back to the first room matching the given alignment's town name.
    5. Alert staff + auto-populate faction rooms, retry alignment search.
    6. Last resort: Limbo (#2).

    This survives realm wipes/reseeds because key-based searches are
    immune to dbref reassignment.
    """
    # --- step 1: dbref ---
    results = search_object(room_key_or_dbref)
    if results:
        return results[0]

    # --- step 2: exact key match via ORM ---
    matches = ObjectDB.objects.filter(
        db_typeclass_path__endswith="Room",
        db_key__iexact=room_key_or_dbref,
    )
    if matches:
        return matches[0]

    # --- step 3: substring match ---
    matches = ObjectDB.objects.filter(
        db_typeclass_path__endswith="Room",
        db_key__icontains=room_key_or_dbref,
    )
    if matches:
        return matches[0]

    # --- step 4: fallback by alignment keywords ---
    faction_room = _search_faction_start_by_alignment(alignment)
    if faction_room:
        return faction_room

    # --- step 5: alert staff and attempt auto-populate, then retry ---
    _alert_and_repopulate_start_rooms(
        alignment=alignment or "unknown",
        room_ref=room_key_or_dbref,
    )
    faction_room = _search_faction_start_by_alignment(alignment)
    if faction_room:
        return faction_room

    # --- step 6: ultimate fallback to Limbo ---
    limbo = search_object("#2")
    return limbo[0] if limbo else None


# ---------------------------------------------------------------------------
# STAT ROLLING ENGINE
# ---------------------------------------------------------------------------

def roll_stats(race_name):
    """
    Roll a complete set of six core stats for a given race.

    Each stat = base_race_stat + random.randint(STAT_VARIANCE_MIN, STAT_VARIANCE_MAX).
    Stats are clamped to a minimum of 1.

    Args:
        race_name (str): The race key from RACES dict.

    Returns:
        dict: Mapping of stat_name -> rolled_value for all six core stats.
    """
    race_data = RACES.get(race_name, RACES["Human"])
    base_stats = race_data.get("stats", {})
    rolled = {}
    for stat in CORE_STATS:
        base = base_stats.get(stat, 10)
        variance = random.randint(STAT_VARIANCE_MIN, STAT_VARIANCE_MAX)
        rolled[stat] = max(1, base + variance)
    return rolled


def format_stats_display(stats):
    """
    Format a stats dict into a readable, color-coded display string.

    Args:
        stats (dict): Mapping of stat_name -> value.

    Returns:
        str: Formatted stat line.
    """
    parts = []
    for stat in CORE_STATS:
        val = stats.get(stat, 10)
        # Color-code: high (>=14) green, low (<=6) red, else white
        if val >= 14:
            color = "|g"
        elif val <= 6:
            color = "|r"
        else:
            color = "|w"
        parts.append(f"{color}{stat.upper():>3}: {val:>2}|n")
    return "  ".join(parts)


# ---------------------------------------------------------------------------
# CHARGEN MENU NODES
# ---------------------------------------------------------------------------

def start(caller, raw_string, **kwargs):
    """Entry point: Choose Faction/Alignment."""
    text = (
        "|w==================================================|n\n"
        "|G         WELCOME TO REALMS OF POWER (ROP)        |n\n"
        "|w==================================================|n\n"
        "Choose your Faction / Alignment to begin character creation:\n"
    )
    options = (
        {"key": "1", "desc": "Good / Neutral Factions (Aethelgard Alliance)", "goto": "node_select_good_race"},
        {"key": "2", "desc": "Evil Factions (Gorgoroth Horde)", "goto": "node_select_evil_race"}
    )
    return text, options


def node_select_good_race(caller, raw_string, **kwargs):
    """Selection for 8 Good/Neutral Races."""
    text = "|G=== SELECT A GOOD / NEUTRAL RACE ===|n\n"
    good_races = [r for r, d in RACES.items() if d["alignment"] in ["Good", "Neutral"]]

    options = []
    for idx, race_name in enumerate(good_races, 1):
        rdata = RACES[race_name]
        desc_str = f"{race_name} (|c{rdata['alignment']}|n) - STR:{rdata['stats']['str']} DEX:{rdata['stats']['dex']} CON:{rdata['stats']['con']}"
        options.append({
            "key": str(idx),
            "desc": desc_str,
            "goto": (_set_race, {"race": race_name})
        })
    options.append({"key": "B", "desc": "Back to Alignment Selection", "goto": "start"})
    return text, options


def node_select_evil_race(caller, raw_string, **kwargs):
    """Selection for 8 Evil Races."""
    text = "|r=== SELECT AN EVIL RACE ===|n\n"
    evil_races = [r for r, d in RACES.items() if d["alignment"] == "Evil"]

    options = []
    for idx, race_name in enumerate(evil_races, 1):
        rdata = RACES[race_name]
        desc_str = f"{race_name} (|rEvil|n) - STR:{rdata['stats']['str']} DEX:{rdata['stats']['dex']} CON:{rdata['stats']['con']}"
        options.append({
            "key": str(idx),
            "desc": desc_str,
            "goto": (_set_race, {"race": race_name})
        })
    options.append({"key": "B", "desc": "Back to Alignment Selection", "goto": "start"})
    return text, options


def _set_race(caller, raw_string, **kwargs):
    """Helper callback to store race and route to class selection."""
    caller.db.chargen_race = kwargs.get("race")
    return "node_select_class"


def node_select_class(caller, raw_string, **kwargs):
    """Selection for 10 Classes — only shows classes valid for the selected race."""
    from world.race_class_matrix import get_valid_classes_for_race

    race = caller.db.chargen_race
    valid_classes = get_valid_classes_for_race(race)

    text = f"Selected Race: |c{race}|n\n\n|w=== SELECT YOUR CLASS ===|n\n"

    options = []
    idx = 1
    for cls_name, cdata in CLASSES.items():
        if cls_name not in valid_classes:
            continue  # Skip classes this race cannot be
        desc_str = f"{cls_name} (HP/lvl: {cdata['hp_per_level']}, Mana/lvl: {cdata['mana_per_level']})"
        options.append({
            "key": str(idx),
            "desc": desc_str,
            "goto": (_set_class, {"cls": cls_name})
        })
        idx += 1
    options.append({"key": "B", "desc": "Back to Race Selection", "goto": "start"})
    return text, options


def _set_class(caller, raw_string, **kwargs):
    """Helper callback to store class and route to stat rolling."""
    caller.db.chargen_class = kwargs.get("cls")
    # Initialize reroll counter
    caller.db.chargen_rerolls_remaining = MAX_REROLLS
    return "node_stat_roll"


# ---------------------------------------------------------------------------
# STAT GENERATION & REROLL NODE
# ---------------------------------------------------------------------------

def node_stat_roll(caller, raw_string, **kwargs):
    """
    Roll (or re-roll) stats and present them to the player.

    On first entry (from class selection), rolls fresh stats.
    On subsequent entries (from reroll), re-rolls all stats.

    Displays:
      - Race and class summary
      - All six rolled stats with color coding
      - Rerolls remaining
      - Options: Accept, Reroll, Start Over
    """
    race = caller.db.chargen_race
    cls = caller.db.chargen_class
    rerolls_left = caller.db.chargen_rerolls_remaining

    # Roll fresh stats every time this node is entered
    stats = roll_stats(race)
    caller.db.chargen_stats = stats

    stat_display = format_stats_display(stats)

    # Calculate derived values for preview
    rdata = RACES[race]
    cdata = CLASSES[cls]
    con_bonus = stats["con"] // 2
    int_wis_bonus = max(stats["int"], stats["wis"]) // 2
    est_hp = 20 + cdata["hp_per_level"] + con_bonus
    est_mana = 10 + cdata["mana_per_level"] + int_wis_bonus

    reroll_text = f"|y{rerolls_left}|n" if rerolls_left > 0 else "|rNone|n"

    text = (
        "|w==================================================|n\n"
        "|G              STAT GENERATION                     |n\n"
        "|w==================================================|n\n"
        f"  Race:      |c{race}|n\n"
        f"  Class:     |c{cls}|n\n"
        f"  Alignment: |c{rdata['alignment']}|n\n"
        "|w--------------------------------------------------|n\n"
        f"  |cRolled Attributes:|n\n"
        f"  {stat_display}\n"
        "|w--------------------------------------------------|n\n"
        f"  Est. HP:   |g{est_hp}|n\n"
        f"  Est. Mana: |c{est_mana}|n\n"
        f"  Rerolls:   {reroll_text}\n"
        "|w==================================================|n\n"
    )

    options = [
        {"key": "1", "desc": "Accept these stats and proceed", "goto": "node_confirm"},
    ]

    if rerolls_left > 0:
        options.append({
            "key": "2",
            "desc": f"Reroll stats ({rerolls_left} remaining)",
            "goto": _do_reroll,
        })

    options.append({"key": "3", "desc": "Start Over", "goto": "start"})

    return text, options


def _do_reroll(caller, raw_string, **kwargs):
    """
    Callback for the reroll option. Decrements the reroll counter
    and returns to the stat roll node for fresh rolls.
    """
    caller.db.chargen_rerolls_remaining -= 1
    return "node_stat_roll"


# ---------------------------------------------------------------------------
# CONFIRMATION & FINALIZATION
# ---------------------------------------------------------------------------

def node_confirm(caller, raw_string, **kwargs):
    """Displays summary and asks for final confirmation."""
    race = caller.db.chargen_race
    cls = caller.db.chargen_class
    rdata = RACES[race]
    cdata = CLASSES[cls]
    stats = caller.db.chargen_stats

    con_bonus = stats["con"] // 2
    int_wis_bonus = max(stats["int"], stats["wis"]) // 2
    est_hp = 20 + cdata["hp_per_level"] + con_bonus
    est_mana = 10 + cdata["mana_per_level"] + int_wis_bonus

    stat_display = format_stats_display(stats)

    text = (
        "|w==================================================|n\n"
        "|G               CHARACTER CONFIRMATION            |n\n"
        "|w==================================================|n\n"
        f"  Race:      |c{race}|n\n"
        f"  Alignment: |c{rdata['alignment']}|n\n"
        f"  Class:     |c{cls}|n\n"
        f"  Base HP:   |g{est_hp}|n\n"
        f"  Base Mana: |g{est_mana}|n\n"
        f"  Stats:     {stat_display}\n"
        "|w==================================================|n\n"
    )

    options = (
        {"key": "1", "desc": "Accept & Create Character", "goto": "node_finalize"},
        {"key": "2", "desc": "Back to Stat Reroll", "goto": "node_stat_roll"},
        {"key": "3", "desc": "Start Over", "goto": "start"},
    )
    return text, options


def node_finalize(caller, raw_string, **kwargs):
    """Create the Character object and finalize."""
    from evennia import create_object
    from evennia.utils import delay
    from world.race_class_matrix import is_race_class_valid

    race = caller.db.chargen_race
    cls = caller.db.chargen_class
    stats = caller.db.chargen_stats

    # Safety net: validate race/class combination
    if not is_race_class_valid(race, cls):
        caller.msg(f"|rInvalid combination: {race}s cannot be {cls}s. Please choose again.|n")
        return "node_select_class"

    r_data = RACES[race]
    c_data = CLASSES[cls]

    # Determine spawn room using robust key-based lookup
    start_room_key = r_data.get("start_room", "#2")
    alignment = r_data.get("alignment", "Good")
    start_room = _find_start_room(start_room_key, alignment=alignment)

    # Use the chosen character name directly, with no race prefix.
    char_name = caller.key

    try:
        new_char = create_object(
            "typeclasses.characters.Character",
            key=char_name,
            location=start_room,
            home=start_room,
        )
    except Exception as err:
        caller.msg(f"|rError creating character: {err}|n")
        return "node_confirm"

    # Set attributes on the character (both db and attributes for robustness)
    new_char.db.race = race
    new_char.attributes.add("race", race)
    new_char.db.character_class = cls
    new_char.attributes.add("class", cls)
    new_char.db.alignment = r_data["alignment"]
    new_char.attributes.add("alignment", r_data["alignment"])
    new_char.db.level = 1
    new_char.attributes.add("level", 1)
    new_char.db.stats = dict(stats)
    new_char.attributes.add("stats", dict(stats))

    con_bonus = stats["con"] // 2
    int_wis_bonus = max(stats["int"], stats["wis"]) // 2

    base_hp = 20 + c_data["hp_per_level"] + con_bonus
    base_mana = 10 + c_data["mana_per_level"] + int_wis_bonus

    # Racial passive: max HP (Ogre +20%) and max mana (High Elf +15%).
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(new_char)
        hp_pct = racial.get("max_hp_pct", 0)
        mana_pct = racial.get("max_mana_pct", 0)
        base_hp = int(base_hp * (1.0 + hp_pct / 100.0))
        base_mana = int(base_mana * (1.0 + mana_pct / 100.0))
    except Exception:
        pass

    # Phase 2.3: talent pool bonuses (Unbreakable hp_per_level, Mana Reservoir)
    try:
        from world.skill_tree import get_talent_pool_bonuses
        pool = get_talent_pool_bonuses(new_char)
        base_hp += pool.get("max_hp", 0)
        base_mana += pool.get("max_mana", 0)
    except Exception:
        pass

    new_char.db.max_hp = base_hp
    new_char.attributes.add("max_hp", base_hp)
    new_char.db.hp = base_hp
    new_char.attributes.add("hp", base_hp)
    new_char.db.max_mana = base_mana
    new_char.attributes.add("max_mana", base_mana)
    new_char.db.mana = base_mana
    new_char.attributes.add("mana", base_mana)

    # Initialize movement
    base_mv = 100
    new_char.attributes.add("mv", base_mv)
    new_char.attributes.add("max_mv", base_mv)

    # Initialize stamina based on CON
    max_stamina = 80 + (stats["con"] * 2) + 2  # level 1 = +2
    new_char.db.stamina = max_stamina
    new_char.attributes.add("stamina", max_stamina)
    new_char.db.max_stamina = max_stamina
    new_char.attributes.add("max_stamina", max_stamina)

    # Initialize XP
    new_char.attributes.add("xp", 0)
    new_char.attributes.add("xp_to_level", 1000)

    # Initialize position to standing
    new_char.db.position = "standing"
    new_char.attributes.add("position", "standing")

    # Initialize equipped items container
    new_char.attributes.add("equipped", {})

    # Initialize save bonuses
    new_char.attributes.add("save_bonuses", {})

    # Initialize practice session
    from world.guildmaster import PracticeSession
    new_char.db.practice_session = PracticeSession()

    # Initialize reputation tracking
    from world.reputation import ReputationSystem
    ReputationSystem.initialize(new_char)

    # Grant class-appropriate starting equipment and gold
    from world.new_player_experience import grant_starting_gear
    gear_messages = grant_starting_gear(new_char)

    # Lock and bind character to account
    new_char.locks.add(f"puppet:id({new_char.id}) or pid({caller.id}) or perm(Admin)")
    caller.characters.add(new_char)

    # Mark creation complete on BOTH the caller AND the new character
    # so at_post_login() doesn't re-launch chargen on either object.
    caller.db.chargen_completed = True
    new_char.db.chargen_completed = True
    new_char.attributes.add("chargen_completed", True)

    # Puppet into the new character after a short delay
    session = caller.sessions.get()[0] if caller.sessions.get() else None
    if session:
        delay(0.3, caller.puppet_object, session, new_char)

    # Show the one-time welcome banner after creation
    from world.new_player_experience import first_login_banner
    banner = first_login_banner(new_char)

    gear_text = "\n".join(gear_messages) if gear_messages else ""

    text = (
        f"\n|gCharacter creation successful!|n\n"
        f"Welcome to Realms of Power as a |c{race} {cls}|n named |w{char_name}|n.\n\n"
        f"{banner}\n\n"
        f"|wStarting Package:|n\n{gear_text}"
    )
    return text, None


# ---------------------------------------------------------------------------
# ENTRY FUNCTION
# ---------------------------------------------------------------------------

def start_chargen(caller):
    """Launches EvMenu for character creation."""
    EvMenu(caller, "world.chargen", start_node="start", auto_quit=True)