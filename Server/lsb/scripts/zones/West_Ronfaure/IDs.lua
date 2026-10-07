-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (41 changed, 8 not in the 2007 dialog DAT 6520 and left unchanged).
-----------------------------------
-- Area: West_Ronfaure
-----------------------------------
zones = zones or {}

zones[xi.zone.WEST_RONFAURE] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6378,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6381,  -- Obtained: <item>.
        GIL_OBTAINED                  = 6383,  -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6420,  -- Obtained key item: <keyitem>.
        KEYITEM_LOST                  = 6421,  -- Lost key item: <keyitem>.
        FELLOW_MESSAGE_OFFSET         = 6409,  -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7028,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7029,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7030,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7050,  -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                 = 6997,  -- Tallying conquest results...
        FISHING_MESSAGE_OFFSET        = 7156,  -- You can't fish here.
        DIG_THROW_AWAY                = 7169,  -- You dig up <item>, but your inventory is full. You regretfully throw the <item> away.
        FIND_NOTHING                  = 7171,  -- You dig and you dig, but find nothing.
        FOUND_ITEM_WITH_EASE          = 7246,  -- It appears your chocobo found this item with ease.
        BEASTMEN_CACHE_OFFSET         = 7349,  -- You discover a cache of beastman resources and receive <number> conquest point[/s]!
        RAMAUFONT_DIALOG              = 7248,  -- Nothing to report.
        ORCISH_SCOUTS                 = 7249,  -- Orcish scouts lurk in the shadows. Consider yourself warned!
        ADALEFONT_DIALOG              = 7250,  -- If you sense danger, just flee into the city. I'll not endanger myself on your account!
        LAILLERA_DIALOG               = 7251,  -- I mustn't chat while on duty. Sorry.
        PICKPOCKET_GACHEMAGE          = 7252,  -- A pickpocket? Now that you mention it, I did see a woman flee the city. She ran west.
        PICKPOCKET_ADALEFONT          = 7253,  -- What, someone picked your pocket? And you call yourself an adventurer!
        PICKPOCKET_COLMAIE            = 7254,  -- A pickpocket? Hmm... Can't say I've seen anyone like that around here.
        PICKPOCKET_LAILLERA           = 7255,  -- A pickpocket, you say? I don't think anybody came through here.
        AAVELEON_HEALED               = 7257,  -- My wounds are healed, thanks to you!
        PICKPOCKET_AAVELEON           = 7283,  -- A pickpocket, out here? Phew, my wallet is safe.
        PALCOMONDAU_REPORT            = 7295,  -- Scout reporting! All is quiet on the road to Ghelsba!
        PALCOMONDAU_ENROUTE           = 7296,  -- Let me be! I must patrol the road to Ghelsba.
        PALCOMONDAU_RETURN            = 7297,  -- I bring word of Ghelsba to the Westgate. Out of my way!
        ZOVRIACE_REPORT               = 7298,  -- Scout reporting! All is quiet on the roads to La Theine!
        ZOVRIACE_ENROUTE              = 7299,  -- I must scour the roads to La Theine for signs of the enemy. Let me pass!
        ZOVRIACE_RETURN               = 7300,  -- Let me be! I return to Southgate with word on La Theine.
        PICKPOCKET_PALCOMONDAU        = 7301,  -- A pickpocket? No, I haven't seen anyone matching that description. I've only seen Aaveleon, and a rather brusque woman.
        PICKPOCKET_ZOVRIACE           = 7302,  -- A pickpocket, out here? Can't say I've seen anyone like that. I'll keep my eyes peeled.
        DIADONOUR_DIALOG              = 7303,  -- Our people often fall prey to roving Orcs nearby. Take care out there!
        LAETTE_DIALOG                 = 7308,  -- This watchtower was built to strengthen Ranperre Gate. You can look around, but stay out of our way.
        CHATARRE_DIALOG               = 7309,  -- Ghelsba and its Orcish camps lie at the foot of mountains yonder. We must be vigilant! They could attack at any time.
        DISMAYED_CUSTOMER             = 7326,  -- You find some worthless scraps of paper.
        CONQUEST                      = 7448,  -- You've earned conquest points!
        SOMETHING_IS_AMISS            = 7800,  -- Something is amiss.
        GARRISON_BASE                 = 7830,  -- Hm? What is this? %? How do I know this is not some [San d'Orian/Bastokan/Windurstian] trick?
        TIME_ELAPSED                  = 7959,  -- Time elapsed: <number> [hour/hours] (Vana'diel time) <number> [minute/minutes] and <number> [second/seconds] (Earth time)
        PLAYER_OBTAINS_ITEM           = 7966,  -- <name> obtains <item>!
        UNABLE_TO_OBTAIN_ITEM         = 7967,  -- You were unable to obtain the item.
        PLAYER_OBTAINS_TEMP_ITEM      = 7968,  -- <name> obtains the temporary item: <item>!
        ALREADY_POSSESS_TEMP          = 7969,  -- You already possess that temporary item.
        NO_COMBINATION                = 7974,  -- You were unable to enter a combination.
        REGIME_REGISTERED             = 10336, -- New training regime registered!
        COMMON_SENSE_SURVIVAL         = 12451, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
        FUNGUS_BEETLE      = GetFirstID('Fungus_Beetle'),
        JAGGEDY_EARED_JACK = GetFirstID('Jaggedy-Eared_Jack'),
        MARAUDER_DVOGZOG   = GetFirstID('Marauder_Dvogzog'),
    },
    npc =
    {
        SIGNPOST_OFFSET = GetFirstID('Signpost'),
        OVERSEER_BASE   = GetFirstID('Doladepaiton_RK'),
    },
}

return zones[xi.zone.WEST_RONFAURE]
