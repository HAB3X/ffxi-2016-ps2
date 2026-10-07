-----------------------------------
-- LAN night Legacy Content GM commands (report 32 §9): !betamusic, !museum, !legacyitem
-----------------------------------
require('modules/module_utils')
local music  = require('modules/lan_legacy/lua/lan_beta_music_data')
local museum = require('modules/lan_legacy/lua/lan_museum_data')
local items  = require('modules/lan_legacy/lua/lan_legacy_items_data')
-----------------------------------
local function tell(player, text)
    player:printToPlayer(text, xi.msg.channel.SYSTEM_3, '')
end

---@type TCommand
local betamusic = { cmdprops = { permission = 1, parameters = 's' } }
betamusic.onTrigger = function(player, arg)
    if arg == nil or arg == '' or arg == 'list' then
        for i, t in ipairs(music) do
            tell(player, string.format('%d: track %d, %s', i, t.id, t.label))
        end

        return
    end

    if arg == 'off' then
        tell(player, 'Change zone to get the normal music back.')
        return
    end

    if not (xi.lanLegacy and xi.lanLegacy.playTrack(player, tonumber(arg) or 0)) then
        tell(player, '!betamusic list | <number> | off')
    end
end

xi.module.registerCommand('betamusic', betamusic)

---@type TCommand
local museumCmd = { cmdprops = { permission = 1, parameters = 's' } }
museumCmd.onTrigger = function(player, arg)
    if arg == nil or arg == '' or arg == 'list' then
        for i, e in ipairs(museum) do
            tell(player, string.format('%d: %s (model %d)', i, e.name, e.model))
        end

        return
    end

    if arg == 'clear' then
        xi.lanLegacy.clearExhibits()
        return
    end

    if arg == 'all' then
        for i = 1, #museum do
            xi.lanLegacy.spawnExhibit(player, i)
        end

        return
    end

    if not xi.lanLegacy.spawnExhibit(player, tonumber(arg) or 0) then
        tell(player, '!museum list | <number> | all | clear')
    end
end

xi.module.registerCommand('museum', museumCmd)

---@type TCommand
local legacyitem = { cmdprops = { permission = 1, parameters = 's' } }
legacyitem.onTrigger = function(player, arg)
    if arg == nil or arg == '' or arg == 'list' then
        for _, it in ipairs(items) do
            tell(player, string.format('%d %s (%s)', it.id, it.name, it.kind))
        end

        return
    end

    if arg == 'all' then
        for _, it in ipairs(items) do
            xi.lanLegacy.giveItem(player, it.id)
        end

        return
    end

    if not xi.lanLegacy.giveItem(player, tonumber(arg) or 0) then
        tell(player, 'Not given (unknown id, not in the item database, or inventory full). !legacyitem list')
    end
end

xi.module.registerCommand('legacyitem', legacyitem)

-- !lanraid list | <key>: GM teleport to a raid/endgame entry NPC (or into the raid zone), report 32 §10.
local raids = require('modules/lan_legacy/lua/lan_raids_data')

---@type TCommand
local lanraid = { cmdprops = { permission = 1, parameters = 's' } }
lanraid.onTrigger = function(player, arg)
    if arg == nil or arg == '' or arg == 'list' then
        local keys = {}
        for _, r in ipairs(raids) do
            table.insert(keys, r.key)
        end

        tell(player, '!lanraid <key>: ' .. table.concat(keys, ', '))
        return
    end

    for _, r in ipairs(raids) do
        if r.key == arg then
            if r.pos then
                tell(player, 'Going to ' .. r.name)
                player:setPos(r.pos[1] + 1, r.pos[2], r.pos[3] + 1, 0, r.zone)
            else
                tell(player, string.format('Going into %s (zone %d). If you land in a wall, use !zone %d instead.', r.name, r.zone, r.zone))
                player:setPos(0, 0, 0, 0, r.zone)
            end

            return
        end
    end

    tell(player, 'Unknown key. !lanraid list')
end

xi.module.registerCommand('lanraid', lanraid)

-- !legacyboss list | <name> | zone : monsters removed from the game after 2009 (report 37's list), as temporary
-- dynamic spawns with darkstar-2012 models and a same-zone LSB group for stats (APPROXIMATE), report 32 §14.
local legacyBosses = require('modules/lan_legacy/lua/lan_legacy_bosses_data')
-- yaml-only groups cannot be instantiated dynamically: map to a SQL stand-in (tools/build_group_map.py, report 32 §15)
local okMap, resolveGroup = pcall(require, 'modules/lan_legacy/lua/lan_group_map')
if not okMap or type(resolveGroup) ~= 'function' then
    resolveGroup = function(group, zone)
        return group, zone, 0
    end
end

local function spawnLegacy(player, b, dx, dz)
    local zone = player:getZone()
    local groupId, groupZoneId, fixedHP = resolveGroup(b.group, b.groupZone, b.name)
    local mob  = zone:insertDynamicEntity({
        objtype               = xi.objType.MOB,
        name                  = b.name,
        x                     = player:getXPos() + dx,
        y                     = player:getYPos(),
        z                     = player:getZPos() + dz,
        rotation              = player:getRotPos(),
        look                  = b.look,
        groupId               = groupId,
        groupZoneId           = groupZoneId,
        minLevel              = b.minLevel,
        maxLevel              = b.maxLevel,
        releaseIdOnDisappear  = true,
        specialSpawnAnimation = true,
    })
    if mob then
        mob:setSpawn(player:getXPos() + dx, player:getYPos(), player:getZPos() + dz, player:getRotPos())
        mob:spawn()
        DisallowRespawn(mob:getID(), true)
        if fixedHP and fixedHP > 0 then
            mob:setMaxHP(fixedHP)
            mob:setHP(mob:getMaxHP())
        end

        print(string.format('[legacyboss] %s spawned %s (model %d, stand-in group %d/%d)', player:getName(), b.name, b.look, groupZoneId, groupId))
    end

    return mob
end

---@type TCommand
local legacyboss = { cmdprops = { permission = 1, parameters = 's' } }
legacyboss.onTrigger = function(player, arg)
    if arg == nil or arg == '' or arg == 'list' then
        local t = {}
        for _, b in ipairs(legacyBosses) do
            table.insert(t, string.format('%s (%s, zone %d)', b.name, b.kind, b.zone))
        end

        tell(player, '!legacyboss <name> | zone: ' .. table.concat(t, ', '))
        return
    end

    if arg == 'zone' then
        local here, n = player:getZoneID(), 0
        for _, b in ipairs(legacyBosses) do
            if b.zone == here then
                n = n + 1
                spawnLegacy(player, b, 4 * math.cos(n), 4 * math.sin(n))
            end
        end

        tell(player, n .. ' legacy monsters of this zone spawned (they do not respawn).')
        return
    end

    for _, b in ipairs(legacyBosses) do
        if string.lower(b.name) == string.lower(arg) then
            if spawnLegacy(player, b, 3, 0) then
                tell(player, string.format('%s spawned (removed from the game after 2009; stats approximate).', b.name))
            else
                tell(player, 'Spawn failed (check the server log).')
            end

            return
        end
    end

    tell(player, 'Unknown name. !legacyboss list')
end

xi.module.registerCommand('legacyboss', legacyboss)
