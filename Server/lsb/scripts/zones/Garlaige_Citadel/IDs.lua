-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012pc = the 2012 client + PC 2025 import (report 36) by research/tools/lsb_textids_2007.py (1 changed, 12 not in the 2007 dialog DAT 6620 and left unchanged).
-----------------------------------
-- Area: Garlaige Citadel (200)
-----------------------------------
zones = zones or {}

zones[xi.zone.GARLAIGE_CITADEL] =
{
    text =
    {
        CONQUEST_BASE                 = 0,     -- Tallying conquest results...
        REGION_POINTS_SANDORIA        = 65,    -- San d'Oria's region points have increased!
        ITEM_CANNOT_BE_OBTAINED       = 6534,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6537,  -- Obtained: <item>.
        GIL_OBTAINED                  = 6538,  -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6557,  -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6551,  -- There is nothing out of the ordinary here.
        SENSE_OF_FOREBODING           = 6552,  -- You are suddenly overcome with a sense of foreboding...
        FELLOW_MESSAGE_OFFSET         = 6565,  -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7165,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7166,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7167,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        GEOMAGNETRON_ATTUNED          = 7176,  -- Your <keyitem> has been attuned to a geomagnetic fount in the corresponding locale.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7187,  -- Your party is unable to participate because certain members' levels are restricted.
        DEVICE_NOT_WORKING            = 7178,  -- The device is not working.
        SYS_OVERLOAD                  = 7187,  -- Warning! Sys...verload! Enterin...fety mode. ID eras...d.
        YOU_LOST_THE                  = 7192,  -- You lost the <item>.
        SPARKLING_LIGHT               = 7204,  -- The ground is sparkling with a strange light.
        A_GATE_OF_STURDY_STEEL        = 7215,  -- A gate of sturdy steel.
        OPEN_WITH_THE_RIGHT_KEY       = 7221,  -- You might be able to open it with the right key.
        GARLAIGE_KEY_BROKE            = 7222,  -- The <item> broke...
        BANISHING_GATES               = 7230,  -- The first banishing gate begins to open...
        BANISHING_GATES_CLOSING       = 7233,  -- The first banishing gate starts to close.
        YOU_FIND_NOTHING              = 7237,  -- You find nothing special.
        HOLE_IN_THE_CEILING           = 7238,  -- There is a hole in the ceiling.
        PRESENCE_FROM_CEILING         = 7239,  -- You sense a presence from in the ceiling.
        HEAT_FROM_CEILING             = 7240,  -- You feel a terrible heat from the ceiling.
        THE_PRESENCE_MOVES            = 7244,  -- The presence in the ceiling seems to have moved to the east.
        CHEST_UNLOCKED                = 7269,  -- You unlock the chest!
        BOXES_HERE                    = 7279,  -- Boxes are carelessly scattered here.
        BOXES_SCATTERED               = 7280,  -- Boxes are carelessly scattered here. Perhaps you could open them with %.
        FEELS_WRONG                   = 7284,  -- Something feels wrong, but nothing happens.
        ITEMS_ITEMS_LA_LA             = 7388,  -- You can hear a strange voice... Items, items, la la la la la
        GOBLIN_SLIPPED_AWAY           = 7394,  -- The Goblin slipped away when you were not looking...
        YOU_COULD_OPEN_THE_GATE       = 7536,  -- If only you had %, you could open the banishing gate...
        THE_GATE_OPENS_FOR_YOU        = 7537,  -- By the power of your %, the gate opens for you.
        COMBINE_INTO_A_CHUNK          = 7539,  -- You combine the % you have collected into a single chunk.
        PLAYER_OBTAINS_ITEM           = 7454,  -- <name> obtains <item>!
        UNABLE_TO_OBTAIN_ITEM         = 7455,  -- You were unable to obtain the item.
        PLAYER_OBTAINS_TEMP_ITEM      = 7456,  -- <name> obtains the temporary item: <item>!
        ALREADY_POSSESS_TEMP          = 7457,  -- You already possess that temporary item.
        NO_COMBINATION                = 7462,  -- You were unable to enter a combination.
        REGIME_REGISTERED             = 9540,  -- New training regime registered!
        LEARNS_SPELL                  = 11548, -- <name> learns <spell>!
        UNCANNY_SENSATION             = 11550, -- You are assaulted by an uncanny sensation.
        COMMON_SENSE_SURVIVAL         = 11581, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
        UNITY_WANTED_BATTLE_INTERACT  = 11466, -- Those who have accepted % must pay # Unity accolades to participate. The content for this Wanted battle is #. [Ready to begin?/You do not have the appropriate object set, so your rewards will be limited.]
    },
    mob =
    {
        APPARATUS_ELEMENTAL = GetFirstID('Light_Elemental'),
        CHANDELIER          = GetFirstID('Chandelier'),
        GUARDIAN_STATUE     = GetFirstID('Guardian_Statue'),
        HAZMAT              = GetFirstID('Hazmat'),
        HOVERING_HOTPOT     = GetFirstID('Hovering_Hotpot'),
        OLD_TWO_WINGS       = GetFirstID('Old_Two-Wings'),
        MIMIC               = GetFirstID('Mimic'),
        SERKET              = GetFirstID('Serket'),
        SKEWER_SAM          = GetFirstID('Skewer_Sam'),
    },
    npc =
    {
        BANISHING_GATE_OFFSET = GetFirstID('_5k0'),
        CHANDELIER_QM         = GetFirstID('qm15'),
        TREASURE_CHEST        = GetFirstID('Treasure_Chest'),
        TREASURE_COFFER       = GetFirstID('Treasure_Coffer'),
    },
}

return zones[xi.zone.GARLAIGE_CITADEL]
