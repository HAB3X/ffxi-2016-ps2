-----------------------------------
-- func: invisible (status)
-- desc: Hides the GM from other players; type it again to be visible (a toggle). Same as !hide.
-- note: added for the PS2 LAN server admin table (research/reports/26_multiplayer.md, section 6); calls !hide.
-----------------------------------
---@type TCommand
local commandObj = {}

commandObj.cmdprops =
{
    permission = 1,
    parameters = 's'
}

commandObj.onTrigger = function(player, ...)
    local base = xi.commands and xi.commands['hide']
    if not base then
        player:printToPlayer('!invisible: the !hide command is not loaded.')
        return
    end

    return base.onTrigger(player, ...)
end

return commandObj
