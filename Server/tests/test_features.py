"""Tests for the auction house, modes, debug log and PCSX2 launcher logic (no database or emulator needed).
Run:  python3 -m unittest discover -s Server/tests
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault('FFXI_DATA_DIR', tempfile.mkdtemp())

import server_ah as ah
import server_control as sc
import server_debug as sd
import server_modes as sm
import server_pcsx2 as pc


class AuctionHouse(unittest.TestCase):
    def test_price_never_at_or_below_shop_price(self):
        for base in (1, 15, 130, 45795):
            self.assertGreater(ah.price_for(base, ah.MIN_PERCENT), base)

    def test_price_scales_and_stacks(self):
        self.assertEqual(ah.price_for(100, 100), 200)
        self.assertEqual(ah.price_for(100, 150), 300)
        self.assertEqual(ah.price_for(100, 100, 12, True), 2400)
        self.assertLessEqual(ah.price_for(40000, 300, 99, True), ah.MAX_PRICE)

    def test_check_rejects_bad_input(self):
        for bad in ({'groups': []}, {'per_item': 0}, {'per_item': 9}, {'percent': 10}, {'percent': 'x'}):
            with self.assertRaises(sc.ServerError):
                ah.check(bad)
        self.assertEqual(ah.check({'groups': ['food', 'nope']})['groups'], ['food'])

    def test_seller_cannot_be_a_player(self):
        self.assertEqual(ah.SELLER_ID, 0)
        self.assertIn('_', ah.SELLER_NAME)

    def test_known_ids(self):
        ids = ah.known_item_ids()
        self.assertTrue(ids is None or 4112 in ids)


class Modes(unittest.TestCase):
    def setUp(self):
        self.old = sm.INIT_TXT
        sm.INIT_TXT = os.path.join(tempfile.mkdtemp(), 'init.txt')

    def tearDown(self):
        sm.INIT_TXT = self.old

    def test_off_by_default(self):
        self.assertFalse(any(v for k, v in sm.states().items() if sm.KIND[k] == 'init'))

    def test_toggle_keeps_other_lines(self):
        with open(sm.INIT_TXT, 'w') as f:
            f.write('# mine\nps2_2007\nlan_hidden\n')
        sm.set_enabled('helm_claim', True)
        sm.set_enabled('oztroja_escape', True)
        self.assertTrue(sm.enabled('helm_claim') and sm.enabled('oztroja_escape'))
        sm.set_enabled('helm_claim', True)                       # twice is the same as once
        self.assertEqual(open(sm.INIT_TXT).read().count('helm_claim\n'), 1)
        sm.set_enabled('helm_claim', False)
        sm.set_enabled('oztroja_escape', False)
        self.assertEqual(open(sm.INIT_TXT).read(), '# mine\nps2_2007\nlan_hidden\n')

    def test_exp_file_parses(self):
        ch = sm._exp_changes()
        self.assertEqual(len(ch), 24)
        self.assertEqual(ch[0], (53, 8200, 9200))


class DebugLog(unittest.TestCase):
    def test_filters(self):
        path = os.path.join(tempfile.mkdtemp(), 'log')
        with open(path, 'w') as f:
            f.write('10:00:00.000 [a] diag one\n10:00:01.000 [a] event two\n10:00:02.000 [a] zone three\n'
                    '10:00:03.000 [a] ERROR: bad\n        0000  aa\n')
        self.assertEqual(len(sd.view('all', path=path).splitlines()), 5)
        self.assertEqual(sd.view('diag', path=path).count('\n'), 0)
        self.assertIn('event two', sd.view('event', path=path))
        self.assertIn('zone three', sd.view('zone', path=path))
        self.assertIn('ERROR', sd.view('error', path=path))
        self.assertEqual(sd.tail('/no/such/file'), [])

    def test_tail_is_limited(self):
        path = os.path.join(tempfile.mkdtemp(), 'log')
        with open(path, 'w') as f:
            f.write(''.join('line %d\n' % i for i in range(5000)))
        self.assertEqual(sd.tail(path, 300)[-1], 'line 4999')
        self.assertEqual(len(sd.tail(path, 300)), 300)


class Pcsx2(unittest.TestCase):
    def test_command(self):
        self.assertEqual(pc.command(['/x/PCSX2'], '/d/a.iso'), ['/x/PCSX2', '-batch', '--', '/d/a.iso'])

    def test_missing_disc_never_starts(self):
        started = []
        with self.assertRaises(sc.ServerError):
            pc.launch(popen=lambda *a, **k: started.append(a), iso='/no/such.iso')
        self.assertEqual(started, [])

    def test_launch_builds_command_without_starting(self):
        iso = os.path.join(tempfile.mkdtemp(), 'a.iso')
        open(iso, 'w').close()
        exe = os.path.join(tempfile.mkdtemp(), 'pcsx2-qt')
        open(exe, 'w').close()
        os.chmod(exe, 0o755)
        started = []
        old_find, old_run = pc.find, pc.is_running
        pc.find, pc.is_running = (lambda: [exe]), (lambda: False)
        try:
            cmd = pc.launch(popen=lambda c, **k: started.append(c), iso=iso)
            pc.is_running = lambda: True
            with self.assertRaises(sc.ServerError):
                pc.launch(popen=lambda c, **k: started.append(c), iso=iso)
        finally:
            pc.find, pc.is_running = old_find, old_run
        self.assertEqual(cmd, [exe, '-batch', '--', iso])
        self.assertEqual(started, [cmd])

    def test_remember_rejects_non_programs(self):
        with self.assertRaises(sc.ServerError):
            pc.remember('/no/such/program')


if __name__ == '__main__':
    unittest.main()
