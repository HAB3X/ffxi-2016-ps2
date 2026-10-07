-----------------------------------
-- lan_natural: Legacy content that spawns by itself (report 32 §15). Data and the source of every value:
-- lan_natural_data.lua / work/b15_hidden/legacy/out/natural_sources.tsv (RETAIL 2009 wiki, LSB, APPROX, INVENTED).
--   * retired field monsters (Floating Eye, Canal Pugil, ...) in their zones with respawn timers and their drops
--   * Dynamis - Buburimu (2009): the six removed dragons roam again; every dragon (the four LSB still has too) disables
--     the Apocalyptic Beast's matching move when killed; all dragons despawn when the Beast dies; then the Nightmare
--     Cockatrice appears (3 clones when it aggroes)
--   * Dynamis - Valkurm: the Dragontrap (2 clones on aggro); while it lives Cirrate Christelle summons Nightmare Morbols
--   * Dynamis - Tavnazia: four Umbral Diabolos (true sight) - the one that aggroes calls a Diabolos suit and vanishes;
--     the Nightmare Antlion (1 of 4 places) gives +30 minutes
--   * the 27 never-released items drop from the monsters listed in itemDrops (INVENTED sources)
-- The GM commands (!legacyboss, !lanboss, !legacyitem) stay. Switch: NATURAL below.
-----------------------------------
require('modules/module_utils')
local D = require('modules/lan_legacy/lua/lan_natural_data')
-----------------------------------
local NATURAL = true

local m = Module:new('lan_natural', NATURAL)

xi = xi or {}
xi.lanNatural = xi.lanNatural or {}
local N = xi.lanNatural

-- extra (invented) item drops by monster name
local itemDropsBy = {}
for _, d in ipairs(D.itemDrops) do
    itemDropsBy[d.source] = itemDropsBy[d.source] or {}
    table.insert(itemDropsBy[d.source], d)
end

local function addDrops(mob, name, drops)
    mob:addListener('ITEM_DROPS', 'LAN_NATURAL_DROPS', function(mobArg, loot)
        for _, dr in ipairs(drops or {}) do
            loot:addItemFixed(dr[1], math.floor(dr[2] * 10 + 0.5))
        end

        for _, d in ipairs(itemDropsBy[name] or {}) do
            loot:addItemFixed(d.item, math.floor(d.chance * 10 + 0.5))
        end
    end)
end

-- yaml-only groups cannot be instantiated dynamically: map to a SQL stand-in (tools/build_group_map.py)
local okMap, resolveGroup = pcall(require, 'modules/lan_legacy/lua/lan_group_map')
if not okMap or type(resolveGroup) ~= 'function' then
    resolveGroup = function(group, zone)
        return group, zone, 0
    end
end

-- one dynamic monster; respawn > 0 keeps its id and LSB respawns it after that many seconds
N.spawn = function(zone, spec)
    local x, y, z = spec.pos[1], spec.pos[2], spec.pos[3]
    local respawn = spec.respawn or 0
    local groupId, groupZoneId, fixedHP = resolveGroup(spec.group, spec.groupZone, spec.name)
    local mob = zone:insertDynamicEntity({
        objtype              = xi.objType.MOB,
        name                 = spec.name,
        x = x, y = y, z = z, rotation = spec.rot or math.random(0, 255),
        look                 = spec.look,
        groupId              = groupId,
        groupZoneId          = groupZoneId,
        minLevel             = spec.minLevel,
        maxLevel             = spec.maxLevel,
        skillList            = spec.skillList or 0,
        respawn              = respawn,
        releaseIdOnDisappear = respawn == 0,
    })
    if not mob then
        print(string.format('[lan_natural] could not spawn %s in zone %d', spec.name, zone:getID()))
        return nil
    end

    mob:setSpawn(x, y, z, spec.rot or 0)
    mob:setDropID(0)   -- never the stand-in group's own loot; ours comes from the ITEM_DROPS listener

    addDrops(mob, spec.name, spec.drops)
    if fixedHP and fixedHP > 0 then
        -- the boss HP from LSB's template of the same monster type (applied on every spawn)
        mob:addListener('SPAWN', 'LAN_NATURAL_HP', function(mobArg)
            mobArg:setMaxHP(fixedHP)
            mobArg:setHP(mobArg:getMaxHP())
        end)
    end

    if respawn == 0 then
        DisallowRespawn(mob:getID(), true)
    end

    mob:spawn()
    return mob
end

-- field monsters ----------------------------------------------------------------------------------------------------
local fieldByZone = {}
for _, f in ipairs(D.field) do
    fieldByZone[f.zoneScript] = fieldByZone[f.zoneScript] or {}
    table.insert(fieldByZone[f.zoneScript], f)
end

local function placeField(zone, list)
    local n = 0
    for _, f in ipairs(list) do
        if f.group > 0 then
            for _, p in ipairs(f.pos) do
                if N.spawn(zone, { name = f.name, pos = p, look = f.look, group = f.group, groupZone = f.groupZone, minLevel = f.minLevel,
                    maxLevel = f.maxLevel, respawn = f.respawn, skillList = f.skillList, drops = f.drops, noStandInDrops = true }) then
                    n = n + 1
                end
            end
        end
    end

    print(string.format('[lan_natural] zone %d: %d retired field monsters placed', zone:getID(), n))
end

for zoneScript, list in pairs(fieldByZone) do
    m:addOverride(string.format('xi.zones.%s.Zone.onInitialize', zoneScript), function(zone)
        if super then
            super(zone)
        end

        placeField(zone, list)
    end)
end

-- helpers ----------------------------------------------------------------------------------------------------------
local function spawnClones(mob, count, spec)
    if mob:getLocalVar('lanClonesDone') == 1 then
        return
    end

    mob:setLocalVar('lanClonesDone', 1)
    local zone = mob:getZone()
    local t    = mob:getTarget()
    for k = 1, count do
        local c = N.spawn(zone, { name = spec.name, pos = { mob:getXPos() + k, mob:getYPos(), mob:getZPos() + k }, look = spec.look,
            group = spec.group, groupZone = spec.groupZone, minLevel = spec.minLevel, maxLevel = spec.maxLevel, skillList = spec.skillList })
        if c then
            c:setLocalVar('lanClonesDone', 1)
            if t then
                c:updateEnmity(t)
            end
        end
    end
end

-- Dynamis - Buburimu --------------------------------------------------------------------------------------------------
local B = D.dyn.buburimu
N.dragonMoveById = N.dragonMoveById or {}   -- dynamic dragon id -> index in D.dragons (its only move)
N.bubDragons     = N.bubDragons or {}

local function dragonKilled(zone, idx)
    zone:setLocalVar('lanAB_block_' .. D.dragons[idx].move, 1)
end

m:addOverride('xi.zones.Dynamis-Buburimu.Zone.onInitialize', function(zone)
    if super then
        super(zone)
    end

    N.bubDragons = {}
    for i, d in ipairs(D.dragons) do
        if d.legacy then
            local mob = N.spawn(zone, { name = d.name, pos = d.pos, look = d.look, group = B.dragonGroup, groupZone = B.zone, minLevel = 82,
                maxLevel = 83, respawn = 900, skillList = B.dragonSkill })
            if mob then
                N.dragonMoveById[mob:getID()] = i
                table.insert(N.bubDragons, mob:getID())
                mob:addListener('DEATH', 'LAN_DRAGON_DEATH', function(mobArg)
                    dragonKilled(zone, i)
                end)
            end
        end
    end

    -- the four dragons LSB still has lock the Beast's moves too (RETAIL 2009)
    for _, mob in pairs(zone:getMobs()) do
        for i, d in ipairs(D.dragons) do
            if not d.legacy and mob:getName() == d.name then
                table.insert(N.bubDragons, mob:getID())
                mob:addListener('DEATH', 'LAN_DRAGON_DEATH', function(mobArg)
                    dragonKilled(zone, i)
                end)
            end
        end
    end

    print(string.format('[lan_natural] Dynamis - Buburimu: %d dragons tracked', #N.bubDragons))
end)

-- a legacy dragon uses only its own move; the Beast loses every move whose dragon died (RETAIL 2009)
for i, d in ipairs(D.dragons) do
    m:addOverride(string.format('xi.actions.mobskills.%s.onMobSkillCheck', d.move), function(target, mob, skill)
        local dm = N.dragonMoveById[mob:getID()]
        if dm and dm ~= i then
            return 1
        end

        if mob:getName() == 'Apocalyptic_Beast' then
            local zone = mob:getZone()
            if zone and zone:getLocalVar('lanAB_block_' .. d.move) == 1 then
                return 1
            end
        end

        if super then
            return super(target, mob, skill)
        end

        return 0
    end)
end

m:addOverride('xi.zones.Dynamis-Buburimu.mobs.Apocalyptic_Beast.onMobSpawn', function(mob)
    if super then
        super(mob)
    end

    -- the invented drops (Excalibur) on the Beast
    mob:addListener('ITEM_DROPS', 'LAN_NATURAL_DROPS', function(mobArg, loot)
        for _, d in ipairs(itemDropsBy['Apocalyptic Beast'] or {}) do
            loot:addItemFixed(d.item, math.floor(d.chance * 10 + 0.5))
        end
    end)
end)

m:addOverride('xi.zones.Dynamis-Buburimu.mobs.Apocalyptic_Beast.onMobDeath', function(mob, player, optParams)
    if super then
        super(mob, player, optParams)
    end

    -- onMobDeath runs once per party member: act once (the killer, or nobody-killed)
    if optParams and not optParams.isKiller and not optParams.noKiller then
        return
    end

    local zone = mob:getZone()
    if not zone then
        return
    end

    -- every dragon still alive despawns (RETAIL); the move locks reset for the next run
    for _, id in ipairs(N.bubDragons) do
        local dm = GetMobByID(id)
        if dm and dm:isSpawned() then
            DespawnMob(id)
        end
    end

    for _, d in ipairs(D.dragons) do
        zone:setLocalVar('lanAB_block_' .. d.move, 0)
    end

    -- the Nightmare Cockatrice appears after the Beast (RETAIL 2009) and splits into 3 clones on aggro
    local spec = { name = 'Nightmare Cockatrice', pos = D.buburimuCockatrice, look = B.cockatriceLook, group = B.cockatriceGroup,
        groupZone = B.zone, minLevel = 78, maxLevel = 80, skillList = B.cockatriceSkill, drops = D.cockatriceDrops }
    local c = N.spawn(zone, spec)
    if c then
        c:addListener('ENGAGE', 'LAN_COCKATRICE_CLONES', function(mobArg, target)
            spawnClones(mobArg, 3, spec)
        end)
    end
end)

-- Dynamis - Valkurm ----------------------------------------------------------------------------------------------------
local V = D.dyn.valkurm

m:addOverride('xi.zones.Dynamis-Valkurm.Zone.onInitialize', function(zone)
    if super then
        super(zone)
    end

    local spec = { name = 'Dragontrap', pos = D.valkurmDragontrap, look = V.trapLook, group = V.trapGroup, groupZone = V.zone,
        minLevel = 78, maxLevel = 80, respawn = 900, skillList = V.trapSkill }
    local t = N.spawn(zone, spec)
    if t then
        t:addListener('ENGAGE', 'LAN_TRAP_CLONES', function(mobArg, target)
            spawnClones(mobArg, 2, { name = 'Dragontrap', look = V.trapLook, group = V.trapGroup, groupZone = V.zone,
                minLevel = 70, maxLevel = 72, skillList = V.trapSkill })
        end)
        t:addListener('DEATH', 'LAN_TRAP_DEATH', function(mobArg)
            zone:setLocalVar('lanDragontrapDead', 1)
        end)
        t:addListener('SPAWN', 'LAN_TRAP_SPAWN', function(mobArg)
            zone:setLocalVar('lanDragontrapDead', 0)
            mobArg:setLocalVar('lanClonesDone', 0)
        end)
    end
end)

-- Christelle summons Nightmare Morbols at 75% and 50% HP while the Dragontrap lives (moments APPROX)
m:addOverride('xi.zones.Dynamis-Valkurm.mobs.Cirrate_Christelle.onMobFight', function(mob, target)
    if super then
        super(mob, target)
    end

    local z = mob:getZone()
    if not z or z:getLocalVar('lanDragontrapDead') == 1 then
        return
    end

    for _, pct in ipairs({ 75, 50 }) do
        local key = 'lanMorbol' .. pct
        if mob:getHPP() <= pct and mob:getLocalVar(key) == 0 then
            mob:setLocalVar(key, 1)
            local mm = N.spawn(z, { name = 'Nightmare Morbol', pos = { mob:getXPos() + 2, mob:getYPos(), mob:getZPos() + 2 }, look = V.morbolLook,
                group = V.trapGroup, groupZone = V.zone, minLevel = 78, maxLevel = 80, skillList = V.morbolSkill })
            if mm and target then
                mm:updateEnmity(target)
            end
        end
    end
end)

-- Dynamis - Tavnazia ---------------------------------------------------------------------------------------------------
local T = D.dyn.tavnazia

m:addOverride('xi.zones.Dynamis-Tavnazia.Zone.onInitialize', function(zone)
    if super then
        super(zone)
    end

    for k = 1, 4 do
        local u = N.spawn(zone, { name = 'Umbral Diabolos', pos = D.tavnaziaPoints[k], look = T.umbralLook, group = T.umbralGroup,
            groupZone = T.zone, minLevel = 80, maxLevel = 80, respawn = 3600 })   -- back an hour later (APPROX: retail = every run)
        if u then
            u:setMobMod(xi.mobMod.DETECTION, xi.detects.SIGHT)   -- true sight (RETAIL)
            u:addListener('ENGAGE', 'LAN_UMBRAL', function(mobArg, target)
                -- call one Diabolos suit that is not up yet, then vanish (RETAIL)
                for _, sid in ipairs(T.suits) do
                    local s = GetMobByID(sid)
                    if s and not s:isSpawned() then
                        s:setSpawn(mobArg:getXPos(), mobArg:getYPos(), mobArg:getZPos(), mobArg:getRotPos())
                        SpawnMob(sid)
                        if target then
                            s:updateEnmity(target)
                        end

                        break
                    end
                end

                DespawnMob(mobArg:getID())
            end)
        end
    end

    local a = N.spawn(zone, { name = 'Nightmare Antlion', pos = D.tavnaziaPoints[math.random(1, 4)], look = T.antlionLook,
        group = T.antlionGroup, groupZone = T.zone, minLevel = 80, maxLevel = 82, respawn = 3600, skillList = T.antlionSkill })
    if a then
        -- next time it comes back at another of the four places (RETAIL: one of four, at random)
        a:addListener('DESPAWN', 'LAN_ANTLION_MOVE', function(mobArg)
            local p = D.tavnaziaPoints[math.random(1, 4)]
            mobArg:setSpawn(p[1], p[2], p[3], 0)
        end)

        a:addListener('DEATH', 'LAN_ANTLION_TE', function(mobArg)
            -- +30 minutes for everyone in Dynamis here (RETAIL)
            for _, pl in pairs(zone:getPlayers()) do
                local eff = pl:getStatusEffect(xi.effect.DYNAMIS)
                if eff and pl:getLocalVar('lanAntlionTE') == 0 then
                    -- same steps as xi.dynamis.timeExtensionOnDeath
                    pl:setLocalVar('lanAntlionTE', 1)
                    eff:setDuration(eff:getDuration() + 30 * 60 * 1000)
                    pl:setLocalVar('dynamis_lasttimeupdate', eff:getTimeRemaining() / 1000)
                    local ID = zones[zone:getID()]
                    if ID and ID.text and ID.text.DYNAMIS_TIME_EXTEND then
                        pl:messageSpecial(ID.text.DYNAMIS_TIME_EXTEND, 30)
                    end
                end
            end
        end)
    end
end)
