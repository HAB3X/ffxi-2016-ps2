-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012pc = the 2012 client + PC 2025 import (report 36) by research/tools/lsb_textids_2007.py (3 changed, 6 not in the 2007 dialog DAT 84291 and left unchanged).
-----------------------------------
-- Area: RaKaznar_Inner_Court
-----------------------------------
zones = zones or {}

zones[xi.zone.RAKAZNAR_INNER_COURT] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398, -- Obtained key item: <keyitem>.
        CARRIED_OVER_POINTS           = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        HOMEPOINT_SET                 = 7707, -- Home point set!
    },
    mob =
    {
        REIVE_MOB_OFFSET = GetFirstID('Heliotrope_Barrier'),
    },
    npc =
    {
        REIVE_COLLISION_OFFSET = GetFirstID('_7o0'),
    },
}

return zones[xi.zone.RAKAZNAR_INNER_COURT]
