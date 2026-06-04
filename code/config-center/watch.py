import threading, json

class WatchManager:
    """观察者/监听器管理 - key 变更通知"""
    
    def __init__(self, kvstore):
        self.kvstore = kvstore
        self._watchers = {}  # {watch_id: {'key': key, 'callback': func}}
        self._lock = threading.Lock()
        self._next_id = 0
    
    def watch(self, key, callback):
        """注册一个 watcher，返回 watch_id"""
        with self._lock:
            self._next_id += 1
            watch_id = f"w{self._next_id}"
            self._watchers[watch_id] = {'key': key, 'callback': callback}
            # 委托给 kvstore 的实际监听
            self.kvstore.watch(self._make_watch_key(key), self._make_dispatcher(watch_id))
            return watch_id
    
    def unwatch(self, watch_id):
        """取消监听"""
        with self._lock:
            return self._watchers.pop(watch_id, None) is not None
    
    def _make_watch_key(self, key):
        """将用户 key 转换为 kvstore 使用的 watch key"""
        return key  # 精确 key 或 key* 前缀
    
    def _make_dispatcher(self, watch_id):
        """创建分发回调"""
        def dispatcher(event):
            with self._lock:
                entry = self._watchers.get(watch_id)
                if entry:
                    cb = entry['callback']
                    try:
                        cb(event)
                    except:
                        pass
        return dispatcher
