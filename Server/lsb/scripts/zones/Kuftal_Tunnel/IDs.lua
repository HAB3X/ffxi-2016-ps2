-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012pc = the 2012 client + PC 2025 import (report 36) by research/tools/lsb_textids_2007.py (1 changed, 6 not in the 2007 dialog DAT 6594 and left unchanged).
-----------------------------------
-- Area: Kuftal_Tunnel
-----------------------------------
zones = zones or {}

zones[xi.zone.KUFTAL_TUNNEL] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378,  -- Obtained: <item>.
        GIL_OBTAINED                  = 6379,  -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398,  -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6392,  -- There is nothing out of the ordinary here.
        FELLOW_MESSAGE_OFFSET         = 6406,  -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7006,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028,  -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                 = 6994,  -- Tallying conquest results...
        REGION_POINTS_SANDORIA        = 7059,  -- San d'Oria's region points have increased!
        FISHING_MESSAGE_OFFSET        = 7153,  -- You can't fish here.
        CHEST_UNLOCKED                = 7252,  -- You unlock the chest!
        DO_NOT_SEE_ANYTHING           = 7267,  -- You do not see anything out of the ordinary.
        FELL                          = 7270,  -- The piece of wood fell off the cliff!
        EVIL                          = 7271,  -- You sense an evil presence...
        FISHBONES                     = 7285,  -- Fish bones lie scattered about the area...
        SENSE_OMINOUS_PRESENCE        = 7287,  -- You sense an ominous presence...
        REGIME_REGISTERED             = 10271, -- New training regime registered!
        PLAYER_OBTAINS_ITEM           = 11323, -- <name> obtains <item>!
        UNABLE_TO_OBTAIN_ITEM         = 11324, -- You were unable to obtain the item.
        PLAYER_OBTAINS_TEMP_ITEM      = 11325, -- <name> obtains the temporary item: <item>!
        ALREADY_POSSESS_TEMP          = 11326, -- You already possess that temporary item.
        NO_COMBINATION                = 11331, -- You were unable to enter a combination.
        COMMON_SENSE_SURVIVAL         = 11444, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
        UNITY_WANTED_BATTLE_INTERACT  = 11363, -- Those who have accepted % must pay # Unity accolades to participate. The content for this Wanted battle is #. [Ready to begin?/You do not have the appropriate object set, so your rewards will be limited.]
    },
    mob =
    {
        AMEMET               = GetFirstID('Amemet'),
        ARACHNE              = GetFirstID('Arachne'),
        BLOODTHIRSTER_MADKIX = GetFirstID('Bloodthirster_Madkix'),
        PELICAN              = GetFirstID('Pelican'),
        SABOTENDER_MARIACHI  = GetFirstID('Sabotender_Mariachi'),
        YOWIE                = GetFirstID('Yowie'),
        TALEKEEPER_OFFSET    = GetFirstID('Gordovs_Ghost'),
        MIMIC                = GetFirstID('Mimic'),
        CANCER               = GetFirstID('Cancer'),
        PHANTOM_WORM         = GetFirstID('Phantom_Worm'),
        GUIVRE               = GetFirstID('Guivre'),
        KETTENKAEFER         = GetFirstID('Kettenkaefer'),
    },
    npc =
    {
        PHANTOM_WORM_QM = GetFirstID('qm1'),
        DOOR_ROCK       = GetFirstID('_4u0'),
        TREASURE_COFFER = GetFirstID('Treasure_Coffer'),
    },
}

return zones[xi.zone.KUFTAL_TUNNEL]
