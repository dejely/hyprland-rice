import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.services
import qs.modules.common

Scope {
    id: root
    property bool syncing: false
    property int nextRequest: 0
    property var unacknowledged: []
    readonly property string host: Quickshell.shellPath("tool-host.qml")
    function request(action, payload) {
        payload = payload || "";
        if (worker.running) {
            const request = {id: ++root.nextRequest, action: action, payload: payload};
            root.unacknowledged = root.unacknowledged.concat([request]);
            worker.write(JSON.stringify(request) + "\n");
        }
        else {
            if (action === "close") return;
            worker.command = [Quickshell.shellPath("integration/rice-core"), "tool", root.host, action, payload];
            worker.running = true;
        }
    }
    function applyState(state) {
        root.syncing = true;
        GlobalStates.overviewOpen = state.overview || false;
        GlobalStates.settingsOpen = state.settings || false;
        GlobalStates.wallpaperSelectorOpen = state.wallpaper || false;
        GlobalStates.sidebarRightOpen = state.notifications || false;
        GlobalStates.mediaControlsOpen = state.media || false;
        GlobalStates.desktopMenuOpen = state.desktopMenu || false;
        if (state.dashboardPage !== undefined) GlobalStates.dashboardPage = state.dashboardPage;
        if (state.dashboardGroup !== undefined) GlobalStates.dashboardGroup = state.dashboardGroup;
        if (state.directory && state.directory !== Wallpapers.effectiveDirectory) Wallpapers.setDirectory(state.directory);
        Wallpapers.previewPath = state.preview || "";
        if (state.confirmed) Wallpapers.confirmedPath = state.confirmed;
        root.syncing = false;
    }
    function receive(line) {
        try {
            const event = JSON.parse(line);
            if (event.event === "ack") root.unacknowledged = root.unacknowledged.filter(request => request.id !== event.id);
            else if (event.event === "state") root.applyState(event.state);
            else if (event.event === "closed") root.applyState({});
            else if (event.event === "patch") {
                for (const change of event.changes) Config.setNestedValue(change.path.join("."), change.value);
            }
        } catch (error) { console.warn("Cannot apply transient tool update"); }
    }
    Process {
        id: worker
        stdinEnabled: true
        environment: ({ RICE_TOOL_SILENT: Notifications.silent ? "1" : "0", RICE_TOOL_UNREAD: String(Notifications.unread), RICE_TOOL_PAGE: String(GlobalStates.dashboardPage), RICE_TOOL_GROUP: GlobalStates.dashboardGroup, RICE_TOOL_UNDO: Todo.deleted ? "1" : "0" })
        stdout: SplitParser { onRead: line => root.receive(line) }
        onExited: (code, status) => {
            root.applyState({});
            Qt.callLater(() => {
                const pending = root.unacknowledged.filter(request => !["close", "task-state", "notification-state"].includes(request.action));
                root.unacknowledged = [];
                if (code === 0 && pending.length) { const latest = pending[pending.length - 1]; root.request(latest.action, latest.payload); }
                else if (code !== 0) console.warn("Transient desktop tool failed; see tools.log");
            });
        }
    }
    Connections {
        target: GlobalStates
        function onOverviewOpenChanged() { if (!root.syncing) root.request(GlobalStates.overviewOpen ? "launcher" : "close"); }
        function onSettingsOpenChanged() { if (!root.syncing) root.request(GlobalStates.settingsOpen ? "settings" : "close"); }
        function onWallpaperSelectorOpenChanged() { if (!root.syncing) root.request(GlobalStates.wallpaperSelectorOpen ? "wallpaper" : "close"); }
        function onSidebarRightOpenChanged() { if (!root.syncing) root.request(GlobalStates.sidebarRightOpen ? "notifications" : "close"); }
        function onMediaControlsOpenChanged() { if (!root.syncing) root.request(GlobalStates.mediaControlsOpen ? "media" : "close"); }
        function onDesktopMenuOpenChanged() {
            if (!root.syncing) root.request(GlobalStates.desktopMenuOpen ? "desktop-menu" : "close", JSON.stringify({x:GlobalStates.desktopMenuX,y:GlobalStates.desktopMenuY,screen:GlobalStates.desktopMenuScreen?.name || ""}));
        }
        function onSettingsTargetChanged() { if (!root.syncing && GlobalStates.settingsTarget) root.request("settings-target", JSON.stringify(GlobalStates.settingsTarget)); }
    }
    Connections {
        target: Notifications
        function onSilentChanged() { if (worker.running) root.request("notification-state", JSON.stringify({silent: Notifications.silent, unread: Notifications.unread})); }
        function onUnreadChanged() { if (worker.running) root.request("notification-state", JSON.stringify({silent: Notifications.silent, unread: Notifications.unread})); }
    }
    Connections {
        target: Todo
        function sendTaskState() { if (worker.running) root.request("task-state", JSON.stringify({busy:Todo.busy,error:Todo.error,undo:!!Todo.deleted})); }
        function onBusyChanged() { sendTaskState(); }
        function onErrorChanged() { sendTaskState(); }
        function onDeletedChanged() { sendTaskState(); }
    }
    IpcHandler {
        target: "search"
        function toggle(): void { root.request("launcher-toggle"); }
        function open(): void { root.request("launcher"); }
        function close(): void { root.request("close"); }
        function workspacesToggle(): void { root.request("overview-toggle"); }
        function clipboardToggle(): void { root.request("clipboard-toggle"); }
        function emojiToggle(): void { root.request("emoji-toggle"); }
        function help(): void { root.request("help"); }
    }
    IpcHandler {
        target: "desktopMenu"
        function open(): void { root.request("desktop-menu", "{}"); }
        function close(): void { root.request("close"); }
    }
    IpcHandler {
        target: "settings"
        function toggle(): void { root.request("settings-toggle"); }
        function open(): void { root.request("settings"); }
        function close(): void { root.request("close"); }
    }
    IpcHandler {
        target: "wallpaperSelector"
        function toggle(): void { root.request("wallpaper-toggle"); }
        function close(): void { root.request("close"); }
        function random(): void { Wallpapers.randomFromCurrentFolder(); }
    }
    IpcHandler {
        target: "sidebarRight"
        function toggle(): void { root.request("notifications-toggle"); }
        function open(): void { root.request("notifications"); }
        function close(): void { root.request("close"); }
    }
    IpcHandler {
        target: "mediaControls"
        function toggle(): void { root.request("media-toggle"); }
        function open(): void { root.request("media"); }
        function close(): void { root.request("close"); }
    }
    CompositorGlobalShortcut { name: "searchToggle"; description: "Native desktop tool"; onPressed: root.request("launcher-toggle") }
    CompositorGlobalShortcut {
        name: "searchToggleRelease"
        description: "Toggle search on release"
        onPressed: GlobalStates.superReleaseMightTrigger = true
        onReleased: {
            if (GlobalStates.superReleaseMightTrigger) root.request("launcher-toggle");
            GlobalStates.superReleaseMightTrigger = true;
        }
    }
    CompositorGlobalShortcut { name: "searchToggleReleaseInterrupt"; description: "Cancel search on modifier release"; onPressed: GlobalStates.superReleaseMightTrigger = false }
    CompositorGlobalShortcut { name: "overviewWorkspacesClose"; description: "Native desktop tool"; onPressed: root.request("close") }
    CompositorGlobalShortcut { name: "overviewWorkspacesToggle"; description: "Native desktop tool"; onPressed: root.request("overview-toggle") }
    CompositorGlobalShortcut { name: "overviewClipboardToggle"; description: "Native desktop tool"; onPressed: root.request("clipboard-toggle") }
    CompositorGlobalShortcut { name: "overviewEmojiToggle"; description: "Native desktop tool"; onPressed: root.request("emoji-toggle") }
    CompositorGlobalShortcut { name: "overviewSymbolsToggle"; description: "Native desktop tool"; onPressed: root.request("symbols") }
    CompositorGlobalShortcut { name: "settingsToggle"; description: "Native desktop tool"; onPressed: root.request("settings-toggle") }
    CompositorGlobalShortcut { name: "wallpaperSelectorToggle"; description: "Native desktop tool"; onPressed: root.request("wallpaper-toggle") }
    CompositorGlobalShortcut { name: "mediaControlsToggle"; description: "Native desktop tool"; onPressed: root.request("media-toggle") }
    CompositorGlobalShortcut { name: "mediaControlsOpen"; description: "Native desktop tool"; onPressed: root.request("media") }
    CompositorGlobalShortcut { name: "mediaControlsClose"; description: "Native desktop tool"; onPressed: root.request("close") }
    CompositorGlobalShortcut { name: "sidebarRightToggle"; description: "Native desktop tool"; onPressed: root.request("notifications-toggle") }
    CompositorGlobalShortcut { name: "sidebarRightOpen"; description: "Native desktop tool"; onPressed: root.request("notifications") }
    CompositorGlobalShortcut { name: "sidebarRightClose"; description: "Native desktop tool"; onPressed: root.request("close") }
    CompositorGlobalShortcut { name: "wallpaperSelectorRandom"; description: "Random wallpaper"; onPressed: Wallpapers.randomFromCurrentFolder() }
    IpcHandler {
        target: "toolNotifications"
        function command(action: string, payload: string): void {
            const data = JSON.parse(payload);
            if (action === "discard") Notifications.discardNotifications(data);
            else if (action === "discardAll") Notifications.discardAllNotifications();
            else if (action === "invoke") Notifications.attemptInvokeAction(data.id, data.action);
            else if (action === "cancelTimeout") Notifications.cancelTimeout(data);
            else if (action === "timeout") Notifications.timeoutNotification(data);
            else if (action === "timeoutAll") Notifications.timeoutAll();
            else if (action === "silent") Notifications.silent = data;
            else if (action === "read") Notifications.markAllRead();
        }
    }
}
