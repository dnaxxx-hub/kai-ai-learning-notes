"""内存键值存储引擎，支持过期时间"""
import time
import re


class Store:
    """内存键值存储，支持过期时间"""
    
    def __init__(self):
        self._data = {}     # {key: value}
        self._expiry = {}   # {key: expire_at_timestamp (ms)}
    
    def set(self, key, value, expire_ms=None):
        self._data[key] = value
        if expire_ms is not None:
            self._expiry[key] = (time.time() * 1000) + expire_ms
        elif key in self._expiry:
            del self._expiry[key]
        return True
    
    def get(self, key):
        self._cleanup()
        if key in self._expiry and time.time() * 1000 >= self._expiry[key]:
            del self._data[key]
            del self._expiry[key]
            return None
        return self._data.get(key)
    
    def delete(self, key):
        existed = key in self._data
        self._data.pop(key, None)
        self._expiry.pop(key, None)
        return existed
    
    def exists(self, key):
        self._cleanup()
        return key in self._data
    
    def expire(self, key, ms):
        """设置过期时间（毫秒）"""
        self._cleanup()
        if key not in self._data:
            return False
        self._expiry[key] = (time.time() * 1000) + ms
        return True
    
    def ttl(self, key):
        """返回剩余 TTL（毫秒）"""
        self._cleanup()
        if key not in self._data:
            return -2
        if key not in self._expiry:
            return -1
        remaining = int(self._expiry[key] - time.time() * 1000)
        return max(0, remaining)
    
    def keys(self, pattern='*'):
        self._cleanup()
        regex = re.escape(pattern).replace(r'\*', '.*').replace(r'\?', '.')
        return [k for k in self._data if re.match(f'^{regex}$', k)]
    
    def flushall(self):
        self._data.clear()
        self._expiry.clear()
    
    def dbsize(self):
        self._cleanup()
        return len(self._data)
    
    def _cleanup(self):
        now = time.time() * 1000
        expired = [k for k, t in list(self._expiry.items()) if now >= t]
        for k in expired:
            del self._data[k]
            del self._expiry[k]
    
    def info(self):
        self._cleanup()
        return {
            'keys': len(self._data),
            'expired_keys': len(self._expiry),
        }
