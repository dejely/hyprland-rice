#!/usr/bin/env python3
"""Dispatch shortcuts without shell interpolation or killing unrelated Quickshells."""
import json
import os
from pathlib import Path
import subprocess
import sys


def call(target, method, *args):
    subprocess.run(['qs', 'ipc', '-c', 'rice-desktop', 'call', target, method, *args], check=True)


def main(action):
    if action == 'desktop':
        subprocess.run(['/usr/bin/python3', str(Path(__file__).with_name('desktop.py'))], check=True)
        return
    if action == 'refresh':
        subprocess.run(['systemctl', '--user', 'restart', 'rice-desktop.service'], check=True)
        return
    mapping = {
        'launcher': ('search', 'toggle'), 'overview': ('search', 'workspacesToggle'),
        'wallpaper': ('wallpaperSelector', 'toggle'), 'colors': ('desktop', 'settings', 'interface'),
        'settings': ('settings', 'toggle'), 'bar-style': ('desktop', 'settings', 'bar'),
        'bar-layout': ('desktop', 'settings', 'bar'), 'bar-toggle': ('bar', 'toggle'),
        'clipboard': ('search', 'clipboardToggle'), 'notifications': ('sidebarRight', 'toggle'),
        'help': ('search', 'help'), 'emoji': ('search', 'emojiToggle'),
        'random-wallpaper': ('wallpaperSelector', 'random'),
    }
    call(*mapping[action])


if __name__ == '__main__':
    main(sys.argv[1])
