-- Text ids rebuilt for the 2007 PS2 client data tooling: PROFILE 2012pc = the 2012 client + PC 2025 import (report 36) by research/tools/lsb_textids_2007.py (1 changed, 11 not in the 2007 dialog DAT 6547 and left unchanged).
-----------------------------------
-- Area: Behemoths_Dominion
-----------------------------------
zones = zones or {}

zones[xi.zone.BEHEMOTHS_DOMINION] =
{
    text =
    {
        ITEM_CANNOT_BE_OBTAINED       = 6375,  -- You cannot obtain the <item>. Come back after sorting your inventory.
        ITEM_OBTAINED                 = 6378,  -- Obtained: <item>.
        GIL_OBTAINED                  = 6380,  -- Obtained <number> gil.
        KEYITEM_OBTAINED              = 6398,  -- Obtained key item: <keyitem>.
        NOTHING_OUT_OF_ORDINARY       = 6392,  -- There is nothing out of the ordinary here.
        SENSE_OF_FOREBODING           = 6393,  -- You are suddenly overcome with a sense of foreboding...
        IRREPRESSIBLE_MIGHT           = 6396,  -- An aura of irrepressible might threatens to overwhelm you...
        FELLOW_MESSAGE_OFFSET         = 6406,  -- I'm ready. I suppose.
        CARRIED_OVER_POINTS           = 7006,  -- You have carried over <number> login point[/s].
        LOGIN_CAMPAIGN_UNDERWAY       = 7007,  -- The [/January/February/March/April/May/June/July/August/September/October/November/December] <number> Login Campaign is currently underway!
        LOGIN_NUMBER                  = 7008,  -- In celebration of your most recent login (login no. <number>), we have provided you with <number> points! You currently have a total of <number> points.
        MEMBERS_LEVELS_ARE_RESTRICTED = 7028,  -- Your party is unable to participate because certain members' levels are restricted.
        CONQUEST_BASE                 = 6994,  -- Tallying conquest results...
        THERE_ARE_SYMBOLS             = 7153,  -- There are some symbols inscribed upon it.
        YOU_HEAR_A_NOISE              = 7155,  -- You hear a noise behind you.
        AIR_AROUND_YOU_CHANGED        = 7159,  -- The air around you has suddenly changed!
        SOMETHING_BETTER              = 7160,  -- Don't you have something better to do right now?
        CANNOT_REMOVE_FRAG            = 7163,  -- It is an oddly shaped stone monument. A shining stone is embedded in it, but cannot be removed...
        ALREADY_OBTAINED_FRAG         = 7344,  -- You have already obtained this monument's <keyitem>. Try searching for another.
        ALREADY_HAVE_ALL_FRAGS        = 7165,  -- You have obtained all of the fragments. You must hurry to the ruins of the ancient shrine!
        FOUND_ALL_FRAGS               = 7346,  -- You have obtained <keyitem>! You now have all 8 fragments of light!
        ZILART_MONUMENT               = 7167,  -- It is an ancient Zilart monument.
        MUST_MOVE_CLOSER              = 7361,  -- You will have to move closer to remove the <keyitem>.
        PLAYER_OBTAINS_ITEM           = 7188,  -- <name> obtains <item>!
        UNABLE_TO_OBTAIN_ITEM         = 7189,  -- You were unable to obtain the item.
        PLAYER_OBTAINS_TEMP_ITEM      = 7190,  -- <name> obtains the temporary item: <item>!
        ALREADY_POSSESS_TEMP          = 7191,  -- You already possess that temporary item.
        NO_COMBINATION                = 7196,  -- You were unable to enter a combination.
        UNITY_WANTED_BATTLE_INTERACT  = 11339, -- Those who have accepted % must pay # Unity accolades to participate. The content for this Wanted battle is #. [Ready to begin?/You do not have the appropriate object set, so your rewards will be limited.]
        REGIME_REGISTERED             = 9352,  -- New training regime registered!
        LEARNS_SPELL                  = 11543, -- <name> learns <spell>!
        UNCANNY_SENSATION             = 11545, -- You are assaulted by an uncanny sensation.
        COMMON_SENSE_SURVIVAL         = 11552, -- It appears that you have arrived at a new survival guide provided by the Adventurers' Mutual Aid Network. Common sense dictates that you should now be able to teleport here from similar tomes throughout the world.
    },
    mob =
    {
        BEHEMOTH                = GetFirstID('Behemoth'),
        KING_BEHEMOTH           = GetFirstID('King_Behemoth'),
        ANCIENT_WEAPON          = GetFirstID('Ancient_Weapon'),
        LEGENDARY_WEAPON        = GetFirstID('Legendary_Weapon'),
        TALEKEEPERS_GIFT_OFFSET = GetFirstID('Picklix_Longindex'),
    },
    npc =
    {
        BEHEMOTH_QM      = GetFirstID('qm_behemoth'),
        CERMET_HEADSTONE = GetFirstID('Cermet_Headstone'),
    },
}

return zones[xi.zone.BEHEMOTHS_DOMINION]
