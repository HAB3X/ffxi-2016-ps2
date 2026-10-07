-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (15 changed, 8 not in the 2007 dialog DAT 6431 and left unchanged).
-----------------------------------
-- Area: Oldton_Movalpolos
-----------------------------------
zones = zones or {}

zones[xi.zone.OLDTON_MOVALPOLOS] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398, -- Obtained key item: <keyitem>.
        KEYITEM_LOST                  = 6399, -- Lost key item: <keyitem>.
        FELLOW_MESSAGE_OFFSET         = 6406, -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                 = 6994, -- Tallying conquest results...
        CONQUEST                      = 7162, -- You've earned conquest points!
        FISHING_MESSAGE_OFFSET        = 7513, -- You can't fish here.
        MINING_IS_POSSIBLE_HERE       = 7636, -- Mining is possible here if you have <item>.
        NO_FIRES_NO_BOMBS             = 7643, -- This place being for garbage. No fires. No bombs.
        KILLING_BOMBS                 = 7648, -- Killing bombs. Bringing <item>.
        REFUSES_TO_GIVE_ANOTHER       = 7656, -- When Brakobrik realizes that you already possess the item he is trying to give you, he refuses to give you another one.
        RAKOROK_DIALOGUE              = 7660, -- Nsy pipul. Gattohre! I bisynw!
        ALTANA_DIE                    = 7662, -- Aaaltaaanaaa... Diiieee!!!
        WAS_TAKEN_FROM_YOU            = 7762, -- The <keyitem> was taken from you...
        MONSTER_APPEARED              = 7675, -- A monster has appeared!
        CHEST_UNLOCKED                = 7683, -- You unlock the chest!
        COMMON_SENSE_SURVIVAL         = 8130, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
        BUGALLUG           = GetFirstID('Bugallug'),
        BUGBEAR_BONDMAN    = GetTableOfIDs('Bugbear_Bondman'),
        BUGBEAR_SERVINGMAN = GetTableOfIDs('Bugbear_Servingman'),
        BUGBEAR_STRONGMAN  = GetTableOfIDs('Bugbear_Strongman'),
        GOBLIN_FREELANCE   = GetTableOfIDs('Goblin_Freelance'),
        GOBLIN_WOLFMAN     = GetFirstID('Goblin_Wolfman'),
        GOBLIN_HAMMERMAN   = GetTableOfIDs('Goblin_Hammerman'),
        MOBLIN_CHAPMAN     = GetTableOfIDs('Moblin_Chapman'),
        MOBLIN_COALMAN     = GetTableOfIDs('Moblin_Coalman'),
        MOBLIN_GASMAN      = GetTableOfIDs('Moblin_Gasman'),
        MOBLIN_PIKEMAN     = GetTableOfIDs('Moblin_Pikeman'),
    },
    npc =
    {
        SCRAWLED_WRITING = GetFirstID('Scrawled_Writing'),
        OVERSEER_BASE    = GetFirstID('Conquest_Banner'),
        TREASURE_CHEST   = GetFirstID('Treasure_Chest'),
        MINING           = GetTableOfIDs('Mining_Point'),
    },
}

return zones[xi.zone.OLDTON_MOVALPOLOS]
