import json
import os
import heapq

from task import Task


class Storage:
    def __init__(self, path='task_queue_data'):
        self.path = path
        os.makedirs(path, exist_ok=True)

    def save(self, queue):
        """持久化所有任务"""
        tasks = [t.to_dict() for t in queue.get_all()]
        with open(os.path.join(self.path, 'tasks.json'), 'w') as f:
            json.dump(tasks, f, indent=2)

    def load(self, queue):
        """加载持久化的任务"""
        path = os.path.join(self.path, 'tasks.json')
        if not os.path.exists(path):
            return
        with open(path) as f:
            tasks = json.load(f)
        for td in tasks:
            task = Task.from_dict(td)
            queue._tasks[task.id] = task
            if task.status == Task.PENDING:
                heapq.heappush(
                    queue._queue,
                    (task.scheduled_at, task.priority, task.id, task),
                )

    def clear(self):
        """清空持久化文件"""
        path = os.path.join(self.path, 'tasks.json')
        if os.path.exists(path):
            os.remove(path)
