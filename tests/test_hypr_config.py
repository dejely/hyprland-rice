import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integration'))
from hypr_config import update


class HyprConfigTests(unittest.TestCase):
    def test_edit_and_reset_preserve_unrelated_options(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'overrides.conf'
            update(path, [('general:gaps_in', '5'), ('decoration:rounding', '10')], [])
            update(path, [('general:gaps_in', '7')], ['decoration:rounding'])
            self.assertIn('general:gaps_in = 7\n', path.read_text())
            self.assertNotIn('rounding', path.read_text())
            before = path.read_bytes()
            with self.assertRaises(ValueError): update(path, [('general:gaps_in', '7\nexec = bad')], [])
            self.assertEqual(path.read_bytes(), before)


class MonitorConfigTests(unittest.TestCase):
    def test_conf_persists_mode_scale_and_reset(self):
        from monitor_config import update
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'monitors.conf'
            update(path, 'eDP-1', [('mode', '1920x1200@60'), ('scale', '1'), ('transform', '1')], [])
            update(path, 'eDP-1', [], ['transform'])
            self.assertIn('monitor = eDP-1, 1920x1200@60, auto, 1\n', path.read_text())
            self.assertNotIn('transform', path.read_text())
