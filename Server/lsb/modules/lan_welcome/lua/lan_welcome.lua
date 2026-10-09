-----------------------------------
-- lan_welcome (FFXI 2016 Server App, Fan Project by Habex): a welcome message that goes to the player who just logged in,
-- and only to that player (nobody else sees it).
--
-- The Server App writes <data dir>/app_server.lua:
--     return { name = 'My World', welcome = 'Welcome to {server}, {player}!' }
-- {player} becomes the character's name and {server} the server name. The file is read at every login, so a changed message
-- applies without a restart. An empty message sends nothing. Undo: remove "lan_welcome" from modules/init.txt.
-----------------------------------
require('modules/module_utils')
-----------------------------------
local m = Module:new('lan_welcome')

local FILE = (os.getenv('FFXI_DATA_DIR') or '.') .. '/app_server.lua'
local LINE = 90 -- the chat window wraps long lines badly, so a long message goes out as several lines

local function readConfig()
    local f = io.open(FILE, 'rb')
    if not f then
        return nil
    end

    local txt = f:read('*a') or ''
    f:close()
    local chunk = loadstring(txt)
    if not chunk then
        return nil
    end

    local ok, data = pcall(chunk)
    if ok and type(data) == 'table' then
        return data
    end

    return nil
end

local function lines(text)
    local out = {}
    local cur = ''
    for word in text:gmatch('%S+') do
        if cur ~= '' and #cur + 1 + #word > LINE then
            out[#out + 1] = cur
            cur = word
        else
            cur = (cur == '') and word or (cur .. ' ' .. word)
        end
    end

    if cur ~= '' then
        out[#out + 1] = cur
    end

    return out
end

m:addOverride('xi.player.onGameIn', function(player, firstLogin, zoning)
    super(player, firstLogin, zoning)

    if zoning then
        return
    end

    player:timer(5000, function(playerArg)
        local cfg = readConfig()
        if cfg == nil or type(cfg.welcome) ~= 'string' or cfg.welcome == '' then
            return
        end

        local text = cfg.welcome:gsub('{player}', function() return playerArg:getName() end):gsub('{server}', function() return tostring(cfg.name or '') end)
        for _, l in ipairs(lines(text)) do
            playerArg:printToPlayer(' ' .. l, xi.msg.channel.SYSTEM_3, '')
        end
    end)
end)

return m
