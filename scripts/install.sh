#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "$(realpath -- "$0")")/.." && pwd)"
cargo build --locked --release --manifest-path "$root/rice-core/Cargo.toml"
exec "$root/rice-core/target/release/rice-core" profile "$root" "$@"
