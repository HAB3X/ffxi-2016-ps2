-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (12 changed, 6 not in the 2007 dialog DAT 6447 and left unchanged).
-----------------------------------
-- Area: Phomiuna_Aqueducts
-----------------------------------
zones = zones or {}

zones[xi.zone.PHOMIUNA_AQUEDUCTS] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398, -- Obtained key item: <keyitem>.
        NOTHING_OUT_HERE              = 6392, -- There is nothing out of the ordinary here.
        CARRIED_OVER_POINTS           = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                 = 6994, -- Tallying conquest results...
        CANNOT_REACH_LADDER           = 7155, -- You cannot reach the ladder from here.
        DOOR_SEALED_SHUT              = 7156, -- The door above you is sealed shut.
        DOOR_FIRMLY_SHUT              = 7157, -- The door is firmly shut.
        DOOR_LOCKED                   = 7158, -- The door is locked. You might be able to open it with %.
        ITEM_BREAKS                   = 7160, -- The <item> breaks!
        LAMP_OFFSET                   = 7164, -- A symbol for fire is engraved on the base of the lamp...
        FISHING_MESSAGE_OFFSET        = 7177, -- You can't fish here.
        COMMON_SENSE_SURVIVAL         = 7433, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
        EBA               = GetFirstID('Eba'),
        FOMOR_BARD        = GetTableOfIDs('Fomor_Bard'),
        FOMOR_BLACK_MAGE  = GetTableOfIDs('Fomor_Black_Mage'),
        FOMOR_DARK_KNIGHT = GetTableOfIDs('Fomor_Dark_Knight'),
        FOMOR_DRAGOON     = GetTableOfIDs('Fomor_Dragoon'),
        FOMOR_MONK        = GetTableOfIDs('Fomor_Monk'),
        FOMOR_NINJA       = GetTableOfIDs('Fomor_Ninja'),
        FOMOR_PALADIN     = GetTableOfIDs('Fomor_Paladin'),
        FOMOR_RANGER      = GetTableOfIDs('Fomor_Ranger'),
        FOMOR_RED_MAGE    = GetTableOfIDs('Fomor_Red_Mage'),
        FOMOR_SAMURAI     = GetTableOfIDs('Fomor_Samurai'),
        FOMOR_SUMMONER    = GetTableOfIDs('Fomor_Summoner'),
        FOMOR_THIEF       = GetTableOfIDs('Fomor_Thief'),
        FOMOR_WARRIOR     = GetTableOfIDs('Fomor_Warrior'),
        MAHISHA           = GetFirstID('Mahisha'),
        TRES_DUENDES      = GetFirstID('Tres_Duendes'),
    },
    npc =
    {
        LADDER_KNOCKING       = GetTableOfIDs('Wooden_Ladder')[4], -- 4th Wooden Ladder on the list
        QM_TAVNAZIAN_COOKBOOK = GetFirstID('qm_tavnazian_cookbook'),
    },
}

return zones[xi.zone.PHOMIUNA_AQUEDUCTS]
