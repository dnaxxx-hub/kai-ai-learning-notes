import json, os, time, threading

class KVStore:
    """持久化键值存储，支持版本号和前缀查询"""
    def __init__(self, path='config_data'):
        self.path = path
        self._data = {}     # {key: (value, version, create_time, modify_time)}
        self._watchers = {} # {key: [callback, ...]} 前缀用 *
        self._lock = threading.Lock()
        os.makedirs(path, exist_ok=True)
        self._load()
    
    def put(self, key, value):
        with self._lock:
            if key in self._data:
                _, ver, ct, _ = self._data[key]
                self._data[key] = (value, ver + 1, ct, time.time())
            else:
                self._data[key] = (value, 1, time.time(), time.time())
            self._save()
            self._notify(key, value)
            return True
    
    def get(self, key):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            return {
                'key': key,
                'value': entry[0],
                'version': entry[1],
                'create_time': entry[2],
                'modify_time': entry[3],
            }
    
    def delete(self, key):
        with self._lock:
            if key not in self._data:
                return False
            del self._data[key]
            self._save()
            self._notify(key, None)
            return True
    
    def list_prefix(self, prefix):
        """前缀查询"""
        with self._lock:
            results = []
            for k in sorted(self._data.keys()):
                if k.startswith(prefix):
                    v = self._data[k]
                    results.append({
                        'key': k,
                        'value': v[0],
                        'version': v[1],
                    })
            return results
    
    def watch(self, key, callback):
        """注册监听器"""
        with self._lock:
            if key not in self._watchers:
                self._watchers[key] = []
            self._watchers[key].append(callback)
    
    def unwatch(self, key, callback):
        with self._lock:
            if key in self._watchers:
                self._watchers[key].remove(callback)
    
    def _notify(self, key, value):
        """通知所有匹配的监听器"""
        # 精确匹配
        for cb in self._watchers.get(key, []):
            try:
                cb({'key': key, 'value': value, 'type': 'update' if value is not None else 'delete'})
            except:
                pass
        
        # 前缀匹配（用 * 结尾）
        for watch_key, callbacks in list(self._watchers.items()):
            if watch_key.endswith('*') and key.startswith(watch_key[:-1]):
                for cb in callbacks:
                    try:
                        cb({'key': key, 'value': value, 'type': 'update'})
                    except:
                        pass
    
    def _save(self):
        filepath = os.path.join(self.path, 'kvstore.json')
        # Convert tuples to lists for JSON serialization
        data = {}
        for k, v in self._data.items():
            data[k] = list(v)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load(self):
        filepath = os.path.join(self.path, 'kvstore.json')
        if not os.path.exists(filepath):
            return
        with open(filepath) as f:
            raw = json.load(f)
        for k, v in raw.items():
            if isinstance(v, list) and len(v) == 4:
                self._data[k] = tuple(v)
            elif isinstance(v, dict):
                self._data[k] = (v.get('value', ''), v.get('version', 1), v.get('create_time', 0), v.get('modify_time', 0))
    
    def stats(self):
        with self._lock:
            return {'keys': len(self._data), 'watchers': sum(len(v) for v in self._watchers.values())}
