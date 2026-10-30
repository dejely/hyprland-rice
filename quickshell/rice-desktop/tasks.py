#!/usr/bin/env python3
"""Local task storage. Stdout is a single JSON response; no shell expansion."""
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
from datetime import datetime, timezone


def validate_task(task):
    if not isinstance(task, dict) or not all(k in task for k in ('id', 'text', 'done', 'created')):
        raise ValueError('Invalid task data. The existing file has been preserved.')
    if (not isinstance(task['id'], str) or not task['id']
            or not isinstance(task['text'], str) or not task['text'].strip()
            or type(task['done']) is not bool or not isinstance(task['created'], str)):
        raise ValueError('Invalid task data. The existing file has been preserved.')
    return task


def task_text(payload):
    value = payload.get('text')
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Write a task first; text cannot be empty.')
    return value.strip()


def read_tasks(path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('tasks'), list):
            raise ValueError()
        tasks = [validate_task(task) for task in data['tasks']]
        if len({t['id'] for t in tasks}) != len(tasks):
            raise ValueError()
        return tasks
    except (ValueError, TypeError, KeyError):
        raise ValueError('Cannot read tasks.json. Fix or restore the file; it has been preserved.') from None


def save_tasks(path, tasks):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.tasks-', delete=False) as out:
            temporary = Path(out.name)
            json.dump({'version': 1, 'tasks': tasks}, out, ensure_ascii=False, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def transact(path, action, payload):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (path.parent / '.tasks.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        tasks = read_tasks(path)
        deleted = None
        if action == 'list':
            return {'ok': True, 'tasks': tasks}
        if action == 'add':
            text = task_text(payload)
            tasks.append({'id': str(uuid.uuid4()), 'text': text, 'done': False,
                          'created': datetime.now(timezone.utc).isoformat()})
        elif action == 'restore':
            task = validate_task(payload['task'])
            if any(t['id'] == task['id'] for t in tasks):
                raise ValueError('This task is already restored.')
            tasks.insert(min(max(int(payload.get('index', len(tasks))), 0), len(tasks)), task)
        elif action in ('toggle', 'edit', 'delete'):
            index = next((i for i, t in enumerate(tasks) if t['id'] == payload.get('id')), None)
            if index is None:
                raise ValueError('Task no longer exists. Refresh the list.')
            if action == 'toggle':
                tasks[index]['done'] = not tasks[index]['done']
            elif action == 'edit':
                text = task_text(payload)
                tasks[index]['text'] = text
            else:
                deleted = {'task': tasks.pop(index), 'index': index}
        else:
            raise ValueError('Unknown task action.')
        save_tasks(path, tasks)
        return {'ok': True, 'tasks': tasks, 'deleted': deleted}


def main():
    try:
        directory = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'hyprland-rice'
        action = sys.argv[1] if len(sys.argv) > 1 else 'list'
        payload = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        if not isinstance(payload, dict):
            raise ValueError('Expected a task object.')
        result = transact(directory / 'tasks.json', action, payload)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
