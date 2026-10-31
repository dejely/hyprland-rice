#!/usr/bin/env python3
"""Apply native wallpaper selection through JaKooLit's Wallust pipeline."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

from palette import sync


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--mode', choices=['light', 'dark'])
    parser.add_argument('--noswitch', action='store_true')
    parser.add_argument('--start-dir')
    parser.add_argument('path', nargs='?', type=Path)
    args = parser.parse_args()
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'hyprland-rice/end4'
    state.mkdir(parents=True, exist_ok=True)
    settings_path = config / 'hyprland-rice/end4/config.json'
    with (state / 'wallpaper.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        settings = json.loads(settings_path.read_text())
        image = args.image or args.path
        if image is None:
            image = Path(settings['background']['wallpaperPath'])
        image = image.expanduser().resolve(strict=True)
        # Wallust writes existing terminal/application templates; no swww renderer is started.
        subprocess.run(['bash', str(config / 'hypr/scripts/WallustSwww.sh'), str(image)], check=True)
        palette = state / 'user/generated/colors.json'
        if not sync(config / 'quickshell/qml_color.json', palette):
            raise RuntimeError('Wallust palette is incomplete. Previous shell colors retained.')
        # Set through Config IPC so a concurrent layout edit is not overwritten.
        subprocess.run(['qs', 'ipc', '-c', 'rice-desktop', 'call', 'desktop', 'wallpaper', str(image)], check=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        subprocess.run(['notify-send', 'Wallpaper change failed', str(error)], check=False)
        raise SystemExit(1)
