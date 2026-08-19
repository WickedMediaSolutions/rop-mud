"""
This reroutes from an URL to a python view-function/class.

The main web/urls.py includes these routes for all urls starting with `admin/`
(the `admin/` part should not be included again here).

"""

from django.urls import path

from evennia.web.admin.urls import urlpatterns as evennia_admin_urlpatterns

# Import our customized Django admin registrations so they are applied
# when the admin site is loaded. This registers AccountDB, ObjectDB,
# ScriptDB, ChannelDB, and Msg with production-ready interfaces.
from web.admin.admin import register_all  # noqa: F401

# add patterns here
urlpatterns = [
    # path("url-pattern", imported_python_view),
    # path("url-pattern", imported_python_view),
]

# read by Django
urlpatterns = urlpatterns + evennia_admin_urlpatterns
