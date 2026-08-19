"""
Character Rules, Races, and Classes for 'rop'
Contains 16 Races (8 Good / 8 Evil) and 10 Classes with stats and modifiers.
"""

# ---------------------------------------------------------------------------
# Server Rules / Guidelines (displayed via `rules` or `help rules`)
# ---------------------------------------------------------------------------

RULES_TEXT = """
|y===== Rules of the Realm ====================================|n

|cGENERAL CONDUCT|n

|wRule 1:  |nRespect all players and staff.
|wRule 2:  |nNo spamming, flooding, or excessive vulgarity.
|wRule 3:  |nPlayer killing must follow PvP rules (see |yhelp pvp|n).
|wRule 4:  |nExploiting bugs is prohibited. Report them with |ybug|n.
|wRule 5:  |nBotting / unattended scripting is not allowed.
|wRule 6:  |nDo not impersonate staff members.
|wRule 7:  |nAdvertising other MUDs is forbidden.

|cACCOUNT RULES|n

|wRule 8:  |nEach player is limited to |y3 accounts|n.
|wRule 9:  |nYou may have unlimited characters across your accounts.
|wRule 10: |nDo not share your account password with anyone.
|wRule 11: |nMultiplaying (running multiple characters at once) is
           allowed only if you are |rnot|w engaged in PvP or
           competitive activities.

|cCHANNEL RULES|n

|wRule 12: |nStay on-topic in public channels.
|wRule 13: |nUse |yooc|n and |ygossip|n for out-of-character chat.
|wRule 14: |nNo inflammatory / derogatory speech in any channel.
|wRule 15: |nEnglish only on public channels.

|cPUNISHMENTS|n

|wFirst offense:   |yWarning|n
|wSecond offense:  |yMute (1 hour)|n
|wThird offense:   |yJail (24 hours)|n
|wFourth offense:  |yAccount suspension (7 days)|n
|wFifth offense:   |yPermanent ban|n

|gSevere violations may skip straight to a ban at staff discretion.|n

|y=============================================================|n
"""

# ---------------------------------------------------------------------------
# RACES (16 Total: 8 Good / 8 Evil)
# Start rooms are searched by key - these match rooms created by
# world/massive_realm_builder.py.  Searching by key survives realm
# wipes/reseeds where dbrefs change.
# ---------------------------------------------------------------------------

RACES = {
    # --- GOOD ALIGNMENT ---
    "Human": {
        "alignment": "Good",
        "start_room": "Aethelgard - Shrine of Light",
        "stats": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        "desc": "Versatile and ambitious, Humans adapt quickly to any discipline.",
        "passive": "Adaptable (+5% bonus XP gain)",
        "passive_effect": {"xp_bonus_pct": 5}
    },
    "High Elf": {
        "alignment": "Good",
        "start_room": "Aethelgard - Shrine of Light",
        "stats": {"str": 7, "dex": 12, "con": 8, "int": 14, "wis": 12, "cha": 11},
        "desc": "Noble and ancient, highly attuned to arcane forces.",
        "passive": "Arcane Affinity (+15% Max Mana)",
        "passive_effect": {"max_mana_pct": 15}
    },
    "Wood Elf": {
        "alignment": "Good",
        "start_room": "Aethelgard - Shrine of Light",
        "stats": {"str": 8, "dex": 14, "con": 9, "int": 10, "wis": 13, "cha": 10},
        "desc": "Swift forest dwellers with uncanny instincts and deadly aim.",
        "passive": "Forest Step (+10% Dodge Rate)",
        "passive_effect": {"dodge_chance_pct": 10}
    },
    "Mountain Dwarf": {
        "alignment": "Good",
        "start_room": "Aethelgard - Shrine of Light",
        "stats": {"str": 13, "dex": 8, "con": 14, "int": 8, "wis": 10, "cha": 7},
        "desc": "Resilient, stout warriors crafted from stone and iron.",
        "passive": "Stone Skin (+5 Base Armor Class)",
        "passive_effect": {"armor_class": 5}
    },
    "Stout Halfling": {
        "alignment": "Good",
        "start_room": "Aethelgard - Shrine of Light",
        "stats": {"str": 6, "dex": 15, "con": 11, "int": 9, "wis": 10, "cha": 13},
        "desc": "Small in stature but incredibly nimble and surprisingly tough.",
        "passive": "Lucky (+5% Critical Strike Chance)",
        "passive_effect": {"crit_chance_pct": 5}
    },
    "Gnome": {
        "alignment": "Good",
        "start_room": "Aethelgard - Shrine of Light",
        "stats": {"str": 5, "dex": 11, "con": 9, "int": 15, "wis": 12, "cha": 10},
        "desc": "Master inventors and magical tinkers with brilliant minds.",
        "passive": "Keen Mind (+10 Magic Resistance)",
        "passive_effect": {"magic_resist_pct": 10}
    },
    "Centaur": {
        "alignment": "Good",
        "start_room": "Aethelgard - Shrine of Light",
        "stats": {"str": 12, "dex": 11, "con": 12, "int": 8, "wis": 10, "cha": 7},
        "desc": "Powerful half-human, half-horse guardians of the open plains.",
        "passive": "Gallop (+20% Movement Speed)",
        "passive_effect": {"move_speed_pct": 20}
    },
    "Pixie": {
        "alignment": "Good",
        "start_room": "Aethelgard - Shrine of Light",
        "stats": {"str": 4, "dex": 16, "con": 6, "int": 13, "wis": 11, "cha": 14},
        "desc": "Tiny winged fae creatures with incredible agility and innate glamour.",
        "passive": "Flight (+15% Evasion, immune to ground traps)",
        "passive_effect": {"evasion_pct": 15, "trap_immune": True}
    },

    # --- EVIL ALIGNMENT ---
    "Orc": {
        "alignment": "Evil",
        "start_room": "Gorgoroth - Dark Temple",
        "stats": {"str": 14, "dex": 9, "con": 13, "int": 6, "wis": 7, "cha": 5},
        "desc": "Brutal frontline warmongers who thrive on bloodshed.",
        "passive": "Berserk Rage (+10% Melee Damage)",
        "passive_effect": {"melee_dmg_pct": 10}
    },
    "Dark Elf": {
        "alignment": "Evil",
        "start_room": "Gorgoroth - Dark Temple",
        "stats": {"str": 8, "dex": 14, "con": 8, "int": 13, "wis": 10, "cha": 9},
        "desc": "Subterranean assassins and dark sorcerers who strike from shadows.",
        "passive": "Shadowmeld (+15% Stealth Efficiency)",
        "passive_effect": {"stealth_efficiency_pct": 15}
    },
    "Undead": {
        "alignment": "Evil",
        "start_room": "Gorgoroth - Dark Temple",
        "stats": {"str": 10, "dex": 8, "con": 14, "int": 11, "wis": 11, "cha": 2},
        "desc": "Reanimated corpses bound by dark magic, feeling no pain.",
        "passive": "Unliving (Immune to Poison & Bleed)",
        "passive_effect": {"poison_immune": True, "bleed_immune": True}
    },
    "Goblin": {
        "alignment": "Evil",
        "start_room": "Gorgoroth - Dark Temple",
        "stats": {"str": 7, "dex": 15, "con": 9, "int": 11, "wis": 7, "cha": 5},
        "desc": "Cunning, greedy scavengers who rely on speed and underhanded tactics.",
        "passive": "Scavenger (+15% Bonus Gold Drops)",
        "passive_effect": {"gold_bonus_pct": 15}
    },
    "Minotaur": {
        "alignment": "Evil",
        "start_room": "Gorgoroth - Dark Temple",
        "stats": {"str": 15, "dex": 7, "con": 14, "int": 5, "wis": 8, "cha": 5},
        "desc": "Massive bovine behemoths capable of crushing enemies underfoot.",
        "passive": "Gore (+10% Chance to Stun on Hit)",
        "passive_effect": {"stun_chance_pct": 10}
    },
    "Lizardfolk": {
        "alignment": "Evil",
        "start_room": "Gorgoroth - Dark Temple",
        "stats": {"str": 11, "dex": 11, "con": 13, "int": 7, "wis": 9, "cha": 4},
        "desc": "Cold-blooded reptilian hunters with thick scaled hide.",
        "passive": "Thick Scales (+4 Natural Armor Class)",
        "passive_effect": {"armor_class": 4}
    },
    "Ogre": {
        "alignment": "Evil",
        "start_room": "Gorgoroth - Dark Temple",
        "stats": {"str": 16, "dex": 5, "con": 15, "int": 4, "wis": 5, "cha": 3},
        "desc": "Towering giants possessing crushing brute strength and massive health.",
        "passive": "Thick Skull (+20% Max Health)",
        "passive_effect": {"max_hp_pct": 20}
    },
    "Demonkin": {
        "alignment": "Evil",
        "start_room": "Gorgoroth - Dark Temple",
        "stats": {"str": 10, "dex": 10, "con": 10, "int": 13, "wis": 9, "cha": 12},
        "desc": "Fiendish mortals carrying the bloodline of the Nether Hells.",
        "passive": "Hellfire Resistance (+15 Fire/Dark Magic Resistance)",
        "passive_effect": {"fire_resist_pct": 15, "dark_resist_pct": 15}
    }
}


# ---------------------------------------------------------------------------
# CLASSES (10 Total)
# ---------------------------------------------------------------------------

CLASSES = {
    "Warrior": {
        "primary_stat": "str",
        "hp_per_level": 15,
        "mana_per_level": 2,
        "desc": "Frontline heavy armor juggernauts specializing in weapons and shields."
    },
    "Paladin": {
        "primary_stat": "str",
        "hp_per_level": 13,
        "mana_per_level": 6,
        "desc": "Holy crusaders blending heavy melee combat with healing and defense."
    },
    "Cleric": {
        "primary_stat": "wis",
        "hp_per_level": 10,
        "mana_per_level": 12,
        "desc": "Divine casters devoted to mending allies and purging enemies."
    },
    "Mage": {
        "primary_stat": "int",
        "hp_per_level": 6,
        "mana_per_level": 16,
        "desc": "Masters of destructive elemental magic and arcane utility."
    },
    "Rogue": {
        "primary_stat": "dex",
        "hp_per_level": 9,
        "mana_per_level": 4,
        "desc": "Stealthy combatants specializing in lockpicking, poisons, and critical strikes."
    },
    "Warlock": {
        "primary_stat": "int",
        "hp_per_level": 8,
        "mana_per_level": 14,
        "desc": "Dark casters who drain soul energy and deal damage over time."
    },
    "Druid": {
        "primary_stat": "wis",
        "hp_per_level": 10,
        "mana_per_level": 10,
        "desc": "Nature guardians capable of shapeshifting, healing, and casting storms."
    },
    "Ranger": {
        "primary_stat": "dex",
        "hp_per_level": 10,
        "mana_per_level": 6,
        "desc": "Deadly marksmen and wilderness trackers adept at ranged combat."
    },
    "Monk": {
        "primary_stat": "dex",
        "hp_per_level": 11,
        "mana_per_level": 5,
        "desc": "Unarmed martial artists utilizing speed, ki power, and strikes."
    },
    "Necromancer": {
        "primary_stat": "int",
        "hp_per_level": 7,
        "mana_per_level": 15,
        "desc": "Commanders of death who raise undead minions and siphon life force."
    }
}


# ---------------------------------------------------------------------------
# EXPERIENCE / LEVELING
# ---------------------------------------------------------------------------

def xp_to_level(level):
    """
    Return the XP threshold required to reach the given level.

    Early levels use a gentle curve so new players progress quickly:
      Level 2:   500 XP  (~28 level-1 kills)
      Level 3:  1000 XP  (~56 level-1 kills)
      Level 5:  2500 XP
      Level 10: 7500 XP
      Level 20: 25000 XP
      Level 50: 125000 XP
      Level 80: 280000 XP

    Formula: 500 * level^1.4 (rounded to nearest 50 for readability).
    """
    import math
    raw = 500 * (level ** 1.4)
    return max(500, int(round(raw / 50) * 50))


def stats_on_level_up(char_class="Warrior", character=None):
    """
    Return the base stat increments awarded per level-up, scaled by class.

    Each class gets a focused distribution reflecting its primary attributes:
      - Warriors get +2 STR/CON, +1 DEX, +0 INT/WIS/CHA
      - Mages get +2 INT/WIS, +1 DEX, +0 STR/CON/CHA
      - Rogues get +2 DEX, +1 STR/CHA, +0 CON/INT/WIS

    Args:
        char_class: The character's class name (default "Warrior")
        character: Optional character object for compatibility

    Returns:
        dict: Mapping of stat_name -> points gained this level
    """
    # Base: every class gets at least +1 to all stats per level
    base = {"str": 1, "dex": 1, "con": 1, "int": 1, "wis": 1, "cha": 1}

    # Class-specific bonus points (on top of base)
    class_bonuses = {
        "Warrior":    {"str": 1, "con": 1, "dex": 0, "int": -1, "wis": -1, "cha": -1},
        "Paladin":    {"str": 1, "wis": 1, "con": 0, "int": 0, "dex": 0, "cha": 0},
        "Cleric":     {"wis": 2, "con": 0, "int": 0, "str": -1, "dex": -1, "cha": 0},
        "Mage":       {"int": 2, "wis": 1, "dex": 0, "str": -1, "con": -1, "cha": -1},
        "Rogue":      {"dex": 2, "cha": 1, "str": 0, "int": 0, "con": -1, "wis": -1},
        "Warlock":    {"int": 2, "cha": 1, "wis": 0, "str": -1, "dex": -1, "con": -1},
        "Druid":      {"wis": 2, "con": 1, "dex": 0, "str": -1, "int": -1, "cha": -1},
        "Ranger":     {"dex": 2, "str": 1, "con": 0, "int": -1, "wis": -1, "cha": -1},
        "Monk":       {"dex": 2, "wis": 1, "con": 0, "str": 0, "int": -1, "cha": -1},
        "Necromancer":{"int": 2, "wis": 1, "con": 0, "str": -1, "dex": -1, "cha": 0},
    }

    bonuses = class_bonuses.get(char_class, class_bonuses["Warrior"])
    result = {}
    for stat in base:
        total = base[stat] + bonuses.get(stat, 0)
        # Never go below 0 stat gain per level
        result[stat] = max(0, total)

    return result


# ---------------------------------------------------------------------------
# WARPOINTS SYSTEM
# ---------------------------------------------------------------------------

# Base warpoints awarded for a cross-faction PvP kill against an equal-level
# opponent.  Scaled up or down based on level difference.
BASE_WARPOINTS = 50

# Minimum level difference before warpoints start to diminish.
# Killing a player more than this many levels below you reduces the award.
WARPOINTS_LEVEL_FLOOR = 5

# Warpoints multiplier per level the victim is above the killer.
WARPOINTS_LEVEL_BONUS = 0.10  # +10% per level above

# Warpoints penalty per level the victim is below the killer (beyond the floor).
WARPOINTS_LEVEL_PENALTY = 0.20  # -20% per level below (beyond floor)

# Minimum warpoints that can be awarded (never zero for a valid cross-faction kill).
MIN_WARPOINTS = 5


def get_racial_bonuses(character) -> dict:
    """
    Return the passive_effect dict for a character's race, or an empty dict
    if the character has no race or the race has no passive_effect defined.

    This is the central hook for racial passives.  All systems that need to
    apply racial bonuses (damage, AC, movement, stealth, XP, gold, etc.)
    should call this function.

    Args:
        character: A Character or Mob object with a 'race' attribute.

    Returns:
        dict: The passive_effect mapping (e.g. {"melee_dmg_pct": 10, ...})
              or an empty dict if none defined.
    """
    race = None
    if hasattr(character, "attributes"):
        race = character.attributes.get("race", default=None)
    if not race:
        return {}

    race_data = RACES.get(race, {})
    return race_data.get("passive_effect", {})


def calculate_warpoints(killer_level, victim_level):
    """
    Calculate warpoints awarded for a cross-faction PvP kill.

    Scaling rules:
      - Equal or higher-level victim: full BASE_WARPOINTS + bonus per level above.
      - Victim within WARPOINTS_LEVEL_FLOOR levels below: full BASE_WARPOINTS.
      - Victim more than WARPOINTS_LEVEL_FLOOR levels below: diminishing returns,
        down to a minimum of MIN_WARPOINTS to prevent farming low-level alts.

    Args:
        killer_level (int): Level of the killer.
        victim_level (int): Level of the victim.

    Returns:
        int: Warpoints awarded (always >= MIN_WARPOINTS for valid kills).
    """
    level_diff = victim_level - killer_level

    if level_diff >= 0:
        # Victim is equal or higher level — bonus for fighting up
        bonus = 1.0 + (level_diff * WARPOINTS_LEVEL_BONUS)
        return max(MIN_WARPOINTS, int(BASE_WARPOINTS * bonus))

    # Victim is lower level
    levels_below = abs(level_diff)

    if levels_below <= WARPOINTS_LEVEL_FLOOR:
        # Within the floor — full base award
        return BASE_WARPOINTS

    # Beyond the floor — diminishing returns
    penalty_levels = levels_below - WARPOINTS_LEVEL_FLOOR
    penalty = 1.0 - (penalty_levels * WARPOINTS_LEVEL_PENALTY)
    # Clamp penalty so it never goes below 0.1 (10% of base)
    penalty = max(0.1, penalty)
    return max(MIN_WARPOINTS, int(BASE_WARPOINTS * penalty))
