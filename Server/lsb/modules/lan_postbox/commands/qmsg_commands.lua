-----------------------------------
-- lan_postbox chat commands: the 2001 beta's quick messages (//qmw //qmr //qmp //qmc, message of the day) and a
-- test helper for the retail Delivery Box. Report 40.
--   !qmw <name> <text>   write a quick message to a character (online or not)   (beta //qmw)
--   !qmr                 read the oldest message and remove it                    (beta //qmr)
--   !qmp                 peek at the oldest message, keep it                      (beta //qmp)
--   !qmc                 how many messages are waiting                            (beta //qmc)
--   !qmclear             delete all of your waiting messages                      (new)
--   !qmm                 message of the day                                       (beta packet 0x49)
--   !postgift <name> <gil|itemid> <qty> [text]   GM only: put gil or an item in a character's Delivery Box
-----------------------------------
require('modules/module_utils')
local lp = require('modules/lan_postbox/lua/lan_postbox')
local R  = lp.core.RESULT
-----------------------------------

local function usage(player, text)
    lp.tell(player, text)
end

---@type TCommand
local qmw = { cmdprops = { permission = 0, parameters = 's' } }
qmw.onTrigger = function(player, arg)
    local name, text = (arg or ''):match('^%s*(%S+)%s+(.+)$')
    if name == nil then
        usage(player, 'Usage: !qmw <name> <text>')
        return
    end

    local res = lp.write(player, name, text)
    if res == R.OK then
        lp.tell(player, string.format('Quick message sent to %s.', name))
    elseif res == R.NO_RECIPIENT then
        lp.tell(player, string.format('( target address NOT exist: %s )', name)) -- beta wording for result -5
    elseif res == R.BOX_FULL then
        lp.tell(player, string.format('( target box full: %s )', name))          -- beta wording for result -2
    else
        lp.tell(player, 'Usage: !qmw <name> <text>')
    end
end

xi.module.registerCommand('qmw', qmw)

local function show(player, msg)
    lp.tell(player, string.format('MSG From:%s  %s', msg.from, msg.text))
    lp.tell(player, string.format(' %d message(s) arrived.', msg.left))
end

---@type TCommand
local qmr = { cmdprops = { permission = 0, parameters = '' } }
qmr.onTrigger = function(player)
    local res, msg = lp.read(player)
    if res == R.OK then
        show(player, msg)
    else
        lp.tell(player, '( NOTHING arrived in post )') -- beta wording for result -22
    end
end

xi.module.registerCommand('qmr', qmr)

---@type TCommand
local qmp = { cmdprops = { permission = 0, parameters = '' } }
qmp.onTrigger = function(player)
    local res, msg = lp.peek(player)
    if res == R.OK then
        show(player, msg)
    else
        lp.tell(player, '( NOTHING arrived in post )')
    end
end

xi.module.registerCommand('qmp', qmp)

---@type TCommand
local qmc = { cmdprops = { permission = 0, parameters = '' } }
qmc.onTrigger = function(player)
    lp.tell(player, string.format(' %d message(s) arrived.', lp.count(player)))
end

xi.module.registerCommand('qmc', qmc)

---@type TCommand
local qmclear = { cmdprops = { permission = 0, parameters = '' } }
qmclear.onTrigger = function(player)
    lp.tell(player, string.format('%d quick message(s) deleted.', lp.clear(player)))
end

xi.module.registerCommand('qmclear', qmclear)

---@type TCommand
local qmm = { cmdprops = { permission = 0, parameters = '' } }
qmm.onTrigger = function(player)
    lp.tell(player, lp.motdText())
end

xi.module.registerCommand('qmm', qmm)

-- GM helper: the retail Delivery Box has no "send as the server" path, this uses LSB's own SendItemToDeliveryBox.
---@type TCommand
local postgift = { cmdprops = { permission = 1, parameters = 'ssis' } }
postgift.onTrigger = function(player, name, what, qty, text)
    if name == nil or what == nil then
        lp.tell(player, 'Usage: !postgift <name> <gil|itemid> <qty> [sender text]')
        return
    end

    local itemId = (what == 'gil') and 65535 or tonumber(what)
    if itemId == nil or itemId < 1 or itemId > 65535 then
        lp.tell(player, 'Usage: !postgift <name> <gil|itemid> <qty> [sender text]')
        return
    end

    local rc = SendItemToDeliveryBox(name, itemId, math.max(qty or 1, 1), text or player:getName())
    lp.tell(player, string.format('SendItemToDeliveryBox(%s, %d, %d) -> %s (0 = ok, 2 = no such player, 3 = no such item)', name, itemId, math.max(qty or 1, 1), tostring(rc)))
end

xi.module.registerCommand('postgift', postgift)
