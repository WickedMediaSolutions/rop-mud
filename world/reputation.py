"""
Reputation System for 'rop' — Faction Standing & Vendor Discounts

Provides:
  - ReputationSystem class
  - Per-faction reputation tracking (clamped [-5000, 5000])
  - Standing tiers: Hated → Hostile → Unfriendly → Neutral → Friendly → Honored → Revered → Exalted
  - Vendor discount scaling based on reputation tier
  - Reputation gain/loss constants for various actions
  - Display formatting for character sheet

Usage:
    from world.reputation import ReputationSystem

    ReputationSystem.initialize(character)
    ReputationSystem.adjust_reputation(character, "aethelgard", 100)
    standing = ReputationSystem.get_standing(character, "aethelgard")
    discount = ReputationSystem.get_vendor_discount(character, "aethelgard")
"""

from typing import Any, Dict, List, Optional, Tuple

from evennia.objects.objects import DefaultCharacter


class ReputationSystem:
    """Centralized faction reputation tracking system."""

    # Faction keys
    FACTIONS = [
        "aethelgard",     # Good-aligned city
        "gorgoroth",      # Evil-aligned city
        "merchants_guild", # Neutral merchant faction
        "arcane_order",   # Magic users guild
        "wildlands",      # Druid/ranger faction
        "underworld",     # Thieves/assassins guild
    ]

    # Reputation value range
    MIN_REPUTATION = -5000
    MAX_REPUTATION = 5000

    # Standing tier thresholds
    # Each tier has a minimum reputation value
    STANDING_TIERS = {
        "Exalted": 4000,
        "Revered": 2500,
        "Honored": 1200,
        "Friendly": 500,
        "Neutral": -499,
        "Unfriendly": -1200,
        "Hostile": -2500,
        "Hated": -5000,
    }

    # Vendor discount multipliers per standing tier
    # Values < 1.0 are discounts, > 1.0 are markups
    VENDOR_DISCOUNTS = {
        "Exalted": 0.65,     # 35% off
        "Revered": 0.75,     # 25% off
        "Honored": 0.85,     # 15% off
        "Friendly": 0.92,    # 8% off
        "Neutral": 1.00,     # Normal price
        "Unfriendly": 1.10,  # 10% markup
        "Hostile": 1.30,     # 30% markup
        "Hated": 1.50,       # 50% markup
    }

    # Reputation gain/loss constants
    REP_KILL_MOB = 5             # Killing a mob in that faction's territory
    REP_KILL_BOSS = 50           # Killing a boss
    REP_COMPLETE_QUEST = 100     # Completing a quest for the faction
    REP_KILL_OPPOSING_PLAYER = 25  # Killing an opposing faction player
    REP_TURN_IN_QUEST_ITEM = 25  # Turning in quest items
    REP_ATTACK_FRIENDLY_NPC = -50  # Attacking a friendly NPC
    REP_KILL_FRIENDLY_NPC = -200   # Killing a friendly NPC
    REP_STEAL_FROM_SHOP = -100    # Stealing from a shop

    @staticmethod
    def initialize(character) -> None:
        """
        Initialize the reputation dict on a character if not already present.
        All factions start at 0 (Neutral).
        """
        if not hasattr(character, "attributes"):
            return
        if not character.attributes.has("reputation"):
            rep = {faction: 0 for faction in ReputationSystem.FACTIONS}
            character.attributes.add("reputation", rep)

    @staticmethod
    def get_reputation(character, faction: str) -> int:
        """
        Get the raw reputation value for a specific faction.

        Args:
            character: The character object.
            faction: The faction key (e.g. "aethelgard").

        Returns:
            int: Reputation value, clamped to [MIN_REPUTATION, MAX_REPUTATION].
        """
        ReputationSystem.initialize(character)
        rep = character.attributes.get("reputation", default={})
        if not rep or not hasattr(rep, "get"):
            return 0
        return rep.get(faction, 0)

    @staticmethod
    def adjust_reputation(character, faction: str, amount: int) -> int:
        """
        Adjust reputation for a faction by the given amount.
        Clamped to [MIN_REPUTATION, MAX_REPUTATION].

        Args:
            character: The character object.
            faction: The faction key.
            amount: Positive or negative change.

        Returns:
            int: New reputation value.
        """
        ReputationSystem.initialize(character)
        rep = character.attributes.get("reputation", default={})
        if not rep or not hasattr(rep, "get"):
            rep = {faction: 0 for faction in ReputationSystem.FACTIONS}

        current = rep.get(faction, 0)
        new_val = max(ReputationSystem.MIN_REPUTATION,
                      min(ReputationSystem.MAX_REPUTATION, current + amount))
        rep[faction] = new_val
        character.attributes.add("reputation", rep)
        return new_val

    @staticmethod
    def get_standing(character, faction: str) -> str:
        """
        Get the standing tier name for a faction.

        Args:
            character: The character object.
            faction: The faction key.

        Returns:
            str: Standing tier name (e.g. "Friendly", "Hostile").
        """
        rep = ReputationSystem.get_reputation(character, faction)
        # Tiers are checked in descending order of threshold
        for tier_name, threshold in sorted(
            ReputationSystem.STANDING_TIERS.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            if rep >= threshold:
                return tier_name

        return "Hated"

    @staticmethod
    def get_vendor_discount(character, faction: str) -> float:
        """
        Get the vendor price multiplier for a faction based on standing.

        Args:
            character: The character object.
            faction: The faction key.

        Returns:
            float: Price multiplier (1.0 = normal, < 1.0 = discount).
        """
        standing = ReputationSystem.get_standing(character, faction)
        return ReputationSystem.VENDOR_DISCOUNTS.get(standing, 1.0)

    @staticmethod
    def format_reputation(character) -> str:
        """
        Return a formatted string showing all faction standings.

        Args:
            character: The character object.

        Returns:
            str: Multi-line formatted reputation display.
        """
        ReputationSystem.initialize(character)
        lines = ["|w=== Reputation ===|n"]

        faction_display = {
            "aethelgard": "|gAethelgard|n (Good)",
            "gorgoroth": "|rGorgoroth|n (Evil)",
            "merchants_guild": "|yMerchants Guild|n",
            "arcane_order": "|cArcane Order|n",
            "wildlands": "|gWildlands|n",
            "underworld": "|mUnderworld|n",
        }

        for faction in ReputationSystem.FACTIONS:
            rep = ReputationSystem.get_reputation(character, faction)
            standing = ReputationSystem.get_standing(character, faction)
            discount = ReputationSystem.get_vendor_discount(character, faction)

            # Color the standing
            if standing in ("Exalted", "Revered", "Honored"):
                standing_color = "|g"
            elif standing == "Friendly":
                standing_color = "|c"
            elif standing == "Neutral":
                standing_color = "|w"
            elif standing == "Unfriendly":
                standing_color = "|y"
            else:
                standing_color = "|r"

            display_name = faction_display.get(faction, faction)
            discount_pct = int((1.0 - discount) * 100) if discount < 1.0 else int((discount - 1.0) * 100)
            discount_str = f"|g-{discount_pct}%|n" if discount < 1.0 else f"|r+{discount_pct}%|n" if discount > 1.0 else "|wnormal|n"

            lines.append(
                f"  {display_name:<24} {standing_color}{standing:<12}|n "
                f"({rep:>+5})  {discount_str}"
            )

        return "\n".join(lines)

    @staticmethod
    def get_opposing_faction(character) -> Optional[str]:
        """
        Get the character's opposing faction based on alignment.

        Good-aligned → gorgoroth is opposing
        Evil-aligned → aethelgard is opposing
        Neutral → None

        Returns:
            Optional[str]: The opposing faction key, or None.
        """
        alignment = character.attributes.get("alignment", default="Neutral") if hasattr(character, "attributes") else "Neutral"
        if alignment == "Good":
            return "gorgoroth"
        elif alignment == "Evil":
            return "aethelgard"
        return None

    @staticmethod
    def get_home_faction(character) -> str:
        """
        Get the character's home faction based on alignment.

        Returns:
            str: The home faction key.
        """
        alignment = character.attributes.get("alignment", default="Neutral") if hasattr(character, "attributes") else "Neutral"
        if alignment == "Good":
            return "aethelgard"
        elif alignment == "Evil":
            return "gorgoroth"
        return "merchants_guild"


# ---------------------------------------------------------------------------
# Player Command
# ---------------------------------------------------------------------------

from commands.command import Command


# ---------------------------------------------------------------------------
# Reputation Vendor NPC
# ---------------------------------------------------------------------------

# Faction-specific gear sold by reputation vendors.
# Each tier requires a minimum standing to purchase.
REPUTATION_VENDOR_GEAR: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "aethelgard": {
        "Friendly": [
            {"key": "Aethelgard Recruit's Blade", "slot": "main_hand", "damage": 12,
             "armor_class": 0, "required_level": 10, "price": 50,
             "desc": "A steel longsword etched with the Aethelgard sunburst."},
            {"key": "Suncrest Shield", "slot": "off_hand", "damage": 0,
             "armor_class": 8, "required_level": 10, "price": 60,
             "desc": "A kite shield bearing the radiant crest of Aethelgard."},
            {"key": "Acolyte's Robe", "slot": "torso", "damage": 0,
             "armor_class": 8, "required_level": 10, "price": 45,
             "desc": "White robes blessed by the clerics of Aethelgard."},
        ],
        "Honored": [
            {"key": "Knight-Captain's Longsword", "slot": "main_hand", "damage": 18,
             "armor_class": 0, "required_level": 20, "price": 150,
             "desc": "A masterwork blade awarded to Aethelgard's finest officers."},
            {"key": "Bulwark of the Sanctum", "slot": "off_hand", "damage": 0,
             "armor_class": 14, "required_level": 20, "price": 180,
             "desc": "A towering shield enchanted with protective wards."},
            {"key": "Paladin's Plate", "slot": "torso", "damage": 0,
             "armor_class": 16, "required_level": 20, "price": 200,
             "desc": "Gleaming plate armour forged in the Sanctum's holy fires."},
            {"key": "Ring of the Faithful", "slot": "ring1", "damage": 0,
             "armor_class": 3, "required_level": 20, "price": 120,
             "desc": "A golden ring that pulses with gentle warmth."},
        ],
        "Revered": [
            {"key": "Dawnbringer", "slot": "main_hand", "damage": 26,
             "armor_class": 0, "required_level": 35, "price": 400,
             "desc": "A legendary sword that blazes with the light of dawn."},
            {"key": "Aegis of Aethelgard", "slot": "off_hand", "damage": 0,
             "armor_class": 20, "required_level": 35, "price": 450,
             "desc": "The sacred shield of Aethelgard's champion."},
            {"key": "Sunforged Plate", "slot": "torso", "damage": 0,
             "armor_class": 22, "required_level": 35, "price": 500,
             "desc": "Armour forged in the heart of a dying star."},
            {"key": "Amulet of Divine Favour", "slot": "neck", "damage": 0,
             "armor_class": 5, "required_level": 35, "price": 300,
             "desc": "An amulet that glows with celestial radiance."},
        ],
        "Exalted": [
            {"key": "Sunburst Blade", "slot": "main_hand", "damage": 35,
             "armor_class": 0, "required_level": 50, "price": 1000,
             "desc": "The fabled blade of the first Paladin-King of Aethelgard."},
            {"key": "Celestial Aegis", "slot": "off_hand", "damage": 0,
             "armor_class": 28, "required_level": 50, "price": 1100,
             "desc": "A shield forged from crystallized starlight."},
            {"key": "Raiment of the Exalted", "slot": "torso", "damage": 0,
             "armor_class": 30, "required_level": 50, "price": 1200,
             "desc": "Armour worn only by those who have transcended mortality."},
            {"key": "Crown of the Righteous", "slot": "head", "damage": 0,
             "armor_class": 12, "required_level": 50, "price": 800,
             "desc": "A golden crown that marks its wearer as Aethelgard's champion."},
        ],
    },
    "gorgoroth": {
        "Friendly": [
            {"key": "Dark Recruit's Cleaver", "slot": "main_hand", "damage": 12,
             "armor_class": 0, "required_level": 10, "price": 50,
             "desc": "A jagged cleaver favoured by Gorgoroth footsoldiers."},
            {"key": "Spiked Bulwark", "slot": "off_hand", "damage": 0,
             "armor_class": 8, "required_level": 10, "price": 60,
             "desc": "A brutal shield bristling with iron spikes."},
            {"key": "Dark Acolyte's Vestments", "slot": "torso", "damage": 0,
             "armor_class": 8, "required_level": 10, "price": 45,
             "desc": "Black robes woven with threads of shadow-essence."},
        ],
        "Honored": [
            {"key": "Dread Captain's Axe", "slot": "main_hand", "damage": 18,
             "armor_class": 0, "required_level": 20, "price": 150,
             "desc": "A massive war-axe wielded by Gorgoroth's dread captains."},
            {"key": "Wall of Torment", "slot": "off_hand", "damage": 0,
             "armor_class": 14, "required_level": 20, "price": 180,
             "desc": "A shield that screams with the voices of the damned."},
            {"key": "Hellforged Plate", "slot": "torso", "damage": 0,
             "armor_class": 16, "required_level": 20, "price": 200,
             "desc": "Black plate armour quenched in the blood of demons."},
            {"key": "Ring of Dark Whispers", "slot": "ring1", "damage": 0,
             "armor_class": 3, "required_level": 20, "price": 120,
             "desc": "A ring that murmurs secrets of the abyss."},
        ],
        "Revered": [
            {"key": "Soulrender", "slot": "main_hand", "damage": 26,
             "armor_class": 0, "required_level": 35, "price": 400,
             "desc": "A blade that drinks the souls of its victims."},
            {"key": "Bastion of Despair", "slot": "off_hand", "damage": 0,
             "armor_class": 20, "required_level": 35, "price": 450,
             "desc": "A shield forged from the despair of a thousand fallen heroes."},
            {"key": "Abyssal Carapace", "slot": "torso", "damage": 0,
             "armor_class": 22, "required_level": 35, "price": 500,
             "desc": "Living armour grown in the deepest pits of the abyss."},
            {"key": "Pendant of the Void", "slot": "neck", "damage": 0,
             "armor_class": 5, "required_level": 35, "price": 300,
             "desc": "A pendant that seems to swallow all light."},
        ],
        "Exalted": [
            {"key": "Doombringer", "slot": "main_hand", "damage": 35,
             "armor_class": 0, "required_level": 50, "price": 1000,
             "desc": "The legendary blade that ended the Age of Light."},
            {"key": "Shadowfortress", "slot": "off_hand", "damage": 0,
             "armor_class": 28, "required_level": 50, "price": 1100,
             "desc": "A shield woven from pure shadow-stuff."},
            {"key": "Harbinger's Mantle", "slot": "torso", "damage": 0,
             "armor_class": 30, "required_level": 50, "price": 1200,
             "desc": "Armour worn by the harbinger of the end times."},
            {"key": "Crown of the Damned", "slot": "head", "damage": 0,
             "armor_class": 12, "required_level": 50, "price": 800,
             "desc": "A crown of black iron that marks its wearer as Gorgoroth's champion."},
        ],
    },
    "merchants_guild": {
        "Friendly": [
            {"key": "Merchant's Lucky Coin", "slot": "ring1", "damage": 0,
             "armor_class": 2, "required_level": 5, "price": 80,
             "desc": "A well-worn coin said to bring fortune to its bearer."},
            {"key": "Trader's Cloak", "slot": "torso", "damage": 0,
             "armor_class": 6, "required_level": 5, "price": 60,
             "desc": "A practical cloak favoured by travelling merchants."},
        ],
        "Honored": [
            {"key": "Guildmaster's Signet", "slot": "ring1", "damage": 0,
             "armor_class": 4, "required_level": 15, "price": 200,
             "desc": "A signet ring marking its wearer as a trusted guild affiliate."},
            {"key": "Caravan Master's Coat", "slot": "torso", "damage": 0,
             "armor_class": 12, "required_level": 15, "price": 180,
             "desc": "A reinforced coat worn by caravan masters on dangerous routes."},
        ],
        "Revered": [
            {"key": "Coin-Lord's Purse", "slot": "ring1", "damage": 0,
             "armor_class": 6, "required_level": 30, "price": 500,
             "desc": "A magical purse that never empties of copper coins."},
            {"key": "Trade Prince's Vestments", "slot": "torso", "damage": 0,
             "armor_class": 18, "required_level": 30, "price": 450,
             "desc": "Opulent robes worn by the wealthiest trade princes."},
        ],
        "Exalted": [
            {"key": "Philosopher's Stone Ring", "slot": "ring1", "damage": 0,
             "armor_class": 8, "required_level": 45, "price": 1200,
             "desc": "A ring rumoured to turn base metals into gold."},
            {"key": "Robe of the Merchant King", "slot": "torso", "damage": 0,
             "armor_class": 24, "required_level": 45, "price": 1000,
             "desc": "Robes worn only by the legendary Merchant Kings of old."},
        ],
    },
    "arcane_order": {
        "Friendly": [
            {"key": "Apprentice's Staff", "slot": "main_hand", "damage": 8,
             "armor_class": 0, "required_level": 10, "price": 40,
             "desc": "A simple wooden staff imbued with minor arcane energy."},
            {"key": "Adept's Robes", "slot": "torso", "damage": 0,
             "armor_class": 6, "required_level": 10, "price": 50,
             "desc": "Robes woven with protective runes for novice mages."},
        ],
        "Honored": [
            {"key": "Staff of the Arcanist", "slot": "main_hand", "damage": 14,
             "armor_class": 0, "required_level": 20, "price": 180,
             "desc": "A staff crackling with stored arcane power."},
            {"key": "Robes of the Magus", "slot": "torso", "damage": 0,
             "armor_class": 12, "required_level": 20, "price": 200,
             "desc": "Robes that shimmer with protective enchantments."},
            {"key": "Circlet of Focus", "slot": "head", "damage": 0,
             "armor_class": 4, "required_level": 20, "price": 150,
             "desc": "A silver circlet that sharpens the wearer's concentration."},
        ],
        "Revered": [
            {"key": "Staff of the Archmage", "slot": "main_hand", "damage": 22,
             "armor_class": 0, "required_level": 35, "price": 500,
             "desc": "A staff that hums with barely-contained magical energy."},
            {"key": "Raiment of the Arcane", "slot": "torso", "damage": 0,
             "armor_class": 18, "required_level": 35, "price": 550,
             "desc": "Robes worn only by those who have mastered the arcane arts."},
            {"key": "Crown of Stars", "slot": "head", "damage": 0,
             "armor_class": 8, "required_level": 35, "price": 400,
             "desc": "A crown that glitters with captured starlight."},
        ],
        "Exalted": [
            {"key": "Staff of the Archon", "slot": "main_hand", "damage": 32,
             "armor_class": 0, "required_level": 50, "price": 1200,
             "desc": "The legendary staff of the first Archon of the Arcane Order."},
            {"key": "Mantle of the Archon", "slot": "torso", "damage": 0,
             "armor_class": 26, "required_level": 50, "price": 1300,
             "desc": "A mantle woven from pure magical essence."},
            {"key": "Diadem of Omniscience", "slot": "head", "damage": 0,
             "armor_class": 12, "required_level": 50, "price": 900,
             "desc": "A diadem that grants glimpses of all knowledge."},
        ],
    },
    "wildlands": {
        "Friendly": [
            {"key": "Ranger's Longbow", "slot": "main_hand", "damage": 10,
             "armor_class": 0, "required_level": 10, "price": 45,
             "desc": "A sturdy longbow crafted from yew by wildlands rangers."},
            {"key": "Forester's Tunic", "slot": "torso", "damage": 0,
             "armor_class": 7, "required_level": 10, "price": 50,
             "desc": "A green tunic that blends perfectly with forest foliage."},
        ],
        "Honored": [
            {"key": "Eagle-Eye Bow", "slot": "main_hand", "damage": 16,
             "armor_class": 0, "required_level": 20, "price": 160,
             "desc": "A bow blessed by the spirits of the great eagles."},
            {"key": "Warden's Leathers", "slot": "torso", "damage": 0,
             "armor_class": 14, "required_level": 20, "price": 180,
             "desc": "Enchanted leather armour worn by the wardens of the wild."},
            {"key": "Cloak of the Wild", "slot": "back", "damage": 0,
             "armor_class": 4, "required_level": 20, "price": 140,
             "desc": "A cloak that shifts colours to match the surrounding terrain."},
        ],
        "Revered": [
            {"key": "Stormcaller Bow", "slot": "main_hand", "damage": 24,
             "armor_class": 0, "required_level": 35, "price": 450,
             "desc": "A bow that can call lightning from a clear sky."},
            {"key": "Ancient Bark Armour", "slot": "torso", "damage": 0,
             "armor_class": 20, "required_level": 35, "price": 500,
             "desc": "Living armour grown from the bark of the Eldest Tree."},
            {"key": "Mantle of the Huntmaster", "slot": "back", "damage": 0,
             "armor_class": 8, "required_level": 35, "price": 350,
             "desc": "A mantle worn by the greatest hunters of the wildlands."},
        ],
        "Exalted": [
            {"key": "Heartseeker", "slot": "main_hand", "damage": 34,
             "armor_class": 0, "required_level": 50, "price": 1100,
             "desc": "The legendary bow that never misses its mark."},
            {"key": "Vestments of the Wild God", "slot": "torso", "damage": 0,
             "armor_class": 28, "required_level": 50, "price": 1200,
             "desc": "Armour blessed by the Wild God himself."},
            {"key": "Wings of the Zephyr", "slot": "back", "damage": 0,
             "armor_class": 12, "required_level": 50, "price": 900,
             "desc": "A cloak woven from the essence of the west wind."},
        ],
    },
    "underworld": {
        "Friendly": [
            {"key": "Shadow Dagger", "slot": "main_hand", "damage": 10,
             "armor_class": 0, "required_level": 10, "price": 45,
             "desc": "A thin blade coated with a paralytic venom."},
            {"key": "Dark Leather Vest", "slot": "torso", "damage": 0,
             "armor_class": 7, "required_level": 10, "price": 50,
             "desc": "Supple black leather that makes no sound."},
        ],
        "Honored": [
            {"key": "Assassin's Kris", "slot": "main_hand", "damage": 16,
             "armor_class": 0, "required_level": 20, "price": 160,
             "desc": "A wavy-bladed dagger favoured by the underworld's deadliest."},
            {"key": "Shadow-Woven Jerkin", "slot": "torso", "damage": 0,
             "armor_class": 14, "required_level": 20, "price": 180,
             "desc": "Armour woven from captured shadows."},
            {"key": "Ring of Silent Steps", "slot": "ring1", "damage": 0,
             "armor_class": 3, "required_level": 20, "price": 150,
             "desc": "A ring that muffles all sound around the wearer."},
        ],
        "Revered": [
            {"key": "Nightfall", "slot": "main_hand", "damage": 24,
             "armor_class": 0, "required_level": 35, "price": 450,
             "desc": "A blade that is invisible in darkness."},
            {"key": "Umbral Carapace", "slot": "torso", "damage": 0,
             "armor_class": 20, "required_level": 35, "price": 500,
             "desc": "Armour that drinks in light, leaving only shadow."},
            {"key": "Band of the Ghost", "slot": "ring1", "damage": 0,
             "armor_class": 6, "required_level": 35, "price": 350,
             "desc": "A ring that allows the wearer to phase through solid matter."},
        ],
        "Exalted": [
            {"key": "Godslayer", "slot": "main_hand", "damage": 34,
             "armor_class": 0, "required_level": 50, "price": 1100,
             "desc": "The legendary dagger said to have killed a god."},
            {"key": "Shroud of the Night Lord", "slot": "torso", "damage": 0,
             "armor_class": 28, "required_level": 50, "price": 1200,
             "desc": "A shroud worn by the Night Lord of the underworld."},
            {"key": "Ring of the Shadow King", "slot": "ring1", "damage": 0,
             "armor_class": 10, "required_level": 50, "price": 900,
             "desc": "The signet ring of the Shadow King himself."},
        ],
    },
}


class ReputationVendorNPC(DefaultCharacter):
    """
    NPC vendor that sells faction-specific gear gated by reputation standing.

    Players must have the required standing tier with the vendor's faction
    to purchase items.  Higher tiers unlock more powerful gear.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.vendor_faction = "aethelgard"
        self.db.vendor_type = "reputation"

    def get_available_gear(self, character) -> List[Dict[str, Any]]:
        """
        Return all gear items the character can see based on their
        reputation standing with this vendor's faction.
        """
        faction = self.attributes.get("vendor_faction", "aethelgard") if hasattr(self, "attributes") else "aethelgard"
        standing = ReputationSystem.get_standing(character, faction)

        # Standing tiers in ascending order
        tier_order = ["Friendly", "Honored", "Revered", "Exalted"]
        available_tiers = []
        for tier in tier_order:
            available_tiers.append(tier)
            if tier == standing:
                break

        faction_gear = REPUTATION_VENDOR_GEAR.get(faction, {})
        available = []
        for tier in available_tiers:
            for item in faction_gear.get(tier, []):
                item_copy = dict(item)
                item_copy["tier"] = tier
                available.append(item_copy)

        return available

    def buy_item(self, character, item_key: str) -> Tuple[bool, str]:
        """
        Sell a reputation-gated item to a player.

        Checks:
          1. Item exists in the vendor's faction gear table.
          2. Player has sufficient reputation standing.
          3. Player meets the required level.
          4. Player has enough gold.
        """
        faction = self.attributes.get("vendor_faction", "aethelgard") if hasattr(self, "attributes") else "aethelgard"
        standing = ReputationSystem.get_standing(character, faction)

        faction_gear = REPUTATION_VENDOR_GEAR.get(faction, {})
        tier_order = ["Friendly", "Honored", "Revered", "Exalted"]

        # Find the item in the gear tables
        found_item = None
        found_tier = None
        for tier in tier_order:
            for item in faction_gear.get(tier, []):
                if item["key"].lower() == item_key.lower():
                    found_item = item
                    found_tier = tier
                    break
            if found_item:
                break

        if not found_item:
            return False, f"'{item_key}' is not sold here."

        # Check reputation standing
        standing_idx = tier_order.index(standing) if standing in tier_order else -1
        required_idx = tier_order.index(found_tier)
        if standing_idx < required_idx:
            return False, f"You need {found_tier} standing or higher to purchase {found_item['key']}. (You are {standing}.)"

        # Check level requirement
        char_level = character.attributes.get("level", default=1) if hasattr(character, "attributes") else 1
        if char_level < found_item["required_level"]:
            return False, f"You must be level {found_item['required_level']} to use {found_item['key']}. (You are level {char_level}.)"

        # Check gold
        gold = character.attributes.get("money", default=0) if hasattr(character, "attributes") else 0
        if gold < found_item["price"]:
            return False, f"You need {found_item['price']} gold to buy {found_item['key']}. (You have {gold} gold.)"

        # Deduct gold
        if hasattr(character, "attributes"):
            character.attributes.add("money", gold - found_item["price"])

        # Create the item and give it to the player
        try:
            from evennia import create_object
            item_obj = create_object(
                "typeclasses.objects.Object",
                key=found_item["key"],
                location=character,
                attributes=[
                    ("desc", found_item["desc"]),
                    ("item_type", "equipment"),
                    ("slot", found_item["slot"]),
                    ("damage", found_item.get("damage", 0)),
                    ("armor_class", found_item.get("armor_class", 0)),
                    ("required_level", found_item["required_level"]),
                    ("value", found_item["price"]),
                    ("faction", faction),
                    ("reputation_tier", found_tier),
                ],
            )
            return True, f"You purchase {found_item['key']} for {found_item['price']} gold!"
        except Exception as e:
            # Refund on failure
            if hasattr(character, "attributes"):
                character.attributes.add("money", gold)
            return False, f"Error creating item: {e}"


# ---------------------------------------------------------------------------
# Reputation Vendor Commands
# ---------------------------------------------------------------------------

class CmdRepVendor(Command):
    """
    Browse and buy from a faction reputation vendor.

    Usage:
      repvendor              — list available gear for your standing
      repvendor buy <item>   — purchase a reputation-gated item

    Reputation vendors sell faction-specific gear that requires a minimum
    standing tier (Friendly → Honored → Revered → Exalted).  Higher tiers
    unlock more powerful equipment.
    """

    key = "repvendor"
    aliases = ["repbuy", "repgear"]
    locks = "cmd:all()"
    help_category = "Commerce"

    def parse(self):
        self.args = self.args.strip()
        if self.args.startswith("buy "):
            self.subcmd = "buy"
            self.target = self.args[4:].strip()
        else:
            self.subcmd = "list"
            self.target = ""

    def func(self):
        caller = self.caller
        location = caller.location
        if not location:
            return

        # Find a reputation vendor in the room
        vendor = None
        for obj in location.contents:
            if isinstance(obj, ReputationVendorNPC):
                vendor = obj
                break

        if not vendor:
            caller.msg("|yThere is no reputation vendor here.|n")
            return

        if self.subcmd == "buy":
            if not self.target:
                caller.msg("|yUsage: repvendor buy <item>|n")
                return
            ok, msg = vendor.buy_item(caller, self.target)
            if ok:
                caller.msg(f"|g{msg}|n")
            else:
                caller.msg(f"|r{msg}|n")
        else:
            # List available gear
            faction = vendor.attributes.get("vendor_faction", "aethelgard") if hasattr(vendor, "attributes") else "aethelgard"
            standing = ReputationSystem.get_standing(caller, faction)
            available = vendor.get_available_gear(caller)

            faction_names = {
                "aethelgard": "|gAethelgard Alliance|n",
                "gorgoroth": "|rGorgoroth Horde|n",
                "merchants_guild": "|yMerchants Guild|n",
                "arcane_order": "|cArcane Order|n",
                "wildlands": "|gWildlands|n",
                "underworld": "|mUnderworld|n",
            }
            faction_display = faction_names.get(faction, faction)

            out = f"|w=== {vendor.key} — {faction_display} |w(Standing: {standing}) ===|n\n"
            if not available:
                out += "|yNo gear available at your current standing.|n\n"
                out += "|yIncrease your reputation to Friendly or higher to unlock gear.|n"
            else:
                current_tier = None
                for item in available:
                    if item["tier"] != current_tier:
                        current_tier = item["tier"]
                        tier_color = {"Friendly": "|c", "Honored": "|g", "Revered": "|Y", "Exalted": "|M"}.get(current_tier, "|w")
                        out += f"\n  {tier_color}--- {current_tier} ---|n\n"
                    out += f"  |c{item['key']}|n [Lvl {item['required_level']}] — |Y{item['price']} gold|n\n"
                    out += f"    {item['desc']}\n"

            caller.msg(out)


class CmdReputation(Command):
    """
    View your faction reputation standings.

    Usage:
      reputation
      rep

    Displays your standing with all major factions, including:
      - Reputation value (clamped -5000 to +5000)
      - Standing tier (Hated → Exalted)
      - Vendor discount/markup percentage

    Reputation is earned by:
      - Killing mobs of opposing factions
      - Completing quests for faction NPCs
      - Killing bosses
    """

    key = "reputation"
    aliases = ["rep"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        caller = self.caller
        from world.reputation import ReputationSystem
        display = ReputationSystem.format_reputation(caller)
        caller.msg(display)
