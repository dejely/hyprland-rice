import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.services
import qs.modules.common
Scope {
    Process {
        id: paletteWorker
        command: ["python3", Quickshell.shellPath("integration/palette.py"),
            Directories.config.toString().replace("file://", "") + "/quickshell/qml_color.json", Directories.generatedMaterialThemePath]
    }
    Timer { interval: 1000; running: true; repeat: true; triggeredOnStart: true; onTriggered: { if (!paletteWorker.running) paletteWorker.running = true; } }

    IpcHandler {
        target: "desktop"
        function status(): string {
            return JSON.stringify({busy: Todo.busy, error: Todo.error, tasks: Todo.list.length,
                completed: Todo.list.filter(t => t.done).length, accent: String(Appearance.m3colors.m3primary),
                settings: GlobalStates.settingsOpen, overview: GlobalStates.overviewOpen})
        }
        function task(action: string, payload: string): bool { return Todo.transact(action, payload); }
        function refreshTasks(): void { Todo.refresh(); }
        function settings(page: string): void { GlobalStates.openSettingsAt(page, "", "", ""); }
        function wallpaper(path: string): void { Config.options.background.wallpaperPath = path; }
        function clipboard(): void { GlobalStates.overviewOpen = true; GlobalStates.searchOpen = true; }
        function help(): void { GlobalStates.overviewOpen = true; }
    }
}
