import QtQuick
import QtQuick.Controls
import QtQuick.Controls as QQC
import QtQuick.Layouts
import qs
import qs.services
import qs.modules.common
import qs.modules.common.widgets
import qs.modules.common.widgets.widgetCanvas
import qs.modules.ii.background.widgets

AbstractBackgroundWidget {
    id: root
    objectName: "rice-tasks"
    configEntryName: "todo"
    hoverEnabled: true
    implicitWidth: configEntry.width
    implicitHeight: configEntry.height
    property string editingId: ""
    component TaskButton: QQC.Button {
        id: button
        implicitHeight: 34
        implicitWidth: 54
        contentItem: StyledText { text: button.text; horizontalAlignment: Text.AlignHCenter; opacity: button.enabled ? 1 : 0.4 }
        background: Rectangle { radius: 10; color: button.hovered ? Appearance.colors.colLayer2 : Appearance.colors.colLayer1; border.width: 1; border.color: Appearance.colors.colLayer0Border }
    }
    component TaskCheck: QQC.CheckBox {
        id: check
        implicitWidth: 28
        implicitHeight: 34
        indicator: Rectangle {
            width: 22; height: 22
            anchors.centerIn: parent
            radius: 11
            color: check.checked ? Appearance.colors.colPrimary : "transparent"
            border.width: 1
            border.color: Appearance.colors.colPrimary
            StyledText { anchors.centerIn: parent; text: check.checked ? "✓" : ""; color: Appearance.colors.colOnPrimary }
        }
    }
    component TaskField: QQC.TextField {
        color: Appearance.colors.colOnLayer0
        placeholderTextColor: Appearance.colors.colSubtext
        selectionColor: Appearance.colors.colPrimary
        selectedTextColor: Appearance.colors.colOnPrimary
        font.family: Appearance.font.family.main
        font.pixelSize: 14
        implicitHeight: 38
        padding: 10
        background: Rectangle { radius: 10; color: Appearance.colors.colLayer2; border.width: 1; border.color: Appearance.colors.colLayer0Border }
    }
    WidgetCard {
        id: card
        anchors.fill: parent
        widget: root
        ColumnLayout {
            anchors { fill: parent; margins: 16 }
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                StyledText { text: "Tasks"; font.pixelSize: 22; Layout.fillWidth: true }
                TaskButton { objectName: "undo-delete"; text: "Undo"; enabled: !!Todo.deleted && !Todo.busy; onClicked: Todo.undo() }
            }
            StyledText {
                Layout.fillWidth: true
                visible: Todo.error.length > 0
                text: Todo.error
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: Appearance.colors.colError
            }
            TaskButton { text: "Retry"; visible: Todo.error.length > 0; enabled: !Todo.busy; onClicked: Todo.refresh() }
            TaskField {
                id: newTask
                objectName: "new-task"
                Layout.fillWidth: true
                placeholderText: "Add a task…"
                enabled: !Todo.busy
                onActiveFocusChanged: GlobalStates.desktopWidgetKeyboardFocus = activeFocus
                onAccepted: { if (Todo.addTask(text)) clear(); }
            }
            StyledText { text: "No tasks yet"; visible: Todo.list.length === 0 && !Todo.error }
            ListView {
                id: taskList
                objectName: "task-scroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 6
                model: Todo.list
                ScrollBar.vertical: ScrollBar {}
                delegate: ColumnLayout {
                    id: row
                    required property var modelData
                    required property int index
                    width: taskList.width
                    RowLayout {
                        Layout.fillWidth: true
                        TaskCheck {
                            objectName: "toggle-" + row.modelData.id
                            checked: row.modelData.done
                            enabled: !Todo.busy
                            onClicked: Todo.run("toggle", {id: row.modelData.id})
                        }
                        StyledText {
                            Layout.fillWidth: true
                            visible: root.editingId !== row.modelData.id
                            text: row.modelData.text
                            textFormat: Text.PlainText
                            font.strikeout: row.modelData.done
                            wrapMode: Text.Wrap
                        }
                        TaskField {
                            id: editField
                            objectName: "edit-field-" + row.modelData.id
                            Layout.fillWidth: true
                            visible: root.editingId === row.modelData.id
                            text: row.modelData.text
                            onActiveFocusChanged: GlobalStates.desktopWidgetKeyboardFocus = activeFocus
                            onAccepted: { if (Todo.edit(row.modelData.id, text)) root.editingId = ""; }
                            Keys.onEscapePressed: root.editingId = ""
                        }
                        TaskButton {
                            objectName: "edit-" + row.modelData.id
                            text: "✎"
                            implicitWidth: 32
                            enabled: !Todo.busy
                            onClicked: { root.editingId = row.modelData.id; editField.forceActiveFocus(); }
                        }
                        TaskButton {
                            objectName: "delete-" + row.modelData.id
                            text: "×"
                            implicitWidth: 32
                            enabled: !Todo.busy
                            onClicked: Todo.run("delete", {id: row.modelData.id})
                        }
                    }
                }
            }
        }
        ResizeHandler {
            anchorItem: card
            hoverActive: root.containsMouse
            locked: Config.options.background.widgetsLocked
            currentWidth: root.width
            resizeMode: "diagonal"
            onResizedXY: (dx, dy, startWidth) => {
                root.configEntry.width = Math.max(320, Math.min(root.scaledScreenWidth, startWidth + dx));
                root.configEntry.height = Math.max(260, Math.min(root.scaledScreenHeight - root.y, 460 + dy));
            }
        }
    }
}
