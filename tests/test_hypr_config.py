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
