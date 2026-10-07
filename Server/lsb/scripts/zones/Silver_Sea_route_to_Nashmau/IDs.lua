-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (9 changed, 5 not in the 2007 dialog DAT 6478 and left unchanged).
-----------------------------------
-- Area: Silver_Sea_route_to_Nashmau
-----------------------------------
zones = zones or {}

zones[xi.zone.SILVER_SEA_ROUTE_TO_NASHMAU] =
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
        FISHING_MESSAGE_OFFSET        = 6994, -- You can't fish here.
        ON_WAY_TO_NASHMAU             = 7245, -- We are on our way to Nashmau. We should arrive in [less than an hour/about 1 hour/about 2 hours/about 3 hours/about 4 hours/about 5 hours/about 6 hours/about 7 hours] (# [minute/minutes] in Earth time).
        DOCKING_IN_NASHMAU            = 7246, -- We are now docking in Nashmau.
        NEARING_NASHMAU               = 7247, -- We are nearing Nashmau.
        JIDWAHN_SHOP_DIALOG           = 7249, -- Would you care for some items to use on your travels?
        ARRIVING_SOON_NASHMAU         = 7250, -- We are on our way to Nashmau. We will be arriving soon.
    },
    mob =
    {
        PROTEUS = GetFirstID('Proteus'),
    },
    npc =
    {
    },
}

return zones[xi.zone.SILVER_SEA_ROUTE_TO_NASHMAU]
