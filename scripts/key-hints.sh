#!/usr/bin/env bash
set -euo pipefail
# Add our row to JaKooLit's cheat sheet without changing the vendor script.
yad() {
    command yad "$@" \
        " CTRL D" "Show desktop or return" "Tasks and clock"
}
export -f yad
exec bash "$HOME/.config/hypr/scripts/KeyHints.sh"
