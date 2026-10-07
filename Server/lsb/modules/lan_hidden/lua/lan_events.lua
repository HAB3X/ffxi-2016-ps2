-----------------------------------
-- lan_events: force LSB's seasonal events on for LAN night, independent of the date (report 32).
-- Switches: lan_hidden_config.lua. Undo: remove the 'lan_hidden' line from modules/init.txt (or run
-- work/b15_hidden/enable/lsb/revert_lan_hidden.sh) and restart the map server.
-----------------------------------
require('modules/module_utils')
local cfg = require('modules/lan_hidden/lua/lan_hidden_config')
-----------------------------------
local m = Module:new('lan_events')

local forcedIds =
{
    StarlightCelebration = cfg.FORCE_STARLIGHT_CELEBRATION,
    egg_hunt             = cfg.FORCE_EGG_HUNT,
}

-- The SeasonalEvent objects keep their own copy of the enable check, so set it on the objects themselves.
local function forceSeasonalEvents()
    for _, event in pairs(xi.events.registeredEvents or {}) do
        if forcedIds[event.id] then
            event:setEnableCheck(function()
                return true
            end)
            print(string.format('[lan_events] seasonal event forced on: %s', event.id))
        end
    end
end

local function applySettings()
    if cfg.FORCE_HARVEST_FESTIVAL then
        xi.settings.main.HALLOWEEN_2005       = 1
        xi.settings.main.HALLOWEEN_YEAR_ROUND = 1
    end

    if cfg.FORCE_EGG_HUNT and xi.settings.main.EGG_HUNT then
        -- same table object the egg hunt script captured at load time, so field changes are seen
        for k, v in pairs(cfg.EGG_HUNT_ERAS or {}) do
            xi.settings.main.EGG_HUNT[k] = v
        end
    end
end

m:addOverride('xi.server.onServerStart', function()
    applySettings()
    forceSeasonalEvents()
    super()
end)

m:addOverride('xi.server.onJSTMidnight', function()
    applySettings()
    forceSeasonalEvents()
    super()
end)

-- Code paths that call the checks directly (egg hunt moogle, harvest trades) instead of the event object.
m:addOverride('xi.events.eggHunt.enabledCheck', function()
    if cfg.FORCE_EGG_HUNT then
        return true
    end

    return super()
end)

m:addOverride('xi.events.starlightCelebration.enabledCheck', function()
    if cfg.FORCE_STARLIGHT_CELEBRATION then
        return true
    end

    return super()
end)

m:addOverride('xi.events.harvestFestival.isHalloweenEnabled', function()
    if cfg.FORCE_HARVEST_FESTIVAL then
        return 1
    end

    return super()
end)
