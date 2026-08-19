"""
Ranged Combat System for 'rop'
==============================
Provides bow/crossbow/thrown-weapon attacks with ammo tracking,
range mechanics, and integration with the tick-based combat system.

Features:
  - Bow, crossbow, longbow, shortbow weapon types
  - Arrow/bolt ammo tracking with consumption per shot
  - DEX-based accuracy and damage (vs STR for melee)
  - Range advantage: first-strike capability before melee engagement
  - Ammo recovery chance from corpses
  - Integration with racial passives and talent bonuses
  - Thrown weapons (daggers, axes, javelins) with retrieval chance

Usage:
  shoot <target>      — Fire a ranged weapon at a target
  fire <target>       — Alias for shoot
  reload              — Check ammo count / reload status
  throw <target>      — Throw a weapon at a target
"""

import random
import time
from evennia.utils import logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Base damage multipliers for ranged weapon types
RANGED_WEAPON_DAMAGE = {
    "shortbow":      1.0,
    "bow":           1.2,
    "longbow":       1.5,
    "crossbow":      1.8,
    "heavy crossbow": 2.2,
    "throwing dagger": 0.6,
    "throwing axe":   0.9,
    "javelin":        1.1,
}

# Ammo types required per weapon category
WEAPON_AMMO_MAP = {
    "shortbow":      "arrow",
    "bow":           "arrow",
    "longbow":       "arrow",
    "crossbow":      "bolt",
    "heavy crossbow": "bolt",
}

# Thrown weapons don't use ammo but have retrieval chance
THROWN_WEAPONS = {"throwing dagger", "throwing axe", "javelin"}

# Chance to recover ammo from a corpse after combat (per shot fired)
AMMO_RECOVERY_CHANCE = 0.40  # 40% per arrow/bolt

# Chance to retrieve a thrown weapon after combat
THROWN_RETRIEVAL_CHANCE = 0.75  # 75%

# Range attack cooldown in seconds (prevents spam)
RANGED_ATTACK_COOLDOWN = 3.0

# DEX modifier for ranged accuracy (percentage of DEX added to hit roll)
DEX_ACCURACY_MOD = 0.5

# DEX modifier for ranged damage (percentage of DEX added to damage)
DEX_DAMAGE_MOD = 0.3

# Minimum distance for ranged advantage (rooms away — 0 = same room)
# In same-room combat, ranged gets a first-strike bonus
RANGED_FIRST_STRIKE_BONUS = 15  # +15 to hit on first ranged attack


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def is_ranged_weapon(obj):
    """
    Check if an object is a ranged weapon (bow, crossbow, or thrown).
    """
    if not obj:
        return False
    weapon_type = obj.attributes.get("weapon_type", default="") if hasattr(obj, "attributes") else ""
    if not weapon_type:
        weapon_type = obj.db.weapon_type if hasattr(obj, "db") else ""
    return weapon_type in RANGED_WEAPON_DAMAGE or weapon_type in WEAPON_AMMO_MAP


def is_bow(obj):
    """Check if an object is a bow-type weapon (requires arrows)."""
    if not obj:
        return False
    weapon_type = obj.attributes.get("weapon_type", default="") if hasattr(obj, "attributes") else ""
    if not weapon_type:
        weapon_type = obj.db.weapon_type if hasattr(obj, "db") else ""
    return weapon_type in WEAPON_AMMO_MAP


def is_crossbow(obj):
    """Check if an object is a crossbow-type weapon (requires bolts)."""
    if not obj:
        return False
    weapon_type = obj.attributes.get("weapon_type", default="") if hasattr(obj, "attributes") else ""
    if not weapon_type:
        weapon_type = obj.db.weapon_type if hasattr(obj, "db") else ""
    return weapon_type in ("crossbow", "heavy crossbow")


def is_thrown_weapon(obj):
    """Check if an object is a thrown weapon."""
    if not obj:
        return False
    weapon_type = obj.attributes.get("weapon_type", default="") if hasattr(obj, "attributes") else ""
    if not weapon_type:
        weapon_type = obj.db.weapon_type if hasattr(obj, "db") else ""
    return weapon_type in THROWN_WEAPONS


def get_ranged_weapon(character):
    """
    Find the equipped ranged weapon on a character.
    Returns (weapon_obj, weapon_type) or (None, None).
    Checks wielded items first, then inventory.
    """
    if not character:
        return None, None

    # Check wielded items (equipment slots)
    for obj in character.contents:
        if not obj or hasattr(obj, "destination") and obj.destination:
            continue
        weapon_type = ""
        if hasattr(obj, "attributes"):
            weapon_type = obj.attributes.get("weapon_type", default="")
        if not weapon_type and hasattr(obj, "db"):
            weapon_type = obj.db.weapon_type or ""
        if weapon_type in RANGED_WEAPON_DAMAGE:
            return obj, weapon_type

    # Check equipment slots
    try:
        from world.mob_equipment import get_equipped_weapon
        weapon = get_equipped_weapon(character)
        if weapon:
            weapon_type = ""
            if hasattr(weapon, "attributes"):
                weapon_type = weapon.attributes.get("weapon_type", default="")
            if not weapon_type and hasattr(weapon, "db"):
                weapon_type = weapon.db.weapon_type or ""
            if weapon_type in RANGED_WEAPON_DAMAGE:
                return weapon, weapon_type
    except Exception:
        pass

    return None, None


def count_ammo(character, ammo_type):
    """
    Count how many units of ammo a character has in their inventory.
    Ammo items are identified by item_type='ammo' and matching ammo_type attribute.
    """
    if not character:
        return 0

    total = 0
    for obj in character.contents:
        if not obj or (hasattr(obj, "destination") and obj.destination):
            continue
        item_type = ""
        obj_ammo_type = ""
        if hasattr(obj, "attributes"):
            item_type = obj.attributes.get("item_type", default="")
            obj_ammo_type = obj.attributes.get("ammo_type", default="")
        if not item_type and hasattr(obj, "db"):
            item_type = obj.db.item_type or ""
            obj_ammo_type = obj.db.ammo_type or ""

        if item_type == "ammo" and obj_ammo_type == ammo_type:
            # Check quantity stack
            qty = 1
            if hasattr(obj, "attributes"):
                qty = obj.attributes.get("quantity", default=1)
            elif hasattr(obj, "db"):
                qty = obj.db.quantity or 1
            total += qty

    return total


def consume_ammo(character, ammo_type, amount=1):
    """
    Remove ammo from the character's inventory.
    Returns True if ammo was successfully consumed, False if insufficient.
    """
    if not character:
        return False

    remaining = amount
    for obj in list(character.contents):
        if remaining <= 0:
            break
        if not obj or (hasattr(obj, "destination") and obj.destination):
            continue
        item_type = ""
        obj_ammo_type = ""
        if hasattr(obj, "attributes"):
            item_type = obj.attributes.get("item_type", default="")
            obj_ammo_type = obj.attributes.get("ammo_type", default="")
        if not item_type and hasattr(obj, "db"):
            item_type = obj.db.item_type or ""
            obj_ammo_type = obj.db.ammo_type or ""

        if item_type == "ammo" and obj_ammo_type == ammo_type:
            qty = 1
            if hasattr(obj, "attributes"):
                qty = obj.attributes.get("quantity", default=1)
            elif hasattr(obj, "db"):
                qty = obj.db.quantity or 1

            if qty <= remaining:
                # Consume entire stack
                remaining -= qty
                obj.delete()
            else:
                # Reduce stack
                new_qty = qty - remaining
                if hasattr(obj, "attributes"):
                    obj.attributes.add("quantity", new_qty)
                if hasattr(obj, "db"):
                    obj.db.quantity = new_qty
                remaining = 0

    return remaining == 0


def get_ammo_type_for_weapon(weapon_type):
    """Return the ammo type required for a given weapon type."""
    return WEAPON_AMMO_MAP.get(weapon_type, "")


def calculate_ranged_damage(attacker, weapon_type):
    """
    Calculate ranged attack damage based on weapon type, DEX, and bonuses.

    Returns (min_damage, max_damage) tuple.
    """
    if not attacker:
        return 1, 4

    # Base damage from weapon type
    base_mult = RANGED_WEAPON_DAMAGE.get(weapon_type, 1.0)

    # Get attacker stats
    dex = attacker.attributes.get("dexterity", default=10) if hasattr(attacker, "attributes") else 10
    level = attacker.attributes.get("level", default=1) if hasattr(attacker, "attributes") else 1

    # Base damage scales with level and DEX
    base_min = int(2 + level * 0.5 + dex * DEX_DAMAGE_MOD)
    base_max = int(5 + level * 1.0 + dex * DEX_DAMAGE_MOD * 1.5)

    # Apply weapon multiplier
    min_dmg = max(1, int(base_min * base_mult))
    max_dmg = max(min_dmg + 1, int(base_max * base_mult))

    # Apply racial bonuses
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(attacker)
        dmg_pct = racial.get("ranged_dmg_pct", racial.get("melee_dmg_pct", 0))
        if dmg_pct:
            min_dmg = int(min_dmg * (1.0 + dmg_pct / 100.0))
            max_dmg = int(max_dmg * (1.0 + dmg_pct / 100.0))
    except Exception:
        pass

    # Apply talent bonuses
    try:
        from world.skill_tree import get_talent_bonuses
        talents = get_talent_bonuses(attacker)
        talent_dmg = talents.get("ranged_damage", talents.get("melee_damage", 0))
        if talent_dmg:
            min_dmg += talent_dmg
            max_dmg += talent_dmg
    except Exception:
        pass

    return max(1, min_dmg), max(min_dmg + 1, max_dmg)


def calculate_ranged_hit_chance(attacker, target):
    """
    Calculate the chance to hit with a ranged attack.
    Uses DEX instead of STR for accuracy.

    Returns a float 0.0-1.0 representing hit probability.
    """
    if not attacker or not target:
        return 0.5

    attacker_dex = attacker.attributes.get("dexterity", default=10) if hasattr(attacker, "attributes") else 10
    attacker_level = attacker.attributes.get("level", default=1) if hasattr(attacker, "attributes") else 1
    target_level = target.attributes.get("level", default=1) if hasattr(target, "attributes") else 1
    target_ac = target.attributes.get("armor_class", default=10) if hasattr(target, "attributes") else 10

    # Base hit chance: 60% + DEX bonus - target AC penalty
    base_chance = 0.60
    dex_bonus = (attacker_dex - 10) * 0.02  # ±2% per DEX point above/below 10
    level_bonus = (attacker_level - target_level) * 0.01  # ±1% per level difference
    ac_penalty = max(0, (target_ac - 10) * 0.005)  # -0.5% per AC above 10

    hit_chance = base_chance + dex_bonus + level_bonus - ac_penalty

    # Apply racial bonuses
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(attacker)
        crit_pct = racial.get("crit_chance_pct", 0)
        if crit_pct:
            hit_chance += crit_pct / 100.0 * 0.5  # Half of crit bonus applies to hit
    except Exception:
        pass

    # Apply talent bonuses
    try:
        from world.skill_tree import get_talent_bonuses
        talents = get_talent_bonuses(attacker)
        thac0 = talents.get("thac0_bonus", 0)
        if thac0:
            hit_chance += thac0 / 100.0
    except Exception:
        pass

    # Clamp to valid range
    return max(0.05, min(0.95, hit_chance))


def perform_ranged_attack(attacker, target, weapon_obj=None, weapon_type=None):
    """
    Execute a single ranged attack.

    Args:
        attacker: The character performing the attack.
        target: The target being attacked.
        weapon_obj: The ranged weapon object (optional, auto-detected if None).
        weapon_type: The weapon type string (optional, auto-detected if None).

    Returns:
        dict with keys: hit (bool), damage (int), message (str), ammo_used (bool),
                        crit (bool), weapon_type (str)
    """
    result = {
        "hit": False,
        "damage": 0,
        "message": "",
        "ammo_used": False,
        "crit": False,
        "weapon_type": weapon_type or "unknown",
    }

    if not attacker or not target:
        result["message"] = "Invalid attacker or target."
        return result

    # Auto-detect weapon if not provided
    if weapon_obj is None or weapon_type is None:
        weapon_obj, weapon_type = get_ranged_weapon(attacker)

    if weapon_type is None:
        result["message"] = "You don't have a ranged weapon equipped."
        return result

    result["weapon_type"] = weapon_type

    # Check ammo for bows/crossbows
    ammo_type = get_ammo_type_for_weapon(weapon_type)
    if ammo_type:
        ammo_count = count_ammo(attacker, ammo_type)
        if ammo_count <= 0:
            result["message"] = f"You don't have any {ammo_type}s! You need ammo to use a {weapon_type}."
            return result

    # Check if target is valid
    if target == attacker:
        result["message"] = "You can't shoot yourself!"
        return result

    # Check if target is in the same room
    if target.location != attacker.location:
        result["message"] = "Your target is not here."
        return result

    # Check safe zone
    if attacker.location and attacker.location.attributes.get("safe_zone", False):
        result["message"] = "You cannot attack in a safe zone."
        return result

    # Check PvP permissions
    if hasattr(target, "has_account") and target.has_account:
        try:
            from world.combat import _is_pvp_allowed
            allowed, reason = _is_pvp_allowed(attacker, target)
            if not allowed:
                result["message"] = reason
                return result
        except Exception:
            pass

    # Check if target is already dead
    target_hp = target.attributes.get("hp", default=0) if hasattr(target, "attributes") else 0
    if target_hp <= 0:
        result["message"] = f"{target.key} is already dead."
        return result

    # Calculate hit chance
    hit_chance = calculate_ranged_hit_chance(attacker, target)

    # First-strike bonus (if target isn't already in combat with attacker)
    in_combat = False
    try:
        from world.tick_combat import CombatHandler
        combat_target = CombatHandler.get_target(attacker)
        if combat_target and combat_target == target:
            in_combat = True
    except Exception:
        pass

    if not in_combat:
        hit_chance += RANGED_FIRST_STRIKE_BONUS / 100.0

    # Roll to hit
    roll = random.random()
    if roll > hit_chance:
        # Miss
        result["message"] = f"Your {weapon_type} shot at {target.key} misses!"
        # Still consume ammo on miss
        if ammo_type:
            consume_ammo(attacker, ammo_type, 1)
            result["ammo_used"] = True
        return result

    # Hit! Calculate damage
    min_dmg, max_dmg = calculate_ranged_damage(attacker, weapon_type)
    damage = random.randint(min_dmg, max_dmg)

    # Check for critical hit (natural 20-style, 5% chance + bonuses)
    crit_chance = 0.05
    try:
        from world.rules import get_racial_bonuses
        racial = get_racial_bonuses(attacker)
        crit_chance += racial.get("crit_chance_pct", 0) / 100.0
    except Exception:
        pass

    try:
        from world.skill_tree import get_talent_bonuses
        talents = get_talent_bonuses(attacker)
        crit_chance += talents.get("crit_chance_pct", 0) / 100.0
    except Exception:
        pass

    is_crit = random.random() < crit_chance
    if is_crit:
        damage = int(damage * 1.5)
        result["crit"] = True

    # Apply damage to target
    try:
        from world.combat import _get_effective_hp, _set_effective_hp, _reduce_shield
        # Check shield absorption
        remaining, absorbed = _reduce_shield(target, damage)
        if absorbed > 0:
            damage = remaining
        current_hp = _get_effective_hp(target)
        new_hp = max(0, current_hp - damage)
        _set_effective_hp(target, new_hp)
    except Exception:
        # Fallback direct HP manipulation
        current_hp = target.attributes.get("hp", default=100) if hasattr(target, "attributes") else 100
        new_hp = max(0, current_hp - damage)
        if hasattr(target, "attributes"):
            target.attributes.add("hp", new_hp)

    result["hit"] = True
    result["damage"] = damage

    # Build message
    crit_text = " |r*CRITICAL*|n" if is_crit else ""
    result["message"] = (
        f"Your {weapon_type} shot hits {target.key} for |r{damage} damage|n!{crit_text}"
    )

    # Consume ammo
    if ammo_type:
        consume_ammo(attacker, ammo_type, 1)
        result["ammo_used"] = True

    # For thrown weapons, remove the weapon from inventory
    if weapon_type in THROWN_WEAPONS and weapon_obj:
        # Move thrown weapon to the room (can be retrieved)
        if attacker.location:
            weapon_obj.location = attacker.location
            result["message"] += f" Your {weapon_type} clatters to the ground."

    # Check if target died
    if new_hp <= 0:
        try:
            from world.combat import _handle_defeat
            _handle_defeat(target, attacker)
        except Exception as err:
            logger.log_err(f"perform_ranged_attack: _handle_defeat failed: {err}")

    return result


def recover_ammo_from_corpse(character, corpse):
    """
    After combat, attempt to recover some ammo from a corpse.
    Called automatically when looting.

    Returns number of ammo recovered.
    """
    if not character or not corpse:
        return 0

    recovered = 0

    # Check for arrows
    arrow_count = corpse.attributes.get("arrows_fired", default=0) if hasattr(corpse, "attributes") else 0
    if arrow_count > 0:
        recovered_arrows = sum(1 for _ in range(arrow_count) if random.random() < AMMO_RECOVERY_CHANCE)
        if recovered_arrows > 0:
            # Create arrow items in character's inventory
            try:
                from evennia import create_object
                from evennia.objects.objects import DefaultObject
                arrow_obj = create_object(
                    DefaultObject,
                    key="arrow",
                    location=character,
                    attributes=[
                        ("item_type", "ammo"),
                        ("ammo_type", "arrow"),
                        ("quantity", recovered_arrows),
                        ("weight", 0.1),
                        ("value", 1),
                    ],
                )
                recovered += recovered_arrows
            except Exception:
                pass

    # Check for bolts
    bolt_count = corpse.attributes.get("bolts_fired", default=0) if hasattr(corpse, "attributes") else 0
    if bolt_count > 0:
        recovered_bolts = sum(1 for _ in range(bolt_count) if random.random() < AMMO_RECOVERY_CHANCE)
        if recovered_bolts > 0:
            try:
                from evennia import create_object
                from evennia.objects.objects import DefaultObject
                bolt_obj = create_object(
                    DefaultObject,
                    key="bolt",
                    location=character,
                    attributes=[
                        ("item_type", "ammo"),
                        ("ammo_type", "bolt"),
                        ("quantity", recovered_bolts),
                        ("weight", 0.15),
                        ("value", 1),
                    ],
                )
                recovered += recovered_bolts
            except Exception:
                pass

    return recovered


def track_ammo_fired(corpse, ammo_type, count=1):
    """Track how many arrows/bolts were fired into a corpse for recovery."""
    if not corpse:
        return
    if ammo_type == "arrow":
        current = corpse.attributes.get("arrows_fired", default=0) if hasattr(corpse, "attributes") else 0
        if hasattr(corpse, "attributes"):
            corpse.attributes.add("arrows_fired", current + count)
    elif ammo_type == "bolt":
        current = corpse.attributes.get("bolts_fired", default=0) if hasattr(corpse, "attributes") else 0
        if hasattr(corpse, "attributes"):
            corpse.attributes.add("bolts_fired", current + count)


# ---------------------------------------------------------------------------
# Ranged Combat Handler (tick-based integration)
# ---------------------------------------------------------------------------

class RangedCombatHandler:
    """
    Handler for managing ranged combat state on a character.

    Tracks:
      - Whether the character is using ranged combat mode
      - Last ranged attack timestamp (cooldown)
      - Preferred ranged weapon
    """

    @staticmethod
    def is_in_ranged_mode(character):
        """Check if character is in ranged combat mode."""
        if not character:
            return False
        return character.attributes.get("ranged_mode", default=False) if hasattr(character, "attributes") else False

    @staticmethod
    def set_ranged_mode(character, enabled=True):
        """Enable or disable ranged combat mode."""
        if not character:
            return
        if hasattr(character, "attributes"):
            character.attributes.add("ranged_mode", enabled)

    @staticmethod
    def get_last_ranged_attack(character):
        """Get timestamp of last ranged attack."""
        if not character:
            return 0
        return character.attributes.get("last_ranged_attack", default=0) if hasattr(character, "attributes") else 0

    @staticmethod
    def set_last_ranged_attack(character, timestamp=None):
        """Record a ranged attack timestamp."""
        if not character:
            return
        if timestamp is None:
            timestamp = time.time()
        if hasattr(character, "attributes"):
            character.attributes.add("last_ranged_attack", timestamp)

    @staticmethod
    def can_ranged_attack(character):
        """Check if enough time has passed since last ranged attack."""
        last = RangedCombatHandler.get_last_ranged_attack(character)
        return (time.time() - last) >= RANGED_ATTACK_COOLDOWN

    @staticmethod
    def get_ranged_target(character):
        """Get the current ranged attack target."""
        if not character:
            return None
        target_dbref = character.attributes.get("ranged_target", default=None) if hasattr(character, "attributes") else None
        if target_dbref:
            try:
                from evennia.objects.models import ObjectDB
                return ObjectDB.objects.filter(id=target_dbref).first()
            except Exception:
                return None
        return None

    @staticmethod
    def set_ranged_target(character, target):
        """Set the current ranged attack target."""
        if not character:
            return
        if hasattr(character, "attributes"):
            if target:
                character.attributes.add("ranged_target", target.id)
            else:
                character.attributes.add("ranged_target", None)

    @staticmethod
    def tick_ranged_combat(character):
        """
        Called each combat tick for characters in ranged mode.
        Automatically fires at the ranged target if available.
        """
        if not character:
            return

        if not RangedCombatHandler.is_in_ranged_mode(character):
            return

        if not RangedCombatHandler.can_ranged_attack(character):
            return

        target = RangedCombatHandler.get_ranged_target(character)
        if not target:
            RangedCombatHandler.set_ranged_mode(character, False)
            return

        # Check target is still valid
        if target.location != character.location:
            character.msg(f"|yYour ranged target {target.key} is no longer here.|n")
            RangedCombatHandler.set_ranged_target(character, None)
            RangedCombatHandler.set_ranged_mode(character, False)
            return

        target_hp = target.attributes.get("hp", default=0) if hasattr(target, "attributes") else 0
        if target_hp <= 0:
            RangedCombatHandler.set_ranged_target(character, None)
            RangedCombatHandler.set_ranged_mode(character, False)
            return

        # Perform the ranged attack
        result = perform_ranged_attack(character, target)
        RangedCombatHandler.set_last_ranged_attack(character)

        # Send messages
        character.msg(f"|c[Ranged]|n {result['message']}")
        if result["hit"] and character.location:
            character.location.msg_contents(
                f"|c{character.key} fires a {result['weapon_type']} at {target.key} "
                f"for {result['damage']} damage!|n",
                exclude=[character, target],
            )
            if target.has_account:
                target.msg(
                    f"|r{character.key} shoots you with a {result['weapon_type']} "
                    f"for {result['damage']} damage!|n"
                )

        # Check ammo after attack
        weapon_obj, weapon_type = get_ranged_weapon(character)
        if weapon_type:
            ammo_type = get_ammo_type_for_weapon(weapon_type)
            if ammo_type:
                remaining = count_ammo(character, ammo_type)
                if remaining <= 0:
                    character.msg(f"|yYou are out of {ammo_type}s! Switching to melee.|n")
                    RangedCombatHandler.set_ranged_mode(character, False)
                    # Fall back to melee combat
                    try:
                        from world.tick_combat import CombatHandler
                        CombatHandler.start_combat(character, target)
                    except Exception:
                        pass
                elif remaining <= 5:
                    character.msg(f"|yLow ammo warning: only {remaining} {ammo_type}(s) remaining.|n")


# ---------------------------------------------------------------------------
# Ammo creation helper (for shops / loot)
# ---------------------------------------------------------------------------

def create_ammo_stack(ammo_type, quantity=20, location=None):
    """
    Create a stack of ammo items.

    Args:
        ammo_type: "arrow" or "bolt"
        quantity: Number of ammo in the stack
        location: Where to place the ammo (character, room, or None)

    Returns:
        The created ammo object, or None on failure.
    """
    try:
        from evennia import create_object
        from evennia.objects.objects import DefaultObject

        ammo_names = {
            "arrow": "a bundle of arrows",
            "bolt": "a bundle of bolts",
        }
        ammo_descs = {
            "arrow": "A bundle of wooden arrows with iron tips.",
            "bolt": "A bundle of metal crossbow bolts.",
        }

        name = ammo_names.get(ammo_type, f"a bundle of {ammo_type}s")
        desc = ammo_descs.get(ammo_type, f"A bundle of {ammo_type} ammunition.")

        ammo_obj = create_object(
            DefaultObject,
            key=name,
            location=location,
            attributes=[
                ("desc", desc),
                ("item_type", "ammo"),
                ("ammo_type", ammo_type),
                ("quantity", quantity),
                ("weight", 0.1 if ammo_type == "arrow" else 0.15),
                ("value", max(1, quantity // 5)),
            ],
        )
        return ammo_obj
    except Exception as err:
        logger.log_err(f"create_ammo_stack: failed to create {ammo_type}: {err}")
        return None


def create_ranged_weapon(weapon_type, location=None):
    """
    Create a ranged weapon object.

    Args:
        weapon_type: One of "shortbow", "bow", "longbow", "crossbow", "heavy crossbow"
        location: Where to place the weapon

    Returns:
        The created weapon object, or None on failure.
    """
    try:
        from evennia import create_object
        from evennia.objects.objects import DefaultObject

        weapon_data = {
            "shortbow": {
                "name": "a shortbow",
                "desc": "A compact hunting bow, easy to handle.",
                "damage": 4,
                "value": 25,
                "weight": 3,
                "level": 1,
            },
            "bow": {
                "name": "a bow",
                "desc": "A standard wooden bow.",
                "damage": 6,
                "value": 50,
                "weight": 4,
                "level": 5,
            },
            "longbow": {
                "name": "a longbow",
                "desc": "A tall yew longbow with excellent range and power.",
                "damage": 9,
                "value": 120,
                "weight": 5,
                "level": 15,
            },
            "crossbow": {
                "name": "a crossbow",
                "desc": "A mechanical crossbow that fires bolts with deadly force.",
                "damage": 11,
                "value": 200,
                "weight": 6,
                "level": 20,
            },
            "heavy crossbow": {
                "name": "a heavy crossbow",
                "desc": "A massive steel crossbow. Slow to reload but devastating.",
                "damage": 15,
                "value": 400,
                "weight": 10,
                "level": 35,
            },
        }

        data = weapon_data.get(weapon_type)
        if not data:
            return None

        weapon = create_object(
            DefaultObject,
            key=data["name"],
            location=location,
            attributes=[
                ("desc", data["desc"]),
                ("item_type", "weapon"),
                ("weapon_type", weapon_type),
                ("damage", data["damage"]),
                ("value", data["value"]),
                ("weight", data["weight"]),
                ("level_required", data["level"]),
                ("equip_slot", "wield"),
            ],
        )
        return weapon
    except Exception as err:
        logger.log_err(f"create_ranged_weapon: failed to create {weapon_type}: {err}")
        return None