//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

ShellRoot {
    id: root
    readonly property var widgetScreen: Quickshell.screens.find(s => s.name.startsWith("eDP")) || Quickshell.screens[0]
    Theme { id: theme }
    SystemClock { id: clock; precision: SystemClock.Minutes }
    TaskCard { id: tasks; theme: theme; screen: root.widgetScreen }

    PanelWindow {
        screen: root.widgetScreen
        anchors { top: true; right: true }
        margins { right: Math.round(screen.width * 0.055); top: Math.round(screen.height * 0.19) }
        implicitWidth: 220
        implicitHeight: 310
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Bottom
        WlrLayershell.namespace: "rice-desktop-clock"
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        Rectangle {
            anchors.fill: parent
            radius: 20
            color: theme.panel
            border { color: theme.border; width: 1 }
            ColumnLayout {
                anchors { fill: parent; margins: 24 }
                spacing: 0
                Text { Layout.alignment: Qt.AlignHCenter; text: Qt.formatDateTime(clock.date, "dddd").toUpperCase(); color: theme.muted; font { family: "Noto Sans"; pixelSize: 11; letterSpacing: 3 } }
                Item { Layout.fillHeight: true }
                Text { Layout.alignment: Qt.AlignHCenter; text: Qt.formatDateTime(clock.date, "HH"); color: theme.foreground; font { family: "Noto Sans"; pixelSize: 76; weight: Font.Bold } lineHeight: 0.95 }
                Text { Layout.alignment: Qt.AlignHCenter; text: Qt.formatDateTime(clock.date, "mm"); color: theme.accent; font { family: "Noto Sans"; pixelSize: 76; weight: Font.Bold } lineHeight: 0.95 }
                Item { Layout.fillHeight: true }
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: theme.border }
                Text { Layout.alignment: Qt.AlignHCenter; Layout.topMargin: 16; text: Qt.formatDateTime(clock.date, "MMM dd · yyyy").toUpperCase(); color: theme.muted; font { family: "Noto Sans"; pixelSize: 12; letterSpacing: 1 } }
            }
        }
    }
    IpcHandler {
        target: "desktop"
        function refreshTasks(): void { tasks.run("list", {}); }
        function task(action: string, payload: string): bool {
            try { return tasks.run(action, JSON.parse(payload)); }
            catch (error) { return false; }
        }
        function status(): string {
            return JSON.stringify({tasks: tasks.tasks.length, completed: tasks.completedCount, busy: tasks.busy, error: tasks.errorMessage, accent: theme.accent.toString(), screen: root.widgetScreen.name});
        }
    }
}
