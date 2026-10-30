#!/usr/bin/env python3
"""Host package operations, independent of presentation branding."""
import argparse
import shutil
import subprocess


def manager():
    # Prefer the host's ID over incidental package tools installed in containers.
    from platform import freedesktop_os_release
    distro = freedesktop_os_release()['ID']
    if distro in ('fedora', 'rhel', 'centos'): return 'dnf'
    if distro in ('arch', 'endeavouros', 'cachyos'): return 'pacman'
    if distro in ('ubuntu', 'debian'): return 'apt-get'
    raise RuntimeError(f'Unsupported host: {distro}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['update', 'count', 'check', 'available'])
    args = parser.parse_args()
    pm = manager()
    if args.action == 'available':
        return 0 if shutil.which(pm) else 1
    if args.action == 'update':
        return subprocess.call(['sudo', pm, *({'dnf': ['upgrade', '--refresh'], 'pacman': ['-Syu'], 'apt-get': ['upgrade']}[pm])])
    if args.action == 'count':
        commands = {'dnf': ['rpm', '-qa'], 'pacman': ['pacman', '-Qq'], 'apt-get': ['dpkg-query', '-W']}
        result = subprocess.run(commands[pm], capture_output=True, text=True, check=True)
        print(f'{len(result.stdout.splitlines())} {pm}')
    else:
        commands = {'dnf': ['dnf', '-q', 'check-upgrade'], 'pacman': ['checkupdates'], 'apt-get': ['apt', 'list', '--upgradable']}
        result = subprocess.run(commands[pm], capture_output=True, text=True)
        if result.returncode not in (0, 2, 100):
            raise RuntimeError(result.stderr.strip() or 'Package query failed')
        lines = result.stdout.splitlines()
        count = sum(bool(line.strip()) and not line.startswith('Listing') for line in lines)
        print(count)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
