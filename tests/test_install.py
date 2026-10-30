import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / 'scripts/install.py'


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config = self.home / '.config'
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.config),
                        XDG_STATE_HOME=str(self.home / '.local/state'))
        (self.config / 'hypr/UserConfigs').mkdir(parents=True)
        (self.config / 'hypr/hyprland.conf').write_text('# existing install\n')
        (self.config / 'waybar').mkdir()
        (self.config / 'waybar/old-config').write_text('{"position":"top"}\n')
        (self.config / 'waybar/config').symlink_to('old-config')
        (self.config / 'waybar/style.css').write_text('/* original CSS */\n')
        self.original = '# Personal configuration\n\n'
        for name in ('Startup_Apps.conf', 'UserKeybinds.conf', 'WindowRules.conf'):
            (self.config / 'hypr/UserConfigs' / name).write_text(self.original)

    def run_installer(self, action, check=True, extra=None):
        return subprocess.run([sys.executable, str(INSTALLER), action, '--no-start', *(extra or [])],
                              env=self.env, capture_output=True, text=True, check=check)

    def test_repeat_install_and_exact_restore(self):
        self.run_installer('install')
        first = (self.config / 'hypr/UserConfigs/UserKeybinds.conf').read_text()
        self.run_installer('install')
        self.assertEqual((self.config / 'hypr/UserConfigs/UserKeybinds.conf').read_text(), first)
        self.assertEqual(first.count('# BEGIN hyprland-rice'), 1)
        tasks = self.home / '.local/share/hyprland-rice/tasks.json'
        tasks.parent.mkdir(parents=True)
        tasks.write_text('personal tasks preserved')
        self.run_installer('uninstall')
        self.assertEqual(os.readlink(self.config / 'waybar/config'), 'old-config')
        self.assertEqual((self.config / 'waybar/style.css').read_text(), '/* original CSS */\n')
        for name in ('Startup_Apps.conf', 'UserKeybinds.conf', 'WindowRules.conf'):
            self.assertEqual((self.config / 'hypr/UserConfigs' / name).read_text(), self.original)
        self.assertEqual(tasks.read_text(), 'personal tasks preserved')
        self.assertFalse((self.config / 'quickshell/rice-desktop').exists())
        self.run_installer('uninstall')

    def test_preserve_later_user_changes(self):
        self.run_installer('install')
        keybinds = self.config / 'hypr/UserConfigs/UserKeybinds.conf'
        keybinds.write_text(keybinds.read_text() + '# Later user setting\n')
        css = self.config / 'waybar/style.css'
        css.unlink()
        css.write_text('/* User replacement */\n')
        self.assertNotEqual(self.run_installer('install', check=False).returncode, 0)
        self.run_installer('uninstall')
        self.assertEqual(css.read_text(), '/* User replacement */\n')
        self.assertIn('# Later user setting', keybinds.read_text())
        self.assertNotIn('# BEGIN hyprland-rice', keybinds.read_text())

    def test_restore_bar_after_using_vendor_selector(self):
        self.run_installer('install')
        config = self.config / 'waybar/config'
        config.unlink()
        config.symlink_to('old-config')
        self.run_installer('install', extra=['--restore-bar'])
        self.assertEqual(Path(os.readlink(config)), INSTALLER.parents[1] / 'waybar/config.jsonc')
        self.run_installer('uninstall')
        self.assertEqual(os.readlink(config), 'old-config')


if __name__ == '__main__':
    unittest.main()
