-----------------------------------
-- Oztroja Escape
-----------------------------------
-- Based on the "oztroja_escape" module by LoxleyXI (https://github.com/LoxleyXI/Modules), GPL-3.0.
-- Changed for this server: the original asks a yes/no question with player:customMenu, which the PS2 game cannot show, so using
-- the hole now says a line and lets the player through at once. The hole is an invisible "???" point.
-- Without this, nobody can leave the top floor of Castle Oztroja except with a Judgment Key, which cannot be found there.
-- Switch it on or off in the Server App (World > Modes); it needs a server restart.
-----------------------------------
require('modules/module_utils')
-----------------------------------
local m = Module:new('oztroja_escape')

local config =
{
    npcPos    = { -107.942, -54.000, 12.714 },
    escapePos = { -129.568, -25.880,  3.566 },
    message   = 'It looks dangerous, but you squeeze through the hole and escape.',
}

m:addOverride('xi.zones.Castle_Oztroja.Zone.onInitialize', function(zone)
    super(zone)

    zone:insertDynamicEntity({
        objtype   = xi.objType.NPC,
        name      = '???',
        x         = config.npcPos[1],
        y         = config.npcPos[2],
        z         = config.npcPos[3],
        widescan  = 0,
        onTrigger = function(player, npc)
            player:printToPlayer(config.message, xi.msg.channel.NS_SAY)
            player:setPos(config.escapePos[1], config.escapePos[2], config.escapePos[3], 0, xi.zone.CASTLE_OZTROJA)
        end,
    })
end)
