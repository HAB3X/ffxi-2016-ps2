-----------------------------------
-- lan_postbox: tell a player at login how many quick messages are waiting (beta: " %d message(s) arrived."),
-- plus the message of the day if one is set in lan_postbox_config.lua.
-----------------------------------
require('modules/module_utils')
local lp = require('modules/lan_postbox/lua/lan_postbox')
-----------------------------------
local m = Module:new('lan_postbox_login', lp.cfg.loginNotice == true)

m:addOverride('xi.player.onGameIn', function(player, firstLogin, zoning)
    super(player, firstLogin, zoning)

    if not zoning then
        player:timer(4000, function(playerArg)
            local n = lp.count(playerArg)
            if n > 0 then
                lp.tell(playerArg, string.format(' %d message(s) arrived. Type !qmr to read.', n))
            end

            if lp.cfg.motd ~= nil and lp.cfg.motd ~= '' then
                lp.tell(playerArg, lp.motdText())
            end
        end)
    end
end)
