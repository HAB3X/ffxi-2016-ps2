-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012pc = the 2012 client + PC 2025 import (report 36) by research/tools/lsb_textids_2007.py (1 changed, 8 not in the 2007 dialog DAT 6444 and left unchanged).
-----------------------------------
-- Area: Lufaise_Meadows
-----------------------------------
zones = zones or {}

zones[xi.zone.LUFAISE_MEADOWS] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375, -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378, -- Obtained: <item>.
        GIL_OBTAINED                  = 6379, -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398, -- Obtained key item: <keyitem>.
        KEYITEM_LOST                  = 6399, -- Lost key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6392, -- There is nothing out of the ordinary here.
        SENSE_OF_FOREBODING           = 6393, -- You are suddenly overcome with a sense of foreboding...
        FELLOW_MESSAGE_OFFSET         = 6406, -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7006, -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007, -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008, -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028, -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                 = 6994, -- Tallying conquest results...
        CONQUEST                      = 7162, -- You've earned conquest points!
        FISHING_MESSAGE_OFFSET        = 7496, -- You can't fish here.
        KI_STOLEN                     = 7705, -- The <keyitem> has been stolen!
        NO_ROOM_COME_BACK_LATER       = 7632, -- You do not have any room in your bag, so you hide the <item> in the grass nearby. Come and retrieve it later.
        LOGGING_IS_POSSIBLE_HERE      = 7665, -- Logging is possible here if you have <item>.
        SURVEY_THE_SURROUNDINGS       = 7672, -- You survey the surroundings but see nothing out of the ordinary.
        MURDEROUS_PRESENCE            = 7673, -- Wait, you sense a murderous presence...!
        YOU_CAN_SEE_FOR_MALMS         = 7674, -- You can see for malms in every direction.
        SPINE_CHILLING_PRESENCE       = 7676, -- You sense a spine-chilling presence!
        AMALTHEIA_TEXT                = 7715, -- A message has been engraved into the rock: Offer up the ancient shield, and the pact shall be honored.
        KURREA_TEXT                   = 7719, -- The stench of rotten flesh fills the air around you. Some scavenger must have made this place its territory.
        KURREA_SLURP                  = 7722, -- Kurrea slurps down the adamantoise soup!
        KURREA_MUSCLES                = 7723, -- Kurrea's muscles bulge crazily!
        KURREA_SHINE                  = 7724, -- Kurrea's scales shine mysteriously!
        KURREA_WIND                   = 7725, -- Kurrea is enveloped by a fierce wind!
        KURREA_RIGID                  = 7726, -- Kurrea's hide grows rigid!
        KURREA_VEIN                   = 7727, -- The veins in Kurrea's head are popping out!
        KURREA_EYES                   = 7728, -- Kurrea's eyes glow weirdly!
        KURREA_CURE                   = 7729, -- Kurrea's wounds disappear!
        KURREA_AURA                   = 7730, -- Kurrea is surrounded by an ominous aura!
        KURREA_GREEN                  = 7731, -- Kurrea's face has turned green...
        COMMON_SENSE_SURVIVAL         = 8759, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
        UNITY_WANTED_BATTLE_INTERACT  = 8679, -- Those who have accepted % must pay # Unity accolades to participate. The content for this Wanted battle is #. [Ready to begin?/You do not have the appropriate object set, so your rewards will be limited.]
    },
    mob =
    {
        AMALTHEIA             = GetFirstID('Amaltheia'),
        BAUMESEL              = GetFirstID('Baumesel'),
        BLACKBONE_FRAZDIZ     = GetFirstID('Blackbone_Frazdiz'),
        COLORFUL_LESHY        = GetFirstID('Colorful_Leshy'),
        FLOCKBOCK             = GetFirstID('Flockbock'),
        FOMOR_BARD            = GetTableOfIDs('Fomor_Bard'),
        FOMOR_BEASTMASTER     = GetTableOfIDs('Fomor_Beastmaster'),
        FOMOR_BLACK_MAGE      = GetTableOfIDs('Fomor_Black_Mage'),
        FOMOR_DARK_KNIGHT     = GetTableOfIDs('Fomor_Dark_Knight'),
        FOMOR_DRAGOON         = GetTableOfIDs('Fomor_Dragoon'),
        FOMOR_MONK            = GetTableOfIDs('Fomor_Monk'),
        FOMOR_NINJA           = GetTableOfIDs('Fomor_Ninja'),
        FOMOR_PALADIN         = GetTableOfIDs('Fomor_Paladin'),
        FOMOR_RANGER          = GetTableOfIDs('Fomor_Ranger'),
        FOMOR_RED_MAGE        = GetTableOfIDs('Fomor_Red_Mage'),
        FOMOR_SAMURAI         = GetTableOfIDs('Fomor_Samurai'),
        FOMOR_SUMMONER        = GetTableOfIDs('Fomor_Summoner'),
        FOMOR_THIEF           = GetTableOfIDs('Fomor_Thief'),
        FOMOR_WARRIOR         = GetTableOfIDs('Fomor_Warrior'),
        KURREA                = GetFirstID('Kurrea'),
        LESHY_OFFSET          = GetFirstID('Leshy'),
        MEGALOBUGARD          = GetFirstID('Megalobugard'),
        PADFOOT               = GetTableOfIDs('Padfoot'),
        SPLINTERSPINE_GRUKJUK = GetFirstID('Splinterspine_Grukjuk'),
        TAVNAZIAN_RAM         = GetTableOfIDs('Tavnazian_Ram'),
        TAVNAZIAN_SHEEP       = GetTableOfIDs('Tavnazian_Sheep'),
    },
    npc =
    {
        LOGGING       = GetTableOfIDs('Logging_Point'),
        OVERSEER_BASE = GetFirstID('Jemmoquel_RK'),
    },
}

return zones[xi.zone.LUFAISE_MEADOWS]
