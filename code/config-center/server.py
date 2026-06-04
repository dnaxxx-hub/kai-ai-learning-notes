import socket, selectors, json
from kvstore import KVStore
from lease import LeaseManager
from protocol import encode_response, decode_request


class ConfigServer:
    def __init__(self, host='0.0.0.0', port=8500, store_path='config_data'):
        self.host = host
        self.port = port
        self.store = KVStore(path=store_path)
        self.lease_mgr = LeaseManager(self.store)
        self.selector = selectors.DefaultSelector()
        self.buffers = {}
    
    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(50)
        sock.setblocking(False)
        self.selector.register(sock, selectors.EVENT_READ, self._accept)
        print(f"🟢 Config Center on {self.host}:{self.port}")
        self._run()
    
    def _accept(self, sock, mask):
        conn, addr = sock.accept()
        conn.setblocking(False)
        self.buffers[conn.fileno()] = b''
        self.selector.register(conn, selectors.EVENT_READ, self._read)
    
    def _read(self, conn, mask):
        try:
            data = conn.recv(4096)
            if not data:
                self._disconnect(conn)
                return
        except:
            self._disconnect(conn)
            return
        
        buf = self.buffers[conn.fileno()]
        buf += data
        self.buffers[conn.fileno()] = buf
        
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            self.buffers[conn.fileno()] = buf
            self._handle_request(conn, line.decode('utf-8', errors='ignore'))
    
    def _handle_request(self, conn, line):
        line = line.strip()
        if not line:
            return
        cmd, args = decode_request(line)
        
        if cmd == 'PUT':
            if len(args) < 2:
                conn.sendall(encode_response(False, error='PUT need key and value').encode())
                return
            key, value = args[0], ' '.join(args[1:])
            self.store.put(key, value)
            conn.sendall(encode_response(True, {'key': key, 'version': self.store.get(key)['version']}).encode())
        
        elif cmd == 'GET':
            if not args:
                conn.sendall(encode_response(False, error='GET need key').encode())
                return
            result = self.store.get(args[0])
            conn.sendall(encode_response(result is not None, result).encode())
        
        elif cmd == 'DEL':
            if not args:
                conn.sendall(encode_response(False, error='DEL need key').encode())
                return
            success = self.store.delete(args[0])
            conn.sendall(encode_response(success, {'deleted': success}).encode())
        
        elif cmd == 'LIST':
            prefix = args[0] if args else '/'
            results = self.store.list_prefix(prefix)
            conn.sendall(encode_response(True, results).encode())
        
        elif cmd == 'GRANT':
            ttl = int(args[0]) if args else 60
            lease = self.lease_mgr.grant(ttl)
            conn.sendall(encode_response(True, {'lease_id': lease.id, 'ttl': ttl}).encode())
        
        elif cmd == 'KEEPALIVE':
            if not args:
                conn.sendall(encode_response(False, error='KEEPALIVE need lease_id').encode())
                return
            ok = self.lease_mgr.keepalive(args[0])
            conn.sendall(encode_response(ok).encode())
        
        elif cmd == 'ATTACH':
            if len(args) < 2:
                conn.sendall(encode_response(False, error='ATTACH need lease_id key').encode())
                return
            ok = self.lease_mgr.attach_key(args[0], args[1])
            conn.sendall(encode_response(ok).encode())
        
        elif cmd == 'REVOKE':
            if not args:
                conn.sendall(encode_response(False, error='REVOKE need lease_id').encode())
                return
            ok = self.lease_mgr.revoke(args[0])
            conn.sendall(encode_response(ok).encode())
        
        elif cmd == 'STATS':
            s = self.store.stats()
            conn.sendall(encode_response(True, s).encode())
        
        else:
            conn.sendall(encode_response(False, error=f'Unknown command: {cmd}').encode())
    
    def _disconnect(self, conn):
        self.buffers.pop(conn.fileno(), None)
        try:
            self.selector.unregister(conn)
            conn.close()
        except:
            pass
    
    def _run(self):
        try:
            while True:
                events = self.selector.select()
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, mask)
        except KeyboardInterrupt:
            self.lease_mgr.stop()
            print("\n🛑 服务器关闭")
