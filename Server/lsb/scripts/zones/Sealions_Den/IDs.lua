-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (18 changed, 6 not in the 2007 dialog DAT 6452 and left unchanged).
-----------------------------------
-- Area: Sealions_Den
-----------------------------------
zones = zones or {}

zones[xi.zone.SEALIONS_DEN] =
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
        IRON_GATE_LOCKED              = 7029, -- A solid iron gate. It is tightly locked...
        MEMBERS_OF_YOUR_PARTY         = 7300, -- Currently, # members of your party (including yourself) have clearance to enter the battlefield.
        MEMBERS_OF_YOUR_ALLIANCE      = 7301, -- Currently, # members of your alliance (including yourself) have clearance to enter the battlefield.
        TIME_LIMIT_FOR_THIS_BATTLE_IS = 7303, -- The time limit for this battle is <number> minutes.
        PARTY_MEMBERS_HAVE_FALLEN     = 7339, -- All party members have fallen in battle. Now leaving the battlefield.
        THE_PARTY_WILL_BE_REMOVED     = 7345, -- If all party members' HP are still zero after # minute[/s], the party will be removed from the battlefield.
        CONQUEST_BASE                 = 7353, -- Tallying conquest results...
        ENTERING_THE_BATTLEFIELD_FOR  = 7609, -- Entering the battlefield for [One to Be Feared/The Warrior's Path/★The Warrior's Path/★One to Be Feared]!
        COSMIC_ELUCIDATION            = 7812, -- You are overwhelmed by Tenzen's Cosmic Elucidation!
        TENZEN_MSG_OFFSET             = 7844, -- You will fall to my blade!
        MAKKI_CHEBUKKI_OFFSET         = 7848, -- Samurai Sky Pirate Power!
        KUKKI_CHEBUKKI_OFFSET         = 7853, -- What? Nooo!
        CHERUKIKI_OFFSET              = 7859, -- We're doomed!
    },
    mob =
    {
        CHERUKIKI      = GetFirstID('Cherukiki'),
        KUKKI_CHEBUKKI = GetFirstID('Kukki-Chebukki'),
        MAKKI_CHEBUKKI = GetFirstID('Makki-Chebukki'),
        MAMMET_22_ZETA = GetFirstID('Mammet-22_Zeta'),
        TENZEN         = GetFirstID('Tenzen'),
    },
    npc =
    {
        AIRSHIP_DOOR_OFFSET = GetFirstID('Airship_Door'),
    },
}

return zones[xi.zone.SEALIONS_DEN]
