-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012pc = the 2012 client + PC 2025 import (report 36) by research/tools/lsb_textids_2007.py (1 changed, 6 not in the 2007 dialog DAT 6425 and left unchanged).
-----------------------------------
-- Area: Uleguerand_Range
-----------------------------------
zones = zones or {}

zones[xi.zone.ULEGUERAND_RANGE] =
{
    text =
    {
        NOTHING_HAPPENS               = 119,  -- Nothing happens...
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6411, -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6392, -- There is nothing out of the ordinary here.
        FELLOW_MESSAGE_OFFSET         = 6406, -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7019, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7020, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7021, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7041, -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                 = 6994, -- Tallying conquest results...
        SOMETHING_GLITTERING          = 7165, -- You see something glittering beneath the surface of the ice.
        WHAT_LIES_BENEATH             = 7166, -- There are many cold <item> scattered around the area. Could someone be trying to melt the ice to retrieve what lies beneath?
        SOMETHING_GLITTERING_BUT      = 7167, -- You see something glittering below the surface here, but the ice encases it completely.
        GEUSH_COUNTER                 = 7220, -- Geush Urvan uses Counterstance!
        FRESH_RABBIT_TRACKS           = 7222, -- There are fresh rabbit tracks here. The creature must still be in the vicinity.
        HOMEPOINT_SET                 = 8352, -- Home point set!
        UNITY_WANTED_BATTLE_INTERACT  = 8163, -- Those who have accepted % must pay # Unity accolades to participate. The content for this Wanted battle is #. [Ready to begin?/You do not have the appropriate object set, so your rewards will be limited.]
    },
    mob =
    {
        BLACK_CONEY  = GetFirstID('Black_Coney'),
        BONNACON     = GetFirstID('Bonnacon'),
        FATHER_FROST = GetFirstID('Father_Frost'),
        GEUSH_URVAN  = GetFirstID('Geush_Urvan'),
        JORMUNGAND   = GetFirstID('Jormungand'),
        MAGNOTAUR    = GetFirstID('Magnotaur'),
        SKVADER      = GetFirstID('Skvader'),
        SNOW_MAIDEN  = GetFirstID('Snow_Maiden'),
        WHITE_CONEY  = GetFirstID('White_Coney'),
    },
    npc =
    {
        RABBIT_FOOTPRINT = GetFirstID('Rabbit_Footprint'),
        WATERFALL        = GetFirstID('_058'),
    },
}

return zones[xi.zone.ULEGUERAND_RANGE]
