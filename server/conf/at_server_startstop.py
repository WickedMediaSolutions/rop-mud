"""
Server startstop hooks

This module contains functions called by Evennia at various
points during its startup, reload and shutdown sequence. It
allows for customizing the server operation as desired.

IMPORTANT: at_server_start() must return as quickly as possible.
Heavy operations (full-table DB scans, 13,766-room population
sweeps, crash recovery integrity checks) block the Twisted
reactor and prevent the portal<->server handshake from completing.
This causes telnet and webclient to hang on connect.

Heavy startup tasks are offloaded to:
  - world.recovery.RecoveryScript (runs every 15s, incremental)
  - world.garbage_collection.GarbageCollectionScript (runs every 60s)
  - Admin commands: @sweep, @recover, @populate

This module must contain at least these global functions:

at_server_init()
at_server_start()
at_server_stop()
at_server_reload_start()
at_server_reload_stop()
at_server_cold_start()
at_server_cold_stop()

"""


def at_server_init():
    """
    This is called first as the server is starting up, regardless of how.
    """
    from evennia.scripts.models import ScriptDB

    # ------------------------------------------------------------------
    # Phase 11: Run database migrations before anything else.
    # Ensures schema/data consistency before any game systems load.
    # ------------------------------------------------------------------
    try:
        from world.migrations import run_migrations
        run_migrations()
    except Exception as err:
        from evennia.utils import logger
        logger.log_err(f"Database migrations failed: {err}")

    # Start the automatic database backup ticker if it isn't already running.
    if not ScriptDB.objects.filter(db_key="auto_backup_script").exists():
        from world.backup import BackupScript
        try:
            BackupScript.create("auto_backup_script", interval=1800, autostart=True)
        except Exception:
            pass

    # Start the automated announcement ticker if it isn't already running.
    if not ScriptDB.objects.filter(db_key="auto_announcement_script").exists():
        from world.announcements import AnnouncementScript
        try:
            AnnouncementScript.create(
                "auto_announcement_script",
                interval=1800,  # will be re-rolled on first tick
                autostart=True,
            )
        except Exception:
            pass

    # Start the global weather ticker if it isn't already running.
    if not ScriptDB.objects.filter(db_key="weather_script").exists():
        from world.weather_script import WeatherScript
        try:
            WeatherScript.create(
                "weather_script",
                interval=60,
                autostart=True,
            )
        except Exception:
            pass

    # Start the global recovery ticker if it isn't already running.
    if not ScriptDB.objects.filter(db_key="global_recovery").exists():
        from world.recovery import RecoveryScript
        try:
            RecoveryScript.create(
                "global_recovery",
                interval=15,
                autostart=True,
            )
        except Exception:
            pass

    # Start the garbage collection ticker if it isn't already running.
    if not ScriptDB.objects.filter(db_key="garbage_collection").exists():
        from world.garbage_collection import GarbageCollectionScript
        try:
            GarbageCollectionScript.create(
                "garbage_collection",
                interval=60,
                autostart=True,
            )
        except Exception:
            pass

    # Register in-memory quest definitions (idempotent).
    try:
        from world.quests import register_default_quests
        register_default_quests()
    except Exception:
        pass

    # Register the newbie tutorial quest (idempotent).
    try:
        from world.new_player_experience import register_first_quest
        register_first_quest()
    except Exception:
        pass

    # Register default NPC dialogue trees (Phase 9 — idempotent).
    try:
        from world.quest_dialogue import register_default_dialogues
        register_default_dialogues()
    except Exception:
        pass

    # Phase 3.2-3.4: Register PvP, Raid, World Event, and Pet systems.
    try:
        from world.boss_loot import register_default_boss_loot
        register_default_boss_loot()
    except Exception:
        pass

    try:
        from world.raid_mechanics import register_default_raids
        register_default_raids()
    except Exception:
        pass

    try:
        from world.world_events import register_default_holidays
        register_default_holidays()
    except Exception:
        pass

    # Phase 3.4: Register expanded content (200+ items, 150+ mobs).
    try:
        from world.content_expansion import register_expanded_content
        item_count, mob_count = register_expanded_content()
        if item_count > 0 or mob_count > 0:
            from evennia.utils import logger
            logger.log_info(
                f"Content expansion registered: {item_count} items, {mob_count} mobs."
            )
    except Exception:
        pass

    # Phase 3.4b: Ensure auto-generated zone batch files exist (idempotent).
    # Writes only missing .ev files so the world always has 30 zones on disk.
    try:
        from world.zone_generator import generate_all_zones, get_zone_count
        generated = generate_all_zones()
        if generated > 0:
            from evennia.utils import logger
            logger.log_info(
                f"Zone generator wrote {generated} missing zone files "
                f"(total {get_zone_count()})."
            )
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Room Title Sanitization — strip debug suffixes from all room titles
    # on every server start.  Idempotent: already-clean titles are
    # unchanged.  Zone metadata is preserved as room attributes.
    # ------------------------------------------------------------------
    try:
        from world.room_titles import sanitize_all_rooms
        result = sanitize_all_rooms(dry_run=False)
        if result.get("changed", 0) > 0:
            from evennia.utils import logger
            logger.log_info(
                f"Room title sanitization: {result['changed']}/{result['total_rooms']} "
                f"rooms cleaned."
            )
    except Exception as err:
        from evennia.utils import logger
        logger.log_err(f"Room title sanitization failed: {err}")


def at_server_start():
    """
    Called every time the server starts.

    MUST be fast.  No full-table DB scans, no 13,766-room population
    sweeps, no crash recovery integrity checks.  Those block the
    Twisted reactor and prevent telnet/webclient from connecting.

    Heavy startup work is handled incrementally by background tick
    scripts (RecoveryScript every 15s, GarbageCollectionScript every
    60s) and by admin commands (@sweep, @recover, @populate).
    """
    from evennia.utils import logger

    # Combat state in-memory rebuild — lightweight: only scans ndb
    # attributes on in-memory objects, no DB queries.
    try:
        from world.tick_combat import rebuild_engagements_from_active_combat
        rebuilt = rebuild_engagements_from_active_combat()
        if rebuilt > 0:
            logger.log_info(f"Combat state restored: {rebuilt} engagements rebuilt.")
    except Exception as err:
        logger.log_err(f"Combat state restoration failed: {err}")

    logger.log_info("Server startup complete — accepting connections.")


def at_server_stop():
    """
    This is called just before the server is shut down, regardless
    of it is for a reload, reset or shutdown.

    Phase 11: Mark clean shutdown so crash recovery knows the last
    shutdown was intentional and the database is consistent.
    """
    try:
        from world.crash_recovery import mark_clean_shutdown
        mark_clean_shutdown()
    except Exception:
        pass


def at_server_reload_start():
    """
    This is called only when the server starts back up after a reload.
    """
    pass


def at_server_reload_stop():
    """
    This is called only when the server stops before a reload.
    """
    try:
        from world.crash_recovery import mark_clean_shutdown
        mark_clean_shutdown()
    except Exception:
        pass


def at_server_cold_start():
    """
    This is called only when the server starts "cold", i.e. after a
    shutdown or a reset.
    """
    pass


def at_server_cold_stop():
    """
    This is called only when the server goes down due to a shutdown or
    reset.
    """
    try:
        from world.crash_recovery import mark_clean_shutdown
        mark_clean_shutdown()
    except Exception:
        pass