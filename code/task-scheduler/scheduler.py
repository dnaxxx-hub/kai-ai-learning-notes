import threading
import time
from task import Task


class ScheduledTask:
    def __init__(self, name, task_name, args=None, kwargs=None,
                 interval=60, enabled=True):
        self.name = name
        self.task_name = task_name
        self.args = args or []
        self.kwargs = kwargs or {}
        self.interval = interval  # 秒数间隔
        self.enabled = enabled
        self.last_run = 0
        self.next_run = time.time()


class Scheduler:
    def __init__(self, task_queue):
        self.task_queue = task_queue
        self._tasks = []  # [ScheduledTask]
        self._lock = threading.Lock()
        self._running = False

    def add_task(self, name, task_name, args=None, kwargs=None, interval=60):
        st = ScheduledTask(name, task_name, args, kwargs, interval)
        with self._lock:
            self._tasks.append(st)
        return st

    def remove_task(self, name):
        with self._lock:
            self._tasks = [t for t in self._tasks if t.name != name]

    def start(self):
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            now = time.time()
            with self._lock:
                for st in self._tasks:
                    if st.enabled and now >= st.next_run:
                        task = Task(st.task_name, st.args, st.kwargs)
                        self.task_queue.put(task)
                        st.last_run = now
                        st.next_run = now + st.interval
            time.sleep(0.5)

    def list_tasks(self):
        with self._lock:
            return [{
                'name': t.name,
                'task_name': t.task_name,
                'interval': t.interval,
                'enabled': t.enabled,
                'last_run': t.last_run,
                'next_run': t.next_run,
            } for t in self._tasks]
