-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012pc = the 2012 client + PC 2025 import (report 36) by research/tools/lsb_textids_2007.py (1 changed, 6 not in the 2007 dialog DAT 6449 and left unchanged).
-----------------------------------
-- Area: Riverne-Site_B01
-----------------------------------
zones = zones or {}

zones[xi.zone.RIVERNE_SITE_B01] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398, -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6392, -- There is nothing out of the ordinary here.
        CARRIED_OVER_POINTS           = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                 = 6994, -- Tallying conquest results...
        TIME_IN_THE_BATTLEFIELD_IS_UP = 7158, -- Your time in the battlefield is up! Now exiting...
        CLEARED_BUT_MEMBERS_ENGAGED   = 7160, -- You are cleared to enter the battlefield, but you cannot while party members are engaged in combat.
        PARTY_MEMBERS_ARE_ENGAGED     = 7171, -- The battlefield where your party members are engaged in combat is locked. Access is denied.
        MEMBERS_OF_YOUR_PARTY         = 7459, -- Currently, # members of your party (including yourself) have clearance to enter the battlefield.
        MEMBERS_OF_YOUR_ALLIANCE      = 7460, -- Currently, # members of your alliance (including yourself) have clearance to enter the battlefield.
        TIME_LIMIT_FOR_THIS_BATTLE_IS = 7462, -- The time limit for this battle is <number> minutes.
        PARTY_MEMBERS_HAVE_FALLEN     = 7498, -- All party members have fallen in battle. Now leaving the battlefield.
        THE_PARTY_WILL_BE_REMOVED     = 7504, -- If all party members' HP are still zero after # minute[/s], the party will be removed from the battlefield.
        ENTERING_THE_BATTLEFIELD_FOR  = 7516, -- Entering the battlefield for [Storms of Fate/The Wyrmking Descends]!
        SD_VERY_SMALL                 = 7518, -- The spatial displacement is very small. If you only had some item that could make it bigger...
        SD_HAS_GROWN                  = 7519, -- The spatial displacement has grown.
        SPACE_SEEMS_DISTORTED         = 7520, -- The space around you seems oddly distorted and disrupted.
        MONUMENT                      = 7526, -- Something has been engraved on this stone, but the message is too difficult to make out.
        GROUND_GIVING_HEAT            = 7528, -- The ground here is giving off heat.
        BAHAMUT_TAUNT                 = 7596, -- Children of Vana'diel, what do you think to accomplish by fighting for your lives? You know your efforts are futile, yet still you resist...
        HOMEPOINT_SET                 = 7725, -- Home point set!
        UNITY_WANTED_BATTLE_INTERACT  = 7638, -- Those who have accepted % must pay # Unity accolades to participate. The content for this Wanted battle is #. [Ready to begin?/You do not have the appropriate object set, so your rewards will be limited.]
    },
    mob =
    {
        BAHAMUT                 = GetFirstID('Bahamut'),
        BAHAMUT_V2              = GetFirstID('Bahamut_bv2'),
        IMDUGUD                 = GetFirstID('Imdugud'),
        SPELL_SPITTER_SPILUSPOK = GetFirstID('Spell_Spitter_Spilospok'),
        UNSTABLE_CLUSTER        = GetFirstID('Unstable_Cluster'),
    },
    npc =
    {
        DISPLACEMENT_OFFSET = GetFirstID('Spatial_Displacement'),
    },
}

return zones[xi.zone.RIVERNE_SITE_B01]
