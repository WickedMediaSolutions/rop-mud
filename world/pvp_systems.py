"""
Structured PvP Systems for 'rop'
=================================
Provides:
  - Arena System: 1v1, 2v2, 3v3 ranked/unranked matches
  - Battlegrounds: Capture the Flag, Faction War Zones, King of the Hill
  - Duel/Wager System: 1v1 with gold/items at stake
  - Bounty Board: Players place bounties; bounty hunters collect

Usage:
  from world.pvp_systems import ArenaManager, BattlegroundManager, DuelManager, BountyBoard
"""

from __future__ import annotations

import random
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from evennia import create_object, search_object
    from evennia.objects.models import ObjectDB
    from typeclasses.rooms import Room
except Exception:
    create_object = None
    search_object = None
    ObjectDB = None
    Room = None


# ===========================================================================
# ARENA SYSTEM
# ===========================================================================

class ArenaMatch:
    """Represents a single arena match (1v1, 2v2, or 3v3)."""

    def __init__(self, match_id: str, team_a: List[Any], team_b: List[Any],
                 match_type: str = "1v1", ranked: bool = False,
                 wager_gold: int = 0):
        self.match_id = match_id
        self.team_a = team_a  # list of character objects
        self.team_b = team_b
        self.match_type = match_type
        self.ranked = ranked
        self.wager_gold = wager_gold
        self.status = "pending"  # pending, active, completed, cancelled
        self.winner: Optional[str] = None  # "team_a" or "team_b"
        self.arena_room: Any = None
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.ended_at: Optional[float] = None
        self.spectators: List[Any] = []

    def start(self) -> bool:
        """Start the match. Returns True if successful."""
        if self.status != "pending":
            return False
        self.status = "active"
        self.started_at = time.time()
        return True

    def end(self, winner: str) -> bool:
        """End the match with a winner."""
        if self.status != "active":
            return False
        self.status = "completed"
        self.winner = winner
        self.ended_at = time.time()
        return True

    def cancel(self) -> bool:
        """Cancel a pending match."""
        if self.status != "pending":
            return False
        self.status = "cancelled"
        return True

    @property
    def duration_seconds(self) -> float:
        """How long the match has been running."""
        if self.started_at is None:
            return 0
        end = self.ended_at or time.time()
        return end - self.started_at

    def get_team_names(self) -> Tuple[str, str]:
        """Return display names for both teams."""
        a_names = ", ".join(c.key for c in self.team_a)
        b_names = ", ".join(c.key for c in self.team_b)
        return a_names, b_names


class ArenaManager:
    """
    Manages all arena matches, queues, and rankings.

    Features:
      - Queue system for 1v1, 2v2, 3v3
      - Ranked ELO tracking
      - Match history
      - Spectator support
    """

    def __init__(self):
        self._matches: Dict[str, ArenaMatch] = {}
        self._queues: Dict[str, List[Any]] = {
            "1v1_unranked": [],
            "1v1_ranked": [],
            "2v2_unranked": [],
            "2v2_ranked": [],
            "3v3_unranked": [],
            "3v3_ranked": [],
        }
        self._elo_ratings: Dict[int, int] = {}  # dbref -> ELO rating
        self._match_history: Dict[int, List[Dict]] = {}  # dbref -> list of match results

    # ---- Queue Management ----

    def join_queue(self, character: Any, queue_type: str) -> Tuple[bool, str]:
        """
        Add a character to an arena queue.

        Args:
            character: The character joining.
            queue_type: One of "1v1_unranked", "1v1_ranked", etc.

        Returns:
            (success, message)
        """
        if queue_type not in self._queues:
            return False, f"Invalid queue type: {queue_type}"

        # Remove from any existing queue first
        self.leave_queue(character)

        # Check if already in a match
        for match in self._matches.values():
            if match.status in ("pending", "active"):
                all_players = match.team_a + match.team_b
                if character in all_players:
                    return False, "You are already in an arena match."

        self._queues[queue_type].append(character)
        team_size = int(queue_type[0])
        queue_len = len(self._queues[queue_type])

        character.msg(f"|g[Arena] You have joined the {queue_type} queue. "
                      f"({queue_len} player(s) waiting)|n")

        # Try to form a match
        if queue_len >= team_size * 2:
            self._try_form_match(queue_type)

        return True, f"Joined {queue_type} queue."

    def leave_queue(self, character: Any) -> Tuple[bool, str]:
        """Remove a character from all arena queues."""
        removed = False
        for qtype, queue in self._queues.items():
            if character in queue:
                queue.remove(character)
                removed = True
                character.msg(f"|y[Arena] You have left the {qtype} queue.|n")
        if not removed:
            return False, "You are not in any arena queue."
        return True, "Left all arena queues."

    def _try_form_match(self, queue_type: str) -> Optional[ArenaMatch]:
        """Try to form a match from a queue."""
        queue = self._queues[queue_type]
        team_size = int(queue_type[0])
        needed = team_size * 2

        if len(queue) < needed:
            return None

        # Take the first N players
        players = queue[:needed]
        del queue[:needed]

        team_a = players[:team_size]
        team_b = players[team_size:]

        ranked = "ranked" in queue_type
        match_id = f"arena_{uuid.uuid4().hex[:8]}"
        match = ArenaMatch(match_id, team_a, team_b, f"{team_size}v{team_size}", ranked)
        self._matches[match_id] = match

        # Notify players
        a_names, b_names = match.get_team_names()
        for p in team_a:
            p.msg(f"|Y|h[Arena] Match found!|n Team A: {a_names} vs Team B: {b_names}")
            p.msg("|wThe match will begin shortly. Prepare for battle!|n")
        for p in team_b:
            p.msg(f"|Y|h[Arena] Match found!|n Team A: {a_names} vs Team B: {b_names}")
            p.msg("|wThe match will begin shortly. Prepare for battle!|n")

        match.start()
        return match

    # ---- Match Management ----

    def get_match(self, match_id: str) -> Optional[ArenaMatch]:
        """Get a match by ID."""
        return self._matches.get(match_id)

    def get_player_match(self, character: Any) -> Optional[ArenaMatch]:
        """Get the active match a player is in."""
        for match in self._matches.values():
            if match.status in ("pending", "active"):
                if character in match.team_a + match.team_b:
                    return match
        return None

    def report_victory(self, match_id: str, winner_team: str) -> Tuple[bool, str]:
        """
        Report a match victory.

        Args:
            match_id: The match ID.
            winner_team: "team_a" or "team_b"

        Returns:
            (success, message)
        """
        match = self._matches.get(match_id)
        if not match:
            return False, "Match not found."
        if match.status != "active":
            return False, "Match is not active."

        match.end(winner_team)

        winners = match.team_a if winner_team == "team_a" else match.team_b
        losers = match.team_b if winner_team == "team_a" else match.team_a

        # Update ELO if ranked
        if match.ranked:
            self._update_elo(winners, losers)

        # Record match history
        for p in winners:
            self._record_match(p, match, "win")
        for p in losers:
            self._record_match(p, match, "loss")

        # Award arena points
        for p in winners:
            pts = p.attributes.get("arena_points", default=0)
            p.attributes.add("arena_points", pts + 10)
            p.msg(f"|Y|h[Arena] Victory!|n You earn 10 Arena Points. (Total: {pts + 10})")

        for p in losers:
            pts = p.attributes.get("arena_points", default=0)
            p.attributes.add("arena_points", max(0, pts - 2))
            p.msg(f"|r[Arena] Defeat.|n You lose 2 Arena Points. (Total: {max(0, pts - 2)})")

        a_names, b_names = match.get_team_names()
        winner_names = a_names if winner_team == "team_a" else b_names
        return True, f"Match complete! {winner_names} wins!"

    def forfeit_match(self, character: Any) -> Tuple[bool, str]:
        """Forfeit the current match for a player."""
        match = self.get_player_match(character)
        if not match:
            return False, "You are not in an active match."

        if character in match.team_a:
            return self.report_victory(match.match_id, "team_b")
        else:
            return self.report_victory(match.match_id, "team_a")

    # ---- ELO System ----

    def get_elo(self, character: Any) -> int:
        """Get a character's ELO rating (default 1200)."""
        return self._elo_ratings.get(character.id, 1200)

    def _update_elo(self, winners: List[Any], losers: List[Any]) -> None:
        """Update ELO ratings after a match."""
        K = 32  # K-factor

        for winner in winners:
            for loser in losers:
                w_elo = self.get_elo(winner)
                l_elo = self.get_elo(loser)

                expected_w = 1.0 / (1.0 + 10 ** ((l_elo - w_elo) / 400.0))
                expected_l = 1.0 - expected_w

                self._elo_ratings[winner.id] = int(w_elo + K * (1.0 - expected_w))
                self._elo_ratings[loser.id] = int(l_elo + K * (0.0 - expected_l))

    def _record_match(self, character: Any, match: ArenaMatch, result: str) -> None:
        """Record a match in a character's history."""
        history = self._match_history.get(character.id, [])
        history.append({
            "match_id": match.match_id,
            "type": match.match_type,
            "ranked": match.ranked,
            "result": result,
            "timestamp": time.time(),
            "duration": match.duration_seconds,
        })
        # Keep last 50 matches
        if len(history) > 50:
            history = history[-50:]
        self._match_history[character.id] = history

    def get_match_history(self, character: Any) -> List[Dict]:
        """Get a character's match history."""
        return self._match_history.get(character.id, [])

    def get_leaderboard(self, limit: int = 10) -> List[Tuple[int, int]]:
        """Get top ELO ratings. Returns list of (dbref, elo)."""
        sorted_elos = sorted(self._elo_ratings.items(), key=lambda x: x[1], reverse=True)
        return sorted_elos[:limit]

    def list_active_matches(self) -> List[Dict[str, Any]]:
        """List all active matches."""
        active = []
        for match in self._matches.values():
            if match.status == "active":
                a_names, b_names = match.get_team_names()
                active.append({
                    "match_id": match.match_id,
                    "type": match.match_type,
                    "ranked": match.ranked,
                    "team_a": a_names,
                    "team_b": b_names,
                    "duration": int(match.duration_seconds),
                    "spectators": len(match.spectators),
                })
        return active


# Global arena manager instance
arena_manager = ArenaManager()


# ===========================================================================
# BATTLEGROUND SYSTEM
# ===========================================================================

class Battleground:
    """
    Represents a battleground instance.

    Types:
      - "ctf": Capture the Flag
      - "faction_war": Faction War Zone (Good vs Evil)
      - "koth": King of the Hill
    """

    BG_TYPES = {
        "ctf": {
            "name": "Capture the Flag",
            "min_players": 4,
            "max_players": 20,
            "duration": 900,  # 15 minutes
            "description": "Capture the enemy flag and return it to your base. First to 3 captures wins!",
        },
        "faction_war": {
            "name": "Faction War",
            "min_players": 6,
            "max_players": 40,
            "duration": 1200,  # 20 minutes
            "description": "Good vs Evil faction battle. Most kills wins!",
        },
        "koth": {
            "name": "King of the Hill",
            "min_players": 4,
            "max_players": 16,
            "duration": 600,  # 10 minutes
            "description": "Control the central point. Team with most control time wins!",
        },
    }

    def __init__(self, bg_id: str, bg_type: str):
        self.bg_id = bg_id
        self.bg_type = bg_type
        self.config = self.BG_TYPES.get(bg_type, self.BG_TYPES["ctf"])
        self.status = "waiting"  # waiting, starting, active, ending, completed
        self.team_a: List[Any] = []  # Good faction
        self.team_b: List[Any] = []  # Evil faction
        self.team_a_score = 0
        self.team_b_score = 0
        self.team_a_kills = 0
        self.team_b_kills = 0
        self.control_point_holder: Optional[str] = None  # "team_a" or "team_b"
        self.control_time_a = 0.0
        self.control_time_b = 0.0
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.ends_at: Optional[float] = None
        self.bg_room: Any = None
        self.flag_a_carrier: Optional[Any] = None
        self.flag_b_carrier: Optional[Any] = None
        self.flag_a_at_base = True
        self.flag_b_at_base = True

    def add_player(self, character: Any, team: str) -> Tuple[bool, str]:
        """Add a player to a team."""
        if self.status != "waiting":
            return False, "Battleground has already started."

        max_players = self.config["max_players"]
        total = len(self.team_a) + len(self.team_b)
        if total >= max_players:
            return False, "Battleground is full."

        if team == "team_a":
            if character in self.team_a:
                return False, "You are already on Team A."
            self.team_a.append(character)
        else:
            if character in self.team_b:
                return False, "You are already on Team B."
            self.team_b.append(character)

        return True, f"Joined {self.config['name']} on {'Team A (Good)' if team == 'team_a' else 'Team B (Evil)'}."

    def remove_player(self, character: Any) -> bool:
        """Remove a player from the battleground."""
        if character in self.team_a:
            self.team_a.remove(character)
            return True
        if character in self.team_b:
            self.team_b.remove(character)
            return True
        return False

    def start(self) -> Tuple[bool, str]:
        """Start the battleground."""
        min_players = self.config["min_players"]
        total = len(self.team_a) + len(self.team_b)
        if total < min_players:
            return False, f"Need at least {min_players} players to start. Currently {total}."

        if len(self.team_a) == 0 or len(self.team_b) == 0:
            return False, "Both teams need at least 1 player."

        self.status = "active"
        self.started_at = time.time()
        self.ends_at = time.time() + self.config["duration"]

        # Notify all players
        for p in self.team_a + self.team_b:
            p.msg(f"|Y|h[Battleground] {self.config['name']} has begun!|n")
            p.msg(f"|w{self.config['description']}|n")

        return True, f"{self.config['name']} started!"

    def end(self) -> Tuple[str, Dict[str, Any]]:
        """
        End the battleground and determine winner.

        Returns:
            (winner_team, results_dict)
        """
        self.status = "completed"

        # Determine winner based on BG type
        if self.bg_type == "ctf":
            if self.team_a_score > self.team_b_score:
                winner = "team_a"
            elif self.team_b_score > self.team_a_score:
                winner = "team_b"
            else:
                winner = "draw"
        elif self.bg_type == "faction_war":
            if self.team_a_kills > self.team_b_kills:
                winner = "team_a"
            elif self.team_b_kills > self.team_a_kills:
                winner = "team_b"
            else:
                winner = "draw"
        elif self.bg_type == "koth":
            if self.control_time_a > self.control_time_b:
                winner = "team_a"
            elif self.control_time_b > self.control_time_a:
                winner = "team_b"
            else:
                winner = "draw"
        else:
            winner = "draw"

        results = {
            "type": self.bg_type,
            "name": self.config["name"],
            "winner": winner,
            "team_a_score": self.team_a_score,
            "team_b_score": self.team_b_score,
            "team_a_kills": self.team_a_kills,
            "team_b_kills": self.team_b_kills,
            "control_time_a": int(self.control_time_a),
            "control_time_b": int(self.control_time_b),
            "duration": int(time.time() - (self.started_at or time.time())),
        }

        # Award honor points
        winners = self.team_a if winner == "team_a" else self.team_b
        losers = self.team_b if winner == "team_a" else self.team_a

        for p in (winners if winner != "draw" else []):
            honor = p.attributes.get("honor_points", default=0)
            p.attributes.add("honor_points", honor + 25)
            p.msg(f"|Y|h[Battleground] Victory!|n You earn 25 Honor Points.")

        for p in (losers if winner != "draw" else []):
            honor = p.attributes.get("honor_points", default=0)
            p.attributes.add("honor_points", honor + 5)
            p.msg(f"|y[Battleground] Defeat.|n You earn 5 Honor Points for participating.")

        if winner == "draw":
            for p in self.team_a + self.team_b:
                honor = p.attributes.get("honor_points", default=0)
                p.attributes.add("honor_points", honor + 10)
                p.msg(f"|y[Battleground] Draw!|n You earn 10 Honor Points.")

        # Broadcast results
        for p in self.team_a + self.team_b:
            p.msg(f"|w[Battleground] {self.config['name']} has ended!|n")
            p.msg(f"|wFinal Score: Team A {self.team_a_score} - Team B {self.team_b_score}|n")

        return winner, results

    def report_kill(self, killer: Any, victim: Any) -> None:
        """Report a kill in the battleground."""
        if killer in self.team_a:
            self.team_a_kills += 1
        elif killer in self.team_b:
            self.team_b_kills += 1

    def capture_flag(self, team: str) -> bool:
        """A team captures the flag. Returns True if they win."""
        if team == "team_a":
            self.team_a_score += 1
            self.flag_b_carrier = None
            self.flag_b_at_base = True
            if self.team_a_score >= 3:
                return True
        else:
            self.team_b_score += 1
            self.flag_a_carrier = None
            self.flag_a_at_base = True
            if self.team_b_score >= 3:
                return True
        return False

    def update_control_point(self, holder: str, delta_seconds: float) -> None:
        """Update control point time."""
        if holder == "team_a":
            self.control_time_a += delta_seconds
        elif holder == "team_b":
            self.control_time_b += delta_seconds

    @property
    def player_count(self) -> int:
        return len(self.team_a) + len(self.team_b)

    @property
    def time_remaining(self) -> int:
        if self.ends_at is None:
            return self.config["duration"]
        return max(0, int(self.ends_at - time.time()))


class BattlegroundManager:
    """Manages all battleground instances."""

    def __init__(self):
        self._battlegrounds: Dict[str, Battleground] = {}
        self._player_bg: Dict[int, str] = {}  # dbref -> bg_id

    def create_battleground(self, bg_type: str) -> Tuple[Optional[Battleground], str]:
        """Create a new battleground instance."""
        if bg_type not in Battleground.BG_TYPES:
            return None, f"Invalid battleground type: {bg_type}"

        bg_id = f"bg_{uuid.uuid4().hex[:8]}"
        bg = Battleground(bg_id, bg_type)
        self._battlegrounds[bg_id] = bg
        return bg, f"Created {bg.config['name']} battleground."

    def get_battleground(self, bg_id: str) -> Optional[Battleground]:
        """Get a battleground by ID."""
        return self._battlegrounds.get(bg_id)

    def get_player_battleground(self, character: Any) -> Optional[Battleground]:
        """Get the battleground a player is in."""
        bg_id = self._player_bg.get(character.id)
        if bg_id:
            return self._battlegrounds.get(bg_id)
        return None

    def join_battleground(self, character: Any, bg_id: str, team: str) -> Tuple[bool, str]:
        """Join a battleground."""
        bg = self._battlegrounds.get(bg_id)
        if not bg:
            return False, "Battleground not found."

        ok, msg = bg.add_player(character, team)
        if ok:
            self._player_bg[character.id] = bg_id
        return ok, msg

    def leave_battleground(self, character: Any) -> Tuple[bool, str]:
        """Leave current battleground."""
        bg = self.get_player_battleground(character)
        if not bg:
            return False, "You are not in a battleground."

        bg.remove_player(character)
        self._player_bg.pop(character.id, None)
        return True, "You have left the battleground."

    def list_battlegrounds(self) -> List[Dict[str, Any]]:
        """List all active/waiting battlegrounds."""
        result = []
        for bg in self._battlegrounds.values():
            if bg.status in ("waiting", "active"):
                result.append({
                    "bg_id": bg.bg_id,
                    "type": bg.bg_type,
                    "name": bg.config["name"],
                    "status": bg.status,
                    "team_a_count": len(bg.team_a),
                    "team_b_count": len(bg.team_b),
                    "time_remaining": bg.time_remaining if bg.status == "active" else None,
                })
        return result

    def cleanup_expired(self) -> int:
        """End and remove expired battlegrounds."""
        count = 0
        now = time.time()
        for bg_id in list(self._battlegrounds.keys()):
            bg = self._battlegrounds[bg_id]
            if bg.status == "active" and bg.ends_at and now >= bg.ends_at:
                bg.end()
                # Remove player mappings
                for p in bg.team_a + bg.team_b:
                    self._player_bg.pop(p.id, None)
                count += 1
            elif bg.status == "completed" and bg.ends_at and now - bg.ends_at > 300:
                # Remove completed BGs after 5 minutes
                del self._battlegrounds[bg_id]
        return count


# Global battleground manager
battleground_manager = BattlegroundManager()


# ===========================================================================
# DUEL / WAGER SYSTEM
# ===========================================================================

class DuelChallenge:
    """Represents a duel challenge between two players."""

    def __init__(self, challenger: Any, target: Any, wager_gold: int = 0,
                 wager_items: Optional[List[str]] = None,
                 duel_type: str = "to_the_death"):
        self.challenger = challenger
        self.target = target
        self.wager_gold = wager_gold
        self.wager_items = wager_items or []
        self.duel_type = duel_type  # "to_the_death", "first_blood", "friendly"
        self.status = "pending"  # pending, accepted, declined, active, completed
        self.winner: Optional[Any] = None
        self.created_at = time.time()
        self.accepted_at: Optional[float] = None
        self.duel_id = f"duel_{uuid.uuid4().hex[:8]}"

    def accept(self) -> Tuple[bool, str]:
        """Accept the duel challenge."""
        if self.status != "pending":
            return False, "This duel is no longer pending."

        # Verify target can afford the wager
        if self.wager_gold > 0:
            target_gold = self.target.attributes.get("gold", default=0)
            if target_gold < self.wager_gold:
                return False, f"{self.target.key} cannot afford the {self.wager_gold} gold wager."

            challenger_gold = self.challenger.attributes.get("gold", default=0)
            if challenger_gold < self.wager_gold:
                return False, f"{self.challenger.key} cannot afford the {self.wager_gold} gold wager."

            # Escrow the gold
            self.challenger.attributes.add("gold", challenger_gold - self.wager_gold)
            self.target.attributes.add("gold", target_gold - self.wager_gold)

        self.status = "accepted"
        self.accepted_at = time.time()
        return True, "Duel accepted! Prepare to fight!"

    def decline(self) -> Tuple[bool, str]:
        """Decline the duel challenge."""
        if self.status != "pending":
            return False, "This duel is no longer pending."
        self.status = "declined"
        return True, "Duel declined."

    def resolve(self, winner: Any, loser: Any) -> Tuple[bool, str]:
        """
        Resolve the duel with a winner.

        Returns:
            (success, message)
        """
        if self.status not in ("accepted", "active"):
            return False, "Duel is not in a resolvable state."

        self.status = "completed"
        self.winner = winner

        # Pay out wager
        if self.wager_gold > 0:
            winner_gold = winner.attributes.get("gold", default=0)
            winner.attributes.add("gold", winner_gold + self.wager_gold * 2)
            winner.msg(f"|Y|h[Duel] You win the duel and claim {self.wager_gold * 2} gold!|n")
            loser.msg(f"|r[Duel] You lost the duel and forfeit {self.wager_gold} gold.|n")

        # Record duel stats
        for char, result in [(winner, "win"), (loser, "loss")]:
            duels_won = char.attributes.get("duels_won", default=0)
            duels_lost = char.attributes.get("duels_lost", default=0)
            if result == "win":
                char.attributes.add("duels_won", duels_won + 1)
            else:
                char.attributes.add("duels_lost", duels_lost + 1)

        return True, f"Duel complete! {winner.key} is victorious!"


class DuelManager:
    """Manages all duel challenges."""

    def __init__(self):
        self._challenges: Dict[str, DuelChallenge] = {}
        self._player_duel: Dict[int, str] = {}  # dbref -> duel_id

    def challenge(self, challenger: Any, target: Any, wager_gold: int = 0,
                  duel_type: str = "to_the_death") -> Tuple[bool, str]:
        """
        Issue a duel challenge.

        Args:
            challenger: The player issuing the challenge.
            target: The player being challenged.
            wager_gold: Amount of gold to wager (each side).
            duel_type: "to_the_death", "first_blood", or "friendly".

        Returns:
            (success, message)
        """
        # Check if either player is already in a duel
        if self._player_duel.get(challenger.id):
            return False, "You are already in a duel challenge."
        if self._player_duel.get(target.id):
            return False, f"{target.key} is already in a duel challenge."

        # Check same room
        if challenger.location != target.location:
            return False, "You must be in the same room to challenge someone."

        # Check PvP status
        if not getattr(target.db, "pvp_enabled", False):
            return False, f"{target.key} does not have PvP enabled."

        # Verify wager
        if wager_gold > 0:
            challenger_gold = challenger.attributes.get("gold", default=0)
            if challenger_gold < wager_gold:
                return False, f"You don't have {wager_gold} gold to wager."

        duel = DuelChallenge(challenger, target, wager_gold, duel_type=duel_type)
        self._challenges[duel.duel_id] = duel
        self._player_duel[challenger.id] = duel.duel_id
        self._player_duel[target.id] = duel.duel_id

        # Notify target
        wager_msg = f" with a |Y{wager_gold} gold|n wager" if wager_gold > 0 else ""
        target.msg(
            f"|Y|h[Duel] {challenger.key} has challenged you to a duel{wager_msg}!|n\n"
            f"|wType |yduel accept|w to accept or |rduel decline|w to decline.|n"
        )
        challenger.msg(f"|g[Duel] You have challenged {target.key} to a duel{wager_msg}.|n")

        return True, f"Duel challenge sent to {target.key}."

    def accept(self, character: Any) -> Tuple[bool, str]:
        """Accept a pending duel challenge."""
        duel_id = self._player_duel.get(character.id)
        if not duel_id:
            return False, "You have no pending duel challenges."

        duel = self._challenges.get(duel_id)
        if not duel:
            return False, "Duel challenge not found."

        if duel.target != character:
            return False, "You can only accept challenges sent to you."

        ok, msg = duel.accept()
        if ok:
            duel.status = "active"
            duel.challenger.msg(f"|Y|h[Duel] {character.key} has accepted your challenge! FIGHT!|n")
            character.msg(f"|Y|h[Duel] You have accepted {duel.challenger.key}'s challenge! FIGHT!|n")
        return ok, msg

    def decline(self, character: Any) -> Tuple[bool, str]:
        """Decline a pending duel challenge."""
        duel_id = self._player_duel.get(character.id)
        if not duel_id:
            return False, "You have no pending duel challenges."

        duel = self._challenges.get(duel_id)
        if not duel:
            return False, "Duel challenge not found."

        ok, msg = duel.decline()
        if ok:
            # Refund wager if any
            if duel.wager_gold > 0 and duel.status == "accepted":
                challenger_gold = duel.challenger.attributes.get("gold", default=0)
                duel.challenger.attributes.add("gold", challenger_gold + duel.wager_gold)
                target_gold = duel.target.attributes.get("gold", default=0)
                duel.target.attributes.add("gold", target_gold + duel.wager_gold)

            duel.challenger.msg(f"|y[Duel] {character.key} has declined your challenge.|n")
            character.msg(f"|y[Duel] You declined {duel.challenger.key}'s challenge.|n")

            self._player_duel.pop(duel.challenger.id, None)
            self._player_duel.pop(duel.target.id, None)
            del self._challenges[duel_id]
        return ok, msg

    def get_player_duel(self, character: Any) -> Optional[DuelChallenge]:
        """Get the active duel for a player."""
        duel_id = self._player_duel.get(character.id)
        if duel_id:
            return self._challenges.get(duel_id)
        return None

    def resolve_duel(self, winner: Any, loser: Any) -> Tuple[bool, str]:
        """Resolve a duel when one player is defeated."""
        duel = self.get_player_duel(winner)
        if not duel:
            duel = self.get_player_duel(loser)
        if not duel:
            return False, "No active duel found."

        ok, msg = duel.resolve(winner, loser)
        if ok:
            self._player_duel.pop(duel.challenger.id, None)
            self._player_duel.pop(duel.target.id, None)
            # Keep in _challenges for history, clean up later
        return ok, msg


# Global duel manager
duel_manager = DuelManager()


# ===========================================================================
# BOUNTY BOARD SYSTEM
# ===========================================================================

class Bounty:
    """Represents a bounty placed on a player."""

    def __init__(self, bounty_id: str, target_name: str, placed_by: str,
                 reward_gold: int, reason: str = "", target_faction: str = ""):
        self.bounty_id = bounty_id
        self.target_name = target_name  # Player name (not object, may be offline)
        self.placed_by = placed_by
        self.reward_gold = reward_gold
        self.reason = reason
        self.target_faction = target_faction
        self.status = "active"  # active, claimed, expired
        self.created_at = time.time()
        self.expires_at = time.time() + 604800  # 7 days
        self.claimed_by: Optional[str] = None
        self.claimed_at: Optional[float] = None

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def time_remaining_str(self) -> str:
        remaining = max(0, int(self.expires_at - time.time()))
        days = remaining // 86400
        hours = (remaining % 86400) // 3600
        return f"{days}d {hours}h"


class BountyBoard:
    """
    Manages the bounty board system.

    Players can:
      - Place bounties on other players (costs gold)
      - View active bounties
      - Claim bounties by killing the target
      - Collect bounty rewards
    """

    def __init__(self):
        self._bounties: Dict[str, Bounty] = {}
        self._bounty_escrow: Dict[str, int] = {}  # bounty_id -> escrowed gold

    def place_bounty(self, placer: Any, target_name: str, reward_gold: int,
                     reason: str = "") -> Tuple[bool, str]:
        """
        Place a bounty on a player.

        Args:
            placer: The character placing the bounty.
            target_name: Name of the target player.
            reward_gold: Gold reward for completing the bounty.
            reason: Optional reason for the bounty.

        Returns:
            (success, message)
        """
        # Validate
        if reward_gold < 100:
            return False, "Minimum bounty reward is 100 gold."
        if reward_gold > 100000:
            return False, "Maximum bounty reward is 100,000 gold."

        # Check if placer can afford it
        placer_gold = placer.attributes.get("gold", default=0)
        if placer_gold < reward_gold:
            return False, f"You don't have {reward_gold} gold."

        # Check if target exists (online or offline)
        target_found = False
        target_faction = ""
        try:
            from evennia import search_object
            targets = search_object(target_name)
            for t in targets:
                if hasattr(t, 'has_account') and t.has_account:
                    target_found = True
                    target_faction = t.attributes.get("alignment", "")
                    break
        except Exception:
            pass

        if not target_found:
            return False, f"Player '{target_name}' not found."

        # Cannot bounty yourself
        if target_name.lower() == placer.key.lower():
            return False, "You cannot place a bounty on yourself."

        # Check for existing active bounty on this target
        for bounty in self._bounties.values():
            if bounty.target_name.lower() == target_name.lower() and bounty.status == "active":
                return False, f"There is already an active bounty on {target_name}."

        # Deduct gold and escrow it
        placer.attributes.add("gold", placer_gold - reward_gold)

        bounty_id = f"bounty_{uuid.uuid4().hex[:8]}"
        bounty = Bounty(bounty_id, target_name, placer.key, reward_gold,
                        reason, target_faction)
        self._bounties[bounty_id] = bounty
        self._bounty_escrow[bounty_id] = reward_gold

        # Announce
        try:
            from evennia.objects.models import ObjectDB
            from typeclasses.characters import Character
            announcement = (
                f"|R|h[BOUNTY] {placer.key} has placed a {reward_gold} gold bounty "
                f"on {target_name}!|n"
            )
            if reason:
                announcement += f" |wReason: {reason}|n"
            for char in ObjectDB.objects.all():
                if isinstance(char, Character) and hasattr(char, 'sessions') and char.sessions.count() > 0:
                    char.msg(announcement)
        except Exception:
            pass

        return True, f"Bounty of {reward_gold} gold placed on {target_name}."

    def claim_bounty(self, hunter: Any, target: Any) -> Tuple[bool, str]:
        """
        Claim a bounty by killing the target.

        Args:
            hunter: The player who killed the target.
            target: The defeated player.

        Returns:
            (success, message)
        """
        # Find active bounty on this target
        target_bounty = None
        for bounty in self._bounties.values():
            if (bounty.target_name.lower() == target.key.lower()
                    and bounty.status == "active"):
                target_bounty = bounty
                break

        if not target_bounty:
            return False, f"No active bounty on {target.key}."

        # Cannot claim your own bounty
        if hunter.key.lower() == target_bounty.placed_by.lower():
            return False, "You cannot claim a bounty you placed yourself."

        # Mark as claimed
        target_bounty.status = "claimed"
        target_bounty.claimed_by = hunter.key
        target_bounty.claimed_at = time.time()

        # Pay out reward
        reward = target_bounty.reward_gold
        hunter_gold = hunter.attributes.get("gold", default=0)
        hunter.attributes.add("gold", hunter_gold + reward)

        # Track bounty hunter stats
        bounties_claimed = hunter.attributes.get("bounties_claimed", default=0)
        hunter.attributes.add("bounties_claimed", bounties_claimed + 1)
        bounty_gold_earned = hunter.attributes.get("bounty_gold_earned", default=0)
        hunter.attributes.add("bounty_gold_earned", bounty_gold_earned + reward)

        # Announce
        try:
            from evennia.objects.models import ObjectDB
            from typeclasses.characters import Character
            announcement = (
                f"|Y|h[BOUNTY CLAIMED] {hunter.key} has claimed the {reward} gold "
                f"bounty on {target.key}!|n"
            )
            for char in ObjectDB.objects.all():
                if isinstance(char, Character) and hasattr(char, 'sessions') and char.sessions.count() > 0:
                    char.msg(announcement)
        except Exception:
            pass

        hunter.msg(f"|Y|h[BOUNTY] You have claimed the {reward} gold bounty on {target.key}!|n")
        return True, f"Bounty claimed! You receive {reward} gold."

    def list_bounties(self, filter_faction: str = "") -> List[Dict[str, Any]]:
        """List all active bounties."""
        result = []
        for bounty in self._bounties.values():
            if bounty.status != "active":
                continue
            if bounty.is_expired:
                bounty.status = "expired"
                continue
            if filter_faction and bounty.target_faction != filter_faction:
                continue
            result.append({
                "bounty_id": bounty.bounty_id,
                "target": bounty.target_name,
                "reward": bounty.reward_gold,
                "placed_by": bounty.placed_by,
                "reason": bounty.reason,
                "faction": bounty.target_faction,
                "expires": bounty.time_remaining_str,
            })
        # Sort by reward descending
        result.sort(key=lambda x: x["reward"], reverse=True)
        return result

    def get_bounty_stats(self, character: Any) -> Dict[str, Any]:
        """Get bounty-related stats for a character."""
        return {
            "bounties_claimed": character.attributes.get("bounties_claimed", default=0),
            "bounty_gold_earned": character.attributes.get("bounty_gold_earned", default=0),
            "bounties_placed": sum(
                1 for b in self._bounties.values()
                if b.placed_by.lower() == character.key.lower()
            ),
        }

    def cancel_bounty(self, character: Any, bounty_id: str) -> Tuple[bool, str]:
        """Cancel a bounty you placed (refunds 50% of reward)."""
        bounty = self._bounties.get(bounty_id)
        if not bounty:
            return False, "Bounty not found."
        if bounty.placed_by.lower() != character.key.lower():
            return False, "You can only cancel your own bounties."
        if bounty.status != "active":
            return False, "This bounty is no longer active."

        bounty.status = "expired"
        refund = bounty.reward_gold // 2
        char_gold = character.attributes.get("gold", default=0)
        character.attributes.add("gold", char_gold + refund)
        return True, f"Bounty cancelled. You receive a {refund} gold refund (50%)."

    def cleanup_expired(self) -> int:
        """Mark expired bounties and return count."""
        count = 0
        for bounty in self._bounties.values():
            if bounty.status == "active" and bounty.is_expired:
                bounty.status = "expired"
                count += 1
        return count


# Global bounty board
bounty_board = BountyBoard()