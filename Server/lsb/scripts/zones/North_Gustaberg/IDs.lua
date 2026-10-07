-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (29 changed, 16 not in the 2007 dialog DAT 6526 and left unchanged).
-----------------------------------
-- Area: North_Gustaberg
-----------------------------------
zones = zones or {}

zones[xi.zone.NORTH_GUSTABERG] =
{
    text =
    {
        CONQUEST_BASE                 = 0,     -- Tallying conquest results...
        NOTHING_HAPPENS               = 281,   -- Nothing happens...
        ITEM_CANNOT_BE_OBTAINED_TWICE = 6567,  -- You cannot obtain any more.
        ITEM_CANNOT_BE_OBTAINED       = 6537,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        FULL_INVENTORY_AFTER_TRADE    = 6539,  -- You cannot obtain the <item>. Try trading again after sorting your inventory.
        ITEM_OBTAINED                 = 6540,  -- Obtained: <item>.
        GIL_OBTAINED                  = 6542,  -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6579,  -- Obtained key item: <keyitem>.
        KEYITEM_LOST                  = 6580,  -- Lost key item: <keyitem>.
        ITEMS_OBTAINED                = 6549,  -- You obtain <number> <item>!
        NOTHING_OUT_OF_ORDINARY       = 6554,  -- There is nothing out of the ordinary here.
        FELLOW_MESSAGE_OFFSET         = 6568,  -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7187,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7188,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7189,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7209,  -- Your party is unable to participate because certain members' levels are restricted.
        FISHING_MESSAGE_OFFSET        = 7156,  -- You can't fish here.
        DIG_THROW_AWAY                = 7169,  -- You dig up <item>, but your inventory is full. You regretfully throw the <item> away.
        FIND_NOTHING                  = 7171,  -- You dig and you dig, but find nothing.
        FOUND_ITEM_WITH_EASE          = 7246,  -- It appears your chocobo found this item with ease.
        BEASTMEN_CACHE_OFFSET         = 7349,  -- You discover a cache of beastman resources and receive <number> conquest point[/s]!
        SENSE_EVIL_PRESENCE           = 7251,  -- You sense an evil presence...
        SPARKLING_LIGHT               = 7292,  -- The ground is sparkling with a strange light.
        SHINING_OBJECT_SLIPS_AWAY     = 7355,  -- The shining object slips through your fingers and is washed further down the stream.
        REACH_WATER_FROM_HERE         = 7362,  -- You can reach the water from here.
        CONQUEST                      = 7398,  -- You've earned conquest points!
        ITEMS_ITEMS_LA_LA             = 7750,  -- You can hear a strange voice... Items, items, la la la la la
        GOBLIN_SLIPPED_AWAY           = 7756,  -- The Goblin slipped away when you were not looking...
        GARRISON_BASE                 = 7766,  -- Hm? What is this? %? How do I know this is not some [San d'Orian/Bastokan/Windurstian] trick?
        PLAYER_OBTAINS_ITEM           = 7981,  -- <name> obtains <item>!
        UNABLE_TO_OBTAIN_ITEM         = 7982,  -- You were unable to obtain the item.
        PLAYER_OBTAINS_TEMP_ITEM      = 7983,  -- <name> obtains the temporary item: <item>!
        ALREADY_POSSESS_TEMP          = 7984,  -- You already possess that temporary item.
        NO_COMBINATION                = 7989,  -- You were unable to enter a combination.
        VOIDWALKER_DESPAWN            = 8020,  -- The monster fades before your eyes, a look of disappointment on its face.
        TIME_ELAPSED                  = 8096,  -- Time elapsed: <number> [hour/hours] (Vana'diel time) <number> [minute/minutes] and <number> [second/seconds] (Earth time)
        REGIME_REGISTERED             = 10307, -- New training regime registered!
        VOIDWALKER_NO_MOB             = 11539, -- The <keyitem> quivers ever so slightly, but emits no light. There seem to be no monsters in the area.
        VOIDWALKER_MOB_TOO_FAR        = 11540, -- The <keyitem> quivers ever so slightly and emits a faint light. There seem to be no monsters in the immediate vicinity.
        VOIDWALKER_MOB_HINT           = 11541, -- The <keyitem> resonates [feebly/softly/solidly/strongly/very strongly/furiously], sending a radiant beam of light lancing towards a spot roughly <number> [yalm/yalms] [east/southeast/south/southwest/west/northwest/north/northeast] of here.
        VOIDWALKER_SPAWN_MOB          = 11427, -- A monster materializes out of nowhere!
        VOIDWALKER_UPGRADE_KI_1       = 11544, -- The <keyitem> takes on a slightly deeper hue and becomes <keyitem>!
        VOIDWALKER_UPGRADE_KI_2       = 11545, -- The <keyitem> takes on a deeper, richer hue and becomes <keyitem>!
        VOIDWALKER_BREAK_KI           = 11546, -- The <keyitem> shatters into tiny fragments.
        VOIDWALKER_OBTAIN_KI          = 11547, -- Obtained key item: <keyitem>!
        COMMON_SENSE_SURVIVAL         = 12493, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
        STINGING_SOPHIE     = GetTableOfIDs('Stinging_Sophie'), -- 2 NMs
        MAIGHDEAN_UAINE     = GetFirstID('Maighdean_Uaine'), -- TODO: PH Audit, 2 NMs
        GAMBILOX_WANDERLING = GetFirstID('Gambilox_Wanderling'),

        VOIDWALKER =
        {
            [xi.keyItem.CLEAR_ABYSSITE] =
            {
                17211881, -- Globster
                17211880, -- Globster
                17211879, -- Globster
                17211878, -- Globster
                17211877, -- Ground Guzzler
                17211876, -- Ground Guzzler
                17211875, -- Ground Guzzler
                17211874, -- Ground Guzzler
            },

            [xi.keyItem.COLORFUL_ABYSSITE] =
            {
                17211873, -- Lamprey Lord
                17211872,  -- Shoggoth
            },

            [xi.keyItem.ORANGE_ABYSSITE] =
            {
                17211865  -- Blobdingnag
            },

            [xi.keyItem.BLACK_ABYSSITE] =
            {
                17211864  -- Yilbegan
            }
        }
    },

    pet =
    {
        [17211865] = -- Blobdingnag
        {
            17211871, -- Septic Boils
            17211870, -- Septic Boils
            17211869, -- Septic Boils
            17211868, -- Septic Boils
            17211867, -- Septic Boils
            17211866, -- Septic Boils
        },
    },

    npc =
    {
        OVERSEER_BASE  = GetFirstID('Ennigreaud_RK'),
        SIRENS_TEAR_QM = GetFirstID('qm1'),
    },

    positions =
    {
        sirensTear =
        {
            [1] = { 310.445, 1.511, 323.755 },
            [2] = { 290.113, 1.877, 319.272 },
            [3] = { 330.155, 1.929, 159.144 },
            [4] = { 349.703, 1.938, 162.502 },
            [5] = { 340.213, 2.869, 223.788 },
        }
    },
}

return zones[xi.zone.NORTH_GUSTABERG]
