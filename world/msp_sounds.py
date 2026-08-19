"""
MSP (MUD Sound Protocol) Sound Registry for 'rop'
==================================================

Defines the sound events used by Evennia's MSP telnet subsystem.
Clients that support MSP (Mudlet, MUSHclient, etc.) will play
these sounds when the corresponding events are triggered.

Architecture:
  - ``TRIGGER_SOUND_MAP`` maps in-game trigger keys to sound file URLs.
  - ``send_msp_sound(session, trigger_key)`` sends an MSP sound command
    to a specific telnet session.
  - ``broadcast_msp_sound(room, trigger_key)`` sends to all telnet
    sessions in a room.

Sound files should be hosted at a public URL accessible to clients.
Default URLs point to a CDN-hosted fantasy sound pack.

Usage:
    from world.msp_sounds import send_msp_sound
    send_msp_sound(session, "combat_hit")
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Sound trigger → URL mapping
# ---------------------------------------------------------------------------

# Base URL for sound files. Override this to point to your own sound server.
SOUND_BASE_URL = "https://cdn.dirtysouthjosh.com/rop/sounds"

# Volume: 0-100
# Priority: 0-100 (higher = more important)
# Type: "sound" | "music" | "loop" | "stop"
# Loops: number of repeats, -1 = infinite

TRIGGER_SOUND_MAP: Dict[str, Dict[str, Any]] = {
    # ---- Combat ----
    "combat_hit": {
        "url": f"{SOUND_BASE_URL}/combat_hit.ogg",
        "volume": 70,
        "priority": 50,
        "type": "sound",
        "loops": 1,
    },
    "combat_miss": {
        "url": f"{SOUND_BASE_URL}/combat_miss.ogg",
        "volume": 50,
        "priority": 40,
        "type": "sound",
        "loops": 1,
    },
    "combat_crit": {
        "url": f"{SOUND_BASE_URL}/combat_crit.ogg",
        "volume": 80,
        "priority": 60,
        "type": "sound",
        "loops": 1,
    },
    "combat_death": {
        "url": f"{SOUND_BASE_URL}/combat_death.ogg",
        "volume": 85,
        "priority": 70,
        "type": "sound",
        "loops": 1,
    },
    "combat_victory": {
        "url": f"{SOUND_BASE_URL}/combat_victory.ogg",
        "volume": 75,
        "priority": 55,
        "type": "sound",
        "loops": 1,
    },
    "combat_flee": {
        "url": f"{SOUND_BASE_URL}/combat_flee.ogg",
        "volume": 60,
        "priority": 45,
        "type": "sound",
        "loops": 1,
    },

    # ---- Magic ----
    "spell_cast": {
        "url": f"{SOUND_BASE_URL}/spell_cast.ogg",
        "volume": 65,
        "priority": 45,
        "type": "sound",
        "loops": 1,
    },
    "spell_heal": {
        "url": f"{SOUND_BASE_URL}/spell_heal.ogg",
        "volume": 70,
        "priority": 50,
        "type": "sound",
        "loops": 1,
    },
    "spell_damage": {
        "url": f"{SOUND_BASE_URL}/spell_damage.ogg",
        "volume": 75,
        "priority": 50,
        "type": "sound",
        "loops": 1,
    },
    "spell_buff": {
        "url": f"{SOUND_BASE_URL}/spell_buff.ogg",
        "volume": 60,
        "priority": 40,
        "type": "sound",
        "loops": 1,
    },
    "spell_debuff": {
        "url": f"{SOUND_BASE_URL}/spell_debuff.ogg",
        "volume": 60,
        "priority": 40,
        "type": "sound",
        "loops": 1,
    },

    # ---- Environment ----
    "room_danger": {
        "url": f"{SOUND_BASE_URL}/room_danger.ogg",
        "volume": 55,
        "priority": 35,
        "type": "sound",
        "loops": 1,
    },
    "room_safe": {
        "url": f"{SOUND_BASE_URL}/town_ambient.ogg",
        "volume": 40,
        "priority": 30,
        "type": "sound",
        "loops": 1,
    },
    "door_open": {
        "url": f"{SOUND_BASE_URL}/door_open.ogg",
        "volume": 50,
        "priority": 30,
        "type": "sound",
        "loops": 1,
    },
    "door_close": {
        "url": f"{SOUND_BASE_URL}/door_close.ogg",
        "volume": 50,
        "priority": 30,
        "type": "sound",
        "loops": 1,
    },
    "portal_activate": {
        "url": f"{SOUND_BASE_URL}/portal_activate.ogg",
        "volume": 70,
        "priority": 50,
        "type": "sound",
        "loops": 1,
    },
    "level_up": {
        "url": f"{SOUND_BASE_URL}/level_up.ogg",
        "volume": 80,
        "priority": 70,
        "type": "sound",
        "loops": 1,
    },

    # ---- Social ----
    "tell_received": {
        "url": f"{SOUND_BASE_URL}/tell_received.ogg",
        "volume": 50,
        "priority": 40,
        "type": "sound",
        "loops": 1,
    },
    "group_invite": {
        "url": f"{SOUND_BASE_URL}/group_invite.ogg",
        "volume": 60,
        "priority": 50,
        "type": "sound",
        "loops": 1,
    },
    "clan_chat": {
        "url": f"{SOUND_BASE_URL}/clan_chat.ogg",
        "volume": 50,
        "priority": 40,
        "type": "sound",
        "loops": 1,
    },

    # ---- Quest ----
    "quest_accept": {
        "url": f"{SOUND_BASE_URL}/quest_accept.ogg",
        "volume": 60,
        "priority": 50,
        "type": "sound",
        "loops": 1,
    },
    "quest_complete": {
        "url": f"{SOUND_BASE_URL}/quest_complete.ogg",
        "volume": 75,
        "priority": 60,
        "type": "sound",
        "loops": 1,
    },
    "quest_update": {
        "url": f"{SOUND_BASE_URL}/quest_update.ogg",
        "volume": 55,
        "priority": 45,
        "type": "sound",
        "loops": 1,
    },

    # ---- Economy ----
    "gold_received": {
        "url": f"{SOUND_BASE_URL}/gold_received.ogg",
        "volume": 55,
        "priority": 40,
        "type": "sound",
        "loops": 1,
    },
    "item_acquired": {
        "url": f"{SOUND_BASE_URL}/item_acquired.ogg",
        "volume": 55,
        "priority": 40,
        "type": "sound",
        "loops": 1,
    },

    # ---- Boss ----
    "boss_encounter": {
        "url": f"{SOUND_BASE_URL}/boss_encounter.ogg",
        "volume": 85,
        "priority": 80,
        "type": "sound",
        "loops": 1,
    },
    "boss_defeat": {
        "url": f"{SOUND_BASE_URL}/boss_defeat.ogg",
        "volume": 90,
        "priority": 80,
        "type": "sound",
        "loops": 1,
    },

    # ---- Music loops (optional) ----
    "music_combat_loop": {
        "url": f"{SOUND_BASE_URL}/music_combat_loop.ogg",
        "volume": 30,
        "priority": 10,
        "type": "loop",
        "loops": -1,
    },
    "music_town_loop": {
        "url": f"{SOUND_BASE_URL}/music_town_loop.ogg",
        "volume": 25,
        "priority": 5,
        "type": "loop",
        "loops": -1,
    },
    "music_explore_loop": {
        "url": f"{SOUND_BASE_URL}/music_explore_loop.ogg",
        "volume": 20,
        "priority": 5,
        "type": "loop",
        "loops": -1,
    },
}


# ---------------------------------------------------------------------------
# MSP Protocol Helpers
# ---------------------------------------------------------------------------

def _build_msp_command(sound_def: Dict[str, Any]) -> str:
    """
    Build an MSP sound command string from a sound definition dict.

    MSP uses the format: !!MUSIC(...) or !!SOUND(...) with key=value pairs.
    """
    msp_type = sound_def.get("type", "sound").upper()
    parts = []
    parts.append(f"url={sound_def['url']}")
    parts.append(f"V={sound_def.get('volume', 50)}")
    parts.append(f"P={sound_def.get('priority', 50)}")
    loops = sound_def.get("loops", 1)
    if loops != 1:
        parts.append(f"L={loops}")

    if msp_type == "LOOP":
        cmd = f"!!MUSIC({';'.join(parts)})"
    elif msp_type == "MUSIC":
        cmd = f"!!MUSIC({';'.join(parts)})"
    else:
        cmd = f"!!SOUND({';'.join(parts)})"
    return cmd


def send_msp_sound(session: Any, trigger_key: str) -> bool:
    """
    Send an MSP sound command to a specific session.

    Returns True if the sound was sent, False if the trigger is unknown
    or the session doesn't have MSP enabled.
    """
    sound_def = TRIGGER_SOUND_MAP.get(trigger_key)
    if sound_def is None:
        return False

    try:
        # Check if this is a telnet session that supports MSP.
        if not hasattr(session, "protocol_flags"):
            return False
        if not session.protocol_flags.get("MSP", False):
            return False

        cmd = _build_msp_command(sound_def)
        # Send as raw telnet data (MSP is a telnet subnegotiation).
        session.msg(data="\n" + cmd + "\n")
        return True
    except Exception:
        return False


def broadcast_msp_sound(room: Any, trigger_key: str) -> int:
    """
    Send an MSP sound to all MSP-capable telnet sessions in a room.

    Returns the number of sessions that received the sound.
    """
    count = 0
    try:
        from evennia.objects.models import ObjectDB

        # Find all connected sessions in the room.
        for obj in getattr(room, "contents", []):
            if not hasattr(obj, "sessions"):
                continue
            for session in obj.sessions.all():
                if send_msp_sound(session, trigger_key):
                    count += 1
    except Exception:
        pass
    return count


def get_available_sounds() -> Dict[str, Dict[str, Any]]:
    """
    Return a copy of the sound registry, useful for admin commands
    that list available sounds.
    """
    return dict(TRIGGER_SOUND_MAP)


# ---------------------------------------------------------------------------
# Sound trigger hooks — integrate into game systems
# ---------------------------------------------------------------------------

# These functions are called by combat, spells, and other systems
# to play appropriate sounds. They gracefully handle sessions without
# MSP support.

def on_combat_hit(attacker: Any, defender: Any) -> None:
    """Called when a melee/magic attack hits."""
    broadcast_msp_sound(attacker.location, "combat_hit")


def on_combat_miss(attacker: Any, defender: Any) -> None:
    """Called when a melee/magic attack misses."""
    broadcast_msp_sound(attacker.location, "combat_miss")


def on_combat_crit(attacker: Any, defender: Any) -> None:
    """Called when a critical hit lands."""
    broadcast_msp_sound(attacker.location, "combat_crit")


def on_combat_death(victim: Any) -> None:
    """Called when a character or mob dies."""
    broadcast_msp_sound(victim.location, "combat_death")


def on_spell_cast(caster: Any) -> None:
    """Called when a spell is cast."""
    broadcast_msp_sound(caster.location, "spell_cast")


def on_level_up(character: Any) -> None:
    """Called when a character gains a level."""
    for session in character.sessions.all():
        send_msp_sound(session, "level_up")


def on_quest_complete(character: Any) -> None:
    """Called when a quest is completed."""
    for session in character.sessions.all():
        send_msp_sound(session, "quest_complete")


def on_boss_encounter(room: Any) -> None:
    """Called when a boss mob is encountered."""
    broadcast_msp_sound(room, "boss_encounter")