describe('Repair', function()
    ---@type CClientEntityPair
    local player
    ---@type CClientEntityPair
    local syncTarget

    before_each(function()
        player = xi.test.world:spawnPlayer(
            {
                job   = xi.job.PUP,
                level = 75,
                zone  = xi.zone.SOUTHERN_SAN_DORIA,
            })

        syncTarget = xi.test.world:spawnPlayer(
            {
                job   = xi.job.WAR,
                level = 20,
                zone  = xi.zone.SOUTHERN_SAN_DORIA,
            })

        player:unlockAttachment(xi.item.HARLEQUIN_FRAME)
        player:unlockAttachment(xi.item.HARLEQUIN_HEAD)
    end)

    local function useRepairWith(oilId)
        player:addItem(oilId, 12)
        player:equipItem(oilId)

        player.actions:inviteToParty(syncTarget)
        syncTarget.actions:acceptPartyInvite()
        player.actions:setLevelSync(syncTarget)
        assert(player:getMainLvl() == 20, string.format('expected sync to 20, level=%d', player:getMainLvl()))

        player:spawnPet(xi.petId.AUTOMATON)
        local pet = player:getPet()
        assert(pet)

        pet:setHP(1)
        player.actions:useAbility(player, xi.jobAbility.REPAIR)
        xi.test.world:tick()

        return pet
    end

    it('heals the automaton with an oil at or below the synced level', function()
        local pet      = useRepairWith(xi.item.CAN_OF_AUTOMATON_OIL)
        local oilsLeft = player:getItemCount(xi.item.CAN_OF_AUTOMATON_OIL)

        assert(pet:getHP() > 1, string.format('expected repair to heal, pet HP=%d', pet:getHP()))
        assert(oilsLeft == 11, string.format('expected one oil consumed, count=%d', oilsLeft))
    end)

    it('refuses an oil above the synced level', function()
        local pet      = useRepairWith(xi.item.CAN_OF_AUTOMATON_OIL_P2)
        local oilsLeft = player:getItemCount(xi.item.CAN_OF_AUTOMATON_OIL_P2)

        assert(pet:getHP() == 1, string.format('expected repair to be refused, pet HP=%d', pet:getHP()))
        assert(oilsLeft == 12, string.format('expected no oil consumed, count=%d', oilsLeft))
    end)
end)
