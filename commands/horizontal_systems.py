"""
Commands for Horizontal Systems (Phase 3.1)
============================================
Tradeskills, Mounts, Survival, Day/Night, Achievements
"""

from commands.command import Command


# ============================================================================
# Tradeskills / Crafting / Gathering
# ============================================================================

class CmdGather(Command):
    """
    Gather raw materials from the environment.

    Usage:
      gather <skill>
      mine
      forage
      fish
      harvest

    Valid skills: mining, foraging, fishing, harvesting.
    The room's biome determines what materials are available.
    Higher skill levels yield rarer materials.
    """

    key = "gather"
    aliases = ["mine", "forage", "fish", "harvest"]
    help_category = "Tradeskills"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        cmd = self.cmdstring.lower()

        # Map aliases to skill keys
        alias_map = {
            "mine": "mining",
            "forage": "foraging",
            "fish": "fishing",
            "harvest": "harvesting",
        }

        if cmd == "gather":
            args = self.args.strip().lower()
            if not args:
                caller.msg("Usage: gather <mining|foraging|fishing|harvesting>")
                return
            skill_key = args
        else:
            skill_key = alias_map.get(cmd, cmd)

        from world.tradeskills import gather
        ok, msg = gather(caller, skill_key)
        caller.msg(msg)


class CmdCraft(Command):
    """
    Craft an item from gathered materials.

    Usage:
      craft <skill> <recipe>
      smith <recipe>
      brew <recipe>
      tailor <recipe>
      enchant <recipe>

    Valid skills: blacksmithing, alchemy, tailoring, enchanting.
    Use 'recipes <skill>' to see available recipes.
    """

    key = "craft"
    aliases = ["smith", "brew", "tailor"]
    help_category = "Tradeskills"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        cmd = self.cmdstring.lower()

        alias_map = {
            "smith": "blacksmithing",
            "brew": "alchemy",
            "tailor": "tailoring",
        }

        if cmd == "craft":
            parts = self.args.strip().split(None, 1)
            if len(parts) < 2:
                caller.msg("Usage: craft <skill> <recipe>")
                caller.msg("Skills: blacksmithing, alchemy, tailoring, enchanting")
                return
            skill_key = parts[0].lower()
            recipe_key = parts[1].lower()
        else:
            skill_key = alias_map.get(cmd, cmd)
            recipe_key = self.args.strip().lower()
            if not recipe_key:
                caller.msg(f"Usage: {cmd} <recipe>")
                return

        from world.tradeskills import craft
        ok, msg = craft(caller, skill_key, recipe_key)
        caller.msg(msg)


class CmdRecipes(Command):
    """
    List available crafting recipes.

    Usage:
      recipes <skill>
      recipes blacksmithing
      recipes alchemy
      recipes tailoring
      recipes enchanting
    """

    key = "recipes"
    help_category = "Tradeskills"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        skill_key = self.args.strip().lower()

        if not skill_key:
            caller.msg("Usage: recipes <blacksmithing|alchemy|tailoring|enchanting>")
            return

        from world.tradeskills import list_recipes, TRADESKILLS
        skill_def = TRADESKILLS.get(skill_key)
        if not skill_def or "craft_verb" not in skill_def:
            caller.msg(f"Unknown crafting skill: {skill_key}")
            return

        recipes = list_recipes(skill_key)
        if not recipes:
            caller.msg(f"No recipes found for {skill_def['name']}.")
            return

        out = [f"|Y{skill_def['name']} Recipes:|n"]
        for r in recipes:
            mats = ", ".join(f"{v}x {k.replace('_', ' ')}" for k, v in r["materials"].items())
            out.append(f"  |W{r['name']}|n (req: lvl {r['skill_req']}) - {mats} - {r['xp']} XP")
        caller.msg("\n".join(out))


class CmdTradeskills(Command):
    """
    View your tradeskill levels and progress.

    Usage:
      tradeskills
      skills
    """

    key = "tradeskills"
    aliases = ["skills"]
    help_category = "Tradeskills"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        from world.tradeskills import list_skills, get_materials

        skills = list_skills(caller)
        out = ["|Y=== Tradeskills ===|n"]
        for s in skills:
            pct = int(s["xp"] / max(1, s["xp_needed"]) * 100) if s["xp_needed"] > 0 else 100
            out.append(f"  {s['name']}: Level {s['level']}/{s['max_level']} ({pct}%)")
        out.append("")

        materials = get_materials(caller)
        if materials:
            out.append("|Y=== Materials ===|n")
            for mat, count in sorted(materials.items()):
                out.append(f"  {mat.replace('_', ' ').title()}: {count}")
        else:
            out.append("|wNo materials gathered yet.|n")

        caller.msg("\n".join(out))


# ============================================================================
# Mounts & Riding
# ============================================================================

class CmdMounts(Command):
    """
    View available mounts and your mount status.

    Usage:
      mounts list     - See all available mounts
      mounts buy <id> - Purchase a mount
      mounts info     - View your mount's stats
      mounts up       - Mount your steed
      mounts down     - Dismount
      mounts rest     - Rest your mount (restores HP)
      mounts feed     - Feed your mount (uses food, grants XP)
    """

    key = "mounts"
    aliases = ["mount"]
    help_category = "Mounts"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        if not args or args == "info":
            from world.mounts import get_mount_info
            info = get_mount_info(caller)
            if not info:
                caller.msg("You don't own a mount. Use 'mounts list' to see available mounts.")
                return
            status = "|gMounted|n" if info["mounted"] else "|wDismounted|n"
            out = [
                f"|Y=== Mount: {info['name']} ===|n",
                f"  Status: {status}",
                f"  Bond Level: {info['level']}/50",
                f"  HP: {info['hp']}/{info['max_hp']}",
                f"  Speed Bonus: +{info['speed_bonus_pct']}%",
            ]
            if info["combat_bonus"]:
                out.append("  Combat Bonuses:")
                for k, v in info["combat_bonus"].items():
                    out.append(f"    {k.replace('_', ' ').title()}: +{v}%")
            caller.msg("\n".join(out))
            return

        if args == "list":
            from world.mounts import list_mounts
            mounts = list_mounts()
            out = ["|Y=== Available Mounts ===|n"]
            for m in mounts:
                out.append(f"  |W{m['name']}|n (lvl {m['min_level']}+) - {m['cost']}g - +{m['speed_bonus_pct']}% speed")
                out.append(f"    {m['desc']}")
            caller.msg("\n".join(out))
            return

        if args.startswith("buy "):
            mount_key = args[4:].strip()
            from world.mounts import buy_mount
            ok, msg = buy_mount(caller, mount_key)
            caller.msg(msg)
            return

        if args == "up":
            from world.mounts import mount_up
            ok, msg = mount_up(caller)
            caller.msg(msg)
            return

        if args == "down":
            from world.mounts import dismount
            ok, msg = dismount(caller)
            caller.msg(msg)
            return

        if args == "rest":
            from world.mounts import rest_mount
            ok, msg = rest_mount(caller)
            caller.msg(msg)
            return

        if args == "feed":
            from world.mounts import feed_mount
            ok, msg = feed_mount(caller)
            caller.msg(msg)
            return

        caller.msg("Usage: mounts <list|buy|info|up|down|rest|feed>")


# ============================================================================
# Hunger / Thirst / Survival
# ============================================================================

class CmdEat(Command):
    """
    Eat food to restore hunger.

    Usage:
      eat <food>
      eat bread
      eat rations

    Use 'food' to see available food items.
    """

    key = "eat"
    help_category = "Survival"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        food_key = self.args.strip().lower()

        if not food_key:
            caller.msg("Usage: eat <food>. Use 'food' to see available items.")
            return

        from world.survival import consume_food
        ok, msg = consume_food(caller, food_key)
        caller.msg(msg)


class CmdDrink(Command):
    """
    Drink to restore thirst.

    Usage:
      drink <beverage>
      drink water
      drink ale

    Use 'drinks' to see available beverages.
    """

    key = "drink"
    help_category = "Survival"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        drink_key = self.args.strip().lower()

        if not drink_key:
            caller.msg("Usage: drink <beverage>. Use 'drinks' to see available items.")
            return

        from world.survival import consume_drink
        ok, msg = consume_drink(caller, drink_key)
        caller.msg(msg)


class CmdFood(Command):
    """
    List available food items.

    Usage:
      food
    """

    key = "food"
    help_category = "Survival"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        from world.survival import list_food
        foods = list_food()
        out = ["|Y=== Available Food ===|n"]
        for f in foods:
            out.append(f"  {f['name']} - Hunger +{f['hunger_restore']} - {f['cost']}g ({f['quality']})")
        caller.msg("\n".join(out))


class CmdDrinks(Command):
    """
    List available beverages.

    Usage:
      drinks
    """

    key = "drinks"
    help_category = "Survival"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        from world.survival import list_drinks
        drinks = list_drinks()
        out = ["|Y=== Available Drinks ===|n"]
        for d in drinks:
            out.append(f"  {d['name']} - Thirst +{d['thirst_restore']} - {d['cost']}g ({d['quality']})")
        caller.msg("\n".join(out))


class CmdHunger(Command):
    """
    Check your hunger and thirst status.

    Usage:
      hunger
      thirst
    """

    key = "hunger"
    aliases = ["thirst"]
    help_category = "Survival"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        from world.survival import get_survival_status
        status = get_survival_status(caller)
        out = [
            f"Hunger: {status['hunger_color']}{status['hunger']}/{status['hunger_max']} ({status['hunger_status']})|n",
            f"Thirst: {status['thirst_color']}{status['thirst']}/{status['thirst_max']} ({status['thirst_status']})|n",
        ]
        caller.msg("\n".join(out))


# ============================================================================
# Day / Night Cycle
# ============================================================================

class CmdTime(Command):
    """
    Check the current game time and day phase.

    Usage:
      time
    """

    key = "time"
    help_category = "General"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        from world.daynight import format_time, get_light_description, get_room_light, get_visibility_text

        time_str = format_time()
        if caller.location:
            light_desc = get_light_description(caller.location)
            caller.msg(f"|Y=== Game Time ===|n\n{time_str}\n{light_desc}")
        else:
            caller.msg(f"|Y=== Game Time ===|n\n{time_str}")


# ============================================================================
# Achievements & Titles
# ============================================================================

class CmdAchievements(Command):
    """
    View your achievements.

    Usage:
      achievements            - List all achievements
      achievements <category> - Filter by category
      achievements points     - Show achievement points

    Categories: Combat, Exploration, Crafting, Social, Collection, Challenge
    """

    key = "achievements"
    aliases = ["achieve", "achs"]
    help_category = "Achievements"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        from world.achievements import get_achievement_list, get_achievement_points, CATEGORIES, TIER_COLORS

        if args == "points":
            points = get_achievement_points(caller)
            caller.msg(f"|YAchievement Points: {points}|n")
            return

        achievements = get_achievement_list(caller)

        if args and args in [c.lower() for c in CATEGORIES]:
            category = next(c for c in CATEGORIES if c.lower() == args)
            achievements = [a for a in achievements if a["category"] == category]

        if not achievements:
            caller.msg("No achievements found.")
            return

        out = ["|Y=== Achievements ===|n"]
        current_cat = None
        for a in achievements:
            if a["category"] != current_cat:
                current_cat = a["category"]
                out.append(f"\n|W{current_cat}:|n")
            status = "|G[UNLOCKED]|n" if a["unlocked"] else "|d[LOCKED]|n"
            tier_color = TIER_COLORS.get(a["tier"], "|w")
            out.append(f"  {status} {tier_color}[{a['tier']}] {a['name']}|n - {a['desc']} (+{a['points']} AP)")
            if a["title"]:
                out.append(f"    Title: {a['title']}")

        points = get_achievement_points(caller)
        out.append(f"\n|YTotal Achievement Points: {points}|n")
        caller.msg("\n".join(out))


class CmdTitle(Command):
    """
    Set or view your active title.

    Usage:
      title              - View your current title
      title list         - List all unlocked titles
      title set <title>  - Set your active title
      title clear        - Remove your active title
    """

    key = "title"
    help_category = "Achievements"
    locks = "cmd:all()"
    auto_help = True

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        from world.achievements import get_active_title, get_unlocked_titles, set_active_title, clear_title

        if not args:
            title = get_active_title(caller)
            if title:
                caller.msg(f"Your title: |Y{title}|n")
            else:
                caller.msg("You have no active title. Use 'title list' to see unlocked titles.")
            return

        if args == "list":
            titles = get_unlocked_titles(caller)
            if titles:
                out = ["|Y=== Unlocked Titles ===|n"]
                for t in titles:
                    out.append(f"  {t}")
                caller.msg("\n".join(out))
            else:
                caller.msg("You haven't unlocked any titles yet.")
            return

        if args.startswith("set "):
            title = args[4:].strip()
            ok, msg = set_active_title(caller, title)
            caller.msg(msg)
            return

        if args == "clear":
            ok, msg = clear_title(caller)
            caller.msg(msg)
            return

        caller.msg("Usage: title <list|set <title>|clear>")