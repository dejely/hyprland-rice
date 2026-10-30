#!/usr/bin/env bash
set -euo pipefail
exec 9>"${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/rice-hyprlock.lock"
flock -n 9 || exit 0
pidof hyprlock >/dev/null || hyprlock -q
