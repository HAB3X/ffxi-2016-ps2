-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012pc = the 2012 client + PC 2025 import (report 36) by research/tools/lsb_textids_2007.py (1 changed, 11 not in the 2007 dialog DAT 6499 and left unchanged).
-----------------------------------
-- Area: Caedarva_Mire
-----------------------------------
zones = zones or {}

zones[xi.zone.CAEDARVA_MIRE] =
{
    text =
    {
        NOTHING_HAPPENS               = 119,  -- Nothing happens...
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398, -- Obtained key item: <keyitem>.
        WARHORSE_HOOFPRINT            = 6388, -- You find the hoofprint of a gigantic warhorse...
        NOTHING_OUT_OF_ORDINARY       = 6392, -- There is nothing out of the ordinary here.
        FELLOW_MESSAGE_OFFSET         = 6406, -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        FISHING_MESSAGE_OFFSET        = 6994, -- You can't fish here.
        STAGING_GATE_CLOSER           = 7246, -- You must move closer.
        STAGING_GATE_INTERACT         = 7247, -- This gate guards an area under Imperial control.
        STAGING_GATE_AZOUPH           = 7248, -- Azouph Isle Staging Point.
        STAGING_GATE_DVUCCA           = 7251, -- Dvucca Isle Staging Point.
        CANNOT_LEAVE                  = 7341, -- You cannot leave this area while in the possession of <keyitem>.
        RESPONSE                      = 7266, -- There is no response...
        YOU_HAVE_A_BADGE              = 7363, -- You have a %? Let me have a closer look at that...
        LOGGING_IS_POSSIBLE_HERE      = 7280, -- Logging is possible here if you have <item>.
        LEG_STUCK                     = 7287, -- Your leg is stuck in the swampy ground!
        MYSTERIOUS_EFFECT             = 7288, -- You gain some mysterious effect from the swamp!
        HAND_OVER_TO_IMMORTAL         = 7445, -- You hand over the % to the Immortal.
        YOUR_IMPERIAL_STANDING        = 7362, -- Your Imperial Standing has increased!
        CANNOT_ENTER                  = 7400, -- You cannot enter at this time. Please wait a while before trying again.
        AREA_FULL                     = 7401, -- This area is fully occupied. You were unable to enter.
        MEMBER_NO_REQS                = 7405, -- Not all of your party members meet the requirements for this objective. Unable to enter area.
        MISSING_KEY_ITEM              = 7490, -- You are not in possession of <keyitem>. Unable to enter area.
        MEMBER_TOO_FAR                = 7409, -- One or more party members are too far away from the entrance. Unable to enter area.
        JAZARAATS_HEADSTONE           = 7459, -- The name Sir Jazaraat is engraved on the headstone...
        SOMEONE_SLIPPED               = 7506, -- It looks like someone slipped here...
        HIDEOUS_BEAST_EMERGES         = 7507, -- A hideous beast emerges from the depths of the swamp!
        SEAPRINCES_TOMBSTONE          = 7983, -- It appears to be the grave of a great soul to an age long past.
        SHED_LEAVES                   = 7989, -- The ground is strewn with shed leaves...
        SICKLY_SWEET                  = 7994, -- A sickly sweet fragrance pervades the air...
        STIFLING_STENCH               = 8000, -- A stifling stench pervades the air...
        SHREDDED_SCRAPS               = 8007, -- Shredded scraps of paper are scattered all over...
        DRAWS_NEAR                    = 8016, -- Something draws near!
        HOMEPOINT_SET                 = 9003, -- Home point set!
        UNITY_WANTED_BATTLE_INTERACT  = 8915, -- Those who have accepted % must pay # Unity accolades to participate. The content for this Wanted battle is #. [Ready to begin?/You do not have the appropriate object set, so your rewards will be limited.]
        COMMON_SENSE_SURVIVAL         = 9083, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
        AYNU_KAYSEY           = GetFirstID('Aynu-kaysey'),
        CAEDARVA_TOAD         = GetFirstID('Caedarva_Toad'),
        CHIGOES =
        {
            ['Wild_Karakul'] = utils.slice(GetTableOfIDs('Chigoe'), 1, 5), -- Entries 1-5 of the table (1-indexed, inclusive)
            ['Mosshorn']     = utils.slice(GetTableOfIDs('Chigoe'), 1, 5), -- Shared Chigoes with Karakul
            ['Peallaidh']    = utils.slice(GetTableOfIDs('Chigoe'), 6, 10), -- Peallaidh's own pool, ids xxx11-15
        },
        EXPERIMENTAL_LAMIA    = GetFirstID('Experimental_Lamia'),
        JAZARAAT              = GetFirstID('Jazaraat'),
        KHIMAIRA              = GetFirstID('Khimaira'),
        LAMIA_NO27            = GetFirstID('Lamia_No27'),
        MAHJLAEF_THE_PAINTORN = GetFirstID('Mahjlaef_the_Paintorn'),
        MOSHDAHN              = GetFirstID('Moshdahn'),
        PEALLAIDH             = GetFirstID('Peallaidh'),
        PEALLAIDH_PH_OFFSET   = GetFirstID('Wild_Karakul'), -- These are 270IDs away. Use offset in case of weird shift.
        TYGER                 = GetFirstID('Tyger'),
        VERDELET              = GetFirstID('Verdelet'),
        ZIKKO                 = GetFirstID('Zikko'),
    },
    npc =
    {
        HOOFPRINT           = GetFirstID('Warhorse_Hoofprint'),
        LOGGING             = GetTableOfIDs('Logging_Point'),
        RUNIC_PORTAL_AZOUPH = GetFirstID('Runic_Portal_Azouph'),
        RUNIC_PORTAL_DVUCCA = GetFirstID('Runic_Portal_Dvucca'),
    },
}

return zones[xi.zone.CAEDARVA_MIRE]
