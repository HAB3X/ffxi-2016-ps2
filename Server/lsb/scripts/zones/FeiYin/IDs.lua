-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012pc = the 2012 client + PC 2025 import (report 36) by research/tools/lsb_textids_2007.py (1 changed, 8 not in the 2007 dialog DAT 6624 and left unchanged).
-----------------------------------
-- Area: FeiYin
-----------------------------------
zones = zones or {}

zones[xi.zone.FEIYIN] =
{
    text =
    {
        CONQUEST_BASE                      = 3,     -- Tallying conquest results...
        REGION_POINTS_SANDORIA             = 68,    -- San d'Oria's region points have increased!
        ITEM_CANNOT_BE_OBTAINED            = 6554,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                      = 6557,  -- Obtained: <item>.
        GIL_OBTAINED                       = 6558,  -- Obtained <number> gil.
        KEYITEM_OBTAINED                   = 6577,  -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY            = 6571,  -- There is nothing out of the ordinary here.
        SENSE_OF_FOREBODING                = 6572,  -- You are suddenly overcome with a sense of foreboding...
        FELLOW_MESSAGE_OFFSET              = 6585,  -- I'm ready. I suppose.
        CARRIED_OVER_POINTS                = 7185,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY            = 7186,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                       = 7187,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED      = 7207,  -- Your party is unable to participate because certain members' levels are restricted.
        FISHING_MESSAGE_OFFSET             = 7173,  -- You can't fish here.
        CHEST_UNLOCKED                     = 7295,  -- You unlock the chest!
        DRIED_UP_FOUNTAIN                  = 7303,  -- There is a dried up fountain here.
        YOU_FIND_NOTHING                   = 7334,  -- You find nothing.
        EVIL_PRESENCE                      = 7335,  -- You feel a conspicuously evil presence.
        SOUL_OF_TAVNAZIA                   = 7336,  -- You are able to make out the blurred letters. The soul of Tavnazia will never perish.
        ITS_FINALLY_OVER                   = 7337,  -- It is finally...over... Ahh... I can... I can see... Tavnazia... The land of wind...and light... My... My home...!
        SOFTLY_SHIMMERING_LIGHT            = 7421,  -- You see a softly shimmering light...
        YOU_REACH_OUT_TO_THE_LIGHT         = 7422,  -- You reach out to the light, and one facet of a curious seed-shaped emblem materializes on the back of your hand. It emanates an otherworldly [red/orange/yellow/green/cerulean/blue/golden/silver/white] radiance.
        THE_LIGHT_DWINDLES                 = 7423,  -- However, the light dwindles and grows dim almost at once...
        EVEN_GREATER_INTENSITY             = 7424,  -- The emblem on your hand glows with even greater intensity!
        YOU_REACH_FOR_THE_LIGHT            = 7425,  -- You reach for the light, but there is no discernable effect...
        SCINTILLATING_BURST_OF_LIGHT       = 7426,  -- As you extend your hand, there is a scintillating burst of light! Now complete, the Mark of Seed glows with near-blinding intensity!
        MARK_OF_SEED_FLICKERS              = 7435,  -- The glow of the Mark of Seed flickers and dims ever so slightly...
        MARK_OF_SEED_GROWS_FAINTER         = 7436,  -- The Mark of Seed grows fainter still. Before long, it will fade away entirely...
        MARK_OF_SEED_IS_ABOUT_TO_DISSIPATE = 7437,  -- The Mark of Seed is about to dissipate entirely! Only a faint outline remains...
        MARK_OF_SEED_HAS_VANISHED          = 7438,  -- The Mark of Seed has vanished without a trace...
        PLAYER_OBTAINS_ITEM                = 7443,  -- <name> obtains <item>!
        UNABLE_TO_OBTAIN_ITEM              = 7444,  -- You were unable to obtain the item.
        PLAYER_OBTAINS_TEMP_ITEM           = 7445,  -- <name> obtains the temporary item: <item>!
        ALREADY_POSSESS_TEMP               = 7446,  -- You already possess that temporary item.
        NO_COMBINATION                     = 7451,  -- You were unable to enter a combination.
        REGIME_REGISTERED                  = 9529,  -- New training regime registered!
        LEARNS_SPELL                       = 10666, -- <name> learns <spell>!
        UNCANNY_SENSATION                  = 10668, -- You are assaulted by an uncanny sensation.
        HOMEPOINT_SET                      = 10717, -- Home point set!
        UNITY_WANTED_BATTLE_INTERACT       = 10585, -- Those who have accepted % must pay # Unity accolades to participate. The content for this Wanted battle is #. [Ready to begin?/You do not have the appropriate object set, so your rewards will be limited.]
    },
    mob =
    {
        MIND_HOARDER        = GetFirstID('Mind_Hoarder'),
        GOLIATH             = GetFirstID('Goliath'),
        NORTHERN_SHADOW     = GetFirstID('Northern_Shadow'),
        EASTERN_SHADOW      = GetFirstID('Eastern_Shadow'),
        SOUTHERN_SHADOW     = GetFirstID('Southern_Shadow'),
        WESTERN_SHADOW      = GetFirstID('Western_Shadow'),
        ALTEDOUR_I_TAVNAZIA = GetFirstID('Altedour_I_Tavnazia'),
        MISER_MURPHY        = GetFirstID('Miser_Murphy'),
        DABOTZS_GHOST       = GetFirstID('Dabotzs_Ghost'),
        CAPRICIOUS_CASSIE   = GetFirstID('Capricious_Cassie'),
    },
    npc =
    {
        AFTERGRLOW_OFFSET       = GetFirstID('Seed_Afterglow'),
        TREASURE_CHEST          = GetFirstID('Treasure_Chest'),
        UNDERGROUND_POOL_OFFSET = GetFirstID('Underground_Pool'),
    },
}

return zones[xi.zone.FEIYIN]
