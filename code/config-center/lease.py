import time, threading, uuid

class Lease:
    def __init__(self, lease_id, ttl, on_expire=None):
        self.id = lease_id
        self.ttl = ttl  # 秒
        self.created_at = time.time()
        self.last_keepalive = time.time()
        self.expired = False
        self.keys = set()  # 关联的键
        self.on_expire = on_expire
    
    def is_expired(self):
        if self.expired:
            return True
        now = time.time()
        if now - self.last_keepalive > self.ttl:
            self.expired = True
            if self.on_expire:
                self.on_expire(self)
            return True
        return False
    
    def keepalive(self):
        self.last_keepalive = time.time()
        self.expired = False
    
    def remaining_ttl(self):
        if self.expired:
            return 0
        return max(0, self.ttl - (time.time() - self.last_keepalive))


class LeaseManager:
    def __init__(self, kvstore=None):
        self.leases = {}  # {lease_id: Lease}
        self.kvstore = kvstore
        self._running = True
        self._thread = threading.Thread(target=self._expire_check, daemon=True)
        self._thread.start()
    
    def grant(self, ttl):
        lease_id = str(uuid.uuid4())[:8]
        lease = Lease(lease_id, ttl, self._on_expire)
        self.leases[lease_id] = lease
        return lease
    
    def keepalive(self, lease_id):
        lease = self.leases.get(lease_id)
        if lease:
            lease.keepalive()
            return True
        return False
    
    def revoke(self, lease_id):
        lease = self.leases.pop(lease_id, None)
        if lease:
            lease.expired = True
            # 删除关联键
            for key in list(lease.keys):
                if self.kvstore:
                    self.kvstore.delete(key)
            return True
        return False
    
    def attach_key(self, lease_id, key):
        lease = self.leases.get(lease_id)
        if lease and not lease.expired:
            lease.keys.add(key)
            return True
        return False
    
    def _on_expire(self, lease):
        for key in list(lease.keys):
            if self.kvstore:
                self.kvstore.delete(key)
        self.leases.pop(lease.id, None)
    
    def _expire_check(self):
        while self._running:
            for lease in list(self.leases.values()):
                lease.is_expired()  # 触发过期
            time.sleep(0.5)
    
    def stop(self):
        self._running = False
