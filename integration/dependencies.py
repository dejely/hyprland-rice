#!/usr/bin/env python3
"""Inventory dependencies and optionally install missing Fedora QML modules locally."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

COMMANDS = ['qs', 'hyprctl', 'wallust', 'magick', 'cliphist', 'wl-copy', 'wl-paste', 'brightnessctl', 'hyprlock', 'hypridle', 'kitty', 'notify-send']


def inventory():
    local = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'hyprland-rice/deps'
    qml = Path('/usr/lib64/qt6/qml/org/kde/syntaxhighlighting/qmldir')
    return {'host': platform.freedesktop_os_release()['ID'],
            'commands': {name: shutil.which(name) for name in COMMANDS},
            'syntax_highlighting': qml.is_file() or Path('/usr/lib/qt6/qml/org/kde/syntaxhighlighting/qmldir').is_file() or (local / 'usr/lib64/qt6/qml/org/kde/syntaxhighlighting/qmldir').is_file()}


def install_missing():
    info = inventory()
    missing = [name for name, path in info['commands'].items() if path is None]
    if missing: raise RuntimeError('Install missing commands with your host package manager: ' + ', '.join(missing))
    if info['syntax_highlighting']: return
    if info['host'] != 'fedora': raise RuntimeError('Install the KDE syntax-highlighting QML module with the host package manager.')
    destination = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'hyprland-rice/deps'
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rice-dependencies-') as td:
        subprocess.run(['dnf', 'download', '--destdir=' + td, 'kf6-syntax-highlighting.' + platform.machine()], check=True)
        for rpm in Path(td).glob('*.rpm'):
            unpack = subprocess.Popen(['rpm2cpio', str(rpm)], stdout=subprocess.PIPE)
            subprocess.run(['cpio', '-idmu', '--quiet', '-D', str(destination)], stdin=unpack.stdout, check=True)
            unpack.stdout.close()
            if unpack.wait(): raise RuntimeError('RPM extraction failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-missing', action='store_true')
    args = parser.parse_args()
    if args.install_missing: install_missing()
    print(json.dumps(inventory(), indent=2))
