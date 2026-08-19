"""
Leaderboard System for 'rop'

Provides:
  leaderboard [category]  - Show top players by category
  leaderboard warpoints   - Top PvP champions
  leaderboard levels      - Top level adventurers
  leaderboard wealth      - Richest players (carried + banked)
  leaderboard kills       - Top monster slayers

Provides a unified ranking system across multiple metrics.
"""

from commands.command import Command
from evennia.objects.models import ObjectDB

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

LEADERBOARD_SIZE = 20

CATEGORIES = {
    "warpoints": {
        "title": "Warpoints Leaderboard",
        "description": "Top PvP champions by Warpoints earned",
        "attr": "warpoints",
    },
    "levels": {
        "title": "Level Leaderboard",
        "description": "Highest-level adventurers in the realm",
        "attr": "level",
    },
    "wealth": {
        "title": "Wealth Leaderboard",
        "description": "Richest players (carried + banked gold)",
        "attr": "wealth",  # Special: computed attribute
    },
    "kills": {
        "title": "Kills Leaderboard",
        "description": "Top monster slayers by total kills",
        "attr": "mob_kills",
    },
}


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def get_all_player_characters():
    """Return all player characters in the game."""
    from typeclasses.characters import Character

    players = []
    for obj in ObjectDB.objects.all():
        if not isinstance(obj, Character):
            continue
        players.append(obj)
    return players


def compute_wealth(character):
    """Compute total wealth (carried + banked) for a character."""
    from world.economy import get_money, get_bank_money
    return get_money(character) + get_bank_money(character)


def get_leaderboard_entries(category):
    """
    Build a ranked list of dicts for the given category.

    Returns a list of dicts with keys:
        name, level, alignment, value (the metric value)
    Sorted descending by value.
    """
    cat_config = CATEGORIES.get(category)
    if not cat_config:
        return []

    attr = cat_config["attr"]
    players = get_all_player_characters()

    entries = []
    for player in players:
        if attr == "wealth":
            value = compute_wealth(player)
        else:
            value = player.attributes.get(attr, default=0) or 0

        entries.append({
            "name": player.key,
            "level": player.attributes.get("level", default=1),
            "alignment": player.attributes.get("alignment", default="?"),
            "value": value,
        })

    # Sort descending by value, then by level as tiebreaker
    entries.sort(key=lambda e: (-e["value"], -e["level"]))
    return entries


def format_leaderboard(category, size=LEADERBOARD_SIZE):
    """
    Build the formatted leaderboard string for a category.
    Returns a string (with ANSI color codes).
    """
    cat_config = CATEGORIES.get(category)
    if not cat_config:
        return "|rUnknown leaderboard category.|n"

    entries = get_leaderboard_entries(category)

    # Filter out zero-value entries
    nonzero = [e for e in entries if e["value"] > 0]

    lines = []
    lines.append(f"|Y|h===== {cat_config['title']} =====|n")
    lines.append(f"|w{cat_config['description']}|n")
    lines.append("")

    if not nonzero:
        lines.append(f"|yNo players ranked yet for {category}.|n")
        return "\n".join(lines)

    top = nonzero[:size]

    # Column header
    lines.append(
        f"|c{'Rank':>4}  {'Name':<20} {'Lvl':>3}  {'Faction':<6}  {'Value':>8}|n"
    )
    lines.append("|Y" + "-" * 55 + "|n")

    for i, entry in enumerate(top, 1):
        # Color-code rank
        if i == 1:
            rank_str = f"|Y{i:>4}|n"
        elif i == 2:
            rank_str = f"|w{i:>4}|n"
        elif i == 3:
            rank_str = f"|r{i:>4}|n"
        else:
            rank_str = f"{i:>4}"

        # Color-code faction
        if entry["alignment"] == "Good":
            faction_str = f"|g{entry['alignment']:<6}|n"
        elif entry["alignment"] == "Evil":
            faction_str = f"|r{entry['alignment']:<6}|n"
        else:
            faction_str = f"{entry['alignment']:<6}"

        # Format value
        if category == "wealth":
            from world.economy import format_money_brief
            value_str = format_money_brief(entry["value"])
        else:
            value_str = f"|Y{entry['value']}|n"

        lines.append(
            f"{rank_str}  |w{entry['name']:<20}|n "
            f"{entry['level']:>3}  {faction_str}  {value_str}"
        )

    lines.append("")
    lines.append(f"|wShowing top {len(top)} of {len(nonzero)} ranked players.|n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# COMMAND
# ---------------------------------------------------------------------------

class CmdLeaderboard(Command):
    """
    Display the top players in the realm by category.

    Usage:
      leaderboard               - Show your current category (defaults to levels)
      leaderboard <category>    - Show a specific category
      leaderboard warpoints     - Top PvP champions
      leaderboard levels        - Highest-level adventurers
      leaderboard wealth        - Richest players
      leaderboard kills         - Top monster slayers
      top [category]            - Shorthand for leaderboard

    Categories: warpoints, levels, wealth, kills
    """

    key = "leaderboard"
    aliases = ["top", "ranking", "rankings", "board"]
    help_category = "Social"
    locks = "cmd:all()"
    auto_help = True

    def parse(self):
        self.args = (self.args or "").strip().lower()

    def func(self):
        caller = self.caller

        # Map aliases
        alias_map = {
            "wp": "warpoints",
            "warp": "warpoints",
            "pvp": "warpoints",
            "lvl": "levels",
            "lv": "levels",
            "level": "levels",
            "xp": "levels",
            "gold": "wealth",
            "money": "wealth",
            "rich": "wealth",
            "kill": "kills",
            "mobkills": "kills",
            "slayer": "kills",
            "slayers": "kills",
        }

        category = "levels"  # Default category

        if self.args:
            raw = self.args
            if raw in alias_map:
                category = alias_map[raw]
            elif raw in CATEGORIES:
                category = raw
            else:
                caller.msg(
                    f"|rUnknown leaderboard category: '{self.args}'.|n\n"
                    "|wValid categories: warpoints, levels, wealth, kills|n"
                )
                return

        output = format_leaderboard(category)
        caller.msg(output)


# Alias for test compatibility
CmdTop = CmdLeaderboard