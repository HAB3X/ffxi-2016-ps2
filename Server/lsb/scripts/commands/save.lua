-----------------------------------
-- func: save
-- desc: Explains LSB's automatic saving (there is no manual save step).
-- note: added for the PS2 LAN server admin table (research/reports/26_multiplayer.md, section 6).
--       LSB already saves by itself: items, gil, experience, quests and key items are written the moment they
--       change; position, equipment and status effects every 5 seconds and at logout/shutdown (persist sweep).
--       So there is nothing to force; this command tells the GM what is saved when.
-----------------------------------
---@type TCommand
local commandObj = {}

commandObj.cmdprops =
{
    permission = 1,
    parameters = ''
}

commandObj.onTrigger = function(player)
    player:printToPlayer('Saved: items, gil, EXP and quests are already in the database; position/equipment follow within 5 seconds.')
end

return commandObj
