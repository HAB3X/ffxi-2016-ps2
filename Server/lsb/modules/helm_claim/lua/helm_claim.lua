-----------------------------------
-- HELM Claim
-----------------------------------
-- Based on the "helm_claim" module by LoxleyXI (https://github.com/LoxleyXI/Modules), GPL-3.0.
-- Changed for this server's LandSandBoat: the tool and gathering type come from xi.helm.dataTable, messages use printToPlayer,
-- time comes from GetSystemTime. Not changed in spirit: a gathering point is "claimed" for a few seconds by the first player who
-- uses it, so two players do not take turns on the same point by accident.
-- Switch it on or off in the Server App (World > Modes); it needs a server restart.
-----------------------------------
require('modules/module_utils')
-----------------------------------
local m = Module:new('helm_claim')

local claim =
{
    MESSAGE = 'Another player is currently using this.',
    DURATION = 10, -- seconds
}

if xi.settings[m.name] then
    claim.MESSAGE  = xi.settings[m.name].MESSAGE or claim.MESSAGE
    claim.DURATION = xi.settings[m.name].CLAIM_DURATION or claim.DURATION
end

m:addOverride('xi.helm.onTrade', function(player, npc, trade, helmType, csid, func)
    local info = xi.helm.dataTable[helmType]
    local now  = GetSystemTime()

    if
        now < npc:getLocalVar('[HELM]ClaimUntil') and
        player:getID() ~= npc:getLocalVar('[HELM]ClaimedBy')
    then
        player:printToPlayer(claim.MESSAGE, xi.msg.channel.SYSTEM_3)
        return
    end

    if info and trade:hasItemQty(info.tool, 1) and trade:getItemCount() == 1 then
        npc:setLocalVar('[HELM]ClaimUntil', now + claim.DURATION)
        npc:setLocalVar('[HELM]ClaimedBy', player:getID())
    end

    super(player, npc, trade, helmType, csid, func)
end)
