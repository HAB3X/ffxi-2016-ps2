-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012 = the 2012 client data (report 28) by research/tools/lsb_textids_2007.py (27 changed, 7 not in the 2007 dialog DAT 6670 and left unchanged).
-----------------------------------
-- Area: Kazham
-----------------------------------
zones = zones or {}

zones[xi.zone.KAZHAM] =
{
    text =
    {
        ASSIST_CHANNEL                = 6380,  -- You will be able to use the Assist Channel until #/#/# at #:# (JST).
        ITEM_CANNOT_BE_OBTAINED       = 6375,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378,  -- Obtained: <item>.
        GIL_OBTAINED                  = 6379,  -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398,  -- Obtained key item: <keyitem>.
        CARRIED_OVER_POINTS           = 6434,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 6435,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 6436,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 6456,  -- Your party is unable to participate because certain members' levels are restricted.
        HOMEPOINT_SET                 = 6424,  -- Home point set!
        CONQUEST_BASE                 = 6425,  -- Tallying conquest results...
        FISHING_MESSAGE_OFFSET        = 6584,  -- You can't fish here.
        REGIME_CANCELED               = 6736,  -- Current training regime canceled.
        HUNT_ACCEPTED                 = 6754,  -- Hunt accepted!
        USE_SCYLDS                    = 6755,  -- You use <number> [scyld/scylds]. Scyld balance: <number>.
        HUNT_RECORDED                 = 6766,  -- You record your hunt.
        OBTAIN_SCYLDS                 = 6768,  -- You obtain <number> [scyld/scylds]! Current balance: <number> [scyld/scylds].
        HUNT_CANCELED                 = 6772,  -- Hunt canceled.
        ITEM_DELIVERY_DIALOG          = 9875,  -- We can deliver packages to Mog Houses anywhere in Vana'diel.
        NOT_ENOUGH_GIL                = 9891,  -- You don't have enough gil.
        PAHYALOLOHOIV_SHOP_DIALOG     = 9937,  -- Nothing in this world is crrreated good or evil. However, evil can arrrise when something exists in a place where it did not originally belong.
        TOJIMUMOSULAH_SHOP_DIALOG     = 9939,  -- Things meant to live will live. Things meant to die will die when their time has come. However, this does not mean you should cease your strrruggle for life.
        GHEMISENTERILO_SHOP_DIALOG    = 9961,  -- Can you really get everything that you want on the mainland?
        NUHCELODENKI_SHOP_DIALOG      = 9963,  -- When you die, you can't take anything with you, but what fun is life if you don't have anything to live it up with?
        KHIFORYUHKOWA_SHOP_DIALOG     = 9964,  -- Sometimes a strrrange Hume comes from the south to buy stuff. I wonder what he's doing down there...
        TAHNPOSBEI_SHOP_DIALOG        = 9965,  -- You don't want to get whipped by those Tonberries, do you? Well, have I got the equipment forrr you!
        OPO_OPO                       = 10290, -- Opo-opo!
        IFRIT_UNLOCKED                = 10431, -- You are now able to summon [Ifrit/Titan/Leviathan/Garuda/Shiva/Ramuh].
        NOMAD_MOOGLE_DIALOG           = 10499, -- I'm a traveling moogle, kupo. I help adventurers in the Outlands access items they have stored in a Mog House elsewhere, kupo.
        MAMERIE_SHOP_DIALOG           = 10522, -- Is there something you require?
        EVISCERATION_LEARNED          = 10559, -- You have learned the weapon skill Evisceration!
        SUSPICIOUS_CHARACTERS         = 10578, -- It's my job to look out for suspicious characters coming in on the airships.
        RETRIEVE_DIALOG_ID            = 10909, -- You retrieve <item> from the porter moogle's care.
        COMMON_SENSE_SURVIVAL         = 11885, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
    },
    npc =
    {
        MAGRIFFON = GetFirstID('Magriffon'),
        TIELLEQUE = GetFirstID('Tielleque'),
    },
}

return zones[xi.zone.KAZHAM]
