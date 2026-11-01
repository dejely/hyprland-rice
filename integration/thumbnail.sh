#!/usr/bin/env bash
set -euo pipefail
src="$1"; thumb="$2"; max="$3"
cache="${XDG_CACHE_HOME:-$HOME/.cache}/hyprland-rice/end4/thumbnails"
[[ "$thumb" == "$cache/"* && "$thumb" =~ /[a-f0-9]{32}\.png$ && "$max" =~ ^(128|256|512|1024)$ ]] || exit 2
mkdir -p -- "$(dirname -- "$thumb")" "$cache"
exec 9>"$cache/.thumbnail.lock"
flock -w 20 9 || exit 2
[[ -f "$thumb" && ! "$src" -nt "$thumb" ]] && exit 0
temporary="$thumb.$$.tmp.png"
worker=""
cleanup() { [[ -z "$worker" ]] || kill "$worker" 2>/dev/null || true; rm -f -- "$temporary"; }
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
timeout 20s magick -limit thread 1 -limit memory 32MiB -limit map 64MiB -limit disk 128MiB -define "jpeg:size=${max}x${max}" "$src[0]" -thumbnail "${max}x${max}" "$temporary" &
worker=$!
if wait "$worker"; then
    worker=""
    mv -- "$temporary" "$thumb"
    "$(dirname -- "$0")/rice-core" cache-prune
    exit 1
fi
worker=""
exit 2
