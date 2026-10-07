-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (5 changed, 6 not in the 2007 dialog DAT 6561 and left unchanged).
-----------------------------------
-- Area: Fort_Ghelsba
-----------------------------------
zones = zones or {}

zones[xi.zone.FORT_GHELSBA] =
{
    text =
    {
        CONQUEST_BASE                 = 0,    -- Tallying conquest results...
        ITEM_CANNOT_BE_OBTAINED       = 6534, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6537, -- Obtained: <item>.
        GIL_OBTAINED                  = 6538, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6557, -- Obtained key item: <keyitem>.
        FELLOW_MESSAGE_OFFSET         = 6565, -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7165, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7166, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7167, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7187, -- Your party is unable to participate because certain members' levels are restricted.
        CHEST_UNLOCKED                = 7291, -- You unlock the chest!
        COMMON_SENSE_SURVIVAL         = 7388, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
        HUNDREDSCAR_HAJWAJ = GetFirstID('Hundredscar_Hajwaj'),
        ORCISH_PANZER      = GetFirstID('Orcish_Panzer'),
    },
    npc =
    {
        TREASURE_CHEST = GetFirstID('Treasure_Chest'),
    },
}

return zones[xi.zone.FORT_GHELSBA]
