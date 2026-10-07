-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (5 changed, 5 not in the 2007 dialog DAT 6551 and left unchanged).
-----------------------------------
-- Area: Mordion_Gaol
-----------------------------------
zones = zones or {}

zones[xi.zone.MORDION_GAOL] =
{
    text =
    {
        CONQUEST_BASE                 = 0,    -- Tallying conquest results...
        ITEM_CANNOT_BE_OBTAINED       = 6534, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6537, -- Obtained: <item>.
        GIL_OBTAINED                  = 6538, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6557, -- Obtained key item: <keyitem>.
        CARRIED_OVER_POINTS           = 7165, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7166, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7167, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7187, -- Your party is unable to participate because certain members' levels are restricted.
        NO_ESCAPE                     = 7153, -- Any attempt at escape is futile!
        PROHIBITED_ACTIVITIES         = 7169, -- Your character has been jailed due to prohibited activities. Your account will soon be suspended due to this violation.
    },
    mob =
    {
    },
    npc =
    {
    },
}

return zones[xi.zone.MORDION_GAOL]
