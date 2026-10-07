-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (10 changed, 6 not in the 2007 dialog DAT 6595 and left unchanged).
-----------------------------------
-- Area: The_Eldieme_Necropolis_[S]
-----------------------------------
zones = zones or {}

zones[xi.zone.THE_ELDIEME_NECROPOLIS_S] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6380, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398, -- Obtained key item: <keyitem>.
        CARRIED_OVER_POINTS           = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        LAYTON_SHOP_DIALOG            = 7048, -- Might you be a student of the same field as I? If that is the case, I might be able to provide you with the proper grimoires...at a price, of course.
        CAMPAIGN_RESULTS_TALLIED      = 7443, -- Campaign results tallied.
        SARCOPHAGUS_SEALED            = 7542, -- It is a stone sarcophagus with the lid sealed tight. It cannot be opened.
        NAMES_CARVED_ON_STONE         = 7543, -- The names of the deceased in this area are carved upon the stone.
        YOU_CAN_NOW_BECOME_A_SCHOLAR  = 7657, -- You can now become a scholar!
        YOU_LEARN_EMBRAVA_AND_KAUSTRA = 7841, -- <name> learns Embrava and Kaustra!
        ITEM_DELIVERY_DIALOG          = 7847, -- Have something to send?
        COMMON_SENSE_SURVIVAL         = 8953, -- It appears that you have arrived at a new survival guide provided by the Servicemen's Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
    },
    npc =
    {
        CAMPAIGN_NPC_OFFSET = GetFirstID('Renvriche_TK'), -- San, Bas, Win, Flag +4, CA
    },
}

return zones[xi.zone.THE_ELDIEME_NECROPOLIS_S]
