import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BACKEND = Path(__file__).resolve().parents[1] / 'quickshell/rice-desktop/tasks.py'
spec = importlib.util.spec_from_file_location('tasks', BACKEND)
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'hyprland-rice/tasks.json'

    def call(self, action, payload=None):
        return store.transact(self.path, action, payload or {})

    def test_lifecycle_and_restart(self):
        self.assertEqual(self.call('list')['tasks'], [])
        task = self.call('add', {'text': '  banana 🍌 "quote" $(literal) <b>text</b>  '})['tasks'][0]
        self.assertTrue(task['id'])
        self.assertEqual(self.call('toggle', {'id': task['id']})['tasks'][0]['done'], True)
        edited = self.call('edit', {'id': task['id'], 'text': 'Changed\nsecond line'})['tasks'][0]
        self.assertEqual(edited['text'], 'Changed\nsecond line')
        deleted = self.call('delete', {'id': task['id']})
        self.assertEqual(deleted['tasks'], [])
        restored = self.call('restore', deleted['deleted'])
        self.assertEqual(restored['tasks'], [edited])
        process = subprocess.run([sys.executable, str(BACKEND), 'list'],
                                 env=dict(os.environ, XDG_DATA_HOME=self.temp.name),
                                 capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(process.stdout)['tasks'], [edited])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_blank_edits_do_not_change_data(self):
        task = self.call('add', {'text': 'Keep me'})['tasks'][0]
        original = self.path.read_bytes()
        for action, payload in [('add', {'text': '  '}), ('add', {'text': 42}),
                                ('edit', {'id': task['id'], 'text': '\n'}),
                                ('edit', {'id': task['id'], 'text': None})]:
            with self.assertRaises(ValueError):
                self.call(action, payload)
            self.assertEqual(self.path.read_bytes(), original)

    def test_corrupt_files_are_preserved(self):
        self.path.parent.mkdir(parents=True)
        for content in ('', '{broken', '{"version":2,"tasks":[]}', '{"version":1,"tasks":[{"id":"x"}]}'):
            self.path.write_text(content)
            with self.assertRaises(ValueError):
                self.call('add', {'text': 'Must not overwrite'})
            self.assertEqual(self.path.read_text(), content)

    def test_concurrent_adds_do_not_lose_tasks(self):
        def add(i):
            subprocess.run([sys.executable, str(BACKEND), 'add', json.dumps({'text': f'Task {i}'})],
                           env=dict(os.environ, XDG_DATA_HOME=self.temp.name),
                           capture_output=True, check=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(add, range(30)))
        tasks = self.call('list')['tasks']
        self.assertEqual(len(tasks), 30)
        self.assertEqual(len({t['id'] for t in tasks}), 30)

    def test_failed_replace_preserves_original(self):
        from unittest.mock import patch
        self.call('add', {'text': 'Keep me'})
        original = self.path.read_bytes()
        with patch.object(store.os, 'replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.call('add', {'text': 'New task'})
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('.tasks-*')), [])


if __name__ == '__main__':
    unittest.main()
