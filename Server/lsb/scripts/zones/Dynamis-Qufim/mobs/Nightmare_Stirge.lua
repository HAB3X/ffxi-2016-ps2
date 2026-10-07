-----------------------------------
-- Area: Dynamis - Qufim
--  Mob: Nightmare Stirge
-----------------------------------
mixins = { require('scripts/mixins/dynamis_dreamland') }
-----------------------------------
---@type TMobEntity
local entity = {}

entity.onMobSpawn = function(mob)
    xi.dynamis.mobInfo(mob)
    mob:setLocalVar('dynamis_currency', 1452)
end

entity.onMobMobskillChoose = function(mob, target, skillId)
    local skillList =
    {
        xi.mobSkill.ULTRASONICS_2,
        xi.mobSkill.BLOOD_DRAIN_2,
    }

    return skillList[math.randomInt(1, #skillList)]
end

return entity
