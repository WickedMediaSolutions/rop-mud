"""
Armor Set System for 'rop'

Provides:
  - ArmorSetDefinition: defines a named armor set with piece slots and bonuses
  - ArmorSetRegistry: manages all armor sets in the game
  - ArmorSetChecker: checks what set bonuses a character currently has active
  - Integration with look self / armory display

Set Bonus thresholds:
  - 2/4 pieces equipped -> partial bonus
  - 4/4 pieces equipped -> full bonus (includes partial)

Usage:
  from world.armor_sets import ArmorSetDefinition, armor_set_registry, \
      ArmorSetChecker

  # Define a set
  ds_set = ArmorSetDefinition(
      set_id="dragonscale",
      name="Dragonscale Armor",
      pieces={
          "head": "Dragonscale Helm",
          "torso": "Dragonscale Breastplate",
          "legs": "Dragonscale Greaves",
          "arms": "Dragonscale Vambraces",
      },
      bonus_2={"max_hp": 20, "defense": 2},       # 2-piece bonus
      bonus_4={"max_hp": 50, "defense": 5, "fire_resist": 15},  # 4-piece
  )
  armor_set_registry.register(ds_set)

  # Check character
  checker = ArmorSetChecker(character)
  active_bonuses = checker.get_active_bonuses()
"""

# ---------------------------------------------------------------------------
# Armor Set Definition
# ---------------------------------------------------------------------------


class ArmorSetDefinition:
    """
    Defines a matching armor set.

    Attributes:
        set_id: Unique string identifier for this set.
        name: Display name shown to players.
        pieces: Dict mapping equipment slot -> item key that counts toward the set.
                e.g. {"head": "Dragonscale Helm", "torso": "Dragonscale Breastplate",
                       "legs": "Dragonscale Greaves", "arms": "Dragonscale Vambraces"}
        bonus_2: Dict of stat bonuses granted when 2 pieces are equipped.
        bonus_4: Dict of stat bonuses granted when all 4 pieces are equipped.
                 (stacks with bonus_2 for a total of 4-piece effect)
        flavor_text: Optional flavor description for tooltip display.
    """

    def __init__(self, set_id, name, pieces, bonus_2=None, bonus_4=None,
                 flavor_text=""):
        self.set_id = set_id
        self.name = name
        self.pieces = pieces  # slot -> item_key
        self.bonus_2 = bonus_2 or {}
        self.bonus_4 = bonus_4 or {}
        self.flavor_text = flavor_text

    def get_item_keys(self):
        """Return the set of item keys that belong to this set."""
        return set(self.pieces.values())

    def get_slots(self):
        """Return the list of slots this set covers."""
        return list(self.pieces.keys())

    def check_piece(self, slot, item_name):
        """
        Check if a given equipped item matches this set's piece for that slot.

        Args:
            slot: Equipment slot name (e.g., "head", "torso").
            item_name: The item key/name that is equipped.

        Returns:
            True if the item matches this set's piece for that slot.
        """
        # Case-insensitive slot lookup
        slot_lower = slot.lower() if slot else ""
        for piece_slot, piece_name in self.pieces.items():
            if piece_slot.lower() == slot_lower:
                return item_name and item_name.lower() == piece_name.lower()
        return False

    def count_equipped(self, equipped):
        """
        Count how many pieces of this set are currently equipped.

        Args:
            equipped: Dict of slot -> item_name from character.

        Returns:
            Number of matching pieces (0-4).
        """
        count = 0
        for slot, expected_name in self.pieces.items():
            equipped_name = equipped.get(slot, "")
            if equipped_name and equipped_name.lower() == expected_name.lower():
                count += 1
        return count

    def get_bonus_for_count(self, count):
        """
        Get the combined stat bonuses for a given number of equipped pieces.

        Args:
            count: Number of set pieces equipped (0-4).

        Returns:
            Dict of bonus_name -> bonus_value. Empty dict if < 2.
        """
        bonuses = {}
        if count >= 4:
            # Apply both 2-piece and 4-piece (stacking)
            for key, value in self.bonus_2.items():
                bonuses[key] = value
            for key, value in self.bonus_4.items():
                bonuses[key] = bonuses.get(key, 0) + value
        elif count >= 2:
            for key, value in self.bonus_2.items():
                bonuses[key] = value
        return bonuses

    def __repr__(self):
        return f"<ArmorSet {self.set_id} ({len(self.pieces)} pieces)>"


# ---------------------------------------------------------------------------
# Armor Set Registry
# ---------------------------------------------------------------------------


class ArmorSetRegistry:
    """
    Central registry of all armor sets in the game.
    """

    def __init__(self):
        self._sets = {}  # set_id -> ArmorSetDefinition

    def register(self, armor_set):
        """Register an ArmorSetDefinition."""
        if not isinstance(armor_set, ArmorSetDefinition):
            raise TypeError("Must register an ArmorSetDefinition instance")
        self._sets[armor_set.set_id] = armor_set

    def get(self, set_id):
        """Retrieve an ArmorSetDefinition by ID, or None."""
        return self._sets.get(set_id)

    def find_set_for_item(self, item_name, slot=None):
        """
        Find which armor set an item belongs to.

        Args:
            item_name: The item's key/name.
            slot: Optional slot to narrow the search.

        Returns:
            ArmorSetDefinition or None.
        """
        if not item_name:
            return None
        item_lower = item_name.lower()
        for armor_set in self._sets.values():
            for piece_slot, piece_name in armor_set.pieces.items():
                if piece_name.lower() == item_lower:
                    if slot is None or piece_slot == slot:
                        return armor_set
        return None

    def all(self):
        """Return all registered armor sets."""
        return list(self._sets.values())

    def clear(self):
        """Remove all sets (useful for testing)."""
        self._sets.clear()


# Global armor set registry
armor_set_registry = ArmorSetRegistry()
ARMOR_SETS = {}  # dict alias populated by register_default_armor_sets()


# ---------------------------------------------------------------------------
# Armor Set Checker (character-bound)
# ---------------------------------------------------------------------------


class ArmorSetChecker:
    """
    Checks a character's equipped items against the armor set registry
    and calculates active set bonuses.

    Usage:
        checker = ArmorSetChecker(character)
        active = checker.get_active_set_bonuses()
        # active is a dict: set_id -> {"set_name": ..., "count": N,
        #                               "bonuses": {...}, "pieces": [...]}
    """

    def __init__(self, character):
        self.character = character

    def get_equipped(self):
        """Get the character's currently equipped items dict (normalized)."""
        try:
            from world.mob_equipment import get_equipped_slot_map
            return get_equipped_slot_map(self.character)
        except Exception:
            raw = self.character.attributes.get("equipped", default={})
            if hasattr(raw, "items"):
                return {str(k): str(v) for k, v in raw.items()}
            return {}

    def get_active_set_bonuses(self):
        """
        Check all equipped items against registered armor sets.

        Returns:
            Dict mapping set_id -> {
                "set_name": str,
                "count": int (pieces equipped),
                "bonuses": dict (active stat bonuses),
                "pieces": list of slot names that matched,
                "flavor_text": str,
            }
            Only includes sets with at least 2 matching pieces.
        """
        equipped = self.get_equipped()
        active = {}

        for armor_set in armor_set_registry.all():
            count = 0
            matched_pieces = []
            for slot, expected_name in armor_set.pieces.items():
                equipped_name = equipped.get(slot, "")
                if equipped_name and equipped_name.lower() == expected_name.lower():
                    count += 1
                    matched_pieces.append(slot)

            if count >= 2:
                bonuses = armor_set.get_bonus_for_count(count)
                active[armor_set.set_id] = {
                    "set_name": armor_set.name,
                    "count": count,
                    "total_pieces": len(armor_set.pieces),
                    "bonuses": bonuses,
                    "pieces": matched_pieces,
                    "flavor_text": armor_set.flavor_text,
                }

        return active

    def get_total_bonuses(self):
        """
        Calculate the combined total of all active set bonuses.

        Returns:
            Dict of stat_name -> total_bonus_value
            (e.g., {"max_hp": 50, "defense": 7})
        """
        all_active = self.get_active_set_bonuses()
        totals = {}
        for set_data in all_active.values():
            for stat, value in set_data["bonuses"].items():
                totals[stat] = totals.get(stat, 0) + value
        return totals

    def format_display(self):
        """
        Build a formatted string showing active set bonuses for display
        in `look self` and similar commands.

        Returns:
            A string suitable for appending to character display, or
            empty string if no sets are active.
        """
        active = self.get_active_set_bonuses()
        if not active:
            return ""

        lines = ["", "|wArmor Set Bonuses:|n"]
        for set_id, data in active.items():
            pieces_str = f"{data['count']}/{data['total_pieces']}"
            lines.append(f"  |c{data['set_name']} ({pieces_str}):|n")
            for stat, value in data["bonuses"].items():
                label = _format_bonus_label(stat)
                lines.append(f"    |g+{value} {label}|n")
            if data.get("flavor_text"):
                lines.append(f"    |y\"{data['flavor_text']}\"|n")

        return "\n".join(lines)


def _format_bonus_label(stat_key):
    """Convert a stat key to a human-readable label."""
    labels = {
        "max_hp": "Max HP",
        "max_mana": "Max MP",
        "defense": "Defense",
        "fire_resist": "Fire Resist",
        "cold_resist": "Cold Resist",
        "poison_resist": "Poison Resist",
        "str": "STR",
        "dex": "DEX",
        "con": "CON",
        "int": "INT",
        "wis": "WIS",
        "cha": "CHA",
    }
    return labels.get(stat_key, stat_key.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Apply set bonuses to character stats (call on equip/dequip)
# ---------------------------------------------------------------------------


def apply_set_bonuses_to_character(character):
    """
    Calculate and store active set bonuses on the character.

    Called whenever equipment changes (equip/unequip) so that
    combat calculations and stat displays always reflect current
    set bonuses.

    Stored as character attribute: "armor_set_bonuses"
    """
    checker = ArmorSetChecker(character)
    total_bonuses = checker.get_total_bonuses()
    active_sets = checker.get_active_set_bonuses()

    character.attributes.add("armor_set_bonuses", total_bonuses)
    character.attributes.add("armor_set_active", active_sets)

    return total_bonuses


def get_stored_set_bonuses(character):
    """
    Retrieve the character's currently stored set bonuses dict.
    Returns empty dict if none are active.
    """
    return character.attributes.get("armor_set_bonuses", default={})


# ---------------------------------------------------------------------------
# Default Armor Sets
# ---------------------------------------------------------------------------


def register_default_armor_sets():
    """
    Register the default armor sets for the game.

    Called at server startup.
    """
    armor_set_registry.clear()
    ARMOR_SETS.clear()

    # --- Dragonscale Set ---
    ds_set = ArmorSetDefinition(
        set_id="dragonscale",
        name="Dragonscale Armor",
        pieces={
            "head": "Dragonscale Helm",
            "torso": "Dragonscale Breastplate",
            "legs": "Dragonscale Greaves",
            "arms": "Dragonscale Vambraces",
        },
        bonus_2={"max_hp": 20, "defense": 2},
        bonus_4={"max_hp": 50, "defense": 5, "fire_resist": 15},
        flavor_text="The scales of the ancient dragon protect the wearer from fire.",
    )
    armor_set_registry.register(ds_set)
    ARMOR_SETS["dragonscale"] = ds_set

    # --- Shadowstalker Set ---
    ss_set = ArmorSetDefinition(
        set_id="shadowstalker",
        name="Shadowstalker Armor",
        pieces={
            "head": "Shadowstalker Cowl",
            "torso": "Shadowstalker Chestguard",
            "legs": "Shadowstalker Leggings",
            "arms": "Shadowstalker Armwraps",
        },
        bonus_2={"max_hp": 15, "dex": 3},
        bonus_4={"max_hp": 40, "dex": 8, "defense": 4},
        flavor_text="Wreathed in shadow, the wearer moves with unnatural grace.",
    )
    armor_set_registry.register(ss_set)
    ARMOR_SETS["shadowstalker"] = ss_set

    # --- Paladin's Radiant Suit ---
    pr_set = ArmorSetDefinition(
        set_id="paladin_radiant",
        name="Paladin's Radiant Suit",
        pieces={
            "head": "Radiant Crown",
            "torso": "Radiant Breastplate",
            "legs": "Radiant Greaves",
            "arms": "Radiant Gauntlets",
        },
        bonus_2={"max_hp": 25, "max_mana": 10},
        bonus_4={"max_hp": 60, "max_mana": 30, "defense": 6},
        flavor_text="Blessed by the Light, this armor shields body and soul.",
    )
    armor_set_registry.register(pr_set)
    ARMOR_SETS["paladin_radiant"] = pr_set

    # --- Lich King's Regalia ---
    lr_set = ArmorSetDefinition(
        set_id="lich_regalia",
        name="Lich King's Regalia",
        pieces={
            "head": "Crown of Undeath",
            "torso": "Bone-Woven Vestments",
            "legs": "Spectral Legwraps",
            "arms": "Gravebound Bracers",
        },
        bonus_2={"max_mana": 15, "int": 3},
        bonus_4={"max_mana": 40, "int": 8, "cold_resist": 20},
        flavor_text="The chill of the grave empowers the wearer's dark magic.",
    )
    armor_set_registry.register(lr_set)
    ARMOR_SETS["lich_regalia"] = lr_set
