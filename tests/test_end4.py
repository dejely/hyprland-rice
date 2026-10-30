import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integration'))
from palette import sync, translate
from shortcuts import ACTIONS, keybind_tree
from build import build


class PaletteTests(unittest.TestCase):
    def test_invalid_palette_retains_last_complete_palette(self):
        colors = dict(windowBackground='#111222', primaryText='#eeeeee', secondaryText='#aaaaaa', accentPrimary='##b5dce8')
        with tempfile.TemporaryDirectory() as td:
            source, dest = Path(td) / 'palette', Path(td) / 'material'
            source.write_text(json.dumps(colors))
            self.assertTrue(sync(source, dest))
            original = dest.read_bytes()
            self.assertEqual(json.loads(original)['primary'], '#b5dce8')
            for value in ('{partial', '{}', '[]', '{"accentPrimary":"bad"}'):
                source.write_text(value)
                self.assertFalse(sync(source, dest))
                self.assertEqual(dest.read_bytes(), original)
            colors['accentPrimary'] = '#778899'
            source.write_text(json.dumps(colors))
            self.assertTrue(sync(source, dest))
            self.assertEqual(json.loads(dest.read_text())['primary'], '#778899')


class ShortcutTests(unittest.TestCase):
    def test_generated_bindings_match_action_map_without_duplicate_chords(self):
        chords = {(m, k) for m, k, *_ in ACTIONS}
        self.assertEqual(len(chords), len(ACTIONS))
        lines = (ROOT / 'integration/keybinds.conf').read_text().splitlines()
        self.assertEqual(sum(line.startswith('unbind = ') for line in lines), len(ACTIONS))
        for mods, key, desc, action in ACTIONS:
            self.assertIn(f'unbind = {mods}, {key}', lines)
            self.assertTrue(any(line.startswith(f'bindd = {mods}, {key}, {desc},') and line.endswith(' ' + action) for line in lines))
        tree = keybind_tree([dict(modmask=69, key='D', dispatcher='exec', arg='desktop', description='Desktop')])
        self.assertEqual(tree['keybinds'][0]['mods'], ['SUPER', 'CTRL', 'SHIFT'])


class BuildTests(unittest.TestCase):
    def test_repeat_build_and_snapshot_integrity(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = Path(td) / 'runtime'
            build(runtime)
            build(runtime)
            self.assertTrue((runtime / 'integration/tasks.py').is_file())
            self.assertNotIn('PanelLoader { component: Lock {} }', (runtime / 'panelFamilies/IllogicalImpulseFamily.qml').read_text())
            self.assertIn('focuswindow address:', (runtime / 'services/HyprlandBackend.qml').read_text())
            self.assertNotIn('todoFileView', (runtime / 'services/Todo.qml').read_text())
            self.assertIn('todoFileView', (ROOT / 'vendor/end4-pC/services/Todo.qml').read_text())

    def test_refuses_to_replace_unmanaged_directory(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / 'personal').write_text('keep')
            with self.assertRaises(ValueError): build(p)
            self.assertEqual((p / 'personal').read_text(), 'keep')


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config = self.home / '.config'
        self.state = self.home / '.local/state/hyprland-rice'
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.config), XDG_STATE_HOME=str(self.home / '.local/state'))
        for name in ('hypr/configs', 'hypr/UserConfigs', 'rofi', 'quickshell'):
            (self.config / name).mkdir(parents=True)
        (self.config / 'hypr/hyprland.conf').write_text('# JaKooLit\n')
        (self.home / 'wallpaper.png').write_bytes(b'fixture')
        (self.config / 'rofi/.current_wallpaper').symlink_to(self.home / 'wallpaper.png')
        (self.config / 'quickshell/rice-desktop').symlink_to(ROOT / 'quickshell/rice-desktop')
        self.startup = 'exec-once = waybar\nexec-once = swaync\nexec-once = swww-daemon\nexec-once = qs -c overview\nexec-once = hypridle\n'
        (self.config / 'hypr/configs/Startup_Apps.conf').write_text(self.startup)
        (self.config / 'hypr/UserConfigs/Startup_Apps.conf').write_text('# personal startup\n')
        self.keys = 'bind = SUPER, V, exec, code\n'
        (self.config / 'hypr/UserConfigs/UserKeybinds.conf').write_text(self.keys)

    def switch(self, profile, check=True):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/install.py'), 'install', '--profile', profile, '--no-start'], env=self.env, capture_output=True, text=True, check=check)

    def test_switch_repeat_and_rollback_preserves_data(self):
        self.switch('end4')
        keys = self.config / 'hypr/UserConfigs/UserKeybinds.conf'
        installed = keys.read_text()
        self.switch('end4')
        self.assertEqual(keys.read_text(), installed)
        self.assertIn(self.keys, installed)
        startup = (self.config / 'hypr/configs/Startup_Apps.conf').read_text()
        self.assertIn('\nexec-once = hypridle\n', startup)
        self.assertIn('# rice-end4 disabled: exec-once = waybar', startup)
        settings = self.config / 'hyprland-rice/end4/config.json'
        settings.write_text(settings.read_text() + '\n')
        self.switch('jakoolit')
        self.assertEqual(keys.read_text(), self.keys)
        self.assertEqual((self.config / 'hypr/configs/Startup_Apps.conf').read_text(), self.startup)
        self.assertEqual(os.readlink(self.config / 'quickshell/rice-desktop'), str(ROOT / 'quickshell/rice-desktop'))
        self.assertTrue(settings.read_text().endswith('\n\n'))

    def test_rollback_refuses_to_discard_later_user_edits(self):
        self.switch('end4')
        keys = self.config / 'hypr/UserConfigs/UserKeybinds.conf'
        keys.write_text(keys.read_text() + '# later user edit\n')
        result = self.switch('jakoolit', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('preserved', result.stderr)
        self.assertIn('# later user edit', keys.read_text())
        self.assertTrue((self.state / 'end4-profile.json').exists())


if __name__ == '__main__':
    unittest.main()
