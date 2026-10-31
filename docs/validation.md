# Validation: 2026-10-30

Tested on Fedora 44 with Hyprland 0.56.2, Quickshell 0.3.2 and the laptop's 1920 × 1200 eDP-1 output at scale 1. Presentation uses Arch branding; package operations detect Fedora independently.

| Check | Result |
|---|---|
| Python unit suite | 17 tests passed: task lifecycle, simultaneous writers, corrupt/failed writes, repeated installation, rollback, uninstall preservation, palette recovery, generated bindings, safe compositor/monitor edits and runtime builds |
| Native shell on temporary headless output | Passed with isolated config/data/state/cache and a private D-Bus session |
| Native task controls | Add, edit, complete/uncomplete, delete and undo passed; task ID retained |
| Long task list | Scrolled to and completed the last of 25 tasks |
| Layout persistence | Moved, resized, hidden/shown and restarted task widget; saved geometry retained |
| Palette regeneration | Valid colors reload; partial JSON retains the last valid colors; recovery succeeds |
| Dashboard | Settings, color/bar section navigation, visible settings cards, native help, wallpaper selector and notification panel exercised |
| Unreadable task data | Error surfaced; original unreadable JSON retained |
| Effective live keybindings | 163 chords before and after; zero missing chords; zero changed unrelated actions; each redirected chord has exactly one action |
| Live rollback | Original Quickshell link and every original binding action restored; original widget IPC responded; switched back to end4 successfully |
| Personal task store | Hash unchanged across integration, restart and rollback checks |
| Wallpaper pipeline | Reapplied the current wallpaper through integration/wallpaper.py; existing Wallust application templates and native shell palette regenerated |
| Restart recovery | Killed the service's main process; systemd restarted it, and native desktop IPC responded |
| Duplicate owners | End4 profile has no running Waybar, swaync, swww-daemon or standalone overview |
| Live desktop | Captured and inspected at 1920 × 1200; center clear; native background below apps; settings centered and floating at 1100 × 680 |
| Desktop return | Dedicated named desktop workspace reveals widgets and returns to the saved workspace; bar avoids negative numbered workspaces |
| Hyprland configuration | No configuration errors after activation and rollback |
| Hypridle | Retained and running; separate harmless one-second timeout listener fired successfully |
| Hyprlock | Executable and configuration retained; native/session lock routing configured. Full lock/authentication/unlock on the laptop was not exercised |
| Git delivery | Private repository; feature branches; no force-push or history rewriting |

Commands:

```bash
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 tests/smoke_end4.py
/usr/bin/python3 scripts/audit-bindings.py /tmp/rice-live-audit/before-binds.json
hyprctl configerrors
qs ipc -c rice-desktop call desktop status
systemctl --user status rice-desktop.service
```

The QML test sends Qt mouse events and exercises the task input handlers. It verifies Qt control behavior and saved state; it does not prove physical-keyboard typing or PAM authentication. Weather stays unconfigured, so no city/API request was tested. System upgrades and account-dependent features were not executed. Monitor-rule serialization is unit-tested; physical display mode/HDR changes were not performed.

Compositor-output churn can produce transient upstream HyprlandData query parse messages; stored tasks and the shell remain available. The host also reports existing desktop-portal and optional external-monitor brightness warnings. These were not treated as proof of failed desktop operation or as successful portal/HDR validation.

Screenshots, logs, fixtures, user settings, tasks and runtime generations stay outside Git. The inspected captures were saved under `/tmp/rice-end4-*.png`; they are not uploaded to the PRs.
