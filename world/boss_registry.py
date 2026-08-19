"""
Boss Registry & Spawner for 'rop'
==================================
Defines the complete 30-boss MajorMUD database (15 Gorgoroth Horde Evil +
15 Aethelgard Alliance Good) with level-appropriate stats, faction
alignment, signature rare drops, and global drop announcements.

Provides spawn_all_bosses() to place each boss inside its designated
lair room (created by world.boss_zones.build_boss_lairs()).

Usage (in evennia shell):
    import world.boss_registry as br
    bosses = br.spawn_all_bosses()
"""

from evennia import create_object, search_object
from evennia.objects.objects import DefaultCharacter


# ---------------------------------------------------------------------------
# Boss typeclass
# ---------------------------------------------------------------------------

class Boss(DefaultCharacter):
    """A MajorMUD boss mob with registry metadata and a rare drop."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.is_boss = True
        self.db.is_mob = True


# ---------------------------------------------------------------------------
# Boss-to-Room name mapping
# ---------------------------------------------------------------------------
# Maps each registry key to the exact room key used in boss_zones.py,
# used by spawn_all_bosses() to locate the correct lair.

BOSS_ROOM_LOOKUP = {
    # --- Evil / Gorgoroth Horde ---
    "skeletal_warlord":   "The Ossuary of the Skeletal Warlord",
    "ignis_red_dragon":   "The Smoldering Cavern of the Red Dragon",
    "pit_fiend":          "The Infernal Catacombs of the Pit Fiend",
    "vampire_marquis":    "The Blood Sanctuary of the Vampire Marquis",
    "demon_overlord":     "The Abyssal Rift of the Demon Overlord",
    "hellhound_alpha":    "The Iron Kennel of the Hellhound Alpha",
    "rotting_behemoth":   "The Plague Pit of the Rotting Behemoth",
    "nightstalker":       "The Shadow Lair of the Nightstalker",
    "fire_giant_king":    "The Obsidian Forge of the Fire Giant King",
    "high_priestess":     "The Shadow Temple of the High Priestess",
    "mummy_lord":         "The Cursed Chamber of the Mummy King",
    "chimera":            "The Toxic Vault of the Chimera",
    "hydra":              "The Venom Pit of the Hydra",
    "werewolf_alpha":     "The Howling Den of the Werewolf Alpha",
    "world_eater":        "The Void Threshold of the World-Eater",
    # --- Good / Aethelgard Alliance ---
    "sun_sovereign":      "The Golden Hall of the Sun Sovereign",
    "seraphim_archon":    "The Celestial Dais of the Ancient Dragon",
    "martyr_king":        "The Ruined Altar of the Fallen Angel",
    "treant_lord":        "The Emerald Grove of the Corrupted Treant",
    "sanctified_golem":   "The Granite Quarry of the Stone Golem Lord",
    "sentinel_captain":   "The Storm Pinnacle of the Wyvern Matriarch",
    "arcane_guardian":    "The Crystal Cave of the Arcane Golem",
    "knight_commander":   "The Scorched Nest of the Phoenix",
    "inquisitor_valen":   "The Dread Spire of the Arch-Mage",
    "fallen_angel":       "The Frozen Throne of the Frost Demon",
    "griffin_matriarch":  "The Desolate Shrine of the Banshee Queen",
    "tide_sovereign":     "The Sunken Grotto of the Sea Serpent",
    "holy_avatar":        "The Crypt of the Lich Lord",
    "sacred_phoenix":     "The Lost Temple of the Kraken",
    "crusader_general":   "The Blood-Stained Arena of the Minotaur Warlord",
}


# ---------------------------------------------------------------------------
# Boss Database
# ---------------------------------------------------------------------------
# Each entry: {
#   "name":         display name,
#   "faction":      "Gorgoroth Horde" or "Aethelgard Alliance",
#   "level":        boss level,
#   "hp":           max hit points,
#   "max_damage":   maximum damage per swing,
#   "rare_drop":    signature rare item name,
#   "drop_stats":   short stat summary for the rare drop,
#   "drop_rate":    percent chance to drop,
#   "announce":     global message when the rare drop occurs,
# }

BOSS_REGISTRY = {
    # ==================================================================
    # 15 EVIL BOSSES — Gorgoroth Horde (targets for Good/Alliance players)
    # ==================================================================

    # 1 — Level 15
    "skeletal_warlord": {
        "name": "The Skeletal Warlord",
        "faction": "Gorgoroth Horde",
        "level": 15,
        "hp": 2500,
        "max_damage": 45,
        "rare_drop": "Bone Handled Head Cutter",
        "drop_stats": "+15 Slash Damage, +3 STR, +2 Crit",
        "drop_rate": 5,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain The Skeletal Warlord "
            "and recovered the legendary |R|hBone Handled Head Cutter|n!"
        ),
    },

    # 2 — Level 40
    "ignis_red_dragon": {
        "name": "Ignis the Red Dragon",
        "faction": "Gorgoroth Horde",
        "level": 40,
        "hp": 8000,
        "max_damage": 95,
        "rare_drop": "Dragonscale Breastplate",
        "drop_stats": "+25 Armor, +10 Fire Resistance",
        "drop_rate": 8,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain Ignis the Red Dragon "
            "and recovered the legendary |R|hDragonscale Breastplate|n!"
        ),
    },

    # 3 — Level 35
    "pit_fiend": {
        "name": "Pit Fiend Korvak",
        "faction": "Gorgoroth Horde",
        "level": 35,
        "hp": 6500,
        "max_damage": 80,
        "rare_drop": "Whip of Flayed Souls",
        "drop_stats": "+20 Shadow Damage, Life Drain Proc",
        "drop_rate": 7,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain Pit Fiend Korvak "
            "and recovered the legendary |R|hWhip of Flayed Souls|n!"
        ),
    },

    # 4 — Level 25
    "vampire_marquis": {
        "name": "Marquis von Dread",
        "faction": "Gorgoroth Horde",
        "level": 25,
        "hp": 4000,
        "max_damage": 60,
        "rare_drop": "Bloodstone Amulet",
        "drop_stats": "+10 HP Regen, +5 Vampiric Strike",
        "drop_rate": 8,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain Marquis von Dread "
            "and recovered the legendary |R|hBloodstone Amulet|n!"
        ),
    },

    # 5 — Level 50
    "demon_overlord": {
        "name": "Overlord Malphas",
        "faction": "Gorgoroth Horde",
        "level": 50,
        "hp": 12000,
        "max_damage": 130,
        "rare_drop": "Doomblade of the Nether",
        "drop_stats": "+35 Chaos Damage, +5 STR, +5 INT",
        "drop_rate": 5,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain Overlord Malphas "
            "and recovered the legendary |R|hDoomblade of the Nether|n!"
        ),
    },

    # 6 — Level 8
    "hellhound_alpha": {
        "name": "Hellhound Alpha",
        "faction": "Gorgoroth Horde",
        "level": 8,
        "hp": 1200,
        "max_damage": 22,
        "rare_drop": "Flame-Collared Ring",
        "drop_stats": "+5 Fire Resistance, +3 STR",
        "drop_rate": 12,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain the Hellhound Alpha "
            "and recovered the legendary |R|hFlame-Collared Ring|n!"
        ),
    },

    # 7 — Level 22
    "rotting_behemoth": {
        "name": "The Rotting Behemoth",
        "faction": "Gorgoroth Horde",
        "level": 22,
        "hp": 3500,
        "max_damage": 55,
        "rare_drop": "Blighted Gauntlets",
        "drop_stats": "+12 Armor, Disease Proc",
        "drop_rate": 9,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain The Rotting Behemoth "
            "and recovered the legendary |R|hBlighted Gauntlets|n!"
        ),
    },

    # 8 — Level 32
    "nightstalker": {
        "name": "The Nightstalker",
        "faction": "Gorgoroth Horde",
        "level": 32,
        "hp": 5500,
        "max_damage": 75,
        "rare_drop": "Cloak of Shadows",
        "drop_stats": "+15 Stealth, +10 AGI",
        "drop_rate": 7,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain The Nightstalker "
            "and recovered the legendary |R|hCloak of Shadows|n!"
        ),
    },

    # 9 — Level 30
    "fire_giant_king": {
        "name": "King Surtur",
        "faction": "Gorgoroth Horde",
        "level": 30,
        "hp": 5000,
        "max_damage": 70,
        "rare_drop": "Obsidian Warhammer",
        "drop_stats": "+18 Smash Damage, Fire Proc",
        "drop_rate": 8,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain King Surtur "
            "and recovered the legendary |R|hObsidian Warhammer|n!"
        ),
    },

    # 10 — Level 20
    "high_priestess": {
        "name": "High Priestess Vex",
        "faction": "Gorgoroth Horde",
        "level": 20,
        "hp": 3000,
        "max_damage": 50,
        "rare_drop": "Unholy Staff",
        "drop_stats": "+15 Spell Power, +10 Shadow Damage",
        "drop_rate": 8,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain High Priestess Vex "
            "and recovered the legendary |R|hUnholy Staff|n!"
        ),
    },

    # 11 — Level 18
    "mummy_lord": {
        "name": "Mummy Lord Akhen",
        "faction": "Gorgoroth Horde",
        "level": 18,
        "hp": 2800,
        "max_damage": 48,
        "rare_drop": "Wrappings of Decay",
        "drop_stats": "+10 Armor, Curse Aura",
        "drop_rate": 9,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain Mummy Lord Akhen "
            "and recovered the legendary |R|hWrappings of Decay|n!"
        ),
    },

    # 12 — Level 12
    "chimera": {
        "name": "The Toxic Chimera",
        "faction": "Gorgoroth Horde",
        "level": 12,
        "hp": 1800,
        "max_damage": 34,
        "rare_drop": "Venom-Coated Dagger",
        "drop_stats": "+10 Slash Damage, Poison Proc",
        "drop_rate": 10,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain The Toxic Chimera "
            "and recovered the legendary |R|hVenom-Coated Dagger|n!"
        ),
    },

    # 13 — Level 28
    "hydra": {
        "name": "The Acidic Hydra",
        "faction": "Gorgoroth Horde",
        "level": 28,
        "hp": 4800,
        "max_damage": 68,
        "rare_drop": "Serpent Scale Shield",
        "drop_stats": "+16 Armor, Acid Resistance",
        "drop_rate": 8,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain The Acidic Hydra "
            "and recovered the legendary |R|hSerpent Scale Shield|n!"
        ),
    },

    # 14 — Level 10
    "werewolf_alpha": {
        "name": "Lycan Alpha",
        "faction": "Gorgoroth Horde",
        "level": 10,
        "hp": 1500,
        "max_damage": 28,
        "rare_drop": "Fanged Ring",
        "drop_stats": "+7 Slash Damage, Bleed Proc",
        "drop_rate": 12,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain Lycan Alpha "
            "and recovered the legendary |R|hFanged Ring|n!"
        ),
    },

    # 15 — Level 45
    "world_eater": {
        "name": "The Void World-Eater",
        "faction": "Gorgoroth Horde",
        "level": 45,
        "hp": 10000,
        "max_damage": 110,
        "rare_drop": "Void Crystal Scepter",
        "drop_stats": "+25 Spell Power, Void Proc",
        "drop_rate": 5,
        "announce": (
            "|R[RARE BOSS DROP]|n {killer} has slain The Void World-Eater "
            "and recovered the legendary |R|hVoid Crystal Scepter|n!"
        ),
    },

    # ==================================================================
    # 15 GOOD BOSSES — Aethelgard Alliance (targets for Evil/Horde players)
    # ==================================================================

    # 16 — Level 40
    "sun_sovereign": {
        "name": "Sun Sovereign Aurelius",
        "faction": "Aethelgard Alliance",
        "level": 40,
        "hp": 8000,
        "max_damage": 90,
        "rare_drop": "Aethelgard Crown of Glory",
        "drop_stats": "+25 Armor, +15 Holy Resistance, +30 Mana",
        "drop_rate": 6,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished Sun Sovereign "
            "Aurelius and claimed the |Y|hAethelgard Crown of Glory|n!"
        ),
    },

    # 17 — Level 50
    "seraphim_archon": {
        "name": "Archon Michael",
        "faction": "Aethelgard Alliance",
        "level": 50,
        "hp": 12000,
        "max_damage": 125,
        "rare_drop": "Greatsword of the Heavens",
        "drop_stats": "+30 Holy Damage, +5 STR, Radiant Aura",
        "drop_rate": 5,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished Archon Michael "
            "and claimed the |Y|hGreatsword of the Heavens|n!"
        ),
    },

    # 18 — Level 15
    "martyr_king": {
        "name": "The Martyr King",
        "faction": "Aethelgard Alliance",
        "level": 15,
        "hp": 2500,
        "max_damage": 42,
        "rare_drop": "Sanctified Aegis",
        "drop_stats": "+12 Defense, +10 Holy Spell Power",
        "drop_rate": 8,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished The Martyr King "
            "and claimed the |Y|hSanctified Aegis|n!"
        ),
    },

    # 19 — Level 20
    "treant_lord": {
        "name": "Ancient Treant Lord",
        "faction": "Aethelgard Alliance",
        "level": 20,
        "hp": 3200,
        "max_damage": 50,
        "rare_drop": "Ironwood Staff of Life",
        "drop_stats": "+15 Healing, +20 MP",
        "drop_rate": 8,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished the Ancient "
            "Treant Lord and claimed the |Y|hIronwood Staff of Life|n!"
        ),
    },

    # 20 — Level 25
    "sanctified_golem": {
        "name": "Granite Sentinel",
        "faction": "Aethelgard Alliance",
        "level": 25,
        "hp": 4200,
        "max_damage": 58,
        "rare_drop": "Granite Cuirass",
        "drop_stats": "+20 Armor, Knockback Resistance",
        "drop_rate": 8,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished the Granite "
            "Sentinel and claimed the |Y|hGranite Cuirass|n!"
        ),
    },

    # 21 — Level 8
    "sentinel_captain": {
        "name": "Sentinel Captain Jon",
        "faction": "Aethelgard Alliance",
        "level": 8,
        "hp": 1200,
        "max_damage": 22,
        "rare_drop": "Dawn Watch Ring",
        "drop_stats": "+5 Armor, +3 STR",
        "drop_rate": 12,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished Sentinel "
            "Captain Jon and claimed the |Y|hDawn Watch Ring|n!"
        ),
    },

    # 22 — Level 18
    "arcane_guardian": {
        "name": "Arcane Guardian",
        "faction": "Aethelgard Alliance",
        "level": 18,
        "hp": 2700,
        "max_damage": 48,
        "rare_drop": "Prism Robes",
        "drop_stats": "+12 MP, +10 Spell Power",
        "drop_rate": 9,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished the Arcane "
            "Guardian and claimed the |Y|hPrism Robes|n!"
        ),
    },

    # 23 — Level 32
    "knight_commander": {
        "name": "Knight-Commander Donald",
        "faction": "Aethelgard Alliance",
        "level": 32,
        "hp": 5600,
        "max_damage": 72,
        "rare_drop": "Silver Shield of Valor",
        "drop_stats": "+20 Armor, +10 Holy Resistance",
        "drop_rate": 7,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished Knight-Commander "
            "Donald and claimed the |Y|hSilver Shield of Valor|n!"
        ),
    },

    # 24 — Level 30
    "inquisitor_valen": {
        "name": "High Inquisitor Valen",
        "faction": "Aethelgard Alliance",
        "level": 30,
        "hp": 5100,
        "max_damage": 70,
        "rare_drop": "Mace of Judgment",
        "drop_stats": "+18 Smash Damage, Holy Proc",
        "drop_rate": 8,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished High Inquisitor "
            "Valen and claimed the |Y|hMace of Judgment|n!"
        ),
    },

    # 25 — Level 35
    "fallen_angel": {
        "name": "The Redeemer",
        "faction": "Aethelgard Alliance",
        "level": 35,
        "hp": 6800,
        "max_damage": 82,
        "rare_drop": "Halo of Light",
        "drop_stats": "+18 Spell Power, +15 Holy Resistance",
        "drop_rate": 7,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished The Redeemer "
            "and claimed the |Y|hHalo of Light|n!"
        ),
    },

    # 26 — Level 28
    "griffin_matriarch": {
        "name": "Griffin Matriarch",
        "faction": "Aethelgard Alliance",
        "level": 28,
        "hp": 4700,
        "max_damage": 65,
        "rare_drop": "Feathered Cloak",
        "drop_stats": "+14 AGI, +10 Wind Resistance",
        "drop_rate": 8,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished the Griffin "
            "Matriarch and claimed the |Y|hFeathered Cloak|n!"
        ),
    },

    # 27 — Level 22
    "tide_sovereign": {
        "name": "Tide Sovereign",
        "faction": "Aethelgard Alliance",
        "level": 22,
        "hp": 3400,
        "max_damage": 55,
        "rare_drop": "Coral Trident",
        "drop_stats": "+14 Pierce Damage, Water Proc",
        "drop_rate": 9,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished the Tide "
            "Sovereign and claimed the |Y|hCoral Trident|n!"
        ),
    },

    # 28 — Level 45
    "holy_avatar": {
        "name": "Avatar of Light",
        "faction": "Aethelgard Alliance",
        "level": 45,
        "hp": 9500,
        "max_damage": 105,
        "rare_drop": "Divine Sunburst Staff",
        "drop_stats": "+28 Spell Power, +20 Holy Damage",
        "drop_rate": 5,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished the Avatar of "
            "Light and claimed the |Y|hDivine Sunburst Staff|n!"
        ),
    },

    # 29 — Level 12
    "sacred_phoenix": {
        "name": "Sacred Phoenix",
        "faction": "Aethelgard Alliance",
        "level": 12,
        "hp": 1700,
        "max_damage": 32,
        "rare_drop": "Flame-Feather Ring",
        "drop_stats": "+8 Fire Resistance, Self-Revive Proc",
        "drop_rate": 10,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished the Sacred "
            "Phoenix and claimed the |Y|hFlame-Feather Ring|n!"
        ),
    },

    # 30 — Level 10
    "crusader_general": {
        "name": "Crusader General Vance",
        "faction": "Aethelgard Alliance",
        "level": 10,
        "hp": 1400,
        "max_damage": 26,
        "rare_drop": "Silver Spur",
        "drop_stats": "+6 AGI, +4 STR",
        "drop_rate": 12,
        "announce": (
            "|Y[RARE BOSS DROP]|n {killer} has vanquished Crusader "
            "General Vance and claimed the |Y|hSilver Spur|n!"
        ),
    },
}


# ---------------------------------------------------------------------------
# Spawner
# ---------------------------------------------------------------------------

def _derive_boss_stats(level: int) -> dict:
    """
    Derive balanced combat stats for a boss based on its level.

    Four tiers:
      Basic (1-15): 80 total stat points
      Advanced (16-30): 100 total
      Epic (31-45): 130 total
      Legendary (46-50): 170 total
    """
    if level <= 15:
        total = 80
    elif level <= 30:
        total = 100
    elif level <= 45:
        total = 130
    else:
        total = 170

    # Distribute: STR heavy, then CON, DEX, INT, WIS, CHA
    str_val = int(total * 0.30)
    con_val = int(total * 0.25)
    dex_val = int(total * 0.20)
    int_val = int(total * 0.12)
    wis_val = int(total * 0.08)
    cha_val = total - str_val - con_val - dex_val - int_val - wis_val

    return {
        "str": max(10, str_val),
        "dex": max(10, dex_val),
        "con": max(10, con_val),
        "int": max(10, int_val),
        "wis": max(10, wis_val),
        "cha": max(8, cha_val),
    }


def spawn_all_bosses():
    """
    Create all 30 boss objects inside their designated boss lair rooms.

    Each boss is looked up in BOSS_REGISTRY.  The matching lair room is
    located by searching for the room key listed in BOSS_ROOM_LOOKUP
    (these are the exact room titles from world/boss_zones.py, stripped of
    ANSI color codes).  The boss is then created as a Boss character and
    placed in that room.

    Attributes assigned to each boss:
        stats (derived from level tier), faction, level, hp, max_hp,
        max_damage, xp_value, gold, equipped weapon, rare_drop, drop_stats,
        drop_rate, announce, is_boss, alignment

    Returns:
        dict: {boss_id: boss_object} for all successfully spawned bosses.
    """
    spawned = {}

    for boss_id, data in BOSS_REGISTRY.items():
        # Locate the boss lair by its room key
        room_key = BOSS_ROOM_LOOKUP.get(boss_id)
        if not room_key:
            continue

        rooms = search_object(room_key)
        if not rooms:
            continue

        room = rooms[0]
        level = data["level"]
        stats = _derive_boss_stats(level)

        boss = create_object(Boss, key=data["name"], location=room)
        boss.db.boss_id = boss_id
        boss.db.faction = data["faction"]
        boss.db.level = level
        boss.db.max_hp = data["hp"]
        boss.db.hp = data["hp"]
        boss.db.max_damage = data["max_damage"]
        boss.db.rare_drop = data["rare_drop"]
        boss.db.drop_stats = data["drop_stats"]
        boss.db.drop_rate = data["drop_rate"]
        boss.db.announce = data["announce"]
        boss.db.is_boss = True
        boss.db.is_mob = True

        # Combat stats — what was missing (fix 1.4)
        boss.attributes.add("stats", stats)
        boss.attributes.add("level", level)
        boss.attributes.add("max_hp", data["hp"])
        boss.attributes.add("hp", data["hp"])
        boss.attributes.add("alignment", "Evil" if data["faction"] == "Gorgoroth Horde" else "Good")

        # XP and gold for kill rewards
        boss.attributes.add("xp_value", level * level * 10)  # e.g. level 50 = 25000 XP
        boss.attributes.add("gold_min", level * 5)
        boss.attributes.add("gold_max", level * 15)

        # Equip a scaled weapon so combat engine sees it
        weapon_damage = data["max_damage"] // 2  # half of max_damage as base weapon
        from evennia import create_object as _co
        weapon = _co("typeclasses.objects.Object", key=f"{data['name']}'s Weapon")
        weapon.attributes.add("damage", weapon_damage)
        weapon.attributes.add("damage_type", "slash")
        weapon.attributes.add("slot", "right_hand")
        weapon.attributes.add("weight", 0)
        weapon.attributes.add("value", 0)
        weapon.location = boss
        boss.attributes.add("equipped", {"right_hand": weapon.key})

        # AC: natural armor scaling with level
        natural_armor = level  # 1 AC per level
        boss.attributes.add("armor_value", natural_armor)

        spawned[boss_id] = boss

    return spawned
