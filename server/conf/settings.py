"""
Evennia settings file for 'rop'.
"""

# Use the defaults from Evennia unless explicitly overridden
from evennia.settings_default import *

######################################################################
# Server Configuration
######################################################################

# Game name
SERVERNAME = "Rites of Passage"

# Multisession Mode (2 = multiple sessions per account, 1 character per session)
MULTISESSION_MODE = 2

# Character Creation Setup
CHARGEN_MENU = "world.chargen"

# Default fallback start location set to Good town (#20)
START_LOCATION = "#20"

# Point to the custom character typeclass
BASE_CHARACTER_TYPECLASS = "typeclasses.characters.Character"

# Use our custom MuxCommand as the default command parent so that
# at_post_cmd() delivers the status prompt after every command.
COMMAND_DEFAULT_CLASS = "commands.command.MuxCommand"

######################################################################
# Authentication & Session Security (Forces Manual Connect Prompt)
######################################################################

# Disable auto-creating characters or auto-puppeting on connection.
AUTO_CREATE_CHARACTER_WITH_ACCOUNT = False
AUTO_PUPPET_ON_LOGIN = False
# Hook custom unloggedin command set
CMDSET_UNLOGGEDIN = "commands.default_cmdsets.UnloggedinCmdSet"
# Disable guest auto-login
GUEST_ENABLED = False

# Disable session cookie persistence (forces manual login on refresh/reconnect)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_AGE = 1

# Idle timeout: disconnect sessions that have been inactive for 1 hour.
# Prevents zombie sessions from clients that disconnect without clean
# TCP teardown (power loss, network drop, etc.).
IDLE_TIMEOUT = 3600

# Connection rate limiting: max new connections per second from a single IP.
# Evennia default is 2; kept at 2 for production safety.
MAX_CONNECTION_RATE = 2

# Maximum total concurrent server sessions.  Prevents resource exhaustion
# from connection floods.  500 is generous for a MUD while capping memory.
MAX_SERVER_SESSIONS = 500

######################################################################
# Secret Settings Override
######################################################################
try:
    from server.conf.secret_settings import *
except ImportError:
    print("secret_settings.py file not found or failed to import.")

######################################################################
# Network and Port Configuration (STRICTLY PRESERVED)
######################################################################

# Change the default Telnet port (default is [4000])
TELNET_PORTS = [4010]

# Change the Web Server ports: (outgoing_public_port, internal_port) (default is [(4001, 4005)])
WEBSERVER_PORTS = [(4011, 4015)]

# Change the WebSocket client port (default is 4002)
WEBSOCKET_CLIENT_PORT = 4012

# Override WebSocket URL for the webclient to use the Caddy-proxied path.
# Without this, the client tries to connect directly to ws://host:4012 which
# fails on HTTPS (mixed content) and is blocked by the firewall.
WEBSOCKET_CLIENT_URL = "wss://rop.dirtysouthjosh.com/ws/"

# Change internal Server-Portal communication port (default is 4006)
AMP_PORT = 4016

# Allowed web hosts
ALLOWED_HOSTS = ["*"]

CMDSET_SESSION = "evennia.commands.default.cmdset_session.SessionCmdSet"

######################################################################
# Webclient Static Assets & Serving
######################################################################

# Where ``evennia collectstatic`` gathers all static assets for a
# production reverse proxy (Caddy, nginx, etc.) to serve directly.
# This must be an absolute path so Caddy can read the files.
import os
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# WebSocket protocol is enabled for the webclient.
WEBSOCKET_CLIENT_ENABLED = True

# ------------------------------------------------------------------
# ASSET BUILDING INSTRUCTIONS
# ------------------------------------------------------------------
# Run these from the game root before serving behind Caddy:
#
#   evennia clearweb       # clear stale web assets (safe)
#   evennia collectstatic  # gather static assets into STATIC_ROOT
#
# The Caddy reverse proxy should serve STATIC_ROOT at /static/ and
# forward /ws/ to the internal WebSocket port (4012). See Caddyfile
# in the project root for the exact configuration.
######################################################################
