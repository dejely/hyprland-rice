#!/usr/bin/env python3
"""Install the overlay with reversible symlinks and marked Hyprland additions."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[1]
HOME = Path.home()
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config'))
STATE = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state')) / 'hyprland-rice'
BEGIN = '# BEGIN hyprland-rice'
END = '# END hyprland-rice'


def block(path, content=None):
    text = path.read_text() if path.exists() else ''
    if BEGIN in text:
        start = text.index(BEGIN)
        end = text.find(END, start)
        if end < 0:
            raise RuntimeError(f'Incomplete integration block: {path}')
        if start > 0 and text[start - 1] == '\n':
            start -= 1
        end += len(END)
        if text[end:end + 1] == '\n':
            end += 1
        text = text[:start] + text[end:]
    if content is not None:
        text += '\n' + BEGIN + '\n' + content + '\n' + END + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def restart():
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['hyprctl', 'reload'], check=True)
    subprocess.run(['bash', str(REPO / 'scripts/start.sh')], check=True)
    subprocess.run(['systemctl', '--user', 'restart', 'rice-desktop.service'], check=True)
    subprocess.run(['pkill', '-x', 'waybar'], check=False)
    log = STATE / 'waybar.log'
    with log.open('a') as output:
        subprocess.Popen(['waybar'], stdout=output, stderr=output, start_new_session=True)


def install(no_start, restore_bar=False):
    for name in ('python3', 'qs', 'waybar', 'hyprctl', 'systemctl'):
        if not shutil.which(name):
            raise RuntimeError(f'Missing dependency: {name}')
    if not (CONFIG / 'hypr/hyprland.conf').is_file():
        raise RuntimeError('Install JaKooLit/Hyprland first.')
    STATE.mkdir(parents=True, exist_ok=True)
    state_path = STATE / 'install.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'links': [], 'blocks': []}
    backup = STATE / 'backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    # Absolute imports keep GTK paths correct whether it resolves symlink targets or not.
    style = STATE / 'style.css'
    style.write_text('@import url(' + json.dumps((CONFIG / 'waybar/wallust/colors-waybar.css').as_uri())
                     + ');\n@import url(' + json.dumps((REPO / 'waybar/style.css').as_uri()) + ');\n')
    links = {
        CONFIG / 'quickshell/rice-desktop': REPO / 'quickshell/rice-desktop',
        CONFIG / 'waybar/config': REPO / 'waybar/config.jsonc',
        CONFIG / 'waybar/style.css': style,
        CONFIG / 'hypr/UserScripts/rice-desktop': REPO / 'scripts',
        CONFIG / 'systemd/user/rice-desktop.service': REPO / 'systemd/rice-desktop.service',
    }
    # Validate repeat installations before changing anything.
    recorded = {item['path']: item for item in state['links']}
    bar_paths = {CONFIG / 'waybar/config', CONFIG / 'waybar/style.css'}
    replaced = set()
    for path, target in links.items():
        if str(path) in recorded and (not path.is_symlink() or Path(os.readlink(path)) != target):
            if restore_bar and path in bar_paths:
                replaced.add(path)
            else:
                raise RuntimeError(f'Installed link was changed externally; preserved: {path}')
    for path, target in links.items():
        if path in replaced:
            backup.mkdir(parents=True, exist_ok=True)
            saved = backup / ('selected-' + path.name)
            if path.is_symlink() or path.is_file():
                shutil.copy2(path, saved, follow_symlinks=False)
                path.unlink()
            elif path.is_dir():
                shutil.copytree(path, saved, symlinks=True)
                shutil.rmtree(path)
            path.symlink_to(target)
            print('Restored custom bar link:', path)
        if str(path) in recorded:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {'path': str(path), 'target': str(target), 'original': 'missing'}
        if path.is_symlink():
            entry.update(original='symlink', link=os.readlink(path))
            path.unlink()
        elif path.exists():
            backup.mkdir(parents=True, exist_ok=True)
            saved = backup / str(len(state['links']))
            if path.is_dir():
                shutil.copytree(path, saved, symlinks=True)
                shutil.rmtree(path)
            else:
                shutil.copy2(path, saved)
                path.unlink()
            entry.update(original='backup', backup=str(saved))
        path.symlink_to(target, target_is_directory=target.is_dir())
        state['links'].append(entry)
        state_path.write_text(json.dumps(state, indent=2) + '\n')
    user = CONFIG / 'hypr/UserConfigs'
    additions = {
        user / 'Startup_Apps.conf': 'exec-once = bash "$HOME/.config/hypr/UserScripts/rice-desktop/start.sh"',
        user / 'UserKeybinds.conf': '\n'.join([
            'unbind = SUPER CTRL, D',
            'bindd = SUPER CTRL, D, Show desktop or return, exec, python3 "$HOME/.config/hypr/UserScripts/rice-desktop/desktop.py"',
            'unbind = SUPER, H',
            'bindd = SUPER, H, help / cheat sheet, exec, bash "$HOME/.config/hypr/UserScripts/rice-desktop/key-hints.sh"',
        ]),
        user / 'WindowRules.conf': '\n'.join([
            'layerrule = match:namespace ^rice-desktop-.*, blur on',
            'layerrule = match:namespace ^rice-desktop-.*, ignore_alpha 0.2',
            'layerrule = match:namespace waybar, blur on',
        ]),
    }
    for path, content in additions.items():
        if str(path) not in state['blocks']:
            backup.mkdir(parents=True, exist_ok=True)
            if path.exists():
                shutil.copy2(path, backup / path.name)
            state['blocks'].append(str(path))
            state_path.write_text(json.dumps(state, indent=2) + '\n')
        block(path, content)
    if not no_start:
        restart()
    print('Installed. Backups and uninstall state:', STATE)


def uninstall(no_start):
    state_path = STATE / 'install.json'
    if not state_path.exists():
        print('Nothing installed.')
        return
    state = json.loads(state_path.read_text())
    if not no_start:
        subprocess.run(['systemctl', '--user', 'stop', 'rice-desktop.service'], check=False)
    for name in state['blocks']:
        path = Path(name)
        if path.exists():
            block(path)
    for entry in reversed(state['links']):
        path = Path(entry['path'])
        if not path.is_symlink() or os.readlink(path) != entry['target']:
            print('Preserved externally changed path:', path)
            continue
        path.unlink()
        if entry['original'] == 'symlink':
            path.symlink_to(entry['link'])
        elif entry['original'] == 'backup':
            saved = Path(entry['backup'])
            if saved.is_dir():
                shutil.copytree(saved, path, symlinks=True)
            else:
                shutil.copy2(saved, path)
    state_path.unlink()
    if not no_start:
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
        subprocess.run(['hyprctl', 'reload'], check=True)
        subprocess.run(['pkill', '-x', 'waybar'], check=False)
        with (STATE / 'waybar.log').open('a') as output:
            subprocess.Popen(['waybar'], stdout=output, stderr=output, start_new_session=True)
    print('Uninstalled. Tasks and backups were preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'uninstall'])
    parser.add_argument('--profile', choices=['end4', 'jakoolit'], help='Switch shell profile; preserves profile settings and tasks')
    parser.add_argument('--no-start', action='store_true', help='Only manage files; do not touch session processes')
    parser.add_argument('--restore-bar', action='store_true', help='Back up and replace bar links changed by a layout/style selector')
    args = parser.parse_args()
    try:
        if args.profile or (STATE / 'end4-profile.json').exists():
            import sys
            sys.path.insert(0, str(REPO / 'integration'))
            import profiles
            if args.action == 'uninstall':
                profiles.switch('jakoolit', args.no_start)
                uninstall(args.no_start)
            else:
                profiles.switch(args.profile or 'end4', args.no_start)
        elif args.action == 'install':
            install(args.no_start, args.restore_bar)
        else:
            uninstall(args.no_start)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')
