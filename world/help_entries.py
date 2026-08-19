"""
File-based help entries for 'rop' (Rites of Passage).

These complement command-based help. Control where Evennia reads these
modules with `settings.FILE_HELP_ENTRY_MODULES`.

Each dict is on the form:

    {'key': <str>,
     'text': <str>}``     # the actual help text. Can contain # subtopic sections
     'category': <str>,   # optional, otherwise settings.DEFAULT_HELP_CATEGORY
     'aliases': <list>,   # optional
     'locks': <str>       # optional

Most entries use the "General" category so they appear in the default
help index shown to players.
"""

HELP_ENTRIES = HELP_ENTRY_DICTS = [
    {
        "key": "races",
        "aliases": ["race"],
        "category": "General",
        "text": """
            |cRACES OF THE REALM|n

            The realm is divided by a war between |gGood|n and |rEvil|n.
            Each of the 16 races below has unique starting stats, a passive
            ability, and a set of permitted classes.

            |gGOOD / NEUTRAL RACES|n
            |wHuman|n          Balanced all-rounders. Passive: +5% XP gain.
            |wHigh Elf|n       Arcane masters. Passive: +15% Max Mana.
            |wWood Elf|n       Swift archers. Passive: +10% Dodge Rate.
            |wMountain Dwarf|n  Sturdy defenders. Passive: +5 Armor.
            |wStout Halfling|n  Nimble and lucky. Passive: +5% Crit Chance.
            |wGnome|n          Brilliant inventors. Passive: +10 Magic Resist.
            |wCentaur|n        Plains guardians. Passive: +20% Movement Speed.
            |wPixie|n          Tiny flyers. Passive: +15% Evasion.

            |rEVIL RACES|n
            |wOrc|n            Brutal warriors. Passive: +10% Melee Damage.
            |wDark Elf|n       Shadow assassins. Passive: +15% Stealth.
            |wUndead|n         Deathless horrors. Passive: Poison/Bleed immunity.
            |wGoblin|n         Cunning scavengers. Passive: +15% Gold Drops.
            |wMinotaur|n       Massive bruisers. Passive: +10% Stun on Hit.
            |wLizardfolk|n     Scaled hunters. Passive: +4 Natural Armor.
            |wOgre|n           Giant brutes. Passive: +20% Max Health.
            |wDemonkin|n       Fiendish blooded. Passive: +15 Fire/Dark Resist.

            Use |yhelp matrix|n to see which classes each race may choose.
            Use |yhelp classes|n to learn about each class.
        """,
    },
    {
        "key": "classes",
        "aliases": ["class"],
        "category": "General",
        "text": """
            |cCLASSES OF THE REALM|n

            There are 10 adventuring classes. Each class determines your
            hit points per level, mana per level, spells, skills, and
            equipment proficiencies.

            |wWarrior|n      Heavy melee juggernaut. Primary: STR.
            |wPaladin|n      Holy frontliner with healing and defense.
            |wCleric|n       Divine healer and buffer. Primary: WIS.
            |wMage|n         Master of destructive magic. Primary: INT.
            |wRogue|n        Stealthy damage dealer. Primary: DEX.
            |wWarlock|n      Dark caster, damage over time. Primary: INT.
            |wDruid|n        Nature caster and shapeshifter. Primary: WIS.
            |wRanger|n       Ranged marksman. Primary: DEX.
            |wMonk|n         Unarmed martial artist. Primary: DEX.
            |wNecromancer|n  Commander of the dead. Primary: INT.

            Spellcasting classes (those that can cast spells) are: Paladin,
            Cleric, Mage, Warlock, Druid, Ranger, and Necromancer.
            Warriors, Rogues, and Monks have no spells — instead they rely
            on physical combat skills.

            Use |yhelp matrix|n to see which races may become each class.
        """,
    },
    {
        "key": "matrix",
        "aliases": ["raceclass", "classrace"],
        "category": "General",
        "text": """
            |cRACE / CLASS COMPATIBILITY MATRIX|n

            Not every race can become every class. Choose carefully during
            character creation.

            |wHuman|n        Warrior, Paladin, Cleric, Mage, Rogue, Warlock, Druid, Ranger, Monk, Necromancer
            |wHigh Elf|n     Paladin, Cleric, Mage, Druid, Ranger, Monk
            |wWood Elf|n     Cleric, Mage, Rogue, Druid, Ranger, Monk
            |wMountain Dwarf|n Warrior, Paladin, Cleric, Rogue
            |wStout Halfling|n Warrior, Rogue, Ranger, Monk
            |wGnome|n        Cleric, Mage, Rogue, Warlock, Druid
            |wCentaur|n      Warrior, Paladin, Druid, Ranger
            |wPixie|n        Mage, Rogue, Druid, Monk
            |wOrc|n          Warrior, Rogue, Warlock, Necromancer
            |wDark Elf|n     Warrior, Mage, Rogue, Warlock, Necromancer
            |wUndead|n       Warrior, Warlock, Necromancer
            |wGoblin|n       Warrior, Rogue, Warlock
            |wMinotaur|n     Warrior, Warlock
            |wLizardfolk|n   Warrior, Rogue, Druid
            |wOgre|n         Warrior
            |wDemonkin|n     Warrior, Mage, Warlock, Necromancer

            Some races also have spell-level restrictions. For example, Orcs,
            Ogres, and Minotaurs cannot learn spells at all, while Pixies
            cannot equip heavy armor.
        """,
    },
    {
        "key": "combat",
        "category": "General",
        "text": """
            |cCOMBAT|n

            Combat uses a tick-based auto-attack system. When you
            |ykill <target>|n, you and your target enter combat and trade
            blows every few seconds until one of you flees or dies.

            |wBasic Commands|n
              |ykill <target>|n  - attack a mob or player
              |yflee|n           - attempt to escape combat
              |ystop|n           - stop fighting

            |wHit & Damage|n
            Hit chance is based on your DEX versus the target's DEX.
            Damage is based on your weapon and STR, reduced by the
            defender's armor and CON. Critical hits deal 150% damage.

            |wDamage Types|n
            Physical (slashing, piercing, bludgeoning) is mitigated by
            armor. Magic (fire, cold, lightning, holy, shadow, arcane,
            poison) is mitigated by magic resistance instead.

            |wCombat Skills|n
            Some classes can use physical skills: |ykick|n, |ybash|n,
            |ybackstab|n, and |ydisarm|n. These cost stamina and trigger
            a cooldown. Train them at a guildmaster.

            |wFleeing|n
            Flee chance is based on your level and DEX versus the target.
            There is a brief delay before a flee resolves. Failing to flee
            keeps you in combat.

            See also: |yhelp pvp|n, |yhelp spells|n.
        """,
    },
    {
        "key": "spells",
        "category": "General",
        "text": """
            |cSPELLS & MAGIC|n

            Spellcasting classes (Paladin, Cleric, Mage, Warlock, Druid,
            Ranger, Necromancer) can learn and cast spells. Warriors,
            Rogues, and Monks have no spellcasting ability.

            |wCommands|n
              |yspells|n       - list spells you know (also |yspellbook|n)
              |ycast <spell>|n - cast a spell

            |wSpell Schools|n
              |yEvocation|n    - direct damage (fireball, lightning bolt)
              |yRestoration|n  - healing and curing
              |yAbjuration|n   - shields and wards
              |yEnfeebling|n   - debuffs, drains, and curses

            |wCasting|n
            Spells cost mana and may have a cooldown. Casting uses your
            INT or WIS (whichever is higher). Targets may resist spells
            with a saving throw based on their WIS and magic resistance.

            Your class determines which spell schools you can access and
            up to what level. Paladins and Rangers have reduced spell
            level caps, while full casters can reach the highest tiers.

            See also: |yhelp combat|n.
        """,
    },
    {
        "key": "pvp",
        "aliases": ["player killing", "pk"],
        "category": "General",
        "text": """
            |cPLAYER VS PLAYER (PvP)|n

            PvP in the realm is governed by the alignment and faction
            system.

            |wAlignment Factions|n
            Good and Evil are at war. Players of opposite factions may
            attack each other freely without any explicit toggle. Neutral
            players may need to enable PvP, and same-faction kills have
            serious consequences.

            |wPvP Toggle|n
              |ypvp|n           - check or toggle your own PvP flag
            Arena zones always allow PvP regardless of faction.

            |wWarpoints|n
            Killing an enemy-faction player awards warpoints, visible on
            the |ywarpoints|n leaderboard. Warpoints scale with the
            victim's level.

            |wOutlaw Status|n
            Killing a same-faction player or committing certain crimes
            marks you as an |rOUTLAW|n. Outlaws are attackable by anyone
            and show a red tag in look and who. Outlaw status expires
            after a short time.

            |wInfamy|n
            Same-faction kills accrue infamy rather than warpoints.

            See also: |yhelp factions|n.
        """,
    },
    {
        "key": "recovery",
        "category": "General",
        "text": """
            |cRECOVERY & POSITIONAL STATES|n

            Your character recovers HP, Mana, Movement (MV), and Stamina
            over time. Recovery pauses during combat.

            |wPositions|n
              |yrest|n       - sit and rest for faster HP/MV recovery
              |ymeditate|n   - recover mana quickly (casters only)
              |ysleep|n      - fastest recovery, but very vulnerable
              |ywake|n       - stand up (also |ystand|n)

            |wRecovery Rates (per tick)|n
              Standing:   5% HP,  5% Mana, 10% MV
              Resting:   15% HP, 10% Mana, 20% MV
              Meditating: 5% HP, 25% Mana, 10% MV
              Sleeping:  30% HP, 30% Mana, 50% MV

            |wStamina|n
            Check stamina with |ystamina|n. Combat skills consume stamina
            and it regenerates over time.

            Sleeping characters are |rVULNERABLE|n — attacks against them
            deal extra damage.
        """,
    },
    {
        "key": "economy",
        "category": "General",
        "text": """
            |cECONOMY & CURRENCY|n

            The realm uses a gold-based economy.

            |wCurrency|n
              100 copper = 10 silver = 1 gold
            You can use shorthand like |y10g|n, |y50s|n, or |y100c|n in
            bank transactions.

            |wShops|n
              |ylist|n          - see what a shopkeeper sells
              |ybuy <item>|n    - buy an item
              |ysell <item>|n   - sell an item
              |yappraise <item>|n - check an item's value
            Shopkeepers give better prices to same-faction characters.

            |wBanks|n
              |ydeposit <amount>|n - store gold
              |ywithdraw <amount>|n - take gold out
              |ybalance|n         - check your account

            |wRepair|n
            Equipment durability degrades in combat. Find a repair NPC
            and use |yrepair <item>|n to restore it for a gold cost.

            |wDropping & Taking Gold|n
              |ydropcoins <amount>|n - drop gold on the ground
              |ytakecoins <amount>|n - pick up gold from the room
        """,
    },
    {
        "key": "movement",
        "category": "General",
        "text": """
            |cMOVEMENT|n

            The realm supports 10 directions of travel.

            |wDirections|n
              |ynorth|n (n), |ysouth|n (s), |yeast|n (e), |ywest|n (w)
              |ynortheast|n (ne), |ynorthwest|n (nw),
              |ysoutheast|n (se), |ysouthwest|n (sw)
              |yup|n (u), |ydown|n (d)

            |wCommands|n
              |yn<direction>|n      - move one room (costs 1 MV)
              |yrun <direction>|n   - run multiple rooms in a line
              |yexits|n             - list visible exits
              |yscan|n              - survey adjacent rooms

            |wMovement Points (MV)|n
            Moving costs MV which regenerates over time and by resting.

            |wEncumbrance|n
            Carrying too much weight slows you and increases movement
            costs. Your carry capacity scales with STR.

            |wDoors|n
            Some exits are doors. Use |yopen <direction>|n,
            |yclose <direction>|n, |ylock <direction>|n and
            |yunlock <direction>|n to interact with them.

            |wBrief Mode|n
              |ybrief|n   - show only titles for visited rooms
              |yverbose|n - always show full descriptions
        """,
    },
    {
        "key": "factions",
        "aliases": ["alignment"],
        "category": "General",
        "text": """
            |cFACTIONS & ALIGNMENT|n

            The realm is locked in an eternal war between |gGood|n and
            |rEvil|n.

            |wGood Faction|n
            The Aethelgard Alliance — headquartered in the radiant city of
            Aethelgard. Good-aligned races are Humans, Elves, Dwarves,
            Halflings, Gnomes, Centaurs, and Pixies.

            |wEvil Faction|n
            The Gorgoroth Horde — headquartered in the volcanic catacombs
            of Gorgoroth. Evil-aligned races are Orcs, Dark Elves, Undead,
            Goblins, Minotaurs, Lizardfolk, Ogres, and Demonkin.

            |wAlignment Effects|n
              - Your alignment determines your starting city.
              - Some rooms restrict entry by alignment.
              - City guards attack opposite-faction intruders.
              - Shopkeepers offer better prices to same-faction players.
              - Cross-faction PvP is always enabled.
              - Use |yrecall|n (level 30+) to return to your faction home.

            |wAlignment Points|n
            Killing opposite-faction mobs or players shifts your alignment
            points. Good is 750+, Neutral is -749 to 749, Evil is -750 or
            lower.

            See also: |yhelp pvp|n.
        """,
    },
    {
        "key": "guildmasters",
        "aliases": ["guildmaster", "practice", "training"],
        "category": "General",
        "text": """
            |cGUILDMASTERS & THE PRACTICE SYSTEM|n

            Guildmasters are NPCs that teach you new spells and combat
            skills in exchange for practice points.

            |wPractice Points|n
            You earn practice points every time you level up. The amount
            depends on your class (casters earn more).

            |wCommands|n
              |ytrain|n              - list what a guildmaster can teach
              |ylearn <spell/skill>|n - learn a specific ability
              |ypractice|n           - show your practice points and ranks

            |wTraining Rules|n
            - Only abilities valid for your race/class are offered.
            - You must meet the ability's level requirement.
            - Training a skill increases its rank.
            - Trained abilities are permanently unlocked.

            Find guildmasters in the major cities (Aethelgard for Good,
            Gorgoroth for Evil).
        """,
    },
    {
        "key": "quests",
        "category": "General",
        "text": """
            |cQUESTS|n

            Quest-giving NPCs are scattered throughout the realm. Approach
            an NPC and use the |yquest|n command to interact.

            |wCommands|n
              |yquest|n            - list available quests
              |yquest <id>|n       - accept or turn in a quest
              |yquest abandon <id>|n - abandon an active quest

            |wQuest Types|n
              |yKill|n    - defeat a number of specific mobs
              |yFetch|n   - collect and deliver items
              |yTalk|n    - speak with a specific NPC

            |wRewards|n
            Quests reward XP, gold, items, and faction alignment.

            |wProgress Tracking|n
            Kill and fetch quests progress automatically as you play.
            When an objective is complete, return to the quest giver to
            collect your reward.

            Check active quests at any time with |yquest|n.
        """,
    },
    {
        "key": "clans",
        "aliases": ["clan"],
        "category": "General",
        "text": """
            |cCLANS|n

            Clans are permanent player organizations aligned to a faction.

            |wCommands|n
              |yclan|n                   - show clan info
              |yclan list|n              - list all clans
              |yclan join <clan>|n       - join a clan
              |yclan leave|n             - leave your clan
              |yclan talk <message>|n    - chat with clanmates

            |wClan Tags|n
            Your clan tag appears in the |ywho|n list, colour-coded by the
            clan's faction (green for Good, red for Evil).
        """,
    },
    {
        "key": "groups",
        "aliases": ["group", "party"],
        "category": "General",
        "text": """
            |cGROUPS|n

            Group up with other adventurers to share XP and tackle tough
            content.

            |wCommands|n
              |ygroup|n                      - show group status
              |ygroup invite <player>|n      - invite someone to your group
              |ygroup accept|n               - accept a pending invite
              |ygroup leave|n                - leave your group
              |ygroup kick <player>|n        - remove a member (leader only)
              |ygroup talk <message>|n       - chat with your group

            |wGroup Benefits|n
            - Shared XP from kills
            - Shared group chat channel
            - Shared PvP flag state

            Group up with others using the |ywho|n command to find them.
        """,
    },
    {
        "key": "newbie",
        "aliases": ["new player", "starter", "beginner", "tutorial"],
        "category": "General",
        "text": """
            |cNEW PLAYER GUIDE|n

            Welcome to |cRites of Passage|n! This guide covers your first
            30 minutes in the realm.

            |w1. Choose Your Race & Class|n
            At character creation you must choose a faction (Good or Evil),
            then a race and class. Not all races can be all classes — see
            |yhelp matrix|n.

            |w2. Basic Commands|n
              |ylook|n           - look around (also |yl|n)
              |yn/s/e/w|n        - move in a direction
              |yi|n / |yinv|n    - check your inventory
              |yeq|n             - check your equipment
              |yscore|n          - view your stats

            |w3. Getting Equipped|n
            Every new character receives a starting package of gear.
            You can buy more from the shopkeepers in your starting city
            with |ylist|n and |ybuy <item>|n.

            |w4. Your First Fight|n
            Use |yconsider <target>|n to judge an enemy's difficulty.
            Start with easy targets! Attack with |ykill <target>|n and
            flee with |yflee|n if things go badly.

            |w5. Recovery|n
            After a fight, type |yrest|n to recover HP faster. Casters
            can |ymeditate|n to regain mana.

            |w6. Your First Quest|n
            Speak to NPCs in town. Use |yquest|n to see available quests
            and accept them. The tutorial NPC in the starting room can
            give you your first quest: defeating a few goblin scouts.

            |w7. Getting Around|n
            Use |yscan|n to survey nearby rooms, and |yrecal|n (level 30+)
            to return to your faction home. See |yhelp movement|n for all
            movement options.

            |wHelpful Tips|n
            - Toggle the status bar with |yprompt|n
            - Read the rules with |yrules|n
            - Chat with others on |ygossip|n
            - See who's online with |ywho|n
            - A full command list is at |yhelp|n
        """,
    },
    {
        "key": "evennia",
        "aliases": ["ev"],
        "category": "General",
        "locks": "read:perm(Developer)",
        "text": """
            Evennia is a MU-game server and framework written in Python. You can read more
            on https://www.evennia.com.

            # subtopics

            ## Installation

            You'll find installation instructions on https://www.evennia.com.

            ## Community

            There are many ways to get help and communicate with other devs!

            ### Discussions

            The Discussions forum is found at https://github.com/evennia/evennia/discussions.

            ### Discord

            There is also a discord channel for chatting - connect using the
            following link: https://discord.gg/AJJpcRUhtF
        """,
    },
]