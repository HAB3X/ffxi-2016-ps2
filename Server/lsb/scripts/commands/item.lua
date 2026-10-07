-----------------------------------
-- func: item <itemId or name> (quantity)
-- desc: Gives you an item. Same as !additem.
-- note: added for the PS2 LAN server admin table (research/reports/26_multiplayer.md, section 6); calls !additem.
-----------------------------------
---@type TCommand
local commandObj = {}

commandObj.cmdprops =
{
    permission = 1,
    parameters = 'siiiiiiiiii'
}

commandObj.onTrigger = function(player, ...)
    local base = xi.commands and xi.commands['additem']
    if not base then
        player:printToPlayer('!item: the !additem command is not loaded.')
        return
    end

    return base.onTrigger(player, ...)
end

return commandObj
