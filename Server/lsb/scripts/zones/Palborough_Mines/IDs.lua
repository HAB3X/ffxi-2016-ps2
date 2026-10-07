-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (13 changed, 7 not in the 2007 dialog DAT 6563 and left unchanged).
-----------------------------------
-- Area: Palborough Mines (143)
-----------------------------------
zones = zones or {}

zones[xi.zone.PALBOROUGH_MINES] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED            = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                      = 6378, -- Obtained: <item>.
        GIL_OBTAINED                       = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED                   = 6398, -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY            = 6392, -- There is nothing out of the ordinary here.
        SENSE_OF_FOREBODING                = 6393, -- You are suddenly overcome with a sense of foreboding...
        FELLOW_MESSAGE_OFFSET              = 6406, -- I'm ready. I suppose.
        CARRIED_OVER_POINTS                = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY            = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                       = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        GEOMAGNETRON_ATTUNED               = 7017, -- Your <keyitem> has been attuned to a geomagnetic fount in the corresponding locale.
        MEMBERS_LEVELS_ARE_RESTRICTED      = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                      = 6994, -- Tallying conquest results...
        FISHING_MESSAGE_OFFSET             = 7153, -- You can't fish here.
        THE_MACHINE_SEEMS_TO_BE_WORKING    = 7305, -- The machine seems to be working, but you cannot discern its purpose.
        SOMETHING_FALLS_OUT_OF_THE_MACHINE = 7308, -- Something falls out of the machine!
        YOU_CANT_CARRY_ANY_MORE_ITEMS      = 7311, -- There seems to be more left in the machine, but you can't carry any more items.
        MINING_IS_POSSIBLE_HERE            = 7332, -- Mining is possible here if you have <item>.
        CHEST_UNLOCKED                     = 7346, -- You unlock the chest!
        HOMEPOINT_SET                      = 7482, -- Home point set!
    },
    mob =
    {
        BU_GHI_HOWLBLADE  = GetFirstID('BuGhi_Howlblade'),
        ZI_GHI_BONEEATER  = GetFirstID('ZiGhi_Boneeater'),
        BEHYA_HUNDREDWALL = GetFirstID('BeHya_Hundredwall'),
        NI_GHU_NESTFENDER = GetFirstID('NiGhu_Nestfender'),
    },
    npc =
    {
        TREASURE_CHEST = GetFirstID('Treasure_Chest'),
        MINING         = GetTableOfIDs('Mining_Point'),
    },
}

return zones[xi.zone.PALBOROUGH_MINES]
