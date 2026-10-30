import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: theme
    property color background: "#18252a"
    property color foreground: "#e5eee9"
    property color muted: "#b3c9c3"
    property color accent: "#a9cede"
    readonly property color panel: Qt.rgba(background.r, background.g, background.b, 0.74)
    readonly property color border: Qt.rgba(accent.r, accent.g, accent.b, 0.24)
    readonly property color field: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.07)

    function loadPalette() {
        try {
            const data = JSON.parse(palette.text());
            const names = {background: "windowBackground", foreground: "primaryText", muted: "secondaryText", accent: "accentPrimary"};
            const next = {};
            for (const key in names) {
                const raw = data[names[key]];
                if (typeof raw !== "string") return;
                const value = "#" + raw.replace(/^#+/, "");
                if (!/^#[0-9a-fA-F]{6}$/.test(value)) return;
                next[key] = value;
            }
            for (const key in next) theme[key] = next[key];
        } catch (error) { /* Keep the last palette while Wallust rewrites the file. */ }
    }

    property FileView palette: FileView {
        path: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/quickshell/qml_color.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: theme.loadPalette()
    }
}
