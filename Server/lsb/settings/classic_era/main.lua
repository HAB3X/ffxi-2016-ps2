-----------------------------------
-- STAGED, NOT ACTIVE: "classic era" overlay for the 2007 PS2 client (Wings of the Goddess launch data,
-- PATCH.VER 20070911). LSB only loads settings/*.lua, so this sub-folder is ignored until applied.
--
-- Written 2026-09-30 by the ps2proxy work (research/reports/15_ps2_proxy.md, section "Classic-era overlay").
-- Source for the choices: research/reports/16_fan_projects_new_content.md (lead 2).
--
-- To apply (with the server stopped, and nobody testing in PCSX2):
--   1. copy this file to work/lsb/settings/main.lua (there is no settings/main.lua yet; if one appears, merge
--      the keys below into it instead). Only the keys listed here change; LSB fills every other main.lua key
--      from settings/default/main.lua (fillMissingKeys).
--   2. optional, era Lua/SQL modules: add these lines to work/lsb/modules/init.txt
--          era/lua
--          era/data
--          era/sql/wotg
--          era/sql/abyssea
--          era/sql/soa
--          era/sql/rov
--      (each era/sql/<x> folder reverts changes made during <x>'s era; toau is left out because the 2007
--      client already has ToAU-era behaviour) and run LSB's dbtool to apply the SQL. Tentative: check each
--      folder's comments first.
--   3. start the server with "1 - Start Server".
-- To undo: delete work/lsb/settings/main.lua (and the init.txt lines) and restart.
-----------------------------------

xi = xi or {}
xi.settings = xi.settings or {}

xi.settings.main =
{
    -- Only content whose content_tag is enabled below is loaded.
    RESTRICT_CONTENT = 1,

    -- The 2007 client knows the base game, RotZ, CoP, ToAU and WotG. Everything later is off.
    ENABLE_ROTZ      = 1,
    ENABLE_COP       = 1,
    ENABLE_TOAU      = 1,
    ENABLE_WOTG      = 1,
    ENABLE_ACP       = 0, -- A Crystalline Prophecy (2008)
    ENABLE_AMK       = 0, -- A Moogle Kupo d'Etat (2008)
    ENABLE_ASA       = 0, -- A Shantotto Ascension (2009)
    ENABLE_ABYSSEA   = 0, -- 2010
    ENABLE_SOA       = 0, -- 2013
    ENABLE_ROV       = 0, -- 2015
    ENABLE_TVR       = 0, -- 2020
    ENABLE_VOIDWATCH = 0, -- 2010

    -- Later features the 2007 engine has no UI for.
    ENABLE_MOG_HOUSE_2F   = 0,
    ENABLE_MOG_GARDEN     = 0,
    ENABLE_FIELD_MANUALS  = 0, -- Fields of Valor (2008)
    ENABLE_GROUNDS_TOMES  = 0, -- Grounds of Valor (2009)
    ENABLE_ROE            = 0, -- Records of Eminence (2015)
    ENABLE_ROE_TIMED      = 0,
    ENABLE_DAILY_TALLY    = 0, -- Gobbie Mystery Box (2012)
    ENABLE_MAGIAN_TRIALS  = 0, -- 2010
    ENABLE_VOIDWALKER     = 0, -- 2014
    ENABLE_TRUST_CASTING  = 0, -- Trusts (2013)
    ENABLE_TRUST_QUESTS   = 0,

    -- Level 75 era.
    INITIAL_LEVEL_CAP = 50,
    MAX_LEVEL         = 75,
}
