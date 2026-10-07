-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (24 changed, 6 not in the 2007 dialog DAT 6585 and left unchanged).
-----------------------------------
-- Area: Throne_Room
-----------------------------------
zones = zones or {}

zones[xi.zone.THRONE_ROOM] =
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
        CONQUEST_BASE                 = 6994, -- Tallying conquest results...
        TIME_IN_THE_BATTLEFIELD_IS_UP = 7158, -- Your time in the battlefield is up! Now exiting...
        CLEARED_BUT_MEMBERS_ENGAGED   = 7160, -- You are cleared to enter the battlefield, but you cannot while party members are engaged in combat.
        PARTY_MEMBERS_ARE_ENGAGED     = 7171, -- The battlefield where your party members are engaged in combat is locked. Access is denied.
        NO_BATTLEFIELD_ENTRY          = 7173, -- The door is sealed shut with an evil curse.
        UNABLE_TO_PROTECT             = 7211, -- You were unable to protect Captain Volker. Now leaving the battlefield.
        TESTIMONY_IS_TORN             = 7213, -- Your <item> is torn...
        TESTIMONY_WEARS               = 7214, -- Your <item> [/rips into shreds!/is on the verge of tearing apart.../is showing signs of wear...] (# [use remains/uses remain].)
        MEMBERS_OF_YOUR_PARTY         = 7459, -- Currently, <number> members of your party (including yourself) have clearance to enter the battlefield.
        MEMBERS_OF_YOUR_ALLIANCE      = 7460, -- Currently, <number> members of your alliance (including yourself) have clearance to enter the battlefield.
        TIME_LIMIT_FOR_THIS_BATTLE_IS = 7462, -- The time limit for this battle is <number> minutes.
        ORB_IS_CRACKED                = 7463, -- There is a crack in the %. It no longer contains a monster.
        A_CRACK_HAS_FORMED            = 7464, -- A crack has formed on the <item>, and the beast inside has been unleashed!
        PARTY_MEMBERS_HAVE_FALLEN     = 7498, -- All party members have fallen in battle. Now leaving the battlefield.
        THE_PARTY_WILL_BE_REMOVED     = 7504, -- If all party members' HP are still zero after # minute[/s], the party will be removed from the battlefield.
        ENTERING_THE_BATTLEFIELD_FOR  = 7609, -- Entering the battlefield for [The Shadow Lord Battle/Where Two Paths Converge/Kindred Spirits/Survival of the Wisest/Smash! A Malevolent Menace/★Kindred Spirits/★The Shadow Lord Battle/True Love/A Fond Farewell/Kipdrix the Faithful]!
        NO_HIDE_AWAY                  = 7631, -- I have not been hiding away from my troubles!
        FEEL_MY_PAIN                  = 7632, -- Feel my twenty years of pain!
        YOUR_ANSWER                   = 7633, -- Is that your answer!?
        RETURN_TO_THE_DARKNESS        = 7634, -- Return with your soul to the darkness you came from!
        CANT_UNDERSTAND               = 7635, -- You--a man who has never lived bound by the chains of his country--how can you understand my pain!?
        BLADE_ANSWER                  = 7636, -- Let my blade be the answer!
    },
    mob =
    {
        GRAND_MARQUIS_CHOMIEL     = GetFirstID('Grand_Marquis_Chomiel'),
        RIKO_KUPENREICH           = GetFirstID('Riko_Kupenreich'),
        SHADOW_LORD_RANK_5_OFFSET = GetFirstID('Shadow_Lord_Phase_1'),
        ZEID_BCNM_OFFSET          = GetFirstID('Zeid'),
    },
    npc =
    {
    },
}

return zones[xi.zone.THRONE_ROOM]
