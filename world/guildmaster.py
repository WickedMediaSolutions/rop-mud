"""
Guildmaster & Practice System for 'rop' — EmlenMUD-Style Training

Provides:
  - PracticeSession dataclass
  - award_practice_points() — called on level-up
  - GuildmasterNPC typeclass
  - get_trainable_spells() / get_trainable_skills()
  - train_spell() / train_skill()
  - CmdTrain, CmdLearn, CmdPractice commands
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from evennia.objects.objects import DefaultCharacter
from commands.command import Command


@dataclass
class PracticeSession:
    """Tracks a player's practice points and trained skills."""
    practice_points: int = 0
    trained_spells: Set[str] = field(default_factory=set)
    trained_skills: Set[str] = field(default_factory=set)
    skill_ranks: Dict[str, int] = field(default_factory=dict)


def award_practice_points(character, level: int):
    """Called on level-up. Awards practice points based on class."""
    char_class = character.attributes.get("class", default="Warrior") if hasattr(character, "attributes") else "Warrior"
    pp_per_level = {
        "Warrior": 3, "Paladin": 4, "Cleric": 5, "Mage": 6,
        "Rogue": 3, "Warlock": 5, "Druid": 5, "Ranger": 4,
        "Monk": 3, "Necromancer": 5,
    }
    points = pp_per_level.get(char_class, 3)
    session = character.attributes.get("practice_session", default=None) if hasattr(character, "attributes") else None
    if session is None:
        session = PracticeSession()
    session.practice_points += points
    if hasattr(character, "attributes"):
        character.attributes.add("practice_session", session)
    character.msg(f"|gYou have earned {points} practice points! (Total: {session.practice_points})|n")


class GuildmasterNPC(DefaultCharacter):
    """NPC that allows players to spend practice points to learn spells/skills."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.guild_class = "Warrior"

    def get_trainable_spells(self, character) -> List[Dict]:
        """Return spells this character can train, with practice point costs."""
        from world.race_class_matrix import can_learn_spell
        from world.spells import SPELLS

        char_level = character.attributes.get("level", default=1) if hasattr(character, "attributes") else 1
        learned = set(character.attributes.get("learned_spells", default=[])) if hasattr(character, "attributes") else set()
        session = character.attributes.get("practice_session", PracticeSession()) if hasattr(character, "attributes") else PracticeSession()
        trained = session.trained_spells

        available = []
        for key, spell in SPELLS.items():
            if spell["name"] in learned or spell["name"] in trained:
                continue
            if spell["level"] > char_level:
                continue
            allowed, _ = can_learn_spell(character, key)
            if not allowed:
                continue
            cost = 2
            available.append({"name": spell["name"], "level": spell["level"],
                              "school": spell["school"], "cost": cost})
        return sorted(available, key=lambda s: s["level"])

    def get_trainable_skills(self, character) -> List[Dict]:
        """Return skills this character can train."""
        from world.race_class_matrix import can_use_skill
        from world.combat_skills import COMBAT_SKILLS

        char_level = character.attributes.get("level", default=1) if hasattr(character, "attributes") else 1
        session = character.attributes.get("practice_session", PracticeSession()) if hasattr(character, "attributes") else PracticeSession()
        trained = session.trained_skills

        available = []
        for key, skill in COMBAT_SKILLS.items():
            if key in trained:
                continue
            if skill["min_level"] > char_level:
                continue
            allowed, _ = can_use_skill(character, key)
            if not allowed:
                continue
            cost = 1
            available.append({"name": skill["name"], "key": key, "level": skill["min_level"], "cost": cost})
        return sorted(available, key=lambda s: s["level"])

    def train_spell(self, character, spell_name: str) -> Tuple[bool, str]:
        """Spend practice points to learn a spell."""
        session = character.attributes.get("practice_session", PracticeSession()) if hasattr(character, "attributes") else PracticeSession()
        trainable = {s["name"]: s for s in self.get_trainable_spells(character)}
        if spell_name not in trainable:
            return False, "You cannot train that spell here."
        info = trainable[spell_name]
        if session.practice_points < info["cost"]:
            return False, f"You need {info['cost']} practice points (have {session.practice_points})."
        session.practice_points -= info["cost"]
        session.trained_spells.add(spell_name)
        learned = character.attributes.get("learned_spells", default=[]) if hasattr(character, "attributes") else []
        learned.append(spell_name)
        if hasattr(character, "attributes"):
            character.attributes.add("learned_spells", learned)
            character.attributes.add("practice_session", session)
        return True, f"You learn {spell_name}! ({session.practice_points} practice points remaining)"

    def train_skill(self, character, skill_key: str) -> Tuple[bool, str]:
        """Spend practice points to learn a skill."""
        from world.combat_skills import COMBAT_SKILLS

        session = character.attributes.get("practice_session", PracticeSession()) if hasattr(character, "attributes") else PracticeSession()
        trainable = {s["key"]: s for s in self.get_trainable_skills(character)}
        if skill_key not in trainable:
            return False, "You cannot train that skill here."
        info = trainable[skill_key]
        if session.practice_points < info["cost"]:
            return False, f"You need {info['cost']} practice points (have {session.practice_points})."
        session.practice_points -= info["cost"]
        session.trained_skills.add(skill_key)
        session.skill_ranks[skill_key] = session.skill_ranks.get(skill_key, 0) + 1
        if hasattr(character, "attributes"):
            character.attributes.add("practice_session", session)
            # Permanent skill-unlock indication: store trained skills on character
            trained = character.attributes.get("trained_skills", default=[])
            if not isinstance(trained, list):
                trained = []
            if skill_key not in trained:
                trained.append(skill_key)
                character.attributes.add("trained_skills", trained)
        return True, f"You learn {info['name']}! ({session.practice_points} practice points remaining)"


# ---------------------------------------------------------------------------
# Guildmaster Commands
# ---------------------------------------------------------------------------

class CmdTrain(Command):
    """List trainable spells/skills at a guildmaster."""
    key = "train"
    locks = "cmd:all()"
    help_category = "Training"

    def func(self):
        caller = self.caller
        location = caller.location
        if not location:
            caller.msg("|rYou are nowhere.|n")
            return

        # Find a guildmaster in the room
        gm = None
        for obj in location.contents:
            if isinstance(obj, GuildmasterNPC):
                gm = obj
                break

        if not gm:
            caller.msg("|yThere is no guildmaster here to train with.|n")
            return

        spells = gm.get_trainable_spells(caller)
        skills = gm.get_trainable_skills(caller)
        session = caller.attributes.get("practice_session", PracticeSession()) if hasattr(caller, "attributes") else PracticeSession()

        out = f"|w=== {gm.key} — Training ({session.practice_points} practice points) ===|n\n"

        if spells:
            out += "|cSpells:|n\n"
            for s in spells:
                out += f"  {s['name']} (Lvl {s['level']}, {s['school']}) — {s['cost']} PP\n"

        if skills:
            out += "|ySkills:|n\n"
            for s in skills:
                out += f"  {s['name']} (Lvl {s['level']}) — {s['cost']} PP\n"

        if not spells and not skills:
            out += "|yNothing available to train at your level.|n"

        caller.msg(out)


class CmdLearn(Command):
    """Learn a specific spell or skill from a guildmaster."""
    key = "learn"
    locks = "cmd:all()"
    help_category = "Training"

    def parse(self):
        self.target = self.args.strip()

    def func(self):
        caller = self.caller
        if not self.target:
            caller.msg("|yUsage: learn <spell or skill name>|n")
            return

        location = caller.location
        if not location:
            return

        gm = None
        for obj in location.contents:
            if isinstance(obj, GuildmasterNPC):
                gm = obj
                break

        if not gm:
            caller.msg("|yThere is no guildmaster here.|n")
            return

        # Try spell first
        ok, msg = gm.train_spell(caller, self.target)
        if ok:
            caller.msg(f"|g{msg}|n")
            return

        # Try skill
        ok, msg = gm.train_skill(caller, self.target.lower().replace(" ", ""))
        if ok:
            caller.msg(f"|g{msg}|n")
            return

        caller.msg(f"|r{msg}|n")


class CmdPractice(Command):
    """Show current practice points and trained abilities."""
    key = "practice"
    locks = "cmd:all()"
    help_category = "Training"

    def func(self):
        caller = self.caller
        session = caller.attributes.get("practice_session", PracticeSession()) if hasattr(caller, "attributes") else PracticeSession()

        out = f"|w=== Practice Session ===|n\n"
        out += f"|cPractice Points: |w{session.practice_points}|n\n"

        if session.trained_spells:
            out += f"|cTrained Spells:|n {', '.join(sorted(session.trained_spells))}\n"

        if session.trained_skills:
            out += f"|yTrained Skills:|n "
            skill_strs = [f"{s} (Rank {session.skill_ranks.get(s, 1)})" for s in sorted(session.trained_skills)]
            out += ", ".join(skill_strs) + "\n"

        if not session.trained_spells and not session.trained_skills:
            out += "|yNo abilities trained yet.|n"

        caller.msg(out)