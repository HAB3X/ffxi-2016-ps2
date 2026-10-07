-----------------------------------
-- func: kill (player)
-- desc: Kills your current target (a monster or player), or the named player.
-- note: added for the PS2 LAN server admin table (research/reports/26_multiplayer.md, section 6).
-----------------------------------
---@type TCommand
local commandObj = {}

commandObj.cmdprops =
{
    permission = 1,
    parameters = 's'
}

local function error(player, msg)
    player:printToPlayer(msg)
    player:printToPlayer('!kill (player)   - without a name it kills your current target')
end

commandObj.onTrigger = function(player, target)
    local targ

    if target then
        targ = GetPlayerByName(target)
        if not targ then
            error(player, string.format('Player named "%s" not found!', target))
            return
        end
    else
        targ = player:getCursorTarget()
        if not targ or targ:isNPC() then
            error(player, 'Target a monster or player first.')
            return
        end
    end

    if not targ:isAlive() then
        player:printToPlayer(string.format('%s is already dead.', targ:getName()))
        return
    end

    targ:setHP(0)
    player:printToPlayer(string.format('Killed %s.', targ:getName()))
end

return commandObj
