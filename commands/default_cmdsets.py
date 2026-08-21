"""
CommandSets for 'rop'
"""

from evennia import default_cmds
from commands.spells import CmdCast, CmdSpells, CmdRead, CmdInscribe
from commands.movement import CmdMove, CmdRun, CmdLookDir
from commands.doors import CmdOpen, CmdClose, CmdLock, CmdUnlock
from commands.general import CmdLookSelf, CmdRest, CmdRent, CmdMeditate, CmdConsider, CmdRecall, CmdPrompt, CmdWho, CmdRules, CmdWarpoints, CmdStats, CmdBrief, CmdVerbose, CmdExits, CmdExamine, CmdScan, CmdSleep, CmdWake, CmdStamina, CmdRevive
from commands.gossip import CmdGossip
from commands.quest import CmdQuest
from commands.clan import CmdClan, CmdClanJoin, CmdClanList, CmdClanLeave, CmdClanTalk
from commands.broadcast import CmdBc
from commands.backup import CmdBackup
from commands.pvp import CmdPvp
from commands.group import CmdGroup, CmdGroupInvite, CmdGroupAccept, CmdGroupLeave, CmdGroupKick, CmdGroupTalk
from commands.bank import CmdDeposit, CmdWithdraw, CmdBalance
from commands.loot import CmdSacrifice, CmdLoot, CmdAutoLoot, CmdAutoSac
from commands.weather import CmdWeather
from commands.drop import CmdDropCoins, CmdTakeCoins, CmdGive, CmdPut, CmdGet, CmdGiveGold
from commands.combat_commands import CmdKill, CmdFlee, CmdStop, CmdCombatBrief
from commands.ranged_commands import CmdShoot, CmdReload, CmdThrow
from commands.equipment import CmdWear, CmdRemove, CmdEquipment, CmdInventory, CmdEquipmentVerify
from world.combat_skills import CmdKick, CmdBash, CmdBackstab, CmdDisarm, CmdHide, CmdUnhide
from world.shopkeeper import CmdBuy, CmdSell, CmdShopList, CmdAppraise
from world.repair_npc import CmdRepair
from world.enchanter import CmdEnchant
from world.auction_house import CmdAuction
from world.guildmaster import CmdTrain, CmdLearn, CmdPractice
from world.reputation import CmdReputation, CmdRepVendor
from world.skill_tree import CmdTalents, CmdTalentBuy, CmdTalentReset
from commands.admin import CmdReload, CmdGoto, CmdSpawn, CmdSet
from commands.mob_admin import CmdTestMobs, CmdSpawnMob, CmdSpawnStats
from commands.realm_admin import CmdSanitizeRooms, CmdVerifyRealm, CmdPopulateRealm
from commands.verify_systems import CmdVerifyAllSystems
from commands.moderation import CmdBan, CmdUnban, CmdMute, CmdUnmute, CmdBanList, CmdKick
from commands.admin_tools import CmdAuditLog, CmdPerfMon
from commands.social import CmdFriend, CmdFriendAdd, CmdFriendRemove, CmdFriendList, CmdIgnore, CmdIgnoreAdd, CmdIgnoreRemove, CmdIgnoreList
from commands.mail import CmdMail, CmdMailSend, CmdMailRead, CmdMailList, CmdMailDelete, CmdMailReply
from commands.housing import CmdHouse, CmdHouseBuy, CmdHouseHome, CmdHouseInvite, CmdHouseUninvite, CmdHouseList, CmdHouseDesc, CmdHouseName, CmdHouseLock, CmdHouseUnlock, CmdHouseVisit
from commands.leaderboard import CmdLeaderboard
from commands.roleplay import CmdEmote, CmdRpDesc, CmdRpInfo, CmdRpStatus
from commands.talk import CmdTalk
from commands.horizontal_systems import (
    CmdGather, CmdCraft, CmdRecipes, CmdTradeskills,
    CmdMounts,
    CmdEat, CmdDrink, CmdFood, CmdDrinks, CmdHunger,
    CmdTime,
    CmdAchievements, CmdTitle,
)
from commands.pvp_commands import CmdArenaQueue, CmdBattleground, CmdDuel, CmdBounty
from commands.raid_commands import CmdRaid, CmdDungeonFinder, CmdWorldEvent, CmdPet
from commands.rogue_commands import (
    CmdPickLock, CmdCraftPoison, CmdApplyPoison,
    CmdListPoisons, CmdListRecipes, CmdLearnPoison, CmdLockpickTool,
)
from commands.druid_commands import CmdShift, CmdRevert, CmdForms
from commands.necromancer_commands import (
    CmdRaiseMinion, CmdDismiss, CmdDismissAll, CmdMinions,
)
from commands.monk_commands import (
    CmdKi, CmdFlurry, CmdStunningStrike, CmdChiHeal,
    CmdTigerPalm, CmdDragonKick, CmdSerenity, CmdMeditateMonk,
)
from commands.unloggedin import CmdUnloggedinLook, CmdUnloggedinHelp


class CharacterCmdSet(default_cmds.CharacterCmdSet):
    """
    Command set for logged-in characters.

    Adds:
      - run / dash / sprint  -- run through rooms in one direction
      - look self / look me  -- examine self with stats & equipment
      - who / w / players    -- list online players with clan tags
      - clan / join / clan talk -- full clan system
      - Standard aliases via Evennia's default commands
        (look->l, inventory->i, equipment->eq)
    """
    key = "DefaultCharacter"
    priority = 102

    def at_cmdset_creation(self):
        super().at_cmdset_creation()
        # Magic
        self.add(CmdCast())
        self.add(CmdSpells())
        self.add(CmdRead())
        self.add(CmdInscribe())
        # Movement
        self.add(CmdMove())
        self.add(CmdRun())
        self.add(CmdLookDir())
        # Doors (Phase 1.2)
        self.add(CmdOpen())
        self.add(CmdClose())
        self.add(CmdLock())
        self.add(CmdUnlock())
        # General / Self-inspection
        self.add(CmdLookSelf())
        # Recovery & Utility
        self.add(CmdRest())
        self.add(CmdRent())
        self.add(CmdMeditate())
        self.add(CmdSleep())
        self.add(CmdWake())
        self.add(CmdStamina())
        self.add(CmdRevive())
        self.add(CmdConsider())
        self.add(CmdRecall())
        # Communication
        self.add(CmdGossip())
        # Quests
        self.add(CmdQuest())
        # Prompt toggle
        self.add(CmdPrompt())
        # Brief / Verbose mode (Phase 1.2)
        self.add(CmdBrief())
        self.add(CmdVerbose())
        # Exits / Examine / Scan (Phase 1.3-1.4)
        self.add(CmdExits())
        self.add(CmdExamine())
        self.add(CmdScan())
        # Who list
        self.add(CmdWho())
        # Rules command
        self.add(CmdRules())
        # Warpoints leaderboard
        self.add(CmdWarpoints())
        # Realm statistics
        self.add(CmdStats())
        # Clan System
        self.add(CmdClan())
        self.add(CmdClanJoin())
        self.add(CmdClanList())
        self.add(CmdClanLeave())
        self.add(CmdClanTalk())
        # Broadcast Channels
        self.add(CmdBc())
        # Admin
        self.add(CmdBackup())
        # PvP Toggle
        self.add(CmdPvp())
        # Group System
        self.add(CmdGroup())
        self.add(CmdGroupInvite())
        self.add(CmdGroupAccept())
        self.add(CmdGroupLeave())
        self.add(CmdGroupKick())
        self.add(CmdGroupTalk())
        # Banking System
        self.add(CmdDeposit())
        self.add(CmdWithdraw())
        self.add(CmdBalance())
        # Looting & Sacrifice System
        self.add(CmdSacrifice())
        self.add(CmdLoot())
        self.add(CmdAutoLoot())
        self.add(CmdAutoSac())
        # Weather
        self.add(CmdWeather())
        # Currency Drop / Take
        self.add(CmdDropCoins())
        self.add(CmdTakeCoins())
        # Give / Put / Get / GiveGold
        self.add(CmdGive())
        self.add(CmdPut())
        self.add(CmdGet())
        self.add(CmdGiveGold())
        # Equipment (wear / remove / equipment / inventory)
        self.add(CmdWear())
        self.add(CmdRemove())
        self.add(CmdEquipment())
        self.add(CmdInventory())
        # Admin: equipment slot audit
        self.add(CmdEquipmentVerify())
        # Combat
        self.add(CmdKill())
        self.add(CmdFlee())
        self.add(CmdStop())
        self.add(CmdCombatBrief())
        # Ranged Combat
        self.add(CmdShoot())
        self.add(CmdReload())
        self.add(CmdThrow())
        # Combat Skills
        self.add(CmdKick())
        self.add(CmdBash())
        self.add(CmdBackstab())
        self.add(CmdDisarm())
        self.add(CmdHide())
        self.add(CmdUnhide())
        # Commerce
        self.add(CmdBuy())
        self.add(CmdSell())
        self.add(CmdShopList())
        self.add(CmdAppraise())
        self.add(CmdRepair())
        self.add(CmdEnchant())
        # Auction House / Trading Post
        self.add(CmdAuction())
        # Training
        self.add(CmdTrain())
        self.add(CmdLearn())
        self.add(CmdPractice())
        # Reputation (Phase 14)
        self.add(CmdReputation())
        self.add(CmdRepVendor())
        # Talent Tree (Phase 14 Sprint 1)
        self.add(CmdTalents())
        self.add(CmdTalentBuy())
        self.add(CmdTalentReset())
        # Admin / Builder (Phase 6.10)
        self.add(CmdReload())
        self.add(CmdGoto())
        self.add(CmdSpawn())
        self.add(CmdSet())
        # Mob Admin / Diagnostics
        self.add(CmdTestMobs())
        self.add(CmdSpawnMob())
        self.add(CmdSpawnStats())
        # Realm Administration
        self.add(CmdSanitizeRooms())
        self.add(CmdVerifyRealm())
        self.add(CmdPopulateRealm())
        # System Verification
        self.add(CmdVerifyAllSystems())
        # Moderation (Phase 10)
        self.add(CmdBan())
        self.add(CmdUnban())
        self.add(CmdMute())
        self.add(CmdUnmute())
        self.add(CmdBanList())
        self.add(CmdKick())
        # Admin Tools (Phase 10)
        self.add(CmdAuditLog())
        self.add(CmdPerfMon())
        # Social & Multiplayer (Phase 8)
        self.add(CmdFriend())
        self.add(CmdFriendAdd())
        self.add(CmdFriendRemove())
        self.add(CmdFriendList())
        self.add(CmdIgnore())
        self.add(CmdIgnoreAdd())
        self.add(CmdIgnoreRemove())
        self.add(CmdIgnoreList())
        # Mail System (Phase 8)
        self.add(CmdMail())
        self.add(CmdMailSend())
        self.add(CmdMailRead())
        self.add(CmdMailList())
        self.add(CmdMailDelete())
        self.add(CmdMailReply())
        # Player Housing (Phase 8)
        self.add(CmdHouse())
        self.add(CmdHouseBuy())
        self.add(CmdHouseHome())
        self.add(CmdHouseInvite())
        self.add(CmdHouseUninvite())
        self.add(CmdHouseList())
        self.add(CmdHouseDesc())
        self.add(CmdHouseName())
        self.add(CmdHouseLock())
        self.add(CmdHouseUnlock())
        self.add(CmdHouseVisit())
        # Leaderboards (Phase 8)
        self.add(CmdLeaderboard())
        # Roleplay Support (Phase 8)
        self.add(CmdEmote())
        self.add(CmdRpDesc())
        self.add(CmdRpInfo())
        self.add(CmdRpStatus())
        # NPC Dialogue / Talk (Phase 9)
        self.add(CmdTalk())
        # Tradeskills / Crafting / Gathering (Phase 3.1)
        self.add(CmdGather())
        self.add(CmdCraft())
        self.add(CmdRecipes())
        self.add(CmdTradeskills())
        # Mounts & Riding (Phase 3.1)
        self.add(CmdMounts())
        # Hunger / Thirst / Survival (Phase 3.1)
        self.add(CmdEat())
        self.add(CmdDrink())
        self.add(CmdFood())
        self.add(CmdDrinks())
        self.add(CmdHunger())
        # Day / Night Cycle (Phase 3.1)
        self.add(CmdTime())
        # Achievements & Titles (Phase 3.1)
        self.add(CmdAchievements())
        self.add(CmdTitle())
        # PvP Systems (Phase 3.2)
        self.add(CmdArenaQueue())
        self.add(CmdBattleground())
        self.add(CmdDuel())
        self.add(CmdBounty())
        # Raid & Dungeon Systems (Phase 3.3)
        self.add(CmdRaid())
        self.add(CmdDungeonFinder())
        self.add(CmdWorldEvent())
        self.add(CmdPet())
        # Rogue Class Mechanics (Phase 2.2)
        self.add(CmdPickLock())
        self.add(CmdCraftPoison())
        self.add(CmdApplyPoison())
        self.add(CmdListPoisons())
        self.add(CmdListRecipes())
        self.add(CmdLearnPoison())
        self.add(CmdLockpickTool())
        # Druid Class Mechanics (Phase 2.2)
        self.add(CmdShift())
        self.add(CmdRevert())
        self.add(CmdForms())
        # Necromancer Class Mechanics (Phase 2.2)
        self.add(CmdRaiseMinion())
        self.add(CmdDismiss())
        self.add(CmdDismissAll())
        self.add(CmdMinions())
        # Monk Class Mechanics (Phase 2.2)
        self.add(CmdKi())
        self.add(CmdFlurry())
        self.add(CmdStunningStrike())
        self.add(CmdChiHeal())
        self.add(CmdTigerPalm())
        self.add(CmdDragonKick())
        self.add(CmdSerenity())
        self.add(CmdMeditateMonk())


class AccountCmdSet(default_cmds.AccountCmdSet):
    """
    Command set for out-of-character account control.
    """
    key = "DefaultAccount"

    def at_cmdset_creation(self):
        super().at_cmdset_creation()


class UnloggedinCmdSet(default_cmds.UnloggedinCmdSet):
    """
    Command set available at the login screen.

    Adds custom look/help commands so external clients (telnet, web)
    see proper guidance before authentication.
    """
    key = "DefaultUnloggedin"

    def at_cmdset_creation(self):
        super().at_cmdset_creation()
        self.add(CmdUnloggedinLook())
        self.add(CmdUnloggedinHelp())
