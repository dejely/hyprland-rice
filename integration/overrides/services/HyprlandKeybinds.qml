pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
Singleton {
    id: root
    property var keybinds: ({children: []})
    function refresh() { reader.running = true; }
    Component.onCompleted: refresh()
    Connections { target: Hyprland; function onRawEvent(event) { if (event.name === "configreloaded") root.refresh(); } }
    Process {
        id: reader
        command: ["/usr/bin/python3", Quickshell.shellPath("integration/shortcuts.py")]
        stdout: StdioCollector { onStreamFinished: { try { root.keybinds = JSON.parse(text); } catch (e) { console.warn("Cannot read effective keybindings"); } } }
    }
}
