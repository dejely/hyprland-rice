#!/usr/bin/env python3
"""Reveal a dedicated workspace on this monitor, or return to its saved workspace."""
import json
import os
from pathlib import Path
import subprocess
import fcntl


def hypr(*args):
    return subprocess.check_output(['hyprctl', *args], text=True)


def main():
    directory = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    with (directory / 'rice-desktop-toggle.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        monitor = next(m for m in json.loads(hypr('monitors', '-j')) if m['focused'])
        desktop = 'rice-desktop-' + monitor['name']
        state_file = directory / 'rice-desktop-workspaces.json'
        try:
            previous = json.loads(state_file.read_text())
        except (FileNotFoundError, ValueError):
            previous = {}
        current = monitor['activeWorkspace']
        if current['name'] == desktop:
            target = previous.get(monitor['name'], '1')
        else:
            previous[monitor['name']] = str(current['id']) if current['id'] > 0 else 'name:' + current['name']
            state_file.write_text(json.dumps(previous))
            target = 'name:' + desktop
        hypr('dispatch', 'workspace', target)


if __name__ == '__main__':
    main()
