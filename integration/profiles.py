#!/usr/bin/env python3
"""Reversible end4 profile layered over the existing JaKooLit rice installation."""
from datetime import datetime
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from build import build, ROOT
from palette import atomic_json, sync

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
STATE = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'hyprland-rice'
MANIFEST = STATE / 'end4-profile.json'
MARKER = '# rice-end4 disabled: '


def snapshot(path, directory, index):
    entry = {'path': str(path), 'kind': 'missing'}
    if path.is_symlink():
        entry.update(kind='link', target=os.readlink(path))
    elif path.exists():
        saved = directory / str(index)
        if path.is_dir(): shutil.copytree(path, saved, symlinks=True)
        else: shutil.copy2(path, saved)
        entry.update(kind='backup', backup=str(saved))
    return entry


def restore(entry):
    path = Path(entry['path'])
    if path.is_symlink() or path.is_file(): path.unlink()
    elif path.is_dir(): shutil.rmtree(path)
    if entry['kind'] == 'link': path.symlink_to(entry['target'])
    elif entry['kind'] == 'backup':
        saved = Path(entry['backup'])
        if saved.is_dir(): shutil.copytree(saved, path, symlinks=True)
        else: shutil.copy2(saved, path)


def legacy():
    spec = importlib.util.spec_from_file_location('rice_legacy', ROOT / 'scripts/install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def set_profile(name):
    atomic_json(STATE / 'profile.json', {'profile': name})


def rollback():
    if not MANIFEST.exists():
        set_profile('jakoolit')
        return
    manifest = json.loads(MANIFEST.read_text())
    # Preflight before restoring anything; never discard user edits made after switching.
    for entry in manifest['entries']:
        path = Path(entry['path'])
        if entry.get('installed_text') is not None:
            if not path.is_file() or path.read_text() != entry['installed_text']:
                raise RuntimeError(f'Profile file changed externally; preserved: {path}. Reconcile with {MANIFEST} before switching.')
        elif entry.get('installed_link') is not None:
            if not path.is_symlink() or os.readlink(path) != entry['installed_link']:
                raise RuntimeError(f'Profile link changed externally; preserved: {path}')
    for entry in reversed(manifest['entries']): restore(entry)
    MANIFEST.unlink()
    set_profile('jakoolit')


def install_end4():
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text())
        path = CONFIG / 'quickshell/rice-desktop'
        entry = next(e for e in manifest['entries'] if e['path'] == str(path))
        if not path.is_symlink() or os.readlink(path) != entry['installed_link']:
            raise RuntimeError(f'Profile link changed externally; preserved: {path}')
        runtime = build(STATE / 'end4-runtimes' / datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        temporary = path.with_name('rice-desktop.next')
        temporary.unlink(missing_ok=True)
        temporary.symlink_to(runtime)
        os.replace(temporary, path)
        entry['installed_link'] = str(runtime)
        atomic_json(MANIFEST, manifest)
        set_profile('end4')
        return
    if not (CONFIG / 'hypr/hyprland.conf').is_file():
        raise RuntimeError('Install JaKooLit/Hyprland first.')
    for cmd in ('qs', 'hyprctl', 'systemctl', 'wallust', 'python3'):
        if not shutil.which(cmd): raise RuntimeError(f'Missing dependency: {cmd}')
    runtime = build(STATE / 'end4-runtimes' / datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup = STATE / 'backups' / ('end4-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True)
    entries = []
    existing_settings = CONFIG / 'hyprland-rice/end4/config.json'
    if existing_settings.exists(): shutil.copy2(existing_settings, backup / 'settings.json')

    def change(path, content=None, target=None):
        entry = snapshot(path, backup, len(entries))
        path.parent.mkdir(parents=True, exist_ok=True)
        entries.append(entry)
        # Record before mutation for recovery after an interrupted install.
        atomic_json(MANIFEST, {'entries': entries})
        if path.is_symlink() or path.is_file(): path.unlink()
        elif path.is_dir(): shutil.rmtree(path)
        if target is not None:
            path.symlink_to(target)
            entry['installed_link'] = str(target)
        else:
            path.write_text(content)
            entry['installed_text'] = content
        atomic_json(MANIFEST, {'entries': entries})

    settings = CONFIG / 'hyprland-rice/end4/config.json'
    settings.parent.mkdir(parents=True, exist_ok=True)
    if not settings.exists():
        data = json.loads((ROOT / 'integration/defaults.json').read_text())
        current = CONFIG / 'rofi/.current_wallpaper'
        if current.exists():
            data['background']['wallpaperPath'] = str(current.resolve())
        else:
            raise RuntimeError('Cannot find current wallpaper: ~/.config/rofi/.current_wallpaper')
        atomic_json(settings, data)
    sync(CONFIG / 'quickshell/qml_color.json', STATE / 'end4/user/generated/colors.json')
    try:
        change(CONFIG / 'quickshell/rice-desktop', target=runtime)
        change(CONFIG / 'hypr/UserScripts/rice-desktop', target=ROOT / 'scripts')
        change(CONFIG / 'systemd/user/rice-desktop.service', target=ROOT / 'systemd/rice-desktop.service')
        # Disable only competing executable lines, in both default and user startup files.
        for relative in ('hypr/configs/Startup_Apps.conf', 'hypr/UserConfigs/Startup_Apps.conf'):
            path = CONFIG / relative
            if not path.exists(): continue
            lines = path.read_text().splitlines(keepends=True)
            for i, line in enumerate(lines):
                if re.match(r'\s*exec(?:-once)?\s*=', line) and re.search(r'\b(?:waybar|swaync|dunst|mako|swww-daemon|hyprpaper|mpvpaper)\b|qs\s+(?:-c|--config)\s+overview', line):
                    lines[i] = MARKER + line
            content = ''.join(lines)
            if relative.endswith('UserConfigs/Startup_Apps.conf') and 'rice-desktop/start.sh' not in content:
                content += '\n# end4 profile\nexec-once = bash "$HOME/.config/hypr/UserScripts/rice-desktop/start.sh"\n'
            change(path, content)
        keys = CONFIG / 'hypr/UserConfigs/UserKeybinds.conf'
        content = keys.read_text() if keys.exists() else ''
        # Keep existing chords, remove only the old integration overrides for the chords replaced below.
        # Super+Shift+D is retained by the original block when present.
        content += '\n# BEGIN rice-end4 shortcuts\n' + (ROOT / 'integration/keybinds.conf').read_text() + '# END rice-end4 shortcuts\n'
        change(keys, content)
        idle = CONFIG / 'hypr/hypridle.conf'
        if idle.is_file():
            content = re.sub(r'(?m)^(\s*lock_cmd\s*=).*$', r'\1 bash "$HOME/.config/hypr/UserScripts/rice-desktop/lock.sh"', idle.read_text())
            change(idle, content)
        overrides = CONFIG / 'hyprland-rice/end4/hyprland.conf'
        if not overrides.exists(): overrides.write_text('# Native dashboard overrides\n')
        defaults = CONFIG / 'hypr/UserConfigs/01-UserDefaults.conf'
        content = defaults.read_text() if defaults.exists() else ''
        monitors = CONFIG / 'hyprland-rice/end4/monitors.conf'
        if not monitors.exists(): monitors.write_text('# Native dashboard monitor overrides\n')
        content += '\n# end4 profile\nsource = $HOME/.config/hyprland-rice/end4/hyprland.conf\n'
        change(defaults, content)
        main = CONFIG / 'hypr/hyprland.conf'
        change(main, main.read_text() + '\n# end4 profile: display overrides follow the original monitor configuration\nsource = $HOME/.config/hyprland-rice/end4/monitors.conf\n')
        rules = CONFIG / 'hypr/UserConfigs/WindowRules.conf'  
        content = rules.read_text() if rules.exists() else ''
        content += '\n# end4 profile\nlayerrule = match:namespace ^quickshell:.*, blur on\nlayerrule = match:namespace ^quickshell:.*, ignore_alpha 0.2\nwindowrule = match:title ^Desktop Settings$, float on\nwindowrule = match:title ^Desktop Settings$, center on\n'
        change(rules, content)
        set_profile('end4')
    except Exception:
        # Restore the exact pre-switch state if any stage fails.
        for entry in reversed(entries): restore(entry)
        MANIFEST.unlink(missing_ok=True)
        raise


def activate(name):
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['hyprctl', 'reload'], check=True)
    if name == 'end4':
        for process in ('waybar', 'swaync', 'swww-daemon', 'dunst', 'mako', 'hyprpaper', 'mpvpaper'):
            subprocess.run(['pkill', '-x', process], check=False)
        subprocess.run(['qs', '-c', 'overview', 'kill'], check=False, stdout=subprocess.DEVNULL)
    if subprocess.run(['pgrep', '-x', 'hypridle'], stdout=subprocess.DEVNULL).returncode == 0:
        subprocess.run(['pkill', '-x', 'hypridle'], check=False)
        with (STATE / 'hypridle.log').open('a') as log:
            subprocess.Popen(['hypridle'], stdout=log, stderr=log, start_new_session=True)
    subprocess.run(['bash', str(ROOT / 'scripts/start.sh')], check=True)
    subprocess.run(['systemctl', '--user', 'restart', 'rice-desktop.service'], check=True)
    if name == 'jakoolit':
        for command in (['swww-daemon', '--format', 'xrgb'], ['swaync'], ['waybar'], ['qs', '-c', 'overview']):
            if subprocess.run(['pgrep', '-x', command[0]], stdout=subprocess.DEVNULL).returncode != 0 or command[0] == 'qs':
                with (STATE / 'rollback.log').open('a') as log:
                    subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)


def switch(name, no_start):
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'profiles.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if name == 'end4': install_end4()
        else: rollback()
        if not no_start: activate(name)
    print('Profile:', name, '| Backups:', STATE / 'backups')
