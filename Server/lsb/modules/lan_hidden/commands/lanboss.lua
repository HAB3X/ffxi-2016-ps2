-----------------------------------
-- func: lanboss
-- desc: LAN night (report 32): spawn a one-off / event boss next to the GM as a temporary monster.
--       !lanboss list          - print the names
--       !lanboss <name>        - spawn it here (LSB stats of its own group; model the 2012 client has)
--       !lanboss find <text>   - search all 2,755 notorious monsters LSB defines whose model the 2012 data has
-- Bosses whose own spawn id is in the 2012 client's list can also be popped in their home zone with !spawnmob <id>
-- (see work/b15_hidden/out/bosses.tsv). Data: modules/lan_hidden/lua/lan_bosses_data.lua (tools/gen_bosses.py).
-----------------------------------
require('modules/module_utils')
local cfg    = require('modules/lan_hidden/lua/lan_hidden_config')
local bosses = require('modules/lan_hidden/lua/lan_bosses_data')
local allNms = require('modules/lan_hidden/lua/lan_bosses_all_data')   -- 2,755 LSB notorious monsters with a 2012 model
-- yaml-only groups cannot be instantiated dynamically: map to a SQL stand-in (tools/build_group_map.py, report 32 §15)
local okMap, resolveGroup = pcall(require, 'modules/lan_hidden/lua/lan_group_map')
if not okMap or type(resolveGroup) ~= 'function' then
    resolveGroup = function(group, zone)
        return group, zone, 0
    end
end
-- the Legacy Bosses (removed after 2009) when the lan_legacy module is installed too
local okLegacy, legacyList = pcall(require, 'modules/lan_legacy/lua/lan_legacy_bosses_data')
if okLegacy and type(legacyList) == 'table' then
    for _, b in ipairs(legacyList) do
        if b.kind ~= 'npc' then
            allNms[string.lower(b.name)] = { name = b.name, group = b.group, zone = b.groupZone, look = b.look, minLevel = b.minLevel,
                maxLevel = b.maxLevel, mobId = 0, inClientList = false, src = 'Legacy (removed after 2009)' }
        end
    end
end
-----------------------------------
---@type TCommand
local commandObj = {}

commandObj.cmdprops =
{
    permission = 1,
    parameters = 's',   -- the whole rest of the line
}

local function tell(player, msg)
    player:printToPlayer(msg, xi.msg.channel.SYSTEM_3, '')
end

commandObj.onTrigger = function(player, arg)
    if not cfg.LANBOSS_COMMAND then
        tell(player, '!lanboss is switched off in lan_hidden_config.lua')
        return
    end

    if arg == nil or arg == '' or arg == 'list' then
        local names = {}
        for key, b in pairs(bosses) do
            table.insert(names, string.format('%s (%s)', key, b.src))
        end

        table.sort(names)
        tell(player, '!lanboss <name>: ' .. table.concat(names, ', '))
        return
    end

    local findText = string.match(arg, '^find%s+(.+)$')
    if findText then
        local hits = {}
        for key, nm in pairs(allNms) do
            if string.find(key, string.lower(findText), 1, true) then
                table.insert(hits, string.format('%s (Lv.%d, %s%s)', key, nm.minLevel, nm.src, nm.inClientList and ', !spawnmob ' .. nm.mobId or ''))
            end
        end

        table.sort(hits)
        tell(player, #hits .. ' found: ' .. table.concat(hits, '; ', 1, math.min(#hits, 25)))
        return
    end

    local b = bosses[string.lower(arg)] or allNms[string.lower(arg)]
    if b == nil then
        tell(player, 'Unknown boss. Try !lanboss list')
        return
    end

    local zone = player:getZone()
    local groupId, groupZoneId, fixedHP = resolveGroup(b.group, b.zone, b.name)
    local minLevel = (b.minLevel or 0) > 0 and b.minLevel or 75
    local maxLevel = math.max(minLevel, b.maxLevel or 0)
    local mob  = zone:insertDynamicEntity({
        objtype               = xi.objType.MOB,
        name                  = b.name,
        x                     = player:getXPos() + 3,
        y                     = player:getYPos(),
        z                     = player:getZPos(),
        rotation              = player:getRotPos(),
        look                  = b.look,
        groupId               = groupId,
        groupZoneId           = groupZoneId,
        minLevel              = minLevel,
        maxLevel              = maxLevel,
        releaseIdOnDisappear  = true,
        specialSpawnAnimation = true,
    })

    if mob == nil then
        tell(player, 'Spawn failed (group not loaded? check the server log)')
        return
    end

    mob:setSpawn(player:getXPos() + 3, player:getYPos(), player:getZPos(), player:getRotPos())
    mob:spawn()
    DisallowRespawn(mob:getID(), true)
    if fixedHP and fixedHP > 0 then
        mob:setMaxHP(fixedHP)
        mob:setHP(mob:getMaxHP())
    end

    print(string.format('[lanboss] %s spawned %s (group %d/%d via %d/%d, model %d, HP %d) id %d', player:getName(), b.name, b.zone, b.group,
        groupZoneId, groupId, b.look, mob:getMaxHP(), mob:getID()))
    tell(player, string.format('%s spawned (Lv.%d-%d). It will not respawn.', b.name, minLevel, maxLevel))
end

xi.module.registerCommand('lanboss', commandObj)
