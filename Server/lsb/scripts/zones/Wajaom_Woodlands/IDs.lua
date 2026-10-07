-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (23 changed, 8 not in the 2007 dialog DAT 6471 and left unchanged).
-----------------------------------
-- Area: Wajaom_Woodlands
-----------------------------------
zones = zones or {}

zones[xi.zone.WAJAOM_WOODLANDS] =
{
    text =
    {
        NOTHING_HAPPENS               = 119,  -- Nothing happens...
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398, -- Obtained key item: <keyitem>.
        WARHORSE_HOOFPRINT            = 6388, -- You find the hoofprint of a gigantic warhorse...
        ITEM_RETURNED                 = 6390, -- The <item> is returned to you.
        NOTHING_OUT_OF_ORDINARY       = 6392, -- There is nothing out of the ordinary here.
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
        PLACE_HYDROGAUGE              = 7279, -- You set the <item> in the glowing trench.
        ENIGMATIC_LIGHT               = 7280, -- The <item> is giving off an enigmatic light.
        LEYPOINT                      = 7335, -- An eerie red glow emanates from this stone platform. The surrounding air feels alive with energy...
        HARVESTING_IS_POSSIBLE_HERE   = 7343, -- Harvesting is possible here if you have <item>.
        WELLSPRING                    = 7380, -- The water in this spring is an unusual color...
        FORGIVE_I_WILL_NOT            = 7385, -- Forgive, I will not. My pet, you hurt!
        GIWAHB_WATCHTOWER_LOCKED      = 7917, -- The door is locked...
        INCREASED_STANDING            = 7918, -- Your Imperial Standing has increased!
        HEADY_FRAGRANCE               = 8421, -- The heady fragrance of wine pervades the air...
        BROKEN_SHARDS                 = 8423, -- Broken shards of insect wing are scattered all over...
        PAMAMA_PEELS                  = 8425, -- Piles of pamama peels litter the ground...
        DRAWS_NEAR                    = 8451, -- Something draws near!
        COMMON_SENSE_SURVIVAL         = 9662, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
        UNITY_WANTED_BATTLE_INTERACT  = 9726, -- Those who have accepted % must pay # Unity accolades to participate. The content for this Wanted battle is #. [Ready to begin?/You do not have the appropriate object set, so your rewards will be limited.]
    },
    mob =
    {
        CHIGOES =
        {
            ['Marid']       = GetTableOfIDs('Chigoe'),
            ['Grand_Marid'] = GetTableOfIDs('Chigoe'),
        },
        JADED_JODY             = GetFirstID('Jaded_Jody'),
        ZORAAL_JAS_PKUUCHA     = GetFirstID('Zoraal_Jas_Pkuucha'),
        PERCIPIENT_ZORAAL_JA   = GetFirstID('Percipient_Zoraal_Ja'),
        VULPANGUE              = GetFirstID('Vulpangue'),
        IRIZ_IMA               = GetFirstID('Iriz_Ima'),
        GOTOH_ZHA_THE_REDOLENT = GetFirstID('Gotoh_Zha_the_Redolent'),
        TINNIN                 = GetFirstID('Tinnin'),
    },
    npc =
    {
        HARVESTING = GetTableOfIDs('Harvesting_Point'),
        HOOFPRINT  = GetFirstID('Warhorse_Hoofprint'),
        WELLSPRING = GetFirstID('Mythralline_Wellspring')
    },
}

return zones[xi.zone.WAJAOM_WOODLANDS]
