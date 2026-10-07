-----------------------------------
-- lan_legacy: the "Legacy Content" add-on for the 2012 build (report 32 §9). Needs the legacy drive clone
-- (work/b15_hidden/legacy/tools/legacy_drive.py) for the beta music and the beta models; the time-capsule NPCs and the
-- quartermaster work on any 2012 drive (RC1 already has the 27 restored item records).
--   GM Home (!gmhome): Beta Jukebox (13 beta tracks), Museum Curator (25 beta models), Legacy Quartermaster
--   (the 27 restored weapons/armour, needs sql/lan_unreleased_items.sql), and 106 retired campaign NPCs placed back in
--   their towns/fields with their original lines.
--   GM commands: !betamusic list|<n>|off, !museum list|<n>|all|clear, !legacyitem list|<id>|all
-- Switches below. Undo: legacy/revert_legacy.sh (removes the module line) + map-server restart.
-----------------------------------
require('modules/module_utils')
local music    = require('modules/lan_legacy/lua/lan_beta_music_data')
local museum   = require('modules/lan_legacy/lua/lan_museum_data')
local capsules = require('modules/lan_legacy/lua/lan_time_capsule_data')
local items    = require('modules/lan_legacy/lua/lan_legacy_items_data')
-----------------------------------
local cfg =
{
    TIME_CAPSULE_NPCS = true,
    GM_HOME_JUKEBOX   = true,
    GM_HOME_MUSEUM    = true,
    GM_HOME_QUARTERMASTER = true,
}

local m = Module:new('lan_legacy')

xi = xi or {}
xi.lanLegacy = xi.lanLegacy or { exhibits = {} }

local GM_HOME = 210

local function say(player, who, text)
    player:printToPlayer(text, xi.msg.channel.NS_SAY, who)
end

local function tell(player, text)
    player:printToPlayer(text, xi.msg.channel.SYSTEM_3, '')
end

-- jukebox ---------------------------------------------------------------------------------------------------------
xi.lanLegacy.playTrack = function(player, idx)
    local t = music[idx]
    if not t then
        return false
    end

    player:changeMusic(xi.musicSlot.ZONE_DAY, t.id)
    player:changeMusic(xi.musicSlot.ZONE_NIGHT, t.id)
    tell(player, string.format('Now playing %d/%d: track %d = %s (until you change zone)', idx, #music, t.id, t.label))
    return true
end

-- museum ----------------------------------------------------------------------------------------------------------
xi.lanLegacy.spawnExhibit = function(player, idx)
    local e = museum[idx]
    if not e then
        return nil
    end

    local zone = player:getZone()
    local col  = (idx - 1) % 5
    local row  = math.floor((idx - 1) / 5)
    local npc  = zone:insertDynamicEntity({
        objtype  = xi.objType.NPC,
        name     = 'Exhibit_' .. idx,
        packetName = e.name,
        look     = e.model,
        x        = player:getXPos() + (col - 2) * 4,
        y        = player:getYPos(),
        z        = player:getZPos() + 4 + row * 4,
        rotation = player:getRotPos(),
        widescan = 1,
        onTrigger = function(p, n)
            say(p, e.name, string.format('2001 beta model (beta file %d, kind %s), shown as model %d.', e.beta, e.kind, e.model))
        end,
        releaseIdOnDisappear = true,
    })
    if npc then
        table.insert(xi.lanLegacy.exhibits, npc:getID())
    end

    return npc
end

xi.lanLegacy.clearExhibits = function()
    for _, id in ipairs(xi.lanLegacy.exhibits) do
        local n = GetNPCByID(id)
        if n then
            n:setStatus(xi.status.DISAPPEAR)
        end
    end

    xi.lanLegacy.exhibits = {}
end

-- quartermaster ---------------------------------------------------------------------------------------------------
xi.lanLegacy.giveItem = function(player, itemId)
    if player:getFreeSlotsCount() < 1 then
        tell(player, 'Inventory full.')
        return false
    end

    return player:addItem(itemId)
end

-- world setup -----------------------------------------------------------------------------------------------------
local function placeCapsules()
    local n = 0
    for i, c in ipairs(capsules) do
        local zone = GetZone(c.zone)
        if zone then
            local lines = c.lines
            zone:insertDynamicEntity({
                objtype    = xi.objType.NPC,
                name       = 'Capsule_' .. i,
                packetName = c.name,
                look       = c.model,
                x          = c.pos[1],
                y          = c.pos[2],
                z          = c.pos[3],
                rotation   = 0,
                widescan   = 1,
                onTrigger  = function(player, npc)
                    local key = 'lanCapsule_' .. i
                    local k   = (player:getLocalVar(key) % #lines) + 1
                    player:setLocalVar(key, k)
                    if k == 1 then
                        tell(player, '(' .. c.label .. ': retired by Square Enix, original lines)')
                    end

                    say(player, c.name, lines[k])
                end,
            })
            n = n + 1
        end
    end

    print(string.format('[lan_legacy] %d time-capsule NPCs placed', n))
end

local function placeGmHome()
    local zone = GetZone(GM_HOME)
    if not zone then
        return
    end

    if cfg.GM_HOME_JUKEBOX then
        zone:insertDynamicEntity({
            objtype = xi.objType.NPC, name = 'Beta_Jukebox', packetName = 'Beta Jukebox', look = 82,
            x = -10, y = 0, z = -6, rotation = 64, widescan = 1,
            onTrigger = function(player, npc)
                local k = (player:getLocalVar('lanJukebox') % #music) + 1
                player:setLocalVar('lanJukebox', k)
                xi.lanLegacy.playTrack(player, k)
            end,
        })
    end

    if cfg.GM_HOME_MUSEUM then
        zone:insertDynamicEntity({
            objtype = xi.objType.NPC, name = 'Museum_Curator', packetName = 'Museum Curator', look = 82,
            x = -6, y = 0, z = -6, rotation = 64, widescan = 1,
            onTrigger = function(player, npc)
                local k = (player:getLocalVar('lanMuseum') % #museum) + 1
                player:setLocalVar('lanMuseum', k)
                say(player, 'Museum Curator', string.format('Exhibit %d of %d: %s. (A 2001 beta model; if it looks broken, note the number.)', k, #museum, museum[k].name))
                xi.lanLegacy.spawnExhibit(player, k)
            end,
        })
    end

    if cfg.GM_HOME_QUARTERMASTER then
        zone:insertDynamicEntity({
            objtype = xi.objType.NPC, name = 'Legacy_Quartermaster', packetName = 'Legacy Quartermaster', look = 82,
            x = -2, y = 0, z = -6, rotation = 64, widescan = 1,
            onTrigger = function(player, npc)
                local k = (player:getLocalVar('lanQM') % #items) + 1
                player:setLocalVar('lanQM', k)
                local it = items[k]
                if xi.lanLegacy.giveItem(player, it.id) then
                    say(player, 'Legacy Quartermaster', string.format('Here is %s (%s, last seen %s). Talk again for the next one (%d of %d).', it.name, it.kind, it.src, k, #items))
                else
                    say(player, 'Legacy Quartermaster', 'That one is not in the item database yet (run lan_unreleased_items.sql).')
                end
            end,
        })
    end
end

m:addOverride('xi.server.onServerStart', function()
    super()
    if cfg.TIME_CAPSULE_NPCS then
        placeCapsules()
    end

    placeGmHome()
end)
