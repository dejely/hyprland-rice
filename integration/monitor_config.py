#!/usr/bin/env python3
"""Persist native monitor controls as Hyprland monitor rules, without Lua."""
import argparse
import fcntl
import json
from pathlib import Path
import re
from palette import atomic_json

FIELDS = {'disabled', 'position', 'mode', 'scale', 'transform', 'bitdepth', 'cm', 'sdrbrightness', 'sdrsaturation', 'min_luminance', 'max_luminance', 'max_avg_luminance', 'sdr_min_luminance', 'sdr_max_luminance', 'vrr'}


def update(path, output, pairs, resets):
    path.parent.mkdir(parents=True, exist_ok=True)
    state = path.with_suffix('.json')
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = json.loads(state.read_text()) if state.exists() else {}
        options = data.setdefault(output, {})
        if not re.fullmatch(r'[a-zA-Z0-9_.:-]+', output): raise ValueError('Invalid monitor name')
        for key in resets: options.pop(key, None)
        for key, value in pairs:
            if key not in FIELDS or any(c in value for c in '\n\r#{},'):
                raise ValueError('Invalid monitor option')
            options[key] = value
        if not options: data.pop(output, None)
        lines = ['# Native dashboard monitor overrides\n']
        for name, opts in sorted(data.items()):
            if opts.get('disabled') == '1':
                lines.append(f'monitor = {name}, disable\n')
                continue
            rule = [name, opts.get('mode', 'preferred'), opts.get('position', 'auto'), opts.get('scale', '1')]
            for key, value in opts.items():
                if key not in ('mode', 'position', 'scale', 'disabled'): rule.extend((key, str(value)))
            lines.append('monitor = ' + ', '.join(rule) + '\n')
        # The JSON is the editing source; the conf is the compositor input.
        atomic_json(state, data)
        from tempfile import NamedTemporaryFile
        import os
        with NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as out:
            out.write(''.join(lines))
            out.flush()
            os.fsync(out.fileno())
        os.replace(out.name, path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', required=True, type=Path)
    parser.add_argument('--output')
    parser.add_argument('--set', nargs=2, action='append', default=[])
    parser.add_argument('--reset', action='append', default=[])
    parser.add_argument('--dump-all', action='store_true')
    args = parser.parse_args()
    if args.dump_all:
        source = args.file.with_suffix('.json')
        print(source.read_text() if source.exists() else '{}')
    else:
        if not args.output: parser.error('--output is required')
        update(args.file, args.output, args.set, args.reset)
