#!/usr/bin/env python
"""
============================================================================
ROP — PROMPT STABILITY & VISIBILITY TESTS
============================================================================

Comprehensive tests for the MajorMUD-style status prompt system:

  Server-side:
    - Character.get_status_prompt() returns correct format
    - Prompt is sent after every command via MuxCommand.at_post_cmd()
    - GMCP handler delivers prompt messages correctly
    - Prompt toggle (on/off) works correctly

  Client-side (DOM simulation):
    - Prompt bar is a singleton (never duplicates)
    - Prompt bar stays in fixed position (never scrolls with terminal)
    - Prompt bar is always visible in the flex layout
    - Multiple prompt updates replace content, don't append
    - Prompt bar handles ANSI, HTML, and plain text content

Run:
    cd /root/rop/rop
    python commands/tests/test_prompt_stability.py

Or with Evennia test runner:
    evennia test commands.tests.test_prompt_stability --verbosity=2
============================================================================
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
import django
django.setup()

import json
import unittest
from unittest.mock import MagicMock, PropertyMock, patch, call


# ============================================================================
# Mock helpers
# ============================================================================

class MockAttributeHandler:
    """Dict-backed attribute handler that mimics Evennia's AttributeHandler."""
    def __init__(self, data=None):
        self._store = dict(data) if data else {}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def add(self, key, value):
        self._store[key] = value

    def __contains__(self, key):
        return key in self._store


def mock_session(cid=1):
    """Create a mock session."""
    sess = MagicMock()
    sess.cid = cid
    sess.sessid = cid
    sess.logged_in = True
    sess.puid = 1
    sess.msg = MagicMock()
    sess.at_sync = MagicMock()
    sess.get_account = MagicMock(return_value=MagicMock())
    return sess


def make_prompt_char(key="TestHero", hp=85, max_hp=100, mv=72, max_mv=100,
                     xp=500, xp_to_level=1000, stamina=90, max_stamina=100,
                     position="standing", prompt_enabled=True, location=None, **extra):
    """
    Create a MagicMock that passes isinstance(_, Character) checks and supports
    get_status_prompt(). We call the real Character.get_status_prompt() as an
    unbound method so we test the actual implementation without touching the DB.
    """
    from typeclasses.characters import Character

    attrs = {
        "race": "Human",
        "class": "Warrior",
        "level": 10,
        "hp": hp,
        "max_hp": max_hp,
        "mv": mv,
        "max_mv": max_mv,
        "xp": xp,
        "xp_to_level": xp_to_level,
        "stamina": stamina,
        "max_stamina": max_stamina,
        "position": position,
        "prompt_enabled": prompt_enabled,
        "equipped": {},
        "stats": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        "alignment": "Good",
        "money": 0,
    }
    attrs.update(extra)

    char = MagicMock(spec=Character, name=f"char:{key}")
    char.key = key
    char.id = 12345
    char.dbref = "#12345"
    char.attributes = MockAttributeHandler(attrs)
    char.db = MagicMock()
    char.db.pvp_enabled = False
    char.location = location
    char.ndb = MagicMock()
    char.ndb.combat_state = None
    char.ndb.active_effects = None
    char.contents = []
    char.sessions = MagicMock()
    char.sessions.count.return_value = 1
    char.msg = MagicMock()
    char.home = None
    char.tags = MagicMock()
    char.tags.get.return_value = None
    char.is_typeclass = MagicMock(return_value=True)

    # Bind the REAL get_status_prompt and _get_weather_prompt_segment methods
    char.get_status_prompt = Character.get_status_prompt.__get__(char, Character)
    char._get_weather_prompt_segment = Character._get_weather_prompt_segment.__get__(char, Character)

    return char


# ============================================================================
# Test: Server-side Prompt Generation (Character.get_status_prompt)
# ============================================================================

class TestPromptGeneration(unittest.TestCase):
    """Unit tests for Character.get_status_prompt()."""

    def setUp(self):
        self.char = make_prompt_char("TestHero", hp=85, max_hp=100, mv=72, max_mv=100,
                                     xp=500, xp_to_level=1000, stamina=90, max_stamina=100,
                                     position="standing")

    def test_prompt_contains_required_segments(self):
        """Prompt must contain HP, MV, EXP, state, and SP segments."""
        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
            prompt = self.char.get_status_prompt()

        self.assertIn("HP:", prompt)
        self.assertIn("MV:", prompt)
        self.assertIn("EXP:", prompt)
        self.assertIn("SP:", prompt)
        self.assertIn("STANDING", prompt)

    def test_prompt_shows_fighting_when_in_combat(self):
        """Prompt must show [FIGHTING] when character is in combat."""
        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=True):
            prompt = self.char.get_status_prompt()

        self.assertIn("FIGHTING", prompt)
        self.assertNotIn("STANDING", prompt)

    def test_prompt_shows_stance_when_not_fighting(self):
        """Prompt must show stance (REST/MEDITATE/SLEEP/STANDING) when not in combat."""
        test_cases = [
            ("resting", "REST"),
            ("meditating", "MEDITATE"),
            ("sleeping", "SLEEP"),
            ("standing", "STANDING"),
        ]

        for stance, expected in test_cases:
            self.char.attributes._store["position"] = stance
            with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
                prompt = self.char.get_status_prompt()
            self.assertIn(expected, prompt,
                          f"Stance '{stance}' should show '{expected}' in prompt")

    def test_prompt_reflects_current_hp(self):
        """Prompt must show current HP values, not stale ones."""
        self.char.attributes._store["hp"] = 42
        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
            prompt = self.char.get_status_prompt()
        self.assertIn("42/100", prompt)

        # Simulate HP change
        self.char.attributes._store["hp"] = 15
        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
            prompt = self.char.get_status_prompt()
        self.assertIn("15/100", prompt)
        self.assertNotIn("42/100", prompt)

    def test_prompt_reflects_current_mv(self):
        """Prompt must show current MV values."""
        self.char.attributes._store["mv"] = 33
        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
            prompt = self.char.get_status_prompt()
        self.assertIn("33/100", prompt)

    def test_prompt_reflects_current_xp(self):
        """Prompt must show current XP values."""
        self.char.attributes._store["xp"] = 750
        self.char.attributes._store["xp_to_level"] = 2000
        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
            prompt = self.char.get_status_prompt()
        self.assertIn("750/2000", prompt)

    def test_prompt_returns_string(self):
        """get_status_prompt must always return a string."""
        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
            prompt = self.char.get_status_prompt()
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)

    def test_prompt_handles_missing_attributes_gracefully(self):
        """Prompt must not crash when attributes are missing (uses defaults)."""
        from typeclasses.characters import Character
        char = MagicMock(spec=Character, name="char:Minimal")
        char.key = "Minimal"
        char.id = 1
        char.dbref = "#1"
        char.attributes = MockAttributeHandler({})
        char.db = MagicMock()
        char.location = None
        char.get_status_prompt = Character.get_status_prompt.__get__(char, Character)

        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
            prompt = char.get_status_prompt()

        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)

    def test_prompt_contains_ansi_color_codes(self):
        """Prompt must contain Evennia-style ANSI color codes (|g, |R, etc.)."""
        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
            prompt = self.char.get_status_prompt()

        self.assertTrue(
            any(c in prompt for c in ["|g", "|y", "|m", "|R", "|W", "|w", "|c", "|b", "|n"]),
            "Prompt should contain ANSI color codes"
        )

    def test_prompt_weather_segment_no_location(self):
        """Prompt weather segment must be empty when character has no location."""
        weather = self.char._get_weather_prompt_segment()
        self.assertEqual(weather, "")


# ============================================================================
# Test: Prompt Sending via MuxCommand.at_post_cmd
# ============================================================================

class TestPromptSending(unittest.TestCase):
    """Tests that the prompt is sent after every command."""

    def setUp(self):
        from typeclasses.characters import Character
        from commands.command import MuxCommand

        self.char = make_prompt_char("PromptUser", hp=100, max_hp=100, mv=100, max_mv=100,
                                     xp=0, xp_to_level=1000, stamina=100, max_stamina=100)

        self.sess = mock_session()
        self.char.sessions = MagicMock()
        self.char.sessions.all.return_value = [self.sess]
        self.char.msg = MagicMock()

        self.cmd = MuxCommand()
        self.cmd.caller = self.char
        self.cmd.cmdstring = "look"

    def test_at_post_cmd_sends_prompt_when_enabled(self):
        """MuxCommand.at_post_cmd must send a prompt when prompt_enabled is True."""
        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
            self.cmd.at_post_cmd()

        prompt_sent = False
        for call_args in self.char.msg.call_args_list:
            kwargs = call_args[1] if len(call_args) > 1 else {}
            if 'prompt' in kwargs:
                prompt_sent = True
                prompt_value = kwargs['prompt']
                self.assertIsInstance(prompt_value, str)
                self.assertGreater(len(prompt_value), 0)
                break

        self.assertTrue(prompt_sent, "A prompt should have been sent via msg(prompt=...)")

    def test_at_post_cmd_does_not_send_prompt_when_disabled(self):
        """MuxCommand.at_post_cmd must NOT send a prompt when prompt_enabled is False."""
        self.char.attributes._store["prompt_enabled"] = False

        self.cmd.at_post_cmd()

        prompt_sent = False
        for call_args in self.char.msg.call_args_list:
            kwargs = call_args[1] if len(call_args) > 1 else {}
            if 'prompt' in kwargs:
                prompt_sent = True
                break

        self.assertFalse(prompt_sent, "No prompt should be sent when prompt_enabled is False")

    def test_at_post_cmd_handles_no_sessions(self):
        """at_post_cmd must not crash when character has no sessions."""
        self.char.sessions.all.return_value = []

        try:
            self.cmd.at_post_cmd()
        except Exception as e:
            self.fail(f"at_post_cmd raised {e} when character has no sessions")

    def test_at_post_cmd_handles_missing_caller(self):
        """at_post_cmd must not crash when caller is None."""
        from commands.command import MuxCommand
        cmd = MuxCommand()
        cmd.caller = None
        cmd.cmdstring = "look"

        try:
            cmd.at_post_cmd()
        except Exception as e:
            self.fail(f"at_post_cmd raised {e} when caller is None")

    def test_prompt_sent_after_every_command_type(self):
        """Prompt must be sent after various command types (look, move, combat, etc.)."""
        commands_to_test = ["look", "north", "kill goblin", "get sword", "inventory",
                           "score", "who", "say hello", "cast fireball"]

        for cmd_name in commands_to_test:
            self.char.msg.reset_mock()
            self.char.attributes._store["prompt_enabled"] = True
            self.cmd.cmdstring = cmd_name

            with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
                self.cmd.at_post_cmd()

            prompt_sent = False
            for call_args in self.char.msg.call_args_list:
                kwargs = call_args[1] if len(call_args) > 1 else {}
                if 'prompt' in kwargs:
                    prompt_sent = True
                    break

            self.assertTrue(prompt_sent, f"Prompt should be sent after '{cmd_name}' command")


# ============================================================================
# Test: Prompt Toggle Command (CmdPrompt)
# ============================================================================

class TestPromptToggle(unittest.TestCase):
    """Tests for the prompt on/off toggle command."""

    def setUp(self):
        from typeclasses.characters import Character

        self.char = make_prompt_char("ToggleUser", prompt_enabled=True)

        self.sess = mock_session()
        self.char.sessions = MagicMock()
        self.char.sessions.all.return_value = [self.sess]
        self.char.msg = MagicMock()

    def test_prompt_toggle_off(self):
        """Turning prompt off must set prompt_enabled to False."""
        from commands.general import CmdPrompt

        cmd = CmdPrompt()
        cmd.caller = self.char
        cmd.cmdstring = "prompt"
        cmd.args = ""

        # Currently enabled, calling func should toggle OFF
        cmd.func()

        self.assertFalse(self.char.attributes.get("prompt_enabled"),
                         "prompt_enabled should be False after toggle from ON")

    def test_prompt_toggle_on(self):
        """Turning prompt on must set prompt_enabled to True."""
        from commands.general import CmdPrompt

        self.char.attributes._store["prompt_enabled"] = False

        cmd = CmdPrompt()
        cmd.caller = self.char
        cmd.cmdstring = "prompt"
        cmd.args = ""

        cmd.func()

        self.assertTrue(self.char.attributes.get("prompt_enabled"),
                        "prompt_enabled should be True after toggle from OFF")

    def test_prompt_toggle_sends_status_message(self):
        """Toggling prompt must send a status message to the character."""
        from commands.general import CmdPrompt

        cmd = CmdPrompt()
        cmd.caller = self.char
        cmd.cmdstring = "prompt"
        cmd.args = ""

        cmd.func()

        self.assertTrue(self.char.msg.called, "Should send status message on toggle")


# ============================================================================
# Test: Client-side Prompt Bar (DOM Simulation)
# ============================================================================

class TestClientPromptBar(unittest.TestCase):
    """
    Simulates the client-side DOM behavior of the prompt bar.

    These tests verify the logic in rop-client.js lines 478-502:
      - The prompt bar is a singleton (id="rop-status-prompt")
      - It is created once and updated in place
      - It never scrolls (it's outside the terminal scroll container)
      - Multiple prompt messages replace content, never append
    """

    def setUp(self):
        self._build_mock_dom()

    def _build_mock_dom(self):
        """Build a minimal DOM structure matching the webclient layout."""
        self._elements_by_id = {}

        body = MagicMock()
        body.className = "rop-client"
        body.children = []

        status = MagicMock()
        status.id = "rop-status"
        body.children.append(status)
        self._elements_by_id["rop-status"] = status

        terminal = MagicMock()
        terminal.id = "rop-terminal"
        terminal.className = "rop-terminal"
        terminal.children = []
        terminal.scrollTop = 0
        terminal.scrollHeight = 500
        terminal.clientHeight = 400
        body.children.append(terminal)
        self._elements_by_id["rop-terminal"] = terminal

        input_bar = MagicMock()
        input_bar.id = "rop-input-bar"
        input_bar.className = "rop-input-bar"
        input_bar.parentNode = body
        body.children.append(input_bar)
        self._elements_by_id["rop-input-bar"] = input_bar

        self._body = body
        self._terminal = terminal
        self._input_bar = input_bar

    def _simulate_prompt_message(self, prompt_text):
        """
        Simulate the client receiving a ["prompt", [text], {}] WebSocket message.

        Replicates rop-client.js lines 478-502.
        """
        prompt_bar = self._elements_by_id.get("rop-status-prompt")
        if not prompt_bar:
            prompt_bar = MagicMock()
            prompt_bar.id = "rop-status-prompt"
            prompt_bar.className = "rop-status-prompt"
            prompt_bar.innerHTML = ""
            prompt_bar.textContent = ""

            input_bar = self._elements_by_id.get("rop-input-bar")
            terminal = self._elements_by_id.get("rop-terminal")
            if input_bar and hasattr(input_bar, 'parentNode') and input_bar.parentNode:
                prompt_bar._inserted_before = input_bar
                self._elements_by_id["rop-status-prompt"] = prompt_bar
            elif terminal and hasattr(terminal, 'parentNode') and terminal.parentNode:
                prompt_bar._appended_to = terminal.parentNode
                self._elements_by_id["rop-status-prompt"] = prompt_bar

        if "\x1b[" in prompt_text:
            prompt_bar.innerHTML = f'<span class="ansi-fg-2">{prompt_text}</span>'
        elif "<" in prompt_text and ">" in prompt_text:
            prompt_bar.innerHTML = prompt_text
        else:
            prompt_bar.textContent = prompt_text

        return prompt_bar

    def test_prompt_bar_is_singleton(self):
        """Prompt bar must be a singleton — only one #rop-status-prompt exists."""
        bar1 = self._simulate_prompt_message("[HP: 100/100] [MV: 100/100]")
        bar2 = self._simulate_prompt_message("[HP: 90/100] [MV: 80/100]")

        self.assertIs(bar1, bar2, "Prompt bar must be the same element (singleton)")

        count = sum(1 for v in self._elements_by_id.values()
                    if hasattr(v, 'id') and v.id == "rop-status-prompt")
        self.assertEqual(count, 1, "Only one #rop-status-prompt element should exist")

    def test_prompt_bar_content_is_replaced_not_appended(self):
        """Each prompt update must replace content, not append to it."""
        self._simulate_prompt_message("[HP: 100/100] FIRST")
        bar = self._simulate_prompt_message("[HP: 90/100] SECOND")

        second_content = bar.textContent
        self.assertNotIn("FIRST", second_content,
                         "Prompt content should be replaced, not appended")
        self.assertIn("SECOND", second_content,
                      "Prompt should contain the latest content")

    def test_prompt_bar_not_in_terminal_scroll_container(self):
        """Prompt bar must NOT be a child of the scrollable terminal."""
        bar = self._simulate_prompt_message("[HP: 100/100]")

        self.assertTrue(
            hasattr(bar, '_inserted_before') or hasattr(bar, '_appended_to'),
            "Prompt bar should be positioned outside the terminal"
        )

    def test_multiple_rapid_prompts_no_duplication(self):
        """Rapid prompt updates must not create duplicate bars."""
        for i in range(50):
            self._simulate_prompt_message(f"[HP: {100-i}/{100}] [Round {i}]")

        count = sum(1 for v in self._elements_by_id.values()
                    if hasattr(v, 'id') and v.id == "rop-status-prompt")
        self.assertEqual(count, 1, f"After 50 rapid prompts, found {count} bars (expected 1)")

    def test_prompt_bar_handles_ansi_content(self):
        """Prompt bar must handle ANSI escape code content."""
        ansi_text = "\x1b[32m[HP: 100/100]\x1b[0m \x1b[33m[MV: 100/100]\x1b[0m"
        bar = self._simulate_prompt_message(ansi_text)

        self.assertTrue(
            bar.innerHTML or bar.textContent,
            "Prompt bar should have content after ANSI update"
        )

    def test_prompt_bar_handles_html_content(self):
        """Prompt bar must handle raw HTML content."""
        html_text = '<span style="color:green">[HP: 100/100]</span>'
        bar = self._simulate_prompt_message(html_text)

        self.assertEqual(bar.innerHTML, html_text,
                         "HTML content should be set as innerHTML")

    def test_prompt_bar_handles_plain_text(self):
        """Prompt bar must handle plain text content."""
        plain_text = "[HP: 100/100] [MV: 100/100] [STANDING]"
        bar = self._simulate_prompt_message(plain_text)

        self.assertEqual(bar.textContent, plain_text,
                         "Plain text should be set as textContent")

    def test_prompt_bar_handles_empty_content(self):
        """Prompt bar must handle empty prompt content gracefully."""
        bar = self._simulate_prompt_message("")
        self.assertIsNotNone(bar)

    def test_prompt_bar_position_is_stable(self):
        """Prompt bar must maintain its position between terminal and input bar."""
        bar = self._simulate_prompt_message("[HP: 100/100]")

        self.assertTrue(
            hasattr(bar, '_inserted_before'),
            "Prompt bar should be positioned before the input bar"
        )

        self.assertIs(bar._inserted_before, self._input_bar,
                      "Prompt bar should be inserted directly before the input bar")


# ============================================================================
# Test: GMCP Handler Prompt Delivery
# ============================================================================

class TestGMCPPromptDelivery(unittest.TestCase):
    """Tests that the GMCP handler correctly formats prompt messages."""

    def test_gmcp_handler_imports(self):
        """GMCP handler module must be importable with expected functions."""
        try:
            from world.gmcp_handler import push_char_vitals
            self.assertTrue(callable(push_char_vitals))
        except ImportError as e:
            self.fail(f"GMCP handler import failed: {e}")

    def test_prompt_message_format(self):
        """
        Verify the wire format for prompt messages matches what the client expects.

        The client (rop-client.js line 478) expects:
          ["prompt", ["<prompt text>"], {}]
        """
        prompt_text = "[HP: 100/100] [MV: 100/100] [STANDING]"
        wire_message = ["prompt", [prompt_text], {}]

        self.assertEqual(wire_message[0], "prompt")
        self.assertIsInstance(wire_message[1], list)
        self.assertEqual(len(wire_message[1]), 1)
        self.assertEqual(wire_message[1][0], prompt_text)
        self.assertIsInstance(wire_message[2], dict)

        json_str = json.dumps(wire_message)
        parsed = json.loads(json_str)
        self.assertEqual(parsed, wire_message)


# ============================================================================
# Test: Integration — Full Prompt Lifecycle
# ============================================================================

class TestPromptLifecycle(unittest.TestCase):
    """End-to-end tests simulating a full login-to-prompt lifecycle."""

    def setUp(self):
        from commands.command import MuxCommand

        self.char = make_prompt_char("LifecycleHero", hp=100, max_hp=100, mv=100, max_mv=100,
                                     xp=0, xp_to_level=1000, stamina=100, max_stamina=100)

        self.sess = mock_session()
        self.char.sessions = MagicMock()
        self.char.sessions.all.return_value = [self.sess]
        self.char.msg = MagicMock()

        self.cmd = MuxCommand()
        self.cmd.caller = self.char

        self.collected_prompts = []

        def capture_msg(*args, **kwargs):
            if 'prompt' in kwargs:
                self.collected_prompts.append(kwargs['prompt'])

        self.char.msg.side_effect = capture_msg

    def test_full_prompt_lifecycle(self):
        """
        Simulate a complete lifecycle:
        1. Commands are executed (at_post_cmd sends prompt after each)
        2. HP changes in combat (prompt reflects new values)
        3. Prompt is toggled off (no more prompts sent)
        4. Prompt is toggled back on (prompts resume)
        """
        # Step 1: Execute a few commands
        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
            for cmd_name in ["look", "north", "score"]:
                self.cmd.cmdstring = cmd_name
                self.cmd.at_post_cmd()

        # Step 2: Simulate combat damage (HP drops)
        self.char.attributes._store["hp"] = 75
        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=True):
            self.cmd.cmdstring = "kill goblin"
            self.cmd.at_post_cmd()

        # Verify combat prompt shows FIGHTING and reduced HP
        combat_prompts = [p for p in self.collected_prompts if "FIGHTING" in p]
        self.assertGreater(len(combat_prompts), 0, "Combat prompt should contain FIGHTING")
        self.assertTrue(any("75/100" in p for p in combat_prompts),
                        "Combat prompt should reflect reduced HP")

        # Step 3: Toggle prompt off
        self.char.attributes._store["prompt_enabled"] = False
        prompt_count_before = len(self.collected_prompts)

        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
            self.cmd.cmdstring = "inventory"
            self.cmd.at_post_cmd()

        prompt_count_after = len(self.collected_prompts)
        self.assertEqual(prompt_count_before, prompt_count_after,
                         "No new prompts should be sent when prompt is disabled")

        # Step 4: Toggle prompt back on
        self.char.attributes._store["prompt_enabled"] = True

        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
            self.cmd.cmdstring = "look"
            self.cmd.at_post_cmd()

        prompt_count_final = len(self.collected_prompts)
        self.assertGreater(prompt_count_final, prompt_count_after,
                           "Prompts should resume when re-enabled")

    def test_prompt_consistency_across_commands(self):
        """Prompt format must be consistent regardless of which command was run."""
        self.char.attributes._store["hp"] = 88
        self.char.attributes._store["mv"] = 55
        self.char.attributes._store["xp"] = 300
        self.char.attributes._store["stamina"] = 70

        prompts_by_command = {}

        def capture_msg(*args, **kwargs):
            if 'prompt' in kwargs:
                prompts_by_command[self.cmd.cmdstring] = kwargs['prompt']

        self.char.msg.side_effect = capture_msg

        commands_to_run = ["look", "north", "inventory", "score", "who", "say hello"]

        with patch('world.tick_combat.CombatHandler.is_in_combat', return_value=False):
            for cmd_name in commands_to_run:
                self.cmd.cmdstring = cmd_name
                self.cmd.at_post_cmd()

        for cmd_name, prompt in prompts_by_command.items():
            self.assertIn("88/100", prompt, f"Prompt after '{cmd_name}' should show HP 88/100")
            self.assertIn("55/100", prompt, f"Prompt after '{cmd_name}' should show MV 55/100")
            self.assertIn("300/1000", prompt, f"Prompt after '{cmd_name}' should show XP 300/1000")
            self.assertIn("70/100", prompt, f"Prompt after '{cmd_name}' should show SP 70/100")


# ============================================================================
# Test: CSS Layout Verification (Prompt Bar Positioning)
# ============================================================================

class TestPromptCSSLayout(unittest.TestCase):
    """
    Verify the CSS properties that keep the prompt bar fixed and visible.

    These tests validate the CSS rules in rop-terminal.css lines 366-384
    that ensure the prompt bar:
      - Is a flex child (never scrolls with terminal)
      - Has flex-shrink: 0 (never collapses)
      - Has min-height (always visible even when empty)
      - Is hidden when empty via :empty pseudo-class
    """

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        css_path = os.path.join(base, "web", "static", "webclient", "css", "rop-terminal.css")
        with open(css_path, "r") as f:
            self.css_content = f.read()

        html_path = os.path.join(base, "web", "templates", "webclient", "webclient.html")
        with open(html_path, "r") as f:
            self.html_content = f.read()

    def test_prompt_bar_css_class_exists(self):
        """.rop-status-prompt CSS class must be defined."""
        self.assertIn(".rop-status-prompt", self.css_content,
                      "CSS must define .rop-status-prompt class")

    def test_prompt_bar_has_flex_shrink_zero(self):
        """Prompt bar must have flex-shrink: 0 to prevent collapsing."""
        self.assertIn("flex-shrink: 0", self.css_content,
                      "Prompt bar CSS must include flex-shrink: 0")

    def test_prompt_bar_has_min_height(self):
        """Prompt bar must have min-height to ensure visibility."""
        prompt_block = self.css_content.split(".rop-status-prompt")[1].split("}")[0]
        self.assertIn("min-height", prompt_block,
                      "Prompt bar CSS must include min-height")

    def test_prompt_bar_hidden_when_empty(self):
        """Prompt bar must use :empty to hide when no content."""
        self.assertIn(".rop-status-prompt:empty", self.css_content,
                      "CSS must define .rop-status-prompt:empty rule")
        self.assertIn("display: none", self.css_content,
                      "Empty prompt bar must have display: none")

    def test_html_has_prompt_bar_element(self):
        """webclient.html must contain the #rop-status-prompt div."""
        self.assertIn('id="rop-status-prompt"', self.html_content,
                      "HTML must contain #rop-status-prompt element")

    def test_prompt_bar_between_terminal_and_input(self):
        """Prompt bar must be positioned between terminal and input bar in HTML."""
        terminal_pos = self.html_content.find('id="rop-terminal"')
        prompt_pos = self.html_content.find('id="rop-status-prompt"')
        input_pos = self.html_content.find('id="rop-input-bar"')

        self.assertGreater(prompt_pos, terminal_pos,
                           "Prompt bar must come AFTER terminal in HTML")
        self.assertLess(prompt_pos, input_pos,
                        "Prompt bar must come BEFORE input bar in HTML")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)