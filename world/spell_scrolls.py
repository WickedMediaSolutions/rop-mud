"""
Spell Scrolls & Consumable Magic Items — Phase 7

Provides:
  - Scroll prototype generation for any spell
  - Scroll use logic (cast spell without mana, class gating)
  - Consumable charging into inventory
  - Integration with item prototypes and loot

A scroll is a single-use magic item that casts a stored spell when read.
Scrolls bypass mana requirements but still respect:
  - Target requirements
  - Spell level vs caster level for effectiveness (scales to reader's level)
  - Race/class spell restrictions (unless marked as a "universal" scroll)
"""

import time
from evennia.utils import search


# ---------------------------------------------------------------------------
# Scroll Generation
# ---------------------------------------------------------------------------

SCROLL_PREFIX = "Scroll of"


def create_scroll_item(spell_name, scroll_level=None, universal=False):
    """
    Create a scroll item definition for a given spell.
    Returns a dict suitable for evennia create_object or a loot table entry.

    Args:
        spell_name: The spell the scroll contains (e.g. "Fireball")
        scroll_level: Optional fixed caster level for the spell. If None,
                      the scroll scales to the reader's level.
        universal: If True, any class can use this scroll regardless of
                   race/class spell restrictions.
    """
    from world.spells import get_spell

    spell = get_spell(spell_name)
    if not spell:
        return None

    scroll_key = f"scrollof{spell['key']}"

    return {
        "key": f"{SCROLL_PREFIX} {spell['name']}",
        "typeclass": "typeclasses.objects.Object",
        "db": {
            "item_type": "scroll",
            "spell_key": spell["key"],
            "spell_name": spell["name"],
            "scroll_level": scroll_level or 0,
            "universal_scroll": universal,
            "value": max(10, spell["level"] * 5),
            "weight": 0.1,
            "desc": (
                f"A scroll inscribed with the spell '{spell['name']}'. "
                f"Reading it aloud will cast the spell once, consuming the scroll. "
                f"{'Usable by any class.' if universal else 'Requires the appropriate casting class.'}"
            ),
        },
    }


def create_scroll_object(spell_name, caller=None, scroll_level=None, universal=False):
    """
    Create and return an actual scroll object in the game world.

    Args:
        spell_name: The spell the scroll contains.
        caller: The account/object creating the scroll (for location).
        scroll_level: Optional fixed caster level.
        universal: If True, bypasses class restrictions.
    """
    from evennia.utils.create import create_object

    item_def = create_scroll_item(spell_name, scroll_level, universal)
    if not item_def:
        return None

    location = caller.location if caller else None
    scroll = create_object(
        item_def["typeclass"],
        key=item_def["key"],
        location=location,
    )

    for attr, value in item_def["db"].items():
        scroll.attributes.add(attr, value)

    return scroll


# ---------------------------------------------------------------------------
# Scroll Use Logic
# ---------------------------------------------------------------------------

def can_use_scroll(character, scroll) -> tuple:
    """
    Check if a character can use a scroll.
    Returns (allowed: bool, reason: str).
    """
    if not hasattr(scroll, "attributes"):
        return False, "That is not a valid scroll."

    scroll_item_type = scroll.attributes.get("item_type", "")
    if scroll_item_type != "scroll":
        return False, "That is not a spell scroll."

    spell_key = scroll.attributes.get("spell_key", "")
    if not spell_key:
        return False, "This scroll is blank."

    from world.spells import get_spell
    spell = get_spell(spell_key)
    if not spell:
        return False, "This scroll contains an unknown spell."

    # Universal scrolls bypass class restrictions
    universal = scroll.attributes.get("universal_scroll", False)
    if not universal:
        from world.race_class_matrix import can_learn_spell
        allowed, reason = can_learn_spell(character, spell_key)
        if not allowed:
            return False, f"You cannot use this scroll: {reason}"

    # Check for stunned/mez
    try:
        from world.status_effects import get_active_effects
        effects = get_active_effects(character)
        if effects and not effects.can_act():
            return False, "You are stunned and cannot read the scroll!"
    except ImportError:
        pass

    return True, ""


def use_scroll(character, scroll) -> tuple:
    """
    Use a scroll, casting the stored spell once then consuming the scroll.
    Returns (success: bool, message: str).
    """
    allowed, reason = can_use_scroll(character, scroll)
    if not allowed:
        return False, reason

    from world.spells import SpellHandler, get_spell

    spell_key = scroll.attributes.get("spell_key", "")
    spell = get_spell(spell_key)
    if not spell:
        return False, "This scroll contains an unknown spell."

    scroll_level = scroll.attributes.get("scroll_level", 0)
    fixed_level = scroll.attributes.get("scroll_level", 0)

    # Determine the effective caster level for scroll scaling
    if scroll_level > 0:
        # Fixed level scroll
        effective_level = scroll_level
    else:
        # Scale to reader's level, capped by spell level requirement
        reader_level = character.attributes.get("level", 1)
        effective_level = max(reader_level, spell["level"])

    # Temporarily grant the spell effect at the effective level
    handler = SpellHandler(character)

    # Bypass normal mana/cooldown requirements by directly executing
    # We'll call the spell execution directly rather than handler.cast()
    # to avoid mana deduction and cooldown initialization.

    # Determine target (scrolls default to self for self-target, or require target)
    target = character
    target_type = spell["target"]

    from world.spells import TARGET_SELF, TARGET_SINGLE, TARGET_AOE, TARGET_PBAOE

    # For single-target and AoE, resolve target
    if target_type in (TARGET_SINGLE, TARGET_AOE, TARGET_PBAOE):
        # For single-target, we need a target. Use current combat target if available.
        target = character.attributes.get("combat_target", None)
        if not target and target_type == TARGET_SINGLE:
            # Fall back to self (many single-target spells can self-target, e.g. heals)
            target = character

    # For AoE, the command layer handles iterating. But for scroll simplicity,
    # we resolve to self for now; the actual AoE iteration happens elsewhere.
    if target_type in (TARGET_AOE, TARGET_PBAOE):
        # Scroll AoE: apply to all valid targets in room
        return _use_aoe_scroll(character, scroll, spell, effective_level)

    # Use a temporary cast through the handler without mana/cooldown
    # Store original mana to preserve
    original_mana = character.attributes.get("mana", 0)
    original_cooldowns = character.attributes.get("spell_cooldowns", {}).copy()

    # Temporarily boost level if the scroll has a fixed level higher than the reader
    original_level = character.attributes.get("level", 1)
    if effective_level > original_level:
        character.attributes.add("level", effective_level)

    try:
        # Cast without mana check by setting mana high temporarily
        character.attributes.add("mana", 999999)
        success, msg = handler._execute_spell(spell, target, character)
        # Restore mana
        character.attributes.add("mana", original_mana)
        character.attributes.add("spell_cooldowns", original_cooldowns)
        if effective_level > original_level:
            character.attributes.add("level", original_level)
    except Exception as e:
        character.attributes.add("mana", original_mana)
        character.attributes.add("spell_cooldowns", original_cooldowns)
        if effective_level > original_level:
            character.attributes.add("level", original_level)
        return False, f"Error casting scroll: {e}"

    if not success:
        return False, msg

    # Consume the scroll
    character.msg(f"|wThe {scroll.key} crumbles to dust as its magic is spent.|n")
    if scroll.location:
        scroll.location.msg_contents(
            f"|w{character.key} reads a {scroll.key}, and it crumbles to dust.|n",
            exclude=[character]
        )
    scroll.delete()

    return True, f"You cast {spell['name']} from the scroll: {msg}"


def _use_aoe_scroll(character, scroll, spell, effective_level):
    """Handle AoE scroll usage: apply spell effect to all targets in the room."""
    from world.spells import SpellHandler

    room = character.location
    if not room:
        # Consume scroll anyway
        scroll.delete()
        return False, "You have no location to cast the scroll's spell in."

    # Target all other characters with hp in the room
    targets = [obj for obj in room.contents
               if obj != character and hasattr(obj, 'attributes') and obj.attributes.has("hp")]

    effect_type = spell["effect"].get("type", "damage")
    if effect_type == "heal":
        targets = [character] + targets

    handler = SpellHandler(character)
    original_mana = character.attributes.get("mana", 0)
    original_level = character.attributes.get("level", 1)
    character.attributes.add("mana", 999999)
    if effective_level > original_level:
        character.attributes.add("level", effective_level)

    hit_count = 0
    try:
        for tgt in targets:
            ok, msg = handler._execute_spell(spell, tgt, character)
            if ok:
                hit_count += 1
    finally:
        character.attributes.add("mana", original_mana)
        if effective_level > original_level:
            character.attributes.add("level", original_level)

    character.msg(f"|wThe {scroll.key} crumbles to dust. {spell['name']} affects {hit_count} target(s).|n")
    scroll.delete()
    return True, f"{spell['name']} hits {hit_count} target(s) from the scroll."


# ---------------------------------------------------------------------------
# Scroll Registry & Helpers
# ---------------------------------------------------------------------------

def get_all_scrollable_spells():
    """Return all spells that can be written onto scrolls."""
    from world.spells import SPELLS
    return list(SPELLS.values())


def generate_scroll_loot_entry(spell_name, chance=0.05, min_level=1):
    """
    Generate a loot table entry for a scroll.
    Returns a tuple suitable for boss_loot / mob loot tables:
        (scroll_item_def, drop_chance)
    """
    item_def = create_scroll_item(spell_name)
    if not item_def:
        return None
    return {
        "item": item_def,
        "chance": chance,
        "min_level": min_level,
    }


def generate_random_scroll(level_range=(1, 80), universal=False):
    """
    Generate a random scroll of an appropriate spell level.
    Returns a scroll item def, or None if no spells match.
    """
    import random
    from world.spells import SPELLS

    min_lvl, max_lvl = level_range
    eligible = [s for s in SPELLS.values() if min_lvl <= s["level"] <= max_lvl]
    if not eligible:
        return None

    spell = random.choice(eligible)
    scroll_level = random.randint(spell["level"], spell["level"] + 5)
    return create_scroll_item(spell["name"], scroll_level, universal)


# ---------------------------------------------------------------------------
# Scroll Command Helper (for commands integration)
# ---------------------------------------------------------------------------

def handle_read_scroll(character, scroll_name):
    """
    Handle the 'read' command for a scroll in the character's inventory.
    Resolves the scroll by name, then uses it.
    """
    scroll = character.search(scroll_name, location=character)
    if not scroll:
        return False, f"You don't have '{scroll_name}'."

    # If search returned a list, take first
    if isinstance(scroll, list):
        scroll = scroll[0]

    return use_scroll(character, scroll)


def handle_inscribe_scroll(character, spell_name):
    """
    Handle the 'inscribe' command: create a scroll from a known spell.
    Requires the character to be able to cast the spell.
    Costs gold based on spell level.
    """
    from world.spells import get_spell

    spell = get_spell(spell_name)
    if not spell:
        return False, f"Unknown spell: '{spell_name}'."

    # Check class gating
    from world.race_class_matrix import can_learn_spell
    allowed, reason = can_learn_spell(character, spell_name)
    if not allowed:
        return False, f"You cannot inscribe this spell: {reason}"

    # Cost: spell level * 50 gold (in copper)
    cost_copper = spell["level"] * 50
    copper = character.attributes.get("copper", 0)

    if copper < cost_copper:
        return False, f"Inscribing a scroll of {spell['name']} costs {cost_copper} copper."

    # Deduct cost
    character.attributes.add("copper", copper - cost_copper)

    # Create scroll
    scroll = create_scroll_object(spell_name, caller=character, scroll_level=character.attributes.get("level", 1))
    if not scroll:
        # Refund on failure
        character.attributes.add("copper", copper)
        return False, "Failed to create the scroll."

    # Move to character inventory
    scroll.location = character

    character.msg(f"|gYou inscribe a scroll of |w{spell['name']}|g for {cost_copper} copper.|n")
    if character.location:
        character.location.msg_contents(
            f"|g{character.key} inscribes a scroll of {spell['name']}.|n",
            exclude=[character]
        )

    return True, f"Created {SCROLL_PREFIX} {spell['name']}."