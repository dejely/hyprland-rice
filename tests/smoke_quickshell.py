#!/usr/bin/env python3
"""Run real QML with isolated data and Qt events on a temporary headless output."""
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
HARNESS = '''
    TestEvent { id: events }
    function findTestItem(item, name) {
            if (item.objectName === name) return item;
            const children = item.children || [];
            for (const child of children) {
                const found = root.findTestItem(child, name);
                if (found) return found;
            }
            return null;
    }
    IpcHandler {
        target: "test"
        function reveal(name: string): bool {
            const item = root.findTestItem(tasks.contentItem, name);
            const scroll = root.findTestItem(tasks.contentItem, "task-scroll");
            if (!item || !scroll) return false;
            let parent = item.parent;
            while (parent && parent !== scroll.contentItem) parent = parent.parent;
            if (parent) {
                const position = item.mapToItem(scroll.contentItem, 0, 0);
                scroll.contentItem.contentY = Math.max(0, Math.min(scroll.contentItem.contentHeight - scroll.height,
                    scroll.contentItem.contentY + position.y - scroll.height / 2));
            }
            return true;
        }
        function click(name: string): bool {
            const item = root.findTestItem(tasks.contentItem, name);
            if (!item || !item.visible || !item.enabled) return false;
            return events.mouseClick(item, item.width / 2, item.height / 2, Qt.LeftButton, Qt.NoModifier, 0);
        }
        function enter(name: string, value: string): bool {
            const item = root.findTestItem(tasks.contentItem, name);
            if (!item || !item.visible || !item.enabled) return false;
            item.text = value;
            item.accepted();
            return true;
        }
    }
'''


def run_smoke(output):
    with tempfile.TemporaryDirectory(prefix='rice-qml-smoke-') as td:
        root = Path(td)
        config = root / 'shell'
        shutil.copytree(REPO / 'quickshell/rice-desktop', config)
        shell = config / 'shell.qml'
        source = shell.read_text().replace('import QtQuick\n', 'import QtQuick\nimport QtTest\n', 1)
        source = re.sub(r'readonly property var widgetScreen:.*',
                        'readonly property var widgetScreen: Quickshell.screens.find(s => s.name === '
                        + json.dumps(output) + ')', source)
        shell.write_text(source[:source.rfind('}')] + HARNESS + '\n}\n')
        palette = root / 'config/quickshell/qml_color.json'
        palette.parent.mkdir(parents=True)
        colors = dict(windowBackground='#18252a', primaryText='#e5eee9', secondaryText='#b3c9c3', accentPrimary='##aabbcc')
        palette.write_text(json.dumps(colors))
        env = dict(os.environ, QT_QPA_PLATFORM='wayland',
                   XDG_CONFIG_HOME=str(root / 'config'), XDG_DATA_HOME=str(root / 'data'))
        log = (root / 'qs.log').open('w+')
        process = subprocess.Popen(['qs', '-p', str(config)], env=env, stdout=log, stderr=log)

        def ipc(target, method, *args):
            return subprocess.check_output(['qs', 'ipc', '-p', str(config), '--any-display', 'call', target, method, *args],
                                           env=env, text=True, stderr=subprocess.DEVNULL).strip()

        def status():
            return json.loads(ipc('desktop', 'status'))

        def wait(predicate, label):
            for _ in range(80):
                time.sleep(0.05)
                try:
                    state = status()
                    if not state['busy'] and predicate(state):
                        return state
                except (subprocess.CalledProcessError, ValueError):
                    pass
            log.flush()
            raise AssertionError(label + '\n' + (root / 'qs.log').read_text())

        def ui(method, *args):
            time.sleep(0.15)  # Let repeater creation and layout finish before targeting a control.
            if method == 'click':
                assert ipc('test', 'reveal', args[0]) == 'true'
                time.sleep(0.1)
            assert ipc('test', method, *args) == 'true', (method, args)
            time.sleep(0.15)

        tasks_file = root / 'data/hyprland-rice/tasks.json'
        try:
            wait(lambda s: s['accent'] == '#aabbcc', 'initial palette and startup')
            ui('enter', 'new-task', 'banana QML test 🍌 <b>literal</b>')
            wait(lambda s: s['tasks'] == 1, 'add via input handler')
            task_id = json.loads(tasks_file.read_text())['tasks'][0]['id']
            ui('click', 'edit-' + task_id)
            ui('enter', 'edit-field-' + task_id, 'Edited task')
            wait(lambda s: s['tasks'] == 1, 'edit')
            assert json.loads(tasks_file.read_text())['tasks'][0]['text'] == 'Edited task'
            ui('click', 'toggle-' + task_id)
            wait(lambda s: s['completed'] == 1, 'complete')
            ui('click', 'completed-toggle')
            ui('click', 'toggle-' + task_id)
            wait(lambda s: s['completed'] == 0, 'uncomplete')
            ui('click', 'delete-' + task_id)
            wait(lambda s: s['tasks'] == 0, 'delete')
            ui('click', 'undo-delete')
            wait(lambda s: s['tasks'] == 1, 'undo')
            assert json.loads(tasks_file.read_text())['tasks'][0]['id'] == task_id
            print('PASS: real QML add, edit, check/uncheck, completed section, delete, and undo.')

            for i in range(24):
                assert ipc('desktop', 'task', 'add', json.dumps({'text': f'Long list task {i}'})) == 'true'
                wait(lambda s: s['tasks'] == i + 2, 'long list')
            last_id = json.loads(tasks_file.read_text())['tasks'][-1]['id']
            ui('click', 'toggle-' + last_id)
            wait(lambda s: s['completed'] == 1, 'scroll to last task and complete it')
            ui('click', 'toggle-' + last_id)
            wait(lambda s: s['completed'] == 0, 'scroll to completed task and restore it')
            print('PASS: 25 tasks load; scrolling reaches and operates the last task.')
            colors['accentPrimary'] = '##778899'
            palette.write_text(json.dumps(colors))
            wait(lambda s: s['accent'] == '#778899', 'palette update')
            palette.write_text('{partial')
            time.sleep(0.2)
            assert status()['accent'] == '#778899'
            colors['accentPrimary'] = '#99aabb'
            palette.write_text(json.dumps(colors))
            wait(lambda s: s['accent'] == '#99aabb', 'palette recovery')
            print('PASS: palette updates, double-hash normalization, and partial-file recovery.')

            process.terminate()
            process.wait(timeout=5)
            process = subprocess.Popen(['qs', '-p', str(config)], env=env, stdout=log, stderr=log)
            wait(lambda s: s['tasks'] == 25, 'restart persistence')
            tasks_file.write_text('{broken')
            ipc('desktop', 'refreshTasks')
            wait(lambda s: bool(s['error']), 'corrupt-file UI error')
            assert tasks_file.read_text() == '{broken'
            print('PASS: widget restart persistence and corrupt-file UI error without overwrite.')
        except Exception:
            subprocess.run(['grim', '-o', output, '/tmp/hyprland-rice-smoke-failed.png'], check=False)
            raise
        finally:
            process.terminate()
            process.wait(timeout=5)
            log.close()


def main():
    def monitors():
        return {m['name'] for m in json.loads(subprocess.check_output(['hyprctl', 'monitors', '-j'], text=True))}
    before = monitors()
    subprocess.run(['hyprctl', 'output', 'create', 'headless'], check=True, stdout=subprocess.DEVNULL)
    created = set()
    try:
        for _ in range(40):
            created = monitors() - before
            if created:
                break
            time.sleep(0.05)
        assert len(created) == 1, created
        run_smoke(next(iter(created)))
    finally:
        for output in created:
            subprocess.run(['hyprctl', 'output', 'remove', output], check=True, stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
