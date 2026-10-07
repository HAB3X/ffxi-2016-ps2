-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (7 changed, 5 not in the 2007 dialog DAT 6519 and left unchanged).
-----------------------------------
-- Area: Castle_Oztroja_[S]
-----------------------------------
zones = zones or {}

zones[xi.zone.CASTLE_OZTROJA_S] =
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
        CAMPAIGN_RESULTS_TALLIED      = 7523, -- Campaign results tallied.
        PARTY_MEMBERS_HAVE_FALLEN     = 7953, -- All party members have fallen in battle. Now leaving the battlefield.
        THE_PARTY_WILL_BE_REMOVED     = 7959, -- If all party members' HP are still zero after # minute[/s], the party will be removed from the battlefield.
    },
    mob =
    {
        AA_XALMO_THE_SAVAGE    = GetFirstID('Aa_Xalmo_the_Savage'),
        ZHUU_BUXU_THE_SILENT   = GetFirstID('Zhuu_Buxu_the_Silent'),
        DUU_MASA_THE_ONECUT    = GetFirstID('Duu_Masa_the_Onecut'),
        DEE_ZELKO_THE_ESOTERIC = GetFirstID('Dee_Zelko_the_Esoteric'),
        MARQUIS_FORNEUS        = GetFirstID('Marquis_Forneus'),
        LOO_KUTTO_THE_PENSIVE  = GetFirstID('Loo_Kutto_the_Pensive'),
        FLESHGNASHER           = GetFirstID('Fleshgnasher'),
        VEE_LADU_THE_TITTERER  = GetFirstID('Vee_Ladu_the_Titterer'),
        MAA_ILLMU_THE_BESTOWER = GetFirstID('Maa_Illmu_the_Bestower'),
        ASTERION               = GetFirstID('Asterion'),
        SUU_XICU_THE_CANTABILE = GetFirstID('Suu_Xicu_the_Cantabile'),
    },
    npc =
    {
        CAMPAIGN_NPC_OFFSET = GetFirstID('Yaibroux_TK'), -- San, Bas, Win, Flag +4, CA
    },
}

return zones[xi.zone.CASTLE_OZTROJA_S]
