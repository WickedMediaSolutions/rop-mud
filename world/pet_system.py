"""
Pet / Companion System for 'rop'
=================================
Provides non-combat pets and combat companions:
  - Non-combat pets (cosmetic, follow owner, emotes)
  - Combat companions (fight alongside owner, level up)
  - Pet shop / adoption
  - Pet bonding and loyalty
  - Pet inventory and equipment

Usage:
  from world.pet_system import PetManager, Pet, Companion
"""

from __future__ import annotations

import random
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from evennia import create_object, search_object
    from evennia.objects.models import ObjectDB
except Exception:
    create_object = None
    search_object = None
    ObjectDB = None


# ===========================================================================
# PET TYPES
# ===========================================================================

PET_TYPES = {
    # Non-combat pets (cosmetic)
    "cat": {
        "name": "Black Cat",
        "type": "non_combat",
        "cost": 50,
        "min_level": 1,
        "description": "A sleek black cat with glowing green eyes. It purrs contentedly at your side.",
        "emotes": ["purrs softly", "flicks its tail", "stares at something unseen", "rubs against your leg"],
        "rarity": "common",
    },
    "dog": {
        "name": "Loyal Hound",
        "type": "non_combat",
        "cost": 75,
        "min_level": 1,
        "description": "A faithful hound with a wagging tail. It barks happily when you return.",
        "emotes": ["wags its tail", "barks happily", "pants excitedly", "sniffs the ground"],
        "rarity": "common",
    },
    "raven": {
        "name": "Shadow Raven",
        "type": "non_combat",
        "cost": 100,
        "min_level": 5,
        "description": "A dark-feathered raven that perches on your shoulder. Its eyes gleam with intelligence.",
        "emotes": ["caws softly", "preens its feathers", "tilts its head", "flaps its wings"],
        "rarity": "uncommon",
    },
    "fox": {
        "name": "Arctic Fox",
        "type": "non_combat",
        "cost": 150,
        "min_level": 10,
        "description": "A beautiful white fox with piercing blue eyes. It moves with silent grace.",
        "emotes": ["twitches its ears", "curls its tail", "yawns lazily", "pounces at a snowflake"],
        "rarity": "uncommon",
    },
    "dragon_whelp": {
        "name": "Dragon Whelp",
        "type": "non_combat",
        "cost": 500,
        "min_level": 20,
        "description": "A tiny dragon hatchling with shimmering scales. It puffs small smoke rings.",
        "emotes": ["puffs a smoke ring", "squeaks adorably", "flaps its tiny wings", "curls up on your shoulder"],
        "rarity": "rare",
    },
    "will_o_wisp": {
        "name": "Will-o'-Wisp",
        "type": "non_combat",
        "cost": 300,
        "min_level": 15,
        "description": "A floating orb of ethereal light that dances around you.",
        "emotes": ["flickers brightly", "floats in a circle", "pulses with soft light", "dances playfully"],
        "rarity": "rare",
    },
    "baby_phoenix": {
        "name": "Phoenix Chick",
        "type": "non_combat",
        "cost": 1000,
        "min_level": 30,
        "description": "A fiery phoenix chick that radiates warmth. It chirps melodically.",
        "emotes": ["chirps a fiery melody", "fluffs its flame-feathers", "emits a warm glow", "hops excitedly"],
        "rarity": "legendary",
    },

    # Combat companions
    "wolf_companion": {
        "name": "Dire Wolf Companion",
        "type": "combat",
        "cost": 200,
        "min_level": 10,
        "description": "A fierce dire wolf that fights alongside you.",
        "hp_per_level": 15,
        "damage_per_level": 3,
        "armor_per_level": 0.5,
        "attack_speed": 3.5,
        "damage_type": "pierce",
        "abilities": ["howl", "pounce"],
        "rarity": "uncommon",
    },
    "bear_companion": {
        "name": "Grizzly Bear Companion",
        "type": "combat",
        "cost": 350,
        "min_level": 18,
        "description": "A massive grizzly bear that tanks damage for you.",
        "hp_per_level": 25,
        "damage_per_level": 4,
        "armor_per_level": 1.5,
        "attack_speed": 4.5,
        "damage_type": "blunt",
        "abilities": ["maul", "roar"],
        "rarity": "rare",
    },
    "panther_companion": {
        "name": "Shadow Panther Companion",
        "type": "combat",
        "cost": 400,
        "min_level": 22,
        "description": "A stealthy panther that strikes from the shadows.",
        "hp_per_level": 12,
        "damage_per_level": 5,
        "armor_per_level": 0.3,
        "attack_speed": 2.5,
        "damage_type": "slash",
        "abilities": ["pounce", "stealth_strike"],
        "rarity": "rare",
    },
    "golem_companion": {
        "name": "Iron Golem Companion",
        "type": "combat",
        "cost": 600,
        "min_level": 30,
        "description": "A towering iron golem that crushes your enemies.",
        "hp_per_level": 30,
        "damage_per_level": 6,
        "armor_per_level": 3.0,
        "attack_speed": 5.0,
        "damage_type": "blunt",
        "abilities": ["ground_slam", "taunt"],
        "rarity": "epic",
    },
    "dragon_companion": {
        "name": "Young Dragon Companion",
        "type": "combat",
        "cost": 1500,
        "min_level": 40,
        "description": "A young dragon that breathes fire on your foes.",
        "hp_per_level": 20,
        "damage_per_level": 8,
        "armor_per_level": 2.0,
        "attack_speed": 3.0,
        "damage_type": "fire",
        "abilities": ["fire_breath", "wing_buffet"],
        "rarity": "legendary",
    },
}


# ===========================================================================
# PET DATA
# ===========================================================================

class Pet:
    """Represents a player's pet (non-combat or combat)."""

    def __init__(self, pet_id: str, pet_type: str, owner_name: str,
                 pet_name: Optional[str] = None):
        template = PET_TYPES.get(pet_type, {})
        self.pet_id = pet_id
        self.pet_type = pet_type
        self.owner_name = owner_name
        self.name = pet_name or template.get("name", "Unknown Pet")
        self.type = template.get("type", "non_combat")
        self.level = 1
        self.xp = 0
        self.bond_level = 1  # 1-10, increases with time and combat
        self.bond_xp = 0
        self.hp = template.get("hp_per_level", 10)
        self.max_hp = template.get("hp_per_level", 10)
        self.damage = template.get("damage_per_level", 1)
        self.armor = template.get("armor_per_level", 0)
        self.attack_speed = template.get("attack_speed", 3.0)
        self.damage_type = template.get("damage_type", "slash")
        self.abilities = template.get("abilities", [])
        self.rarity = template.get("rarity", "common")
        self.emotes = template.get("emotes", ["looks around curiously"])
        self.description = template.get("description", "")
        self.last_attack = 0.0
        self.last_emote = 0.0
        self.created_at = time.time()
        self.is_active = True
        self.equipment: Dict[str, Any] = {}  # pet collar, armor, etc.

    def serialize(self) -> Dict[str, Any]:
        """Serialize pet data for storage."""
        return {
            "pet_id": self.pet_id,
            "pet_type": self.pet_type,
            "name": self.name,
            "type": self.type,
            "level": self.level,
            "xp": self.xp,
            "bond_level": self.bond_level,
            "bond_xp": self.bond_xp,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "damage": self.damage,
            "armor": self.armor,
            "attack_speed": self.attack_speed,
            "damage_type": self.damage_type,
            "abilities": self.abilities,
            "rarity": self.rarity,
            "created_at": self.created_at,
            "is_active": self.is_active,
            "equipment": self.equipment,
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any], owner_name: str) -> "Pet":
        """Restore a pet from serialized data."""
        pet = cls(data["pet_id"], data["pet_type"], owner_name, data.get("name"))
        pet.level = data.get("level", 1)
        pet.xp = data.get("xp", 0)
        pet.bond_level = data.get("bond_level", 1)
        pet.bond_xp = data.get("bond_xp", 0)
        pet.hp = data.get("hp", pet.max_hp)
        pet.max_hp = data.get("max_hp", pet.max_hp)
        pet.damage = data.get("damage", pet.damage)
        pet.armor = data.get("armor", pet.armor)
        pet.attack_speed = data.get("attack_speed", pet.attack_speed)
        pet.damage_type = data.get("damage_type", pet.damage_type)
        pet.abilities = data.get("abilities", pet.abilities)
        pet.rarity = data.get("rarity", pet.rarity)
        pet.created_at = data.get("created_at", time.time())
        pet.is_active = data.get("is_active", True)
        pet.equipment = data.get("equipment", {})
        return pet

    def get_display_name(self) -> str:
        """Get color-coded display name based on rarity."""
        colors = {
            "common": "|w",
            "uncommon": "|g",
            "rare": "|b",
            "epic": "|m",
            "legendary": "|Y",
        }
        color = colors.get(self.rarity, "|w")
        return f"{color}{self.name}|n"

    def get_random_emote(self) -> str:
        """Get a random emote for the pet."""
        return random.choice(self.emotes)

    def gain_xp(self, amount: int) -> bool:
        """
        Add XP to the pet. Returns True if the pet leveled up.
        """
        self.xp += amount
        xp_needed = self._xp_for_next_level()
        if self.xp >= xp_needed:
            self.level += 1
            self.xp -= xp_needed
            self._apply_level_up()
            return True
        return False

    def _xp_for_next_level(self) -> int:
        """XP needed for next level."""
        return 100 * self.level * self.level

    def _apply_level_up(self) -> None:
        """Apply stat increases on level up."""
        template = PET_TYPES.get(self.pet_type, {})
        if self.type == "combat":
            self.max_hp = template.get("hp_per_level", 10) * self.level
            self.hp = self.max_hp
            self.damage = template.get("damage_per_level", 1) * self.level
            self.armor = int(template.get("armor_per_level", 0) * self.level)

    def gain_bond(self, amount: int = 1) -> bool:
        """
        Increase bond with the pet. Returns True if bond level increased.
        """
        self.bond_xp += amount
        needed = 50 * self.bond_level
        if self.bond_xp >= needed:
            self.bond_level = min(10, self.bond_level + 1)
            self.bond_xp -= needed
            return True
        return False

    def get_bond_bonus(self) -> float:
        """Get damage bonus from bond level (2% per bond level)."""
        return 1.0 + (self.bond_level * 0.02)

    def take_damage(self, damage: int) -> int:
        """
        Apply damage to the pet. Returns remaining HP.
        """
        self.hp = max(0, self.hp - damage)
        return self.hp

    def heal(self, amount: int) -> int:
        """Heal the pet. Returns new HP."""
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp

    def is_alive(self) -> bool:
        return self.hp > 0


# ===========================================================================
# PET MANAGER
# ===========================================================================

class PetManager:
    """
    Manages all pets for all players.

    Features:
      - Adopt/buy pets
      - Release/abandon pets
      - Switch active pet
      - Pet combat integration
      - Pet bonding and leveling
    """

    def __init__(self):
        self._player_pets: Dict[int, List[Pet]] = {}  # dbref -> list of Pet
        self._active_pet: Dict[int, str] = {}  # dbref -> pet_id

    # ---- Pet Ownership ----

    def adopt_pet(self, character: Any, pet_type: str,
                  pet_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Adopt a new pet.

        Args:
            character: The player adopting.
            pet_type: Key in PET_TYPES.
            pet_name: Optional custom name for the pet.

        Returns:
            (success, message)
        """
        if pet_type not in PET_TYPES:
            return False, f"Unknown pet type: {pet_type}"

        template = PET_TYPES[pet_type]
        char_level = character.attributes.get("level", default=1)

        if char_level < template["min_level"]:
            return False, f"You must be level {template['min_level']} to adopt a {template['name']}."

        # Check cost
        cost = template["cost"]
        char_gold = character.attributes.get("gold", default=0)
        if char_gold < cost:
            return False, f"You need {cost} gold to adopt a {template['name']}. You have {char_gold}."

        # Check pet limit
        pets = self._player_pets.get(character.id, [])
        max_pets = 3 + (char_level // 10)  # 3 base + 1 per 10 levels
        if len(pets) >= max_pets:
            return False, f"You can only have {max_pets} pets. Release one first."

        # Deduct gold
        character.attributes.add("gold", char_gold - cost)

        # Create pet
        pet_id = f"pet_{uuid.uuid4().hex[:8]}"
        pet = Pet(pet_id, pet_type, character.key, pet_name)

        if character.id not in self._player_pets:
            self._player_pets[character.id] = []
        self._player_pets[character.id].append(pet)

        # Auto-activate if no active pet
        if character.id not in self._active_pet:
            self._active_pet[character.id] = pet_id

        return True, f"You adopted a {pet.get_display_name()}! Use 'pet list' to see your pets."

    def release_pet(self, character: Any, pet_id: str) -> Tuple[bool, str]:
        """Release a pet back to the wild."""
        pets = self._player_pets.get(character.id, [])
        for i, pet in enumerate(pets):
            if pet.pet_id == pet_id:
                name = pet.name
                pets.pop(i)
                if self._active_pet.get(character.id) == pet_id:
                    self._active_pet.pop(character.id, None)
                    # Activate next pet if available
                    if pets:
                        self._active_pet[character.id] = pets[0].pet_id
                if not pets:
                    self._player_pets.pop(character.id, None)
                return True, f"You release {name} back into the wild."
        return False, "Pet not found."

    def get_pets(self, character: Any) -> List[Pet]:
        """Get all pets owned by a character."""
        return self._player_pets.get(character.id, [])

    def get_active_pet(self, character: Any) -> Optional[Pet]:
        """Get the character's currently active pet."""
        pet_id = self._active_pet.get(character.id)
        if not pet_id:
            return None
        pets = self._player_pets.get(character.id, [])
        for pet in pets:
            if pet.pet_id == pet_id:
                return pet
        return None

    def set_active_pet(self, character: Any, pet_id: str) -> Tuple[bool, str]:
        """Switch which pet is active."""
        pets = self._player_pets.get(character.id, [])
        for pet in pets:
            if pet.pet_id == pet_id:
                self._active_pet[character.id] = pet_id
                return True, f"{pet.get_display_name()} is now your active pet."
        return False, "Pet not found."

    def rename_pet(self, character: Any, pet_id: str, new_name: str) -> Tuple[bool, str]:
        """Rename a pet."""
        pets = self._player_pets.get(character.id, [])
        for pet in pets:
            if pet.pet_id == pet_id:
                old_name = pet.name
                pet.name = new_name
                return True, f"Renamed {old_name} to {new_name}."
        return False, "Pet not found."

    # ---- Pet Combat ----

    def pet_combat_tick(self, character: Any, target: Any) -> List[str]:
        """
        Process one combat tick for the active combat pet.

        Returns list of message strings.
        """
        pet = self.get_active_pet(character)
        if not pet or pet.type != "combat" or not pet.is_alive():
            return []

        messages = []
        now = time.time()

        # Check attack cooldown
        if now - pet.last_attack < pet.attack_speed:
            return []

        pet.last_attack = now

        # Hit roll
        hit_chance = 0.75 + (pet.bond_level * 0.02)
        if random.random() > hit_chance:
            messages.append(f"|WYour {pet.get_display_name()} misses {target.key}.|n")
            return messages

        # Damage calculation
        base_dmg = pet.damage
        bond_mult = pet.get_bond_bonus()
        variance = random.uniform(0.8, 1.2)
        dmg = max(1, int(base_dmg * bond_mult * variance))

        # Apply damage
        if hasattr(target, "attributes"):
            hp = target.attributes.get("hp", 0)
            target.attributes.add("hp", max(0, hp - dmg))

        messages.append(f"|WYour {pet.get_display_name()} attacks {target.key} for {dmg} damage.|n")

        # Pet gains XP from combat
        if pet.gain_xp(dmg):
            messages.append(f"|gYour {pet.get_display_name()} has grown to level {pet.level}!|n")

        # Bond gain
        if pet.gain_bond(1):
            messages.append(f"|YYour bond with {pet.get_display_name()} has deepened! (Bond Level {pet.bond_level})|n")

        # Check if target died
        if hasattr(target, "attributes") and target.attributes.get("hp", 0) <= 0:
            try:
                from world.tick_combat import _handle_target_death
                _handle_target_death(character, target)
            except Exception:
                pass

        return messages

    def pet_take_damage(self, character: Any, damage: int) -> Tuple[int, List[str]]:
        """
        Active combat pet absorbs some damage for the owner.

        Returns (remaining_damage, messages).
        """
        pet = self.get_active_pet(character)
        if not pet or pet.type != "combat" or not pet.is_alive():
            return damage, []

        messages = []
        absorbed = min(damage // 3, pet.hp)  # Pet absorbs up to 1/3 of damage
        pet.take_damage(absorbed)
        remaining = damage - absorbed

        if pet.hp <= 0:
            messages.append(f"|RYour {pet.get_display_name()} falls in battle!|n")
        else:
            messages.append(f"|yYour {pet.get_display_name()} absorbs {absorbed} damage for you.|n")

        return remaining, messages

    def pet_emote_tick(self, character: Any) -> Optional[str]:
        """
        Get a random pet emote (for non-combat pets).

        Returns emote string or None.
        """
        pet = self.get_active_pet(character)
        if not pet or pet.type != "non_combat":
            return None

        now = time.time()
        if now - pet.last_emote < 30:  # Emote every 30 seconds
            return None

        pet.last_emote = now
        emote = pet.get_random_emote()
        return f"|w{pet.get_display_name()} {emote}.|n"

    def feed_pet(self, character: Any, food_item: str = "pet food") -> Tuple[bool, str]:
        """Feed the active pet to restore HP and gain bond."""
        pet = self.get_active_pet(character)
        if not pet:
            return False, "You don't have an active pet."

        heal_amount = pet.max_hp // 4
        pet.heal(heal_amount)
        pet.gain_bond(2)

        return True, f"You feed {pet.get_display_name()}. It recovers {heal_amount} HP and seems happier!"

    def rest_pet(self, character: Any) -> Tuple[bool, str]:
        """Rest the active pet to full HP."""
        pet = self.get_active_pet(character)
        if not pet:
            return False, "You don't have an active pet."

        pet.heal(pet.max_hp)
        return True, f"{pet.get_display_name()} rests and recovers to full health."

    # ---- Persistence ----

    def save_pets(self, character: Any) -> None:
        """Save all pet data to character attributes."""
        pets = self._player_pets.get(character.id, [])
        serialized = [p.serialize() for p in pets]
        character.attributes.add("pets_data", serialized)
        character.attributes.add("active_pet_id", self._active_pet.get(character.id, ""))

    def load_pets(self, character: Any) -> None:
        """Load pet data from character attributes."""
        serialized = character.attributes.get("pets_data", default=[])
        if not serialized:
            return

        pets = []
        for data in serialized:
            pet = Pet.deserialize(data, character.key)
            pets.append(pet)
        self._player_pets[character.id] = pets

        active_id = character.attributes.get("active_pet_id", default="")
        if active_id and any(p.pet_id == active_id for p in pets):
            self._active_pet[character.id] = active_id
        elif pets:
            self._active_pet[character.id] = pets[0].pet_id


# Global pet manager
pet_manager = PetManager()