"""ps2proxy_update: serves game updates to the PS2 over the lobby port (Fan Project by Habex).

The game connects to the lobby port and sends its own binary packets. An update check starts with the text "GET ", so the
first bytes of a connection tell the two apart: no extra port has to be opened.

  GET /update/manifest        the list of files of the current update (404 when there is no update)
  GET /update/f/<name>        one file of it (a "Range: bytes=N-" header continues a download)

Server/updates/manifest.txt and Server/updates/files/ are written by Server/update_tool.py. Manifest, one item per line:
  FFXIUPD 1
  version <number>                       goes up with every published update
  H <size> <crc32 hex> <file>            the game program (host); the PS2 starts it instead of the one on the disc
  D <size> <crc32 hex> <file> <path>     a game data file, put at <path> on the PS2 hard drive
"""
import os, re, socket

NAME_OK = re.compile(r'^[A-Za-z0-9._-]{1,64}$')
CHUNK = 64 * 1024


def is_http(first):
    return first[:4] == b'GET '


def _send(sock, code, text, body=b'', extra=''):
    head = 'HTTP/1.0 %d %s\r\nContent-Length: %d\r\nConnection: close\r\n%s\r\n' % (code, text, len(body), extra)
    sock.sendall(head.encode('latin-1') + body)


def _read_request(sock):
    data = b''
    while b'\r\n\r\n' not in data and len(data) < 4096:
        part = sock.recv(1024)
        if not part:
            break
        data += part
    lines = data.decode('latin-1', 'replace').split('\r\n')
    return lines[0], {k.strip().lower(): v.strip() for k, v in (l.split(':', 1) for l in lines[1:] if ':' in l)}


def handle(sock, addr, root, log):
    """Answer one request on an accepted connection, then close it."""
    try:
        sock.settimeout(20)
        line, headers = _read_request(sock)
        parts = line.split(' ')
        path = parts[1] if len(parts) >= 2 else ''
        if path == '/update/manifest':
            mf = os.path.join(root, 'manifest.txt')
            if not os.path.isfile(mf):
                _send(sock, 404, 'Not Found')
                return
            body = open(mf, 'rb').read()
            _send(sock, 200, 'OK', body)
            log('update', '%s asked for the update list (%d B)' % (addr[0], len(body)))
            return
        m = re.match(r'^/update/f/([^/?#]+)$', path)
        if not m or not NAME_OK.match(m.group(1)):
            _send(sock, 404, 'Not Found')
            return
        fp = os.path.join(root, 'files', m.group(1))
        if not os.path.isfile(fp):
            _send(sock, 404, 'Not Found')
            return
        size = os.path.getsize(fp)
        start = 0
        rg = re.match(r'^bytes=(\d+)-$', headers.get('range', ''))
        if rg:
            start = min(int(rg.group(1)), size)
        sent = 0
        with open(fp, 'rb') as f:
            f.seek(start)
            extra = 'Content-Range: bytes %d-%d/%d\r\n' % (start, size - 1, size) if start else ''
            head = 'HTTP/1.0 %d %s\r\nContent-Length: %d\r\nConnection: close\r\n%s\r\n' % (
                206 if start else 200, 'Partial Content' if start else 'OK', size - start, extra)
            sock.sendall(head.encode('latin-1'))
            while True:
                chunk = f.read(CHUNK)
                if not chunk:
                    break
                sock.sendall(chunk)
                sent += len(chunk)
        log('update', '%s downloaded %s (%d of %d B%s)' % (addr[0], m.group(1), sent, size, ', continued' if start else ''))
    except (OSError, socket.timeout):
        pass
    finally:
        try:
            sock.close()
        except OSError:
            pass
