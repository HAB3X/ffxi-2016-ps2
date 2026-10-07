#!/usr/bin/env python3
"""Make a copy of the release folder to give to someone else, without this computer's private files:
Server/data (database, profiles, passwords, chat history, logs), the map server's runtime files in Server/lsb
(log/, login.cert/key, app_bridge.*, app_roles.lua), the database password in Server/lsb/settings/network.lua
(reset to the blank template) and Python caches.

    python3 make_share_copy.py "/path/to/new folder"
"""
import os, shutil, sys

RELEASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKIP_DIRS = {os.path.join('Server', 'data'), os.path.join('Server', 'lsb', 'log'), os.path.join('Server', 'lsb', '.build-venv')}
SKIP_FILES = {os.path.join('Server', 'lsb', n) for n in ('login.cert', 'login.key', 'app_bridge.queue', 'app_bridge.alive', 'app_roles.lua')}


def main(dest):
    if os.path.exists(dest):
        sys.exit('That folder exists already. Pick a new name.')

    def ignore(d, names):
        rel = os.path.relpath(d, RELEASE)
        out = {'__pycache__', '.DS_Store'} & set(names)
        for n in names:
            p = os.path.normpath(os.path.join(rel, n))
            if p in SKIP_DIRS or p in SKIP_FILES or n.endswith('.part'):
                out.add(n)
        return out
    shutil.copytree(RELEASE, dest, ignore=ignore, symlinks=True)
    net = os.path.join(dest, 'Server', 'lsb', 'settings')
    shutil.copy(os.path.join(net, 'network.lua.template'), os.path.join(net, 'network.lua'))
    print('Done: %s' % dest)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
