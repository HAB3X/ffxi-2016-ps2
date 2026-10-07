-----------------------------------
-- func: reload <globals file>
-- desc: Reloads a Lua file from scripts/globals. Same as !reloadglobal (see also !reloadquest, !reloadinteraction).
-- note: added for the PS2 LAN server admin table (research/reports/26_multiplayer.md, section 6); calls !reloadglobal.
-----------------------------------
---@type TCommand
local commandObj = {}

commandObj.cmdprops =
{
    permission = 1,
    parameters = 'ss'
}

commandObj.onTrigger = function(player, ...)
    local base = xi.commands and xi.commands['reloadglobal']
    if not base then
        player:printToPlayer('!reload: the !reloadglobal command is not loaded.')
        return
    end

    return base.onTrigger(player, ...)
end

return commandObj
