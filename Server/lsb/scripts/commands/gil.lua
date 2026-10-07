-----------------------------------
-- func: gil <amount> (player)
-- desc: Gives gil to you or a player. Same as !givegil (!setgil / !takegil also exist).
-- note: added for the PS2 LAN server admin table (research/reports/26_multiplayer.md, section 6); calls !givegil.
-----------------------------------
---@type TCommand
local commandObj = {}

commandObj.cmdprops =
{
    permission = 1,
    parameters = 'is'
}

commandObj.onTrigger = function(player, ...)
    local base = xi.commands and xi.commands['givegil']
    if not base then
        player:printToPlayer('!gil: the !givegil command is not loaded.')
        return
    end

    return base.onTrigger(player, ...)
end

return commandObj
