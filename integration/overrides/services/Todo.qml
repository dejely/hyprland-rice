pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
Singleton {
    id: root
    property var list: []
    property var deleted: null
    property string error: ""
    property bool busy: false
    property string pending: ""
    function transact(action, payload) {
        if (busy) return false;
        busy = true;
        pending = action;
        worker.command = ["python3", Quickshell.shellPath("integration/tasks.py"), action, payload];
        worker.running = true;
        return true;
    }
    function run(action, payload) { return transact(action, JSON.stringify(payload || {})); }
    function addTask(text) { return run("add", {text: text}); }
    function markDone(index) { if (list[index] && !list[index].done) return run("toggle", {id: list[index].id}); return false; }
    function markUnfinished(index) { if (list[index] && list[index].done) return run("toggle", {id: list[index].id}); return false; }
    function deleteItem(index) { return list[index] ? run("delete", {id: list[index].id}) : false; }
    function edit(id, text) { return run("edit", {id: id, text: text}); }
    function undo() { return deleted ? run("restore", deleted) : false; }
    function refresh() { return run("list", {}); }
    Component.onCompleted: refresh()
    Process {
        id: worker
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const result = JSON.parse(text);
                    if (!result.ok) { root.error = result.error; return; }
                    root.list = result.tasks.map(t => Object.assign({}, t, {content: t.text}));
                    root.error = "";
                    if (root.pending === "delete") root.deleted = result.deleted;
                    if (root.pending === "restore") root.deleted = null;
                } catch (e) { root.error = "Could not read tasks. The saved file is preserved."; }
            }
        }
        onExited: (code, status) => {
            if (code !== 0 && !root.error) root.error = "Task operation failed. Retry to reload.";
            root.busy = false;
        }
    }
    Timer { interval: 3000; running: true; repeat: true; onTriggered: { if (!root.busy) root.refresh(); } }
}
