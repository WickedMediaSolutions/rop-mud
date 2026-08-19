"""
Recovery & Positional States for 'rop' — Rest / Meditate / Sleep

Provides:
  - Position enum (STANDING, RESTING, MEDITATING, SLEEPING)
  - POSITION_REGEN_RATES with HP/Mana/MV/Stamina percentages
  - RecoveryScript (global ticker, 15s interval)
"""

from enum import Enum

from evennia.scripts.scripts import DefaultScript
from evennia.objects.models import ObjectDB


class Position(Enum):
    STANDING = "standing"
    RESTING = "resting"
    MEDITATING = "meditating"
    SLEEPING = "sleeping"


RECOVERY_TICK_INTERVAL = 15.0  # Seconds between regen ticks

POSITION_REGEN_RATES = {
    Position.STANDING:   {"hp_pct": 0.08, "mana_pct": 0.08, "mv_pct": 0.15, "stamina_pct": 0.08},
    Position.RESTING:    {"hp_pct": 0.15, "mana_pct": 0.10, "mv_pct": 0.20, "stamina_pct": 0.10},
    Position.MEDITATING: {"hp_pct": 0.05, "mana_pct": 0.25, "mv_pct": 0.10, "stamina_pct": 0.05},
    Position.SLEEPING:   {"hp_pct": 0.30, "mana_pct": 0.30, "mv_pct": 0.50, "stamina_pct": 0.20},
}


class RecoveryScript(DefaultScript):
    """Global script that ticks every 15s to regen HP/Mana/MV/Stamina for all players."""

    def at_script_creation(self):
        self.key = "global_recovery"
        self.desc = "Global HP/Mana/MV/Stamina recovery ticker"
        self.interval = RECOVERY_TICK_INTERVAL
        self.persistent = True

    def at_repeat(self):
        from typeclasses.characters import Character
        from world.tick_combat import CombatHandler
        from world.race_class_matrix import can_cast_spells

        for char in ObjectDB.objects.all():
            if not isinstance(char, Character):
                continue
            if not char.has_account:
                continue
            if CombatHandler.is_in_combat(char):
                continue  # No regen during combat

            position_str = char.attributes.get("position", default="standing")
            try:
                pos_enum = Position(position_str)
            except ValueError:
                pos_enum = Position.STANDING

            rates = POSITION_REGEN_RATES[pos_enum]

            # Talent bonuses (Phase 2.3): flat HP/stamina regen per tick
            try:
                from world.skill_tree import get_talent_bonuses
                talent_bonuses = get_talent_bonuses(char)
            except Exception:
                talent_bonuses = {}

            # HP regen
            max_hp = char.attributes.get("max_hp", 100)
            hp = char.attributes.get("hp", 0)
            hp_regen = max(1, int(max_hp * rates["hp_pct"]))
            hp_regen += int(talent_bonuses.get("hp_regen", 0))
            char.attributes.add("hp", min(max_hp, hp + hp_regen))

            # Mana regen (only for mana-using classes)
            if can_cast_spells(char):
                max_mana = char.attributes.get("max_mana", 50)
                mana = char.attributes.get("mana", 0)
                mana_regen = max(1, int(max_mana * rates["mana_pct"]))
                char.attributes.add("mana", min(max_mana, mana + mana_regen))

            # MV regen
            max_mv = char.attributes.get("max_mv", 100)
            mv = char.attributes.get("mv", 0)
            mv_regen = max(1, int(max_mv * rates["mv_pct"]))
            char.attributes.add("mv", min(max_mv, mv + mv_regen))

            # Stamina regen — max stamina scales with CON and level
            stats = char.attributes.get("stats", default={})
            con_val = stats.get("con", 10) if (stats is not None and hasattr(stats, "items")) else 10
            level = char.attributes.get("level", default=1)
            max_stamina = 80 + (con_val * 2) + (level * 2)
            char.attributes.add("max_stamina", max_stamina)
            stamina = char.attributes.get("stamina", max_stamina)
            stamina_regen = max(1, int(max_stamina * rates["stamina_pct"]))
            stamina_regen += int(talent_bonuses.get("stamina_regen", 0))
            char.attributes.add("stamina", min(max_stamina, stamina + stamina_regen))
