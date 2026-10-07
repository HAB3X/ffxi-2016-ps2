-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (31 changed, 7 not in the 2007 dialog DAT 6480 and left unchanged).
-----------------------------------
-- Area: The_Ashu_Talif (60)
-----------------------------------
zones = zones or {}

zones[xi.zone.THE_ASHU_TALIF] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        FULL_INVENTORY_AFTER_TRADE    = 6377, -- You cannot obtain the <item>. Try trading again after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398, -- Obtained key item: <keyitem>.
        KEYITEM_LOST                  = 6399, -- Lost key item: <keyitem>.
        NOT_HAVE_ENOUGH_GIL           = 6383, -- You do not have enough gil.
        ITEMS_OBTAINED                = 6387, -- You obtain <number> <item>!
        CARRIED_OVER_POINTS           = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        TIME_TO_COMPLETE              = 7340, -- You have <number> [minute/minutes] (Earth time) to complete this mission.
        MISSION_FAILED                = 7341, -- The mission has failed. Leaving area.
        TIME_REMAINING_MINUTES        = 7345, -- Time remaining: <number> [minute/minutes] (Earth time).
        TIME_REMAINING_SECONDS        = 7346, -- Time remaining: <number> [second/seconds] (Earth time).
        FADES_INTO_NOTHINGNESS        = 7431, -- The <item> fades into nothingness...
        PARTY_FALLEN                  = 7348, -- All party members have fallen in battle. Mission failure in <number> [minute/minutes].
        GOWAM_DEATH                   = 7495, -- Ugh...
        YAZQUHL_CORSAIR_COULD         = 7496, -- Did you really think a corsair could defeat me? Ludicrous.
        YAZQUHL_ENGAGE                = 7497, -- No need for worry, corsairs... You will be a fitting sacrifice for the Empire!
        YAZQUHL_DEATH                 = 7498, -- Defeated...by a corsair...?
        TAKE_THIS                     = 7499, -- Take this!
        REST_BENEATH                  = 7500, -- Time for you to rest beneath the waves!
        STOP_US                       = 7501, -- There's nothing you can do to stop us!
        YOU_WILL_REGRET               = 7502, -- You will regret for eternity the day you turned against the Empire!
        BATTLE_HIGH_SEAS              = 7503, -- A battle on the high seas? My warrior's spirit soars in anticipation!
        TIME_IS_NEAR                  = 7504, -- My time is near...
        SO_I_FALL                     = 7505, -- And so I fall...
        SWIFT_AS_LIGHTNING            = 7506, -- Swift as lightning...!
        HARNESS_THE_WHIRLWIND         = 7507, -- Harness the whirlwind...!
        STING_OF_MY_BLADE             = 7508, -- Feel the sting of my blade!
        UNNATURAL_CURS                = 7509, -- Unnatural curs!
        OVERPOWERED_CREW              = 7510, -- You have overpowered my crew...
        TEST_YOUR_BLADES              = 7511, -- I will test your blades. Prepare to join your ancestors...
        FOR_THE_BLACK_COFFIN          = 7512, -- For the Black Coffin!
        FOR_EPHRAMAD                  = 7513, -- For Ephramad!
        TROUBLESOME_SQUABS            = 7514, -- Troublesome squabs...
    },

    mob =
    {
        GESSHO              = GetFirstID('Gessho'),
        ASHU_CREW_OFFSET    = GetFirstID('Ashu_Talif_Crew_mnk'),
        ASHU_CAPTAIN_OFFSET = GetFirstID('Ashu_Talif_Captain'),
        GOWAM               = GetFirstID('Gowam'),
        YAZQUHL             = GetFirstID('Yazquhl'),
    },

    npc =
    {
    },
}

return zones[xi.zone.THE_ASHU_TALIF]
