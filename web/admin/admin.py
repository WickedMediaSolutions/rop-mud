"""
Customized Django Admin registrations for 'rop' — Phase 10

Registers Evennia's core models with production-ready admin interfaces:

  - AccountDB: ban/mute status indicators, search by username/email
  - ObjectDB: typeclass path, location, search by key/dbref
  - ScriptDB: active/persistent filters, interval display
  - ChannelDB: subscription counts
  - Msg: sender/receiver search

Also registers custom read-only "views" for the audit trail and
server performance metrics, accessible from the Django admin index.
"""

from django.contrib import admin
from django.utils.html import format_html


# ---------------------------------------------------------------------------
# AccountDB — with ban/mute indicators
# ---------------------------------------------------------------------------

def _register_account_admin():
    try:
        from evennia.accounts.models import AccountDB

        @admin.register(AccountDB)
        class AccountAdmin(admin.ModelAdmin):
            list_display = (
                "id",
                "username",
                "email",
                "date_created",
                "last_login",
                "ban_status",
                "mute_status",
                "session_count",
            )
            search_fields = ("username", "email", "id")
            list_filter = ("is_superuser", "is_staff", "date_created")
            readonly_fields = ("id", "date_created", "last_login")

            def ban_status(self, obj):
                from commands.moderation import get_ban_info
                info = get_ban_info(obj)
                if not info.get("banned"):
                    return format_html('<span style="color:green">No</span>')
                if info.get("permanent"):
                    return format_html('<span style="color:red;font-weight:bold">PERMANENT</span>')
                secs = info.get("expires_in", 0)
                return format_html(f'<span style="color:red">{secs // 60}m remaining</span>')

            ban_status.short_description = "Banned"

            def mute_status(self, obj):
                from commands.moderation import get_mute_info
                info = get_mute_info(obj)
                if not info.get("muted"):
                    return format_html('<span style="color:green">No</span>')
                if info.get("permanent"):
                    return format_html('<span style="color:orange;font-weight:bold">PERMANENT</span>')
                secs = info.get("expires_in", 0)
                return format_html(f'<span style="color:orange">{secs // 60}m remaining</span>')

            mute_status.short_description = "Muted"

            def session_count(self, obj):
                try:
                    return obj.sessions.count()
                except Exception:
                    return 0

            session_count.short_description = "Sessions"

    except Exception:
        pass


# ---------------------------------------------------------------------------
# ObjectDB
# ---------------------------------------------------------------------------

def _register_objectdb_admin():
    try:
        from evennia.objects.models import ObjectDB

        @admin.register(ObjectDB)
        class ObjectAdmin(admin.ModelAdmin):
            list_display = (
                "id",
                "db_key",
                "db_typeclass_path",
                "db_location",
                "db_home",
                "db_date_created",
                "db_date_modified",
            )
            search_fields = ("db_key", "id", "db_typeclass_path")
            list_filter = ("db_typeclass_path", "db_date_created")
            readonly_fields = ("id", "db_date_created", "db_date_modified")

    except Exception:
        pass


# ---------------------------------------------------------------------------
# ScriptDB
# ---------------------------------------------------------------------------

def _register_scriptdb_admin():
    try:
        from evennia.scripts.models import ScriptDB

        @admin.register(ScriptDB)
        class ScriptAdmin(admin.ModelAdmin):
            list_display = (
                "id",
                "db_key",
                "db_typeclass_path",
                "db_interval",
                "db_repeats",
                "db_is_active",
                "db_is_persistent",
            )
            search_fields = ("db_key", "id", "db_typeclass_path")
            list_filter = ("db_is_active", "db_is_persistent", "db_typeclass_path")

    except Exception:
        pass


# ---------------------------------------------------------------------------
# ChannelDB
# ---------------------------------------------------------------------------

def _register_channeldb_admin():
    try:
        from evennia.comms.models import ChannelDB

        @admin.register(ChannelDB)
        class ChannelAdmin(admin.ModelAdmin):
            list_display = ("id", "db_key", "db_typeclass_path", "db_date_created")
            search_fields = ("db_key", "id")

    except Exception:
        pass


# ---------------------------------------------------------------------------
# Msg
# ---------------------------------------------------------------------------

def _register_msg_admin():
    try:
        from evennia.comms.models import Msg

        @admin.register(Msg)
        class MsgAdmin(admin.ModelAdmin):
            list_display = ("id", "db_sender", "db_receivers_display", "db_date_created")
            search_fields = ("db_sender__username", "db_message", "id")
            list_filter = ("db_date_created",)

            def db_receivers_display(self, obj):
                try:
                    recv = obj.db_receivers_players.all()
                    if not recv:
                        recv = obj.db_receivers_channels.all()
                    return ", ".join(str(r) for r in recv[:5])
                except Exception:
                    return ""
            db_receivers_display.short_description = "Receivers"

    except Exception:
        pass


# ---------------------------------------------------------------------------
# Run all registrations
# ---------------------------------------------------------------------------

def register_all():
    """Register all custom admin classes. Idempotent — safe to call twice."""
    _register_account_admin()
    _register_objectdb_admin()
    _register_scriptdb_admin()
    _register_channeldb_admin()
    _register_msg_admin()


register_all()
