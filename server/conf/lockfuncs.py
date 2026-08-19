"""

Lockfuncs

Lock functions are functions available when defining lock strings,
which in turn limits access to various game systems.

All functions defined globally in this module are assumed to be
available for use in lockstrings to determine access. See the
Evennia documentation for more info on locks.

A lock function is always called with two arguments, accessing_obj and
accessed_obj, followed by any number of arguments. All possible
arguments should be handled with *args, **kwargs. The lock function
should handle all eventual tracebacks by logging the error and
returning False.

Lock functions in this module extend (and will overload same-named)
lock functions from evennia.locks.lockfuncs.

"""


def safe_zone(accessing_obj, accessed_obj, *args, **kwargs):
    """
    Lock function: safe_zone()

    Returns True if the accessed_obj (typically a Room) is marked as a
    safe zone where PvP combat is forbidden.

    Usage in lock strings:
        pvp:not safe_zone()   -- allows PvP only when NOT in a safe zone
    """
    return bool(accessed_obj.attributes.get("safe_zone", False))


def can_cast_spells(accessing_obj, accessed_obj, *args, **kwargs):
    """
    Lock function: can_cast_spells()

    Returns True if the accessing_obj's class can cast spells.
    Used to gate CmdCast and CmdSpells commands from non-casting classes.

    Usage in lock strings:
        cmd:can_cast_spells()
    """
    from world.race_class_matrix import can_cast_spells as _check
    return _check(accessing_obj)


def can_use_skill(accessing_obj, accessed_obj, *args, **kwargs):
    """
    Lock function: can_use_skill()

    Returns True if the accessing_obj's class can use the specified skill.
    The skill key is passed as the first argument.

    Usage in lock strings:
        cmd:can_use_skill(kick)
        cmd:can_use_skill(bash)
    """
    from world.race_class_matrix import can_use_skill as _check
    skill_key = args[0] if args else ""
    if not skill_key:
        return False
    allowed, _ = _check(accessing_obj, skill_key)
    return allowed


def can_equip_slot(accessing_obj, accessed_obj, *args, **kwargs):
    """
    Lock function: can_equip_slot()

    Returns True if the accessing_obj can equip the given item type
    in the specified slot. The slot and item_type are passed as args.

    Usage in lock strings:
        cmd:can_equip_slot(weapon, weapon_sword)
    """
    from world.race_class_matrix import can_equip_slot as _check
    slot = args[0] if len(args) > 0 else ""
    item_type = args[1] if len(args) > 1 else ""
    if not slot or not item_type:
        return False
    allowed, _ = _check(accessing_obj, slot, item_type)
    return allowed


def is_outlaw(accessing_obj, accessed_obj, *args, **kwargs):
    """
    Lock function: is_outlaw()

    Returns True if the accessing_obj is currently flagged as an outlaw.

    Usage in lock strings:
        cmd:not is_outlaw()  -- blocks command for outlaws
    """
    from world.alignment_system import AlignmentSystem
    return AlignmentSystem.is_outlaw(accessing_obj)
