from evennia.objects.objects import DefaultCharacter


class Character(DefaultCharacter):

    def at_object_creation(self):
        super().at_object_creation()
        self.db.chargen_completed = False
        # Status prompt: enabled by default for all players.
        self.attributes.add("prompt_enabled", True)
        # Initialize empty equipment slots
        self.attributes.add("equipped", {})

    # ------------------------------------------------------------------
    # Phase 6.11 — Memory leak prevention / cleanup
    # ------------------------------------------------------------------

    def at_object_delete(self):
        """
        Clean up non-persistent state and combat references before deletion.

        Prevents dangling ndb references and ensures any active combat
        instances tied to this character are stopped.
        """
        # Stop combat if this character is engaged
        try:
            from world.tick_combat import CombatHandler
            CombatHandler.stop_combat(self)
        except Exception:
            pass

        # Clear any ndb (non-persistent) references
        if hasattr(self, "ndb"):
            try:
                self.ndb.clear()
            except Exception:
                pass

        return super().at_object_delete()

    @property
    def spells(self):
        """Return the SpellHandler for this character."""
        from world.spells import SpellHandler
        return SpellHandler(self)

    @property
    def quests(self):
        """Return the QuestHandler for this character."""
        from world.quests import QuestHandler
        return QuestHandler(self)

    # ------------------------------------------------------------------
    # Phase 1.2 — Status Effects helpers
    # ------------------------------------------------------------------

    def get_active_effects(self):
        """Return the ActiveEffects manager for this character."""
        from world.status_effects import get_active_effects
        return get_active_effects(self)

    def apply_status_effect(self, effect):
        """Apply a status effect to this character."""
        from world.status_effects import apply_status_effect
        return apply_status_effect(self, effect)

    def remove_status_effect(self, slot):
        """Remove all status effects of a given slot type."""
        effects = self.get_active_effects()
        if effects:
            effects.remove_effect_by_slot(slot)

    def clear_all_effects(self):
        """Remove all status effects from this character."""
        effects = self.get_active_effects()
        if effects:
            effects.clear_all()

    def get_effect_display(self):
        """Return a compact display of all active effects."""
        effects = self.get_active_effects()
        if effects:
            return effects.get_effect_display()
        return ""

    # ------------------------------------------------------------------
    # MajorMUD-style Status Prompt
    # ------------------------------------------------------------------

    def get_status_prompt(self):
        """
        Build the MajorMUD-style status prompt line.

        Format (single line, ANSI color-coded):
          [HP: current/max] [MV: current/max] [EXP: current/max] [FIGHTING or state] [SP: current/max] [Weather]

        Combat state is checked via CombatHandler.is_in_combat() which
        reads the live ENGAGEMENTS table — so [FIGHTING] appears and
        disappears instantly when combat starts/stops, with zero stale
        state.

        When not fighting, the character's position (standing/resting/
        meditating/sleeping) is displayed instead.
        """
        hp = self.attributes.get("hp", default=100)
        max_hp = self.attributes.get("max_hp", default=100)
        mv = self.attributes.get("mv", default=100)
        max_mv = self.attributes.get("max_mv", default=100)
        # Phase 2.3: talent pool bonuses (Fleet-Footed, Unbreakable, Mana Reservoir)
        try:
            from world.skill_tree import get_talent_pool_bonuses
            pool = get_talent_pool_bonuses(self)
            max_hp += pool.get("max_hp", 0)
            max_mv += pool.get("max_mv", 0)
        except Exception:
            pass
        exp = self.attributes.get("xp", default=0)
        tnl = self.attributes.get("xp_to_level", default=1000)
        stamina = self.attributes.get("stamina", default=100)
        max_stamina = self.attributes.get("max_stamina", default=100)

        segments = []

        # HP, MV, EXP are always shown
        segments.append(f"|g[HP: {hp}/{max_hp}]|n")
        segments.append(f"|y[MV: {mv}/{max_mv}]|n")
        segments.append(f"|m[EXP: {exp}/{tnl}]|n")

        # FIGHTING or current state — exact toggle, no stale state
        from world.tick_combat import CombatHandler
        if CombatHandler.is_in_combat(self):
            segments.append("|R[FIGHTING]|n")
        else:
            # Show stance/position when not fighting
            stance = self.attributes.get("position", default="standing")
            if stance == "resting":
                segments.append("|y[REST]|n")
            elif stance == "meditating":
                segments.append("|c[MEDITATE]|n")
            elif stance == "sleeping":
                segments.append("|b[SLEEP]|n")
            else:
                segments.append("|W[STANDING]|n")

        # Stamina / SP
        segments.append(f"|w[SP: {stamina}/{max_stamina}]|n")

        # Gold / carried wealth
        try:
            from world.economy import get_prompt_money_segment
            segments.append(get_prompt_money_segment(self))
        except Exception:
            pass

        # Weather condition — always at the end
        weather_part = self._get_weather_prompt_segment()
        if weather_part:
            segments.append(f"{weather_part}")

        return " ".join(segments)

    def _get_weather_prompt_segment(self):
        """
        Return a compact, color-coded weather segment for the status prompt,
        or "" when the character has no location or is indoors.
        """
        location = self.location
        if location is None:
            return ""

        try:
            from world.weather import format_weather_short
            return format_weather_short(location)
        except Exception:
            return ""

    def at_pre_cmd(self):
        """
        Hook called before every command is executed.

        Delivers the MajorMUD-style status prompt automatically whenever
        the player presses enter, so it always reflects current stats.
        Respects the `prompt_enabled` attribute so players can use the
        `prompt` command to toggle it off.

        Also pushes Char.Vitals via GMCP for rich clients (Mudlet, etc.)
        so their GUI health bars and stat displays stay in sync.
        """
        if self.attributes.get("prompt_enabled", default=True):
            self.msg(prompt=self.get_status_prompt())

        # Push GMCP Char.Vitals to all GMCP-capable sessions
        try:
            from world.gmcp_handler import push_char_vitals
            push_char_vitals(self)
        except Exception:
            pass

    def at_post_login(self, session=None, **kwargs):
        # Call super() if Evennia ever adds at_post_login to DefaultCharacter.
        try:
            super().at_post_login(session=session, **kwargs)
        except AttributeError:
            pass

        # Safety net: launch the chargen menu only if this character was
        # created outside of normal chargen (e.g. admin @create) and the
        # flag is missing.  Both chargen.py and charcreate.py now set
        # chargen_completed=True on the newly created character so this
        # guard should rarely trigger during normal play.
        if not self.attributes.has("chargen_completed") or not self.db.chargen_completed:
            from world.chargen import start_chargen
            start_chargen(self)
            return

        # P2.2 — Daily quest reset check on login
        try:
            self.quests.check_daily_resets()
        except Exception:
            pass

        # Display the Message of the Day after successful login
        from world.motd import render_motd
        self.msg(render_motd(self))

        # Phase 8 — Notify friends that this character came online
        try:
            from commands.social import notify_friends_online
            notify_friends_online(self)
        except Exception:
            pass

        # Push initial GMCP data to rich clients (Char.Vitals + Room.Info)
        try:
            from world.gmcp_handler import push_char_vitals, push_room_info
            push_char_vitals(self)
            push_room_info(self)
        except Exception:
            pass

    def at_post_puppet(self, **kwargs):
        """
        Hook called after this character is puppeted by a session.

        Pushes initial GMCP data (Char.Vitals + Room.Info) to the
        newly attached session so rich clients can populate their
        GUI modules immediately on login.
        """
        try:
            from world.gmcp_handler import push_char_vitals, push_room_info
            push_char_vitals(self)
            push_room_info(self)
        except Exception:
            pass

    def at_after_move(self, source_location, **kwargs):
        """
        Hook called after this character moves to a new room.

        Pushes Room.Info via GMCP so rich clients can update their
        mini-maps, room displays, and visible entity lists.
        """
        try:
            from world.gmcp_handler import push_room_info
            push_room_info(self)
        except Exception:
            pass

    def return_appearance(self, looker, **kwargs):
        """
        Override the default return_appearance to provide an enriched,
        detailed view when someone looks at this character (including self).

        Shows character info, stats, health/mana/movement, equipment,
        and physical description.
        """
        if not looker:
            return super().return_appearance(looker, **kwargs)

        # Is the looker looking at themselves?
        is_self = looker == self

        lines = []
        # Name and title
        lines.append(f"|w{self.key}|n")
        if is_self:
            lines.append("(That's you!)")

        lines.append("-" * 50)

        # Race & Class
        race = self.attributes.get("race", default="Unknown")
        charclass = self.attributes.get("class", default="Unknown")
        level = self.attributes.get("level", default=1)

        lines.append(
            f"|cRace:|n {race}   |cClass:|n {charclass}   |cLevel:|n {level}"
        )

        # Stats block
        stats = self.attributes.get("stats", default={})
        if stats:
            stat_line = "  ".join(
                f"|c{k.upper():>3}:|n {v:>2}" for k, v in stats.items()
            )
            lines.append(stat_line)

        # HP / Mana / Movement
        hp = self.attributes.get("hp", default=100)
        max_hp = self.attributes.get("max_hp", default=100)
        mana = self.attributes.get("mana", default=50)
        max_mana = self.attributes.get("max_mana", default=50)
        mv = self.attributes.get("mv", default=100)
        max_mv = self.attributes.get("max_mv", default=100)

        lines.append(
            f"|rHP:|n {hp}/{max_hp}   |bMana:|n {mana}/{max_mana}   "
            f"|yMV:|n {mv}/{max_mv}"
        )

        # Alignment
        alignment = self.attributes.get("alignment", default="Neutral")
        lines.append(f"|cAlignment:|n {alignment}")

        # Warpoints
        warpoints = self.attributes.get("warpoints", default=0)
        lines.append(f"|cWarpoints:|n {warpoints}")

        # Clan
        clan = self.attributes.get("clan", default=None)
        if clan:
            lines.append(f"|cClan:|n {clan}")

        # Phase 6.8 — Outlaw status (visible when looking at any player)
        try:
            from world.alignment_system import is_outlaw
            if is_outlaw(self):
                lines.append("|r[OUTLAW]|n This character is flagged as an Outlaw!")
        except Exception:
            pass

        # Physical description
        desc = self.db.desc
        lines.append("")
        if desc:
            lines.append(f"|wDescription:|n {desc}")
        else:
            lines.append(
                f"|wDescription:|n A {race} {charclass} of level {level}, "
                f"ready for adventure."
            )

        # Armor Set Bonuses (visible on self-look)
        if is_self:
            from world.armor_sets import ArmorSetChecker
            checker = ArmorSetChecker(self)
            set_display = checker.format_display()
            if set_display:
                lines.append(set_display.strip())

        # Equipment (visible to any looker)
        lines.append("")
        lines.append("|wEquipment:|n")
        equipped = self.attributes.get("equipped", default={})
        if equipped:
            for slot, item_name in equipped.items():
                lines.append(f"  |c{slot.capitalize()}:|n {item_name}")
        else:
            lines.append("  |yNothing equipped.|n")

        # Auto-loot / auto-sac status
        autoloot_on = self.attributes.get("autoloot", default=False)
        autosac_on = self.attributes.get("autosac", default=False)
        lines.append(
            f"|cAuto-Loot:|n {'|gON|n' if autoloot_on else '|rOFF|n'}   "
            f"|cAuto-Sacrifice:|n {'|gON|n' if autosac_on else '|rOFF|n'}"
        )

        # Phase 1.2: Active status effects visible on self-look
        if is_self:
            effect_display = self.get_effect_display()
            if effect_display:
                lines.append(f"|rActive Effects:|n {effect_display}")

        # ---- Phase 6.8 — Self-look enhancements ----
        if is_self:
            # Current position
            position = self.attributes.get("position", default="standing")
            lines.append(f"|cPosition:|n {position.capitalize()}")

            # Encumbrance level
            try:
                from world.encumbrance import (
                    get_carry_capacity,
                    get_current_encumbrance,
                )
                capacity = get_carry_capacity(self)
                current_w = get_current_encumbrance(self)
                pct = int(current_w / capacity * 100) if capacity > 0 else 0
                if current_w > capacity:
                    lines.append(
                        f"|cEncumbrance:|n |r{current_w:.1f}/{capacity:.1f} kg "
                        f"({pct}%) — OVERBURDENED|n"
                    )
                elif pct >= 75:
                    lines.append(
                        f"|cEncumbrance:|n |y{current_w:.1f}/{capacity:.1f} kg ({pct}%)|n"
                    )
                else:
                    lines.append(
                        f"|cEncumbrance:|n {current_w:.1f}/{capacity:.1f} kg ({pct}%)"
                    )
            except Exception:
                pass

            # Equipment durability summary
            durability_lines = self._get_equipment_durability_summary()
            if durability_lines:
                lines.append("|wEquipment Durability:|n")
                lines.extend(durability_lines)

            # Practice points remaining
            try:
                session = self.attributes.get("practice_session", default=None)
                if session is not None:
                    pp = getattr(session, "practice_points", 0)
                    lines.append(f"|cPractice Points:|n {pp}")
            except Exception:
                pass

            # Inventory count
            inv = self.contents
            item_count = len([obj for obj in inv if not obj.destination])
            if item_count > 0:
                lines.append(
                    f"\n|wInventory:|n {item_count} item(s). "
                    f"Type |wi|n or |winventory|n to list them."
                )

        return "\n".join(lines)

    def _get_equipment_durability_summary(self):
        """
        Return a list of colour-coded durability lines for equipped gear,
        or an empty list when nothing is equipped.

        Phase 6.8 — self-look equipment durability summary.
        """
        equipped = self.attributes.get("equipped", default={})
        if not equipped:
            return []

        lines = []
        for slot, item_name in equipped.items():
            durability = None
            max_durability = None
            # Locate the equipped item content by name to read durability
            for obj in self.contents:
                if getattr(obj, "destination", None):
                    continue
                if obj.key == item_name and hasattr(obj, "attributes"):
                    durability = obj.attributes.get("durability", default=None)
                    max_durability = obj.attributes.get("max_durability", default=None)
                    break

            if durability is None or max_durability is None:
                continue

            pct = int(durability / max_durability * 100) if max_durability > 0 else 0
            if pct > 75:
                color = "|g"
            elif pct > 50:
                color = "|y"
            elif pct > 25:
                color = "|r"
            else:
                color = "|R"

            lines.append(
                f"    {slot.capitalize():<12} {color}{durability}/{max_durability} ({pct}%)|n"
            )

        return lines

    # ------------------------------------------------------------------
    # Auto-Leveling System
    # ------------------------------------------------------------------

    def award_xp(self, amount):
        """
        Grant XP to the character, automatically triggering level-up checks.

        This should be called whenever a character earns XP (from killing
        mobs, completing quests, etc.) instead of manually setting
        attributes.
        """
        current_xp = self.attributes.get("xp", default=0)
        new_xp = current_xp + amount
        self.attributes.add("xp", new_xp)

        # Loop in case the XP award pushes them through multiple levels
        while self._check_level_up():
            pass

    def _check_level_up(self):
        """
        Check if the character has enough XP to level up.
        If so, perform the level-up and return True.
        If not enough XP, return False (stops the level-up loop).
        """
        from world.rules import xp_to_level, stats_on_level_up, CLASSES, get_racial_bonuses

        level = self.attributes.get("level", default=1)
        current_xp = self.attributes.get("xp", default=0)
        needed = xp_to_level(level)

        if current_xp < needed:
            return False

        # --- Perform Level-Up ---
        new_level = level + 1

        # Deduct the XP cost for this level
        self.attributes.add("xp", current_xp - needed)

        # Update level
        self.attributes.add("level", new_level)

        # Update next-level XP threshold
        next_needed = xp_to_level(new_level)
        self.attributes.add("xp_to_level", next_needed)

        # Boost Max HP
        char_class = self.attributes.get("class", default="Warrior")
        class_data = CLASSES.get(char_class, CLASSES["Warrior"])
        hp_gain = class_data.get("hp_per_level", 10)
        # Racial passive: max HP bonus (Ogre +20%) applies to each level gain
        # so the bonus stays proportional at higher levels.
        try:
            racial = get_racial_bonuses(self)
            hp_pct = racial.get("max_hp_pct", 0)
            if hp_pct:
                hp_gain = int(hp_gain * (1.0 + hp_pct / 100.0))
        except Exception:
            pass
        max_hp = self.attributes.get("max_hp", default=100)
        max_hp += hp_gain
        self.attributes.add("max_hp", max_hp)

        # Boost Max Mana
        mana_gain = class_data.get("mana_per_level", 5)
        # Racial passive: max mana bonus (High Elf +15%).
        try:
            racial = get_racial_bonuses(self)
            mana_pct = racial.get("max_mana_pct", 0)
            if mana_pct:
                mana_gain = int(mana_gain * (1.0 + mana_pct / 100.0))
        except Exception:
            pass
        max_mana = self.attributes.get("max_mana", default=50)
        max_mana += mana_gain
        self.attributes.add("max_mana", max_mana)

        # Boost Max Movement
        max_mv = self.attributes.get("max_mv", default=100)
        max_mv += 5
        self.attributes.add("max_mv", max_mv)

        # Boost base stats (class-specific)
        stat_bonuses = stats_on_level_up(char_class, self)
        stats = self.attributes.get("stats", default={})
        if stats:
            for stat_key, bonus in stat_bonuses.items():
                stats[stat_key] = stats.get(stat_key, 10) + bonus
            self.attributes.add("stats", stats)

        # Refill HP / Mana / MV to new max on level-up
        self.attributes.add("hp", max_hp)
        self.attributes.add("mana", max_mana)
        self.attributes.add("mv", max_mv)

        # Grant new spells available at this level
        new_spells = self._grant_spells_for_level(new_level)
        spell_names = ", ".join(new_spells) if new_spells else "no new spells"

        # Award practice points for this level-up
        from world.guildmaster import award_practice_points
        award_practice_points(self, new_level)

        # Award talent points for this level-up
        from world.skill_tree import award_talent_points
        award_talent_points(self, new_level)

        # Build the bright level-up announcement
        message = (
            f"|y|h{'=' * 55}|n\n"
            f"|c|h          ⚡ LEVEL UP! You are now Level {new_level}! ⚡|n\n"
            f"|y|h{'=' * 55}|n\n"
            f"|gMax HP: |w{max_hp - hp_gain} |r→ |W{max_hp}|n  "
            f"|gMax MP: |w{max_mana - mana_gain} |r→ |W{max_mana}|n  "
            f"|gMax MV: |w{max_mv - 5} |r→ |W{max_mv}|n\n"
            f"|cNew Spells: |w{spell_names}|n\n"
            f"|mNext Level: |w{xp_to_level(new_level)} XP needed|n\n"
            f"|y|h{'=' * 55}|n"
        )
        self.msg(message)

        return True

    def _grant_spells_for_level(self, level):
        """
        Grant all spells that become available at exactly this level,
        respecting race/class gating.
        Returns a list of spell names that were newly learned.
        """
        from world.spells import SPELLS
        from world.race_class_matrix import can_learn_spell

        learned = self.attributes.get("learned_spells", default=[])
        if not isinstance(learned, list):
            learned = []

        new_spells = []
        for spell_key, spell_data in SPELLS.items():
            if spell_data["level"] == level:
                spell_name = spell_data["name"]
                if spell_name not in learned:
                    allowed, _ = can_learn_spell(self, spell_key)
                    if allowed:
                        learned.append(spell_name)
                        new_spells.append(spell_name)

        # Sort to keep things consistent
        learned.sort()
        self.attributes.add("learned_spells", learned)

        return new_spells