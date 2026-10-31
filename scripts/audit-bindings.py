#!/usr/bin/env python3
"""Compare effective bindings against a saved pre-switch hyprctl binds -j snapshot."""
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integration'))
from shortcuts import ACTIONS


def chord(row):
    return row['modmask'], row.get('key', '').lower(), row.get('keycode', 0)


def normalized_arg(row):
    value = row.get('arg', '')
    # One retained desktop chord changes backend while preserving its action.
    roots = (str(Path.home()), '$HOME')
    aliases = {f'{interpreter} "{home}/.config/hypr/UserScripts/rice-desktop/{file}"'
               for home in roots for interpreter, file in (
                   ('python3', 'desktop.py'), ('/usr/bin/python3', 'desktop.py'),
                   ('bash', 'desktop.sh'))}
    return 'rice:desktop-toggle' if row['dispatcher'] == 'exec' and value in aliases else value


def audit(before, after):
    mask = {'SUPER': 64, 'CTRL': 4, 'ALT': 8, 'SHIFT': 1}
    redirected = {(sum(mask[m] for m in mods.split()), key.lower(), 0) for mods, key, *_ in ACTIONS}
    previous = {chord(row) for row in before}
    current = {chord(row) for row in after}
    missing = previous - current
    old_actions = Counter((chord(r), r['dispatcher'], normalized_arg(r)) for r in before if chord(r) not in redirected)
    new_actions = Counter((chord(r), r['dispatcher'], normalized_arg(r)) for r in after if chord(r) not in redirected)
    changed = old_actions - new_actions
    duplicates = [key for key in redirected if sum(chord(r) == key for r in after) != 1]
    return {'before_chords': len(previous), 'after_chords': len(current), 'missing_chords': len(missing),
            'changed_unrelated_actions': sum(changed.values()), 'redirected_chords_without_exactly_one_action': len(duplicates)}


if __name__ == '__main__':
    before = json.loads(Path(sys.argv[1]).read_text())
    after = json.loads(subprocess.check_output(['hyprctl', 'binds', '-j'], text=True))
    result = audit(before, after)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if any(result[key] for key in ('missing_chords', 'changed_unrelated_actions', 'redirected_chords_without_exactly_one_action')) else 0)
