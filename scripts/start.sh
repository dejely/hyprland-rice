#!/usr/bin/env bash
set -euo pipefail
# Import only display/session identifiers; no credentials or unrelated variables.
systemctl --user import-environment WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE XDG_CURRENT_DESKTOP DISPLAY
systemctl --user start rice-desktop.service
