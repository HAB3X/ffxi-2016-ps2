-----------------------------------
-- func: serverinfo
-- desc: Shows server time, zone uptime and who is online.
-- note: added for the PS2 LAN server admin table (research/reports/26_multiplayer.md, section 6).
-----------------------------------
---@type TCommand
local commandObj = {}

commandObj.cmdprops =
{
    permission = 1,
    parameters = ''
}

commandObj.onTrigger = function(player)
    local names = {}
    for zoneId = 0, 300 do
        local zone = GetZone(zoneId)
        if zone then
            for _, pc in pairs(zone:getPlayers()) do
                table.insert(names, string.format('%s (%s)', pc:getName(), zone:getName()))
            end
        end
    end

    local zone = player:getZone()
    local up   = zone and zone:getUptime() or 0
    player:printToPlayer(string.format('Server time %s. This zone has been up %d min.', os.date('%Y-%m-%d %H:%M:%S'), math.floor(up / 60)), xi.msg.channel.SYSTEM_3)
    player:printToPlayer(string.format('%d online: %s', #names, table.concat(names, ', ')), xi.msg.channel.SYSTEM_3)
end

return commandObj
