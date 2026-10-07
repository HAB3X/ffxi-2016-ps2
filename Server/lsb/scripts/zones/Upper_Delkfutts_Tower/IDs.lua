-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (15 changed, 8 not in the 2007 dialog DAT 6578 and left unchanged).
-----------------------------------
-- Area: Upper_Delkfutts_Tower
-----------------------------------
zones = zones or {}

zones[xi.zone.UPPER_DELKFUTTS_TOWER] =
{
    text =
    {
        THIS_ELEVATOR_GOES_DOWN       = 25,    -- This elevator goes down, but it is locked. Perhaps a key is needed to activate it.
        ITEM_CANNOT_BE_OBTAINED       = 6410,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6413,  -- Obtained: <item>.
        GIL_OBTAINED                  = 6414,  -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6433,  -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6427,  -- There is nothing out of the ordinary here.
        FELLOW_MESSAGE_OFFSET         = 6441,  -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7041,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7042,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7043,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7063,  -- Your party is unable to participate because certain members' levels are restricted.
        FISHING_MESSAGE_OFFSET        = 7029,  -- You can't fish here.
        CONQUEST_BASE                 = 7121,  -- Tallying conquest results...
        REGION_POINTS_SANDORIA        = 7186,  -- San d'Oria's region points have increased!
        CHEST_UNLOCKED                = 7287,  -- You unlock the chest!
        PLAYER_OBTAINS_ITEM           = 7310,  -- <name> obtains <item>!
        UNABLE_TO_OBTAIN_ITEM         = 7311,  -- You were unable to obtain the item.
        PLAYER_OBTAINS_TEMP_ITEM      = 7312,  -- <name> obtains the temporary item: <item>!
        ALREADY_POSSESS_TEMP          = 7313,  -- You already possess that temporary item.
        NO_COMBINATION                = 7318,  -- You were unable to enter a combination.
        REGIME_REGISTERED             = 9396,  -- New training regime registered!
        LEARNS_SPELL                  = 10533, -- <name> learns <spell>!
        UNCANNY_SENSATION             = 10535, -- You are assaulted by an uncanny sensation.
        HOMEPOINT_SET                 = 10544, -- Home point set!
    },
    mob =
    {
        ALKYONEUS = GetFirstID('Alkyoneus'),
        ENKELADOS = GetTableOfIDs('Enkelados'),
        IXTAB     = GetTableOfIDs('Ixtab'),
        PALLAS    = GetFirstID('Pallas'),
    },
    npc =
    {
        QM_DELKFUTT_KEY = GetFirstID('qm_delkfutts_key'),
        TREASURE_CHEST  = GetFirstID('Treasure_Chest'),
    },
}

return zones[xi.zone.UPPER_DELKFUTTS_TOWER]
