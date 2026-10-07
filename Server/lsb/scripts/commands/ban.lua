-----------------------------------
-- func: ban <player> (reason)
-- desc: Bans a player from playing: sends them to jail (Mordion Gaol) and logs them off. They log back in inside the
--       jail; !pardon <player> (while they are online) lets them out.
-- note: added for the PS2 LAN server admin table (research/reports/26_multiplayer.md, section 6).
--       Lua cannot change the accounts table; an account-level ban is: UPDATE accounts SET status = 2 WHERE login = '<name>';
--       (see the report). Jail works for online and offline characters on this server.
-----------------------------------
---@type TCommand
local commandObj = {}

commandObj.cmdprops =
{
    permission = 1,
    parameters = 'ss'
}

commandObj.onTrigger = function(player, target, reason)
    if not target then
        player:printToPlayer('!ban <player> (reason)   - once they log back in, !pardon <player> lets them out')
        return
    end

    local jail = xi.commands and xi.commands['jail']
    if not jail then
        player:printToPlayer('!ban: the !jail command is not loaded.')
        return
    end

    jail.onTrigger(player, target, 1, reason or 'banned by GM')
    local targ = GetPlayerByName(target)
    if targ then
        targ:leaveGame()
    end

    player:printToPlayer(string.format('%s is banned (jailed%s).', target, targ and ' and logged off' or ''))
end

return commandObj
