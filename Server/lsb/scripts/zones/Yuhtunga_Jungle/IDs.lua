-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012pc = the 2012 client + PC 2025 import (report 36) by research/tools/lsb_textids_2007.py (1 changed, 11 not in the 2007 dialog DAT 6543 and left unchanged).
-----------------------------------
-- Area: Yuhtunga_Jungle
-----------------------------------
zones = zones or {}

zones[xi.zone.YUHTUNGA_JUNGLE] =
{
    text =
    {
        NOTHING_HAPPENS               = 119,   -- Nothing happens...
        ITEM_CANNOT_BE_OBTAINED       = 6375,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378,  -- Obtained: <item>.
        GIL_OBTAINED                  = 6380,  -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398,  -- Obtained key item: <keyitem>.
        KEYITEM_LOST                  = 6399,  -- Lost key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6392,  -- There is nothing out of the ordinary here.
        SENSE_OF_FOREBODING           = 6393,  -- You are suddenly overcome with a sense of foreboding...
        NOW_IS_NOT_THE_TIME           = 6394,  -- Now is not the time for that!
        FELLOW_MESSAGE_OFFSET         = 6406,  -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7006,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028,  -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                 = 6994,  -- Tallying conquest results...
        REGION_POINTS_SANDORIA        = 7059,  -- San d'Oria's region points have increased!
        EXP_FORCE_KILL_SANDORIA       = 7062,  -- San d'Orian E.F. defeats beastmen hordes... Maintain current momentum.
        BEASTMEN_BANNER_CURSE         = 7073,  -- There was a curse on the beastmen's banner!
        BEASTMEN_BANNER_LIFTED        = 7074,  -- The curse of the beastmen's banner has been lifted!
        BEASTMEN_BANNER               = 7075,  -- There is a beastmen's banner.
        CONQUEST                      = 7162,  -- You've earned conquest points!
        FISHING_MESSAGE_OFFSET        = 7495,  -- You can't fish here.
        DIG_THROW_AWAY                = 7508,  -- You dig up <item>, but your inventory is full. You regretfully throw the <item> away.
        FIND_NOTHING                  = 7510,  -- You dig and you dig, but find nothing.
        AMK_DIGGING_OFFSET            = 7576,  -- You spot some familiar footprints. You are convinced that your moogle friend has been digging in the immediate vicinity.
        FOUND_ITEM_WITH_EASE          = 7585,  -- It appears your chocobo found this item with ease.
        BEASTMEN_CACHE_OFFSET         = 7669,  -- You discover a cache of beastman resources and receive <number> conquest point[/s]!
        FLOWER_BLOOMING               = 7593,  -- A large flower is blooming.
        FOUND_NOTHING_IN_FLOWER       = 7596,  -- You find nothing inside the flower.
        FEEL_DIZZY                    = 7597,  -- You feel slightly dizzy. You must have breathed in too much of the pollen.
        SOMETHING_BETTER              = 7610,  -- Don't you have something better to do right now?
        CANNOT_REMOVE_FRAG            = 7613,  -- It is an oddly shaped stone monument. A shining stone is embedded in it, but cannot be removed...
        ALREADY_OBTAINED_FRAG         = 7702,  -- You have already obtained this monument's <keyitem>. Try searching for another.
        ALREADY_HAVE_ALL_FRAGS        = 7615,  -- You have obtained all of the fragments. You must hurry to the ruins of the ancient shrine!
        FOUND_ALL_FRAGS               = 7704,  -- You have obtained <keyitem>! You now have all 8 fragments of light!
        ZILART_MONUMENT               = 7617,  -- It is an ancient Zilart monument.
        TOUCHING_RED_JEWEL            = 7619,  -- Touching the red jewel has infuriated the Opo-opos of the forest. It would be wise to leave immediately.
        MUST_MOVE_CLOSER              = 7719,  -- You will have to move closer to remove the <keyitem>.
        THE_OPO_OPOS_ATTACK           = 7633,  -- The Opo-opos attack!
        LOGGING_IS_POSSIBLE_HERE      = 7634,  -- Logging is possible here if you have <item>.
        HARVESTING_IS_POSSIBLE_HERE   = 7641,  -- Harvesting is possible here if you have <item>.
        SOMETHING_IS_BURIED_HERE      = 7684,  -- It looks like something is buried here. If you had <item> you could dig it up.
        GARRISON_BASE                 = 7711,  -- Hm? What is this? %? How do I know this is not some [San d'Orian/Bastokan/Windurstian] trick?
        SWARM_APPEARED                = 7757,  -- A swarm has appeared!
        TIME_ELAPSED                  = 7776,  -- Time elapsed: <number> [hour/hours] (Vana'diel time) <number> [minute/minutes] and <number> [second/seconds] (Earth time)
        PLAYER_OBTAINS_ITEM           = 7797,  -- <name> obtains <item>!
        UNABLE_TO_OBTAIN_ITEM         = 7798,  -- You were unable to obtain the item.
        PLAYER_OBTAINS_TEMP_ITEM      = 7799,  -- <name> obtains the temporary item: <item>!
        ALREADY_POSSESS_TEMP          = 7800,  -- You already possess that temporary item.
        NO_COMBINATION                = 7805,  -- You were unable to enter a combination.
        UNITY_WANTED_BATTLE_INTERACT  = 11979, -- Those who have accepted % must pay # Unity accolades to participate. The content for this Wanted battle is #. [Ready to begin?/You do not have the appropriate object set, so your rewards will be limited.]
        REGIME_REGISTERED             = 9961,  -- New training regime registered!
        COMMON_SENSE_SURVIVAL         = 12066, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
        BAYAWAK                = GetFirstID('Bayawak'),
        CARTHI                 = GetFirstID('Carthi'),
        DEMISAHAGIN_BARD       = GetFirstID('Demisahagin_Bard'),
        DEMISAHAGIN_DRAGOON    = GetFirstID('Demisahagin_Dragoon'),
        DEMISAHAGIN_MONK       = GetFirstID('Demisahagin_Monk'),
        DEMISAHAGIN_WHITE_MAGE = GetFirstID('Demishagin_White_Mage'), -- Demishagin name typo is retail accurate
        HOBGOBLIN_BEASTMASTER  = GetFirstID('Hobgoblin_Beastmaster'),
        HOBGOBLIN_BLACK_MAGE   = GetFirstID('Hobgoblin_Black_Mage'),
        HOBGOBLIN_DARK_KNIGHT  = GetFirstID('Hobgoblin_Dark_Knight'),
        HOBGOBLIN_RANGER       = GetFirstID('Hobgoblin_Ranger'),
        HOBGOBLIN_RED_MAGE     = GetFirstID('Hobgoblin_Red_Mage'),
        HOBGOBLIN_THIEF        = GetFirstID('Hobgoblin_Thief'),
        HOBGOBLIN_WARRIOR      = GetFirstID('Hobgoblin_Warrior'),
        HOBGOBLIN_WHITE_MAGE   = GetFirstID('Hobgoblin_White_Mage'),
        MISCHIEVOUS_MICHOLAS   = GetFirstID('Mischievous_Micholas'),
        NASUS_OFFSET           = GetFirstID('Nasus'),
        ROSE_GARDEN            = GetFirstID('Rose_Garden'),
        SIREN                  = GetFirstID('Siren'),
        TIPHA                  = GetFirstID('Tipha'),
        VOLUPTUOUS_VILMA       = GetFirstID('Voluptuous_Vilma'),
    },
    npc =
    {
        BEASTMENS_BANNER         = GetFirstID('Beastmens_Banner'),
        BEASTMEN_TREASURE_OFFSET = GetFirstID('qm3'),
        BLUE_RAFFLESIA_OFFSET    = GetFirstID('Blue_Rafflesia'),
        CERMET_HEADSTONE         = GetFirstID('Cermet_Headstone'),
        OVERSEER_BASE            = GetFirstID('Zorchorevi_RK'),
        PEDDLESTOX               = GetFirstID('Peddlestox'),
        TUNING_OUT_QM            = GetFirstID('qm2'),

        HARVESTING = GetTableOfIDs('Harvesting_Point'),
        LOGGING    = GetTableOfIDs('Logging_Point'),
    },
}

return zones[xi.zone.YUHTUNGA_JUNGLE]
