-----------------------------------
-- LAN night "hidden content" switches (report 32, research/reports/32_hidden_content.md).
-- Data file only (no Module): the lan_* modules in this folder read it. Edit, then restart the map server.
-- Everything here is OFF in stock LSB and needs the 2012 client + LAN data set (report 28).
-----------------------------------
return
{
    -- Seasonal events, forced on regardless of the real (JST) date. Each one's client data was checked against the
    -- LAN set (work/b15_hidden/out/seasonal_check.tsv).
    FORCE_STARLIGHT_CELEBRATION = true,  -- Dec event: city decorations (models 1241-1248) + Jeuno music 239
    FORCE_EGG_HUNT              = false, -- Apr event: Egg Hunt moogles in the 6 nation cities (cutscenes present)
    FORCE_HARVEST_FESTIVAL      = true,  -- Oct 20-Nov 1: trick-or-treat NPC costumes (HALLOWEEN_2005 version)

    -- Egg Hunt era flags (only read while FORCE_EGG_HUNT is on). 2005 is the base; 2006-2009 add prizes that exist in
    -- the 2012 data. Later eras need items the 2012 client does not have, so leave them off.
    EGG_HUNT_ERAS = { ERA_2006 = true, ERA_2007 = true, ERA_2008 = true, ERA_2009 = true },

    -- GM Home (zone 210, reach it with !gmhome): let the developers' debug NPCs play their own cutscene/menus from the
    -- 2012 client data (Map-Change, Equip Navi, Level-Check, Lottery-Maker, ...). Choices are printed to the GM and to
    -- the server log; nothing is granted or changed. GM-only area.
    GMHOME_DEBUG_NPCS = true,

    -- !lanboss <name> spawns a one-off / event boss next to the GM as a temporary (dynamic) monster, using LSB's own
    -- stats and a model the 2012 client has. !lanboss list prints the names.
    LANBOSS_COMMAND = true,
}
