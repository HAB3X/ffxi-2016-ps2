-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (22 changed, 6 not in the 2007 dialog DAT 6454 and left unchanged).
-----------------------------------
-- Area: Grand_Palace_of_HuXzoi
-----------------------------------
zones = zones or {}

zones[xi.zone.GRAND_PALACE_OF_HUXZOI] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398, -- Obtained key item: <keyitem>.
        CARRIED_OVER_POINTS           = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                 = 7016, -- Tallying conquest results...
        DOES_NOT_RESPOND              = 7180, -- The gate does not respond...
        PRESENCE_HAS_DRAWN            = 7296, -- Your presence has drawn unwanted attention!
        NOTHING_LEFT_TO_DO            = 7299, -- You have nothing left to do here.
        REQUEST_CONFIRMED             = 7301, -- Security portal access request confirmed. Commencing patrol routine. Stay on alert for intruder interference.
        PATROL_COMPLETED              = 7302, -- Patrol routine completed. Request transfer of final security portal access duty. Awaiting confirmation.
        DUTY_COMPLETE                 = 7303, -- Transfer of final security portal access duty complete.
        TRANSFER_OF_ACCESS_DUTY       = 7304, -- Transfer of access duty complete.
        RETURNING_TO_REGULAR_DUTIES   = 7305, -- Returning to regular duties.
        PORTAL_EAST                   = 7306, -- You hear a portal open to the east...
        PORTAL_WEST                   = 7307, -- You hear a portal open to the west...
        PORTAL_NORTH                  = 7308, -- You hear a portal open to the north...
        TIME_EXCEEDED                 = 7309, -- Patrol routine time restriction exceeded. Patrol aborted.
        PATROL_SUSPENDED              = 7310, -- Patrol suspended. Awaiting orders.
        RECOMMENCING_PATROL           = 7311, -- Recommencing patrol.
        RECENTLY_ACTIVATED            = 7312, -- The alcove has recently been activated...
        TIME_RESTRICTION              = 7313, -- Time restriction: <number> [minute/minutes] (Earth time)
        QUASILUMIN_MAP_QUEST_OFFSET   = 7314, -- Warning. Chamber of Eventide accessed by unauthorized personnel, 4789209-980 increments previous.
        IXAERN_MNK_QM                 = 7325, -- You hear something vaguely resembling a voice emanating from the depths of your soul. Bring me...aer...reccceptac...
        HOMEPOINT_SET                 = 7477, -- Home point set!
    },
    mob =
    {
        JAILER_OF_TEMPERANCE_PH = utils.slice(GetTableOfIDs('Eozdei_Still'), 1, 5), -- Entries 1-5 of the table (1-indexed, inclusive)
        IXGHRAH                 = GetFirstID('Ixghrah'),
        JAILER_OF_TEMPERANCE    = GetFirstID('Jailer_of_Temperance'),
        IXAERN_MNK              = GetFirstID('Ixaern_MNK'),
        EOGHRAH_BIRD            = utils.slice(GetTableOfIDs('Eoghrah'), 1, 38),
        EOGHRAH_SPIDER          = utils.slice(GetTableOfIDs('Eoghrah'), 39),
    },
    npc =
    {
        QM_IXAERN_MNK        = GetFirstID('qm_ixaern_mnk'),
        QUASILUMIN_OFFSET    = GetFirstID('Quasilumin'),
        ESCORT_1_DOOR_OFFSET = GetFirstID('_0y6'),
        ESCORT_2_DOOR_OFFSET = GetFirstID('_iyn'),
        ESCORT_3_DOOR_OFFSET = GetFirstID('_iyk'),
        ESCORT_4_DOOR_OFFSET = GetFirstID('_iyd'),
        CERMET_ALCOVE_OFFSET = GetFirstID('Cermet_Alcove'),
    },
}

return zones[xi.zone.GRAND_PALACE_OF_HUXZOI]
