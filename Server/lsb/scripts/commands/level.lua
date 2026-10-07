-----------------------------------
-- func: level <level> (player)
-- desc: Sets your (or a player's) main job level. Same as !setplayerlevel.
-- note: added for the PS2 LAN server admin table (research/reports/26_multiplayer.md, section 6); calls !setplayerlevel.
-----------------------------------
---@type TCommand
local commandObj = {}

commandObj.cmdprops =
{
    permission = 1,
    parameters = 'ss'
}

commandObj.onTrigger = function(player, ...)
    local base = xi.commands and xi.commands['setplayerlevel']
    if not base then
        player:printToPlayer('!level: the !setplayerlevel command is not loaded.')
        return
    end

    return base.onTrigger(player, ...)
end

return commandObj
