# hyprland-rice

A small desktop customization for JaKooLit's Hyprland dots: a local task list, a clock card, and a compact bottom Waybar. The cards sit behind application windows and use the colors generated when you change wallpapers through JaKooLit's selector. Your wallpaper and existing overview stay in place.

This was built and checked on Hyprland 0.56.2, and Quickshell 0.3.2 at 1920 × 1200. The widget prefers the laptop's eDP display and falls back to the first screen. The configuration is intended for JaKooLit's existing directory structure, including its Wallust templates.

## Install

Keep this checkout in a permanent location; installation links directly to it. You need Python 3, Quickshell, Waybar, Hyprland, and a systemd user session. Rofi, pavucontrol, pactl, and nm-connection-editor provide the bar's launcher, audio, and network actions.

```bash
python3 scripts/install.py install
```

The installer saves original files and symlink targets under `~/.local/state/hyprland-rice`, adds marked entries to JaKooLit's user configuration, and starts the widgets and bar. Running it again does not duplicate entries or replace the first backup. It refuses to overwrite installed links that you changed yourself.

The widgets run as `rice-desktop.service`. The Hyprland startup entry imports the display variables and starts that service each session. The service restarts the widget if JaKooLit's wallpaper refresh kills Quickshell. It does not start or replace the existing overview.

## Use

Press **Super + Ctrl + D** to visit an empty desktop workspace on the current monitor. Press it again to return. This replaces JaKooLit's default "remove master" binding. It is also listed in the **Super + H** cheat sheet, through a wrapper that leaves the vendor help script unchanged. Application windows are not moved or closed. The widgets are on the laptop screen, so switch from that screen to interact with them.

Click the task field, type a task, and press Enter or the plus button. Use the circle to complete it, the pencil to edit, and the cross to delete. Press Enter or the save checkmark to save an edit, or Escape to cancel. Deleted tasks can be restored with Undo until the widget restarts or another task is deleted. Completed tasks live in a collapsible section.

Tasks save after every change to `~/.local/share/hyprland-rice/tasks.json`, outside this repository. The store uses a process lock and atomic replacement, with private file permissions. A corrupt task file produces an error and stays untouched; correct or restore that file, then use the retry button. There is no online account or synchronization.

Use **Super + W** to change the wallpaper as usual. The widget watches `~/.config/quickshell/qml_color.json`; Waybar imports JaKooLit's generated palette. Partial or invalid palettes leave the last valid widget colors in place. No wallpaper images are included here.

The bottom bar offers the Rofi launcher, workspaces, clock, tray, volume, network, and battery. Click volume for pavucontrol, right-click it to mute, or scroll to adjust it. Click the network icon to open connection settings. JaKooLit's bar style/layout selectors can replace the active custom bar. To return to this bar, run `python3 scripts/install.py install --restore-bar`; the selected bar links are backed up before replacement.

## Check and remove

```bash
python3 -m unittest discover -s tests -v
python3 tests/smoke_quickshell.py
systemctl --user status rice-desktop.service
qs ipc -c rice-desktop call desktop status
hyprctl configerrors
```

Task operations are also exposed through Quickshell IPC for integration checks. `desktop.task(action, payload)` accepts `list`, `add`, `edit`, `toggle`, `delete`, or `restore`, with a JSON object payload matching the Python store. It returns whether the request started; read `desktop.status()` after the busy flag clears to check completion or errors. `desktop.refreshTasks()` reloads tasks changed externally. The UI refreshes on its own operations; it does not continuously poll the task file.

```bash
python3 scripts/install.py uninstall
```

Uninstall stops the widget, removes its marked configuration entries, restores the previous bar files or symlinks, and restarts Waybar. It keeps tasks and backups. Later edits outside the marked blocks are preserved; externally replaced managed paths are left untouched. For isolated file-management checks, both commands accept `--no-start`.

The unit tests cover task lifecycle, restart persistence, simultaneous writers, blank input, corrupt data, failed writes, repeated installation, restoration, and later user edits. The optional Quickshell smoke check requires a running Hyprland session, QtTest, and grim. It creates a temporary headless output, exercises the real QML with isolated tasks and colors, then removes that output. It checks editing, completion, deletion, undo, long lists, palette reload, restart persistence, and corrupt-file errors without changing your task data. These checks do not replace inspecting appearance and input on the physical display.

## Credits

The desktop layout was inspired by the reference image supplied for this project. This is an independent customization of [JaKooLit's Hyprland-Dots](https://github.com/JaKooLit/Hyprland-Dots), using its existing theme pipeline rather than redistributing the dots. Wallpaper credits belong to the original artists listed in [Wallpaper-Bank](https://github.com/JaKooLit/Wallpaper-Bank). The desktop cards use [Quickshell](https://quickshell.org/docs/v0.3.2/); the bar uses [Waybar](https://github.com/Alexays/Waybar).
