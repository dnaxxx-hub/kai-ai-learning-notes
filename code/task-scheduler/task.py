import uuid, time, json
from functools import wraps


class Task:
    """任务模型"""
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'
    RETRY = 'RETRY'

    def __init__(self, name, args=None, kwargs=None, task_id=None,
                 retries=0, max_retries=3, schedule_time=None, priority=0):
        self.task_id = task_id or str(uuid.uuid4())
        self.name = name
        self.args = args or []
        self.kwargs = kwargs or {}
        self.status = Task.PENDING
        self.result = None
        self.error = None
        self.retries = retries
        self.max_retries = max_retries
        self.priority = priority
        self.created_at = time.time()
        self.started_at = None
        self.completed_at = None
        self.schedule_time = schedule_time  # 定时执行时间戳
        self.worker_id = None

    def to_dict(self):
        return {
            'task_id': self.task_id,
            'name': self.name,
            'args': self.args,
            'kwargs': self.kwargs,
            'status': self.status,
            'result': self.result,
            'error': self.error,
            'retries': self.retries,
            'max_retries': self.max_retries,
            'priority': self.priority,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'schedule_time': self.schedule_time,
            'worker_id': self.worker_id,
        }

    @classmethod
    def from_dict(cls, d):
        t = cls(d['name'], d.get('args', []), d.get('kwargs', {}), d.get('task_id'))
        for k, v in d.items():
            setattr(t, k, v)
        return t


# 任务注册中心
_tasks = {}


def task(func=None, name=None, max_retries=3, priority=0):
    """装饰器：将函数注册为可调度的任务"""
    def decorator(f):
        task_name = name or f.__name__
        _tasks[task_name] = {
            'func': f,
            'name': task_name,
            'max_retries': max_retries,
            'priority': priority,
        }
        @wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)
        return wrapper
    return decorator(func) if func else decorator


def get_task_func(task_name):
    info = _tasks.get(task_name)
    if info:
        return info
    return None


def list_tasks():
    return list(_tasks.keys())
