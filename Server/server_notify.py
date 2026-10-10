"""Messages to a Discord channel: server started, stopped, restarted after a problem, scheduled event on or off (FFXI 2016 Server).
The channel's webhook address is kept in the server settings file (Server/data/server_config.json) and never shown in a log."""
import json
import re
import urllib.request

import server_control as sc

HOOK_RE = re.compile(r'^https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_-]+$')


def webhook():
    return str(sc.load_config().get('discord_webhook', '') or '')


def save_webhook(url):
    url = (url or '').strip()
    if url and not HOOK_RE.match(url):
        raise sc.ServerError('That does not look like a Discord webhook address. In Discord: channel settings > Integrations > Webhooks > Copy Webhook URL.')
    cfg = sc.load_config()
    cfg['discord_webhook'] = url
    sc.save_config(cfg)


def send(text, url=None):
    """Post a line to the channel. Returns (True, '') or (False, why). Never raises."""
    url = url or webhook()
    if not url:
        return False, 'No Discord address is set.'
    try:
        req = urllib.request.Request(url, data=json.dumps({'content': str(text)[:1900]}).encode('utf-8'),
                                     headers={'Content-Type': 'application/json', 'User-Agent': 'ffxi-2016-server'})
        urllib.request.urlopen(req, timeout=8).read()
        return True, ''
    except Exception as e:                                   # noqa: BLE001
        return False, 'Discord did not take it (%s).' % getattr(e, 'reason', e)
