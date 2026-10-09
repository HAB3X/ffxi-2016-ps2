-----------------------------------
-- hardcore_mode (FFXI 2016 Server App, Fan Project by Habex): a character that falls cannot come back.
--
-- The Server App writes <data dir>/hardcore.lua:   return { on = true, lives = 1 }
-- With "on", every death counts. When a character has died "lives" times it is marked fallen: everyone gets a server message, the
-- character is logged out, and it cannot log in again. Nothing is deleted: the Server App lists fallen characters and can restore
-- them. GMs are exempt. The file is read at every death and login, so switching it on or off needs no restart.
-- The module is always loaded and does nothing while the mode is off.
-----------------------------------
require('modules/module_utils')
-----------------------------------
local m = Module:new('hardcore_mode')

local FILE = (os.getenv('FFXI_DATA_DIR') or '.') .. '/hardcore.lua'

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
    if ok and type(data) == 'table' and data.on == true then
        return data
    end

    return nil
end

m:addOverride('xi.player.onPlayerDeath', function(player)
    super(player)

    local cfg = readConfig()
    if cfg == nil or player:getGMLevel() > 0 then
        return
    end

    local lives  = math.max(1, math.floor(tonumber(cfg.lives) or 1))
    local deaths = player:getCharVar('HC_deaths') + 1
    player:setCharVar('HC_deaths', deaths)

    if deaths >= lives then
        player:setCharVar('HC_fallen', 1)
        player:printToArea(string.format('%s has fallen in hardcore mode.', player:getName()), xi.msg.channel.SYSTEM_3, xi.msg.area.SYSTEM, '')
        player:printToPlayer('Your journey ends here. This character cannot log in again.', xi.msg.channel.SYSTEM_3, '')
        player:timer(8000, function(playerArg)
            playerArg:leaveGame()
        end)
    else
        local left = lives - deaths
        player:printToPlayer(string.format('Hardcore: %d %s left.', left, left == 1 and 'life' or 'lives'), xi.msg.channel.SYSTEM_3, '')
    end
end)

m:addOverride('xi.player.onGameIn', function(player, firstLogin, zoning)
    super(player, firstLogin, zoning)

    if zoning or readConfig() == nil or player:getGMLevel() > 0 then
        return
    end

    if player:getCharVar('HC_fallen') == 1 then
        player:timer(3000, function(playerArg)
            playerArg:printToPlayer('This character has fallen in hardcore mode and cannot play any more.', xi.msg.channel.SYSTEM_3, '')
            playerArg:timer(5000, function(p)
                p:leaveGame()
            end)
        end)
    end
end)

return m
