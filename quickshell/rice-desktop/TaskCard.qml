pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

PanelWindow {
    id: panel
    required property var theme
    property var tasks: []
    property var deleted: null
    property string errorMessage: ""
    property string pendingAction: ""
    property string editingId: ""
    property bool showCompleted: false
    property bool busy: false
    readonly property int completedCount: tasks.filter(t => t.done).length
    readonly property var activeTasks: tasks.filter(t => !t.done)
    readonly property var completedTasks: tasks.filter(t => t.done)

    anchors { top: true; left: true }
    margins { left: Math.round(screen.width * 0.035); top: Math.round(screen.height * 0.15) }
    implicitWidth: Math.min(360, screen.width * 0.30)
    implicitHeight: Math.min(650, screen.height * 0.68)
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Bottom
    WlrLayershell.namespace: "rice-desktop-tasks"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand

    function run(action, payload) {
        if (busy) return false;
        busy = true;
        pendingAction = action;
        worker.command = ["python3", Quickshell.shellPath("tasks.py"), action, JSON.stringify(payload || {})];
        worker.running = true;
        return true;
    }

    Component.onCompleted: run("list", {})
    Process {
        id: worker
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const response = JSON.parse(text);
                    if (!response.ok) {
                        panel.errorMessage = response.error;
                        return;
                    }
                    panel.tasks = response.tasks;
                    panel.errorMessage = "";
                    if (panel.pendingAction === "add") newTask.clear();
                    if (panel.pendingAction === "edit") panel.editingId = "";
                    if (panel.pendingAction === "delete") panel.deleted = response.deleted;
                    if (panel.pendingAction === "restore") panel.deleted = null;
                } catch (error) {
                    panel.errorMessage = "Could not load tasks. Your saved file has been preserved.";
                }
            }
        }
        onExited: { panel.busy = false; }
    }

    component SmallButton: Button {
        id: button
        property string accessibleLabel: text
        Accessible.name: accessibleLabel
        implicitWidth: 34
        implicitHeight: 34
        hoverEnabled: true
        background: Rectangle {
            radius: 9
            color: button.hovered ? panel.theme.field : "transparent"
        }
        contentItem: Text {
            text: button.text
            color: panel.theme.accent
            font.pixelSize: 17
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        ToolTip.visible: hovered
        ToolTip.text: accessibleLabel
    }

    component TaskRow: ColumnLayout {
        id: row
        required property var task
        Layout.fillWidth: true
        spacing: 6
        RowLayout {
            Layout.fillWidth: true
            spacing: 9
            SmallButton {
                objectName: "toggle-" + row.task.id
                text: row.task.done ? "✓" : "○"
                accessibleLabel: row.task.done ? "Mark unfinished" : "Complete task"
                enabled: !panel.busy
                onClicked: panel.run("toggle", {id: row.task.id})
            }
            Text {
                visible: panel.editingId !== row.task.id
                Layout.fillWidth: true
                text: row.task.text
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: row.task.done ? panel.theme.muted : panel.theme.foreground
                opacity: row.task.done ? 0.65 : 1
                font { family: "Noto Sans"; pixelSize: 14; strikeout: row.task.done }
                MouseArea {
                    anchors.fill: parent
                    onDoubleClicked: { panel.editingId = row.task.id; editTask.text = row.task.text; editTask.forceActiveFocus(); }
                }
            }
            TextField {
                id: editTask
                objectName: "edit-field-" + row.task.id
                visible: panel.editingId === row.task.id
                Layout.fillWidth: true
                color: panel.theme.foreground
                selectionColor: panel.theme.accent
                font.pixelSize: 14
                background: Rectangle { radius: 8; color: panel.theme.field }
                enabled: !panel.busy
                onAccepted: panel.run("edit", {id: row.task.id, text: text})
                Keys.onEscapePressed: panel.editingId = ""
            }
            SmallButton {
                objectName: "edit-" + row.task.id
                text: panel.editingId === row.task.id ? "✓" : "✎"
                accessibleLabel: panel.editingId === row.task.id ? "Save task" : "Edit task"
                enabled: !panel.busy
                onClicked: {
                    if (panel.editingId === row.task.id) panel.run("edit", {id: row.task.id, text: editTask.text});
                    else { panel.editingId = row.task.id; editTask.text = row.task.text; editTask.forceActiveFocus(); }
                }
            }
            SmallButton {
                objectName: "delete-" + row.task.id
                text: "×"
                accessibleLabel: "Delete task"
                enabled: !panel.busy
                onClicked: panel.run("delete", {id: row.task.id})
            }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: panel.theme.border; opacity: 0.4 }
    }

    Rectangle {
        anchors.fill: parent
        radius: 20
        color: panel.theme.panel
        border { color: panel.theme.border; width: 1 }
        ColumnLayout {
            anchors { fill: parent; margins: 23 }
            spacing: 16
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 4
                    Text { text: "MAKE ROOM FOR"; color: panel.theme.muted; font { family: "Noto Sans"; pixelSize: 10; letterSpacing: 2 } }
                    Text { text: "What matters."; color: panel.theme.foreground; font { family: "Noto Sans"; pixelSize: 26; weight: Font.DemiBold } }
                }
                Item { Layout.fillWidth: true }
                Text { text: "✦"; color: panel.theme.accent; font.pixelSize: 26 }
            }
            Text {
                text: panel.tasks.length ? panel.completedCount + " of " + panel.tasks.length + " complete" : "A little progress, every day."
                color: panel.theme.muted
                font.pixelSize: 12
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 44
                radius: 11
                color: panel.theme.field
                border.color: newTask.activeFocus ? panel.theme.accent : panel.theme.border
                RowLayout {
                    anchors { fill: parent; leftMargin: 12; rightMargin: 5 }
                    TextField {
                        id: newTask
                        objectName: "new-task"
                        Layout.fillWidth: true
                        placeholderText: "Add a task…"
                        placeholderTextColor: panel.theme.muted
                        color: panel.theme.foreground
                        selectionColor: panel.theme.accent
                        font { family: "Noto Sans"; pixelSize: 13 }
                        background: Item {}
                        enabled: !panel.busy
                        onAccepted: { if (text.trim()) panel.run("add", {text: text}); }
                        Keys.onEscapePressed: focus = false
                    }
                    SmallButton {
                        objectName: "add-task"
                        text: "+"
                        accessibleLabel: "Add task"
                        enabled: !panel.busy && newTask.text.trim().length > 0
                        onClicked: panel.run("add", {text: newTask.text})
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                visible: panel.errorMessage.length > 0
                text: panel.errorMessage
                textFormat: Text.PlainText
                color: panel.theme.foreground
                wrapMode: Text.Wrap
                font.pixelSize: 12
            }
            SmallButton {
                visible: panel.errorMessage.length > 0
                text: "↻"
                accessibleLabel: "Retry loading tasks"
                enabled: !panel.busy
                onClicked: panel.run("list", {})
            }
            ScrollView {
                id: taskScroll
                objectName: "task-scroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: availableWidth
                contentHeight: taskList.implicitHeight
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ColumnLayout {
                    id: taskList
                    width: taskScroll.availableWidth
                    height: implicitHeight
                    spacing: 12
                    Text {
                        visible: panel.activeTasks.length === 0
                        Layout.fillWidth: true
                        Layout.topMargin: 22
                        text: panel.tasks.length ? "All caught up. Take a breath." : "Your next small step starts here."
                        wrapMode: Text.Wrap
                        color: panel.theme.muted
                        font.pixelSize: 13
                    }
                    Repeater { model: panel.activeTasks; TaskRow { required property var modelData; task: modelData } }
                    Button {
                        id: completedButton
                        objectName: "completed-toggle"
                        visible: panel.completedCount > 0
                        Layout.fillWidth: true
                        text: (panel.showCompleted ? "▾  " : "▸  ") + "Completed · " + panel.completedCount
                        onClicked: panel.showCompleted = !panel.showCompleted
                        contentItem: Text { text: completedButton.text; color: panel.theme.muted; font.pixelSize: 12 }
                        background: Item {}
                    }
                    Repeater { model: panel.showCompleted ? panel.completedTasks : []; TaskRow { required property var modelData; task: modelData } }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                visible: panel.deleted !== null
                Text { Layout.fillWidth: true; text: "Task removed"; color: panel.theme.muted; font.pixelSize: 12 }
                Button {
                    id: undoButton
                    objectName: "undo-delete"
                    text: "Undo"
                    enabled: !panel.busy
                    onClicked: panel.run("restore", panel.deleted)
                    contentItem: Text { text: undoButton.text; color: panel.theme.accent; font.pixelSize: 12 }
                    background: Item {}
                }
            }
            Text { text: "LOCAL TASKS  /  JUST FOR YOU"; color: panel.theme.muted; opacity: 0.6; font { pixelSize: 9; letterSpacing: 1.4 } }
        }
    }
}
