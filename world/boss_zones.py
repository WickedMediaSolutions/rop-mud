"""
Boss Lair Zones for 'rop'
==========================
Defines 30 high-contrast, atmospheric boss chambers attached to existing
regional endpoints across the East/West realms and Neutral territories.

Each boss lair is a standalone room with:
  - A vivid ANSI color-coded title
  - A 3-line atmospheric description
  - Tags for boss_lair identification and zone attachment
  - A db.is_boss_lair flag for downstream combat/loot systems

Usage (in evennia shell):
    import world.boss_zones as bz
    lairs = bz.build_boss_lairs()
"""

from evennia import create_object, search_tag


# ---------------------------------------------------------------------------
# Boss Lair Definitions
# ---------------------------------------------------------------------------
# Each entry: (boss_id, title, zone_anchor, description_lines)
# zone_anchor is the zone_key from builder_phase1.py that this lair attaches to.

BOSS_LAIR_DEFS = [
    # 1
    (
        "boss_red_dragon",
        "|RThe Smoldering Cavern of the Red Dragon|n",
        "hellfire_spire",
        (
            "|rRivers of molten rock snake across the basalt floor, their crimson glow",
            "pulsing like a living heartbeat. The air shimmers with blistering heat as",
            "a mountain of obsidian scales shifts restlessly atop a throne of cooled magma.|n",
        ),
    ),
    # 2
    (
        "boss_skeletal_warlord",
        "|WThe Ossuary of the Skeletal Warlord|n",
        "bone_fields",
        (
            "|wCountless bones are stacked floor to vaulted ceiling in grotesque architectural",
            "precision—femurs form pillars, ribs arch into buttresses, and skulls stare",
            "empty-eyed from every niche. At the center, a throne of fused vertebrae awaits.|n",
        ),
    ),
    # 3
    (
        "boss_lich_lord",
        "|xThe Crypt of the Lich Lord|n",
        "vile_grounds",
        (
            "|mA palpable chill leaches the warmth from your bones as frost-limned sarcophagi",
            "line the walls in silent rows. Faint whispers in a dead language coil through",
            "the darkness, and a single phylactery pulses with sickly green light at the altar.|n",
        ),
    ),
    # 4
    (
        "boss_high_priestess",
        "|MThe Shadow Temple of the High Priestess|n",
        "drow_caverns_sub",
        (
            "|mBlack marble columns carved into twisting serpents rise toward an invisible",
            "ceiling lost in shadow. Incense burners shaped like screaming faces exhale",
            "cloying violet smoke, and a veiled altar drips with fresh offerings of blood.|n",
        ),
    ),
    # 5
    (
        "boss_sea_serpent",
        "|BThe Sunken Grotto of the Sea Serpent|n",
        "dawn_light_coast",
        (
            "|bBioluminescent barnacles cast an eerie blue-green glow across walls encrusted",
            "with centuries of coral and salt. Water drips from stalactites in a slow,",
            "hypnotic rhythm, and something vast coils in the ink-black depths below.|n",
        ),
    ),
    # 6
    (
        "boss_fire_giant_king",
        "|YThe Obsidian Forge of the Fire Giant King|n",
        "obsidian_ridge",
        (
            "|RA colossal anvil carved from a single block of volcanic glass dominates the",
            "chamber, still ringing from the last hammer-blow. Rivers of molten iron",
            "channel through rune-carved troughs, and the walls weep beads of liquid flame.|n",
        ),
    ),
    # 7
    (
        "boss_frost_demon",
        "|CThe Frozen Throne of the Frost Demon|n",
        "desolation_pass",
        (
            "|cA throne of never-melting ice rises at the heart of a hexagonal chamber whose",
            "walls are etched with frost-scrolls of ancient infernal pacts. Your breath",
            "crystallizes mid-air as the temperature plunges toward absolute zero.|n",
        ),
    ),
    # 8
    (
        "boss_vampire_marquis",
        "|RThe Blood Sanctuary of the Vampire Marquis|n",
        "blood_river_delta",
        (
            "|rCrimson tapestries depicting centuries of slaughter adorn walls that seem to",
            "weep fresh blood from invisible pores. A grand obsidian chalice rests upon",
            "an altar of fused bone, and the air tastes of copper and old wine.|n",
        ),
    ),
    # 9
    (
        "boss_fallen_angel",
        "|WThe Ruined Altar of the Fallen Angel|n",
        "astraea_ruins",
        (
            "|wShattered stained-glass windows once depicting celestial glory now lie in",
            "jagged shards across a cracked marble floor. A pair of scorched, six-winged",
            "silhouettes are burned into the stone behind a toppled altar, still smoldering.|n",
        ),
    ),
    # 10
    (
        "boss_chimera",
        "|GThe Toxic Vault of the Chimera|n",
        "verdant_mire",
        (
            "|gPools of bubbling green ichor dot the floor, each one releasing tendrils of",
            "caustic vapor that etch the stone walls. The skeletons of failed hunters",
            "lie half-dissolved in the sludge, their armor still softly hissing as it corrodes.|n",
        ),
    ),
    # 11
    (
        "boss_arch_mage",
        "|MThe Dread Spire of the Arch-Mage|n",
        "hellfire_spire",
        (
            "|mArcane circles spiral across every surface—floor, walls, and the domed ceiling—",
            "each one humming at a different dissonant frequency. Floating grimoires orbit",
            "a central lectern where a single open page blazes with forbidden incantations.|n",
        ),
    ),
    # 12
    (
        "boss_hellhound_alpha",
        "|rThe Iron Kennel of the Hellhound Alpha|n",
        "ashen_wastes",
        (
            "|RCharred iron bars line both sides of a long, soot-blackened hall, each cell",
            "scored deep with claw marks. The floor is littered with splintered bone and",
            "scraps of slag-metal, and a low, rumbling growl vibrates through the iron plates.|n",
        ),
    ),
    # 13
    (
        "boss_hydra",
        "|gThe Venom Pit of the Hydra|n",
        "blighted_chasm",
        (
            "|GA vast circular pit descends into darkness, its walls slick with glistening",
            "venom that glows faintly yellow-green. Dozens of shed scales the size of",
            "shields litter the rim, each one still dripping with paralytic toxin.|n",
        ),
    ),
    # 14
    (
        "boss_stone_golem_lord",
        "|wThe Granite Quarry of the Stone Golem Lord|n",
        "stoneguard_mines",
        (
            "|WColossal blocks of rough-hewn granite stand in silent ranks like a petrified",
            "army awaiting orders. Chisel marks cover every surface, and the dust-filled",
            "air carries the grinding rumble of stone shifting against ancient stone.|n",
        ),
    ),
    # 15
    (
        "boss_banshee_queen",
        "|xThe Desolate Shrine of the Banshee Queen|n",
        "screaming_canyons",
        (
            "|wA ruined shrine perches at the edge of a howling abyss, its altar cloth",
            "long since rotted to tattered grey wisps. The wind screams through the",
            "canyon with an almost-human wail, and spectral forms flicker at the edge of sight.|n",
        ),
    ),
    # 16
    (
        "boss_phoenix",
        "|YThe Scorched Nest of the Phoenix|n",
        "great_sun_wastes",
        (
            "|RAn enormous nest woven from charred cedar boughs and molten gold filaments",
            "crowns a pillar of fused desert glass. Ash swirls in lazy thermals, and",
            "the entire chamber pulses with waves of regenerative heat and blinding light.|n",
        ),
    ),
    # 17
    (
        "boss_mummy_king",
        "|yThe Cursed Chamber of the Mummy King|n",
        "great_sun_wastes",
        (
            "|YHieroglyphs etched in tarnished gold leaf cover every inch of the sandstone",
            "walls, telling tales of a deathless tyrant. Canopic jars sealed with wax",
            "and ancient sigils line the perimeter, and a sarcophagus of black basalt waits open.|n",
        ),
    ),
    # 18
    (
        "boss_demon_overlord",
        "|RThe Abyssal Rift of the Demon Overlord|n",
        "dread_valley",
        (
            "|rThe floor splits open into a yawning chasm that descends into roiling crimson",
            "clouds and distant screams. Black iron chains as thick as tree trunks stretch",
            "across the rift, each link etched with binding runes that flicker and fail.|n",
        ),
    ),
    # 19
    (
        "boss_corrupted_treant",
        "|GThe Emerald Grove of the Corrupted Treant|n",
        "eldergrove_thicket",
        (
            "|gWhat was once a sacred grove now festers with black sap oozing from twisted",
            "bark. Thorned vines slither across the ground with predatory intent, and",
            "the ancient heart-tree at the center pulses with a sickly, fungal green light.|n",
        ),
    ),
    # 20
    (
        "boss_werewolf_alpha",
        "|YThe Howling Den of the Werewolf Alpha|n",
        "rotwood_forest",
        (
            "|wA cavernous den reeking of musk and old blood, its walls gouged with",
            "territorial claw-marks that spell out dominance in a language of savagery.",
            "Scattered across the floor are the gnawed bones of challengers who failed.|n",
        ),
    ),
    # 21
    (
        "boss_wyvern_matriarch",
        "|CThe Storm Pinnacle of the Wyvern Matriarch|n",
        "highland_pass",
        (
            "|cA windswept aerie perched atop the highest crag, where lightning arcs",
            "continuously between iron-grey storm clouds and the jagged peak. The",
            "nest is a tangle of shattered treetops and the scorched armor of fallen knights.|n",
        ),
    ),
    # 22
    (
        "boss_rotting_behemoth",
        "|gThe Plague Pit of the Rotting Behemoth|n",
        "blighted_chasm",
        (
            "|GA vast sinkhole filled with bubbling, necrotic sludge that releases clouds",
            "of choking miasma. Half-digested carcasses of enormous creatures protrude",
            "from the muck at grotesque angles, their flesh still sloughing off in sheets.|n",
        ),
    ),
    # 23
    (
        "boss_sun_sovereign",
        "|YThe Golden Hall of the Sun Sovereign|n",
        "golden_plains",
        (
            "|WBlinding radiance reflects off every surface—polished gold tiles, mirrored",
            "columns, and a domed ceiling inlaid with sunstone mosaics. The air hums",
            "with concentrated solar energy, and the floor is warm as living skin.|n",
        ),
    ),
    # 24
    (
        "boss_nightstalker",
        "|xThe Shadow Lair of the Nightstalker|n",
        "under_tunnels",
        (
            "|mA darkness so absolute it feels solid presses against your eyes, swallowing",
            "even magical light within arm's reach. The only sound is the soft skitter",
            "of something circling patiently, just beyond the edge of perception.|n",
        ),
    ),
    # 25
    (
        "boss_arcane_golem",
        "|CThe Crystal Cave of the Arcane Golem|n",
        "echoing_caverns",
        (
            "|cThousands of mana-crystals jut from every surface at precise geometric angles,",
            "each one humming at a slightly different pitch to form an eerie, resonant chord.",
            "At the center, a dormant construct of living crystal waits to be awakened.|n",
        ),
    ),
    # 26
    (
        "boss_pit_fiend",
        "|RThe Infernal Catacombs of the Pit Fiend|n",
        "brimstone_courtyard",
        (
            "|rSulfur-crusted tunnels twist downward into a labyrinth of fire and brimstone,",
            "the walls themselves seeming to breathe with slow, malevolent exhalations.",
            "Iron cages hang from the ceiling, each containing the charred remains of a soul.|n",
        ),
    ),
    # 27
    (
        "boss_kraken",
        "|BThe Lost Temple of the Kraken|n",
        "south_shore",
        (
            "|bA drowned temple leans at a precarious angle, its halls half-flooded with",
            "seawater that rises and falls with the distant tide. Barnacle-encrusted",
            "tentacles are carved into every archway, their stone suckers still sharp as blades.|n",
        ),
    ),
    # 28
    (
        "boss_world_eater",
        "|xThe Void Threshold of the World-Eater|n",
        "desolation_pass",
        (
            "|mA perfect sphere of absolute nothingness hovers at the chamber's center,",
            "its event horizon ringed with the frozen light of consumed stars. The",
            "stone floor around it has been worn smooth by eons of slow, inevitable approach.|n",
        ),
    ),
    # 29
    (
        "boss_minotaur_warlord",
        "|RThe Blood-Stained Arena of the Minotaur Warlord|n",
        "blood_forge",
        (
            "|rA circular arena sunk deep into the bedrock, its sand floor permanently",
            "stained rust-red from countless death-matches. The walls are lined with",
            "the broken weapons and shattered shields of every challenger who has ever fallen.|n",
        ),
    ),
    # 30
    (
        "boss_ancient_dragon",
        "|YThe Celestial Dais of the Ancient Dragon|n",
        "astraea_ruins",
        (
            "|WA floating platform of white marble drifts among the stars, tethered to",
            "the mortal realm by chains of pure starlight. Constellations wheel overhead",
            "in impossible patterns, and the dais thrums with the weight of primordial power.|n",
        ),
    ),
]


# ---------------------------------------------------------------------------
# Public builder function
# ---------------------------------------------------------------------------

def build_boss_lairs():
    """
    Create 30 boss lair rooms attached to existing regional zone endpoints.

    Each lair is created as a typeclasses.rooms.Room with:
      - High-contrast ANSI color title
      - 3-line atmospheric description
      - Tags: boss_lair (category), zone_anchor (category), and unique boss_id
      - db.is_boss_lair = True

    Returns:
        dict: {boss_id: room_object} mapping each boss identifier to its room.
    """
    lairs = {}

    for boss_id, title, zone_anchor, desc_lines in BOSS_LAIR_DEFS:
        # Build the full description from the 3-line tuple
        desc = "\n".join(desc_lines)

        # Create the room
        room = create_object("typeclasses.rooms.Room", key=title)
        room.db.desc = desc
        room.db.is_boss_lair = True

        # Tagging: boss_lair category, zone anchor, and unique boss_id
        room.tags.add("boss_lair", category="room_type")
        room.tags.add(zone_anchor, category="zone_anchor")
        room.tags.add(boss_id, category="boss_id")

        lairs[boss_id] = room

    return lairs