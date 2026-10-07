-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (40 changed, 15 not in the 2007 dialog DAT 6535 and left unchanged).
-----------------------------------
-- Area: West_Sarutabaruta
-----------------------------------
zones = zones or {}

zones[xi.zone.WEST_SARUTABARUTA] =
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
        FELLOW_MESSAGE_OFFSET         = 6406,  -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7006,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028,  -- Your party is unable to participate because certain members' levels are restricted.
        FISHING_MESSAGE_OFFSET        = 6994,  -- You can't fish here.
        DIG_THROW_AWAY                = 7007,  -- You dig up <item>, but your inventory is full. You regretfully throw the <item> away.
        FIND_NOTHING                  = 7009,  -- You dig and you dig, but find nothing.
        FOUND_ITEM_WITH_EASE          = 7084,  -- It appears your chocobo found this item with ease.
        BEASTMEN_CACHE_OFFSET         = 7168,  -- You discover a cache of beastman resources and receive <number> conquest point[/s]!
        CONQUEST_BASE                 = 7086,  -- Tallying conquest results...
        SIGN_1                        = 7314,  -- Northeast: Central Tower, Horutoto Ruins Northwest: Giddeus South: Port Windurst
        SIGN_3                        = 7315,  -- East: East Sarutabaruta West: Giddeus
        SIGN_5                        = 7316,  -- Northeast: Central Tower, Horutoto Ruins East: East Sarutabaruta West: Giddeus
        SIGN_7                        = 7317,  -- South: Windurst East: East Sarutabaruta
        SIGN_9                        = 7318,  -- West: Giddeus North: East Sarutabaruta South: Windurst
        SIGN_11                       = 7319,  -- North: East Sarutabaruta Southeast: Windurst
        SIGN_13                       = 7320,  -- East: Port Windurst West: West Tower, Horutoto Ruins
        SIGN_15                       = 7321,  -- East: East Sarutabaruta West: Giddeus Southeast: Windurst
        SIGN_17                       = 7322,  -- Northwest: Northwest Tower, Horutoto Ruins East: Outpost Southwest: Giddeus
        PAORE_KUORE_DIALOG            = 7324,  -- Welcome to Windurst! Proceed through this gateway to entaru Port Windurst.
        KOLAPO_OILAPO_DIALOG          = 7325,  -- Hi-diddly-diddly! This is the gateway to Windurst! The grasslands you're on now are known as West Sarutabaruta.
        MAATA_ULAATA                  = 7326,  -- Hello-wello! This is the central tower of the Horutoto Ruins. It's one of the several ancient-wancient magic towers which dot these grasslands.
        COME_FROM_THE_ORASTERY        = 7327,  -- I am Fuahah. I've come from the Orastery's Mage Academy to investigate the Horutoto Ruins.
        FERAL_CARDIANS                = 7328,  -- Beneath this magic tower lurk some of the feral Cardians that have escaped from the care of the Manustery. So be very-wery careful down there!
        IPUPU_DIALOG                  = 7329,  -- I decided to take a little strolly-wolly, but before I realized it, I found myself way out here! Now I am sorta stuck... Woe is me!
        FROST_DEPOSIT_TWINKLES        = 7336,  -- A frost deposit at the base of the tree twinkles in the starlight.
        MELT_BARE_HANDS               = 7338,  -- It looks like it would melt if you touched it with your bare hands...
        HARVESTING_IS_POSSIBLE_HERE   = 7374,  -- Harvesting is possible here if you have <item>.
        CONQUEST                      = 7390,  -- You've earned conquest points!
        GARRISON_BASE                 = 7744,  -- Hm? What is this? %? How do I know this is not some [San d'Orian/Bastokan/Windurstian] trick?
        PLAYER_OBTAINS_ITEM           = 7791,  -- <name> obtains <item>!
        UNABLE_TO_OBTAIN_ITEM         = 7792,  -- You were unable to obtain the item.
        PLAYER_OBTAINS_TEMP_ITEM      = 7793,  -- <name> obtains the temporary item: <item>!
        ALREADY_POSSESS_TEMP          = 7794,  -- You already possess that temporary item.
        NO_COMBINATION                = 7799,  -- You were unable to enter a combination.
        VOIDWALKER_DESPAWN            = 7830,  -- The monster fades before your eyes, a look of disappointment on its face.
        REGIME_REGISTERED             = 10116, -- New training regime registered!
        DONT_SWAP_JOBS                = 10117, -- Changing your job will result in the cancellation of your current training regime.
        REGIME_CANCELED               = 10118, -- Training regime canceled.
        VOIDWALKER_NO_MOB             = 11370, -- The <keyitem> quivers ever so slightly, but emits no light. There seem to be no monsters in the area.
        VOIDWALKER_MOB_TOO_FAR        = 11371, -- The <keyitem> quivers ever so slightly and emits a faint light. There seem to be no monsters in the immediate vicinity.
        VOIDWALKER_MOB_HINT           = 11372, -- The <keyitem> resonates [feebly/softly/solidly/strongly/very strongly/furiously], sending a radiant beam of light lancing towards a spot roughly <number> [yalm/yalms] [east/southeast/south/southwest/west/northwest/north/northeast] of here.
        VOIDWALKER_SPAWN_MOB          = 11277, -- A monster materializes out of nowhere!
        VOIDWALKER_UPGRADE_KI_1       = 11375, -- The <keyitem> takes on a slightly deeper hue and becomes <keyitem>!
        VOIDWALKER_UPGRADE_KI_2       = 11376, -- The <keyitem> takes on a deeper, richer hue and becomes <keyitem>!
        VOIDWALKER_BREAK_KI           = 11377, -- The <keyitem> shatters into tiny fragments.
        VOIDWALKER_OBTAIN_KI          = 11378, -- Obtained key item: <keyitem>!
        COMMON_SENSE_SURVIVAL         = 12361, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },

    mob =
    {
        NUNYENUNC   = GetFirstID('Nunyenunc'),
        TOM_TIT_TAT = GetTableOfIDs('Tom_Tit_Tat'),
        VOIDWALKER  =
        {
            [xi.keyItem.CLEAR_ABYSSITE] =
            {
                17248624, -- Raker bee
                17248623, -- Raker bee
                17248622, -- Raker bee
                17248621, -- Raker bee
                17248620,  -- Rummager beetle
                17248619,  -- Rummager beetle
                17248618,  -- Rummager beetle
                17248617,  -- Rummager beetle
            },

            [xi.keyItem.COLORFUL_ABYSSITE] =
            {
                17248616,  -- Jyeshtha
                17248615, -- Farruca Fly
            },

            [xi.keyItem.BROWN_ABYSSITE] =
            {
                17248614, -- Orcus
            },

            [xi.keyItem.BLACK_ABYSSITE] =
            {
                17248613, -- Yilbegan
            },
        }
    },

    npc =
    {
        SIGNPOST_OFFSET = GetFirstID('Signpost'),
        OVERSEER_BASE   = GetFirstID('Naguipeillont_RK'),
        HARVESTING      = GetTableOfIDs('Harvesting_Point'),
    },
}

return zones[xi.zone.WEST_SARUTABARUTA]
