-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012pc = the 2012 client + PC 2025 import (report 36) by research/tools/lsb_textids_2007.py (1 changed, 6 not in the 2007 dialog DAT 6548 and left unchanged).
-----------------------------------
-- Area: Valley_of_Sorrows
-----------------------------------
zones = zones or {}

zones[xi.zone.VALLEY_OF_SORROWS] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        FULL_INVENTORY_AFTER_TRADE    = 6377,  -- You cannot obtain the <item>. Try trading again after sorting your inventory.
        ITEM_OBTAINED                 = 6378,  -- Obtained: <item>.
        GIL_OBTAINED                  = 6380,  -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398,  -- Obtained key item: <keyitem>.
        ITEMS_OBTAINED                = 6387,  -- You obtain <number> <item>!
        NOTHING_OUT_OF_ORDINARY       = 6392,  -- There is nothing out of the ordinary here.
        AURA_THREATENS                = 6396,  -- An aura of irrepressible might threatens to overwhelm you...
        FELLOW_MESSAGE_OFFSET         = 6406,  -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7006,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028,  -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                 = 6994,  -- Tallying conquest results...
        SOMETHING_BURRIED             = 7153,  -- It looks like something was buried here.
        PLAYER_OBTAINS_ITEM           = 7343,  -- <name> obtains <item>!
        UNABLE_TO_OBTAIN_ITEM         = 7344,  -- You were unable to obtain the item.
        PLAYER_OBTAINS_TEMP_ITEM      = 7345,  -- <name> obtains the temporary item: <item>!
        ALREADY_POSSESS_TEMP          = 7346,  -- You already possess that temporary item.
        NO_COMBINATION                = 7351,  -- You were unable to enter a combination.
        UNITY_WANTED_BATTLE_INTERACT  = 10624, -- Those who have accepted % must pay # Unity accolades to participate. The content for this Wanted battle is #. [Ready to begin?/You do not have the appropriate object set, so your rewards will be limited.]
        REGIME_REGISTERED             = 9507,  -- New training regime registered!
        COMMON_SENSE_SURVIVAL         = 10828, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
        ADAMANTOISE   = GetFirstID('Adamantoise'),
        ASPIDOCHELONE = GetFirstID('Aspidochelone'),
    },
    npc =
    {
        ADAMANTOISE_QM = GetFirstID('qm_adamantoise'),
    },
}

return zones[xi.zone.VALLEY_OF_SORROWS]
