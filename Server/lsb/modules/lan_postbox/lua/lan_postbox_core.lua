-----------------------------------
-- lan_postbox core: the beta's "quick message" (QMSG) mailbox, as pure Lua over a char-variable store.
--
-- The 2001 JP beta (and the 2002 launch build) had //qmw (write), //qmr (read), //qmp (peek), //qmc (count) and
-- a message of the day, over c2s/s2c packets 0x46-0x4A (report 40 section 5). The game programs from 2003 on have none of that
-- code, so here the same semantics are offered as server chat commands (see commands/qmsg_commands.lua).
--
-- This file has NO dependency on the LandSandBoat Lua API. The caller passes a store:
--     store.get(charid, varname) -> integer (0 when unset)
--     store.set(charid, varname, value)      (value 0 deletes the variable)
-- so it can be unit-tested with plain LuaJIT (work/b44_postbox/tests/test_qmsg_core.lua).
--
-- Storage (all in the recipient's char_vars; value 0 = row deleted = "unset"):
--     [QM]<k>t      commit stamp (seconds). Non-zero = slot k holds a message. Written LAST, cleared FIRST.
--     [QM]<k>l      body length in bytes
--     [QM]<k>b<j>   body, 3 bytes per variable (little-endian), j = 1..ceil(len/3)
--     [QM]<k>n<j>   sender name, 3 bytes per variable, j = 1..5 (15 characters, the FFXI name limit)
--     [QM]<k>s      sequence (monotonic per mailbox) so two messages in the same second keep their order
--     [QM]seq       the mailbox sequence counter
-----------------------------------
local M = {}

M.RESULT =
{
    OK            = 'ok',
    NO_RECIPIENT  = 'no_recipient',
    BOX_FULL      = 'box_full',
    EMPTY         = 'empty',
    BAD_TEXT      = 'bad_text',
}

local NAME_CHUNKS = 5

local function key(slot, suffix)
    return string.format('[QM]%d%s', slot, suffix)
end

local function packBytes(str, first, last)
    local v, mul = 0, 1
    for i = first, last do
        local b = str:byte(i) or 0
        v = v + b * mul
        mul = mul * 256
    end

    return v
end

local function unpackBytes(v, count)
    local out = {}
    for _ = 1, count do
        out[#out + 1] = string.char(v % 256)
        v = math.floor(v / 256)
    end

    return table.concat(out)
end

local function writeString(store, charid, slot, prefix, str, maxChunks)
    local n = 0
    for j = 1, maxChunks do
        local first = (j - 1) * 3 + 1
        if first > #str then
            break
        end

        store.set(charid, key(slot, prefix .. j), packBytes(str, first, math.min(first + 2, #str)))
        n = n + 1
    end

    return n
end

local function readString(store, charid, slot, prefix, len, maxChunks)
    local parts = {}
    local chunks = math.min(math.ceil(len / 3), maxChunks)
    for j = 1, chunks do
        local remaining = len - (j - 1) * 3
        parts[#parts + 1] = unpackBytes(store.get(charid, key(slot, prefix .. j)), math.min(3, remaining))
    end

    return table.concat(parts)
end

local function clearSlot(store, charid, slot, bodyLen)
    store.set(charid, key(slot, 't'), 0) -- invisible first
    for j = 1, math.ceil(bodyLen / 3) do
        store.set(charid, key(slot, 'b' .. j), 0)
    end

    for j = 1, NAME_CHUNKS do
        store.set(charid, key(slot, 'n' .. j), 0)
    end

    store.set(charid, key(slot, 'l'), 0)
    store.set(charid, key(slot, 's'), 0)
end

-- slots currently holding a message, oldest first: { { slot = k, seq = n, stamp = t }, ... }
function M.list(store, charid, cfg)
    local found = {}
    for k = 1, cfg.maxSlots do
        local t = store.get(charid, key(k, 't'))
        if t ~= 0 then
            found[#found + 1] = { slot = k, stamp = t, seq = store.get(charid, key(k, 's')) }
        end
    end

    table.sort(found, function(a, b)
        if a.seq ~= b.seq then
            return a.seq < b.seq
        end

        return a.slot < b.slot
    end)

    return found
end

function M.count(store, charid, cfg)
    return #M.list(store, charid, cfg)
end

-- sanitise: printable bytes only, trimmed, cut to maxLength
function M.cleanText(text, cfg)
    if type(text) ~= 'string' then
        return nil
    end

    text = text:gsub('%c', ' '):gsub('^%s+', ''):gsub('%s+$', '')
    if #text == 0 then
        return nil
    end

    if #text > cfg.maxLength then
        text = text:sub(1, cfg.maxLength)
    end

    return text
end

-- write(store, recipientCharId, senderName, text, cfg, nowSeconds) -> result, slot
function M.write(store, recipientId, senderName, text, cfg, now)
    if not recipientId or recipientId == 0 then
        return M.RESULT.NO_RECIPIENT
    end

    text = M.cleanText(text, cfg)
    if not text then
        return M.RESULT.BAD_TEXT
    end

    local used = {}
    for _, e in ipairs(M.list(store, recipientId, cfg)) do
        used[e.slot] = true
    end

    local slot
    for k = 1, cfg.maxSlots do
        if not used[k] then
            slot = k
            break
        end
    end

    if not slot then
        return M.RESULT.BOX_FULL
    end

    senderName = tostring(senderName or ''):sub(1, 15)
    local seq = store.get(recipientId, '[QM]seq') + 1
    store.set(recipientId, '[QM]seq', seq)

    writeString(store, recipientId, slot, 'b', text, math.ceil(cfg.maxLength / 3))
    writeString(store, recipientId, slot, 'n', senderName, NAME_CHUNKS)
    store.set(recipientId, key(slot, 'l'), #text)
    store.set(recipientId, key(slot, 's'), seq)
    store.set(recipientId, key(slot, 'nl'), #senderName)
    store.set(recipientId, key(slot, 't'), math.max(now or 1, 1)) -- commit

    return M.RESULT.OK, slot
end

-- peek the oldest message without removing it -> result, { from, text, stamp, slot, left }
function M.peek(store, charid, cfg)
    local list = M.list(store, charid, cfg)
    if #list == 0 then
        return M.RESULT.EMPTY
    end

    local e   = list[1]
    local len = store.get(charid, key(e.slot, 'l'))
    local nl  = store.get(charid, key(e.slot, 'nl'))
    return M.RESULT.OK,
    {
        slot  = e.slot,
        stamp = e.stamp,
        left  = #list,
        text  = readString(store, charid, e.slot, 'b', len, math.ceil(cfg.maxLength / 3)),
        from  = readString(store, charid, e.slot, 'n', nl, NAME_CHUNKS),
        len   = len,
    }
end

-- read = peek + remove
function M.read(store, charid, cfg)
    local res, msg = M.peek(store, charid, cfg)
    if res ~= M.RESULT.OK then
        return res
    end

    clearSlot(store, charid, msg.slot, msg.len)
    store.set(charid, key(msg.slot, 'nl'), 0)
    msg.left = msg.left - 1
    return res, msg
end

function M.clear(store, charid, cfg)
    local n = 0
    for _, e in ipairs(M.list(store, charid, cfg)) do
        local len = store.get(charid, key(e.slot, 'l'))
        clearSlot(store, charid, e.slot, len)
        store.set(charid, key(e.slot, 'nl'), 0)
        n = n + 1
    end

    return n
end

return M
