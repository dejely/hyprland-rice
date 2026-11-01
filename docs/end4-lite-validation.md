# end4-lite validation

Test host: Fedora 44, Hyprland 0.56.2, Quickshell 0.3.2, Qt 6.11.2, 1920 × 1200 at scale 1. The profile retains Arch presentation and uses the actual host package manager for updates.

Status on 2026-11-01: implemented and opt-in, with JaKooLit restored after live checks. Functional checks pass. The strict 250 MiB total-service memory gate remains unmet; lower process memory is not presented as a pass for that gate.

## Runtime

```text
rice-desktop.service
  Quickshell: background, widgets, bar, notifications, settings writer, task undo
    rice-core tool: temporary broker while a panel is open
      Quickshell: launcher, dashboard, wallpaper picker, notifications, media
```

Closing the last panel exits the temporary shell. Its private settings copy contains only shell configuration; changed fields are sent to the main shell, which performs the persistent write. Concurrent changes to unrelated settings are preserved. Tasks always use `~/.local/share/hyprland-rice/tasks.json`; panel mutations and undo go through the main shell. Only the main shell owns the notification bus name. Panel actions are forwarded to it.

Rust handles atomic storage, palette translation, installation, profile restoration and upstream compatibility helpers. Shell scripts launch the binary and serialize thumbnail generation. Existing QML retains the native visual controls. Development tests use Python; the new installer and lite runtime do not invoke it.

## Checks

| Check | Result |
|---|---|
| Automated suite | 32 tests pass, including 40 concurrent task writers, corrupt-file preservation, task IDs, palette recovery, profile edit guards, rollback and thumbnail limits |
| Broker ownership | Final settings flushed; normal close reaps the child; unexpected exit reported; killing the broker terminates its panel |
| Long-running helpers | Network monitor exits with its QML owner, including abrupt termination |
| Rust | `cargo fmt --check` and `cargo clippy --locked -- -D warnings` pass |
| Shell | Installer, thumbnail helper and rendering defaults pass `bash -n` |
| Graphical smoke | Passed native task editing/completion/undo, 25-task scrolling, widget geometry and visibility persistence, incomplete palette recovery, empty weather/media presentation, real dashboard cards and wallpaper thumbnails |
| Shared state | Concurrent main/tool settings changes retained; tool deletion undone from main; child notification dismissal forwarded to the sole main notification owner |
| Native desktop menu | Real menu window constructs in the temporary host; widget controls remain available |
| Panel stress | 20 cycles each of launcher, overview, clipboard, wallpaper, settings, notifications and desktop menu; all 140 cycles completed; one shell and one network monitor remained after each group |
| Live shortcuts | All 163 chords retained; no missing chords, changed unrelated actions or duplicate redirected actions |
| Live rendering | Desktop and dashboard captured and inspected at 1920 × 1200; center clear, one native bar, dark cards and wallpaper colors retained |
| Live restart | Killed the main shell while settings were open; systemd recovered the main shell and desktop IPC |
| Wallpaper | Reapplied the current image through the Rust/Wallust path; native colors remained available and no competing wallpaper daemon was started |
| Live rollback | Fixed installer verified on the laptop; original Quickshell link and binding actions restored; no Hyprland config errors; personal task hash unchanged |
| Idle/lock | Hypridle retained and running; correct native `lock_cmd` installed and original command restored on rollback; hyprlock executable present; authentication not exercised |

The graphical smoke test uses isolated config/data/state/cache and a private D-Bus session on a temporary output. Run graphical tests serially: focus grabs belong to the compositor and can conflict even on separate headless outputs.

```bash
cargo build --locked --release --manifest-path rice-core/Cargo.toml
/usr/bin/python3 -m unittest discover -s tests -v
RICE_SMOKE_PROFILE=end4-lite /usr/bin/python3 tests/smoke_end4.py
/usr/bin/python3 tests/profile_memory.py --profile end4-lite \
  --no-depth --atlas-size 512 --render-loop basic --shared-bus \
  --seconds 600 --cycles 20 --report /tmp/rice-lite-memory.json
```

## Memory measurement

The 250 MiB target applies to idle memory after startup and after panel use. The measurement harness records the entire service cgroup, child processes, swap, proportional resident memory (PSS), peak usage and kernel memory categories. Virtual address space is not a RAM measurement. Open-panel peaks are recorded separately from settled idle usage. Reclaimable file cache is reported explicitly rather than silently omitted. Reports and captures remain outside Git.

The original full-shell control settled at 728.3 MiB service memory and 556.6 MiB PSS in the same headless setup. Earlier single-process lite experiments met cold idle but retained substantial memory after panel use; they are not acceptance evidence for the final profile. A broker test exposed orphaned `nmcli monitor` processes; the owner-lifetime guard and its regression test address that cause.

Final broker run: 120 seconds idle followed by 140 panel cycles. Memory pressure caused swapping, which is included below rather than treating lower resident memory as a saving.

| Measurement | Total service + swap | PSS + service swap, upper bound |
|---|---:|---:|
| Original full-shell settled control | 728.3 MiB | 556.6 MiB |
| Lite at the end of the idle phase | 254.1 MiB | 214.2 MiB |
| Lite after all 140 panel cycles | 747.2 MiB | 220.6 MiB |
| Lite live laptop spot check, no swap | 358.3 MiB | 221.6 MiB |

The final stress sample includes 107.5 MiB swap and about 509.5 MiB file cache (`memory.stat.file - shmem`), with one Quickshell and one network monitor. Anonymous memory, shared memory, kernel charges and swap together account for about 236.5 MiB. Clean file cache is reclaimable by Linux, but remains included in the total-service column. These observations support reduced retained process memory and successful panel teardown; they do **not** establish a 250 MiB cache-inclusive ceiling. The largest recorded service peak was 920.9 MiB before separately accounting for swap. Transient panel use can still be expensive.

Reports, logs and screenshots are local `/tmp/rice-lite-final.json*` and `/tmp/rice-lite-live-audit/` artifacts. They are not committed or uploaded. JaKooLit remains selected because the strict total-service target has not passed. Enabling lite is an explicit profile choice, not an automatic rollout.

Live verification also caught a malformed installer lock directive and a config-file deletion gap during rollback. The fixed installer uses a literal-preserving replacement for `lock_cmd` and atomic replacement of watched config files. The regression suite checks the exact lock directive and observes filesystem events to reject deletion of `hyprland.conf` during installation or rollback; live switching and restoration then passed.

`--shared-bus` uses the host's existing session bus to avoid charging duplicate test-only portal services. The active JaKooLit notification server retains its bus name during this memory run. The separate private-bus smoke test verifies native notification ownership and actions.

## Scope and limits

The lite catalog offers profile, calendar, tasks, clock, media, weather and resources. Static installed icon theme variants are supported. Dynamic icon recoloring, lyric fetching and the wider upstream widget catalog remain outside lite; the full `end4` profile remains available.

Qt input events exercise controls, scrolling and saved state. They do not prove physical keyboard input, PAM authentication, HDR, physical display mode changes or account-dependent services. Weather remains at its city-setup prompt; upgrades and account features are not executed. A live lock/authentication/unlock cycle must be tested separately.

Rollback uses `./scripts/install.sh install --profile jakoolit`. Tasks, wallpapers and personal settings are preserved. The installer refuses to overwrite managed files edited outside it.
