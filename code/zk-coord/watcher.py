class WatcherManager:
    """Watched 通知管理"""

    def __init__(self):
        self._watchers = {}  # {(path, event_type): [callback, ...]}

    def watch(self, path, event_type, callback):
        """注册监听
        event_type: 'created' / 'deleted' / 'data_changed' / 'child_changed'
        """
        key = (path, event_type)
        if key not in self._watchers:
            self._watchers[key] = []
        self._watchers[key].append(callback)

    def unwatch(self, path, event_type, callback):
        key = (path, event_type)
        if key in self._watchers:
            self._watchers[key].remove(callback)
            if not self._watchers[key]:
                del self._watchers[key]

    def notify(self, path, event_type, extra=None):
        """触发通知"""
        callbacks = []
        # 直接路径通知
        key = (path, event_type)
        callbacks.extend(list(self._watchers.get(key, [])))

        # 父路径的 child_changed 也要通知
        parent_path = '/'.join(path.rstrip('/').split('/')[:-1]) or '/'
        parent_key = (parent_path, 'child_changed')
        callbacks.extend(list(self._watchers.get(parent_key, [])))

        for cb in callbacks:
            try:
                cb({'path': path, 'type': event_type, 'extra': extra})
            except Exception:
                pass
