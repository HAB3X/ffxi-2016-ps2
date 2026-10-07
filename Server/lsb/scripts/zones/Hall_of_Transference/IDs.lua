-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (6 changed, 5 not in the 2007 dialog DAT 6434 and left unchanged).
-----------------------------------
-- Area: Hall_of_Transference
-----------------------------------
zones = zones or {}

zones[xi.zone.HALL_OF_TRANSFERENCE] =
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
        NO_RESPONSE_OFFSET            = 7189, -- There is no response.
        DOOR_FIRMLY_SHUT              = 7190, -- The door is firmly shut.
        YOU_MUST_MOVE_CLOSER          = 7191, -- You must move closer to inspect the device.
    },
    mob =
    {
    },
    npc =
    {
    },
}

return zones[xi.zone.HALL_OF_TRANSFERENCE]
