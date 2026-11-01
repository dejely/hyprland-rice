//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.services
import qs.modules.common
import qs.modules.ii.overview
import qs.modules.ii.settings
import qs.modules.ii.wallpaperSelector
import qs.modules.ii.sidebarRight
import qs.modules.ii.mediaControls
import qs.modules.ii.desktopMenu

ShellRoot {
    id: root
    property bool started: false
    function closeAll(keepOverview) {
        if (!keepOverview) GlobalStates.overviewOpen = false;
        GlobalStates.settingsOpen = false;
        GlobalStates.wallpaperSelectorOpen = false;
        GlobalStates.sidebarRightOpen = false;
        GlobalStates.mediaControlsOpen = false;
        GlobalStates.desktopMenuOpen = false;
    }
    function open(action, payload) {
        if (action === "task-state") {
            const state = JSON.parse(payload);
            Todo.parentBusy = state.busy;
            Todo.deleted = state.undo ? ({available:true}) : null;
            Todo.error = state.error;
            return;
        }
        if (action === "notification-state") {
            const state = JSON.parse(payload);
            Notifications.syncingToolState = true;
            Notifications.silent = state.silent;
            Notifications.unread = state.unread;
            Notifications.syncingToolState = false;
            return;
        }
        queryTimer.stop();
        const previous = {overview: GlobalStates.overviewOpen, settings: GlobalStates.settingsOpen, wallpaper: GlobalStates.wallpaperSelectorOpen, notifications: GlobalStates.sidebarRightOpen, media: GlobalStates.mediaControlsOpen, query: LauncherSearch.query};
        if (action === "close") { root.closeAll(); return; }
        if (action === "settings-target") {
            root.closeAll();
            const target = JSON.parse(payload);
            GlobalStates.openSettingsAt(target.page, target.label || "", target.section || "", target.subsection || "");
            return;
        }
        const searchRequest = ["launcher", "overview", "clipboard", "emoji"].some(prefix => action.startsWith(prefix)) || action === "help" || action === "symbols";
        root.closeAll(searchRequest && previous.overview);
        if (action === "desktop-menu") {
            const point = JSON.parse(payload || "{}");
            GlobalStates.desktopMenuScreen = Quickshell.screens.find(s => s.name === (Quickshell.env("RICE_TEST_OUTPUT") || point.screen)) || Quickshell.screens[0];
            GlobalStates.desktopMenuX = point.x ?? GlobalStates.desktopMenuScreen.width / 2;
            GlobalStates.desktopMenuY = point.y ?? GlobalStates.desktopMenuScreen.height / 2;
            GlobalStates.desktopMenuOpen = true;
            return;
        }
        if (action.startsWith("launcher") || action.startsWith("overview")) {
            GlobalStates.overviewOpen = !action.endsWith("toggle") || !previous.overview;
            if (GlobalStates.overviewOpen) overview.setQuery("");
        }
        else if (action.startsWith("clipboard") || action.startsWith("emoji") || action === "help" || action === "symbols") {
            const prefix = action.startsWith("clipboard") ? Config.options.search.prefix.clipboard : Config.options.search.prefix.emojis;
            if (action.endsWith("toggle") && previous.overview && previous.query.startsWith(prefix)) return;
            GlobalStates.overviewOpen = true;
            queryTimer.query = action === "help" ? "<" : action === "symbols" ? Config.options.search.prefix.symbols : action.startsWith("emoji") ? Config.options.search.prefix.emojis : Config.options.search.prefix.clipboard;
            queryTimer.restart();
        } else if (action.startsWith("settings")) GlobalStates.settingsOpen = !action.endsWith("toggle") || !previous.settings;
        else if (action.startsWith("wallpaper")) GlobalStates.wallpaperSelectorOpen = !action.endsWith("toggle") || !previous.wallpaper;
        else if (action.startsWith("notifications")) { GlobalStates.sidebarRightOpen = !action.endsWith("toggle") || !previous.notifications; Notifications.markAllRead(); }
        else if (action.startsWith("media")) GlobalStates.mediaControlsOpen = !action.endsWith("toggle") || !previous.media;
    }
    Timer { id: queryTimer; property string query: ""; interval: 80; onTriggered: overview.setQuery(query) }
    Timer { id: startup; interval: 80; onTriggered: { root.started = true; GlobalStates.dashboardPage = Number(Quickshell.env("RICE_TOOL_PAGE") || "0"); GlobalStates.dashboardGroup = Quickshell.env("RICE_TOOL_GROUP") || ""; root.open(Quickshell.env("RICE_TOOL_ACTION"), Quickshell.env("RICE_TOOL_PAYLOAD") || ""); stateDelay.restart(); } }
    function begin() { if (Config.ready && !root.started && !startup.running) { MaterialThemeLoader.reapplyTheme(); startup.start(); } }
    Component.onCompleted: begin()
    Connections { target: Config; function onReadyChanged() { root.begin(); } }
    Overview { id: overview }
    Settings {}
    WallpaperSelector { id: wallpaperSelector }
    SidebarRight {}
    MediaControls {}
    DesktopMenu { id: desktopMenu }
    FileView { id: stateFile; path: Quickshell.env("RICE_TOOL_STATUS"); printErrors: false }
    Timer {
        id: stateDelay
        interval: 20
        onTriggered: stateFile.setText(JSON.stringify({started: root.started, open: GlobalStates.overviewOpen || GlobalStates.settingsOpen || GlobalStates.wallpaperSelectorOpen || GlobalStates.sidebarRightOpen || GlobalStates.mediaControlsOpen || GlobalStates.desktopMenuOpen || wallpaperSelector.reallyOpen, desktopMenu: GlobalStates.desktopMenuOpen, overview: GlobalStates.overviewOpen, settings: GlobalStates.settingsOpen, wallpaper: GlobalStates.wallpaperSelectorOpen, notifications: GlobalStates.sidebarRightOpen, media: GlobalStates.mediaControlsOpen, dashboardPage: GlobalStates.dashboardPage, dashboardGroup: GlobalStates.dashboardGroup, directory: Wallpapers.effectiveDirectory, preview: Wallpapers.previewPath, confirmed: Wallpapers.confirmedPath}))
    }
    Connections {
        target: GlobalStates
        function onOverviewOpenChanged() { stateDelay.restart(); }
        function onSettingsOpenChanged() { stateDelay.restart(); }
        function onWallpaperSelectorOpenChanged() { stateDelay.restart(); }
        function onSidebarRightOpenChanged() { stateDelay.restart(); }
        function onMediaControlsOpenChanged() { stateDelay.restart(); }
        function onDesktopMenuOpenChanged() { stateDelay.restart(); }
        function onDashboardPageChanged() { stateDelay.restart(); }
        function onDashboardGroupChanged() { stateDelay.restart(); }
    }
    Connections { target: wallpaperSelector; function onReallyOpenChanged() { stateDelay.restart(); } }
    Connections { target: Wallpapers; function onEffectiveDirectoryChanged() { stateDelay.restart(); } function onPreviewPathChanged() { stateDelay.restart(); } function onConfirmedPathChanged() { stateDelay.restart(); } }
    IpcHandler { target: "tool"; function open(action: string, payload: string): void { root.open(action, payload); } }
}
