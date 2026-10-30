#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/python3 "$(dirname -- "$(realpath -- "$0")")/../integration/shortcuts.py" --yad
