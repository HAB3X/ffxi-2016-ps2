-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012pc = the 2012 client + PC 2025 import (report 36) by research/tools/lsb_textids_2007.py (1 changed, 6 not in the 2007 dialog DAT 6527 and left unchanged).
-----------------------------------
-- Area: South_Gustaberg
-----------------------------------
zones = zones or {}

zones[xi.zone.SOUTH_GUSTABERG] =
{
    text =
    {
        NOTHING_HAPPENS               = 122,   -- Nothing happens...
        ITEM_CANNOT_BE_OBTAINED       = 6378,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6381,  -- Obtained: <item>.
        GIL_OBTAINED                  = 6383,  -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6420,  -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6395,  -- There is nothing out of the ordinary here.
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
        MONSTER_TRACKS                = 7317,  -- You see monster tracks on the ground.
        MONSTER_TRACKS_FRESH          = 7318,  -- You see fresh monster tracks on the ground.
        NOTHING_SEEMS_HAPPENING       = 7319,  -- Nothing seems to be happening.
        YOU_PUT_ITEM_DOWN             = 7320,  -- You put <item> down.
        FIRE_GOOD                     = 7321,  -- The fire seems to be good enough for cooking.
        FIRE_PUT                      = 7322,  -- You put <item> in the fire.
        FIRE_TAKE                     = 7323,  -- You take <item> out of the fire.
        FIRE_LONGER                   = 7324,  -- It may take a little while more to cook the <item>.
        MEAT_ALREADY_PUT              = 7325,  -- The <item> is already in the fire.
        ITEMS_ITEMS_LA_LA             = 7422,  -- You can hear a strange voice... Items, items, la la la la la
        GOBLIN_SLIPPED_AWAY           = 7428,  -- The Goblin slipped away when you were not looking...
        PLAYER_OBTAINS_ITEM           = 7442,  -- <name> obtains <item>!
        UNABLE_TO_OBTAIN_ITEM         = 7443,  -- You were unable to obtain the item.
        PLAYER_OBTAINS_TEMP_ITEM      = 7444,  -- <name> obtains the temporary item: <item>!
        ALREADY_POSSESS_TEMP          = 7445,  -- You already possess that temporary item.
        NO_COMBINATION                = 7450,  -- You were unable to enter a combination.
        UNITY_WANTED_BATTLE_INTERACT  = 11885, -- Those who have accepted % must pay # Unity accolades to participate. The content for this Wanted battle is #. [Ready to begin?/You do not have the appropriate object set, so your rewards will be limited.]
        TIME_ELAPSED                  = 7572,  -- Time elapsed: <number> [hour/hours] (Vana'diel time) <number> [minute/minutes] and <number> [second/seconds] (Earth time)
        REGIME_REGISTERED             = 9785,  -- New training regime registered!
    },
    mob =
    {
        CARNERO       = GetTableOfIDs('Carnero'),
        LEAPING_LIZZY = GetTableOfIDs('Leaping_Lizzy'),
        BUBBLY_BERNIE = GetFirstID('Bubbly_Bernie'),
    },
    npc =
    {
    },
}

return zones[xi.zone.SOUTH_GUSTABERG]
