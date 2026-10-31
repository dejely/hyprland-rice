#!/usr/bin/env python3
"""Exercise the integrated native shell on a temporary output with isolated data."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integration'))
from build import build
from palette import atomic_json, sync

HARNESS = '''
        TestEvent { id: riceEvents }
        function riceFind(item, name) {
            if (item.objectName === name) return item;
            for (const child of (item.children || [])) {
                const result = riceFind(child, name);
                if (result) return result;
            }
            return null;
        }
        IpcHandler {
            target: "test"
            function enter(name: string, value: string): bool {
                const item = bgRoot.riceFind(widgetCanvas, name);
                if (!item || !item.visible || !item.enabled) return false;
                item.forceActiveFocus(); item.text = value; item.accepted(); return true;
            }
            function click(name: string): bool {
                const item = bgRoot.riceFind(widgetCanvas, name);
                if (!item || !item.visible || !item.enabled) return false;
                return riceEvents.mouseClick(item, item.width/2, item.height/2, Qt.LeftButton, Qt.NoModifier, 0);
            }
            function last(): bool {
                const list = bgRoot.riceFind(widgetCanvas, "task-scroll");
                if (!list) return false;
                list.positionViewAtEnd(); return true;
            }
            function layout(): string {
                const item = bgRoot.riceFind(widgetCanvas, "rice-tasks");
                return JSON.stringify({x:item.x, y:item.y, width:item.width, height:item.height});
            }
            function move(x: int, y: int): void {
                const item = bgRoot.riceFind(widgetCanvas, "rice-tasks");
                item.animateXPos=false; item.animateYPos=false; item.x=x; item.y=y; item.commitPosition();
            }
            function renderStats(): string { return JSON.stringify({shapeSize: centeredWallpaper.centeredShapeRenderSize, centered: centeredWallpaper.centeredWallpaperEnabled}); }
        function centered(enabled: bool): void { Config.options.background.centeredWallpaper = enabled; }
        function resize(width: int, height: int): void {
                Config.options.background.widgets.todo.width=width;
                Config.options.background.widgets.todo.height=height;
            }
            function visibility(enabled: bool): void { Config.options.background.widgets.todo.enable=enabled; }
        }
'''


def run(output):
    with tempfile.TemporaryDirectory(prefix='rice-end4-smoke-') as td:
        root = Path(td)
        runtime = root / 'shell'
        if os.environ.get('RICE_SMOKE_PROFILE') == 'end4-lite':
            subprocess.run([str(ROOT / 'rice-core/target/release/rice-core'), 'build', str(ROOT), str(runtime), 'end4-lite'], check=True, stdout=subprocess.DEVNULL)
        else:
            runtime = build(runtime)
        bg = runtime / 'modules/ii/background/Background.qml'
        source = bg.read_text().replace('import QtQuick\n', 'import QtQuick\nimport QtTest\n', 1)
        bg.write_text(source.replace('        id: bgRoot', '        id: bgRoot\n' + HARNESS, 1))
        dashboard = runtime / 'modules/ii/settings/DashboardSettingsPage.qml'
        source = dashboard.read_text().replace('import QtQuick\n', 'import QtQuick\nimport Quickshell.Io\n', 1)
        source = source.replace('    id: root', '    id: root\n    IpcHandler { target: "dashboard-test"; function cards(): int { return root.layoutResult.count; } }', 1)
        dashboard.write_text(source)
        data = json.loads((ROOT / 'integration/defaults.json').read_text())
        data['background']['wallpaperPath'] = str((Path.home() / '.config/rofi/.current_wallpaper').resolve())
        # Isolate the native file picker from the wallpaper library.
        data['wallpaperSelector'] = {'userPath': str(root)}
        atomic_json(root / 'config/hyprland-rice/end4/config.json', data)
        palette = root / 'config/quickshell/qml_color.json'
        colors = dict(windowBackground='#10151c', primaryText='#eeeeee', secondaryText='#aaaaaa', accentPrimary='##aabbcc')
        atomic_json(palette, colors)
        sync(palette, root / 'state/hyprland-rice/end4/user/generated/colors.json')
        tools = root / 'bin'
        tools.mkdir()
        trace = tools / 'hyprctl'
        trace.write_text('#!/usr/bin/env bash\nif [[ \"${1:-}\" == reload ]]; then ps -p \"$PPID\" -o args= >> \"$RICE_COMMAND_LOG\"; fi\nprintf "%s\\n" "$*" >> "$RICE_COMMAND_LOG"\nexec /usr/bin/hyprctl "$@"\n')
        trace.chmod(0o755)
        deps = Path.home() / '.local/share/hyprland-rice/deps/usr/lib64'
        env = dict(os.environ, PATH=str(tools) + ':' + os.environ['PATH'], RICE_COMMAND_LOG=str(root / 'commands.log'), QT_QPA_PLATFORM='wayland', QML_IMPORT_PATH=str(runtime / 'native') + ':' + str(deps / 'qt6/qml'), LD_LIBRARY_PATH=str(deps),
                   XDG_CONFIG_HOME=str(root / 'config'), XDG_DATA_HOME=str(root / 'data'),
                   XDG_STATE_HOME=str(root / 'state'), XDG_CACHE_HOME=str(root / 'cache'), RICE_TEST_OUTPUT=output)
        if os.environ.get('RICE_SMOKE_PROFILE') == 'end4-lite':
            env.update(dict(line.removeprefix('export ').split('=', 1) for line in (ROOT / 'integration/lite-env.sh').read_text().splitlines() if line.startswith('export ')))
        # Private bus prevents taking the laptop notification service name.
        logfile = (root / 'shell.log').open('w+')
        process = None

        def start():
            return subprocess.Popen(['dbus-run-session', 'qs', '-p', str(runtime)], env=env, stdout=logfile, stderr=logfile)

        def ipc(target, method, *args):
            return subprocess.check_output(['qs', 'ipc', '-p', str(runtime), 'call', target, method, *map(str, args)], env=env, text=True, stderr=subprocess.DEVNULL).strip()

        def wait(predicate, label):
            for _ in range(100):
                time.sleep(0.1)
                try:
                    status = json.loads(ipc('desktop', 'status'))
                    if not status['busy'] and predicate(status): return status
                except (ValueError, subprocess.CalledProcessError): pass
            raise AssertionError(label + '\n' + (root / 'shell.log').read_text(errors='replace')[-16000:])

        def ui(method, *args):
            time.sleep(0.25)
            result = ipc('test', method, *args)
            assert result == 'true', (method, args, ipc('desktop', 'status'))
            time.sleep(0.25)

        def stop():
            if process and process.poll() is None:
                subprocess.run(['qs', '-p', str(runtime), 'kill'], env=env, stdout=subprocess.DEVNULL)
                process.wait(timeout=10)

        tasks = root / 'data/hyprland-rice/tasks.json'
        try:
            process = start()
            wait(lambda s: s['accent'] == '#aabbcc', 'native shell startup')
            time.sleep(4)
            assert '\nreload\n' not in (root / 'commands.log').read_text(), 'Shell reloaded compositor during startup'
            if os.environ.get('RICE_STARTUP_ONLY'):
                print((root / 'commands.log').read_text())
                print(subprocess.check_output(['hyprctl', 'monitors', '-j'], text=True))
                return
            ui('enter', 'new-task', 'banana native task <b>literal</b>')
            wait(lambda s: s['tasks'] == 1, 'task entry')
            task_id = json.loads(tasks.read_text())['tasks'][0]['id']
            ui('click', 'edit-' + task_id)
            ui('enter', 'edit-field-' + task_id, 'Edited native task')
            wait(lambda s: s['tasks'] == 1, 'edit finished')
            assert json.loads(tasks.read_text())['tasks'][0]['text'] == 'Edited native task'
            ui('click', 'toggle-' + task_id)
            wait(lambda s: s['completed'] == 1, 'completion')
            ui('click', 'toggle-' + task_id)
            wait(lambda s: s['completed'] == 0, 'uncomplete')
            ui('click', 'delete-' + task_id)
            wait(lambda s: s['tasks'] == 0, 'delete')
            ui('click', 'undo-delete')
            wait(lambda s: s['tasks'] == 1, 'undo')
            assert json.loads(tasks.read_text())['tasks'][0]['id'] == task_id
            print('PASS native UI entry, edit, completion, delete and undo retain ID', flush=True)
            if os.environ.get('RICE_SMOKE_PROFILE') == 'end4-lite':
                assert json.loads(ipc('test', 'renderStats'))['shapeSize'] == 1
                ipc('test', 'centered', 'true')
                time.sleep(.8)
                assert json.loads(ipc('test', 'renderStats'))['shapeSize'] > 1
                ipc('test', 'centered', 'false')
                time.sleep(1.5)
                assert json.loads(ipc('test', 'renderStats'))['shapeSize'] == 1
                print('PASS disabled wallpaper masks stay unallocated; enabling and disabling works', flush=True)
            for index in range(24):
                assert ipc('desktop', 'task', 'add', json.dumps({'text': f'Native list item {index}'})) == 'true'
                wait(lambda s: s['tasks'] == index + 2, 'long list')
            last_id = json.loads(tasks.read_text())['tasks'][-1]['id']
            ui('last')
            ui('click', 'toggle-' + last_id)
            wait(lambda s: s['completed'] == 1, 'scroll to last task')
            print('PASS scrolling operates the last of 25 tasks', flush=True)
            ipc('test', 'move', 60, 510)
            ipc('test', 'resize', 380, 470)
            ipc('test', 'visibility', 'false')
            time.sleep(0.5)
            ipc('test', 'visibility', 'true')
            time.sleep(0.8)
            layout = json.loads(ipc('test', 'layout'))
            assert layout == dict(x=60, y=510, width=380, height=470), layout
            colors['accentPrimary'] = '#778899'
            atomic_json(palette, colors)
            wait(lambda s: s['accent'] == '#778899', 'palette update')
            palette.write_text('{partial')
            time.sleep(1.5)
            assert json.loads(ipc('desktop', 'status'))['accent'] == '#778899'
            atomic_json(palette, colors)
            wait(lambda s: s['accent'] == '#778899', 'palette recovery')
            print('PASS palette update, incomplete palette retention and recovery', flush=True)
            # Native panels load on demand and close without a persistent focus grab.
            for target, method in [('settings','open'), ('search','help'), ('wallpaperSelector','toggle'), ('sidebarRight','open')]:
                ipc(target, method)
                time.sleep(0.8)
                if target == 'wallpaperSelector': ipc(target, 'toggle')
                else: ipc(target, 'close')
            for method, group in [('colors', 'Interface'), ('barStyle', 'Bar'), ('barLayout', 'Bar')]:
                ipc('desktop', method)
                wait(lambda s: s['settings'] and s['dashboardPage'] == 4 and s['dashboardGroup'] == group, 'dashboard section navigation')
                time.sleep(1.5)
                assert int(ipc('dashboard-test', 'cards')) > 0, (method, group, 'Empty settings group')
                ipc('settings', 'close')
            print('PASS dashboard, targeted color/bar settings, native shortcut help, wallpaper and notifications IPC', flush=True)
            stop()
            process = start()
            wait(lambda s: s['tasks'] == 25, 'restart persistence')
            time.sleep(4)
            layout = json.loads(ipc('test', 'layout'))
            assert layout == dict(x=60, y=510, width=380, height=470), layout
            print('PASS task and moved/resized widget layout persistence after restart', flush=True)
            subprocess.run(['grim', '-o', output, '/tmp/rice-end4-verified.png'], check=True)
            tasks.write_text('{broken')
            ipc('desktop', 'refreshTasks')
            wait(lambda s: bool(s['error']), 'unreadable task data')
            assert tasks.read_text() == '{broken'
            print('PASS unreadable task data displays an error without overwrite', flush=True)
            log = (root / 'shell.log').read_text(errors='replace')
            errors = [line for line in log.splitlines() if 'Failed to load configuration' in line or 'ReferenceError:' in line or 'TypeError:' in line]
            assert not errors, '\n'.join(errors)
        except Exception:
            subprocess.run(['grim', '-o', output, '/tmp/rice-end4-failed.png'], check=False)
            shutil.copy2(root / 'shell.log', '/tmp/rice-end4-failed.log')
            shutil.copy2(root / 'commands.log', '/tmp/rice-end4-failed-commands.log')
            shutil.copy2(root / 'config/hyprland-rice/end4/config.json', '/tmp/rice-end4-failed-config.json')
            raise
        finally:
            stop()
            logfile.close()


def main():
    def monitors(): return json.loads(subprocess.check_output(['hyprctl', 'monitors', '-j'], text=True))
    before = monitors()
    original = next(m['name'] for m in before if m['focused'])
    before_names = {m['name'] for m in before}
    subprocess.run(['hyprctl', 'output', 'create', 'headless'], check=True, stdout=subprocess.DEVNULL)
    output = None
    try:
        for _ in range(40):
            names = {m['name'] for m in monitors()} - before_names
            if names: output = names.pop(); break
            time.sleep(0.05)
        assert output
        subprocess.run(['hyprctl', 'keyword', 'monitor', output + ',1920x1200@60,auto,1'], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['hyprctl', 'dispatch', 'focusmonitor', output], check=True, stdout=subprocess.DEVNULL)
        run(output)
    finally:
        subprocess.run(['hyprctl', 'dispatch', 'focusmonitor', original], check=False, stdout=subprocess.DEVNULL)
        if output: subprocess.run(['hyprctl', 'output', 'remove', output], check=True, stdout=subprocess.DEVNULL)


if __name__ == '__main__': main()
