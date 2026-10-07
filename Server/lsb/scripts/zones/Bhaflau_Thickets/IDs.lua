-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (23 changed, 11 not in the 2007 dialog DAT 6472 and left unchanged).
-----------------------------------
-- Area: Bhaflau_Thickets
-----------------------------------
zones = zones or {}

zones[xi.zone.BHAFLAU_THICKETS] =
{
    text =
    {
        NOTHING_HAPPENS               = 119,  -- Nothing happens...
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398, -- Obtained key item: <keyitem>.
        WARHORSE_HOOFPRINT            = 6388, -- You find the hoofprint of a gigantic warhorse...
        FELLOW_MESSAGE_OFFSET         = 6406, -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        FISHING_MESSAGE_OFFSET        = 6994, -- You can't fish here.
        DIG_THROW_AWAY                = 7007, -- You dig up <item>, but your inventory is full. You regretfully throw the <item> away.
        FIND_NOTHING                  = 7009, -- You dig and you dig, but find nothing.
        FOUND_ITEM_WITH_EASE          = 7084, -- It appears your chocobo found this item with ease.
        BEASTMEN_CACHE_OFFSET         = 7164, -- You discover a cache of beastman resources and receive <number> conquest point[/s]!
        STAGING_GATE_CLOSER           = 7246, -- You must move closer.
        STAGING_GATE_INTERACT         = 7247, -- This gate guards an area under Imperial control.
        STAGING_GATE_MAMOOL           = 7249, -- Mamool Ja Staging Point.
        CANNOT_LEAVE                  = 7341, -- You cannot leave this area while in the possession of <keyitem>.
        RESPONSE                      = 7266, -- There is no response...
        YOU_HAVE_A_BADGE              = 7363, -- You have a %? Let me have a closer look at that...
        HAND_OVER_TO_IMMORTAL         = 7563, -- You hand over the % to the Immortal.
        YOUR_IMPERIAL_STANDING        = 7480, -- Your Imperial Standing has increased!
        HARVESTING_IS_POSSIBLE_HERE   = 7498, -- Harvesting is possible here if you have <item>.
        CANNOT_ENTER                  = 7521, -- You cannot enter at this time. Please wait a while before trying again.
        AREA_FULL                     = 7522, -- This area is fully occupied. You were unable to enter.
        MEMBER_NO_REQS                = 7526, -- Not all of your party members meet the requirements for this objective. Unable to enter area.
        MISSING_KEY_ITEM              = 7611, -- You are not in possession of <keyitem>. Unable to enter area.
        MEMBER_TOO_FAR                = 7530, -- One or more party members are too far away from the entrance. Unable to enter area.
        WELLSPRING                    = 7580, -- The water in this spring is an unusual color...
        SHED_LEAVES                   = 7589, -- The ground is strewn with shed leaves...
        BLOOD_STAINS                  = 7591, -- The ground is smeared with bloodstains...
        DRAWS_NEAR                    = 7616, -- Something draws near!
        HOMEPOINT_SET                 = 7721, -- Home point set!
    },
    mob =
    {
        CHIGOES              =
        {
            ['Marid']        = utils.slice(GetTableOfIDs('Chigoe'), 1, 5), -- Entries 1-5 of the table (1-indexed, inclusive)
            ['Grand_Marid']  = utils.slice(GetTableOfIDs('Chigoe'), 1, 5), -- Entries 1-5 of the table (1-indexed, inclusive)
        },
        DEA                = GetFirstID('Dea'),
        EMERGENT_ELM       = GetFirstID('Emergent_Elm'),
        HARVESTMAN         = GetFirstID('Harvestman'),
        LIVIDROOT_AMOOSHAH = GetFirstID('Lividroot_Amooshah'),
        MAHISHASURA        = GetFirstID('Mahishasura'),
        NIS_PUK            = GetFirstID('Nis_Puk'),
        PLAGUE_CHIGOE      = GetFirstID('Plague_Chigoe'),
    },
    npc =
    {
        HARVESTING = GetTableOfIDs('Harvesting_Point'),
        HOOFPRINT  = GetFirstID('Warhorse_Hoofprint'),
    },
}

return zones[xi.zone.BHAFLAU_THICKETS]
