-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (11 changed, 6 not in the 2007 dialog DAT 6581 and left unchanged).
-----------------------------------
-- Area: Castle_Zvahl_Baileys
-----------------------------------
zones = zones or {}

zones[xi.zone.CASTLE_ZVAHL_BAILEYS] =
{
    text =
    {
        CONQUEST_BASE                 = 0,    -- Tallying conquest results...
        REGION_POINTS_SANDORIA        = 65,   -- San d'Oria's region points have increased!
        ITEM_CANNOT_BE_OBTAINED       = 6534, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6537, -- Obtained: <item>.
        GIL_OBTAINED                  = 6538, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6557, -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6551, -- There is nothing out of the ordinary here.
        SENSE_OF_FOREBODING           = 6552, -- You are suddenly overcome with a sense of foreboding...
        FELLOW_MESSAGE_OFFSET         = 6565, -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7165, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7166, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7167, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7187, -- Your party is unable to participate because certain members' levels are restricted.
        CHEST_UNLOCKED                = 7167, -- You unlock the chest!
        MOBLIN_EARPLUG_ON_THE_GROUND  = 7493, -- You see a Moblin earplug lying on the ground. Could Zeelozok have met his end here...?
        MARQUIS_ATTACKS               = 7494, -- Marquis Andrealphus and his minions attack!
        YOU_FIND_NOTHING              = 7495, -- You find nothing.
        BEGONE_FROM_THESE_HALLS       = 7496, -- Insolent adventurer! Begone from these halls!
        COMMON_SENSE_SURVIVAL         = 7622, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
        MARQUIS_SABNOCK    = GetFirstID('Marquis_Sabnock'),
        LIKHO              = GetFirstID('Likho'),
        MARQUIS_ALLOCEN    = GetFirstID('Marquis_Allocen'),
        MARQUIS_AMON       = GetFirstID('Marquis_Amon'),
        DUKE_HABORYM       = GetFirstID('Duke_Haborym'),
        GRAND_DUKE_BATYM   = GetFirstID('Grand_Duke_Batym'),
        DARK_SPARK         = GetFirstID('Dark_Spark'),
        MIMIC              = GetFirstID('Mimic'),
        MARQUIS_ANDREALPUS = GetFirstID('Marquis_Andrealphus'),
    },
    npc =
    {
        TORCH_OFFSET    = GetFirstID('Torch'),
        TREASURE_CHEST  = GetFirstID('Treasure_Chest'),
        TREASURE_COFFER = GetFirstID('Treasure_Coffer'),
    },
}

return zones[xi.zone.CASTLE_ZVAHL_BAILEYS]
