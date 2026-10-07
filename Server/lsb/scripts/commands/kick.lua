-----------------------------------
-- func: kick <player>
-- desc: Logs a player off. Same as !logoff.
-- note: added for the PS2 LAN server admin table (research/reports/26_multiplayer.md, section 6); calls !logoff.
-----------------------------------
---@type TCommand
local commandObj = {}

commandObj.cmdprops =
{
    permission = 1,
    parameters = 's'
}

commandObj.onTrigger = function(player, ...)
    local base = xi.commands and xi.commands['logoff']
    if not base then
        player:printToPlayer('!kick: the !logoff command is not loaded.')
        return
    end

    return base.onTrigger(player, ...)
end

return commandObj
