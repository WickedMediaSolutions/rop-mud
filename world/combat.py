"""
Combat Handler for 'rop' — PvP Mechanics, Death Penalties, and Corpses

Provides:
  - Safe-zone enforcement (combat disallowed in safe_zone rooms)
  - PvP toggle (pvp on/off) so same-faction players can opt in/out
  - Death: percentage XP loss, corpse left with inventory + coins
  - Corpse looting: owner-only for 5 minutes, then public
  - NPC corpses: created on death for looting/sacrificing
  - Auto-loot / auto-sacrifice post-combat triggers
"""

import random
import time
from evennia import create_object
from evennia.objects.objects import DefaultObject
from evennia.utils import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Percentage of current XP lost on death
DEATH_XP_LOSS_PERCENT = 10

# Seconds before a corpse becomes public (owner-only until then)
CORPSE_OWNER_ONLY_SECONDS = 300  # 5 minutes

# XP awarded for killing an NPC (will be scaled by NPC level)
BASE_NPC_XP = 50

# Sacrifice reward range (copper pieces per mob level)
SAC_MIN_COINS_PER_LEVEL = 1
SAC_MAX_COINS_PER_LEVEL = 5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def is_safe_zone(room):
    """
    Check if a room is a safe zone where combat is disallowed.

    Safe zones include towns, shops, faction havens, and other
    designated non-combat areas. Returns True if combat is forbidden
    in this room.
    """
    if not room:
        return False
    # Check for safe_zone tag or attribute
    if room.attributes.get("safe_zone", default=False):
        return True
    # Check zone tags for known safe zone names
    if hasattr(room, "tags"):
        zone_tags = room.tags.get(category="zone")
        if zone_tags:
            if isinstance(zone_tags, str):
                zone_tags = [zone_tags]
            safe_zone_names = {"town", "shop", "haven", "sanctuary", "safe"}
            for tag in zone_tags:
                if tag.lower() in safe_zone_names:
                    return True
    return False


def _get_effective_hp(target):
    """Fetch current HP.

    Falls back to ``max_hp`` when the ``hp`` attribute is absent so a
    freshly-spawned or legacy target is never mistaken for already-dead.
    """
    hp = target.attributes.get("hp", None)
    if hp is None:
        return target.attributes.get("max_hp", 100)
    return hp


def _set_effective_hp(target, value):
    target.attributes.add("hp", max(0, value))


def _get_max_hp(target):
    return target.attributes.get("max_hp", 100)


def _get_shield(target):
    """Return remaining shield absorption amount (0 if none)."""
    return target.attributes.get("shield_amount", 0)


def _reduce_shield(target, damage):
    """
    Absorb as much damage as possible through the active shield.
    Returns (remaining_damage_after_shield, amount_absorbed).
    """
    shield = _get_shield(target)
    if shield <= 0:
        return damage, 0

    absorbed = min(damage, shield)
    target.attributes.add("shield_amount", shield - absorbed)
    return damage - absorbed, absorbed


# ---------------------------------------------------------------------------
# PvP / Safe-Zone Permission Checks
# ---------------------------------------------------------------------------

def _is_pvp_allowed(attacker, target):
    """
    Return (allowed, reason) tuple.

    Checks in order:
      1. Safe zone: combat is always blocked in safe-zone rooms.
      2. NPC targets (no alignment attribute) are always valid.
      3. Same-faction: both must have `pvp on` (or be opposing factions).
    """
    # 1. Safe zone check — blocks ALL combat, even vs NPCs
    location = attacker.location
    if location and location.attributes.get("safe_zone", False):
        return False, "You cannot fight in a safe zone."

    # 2. Only enforce PvP rules when the target has an alignment (player character).
    #    NPCs / mobs won't have an alignment attribute set.
    target_align = target.attributes.get("alignment", "")
    if not target_align:
        return True, ""

    # 3. Opposite factions: Good vs Evil auto-allow PvP without explicit toggle
    attacker_align = attacker.attributes.get("alignment", "")
    if attacker_align and target_align:
        if attacker_align != target_align:
            # Cross-faction: always allowed (Good vs Evil)
            return True, ""

    # 4. Same faction: require both to have pvp_enabled (or share via group)
    if attacker_align and attacker_align == target_align:
        attacker_pvp = _get_effective_pvp(attacker)
        target_pvp = _get_effective_pvp(target)
        if not attacker_pvp:
            return False, "You have PvP disabled. Use |wpvp on|n to enable it."
        if not target_pvp:
            return False, f"{target.key} has PvP disabled."

    return True, ""


def _can_attack(attacker, target):
    """
    Convenience wrapper. Returns True if attack is permitted, False otherwise.
    Sends an error message to the attacker when denied.
    """
    allowed, reason = _is_pvp_allowed(attacker, target)
    if not allowed:
        attacker.msg(f"|r{reason}|n")
        return False
    return True


def _get_effective_pvp(character) -> bool:
    """
    Return True if the character (or any group member) has PvP enabled.

    Group PvP sharing: if any member of the character's group has
    ``pvp_enabled`` set on their db, the entire group is flagged for PvP.
    This prevents a player from hiding behind a group while their
    groupmates are flagged.
    """
    # Check the character's own flag first
    if getattr(character.db, "pvp_enabled", False):
        return True

    # Check group members
    group_id = character.attributes.get("group_id", default=None)
    if group_id:
        from commands.group import get_group_members
        for member in get_group_members(character):
            if getattr(member.db, "pvp_enabled", False):
                return True

    return False


# ---------------------------------------------------------------------------
# Corpse creation helpers
# ---------------------------------------------------------------------------

def _make_corpse(name, location, contents, money, npc_level=None, owner_id=None,
                owner_name=None):
    """
    Internal factory: create a corpse object with the given attributes.

    npc_level is stored for sacrifice reward scaling.
    """
    attrs = [
        ("desc", f"The lifeless body of {name} lies here. "
                 f"{len(contents)} item(s) and {money} gold can be seen."),
        ("is_corpse", True),
        ("corpse_created_at", time.time()),
        ("corpse_owner_only_seconds", CORPSE_OWNER_ONLY_SECONDS),
        ("money", money),
    ]

    if npc_level is not None:
        attrs.append(("corpse_npc_level", npc_level))
    if owner_id is not None:
        attrs.append(("corpse_owner_id", owner_id))
        attrs.append(("corpse_owner_name", owner_name or "unknown"))

    corpse = create_object(
        DefaultObject,
        key=f"corpse of {name}",
        location=location,
        attributes=attrs,
    )

    for obj in contents:
        obj.move_to(corpse, quiet=True)

    return corpse


def create_corpse(victim, killer):
    """
    Create a corpse for a player character victim, containing all their
    inventory items and coins.  The corpse is owner-locked for
    CORPSE_OWNER_ONLY_SECONDS.
    """
    location = victim.location
    if not location:
        return None

    contents = [obj for obj in victim.contents if not obj.destination]
    money = victim.attributes.get("money", 0) or 0

    corpse = _make_corpse(
        name=victim.key,
        location=location,
        contents=contents,
        money=money,
        owner_id=victim.id,
        owner_name=victim.key,
    )

    victim.attributes.add("money", 0)
    return corpse


def _create_npc_corpse(npc, killer, npc_level, gold_drop=None):
    """
    Create a corpse for an NPC/monster.  Moves all items from the NPC
    into the corpse, including equipped gear, and transfers copper/silver/gold
    coins based on the mob's level.

    The corpse receives:
      - All inventory items (non-exit objects in npc.contents)
      - All equipped gear (transferred via transfer_equipped_to_corpse)
      - Copper, silver, and gold coins from the mob's coin attributes
    """
    location = npc.location
    if not location:
        return None

    # Transfer equipped gear from the mob to its inventory first
    # so it gets picked up by the contents scan below.
    try:
        from world.mob_equipment import transfer_equipped_to_corpse
    except Exception as err:
        logger.log_err(f"_create_npc_corpse: failed to import transfer_equipped_to_corpse: {err}")
        transfer_equipped_to_corpse = None

    # Collect all non-exit items from the NPC
    contents = [obj for obj in npc.contents if not obj.destination]

    # Calculate total coin value in gold-equivalent for the corpse
    # (copper/silver/gold tiers)
    copper = npc.attributes.get("copper_coins", default=0) if hasattr(npc, "attributes") else 0
    silver = npc.attributes.get("silver_coins", default=0) if hasattr(npc, "attributes") else 0
    gold = npc.attributes.get("gold_coins", default=0) if hasattr(npc, "attributes") else 0

    # Use provided gold_drop or fallback to level-based random
    if gold_drop is not None:
        gold = gold_drop

    # If no coins were generated (legacy mob), fall back to level-based
    if copper == 0 and silver == 0 and gold == 0:
        gold = random.randint(1, npc_level * 3)

    # Total money in gold-equivalent for the corpse
    total_money = gold + (silver // 10) + (copper // 100)

    corpse = _make_corpse(
        name=npc.key,
        location=location,
        contents=contents,
        money=max(1, total_money),
        npc_level=npc_level,
    )

    # Store coin breakdown on the corpse for detailed looting
    corpse.attributes.add("copper_coins", copper)
    corpse.attributes.add("silver_coins", silver)
    corpse.attributes.add("gold_coins", gold)

    # Transfer equipped items into the corpse AFTER contents scan
    # (so they don't get double-counted)
    if transfer_equipped_to_corpse:
        transfer_equipped_to_corpse(npc, corpse)

    return corpse


def _roll_loot_table(loot_table):
    """
    Roll a mob's loot table and return a list of created item objects.

    loot_table is a list of dicts with keys:
      - item_key: str (prototype key to spawn, resolved via ITEM_PROTOTYPES)
      - weight: float (relative drop chance)
      - min_qty: int (minimum quantity)
      - max_qty: int (maximum quantity)

    Resolves ITEM_PROTOTYPES from world.prototypes to create statted items.
    Falls back to a bare DefaultObject if the prototype is not found.
    """
    items = []
    if not loot_table:
        return items

    try:
        from world.prototypes import ITEM_PROTOTYPES
    except Exception as err:
        logger.log_err(f"_roll_loot_table: failed to import ITEM_PROTOTYPES: {err}")
        ITEM_PROTOTYPES = {}

    for entry in loot_table:
        weight = entry.get("weight", 1.0)
        if random.random() > weight:
            continue
        item_key = entry.get("item_key", "")
        if not item_key:
            continue
        qty = random.randint(entry.get("min_qty", 1), entry.get("max_qty", 1))
        for _ in range(qty):
            try:
                proto = ITEM_PROTOTYPES.get(item_key)
                if proto:
                    # Clone the prototype dict so we can override key/attrs.
                    # IMPORTANT: prototypes use "attrs" internally but
                    # Evennia's create_object() expects "attributes".
                    import copy
                    proto_copy = copy.deepcopy(proto)
                    proto_copy.setdefault("key", item_key)
                    if "attrs" in proto_copy and "attributes" not in proto_copy:
                        proto_copy["attributes"] = proto_copy.pop("attrs")
                    item = create_object(**proto_copy)
                else:
                    # Fallback: bare object with minimal attributes
                    from evennia.objects.objects import DefaultObject
                    item = create_object(
                        DefaultObject,
                        key=item_key,
                        attributes=[
                            ("weight", entry.get("weight_attr", 1)),
                            ("value", entry.get("value", 1)),
                            ("damage", entry.get("damage", 0)),
                            ("armor", entry.get("armor", 0)),
                            ("item_type", entry.get("item_type", "misc")),
                        ],
                    )
                items.append(item)
            except Exception as err:
                try:
                    logger.log_err(f"_roll_loot_table: failed to create item "
                                   f"'{item_key}': {err}")
                except Exception as log_err:
                    logger.log_err(f"_roll_loot_table: logger failure: {log_err}")

    return items


# ---------------------------------------------------------------------------
# Auto-loot / auto-sac helpers
# ---------------------------------------------------------------------------

def _auto_loot_corpse(killer, corpse):
    """
    Automatically loot all coins and items from a corpse into the killer's
    inventory.  Sends a brief message to the killer.
    """
    corpse_money = corpse.attributes.get("money", 0) or 0
    items = [obj for obj in corpse.contents if not obj.destination]

    if corpse_money > 0:
        current_money = killer.attributes.get("money", default=0)
        killer.attributes.add("money", current_money + corpse_money)
        corpse.attributes.add("money", 0)

    item_count = len(items)
    for obj in items:
        obj.move_to(killer, quiet=True)

    parts = []
    if corpse_money > 0:
        parts.append(f"|Y{corpse_money} gold|n")
    if item_count > 0:
        parts.append(f"|w{item_count} item(s)|n")

    if parts:
        killer.msg(
            f"|g[Auto-Loot] You loot {corpse.key} and take "
            f"{', '.join(parts)}.|n"
        )


def _auto_sac_corpse(killer, corpse):
    """
    Automatically sacrifice a corpse and award coins to the killer.

    This is called after auto-loot (if both are enabled) so it sacrifices
    the now-empty corpse for bonus coins.
    """
    npc_level = corpse.attributes.get("corpse_npc_level", default=1)
    from commands.loot import calculate_sac_reward
    coins, display = calculate_sac_reward(npc_level)

    current_money = killer.attributes.get("money", default=0)
    killer.attributes.add("money", current_money + coins)

    killer.msg(
        f"|c[Auto-Sac] You offer {corpse.key} to the gods and receive "
        f"|W{display}|c!|n"
    )

    corpse.delete()


# ---------------------------------------------------------------------------
# Defeat handler
# ---------------------------------------------------------------------------

def _handle_defeat(target, killer):
    """
    Handle a character/NPC being reduced to 0 HP.

    For player characters:
      1. Deduct DEATH_XP_LOSS_PERCENT of current XP
      2. Create a corpse with inventory + coins
      3. Award Warpoints for cross-faction kills (or apply Infamy for same-faction)
      4. Broadcast realm-wide victory announcement for cross-faction kills
      5. Move the target to their home (or faction start room)
      6. Restore HP/Mana/MV

    For NPCs/monsters:
      1. Award XP to the killer (split among group if in one)
      2. Create a corpse with coins/items from the NPC
      3. Trigger autoloot / autosac for the killer if enabled
      4. Delete the NPC
    """
    # Determine if target is an NPC (no account, no alignment)
    target_is_npc = not target.attributes.get("alignment", "")

    if target_is_npc:
        # --- NPC/Monster Defeat: Award XP ---
        npc_level = target.attributes.get("level", default=1)
        xp_value = target.attributes.get("xp_value", default=None)
        xp_award = xp_value if xp_value is not None else (BASE_NPC_XP * npc_level)

        # Award XP to killer, splitting among group if applicable
        from commands.group import split_group_xp
        split_group_xp(killer, xp_award)

        # Advance any active kill quests for the killer
        try:
            killer.quests.report_kill(target.key)
        except Exception as err:
            logger.log_err(f"_handle_defeat: quests.report_kill failed for {killer.key} on {target.key}: {err}")

        # --- Reputation adjustment for mob kills ---
        try:
            from world.reputation import ReputationSystem
            mob_faction = target.attributes.get("faction", default="") if hasattr(target, "attributes") else ""
            if mob_faction == "good":
                ReputationSystem.adjust_reputation(killer, "aethelgard", ReputationSystem.REP_KILL_MOB)
                ReputationSystem.adjust_reputation(killer, "gorgoroth", -ReputationSystem.REP_KILL_MOB)
            elif mob_faction == "evil":
                ReputationSystem.adjust_reputation(killer, "gorgoroth", ReputationSystem.REP_KILL_MOB)
                ReputationSystem.adjust_reputation(killer, "aethelgard", -ReputationSystem.REP_KILL_MOB)
            # Boss kills give extra reputation
            if target.attributes.get("is_boss", default=False) if hasattr(target, "attributes") else False:
                if mob_faction == "good":
                    ReputationSystem.adjust_reputation(killer, "aethelgard", ReputationSystem.REP_KILL_BOSS)
                elif mob_faction == "evil":
                    ReputationSystem.adjust_reputation(killer, "gorgoroth", ReputationSystem.REP_KILL_BOSS)
        except Exception as err:
            logger.log_err(f"_handle_defeat: reputation adjustment failed for {killer.key}: {err}")

        # Notify the room
        if target.location:
            target.location.msg_contents(
                f"|g{target.key} has been slain by {killer.key}!|n",
                exclude=[killer],
            )
        killer.msg(f"|gYou have slain {target.key}!|n")

        # --- Phase 4.1: Roll mob loot table ---
        # Check if the mob has a loot_table attribute
        loot_table = target.attributes.get("loot_table", default=None) if hasattr(target, "attributes") else None
        loot_items = []
        if loot_table:
            loot_items = _roll_loot_table(loot_table)

        # Use gold_min/gold_max from the mob if available, otherwise fallback
        gold_min = target.attributes.get("gold_min", default=None) if hasattr(target, "attributes") else None
        gold_max = target.attributes.get("gold_max", default=None) if hasattr(target, "attributes") else None
        if gold_min is not None and gold_max is not None:
            gold_drop = random.randint(gold_min, gold_max)
        else:
            gold_drop = random.randint(1, npc_level * 3)

        # Racial passive: bonus gold drops (Goblin +15%).
        try:
            from world.rules import get_racial_bonuses
            racial = get_racial_bonuses(killer)
            gold_pct = racial.get("gold_bonus_pct", 0)
            if gold_pct:
                gold_drop = int(gold_drop * (1.0 + gold_pct / 100.0))
        except Exception as err:
            logger.log_err(f"_handle_defeat: racial gold bonus failed for {killer.key}: {err}")

        # Phase 2.3: Scavenger talent grants +5% bonus gold per rank.
        try:
            from world.skill_tree import get_talent_bonuses
            talent_gold_pct = get_talent_bonuses(killer).get("gold_bonus_pct", 0)
            if talent_gold_pct:
                gold_drop = int(gold_drop * (1.0 + talent_gold_pct / 100.0))
        except Exception as err:
            logger.log_err(f"_handle_defeat: talent gold bonus failed for {killer.key}: {err}")

        # Create a corpse for the NPC so it can be looted/sacrificed
        corpse = _create_npc_corpse(target, killer, npc_level, gold_drop=gold_drop)

        # Move loot table items into the corpse
        if corpse and loot_items:
            for item in loot_items:
                item.move_to(corpse, quiet=True)
            if killer.location:
                killer.location.msg_contents(
                    f"|w{killer.key} finds treasure on the corpse of {target.key}!|n"
                )

        # --- Boss Loot Drop ---
        # If the NPC is a boss, roll its loot table and drop items
        from world.boss_loot import boss_loot_registry, BossLootHandler, is_boss
        boss_items = []
        if is_boss(target):
            loot_table = boss_loot_registry.get(target.key)
            if loot_table:
                boss_items = BossLootHandler.roll_boss_loot(loot_table)
                for item in boss_items:
                    if corpse:
                        item.move_to(corpse, quiet=True)
                    else:
                        item.move_to(target.location, quiet=True)

                if boss_items and target.location:
                    display = BossLootHandler.get_drop_display(boss_items)
                    target.location.msg_contents(
                        f"|Y|h[BOSS LOOT] {target.key} drops: {display}|n"
                    )

        # Trigger auto-loot / auto-sac if the killer has them enabled
        if corpse and killer.attributes.get("autoloot", default=False):
            _auto_loot_corpse(killer, corpse)
        if corpse and killer.attributes.get("autosac", default=False):
            _auto_sac_corpse(killer, corpse)

        # Delete the NPC unless it is a Mob (which schedules its own respawn)
        if hasattr(target, "die") and callable(getattr(target, "die", None)):
            # Mob lifecycle: die() schedules respawn instead of deleting.
            target.die(killer)
        else:
            target.delete()
        return

    # --- Player Character Defeat ---
    killer_name = killer.key if killer is not None else "unknown forces"
    target.msg("|rYou have been defeated!|n")
    if target.location:
        target.location.msg_contents(
            f"|r{target.key} has been defeated by {killer_name}!|n",
            exclude=[target],
        )

    # ---- XP Loss ----
    current_xp = target.attributes.get("xp", 0)
    xp_loss = int(current_xp * DEATH_XP_LOSS_PERCENT / 100)
    new_xp = max(0, current_xp - xp_loss)
    target.attributes.add("xp", new_xp)
    target.msg(f"|rYou lose {xp_loss} XP. ({new_xp} remaining)|n")

    # ---- Corpse ----
    corpse = create_corpse(target, killer)
    if corpse:
        target.msg(
            f"|yYour corpse has been left behind in "
            f"{target.location.key if target.location else 'the void'}.|n"
            f"|yYou have {CORPSE_OWNER_ONLY_SECONDS // 60} minutes to "
            f"return and loot it before it becomes public.|n"
        )
        target.location.msg_contents(
            f"|yThe corpse of {target.key} drops to the ground.|n",
            exclude=[target],
        )

    # ---- Warpoints / Infamy ----
    # Skipped when there is no killer (e.g., bleed-out death).
    if killer is not None:
        killer_align = killer.attributes.get("alignment", "")
        target_align = target.attributes.get("alignment", "")

        if killer_align and target_align and killer_align != target_align:
            # Cross-faction kill: award Warpoints
            _award_warpoints(killer, target)
        elif killer_align and target_align and killer_align == target_align:
            # Same-faction kill: apply Infamy / PK penalty
            _apply_infamy(killer, target)

    # ---- Respawn ----
    # Try to move to home; fall back to faction start room
    home = target.home
    if not home:
        alignment = target.attributes.get("alignment", "Good")
        from evennia import search_object
        if alignment == "Evil":
            start_key = "Gorgoroth - Dark Temple"
        else:
            start_key = "Aethelgard - Shrine of Light"
        home_candidates = search_object(start_key, typeclass="typeclasses.rooms.Room")
        home = home_candidates[0] if home_candidates else None

    if home:
        target.move_to(home, quiet=False)
    else:
        target.msg("|rNo home found! Contact an admin.|n")

    # Restore HP / Mana / MV
    target.attributes.add("hp", target.attributes.get("max_hp", 100))
    target.attributes.add("mana", target.attributes.get("max_mana", 50))
    target.attributes.add("mv", target.attributes.get("max_mv", 100))


# ---------------------------------------------------------------------------
# PvP reward / penalty
# ---------------------------------------------------------------------------

def _award_warpoints(killer, victim):
    """
    Award Warpoints to the killer for a cross-faction PvP kill.

    Calculates warpoints based on level difference, adds them to the
    killer's persistent total, and broadcasts a realm-wide victory
    announcement.
    """
    from world.rules import calculate_warpoints

    killer_level = killer.attributes.get("level", default=1)
    victim_level = victim.attributes.get("level", default=1)
    killer_align = killer.attributes.get("alignment", "Unknown")

    wp_earned = calculate_warpoints(killer_level, victim_level)

    # Add to killer's persistent warpoints total
    current_wp = killer.attributes.get("warpoints", default=0)
    new_total = current_wp + wp_earned
    killer.attributes.add("warpoints", new_total)

    # Increment kill counter
    kills = killer.attributes.get("kills", default=0)
    killer.attributes.add("kills", kills + 1)

    # Notify the killer
    killer.msg(
        f"|Y|h[PVP] You have earned {wp_earned} Warpoints for the "
        f"{killer_align} faction! (Total: {new_total} WP)|n"
    )

    # Realm-wide victory announcement
    _broadcast_warpoints(killer, victim, wp_earned, killer_align)


def _broadcast_warpoints(killer, victim, wp_earned, faction):
    """
    Broadcast a realm-wide PvP victory announcement to all connected players.
    """
    from evennia.objects.models import ObjectDB
    from typeclasses.characters import Character

    announcement = (
        f"|Y|h[PVP] {killer.key} has slain {victim.key} in battle and "
        f"earned {wp_earned} Warpoints for the {faction} faction!|n"
    )

    # Send to all online player characters
    for char in ObjectDB.objects.all():
        if not isinstance(char, Character):
            continue
        if not hasattr(char, 'sessions') or char.sessions.count() == 0:
            continue
        char.msg(announcement)


def _apply_infamy(killer, victim):
    """
    Apply an Infamy / PK penalty for a same-faction kill.

    Same-faction kills do NOT award Warpoints.  Instead the killer
    receives an infamy mark and a warning.
    """
    # Increment infamy counter
    infamy = killer.attributes.get("infamy", default=0)
    killer.attributes.add("infamy", infamy + 1)

    killer.msg(
        f"|r|h[INFAMY] You have slain a fellow {killer.attributes.get('alignment', 'ally')} "
        f"({victim.key})! No Warpoints awarded. Infamy: {infamy + 1}|n"
    )


# ---------------------------------------------------------------------------
# Combat actions
# ---------------------------------------------------------------------------

def apply_magic_damage(caster, target, damage, spell_name="Unknown Spell"):
    """
    Apply magic damage to a target, respecting shields, safe zones, and PvP rules.

    Called by SpellHandler._apply_damage().

    Returns a string message describing the result.
    """
    # PvP / safe-zone check
    if not _can_attack(caster, target):
        return "Combat prevented."

    # Reduce via shield first
    remaining, absorbed = _reduce_shield(target, damage)

    # Apply remaining damage to HP
    current_hp = _get_effective_hp(target)
    max_hp = _get_max_hp(target)

    actual_damage = min(remaining, current_hp)
    _set_effective_hp(target, current_hp - actual_damage)

    # Build result message
    parts = []
    if absorbed > 0:
        parts.append(f"{target.key}'s shield absorbs {absorbed} damage")
    parts.append(f"{target.key} takes {actual_damage} magic damage from {spell_name}")

    # Broadcast
    caster.msg(
        f"|rYou cast {spell_name} on {target.key} for {damage} damage|n"
        f"{' (shield absorbed ' + str(absorbed) + ')' if absorbed > 0 else ''}. "
        f"[{_get_effective_hp(target)}/{max_hp} HP]"
    )
    if target != caster:
        target.msg(
            f"|r{caster.key} casts {spell_name} on you for {damage} damage|n"
            f"{' (your shield absorbs ' + str(absorbed) + ')' if absorbed > 0 else ''}. "
            f"[{_get_effective_hp(target)}/{max_hp} HP]"
        )

    if target.location:
        target.location.msg_contents(
            f"|r{caster.key} casts {spell_name} on {target.key}!|n"
            f"{' (' + str(absorbed) + ' absorbed by shield)' if absorbed > 0 else ''}",
            exclude=[caster, target]
        )

    # Notify the target they were hit so mobs can retaliate (lock onto the caster).
    try:
        target.at_damage(actual_damage, caster)
    except Exception as err:
        logger.log_err(f"apply_magic_damage: target.at_damage failed for {target.key}: {err}")

    if _get_effective_hp(target) <= 0:
        _handle_defeat(target, caster)

    return " ".join(parts)


def apply_physical_damage(attacker, target, base_damage):
    """
    Apply physical (non-magic) damage, respecting shields, stats,
    equipped armor, safe zones, and PvP rules.

    Used by melee / ranged combat.

    Armor integration: if the target has armor equipped, the correct
    amount is absorbed based on damage type mitigation.  If the target
    has no armor equipped, absorption is 0 (no phantom absorption).
    """
    # PvP / safe-zone check
    if not _can_attack(attacker, target):
        return 0

    # Effective stats (base + equipment bonuses)
    try:
        from world.mob_equipment import get_effective_stats
        attacker_stats = get_effective_stats(attacker)
        target_stats = get_effective_stats(target)
    except Exception as err:
        logger.log_err(f"apply_physical_damage: get_effective_stats failed: {err}")
        attacker_stats = attacker.attributes.get("stats", {}) or {}
        target_stats = target.attributes.get("stats", {}) or {}

    str_bonus = max(0, (attacker_stats.get("str", 10) - 10) // 2)

    # Determine damage type from the attacker's equipped weapon
    try:
        from world.mob_equipment import get_equipped_weapon_damage_type
        from world.damage_formulas import DamageType
        dt_str = get_equipped_weapon_damage_type(attacker)
        damage_type = DamageType(dt_str)
    except Exception as err:
        logger.log_err(f"apply_physical_damage: get_equipped_weapon_damage_type failed: {err}")
        from world.damage_formulas import DamageType
        damage_type = DamageType.SLASH

    raw_damage = max(1, base_damage + str_bonus)

    # Armor absorption — only when armor is actually equipped
    try:
        from world.damage_formulas import calculate_armor_absorption
        armor_absorbed = calculate_armor_absorption(target, raw_damage, damage_type)
    except Exception as err:
        logger.log_err(f"apply_physical_damage: calculate_armor_absorption failed: {err}")
        armor_absorbed = 0

    post_armor = max(1, raw_damage - armor_absorbed)

    remaining, shield_absorbed = _reduce_shield(target, post_armor)

    # Sleeping vulnerability: +50% extra damage
    target_position = target.attributes.get("position", default="standing") if hasattr(target, "attributes") else "standing"
    if target_position == "sleeping":
        remaining = int(remaining * 1.5)

    current_hp = _get_effective_hp(target)
    max_hp = _get_max_hp(target)
    actual = min(remaining, current_hp)
    _set_effective_hp(target, current_hp - actual)

    sleep_msg = " |R[VULNERABLE - SLEEPING]|n" if target_position == "sleeping" else ""
    armor_msg = f" |b[Armor absorbs {armor_absorbed}]|n" if armor_absorbed > 0 else ""
    shield_msg = f" |b[Shield absorbs {shield_absorbed}]|n" if shield_absorbed > 0 else ""

    attacker.msg(
        f"|rYou hit {target.key} for {actual} physical damage.|n"
        f"{armor_msg}{shield_msg}{sleep_msg} "
        f"[{_get_effective_hp(target)}/{max_hp} HP]|n"
    )
    target.msg(
        f"|r{attacker.key} hits you for {actual} physical damage.|n"
        f"{armor_msg}{shield_msg}{sleep_msg} "
        f"[{_get_effective_hp(target)}/{max_hp} HP]|n"
    )

    if target.location:
        target.location.msg_contents(
            f"|r{attacker.key} attacks {target.key}!|n",
            exclude=[attacker, target]
        )

    # Notify the target they were hit so mobs can retaliate (lock onto the attacker).
    try:
        target.at_damage(actual, attacker)
    except Exception as err:
        logger.log_err(f"apply_physical_damage: target.at_damage failed for {target.key}: {err}")

    if _get_effective_hp(target) <= 0:
        _handle_defeat(target, attacker)

    return actual
