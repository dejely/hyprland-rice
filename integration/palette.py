#!/usr/bin/env python3
"""Translate a complete Wallust palette; invalid reads retain the last valid file."""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile


def translate(source):
    def color(name):
        value = '#' + source[name].lstrip('#')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise ValueError(f'Invalid color: {name}')
        return value
    bg, fg, muted, accent = [color(n) for n in ('windowBackground', 'primaryText', 'secondaryText', 'accentPrimary')]
    roles = dict(background=bg, onBackground=fg, surface=bg, surfaceDim=bg, surfaceBright=bg,
                 surfaceContainerLowest=bg, surfaceContainerLow=bg, surfaceContainer=bg,
                 surfaceContainerHigh=bg, surfaceContainerHighest=bg, surfaceVariant=bg,
                 onSurface=fg, onSurfaceVariant=muted, outline=muted, outlineVariant=bg,
                 inverseSurface=fg, inverseOnSurface=bg, inversePrimary=accent,
                 primary=accent, onPrimary=bg, primaryContainer=bg, onPrimaryContainer=fg,
                 secondary=accent, onSecondary=bg, secondaryContainer=bg, onSecondaryContainer=fg,
                 tertiary=accent, onTertiary=bg, tertiaryContainer=bg, onTertiaryContainer=fg,
                 surfaceTint=accent, error='#ffb4ab', onError='#690005', errorContainer='#93000a', onErrorContainer='#ffdad6')
    return roles


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as out:
        temporary = Path(out.name)
        json.dump(value, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def sync(source, destination):
    try:
        roles = translate(json.loads(source.read_text()))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False
    if destination.exists() and destination.read_text() == json.dumps(roles, indent=2) + '\n':
        return True
    atomic_json(destination, roles)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if sync(args.source, args.destination) else 1)
