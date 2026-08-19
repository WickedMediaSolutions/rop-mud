"""
Combat Skills System for 'rop' — Physical Combat Arts

Provides:
  - COMBAT_SKILLS registry (kick, bash, backstab, disarm)
  - Skill execution integrated with CombatEngine auto-attack rounds
  - Stamina resource tracking
  - Skill cooldown tracking
  - CmdKick, CmdBash, CmdBackstab, CmdDisarm commands
  - Stealth system: hide/unhide with DEX skill check, cooldown, duration,
    room messages, auto-break on movement/spells/attacks
  - Stun application on kick/bash
  - Disarm drops weapon object into the room (not vanished)
"""

import random
import time
from world.damage_formulas import DamageType

# ---------------------------------------------------------------------------
# Stealth Constants
# ---------------------------------------------------------------------------

STEALTH_COOLDOWN = 30          # seconds before re-hiding
STEALTH_MAX_DURATION = 300     # 5 minutes max stealth
STEALTH_BASE_CHANCE = 0.40     # base hide success at DEX 10
STEALTH_DEX_SCALING = 0.04     # +4% per DEX above 10
STEALTH_MIN_CHANCE = 0.15
STEALTH_MAX_CHANCE = 0.90

# ---------------------------------------------------------------------------
# Skill Registry
# ---------------------------------------------------------------------------

COMBAT_SKILLS = {
    "kick": {
        "name": "Kick",
        "classes": ["Warrior", "Monk", "Rogue", "Ranger"],
        "min_level": 1,
        "cooldown": 8,
        "damage_mult": 1.3,
        "damage_type": DamageType.BLUNT,
        "stun_chance": 0.10,
        "stun_duration": 3.0,
        "mana_cost": 0,
        "stamina_cost": 10,
        # Phase 2.3: talent gating — requires Weapon Specialist rank 1
        "talent_prereq": "weapon_specialist",
        "talent_rank": 1,
    },
    "bash": {
        "name": "Bash",
        "classes": ["Warrior", "Paladin"],
        "min_level": 5,
        "cooldown": 12,
        "damage_mult": 1.5,
        "damage_type": DamageType.BLUNT,
        "stun_chance": 0.25,
        "stun_duration": 4.0,
        "mana_cost": 0,
        "stamina_cost": 20,
        # Phase 2.3: talent gating — requires Weapon Specialist rank 3
        "talent_prereq": "weapon_specialist",
        "talent_rank": 3,
    },
    "backstab": {
        "name": "Backstab",
        "classes": ["Rogue"],
        "min_level": 3,
        "cooldown": 15,
        "damage_mult": 2.5,
        "damage_type": DamageType.PIERCE,
        "requires_stealth": True,
        "stealth_bonus_mult": 1.5,  # Extra 50% if stealthed
        "mana_cost": 0,
        "stamina_cost": 25,
        # Phase 2.3: talent gating — requires Dodge rank 2
        "talent_prereq": "dodge",
        "talent_rank": 2,
    },
    "disarm": {
        "name": "Disarm",
        "classes": ["Warrior", "Rogue", "Monk"],
        "min_level": 8,
        "cooldown": 20,
        "damage_mult": 0.5,
        "damage_type": DamageType.SLASH,
        "disarm_chance": 0.30,
        "mana_cost": 0,
        "stamina_cost": 15,
        # Phase 2.3: talent gating — requires Iron Grip rank 1
        "talent_prereq": "iron_grip",
        "talent_rank": 1,
    },
}


# ---------------------------------------------------------------------------
# Skill Execution
# ---------------------------------------------------------------------------

def execute_skill_attack(character, target, skill_name: str) -> str:
    """
    Execute a special physical skill within the combat round.
    Returns a message string describing the result.

    Called by CombatEngine._execute_skill_round() during auto-attack ticks.
    Also callable directly from command handlers for immediate execution.
    """
    from world.tick_combat import _roll_attack_hit, _get_weapon_damage, _apply_damage_to_target, _is_alive, CombatHandler

    skill = COMBAT_SKILLS.get(skill_name)
    if not skill:
        return "Unknown skill."

    # Check class permission
    from world.race_class_matrix import can_use_skill
    allowed, reason = can_use_skill(character, skill_name)
    if not allowed:
        return reason

    # Phase 2.3: Check talent prerequisite (skill tree gating)
    talent_prereq = skill.get("talent_prereq")
    talent_rank = skill.get("talent_rank", 0)
    if talent_prereq and talent_rank > 0:
        try:
            from world.skill_tree import _get_session, TALENT_DEFINITIONS
            session = _get_session(character)
            current_rank = session.talents.get(talent_prereq, 0)
            if current_rank < talent_rank:
                talent_name = TALENT_DEFINITIONS.get(talent_prereq, {}).get("name", talent_prereq)
                return f"You need {talent_name} rank {talent_rank} to use {skill['name']} (you have rank {current_rank})."
        except Exception:
            pass

    # Check level
    char_level = character.attributes.get("level", 1) if hasattr(character, "attributes") else 1
    if char_level < skill["min_level"]:
        return f"You must be level {skill['min_level']} to use {skill['name']}."

    # Check stamina
    stamina = character.attributes.get("stamina", default=100) if hasattr(character, "attributes") else 100
    if stamina < skill["stamina_cost"]:
        return f"Not enough stamina for {skill['name']} (need {skill['stamina_cost']}, have {stamina})."

    # Check cooldown
    cooldowns = character.attributes.get("skill_cooldowns", {}) if hasattr(character, "attributes") else {}
    remaining = cooldowns.get(skill_name, 0) - time.time()
    if remaining > 0:
        return f"{skill['name']} is on cooldown for {int(remaining)}s."

    # Check stealth requirement for backstab
    if skill.get("requires_stealth", False):
        is_stealthed = character.attributes.get("stealthed", False) if hasattr(character, "attributes") else False
        if not is_stealthed:
            return "You must be hidden to backstab."

    # Deduct stamina
    if hasattr(character, "attributes"):
        character.attributes.add("stamina", stamina - skill["stamina_cost"])

    # Hit roll
    if not _roll_attack_hit(character, target):
        return f"Your {skill['name']} misses {target.key}!"

    # Damage calculation with skill multiplier
    weapon_dmg = _get_weapon_damage(character)
    from world.damage_formulas import calculate_melee_damage
    result = calculate_melee_damage(character, target, weapon_dmg, skill["damage_type"])
    result["damage"] = int(result["damage"] * skill["damage_mult"])

    # Stealth bonus for backstab
    if skill_name == "backstab" and skill.get("requires_stealth", False):
        is_stealthed = character.attributes.get("stealthed", False) if hasattr(character, "attributes") else False
        if is_stealthed:
            stealth_mult = skill.get("stealth_bonus_mult", 1.5)
            # Racial passive: stealth efficiency (Dark Elf +15%).
            try:
                from world.rules import get_racial_bonuses
                racial = get_racial_bonuses(character)
                stealth_pct = racial.get("stealth_efficiency_pct", 0)
                if stealth_pct:
                    stealth_mult += stealth_pct / 100.0
            except Exception:
                pass
            result["damage"] = int(result["damage"] * stealth_mult)
            # Break stealth after backstab
            if hasattr(character, "attributes"):
                character.attributes.add("stealthed", False)
            character.msg("|mYou break from the shadows!|n")

    _apply_damage_to_target(character, target, result["damage"],
                            is_crit=result.get("crit", False),
                            absorbed=result.get("absorbed", 0))

    # Stun check
    if random.random() < skill.get("stun_chance", 0):
        if hasattr(target, "attributes"):
            target.attributes.add("stunned", True)
            target.msg("|mYou have been stunned!|n")
            from evennia.utils import delay
            stun_dur = skill.get("stun_duration", 3.0)
            delay(stun_dur, lambda t=target: t.attributes.add("stunned", False) if hasattr(t, "attributes") else None)

    # Disarm check — drop weapon object into the room
    if random.random() < skill.get("disarm_chance", 0):
        if hasattr(target, "attributes"):
            equipped = target.attributes.get("equipped", default={})
            weapon_slots = ["main_hand", "two_handed", "weapon", "two_hand"]
            for slot in weapon_slots:
                if slot in equipped:
                    weapon_name = equipped.pop(slot)
                    target.attributes.add("equipped", equipped)
                    target.msg(f"|mYou have been disarmed! Your {weapon_name} falls to the ground!|n")
                    character.msg(f"|gYou disarm {target.key}'s {weapon_name}!|n")

                    # Create the weapon object in the room
                    loc = getattr(target, "location", None)
                    if loc and weapon_name:
                        try:
                            from evennia import create_object
                            weapon_obj = create_object(
                                key=weapon_name,
                                typeclass="typeclasses.objects.Object",
                                location=loc,
                            )
                            if weapon_obj:
                                weapon_obj.db.desc = f"A {weapon_name} that was knocked from {target.key}'s grasp."
                                loc.msg_contents(
                                    f"|y{weapon_name} clatters to the ground!|n",
                                    exclude=[character, target],
                                )
                        except Exception:
                            pass
                    break

    # Set cooldown
    if hasattr(character, "attributes"):
        cooldowns[skill_name] = time.time() + skill["cooldown"]
        character.attributes.add("skill_cooldowns", cooldowns)

    # Check for death
    if not _is_alive(target):
        from world.tick_combat import _handle_target_death
        _handle_target_death(character, target)

    return f"You use {skill['name']} on {target.key} for {result['damage']} damage!"


# ---------------------------------------------------------------------------
# Skill Commands
# ---------------------------------------------------------------------------

from commands.command import Command
from world.tick_combat import CombatHandler


class CmdKick(Command):
    """
    Kick your combat target for bonus blunt damage. Chance to stun.

    Usage:
      kick

    Queues a kick for your next auto-attack round.  The kick deals
    130% weapon damage as blunt damage and has a 10% chance to stun
    the target for 3 seconds.
    """
    key = "kick"
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = self.caller
        if not CombatHandler.is_in_combat(caller):
            caller.msg("|yYou are not in combat.|n")
            return
        target = CombatHandler.get_target(caller)
        if not target:
            caller.msg("|yYou have no target.|n")
            return

        # Queue the skill for the next auto-attack round
        success, msg = CombatHandler.queue_skill(caller, "kick")
        if success:
            caller.msg(f"|g{msg}|n")
        else:
            caller.msg(f"|r{msg}|n")


class CmdBash(Command):
    """
    Bash your target for heavy blunt damage. High stun chance.

    Usage:
      bash

    Queues a bash for your next auto-attack round.  The bash deals
    150% weapon damage as blunt damage and has a 25% chance to stun
    the target for 4 seconds.
    """
    key = "bash"
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = self.caller
        if not CombatHandler.is_in_combat(caller):
            caller.msg("|yYou are not in combat.|n")
            return
        target = CombatHandler.get_target(caller)
        if not target:
            caller.msg("|yYou have no target.|n")
            return

        success, msg = CombatHandler.queue_skill(caller, "bash")
        if success:
            caller.msg(f"|g{msg}|n")
        else:
            caller.msg(f"|r{msg}|n")


class CmdBackstab(Command):
    """
    Backstab your target for massive piercing damage. Requires stealth.

    Usage:
      backstab

    Queues a backstab for your next auto-attack round.  The backstab
    deals 250% weapon damage as piercing damage.  If you are stealthed
    (hidden), the damage is increased by an additional 50%.

    Requires: Rogue class, level 3+, stealthed state.
    """
    key = "backstab"
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = self.caller
        if not CombatHandler.is_in_combat(caller):
            caller.msg("|yYou are not in combat.|n")
            return
        target = CombatHandler.get_target(caller)
        if not target:
            caller.msg("|yYou have no target.|n")
            return

        success, msg = CombatHandler.queue_skill(caller, "backstab")
        if success:
            caller.msg(f"|g{msg}|n")
        else:
            caller.msg(f"|r{msg}|n")


class CmdHide(Command):
    """
    Hide in the shadows, entering a stealthed state.

    Usage:
      hide

    Allows Rogues to become stealthed.  While stealthed, you can
    use the backstab skill to deal massive bonus damage.  Attacking,
    casting spells, or moving will break your stealth.

    Success is based on your DEX score.  Dark Elves receive a racial
    bonus to stealth efficiency.  Stealth lasts up to 5 minutes and
    has a 30-second cooldown after breaking.

    Requires: Rogue class.
    """

    key = "hide"
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = self.caller
        char_class = caller.attributes.get("class", "Warrior") if hasattr(caller, "attributes") else "Warrior"
        if char_class != "Rogue":
            caller.msg("|rOnly Rogues can hide in the shadows.|n")
            return

        # Already stealthed?
        if caller.attributes.get("stealthed", False) if hasattr(caller, "attributes") else False:
            caller.msg("|yYou are already hidden.|n")
            return

        # Cooldown check
        stealth_cooldowns = caller.attributes.get("stealth_cooldowns", {}) if hasattr(caller, "attributes") else {}
        remaining = stealth_cooldowns.get("hide", 0) - time.time()
        if remaining > 0:
            caller.msg(f"|yYou must wait {int(remaining)}s before hiding again.|n")
            return

        # DEX-based skill check
        dex = caller.attributes.get("stats", {}).get("dex", 10) if hasattr(caller, "attributes") else 10
        try:
            dex = int(dex)
        except (TypeError, ValueError):
            dex = 10
        chance = STEALTH_BASE_CHANCE + (dex - 10) * STEALTH_DEX_SCALING

        # Racial stealth efficiency bonus (Dark Elf +15%)
        try:
            from world.rules import get_racial_bonuses
            racial = get_racial_bonuses(caller)
            stealth_pct = racial.get("stealth_efficiency_pct", 0)
            if stealth_pct:
                chance += stealth_pct / 100.0
        except Exception:
            pass

        chance = max(STEALTH_MIN_CHANCE, min(STEALTH_MAX_CHANCE, chance))

        if random.random() > chance:
            caller.msg("|yYou attempt to hide but remain visible.|n")
            return

        if hasattr(caller, "attributes"):
            caller.attributes.add("stealthed", True)
            caller.attributes.add("stealth_expires", time.time() + STEALTH_MAX_DURATION)
        caller.msg("|mYou slip into the shadows.|n")

        # Room message (others see the rogue vanish)
        loc = getattr(caller, "location", None)
        if loc:
            loc.msg_contents(f"|m{caller.key} fades into the shadows.|n", exclude=[caller])


class CmdUnhide(Command):
    """
    Step out of the shadows, ending your stealthed state.

    Usage:
      unhide
      appear

    Voluntarily breaks your stealth.  You will be visible to everyone
    in the room and must wait 30 seconds before hiding again.
    """

    key = "unhide"
    aliases = ["appear"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = self.caller
        is_stealthed = caller.attributes.get("stealthed", False) if hasattr(caller, "attributes") else False
        if not is_stealthed:
            caller.msg("|yYou are not hidden.|n")
            return

        break_stealth(caller, reason="voluntary")
        caller.msg("|mYou step out of the shadows.|n")


def break_stealth(character, reason: str = "action") -> None:
    """
    Break stealth on a character and set the hide cooldown.

    Called whenever a stealthed character performs an action that
    should reveal them: attacking, casting a spell, moving, or
    voluntarily unhiding.

    Args:
        character: The character breaking stealth.
        reason: One of 'attack', 'spell', 'move', 'voluntary', 'action'.
    """
    if not hasattr(character, "attributes"):
        return

    was_stealthed = character.attributes.get("stealthed", False)
    if not was_stealthed:
        return

    character.attributes.add("stealthed", False)
    character.attributes.add("stealth_expires", 0)

    # Set cooldown
    stealth_cooldowns = character.attributes.get("stealth_cooldowns", {})
    stealth_cooldowns["hide"] = time.time() + STEALTH_COOLDOWN
    character.attributes.add("stealth_cooldowns", stealth_cooldowns)

    # Room message
    loc = getattr(character, "location", None)
    if loc:
        if reason == "voluntary":
            loc.msg_contents(f"|m{character.key} steps out of the shadows.|n", exclude=[character])
        elif reason == "attack":
            loc.msg_contents(f"|m{character.key} springs from the shadows!|n", exclude=[character])
        elif reason == "spell":
            loc.msg_contents(f"|m{character.key}'s spell reveals their position!|n", exclude=[character])
        elif reason == "move":
            loc.msg_contents(f"|m{character.key} emerges from the shadows as they move.|n", exclude=[character])
        else:
            loc.msg_contents(f"|m{character.key} becomes visible again.|n", exclude=[character])


class CmdDisarm(Command):
    """
    Attempt to disarm your target, forcing them to drop their weapon.

    Usage:
      disarm

    Queues a disarm for your next auto-attack round.  The disarm deals
    50% weapon damage and has a 30% chance to force the target to drop
    their equipped weapon.
    """
    key = "disarm"
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = self.caller
        if not CombatHandler.is_in_combat(caller):
            caller.msg("|yYou are not in combat.|n")
            return
        target = CombatHandler.get_target(caller)
        if not target:
            caller.msg("|yYou have no target.|n")
            return

        success, msg = CombatHandler.queue_skill(caller, "disarm")
        if success:
            caller.msg(f"|g{msg}|n")
        else:
            caller.msg(f"|r{msg}|n")