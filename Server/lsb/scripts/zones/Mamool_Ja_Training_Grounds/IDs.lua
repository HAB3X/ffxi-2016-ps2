-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (13 changed, 5 not in the 2007 dialog DAT 6486 and left unchanged).
-----------------------------------
-- Area: Mamool_Ja_Training_Grounds
-----------------------------------
zones = zones or {}

zones[xi.zone.MAMOOL_JA_TRAINING_GROUNDS] =
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
        PLAYER_OBTAINS_ITEM           = 7248, -- <name> obtains <item>!
        ASSAULT_START_OFFSET          = 7383, -- Max MP Down removed for <name>.
        TIME_TO_COMPLETE              = 7444, -- You have <number> [minute/minutes] (Earth time) to complete this mission.
        MISSION_FAILED                = 7445, -- The mission has failed. Leaving area.
        RUNE_UNLOCKED_POS             = 7446, -- Mission objective completed. Unlocking Rune of Release ([A/B/C/D/E/F/G/H/I/J/K/L/M/N/O/P/Q/R/S/T/U/V/W/X/Y/Z]-<number>).
        ASSAULT_POINTS_OBTAINED       = 7448, -- You gain <number> [Assault point/Assault points]!
        TIME_REMAINING_MINUTES        = 7449, -- Time remaining: <number> [minute/minutes] (Earth time).
        TIME_REMAINING_SECONDS        = 7450, -- Time remaining: <number> [second/seconds] (Earth time).
        PARTY_FALLEN                  = 7452, -- All party members have fallen in battle. Mission failure in <number> [minute/minutes].
        BRUJEEL_TEXT                  = 7461, -- Am I glad to see you!
    },

    mob =
    {
        DILAPIDATED_GATE     = GetFirstID('Dilapidated_Gate'),
        MAMOOL_JA_WARDER_WHM = GetFirstID('Mamool_Ja_Warder_whm'),

        [xi.assault.mission.PREEMPTIVE_STRIKE] =
        {
            MOBS_START =
            {
                17047570, 17047571, 17047572, 17047573, 17047574, 17047575, 17047576, 17047577, 17047578, 17047579,
                17047580, 17047581, 17047582, 17047583, 17047584, 17047585, 17047586, 17047587, 17047588, 17047589,
            },
        },
    },

    npc =
    {
        ANCIENT_LOCKBOX = GetFirstID('Ancient_Lockbox'),
        RUNE_OF_RELEASE = GetFirstID('Rune_of_Release'),
        BRUJEEL         = GetFirstID('Brujeel'),
        _JU3            = GetFirstID('_ju3'),
        _JU5            = GetFirstID('_ju5'),
        _JU7            = GetFirstID('_ju7'),
        _JUL            = GetFirstID('_jul'),
        _JUM            = GetFirstID('_jum'),
        _JUN            = GetFirstID('_jun'),
    },
}

return zones[xi.zone.MAMOOL_JA_TRAINING_GROUNDS]
