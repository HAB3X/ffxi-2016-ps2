-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (9 changed, 13 not in the 2007 dialog DAT 6501 and left unchanged).
-----------------------------------
-- Area: East_Ronfaure_[S]
-----------------------------------
zones = zones or {}

zones[xi.zone.EAST_RONFAURE_S] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6380, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398, -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6392, -- There is nothing out of the ordinary here.
        CARRIED_OVER_POINTS           = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        LOGGING_IS_POSSIBLE_HERE      = 7090, -- Logging is possible here if you have <item>.
        CAMPAIGN_RESULTS_TALLIED      = 7298, -- Campaign results tallied.
        FISHING_MESSAGE_OFFSET        = 7674, -- You can't fish here.
        VOIDWALKER_DESPAWN            = 7928, -- The monster fades before your eyes, a look of disappointment on its face.
        VOIDWALKER_NO_MOB             = 8064, -- The <keyitem> quivers ever so slightly, but emits no light. There seem to be no monsters in the area.
        VOIDWALKER_MOB_TOO_FAR        = 8065, -- The <keyitem> quivers ever so slightly and emits a faint light. There seem to be no monsters in the immediate vicinity.
        VOIDWALKER_MOB_HINT           = 8066, -- The <keyitem> resonates [feebly/softly/solidly/strongly/very strongly/furiously], sending a radiant beam of light lancing towards a spot roughly <number> [yalm/yalms] [east/southeast/south/southwest/west/northwest/north/northeast] of here.
        VOIDWALKER_SPAWN_MOB          = 7978, -- A monster materializes out of nowhere!
        VOIDWALKER_UPGRADE_KI_1       = 8069, -- The <keyitem> takes on a slightly deeper hue and becomes <keyitem>!
        VOIDWALKER_UPGRADE_KI_2       = 8070, -- The <keyitem> takes on a deeper, richer hue and becomes <keyitem>!
        VOIDWALKER_BREAK_KI           = 8071, -- The <keyitem> shatters into tiny fragments.
        VOIDWALKER_OBTAIN_KI          = 8072, -- Obtained key item: <keyitem>!
        COMMON_SENSE_SURVIVAL         = 8982, -- It appears that you have arrived at a new survival guide provided by the Servicemen's Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },

    mob =
    {
        GOBLINTRAP = GetFirstID('Goblintrap'),
        SKOGS_FRU  = GetFirstID('Skogs_Fru'),
        MYRADROSH  = GetFirstID('Myradrosh'),

        VOIDWALKER =
        {
            [xi.keyItem.CLEAR_ABYSSITE] =
            {
                17109393, -- Sunderclaw
                17109392, -- Sunderclaw
                17109391, -- Sunderclaw
                17109390, -- Sunderclaw
                17109389, -- Quagmire Pugil
                17109388, -- Quagmire Pugil
                17109387, -- Quagmire Pugil
                17109386, -- Quagmire Pugil
            },

            [xi.keyItem.COLORFUL_ABYSSITE] =
            {
                17109385, -- Capricornus
                17109384, -- Yacumama
            },

            [xi.keyItem.BLUE_ABYSSITE] =
            {
                17109383, -- Krabkatoa
            },

            [xi.keyItem.BLACK_ABYSSITE] =
            {
                17109382, -- Yilbegan
            }
        }
    },

    npc =
    {
        CAMPAIGN_NPC_OFFSET = GetFirstID('Arlayse_RK'), -- San, Bas, Win, Flag +4, CA
        LOGGING             = GetTableOfIDs('Logging_Point'),
    },
}

return zones[xi.zone.EAST_RONFAURE_S]
