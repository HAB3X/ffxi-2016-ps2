-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (15 changed, 7 not in the 2007 dialog DAT 6586 and left unchanged).
-----------------------------------
-- Area: Ranguemont Pass (166)
-----------------------------------
zones = zones or {}

zones[xi.zone.RANGUEMONT_PASS] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378,  -- Obtained: <item>.
        GIL_OBTAINED                  = 6379,  -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398,  -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6392,  -- There is nothing out of the ordinary here.
        SENSE_OF_FOREBODING           = 6393,  -- You are suddenly overcome with a sense of foreboding...
        FELLOW_MESSAGE_OFFSET         = 6406,  -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7006,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        GEOMAGNETRON_ATTUNED          = 7017,  -- Your <keyitem> has been attuned to a geomagnetic fount in the corresponding locale.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028,  -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                 = 6994,  -- Tallying conquest results...
        FISHING_MESSAGE_OFFSET        = 7153,  -- You can't fish here.
        WATERS_OF_OBLIVION            = 7286,  -- You behold the Waters of Oblivion.
        REGIME_REGISTERED             = 9454,  -- New training regime registered!
        PLAYER_OBTAINS_ITEM           = 10506, -- <name> obtains <item>!
        UNABLE_TO_OBTAIN_ITEM         = 10507, -- You were unable to obtain the item.
        PLAYER_OBTAINS_TEMP_ITEM      = 10508, -- <name> obtains the temporary item: <item>!
        ALREADY_POSSESS_TEMP          = 10509, -- You already possess that temporary item.
        NO_COMBINATION                = 10514, -- You were unable to enter a combination.
        COMMON_SENSE_SURVIVAL         = 10694, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
        GLOOM_EYE    = GetFirstID('Gloom_Eye'),
        HYAKUME      = GetFirstID('Hyakume'),
        TAISAIJIN    = GetFirstID('Taisaijin'),
        TROS         = GetFirstID('Tros'),
    },
    npc =
    {
    },
}

return zones[xi.zone.RANGUEMONT_PASS]
