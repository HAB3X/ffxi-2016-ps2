-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (17 changed, 11 not in the 2007 dialog DAT 6617 and left unchanged).
-----------------------------------
-- Area: Crawlers_Nest
-----------------------------------
zones = zones or {}

zones[xi.zone.CRAWLERS_NEST] =
{
    text =
    {
        CONQUEST_BASE                 = 0,     -- Tallying conquest results...
        REGION_POINTS_SANDORIA        = 65,    -- San d'Oria's region points have increased!
        DEVICE_NOT_WORKING            = 173,   -- The device is not working.
        SYS_OVERLOAD                  = 182,   -- Warning! Sys...verload! Enterin...fety mode. ID eras...d.
        YOU_LOST_THE                  = 187,   -- You lost the <item>.
        ITEM_CANNOT_BE_OBTAINED       = 6565,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6568,  -- Obtained: <item>.
        GIL_OBTAINED                  = 6569,  -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6588,  -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6582,  -- There is nothing out of the ordinary here.
        SENSE_OF_FOREBODING           = 6583,  -- You are suddenly overcome with a sense of foreboding...
        FELLOW_MESSAGE_OFFSET         = 6596,  -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7196,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7197,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7198,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        GEOMAGNETRON_ATTUNED          = 7207,  -- Your <keyitem> has been attuned to a geomagnetic fount in the corresponding locale.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7218,  -- Your party is unable to participate because certain members' levels are restricted.
        CHEST_UNLOCKED                = 7196,  -- You unlock the chest!
        SOMEONE_HAS_BEEN_DIGGING_HERE = 7204,  -- Someone has been digging here.
        EQUIPMENT_NOT_PURIFIED        = 7205,  -- Your equipment has not been completely purified.
        YOU_BURY_THE                  = 7287,  -- You bury the <item> and <item>.
        NOTHING_WILL_HAPPEN_YET       = 7210,  -- It seems that nothing will happen yet.
        NOTHING_SEEMS_TO_HAPPEN       = 7211,  -- Nothing seems to happen.
        COMBINE_INTO_A_CLUMP          = 7361,  -- You combine the % you have accumulated into a single clump.
        PLAYER_OBTAINS_ITEM           = 7286,  -- <name> obtains <item>!
        UNABLE_TO_OBTAIN_ITEM         = 7287,  -- You were unable to obtain the item.
        PLAYER_OBTAINS_TEMP_ITEM      = 7288,  -- <name> obtains the temporary item: <item>!
        ALREADY_POSSESS_TEMP          = 7289,  -- You already possess that temporary item.
        NO_COMBINATION                = 7294,  -- You were unable to enter a combination.
        REGIME_REGISTERED             = 9372,  -- New training regime registered!
        LEARNS_SPELL                  = 11370, -- <name> learns <spell>!
        UNCANNY_SENSATION             = 11372, -- You are assaulted by an uncanny sensation.
        COMMON_SENSE_SURVIVAL         = 11404, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
        DEMONIC_TIPHIA      = GetFirstID('Demonic_Tiphia'),
        AWD_GOGGIE          = GetFirstID('Awd_Goggie'),
        DYNAST_BEETLE       = GetFirstID('Dynast_Beetle'),
        DREADBUG            = GetFirstID('Dreadbug'),
        MIMIC               = GetFirstID('Mimic'),
        APPARATUS_ELEMENTAL = GetTableOfIDs('Water_Elemental')[9], -- 9th Water Elemental
    },
    npc =
    {
        TREASURE_CHEST  = GetFirstID('Treasure_Chest'),
        TREASURE_COFFER = GetFirstID('Treasure_Coffer'),
    },
}

return zones[xi.zone.CRAWLERS_NEST]
