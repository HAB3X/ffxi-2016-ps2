"""Stock the auction house (FFXI 2016 Server, Fan Project by Habex).

A small server starts with an empty auction house. This puts ordinary items on sale so there is something to buy.
The idea (a server character that lists items at set prices) comes from the ffxiahbot project (MIT licence); this code is our own.

How LandSandBoat stores a listing (table auction_house): itemid, stack (0 = single item, 1 = a full stack), seller (character id),
seller_name, date, price (for the whole listing), and buyer_name which is NULL while the listing is open.
Every row this file writes has seller = 0 and seller_name = SELLER_NAME. Seller 0 is special in the game's own database trigger:
when a listing with seller 0 sells, nobody is paid and no mail is sent, and no real character has id 0. Every change here only
looks at those rows, so a player's listings are never touched, and "Remove the server's listings" deletes only the open ones of
this seller (sold ones stay as price history).
"""
import json
import os
import re
import time

import server_control as sc

SELLER_NAME = 'Server_AH'            # real character names cannot contain an underscore
SELLER_ID = 0
MAX_LISTINGS = 8000                  # the most open listings the server character will ever hold
KNOWN_IDS_LUA = os.path.join(sc.LSB, 'modules', 'ps2_2007', 'item_ids_2007.lua')
STATE_FILE = os.path.join(sc.DATA, 'ah_state.json')

# plain-language groups of auction house categories (item_basic.aH)
GROUPS = [
    ('materials', 'Crystals and crafting materials', list(range(38, 45)) + [35, 63]),
    ('food', 'Food and fish', list(range(51, 60))),
    ('medicine', 'Medicine, ninja tools and ammunition', [33, 49, 15]),
    ('scrolls', 'Magic scrolls', [28, 29, 30, 31, 32, 45]),
    ('weapons', 'Weapons', list(range(1, 15))),
    ('armor', 'Armor', list(range(16, 27))),
    ('furniture', 'Furniture', [34]),
]
GROUP_IDS = {k: ids for k, _, ids in GROUPS}
DEFAULTS = {'groups': ['materials', 'food', 'medicine'], 'per_item': 2, 'percent': 100, 'stacks': True, 'refill': 'off'}
REFILLS = [('off', 'Only when I press the button', 0), ('hourly', 'Every hour', 3600), ('sixhourly', 'Every 6 hours', 21600),
           ('daily', 'Every day', 86400)]
REFILL_SECONDS = {k: s for k, _, s in REFILLS}
# items that cannot be sold on the auction house or are not for ordinary players: GM only, no auction, no sale, Ex, Rare
SKIP_FLAGS = 2 | 64 | 4096 | 16384 | 32768
MAX_PRICE = 99999999
# Shops pay BaseSell for an item. Auction prices are usually about twice that; "normal price" here is 2 x BaseSell.
NORMAL_FACTOR = 2
MIN_PERCENT, MAX_PERCENT = 50, 300


def settings():
    """The saved options (missing ones filled in with the defaults)."""
    saved = sc.load_config().get('ah')
    s = dict(DEFAULTS)
    if isinstance(saved, dict):
        s.update({k: saved[k] for k in DEFAULTS if k in saved})
    return s


def check(opts):
    """Validates and tidies the options from the form; raises ServerError in plain words."""
    s = dict(DEFAULTS)
    groups = [g for g in opts.get('groups', s['groups']) if g in GROUP_IDS]
    if not groups:
        raise sc.ServerError('Pick at least one kind of item.')
    s['groups'] = groups
    try:
        s['per_item'] = int(float(opts.get('per_item', s['per_item'])))
        s['percent'] = int(float(opts.get('percent', s['percent'])))
    except (TypeError, ValueError):
        raise sc.ServerError('Listings and price must be whole numbers.')
    if not 1 <= s['per_item'] <= 5:
        raise sc.ServerError('Listings per item must be between 1 and 5.')
    if not MIN_PERCENT <= s['percent'] <= MAX_PERCENT:
        raise sc.ServerError('The price must be between %d%% and %d%% of the normal price (lower would let players make gil by buying and '
                             'selling to a shop).' % (MIN_PERCENT, MAX_PERCENT))
    s['stacks'] = bool(opts.get('stacks', s['stacks']))
    refill = opts.get('refill', s['refill'])
    s['refill'] = refill if refill in REFILL_SECONDS else 'off'
    return s


def save_settings(opts):
    s = check(opts)
    cfg = sc.load_config()
    cfg['ah'] = s
    sc.save_config(cfg)
    return s


def _state():
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(st):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(st, f)
    os.replace(STATE_FILE + '.tmp', STATE_FILE)


def known_item_ids():
    """The item ids the 2007 PS2 game knows (an item it does not know shows as an empty line). None when the list is not there."""
    try:
        with open(KNOWN_IDS_LUA, encoding='utf-8') as f:
            return {int(n) for n in re.findall(r'\[(\d+)\]\s*=\s*true', f.read())}
    except OSError:
        return None


def price_for(base_sell, percent, stack_size=1, stack=False):
    """Gil for one listing. base_sell is what a shop pays for the item."""
    one = max(base_sell + 1, round(base_sell * NORMAL_FACTOR * percent / 100.0))   # never at or below the shop price
    total = one * (stack_size if stack else 1)
    return int(min(MAX_PRICE, total))


def candidates(groups, known=None):
    """[(itemid, stack_size, base_sell)] of the items to sell, from the game's own item list."""
    cats = sorted({c for g in groups for c in GROUP_IDS.get(g, [])})
    if not cats:
        return []
    rows = sc.sql('SELECT itemid, stackSize, BaseSell FROM item_basic WHERE aH IN (%s) AND BaseSell > 0 AND (flags & %d) = 0 ORDER BY itemid'
                  % (','.join(str(c) for c in cats), SKIP_FLAGS))
    known = known if known is not None else known_item_ids()
    out = []
    for r in rows:
        item = int(r[0])
        if known is None or item in known:
            out.append((item, max(1, int(r[1])), int(r[2])))
    return out


def _open_counts():
    """{(itemid, stack): number of open listings by the server character}"""
    return {k: v[0] for k, v in _open_info().items()}


def _open_info():
    """{(itemid, stack): (open listings, lowest price, highest price)}"""
    rows = sc.sql("SELECT itemid, stack, COUNT(*), MIN(price), MAX(price) FROM auction_house WHERE seller = %d AND seller_name = '%s' "
                  "AND buyer_name IS NULL GROUP BY itemid, stack" % (SELLER_ID, SELLER_NAME))
    return {(int(a), int(b)): (int(c), int(lo), int(hi)) for a, b, c, lo, hi in rows}


def plan(opts=None):
    """What stocking would do: {'items': kinds of items, 'add': listings to add, 'open': listings open now}"""
    s = check(opts) if opts else settings()
    have = _open_counts()
    items = candidates(s['groups'])
    add = 0
    for item, size, _ in items:
        for stack in ((0, 1) if s['stacks'] and size > 1 else (0,)):
            add += max(0, s['per_item'] - have.get((item, stack), 0))
    return {'items': len(items), 'add': add, 'open': sum(have.values())}


def stock(opts=None):
    """Puts the items on sale: tops every chosen item up to the wanted number of listings and sets all the server's open listings to the
    chosen price. Running it again changes nothing that is already right. Returns {'added', 'items', 'open'}."""
    s = check(opts) if opts else settings()
    items = candidates(s['groups'])
    if not items:
        raise sc.ServerError('No items were found. Has the world database been loaded? Start the server once first.')
    info = _open_info()
    have = {k: v[0] for k, v in info.items()}
    now = int(time.time())
    rows = []
    prices = {}
    room = MAX_LISTINGS - sum(have.values())
    for item, size, base in items:
        for stack in ((0, 1) if s['stacks'] and size > 1 else (0,)):
            price = price_for(base, s['percent'], size, bool(stack))
            prices[(item, stack)] = price
            need = max(0, s['per_item'] - have.get((item, stack), 0))
            for _ in range(min(need, max(0, room))):
                rows.append((item, stack, price))
                room -= 1
    before = {int(r[0]) for r in sc.sql('SELECT itemid FROM auction_house_items')}
    stmts = ['START TRANSACTION']
    for (item, stack), price in prices.items():                                    # prices follow the chosen percentage
        if (item, stack) in info and info[(item, stack)][1:] != (price, price):
            stmts.append("UPDATE auction_house SET price = %d WHERE seller = %d AND seller_name = '%s' AND buyer_name IS NULL AND itemid = %d "
                         "AND stack = %d AND price <> %d" % (price, SELLER_ID, SELLER_NAME, item, stack, price))
    for i in range(0, len(rows), 500):
        vals = ','.join("(%d,%d,%d,'%s',%d,%d)" % (it, st, SELLER_ID, SELLER_NAME, now, pr) for it, st, pr in rows[i:i + 500])
        stmts.append('INSERT INTO auction_house (itemid, stack, seller, seller_name, date, price) VALUES ' + vals)
    stmts.append('COMMIT')
    sc.sql('', stdin_bytes=(';\n'.join(stmts) + ';\n').encode('ascii'))
    st = _state()
    added_items = set(st.get('added_items', [])) | ({it for it, _, _ in rows} - before)    # items the listing trigger newly put on the "ever sold" list
    st.update({'added_items': sorted(added_items), 'last_run': now})
    _save_state(st)
    return {'added': len(rows), 'items': len(items), 'open': sum(have.values()) + len(rows)}


def open_count():
    return sum(_open_counts().values())


def clear():
    """Removes the server character's open listings and nothing else. Returns how many were removed."""
    st = _state()
    n = open_count()
    stmts = ["DELETE FROM auction_house WHERE seller = %d AND seller_name = '%s' AND buyer_name IS NULL" % (SELLER_ID, SELLER_NAME)]
    added = [int(i) for i in st.get('added_items', [])]
    if added:                                                                      # take back the "ever listed" marks this feature added
        stmts.append('DELETE FROM auction_house_items WHERE itemid IN (%s) AND itemid NOT IN (SELECT itemid FROM auction_house)'
                     % ','.join(str(i) for i in added))
    sc.sql('', stdin_bytes=(';\n'.join(stmts) + ';\n').encode('ascii'))
    st['added_items'] = []
    _save_state(st)
    return n


def refill_due(now=None):
    """True when the chosen refill schedule says it is time (the Server App checks this every half minute while the database is on)."""
    every = REFILL_SECONDS.get(settings()['refill'], 0)
    if not every:
        return False
    return (now or time.time()) - _state().get('last_run', 0) >= every


def summary(plan_result):
    return '%d kinds of items, %d listings open now, %d to add.' % (plan_result['items'], plan_result['open'], plan_result['add'])
