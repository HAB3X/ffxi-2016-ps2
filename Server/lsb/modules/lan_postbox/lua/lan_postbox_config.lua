-----------------------------------
-- lan_postbox configuration (data file: no Module is constructed here, so the loader leaves it alone)
-----------------------------------
return
{
    -- how many quick messages one character can hold (the beta post box had 8 work slots per box)
    maxSlots = 8,

    -- longest message body in bytes. 3 bytes are packed into one char_vars row, so 60 bytes = 20 rows per message.
    -- (The 2001 beta allowed 0xA0 = 160 bytes on the wire; a chat line is never that long.)
    maxLength = 60,

    -- tell a player how many messages are waiting when they log in (beta: " %d message(s) arrived.")
    loginNotice = true,

    -- "message of the day" shown by !qmm and at login (beta: /motd, packet 0x49). Empty = none.
    motd = '',
}
