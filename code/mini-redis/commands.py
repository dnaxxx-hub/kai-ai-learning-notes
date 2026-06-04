"""命令处理器 - SET/GET/DEL/EXISTS/EXPIRE/KEYS/FLUSHALL/PING/INFO"""


class CommandHandler:
    def __init__(self, store):
        self.store = store
        self.commands = {
            'PING': self._ping,
            'SET': self._set,
            'GET': self._get,
            'DEL': self._del,
            'EXISTS': self._exists,
            'EXPIRE': self._expire,
            'TTL': self._ttl,
            'KEYS': self._keys,
            'FLUSHALL': self._flushall,
            'DBSIZE': self._dbsize,
            'INFO': self._info,
        }
    
    def execute(self, cmd, args):
        handler = self.commands.get(cmd)
        if not handler:
            raise ValueError(f'ERR unknown command \'{cmd}\'')
        return handler(args)
    
    def _ping(self, args):
        return 'PONG'
    
    def _set(self, args):
        if len(args) < 2:
            raise ValueError('ERR wrong number of arguments for SET')
        key = args[0]
        value = args[1]
        expire_ms = None
        # 检查 PX 参数
        i = 2
        while i < len(args):
            if args[i].upper() == 'PX':
                if i + 1 < len(args):
                    expire_ms = int(args[i + 1])
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        self.store.set(key, value, expire_ms)
        return 'OK'
    
    def _get(self, args):
        if not args:
            raise ValueError('ERR wrong number of arguments for GET')
        return self.store.get(args[0])
    
    def _del(self, args):
        if not args:
            raise ValueError('ERR wrong number of arguments for DEL')
        return sum(1 for k in args if self.store.delete(k))
    
    def _exists(self, args):
        if not args:
            raise ValueError('ERR wrong number of arguments for EXISTS')
        return sum(1 for k in args if self.store.exists(k))
    
    def _expire(self, args):
        if len(args) < 2:
            raise ValueError('ERR wrong number of arguments for EXPIRE')
        return 1 if self.store.expire(args[0], int(args[1])) else 0
    
    def _ttl(self, args):
        if not args:
            raise ValueError('ERR wrong number of arguments for TTL')
        return self.store.ttl(args[0])
    
    def _keys(self, args):
        pattern = args[0] if args else '*'
        return self.store.keys(pattern)
    
    def _flushall(self, args):
        self.store.flushall()
        return 'OK'
    
    def _dbsize(self, args):
        return self.store.dbsize()
    
    def _info(self, args):
        info = self.store.info()
        return '\n'.join(f'{k}:{v}' for k, v in info.items())
