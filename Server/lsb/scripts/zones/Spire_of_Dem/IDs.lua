-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (15 changed, 7 not in the 2007 dialog DAT 6439 and left unchanged).
-----------------------------------
-- Area: Spire_of_Dem
-----------------------------------
zones = zones or {}

zones[xi.zone.SPIRE_OF_DEM] =
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
        TIME_IN_THE_BATTLEFIELD_IS_UP = 6999, -- Your time in the battlefield is up! Now exiting...
        CLEARED_BUT_MEMBERS_ENGAGED   = 7001, -- You are cleared to enter the battlefield, but you cannot while party members are engaged in combat.
        PARTY_MEMBERS_ARE_ENGAGED     = 7012, -- The battlefield where your party members are engaged in combat is locked. Access is denied.
        NO_BATTLEFIELD_ENTRY          = 7024, -- You can hear a faint scraping sound from within, but the way is barred by some strange membrane...
        MEMBERS_OF_YOUR_PARTY         = 7300, -- Currently, # members of your party (including yourself) have clearance to enter the battlefield.
        MEMBERS_OF_YOUR_ALLIANCE      = 7301, -- Currently, # members of your alliance (including yourself) have clearance to enter the battlefield.
        TIME_LIMIT_FOR_THIS_BATTLE_IS = 7303, -- The time limit for this battle is <number> minutes.
        ORB_IS_CRACKED                = 7304, -- There is a crack in the %. It no longer contains a monster.
        A_CRACK_HAS_FORMED            = 7305, -- A crack has formed on the <item>, and the beast inside has been unleashed!
        PARTY_MEMBERS_HAVE_FALLEN     = 7339, -- All party members have fallen in battle. Now leaving the battlefield.
        THE_PARTY_WILL_BE_REMOVED     = 7345, -- If all party members' HP are still zero after # minute[/s], the party will be removed from the battlefield.
        FADES_INTO_NOTHINGNESS        = 7438, -- The % fades into nothingness...
        ENTERING_THE_BATTLEFIELD_FOR  = 7536, -- Entering the battlefield for [Ancient Flames Beckon/You Are What You Eat/Empty Dreams]!
        CANT_REMEMBER                 = 7659, -- You cannot remember when exactly, but you have obtained <item>!
    },
    mob =
    {
        PROGENERATOR = GetFirstID('Progenerator'),
        INGESTER     = GetFirstID('Ingester'),
    },
    npc =
    {
    },
}

return zones[xi.zone.SPIRE_OF_DEM]
