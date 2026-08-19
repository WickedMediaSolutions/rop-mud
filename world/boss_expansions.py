"""
Dungeon Expansion Chains for 'rop'
===================================
Builds 30 multi-room dungeon expansion chains (15 Gorgoroth Evil + 15
Aethelgard Good) that connect regional realm endpoints to the 30 boss
lairs defined in world/boss_zones.py.

Each chain contains 5–10 rooms with dynamic, depth-aware descriptions
and bidirectional exits linking the rooms in sequence. The final room
in each chain connects to the matching boss chamber.

Usage (in evennia shell):
    import world.boss_expansions as be
    expansions = be.build_dungeon_expansions()
"""

from evennia import create_object, search_tag
from evennia.objects.objects import DefaultRoom, DefaultExit


# ---------------------------------------------------------------------------
# Room description helpers
# ---------------------------------------------------------------------------

def _depth_desc(room_num, total, dungeon_name, faction_color, depth_flavor):
    """Generate a room description reflecting dungeon depth."""
    progress = f"[Room {room_num}/{total}]"
    return (
        f"{faction_color}{dungeon_name} {progress}|n\n\n"
        f"{depth_flavor[room_num - 1]}"
    )


def _link_rooms(room_a, room_b, exit_name_forward, exit_name_back):
    """Create bidirectional exits between two rooms."""
    ext_fwd = create_object(
        "typeclasses.exits.Exit",
        key=exit_name_forward,
        location=room_a,
        destination=room_b,
    )
    ext_back = create_object(
        "typeclasses.exits.Exit",
        key=exit_name_back,
        location=room_b,
        destination=room_a,
    )
    return ext_fwd, ext_back


# ---------------------------------------------------------------------------
# Dungeon Expansion Definitions
# ---------------------------------------------------------------------------
# Each entry:
#   (dungeon_id, dungeon_name, faction, room_count, boss_id, flavor_lines,
#    exit_dir_forward, exit_dir_back)

DUNGEON_EXPANSIONS = [
    # ==================================================================
    # GORGOROTH HORDE (EVIL) — 15 Dungeons
    # ==================================================================

    # 1 — The Catacombs of Despair → Skeletal Warlord (Lvl 15)
    (
        "dng_catacombs_despair",
        "The Catacombs of Despair",
        "evil",
        5,
        "boss_skeletal_warlord",
        [
            "|rThe entrance yawns like a wound in the earth, its crumbling archway "
            "festooned with the femurs of long-dead prisoners. A cold draft carries "
            "the faint rattle of dry bones from deep within the catacombs.|n",
            "|rNarrow stone corridors branch in every direction, the walls lined with "
            "niches packed tight with age-yellowed skulls. Somewhere in the distance, "
            "a bony finger taps out a slow, patient rhythm against the stone.|n",
            "|rThe floor here is carpeted with shattered ribcages that crunch underfoot "
            "like dry leaves. Faint phosphorescent fungi cast a sickly green glow on "
            "walls slick with ancient moisture and mineral deposits.|n",
            "|rThe corridor widens into a macabre gallery—entire skeletons are fused "
            "into the walls in poses of eternal agony, their jaws frozen mid-scream. "
            "The air grows heavier, colder, and the tapping sound has stopped.|n",
            "|RThe catacombs open into a vast ossuary, a cathedral of bone where "
            "countless dead stand silent vigil. A throne of fused vertebrae dominates "
            "the chamber ahead, and the air thrums with ancient malice.|n",
        ],
        "north",
        "south",
    ),

    # 2 — The Volcanic Trenches → Red Dragon (Lvl 40)
    (
        "dng_volcanic_trenches",
        "The Volcanic Trenches",
        "evil",
        8,
        "boss_red_dragon",
        [
            "|rThe ground trembles beneath your feet as you descend into a smoking "
            "fissure. Jagged obsidian walls weep beads of molten glass, and the air "
            "shimmers with waves of oppressive heat.|n",
            "|rA narrow stone bridge spans a river of churning magma, its surface "
            "cracked and glowing faintly orange from the heat below. Sulfurous steam "
            "vents erupt at irregular intervals, scalding anyone caught off guard.|n",
            "|RThe trench floor is a maze of cooled lava tubes, their glassy walls "
            "reflecting distorted, flame-lit silhouettes. The roar of a distant "
            "eruption echoes through the stone, deep and ominous.|n",
            "|RGeodes studded with fire opals line the walls here, pulsing with a "
            "rhythmic inner light that matches the heartbeat of the mountain. Each "
            "pulse sends a wave of heat rippling through the chamber.|n",
            "|RThe path dips sharply into a ravine where the walls glow cherry-red "
            "and rivulets of molten iron trace glowing veins through the basalt. "
            "The heat is nearly unbearable; your breath comes in ragged gasps.|n",
            "|RAn immense cavern opens ahead, its ceiling lost in swirling smoke and "
            "ash. Pillars of cooled magma rise like the bars of a colossal cage, and "
            "the floor is littered with the charred bones of previous explorers.|n",
            "|RThe trench narrows to a single winding passage, its walls so hot they "
            "radiate visible waves of distortion. The distant sound of something vast "
            "shifting its weight echoes from the cavern beyond.|n",
            "|RYou emerge onto a ledge overlooking a sea of fire. Across the molten "
            "expanse, a throne of obsidian scales awaits—the lair of the great red "
            "dragon, where the very stone breathes flame.|n",
        ],
        "north",
        "south",
    ),

    # 3 — The Iron Tunnels → Fire Giant King (Lvl 35)
    (
        "dng_iron_tunnels",
        "The Iron Tunnels",
        "evil",
        6,
        "boss_fire_giant_king",
        [
            "|rThe tunnel mouth is reinforced with black iron bands, each one stamped "
            "with the smoldering rune of the fire giant clans. The clang of an immense "
            "hammer striking an anvil reverberates from somewhere deep within.|n",
            "|rWalls of raw iron ore streak the tunnel in bands of rust and hematite. "
            "Massive chain hoists dangle from the ceiling, their iron links each as "
            "thick as a warrior's arm, still swaying gently from some unseen force.|n",
            "|RThe tunnel opens into a forge-chamber where a river of molten slag "
            "flows through a carved stone channel. Tongs and hammers the size of "
            "battering rams lean against the walls, radiating residual heat.|n",
            "|RHeat shimmers distort the air as you pass rows of giant-sized anvils, "
            "each one scarred by millennia of hammer-blows. The rhythmic pounding "
            "grows louder, shaking dust from the tunnel ceiling.|n",
            "|RThe floor is a mosaic of cooled slag and discarded ingots of black "
            "iron. Sparks fountain from a side passage where unseen hands work "
            "bellows the size of siege engines, feeding the eternal forge fires.|n",
            "|RThe tunnel terminates at a colossal iron door carved with the image "
            "of a crowned giant wreathed in flames. The door is slightly ajar, and "
            "blinding orange light spills through the gap along with waves of heat.|n",
        ],
        "north",
        "south",
    ),

    # 4 — The Crypts of Blood → Vampire Marquis (Lvl 18)
    (
        "dng_crypts_blood",
        "The Crypts of Blood",
        "evil",
        5,
        "boss_vampire_marquis",
        [
            "|rA narrow stairwell spirals downward, its steps slick with a dark, "
            "sticky residue that glistens wetly in the torchlight. The copper scent "
            "of old blood hangs thick in the stagnant air.|n",
            "|rThe crypt corridor is lined with alcoves, each containing an ornate "
            "sarcophagus carved from dark marble. Faint scratching sounds emanate "
            "from within the stone coffins, as if something is trying to get out.|n",
            "|rCrimson tapestries drape the walls here, depicting scenes of ancient "
            "feasts where the guests are pale and the wine is thick. A chalice of "
            "tarnished silver sits on a pedestal, still half-full.|n",
            "|rThe passage opens into a grand hall where chandeliers of black iron "
            "hold candles that burn with an eerie blue flame. Portraits of a gaunt "
            "noble family line the walls, their eyes following your every move.|n",
            "|RThe hall narrows to a single obsidian door inscribed with the heraldry "
            "of the Nightveil bloodline. Beyond it, the sickly sweet scent of old "
            "wine and fresh blood beckons you forward.|n",
        ],
        "north",
        "south",
    ),

    # 5 — The Pit of Torment → Demon Overlord (Lvl 50)
    (
        "dng_pit_torment",
        "The Pit of Torment",
        "evil",
        7,
        "boss_demon_overlord",
        [
            "|rA spiral staircase carved into living bone descends into darkness, "
            "each step inscribed with a name that seems to writhe and change as "
            "you look at it. Screams drift up from the depths below.|n",
            "|rThe walls of this chamber are formed from fused, screaming faces—each "
            "one trapped in a moment of eternal agony. Chains dangle from the ceiling, "
            "some still holding the rusted shackles of former prisoners.|n",
            "|RThe pit opens into a vast cavern where cages of black iron hang over "
            "a bottomless chasm. Some cages are empty; others hold desiccated corpses "
            "that twitch and moan as you pass.|n",
            "|RThe path narrows to a bridge of fused vertebrae spanning a river of "
            "boiling blood. The bridge groans under your weight, and far below, "
            "something massive stirs in the crimson depths.|n",
            "|RYou enter a chamber ringed with iron thrones, each one occupied by "
            "a chained skeletal figure wearing a crown of rusted nails. In the center, "
            "a summoning circle etched in salt and ash still smolders.|n",
            "|RThe walls here are lined with mirrors of black glass that reflect not "
            "your image but twisted, demonic versions of yourself. Each reflection "
            "grins with too many teeth as you pass.|n",
            "|RThe tunnel ends at a precipice overlooking a roiling abyss of crimson "
            "clouds. Black iron chains stretch across the void toward a distant rift "
            "where the demon overlord holds court.|n",
        ],
        "down",
        "up",
    ),

    # 6 — The Smoldering Kennels → Hellhound Alpha (Lvl 8)
    (
        "dng_smoldering_kennels",
        "The Smoldering Kennels",
        "evil",
        4,
        "boss_hellhound_alpha",
        [
            "|rThe entrance is a low, soot-stained archway from which a wave of "
            "animal heat and the stench of sulfur pours forth. Deep claw marks score "
            "the stone on either side of the passage.|n",
            "|rIron-barred cells line both sides of the corridor, their floors "
            "littered with charred bones and tufts of singed black fur. Something "
            "in the darkness growls—a low, rumbling sound that vibrates in your chest.|n",
            "|rThe kennel widens into a feeding chamber where slabs of scorched meat "
            "hang from iron hooks. Water troughs carved from volcanic rock bubble "
            "with a black, tar-like liquid that reeks of brimstone.|n",
            "|RThe corridor ends at a massive iron door, its surface warped and "
            "buckled from the heat within. Through the gaps, you can see the glow "
            "of ember-bright eyes and hear the alpha's deep, menacing growl.|n",
        ],
        "north",
        "south",
    ),

    # 7 — The Rotten Swamps → Rotting Behemoth (Lvl 27)
    (
        "dng_rotten_swamps",
        "The Rotten Swamps",
        "evil",
        6,
        "boss_rotting_behemoth",
        [
            "|gThe ground turns soft and treacherous underfoot as you enter the swamp, "
            "each step releasing a puff of foul-smelling gas. Twisted cypress trees "
            "drip with pale moss that waves like drowned hair in the stagnant breeze.|n",
            "|gPools of bubbling black water dot the path, their surfaces iridescent "
            "with a film of decay. The bloated carcass of a giant swamp creature lies "
            "half-submerged, its flesh still slowly sloughing off into the murk.|n",
            "|GThe path narrows to a causeway of half-rotted logs lashed together with "
            "creeping vines. Below, something large and pale moves just beneath the "
            "surface of the black water, stirring up clouds of bone fragments.|n",
            "|GThe swamp thickens into a grove of dead trees whose bark weeps a thick, "
            "amber-hued pus. Giant leeches pulse lazily on the trunks, each one the "
            "size of a hunting dog, their bodies glistening with disease.|n",
            "|GThe causeway ends at a sinkhole rimmed with the skeletons of creatures "
            "that tried and failed to climb out. A foul miasma rises from the pit, "
            "thick enough to taste, carrying the stench of centuries of decay.|n",
            "|GThe sinkhole descends into a vast underground chamber where the floor "
            "is a churning sea of necrotic sludge. Half-digested remains of enormous "
            "beasts protrude from the muck at grotesque angles.|n",
        ],
        "down",
        "up",
    ),

    # 8 — The Shadowed Catacombs → Nightstalker (Lvl 5)
    (
        "dng_shadowed_catacombs",
        "The Shadowed Catacombs",
        "evil",
        5,
        "boss_nightstalker",
        [
            "|xThe entrance is little more than a crack in the canyon wall, a slit "
            "of absolute darkness that swallows all light. The air that seeps out "
            "is cold and carries the faint, musky scent of a predator's den.|n",
            "|xThe tunnel twists sharply, and the darkness deepens until it feels "
            "like a physical weight pressing against your skin. Your footsteps echo "
            "strangely, as if something is walking just behind you, matching your pace.|n",
            "|mA small chamber opens up, lit only by a faint phosphorescent glow from "
            "fungi growing on the ceiling. The walls are covered in deep scratches—"
            "territorial markings left by something large and deeply territorial.|n",
            "|mThe tunnel constricts to a crawlspace where the ceiling dips low enough "
            "to force you onto your hands and knees. The stone is worn smooth, as if "
            "something has slithered through here countless times before.|n",
            "|xThe passage opens into a final chamber where the darkness is so complete "
            "it swallows even magical light. The only sound is a soft, patient skitter "
            "circling slowly just beyond the edge of perception.|n",
        ],
        "north",
        "south",
    ),

    # 9 — The Brimstone Descent → Pit Fiend (Lvl 48)
    (
        "dng_brimstone_descent",
        "The Brimstone Descent",
        "evil",
        6,
        "boss_pit_fiend",
        [
            "|rSulfur-encrusted steps spiral downward into a haze of yellow-green "
            "fumes. The air is thick with the acrid stench of brimstone, and each "
            "breath burns your throat like cheap gin.|n",
            "|rThe stairwell opens into a chamber where vents in the floor blast "
            "superheated steam at irregular intervals. The walls are coated in "
            "crystalline sulfur deposits that glow faintly in the dim light.|n",
            "|RThe descent continues through a maze of narrow, twisting tunnels where "
            "the walls themselves seem to breathe—slow, rhythmic expansions and "
            "contractions that pulse with a malevolent heartbeat.|n",
            "|RIron cages hang from the ceiling at various heights, some empty, "
            "others containing the charred, skeletal remains of condemned souls. "
            "Chains rattle softly, though there is no breeze to move them.|n",
            "|RThe tunnel opens into a grand hall lined with pillars of fused bone "
            "and brimstone. At the center, a pit of molten rock and iron bubbles "
            "slowly, casting dancing shadows on the walls.|n",
            "|RThe hall terminates at a massive archway carved from a single block "
            "of obsidian, its surface etched with infernal contracts written in a "
            "language that burns the eyes to read. Hellfire flickers beyond.|n",
        ],
        "down",
        "up",
    ),

    # 10 — The Howling Canyons → Banshee Queen (Lvl 26)
    (
        "dng_howling_canyons",
        "The Howling Canyons",
        "evil",
        5,
        "boss_banshee_queen",
        [
            "|xThe canyon walls rise sheer on either side, their surfaces worn smooth "
            "by eons of screaming wind. The gale that funnels through the passage "
            "carries an almost-human wail that sets your teeth on edge.|n",
            "|wThe path narrows to a ledge barely wide enough for two to walk abreast, "
            "with a sheer drop into mist on one side. Tattered strips of grey fabric "
            "snagged on the rocks flutter like lost spirits in the wind.|n",
            "|wThe canyon widens into a natural amphitheater where the wind howls "
            "through dozens of erosion-carved flutes in the rock face. The resulting "
            "chorus sounds like a choir of the damned singing a funeral dirge.|n",
            "|wThe ledge passes through a field of standing stones, each one carved "
            "with a woman's face contorted in an eternal scream. The wind whistles "
            "through the stones, giving each face a different, agonized voice.|n",
            "|xThe path ends at a ruined shrine perched on the edge of a howling "
            "abyss. Spectral forms flicker in the corner of your eye, and the wind "
            "screams a name over and over—a name that sounds disturbingly like yours.|n",
        ],
        "north",
        "south",
    ),

    # 11 — The Venom Tunnels → Hydra (Lvl 16)
    (
        "dng_venom_tunnels",
        "The Venom Tunnels",
        "evil",
        5,
        "boss_hydra",
        [
            "|gThe tunnel entrance is ringed with sickly yellow-green crystals that "
            "drip a viscous, glowing fluid. The air burns slightly on your skin, and "
            "the scent of something caustic and organic fills your nostrils.|n",
            "|gThe walls of the tunnel are slick with a glistening residue that glows "
            "faintly in the dark. Dozens of shed scales the size of dinner plates "
            "litter the floor, their edges still razor-sharp.|n",
            "|GThe tunnel opens into a chamber where the ceiling is obscured by thick "
            "webs of some fibrous, organic material. Dripping from the strands are "
            "drops of concentrated venom that hiss when they strike the stone floor.|n",
            "|GThe passage constricts to a narrow tube, its walls coated in a layer "
            "of slime that numbs the skin on contact. The tunnel slopes downward at "
            "a steep angle, forcing you to half-slide toward the depths below.|n",
            "|GThe tunnel ends at the rim of a vast circular pit. The walls are slick "
            "with paralytic toxin, and dozens of shed scales litter the edge. From "
            "the darkness below comes the sound of many throats hissing in unison.|n",
        ],
        "down",
        "up",
    ),

    # 12 — The Dread Vaults → Lich Lord (Lvl 30)
    (
        "dng_dread_vaults",
        "The Dread Vaults",
        "evil",
        5,
        "boss_lich_lord",
        [
            "|mThe vault entrance is a slab of black granite etched with warding "
            "sigils that still flicker with a faint, unwholesome light. The air "
            "that escapes is cold enough to form frost on your lips.|n",
            "|mThe corridor is lined with niches containing canopic jars of ancient "
            "design, their seals still intact. Each jar pulses with a faint inner "
            "light, and whispers in a dead language coil through the darkness.|n",
            "|xThe vault opens into a scriptorium where rotted scrolls and crumbling "
            "codices are stacked floor to ceiling. In the center, a lectern holds "
            "a single open book whose pages turn by themselves in the still air.|n",
            "|xThe passage descends through a series of archways, each one inscribed "
            "with the names of the lich lord's defeated enemies. The names grow more "
            "recent as you progress, and the last archway bears a name you recognize.|n",
            "|MThe vault ends at a chamber of black ice where sarcophagi line the "
            "walls in silent rows. A phylactery pulses with sickly green light at "
            "the altar, and the air is heavy with centuries of hoarded power.|n",
        ],
        "north",
        "south",
    ),

    # 13 — The Spider Caverns → High Priestess (Lvl 21)
    (
        "dng_spider_caverns",
        "The Spider Caverns",
        "evil",
        5,
        "boss_high_priestess",
        [
            "|mThe cavern entrance is veiled by thick curtains of spider silk that "
            "part with an unsettling, sticky resistance. The air is heavy with the "
            "cloying scent of incense and something darker beneath it.|n",
            "|mThe passage is lined with alcoves where statues of a many-armed "
            "goddess stand in poses of ecstatic worship. Each statue holds a bowl "
            "that catches the steady drip of dark liquid from the ceiling above.|n",
            "|MThe cavern widens into a temple antechamber where black marble columns "
            "carved into twisting serpents rise toward an invisible ceiling. Braziers "
            "burn with violet flame, casting unsettling shadows that move independently.|n",
            "|MThe floor here is a mosaic depicting a great spider at the center of "
            "a web that spans the entire chamber. The web's strands are inlaid with "
            "silver that catches the violet light and seems to pulse with a life of "
            "its own.|n",
            "|MThe passage ends at a veil of black silk embroidered with silver "
            "threads in the pattern of a screaming face. Incense smoke coils through "
            "the veil, and the sound of a woman's soft, hypnotic chanting beckons "
            "from beyond.|n",
        ],
        "north",
        "south",
    ),

    # 14 — The Frozen Passage → Frost Demon (Lvl 32)
    (
        "dng_frozen_passage",
        "The Frozen Passage",
        "evil",
        5,
        "boss_frost_demon",
        [
            "|cThe passage mouth is rimed with ice that never melts, even in the "
            "hottest summer. A bitter wind howls from within, carrying crystals of "
            "ice that sting like tiny needles against exposed skin.|n",
            "|cThe tunnel walls are sheathed in a layer of blue-white ice so clear "
            "you can see the frozen bodies of ancient warriors trapped within. Their "
            "faces are frozen in expressions of abject terror, eyes wide and staring.|n",
            "|CThe passage widens into a chamber where icicles the size of spears "
            "hang from the ceiling in glittering rows. The floor is a sheet of black "
            "ice that reflects the ice above in a disorienting, infinite mirror.|n",
            "|CThe tunnel descends into a crevasse where the walls are etched with "
            "frost-scrolls of ancient infernal pacts. Your breath crystallizes in "
            "mid-air, and the cold is so intense it burns like fire.|n",
            "|CThe passage ends at an archway of ice so pure it is nearly invisible. "
            "Beyond it, a throne of never-melting ice rises in a hexagonal chamber "
            "where the temperature plunges toward absolute zero.|n",
        ],
        "north",
        "south",
    ),

    # 15 — The Blood Arena Corridors → Minotaur Warlord (Lvl 19)
    (
        "dng_blood_arena",
        "The Blood Arena Corridors",
        "evil",
        5,
        "boss_minotaur_warlord",
        [
            "|rThe corridor walls are rough-hewn stone, stained dark with old blood "
            "that has seeped into the very rock. The distant roar of a crowd echoes "
            "faintly, along with the clash of steel on steel.|n",
            "|rThe passage is lined with rusted weapon racks holding the shattered "
            "remains of swords, axes, and shields—trophies taken from defeated "
            "challengers. Each broken weapon is tagged with a name and a date.|n",
            "|RThe corridor opens into a gladiator's ready-room where manacles hang "
            "from the walls and the floor is scarred with the desperate claw marks "
            "of those who were dragged, unwilling, into the arena.|n",
            "|RThe passage narrows to a tunnel that slopes downward, its walls "
            "covered in crude tally marks—hundreds of them, each one representing "
            "a death in the arena above. The marks grow fresher as you descend.|n",
            "|RThe tunnel ends at a heavy iron portcullis, its bars slick with blood "
            "so fresh it still drips. Beyond the gate, you can hear the heavy "
            "breathing of something immense pacing back and forth on blood-soaked sand.|n",
        ],
        "down",
        "up",
    ),

    # ==================================================================
    # AETHELGARD ALLIANCE (GOOD) — 15 Dungeons
    # ==================================================================

    # 16 — The Sunspire Cloisters → Sun Sovereign (Lvl 38)
    (
        "dng_sunspire_cloisters",
        "The Sunspire Cloisters",
        "good",
        6,
        "boss_sun_sovereign",
        [
            "|WThe cloister entrance is a grand archway of white marble, its keystone "
            "carved with a radiant sunburst. Warm light spills from within, and the "
            "air carries the faint scent of incense and old parchment.|n",
            "|WThe corridor is lined with arched windows of stained glass depicting "
            "scenes of solar triumph—the sun god banishing darkness, crowning kings, "
            "and healing the wounded. The light through the glass paints the floor in "
            "jewel-toned patterns.|n",
            "|YThe cloister opens into a courtyard where a fountain of liquid gold "
            "bubbles at the center of a mosaic floor. The mosaic depicts the sun in "
            "all its phases, from the faintest dawn to the blazing zenith.|n",
            "|YThe passage continues through a hall of mirrors where every surface—"
            "floor, walls, ceiling—is polished to a blinding brilliance. Your "
            "reflection is multiplied a thousand times, each one glowing with an "
            "inner radiance that is not entirely your own.|n",
            "|YThe cloister narrows to a staircase of white marble that spirals "
            "upward, each step inscribed with a verse from the solar hymns. The "
            "air grows warmer with each step, and the light intensifies.|n",
            "|YThe staircase ends at a pair of golden doors inlaid with sunstone "
            "mosaics that pulse with stored solar energy. The doors are warm to the "
            "touch, and light blazes through the seams like a captive star.|n",
        ],
        "up",
        "down",
    ),

    # 17 — The Celestial Staircase → Ancient Dragon (Lvl 50)
    (
        "dng_celestial_staircase",
        "The Celestial Staircase",
        "good",
        10,
        "boss_ancient_dragon",
        [
            "|WThe staircase begins at the summit of the highest peak, a single "
            "step of white marble floating unsupported in the air. Beyond it, more "
            "steps rise into the clouds, each one glowing faintly with starlight.|n",
            "|WThe stairs wind upward through a layer of silver clouds that part "
            "before you like a veil. The air grows thin and pure, and the world "
            "below shrinks to a patchwork of greens and browns.|n",
            "|WThe staircase passes through a belt of stars—actual stars, miniature "
            "suns that float in lazy orbits around the marble steps. They hum with "
            "a frequency that resonates deep in your bones.|n",
            "|WThe stairs broaden into a platform where constellations are visible "
            "beneath your feet, their patterns shifting and reforming in an endless "
            "celestial dance. The Milky Way streams past like a river of diamond dust.|n",
            "|WThe ascent continues through a nebula of violet and gold, its tendrils "
            "of cosmic dust parting around you like the fingers of a gentle hand. "
            "The silence here is absolute and profound.|n",
            "|WThe staircase passes a waystation—a small platform with a fountain "
            "that pours liquid starlight into a basin of obsidian. Drinking from it "
            "fills you with a warmth that has nothing to do with heat.|n",
            "|WThe stairs wind through a region where time itself seems to slow. "
            "Each step takes an eternity, and the stars wheel overhead in slow, "
            "majestic arcs that span millennia in a single glance.|n",
            "|WThe staircase rises through a veil of pure white light that strips "
            "away all shadow and all doubt. When you emerge, you are standing on a "
            "platform of marble that floats among the constellations.|n",
            "|WThe final stretch of stairs is lined with statues of ancient dragons "
            "carved from starlight itself, their forms semi-transparent and ever-"
            "shifting. Each one turns its head to watch you pass with knowing eyes.|n",
            "|WThe staircase ends at a floating dais of white marble tethered to "
            "the mortal realm by chains of pure starlight. Constellations wheel "
            "overhead in impossible patterns, and the dais thrums with primordial power.|n",
        ],
        "up",
        "down",
    ),

    # 18 — The Sacred Catacombs → Fallen Angel (Lvl 36)
    (
        "dng_sacred_catacombs",
        "The Sacred Catacombs",
        "good",
        5,
        "boss_fallen_angel",
        [
            "|wThe entrance is a modest archway of white stone, half-hidden behind "
            "a curtain of flowering vines. The air that drifts out is cool and "
            "carries the faint sound of distant, mournful chanting.|n",
            "|wThe catacomb walls are lined with the sarcophagi of honored saints, "
            "each one carved with their likeness and the deeds that earned them "
            "their place here. Candles burn at each sarcophagus, their flames steady "
            "and unwavering.|n",
            "|WThe passage opens into a chapel where shattered stained-glass windows "
            "depict the fall of an angel—six wings, a blazing sword, and a descent "
            "into darkness. The fragments of glass on the floor still glow faintly.|n",
            "|WThe catacombs descend into a deeper chamber where the walls are "
            "scorched black as if by a great fire. The smell of ozone and burnt "
            "feathers hangs in the air, and the stone underfoot is cracked and heat-"
            "fractured in a radial pattern.|n",
            "|WThe passage ends at a marble altar that has been toppled and cracked "
            "in two. A pair of scorched, six-winged silhouettes are burned into the "
            "stone behind it, and the air thrums with the echo of an ancient tragedy.|n",
        ],
        "down",
        "up",
    ),

    # 19 — The Emerald Wilderness → Corrupted Treant (Lvl 10)
    (
        "dng_emerald_wilderness",
        "The Emerald Wilderness",
        "good",
        7,
        "boss_corrupted_treant",
        [
            "|GThe trail begins at the edge of a pristine forest, where ancient oaks "
            "tower overhead and dappled sunlight filters through a canopy of emerald "
            "leaves. Birdsong fills the air, and the path is soft with moss.|n",
            "|GThe trail winds deeper into the woods, where the trees grow thicker "
            "and the sunlight grows dimmer. The birdsong fades, replaced by an "
            "unnatural silence broken only by the creak of ancient branches.|n",
            "|gThe forest begins to change—the moss underfoot gives way to a slick, "
            "black substance that oozes between your toes. The trees here bear "
            "strange cankers that weep a dark, viscous sap.|n",
            "|gThe trail passes through a grove where the trees are twisted into "
            "agonized shapes, their bark split and seeping a foul-smelling ichor. "
            "Thorned vines slither across the path with a disturbingly purposeful "
            "motion.|n",
            "|gThe wilderness deepens into a region of perpetual twilight, where "
            "the canopy is so thick no light penetrates. Fungal growths on the "
            "trees pulse with a sickly green bioluminescence that casts more shadow "
            "than light.|n",
            "|gThe path constricts to a narrow trail hemmed in by walls of thorned "
            "bramble. The thorns seem to reach toward you as you pass, and the "
            "scratches they leave on your armor fester with a black, spreading stain.|n",
            "|GThe trail ends at a clearing dominated by an immense heart-tree, "
            "its trunk twisted and blackened, its leaves long since fallen. The "
            "ground around it is dead and bare, and the tree pulses with a slow, "
            "malignant heartbeat.|n",
        ],
        "north",
        "south",
    ),

    # 20 — The Granite Deep → Stone Golem Lord (Lvl 13)
    (
        "dng_granite_deep",
        "The Granite Deep",
        "good",
        6,
        "boss_stone_golem_lord",
        [
            "|wThe quarry entrance is a vast, open pit carved into the mountainside, "
            "its walls showing the strata of millennia in bands of grey and white. "
            "Massive blocks of rough-hewn granite lie scattered around the entrance.|n",
            "|wThe descent into the quarry follows a road paved with granite dust "
            "that sparkles faintly in the light. The walls rise higher on either "
            "side, and the sound of distant chiseling echoes from deep within.|n",
            "|WThe quarry road passes through a field of unfinished statues—warriors, "
            "guardians, and beasts, all carved from granite but left incomplete. "
            "Some are missing heads, others arms, and a few stand frozen mid-step "
            "as if simply waiting for the command to move.|n",
            "|WThe passage narrows to a tunnel carved through living rock, its walls "
            "bearing the marks of chisels and hammers. The dust in the air is thick "
            "enough to taste, and the grinding rumble of stone on stone vibrates "
            "through the floor.|n",
            "|WThe tunnel opens into a vast underground hall where columns of granite "
            "rise like a petrified forest. Each column is carved with the face of a "
            "different guardian, their stone eyes watching you with ancient patience.|n",
            "|WThe hall ends at a massive stone door carved from a single slab of "
            "granite, its surface etched with the image of a crowned golem lord. "
            "The door grinds open slowly, revealing ranks of silent stone soldiers "
            "standing at attention.|n",
        ],
        "down",
        "up",
    ),

    # 21 — The Dawn Outpost Trail → Werewolf Alpha (Lvl 6)
    (
        "dng_dawn_outpost",
        "The Dawn Outpost Trail",
        "good",
        4,
        "boss_werewolf_alpha",
        [
            "|WThe trail begins at a small wooden outpost flying the Aethelgard "
            "sunburst banner. The path is well-trodden and lined with wildflowers, "
            "but the outpost walls are scarred with deep claw marks.|n",
            "|WThe trail winds through a meadow where the grass is trampled flat "
            "in wide, circular patches. Tufts of coarse grey fur are caught on the "
            "brambles, and the prints of massive paws lead deeper into the woods.|n",
            "|wThe path enters the treeline, where the friendly meadow gives way to "
            "a dark and tangled forest. The trees here are scored with territorial "
            "claw marks, and the undergrowth rustles with something large that moves "
            "just out of sight.|n",
            "|wThe trail ends at the mouth of a cavern that reeks of musk and old "
            "blood. The floor is littered with the gnawed bones of deer and wild "
            "boar, and a low, rumbling growl echoes from the darkness within.|n",
        ],
        "north",
        "south",
    ),

    # 22 — The Crystal Pass → Arcane Golem (Lvl 25)
    (
        "dng_crystal_pass",
        "The Crystal Pass",
        "good",
        5,
        "boss_arcane_golem",
        [
            "|CThe pass begins at a narrow cleft in the mountainside, its walls "
            "studded with small crystals that catch the light and scatter it into "
            "rainbow fragments. A faint, musical hum emanates from the passage.|n",
            "|CThe pass widens into a corridor where mana-crystals of increasing "
            "size protrude from the walls at precise geometric angles. Each crystal "
            "hums at a slightly different pitch, creating a chord that resonates "
            "in your chest.|n",
            "|CThe tunnel opens into a chamber where the ceiling is a dome of "
            "interlocking crystal plates, each one glowing with a soft inner light. "
            "The floor is a mosaic of crystal shards arranged in arcane sigils.|n",
            "|CThe passage continues through a gallery where crystal formations "
            "have grown into the shapes of arcane symbols—circles, triangles, and "
            "more complex geometries that hurt to look at directly. The air crackles "
            "with stored magical energy.|n",
            "|CThe pass ends at a cavern where thousands of mana-crystals jut from "
            "every surface, each one humming at a slightly different pitch. At the "
            "center, a dormant construct of living crystal waits to be awakened.|n",
        ],
        "north",
        "south",
    ),

    # 23 — The Stormwind Ascent → Wyvern Matriarch (Lvl 29)
    (
        "dng_stormwind_ascent",
        "The Stormwind Ascent",
        "good",
        5,
        "boss_wyvern_matriarch",
        [
            "|CThe ascent begins at the base of a windswept crag where the grass "
            "is flattened permanently by the ceaseless gale. Lightning arcs between "
            "the iron-grey clouds overhead, and the air smells of ozone and rain.|n",
            "|CThe trail switchbacks up the mountainside, each turn bringing you "
            "closer to the storm clouds that wreathe the peak. The wind grows "
            "stronger with each step, tugging at your cloak and screaming past "
            "your ears.|n",
            "|cThe path narrows to a knife-edge ridge with sheer drops on both "
            "sides. The wind here is strong enough to stagger a grown man, and "
            "the rocks are slick with condensed moisture from the ever-present "
            "storm clouds.|n",
            "|cThe ridge widens into a plateau where the remnants of old nests "
            "litter the ground—shattered treetops, scorched armor, and the bones "
            "of mountain goats picked clean. Lightning strikes the peak with "
            "regular, deafening cracks.|n",
            "|CThe ascent ends at a windswept aerie perched atop the highest crag. "
            "The nest is a tangle of shattered timber and scorched metal, and "
            "lightning arcs continuously between the clouds and the jagged peak.|n",
        ],
        "up",
        "down",
    ),

    # 24 — The Sunken Coast Caves → Sea Serpent (Lvl 24)
    (
        "dng_sunken_coast",
        "The Sunken Coast Caves",
        "good",
        5,
        "boss_sea_serpent",
        [
            "|BThe cave entrance is half-hidden behind a waterfall that cascades "
            "down the coastal cliffs. Salt spray hangs in the air, and the roar "
            "of the ocean mingles with the thunder of falling water.|n",
            "|bThe cave floor is slick with seawater and dotted with tide pools "
            "where anemones wave their tentacles in the dim light. The walls are "
            "encrusted with barnacles and pale, calcium-deposited formations.|n",
            "|BThe tunnel descends beneath the water table, and the walls glisten "
            "with a constant seep of seawater. The sound of dripping water echoes "
            "in the darkness, and the air grows thick with the scent of salt and "
            "decaying seaweed.|n",
            "|bThe cave opens into a vast underground lagoon where bioluminescent "
            "algae paint the water in swirling patterns of blue and green. Something "
            "large breaks the surface briefly before submerging again with a heavy "
            "splash.|n",
            "|BThe lagoon narrows to a flooded channel where the ceiling dips low "
            "enough to force you to wade through waist-deep, ink-black water. The "
            "walls are alive with glowing barnacles that pulse in a slow, hypnotic "
            "rhythm.|n",
        ],
        "down",
        "up",
    ),

    # 25 — The Toxic Wilds → Chimera (Lvl 12)
    (
        "dng_toxic_wilds",
        "The Toxic Wilds",
        "good",
        5,
        "boss_chimera",
        [
            "|gThe path leaves the main road and enters a region where the vegetation "
            "is unnaturally lush and brightly colored. Flowers of impossible hues "
            "nod in the breeze, and the air is thick with a cloying, chemical "
            "sweetness.|n",
            "|gThe trail grows more treacherous as the ground turns spongy and "
            "unstable. Pools of viscous green liquid bubble lazily on either side, "
            "each one releasing tendrils of vapor that sting the eyes and throat.|n",
            "|GThe wilderness deepens into a region where the trees are draped in "
            "phosphorescent moss that glows with a sickly yellow-green light. The "
            "skeletons of small animals lie scattered on the ground, their bones "
            "pitted and etched as if by acid.|n",
            "|GThe path winds through a grove of trees whose bark is peeling away "
            "in sheets, revealing raw, weeping wood beneath. The sap that drips "
            "from the wounds hisses when it strikes the ground, leaving smoking "
            "craters in the soil.|n",
            "|GThe trail ends at the mouth of a vault carved into the toxic earth, "
            "its walls slick with caustic slime. The skeletons of failed hunters "
            "lie half-dissolved in the sludge, their armor still softly hissing "
            "as it corrodes.|n",
        ],
        "north",
        "south",
    ),

    # 26 — The Scorched Desert Path → Phoenix (Lvl 34)
    (
        "dng_scorched_desert",
        "The Scorched Desert Path",
        "good",
        5,
        "boss_phoenix",
        [
            "|yThe path begins at the edge of the great desert, where the sand is "
            "white-hot and the sun beats down mercilessly. A line of standing stones "
            "marks the route, each one carved with the image of a bird wreathed in "
            "flames.|n",
            "|yThe trail winds through dunes of golden sand that shift and whisper "
            "in the desert wind. The heat is intense, and the air shimmers with "
            "mirages of water and palm trees that vanish as you approach.|n",
            "|YThe path passes through a field of fused glass—the remnants of some "
            "ancient, cataclysmic fire that turned the sand to crystal. The glass "
            "is still warm to the touch, and the light refracts through it in "
            "dazzling patterns.|n",
            "|YThe trail approaches a pillar of fused desert glass that rises from "
            "the dunes like a frozen flame. Ash swirls in lazy thermals around the "
            "pillar, and the air pulses with waves of heat and shimmering light.|n",
            "|RThe path ends at the base of the glass pillar, where a nest woven "
            "from charred cedar boughs and molten gold filaments crowns the summit. "
            "The entire structure pulses with regenerative heat and blinding radiance.|n",
        ],
        "up",
        "down",
    ),

    # 27 — The Cursed Sands → Mummy King (Lvl 22)
    (
        "dng_cursed_sands",
        "The Cursed Sands",
        "good",
        5,
        "boss_mummy_king",
        [
            "|yThe path enters a region of the desert where the sand is dark as "
            "charcoal and the wind carries whispers in a language long dead. "
            "Half-buried obelisks jut from the dunes at odd angles, their surfaces "
            "etched with hieroglyphs.|n",
            "|yThe trail passes between two colossal statues of a jackal-headed god, "
            "their stone eyes seeming to follow your progress. The sand beneath them "
            "is littered with small, wrapped bundles that crumble to dust at the "
            "slightest touch.|n",
            "|YThe path descends into a depression where the sand has been swept "
            "away to reveal a stone causeway leading to an underground entrance. "
            "The walls of the causeway are covered in gold leaf and hieroglyphs "
            "telling tales of a deathless tyrant.|n",
            "|YThe causeway leads to a antechamber where canopic jars sealed with "
            "wax and ancient sigils line the walls. Each jar is labeled with a "
            "different organ and a different curse, and the air is thick with the "
            "scent of myrrh and decay.|n",
            "|YThe antechamber ends at a corridor of black basalt that slopes "
            "downward into the earth. Hieroglyphs etched in tarnished gold leaf "
            "cover every inch of the walls, and the temperature drops sharply "
            "with each step.|n",
        ],
        "down",
        "up",
    ),

    # 28 — The Dread Spire Approach → Arch-Mage (Lvl 44)
    (
        "dng_dread_spire_approach",
        "The Dread Spire Approach",
        "good",
        5,
        "boss_arch_mage",
        [
            "|MThe approach begins at a twisted iron gate set into the base of a "
            "towering spire of black stone. Arcane symbols flare along the gate's "
            "bars as you approach, then fade, allowing you to pass.|n",
            "|MThe spiral staircase inside the spire is lit by floating orbs of "
            "magelight that drift lazily through the air, changing color with each "
            "passing moment. The stairs are worn smooth by centuries of arcane "
            "footsteps.|n",
            "|MThe staircase passes through a library where bookshelves stretch "
            "upward into darkness, their contents glowing faintly with stored "
            "magical energy. Floating grimoires drift between the shelves, their "
            "pages turning in silent, self-directed study.|n",
            "|MThe stairs continue upward through a chamber where the walls are "
            "covered in arcane circles that spiral and overlap in dizzying patterns. "
            "Each circle hums at a different frequency, and the combined resonance "
            "makes your teeth ache.|n",
            "|MThe staircase ends at a pair of doors that are not made of wood or "
            "metal but of pure, solidified magical energy. Arcane circles spiral "
            "across their surface, and they part silently as you approach, revealing "
            "the dread spire's highest chamber.|n",
        ],
        "up",
        "down",
    ),

    # 29 — The Lost Temple Depths → Kraken (Lvl 46)
    (
        "dng_lost_temple_depths",
        "The Lost Temple Depths",
        "good",
        5,
        "boss_kraken",
        [
            "|BThe temple entrance is a crumbling archway half-submerged in the "
            "coastal surf, its stones worn smooth by centuries of waves. Barnacles "
            "encrust every surface, and the smell of the deep ocean wafts from "
            "within.|n",
            "|bThe corridor slopes downward, its walls slick with seawater and "
            "dotted with sea anemones that glow with a faint bioluminescence. The "
            "sound of the surf fades, replaced by the deep, resonant silence of "
            "the ocean depths.|n",
            "|BThe passage opens into a chamber where the walls are carved with "
            "reliefs of tentacled sea creatures and ancient mariners making offerings "
            "at a drowned altar. The floor is ankle-deep in seawater that rises and "
            "falls with the distant tide.|n",
            "|bThe temple continues deeper, its halls half-flooded with seawater "
            "that grows deeper with each step. The walls here are encrusted with "
            "coral formations that have grown into the shapes of grasping hands "
            "and coiled tentacles.|n",
            "|BThe passage ends at a grand archway carved with the image of a "
            "massive kraken, its tentacles wrapping around a sinking ship. Beyond "
            "the arch, seawater laps at the steps of a drowned temple, and something "
            "vast stirs in the depths.|n",
        ],
        "down",
        "up",
    ),

    # 30 — The Void Walk → World-Eater (Lvl 45)
    (
        "dng_void_walk",
        "The Void Walk",
        "good",
        5,
        "boss_world_eater",
        [
            "|xThe entrance is a perfect circle of absolute darkness cut into the "
            "cliff face, its edges unnaturally smooth and cold to the touch. The "
            "air around it is still and silent, as if the world itself is holding "
            "its breath.|n",
            "|xThe passage is a corridor of black stone that seems to absorb all "
            "light and sound. Your footsteps make no noise, and your torchlight "
            "extends barely a foot in front of you before being swallowed by the "
            "darkness.|n",
            "|mThe corridor opens into a chamber where the walls are lined with "
            "shelves holding small, dark spheres that pulse with a faint, dying "
            "light—the frozen remnants of consumed stars. The air is heavy with "
            "the weight of eons.|n",
            "|mThe passage continues through a region where gravity seems to shift "
            "and warp, the floor becoming the wall and the ceiling becoming the "
            "floor in dizzying succession. The only constant is the pull toward "
            "the chamber at the center.|n",
            "|xThe passage ends at the threshold of a chamber dominated by a perfect "
            "sphere of absolute nothingness. Its event horizon is ringed with the "
            "frozen light of consumed stars, and the stone floor around it has been "
            "worn smooth by eons of slow, inevitable approach.|n",
        ],
        "north",
        "south",
    ),
]


# ---------------------------------------------------------------------------
# Public builder function
# ---------------------------------------------------------------------------

def build_dungeon_expansions():
    """
    Create 30 multi-room dungeon expansion chains (15 evil, 15 good) that
    connect regional realm endpoints to the 30 boss lairs.

    Each dungeon chain:
      - Creates 5–10 rooms with dynamic, depth-aware descriptions
      - Links rooms with bidirectional exits (north/south, east/west, up/down)
      - Tags the final room to connect to the corresponding boss lair
      - Tags the first room with the zone_anchor for regional attachment

    Returns:
        dict: {dungeon_id: [room_objects]} mapping each dungeon to its room list.
    """
    expansions = {}

    for (
        dungeon_id,
        dungeon_name,
        faction,
        room_count,
        boss_id,
        flavor_lines,
        exit_forward,
        exit_back,
    ) in DUNGEON_EXPANSIONS:

        faction_color = "|r" if faction == "evil" else "|Y"
        rooms = []

        for i in range(1, room_count + 1):
            # Build room title and description
            title = (
                f"{faction_color}{dungeon_name} — Chamber {i}/{room_count}|n"
            )
            desc = _depth_desc(i, room_count, dungeon_name, faction_color, flavor_lines)

            room = create_object("typeclasses.rooms.Room", key=title)
            room.db.desc = desc
            room.db.is_dungeon_room = True

            # Tagging
            room.tags.add("dungeon_expansion", category="room_type")
            room.tags.add(dungeon_id, category="dungeon_id")
            room.tags.add(faction, category="faction")
            room.tags.add(str(i), category="dungeon_depth")

            rooms.append(room)

            # Link sequential rooms
            if i > 1:
                _link_rooms(rooms[i - 2], rooms[i - 1], exit_forward, exit_back)

        # Tag the final room with the boss lair it connects to
        rooms[-1].tags.add(boss_id, category="boss_entrance")

        # Tag the first room as the dungeon entry point (for regional attachment)
        rooms[0].tags.add("dungeon_entrance", category="room_type")
        rooms[0].tags.add(dungeon_id, category="entrance_for")

        expansions[dungeon_id] = rooms

    return expansions