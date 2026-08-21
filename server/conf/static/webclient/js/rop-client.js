/**
 * Rites of Passage — Custom WebSocket Client v2.0
 * ================================================
 * Connects directly to Evennia's WebSocket port 4012 using the
 * v1.evennia.com subprotocol.  No jQuery, no GoldenLayout, no
 * external dependencies — just vanilla JS and a clean terminal UI.
 *
 * Features:
 *   - Full ANSI SGR → HTML color engine (16-col, 256-col, true color)
 *   - Integrated Web Audio SFX engine with text-pattern triggers
 *   - Command history (Up/Down arrow keys)
 *   - Smart auto-scroll (pauses on manual scroll-up)
 *   - Focus management (click terminal → focus input)
 *   - Custom JSON audio payload support from Evennia backend
 *
 * Evennia v1 Wire Format:
 *   Client → Server:  ["text", ["command"], {}]
 *   Server → Client:  ["text", ["<HTML or ANSI text>"], {}]
 *   Audio payload:    ["audio", {"trigger": "combat_hit"}, {}]
 */

(function () {
    "use strict";

    // HTML entity definitions (built without literal & to prevent editor corruption)
    var _a = String.fromCharCode(38);
    var AMP  = _a + "amp;";
    var LT   = _a + "lt;";
    var GT   = _a + "gt;";
    var QUOT = _a + "quot;";
    var APOS = _a + "#039;";

    // ── DOM references ──
    var terminal    = document.getElementById("rop-terminal");
    var inputEl     = document.getElementById("rop-command");
    var statusDot   = document.getElementById("rop-status-dot");
    var statusText  = document.getElementById("rop-status-text");
    var reconnectBtn = document.getElementById("rop-reconnect-btn");
    var muteBtn     = document.getElementById("rop-mute-btn");
    var volumeSlider = document.getElementById("rop-volume-slider");

    // ── Configuration ──
    var CFG = window.ROP_CONFIG || {};
    var WS_PROTOCOL = CFG.subprotocol || "v1.evennia.com";
    var WS_PORT = CFG.websocketPort || 4012;
    var RECONNECT_DELAY_MS = 2000;
    var MAX_RECONNECT_DELAY_MS = 30000;
    var SCROLL_THRESHOLD = 50;

    var socket = null;
    var reconnectTimer = null;
    var reconnectAttempts = 0;
    var intentionalClose = false;
    var cuid = generateUID();

    // ── Command History ──
    var MAX_HISTORY = 500;
    var cmdHistory = [];
    var historyIndex = -1;
    var currentDraft = "";

    // ── Smart Auto-Scroll State ──
    var userScrolledUp = false;

    // ── Prompt persistence ──
    // Cache the last known prompt HTML so the status bar never goes blank.
    // When incoming server text does NOT contain a prompt update, the
    // client holds and continues displaying this cached state in real time.
    var lastPromptHtml = "";

    // ── Volume / Mute State ──
    var audioMuted = false;
    var audioVolume = 0.7;

    // ═══════════════════════════════════════════════════════════════
    // ANSI SGR → HTML ENGINE
    // ═══════════════════════════════════════════════════════════════

    var ANSI_RE = /\x1b\[([\d;]*)m/g;

    var FG_COLORS_16 = [
        "#000000", "#cc0000", "#4e9a06", "#c4a000",
        "#3465a4", "#75507b", "#06989a", "#d3d7cf",
        "#555753", "#ef2929", "#8ae234", "#fce94f",
        "#729fcf", "#ad7fa8", "#34e2e2", "#eeeeec"
    ];

    var CUBE_LEVELS = [0x00, 0x5f, 0x87, 0xaf, 0xd7, 0xff];

    function cubeToHex(idx) {
        var r = CUBE_LEVELS[Math.floor(idx / 36) % 6];
        var g = CUBE_LEVELS[Math.floor(idx / 6) % 6];
        var b = CUBE_LEVELS[idx % 6];
        return "#" + hex(r) + hex(g) + hex(b);
    }

    function grayscaleToHex(idx) {
        var val = (idx - 232) * 10 + 8;
        var v = Math.min(255, val);
        return "#" + hex(v) + hex(v) + hex(v);
    }

    function hex(v) {
        return ("0" + v.toString(16)).slice(-2);
    }

    function ansiToHtml(text) {
        if (text.indexOf("\x1b[") === -1) {
            return escapeHtml(text);
        }

        var tokens = [];
        var lastIndex = 0;
        var openSpans = 0;
        var match;
        var re = new RegExp(ANSI_RE.source, "g");

        while ((match = re.exec(text)) !== null) {
            if (match.index > lastIndex) {
                tokens.push(escapeHtml(text.substring(lastIndex, match.index)));
            }
            lastIndex = re.lastIndex;

            var params = match[1] ? match[1].split(";").map(Number) : [0];
            var classes = [];
            var styles = [];

            var i = 0;
            while (i < params.length) {
                var p = params[i];

                if (p === 0) {
                    while (openSpans > 0) {
                        tokens.push("</span>");
                        openSpans--;
                    }
                    classes.length = 0;
                    styles.length = 0;
                    i++;
                    continue;
                }

                if (p === 1) { classes.push("ansi-bold"); i++; continue; }
                if (p === 2) { classes.push("ansi-dim"); i++; continue; }
                if (p === 3) { classes.push("ansi-italic"); i++; continue; }
                if (p === 4) { classes.push("ansi-underline"); i++; continue; }
                if (p === 5) { classes.push("ansi-blink"); i++; continue; }
                if (p === 7) { classes.push("ansi-reverse"); i++; continue; }
                if (p === 8) { classes.push("ansi-hidden"); i++; continue; }
                if (p === 9) { classes.push("ansi-strikethrough"); i++; continue; }

                if (p === 22) { classes = classes.filter(function (c) { return c !== "ansi-bold" && c !== "ansi-dim"; }); i++; continue; }
                if (p === 23) { classes = classes.filter(function (c) { return c !== "ansi-italic"; }); i++; continue; }
                if (p === 24) { classes = classes.filter(function (c) { return c !== "ansi-underline"; }); i++; continue; }
                if (p === 25) { classes = classes.filter(function (c) { return c !== "ansi-blink"; }); i++; continue; }
                if (p === 27) { classes = classes.filter(function (c) { return c !== "ansi-reverse"; }); i++; continue; }
                if (p === 28) { classes = classes.filter(function (c) { return c !== "ansi-hidden"; }); i++; continue; }
                if (p === 29) { classes = classes.filter(function (c) { return c !== "ansi-strikethrough"; }); i++; continue; }

                if (p >= 30 && p <= 37) { classes.push("ansi-fg-" + (p - 30)); i++; continue; }
                if (p >= 90 && p <= 97) { classes.push("ansi-fg-" + (p - 90 + 8)); i++; continue; }
                if (p === 39) {
                    classes = classes.filter(function (c) { return c.indexOf("ansi-fg-") !== 0; });
                    styles = styles.filter(function (s) { return s.indexOf("color:") !== 0; });
                    i++; continue;
                }

                if (p >= 40 && p <= 47) { classes.push("ansi-bg-" + (p - 40)); i++; continue; }
                if (p >= 100 && p <= 107) { classes.push("ansi-bg-" + (p - 100 + 8)); i++; continue; }
                if (p === 49) {
                    classes = classes.filter(function (c) { return c.indexOf("ansi-bg-") !== 0; });
                    styles = styles.filter(function (s) { return s.indexOf("background-color:") !== 0; });
                    i++; continue;
                }

                // 256-color foreground: 38;5;N
                if (p === 38 && params[i + 1] === 5 && typeof params[i + 2] === "number") {
                    var n = params[i + 2];
                    var hc;
                    if (n <= 15) hc = FG_COLORS_16[n];
                    else if (n <= 231) hc = cubeToHex(n - 16);
                    else if (n <= 255) hc = grayscaleToHex(n);
                    else hc = FG_COLORS_16[7];
                    styles.push("color:" + hc);
                    i += 3;
                    continue;
                }

                // 256-color background: 48;5;N
                if (p === 48 && params[i + 1] === 5 && typeof params[i + 2] === "number") {
                    var n2 = params[i + 2];
                    var hc2;
                    if (n2 <= 15) hc2 = FG_COLORS_16[n2];
                    else if (n2 <= 231) hc2 = cubeToHex(n2 - 16);
                    else if (n2 <= 255) hc2 = grayscaleToHex(n2);
                    else hc2 = FG_COLORS_16[7];
                    styles.push("background-color:" + hc2);
                    i += 3;
                    continue;
                }

                // True color foreground: 38;2;R;G;B
                if (p === 38 && params[i + 1] === 2 &&
                    typeof params[i + 2] === "number" &&
                    typeof params[i + 3] === "number" &&
                    typeof params[i + 4] === "number") {
                    var r1 = params[i + 2], g1 = params[i + 3], b1 = params[i + 4];
                    styles.push("color:#" + hex(r1) + hex(g1) + hex(b1));
                    i += 5;
                    continue;
                }

                // True color background: 48;2;R;G;B
                if (p === 48 && params[i + 1] === 2 &&
                    typeof params[i + 2] === "number" &&
                    typeof params[i + 3] === "number" &&
                    typeof params[i + 4] === "number") {
                    var r2 = params[i + 2], g2 = params[i + 3], b2 = params[i + 4];
                    styles.push("background-color:#" + hex(r2) + hex(g2) + hex(b2));
                    i += 5;
                    continue;
                }

                i++;
            }

            if (classes.length > 0 || styles.length > 0) {
                var clsStr = classes.join(" ");
                var styleStr = styles.join(";");
                var tag = '<span class="' + clsStr + '"';
                if (styleStr) tag += ' style="' + styleStr + '"';
                tag += ">";
                tokens.push(tag);
                openSpans++;
            }
        }

        tokens.push(escapeHtml(text.substring(lastIndex)));

        while (openSpans > 0) {
            tokens.push("</span>");
            openSpans--;
        }

        return tokens.join("");
    }

    function escapeHtml(str) {
        return str
            .replace(new RegExp(String.fromCharCode(38), "g"), AMP)
            .replace(new RegExp(String.fromCharCode(60), "g"), LT)
            .replace(new RegExp(String.fromCharCode(62), "g"), GT)
            .replace(new RegExp(String.fromCharCode(34), "g"), QUOT)
            .replace(new RegExp(String.fromCharCode(39), "g"), APOS);
    }

    // ═══════════════════════════════════════════════════════════════
    // AUDIO / SFX ENGINE
    // ═══════════════════════════════════════════════════════════════

    var AUDIO_TRIGGERS = [
        { pattern: /\b(?:hit|strike|slash|bash|pierce|wound|injure)\b.*\b(?:for \d+|hard|solidly)\b/i, url: "https://cdn.dirtysouthjosh.com/rop/sounds/combat_hit.ogg", volume: 0.7, cooldown: 300 },
        { pattern: /\b(?:miss|dodg|evad|parr|block)\w*/i,                                                   url: "https://cdn.dirtysouthjosh.com/rop/sounds/combat_miss.ogg", volume: 0.5, cooldown: 400 },
        { pattern: /\b(?:critical|crit|CRIT|deadly blow|devastat)\b/i,                                         url: "https://cdn.dirtysouthjosh.com/rop/sounds/combat_crit.ogg", volume: 0.8, cooldown: 500 },
        { pattern: /\b(?:died|killed|slain|destroyed|dead|death)\b/i,                                          url: "https://cdn.dirtysouthjosh.com/rop/sounds/combat_death.ogg", volume: 0.85, cooldown: 1000 },
        { pattern: /\b(?:victory|victorious|triumph|vanquish)\b/i,                                              url: "https://cdn.dirtysouthjosh.com/rop/sounds/combat_victory.ogg", volume: 0.75, cooldown: 1000 },
        { pattern: /\b(?:flee|fled|fleeing|retreat|escape)\b/i,                                                 url: "https://cdn.dirtysouthjosh.com/rop/sounds/combat_flee.ogg", volume: 0.6, cooldown: 600 },
        { pattern: /\b(?:cast|spell|incant|chant|invoke|conjure)\b/i,                                           url: "https://cdn.dirtysouthjosh.com/rop/sounds/spell_cast.ogg", volume: 0.65, cooldown: 300 },
        { pattern: /\b(?:heal|cure|restore|mend|regenerate)\b.*\b(?:hit points|HP|health)\b/i,             url: "https://cdn.dirtysouthjosh.com/rop/sounds/spell_heal.ogg", volume: 0.7, cooldown: 400 },
        { pattern: /\b(?:fireball|lightning|blast|explosion|inferno|frost|shadow bolt)\b/i,                      url: "https://cdn.dirtysouthjosh.com/rop/sounds/spell_damage.ogg", volume: 0.75, cooldown: 500 },
        { pattern: /\b(?:buff|enchant|empower|strengthen|haste|shield)\b/i,                                      url: "https://cdn.dirtysouthjosh.com/rop/sounds/spell_buff.ogg", volume: 0.6, cooldown: 400 },
        { pattern: /\b(?:debuff|curse|weaken|slow|poison|disease)\b/i,                                           url: "https://cdn.dirtysouthjosh.com/rop/sounds/spell_debuff.ogg", volume: 0.6, cooldown: 400 },
        { pattern: /\b(?:level up|gained a level|advance|rises in power|new rank)\b/i,                           url: "https://cdn.dirtysouthjosh.com/rop/sounds/level_up.ogg", volume: 0.8, cooldown: 2000 },
        { pattern: /\b(?:quest (?:accepted|begun|started)|new objective)\b/i,                                    url: "https://cdn.dirtysouthjosh.com/rop/sounds/quest_accept.ogg", volume: 0.6, cooldown: 1000 },
        { pattern: /\b(?:quest (?:complete|finished|fulfilled)|reward earned)\b/i,                               url: "https://cdn.dirtysouthjosh.com/rop/sounds/quest_complete.ogg", volume: 0.75, cooldown: 2000 },
        { pattern: /\b(?:boss|BOSS|dread lord|ancient|guardian|overlord|monstrosity)\b/i,                        url: "https://cdn.dirtysouthjosh.com/rop/sounds/boss_encounter.ogg", volume: 0.85, cooldown: 3000 },
        { pattern: /\b(?:boss (?:defeated|slain|vanquished|destroyed|fell))\b/i,                                 url: "https://cdn.dirtysouthjosh.com/rop/sounds/boss_defeat.ogg", volume: 0.9, cooldown: 5000 },
        { pattern: /\b(?:tells? you|whispers? to you|sends you a message)\b/i,                                   url: "https://cdn.dirtysouthjosh.com/rop/sounds/tell_received.ogg", volume: 0.5, cooldown: 1000 },
        { pattern: /\b(?:received \d+ gold|earned \d+ gold|found \d+ gold|picked up \d+ gold)\b/i,      url: "https://cdn.dirtysouthjosh.com/rop/sounds/gold_received.ogg", volume: 0.55, cooldown: 800 },
        { pattern: /\b(?:you (?:pick up|acquire|receive|obtain|find|discover|loot))\b.*\b(?:item|sword|shield|armor|ring|amulet|scroll|potion)\b/i, url: "https://cdn.dirtysouthjosh.com/rop/sounds/item_acquired.ogg", volume: 0.55, cooldown: 800 },
        { pattern: /\b(?:door (?:opens|creaks open|swings open))\b/i,                                            url: "https://cdn.dirtysouthjosh.com/rop/sounds/door_open.ogg", volume: 0.5, cooldown: 600 },
        { pattern: /\b(?:door (?:closes|shuts|slams))\b/i,                                                       url: "https://cdn.dirtysouthjosh.com/rop/sounds/door_close.ogg", volume: 0.5, cooldown: 600 },
        { pattern: /\b(?:portal (?:opens|activates|shimmers|appears))\b/i,                                        url: "https://cdn.dirtysouthjosh.com/rop/sounds/portal_activate.ogg", volume: 0.7, cooldown: 1500 }
    ];

    var audioCooldowns = {};

    function playAudioUrl(url, vol) {
        if (audioMuted) return;
        var now = Date.now();
        var cooldown = audioCooldowns[url] || 0;
        if (now - cooldown < 100) return;
        var effectiveVol = audioVolume * (vol || 0.7);
        try {
            var audio = new Audio(url);
            audio.volume = Math.min(1, Math.max(0, effectiveVol));
            audio.play().catch(function () {});
            audioCooldowns[url] = now;
            audio.addEventListener("ended", function () { audio.remove(); });
            audio.addEventListener("error", function () { audio.remove(); });
        } catch (e) {}
    }

    function processAudioTriggers(text) {
        var stripped = text.replace(/<[^>]*>/g, "");
        var now = Date.now();
        for (var i = 0; i < AUDIO_TRIGGERS.length; i++) {
            var trigger = AUDIO_TRIGGERS[i];
            if (trigger.pattern.test(stripped)) {
                var lastPlayed = audioCooldowns[trigger.url] || 0;
                if (now - lastPlayed < trigger.cooldown) continue;
                audioCooldowns[trigger.url] = now;
                playAudioUrl(trigger.url, trigger.volume);
                break;
            }
        }
    }

    function handleAudioPayload(payload) {
        if (!payload || typeof payload !== "object") return;
        if (payload.url) { playAudioUrl(payload.url, payload.volume || 0.7); return; }
        if (payload.trigger) {
            var key = payload.trigger.toLowerCase();
            for (var i = 0; i < AUDIO_TRIGGERS.length; i++) {
                if (AUDIO_TRIGGERS[i].url.indexOf(key) !== -1) {
                    playAudioUrl(AUDIO_TRIGGERS[i].url, payload.volume || AUDIO_TRIGGERS[i].volume || 0.7);
                    return;
                }
            }
            playAudioUrl("https://cdn.dirtysouthjosh.com/rop/sounds/" + key + ".ogg", payload.volume || 0.7);
        }
    }

    // ── Volume control handlers ──
    if (volumeSlider) {
        volumeSlider.value = Math.round(audioVolume * 100);
        volumeSlider.addEventListener("input", function () {
            audioVolume = parseInt(volumeSlider.value, 10) / 100;
            updateMuteButtonState();
        });
    }

    function updateMuteButtonState() {
        if (muteBtn) {
            if (audioMuted || audioVolume === 0) {
                muteBtn.textContent = "\uD83D\uDD07";
                muteBtn.setAttribute("aria-label", "Unmute game audio");
                muteBtn.classList.add("rop-muted");
            } else {
                muteBtn.textContent = "\uD83D\uDD0A";
                muteBtn.setAttribute("aria-label", "Mute game audio");
                muteBtn.classList.remove("rop-muted");
            }
        }
    }

    if (muteBtn) {
        muteBtn.addEventListener("click", function () {
            audioMuted = !audioMuted;
            updateMuteButtonState();
        });
        updateMuteButtonState();
    }

    // ═══════════════════════════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════════════════════════

    function generateUID() {
        return Math.random().toString(36).substring(2, 15) +
               Math.random().toString(36).substring(2, 15);
    }

    function buildWsUrl() {
        if (CFG.websocketUrl && CFG.websocketUrl.trim() !== "") {
            return CFG.websocketUrl.trim();
        }
        var scheme = (window.location.protocol === "https:") ? "wss" : "ws";
        return scheme + "://" + window.location.hostname + ":" + WS_PORT;
    }

    function log(msg) {
        console.log("[ROP-Client]", msg);
    }

    function setStatus(state, text) {
        statusDot.className = "status-dot " + state;
        statusText.textContent = text;
        reconnectBtn.disabled = (state === "connected");
        inputEl.disabled = (state !== "connected");
        if (state === "connected") inputEl.focus();
    }

    function isAtBottom() {
        return (terminal.scrollTop + terminal.clientHeight + SCROLL_THRESHOLD) >= terminal.scrollHeight;
    }

    function scrollToBottom() {
        terminal.scrollTop = terminal.scrollHeight;
    }

    terminal.addEventListener("scroll", function () {
        userScrolledUp = !isAtBottom();
    });

    function clearWelcome() {
        var welcome = terminal.querySelector(".rop-welcome");
        if (welcome) welcome.remove();
    }

    function appendOutput(html) {
        clearWelcome();
        var div = document.createElement("div");
        div.className = "rop-line";
        div.innerHTML = html;
        terminal.appendChild(div);
        if (!userScrolledUp) scrollToBottom();
    }

    function appendSystemMessage(text, cls) {
        clearWelcome();
        var div = document.createElement("div");
        div.className = "rop-line rop-system " + (cls || "");
        div.textContent = text;
        terminal.appendChild(div);
        if (!userScrolledUp) scrollToBottom();
    }

    // ── Prompt persistence helpers ──

    function ensurePromptBar() {
        var promptBar = document.getElementById("rop-status-prompt");
        if (!promptBar) {
            promptBar = document.createElement("div");
            promptBar.id = "rop-status-prompt";
            promptBar.className = "rop-status-prompt";
            var inputBar = document.getElementById("rop-input-bar");
            if (inputBar && inputBar.parentNode) {
                inputBar.parentNode.insertBefore(promptBar, inputBar);
            } else if (terminal && terminal.parentNode) {
                terminal.parentNode.appendChild(promptBar);
            }
        }
        return promptBar;
    }

    function restoreLastPrompt() {
        if (!lastPromptHtml) return;
        var promptBar = ensurePromptBar();
        promptBar.innerHTML = lastPromptHtml;
    }

    function connect() {
        if (socket && (socket.readyState === WebSocket.OPEN ||
                       socket.readyState === WebSocket.CONNECTING)) return;

        setStatus("connecting", "Connecting...");

        var wsUrl = buildWsUrl();
        var csessid = CFG.csessid || cuid;
        var sep = (wsUrl.indexOf("?") !== -1) ? String.fromCharCode(38) : "?";
        var wsQuery = wsUrl + sep +
                      encodeURIComponent(csessid) +
                      String.fromCharCode(38) +
                      encodeURIComponent(cuid) +
                      String.fromCharCode(38) + "rop-custom";

        log("Connecting to " + wsQuery);

        try {
            socket = new WebSocket(wsQuery, [WS_PROTOCOL]);
        } catch (err) {
            log("WebSocket construction failed: " + err.message);
            setStatus("disconnected", "Connection failed — retrying...");
            scheduleReconnect();
            return;
        }

        socket.onopen = function () {
            log("WebSocket connected.");
            reconnectAttempts = 0;
            setStatus("connected", "Connected");
            appendSystemMessage("Connected to Rites of Passage.", "rop-connected");
            // Restore the last known prompt so the status bar never
            // goes blank across reconnection cycles.
            restoreLastPrompt();
            inputEl.focus();
        };

        socket.onmessage = function (event) {
            try {
                var data = JSON.parse(event.data);
                if (Array.isArray(data) && data.length >= 3) {
                    var cmdname = data[0];
                    var args = data[1];

                    if (cmdname === "text" && args.length > 0) {
                        var raw = args[0];
                        var html;
                        if (raw.indexOf("\x1b[") !== -1) {
                            html = ansiToHtml(raw);
                            processAudioTriggers(raw);
                        } else if (raw.indexOf("<") !== -1 && raw.indexOf(">") !== -1) {
                            html = raw;
                            processAudioTriggers(raw);
                        } else {
                            html = escapeHtml(raw);
                            processAudioTriggers(raw);
                        }
                        appendOutput(html);
                    } else if (cmdname === "prompt" && args.length > 0) {
                        // MajorMUD-style: update the fixed status prompt bar.
                        // The bar is pinned between the terminal and input bar
                        // and NEVER scrolls — it stays as a persistent status bar.
                        var promptBar = ensurePromptBar();
                        var rawPrompt = args[0];
                        var rendered;
                        if (rawPrompt.indexOf("\x1b[") !== -1) {
                            rendered = ansiToHtml(rawPrompt);
                        } else if (rawPrompt.indexOf("<") !== -1 && rawPrompt.indexOf(">") !== -1) {
                            rendered = rawPrompt;
                        } else {
                            rendered = escapeHtml(rawPrompt);
                        }
                        promptBar.innerHTML = rendered;
                        // Cache for real-time persistence — if subsequent
                        // server text does not include a prompt update, the
                        // bar continues to display this last known state.
                        lastPromptHtml = rendered;
                    } else if (cmdname === "audio") {
                        handleAudioPayload(args[0]);
                    } else {
                        log("Unhandled server command: " + cmdname);
                    }
                }
            } catch (e) {
                log("Failed to parse server message: " + e.message);
            }
        };

        socket.onclose = function (event) {
            log("WebSocket closed (code=" + event.code + ").");
            socket = null;
            if (!intentionalClose) {
                setStatus("disconnected", "Disconnected — reconnecting...");
                appendSystemMessage("Connection lost. Reconnecting...", "rop-disconnected");
                scheduleReconnect();
            } else {
                setStatus("disconnected", "Disconnected");
                intentionalClose = false;
            }
            // Restore the last known prompt on disconnect so the status
            // bar never goes blank across disconnection cycles.
            restoreLastPrompt();
        };

        socket.onerror = function () {
            log("WebSocket error.");
        };
    }

    function disconnect() {
        intentionalClose = true;
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        if (socket) {
            try { socket.send(JSON.stringify(["websocket_close", [], {}])); } catch (e) {}
            socket.close();
            socket = null;
        }
    }

    function scheduleReconnect() {
        if (reconnectTimer) clearTimeout(reconnectTimer);
        reconnectAttempts++;
        var delay = Math.min(
            RECONNECT_DELAY_MS * Math.pow(1.5, reconnectAttempts - 1),
            MAX_RECONNECT_DELAY_MS
        );
        log("Reconnecting in " + (delay / 1000) + "s (attempt " + reconnectAttempts + ")");
        reconnectTimer = setTimeout(function () { connect(); }, delay);
    }

    function sendCommand(text) {
        if (!text || !text.trim()) return;
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            appendSystemMessage("Not connected to the server.", "rop-warning");
            return;
        }
        var trimmed = text.trim();
        if (cmdHistory.length === 0 || cmdHistory[cmdHistory.length - 1] !== trimmed) {
            cmdHistory.push(trimmed);
            if (cmdHistory.length > MAX_HISTORY) cmdHistory.shift();
        }
        historyIndex = cmdHistory.length;
        currentDraft = "";
        socket.send(JSON.stringify(["text", [trimmed], {}]));
    }

    inputEl.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            var cmd = inputEl.value;
            inputEl.value = "";
            sendCommand(cmd);
            return;
        }

        if (event.key === "ArrowUp") {
            event.preventDefault();
            if (cmdHistory.length === 0) return;
            if (historyIndex === cmdHistory.length) currentDraft = inputEl.value;
            if (historyIndex > 0) { historyIndex--; inputEl.value = cmdHistory[historyIndex]; }
            inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length);
            return;
        }

        if (event.key === "ArrowDown") {
            event.preventDefault();
            if (historyIndex < cmdHistory.length - 1) {
                historyIndex++;
                inputEl.value = cmdHistory[historyIndex];
            } else {
                historyIndex = cmdHistory.length;
                inputEl.value = currentDraft;
            }
            inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length);
            return;
        }

        if (event.key === "Tab") { event.preventDefault(); return; }

        if (event.key.length === 1 || event.key === "Backspace" || event.key === "Delete") {
            historyIndex = cmdHistory.length;
            currentDraft = "";
        }
    });

    reconnectBtn.addEventListener("click", function () {
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        reconnectAttempts = 0;
        connect();
    });

    terminal.addEventListener("click", function (e) {
        if (window.getSelection && window.getSelection().toString().length > 0) return;
        if (socket && socket.readyState === WebSocket.OPEN) inputEl.focus();
    });

    var inputBar = document.getElementById("rop-input-bar");
    if (inputBar) {
        inputBar.addEventListener("click", function () { inputEl.focus(); });
    }

    document.addEventListener("keydown", function (e) {
        var tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : "";
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        if (e.ctrlKey || e.altKey || e.metaKey) return;
        if (e.key.length === 1 && socket && socket.readyState === WebSocket.OPEN) {
            e.preventDefault();
            inputEl.focus();
            inputEl.value += e.key;
            inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length);
        }
    });

    window.addEventListener("beforeunload", function () { disconnect(); });

    log("ROP WebClient v2.0 initializing.");
    connect();
})();