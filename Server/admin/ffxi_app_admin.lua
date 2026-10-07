-----------------------------------
-- FFXI 2016 Server App (Server/server_admin.py): admin actions that run inside the map server.
--
-- The app adds one line to Server/lsb/app_bridge.queue (read by the lan_appbridge module every few seconds):
--     lua (function() dofile("<this file>"); return FFXIAPP.run("<id>", "<action>", ...) end)()
-- The file is loaded again on every call (it is tiny), so edits take effect without restarting anything.
-- Every action prints exactly one result line into Server/data/logs/xi_map.log, which the app reads back:
--     [FFXIAPP <id>] ok <text>        or        [FFXIAPP <id>] err <text>
-- An action on a player who is not online answers "err offline" so the app can use a database-only path instead.
-----------------------------------
FFXIAPP = FFXIAPP or {}
local A = FFXIAPP

local SYSTEM = 6 -- xi.msg.channel.SYSTEM_1: the standard system-message line every client version shows

local function eachPlayer(fn)
    local seen = {}
    for _, zoneId in pairs(xi.zone or {}) do
        if type(zoneId) == 'number' and not seen[zoneId] then
            seen[zoneId] = true
            local zone = GetZone(zoneId)
            if zone then
                for _, p in pairs(zone:getPlayers()) do
                    fn(p)
                end
            end
        end
    end
end

local function target(name)
    local p = GetPlayerByName(name)
    if p == nil then
        error('offline', 0)
    end

    return p
end

local actions = {}

-- Message to everyone in game. chan: optional chat channel number (default system message).
actions.broadcast = function(msg, chan)
    local n = 0
    eachPlayer(function(p)
        p:printToPlayer(msg, chan or SYSTEM)
        n = n + 1
    end)
    return string.format('message sent to %d player(s)', n)
end

-- Private message to one player.
actions.tell = function(name, msg, chan)
    local p = target(name)
    p:printToPlayer(msg, chan or SYSTEM)
    return 'message sent to ' .. p:getName()
end

-- Online players, as name@zone_id;name@zone_id;...
actions.who = function()
    local list = {}
    eachPlayer(function(p)
        table.insert(list, string.format('%s@%d', p:getName(), p:getZoneID()))
    end)
    return #list .. ' ' .. table.concat(list, ';')
end

-- Give an item: straight into the inventory, or to the delivery box (mog house) when the inventory is full.
actions.give = function(name, itemId, qty)
    qty = qty or 1
    local p = target(name)
    local zoneIds = zones and zones[p:getZoneID()]
    if p:getFreeSlotsCount() > 0 and p:addItem({ id = itemId, quantity = qty }) then
        pcall(function()
            if qty > 1 then
                p:messageSpecial(zoneIds.text.ITEM_OBTAINED + 9, itemId, qty)
            else
                p:messageSpecial(zoneIds.text.ITEM_OBTAINED, itemId)
            end
        end)
        return string.format('gave %s item %d x%d (inventory)', p:getName(), itemId, qty)
    end

    local rc = SendItemToDeliveryBox(p:getName(), itemId, qty, 'Server')
    if rc == 0 or rc == 1 then
        p:printToPlayer('The server sent you an item: it is waiting in your delivery box (mog house).', SYSTEM)
        return string.format('inventory full: item %d x%d sent to %s\'s delivery box', itemId, qty, p:getName())
    end

    error('could not give the item (code ' .. tostring(rc) .. ')', 0)
end

-- Delivery box for a player who is offline (the map server writes it the same way the in-game delivery does).
actions.deliver = function(name, itemId, qty)
    local rc = SendItemToDeliveryBox(name, itemId, qty or 1, 'Server')
    local why = { [0] = 'sent', [1] = 'sent (limited to one stack)', [2] = 'no such character', [3] = 'no such item', [4] = 'database error' }
    if rc == 0 or rc == 1 then
        return string.format('item %d x%d %s to %s\'s delivery box', itemId, qty or 1, why[rc], name)
    end

    error(why[rc] or ('code ' .. tostring(rc)), 0)
end

-- Move a player to another zone, at the given spot (the Server App passes a zone entrance), or 0,0,0 like !zone.
actions.zone = function(name, zoneId, x, y, z, rot)
    local p = target(name)
    p:printToPlayer('The server is moving you to another area.', SYSTEM)
    p:setPos(x or 0, y or 0, z or 0, rot or 0, zoneId)
    return string.format('moving %s to zone %d', p:getName(), zoneId)
end

-- Send a player to their home point.
actions.home = function(name)
    local p = target(name)
    p:warp()
    return 'sent ' .. p:getName() .. ' to their home point'
end

-- Log a player out (like !kick / !logoff).
actions.kick = function(name)
    local p = target(name)
    local n = p:getName()
    p:leaveGame()
    return n .. ' has been logged off'
end

-- GM level 0-5.
actions.promote = function(name, level)
    local p = target(name)
    p:setGMLevel(level)
    if level == 0 then
        pcall(function() p:setVisibleGMLevel(0) end)
    end

    p:printToPlayer(string.format('You have been set to GM level %d.', level), SYSTEM)
    return string.format('%s is now GM level %d', p:getName(), level)
end

-- Free a player stuck in a cutscene / event.
actions.release = function(name)
    local p = target(name)
    p:release()
    return 'released ' .. p:getName()
end

-- Full HP and MP (raise first if the player is KO).
actions.heal = function(name)
    local p = target(name)
    if p:isDead() then
        p:sendRaise(3)
        return 'raise offered to ' .. p:getName() .. ' (they must accept it)'
    end

    p:setHP(p:getMaxHP())
    p:setMP(p:getMaxMP())
    p:printToPlayer('The server restored your HP and MP.', SYSTEM)
    return 'healed ' .. p:getName()
end

-- 6 Oct 2026 (moderation): a real /tell line from the server (shows as a tell from <sender> in every client version).
actions.whisper = function(name, msg, sender)
    local p = target(name)
    p:printToPlayer(msg, 3, sender or 'Server') -- 3 = xi.msg.channel.TELL
    return 'whisper sent to ' .. p:getName()
end

-- Jail (Mordion Gaol, like !jail): online = move now; offline = the database is changed by the map server (SendToJailOffline).
local JAIL = { [1] = { -620, 11, 660 }, [2] = { -180, 11, 660 }, [3] = { 260, 11, 660 }, [4] = { 700, 11, 660 } }
actions.jail = function(name, cell)
    cell = JAIL[cell or 1] and (cell or 1) or 1
    local dest = JAIL[cell]
    local p = GetPlayerByName(name)
    if p then
        p:setCharVar('inJail', cell)
        p:printToPlayer('You have been sent to jail by the server.', SYSTEM)
        p:setPos(dest[1], dest[2], dest[3], 0, 131)
        return p:getName() .. ' is jailed (Mordion Gaol cell ' .. cell .. ')'
    end

    local id = GetPlayerIDByName(name)
    if id == nil or id <= 0 or id >= 0xFFFFFFFF then
        error('no such character', 0)
    end

    SendToJailOffline(id, cell, dest[1], dest[2], dest[3], 0)
    return name .. ' is offline: jailed (cell ' .. cell .. ') - they start there next time'
end

-- Out of jail: home point (online). Offline players are handled by the app in the database.
actions.unjail = function(name)
    local p = target(name)
    p:setCharVar('inJail', 0)
    p:printToPlayer('You have been released from jail.', SYSTEM)
    p:warp()
    return p:getName() .. ' is out of jail (sent to their home point)'
end

-- Move player <name> to where player <to> stands.
actions.bring = function(name, to)
    local p = target(name)
    local t = GetPlayerByName(to)
    if t == nil then
        error(to .. ' is not in the game', 0)
    end

    p:printToPlayer('The server is moving you to ' .. t:getName() .. '.', SYSTEM)
    p:setPos(t:getXPos(), t:getYPos(), t:getZPos(), t:getRotPos(), t:getZoneID())
    return string.format('moving %s to %s', p:getName(), t:getName())
end

-- Tell a player they were muted / unmuted (the mute itself is in the PS2 proxy: .tools/muted.txt).
actions.mutenote = function(name, on)
    local p = target(name)
    p:printToPlayer(on and 'You have been muted by the server: your chat is not shown to anyone.' or 'You can chat again.', SYSTEM)
    return 'told ' .. p:getName()
end


-- Release (FFXI 2016 Server App): more GM actions for the chat box commands.
actions.gil = function(name, amount)
    local p = target(name)
    p:addGil(amount)
    p:printToPlayer(string.format('The server gave you %d gil.', amount), SYSTEM)
    return string.format('%s now has %d gil', p:getName(), p:getGil())
end

actions.level = function(name, level)
    local p = target(name)
    p:setLevel(level)
    p:printToPlayer(string.format('The server set your level to %d.', level), SYSTEM)
    return string.format('%s is now level %d', p:getName(), p:getMainLvl())
end

actions.job = function(name, jobId, level)
    local p = target(name)
    if jobId == xi.job.PUP and p:getAutomatonName() == '' then
        p:setPetName(xi.petType.AUTOMATON, xi.petName.MK_IV)
    end

    local pet = p:getPet()
    if pet then
        p:despawnPet()
    end

    p:changeJob(jobId)
    if level then
        p:setLevel(level)
    end

    p:printToPlayer('The server changed your job.', SYSTEM)
    return string.format('%s is now job %d level %d', p:getName(), p:getMainJob(), p:getMainLvl())
end

actions.kill = function(name)
    local p = target(name)
    if p:isDead() then
        error(p:getName() .. ' is already KO', 0)
    end

    p:setHP(0)
    return p:getName() .. ' was knocked out'
end

actions.revive = function(name)
    local p = target(name)
    if not p:isDead() then
        error(p:getName() .. ' is not KO', 0)
    end

    p:sendRaise(3)
    return 'raise offered to ' .. p:getName() .. ' (they must accept it)'
end

actions.announce = function(msg)
    local n = 0
    eachPlayer(function(p)
        p:printToPlayer(msg, 7) -- xi.msg.channel.SYSTEM_2: login / world announcement line
        n = n + 1
    end)
    return string.format('announcement sent to %d player(s)', n)
end

-- Roles (Server App > Roles): the GM level a role needs, and a plain message to the player.
actions.setrole = function(name, level, roleName)
    local p = target(name)
    p:setGMLevel(level)
    if level == 0 then
        pcall(function() p:setVisibleGMLevel(0) end)
        p:printToPlayer('Your role was removed by the server.', SYSTEM)
    else
        p:printToPlayer('You are now: ' .. tostring(roleName) .. '.', SYSTEM)
    end

    return string.format('%s GM level %d', p:getName(), level)
end

A.run = function(id, action, ...)
    local fn = actions[action]
    local ok, res
    if fn == nil then
        ok, res = false, 'unknown action ' .. tostring(action)
    else
        ok, res = pcall(fn, ...)
    end

    print(string.format('[FFXIAPP %s] %s %s', id, ok and 'ok' or 'err', tostring(res)))
end
