import threading
import json
import os


class ResultBackend:
    def __init__(self, data_path='ts_data'):
        self._results = {}  # {task_id: task_dict}
        self._lock = threading.Lock()
        self.data_path = data_path
        os.makedirs(data_path, exist_ok=True)
        self._load()

    def set_result(self, task):
        with self._lock:
            self._results[task.task_id] = task.to_dict()
        self._save()

    def get_result(self, task_id):
        with self._lock:
            d = self._results.get(task_id)
            if d is not None:
                return d
            return None

    def list_results(self, limit=50, status=None):
        with self._lock:
            results = list(self._results.values())
            if status:
                results = [r for r in results if r['status'] == status]
            results.sort(key=lambda x: x.get('created_at', 0), reverse=True)
            return results[:limit]

    def clear(self):
        with self._lock:
            self._results.clear()
        self._save()

    def _save(self):
        path = os.path.join(self.data_path, 'results.json')
        with open(path, 'w') as f:
            with self._lock:
                json.dump(self._results, f, indent=2)

    def _load(self):
        path = os.path.join(self.data_path, 'results.json')
        if not os.path.exists(path):
            return
        with open(path) as f:
            data = json.load(f)
            self._results = data
