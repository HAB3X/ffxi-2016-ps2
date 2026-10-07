-----------------------------------
-- lan_roles (FFXI 2016 Server App, Fan Project by Habex): roles for in-game "!" GM commands.
--
-- The Server App writes <xi_map working dir>/app_roles.lua:
--     return { roles = { ['Moderator'] = { kick = true, jail = true } }, members = { ['charname'] = 'Moderator' } }
-- A character may use a "!" command only when its role allows that command. Commands with permission 0 (harmless
-- player commands) stay open to everyone. Characters without a role cannot use any other command, whatever their
-- GM level. The file is re-read every few seconds (time-server tick), so role changes apply without a restart.
-- Every command's onTrigger is wrapped once at server start and again if a command script is reloaded.
-----------------------------------
require('modules/module_utils')
-----------------------------------
local m = Module:new('lan_roles')

local FILE = (os.getenv('FFXI_DATA_DIR') or '.') .. '/app_roles.lua'   -- Server/data (set by the Server App), else the working dir
local state = { text = false, data = { roles = {}, members = {} }, depth = 0 }

local function loadRoles()
    local f = io.open(FILE, 'rb')
    if not f then
        state.text = nil
        state.data = { roles = {}, members = {} }
        return
    end

    local txt = f:read('*a') or ''
    f:close()
    if txt == state.text then
        return
    end

    local chunk = loadstring(txt)
    if chunk then
        local ok, d = pcall(chunk)
        if ok and type(d) == 'table' then
            state.data = { roles = d.roles or {}, members = d.members or {} }
            state.text = txt
            print('[lan_roles] roles loaded')
        end
    end
end

local function allowed(player, name, cmd)
    local perm = (cmd.cmdprops and cmd.cmdprops.permission) or 1
    if perm == 0 then
        return true
    end

    local role = state.data.members[string.lower(player:getName())]
    local r = role and state.data.roles[role]
    return type(r) == 'table' and r[name] == true
end

local function wrapAll()
    if type(xi.commands) ~= 'table' then
        return
    end

    for name, cmd in pairs(xi.commands) do
        if type(cmd) == 'table' and type(cmd.onTrigger) == 'function' and cmd.onTrigger ~= cmd.__lanRolesWrapper then
            local orig = cmd.onTrigger
            local wrapper = function(player, ...)
                -- only the command the player typed is checked; a command that calls another one (e.g. !kick runs
                -- !logoff) is not checked again
                if state.depth == 0 and player and player.getName and not allowed(player, name, cmd) then
                    player:printToPlayer("You don't have permission to use that.", xi.msg.channel.SYSTEM_1)
                    print(string.format('[lan_roles] refused !%s for %s', name, player:getName()))
                    return
                end

                state.depth = state.depth + 1
                local res = { pcall(orig, player, ...) }
                state.depth = state.depth - 1
                if not res[1] then
                    error(res[2], 0)
                end

                return unpack(res, 2)
            end

            cmd.__lanRolesWrapper = wrapper
            cmd.onTrigger         = wrapper
        end
    end
end

m:addOverride('xi.server.onServerStart', function()
    super()
    pcall(loadRoles)
    pcall(wrapAll)
end)

m:addOverride('xi.server.onTimeServerTick', function()
    super()
    local ok, e = pcall(loadRoles)
    if not ok then
        print('[lan_roles] could not read roles: ' .. tostring(e))
    end

    pcall(wrapAll)
end)

return m
