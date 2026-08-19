"""
GMCP (Generic MUD Communication Protocol) Bridge for 'rop'
===========================================================

Provides structured JSON data push to GMCP-capable telnet clients
(Mudlet, MUSHclient, etc.) for rich GUI modules: health bars,
mini-maps, combat trackers, and status displays.

Evennia's portal auto-negotiates GMCP via IAC on telnet connect.
This module hooks into the character lifecycle to push data packages
whenever the character's state changes.

Architecture:
  - ``send_gmcp(session, package, data)`` — sends a GMCP package to
    a specific session.
  - ``push_char_vitals(character)`` — sends Char.Vitals to all of a
    character's GMCP-capable sessions.
  - ``push_room_info(character)`` — sends Room.Info on room entry.
  - ``push_combat_info(character)`` — sends Combat.Info when combat
    state changes.

Usage (from character hooks):
    from world.gmcp_handler import push_char_vitals, push_room_info
    push_char_vitals(character)
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Core send function
# ---------------------------------------------------------------------------

def _get_gmcp_sessions(character) -> List[Any]:
    """
    Return all sessions attached to this character that support GMCP.

    Evennia stores OOB capability flags on the session's protocol handler.
    We check ``session.protocol_flags.get("OOB")`` and the GMCP-specific
    flag on the TelnetOOB handler.
    """
    sessions = []
    try:
        for session in character.sessions.all():
            # Check if this session negotiated GMCP
            protocol = getattr(session, 'protocol', None)
            if protocol is None:
                continue
            flags = getattr(protocol, 'protocol_flags', {})
            if flags.get('OOB') and flags.get('GMCP'):
                sessions.append(session)
    except Exception:
        pass
    return sessions


def send_gmcp(session, package: str, data: Dict[str, Any]) -> bool:
    """
    Send a GMCP package to a single session.

    Args:
        session: An Evennia session object.
        package: GMCP package name (e.g. 'Char.Vitals').
        data: Dictionary to JSON-serialize as the package payload.

    Returns:
        True if the package was queued for sending, False otherwise.
    """
    try:
        # Evennia's session.msg() accepts an oob= keyword that
        # triggers data_out() on the telnet OOB handler.
        json_str = json.dumps(data, separators=(',', ':'))
        session.msg(oob=(package, json_str))
        return True
    except Exception:
        return False


def broadcast_gmcp(character, package: str, data: Dict[str, Any]) -> int:
    """
    Send a GMCP package to all GMCP-capable sessions of a character.

    Returns:
        Number of sessions the package was sent to.
    """
    count = 0
    for session in _get_gmcp_sessions(character):
        if send_gmcp(session, package, data):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Package builders
# ---------------------------------------------------------------------------

def build_char_vitals(character) -> Dict[str, Any]:
    """
    Build the Char.Vitals GMCP package.

    Sent after every command (via at_pre_cmd) so the client always
    has current HP, mana, stamina, and XP values.
    """
    hp = character.attributes.get("hp", default=100)
    max_hp = character.attributes.get("max_hp", default=100)
    mana = character.attributes.get("mana", default=50)
    max_mana = character.attributes.get("max_mana", default=50)
    mv = character.attributes.get("mv", default=100)
    max_mv = character.attributes.get("max_mv", default=100)
    stamina = character.attributes.get("stamina", default=100)
    max_stamina = character.attributes.get("max_stamina", default=100)
    xp = character.attributes.get("xp", default=0)
    xp_to_level = character.attributes.get("xp_to_level", default=1000)
    level = character.attributes.get("level", default=1)
    alignment = character.attributes.get("alignment", default="Neutral")

    # Combat state
    try:
        from world.tick_combat import CombatHandler
        in_combat = CombatHandler.is_in_combat(character)
    except Exception:
        in_combat = False

    # Position
    position = character.attributes.get("position", default="standing")

    # Gold
    try:
        from world.economy import get_gold_amount
        gold = get_gold_amount(character)
    except Exception:
        gold = 0

    return {
        "hp": hp,
        "max_hp": max_hp,
        "mana": mana,
        "max_mana": max_mana,
        "mv": mv,
        "max_mv": max_mv,
        "stamina": stamina,
        "max_stamina": max_stamina,
        "xp": xp,
        "xp_to_level": xp_to_level,
        "level": level,
        "gold": gold,
        "alignment": alignment,
        "position": position,
        "in_combat": in_combat,
    }


def build_room_info(character) -> Optional[Dict[str, Any]]:
    """
    Build the Room.Info GMCP package.

    Sent when the character enters a new room.  Includes room name,
    description, exits, visible players, and visible mobs.
    """
    location = character.location
    if location is None:
        return None

    # Exits
    exits = []
    try:
        for exit_obj in location.exits:
            exits.append({
                "name": exit_obj.key,
                "aliases": list(exit_obj.aliases.all()) if hasattr(exit_obj, 'aliases') else [],
            })
    except Exception:
        pass

    # Visible players (excluding self)
    players = []
    try:
        for obj in location.contents:
            if obj != character and hasattr(obj, 'has_account') and obj.has_account:
                players.append({
                    "name": obj.key,
                    "level": obj.attributes.get("level", default=1),
                })
    except Exception:
        pass

    # Visible mobs
    mobs = []
    try:
        for obj in location.contents:
            if obj != character and hasattr(obj, 'attributes'):
                is_mob = obj.attributes.get("is_mob", False)
                if is_mob:
                    mobs.append({
                        "name": obj.key,
                        "level": obj.attributes.get("level", default=1),
                        "hp": obj.attributes.get("hp", default=100),
                        "max_hp": obj.attributes.get("max_hp", default=100),
                    })
    except Exception:
        pass

    # Zone info
    zone = location.attributes.get("zone", default="Unknown")
    terrain = location.attributes.get("terrain", default="indoor")
    is_safe = location.attributes.get("safe_zone", False)

    return {
        "name": location.key,
        "zone": zone,
        "terrain": terrain,
        "is_safe": is_safe,
        "exits": exits,
        "players": players,
        "mobs": mobs,
    }


def build_combat_info(character) -> Optional[Dict[str, Any]]:
    """
    Build the Combat.Info GMCP package.

    Sent when combat state changes.  Includes target info and
    active combat status.
    """
    try:
        from world.tick_combat import CombatHandler
    except Exception:
        return None

    if not CombatHandler.is_in_combat(character):
        return {"active": False}

    target = character.ndb.combat_target
    if target is None:
        return {"active": False}

    return {
        "active": True,
        "target": target.key,
        "target_hp": target.attributes.get("hp", default=0),
        "target_max_hp": target.attributes.get("max_hp", default=100),
        "target_level": target.attributes.get("level", default=1),
    }


# ---------------------------------------------------------------------------
# Convenience push functions (called from character hooks)
# ---------------------------------------------------------------------------

def push_char_vitals(character) -> int:
    """
    Push Char.Vitals to all GMCP-capable sessions.

    Called from Character.at_pre_cmd() after every command.
    """
    data = build_char_vitals(character)
    return broadcast_gmcp(character, "Char.Vitals", data)


def push_room_info(character) -> int:
    """
    Push Room.Info to all GMCP-capable sessions.

    Called from Character.at_after_move() when entering a new room.
    """
    data = build_room_info(character)
    if data is None:
        return 0
    return broadcast_gmcp(character, "Room.Info", data)


def push_combat_info(character) -> int:
    """
    Push Combat.Info to all GMCP-capable sessions.

    Called when combat starts, ends, or the target changes.
    """
    data = build_combat_info(character)
    if data is None:
        return 0
    return broadcast_gmcp(character, "Combat.Info", data)