-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (36 changed, 6 not in the 2007 dialog DAT 6484 and left unchanged).
-----------------------------------
-- Area: Navukgo_Execution_Chamber
-----------------------------------
zones = zones or {}

zones[xi.zone.NAVUKGO_EXECUTION_CHAMBER] =
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
        TIME_IN_THE_BATTLEFIELD_IS_UP = 7158, -- Your time in the battlefield is up! Now exiting...
        CLEARED_BUT_MEMBERS_ENGAGED   = 7160, -- You are cleared to enter the battlefield, but you cannot while party members are engaged in combat.
        PARTY_MEMBERS_ARE_ENGAGED     = 7171, -- The battlefield where your party members are engaged in combat is locked. Access is denied.
        NO_BATTLEFIELD_ENTRY          = 7196, -- The door is locked.
        TESTIMONY_IS_TORN             = 7213, -- Your <item> is torn...
        TESTIMONY_WEARS               = 7214, -- Your <item> [/rips into shreds!/is on the verge of tearing apart.../is showing signs of wear...] (# [use remains/uses remain].)
        MEMBERS_OF_YOUR_PARTY         = 7459, -- Currently, # members of your party (including yourself) have clearance to enter the battlefield.
        MEMBERS_OF_YOUR_ALLIANCE      = 7460, -- Currently, # members of your alliance (including yourself) have clearance to enter the battlefield.
        TIME_LIMIT_FOR_THIS_BATTLE_IS = 7462, -- The time limit for this battle is <number> minutes.
        ORB_IS_CRACKED                = 7463, -- There is a crack in the %. It no longer contains a monster.
        A_CRACK_HAS_FORMED            = 7464, -- A crack has formed on the <item>, and the beast inside has been unleashed!
        PARTY_MEMBERS_HAVE_FALLEN     = 7498, -- All party members have fallen in battle. Now leaving the battlefield.
        THE_PARTY_WILL_BE_REMOVED     = 7504, -- If all party members' HP are still zero after # minute[/s], the party will be removed from the battlefield.
        IMPERIAL_ORDER_BREAKS         = 7597, -- The <item> breaks!
        ENTERING_THE_BATTLEFIELD_FOR  = 7517, -- Entering the battlefield for [Tough Nut to Crack/Happy Caster/Omens/Achieving True Power/Shield of Diplomacy/An Imperial Heist]!
        SHAMARHAAN_LET_US_BEGIN       = 7547, -- Let us begin.
        SHAMARHAAN_AUTOMATON_POWER    = 7548, -- Do not underestimate my automaton's power!
        SHAMARHAAN_NOT_READY          = 7549, -- Unfortunately, it looks like you are still not ready yet...
        SHAMARHAAN_MAGNIFICENT        = 7550, -- Magnificent work...
        SHAMARHAAN_GOT_TRICKS         = 7551, -- I've got a few tricks up my own sleeve!
        SHAMARHAAN_LETS_TRY           = 7552, -- Hmm... Let's try this one...
        SHAMARHAAN_FULL_STEAM         = 7553, -- Full steam ahead!
        SHAMARHAAN_ENOUGH             = 7554, -- Enough. I have no desire to watch this foolishness all day.
        SHAMARHAAN_UNDERESTIMATED     = 7555, -- It looks like I underestimated you!
        YOUR_LEVEL_LIMIT_IS_NOW_75    = 7557, -- Your level limit is now 75.
        KARABABA_ENOUGH               = 7562, -- That's quite enough...
        KARABABA_ROUGH                = 7563, -- Time for me to start playing rough!
        KARABARA_FIRE                 = 7564, -- Fuel for the fire! It doesn't pay to invoke my ire!
        KARABARA_ICE                  = 7565, -- Well, if you won't play nice, I'll put your sorry hide on ice!
        KARABARA_WIND                 = 7566, -- This battle is growing stale. How about we have a refreshing gale!
        KARABARA_EARTH                = 7567, -- Sometimes it comes as quite a shock, how much damage you can deal with simple rock!
        KARABARA_LIGHTNING            = 7568, -- How I love to rip things asunder! Witness the power of lightning and thunder!
        KARABARA_WATER                = 7569, -- Water is more dangerous than most expect. Never fear, I'll teach you respect!
        KARABABA_QUIT                 = 7577, -- What a completely useless shield. It's time for me to quit the field.
    },
    mob =
    {
        KHIMAIRA_13   = GetFirstID('Khimaira_13'),
        IMMORTAL_FLAN = GetFirstID('Immortal_Flan'),
        SHAMARHAAN    = GetFirstID('Shamarhaan'),
    },
    npc =
    {
    },
}

return zones[xi.zone.NAVUKGO_EXECUTION_CHAMBER]
