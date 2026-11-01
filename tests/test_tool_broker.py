"""Exercise broker process ownership without starting a graphical shell."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'rice-core/target/release/rice-core'


class ToolBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=f'{self.bin}:/usr/bin',
                        XDG_RUNTIME_DIR=str(self.root / 'runtime'),
                        XDG_CONFIG_HOME=str(self.root / 'config'),
                        XDG_STATE_HOME=str(self.root / 'state'),
                        BROKER_TEST_PID=str(self.root / 'child.pid'))
        config = self.root / 'config/hyprland-rice/end4/config.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'bar': {'verbose': False}, 'keep': 42}))

    def tearDown(self):
        self.tmp.cleanup()

    def fake_qs(self, body):
        executable = self.bin / 'qs'
        executable.write_text('#!/bin/sh\nset -eu\n' + body)
        executable.chmod(0o755)

    def command(self):
        return [str(BIN), 'tool', str(self.root / 'tool-host.qml'), 'settings']

    def test_closed_tool_flushes_edits_and_reaps_child(self):
        self.fake_qs('echo $$ > "$BROKER_TEST_PID"\n'
                     'printf \'{"bar":{"verbose":true},"keep":42}\' > "$RICE_SETTINGS_PATH"\n'
                     'printf \'{"started":true,"open":false}\' > "$RICE_TOOL_STATUS"\n'
                     'exec sleep 30\n')
        result = subprocess.run(self.command(), env=self.env, capture_output=True,
                                text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        events = [json.loads(line) for line in result.stdout.splitlines()]
        edits = [edit for event in events if event['event'] == 'patch'
                 for edit in event['changes']]
        self.assertEqual(edits, [{'path': ['bar', 'verbose'], 'value': True}])
        self.assertEqual(events[-1]['event'], 'closed')
        self.assertFalse(Path('/proc/' + (self.root / 'child.pid').read_text().strip()).exists())

    def test_unexpected_child_failure_is_reported(self):
        self.fake_qs('exit 3\n')
        result = subprocess.run(self.command(), env=self.env, capture_output=True,
                                text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Transient UI exited unexpectedly', result.stderr)

    def test_killing_broker_terminates_tool(self):
        self.fake_qs('echo $$ > "$BROKER_TEST_PID"\nexec sleep 30\n')
        broker = subprocess.Popen(self.command(), env=self.env, stdin=subprocess.PIPE,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                if (self.root / 'child.pid').exists():
                    break
                time.sleep(.02)
            self.assertTrue((self.root / 'child.pid').exists())
            pid = (self.root / 'child.pid').read_text().strip()
            broker.kill()
            broker.wait(timeout=3)
            for _ in range(100):
                stat = Path(f'/proc/{pid}/stat')
                if not stat.exists() or stat.read_text().split()[2] == 'Z':
                    break
                time.sleep(.02)
            else:
                self.fail('Tool remained alive after its broker was killed')
        finally:
            if broker.poll() is None:
                broker.kill()
                broker.wait()
            broker.stdin.close()
