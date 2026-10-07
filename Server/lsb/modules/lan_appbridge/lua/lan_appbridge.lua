-----------------------------------
-- lan_appbridge (FFXI Server app, 6 Oct 2026): a console link that works on every OS (the Mac/Linux one needs a
-- pseudo-terminal; LandSandBoat's console on Windows only reads a real keyboard).
-- The app appends lines to <xi_map working dir>/app_bridge.queue; each line is one Lua chunk, exactly what the app would
-- type into the map server console after "lua " (it calls research/tools/ffxi_app_admin.lua, which prints its answer
-- into xi_map.log). This module runs new lines on every time-server tick (every 2.4 s) and touches
-- app_bridge.alive every ~20 s so the app knows the bridge is there.
-- Lines written before the map server started are skipped. Undo: remove "lan_appbridge" from modules/init.txt.
-----------------------------------
require('modules/module_utils')
-----------------------------------
local m = Module:new('lan_appbridge')

local DIR   = (os.getenv('FFXI_DATA_DIR') or '.') .. '/'   -- release: Server/data
local QUEUE = DIR .. 'app_bridge.queue'
local ALIVE = DIR .. 'app_bridge.alive'
local state = { pos = nil, last_alive = 0 }

local function fileSize(path)
    local f = io.open(path, 'rb')
    if not f then
        return 0
    end

    local n = f:seek('end')
    f:close()
    return n or 0
end

local function poll()
    if state.pos == nil then
        state.pos = fileSize(QUEUE) -- start "now": never replay old commands
    end

    local now = os.time()
    if now - state.last_alive >= 20 then
        state.last_alive = now
        local a = io.open(ALIVE, 'w')
        if a then
            a:write(tostring(now))
            a:close()
        end
    end

    local size = fileSize(QUEUE)
    if size < state.pos then
        state.pos = 0 -- the app truncated the file
    end

    if size == state.pos then
        return
    end

    local f = io.open(QUEUE, 'rb')
    if not f then
        return
    end

    f:seek('set', state.pos)
    local data = f:read('*a') or ''
    f:close()
    local lastNl = data:match('^.*()\n')
    if not lastNl then
        return -- no complete line yet
    end

    state.pos = state.pos + lastNl
    for line in data:sub(1, lastNl):gmatch('([^\r\n]+)') do
        local chunk, err = loadstring(line)
        if chunk then
            local ok, e = pcall(chunk)
            if not ok then
                print('[FFXIAPP bridge] error ' .. tostring(e))
            end
        else
            print('[FFXIAPP bridge] bad line: ' .. tostring(err))
        end
    end
end

m:addOverride('xi.server.onTimeServerTick', function()
    super()
    local ok, e = pcall(poll)
    if not ok then
        print('[FFXIAPP bridge] poll failed: ' .. tostring(e))
    end
end)

return m
