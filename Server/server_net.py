#!/usr/bin/env python3
"""FFXI 2016 Release - addresses and router ports for playing over the internet (Fan Project by Habex).

  same house   this computer's address on the home network
  internet     the home's public address (players outside the house type this; the router must forward the ports)
  Tailscale    the 100.x address, if Tailscale is running (optional)

The router ports can be opened by hand (the list is in FORWARD) or automatically with UPnP, which most home routers
support. Python standard library only (Mac, Windows, Linux).
"""
import ipaddress, json, os, re, shutil, socket, subprocess, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

import server_control as sc

INTERNET_IP_FILE = os.path.join(sc.DATA, 'internet_ip.txt')   # read by the PS2 login part on every sign-in
P = sc.PORTS
# Every port a player's game connects to. Nothing else is needed for internet play.
FORWARD = [('TCP', P['lobby'], 'sign-in'), ('UDP', P['relay'], 'game world'), ('TCP', P['search'], 'search (/sea)'),
           ('TCP', P['social'], 'friend list')]
NO_WINDOW = sc.NO_WINDOW


def _is_public(ip):
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_unspecified
                or a in ipaddress.ip_network('100.64.0.0/10'))


# ---------------------------------------------------------------- Tailscale
def tailscale_address():
    """The Tailscale 100.x address of this computer, or ''."""
    try:                                                     # no packet is sent: this only asks which network card would be used
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('100.100.100.100', 53))
        ip = s.getsockname()[0]
        s.close()
        if ipaddress.ip_address(ip) in ipaddress.ip_network('100.64.0.0/10'):
            return ip
    except (OSError, ValueError):
        pass
    for exe in (shutil.which('tailscale'), '/Applications/Tailscale.app/Contents/MacOS/Tailscale',
                r'C:\Program Files\Tailscale\tailscale.exe'):
        if exe and os.path.exists(exe):
            try:
                r = subprocess.run([exe, 'ip', '-4'], capture_output=True, text=True, timeout=4, creationflags=NO_WINDOW)
                ip = r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else ''
                if ip.startswith('100.'):
                    return ip
            except (OSError, subprocess.SubprocessError, IndexError):
                pass
    return ''


# ---------------------------------------------------------------- the public (internet) address
def _fetch(url, timeout=5):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FFXI-2016-Server'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(64).decode('ascii', 'replace').strip()
    except Exception:                                        # noqa: BLE001  (no certificates, no network, ...)
        pass
    curl = shutil.which('curl') or shutil.which('curl.exe')
    if curl:
        try:
            r = subprocess.run([curl, '-s', '-m', str(timeout), url], capture_output=True, text=True, timeout=timeout + 2,
                               creationflags=NO_WINDOW)
            return r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return ''


def detect_public_address():
    """Ask the router (UPnP) and then two web services what this home's internet address is. '' if unknown."""
    try:
        ip = upnp_external_ip()
        if ip and _is_public(ip):
            return ip
    except Exception:                                        # noqa: BLE001
        pass
    for url in ('https://api.ipify.org', 'https://ifconfig.me/ip', 'https://icanhazip.com'):
        ip = _fetch(url)
        if re.fullmatch(r'\d{1,3}(\.\d{1,3}){3}', ip or '') and _is_public(ip):
            return ip
    return ''


def public_address(refresh=False):
    """(address, how): the address set by hand in the app, else the detected one (re-checked every 10 minutes)."""
    cfg = sc.load_config()
    if cfg.get('internet_ip_manual'):
        return cfg['internet_ip_manual'], 'set by hand'
    if refresh or not cfg.get('internet_ip') or time.time() - cfg.get('internet_ip_time', 0) > 600:
        ip = detect_public_address()
        cfg = sc.load_config()
        if ip:
            cfg['internet_ip'] = ip
        cfg['internet_ip_time'] = time.time()
        sc.save_config(cfg)
    ip = cfg.get('internet_ip', '')
    write_internet_ip_file(ip)
    return ip, 'found automatically' if ip else 'not found'


def set_manual_public_address(ip):
    ip = (ip or '').strip()
    cfg = sc.load_config()
    if ip:
        try:
            socket.inet_aton(ip)
        except OSError:
            raise sc.ServerError('That is not an address like 81.12.34.56.')
        if not _is_public(ip):
            raise sc.ServerError('%s is a home-network address, not an internet address.' % ip)
        cfg['internet_ip_manual'] = ip
    else:
        cfg.pop('internet_ip_manual', None)
    sc.save_config(cfg)
    public_address()


def write_internet_ip_file(ip):
    try:
        os.makedirs(sc.DATA, exist_ok=True)
        old = open(INTERNET_IP_FILE).read().strip() if os.path.exists(INTERNET_IP_FILE) else None
        if old != (ip or ''):
            with open(INTERNET_IP_FILE, 'w') as f:
                f.write((ip or '') + '\n')
    except OSError:
        pass


# ---------------------------------------------------------------- UPnP (asks the router to open the ports)
class UpnpError(Exception):
    pass


_gw_cache = {'t': 0, 'gw': None}


def upnp_gateway(timeout=3.0):
    """The router's UPnP port-mapping service: dict(control=url, service=type, lan_ip=this computer) or None."""
    if _gw_cache['gw'] and time.time() - _gw_cache['t'] < 300:
        return _gw_cache['gw']
    lan = sc.lan_address()
    if not lan:
        return None
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    try:
        s.bind((lan, 0))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(lan))
    except OSError:
        pass
    s.settimeout(0.5)
    for st in ('urn:schemas-upnp-org:device:InternetGatewayDevice:1', 'urn:schemas-upnp-org:device:InternetGatewayDevice:2',
               'urn:schemas-upnp-org:service:WANIPConnection:1', 'urn:schemas-upnp-org:service:WANPPPConnection:1'):
        msg = ('M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 2\r\nST: %s\r\n\r\n' % st).encode()
        try:
            s.sendto(msg, ('239.255.255.250', 1900))
        except OSError:
            pass
    locations, end = [], time.time() + timeout
    while time.time() < end:
        try:
            data, _ = s.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError:
            break
        m = re.search(rb'(?im)^location:\s*(\S+)', data)
        if m and m.group(1).decode('ascii', 'replace') not in locations:
            locations.append(m.group(1).decode('ascii', 'replace'))
    s.close()
    for loc in locations:
        try:
            with urllib.request.urlopen(loc, timeout=4) as r:
                xml = r.read(512 * 1024)
            root = ET.fromstring(xml)
        except Exception:                                    # noqa: BLE001
            continue
        ns = {'d': 'urn:schemas-upnp-org:device-1-0'}
        base = root.findtext('d:URLBase', default='', namespaces=ns) or loc
        for svc in root.iter('{urn:schemas-upnp-org:device-1-0}service'):
            stype = svc.findtext('d:serviceType', default='', namespaces=ns)
            if 'WANIPConnection' in stype or 'WANPPPConnection' in stype:
                ctrl = urllib.parse.urljoin(base, svc.findtext('d:controlURL', default='', namespaces=ns))
                gw = dict(control=ctrl, service=stype, lan_ip=lan, location=loc)
                _gw_cache.update(t=time.time(), gw=gw)
                return gw
    _gw_cache.update(t=time.time(), gw=None)
    return None


def _soap(gw, action, args=()):
    body = ''.join('<%s>%s</%s>' % (k, v, k) for k, v in args)
    env = ('<?xml version="1.0"?>\r\n<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
           's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:%s xmlns:u="%s">%s</u:%s></s:Body></s:Envelope>'
           % (action, gw['service'], body, action)).encode()
    req = urllib.request.Request(gw['control'], data=env, method='POST', headers={
        'Content-Type': 'text/xml; charset="utf-8"', 'SOAPAction': '"%s#%s"' % (gw['service'], action)})
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            xml = r.read()
    except urllib.error.HTTPError as e:
        xml = e.read()
        code = re.search(rb'<errorCode>(\d+)</errorCode>', xml)
        desc = re.search(rb'<errorDescription>([^<]*)</errorDescription>', xml)
        raise UpnpError('%s%s' % (desc.group(1).decode() if desc else 'the router said no',
                                  ' (code %s)' % code.group(1).decode() if code else ''))
    except OSError as e:
        raise UpnpError('the router did not answer (%s)' % e)
    out = {}
    for m in re.finditer(rb'<(New[A-Za-z]+)>([^<]*)</\1>', xml):
        out[m.group(1).decode()] = m.group(2).decode()
    return out


def upnp_external_ip():
    gw = upnp_gateway()
    if not gw:
        return ''
    return _soap(gw, 'GetExternalIPAddress').get('NewExternalIPAddress', '')


def upnp_open_ports():
    """Ask the router to forward every game port to this computer. Returns a list of (ok, text)."""
    gw = upnp_gateway()
    if not gw:
        raise sc.ServerError('Your router did not answer. Either it has UPnP switched off, or it does not have it. '
                             'Open the ports by hand instead (see "How do friends connect?").')
    out = []
    for proto, port, what in FORWARD:
        args = [('NewRemoteHost', ''), ('NewExternalPort', port), ('NewProtocol', proto), ('NewInternalPort', port),
                ('NewInternalClient', gw['lan_ip']), ('NewEnabled', 1), ('NewPortMappingDescription', 'FFXI 2016 Server'),
                ('NewLeaseDuration', 0)]
        try:
            try:
                _soap(gw, 'AddPortMapping', args)
            except UpnpError:
                _soap(gw, 'AddPortMapping', args[:-1] + [('NewLeaseDuration', 604800)])   # routers that want a time limit (7 days)
            out.append((True, '%s %d (%s) opened' % (proto, port, what)))
        except UpnpError as e:
            out.append((False, '%s %d (%s): %s' % (proto, port, what, e)))
    sc.log_line('UPnP open ports: ' + '; '.join(t for _, t in out))
    return out


def upnp_check_ports():
    """[(proto, port, what, state)] with state 'open' (to this computer), 'other' (to another computer) or 'closed'.
    None if the router does not do UPnP."""
    gw = upnp_gateway()
    if not gw:
        return None
    out = []
    for proto, port, what in FORWARD:
        try:
            r = _soap(gw, 'GetSpecificPortMappingEntry', [('NewRemoteHost', ''), ('NewExternalPort', port), ('NewProtocol', proto)])
            to = r.get('NewInternalClient', '')
            out.append((proto, port, what, 'open' if to == gw['lan_ip'] else 'other:' + to))
        except UpnpError:
            out.append((proto, port, what, 'closed'))
    return out


def test_ports():
    """Plain-words report: what the router says (UPnP) and whether the sign-in port answers on the internet address."""
    lines = []
    ip, how = public_address()
    try:
        check = upnp_check_ports()
    except Exception:                                        # noqa: BLE001
        check = None
    if check is None:
        lines.append((None, 'Your router does not answer UPnP questions, so the app cannot read its settings.'))
    else:
        for proto, port, what, state in check:
            if state == 'open':
                lines.append((True, '%s %d (%s): forwarded to this computer' % (proto, port, what)))
            elif state.startswith('other:'):
                lines.append((False, '%s %d (%s): forwarded to ANOTHER computer (%s)' % (proto, port, what, state[6:])))
            else:
                lines.append((False, '%s %d (%s): not forwarded' % (proto, port, what)))
    if ip and sc.is_running('proxy'):
        try:
            socket.create_connection((ip, P['lobby']), timeout=3).close()
            lines.append((True, 'The sign-in port answers on the internet address %s.' % ip))
        except OSError:
            lines.append((None, 'The sign-in port did not answer on %s from here. Many routers cannot test this from inside the '
                                'house, so ask a friend outside to try signing in.' % ip))
    elif not sc.is_running('proxy'):
        lines.append((None, 'Start the server to test the sign-in port.'))
    return lines


# ---------------------------------------------------------------- Local / Port forwarding, and "is it working?"
def get_mode():
    return 'internet' if sc.load_config().get('mode') == 'internet' else 'local'


def set_mode(mode):
    cfg = sc.load_config()
    cfg['mode'] = 'internet' if mode == 'internet' else 'local'
    sc.save_config(cfg)


def mac_firewall_on():
    if not sc.MAC:
        return False
    try:
        r = subprocess.run(['/usr/libexec/ApplicationFirewall/socketfilterfw', '--getglobalstate'], capture_output=True, text=True, timeout=4)
        return 'enabled' in r.stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return False


def check_working(mode=None):
    """(state, headline, details): state 'ok', 'bad' or 'unsure'. Plain words, with the fix."""
    mode = mode or get_mode()
    st = sc.status()
    if not st['on']:
        missing = [sc.NICE[p] for p in ['database'] + sc.PROGRAMS + ['proxy'] if not st[p]]
        if not st['any']:
            return 'bad', 'Not working: the server is off', 'Click "Start Server".'
        return 'bad', 'Not working: part of the server is off', 'Off: %s. Click "Start Server" to start it again.' % ', '.join(missing)
    lan = sc.lan_address()
    if not lan:
        return 'bad', 'Not working: this computer is not on a network', 'Connect it to your router or Wi-Fi.'
    for proto, port, what in FORWARD:
        if proto == 'TCP' and not (port == P['social'] and not st['social']):
            try:
                socket.create_connection((lan, port), timeout=2).close()
            except OSError:
                return 'bad', 'Not working: the %s port does not answer' % what, \
                       'TCP %d does not answer on %s. Click "Stop Server", then "Start Server".' % (port, lan)
    notes = []
    if mac_firewall_on():
        notes.append('Mac firewall is on: click Allow if the Mac asks about incoming connections.')
    if mode == 'local':
        return 'ok', 'Working', ('ServerIP %s, ServerPort %d' % (lan, P['lobby']) + ('\n' + ' '.join(notes) if notes else ''))
    # port forwarding
    ip, how = public_address()
    if not ip:
        return 'bad', 'Not working: your internet address was not found', 'Click "change" next to it and type it (your router\'s status page shows it).'
    try:
        gw = upnp_gateway()
        rip = upnp_external_ip() if gw else ''
    except Exception:                                        # noqa: BLE001
        gw, rip = None, ''
    if rip and not _is_public(rip):
        return 'bad', 'Not working: your internet provider shares its addresses (CGNAT)', \
               'Your router\'s own internet address is %s, which is not reachable from the internet, so port forwarding ' \
               'cannot work. Ask your provider for a public IP address, or use Tailscale.' % rip
    mapped = None
    if gw:
        try:
            mapped = upnp_check_ports()
        except Exception:                                    # noqa: BLE001
            mapped = None
    if mapped:
        bad = [m for m in mapped if m[3] != 'open']
        if bad:
            return 'bad', 'Not working: %d port%s not forwarded' % (len(bad), '' if len(bad) == 1 else 's'), \
                   'Forward to this computer (%s): %s. Click "Open ports for me", or add them in your router.' % (
                       lan, ', '.join('%s %d' % (m[0], m[1]) for m in bad))
    hairpin = False
    try:
        socket.create_connection((ip, P['lobby']), timeout=3).close()
        hairpin = True
    except OSError:
        pass
    if hairpin and (mapped or not gw):
        return 'ok', 'Working', 'ServerIP %s, ServerPort %d' % (ip, P['lobby'])
    if mapped:
        return 'unsure', 'Probably working (can\'t confirm from inside the house)', \
               'Your router forwards all 4 ports to this computer. Most routers cannot test this from inside, ' \
               'so ask a friend to try signing in with ServerIP %s.' % ip
    return 'unsure', 'Can\'t confirm from inside. Ask a friend to try', \
           'Your router does not tell the app its settings (no UPnP). Check that these ports are forwarded to %s: %s. ' \
           'Then ask a friend to sign in with ServerIP %s.' % (lan, ', '.join('%s %d' % (f[0], f[1]) for f in FORWARD), ip)


if __name__ == '__main__':
    print('same house :', sc.lan_address())
    print('tailscale  :', tailscale_address() or '-')
    print('internet   :', public_address(refresh=True))
    gw = upnp_gateway()
    print('router UPnP:', gw and gw['control'] or 'not found')
    if gw:
        print('router says internet address:', upnp_external_ip())
        for row in upnp_check_ports():
            print('  ', row)
