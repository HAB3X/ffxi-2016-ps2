-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (28 changed, 8 not in the 2007 dialog DAT 6588 and left unchanged).
-----------------------------------
-- Area: Chamber_of_Oracles
-----------------------------------
zones = zones or {}

zones[xi.zone.CHAMBER_OF_ORACLES] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED          = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                    = 6378, -- Obtained: <item>.
        GIL_OBTAINED                     = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED                 = 6398, -- Obtained key item: <keyitem>.
        CARRIED_OVER_POINTS              = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY          = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                     = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED    = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                    = 6994, -- Tallying conquest results...
        YOU_CANNOT_ENTER_THE_BATTLEFIELD = 7155, -- You cannot enter the battlefield at present. Please wait a little longer.
        TIME_IN_THE_BATTLEFIELD_IS_UP    = 7158, -- Your time in the battlefield is up! Now exiting...
        CLEARED_BUT_MEMBERS_ENGAGED      = 7160, -- You are cleared to enter the battlefield, but you cannot while party members are engaged in combat.
        PARTY_MEMBERS_ARE_ENGAGED        = 7171, -- The battlefield where your party members are engaged in combat is locked. Access is denied.
        NO_BATTLEFIELD_ENTRY             = 7174, -- A mysterious force is sealing the platform.
        TESTIMONY_IS_TORN                = 7213, -- Your <item> is torn...
        TESTIMONY_WEARS                  = 7214, -- Your <item> [/rips into shreds!/is on the verge of tearing apart.../is showing signs of wear...] (# [use remains/uses remain].)
        MEMBERS_OF_YOUR_PARTY            = 7459, -- Currently, # members of your party (including yourself) have clearance to enter the battlefield.
        MEMBERS_OF_YOUR_ALLIANCE         = 7460, -- Currently, # members of your alliance (including yourself) have clearance to enter the battlefield.
        TIME_LIMIT_FOR_THIS_BATTLE_IS    = 7462, -- The time limit for this battle is <number> minutes.
        ORB_IS_CRACKED                   = 7463, -- There is a crack in the %. It no longer contains a monster.
        A_CRACK_HAS_FORMED               = 7464, -- A crack has formed on the <item>, and the beast inside has been unleashed!
        PARTY_MEMBERS_HAVE_FALLEN        = 7498, -- All party members have fallen in battle. Now leaving the battlefield.
        THE_PARTY_WILL_BE_REMOVED        = 7504, -- If all party members' HP are still zero after # minute[/s], the party will be removed from the battlefield.
        ENTERING_THE_BATTLEFIELD_FOR     = 7516, -- Entering the battlefield for [Through the Quicksand Caves/Legion XI Comitatensis/Shattering Stars (SAM)/Shattering Stars (NIN)/Shattering Stars (DRG)/Cactuar Suave/Eye of the Storm/The Scarlet King/Roar! A Cat Burglar Bares Her Fangs/Dragon Scales/★Legion XI Comitatensis]!
        PLACED_INTO_THE_PEDESTAL         = 7551, -- It appears that something should be placed into this pedestal.
        YOU_PLACE_THE                    = 7645, -- You place the <item> into the pedestal.
        IS_SET_IN_THE_PEDESTAL           = 7646, -- The <item> is set in the pedestal.
        HAS_LOST_ITS_POWER               = 7647, -- The <item> has lost its power.
        DOOR_IS_FIRMLY_SHUT              = 7555, -- The door is firmly shut.
        YOU_DECIDED_TO_SHOW_UP           = 7573, -- So, you decided to show up. Now it's time to see what you're really made of, heh heh heh.
        LOOKS_LIKE_YOU_WERENT_READY      = 7574, -- Looks like you weren't ready for me, were you? Now go home, wash your face, and come back when you think you've got what it takes.
        YOUVE_COME_A_LONG_WAY            = 7575, -- Hm. That was a mighty fine display of skill there, <name>. You've come a long way...
        TEACH_YOU_TO_RESPECT_ELDERS      = 7576, -- I'll teach you to respect your elders!
        TAKE_THAT_YOU_WHIPPERSNAPPER     = 7577, -- Take that, you whippersnapper!
        NOW_THAT_IM_WARMED_UP            = 7578, -- Now that I'm warmed up...
        THAT_LL_HURT_IN_THE_MORNING      = 7579, -- Ungh... That'll hurt in the morning...
    },
    mob =
    {
        CENTURIO_V_III   = GetFirstID('Centurio_V-III'),
        MAAT             = GetFirstID('Maat_sam'),
        NANAA_MIHGO      = GetFirstID('Nanaa_Mihgo'),
        SECUTOR_XI_XXXII = GetFirstID('Secutor_XI-XXXII'),
    },
    npc =
    {
    },
}

return zones[xi.zone.CHAMBER_OF_ORACLES]
