-----------------------------------
-- func: spawn <mob id> (despawn time) (respawn time)
-- desc: Spawns a mob by id. Same as !spawnmob.
-- note: added for the PS2 LAN server admin table (research/reports/26_multiplayer.md, section 6); calls !spawnmob.
-----------------------------------
---@type TCommand
local commandObj = {}

commandObj.cmdprops =
{
    permission = 1,
    parameters = 'iii'
}

commandObj.onTrigger = function(player, ...)
    local base = xi.commands and xi.commands['spawnmob']
    if not base then
        player:printToPlayer('!spawn: the !spawnmob command is not loaded.')
        return
    end

    return base.onTrigger(player, ...)
end

return commandObj
