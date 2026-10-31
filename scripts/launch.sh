#!/usr/bin/env bash
set -euo pipefail
# User-local Fedora QML dependency fallback, if the system module is missing.
deps="${XDG_DATA_HOME:-$HOME/.local/share}/hyprland-rice/deps/usr/lib64"
if [[ -d "$deps/qt6/qml" ]]; then
    export QML_IMPORT_PATH="$deps/qt6/qml${QML_IMPORT_PATH:+:$QML_IMPORT_PATH}"
    export LD_LIBRARY_PATH="$deps${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
exec /usr/bin/qs --no-duplicate --config rice-desktop
