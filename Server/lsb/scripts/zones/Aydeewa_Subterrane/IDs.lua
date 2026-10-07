-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012pc = the 2012 client + PC 2025 import (report 36) by research/tools/lsb_textids_2007.py (1 changed, 6 not in the 2007 dialog DAT 6488 and left unchanged).
-----------------------------------
-- Area: Aydeewa_Subterrane
-----------------------------------
zones = zones or {}

zones[xi.zone.AYDEEWA_SUBTERRANE] =
{
    text =
    {
        NOTHING_HAPPENS               = 119,  -- Nothing happens...
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398, -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6392, -- There is nothing out of the ordinary here.
        FELLOW_MESSAGE_OFFSET         = 6406, -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        FISHING_MESSAGE_OFFSET        = 6994, -- You can't fish here.
        MINING_IS_POSSIBLE_HERE       = 7257, -- Mining is possible here if you have <item>.
        MUSHROOM_NEEDS_FERTILIZER     = 7341, -- There is a mushroom growing here. It might grow larger if it had some fertilizer.
        MUSHROOM_IS_GROWING_HERE      = 7342, -- There is a mushroom growing here.
        TRACES_OF_MUSHROOMS           = 7343, -- There are traces indicating that a mushroom was growing here.
        MONSTER_MUSHROOM_SPROUTS      = 7344, -- The mushroom has grown into a monster!
        MUSHROOM_HAS_GROWN            = 7345, -- The mushroom seems to have grown a bit.
        NO_MORE_FERTILIZER            = 7346, -- The mushroom does not need any more fertilizer now.
        NOTHING_HAPPENS_2             = 7347, -- Nothing happens.
        PULL_UP_MUSHROOM_1            = 7348, -- You pull up the mushroom and obtain <item>!
        PULL_UP_MUSHROOM_2            = 7349, -- You pull up the mushroom and obtain <item>!
        PULL_UP_MUSHROOM_3            = 7350, -- You pull up the mushroom and obtain <item>!
        PULL_UP_MUSHROOM_4            = 7351, -- You pull up the mushroom and obtain <item>!
        NO_MORE_SPROUTS               = 7634, -- However, you cannot carry any more sprouts.
        PW_WHO_DARES                  = 7892, -- Who dares disturb these gates? Pathetic mortal, what foolishness has brought you here? No matter, your fate is now irrevocably sealed. Come now, do not fear. Embrace your death!
        SENSE_OMINOUS_PRESENCE        = 7935, -- You sense an ominous presence...
        BLOOD_STAINS                  = 7941, -- The ground is smeared with bloodstains...
        DRAWS_NEAR                    = 7966, -- Something draws near!
        COMMON_SENSE_SURVIVAL         = 8931, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
        UNITY_WANTED_BATTLE_INTERACT  = 8846, -- Those who have accepted % must pay # Unity accolades to participate. The content for this Wanted battle is #. [Ready to begin?/You do not have the appropriate object set, so your rewards will be limited.]
    },
    mob =
    {
        BLUESTREAK_GYUGYUROON = GetFirstID('Bluestreak_Gyugyuroon'),
        CHIGRE                = GetFirstID('Chigre'),
        CRYSTAL_EATER         = GetFirstID('Crystal_Eater'),
        NOSFERATU             = GetFirstID('Nosferatu'),
        PANDEMONIUM_WARDEN    = GetFirstID('Pandemonium_Warden'),
        PANDEMONIUM_LAMPS     = GetTableOfIDs('Pandemonium_Lamp'),
        PANDEMONIUM_AVATARS   = GetTableOfIDs('Pandemonium_Lamp_Avatar'),
    },
    npc =
    {
        DAMPSOIL       = GetFirstID('Dampsoil'),
        MUSHROOM_PATCH = GetFirstID('Mushroom_Patch'),
    },
}

return zones[xi.zone.AYDEEWA_SUBTERRANE]
