"""A shareable page about your server (FFXI 2016 Server, Fan Project by Habex): the era, level cap, rates, open expansions, events and
how many players are on. One self-contained HTML file with no outside links.

The Server App rewrites Server/data/info.html now and then. The login proxy serves it at http://<your address>:<port>/info (the same port players
type), and the app can also save a copy to post on a website or Discord."""
import html
import os
import time

import server_control as sc
import server_settings as ss

INFO_FILE = os.path.join(sc.DATA, 'info.html')
EXPANSIONS = (('ENABLE_ROTZ', 'Rise of the Zilart'), ('ENABLE_COP', 'Chains of Promathia'), ('ENABLE_TOAU', 'Treasures of Aht Urhgan'),
              ('ENABLE_WOTG', 'Wings of the Goddess'), ('ENABLE_ACP', 'A Crystalline Prophecy'), ('ENABLE_AMK', "A Moogle Kupo d'Etat"),
              ('ENABLE_ASA', 'A Shantotto Ascension'), ('ENABLE_ABYSSEA', 'Abyssea'), ('ENABLE_SOA', 'Seekers of Adoulin'))


def _x(v):
    return ('%g' % v) if isinstance(v, float) else str(v)


def snapshot(players=None):
    """The facts for the page, as plain data."""
    name = ss.get()['name']
    rules = ss.get_values('rules')
    era = next((label for k, label, _, _ in ss.ERAS if k == ss.detect_era()), 'Custom rules')
    changed = []
    for group in ('rates', 'monsters'):
        vals = ss.get_values(group)
        for st in ss.GROUPS[group]:
            if abs(float(vals[st.key]) - 1.0) > 1e-9:
                changed.append((st.label, float(vals[st.key])))
    try:
        import server_hardcore
        hardcore = server_hardcore.get()
    except Exception:                                        # noqa: BLE001
        hardcore = {'on': False, 'lives': 1}
    return {'name': name, 'era': era, 'max_level': int(rules['MAX_LEVEL']), 'start_cap': int(rules['INITIAL_LEVEL_CAP']),
            'expansions': [label for key, label in EXPANSIONS if int(rules.get(key, 0))], 'changed': changed, 'hardcore': hardcore,
            'events': [ss.event_text(e) + '  (' + e['name'] + ')' for e in ss.list_events() if e.get('on', True)], 'players': players,
            'when': time.strftime('%d %b %Y, %H:%M')}


CSS = ('body{margin:0;background:#070b1c;color:#eef2ff;font:16px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif}'
       '.wrap{max-width:760px;margin:0 auto;padding:32px 20px}h1{margin:0 0 4px;font-size:30px}.sub{color:#a7b3d9;margin:0 0 24px}'
       '.card{background:#0e1633;border:1px solid #222f63;border-radius:14px;padding:18px 22px;margin:0 0 16px}'
       'h2{margin:0 0 10px;font-size:15px;letter-spacing:.06em;text-transform:uppercase;color:#f0cf7a}'
       'ul{margin:0;padding-left:20px}li{margin:3px 0}.k{color:#a7b3d9}.big{font-size:22px;font-weight:600}'
       '.row{display:flex;gap:28px;flex-wrap:wrap}.row div{min-width:130px}.foot{color:#6f7ca8;font-size:13px;margin-top:24px}')


def build_html(info, address=None):
    e = html.escape
    out = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
           '<title>%s</title><style>%s</style></head><body><div class="wrap">' % (e(info['name']), CSS),
           '<h1>%s</h1><p class="sub">%s &middot; a Final Fantasy XI server for the PS2</p>' % (e(info['name']), e(info['era']))]
    on = '%d online' % info['players'] if info['players'] is not None else 'Unknown'
    out.append('<div class="card"><div class="row"><div><div class="k">Level cap</div><div class="big">%d</div></div>'
               '<div><div class="k">Players now</div><div class="big">%s</div></div>'
               '<div><div class="k">Mode</div><div class="big">%s</div></div></div></div>' %
               (info['max_level'], e(on), ('Hardcore (%d %s)' % (info['hardcore']['lives'], 'life' if info['hardcore']['lives'] == 1 else 'lives'))
                if info['hardcore']['on'] else 'Normal'))
    if info['changed']:
        out.append('<div class="card"><h2>Rates</h2><ul>%s</ul></div>' % ''.join('<li>%s <span class="k">x%s</span></li>' % (e(a), _x(b)) for a, b in info['changed']))
    else:
        out.append('<div class="card"><h2>Rates</h2>Normal rates.</div>')
    out.append('<div class="card"><h2>Open content</h2><ul>%s</ul></div>' % ''.join('<li>%s</li>' % e(x) for x in info['expansions']))
    if info['events']:
        out.append('<div class="card"><h2>Events</h2><ul>%s</ul></div>' % ''.join('<li>%s</li>' % e(x) for x in info['events']))
    if address:
        out.append('<div class="card"><h2>How to join</h2>On the PS2 sign-in page type <b>%s</b> as the server address and <b>%s</b> as the port, '
                   'then your player name and password from the server owner.</div>' % (e(address[0]), e(str(address[1]))))
    out.append('<p class="foot">Updated %s. An unofficial fan project, not made or supported by Square Enix. Final Fantasy XI is a trademark of '
               'Square Enix.</p></div></body></html>' % e(info['when']))
    return ''.join(out)


def write(address=None, players=None, path=None):
    """Rewrite the page. `address` is (host, port) to show a "How to join" box, or None to leave the address out."""
    path = path or INFO_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(build_html(snapshot(players), address))
    os.replace(tmp, path)
    return path
