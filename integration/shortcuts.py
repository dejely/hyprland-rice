#!/usr/bin/env python3
"""Shared action map and effective-binding help for both shell profiles."""
import json
import subprocess

# modifiers, key, description, action
ACTIONS = [
    ('SUPER', 'D', 'Native launcher', 'launcher'),
    ('SUPER', 'A', 'Native overview', 'overview'),
    ('SUPER', 'W', 'Native wallpaper selector', 'wallpaper'),
    ('SUPER', 'T', 'Wallpaper and colors settings', 'colors'),
    ('SUPER SHIFT', 'E', 'Native settings dashboard', 'settings'),
    ('SUPER CTRL', 'B', 'Bar styling settings', 'bar-style'),
    ('SUPER ALT', 'B', 'Bar layout settings', 'bar-layout'),
    ('SUPER CTRL ALT', 'B', 'Toggle native bar', 'bar-toggle'),
    ('SUPER ALT', 'R', 'Refresh integrated shell', 'refresh'),
    ('SUPER ALT', 'V', 'Native clipboard', 'clipboard'),
    ('SUPER SHIFT', 'N', 'Native notification panel', 'notifications'),
    ('SUPER CTRL', 'D', 'Show desktop or return', 'desktop'),
    ('SUPER', 'H', 'Shortcut help', 'help'),
    ('SUPER SHIFT', 'K', 'Search effective shortcuts', 'help'),
    ('SUPER ALT', 'E', 'Native emoji picker', 'emoji'),
    ('CTRL ALT', 'W', 'Native random wallpaper', 'random-wallpaper'),
]


def effective():
    return json.loads(subprocess.check_output(['hyprctl', 'binds', '-j'], text=True))


def keybind_tree(bindings):
    mods = ((64, 'SUPER'), (4, 'CTRL'), (8, 'ALT'), (1, 'SHIFT'))
    return {'name': 'Effective shortcuts', 'children': [], 'keybinds': [
        dict(mods=[name for mask, name in mods if row['modmask'] & mask],
             key=row.get('key') or 'code:' + str(row.get('keycode')),
             dispatcher=row['dispatcher'], params=row.get('arg', ''),
             comment=row.get('description') or row['dispatcher'] + ' ' + row.get('arg', ''))
        for row in bindings]}


if __name__ == '__main__':
    print(json.dumps(keybind_tree(effective())))
