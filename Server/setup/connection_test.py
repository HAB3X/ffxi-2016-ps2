#!/usr/bin/env python3
"""Connection test for the FFXI 2016 server. Run it on the server computer, then on another computer on the same network
(or away from home, using your internet address or hostname):   python3 connection_test.py [address or name]
With no address it tests this computer and prints what to type into the PS2's Server IP box."""
import socket, sys, urllib.request
PORTS = [(54001, "lobby (sign in)"), (54242, "search"), (54460, "friend list")]   # TCP; the game world (UDP 54240) cannot be probed
def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.connect(("10.255.255.255", 1)); return s.getsockname()[0]
    except OSError: return "127.0.0.1"
    finally: s.close()
def public_ip():
    for u in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try: return urllib.request.urlopen(u, timeout=5).read().decode().strip()
        except Exception: pass
    return None
host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
try: addr = socket.gethostbyname(host)
except OSError: print("Cannot look up '%s' - check the spelling / dynamic DNS name." % host); sys.exit(1)
print("Testing %s (%s)" % (host, addr)); bad = 0
for port, name in PORTS:
    try: socket.create_connection((addr, port), 4).close(); print("  OK      TCP %d  %s" % (port, name))
    except OSError as e: bad += 1; print("  FAILED  TCP %d  %s  (%s)" % (port, name, e))
if len(sys.argv) < 2:
    print("\nPS2 on the same network: Server IP = %s" % lan_ip()); p = public_ip()
    if p: print("PS2 away from home:      Server IP = %s (or your hostname), with the ports forwarded on your router" % p)
if bad:
    print("\nSome ports did not answer. Either the server is not running, this computer's firewall is blocking it (allow the server programs), "
          "or, from another network, your router is not forwarding the port or your provider shares one address between customers (CGNAT).")
else:
    print("\nAll the lobby ports answer. If the PS2 still shows FFXI-3101, check that it is on the same network (no guest wifi or client isolation) "
          "and that the Server IP is exactly as shown.")
