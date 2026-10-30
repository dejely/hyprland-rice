import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs
import qs.services
import qs.modules.common
import qs.modules.common.widgets
import qs.modules.ii.background.widgets

AbstractBackgroundWidget {
    id: root
    objectName: "rice-tasks"
    configEntryName: "todo"
    hoverEnabled: true
    implicitWidth: 360
    implicitHeight: 460
    property string editingId: ""
    WidgetCard {
        anchors.fill: parent
        widget: root
        ColumnLayout {
            anchors { fill: parent; margins: 16 }
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                StyledText { text: "Tasks"; font.pixelSize: 22; Layout.fillWidth: true }
                Button { objectName: "undo-delete"; text: "Undo"; enabled: !!Todo.deleted && !Todo.busy; onClicked: Todo.undo() }
            }
            StyledText {
                Layout.fillWidth: true
                visible: Todo.error.length > 0
                text: Todo.error
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: Appearance.colors.colError
            }
            Button { text: "Retry"; visible: Todo.error.length > 0; enabled: !Todo.busy; onClicked: Todo.refresh() }
            TextField {
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
                        CheckBox {
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
                        TextField {
                            id: editField
                            objectName: "edit-field-" + row.modelData.id
                            Layout.fillWidth: true
                            visible: root.editingId === row.modelData.id
                            text: row.modelData.text
                            onActiveFocusChanged: GlobalStates.desktopWidgetKeyboardFocus = activeFocus
                            onAccepted: { if (Todo.edit(row.modelData.id, text)) root.editingId = ""; }
                            Keys.onEscapePressed: root.editingId = ""
                        }
                        Button {
                            objectName: "edit-" + row.modelData.id
                            text: "✎"
                            implicitWidth: 32
                            enabled: !Todo.busy
                            onClicked: { root.editingId = row.modelData.id; editField.forceActiveFocus(); }
                        }
                        Button {
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
    }
}
