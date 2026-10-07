-----------------------------------
-- lan_postbox runtime glue: binds the pure core (lan_postbox_core.lua) to the LandSandBoat Lua API.
-- Not a Module (no overrides declared here) -> the loader treats it as a helper file; commands/ and the login
-- module require() it.
-----------------------------------
local core = require('modules/lan_postbox/lua/lan_postbox_core')
local cfg  = require('modules/lan_postbox/lua/lan_postbox_config')

xi = xi or {}
xi.lanPostbox = xi.lanPostbox or {}
local P = xi.lanPostbox

P.core = core
P.cfg  = cfg

-- the real char_vars store (GetCharVar / SetCharVar work on offline characters: they go straight to SQL)
P.store =
{
    get = function(charid, name)
        return GetCharVar(charid, name)
    end,

    set = function(charid, name, value)
        SetCharVar(charid, name, value)
    end,
}

local function now()
    if GetSystemTime then
        return GetSystemTime()
    end

    return os.time()
end

function P.tell(player, text)
    player:printToPlayer(text, xi.msg.channel.SYSTEM_3, '')
end

function P.write(player, toName, text)
    local rid = GetPlayerIDByName(toName)
    local res, slot = core.write(P.store, rid, player:getName(), text, cfg, now())
    if res == core.RESULT.OK then
        local target = GetPlayerByName(toName)
        if target ~= nil then
            P.tell(target, string.format(' %s : quick message arrived (%d waiting). Type !qmr to read it.', player:getName(), core.count(P.store, rid, cfg)))
        end
    end

    return res, slot
end

function P.count(player)
    return core.count(P.store, player:getID(), cfg)
end

function P.read(player)
    return core.read(P.store, player:getID(), cfg)
end

function P.peek(player)
    return core.peek(P.store, player:getID(), cfg)
end

function P.clear(player)
    return core.clear(P.store, player:getID(), cfg)
end

function P.motdText()
    if cfg.motd ~= nil and cfg.motd ~= '' then
        return '<message of the day> ' .. cfg.motd
    end

    return '<No message of the day today>'
end

return P
