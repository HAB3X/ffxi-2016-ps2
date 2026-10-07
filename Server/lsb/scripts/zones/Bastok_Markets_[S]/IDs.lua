-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (24 changed, 8 not in the 2007 dialog DAT 6507 and left unchanged).
-----------------------------------
-- Area: Bastok_Markets_[S]
-----------------------------------
zones = zones or {}

zones[xi.zone.BASTOK_MARKETS_S] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378,  -- Obtained: <item>.
        GIL_OBTAINED                  = 6379,  -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398,  -- Obtained key item: <keyitem>.
        ITEM_RETURNED_TO_CHAR         = 6390,  -- The <keyitem> is returned to you.
        REPORT_TO_CAIT_SITH           = 6979,  -- You have obtained all of Lilisette's memory fragments. Make haste and report to Cait Sith.
        CARRIED_OVER_POINTS           = 7006,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028,  -- Your party is unable to participate because certain members' levels are restricted.
        FISHING_MESSAGE_OFFSET        = 6994,  -- You can't fish here.
        GATE_IS_LOCKED                = 7132,  -- The gate is locked.
        BLINGBRIX_SHOP_DIALOG         = 7136,  -- Blingbrix good Gobbie from Boodlix's! Boodlix's Emporium help fighting fighters and maging mages. Gil okay, okay?
        MOG_LOCKER_OFFSET             = 7395,  -- Your Mog Locker lease is valid until <timestamp>, kupo.
        REGIME_CANCELED               = 7611,  -- Current training regime canceled.
        HUNT_ACCEPTED                 = 7629,  -- Hunt accepted!
        USE_SCYLDS                    = 7630,  -- You use <number> [scyld/scylds]. Scyld balance: <number>.
        HUNT_RECORDED                 = 7641,  -- You record your hunt.
        OBTAIN_SCYLDS                 = 7643,  -- You obtain <number> [scyld/scylds]! Current balance: <number> [scyld/scylds].
        HUNT_CANCELED                 = 7647,  -- Hunt canceled.
        HOMEPOINT_SET                 = 10740, -- Home point set!
        KARLOTTE_DELIVERY_DIALOG      = 10755, -- I am here to help with all your parcel delivery needs.
        WELDON_DELIVERY_DIALOG        = 10756, -- Do you have something you wish to send?
        ARE_TAKEN_AWAY_FROM_CHAR      = 11556, -- The <keyitem> are taken away from <player>!
        CAMPAIGN_RESULTS_TALLIED      = 11639, -- Campaign results tallied.
        NOW_ALLIED_WITH               = 11914, -- You are now a member of the [/Knights of the Iron Ram/Republican Legion's Fourth Division/Cobra Unit]!
        ALLIED_SIGIL                  = 12239, -- You have received the Allied Sigil!
        SILKE_SHOP_DIALOG             = 12690, -- You wouldn't happen to be a fellow scholar, by any chance? The contents of these pages are beyond me, but perhaps you might glean something from them. They could be yours...for a nominal fee.
        KEVAN_TURN_IN                 = 13437, -- Just as we suspected. This contains a great deal of information that will prove vital to our cause. Hm, what's this? Not sure what to make of this... Doesn't seem to be terribly important. Here, why don't you hang onto it? See if you can't get some use out of it down the road.
        RETRIEVE_DIALOG_ID            = 14599, -- You retrieve <item> from the porter moogle's care.
        NOT_ENOUGH_NOTES              = 14773, -- You tryin' to cheat me? That's not nearly enough notes!
        COMMON_SENSE_SURVIVAL         = 14817, -- It appears that you have arrived at a new survival guide provided by the Servicemen's Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
    },
    npc =
    {
        CAMPAIGN_NPC_OFFSET = GetFirstID('Hostarfaux_TK'), -- San, Bas, Win, Flag +4, CA
        -- SHENNI              = GetFirstID('Shenni'),
    },
}

return zones[xi.zone.BASTOK_MARKETS_S]
