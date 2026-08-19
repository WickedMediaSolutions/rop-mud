"""
Spell Commands for 'rop'

  cast <spell> [= <target>]   — Cast a spell on a target (or self)
  spells / spellbook           — List your available spells
  spell <name>                 — Show detailed info about a spell
  effects                      — Show active status effects (Phase 1.2)
  saves                        — Show saving throw bonuses (Phase 1.2)
  read <scroll>                — Read a spell scroll (Phase 7)
  inscribe <spell>             — Inscribe a spell onto a scroll (Phase 7)
  scribe <spell>               — Alias for inscribe (Phase 7)
"""

from commands.command import Command
from evennia.utils.search import search_object
from world.spells import (
    SpellHandler, get_spell, format_spellbook, format_spell_detail,
    TARGET_SELF, TARGET_SINGLE, TARGET_AOE, TARGET_PBAOE
)


class CmdCast(Command):
    """
    Cast a magic spell.

    Usage:
      cast <spell>
      cast <spell> = <target>

    When no target is specified, the spell is cast on yourself (for heals,
    shields, or buffs).  For damaging or debuff spells, you must provide a
    target.

    Phase 1.2: Spells now have damage types, saving throws, and status effects.

    Examples:
      cast sparks = goblin
      cast minor heal
      cast fireball
      cast meteor swarm = dark elf
    """

    key = "cast"
    aliases = ["c"]
    locks = "cmd:can_cast_spells()"
    help_category = "Magic"

    def parse(self):
        self.spell_name = ""
        self.target_name = ""

        args = self.args.strip()
        if not args:
            return

        if "=" in args:
            self.spell_name, self.target_name = args.split("=", 1)
            self.spell_name = self.spell_name.strip()
            self.target_name = self.target_name.strip()
        else:
            self.spell_name = args

    def func(self):
        caller = self.caller
        spell_name = self.spell_name

        if not spell_name:
            caller.msg("|yUsage: cast <spell> [= <target>]|n")
            return

        spell = get_spell(spell_name)
        if not spell:
            caller.msg(f"|rUnknown spell: '{spell_name}'. Use |wspells|r to see your spellbook.|n")
            return

        # ===== CRITICAL GATE: Race/Class permission check =====
        from world.race_class_matrix import can_learn_spell
        allowed, reason = can_learn_spell(caller, spell_name)
        if not allowed:
            caller.msg(f"|r{reason}|n")
            return
        # ======================================================

        # Phase 1.2: Check if caller is stunned (can't cast)
        try:
            from world.status_effects import get_active_effects
            effects = get_active_effects(caller)
            if effects and not effects.can_act():
                caller.msg("|rYou are stunned and cannot cast spells!|n")
                return
        except ImportError:
            pass

        # Break stealth on spell cast
        try:
            from world.combat_skills import break_stealth
            break_stealth(caller, reason="spell")
        except Exception:
            pass

        # Instantiate handler
        handler = SpellHandler(caller)

        ok, err = handler.can_cast(spell_name)
        if not ok:
            caller.msg(f"|r{err}|n")
            return

        # Resolve target based on spell type
        target_type = spell["target"]
        target = None

        if target_type == TARGET_SELF:
            target = caller

        elif target_type in (TARGET_SINGLE, TARGET_AOE, TARGET_PBAOE):
            if self.target_name:
                # Search in current room for target
                results = caller.search(self.target_name, location=caller.location)
                if not results:
                    caller.msg(f"|rYou don't see '{self.target_name}' here.|n")
                    return
                target = results[0] if hasattr(results, '__iter__') and not isinstance(results, str) else results
                if isinstance(results, list):
                    target = results[0]
                else:
                    target = results
                if not target:
                    caller.msg(f"|rYou don't see '{self.target_name}' here.|n")
                    return
            elif target_type == TARGET_SINGLE:
                caller.msg("|rYou must specify a target for that spell. Usage: cast <spell> = <target>|n")
                return
            # AoE without explicit target: target all enemies in room (handled by handler if needed)

        # For AoE spells, iterate over all characters in the room
        if target_type in (TARGET_AOE, TARGET_PBAOE):
            self._cast_aoe(handler, spell, caller)
        else:
            success, msg = handler.cast(spell_name, target=target, caller=caller)
            if success:
                caller.msg(msg)
            else:
                caller.msg(f"|r{msg}|n")

    def _cast_aoe(self, handler, spell, caller):
        """Cast an AoE spell on all valid targets in the room."""
        room = caller.location
        if not room:
            caller.msg("|rYou have no location to cast in.|n")
            return

        # Get all character objects in the room (excluding caller for damaging spells)
        targets = [obj for obj in room.contents
                   if obj != caller and hasattr(obj, 'attributes') and obj.attributes.has("hp")]

        # If target_name specified, try to find specific target(s)
        if self.target_name:
            found = caller.search(self.target_name, location=room)
            if found:
                if isinstance(found, list):
                    targets = [t for t in found if hasattr(t, 'attributes') and t.attributes.has("hp")]
                elif hasattr(found, 'attributes') and found.attributes.has("hp"):
                    targets = [found]

        if not targets:
            # Fall back: just damage the caller for testing/training
            caller.msg("|yNo valid targets in the room for an AoE spell.|n")
            return

        effect_type = spell["effect"].get("type", "damage")
        if effect_type == "heal":
            # Mass heals affect caller + allies
            targets = [caller] + [obj for obj in room.contents
                                  if obj != caller and hasattr(obj, 'attributes') and obj.attributes.has("hp")]

        hit_count = 0
        for tgt in targets:
            ok, msg = handler.cast(spell["key"], target=tgt, caller=caller)
            if ok:
                hit_count += 1

        caller.msg(f"|g{spell['name']} hits {hit_count} target(s)!|n")


class CmdSpells(Command):
    """
    View your spellbook — all spells available at your current level.

    Usage:
      spells
      spellbook
      spell <name>          — show detailed info about one spell
    """

    key = "spells"
    aliases = ["spellbook", "spell"]
    locks = "cmd:can_cast_spells()"
    help_category = "Magic"

    def parse(self):
        self.spell_lookup = self.args.strip()

    def func(self):
        caller = self.caller

        if self.spell_lookup and self.cmdstring == "spell":
            # Show detailed spell info
            detail = format_spell_detail(self.spell_lookup)
            caller.msg(detail)
        else:
            # Show full spellbook
            book = format_spellbook(caller)
            caller.msg(book)


class CmdEffects(Command):
    """
    View your active status effects.

    Usage:
      effects

    Phase 1.2: Shows all DoTs, crowd control, and debuffs currently affecting you.
    """

    key = "effects"
    aliases = ["status", "buffs"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = self.caller
        try:
            effects = caller.get_active_effects()
            if effects:
                display = effects.get_effect_display()
                if display:
                    caller.msg(f"|cActive Effects:|n {display}")
                else:
                    caller.msg("|yYou have no active status effects.|n")
            else:
                caller.msg("|yYou have no active status effects.|n")
        except Exception:
            caller.msg("|yYou have no active status effects.|n")


class CmdRead(Command):
    """
    Read a spell scroll to cast its stored spell.

    Usage:
      read <scroll>

    Reading a scroll casts the spell inscribed on it (once) and
    consumes the scroll.  No mana is required.

    Phase 7: Spell scrolls are consumable magic items.
    """

    key = "read"
    aliases = ["recite", "use scroll"]
    locks = "cmd:all()"
    help_category = "Magic"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        if not args:
            caller.msg("|yUsage: read <scroll>|n")
            return

        from world.spell_scrolls import handle_read_scroll
        success, msg = handle_read_scroll(caller, args)

        if success:
            caller.msg(f"|g{msg}|n")
        else:
            caller.msg(f"|r{msg}|n")


class CmdInscribe(Command):
    """
    Inscribe a known spell onto a blank scroll.

    Usage:
      inscribe <spell>
      scribe <spell>

    Creates a single-use spell scroll for the specified spell.
    Costs copper based on the spell's level (50 copper per level).

    Phase 7: Scroll inscription lets casters create consumables.
    """

    key = "inscribe"
    aliases = ["scribe"]
    locks = "cmd:can_cast_spells()"
    help_category = "Magic"

    def func(self):
        caller = self.caller
        spell_name = self.args.strip()

        if not spell_name:
            caller.msg("|yUsage: inscribe <spell>|n")
            return

        from world.spell_scrolls import handle_inscribe_scroll
        success, msg = handle_inscribe_scroll(caller, spell_name)

        if success:
            caller.msg(f"|g{msg}|n")
        else:
            caller.msg(f"|r{msg}|n")


class CmdSaves(Command):
    """
    View your saving throw bonuses.

    Usage:
      saves

    Phase 1.2: Shows your bonuses against Poison, Death, Petrification, Rod, and Spell.
    """

    key = "saves"
    aliases = ["savingthrows", "resistances"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = self.caller
        try:
            from world.saving_throws import get_save_bonus_display
            display = get_save_bonus_display(caller)
            if display:
                caller.msg(f"|cSaving Throw Bonuses:|n\n{display}")
            else:
                caller.msg("|yNo saving throw data available.|n")
        except Exception:
            caller.msg("|yNo saving throw data available.|n")