#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "$(realpath -- "$0")")/.." && pwd)"
output="$root/rice-core/target/native/Rice/Native"
mkdir -p "$output"
exec 9>"$root/rice-core/target/native-build.lock"
flock 9
qt_version="$(pkg-config --modversion Qt6Qml)"
if [[ -f "$output/qt-version" && "$(cat "$output/qt-version")" == "$qt_version" && -f "$output/libricememory.so" && "$output/libricememory.so" -nt "$root/native/memory.cpp" && "$output/libricememory.so" -nt "$0" ]]; then exit 0; fi
moc_dir="$(pkg-config --variable=libexecdir Qt6Core)"
read -r -a qt_includes <<< "$(pkg-config --cflags Qt6Qml Qt6Quick)"
"$moc_dir/moc" "${qt_includes[@]}" "$root/native/memory.cpp" -o "$output/memory.moc"
read -r -a qt_flags <<< "$(pkg-config --cflags --libs Qt6Qml Qt6Quick)"
c++ -std=c++17 -O2 -fPIC -shared -I"$output" "$root/native/memory.cpp" "${qt_flags[@]}" -o "$output/libricememory.so.next"
mv -- "$output/libricememory.so.next" "$output/libricememory.so"
printf '%s\n' "$qt_version" > "$output/qt-version"
printf 'module Rice.Native\nplugin ricememory\n' > "$output/qmldir"
