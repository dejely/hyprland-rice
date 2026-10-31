# hyprland-rice

An Arch-styled desktop for an existing JaKooLit Hyprland installation. Choose the full end4-pC shell or the original JaKooLit profile with the task cards and compact Waybar. Both use the same local tasks and wallpaper colors.

## Install and switch

Keep this checkout in a permanent location. First inspect dependencies, then install only missing ones:

```bash
/usr/bin/python3 integration/dependencies.py
/usr/bin/python3 integration/dependencies.py --install-missing
/usr/bin/python3 scripts/install.py install --profile end4
```

The dependency helper inventories the installed commands. On Fedora it can extract the missing KDE syntax-highlighting QML package into a user-local directory, without sudo. Other missing commands are reported for installation with the actual host package manager. The tested host is Fedora; Arch branding is presentation. System updates detect the host and use dnf, pacman, or apt-get. Updates require the usual local administrator authentication. Automatic update checks are off initially.

Quickshell, Hyprland, Python 3, systemd user services, Wallust, ImageMagick, cliphist, wl-clipboard, brightnessctl, kitty, libnotify, hyprlock, and hypridle must already be available. The shell also needs the Qt Quick Controls, Effects, Positioning, Multimedia, Qt5Compat, KDE Kirigami and syntax-highlighting QML modules. The pinned shell includes its Material Symbols fonts; other text uses Noto Sans and your Nerd Font.

The installer builds a runtime copy under `~/.local/state/hyprland-rice/end4-runtimes/` and keeps `rice-desktop` as the Quickshell config and systemd service name. Repeating installation builds a new generation before changing the config symlink. The repository's upstream snapshot is never edited by installation.

Switch back with:

```bash
/usr/bin/python3 scripts/install.py install --profile jakoolit
```

End4 startup disables backed-up executable entries for Waybar, notification daemons, wallpaper daemons, and the separate overview. End4 owns those surfaces. Hypridle stays active, with its lock command backed up and redirected to hyprlock. The existing lock shortcut still sends the session lock request. Native lock actions use the same hyprlock wrapper. Window decorations and animations stay as configured until you explicitly change them.

The original no-profile command remains available for installing the JaKooLit overlay on a fresh setup:

```bash
/usr/bin/python3 scripts/install.py install
```

## Appearance and widgets

End4 starts with your current wallpaper, dark translucent surfaces, 20 px card corners and subtle borders. Profile, calendar and tasks sit on the left; clock, music, weather and CPU/RAM/battery sit on the right. The compact centered bottom bar contains the Arch launcher icon, workspaces, clock, tray, audio, network and battery.

Native widget controls handle movement, resizing and visibility. Right-click the desktop for widget controls; right-click a widget to toggle the movement lock. Use the resize grip on supported widgets. Positions, sizes and visibility persist in `~/.config/hyprland-rice/end4/config.json`. The task card also has a resize grip. Layout changes are separate from task data.

Music follows active MPRIS players and says “No active player” when none is available. Weather starts with a city-setup prompt and GPS disabled. Account-dependent features, online presets, AI and shared weather API defaults are unconfigured. Supply your own settings through the native interface if wanted.

Native wallpaper selection runs JaKooLit's existing Wallust templates so terminal and application palettes still update. `integration/palette.py` maps those colors to the shell's Material roles. Invalid or partially regenerated palettes leave the last valid colors in place. The runtime does not launch swww to render wallpapers. Color settings provide wallpaper selection and regeneration through this pipeline.

Dashboard compositor options write a separate `~/.config/hyprland-rice/end4/hyprland.conf`, sourced only while end4 is selected. Merely loading or searching settings does not apply the upstream compositor defaults. Animation preset actions open the installed JaKooLit menu.

## Shortcuts

Existing terminal, browser, file-manager, custom application, window-management, screenshot and lock chords remain in their existing files. Each redirected chord is unbound before its new action is added.

| Shortcut | End4 action |
|---|---|
| Super + D | Native launcher |
| Super + A | Native overview |
| Super + W | Native wallpaper selector |
| Super + T | Wallpaper/colors settings |
| Super + Shift + E | Native dashboard |
| Super + Ctrl + B | Bar styling settings |
| Super + Alt + B | Bar layout settings |
| Super + Ctrl + Alt + B | Toggle bar |
| Super + Alt + R | Restart rice-desktop |
| Super + Alt + V | Native clipboard |
| Super + Shift + N | Native notification panel |
| Super + Ctrl + D | Reveal desktop or return |
| Super + H / Super + Shift + K | Native searchable shortcut help |
| Super + Alt + E | Native emoji picker |
| Ctrl + Alt + W | Native random wallpaper |

The launcher's `<` search and the JaKooLit cheat sheet both read `hyprctl binds -j`, so they show effective bindings, including custom additions. An existing Super + Shift + D desktop shortcut is preserved when present. The launcher and overview share upstream's native search/overview surface.

## Tasks and IPC

All native task views use the existing atomic Python backend and `~/.local/share/hyprland-rice/tasks.json`. IDs, completion flags and creation dates are preserved. The desktop card supports adding, editing, completing, deleting and undoing deletion. Blank or unreadable data shows an error and preserves the file. Retry reloads it. Undo lasts until another deletion or a shell restart.

Each mutation locks the store, reads its current contents and atomically replaces the file. Concurrent writers therefore retain each other's saves. The UI reloads on its own operations or explicit refresh; it does not continuously poll external edits.

```bash
qs ipc -c rice-desktop call desktop status
qs ipc -c rice-desktop call desktop refreshTasks
qs ipc -c rice-desktop call desktop task list '{}'
```

`desktop.task(action, payload)` retains `list`, `add`, `edit`, `toggle`, `delete` and `restore`. It returns whether a request started; wait for `desktop.status().busy` to clear and check `error`. Personal tasks, settings, wallpaper files, runtime generations and credentials are outside Git.

## Backups and removal

Backups and switch manifests live under `~/.local/state/hyprland-rice`. Switching back restores pre-switch files and symlink targets. A conflicting edit to a managed startup or shortcut file stops rollback before restoration; reconcile that file against the backup and manifest, then retry. Your edits are retained. Native end4 settings and compositor overrides persist for the next switch.

```bash
/usr/bin/python3 scripts/install.py uninstall
```

Uninstall first restores the previous profile, then removes the original overlay if installed. Tasks, wallpapers, native settings, backups and downloaded user-local dependencies remain. `--no-start` manages files without changing session processes.

## Verification

```bash
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 tests/smoke_end4.py
/usr/bin/python3 tests/smoke_quickshell.py
systemctl --user status rice-desktop.service
hyprctl configerrors
```

The native smoke test creates a temporary 1920 × 1200 headless output, isolates settings/tasks/cache and D-Bus, checks the real task controls, long-list scrolling, widget layout persistence, palette recovery, dashboard sections and unreadable-file errors, then removes the output and restores monitor focus. It briefly focuses the headless output to render and exercise input. It also traces compositor commands to reject startup reloads. See [validation results](docs/validation.md) for the checks actually run and remaining limitations.

## Attribution

[end4-pC](https://github.com/pctrade/end4-pC), maintained by pctrade and based on end-4's illogical-impulse, is pinned to `91c19a4da710910b2c54a651f27801453cfd8ac0`. Its GPL-3.0 license and credits are preserved under [vendor/end4-pC](vendor/end4-pC/LICENSE). The public shared weather fallback is cleared; all integration patches live outside the snapshot. See [upstream provenance](vendor/UPSTREAM.md).

The base desktop and Wallust pipeline belong to [JaKooLit's Hyprland-Dots](https://github.com/JaKooLit/Hyprland-Dots). Wallpaper credits remain with the original artists in [Wallpaper-Bank](https://github.com/JaKooLit/Wallpaper-Bank). Shell surfaces use [Quickshell](https://quickshell.org/); the rollback bar uses [Waybar](https://github.com/Alexays/Waybar). Changes derived from the vendored shell retain its GPL-3.0 terms.
