"""
PvP Commands for 'rop'
=======================
Commands for Arena, Battlegrounds, Duels, and Bounty Board.

Commands:
  arena queue <type>     - Join arena queue (1v1, 2v2, 3v3, ranked/unranked)
  arena leave            - Leave arena queue
  arena status           - Show arena status/ELO
  arena leaderboard      - Show arena rankings
  arena forfeit          - Forfeit current match

  bg list                - List active battlegrounds
  bg join <id> <team>    - Join a battleground
  bg leave               - Leave current battleground
  bg status              - Show battleground status

  duel <target> [wager]  - Challenge someone to a duel
  duel accept            - Accept a duel challenge
  duel decline           - Decline a duel challenge
  duel status            - Show duel status

  bounty place <target> <gold> [reason]  - Place a bounty
  bounty list [faction]  - List active bounties
  bounty stats           - Show bounty hunter stats
  bounty cancel <id>     - Cancel a bounty you placed
"""

from commands.command import Command


class CmdArenaQueue(Command):
    """
    Join an arena queue for structured PvP.

    Usage:
      arena queue <type>
      arena leave
      arena status
      arena leaderboard
      arena forfeit

    Queue types:
      1v1_unranked, 1v1_ranked, 2v2_unranked, 2v2_ranked,
      3v3_unranked, 3v3_ranked

    Ranked matches affect your ELO rating. Unranked are for practice.
    """

    key = "arena"
    aliases = []
    locks = "cmd:all()"
    help_category = "PvP"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        from world.pvp_systems import arena_manager

        if not args:
            caller.msg("Usage: arena queue <type> | leave | status | leaderboard | forfeit")
            return

        parts = args.split(None, 1)
        subcmd = parts[0]
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "queue":
            if not subargs:
                caller.msg("Queue types: 1v1_unranked, 1v1_ranked, 2v2_unranked, 2v2_ranked, 3v3_unranked, 3v3_ranked")
                return
            ok, msg = arena_manager.join_queue(caller, subargs)
            caller.msg(msg)

        elif subcmd == "leave":
            ok, msg = arena_manager.leave_queue(caller)
            caller.msg(msg)

        elif subcmd == "status":
            match = arena_manager.get_player_match(caller)
            if match:
                a_names, b_names = match.get_team_names()
                caller.msg(f"|Y|hActive Match:|n {match.match_type} {'(Ranked)' if match.ranked else '(Unranked)'}")
                caller.msg(f"  Team A: {a_names}")
                caller.msg(f"  Team B: {b_names}")
                caller.msg(f"  Duration: {int(match.duration_seconds)}s")
            else:
                elo = arena_manager.get_elo(caller)
                pts = caller.attributes.get("arena_points", default=0)
                caller.msg(f"|wArena Status:|n Not in a match.")
                caller.msg(f"  ELO Rating: {elo}")
                caller.msg(f"  Arena Points: {pts}")
                history = arena_manager.get_match_history(caller)
                wins = sum(1 for h in history if h["result"] == "win")
                losses = sum(1 for h in history if h["result"] == "loss")
                caller.msg(f"  Record: {wins}W - {losses}L")

        elif subcmd == "leaderboard":
            lb = arena_manager.get_leaderboard(10)
            if not lb:
                caller.msg("No ranked matches have been played yet.")
                return
            caller.msg("|Y|hArena Leaderboard (Top 10):|n")
            for i, (dbref, elo) in enumerate(lb, 1):
                try:
                    from evennia import search_object
                    chars = search_object(f"#{dbref}")
                    name = chars[0].key if chars else f"Unknown({dbref})"
                except Exception:
                    name = f"Unknown({dbref})"
                caller.msg(f"  {i}. {name} - {elo} ELO")

        elif subcmd == "forfeit":
            ok, msg = arena_manager.forfeit_match(caller)
            caller.msg(msg)

        else:
            caller.msg("Usage: arena queue <type> | leave | status | leaderboard | forfeit")


class CmdBattleground(Command):
    """
    Join battlegrounds for large-scale faction PvP.

    Usage:
      bg list                    - List active battlegrounds
      bg join <id> <team>        - Join a battleground (team: a or b)
      bg leave                   - Leave current battleground
      bg status                  - Show battleground status
      bg create <type>           - Create a new battleground (admin)

    Battleground types:
      ctf         - Capture the Flag
      faction_war - Faction War (Good vs Evil)
      koth        - King of the Hill
    """

    key = "bg"
    aliases = ["battleground"]
    locks = "cmd:all()"
    help_category = "PvP"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        from world.pvp_systems import battleground_manager

        if not args:
            caller.msg("Usage: bg list | join <id> <team> | leave | status | create <type>")
            return

        parts = args.split(None, 2)
        subcmd = parts[0]

        if subcmd == "list":
            bgs = battleground_manager.list_battlegrounds()
            if not bgs:
                caller.msg("No active battlegrounds. Create one with 'bg create <type>'.")
                return
            caller.msg("|Y|hActive Battlegrounds:|n")
            for bg in bgs:
                status_color = "|g" if bg["status"] == "active" else "|y"
                caller.msg(
                    f"  [{bg['bg_id'][:8]}] {bg['name']} ({bg['type']}) "
                    f"{status_color}{bg['status']}|n - "
                    f"Team A: {bg['team_a_count']} | Team B: {bg['team_b_count']}"
                )
                if bg["time_remaining"]:
                    caller.msg(f"    Time remaining: {bg['time_remaining']}s")

        elif subcmd == "join":
            if len(parts) < 3:
                caller.msg("Usage: bg join <id> <team>  (team: a or b)")
                return
            bg_id = parts[1]
            team = "team_a" if parts[2] == "a" else "team_b"
            ok, msg = battleground_manager.join_battleground(caller, bg_id, team)
            caller.msg(msg)

        elif subcmd == "leave":
            ok, msg = battleground_manager.leave_battleground(caller)
            caller.msg(msg)

        elif subcmd == "status":
            bg = battleground_manager.get_player_battleground(caller)
            if not bg:
                caller.msg("You are not in a battleground.")
                return
            caller.msg(f"|Y|hBattleground: {bg.config['name']} ({bg.bg_type})|n")
            caller.msg(f"  Status: {bg.status}")
            caller.msg(f"  Team A: {len(bg.team_a)} players | Score: {bg.team_a_score} | Kills: {bg.team_a_kills}")
            caller.msg(f"  Team B: {len(bg.team_b)} players | Score: {bg.team_b_score} | Kills: {bg.team_b_kills}")
            if bg.status == "active":
                caller.msg(f"  Time remaining: {bg.time_remaining}s")

        elif subcmd == "create":
            if len(parts) < 2:
                caller.msg("Usage: bg create <type>  (ctf, faction_war, koth)")
                return
            bg_type = parts[1]
            bg, msg = battleground_manager.create_battleground(bg_type)
            if bg:
                caller.msg(f"|g{msg}|n")
                caller.msg(f"Battleground ID: {bg.bg_id}")
                caller.msg(f"Tell others to join with: bg join {bg.bg_id} a  or  bg join {bg.bg_id} b")
            else:
                caller.msg(f"|r{msg}|n")

        else:
            caller.msg("Usage: bg list | join <id> <team> | leave | status | create <type>")


class CmdDuel(Command):
    """
    Challenge another player to a duel with optional gold wager.

    Usage:
      duel <target> [wager]    - Challenge someone to a duel
      duel accept              - Accept a pending duel challenge
      duel decline             - Decline a pending duel challenge
      duel status              - Show your duel status

    Examples:
      duel Bob                 - Challenge Bob to a friendly duel
      duel Bob 500             - Challenge Bob with 500 gold wager
      duel accept              - Accept the challenge
    """

    key = "duel"
    aliases = []
    locks = "cmd:all()"
    help_category = "PvP"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        from world.pvp_systems import duel_manager

        if not args:
            caller.msg("Usage: duel <target> [wager] | accept | decline | status")
            return

        parts = args.split(None, 2)
        subcmd = parts[0].lower()

        if subcmd == "accept":
            ok, msg = duel_manager.accept(caller)
            caller.msg(msg)

        elif subcmd == "decline":
            ok, msg = duel_manager.decline(caller)
            caller.msg(msg)

        elif subcmd == "status":
            duel = duel_manager.get_player_duel(caller)
            if not duel:
                caller.msg("You are not in any duel.")
                return
            caller.msg(f"|Y|hDuel Status:|n")
            caller.msg(f"  Challenger: {duel.challenger.key}")
            caller.msg(f"  Target: {duel.target.key}")
            caller.msg(f"  Status: {duel.status}")
            if duel.wager_gold > 0:
                caller.msg(f"  Wager: {duel.wager_gold} gold each")
            if duel.winner:
                caller.msg(f"  Winner: {duel.winner.key}")

        else:
            # Challenge a target
            target_name = parts[0]
            wager = 0
            if len(parts) > 1:
                try:
                    wager = int(parts[1])
                except ValueError:
                    caller.msg("Wager must be a number (gold amount).")
                    return

            # Find target in room
            target = None
            location = caller.location
            if location:
                for obj in location.contents:
                    if obj.key.lower() == target_name.lower() and obj != caller:
                        target = obj
                        break

            if not target:
                caller.msg(f"Cannot find '{target_name}' in the room.")
                return

            ok, msg = duel_manager.challenge(caller, target, wager)
            caller.msg(msg)


class CmdBounty(Command):
    """
    Place and manage bounties on other players.

    Usage:
      bounty place <target> <gold> [reason]  - Place a bounty
      bounty list [faction]                  - List active bounties
      bounty stats                           - Show your bounty stats
      bounty cancel <id>                     - Cancel a bounty you placed

    Bounties are claimed automatically when you kill the target.
    Minimum bounty: 100 gold. Maximum: 100,000 gold.
    """

    key = "bounty"
    aliases = ["bounties"]
    locks = "cmd:all()"
    help_category = "PvP"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        from world.pvp_systems import bounty_board

        if not args:
            caller.msg("Usage: bounty place <target> <gold> [reason] | list | stats | cancel <id>")
            return

        parts = args.split(None, 2)
        subcmd = parts[0].lower()

        if subcmd == "place":
            if len(parts) < 3:
                caller.msg("Usage: bounty place <target> <gold> [reason]")
                return
            target_name = parts[1]
            try:
                gold = int(parts[2])
            except ValueError:
                caller.msg("Gold amount must be a number.")
                return
            reason = ""
            if len(parts) > 2:
                # Reason is everything after gold
                remaining = args.split(None, 3)
                if len(remaining) > 3:
                    reason = remaining[3]

            ok, msg = bounty_board.place_bounty(caller, target_name, gold, reason)
            caller.msg(msg)

        elif subcmd == "list":
            faction = parts[1] if len(parts) > 1 else ""
            bounties = bounty_board.list_bounties(faction)
            if not bounties:
                caller.msg("No active bounties.")
                return
            caller.msg("|R|hActive Bounties:|n")
            for b in bounties[:20]:
                caller.msg(
                    f"  [{b['bounty_id'][:8]}] |Y{b['target']}|n - "
                    f"|Y{b['reward']} gold|n by {b['placed_by']} "
                    f"({b['faction']}) - Expires in {b['expires']}"
                )
                if b["reason"]:
                    caller.msg(f"    Reason: {b['reason']}")

        elif subcmd == "stats":
            stats = bounty_board.get_bounty_stats(caller)
            caller.msg("|Y|hBounty Stats:|n")
            caller.msg(f"  Bounties Claimed: {stats['bounties_claimed']}")
            caller.msg(f"  Gold Earned: {stats['bounty_gold_earned']}")
            caller.msg(f"  Bounties Placed: {stats['bounties_placed']}")

        elif subcmd == "cancel":
            if len(parts) < 2:
                caller.msg("Usage: bounty cancel <bounty_id>")
                return
            ok, msg = bounty_board.cancel_bounty(caller, parts[1])
            caller.msg(msg)

        else:
            caller.msg("Usage: bounty place <target> <gold> [reason] | list | stats | cancel <id>")