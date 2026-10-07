-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (16 changed, 7 not in the 2007 dialog DAT 6631 and left unchanged).
-----------------------------------
-- Area: Cloister_of_Tides
-----------------------------------
zones = zones or {}

zones[xi.zone.CLOISTER_OF_TIDES] =
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
        PROTOCRYSTAL                     = 7177, -- It is a giant crystal.
        MEMBERS_OF_YOUR_PARTY            = 7459, -- Currently, # members of your party (including yourself) have clearance to enter the battlefield.
        MEMBERS_OF_YOUR_ALLIANCE         = 7460, -- Currently, # members of your alliance (including yourself) have clearance to enter the battlefield.
        TIME_LIMIT_FOR_THIS_BATTLE_IS    = 7462, -- The time limit for this battle is <number> minutes.
        PARTY_MEMBERS_HAVE_FALLEN        = 7498, -- All party members have fallen in battle. Now leaving the battlefield.
        THE_PARTY_WILL_BE_REMOVED        = 7504, -- If all party members' HP are still zero after # minute[/s], the party will be removed from the battlefield.
        LEVIATHAN_UNLOCKED               = 7507, -- You are now able to summon [Ifrit/Titan/Leviathan/Garuda/Shiva/Ramuh].
        ENTERING_THE_BATTLEFIELD_FOR     = 7587, -- Entering the battlefield for [Trial by Water/Trial-Size Trial by Water/Waking the Beast/Sugar-coated Directive/★Trial by Water]!
        ATTACH_SEAL                      = 7739, -- <player> attaches <item> to the protocrystal.
        POWER_STYMIES                    = 7740, -- An unseen power stymies your efforts to attach <item> to the protocrystal.
    },
    mob =
    {
        LEVIATHAN_PRIME_ASA   = GetFirstID('Leviathan_Prime_ASA'),
    },
    npc =
    {
    },
}

return zones[xi.zone.CLOISTER_OF_TIDES]
