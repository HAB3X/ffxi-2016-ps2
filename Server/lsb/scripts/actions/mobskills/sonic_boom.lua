-----------------------------------
-- Sonic Boom
-- Reduces attack of targets in area of effect.
-----------------------------------
---@type TMobSkill
local mobskillObject = {}

mobskillObject.onMobSkillCheck = function(target, mob, skill)
    return 0
end

mobskillObject.onMobWeaponSkill = function(mob, target, skill, action)
    if target:hasStatusEffect(xi.effect.ATTACK_DOWN) then
        skill:setMsg(xi.msg.basic.SKILL_NO_EFFECT)
    else
        local duration = xi.mobskills.calculateDuration(skill:getTP(), 180, 540)

        skill:setMsg(xi.mobskills.mobStatusEffectMove(mob, target, xi.effect.ATTACK_DOWN, 25, 0, duration))

        return xi.effect.ATTACK_DOWN
    end
end

return mobskillObject
