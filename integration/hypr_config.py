#!/usr/bin/env python3
"""Persist native dashboard option changes in an integration-owned Hyprland conf."""
import argparse
import fcntl
import os
from pathlib import Path
import re
import subprocess
import tempfile


def update(path, pairs, resets):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        values = {}
        if path.exists():
            for line in path.read_text().splitlines():
                if '=' in line:
                    key, value = line.split('=', 1)
                    values[key.strip()] = value.strip()
        for key in resets: values.pop(key, None)
        for key, value in pairs:
            if not re.fullmatch(r'[a-zA-Z0-9_:-]+', key) or any(char in value for char in '\n\r#{}'):
                raise ValueError('Invalid Hyprland option')
            if value == '[[EMPTY]]': values.pop(key, None)
            else: values[key] = value
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as out:
            out.write('# Native dashboard overrides; applied only in the end4 profile.\n')
            for key, value in sorted(values.items()): out.write(f'{key} = {value}\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(out.name, path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, default=Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'hyprland-rice/end4/hyprland.conf')
    parser.add_argument('--set', nargs=2, action='append', default=[])
    parser.add_argument('--reset', action='append', default=[])
    parser.add_argument('--anim-preset')
    parser.add_argument('--anim-file')
    args = parser.parse_args()
    if args.anim_preset:
        config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
        # Use the installed JaKooLit animation menu and preserve its own backups.
        raise SystemExit(subprocess.call(['bash', str(config / 'hypr/scripts/Animations.sh')]))
    update(args.file, args.set, args.reset)
    subprocess.run(['hyprctl', 'reload'], check=True)
